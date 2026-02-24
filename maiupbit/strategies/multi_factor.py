"""다중팩터 랭킹 전략.

강환국 다중팩터 프레임워크를 암호화폐에 적응:
- PER/PBR 대신 모멘텀, 퀄리티(거래량 일관성), 변동성, 단기성과 사용
- 각 팩터 Z-score 기반 복합 랭킹
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from maiupbit.indicators.volatility import atr
from maiupbit.strategies.base import StrategyConfig


@dataclass
class MultiFactorConfig(StrategyConfig):
    """다중팩터 전략 설정."""

    momentum_weight: float = 0.3
    quality_weight: float = 0.2
    volatility_weight: float = 0.2
    performance_weight: float = 0.3
    top_n: int = 5
    rebalance_days: int = 7


class MultiFactorStrategy:
    """다중팩터 랭킹 전략 (PortfolioStrategy 호환).

    팩터:
    - 모멘텀: 28일 수익률
    - 퀄리티: 거래량 CV (변동계수, 낮을수록 일관적)
    - 변동성: ATR/가격 (낮을수록 안정적)
    - 성과: 7일 수익률
    """

    def __init__(self, config: MultiFactorConfig | None = None) -> None:
        self.config = config or MultiFactorConfig()

    def _calculate_factors(
        self,
        data: dict[str, pd.DataFrame],
        date: pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """각 코인의 팩터 값 계산.

        Args:
            data: {symbol: OHLCV DataFrame}.
            date: 기준 날짜.

        Returns:
            팩터 값 DataFrame (index=symbol).
        """
        factors = []
        for symbol, df in data.items():
            if date is not None:
                df = df.loc[:date]
            if len(df) < 30:
                continue

            close = df["close"]

            # 모멘텀: 28일 수익률
            mom_28 = close.pct_change(28).iloc[-1] if len(df) >= 29 else np.nan

            # 퀄리티: 거래량 CV (낮을수록 좋음 → 역수 사용)
            vol_20 = df["volume"].tail(20)
            vol_cv = vol_20.std() / vol_20.mean() if vol_20.mean() > 0 else np.nan
            quality = 1.0 / vol_cv if vol_cv and vol_cv > 0 else 0.0

            # 변동성: ATR/가격 (낮을수록 좋음 → 역수)
            atr_val = atr(df["high"], df["low"], close, length=14).iloc[-1]
            price = close.iloc[-1]
            vol_factor = 1.0 / (atr_val / price) if atr_val > 0 and price > 0 else 0.0

            # 성과: 7일 수익률
            perf_7 = close.pct_change(7).iloc[-1] if len(df) >= 8 else np.nan

            factors.append({
                "symbol": symbol,
                "momentum": mom_28,
                "quality": quality,
                "volatility": vol_factor,
                "performance": perf_7,
            })

        if not factors:
            return pd.DataFrame()
        return pd.DataFrame(factors).set_index("symbol")

    @staticmethod
    def _zscore(series: pd.Series) -> pd.Series:
        """Z-score 표준화."""
        std = series.std()
        if std == 0 or np.isnan(std):
            return pd.Series(0.0, index=series.index)
        return (series - series.mean()) / std

    def rank_coins(
        self,
        data: dict[str, pd.DataFrame],
        date: pd.Timestamp | None = None,
    ) -> list[dict]:
        """다중팩터 기반 코인 랭킹.

        Args:
            data: {symbol: OHLCV DataFrame}.
            date: 기준 날짜.

        Returns:
            [{"symbol", "composite_score", "momentum", "quality", "volatility", "performance", "rank"}].
        """
        factors = self._calculate_factors(data, date)
        if factors.empty:
            return []

        # Z-score 표준화
        z_scores = pd.DataFrame(index=factors.index)
        z_scores["momentum"] = self._zscore(factors["momentum"])
        z_scores["quality"] = self._zscore(factors["quality"])
        z_scores["volatility"] = self._zscore(factors["volatility"])
        z_scores["performance"] = self._zscore(factors["performance"])

        # 복합 점수
        composite = (
            z_scores["momentum"] * self.config.momentum_weight
            + z_scores["quality"] * self.config.quality_weight
            + z_scores["volatility"] * self.config.volatility_weight
            + z_scores["performance"] * self.config.performance_weight
        )

        results = []
        for symbol in composite.sort_values(ascending=False).index:
            results.append({
                "symbol": symbol,
                "composite_score": round(float(composite[symbol]), 4),
                "momentum": round(float(factors.loc[symbol, "momentum"]), 6)
                if not np.isnan(factors.loc[symbol, "momentum"])
                else None,
                "quality": round(float(factors.loc[symbol, "quality"]), 4),
                "volatility": round(float(factors.loc[symbol, "volatility"]), 4),
                "performance": round(float(factors.loc[symbol, "performance"]), 6)
                if not np.isnan(factors.loc[symbol, "performance"])
                else None,
            })

        for i, r in enumerate(results):
            r["rank"] = i + 1
        return results

    def allocate(
        self,
        data: dict[str, pd.DataFrame],
        date: pd.Timestamp | None = None,
    ) -> dict[str, float]:
        """다중팩터 랭킹 기반 동일가중 배분.

        Args:
            data: {symbol: OHLCV DataFrame}.
            date: 기준 날짜.

        Returns:
            {symbol: weight} 상위 N개 동일가중.
        """
        rankings = self.rank_coins(data, date)
        selected = rankings[: self.config.top_n]

        if not selected:
            return {}

        weight = round(1.0 / len(selected), 4)
        return {r["symbol"]: weight for r in selected}
