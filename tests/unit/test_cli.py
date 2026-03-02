"""
CLI command unit tests
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helper - Test OHLCV DataFrame
# ---------------------------------------------------------------------------

def _make_ohlcv(n: int = 50) -> pd.DataFrame:
    """Test OHLCV DataFrame (includes columns needed for indicator calculation)"""
    np.random.seed(7)
    dates = pd.date_range("2026-01-01", periods=n, freq="h")
    close = 50_000 + np.cumsum(np.random.randn(n) * 500)
    return pd.DataFrame(
        {
            "open":   close + np.random.randn(n) * 100,
            "high":   close + np.abs(np.random.randn(n) * 200),
            "low":    close - np.abs(np.random.randn(n) * 200),
            "close":  close,
            "volume": np.random.randint(100, 5000, n).astype(float),
        },
        index=dates,
    )


def _analyze_args(**kwargs: Any) -> argparse.Namespace:
    defaults = {"symbol": "KRW-BTC", "days": 30, "format": "json"}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _portfolio_args(**kwargs: Any) -> argparse.Namespace:
    defaults = {"format": "json"}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _trade_args(**kwargs: Any) -> argparse.Namespace:
    defaults = {
        "action": "buy", "symbol": "KRW-BTC", "amount": 50_000.0,
        "confirm": False, "format": "json",
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# cmd_analyze
# Note: CLI functions internally use local imports of the form `from maiupbit.exchange.upbit import UPbitExchange`
# Therefore, source modules must be patched.
# ---------------------------------------------------------------------------

class TestCmdAnalyze:
    def test_analyze_json_output(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Check JSON output after normal execution"""
        ohlcv = _make_ohlcv()

        mock_exchange_instance = MagicMock()
        mock_exchange_instance.get_ohlcv.return_value = ohlcv
        mock_exchange_instance.get_current_price.return_value = 55_000_000.0

        mock_analyze_result = {
            "indicators": {"rsi_14": 55.0, "macd": 100.0, "macd_signal": 90.0},
            "signals": {"recommendation": "hold"},
            "score": 0.0,
        }

        with patch("maiupbit.exchange.upbit.UPbitExchange", return_value=mock_exchange_instance):
            from maiupbit.analysis.technical import TechnicalAnalyzer
            mock_analyzer = MagicMock()
            mock_analyzer.analyze.return_value = mock_analyze_result

            from maiupbit.cli import cmd_analyze
            cmd_analyze(_analyze_args())

        captured = capsys.readouterr()
        assert "json" in captured.out

    def test_analyze_exits_without_api_keys(self, monkeypatch) -> None:
        """Test that the function exits with code 1 if API keys are not set"""
        monkeypatch.delenv("UPBIT_ACCESS_KEY", raising=False)
        monkeypatch.delenv("UPBIT_SECRET_KEY", raising=False)

        from maiupbit.cli import cmd_analyze
        with pytest.raises(SystemExit) as exc_info:
            cmd_analyze(_analyze_args())
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# cmd_trade
# ---------------------------------------------------------------------------

