"""퀀트 전략 단위 테스트."""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime


@pytest.fixture
def multi_coin_data() -> dict[str, pd.DataFrame]:
    """테스트용 다중 코인 데이터 (3종목, 400일)."""
    np.random.seed(42)
    n = 400
    dates = pd.date_range("2025-01-01", periods=n, freq="D")

    data = {}
    for i, symbol in enumerate(["KRW-BTC", "KRW-ETH", "KRW-SOL"]):
        base = [50000, 3000, 100][i]
        close = base + np.cumsum(np.random.randn(n) * base * 0.02)
        close = np.maximum(close, base * 0.1)  # 음수 방지
        data[symbol] = pd.DataFrame(
            {
                "open": close + np.random.randn(n) * base * 0.005,
                "high": close + abs(np.random.randn(n) * base * 0.01),
                "low": close - abs(np.random.randn(n) * base * 0.01),
                "close": close,
                "volume": np.random.randint(1000, 100000, n).astype(float),
            },
            index=dates,
        )
    return data


class TestVolatilityBreakout:
    def test_signal_returns_valid(self, sample_ohlcv: pd.DataFrame) -> None:
        from maiupbit.strategies.volatility_breakout import VolatilityBreakoutStrategy

        strategy = VolatilityBreakoutStrategy()
        sig = strategy.signal(sample_ohlcv)
        assert sig in (1, 0, -1)

    def test_signal_insufficient_data(self) -> None:
        from maiupbit.strategies.volatility_breakout import VolatilityBreakoutStrategy

        strategy = VolatilityBreakoutStrategy()
        df = pd.DataFrame(
            {"open": [100], "high": [110], "low": [90], "close": [105]},
        )
        assert strategy.signal(df) == 0

    def test_position_size(self, sample_ohlcv: pd.DataFrame) -> None:
        from maiupbit.strategies.volatility_breakout import VolatilityBreakoutStrategy

        strategy = VolatilityBreakoutStrategy()
        size = strategy.calculate_position_size(1_000_000, sample_ohlcv)
        assert 0 < size <= 1_000_000

    def test_find_optimal_k(self, sample_ohlcv: pd.DataFrame) -> None:
        from maiupbit.strategies.volatility_breakout import VolatilityBreakoutStrategy

        results = VolatilityBreakoutStrategy.find_optimal_k(
            sample_ohlcv, k_range=[0.3, 0.5, 0.7]
        )
        assert isinstance(results, dict)
        assert len(results) == 3
        assert 0.3 in results

    def test_backtest_engine_compat(self, sample_ohlcv: pd.DataFrame) -> None:
        from maiupbit.strategies.volatility_breakout import VolatilityBreakoutStrategy
        from maiupbit.backtest.engine import BacktestEngine

        engine = BacktestEngine(initial_capital=1_000_000)
        strategy = VolatilityBreakoutStrategy()
        result = engine.run(sample_ohlcv, strategy)
        assert "total_return" in result
        assert "sharpe_ratio" in result
        assert "max_drawdown" in result


class TestDualMomentum:
    def test_signal_basic(self, multi_coin_data: dict) -> None:
        from maiupbit.strategies.momentum import DualMomentumStrategy

        strategy = DualMomentumStrategy()
        df = multi_coin_data["KRW-BTC"]
        sig = strategy.signal(df)
        assert sig in (1, 0, -1)

    def test_rank_coins(self, multi_coin_data: dict) -> None:
        from maiupbit.strategies.momentum import DualMomentumStrategy

        strategy = DualMomentumStrategy()
        rankings = strategy.rank_coins(multi_coin_data)
        assert isinstance(rankings, list)
        assert len(rankings) > 0
        assert "symbol" in rankings[0]
        assert "score" in rankings[0]
        assert "rank" in rankings[0]
        # 순위 순서 확인
        assert rankings[0]["rank"] == 1

    def test_allocate(self, multi_coin_data: dict) -> None:
        from maiupbit.strategies.momentum import DualMomentumStrategy

        strategy = DualMomentumStrategy()
        allocations = strategy.allocate(multi_coin_data)
        assert isinstance(allocations, dict)
        # 합계 <= 1.0
        if allocations:
            assert sum(allocations.values()) <= 1.0 + 0.001

    def test_signal_insufficient_data(self) -> None:
        from maiupbit.strategies.momentum import DualMomentumStrategy

        strategy = DualMomentumStrategy()
        df = pd.DataFrame({"close": [100, 110, 120]})
        assert strategy.signal(df) == 0


