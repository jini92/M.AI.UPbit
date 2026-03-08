import pytest
import pandas as pd
import numpy as np
from datetime import datetime


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Test single coin OHLCV data (200 days)."""
    np.random.seed(42)
    n = 200
    dates = pd.date_range("2025-06-01", periods=n, freq="D")
    base = 50000
    close = base + np.cumsum(np.random.randn(n) * base * 0.02)
    close = np.maximum(close, base * 0.1)
    high = close + np.random.rand(n) * base * 0.01
    low = close - np.random.rand(n) * base * 0.01
    volume = np.random.rand(n) * 1000 + 100
    return pd.DataFrame(
        {"open": close + np.random.randn(n) * base * 0.005,
         "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


@pytest.fixture
def multi_coin_data() -> dict[str, pd.DataFrame]:
    """Test multiple coin data (3 symbols, 400 days)."""
    np.random.seed(42)
    n = 400
    dates = pd.date_range("2025-01-01", periods=n, freq="D")
    data = {}
    for i, symbol in enumerate(["KRW-BTC", "KRW-ETH", "KRW-SOL"]):
        base = [50000, 3000, 100][i]
        close = base + np.cumsum(np.random.randn(n) * base * 0.02)
        close = np.maximum(close, base * 0.1)
        high = close + np.random.rand(n) * base * 0.01
        low = close - np.random.rand(n) * base * 0.01
        volume = np.random.rand(n) * 1000 + 100
        data[symbol] = pd.DataFrame(
            {"open": close + np.random.randn(n) * base * 0.005,
             "high": high, "low": low, "close": close, "volume": volume},
            index=dates,
        )
    return data


class TestVolatilityBreakoutStrategy:
    """Test VolatilityBreakoutStrategy."""

    def test_signal_returns_valid(self, sample_ohlcv):
        from maiupbit.strategies.volatility_breakout import VolatilityBreakoutStrategy
        strategy = VolatilityBreakoutStrategy()
        sig = strategy.signal(sample_ohlcv)
        assert sig in (1, -1, 0)

    def test_auto_k_optimization(self, sample_ohlcv):
        from maiupbit.strategies.volatility_breakout import (
            VolatilityBreakoutStrategy, VolatilityBreakoutConfig,
        )
        config = VolatilityBreakoutConfig(auto_k=True)
        strategy = VolatilityBreakoutStrategy(config)
        sig = strategy.signal(sample_ohlcv)
        assert sig in (1, -1, 0)

    def test_find_optimal_k(self, sample_ohlcv):
        from maiupbit.strategies.volatility_breakout import VolatilityBreakoutStrategy
        result = VolatilityBreakoutStrategy.find_optimal_k(sample_ohlcv)
        assert isinstance(result, dict)
        assert 0.5 in result

    def test_position_size(self, sample_ohlcv):
        from maiupbit.strategies.volatility_breakout import VolatilityBreakoutStrategy
        strategy = VolatilityBreakoutStrategy()
        size = strategy.calculate_position_size(10_000_000, sample_ohlcv)
        assert 0 < size <= 10_000_000


class TestDualMomentumStrategy:
    """Test DualMomentumStrategy."""

    def test_signal(self, sample_ohlcv):
        from maiupbit.strategies.momentum import DualMomentumStrategy
        strategy = DualMomentumStrategy()
        sig = strategy.signal(sample_ohlcv)
        assert sig in (1, -1, 0)

    def test_rank_coins(self, multi_coin_data):
        from maiupbit.strategies.momentum import DualMomentumStrategy
        strategy = DualMomentumStrategy()
        rankings = strategy.rank_coins(multi_coin_data)
        assert isinstance(rankings, list)
        assert all("symbol" in r and "score" in r and "rank" in r for r in rankings)

    def test_allocate(self, multi_coin_data):
        from maiupbit.strategies.momentum import DualMomentumStrategy
        strategy = DualMomentumStrategy()
        alloc = strategy.allocate(multi_coin_data)
        assert isinstance(alloc, dict)
        if alloc:
            assert sum(alloc.values()) <= 1.01


class TestMultiFactorStrategy:
    """Test MultiFactorStrategy with volume growth quality factor."""

    def test_rank_coins(self, multi_coin_data):
        from maiupbit.strategies.multi_factor import MultiFactorStrategy
        strategy = MultiFactorStrategy()
        rankings = strategy.rank_coins(multi_coin_data)
        assert isinstance(rankings, list)
        assert all("composite_score" in r and "quality" in r for r in rankings)

    def test_allocate_top_n(self, multi_coin_data):
        from maiupbit.strategies.multi_factor import MultiFactorStrategy, MultiFactorConfig
        strategy = MultiFactorStrategy(MultiFactorConfig(top_n=2))
        alloc = strategy.allocate(multi_coin_data)
        assert len(alloc) <= 2

    def test_quality_is_volume_growth(self, multi_coin_data):
        """Quality factor should be volume growth rate, not CV inverse."""
        from maiupbit.strategies.multi_factor import MultiFactorStrategy
        strategy = MultiFactorStrategy()
        rankings = strategy.rank_coins(multi_coin_data)
        for r in rankings:
            # Volume growth rate should be around 1.0 for random data
            assert r["quality"] is not None
            assert r["quality"] > 0


class TestGTAAStrategy:
    """Test GTAAStrategy with updated parameters."""

    def test_config_defaults(self):
        from maiupbit.strategies.allocation import GTAAConfig
        config = GTAAConfig()
        assert config.sma_filter == 120
        assert config.momentum_periods == [28, 84, 168, 365]
        assert config.momentum_weights == [12, 4, 2, 1]

    def test_allocate(self, multi_coin_data):
        from maiupbit.strategies.allocation import GTAAStrategy, GTAAConfig
        config = GTAAConfig(sma_filter=50, momentum_periods=[28, 84])
        strategy = GTAAStrategy(config)
        alloc = strategy.allocate(multi_coin_data)
        assert isinstance(alloc, dict)
        if alloc:
            assert sum(alloc.values()) <= 1.01


class TestSeasonalFilter:
    """Test SeasonalFilter."""

    def test_bullish_season(self):
        from maiupbit.strategies.seasonal import SeasonalFilter
        sf = SeasonalFilter()
        info = sf.get_season_info(datetime(2026, 1, 15))
        assert info["season"] == "bullish"
        assert info["multiplier"] == 1.2

    def test_bearish_season(self):
        from maiupbit.strategies.seasonal import SeasonalFilter
        sf = SeasonalFilter()
        info = sf.get_season_info(datetime(2026, 6, 15))
        assert info["season"] == "bearish"
        assert info["multiplier"] == 0.7

    def test_adjust_allocations(self):
        from maiupbit.strategies.seasonal import SeasonalFilter
        sf = SeasonalFilter()
        alloc = {"KRW-BTC": 0.5, "KRW-ETH": 0.3}
        adjusted = sf.adjust_allocations(alloc, datetime(2026, 1, 15))
        assert isinstance(adjusted, dict)
        assert sum(adjusted.values()) <= 1.01


class TestRiskManager:
    """Test RiskManager."""

    def test_atr_position_size(self, sample_ohlcv):
        from maiupbit.strategies.risk import RiskManager
        rm = RiskManager()
        size = rm.atr_position_size(10_000_000, sample_ohlcv)
        assert 0 < size <= 10_000_000 * rm.config.max_position

    def test_mdd_multiplier(self):
        from maiupbit.strategies.risk import RiskManager
        rm = RiskManager()
        assert rm.get_mdd_multiplier(0.0) == 1.0
        assert rm.get_mdd_multiplier(-0.15) == 0.75
        assert rm.get_mdd_multiplier(-0.25) == 0.50
        assert rm.get_mdd_multiplier(-0.45) == 0.00

    def test_equal_weight_constraint(self):
        from maiupbit.strategies.risk import RiskManager
        rm = RiskManager()
        alloc = {"A": 0.5, "B": 0.3, "C": 0.2}
        constrained = rm.apply_equal_weight_constraint(alloc)
        assert all(w <= rm.config.max_position for w in constrained.values())

    def test_mdd_rule(self):
        from maiupbit.strategies.risk import RiskManager
        rm = RiskManager()
        alloc = {"A": 0.5, "B": 0.3}
        equity = pd.Series([100, 110, 105, 90, 80, 75])  # ~32% drawdown
        adjusted = rm.apply_mdd_rule(alloc, equity)
        assert all(adjusted[k] <= alloc[k] for k in alloc)


class TestCompositionPipeline:
    """Test full strategy composition pipeline."""

    def test_momentum_seasonal_risk(self, multi_coin_data):
        from maiupbit.strategies.momentum import DualMomentumStrategy
        from maiupbit.strategies.seasonal import SeasonalFilter
        from maiupbit.strategies.risk import RiskManager

        strategy = DualMomentumStrategy()
        sf = SeasonalFilter()
        rm = RiskManager()

        alloc = strategy.allocate(multi_coin_data)
        adjusted = sf.adjust_allocations(alloc, datetime(2026, 1, 15))
        final = rm.apply_equal_weight_constraint(adjusted)
        assert isinstance(final, dict)

    def test_gtaa_seasonal_risk(self, multi_coin_data):
        from maiupbit.strategies.allocation import GTAAStrategy, GTAAConfig
        from maiupbit.strategies.seasonal import SeasonalFilter
        from maiupbit.strategies.risk import RiskManager

        config = GTAAConfig(sma_filter=50, momentum_periods=[28, 84])
        strategy = GTAAStrategy(config)
        sf = SeasonalFilter()
        rm = RiskManager()

        alloc = strategy.allocate(multi_coin_data)
        adjusted = sf.adjust_allocations(alloc, datetime(2026, 1, 15))
        final = rm.apply_equal_weight_constraint(adjusted)
        assert isinstance(final, dict)