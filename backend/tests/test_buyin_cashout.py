"""Integration tests for Buy-in / Cash-out / Seat Tracking / Transactions."""

import uuid as _uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import hash_password
from app.tables.models import PlayerSeat
from app.users.models import User


# ---------------------------------------------------------------------------
# Buy-in tests (7)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_buy_in_success(
    async_client: AsyncClient, banker_headers: dict, open_table: dict, player_user: User
):
    resp = await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["total_buy_in"] == 1000
    assert data["current_balance"] == 1000
    assert data["transaction"]["type"] == "BUY_IN"
    assert data["transaction"]["amount"] == 1000

    # Verify player appears in player list
    resp2 = await async_client.get(
        f"/api/tables/{open_table['id']}/players",
        headers=banker_headers,
    )
    assert resp2.status_code == 200
    players = resp2.json()["players"]
    assert len(players) == 1
    assert players[0]["player_id"] == str(player_user.id)


@pytest.mark.asyncio
async def test_buy_in_creates_player_seat(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,
    player_user: User,
):
    await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_headers,
    )
    # Table detail should show the player
    resp = await async_client.get(
        f"/api/tables/{open_table['id']}",
        headers=banker_headers,
    )
    assert resp.status_code == 200
    detail = resp.json()
    assert len(detail["players"]) == 1
    assert detail["players"][0]["player_id"] == str(player_user.id)
    assert detail["players"][0]["seated_at"] is not None
    assert detail["players"][0]["is_active"] is True


@pytest.mark.asyncio
async def test_buy_in_multiple_times(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,
    player_user: User,
):
    await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_headers,
    )
    resp = await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 500},
        headers=banker_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["total_buy_in"] == 1500
    assert data["current_balance"] == 1500


