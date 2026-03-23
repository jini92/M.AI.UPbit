"""Low-level SQLite read/write API for market candle and snapshot data.

Provides idempotent upsert, DataFrame-friendly queries, coverage checks,
and analysis snapshot persistence for decision provenance.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from maiupbit.storage.schema import init_schema

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("data/market_data.db")


class SQLiteStore:
    """SQLite-backed candle storage with idempotent upsert and range queries.

    Args:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def _ensure_schema(self) -> None:
        conn = self._get_conn()
        init_schema(conn)

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    def upsert_candles(self, df: pd.DataFrame, symbol: str, interval: str, source: str = "upbit") -> int:
        """Upsert OHLCV candles into the canonical store.

        Expects a DataFrame with a DatetimeIndex and columns: open, high, low, close, volume.
        The ``value`` column is optional.

        Args:
            df: OHLCV DataFrame (DatetimeIndex).
            symbol: Market symbol, e.g. ``KRW-BTC``.
            interval: Candle interval, e.g. ``day``, ``minute60``.
            source: Data source label.

        Returns:
            Number of rows upserted.
        """
        if df is None or df.empty:
            return 0

        conn = self._get_conn()
        now_utc = datetime.now(timezone.utc).isoformat()
        rows = []
        for ts, row in df.iterrows():
            candle_time = pd.Timestamp(ts).tz_localize(None).isoformat() if pd.Timestamp(ts).tzinfo is None else pd.Timestamp(ts).tz_convert("UTC").tz_localize(None).isoformat()
            rows.append((
                symbol,
                interval,
                candle_time,
                float(row["open"]),
                float(row["high"]),
                float(row["low"]),
                float(row["close"]),
                float(row.get("volume", 0)) if pd.notna(row.get("volume")) else None,
                float(row.get("value", 0)) if pd.notna(row.get("value")) else None,
                source,
                now_utc,
            ))

        conn.executemany(
            """\
            INSERT INTO market_candles
                (symbol, interval, candle_time_utc, open, high, low, close, volume, value, source, ingested_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (symbol, interval, candle_time_utc)
            DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume,
                value = excluded.value,
                source = excluded.source,
                ingested_at_utc = excluded.ingested_at_utc
            """,
            rows,
        )
        conn.commit()
        return len(rows)

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    def query_candles(
        self,
        symbol: str,
        interval: str,
        count: Optional[int] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """Query candles from the store, returned as a DatetimeIndex DataFrame.

        Args:
            symbol: Market symbol.
            interval: Candle interval.
            count: Max rows to return (latest N). Ignored if start/end given.
            start: ISO start time (inclusive).
            end: ISO end time (inclusive).

        Returns:
            OHLCV DataFrame with DatetimeIndex sorted ascending.
        """
        conn = self._get_conn()
        conditions = ["symbol = ?", "interval = ?"]
        params: list = [symbol, interval]

        if start:
            conditions.append("candle_time_utc >= ?")
            params.append(start)
        if end:
            conditions.append("candle_time_utc <= ?")
            # Normalize date-only strings (e.g. "2026-01-20") to end-of-day
            # so that candles stored as "2026-01-20T00:00:00" are included.
            end_str = end
            if len(end_str) == 10:  # "YYYY-MM-DD" format
                end_str = end_str + "T23:59:59"
            params.append(end_str)

        where = " AND ".join(conditions)

        if count and not start:
            # Get latest N candles (optionally up to ``end``)
            sql = (
                f"SELECT * FROM market_candles WHERE {where} "
                f"ORDER BY candle_time_utc DESC LIMIT ?"
            )
            params.append(count)
            df = pd.read_sql_query(sql, conn, params=params)
            df = df.sort_values("candle_time_utc")
        else:
            sql = f"SELECT * FROM market_candles WHERE {where} ORDER BY candle_time_utc ASC"
            df = pd.read_sql_query(sql, conn, params=params)

        if df.empty:
            return pd.DataFrame()

        df.index = pd.to_datetime(df["candle_time_utc"])
        df.index.name = None
        df = df[["open", "high", "low", "close", "volume", "value"]]
        return df

    def get_coverage(self, symbol: str, interval: str) -> tuple[Optional[str], Optional[str], int]:
        """Return (earliest_time, latest_time, row_count) for a symbol/interval.

        Args:
            symbol: Market symbol.
            interval: Candle interval.

        Returns:
            Tuple of (earliest candle time, latest candle time, count).
        """
        conn = self._get_conn()
        row = conn.execute(
            """\
            SELECT MIN(candle_time_utc), MAX(candle_time_utc), COUNT(*)
            FROM market_candles
            WHERE symbol = ? AND interval = ?
            """,
            (symbol, interval),
        ).fetchone()
        return (row[0], row[1], row[2]) if row and row[2] > 0 else (None, None, 0)

    # ------------------------------------------------------------------
    # Ingestion runs
    # ------------------------------------------------------------------

    def start_ingestion_run(self, task: str, symbol: Optional[str] = None, interval: Optional[str] = None) -> str:
        """Record the start of an ingestion run.

        Args:
            task: Run type (``backfill``, ``refresh``, ``warmup``).
            symbol: Optional symbol scope.
            interval: Optional interval scope.

        Returns:
            The run_id (UUID string).
        """
        conn = self._get_conn()
        run_id = str(uuid.uuid4())
        now_utc = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """\
            INSERT INTO ingestion_runs (run_id, started_at_utc, task, symbol, interval, status)
            VALUES (?, ?, ?, ?, ?, 'running')
            """,
            (run_id, now_utc, task, symbol, interval),
        )
        conn.commit()
        return run_id

    def finish_ingestion_run(
        self, run_id: str, rows_written: int = 0, status: str = "ok", error_message: Optional[str] = None
    ) -> None:
        """Record the completion of an ingestion run.

        Args:
            run_id: The run_id returned by ``start_ingestion_run``.
            rows_written: Total rows written.
            status: Final status (``ok``, ``partial``, ``error``).
            error_message: Error details if applicable.
        """
        conn = self._get_conn()
        now_utc = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """\
            UPDATE ingestion_runs
            SET finished_at_utc = ?, rows_written = ?, status = ?, error_message = ?
            WHERE run_id = ?
            """,
            (now_utc, rows_written, status, error_message, run_id),
        )
        conn.commit()

    # ------------------------------------------------------------------
    # Analysis snapshots
    # ------------------------------------------------------------------

    @staticmethod
    def _to_json(obj: Any) -> Optional[str]:
        """Safely serialize an object to a compact JSON string.

        Args:
            obj: Any JSON-serializable object.

        Returns:
            JSON string, or None if obj is None/empty.
        """
        if obj is None:
            return None
        if isinstance(obj, str):
            return obj
        try:
            return json.dumps(obj, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return str(obj)

    def save_snapshot(
        self,
        symbol: str,
        kind: str,
        *,
        trade_id: Optional[str] = None,
        market_data: Any = None,
        indicators: Any = None,
        quant_signals: Any = None,
        llm_result: Any = None,
        knowledge_summary: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """Persist an analysis snapshot for decision provenance.

        Args:
            symbol: Market symbol (e.g. ``KRW-BTC``).
            kind: Snapshot kind (``auto_trade``, ``daily_report``, ``quant``, ``training``).
            trade_id: Optional linked trade ID.
            market_data: Market context dict/object (serialized to JSON).
            indicators: Indicator values dict/object.
            quant_signals: Quant strategy outputs.
            llm_result: LLM decision output.
            knowledge_summary: Mnemo knowledge excerpt.
            provider: LLM provider name (``openai``, ``ollama``).
            model: LLM model name.

        Returns:
            The snapshot_id (UUID string).
        """
        conn = self._get_conn()
        snapshot_id = str(uuid.uuid4())
        now_utc = datetime.now(timezone.utc).isoformat()

        conn.execute(
            """\
            INSERT INTO analysis_snapshots
                (snapshot_id, created_at_utc, symbol, kind, trade_id,
                 market_json, indicators_json, quant_json, llm_json,
                 knowledge_summary, provider, model)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id, now_utc, symbol, kind, trade_id,
                self._to_json(market_data),
                self._to_json(indicators),
                self._to_json(quant_signals),
                self._to_json(llm_result),
                knowledge_summary[:2000] if knowledge_summary else None,
                provider, model,
            ),
        )
        conn.commit()
        logger.debug("Saved analysis snapshot %s for %s/%s", snapshot_id, symbol, kind)
        return snapshot_id

    def query_snapshots(
        self,
        symbol: Optional[str] = None,
        kind: Optional[str] = None,
        trade_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Query analysis snapshots with optional filters.

        Args:
            symbol: Filter by symbol.
            kind: Filter by kind.
            trade_id: Filter by linked trade ID.
            limit: Max rows to return.

        Returns:
            List of snapshot dicts with JSON fields parsed back to objects.
        """
        conn = self._get_conn()
        conditions = []
        params: list = []

        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol)
        if kind:
            conditions.append("kind = ?")
            params.append(kind)
        if trade_id:
            conditions.append("trade_id = ?")
            params.append(trade_id)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = (
            f"SELECT * FROM analysis_snapshots {where} "
            f"ORDER BY created_at_utc DESC LIMIT ?"
        )
        params.append(limit)

        cursor = conn.execute(sql, params)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        results = []
        json_fields = {"market_json", "indicators_json", "quant_json", "llm_json"}
        for row in rows:
            record = dict(zip(columns, row))
            for field in json_fields:
                val = record.get(field)
                if val and isinstance(val, str):
                    try:
                        record[field] = json.loads(val)
                    except (json.JSONDecodeError, ValueError):
                        pass
            results.append(record)
        return results

    def get_snapshot(self, snapshot_id: str) -> Optional[dict]:
        """Retrieve a single snapshot by ID.

        Args:
            snapshot_id: The snapshot UUID.

        Returns:
            Snapshot dict or None if not found.
        """
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM analysis_snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        )
        columns = [desc[0] for desc in cursor.description]
        row = cursor.fetchone()
        if not row:
            return None

        record = dict(zip(columns, row))
        json_fields = {"market_json", "indicators_json", "quant_json", "llm_json"}
        for field in json_fields:
            val = record.get(field)
            if val and isinstance(val, str):
                try:
                    record[field] = json.loads(val)
                except (json.JSONDecodeError, ValueError):
                    pass
        return record
