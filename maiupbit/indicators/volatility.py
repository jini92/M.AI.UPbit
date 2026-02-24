"""변동성 지표 모듈.

볼린저 밴드 계산 함수를 제공합니다.
"""

from typing import Tuple

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
