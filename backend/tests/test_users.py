import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_user_as_admin(async_client: AsyncClient, admin_headers: dict):
    """Admin 建立 banker -> 201 + UserResponse（不含 password_hash）"""
    response = await async_client.post(
        "/api/users",
        json={
            "username": "newbanker",
            "password": "secure123",
            "display_name": "New Banker",
            "role": "banker",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newbanker"
    assert data["display_name"] == "New Banker"
    assert data["role"] == "banker"
    assert data["is_active"] is True
    assert "id" in data
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_create_user_duplicate_username(async_client: AsyncClient, admin_headers: dict):
    """重複 username -> 409"""
    payload = {
        "username": "dupuser",
        "password": "secure123",
        "display_name": "Dup User",
        "role": "banker",
    }
    resp1 = await async_client.post("/api/users", json=payload, headers=admin_headers)
    assert resp1.status_code == 201

    resp2 = await async_client.post("/api/users", json=payload, headers=admin_headers)
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_create_user_as_banker(async_client: AsyncClient, banker_headers: dict):
    """Banker 嘗試建立帳號 -> 403"""
    response = await async_client.post(
        "/api/users",
        json={
            "username": "another",
            "password": "secure123",
            "display_name": "Another",
            "role": "banker",
        },
        headers=banker_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_users_as_admin(async_client: AsyncClient, admin_headers: dict):
    """Admin 列出所有使用者 -> 200 + users list + total"""
    response = await async_client.get("/api/users", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "users" in data
    assert "total" in data
    assert isinstance(data["users"], list)
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_list_users_as_banker(async_client: AsyncClient, banker_headers: dict):
    """Banker 嘗試列出使用者 -> 403"""
    response = await async_client.get("/api/users", headers=banker_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_user_as_admin(async_client: AsyncClient, admin_headers: dict):
    """Admin 修改 user display_name -> 200 + 更新後資料"""
    create_resp = await async_client.post(
        "/api/users",
        json={
            "username": "toupdate",
            "password": "secure123",
            "display_name": "Before Update",
            "role": "banker",
        },
        headers=admin_headers,
    )
    assert create_resp.status_code == 201
    user_id = create_resp.json()["id"]

    response = await async_client.patch(
        f"/api/users/{user_id}",
        json={"display_name": "After Update"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "After Update"
    assert "password_hash" not in response.json()


@pytest.mark.asyncio
async def test_update_user_not_found(async_client: AsyncClient, admin_headers: dict):
    """修改不存在的 user_id -> 404"""
    fake_id = str(uuid.uuid4())
    response = await async_client.patch(
        f"/api/users/{fake_id}",
        json={"display_name": "Ghost"},
        headers=admin_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_access_without_token(async_client: AsyncClient):
    """不帶 token 打需認證端點 -> 401"""
    response = await async_client.get("/api/users")
    assert response.status_code == 401
