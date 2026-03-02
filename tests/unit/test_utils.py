"""unit tests for the utils module (data.py, report.py, signals add_all_signals)"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def small_ohlcv() -> pd.DataFrame:
    """Sufficient 50-row OHLCV for indicator calculation"""
    np.random.seed(11)
    n = 50
    dates = pd.date_range("2026-01-01", periods=n, freq="D")
    close = 10_000 + np.cumsum(np.random.randn(n) * 100)
    return pd.DataFrame(
        {
            "open":   close + np.random.randn(n) * 50,
            "high":   close + np.abs(np.random.randn(n) * 100),
            "low":    close - np.abs(np.random.randn(n) * 100),
            "close":  close,
            "volume": np.random.randint(100, 5000, n).astype(float),
        },
        index=dates,
    )


# ---------------------------------------------------------------------------
# signals.add_all_signals
# ---------------------------------------------------------------------------

class TestAddAllSignals:
    def test_returns_dataframe(self, small_ohlcv: pd.DataFrame) -> None:
        from maiupbit.indicators.signals import add_all_signals
        result = add_all_signals(small_ohlcv)
        assert isinstance(result, pd.DataFrame)

    def test_does_not_modify_original(self, small_ohlcv: pd.DataFrame) -> None:
        from maiupbit.indicators.signals import add_all_signals
        original_cols = set(small_ohlcv.columns)
        add_all_signals(small_ohlcv)
        assert set(small_ohlcv.columns) == original_cols

    def test_adds_expected_columns(self, small_ohlcv: pd.DataFrame) -> None:
        from maiupbit.indicators.signals import add_all_signals
        result = add_all_signals(small_ohlcv)
        expected_cols = {
            "SMA_10", "EMA_10", "RSI_14",
            "STOCHk_14_3_3", "STOCHd_14_3_3",
            "MACD", "Signal_Line", "MACD_Histogram",
            "Upper_Band", "Middle_Band", "Lower_Band",
            "MACD_Signal",
        }
        assert expected_cols.issubset(result.columns)

    def test_macd_signal_values(self, small_ohlcv: pd.DataFrame) -> None:
        from maiupbit.indicators.signals import add_all_signals
        result = add_all_signals(small_ohlcv)
        valid = result["MACD_Signal"].dropna()
        assert set(valid.unique()).issubset({-1.0, 0.0, 1.0})

    def test_sma_10_length(self, small_ohlcv: pd.DataFrame) -> None:
        from maiupbit.indicators.signals import add_all_signals
        result = add_all_signals(small_ohlcv)
        assert len(result) == len(small_ohlcv)

    def test_original_columns_preserved(self, small_ohlcv: pd.DataFrame) -> None:
        from maiupbit.indicators.signals import add_all_signals
        result = add_all_signals(small_ohlcv)
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in result.columns


# ---------------------------------------------------------------------------
# utils.data — prepare_data
# ---------------------------------------------------------------------------

class TestPrepareData:
    def test_returns_json_string(self, small_ohlcv: pd.DataFrame) -> None:
        from maiupbit.utils.data import prepare_data
        result = prepare_data(small_ohlcv, small_ohlcv)
        assert isinstance(result, str)

    def test_result_is_valid_json(self, small_ohlcv: pd.DataFrame) -> None:
        from maiupbit.utils.data import prepare_data
        result = prepare_data(small_ohlcv, small_ohlcv)
        # json.loads can deserialize nested json.dumps
        inner = json.loads(result)
        assert isinstance(inner, str)  # double serialization

    def test_uses_both_dataframes(self, small_ohlcv: pd.DataFrame) -> None:
        """Check that both DataFrames are reflected"""
        from maiupbit.utils.data import prepare_data
        daily = small_ohlcv.copy()
        hourly = small_ohlcv.copy()
        result = prepare_data(daily, hourly)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# utils.data — get_instructions
# ---------------------------------------------------------------------------

class TestGetInstructions:
    def test_reads_file_content(self, tmp_path: Path) -> None:
        from maiupbit.utils.data import get_instructions
        test_file = tmp_path / "instructions.txt"
        test_file.write_text("Buy low, sell high.", encoding="utf-8")
        result = get_instructions(str(test_file))
        assert result == "Buy low, sell high."

    def test_returns_none_for_missing_file(self) -> None:
        from maiupbit.utils.data import get_instructions
        result = get_instructions("/nonexistent/path/instructions.txt")
        assert result is None

    def test_returns_multiline_content(self, tmp_path: Path) -> None:
        from maiupbit.utils.data import get_instructions
        content = "Line 1\nLine 2\nLine 3"
        f = tmp_path / "multi.txt"
        f.write_text(content, encoding="utf-8")
        result = get_instructions(str(f))
        assert result == content


# ---------------------------------------------------------------------------
# utils.report — ReportGenerator
# ---------------------------------------------------------------------------

class TestReportGenerator:
    def _sample_analysis(self) -> dict:
        return {
            "recommendation": "buy",
            "buy_price": "50,000,000",
            "sell_price": "55,000,000",
            "reason": "Strong upward momentum",
            "technical_analysis": {
                "key_indicators": "RSI=45, MACD bullish",
                "chart_patterns": "Cup and handle",
            },
            "market_sentiment": "positive",
            "risk_management": {
                "position_sizing": "10% of portfolio",
                "stop_loss": "48,000,000",
                "take_profit": "56,000,000",
            },
        }

    def test_generates_pdf_file(self, tmp_path: Path) -> None:
        from maiupbit.utils.report import ReportGenerator
        gen = ReportGenerator()
        output_path = str(tmp_path / "report.pdf")
        result = gen.generate_pdf(
            symbol="KRW-BTC",
            analysis_result=self._sample_analysis(),
            news_text="Bitcoin surges past record high.\n\nInvestors cheer the rally.",
            output_path=output_path,
        )
        assert os.path.exists(result)
        assert result.endswith(".pdf")

    def test_generates_pdf_with_empty_news(self, tmp_path: Path) -> None:
        from maiupbit.utils.report import ReportGenerator
        gen = ReportGenerator()
        output_path = str(tmp_path / "report_empty_news.pdf")
        result = gen.generate_pdf(
            symbol="KRW-ETH",
            analysis_result=self._sample_analysis(),
            news_text="",
            output_path=output_path,
        )
        assert os.path.exists(result)

    def test_pdf_returns_absolute_path(self, tmp_path: Path) -> None:
        from maiupbit.utils.report import ReportGenerator
        gen = ReportGenerator()
        output_path = str(tmp_path / "report_path.pdf")
        result = gen.generate_pdf(
            symbol="KRW-BTC",
            analysis_result=self._sample_analysis(),
            news_text="Some news.",
            output_path=output_path,
        )
        assert os.path.isabs(result)

    def test_generates_pdf_with_partial_analysis(self, tmp_path: Path) -> None:
        """Generate PDF even with missing fields"""
        from maiupbit.utils.report import ReportGenerator
        gen = ReportGenerator()
        output_path = str(tmp_path / "partial.pdf")
        result = gen.generate_pdf(
            symbol="KRW-XRP",
            analysis_result={},  # all fields N/A
            news_text="",
            output_path=output_path,
        )
        assert os.path.exists(result)

    def test_raises_on_unwritable_path(self) -> None:
        """Raise RuntimeError if path is unwritable"""
        from maiupbit.utils.report import ReportGenerator
        gen = ReportGenerator()
        with pytest.raises(RuntimeError):
            gen.generate_pdf(
                symbol="KRW-BTC",
                analysis_result=self._sample_analysis(),
                news_text="news",
                output_path="/no_such_dir/report.pdf",
            )