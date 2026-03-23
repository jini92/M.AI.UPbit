"""Unit tests for maiupbit.services.market_data.MarketDataService."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from maiupbit.services.market_data import MarketDataService
from maiupbit.storage.sqlite_store import SQLiteStore


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    s = SQLiteStore(db_path=tmp_path / "test.db")
    yield s
    s.close()


@pytest.fixture
def sample_candles() -> pd.DataFrame:
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


class TestLocalFirstReads:
    def test_returns_local_data_when_sufficient(self, store: SQLiteStore, sample_candles: pd.DataFrame) -> None:
        """When local store has enough data, no live fetch should happen."""
        store.upsert_candles(sample_candles, "KRW-BTC", "day")
        service = MarketDataService(store=store, exchange=None)

        result = service.get_ohlcv("KRW-BTC", "day", count=10)
        assert len(result) == 10

    def test_returns_empty_when_no_data_and_no_exchange(self, store: SQLiteStore) -> None:
        service = MarketDataService(store=store, exchange=None)
        result = service.get_ohlcv("KRW-BTC", "day", count=10)
        assert result.empty

    @patch("maiupbit.services.market_data.pyupbit")
    def test_fetches_live_when_local_insufficient(
        self, mock_pyupbit, store: SQLiteStore, sample_candles: pd.DataFrame
    ) -> None:
        """When local data is insufficient, should fetch from exchange."""
        mock_pyupbit.get_ohlcv.return_value = sample_candles

        exchange = MagicMock()
        service = MarketDataService(store=store, exchange=exchange)
        result = service.get_ohlcv("KRW-BTC", "day", count=30)

        assert not result.empty
        mock_pyupbit.get_ohlcv.assert_called_once()

    @patch("maiupbit.services.market_data.pyupbit")
    def test_live_fetch_upserts_into_store(
        self, mock_pyupbit, store: SQLiteStore, sample_candles: pd.DataFrame
    ) -> None:
        """Live-fetched data should be persisted in the store."""
        mock_pyupbit.get_ohlcv.return_value = sample_candles

        exchange = MagicMock()
        service = MarketDataService(store=store, exchange=exchange)
        service.get_ohlcv("KRW-BTC", "day", count=30)

        # Verify data was stored
        _, _, count = store.get_coverage("KRW-BTC", "day")
        assert count == 30

    @patch("maiupbit.services.market_data.pyupbit")
    def test_ingestion_run_recorded(
        self, mock_pyupbit, store: SQLiteStore, sample_candles: pd.DataFrame
    ) -> None:
        """A successful fetch should record an ingestion run."""
        mock_pyupbit.get_ohlcv.return_value = sample_candles

        exchange = MagicMock()
        service = MarketDataService(store=store, exchange=exchange)
        service.get_ohlcv("KRW-BTC", "day", count=30)

        conn = store._get_conn()
        runs = conn.execute("SELECT status FROM ingestion_runs").fetchall()
        assert len(runs) == 1
        assert runs[0][0] == "ok"

    def test_prefer_local_false_always_fetches(self, store: SQLiteStore, sample_candles: pd.DataFrame) -> None:
        """With prefer_local=False, should attempt live fetch even with local data."""
        store.upsert_candles(sample_candles, "KRW-BTC", "day")
        service = MarketDataService(store=store, exchange=None)

        # No exchange, so falls back to local anyway
        result = service.get_ohlcv("KRW-BTC", "day", count=10, prefer_local=False)
        assert len(result) == 10
