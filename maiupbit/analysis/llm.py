# -*- coding: utf-8 -*-
"""
maiupbit.analysis.llm
~~~~~~~~~~~~~~~~~~~~~~

LLM 기반 종합 투자 분석 모듈 (OpenAI GPT-4o / Ollama 지원).

시장 데이터, 기술 지표, LSTM 예측, 뉴스를 종합하여
OpenAI-호환 Chat Completions API 로 매수/매도/홀드 권고를 수신합니다.
Ollama 는 ``http://localhost:11434/v1`` 에서 OpenAI-호환 API 를 제공하므로
동일한 ``openai`` 패키지로 두 프로바이더를 모두 지원합니다.

사용 예 (OpenAI)::

    analyzer = LLMAnalyzer(api_key="sk-...")
    result = analyzer.analyze(...)

사용 예 (Ollama)::

    analyzer = LLMAnalyzer(provider="ollama")
    result = analyzer.analyze(...)

환경 변수::

    LLM_PROVIDER      - "openai" (기본) 또는 "ollama"
    OLLAMA_BASE_URL   - Ollama API URL (기본: http://localhost:11434/v1)
    OLLAMA_MODEL      - Ollama 모델 이름 (기본: qwen2.5:14b)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Literal, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# 기본 분석 프롬프트 (v2 — Ollama/OpenAI 공통 최적화)
# ------------------------------------------------------------------
_DEFAULT_INSTRUCTIONS: str = """\
You are an expert cryptocurrency investment analyst for the UPbit exchange (Korea).
You analyze market data, technical indicators, ML predictions, and news to produce a single JSON trading recommendation.

## Analysis Steps
1. Read the OHLCV price data and identify the current trend (uptrend/downtrend/sideways).
2. Evaluate technical indicators:
   - RSI: <30 oversold (buy signal), >70 overbought (sell signal)
   - MACD: golden cross = bullish, dead cross = bearish
   - Bollinger Bands: price near lower band = buy opportunity, near upper band = caution
   - Stochastic: <20 oversold, >80 overbought
   - ATR: measures volatility level for position sizing
   - Momentum Score: weighted multi-period momentum (positive = uptrend)
3. Check ML model predictions (LSTM/Transformer) for price direction.
4. Assess news sentiment (positive/negative/neutral).
5. If signals conflict, prioritize capital preservation and recommend "hold".

## Output Rules
- Return ONLY a valid JSON object. No markdown, no explanation outside JSON.
- The "reason" field MUST be written in Korean (한국어).
- buy_price/sell_price should be realistic numbers based on the data, or null.

