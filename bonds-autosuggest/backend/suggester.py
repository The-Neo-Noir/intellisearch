"""
The core "as-you-type" suggestion engine.

For every keystroke the frontend sends the full text plus the cursor
position. This module figures out:

  1. What the user is in the middle of typing right now (the current
     partial token), and what came immediately before it.
  2. Whether that context is inside a recognized "slot" (they just typed
     a trigger phrase like "rated" or "maturing in"), in which case we
     rank that slot's own values by prefix + fuzzy match.
  3. Otherwise, what to suggest next: completions of trigger phrases for
     attributes not yet mentioned (ranked by a contextual transition
     table so it *feels* like it understands typical query shape), plus
     direct entity recognition (typing "AAA" or "Reliance" straight off,
     with no trigger word at all).
  4. A live parse of the whole query into a draft filter dict (the DSL
     preview), so the UI can show chips and phase 2 has something to
     build on.

Everything here is deterministic and local: a trie + difflib fuzzy
fallback + a hand-authored grammar. No network call, no model weights.
"""
import re
from collections import Counter
from datetime import date

from .grammar import (
    SLOTS, SLOT_BY_ID, TRANSITIONS, GTE_WORDS, LTE_WORDS,
    PERPETUAL_YEAR_THRESHOLD,
)
from .vocab import get_vocab
from . import fuzzy

_TOKEN_RE = re.compile(r"\S+")


def _format_year(year):
    return "Perpetual" if year >= PERPETUAL_YEAR_THRESHOLD else str(year)


def _bond_matches_filter(bond, slot_id, value):
    if slot_id == "coupon":
        rate = bond.get("coupon")
        if rate is None:
            return False
        op, v = value.get("op", "eq"), value.get("value")
        if op == "gte":
            return rate >= v
        if op == "lte":
            return rate <= v
        return abs(rate - v) < 0.01
    if slot_id == "maturity_year":
        year = bond.get("maturity_year")
        op, v = value.get("op", "eq"), value.get("value")
        if op == "gte":
            return year >= v
        if op == "lte":
            return year <= v
        return year == v
    return bond.get(slot_id) == value


def _scoped_bonds(all_bonds, parsed, exclude=None):
    """Narrows the dataset to bonds matching every filter already parsed
    from the query, except the slot currently being filled -- this is
    what makes later suggestions faceted (e.g. once "AAA" and "PSU Bond"
    are set, coupon-rate suggestions only reflect rates that actually
    occur on AAA PSU bonds, not the whole universe). Falls back to the
    unfiltered set if the combination has zero matches, so a slightly
    odd combination never dead-ends the dropdown."""
    if not parsed:
        return all_bonds
    subset = all_bonds
    for slot_id, value in parsed.items():
        if slot_id == exclude:
            continue
        subset = [b for b in subset if _bond_matches_filter(b, slot_id, value)]
        if not subset:
            return all_bonds
    return subset


def _tokenize_prefix(text, cursor):
    """Returns (prior_tokens, current_token_text, current_start)."""
    prefix = text[:cursor]
    matches = list(_TOKEN_RE.finditer(prefix))
    if matches and matches[-1].end() == cursor:
        current = matches.pop()
        return matches, current.group(), current.start()
    return matches, "", cursor


def _build_trigger_table():
    """Returns dict phrase -> [slots] for quick membership testing,
    built once at startup (cheap: ~10 slots, ~25 trigger phrases)."""
    table = {}
    for slot in SLOTS:
        for trig in slot["triggers"]:
            table.setdefault(trig.lower(), []).append(slot)
    return table


_ALL_QUALIFIERS = sorted(GTE_WORDS | LTE_WORDS, key=lambda p: -len(p.split()))


def _strip_trailing_qualifier(words):
    """A qualifier word ("above", "at least", ...) can sit between a
    trigger and the value ("rate above 7", "rated below AA"). Strip it
    from the tail so trigger detection still sees the value slot as
    active right after it. Longest phrases checked first."""
    for q in _ALL_QUALIFIERS:
        qw = q.split()
        n = len(qw)
        if n <= len(words) and [w for w in words[-n:]] == qw:
            return words[:-n]
    return words


def _detect_active_slots(prior_words, trigger_table):
    """If the most recent word(s) exactly complete a trigger phrase,
    return (matching_slots, k) where k is how many trailing words formed
    the trigger. Longer (more specific) triggers win over shorter ones."""
    for k in (3, 2, 1):
        if k > len(prior_words):
            continue
        phrase = " ".join(prior_words[-k:])
        if phrase in trigger_table:
            return trigger_table[phrase], k
    return [], 0


