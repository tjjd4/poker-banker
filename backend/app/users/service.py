import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import hash_password
from app.exceptions import ConflictError, NotFoundError
from app.users.models import User
from app.users.schemas import UserCreate, UserUpdate


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    user = User(
        id=uuid.uuid4(),
        username=data.username,
        password_hash=hash_password(data.password),
        display_name=data.display_name,
        role=data.role,
        is_active=True,
    )
    db.add(user)
    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError:
        await db.rollback()
        raise ConflictError(f"Username '{data.username}' already exists")
    return user


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def list_users(
    db: AsyncSession, offset: int = 0, limit: int = 50
) -> dict:
    count_stmt = select(func.count()).select_from(User)
    total = (await db.execute(count_stmt)).scalar()

    data_stmt = select(User).order_by(User.created_at).offset(offset).limit(limit)
    items = list((await db.execute(data_stmt)).scalars().all())

    return {"items": items, "total": total, "offset": offset, "limit": limit}


async def reset_user_password(
    db: AsyncSession, user_id: uuid.UUID, new_password: str
) -> None:
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise NotFoundError("User not found")
    user.password_hash = hash_password(new_password)
    await db.commit()


async def update_user(db: AsyncSession, user_id: uuid.UUID, data: UserUpdate) -> User:
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise NotFoundError("User not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user
