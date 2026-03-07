# -*- coding: utf-8 -*-
"""maiupbit.trading.auto_trader - Automated Trading System"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from maiupbit.exchange.upbit import UPbitExchange
from maiupbit.trading.journal import TradeJournal

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))

DEFAULT_CONFIG = {
    "min_confidence": float(os.getenv("MIN_CONFIDENCE", "0.6")),
    "max_position_ratio": float(os.getenv("MAX_POSITION_RATIO", "0.3")),
    "min_order_krw": float(os.getenv("MIN_ORDER_KRW", "5000")),
    "fee_rate": float(os.getenv("FEE_RATE", "0.0005")),
}


class AutoTrader:
    def __init__(
        self,
        exchange=None,
        journal=None,
        llm_analyzer=None,
        knowledge_provider=None,
        config=None,
    ):
        self.exchange = exchange or UPbitExchange(
            access_key=os.getenv("UPBIT_ACCESS_KEY", ""),
            secret_key=os.getenv("UPBIT_SECRET_KEY", ""),
        )
        self.journal = journal or TradeJournal()
        self.llm = llm_analyzer
        self.knowledge = knowledge_provider
        self.config = {**DEFAULT_CONFIG, **(config or {})}

    def run(self, symbol: str, dry_run: bool = False) -> dict:
        return self.execute_trade(symbol, dry_run=dry_run)

    def execute_trade(self, symbol: str, dry_run: bool = False) -> dict:
        market_data = self._collect_market_data(symbol)
        quant_signals = self._analyze_quantitative_signals(symbol)
        knowledge_context = self._gather_knowledge_from_mnemo(symbol)
        llm_result = self._make_llm_decision(market_data, quant_signals, knowledge_context)
        decision = self._make_trade_decision(symbol, market_data, quant_signals, llm_result)
        return self._execute_and_log_trade(
            symbol, decision, market_data, quant_signals, llm_result, knowledge_context, dry_run
        )

    def _collect_market_data(self, symbol: str) -> dict:
        try:
            current_price = self.exchange.get_current_price(symbol)
        except Exception as exc:
            logger.warning("Failed to fetch price for %s: %s", symbol, exc)
            current_price = 0

        indicators, signals = {}, {}
        try:
            import pyupbit
            from maiupbit.indicators.trend import sma, ema
            from maiupbit.indicators.momentum import rsi
            from maiupbit.indicators.volatility import bollinger_bands
            df = pyupbit.get_ohlcv(symbol, count=200)
            if df is not None and not df.empty:
                close = df["close"]
                df["sma_20"] = sma(close, 20)
                df["ema_12"] = ema(close, 12)
                df["rsi_14"] = rsi(close, 14)
                upper, middle, lower = bollinger_bands(close)
                df["bb_upper"] = upper
                df["bb_middle"] = middle
                df["bb_lower"] = lower
                last = df.iloc[-1]
                indicators = {k: (float(v) if v == v else None) for k, v in last.items()}
                rsi_val = indicators.get("rsi_14")
                signals["rsi_signal"] = (
                    "oversold" if rsi_val and rsi_val < 30 else
                    "overbought" if rsi_val and rsi_val > 70 else "neutral"
                )
                close_price = indicators.get("close", 0)
                sma20 = indicators.get("sma_20", 0)
                signals["macd_signal"] = (
                    "bullish" if close_price and sma20 and close_price > sma20 else
                    "bearish" if close_price and sma20 and close_price < sma20 else "neutral"
                )
        except Exception as exc:
            logger.warning("Technical indicator calculation failed: %s", exc)

        return {"current_price": current_price, "indicators": indicators, "signals": signals}

    def _analyze_quantitative_signals(self, symbol: str) -> dict:
        quant = {}
        try:
            from maiupbit.strategies.momentum import DualMomentumStrategy
            quant["momentum"] = DualMomentumStrategy().analyze(symbol)
        except Exception as exc:
            logger.debug("Quant signal failed: %s", exc)
        return quant

    def _gather_knowledge_from_mnemo(self, symbol: str) -> str:
        if not self.knowledge:
            return ""
        try:
            coin = symbol.replace("KRW-", "")
            return self.knowledge.search_for_coin(coin) or ""
        except Exception as exc:
            logger.debug("Mnemo fetch failed: %s", exc)
            return ""

    def _make_llm_decision(self, market_data, quant_signals, knowledge_context) -> dict:
        fallback = {"decision": "hold", "confidence": 0.5, "reason": "LLM unavailable."}
        if not self.llm:
            return fallback
        try:
            result = self.llm.analyze(
                data_json=json.dumps({
                    "price": market_data["current_price"],
                    "indicators": {k: v for k, v in market_data["indicators"].items() if v is not None},
                    "quant_signals": {k: str(v)[:200] for k, v in quant_signals.items()},
                }, ensure_ascii=False),
                current_status=json.dumps({
                    "price": market_data["current_price"],
                    "rsi_signal": market_data["signals"].get("rsi_signal"),
                    "macd_signal": market_data["signals"].get("macd_signal"),
                }, ensure_ascii=False),
                macd_signals=[market_data["signals"].get("macd_signal", "neutral")],
                technical_indicators={k: v for k, v in market_data["indicators"].items() if v is not None},
                lstm_predictions=[],
                news_text="",
                knowledge_context=knowledge_context,
            )
            return result if isinstance(result, dict) else fallback
        except Exception as exc:
            logger.error("LLM decision error: %s", exc)
            return fallback

    def _make_trade_decision(self, symbol, market_data, quant_signals, llm_result) -> dict:
# LLMAnalyzer returns "recommendation", fallback to "decision" for compatibility
action = llm_result.get("recommendation", llm_result.get("decision", "hold"))
reason = llm_result.get("reason", "")
# Use actual confidence from LLM; fallback only when completely missing
raw_confidence = llm_result.get("confidence")
if raw_confidence is not None:
    confidence = float(raw_confidence)
else:
    # LLM did not provide confidence at all (legacy/error path)
    confidence = 0.7 if action in ("buy", "sell") else 0.5

        if confidence < self.config["min_confidence"]:
            return {"action": "hold", "confidence": confidence, "volume": 0,
                    "reason": f"Confidence {confidence:.2f} below threshold."}

        volume = self._calculate_position_size(symbol, action, market_data)
        if volume <= 0:
            return {"action": "hold", "confidence": confidence, "volume": 0,
                    "reason": "Position size zero."}

        return {"action": action, "confidence": confidence, "volume": volume, "reason": reason}

    def _calculate_position_size(self, symbol, action, market_data) -> float:
        price = market_data.get("current_price", 0)
        if not price or price <= 0:
            return 0.0
        try:
            portfolio = self.exchange.get_portfolio()
        except Exception as exc:
            logger.warning("Failed to fetch portfolio: %s", exc)
            return 0.0

        if action == "buy":
            krw_df = portfolio.get("KRW")
            if krw_df is None or krw_df.empty:
                return 0.0
            krw_rows = krw_df[krw_df["symbol"] == "KRW"]
            krw = float(krw_rows["quantity"].sum()) if not krw_rows.empty else 0.0
            max_krw = krw * self.config["max_position_ratio"]
            return max_krw if max_krw >= self.config["min_order_krw"] else 0.0

        if action == "sell":
            coin = symbol.replace("KRW-", "")
            krw_df = portfolio.get("KRW")
            if krw_df is None or krw_df.empty:
                return 0.0
            coin_rows = krw_df[krw_df["symbol"] == symbol]
            qty = float(coin_rows["quantity"].sum()) if not coin_rows.empty else 0.0
            sell_vol = qty * self.config["max_position_ratio"]
            return sell_vol if sell_vol * price >= self.config["min_order_krw"] else 0.0

        return 0.0

    def _execute_and_log_trade(
        self, symbol, decision, market_data, quant_signals, llm_result, knowledge_context, dry_run
    ) -> dict:
        action = decision["action"]
        confidence = decision["confidence"]
        volume = decision.get("volume", 0)
        reason = decision.get("reason", "")

        analysis = {
            "rsi": market_data["indicators"].get("rsi_14"),
            "macd_signal": market_data["signals"].get("macd_signal"),
            "rsi_signal": market_data["signals"].get("rsi_signal"),
            "quant_signals": {k: str(v)[:100] for k, v in quant_signals.items()},
            "llm_decision": llm_result.get("decision"),
            "llm_confidence": confidence,
            "llm_reason": reason,
            "knowledge_hits": knowledge_context.count("\n") if knowledge_context else 0,
            "knowledge_summary": knowledge_context[:200] if knowledge_context else "",
        }

        order_result, executed, total_krw, fee = {}, False, 0.0, 0.0

        if not dry_run and action in ("buy", "sell"):
            try:
                if action == "buy":
                    order_result = self.exchange.buy_market(symbol, volume)
                    total_krw = volume
                    fee = volume * self.config["fee_rate"]
                else:
                    order_result = self.exchange.sell_market(symbol, volume)
                    total_krw = volume * market_data.get("current_price", 0)
                    fee = total_krw * self.config["fee_rate"]
                if "error" not in order_result:
                    executed = True
            except Exception as exc:
                logger.error("Order execution error: %s", exc)
                order_result = {"error": str(exc)}

        trade_record = self.journal.record_trade(
            symbol=symbol, action=action, volume=volume,
            price=market_data.get("current_price", 0),
            total_krw=total_krw, fee=fee,
            analysis=analysis,
            order_result=order_result if executed else None,
        )

        return {
            "trade_id": trade_record["trade_id"],
            "action": action, "confidence": confidence,
            "volume": volume, "price": market_data.get("current_price", 0),
            "total_krw": total_krw, "fee": fee,
            "executed": executed, "dry_run": dry_run,
            "reason": reason,
            "order_result": order_result if executed else None,
        }
