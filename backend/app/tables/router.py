import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_session
from app.tables import service
from app.tables.schemas import (
    TableCreate,
    TableDetailResponse,
    TableListResponse,
    TableResponse,
    TableStatusUpdate,
    TableUnlock,
)
from app.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=TableResponse, status_code=status.HTTP_201_CREATED)
async def create_table(
    body: TableCreate,
    current_user: Annotated[User, Depends(require_role("admin", "banker"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.create_table(db, current_user.id, body)


@router.get("", response_model=TableListResponse)
async def list_tables(
    current_user: Annotated[User, Depends(require_role("admin", "banker"))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status_filter: str | None = Query(None, alias="status"),
):
    banker_id = None if current_user.role == "admin" else current_user.id
    tables = await service.list_tables(db, banker_id, status_filter)
    return TableListResponse(tables=tables, total=len(tables))


@router.get("/{table_id}", response_model=TableDetailResponse)
async def get_table(
    table_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_role("admin", "banker"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    detail = await service.get_table_detail(db, table_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Table not found"
        )
    if current_user.role != "admin" and detail["banker_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't own this table",
        )
    return detail


@router.patch("/{table_id}/status", response_model=TableResponse)
async def update_table_status(
    table_id: uuid.UUID,
    body: TableStatusUpdate,
    current_user: Annotated[User, Depends(require_role("admin", "banker"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    banker_id = None if current_user.role == "admin" else current_user.id
    return await service.update_table_status(db, table_id, body.status, banker_id)


@router.patch("/{table_id}/unlock", response_model=TableResponse)
async def unlock_table(
    table_id: uuid.UUID,
    body: TableUnlock,
    current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    logger.info(
        "Table %s unlocked by admin %s (%s): %s",
        table_id,
        current_user.id,
        current_user.username,
        body.reason,
    )
    return await service.unlock_table(db, table_id, body.reason, current_user.id)


# ---------------------------------------------------------------------------
# Buy-in / Cash-out / Players / Transactions
# ---------------------------------------------------------------------------

from app.transactions import service as txn_service
from app.transactions.schemas import (
    BuyInRequest,
    BuyInResponse,
    CashOutRequest,
    CashOutResponse,
    TablePlayersResponse,
    TransactionListResponse,
)


@router.post("/{table_id}/buy-in", response_model=BuyInResponse, status_code=status.HTTP_201_CREATED)
async def buy_in(
    table_id: uuid.UUID,
    body: BuyInRequest,
    current_user: Annotated[User, Depends(require_role("admin", "banker"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    table = await service.get_table(db, table_id)
    if table is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Table not found"
        )
    if current_user.role != "admin" and table.banker_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't own this table",
        )
    return await txn_service.buy_in(db, table_id, body.player_id, body.amount, current_user.id)


@router.post("/{table_id}/cash-out", response_model=CashOutResponse)
async def cash_out(
    table_id: uuid.UUID,
    body: CashOutRequest,
    current_user: Annotated[User, Depends(require_role("admin", "banker"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    table = await service.get_table(db, table_id)
    if table is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Table not found"
        )
    if current_user.role != "admin" and table.banker_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't own this table",
        )
    return await txn_service.cash_out(db, table_id, body.player_id, body.chip_count, current_user.id)


@router.get("/{table_id}/players", response_model=TablePlayersResponse)
async def get_table_players(
    table_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_role("admin", "banker"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    table = await service.get_table(db, table_id)
    if table is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Table not found"
        )
    if current_user.role != "admin" and table.banker_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't own this table",
        )
    players = await txn_service.get_table_players(db, table_id)
    return TablePlayersResponse(table_id=table_id, players=players)


@router.get("/{table_id}/transactions", response_model=TransactionListResponse)
async def get_table_transactions(
    table_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_role("admin", "banker"))],
    db: Annotated[AsyncSession, Depends(get_session)],
    player_id: uuid.UUID | None = Query(None),
):
    table = await service.get_table(db, table_id)
    if table is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Table not found"
        )
    if current_user.role != "admin" and table.banker_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't own this table",
        )
    txns = await txn_service.get_table_transactions(db, table_id, player_id)
    return TransactionListResponse(transactions=txns, total=len(txns))


# ---------------------------------------------------------------------------
# Insurance sub-router
# ---------------------------------------------------------------------------

from app.insurance.router import router as insurance_router

router.include_router(insurance_router, prefix="/{table_id}/insurance", tags=["insurance"])

# ---------------------------------------------------------------------------
# Jackpot sub-router
# ---------------------------------------------------------------------------

from app.jackpot.router import table_jackpot_router

router.include_router(table_jackpot_router, prefix="/{table_id}/jackpot", tags=["jackpot"])
