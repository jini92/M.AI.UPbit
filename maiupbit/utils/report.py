"""리포트 생성 유틸리티 모듈.

분석 결과와 뉴스 텍스트를 받아 PDF 파일로 저장하는
ReportGenerator 클래스를 제공합니다.

Note:
    Streamlit 의존성 없이 동작합니다.
    reportlab 라이브러리가 필요합니다.
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
    """트레이딩 분석 결과를 PDF로 저장하는 리포트 생성기.

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
        """분석 결과와 뉴스를 포함한 PDF 리포트를 파일로 저장합니다.

        Args:
            symbol: 거래 심볼 (예: "KRW-BTC").
            analysis_result: GPT-4 분석 결과 dict.
                필드: recommendation, buy_price, sell_price, reason,
                      technical_analysis.key_indicators,
                      technical_analysis.chart_patterns,
                      market_sentiment,
                      risk_management.position_sizing,
                      risk_management.stop_loss,
                      risk_management.take_profit
            news_text: 뉴스 기사 텍스트 (기사 간 '\\n\\n' 구분).
            output_path: 저장할 PDF 파일 경로.

        Returns:
            저장된 PDF 파일의 절대 경로.

        Raises:
            RuntimeError: PDF 생성에 실패한 경우.
        """
        logger.info("트레이딩 리포트 생성 중... [%s]", symbol)

        # 분석 결과 안전 추출
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

            # --- 제목 ---
            title_style = styles["Heading1"]
            title_style.fontSize = 24
            title_style.leading = 30
            elements.append(Paragraph(f"Trading Report - {symbol}", title_style))
            elements.append(Spacer(1, 24))

            # --- 뉴스 섹션 ---
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

            # --- 분석 결과 섹션 ---
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

            # --- PDF 빌드 및 파일 저장 ---
            doc.build(elements)

            abs_path = os.path.abspath(output_path)
            with open(abs_path, "wb") as f:
                f.write(buffer.getvalue())

            logger.info("리포트 저장 완료: %s", abs_path)
            return abs_path

        except Exception as exc:
            logger.error("리포트 생성 실패: %s", exc)
            raise RuntimeError(f"PDF 생성 실패: {exc}") from exc
