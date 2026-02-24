"""테스트 공통 설정"""
import pytest
import pandas as pd
import numpy as np


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """테스트용 OHLCV 데이터 (100개 시간봉)"""
    np.random.seed(42)
    n = 100
    dates = pd.date_range("2026-01-01", periods=n, freq="h")
    close = 50000 + np.cumsum(np.random.randn(n) * 500)
    return pd.DataFrame(
        {
            "open": close + np.random.randn(n) * 100,
            "high": close + abs(np.random.randn(n) * 200),
            "low": close - abs(np.random.randn(n) * 200),
            "close": close,
            "volume": np.random.randint(100, 10000, n).astype(float),
        },
        index=dates,
    )


@pytest.fixture
def sample_close(sample_ohlcv: pd.DataFrame) -> pd.Series:
    """테스트용 종가 Series"""
    return sample_ohlcv["close"]
