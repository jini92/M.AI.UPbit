"""Base class for strategy framework.

Defines the QuantStrategy (single asset) and PortfolioStrategy (multiple assets) Protocols.
Compatible with existing BacktestEngine.run(data, strategy).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Protocol

import pandas as pd


class QuantStrategy(Protocol):
    """Single asset trading strategy protocol — compatible with BacktestEngine.

    Implementing the signal() method allows usage in existing BacktestEngine.run().
    """

    def signal(self, data: pd.DataFrame) -> int:
        """Generate trading signals.

        Args:
            data: OHLCV + indicator data up to now.

        Returns:
            1=buy, -1=sell, 0=hold.
        """
        ...


class PortfolioStrategy(Protocol):
    """Multiple asset portfolio strategy protocol — compatible with PortfolioBacktestEngine.

    The allocate() method returns the weight of each asset.
    """

    def allocate(
        self,
        data: dict[str, pd.DataFrame],
        date: pd.Timestamp | None = None,
    ) -> dict[str, float]:
        """Calculate allocation weights for assets.

        Args:
            data: Dictionary of {symbol: OHLCV DataFrame}.
            date: Allocation reference date (None means the latest).

        Returns:
            Dictionary of {symbol: weight}. Total <= 1.0 (the rest is cash).
        """
        ...


@dataclass
class StrategyConfig:
    """Base class for serializing strategy parameters."""

    def to_dict(self) -> dict:
        """Convert configuration to dictionary."""
        return asdict(self)