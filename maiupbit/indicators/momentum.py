"""Momentum indicator module.

Provides functions to calculate RSI and stochastic values.
"""

from typing import Tuple

import numpy as np
import pandas as pd


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    """Calculates the Relative Strength Index (RSI).

    Args:
        series: Closing price data or similar (pandas Series).
        length: RSI calculation period (default is 14).

    Returns:
        pandas Series containing RSI values in the range of 0 to 100.
    """
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(com=length - 1, min_periods=length).mean()
    avg_loss = loss.ewm(com=length - 1, min_periods=length).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_values = 100 - (100 / (1 + rs))
    return rsi_values


def stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k: int = 14,
    d: int = 3,
    smooth_k: int = 3,
) -> Tuple[pd.Series, pd.Series]:
    """Calculates the Stochastic %K and %D.

    Args:
        high: High price data (pandas Series).
        low: Low price data (pandas Series).
        close: Closing price data (pandas Series).
        k: Period for %K calculation (default is 14).
        d: SMA period for %D (default is 3).
        smooth_k: Smoothing period for %K (default is 3).

    Returns:
        Tuple of (stoch_k, stoch_d), each a pandas Series.
    """
    lowest_low = low.rolling(window=k).min()
    highest_high = high.rolling(window=k).max()

    raw_k = 100 * (close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
    stoch_k = raw_k.rolling(window=smooth_k).mean()
    stoch_d = stoch_k.rolling(window=d).mean()

    return stoch_k, stoch_d


def momentum_score(
    close: pd.Series,
    periods: list[int] | None = None,
    weights: list[float] | None = None,
) -> pd.Series:
    """Calculates the weighted momentum score by Kang.

    Calculates a comprehensive momentum by summing up the product of returns
    and weights for each period. Default crypto values are 28/84/168/365 days, 
    with weights 12/4/2/1 respectively.

    Args:
        close: Closing price data.
        periods: List of momentum calculation periods (default is [28, 84, 168, 365]).
        weights: Weights for each period (default is [12, 4, 2, 1]).

    Returns:
        pandas Series containing the weighted momentum score.
    """
    if periods is None:
        periods = [28, 84, 168, 365]
    if weights is None:
        weights = [12, 4, 2, 1]

    total_weight = sum(weights)
    score = pd.Series(0.0, index=close.index)
    for period, weight in zip(periods, weights):
        ret = close.pct_change(period)
        score = score + ret * (weight / total_weight)
    return score


def average_momentum_signal(
    close: pd.Series,
    lookbacks: list[int] | None = None,
) -> pd.Series:
    """Calculates the average signal of 12 individual momentum indicators.

    For each lookback period, generates an individual momentum signal with
    a value of 1 if return > 0 and 0 otherwise. Then calculates the mean (0~1).
    The result can be used as position weight.

    Args:
        close: Closing price data.
        lookbacks: List of periods for individual momentum signals.
            Default is [7, 14, 21, 28, 35, 42, 49, 56, 63, 70, 77, 84].

    Returns:
        pandas Series containing the average momentum signal (0~1).
    """
    if lookbacks is None:
        lookbacks = [7, 14, 21, 28, 35, 42, 49, 56, 63, 70, 77, 84]

    signals = pd.DataFrame(index=close.index)
    for lb in lookbacks:
        ret = close.pct_change(lb)
        signals[f"mom_{lb}"] = (ret > 0).astype(float)
    return signals.mean(axis=1)