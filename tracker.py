"""Trade logging and state persistence."""
import csv
import json
import os
from datetime import datetime, timezone

TRADES_FILE = "logs/trades.csv"
DECISIONS_FILE = "logs/decisions.csv"
STATE_FILE = "state.json"

_TRADE_FIELDS = ["timestamp", "action", "ticker", "quantity", "price", "value_eur"]
_DECISION_FIELDS = [
    "timestamp", "ticker", "signal", "action_taken",
    "price", "sma_fast", "sma_slow", "rsi", "ai_reasoning",
]


def _ensure_csv(path: str, fields: list[str]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=fields).writeheader()


def log_decision(ticker: str, signal: str, action: str, indicators: dict, reasoning: str):
    _ensure_csv(DECISIONS_FILE, _DECISION_FIELDS)
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ticker": ticker,
        "signal": signal,
        "action_taken": action,
        "price": indicators.get("price", ""),
        "sma_fast": indicators.get("sma_fast", ""),
        "sma_slow": indicators.get("sma_slow", ""),
        "rsi": indicators.get("rsi", ""),
        "ai_reasoning": reasoning.replace("\n", " "),
    }
    with open(DECISIONS_FILE, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=_DECISION_FIELDS).writerow(row)


def log_trade(action: str, ticker: str, quantity: float, price: float):
    _ensure_csv(TRADES_FILE, _TRADE_FIELDS)
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "ticker": ticker,
        "quantity": quantity,
        "price": price,
        "value_eur": round(abs(quantity) * price, 2),
    }
    with open(TRADES_FILE, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=_TRADE_FIELDS).writerow(row)


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {"positions": {}}
    with open(STATE_FILE) as f:
        state = json.load(f)
    # Migrate old single-position format {"position": ...} → {"positions": {...}}
    if "position" in state and "positions" not in state:
        pos = state["position"]
        state = {"positions": {pos["ticker"]: pos} if pos else {}}
        save_state(state)
    return state


def get_position(ticker: str) -> dict | None:
    return load_state()["positions"].get(ticker)


def set_position(ticker: str, position: dict | None) -> None:
    state = load_state()
    if position is None:
        state["positions"].pop(ticker, None)
    else:
        state["positions"][ticker] = position
    save_state(state)
