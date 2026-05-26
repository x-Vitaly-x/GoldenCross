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


def _down_then_oscillating_up(n_warmup: int = 50, n_down: int = 180, n_up: int = 300) -> list[float]:
    """Downtrend (SMA50 falls below SMA200) then oscillating rally (golden cross fires, RSI < 65)."""
    warmup = [100.0] * n_warmup
    down   = [100.0 - i * 0.15 for i in range(n_down)]
    bottom = down[-1]
    up     = [bottom + i * 0.12 + 20.0 * math.sin(i * 0.4) for i in range(n_up)]
    return warmup + down + up


def _down_up_then_crash() -> list[float]:
    """Downtrend + oscillating rally (golden cross) + sharp crash (triggers stop-loss)."""
    base  = _down_then_oscillating_up(n_up=150)
    peak  = base[-1]
    crash = [peak - i * 3.0 for i in range(20)]
    return base + crash


# --- simulation smoke tests ---

def test_simulate_returns_equity_same_length_as_df():
    df = _make_df(_down_then_oscillating_up())
    _, equity = backtest._simulate(df, 1000.0)
    assert len(equity) == len(df)


def test_simulate_equity_starts_at_initial_cash():
    df = _make_df(_down_then_oscillating_up())
    _, equity = backtest._simulate(df, 1000.0)
    assert equity[0] == pytest.approx(1000.0)


def test_simulate_produces_buy_on_uptrend():
    df = _make_df(_down_then_oscillating_up())
    trades, _ = backtest._simulate(df, 1000.0)
    buys = [t for t in trades if t.action == "BUY"]
    assert len(buys) >= 1


def test_simulate_produces_sell_after_rally_and_drop():
    df = _make_df(_down_up_then_crash())
    trades, _ = backtest._simulate(df, 1000.0)
    sells = [t for t in trades if t.action in ("SELL", "STOP_LOSS")]
    assert len(sells) >= 1


def test_simulate_stop_loss_fires_on_sharp_drop():
    df = _make_df(_down_up_then_crash())
    trades, _ = backtest._simulate(df, 1000.0)
    stops = [t for t in trades if t.action == "STOP_LOSS"]
    assert len(stops) >= 1


def test_simulate_no_trades_on_flat_data():
    df = _make_df([100.0] * (strategy.SMA_SLOW + 50))
    trades, _ = backtest._simulate(df, 1000.0)
    assert len([t for t in trades if t.action == "BUY"]) == 0


def test_simulate_equity_never_negative():
    df = _make_df(_down_up_then_crash())
    _, equity = backtest._simulate(df, 1000.0)
    assert all(v >= 0 for v in equity)
