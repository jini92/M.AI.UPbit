#!/usr/bin/env python3
"""모델 재학습 스크립트"""
import sys, os, json
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from maiupbit.exchange.upbit import UPbitExchange


def train(symbol: str = 'KRW-BTC', days: int = 90):
    """LSTM 모델 재학습"""
    exchange = UPbitExchange()
    hourly = exchange.get_ohlcv(symbol, 'minute60', count=days * 24)

    if hourly is None:
        print(json.dumps({'error': f'Failed to fetch data for {symbol}'}))
        return

    try:
        from maiupbit.models.lstm import LSTMPredictor

        model_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models')
        os.makedirs(model_dir, exist_ok=True)

        predictor = LSTMPredictor(lookback=720)
        result = predictor.train(hourly['close'].values.reshape(-1, 1))

        model_path = os.path.join(model_dir, f'{symbol.replace("-", "_").lower()}_lstm.h5')
        predictor.save(model_path)

        print(json.dumps({
            'status': 'success',
            'symbol': symbol,
            'model_path': model_path,
            'training_result': result,
            'timestamp': datetime.now().isoformat()
        }, ensure_ascii=False, indent=2, default=str))
    except ImportError:
        print(json.dumps({'error': 'tensorflow not installed. Run: pip install maiupbit[ml]'}))


if __name__ == '__main__':
    symbol = sys.argv[1] if len(sys.argv) > 1 else 'KRW-BTC'
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 90
    train(symbol, days)
