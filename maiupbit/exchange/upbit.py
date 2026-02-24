"""UPbit 거래소 연동 모듈.

pyupbit를 래핑하여 BaseExchange 인터페이스를 구현합니다.
거래 기록은 JSON 파일로 저장합니다.
"""

import json
import logging
import os
import requests
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import pyupbit

from maiupbit.exchange.base import BaseExchange

logger = logging.getLogger(__name__)


class UPbitExchange(BaseExchange):
    """UPbit 거래소 구현체.

    pyupbit 라이브러리를 래핑하여 표준 거래소 인터페이스를 제공합니다.
    거래 기록은 JSON 파일로 저장됩니다.

    Attributes:
        access_key: UPbit API Access Key.
        secret_key: UPbit API Secret Key.
        trade_history_path: 거래 기록 JSON 파일 경로.
    """

    def __init__(
        self,
        access_key: str | None = None,
        secret_key: str | None = None,
        trade_history_path: str = "trade_history.json",
    ) -> None:
        """UPbitExchange 초기화.

        Args:
            access_key: UPbit API Access Key (없으면 시세 조회만 가능).
            secret_key: UPbit API Secret Key (없으면 시세 조회만 가능).
            trade_history_path: 거래 기록 JSON 파일 경로 (기본값: "trade_history.json").
        """
        self.access_key = access_key
        self.secret_key = secret_key
        self.trade_history_path = trade_history_path
        self._upbit = pyupbit.Upbit(access_key, secret_key) if access_key and secret_key else None

    # ------------------------------------------------------------------
    # BaseExchange 구현
    # ------------------------------------------------------------------

    def get_ohlcv(
        self,
        symbol: str,
        interval: str = "day",
        count: int = 30,
        to: Optional[str] = None,
    ) -> pd.DataFrame:
        """OHLCV 데이터를 조회합니다.

        Args:
            symbol: 거래 심볼 (예: "KRW-BTC").
            interval: 시간 간격 (예: "day", "minute60").
            count: 조회할 캔들 수.
            to: 종료 날짜 문자열 (YYYY-MM-DD). None이면 현재 시각.

        Returns:
            OHLCV DataFrame. 오류 발생 시 빈 DataFrame 반환.
        """
        try:
            df = pyupbit.get_ohlcv(symbol, interval=interval, count=count, to=to)
            return df if df is not None else pd.DataFrame()
        except Exception as exc:
            logger.error("OHLCV 조회 실패 [%s]: %s", symbol, exc)
            return pd.DataFrame()

    def get_current_price(self, symbol: str) -> float:
        """현재 가격을 조회합니다.

        Args:
            symbol: 거래 심볼 (예: "KRW-BTC").

        Returns:
            현재 가격. 오류 발생 시 0.0 반환.
        """
        try:
            price = pyupbit.get_current_price(symbol)
            return float(price) if price is not None else 0.0
        except Exception as exc:
            logger.error("현재 가격 조회 실패 [%s]: %s", symbol, exc)
            return 0.0

    def get_orderbook(self, symbol: str) -> dict:
        """오더북(호가창) 정보를 조회합니다.

        Args:
            symbol: 거래 심볼 (예: "KRW-BTC").

        Returns:
            오더북 정보 dict. 오류 발생 시 빈 dict 반환.
        """
        try:
            orderbook = pyupbit.get_orderbook(ticker=symbol)
            return orderbook if orderbook else {}
        except Exception as exc:
            logger.error("오더북 조회 실패 [%s]: %s", symbol, exc)
            return {}

    def get_portfolio(self) -> dict:
        """보유 자산(포트폴리오) 정보를 조회합니다.

        Returns:
            시장별 포트폴리오 DataFrame을 담은 dict.
            {"KRW": DataFrame, "BTC": DataFrame, "USDT": DataFrame}
        """
        if not self._upbit:
            return {"error": "API keys required for portfolio. Set UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY."}
        balances = self._upbit.get_balances()
        portfolio_data: dict = {"KRW": [], "BTC": [], "USDT": []}

        for balance in balances:
            if not isinstance(balance, dict):
                logger.warning("예상치 못한 잔고 형식: %s", type(balance))
                continue

            currency: str = balance["currency"]
            quantity: float = float(balance["balance"])
            avg_buy_price: float = float(balance["avg_buy_price"])

            if currency == "KRW":
                current_price = 1.0
                market = "KRW"
                symbol = "KRW"
            else:
                current_price = 0.0
                market = "KRW"
                for mkt in ["KRW", "BTC", "USDT"]:
                    sym = f"{mkt}-{currency}"
                    try:
                        price = pyupbit.get_current_price(sym)
                        if price:
                            current_price = float(price)
                            market = mkt
                            symbol = sym
                            break
                    except Exception:
                        continue
                else:
                    continue

            value = quantity * current_price
            pnl = value - (quantity * avg_buy_price)
            asset_type = "Crypto" if currency != "KRW" else "Cash"

            portfolio_data[market].append(
                {
                    "asset_type": asset_type,
                    "symbol": symbol,
                    "currency": currency,
                    "quantity": quantity,
                    "current_price": current_price,
                    "avg_buy_price": avg_buy_price,
                    "value": value,
                    "pnl": pnl,
                }
            )

        # 플랫 리스트 + 총 자산 합산
        all_assets = []
        total_value = 0.0
        for mkt, items in portfolio_data.items():
            for item in items:
                all_assets.append(item)
                total_value += item["value"]

        return {"assets": all_assets, "total_value": total_value}

    def buy_market(self, symbol: str, amount: float) -> dict:
        """시장가 매수 주문을 실행합니다.

        Args:
            symbol: 거래 심볼 (예: "KRW-BTC").
            amount: 매수 금액 (KRW 기준).

        Returns:
            주문 결과 dict. 실패 시 {"error": str} 반환.
        """
        if not self._upbit:
            return {"error": "API keys required for trading."}
        logger.info("시장가 매수 시도: %s, 금액 %s", symbol, amount)
        try:
            result = self._upbit.buy_market_order(symbol, amount)
            logger.info("매수 성공: %s", result)
            price = result.get("price", 0.0) if isinstance(result, dict) else 0.0
            self._save_trade(symbol, amount, "buy", price)
            return result if isinstance(result, dict) else {"result": result}
        except Exception as exc:
            logger.error("매수 실패 [%s]: %s", symbol, exc)
            return {"error": str(exc)}

    def sell_market(self, symbol: str, amount: float) -> dict:
        """시장가 매도 주문을 실행합니다.

        Args:
            symbol: 거래 심볼 (예: "KRW-BTC").
            amount: 매도 수량.

        Returns:
            주문 결과 dict. 실패 시 {"error": str} 반환.
        """
        if not self._upbit:
            return {"error": "API keys required for trading."}
        logger.info("시장가 매도 시도: %s, 수량 %s", symbol, amount)
        try:
            result = self._upbit.sell_market_order(symbol, amount)
            logger.info("매도 성공: %s", result)
            price = result.get("price", 0.0) if isinstance(result, dict) else 0.0
            self._save_trade(symbol, amount, "sell", price)
            return result if isinstance(result, dict) else {"result": result}
        except Exception as exc:
            logger.error("매도 실패 [%s]: %s", symbol, exc)
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # 추가 유틸리티 메서드
    # ------------------------------------------------------------------

    def get_current_status(self, symbol: str) -> str:
        """현재 거래 상태를 JSON 문자열로 반환합니다.

        Args:
            symbol: 거래 심볼 (예: "KRW-BTC").

        Returns:
            timestamp, orderbook, balance, krw_balance, coin_avg_buy_price를
            포함한 JSON 문자열.
        """
        orderbook = self.get_orderbook(symbol)
        current_time = orderbook.get("timestamp") if isinstance(orderbook, dict) else None
        balance = self._upbit.get_balance(ticker=symbol)
        avg_buy_price = self._upbit.get_avg_buy_price(ticker=symbol)
        krw_balance = self._upbit.get_balance(ticker="KRW")

        import json
        return json.dumps(
            {
                "current_time": current_time,
                "orderbook": orderbook,
                "balance": balance,
                "krw_balance": krw_balance,
                "coin_avg_buy_price": avg_buy_price,
            }
        )

    def fetch_data(
        self,
        symbol: str,
        start_date=None,
        end_date=None,
    ):
        """일별/시간별 OHLCV 데이터를 조회합니다.

        Args:
            symbol: 거래 심볼 (예: "KRW-BTC").
            start_date: 시작 날짜 (datetime.date). None이면 30일 전.
            end_date: 종료 날짜 (datetime.date). None이면 오늘.

        Returns:
            (daily_df, hourly_df) 튜플. 오류 시 (None, None) 반환.
        """
        from datetime import date as date_type

        if end_date is None:
            end_date = datetime.now().date()
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        try:
            count_daily = (end_date - start_date).days + 1
            count_hourly = count_daily * 24
            end_str = end_date.strftime("%Y-%m-%d")

            daily_data = pyupbit.get_ohlcv(symbol, "day", to=end_str, count=count_daily)
            hourly_data = pyupbit.get_ohlcv(symbol, interval="minute60", to=end_str, count=count_hourly)
            return daily_data, hourly_data
        except Exception as exc:
            logger.error("데이터 조회 실패 [%s]: %s", symbol, exc)
            return None, None

    @staticmethod
    def get_market_info() -> dict:
        """UPbit 전체 마켓 정보를 조회합니다.

        Returns:
            {한국명: 마켓코드} 형태의 dict.
            KRW 및 BTC 마켓만 포함합니다.
        """
        url = "https://api.upbit.com/v1/market/all"
        try:
            response = requests.get(url, timeout=10)
            markets_info = response.json()
            return {
                m["korean_name"]: m["market"]
                for m in markets_info
                if "BTC-" in m["market"] or "KRW-" in m["market"]
            }
        except Exception as exc:
            logger.error("마켓 정보 조회 실패: %s", exc)
            return {}

    def get_trade_history(self) -> list:
        """저장된 거래 기록을 반환합니다.

        Returns:
            거래 기록 list. 파일이 없으면 빈 리스트 반환.
        """
        if not os.path.exists(self.trade_history_path):
            return []
        try:
            with open(self.trade_history_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.error("거래 기록 로드 실패: %s", exc)
            return []

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _save_trade(
        self,
        symbol: str,
        amount: float,
        trade_type: str,
        price: float,
    ) -> None:
        """거래 기록을 JSON 파일에 저장합니다.

        Args:
            symbol: 거래 심볼.
            amount: 거래 수량 또는 금액.
            trade_type: "buy" 또는 "sell".
            price: 거래 가격.
        """
        history = self.get_trade_history()
        history.append(
            {
                "id": len(history) + 1,
                "symbol": symbol,
                "amount": amount,
                "trade_type": trade_type,
                "price": price,
                "timestamp": datetime.now().isoformat(),
            }
        )
        try:
            with open(self.trade_history_path, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.error("거래 기록 저장 실패: %s", exc)
