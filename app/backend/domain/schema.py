from typing import Optional

from pydantic import BaseModel


class BondQueryRequest(BaseModel):
    query: str


class BondQueryResponse(BaseModel):
    isin: str | None = None
    currency: str | None = None
    issuer: str | None = None
    segment: str | None = None
    coupon: str | None = None
    maturityYear: int | None = None
    rating: Optional[str] = None
    yieldType: str | None = None
    issuer_location: str | None = None


# DTO for results shown to the frontend after fetching from DB


class BondOut(BaseModel):
    isin: str | None = None
    currency: str | None = None
    issuer: str
    segment: str
    coupon: float
    maturityYear: int
    yieldType: str | None = None
    rating: str
    issuer_location: str | None = None


class Response:
    result: BondOut
    dsl: BondQueryResponse


class QueryRequest(BaseModel):
    query: str
