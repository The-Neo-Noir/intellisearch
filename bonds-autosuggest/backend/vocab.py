"""
Loads the bond dataset once and derives everything the suggester needs:
 - per-field value frequency counts (for ranking "most common first")
 - a Trie per categorical field (for prefix lookup)
 - a flat list of every known phrase across all fields, longest-first,
   used by the incremental parser to recognize values in free text.
"""
import json
import os
from collections import Counter

from .trie import Trie
from .grammar import SLOTS

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "bonds.json")

CATEGORICAL_FIELDS = [s["source"] for s in SLOTS if s.get("source")]


class Vocab:
    def __init__(self, data_path=DATA_PATH):
        with open(data_path) as f:
            self.bonds = json.load(f)

        self.field_counts = {field: Counter() for field in CATEGORICAL_FIELDS}
        for bond in self.bonds:
            for field in CATEGORICAL_FIELDS:
                val = bond.get(field)
                if val:
                    self.field_counts[field][val] += 1

        self.tries = {}
        for field, counter in self.field_counts.items():
            trie = Trie()
            for value, count in counter.items():
                trie.insert(value, value, weight=count)
            self.tries[field] = trie

        self.maturity_years = sorted({b["maturity_year"] for b in self.bonds})
        self.year_counts = Counter(b["maturity_year"] for b in self.bonds)
        self.rate_counts = Counter(b["coupon"] for b in self.bonds if b.get("coupon") is not None)

        # Longest-phrase-first list for the free-text parser:
        # (lowercase phrase, field, canonical display value)
        phrases = []
        for field, counter in self.field_counts.items():
            for value in counter:
                phrases.append((value.lower(), field, value))
        for slot in SLOTS:
            if slot["type"] == "direct":
                for value in slot["direct_values"]:
                    phrases.append((value.lower(), slot["id"], value))
        phrases.sort(key=lambda t: -len(t[0]))
        self.all_phrases = phrases

    def top_values(self, field, limit=8):
        return self.field_counts.get(field, Counter()).most_common(limit)

    def candidates(self, field, limit=50):
        return list(self.field_counts.get(field, Counter()).items())[:limit]


_singleton = None


def get_vocab():
    global _singleton
    if _singleton is None:
        _singleton = Vocab()
    return _singleton
