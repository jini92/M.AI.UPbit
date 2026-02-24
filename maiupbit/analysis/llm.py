# -*- coding: utf-8 -*-
"""
maiupbit.analysis.llm
~~~~~~~~~~~~~~~~~~~~~~

LLM(GPT-4o) 기반 종합 투자 분석 모듈.

시장 데이터, 기술 지표, LSTM 예측, 뉴스를 종합하여
OpenAI GPT-4o 모델로부터 매수/매도/홀드 권고를 수신합니다.

사용 예::

    analyzer = LLMAnalyzer(api_key="sk-...")
    result = analyzer.analyze(
        data_json=data_json_str,
        current_status=current_status_str,
        macd_signals=macd_signals_list,
        technical_indicators=tech_dict,
        lstm_predictions=lstm_preds,
        news_text=news_str,
    )
    print(result["recommendation"])  # 'buy' | 'sell' | 'hold'
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# 기본 분석 프롬프트 (instructions.md 내용 내장)
# ------------------------------------------------------------------
_DEFAULT_INSTRUCTIONS: str = """\
# Upbit Digital Assets Investment Automation Instruction

## Role
You serve as the Selected Coin Investment Analysis Engine, tasked with issuing hourly investment recommendations and predicting optimal buy/sell prices for the user-selected trading pair on the Upbit exchange. Your objective is to maximize returns through aggressive yet informed trading strategies while carefully managing risk.

The selected trading pair can be any coin traded against KRW (Korean Won) or BTC (Bitcoin) on the Upbit platform, such as KRW-BTC, KRW-ETH, KRW-XRP, BTC-ETH, BTC-XRP, etc. Your analysis and recommendations should be adaptable to the specific characteristics and market conditions of the chosen trading pair.

## Data Overview
### JSON Data 1: Market Analysis Data
- **Purpose**: Provides comprehensive analytics on the selected coin trading pair to facilitate market trend analysis and guide investment decisions.
- **Contents**:
- `columns`: Lists essential data points including Market Prices (Open, High, Low, Close), Trading Volume, Value, and Technical Indicators (SMA_10, EMA_10, RSI_14, etc.).
- `index`: Timestamps for data entries, labeled 'daily' or 'hourly'.
- `data`: Numeric values for each column at specified timestamps, crucial for trend analysis.

### JSON Data 2: Current Investment State
- **Purpose**: Offers a real-time overview of your investment status for the selected coin.
- **Contents**:
    - `current_time`: Current time in milliseconds since the Unix epoch.
    - `orderbook`: Current market depth details for the selected coin.
    - `balance`: The amount of the selected coin currently held.
    - `krw_balance`: The amount of Korean Won available for trading.
    - `avg_buy_price`: The average price at which the held coin was purchased.

### JSON Data 3: Technical Indicator Analysis
- **Purpose**: Provides the results of analyzing technical indicators.
- **Contents**: sma_10, ema_10, rsi_14, macd, macd_signal, macd_histogram, stoch_k, stoch_d, upper_band, middle_band, lower_band.

## Task Instructions
1. Analyze the provided historical price data (JSON Data 1) to identify key patterns, trends, and potential opportunities.
2. Evaluate the current investment state (JSON Data 2) to understand the user's holdings, available funds, and average purchase price.
3. Review the technical indicator analysis (JSON Data 3) to gauge market momentum, volatility, and potential buy/sell signals.
4. Assess market sentiment by analyzing relevant news articles.
5. Based on the comprehensive analysis, provide clear and actionable trading recommendations (buy, sell, or hold).
6. Predict the optimal buy and sell prices based on historical data, current market conditions, technical indicators, and LSTM predictions.
7. Offer guidance on position sizing and risk management.
8. Provide a concise summary of the key reasons supporting your recommendations.
9. If the analysis reveals conflicting signals, acknowledge limitations and prioritize capital preservation.
10. Continuously monitor market conditions and adapt recommendations as needed.

## Analysis Result Format
Your trading recommendations MUST be returned as a JSON object:

