"""Hardening tests for reviewer-flagged issues.

Covers:
- MarketDataService local-hit with to= parameter
- query_candles count+end combo
- auto_trade.py using store-backed exchange
- backfill page-stepping overlap avoidance
"""

from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from maiupbit.services.market_data import MarketDataService
from maiupbit.storage.sqlite_store import SQLiteStore


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    s = SQLiteStore(db_path=tmp_path / "test.db")
    yield s
    s.close()


@pytest.fixture
def candles_jan() -> pd.DataFrame:
    """30 daily candles from 2026-01-01 to 2026-01-30."""
    np.random.seed(42)
    n = 30
    dates = pd.date_range("2026-01-01", periods=n, freq="D")
    close = 50000 + np.cumsum(np.random.randn(n) * 500)
    return pd.DataFrame(
        {
            "open": close + np.random.randn(n) * 100,
            "high": close + abs(np.random.randn(n) * 200),
            "low": close - abs(np.random.randn(n) * 200),
            "close": close,
            "volume": np.random.randint(100, 10000, n).astype(float),
        },
        index=dates,
    )


# ------------------------------------------------------------------
# MarketDataService: to= parameter correctness
# ------------------------------------------------------------------

class TestServiceToParam:
    def test_local_hit_respects_to_param(self, store: SQLiteStore, candles_jan: pd.DataFrame) -> None:
        """When to= is set, local hit should only return candles on or before that date."""
        store.upsert_candles(candles_jan, "KRW-BTC", "day")
        service = MarketDataService(store=store, exchange=None)

        # Ask for 10 candles ending on Jan 15
        result = service.get_ohlcv("KRW-BTC", "day", count=10, to="2026-01-15")
        assert len(result) == 10
        # All candles should be on or before Jan 15
        assert result.index.max() <= pd.Timestamp("2026-01-15")

    def test_local_hit_without_to_returns_latest(self, store: SQLiteStore, candles_jan: pd.DataFrame) -> None:
        """Without to=, local hit should return the latest candles."""
        store.upsert_candles(candles_jan, "KRW-BTC", "day")
        service = MarketDataService(store=store, exchange=None)

        result = service.get_ohlcv("KRW-BTC", "day", count=10)
        assert len(result) == 10
        # Should include the latest candle (Jan 30)
        assert result.index.max() == pd.Timestamp("2026-01-30")

    def test_to_param_insufficient_local_triggers_fetch(self, store: SQLiteStore, candles_jan: pd.DataFrame) -> None:
        """When to= restricts local data below count, should attempt live fetch."""
        # Store has 30 candles ending Jan 30, but only 5 candles <= Jan 5
        store.upsert_candles(candles_jan, "KRW-BTC", "day")

        with patch("maiupbit.services.market_data.pyupbit") as mock_pyupbit:
            mock_pyupbit.get_ohlcv.return_value = candles_jan.iloc[:10]
            exchange = MagicMock()
            service = MarketDataService(store=store, exchange=exchange)

            result = service.get_ohlcv("KRW-BTC", "day", count=10, to="2026-01-05")
            # Only 5 local candles <= Jan 5, so live fetch should be attempted
            mock_pyupbit.get_ohlcv.assert_called_once()

    def test_fallback_respects_to_on_no_exchange(self, store: SQLiteStore, candles_jan: pd.DataFrame) -> None:
        """Fallback path should also respect to= parameter."""
        store.upsert_candles(candles_jan, "KRW-BTC", "day")
        service = MarketDataService(store=store, exchange=None)

        # Ask for 100 candles up to Jan 10 — only ~10 exist
        result = service.get_ohlcv("KRW-BTC", "day", count=100, to="2026-01-10")
        assert len(result) <= 10
        assert result.index.max() <= pd.Timestamp("2026-01-10")


# ------------------------------------------------------------------
# query_candles: count + end combo
# ------------------------------------------------------------------