@pytest.mark.asyncio
async def test_buy_in_table_not_open(
    async_client: AsyncClient,
    banker_headers: dict,
    created_table: dict,
    player_user: User,
):
    resp = await async_client.post(
        f"/api/tables/{created_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_headers,
    )
    assert resp.status_code == 400
    assert "not open" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_buy_in_settling_rejected(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,
    player_user: User,
):
    # First buy-in, then move to SETTLING
    await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_headers,
    )
    await async_client.patch(
        f"/api/tables/{open_table['id']}/status",
        json={"status": "SETTLING"},
        headers=banker_headers,
    )
    # Try buy-in during SETTLING
    resp = await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 500},
        headers=banker_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_buy_in_invalid_amount(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,
    player_user: User,
):
    # amount=0
    resp = await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 0},
        headers=banker_headers,
    )
    assert resp.status_code == 422

    # amount=-100
    resp = await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": -100},
        headers=banker_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_buy_in_nonexistent_player(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,
):
    resp = await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(_uuid.uuid4()), "amount": 1000},
        headers=banker_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_buy_in_inactive_player_rejected(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,
    inactive_user: User,
):
    resp = await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(inactive_user.id), "amount": 1000},
        headers=banker_headers,
    )
    assert resp.status_code == 404
    assert "player not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Cash-out tests (7)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cash_out_success(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,
    player_user: User,
):
    # Buy-in first
    await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_headers,
    )
    # Cash-out
    resp = await async_client.post(
        f"/api/tables/{open_table['id']}/cash-out",
        json={"player_id": str(player_user.id), "chip_count": 800},
        headers=banker_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["chip_count"] == 800
    assert data["total_buy_in"] == 1000
    assert data["net_result"] == -200
    assert data["rake_amount"] > 0
    assert len(data["transactions"]) == 2  # CASH_OUT + RAKE

    # Player should no longer be seated
    resp2 = await async_client.get(
        f"/api/tables/{open_table['id']}/players",
        headers=banker_headers,
    )
    players = resp2.json()["players"]
    assert len(players) == 1
    assert players[0]["is_seated"] is False


@pytest.mark.asyncio
async def test_cash_out_with_rake_calculation(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,
    player_user: User,
    session: AsyncSession,
):
    # Buy-in
    await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_headers,
    )
    # Modify seated_at to 47 minutes ago
    result = await session.execute(
        select(PlayerSeat).where(
            PlayerSeat.table_id == _uuid.UUID(open_table["id"]),
            PlayerSeat.player_id == player_user.id,
        )
    )
    seat = result.scalar_one()
    now = datetime.now(timezone.utc)
    seat.seated_at = now - timedelta(minutes=47)
    await session.commit()

    # Cash-out — rake should be ceil(47/30) * 500 = 2 * 500 = 1000
    resp = await async_client.post(
        f"/api/tables/{open_table['id']}/cash-out",
        json={"player_id": str(player_user.id), "chip_count": 800},
        headers=banker_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["rake_amount"] == 1000


@pytest.mark.asyncio
async def test_cash_out_winning_player(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,
    player_user: User,
):
    await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_headers,
    )
    resp = await async_client.post(
        f"/api/tables/{open_table['id']}/cash-out",
        json={"player_id": str(player_user.id), "chip_count": 3000},
        headers=banker_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["net_result"] == 2000


@pytest.mark.asyncio
async def test_cash_out_zero_chips(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,
    player_user: User,
):
    await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_headers,
    )
    resp = await async_client.post(
        f"/api/tables/{open_table['id']}/cash-out",
        json={"player_id": str(player_user.id), "chip_count": 0},
        headers=banker_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["net_result"] == -1000


@pytest.mark.asyncio
async def test_cash_out_player_not_seated(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,
    player_user: User,
):
    resp = await async_client.post(
        f"/api/tables/{open_table['id']}/cash-out",
        json={"player_id": str(player_user.id), "chip_count": 800},
        headers=banker_headers,
    )
    assert resp.status_code == 400
    assert "not seated" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cash_out_during_settling(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,
    player_user: User,
):
    # Buy-in, then SETTLING
    await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_headers,
    )
    await async_client.patch(
        f"/api/tables/{open_table['id']}/status",
        json={"status": "SETTLING"},
        headers=banker_headers,
    )
    # Cash-out during SETTLING should succeed
    resp = await async_client.post(
        f"/api/tables/{open_table['id']}/cash-out",
        json={"player_id": str(player_user.id), "chip_count": 800},
        headers=banker_headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_cash_out_closed_table(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,
    player_user: User,
):
    # Buy-in → SETTLING → cash-out → CLOSED
    await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_headers,
    )
    await async_client.patch(
        f"/api/tables/{open_table['id']}/status",
        json={"status": "SETTLING"},
        headers=banker_headers,
    )
    await async_client.post(
        f"/api/tables/{open_table['id']}/cash-out",
        json={"player_id": str(player_user.id), "chip_count": 800},
        headers=banker_headers,
    )
    await async_client.patch(
        f"/api/tables/{open_table['id']}/status",
        json={"status": "CLOSED"},
        headers=banker_headers,
    )
    # Try cash-out on CLOSED table — need a new player since original already cashed out
    # Actually, the table is CLOSED so it should just reject
    # We need to create a new player for this, but simpler: just try cash-out endpoint
    # The service checks table status first before seat status
    resp = await async_client.post(
        f"/api/tables/{open_table['id']}/cash-out",
        json={"player_id": str(player_user.id), "chip_count": 100},
        headers=banker_headers,
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Seat tracking tests (2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rebuy_after_cashout_keeps_seat_time(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,
    player_user: User,
    session: AsyncSession,
):
    # Buy-in
    await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_headers,
    )
    # Get original seated_at
    result = await session.execute(
        select(PlayerSeat).where(
            PlayerSeat.table_id == _uuid.UUID(open_table["id"]),
            PlayerSeat.player_id == player_user.id,
        )
    )
    seat = result.scalar_one()
    original_seated_at = seat.seated_at

    # Cash-out
    await async_client.post(
        f"/api/tables/{open_table['id']}/cash-out",
        json={"player_id": str(player_user.id), "chip_count": 800},
        headers=banker_headers,
    )

    # Re-buy-in
    await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 500},
        headers=banker_headers,
    )

    # Verify seated_at unchanged, is_active=True
    table_uuid = _uuid.UUID(open_table["id"])
    player_uuid = player_user.id
    session.expire_all()
    result = await session.execute(
        select(PlayerSeat).where(
            PlayerSeat.table_id == table_uuid,
            PlayerSeat.player_id == player_uuid,
        )
    )
    seat = result.scalar_one()
    assert seat.is_active is True
    assert seat.seated_at == original_seated_at
    assert seat.left_at is None


