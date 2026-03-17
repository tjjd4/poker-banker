import pytest


# ---------------------------------------------------------------------------
# 1.6 — Production Secret Validation
# ---------------------------------------------------------------------------


def test_default_secret_with_sqlite_is_allowed():
    """Default SECRET_KEY + SQLite URL (test mode) must NOT raise."""
    from app.config import Settings

    s = Settings(
        SECRET_KEY="dev-secret-key-change-in-production",
        DATABASE_URL="sqlite+aiosqlite:///./test.db",
    )
    assert s.SECRET_KEY == "dev-secret-key-change-in-production"


def test_default_secret_with_postgres_raises():
    """Default SECRET_KEY + PostgreSQL DATABASE_URL (production) must raise ValueError."""
    from app.config import Settings

    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(
            SECRET_KEY="dev-secret-key-change-in-production",
            DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/poker_banker",
        )


def test_custom_secret_with_postgres_is_allowed():
    """Custom SECRET_KEY + PostgreSQL URL is valid."""
    from app.config import Settings

    s = Settings(
        SECRET_KEY="a-strong-production-secret-key-that-is-different",
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/poker_banker",
    )
    assert s.SECRET_KEY == "a-strong-production-secret-key-that-is-different"


def test_default_secret_with_memory_sqlite_is_allowed():
    """Default SECRET_KEY + in-memory SQLite must NOT raise."""
    from app.config import Settings

    s = Settings(
        SECRET_KEY="dev-secret-key-change-in-production",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
    )
    assert s.DATABASE_URL == "sqlite+aiosqlite:///:memory:"
