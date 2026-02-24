"""시그널 생성 모듈.

MACD 크로스오버 기반 매수/매도 시그널 및
DataFrame 전체 시그널 추가 함수를 제공합니다.
"""

import numpy as np
import pandas as pd

from maiupbit.indicators.trend import macd as calc_macd
from maiupbit.indicators.momentum import rsi as calc_rsi, stochastic as calc_stochastic
from maiupbit.indicators.volatility import bollinger_bands as calc_bollinger_bands, atr as calc_atr, noise_ratio as calc_noise_ratio
from maiupbit.indicators.momentum import momentum_score as calc_momentum_score


def macd_signal(macd_series: pd.Series, signal_series: pd.Series) -> pd.Series:
    """MACD 크로스오버 기반 매수/매도 시그널을 생성합니다.

    MACD > Signal Line  → buy  ( 1)
    MACD < Signal Line  → sell (-1)
    같음                → neutral (0)

    Args:
        macd_series: MACD 라인 값 (pandas Series).
        signal_series: Signal Line 값 (pandas Series).

    Returns:
        1(buy) / -1(sell) / 0(neutral) 값을 담은 pandas Series.
    """
    signal = pd.Series(index=macd_series.index, data=np.zeros(len(macd_series)), dtype=float)
    signal[macd_series > signal_series] = 1
    signal[macd_series < signal_series] = -1
    return signal


def add_all_signals(df: pd.DataFrame) -> pd.DataFrame:
    """DataFrame에 모든 기술 지표 및 시그널 컬럼을 추가합니다.

    추가되는 컬럼:
        - SMA_10: 10일 단순 이동 평균
        - EMA_10: 10일 지수 이동 평균
        - RSI_14: 14기간 RSI
        - STOCHk_14_3_3: 스토캐스틱 %K
        - STOCHd_14_3_3: 스토캐스틱 %D
        - MACD: MACD 라인
        - Signal_Line: MACD Signal Line
        - MACD_Histogram: MACD Histogram
        - Upper_Band: 볼린저 밴드 상단
        - Middle_Band: 볼린저 밴드 중간
        - Lower_Band: 볼린저 밴드 하단
        - MACD_Signal: 매수(1)/매도(-1)/중립(0) 시그널

    Args:
        df: 'open', 'high', 'low', 'close', 'volume' 컬럼을 포함한 OHLCV DataFrame.

    Returns:
        지표 및 시그널 컬럼이 추가된 DataFrame (원본 수정 없이 복사본 반환).
    """
    df = df.copy()
    close = df["close"]
    high = df["high"]
    low = df["low"]

    # 추세 지표
    df["SMA_10"] = close.rolling(window=10).mean()
    df["EMA_10"] = close.ewm(span=10, adjust=False).mean()

    macd_line, signal_line, histogram = calc_macd(close)
    df["MACD"] = macd_line
    df["Signal_Line"] = signal_line
    df["MACD_Histogram"] = histogram

    # 모멘텀 지표
    df["RSI_14"] = calc_rsi(close, length=14)
    stoch_k, stoch_d = calc_stochastic(high, low, close, k=14, d=3, smooth_k=3)
    df["STOCHk_14_3_3"] = stoch_k
    df["STOCHd_14_3_3"] = stoch_d

    # 변동성 지표
    upper, middle, lower = calc_bollinger_bands(close, length=20, std_dev=2.0)
    df["Upper_Band"] = upper
    df["Middle_Band"] = middle
    df["Lower_Band"] = lower

    # 퀀트 지표
    df["ATR_14"] = calc_atr(high, low, close, length=14)
    df["Noise_20"] = calc_noise_ratio(df["open"], high, low, close, length=20)
    df["Momentum_Score"] = calc_momentum_score(close)

    # 시그널
    df["MACD_Signal"] = macd_signal(df["MACD"], df["Signal_Line"])

    return df
