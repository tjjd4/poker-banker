"""
Phase 4 — Pagination tests for list endpoints.

Endpoints under test:
  GET /api/users                            (admin only)
  GET /api/tables                           (admin or banker)
  GET /api/jackpot-pools                    (admin or banker)
  GET /api/tables/{table_id}/transactions   (admin or banker, table-scoped)

Each response must expose: total (int), offset (int), limit (int) alongside the
existing list field so that backwards-compatible clients continue to work.
"""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Users list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_users_list_default_pagination(
    async_client: AsyncClient, admin_headers: dict
):
    """GET /api/users with no params returns total, offset=0, limit=50 metadata."""
    response = await async_client.get("/api/users", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "users" in data
    assert "total" in data
    assert data["offset"] == 0
    assert data["limit"] == 50
    assert isinstance(data["total"], int)


@pytest.mark.asyncio
async def test_users_list_with_limit(async_client: AsyncClient, admin_headers: dict):
    """GET /api/users?limit=1 returns at most 1 user in the list."""
    # Seed two extra users so there are at least 2 total
    for i in range(2):
        await async_client.post(
            "/api/users",
            json={
                "username": f"limituser{i}",
                "password": "secure123",
                "display_name": f"Limit User {i}",
                "role": "banker",
            },
            headers=admin_headers,
        )

    response = await async_client.get("/api/users?limit=1", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 1
    assert len(data["users"]) == 1
    assert data["total"] >= 2  # total reflects full count, not the page


@pytest.mark.asyncio
async def test_users_list_with_offset(async_client: AsyncClient, admin_headers: dict):
    """GET /api/users?offset=1&limit=2 skips first user and returns 2."""
    # Ensure at least 3 users exist (admin + 2 new)
    for i in range(2):
        await async_client.post(
            "/api/users",
            json={
                "username": f"offsetuser{i}",
                "password": "secure123",
                "display_name": f"Offset User {i}",
                "role": "banker",
            },
            headers=admin_headers,
        )

    all_resp = await async_client.get("/api/users", headers=admin_headers)
    total = all_resp.json()["total"]

    response = await async_client.get(
        "/api/users?offset=1&limit=2", headers=admin_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["offset"] == 1
    assert data["limit"] == 2
    assert data["total"] == total
    # Page size must not exceed limit, and must not exceed remaining items
    assert len(data["users"]) == min(2, total - 1)


@pytest.mark.asyncio
async def test_users_list_invalid_limit(
    async_client: AsyncClient, admin_headers: dict
):
    """GET /api/users?limit=0 -> 422 (limit must be >= 1)."""
    response = await async_client.get("/api/users?limit=0", headers=admin_headers)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Tables list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tables_list_default_pagination(
    async_client: AsyncClient, admin_headers: dict
):
    """GET /api/tables returns tables list with total, offset=0, limit=50."""
    response = await async_client.get("/api/tables", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "tables" in data
    assert "total" in data
    assert data["offset"] == 0
    assert data["limit"] == 50


# ---------------------------------------------------------------------------
# Jackpot pools list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_jackpot_pools_default_pagination(
    async_client: AsyncClient, admin_headers: dict
):
    """GET /api/jackpot-pools returns pools list with total, offset=0, limit=50."""
    response = await async_client.get("/api/jackpot-pools", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "pools" in data
    assert "total" in data
    assert data["offset"] == 0
    assert data["limit"] == 50


# ---------------------------------------------------------------------------
# Table transactions list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_table_transactions_pagination(
    async_client: AsyncClient,
    admin_headers: dict,
    banker_headers: dict,
    created_table: dict,
):
    """GET /api/tables/{id}/transactions returns transactions with total, offset, limit."""
    table_id = created_table["id"]
    response = await async_client.get(
        f"/api/tables/{table_id}/transactions", headers=banker_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "transactions" in data
    assert "total" in data
    assert data["offset"] == 0
    assert data["limit"] == 50
