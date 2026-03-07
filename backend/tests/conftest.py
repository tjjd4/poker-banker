import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_session
from app.main import app

# Import all models so Base.metadata.create_all can resolve FK references
from app.tables.models import Table, PlayerSeat  # noqa: F401
from app.transactions.models import Transaction  # noqa: F401
from app.insurance.models import InsuranceEvent  # noqa: F401
from app.jackpot.models import JackpotPool, JackpotTrigger  # noqa: F401

# Use SQLite async for tests (no PostgreSQL dependency)
# Use /tmp on Linux native fs to avoid WSL NTFS disk I/O errors
TEST_DATABASE_URL = "sqlite+aiosqlite:////tmp/poker_banker_test.db"

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


# ---------------------------------------------------------------------------
# Player fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def player_token(async_client: AsyncClient, admin_token: str) -> str:
    """用 admin 建立 player user 並登入，回傳 access_token。"""
    await async_client.post(
        "/api/users",
        json={
            "username": "player1",
            "password": "player123",
            "display_name": "Player One",
            "role": "player",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await async_client.post(
        "/api/auth/login",
        json={"username": "player1", "password": "player123"},
    )
    return resp.json()["access_token"]


@pytest.fixture
def player_headers(player_token: str) -> dict:
    return {"Authorization": f"Bearer {player_token}"}


# ---------------------------------------------------------------------------
# Second banker fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def banker_b_token(async_client: AsyncClient, admin_token: str) -> str:
    """用 admin 建立第二個 banker 並登入，回傳 access_token。"""
    await async_client.post(
        "/api/users",
        json={
            "username": "banker2",
            "password": "banker456",
            "display_name": "Banker Two",
            "role": "banker",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await async_client.post(
        "/api/auth/login",
        json={"username": "banker2", "password": "banker456"},
    )
    return resp.json()["access_token"]


@pytest.fixture
def banker_b_headers(banker_b_token: str) -> dict:
    return {"Authorization": f"Bearer {banker_b_token}"}


# ---------------------------------------------------------------------------
# Player user fixture (direct DB creation, no API)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def player_user(session: AsyncSession) -> User:
    """直接在 DB 建立 player user，供 buy-in/cash-out 測試使用。"""
    user = User(
        id=_uuid.uuid4(),
        username="testplayer",
        password_hash=hash_password("testplayer123"),
        display_name="Test Player",
        role="player",
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Table fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def created_table(async_client: AsyncClient, banker_headers: dict) -> dict:
    """建立一個 CREATED 狀態的桌檯，回傳 response dict。"""
    resp = await async_client.post(
        "/api/tables",
        json={
            "name": "Test Table",
            "blind_level": "1/2",
            "rake_interval_minutes": 30,
            "rake_amount": 500,
            "jackpot_per_hand": 0,
        },
        headers=banker_headers,
    )
    assert resp.status_code == 201
    return resp.json()


@pytest_asyncio.fixture
async def open_table(
    async_client: AsyncClient, banker_headers: dict, created_table: dict
) -> dict:
    """建立一個 OPEN 狀態的桌檯。"""
    resp = await async_client.patch(
        f"/api/tables/{created_table['id']}/status",
        json={"status": "OPEN"},
        headers=banker_headers,
    )
    assert resp.status_code == 200
    return resp.json()


# ---------------------------------------------------------------------------
# Insurance fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def player_user_b(session: AsyncSession) -> User:
    """直接在 DB 建立第二個 player user，供保險測試使用。"""
    user = User(
        id=_uuid.uuid4(),
        username="testplayer_b",
        password_hash=hash_password("testplayerb123"),
        display_name="Test Player B",
        role="player",
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def two_seated_players(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,
    player_user: User,
    player_user_b: User,
) -> dict:
    """在 open_table 中建立兩個在座玩家（各 Buy-in 5000）。"""
    await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 5000},
        headers=banker_headers,
    )
    await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user_b.id), "amount": 5000},
        headers=banker_headers,
    )
    return {
        "table": open_table,
        "buyer": player_user,
        "opponent": player_user_b,
    }


@pytest.fixture
def sample_flop_cards() -> dict:
    """一組合法的 Flop 階段牌面。"""
    return {
        "buyer_hand": ["As", "Ks"],
        "opponent_hand": ["7h", "6h"],
        "community_cards": ["8h", "5h", "2d"],
    }


@pytest.fixture
def sample_turn_cards() -> dict:
    """一組合法的 Turn 階段牌面。"""
    return {
        "buyer_hand": ["As", "Ks"],
        "opponent_hand": ["7h", "6h"],
        "community_cards": ["8h", "5h", "2d", "Jc"],
    }


# ---------------------------------------------------------------------------
# Jackpot fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def player_user_c(session: AsyncSession) -> User:
    """直接在 DB 建立第三個 player user，供 Jackpot 測試使用。"""
    user = User(
        id=_uuid.uuid4(),
        username="testplayer_c",
        password_hash=hash_password("testplayerc123"),
        display_name="Test Player C",
        role="player",
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def jackpot_pool(async_client: AsyncClient, banker_headers: dict) -> dict:
    """建立一個 Jackpot 池，回傳 response dict。"""
    resp = await async_client.post(
        "/api/jackpot-pools",
        json={"name": "Test Pool"},
        headers=banker_headers,
    )
    assert resp.status_code == 201
    return resp.json()


@pytest_asyncio.fixture
async def open_table_with_jackpot(
    async_client: AsyncClient,
    banker_headers: dict,
    jackpot_pool: dict,
) -> dict:
    """建立一個啟用 Jackpot 的 OPEN 桌檯。"""
    resp = await async_client.post(
        "/api/tables",
        json={
            "name": "Jackpot Table",
            "blind_level": "1/2",
            "rake_interval_minutes": 30,
            "rake_amount": 500,
            "jackpot_per_hand": 60,
            "jackpot_pool_id": jackpot_pool["id"],
        },
        headers=banker_headers,
    )
    assert resp.status_code == 201
    table = resp.json()
    resp2 = await async_client.patch(
        f"/api/tables/{table['id']}/status",
        json={"status": "OPEN"},
        headers=banker_headers,
    )
    assert resp2.status_code == 200
    return {**resp2.json(), "pool_id": jackpot_pool["id"]}
