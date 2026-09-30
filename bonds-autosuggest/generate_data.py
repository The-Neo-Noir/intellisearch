"""
Builds the working dataset for the autosuggest prototype: the 6 real
documents pulled from the actual MongoDB collection, embedded verbatim,
plus a larger batch of synthetic bonds generated in the same shape (same
field names, same style of values) so the suggester has enough volume and
variety to demonstrate prefix/fuzzy matching, faceting, and ambiguous
triggers convincingly.

Run: python3 generate_data.py
Writes: data/bonds.json

The 6 real records are kept exactly as given, including data-quality
quirks visible in the source (e.g. Aegon Ltd's issuer_location is "US"
despite being a Dutch-origin insurer; the European Investment Bank record
similarly shows issuer_location "US"; the EIB ISIN "XS009467541" is only
11 characters, one short of a standard ISIN). These aren't "fixed" here
because they reflect what's actually in the collection -- a production
version of this should surface them as a data-quality flag, not silently
correct them.
"""
import json
import os
import random

random.seed(7)

# ---------------------------------------------------------------- real data --
# Verbatim from the MongoDB collection (yieldType/coupon/segment/etc. as given).
REAL_BONDS = [
    {
        "isin": "USG21776AB80",
        "issuer": "CK Hutchson International",
        "coupon": 4.5,
        "maturity_year": 2034,
        "rating": "AA+",
        "segment": "Retail",
        "currency": "USD",
        "issuer_location": "US",
        "yieldType": "Fixed",
    },
    {
        "isin": "US00287YEC93",
        "issuer": "AbbVie Inc",
        "coupon": 4.148081,
        "maturity_year": 2026,
        "rating": "A-",
        "segment": "Private",
        "currency": "USD",
        "issuer_location": "US",
        "yieldType": "Floating",
    },
    {
        "isin": "HK0000087145",
        "issuer": "Hong Kong Exchange Fund Note",
        "coupon": 2.07,
        "maturity_year": 2026,
        "rating": "AA-",
        "segment": "Bank",
        "currency": "HKD",
        "issuer_location": "HK",
        "yieldType": "Fixed",
    },
    {
        "isin": "XS3162348018",
        "issuer": "ABN AMRO Bank NV",
        "coupon": 4.892,
        "maturity_year": 2030,
        "rating": "A",
        "segment": "Bank",
        "currency": "AUD",
        "issuer_location": "NL",
        "yieldType": "Floating",
    },
    {
        "isin": "NL0000116150",
        "issuer": "Aegon Ltd",
        "coupon": 2.915,
        "maturity_year": 2174,  # perpetual-style sentinel, kept as-is
        "rating": "BBB-",
        "segment": "Private",
        "currency": "EUR",
        "issuer_location": "US",
        "yieldType": "Floating",
    },
    {
        "isin": "XS009467541",  # 11 chars in source; kept as-is
        "issuer": "European Investment Bank",
        "coupon": 0,
        "maturity_year": 2028,
        "rating": "AAA",
        "segment": "Private",
        "currency": "GBP",
        "issuer_location": "US",
        "yieldType": "Zero Coupon",
    },
]

# ------------------------------------------------------------ synthetic pool --
# (issuer, issuer_location, category) -- category only biases which segment /
# rating / coupon range / currency an issuer tends toward, it isn't a stored
# field (the real schema has no issuer_type).
ISSUERS = [
    ("Apple Inc", "US", "corporate"),
    ("Microsoft Corp", "US", "corporate"),
    ("JPMorgan Chase & Co", "US", "bank"),
    ("Bank of America Corp", "US", "bank"),
    ("Goldman Sachs Group", "US", "bank"),
    ("Pfizer Inc", "US", "corporate"),
    ("ExxonMobil Corp", "US", "corporate"),
    ("Verizon Communications", "US", "corporate"),
    ("Home Depot Inc", "US", "corporate"),
    ("General Electric Co", "US", "corporate"),
    ("US Treasury", "US", "sovereign"),
    ("HSBC Holdings plc", "GB", "bank"),
    ("Barclays Bank plc", "GB", "bank"),
    ("BP plc", "GB", "corporate"),
    ("Vodafone Group plc", "GB", "corporate"),
    ("GlaxoSmithKline plc", "GB", "corporate"),
    ("Lloyds Banking Group", "GB", "bank"),
    ("UK Treasury Gilt", "GB", "sovereign"),
    ("ABN AMRO Bank NV", "NL", "bank"),
    ("ING Groep NV", "NL", "bank"),
    ("Shell plc", "NL", "corporate"),
    ("Heineken NV", "NL", "corporate"),
    ("Deutsche Bank AG", "DE", "bank"),
    ("Siemens AG", "DE", "corporate"),
    ("Volkswagen AG", "DE", "corporate"),
    ("Allianz SE", "DE", "corporate"),
    ("KfW", "DE", "supranational"),
    ("BNP Paribas SA", "FR", "bank"),
    ("TotalEnergies SE", "FR", "corporate"),
    ("AXA SA", "FR", "corporate"),
    ("Societe Generale SA", "FR", "bank"),
    ("French Republic OAT", "FR", "sovereign"),
    ("CK Hutchison Holdings", "HK", "corporate"),
    ("HSBC Hong Kong", "HK", "bank"),
    ("MTR Corporation", "HK", "corporate"),
    ("Cathay Pacific Airways", "HK", "corporate"),
    ("Alibaba Group Holding", "CN", "corporate"),
    ("Tencent Holdings", "CN", "corporate"),
    ("Bank of China", "CN", "bank"),
    ("China Development Bank", "CN", "bank"),
    ("Toyota Motor Corp", "JP", "corporate"),
    ("Sony Group Corp", "JP", "corporate"),
    ("Mitsubishi UFJ Financial", "JP", "bank"),
    ("Japan Bank for International Cooperation", "JP", "supranational"),
    ("DBS Group Holdings", "SG", "bank"),
    ("Temasek Financial", "SG", "sovereign"),
    ("Singapore Airlines", "SG", "corporate"),
    ("OCBC Bank", "SG", "bank"),
    ("Commonwealth Bank of Australia", "AU", "bank"),
    ("BHP Group", "AU", "corporate"),
    ("Westpac Banking Corp", "AU", "bank"),
    ("Nestle SA", "CH", "corporate"),
    ("Roche Holding AG", "CH", "corporate"),
    ("UBS Group AG", "CH", "bank"),
    ("European Investment Bank", "LU", "supranational"),
    ("World Bank (IBRD)", "US", "supranational"),
    ("Asian Development Bank", "PH", "supranational"),
    ("African Development Bank", "CI", "supranational"),
    ("Hong Kong Exchange Fund Note", "HK", "sovereign"),
    ("AbbVie Inc", "US", "corporate"),
    ("Aegon Ltd", "US", "corporate"),
]

