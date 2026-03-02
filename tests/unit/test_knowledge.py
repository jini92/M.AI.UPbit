# -*- coding: utf-8 -*-
"""KnowledgeProvider tests."""

import json
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from maiupbit.analysis.knowledge import KnowledgeProvider, _COIN_KEYWORDS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def provider(tmp_path):
    """Test KnowledgeProvider (prevents actual Mnemo call)."""
    # Create fake script file
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    script = scripts_dir / "integrated_search.py"
    script.write_text("# dummy")
    return KnowledgeProvider(
        mnemo_path=str(tmp_path),
        vault_path=str(tmp_path / "vault"),
        memory_path=str(tmp_path / "memory"),
        enabled=True,
    )


@pytest.fixture
def disabled_provider(tmp_path):
    """Disabled KnowledgeProvider."""
    return KnowledgeProvider(
        mnemo_path=str(tmp_path),
        enabled=False,
    )


SAMPLE_RESULTS = [
    {
        "name": "Bitcoin Investment Strategy",
        "score": 8.5,
        "snippet": "BTC long-term investment DCA strategy is effective",
        "source": "vault",
        "path": "/vault/crypto/btc.md",
    },
    {
        "name": "Quant Investment Solution",
        "score": 7.2,
        "snippet": "ChatGPT-based quant investment portfolio",
        "source": "vault",
        "path": "/vault/daily/quant.md",
    },
]


# ---------------------------------------------------------------------------
# Tests: Initialization and Availability
# ---------------------------------------------------------------------------

class TestKnowledgeProviderInit:
    """Initialization and availability tests."""

    def test_default_enabled(self, provider):
        assert provider.enabled is True

    def test_disabled_provider(self, disabled_provider):
        assert disabled_provider.enabled is False
        assert disabled_provider.is_available() is False

    def test_is_available_with_script(self, provider):
        assert provider.is_available() is True

    def test_is_available_without_script(self, tmp_path):
        p = KnowledgeProvider(mnemo_path=str(tmp_path), enabled=True)
        assert p.is_available() is False

    def test_env_enabled(self, tmp_path):
        with patch.dict("os.environ", {"MNEMO_ENABLED": "false"}):
            p = KnowledgeProvider(mnemo_path=str(tmp_path))
            assert p.enabled is False

    def test_env_enabled_true(self, tmp_path):
        with patch.dict("os.environ", {"MNEMO_ENABLED": "true"}):
            p = KnowledgeProvider(mnemo_path=str(tmp_path))
            assert p.enabled is True


# ---------------------------------------------------------------------------
# Tests: Search
# ---------------------------------------------------------------------------

class TestSearch:
    """search() method tests."""

    def test_search_disabled(self, disabled_provider):
        results = disabled_provider.search("bitcoin")
        assert results == []

    def test_search_success(self, provider):
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(SAMPLE_RESULTS)
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            results = provider.search("비트코인 투자")

        assert len(results) == 2
        assert results[0]["name"] == "Bitcoin Investment Strategy"
        assert results[0]["score"] == 8.5

    def test_search_with_log_noise(self, provider):
        """Extract JSON even if stdout contains logs."""
        noisy_output = "Loading model...\nSome log\n" + json.dumps(SAMPLE_RESULTS)
        mock_result = MagicMock()
        mock_result.stdout = noisy_output

        with patch("subprocess.run", return_value=mock_result):
            results = provider.search("test")

        assert len(results) == 2

    def test_search_empty_stdout(self, provider):
        mock_result = MagicMock()
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            results = provider.search("test")

        assert results == []

    def test_search_timeout(self, provider):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
            results = provider.search("test", timeout=30)

        assert results == []

    def test_search_json_error(self, provider):
        mock_result = MagicMock()
        mock_result.stdout = "[invalid json"

        with patch("subprocess.run", return_value=mock_result):
            results = provider.search("test")

        assert results == []

    def test_search_exception(self, provider):
        with patch("subprocess.run", side_effect=OSError("no python")):
            results = provider.search("test")

        assert results == []


