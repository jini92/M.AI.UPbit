#!/usr/bin/env python3
"""OpenClaw HEARTBEAT용 시장 모니터링"""
import sys, os, json
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from maiupbit.exchange.upbit import UPbitExchange
from maiupbit.indicators import trend, momentum, volatility


def monitor(symbols: list[str] = None, threshold: float = 5.0) -> dict:
    """관심 코인 모니터링. threshold% 이상 변동 시 알림 대상"""
    exchange = UPbitExchange()

    if not symbols:
        symbols = ['KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-SOL', 'KRW-DOGE']

    alerts = []
    status = []

    for symbol in symbols:
        try:
            daily = exchange.get_ohlcv(symbol, 'day', count=2)
            if daily is None or len(daily) < 2:
                continue

            prev_close = daily.iloc[-2]['close']
            curr_close = daily.iloc[-1]['close']
            change_pct = (curr_close - prev_close) / prev_close * 100

            hourly = exchange.get_ohlcv(symbol, 'minute60', count=24)
            if hourly is not None and len(hourly) >= 14:
                rsi_val = momentum.rsi(hourly['close'], 14).iloc[-1]
            else:
                rsi_val = None

            coin_status = {
                'symbol': symbol,
                'price': curr_close,
                'change_pct': round(change_pct, 2),
                'rsi': round(rsi_val, 1) if rsi_val else None
            }
            status.append(coin_status)

            if abs(change_pct) >= threshold:
                direction = '급등' if change_pct > 0 else '급락'
                alerts.append({
                    'symbol': symbol,
                    'type': direction,
                    'change_pct': round(change_pct, 2),
                    'price': curr_close
                })

            if rsi_val and (rsi_val > 80 or rsi_val < 20):
                zone = '과매수' if rsi_val > 80 else '과매도'
                alerts.append({
                    'symbol': symbol,
                    'type': f'RSI {zone}',
                    'rsi': round(rsi_val, 1),
                    'price': curr_close
                })
        except Exception as e:
            continue

    return {'status': status, 'alerts': alerts, 'has_alerts': len(alerts) > 0}


if __name__ == '__main__':
    symbols = sys.argv[1:] if len(sys.argv) > 1 else None
    result = monitor(symbols)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