CURRENCY_BY_LOCATION = {
    "US": "USD", "GB": "GBP", "NL": "EUR", "DE": "EUR", "FR": "EUR",
    "HK": "HKD", "CN": "CNH", "JP": "JPY", "SG": "SGD", "AU": "AUD",
    "CH": "CHF", "LU": "EUR", "PH": "USD", "CI": "USD",
}
CROSS_BORDER_CURRENCIES = ["USD", "EUR", "GBP", "AUD", "HKD", "SGD", "CHF"]

RATINGS_IG_HIGH = ["AAA", "AA+", "AA", "AA-"]
RATINGS_IG_MID = ["A+", "A", "A-", "BBB+", "BBB"]
RATINGS_IG_LOW = ["BBB-"]
RATINGS_HY = ["BB+", "BB", "B+"]

SEGMENTS_BY_CATEGORY = {
    "sovereign": {"Sovereign": 0.7, "Bank": 0.2, "Private": 0.1},
    "supranational": {"Supranational": 0.7, "Private": 0.2, "Bank": 0.1},
    "bank": {"Bank": 0.6, "Private": 0.25, "Retail": 0.15},
    "corporate": {"Retail": 0.4, "Private": 0.35, "Corporate": 0.25},
}

PERPETUAL_YEARS = [2100, 2124, 2174]


def weighted_choice(weights_dict):
    keys = list(weights_dict.keys())
    weights = list(weights_dict.values())
    return random.choices(keys, weights=weights)[0]


def rating_for(category):
    if category in ("sovereign", "supranational"):
        pool = RATINGS_IG_HIGH if random.random() < 0.85 else RATINGS_IG_MID
    elif category == "bank":
        pool = random.choices(
            [RATINGS_IG_HIGH, RATINGS_IG_MID, RATINGS_IG_LOW],
            weights=[0.35, 0.5, 0.15],
        )[0]
    else:
        pool = random.choices(
            [RATINGS_IG_HIGH, RATINGS_IG_MID, RATINGS_IG_LOW, RATINGS_HY],
            weights=[0.2, 0.4, 0.2, 0.2],
        )[0]
    return random.choice(pool)


def coupon_for(category, yield_type):
    if yield_type == "Zero Coupon":
        return 0
    base = {
        "sovereign": (1.5, 4.5),
        "supranational": (1.0, 4.0),
        "bank": (2.5, 6.5),
        "corporate": (2.0, 7.5),
    }[category]
    val = round(random.uniform(*base), 3)
    return val


def isin_for(location, currency, idx):
    # Cross-currency bonds (a bond in a currency not native to the issuer's
    # home market) are conventionally issued as Eurobonds under the "XS"
    # ICSD prefix, mirroring the real ABN AMRO / EIB records.
    native_ccy = CURRENCY_BY_LOCATION.get(location)
    prefix = "XS" if currency != native_ccy else location
    body = "".join(random.choices("0123456789ABCDEFGHJKLMNPQRSTUVWXYZ", k=9))
    return f"{prefix}{body}{idx % 10}"


def build_synthetic(n=520):
    bonds = []
    for i in range(n):
        issuer, location, category = random.choice(ISSUERS)
        native_ccy = CURRENCY_BY_LOCATION.get(location, "USD")
        currency = native_ccy if random.random() < 0.6 else random.choice(CROSS_BORDER_CURRENCIES)
        yield_type = random.choices(
            ["Fixed", "Floating", "Zero Coupon"], weights=[0.62, 0.28, 0.10]
        )[0]
        coupon = coupon_for(category, yield_type)
        if random.random() < 0.02:
            maturity_year = random.choice(PERPETUAL_YEARS)
        else:
            maturity_year = random.randint(2025, 2048)
        rating = rating_for(category)
        segment = weighted_choice(SEGMENTS_BY_CATEGORY[category])
        bonds.append({
            "isin": isin_for(location, currency, i),
            "issuer": issuer,
            "coupon": coupon,
            "maturity_year": maturity_year,
            "rating": rating,
            "segment": segment,
            "currency": currency,
            "issuer_location": location,
            "yieldType": yield_type,
        })
    return bonds


if __name__ == "__main__":
    bonds = REAL_BONDS + build_synthetic()
    random.shuffle(bonds)
    out_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "bonds.json")
    with open(out_path, "w") as f:
        json.dump(bonds, f, indent=2)
    print(f"Generated {len(bonds)} bonds ({len(REAL_BONDS)} real + {len(bonds) - len(REAL_BONDS)} synthetic) -> {out_path}")
