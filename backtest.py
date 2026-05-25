"""
Backtest the GoldenCross strategy against historical hourly OHLCV data.

Usage:
    python backtest.py VWCE.DE
    python backtest.py VWCE.DE --period 1y
    python backtest.py VWCE.DE --cash 5000 --period 2y
"""
import argparse
import sys
from dataclasses import dataclass, field

import pandas as pd

import config
import data as data_module
import strategy
from main import _is_stop_loss_triggered


@dataclass
class _Trade:
    action: str          # BUY | SELL | STOP_LOSS
    timestamp: pd.Timestamp
    price: float
    quantity: float
    pnl: float = 0.0


def _simulate(df: pd.DataFrame, initial_cash: float) -> tuple[list[_Trade], list[float]]:
    """Walk forward through pre-computed indicator data, return trades and equity curve."""
    df = strategy.compute_indicators(df)

    cash = initial_cash
    position: dict | None = None
    trades: list[_Trade] = []
    equity: list[float] = []

    for i in range(len(df)):
        row = df.iloc[i]
        price = float(row["close"])
        pos_value = position["quantity"] * price if position else 0.0
        equity.append(cash + pos_value)

        # Need at least SMA_SLOW + 1 candles for a valid crossover check
        if i < strategy.SMA_SLOW:
            continue

        if pd.isna(row["sma_slow"]) or pd.isna(row["sma_fast"]) or pd.isna(row["rsi"]):
            continue

        prev = df.iloc[i - 1]
        if pd.isna(prev["sma_slow"]):
            continue

        indicators = {
            "price": round(price, 4),
            "sma_fast": round(float(row["sma_fast"]), 4),
            "sma_slow": round(float(row["sma_slow"]), 4),
            "rsi": round(float(row["rsi"]), 2),
        }

        golden_cross = (
            float(prev["sma_fast"]) <= float(prev["sma_slow"])
            and float(row["sma_fast"]) > float(row["sma_slow"])
        )
        death_cross = (
            float(prev["sma_fast"]) >= float(prev["sma_slow"])
            and float(row["sma_fast"]) < float(row["sma_slow"])
        )

        if golden_cross and indicators["rsi"] < strategy.RSI_OVERBOUGHT:
            signal = "BUY"
        elif death_cross and indicators["rsi"] > strategy.RSI_OVERSOLD:
            signal = "SELL"
        else:
            signal = "HOLD"

        has_position = position is not None

        # Trend-continuation entry: mirrors main.py
        if signal == "HOLD" and not has_position:
            if indicators["sma_fast"] > indicators["sma_slow"] and indicators["rsi"] < strategy.RSI_OVERBOUGHT:
                signal = "BUY"

        # Stop-loss override: mirrors main.py
        stop_loss = False
        if has_position and signal != "SELL" and _is_stop_loss_triggered(position, price):
            signal = "SELL"
            stop_loss = True

        if signal == "BUY" and not has_position:
            invest = cash * config.POSITION_FRACTION
            quantity = invest / price
            cash -= invest
            position = {"entry_price": str(price), "quantity": quantity}
            trades.append(_Trade("BUY", df.index[i], price, quantity))

        elif signal == "SELL" and has_position:
            quantity = position["quantity"]
            proceeds = quantity * price
            pnl = proceeds - quantity * float(position["entry_price"])
            cash += proceeds
            trades.append(_Trade("STOP_LOSS" if stop_loss else "SELL", df.index[i], price, quantity, pnl))
            position = None

    return trades, equity


