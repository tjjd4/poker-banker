"""
Tests for domain exception hierarchy (Task 2.1).

These tests are written FIRST (RED phase) — they will fail until
backend/app/exceptions.py is created.
"""
import pytest


def test_import_poker_banker_error():
    """PokerBankerError must be importable from app.exceptions."""
    from app.exceptions import PokerBankerError
    assert issubclass(PokerBankerError, Exception)


def test_not_found_error_is_subclass():
    """NotFoundError must be a subclass of PokerBankerError."""
    from app.exceptions import NotFoundError, PokerBankerError
    assert issubclass(NotFoundError, PokerBankerError)


def test_forbidden_error_is_subclass():
    """ForbiddenError must be a subclass of PokerBankerError."""
    from app.exceptions import ForbiddenError, PokerBankerError
    assert issubclass(ForbiddenError, PokerBankerError)


def test_conflict_error_is_subclass():
    """ConflictError must be a subclass of PokerBankerError."""
    from app.exceptions import ConflictError, PokerBankerError
    assert issubclass(ConflictError, PokerBankerError)


def test_validation_error_is_subclass():
    """ValidationError must be a subclass of PokerBankerError."""
    from app.exceptions import ValidationError, PokerBankerError
    assert issubclass(ValidationError, PokerBankerError)


def test_can_raise_and_catch_not_found():
    """NotFoundError can be raised and caught as PokerBankerError."""
    from app.exceptions import NotFoundError, PokerBankerError
    with pytest.raises(PokerBankerError):
        raise NotFoundError("Table not found")


def test_can_raise_and_catch_forbidden():
    """ForbiddenError can be raised and caught as PokerBankerError."""
    from app.exceptions import ForbiddenError, PokerBankerError
    with pytest.raises(PokerBankerError):
        raise ForbiddenError("You don't own this table")


def test_can_raise_and_catch_conflict():
    """ConflictError can be raised and caught as PokerBankerError."""
    from app.exceptions import ConflictError, PokerBankerError
    with pytest.raises(PokerBankerError):
        raise ConflictError("Username already exists")


def test_can_raise_and_catch_validation_error():
    """ValidationError can be raised and caught as PokerBankerError."""
    from app.exceptions import ValidationError, PokerBankerError
    with pytest.raises(PokerBankerError):
        raise ValidationError("Invalid input")


def test_not_found_stores_message():
    """Exception message is accessible via str()."""
    from app.exceptions import NotFoundError
    err = NotFoundError("User not found")
    assert "User not found" in str(err)


def test_each_exception_is_distinct():
    """Domain exceptions are not interchangeable — catching NotFoundError does not catch ForbiddenError."""
    from app.exceptions import NotFoundError, ForbiddenError
    with pytest.raises(ForbiddenError):
        try:
            raise ForbiddenError("forbidden")
        except NotFoundError:
            pass  # should NOT catch it


def test_authentication_error_is_subclass():
    """AuthenticationError must be a subclass of PokerBankerError."""
    from app.exceptions import AuthenticationError, PokerBankerError
    assert issubclass(AuthenticationError, PokerBankerError)


def test_can_raise_and_catch_authentication_error():
    """AuthenticationError can be raised and caught as PokerBankerError."""
    from app.exceptions import AuthenticationError, PokerBankerError
    with pytest.raises(PokerBankerError):
        raise AuthenticationError("Invalid credentials")


def test_domain_exceptions_are_not_http_exceptions():
    """Domain exceptions must NOT inherit from fastapi.HTTPException."""
    from fastapi import HTTPException
    from app.exceptions import (
        PokerBankerError,
        NotFoundError,
        ForbiddenError,
        ConflictError,
        ValidationError,
        AuthenticationError,
    )
    for cls in (PokerBankerError, NotFoundError, ForbiddenError, ConflictError, ValidationError, AuthenticationError):
        assert not issubclass(cls, HTTPException), (
            f"{cls.__name__} should not inherit from HTTPException"
        )


# ---------------------------------------------------------------------------
# Integration tests — verify exception handlers map to correct HTTP status codes
# ---------------------------------------------------------------------------

import pytest
import pytest_asyncio


@pytest.mark.asyncio
async def test_not_found_error_maps_to_404(async_client, admin_headers):
    """NotFoundError raised by a service must produce an HTTP 404 response."""
    import uuid
    fake_id = uuid.uuid4()
    # PATCH /api/users/{user_id} calls update_user which raises NotFoundError for missing user
    resp = await async_client.patch(
        f"/api/users/{fake_id}",
        json={"display_name": "X"},
        headers=admin_headers,
    )
    assert resp.status_code == 404
    assert "detail" in resp.json()


@pytest.mark.asyncio
async def test_conflict_error_maps_to_409(async_client, admin_headers):
    """ConflictError raised by a service must produce an HTTP 409 response."""
    user_payload = {
        "username": "dupuser",
        "password": "password123",
        "display_name": "Dup User",
        "role": "banker",
    }
    # Create the user once
    resp1 = await async_client.post("/api/users", json=user_payload, headers=admin_headers)
    assert resp1.status_code == 201
    # Try to create again — ConflictError → 409
    resp2 = await async_client.post("/api/users", json=user_payload, headers=admin_headers)
    assert resp2.status_code == 409
    assert "detail" in resp2.json()


@pytest.mark.asyncio
async def test_validation_error_maps_to_400(async_client, admin_headers):
    """ValidationError raised by a service must produce an HTTP 400 response."""
    import uuid
    # Try invalid status transition (CREATED → SETTLING) — raises ValidationError
    resp_create = await async_client.post(
        "/api/tables",
        json={
            "name": "Err Table",
            "blind_level": "1/2",
            "rake_interval_minutes": 30,
            "rake_amount": 100,
            "jackpot_per_hand": 0,
        },
        headers=admin_headers,
    )
    assert resp_create.status_code == 201
    table_id = resp_create.json()["id"]

    # CREATED → SETTLING is invalid — service raises ValidationError
    resp = await async_client.patch(
        f"/api/tables/{table_id}/status",
        json={"status": "SETTLING"},
        headers=admin_headers,
    )
    assert resp.status_code == 400
    assert "detail" in resp.json()


@pytest.mark.asyncio
async def test_forbidden_error_maps_to_403(async_client, admin_headers, banker_headers, banker_b_headers):
    """ForbiddenError raised by a service must produce an HTTP 403 response."""
    # Banker A creates a table
    resp_create = await async_client.post(
        "/api/tables",
        json={
            "name": "Banker A Table",
            "blind_level": "1/2",
            "rake_interval_minutes": 30,
            "rake_amount": 100,
            "jackpot_per_hand": 0,
        },
        headers=banker_headers,
    )
    assert resp_create.status_code == 201
    table_id = resp_create.json()["id"]

    # Banker B tries to update status — ForbiddenError → 403
    resp = await async_client.patch(
        f"/api/tables/{table_id}/status",
        json={"status": "OPEN"},
        headers=banker_b_headers,
    )
    assert resp.status_code == 403
    assert "detail" in resp.json()


@pytest.mark.asyncio
async def test_detail_field_contains_message(async_client, admin_headers):
    """The error response must include the detail message from the exception."""
    import uuid
    fake_id = uuid.uuid4()
    # PATCH /api/users/{user_id} calls update_user which raises NotFoundError("User not found")
    resp = await async_client.patch(
        f"/api/users/{fake_id}",
        json={"display_name": "X"},
        headers=admin_headers,
    )
    assert resp.status_code == 404
    data = resp.json()
    assert data["detail"] == "User not found"
