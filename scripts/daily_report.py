#!/usr/bin/env python3
"""OpenClaw daily analysis report generation"""
import sys, os, json, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from maiupbit.exchange.upbit import UPbitExchange
from maiupbit.analysis.technical import TechnicalAnalyzer


def _get_knowledge_context(symbols: list[str]) -> str:
    """Retrieve Mnemo knowledge context (graceful degradation)."""
    try:
        from maiupbit.analysis.knowledge import KnowledgeProvider
        kp = KnowledgeProvider()
        if not kp.is_available():
            return ""
        # Search based on the first symbol
        return kp.enrich_llm_context(symbols[0], top_k=3, timeout=20)
    except Exception:  # noqa: BLE001
        return ""


def daily_report(symbols: list[str] = None) -> dict:
    """Generate daily analysis report"""
    exchange = UPbitExchange(
        access_key=os.getenv('UPBIT_ACCESS_KEY'),
        secret_key=os.getenv('UPBIT_SECRET_KEY')
    )
    analyzer = TechnicalAnalyzer(exchange)

    if not symbols:
        symbols = ['KRW-BTC', 'KRW-ETH', 'KRW-XRP']

    report = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'portfolio': None,
        'analysis': [],
        'recommendations': []
    }

    # Portfolio
    if os.getenv('UPBIT_ACCESS_KEY'):
        try:
            report['portfolio'] = exchange.get_portfolio()
        except Exception:
            pass

    # Analysis for each coin
    for symbol in symbols:
        try:
            daily = exchange.get_ohlcv(symbol, 'day', count=30)
            if daily is not None:
                analysis = analyzer.analyze(symbol, daily)
                analysis['symbol'] = symbol
                analysis['current_price'] = exchange.get_current_price(symbol)
                report['analysis'].append(analysis)
        except Exception:
            continue

    # Mnemo knowledge context
    knowledge = _get_knowledge_context(symbols or ['KRW-BTC'])
    if knowledge:
        report['knowledge_enriched'] = True
        report['knowledge_source'] = "Mnemo (MAISECONDBRAIN)"
        report['knowledge_context'] = knowledge[:500]  # Summary for the report

    return report


if __name__ == '__main__':
    symbols = sys.argv[1:] if len(sys.argv) > 1 else None
    result = daily_report(symbols)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))