"""Report generation utility module.

Provides the ReportGenerator class for saving analysis results and news text to PDF files.

Note:
    Works without Streamlit dependency.
    Requires the reportlab library.
"""

import io
import logging
import os
from typing import Any, Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

logger = logging.getLogger(__name__)


class ReportGenerator:
    """A report generator for saving trading analysis results to PDF.

    Example::

        gen = ReportGenerator()
        gen.generate_pdf(
            symbol="KRW-BTC",
            analysis_result=analysis,
            news_text=news,
            output_path="report_KRW-BTC.pdf",
        )
    """

    def generate_pdf(
        self,
        symbol: str,
        analysis_result: Dict[str, Any],
        news_text: str,
        output_path: str,
    ) -> str:
        """Saves a PDF report containing the analysis results and news text.

        Args:
            symbol: Trading symbol (e.g., "KRW-BTC").
            analysis_result: GPT-4 analysis result dict.
                Fields: recommendation, buy_price, sell_price, reason,
                        technical_analysis.key_indicators,
                        technical_analysis.chart_patterns,
                        market_sentiment,
                        risk_management.position_sizing,
                        risk_management.stop_loss,
                        risk_management.take_profit
            news_text: News article text (articles separated by '\\n\\n').
            output_path: Path to save the PDF file.

        Returns:
            Absolute path of the saved PDF file.

        Raises:
            RuntimeError: If PDF generation fails.
        """
        logger.info("Generating trading report... [%s]", symbol)

        # Safely extract analysis results
        recommendation = analysis_result.get("recommendation", "N/A")
        buy_price = analysis_result.get("buy_price", "N/A")
        sell_price = analysis_result.get("sell_price", "N/A")
        reason = analysis_result.get("reason", "N/A")

        tech = analysis_result.get("technical_analysis") or {}
        key_indicators = tech.get("key_indicators", "N/A")
        chart_patterns = tech.get("chart_patterns", "N/A")

        market_sentiment = analysis_result.get("market_sentiment", "N/A")

        risk = analysis_result.get("risk_management") or {}
        position_sizing = risk.get("position_sizing", "N/A")
        stop_loss = risk.get("stop_loss", "N/A")
        take_profit = risk.get("take_profit", "N/A")

        try:
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            elements = []
            styles = getSampleStyleSheet()

            # --- Title ---
            title_style = styles["Heading1"]
            title_style.fontSize = 24
            title_style.leading = 30
            elements.append(Paragraph(f"Trading Report - {symbol}", title_style))
            elements.append(Spacer(1, 24))

            # --- News Section ---
            news_title_style = styles["Heading2"]
            news_title_style.fontSize = 16
            news_title_style.leading = 24
            elements.append(Paragraph(f"Coin News - {symbol}", news_title_style))
            elements.append(Spacer(1, 12))

            for article in news_text.split("\n\n"):
                stripped = article.strip()
                if stripped:
                    elements.append(Paragraph(stripped, styles["Normal"]))
                    elements.append(Spacer(1, 12))

            elements.append(Spacer(1, 24))

            # --- Analysis Results Section ---
            analysis_style = styles["Normal"]
            analysis_style.fontSize = 12
            analysis_style.leading = 20

            analysis_html = (
                f"<b>Recommendation:</b> {recommendation}<br/>"
                f"<b>Buy Price:</b> {buy_price}<br/>"
                f"<b>Sell Price:</b> {sell_price}<br/>"
                f"<b>Reason:</b> {reason}<br/>"
                f"<b>Key Indicators:</b> {key_indicators}<br/>"
                f"<b>Chart Patterns:</b> {chart_patterns}<br/>"
                f"<b>Market Sentiment:</b> {market_sentiment}<br/>"
                f"<b>Position Sizing:</b> {position_sizing}<br/>"
                f"<b>Stop Loss:</b> {stop_loss}<br/>"
                f"<b>Take Profit:</b> {take_profit}"
            )
            elements.append(Paragraph(analysis_html, analysis_style))

            # --- PDF Build and File Save ---
            doc.build(elements)

            abs_path = os.path.abspath(output_path)
            with open(abs_path, "wb") as f:
                f.write(buffer.getvalue())

            logger.info("Report saved: %s", abs_path)
            return abs_path

        except Exception as exc:
            logger.error("Failed to generate report: %s", exc)
            raise RuntimeError(f"PDF generation failed: {exc}") from exc