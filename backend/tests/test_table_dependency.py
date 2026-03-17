"""
Tests for the shared table ownership dependency (Task 2.2).

Tests are written first (RED phase) — they verify that:
1. get_owned_table can be imported from app.tables.dependencies
2. Admins can access any table (regardless of banker_id)
3. Bankers can only access tables they own
4. Accessing a non-existent table returns 404
5. Accessing another banker's table returns 403
"""
import uuid
import pytest


# ---------------------------------------------------------------------------
# Unit tests — dependency module structure
# ---------------------------------------------------------------------------


def test_get_owned_table_is_importable():
    """get_owned_table must be importable from app.tables.dependencies."""
    from app.tables.dependencies import get_owned_table
    import inspect
    assert callable(get_owned_table)
    assert inspect.iscoroutinefunction(get_owned_table)


def test_dependencies_module_exists():
    """app.tables.dependencies module must exist."""
    import importlib
    mod = importlib.import_module("app.tables.dependencies")
    assert mod is not None


# ---------------------------------------------------------------------------
# Integration tests — verify ownership enforcement via API endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_banker_cannot_access_another_bankers_table_players(
    async_client, banker_headers, banker_b_headers, created_table
):
    """Banker B must receive 403 when accessing Banker A's table players."""
    table_id = created_table["id"]
    resp = await async_client.get(
        f"/api/tables/{table_id}/players",
        headers=banker_b_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_access_any_table_players(
    async_client, admin_headers, created_table
):
    """Admin must be able to access any banker's table players."""
    table_id = created_table["id"]
    resp = await async_client.get(
        f"/api/tables/{table_id}/players",
        headers=admin_headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_banker_can_access_own_table_players(
    async_client, banker_headers, created_table
):
    """Banker must be able to access their own table's players."""
    table_id = created_table["id"]
    resp = await async_client.get(
        f"/api/tables/{table_id}/players",
        headers=banker_headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_nonexistent_table_returns_404_for_buy_in(
    async_client, admin_headers
):
    """Accessing a non-existent table via buy-in returns 404."""
    fake_id = uuid.uuid4()
    resp = await async_client.post(
        f"/api/tables/{fake_id}/buy-in",
        json={"player_id": str(uuid.uuid4()), "amount": 1000},
        headers=admin_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_banker_cannot_buy_in_to_another_bankers_table(
    async_client, banker_headers, banker_b_headers, open_table, player_user
):
    """Banker B must receive 403 when buying into Banker A's table."""
    table_id = open_table["id"]
    resp = await async_client.post(
        f"/api/tables/{table_id}/buy-in",
        json={"player_id": str(player_user.id), "amount": 1000},
        headers=banker_b_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_banker_cannot_view_transactions_of_another_bankers_table(
    async_client, banker_headers, banker_b_headers, created_table
):
    """Banker B must receive 403 when viewing Banker A's table transactions."""
    table_id = created_table["id"]
    resp = await async_client.get(
        f"/api/tables/{table_id}/transactions",
        headers=banker_b_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_nonexistent_table_returns_404_for_players_endpoint(
    async_client, admin_headers
):
    """Accessing a non-existent table's players returns 404."""
    fake_id = uuid.uuid4()
    resp = await async_client.get(
        f"/api/tables/{fake_id}/players",
        headers=admin_headers,
    )
    assert resp.status_code == 404
