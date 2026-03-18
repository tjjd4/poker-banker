import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_session
from app.jackpot import service
from app.schemas import PaginationParams
from app.jackpot.schemas import (
    JackpotPoolCreate,
    JackpotPoolListResponse,
    JackpotPoolResponse,
    JackpotTriggerRequest,
    JackpotTriggerResponse,
    RecordHandResponse,
)
from app.tables.dependencies import get_owned_table
from app.tables.models import Table
from app.users.models import User

# Pool CRUD — mounted at /api/jackpot-pools in main.py
router = APIRouter()

# Table-scoped operations — mounted at /api/tables/{table_id}/jackpot in tables/router.py
table_jackpot_router = APIRouter()


# ---------------------------------------------------------------------------
# Pool CRUD
# ---------------------------------------------------------------------------


@router.post("", response_model=JackpotPoolResponse, status_code=status.HTTP_201_CREATED)
async def create_pool(
    body: JackpotPoolCreate,
    current_user: Annotated[User, Depends(require_role("admin", "banker"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.create_pool(db, current_user.id, body)


@router.get("", response_model=JackpotPoolListResponse)
async def list_pools(
    current_user: Annotated[User, Depends(require_role("admin", "banker"))],
    db: Annotated[AsyncSession, Depends(get_session)],
    pagination: Annotated[PaginationParams, Depends()],
):
    result = await service.list_pools(db, current_user, pagination.offset, pagination.limit)
    return JackpotPoolListResponse(
        pools=result["items"],
        total=result["total"],
        offset=result["offset"],
        limit=result["limit"],
    )


@router.get("/{pool_id}", response_model=JackpotPoolResponse)
async def get_pool(
    pool_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_role("admin", "banker"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    pool = await service.get_pool(db, pool_id)
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jackpot pool not found",
        )
    if current_user.role != "admin" and pool.banker_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't own this pool",
        )
    return pool


@router.get("/{pool_id}/triggers", response_model=list[JackpotTriggerResponse])
async def get_pool_triggers(
    pool_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_role("admin", "banker"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    pool = await service.get_pool(db, pool_id)
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jackpot pool not found",
        )
    if current_user.role != "admin" and pool.banker_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't own this pool",
        )
    return await service.get_pool_triggers(db, pool_id)


# ---------------------------------------------------------------------------
# Table-scoped operations (sub-router)
# ---------------------------------------------------------------------------


@table_jackpot_router.post("/hand", response_model=RecordHandResponse)
async def record_hand(
    current_user: Annotated[User, Depends(require_role("admin", "banker"))],
    db: Annotated[AsyncSession, Depends(get_session)],
    table: Annotated[Table, Depends(get_owned_table)],
):
    return await service.record_hand(db, table.id, current_user.id)


@table_jackpot_router.post("/trigger", response_model=JackpotTriggerResponse)
async def trigger_payout(
    body: JackpotTriggerRequest,
    current_user: Annotated[User, Depends(require_role("admin", "banker"))],
    db: Annotated[AsyncSession, Depends(get_session)],
    table: Annotated[Table, Depends(get_owned_table)],
):
    return await service.trigger_payout(db, table.id, body, current_user.id)
