from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---- Request ----


class TableCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    blind_level: str = Field(..., min_length=1, max_length=20)
    rake_interval_minutes: int = Field(..., gt=0)
    rake_amount: int = Field(..., gt=0)
    jackpot_per_hand: int = Field(default=0, ge=0)
    jackpot_pool_id: UUID | None = None


class TableStatusUpdate(BaseModel):
    status: Literal["OPEN", "SETTLING", "CLOSED"]


class TableUnlock(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


# ---- Response ----


class TableResponse(BaseModel):
    id: UUID
    name: str
    blind_level: str
    rake_interval_minutes: int
    rake_amount: int
    jackpot_per_hand: int
    jackpot_pool_id: UUID | None
    status: str
    banker_id: UUID
    opened_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlayerSeatResponse(BaseModel):
    id: UUID
    player_id: UUID
    player_display_name: str
    seated_at: datetime
    left_at: datetime | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class TableDetailResponse(TableResponse):
    """桌檯詳情，含在座玩家列表"""

    players: list[PlayerSeatResponse] = []


class TableListResponse(BaseModel):
    tables: list[TableResponse]
    total: int