```json
{
  "decision": "buy/sell/hold",
  "buy_price": <predicted optimal buy price or null>,
  "sell_price": <predicted optimal sell price or null>,
  "reason": "A concise summary of the key reasons and insights supporting your recommendation",
  "technical_analysis": {
    "key_indicators": "Most relevant technical indicators and their implications",
    "chart_patterns": "Notable chart patterns and their potential significance"
  },
  "market_sentiment": "An assessment of current market sentiment",
  "risk_management": {
    "position_sizing": "Recommended position size",
    "stop_loss": "Suggested stop-loss level",
    "take_profit": "Recommended take-profit target"
  }
}
```
"""


class LLMAnalyzer:
    """LLM(GPT-4o) 기반 종합 투자 분석기.

    시장 데이터, 기술 지표, LSTM 예측, 뉴스를 종합하여
    OpenAI Chat Completions API 로 매수/매도/홀드 투자 권고를 생성합니다.

    Attributes:
        client (OpenAI): OpenAI 클라이언트 인스턴스.
        model (str): 사용할 OpenAI 모델 식별자.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
    ) -> None:
        """LLMAnalyzer 초기화.

        Args:
            api_key: OpenAI API 키.
                None 이면 ``OPENAI_API_KEY`` 환경 변수를 사용합니다.
            model: 사용할 OpenAI 모델. 기본값 ``"gpt-4o"``.
        """
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _get_default_instructions(self) -> str:
        """기본 분석 프롬프트를 반환.

        Returns:
            ``instructions.md`` 내용을 내장한 기본 시스템 프롬프트 문자열.
        """
        return _DEFAULT_INSTRUCTIONS

    def _parse_response(self, raw: str) -> dict:
        """GPT 응답 JSON 을 파싱하여 표준 결과 딕셔너리로 변환.

        Args:
            raw: GPT 응답의 content 문자열 (JSON 형식).

        Returns:
            표준화된 분석 결과 딕셔너리.
            파싱 실패 시 'recommendation': 'hold' 인 기본값 반환.
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("GPT 응답 JSON 파싱 실패: %s\n원본: %s", exc, raw[:500])
            return self._default_result()

        result = {
            "recommendation": data.get("decision", "hold"),
            "buy_price": data.get("buy_price"),
            "sell_price": data.get("sell_price"),
            "reason": data.get("reason", ""),
            "technical_analysis": {
                "key_indicators": data.get("technical_analysis", {}).get(
                    "key_indicators", ""
                ),
                "chart_patterns": data.get("technical_analysis", {}).get(
                    "chart_patterns", ""
                ),
            },
            "market_sentiment": data.get("market_sentiment", ""),
            "risk_management": {
                "position_sizing": data.get("risk_management", {}).get(
                    "position_sizing", ""
                ),
                "stop_loss": data.get("risk_management", {}).get("stop_loss", ""),
                "take_profit": data.get("risk_management", {}).get("take_profit", ""),
            },
        }
        return result

    def _default_result(self) -> dict:
        """파싱 실패 등 오류 상황에서 반환할 기본 결과.

        Returns:
            recommendation='hold' 인 기본 결과 딕셔너리.
        """
        return {
            "recommendation": "hold",
            "buy_price": None,
            "sell_price": None,
            "reason": "분석 결과를 가져오는 데 실패했습니다. 잠시 후 재시도하세요.",
            "technical_analysis": {"key_indicators": "", "chart_patterns": ""},
            "market_sentiment": "",
            "risk_management": {
                "position_sizing": "",
                "stop_loss": "",
                "take_profit": "",
            },
        }

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------

    def analyze(
        self,
        data_json: str,
        current_status: str,
        macd_signals: list,
        technical_indicators: dict,
        lstm_predictions: list,
        news_text: str = "",
        instructions: Optional[str] = None,
    ) -> dict:
        """GPT-4o 로 종합 투자 분석 수행.

        Args:
            data_json: 일봉·시간봉 OHLCV + 기술 지표를 담은 JSON 문자열
                (JSON Data 1).
            current_status: 현재 투자 상태 JSON 문자열
                (잔고, 오더북, 평균 매수가 등, JSON Data 2).
            macd_signals: MACD 매수/매도 신호 리스트.
            technical_indicators: 최신 기술 지표 딕셔너리 (JSON Data 3).
            lstm_predictions: LSTM 예측 가격 리스트.
            news_text: 관련 뉴스 텍스트. 기본값 빈 문자열.
            instructions: 시스템 프롬프트. None 이면 기본 프롬프트 사용.

        Returns:
            분석 결과 딕셔너리::

                {
                    'recommendation': str,           # 'buy' | 'sell' | 'hold'
                    'buy_price': float | None,        # 권장 매수 가격
                    'sell_price': float | None,       # 권장 매도 가격
                    'reason': str,                    # 결정 근거
                    'technical_analysis': {
                        'key_indicators': str,
                        'chart_patterns': str,
                    },
                    'market_sentiment': str,
                    'risk_management': {
                        'position_sizing': str,
                        'stop_loss': str,
                        'take_profit': str,
                    },
                }

            API 호출 실패 또는 JSON 파싱 오류 시 기본값('hold') 반환.

        Raises:
            Exception: OpenAI API 호출 중 예기치 않은 오류 발생 시.
        """
        system_prompt = instructions if instructions else self._get_default_instructions()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": data_json},
            {"role": "user", "content": current_status},
            {"role": "user", "content": f"MACD Signals: {macd_signals}"},
            {"role": "user", "content": f"Technical Indicators: {technical_indicators}"},
            {"role": "user", "content": f"LSTM Predictions: {lstm_predictions}"},
            {"role": "user", "content": f"News Articles:\n{news_text}"},
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                top_p=0.2,
                seed=1234,
                response_format={"type": "json_object"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("OpenAI API 호출 실패: %s", exc)
            return self._default_result()

        raw_content: str = response.choices[0].message.content or ""
        result = self._parse_response(raw_content)

        logger.info(
            "LLMAnalyzer.analyze 완료 — recommendation=%s",
            result.get("recommendation"),
        )
        return result
