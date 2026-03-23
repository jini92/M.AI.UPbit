#!/usr/bin/env python3
"""Export candles and analysis snapshots from the canonical SQLite store.

Usage:
    python scripts/export_market_data.py candles --symbol KRW-BTC --interval day
    python scripts/export_market_data.py candles --symbol KRW-BTC --interval day --format parquet
    python scripts/export_market_data.py snapshots --symbol KRW-BTC --kind auto_trade
    python scripts/export_market_data.py snapshots --kind daily_report --limit 100
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from maiupbit.storage.sqlite_store import SQLiteStore

DEFAULT_EXPORT_DIR = Path("data/exports")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def export_candles(args) -> None:
    """Export OHLCV candles to CSV or Parquet."""
    store = SQLiteStore(db_path=args.db) if args.db else SQLiteStore()

    df = store.query_candles(
        symbol=args.symbol,
        interval=args.interval,
        start=args.start,
        end=args.end,
    )

    if df.empty:
        print(json.dumps({"error": f"No candles found for {args.symbol}/{args.interval}"}))
        store.close()
        return

    out_dir = Path(args.output) if args.output else DEFAULT_EXPORT_DIR / "candles"
    _ensure_dir(out_dir)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{args.symbol.replace('-', '_')}_{args.interval}_{timestamp}"

    if args.format == "parquet":
        try:
            out_path = out_dir / f"{base_name}.parquet"
            df.to_parquet(str(out_path))
        except ImportError:
            print(json.dumps({
                "error": "pyarrow not installed. Use --format csv or: pip install pyarrow"
            }))
            store.close()
            return
    else:
        out_path = out_dir / f"{base_name}.csv"
        df.to_csv(str(out_path))

    result = {
        "exported": str(out_path),
        "format": args.format,
        "symbol": args.symbol,
        "interval": args.interval,
        "rows": len(df),
    }
    if not df.empty:
        result["date_range"] = {
            "start": str(df.index.min()),
            "end": str(df.index.max()),
        }

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    store.close()


def export_snapshots(args) -> None:
    """Export analysis snapshots to CSV."""
    store = SQLiteStore(db_path=args.db) if args.db else SQLiteStore()

    snapshots = store.query_snapshots(
        symbol=args.symbol,
        kind=args.kind,
        trade_id=args.trade_id,
        limit=args.limit,
    )

    if not snapshots:
        print(json.dumps({"error": "No snapshots found matching filters"}))
        store.close()
        return

    out_dir = Path(args.output) if args.output else DEFAULT_EXPORT_DIR / "snapshots"
    _ensure_dir(out_dir)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filter_parts = []
    if args.symbol:
        filter_parts.append(args.symbol.replace("-", "_"))
    if args.kind:
        filter_parts.append(args.kind)
    filter_label = "_".join(filter_parts) if filter_parts else "all"
    base_name = f"snapshots_{filter_label}_{timestamp}"

    # Flatten JSON fields for CSV export
    import pandas as pd
    rows = []
    for snap in snapshots:
        flat = {}
        for key, val in snap.items():
            if isinstance(val, dict):
                flat[key] = json.dumps(val, ensure_ascii=False, default=str)
            else:
                flat[key] = val
        rows.append(flat)

    df = pd.DataFrame(rows)
    out_path = out_dir / f"{base_name}.csv"
    df.to_csv(str(out_path), index=False)

    result = {
        "exported": str(out_path),
        "format": "csv",
        "rows": len(snapshots),
        "filters": {
            "symbol": args.symbol,
            "kind": args.kind,
            "trade_id": args.trade_id,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    store.close()


def main():
    parser = argparse.ArgumentParser(
        prog="export_market_data",
        description="Export market data from canonical SQLite store",
    )
    parser.add_argument("--db", help="Path to SQLite DB (default: data/market_data.db)")

    subparsers = parser.add_subparsers(dest="command", help="Export target")

    # candles
    p_candles = subparsers.add_parser("candles", help="Export OHLCV candles")
    p_candles.add_argument("--symbol", required=True, help="Market symbol (e.g. KRW-BTC)")
    p_candles.add_argument("--interval", default="day", help="Candle interval (default: day)")
    p_candles.add_argument("--start", help="Start date (ISO format)")
    p_candles.add_argument("--end", help="End date (ISO format)")
    p_candles.add_argument("--format", choices=["csv", "parquet"], default="csv", help="Output format")
    p_candles.add_argument("--output", help="Output directory (default: data/exports/candles/)")
    p_candles.set_defaults(func=export_candles)

    # snapshots
    p_snap = subparsers.add_parser("snapshots", help="Export analysis snapshots")
    p_snap.add_argument("--symbol", help="Filter by symbol")
    p_snap.add_argument("--kind", help="Filter by kind (auto_trade, daily_report, etc.)")
    p_snap.add_argument("--trade-id", dest="trade_id", help="Filter by trade ID")
    p_snap.add_argument("--limit", type=int, default=100, help="Max rows (default: 100)")
    p_snap.add_argument("--output", help="Output directory (default: data/exports/snapshots/)")
    p_snap.set_defaults(func=export_snapshots)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
