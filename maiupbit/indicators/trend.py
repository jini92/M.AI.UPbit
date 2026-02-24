"""추세 지표 모듈.

SMA, EMA, MACD 계산 함수를 제공합니다.
"""

from typing import Tuple

import pandas as pd


def sma(series: pd.Series, length: int) -> pd.Series:
    """단순 이동 평균(SMA)을 계산합니다.

    Args:
        series: 종가 등 가격 데이터 (pandas Series).
        length: 이동 평균 기간.

    Returns:
        SMA 값을 담은 pandas Series.
    """
    return series.rolling(window=length).mean()


def ema(series: pd.Series, length: int) -> pd.Series:
    """지수 이동 평균(EMA)을 계산합니다.

    Args:
        series: 종가 등 가격 데이터 (pandas Series).
        length: EMA 기간.

    Returns:
        EMA 값을 담은 pandas Series.
    """
    return series.ewm(span=length, adjust=False).mean()


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """MACD, Signal Line, Histogram을 계산합니다.

    Args:
        series: 종가 등 가격 데이터 (pandas Series).
        fast: 빠른 EMA 기간 (기본값 12).
        slow: 느린 EMA 기간 (기본값 26).
        signal: Signal Line EMA 기간 (기본값 9).

    Returns:
        (macd_line, signal_line, histogram) 튜플.
        각각 pandas Series.
    """
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram
