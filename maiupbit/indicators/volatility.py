"""Volatility indicator module.

Provides functions to calculate Bollinger Bands, ATR, and Noise Ratio.
"""

from typing import Tuple

import numpy as np
import pandas as pd


def bollinger_bands(
    series: pd.Series,
    length: int = 20,
    std_dev: float = 2.0,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculates Bollinger Bands (upper, middle, lower).

    Args:
        series: Closing price data or similar (pandas Series).
        length: Period for moving average and standard deviation calculation (default 20).
        std_dev: Standard deviation multiplier (default 2.0).

    Returns:
        Tuple of (upper_band, middle_band, lower_band), each a pandas Series.
    """
    middle = series.rolling(window=length).mean()
    rolling_std = series.rolling(window=length).std()
    upper = middle + (rolling_std * std_dev)
    lower = middle - (rolling_std * std_dev)
    return upper, middle, lower


def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    length: int = 14,
) -> pd.Series:
    """Calculates Average True Range(ATR).

    Args:
        high: High price data.
        low: Low price data.
        close: Closing price data.
        length: Period for ATR calculation (default 14).

    Returns:
        pandas Series containing the ATR values.
    """
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.rolling(window=length).mean()


def noise_ratio(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    length: int = 20,
) -> pd.Series:
    """Calculates the Noise Ratio by Kang Won Gu.

    Noise = 1 - abs(close - open) / (high - low).
    Lower values indicate a stronger trend and are favorable for volatility breakout strategies.

    Args:
        open_: Opening price data.
        high: High price data.
        low: Low price data.
        close: Closing price data.
        length: Period for moving average calculation (default 20).

    Returns:
        pandas Series containing the rolling mean of Noise Ratio values between 0 and 1.
    """
    daily_range = high - low
    body = (close - open_).abs()
    raw_noise = np.where(daily_range > 0, 1.0 - body / daily_range, 1.0)
    noise_series = pd.Series(raw_noise, index=close.index)
    return noise_series.rolling(window=length).mean()