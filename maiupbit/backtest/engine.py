"""백테스팅 엔진"""
from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Protocol


class Strategy(Protocol):
    """전략 프로토콜 — signal() 메서드만 구현하면 됨"""

    def signal(self, data: pd.DataFrame) -> int:
        """매매 시그널 생성.

        Args:
            data: 현재까지의 OHLCV + 지표 데이터

        Returns:
            1=buy, -1=sell, 0=hold
        """
        ...


class BacktestEngine:
    """백테스트 엔진

    Usage:
        engine = BacktestEngine(initial_capital=1_000_000)
        result = engine.run(data, my_strategy)
        print(result['total_return'], result['sharpe_ratio'])
    """

    def __init__(self, initial_capital: float = 1_000_000) -> None:
        self.initial_capital = initial_capital

    def run(self, data: pd.DataFrame, strategy: Strategy) -> dict:
        """백테스트 실행.

        Args:
            data: OHLCV DataFrame (close 컬럼 필수)
            strategy: Strategy 프로토콜 구현체

        Returns:
            dict: {total_return, sharpe_ratio, max_drawdown, num_trades, trades, final_equity}
        """
        capital = self.initial_capital
        position = 0.0
        trades: list[dict] = []
        equity: list[float] = []

        for i in range(len(data)):
            sig = strategy.signal(data.iloc[: i + 1])
            price = data.iloc[i]["close"]

            if sig == 1 and position == 0:
                position = capital / price
                capital = 0.0
                trades.append({"type": "buy", "price": price, "index": i})
            elif sig == -1 and position > 0:
                capital = position * price
                position = 0.0
                trades.append({"type": "sell", "price": price, "index": i})

            equity.append(capital + position * price)

        equity_series = pd.Series(equity, index=data.index)
        total_return = (equity[-1] - self.initial_capital) / self.initial_capital * 100

        returns = equity_series.pct_change().dropna()
        sharpe = float(
            (returns.mean() / returns.std() * (252**0.5))
            if returns.std() > 0
            else 0
        )

        peak = equity_series.cummax()
        drawdown = (equity_series - peak) / peak
        mdd = float(drawdown.min() * 100)

        return {
            "total_return": round(total_return, 2),
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown": round(mdd, 2),
            "num_trades": len(trades),
            "trades": trades,
            "final_equity": round(equity[-1], 0),
        }
