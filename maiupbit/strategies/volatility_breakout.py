"""Volatility breakout strategy.

Adapted Larry Williams volatility breakout to Kang Whan Guk method:
- Buy when the current open price + previous day's range × k breaks out
- Noise ratio filter + MA filter
- ATR based position sizing
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from maiupbit.indicators.volatility import atr, noise_ratio
from maiupbit.strategies.base import StrategyConfig


@dataclass
class VolatilityBreakoutConfig(StrategyConfig):
    """Volatility breakout strategy configuration."""

    k: float = 0.5
    noise_threshold: float = 0.6
    ma_filter: int = 20
    risk_per_trade: float = 0.02
    auto_k: bool = True
    k_search_range: list[float] = field(default_factory=lambda: [round(0.1 * i, 1) for i in range(1, 11)])


class VolatilityBreakoutStrategy:
    """Volatility breakout strategy (QuantStrategy compatible).

    Usage:
        strategy = VolatilityBreakoutStrategy()
        engine = BacktestEngine()
        result = engine.run(data, strategy)
    """

    def __init__(self, config: VolatilityBreakoutConfig | None = None) -> None:
        self.config = config or VolatilityBreakoutConfig()
        self._in_position = False

    def signal(self, data: pd.DataFrame) -> int:
        """Volatility breakout trading signal.

        Args:
            data: OHLCV DataFrame (open, high, low, close required).

        Returns:
            1=buy, -1=sell, 0=hold.
        """
        if len(data) < 3:
            return 0

        # Auto-optimize k from recent data if enabled
        k = self.config.k
        if self.config.auto_k and len(data) >= 30:
            optimal = self.find_optimal_k(data.iloc[:-1], self.config.k_search_range)
            if optimal:
                best_k = max(optimal, key=optimal.get)
                if optimal[best_k] > 0:
                    k = best_k

        today = data.iloc[-1]
        yesterday = data.iloc[-2]

        prev_range = yesterday["high"] - yesterday["low"]
        breakout_price = today["open"] + prev_range * k

        # MA filter
        if self.config.ma_filter > 0 and len(data) >= self.config.ma_filter:
            ma = data["close"].rolling(self.config.ma_filter).mean().iloc[-1]
            if today["close"] < ma:
                if self._in_position:
                    self._in_position = False
                    return -1
                return 0

        # Noise filter
        if len(data) >= 20:
            nr = noise_ratio(
                data["open"], data["high"], data["low"], data["close"], length=20
            ).iloc[-1]
            if not np.isnan(nr) and nr > self.config.noise_threshold:
                if self._in_position:
                    self._in_position = False
                    return -1
                return 0

        # Breakout buy
        if not self._in_position and today["high"] >= breakout_price:
            self._in_position = True
            return 1

        # Close position at the end of the day (sell at next open)
        if self._in_position:
            self._in_position = False
            return -1

        return 0

    def calculate_position_size(
        self,
        capital: float,
        data: pd.DataFrame,
    ) -> float:
        """Calculate position size based on ATR.

        Args:
            capital: Current capital.
            data: OHLCV DataFrame.

        Returns:
            Investment amount.
        """
        if len(data) < 15:
            return capital * self.config.risk_per_trade

        atr_val = atr(data["high"], data["low"], data["close"], length=14).iloc[-1]
        if np.isnan(atr_val) or atr_val <= 0:
            return capital * self.config.risk_per_trade

        price = data["close"].iloc[-1]
        risk_amount = capital * self.config.risk_per_trade
        position_size = risk_amount / atr_val * price
        return min(position_size, capital)

    @staticmethod
    def find_optimal_k(
        data: pd.DataFrame,
        k_range: list[float] | None = None,
    ) -> dict:
        """Search for optimal k value through backtesting.

        Args:
            data: OHLCV DataFrame.
            k_range: List of k values to search.

        Returns:
            {k: return_pct} dictionary.
        """
        if k_range is None:
            k_range = [round(0.1 * i, 1) for i in range(1, 11)]

        results = {}
        for k in k_range:
            capital = 1_000_000.0
            for i in range(2, len(data)):
                prev_range = data.iloc[i - 1]["high"] - data.iloc[i - 1]["low"]
                breakout = data.iloc[i]["open"] + prev_range * k
                if data.iloc[i]["high"] >= breakout:
                    buy_price = breakout
                    sell_price = data.iloc[i]["close"]
                    capital *= sell_price / buy_price
            ret = (capital - 1_000_000) / 1_000_000 * 100
            results[k] = round(ret, 2)
        return results