class TestCmdTrade:
    def test_trade_preview_without_confirm(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that without --confirm, a preview is shown and the function exits with code 0"""
        monkeypatch.setenv("UPBIT_ACCESS_KEY", "ak")
        monkeypatch.setenv("UPBIT_SECRET_KEY", "sk")

        mock_exchange_instance = MagicMock()
        mock_exchange_instance.get_current_price.return_value = 50_000_000.0

        with patch("maiupbit.exchange.upbit.UPbitExchange", return_value=mock_exchange_instance):
            from maiupbit.cli import cmd_trade
            with pytest.raises(SystemExit) as exc_info:
                cmd_trade(_trade_args(confirm=False))

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "--confirm" in captured.out

    def test_trade_exits_without_api_keys(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that the function exits with code 1 if API keys are not set"""
        monkeypatch.delenv("UPBIT_ACCESS_KEY", raising=False)
        monkeypatch.delenv("UPBIT_SECRET_KEY", raising=False)

        from maiupbit.cli import cmd_trade
        with pytest.raises(SystemExit) as exc_info:
            cmd_trade(_trade_args(confirm=True))
        assert exc_info.value.code == 1

    def test_trade_buy_with_confirm(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that with --confirm, buy_market is called"""
        monkeypatch.setenv("UPBIT_ACCESS_KEY", "ak")
        monkeypatch.setenv("UPBIT_SECRET_KEY", "sk")

        mock_exchange_instance = MagicMock()
        mock_exchange_instance.buy_market.return_value = {"uuid": "buy-123"}

        with patch("maiupbit.exchange.upbit.UPbitExchange", return_value=mock_exchange_instance):
            from maiupbit.cli import cmd_trade
            cmd_trade(_trade_args(action="buy", confirm=True))

        mock_exchange_instance.buy_market.assert_called_once_with("KRW-BTC", 50_000.0)

    def test_trade_sell_with_confirm(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that with --confirm, sell_market is called"""
        monkeypatch.setenv("UPBIT_ACCESS_KEY", "ak")
        monkeypatch.setenv("UPBIT_SECRET_KEY", "sk")

        mock_exchange_instance = MagicMock()
        mock_exchange_instance.sell_market.return_value = {"uuid": "sell-456"}

        with patch("maiupbit.exchange.upbit.UPbitExchange", return_value=mock_exchange_instance):
            from maiupbit.cli import cmd_trade
            cmd_trade(_trade_args(action="sell", amount=0.001, confirm=True))

        mock_exchange_instance.sell_market.assert_called_once_with("KRW-BTC", 0.001)

    def test_trade_unknown_action_exits(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that an unknown action causes the function to exit with code 1"""
        monkeypatch.setenv("UPBIT_ACCESS_KEY", "ak")
        monkeypatch.setenv("UPBIT_SECRET_KEY", "sk")

        mock_exchange_instance = MagicMock()

        with patch("maiupbit.exchange.upbit.UPbitExchange", return_value=mock_exchange_instance):
            from maiupbit.cli import cmd_trade
            with pytest.raises(SystemExit) as exc_info:
                cmd_trade(_trade_args(action="unknown", confirm=True))
        assert exc_info.value.code == 1

    def test_trade_preview_shows_symbol_and_amount(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that the preview shows symbol and amount"""
        monkeypatch.setenv("UPBIT_ACCESS_KEY", "ak")
        monkeypatch.setenv("UPBIT_SECRET_KEY", "sk")

        mock_exchange_instance = MagicMock()
        mock_exchange_instance.get_current_price.return_value = 50_000_000.0

        with patch("maiupbit.exchange.upbit.UPbitExchange", return_value=mock_exchange_instance):
            from maiupbit.cli import cmd_trade
            with pytest.raises(SystemExit):
                cmd_trade(_trade_args(symbol="KRW-ETH", amount=100_000.0, confirm=False))

        captured = capsys.readouterr()
        assert "symbol" in captured.out and "amount" in captured.out


# ---------------------------------------------------------------------------
# TestMain
# ---------------------------------------------------------------------------

class TestMain:
    def test_main_no_command_exits_0(self) -> None:
        """Test that without a subcommand, help is printed and the function exits with code 0"""
        with patch("sys.argv", ["maiupbit"]):
            from maiupbit.cli import main
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_main_analyze_subcommand_dispatches(self) -> None:
        """Test that the analyze subcommand calls cmd_analyze"""
        ohlcv = _make_ohlcv()

        mock_exchange_instance = MagicMock()
        mock_exchange_instance.get_ohlcv.return_value = ohlcv
        mock_exchange_instance.get_current_price.return_value = 0.0

        with patch("sys.argv", ["maiupbit", "analyze", "KRW-BTC", "--format", "json"]):
            with patch("maiupbit.exchange.upbit.UPbitExchange", return_value=mock_exchange_instance):
                from maiupbit.cli import main
                main()  # sys.exit 없이 정상 종료