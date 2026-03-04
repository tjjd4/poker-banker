import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.tables.models import PlayerSeat


# ===== 建立桌檯 =====


@pytest.mark.asyncio
async def test_create_table_as_banker(async_client: AsyncClient, banker_headers: dict):
    """Banker 建立桌檯 → 201，status 為 CREATED"""
    resp = await async_client.post(
        "/api/tables",
        json={
            "name": "週五局",
            "blind_level": "1/2",
            "rake_interval_minutes": 30,
            "rake_amount": 500,
            "jackpot_per_hand": 0,
        },
        headers=banker_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "CREATED"
    assert data["name"] == "週五局"
    assert data["blind_level"] == "1/2"
    assert data["rake_interval_minutes"] == 30
    assert data["rake_amount"] == 500
    assert data["jackpot_per_hand"] == 0
    assert data["opened_at"] is None
    assert data["closed_at"] is None
    assert "id" in data
    assert "banker_id" in data


@pytest.mark.asyncio
async def test_create_table_as_player(async_client: AsyncClient, player_headers: dict):
    """Player 建立桌檯 → 403"""
    resp = await async_client.post(
        "/api/tables",
        json={
            "name": "Player Table",
            "blind_level": "1/2",
            "rake_interval_minutes": 30,
            "rake_amount": 500,
        },
        headers=player_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_table_invalid_rake(
    async_client: AsyncClient, banker_headers: dict
):
    """rake_interval_minutes=0 或 rake_amount=-1 → 422"""
    resp = await async_client.post(
        "/api/tables",
        json={
            "name": "Bad Table",
            "blind_level": "1/2",
            "rake_interval_minutes": 0,
            "rake_amount": -1,
        },
        headers=banker_headers,
    )
    assert resp.status_code == 422


# ===== 列表與詳情 =====


@pytest.mark.asyncio
async def test_list_tables_as_banker(
    async_client: AsyncClient, banker_headers: dict, created_table: dict
):
    """Banker 列出自己的桌檯"""
    # 再建一張桌
    await async_client.post(
        "/api/tables",
        json={
            "name": "Second Table",
            "blind_level": "5/10",
            "rake_interval_minutes": 20,
            "rake_amount": 1000,
        },
        headers=banker_headers,
    )
    resp = await async_client.get("/api/tables", headers=banker_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    assert isinstance(data["tables"], list)


@pytest.mark.asyncio
async def test_list_tables_filtered_by_status(
    async_client: AsyncClient, banker_headers: dict, open_table: dict
):
    """status=OPEN 只回傳 OPEN 的桌檯"""
    resp = await async_client.get(
        "/api/tables?status=OPEN", headers=banker_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert all(t["status"] == "OPEN" for t in data["tables"])


@pytest.mark.asyncio
async def test_banker_cannot_see_other_bankers_tables(
    async_client: AsyncClient,
    banker_b_headers: dict,
    created_table: dict,
):
    """Banker B 看不到 Banker A 的桌檯"""
    resp = await async_client.get("/api/tables", headers=banker_b_headers)
    assert resp.status_code == 200
    data = resp.json()
    table_ids = [t["id"] for t in data["tables"]]
    assert created_table["id"] not in table_ids


@pytest.mark.asyncio
async def test_admin_can_see_all_tables(
    async_client: AsyncClient, admin_headers: dict, created_table: dict
):
    """Admin 可以看到所有 Banker 建的桌檯"""
    resp = await async_client.get("/api/tables", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    table_ids = [t["id"] for t in data["tables"]]
    assert created_table["id"] in table_ids


@pytest.mark.asyncio
async def test_get_table_detail(
    async_client: AsyncClient, banker_headers: dict, created_table: dict
):
    """GET /api/tables/{id} 回傳含 players 空列表"""
    resp = await async_client.get(
        f"/api/tables/{created_table['id']}", headers=banker_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == created_table["id"]
    assert "players" in data
    assert isinstance(data["players"], list)
    assert len(data["players"]) == 0


@pytest.mark.asyncio
async def test_banker_cannot_see_other_bankers_table_detail(
    async_client: AsyncClient,
    banker_b_headers: dict,
    created_table: dict,
):
    """Banker B 取得 Banker A 的桌檯詳情 → 403"""
    resp = await async_client.get(
        f"/api/tables/{created_table['id']}", headers=banker_b_headers
    )
    assert resp.status_code == 403


# ===== 狀態轉換 Happy Path =====


@pytest.mark.asyncio
async def test_status_created_to_open(
    async_client: AsyncClient, banker_headers: dict, created_table: dict
):
    """CREATED → OPEN → 200，opened_at 不為 null"""
    resp = await async_client.patch(
        f"/api/tables/{created_table['id']}/status",
        json={"status": "OPEN"},
        headers=banker_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "OPEN"
    assert data["opened_at"] is not None


@pytest.mark.asyncio
async def test_status_open_to_settling(
    async_client: AsyncClient, banker_headers: dict, open_table: dict
):
    """OPEN → SETTLING → 200"""
    resp = await async_client.patch(
        f"/api/tables/{open_table['id']}/status",
        json={"status": "SETTLING"},
        headers=banker_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "SETTLING"


@pytest.mark.asyncio
async def test_status_settling_to_closed_no_players(
    async_client: AsyncClient, banker_headers: dict, open_table: dict
):
    """SETTLING → CLOSED（無在座玩家）→ 200，closed_at 不為 null"""
    # OPEN → SETTLING
    await async_client.patch(
        f"/api/tables/{open_table['id']}/status",
        json={"status": "SETTLING"},
        headers=banker_headers,
    )
    # SETTLING → CLOSED
    resp = await async_client.patch(
        f"/api/tables/{open_table['id']}/status",
        json={"status": "CLOSED"},
        headers=banker_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "CLOSED"
    assert data["closed_at"] is not None


# ===== 狀態轉換 Sad Path =====


@pytest.mark.asyncio
async def test_status_created_to_settling_rejected(
    async_client: AsyncClient, banker_headers: dict, created_table: dict
):
    """CREATED → SETTLING → 400"""
    resp = await async_client.patch(
        f"/api/tables/{created_table['id']}/status",
        json={"status": "SETTLING"},
        headers=banker_headers,
    )
    assert resp.status_code == 400
    assert "hasn't been opened" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_status_created_to_closed_rejected(
    async_client: AsyncClient, banker_headers: dict, created_table: dict
):
    """CREATED → CLOSED → 400"""
    resp = await async_client.patch(
        f"/api/tables/{created_table['id']}/status",
        json={"status": "CLOSED"},
        headers=banker_headers,
    )
    assert resp.status_code == 400
    assert "hasn't been opened" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_status_open_to_created_rejected(
    async_client: AsyncClient, banker_headers: dict, open_table: dict
):
    """OPEN → CREATED → 422（CREATED 不在 Literal 中，被 Pydantic 攔截）"""
    resp = await async_client.patch(
        f"/api/tables/{open_table['id']}/status",
        json={"status": "CREATED"},
        headers=banker_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_status_settling_to_open_rejected(
    async_client: AsyncClient, banker_headers: dict, open_table: dict
):
    """SETTLING → OPEN → 400"""
    # OPEN → SETTLING
    await async_client.patch(
        f"/api/tables/{open_table['id']}/status",
        json={"status": "SETTLING"},
        headers=banker_headers,
    )
    # SETTLING → OPEN
    resp = await async_client.patch(
        f"/api/tables/{open_table['id']}/status",
        json={"status": "OPEN"},
        headers=banker_headers,
    )
    assert resp.status_code == 400
    assert "Cannot revert" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_status_closed_to_open_rejected(
    async_client: AsyncClient, banker_headers: dict, open_table: dict
):
    """CLOSED → OPEN → 400"""
    # OPEN → SETTLING → CLOSED
    await async_client.patch(
        f"/api/tables/{open_table['id']}/status",
        json={"status": "SETTLING"},
        headers=banker_headers,
    )
    await async_client.patch(
        f"/api/tables/{open_table['id']}/status",
        json={"status": "CLOSED"},
        headers=banker_headers,
    )
    # CLOSED → OPEN
    resp = await async_client.patch(
        f"/api/tables/{open_table['id']}/status",
        json={"status": "OPEN"},
        headers=banker_headers,
    )
    assert resp.status_code == 400
    assert "admin unlock" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_status_same_status_rejected(
    async_client: AsyncClient, banker_headers: dict, open_table: dict
):
    """OPEN → OPEN → 400 "already in OPEN status" """
    resp = await async_client.patch(
        f"/api/tables/{open_table['id']}/status",
        json={"status": "OPEN"},
        headers=banker_headers,
    )
    assert resp.status_code == 400
    assert "already in OPEN status" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_settling_to_closed_blocked_by_active_player(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,
    session: AsyncSession,
    admin_user,
):
    """SETTLING → CLOSED 被在座玩家阻擋 → 400"""
    # OPEN → SETTLING
    await async_client.patch(
        f"/api/tables/{open_table['id']}/status",
        json={"status": "SETTLING"},
        headers=banker_headers,
    )
    # 直接在 DB 建立一個 is_active=True 的 PlayerSeat
    seat = PlayerSeat(
        id=uuid.uuid4(),
        table_id=uuid.UUID(open_table["id"]),
        player_id=admin_user.id,
        seated_at=datetime.now(timezone.utc),
        is_active=True,
    )
    session.add(seat)
    await session.commit()

    # SETTLING → CLOSED → 400
    resp = await async_client.patch(
        f"/api/tables/{open_table['id']}/status",
        json={"status": "CLOSED"},
        headers=banker_headers,
    )
    assert resp.status_code == 400
    assert "active players" in resp.json()["detail"]


# ===== Admin 解鎖 =====


@pytest.mark.asyncio
async def test_admin_unlock_closed_table(
    async_client: AsyncClient,
    admin_headers: dict,
    banker_headers: dict,
    open_table: dict,
):
    """Admin 解鎖 CLOSED 桌檯 → 200，狀態變 SETTLING，closed_at 清除"""
    # OPEN → SETTLING → CLOSED
    await async_client.patch(
        f"/api/tables/{open_table['id']}/status",
        json={"status": "SETTLING"},
        headers=banker_headers,
    )
    await async_client.patch(
        f"/api/tables/{open_table['id']}/status",
        json={"status": "CLOSED"},
        headers=banker_headers,
    )
    # Admin unlock
    resp = await async_client.patch(
        f"/api/tables/{open_table['id']}/unlock",
        json={"reason": "Need to adjust player balances"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SETTLING"
    assert data["closed_at"] is None


@pytest.mark.asyncio
async def test_admin_unlock_requires_reason(
    async_client: AsyncClient, admin_headers: dict, created_table: dict
):
    """reason 為空字串 → 422"""
    resp = await async_client.patch(
        f"/api/tables/{created_table['id']}/unlock",
        json={"reason": ""},
        headers=admin_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_banker_cannot_unlock(
    async_client: AsyncClient, banker_headers: dict, created_table: dict
):
    """Banker 嘗試 unlock → 403"""
    resp = await async_client.patch(
        f"/api/tables/{created_table['id']}/unlock",
        json={"reason": "Banker trying to unlock"},
        headers=banker_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unlock_non_closed_table(
    async_client: AsyncClient, admin_headers: dict, open_table: dict
):
    """OPEN 狀態的桌檯 → Admin unlock → 400"""
    resp = await async_client.patch(
        f"/api/tables/{open_table['id']}/unlock",
        json={"reason": "Try unlock non-closed"},
        headers=admin_headers,
    )
    assert resp.status_code == 400


# ===== 權限 =====


@pytest.mark.asyncio
async def test_banker_cannot_change_other_bankers_table_status(
    async_client: AsyncClient,
    banker_b_headers: dict,
    created_table: dict,
):
    """Banker B 嘗試改 Banker A 桌檯狀態 → 403"""
    resp = await async_client.patch(
        f"/api/tables/{created_table['id']}/status",
        json={"status": "OPEN"},
        headers=banker_b_headers,
    )
    assert resp.status_code == 403
