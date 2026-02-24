"""기술 지표 단위 테스트"""
import pytest
import pandas as pd
import numpy as np


class TestTrend:
    def test_sma(self, sample_ohlcv: pd.DataFrame) -> None:
        from maiupbit.indicators.trend import sma

        result = sma(sample_ohlcv["close"], 10)
        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_ohlcv)
        assert result.iloc[:9].isna().all()
        assert not result.iloc[9:].isna().any()

    def test_ema(self, sample_ohlcv: pd.DataFrame) -> None:
        from maiupbit.indicators.trend import ema

        result = ema(sample_ohlcv["close"], 10)
        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_ohlcv)

    def test_macd(self, sample_ohlcv: pd.DataFrame) -> None:
        from maiupbit.indicators.trend import macd

        result = macd(sample_ohlcv["close"])
        # macd returns tuple of 3 Series: (macd_line, signal_line, histogram)
        assert isinstance(result, tuple)
        assert len(result) == 3
        for series in result:
            assert isinstance(series, pd.Series)


class TestMomentum:
    def test_rsi(self, sample_ohlcv: pd.DataFrame) -> None:
        from maiupbit.indicators.momentum import rsi

        result = rsi(sample_ohlcv["close"], 14)
        assert isinstance(result, pd.Series)
        valid = result.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_stochastic(self, sample_ohlcv: pd.DataFrame) -> None:
        from maiupbit.indicators.momentum import stochastic

        result = stochastic(
            sample_ohlcv["high"], sample_ohlcv["low"], sample_ohlcv["close"]
        )
        # stochastic returns tuple of 2 Series: (k, d)
        assert isinstance(result, tuple)
        assert len(result) == 2
        for series in result:
            assert isinstance(series, pd.Series)


class TestVolatility:
    def test_bollinger_bands(self, sample_ohlcv: pd.DataFrame) -> None:
        from maiupbit.indicators.volatility import bollinger_bands

        result = bollinger_bands(sample_ohlcv["close"])
        # bollinger_bands returns tuple of 3 Series: (upper, middle, lower)
        assert isinstance(result, tuple)
        assert len(result) == 3
        upper, middle, lower = result
        assert isinstance(upper, pd.Series)
        # upper >= middle >= lower (where not NaN)
        valid_idx = upper.dropna().index
        assert (upper[valid_idx] >= middle[valid_idx]).all()
        assert (middle[valid_idx] >= lower[valid_idx]).all()


class TestSignals:
    def test_macd_signal(self, sample_ohlcv: pd.DataFrame) -> None:
        from maiupbit.indicators.trend import macd
        from maiupbit.indicators.signals import macd_signal

        macd_line, signal_line, _ = macd(sample_ohlcv["close"])
        result = macd_signal(macd_line, signal_line)
        assert isinstance(result, pd.Series)
        assert set(result.dropna().unique()).issubset({-1, 0, 1})
