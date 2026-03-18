import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_session
from app.reports import service
from app.reports.schemas import DailyReportResponse, TableReportResponse
from app.users.models import User

router = APIRouter()


@router.get("/daily", response_model=DailyReportResponse)
async def daily_report(
    current_user: Annotated[User, Depends(require_role("admin", "banker"))],
    db: Annotated[AsyncSession, Depends(get_session)],
    date: datetime.date = Query(default=None),
) -> DailyReportResponse:
    target_date = date or datetime.date.today()
    banker_id = current_user.id if current_user.role == "banker" else None
    return await service.get_daily_report(db, target_date, banker_id)


@router.get("/table/{table_id}", response_model=TableReportResponse)
async def table_report(
    table_id: UUID,
    current_user: Annotated[User, Depends(require_role("admin", "banker"))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> TableReportResponse:
    return await service.get_table_report(db, table_id, current_user)
