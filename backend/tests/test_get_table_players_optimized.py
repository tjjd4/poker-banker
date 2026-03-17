"""
Tests for the optimized get_table_players query (Task 2.3).

These tests verify that the rewritten get_table_players returns correct
aggregated data using a single query instead of per-player loops.
"""
import uuid
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import hash_password
from app.tables.models import PlayerSeat, Table
from app.transactions.models import Transaction
from app.users.models import User


# ---------------------------------------------------------------------------
# Helper to create test data directly in the DB
# ---------------------------------------------------------------------------


async def _create_user(session: AsyncSession, username: str) -> User:
    user = User(
        id=uuid.uuid4(),
        username=username,
        password_hash=hash_password("pass"),
        display_name=f"Display {username}",
        role="player",
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _create_table(session: AsyncSession, banker_id: uuid.UUID) -> Table:
    table = Table(
        id=uuid.uuid4(),
        name="Test Table",
        blind_level="1/2",
        rake_interval_minutes=30,
        rake_amount=100,
        jackpot_per_hand=0,
        status="OPEN",
        banker_id=banker_id,
    )
    session.add(table)
    await session.flush()
    return table


async def _seat_player(
    session: AsyncSession, table_id: uuid.UUID, player_id: uuid.UUID
) -> PlayerSeat:
    from datetime import datetime, timezone
    seat = PlayerSeat(
        id=uuid.uuid4(),
        table_id=table_id,
        player_id=player_id,
        seated_at=datetime.now(timezone.utc),
        is_active=True,
    )
    session.add(seat)
    await session.flush()
    return seat


async def _add_transaction(
    session: AsyncSession,
    table_id: uuid.UUID,
    player_id: uuid.UUID,
    txn_type: str,
    amount: int,
    balance_after: int,
    created_by: uuid.UUID,
) -> Transaction:
    txn = Transaction(
        id=uuid.uuid4(),
        table_id=table_id,
        player_id=player_id,
        type=txn_type,
        amount=amount,
        balance_after=balance_after,
        created_by=created_by,
    )
    session.add(txn)
    await session.flush()
    return txn


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_table_players_empty_table(session: AsyncSession, admin_user: User):
    """get_table_players returns empty list for a table with no players."""
    from app.transactions.service import get_table_players

    table = await _create_table(session, admin_user.id)
    await session.commit()

    result = await get_table_players(session, table.id)
    assert result == []


@pytest.mark.asyncio
async def test_get_table_players_single_player_correct_totals(
    session: AsyncSession, admin_user: User
):
    """get_table_players returns correct total_buy_in and current_balance for a single player."""
    from app.transactions.service import get_table_players

    table = await _create_table(session, admin_user.id)
    player = await _create_user(session, "solo_player")
    await _seat_player(session, table.id, player.id)

    # Two buy-ins: 1000 + 500
    await _add_transaction(session, table.id, player.id, "BUY_IN", 1000, 1000, admin_user.id)
    await _add_transaction(session, table.id, player.id, "BUY_IN", 500, 1500, admin_user.id)
    await session.commit()

    result = await get_table_players(session, table.id)

    assert len(result) == 1
    p = result[0]
    assert p["player_id"] == player.id
    assert p["display_name"] == "Display solo_player"
    assert p["total_buy_in"] == 1500
    assert p["current_balance"] == 1500
    assert p["is_seated"] is True


@pytest.mark.asyncio
async def test_get_table_players_multiple_players(
    session: AsyncSession, admin_user: User
):
    """get_table_players returns correct data for multiple players independently."""
    from app.transactions.service import get_table_players

    table = await _create_table(session, admin_user.id)
    player_a = await _create_user(session, "player_a")
    player_b = await _create_user(session, "player_b")

    await _seat_player(session, table.id, player_a.id)
    await _seat_player(session, table.id, player_b.id)

    # Player A: buy-in 2000
    await _add_transaction(session, table.id, player_a.id, "BUY_IN", 2000, 2000, admin_user.id)
    # Player B: buy-in 1000, then another 500
    await _add_transaction(session, table.id, player_b.id, "BUY_IN", 1000, 1000, admin_user.id)
    await _add_transaction(session, table.id, player_b.id, "BUY_IN", 500, 1500, admin_user.id)
    await session.commit()

    result = await get_table_players(session, table.id)

    assert len(result) == 2
    by_id = {p["player_id"]: p for p in result}

    assert by_id[player_a.id]["total_buy_in"] == 2000
    assert by_id[player_a.id]["current_balance"] == 2000

    assert by_id[player_b.id]["total_buy_in"] == 1500
    assert by_id[player_b.id]["current_balance"] == 1500


@pytest.mark.asyncio
async def test_get_table_players_balance_includes_all_transaction_types(
    session: AsyncSession, admin_user: User
):
    """current_balance reflects all transaction types (BUY_IN + negative amounts)."""
    from app.transactions.service import get_table_players

    table = await _create_table(session, admin_user.id)
    player = await _create_user(session, "balance_player")
    await _seat_player(session, table.id, player.id)

    # Buy-in 2000, rake -200 → net balance = 1800
    await _add_transaction(session, table.id, player.id, "BUY_IN", 2000, 2000, admin_user.id)
    await _add_transaction(session, table.id, player.id, "RAKE", -200, 1800, admin_user.id)
    await session.commit()

    result = await get_table_players(session, table.id)

    assert len(result) == 1
    p = result[0]
    assert p["total_buy_in"] == 2000      # Only BUY_IN transactions
    assert p["current_balance"] == 1800   # BUY_IN + RAKE


@pytest.mark.asyncio
async def test_get_table_players_seated_status_correct(
    session: AsyncSession, admin_user: User
):
    """is_seated reflects the current is_active state of the PlayerSeat."""
    from app.transactions.service import get_table_players
    from datetime import datetime, timezone

    table = await _create_table(session, admin_user.id)
    player = await _create_user(session, "seated_player")
    seat = await _seat_player(session, table.id, player.id)

    await _add_transaction(session, table.id, player.id, "BUY_IN", 1000, 1000, admin_user.id)
    await session.commit()

    # Initially seated
    result = await get_table_players(session, table.id)
    assert result[0]["is_seated"] is True

    # Mark as left
    seat.is_active = False
    seat.left_at = datetime.now(timezone.utc)
    await session.commit()

    # Need a fresh session query to see updated state
    result2 = await get_table_players(session, table.id)
    assert result2[0]["is_seated"] is False


@pytest.mark.asyncio
async def test_get_table_players_player_with_no_transactions(
    session: AsyncSession, admin_user: User
):
    """A seated player with no transactions should have total_buy_in=0, current_balance=0."""
    from app.transactions.service import get_table_players

    table = await _create_table(session, admin_user.id)
    player = await _create_user(session, "no_txn_player")
    await _seat_player(session, table.id, player.id)
    await session.commit()

    result = await get_table_players(session, table.id)

    assert len(result) == 1
    p = result[0]
    assert p["total_buy_in"] == 0
    assert p["current_balance"] == 0
