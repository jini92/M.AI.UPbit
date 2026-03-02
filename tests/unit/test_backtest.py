"""Unit tests for BacktestEngine"""
from __future__ import annotations

import pandas as pd
import numpy as np
import pytest

from maiupbit.backtest.engine import BacktestEngine


# ---------------------------------------------------------------------------
# Test strategy classes
# ---------------------------------------------------------------------------

class BuyAndHoldStrategy:
    """Buy on the first candle and hold until the end"""

    def signal(self, data: pd.DataFrame) -> int:
        if len(data) == 1:
            return 1  # Buy on the first candle
        return 0      # Hold after that


class BuySellAlternatingStrategy:
    """Buy on odd candles, sell on even candles"""

    def signal(self, data: pd.DataFrame) -> int:
        idx = len(data)
        if idx % 2 == 1:
            return 1   # Buy on odd candles
        elif idx % 2 == 0:
            return -1  # Sell on even candles
        return 0


class NeverTradeStrategy:
    """Always hold"""

    def signal(self, data: pd.DataFrame) -> int:
        return 0


class AlwaysBuyStrategy:
    """Always attempt to buy (ignores existing position)"""

    def signal(self, data: pd.DataFrame) -> int:
        return 1


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def flat_data() -> pd.DataFrame:
    """Price is constant for 100 candles"""
    dates = pd.date_range("2026-01-01", periods=100, freq="D")
    return pd.DataFrame(
        {
            "open":   [1000.0] * 100,
            "high":   [1010.0] * 100,
            "low":    [990.0]  * 100,
            "close":  [1000.0] * 100,
            "volume": [1000.0] * 100,
        },
        index=dates,
    )


@pytest.fixture
def rising_data() -> pd.DataFrame:
    """Consistently rising for 100 candles"""
    dates = pd.date_range("2026-01-01", periods=100, freq="D")
    closes = [1000.0 + i * 10 for i in range(100)]  # From 1000 to 1990
    return pd.DataFrame(
        {
            "open":   closes,
            "high":   [c + 5 for c in closes],
            "low":    [c - 5 for c in closes],
            "close":  closes,
            "volume": [1000.0] * 100,
        },
        index=dates,
    )


@pytest.fixture
def engine() -> BacktestEngine:
    return BacktestEngine(initial_capital=1_000_000)


# ---------------------------------------------------------------------------
# Basic functionality tests
# ---------------------------------------------------------------------------

class TestBacktestRunBasic:
    def test_returns_expected_keys(
        self, engine: BacktestEngine, flat_data: pd.DataFrame
    ) -> None:
        result = engine.run(flat_data, NeverTradeStrategy())
        expected_keys = {
            "total_return",
            "sharpe_ratio",
            "max_drawdown",
            "num_trades",
            "trades",
            "final_equity",
        }
        assert expected_keys.issubset(result.keys())

    def test_never_trade_strategy_keeps_capital(
        self, engine: BacktestEngine, flat_data: pd.DataFrame
    ) -> None:
        result = engine.run(flat_data, NeverTradeStrategy())
        assert result["num_trades"] == 0
        assert result["final_equity"] == pytest.approx(1_000_000.0)
        assert result["total_return"] == pytest.approx(0.0)

    def test_buy_and_hold_flat_no_profit(
        self, engine: BacktestEngine, flat_data: pd.DataFrame
    ) -> None:
        result = engine.run(flat_data, BuyAndHoldStrategy())
        assert result["num_trades"] == 1  # Only one buy occurs
        assert result["total_return"] == pytest.approx(0.0, abs=0.1)

    def test_buy_and_hold_rising_makes_profit(
        self, engine: BacktestEngine, rising_data: pd.DataFrame
    ) -> None:
        result = engine.run(rising_data, BuyAndHoldStrategy())
        assert result["num_trades"] == 1
        # From 1000 to 1990: approximately 99% return
        assert result["total_return"] > 50.0

    def test_final_equity_type(
        self, engine: BacktestEngine, flat_data: pd.DataFrame
    ) -> None:
        result = engine.run(flat_data, NeverTradeStrategy())
        assert isinstance(result["final_equity"], float)


