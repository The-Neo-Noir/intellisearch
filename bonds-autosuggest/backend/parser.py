"""
Incrementally parses whatever free text the user has typed so far into a
structured filter (the same shape the eventual DSL/JSON hand-off to the
existing query engine would use). This runs on every keystroke so the UI
can show a live "parsed query" preview -- which doubles as a bridge
towards phase 2 (NL -> DSL) since this dict essentially *is* a draft DSL.
"""
import re
from datetime import date

from .grammar import GTE_WORDS, LTE_WORDS, PERPETUAL_YEAR_THRESHOLD
from .vocab import get_vocab

_RATE_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_QUALIFIER_WORDS = r"(?:above|over|at least|more than|greater than|below|under|at most|less than|up to|min|max)"
_RATE_WORD_RE = re.compile(
    rf"(?:rate|coupon|yield)\s+(?:of\s+)?(?:{_QUALIFIER_WORDS}\s+)?(\d+(?:\.\d+)?)\b"
)
_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_REL_YEARS_RE = re.compile(r"\bin\s+(\d+)\s+years?\b")


def _qualifier_before(text_lower, pos, window=18):
    segment = text_lower[max(0, pos - window):pos]
    for w in GTE_WORDS:
        if w in segment:
            return "gte"
    for w in LTE_WORDS:
        if w in segment:
            return "lte"
    return None


def parse(text):
    """Returns a dict of slot_id -> value (scalar) or {"op","value"}."""
    text_l = text.lower()
    n = len(text)
    consumed = [False] * n
    result = {}

    def mark(s, e):
        for i in range(s, e):
            if 0 <= i < n:
                consumed[i] = True

    def is_free(s, e):
        return not any(consumed[s:e])

    # --- coupon ---
    for m in _RATE_PCT_RE.finditer(text):
        s, e = m.span()
        if is_free(s, e):
            qualifier = _qualifier_before(text_l, s)
            result["coupon"] = {"op": qualifier or "eq", "value": float(m.group(1))}
            mark(s, e)
            break
    if "coupon" not in result:
        m = _RATE_WORD_RE.search(text_l)
        if m:
            s, e = m.span(1)
            if is_free(s, e):
                qualifier = _qualifier_before(text_l, s)
                result["coupon"] = {"op": qualifier or "eq", "value": float(m.group(1))}
                mark(*m.span())

    # --- maturity year ---
    for m in _YEAR_RE.finditer(text):
        s, e = m.span()
        if is_free(s, e):
            qualifier = _qualifier_before(text_l, s)
            result["maturity_year"] = {"op": qualifier or "eq", "value": int(m.group(1))}
            mark(s, e)
            break
    if "maturity_year" not in result:
        m = _REL_YEARS_RE.search(text_l)
        if m:
            result["maturity_year"] = {"op": "eq", "value": date.today().year + int(m.group(1))}
            mark(*m.span())
        elif "next year" in text_l:
            idx = text_l.index("next year")
            result["maturity_year"] = {"op": "eq", "value": date.today().year + 1}
            mark(idx, idx + len("next year"))
        elif "perpetual" in text_l:
            # real-world convention seen in the source data: a note with
            # no fixed redemption date is stored with a far-future
            # sentinel year (e.g. 2174) rather than a null maturity.
            idx = text_l.index("perpetual")
            result["maturity_year"] = {"op": "gte", "value": PERPETUAL_YEAR_THRESHOLD}
            mark(idx, idx + len("perpetual"))

    # --- categorical / direct-value phrases (issuer, segment,
    # issuer_location, rating, currency, yieldType) ---
    vocab = get_vocab()
    for phrase, field, display in vocab.all_phrases:
        if not phrase or field in result:
            continue
        start = 0
        while True:
            idx = text_l.find(phrase, start)
            if idx == -1:
                break
            s, e = idx, idx + len(phrase)
            left_ok = s == 0 or not text_l[s - 1].isalnum()
            right_ok = e == len(text_l) or not text_l[e].isalnum()
            if left_ok and right_ok and is_free(s, e):
                result[field] = display
                mark(s, e)
                break
            start = idx + 1

    return result