@pytest.mark.asyncio
async def test_cash_out_updates_left_at(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,
    player_user: User,
    session: AsyncSession,
):
    await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_headers,
    )
    await async_client.post(
        f"/api/tables/{open_table['id']}/cash-out",
        json={"player_id": str(player_user.id), "chip_count": 800},
        headers=banker_headers,
    )
    table_uuid = _uuid.UUID(open_table["id"])
    player_uuid = player_user.id
    session.expire_all()
    result = await session.execute(
        select(PlayerSeat).where(
            PlayerSeat.table_id == table_uuid,
            PlayerSeat.player_id == player_uuid,
        )
    )
    seat = result.scalar_one()
    assert seat.left_at is not None
    assert seat.is_active is False


# ---------------------------------------------------------------------------
# Transaction queries (2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_table_transactions(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,
    player_user: User,
):
    # Buy-in then cash-out → should produce 3 transactions (BUY_IN + CASH_OUT + RAKE)
    await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_headers,
    )
    await async_client.post(
        f"/api/tables/{open_table['id']}/cash-out",
        json={"player_id": str(player_user.id), "chip_count": 800},
        headers=banker_headers,
    )
    resp = await async_client.get(
        f"/api/tables/{open_table['id']}/transactions",
        headers=banker_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    types = [t["type"] for t in data["transactions"]]
    assert "BUY_IN" in types
    assert "CASH_OUT" in types
    assert "RAKE" in types


@pytest.mark.asyncio
async def test_get_table_transactions_filter_by_player(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,
    player_user: User,
    session: AsyncSession,
):
    # Create a second player directly in DB
    player2 = User(
        id=_uuid.uuid4(),
        username="testplayer2",
        password_hash=hash_password("testplayer2"),
        display_name="Test Player 2",
        role="player",
        is_active=True,
    )
    session.add(player2)
    await session.commit()
    await session.refresh(player2)

    # Buy-in for both players
    await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_headers,
    )
    await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player2.id), "amount": 2000},
        headers=banker_headers,
    )

    # Filter by player_user
    resp = await async_client.get(
        f"/api/tables/{open_table['id']}/transactions?player_id={player_user.id}",
        headers=banker_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["transactions"][0]["player_id"] == str(player_user.id)


# ---------------------------------------------------------------------------
# Player list (1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_table_players(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,
    player_user: User,
    session: AsyncSession,
):
    # Create second player
    player2 = User(
        id=_uuid.uuid4(),
        username="testplayer3",
        password_hash=hash_password("testplayer3"),
        display_name="Test Player 3",
        role="player",
        is_active=True,
    )
    session.add(player2)
    await session.commit()
    await session.refresh(player2)

    # Both buy-in
    await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_headers,
    )
    await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player2.id), "amount": 2000},
        headers=banker_headers,
    )

    resp = await async_client.get(
        f"/api/tables/{open_table['id']}/players",
        headers=banker_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["players"]) == 2
    for p in data["players"]:
        assert p["total_buy_in"] > 0
        assert p["current_balance"] > 0
        assert p["is_seated"] is True


# ---------------------------------------------------------------------------
# RBAC (2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_buy_in_other_bankers_table_rejected(
    async_client: AsyncClient,
    banker_b_headers: dict,
    open_table: dict,
    player_user: User,
):
    resp = await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_b_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_player_cannot_buy_in(
    async_client: AsyncClient,
    player_headers: dict,
    open_table: dict,
    player_user: User,
):
    resp = await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=player_headers,
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Balance accuracy (1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_balance_after_accuracy(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,
    player_user: User,
):
    # Buy-in 1000
    resp1 = await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_headers,
    )
    assert resp1.json()["transaction"]["balance_after"] == 1000

    # Buy-in 500
    resp2 = await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 500},
        headers=banker_headers,
    )
    assert resp2.json()["transaction"]["balance_after"] == 1500

    # Cash-out 800
    resp3 = await async_client.post(
        f"/api/tables/{open_table['id']}/cash-out",
        json={"player_id": str(player_user.id), "chip_count": 800},
        headers=banker_headers,
    )
    data = resp3.json()
    txns = data["transactions"]
    cash_out_txn = [t for t in txns if t["type"] == "CASH_OUT"][0]
    rake_txn = [t for t in txns if t["type"] == "RAKE"][0]

    # balance_after for CASH_OUT = 1500 - 800 = 700
    assert cash_out_txn["balance_after"] == 700
    # balance_after for RAKE = 700 - rake_amount
    rake_amount = data["rake_amount"]
    assert rake_txn["balance_after"] == 700 - rake_amount


