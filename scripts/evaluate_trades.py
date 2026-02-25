#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""매매 사후 평가 스크립트 (크론용).

매일 07:30 KST 실행.
24h+ 경과한 미평가 매매의 수익률·정확도 평가.

Usage:
    python scripts/evaluate_trades.py
"""

import json
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


def main() -> None:
    access_key = os.getenv("UPBIT_ACCESS_KEY")
    secret_key = os.getenv("UPBIT_SECRET_KEY")

    if not access_key or not secret_key:
        print(json.dumps({"error": "UPBIT_ACCESS_KEY/SECRET_KEY 필요"}))
        sys.exit(1)

    from maiupbit.exchange.upbit import UPbitExchange
    from maiupbit.trading.journal import TradeJournal
    from maiupbit.trading.outcome import OutcomeTracker

    exchange = UPbitExchange(access_key=access_key, secret_key=secret_key)
    journal = TradeJournal(path="trade_journal.json")
    tracker = OutcomeTracker(exchange=exchange, journal=journal)

    results = tracker.evaluate_pending()

    # Obsidian 노트 업데이트
    if results:
        try:
            from maiupbit.integrations.obsidian import ObsidianSync
            sync = ObsidianSync()
            all_trades = journal.get_trades(days=7)
            for r in results:
                trade = next(
                    (t for t in all_trades if t["trade_id"] == r["trade_id"]),
                    None,
                )
                if trade:
                    sync.update_outcome_note(trade, journal)
        except Exception as exc:
            logging.warning("Obsidian 업데이트 실패: %s", exc)

    output = {
        "evaluated": len(results),
        "results": results,
        "stats": journal.get_stats(days=7),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
