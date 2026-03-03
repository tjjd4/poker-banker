from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    display_name: str = Field(..., min_length=1, max_length=100)
    role: Literal["admin", "banker", "player"]


class UserUpdate(BaseModel):
    display_name: str | None = None
    role: Literal["admin", "banker", "player"] | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: UUID
    username: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int
