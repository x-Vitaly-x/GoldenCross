from unittest.mock import patch

import pytest

import broker

# --- get_free_cash ---

def test_get_free_cash_reads_available_to_trade():
    account = {"cash": {"availableToTrade": 1234.56, "reservedForOrders": 0}}
    with patch("broker._get", return_value=account):
        assert broker.get_free_cash() == 1234.56


def test_get_free_cash_returns_zero_when_key_missing():
    with patch("broker._get", return_value={"cash": {}}):
        assert broker.get_free_cash() == 0.0


# --- get_position ---

def test_get_position_finds_matching_ticker():
    positions = [
        {"ticker": "AAPL_US_EQ", "quantity": 1.0},
        {"ticker": "VWCEd_EQ",   "quantity": 10.0},
    ]
    with patch("broker.get_positions", return_value=positions):
        pos = broker.get_position("VWCEd_EQ")
    assert pos["quantity"] == 10.0


def test_get_position_returns_none_when_not_found():
    with patch("broker.get_positions", return_value=[]):
        assert broker.get_position("VWCEd_EQ") is None


# --- place_market_buy ---

def test_place_market_buy_rounds_to_4_decimal_places():
    with patch("broker._post", return_value={}) as mock_post:
        broker.place_market_buy("VWCEd_EQ", 29.780564)
    body = mock_post.call_args[0][1]
    assert body["quantity"] == 29.7806
    assert body["ticker"] == "VWCEd_EQ"


def test_place_market_buy_sends_to_correct_endpoint():
    with patch("broker._post", return_value={}) as mock_post:
        broker.place_market_buy("VWCEd_EQ", 1.0)
    assert mock_post.call_args[0][0] == "/equity/orders/market"


# --- place_market_sell ---

def test_place_market_sell_negates_quantity():
    with patch("broker._post", return_value={}) as mock_post:
        broker.place_market_sell("VWCEd_EQ", 10.0)
    body = mock_post.call_args[0][1]
    assert body["quantity"] == -10.0


def test_place_market_sell_rounds_to_4_decimal_places():
    with patch("broker._post", return_value={}) as mock_post:
        broker.place_market_sell("VWCEd_EQ", 10.123456)
    body = mock_post.call_args[0][1]
    assert body["quantity"] == -10.1235


def test_place_market_sell_negates_already_negative_input():
    with patch("broker._post", return_value={}) as mock_post:
        broker.place_market_sell("VWCEd_EQ", -5.0)
    body = mock_post.call_args[0][1]
    assert body["quantity"] == -5.0


# --- close_position ---

def test_close_position_raises_when_no_position():
    with patch("broker.get_position", return_value=None):
        with pytest.raises(ValueError, match="No open position"):
            broker.close_position("VWCEd_EQ")


def test_close_position_sells_full_quantity():
    pos = {"ticker": "VWCEd_EQ", "quantity": 7.5}
    with patch("broker.get_position", return_value=pos):
        with patch("broker.place_market_sell", return_value={}) as mock_sell:
            broker.close_position("VWCEd_EQ")
    mock_sell.assert_called_once_with("VWCEd_EQ", 7.5)
