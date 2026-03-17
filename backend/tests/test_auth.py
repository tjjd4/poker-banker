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


# ---------------------------------------------------------------------------
# 1.1 — Input Length Validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_username_too_long(async_client: AsyncClient):
    """username > 50 chars -> 422"""
    response = await async_client.post(
        "/api/auth/login",
        json={"username": "a" * 51, "password": "somepassword"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_username_exactly_50_chars(async_client: AsyncClient, admin_user):
    """username == 50 chars is accepted (wrong creds -> 401, not 422)"""
    response = await async_client.post(
        "/api/auth/login",
        json={"username": "a" * 50, "password": "somepassword"},
    )
    # 401 (not found) is correct — validation passed, auth failed
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_password_too_long(async_client: AsyncClient):
    """password > 128 chars -> 422"""
    response = await async_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "p" * 129},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_password_exactly_128_chars(async_client: AsyncClient):
    """password == 128 chars passes validation (non-existent user -> 401, not 422)"""
    response = await async_client.post(
        "/api/auth/login",
        json={"username": "nonexistent_user_xyz", "password": "p" * 128},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 1.2 — CORS Middleware
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cors_preflight_allowed_origin(async_client: AsyncClient):
    """OPTIONS from allowed origin -> Access-Control-Allow-Origin header present"""
    response = await async_client.options(
        "/api/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" in response.headers


@pytest.mark.asyncio
async def test_cors_preflight_unknown_origin(async_client: AsyncClient):
    """OPTIONS from unknown origin -> no Access-Control-Allow-Origin header"""
    response = await async_client.options(
        "/api/auth/login",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in response.headers


# ---------------------------------------------------------------------------
# 1.3 — Rate Limiting on Auth Endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_rate_limit(async_client: AsyncClient, admin_user):
    """6th login attempt within a minute -> 429"""
    payload = {"username": "admin", "password": "wrongpassword"}
    for _ in range(5):
        await async_client.post("/api/auth/login", json=payload)
    response = await async_client.post("/api/auth/login", json=payload)
    assert response.status_code == 429


# ---------------------------------------------------------------------------
# 1.4 — Password Change Endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_change_password_success(async_client: AsyncClient, admin_token: str):
    """Authenticated user changes password successfully -> 200"""
    response = await async_client.post(
        "/api/auth/change-password",
        json={"current_password": "admin123", "new_password": "newpassword1"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current(async_client: AsyncClient, admin_token: str):
    """Wrong current_password -> 400"""
    response = await async_client.post(
        "/api/auth/change-password",
        json={"current_password": "wrongpassword", "new_password": "newpassword1"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_change_password_new_too_short(async_client: AsyncClient, admin_token: str):
    """new_password < 8 chars -> 422"""
    response = await async_client.post(
        "/api/auth/change-password",
        json={"current_password": "admin123", "new_password": "short"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_change_password_unauthenticated(async_client: AsyncClient):
    """No token -> 401"""
    response = await async_client.post(
        "/api/auth/change-password",
        json={"current_password": "admin123", "new_password": "newpassword1"},
    )
    assert response.status_code == 401
