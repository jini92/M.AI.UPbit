"""퀀트 지표 단위 테스트 — ATR, noise_ratio, momentum_score, average_momentum_signal."""
import pandas as pd


class TestATR:
    def test_atr_basic(self, sample_ohlcv: pd.DataFrame) -> None:
        from maiupbit.indicators.volatility import atr

        result = atr(sample_ohlcv["high"], sample_ohlcv["low"], sample_ohlcv["close"])
        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_ohlcv)
        # 처음 13개는 NaN (rolling(14), TR은 index 0부터 유효)
        assert result.iloc[:13].isna().all()
        assert not result.iloc[13:].isna().any()
        # 유효값은 양수
        valid = result.dropna()
        assert (valid > 0).all()

    def test_atr_custom_length(self, sample_ohlcv: pd.DataFrame) -> None:
        from maiupbit.indicators.volatility import atr

        result = atr(
            sample_ohlcv["high"], sample_ohlcv["low"], sample_ohlcv["close"],
            length=7,
        )
        assert result.iloc[:6].isna().all()
        assert not result.iloc[6:].isna().any()


class TestNoiseRatio:
    def test_noise_ratio_range(self, sample_ohlcv: pd.DataFrame) -> None:
        from maiupbit.indicators.volatility import noise_ratio

        result = noise_ratio(
            sample_ohlcv["open"], sample_ohlcv["high"],
            sample_ohlcv["low"], sample_ohlcv["close"],
        )
        assert isinstance(result, pd.Series)
        valid = result.dropna()
        assert (valid >= 0).all()
        assert (valid <= 1).all()

    def test_noise_ratio_custom_length(self, sample_ohlcv: pd.DataFrame) -> None:
        from maiupbit.indicators.volatility import noise_ratio

        result = noise_ratio(
            sample_ohlcv["open"], sample_ohlcv["high"],
            sample_ohlcv["low"], sample_ohlcv["close"],
            length=10,
        )
        # rolling(10): 처음 9개 NaN
        assert result.iloc[:9].isna().all()
        assert not result.iloc[9:].isna().any()


class TestMomentumScore:
    def test_momentum_score_basic(self, sample_ohlcv: pd.DataFrame) -> None:
        from maiupbit.indicators.momentum import momentum_score

        result = momentum_score(sample_ohlcv["close"])
        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_ohlcv)

    def test_momentum_score_custom_periods(self, sample_ohlcv: pd.DataFrame) -> None:
        from maiupbit.indicators.momentum import momentum_score

        result = momentum_score(
            sample_ohlcv["close"],
            periods=[7, 14, 28],
            weights=[3, 2, 1],
        )
        assert isinstance(result, pd.Series)
        # 7일 이전은 NaN 포함 가능
        valid = result.dropna()
        assert len(valid) > 0


class TestAverageMomentumSignal:
    def test_average_momentum_signal_range(self, sample_ohlcv: pd.DataFrame) -> None:
        from maiupbit.indicators.momentum import average_momentum_signal

        result = average_momentum_signal(sample_ohlcv["close"])
        assert isinstance(result, pd.Series)
        valid = result.dropna()
        assert (valid >= 0).all()
        assert (valid <= 1).all()

    def test_average_momentum_signal_custom(self, sample_ohlcv: pd.DataFrame) -> None:
        from maiupbit.indicators.momentum import average_momentum_signal

        result = average_momentum_signal(
            sample_ohlcv["close"],
            lookbacks=[7, 14, 21],
        )
        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_ohlcv)


class TestAddAllSignals:
    def test_quant_columns_added(self, sample_ohlcv: pd.DataFrame) -> None:
        from maiupbit.indicators.signals import add_all_signals

        result = add_all_signals(sample_ohlcv)
        assert "ATR_14" in result.columns
        assert "Noise_20" in result.columns
        assert "Momentum_Score" in result.columns
        # 기존 컬럼도 유지
        assert "RSI_14" in result.columns
        assert "MACD_Signal" in result.columns
