from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---- Request ----


class JackpotPoolCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class JackpotTriggerRequest(BaseModel):
    pool_id: UUID
    winner_id: UUID
    hand_description: str = Field(min_length=1, max_length=200)
    payout_amount: int = Field(gt=0)


# ---- Response ----


class JackpotPoolResponse(BaseModel):
    id: UUID
    name: str
    balance: int
    banker_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JackpotPoolListResponse(BaseModel):
    pools: list[JackpotPoolResponse]
    total: int


class HandContribution(BaseModel):
    player_id: UUID
    display_name: str
    amount: int


class RecordHandResponse(BaseModel):
    pool_id: UUID
    pool_balance: int
    jackpot_per_hand: int
    contributions: list[HandContribution]
    remainder: int


class JackpotTriggerResponse(BaseModel):
    id: UUID
    pool_id: UUID
    table_id: UUID
    winner_id: UUID
    hand_description: str
    payout_amount: int
    pool_balance_after: int
    triggered_by: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
