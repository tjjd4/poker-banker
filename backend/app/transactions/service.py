import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tables.models import PlayerSeat, Table
from app.transactions.models import Transaction
from app.transactions.rake import calculate_rake
from app.users.models import User


async def _lock_table(db: AsyncSession, table_id: uuid.UUID) -> Table | None:
    """Load a table row with FOR UPDATE lock (PostgreSQL) to serialize operations.

    SQLite does not support FOR UPDATE, so the lock clause is skipped.
    """
    stmt = select(Table).where(Table.id == table_id)
    if db.bind.dialect.name != "sqlite":
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def buy_in(
    db: AsyncSession,
    table_id: uuid.UUID,
    player_id: uuid.UUID,
    amount: int,
    created_by: uuid.UUID,
) -> dict:
    # 1. Table must be OPEN (FOR UPDATE lock serializes concurrent requests)
    table = await _lock_table(db, table_id)
    if table is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Table not found"
        )
    if table.status != "OPEN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Table is not open for buy-in",
        )

    # 2. Player must exist and be active
    player = await db.get(User, player_id)
    if player is None or not player.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Player not found"
        )

    # 3. Get or create PlayerSeat
    result = await db.execute(
        select(PlayerSeat).where(
            PlayerSeat.table_id == table_id,
            PlayerSeat.player_id == player_id,
        )
    )
    seat = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if seat is None:
        seat = PlayerSeat(
            id=uuid.uuid4(),
            table_id=table_id,
            player_id=player_id,
            seated_at=now,
            is_active=True,
        )
        db.add(seat)
    elif not seat.is_active:
        # Re-seat: keep original seated_at, clear left_at
        seat.is_active = True
        seat.left_at = None

    # 4. Calculate balance_after
    sum_result = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.table_id == table_id,
            Transaction.player_id == player_id,
        )
    )
    current_sum = sum_result.scalar()
    balance_after = current_sum + amount

    # 5. Create BUY_IN transaction
    txn = Transaction(
        id=uuid.uuid4(),
        table_id=table_id,
        player_id=player_id,
        type="BUY_IN",
        amount=amount,
        balance_after=balance_after,
        created_by=created_by,
    )
    db.add(txn)
    await db.commit()
    await db.refresh(txn)

    # 6. Calculate total_buy_in
    buy_in_result = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.table_id == table_id,
            Transaction.player_id == player_id,
            Transaction.type == "BUY_IN",
        )
    )
    total_buy_in = buy_in_result.scalar()

    return {
        "transaction": txn,
        "total_buy_in": total_buy_in,
        "current_balance": balance_after,
    }


async def cash_out(
    db: AsyncSession,
    table_id: uuid.UUID,
    player_id: uuid.UUID,
    chip_count: int,
    created_by: uuid.UUID,
    now: datetime | None = None,
) -> dict:
    if now is None:
        now = datetime.now(timezone.utc)

    # 1. Table must be OPEN or SETTLING (FOR UPDATE lock serializes concurrent requests)
    table = await _lock_table(db, table_id)
    if table is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Table not found"
        )
    if table.status not in ("OPEN", "SETTLING"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Table is not open for cash-out",
        )

    # 2. Player must be actively seated
    result = await db.execute(
        select(PlayerSeat).where(
            PlayerSeat.table_id == table_id,
            PlayerSeat.player_id == player_id,
        )
    )
    seat = result.scalar_one_or_none()
    if seat is None or not seat.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Player is not seated at this table",
        )

    # 3. Total buy-in
    buy_in_result = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.table_id == table_id,
            Transaction.player_id == player_id,
            Transaction.type == "BUY_IN",
        )
    )
    total_buy_in = buy_in_result.scalar()

    # 4. Calculate rake (normalize naive datetimes from SQLite)
    seated_at = seat.seated_at
    if seated_at.tzinfo is None:
        seated_at = seated_at.replace(tzinfo=timezone.utc)
    rake = calculate_rake(
        seated_at, now, table.rake_interval_minutes, table.rake_amount
    )

    # 5. Current sum of all amounts
    sum_result = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.table_id == table_id,
            Transaction.player_id == player_id,
        )
    )
    current_sum = sum_result.scalar()

    # 6. CASH_OUT transaction
    cash_out_balance = current_sum + (-chip_count)
    txn_cashout = Transaction(
        id=uuid.uuid4(),
        table_id=table_id,
        player_id=player_id,
        type="CASH_OUT",
        amount=-chip_count,
        balance_after=cash_out_balance,
        created_by=created_by,
    )
    db.add(txn_cashout)

    # 7. RAKE transaction
    rake_balance = cash_out_balance + (-rake)
    txn_rake = Transaction(
        id=uuid.uuid4(),
        table_id=table_id,
        player_id=player_id,
        type="RAKE",
        amount=-rake,
        balance_after=rake_balance,
        created_by=created_by,
    )
    db.add(txn_rake)

    # 8. Update PlayerSeat
    seat.is_active = False
    seat.left_at = now

    # 9. Atomic commit
    await db.commit()
    await db.refresh(txn_cashout)
    await db.refresh(txn_rake)

    # 10. Results
    net_result = chip_count - total_buy_in
    seated_minutes = (now - seated_at).total_seconds() / 60

    return {
        "transactions": [txn_cashout, txn_rake],
        "chip_count": chip_count,
        "total_buy_in": total_buy_in,
        "rake_amount": rake,
        "net_result": net_result,
        "seated_minutes": seated_minutes,
    }


async def get_player_status(
    db: AsyncSession, table_id: uuid.UUID, player_id: uuid.UUID
) -> dict | None:
    # Get seat
    result = await db.execute(
        select(PlayerSeat).where(
            PlayerSeat.table_id == table_id,
            PlayerSeat.player_id == player_id,
        )
    )
    seat = result.scalar_one_or_none()
    if seat is None:
        return None

    # Get player display name
    player = await db.get(User, player_id)

    # Total buy-in
    buy_in_result = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.table_id == table_id,
            Transaction.player_id == player_id,
            Transaction.type == "BUY_IN",
        )
    )
    total_buy_in = buy_in_result.scalar()

    # Current balance
    sum_result = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.table_id == table_id,
            Transaction.player_id == player_id,
        )
    )
    current_balance = sum_result.scalar()

    return {
        "player_id": seat.player_id,
        "display_name": player.display_name if player else "Unknown",
        "total_buy_in": total_buy_in,
        "current_balance": current_balance,
        "is_seated": seat.is_active,
        "seated_at": seat.seated_at,
        "left_at": seat.left_at,
    }


async def get_table_players(
    db: AsyncSession, table_id: uuid.UUID
) -> list[dict]:
    result = await db.execute(
        select(PlayerSeat.player_id).where(PlayerSeat.table_id == table_id)
    )
    player_ids = [row[0] for row in result.all()]

    players = []
    for pid in player_ids:
        ps = await get_player_status(db, table_id, pid)
        if ps is not None:
            players.append(ps)
    return players


async def get_table_transactions(
    db: AsyncSession,
    table_id: uuid.UUID,
    player_id: uuid.UUID | None = None,
) -> list[Transaction]:
    stmt = select(Transaction).where(Transaction.table_id == table_id)
    if player_id is not None:
        stmt = stmt.where(Transaction.player_id == player_id)
    stmt = stmt.order_by(Transaction.created_at)
    result = await db.execute(stmt)
    return list(result.scalars().all())