# ---------------------------------------------------------------------------
# Tests: Coin-specific search
# ---------------------------------------------------------------------------

class TestSearchForCoin:
    """search_for_coin() tests."""

    def test_btc_keywords(self, provider):
        with patch.object(provider, "search", return_value=SAMPLE_RESULTS) as mock:
            provider.search_for_coin("KRW-BTC")
            call_query = mock.call_args[0][0]
            assert "비트코인" in call_query

    def test_unknown_coin(self, provider):
        with patch.object(provider, "search", return_value=[]) as mock:
            provider.search_for_coin("KRW-UNKNOWN")
            call_query = mock.call_args[0][0]
            assert "UNKNOWN" in call_query

    def test_symbol_parsing(self, provider):
        with patch.object(provider, "search", return_value=[]) as mock:
            provider.search_for_coin("ETH")
            call_query = mock.call_args[0][0]
            assert "이더리움" in call_query


# ---------------------------------------------------------------------------
# Tests: Formatting
# ---------------------------------------------------------------------------

class TestFormatAsContext:
    """format_as_context() tests."""

    def test_empty_results(self, provider):
        assert provider.format_as_context([]) == ""

    def test_basic_format(self, provider):
        context = provider.format_as_context(SAMPLE_RESULTS)
        assert "Knowledge Context from Mnemo" in context
        assert "Bitcoin Investment Strategy" in context
        assert "Quant Investment Solution" in context

    def test_max_chars_limit(self, provider):
        context = provider.format_as_context(SAMPLE_RESULTS, max_chars=100)
        assert len(context) <= 200  # header + some content

    def test_includes_source_and_score(self, provider):
        context = provider.format_as_context(SAMPLE_RESULTS)
        assert "vault" in context
        assert "8.5" in context


# ---------------------------------------------------------------------------
# Tests: LLM Context Enrichment
# ---------------------------------------------------------------------------

class TestEnrichLLMContext:
    """enrich_llm_context() tests."""

    def test_disabled_returns_empty(self, disabled_provider):
        result = disabled_provider.enrich_llm_context("KRW-BTC")
        assert result == ""

    def test_with_results(self, provider):
        with patch.object(provider, "search_for_coin", return_value=SAMPLE_RESULTS):
            context = provider.enrich_llm_context("KRW-BTC")

        assert "Bitcoin Investment Strategy" in context
        assert "Knowledge Context" in context

    def test_no_results(self, provider):
        with patch.object(provider, "search_for_coin", return_value=[]):
            context = provider.enrich_llm_context("KRW-BTC")

        assert context == ""


# ---------------------------------------------------------------------------
# Tests: Market Context Search
# ---------------------------------------------------------------------------

class TestSearchMarketContext:
    """search_market_context() tests."""

    def test_deduplication(self, provider):
        with patch.object(provider, "search", return_value=SAMPLE_RESULTS):
            results = provider.search_market_context(top_k=5)

        # 2 queries × 2 results = 4, deduplicated to 2
        assert len(results) == 2

    def test_empty_results(self, provider):
        with patch.object(provider, "search", return_value=[]):
            results = provider.search_market_context()

        assert results == []


# ---------------------------------------------------------------------------
# Tests: COIN_KEYWORDS Mapping
# ---------------------------------------------------------------------------

class TestCoinKeywords:
    """_COIN_KEYWORDS mapping tests."""

    def test_btc_has_korean(self):
        assert "비트코인" in _COIN_KEYWORDS["BTC"]

    def test_eth_has_korean(self):
        assert "이더리움" in _COIN_KEYWORDS["ETH"]

    def test_all_coins_have_entries(self):
        for coin in ["BTC", "ETH", "XRP", "SOL", "DOGE"]:
            assert coin in _COIN_KEYWORDS
            assert len(_COIN_KEYWORDS[coin]) >= 2