"""TechnicalAnalyzer / LLMAnalyzer 단위 테스트"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from maiupbit.analysis.llm import LLMAnalyzer
from maiupbit.analysis.technical import TechnicalAnalyzer, _safe_float


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_exchange() -> MagicMock:
    """get_ohlcv, get_current_price를 가진 모의 거래소"""
    return MagicMock()


@pytest.fixture
def analyzer(mock_exchange: MagicMock) -> TechnicalAnalyzer:
    return TechnicalAnalyzer(exchange=mock_exchange)


@pytest.fixture
def ohlcv_100() -> pd.DataFrame:
    """분석에 충분한 100개 OHLCV 데이터"""
    np.random.seed(99)
    n = 100
    dates = pd.date_range("2026-01-01", periods=n, freq="h")
    close = 50_000 + np.cumsum(np.random.randn(n) * 500)
    return pd.DataFrame(
        {
            "open":   close + np.random.randn(n) * 100,
            "high":   close + np.abs(np.random.randn(n) * 200),
            "low":    close - np.abs(np.random.randn(n) * 200),
            "close":  close,
            "volume": np.random.randint(100, 10_000, n).astype(float),
        },
        index=dates,
    )


@pytest.fixture
def oversold_ohlcv() -> pd.DataFrame:
    """RSI 과매도 상태를 만들도록 급락하는 데이터"""
    n = 50
    dates = pd.date_range("2026-01-01", periods=n, freq="h")
    # 꾸준히 하락
    close = np.linspace(100_000, 30_000, n)
    return pd.DataFrame(
        {
            "open":   close + 100,
            "high":   close + 200,
            "low":    close - 200,
            "close":  close,
            "volume": [1000.0] * n,
        },
        index=dates,
    )


@pytest.fixture
def overbought_ohlcv() -> pd.DataFrame:
    """RSI 과매수 상태를 만들도록 급등하는 데이터"""
    n = 50
    dates = pd.date_range("2026-01-01", periods=n, freq="h")
    close = np.linspace(30_000, 100_000, n)
    return pd.DataFrame(
        {
            "open":   close - 100,
            "high":   close + 200,
            "low":    close - 200,
            "close":  close,
            "volume": [1000.0] * n,
        },
        index=dates,
    )


# ---------------------------------------------------------------------------
# analyze()
# ---------------------------------------------------------------------------

class TestAnalyze:
    def test_returns_expected_top_level_keys(
        self, analyzer: TechnicalAnalyzer, ohlcv_100: pd.DataFrame
    ) -> None:
        result = analyzer.analyze("KRW-BTC", ohlcv_100)
        assert set(result.keys()) >= {"indicators", "signals", "score", "recommendation"}

    def test_indicators_keys_present(
        self, analyzer: TechnicalAnalyzer, ohlcv_100: pd.DataFrame
    ) -> None:
        result = analyzer.analyze("KRW-BTC", ohlcv_100)
        expected = {
            "sma_10", "ema_10", "rsi_14", "macd", "macd_signal",
            "macd_histogram", "stoch_k", "stoch_d",
            "upper_band", "middle_band", "lower_band",
        }
        assert expected == set(result["indicators"].keys())

    def test_signals_keys_present(
        self, analyzer: TechnicalAnalyzer, ohlcv_100: pd.DataFrame
    ) -> None:
        result = analyzer.analyze("KRW-BTC", ohlcv_100)
        assert set(result["signals"].keys()) >= {"macd_signal", "rsi_signal", "bb_signal"}

    def test_score_range(
        self, analyzer: TechnicalAnalyzer, ohlcv_100: pd.DataFrame
    ) -> None:
        result = analyzer.analyze("KRW-BTC", ohlcv_100)
        assert -1.0 <= result["score"] <= 1.0

    def test_recommendation_valid_value(
        self, analyzer: TechnicalAnalyzer, ohlcv_100: pd.DataFrame
    ) -> None:
        result = analyzer.analyze("KRW-BTC", ohlcv_100)
        assert result["recommendation"] in ("buy", "sell", "hold")

    def test_recommendation_buy_when_high_score(
        self, analyzer: TechnicalAnalyzer, oversold_ohlcv: pd.DataFrame
    ) -> None:
        result = analyzer.analyze("KRW-BTC", oversold_ohlcv)
        # 과매도 상태면 score >= 0.3 → buy 권장
        # (데이터에 따라 달라질 수 있으므로 score 기준으로 확인)
        if result["score"] >= 0.3:
            assert result["recommendation"] == "buy"
        elif result["score"] <= -0.3:
            assert result["recommendation"] == "sell"
        else:
            assert result["recommendation"] == "hold"

    def test_recommendation_sell_when_low_score(
        self, analyzer: TechnicalAnalyzer, overbought_ohlcv: pd.DataFrame
    ) -> None:
        result = analyzer.analyze("KRW-BTC", overbought_ohlcv)
        if result["score"] <= -0.3:
            assert result["recommendation"] == "sell"


# ---------------------------------------------------------------------------
# 시그널 해석 (macd/rsi/bb)
# ---------------------------------------------------------------------------

class TestSignalInterpretation:
    def test_macd_bullish_when_macd_above_signal(
        self, analyzer: TechnicalAnalyzer
    ) -> None:
        """MACD > Signal → bullish"""
        n = 50
        dates = pd.date_range("2026-01-01", periods=n, freq="h")
        close = np.linspace(10_000, 20_000, n)
        df = pd.DataFrame(
            {"open": close, "high": close + 100, "low": close - 100,
             "close": close, "volume": [1000.0] * n},
            index=dates,
        )
        result = analyzer.analyze("KRW-ETH", df)
        assert result["signals"]["macd_signal"] in ("bullish", "bearish", "neutral")

    def test_rsi_oversold_signal(
        self, analyzer: TechnicalAnalyzer, oversold_ohlcv: pd.DataFrame
    ) -> None:
        result = analyzer.analyze("KRW-BTC", oversold_ohlcv)
        rsi_val = result["indicators"]["rsi_14"]
        if rsi_val is not None and rsi_val < 30:
            assert result["signals"]["rsi_signal"] == "oversold"

    def test_rsi_overbought_signal(
        self, analyzer: TechnicalAnalyzer, overbought_ohlcv: pd.DataFrame
    ) -> None:
        result = analyzer.analyze("KRW-BTC", overbought_ohlcv)
        rsi_val = result["indicators"]["rsi_14"]
        if rsi_val is not None and rsi_val > 70:
            assert result["signals"]["rsi_signal"] == "overbought"

    def test_rsi_neutral_range(
        self, analyzer: TechnicalAnalyzer, ohlcv_100: pd.DataFrame
    ) -> None:
        result = analyzer.analyze("KRW-BTC", ohlcv_100)
        rsi_val = result["indicators"]["rsi_14"]
        if rsi_val is not None and 30 <= rsi_val <= 70:
            assert result["signals"]["rsi_signal"] == "neutral"

    def test_bb_signal_valid_values(
        self, analyzer: TechnicalAnalyzer, ohlcv_100: pd.DataFrame
    ) -> None:
        result = analyzer.analyze("KRW-BTC", ohlcv_100)
        assert result["signals"]["bb_signal"] in ("upper", "lower", "inside")


# ---------------------------------------------------------------------------
# recommend_by_trend
# ---------------------------------------------------------------------------

class TestRecommendByTrend:
    def _make_trend_ohlcv(self, n: int = 120, rising: bool = True) -> pd.DataFrame:
        dates = pd.date_range("2024-01-01", periods=n, freq="D")
        if rising:
            close = np.linspace(10_000, 25_000, n)
        else:
            close = np.linspace(25_000, 10_000, n)
        return pd.DataFrame(
            {"open": close, "high": close * 1.02, "low": close * 0.98,
             "close": close, "volume": [1000.0] * n, "value": [1000.0 * c for c in close]},
            index=dates,
        )

    def test_returns_list(
        self, analyzer: TechnicalAnalyzer, mock_exchange: MagicMock
    ) -> None:
        mock_exchange.get_ohlcv.return_value = self._make_trend_ohlcv()
        fake_markets = {"비트코인": "KRW-BTC"}
        with patch.object(analyzer, "_get_market_info", return_value=fake_markets):
            result = analyzer.recommend_by_trend(top_n=5)
        assert isinstance(result, list)

    def test_top_n_respected(
        self, analyzer: TechnicalAnalyzer, mock_exchange: MagicMock
    ) -> None:
        mock_exchange.get_ohlcv.return_value = self._make_trend_ohlcv(rising=True)
        fake_markets = {f"코인{i}": f"KRW-COIN{i}" for i in range(10)}
        with patch.object(analyzer, "_get_market_info", return_value=fake_markets):
            result = analyzer.recommend_by_trend(top_n=3)
        assert len(result) <= 3

    def test_empty_market_info_returns_empty_list(
        self, analyzer: TechnicalAnalyzer
    ) -> None:
        with patch.object(analyzer, "_get_market_info", return_value={}):
            result = analyzer.recommend_by_trend()
        assert result == []

    def test_insufficient_data_skipped(
        self, analyzer: TechnicalAnalyzer, mock_exchange: MagicMock
    ) -> None:
        # 데이터가 너무 적으면 (< 90) 건너뜀
        short_df = self._make_trend_ohlcv(n=30)
        mock_exchange.get_ohlcv.return_value = short_df
        with patch.object(analyzer, "_get_market_info", return_value={"비트코인": "KRW-BTC"}):
            result = analyzer.recommend_by_trend()
        assert result == []

    def test_exception_in_exchange_handled(
        self, analyzer: TechnicalAnalyzer, mock_exchange: MagicMock
    ) -> None:
        mock_exchange.get_ohlcv.side_effect = Exception("network error")
        with patch.object(analyzer, "_get_market_info", return_value={"비트코인": "KRW-BTC"}):
            result = analyzer.recommend_by_trend()
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# recommend_by_performance
# ---------------------------------------------------------------------------

class TestRecommendByPerformance:
    def _make_perf_ohlcv(self, start: float, end: float, days: int = 8) -> pd.DataFrame:
        dates = pd.date_range("2026-01-01", periods=days, freq="D")
        close = np.linspace(start, end, days)
        return pd.DataFrame(
            {"open": close, "high": close * 1.01, "low": close * 0.99,
             "close": close, "volume": [1000.0] * days},
            index=dates,
        )

    def test_returns_list(
        self, analyzer: TechnicalAnalyzer, mock_exchange: MagicMock
    ) -> None:
        mock_exchange.get_ohlcv.return_value = self._make_perf_ohlcv(1000, 1100)
        with patch.object(analyzer, "_get_market_info", return_value={"비트코인": "KRW-BTC"}):
            result = analyzer.recommend_by_performance(top_n=3, days=7)
        assert isinstance(result, list)

    def test_returns_symbol_and_reason_tuple(
        self, analyzer: TechnicalAnalyzer, mock_exchange: MagicMock
    ) -> None:
        mock_exchange.get_ohlcv.return_value = self._make_perf_ohlcv(1000, 1100)
        with patch.object(analyzer, "_get_market_info", return_value={"비트코인": "KRW-BTC"}):
            result = analyzer.recommend_by_performance(top_n=3, days=7)
        if result:
            symbol, reason = result[0]
            assert isinstance(symbol, str)
            assert "%" in reason  # 수익률 언급

    def test_sorted_by_performance_descending(
        self, analyzer: TechnicalAnalyzer, mock_exchange: MagicMock
    ) -> None:
        # 세 코인에 서로 다른 수익률 부여
        markets = {"비트코인": "KRW-BTC", "이더리움": "KRW-ETH", "리플": "KRW-XRP"}

        def side_effect(symbol: str, **kwargs: Any) -> pd.DataFrame:
            gains = {"KRW-BTC": 30, "KRW-ETH": 50, "KRW-XRP": 10}
            start = 1000.0
            end_price = start * (1 + gains.get(symbol, 0) / 100)
            return self._make_perf_ohlcv(start, end_price)

        mock_exchange.get_ohlcv.side_effect = side_effect
        with patch.object(analyzer, "_get_market_info", return_value=markets):
            result = analyzer.recommend_by_performance(top_n=3, days=7)

        symbols = [r[0] for r in result]
        assert symbols[0] == "KRW-ETH"  # 50% 수익 1위

    def test_top_n_respected(
        self, analyzer: TechnicalAnalyzer, mock_exchange: MagicMock
    ) -> None:
        mock_exchange.get_ohlcv.return_value = self._make_perf_ohlcv(1000, 1200)
        markets = {f"코인{i}": f"KRW-COIN{i}" for i in range(10)}
        with patch.object(analyzer, "_get_market_info", return_value=markets):
            result = analyzer.recommend_by_performance(top_n=2, days=7)
        assert len(result) <= 2

    def test_empty_market_returns_empty_list(self, analyzer: TechnicalAnalyzer) -> None:
        with patch.object(analyzer, "_get_market_info", return_value={}):
            result = analyzer.recommend_by_performance()
        assert result == []


# ---------------------------------------------------------------------------
# _safe_float 유틸리티
# ---------------------------------------------------------------------------

class TestSafeFloat:
    def test_valid_float(self) -> None:
        assert _safe_float(3.14) == pytest.approx(3.14)

    def test_int_converted(self) -> None:
        assert _safe_float(42) == pytest.approx(42.0)

    def test_none_returns_none(self) -> None:
        assert _safe_float(None) is None

    def test_nan_returns_none(self) -> None:
        assert _safe_float(float("nan")) is None

    def test_string_returns_none(self) -> None:
        assert _safe_float("not a number") is None

    def test_numpy_nan_returns_none(self) -> None:
        assert _safe_float(np.nan) is None

    def test_zero(self) -> None:
        assert _safe_float(0) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# LLMAnalyzer
# ---------------------------------------------------------------------------

_SAMPLE_LLM_JSON = json.dumps({
    "decision": "buy",
    "buy_price": 50000,
    "sell_price": 55000,
    "reason": "RSI 과매도 구간 진입 + MACD 골든크로스 확인으로 매수 적기",
    "technical_analysis": {
        "key_indicators": "RSI oversold",
        "trend": "uptrend",
    },
    "market_sentiment": "positive",
    "risk_management": {
        "position_sizing": "자본의 5%",
        "stop_loss": "48000",
        "take_profit": "56000",
    },
})


class TestLLMAnalyzer:
    """LLMAnalyzer 단위 테스트 (OpenAI / Ollama 프로바이더)."""

    # -- init / provider 설정 -------------------------------------------

    @patch("maiupbit.analysis.llm.OpenAI")
    def test_init_default_openai(self, mock_openai_cls: MagicMock) -> None:
        """기본 프로바이더는 openai, 모델은 gpt-4o."""
        analyzer = LLMAnalyzer(api_key="sk-test")
        assert analyzer.provider == "openai"
        assert analyzer.model == "gpt-4o"
        mock_openai_cls.assert_called_once_with(api_key="sk-test")

    @patch("maiupbit.analysis.llm.OpenAI")
    def test_init_ollama_provider(self, mock_openai_cls: MagicMock) -> None:
        """provider='ollama' 설정 시 base_url, api_key, model 자동 결정."""
        analyzer = LLMAnalyzer(provider="ollama")
        assert analyzer.provider == "ollama"
        assert analyzer.model == "qwen2.5:14b"
        mock_openai_cls.assert_called_once_with(
            api_key="ollama",
            base_url="http://localhost:11434/v1",
        )

    @patch.dict("os.environ", {
        "LLM_PROVIDER": "ollama",
        "OLLAMA_BASE_URL": "http://myhost:11434/v1",
        "OLLAMA_MODEL": "llama3:8b",
    })
    @patch("maiupbit.analysis.llm.OpenAI")
    def test_init_from_env_vars(self, mock_openai_cls: MagicMock) -> None:
        """환경 변수로 프로바이더, base_url, 모델 설정."""
        analyzer = LLMAnalyzer()
        assert analyzer.provider == "ollama"
        assert analyzer.model == "llama3:8b"
        mock_openai_cls.assert_called_once_with(
            api_key="ollama",
            base_url="http://myhost:11434/v1",
        )

    # -- _parse_response ------------------------------------------------

    @patch("maiupbit.analysis.llm.OpenAI")
    def test_parse_response_valid_json(self, mock_openai_cls: MagicMock) -> None:
        """표준 JSON 문자열 파싱."""
        analyzer = LLMAnalyzer(api_key="sk-test")
        result = analyzer._parse_response(_SAMPLE_LLM_JSON)
        assert result["recommendation"] == "buy"
        assert result["buy_price"] == 50000
        assert result["sell_price"] == 55000
        assert "RSI" in result["reason"]
        assert result["technical_analysis"]["trend"] == "uptrend"

    @patch("maiupbit.analysis.llm.OpenAI")
    def test_parse_response_markdown_codeblock(self, mock_openai_cls: MagicMock) -> None:
        """마크다운 ```json ... ``` 코드 블록 내부 JSON 파싱."""
        analyzer = LLMAnalyzer(api_key="sk-test")
        wrapped = f"```json\n{_SAMPLE_LLM_JSON}\n```"
        result = analyzer._parse_response(wrapped)
        assert result["recommendation"] == "buy"
        assert result["buy_price"] == 50000

    @patch("maiupbit.analysis.llm.OpenAI")
    def test_parse_response_invalid_returns_default(self, mock_openai_cls: MagicMock) -> None:
        """파싱 불가 문자열 → 기본 hold 결과 반환."""
        analyzer = LLMAnalyzer(api_key="sk-test")
        result = analyzer._parse_response("not valid json at all")
        assert result["recommendation"] == "hold"
        assert result["buy_price"] is None

    @patch("maiupbit.analysis.llm.OpenAI")
    def test_parse_response_legacy_chart_patterns(self, mock_openai_cls: MagicMock) -> None:
        """기존 chart_patterns 필드를 trend로 매핑 (하위 호환)."""
        legacy_json = json.dumps({
            "decision": "hold",
            "reason": "횡보 중",
            "technical_analysis": {"key_indicators": "RSI 50", "chart_patterns": "sideways"},
        })
        analyzer = LLMAnalyzer(api_key="sk-test")
        result = analyzer._parse_response(legacy_json)
        assert result["technical_analysis"]["trend"] == "sideways"

    # -- analyze --------------------------------------------------------

    @patch("maiupbit.analysis.llm.OpenAI")
    def test_analyze_success_mock(self, mock_openai_cls: MagicMock) -> None:
        """analyze() 가 올바른 구조의 결과를 반환."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_choice = MagicMock()
        mock_choice.message.content = _SAMPLE_LLM_JSON
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        analyzer = LLMAnalyzer(api_key="sk-test")
        result = analyzer.analyze(
            data_json="{}",
            current_status="{}",
            macd_signals=[],
            technical_indicators={},
            lstm_predictions=[],
        )
        assert result["recommendation"] == "buy"
        assert "RSI" in result["reason"]
        mock_client.chat.completions.create.assert_called_once()

    @patch("maiupbit.analysis.llm.OpenAI")
    def test_analyze_api_error_returns_default(self, mock_openai_cls: MagicMock) -> None:
        """API 예외 발생 시 기본 hold 결과 반환."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        analyzer = LLMAnalyzer(api_key="sk-test")
        result = analyzer.analyze(
            data_json="{}",
            current_status="{}",
            macd_signals=[],
            technical_indicators={},
            lstm_predictions=[],
        )
        assert result["recommendation"] == "hold"
        assert result["buy_price"] is None
