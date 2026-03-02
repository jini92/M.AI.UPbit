# -*- coding: utf-8 -*-
"""maiupbit.integrations.obsidian — Synchronize trading records to Obsidian bolt.

Automatically generate trading records in Obsidian markdown notes.
Mnemo daily_enrich parses these notes and accumulates them into a knowledge graph.
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
    """Synchronize trading notes to the Obsidian bolt.

    Attributes:
        vault_path: Root path of the Obsidian vault.
        trades_dir: Directory for storing trade notes.
        reports_dir: Directory for storing report files.
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
        """Save a single trade record as an Obsidian note.

        Args:
            trade: Dictionary containing the trade record.
            journal: TradeJournal instance for creating notes.

        Returns:
            Path to the created note or None.
        """
        self.trades_dir.mkdir(parents=True, exist_ok=True)

        note_content = journal.to_obsidian_note(trade)
        filename = f"{trade['trade_id']}.md"
        note_path = self.trades_dir / filename

        try:
            note_path.write_text(note_content, encoding="utf-8")
            logger.info("Obsidian note created: %s", note_path.name)
            return note_path
        except OSError as exc:
            logger.error("Failed to create note: %s", exc)
            return None

    def sync_daily_trades(
        self, trades: list[dict], journal: TradeJournal
    ) -> list[Path]:
        """Synchronize multiple trade records to Obsidian notes.

        Args:
            trades: List of trade record dictionaries.
            journal: TradeJournal instance for creating notes.

        Returns:
            Paths to the created notes.
        """
        paths = []
        for trade in trades:
            path = self.sync_trade(trade, journal)
            if path:
                paths.append(path)
        return paths

    def update_outcome_note(self, trade: dict, journal: TradeJournal) -> bool:
        """Update a post-trade evaluation result to an existing note.

        Overwrite the existing note with new content (including the post-evaluation section).

        Args:
            trade: Dictionary containing the completed trade record.
            journal: TradeJournal instance for creating notes.

        Returns:
            True if update is successful, False otherwise.
        """
        filename = f"{trade['trade_id']}.md"
        note_path = self.trades_dir / filename

        if not note_path.exists():
            logger.warning("No note to update: %s", filename)
            return False

        note_content = journal.to_obsidian_note(trade)
        try:
            note_path.write_text(note_content, encoding="utf-8")
            logger.info("Obsidian note post-evaluation updated: %s", filename)
            return True
        except OSError as exc:
            logger.error("Failed to update note: %s", exc)
            return False

    def generate_weekly_report(
        self, stats: dict, trades: list[dict], week_label: Optional[str] = None
    ) -> Optional[Path]:
        """Generate a weekly performance report note.

        Args:
            stats: Dictionary containing the results of TradeJournal.get_stats().
            trades: List of trades for the given week.
            week_label: Label for the week (e.g., "2026-W09"). If None, auto-generated.

        Returns:
            Path to the created report or None.
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
            f"# M.AI.UPbit Weekly Report — {week_label}",
            "",
            "## Performance Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Trades | {stats.get('total_trades', 0)} |",
            f"| Evaluated Trades | {stats.get('evaluated_trades', 0)} |",
            f"| Win Rate | {stats.get('win_rate', 0) * 100:.1f}% |",
            f"| Average PNL | {stats.get('avg_pnl_percent', 0):.2f}% |",
            f"| Max Gain | {stats.get('max_gain_percent', 0):.2f}% |",
            f"| Max Loss | {stats.get('max_loss_percent', 0):.2f}% |",
            f"| Total Fees | ₩{stats.get('total_fee_krw', 0):,.2f} |",
            "",
            "## Trade List",
            "",
            "| Timestamp | Symbol | Action | Amount | Result |",
            "|-----------|--------|--------|--------|--------|",
        ]

        for t in trades:
            outcome = t.get("outcome", {})
            result_str = ""
            if outcome.get("was_correct") is True:
                result_str = f"✅ {outcome.get('pnl_percent', 0):.2f}%"
            elif outcome.get("was_correct") is False:
                result_str = f"❌ {outcome.get('pnl_percent', 0):.2f}%"
            else:
                result_str = "⏳ Pending"

            ts = t.get("timestamp", "")[:16]
            lines.append(
                f"| {ts} | {t['symbol']} | {t['action']} "
                f"| ₩{t.get('total_krw', 0):,.0f} | {result_str} |"
            )

        lines.extend([
            "",
            "## AI Analysis Accuracy Trend",
            "",
            f"This week's win rate: **{stats.get('win_rate', 0) * 100:.1f}%**",
            "",
            "---",
            f"_Generated by M.AI.UPbit AutoTrader_",
        ])

        report_path = self.reports_dir / f"{week_label}.md"
        try:
            report_path.write_text("\n".join(lines), encoding="utf-8")
            logger.info("Weekly report generated: %s", report_path.name)
            return report_path
        except OSError as exc:
            logger.error("Failed to generate report: %s", exc)
            return None