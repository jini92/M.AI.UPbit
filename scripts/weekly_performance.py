#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Weekly performance report generation (cron job).

Runs every Monday at 08:00 KST.

Usage:
    python scripts/weekly_performance.py [--weeks 1]
"""

import argparse
import json
import logging

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Weekly performance report")
    parser.add_argument("--weeks", type=int, default=1, help="Number of weeks")
    args = parser.parse_args()

    from maiupbit.trading.journal import TradeJournal
    from maiupbit.integrations.obsidian import ObsidianSync

    journal = TradeJournal(path="trade_journal.json")
    days = args.weeks * 7
    stats = journal.get_stats(days=days)
    trades = journal.get_trades(days=days)

    sync = ObsidianSync()
    report_path = sync.generate_weekly_report(stats, trades)

    output = {
        "period_days": days,
        "stats": stats,
        "trade_count": len(trades),
        "report_path": str(report_path) if report_path else None,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()