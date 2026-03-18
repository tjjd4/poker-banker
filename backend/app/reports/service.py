import datetime
import uuid
from typing import Optional

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ForbiddenError, NotFoundError
from app.reports.schemas import (
    DailyReportResponse,
    PlayerSummary,
    TableReportResponse,
    TableTotals,
)
from app.tables.models import Table
from app.transactions.models import Transaction
from app.users.models import User


async def get_daily_report(
    db: AsyncSession,
    target_date: datetime.date,
    banker_id: Optional[uuid.UUID] = None,
) -> DailyReportResponse:
    date_str = target_date.isoformat()

    # Single aggregate query across all matching transactions
    tx_stmt = (
        select(
            func.sum(case((Transaction.type == "BUY_IN", Transaction.amount), else_=0)).label("buy_ins_sum"),
            func.count(case((Transaction.type == "BUY_IN", 1))).label("buy_ins_count"),
            func.sum(case((Transaction.type == "CASH_OUT", Transaction.amount), else_=0)).label("cash_outs_sum"),
            func.count(case((Transaction.type == "CASH_OUT", 1))).label("cash_outs_count"),
            func.sum(case((Transaction.type == "RAKE", Transaction.amount), else_=0)).label("rake_sum"),
            func.sum(case((Transaction.type == "JACKPOT_CONTRIBUTION", Transaction.amount), else_=0)).label("jackpot_sum"),
            func.sum(case((Transaction.type == "INSURANCE_BUY", Transaction.amount), else_=0)).label("insurance_sum"),
        )
        .join(Table, Transaction.table_id == Table.id)
        .where(func.date(Transaction.created_at) == date_str)
    )
    if banker_id is not None:
        tx_stmt = tx_stmt.where(Table.banker_id == banker_id)

    tx_row = (await db.execute(tx_stmt)).one()

    # Distinct active players (those who had BUY_IN or CASH_OUT)
    player_stmt = (
        select(func.count(func.distinct(Transaction.player_id)))
        .join(Table, Transaction.table_id == Table.id)
        .where(func.date(Transaction.created_at) == date_str)
        .where(Transaction.type.in_(["BUY_IN", "CASH_OUT"]))
    )
    if banker_id is not None:
        player_stmt = player_stmt.where(Table.banker_id == banker_id)
    players_active = (await db.execute(player_stmt)).scalar() or 0

    # Tables opened / closed on this date
    opened_stmt = (
        select(func.count())
        .select_from(Table)
        .where(func.date(Table.opened_at) == date_str)
    )
    closed_stmt = (
        select(func.count())
        .select_from(Table)
        .where(func.date(Table.closed_at) == date_str)
    )
    if banker_id is not None:
        opened_stmt = opened_stmt.where(Table.banker_id == banker_id)
        closed_stmt = closed_stmt.where(Table.banker_id == banker_id)

    tables_opened = (await db.execute(opened_stmt)).scalar() or 0
    tables_closed = (await db.execute(closed_stmt)).scalar() or 0

    # CASH_OUT, RAKE, JACKPOT_CONTRIBUTION, INSURANCE_BUY are stored as
    # negative amounts (money leaving the player). Negate for reporting.
    return DailyReportResponse(
        report_date=target_date,
        tables_opened=tables_opened,
        tables_closed=tables_closed,
        total_buy_ins_count=tx_row.buy_ins_count or 0,
        total_buy_ins_sum=tx_row.buy_ins_sum or 0,
        total_cash_outs_count=tx_row.cash_outs_count or 0,
        total_cash_outs_sum=-(tx_row.cash_outs_sum or 0),
        total_rake_collected=-(tx_row.rake_sum or 0),
        total_jackpot_contributions=-(tx_row.jackpot_sum or 0),
        total_insurance_bought=-(tx_row.insurance_sum or 0),
        total_players_active=players_active,
    )


async def get_table_report(
    db: AsyncSession,
    table_id: uuid.UUID,
    current_user: User,
) -> TableReportResponse:
    table = await db.get(Table, table_id)
    if table is None:
        raise NotFoundError("Table not found")
    if current_user.role == "banker" and table.banker_id != current_user.id:
        raise ForbiddenError("You do not have access to this table's report")

    # Per-player aggregates with User JOIN — single query, no N+1
    agg_stmt = (
        select(
            Transaction.player_id,
            User.display_name,
            func.sum(case((Transaction.type == "BUY_IN", Transaction.amount), else_=0)).label("total_buy_in"),
            func.sum(case((Transaction.type == "CASH_OUT", Transaction.amount), else_=0)).label("total_cash_out"),
            func.sum(case((Transaction.type == "RAKE", Transaction.amount), else_=0)).label("rake_paid"),
        )
        .join(User, Transaction.player_id == User.id)
        .where(Transaction.table_id == table_id)
        .where(Transaction.type.in_(["BUY_IN", "CASH_OUT", "RAKE"]))
        .group_by(Transaction.player_id, User.display_name)
    )
    rows = (await db.execute(agg_stmt)).all()

    players: list[PlayerSummary] = []
    for row in rows:
        buy_in = row.total_buy_in or 0
        # CASH_OUT and RAKE stored as negative; negate for reporting
        cash_out = -(row.total_cash_out or 0)
        rake = -(row.rake_paid or 0)
        players.append(
            PlayerSummary(
                player_id=row.player_id,
                display_name=row.display_name,
                total_buy_in=buy_in,
                total_cash_out=cash_out,
                rake_paid=rake,
                net_result=cash_out - buy_in - rake,
            )
        )

    totals = TableTotals(
        total_buy_in=sum(p.total_buy_in for p in players),
        total_cash_out=sum(p.total_cash_out for p in players),
        total_rake=sum(p.rake_paid for p in players),
        net_result=sum(p.net_result for p in players),
    )

    return TableReportResponse(
        table_id=table.id,
        table_name=table.name,
        blind_level=table.blind_level,
        status=table.status,
        players=players,
        totals=totals,
    )