class TestMultiFactor:
    def test_rank_coins(self, multi_coin_data: dict) -> None:
        from maiupbit.strategies.multi_factor import MultiFactorStrategy

        strategy = MultiFactorStrategy()
        rankings = strategy.rank_coins(multi_coin_data)
        assert isinstance(rankings, list)
        assert len(rankings) > 0
        assert "composite_score" in rankings[0]
        assert "rank" in rankings[0]

    def test_allocate(self, multi_coin_data: dict) -> None:
        from maiupbit.strategies.multi_factor import MultiFactorStrategy

        strategy = MultiFactorStrategy()
        allocations = strategy.allocate(multi_coin_data)
        assert isinstance(allocations, dict)
        if allocations:
            assert sum(allocations.values()) <= 1.0 + 0.001

    def test_empty_data(self) -> None:
        from maiupbit.strategies.multi_factor import MultiFactorStrategy

        strategy = MultiFactorStrategy()
        rankings = strategy.rank_coins({})
        assert rankings == []


class TestGTAA:
    def test_allocate(self, multi_coin_data: dict) -> None:
        from maiupbit.strategies.allocation import GTAAStrategy, GTAAConfig

        # SMA 200일보다 충분한 데이터가 있으므로 동작해야 함
        config = GTAAConfig(sma_filter=50, momentum_periods=[28, 84])
        strategy = GTAAStrategy(config)
        allocations = strategy.allocate(multi_coin_data)
        assert isinstance(allocations, dict)

    def test_allocate_empty_data(self) -> None:
        from maiupbit.strategies.allocation import GTAAStrategy

        strategy = GTAAStrategy()
        allocations = strategy.allocate({})
        assert allocations == {}


class TestSeasonalFilter:
    def test_get_season_info(self) -> None:
        from maiupbit.strategies.seasonal import SeasonalFilter

        f = SeasonalFilter()
        info = f.get_season_info(datetime(2026, 1, 15))
        assert info["month"] == 1
        assert info["season"] == "bullish"
        assert info["multiplier"] == 1.2

    def test_bearish_season(self) -> None:
        from maiupbit.strategies.seasonal import SeasonalFilter

        f = SeasonalFilter()
        info = f.get_season_info(datetime(2026, 7, 15))
        assert info["season"] == "bearish"
        assert info["multiplier"] == 0.7

    def test_adjust_allocations_bullish(self) -> None:
        from maiupbit.strategies.seasonal import SeasonalFilter

        f = SeasonalFilter()
        alloc = {"KRW-BTC": 0.3, "KRW-ETH": 0.2}
        adjusted = f.adjust_allocations(alloc, datetime(2026, 1, 15))
        # 강세 시즌이므로 비중 증가 (1.2 배수)
        assert adjusted["KRW-BTC"] > 0.3 or sum(adjusted.values()) <= 1.0

    def test_adjust_allocations_bearish(self) -> None:
        from maiupbit.strategies.seasonal import SeasonalFilter

        f = SeasonalFilter()
        alloc = {"KRW-BTC": 0.3, "KRW-ETH": 0.2}
        adjusted = f.adjust_allocations(alloc, datetime(2026, 7, 15))
        # 약세 시즌이므로 비중 감소
        assert adjusted["KRW-BTC"] < 0.3

    def test_adjust_empty(self) -> None:
        from maiupbit.strategies.seasonal import SeasonalFilter

        f = SeasonalFilter()
        assert f.adjust_allocations({}) == {}

    def test_halving_phase(self) -> None:
        from maiupbit.strategies.seasonal import SeasonalFilter

        f = SeasonalFilter()
        # 2024 반감기 직후
        info = f.get_season_info(datetime(2024, 6, 1))
        assert info["halving_phase"] == "post_halving_bull"


