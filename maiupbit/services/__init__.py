"""maiupbit.services — Service layer for coordinated data access."""

from __future__ import annotations

import os
from typing import Optional


def create_exchange(
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    db_path: Optional[str] = None,
) -> "maiupbit.exchange.upbit.UPbitExchange":
    """Build a UPbitExchange wired to the local-first MarketDataService.

    This is the recommended way for scripts to obtain an exchange instance.
    The returned exchange reads candles from the SQLite store first and
    only fetches from Upbit when local coverage is insufficient.

    Args:
        access_key: UPbit API key (defaults to env ``UPBIT_ACCESS_KEY``).
        secret_key: UPbit API secret (defaults to env ``UPBIT_SECRET_KEY``).
        db_path: Optional override for the SQLite DB path.

    Returns:
        A fully wired UPbitExchange instance.
    """
    from maiupbit.exchange.upbit import UPbitExchange
    from maiupbit.services.market_data import MarketDataService
    from maiupbit.storage.sqlite_store import SQLiteStore

    ak = access_key or os.getenv("UPBIT_ACCESS_KEY") or None
    sk = secret_key or os.getenv("UPBIT_SECRET_KEY") or None

    store = SQLiteStore(db_path=db_path) if db_path else SQLiteStore()
    # Build exchange first (without service) so the service can reference it
    exchange = UPbitExchange(access_key=ak, secret_key=sk)
    service = MarketDataService(store=store, exchange=exchange)
    # Attach service so exchange.get_ohlcv() uses local-first path
    exchange._market_data_service = service
    return exchange
