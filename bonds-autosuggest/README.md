# Bonds Search — Autosuggest + LLM DSL Prototype

A working prototype of the bond search pipeline: context-aware, as-you-type
search suggestions (phase 1), plus an on-submit LLM call that converts the
finished free-text query into the real DSL/JSON (phase 2). Built against
the actual MongoDB document shape (isin, issuer, coupon, maturity_year,
rating, segment, currency, issuer_location, yieldType).

## Run it

Pure Python 3 standard library for phase 1 — nothing to `pip install`.
Phase 2 (the "Convert with AI" button) calls the Anthropic API and needs
`ANTHROPIC_API_KEY` set; without it, phase 1 works fully and phase 2 shows
a clear message instead of failing silently.

```
python3 generate_data.py         # writes data/bonds.json (6 real bonds + 520 synthetic, same shape)
export ANTHROPIC_API_KEY=sk-ant-...   # optional, only needed for "Convert with AI"
python3 -m backend.ws_server
```

Then open `http://localhost:8000`. Try typing:

- `bonds from ABN AMRO Bank NV rated A maturing in 2030`
- `bonds with rate above 4% currency USD`
- `floating rate bank bonds from HK`
- `zero coupon bonds from European Investment Bank`
- `perpetual bonds rated BBB-`

Watch the dropdown suggest completions as you type — including, once
you've typed enough for the engine to guess what's likely next (e.g.
`bonds from US `), multiple natural phrasings for the top-ranked next
attribute at once ("with coupon rate above", "with coupon rate below",
"yielding"), not just one bare trigger word. **Tab** accepts the
highlighted suggestion and keeps you typing; **Enter** submits the whole
query and runs it through "Convert with AI" — they're deliberately not
the same action.

Then try typing something the local grammar was never taught — `triple a
rated junk bank bonds from Europe` — and press **Enter** (or click
**Convert with AI**): the local "Local hint" panel above will show little
or nothing (it doesn't know "triple a" means AAA), while the LLM panel
below correctly produces `{"rating": "AAA", ...}` style output. That
contrast is the point of splitting the pipeline this way.

One more thing worth trying: type `bonds rate ` and notice it suggests
"above …" / "below …", not a specific percentage. That's deliberate — see
"No guessing numbers from live data" below.

## Why two tiers, and why the split matters

Earlier drafts of this prototype had the local parser's live preview
labeled as a "draft DSL" — implying it was a rough version of the real
thing. That was the wrong framing, and worth being explicit about, because
it changes what each piece is *for*:

- **Phase 1 (`suggester.py`, `parser.py`, `grammar.py`, `trie.py`,
  `fuzzy.py`)** exists to make **typing** pleasant: instant, deterministic,
  free, and it has to respond on every keystroke, so it cannot be an LLM
  call. It only ever understands phrasing this hand-authored grammar was
  explicitly taught. "AAA", "rated", "maturing in 2030" — yes. "triple a",
  "junk bonds", "floater" — no, and it shouldn't try to guess; the local
  "parsed" preview is now explicitly labeled a **hint**, not a DSL.
- **Phase 2 (`llm_dsl.py`)** exists to make the **final conversion**
  correct: it runs *once*, when the user is done typing, sends the raw
  text plus the actual schema/enum values to an LLM, and gets back
  authoritative DSL — including exactly the informal/spoken phrasing
  ("triple a" → `AAA`, "junk" → sub-investment-grade, "floater" →
  `Floating`) that a hand-rolled grammar would have to enumerate forever
  and still never fully catch. This is the right place to pay LLM
  latency/cost, because it happens once per search, not once per
  character.

Put differently: phase 1's job is *speed while typing*; phase 2's job is
*correctness of the final filter*. They were being conflated before —
now they're two separate code paths with two separate UI panels, and the
demo above is designed to make the difference visible.

The original comparison of ngram/trie vs. Elasticsearch vs. LLM (kept
below) is really a comparison of what's available *within* phase 1's
constraints, plus where phase 2 fits in:

| Layer | What it's good at | What it's bad at |
|---|---|---|
| **Trie / prefix index** | Sub-millisecond "starts with" lookups over a fixed vocabulary (issuers, ratings, currencies). Cheap, deterministic, trivially cacheable. | Doesn't understand *what kind of thing* the user is typing, or typos. |
| **Fuzzy match (edit distance)** | Recovers from typos and partial recall ("relince" → Reliance). | Needs a candidate shortlist first, or it's O(n) per keystroke. |
| **Grammar / slot-filling** | Understands *context* — "rate" precedes a number, "rated" precedes a rating, "from" is ambiguous between issuer/segment/location. | Has to be authored (or learned from query logs); never generalizes to phrasing nobody anticipated — see above. |
| **Elasticsearch** (completion suggester / edge n-grams) | Phase 1's ideas at production scale — millions of ISINs, low-latency fan-out, typo tolerance, faceted counts as infra you don't hand-roll. | Still not "understanding" — a faster substrate for the same trie ideas, not a replacement for the grammar layer or for phase 2. |
| **LLM** | Genuinely open-ended language understanding — this is phase 2, full stop. | Wrong tool for per-keystroke autocomplete: 100–1000ms+ latency and cost per call, which is exactly why it's on submit, not on every character. |

### No guessing numbers from live data

An earlier version of the coupon suggester ranked candidate percentages
("3.45%", "5%"...) by how often that *exact* value occurred in the current
dataset. That's wrong for a field like this: coupon is continuous (real
records have values like `4.148081`, not round numbers), the dataset is
described as huge and constantly changing, and "3.45% occurs today"
doesn't mean anything useful about the query the user is trying to write
— it would also require a live, constantly-refreshed frequency aggregate
just to power an autocomplete dropdown. Two fixes, both in
`_rate_candidates` (`backend/suggester.py`):

