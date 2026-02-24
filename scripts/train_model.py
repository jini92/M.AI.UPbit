#!/usr/bin/env python3
"""모델 재학습 스크립트 — LSTM 또는 Transformer"""
import sys, os, json
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from maiupbit.exchange.upbit import UPbitExchange


def train(symbol: str = 'KRW-BTC', days: int = 90, model_type: str = 'transformer'):
    """모델 재학습

    Args:
        symbol: 종목 코드 (예: KRW-BTC)
        days: 학습 데이터 기간 (일)
        model_type: 'lstm' 또는 'transformer'
    """
    exchange = UPbitExchange()
    hourly = exchange.get_ohlcv(symbol, 'minute60', count=days * 24)

    if hourly is None or len(hourly) == 0:
        print(json.dumps({'error': f'Failed to fetch data for {symbol}'}))
        return

    model_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models')
    os.makedirs(model_dir, exist_ok=True)

    close_data = hourly['close'].values

    if model_type == 'transformer':
        try:
            from maiupbit.models.transformer import TransformerPredictor

            lookback = min(168, len(close_data) // 3)  # 7일 또는 데이터의 1/3
            predictor = TransformerPredictor(lookback=lookback, d_model=64, nhead=4, num_layers=2)
            result = predictor.train(close_data, epochs=50, batch_size=32)

            model_path = os.path.join(model_dir, f'{symbol.replace("-", "_").lower()}_transformer.pt')
            predictor.save(model_path)

        except ImportError:
            print(json.dumps({'error': 'torch not installed. Run: pip install maiupbit[transformer]'}))
            return

    elif model_type == 'lstm':
        try:
            from maiupbit.models.lstm import LSTMPredictor

            predictor = LSTMPredictor(lookback=720)
            result = predictor.train(close_data, epochs=100)

            model_path = os.path.join(model_dir, f'{symbol.replace("-", "_").lower()}_lstm.h5')
            predictor.save(model_path)

        except ImportError:
            print(json.dumps({'error': 'tensorflow not installed. Run: pip install maiupbit[lstm]'}))
            return
    else:
        print(json.dumps({'error': f'Unknown model type: {model_type}. Use "transformer" or "lstm"'}))
        return

    print(json.dumps({
        'status': 'success',
        'symbol': symbol,
        'model_type': model_type,
        'model_path': model_path,
        'data_points': len(close_data),
        'training_result': result,
        'timestamp': datetime.now().isoformat()
    }, ensure_ascii=False, indent=2, default=str))


if __name__ == '__main__':
    symbol = sys.argv[1] if len(sys.argv) > 1 else 'KRW-BTC'
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 90
    model_type = sys.argv[3] if len(sys.argv) > 3 else 'transformer'
    train(symbol, days, model_type)
