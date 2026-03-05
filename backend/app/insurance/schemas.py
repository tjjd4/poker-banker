import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---- Requests ----


class InsuranceCreateRequest(BaseModel):
    """Banker creates an insurance event (input card data)."""
    buyer_id: uuid.UUID
    opponent_id: uuid.UUID
    buyer_hand: list[str] = Field(min_length=2, max_length=2)
    opponent_hand: list[str] = Field(min_length=2, max_length=2)
    community_cards: list[str] = Field(min_length=3, max_length=4)


class InsuranceConfirmRequest(BaseModel):
    """Buyer confirms purchasing insurance."""
    insured_amount: int = Field(gt=0)
    seller_id: uuid.UUID | None = None


class InsuranceResolveRequest(BaseModel):
    """Resolve insurance after showdown."""
    is_hit: bool
    final_community_cards: list[str] = Field(min_length=5, max_length=5)


# ---- Responses ----


class InsuranceCalcResponse(BaseModel):
    """Returned after creating an insurance event with calculation results."""
    id: uuid.UUID
    table_id: uuid.UUID
    buyer_id: uuid.UUID
    buyer_hand: list[str]
    opponent_hand: list[str]
    community_cards: list[str]
    outs: int
    total_combinations: int
    win_probability: float
    odds: float
    created_at: datetime


class InsuranceDetailResponse(BaseModel):
    """Full detail of an insurance event."""
    id: uuid.UUID
    table_id: uuid.UUID
    buyer_id: uuid.UUID
    seller_id: Optional[uuid.UUID] = None
    buyer_hand: list[str]
    opponent_hand: list[str]
    community_cards: list[str]
    outs: int
    win_probability: float
    odds: float
    insured_amount: int
    payout_amount: int
    is_hit: Optional[bool] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InsuranceListResponse(BaseModel):
    """List of insurance events."""
    events: list[InsuranceDetailResponse]
    total: int
