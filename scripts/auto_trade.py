#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auto trading script for M.AI.Upbit.

This script runs from 07:00 to 19:00 KST daily.
It uses Obsidian for trade record synchronization.

Usage:
    python scripts/auto_trade.py [--symbol KRW-BTC] [--dry-run] [--provider ollama]
"""

import argparse
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
logger = logging.getLogger("auto_trade")


def main() -> None:
    parser = argparse.ArgumentParser(description="M.AI.Upbit auto trading script")
    parser.add_argument("--symbol", default="KRW-BTC", help="Trading symbol")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (no actual trades)")
    parser.add_argument("--provider", default=None, help="LLM provider (openai/ollama)")
    args = parser.parse_args()

    access_key = os.getenv("UPBIT_ACCESS_KEY")
    secret_key = os.getenv("UPBIT_SECRET_KEY")

    if not access_key or not secret_key:
        print(json.dumps({"error": "UPBIT_ACCESS_KEY/SECRET_KEY missing"}))
        sys.exit(1)

    # Exchange — use store-backed factory for local-first reads + snapshot persistence
    from maiupbit.services import create_exchange
    exchange = create_exchange(access_key=access_key, secret_key=secret_key)

    # Journal
    from maiupbit.trading.journal import TradeJournal
    journal = TradeJournal(path="trade_journal.json")

    # LLM (optional)
    llm = None
    try:
        from maiupbit.analysis.llm import LLMAnalyzer
        provider = args.provider or os.getenv("LLM_PROVIDER", "ollama")
        llm = LLMAnalyzer(provider=provider)
        logger.info("LLM initialized with %s (%s)", provider, llm.model)
    except Exception as exc:
        logger.warning("Failed to initialize LLM (reason: %s): %s", type(exc).__name__, exc)

    # Knowledge (optional)
    knowledge = None
    try:
        from maiupbit.analysis.knowledge import KnowledgeProvider
        knowledge = KnowledgeProvider()
        if knowledge.is_available():
            logger.info("Mnemo KnowledgeProvider initialized")
        else:
            knowledge = None
            logger.info("Mnemo unavailable (data not found)")
    except Exception as exc:
        logger.debug("Failed to initialize KnowledgeProvider: %s", exc)

    # AutoTrader
    from maiupbit.trading.auto_trader import AutoTrader
    trader = AutoTrader(
        exchange=exchange,
        journal=journal,
        llm_analyzer=llm,
        knowledge_provider=knowledge,
    )

    # Execution
    # Execute with overall timeout
    import concurrent.futures as _cf
    import os as _os
    RUN_TIMEOUT = float(_os.getenv("AUTO_TRADE_TIMEOUT", "300"))
    try:
        with _cf.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(trader.run, args.symbol, args.dry_run)
            result = future.result(timeout=RUN_TIMEOUT)
    except _cf.TimeoutError:
        logger.error("auto_trade timeout (%ds): %s", RUN_TIMEOUT, args.symbol)
        import json as _json, sys
        print(_json.dumps({"action": "error", "reason": f"timeout ({RUN_TIMEOUT}s)"}, ensure_ascii=False))
        sys.exit(1)

    # Obsidian sync
    if result.get("trade_id"):
        try:
            from maiupbit.integrations.obsidian import ObsidianSync
            sync = ObsidianSync()
            trades = journal.get_trades(days=1)
            latest = next((t for t in trades if t["trade_id"] == result["trade_id"]), None)
            if latest:
                sync.sync_trade(latest, journal)
        except Exception as exc:
            logger.warning("Failed to synchronize with Obsidian: %s", exc)

    # JSON output (MAIBOT response format)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()