def _rightmost_trigger_slot(prior_words, trigger_table):
    """Scans the whole prefix (not just the tail) for the trigger phrase
    that ends closest to the cursor. Used as the "what have we most
    recently been talking about" signal for the transition table."""
    best_end = -1
    best_slot = None
    for end in range(1, len(prior_words) + 1):
        for k in (3, 2, 1):
            start = end - k
            if start < 0:
                continue
            phrase = " ".join(prior_words[start:end])
            if phrase in trigger_table:
                if end > best_end:
                    best_end = end
                    best_slot = trigger_table[phrase][0]["id"]
    return best_slot


def _value_suggestion(value, slot, score, kind):
    return {
        "insert": f"{value} ",
        "display": f"{slot['label']}: {value}",
        "slot": slot["id"],
        "slot_label": slot["label"],
        "color": slot["color"],
        "kind": kind,
        "score": score,
    }


def _trigger_suggestion(trigger_text, slots, score):
    labels = "/".join(s["label"] for s in slots)
    return {
        "insert": f"{trigger_text} ",
        "display": trigger_text,
        "slot": slots[0]["id"] if len(slots) == 1 else [s["id"] for s in slots],
        "slot_label": labels,
        "color": slots[0]["color"],
        "kind": "trigger",
        "score": score,
    }


def _categorical_candidates(slot, current_token, vocab, bonds, limit=6):
    field = slot["source"]
    full_scope = bonds is vocab.bonds
    if full_scope:
        # fast path over the whole corpus: prebuilt trie, O(len(prefix))
        trie = vocab.tries.get(field)
        counts_items = vocab.candidates(field)
        top_items = vocab.top_values(field, limit=limit)
    else:
        # narrower facet: cheap to just count the (already small) subset
        counts = Counter(b.get(field) for b in bonds if b.get(field))
        if not counts:
            counts = vocab.field_counts.get(field, Counter())
        trie = None
        counts_items = list(counts.items())
        top_items = counts.most_common(limit)

    out = []
    if current_token:
        if trie:
            prefix_matches = trie.search_prefix(current_token, limit=limit)
        else:
            prefix_matches = sorted(
                ((v, c) for v, c in counts_items if v.lower().startswith(current_token.lower())),
                key=lambda t: -t[1],
            )[:limit]
        seen = {v for v, _ in prefix_matches}
        for val, weight in prefix_matches:
            out.append(_value_suggestion(val, slot, 1000 + weight, "value"))
        if len(out) < limit:
            fuzzy_matches = fuzzy.close_matches(
                current_token, counts_items, limit=limit - len(out)
            )
            for val, sim in fuzzy_matches:
                if val in seen:
                    continue
                out.append(_value_suggestion(val, slot, 400 * sim, "value-fuzzy"))
    else:
        for val, count in top_items:
            out.append(_value_suggestion(val, slot, 900 + count, "value"))
    return out


def _direct_candidates(slot, current_token, bonds=None, limit=4):
    values = slot["direct_values"]
    counts = Counter()
    if bonds is not None:
        field = slot["id"]
        counts = Counter(b.get(field) for b in bonds if b.get(field) in values)
    weight_of = lambda v: counts.get(v, 0)
    out = []
    if current_token:
        pref = sorted(
            (v for v in values if v.lower().startswith(current_token.lower())),
            key=lambda v: -weight_of(v),
        )
        for v in pref:
            out.append(_value_suggestion(v, slot, 1000 + weight_of(v), "value"))
        if not pref:
            for v, sim in fuzzy.close_matches(current_token, [(v, 1) for v in values], limit=limit):
                out.append(_value_suggestion(v, slot, 400 * sim, "value-fuzzy"))
    else:
        for v in sorted(values, key=lambda v: -weight_of(v)):
            out.append(_value_suggestion(v, slot, 900 + weight_of(v), "value"))
    return out


_NICE_RATE_DELTAS = [0.25, -0.25, 0.5, -0.5, 0.75, -0.75, 1.0, -1.0]


