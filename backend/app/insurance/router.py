import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_session
from app.insurance import service
from app.insurance.schemas import (
    InsuranceCalcResponse,
    InsuranceConfirmRequest,
    InsuranceCreateRequest,
    InsuranceDetailResponse,
    InsuranceListResponse,
    InsuranceResolveRequest,
)
from app.tables import service as table_service
from app.users.models import User

router = APIRouter()


async def _check_table_ownership(
    db: AsyncSession, table_id: uuid.UUID, current_user: User
) -> None:
    """Shared ownership check for all insurance endpoints."""
    table = await table_service.get_table(db, table_id)
    if table is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Table not found"
        )
    if current_user.role != "admin" and table.banker_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't own this table",
        )


@router.post("", response_model=InsuranceCalcResponse, status_code=status.HTTP_201_CREATED)
async def create_insurance_event(
    table_id: uuid.UUID,
    body: InsuranceCreateRequest,
    current_user: Annotated[User, Depends(require_role("admin", "banker"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    await _check_table_ownership(db, table_id, current_user)
    return await service.create_insurance_event(db, table_id, body, current_user.id)


@router.patch(
    "/{insurance_id}/confirm", response_model=InsuranceDetailResponse
)
async def confirm_insurance(
    table_id: uuid.UUID,
    insurance_id: uuid.UUID,
    body: InsuranceConfirmRequest,
    current_user: Annotated[User, Depends(require_role("admin", "banker"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    await _check_table_ownership(db, table_id, current_user)
    return await service.confirm_insurance(
        db, table_id, insurance_id, body, current_user.id
    )


@router.patch(
    "/{insurance_id}/resolve", response_model=InsuranceDetailResponse
)
async def resolve_insurance(
    table_id: uuid.UUID,
    insurance_id: uuid.UUID,
    body: InsuranceResolveRequest,
    current_user: Annotated[User, Depends(require_role("admin", "banker"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    await _check_table_ownership(db, table_id, current_user)
    return await service.resolve_insurance(
        db, table_id, insurance_id, body, current_user.id
    )


@router.get("", response_model=InsuranceListResponse)
async def list_insurance_events(
    table_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_role("admin", "banker"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    await _check_table_ownership(db, table_id, current_user)
    events = await service.get_table_insurance_events(db, table_id)
    return InsuranceListResponse(events=events, total=len(events))
