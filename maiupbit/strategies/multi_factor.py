from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from maiupbit.indicators.volatility import atr
from maiupbit.strategies.base import StrategyConfig


@dataclass
class MultiFactorConfig(StrategyConfig):
    """Multi-factor strategy configuration."""

    momentum_weight: float = 0.3
    quality_weight: float = 0.2
    volatility_weight: float = 0.2
    performance_weight: float = 0.3
    top_n: int = 5
    rebalance_days: int = 7


class MultiFactorStrategy:
    """Multi-factor ranking strategy (PortfolioStrategy compatible).

    Factors:
    - Momentum: 28-day return rate
    - Quality: Volume growth rate (recent vs prior period)
    - Volatility: ATR/price (lower is better)
    - Performance: 7-day return rate
    """

    def __init__(self, config: MultiFactorConfig | None = None) -> None:
        self.config = config or MultiFactorConfig()

    def _calculate_factors(
        self,
        data: dict[str, pd.DataFrame],
        date: pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Calculate factor values for each coin.

        Args:
            data: {symbol: OHLCV DataFrame}.
            date: Reference date.

        Returns:
            Factor value DataFrame (index=symbol).
        """
        factors = []
        for symbol, df in data.items():
            if date is not None:
                df = df.loc[:date]
            if len(df) < 30:
                continue

            close = df["close"]

            # Momentum: 28-day return rate
            mom_28 = close.pct_change(28).iloc[-1] if len(df) >= 29 else np.nan

            # Quality: Volume growth rate (recent 10d vs prior 10d)
            vol_recent = df["volume"].tail(10).mean()
            vol_prior = df["volume"].iloc[-20:-10].mean() if len(df) >= 20 else vol_recent
            quality = (vol_recent / vol_prior) if vol_prior > 0 else 1.0

            # Volatility: ATR/price (lower is better → use reciprocal)
            atr_val = atr(df["high"], df["low"], close, length=14).iloc[-1]
            price = close.iloc[-1]
            vol_factor = 1.0 / (atr_val / price) if atr_val > 0 and price > 0 else 0.0

            # Performance: 7-day return rate
            perf_7 = close.pct_change(7).iloc[-1] if len(df) >= 8 else np.nan

            factors.append({
                "symbol": symbol,
                "momentum": mom_28,
                "quality": quality,
                "volatility": vol_factor,
                "performance": perf_7,
            })

        if not factors:
            return pd.DataFrame()
        return pd.DataFrame(factors).set_index("symbol")

    @staticmethod
    def _zscore(series: pd.Series) -> pd.Series:
        """Z-score normalization."""
        std = series.std()
        if std == 0 or np.isnan(std):
            return pd.Series(0.0, index=series.index)
        return (series - series.mean()) / std

    def rank_coins(
        self,
        data: dict[str, pd.DataFrame],
        date: pd.Timestamp | None = None,
    ) -> list[dict]:
        """Multi-factor based coin ranking.

        Args:
            data: {symbol: OHLCV DataFrame}.
            date: Reference date.

        Returns:
            [{"symbol", "composite_score", "momentum", "quality", "volatility", "performance", "rank"}].
        """
        factors = self._calculate_factors(data, date)
        if factors.empty:
            return []

        # Z-score normalization
        z_scores = pd.DataFrame(index=factors.index)
        z_scores["momentum"] = self._zscore(factors["momentum"])
        z_scores["quality"] = self._zscore(factors["quality"])
        z_scores["volatility"] = self._zscore(factors["volatility"])
        z_scores["performance"] = self._zscore(factors["performance"])

        # Composite score
        composite = (
            z_scores["momentum"] * self.config.momentum_weight
            + z_scores["quality"] * self.config.quality_weight
            + z_scores["volatility"] * self.config.volatility_weight
            + z_scores["performance"] * self.config.performance_weight
        )

        results = []
        for symbol in composite.sort_values(ascending=False).index:
            results.append({
                "symbol": symbol,
                "composite_score": round(float(composite[symbol]), 4),
                "momentum": round(float(factors.loc[symbol, "momentum"]), 6)
                if not np.isnan(factors.loc[symbol, "momentum"])
                else None,
                "quality": round(float(factors.loc[symbol, "quality"]), 4),
                "volatility": round(float(factors.loc[symbol, "volatility"]), 4),
                "performance": round(float(factors.loc[symbol, "performance"]), 6)
                if not np.isnan(factors.loc[symbol, "performance"])
                else None,
            })

        for i, r in enumerate(results):
            r["rank"] = i + 1
        return results

    def allocate(
        self,
        data: dict[str, pd.DataFrame],
        date: pd.Timestamp | None = None,
    ) -> dict[str, float]:
        """Multi-factor ranking based equal-weight allocation.

        Args:
            data: {symbol: OHLCV DataFrame}.
            date: Reference date.

        Returns:
            {symbol: weight} top N equally weighted.
        """
        rankings = self.rank_coins(data, date)
        selected = rankings[: self.config.top_n]

        if not selected:
            return {}

        weight = round(1.0 / len(selected), 4)
        return {r["symbol"]: weight for r in selected}