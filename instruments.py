"""Instrument registry — persisted to instruments.json."""
import json
import os

INSTRUMENTS_FILE = "instruments.json"

_PLACEHOLDER_NAME = "Default instrument"


def load_instruments() -> list[dict]:
    if not os.path.exists(INSTRUMENTS_FILE):
        return []
    with open(INSTRUMENTS_FILE) as f:
        instruments = json.load(f)
    # Fix placeholder names written before name-lookup was in place
    changed = False
    for instr in instruments:
        if instr.get("name") in (_PLACEHOLDER_NAME, "", None):
            import data
            instr["name"] = data.get_instrument_name(instr["ticker_yfinance"])
            changed = True
    if changed:
        save_instruments(instruments)
    return instruments


def save_instruments(instruments: list[dict]) -> None:
    with open(INSTRUMENTS_FILE, "w") as f:
        json.dump(instruments, f, indent=2)


def add_instrument(ticker_t212: str, ticker_yfinance: str, name: str) -> dict:
    instruments = load_instruments()
    if any(i["ticker_t212"] == ticker_t212 for i in instruments):
        raise ValueError(f"Instrument {ticker_t212} already exists")
    entry = {
        "ticker_t212": ticker_t212,
        "ticker_yfinance": ticker_yfinance,
        "name": name,
        "enabled": True,
    }
    instruments.append(entry)
    save_instruments(instruments)
    return entry


def remove_instrument(ticker_t212: str) -> None:
    save_instruments([i for i in load_instruments() if i["ticker_t212"] != ticker_t212])


def toggle_instrument(ticker_t212: str, enabled: bool) -> None:
    instruments = load_instruments()
    for instr in instruments:
        if instr["ticker_t212"] == ticker_t212:
            instr["enabled"] = enabled
            break
    save_instruments(instruments)


def enabled_instruments() -> list[dict]:
    return [i for i in load_instruments() if i.get("enabled", True)]
