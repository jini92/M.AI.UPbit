"""전략 프레임워크 기반 클래스.

QuantStrategy (단일 종목)와 PortfolioStrategy (다중 종목) Protocol 정의.
기존 BacktestEngine.run(data, strategy) 호환.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Protocol

import pandas as pd


class QuantStrategy(Protocol):
    """단일 종목 전략 Protocol — BacktestEngine 호환.

    signal() 메서드만 구현하면 기존 BacktestEngine.run()에서 사용 가능.
    """

    def signal(self, data: pd.DataFrame) -> int:
        """매매 시그널 생성.

        Args:
            data: 현재까지의 OHLCV + 지표 데이터.

        Returns:
            1=buy, -1=sell, 0=hold.
        """
        ...


class PortfolioStrategy(Protocol):
    """다중 자산 전략 Protocol — PortfolioBacktestEngine 호환.

    allocate() 메서드로 자산별 비중을 반환.
    """

    def allocate(
        self,
        data: dict[str, pd.DataFrame],
        date: pd.Timestamp | None = None,
    ) -> dict[str, float]:
        """자산배분 비중 산출.

        Args:
            data: {symbol: OHLCV DataFrame} 딕셔너리.
            date: 배분 기준 날짜 (None이면 최신).

        Returns:
            {symbol: weight} 딕셔너리. 합계 <= 1.0 (나머지 현금).
        """
        ...


@dataclass
class StrategyConfig:
    """전략 파라미터 직렬화 기본 클래스."""

    def to_dict(self) -> dict:
        """설정을 딕셔너리로 변환."""
        return asdict(self)
