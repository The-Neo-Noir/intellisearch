"""
Pure-stdlib fuzzy matching, used as a fallback when the user's partial
token doesn't prefix-match anything (typos, transpositions, partial
recall of a name). Uses difflib's Ratcliff/Obershelp ratio, which ships
with every Python install -- no rapidfuzz/Levenshtein dependency needed.
"""
from difflib import SequenceMatcher


def close_matches(query, candidates, limit=5, cutoff=0.6):
    """candidates: iterable of (display_value, weight). Returns up to
    `limit` (display_value, score) pairs scored by string similarity,
    tie-broken by weight."""
    if not query:
        return []
    q = query.lower()
    scored = []
    for val, weight in candidates:
        ratio = SequenceMatcher(None, q, val.lower()).ratio()
        # also reward matches on any individual word in a multi-word value
        # (e.g. "reliance" should score well against "Reliance Industries")
        word_ratio = max(
            (SequenceMatcher(None, q, w).ratio() for w in val.lower().split()),
            default=0,
        )
        score = max(ratio, word_ratio)
        if score >= cutoff:
            scored.append((val, score, weight))
    scored.sort(key=lambda t: (-t[1], -t[2]))
    return [(val, score) for val, score, _ in scored[:limit]]
