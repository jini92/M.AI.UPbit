#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""?먮룞留ㅻℓ ?ㅽ뻾 ?ㅽ겕由쏀듃 (?щ줎??.

留ㅼ씪 07:00 + 19:00 KST ?ㅽ뻾.
遺꾩꽍 ??留ㅻℓ 寃곗젙 ???ㅽ뻾 ??湲곕줉 ??Obsidian ?숆린??

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
    parser = argparse.ArgumentParser(description="M.AI.UPbit ?먮룞留ㅻℓ")
    parser.add_argument("--symbol", default="KRW-BTC", help="嫄곕옒 ?щ낵")
    parser.add_argument("--dry-run", action="store_true", help="遺꾩꽍留?(留ㅻℓ ????")
    parser.add_argument("--provider", default=None, help="LLM provider (openai/ollama)")
    args = parser.parse_args()

    access_key = os.getenv("UPBIT_ACCESS_KEY")
    secret_key = os.getenv("UPBIT_SECRET_KEY")

    if not access_key or not secret_key:
        print(json.dumps({"error": "UPBIT_ACCESS_KEY/SECRET_KEY ?꾩슂"}))
        sys.exit(1)

    # Exchange
    from maiupbit.exchange.upbit import UPbitExchange
    exchange = UPbitExchange(access_key=access_key, secret_key=secret_key)

    # Journal
    from maiupbit.trading.journal import TradeJournal
    journal = TradeJournal(path="trade_journal.json")

    # LLM (optional)
    llm = None
    try:
        from maiupbit.analysis.llm import LLMAnalyzer
        provider = args.provider or os.getenv("LLM_PROVIDER", "ollama")
        llm = LLMAnalyzer(provider=provider)
        logger.info("LLM 珥덇린?? %s (%s)", provider, llm.model)
    except Exception as exc:
        logger.warning("LLM 珥덇린???ㅽ뙣 (湲곗닠吏???대갚): %s", exc)

    # Knowledge (optional)
    knowledge = None
    try:
        from maiupbit.analysis.knowledge import KnowledgeProvider
        knowledge = KnowledgeProvider()
        if knowledge.is_available():
            logger.info("Mnemo KnowledgeProvider ?쒖꽦??)
        else:
            knowledge = None
            logger.info("Mnemo 誘몄꽕移?(吏???놁씠 吏꾪뻾)")
    except Exception as exc:
        logger.debug("KnowledgeProvider 珥덇린???ㅽ뙣: %s", exc)

    # AutoTrader
    from maiupbit.trading.auto_trader import AutoTrader
    trader = AutoTrader(
        exchange=exchange,
        journal=journal,
        llm_analyzer=llm,
        knowledge_provider=knowledge,
    )

    # ?ㅽ뻾
    result = trader.run(symbol=args.symbol, dry_run=args.dry_run)

    # Obsidian ?숆린??    if result.get("trade_id"):
        try:
            from maiupbit.integrations.obsidian import ObsidianSync
            sync = ObsidianSync()
            trades = journal.get_trades(days=1)
            latest = next((t for t in trades if t["trade_id"] == result["trade_id"]), None)
            if latest:
                sync.sync_trade(latest, journal)
        except Exception as exc:
            logger.warning("Obsidian ?숆린???ㅽ뙣: %s", exc)

    # JSON 異쒕젰 (MAIBOT ?щ줎 ?뚯떛??
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()

