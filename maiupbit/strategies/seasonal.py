"""시즌/사이클 타이밍 필터.

강환국 시즌 전략:
- 10~4월 강세 (비중 확대)
- 5~9월 약세 (비중 축소)
- 비트코인 반감기 사이클 참조
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from maiupbit.strategies.base import StrategyConfig

# 비트코인 반감기 날짜
HALVING_DATES = [
    datetime(2012, 11, 28),
    datetime(2016, 7, 9),
    datetime(2020, 5, 11),
    datetime(2024, 4, 19),
    # 예상
    datetime(2028, 4, 1),
]

# 월별 시즌 성격 (1~12월)
MONTHLY_SEASONALITY: dict[int, str] = {
    1: "bullish",
    2: "bullish",
    3: "bullish",
    4: "bullish",
    5: "bearish",
    6: "bearish",
    7: "bearish",
    8: "bearish",
    9: "bearish",
    10: "bullish",
    11: "bullish",
    12: "bullish",
}


@dataclass
class SeasonalConfig(StrategyConfig):
    """시즌 필터 설정."""

    bullish_months: list[int] = field(
        default_factory=lambda: [10, 11, 12, 1, 2, 3, 4]
    )
    bearish_months: list[int] = field(default_factory=lambda: [5, 6, 7, 8, 9])
    bullish_multiplier: float = 1.2
    bearish_multiplier: float = 0.7
    halving_boost: float = 1.3
    halving_window_days: int = 365


class SeasonalFilter:
    """시즌/반감기 타이밍 필터 (조합용).

    다른 전략의 배분 결과에 시즌 조정을 적용합니다.

    사용:
        allocations = momentum.allocate(data)
        allocations = seasonal.adjust_allocations(allocations, datetime.now())
    """

    def __init__(self, config: SeasonalConfig | None = None) -> None:
        self.config = config or SeasonalConfig()

    def get_season_info(self, date: datetime | None = None) -> dict:
        """현재 시즌 정보 조회.

        Args:
            date: 기준 날짜 (None이면 현재).

        Returns:
            {"month", "season", "multiplier", "halving_phase", "days_since_halving",
             "next_halving", "days_to_next_halving"}.
        """
        if date is None:
            date = datetime.now()

        month = date.month
        season = MONTHLY_SEASONALITY.get(month, "neutral")
        multiplier = (
            self.config.bullish_multiplier
            if month in self.config.bullish_months
            else self.config.bearish_multiplier
        )

        # 반감기 분석
        halving_phase = "unknown"
        days_since = None
        next_halving = None
        days_to_next = None

        past_halvings = [h for h in HALVING_DATES if h <= date]
        future_halvings = [h for h in HALVING_DATES if h > date]

        if past_halvings:
            last_halving = past_halvings[-1]
            days_since = (date - last_halving).days

            if days_since <= self.config.halving_window_days:
                halving_phase = "post_halving_bull"
            elif days_since <= self.config.halving_window_days * 2:
                halving_phase = "mid_cycle"
            else:
                halving_phase = "pre_halving"

        if future_halvings:
            next_halving = future_halvings[0]
            days_to_next = (next_halving - date).days

        return {
            "month": month,
            "season": season,
            "multiplier": round(multiplier, 2),
            "halving_phase": halving_phase,
            "days_since_halving": days_since,
            "next_halving": next_halving.strftime("%Y-%m-%d") if next_halving else None,
            "days_to_next_halving": days_to_next,
        }

    def adjust_allocations(
        self,
        allocations: dict[str, float],
        date: datetime | None = None,
    ) -> dict[str, float]:
        """시즌에 따라 배분 비중 조정.

        Args:
            allocations: {symbol: weight} 원본 배분.
            date: 기준 날짜.

        Returns:
            시즌 조정된 {symbol: weight}.
        """
        if not allocations:
            return allocations

        info = self.get_season_info(date)
        multiplier = info["multiplier"]

        # 반감기 후 강세 구간이면 추가 부스트
        if info["halving_phase"] == "post_halving_bull":
            multiplier *= self.config.halving_boost

        adjusted = {}
        for symbol, weight in allocations.items():
            adjusted[symbol] = round(weight * multiplier, 4)

        # 합계가 1.0을 초과하면 정규화
        total = sum(adjusted.values())
        if total > 1.0:
            for symbol in adjusted:
                adjusted[symbol] = round(adjusted[symbol] / total, 4)

        return adjusted
