"""리스크 관리 모듈.

강환국 리스크 관리 프레임워크:
- ATR 기반 포지션 사이징
- 켈리 공식 (최적 투자 비율)
- MDD 단계별 디레버리징
- 최대 비중 제한
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from maiupbit.indicators.volatility import atr
from maiupbit.strategies.base import StrategyConfig


@dataclass
class RiskConfig(StrategyConfig):
    """리스크 관리 설정."""

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
    kelly_fraction: float = 0.25  # 켈리의 1/4 (보수적)


class RiskManager:
    """리스크 관리자 (조합용).

    다른 전략의 배분 결과에 리스크 관리를 적용합니다.

    사용:
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
        """ATR 기반 포지션 사이즈 계산.

        Args:
            capital: 현재 자본금.
            data: OHLCV DataFrame.
            length: ATR 기간.

        Returns:
            투자할 금액.
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
        """과거 거래 이력으로 켈리 비율 계산.

        Args:
            trades: [{"type": "buy"/"sell", "price": float}] 리스트.

        Returns:
            켈리 비율 (0~1). 음수면 0 반환.
        """
        if len(trades) < 4:
            return self.config.kelly_fraction

        profits = []
        for i in range(0, len(trades) - 1, 2):
            if trades[i]["type"] == "buy" and trades[i + 1]["type"] == "sell":
                ret = (trades[i + 1]["price"] - trades[i]["price"]) / trades[i]["price"]
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

        # 켈리 공식: f = W - (1-W)/R, R = avg_win/avg_loss
        r = avg_win / avg_loss
        kelly = win_rate - (1 - win_rate) / r

        # 보수적 적용 (1/4 켈리)
        result = max(0.0, kelly * self.config.kelly_fraction / 0.25)
        return round(min(result, 1.0), 4)

    @staticmethod
    def calc_current_mdd(equity: pd.Series) -> float:
        """현재 MDD 계산.

        Args:
            equity: 자산 가치 시계열.

        Returns:
            현재 MDD (음수, 예: -0.15 = 15% 하락).
        """
        if len(equity) < 2:
            return 0.0
        peak = equity.cummax()
        drawdown = (equity - peak) / peak
        return float(drawdown.iloc[-1])

    def get_mdd_multiplier(self, mdd: float) -> float:
        """MDD에 따른 포지션 배수 조회.

        Args:
            mdd: 현재 MDD (음수).

        Returns:
            포지션 배수 (0.0~1.0).
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
        """MDD 규칙에 따라 배분 비중 축소.

        Args:
            allocations: {symbol: weight} 원본 배분.
            equity: 자산 가치 시계열.

        Returns:
            MDD 조정된 {symbol: weight}.
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
        """최대 비중 제한 적용.

        Args:
            allocations: {symbol: weight}.

        Returns:
            제한 적용된 {symbol: weight}.
        """
        if not allocations:
            return allocations

        constrained = {}
        excess = 0.0
        uncapped_count = 0

        # 1차: 최대 비중 초과분 누적
        for symbol, weight in allocations.items():
            if weight > self.config.max_position:
                constrained[symbol] = self.config.max_position
                excess += weight - self.config.max_position
            else:
                constrained[symbol] = weight
                uncapped_count += 1

        # 2차: 초과분 재분배
        if excess > 0 and uncapped_count > 0:
            add_per = excess / uncapped_count
            for symbol in constrained:
                if constrained[symbol] < self.config.max_position:
                    new_weight = constrained[symbol] + add_per
                    constrained[symbol] = round(
                        min(new_weight, self.config.max_position), 4
                    )

        return constrained
