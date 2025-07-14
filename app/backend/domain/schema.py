from typing import Optional

from pydantic import BaseModel


class BondQueryRequest(BaseModel):
    query: str


class BondQueryResponse(BaseModel):
    issuer: str | None = None
    coupon: str | None = None
    maturityYear: int | None = None
    rating: Optional[str] = None
    segment: str | None = None
    location: str | None = None


# DTO for results shown to the frontend after fetching from DB

class BondOut(BaseModel):
    issuer: str
    coupon: float
    maturityYear: int
    rating: str
    segment: str
    location: str


class QueryRequest(BaseModel):
    query: str
