"""Unit tests for maiupbit.storage (schema + sqlite_store)."""

import sqlite3
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from maiupbit.storage.schema import SCHEMA_VERSION, init_schema
from maiupbit.storage.sqlite_store import SQLiteStore


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Return a path for a temporary SQLite database."""
    return tmp_path / "test_market.db"


@pytest.fixture
def store(tmp_db: Path) -> SQLiteStore:
    """Return a fresh SQLiteStore backed by a temp DB."""
    s = SQLiteStore(db_path=tmp_db)
    yield s
    s.close()


@pytest.fixture
def sample_candles() -> pd.DataFrame:
    """Generate a small OHLCV DataFrame with 10 daily candles."""
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
            "value": np.random.randint(1_000_000, 50_000_000, n).astype(float),
        },
        index=dates,
    )


# ------------------------------------------------------------------
# Schema tests
# ------------------------------------------------------------------

class TestSchema:
    def test_init_schema_creates_tables(self, store: SQLiteStore) -> None:
        """Schema init should create market_candles, ingestion_runs, schema_meta."""
        conn = store._get_conn()
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "market_candles" in tables
        assert "ingestion_runs" in tables
        assert "schema_meta" in tables

    def test_schema_version_recorded(self, store: SQLiteStore) -> None:
        conn = store._get_conn()
        row = conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        ).fetchone()
        assert row is not None
        assert row[0] == str(SCHEMA_VERSION)

    def test_idempotent_init(self, tmp_db: Path) -> None:
        """Calling init_schema twice should not error."""
        s1 = SQLiteStore(db_path=tmp_db)
        s2 = SQLiteStore(db_path=tmp_db)
        conn = s2._get_conn()
        tables = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()
        assert tables[0] >= 3
        s1.close()
        s2.close()


# ------------------------------------------------------------------
# Upsert tests
# ------------------------------------------------------------------

class TestUpsert:
    def test_upsert_inserts_new_rows(self, store: SQLiteStore, sample_candles: pd.DataFrame) -> None:
        rows = store.upsert_candles(sample_candles, "KRW-BTC", "day")
        assert rows == 10

    def test_upsert_is_idempotent(self, store: SQLiteStore, sample_candles: pd.DataFrame) -> None:
        """Upserting the same data twice should not create duplicates."""
        store.upsert_candles(sample_candles, "KRW-BTC", "day")
        store.upsert_candles(sample_candles, "KRW-BTC", "day")
        _, _, count = store.get_coverage("KRW-BTC", "day")
        assert count == 10

    def test_upsert_updates_existing(self, store: SQLiteStore, sample_candles: pd.DataFrame) -> None:
        """Upserting with changed close prices should update existing rows."""
        store.upsert_candles(sample_candles, "KRW-BTC", "day")

        modified = sample_candles.copy()
        modified["close"] = modified["close"] + 1000
        store.upsert_candles(modified, "KRW-BTC", "day")

        result = store.query_candles("KRW-BTC", "day")
        assert len(result) == 10
        # Verify close prices were updated
        np.testing.assert_array_almost_equal(
            result["close"].values, modified["close"].values
        )

    def test_upsert_empty_dataframe(self, store: SQLiteStore) -> None:
        rows = store.upsert_candles(pd.DataFrame(), "KRW-BTC", "day")
        assert rows == 0

    def test_upsert_none_dataframe(self, store: SQLiteStore) -> None:
        rows = store.upsert_candles(None, "KRW-BTC", "day")
        assert rows == 0

    def test_upsert_different_symbols(self, store: SQLiteStore, sample_candles: pd.DataFrame) -> None:
        """Same candle times for different symbols should not conflict."""
        store.upsert_candles(sample_candles, "KRW-BTC", "day")
        store.upsert_candles(sample_candles, "KRW-ETH", "day")
        _, _, btc_count = store.get_coverage("KRW-BTC", "day")
        _, _, eth_count = store.get_coverage("KRW-ETH", "day")
        assert btc_count == 10
        assert eth_count == 10

    def test_upsert_different_intervals(self, store: SQLiteStore, sample_candles: pd.DataFrame) -> None:
        """Same symbol with different intervals should not conflict."""
        store.upsert_candles(sample_candles, "KRW-BTC", "day")
        store.upsert_candles(sample_candles, "KRW-BTC", "minute60")
        _, _, day_count = store.get_coverage("KRW-BTC", "day")
        _, _, hour_count = store.get_coverage("KRW-BTC", "minute60")
        assert day_count == 10
        assert hour_count == 10


# ------------------------------------------------------------------
# Query tests
# ------------------------------------------------------------------

class TestQuery:
    def test_query_returns_dataframe_with_ohlcv(self, store: SQLiteStore, sample_candles: pd.DataFrame) -> None:
        store.upsert_candles(sample_candles, "KRW-BTC", "day")
        result = store.query_candles("KRW-BTC", "day")
        assert isinstance(result, pd.DataFrame)
        assert set(result.columns) >= {"open", "high", "low", "close", "volume"}
        assert len(result) == 10

    def test_query_count_limits_rows(self, store: SQLiteStore, sample_candles: pd.DataFrame) -> None:
        store.upsert_candles(sample_candles, "KRW-BTC", "day")
        result = store.query_candles("KRW-BTC", "day", count=5)
        assert len(result) == 5

    def test_query_count_returns_latest(self, store: SQLiteStore, sample_candles: pd.DataFrame) -> None:
        """count=5 should return the 5 most recent candles."""
        store.upsert_candles(sample_candles, "KRW-BTC", "day")
        result = store.query_candles("KRW-BTC", "day", count=5)
        full = store.query_candles("KRW-BTC", "day")
        pd.testing.assert_frame_equal(result, full.tail(5))

    def test_query_empty_symbol(self, store: SQLiteStore) -> None:
        result = store.query_candles("KRW-NONEXISTENT", "day")
        assert result.empty

    def test_query_with_time_range(self, store: SQLiteStore, sample_candles: pd.DataFrame) -> None:
        store.upsert_candles(sample_candles, "KRW-BTC", "day")
        result = store.query_candles(
            "KRW-BTC", "day",
            start="2026-01-03T00:00:00",
            end="2026-01-07T00:00:00",
        )
        assert len(result) == 5

    def test_query_has_datetime_index(self, store: SQLiteStore, sample_candles: pd.DataFrame) -> None:
        store.upsert_candles(sample_candles, "KRW-BTC", "day")
        result = store.query_candles("KRW-BTC", "day")
        assert isinstance(result.index, pd.DatetimeIndex)


# ------------------------------------------------------------------
# Coverage tests
# ------------------------------------------------------------------

class TestCoverage:
    def test_coverage_empty(self, store: SQLiteStore) -> None:
        earliest, latest, count = store.get_coverage("KRW-BTC", "day")
        assert earliest is None
        assert latest is None
        assert count == 0

    def test_coverage_after_insert(self, store: SQLiteStore, sample_candles: pd.DataFrame) -> None:
        store.upsert_candles(sample_candles, "KRW-BTC", "day")
        earliest, latest, count = store.get_coverage("KRW-BTC", "day")
        assert count == 10
        assert earliest is not None
        assert latest is not None
        assert earliest < latest


# ------------------------------------------------------------------
# Ingestion run tests
# ------------------------------------------------------------------

class TestIngestionRuns:
    def test_start_and_finish_run(self, store: SQLiteStore) -> None:
        run_id = store.start_ingestion_run("backfill", "KRW-BTC", "day")
        assert isinstance(run_id, str)
        assert len(run_id) == 36  # UUID length

        store.finish_ingestion_run(run_id, rows_written=100, status="ok")

        conn = store._get_conn()
        row = conn.execute(
            "SELECT status, rows_written FROM ingestion_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        assert row[0] == "ok"
        assert row[1] == 100

    def test_error_run(self, store: SQLiteStore) -> None:
        run_id = store.start_ingestion_run("backfill")
        store.finish_ingestion_run(run_id, status="error", error_message="timeout")

        conn = store._get_conn()
        row = conn.execute(
            "SELECT status, error_message FROM ingestion_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        assert row[0] == "error"
        assert row[1] == "timeout"


# ------------------------------------------------------------------
# Schema migration tests
# ------------------------------------------------------------------

class TestSchemaMigration:
    def test_schema_version_is_2(self, store: SQLiteStore) -> None:
        assert SCHEMA_VERSION == 2

    def test_analysis_snapshots_table_exists(self, store: SQLiteStore) -> None:
        conn = store._get_conn()
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "analysis_snapshots" in tables

    def test_migration_from_v1_adds_snapshots(self, tmp_path: Path) -> None:
        """Simulate a v1 database and verify migration creates analysis_snapshots."""
        db_path = tmp_path / "v1_migrate.db"
        conn = sqlite3.connect(str(db_path))
        # Create only v1 tables manually
        conn.execute("""\
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            )""")
        conn.execute(
            "INSERT INTO schema_meta (key, value) VALUES ('schema_version', '1')"
        )
        conn.execute("""\
            CREATE TABLE IF NOT EXISTS market_candles (
                symbol TEXT NOT NULL, interval TEXT NOT NULL,
                candle_time_utc TEXT NOT NULL, open REAL NOT NULL,
                high REAL NOT NULL, low REAL NOT NULL, close REAL NOT NULL,
                volume REAL, value REAL,
                source TEXT NOT NULL DEFAULT 'upbit',
                ingested_at_utc TEXT NOT NULL,
                PRIMARY KEY (symbol, interval, candle_time_utc)
            )""")
        conn.execute("""\
            CREATE TABLE IF NOT EXISTS ingestion_runs (
                run_id TEXT NOT NULL PRIMARY KEY,
                started_at_utc TEXT NOT NULL, finished_at_utc TEXT,
                task TEXT NOT NULL, symbol TEXT, interval TEXT,
                rows_written INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'running', error_message TEXT
            )""")
        conn.commit()
        conn.close()

        # Now open with SQLiteStore which should run migration
        store = SQLiteStore(db_path=db_path)
        conn = store._get_conn()
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "analysis_snapshots" in tables

        # Version should be updated to 2
        row = conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        ).fetchone()
        assert row[0] == "2"
        store.close()


# ------------------------------------------------------------------
# Analysis snapshot tests
# ------------------------------------------------------------------

class TestAnalysisSnapshots:
    def test_save_snapshot_returns_uuid(self, store: SQLiteStore) -> None:
        sid = store.save_snapshot(
            symbol="KRW-BTC",
            kind="auto_trade",
            market_data={"current_price": 50000},
        )
        assert isinstance(sid, str)
        assert len(sid) == 36

    def test_save_and_query_snapshot(self, store: SQLiteStore) -> None:
        store.save_snapshot(
            symbol="KRW-BTC",
            kind="auto_trade",
            trade_id="trade-123",
            market_data={"current_price": 50000, "indicators": {"rsi": 45}},
            indicators={"rsi_14": 45.0, "sma_20": 49000},
            quant_signals={"momentum": "bullish"},
            llm_result={"decision": "buy", "confidence": 0.8, "reason": "test"},
            knowledge_summary="BTC is strong",
            provider="ollama",
            model="qwen2.5:14b",
        )

        results = store.query_snapshots(symbol="KRW-BTC")
        assert len(results) == 1
        snap = results[0]
        assert snap["symbol"] == "KRW-BTC"
        assert snap["kind"] == "auto_trade"
        assert snap["trade_id"] == "trade-123"
        assert snap["market_json"]["current_price"] == 50000
        assert snap["indicators_json"]["rsi_14"] == 45.0
        assert snap["quant_json"]["momentum"] == "bullish"
        assert snap["llm_json"]["decision"] == "buy"
        assert snap["knowledge_summary"] == "BTC is strong"
        assert snap["provider"] == "ollama"
        assert snap["model"] == "qwen2.5:14b"

    def test_get_snapshot_by_id(self, store: SQLiteStore) -> None:
        sid = store.save_snapshot(
            symbol="KRW-ETH",
            kind="daily_report",
            market_data={"price": 3000},
        )
        snap = store.get_snapshot(sid)
        assert snap is not None
        assert snap["snapshot_id"] == sid
        assert snap["symbol"] == "KRW-ETH"

    def test_get_snapshot_not_found(self, store: SQLiteStore) -> None:
        result = store.get_snapshot("nonexistent-id")
        assert result is None

    def test_query_by_kind(self, store: SQLiteStore) -> None:
        store.save_snapshot(symbol="KRW-BTC", kind="auto_trade")
        store.save_snapshot(symbol="KRW-BTC", kind="daily_report")
        store.save_snapshot(symbol="KRW-ETH", kind="daily_report")

        auto = store.query_snapshots(kind="auto_trade")
        assert len(auto) == 1
        reports = store.query_snapshots(kind="daily_report")
        assert len(reports) == 2

    def test_query_by_trade_id(self, store: SQLiteStore) -> None:
        store.save_snapshot(symbol="KRW-BTC", kind="auto_trade", trade_id="t-1")
        store.save_snapshot(symbol="KRW-BTC", kind="auto_trade", trade_id="t-2")

        results = store.query_snapshots(trade_id="t-1")
        assert len(results) == 1
        assert results[0]["trade_id"] == "t-1"

    def test_query_limit(self, store: SQLiteStore) -> None:
        for i in range(10):
            store.save_snapshot(symbol="KRW-BTC", kind="auto_trade")
        results = store.query_snapshots(limit=3)
        assert len(results) == 3

    def test_snapshot_with_none_fields(self, store: SQLiteStore) -> None:
        """Snapshots with minimal fields should work."""
        sid = store.save_snapshot(symbol="KRW-BTC", kind="quant")
        snap = store.get_snapshot(sid)
        assert snap is not None
        assert snap["trade_id"] is None
        assert snap["market_json"] is None
        assert snap["llm_json"] is None
        assert snap["provider"] is None

    def test_snapshot_json_roundtrip(self, store: SQLiteStore) -> None:
        """Complex nested dicts should serialize and deserialize cleanly."""
        complex_data = {
            "nested": {"deep": [1, 2, 3]},
            "unicode": "test data",
            "number": 123.456,
        }
        sid = store.save_snapshot(
            symbol="KRW-BTC",
            kind="auto_trade",
            market_data=complex_data,
        )
        snap = store.get_snapshot(sid)
        assert snap["market_json"] == complex_data
