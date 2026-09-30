"""
The "grammar" the suggestion engine understands: which trigger phrases
introduce which attribute (slot), what kind of value each slot expects,
and how slots typically follow one another in a spoken/typed query.

This hand-authored grammar + transition table is the lightweight, fully
local stand-in for a trained intent model. It costs nothing to run, needs
no GPU/API, and is easy for a domain expert (not just an engineer) to
extend by adding a row.

Slot ids and `source` fields are kept identical to the real MongoDB
document shape (isin, issuer, coupon, maturity_year, rating, segment,
currency, issuer_location, yieldType) so the parser's output dict can be
handed straight to a query against that collection with no translation
layer.
"""

# Each slot definition:
#   id        - internal key, matches a field in the bond DSL / dataset
#   label     - human label shown in the suggestion dropdown
#   triggers  - phrases that, when the user just typed them, activate this
#               slot (longest phrases are matched first)
#   type      - "categorical" | "numeric_percent" | "numeric_year" | "direct"
#   source    - dataset field to pull candidate values from (categorical)
#   color     - UI tag color
#   direct_values - for "direct" slots, the fixed value list (also doubles
#               as the trigger words themselves, e.g. "Floating" both
#               triggers and fills the yieldType slot)

SLOTS = [
    {
        "id": "isin",
        "label": "ISIN",
        "triggers": ["isin"],
        "suggest_trigger": "isin",
        "type": "categorical",
        "source": "isin",
        "color": "#334155",
    },
    {
        "id": "issuer",
        "label": "Issuer",
        "triggers": ["from", "issued by", "issuer", "by"],
        "suggest_trigger": "from",
        "type": "categorical",
        "source": "issuer",
        "color": "#2563eb",
    },
    {
        "id": "segment",
        "label": "Segment",
        "triggers": ["from", "segment", "sector"],
        "suggest_trigger": "segment",
        "type": "categorical",
        "source": "segment",
        "color": "#7c3aed",
    },
    {
        "id": "issuer_location",
        "label": "Issuer location",
        "triggers": ["from", "in", "located in", "issuer location", "domiciled in"],
        "suggest_trigger": "from",
        "type": "categorical",
        "source": "issuer_location",
        "color": "#0891b2",
    },
    {
        "id": "yieldType",
        "label": "Yield type",
        "triggers": ["coupon type", "yield type"],
        "suggest_trigger": "coupon type",
        "type": "direct",
        "direct_values": ["Fixed", "Floating", "Zero Coupon"],
        "color": "#b45309",
    },
    {
        "id": "coupon",
        "label": "Coupon",
        "triggers": ["rate", "coupon", "yield", "coupon rate", "paying", "at", "yielding"],
        "suggest_trigger": "rate",
        # Each phrase ends either in an existing trigger word or in a
        # qualifier word (above/below/...) that _strip_trailing_qualifier
        # already reduces to one -- so these need no new detection logic,
        # they're purely extra phrasing offered at suggestion time.
        "phrases": ["with coupon rate above", "with coupon rate below", "yielding"],
        "type": "numeric_percent",
        "color": "#dc2626",
    },
    {
        "id": "rating",
        "label": "Rating",
        "triggers": ["rated", "rating"],
        "suggest_trigger": "rated",
        "phrases": ["rated above", "rated below"],
        "type": "categorical",
        "source": "rating",
        "color": "#65a30d",
    },
    {
        "id": "currency",
        "label": "Currency",
        "triggers": ["currency", "denominated in", "in"],
        "suggest_trigger": "currency",
        "phrases": ["denominated in", "priced in"],
        "type": "categorical",
        "source": "currency",
        "color": "#9333ea",
    },
    {
        "id": "maturity_year",
        "label": "Maturity",
        "triggers": [
            "maturing in", "maturing", "maturity", "due in", "matures in",
            "expiring in", "redeeming in",
        ],
        "suggest_trigger": "maturing in",
        "phrases": ["maturing after", "maturing before"],
        "type": "numeric_year",
        "color": "#c2410c",
    },
]

SLOT_BY_ID = {s["id"]: s for s in SLOTS}

# Maturity years at or beyond this are a known real-world convention for
# perpetual / undated notes (seen in the source data as e.g. 2174) rather
# than a literal redemption date. Display these as "Perpetual" instead of
# the raw year.
PERPETUAL_YEAR_THRESHOLD = 2100

# Qualifier words that turn a bare value into a range comparison.
GTE_WORDS = {
    "above", "over", "min", "at least", "more than", "greater than", "after",
}
LTE_WORDS = {
    "below", "under", "max", "at most", "less than", "up to", "before",
}

# Hand-authored "what tends to follow what" weights. Used only when no
# trigger word is being actively typed, to rank the *next* suggested
# trigger phrases contextually rather than alphabetically. This is the
# same role a bigram/transition model learned from real query logs would
# play once the system has usage data to train on.
TRANSITIONS = {
    None: {  # start of query
        "issuer": 10, "segment": 8, "issuer_location": 6, "rating": 3,
        "coupon": 3, "maturity_year": 2, "isin": 1,
    },
    "issuer": {
        "coupon": 9, "rating": 8, "maturity_year": 6, "segment": 4,
        "currency": 3, "yieldType": 3, "issuer_location": 2,
    },
    "segment": {
        "rating": 8, "coupon": 8, "maturity_year": 6, "issuer": 4,
        "currency": 3, "issuer_location": 3,
    },
    "issuer_location": {
        "coupon": 8, "rating": 7, "maturity_year": 6, "currency": 4,
        "segment": 3,
    },
    "yieldType": {
        "coupon": 8, "maturity_year": 5, "rating": 4,
    },
    "coupon": {
        "rating": 8, "maturity_year": 8, "yieldType": 5, "currency": 4,
    },
    "rating": {
        "maturity_year": 8, "coupon": 6, "currency": 4, "issuer_location": 3,
    },
    "currency": {
        "maturity_year": 7, "rating": 5, "coupon": 5,
    },
    "maturity_year": {
        "rating": 6, "coupon": 5, "currency": 3, "issuer_location": 2,
    },
}
