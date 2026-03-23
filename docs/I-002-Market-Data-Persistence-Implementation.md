# I-002 — Market Data Persistence Implementation

> **Document ID**: I-002
> **Project**: M.AI.UPbit
> **Date**: 2026-03-23
> **Status**: Complete
> **Author**: MAIBOT
> **Relates to**: A-002, D-003

---

## 1. Summary

This document records the implementation of the local-first market data persistence layer described in D-003. The initiative introduced a canonical SQLite store for OHLCV candles and analysis snapshots, rewired all scripts to use a store-backed exchange path, and added export tooling.

---

## 2. Phase Completion Status

| Phase | Description | Status | Notes |
|---|---|---|---|
| 1 | Storage foundation | **Complete** | Schema v2, SQLiteStore, idempotent upsert, migrations |
| 2 | Read-path integration | **Complete** | MarketDataService, `create_exchange()` factory, 7 scripts rewired |
| 3 | Backfill / warmup | **Complete** | `backfill_market_data.py`, page-stepping overlap fix, refresh mode |
| 4 | Analysis snapshot persistence | **Complete** | `analysis_snapshots` table, auto_trader + daily_report persist snapshots |
| 5 | Export layer | **Complete** | `export_market_data.py` CLI, CSV + Parquet (optional) |
| 6 | Hardening | **Complete** | `to=` semantics, `count+end` query combo, auto_trade rewiring, backfill overlap fix |

---

## 3. New Modules

| Module | Purpose |
|---|---|
| `maiupbit/storage/schema.py` | Schema DDL, versioned migrations (v1 → v2) |
| `maiupbit/storage/sqlite_store.py` | Low-level SQLite API: upsert, query, coverage, snapshots |
| `maiupbit/storage/__init__.py` | Package marker |
| `maiupbit/services/market_data.py` | Coverage-aware local-first read service |
| `maiupbit/services/__init__.py` | `create_exchange()` factory |
| `scripts/backfill_market_data.py` | Historical backfill + incremental refresh |
| `scripts/export_market_data.py` | CSV/Parquet export CLI |

## 4. Modified Modules

| Module | Change |
|---|---|
| `maiupbit/exchange/upbit.py` | `get_ohlcv()` routes through MarketDataService when wired; `fetch_data()` documented as intentional bypass |
| `maiupbit/trading/auto_trader.py` | `_save_analysis_snapshot()` + `_get_store()` for decision provenance |
| `scripts/auto_trade.py` | `UPbitExchange()` → `create_exchange()` |
| `scripts/quant.py` | 5 command functions rewired to `create_exchange()` |
| `scripts/daily_report.py` | Rewired + snapshot persistence per symbol |
| `scripts/monitor.py` | Rewired to `create_exchange()` |
| `scripts/train_model.py` | Rewired to `create_exchange()` |

## 5. New Test Files

| Test file | Tests | Coverage area |
|---|---|---|
| `tests/unit/test_storage.py` | 32 | Schema, upsert, query, coverage, ingestion runs, migrations, snapshots |
| `tests/unit/test_market_data_service.py` | 6 | Local-first reads, live fetch, ingestion run recording |
| `tests/unit/test_create_exchange.py` | 5 | Factory wiring, local store usage, live fallback, script wiring |
| `tests/unit/test_auto_trader_snapshot.py` | 5 | Snapshot persistence, content validation, no-store fallback |
| `tests/unit/test_export.py` | 7 | Candle CSV export, snapshot CSV export, JSON field serialization |
| `tests/unit/test_hardening.py` | 10 | `to=` semantics, `count+end` query, auto_trade wiring, backfill overlap |

**Total new tests**: 65

---

## 6. Architecture Decisions

### 6.1 `pyupbit` called directly in `_fetch_and_store`

`MarketDataService._fetch_and_store()` calls `pyupbit.get_ohlcv()` directly rather than the injected exchange. This is intentional: `UPbitExchange.get_ohlcv()` delegates to the service, so calling it from the service would cause infinite recursion. The exchange object's presence gates whether live fetching is allowed.

### 6.2 `fetch_data()` bypasses the service

`UPbitExchange.fetch_data()` returns `(daily_df, hourly_df)` — a tuple incompatible with the service's single-DataFrame contract. It is kept as a direct pyupbit call with documentation explaining the rationale.

### 6.3 No true gap-aware merge

The service re-fetches the full `count` from live when local coverage is insufficient, rather than computing exact missing date ranges. This is acceptable for current scale and avoids complex range arithmetic.

### 6.4 `rows_written` counts upserts, not net-new

SQLite `INSERT OR REPLACE` does not distinguish inserts from updates in `executemany`. The `rows_written` metric reflects total rows processed, not net-new rows added.

### 6.5 Date-only `end` normalization

`query_candles(end="2026-01-20")` normalizes to `"2026-01-20T23:59:59"` so candles stored as `"2026-01-20T00:00:00"` are correctly included.

---

## 7. Schema

### v2 (current)

**Tables**: `market_candles`, `ingestion_runs`, `analysis_snapshots`, `schema_meta`

The migration system in `schema.py` automatically upgrades v1 databases (candles + ingestion_runs only) to v2 (adds analysis_snapshots) on connection.

---

## 8. Script Wiring Summary

All production scripts now use `create_exchange()` from `maiupbit.services`:

| Script | `create_exchange()` | Snapshot persistence |
|---|---|---|
| `auto_trade.py` | Yes | Yes (via auto_trader) |
| `quant.py` | Yes (5 commands) | No |
| `daily_report.py` | Yes | Yes (per symbol) |
| `monitor.py` | Yes | No |
| `train_model.py` | Yes | No |
| `evaluate_trades.py` | No (uses raw UPbitExchange) | No |

`evaluate_trades.py` is a minor utility not in the core data path; rewiring is deferred.

---

## 9. Known Limitations

1. **No gap-aware merge** — service refetches full count, not just missing ranges
2. **No ticker_snapshots table** — deferred from D-003 Section 5.2
3. **Parquet requires pyarrow** — not installed in current env; export falls back gracefully
4. **Snapshot failures are silently swallowed** — by design, to never break the main workflow
5. **`evaluate_trades.py`** — not yet rewired to `create_exchange()`

---

_Updated 2026-03-23._
