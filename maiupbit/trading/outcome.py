# -*- coding: utf-8 -*-
"""maiupbit.trading.outcome — trading post-evaluation.

Evaluates the price movement of trades that have passed 24 hours after execution to automatically assess judgment accuracy.
"""

from __future__ import annotations

import logging
from typing import Optional

from maiupbit.exchange.upbit import UPbitExchange
from maiupbit.trading.journal import TradeJournal

logger = logging.getLogger(__name__)


class OutcomeTracker:
    """Trading post-evaluation tracker.

    Attributes:
        exchange: UPbit exchange instance.
        journal: trade record journal.
    """

    def __init__(self, exchange: UPbitExchange, journal: TradeJournal) -> None:
        self.exchange = exchange
        self.journal = journal

    def evaluate_pending(self, min_hours: float = 24.0) -> list[dict]:
        """Batch evaluation of pending trades.

        Args:
            min_hours: minimum elapsed time (default 24h).

        Returns:
            List of evaluated results.
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

        logger.info("Post-evaluation complete: %d/%d items", len(results), len(pending))
        return results

    def _evaluate_trade(self, trade: dict) -> Optional[dict]:
        """Evaluate a single trade.

        Args:
            trade: trade record.

        Returns:
            Evaluation result dict or None.
        """
        symbol = trade["symbol"]
        action = trade["action"]
        entry_price = trade["price"]

        if not entry_price or entry_price <= 0:
            logger.warning("No entry price: %s", trade["trade_id"])
            return None

        try:
            current_price = self.exchange.get_current_price(symbol)
            if not current_price:
                return None
        except Exception as exc:
            logger.error("Price lookup failed [%s]: %s", symbol, exc)
            return None

        # Calculate profit and loss percentage
        pnl_percent = ((current_price - entry_price) / entry_price) * 100

        # Accuracy assessment
        if action == "sell":
            # Price decline after sell → correct judgment
            was_correct = current_price <= entry_price
            pnl_percent = -pnl_percent  # Sell is profit with a price drop
        elif action == "buy":
            # Price rise after buy → correct judgment
            was_correct = current_price >= entry_price
        else:
            was_correct = None

        result = {
            "price_after_24h": current_price,
            "pnl_percent": round(pnl_percent, 4),
            "was_correct": was_correct,
        }

        logger.info(
            "Evaluation: %s %s — entry=%.6f, now=%.6f, pnl=%.2f%%, correct=%s",
            action, symbol, entry_price, current_price, pnl_percent,
            "✅" if was_correct else "❌",
        )
        return result