# ---------------------------------------------------------------------------
# Buy-sell alternating strategy tests
# ---------------------------------------------------------------------------

class TestBacktestBuySell:
    def test_alternating_strategy_trades_count(
        self, engine: BacktestEngine, flat_data: pd.DataFrame
    ) -> None:
        result = engine.run(flat_data, BuySellAlternatingStrategy())
        # Odd (buy) → Even (sell): At least two trades occur
        assert result["num_trades"] >= 2

    def test_trade_records_structure(
        self, engine: BacktestEngine, flat_data: pd.DataFrame
    ) -> None:
        result = engine.run(flat_data, BuySellAlternatingStrategy())
        for trade in result["trades"]:
            assert "type" in trade
            assert trade["type"] in ("buy", "sell")
            assert "price" in trade
            assert "index" in trade

    def test_alternating_flat_data_near_zero_return(
        self, engine: BacktestEngine, flat_data: pd.DataFrame
    ) -> None:
        result = engine.run(flat_data, BuySellAlternatingStrategy())
        # No price movement means little profit or loss
        assert abs(result["total_return"]) < 1.0

    def test_always_buy_strategy_buys_once(
        self, engine: BacktestEngine, flat_data: pd.DataFrame
    ) -> None:
        # Cannot buy again if position exists → Only one buy occurs
        result = engine.run(flat_data, AlwaysBuyStrategy())
        buy_trades = [t for t in result["trades"] if t["type"] == "buy"]
        assert len(buy_trades) == 1


# ---------------------------------------------------------------------------
# Metrics calculation validation tests
# ---------------------------------------------------------------------------

class TestBacktestMetrics:
    def test_total_return_calculation(
        self, rising_data: pd.DataFrame
    ) -> None:
        engine = BacktestEngine(initial_capital=1_000_000)
        result = engine.run(rising_data, BuyAndHoldStrategy())
        # From 1000 to 1990: approximately 99% return
        assert result["total_return"] > 50.0

    def test_sharpe_ratio_zero_when_no_volatility(
        self, engine: BacktestEngine, flat_data: pd.DataFrame
    ) -> None:
        # Always hold + constant price → No volatility → Sharpe ratio is 0
        result = engine.run(flat_data, NeverTradeStrategy())
        assert result["sharpe_ratio"] == pytest.approx(0.0)

    def test_sharpe_positive_on_consistently_rising(
        self, engine: BacktestEngine, rising_data: pd.DataFrame
    ) -> None:
        result = engine.run(rising_data, BuyAndHoldStrategy())
        assert result["sharpe_ratio"] >= 0.0


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------

class TestBacktestEdgeCases:
    def test_single_row_data(self) -> None:
        engine = BacktestEngine(initial_capital=500_000)
        data = pd.DataFrame(
            {"open": [100.0], "high": [110.0], "low": [90.0], "close": [100.0], "volume": [100.0]},
            index=pd.date_range("2026-01-01", periods=1, freq="D"),
        )
        result = engine.run(data, BuyAndHoldStrategy())
        assert "total_return" in result
        assert isinstance(result["final_equity"], float)

    def test_custom_initial_capital(self) -> None:
        engine = BacktestEngine(initial_capital=500_000)
        dates = pd.date_range("2026-01-01", periods=10, freq="D")
        data = pd.DataFrame(
            {"open": [100.0] * 10, "high": [110.0] * 10,
             "low": [90.0] * 10, "close": [100.0] * 10, "volume": [100.0] * 10},
            index=dates,
        )
        result = engine.run(data, NeverTradeStrategy())
        assert result["final_equity"] == pytest.approx(500_000.0)

    def test_num_trades_is_int(
        self, engine: BacktestEngine, flat_data: pd.DataFrame
    ) -> None:
        result = engine.run(flat_data, NeverTradeStrategy())
        assert isinstance(result["num_trades"], int)
        assert result["num_trades"] == 0