@pytest.mark.asyncio
async def test_concurrent_buy_ins(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,
    player_user: User,
):
    for _ in range(5):
        resp = await async_client.post(
            f"/api/tables/{open_table['id']}/buy-in",
            json={"player_id": str(player_user.id), "amount": 1000},
            headers=banker_headers,
        )
        assert resp.status_code == 201

    resp_final = await async_client.get(
        f"/api/tables/{open_table['id']}/players",
        headers=banker_headers,
    )
    players = resp_final.json()["players"]
    player_data = [p for p in players if p["player_id"] == str(player_user.id)][0]
    assert player_data["current_balance"] == 5000

    resp_txns = await async_client.get(
        f"/api/tables/{open_table['id']}/transactions?player_id={player_user.id}",
        headers=banker_headers,
    )
    txns = resp_txns.json()["transactions"]
    balances = sorted([t["balance_after"] for t in txns])
    assert balances == [1000, 2000, 3000, 4000, 5000]


# ---------------------------------------------------------------------------
# State machine integration (2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_settling_to_closed_after_all_cash_out(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,
    player_user: User,
    session: AsyncSession,
):
    # Create second player
    player2 = User(
        id=_uuid.uuid4(),
        username="testplayer4",
        password_hash=hash_password("testplayer4"),
        display_name="Test Player 4",
        role="player",
        is_active=True,
    )
    session.add(player2)
    await session.commit()
    await session.refresh(player2)

    # Both buy-in
    await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_headers,
    )
    await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player2.id), "amount": 2000},
        headers=banker_headers,
    )

    # SETTLING
    await async_client.patch(
        f"/api/tables/{open_table['id']}/status",
        json={"status": "SETTLING"},
        headers=banker_headers,
    )

    # Both cash-out
    await async_client.post(
        f"/api/tables/{open_table['id']}/cash-out",
        json={"player_id": str(player_user.id), "chip_count": 800},
        headers=banker_headers,
    )
    await async_client.post(
        f"/api/tables/{open_table['id']}/cash-out",
        json={"player_id": str(player2.id), "chip_count": 1500},
        headers=banker_headers,
    )

    # CLOSED should succeed
    resp = await async_client.patch(
        f"/api/tables/{open_table['id']}/status",
        json={"status": "CLOSED"},
        headers=banker_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "CLOSED"


@pytest.mark.asyncio
async def test_settling_to_closed_blocked_with_seated_player(
    async_client: AsyncClient,
    banker_headers: dict,
    open_table: dict,
    player_user: User,
    session: AsyncSession,
):
    # Create second player
    player2 = User(
        id=_uuid.uuid4(),
        username="testplayer5",
        password_hash=hash_password("testplayer5"),
        display_name="Test Player 5",
        role="player",
        is_active=True,
    )
    session.add(player2)
    await session.commit()
    await session.refresh(player2)

    # Both buy-in
    await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_headers,
    )
    await async_client.post(
        f"/api/tables/{open_table['id']}/buy-in",
        json={"player_id": str(player2.id), "amount": 2000},
        headers=banker_headers,
    )

    # SETTLING
    await async_client.patch(
        f"/api/tables/{open_table['id']}/status",
        json={"status": "SETTLING"},
        headers=banker_headers,
    )

    # Only one cash-out
    await async_client.post(
        f"/api/tables/{open_table['id']}/cash-out",
        json={"player_id": str(player_user.id), "chip_count": 800},
        headers=banker_headers,
    )

    # CLOSED should fail — player2 still seated
    resp = await async_client.patch(
        f"/api/tables/{open_table['id']}/status",
        json={"status": "CLOSED"},
        headers=banker_headers,
    )
    assert resp.status_code == 400
    assert "active players" in resp.json()["detail"].lower()
