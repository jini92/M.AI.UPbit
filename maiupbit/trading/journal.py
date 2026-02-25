# -*- coding: utf-8 -*-
"""maiupbit.trading.journal — 구조화된 거래 기록 (분석 근거 포함).

매매 기록을 분석 근거·사후 평가와 함께 JSON으로 저장.
Mnemo 지식그래프 + Obsidian 노트 생성의 원본 데이터.
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
    """구조화된 거래 기록 관리자.

    Attributes:
        path: 저널 JSON 파일 경로.
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
            logger.warning("저널 파일 손상, 빈 리스트로 초기화: %s", self.path)
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
        """매매 기록 저장.

        Args:
            symbol: 거래 심볼 (예: ``KRW-BTT``).
            action: ``"buy"`` / ``"sell"`` / ``"hold"``.
            volume: 거래 수량.
            price: 체결 가격.
            total_krw: 총 거래 금액 (KRW).
            fee: 수수료 (KRW).
            analysis: AI 분석 근거 dict.
            order_result: UPbit API 응답 원본.

        Returns:
            저장된 거래 레코드 dict (trade_id 포함).
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
        logger.info("거래 기록 저장: %s %s %s", action, symbol, trade_id)
        return record

    def update_outcome(self, trade_id: str, outcome: dict) -> bool:
        """사후 평가 업데이트.

        Args:
            trade_id: 대상 거래 ID.
            outcome: ``{price_after_24h, pnl_percent, was_correct}``

        Returns:
            업데이트 성공 여부.
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
                logger.info("사후 평가 완료: %s", trade_id)
                return True
        logger.warning("거래 ID를 찾을 수 없음: %s", trade_id)
        return False

    def get_pending_outcomes(self, min_hours: float = 24.0) -> list[dict]:
        """사후 평가 미완료 + 24h 이상 경과한 매매 목록.

        Args:
            min_hours: 최소 경과 시간 (기본 24시간).

        Returns:
            평가 대기 중인 거래 목록.
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
        """매매 기록 조회.

        Args:
            symbol: 심볼 필터.
            days: 최근 N일 필터.
            action: 행동 필터 (buy/sell/hold).

        Returns:
            필터된 거래 목록 (최신순).
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
        """통계 요약.

        Args:
            days: 최근 N일 기간.

        Returns:
            총 매매수, 승률, 평균 수익률, 최대 손실 등.
        """
        trades = self.get_trades(days=days)
        executed = [t for t in trades if t["action"] in ("buy", "sell")]
        evaluated = [
            t for t in executed
            if t.get("outcome", {}).get("was_correct") is not None
        ]
        pnls = [
            t["outcome"]["pnl_percent"]
            for t in evaluated
            if t["outcome"].get("pnl_percent") is not None
        ]

        total = len(executed)
        wins = sum(1 for t in evaluated if t["outcome"]["was_correct"])
        win_rate = wins / len(evaluated) if evaluated else 0.0
        avg_pnl = sum(pnls) / len(pnls) if pnls else 0.0
        max_loss = min(pnls) if pnls else 0.0
        max_gain = max(pnls) if pnls else 0.0

        return {
            "period_days": days,
            "total_trades": total,
            "evaluated_trades": len(evaluated),
            "pending_evaluation": total - len(evaluated),
            "wins": wins,
            "losses": len(evaluated) - wins,
            "win_rate": round(win_rate, 4),
            "avg_pnl_percent": round(avg_pnl, 4),
            "max_loss_percent": round(max_loss, 4),
            "max_gain_percent": round(max_gain, 4),
            "total_fee_krw": round(sum(t.get("fee", 0) for t in executed), 2),
        }

    def to_obsidian_note(self, trade: dict) -> str:
        """거래 기록을 Obsidian 마크다운 노트로 변환.

        Args:
            trade: 거래 레코드 dict.

        Returns:
            마크다운 문자열.
        """
        a = trade.get("analysis", {})
        o = trade.get("outcome", {})
        coin = trade["symbol"].replace("KRW-", "")

        lines = [
            "---",
            f"tags: [maiupbit, trade, {coin}, {trade['action']}]",
            f"date: {trade['date']}",
            f"symbol: {trade['symbol']}",
            f"action: {trade['action']}",
            f"confidence: {a.get('llm_confidence', 'N/A')}",
            f"pnl: {o.get('pnl_percent', 'null')}",
            "---",
            "",
            "## 매매 기록",
            f"- **종목:** {trade['symbol']}",
            f"- **행동:** {trade['action']}",
            f"- **수량:** {trade['volume']:,.0f}개 @ ₩{trade['price']:.6f}",
            f"- **총액:** ₩{trade['total_krw']:,.2f}",
            f"- **수수료:** ₩{trade['fee']:,.2f}",
            f"- **시각:** {trade['timestamp']}",
            "",
            "## AI 분석 근거",
            f"- **RSI:** {a.get('rsi', 'N/A')}",
            f"- **MACD:** {a.get('macd_signal', 'N/A')}",
            f"- **Stochastic K:** {a.get('stoch_k', 'N/A')}",
            f"- **퀀트 스코어:** {a.get('quant_score', 'N/A')}",
            f"- **LLM 판단:** {a.get('llm_decision', 'N/A')} "
            f"(confidence: {a.get('llm_confidence', 'N/A')})",
            f"- **이유:** {a.get('llm_reason', 'N/A')}",
            "",
            "## Mnemo 지식 참조",
            f"- 검색 결과: {a.get('knowledge_hits', 0)}건",
            f"- 요약: {a.get('knowledge_summary', '없음')}",
            "",
            "## 사후 평가",
        ]

        if o.get("evaluated_at"):
            lines.extend([
                f"- 24h 후 가격: ₩{o.get('price_after_24h', 'N/A')}",
                f"- 수익률: {o.get('pnl_percent', 'N/A')}%",
                f"- 판단 정확도: {'✅ 올바름' if o.get('was_correct') else '❌ 틀림'}",
                f"- 평가 시각: {o['evaluated_at']}",
            ])
        else:
            lines.extend([
                "- 24h 후 가격: (평가 대기)",
                "- 수익률: (평가 대기)",
                "- 판단 정확도: (평가 대기)",
            ])

        return "\n".join(lines) + "\n"