def _rate_candidates(slot, current_token, vocab, bonds, limit=6):
    """Deliberately does NOT rank by which exact coupon values happen to
    exist in the current dataset. Coupon is a continuous value on a
    dataset that can be huge and changing in real time -- "3.45% exists
    today" is not a meaningful signal, it's just noise that would need a
    live frequency aggregate to be kept fresh forever. Instead:
      - once the user has typed a number, offer round neighboring values
        purely arithmetically (nearest first);
      - before that, predict the *comparison* they're about to make
        ("above"/"below"), which is genuinely useful and true regardless
        of what the data looks like today or next year.
    """
    out = []
    if current_token and re.match(r"^\d", current_token):
        try:
            base = float(current_token)
        except ValueError:
            base = None
        if base is not None:
            out.append(_value_suggestion(f"{base:g}%", slot, 1000, "value"))
            seen = {round(base, 2)}
            near = []
            for d in _NICE_RATE_DELTAS:
                r = round(base + d, 2)
                if r < 0 or r in seen:
                    continue
                seen.add(r)
                near.append(r)
            near.sort(key=lambda r: abs(r - base))
            for r in near[:max(0, limit - 1)]:
                out.append(_value_suggestion(f"{r:g}%", slot, 900 - abs(r - base) * 10, "value"))
            return out
    for label, score in (("above", 900), ("below", 880)):
        out.append({
            "insert": f"{label} ",
            "display": f"{slot['label']}: {label} …",
            "slot": slot["id"],
            "slot_label": slot["label"],
            "color": slot["color"],
            "kind": "trigger",
            "score": score,
        })
    return out


def _year_candidates(slot, current_token, vocab, bonds, limit=6):
    """Unlike coupon, a maturity year genuinely is a small, bounded set
    (a few decades) even over a huge live dataset, so checking which
    years actually occur -- or the min/max range -- is a cheap,
    legitimate lookup, not a fragile live aggregate. What we deliberately
    avoid is ranking specific years by how often they occur *right now*:
    that's the same "matches today's data" trap as coupon, just milder.
    Ranking is by proximity to today instead.
    """
    out = []
    this_year = date.today().year
    years = sorted({b["maturity_year"] for b in bonds} if bonds else vocab.maturity_years)
    if not years:
        years = vocab.maturity_years
    concrete_years = [y for y in years if y < PERPETUAL_YEAR_THRESHOLD]
    has_perpetual = len(concrete_years) < len(years)

    if current_token and current_token.isdigit():
        matches = sorted(
            {y for y in years if str(y).startswith(current_token)},
            key=lambda y: abs(y - this_year),
        )
        seen_labels = set()
        for y in matches:
            label = _format_year(y)
            if label in seen_labels:
                continue
            seen_labels.add(label)
            out.append(_value_suggestion(label, slot, 900 - abs(y - this_year), "value"))
            if len(out) >= limit:
                break
        return out
    if current_token and "perpetual".startswith(current_token.lower()) and has_perpetual:
        out.append(_value_suggestion("Perpetual", slot, 950, "value"))
        return out
    if not current_token:
        for label, year in [
            ("next year", this_year + 1),
            ("in 3 years", this_year + 3),
            ("in 5 years", this_year + 5),
            ("in 10 years", this_year + 10),
        ]:
            out.append({
                "insert": f"{label} ",
                "display": f"{slot['label']}: {label} ({year})",
                "slot": slot["id"],
                "slot_label": slot["label"],
                "color": slot["color"],
                "kind": "value",
                "score": 850,
            })
        if has_perpetual:
            out.append({
                "insert": "perpetual ",
                "display": f"{slot['label']}: Perpetual",
                "slot": slot["id"],
                "slot_label": slot["label"],
                "color": slot["color"],
                "kind": "value",
                "score": 830,
            })
        # Boundary hints, not guesses: the earliest/latest maturity that
        # actually occurs is a cheap min/max lookup, not a frequency
        # aggregate -- fundamentally different from "predicting" a value.
        if concrete_years:
            out.append(_value_suggestion(
                str(min(concrete_years)), slot, 810, "value"
            ))
            if max(concrete_years) != min(concrete_years):
                out.append(_value_suggestion(
                    str(max(concrete_years)), slot, 800, "value"
                ))
    return out


