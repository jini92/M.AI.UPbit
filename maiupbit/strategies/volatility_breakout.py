"""변동성 돌파 전략.

래리 윌리엄스 변동성 돌파를 강환국 방식으로 적응:
- 당일 시가 + 전일 레인지 × k 돌파 시 매수
- 노이즈 비율 필터 + MA 필터
- ATR 기반 포지션 사이징
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from maiupbit.indicators.volatility import atr, noise_ratio
from maiupbit.strategies.base import StrategyConfig


@dataclass
class VolatilityBreakoutConfig(StrategyConfig):
    """변동성 돌파 전략 설정."""

    k: float = 0.5
    noise_threshold: float = 0.6
    ma_filter: int = 20
    risk_per_trade: float = 0.02


class VolatilityBreakoutStrategy:
    """변동성 돌파 전략 (QuantStrategy 호환).

    사용:
        strategy = VolatilityBreakoutStrategy()
        engine = BacktestEngine()
        result = engine.run(data, strategy)
    """

    def __init__(self, config: VolatilityBreakoutConfig | None = None) -> None:
        self.config = config or VolatilityBreakoutConfig()
        self._in_position = False

    def signal(self, data: pd.DataFrame) -> int:
        """변동성 돌파 매매 시그널.

        Args:
            data: OHLCV DataFrame (open, high, low, close 필수).

        Returns:
            1=buy, -1=sell, 0=hold.
        """
        if len(data) < 3:
            return 0

        today = data.iloc[-1]
        yesterday = data.iloc[-2]

        prev_range = yesterday["high"] - yesterday["low"]
        breakout_price = today["open"] + prev_range * self.config.k

        # MA 필터
        if self.config.ma_filter > 0 and len(data) >= self.config.ma_filter:
            ma = data["close"].rolling(self.config.ma_filter).mean().iloc[-1]
            if today["close"] < ma:
                if self._in_position:
                    self._in_position = False
                    return -1
                return 0

        # 노이즈 필터
        if len(data) >= 20:
            nr = noise_ratio(
                data["open"], data["high"], data["low"], data["close"], length=20
            ).iloc[-1]
            if not np.isnan(nr) and nr > self.config.noise_threshold:
                if self._in_position:
                    self._in_position = False
                    return -1
                return 0

        # 돌파 매수
        if not self._in_position and today["high"] >= breakout_price:
            self._in_position = True
            return 1

        # 일봉 종료 시 청산 (다음봉 시가에 매도)
        if self._in_position:
            self._in_position = False
            return -1

        return 0

    def calculate_position_size(
        self,
        capital: float,
        data: pd.DataFrame,
    ) -> float:
        """ATR 기반 포지션 사이즈 계산.

        Args:
            capital: 현재 자본금.
            data: OHLCV DataFrame.

        Returns:
            투자할 금액.
        """
        if len(data) < 15:
            return capital * self.config.risk_per_trade

        atr_val = atr(data["high"], data["low"], data["close"], length=14).iloc[-1]
        if np.isnan(atr_val) or atr_val <= 0:
            return capital * self.config.risk_per_trade

        price = data["close"].iloc[-1]
        risk_amount = capital * self.config.risk_per_trade
        position_size = risk_amount / atr_val * price
        return min(position_size, capital)

    @staticmethod
    def find_optimal_k(
        data: pd.DataFrame,
        k_range: list[float] | None = None,
    ) -> dict:
        """최적 k값을 백테스트로 탐색합니다.

        Args:
            data: OHLCV DataFrame.
            k_range: 탐색할 k값 리스트.

        Returns:
            {k: return_pct} 딕셔너리.
        """
        if k_range is None:
            k_range = [round(0.1 * i, 1) for i in range(1, 11)]

        results = {}
        for k in k_range:
            capital = 1_000_000.0
            for i in range(2, len(data)):
                prev_range = data.iloc[i - 1]["high"] - data.iloc[i - 1]["low"]
                breakout = data.iloc[i]["open"] + prev_range * k
                if data.iloc[i]["high"] >= breakout:
                    buy_price = breakout
                    sell_price = data.iloc[i]["close"]
                    capital *= sell_price / buy_price
            ret = (capital - 1_000_000) / 1_000_000 * 100
            results[k] = round(ret, 2)
        return results
