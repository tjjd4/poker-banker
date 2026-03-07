"""Jackpot 獎金池管理 + 每手扣款 + 觸發發放 tests."""

import uuid

import pytest
from httpx import AsyncClient

from app.users.models import User


# ===== 池管理 =====


@pytest.mark.asyncio
async def test_create_pool(
    async_client: AsyncClient, banker_headers: dict,
):
    resp = await async_client.post(
        "/api/jackpot-pools",
        json={"name": "Main Pool"},
        headers=banker_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Main Pool"
    assert data["balance"] == 0
    assert "banker_id" in data


@pytest.mark.asyncio
async def test_list_pools_banker_isolation(
    async_client: AsyncClient,
    banker_headers: dict,
    banker_b_headers: dict,
):
    # Banker A creates a pool
    await async_client.post(
        "/api/jackpot-pools",
        json={"name": "Pool A"},
        headers=banker_headers,
    )
    # Banker B creates a pool
    await async_client.post(
        "/api/jackpot-pools",
        json={"name": "Pool B"},
        headers=banker_b_headers,
    )
    # Banker B should only see own pool
    resp = await async_client.get("/api/jackpot-pools", headers=banker_b_headers)
    assert resp.status_code == 200
    pools = resp.json()["pools"]
    assert len(pools) == 1
    assert pools[0]["name"] == "Pool B"


@pytest.mark.asyncio
async def test_admin_sees_all_pools(
    async_client: AsyncClient,
    banker_headers: dict,
    banker_b_headers: dict,
    admin_headers: dict,
):
    await async_client.post(
        "/api/jackpot-pools",
        json={"name": "Pool A"},
        headers=banker_headers,
    )
    await async_client.post(
        "/api/jackpot-pools",
        json={"name": "Pool B"},
        headers=banker_b_headers,
    )
    resp = await async_client.get("/api/jackpot-pools", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 2


# ===== 建桌時的關聯驗證 =====


@pytest.mark.asyncio
async def test_create_table_with_jackpot_pool(
    async_client: AsyncClient, banker_headers: dict, jackpot_pool: dict,
):
    resp = await async_client.post(
        "/api/tables",
        json={
            "name": "JP Table",
            "blind_level": "1/2",
            "rake_interval_minutes": 30,
            "rake_amount": 500,
            "jackpot_per_hand": 60,
            "jackpot_pool_id": jackpot_pool["id"],
        },
        headers=banker_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["jackpot_per_hand"] == 60
    assert resp.json()["jackpot_pool_id"] == jackpot_pool["id"]


@pytest.mark.asyncio
async def test_create_table_jackpot_without_pool_rejected(
    async_client: AsyncClient, banker_headers: dict,
):
    resp = await async_client.post(
        "/api/tables",
        json={
            "name": "JP Table",
            "blind_level": "1/2",
            "rake_interval_minutes": 30,
            "rake_amount": 500,
            "jackpot_per_hand": 60,
        },
        headers=banker_headers,
    )
    assert resp.status_code == 400
    assert "jackpot pool" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_table_jackpot_zero_no_pool_ok(
    async_client: AsyncClient, banker_headers: dict,
):
    resp = await async_client.post(
        "/api/tables",
        json={
            "name": "No JP Table",
            "blind_level": "1/2",
            "rake_interval_minutes": 30,
            "rake_amount": 500,
            "jackpot_per_hand": 0,
        },
        headers=banker_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["jackpot_per_hand"] == 0


@pytest.mark.asyncio
async def test_create_table_with_other_bankers_pool_rejected(
    async_client: AsyncClient,
    banker_b_headers: dict,
    jackpot_pool: dict,  # Owned by banker1
):
    resp = await async_client.post(
        "/api/tables",
        json={
            "name": "JP Table",
            "blind_level": "1/2",
            "rake_interval_minutes": 30,
            "rake_amount": 500,
            "jackpot_per_hand": 60,
            "jackpot_pool_id": jackpot_pool["id"],
        },
        headers=banker_b_headers,
    )
    assert resp.status_code == 400


# ===== 記錄一手 =====


@pytest.mark.asyncio
async def test_record_hand_success(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table_with_jackpot: dict,
    player_user: User,
    player_user_b: User,
    player_user_c: User,
):
    """3 players, jackpot_per_hand=60, per_player=20, remainder=0."""
    table_id = open_table_with_jackpot["id"]

    # Seat 3 players
    for p in [player_user, player_user_b, player_user_c]:
        resp = await async_client.post(
            f"/api/tables/{table_id}/buy-in",
            json={"player_id": str(p.id), "amount": 1000},
            headers=banker_headers,
        )
        assert resp.status_code == 201

    # Record hand
    resp = await async_client.post(
        f"/api/tables/{table_id}/jackpot/hand",
        headers=banker_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["jackpot_per_hand"] == 60
    assert data["remainder"] == 0
    assert data["pool_balance"] == 60
    assert len(data["contributions"]) == 3
    for c in data["contributions"]:
        assert c["amount"] == 20


@pytest.mark.asyncio
async def test_record_hand_with_remainder(
    async_client: AsyncClient,
    banker_headers: dict,
    jackpot_pool: dict,
    player_user: User,
    player_user_b: User,
    player_user_c: User,
):
    """4 players, jackpot_per_hand=50, per_player=12, remainder=2."""
    # Create table with jackpot_per_hand=50
    resp = await async_client.post(
        "/api/tables",
        json={
            "name": "Remainder Table",
            "blind_level": "1/2",
            "rake_interval_minutes": 30,
            "rake_amount": 500,
            "jackpot_per_hand": 50,
            "jackpot_pool_id": jackpot_pool["id"],
        },
        headers=banker_headers,
    )
    assert resp.status_code == 201
    table_id = resp.json()["id"]

    # Open table
    await async_client.patch(
        f"/api/tables/{table_id}/status",
        json={"status": "OPEN"},
        headers=banker_headers,
    )

    # Create a 4th player directly via admin API
    admin_token_resp = await async_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    admin_h = {"Authorization": f"Bearer {admin_token_resp.json()['access_token']}"}
    await async_client.post(
        "/api/users",
        json={
            "username": "testplayer_d",
            "password": "testplayerd123",
            "display_name": "Test Player D",
            "role": "player",
        },
        headers=admin_h,
    )
    login_d = await async_client.post(
        "/api/auth/login",
        json={"username": "testplayer_d", "password": "testplayerd123"},
    )
    # Get player D's id from listing
    users_resp = await async_client.get("/api/users", headers=admin_h)
    player_d_id = None
    for u in users_resp.json()["users"]:
        if u["username"] == "testplayer_d":
            player_d_id = u["id"]
            break

    # Seat 4 players
    for pid in [str(player_user.id), str(player_user_b.id), str(player_user_c.id), player_d_id]:
        await async_client.post(
            f"/api/tables/{table_id}/buy-in",
            json={"player_id": pid, "amount": 1000},
            headers=banker_headers,
        )

    # Record hand
    resp = await async_client.post(
        f"/api/tables/{table_id}/jackpot/hand",
        headers=banker_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["jackpot_per_hand"] == 50
    assert data["remainder"] == 2
    assert data["pool_balance"] == 50
    assert len(data["contributions"]) == 4
    for c in data["contributions"]:
        assert c["amount"] == 12


@pytest.mark.asyncio
async def test_record_hand_single_player(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table_with_jackpot: dict,
    player_user: User,
):
    """1 player, jackpot_per_hand=60, per_player=60."""
    table_id = open_table_with_jackpot["id"]
    await async_client.post(
        f"/api/tables/{table_id}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_headers,
    )
    resp = await async_client.post(
        f"/api/tables/{table_id}/jackpot/hand",
        headers=banker_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["contributions"]) == 1
    assert data["contributions"][0]["amount"] == 60
    assert data["remainder"] == 0


@pytest.mark.asyncio
async def test_record_hand_no_active_players(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table_with_jackpot: dict,
):
    """No players → 400."""
    resp = await async_client.post(
        f"/api/tables/{open_table_with_jackpot['id']}/jackpot/hand",
        headers=banker_headers,
    )
    assert resp.status_code == 400
    assert "no active players" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_record_hand_table_not_open(
    async_client: AsyncClient,
    banker_headers: dict,
    jackpot_pool: dict,
):
    """CREATED table → 400."""
    resp = await async_client.post(
        "/api/tables",
        json={
            "name": "Not Open",
            "blind_level": "1/2",
            "rake_interval_minutes": 30,
            "rake_amount": 500,
            "jackpot_per_hand": 60,
            "jackpot_pool_id": jackpot_pool["id"],
        },
        headers=banker_headers,
    )
    table_id = resp.json()["id"]
    resp = await async_client.post(
        f"/api/tables/{table_id}/jackpot/hand",
        headers=banker_headers,
    )
    assert resp.status_code == 400
    assert "not open" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_record_hand_jackpot_not_enabled(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,  # jackpot_per_hand=0
):
    resp = await async_client.post(
        f"/api/tables/{open_table['id']}/jackpot/hand",
        headers=banker_headers,
    )
    assert resp.status_code == 400
    assert "not enabled" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_record_hand_accumulates_balance(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table_with_jackpot: dict,
    player_user: User,
):
    """3 hands, each 60 → pool balance = 180."""
    table_id = open_table_with_jackpot["id"]
    pool_id = open_table_with_jackpot["pool_id"]

    await async_client.post(
        f"/api/tables/{table_id}/buy-in",
        json={"player_id": str(player_user.id), "amount": 5000},
        headers=banker_headers,
    )

    for _ in range(3):
        resp = await async_client.post(
            f"/api/tables/{table_id}/jackpot/hand",
            headers=banker_headers,
        )
        assert resp.status_code == 200

    # Verify pool balance
    resp = await async_client.get(
        f"/api/jackpot-pools/{pool_id}",
        headers=banker_headers,
    )
    assert resp.json()["balance"] == 180


# ===== 觸發發放 =====


@pytest.mark.asyncio
async def test_trigger_payout_success(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table_with_jackpot: dict,
    player_user: User,
):
    table_id = open_table_with_jackpot["id"]
    pool_id = open_table_with_jackpot["pool_id"]

    # Seat player + build pool balance
    await async_client.post(
        f"/api/tables/{table_id}/buy-in",
        json={"player_id": str(player_user.id), "amount": 5000},
        headers=banker_headers,
    )
    # Record enough hands to accumulate 500+ (9 hands × 60 = 540)
    for _ in range(9):
        await async_client.post(
            f"/api/tables/{table_id}/jackpot/hand",
            headers=banker_headers,
        )

    # Trigger payout 300
    resp = await async_client.post(
        f"/api/tables/{table_id}/jackpot/trigger",
        json={
            "pool_id": pool_id,
            "winner_id": str(player_user.id),
            "hand_description": "四條K",
            "payout_amount": 300,
        },
        headers=banker_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["payout_amount"] == 300
    assert data["pool_balance_after"] == 540 - 300  # 240
    assert data["winner_id"] == str(player_user.id)

    # Verify pool balance
    resp = await async_client.get(
        f"/api/jackpot-pools/{pool_id}",
        headers=banker_headers,
    )
    assert resp.json()["balance"] == 240


@pytest.mark.asyncio
async def test_trigger_payout_insufficient_balance(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table_with_jackpot: dict,
    player_user: User,
):
    table_id = open_table_with_jackpot["id"]
    pool_id = open_table_with_jackpot["pool_id"]

    await async_client.post(
        f"/api/tables/{table_id}/buy-in",
        json={"player_id": str(player_user.id), "amount": 5000},
        headers=banker_headers,
    )
    # Record 1 hand → pool = 60
    await async_client.post(
        f"/api/tables/{table_id}/jackpot/hand",
        headers=banker_headers,
    )

    resp = await async_client.post(
        f"/api/tables/{table_id}/jackpot/trigger",
        json={
            "pool_id": pool_id,
            "winner_id": str(player_user.id),
            "hand_description": "同花順",
            "payout_amount": 200,
        },
        headers=banker_headers,
    )
    assert resp.status_code == 400
    assert "insufficient" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_trigger_payout_exact_balance(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table_with_jackpot: dict,
    player_user: User,
):
    table_id = open_table_with_jackpot["id"]
    pool_id = open_table_with_jackpot["pool_id"]

    await async_client.post(
        f"/api/tables/{table_id}/buy-in",
        json={"player_id": str(player_user.id), "amount": 5000},
        headers=banker_headers,
    )
    # 5 hands → pool = 300
    for _ in range(5):
        await async_client.post(
            f"/api/tables/{table_id}/jackpot/hand",
            headers=banker_headers,
        )

    resp = await async_client.post(
        f"/api/tables/{table_id}/jackpot/trigger",
        json={
            "pool_id": pool_id,
            "winner_id": str(player_user.id),
            "hand_description": "皇家同花順",
            "payout_amount": 300,
        },
        headers=banker_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["pool_balance_after"] == 0

    resp = await async_client.get(
        f"/api/jackpot-pools/{pool_id}",
        headers=banker_headers,
    )
    assert resp.json()["balance"] == 0


@pytest.mark.asyncio
async def test_trigger_payout_winner_not_seated(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table_with_jackpot: dict,
    player_user: User,
):
    table_id = open_table_with_jackpot["id"]
    pool_id = open_table_with_jackpot["pool_id"]

    # Seat player + build balance
    await async_client.post(
        f"/api/tables/{table_id}/buy-in",
        json={"player_id": str(player_user.id), "amount": 5000},
        headers=banker_headers,
    )
    await async_client.post(
        f"/api/tables/{table_id}/jackpot/hand",
        headers=banker_headers,
    )

    resp = await async_client.post(
        f"/api/tables/{table_id}/jackpot/trigger",
        json={
            "pool_id": pool_id,
            "winner_id": str(uuid.uuid4()),  # Not seated
            "hand_description": "四條A",
            "payout_amount": 50,
        },
        headers=banker_headers,
    )
    assert resp.status_code == 400
    assert "not seated" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_trigger_payout_table_not_open(
    async_client: AsyncClient,
    banker_headers: dict,
    jackpot_pool: dict,
    player_user: User,
):
    # Create CREATED table (not opened)
    resp = await async_client.post(
        "/api/tables",
        json={
            "name": "Not Open",
            "blind_level": "1/2",
            "rake_interval_minutes": 30,
            "rake_amount": 500,
            "jackpot_per_hand": 60,
            "jackpot_pool_id": jackpot_pool["id"],
        },
        headers=banker_headers,
    )
    table_id = resp.json()["id"]

    resp = await async_client.post(
        f"/api/tables/{table_id}/jackpot/trigger",
        json={
            "pool_id": jackpot_pool["id"],
            "winner_id": str(player_user.id),
            "hand_description": "四條A",
            "payout_amount": 100,
        },
        headers=banker_headers,
    )
    assert resp.status_code == 400
    assert "not open" in resp.json()["detail"].lower()


# ===== 歷史與跨桌 =====


@pytest.mark.asyncio
async def test_pool_triggers_history(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table_with_jackpot: dict,
    player_user: User,
):
    table_id = open_table_with_jackpot["id"]
    pool_id = open_table_with_jackpot["pool_id"]

    await async_client.post(
        f"/api/tables/{table_id}/buy-in",
        json={"player_id": str(player_user.id), "amount": 5000},
        headers=banker_headers,
    )
    # Build pool: 10 hands × 60 = 600
    for _ in range(10):
        await async_client.post(
            f"/api/tables/{table_id}/jackpot/hand",
            headers=banker_headers,
        )

    # Trigger twice
    for desc in ["四條K", "同花順"]:
        await async_client.post(
            f"/api/tables/{table_id}/jackpot/trigger",
            json={
                "pool_id": pool_id,
                "winner_id": str(player_user.id),
                "hand_description": desc,
                "payout_amount": 100,
            },
            headers=banker_headers,
        )

    resp = await async_client.get(
        f"/api/jackpot-pools/{pool_id}/triggers",
        headers=banker_headers,
    )
    assert resp.status_code == 200
    triggers = resp.json()
    assert len(triggers) == 2


@pytest.mark.asyncio
async def test_pool_balance_persists_across_tables(
    async_client: AsyncClient,
    banker_headers: dict,
    jackpot_pool: dict,
    player_user: User,
):
    pool_id = jackpot_pool["id"]

    # Table A: 5 hands × 60 = 300
    resp = await async_client.post(
        "/api/tables",
        json={
            "name": "Table A",
            "blind_level": "1/2",
            "rake_interval_minutes": 30,
            "rake_amount": 500,
            "jackpot_per_hand": 60,
            "jackpot_pool_id": pool_id,
        },
        headers=banker_headers,
    )
    table_a_id = resp.json()["id"]
    await async_client.patch(
        f"/api/tables/{table_a_id}/status",
        json={"status": "OPEN"},
        headers=banker_headers,
    )
    await async_client.post(
        f"/api/tables/{table_a_id}/buy-in",
        json={"player_id": str(player_user.id), "amount": 5000},
        headers=banker_headers,
    )
    for _ in range(5):
        await async_client.post(
            f"/api/tables/{table_a_id}/jackpot/hand",
            headers=banker_headers,
        )

    # Close table A: settle → cash out → close
    await async_client.patch(
        f"/api/tables/{table_a_id}/status",
        json={"status": "SETTLING"},
        headers=banker_headers,
    )
    await async_client.post(
        f"/api/tables/{table_a_id}/cash-out",
        json={"player_id": str(player_user.id), "chip_count": 4700},
        headers=banker_headers,
    )
    await async_client.patch(
        f"/api/tables/{table_a_id}/status",
        json={"status": "CLOSED"},
        headers=banker_headers,
    )

    # Table B: 3 hands × 60 = 180
    resp = await async_client.post(
        "/api/tables",
        json={
            "name": "Table B",
            "blind_level": "1/2",
            "rake_interval_minutes": 30,
            "rake_amount": 500,
            "jackpot_per_hand": 60,
            "jackpot_pool_id": pool_id,
        },
        headers=banker_headers,
    )
    table_b_id = resp.json()["id"]
    await async_client.patch(
        f"/api/tables/{table_b_id}/status",
        json={"status": "OPEN"},
        headers=banker_headers,
    )
    await async_client.post(
        f"/api/tables/{table_b_id}/buy-in",
        json={"player_id": str(player_user.id), "amount": 5000},
        headers=banker_headers,
    )
    for _ in range(3):
        await async_client.post(
            f"/api/tables/{table_b_id}/jackpot/hand",
            headers=banker_headers,
        )

    # Pool balance = 300 + 180 = 480
    resp = await async_client.get(
        f"/api/jackpot-pools/{pool_id}",
        headers=banker_headers,
    )
    assert resp.json()["balance"] == 480


# ===== balance_after 正確性 =====


@pytest.mark.asyncio
async def test_jackpot_contribution_balance_after(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table_with_jackpot: dict,
    player_user: User,
):
    """Buy-in 1000 → hand (deduct 60) → balance 940 → hand → balance 880."""
    table_id = open_table_with_jackpot["id"]
    await async_client.post(
        f"/api/tables/{table_id}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_headers,
    )

    # Hand 1
    await async_client.post(
        f"/api/tables/{table_id}/jackpot/hand",
        headers=banker_headers,
    )
    # Hand 2
    await async_client.post(
        f"/api/tables/{table_id}/jackpot/hand",
        headers=banker_headers,
    )

    # Check transactions
    resp = await async_client.get(
        f"/api/tables/{table_id}/transactions?player_id={player_user.id}",
        headers=banker_headers,
    )
    txns = resp.json()["transactions"]
    jp_txns = [t for t in txns if t["type"] == "JACKPOT_CONTRIBUTION"]
    assert len(jp_txns) == 2
    assert jp_txns[0]["amount"] == -60
    assert jp_txns[0]["balance_after"] == 940
    assert jp_txns[1]["amount"] == -60
    assert jp_txns[1]["balance_after"] == 880


@pytest.mark.asyncio
async def test_jackpot_payout_balance_after(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table_with_jackpot: dict,
    player_user: User,
):
    """Buy-in 1000 → payout 500 → balance 1500."""
    table_id = open_table_with_jackpot["id"]
    pool_id = open_table_with_jackpot["pool_id"]

    await async_client.post(
        f"/api/tables/{table_id}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_headers,
    )
    # Build pool: 9 hands × 60 = 540
    for _ in range(9):
        await async_client.post(
            f"/api/tables/{table_id}/jackpot/hand",
            headers=banker_headers,
        )

    # Trigger payout 500
    await async_client.post(
        f"/api/tables/{table_id}/jackpot/trigger",
        json={
            "pool_id": pool_id,
            "winner_id": str(player_user.id),
            "hand_description": "皇家同花順",
            "payout_amount": 500,
        },
        headers=banker_headers,
    )

    resp = await async_client.get(
        f"/api/tables/{table_id}/transactions?player_id={player_user.id}",
        headers=banker_headers,
    )
    txns = resp.json()["transactions"]
    payout_txn = [t for t in txns if t["type"] == "JACKPOT_PAYOUT"]
    assert len(payout_txn) == 1
    assert payout_txn[0]["amount"] == 500
    # balance = 1000 (buy-in) + 9 × (-60) (contributions) + 500 (payout) = 960
    assert payout_txn[0]["balance_after"] == 1000 - 540 + 500


# ===== 權限 =====


@pytest.mark.asyncio
async def test_record_hand_other_bankers_table_rejected(
    async_client: AsyncClient,
    banker_b_headers: dict,
    open_table_with_jackpot: dict,
    player_user: User,
    banker_headers: dict,
):
    """Banker B cannot record hand on Banker A's table."""
    table_id = open_table_with_jackpot["id"]
    await async_client.post(
        f"/api/tables/{table_id}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_headers,
    )
    resp = await async_client.post(
        f"/api/tables/{table_id}/jackpot/hand",
        headers=banker_b_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_trigger_payout_other_bankers_table_rejected(
    async_client: AsyncClient,
    banker_b_headers: dict,
    open_table_with_jackpot: dict,
    player_user: User,
    banker_headers: dict,
):
    """Banker B cannot trigger payout on Banker A's table."""
    table_id = open_table_with_jackpot["id"]
    pool_id = open_table_with_jackpot["pool_id"]
    await async_client.post(
        f"/api/tables/{table_id}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_headers,
    )
    await async_client.post(
        f"/api/tables/{table_id}/jackpot/hand",
        headers=banker_headers,
    )
    resp = await async_client.post(
        f"/api/tables/{table_id}/jackpot/trigger",
        json={
            "pool_id": pool_id,
            "winner_id": str(player_user.id),
            "hand_description": "四條A",
            "payout_amount": 50,
        },
        headers=banker_b_headers,
    )
    assert resp.status_code == 403
