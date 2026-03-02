# -*- coding: utf-8 -*-
"""maiupbit.trading.journal — Structured trading records (with analysis rationale).

Stores trading records in JSON format, including analysis rationale and post-trade evaluation.
Serves as the original data for Mnemo knowledge graph and Obsidian notes creation.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


def _now_kst() -> datetime:
    return datetime.now(KST)


class TradeJournal:
    """Manager for structured trading records.

    Attributes:
        path: Journal JSON file path.
    """

    def __init__(self, path: str = "trade_journal.json") -> None:
        self.path = Path(path)
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def _load(self) -> list[dict]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            logger.warning("Journal file damaged, initializing with empty list: %s", self.path)
            return []

    def _save(self, records: list[dict]) -> None:
        self.path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def record_trade(
        self,
        symbol: str,
        action: str,
        volume: float,
        price: float,
        total_krw: float,
        fee: float,
        analysis: Optional[dict] = None,
        order_result: Optional[dict] = None,
    ) -> dict:
        """Save trading record.

        Args:
            symbol: Trade symbol (e.g., ``KRW-BTT``).
            action: ``"buy"`` / ``"sell"`` / ``"hold"``.
            volume: Trade quantity.
            price: Execution price.
            total_krw: Total trade amount in KRW.
            fee: Fee in KRW.
            analysis: AI rationale dict.
            order_result: UPbit API response.

        Returns:
            Saved trading record dict (includes trade_id).
        """
        now = _now_kst()
        trade_id = f"{now.strftime('%Y-%m-%d_%H-%M')}_{symbol}_{action}_{uuid.uuid4().hex[:6]}"

        record: dict = {
            "trade_id": trade_id,
            "timestamp": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "symbol": symbol,
            "action": action,
            "volume": volume,
            "price": price,
            "total_krw": total_krw,
            "fee": fee,
            "analysis": analysis or {},
            "order_result": order_result or {},
            "outcome": {
                "price_after_24h": None,
                "pnl_percent": None,
                "was_correct": None,
                "evaluated_at": None,
            },
        }

        records = self._load()
        records.append(record)
        self._save(records)
        logger.info("Trade record saved: %s %s %s", action, symbol, trade_id)
        return record

    def update_outcome(self, trade_id: str, outcome: dict) -> bool:
        """Update post-trade evaluation.

        Args:
            trade_id: Target trade ID.
            outcome: ``{price_after_24h, pnl_percent, was_correct}``

        Returns:
            Success of the update operation.
        """
        records = self._load()
        for rec in records:
            if rec["trade_id"] == trade_id:
                rec["outcome"] = {
                    **rec.get("outcome", {}),
                    **outcome,
                    "evaluated_at": _now_kst().isoformat(),
                }
                self._save(records)
                logger.info("Post-trade evaluation completed: %s", trade_id)
                return True
        logger.warning("Trade ID not found: %s", trade_id)
        return False

    def get_pending_outcomes(self, min_hours: float = 24.0) -> list[dict]:
        """List of trades pending post-trade evaluation and older than 24 hours.

        Args:
            min_hours: Minimum elapsed time (default 24 hours).

        Returns:
            List of trades awaiting evaluation.
        """
        records = self._load()
        cutoff = _now_kst() - timedelta(hours=min_hours)
        pending = []
        for rec in records:
            if rec.get("action") == "hold":
                continue
            outcome = rec.get("outcome", {})
            if outcome.get("evaluated_at") is not None:
                continue
            ts = datetime.fromisoformat(rec["timestamp"])
            if ts <= cutoff:
                pending.append(rec)
        return pending

    def get_trades(
        self,
        symbol: Optional[str] = None,
        days: Optional[int] = None,
        action: Optional[str] = None,
    ) -> list[dict]:
        """Retrieve trading records.

        Args:
            symbol: Symbol filter.
            days: Recent N-day filter.
            action: Action filter (buy/sell/hold).

        Returns:
            Filtered trade list (latest first).
        """
        records = self._load()
        if symbol:
            records = [r for r in records if r["symbol"] == symbol]
        if action:
            records = [r for r in records if r["action"] == action]
        if days:
            cutoff = _now_kst() - timedelta(days=days)
            records = [
                r for r in records
                if datetime.fromisoformat(r["timestamp"]) >= cutoff
            ]
        return sorted(records, key=lambda r: r["timestamp"], reverse=True)

    def get_stats(self, days: int = 30) -> dict:
        """Summary statistics.

        Args:
            days: Recent N-day period.

        Returns:
            Total trades, win rate, average PnL, max loss, etc.
        """
        trades = self.get_trades(days=days)
        executed = [t for t in trades if t["action"] in ("buy", "sell")]
        evaluated = [
            t for t in executed
            if t.get("outcome", {}).get("was_correct") is not None
        ]
        pnls = [o['pnl_percent'] for o in [trade.get('outcome', {}) for trade in evaluated] if o['pnl_percent']]

        stats = {
            'total_trades': len(trades),
            'executed_trades': len(executed),
            'evaluated_trades': len(evaluated),
            'win_rate': sum([o['was_correct'] for o in [trade.get('outcome', {}) for trade in evaluated]]) / len(evaluated) if evaluated else 0,
            'average_pnl': sum(pnls) / len(pnls) if pnls else None
        }

        return stats

    def to_markdown(self, trade: dict) -> str:
        """Convert a trading record into markdown format.

        Args:
            trade: Trading record dictionary.

        Returns:
            Markdown string.
        """
        analysis = trade.get("analysis", {})
        outcome = trade.get("outcome", {})
        coin = trade["symbol"].replace("KRW-", "")

        lines = [
            "---",
            f"tags: [maiupbit, trade, {coin}, {trade['action']}]",
            f"date: {trade['date']}",
            f"symbol: {trade['symbol']}",
            f"action: {trade['action']}",
            f"confidence: {analysis.get('llm_confidence', 'N/A')}",
            f"pnl: {outcome.get('pnl_percent', 'null')}",
            "---",
            "",
            "## Trading Record",
            f"- **Symbol:** {trade['symbol']}",
            f"- **Action:** {trade['action']}",
            f"- **Quantity:** {trade['volume']:,.0f} @ ₩{trade['price']:.6f}",
            f"- **Total Amount:** ₩{trade['total_krw']:,.2f}",
            f"- **Fee:** ₩{trade['fee']:,.2f}",
            f"- **Timestamp:** {trade['timestamp']}",
            "",
            "## AI Analysis Rationale",
            f"- **RSI:** {analysis.get('rsi', 'N/A')}",
            f"- **MACD Signal:** {analysis.get('macd_signal', 'N/A')}",
            f"- **Stochastic K:** {analysis.get('stoch_k', 'N/A')}",
            f"- **Quant Score:** {analysis.get('quant_score', 'N/A')}",
            f"- **LLM Decision:** {analysis.get('llm_decision', 'N/A')} "
            f"(confidence: {analysis.get('llm_confidence', 'N/A')})",
            f"- **Reasoning:** {analysis.get('llm_reason', 'N/A')}",
            "",
            "## Mnemo Knowledge Reference",
            f"- Search results: {analysis.get('knowledge_hits', 0)} hits",
            f"- Summary: {analysis.get('knowledge_summary', 'none')}",
            "",
            "## Post-Trade Evaluation",
        ]

        if outcome.get("evaluated_at"):
            lines.extend([
                f"- Price after 24h: ₩{outcome.get('price_after_24h', 'N/A')}",
                f"- Profit/Loss: {outcome.get('pnl_percent', 'N/A')}%",
                f"- Accuracy of prediction: {'✅ Correct' if outcome.get('was_correct') else '❌ Incorrect'}",
                f"- Evaluation timestamp: {outcome['evaluated_at']}",
            ])
        else:
            lines.extend([
                "- Price after 24h: (Pending evaluation)",
                "- Profit/Loss: (Pending evaluation)",
                "- Accuracy of prediction: (Pending evaluation)",
            ])

        return "\n".join(lines) + "\n"