class Suggester:
    def __init__(self):
        self.vocab = get_vocab()
        self.trigger_table = _build_trigger_table()

    def suggest(self, text, cursor=None):
        from .parser import parse  # local import avoids a circular import

        if cursor is None or cursor > len(text):
            cursor = len(text)
        prior_tokens, current_token, current_start = _tokenize_prefix(text, cursor)
        prior_words = [t.group().lower() for t in prior_tokens]

        parsed = parse(text)
        stripped_words = _strip_trailing_qualifier(prior_words)
        active_slots, k = _detect_active_slots(stripped_words, self.trigger_table)

        candidates = []
        if active_slots:
            for slot in active_slots:
                if slot["type"] == "numeric_percent":
                    # coupon suggestions are pure arithmetic (see
                    # _rate_candidates) -- no need to filter the dataset
                    # at all, which matters once it's huge.
                    candidates.extend(_rate_candidates(slot, current_token, self.vocab, None))
                    continue
                scoped = _scoped_bonds(self.vocab.bonds, parsed, exclude=slot["id"])
                if slot["type"] == "categorical":
                    candidates.extend(_categorical_candidates(slot, current_token, self.vocab, scoped))
                elif slot["type"] == "direct":
                    candidates.extend(_direct_candidates(slot, current_token, scoped))
                elif slot["type"] == "numeric_year":
                    candidates.extend(_year_candidates(slot, current_token, self.vocab, scoped))
        else:
            last_slot = _rightmost_trigger_slot(prior_words, self.trigger_table)
            transitions = TRANSITIONS.get(last_slot, TRANSITIONS[None])

            # group slots that share the same suggested trigger phrase
            # (e.g. "from" covers issuer/segment/state) into one entry
            by_trigger = {}
            for slot in SLOTS:
                if slot["id"] in parsed:
                    continue  # already filled, don't re-suggest its trigger
                trig = slot.get("suggest_trigger")
                if not trig:
                    continue
                by_trigger.setdefault(trig, []).append(slot)

            for trig, slots in by_trigger.items():
                if current_token and not trig.startswith(current_token.lower()):
                    continue
                weight = max(transitions.get(s["id"], 1) for s in slots)
                candidates.append(_trigger_suggestion(trig, slots, 100 + weight * 10))

            if not current_token:
                # "predict the next few words", not just the next word:
                # for the single most likely next attribute, also offer
                # its alternate natural phrasings (e.g. after "from US",
                # coupon ranks highest -> show "with coupon rate above",
                # "with coupon rate below", "yielding" alongside the bare
                # "rate" suggestion, not instead of it).
                single_slot_groups = [
                    (trig, slots[0]) for trig, slots in by_trigger.items() if len(slots) == 1
                ]
                if single_slot_groups:
                    top_trig, top_slot = max(
                        single_slot_groups,
                        key=lambda ts: transitions.get(ts[1]["id"], 1),
                    )
                    base_weight = transitions.get(top_slot["id"], 1)
                    for i, phrase in enumerate(top_slot.get("phrases", [])[:3]):
                        if phrase == top_trig:
                            continue
                        candidates.append({
                            "insert": f"{phrase} ",
                            "display": phrase,
                            "slot": top_slot["id"],
                            "slot_label": top_slot["label"],
                            "color": top_slot["color"],
                            "kind": "trigger",
                            "score": 100 + base_weight * 10 - (i + 1),
                        })

            if current_token:
                # direct entity recognition: no trigger word needed at all
                scoped = _scoped_bonds(self.vocab.bonds, parsed)
                for slot in SLOTS:
                    if slot["id"] in parsed:
                        continue
                    if slot["type"] == "categorical":
                        matches = _categorical_candidates(slot, current_token, self.vocab, scoped, limit=3)
                        for m in matches:
                            m["score"] *= 0.6  # trigger-guided matches still rank a bit higher
                        candidates.extend(matches)
                    elif slot["type"] == "direct":
                        candidates.extend(_direct_candidates(slot, current_token, scoped, limit=3))

        candidates.sort(key=lambda c: -c["score"])
        top = candidates[:8]
        for c in top:
            c.pop("score", None)

        active_slot_labels = None
        if active_slots:
            active_slot_labels = "/".join(s["label"] for s in active_slots)

        return {
            "suggestions": top,
            "parsed": _format_parsed(parsed),
            "active_slot": active_slot_labels,
            "replace_span": [current_start, cursor],
            "current_token": current_token,
        }


def _format_parsed(parsed):
    """Render the internal parse into a friendly {label: text} dict for
    the chip UI, and keep the raw DSL alongside it."""
    chips = []
    for slot_id, value in parsed.items():
        slot = SLOT_BY_ID.get(slot_id)
        label = slot["label"] if slot else slot_id
        if isinstance(value, dict):
            op = value.get("op", "eq")
            v = value.get("value")
            symbol = {"gte": "≥", "lte": "≤", "eq": "="}.get(op, "=")
            if slot_id == "coupon":
                text = f"{symbol} {v}%"
            elif slot_id == "maturity_year" and v >= PERPETUAL_YEAR_THRESHOLD:
                text = "Perpetual"
            else:
                text = f"{symbol} {v}"
        else:
            text = str(value)
        color = slot["color"] if slot else "#6b7280"
        chips.append({"slot": slot_id, "label": label, "text": text, "color": color})
    return {"chips": chips, "dsl": parsed}


_singleton = None


def get_suggester():
    global _singleton
    if _singleton is None:
        _singleton = Suggester()
    return _singleton
