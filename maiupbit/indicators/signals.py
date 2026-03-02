"""Signal generation module.

Provides functions for generating buy/sell signals based on MACD crossovers and adding comprehensive signal columns to a DataFrame.
"""

import numpy as np
import pandas as pd

from maiupbit.indicators.trend import macd as calc_macd
from maiupbit.indicators.momentum import rsi as calc_rsi, stochastic as calc_stochastic
from maiupbit.indicators.volatility import bollinger_bands as calc_bollinger_bands, atr as calc_atr, noise_ratio as calc_noise_ratio
from maiupbit.indicators.momentum import momentum_score as calc_momentum_score


def macd_signal(macd_series: pd.Series, signal_series: pd.Series) -> pd.Series:
    """Generates buy/sell signals based on MACD crossovers.

    MACD > Signal Line  → buy (1)
    MACD < Signal Line  → sell (-1)
    Equal               → neutral (0)

    Args:
        macd_series: MACD line values (pandas Series).
        signal_series: Signal line values (pandas Series).

    Returns:
        A pandas Series containing 1(buy) / -1(sell) / 0(neutral) values.
    """
    signal = pd.Series(index=macd_series.index, data=np.zeros(len(macd_series)), dtype=float)
    signal[macd_series > signal_series] = 1
    signal[macd_series < signal_series] = -1
    return signal


def add_all_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Adds all technical indicator and signal columns to a DataFrame.

    Added columns:
        - SMA_10: 10-day simple moving average
        - EMA_10: 10-day exponential moving average
        - RSI_14: 14-period RSI
        - STOCHk_14_3_3: Stochastic %K
        - STOCHd_14_3_3: Stochastic %D
        - MACD: MACD line
        - Signal_Line: MACD signal line
        - MACD_Histogram: MACD histogram
        - Upper_Band: Bollinger band upper
        - Middle_Band: Bollinger band middle
        - Lower_Band: Bollinger band lower
        - MACD_Signal: Buy(1)/Sell(-1)/Neutral(0) signal

    Args:
        df: OHLCV DataFrame with 'open', 'high', 'low', 'close', 'volume' columns.

    Returns:
        A copy of the DataFrame with indicator and signal columns added.
    """
    df = df.copy()
    close = df["close"]
    high = df["high"]
    low = df["low"]

    # Trend indicators
    df["SMA_10"] = close.rolling(window=10).mean()
    df["EMA_10"] = close.ewm(span=10, adjust=False).mean()

    macd_line, signal_line, histogram = calc_macd(close)
    df["MACD"] = macd_line
    df["Signal_Line"] = signal_line
    df["MACD_Histogram"] = histogram

    # Momentum indicators
    df["RSI_14"] = calc_rsi(close, length=14)
    stoch_k, stoch_d = calc_stochastic(high, low, close, k=14, d=3, smooth_k=3)
    df["STOCHk_14_3_3"] = stoch_k
    df["STOCHd_14_3_3"] = stoch_d

    # Volatility indicators
    upper, middle, lower = calc_bollinger_bands(close, length=20, std_dev=2.0)
    df["Upper_Band"] = upper
    df["Middle_Band"] = middle
    df["Lower_Band"] = lower

    # Quantitative indicators
    df["ATR_14"] = calc_atr(high, low, close, length=14)
    df["Noise_20"] = calc_noise_ratio(df["open"], high, low, close, length=20)
    df["Momentum_Score"] = calc_momentum_score(close)

    # Signals
    df["MACD_Signal"] = macd_signal(df["MACD"], df["Signal_Line"])

    return df