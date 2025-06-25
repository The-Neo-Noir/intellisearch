from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
from llm_utils import parse_query_with_llm
import uuid
import os

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
BONDS_FILE = os.path.join(DATA_DIR, "synthetic_bonds.json")
USERS_FILE = os.path.join(DATA_DIR, "synthetic_users.json")
LOGS_FILE = os.path.join(DATA_DIR, "search_logs.json")

class SearchRequest(BaseModel):
    query: str
    user_id: str

class FeedbackRequest(BaseModel):
    search_id: str
    feedback: str

def bond_matches_filters(bond, filters):
    for k, v in filters.items():
        if v is None:
            continue
        # Special handling for face_value "above"
        if k == "face_value" and isinstance(v, int):
            if bond.get("face_value", 0) < v:
                return False
            continue
        # Special handling for coupon_rate "above"
        if k == "coupon_rate" and isinstance(v, float):
            if bond.get("coupon_rate", 0) < v:
                return False
            continue
        # For boolean fields
        if isinstance(v, bool):
            if bond.get(k) != v:
                return False
            continue
        # For credit_rating, allow list of acceptable ratings
        if k == "credit_rating":
            bond_rating = str(bond.get(k, "")).upper().replace(" ", "")
            if isinstance(v, list):
                if bond_rating not in [r.upper().replace(" ", "") for r in v]:
                    return False
            else:
                filter_rating = str(v).upper().replace(" ", "")
                if bond_rating != filter_rating:
                    return False
            continue
        # For string fields
        if isinstance(v, str):
            if str(bond.get(k, "")).lower() != v.lower():
                return False
            continue
        # For numeric fields
        if isinstance(v, (int, float)):
            if bond.get(k) != v:
                return False
            continue
    return True

@app.post("/search")
async def search_bonds(req: SearchRequest):
    filters = parse_query_with_llm(req.query, req.user_id)
    print("DEBUG FILTERS:", filters)  # Print filters for debugging
    with open(BONDS_FILE) as f:
        bonds = json.load(f)
    results = []
    for bond in bonds:
        if bond_matches_filters(bond, filters):
            results.append(bond)
    search_id = str(uuid.uuid4())
    log_entry = {
        "search_id": search_id,
        "user_id": req.user_id,
        "query": req.query,
        "filters": filters,
        "results": results,
    }
    with open(LOGS_FILE, "a") as f:
        f.write(json.dumps(log_entry) + "\n")
    return {"search_id": search_id, "results": results, "filters": filters}

@app.post("/feedback")
async def feedback(req: FeedbackRequest):
    with open(LOGS_FILE, "a") as f:
        f.write(json.dumps({"search_id": req.search_id, "feedback": req.feedback}) + "\n")
    return {"status": "ok"}

@app.get("/synthetic-bonds")
async def get_synthetic_bonds():
    with open(BONDS_FILE) as f:
        return json.load(f)

@app.get("/frontier-profile/{user_id}")
async def get_frontier_profile(user_id: str):
    with open(USERS_FILE) as f:
        users = json.load(f)
    for user in users:
        if user["user_id"] == user_id:
            return user
    return {}
