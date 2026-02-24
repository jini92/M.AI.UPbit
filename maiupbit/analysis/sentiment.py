# -*- coding: utf-8 -*-
"""
maiupbit.analysis.sentiment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

뉴스 수집 및 감성 분석 모듈.

Google News RSS 피드를 통해 코인 관련 뉴스를 수집하고
텍스트 기반의 간단한 감성 점수를 계산합니다.

사용 예::

    analyzer = SentimentAnalyzer()
    news_list = analyzer.get_news("KRW-BTC", num_articles=5)
    sentiment = analyzer.analyze_sentiment(news_list)
    news_text = analyzer.get_news_text("KRW-BTC")
"""

from __future__ import annotations

import logging
import re
from typing import Optional

import feedparser
from bs4 import BeautifulSoup
from urllib.request import urlopen

logger = logging.getLogger(__name__)

# 긍정/부정 키워드 (영문 기준 — 필요 시 확장 가능)
_POSITIVE_KEYWORDS: frozenset[str] = frozenset(
    [
        "surge", "rally", "bull", "gain", "rise", "up", "high", "growth",
        "positive", "profit", "adoption", "bullish", "breakout", "support",
        "partnership", "launch", "upgrade", "soar", "record", "all-time",
    ]
)
_NEGATIVE_KEYWORDS: frozenset[str] = frozenset(
    [
        "crash", "dump", "bear", "loss", "fall", "down", "low", "decline",
        "negative", "hack", "ban", "sell-off", "bearish", "breakdown", "risk",
        "fraud", "scam", "lawsuit", "regulation", "fud", "drop", "plunge",
    ]
)


class SentimentAnalyzer:
    """뉴스 수집 및 감성 분석 엔진.

    Google News RSS 피드를 파싱하여 코인 관련 뉴스를 수집하고,
    키워드 기반의 단순 감성 점수를 계산합니다.
    """

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _extract_summary(self, raw_summary: str) -> str:
        """HTML 태그 및 불필요한 문자열을 제거하여 깨끗한 요약문 반환.

        Args:
            raw_summary: feedparser entry 의 원본 summary 문자열.

        Returns:
            정제된 요약 텍스트.
        """
        # HTML 태그 제거
        text = re.sub(r"<[^<]+?>", "", raw_summary)
        # " - 출처명" 형식 제거
        text = re.sub(r"\s-\s.*$", "", text)
        # 다중 공백 정규화
        text = re.sub(r"\s{2,}", " ", text)
        return text.strip()

    def _get_article_content(self, url: str) -> str:
        """URL 에서 기사 본문을 추출.

        Args:
            url: 기사 페이지 URL.

        Returns:
            ``<p>`` 태그를 이어붙인 기사 본문 문자열.
            오류 발생 시 빈 문자열 반환.
        """
        try:
            html = urlopen(url, timeout=10).read()
            soup = BeautifulSoup(html, "html.parser")
            paragraphs = [p.get_text() for p in soup.find_all("p")]
            return "\n".join(paragraphs)
        except Exception as exc:  # noqa: BLE001
            logger.debug("기사 본문 추출 실패 (%s): %s", url, exc)
            return ""

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------

    def get_news(
        self,
        symbol: str,
        num_articles: int = 5,
    ) -> list[dict]:
        """Google News RSS 에서 코인 관련 뉴스를 수집.

        Args:
            symbol: 거래 심볼 또는 코인명. 예: ``"KRW-BTC"``, ``"bitcoin"``.
                KRW-XXX 형식인 경우 'XXX' 부분을 검색어로 사용합니다.
            num_articles: 수집할 최대 기사 수. 기본값 5.

        Returns:
            뉴스 항목 리스트. 각 항목::

                {
                    'title': str,    # 기사 제목
                    'summary': str,  # 정제된 요약
                    'link': str,     # 원문 URL
                }

            수집 실패 시 빈 리스트 반환.
        """
        # 심볼에서 코인 티커 추출 (예: "KRW-BTC" → "BTC")
        query_term = symbol.split("-")[-1] if "-" in symbol else symbol

        rss_url = (
            f"https://news.google.com/rss/search"
            f"?q={query_term}+crypto&hl=en-US&gl=US&ceid=US:en"
        )

        try:
            feed = feedparser.parse(rss_url)
        except Exception as exc:  # noqa: BLE001
            logger.error("뉴스 피드 파싱 실패: %s", exc)
            return []

        news_list: list[dict] = []
        for entry in feed.entries[:num_articles]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            raw_summary = entry.get("summary", "")
            summary = self._extract_summary(raw_summary)

            news_list.append(
                {
                    "title": title,
                    "summary": summary,
                    "link": link,
                }
            )

        logger.info(
            "get_news('%s'): %d개 기사 수집 완료",
            symbol,
            len(news_list),
        )
        return news_list

    def analyze_sentiment(self, news_list: list[dict]) -> dict:
        """수집된 뉴스 목록에 대한 감성 점수 계산.

        제목과 요약문의 키워드를 분석하여 -1.0 ~ 1.0 범위의
        감성 점수를 반환합니다.

        Args:
            news_list: :meth:`get_news` 의 반환값.

        Returns:
            감성 분석 결과::

                {
                    'score': float,   # -1.0 (매우 부정) ~ 1.0 (매우 긍정)
                    'summary': str,   # 감성 레이블 ('positive' | 'negative' | 'neutral')
                }
        """
        if not news_list:
            return {"score": 0.0, "summary": "neutral"}

        total_score = 0.0
        for item in news_list:
            combined_text = (
                (item.get("title", "") + " " + item.get("summary", "")).lower()
            )

            pos_count = sum(1 for kw in _POSITIVE_KEYWORDS if kw in combined_text)
            neg_count = sum(1 for kw in _NEGATIVE_KEYWORDS if kw in combined_text)

            article_score = (pos_count - neg_count) / max(pos_count + neg_count, 1)
            total_score += article_score

        avg_score = total_score / len(news_list)
        # -1.0 ~ 1.0 클리핑
        avg_score = max(-1.0, min(1.0, avg_score))

        if avg_score > 0.1:
            label = "positive"
        elif avg_score < -0.1:
            label = "negative"
        else:
            label = "neutral"

        logger.info(
            "analyze_sentiment: score=%.3f, label=%s (%d articles)",
            avg_score,
            label,
            len(news_list),
        )
        return {"score": avg_score, "summary": label}

    def get_news_text(
        self,
        symbol: str,
        num_articles: int = 5,
    ) -> str:
        """LLM 입력용 뉴스 텍스트 블록을 반환.

        Args:
            symbol: 거래 심볼 또는 코인명. 예: ``"KRW-BTC"``.
            num_articles: 수집할 최대 기사 수. 기본값 5.

        Returns:
            번호가 매겨진 뉴스 텍스트 문자열.
            수집된 기사가 없으면 빈 문자열 반환.

        Example::

            Article 1:

            Title: Bitcoin surges past $70,000

            Summary: Bitcoin hit a new record high on Tuesday...

            Article 2:
            ...
        """
        news_list = self.get_news(symbol, num_articles=num_articles)
        if not news_list:
            return ""

        lines: list[str] = []
        for i, item in enumerate(news_list, start=1):
            lines.append(f"Article {i}:")
            lines.append("")
            lines.append(f"Title: {item['title']}")
            lines.append("")
            lines.append(f"Summary: {item['summary']}")
            lines.append("")
            lines.append("")  # 기사 간 구분 빈 줄

        return "\n".join(lines)
