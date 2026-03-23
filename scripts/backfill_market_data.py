#!/usr/bin/env python3
"""Backfill market candle data into the local SQLite store.

Usage:
    # Backfill default watchlist, day + minute60
    python scripts/backfill_market_data.py

    # Specific symbols and interval
    python scripts/backfill_market_data.py --symbols KRW-BTC,KRW-ETH --interval day --days 365

    # Refresh latest candles only
    python scripts/backfill_market_data.py --refresh
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import timedelta

import pyupbit

from maiupbit.storage.sqlite_store import SQLiteStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_WATCHLIST = [
    "KRW-BTC",
    "KRW-ETH",
    "KRW-XRP",
    "KRW-SOL",
    "KRW-DOGE",
    "KRW-BTT",
]

DEFAULT_INTERVALS = ["day", "minute60"]

# pyupbit returns at most 200 candles per call
MAX_CANDLES_PER_CALL = 200


def backfill_symbol(
    store: SQLiteStore,
    symbol: str,
    interval: str,
    days: int,
) -> int:
    """Backfill candles for a single symbol/interval combination.

    Args:
        store: SQLiteStore instance.
        symbol: Market symbol.
        interval: Candle interval.
        days: Number of days of history to fetch.

    Returns:
        Total rows upserted.
    """
    if interval == "day":
        total_candles = days
    elif interval == "minute60":
        total_candles = days * 24
    elif interval == "minute240":
        total_candles = days * 6
    else:
        total_candles = days

    # Map interval to timedelta for stepping back between pages
    _interval_step = {
        "day": timedelta(days=1),
        "minute60": timedelta(hours=1),
        "minute240": timedelta(hours=4),
        "minute30": timedelta(minutes=30),
        "minute15": timedelta(minutes=15),
        "minute10": timedelta(minutes=10),
        "minute5": timedelta(minutes=5),
        "minute3": timedelta(minutes=3),
        "minute1": timedelta(minutes=1),
        "week": timedelta(weeks=1),
        "month": timedelta(days=30),
    }
    step_back = _interval_step.get(interval, timedelta(days=1))

    run_id = store.start_ingestion_run("backfill", symbol, interval)
    total_rows = 0
    total_fetched = 0

    try:
        remaining = total_candles
        to_param = None

        while remaining > 0:
            batch = min(remaining, MAX_CANDLES_PER_CALL)
            df = pyupbit.get_ohlcv(symbol, interval=interval, count=batch, to=to_param)

            if df is None or df.empty:
                logger.warning("No data returned for %s/%s (to=%s)", symbol, interval, to_param)
                break

            rows = store.upsert_candles(df, symbol, interval)
            total_rows += rows
            total_fetched += len(df)
            remaining -= len(df)

            # Step back by one interval from the earliest candle to avoid
            # re-fetching it in the next batch.
            earliest = df.index[0]
            stepped = earliest - step_back
            to_param = stepped.strftime("%Y-%m-%dT%H:%M:%S")

            logger.info(
                "  %s/%s: fetched %d candles (upserted %d, remaining ~%d)",
                symbol, interval, len(df), total_rows, max(remaining, 0),
            )

            # Rate limit: pyupbit recommends ~10 req/sec
            time.sleep(0.15)

        store.finish_ingestion_run(run_id, rows_written=total_rows, status="ok")
    except Exception as exc:
        store.finish_ingestion_run(run_id, rows_written=total_rows, status="error", error_message=str(exc))
        logger.error("Backfill failed for %s/%s: %s", symbol, interval, exc)

    return total_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill market candle data into SQLite store")
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated symbols (default: watchlist)",
    )
    parser.add_argument(
        "--interval",
        type=str,
        default=None,
        help="Single interval to backfill (default: day + minute60)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Days of history to fetch (default: 365)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Quick refresh: fetch latest 2 days of candles per symbol/interval",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="SQLite DB path (default: data/market_data.db)",
    )
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else DEFAULT_WATCHLIST
    intervals = [args.interval] if args.interval else DEFAULT_INTERVALS
    days = 2 if args.refresh else args.days

    store = SQLiteStore(db_path=args.db_path)
    grand_total = 0

    logger.info("Backfill starting: %d symbols x %d intervals, %d days", len(symbols), len(intervals), days)

    for symbol in symbols:
        for interval in intervals:
            logger.info("Backfilling %s / %s ...", symbol, interval)
            rows = backfill_symbol(store, symbol, interval, days)
            grand_total += rows

    store.close()
    logger.info("Backfill complete. Total rows upserted: %d", grand_total)


if __name__ == "__main__":
    main()
