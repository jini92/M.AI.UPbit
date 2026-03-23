# D-003 — Market Data Accumulation Architecture

> **Document ID**: D-003  
> **Project**: M.AI.UPbit  
> **Date**: 2026-03-23  
> **Status**: Implemented  
> **Author**: MAIBOT

---

## 1. Goal

Introduce a durable local market data layer that makes M.AI.UPbit reproducible, queryable, and easier to evolve.

This design is intended to support:

- quant reports,
- daily reports,
- backtests,
- auto-trade decision provenance,
- future notebook/newsletter reuse.

---

## 2. Target Architecture

```text
                    ┌──────────────────────────┐
                    │      Upbit / pyupbit     │
                    └────────────┬─────────────┘
                                 │ fetch missing ranges
                                 ▼
                    ┌──────────────────────────┐
                    │   MarketDataService      │
                    │ coverage check + upsert  │
                    └────────────┬─────────────┘
                                 │
                ┌────────────────┴────────────────┐
                │                                 │
                ▼                                 ▼
     ┌──────────────────────┐         ┌────────────────────────┐
     │ SQLite canonical DB  │         │ CSV / Parquet exports  │
     │ data/market_data.db  │         │ data/exports/*         │
     └──────────┬───────────┘         └────────────────────────┘
                │
                ▼
     ┌───────────────────────────────────────────────────────────┐
     │ report / quant / monitor / training / auto_trade scripts │
     └───────────────────────────────────────────────────────────┘
```

---

## 3. Design Principles

1. **Local-first** — no external database required.
2. **Canonical-before-export** — SQLite is source of truth; CSV/Parquet is derived.
3. **Idempotent ingestion** — repeated runs should upsert, not duplicate.
4. **Backwards-compatible migration** — existing JSON outputs stay working.
5. **Decision provenance matters** — store not only candles, but also analysis snapshots.
6. **Small surface area first** — candles first, richer snapshots second.

---

## 4. Storage Layout

### 4.1 Canonical store

```text
data/
├── market_data.db
└── exports/
    ├── candles/
    ├── snapshots/
    └── reports/
```

### 4.2 Existing artifacts kept during transition

- `trade_journal.json`
- `trade_history.json`
- `docs/newsletter/*.json`

These remain valid during migration, but newly introduced code should increasingly rely on the SQLite store.

---

## 5. Proposed Schema

### 5.1 `market_candles`

Canonical OHLCV store.

| Column | Type | Notes |
|---|---|---|
| `symbol` | TEXT | e.g. `KRW-BTC` |
| `interval` | TEXT | `day`, `minute60`, later expandable |
| `candle_time_utc` | TEXT | canonical timestamp |
| `open` | REAL | required |
| `high` | REAL | required |
| `low` | REAL | required |
| `close` | REAL | required |
| `volume` | REAL | optional but expected |
| `value` | REAL | trade value if available |
| `source` | TEXT | default `upbit` |
| `ingested_at_utc` | TEXT | ingestion timestamp |

**Primary key:** `(symbol, interval, candle_time_utc)`

### 5.2 `ticker_snapshots`

Optional but recommended for decision audit.

| Column | Type | Notes |
|---|---|---|
| `symbol` | TEXT | tracked symbol |
| `snapshot_time_utc` | TEXT | capture time |
| `trade_price` | REAL | last trade price |
| `signed_change_rate` | REAL | 24h rate |
| `acc_trade_volume_24h` | REAL | if available |
| `raw_json` | TEXT | optional raw payload |

### 5.3 `analysis_snapshots`

Stores the exact context used for a report or trading decision.

| Column | Type | Notes |
|---|---|---|
| `snapshot_id` | TEXT | UUID |
| `created_at_utc` | TEXT | snapshot creation time |
| `symbol` | TEXT | analysis symbol |
| `kind` | TEXT | `daily_report`, `quant`, `auto_trade`, `training` |
| `trade_id` | TEXT NULL | linked trade if applicable |
| `market_json` | TEXT | compact serialized market context |
| `indicators_json` | TEXT | derived indicator snapshot |
| `quant_json` | TEXT | quant outputs |
| `llm_json` | TEXT | LLM result if used |
| `knowledge_summary` | TEXT | Mnemo context excerpt |
| `provider` | TEXT | `openai`, `ollama`, etc. |
| `model` | TEXT | model name if applicable |

### 5.4 `ingestion_runs`

Observability for backfills and refreshes.

| Column | Type | Notes |
|---|---|---|
| `run_id` | TEXT | UUID |
| `started_at_utc` | TEXT | start time |
| `finished_at_utc` | TEXT | end time |
| `task` | TEXT | `backfill`, `refresh`, `warmup` |
| `symbol` | TEXT NULL | optional |
| `interval` | TEXT NULL | optional |
| `rows_written` | INTEGER | inserted/upserted rows |
| `status` | TEXT | `ok`, `partial`, `error` |
| `error_message` | TEXT NULL | failure detail |

---

## 6. Proposed Code Modules

| Module | Purpose |
|---|---|
| `maiupbit/storage/schema.py` | SQL schema creation / migrations |
| `maiupbit/storage/sqlite_store.py` | low-level DB read/write API |
| `maiupbit/services/market_data.py` | coverage-aware fetch + upsert + DataFrame return |
| `scripts/backfill_market_data.py` | scheduled backfill / warmup |
| `scripts/export_market_data.py` | CSV/Parquet exports for notebooks/reports |

