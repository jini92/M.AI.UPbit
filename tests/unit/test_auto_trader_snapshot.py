"""Test that AutoTrader persists analysis snapshots to SQLite."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from maiupbit.storage.sqlite_store import SQLiteStore
from maiupbit.services.market_data import MarketDataService
from maiupbit.trading.auto_trader import AutoTrader


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    s = SQLiteStore(db_path=tmp_path / "test.db")
    yield s
    s.close()


@pytest.fixture
def wired_exchange(store: SQLiteStore):
    """Build a mock exchange with a real MarketDataService + store attached."""
    exchange = MagicMock()
    exchange.get_current_price.return_value = 50000.0
    exchange.get_portfolio.return_value = {
        "KRW": pd.DataFrame([{"symbol": "KRW", "quantity": 1000000, "current_price": 1, "avg_buy_price": 1}])
    }

    service = MarketDataService(store=store, exchange=exchange)
    exchange._market_data_service = service

    # Make get_ohlcv return a small DataFrame
    idx = pd.date_range("2026-01-01", periods=30, freq="D")
    df = pd.DataFrame(
        {"open": 50000.0, "high": 51000.0, "low": 49000.0, "close": 50500.0, "volume": 100.0},
        index=idx,
    )
    exchange.get_ohlcv.return_value = df
    return exchange


class TestAutoTraderSnapshot:
    def test_execute_trade_saves_snapshot(self, store: SQLiteStore, wired_exchange) -> None:
        """AutoTrader.execute_trade should persist an analysis snapshot."""
        trader = AutoTrader(exchange=wired_exchange)
        result = trader.execute_trade("KRW-BTC", dry_run=True)

        assert "snapshot_id" in result
        assert result["snapshot_id"] is not None

        # Verify it's in the store
        snap = store.get_snapshot(result["snapshot_id"])
        assert snap is not None
        assert snap["symbol"] == "KRW-BTC"
        assert snap["kind"] == "auto_trade"
        assert snap["trade_id"] == result["trade_id"]

    def test_snapshot_contains_market_data(self, store: SQLiteStore, wired_exchange) -> None:
        """Snapshot should contain the market context used for the decision."""
        trader = AutoTrader(exchange=wired_exchange)
        result = trader.execute_trade("KRW-BTC", dry_run=True)

        snap = store.get_snapshot(result["snapshot_id"])
        assert snap["market_json"] is not None
        assert "current_price" in snap["market_json"]

    def test_snapshot_contains_llm_result(self, store: SQLiteStore, wired_exchange) -> None:
        """Snapshot should contain the LLM decision output."""
        trader = AutoTrader(exchange=wired_exchange)
        result = trader.execute_trade("KRW-BTC", dry_run=True)

        snap = store.get_snapshot(result["snapshot_id"])
        # Default fallback LLM result when no LLM is configured
        assert snap["llm_json"] is not None
        assert snap["llm_json"]["decision"] == "hold"

    def test_no_snapshot_when_no_store(self) -> None:
        """When exchange has no MarketDataService, snapshot_id should be None."""
        exchange = MagicMock()
        exchange.get_current_price.return_value = 50000.0
        exchange._market_data_service = None

        idx = pd.date_range("2026-01-01", periods=30, freq="D")
        df = pd.DataFrame(
            {"open": 50000.0, "high": 51000.0, "low": 49000.0, "close": 50500.0, "volume": 100.0},
            index=idx,
        )
        exchange.get_ohlcv.return_value = df

        trader = AutoTrader(exchange=exchange)
        result = trader.execute_trade("KRW-BTC", dry_run=True)

        assert result["snapshot_id"] is None

    def test_query_snapshots_by_trade_id(self, store: SQLiteStore, wired_exchange) -> None:
        """Should be able to look up a snapshot from a trade_id."""
        trader = AutoTrader(exchange=wired_exchange)
        result = trader.execute_trade("KRW-BTC", dry_run=True)

        snapshots = store.query_snapshots(trade_id=result["trade_id"])
        assert len(snapshots) == 1
        assert snapshots[0]["snapshot_id"] == result["snapshot_id"]
