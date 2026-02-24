# -*- coding: utf-8 -*-
"""
maiupbit.analysis.technical
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

기술적 분석 엔진.

이동평균선, 볼린저밴드, RSI, MACD, 스토캐스틱 지표를 계산하고
코인 추천 알고리즘(추세 기반 / 수익률 기반)을 제공합니다.

사용 예::

    analyzer = TechnicalAnalyzer(exchange=pyupbit)
    result = analyzer.analyze("KRW-BTC", df)
    trend_picks = analyzer.recommend_by_trend(top_n=5)
    perf_picks  = analyzer.recommend_by_performance(top_n=5, days=7)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    """기술적 분석 엔진.

    Attributes:
        exchange: pyupbit 모듈 또는 동일 인터페이스를 가진 거래소 객체.
            ``get_ohlcv``, ``get_current_price`` 메서드를 사용합니다.
    """

    def __init__(self, exchange: Any) -> None:
        """TechnicalAnalyzer 초기화.

        Args:
            exchange: pyupbit 또는 동일 인터페이스 거래소 모듈/객체.
        """
        self.exchange = exchange

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _get_market_info(self) -> dict[str, str]:
        """Upbit 전체 마켓 정보를 ``{한국어명: 심볼}`` 딕셔너리로 반환.

        Returns:
            마켓 딕셔너리. 예: ``{'비트코인': 'KRW-BTC', ...}``
        """
        import requests  # 런타임 의존성 — 불필요한 최상단 임포트 방지

        url = "https://api.upbit.com/v1/market/all"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            markets = resp.json()
            return {
                m["korean_name"]: m["market"]
                for m in markets
                if "BTC-" in m["market"] or "KRW-" in m["market"]
            }
        except Exception as exc:  # noqa: BLE001
            logger.error("마켓 정보 조회 실패: %s", exc)
            return {}

    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """DataFrame 에 이동평균선, 볼린저밴드, RSI, MACD, 스토캐스틱 지표 추가.

        Args:
            df: 'open', 'high', 'low', 'close', 'volume' 컬럼을 가진 OHLCV DataFrame.

        Returns:
            지표가 추가된 DataFrame (원본 수정 없이 사본 반환).
        """
        df = df.copy()

        # 이동평균선
        df["SMA_10"] = df["close"].rolling(window=10).mean()
        df["EMA_10"] = df["close"].ewm(span=10, adjust=False).mean()

        # RSI
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df["RSI_14"] = 100 - (100 / (1 + rs))

        # MACD
        ema_fast = df["close"].ewm(span=12, adjust=False).mean()
        ema_slow = df["close"].ewm(span=26, adjust=False).mean()
        df["MACD"] = ema_fast - ema_slow
        df["Signal_Line"] = df["MACD"].ewm(span=9, adjust=False).mean()
        df["MACD_Histogram"] = df["MACD"] - df["Signal_Line"]

        # 볼린저밴드
        df["Middle_Band"] = df["close"].rolling(window=20).mean()
        std_dev = df["close"].rolling(window=20).std()
        df["Upper_Band"] = df["Middle_Band"] + std_dev * 2
        df["Lower_Band"] = df["Middle_Band"] - std_dev * 2

        # 스토캐스틱
        low_14 = df["low"].rolling(window=14).min()
        high_14 = df["high"].rolling(window=14).max()
        df["STOCHk_14_3_3"] = (
            (df["close"] - low_14) / (high_14 - low_14).replace(0, np.nan) * 100
        )
        df["STOCHd_14_3_3"] = df["STOCHk_14_3_3"].rolling(window=3).mean()

        return df

    def _score_signal(self, row: pd.Series) -> float:
        """단일 행(row)의 기술 지표를 바탕으로 매수 신호 점수 계산.

        Args:
            row: 지표가 포함된 DataFrame 의 마지막 행.

        Returns:
            -1.0 ~ 1.0 범위의 종합 점수.
                양수: 매수 신호, 음수: 매도 신호.
        """
        score = 0.0
        count = 0

        # RSI
        if pd.notna(row.get("RSI_14")):
            rsi = row["RSI_14"]
            if rsi < 30:
                score += 1.0   # 과매도 → 매수
            elif rsi > 70:
                score -= 1.0   # 과매수 → 매도
            count += 1

        # MACD vs Signal
        if pd.notna(row.get("MACD")) and pd.notna(row.get("Signal_Line")):
            score += 1.0 if row["MACD"] > row["Signal_Line"] else -1.0
            count += 1

        # 볼린저밴드
        if pd.notna(row.get("Upper_Band")) and pd.notna(row.get("Lower_Band")):
            if row["close"] < row["Lower_Band"]:
                score += 1.0
            elif row["close"] > row["Upper_Band"]:
                score -= 1.0
            count += 1

        # 스토캐스틱
        if pd.notna(row.get("STOCHk_14_3_3")):
            stoch_k = row["STOCHk_14_3_3"]
            if stoch_k < 20:
                score += 1.0
            elif stoch_k > 80:
                score -= 1.0
            count += 1

        return score / count if count > 0 else 0.0

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------

    def analyze(self, symbol: str, df: pd.DataFrame) -> dict:
        """단일 코인에 대한 종합 기술 분석 수행.

        Args:
            symbol: 거래 심볼. 예: ``"KRW-BTC"``.
            df: 'close', 'high', 'low' 컬럼을 포함한 OHLCV DataFrame.

        Returns:
            분석 결과 딕셔너리::

                {
                    'indicators': {
                        'sma_10': float,
                        'ema_10': float,
                        'rsi_14': float,
                        'macd': float,
                        'macd_signal': float,
                        'macd_histogram': float,
                        'stoch_k': float,
                        'stoch_d': float,
                        'upper_band': float,
                        'middle_band': float,
                        'lower_band': float,
                    },
                    'signals': {
                        'macd_signal': 'bullish' | 'bearish' | 'neutral',
                        'rsi_signal': 'overbought' | 'oversold' | 'neutral',
                        'bb_signal': 'upper' | 'lower' | 'inside',
                    },
                    'score': float,          # -1.0 ~ 1.0
                    'recommendation': str,   # 'buy' | 'sell' | 'hold'
                }
        """
        df = self._add_indicators(df)
        last = df.iloc[-1]

        indicators = {
            "sma_10": _safe_float(last.get("SMA_10")),
            "ema_10": _safe_float(last.get("EMA_10")),
            "rsi_14": _safe_float(last.get("RSI_14")),
            "macd": _safe_float(last.get("MACD")),
            "macd_signal": _safe_float(last.get("Signal_Line")),
            "macd_histogram": _safe_float(last.get("MACD_Histogram")),
            "stoch_k": _safe_float(last.get("STOCHk_14_3_3")),
            "stoch_d": _safe_float(last.get("STOCHd_14_3_3")),
            "upper_band": _safe_float(last.get("Upper_Band")),
            "middle_band": _safe_float(last.get("Middle_Band")),
            "lower_band": _safe_float(last.get("Lower_Band")),
        }

        # 신호 판정
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
        if indicators["upper_band"] and indicators["lower_band"]:
            close = float(last["close"])
            if close > indicators["upper_band"]:
                bb_sig = "upper"
            elif close < indicators["lower_band"]:
                bb_sig = "lower"

        signals = {
            "macd_signal": macd_sig,
            "rsi_signal": rsi_sig,
            "bb_signal": bb_sig,
        }

        score = self._score_signal(last)
        recommendation = "buy" if score >= 0.3 else ("sell" if score <= -0.3 else "hold")

        logger.info(
            "%s 기술 분석 완료 — score=%.2f, recommendation=%s",
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
    ) -> list[tuple[str, str]]:
        """이동평균선 배열 + 볼린저밴드 기반 상승 추세 코인 추천.

        7일·30일·90일 이동평균선이 정배열(ma7 > ma30 > ma90)을 이루면서
        현재 가격이 볼린저밴드 상한선을 돌파한 코인을 추천합니다.

        Args:
            top_n: 반환할 추천 코인 수. 기본값 5.
            day_range: 조회할 과거 일수. 기본값 365.

        Returns:
            ``[(심볼, 추천 이유), ...]`` 형식의 리스트.
        """
        market_info = self._get_market_info()
        end_date = datetime.now().date()
        recommended: list[tuple[str, str]] = []

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
                df["upper"] = df["ma30"] + std * 2

                ma7 = df["ma7"].iloc[-1]
                ma30 = df["ma30"].iloc[-1]
                ma90 = df["ma90"].iloc[-1]

                if pd.isna(ma7) or pd.isna(ma30) or pd.isna(ma90):
                    continue

                if ma7 > ma30 > ma90:
                    close_price = df["close"].iloc[-1]
                    upper_band = df["upper"].iloc[-1]
                    if close_price > upper_band:
                        reason = (
                            "7일, 30일, 90일 이동평균선이 상승 배열을 이루고 있으며, "
                            "현재 가격이 볼린저밴드 상한선을 돌파했습니다."
                        )
                        recommended.append((symbol, reason))

            except Exception as exc:  # noqa: BLE001
                logger.debug("recommend_by_trend — %s 처리 실패: %s", symbol, exc)
                continue

        # 중복 제거 후 top_n 반환
        unique_recommended = list(dict.fromkeys(recommended))[:top_n]
        logger.info("recommend_by_trend: %d개 추천 완료", len(unique_recommended))
        return unique_recommended

    def recommend_by_performance(
        self,
        top_n: int = 5,
        days: int = 7,
    ) -> list[tuple[str, str]]:
        """최근 수익률 기반 코인 추천.

        최근 ``days`` 일 동안의 수익률을 기준으로 상위 코인을 추천합니다.

        Args:
            top_n: 반환할 추천 코인 수. 기본값 5.
            days: 수익률 계산 기간(일). 기본값 7.

        Returns:
            ``[(심볼, 추천 이유), ...]`` 형식의 리스트 (수익률 높은 순).
        """
        market_info = self._get_market_info()
        end_date = datetime.now().date()
        performance: list[tuple[str, float]] = []

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
                logger.debug("recommend_by_performance — %s 처리 실패: %s", symbol, exc)
                continue

        # 수익률 내림차순 정렬 후 top_n
        performance.sort(key=lambda x: x[1], reverse=True)
        top = performance[:top_n]

        result: list[tuple[str, str]] = []
        for symbol, returns in top:
            reason = f"최근 {days}일 간 {returns:.2f}%의 수익률을 기록하였습니다."
            result.append((symbol, reason))

        logger.info("recommend_by_performance: %d개 추천 완료", len(result))
        return result


# ------------------------------------------------------------------
# 모듈 내부 유틸리티
# ------------------------------------------------------------------

def _safe_float(value: Any) -> Optional[float]:
    """NaN·None 을 None 으로 변환하는 유틸리티.

    Args:
        value: 변환할 값.

    Returns:
        float 또는 None.
    """
    try:
        f = float(value)
        return None if (f != f) else f  # NaN 검사 (f != f → True when NaN)
    except (TypeError, ValueError):
        return None
