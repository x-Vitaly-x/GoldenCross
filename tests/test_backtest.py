"""Tests for the backtest simulation logic using synthetic price data."""
import math

import pandas as pd
import pytest

import backtest
import strategy


def _make_df(closes: list[float]) -> pd.DataFrame:
    """Build a minimal OHLCV DataFrame from a list of close prices."""
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="1h")
    return pd.DataFrame({"open": closes, "high": closes, "low": closes,
                         "close": closes, "volume": 1000}, index=idx)


def _oscillating_uptrend(n: int = 200) -> list[float]:
    """Gentle uptrend with oscillations — golden cross fires with RSI well below overbought."""
    return [100.0 + i * 0.05 + 3.0 * math.sin(i * 0.3) for i in range(n)]


def _up_then_down(n_up: int = 60, n_down: int = 40) -> list[float]:
    """Rally then sell-off — should produce a death cross."""
    up   = [100.0 + i * 0.5 for i in range(n_up)]
    down = [up[-1] - i * 0.5 for i in range(n_down)]
    return up + down


# --- simulation smoke tests ---

def test_simulate_returns_equity_same_length_as_df():
    df = _make_df(_oscillating_uptrend())
    _, equity = backtest._simulate(df, 1000.0)
    assert len(equity) == len(df)


def test_simulate_equity_starts_at_initial_cash():
    df = _make_df(_oscillating_uptrend())
    _, equity = backtest._simulate(df, 1000.0)
    assert equity[0] == pytest.approx(1000.0)


def test_simulate_produces_buy_on_uptrend():
    df = _make_df(_oscillating_uptrend(200))
    trades, _ = backtest._simulate(df, 1000.0)
    buys = [t for t in trades if t.action == "BUY"]
    assert len(buys) >= 1


def test_simulate_produces_sell_after_rally_and_drop():
    df = _make_df(_up_then_down(n_up=70, n_down=50))
    trades, _ = backtest._simulate(df, 1000.0)
    sells = [t for t in trades if t.action in ("SELL", "STOP_LOSS")]
    assert len(sells) >= 1


def test_simulate_stop_loss_fires_on_sharp_drop():
    # Buy into uptrend, then drop 20% — well beyond the 10% stop-loss
    prices = [100.0] * 60 + [100.0 + i * 0.5 for i in range(30)]  # uptrend triggers BUY
    peak = prices[-1]
    prices += [peak - i * 2.0 for i in range(40)]  # sharp sell-off
    df = _make_df(prices)
    trades, _ = backtest._simulate(df, 1000.0)
    stops = [t for t in trades if t.action == "STOP_LOSS"]
    assert len(stops) >= 1


def test_simulate_no_trades_on_flat_data():
    # Perfectly flat — no crossover ever fires
    df = _make_df([100.0] * 120)
    trades, _ = backtest._simulate(df, 1000.0)
    buys = [t for t in trades if t.action == "BUY"]
    # Trend-continuation entry fires immediately (SMA_fast == SMA_slow on flat data
    # means the condition sma_fast > sma_slow is False, so no entry expected)
    assert len(buys) == 0


def test_simulate_equity_never_negative():
    df = _make_df(_up_then_down())
    _, equity = backtest._simulate(df, 1000.0)
    assert all(v >= 0 for v in equity)
