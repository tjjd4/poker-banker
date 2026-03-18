import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Daily report
# ---------------------------------------------------------------------------


class DailyReportResponse(BaseModel):
    report_date: datetime.date
    tables_opened: int = Field(ge=0)
    tables_closed: int = Field(ge=0)
    total_buy_ins_count: int = Field(ge=0)
    total_buy_ins_sum: int = Field(ge=0)
    total_cash_outs_count: int = Field(ge=0)
    total_cash_outs_sum: int = Field(ge=0)
    total_rake_collected: int = Field(ge=0)
    total_jackpot_contributions: int = Field(ge=0)
    total_insurance_bought: int = Field(ge=0)
    total_players_active: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Table report
# ---------------------------------------------------------------------------


class PlayerSummary(BaseModel):
    player_id: UUID
    display_name: str
    total_buy_in: int
    total_cash_out: int
    rake_paid: int
    net_result: int  # cash_out - buy_in - rake


class TableTotals(BaseModel):
    total_buy_in: int
    total_cash_out: int
    total_rake: int
    net_result: int


class TableReportResponse(BaseModel):
    table_id: UUID
    table_name: str
    blind_level: str
    status: str
    players: list[PlayerSummary]
    totals: TableTotals
