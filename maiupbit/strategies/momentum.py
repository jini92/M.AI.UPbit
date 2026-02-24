"""듀얼 모멘텀 전략.

강환국 듀얼 모멘텀 프레임워크:
- 절대 모멘텀: 수익률 > 0 (양수 모멘텀만 투자)
- 상대 모멘텀: 코인 간 모멘텀 점수 비교 → 상위 N개
- 평균 모멘텀 시그널: 12개 기간 모멘텀 평균 → 포지션 비중
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from maiupbit.indicators.momentum import momentum_score, average_momentum_signal
from maiupbit.strategies.base import StrategyConfig


@dataclass
class DualMomentumConfig(StrategyConfig):
    """듀얼 모멘텀 전략 설정."""

    score_periods: list[int] = field(default_factory=lambda: [28, 84, 168, 365])
    score_weights: list[float] = field(default_factory=lambda: [12, 4, 2, 1])
    abs_threshold: float = 0.0
    top_n: int = 5
    rebalance_days: int = 7


class DualMomentumStrategy:
    """듀얼 모멘텀 전략 (QuantStrategy + PortfolioStrategy 모두 호환).

    단일 종목: signal() → BacktestEngine
    다중 종목: allocate() → PortfolioBacktestEngine
    """

    def __init__(self, config: DualMomentumConfig | None = None) -> None:
        self.config = config or DualMomentumConfig()

    def signal(self, data: pd.DataFrame) -> int:
        """단일 종목 절대 모멘텀 시그널.

        Args:
            data: OHLCV DataFrame.

        Returns:
            1=buy (모멘텀 양수), -1=sell (모멘텀 음수), 0=hold.
        """
        if len(data) < max(self.config.score_periods):
            return 0

        score = momentum_score(
            data["close"],
            periods=self.config.score_periods,
            weights=self.config.score_weights,
        ).iloc[-1]

        if score > self.config.abs_threshold:
            return 1
        elif score < -self.config.abs_threshold:
            return -1
        return 0

    def rank_coins(
        self,
        data: dict[str, pd.DataFrame],
        date: pd.Timestamp | None = None,
    ) -> list[dict]:
        """코인 모멘텀 랭킹.

        Args:
            data: {symbol: OHLCV DataFrame} 딕셔너리.
            date: 기준 날짜 (None이면 최신).

        Returns:
            [{"symbol", "score", "avg_signal", "rank"}] 리스트 (점수 내림차순).
        """
        rankings = []
        for symbol, df in data.items():
            if date is not None:
                df = df.loc[:date]
            if len(df) < max(self.config.score_periods):
                continue

            score = momentum_score(
                df["close"],
                periods=self.config.score_periods,
                weights=self.config.score_weights,
            ).iloc[-1]

            avg_sig = average_momentum_signal(df["close"]).iloc[-1]

            rankings.append({
                "symbol": symbol,
                "score": round(float(score), 6),
                "avg_signal": round(float(avg_sig), 4),
            })

        rankings.sort(key=lambda x: x["score"], reverse=True)
        for i, r in enumerate(rankings):
            r["rank"] = i + 1
        return rankings

    def allocate(
        self,
        data: dict[str, pd.DataFrame],
        date: pd.Timestamp | None = None,
    ) -> dict[str, float]:
        """듀얼 모멘텀 기반 자산배분.

        1) 절대 모멘텀 필터: score > threshold
        2) 상대 모멘텀: 상위 N개 선택
        3) 평균 모멘텀 시그널로 비중 산출

        Args:
            data: {symbol: OHLCV DataFrame}.
            date: 기준 날짜.

        Returns:
            {symbol: weight} (합계 <= 1.0).
        """
        rankings = self.rank_coins(data, date)

        # 절대 모멘텀 필터
        positive = [r for r in rankings if r["score"] > self.config.abs_threshold]

        # 상위 N개
        selected = positive[: self.config.top_n]

        if not selected:
            return {}

        # 평균 모멘텀 시그널로 비중 산출
        total_signal = sum(r["avg_signal"] for r in selected)
        if total_signal <= 0:
            return {}

        allocations = {}
        for r in selected:
            weight = r["avg_signal"] / total_signal
            allocations[r["symbol"]] = round(weight, 4)

        return allocations
