"""거래소 추상 인터페이스 모듈.

모든 거래소 구현체가 상속해야 할 BaseExchange ABC를 정의합니다.
"""

from abc import ABC, abstractmethod

import pandas as pd


class BaseExchange(ABC):
    """거래소 공통 인터페이스 추상 기본 클래스.

    새로운 거래소 연동 시 이 클래스를 상속하여
    모든 추상 메서드를 구현해야 합니다.
    """

    @abstractmethod
    def get_ohlcv(self, symbol: str, interval: str, count: int) -> pd.DataFrame:
        """OHLCV(시가/고가/저가/종가/거래량) 데이터를 조회합니다.

        Args:
            symbol: 거래 심볼 (예: "KRW-BTC").
            interval: 시간 간격 (예: "day", "minute60").
            count: 조회할 캔들 수.

        Returns:
            OHLCV 데이터가 담긴 pandas DataFrame.
        """
        ...

    @abstractmethod
    def get_current_price(self, symbol: str) -> float:
        """특정 심볼의 현재 가격을 조회합니다.

        Args:
            symbol: 거래 심볼 (예: "KRW-BTC").

        Returns:
            현재 가격 (float).
        """
        ...

    @abstractmethod
    def get_orderbook(self, symbol: str) -> dict:
        """특정 심볼의 호가창(오더북) 정보를 조회합니다.

        Args:
            symbol: 거래 심볼 (예: "KRW-BTC").

        Returns:
            오더북 정보를 담은 dict.
        """
        ...

    @abstractmethod
    def get_portfolio(self) -> dict:
        """현재 계좌의 보유 자산(포트폴리오) 정보를 조회합니다.

        Returns:
            시장별 포트폴리오 데이터를 담은 dict.
            예: {"KRW": pd.DataFrame, "BTC": pd.DataFrame, ...}
        """
        ...

    @abstractmethod
    def buy_market(self, symbol: str, amount: float) -> dict:
        """시장가 매수 주문을 실행합니다.

        Args:
            symbol: 거래 심볼 (예: "KRW-BTC").
            amount: 매수 금액 (KRW 기준).

        Returns:
            주문 결과를 담은 dict.
        """
        ...

    @abstractmethod
    def sell_market(self, symbol: str, amount: float) -> dict:
        """시장가 매도 주문을 실행합니다.

        Args:
            symbol: 거래 심볼 (예: "KRW-BTC").
            amount: 매도 수량.

        Returns:
            주문 결과를 담은 dict.
        """
        ...
