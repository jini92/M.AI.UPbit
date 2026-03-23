"""Coverage-aware market data service.

Provides local-first OHLCV reads: checks SQLite first, fetches from
the exchange only for missing ranges, then upserts and returns.
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
import pyupbit

from maiupbit.storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)


class MarketDataService:
    """Coordinate candle reads between the local store and a live exchange.

    The injected *exchange* is used for live fetches via ``pyupbit`` (the
    exchange object itself is kept so the service can be wired bidirectionally,
    but actual API calls go through ``pyupbit.get_ohlcv`` which is the only
    reliable candle endpoint).  When *exchange* is ``None`` the service
    operates in local-only mode.

    Args:
        store: SQLiteStore instance.
        exchange: An exchange object.  Its presence enables live fetching
                  (via ``pyupbit``).  If ``None``, local-only mode.
    """

    def __init__(self, store: Optional[SQLiteStore] = None, exchange=None) -> None:
        self._store = store or SQLiteStore()
        self._exchange = exchange

    @property
    def store(self) -> SQLiteStore:
        return self._store

    def get_ohlcv(
        self,
        symbol: str,
        interval: str = "day",
        count: int = 30,
        to: Optional[str] = None,
        prefer_local: bool = True,
    ) -> pd.DataFrame:
        """Return OHLCV candles, using local store when possible.

        Resolution:
            1. If prefer_local, query local store (respecting ``to``).
            2. If local coverage satisfies the request, return local data.
            3. Otherwise, fetch from exchange, upsert, and return.

        Args:
            symbol: Market symbol (e.g. ``KRW-BTC``).
            interval: Candle interval (``day``, ``minute60``, etc.).
            count: Number of candles requested.
            to: End date/time string for the query window.  When set, only
                candles on or before this timestamp are considered.
            prefer_local: If True, try local store first.

        Returns:
            OHLCV DataFrame with DatetimeIndex. Empty DataFrame on failure.
        """
        if prefer_local:
            local_df = self._store.query_candles(
                symbol, interval, count=count, end=to,
            )
            if len(local_df) >= count:
                logger.debug(
                    "Local hit: %s %s — %d candles (to=%s)",
                    symbol, interval, len(local_df), to,
                )
                return local_df.tail(count)

        # Local coverage insufficient — fetch live
        live_df = self._fetch_and_store(symbol, interval, count, to)
        if live_df is not None and not live_df.empty:
            return live_df

        # Fallback: return whatever local data we have
        return self._store.query_candles(symbol, interval, count=count, end=to)

    def _fetch_and_store(
        self,
        symbol: str,
        interval: str,
        count: int,
        to: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """Fetch from exchange via pyupbit, upsert into store, return the DataFrame.

        Note: ``pyupbit.get_ohlcv`` is the canonical candle endpoint.  The
        injected exchange gates whether live fetching is allowed (non-None
        means yes) but the actual HTTP call goes through pyupbit because
        UPbitExchange.get_ohlcv delegates back to this service, which would
        cause infinite recursion if called here.

        Args:
            symbol: Market symbol.
            interval: Candle interval.
            count: Number of candles.
            to: Optional end time.

        Returns:
            The fetched DataFrame, or None on failure.
        """
        if self._exchange is None:
            return None

        try:
            df = pyupbit.get_ohlcv(symbol, interval=interval, count=count, to=to)
            if df is None or df.empty:
                return None

            run_id = self._store.start_ingestion_run("refresh", symbol, interval)
            try:
                rows = self._store.upsert_candles(df, symbol, interval)
                self._store.finish_ingestion_run(run_id, rows_written=rows, status="ok")
                logger.info("Fetched and stored %d candles for %s/%s", rows, symbol, interval)
            except Exception as exc:
                self._store.finish_ingestion_run(run_id, status="error", error_message=str(exc))
                raise

            return df
        except Exception as exc:
            logger.error("Live fetch failed for %s/%s: %s", symbol, interval, exc)
            return None

    def close(self) -> None:
        """Close underlying store connection."""
        self._store.close()
