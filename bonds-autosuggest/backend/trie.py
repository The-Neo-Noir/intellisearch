"""
A small character-level trie for fast prefix lookups over categorical
attribute values (issuer names, segments, ratings, ...).

Why a trie at all, when the vocab per field is only a few hundred distinct
strings? Because it makes prefix lookup O(len(prefix)) instead of O(n),
which matters once this is fed by a live keystroke stream (every
character typed fires a lookup) and once real deployments have thousands
of issuers/ISINs rather than a few hundred. It's also the natural data
structure to swap in a compressed/disk-backed form (e.g. a DAWG) later
without changing the suggester's interface.
"""


class _Node:
    __slots__ = ("children", "payloads")

    def __init__(self):
        self.children = {}
        self.payloads = []  # list of (display_value, weight) stored at this
        # node's terminal point (usually just one, but duplicates collapse)


class Trie:
    def __init__(self):
        self.root = _Node()

    def insert(self, key, display_value, weight=1):
        """key is matched case-insensitively; display_value is what gets
        shown/inserted into the user's text."""
        node = self.root
        for ch in key.lower():
            node = node.children.setdefault(ch, _Node())
        node.payloads.append((display_value, weight))

    def _collect(self, node, limit):
        out = []
        stack = [node]
        while stack and len(out) < limit * 4:
            n = stack.pop()
            out.extend(n.payloads)
            stack.extend(n.children.values())
        return out

    def search_prefix(self, prefix, limit=8):
        """Returns up to `limit` (display_value, weight) pairs whose key
        starts with `prefix` (case-insensitive), sorted by weight desc."""
        node = self.root
        for ch in prefix.lower():
            if ch not in node.children:
                return []
            node = node.children[ch]
        results = self._collect(node, limit)
        # de-dupe by display value, keeping the max weight seen
        best = {}
        for val, w in results:
            if val not in best or w > best[val]:
                best[val] = w
        ranked = sorted(best.items(), key=lambda kv: -kv[1])
        return ranked[:limit]
