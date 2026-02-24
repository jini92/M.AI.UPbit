"""모멘텀 지표 모듈.

RSI, 스토캐스틱 계산 함수를 제공합니다.
"""

from typing import Tuple

import numpy as np
import pandas as pd


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    """RSI(상대강도지수)를 계산합니다.

    Args:
        series: 종가 등 가격 데이터 (pandas Series).
        length: RSI 계산 기간 (기본값 14).

    Returns:
        RSI 값(0~100 범위)을 담은 pandas Series.
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
    """스토캐스틱 %K와 %D를 계산합니다.

    Args:
        high: 고가 데이터 (pandas Series).
        low: 저가 데이터 (pandas Series).
        close: 종가 데이터 (pandas Series).
        k: %K 계산 기간 (기본값 14).
        d: %D SMA 기간 (기본값 3).
        smooth_k: %K 스무딩 기간 (기본값 3).

    Returns:
        (stoch_k, stoch_d) 튜플.
        각각 pandas Series.
    """
    lowest_low = low.rolling(window=k).min()
    highest_high = high.rolling(window=k).max()

    raw_k = 100 * (close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
    stoch_k = raw_k.rolling(window=smooth_k).mean()
    stoch_d = stoch_k.rolling(window=d).mean()

    return stoch_k, stoch_d
