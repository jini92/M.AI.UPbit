"""Quant strategy package.

Modules based on the framework by Hwan-guk Kang for quantitative investment.
"""

from maiupbit.strategies.base import QuantStrategy, PortfolioStrategy, StrategyConfig
from maiupbit.strategies.volatility_breakout import VolatilityBreakoutStrategy, VolatilityBreakoutConfig
from maiupbit.strategies.momentum import DualMomentumStrategy, DualMomentumConfig
from maiupbit.strategies.multi_factor import MultiFactorStrategy, MultiFactorConfig
from maiupbit.strategies.allocation import GTAAStrategy, GTAAConfig
from maiupbit.strategies.seasonal import SeasonalFilter, SeasonalConfig
from maiupbit.strategies.risk import RiskManager, RiskConfig

__all__ = [
    "QuantStrategy",
    "PortfolioStrategy",
    "StrategyConfig",
    "VolatilityBreakoutStrategy",
    "VolatilityBreakoutConfig",
    "DualMomentumStrategy",
    "DualMomentumConfig",
    "MultiFactorStrategy",
    "MultiFactorConfig",
    "GTAAStrategy",
    "GTAAConfig",
    "SeasonalFilter",
    "SeasonalConfig",
    "RiskManager",
    "RiskConfig",
]