def _report(ticker_yf: str, df: pd.DataFrame, trades: list[_Trade],
            equity: list[float], initial_cash: float) -> None:
    final_value = equity[-1]
    strategy_return = (final_value - initial_cash) / initial_cash * 100

    bh_price_in  = float(df["close"].iloc[strategy.SMA_SLOW])
    bh_price_out = float(df["close"].iloc[-1])
    bh_invested  = initial_cash * config.POSITION_FRACTION
    bh_final     = (initial_cash - bh_invested) + bh_invested * (bh_price_out / bh_price_in)
    bh_return    = (bh_final - initial_cash) / initial_cash * 100

    buys  = [t for t in trades if t.action == "BUY"]
    sells = [t for t in trades if t.action in ("SELL", "STOP_LOSS")]
    stops = [t for t in trades if t.action == "STOP_LOSS"]
    wins  = sum(1 for t in sells if t.pnl > 0)
    win_rate = wins / len(sells) * 100 if sells else 0.0

    eq = pd.Series(equity)
    max_drawdown = ((eq - eq.cummax()) / eq.cummax() * 100).min()

    print()
    print("=" * 54)
    print(f"  Backtest: {ticker_yf}")
    print(f"  Period:   {df.index[0].date()} → {df.index[-1].date()}")
    print(f"  Capital:  €{initial_cash:,.2f}")
    print("=" * 54)
    print(f"  Strategy return:   {strategy_return:+.2f}%  (€{final_value:,.2f})")
    print(f"  Buy & hold:        {bh_return:+.2f}%  (€{bh_final:,.2f})")
    print(f"  Outperformance:    {strategy_return - bh_return:+.2f}%")
    print()
    print(f"  Trades:            {len(buys)}")
    print(f"  Win rate:          {win_rate:.1f}%")
    print(f"  Stop-loss fires:   {len(stops)}")
    print(f"  Max drawdown:      {max_drawdown:.2f}%")
    print("=" * 54)

    if buys:
        print()
        print("  Trade log:")
        for buy, sell in zip(buys, sells):
            pnl_pct = sell.pnl / (buy.price * buy.quantity) * 100
            label = f"{sell.action:<10}"
            print(f"    {buy.timestamp.date()}  BUY  €{buy.price:.2f}"
                  f"  →  {sell.timestamp.date()}  {label}  €{sell.price:.2f}"
                  f"  ({pnl_pct:+.1f}%)")
        if len(buys) > len(sells):
            last = buys[-1]
            open_pnl = (float(df["close"].iloc[-1]) - last.price) / last.price * 100
            print(f"    {last.timestamp.date()}  BUY  €{last.price:.2f}"
                  f"  →  still open  ({open_pnl:+.1f}% unrealised)")
    print()


def run_backtest(ticker_yf: str, initial_cash: float, period: str, interval: str) -> None:
    print(f"Downloading {ticker_yf} ({period} {interval})…", flush=True)
    try:
        df = data_module.fetch_ohlcv(ticker_yf, period=period, interval=interval)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    n = len(df)
    print(f"  {n} candles  ({df.index[0].date()} → {df.index[-1].date()})")

    if n < strategy.SMA_SLOW + 10:
        print(f"Error: need at least {strategy.SMA_SLOW + 10} candles, got {n}.", file=sys.stderr)
        sys.exit(1)

    trades, equity = _simulate(df, initial_cash)
    _report(ticker_yf, df, trades, equity, initial_cash)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest the GoldenCross strategy")
    parser.add_argument("ticker", help="yfinance ticker (e.g. VWCE.DE, SPY, QQQ)")
    parser.add_argument(
        "--interval", default="1h", choices=["1h", "1d"],
        help="Candle interval: 1h (default) or 1d. Hourly max is 2y; daily supports up to 10y+.",
    )
    parser.add_argument(
        "--period", default=None,
        help="History period: 6mo, 1y, 2y, 5y, 10y, etc. Defaults: 2y for 1h, 5y for 1d.",
    )
    parser.add_argument(
        "--cash", type=float, default=5000.0,
        help="Starting capital in EUR (default: 5000)",
    )
    args = parser.parse_args()
    period = args.period or ("2y" if args.interval == "1h" else "5y")
    run_backtest(args.ticker, args.cash, period, args.interval)
