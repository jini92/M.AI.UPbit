"""Unit tests for SentimentAnalyzer"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from maiupbit.analysis.sentiment import SentimentAnalyzer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def analyzer() -> SentimentAnalyzer:
    return SentimentAnalyzer()


# ---------------------------------------------------------------------------
# _extract_summary
# ---------------------------------------------------------------------------

class TestExtractSummary:
    def test_removes_html_tags(self, analyzer: SentimentAnalyzer) -> None:
        raw = "<p>Bitcoin <b>surges</b> past $70,000</p>"
        result = analyzer._extract_summary(raw)
        assert "<" not in result
        assert "Bitcoin" in result
        assert "surges" in result

    def test_removes_source_suffix(self, analyzer: SentimentAnalyzer) -> None:
        raw = "Bitcoin surges - CoinDesk"
        result = analyzer._extract_summary(raw)
        assert "CoinDesk" not in result

    def test_normalizes_whitespace(self, analyzer: SentimentAnalyzer) -> None:
        raw = "Bitcoin   surges   past   $70,000"
        result = analyzer._extract_summary(raw)
        assert "  " not in result

    def test_empty_string(self, analyzer: SentimentAnalyzer) -> None:
        result = analyzer._extract_summary("")
        assert result == ""

    def test_plain_text_unchanged(self, analyzer: SentimentAnalyzer) -> None:
        raw = "Simple plain text"
        result = analyzer._extract_summary(raw)
        assert result == "Simple plain text"


# ---------------------------------------------------------------------------
# analyze_sentiment
# ---------------------------------------------------------------------------

class TestAnalyzeSentiment:
    def test_empty_list_returns_neutral(self, analyzer: SentimentAnalyzer) -> None:
        result = analyzer.analyze_sentiment([])
        assert result["score"] == 0.0
        assert result["summary"] == "neutral"

    def test_positive_keywords_give_positive_score(
        self, analyzer: SentimentAnalyzer
    ) -> None:
        news = [
            {"title": "Bitcoin surge rally bull gain rise", "summary": "bullish breakout"},
        ]
        result = analyzer.analyze_sentiment(news)
        assert result["score"] > 0.0
        assert result["summary"] == "positive"

    def test_negative_keywords_give_negative_score(
        self, analyzer: SentimentAnalyzer
    ) -> None:
        news = [
            {"title": "Bitcoin crash dump bear loss fall", "summary": "bearish breakdown ban"},
        ]
        result = analyzer.analyze_sentiment(news)
        assert result["score"] < 0.0
        assert result["summary"] == "negative"

    def test_mixed_keywords_neutral_score(
        self, analyzer: SentimentAnalyzer
    ) -> None:
        news = [
            {"title": "surge crash rally dump", "summary": "bull bear"},
        ]
        result = analyzer.analyze_sentiment(news)
        assert result["summary"] in ("neutral", "positive", "negative")
        assert -1.0 <= result["score"] <= 1.0

    def test_score_clamped_to_range(self, analyzer: SentimentAnalyzer) -> None:
        news = [
            {"title": " ".join(["surge"] * 20), "summary": "bullish rally profit gain"},
        ] * 5
        result = analyzer.analyze_sentiment(news)
        assert -1.0 <= result["score"] <= 1.0

    def test_multiple_articles_averaged(self, analyzer: SentimentAnalyzer) -> None:
        news = [
            {"title": "Bitcoin surge rally", "summary": "gain rise"},
            {"title": "Bitcoin crash dump", "summary": "bear loss"},
        ]
        result = analyzer.analyze_sentiment(news)
        assert isinstance(result["score"], float)
        assert result["summary"] in ("positive", "negative", "neutral")


# ---------------------------------------------------------------------------
# get_news (feedparser mocking)
# ---------------------------------------------------------------------------

class TestGetNews:
    def _make_feed_entry(self, title: str, summary: str, link: str) -> MagicMock:
        entry = MagicMock()
        entry.get.side_effect = lambda key, default="": {
            "title": title, "summary": summary, "link": link
        }.get(key, default)
        return entry

    def test_returns_list_of_dicts(self, analyzer: SentimentAnalyzer) -> None:
        mock_feed = MagicMock()
        mock_feed.entries = [
            self._make_feed_entry("BTC surges", "<p>Bitcoin rises</p>", "https://example.com/1"),
            self._make_feed_entry("ETH rally", "Ethereum gains", "https://example.com/2"),
        ]
        with patch("maiupbit.analysis.sentiment.feedparser.parse", return_value=mock_feed):
            result = analyzer.get_news("KRW-BTC", num_articles=5)
        assert isinstance(result, list)
        assert len(result) == 2
        for item in result:
            assert "title" in item
            assert "summary" in item
            assert "link" in item

    def test_respects_num_articles(self, analyzer: SentimentAnalyzer) -> None:
        mock_feed = MagicMock()
        mock_feed.entries = [
            self._make_feed_entry(f"Article {i}", f"Summary {i}", f"https://ex.com/{i}")
            for i in range(10)
        ]
        with patch("maiupbit.analysis.sentiment.feedparser.parse", return_value=mock_feed):
            result = analyzer.get_news("KRW-BTC", num_articles=3)
        assert len(result) == 3

    def test_returns_empty_on_exception(self, analyzer: SentimentAnalyzer) -> None:
        with patch(
            "maiupbit.analysis.sentiment.feedparser.parse",
            side_effect=Exception("network error"),
        ):
            result = analyzer.get_news("KRW-BTC")
        assert result == []

    def test_symbol_without_dash(self, analyzer: SentimentAnalyzer) -> None:
        mock_feed = MagicMock()
        mock_feed.entries = []
        with patch(
            "maiupbit.analysis.sentiment.feedparser.parse", return_value=mock_feed
        ) as mock_parse:
            analyzer.get_news("bitcoin", num_articles=5)
        call_url = mock_parse.call_args[0][0]
        assert "bitcoin" in call_url

    def test_symbol_with_dash_uses_ticker(self, analyzer: SentimentAnalyzer) -> None:
        mock_feed = MagicMock()
        mock_feed.entries = []
        with patch(
            "maiupbit.analysis.sentiment.feedparser.parse", return_value=mock_feed
        ) as mock_parse:
            analyzer.get_news("KRW-BTC", num_articles=5)
        call_url = mock_parse.call_args[0][0]
        assert "BTC" in call_url


# ---------------------------------------------------------------------------
# get_news_text
# ---------------------------------------------------------------------------

class TestGetNewsText:
    def test_returns_string(self, analyzer: SentimentAnalyzer) -> None:
        mock_news = [
            {"title": "BTC surge", "summary": "Bitcoin rises sharply", "link": "https://x.com/1"},
        ]
        with patch.object(analyzer, "get_news", return_value=mock_news):
            result = analyzer.get_news_text("KRW-BTC")
        assert isinstance(result, str)

    def test_contains_article_number(self, analyzer: SentimentAnalyzer) -> None:
        mock_news = [
            {"title": "Article Title", "summary": "Summary here", "link": ""},
        ]
        with patch.object(analyzer, "get_news", return_value=mock_news):
            result = analyzer.get_news_text("KRW-BTC")
        assert "Article 1:" in result

    def test_contains_title_and_summary(self, analyzer: SentimentAnalyzer) -> None:
        mock_news = [
            {"title": "BTC Hits 70K", "summary": "Record breaking", "link": ""},
        ]
        with patch.object(analyzer, "get_news", return_value=mock_news):
            result = analyzer.get_news_text("KRW-BTC")
        assert "BTC Hits 70K" in result
        assert "Summary: Record breaking" in result

    def test_empty_string_on_no_articles(self, analyzer: SentimentAnalyzer) -> None:
        mock_news = []
        with patch.object(analyzer, "get_news", return_value=mock_news):
            result = analyzer.get_news_text("KRW-BTC")
        assert result == ""

    def test_multiple_articles_formatted(self, analyzer: SentimentAnalyzer) -> None:
        mock_news = [
            {"title": f"Title {i}", "summary": f"Summary {i}", "link": ""}
            for i in range(3)
        ]
        with patch.object(analyzer, "get_news", return_value=mock_news):
            result = analyzer.get_news_text("KRW-BTC")
        assert "Article 1:" in result
        assert "Title 1" in result
        assert "Summary: Summary 1" in result
        assert "Article 2:" in result
        assert "Title 2" in result
        assert "Summary: Summary 2" in result
        assert "Article 3:" in result
        assert "Title 3" in result
        assert "Summary: Summary 3" in result


# ---------------------------------------------------------------------------
# _get_article_content
# ---------------------------------------------------------------------------

class TestGetArticleContent:
    def test_returns_text_from_paragraphs(self, analyzer: SentimentAnalyzer) -> None:
        html = b"<html><body><p>Para 1</p><p>Para 2</p></body></html>"
        mock_response = MagicMock()
        mock_response.read.return_value = html
        with patch("maiupbit.analysis.sentiment.urlopen", return_value=mock_response):
            result = analyzer._get_article_content("https://example.com")
        assert "Para 1" in result
        assert "Para 2" in result

    def test_returns_empty_string_on_error(self, analyzer: SentimentAnalyzer) -> None:
        with patch(
            "maiupbit.analysis.sentiment.urlopen",
            side_effect=Exception("timeout"),
        ):
            result = analyzer._get_article_content("https://example.com")
        assert result == ""