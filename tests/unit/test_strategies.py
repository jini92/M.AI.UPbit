import pytest
import pandas as pd
import numpy as np
from datetime import datetime


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
        close = np.maximum(close, base * 0.1)  # Prevent negative values
        data[symbol] = pd.DataFrame(
            {
                "open": close + np.random.randn(n) * base * 0.005,
                "high": close + np.random.rand(n) * (close - close * 0.02),
                "low": close - np.random.rand(n) * (close * 0.02),
                "close": close
            },
            index=dates
        )
    return data


class TestVolatilityStrategy:
    """Test volatility strategy."""

    def test_volatility_strategy(self, sample_ohlcv: pd.DataFrame):
        from maiupbit.strategies.volatility import VolatilityStrategy

        vs = VolatilityStrategy()
        signal = vs.generate_signal(sample_ohlcv)
        assert isinstance(signal, bool)


class TestVolatilityBacktestEngine:
    """Test volatility backtesting engine."""

    def test_run(self, sample_ohlcv: pd.DataFrame):
        from maiupbit.backtest.volatility_engine import VolatilityBacktestEngine
        from maiupbit.strategies.volatility import VolatilityStrategy

        engine = VolatilityBacktestEngine(initial_capital=10000)
        strategy = VolatilityStrategy()
        result = engine.run(sample_ohlcv, strategy)

        assert "total_return" in result
        assert "sharpe_ratio" in result
        assert "max_drawdown" in result


class TestVolatilityComposition:
    """Test volatility composition."""

    def test_volatility_pipeline(self, sample_ohlcv: pd.DataFrame):
        from maiupbit.strategies.volatility import VolatilityStrategy
        from maiupbit.backtest.volatility_engine import VolatilityBacktestEngine

        vs = VolatilityStrategy()
        engine = VolatilityBacktestEngine(initial_capital=10000)

        result = engine.run(sample_ohlcv, vs)
        assert "total_return" in result


class TestVolatilityRiskManager:
    """Test volatility risk management."""

    def test_atr_position_size(self, sample_ohlcv: pd.DataFrame):
        from maiupbit.strategies.risk import RiskManager

        rm = RiskManager()
        size = rm.atr_position_size(10000000, sample_ohlcv)
        assert 0 < size <= 10000000 * rm.config.max_position


class TestVolatilitySeasonalAdjustment:
    """Test seasonal adjustment for volatility strategy."""

    def test_seasonal_adjustment(self):
        from maiupbit.strategies.seasonal import SeasonalFilter
        from maiupbit.strategies.volatility import VolatilityStrategy

        sf = SeasonalFilter()
        vs = VolatilityStrategy()

        alloc = vs.allocate(multi_coin_data)
        adjusted_alloc = sf.adjust_allocations(alloc, datetime(2026, 1, 15))

        assert isinstance(adjusted_alloc, dict)


class TestVolatilityPortfolioBacktestEngine:
    """Test portfolio backtesting engine for volatility strategy."""

    def test_run(self, multi_coin_data: dict):
        from maiupbit.backtest.portfolio_engine import PortfolioBacktestEngine
        from maiupbit.strategies.volatility import VolatilityStrategy

        engine = PortfolioBacktestEngine(initial_capital=10000000)
        strategy = VolatilityStrategy()
        result = engine.run(multi_coin_data, strategy, rebalance_days=7)

        assert "total_return" in result
        assert "sharpe_ratio" in result
        assert "max_drawdown" in result


class TestVolatilityCompositionWithRisk:
    """Test volatility composition with risk management."""

    def test_volatility_risk_pipeline(self, multi_coin_data: dict):
        from maiupbit.strategies.volatility import VolatilityStrategy
        from maiupbit.strategies.risk import RiskManager

        vs = VolatilityStrategy()
        rm = RiskManager()

        alloc = vs.allocate(multi_coin_data)
        adjusted_alloc = rm.apply_equal_weight_constraint(alloc)

        assert isinstance(adjusted_alloc, dict)


class TestVolatilityCompositionWithSeasonal:
    """Test volatility composition with seasonal adjustment."""

    def test_volatility_seasonal_pipeline(self, multi_coin_data: dict):
        from maiupbit.strategies.volatility import VolatilityStrategy
        from maiupbit.strategies.seasonal import SeasonalFilter

        vs = VolatilityStrategy()
        sf = SeasonalFilter()

        alloc = vs.allocate(multi_coin_data)
        adjusted_alloc = sf.adjust_allocations(alloc, datetime(2026, 1, 15))

        assert isinstance(adjusted_alloc, dict)


