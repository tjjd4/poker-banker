"""
Shared table ownership dependency (Task 2.2).

Eliminates the repeated ownership-check pattern across routers:
- tables/router.py
- insurance/router.py
- jackpot/router.py
"""
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_session
from app.tables import service as table_service
from app.users.models import User


async def get_owned_table(
    table_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Load table and verify caller is admin or the table's banker.

    Raises:
        HTTPException 404 if the table does not exist.
        HTTPException 403 if the caller is not the table's banker (and not admin).
    """
    table = await table_service.get_table(db, table_id)
    if table is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found",
        )
    if current_user.role != "admin" and table.banker_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this table",
        )
    return table
