import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.insurance.calculator import calculate_outs_and_odds, validate_card_set
from app.insurance.models import InsuranceEvent
from app.insurance.schemas import (
    InsuranceConfirmRequest,
    InsuranceCreateRequest,
    InsuranceResolveRequest,
)
from app.tables.models import PlayerSeat, Table
from app.transactions.models import Transaction
from app.transactions.service import _lock_table


async def _check_player_seated(
    db: AsyncSession, table_id: uuid.UUID, player_id: uuid.UUID, label: str
) -> None:
    """Raise 400 if player is not actively seated at the table."""
    result = await db.execute(
        select(PlayerSeat).where(
            PlayerSeat.table_id == table_id,
            PlayerSeat.player_id == player_id,
            PlayerSeat.is_active == True,  # noqa: E712
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} is not seated at this table",
        )


async def _get_balance_after(
    db: AsyncSession, table_id: uuid.UUID, player_id: uuid.UUID
) -> int:
    """Get current balance (sum of all transaction amounts) for a player at a table."""
    result = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.table_id == table_id,
            Transaction.player_id == player_id,
        )
    )
    return result.scalar()


async def create_insurance_event(
    db: AsyncSession,
    table_id: uuid.UUID,
    data: InsuranceCreateRequest,
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
            detail="Table is not open",
        )

    # 2. Buyer must be seated
    await _check_player_seated(db, table_id, data.buyer_id, "Buyer")

    # 3. Opponent must be seated
    await _check_player_seated(db, table_id, data.opponent_id, "Opponent")

    # 4. Validate cards
    errors = validate_card_set(data.buyer_hand, data.opponent_hand, data.community_cards)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(errors),
        )

    # 5. Calculate outs and odds
    calc = calculate_outs_and_odds(
        data.buyer_hand, data.opponent_hand, data.community_cards
    )

    # 6. Create InsuranceEvent
    event = InsuranceEvent(
        id=uuid.uuid4(),
        table_id=table_id,
        buyer_id=data.buyer_id,
        buyer_hand=data.buyer_hand,
        opponent_hand=data.opponent_hand,
        community_cards=data.community_cards,
        outs=calc["outs"],
        win_probability=calc["win_probability"],
        odds=calc["odds"],
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    # 7. Return dict with model fields + total_combinations
    return {
        "id": event.id,
        "table_id": event.table_id,
        "buyer_id": event.buyer_id,
        "buyer_hand": event.buyer_hand,
        "opponent_hand": event.opponent_hand,
        "community_cards": event.community_cards,
        "outs": event.outs,
        "total_combinations": calc["total_combinations"],
        "win_probability": event.win_probability,
        "odds": event.odds,
        "created_at": event.created_at,
    }


async def confirm_insurance(
    db: AsyncSession,
    table_id: uuid.UUID,
    insurance_id: uuid.UUID,
    data: InsuranceConfirmRequest,
    created_by: uuid.UUID,
) -> InsuranceEvent:
    # 1. Get event
    event = await db.get(InsuranceEvent, insurance_id)
    if event is None or event.table_id != table_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insurance event not found",
        )

    # 2. Check not already confirmed
    if event.insured_amount != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insurance already confirmed",
        )

    # 3. Update event
    event.insured_amount = data.insured_amount
    event.seller_id = data.seller_id

    # 4. Create INSURANCE_BUY Transaction
    current_balance = await _get_balance_after(db, table_id, event.buyer_id)
    balance_after = current_balance + (-data.insured_amount)

    txn = Transaction(
        id=uuid.uuid4(),
        table_id=table_id,
        player_id=event.buyer_id,
        type="INSURANCE_BUY",
        amount=-data.insured_amount,
        balance_after=balance_after,
        note=f"Insurance buy: event {insurance_id}",
        created_by=created_by,
    )
    db.add(txn)

    await db.commit()
    await db.refresh(event)
    return event


async def resolve_insurance(
    db: AsyncSession,
    table_id: uuid.UUID,
    insurance_id: uuid.UUID,
    data: InsuranceResolveRequest,
    created_by: uuid.UUID,
) -> InsuranceEvent:
    # 1. Get event
    event = await db.get(InsuranceEvent, insurance_id)
    if event is None or event.table_id != table_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insurance event not found",
        )

    # 2. Must be confirmed
    if event.insured_amount == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insurance not yet confirmed",
        )

    # 3. Must not be already resolved
    if event.is_hit is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insurance already resolved",
        )

    # 4. Validate final_community_cards prefix matches original
    original = event.community_cards
    final = data.final_community_cards
    if final[: len(original)] != original:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Final community cards must start with the original community cards",
        )

    # 5. Update is_hit
    event.is_hit = data.is_hit

    # 6. Calculate payout
    if data.is_hit:
        payout_amount = int(event.insured_amount * event.odds)
        event.payout_amount = payout_amount

        # Create INSURANCE_PAYOUT Transaction
        current_balance = await _get_balance_after(db, table_id, event.buyer_id)
        balance_after = current_balance + payout_amount

        txn = Transaction(
            id=uuid.uuid4(),
            table_id=table_id,
            player_id=event.buyer_id,
            type="INSURANCE_PAYOUT",
            amount=payout_amount,
            balance_after=balance_after,
            note=f"Insurance payout: event {insurance_id}",
            created_by=created_by,
        )
        db.add(txn)
    else:
        event.payout_amount = 0

    await db.commit()
    await db.refresh(event)
    return event


async def get_table_insurance_events(
    db: AsyncSession, table_id: uuid.UUID
) -> list[InsuranceEvent]:
    result = await db.execute(
        select(InsuranceEvent)
        .where(InsuranceEvent.table_id == table_id)
        .order_by(InsuranceEvent.created_at)
    )
    return list(result.scalars().all())
