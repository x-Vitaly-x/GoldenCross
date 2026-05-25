"""
RogueTrader — hourly trading bot entry point.

Each cycle:
  1. Skip if Xetra market is closed
  2. For each enabled instrument:
     a. Fetch hourly OHLCV data
     b. Generate signal (SMA crossover + RSI)
     c. Override to BUY if in uptrend with no position (trend-continuation entry)
     d. Get AI commentary (Together.ai)
     e. Execute trade if signal changed position
     f. Log decision and any trade
"""
import logging
import time
from datetime import datetime, timezone

import ai_analyst
import broker
import config
import data
import instruments as instr_module
import strategy
import tracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger(__name__)


def _is_market_open(now: datetime | None = None) -> bool:
    """Returns True if Xetra is currently open (Mon–Fri, 07:00–15:30 UTC)."""
    if now is None:
        now = datetime.now(timezone.utc)
    if now.weekday() >= 5:
        return False
    market_open  = now.replace(hour=7,  minute=0,  second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now < market_close


def _is_stop_loss_triggered(pos: dict, current_price: float, stop_loss_pct: float = config.STOP_LOSS_PCT) -> bool:
    """Returns True if price has fallen stop_loss_pct below the entry price."""
    entry_price = float(pos["entry_price"])
    return (entry_price - current_price) / entry_price >= stop_loss_pct


def run_instrument(instr: dict) -> None:
    """Run one full trading cycle for a single instrument."""
    t212 = instr["ticker_t212"]
    yf_ticker = instr["ticker_yfinance"]

    pos = tracker.get_position(t212)
    has_position = pos is not None

    log.info(f"[{t212}] Fetching data — {yf_ticker}")
    df = data.fetch_ohlcv(yf_ticker, period="60d", interval="1h")

    signal, indicators = strategy.generate_signal(df)
    if not indicators:
        log.warning(f"[{t212}] Not enough data to generate signal, skipping")
        return

    # Trend-continuation entry: buy into an existing uptrend if we have no position
    if signal == "HOLD" and not has_position:
        if indicators["sma_fast"] > indicators["sma_slow"] and indicators["rsi"] < 65:
            signal = "BUY"
            log.info(f"[{t212}] Trend-continuation entry: uptrend with no position, overriding to BUY")

    # Stop-loss override: force SELL if position has fallen beyond the threshold
    stop_loss_triggered = False
    if has_position and signal != "SELL" and _is_stop_loss_triggered(pos, indicators["price"]):
        loss_pct = (float(pos["entry_price"]) - indicators["price"]) / float(pos["entry_price"])
        log.warning(f"[{t212}] Stop-loss triggered: {loss_pct:.1%} loss (entry={pos['entry_price']}, current={indicators['price']})")
        signal = "SELL"
        stop_loss_triggered = True

    log.info(
        f"[{t212}] Signal={signal} price={indicators['price']} "
        f"SMA20={indicators['sma_fast']} SMA50={indicators['sma_slow']} "
        f"RSI={indicators['rsi']}"
    )

    reasoning = ai_analyst.analyse(t212, signal, indicators, df["close"].tolist())
    log.info(f"[{t212}] AI: {reasoning}")

    action = "HOLD"

    if signal == "BUY" and not has_position:
        cash = broker.get_free_cash()
        invest_eur = cash * config.POSITION_FRACTION
        if invest_eur < 1.0:
            log.warning(f"[{t212}] Free cash too low to buy: €{cash:.2f}")
        else:
            quantity = invest_eur / indicators["price"]
            broker.place_market_buy(t212, quantity)
            tracker.log_trade("BUY", t212, quantity, indicators["price"])
            tracker.set_position(t212, {
                "ticker": t212,
                "quantity": quantity,
                "entry_price": indicators["price"],
                "entry_time": datetime.now(timezone.utc).isoformat(),
            })
            action = "BUY"
            log.info(f"[{t212}] BUY {quantity:.4f} @ {indicators['price']}")

    elif signal == "SELL" and has_position:
        broker.close_position(t212)
        tracker.log_trade("SELL", t212, float(pos["quantity"]), indicators["price"])
        pnl = (indicators["price"] - float(pos["entry_price"])) * float(pos["quantity"])
        log.info(
            f"[{t212}] SELL {pos['quantity']:.4f} @ {indicators['price']} "
            f"| P&L: €{pnl:+.2f}"
        )
        tracker.set_position(t212, None)
        action = "STOP_LOSS" if stop_loss_triggered else "SELL"

    tracker.log_decision(t212, signal, action, indicators, reasoning)


def run_once():
    if not _is_market_open():
        log.info("Market closed, skipping")
        return

    for instr in instr_module.enabled_instruments():
        try:
            run_instrument(instr)
        except Exception as e:
            log.error(f"Cycle failed for {instr['ticker_t212']}: {e}", exc_info=True)


def _seconds_until_next_hour() -> float:
    now = datetime.now(timezone.utc)
    return (59 - now.minute) * 60 + (60 - now.second)


if __name__ == "__main__":
    instrs = instr_module.enabled_instruments()
    tickers = ", ".join(i["ticker_t212"] for i in instrs)
    log.info(
        f"RogueTrader starting | mode={config.T212_MODE} | "
        f"instruments=[{tickers}] | model={config.AI_MODEL}"
    )
    while True:
        try:
            run_once()
        except Exception as e:
            log.error(f"Cycle failed: {e}", exc_info=True)

        wait = _seconds_until_next_hour()
        log.info(f"Next run in {wait:.0f}s ({wait/60:.1f} min)")
        time.sleep(wait)