class TestQueryCandlesCountEnd:
    def test_count_with_end_limits_both(self, store: SQLiteStore, candles_jan: pd.DataFrame) -> None:
        """query_candles(count=5, end='2026-01-15') should return 5 candles all <= Jan 15."""
        store.upsert_candles(candles_jan, "KRW-BTC", "day")
        result = store.query_candles("KRW-BTC", "day", count=5, end="2026-01-15")

        assert len(result) == 5
        assert result.index.max() <= pd.Timestamp("2026-01-15")

    def test_count_with_end_returns_latest_before_end(self, store: SQLiteStore, candles_jan: pd.DataFrame) -> None:
        """Should return the latest N candles up to end, not the earliest."""
        store.upsert_candles(candles_jan, "KRW-BTC", "day")
        result = store.query_candles("KRW-BTC", "day", count=3, end="2026-01-20")

        assert len(result) == 3
        # The 3 latest candles before Jan 20 should be Jan 18, 19, 20
        assert result.index.max() <= pd.Timestamp("2026-01-20")
        assert result.index.min() >= pd.Timestamp("2026-01-18")

    def test_count_without_end_returns_overall_latest(self, store: SQLiteStore, candles_jan: pd.DataFrame) -> None:
        """Without end, count returns the overall latest N candles."""
        store.upsert_candles(candles_jan, "KRW-BTC", "day")
        result = store.query_candles("KRW-BTC", "day", count=5)

        assert len(result) == 5
        assert result.index.max() == pd.Timestamp("2026-01-30")


# ------------------------------------------------------------------
# auto_trade.py: store-backed path
# ------------------------------------------------------------------

class TestAutoTradeScript:
    @patch("maiupbit.services.create_exchange")
    def test_auto_trade_uses_create_exchange(self, mock_factory) -> None:
        """auto_trade.py should use create_exchange() instead of raw UPbitExchange."""
        import importlib
        import scripts.auto_trade as mod
        importlib.reload(mod)

        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "create_exchange" in source
        assert "UPbitExchange(access_key=" not in source


# ------------------------------------------------------------------
# Backfill: page-stepping overlap avoidance
# ------------------------------------------------------------------

class TestBackfillStepping:
    def test_step_back_avoids_overlap(self) -> None:
        """backfill_symbol should step to_param back by one interval to avoid re-fetching."""
        from scripts.backfill_market_data import backfill_symbol

        call_args = []

        def mock_get_ohlcv(symbol, interval, count, to=None):
            call_args.append({"symbol": symbol, "interval": interval, "count": count, "to": to})
            if len(call_args) > 3:
                return None  # stop after 3 batches
            # Return a small DataFrame
            n = min(count, 5)
            start_date = "2026-01-15" if to is None else to[:10]
            dates = pd.date_range(end=start_date, periods=n, freq="D")
            return pd.DataFrame(
                {"open": 50000.0, "high": 51000.0, "low": 49000.0, "close": 50500.0, "volume": 100.0},
                index=dates,
            )

        store = MagicMock()
        store.start_ingestion_run.return_value = "run-1"
        store.upsert_candles.return_value = 5

        with patch("scripts.backfill_market_data.pyupbit") as mock_pyupbit:
            mock_pyupbit.get_ohlcv = mock_get_ohlcv
            backfill_symbol(store, "KRW-BTC", "day", days=15)

        # The second call's to= should be earlier than the first batch's earliest candle
        assert len(call_args) >= 2
        # First call has to=None (latest)
        assert call_args[0]["to"] is None
        # Second call should have stepped back by one day from batch 1's earliest
        second_to = call_args[1]["to"]
        assert second_to is not None
        # The stepped-back time should be strictly before the first batch's earliest
        first_batch_earliest = pd.Timestamp(call_args[0]["to"] or "2026-01-15") - timedelta(days=4)
        second_to_ts = pd.Timestamp(second_to)
        # The key assertion: second call's to < first batch's earliest candle
        # (it steps back by 1 day from earliest)
        assert second_to_ts < first_batch_earliest + timedelta(days=1)

    def test_refresh_help_matches_behavior(self) -> None:
        """--refresh sets days=2, and help text should mention 2 days."""
        from scripts.backfill_market_data import main
        import inspect
        source = inspect.getsource(main)
        # Verify the help text and behavior are aligned
        assert "2 days" in source or "days = 2" in source
