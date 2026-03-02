"""Test common settings"""
import pytest
import pandas as pd
import numpy as np


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Test OHLCV data (100 time periods)"""
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
    """Test closing price Series"""
    return sample_ohlcv["close"]