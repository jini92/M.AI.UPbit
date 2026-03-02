"""Season/Cycle timing filter.

Kwang Hwan Kuk's seasonal strategy:
- Bullish from October to April (increase weight)
- Bearish from May to September (decrease weight)
- Refer to Bitcoin halving cycle
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from maiupbit.strategies.base import StrategyConfig

# Bitcoin halving dates
HALVING_DATES = [
    datetime(2012, 11, 28),
    datetime(2016, 7, 9),
    datetime(2020, 5, 11),
    datetime(2024, 4, 19),
    # Estimated
    datetime(2028, 4, 1),
]

# Monthly seasonality (January to December)
MONTHLY_SEASONALITY: dict[int, str] = {
    1: "bullish",
    2: "bullish",
    3: "bullish",
    4: "bullish",
    5: "bearish",
    6: "bearish",
    7: "bearish",
    8: "bearish",
    9: "bearish",
    10: "bullish",
    11: "bullish",
    12: "bullish",
}


@dataclass
class SeasonalConfig(StrategyConfig):
    """Season filter settings."""

    bullish_months: list[int] = field(
        default_factory=lambda: [10, 11, 12, 1, 2, 3, 4]
    )
    bearish_months: list[int] = field(default_factory=lambda: [5, 6, 7, 8, 9])
    bullish_multiplier: float = 1.2
    bearish_multiplier: float = 0.7
    halving_boost: float = 1.3
    halving_window_days: int = 365


class SeasonalFilter:
    """Season/halving timing filter (for combination).

    Applies seasonal adjustments to the distribution results of other strategies.

    Usage:
        allocations = momentum.allocate(data)
        allocations = seasonal.adjust_allocations(allocations, datetime.now())
    """

    def __init__(self, config: SeasonalConfig | None = None) -> None:
        self.config = config or SeasonalConfig()

    def get_season_info(self, date: datetime | None = None) -> dict:
        """Retrieve current season information.

        Args:
            date: Reference date (None means now).

        Returns:
            {"month", "season", "multiplier", "halving_phase", "days_since_halving",
             "next_halving", "days_to_next_halving"}.
        """
        if date is None:
            date = datetime.now()

        month = date.month
        season = MONTHLY_SEASONALITY.get(month, "neutral")
        multiplier = (
            self.config.bullish_multiplier
            if month in self.config.bullish_months
            else self.config.bearish_multiplier
        )

        # Halving analysis
        halving_phase = "unknown"
        days_since = None
        next_halving = None
        days_to_next = None

        past_halvings = [h for h in HALVING_DATES if h <= date]
        future_halvings = [h for h in HALVING_DATES if h > date]

        if past_halvings:
            last_halving = past_halvings[-1]
            days_since = (date - last_halving).days

            if days_since <= self.config.halving_window_days:
                halving_phase = "post_halving_bull"
            elif days_since <= self.config.halving_window_days * 2:
                halving_phase = "mid_cycle"
            else:
                halving_phase = "pre_halving"

        if future_halvings:
            next_halving = future_halvings[0]
            days_to_next = (next_halving - date).days

        return {
            "month": month,
            "season": season,
            "multiplier": round(multiplier, 2),
            "halving_phase": halving_phase,
            "days_since_halving": days_since,
            "next_halving": next_halving.strftime("%Y-%m-%d") if next_halving else None,
            "days_to_next_halving": days_to_next,
        }

    def adjust_allocations(
        self,
        allocations: dict[str, float],
        date: datetime | None = None,
    ) -> dict[str, float]:
        """Adjust allocation weights based on season.

        Args:
            allocations: {symbol: weight} original distribution.
            date: Reference date.

        Returns:
            Seasonally adjusted {symbol: weight}.
        """
        if not allocations:
            return allocations

        info = self.get_season_info(date)
        multiplier = info["multiplier"]

        # Additional boost during post-halving bullish phase
        if info["halving_phase"] == "post_halving_bull":
            multiplier *= self.config.halving_boost

        adjusted = {}
        for symbol, weight in allocations.items():
            adjusted[symbol] = round(weight * multiplier, 4)

        # Normalize if total exceeds 1.0
        total = sum(adjusted.values())
        if total > 1.0:
            for symbol in adjusted:
                adjusted[symbol] = round(adjusted[symbol] / total, 4)

        return adjusted