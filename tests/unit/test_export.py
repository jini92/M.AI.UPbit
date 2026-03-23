"""Unit tests for scripts/export_market_data.py export functionality."""

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from maiupbit.storage.sqlite_store import SQLiteStore


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    s = SQLiteStore(db_path=tmp_path / "test.db")
    yield s
    s.close()


@pytest.fixture
def sample_candles() -> pd.DataFrame:
    np.random.seed(42)
    n = 10
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


@pytest.fixture
def populated_store(store: SQLiteStore, sample_candles: pd.DataFrame) -> SQLiteStore:
    """Store with candles and snapshots pre-loaded."""
    store.upsert_candles(sample_candles, "KRW-BTC", "day")
    store.save_snapshot(
        symbol="KRW-BTC",
        kind="auto_trade",
        trade_id="t-1",
        market_data={"price": 50000},
        indicators={"rsi": 45},
        llm_result={"decision": "hold"},
    )
    store.save_snapshot(
        symbol="KRW-BTC",
        kind="daily_report",
        market_data={"price": 50500},
        indicators={"rsi": 48},
    )
    return store


class TestExportCandles:
    def test_export_csv(self, populated_store: SQLiteStore, tmp_path: Path) -> None:
        """Candle export to CSV should produce a valid file."""
        out_dir = tmp_path / "out"
        df = populated_store.query_candles("KRW-BTC", "day")
        assert not df.empty

        out_dir.mkdir()
        out_path = out_dir / "test_candles.csv"
        df.to_csv(str(out_path))

        # Verify file is readable and has correct row count
        loaded = pd.read_csv(str(out_path), index_col=0, parse_dates=True)
        assert len(loaded) == 10
        assert set(loaded.columns) >= {"open", "high", "low", "close", "volume"}

    def test_export_empty_returns_empty_df(self, store: SQLiteStore) -> None:
        """Exporting non-existent data should return empty."""
        df = store.query_candles("KRW-NONEXISTENT", "day")
        assert df.empty


class TestExportSnapshots:
    def test_export_snapshots_csv(self, populated_store: SQLiteStore, tmp_path: Path) -> None:
        """Snapshot export to CSV should produce a valid file."""
        snapshots = populated_store.query_snapshots(symbol="KRW-BTC")
        assert len(snapshots) == 2

        # Flatten and write like the export script does
        rows = []
        for snap in snapshots:
            flat = {}
            for key, val in snap.items():
                if isinstance(val, dict):
                    flat[key] = json.dumps(val, ensure_ascii=False, default=str)
                else:
                    flat[key] = val
            rows.append(flat)

        df = pd.DataFrame(rows)
        out_path = tmp_path / "snapshots.csv"
        df.to_csv(str(out_path), index=False)

        loaded = pd.read_csv(str(out_path))
        assert len(loaded) == 2
        assert "snapshot_id" in loaded.columns
        assert "symbol" in loaded.columns
        assert "kind" in loaded.columns

    def test_snapshot_csv_json_fields_are_strings(self, populated_store: SQLiteStore) -> None:
        """JSON fields should be serialized as strings in export."""
        snapshots = populated_store.query_snapshots(symbol="KRW-BTC")
        for snap in snapshots:
            # When exported, dicts get serialized to JSON strings
            if snap["market_json"] is not None:
                serialized = json.dumps(snap["market_json"], ensure_ascii=False, default=str)
                assert isinstance(serialized, str)
                # Verify round-trip
                parsed = json.loads(serialized)
                assert parsed == snap["market_json"]

    def test_filter_by_kind(self, populated_store: SQLiteStore) -> None:
        auto = populated_store.query_snapshots(kind="auto_trade")
        assert len(auto) == 1
        assert auto[0]["kind"] == "auto_trade"

    def test_filter_by_trade_id(self, populated_store: SQLiteStore) -> None:
        results = populated_store.query_snapshots(trade_id="t-1")
        assert len(results) == 1
        assert results[0]["trade_id"] == "t-1"

    def test_export_empty_snapshots(self, store: SQLiteStore) -> None:
        results = store.query_snapshots(symbol="KRW-NONEXISTENT")
        assert len(results) == 0