class TestVolatilityCompositionWithGTAARisk:
    """Test volatility composition with GTAA risk management."""

    def test_volatility_gtaa_risk_pipeline(self, multi_coin_data: dict):
        from maiupbit.strategies.allocation import GTAAStrategy, GTAAConfig
        from maiupbit.strategies.volatility import VolatilityStrategy

        config = GTAAConfig(sma_filter=50, momentum_periods=[28, 84])
        gtaa = GTAAStrategy(config)
        vs = VolatilityStrategy()

        alloc = vs.allocate(multi_coin_data)
        adjusted_alloc = gtaa.apply_equal_weight_constraint(alloc)

        assert isinstance(adjusted_alloc, dict)


class TestVolatilityCompositionWithRiskAndSeasonal:
    """Test volatility composition with risk management and seasonal adjustment."""

    def test_volatility_risk_seasonal_pipeline(self, multi_coin_data: dict):
        from maiupbit.strategies.volatility import VolatilityStrategy
        from maiupbit.strategies.risk import RiskManager
        from maiupbit.strategies.seasonal import SeasonalFilter

        vs = VolatilityStrategy()
        rm = RiskManager()
        sf = SeasonalFilter()

        alloc = vs.allocate(multi_coin_data)
        adjusted_alloc = sf.adjust_allocations(alloc, datetime(2026, 1, 15))
        final_alloc = rm.apply_equal_weight_constraint(adjusted_alloc)

        assert isinstance(final_alloc, dict)


class TestVolatilityCompositionWithGTAARiskAndSeasonal:
    """Test volatility composition with GTAA risk management and seasonal adjustment."""

    def test_volatility_gtaa_risk_seasonal_pipeline(self, multi_coin_data: dict):
        from maiupbit.strategies.allocation import GTAAStrategy, GTAAConfig
        from maiupbit.strategies.volatility import VolatilityStrategy
        from maiupbit.strategies.seasonal import SeasonalFilter

        config = GTAAConfig(sma_filter=50, momentum_periods=[28, 84])
        gtaa = GTAAStrategy(config)
        vs = VolatilityStrategy()
        sf = SeasonalFilter()

        alloc = vs.allocate(multi_coin_data)
        adjusted_alloc = sf.adjust_allocations(alloc, datetime(2026, 1, 15))
        final_alloc = gtaa.apply_equal_weight_constraint(adjusted_alloc)

        assert isinstance(final_alloc, dict)


class TestVolatilityCompositionWithRiskAndSeasonalGTAARisk:
    """Test volatility composition with risk management and seasonal adjustment using GTAA."""

    def test_volatility_risk_seasonal_gtaa_pipeline(self, multi_coin_data: dict):
        from maiupbit.strategies.allocation import GTAAStrategy, GTAAConfig
        from maiupbit.strategies.volatility import VolatilityStrategy
        from maiupbit.strategies.risk import RiskManager
        from maiupbit.strategies.seasonal import SeasonalFilter

        config = GTAAConfig(sma_filter=50, momentum_periods=[28, 84])
        gtaa = GTAAStrategy(config)
        vs = VolatilityStrategy()
        rm = RiskManager()
        sf = SeasonalFilter()

        alloc = vs.allocate(multi_coin_data)
        adjusted_alloc = sf.adjust_allocations(alloc, datetime(2026, 1, 15))
        final_alloc = gtaa.apply_equal_weight_constraint(rm.apply_equal_weight_constraint(adjusted_alloc))

        assert isinstance(final_alloc, dict)


class TestVolatilityCompositionWithRiskAndSeasonalGTAARiskPortfolio:
    """Test volatility composition with risk management and seasonal adjustment using GTAA for portfolio."""

    def test_volatility_risk_seasonal_gtaa_portfolio_pipeline(self, multi_coin_data: dict):
        from maiupbit.backtest.portfolio_engine import PortfolioBacktestEngine
        from maiupbit.strategies.allocation import GTAAStrategy, GTAAConfig
        from maiupbit.strategies.volatility import VolatilityStrategy
        from maiupbit.strategies.risk import RiskManager
        from maiupbit.strategies.seasonal import SeasonalFilter

        config = GTAAConfig(sma_filter=50, momentum_periods=[28, 84])
        gtaa = GTAAStrategy(config)
        vs = VolatilityStrategy()
        rm = RiskManager()
        sf = SeasonalFilter()

        engine = PortfolioBacktestEngine(initial_capital=10000000)

        alloc = vs.allocate(multi_coin_data)
        adjusted_alloc = sf.adjust_allocations(alloc, datetime(2026, 1, 15))
        final_alloc = gtaa.apply_equal_weight_constraint(rm.apply_equal_weight_constraint(adjusted_alloc))

        result = engine.run(multi_coin_data, vs, rebalance_days=7)

        assert "total_return" in result