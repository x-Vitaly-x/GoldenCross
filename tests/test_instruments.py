import json

import pytest

import instruments


@pytest.fixture(autouse=True)
def isolated_file(tmp_path, monkeypatch):
    monkeypatch.setattr(instruments, "INSTRUMENTS_FILE", str(tmp_path / "instruments.json"))


# --- load / save ---

def test_load_returns_empty_when_no_file():
    result = instruments.load_instruments()
    assert result == []


def test_load_reads_existing_file():
    instruments.add_instrument("VWCEd_EQ", "VWCE.DE", "Vanguard FTSE All-World")
    result = instruments.load_instruments()
    assert len(result) == 1
    assert result[0]["ticker_t212"] == "VWCEd_EQ"


# --- add ---

def test_add_instrument_appends_entry():
    instruments.add_instrument("NEW_EQ", "NEW.DE", "New Fund")
    result = instruments.load_instruments()
    tickers = [i["ticker_t212"] for i in result]
    assert "NEW_EQ" in tickers


def test_add_instrument_returns_entry():
    entry = instruments.add_instrument("NEW_EQ", "NEW.DE", "New Fund")
    assert entry["ticker_t212"] == "NEW_EQ"
    assert entry["ticker_yfinance"] == "NEW.DE"
    assert entry["enabled"] is True


def test_add_instrument_raises_on_duplicate():
    instruments.add_instrument("DUP_EQ", "DUP.DE", "Dup Fund")
    with pytest.raises(ValueError, match="already exists"):
        instruments.add_instrument("DUP_EQ", "DUP2.DE", "Dup Fund 2")


# --- remove ---

def test_remove_instrument_deletes_entry():
    instruments.add_instrument("REM_EQ", "REM.DE", "Remove Me")
    instruments.remove_instrument("REM_EQ")
    tickers = [i["ticker_t212"] for i in instruments.load_instruments()]
    assert "REM_EQ" not in tickers


def test_remove_nonexistent_instrument_is_noop():
    before = instruments.load_instruments()
    instruments.remove_instrument("GHOST_EQ")
    assert instruments.load_instruments() == before


# --- toggle ---

def test_toggle_instrument_disables():
    instruments.add_instrument("TOG_EQ", "TOG.DE", "Toggle Me")
    instruments.toggle_instrument("TOG_EQ", False)
    entry = next(i for i in instruments.load_instruments() if i["ticker_t212"] == "TOG_EQ")
    assert entry["enabled"] is False


def test_toggle_instrument_re_enables():
    instruments.add_instrument("TOG2_EQ", "TOG2.DE", "Toggle Me 2")
    instruments.toggle_instrument("TOG2_EQ", False)
    instruments.toggle_instrument("TOG2_EQ", True)
    entry = next(i for i in instruments.load_instruments() if i["ticker_t212"] == "TOG2_EQ")
    assert entry["enabled"] is True


# --- enabled_instruments ---

def test_enabled_instruments_excludes_disabled():
    instruments.add_instrument("ON_EQ",  "ON.DE",  "On")
    instruments.add_instrument("OFF_EQ", "OFF.DE", "Off")
    instruments.toggle_instrument("OFF_EQ", False)
    enabled = [i["ticker_t212"] for i in instruments.enabled_instruments()]
    assert "ON_EQ" in enabled
    assert "OFF_EQ" not in enabled
