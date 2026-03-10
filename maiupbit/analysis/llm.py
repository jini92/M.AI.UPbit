# -*- coding: utf-8 -*-
"""
maiupbit.analysis.llm
~~~~~~~~~~~~~~~~~~~~~~

LLM-based comprehensive investment analysis module (OpenAI GPT-4o / Ollama support).

Combines market data, technical indicators, LSTM predictions, and news to receive buy/sell/hold recommendations via an OpenAI-compatible Chat Completions API.
Ollama provides an OpenAI-compatible API at ``http://localhost:11434/v1``, so both providers are supported using the same ``openai`` package.

Usage example (OpenAI)::

    analyzer = LLMAnalyzer(api_key="sk-...")
    result = analyzer.analyze(...)

Usage example (Ollama)::

    analyzer = LLMAnalyzer(provider="ollama")
    result = analyzer.analyze(...)

Environment variables::

    LLM_PROVIDER      - "openai" (default) or "ollama"
    OLLAMA_BASE_URL   - Ollama API URL (default: http://localhost:11434/v1)
    OLLAMA_MODEL      - Ollama model name (default: qwen2.5:14b)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Literal, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Default analysis prompt (v2 ??Ollama/OpenAI optimized common version)
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
- The "reason" field MUST be written in English (2-3 sentences).
- buy_price/sell_price should be realistic numbers based on the data, or null.

## JSON Schema
{"decision":"buy|sell|hold","confidence":0.0,"buy_price":number|null,"sell_price":number|null,"reason":"Key reasons in Korean (2-3 sentences)","technical_analysis":{"key_indicators":"Summary of key indicators","trend":"uptrend|downtrend|sideways"},"market_sentiment":"positive|negative|neutral|unknown","risk_management":{"position_sizing":"Investment weight suggestion (e.g., 5% of capital)","stop_loss":"Stop loss price","take_profit":"Take profit price"}}
- 0.9+: Very strong signal (multiple confirming indicators, clear trend)
- 0.7-0.89: Strong signal (most indicators agree)
- 0.6-0.69: Moderate signal (some conflict, but directional bias clear)
- 0.5-0.59: Weak signal (mixed indicators, lean toward hold)
- 0.4-0.49: No clear signal, recommend hold
"""

_DEFAULT_INSTRUCTIONS = _DEFAULT_INSTRUCTIONS.replace("Key reasons in Korean (2-3 sentences)", "Key reasons in English (2-3 sentences)")
_DEFAULT_INSTRUCTIONS = _DEFAULT_INSTRUCTIONS.replace("Summary of key indicators", "Summary of key indicators")
_DEFAULT_INSTRUCTIONS = _DEFAULT_INSTRUCTIONS.replace("Investment weight suggestion (e.g., 5% of capital)", "Investment weight suggestion (e.g., 5% of capital)")
_DEFAULT_INSTRUCTIONS = _DEFAULT_INSTRUCTIONS.replace("Stop loss price", "Stop loss price")
_DEFAULT_INSTRUCTIONS = _DEFAULT_INSTRUCTIONS.replace("Take profit price", "Take profit price")

_DEFAULT_INSTRUCTIONS = _DEFAULT_INSTRUCTIONS.encode('ascii', 'ignore').decode('ascii')

class LLMAnalyzer:
    def __init__(self, api_key=None, provider=None):
        import os
        from openai import OpenAI

        self.provider = provider or os.getenv("LLM_PROVIDER", "openai")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.timeout = 60

        if self.provider == "ollama":
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
            self.model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
            self.num_gpu = int(os.getenv("OLLAMA_GPU_LAYERS", "99"))
            self.client = OpenAI(api_key="ollama", base_url=base_url)
        else:
            self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            self.client = OpenAI(api_key=self.api_key)

    def _get_default_instructions(self):
        return _DEFAULT_INSTRUCTIONS
    
    def _parse_response(self, raw_content: str) -> dict:
        result = {
            "recommendation": "hold",
            "buy_price": None,
            "sell_price": None,
            "reason": "",
            "technical_analysis": {"key_indicators": "", "trend": ""},
            "market_sentiment": "",
            "risk_management": {
                "position_sizing": "",
                "stop_loss": "",
                "take_profit": "",
            },
        }
        
        try:
            response_data = json.loads(raw_content)
            
            result["recommendation"] = response_data.get("decision", "hold")
            result["confidence"] = float(response_data.get("confidence", 0.5))
            result["buy_price"] = response_data.get("buy_price")
            result["sell_price"] = response_data.get("sell_price")
            result["reason"] = response_data.get("reason", "")
            result["technical_analysis"]["key_indicators"] = response_data.get("technical_analysis").get("key_indicators", "")
            result["technical_analysis"]["trend"] = response_data.get("technical_analysis").get("trend", "")
            result["market_sentiment"] = response_data.get("market_sentiment", "")
            result["risk_management"]["position_sizing"] = response_data.get("risk_management").get("position_sizing", "")
            result["risk_management"]["stop_loss"] = response_data.get("risk_management").get("stop_loss", "")
            result["risk_management"]["take_profit"] = response_data.get("risk_management").get("take_profit", "")
            
        except Exception as exc:
            logger.error(f"Failed to parse JSON response: {exc}")
        
        return result
    
    def _default_result(self) -> dict:
        return {
            "recommendation": "hold",
            "buy_price": None,
            "sell_price": None,
            "reason": "Failed to retrieve analysis results. Please try again later.",
            "technical_analysis": {"key_indicators": "", "trend": ""},
            "market_sentiment": "",
            "risk_management": {
                "position_sizing": "",
                "stop_loss": "",
                "take_profit": "",
            },
        }
    
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
        
        system_prompt = instructions if instructions else self._get_default_instructions()

        parts = [
            "## Market Data (OHLCV + Indicators)",
            data_json,
            "",
            "## Current Investment Status",
            current_status,
            "",
            f"## Latest Technical Indicator Values\n{json.dumps(technical_indicators, ensure_ascii=False)}",
            "",
            f"## MACD Signals\n{macd_signals}",
            "",
            f"## ML Predictions (LSTM/Transformer)\n{lstm_predictions}",
        ]

        if news_text:
            parts.append(f"\n## News\n{news_text}")

        if knowledge_context:
            parts.append(f"\n## Reference Knowledge\n{knowledge_context}")

        parts.append("\nPlease analyze the above data and respond in JSON format.")

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
            
            kwargs["response_format"] = {"type": "json_object"}
            # Ollama: pass num_gpu option to limit GPU layers (avoids CUDA memory fragmentation)
            if self.provider == "ollama":
                kwargs["extra_body"] = {"options": {"num_gpu": getattr(self, "num_gpu", 99)}}
            response = self.client.chat.completions.create(**kwargs, timeout=self.timeout)
        except Exception as exc: 
            logger.error(f"LLM API call failed (provider={self.provider}): {exc}")
            return self._default_result()

        raw_content: str = response.choices[0].message.content or ""
        result = self._parse_response(raw_content)

        logger.info(
            "LLMAnalyzer.analyze completed ??provider=%s, model=%s, recommendation=%s",
            self.provider,
            self.model,
            result.get("recommendation"),
        )
        
        return result
