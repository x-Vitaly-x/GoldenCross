from datetime import datetime, timezone

import main


_POS = {"entry_price": "100.00", "quantity": "10.0", "ticker": "X_EQ"}


# --- _is_stop_loss_triggered ---

def test_stop_loss_not_triggered_below_threshold():
    assert main._is_stop_loss_triggered(_POS, 91.0, stop_loss_pct=0.10) is False


def test_stop_loss_triggered_at_exact_threshold():
    assert main._is_stop_loss_triggered(_POS, 90.0, stop_loss_pct=0.10) is True


def test_stop_loss_triggered_beyond_threshold():
    assert main._is_stop_loss_triggered(_POS, 80.0, stop_loss_pct=0.10) is True


def test_stop_loss_not_triggered_when_price_rises():
    assert main._is_stop_loss_triggered(_POS, 110.0, stop_loss_pct=0.10) is False


def test_stop_loss_not_triggered_at_entry_price():
    assert main._is_stop_loss_triggered(_POS, 100.0, stop_loss_pct=0.10) is False


def _dt(weekday: int, hour: int, minute: int = 0) -> datetime:
    """Build a UTC datetime on the given weekday (0=Mon … 6=Sun)."""
    # 2024-01-01 is a Monday — offset by weekday to get the right day
    return datetime(2024, 1, 1 + weekday, hour, minute, tzinfo=timezone.utc)


# --- _is_market_open ---

def test_open_on_monday_during_hours():
    assert main._is_market_open(_dt(0, 17)) is True


def test_open_at_exactly_market_open():
    assert main._is_market_open(_dt(0, 14, 30)) is True


def test_closed_one_minute_before_open():
    assert main._is_market_open(_dt(0, 14, 29)) is False


def test_closed_at_exactly_market_close():
    assert main._is_market_open(_dt(0, 21, 0)) is False


def test_closed_after_market_close():
    assert main._is_market_open(_dt(0, 22, 0)) is False


def test_closed_on_saturday():
    assert main._is_market_open(_dt(5, 17)) is False


def test_closed_on_sunday():
    assert main._is_market_open(_dt(6, 17)) is False


def test_open_on_friday():
    assert main._is_market_open(_dt(4, 17)) is True
