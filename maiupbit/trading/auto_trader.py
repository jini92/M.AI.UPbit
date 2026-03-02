# -*- coding: utf-8 -*-
"""maiupbit.trading.auto_trader Automated Trading System

This module provides an automated trading system that executes trades based on a series of steps including market data collection, quantitative signal analysis, knowledge gathering from Mnemo, and decision-making using LLM.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from maiupbit.exchange.upbit import UPbit
from maiupbit.trading.llm_analyzer import LlmAnalyzer
from maiupbit.trading.trade_journal import TradeJournal


class AutoTrader:
    def __init__(self, llm: LlmAnalyzer = None, journal: TradeJournal = None):
        self.llm = llm
        self.journal = journal

    def execute_trade(self, symbol: str, dry_run: bool = False) -> dict:
        market_data = self._collect_market_data(symbol)
        quant_signals = self._analyze_quantitative_signals()
        knowledge_context = self._gather_knowledge_from_mnemo()

        llm_result = self._make_llm_decision(market_data, quant_signals, knowledge_context)

        decision = self._make_trade_decision(symbol, market_data, quant_signals, llm_result)
        trade_record = self._execute_and_log_trade(symbol, decision, market_data, quant_signals, llm_result, dry_run)

        return trade_record

    def _collect_market_data(self, symbol: str) -> dict:
        current_price = self.exchange.get_current_price(symbol)
        indicators = self._calculate_technical_indicators()
        signals = self._generate_signal_analysis()

        market_data = {
            "current_price": current_price,
            "indicators": indicators,
            "signals": signals
        }

        return market_data

    def _analyze_quantitative_signals(self) -> dict:
        quant_signals = {}

        # Implement quantitative signal analysis logic here
        return quant_signals

    def _gather_knowledge_from_mnemo(self) -> str:
        knowledge_context = ""

        # Implement knowledge gathering from Mnemo here
        return knowledge_context

    def _make_llm_decision(self, market_data: dict, quant_signals: dict, knowledge_context: str) -> dict:
        fallback = {
            "decision": "hold",
            "confidence": 0.5,
            "reason": f"LLM is not available or encountered an error."
        }
        
        if self.llm:
            try:
                result = self.llm.analyze(
                    data_json=self._prepare_data_for_llm(market_data, quant_signals),
                    current_status=self._prepare_current_status(market_data),
                    macd_signals=[market_data["signals"].get("macd_signal", "neutral")],
                    technical_indicators={k: v for k, v in market_data["indicators"].items() if v is not None},
                    lstm_predictions=[],
                    news_text="",
                    knowledge_context=knowledge_context
                )
                
                return result if isinstance(result, dict) else fallback
            except Exception as exc:
                logging.error(f"LLM decision making error: {exc}")
        return fallback

    def _prepare_data_for_llm(self, market_data: dict, quant_signals: dict) -> str:
        data_json = {
            "symbol": market_data["current_price"],
            "indicators": market_data["indicators"],
            "quant_signals": {k: str(v)[:200] for k, v in quant_signals.items()}
        }
        
        return _json.dumps(data_json)

    def _prepare_current_status(self, market_data: dict) -> str:
        current_status = {
            "symbol": market_data["current_price"],
            "price": market_data.get("current_price"),
            "score": market_data.get("signals", {}).get("quant_score"),
            "recommendation": market_data.get("signals", {}).get("llm_decision")
        }
        
        return _json.dumps(current_status)

    def _make_trade_decision(self, symbol: str, market_data: dict, quant_signals: dict, llm_result: dict) -> dict:
        action = llm_result.get("decision", "hold")
        confidence = float(llm_result.get("confidence", 0.5))
        reason = llm_result.get("reason", "")

        if confidence < self.config["min_confidence"]:
            return {
                "action": "hold",
                "confidence": confidence,
                "volume": 0,
                "reason": f"Confidence {confidence:.2f} is below the minimum threshold."
            }

        volume = self._calculate_position_size(symbol, action)
        
        if volume <= 0:
            return {
                "action": "hold",
                "confidence": confidence,
                "volume": 0,
                "reason": f"Position size is zero due to insufficient balance or order size constraints."
            }
            
        return {
            "action": action,
            "confidence": confidence,
            "volume": volume,
            "reason": reason
        }

    def _calculate_position_size(self, symbol: str, action: str) -> float:
        price = self.exchange.get_current_price(symbol)
        
        if not price or price <= 0:
            return 0.0

        if action == "buy":
            balances = self.exchange.get_balances()
            krw_balance = sum(b["balance"] for b in balances if b["currency"] == "KRW")
            
            max_krw = krw_balance * self.config["max_position_ratio"]
            min_order_size = self.config["min_order_krw"]

            return max(min_order_size, max_krw) if max_krw >= min_order_size else 0.0

        elif action == "sell":
            balances = self.exchange.get_balances()
            coin_currency = symbol.replace("KRW-", "")
            
            coin_balance = sum(b["balance"] for b in balances if b["currency"] == coin_currency)
            sell_volume = coin_balance * self.config["max_position_ratio"]
            min_order_size = self.config["min_order_krw"]

            return max(min_order_size / price, sell_volume) if (sell_volume * price >= min_order_size) else 0.0

        return 0.0

    def _execute_and_log_trade(self, symbol: str, decision: dict, market_data: dict, quant_signals: dict, llm_result: dict, dry_run: bool = False) -> dict:
        action = decision["action"]
        confidence = decision["confidence"]
        volume = decision.get("volume", 0)
        reason = decision.get("reason", "")
        
        analysis = {
            "rsi": market_data["indicators"].get("rsi_14"),
            "macd_signal": market_data["signals"].get("macd_signal"),
            "stoch_k": market_data["indicators"].get("stoch_k"),
            "bb_position": market_data["signals"].get("bb_signal"),
            "quant_score": market_data.get("score"),
            "llm_decision": llm_result.get("decision"),
            "llm_confidence": confidence,
            "llm_reason": reason,
            "knowledge_hits": knowledge_context.count("\n") if knowledge_context else 0,
            "knowledge_summary": knowledge_context[:200] if knowledge_context else "",
            "strategy_signals": {k: str(v)[:100] for k, v in quant_signals.items()},
        }

        order_result = {}
        executed = False
        total_krw = 0.0
        fee = 0.0

        try:
            if action == "buy":
                order_result = self.exchange.buy_market(symbol, volume)
                total_krw = volume
                fee = volume * self.config["fee_rate"]
                
            elif action == "sell":
                order_result = self.exchange.sell_market(symbol, volume)
                total_krw = volume * market_data.get("current_price", 0)
                fee = total_krw * self.config["fee_rate"]

            if not dry_run and "error" not in order_result:
                executed = True
        except Exception as exc:
            logging.error(f"Order execution error: {exc}")
            order_result = {"error": str(exc)}

        trade_record = self.journal.record_trade(
            symbol=symbol,
            action=action,
            volume=volume,
            price=market_data.get("current_price", 0),
            total_krw=total_krw,
            fee=fee,
            analysis=analysis,
            order_result=order_result if executed else None
        )

        return {
            "trade_id": trade_record["trade_id"],
            "action": action,
            "confidence": confidence,
            "volume": volume,
            "price": market_data.get("current_price", 0),
            "total_krw": total_krw,
            "fee": fee,
            "executed": executed,
            "dry_run": dry_run,
            "reason": reason,
            "order_result": order_result if executed else None
        }