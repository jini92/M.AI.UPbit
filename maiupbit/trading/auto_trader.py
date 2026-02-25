# -*- coding: utf-8 -*-
"""maiupbit.trading.auto_trader — 자동매매 오케스트레이터.

분석 → 결정 → 실행 → 기록 전체 플로우를 단일 ``run()`` 호출로 수행.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from maiupbit.exchange.upbit import UPbitExchange
from maiupbit.trading.journal import TradeJournal

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

_DEFAULT_CONFIG: dict = {
    "max_position_ratio": 0.10,
    "min_confidence": 0.60,
    "min_profit_threshold": 0.003,
    "daily_loss_limit": -0.05,
    "fee_rate": 0.0005,
    "min_order_krw": 5000,
}


class AutoTrader:
    """자동매매 오케스트레이터.

    시장 데이터 수집 → 퀀트 시그널 → Mnemo 지식 조회 →
    LLM 종합 분석 → 매매 결정 → 실행 → 기록.

    Attributes:
        exchange: UPbit 거래소 인스턴스.
        journal: 거래 기록 저널.
        config: 운용 설정.
    """

    def __init__(
        self,
        exchange: UPbitExchange,
        journal: TradeJournal,
        llm_analyzer=None,
        knowledge_provider=None,
        config: Optional[dict] = None,
    ) -> None:
        self.exchange = exchange
        self.journal = journal
        self.llm = llm_analyzer
        self.knowledge = knowledge_provider
        self.config = {**_DEFAULT_CONFIG, **(config or {})}

    # ------------------------------------------------------------------
    # 메인 실행
    # ------------------------------------------------------------------

    def run(self, symbol: str = "KRW-BTT", dry_run: bool = False) -> dict:
        """전체 자동매매 플로우 실행.

        Args:
            symbol: 거래 심볼.
            dry_run: True면 분석만 하고 매매 실행 안 함.

        Returns:
            실행 결과 dict (action, confidence, executed, trade_id 등).
        """
        logger.info("=== AutoTrader 실행: %s (dry_run=%s) ===", symbol, dry_run)

        # Step 1: 시장 데이터 + 기술지표
        market = self._collect_market_data(symbol)
        if not market:
            return {"action": "error", "reason": "시장 데이터 수집 실패"}

        # Step 2: 퀀트 시그널
        quant = self._collect_quant_signals(symbol)

        # Step 3: Mnemo 지식
        knowledge_ctx = self._collect_knowledge(symbol)

        # Step 4: LLM 분석
        llm_result = self._run_llm_analysis(symbol, market, quant, knowledge_ctx)

        # Step 5: 매매 결정
        decision = self._make_decision(symbol, market, quant, llm_result)

        # Step 6: 실행 + 기록
        result = self._execute_and_record(
            symbol, decision, market, quant, llm_result, knowledge_ctx, dry_run
        )

        logger.info("AutoTrader 완료: %s → %s (conf=%.2f)",
                     symbol, result.get("action"), result.get("confidence", 0))
        return result

    # ------------------------------------------------------------------
    # Step 1: 시장 데이터
    # ------------------------------------------------------------------

    def _collect_market_data(self, symbol: str) -> Optional[dict]:
        """시장 데이터 + 기술지표 수집."""
        try:
            price = self.exchange.get_current_price(symbol)
            if not price:
                return None

            # OHLCV DataFrame 가져오기
            df = self.exchange.get_ohlcv(symbol, interval="day", count=60)
            if df is None or df.empty:
                logger.warning("OHLCV 데이터 없음, 가격만 사용")
                return {"current_price": price, "indicators": {},
                        "signals": {}, "score": 0.5, "recommendation": "hold"}

            from maiupbit.analysis.technical import TechnicalAnalyzer
            analyzer = TechnicalAnalyzer(self.exchange)
            analysis = analyzer.analyze(symbol, df)

            return {
                "current_price": price,
                "indicators": analysis.get("indicators", {}),
                "signals": analysis.get("signals", {}),
                "score": analysis.get("score", 0.5),
                "recommendation": analysis.get("recommendation", "hold"),
            }
        except Exception as exc:
            logger.error("시장 데이터 수집 실패: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Step 2: 퀀트 시그널
    # ------------------------------------------------------------------

    def _collect_quant_signals(self, symbol: str) -> dict:
        """퀀트 전략 시그널 수집."""
        signals: dict = {}
        try:
            from maiupbit.strategies.seasonal import SeasonalStrategy
            season = SeasonalStrategy()
            signals["season"] = season.analyze()
        except Exception as exc:
            logger.debug("시즌 분석 실패: %s", exc)

        try:
            from maiupbit.strategies.volatility_breakout import VolatilityBreakoutStrategy
            vb = VolatilityBreakoutStrategy(self.exchange)
            signals["breakout"] = vb.analyze(symbol)
        except Exception as exc:
            logger.debug("돌파 분석 실패: %s", exc)

        try:
            from maiupbit.strategies.momentum import DualMomentumStrategy
            mom = DualMomentumStrategy(self.exchange)
            signals["momentum"] = mom.analyze(symbols=[symbol])
        except Exception as exc:
            logger.debug("모멘텀 분석 실패: %s", exc)

        return signals

    # ------------------------------------------------------------------
    # Step 3: Mnemo 지식
    # ------------------------------------------------------------------

    def _collect_knowledge(self, symbol: str) -> str:
        """Mnemo 지식그래프에서 관련 컨텍스트 수집."""
        if not self.knowledge:
            return ""
        try:
            ctx = self.knowledge.enrich_llm_context(symbol)
            return ctx if ctx else ""
        except Exception as exc:
            logger.debug("Mnemo 지식 수집 실패 (graceful skip): %s", exc)
            return ""

    # ------------------------------------------------------------------
    # Step 4: LLM 분석
    # ------------------------------------------------------------------

    def _run_llm_analysis(
        self, symbol: str, market: dict, quant: dict, knowledge_ctx: str
    ) -> dict:
        """LLM 종합 분석."""
        fallback = {
            "decision": market.get("recommendation", "hold"),
            "confidence": market.get("score", 0.5),
            "reason": "기술지표 기반 판단 (LLM 미사용)",
        }
        if not self.llm:
            return fallback
        try:
            import json as _json

            indicators = market.get("indicators", {})
            signals = market.get("signals", {})

            # LLMAnalyzer.analyze() 시그니처에 맞게 인자 구성
            data_json = _json.dumps({
                "symbol": symbol,
                "current_price": market.get("current_price"),
                "indicators": indicators,
                "quant_signals": {k: str(v)[:200] for k, v in quant.items()},
            }, default=str)

            current_status = _json.dumps({
                "symbol": symbol,
                "price": market.get("current_price"),
                "score": market.get("score"),
                "recommendation": market.get("recommendation"),
            }, default=str)

            macd_signal = signals.get("macd_signal", "neutral")
            tech_indicators = {
                k: v for k, v in indicators.items() if v is not None
            }

            result = self.llm.analyze(
                data_json=data_json,
                current_status=current_status,
                macd_signals=[macd_signal],
                technical_indicators=tech_indicators,
                lstm_predictions=[],
                news_text="",
                knowledge_context=knowledge_ctx,
            )
            return result if isinstance(result, dict) else fallback
        except Exception as exc:
            logger.error("LLM 분석 실패: %s", exc)
            fallback["reason"] = f"LLM 실패, 기술지표 폴백: {exc}"
            return fallback

    # ------------------------------------------------------------------
    # Step 5: 매매 결정
    # ------------------------------------------------------------------

    def _make_decision(
        self, symbol: str, market: dict, quant: dict, llm_result: dict
    ) -> dict:
        """매매 결정 로직.

        Returns:
            {action, confidence, volume, reason}
        """
        action = llm_result.get("decision", "hold")
        confidence = float(llm_result.get("confidence", 0.5))
        reason = llm_result.get("reason", "")

        # Confidence 체크
        if confidence < self.config["min_confidence"]:
            return {
                "action": "hold",
                "confidence": confidence,
                "volume": 0,
                "reason": f"Confidence {confidence:.2f} < {self.config['min_confidence']} 임계값",
            }

        # 포지션 사이징
        volume = self._calculate_position_size(symbol, action)
        if volume <= 0:
            return {
                "action": "hold",
                "confidence": confidence,
                "volume": 0,
                "reason": f"포지션 사이즈 0 (최소주문 미달 또는 잔고 부족)",
            }

        return {
            "action": action,
            "confidence": confidence,
            "volume": volume,
            "reason": reason,
        }

    def _calculate_position_size(self, symbol: str, action: str) -> float:
        """포지션 사이징 (자산의 최대 10%, 최소주문 ₩5,000 고려)."""
        try:
            price = self.exchange.get_current_price(symbol)
            if not price or price <= 0:
                return 0.0

            if action == "buy":
                # KRW 잔고 기반
                balances = self.exchange.get_balances()
                krw = 0.0
                for b in balances:
                    if b.get("currency") == "KRW":
                        krw = float(b.get("balance", 0))
                        break
                max_krw = krw * self.config["max_position_ratio"]
                if max_krw < self.config["min_order_krw"]:
                    # 잔고 부족하면 최소주문금액 시도
                    max_krw = self.config["min_order_krw"] if krw >= self.config["min_order_krw"] else 0
                return max_krw  # buy는 KRW 금액 반환

            elif action == "sell":
                # 코인 잔고 기반
                balances = self.exchange.get_balances()
                coin_currency = symbol.replace("KRW-", "")
                coin_balance = 0.0
                for b in balances:
                    if b.get("currency") == coin_currency:
                        coin_balance = float(b.get("balance", 0))
                        break
                sell_volume = coin_balance * self.config["max_position_ratio"]
                sell_krw = sell_volume * price
                if sell_krw < self.config["min_order_krw"]:
                    # 최소주문 미달 → 최소주문에 맞게 올림
                    sell_volume = self.config["min_order_krw"] / price
                    if sell_volume > coin_balance:
                        return 0.0  # 잔고 부족
                return sell_volume

        except Exception as exc:
            logger.error("포지션 사이징 실패: %s", exc)
            return 0.0
        return 0.0

    # ------------------------------------------------------------------
    # Step 6: 실행 + 기록
    # ------------------------------------------------------------------

    def _execute_and_record(
        self,
        symbol: str,
        decision: dict,
        market: dict,
        quant: dict,
        llm_result: dict,
        knowledge_ctx: str,
        dry_run: bool,
    ) -> dict:
        """매매 실행 + TradeJournal 기록."""
        action = decision["action"]
        confidence = decision["confidence"]
        volume = decision.get("volume", 0)
        reason = decision.get("reason", "")
        price = market.get("current_price", 0)
        indicators = market.get("indicators", {})

        # 분석 근거 구성
        analysis = {
            "rsi": indicators.get("rsi_14"),
            "macd_signal": market.get("signals", {}).get("macd_signal"),
            "stoch_k": indicators.get("stoch_k"),
            "bb_position": market.get("signals", {}).get("bb_signal"),
            "quant_score": market.get("score"),
            "llm_decision": llm_result.get("decision"),
            "llm_confidence": confidence,
            "llm_reason": reason,
            "knowledge_hits": knowledge_ctx.count("\n") if knowledge_ctx else 0,
            "knowledge_summary": knowledge_ctx[:200] if knowledge_ctx else "",
            "strategy_signals": {k: str(v)[:100] for k, v in quant.items()},
        }

        order_result = {}
        executed = False
        total_krw = 0.0
        fee = 0.0

        if action in ("buy", "sell") and not dry_run:
            try:
                if action == "buy":
                    order_result = self.exchange.buy_market(symbol, volume)
                    total_krw = volume
                    fee = volume * self.config["fee_rate"]
                else:
                    order_result = self.exchange.sell_market(symbol, volume)
                    total_krw = volume * price
                    fee = total_krw * self.config["fee_rate"]

                if "error" not in order_result:
                    executed = True
                else:
                    logger.error("주문 실패: %s", order_result)
            except Exception as exc:
                logger.error("주문 실행 예외: %s", exc)
                order_result = {"error": str(exc)}

        # 저널 기록 (hold도 기록 — 데이터 축적)
        trade = self.journal.record_trade(
            symbol=symbol,
            action=action,
            volume=volume,
            price=price,
            total_krw=total_krw,
            fee=fee,
            analysis=analysis,
            order_result=order_result if executed else None,
        )

        return {
            "trade_id": trade["trade_id"],
            "action": action,
            "confidence": confidence,
            "volume": volume,
            "price": price,
            "total_krw": total_krw,
            "fee": fee,
            "executed": executed,
            "dry_run": dry_run,
            "reason": reason,
            "order_result": order_result if executed else None,
        }
