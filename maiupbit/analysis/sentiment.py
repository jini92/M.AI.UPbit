# -*- coding: utf-8 -*-
"""
maiupbit.analysis.sentiment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

News collection and sentiment analysis module.

Collects coin-related news from Google News RSS feed and calculates a simple text-based sentiment score.

Usage example::

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

# Positive/Negative keywords (English based — expandable as needed)
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
    """News collection and sentiment analysis engine.

    Parses Google News RSS feed to collect coin-related news,
    and calculates a simple keyword-based sentiment score.
    """

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_summary(self, raw_summary: str) -> str:
        """Removes HTML tags and unnecessary strings to return a clean summary.

        Args:
            raw_summary: Original summary string from feedparser entry.

        Returns:
            Cleaned summary text.
        """
        # Remove HTML tags
        text = re.sub(r"<[^<]+?>", "", raw_summary)
        # Remove " - Source Name" format
        text = re.sub(r"\s-\s.*$", "", text)
        # Normalize multiple spaces
        text = re.sub(r"\s{2,}", " ", text)
        return text.strip()

    def _get_article_content(self, url: str) -> str:
        """Extract article content from URL.

        Args:
            url: Article page URL.

        Returns:
            String of concatenated ``<p>`` tags for the article body.
            Returns an empty string if an error occurs.
        """
        try:
            html = urlopen(url, timeout=10).read()
            soup = BeautifulSoup(html, "html.parser")
            paragraphs = [p.get_text() for p in soup.find_all("p")]
            return "\n".join(paragraphs)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to extract article content (%s): %s", url, exc)
            return ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_news(
        self,
        symbol: str,
        num_articles: int = 5,
    ) -> list[dict]:
        """Collects coin-related news from Google News RSS.

        Args:
            symbol: Trading symbol or coin name. Example: ``"KRW-BTC"``, ``"bitcoin"``.
                If in KRW-XXX format, the 'XXX' part is used as a search term.
            num_articles: Maximum number of articles to collect. Default 5.

        Returns:
            List of news items. Each item::
            
                {
                    'title': str,    # Article title
                    'summary': str,  # Cleaned summary
                    'link': str,     # Original URL
                }

            Returns an empty list if collection fails.
        """
        # Extract coin ticker from symbol (e.g., "KRW-BTC" → "BTC")
        query_term = symbol.split("-")[-1] if "-" in symbol else symbol

        rss_url = (
            f"https://news.google.com/rss/search"
            f"?q={query_term}+crypto&hl=en-US&gl=US&ceid=US:en"
        )

        try:
            feed = feedparser.parse(rss_url)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to parse news feed: %s", exc)
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
            "get_news('%s'): %d articles collected",
            symbol,
            len(news_list),
        )
        return news_list

    def analyze_sentiment(self, news_list: list[dict]) -> dict:
        """Calculates sentiment score for the collected news list.

        Analyzes keywords in titles and summaries to return a sentiment score
        within the range of -1.0 (very negative) to 1.0 (very positive).

        Args:
            news_list: Return value from :meth:`get_news`.

        Returns:
            Sentiment analysis result::
            
                {
                    'score': float,   # -1.0 (very negative) ~ 1.0 (very positive)
                    'summary': str,   # Sentiment label ('positive' | 'negative' | 'neutral')
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
        # Clip to -1.0 ~ 1.0
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
        """Returns a news text block for LLM input.

        Args:
            symbol: Trading symbol or coin name. Example: ``"KRW-BTC"``.
            num_articles: Maximum number of articles to collect. Default 5.

        Returns:
            Numbered news text string.
            Returns an empty string if no articles are collected.

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
            lines.append("")  # Blank line between articles

        return "\n".join(lines)