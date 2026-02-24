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


def momentum_score(
    close: pd.Series,
    periods: list[int] | None = None,
    weights: list[float] | None = None,
) -> pd.Series:
    """강환국 가중 모멘텀 점수를 계산합니다.

    각 기간의 수익률에 가중치를 곱한 합으로 종합 모멘텀을 산출합니다.
    암호화폐 기본값: 28/84/168/365일, 가중치 12/4/2/1.

    Args:
        close: 종가 데이터.
        periods: 모멘텀 계산 기간 리스트 (기본값 [28, 84, 168, 365]).
        weights: 각 기간의 가중치 (기본값 [12, 4, 2, 1]).

    Returns:
        가중 모멘텀 점수 pandas Series.
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
    """12개 개별 모멘텀의 평균 시그널을 계산합니다.

    각 lookback 기간에서 수익률 > 0이면 1, 아니면 0으로
    개별 모멘텀 시그널을 생성하고 평균을 구합니다(0~1).
    결과값은 포지션 비중으로 사용 가능합니다.

    Args:
        close: 종가 데이터.
        lookbacks: 개별 모멘텀 기간 리스트.
            기본값: [7, 14, 21, 28, 35, 42, 49, 56, 63, 70, 77, 84].

    Returns:
        평균 모멘텀 시그널(0~1) pandas Series.
    """
    if lookbacks is None:
        lookbacks = [7, 14, 21, 28, 35, 42, 49, 56, 63, 70, 77, 84]

    signals = pd.DataFrame(index=close.index)
    for lb in lookbacks:
        ret = close.pct_change(lb)
        signals[f"mom_{lb}"] = (ret > 0).astype(float)
    return signals.mean(axis=1)