### Files to refactor first

| File | Change |
|---|---|
| `maiupbit/exchange/upbit.py` | route candle reads through the store-backed service |
| `maiupbit/trading/auto_trader.py` | remove direct `pyupbit.get_ohlcv(...)` usage |
| `scripts/quant.py` | use canonical local candles |
| `scripts/daily_report.py` | use canonical local candles |
| `scripts/monitor.py` | optionally warm latest snapshots from store-backed service |
| `scripts/train_model.py` | use canonical historical data for training |

---

## 7. Read Path Design

### 7.1 Caller contract

Callers should request candles like this conceptually:

```python
service.get_ohlcv(symbol="KRW-BTC", interval="day", count=365, prefer_local=True)
```

### 7.2 Resolution algorithm

1. Check local SQLite coverage for the requested symbol/interval/range.
2. If coverage is complete, return local data.
3. If coverage is partial or missing:
   - fetch only missing ranges from Upbit,
   - normalize timestamps,
   - upsert into SQLite,
   - return the completed local result.
4. Record ingestion metadata in `ingestion_runs`.

### 7.3 Expected benefits

- repeated quant/report runs become deterministic,
- fewer redundant API calls,
- easier debugging when a report changes,
- one read path instead of scattered direct fetches.

---

## 8. Write Path Design

### 8.1 Scheduled backfill

A new script should support both:

- **historical backfill** for first-time setup,
- **incremental refresh** for ongoing operation.

Example modes:

```bash
python scripts/backfill_market_data.py --symbols KRW-BTC,KRW-ETH --interval day --days 730
python scripts/backfill_market_data.py --symbols KRW-BTC,KRW-ETH --interval minute60 --days 180
python scripts/backfill_market_data.py --watchlist --refresh-latest
```

### 8.2 Decision snapshot persistence

Before or during report/trade generation, store:

- candle window used,
- derived indicators,
- quant outputs,
- LLM output,
- Mnemo summary.

This creates an audit trail that the current JSON journal alone cannot provide.

---

## 9. Migration Strategy

### Phase 1 — Foundation

**Deliverables**

- SQLite schema
- storage module
- unit tests for insert/upsert/query
- `.gitignore` updates for `data/*.db` and exports

**Acceptance**

- can create DB from scratch,
- can upsert candles idempotently,
- can query a symbol/interval range into a DataFrame.

### Phase 2 — Read-path integration

**Deliverables**

- `UPbitExchange.get_ohlcv()` backed by `MarketDataService`
- `auto_trader.py` stops calling `pyupbit.get_ohlcv(...)` directly
- `quant.py`, `daily_report.py`, `train_model.py` consume the store

**Acceptance**

- repeated report/quant runs hit local data when already available,
- live fetches only fill gaps.

### Phase 3 — Backfill + operational warmup

**Deliverables**

- `scripts/backfill_market_data.py`
- initial watchlist definition
- cron or manual warmup procedure

**Acceptance**

- fresh environment can build a useful local history,
- daily workflow has candles ready before report/trade generation.

### Phase 4 — Analysis provenance

**Deliverables**

- `analysis_snapshots` persistence
- trade-to-snapshot linking
- optional ticker snapshot capture

**Acceptance**

- every executed trade can be audited back to its exact analysis context.

### Phase 5 — Export and analytics reuse

**Deliverables**

- CSV/Parquet exports
- notebook/newsletter friendly datasets
- documented usage examples

**Acceptance**

- newsletter/report tooling can run from local exports without rebuilding ad hoc datasets.

---

## 10. Recommended Initial Watchlist

Start narrow to keep delivery fast and data useful:

- `KRW-BTC`
- `KRW-ETH`
- `KRW-XRP`
- `KRW-SOL`
- `KRW-DOGE`
- `KRW-BTT`
- plus any newly traded symbol

This matches the current monitoring/report focus and avoids building a giant store before the workflow proves itself.

---

## 11. Test Strategy

### Unit tests

- schema creation
- candle upsert idempotency
- time-range query correctness
- missing-range merge logic
- export generation

### Integration tests

- mocked Upbit backfill
- store-backed `get_ohlcv()` behavior
- `auto_trade` snapshot persistence
- `quant.py` / `daily_report.py` deterministic behavior with seeded DB

### Regression tests

- existing script JSON outputs remain backward-compatible
- new storage layer does not change trading safety behavior

---

## 12. Open Questions

1. Should `minute240` be added in Phase 1 or deferred?
2. Should `trade_journal.json` remain source-of-truth long-term, or eventually mirror into SQL?
3. Do we want ticker snapshots only, or orderbook snapshots too?
4. How much hourly history is operationally worth retaining before exporting older partitions?

---

## 13. Recommended Execution Order

If implementation starts immediately, the best order is:

1. storage foundation,
2. exchange/service integration,
3. backfill script,
4. analysis snapshot persistence,
5. export tooling.

That order minimizes risk and unlocks usable value early.

---

_This design intentionally prefers a small, durable local architecture over a heavy data platform._
