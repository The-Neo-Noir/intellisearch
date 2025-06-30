import json
import os
import re

DATA_DIR = os.path.dirname(__file__) + "/data"
USERS_FILE = os.path.join(DATA_DIR, "synthetic_users.json")

def get_frontier_profile(user_id):
    with open(USERS_FILE) as f:
        users = json.load(f)
    for user in users:
        if user["user_id"] == user_id:
            return user
    return {}

def parse_query_with_llm(query: str, user_id: str = None):
    filters = {
        "issuer": None,
        "currency": None,
        "return": None,
        "duration": None,
        "segment": None,
        "industry": None,
        "country": None,
        "maturity_date": None,
        "coupon_rate": None,
        "credit_rating": None,
        "callable": None,
        "puttable": None,
        "seniority": None,
        "secured": None,
        "tax_status": None,
        "min_investment": None,
        "frequency": None,
        "listing_exchange": None,
        "type": None,
        "subordination": None,
        "convertible": None,
        "perpetual": None,
        "green_bond": None,
        "sinking_fund": None,
        "market": None,
        "face_value": None
    }
    q = query.lower()

    # Issuer
    for issuer in ["hsbc", "dbs", "icici"]:
        if issuer in q:
            filters["issuer"] = issuer.upper()

    # Currency
    for currency in ["sgd", "usd", "inr"]:
        if currency in q:
            filters["currency"] = currency.upper()

    # Return/Yield
    if "high yield" in q or "high return" in q:
        filters["return"] = "high"
    elif "medium return" in q or "medium yield" in q:
        filters["return"] = "medium"
    elif "low return" in q or "low yield" in q:
        filters["return"] = "low"

    # Duration
    if "long duration" in q or "long term" in q:
        filters["duration"] = "long"
    elif "short duration" in q or "short term" in q:
        filters["duration"] = "short"
    elif "medium duration" in q or "medium term" in q:
        filters["duration"] = "medium"

    # Segment/Industry
    if "corporate" in q:
        filters["segment"] = "Corporate"
    if "sovereign" in q:
        filters["segment"] = "Sovereign"
    if "banking" in q:
        filters["industry"] = "Banking"
    if "finance" in q:
        filters["industry"] = "Finance"
    if "energy" in q:
        filters["industry"] = "Energy"
    if "technology" in q:
        filters["industry"] = "Technology"

    # Country/Market
    if "india" in q or "indian" in q:
        filters["country"] = "India"
        filters["market"] = "Primary"
        filters["currency"] = filters["currency"] or "INR"
    if "singapore" in q or "sgx" in q:
        filters["country"] = "Singapore"
        filters["market"] = "Primary"
        filters["currency"] = filters["currency"] or "SGD"
    if "usa" in q or "us" in q or "nyse" in q:
        filters["country"] = "USA"
        filters["market"] = "Primary"
        filters["currency"] = filters["currency"] or "USD"

    # Green bond
    if "green bond" in q or "green bonds" in q:
        filters["green_bond"] = True

    # Callable/Puttable
    if "callable" in q:
        filters["callable"] = True
    if "puttable" in q:
        filters["puttable"] = True

    # Seniority
    if "senior" in q:
        filters["seniority"] = "Senior"
    if "subordinated" in q:
        filters["seniority"] = "Subordinated"

    # Secured
    if "secured" in q:
        filters["secured"] = True

    # Tax status
    if "tax-free" in q:
        filters["tax_status"] = "Tax-Free"
    if "taxable" in q:
        filters["tax_status"] = "Taxable"

    # Frequency
    if "annual" in q:
        filters["frequency"] = "Annual"
    if "semi-annual" in q:
        filters["frequency"] = "Semi-Annual"
    if "quarterly" in q:
        filters["frequency"] = "Quarterly"

    # Listing exchange
    if "sgx" in q:
        filters["listing_exchange"] = "SGX"
    if "nse" in q:
        filters["listing_exchange"] = "NSE"
    if "nyse" in q:
        filters["listing_exchange"] = "NYSE"

    # Type
    if "fixed" in q:
        filters["type"] = "Fixed"
    if "floating" in q:
        filters["type"] = "Floating"

    # Convertible/Perpetual/Sinking fund
    if "convertible" in q:
        filters["convertible"] = True
    if "perpetual" in q:
        filters["perpetual"] = True
    if "sinking fund" in q:
        filters["sinking_fund"] = True

    # Market
    if "primary" in q:
        filters["market"] = "Primary"
    if "secondary" in q:
        filters["market"] = "Secondary"

    # Credit rating (support A++, A+, A, A-, A-- and phrases like "high rating", "low rating")
    rating_levels = ["A++", "A+", "A", "A-", "A--"]
    q = query.lower()

    # Map "high rating" and "low rating" to credit ratings
    if "high rating" in q or "highest rating" in q or "top rating" in q:
        filters["credit_rating"] = ["A++"]
    elif "low rating" in q or "lowest rating" in q or "bottom rating" in q:
        filters["credit_rating"] = ["A--"]
    elif "medium rating" in q or "average rating" in q:
        filters["credit_rating"] = ["A"]
    # Map "high risk" to lowest rating, "low risk" to highest rating
    elif "high risk" in q:
        filters["credit_rating"] = ["A--"]
    elif "low risk" in q:
        filters["credit_rating"] = ["A++"]
    else:
        # Match explicit ratings (A++, A+, etc.)
        rating_match = re.search(r"\b(a\+\+|a\+|a-|a--|a)\b", q)
        if rating_match:
            filters["credit_rating"] = [rating_match.group(1).upper()]
        else:
            pass
    # Face value above
    match = re.search(r"face value (above|greater than|over) (\d+)", q)
    if match:
        filters["face_value"] = int(match.group(2)) + 1

    # Coupon rate above
    match = re.search(r"coupon rate (above|greater than|over) (\d+(\.\d+)?)", q)
    if match:
        filters["coupon_rate"] = float(match.group(2)) + 0.01

    # Apply frontier-specific customizations
    if user_id:
        profile = get_frontier_profile(user_id)
        if profile and "custom_filters" in profile:
            for k, v in profile["custom_filters"].items():
                if not filters.get(k):
                    filters[k] = v

    return filters
