import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_session
from app.main import app

# Use SQLite async for tests (no PostgreSQL dependency)
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine_test = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_test = async_sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_test() as s:
        yield s


async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_test() as s:
        yield s


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()

# ---------------------------------------------------------------------------
# Auth / User helper fixtures
# ---------------------------------------------------------------------------
import uuid as _uuid

from app.auth.service import hash_password
from app.users.models import User


@pytest_asyncio.fixture
async def admin_user(session: AsyncSession) -> User:
    """直接在測試 DB 建立 admin（不靠 lifespan seed，因測試用 SQLite）。"""
    user = User(
        id=_uuid.uuid4(),
        username="admin",
        password_hash=hash_password("admin123"),
        display_name="Admin User",
        role="admin",
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def inactive_user(session: AsyncSession) -> User:
    """在測試 DB 建立一個停用帳號。"""
    user = User(
        id=_uuid.uuid4(),
        username="inactive",
        password_hash=hash_password("password123"),
        display_name="Inactive User",
        role="banker",
        is_active=False,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_token(async_client: AsyncClient, admin_user: User) -> str:
    """建立 admin user 並登入，回傳 access_token。"""
    resp = await async_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def banker_token(async_client: AsyncClient, admin_token: str) -> str:
    """用 admin 建立 banker user 並登入，回傳 access_token。"""
    await async_client.post(
        "/api/users",
        json={
            "username": "banker1",
            "password": "banker123",
            "display_name": "Banker One",
            "role": "banker",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await async_client.post(
        "/api/auth/login",
        json={"username": "banker1", "password": "banker123"},
    )
    return resp.json()["access_token"]


@pytest.fixture
def admin_headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def banker_headers(banker_token: str) -> dict:
    return {"Authorization": f"Bearer {banker_token}"}
