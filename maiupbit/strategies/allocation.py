"""GTAA Dynamic Asset Allocation Strategy.

Kwang Hwan Gu GTAA (Global Tactical Asset Allocation) Framework:
- Invest only in assets with positive momentum, hold cash if negative
- SMA Filter: Only invest in assets where current price > SMA(200)
- Allocate equally among the top N assets
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from maiupbit.indicators.momentum import momentum_score
from maiupbit.strategies.base import StrategyConfig


@dataclass
class GTAAConfig(StrategyConfig):
    """GTAA Asset Allocation Strategy Configuration."""

    momentum_periods: list[int] = field(default_factory=lambda: [28, 84, 168])
    momentum_weights: list[float] = field(default_factory=lambda: [6, 3, 1])
    sma_filter: int = 200
    max_positions: int = 5
    rebalance_days: int = 7


class GTAAStrategy:
    """GTAA Dynamic Asset Allocation Strategy (PortfolioStrategy compatible).

    Selection Criteria:
    1) Positive momentum score
    2) Current price > SMA(sma_filter)
    3) Top max_positions assets based on momentum score
    4) Equal-weight allocation
    """

    def __init__(self, config: GTAAConfig | None = None) -> None:
        self.config = config or GTAAConfig()

    def _evaluate_asset(
        self,
        symbol: str,
        df: pd.DataFrame,
        date: pd.Timestamp | None = None,
    ) -> dict | None:
        """Evaluate individual asset.

        Args:
            symbol: Symbol code.
            df: OHLCV DataFrame.
            date: Reference date.

        Returns:
            {"symbol", "score", "above_sma"} or None.
        """
        if date is not None:
            df = df.loc[:date]

        min_required = max(
            max(self.config.momentum_periods),
            self.config.sma_filter,
        )
        if len(df) < min_required:
            return None

        close = df["close"]

        score = momentum_score(
            close,
            periods=self.config.momentum_periods,
            weights=self.config.momentum_weights,
        ).iloc[-1]

        if np.isnan(score) or score <= 0:
            return None

        # SMA filter
        sma_val = close.rolling(self.config.sma_filter).mean().iloc[-1]
        if np.isnan(sma_val) or close.iloc[-1] < sma_val:
            return None

        return {
            "symbol": symbol,
            "score": float(score),
            "above_sma": True,
        }

    def allocate(
        self,
        data: dict[str, pd.DataFrame],
        date: pd.Timestamp | None = None,
    ) -> dict[str, float]:
        """GTAA Dynamic Asset Allocation.

        Args:
            data: {symbol: OHLCV DataFrame}.
            date: Reference date.

        Returns:
            {symbol: weight} equal-weight allocation.
        """
        candidates = []
        for symbol, df in data.items():
            result = self._evaluate_asset(symbol, df, date)
            if result is not None:
                candidates.append(result)

        candidates.sort(key=lambda x: x["score"], reverse=True)
        selected = candidates[: self.config.max_positions]

        if not selected:
            return {}

        weight = round(1.0 / len(selected), 4)
        return {c["symbol"]: weight for c in selected}