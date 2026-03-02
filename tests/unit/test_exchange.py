"""UPbitExchange unit tests"""
from __future__ import annotations

import json
import requests
from unittest.mock import MagicMock, patch

import pytest

from maiupbit.exchange.upbit import UPbitExchange


def test_empty_history_when_no_file(tmp_path: Path) -> None:
    ex = UPbitExchange(trade_history_path=str(tmp_path / "nonexistent.json"))
    assert ex.get_trade_history() == []


def test_save_and_load(tmp_path: Path) -> None:
    path = str(tmp_path / "history.json")
    ex = UPbitExchange(trade_history_path=path)

    ex._save_trade("KRW-BTC", 50_000.0, "buy", 50_000_000.0)
    ex._save_trade("KRW-ETH", 0.1, "sell", 3_000_000.0)

    history = ex.get_trade_history()
    assert len(history) == 2
    assert history[0]["symbol"] == "KRW-BTC"
    assert history[0]["trade_type"] == "buy"
    assert history[1]["symbol"] == "KRW-ETH"
    assert history[1]["trade_type"] == "sell"
    assert history[1]["id"] == 2


def test_history_persists_across_instances(tmp_path: Path) -> None:
    path = str(tmp_path / "history.json")
    ex1 = UPbitExchange(trade_history_path=path)
    ex1._save_trade("KRW-BTC", 10_000.0, "buy", 100_000.0)

    ex2 = UPbitExchange(trade_history_path=path)
    history = ex2.get_trade_history()
    assert len(history) == 1


def test_load_returns_empty_on_corrupt_json(tmp_path: Path) -> None:
    path = str(tmp_path / "corrupt.json")
    Path(path).write_text("NOT JSON", encoding="utf-8")
    ex = UPbitExchange(trade_history_path=path)
    assert ex.get_trade_history() == []


def test_returns_dict_on_success() -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"korean_name": "Bitcoin", "market": "KRW-BTC"},
        {"korean_name": "Ethereum", "market": "KRW-ETH"},
        {"korean_name": "USD Coin", "market": "USDT-USDC"},  # Filtered out
    ]
    with patch("maiupbit.exchange.upbit.requests.get", return_value=mock_response):
        result = UPbitExchange.get_market_info()
    assert isinstance(result, dict)
    assert "Bitcoin" in result
    assert result["Bitcoin"] == "KRW-BTC"
    assert "USD Coin" not in result  # Not a KRW/BTC market


def test_returns_empty_dict_on_exception() -> None:
    with patch(
        "maiupbit.exchange.upbit.requests.get",
        side_effect=Exception("connection refused"),
    ):
        result = UPbitExchange.get_market_info()
    assert result == {}


def test_filters_btc_markets() -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"korean_name": "Bitcoin", "market": "BTC-ETH"},
        {"korean_name": "Ethereum", "market": "KRW-ETH"},
    ]
    with patch("maiupbit.exchange.upbit.requests.get", return_value=mock_response):
        result = UPbitExchange.get_market_info()
    assert "Bitcoin" in result  # BTC- included
    assert "Ethereum" in result  # KRW- included


def test_returns_json_string(tmp_path: Path) -> None:
    mock_upbit = MagicMock()
    mock_upbit.get_balance.return_value = 0.5
    mock_upbit.get_avg_buy_price.return_value = 50_000_000.0

    with patch("maiupbit.exchange.upbit.pyupbit.Upbit", return_value=mock_upbit):
        ex = UPbitExchange(
            access_key="ak",
            secret_key="sk",
            trade_history_path=str(tmp_path / "th.json"),
        )

    with patch.object(ex, "get_orderbook", return_value={"timestamp": 12345}):
        import json as _json
        result = ex.get_current_status("KRW-BTC")

    data = _json.loads(result)
    assert "current_time" in data
    assert "orderbook" in data
    assert "balance" in data
    assert "krw_balance" in data
    assert "coin_avg_buy_price" in data


def test_current_status_includes_balance(tmp_path: Path) -> None:
    mock_upbit = MagicMock()
    mock_upbit.get_balance.side_effect = lambda ticker: (
        0.01 if "BTC" in ticker else 500_000.0
    )
    mock_upbit.get_avg_buy_price.return_value = 50_000_000.0

    with patch("maiupbit.exchange.upbit.pyupbit.Upbit", return_value=mock_upbit):
        ex = UPbitExchange(
            access_key="ak",
            secret_key="sk",
            trade_history_path=str(tmp_path / "th.json"),
        )

    with patch.object(ex, "get_orderbook", return_value={}):
        import json as _json
        result = ex.get_current_status("KRW-BTC")

    data = _json.loads(result)
    assert data["balance"] == 0.01


def test_returns_tuple_on_success(tmp_path: Path) -> None:
    with patch("maiupbit.exchange.upbit.pyupbit.Upbit"):
        ex = UPbitExchange(
            access_key="ak",
            secret_key="sk",
            trade_history_path=str(tmp_path / "th.json"),
        )

    sample_df = MagicMock()
    sample_df.to_dict.return_value = {"daily": {}, "hourly": {}}
    with patch("maiupbit.exchange.upbit.pyupbit.get_ohlcv", return_value=sample_df):
        daily, hourly = ex.fetch_data("KRW-BTC")

    assert daily is not None
    assert hourly is not None
    assert isinstance(daily, dict)
    assert isinstance(hourly, dict)


def test_returns_none_on_exception(tmp_path: Path) -> None:
    with patch("maiupbit.exchange.upbit.pyupbit.Upbit"):
        ex = UPbitExchange(
            access_key="ak",
            secret_key="sk",
            trade_history_path=str(tmp_path / "th.json"),
        )

    with patch(
        "maiupbit.exchange.upbit.pyupbit.get_ohlcv", side_effect=Exception("network error")
    ):
        daily, hourly = ex.fetch_data("KRW-BTC")

    assert daily is None
    assert hourly is None


def test_uses_default_date_range(tmp_path: Path) -> None:
    """start_date/end_date not provided should use default values"""
    with patch("maiupbit.exchange.upbit.pyupbit.Upbit"):
        ex = UPbitExchange(
            access_key="ak",
            secret_key="sk",
            trade_history_path=str(tmp_path / "th.json"),
        )

    sample_df = MagicMock()
    sample_df.to_dict.return_value = {"daily": {}, "hourly": {}}
    with patch("maiupbit.exchange.upbit.pyupbit.get_ohlcv", return_value=sample_df) as mock_ohlcv:
        ex.fetch_data("KRW-BTC")

    assert mock_ohlcv.call_count == 2  # daily + hourly