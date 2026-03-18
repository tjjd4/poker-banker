import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_session
from app.exceptions import NotFoundError
from app.schemas import PaginationParams
from app.users import service
from app.users.models import User
from app.users.schemas import ResetPasswordRequest, UserCreate, UserListResponse, UserResponse, UserUpdate

router = APIRouter()


@router.get("", response_model=UserListResponse)
async def list_users(
    _current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_session)],
    pagination: Annotated[PaginationParams, Depends()],
):
    result = await service.list_users(db, pagination.offset, pagination.limit)
    return UserListResponse(
        users=result["items"],
        total=result["total"],
        offset=result["offset"],
        limit=result["limit"],
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    _current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.create_user(db, body)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    _current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    user = await service.get_user_by_id(db, user_id)
    if user is None:
        raise NotFoundError("User not found")
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    _current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.update_user(db, user_id, body)


@router.post("/{user_id}/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    user_id: uuid.UUID,
    body: ResetPasswordRequest,
    _current_user: Annotated[User, Depends(require_role("admin"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    await service.reset_user_password(db, user_id, body.new_password)
    return {"message": "Password reset successfully"}
