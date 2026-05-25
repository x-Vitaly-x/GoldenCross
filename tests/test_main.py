from datetime import datetime, timezone

import main


def _dt(weekday: int, hour: int, minute: int = 0) -> datetime:
    """Build a UTC datetime on the given weekday (0=Mon … 6=Sun)."""
    # 2024-01-01 is a Monday — offset by weekday to get the right day
    return datetime(2024, 1, 1 + weekday, hour, minute, tzinfo=timezone.utc)


# --- _is_market_open ---

def test_open_on_monday_during_hours():
    assert main._is_market_open(_dt(0, 10)) is True


def test_open_at_exactly_market_open():
    assert main._is_market_open(_dt(0, 7, 0)) is True


def test_closed_one_minute_before_open():
    assert main._is_market_open(_dt(0, 6, 59)) is False


def test_closed_at_exactly_market_close():
    assert main._is_market_open(_dt(0, 15, 30)) is False


def test_closed_after_market_close():
    assert main._is_market_open(_dt(0, 16, 0)) is False


def test_closed_on_saturday():
    assert main._is_market_open(_dt(5, 10)) is False


def test_closed_on_sunday():
    assert main._is_market_open(_dt(6, 10)) is False


def test_open_on_friday():
    assert main._is_market_open(_dt(4, 12)) is True
