"""Reports module tests — daily aggregates + per-table breakdown."""

import uuid

import pytest
from httpx import AsyncClient

from app.users.models import User


# ---------------------------------------------------------------------------
# Helper: create a table, open it, do a buy-in and cash-out for one player
# ---------------------------------------------------------------------------


async def _create_open_table(async_client: AsyncClient, headers: dict, name: str = "Report Table") -> str:
    resp = await async_client.post(
        "/api/tables",
        json={
            "name": name,
            "blind_level": "1/2",
            "rake_interval_minutes": 30,
            "rake_amount": 500,
            "jackpot_per_hand": 0,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    table_id = resp.json()["id"]

    resp2 = await async_client.patch(
        f"/api/tables/{table_id}/status",
        json={"status": "OPEN"},
        headers=headers,
    )
    assert resp2.status_code == 200
    return table_id


async def _do_buy_in(
    async_client: AsyncClient, headers: dict, table_id: str, player_id: str, amount: int
) -> None:
    resp = await async_client.post(
        f"/api/tables/{table_id}/buy-in",
        json={"player_id": player_id, "amount": amount},
        headers=headers,
    )
    assert resp.status_code == 201


async def _do_cash_out(
    async_client: AsyncClient, headers: dict, table_id: str, player_id: str, chip_count: int
) -> None:
    # Move to SETTLING first
    await async_client.patch(
        f"/api/tables/{table_id}/status",
        json={"status": "SETTLING"},
        headers=headers,
    )
    resp = await async_client.post(
        f"/api/tables/{table_id}/cash-out",
        json={"player_id": player_id, "chip_count": chip_count},
        headers=headers,
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Daily report tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_daily_report_default_date_returns_200(
    async_client: AsyncClient,
    admin_headers: dict,
):
    """Admin request with no data → 200, all zero aggregates."""
    resp = await async_client.get("/api/reports/daily", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "report_date" in data
    assert data["tables_opened"] == 0
    assert data["tables_closed"] == 0
    assert data["total_buy_ins_count"] == 0
    assert data["total_buy_ins_sum"] == 0
    assert data["total_cash_outs_count"] == 0
    assert data["total_cash_outs_sum"] == 0
    assert data["total_rake_collected"] == 0
    assert data["total_jackpot_contributions"] == 0
    assert data["total_insurance_bought"] == 0
    assert data["total_players_active"] == 0


@pytest.mark.asyncio
async def test_daily_report_with_data(
    async_client: AsyncClient,
    admin_headers: dict,
    banker_headers: dict,
    player_user: User,
):
    """Buy-in 1000 + cash-out 800 → daily counts/sums are correct."""
    table_id = await _create_open_table(async_client, banker_headers)
    await _do_buy_in(async_client, banker_headers, table_id, str(player_user.id), 1000)
    await _do_cash_out(async_client, banker_headers, table_id, str(player_user.id), 800)

    resp = await async_client.get("/api/reports/daily", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_buy_ins_count"] == 1
    assert data["total_buy_ins_sum"] == 1000
    assert data["total_cash_outs_count"] == 1
    assert data["total_cash_outs_sum"] == 800
    assert data["total_players_active"] == 1


@pytest.mark.asyncio
async def test_daily_report_banker_sees_only_own_tables(
    async_client: AsyncClient,
    banker_headers: dict,
    banker_b_headers: dict,
    player_user: User,
):
    """Banker A and Banker B each have a table; each only sees their own data."""
    # Banker A table: buy-in 1000
    table_a_id = await _create_open_table(async_client, banker_headers, name="Table A")
    await _do_buy_in(async_client, banker_headers, table_a_id, str(player_user.id), 1000)

    # Banker B table: buy-in 2000
    table_b_id = await _create_open_table(async_client, banker_b_headers, name="Table B")
    await _do_buy_in(async_client, banker_b_headers, table_b_id, str(player_user.id), 2000)

    # Banker A's view
    resp_a = await async_client.get("/api/reports/daily", headers=banker_headers)
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    assert data_a["total_buy_ins_count"] == 1
    assert data_a["total_buy_ins_sum"] == 1000

    # Banker B's view
    resp_b = await async_client.get("/api/reports/daily", headers=banker_b_headers)
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    assert data_b["total_buy_ins_count"] == 1
    assert data_b["total_buy_ins_sum"] == 2000


@pytest.mark.asyncio
async def test_daily_report_with_specific_date(
    async_client: AsyncClient,
    admin_headers: dict,
):
    """?date=2020-01-01 → empty/zero since no data for that date."""
    resp = await async_client.get("/api/reports/daily?date=2020-01-01", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["report_date"] == "2020-01-01"
    assert data["total_buy_ins_count"] == 0
    assert data["total_players_active"] == 0


@pytest.mark.asyncio
async def test_daily_report_player_role_forbidden(
    async_client: AsyncClient,
    player_headers: dict,
):
    """Player role → 403."""
    resp = await async_client.get("/api/reports/daily", headers=player_headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Table report tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_table_report_success(
    async_client: AsyncClient,
    admin_headers: dict,
    banker_headers: dict,
    player_user: User,
):
    """Buy-in 1000, cash-out 800, rake 500 → net_result = 800 - 1000 - 500 = -700."""
    table_id = await _create_open_table(async_client, banker_headers)
    await _do_buy_in(async_client, banker_headers, table_id, str(player_user.id), 1000)
    await _do_cash_out(async_client, banker_headers, table_id, str(player_user.id), 800)

    resp = await async_client.get(f"/api/reports/table/{table_id}", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["table_id"] == table_id
    assert "table_name" in data
    assert "blind_level" in data
    assert "status" in data
    assert len(data["players"]) == 1

    player_row = data["players"][0]
    assert player_row["player_id"] == str(player_user.id)
    assert player_row["total_buy_in"] == 1000
    assert player_row["total_cash_out"] == 800
    # rake_amount=500, any non-zero seated duration charges 1 interval = 500
    assert player_row["rake_paid"] == 500
    assert player_row["net_result"] == 800 - 1000 - 500  # -700

    totals = data["totals"]
    assert totals["total_buy_in"] == 1000
    assert totals["total_cash_out"] == 800
    assert totals["total_rake"] == 500
    assert totals["net_result"] == -700


@pytest.mark.asyncio
async def test_table_report_player_display_name_from_join(
    async_client: AsyncClient,
    admin_headers: dict,
    banker_headers: dict,
    player_user: User,
):
    """Player display_name is correctly returned in the report (verifies the JOIN query fetches names).

    This test exists to ensure the N+1 fix (joining User in the aggregate query rather than
    issuing a separate SELECT per player) does not break display_name resolution.
    """
    table_id = await _create_open_table(async_client, banker_headers)
    await _do_buy_in(async_client, banker_headers, table_id, str(player_user.id), 500)

    resp = await async_client.get(f"/api/reports/table/{table_id}", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["players"]) == 1
    player_row = data["players"][0]
    assert player_row["player_id"] == str(player_user.id)
    # display_name must match the player's actual display_name, not "Unknown"
    assert player_row["display_name"] == player_user.display_name
    assert player_row["display_name"] != "Unknown"


@pytest.mark.asyncio
async def test_table_report_not_found(
    async_client: AsyncClient,
    admin_headers: dict,
):
    """Non-existent table UUID → 404."""
    fake_id = str(uuid.uuid4())
    resp = await async_client.get(f"/api/reports/table/{fake_id}", headers=admin_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_table_report_banker_forbidden_other_table(
    async_client: AsyncClient,
    banker_headers: dict,
    banker_b_headers: dict,
):
    """Banker B cannot see Banker A's table report → 403."""
    table_id = await _create_open_table(async_client, banker_headers, name="Banker A Table")
    resp = await async_client.get(f"/api/reports/table/{table_id}", headers=banker_b_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_table_report_player_forbidden(
    async_client: AsyncClient,
    player_headers: dict,
):
    """Player role cannot access table report → 403."""
    fake_id = str(uuid.uuid4())
    resp = await async_client.get(f"/api/reports/table/{fake_id}", headers=player_headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Schema contract tests — monetary fields must be non-negative
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_daily_report_monetary_fields_are_non_negative(
    async_client: AsyncClient,
    admin_headers: dict,
    banker_headers: dict,
    player_user: User,
):
    """All monetary fields in DailyReportResponse must be >= 0.

    This documents the ge=0 schema contract: even after buy-in and cash-out
    activity, the aggregated amounts reported to the client must never be
    negative (the service negates stored negative amounts before returning).
    """
    table_id = await _create_open_table(async_client, banker_headers)
    await _do_buy_in(async_client, banker_headers, table_id, str(player_user.id), 500)
    await _do_cash_out(async_client, banker_headers, table_id, str(player_user.id), 400)

    resp = await async_client.get("/api/reports/daily", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    monetary_fields = [
        "total_buy_ins_sum",
        "total_cash_outs_sum",
        "total_rake_collected",
        "total_jackpot_contributions",
        "total_insurance_bought",
    ]
    for field in monetary_fields:
        assert data[field] >= 0, f"Field {field!r} was negative: {data[field]}"
