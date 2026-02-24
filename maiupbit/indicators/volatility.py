"""변동성 지표 모듈.

볼린저 밴드, ATR, 노이즈 비율 계산 함수를 제공합니다.
"""

from typing import Tuple

import numpy as np
import pandas as pd


def bollinger_bands(
    series: pd.Series,
    length: int = 20,
    std_dev: float = 2.0,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """볼린저 밴드(상단, 중간, 하단)를 계산합니다.

    Args:
        series: 종가 등 가격 데이터 (pandas Series).
        length: 이동 평균 및 표준편차 계산 기간 (기본값 20).
        std_dev: 표준편차 배수 (기본값 2.0).

    Returns:
        (upper_band, middle_band, lower_band) 튜플.
        각각 pandas Series.
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
    """Average True Range(ATR)를 계산합니다.

    Args:
        high: 고가 데이터.
        low: 저가 데이터.
        close: 종가 데이터.
        length: ATR 계산 기간 (기본값 14).

    Returns:
        ATR 값을 담은 pandas Series.
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
    """강환국 노이즈 비율을 계산합니다.

    노이즈 = 1 - abs(close - open) / (high - low).
    값이 낮을수록 추세가 강하고 변동성 돌파 전략에 유리합니다.

    Args:
        open_: 시가 데이터.
        high: 고가 데이터.
        low: 저가 데이터.
        close: 종가 데이터.
        length: 이동 평균 기간 (기본값 20).

    Returns:
        노이즈 비율(0~1)의 이동평균 pandas Series.
    """
    daily_range = high - low
    body = (close - open_).abs()
    raw_noise = np.where(daily_range > 0, 1.0 - body / daily_range, 1.0)
    noise_series = pd.Series(raw_noise, index=close.index)
    return noise_series.rolling(window=length).mean()