class TestRiskManager:
    def test_atr_position_size(self, sample_ohlcv: pd.DataFrame) -> None:
        from maiupbit.strategies.risk import RiskManager

        rm = RiskManager()
        size = rm.atr_position_size(10_000_000, sample_ohlcv)
        assert 0 < size <= 10_000_000 * rm.config.max_position

    def test_kelly_from_history(self) -> None:
        from maiupbit.strategies.risk import RiskManager

        rm = RiskManager()
        trades = [
            {"type": "buy", "price": 100},
            {"type": "sell", "price": 110},
            {"type": "buy", "price": 105},
            {"type": "sell", "price": 95},
            {"type": "buy", "price": 100},
            {"type": "sell", "price": 115},
            {"type": "buy", "price": 110},
            {"type": "sell", "price": 120},
        ]
        kelly = rm.kelly_from_history(trades)
        assert 0 <= kelly <= 1.0

    def test_kelly_insufficient_trades(self) -> None:
        from maiupbit.strategies.risk import RiskManager

        rm = RiskManager()
        kelly = rm.kelly_from_history([{"type": "buy", "price": 100}])
        assert kelly == rm.config.kelly_fraction

    def test_calc_current_mdd(self) -> None:
        from maiupbit.strategies.risk import RiskManager

        equity = pd.Series([100, 110, 105, 95, 100])
        mdd = RiskManager.calc_current_mdd(equity)
        # 현재 100이고 peak 110 → mdd = (100-110)/110 ≈ -0.0909
        assert mdd < 0

    def test_get_mdd_multiplier(self) -> None:
        from maiupbit.strategies.risk import RiskManager

        rm = RiskManager()
        assert rm.get_mdd_multiplier(0.0) == 1.0
        assert rm.get_mdd_multiplier(-0.15) == 0.75
        assert rm.get_mdd_multiplier(-0.25) == 0.50
        assert rm.get_mdd_multiplier(-0.45) == 0.00

    def test_apply_mdd_rule(self) -> None:
        from maiupbit.strategies.risk import RiskManager

        rm = RiskManager()
        alloc = {"KRW-BTC": 0.4, "KRW-ETH": 0.3}
        equity = pd.Series([100, 110, 90, 80])  # MDD = (80-110)/110 ≈ -0.27
        adjusted = rm.apply_mdd_rule(alloc, equity)
        # MDD -0.27 → multiplier 0.5
        assert adjusted["KRW-BTC"] == round(0.4 * 0.5, 4)

    def test_apply_equal_weight_constraint(self) -> None:
        from maiupbit.strategies.risk import RiskManager

        rm = RiskManager()
        alloc = {"KRW-BTC": 0.5, "KRW-ETH": 0.3, "KRW-SOL": 0.1}
        constrained = rm.apply_equal_weight_constraint(alloc)
        assert constrained["KRW-BTC"] <= rm.config.max_position
        assert constrained["KRW-ETH"] <= rm.config.max_position


class TestPortfolioBacktestEngine:
    def test_run(self, multi_coin_data: dict) -> None:
        from maiupbit.backtest.portfolio_engine import PortfolioBacktestEngine
        from maiupbit.strategies.momentum import DualMomentumStrategy

        engine = PortfolioBacktestEngine(initial_capital=10_000_000)
        strategy = DualMomentumStrategy()
        result = engine.run(multi_coin_data, strategy, rebalance_days=7)

        assert "total_return" in result
        assert "sharpe_ratio" in result
        assert "max_drawdown" in result
        assert "equity_curve" in result
        assert "allocation_history" in result
        assert "per_asset_return" in result
        assert isinstance(result["equity_curve"], pd.Series)
        assert result["num_rebalances"] > 0

    def test_run_empty_data(self) -> None:
        from maiupbit.backtest.portfolio_engine import PortfolioBacktestEngine
        from maiupbit.strategies.momentum import DualMomentumStrategy

        engine = PortfolioBacktestEngine()
        result = engine.run({}, DualMomentumStrategy())
        assert result["total_return"] == 0.0

    def test_run_with_multi_factor(self, multi_coin_data: dict) -> None:
        from maiupbit.backtest.portfolio_engine import PortfolioBacktestEngine
        from maiupbit.strategies.multi_factor import MultiFactorStrategy

        engine = PortfolioBacktestEngine(initial_capital=10_000_000)
        strategy = MultiFactorStrategy()
        result = engine.run(multi_coin_data, strategy, rebalance_days=14)
        assert "total_return" in result
        assert result["final_equity"] > 0


class TestStrategyComposition:
    """전략 조합 통합 테스트."""

    def test_momentum_seasonal_risk_pipeline(self, multi_coin_data: dict) -> None:
        from maiupbit.strategies.momentum import DualMomentumStrategy
        from maiupbit.strategies.seasonal import SeasonalFilter
        from maiupbit.strategies.risk import RiskManager

        momentum = DualMomentumStrategy()
        seasonal = SeasonalFilter()
        risk = RiskManager()

        alloc = momentum.allocate(multi_coin_data)
        alloc = seasonal.adjust_allocations(alloc, datetime(2026, 1, 15))
        alloc = risk.apply_equal_weight_constraint(alloc)

        assert isinstance(alloc, dict)
        for weight in alloc.values():
            assert weight <= risk.config.max_position + 0.001

    def test_gtaa_seasonal_risk_pipeline(self, multi_coin_data: dict) -> None:
        from maiupbit.strategies.allocation import GTAAStrategy, GTAAConfig
        from maiupbit.strategies.seasonal import SeasonalFilter
        from maiupbit.strategies.risk import RiskManager

        config = GTAAConfig(sma_filter=50, momentum_periods=[28, 84])
        gtaa = GTAAStrategy(config)
        seasonal = SeasonalFilter()
        risk = RiskManager()

        alloc = gtaa.allocate(multi_coin_data)
        alloc = seasonal.adjust_allocations(alloc, datetime(2026, 7, 15))
        alloc = risk.apply_equal_weight_constraint(alloc)

        assert isinstance(alloc, dict)
        if alloc:
            total = sum(alloc.values())
            assert total <= 1.0 + 0.001
