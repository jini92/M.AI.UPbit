"""Unit tests for maiupbit.services.create_exchange factory."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

from maiupbit.services import create_exchange
from maiupbit.services.market_data import MarketDataService


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


class TestCreateExchange:
    def test_returns_exchange_with_service(self, tmp_path: Path) -> None:
        """Factory should return an exchange with MarketDataService attached."""
        db_path = str(tmp_path / "test.db")
        exchange = create_exchange(db_path=db_path)
        assert exchange._market_data_service is not None
        assert isinstance(exchange._market_data_service, MarketDataService)

    def test_exchange_get_ohlcv_uses_local_store(
        self, tmp_path: Path, sample_candles: pd.DataFrame,
    ) -> None:
        """When local store has data, exchange.get_ohlcv should return it without live fetch."""
        db_path = str(tmp_path / "test.db")
        exchange = create_exchange(db_path=db_path)

        # Pre-populate the store
        store = exchange._market_data_service.store
        store.upsert_candles(sample_candles, "KRW-BTC", "day")

        with patch("maiupbit.services.market_data.pyupbit") as mock_pyupbit:
            result = exchange.get_ohlcv("KRW-BTC", "day", count=10)
            # Should NOT call pyupbit because local data is sufficient
            mock_pyupbit.get_ohlcv.assert_not_called()
            assert len(result) == 10

    @patch("maiupbit.services.market_data.pyupbit")
    def test_exchange_fetches_live_when_store_empty(
        self, mock_pyupbit, tmp_path: Path, sample_candles: pd.DataFrame,
    ) -> None:
        """When local store is empty, should fall back to live fetch."""
        mock_pyupbit.get_ohlcv.return_value = sample_candles
        db_path = str(tmp_path / "test.db")
        exchange = create_exchange(db_path=db_path)

        result = exchange.get_ohlcv("KRW-BTC", "day", count=30)
        mock_pyupbit.get_ohlcv.assert_called_once()
        assert not result.empty

    def test_factory_without_api_keys(self, tmp_path: Path) -> None:
        """Factory should work without API keys (read-only mode)."""
        db_path = str(tmp_path / "test.db")
        exchange = create_exchange(db_path=db_path)
        assert exchange._upbit is None  # No API keys -> no auth client
        assert exchange._market_data_service is not None


class TestScriptWiring:
    """Verify scripts use create_exchange and thus the local-first path."""

    @patch("maiupbit.services.market_data.pyupbit")
    @patch("maiupbit.exchange.upbit.pyupbit")
    def test_monitor_uses_local_first_path(
        self, mock_exchange_pyupbit, mock_service_pyupbit,
        tmp_path: Path, sample_candles: pd.DataFrame,
    ) -> None:
        """Monitor script should read through MarketDataService."""
        from maiupbit.storage.sqlite_store import SQLiteStore
        from maiupbit.services.market_data import MarketDataService
        from maiupbit.exchange.upbit import UPbitExchange

        db_path = str(tmp_path / "monitor_test.db")
        store = SQLiteStore(db_path=db_path)
        store.upsert_candles(sample_candles.tail(5), "KRW-BTC", "day")

        hourly = sample_candles.copy()
        hourly.index = pd.date_range("2026-01-01", periods=30, freq="h")
        store.upsert_candles(hourly, "KRW-BTC", "minute60")

        exchange = UPbitExchange()
        service = MarketDataService(store=store, exchange=exchange)
        exchange._market_data_service = service

        # Patch at the source so the lazy import picks it up
        with patch("maiupbit.services.create_exchange", return_value=exchange):
            import scripts.monitor
            result = scripts.monitor.monitor(symbols=["KRW-BTC"])
            assert "status" in result
            # pyupbit should NOT be called for OHLCV — local data was used
            mock_service_pyupbit.get_ohlcv.assert_not_called()

        store.close()
