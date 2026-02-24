"""UPbitExchange 단위 테스트"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from maiupbit.exchange.upbit import UPbitExchange


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def exchange_no_keys() -> UPbitExchange:
    """API 키 없는 거래소 인스턴스"""
    return UPbitExchange()


@pytest.fixture
def exchange_with_keys(tmp_path: Path) -> UPbitExchange:
    """API 키 있는 거래소 인스턴스 (pyupbit.Upbit 은 모킹)"""
    trade_file = str(tmp_path / "trade_history.json")
    with patch("maiupbit.exchange.upbit.pyupbit.Upbit") as mock_upbit_cls:
        mock_upbit_cls.return_value = MagicMock()
        ex = UPbitExchange(
            access_key="test_access",
            secret_key="test_secret",
            trade_history_path=trade_file,
        )
    return ex


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """테스트용 OHLCV DataFrame"""
    import numpy as np

    n = 5
    return pd.DataFrame(
        {
            "open":   [100.0, 101.0, 102.0, 103.0, 104.0],
            "high":   [105.0, 106.0, 107.0, 108.0, 109.0],
            "low":    [95.0,  96.0,  97.0,  98.0,  99.0],
            "close":  [102.0, 103.0, 104.0, 105.0, 106.0],
            "volume": [1000.0, 2000.0, 1500.0, 1800.0, 2200.0],
        }
    )


# ---------------------------------------------------------------------------
# get_ohlcv
# ---------------------------------------------------------------------------

class TestGetOhlcv:
    def test_returns_dataframe_on_success(
        self, exchange_no_keys: UPbitExchange, sample_df: pd.DataFrame
    ) -> None:
        with patch("maiupbit.exchange.upbit.pyupbit.get_ohlcv", return_value=sample_df):
            result = exchange_no_keys.get_ohlcv("KRW-BTC", "day", count=5)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 5

    def test_returns_empty_df_on_none(self, exchange_no_keys: UPbitExchange) -> None:
        with patch("maiupbit.exchange.upbit.pyupbit.get_ohlcv", return_value=None):
            result = exchange_no_keys.get_ohlcv("KRW-BTC")
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_returns_empty_df_on_exception(self, exchange_no_keys: UPbitExchange) -> None:
        with patch(
            "maiupbit.exchange.upbit.pyupbit.get_ohlcv",
            side_effect=Exception("network error"),
        ):
            result = exchange_no_keys.get_ohlcv("KRW-BTC")
        assert isinstance(result, pd.DataFrame)
        assert result.empty


# ---------------------------------------------------------------------------
# get_current_price
# ---------------------------------------------------------------------------

class TestGetCurrentPrice:
    def test_returns_float_on_success(self, exchange_no_keys: UPbitExchange) -> None:
        with patch("maiupbit.exchange.upbit.pyupbit.get_current_price", return_value=50_000_000):
            price = exchange_no_keys.get_current_price("KRW-BTC")
        assert price == 50_000_000.0
        assert isinstance(price, float)

    def test_returns_zero_on_none(self, exchange_no_keys: UPbitExchange) -> None:
        with patch("maiupbit.exchange.upbit.pyupbit.get_current_price", return_value=None):
            price = exchange_no_keys.get_current_price("KRW-BTC")
        assert price == 0.0

    def test_returns_zero_on_exception(self, exchange_no_keys: UPbitExchange) -> None:
        with patch(
            "maiupbit.exchange.upbit.pyupbit.get_current_price",
            side_effect=RuntimeError("timeout"),
        ):
            price = exchange_no_keys.get_current_price("KRW-BTC")
        assert price == 0.0


# ---------------------------------------------------------------------------
# get_portfolio
# ---------------------------------------------------------------------------

class TestGetPortfolio:
    def test_returns_error_without_api_keys(self, exchange_no_keys: UPbitExchange) -> None:
        result = exchange_no_keys.get_portfolio()
        assert "error" in result

    def test_returns_portfolio_with_api_keys(self, tmp_path: Path) -> None:
        mock_upbit = MagicMock()
        mock_upbit.get_balances.return_value = [
            {"currency": "KRW", "balance": "500000", "avg_buy_price": "0"},
        ]

        with patch("maiupbit.exchange.upbit.pyupbit.Upbit", return_value=mock_upbit):
            ex = UPbitExchange(
                access_key="ak",
                secret_key="sk",
                trade_history_path=str(tmp_path / "th.json"),
            )

        result = ex.get_portfolio()
        assert isinstance(result, dict)
        assert "assets" in result
        assert "total_value" in result
        assert len(result["assets"]) == 1
        assert result["assets"][0]["currency"] == "KRW"
        assert result["total_value"] == 500000.0

    def test_portfolio_with_crypto_balance(self, tmp_path: Path) -> None:
        mock_upbit = MagicMock()
        mock_upbit.get_balances.return_value = [
            {"currency": "BTC", "balance": "0.01", "avg_buy_price": "50000000"},
        ]

        with patch("maiupbit.exchange.upbit.pyupbit.Upbit", return_value=mock_upbit):
            with patch(
                "maiupbit.exchange.upbit.pyupbit.get_current_price",
                return_value=55_000_000.0,
            ):
                ex = UPbitExchange(
                    access_key="ak",
                    secret_key="sk",
                    trade_history_path=str(tmp_path / "th.json"),
                )
                result = ex.get_portfolio()

        assert isinstance(result, dict)
        assert "assets" in result
        assert len(result["assets"]) == 1
        assert result["assets"][0]["symbol"] == "KRW-BTC"
        assert result["total_value"] == 550000.0


# ---------------------------------------------------------------------------
# buy_market / sell_market
# ---------------------------------------------------------------------------

class TestBuyMarket:
    def test_returns_error_without_api_keys(self, exchange_no_keys: UPbitExchange) -> None:
        result = exchange_no_keys.buy_market("KRW-BTC", 10000)
        assert "error" in result

    def test_buy_success(self, tmp_path: Path) -> None:
        mock_upbit = MagicMock()
        mock_upbit.buy_market_order.return_value = {"uuid": "abc123", "price": 50_000_000.0}

        with patch("maiupbit.exchange.upbit.pyupbit.Upbit", return_value=mock_upbit):
            ex = UPbitExchange(
                access_key="ak",
                secret_key="sk",
                trade_history_path=str(tmp_path / "th.json"),
            )

        result = ex.buy_market("KRW-BTC", 50_000)
        assert isinstance(result, dict)
        assert result.get("uuid") == "abc123"
        # 거래 기록 저장 확인
        history = ex.get_trade_history()
        assert len(history) == 1
        assert history[0]["trade_type"] == "buy"

    def test_buy_exception(self, tmp_path: Path) -> None:
        mock_upbit = MagicMock()
        mock_upbit.buy_market_order.side_effect = Exception("order failed")

        with patch("maiupbit.exchange.upbit.pyupbit.Upbit", return_value=mock_upbit):
            ex = UPbitExchange(
                access_key="ak",
                secret_key="sk",
                trade_history_path=str(tmp_path / "th.json"),
            )

        result = ex.buy_market("KRW-BTC", 50_000)
        assert "error" in result


class TestSellMarket:
    def test_returns_error_without_api_keys(self, exchange_no_keys: UPbitExchange) -> None:
        result = exchange_no_keys.sell_market("KRW-BTC", 0.001)
        assert "error" in result

    def test_sell_success(self, tmp_path: Path) -> None:
        mock_upbit = MagicMock()
        mock_upbit.sell_market_order.return_value = {"uuid": "sell123", "price": 48_000_000.0}

        with patch("maiupbit.exchange.upbit.pyupbit.Upbit", return_value=mock_upbit):
            ex = UPbitExchange(
                access_key="ak",
                secret_key="sk",
                trade_history_path=str(tmp_path / "th.json"),
            )

        result = ex.sell_market("KRW-BTC", 0.001)
        assert isinstance(result, dict)
        assert result.get("uuid") == "sell123"
        history = ex.get_trade_history()
        assert len(history) == 1
        assert history[0]["trade_type"] == "sell"

    def test_sell_exception(self, tmp_path: Path) -> None:
        mock_upbit = MagicMock()
        mock_upbit.sell_market_order.side_effect = Exception("sell failed")

        with patch("maiupbit.exchange.upbit.pyupbit.Upbit", return_value=mock_upbit):
            ex = UPbitExchange(
                access_key="ak",
                secret_key="sk",
                trade_history_path=str(tmp_path / "th.json"),
            )

        result = ex.sell_market("KRW-BTC", 0.001)
        assert "error" in result


# ---------------------------------------------------------------------------
# _save_trade / get_trade_history
# ---------------------------------------------------------------------------

class TestTradeHistory:
    def test_empty_history_when_no_file(self, tmp_path: Path) -> None:
        ex = UPbitExchange(trade_history_path=str(tmp_path / "nonexistent.json"))
        assert ex.get_trade_history() == []

    def test_save_and_load(self, tmp_path: Path) -> None:
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

    def test_history_persists_across_instances(self, tmp_path: Path) -> None:
        path = str(tmp_path / "history.json")
        ex1 = UPbitExchange(trade_history_path=path)
        ex1._save_trade("KRW-BTC", 10_000.0, "buy", 100_000.0)

        ex2 = UPbitExchange(trade_history_path=path)
        history = ex2.get_trade_history()
        assert len(history) == 1

    def test_load_returns_empty_on_corrupt_json(self, tmp_path: Path) -> None:
        path = str(tmp_path / "corrupt.json")
        Path(path).write_text("NOT JSON", encoding="utf-8")
        ex = UPbitExchange(trade_history_path=path)
        assert ex.get_trade_history() == []


# ---------------------------------------------------------------------------
# get_market_info
# ---------------------------------------------------------------------------

class TestGetMarketInfo:
    def test_returns_dict_on_success(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"korean_name": "비트코인", "market": "KRW-BTC"},
            {"korean_name": "이더리움", "market": "KRW-ETH"},
            {"korean_name": "USD 코인", "market": "USDT-USDC"},  # 필터 제외
        ]
        with patch("maiupbit.exchange.upbit.requests.get", return_value=mock_response):
            result = UPbitExchange.get_market_info()
        assert isinstance(result, dict)
        assert "비트코인" in result
        assert result["비트코인"] == "KRW-BTC"
        assert "USD 코인" not in result  # KRW/BTC 마켓 아님

    def test_returns_empty_dict_on_exception(self) -> None:
        with patch(
            "maiupbit.exchange.upbit.requests.get",
            side_effect=Exception("connection refused"),
        ):
            result = UPbitExchange.get_market_info()
        assert result == {}

    def test_filters_btc_markets(self) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"korean_name": "비트코인", "market": "BTC-ETH"},
            {"korean_name": "이더리움", "market": "KRW-ETH"},
        ]
        with patch("maiupbit.exchange.upbit.requests.get", return_value=mock_response):
            result = UPbitExchange.get_market_info()
        assert "비트코인" in result  # BTC- 포함
        assert "이더리움" in result  # KRW- 포함


# ---------------------------------------------------------------------------
# get_current_status
# ---------------------------------------------------------------------------

class TestGetCurrentStatus:
    def test_returns_json_string(self, tmp_path: Path) -> None:
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

    def test_current_status_includes_balance(self, tmp_path: Path) -> None:
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


# ---------------------------------------------------------------------------
# fetch_data
# ---------------------------------------------------------------------------

class TestFetchData:
    def test_returns_tuple_on_success(
        self, tmp_path: Path, sample_df: pd.DataFrame
    ) -> None:
        with patch("maiupbit.exchange.upbit.pyupbit.Upbit"):
            ex = UPbitExchange(
                access_key="ak",
                secret_key="sk",
                trade_history_path=str(tmp_path / "th.json"),
            )

        with patch(
            "maiupbit.exchange.upbit.pyupbit.get_ohlcv",
            return_value=sample_df,
        ):
            daily, hourly = ex.fetch_data("KRW-BTC")

        assert daily is not None
        assert hourly is not None
        assert isinstance(daily, pd.DataFrame)
        assert isinstance(hourly, pd.DataFrame)

    def test_returns_none_on_exception(self, tmp_path: Path) -> None:
        with patch("maiupbit.exchange.upbit.pyupbit.Upbit"):
            ex = UPbitExchange(
                access_key="ak",
                secret_key="sk",
                trade_history_path=str(tmp_path / "th.json"),
            )

        with patch(
            "maiupbit.exchange.upbit.pyupbit.get_ohlcv",
            side_effect=Exception("network error"),
        ):
            daily, hourly = ex.fetch_data("KRW-BTC")

        assert daily is None
        assert hourly is None

    def test_uses_default_date_range(self, tmp_path: Path, sample_df: pd.DataFrame) -> None:
        """start_date/end_date 없으면 기본값 사용"""
        with patch("maiupbit.exchange.upbit.pyupbit.Upbit"):
            ex = UPbitExchange(
                access_key="ak",
                secret_key="sk",
                trade_history_path=str(tmp_path / "th.json"),
            )

        with patch(
            "maiupbit.exchange.upbit.pyupbit.get_ohlcv",
            return_value=sample_df,
        ) as mock_ohlcv:
            ex.fetch_data("KRW-BTC")

        assert mock_ohlcv.call_count == 2  # daily + hourly
