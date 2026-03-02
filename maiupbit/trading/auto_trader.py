# -*- coding: utf-8 -*-
"""maiupbit.trading.auto_trader ???먮룞留ㅻℓ ?ㅼ??ㅽ듃?덉씠??

遺꾩꽍 ??寃곗젙 ???ㅽ뻾 ??湲곕줉 ?꾩껜 ?뚮줈?곕? ?⑥씪 ``run()`` ?몄텧濡??섑뻾.
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
    """?먮룞留ㅻℓ ?ㅼ??ㅽ듃?덉씠??

    ?쒖옣 ?곗씠???섏쭛 ??????쒓렇????Mnemo 吏??議고쉶 ??    LLM 醫낇빀 遺꾩꽍 ??留ㅻℓ 寃곗젙 ???ㅽ뻾 ??湲곕줉.

    Attributes:
        exchange: UPbit 嫄곕옒???몄뒪?댁뒪.
        journal: 嫄곕옒 湲곕줉 ???
        config: ?댁슜 ?ㅼ젙.
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
    # 硫붿씤 ?ㅽ뻾
    # ------------------------------------------------------------------

    def run(self, symbol: str = "KRW-BTC", dry_run: bool = False) -> dict:
        """?꾩껜 ?먮룞留ㅻℓ ?뚮줈???ㅽ뻾.

        Args:
            symbol: 嫄곕옒 ?щ낵.
            dry_run: True硫?遺꾩꽍留??섍퀬 留ㅻℓ ?ㅽ뻾 ????

        Returns:
            ?ㅽ뻾 寃곌낵 dict (action, confidence, executed, trade_id ??.
        """
        logger.info("=== AutoTrader ?ㅽ뻾: %s (dry_run=%s) ===", symbol, dry_run)

        # Step 1: ?쒖옣 ?곗씠??+ 湲곗닠吏??        market = self._collect_market_data(symbol)
        if not market:
            return {"action": "error", "reason": "?쒖옣 ?곗씠???섏쭛 ?ㅽ뙣"}

        # Step 2: ????쒓렇??        quant = self._collect_quant_signals(symbol)

        # Step 3: Mnemo 吏??        knowledge_ctx = self._collect_knowledge(symbol)

        # Step 4: LLM 遺꾩꽍
        llm_result = self._run_llm_analysis(symbol, market, quant, knowledge_ctx)

        # Step 5: 留ㅻℓ 寃곗젙
        decision = self._make_decision(symbol, market, quant, llm_result)

        # Step 6: ?ㅽ뻾 + 湲곕줉
        result = self._execute_and_record(
            symbol, decision, market, quant, llm_result, knowledge_ctx, dry_run
        )

        logger.info("AutoTrader ?꾨즺: %s ??%s (conf=%.2f)",
                     symbol, result.get("action"), result.get("confidence", 0))
        return result

    # ------------------------------------------------------------------
    # Step 1: ?쒖옣 ?곗씠??    # ------------------------------------------------------------------

    def _collect_market_data(self, symbol: str) -> Optional[dict]:
        """?쒖옣 ?곗씠??+ 湲곗닠吏???섏쭛."""
        try:
            price = self.exchange.get_current_price(symbol)
            if not price:
                return None

            # OHLCV DataFrame 媛?몄삤湲?            df = self.exchange.get_ohlcv(symbol, interval="day", count=60)
            if df is None or df.empty:
                logger.warning("OHLCV ?곗씠???놁쓬, 媛寃⑸쭔 ?ъ슜")
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
            logger.error("?쒖옣 ?곗씠???섏쭛 ?ㅽ뙣: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Step 2: ????쒓렇??    # ------------------------------------------------------------------

    def _collect_quant_signals(self, symbol: str) -> dict:
        """????꾨왂 ?쒓렇???섏쭛."""
        signals: dict = {}
        try:
            from maiupbit.strategies.seasonal import SeasonalStrategy
            season = SeasonalStrategy()
            signals["season"] = season.analyze()
        except Exception as exc:
            logger.debug("?쒖쫵 遺꾩꽍 ?ㅽ뙣: %s", exc)

        try:
            from maiupbit.strategies.volatility_breakout import VolatilityBreakoutStrategy
            vb = VolatilityBreakoutStrategy(self.exchange)
            signals["breakout"] = vb.analyze(symbol)
        except Exception as exc:
            logger.debug("?뚰뙆 遺꾩꽍 ?ㅽ뙣: %s", exc)

        try:
            from maiupbit.strategies.momentum import DualMomentumStrategy
            mom = DualMomentumStrategy(self.exchange)
            signals["momentum"] = mom.analyze(symbols=[symbol])
        except Exception as exc:
            logger.debug("紐⑤찘? 遺꾩꽍 ?ㅽ뙣: %s", exc)

        return signals

    # ------------------------------------------------------------------
    # Step 3: Mnemo 吏??    # ------------------------------------------------------------------

    def _collect_knowledge(self, symbol: str) -> str:
        """Mnemo 吏?앷렇?섑봽?먯꽌 愿??而⑦뀓?ㅽ듃 ?섏쭛."""
        if not self.knowledge:
            return ""
        try:
            ctx = self.knowledge.enrich_llm_context(symbol)
            return ctx if ctx else ""
        except Exception as exc:
            logger.debug("Mnemo 吏???섏쭛 ?ㅽ뙣 (graceful skip): %s", exc)
            return ""

    # ------------------------------------------------------------------
    # Step 4: LLM 遺꾩꽍
    # ------------------------------------------------------------------

    def _run_llm_analysis(
        self, symbol: str, market: dict, quant: dict, knowledge_ctx: str
    ) -> dict:
        """LLM 醫낇빀 遺꾩꽍."""
        fallback = {
            "decision": market.get("recommendation", "hold"),
            "confidence": market.get("score", 0.5),
            "reason": "湲곗닠吏??湲곕컲 ?먮떒 (LLM 誘몄궗??",
        }
        if not self.llm:
            return fallback
        import concurrent.futures as _cf
        import os as _os
        LLM_STEP_TIMEOUT = float(_os.getenv("LLM_STEP_TIMEOUT", "90"))

        def _do_llm_call() -> dict:
            import json as _json
            indicators = market.get("indicators", {})
            signals = market.get("signals", {})
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

        try:
            with _cf.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(_do_llm_call)
                return future.result(timeout=LLM_STEP_TIMEOUT)
        except _cf.TimeoutError:
            logger.error("LLM timeout (%ds): %s", LLM_STEP_TIMEOUT, symbol)
            fallback["reason"] = f"LLM timeout ({LLM_STEP_TIMEOUT}s), fallback to technicals"
            return fallback
        except Exception as exc:
            logger.error("LLM error: %s", exc)
            fallback["reason"] = f"LLM failed, fallback to technicals: {exc}"
            return fallback

    # ------------------------------------------------------------------
    # Step 5: 留ㅻℓ 寃곗젙
    # ------------------------------------------------------------------

    def _make_decision(
        self, symbol: str, market: dict, quant: dict, llm_result: dict
    ) -> dict:
        """留ㅻℓ 寃곗젙 濡쒖쭅.

        Returns:
            {action, confidence, volume, reason}
        """
        action = llm_result.get("decision", "hold")
        confidence = float(llm_result.get("confidence", 0.5))
        reason = llm_result.get("reason", "")

        # Confidence 泥댄겕
        if confidence < self.config["min_confidence"]:
            return {
                "action": "hold",
                "confidence": confidence,
                "volume": 0,
                "reason": f"Confidence {confidence:.2f} < {self.config['min_confidence']} ?꾧퀎媛?,
            }

        # ?ъ????ъ씠吏?        volume = self._calculate_position_size(symbol, action)
        if volume <= 0:
            return {
                "action": "hold",
                "confidence": confidence,
                "volume": 0,
                "reason": f"?ъ????ъ씠利?0 (理쒖냼二쇰Ц 誘몃떖 ?먮뒗 ?붽퀬 遺議?",
            }

        return {
            "action": action,
            "confidence": confidence,
            "volume": volume,
            "reason": reason,
        }

    def _calculate_position_size(self, symbol: str, action: str) -> float:
        """?ъ????ъ씠吏?(?먯궛??理쒕? 10%, 理쒖냼二쇰Ц ??,000 怨좊젮)."""
        try:
            price = self.exchange.get_current_price(symbol)
            if not price or price <= 0:
                return 0.0

            if action == "buy":
                # KRW ?붽퀬 湲곕컲
                balances = self.exchange.get_balances()
                krw = 0.0
                for b in balances:
                    if b.get("currency") == "KRW":
                        krw = float(b.get("balance", 0))
                        break
                max_krw = krw * self.config["max_position_ratio"]
                if max_krw < self.config["min_order_krw"]:
                    # ?붽퀬 遺議깊븯硫?理쒖냼二쇰Ц湲덉븸 ?쒕룄
                    max_krw = self.config["min_order_krw"] if krw >= self.config["min_order_krw"] else 0
                return max_krw  # buy??KRW 湲덉븸 諛섑솚

            elif action == "sell":
                # 肄붿씤 ?붽퀬 湲곕컲
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
                    # 理쒖냼二쇰Ц 誘몃떖 ??理쒖냼二쇰Ц??留욊쾶 ?щ┝
                    sell_volume = self.config["min_order_krw"] / price
                    if sell_volume > coin_balance:
                        return 0.0  # ?붽퀬 遺議?                return sell_volume

        except Exception as exc:
            logger.error("?ъ????ъ씠吏??ㅽ뙣: %s", exc)
            return 0.0
        return 0.0

    # ------------------------------------------------------------------
    # Step 6: ?ㅽ뻾 + 湲곕줉
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
        """留ㅻℓ ?ㅽ뻾 + TradeJournal 湲곕줉."""
        action = decision["action"]
        confidence = decision["confidence"]
        volume = decision.get("volume", 0)
        reason = decision.get("reason", "")
        price = market.get("current_price", 0)
        indicators = market.get("indicators", {})

        # 遺꾩꽍 洹쇨굅 援ъ꽦
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
                    logger.error("二쇰Ц ?ㅽ뙣: %s", order_result)
            except Exception as exc:
                logger.error("二쇰Ц ?ㅽ뻾 ?덉쇅: %s", exc)
                order_result = {"error": str(exc)}

        # ???湲곕줉 (hold??湲곕줉 ???곗씠??異뺤쟻)
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

