"""Dual Momentum Strategy.

Kwang Hwan Gu Dual Momentum Framework:
- Absolute Momentum: Return > 0 (only positive momentum investments)
- Relative Momentum: Compare momentum scores between coins → Top N
- Average Momentum Signal: 12 period average momentum signal → Position weight
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from maiupbit.indicators.momentum import momentum_score, average_momentum_signal
from maiupbit.strategies.base import StrategyConfig


@dataclass
class DualMomentumConfig(StrategyConfig):
    """Dual Momentum strategy configuration."""

    score_periods: list[int] = field(default_factory=lambda: [28, 84, 168, 365])
    score_weights: list[float] = field(default_factory=lambda: [12, 4, 2, 1])
    abs_threshold: float = 0.0
    top_n: int = 5
    rebalance_days: int = 7


class DualMomentumStrategy:
    """Dual Momentum Strategy (compatible with QuantStrategy and PortfolioStrategy).

    Single symbol: signal() → BacktestEngine
    Multiple symbols: allocate() → PortfolioBacktestEngine
    """

    def __init__(self, config: DualMomentumConfig | None = None) -> None:
        self.config = config or DualMomentumConfig()

    def signal(self, data: pd.DataFrame) -> int:
        """Single symbol absolute momentum signal.

        Args:
            data: OHLCV DataFrame.

        Returns:
            1=buy (positive momentum), -1=sell (negative momentum), 0=hold.
        """
        if len(data) < max(self.config.score_periods):
            return 0

        score = momentum_score(
            data["close"],
            periods=self.config.score_periods,
            weights=self.config.score_weights,
        ).iloc[-1]

        if score > self.config.abs_threshold:
            return 1
        elif score < -self.config.abs_threshold:
            return -1
        return 0

    def rank_coins(
        self,
        data: dict[str, pd.DataFrame],
        date: pd.Timestamp | None = None,
    ) -> list[dict]:
        """Coin momentum ranking.

        Args:
            data: {symbol: OHLCV DataFrame} dictionary.
            date: Reference date (None for latest).

        Returns:
            [{"symbol", "score", "avg_signal", "rank"}] list (sorted by score descending).
        """
        rankings = []
        for symbol, df in data.items():
            if date is not None:
                df = df.loc[:date]
            if len(df) < max(self.config.score_periods):
                continue

            score = momentum_score(
                df["close"],
                periods=self.config.score_periods,
                weights=self.config.score_weights,
            ).iloc[-1]

            avg_sig = average_momentum_signal(df["close"]).iloc[-1]

            rankings.append({
                "symbol": symbol,
                "score": round(float(score), 6),
                "avg_signal": round(float(avg_sig), 4),
            })

        rankings.sort(key=lambda x: x["score"], reverse=True)
        for i, r in enumerate(rankings):
            r["rank"] = i + 1
        return rankings

    def allocate(
        self,
        data: dict[str, pd.DataFrame],
        date: pd.Timestamp | None = None,
    ) -> dict[str, float]:
        """Dual Momentum based asset allocation.

        1) Absolute momentum filter: score > threshold
        2) Relative momentum: Top N selection
        3) Average momentum signal for weight calculation

        Args:
            data: {symbol: OHLCV DataFrame}.
            date: Reference date.

        Returns:
            {symbol: weight} (sum <= 1.0).
        """
        rankings = self.rank_coins(data, date)

        # Absolute momentum filter
        positive = [r for r in rankings if r["score"] > self.config.abs_threshold]

        # Top N selection
        selected = positive[: self.config.top_n]

        if not selected:
            return {}

        # Average momentum signal for weight calculation
        total_signal = sum(r["avg_signal"] for r in selected)
        if total_signal <= 0:
            return {}

        allocations = {}
        for r in selected:
            weight = r["avg_signal"] / total_signal
            allocations[r["symbol"]] = round(weight, 4)

        return allocations