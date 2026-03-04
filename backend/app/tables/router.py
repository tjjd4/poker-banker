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
# Stubs — preserved for future implementation
# ---------------------------------------------------------------------------


@router.post("/{table_id}/seats")
async def seat_player(table_id: str):
    pass


@router.post("/{table_id}/transactions")
async def create_transaction(table_id: str):
    pass


@router.post("/{table_id}/insurance")
async def create_insurance_event(table_id: str):
    pass
