"""Regression guard tests -- 2026-03-12.

Lock critical indicator parameters to prevent accidental changes.
Uses inspect + re to verify source code defaults without API calls.
"""
from __future__ import annotations

import inspect
import re

import pytest


class TestCriticalSettings:
    """Guard tests for critical indicator parameters."""

    def test_rsi_length_is_14(self) -> None:
        """RSI length must be 14 (crypto standard). Changing breaks signal compatibility."""
        from maiupbit.indicators.momentum import rsi

        src = inspect.getsource(rsi)
        assert "length: int = 14" in src, "RSI default length must be 14"

    def test_bollinger_std_dev_is_2(self) -> None:
        """Bollinger std_dev must be 2.0 (captures ~95% of price action)."""
        from maiupbit.indicators.volatility import bollinger_bands

        src = inspect.getsource(bollinger_bands)
        assert "std_dev: float = 2.0" in src, "Bollinger std_dev default must be 2.0"

    def test_bollinger_length_is_20(self) -> None:
        """Bollinger length must be 20 (standard SMA period)."""
        from maiupbit.indicators.volatility import bollinger_bands

        src = inspect.getsource(bollinger_bands)
        assert "length: int = 20" in src, "Bollinger length default must be 20"

    def test_atr_length_is_14(self) -> None:
        """ATR length must be 14 (Wilder standard)."""
        from maiupbit.indicators.volatility import atr

        src = inspect.getsource(atr)
        assert "length: int = 14" in src, "ATR default length must be 14"

    def test_momentum_periods_locked(self) -> None:
        """Momentum periods must be [28, 84, 168, 365] (Kang framework)."""
        from maiupbit.indicators.momentum import momentum_score

        src = inspect.getsource(momentum_score)
        assert "periods = [28, 84, 168, 365]" in src, (
            "Momentum default periods must be [28, 84, 168, 365]"
        )

    def test_momentum_weights_locked(self) -> None:
        """Momentum weights must be [12, 4, 2, 1] (Kang framework)."""
        from maiupbit.indicators.momentum import momentum_score

        src = inspect.getsource(momentum_score)
        assert "weights = [12, 4, 2, 1]" in src, (
            "Momentum default weights must be [12, 4, 2, 1]"
        )