## JSON Schema
{"decision":"buy|sell|hold","buy_price":number|null,"sell_price":number|null,"reason":"한국어로 핵심 근거 2-3문장","technical_analysis":{"key_indicators":"주요 지표 요약","trend":"uptrend|downtrend|sideways"},"market_sentiment":"positive|negative|neutral|unknown","risk_management":{"position_sizing":"투자 비중 제안 (예: 자본의 5%)","stop_loss":"손절 가격 또는 비율","take_profit":"익절 가격 또는 비율"}}
"""


_DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
_DEFAULT_OLLAMA_MODEL = "qwen2.5:14b"


class LLMAnalyzer:
    """LLM 기반 종합 투자 분석기 (OpenAI / Ollama 지원).

    시장 데이터, 기술 지표, LSTM 예측, 뉴스를 종합하여
    OpenAI-호환 Chat Completions API 로 매수/매도/홀드 투자 권고를 생성합니다.

    Attributes:
        provider: ``"openai"`` 또는 ``"ollama"``.
        client: OpenAI-호환 클라이언트 인스턴스.
        model: 사용할 모델 식별자.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[Literal["openai", "ollama"]] = None,
        base_url: Optional[str] = None,
    ) -> None:
        """LLMAnalyzer 초기화.

        Args:
            api_key: API 키. ``None`` 이면 프로바이더에 따라 자동 결정:
                - openai: ``OPENAI_API_KEY`` 환경 변수
                - ollama: ``"ollama"`` (필수이나 실제 사용되지 않음)
            model: 모델 식별자. ``None`` 이면 프로바이더에 따라 자동 결정:
                - openai: ``"gpt-4o"``
                - ollama: ``OLLAMA_MODEL`` 환경 변수 또는 ``"qwen2.5:14b"``
            provider: ``"openai"`` (기본) 또는 ``"ollama"``.
                ``None`` 이면 ``LLM_PROVIDER`` 환경 변수 또는 ``"openai"``.
            base_url: OpenAI-호환 API base URL.
                ``None`` 이면 프로바이더에 따라 자동 결정:
                - openai: OpenAI 기본값 (설정하지 않음)
                - ollama: ``OLLAMA_BASE_URL`` 환경 변수 또는 ``"http://localhost:11434/v1"``
        """
        self.provider: str = provider or os.getenv("LLM_PROVIDER", "openai")

        self.timeout: float = float(os.getenv("LLM_TIMEOUT", "60"))

        if self.provider == "ollama":
            resolved_base_url = base_url or os.getenv("OLLAMA_BASE_URL", _DEFAULT_OLLAMA_BASE_URL)
            resolved_api_key = api_key or "ollama"
            self.model = model or os.getenv("OLLAMA_MODEL", _DEFAULT_OLLAMA_MODEL)
            self.client = OpenAI(
                api_key=resolved_api_key,
                base_url=resolved_base_url,
                timeout=self.timeout,
            )
        else:
            resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
            self.model = model or "gpt-4o"
            kwargs: dict = {"api_key": resolved_api_key, "timeout": self.timeout}
            if base_url:
                kwargs["base_url"] = base_url
            self.client = OpenAI(**kwargs)

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
        """LLM 응답 JSON 을 파싱하여 표준 결과 딕셔너리로 변환.

        마크다운 코드 블록(````json ... ````)으로 감싸진 JSON 도 처리합니다.
        (Ollama 모델이 흔히 이 형식으로 응답)

        Args:
            raw: LLM 응답의 content 문자열 (JSON 형식).

        Returns:
            표준화된 분석 결과 딕셔너리.
            파싱 실패 시 'recommendation': 'hold' 인 기본값 반환.
        """
        text = raw.strip()

        # Strip markdown code blocks if present (common with Ollama models)
        if text.startswith("```"):
            first_newline = text.index("\n")
            text = text[first_newline + 1:]
            if text.endswith("```"):
                text = text[:-3].strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("LLM 응답 JSON 파싱 실패: %s\n원본: %s", exc, raw[:500])
            return self._default_result()

        ta = data.get("technical_analysis", {})
        rm = data.get("risk_management", {})
        result = {
            "recommendation": data.get("decision", "hold"),
            "buy_price": data.get("buy_price"),
            "sell_price": data.get("sell_price"),
            "reason": data.get("reason", ""),
            "technical_analysis": {
                "key_indicators": ta.get("key_indicators", ""),
                "trend": ta.get("trend", ta.get("chart_patterns", "")),
            },
            "market_sentiment": data.get("market_sentiment", ""),
            "risk_management": {
                "position_sizing": rm.get("position_sizing", ""),
                "stop_loss": rm.get("stop_loss", ""),
                "take_profit": rm.get("take_profit", ""),
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
            "technical_analysis": {"key_indicators": "", "trend": ""},
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
        knowledge_context: str = "",
    ) -> dict:
        """LLM 으로 종합 투자 분석 수행 (OpenAI 또는 Ollama).

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
            knowledge_context: Mnemo 지식그래프 컨텍스트. 기본값 빈 문자열.
                KnowledgeProvider.enrich_llm_context()로 생성.

        Returns:
            분석 결과 딕셔너리::

                {
                    'recommendation': str,           # 'buy' | 'sell' | 'hold'
                    'buy_price': float | None,        # 권장 매수 가격
                    'sell_price': float | None,       # 권장 매도 가격
                    'reason': str,                    # 결정 근거 (한국어)
                    'technical_analysis': {
                        'key_indicators': str,
                        'trend': str,                # 'uptrend' | 'downtrend' | 'sideways'
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

        # 단일 구조화 메시지로 통합 (Ollama 14B 최적화: 분산 메시지 대비 정확도 향상)
        parts = [
            "## 시장 데이터 (OHLCV + 지표)",
            data_json,
            "",
            "## 현재 투자 상태",
            current_status,
            "",
            f"## 기술 지표 최신값\n{json.dumps(technical_indicators, ensure_ascii=False)}",
            "",
            f"## MACD 시그널\n{macd_signals}",
            "",
            f"## ML 예측 (LSTM/Transformer)\n{lstm_predictions}",
        ]

        if news_text:
            parts.append(f"\n## 뉴스\n{news_text}")

        if knowledge_context:
            parts.append(f"\n## 참고 지식\n{knowledge_context}")

        parts.append("\n위 데이터를 종합 분석하여 JSON으로 응답하세요.")

        user_content = "\n".join(parts)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        try:
            kwargs: dict = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.2,
                "top_p": 0.2,
                "seed": 1234,
            }
            # OpenAI 와 Ollama 모두 response_format 을 지원.
            # Ollama 는 format 파라미터를 통해 네이티브 JSON 출력을 제공하며,
            # OpenAI-호환 API 에서도 response_format 이 정상 동작함.
            # 마크다운 코드 블록 폴백은 _parse_response() 에서 안전망으로 유지.
            kwargs["response_format"] = {"type": "json_object"}
            response = self.client.chat.completions.create(**kwargs, timeout=self.timeout)
        except Exception as exc:  # noqa: BLE001
            logger.error("LLM API 호출 실패 (provider=%s): %s", self.provider, exc)
            return self._default_result()

        raw_content: str = response.choices[0].message.content or ""
        result = self._parse_response(raw_content)

        logger.info(
            "LLMAnalyzer.analyze 완료 — provider=%s, model=%s, recommendation=%s",
            self.provider,
            self.model,
            result.get("recommendation"),
        )
        return result
