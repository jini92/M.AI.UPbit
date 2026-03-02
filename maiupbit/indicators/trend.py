"""Trend indicator module.

Provides functions to calculate SMA, EMA, and MACD.
"""

from typing import Tuple

import pandas as pd


def sma(series: pd.Series, length: int) -> pd.Series:
    """Calculates the Simple Moving Average (SMA).

    Args:
        series: Closing price data or similar (pandas Series).
        length: Period for moving average.

    Returns:
        A pandas Series containing SMA values.
    """
    return series.rolling(window=length).mean()


def ema(series: pd.Series, length: int) -> pd.Series:
    """Calculates the Exponential Moving Average (EMA).

    Args:
        series: Closing price data or similar (pandas Series).
        length: Period for EMA.

    Returns:
        A pandas Series containing EMA values.
    """
    return series.ewm(span=length, adjust=False).mean()


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculates MACD, Signal Line, and Histogram.

    Args:
        series: Closing price data or similar (pandas Series).
        fast: Period for the fast EMA (default 12).
        slow: Period for the slow EMA (default 26).
        signal: Period for the Signal Line EMA (default 9).

    Returns:
        A tuple of (macd_line, signal_line, histogram), each a pandas Series.
    """
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram