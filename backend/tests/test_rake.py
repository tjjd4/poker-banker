"""Pure function tests for rake calculation — no DB, no async."""

from datetime import datetime, timezone

from app.transactions.rake import calculate_rake


def _dt(minutes_offset: int) -> tuple[datetime, datetime]:
    """Return (seated_at, left_at) pair with the given duration in minutes."""
    base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return base, base.replace(minute=0, second=0) + __import__("datetime").timedelta(minutes=minutes_offset)


def test_rake_exact_one_period():
    seated = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    left = datetime(2025, 1, 1, 12, 30, 0, tzinfo=timezone.utc)
    assert calculate_rake(seated, left, 30, 100) == 100


def test_rake_partial_period_rounds_up():
    seated = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    left = datetime(2025, 1, 1, 12, 1, 0, tzinfo=timezone.utc)
    assert calculate_rake(seated, left, 30, 100) == 100


def test_rake_multiple_periods():
    seated = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    left = datetime(2025, 1, 1, 12, 47, 0, tzinfo=timezone.utc)
    assert calculate_rake(seated, left, 30, 100) == 200


def test_rake_exact_two_periods():
    seated = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    left = datetime(2025, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
    assert calculate_rake(seated, left, 30, 100) == 200


def test_rake_zero_duration():
    seated = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    left = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert calculate_rake(seated, left, 30, 100) == 0


def test_rake_large_duration():
    seated = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    left = datetime(2025, 1, 1, 15, 0, 0, tzinfo=timezone.utc)
    assert calculate_rake(seated, left, 30, 100) == 600


def test_rake_different_interval():
    seated = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    left = datetime(2025, 1, 1, 12, 25, 0, tzinfo=timezone.utc)
    assert calculate_rake(seated, left, 15, 50) == 100
