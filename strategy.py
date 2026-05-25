"""
Signal generation: SMA crossover filtered by RSI.

BUY  — SMA20 crosses above SMA50 AND RSI < 65  (momentum up, not overbought)
SELL — SMA20 crosses below SMA50 AND RSI > 35  (momentum down, not oversold)
HOLD — everything else
"""
import pandas as pd
import ta

SMA_FAST = 20
SMA_SLOW = 50
RSI_PERIOD = 14
RSI_OVERBOUGHT = 65
RSI_OVERSOLD = 35


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["sma_fast"] = ta.trend.sma_indicator(df["close"], window=SMA_FAST)
    df["sma_slow"] = ta.trend.sma_indicator(df["close"], window=SMA_SLOW)
    df["rsi"] = ta.momentum.rsi(df["close"], window=RSI_PERIOD)
    return df


def generate_signal(df: pd.DataFrame) -> tuple[str, dict]:
    """
    Returns (signal, indicators) where signal is 'BUY', 'SELL', or 'HOLD'
    and indicators is a dict with the latest computed values.
    Requires at least SMA_SLOW + 2 rows of data.
    """
    if len(df) < SMA_SLOW + 2:
        return "HOLD", {}

    df = compute_indicators(df)
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    indicators = {
        "price": round(float(latest["close"]), 4),
        "sma_fast": round(float(latest["sma_fast"]), 4),
        "sma_slow": round(float(latest["sma_slow"]), 4),
        "rsi": round(float(latest["rsi"]), 2),
    }

    golden_cross = (
        float(prev["sma_fast"]) <= float(prev["sma_slow"])
        and float(latest["sma_fast"]) > float(latest["sma_slow"])
    )
    death_cross = (
        float(prev["sma_fast"]) >= float(prev["sma_slow"])
        and float(latest["sma_fast"]) < float(latest["sma_slow"])
    )

    if golden_cross and indicators["rsi"] < RSI_OVERBOUGHT:
        return "BUY", indicators
    if death_cross and indicators["rsi"] > RSI_OVERSOLD:
        return "SELL", indicators
    return "HOLD", indicators
