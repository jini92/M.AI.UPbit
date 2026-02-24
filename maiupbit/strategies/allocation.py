"""GTAA 동적 자산배분 전략.

강환국 GTAA(Global Tactical Asset Allocation) 프레임워크:
- 모멘텀 양수 자산만 투자, 음수면 현금 보유
- SMA 필터: 현재가 > SMA(200)인 자산만 투자
- 상위 N개 동일가중 배분
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from maiupbit.indicators.momentum import momentum_score
from maiupbit.strategies.base import StrategyConfig


@dataclass
class GTAAConfig(StrategyConfig):
    """GTAA 자산배분 전략 설정."""

    momentum_periods: list[int] = field(default_factory=lambda: [28, 84, 168])
    momentum_weights: list[float] = field(default_factory=lambda: [6, 3, 1])
    sma_filter: int = 200
    max_positions: int = 5
    rebalance_days: int = 7


class GTAAStrategy:
    """GTAA 동적 자산배분 전략 (PortfolioStrategy 호환).

    선택 기준:
    1) 모멘텀 점수 양수
    2) 현재가 > SMA(sma_filter)
    3) 모멘텀 점수 기준 상위 max_positions개
    4) 동일가중 배분
    """

    def __init__(self, config: GTAAConfig | None = None) -> None:
        self.config = config or GTAAConfig()

    def _evaluate_asset(
        self,
        symbol: str,
        df: pd.DataFrame,
        date: pd.Timestamp | None = None,
    ) -> dict | None:
        """개별 자산 평가.

        Args:
            symbol: 종목 코드.
            df: OHLCV DataFrame.
            date: 기준 날짜.

        Returns:
            {"symbol", "score", "above_sma"} 또는 None.
        """
        if date is not None:
            df = df.loc[:date]

        min_required = max(
            max(self.config.momentum_periods),
            self.config.sma_filter,
        )
        if len(df) < min_required:
            return None

        close = df["close"]

        score = momentum_score(
            close,
            periods=self.config.momentum_periods,
            weights=self.config.momentum_weights,
        ).iloc[-1]

        if np.isnan(score) or score <= 0:
            return None

        # SMA 필터
        sma_val = close.rolling(self.config.sma_filter).mean().iloc[-1]
        if np.isnan(sma_val) or close.iloc[-1] < sma_val:
            return None

        return {
            "symbol": symbol,
            "score": float(score),
            "above_sma": True,
        }

    def allocate(
        self,
        data: dict[str, pd.DataFrame],
        date: pd.Timestamp | None = None,
    ) -> dict[str, float]:
        """GTAA 동적 자산배분.

        Args:
            data: {symbol: OHLCV DataFrame}.
            date: 기준 날짜.

        Returns:
            {symbol: weight} 동일가중 배분.
        """
        candidates = []
        for symbol, df in data.items():
            result = self._evaluate_asset(symbol, df, date)
            if result is not None:
                candidates.append(result)

        candidates.sort(key=lambda x: x["score"], reverse=True)
        selected = candidates[: self.config.max_positions]

        if not selected:
            return {}

        weight = round(1.0 / len(selected), 4)
        return {c["symbol"]: weight for c in selected}
