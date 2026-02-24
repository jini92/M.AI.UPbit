"""BacktestEngine 단위 테스트"""
from __future__ import annotations

import pandas as pd
import numpy as np
import pytest

from maiupbit.backtest.engine import BacktestEngine


# ---------------------------------------------------------------------------
# 테스트용 전략 클래스
# ---------------------------------------------------------------------------

class BuyAndHoldStrategy:
    """첫 봉에 매수하고 끝까지 보유"""

    def signal(self, data: pd.DataFrame) -> int:
        if len(data) == 1:
            return 1  # 첫 봉: 매수
        return 0      # 이후: 보유


class BuySellAlternatingStrategy:
    """홀수 봉에 매수, 짝수 봉에 매도"""

    def signal(self, data: pd.DataFrame) -> int:
        idx = len(data)
        if idx % 2 == 1:
            return 1   # 홀수: 매수
        elif idx % 2 == 0:
            return -1  # 짝수: 매도
        return 0


class NeverTradeStrategy:
    """항상 hold"""

    def signal(self, data: pd.DataFrame) -> int:
        return 0


class AlwaysBuyStrategy:
    """항상 매수 시도 (포지션 있어도 무시됨)"""

    def signal(self, data: pd.DataFrame) -> int:
        return 1


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def flat_data() -> pd.DataFrame:
    """가격이 일정한 100개 캔들"""
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
    """꾸준히 상승하는 100개 캔들"""
    dates = pd.date_range("2026-01-01", periods=100, freq="D")
    closes = [1000.0 + i * 10 for i in range(100)]  # 1000 → 1990
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
# 기본 동작
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
        assert result["num_trades"] == 1  # 매수만 발생
        assert result["total_return"] == pytest.approx(0.0, abs=0.1)

    def test_buy_and_hold_rising_makes_profit(
        self, engine: BacktestEngine, rising_data: pd.DataFrame
    ) -> None:
        result = engine.run(rising_data, BuyAndHoldStrategy())
        assert result["num_trades"] == 1
        # 1000 → 1990: 약 99% 수익
        assert result["total_return"] > 50.0

    def test_final_equity_type(
        self, engine: BacktestEngine, flat_data: pd.DataFrame
    ) -> None:
        result = engine.run(flat_data, NeverTradeStrategy())
        assert isinstance(result["final_equity"], float)


# ---------------------------------------------------------------------------
# 매매 반복 전략
# ---------------------------------------------------------------------------

class TestBacktestBuySell:
    def test_alternating_strategy_trades_count(
        self, engine: BacktestEngine, flat_data: pd.DataFrame
    ) -> None:
        result = engine.run(flat_data, BuySellAlternatingStrategy())
        # 홀수(매수)→짝수(매도) 반복: 최소 2회 이상 거래
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
        # 가격 변동 없으면 수익/손실 거의 없음
        assert abs(result["total_return"]) < 1.0

    def test_always_buy_strategy_buys_once(
        self, engine: BacktestEngine, flat_data: pd.DataFrame
    ) -> None:
        # 포지션이 있으면 추가 매수 불가 → 첫 번째만 매수
        result = engine.run(flat_data, AlwaysBuyStrategy())
        buy_trades = [t for t in result["trades"] if t["type"] == "buy"]
        assert len(buy_trades) == 1


# ---------------------------------------------------------------------------
# 지표 계산 검증
# ---------------------------------------------------------------------------

class TestBacktestMetrics:
    def test_total_return_calculation(
        self, rising_data: pd.DataFrame
    ) -> None:
        engine = BacktestEngine(initial_capital=1_000_000)
        result = engine.run(rising_data, BuyAndHoldStrategy())
        # 수동 계산: buy at 1000, hold through 1990
        buy_price = 1000.0
        final_price = 1990.0
        expected_return = (final_price - buy_price) / buy_price * 100
        assert result["total_return"] == pytest.approx(expected_return, rel=0.01)

    def test_max_drawdown_is_non_positive(
        self, engine: BacktestEngine, rising_data: pd.DataFrame
    ) -> None:
        result = engine.run(rising_data, BuyAndHoldStrategy())
        assert result["max_drawdown"] <= 0.0

    def test_max_drawdown_flat_data_is_zero(
        self, engine: BacktestEngine, flat_data: pd.DataFrame
    ) -> None:
        result = engine.run(flat_data, BuyAndHoldStrategy())
        assert result["max_drawdown"] == pytest.approx(0.0, abs=0.01)

    def test_sharpe_ratio_type(
        self, engine: BacktestEngine, flat_data: pd.DataFrame
    ) -> None:
        result = engine.run(flat_data, NeverTradeStrategy())
        assert isinstance(result["sharpe_ratio"], float)

    def test_sharpe_ratio_zero_when_no_volatility(
        self, engine: BacktestEngine, flat_data: pd.DataFrame
    ) -> None:
        # 항상 hold + 가격 고정 → 수익률 분산 0 → sharpe 0
        result = engine.run(flat_data, NeverTradeStrategy())
        assert result["sharpe_ratio"] == pytest.approx(0.0)

    def test_sharpe_positive_on_consistently_rising(
        self, engine: BacktestEngine, rising_data: pd.DataFrame
    ) -> None:
        result = engine.run(rising_data, BuyAndHoldStrategy())
        assert result["sharpe_ratio"] >= 0.0


# ---------------------------------------------------------------------------
# 엣지 케이스
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
