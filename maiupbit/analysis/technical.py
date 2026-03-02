# -*- coding: utf-8 -*-
"""
maiupbit.analysis.technical
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Technical analysis engine.

Calculates moving averages, Bollinger Bands, RSI, MACD, Stochastic indicators,
and provides coin recommendation algorithms (trend-based / performance-based).

Usage example::

    analyzer = TechnicalAnalyzer(exchange=pyupbit)
    result = analyzer.analyze("KRW-BTC", df)
    trend_picks = analyzer.recommend_by_trend(top_n=5)
    perf_picks  = analyzer.recommend_by_performance(top_n=5, days=7)
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    def __init__(self, exchange):
        self.exchange = exchange

    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators to the DataFrame."""
        df["SMA_10"] = df["close"].rolling(window=10).mean()
        df["EMA_10"] = df["close"].ewm(span=10, adjust=False).mean()
        df["RSI_14"] = self._calculate_rsi(df["close"], window=14)
        std = df["close"].rolling(window=20).std()
        df["Upper_Band"] = df["EMA_10"] + std * 2
        return df

    def _calculate_rsi(self, prices: pd.Series, window: int) -> pd.Series:
        """Calculate RSI."""
        delta = prices.diff().dropna()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=window).mean()
        avg_loss = loss.rolling(window=window).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _safe_float(self, value: Any) -> Optional[float]:
        """Utility to convert NaN and None to None."""
        try:
            f = float(value)
            return None if (f != f) else f  # Check for NaN
        except (TypeError, ValueError):
            return None

    def analyze(self, symbol: str, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze the given DataFrame and provide technical indicators."""
        df = self._add_indicators(df)
        last = df.iloc[-1]

        indicators = {
            "sma_10": _safe_float(last.get("SMA_10")),
            "ema_10": _safe_float(last.get("EMA_10")),
            "rsi_14": _safe_float(last.get("RSI_14")),
            "upper_band": _safe_float(last.get("Upper_Band")),
        }

        # Signal determination
        macd_sig = "neutral"
        if indicators["macd"] is not None and indicators["macd_signal"] is not None:
            macd_sig = "bullish" if indicators["macd"] > indicators["macd_signal"] else "bearish"

        rsi_sig = "neutral"
        if indicators["rsi_14"] is not None:
            if indicators["rsi_14"] > 70:
                rsi_sig = "overbought"
            elif indicators["rsi_14"] < 30:
                rsi_sig = "oversold"

        bb_sig = "inside"
        if indicators["upper_band"]:
            close_price = float(last["close"])
            if close_price > indicators["upper_band"]:
                bb_sig = "above"

        signals = {
            "macd_signal": macd_sig,
            "rsi_signal": rsi_sig,
            "bb_signal": bb_sig,
        }

        score = self._score_signal(last)
        recommendation = "buy" if score >= 0.3 else ("sell" if score <= -0.3 else "hold")

        logger.info(
            "%s technical analysis complete — score=%.2f, recommendation=%s",
            symbol,
            score,
            recommendation,
        )

        return {
            "indicators": indicators,
            "signals": signals,
            "score": score,
            "recommendation": recommendation,
        }

    def recommend_by_trend(
        self,
        top_n: int = 5,
        day_range: int = 365,
    ) -> List[Tuple[str, str]]:
        """Recommend coins based on moving averages and Bollinger Bands."""
        market_info = self._get_market_info()
        end_date = pd.Timestamp.now().date()
        recommended: List[Tuple[str, str]] = []

        for symbol in market_info.values():
            try:
                ohlcv = self.exchange.get_ohlcv(
                    symbol,
                    interval="day",
                    count=day_range,
                    to=end_date.strftime("%Y-%m-%d"),
                )
                if ohlcv is None or len(ohlcv) < 90:
                    continue

                df = pd.DataFrame(
                    ohlcv, columns=["open", "high", "low", "close", "volume", "value"]
                )
                df.index.name = "timestamp"

                df["ma7"] = df["close"].rolling(window=7).mean()
                df["ma30"] = df["close"].rolling(window=30).mean()
                df["ma90"] = df["close"].rolling(window=90).mean()
                std = df["close"].rolling(window=20).std()
                df["upper_band"] = df["ma30"] + std * 2

                ma7 = df["ma7"].iloc[-1]
                ma30 = df["ma30"].iloc[-1]
                ma90 = df["ma90"].iloc[-1]

                if pd.isna(ma7) or pd.isna(ma30) or pd.isna(ma90):
                    continue

                if ma7 > ma30 > ma90:
                    close_price = df["close"].iloc[-1]
                    upper_band = df["upper_band"].iloc[-1]
                    if close_price > upper_band:
                        reason = (
                            "7-day, 30-day, and 90-day moving averages are in an uptrend, "
                            "and the current price has broken through the Bollinger Band upper band."
                        )
                        recommended.append((symbol, reason))

            except Exception as exc:  # noqa: BLE001
                logger.debug("recommend_by_trend — %s processing failed: %s", symbol, exc)
                continue

        unique_recommended = list(dict.fromkeys(recommended))[:top_n]
        logger.info("recommend_by_trend: %d recommendations completed", len(unique_recommended))
        return unique_recommended

    def recommend_by_performance(
        self,
        top_n: int = 5,
        days: int = 7,
    ) -> List[Tuple[str, str]]:
        """Recommend coins based on recent performance."""
        market_info = self._get_market_info()
        end_date = pd.Timestamp.now().date()
        performance: List[Tuple[str, float]] = []

        for symbol in market_info.values():
            try:
                ohlcv = self.exchange.get_ohlcv(
                    symbol,
                    interval="day",
                    count=days + 1,
                    to=end_date.strftime("%Y-%m-%d"),
                )
                if ohlcv is None or len(ohlcv) < days + 1:
                    continue

                start_price = float(ohlcv.iloc[0]["close"])
                end_price = float(ohlcv.iloc[-1]["close"])
                if start_price == 0:
                    continue

                returns = (end_price - start_price) / start_price * 100
                performance.append((symbol, returns))

            except Exception as exc:  # noqa: BLE001
                logger.debug("recommend_by_performance — %s processing failed: %s", symbol, exc)
                continue

        performance.sort(key=lambda x: x[1], reverse=True)
        top = performance[:top_n]

        result: List[Tuple[str, str]] = []
        for symbol, returns in top:
            reason = f"Recorded {returns:.2f}% return over the past {days} days."
            result.append((symbol, reason))

        logger.info("recommend_by_performance: %d recommendations completed", len(result))
        return result

    def _get_market_info(self) -> Dict[str, str]:
        """Get market information."""
        # Placeholder for actual implementation
        return {}