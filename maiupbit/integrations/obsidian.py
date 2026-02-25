# -*- coding: utf-8 -*-
"""maiupbit.integrations.obsidian — Obsidian 볼트 동기화.

거래 기록을 Obsidian 마크다운 노트로 자동 생성.
Mnemo daily_enrich가 이 노트를 파싱하여 지식그래프에 축적.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from maiupbit.trading.journal import TradeJournal

logger = logging.getLogger(__name__)

_DEFAULT_VAULT = os.getenv(
    "MNEMO_VAULT_PATH", r"C:\Users\jini9\OneDrive\Documents\JINI_SYNC"
)
_DEFAULT_PROJECT = "01.PROJECT/16.M.AI.UPbit"


class ObsidianSync:
    """Obsidian 볼트에 거래 노트 동기화.

    Attributes:
        vault_path: Obsidian 볼트 루트 경로.
        trades_dir: 거래 노트 저장 디렉토리.
        reports_dir: 리포트 저장 디렉토리.
    """

    def __init__(
        self,
        vault_path: Optional[str] = None,
        project_folder: str = _DEFAULT_PROJECT,
    ) -> None:
        self.vault_path = Path(vault_path or _DEFAULT_VAULT)
        self.trades_dir = self.vault_path / project_folder / "trades"
        self.reports_dir = self.vault_path / project_folder / "reports"

    def sync_trade(self, trade: dict, journal: TradeJournal) -> Optional[Path]:
        """단일 거래를 Obsidian 노트로 저장.

        Args:
            trade: 거래 레코드 dict.
            journal: TradeJournal 인스턴스 (노트 생성용).

        Returns:
            생성된 노트 경로 또는 None.
        """
        self.trades_dir.mkdir(parents=True, exist_ok=True)

        note_content = journal.to_obsidian_note(trade)
        filename = f"{trade['trade_id']}.md"
        note_path = self.trades_dir / filename

        try:
            note_path.write_text(note_content, encoding="utf-8")
            logger.info("Obsidian 노트 생성: %s", note_path.name)
            return note_path
        except OSError as exc:
            logger.error("노트 생성 실패: %s", exc)
            return None

    def sync_daily_trades(
        self, trades: list[dict], journal: TradeJournal
    ) -> list[Path]:
        """여러 거래를 Obsidian 노트로 동기화.

        Args:
            trades: 거래 레코드 목록.
            journal: TradeJournal 인스턴스.

        Returns:
            생성된 노트 경로 목록.
        """
        paths = []
        for trade in trades:
            path = self.sync_trade(trade, journal)
            if path:
                paths.append(path)
        return paths

    def update_outcome_note(self, trade: dict, journal: TradeJournal) -> bool:
        """사후 평가 결과를 기존 노트에 업데이트.

        기존 노트를 새 내용으로 덮어쓰기 (사후 평가 섹션 포함).

        Args:
            trade: 사후 평가가 완료된 거래 레코드.
            journal: TradeJournal 인스턴스.

        Returns:
            업데이트 성공 여부.
        """
        filename = f"{trade['trade_id']}.md"
        note_path = self.trades_dir / filename

        if not note_path.exists():
            logger.warning("업데이트할 노트 없음: %s", filename)
            return False

        note_content = journal.to_obsidian_note(trade)
        try:
            note_path.write_text(note_content, encoding="utf-8")
            logger.info("Obsidian 노트 사후 평가 업데이트: %s", filename)
            return True
        except OSError as exc:
            logger.error("노트 업데이트 실패: %s", exc)
            return False

    def generate_weekly_report(
        self, stats: dict, trades: list[dict], week_label: Optional[str] = None
    ) -> Optional[Path]:
        """주간 성과 리포트 노트 생성.

        Args:
            stats: TradeJournal.get_stats() 결과.
            trades: 해당 주 거래 목록.
            week_label: 주 라벨 (예: "2026-W09"). None이면 자동 생성.

        Returns:
            생성된 리포트 경로 또는 None.
        """
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        if not week_label:
            now = datetime.now()
            week_label = f"{now.year}-W{now.isocalendar()[1]:02d}"

        lines = [
            "---",
            f"tags: [maiupbit, report, weekly]",
            f"date: {datetime.now().strftime('%Y-%m-%d')}",
            f"week: {week_label}",
            "---",
            "",
            f"# M.AI.UPbit 주간 리포트 — {week_label}",
            "",
            "## 성과 요약",
            "",
            f"| 지표 | 값 |",
            f"|------|-----|",
            f"| 총 매매 | {stats.get('total_trades', 0)}건 |",
            f"| 평가 완료 | {stats.get('evaluated_trades', 0)}건 |",
            f"| 승률 | {stats.get('win_rate', 0) * 100:.1f}% |",
            f"| 평균 수익률 | {stats.get('avg_pnl_percent', 0):.2f}% |",
            f"| 최대 수익 | {stats.get('max_gain_percent', 0):.2f}% |",
            f"| 최대 손실 | {stats.get('max_loss_percent', 0):.2f}% |",
            f"| 총 수수료 | ₩{stats.get('total_fee_krw', 0):,.2f} |",
            "",
            "## 매매 목록",
            "",
            "| 시각 | 종목 | 행동 | 금액 | 결과 |",
            "|------|------|------|------|------|",
        ]

        for t in trades:
            outcome = t.get("outcome", {})
            result_str = ""
            if outcome.get("was_correct") is True:
                result_str = f"✅ {outcome.get('pnl_percent', 0):.2f}%"
            elif outcome.get("was_correct") is False:
                result_str = f"❌ {outcome.get('pnl_percent', 0):.2f}%"
            else:
                result_str = "⏳ 대기"

            ts = t.get("timestamp", "")[:16]
            lines.append(
                f"| {ts} | {t['symbol']} | {t['action']} "
                f"| ₩{t.get('total_krw', 0):,.0f} | {result_str} |"
            )

        lines.extend([
            "",
            "## AI 분석 정확도 추이",
            "",
            f"이번 주 승률: **{stats.get('win_rate', 0) * 100:.1f}%**",
            "",
            "---",
            f"_Generated by M.AI.UPbit AutoTrader_",
        ])

        report_path = self.reports_dir / f"{week_label}.md"
        try:
            report_path.write_text("\n".join(lines), encoding="utf-8")
            logger.info("주간 리포트 생성: %s", report_path.name)
            return report_path
        except OSError as exc:
            logger.error("리포트 생성 실패: %s", exc)
            return None
