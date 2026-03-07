import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.jackpot.models import JackpotPool, JackpotTrigger
from app.jackpot.schemas import JackpotPoolCreate, JackpotTriggerRequest
from app.tables.models import PlayerSeat, Table
from app.transactions.models import Transaction
from app.transactions.service import _lock_table
from app.users.models import User


async def create_pool(
    db: AsyncSession, banker_id: uuid.UUID, data: JackpotPoolCreate
) -> JackpotPool:
    pool = JackpotPool(
        id=uuid.uuid4(),
        name=data.name,
        balance=0,
        banker_id=banker_id,
    )
    db.add(pool)
    await db.commit()
    await db.refresh(pool)
    return pool


async def list_pools(
    db: AsyncSession, current_user: User
) -> list[JackpotPool]:
    stmt = select(JackpotPool)
    if current_user.role != "admin":
        stmt = stmt.where(JackpotPool.banker_id == current_user.id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_pool(
    db: AsyncSession, pool_id: uuid.UUID
) -> JackpotPool | None:
    return await db.get(JackpotPool, pool_id)


async def record_hand(
    db: AsyncSession, table_id: uuid.UUID, operated_by: uuid.UUID
) -> dict:
    # 1. Lock table + verify OPEN
    table = await _lock_table(db, table_id)
    if table is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Table not found"
        )
    if table.status != "OPEN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Table is not open",
        )

    # 2. Jackpot must be enabled
    if table.jackpot_per_hand <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jackpot is not enabled for this table",
        )

    # 3. Must have linked pool
    if table.jackpot_pool_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Table has no jackpot pool linked",
        )

    # 4. Get active players
    result = await db.execute(
        select(PlayerSeat).where(
            PlayerSeat.table_id == table_id,
            PlayerSeat.is_active == True,  # noqa: E712
        )
    )
    seats = list(result.scalars().all())
    player_count = len(seats)

    if player_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active players at the table",
        )

    # 5. Calculate split
    per_player = table.jackpot_per_hand // player_count
    remainder = table.jackpot_per_hand % player_count

    # 6. Create JACKPOT_CONTRIBUTION transactions for each player
    contributions = []
    for seat in seats:
        # Calculate balance_after
        sum_result = await db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.table_id == table_id,
                Transaction.player_id == seat.player_id,
            )
        )
        current_sum = sum_result.scalar()
        balance_after = current_sum + (-per_player)

        txn = Transaction(
            id=uuid.uuid4(),
            table_id=table_id,
            player_id=seat.player_id,
            type="JACKPOT_CONTRIBUTION",
            amount=-per_player,
            balance_after=balance_after,
            created_by=operated_by,
        )
        db.add(txn)

        # Get display name
        player = await db.get(User, seat.player_id)
        contributions.append({
            "player_id": seat.player_id,
            "display_name": player.display_name if player else "Unknown",
            "amount": per_player,
        })

    # 7. Atomic pool balance update
    await db.execute(
        update(JackpotPool)
        .where(JackpotPool.id == table.jackpot_pool_id)
        .values(balance=JackpotPool.balance + table.jackpot_per_hand)
    )

    await db.commit()

    # 8. Re-fetch pool for response
    pool = await db.get(JackpotPool, table.jackpot_pool_id)

    return {
        "pool_id": pool.id,
        "pool_balance": pool.balance,
        "jackpot_per_hand": table.jackpot_per_hand,
        "contributions": contributions,
        "remainder": remainder,
    }


async def trigger_payout(
    db: AsyncSession,
    table_id: uuid.UUID,
    data: JackpotTriggerRequest,
    operated_by: uuid.UUID,
) -> JackpotTrigger:
    # 1. Lock table + verify OPEN
    table = await _lock_table(db, table_id)
    if table is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Table not found"
        )
    if table.status != "OPEN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Table is not open",
        )

    # 2. Get pool + check balance
    pool = await db.get(JackpotPool, data.pool_id)
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jackpot pool not found",
        )
    if pool.balance < data.payout_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient jackpot pool balance",
        )

    # 3. Winner must be seated
    seat_result = await db.execute(
        select(PlayerSeat).where(
            PlayerSeat.table_id == table_id,
            PlayerSeat.player_id == data.winner_id,
            PlayerSeat.is_active == True,  # noqa: E712
        )
    )
    if seat_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Winner is not seated at this table",
        )

    # 4. Create JACKPOT_PAYOUT transaction
    sum_result = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.table_id == table_id,
            Transaction.player_id == data.winner_id,
        )
    )
    current_sum = sum_result.scalar()
    balance_after = current_sum + data.payout_amount

    txn = Transaction(
        id=uuid.uuid4(),
        table_id=table_id,
        player_id=data.winner_id,
        type="JACKPOT_PAYOUT",
        amount=data.payout_amount,
        balance_after=balance_after,
        created_by=operated_by,
    )
    db.add(txn)

    # 5. Atomic pool balance update
    pool_balance_after = pool.balance - data.payout_amount
    await db.execute(
        update(JackpotPool)
        .where(JackpotPool.id == data.pool_id)
        .values(balance=JackpotPool.balance - data.payout_amount)
    )

    # 6. Create trigger record
    trigger = JackpotTrigger(
        id=uuid.uuid4(),
        pool_id=data.pool_id,
        table_id=table_id,
        winner_id=data.winner_id,
        hand_description=data.hand_description,
        payout_amount=data.payout_amount,
        pool_balance_after=pool_balance_after,
        triggered_by=operated_by,
    )
    db.add(trigger)

    await db.commit()
    await db.refresh(trigger)
    return trigger


async def get_pool_triggers(
    db: AsyncSession, pool_id: uuid.UUID
) -> list[JackpotTrigger]:
    result = await db.execute(
        select(JackpotTrigger)
        .where(JackpotTrigger.pool_id == pool_id)
        .order_by(JackpotTrigger.created_at)
    )
    return list(result.scalars().all())
