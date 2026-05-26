import pandas as pd
import pytest

import strategy


def _df(prev_fast, prev_slow, last_fast, last_slow, rsi, n=strategy.SMA_SLOW + 2):
    """Build a DataFrame with pre-set indicator values at the last two rows."""
    return pd.DataFrame(
        {
            "close":    [100.0]    * n,
            "sma_fast": [prev_fast] * (n - 1) + [last_fast],
            "sma_slow": [prev_slow] * (n - 1) + [last_slow],
            "rsi":      [rsi]      * n,
        },
        index=pd.date_range("2020-01-01", periods=n, freq="h"),
    )


@pytest.fixture(autouse=True)
def passthrough_indicators(monkeypatch):
    """Skip real indicator computation — use whatever columns the df already has."""
    monkeypatch.setattr(strategy, "compute_indicators", lambda df: df)


# --- insufficient data ---

def test_insufficient_data_returns_hold_with_empty_indicators():
    short_df = pd.DataFrame({"close": [100.0] * 10})
    signal, indicators = strategy.generate_signal(short_df)
    assert signal == "HOLD"
    assert indicators == {}


# --- golden cross (BUY) ---

def test_golden_cross_buys():
    df = _df(prev_fast=99, prev_slow=100, last_fast=101, last_slow=100, rsi=50)
    signal, _ = strategy.generate_signal(df)
    assert signal == "BUY"


def test_golden_cross_blocked_when_overbought():
    df = _df(prev_fast=99, prev_slow=100, last_fast=101, last_slow=100, rsi=65)
    signal, _ = strategy.generate_signal(df)
    assert signal == "HOLD"


# --- death cross (SELL) ---

def test_death_cross_sells():
    df = _df(prev_fast=101, prev_slow=100, last_fast=99, last_slow=100, rsi=50)
    signal, _ = strategy.generate_signal(df)
    assert signal == "SELL"


def test_death_cross_blocked_when_oversold():
    df = _df(prev_fast=101, prev_slow=100, last_fast=99, last_slow=100, rsi=35)
    signal, _ = strategy.generate_signal(df)
    assert signal == "HOLD"


# --- no crossover ---

def test_uptrend_continuation_holds():
    df = _df(prev_fast=101, prev_slow=100, last_fast=102, last_slow=100, rsi=50)
    signal, _ = strategy.generate_signal(df)
    assert signal == "HOLD"


def test_downtrend_continuation_holds():
    df = _df(prev_fast=99, prev_slow=100, last_fast=98, last_slow=100, rsi=50)
    signal, _ = strategy.generate_signal(df)
    assert signal == "HOLD"


# --- indicators dict ---

def test_indicators_contain_expected_keys():
    df = _df(prev_fast=101, prev_slow=100, last_fast=102, last_slow=100, rsi=50)
    _, indicators = strategy.generate_signal(df)
    assert set(indicators) == {"price", "sma_fast", "sma_slow", "rsi"}


def test_indicators_reflect_latest_row():
    df = _df(prev_fast=99, prev_slow=100, last_fast=101, last_slow=100, rsi=55)
    _, indicators = strategy.generate_signal(df)
    assert indicators["sma_fast"] == 101.0
    assert indicators["sma_slow"] == 100.0
    assert indicators["rsi"] == 55.0
