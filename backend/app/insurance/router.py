import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
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
from app.tables.dependencies import get_owned_table
from app.tables.models import Table
from app.users.models import User

router = APIRouter()


@router.post("", response_model=InsuranceCalcResponse, status_code=status.HTTP_201_CREATED)
async def create_insurance_event(
    body: InsuranceCreateRequest,
    current_user: Annotated[User, Depends(require_role("admin", "banker"))],
    db: Annotated[AsyncSession, Depends(get_session)],
    table: Annotated[Table, Depends(get_owned_table)],
):
    return await service.create_insurance_event(db, table.id, body, current_user.id)


@router.patch(
    "/{insurance_id}/confirm", response_model=InsuranceDetailResponse
)
async def confirm_insurance(
    insurance_id: uuid.UUID,
    body: InsuranceConfirmRequest,
    current_user: Annotated[User, Depends(require_role("admin", "banker"))],
    db: Annotated[AsyncSession, Depends(get_session)],
    table: Annotated[Table, Depends(get_owned_table)],
):
    return await service.confirm_insurance(
        db, table.id, insurance_id, body, current_user.id
    )


@router.patch(
    "/{insurance_id}/resolve", response_model=InsuranceDetailResponse
)
async def resolve_insurance(
    insurance_id: uuid.UUID,
    body: InsuranceResolveRequest,
    current_user: Annotated[User, Depends(require_role("admin", "banker"))],
    db: Annotated[AsyncSession, Depends(get_session)],
    table: Annotated[Table, Depends(get_owned_table)],
):
    return await service.resolve_insurance(
        db, table.id, insurance_id, body, current_user.id
    )


@router.get("", response_model=InsuranceListResponse)
async def list_insurance_events(
    current_user: Annotated[User, Depends(require_role("admin", "banker"))],
    db: Annotated[AsyncSession, Depends(get_session)],
    table: Annotated[Table, Depends(get_owned_table)],
):
    events = await service.get_table_insurance_events(db, table.id)
    return InsuranceListResponse(events=events, total=len(events))
