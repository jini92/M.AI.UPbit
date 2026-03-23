"""SQLite schema creation and migration for market data storage.

Tables:
    market_candles      — canonical OHLCV store
    ingestion_runs      — observability for backfills and refreshes
    analysis_snapshots  — decision provenance (analysis context at decision time)
"""

SCHEMA_VERSION = 2

MARKET_CANDLES_DDL = """\
CREATE TABLE IF NOT EXISTS market_candles (
    symbol          TEXT    NOT NULL,
    interval        TEXT    NOT NULL,
    candle_time_utc TEXT    NOT NULL,
    open            REAL    NOT NULL,
    high            REAL    NOT NULL,
    low             REAL    NOT NULL,
    close           REAL    NOT NULL,
    volume          REAL,
    value           REAL,
    source          TEXT    NOT NULL DEFAULT 'upbit',
    ingested_at_utc TEXT    NOT NULL,
    PRIMARY KEY (symbol, interval, candle_time_utc)
);
"""

MARKET_CANDLES_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_candles_symbol_interval "
    "ON market_candles (symbol, interval, candle_time_utc);",
]

INGESTION_RUNS_DDL = """\
CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id          TEXT    NOT NULL PRIMARY KEY,
    started_at_utc  TEXT    NOT NULL,
    finished_at_utc TEXT,
    task            TEXT    NOT NULL,
    symbol          TEXT,
    interval        TEXT,
    rows_written    INTEGER DEFAULT 0,
    status          TEXT    NOT NULL DEFAULT 'running',
    error_message   TEXT
);
"""

ANALYSIS_SNAPSHOTS_DDL = """\
CREATE TABLE IF NOT EXISTS analysis_snapshots (
    snapshot_id         TEXT    NOT NULL PRIMARY KEY,
    created_at_utc      TEXT    NOT NULL,
    symbol              TEXT    NOT NULL,
    kind                TEXT    NOT NULL,
    trade_id            TEXT,
    market_json         TEXT,
    indicators_json     TEXT,
    quant_json          TEXT,
    llm_json            TEXT,
    knowledge_summary   TEXT,
    provider            TEXT,
    model               TEXT
);
"""

ANALYSIS_SNAPSHOTS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_snapshots_symbol "
    "ON analysis_snapshots (symbol, kind, created_at_utc);",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_trade_id "
    "ON analysis_snapshots (trade_id);",
]

SCHEMA_META_DDL = """\
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

ALL_DDL = [
    MARKET_CANDLES_DDL,
    *MARKET_CANDLES_INDEXES,
    INGESTION_RUNS_DDL,
    ANALYSIS_SNAPSHOTS_DDL,
    *ANALYSIS_SNAPSHOTS_INDEXES,
    SCHEMA_META_DDL,
]

# Migrations keyed by target version.  Each entry is a list of SQL statements
# that bring the schema from (version - 1) to version.
MIGRATIONS = {
    2: [
        ANALYSIS_SNAPSHOTS_DDL,
        *ANALYSIS_SNAPSHOTS_INDEXES,
    ],
}


def init_schema(conn) -> None:
    """Create all tables and indexes idempotently, then run any pending migrations.

    Args:
        conn: sqlite3 connection object.
    """
    cursor = conn.cursor()
    for ddl in ALL_DDL:
        cursor.execute(ddl)

    # Run incremental migrations for existing databases
    _run_migrations(conn)

    cursor.execute(
        "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )
    conn.commit()


def _run_migrations(conn) -> None:
    """Apply any pending migrations based on stored schema_version.

    Args:
        conn: sqlite3 connection object.
    """
    cursor = conn.cursor()
    row = cursor.execute(
        "SELECT value FROM schema_meta WHERE key = 'schema_version'"
    ).fetchone()
    current = int(row[0]) if row else 1

    for target in sorted(MIGRATIONS.keys()):
        if target > current:
            for stmt in MIGRATIONS[target]:
                cursor.execute(stmt)
    conn.commit()
