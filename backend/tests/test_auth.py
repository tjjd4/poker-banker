import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient, admin_user):
    """正確帳密登入 -> 200 + access_token + refresh_token"""
    response = await async_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(async_client: AsyncClient, admin_user):
    """錯誤密碼 -> 401"""
    response = await async_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrongpassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(async_client: AsyncClient):
    """不存在的 username -> 401"""
    response = await async_client.post(
        "/api/auth/login",
        json={"username": "nouser", "password": "whatever"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user(async_client: AsyncClient, inactive_user):
    """is_active=False 的帳號 -> 401"""
    response = await async_client.post(
        "/api/auth/login",
        json={"username": "inactive", "password": "password123"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_success(async_client: AsyncClient, admin_user):
    """合法 refresh_token -> 200 + 新的 token pair"""
    login_resp = await async_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    response = await async_client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_refresh_token_invalid(async_client: AsyncClient):
    """亂碼 refresh_token -> 401"""
    response = await async_client.post(
        "/api/auth/refresh",
        json={"refresh_token": "not.a.valid.token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_using_access_token(async_client: AsyncClient, admin_user):
    """用 access_token 當 refresh_token -> 401（type 不符）"""
    login_resp = await async_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    access_token = login_resp.json()["access_token"]

    response = await async_client.post(
        "/api/auth/refresh",
        json={"refresh_token": access_token},
    )
    assert response.status_code == 401
