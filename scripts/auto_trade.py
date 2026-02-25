#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""자동매매 실행 스크립트 (크론용).

매일 07:00 + 19:00 KST 실행.
분석 → 매매 결정 → 실행 → 기록 → Obsidian 동기화.

Usage:
    python scripts/auto_trade.py [--symbol KRW-BTT] [--dry-run] [--provider ollama]
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
    parser = argparse.ArgumentParser(description="M.AI.UPbit 자동매매")
    parser.add_argument("--symbol", default="KRW-BTT", help="거래 심볼")
    parser.add_argument("--dry-run", action="store_true", help="분석만 (매매 안 함)")
    parser.add_argument("--provider", default=None, help="LLM provider (openai/ollama)")
    args = parser.parse_args()

    access_key = os.getenv("UPBIT_ACCESS_KEY")
    secret_key = os.getenv("UPBIT_SECRET_KEY")

    if not access_key or not secret_key:
        print(json.dumps({"error": "UPBIT_ACCESS_KEY/SECRET_KEY 필요"}))
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
        logger.info("LLM 초기화: %s (%s)", provider, llm.model)
    except Exception as exc:
        logger.warning("LLM 초기화 실패 (기술지표 폴백): %s", exc)

    # Knowledge (optional)
    knowledge = None
    try:
        from maiupbit.analysis.knowledge import KnowledgeProvider
        knowledge = KnowledgeProvider()
        if knowledge.is_available():
            logger.info("Mnemo KnowledgeProvider 활성화")
        else:
            knowledge = None
            logger.info("Mnemo 미설치 (지식 없이 진행)")
    except Exception as exc:
        logger.debug("KnowledgeProvider 초기화 실패: %s", exc)

    # AutoTrader
    from maiupbit.trading.auto_trader import AutoTrader
    trader = AutoTrader(
        exchange=exchange,
        journal=journal,
        llm_analyzer=llm,
        knowledge_provider=knowledge,
    )

    # 실행
    result = trader.run(symbol=args.symbol, dry_run=args.dry_run)

    # Obsidian 동기화
    if result.get("trade_id"):
        try:
            from maiupbit.integrations.obsidian import ObsidianSync
            sync = ObsidianSync()
            trades = journal.get_trades(days=1)
            latest = next((t for t in trades if t["trade_id"] == result["trade_id"]), None)
            if latest:
                sync.sync_trade(latest, journal)
        except Exception as exc:
            logger.warning("Obsidian 동기화 실패: %s", exc)

    # JSON 출력 (MAIBOT 크론 파싱용)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
