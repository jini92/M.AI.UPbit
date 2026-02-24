#!/usr/bin/env python3
"""OpenClaw용 일일 분석 리포트 생성"""
import sys, os, json, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from maiupbit.exchange.upbit import UPbitExchange
from maiupbit.analysis.technical import TechnicalAnalyzer


def _get_knowledge_context(symbols: list[str]) -> str:
    """Mnemo 지식 컨텍스트 조회 (graceful degradation)."""
    try:
        from maiupbit.analysis.knowledge import KnowledgeProvider
        kp = KnowledgeProvider()
        if not kp.is_available():
            return ""
        # 첫 번째 심볼 기준으로 검색
        return kp.enrich_llm_context(symbols[0], top_k=3, timeout=20)
    except Exception:  # noqa: BLE001
        return ""


def daily_report(symbols: list[str] = None) -> dict:
    """일일 분석 리포트 생성"""
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

    # 포트폴리오
    if os.getenv('UPBIT_ACCESS_KEY'):
        try:
            report['portfolio'] = exchange.get_portfolio()
        except Exception:
            pass

    # 각 코인 분석
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

    # Mnemo 지식 컨텍스트
    knowledge = _get_knowledge_context(symbols or ['KRW-BTC'])
    if knowledge:
        report['knowledge_enriched'] = True
        report['knowledge_source'] = "Mnemo (MAISECONDBRAIN)"
        report['knowledge_context'] = knowledge[:500]  # 리포트용 요약

    return report


if __name__ == '__main__':
    symbols = sys.argv[1:] if len(sys.argv) > 1 else None
    result = daily_report(symbols)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
