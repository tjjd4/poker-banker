import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BuyInRequest(BaseModel):
    player_id: uuid.UUID
    amount: int = Field(gt=0)


class CashOutRequest(BaseModel):
    player_id: uuid.UUID
    chip_count: int = Field(ge=0)


class TransactionResponse(BaseModel):
    id: uuid.UUID
    table_id: uuid.UUID
    player_id: uuid.UUID
    type: str
    amount: int
    balance_after: int
    note: Optional[str] = None
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class BuyInResponse(BaseModel):
    transaction: TransactionResponse
    total_buy_in: int
    current_balance: int


class CashOutResponse(BaseModel):
    transactions: list[TransactionResponse]
    chip_count: int
    total_buy_in: int
    rake_amount: int
    net_result: int
    seated_minutes: float


class PlayerStatusResponse(BaseModel):
    player_id: uuid.UUID
    display_name: str
    total_buy_in: int
    current_balance: int
    is_seated: bool
    seated_at: Optional[datetime] = None
    left_at: Optional[datetime] = None


class TablePlayersResponse(BaseModel):
    table_id: uuid.UUID
    players: list[PlayerStatusResponse]


class TransactionListResponse(BaseModel):
    transactions: list[TransactionResponse]
    total: int
