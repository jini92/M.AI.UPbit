"""CI Weekly Report Generator - runs in GitHub Actions without GUI dependencies"""
import json, sys, os
sys.path.insert(0, os.getcwd())

import pyupbit
from maiupbit.strategies.momentum import DualMomentumStrategy
from maiupbit.strategies.multi_factor import MultiFactorStrategy
from maiupbit.strategies.seasonal import SeasonalFilter
from datetime import datetime

SYMBOLS = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-DOT",
           "KRW-AVAX", "KRW-LINK", "KRW-ADA", "KRW-DOGE"]


class DataFetcher:
    """Simple pyupbit-based OHLCV fetcher."""
    def fetch_ohlcv(self, symbol: str, count: int = 200):
        return pyupbit.get_ohlcv(symbol, count=count)


fetcher = DataFetcher()
seasonal = SeasonalFilter()
momentum = DualMomentumStrategy()
factor = MultiFactorStrategy()

season_info = seasonal.get_season_info()

# Momentum ranking
mom_scores = {}
for sym in SYMBOLS:
    try:
        df = fetcher.fetch_ohlcv(sym, count=200)
        score = momentum.calculate_momentum_score(df)
        mom_scores[sym] = float(score)
    except:
        pass

mom_rank = sorted(mom_scores.items(), key=lambda x: x[1], reverse=True)

report = {
    "date": datetime.now().strftime("%Y-%m-%d"),
    "season": season_info,
    "momentum_top5": [{"symbol": s, "score": round(v,4)} for s,v in mom_rank[:5]],
    "signal": "CASH" if all(v < 0 for v in mom_scores.values()) else "INVEST",
    "top_coin": mom_rank[0][0] if mom_rank else "N/A"
}

print(json.dumps(report, ensure_ascii=False, indent=2))
