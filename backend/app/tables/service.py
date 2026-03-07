import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.jackpot.models import JackpotPool
from app.tables.models import PlayerSeat, Table
from app.tables.schemas import TableCreate, TableStatusUpdate
from app.users.models import User

# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

VALID_TRANSITIONS = {
    ("CREATED", "OPEN"),
    ("OPEN", "SETTLING"),
    ("SETTLING", "CLOSED"),
}

ERROR_MESSAGES: dict[tuple[str, str], str] = {
    ("CREATED", "SETTLING"): "Cannot settle a table that hasn't been opened",
    ("CREATED", "CLOSED"): "Cannot close a table that hasn't been opened",
    ("OPEN", "CREATED"): "Cannot revert table status",
    ("SETTLING", "OPEN"): "Cannot revert table status",
    ("SETTLING", "CREATED"): "Cannot revert table status",
    ("CLOSED", "OPEN"): "Cannot revert table status. Use admin unlock to reopen for settling",
    ("CLOSED", "CREATED"): "Cannot revert table status",
    ("CLOSED", "SETTLING"): "Cannot revert table status",
}

# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------


async def create_table(
    db: AsyncSession, banker_id: uuid.UUID, data: TableCreate
) -> Table:
    # Jackpot pool validation
    if data.jackpot_per_hand > 0 and data.jackpot_pool_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must specify a jackpot pool when jackpot_per_hand > 0",
        )
    if data.jackpot_pool_id is not None:
        pool = await db.get(JackpotPool, data.jackpot_pool_id)
        if pool is None or pool.banker_id != banker_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Jackpot pool not found or not owned by you",
            )

    table = Table(
        id=uuid.uuid4(),
        name=data.name,
        blind_level=data.blind_level,
        rake_interval_minutes=data.rake_interval_minutes,
        rake_amount=data.rake_amount,
        jackpot_per_hand=data.jackpot_per_hand,
        jackpot_pool_id=data.jackpot_pool_id,
        status="CREATED",
        banker_id=banker_id,
    )
    db.add(table)
    await db.commit()
    await db.refresh(table)
    return table


async def list_tables(
    db: AsyncSession,
    banker_id: uuid.UUID | None,
    status_filter: str | None = None,
) -> list[Table]:
    stmt = select(Table)
    if banker_id is not None:
        stmt = stmt.where(Table.banker_id == banker_id)
    if status_filter is not None:
        stmt = stmt.where(Table.status == status_filter)
    stmt = stmt.order_by(Table.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_table(db: AsyncSession, table_id: uuid.UUID) -> Table | None:
    return await db.get(Table, table_id)


async def get_table_detail(db: AsyncSession, table_id: uuid.UUID) -> dict | None:
    table = await db.get(Table, table_id)
    if table is None:
        return None

    stmt = (
        select(
            PlayerSeat.id,
            PlayerSeat.player_id,
            User.display_name.label("player_display_name"),
            PlayerSeat.seated_at,
            PlayerSeat.left_at,
            PlayerSeat.is_active,
        )
        .join(User, PlayerSeat.player_id == User.id)
        .where(PlayerSeat.table_id == table_id)
        .order_by(PlayerSeat.seated_at)
    )
    result = await db.execute(stmt)
    players = [row._asdict() for row in result.all()]

    return {
        "id": table.id,
        "name": table.name,
        "blind_level": table.blind_level,
        "rake_interval_minutes": table.rake_interval_minutes,
        "rake_amount": table.rake_amount,
        "jackpot_per_hand": table.jackpot_per_hand,
        "jackpot_pool_id": table.jackpot_pool_id,
        "status": table.status,
        "banker_id": table.banker_id,
        "opened_at": table.opened_at,
        "closed_at": table.closed_at,
        "created_at": table.created_at,
        "updated_at": table.updated_at,
        "players": players,
    }


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


async def update_table_status(
    db: AsyncSession,
    table_id: uuid.UUID,
    new_status: str,
    banker_id: uuid.UUID | None = None,
) -> Table:
    table = await db.get(Table, table_id)
    if table is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Table not found"
        )

    # Ownership check (skip for admin, i.e. banker_id=None)
    if banker_id is not None and table.banker_id != banker_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't own this table",
        )

    current = table.status

    # Same status
    if current == new_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Table is already in {new_status} status",
        )

    # Invalid transition
    if (current, new_status) not in VALID_TRANSITIONS:
        msg = ERROR_MESSAGES.get(
            (current, new_status),
            f"Invalid status transition from {current} to {new_status}",
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    # Precondition: SETTLING → CLOSED requires all players to have left
    if current == "SETTLING" and new_status == "CLOSED":
        result = await db.execute(
            select(func.count())
            .select_from(PlayerSeat)
            .where(PlayerSeat.table_id == table_id, PlayerSeat.is_active == True)  # noqa: E712
        )
        active_count = result.scalar()
        if active_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot close table: there are still active players seated",
            )

    # Side effects
    if new_status == "OPEN":
        table.opened_at = datetime.now(timezone.utc)
    elif new_status == "CLOSED":
        table.closed_at = datetime.now(timezone.utc)

    table.status = new_status
    await db.commit()
    await db.refresh(table)
    return table


async def unlock_table(
    db: AsyncSession,
    table_id: uuid.UUID,
    reason: str,
    admin_id: uuid.UUID,
) -> Table:
    table = await db.get(Table, table_id)
    if table is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Table not found"
        )

    if table.status != "CLOSED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can only unlock a CLOSED table, current status is {table.status}",
        )

    table.status = "SETTLING"
    table.closed_at = None
    await db.commit()
    await db.refresh(table)
    return table