- **Once the user has typed a number**, neighboring suggestions are
  generated by simple arithmetic (±0.25/0.5/0.75/1.0 around what they
  typed), ranked by numeric distance — no dataset lookup at all.
- **Before they've typed a number**, the honest prediction isn't a
  specific value, it's the *comparison* — so the suggestions are "above"
  / "below", which is genuinely useful and true regardless of what's in
  the data today, next year, or at 100x the current volume.

Maturity year gets a lighter version of the same treatment: years are a
small, bounded set even at huge scale (a few decades), so checking which
years actually occur is cheap and legitimate — but ranking specific years
by how often they occur *right now* has the same staleness problem, just
milder. Suggestions there are ranked by proximity to today's date, and
the "most extreme" hints offered are the honest min/max of what actually
occurs (a cheap range check), never a "predicted" middle value implying
popularity it may not have tomorrow.

Production scaling path for phase 1, unchanged by any of the above: the
`Trie` class → Elasticsearch completion suggester / edge n-grams once
vocab size justifies it; the `difflib` fuzzy fallback → ES's built-in
fuzziness or a real Levenshtein automaton; the hand-authored
`TRANSITIONS` table in `grammar.py` → a bigram model learned from real
query logs once there's usage data.

## How it works

1. **Grammar** (`backend/grammar.py`): each searchable attribute as a
   "slot" — trigger words ("from", "rated", "maturing in"), value type
   (categorical / numeric / fixed set), and a transition table for what
   tends to follow what. Slot ids and `source` fields match the real
   document schema exactly (`isin`, `issuer`, `coupon`, `maturity_year`,
   `rating`, `segment`, `currency`, `issuer_location`, `yieldType`).
2. **Vocab** (`backend/vocab.py`): loads the dataset once, builds
   per-field frequency counts and a `Trie` per categorical field.
3. **Suggester** (`backend/suggester.py`), on every keystroke:
   - Finds the word being typed right now and what came just before it.
   - If the preceding word(s) exactly complete a trigger phrase, that
     slot is "active" — rank its values by trie prefix match, falling
     back to fuzzy match for typos.
   - **Ambiguous triggers handled explicitly**: "from" maps to issuer
     *and* segment *and* issuer location at once, tagged by type.
   - **Facet narrowing**: once earlier filters are set (e.g. issuer =
     Aegon Ltd), later suggestions for rating/coupon/maturity are scoped
     to bonds actually matching — including surfacing "Perpetual" as a
     maturity suggestion only when the scoped subset actually has one.
   - Recognizes values typed with **no trigger word at all** ("AAA",
     "Floating", a country code) — but only exact/near-exact matches to
     known values; this is the boundary phase 2 exists to push past.
   - Qualifier words ("above", "below", "after", "before"...) become
     range operators; "perpetual" is recognized as a maturity value
     (mapped to the ≥2100 sentinel-year convention seen in the source
     data — see Data below).
