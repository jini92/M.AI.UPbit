# A-002 — Market Data Accumulation Gap Analysis

> **Document ID**: A-002  
> **Project**: M.AI.UPbit  
> **Date**: 2026-03-23  
> **Status**: Complete  
> **Author**: MAIBOT

---

## 1. Objective

Define whether M.AI.UPbit has enough persistent data to support reproducible analysis, long-horizon backtests, decision auditing, and a durable learning loop.

**Conclusion:** not yet. The project has started to accumulate trade decision logs, but it does **not** yet have a durable market data layer.

---

## 2. Current State Observed

### 2.1 Durable files that exist today

| Artifact | Current role | Observation |
|---|---|---|
| `trade_journal.json` | Structured trade decision log | ~36 records observed on 2026-03-23, but currently dominated by `hold` records |
| `trade_history.json` | Lightweight buy/sell history | Small JSON history (~6 records observed) |
| `docs/newsletter/*.json` | Newsletter/report payload snapshots | Point-in-time output only, not a canonical market store |
| `benchmarks/baseline.json` | Regression guard baseline | Configuration baseline, not market history |

### 2.2 Market data access pattern today

Current code paths fetch live data directly from Upbit or `pyupbit` and do not persist a canonical local copy.

| Code path | Current behavior | Limitation |
|---|---|---|
| `maiupbit/exchange/upbit.py#get_ohlcv()` | Calls `pyupbit.get_ohlcv(...)` directly | No cache, no historical store, no replayability |
| `maiupbit/exchange/upbit.py#fetch_data()` | Fetches daily + hourly OHLCV directly | Returns DataFrames only; nothing is stored |
| `maiupbit/trading/auto_trader.py#_collect_market_data()` | Calls `pyupbit.get_ohlcv(symbol, count=200)` directly | Bypasses exchange abstraction and any future cache/store |
| `scripts/quant.py` | Pulls live OHLCV on demand | Quant results are not reproducible unless the same API data is fetched again |
| `scripts/daily_report.py` / `scripts/monitor.py` | Compute from live fetches | Reports can be regenerated only approximately |

### 2.3 Legacy precedent already existed

The legacy POC in `app.py` previously used SQLite (`trade_history.db`) for trade persistence.
That means the project has already demonstrated that a local embedded database is operationally acceptable.

**Important observation:** the modular refactor improved architecture and testability, but the durable storage layer did not evolve with it.

---

## 3. Why the current data is not enough yet

### 3.1 Reproducibility gap

Today, most analysis is based on live fetches. That means:

- historical analyses are hard to replay exactly,
- backtest inputs are not versioned locally,
- newsletter or report outputs cannot be regenerated from a canonical internal source.

### 3.2 Provenance gap

`trade_journal.json` records a compact decision summary, but not the full market snapshot that produced the decision.

Missing today:

- the exact candle set used for the decision,
- exact indicator values across the analysis window,
- exact quant ranking inputs,
- exact LLM input snapshot beyond a short summary,
- exact ticker snapshot for later audit.

### 3.3 Learning loop gap

The project vision depends on **data → knowledge → better decisions**. Right now the system stores decision outcomes much better than raw market context.

As a result:

- Mnemo can learn from trade notes,
- but M.AI.UPbit cannot reliably reconstruct the full market state behind those notes,
- and model/backtest improvements remain partially dependent on refetching live APIs.

### 3.4 Scaling gap

JSON append-only files are fine for tens of records, but not ideal for:

- multi-symbol OHLCV history,
- time-range queries,
- deduplication/upserts,
- interval coverage checks,
- joining trades with market context.

### 3.5 Evaluation gap

`TradeJournal.get_pending_outcomes()` intentionally skips `hold` records. Since the observed journal is currently dominated by `hold`, data volume is increasing faster than meaningful evaluated outcome volume.

That is not a bug by itself, but it means **journal growth alone does not equal learning-quality growth**.

---

## 4. Non-Goals for this phase

This storage initiative should **not** try to solve everything at once.

Out of scope for the first implementation:

- tick-level or orderbook-level high-frequency storage,
- cloud database deployment,
- migration of every existing JSON artifact into SQL on day one,
- full portfolio accounting engine redesign,
- multi-exchange abstraction redesign.

---

## 5. Decision

Adopt a **local-first layered storage architecture**:

1. **SQLite as the canonical operational store** for market candles and analysis snapshots.
2. **CSV/Parquet exports as secondary analytics/export artifacts** for notebooks, reports, and newsletter generation.
3. Keep `trade_journal.json` and `trade_history.json` temporarily for backward compatibility during migration.

### Why SQLite first

SQLite is the best first step because it gives the project:

- idempotent upserts,
- primary keys for dedupe,
- fast local queries,
- zero external infrastructure,
- easy Python integration,
- simple backup/portability.

### Why not CSV-only

CSV is useful for export and manual inspection, but weak as a canonical store because it does not naturally solve:

- deduplication,
- partial-range backfills,
- interval coverage checks,
- atomic writes,
- reliable joins between market data and decision metadata.

---

## 6. Recommended Scope for Phase 1

### Symbols

Start with a focused watchlist:

- `KRW-BTC`
- `KRW-ETH`
- `KRW-XRP`
- `KRW-SOL`
- `KRW-DOGE`
- `KRW-BTT`
- plus any symbol that appears in actual trades

### Intervals

Start with:

- `day`
- `minute60`

Optional later:

- `minute240`
- `minute15`

### Retention

- Daily candles: full available history for tracked symbols
- Hourly candles: at least rolling 180-365 days initially
- Analysis snapshots: retain all

---

## 7. Success Criteria

The initiative is successful when M.AI.UPbit can do all of the following without depending on a fresh live fetch for every task:

1. Rebuild a quant report from the local store.
2. Re-run a backtest from canonical local candles.
3. Link a trade decision to the exact analysis snapshot used at decision time.
4. Export selected datasets to CSV/Parquet for notebooks and newsletter workflows.
5. Warm the latest candles locally before daily report / quant / auto-trade runs.

---

## 8. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Storage design becomes too ambitious | Slower delivery | Start with candles + analysis snapshots only |
| Direct `pyupbit` calls remain scattered | Inconsistent behavior | Centralize all candle reads behind one service layer |
| DB file grows too quickly | Operational friction | Keep SQLite canonical, export heavy analytics separately |
| Mixed sources drift over time | Hard-to-debug reports | Add ingestion metadata and idempotent upsert rules |
| Breaking existing scripts | Delivery risk | Keep JSON outputs and CLI behavior backward-compatible |

---

## 9. Recommendation Summary

M.AI.UPbit has **started** to accumulate decision data, but it has **not yet built the durable market data asset** that the flywheel really needs.

The right next step is:

- **not** “collect more JSON”,
- but **introduce a canonical SQLite-backed market data layer**,
- then refactor report / quant / auto-trade code to read through that layer,
- then export to CSV/Parquet only where analytics portability is useful.

That keeps the system small, local, reproducible, and ready for the next growth stage.

---

_Updated as of repository inspection on 2026-03-23._
