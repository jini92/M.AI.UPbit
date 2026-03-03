"""UPbit exchange integration module.

Wraps pyupbit to implement the BaseExchange interface.
Trade records are stored in a JSON file.
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
    """UPbit exchange implementation.

    Wraps the pyupbit library to provide a standard exchange interface.
    Trade records are stored in a JSON file.

    Attributes:
        access_key: UPbit API Access Key.
        secret_key: UPbit API Secret Key.
        trade_history_path: Path to the trade history JSON file (default "trade_history.json").
    """

    def __init__(
        self,
        access_key: str | None = None,
        secret_key: str | None = None,
        trade_history_path: str = "trade_history.json",
    ) -> None:
        """Initialize UPbitExchange.

        Args:
            access_key: UPbit API Access Key (required for trading).
            secret_key: UPbit API Secret Key (required for trading).
            trade_history_path: Path to the trade history JSON file (default "trade_history.json").
        """
        self.access_key = access_key
        self.secret_key = secret_key
        self.trade_history_path = trade_history_path
        self._upbit = pyupbit.Upbit(access_key, secret_key) if access_key and secret_key else None

    # ------------------------------------------------------------------
    # BaseExchange implementation
    # ------------------------------------------------------------------

    def get_ohlcv(
        self,
        symbol: str,
        interval: str = "day",
        count: int = 30,
        to: Optional[str] = None,
    ) -> pd.DataFrame:
        """Retrieve OHLCV data.

        Args:
            symbol: Trading symbol (e.g., "KRW-BTC").
            interval: Time interval (e.g., "day", "minute60").
            count: Number of candles to retrieve.
            to: End date string (YYYY-MM-DD). None for current time.

        Returns:
            OHLCV DataFrame. Returns an empty DataFrame on error.
        """
        try:
            df = pyupbit.get_ohlcv(symbol, interval=interval, count=count, to=to)
            return df if df is not None else pd.DataFrame()
        except Exception as exc:
            logger.error("OHLCV retrieval failed [%s]: %s", symbol, exc)
            return pd.DataFrame()

    def get_current_price(self, symbol: str) -> float:
        """Retrieve current price.

        Args:
            symbol: Trading symbol (e.g., "KRW-BTC").

        Returns:
            Current price. Returns 0.0 on error.
        """
        try:
            price = pyupbit.get_current_price(symbol)
            return float(price) if price is not None else 0.0
        except Exception as exc:
            logger.error("Current price retrieval failed [%s]: %s", symbol, exc)
            return 0.0

    def get_orderbook(self, symbol: str) -> dict:
        """Retrieve order book (order book).

        Args:
            symbol: Trading symbol (e.g., "KRW-BTC").

        Returns:
            Order book information dict. Returns an empty dict on error.
        """
        try:
            orderbook = pyupbit.get_orderbook(ticker=symbol)
            return orderbook if orderbook else {}
        except Exception as exc:
            logger.error("Order book retrieval failed [%s]: %s", symbol, exc)
            return {}

    def get_portfolio(self) -> dict:
        """Retrieve portfolio (balance) information.

        Returns:
            Market-specific portfolio DataFrame in a dict.
            {"KRW": DataFrame, "BTC": DataFrame, "USDT": DataFrame}
        """
        if not self._upbit:
            return {"error": "API keys required for portfolio. Set UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY."}
        balances = self._upbit.get_balances()
        portfolio_data: dict = {"KRW": [], "BTC": [], "USDT": []}

        for balance in balances:
            if not isinstance(balance, dict):
                logger.warning("Unexpected balance format: %s", type(balance))
                continue

            currency: str = balance["currency"]
            quantity: float = float(balance["balance"])
            avg_buy_price: float = float(balance["avg_buy_price"])

            if currency == "KRW":
                current_price = 1.0
                market = "KRW"
                symbol = "KRW"
            else:
                try:
                    symbol = f"KRW-{currency}"
                    current_price = pyupbit.get_current_price(symbol)
                    if not current_price:
                        continue
                    market = "KRW"
                except Exception as exc:
                    logger.error("Failed to retrieve current price for %s: %s", currency, exc)
                    continue

            portfolio_data[market].append(
                {
                    "symbol": symbol,
                    "quantity": quantity,
                    "current_price": current_price,
                    "avg_buy_price": avg_buy_price,
                }
            )

        return {k: pd.DataFrame(v) for k, v in portfolio_data.items()}

    def get_current_status(self, symbol: str) -> str:
        """Return the current trading status as a JSON string.

        Args:
            symbol: Trading symbol (e.g., "KRW-BTC").

        Returns:
            JSON string containing timestamp, orderbook, balance, krw_balance, coin_avg_buy_price.
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
        """Retrieve daily/hourly OHLCV data.

        Args:
            symbol: Trading symbol (e.g., "KRW-BTC").
            start_date: Start date (datetime.date). None for 30 days ago.
            end_date: End date (datetime.date). None for today.

        Returns:
            Tuple of daily_df and hourly_df. Returns (None, None) on error.
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
            logger.error("Data retrieval failed [%s]: %s", symbol, exc)
            return None, None

    @staticmethod
    def get_market_info() -> dict:
        """Retrieve UPbit market information.

        Returns:
            Dict with {Korean name: Market code}. Includes KRW and BTC markets only.
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
            logger.error("Market information retrieval failed: %s", exc)
            return {}

    def get_trade_history(self) -> list:
        """Return stored trade history.

        Returns:
            List of trade records. Returns an empty list if file does not exist.
        """
        if not os.path.exists(self.trade_history_path):
            return []
        try:
            with open(self.trade_history_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.error("Trade history load failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Trading (abstract method implementations)
    # ------------------------------------------------------------------

    def buy_market(self, symbol: str, amount: float) -> dict:
        """Execute a market buy order.

        Args:
            symbol: Trading symbol (e.g., "KRW-BTC").
            amount: Purchase amount (in KRW).

        Returns:
            Dictionary containing the order result.
        """
        if not self._upbit:
            raise RuntimeError("API keys required for trading")
        result = self._upbit.buy_market_order(symbol, amount)
        price = self.get_current_price(symbol)
        self._save_trade(symbol, amount, "buy", price)
        return result

    def sell_market(self, symbol: str, amount: float) -> dict:
        """Execute a market sell order.

        Args:
            symbol: Trading symbol (e.g., "KRW-BTC").
            amount: Sell quantity.

        Returns:
            Dictionary containing the order result.
        """
        if not self._upbit:
            raise RuntimeError("API keys required for trading")
        result = self._upbit.sell_market_order(symbol, amount)
        price = self.get_current_price(symbol)
        self._save_trade(symbol, amount, "sell", price)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save_trade(
        self,
        symbol: str,
        amount: float,
        trade_type: str,
        price: float,
    ) -> None:
        """Save trade record to JSON file.

        Args:
            symbol: Trading symbol.
            amount: Trade quantity or amount.
            trade_type: "buy" or "sell".
            price: Trade price.
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
            logger.error("Trade history save failed: %s", exc)