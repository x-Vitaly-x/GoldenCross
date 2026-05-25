import csv
import json

import pytest

import tracker

INDICATORS = {"price": 100.0, "sma_fast": 101.0, "sma_slow": 99.0, "rsi": 50.0}


@pytest.fixture(autouse=True)
def isolated_files(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "TRADES_FILE",    str(tmp_path / "logs" / "trades.csv"))
    monkeypatch.setattr(tracker, "DECISIONS_FILE", str(tmp_path / "logs" / "decisions.csv"))
    monkeypatch.setattr(tracker, "STATE_FILE",     str(tmp_path / "state.json"))


# --- state ---

def test_load_state_defaults_when_no_file():
    assert tracker.load_state() == {"positions": {}}


def test_set_and_get_position_round_trips():
    pos = {"ticker": "TEST_EQ", "quantity": 10.0, "entry_price": 100.0}
    tracker.set_position("TEST_EQ", pos)
    assert tracker.get_position("TEST_EQ") == pos


def test_get_position_returns_none_when_not_set():
    assert tracker.get_position("MISSING_EQ") is None


def test_set_position_none_removes_ticker():
    tracker.set_position("TEST_EQ", {"ticker": "TEST_EQ", "quantity": 5.0, "entry_price": 50.0})
    tracker.set_position("TEST_EQ", None)
    assert tracker.get_position("TEST_EQ") is None


def test_multiple_positions_stored_independently():
    tracker.set_position("AAA_EQ", {"ticker": "AAA_EQ", "quantity": 1.0, "entry_price": 10.0})
    tracker.set_position("BBB_EQ", {"ticker": "BBB_EQ", "quantity": 2.0, "entry_price": 20.0})
    assert tracker.get_position("AAA_EQ")["quantity"] == 1.0
    assert tracker.get_position("BBB_EQ")["quantity"] == 2.0


def test_load_state_migrates_old_single_position_format(tmp_path, monkeypatch):
    state_file = str(tmp_path / "state.json")
    monkeypatch.setattr(tracker, "STATE_FILE", state_file)
    old_pos = {"ticker": "OLD_EQ", "quantity": 3.0, "entry_price": 30.0}
    with open(state_file, "w") as f:
        json.dump({"position": old_pos}, f)
    state = tracker.load_state()
    assert "positions" in state
    assert state["positions"]["OLD_EQ"] == old_pos


def test_load_state_migrates_old_null_position_format(tmp_path, monkeypatch):
    state_file = str(tmp_path / "state.json")
    monkeypatch.setattr(tracker, "STATE_FILE", state_file)
    with open(state_file, "w") as f:
        json.dump({"position": None}, f)
    state = tracker.load_state()
    assert state == {"positions": {}}


# --- trade log ---

def test_log_trade_creates_header_and_row():
    tracker.log_trade("BUY", "TEST_EQ", 5.0, 100.0)
    with open(tracker.TRADES_FILE) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["action"] == "BUY"
    assert rows[0]["ticker"] == "TEST_EQ"


def test_log_trade_value_eur_is_abs_quantity_times_price():
    tracker.log_trade("BUY", "TEST_EQ", 5.0, 100.0)
    with open(tracker.TRADES_FILE) as f:
        rows = list(csv.DictReader(f))
    assert float(rows[0]["value_eur"]) == 500.0


def test_log_trade_value_eur_uses_abs_for_negative_quantity():
    tracker.log_trade("SELL", "TEST_EQ", -5.0, 100.0)
    with open(tracker.TRADES_FILE) as f:
        rows = list(csv.DictReader(f))
    assert float(rows[0]["value_eur"]) == 500.0


def test_log_trade_appends_multiple_rows():
    tracker.log_trade("BUY",  "TEST_EQ", 5.0, 100.0)
    tracker.log_trade("SELL", "TEST_EQ", 5.0, 110.0)
    with open(tracker.TRADES_FILE) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2


# --- decision log ---

def test_log_decision_creates_row():
    tracker.log_decision("TEST_EQ", "BUY", "BUY", INDICATORS, "looks good")
    with open(tracker.DECISIONS_FILE) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["signal"] == "BUY"
    assert rows[0]["action_taken"] == "BUY"


def test_log_decision_strips_newlines_from_reasoning():
    tracker.log_decision("TEST_EQ", "HOLD", "HOLD", INDICATORS, "line1\nline2")
    with open(tracker.DECISIONS_FILE) as f:
        rows = list(csv.DictReader(f))
    assert "\n" not in rows[0]["ai_reasoning"]


def test_log_decision_appends_multiple_rows():
    tracker.log_decision("TEST_EQ", "BUY",  "BUY",  INDICATORS, "a")
    tracker.log_decision("TEST_EQ", "HOLD", "HOLD", INDICATORS, "b")
    with open(tracker.DECISIONS_FILE) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
