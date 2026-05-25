"""Trading212 REST API wrapper. Works against demo and live endpoints."""
import requests

import config

_AUTH = (config.T212_API_KEY, config.T212_SECRET_KEY)
_HEADERS = {"Content-Type": "application/json"}


def _get(path: str) -> dict | list:
    r = requests.get(f"{config.T212_BASE_URL}{path}", auth=_AUTH, headers=_HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict) -> dict:
    r = requests.post(f"{config.T212_BASE_URL}{path}", auth=_AUTH, headers=_HEADERS, json=body, timeout=10)
    r.raise_for_status()
    return r.json()


def get_account() -> dict:
    """Returns account summary including free cash."""
    return _get("/equity/account/summary")


def get_free_cash() -> float:
    account = get_account()
    cash = account.get("cash", {})
    return float(cash.get("availableToTrade", 0))


def get_positions() -> list[dict]:
    return _get("/equity/positions")


def get_position(ticker: str) -> dict | None:
    for p in get_positions():
        if p.get("ticker") == ticker:
            return p
    return None


def place_market_buy(ticker: str, quantity: float) -> dict:
    """Buy `quantity` shares (fractional allowed, max 4 decimal places)."""
    return _post("/equity/orders/market", {
        "ticker": ticker,
        "quantity": round(quantity, 4),
    })


def place_market_sell(ticker: str, quantity: float) -> dict:
    """Sell `quantity` shares. Pass a positive number — negation is handled here."""
    return _post("/equity/orders/market", {
        "ticker": ticker,
        "quantity": -abs(round(quantity, 4)),
    })


def close_position(ticker: str) -> dict:
    """Sell the entire open position for `ticker`."""
    pos = get_position(ticker)
    if pos is None:
        raise ValueError(f"No open position for {ticker}")
    return place_market_sell(ticker, pos["quantity"])