4. **Parser** (`backend/parser.py`): re-parses the whole query on every
   keystroke into the **local hint** dict — feeds the chip row and JSON
   preview panel. Explicitly not the final DSL (see above).
5. **LLM bridge** (`backend/llm_dsl.py`): the phase-2 call. Builds a
   system prompt from the *live* vocab (so it always reflects the actual
   dataset's enum values), calls the Anthropic Messages API via a plain
   `urllib` POST (no SDK dependency), and parses the JSON response.
   Raises a clear `RuntimeError` with setup instructions if
   `ANTHROPIC_API_KEY` isn't set, rather than crashing the connection.
6. **Transport** (`backend/ws_server.py`): one WebSocket endpoint, two
   message actions — `"suggest"` (phase 1, every keystroke) and
   `"llm_parse"` (phase 2, only sent when the user clicks "Convert with
   AI"). Built on `http.server` + `socket` + `hashlib`/`base64` (the RFC
   6455 handshake and frame format, by hand) because this was built
   somewhere with no package-index access — swapping it for FastAPI +
   `uvicorn` later is a couple of hours' work and doesn't touch anything
   in `backend/` above this file.

## Data

`generate_data.py` writes the **6 real documents exactly as given**
(verbatim field values, including visible data-quality quirks like
Aegon Ltd's and the European Investment Bank's `issuer_location` both
being "US" despite neither being a US entity, and the EIB ISIN
`XS009467541` being 11 characters instead of 12 — these are preserved,
not silently corrected, because a production version of this should
surface them as data-quality flags rather than launder them) plus ~520
synthetic bonds in the same shape for volume: global issuers across the
US, UK, EU, Hong Kong, China, Japan, Singapore, Australia and
Switzerland, plus a handful of sovereigns and supranationals, plausible
ISINs (including "XS" Eurobond-style prefixes for cross-currency issues,
matching the pattern in the real ABN AMRO and EIB records), and a small
share of perpetual/undated notes using the same ≥2100 sentinel-year
convention observed in the real Aegon record (maturity_year 2174).

**Assumption flagged**: the real sample's `segment` values (Retail,
Private, Bank) look like a distribution/sales channel rather than an
issuer-type classification — a corporate name like AbbVie appears under
"Private", not "Corporate". The synthetic data adds "Corporate",
"Sovereign" and "Supranational" as further segment values for demo
variety; if the real taxonomy is actually closed to
{Retail, Private, Bank}, that's a one-line change in
`generate_data.py`'s `SEGMENTS_BY_CATEGORY`.

## Known limitations / natural next steps

- **Ordinal comparisons on categorical fields** in the local hint: "rated
  below A" shows as `rating: A` there (qualifier dropped) — the LLM tier
  already handles this correctly, so this only matters if the local hint
  needs to become more literal-minded.
- **Chips are read-only**; click-to-remove needs the parser to track text
  spans per match, not just values.
- **Transition weights are hand-authored**, not learned from real query
  logs yet.
- **No negation** ("not rated AAA") in the local grammar — the LLM tier
  already handles it if asked; local-hint support would need a
  "not/excluding" qualifier slot.
- **The LLM call is synchronous** and blocks that one WebSocket
  connection's thread for its duration (a few hundred ms to a couple of
  seconds) — fine at prototype scale since it's on-demand and each
  connection has its own thread, but a production version should have a
  timeout/retry policy and probably a queue rather than a raw blocking
  call per request.
- **No caching** of LLM conversions — identical queries re-call the API.
  Trivial to add (hash the text, cache the DSL) once this sees real
  traffic patterns.

## File layout

```
generate_data.py         real (6) + synthetic (~520) dataset generator
data/bonds.json           generated dataset
backend/
  grammar.py              slots, triggers, transition weights
  vocab.py                 loads data, builds per-field counts + tries
  trie.py                   prefix trie
  fuzzy.py                  difflib-based fuzzy fallback
  parser.py                 free text -> local hint dict (NOT the final DSL)
  suggester.py               phase-1 engine tying it all together
  llm_dsl.py                 phase-2: text -> authoritative DSL via LLM
  ws_server.py                stdlib HTTP + WebSocket server, both actions
frontend/
  index.html, style.css, app.js    search box, dropdown, local-hint panel,
                                     "Convert with AI" panel
```
