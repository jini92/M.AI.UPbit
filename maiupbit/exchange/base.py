# Trading exchange abstract interface module.

from abc import ABC, abstractmethod

import pandas as pd


class BaseExchange(ABC):
    """Trading exchange common interface abstract base class.

    When integrating a new exchange, inherit from this class and implement all abstract methods.
    """

    @abstractmethod
    def get_ohlcv(self, symbol: str, interval: str, count: int) -> pd.DataFrame:
        """Retrieve OHLCV (open/high/low/close/volume) data.

        Args:
            symbol: Trading symbol (e.g., "KRW-BTC").
            interval: Time interval (e.g., "day", "minute60").
            count: Number of candles to retrieve.

        Returns:
            pandas DataFrame containing OHLCV data.
        """
        ...

    @abstractmethod
    def get_current_price(self, symbol: str) -> float:
        """Retrieve the current price for a specific symbol.

        Args:
            symbol: Trading symbol (e.g., "KRW-BTC").

        Returns:
            Current price (float).
        """
        ...

    @abstractmethod
    def get_orderbook(self, symbol: str) -> dict:
        """Retrieve order book information for a specific symbol.

        Args:
            symbol: Trading symbol (e.g., "KRW-BTC").

        Returns:
            Dictionary containing order book information.
        """
        ...

    @abstractmethod
    def get_portfolio(self) -> dict:
        """Retrieve portfolio information for the current account.

        Returns:
            Dictionary containing market-specific portfolio data.
            Example: {"KRW": pd.DataFrame, "BTC": pd.DataFrame, ...}
        """
        ...

    @abstractmethod
    def buy_market(self, symbol: str, amount: float) -> dict:
        """Execute a market buy order.

        Args:
            symbol: Trading symbol (e.g., "KRW-BTC").
            amount: Purchase amount (in KRW).

        Returns:
            Dictionary containing the order result.
        """
        ...

    @abstractmethod
    def sell_market(self, symbol: str, amount: float) -> dict:
        """Execute a market sell order.

        Args:
            symbol: Trading symbol (e.g., "KRW-BTC").
            amount: Sell quantity.

        Returns:
            Dictionary containing the order result.
        """
        ...