"""Risk management module.

Kwang Hwan Gu risk management framework:
- ATR-based position sizing
- Kelly formula (optimal investment ratio)
- MDD tiered de-leveraging
- Maximum weight limit
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from maiupbit.indicators.volatility import atr
from maiupbit.strategies.base import StrategyConfig


@dataclass
class RiskConfig(StrategyConfig):
    """Risk management settings."""

    max_position: float = 0.2
    risk_per_trade: float = 0.02
    mdd_tiers: list[dict] = field(
        default_factory=lambda: [
            {"threshold": -0.10, "multiplier": 0.75},
            {"threshold": -0.20, "multiplier": 0.50},
            {"threshold": -0.30, "multiplier": 0.25},
            {"threshold": -0.40, "multiplier": 0.00},
        ]
    )
    kelly_fraction: float = 0.25  # Kelly's 1/4 (conservative)


class RiskManager:
    """Risk manager (for combination).

    Applies risk management to the distribution results of other strategies.

    Usage:
        allocations = momentum.allocate(data)
        allocations = risk.apply_equal_weight_constraint(allocations)
        allocations = risk.apply_mdd_rule(allocations, equity_curve)
    """

    def __init__(self, config: RiskConfig | None = None) -> None:
        self.config = config or RiskConfig()

    def atr_position_size(
        self,
        capital: float,
        data: pd.DataFrame,
        length: int = 14,
    ) -> float:
        """ATR-based position size calculation.

        Args:
            capital: Current capital.
            data: OHLCV DataFrame.
            length: ATR period.

        Returns:
            Investment amount.
        """
        if len(data) < length + 1:
            return capital * self.config.risk_per_trade

        atr_val = atr(data["high"], data["low"], data["close"], length=length).iloc[-1]
        price = data["close"].iloc[-1]

        if np.isnan(atr_val) or atr_val <= 0 or price <= 0:
            return capital * self.config.risk_per_trade

        risk_amount = capital * self.config.risk_per_trade
        position = risk_amount / atr_val * price
        max_allowed = capital * self.config.max_position
        return min(position, max_allowed)

    def kelly_from_history(self, trades: list[dict]) -> float:
        """Calculate Kelly ratio from historical trade history.

        Args:
            trades: [{"type": "buy"/"sell", "price": float}] list.

        Returns:
            Kelly ratio (0~1). Negative returns 0.
        """
        if len(trades) < 4:
            return self.config.kelly_fraction

        profits = []
        for i in range(0, len(trades) - 1, 2):
            if trades[i]["type"] == "buy" and trades[i + 1]["type"] == "sell":
                ret = (trades[i + 1]["price"] - trades[i]["price"]) / trades[i][
                    "price"
                ]
                profits.append(ret)

        if not profits:
            return self.config.kelly_fraction

        wins = [p for p in profits if p > 0]
        losses = [p for p in profits if p < 0]

        if not wins or not losses:
            return self.config.kelly_fraction

        win_rate = len(wins) / len(profits)
        avg_win = np.mean(wins)
        avg_loss = abs(np.mean(losses))

        if avg_loss == 0:
            return self.config.kelly_fraction

        # Kelly formula: f = W - (1-W)/R, R = avg_win/avg_loss
        r = avg_win / avg_loss
        kelly = win_rate - (1 - win_rate) / r

        # Conservative application (1/4 Kelly)
        result = max(0.0, kelly * self.config.kelly_fraction / 0.25)
        return round(min(result, 1.0), 4)

    @staticmethod
    def calc_current_mdd(equity: pd.Series) -> float:
        """Calculate current MDD.

        Args:
            equity: Asset value time series.

        Returns:
            Current MDD (negative, e.g., -0.15 = 15% decline).
        """
        if len(equity) < 2:
            return 0.0
        peak = equity.cummax()
        drawdown = (equity - peak) / peak
        return float(drawdown.iloc[-1])

    def get_mdd_multiplier(self, mdd: float) -> float:
        """Retrieve position multiplier based on MDD.

        Args:
            mdd: Current MDD (negative).

        Returns:
            Position multiplier (0.0~1.0).
        """
        multiplier = 1.0
        for tier in self.config.mdd_tiers:
            if mdd <= tier["threshold"]:
                multiplier = min(multiplier, tier["multiplier"])
        return multiplier

    def apply_mdd_rule(
        self,
        allocations: dict[str, float],
        equity: pd.Series,
    ) -> dict[str, float]:
        """Reduce allocation weights according to MDD rule.

        Args:
            allocations: {symbol: weight} original distribution.
            equity: Asset value time series.

        Returns:
            MDD adjusted {symbol: weight}.
        """
        if not allocations or len(equity) < 2:
            return allocations

        mdd = self.calc_current_mdd(equity)
        multiplier = self.get_mdd_multiplier(mdd)

        if multiplier >= 1.0:
            return allocations

        return {
            symbol: round(weight * multiplier, 4)
            for symbol, weight in allocations.items()
        }

    def apply_equal_weight_constraint(
        self,
        allocations: dict[str, float],
    ) -> dict[str, float]:
        """Apply maximum weight limit.

        Args:
            allocations: {symbol: weight}.

        Returns:
            Limit applied {symbol: weight}.
        """
        if not allocations:
            return allocations

        constrained = {}
        excess = 0.0
        uncapped_count = 0

        # First pass: accumulate overages
        for symbol, weight in allocations.items():
            if weight > self.config.max_position:
                constrained[symbol] = self.config.max_position
                excess += weight - self.config.max_position
            else:
                constrained[symbol] = weight
                uncapped_count += 1

        # Second pass: redistribute overages
        if excess > 0 and uncapped_count > 0:
            add_per = excess / uncapped_count
            for symbol in constrained:
                if constrained[symbol] < self.config.max_position:
                    new_weight = constrained[symbol] + add_per
                    constrained[symbol] = round(
                        min(new_weight, self.config.max_position), 4
                    )

        return constrained