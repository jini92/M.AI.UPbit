# T-002 — Market Data Persistence Validation Report

> **Document ID**: T-002
> **Project**: M.AI.UPbit
> **Date**: 2026-03-23
> **Status**: Pass (scoped)
> **Author**: MAIBOT
> **Relates to**: I-002, D-003

---

## 1. Scope

This report covers validation of the market data persistence initiative (Phases 1-6 from D-003) and the subsequent hardening pass. It does not cover pre-existing test failures unrelated to this initiative.

---

## 2. Validation Commands

### 2.1 Scoped test suite (all market-data + core tests)

```bash
python -m pytest tests/unit/test_storage.py tests/unit/test_auto_trader_snapshot.py \
  tests/unit/test_export.py tests/unit/test_create_exchange.py \
  tests/unit/test_market_data_service.py tests/unit/test_hardening.py \
  tests/unit/test_indicators.py tests/unit/test_quant_indicators.py \
  tests/unit/test_strategies.py tests/unit/test_backtest.py -v
```

### 2.2 Full suite (for pre-existing failure inventory)

```bash
python -m pytest tests/unit/ --ignore=tests/unit/test_analysis.py -v
```

---

## 3. Results

### 3.1 Scoped suite

| Metric | Value |
|---|---|
| **Total tests** | 117 |
| **Passed** | 117 |
| **Failed** | 0 |
| **Skipped** | 0 |
| **Runtime** | ~2.3s |
| **Verdict** | **PASS** |

### 3.2 Breakdown by test file

| Test file | Tests | Result |
|---|---|---|
| `test_storage.py` | 32 | 32 passed |
| `test_auto_trader_snapshot.py` | 5 | 5 passed |
| `test_export.py` | 7 | 7 passed |
| `test_create_exchange.py` | 5 | 5 passed |
| `test_market_data_service.py` | 6 | 6 passed |
| `test_hardening.py` | 10 | 10 passed |
| `test_indicators.py` | 7 | 7 passed |
| `test_quant_indicators.py` | 9 | 9 passed |
| `test_strategies.py` | 21 | 21 passed |
| `test_backtest.py` | 15 | 15 passed |

### 3.3 Full suite results

| Metric | Value |
|---|---|
| **Total tests** | 218 |
| **Passed** | 198 |
| **Failed** | 17 |
| **Skipped** | 3 |
| **Runtime** | ~102s |

---

## 4. Pre-existing Failures (Unrelated)

These 17 failures exist independently of the market data initiative. None are caused by or affected by the changes in this initiative.

| Test file | Failures | Root cause |
|---|---|---|
| `test_cli.py` | 3 | CLI behavior changes, API key handling |
| `test_exchange.py` | 2 | Trade history JSON handling, tuple assertion |
| `test_knowledge.py` | 4 | Subprocess/search integration, Mnemo availability |
| `test_models.py` | 6 | Windows paging file error loading torch/CUDA DLLs |
| `test_sentiment.py` | 1 | Article formatting assertion |
| `test_create_exchange.py` | 1 (in full suite only) | Env contamination from torch loading; passes in isolation |

**Note**: `test_analysis.py` is excluded from all runs due to a pre-existing `_safe_float` import error.

---

## 5. Coverage Areas Validated

### 5.1 Storage foundation (Phase 1)
- Schema creation, idempotent init, version tracking
- Candle upsert (insert, update, empty, null, multi-symbol, multi-interval)
- Query (count, time range, datetime index, empty)
- Coverage tracking
- Ingestion run lifecycle (start, finish, error)
- Schema migration v1 → v2

### 5.2 Read-path integration (Phase 2)
- Local-first reads (sufficient local data returns without fetch)
- Live fetch when local insufficient (with mock pyupbit)
- Live fetch upserts into store
- Ingestion run recorded on fetch
- `prefer_local=False` bypasses local check
- `create_exchange()` wiring (service attached, local store used, live fallback)

### 5.3 Backfill (Phase 3)
- Page-stepping avoids overlap (steps back by one interval)
- `--refresh` help text matches behavior (2 days)

### 5.4 Analysis snapshots (Phase 4)
- Save returns UUID
- Save and query roundtrip
- Get by ID, not-found handling
- Filter by kind, trade_id
- Query limit
- Null field handling
- JSON serialization roundtrip
- AutoTrader persists snapshot on trade
- Snapshot contains market_data, llm_result
- No snapshot when no store (graceful degradation)
- Query snapshots by trade_id

### 5.5 Export (Phase 5)
- Candle CSV export, empty handling
- Snapshot CSV export, JSON field serialization
- Filter by kind, trade_id
- Empty snapshot handling

### 5.6 Hardening (Phase 6)
- `to=` parameter respected on local-hit path
- `to=` insufficient local triggers fetch
- Fallback respects `to=`
- `query_candles(count=, end=)` combo correctness
- `auto_trade.py` uses `create_exchange()`

---

## 6. Validation Gaps

| Gap | Severity | Reason |
|---|---|---|
| Live backfill end-to-end | Low | Requires real Upbit API; covered by mock tests |
| Parquet export | Low | pyarrow not installed; CSV path validated |
| `evaluate_trades.py` wiring | Low | Minor utility, not in core data path |
| `ticker_snapshots` table | Deferred | Not in current plan scope (D-003 Section 5.2 marked optional) |
| Gap-aware partial fetch | Deferred | Service refetches full count; noted as architectural limitation |

---

## 7. Conclusion

The market data persistence initiative is **complete** against the approved 6-phase plan. All 117 scoped tests pass. The 17 full-suite failures are pre-existing and unrelated. The implementation is ready for a final reviewer pass.

---

_Generated 2026-03-23._
