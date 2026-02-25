# -*- coding: utf-8 -*-
"""maiupbit.trading.outcome — 매매 사후 평가.

매매 후 24시간 경과한 거래의 가격 변동을 조회하여
판단 정확도를 자동 평가합니다.
"""

from __future__ import annotations

import logging
from typing import Optional

from maiupbit.exchange.upbit import UPbitExchange
from maiupbit.trading.journal import TradeJournal

logger = logging.getLogger(__name__)


class OutcomeTracker:
    """매매 사후 평가 추적기.

    Attributes:
        exchange: UPbit 거래소 인스턴스.
        journal: 거래 기록 저널.
    """

    def __init__(self, exchange: UPbitExchange, journal: TradeJournal) -> None:
        self.exchange = exchange
        self.journal = journal

    def evaluate_pending(self, min_hours: float = 24.0) -> list[dict]:
        """미평가 매매 일괄 평가.

        Args:
            min_hours: 최소 경과 시간 (기본 24h).

        Returns:
            평가된 결과 목록.
        """
        pending = self.journal.get_pending_outcomes(min_hours=min_hours)
        results = []

        for trade in pending:
            result = self._evaluate_trade(trade)
            if result:
                self.journal.update_outcome(trade["trade_id"], result)
                results.append({
                    "trade_id": trade["trade_id"],
                    "symbol": trade["symbol"],
                    "action": trade["action"],
                    **result,
                })

        logger.info("사후 평가 완료: %d/%d건", len(results), len(pending))
        return results

    def _evaluate_trade(self, trade: dict) -> Optional[dict]:
        """단일 매매 평가.

        Args:
            trade: 거래 레코드.

        Returns:
            평가 결과 dict 또는 None.
        """
        symbol = trade["symbol"]
        action = trade["action"]
        entry_price = trade["price"]

        if not entry_price or entry_price <= 0:
            logger.warning("진입 가격 없음: %s", trade["trade_id"])
            return None

        try:
            current_price = self.exchange.get_current_price(symbol)
            if not current_price:
                return None
        except Exception as exc:
            logger.error("가격 조회 실패 [%s]: %s", symbol, exc)
            return None

        # 수익률 계산
        pnl_percent = ((current_price - entry_price) / entry_price) * 100

        # 정확도 판정
        if action == "sell":
            # 매도 후 가격 하락 → 올바른 판단
            was_correct = current_price <= entry_price
            pnl_percent = -pnl_percent  # 매도는 하락이 수익
        elif action == "buy":
            # 매수 후 가격 상승 → 올바른 판단
            was_correct = current_price >= entry_price
        else:
            was_correct = None

        result = {
            "price_after_24h": current_price,
            "pnl_percent": round(pnl_percent, 4),
            "was_correct": was_correct,
        }

        logger.info(
            "평가: %s %s — entry=%.6f, now=%.6f, pnl=%.2f%%, correct=%s",
            action, symbol, entry_price, current_price, pnl_percent,
            "✅" if was_correct else "❌",
        )
        return result
