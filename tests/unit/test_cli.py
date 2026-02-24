"""CLI 커맨드 단위 테스트"""
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
# 헬퍼 - 테스트용 OHLCV DataFrame
# ---------------------------------------------------------------------------

def _make_ohlcv(n: int = 50) -> pd.DataFrame:
    """테스트용 OHLCV DataFrame (지표 계산에 필요한 컬럼 포함)"""
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
# Note: CLI 함수 내부에서 `from maiupbit.exchange.upbit import UPbitExchange`
# 형태로 로컬 임포트하므로, 소스 모듈에서 패치해야 합니다.
# ---------------------------------------------------------------------------

class TestCmdAnalyze:
    def test_analyze_json_output(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """정상 실행 후 JSON 출력 확인"""
        ohlcv = _make_ohlcv()

        mock_exchange_instance = MagicMock()
        mock_exchange_instance.get_ohlcv.return_value = ohlcv
        mock_exchange_instance.get_current_price.return_value = 55_000_000.0

        mock_analyze_result = {
            "indicators": {"rsi_14": 55.0, "macd": 100.0, "macd_signal": 90.0},
            "signals": {"macd_signal": "bullish", "rsi_signal": "neutral", "bb_signal": "inside"},
            "score": 0.5,
            "recommendation": "buy",
        }

        # 로컬 임포트이므로 소스 모듈에서 패치
        with patch("maiupbit.exchange.upbit.UPbitExchange", return_value=mock_exchange_instance):
            with patch("maiupbit.analysis.technical.TechnicalAnalyzer") as mock_analyzer_cls:
                mock_analyzer_instance = MagicMock()
                mock_analyzer_instance.analyze.return_value = mock_analyze_result
                mock_analyzer_cls.return_value = mock_analyzer_instance

                from maiupbit.cli import cmd_analyze
                cmd_analyze(_analyze_args(format="json"))

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["recommendation"] == "buy"
        assert output["current_price"] == 55_000_000.0

    def test_analyze_text_output(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """text 포맷 출력 확인"""
        ohlcv = _make_ohlcv()

        mock_exchange_instance = MagicMock()
        mock_exchange_instance.get_ohlcv.return_value = ohlcv
        mock_exchange_instance.get_current_price.return_value = 45_000_000.0

        mock_analyze_result = {
            "indicators": {"rsi": 60.0},
            "signals": {"macd": "bullish"},
            "score": 0.4,
            "recommendation": "hold",
        }

        with patch("maiupbit.exchange.upbit.UPbitExchange", return_value=mock_exchange_instance):
            with patch("maiupbit.analysis.technical.TechnicalAnalyzer") as mock_analyzer_cls:
                mock_analyzer_instance = MagicMock()
                mock_analyzer_instance.analyze.return_value = mock_analyze_result
                mock_analyzer_cls.return_value = mock_analyzer_instance

                from maiupbit.cli import cmd_analyze
                cmd_analyze(_analyze_args(format="text"))

        captured = capsys.readouterr()
        assert "KRW-BTC" in captured.out
        assert "45,000,000" in captured.out

    def test_analyze_exits_on_none_data(self) -> None:
        """데이터 조회 실패 시 sys.exit(1)"""
        mock_exchange_instance = MagicMock()
        mock_exchange_instance.get_ohlcv.return_value = None  # None 반환 → 오류

        with patch("maiupbit.exchange.upbit.UPbitExchange", return_value=mock_exchange_instance):
            from maiupbit.cli import cmd_analyze
            with pytest.raises(SystemExit) as exc_info:
                cmd_analyze(_analyze_args())
        assert exc_info.value.code == 1

    def test_analyze_calls_get_ohlcv_twice(self) -> None:
        """daily + hourly 두 번 호출 확인"""
        ohlcv = _make_ohlcv()

        mock_exchange_instance = MagicMock()
        mock_exchange_instance.get_ohlcv.return_value = ohlcv
        mock_exchange_instance.get_current_price.return_value = 0.0

        with patch("maiupbit.exchange.upbit.UPbitExchange", return_value=mock_exchange_instance):
            with patch("maiupbit.analysis.technical.TechnicalAnalyzer") as mock_analyzer_cls:
                mock_analyzer_cls.return_value.analyze.return_value = {
                    "indicators": {}, "signals": {}, "score": 0.0, "recommendation": "hold"
                }
                from maiupbit.cli import cmd_analyze
                cmd_analyze(_analyze_args())

        assert mock_exchange_instance.get_ohlcv.call_count == 2


# ---------------------------------------------------------------------------
# cmd_portfolio
# ---------------------------------------------------------------------------

class TestCmdPortfolio:
    def test_portfolio_exits_without_api_keys(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """API 키 없으면 sys.exit(1)"""
        monkeypatch.delenv("UPBIT_ACCESS_KEY", raising=False)
        monkeypatch.delenv("UPBIT_SECRET_KEY", raising=False)

        from maiupbit.cli import cmd_portfolio
        with pytest.raises(SystemExit) as exc_info:
            cmd_portfolio(_portfolio_args())
        assert exc_info.value.code == 1

    def test_portfolio_error_message_without_keys(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """에러 메시지에 'error' 키 포함 확인"""
        monkeypatch.delenv("UPBIT_ACCESS_KEY", raising=False)
        monkeypatch.delenv("UPBIT_SECRET_KEY", raising=False)

        from maiupbit.cli import cmd_portfolio
        with pytest.raises(SystemExit):
            cmd_portfolio(_portfolio_args(format="json"))

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "error" in output

    def test_portfolio_runs_with_api_keys(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """API 키가 있으면 포트폴리오 출력"""
        monkeypatch.setenv("UPBIT_ACCESS_KEY", "fake_access")
        monkeypatch.setenv("UPBIT_SECRET_KEY", "fake_secret")

        mock_exchange_instance = MagicMock()
        mock_exchange_instance.get_portfolio.return_value = {
            "KRW": pd.DataFrame([{
                "asset_type": "Cash", "symbol": "KRW", "currency": "KRW",
                "quantity": 100_000.0, "current_price": 1.0,
                "avg_buy_price": 1.0, "value": 100_000.0, "pnl": 0.0,
            }]),
            "BTC": pd.DataFrame(),
            "USDT": pd.DataFrame(),
        }

        # 소스 모듈에서 패치
        with patch("maiupbit.exchange.upbit.UPbitExchange", return_value=mock_exchange_instance):
            from maiupbit.cli import cmd_portfolio
            cmd_portfolio(_portfolio_args(format="json"))

        # 예외 없이 실행되면 통과
        assert mock_exchange_instance.get_portfolio.called


# ---------------------------------------------------------------------------
# cmd_trade
# ---------------------------------------------------------------------------

class TestCmdTrade:
    def test_trade_preview_without_confirm(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--confirm 없으면 미리보기만 출력하고 sys.exit(0)"""
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
        """API 키 없으면 sys.exit(1)"""
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
        """--confirm 있으면 buy_market 호출"""
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
        """--confirm 있으면 sell_market 호출"""
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
        """알 수 없는 action → sys.exit(1)"""
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
        """미리보기에 심볼 및 금액 표시"""
        monkeypatch.setenv("UPBIT_ACCESS_KEY", "ak")
        monkeypatch.setenv("UPBIT_SECRET_KEY", "sk")

        mock_exchange_instance = MagicMock()
        mock_exchange_instance.get_current_price.return_value = 50_000_000.0

        with patch("maiupbit.exchange.upbit.UPbitExchange", return_value=mock_exchange_instance):
            from maiupbit.cli import cmd_trade
            with pytest.raises(SystemExit):
                cmd_trade(_trade_args(symbol="KRW-ETH", amount=100_000.0, confirm=False))

        captured = capsys.readouterr()
        assert "KRW-ETH" in captured.out


# ---------------------------------------------------------------------------
# main() argparse 통합 테스트
# ---------------------------------------------------------------------------

class TestMain:
    def test_main_no_command_exits_0(self) -> None:
        """서브커맨드 없으면 help 출력 후 sys.exit(0)"""
        with patch("sys.argv", ["maiupbit"]):
            from maiupbit.cli import main
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_main_analyze_subcommand_dispatches(self) -> None:
        """analyze 서브커맨드가 cmd_analyze를 호출하는지 확인"""
        ohlcv = _make_ohlcv()

        mock_exchange_instance = MagicMock()
        mock_exchange_instance.get_ohlcv.return_value = ohlcv
        mock_exchange_instance.get_current_price.return_value = 0.0

        with patch("sys.argv", ["maiupbit", "analyze", "KRW-BTC", "--format", "json"]):
            with patch("maiupbit.exchange.upbit.UPbitExchange", return_value=mock_exchange_instance):
                with patch("maiupbit.analysis.technical.TechnicalAnalyzer") as mock_analyzer_cls:
                    mock_analyzer_cls.return_value.analyze.return_value = {
                        "indicators": {}, "signals": {}, "score": 0.0, "recommendation": "hold"
                    }
                    from maiupbit.cli import main
                    main()  # sys.exit 없이 정상 종료
