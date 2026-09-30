"""
Phase 2: authoritative free-text -> DSL conversion via an LLM.

This is deliberately separate from `suggester.py` / `parser.py`. Those
exist to make *typing* pleasant (instant, local, one call per keystroke)
and their live "parsed" preview is a best-effort local guess -- it only
understands phrasing this hand-authored grammar anticipated. It will not
understand "triple a" -> AAA, "junk bonds" -> sub-investment-grade,
"long-dated" -> maturity far out, or any phrasing nobody enumerated.

That's precisely the job an LLM is good at, and precisely why it does not
belong on the hot per-keystroke path: this call is made *once*, when the
user submits/finalizes their query, not on every character typed.

Requires ANTHROPIC_API_KEY to be set in the environment. No SDK
dependency -- just a plain HTTPS POST via urllib (stdlib), consistent
with the rest of this prototype's zero-dependency approach.
"""
import json
import os
import urllib.error
import urllib.request

from .vocab import get_vocab

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")


def _enum(field, limit=60):
    vocab = get_vocab()
    return sorted(vocab.field_counts.get(field, {}).keys())[:limit]


def _system_prompt():
    ratings = _enum("rating")
    segments = _enum("segment")
    currencies = _enum("currency")
    locations = _enum("issuer_location")
    return f"""You convert a free-text bond search query into a single JSON filter object for a bond search system. This is the ONLY thing you do -- output strict JSON and nothing else: no prose, no markdown code fences, no explanation.

Only include keys the user's query actually mentions or clearly implies. Omit anything not mentioned.

Allowed keys and value shapes:
- "isin": string, as typed.
- "issuer": string. Match to a known issuer name if the query clearly refers to one; otherwise pass through what the user typed.
- "segment": one of {segments}
- "issuer_location": an ISO-2 country code, one of {locations}
- "currency": an ISO currency code, one of {currencies}
- "rating": one of {ratings}. Normalize spoken/informal rating language: "triple a" -> "AAA", "double a plus" -> "AA+", "single a minus" -> "A-", "junk" / "high yield" / "speculative grade" -> a sub-investment-grade rating such as "BB+", "investment grade" is unclear alone (don't guess a specific letter for it unless a number/direction is also given).
- "yieldType": one of ["Fixed", "Floating", "Zero Coupon"]. "floater" -> "Floating", "zero" -> "Zero Coupon".
- "coupon": {{"op": "eq" | "gte" | "lte", "value": <number>}}. This is a percentage (4.5 means 4.5%). "above/over/at least X%" -> gte. "below/under/at most X%" -> lte.
- "maturity_year": {{"op": "eq" | "gte" | "lte", "value": <year>}}. "after/later than YEAR" -> gte. "before YEAR" -> lte. "perpetual" / "undated" / "no fixed maturity" -> {{"op": "gte", "value": 2100}} (this dataset's convention for perpetual notes). "long-dated" with no explicit year -> use your judgement (e.g. gte current year + 15) rather than omitting it.

Respond with ONLY the JSON object.

Examples:
Query: "triple a rated bank bonds in euros"
{{"rating": "AAA", "segment": "Bank", "currency": "EUR"}}

Query: "junk bonds maturing after 2030"
{{"rating": "BB+", "maturity_year": {{"op": "gte", "value": 2031}}}}

Query: "perpetual floaters from ABN AMRO"
{{"issuer": "ABN AMRO Bank NV", "yieldType": "Floating", "maturity_year": {{"op": "gte", "value": 2100}}}}
"""


def _extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in model output: {text[:300]!r}")
    return json.loads(text[start:end + 1])


def to_dsl_with_llm(text, api_key=None, model=None, timeout=20):
    """Sends `text` to the LLM and returns the parsed DSL dict. Raises
    RuntimeError with a user-facing message on any failure (missing key,
    network error, bad response) -- callers should catch this and show it
    rather than let it propagate as a stack trace."""
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No ANTHROPIC_API_KEY set. Export it in your shell "
            "(export ANTHROPIC_API_KEY=sk-ant-...) and restart the server "
            "to enable AI-assisted parsing. Until then, this button won't work "
            "-- the per-keystroke suggestions above don't need it and keep working either way."
        )

    body = json.dumps({
        "model": model or DEFAULT_MODEL,
        "max_tokens": 400,
        "system": _system_prompt(),
        "messages": [{"role": "user", "content": text}],
    }).encode("utf-8")

    req = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"LLM API returned {exc.code}: {detail}")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach the LLM API: {exc.reason}")

    content_blocks = payload.get("content", [])
    text_out = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
    try:
        return _extract_json(text_out)
    except (ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(str(exc))
