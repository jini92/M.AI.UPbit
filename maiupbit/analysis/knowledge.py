# -*- coding: utf-8 -*-
"""
maiupbit.analysis.knowledge
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Mnemo(MAISECONDBRAIN) knowledge graph integration module.

Searches for investment-related knowledge from Obsidian bolt + MAIBOT memory to enhance LLM analysis context.

Graceful degradation if Mnemo is not installed or search fails: returns empty results without affecting existing analysis pipelines.

Usage example::

    provider = KnowledgeProvider()
    context = provider.search("Bitcoin market outlook")
    enriched = provider.enrich_llm_context("BTC analysis data...", "KRW-BTC")

Environment variables::

    MNEMO_VAULT_PATH   - Obsidian bolt path (required)
    MNEMO_MEMORY_PATH  - MAIBOT memory path (required)
    MNEMO_CACHE_DIR    - Mnemo cache directory (default: .mnemo)
    MNEMO_USE_RERANKER - Use re-ranker (default: true)
    MNEMO_ENABLED      - Knowledge search activation (default: true)
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Mnemo project path
_DEFAULT_MNEMO_PATH = r"C:\TEST\MAISECONDBRAIN"
_DEFAULT_VAULT_PATH = r"C:\Users\jini9\OneDrive\Documents\JINI_SYNC"
_DEFAULT_MEMORY_PATH = r"C:\MAIBOT\memory"

# Investment/market related search term expansion mapping
_COIN_KEYWORDS: dict[str, list[str]] = {
    "BTC": ["Bitcoin", "bitcoin", "BTC", "cryptocurrency", "digital asset"],
    "ETH": ["Ethereum", "ethereum", "ETH", "smart contract"],
    "XRP": ["Ripple", "ripple", "XRP"],
    "SOL": ["Solana", "solana", "SOL"],
    "DOGE": ["Dogecoin", "dogecoin", "DOGE"],
}

# Default investment-related search queries
_DEFAULT_QUERIES: list[str] = [
    "cryptocurrency market outlook investment strategy",
    "quantitative trading momentum volatility",
]


class KnowledgeProvider:
    """Mnemo knowledge graph search wrapper.

    Calls integrated_search.py from MAISECONDBRAIN as a subprocess to search for related knowledge in Obsidian bolt + MAIBOT memory.

    Attributes:
        enabled: Whether knowledge search is activated.
        mnemo_path: Path to the MAISECONDBRAIN project.
    """

    def __init__(
        self,
        mnemo_path: Optional[str] = None,
        vault_path: Optional[str] = None,
        memory_path: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        """Initialize KnowledgeProvider.

        Args:
            mnemo_path: Path to the MAISECONDBRAIN project. Uses default if None.
            vault_path: Obsidian bolt path. Uses environment variable or default if None.
            memory_path: MAIBOT memory path. Uses environment variable or default if None.
            enabled: Activation status. Uses MNEMO_ENABLED environment variable (default true) if None.
        """
        self.mnemo_path = Path(mnemo_path or _DEFAULT_MNEMO_PATH)
        self.vault_path = vault_path or os.getenv("MNEMO_VAULT_PATH", _DEFAULT_VAULT_PATH)
        self.memory_path = memory_path or os.getenv("MNEMO_MEMORY_PATH", _DEFAULT_MEMORY_PATH)

        if enabled is not None:
            self.enabled = enabled
        else:
            self.enabled = os.getenv("MNEMO_ENABLED", "true").lower() in ("true", "1", "yes")

        self._search_script = self.mnemo_path / "scripts" / "integrated_search.py"

    def is_available(self) -> bool:
        """Check if Mnemo search is available.

        Returns:
            True if available.
        """
        if not self.enabled:
            return False
        return self._search_script.exists()

    def search(
        self,
        query: str,
        top_k: int = 5,
        timeout: int = 30,
    ) -> list[dict]:
        """Search Mnemo knowledge graph.

        Args:
            query: Search query.
            top_k: Maximum number of results to return.
            timeout: Search timeout (seconds).

        Returns:
            List of search results. Each item::
                {
                    'name': str,       # Document name
                    'score': float,    # Relevance score
                    'snippet': str,    # Document snippet
                    'source': str,     # 'vault' or 'memory'
                    'path': str,       # File path
                }

            Returns an empty list if search fails.
        """
        if not self.is_available():
            logger.debug("Mnemo knowledge search is disabled or not installed")
            return []

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["MNEMO_VAULT_PATH"] = self.vault_path
        env["MNEMO_MEMORY_PATH"] = self.memory_path
        env["MNEMO_CACHE_DIR"] = os.getenv("MNEMO_CACHE_DIR", ".mnemo")
        env["MNEMO_USE_RERANKER"] = os.getenv("MNEMO_USE_RERANKER", "true")

        cmd = [
            "python",
            str(self._search_script),
            query,
            "--top-k", str(top_k),
            "--format", "json",
        ]

        results = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        if results.returncode != 0:
            logger.error("Mnemo search failed: %s", results.stderr.decode())
            return []

        try:
            json_results = json.loads(results.stdout)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON from Mnemo search output: %s", str(e))
            return []

        return json_results

    def search_for_coin(
        self,
        symbol: str,
        top_k: int = 5,
        timeout: int = 30,
    ) -> list[dict]:
        """Search for coin-related knowledge.

        Args:
            symbol: Trading symbol. Example: "KRW-BTC".
            top_k: Number of results to return.
            timeout: Search timeout (seconds).

        Returns:
            List of search results.
        """
        ticker = _COIN_KEYWORDS.get(symbol, [symbol])[:3]
        query = f"{' '.join(ticker)} market outlook investment"
        return self.search(query, top_k=top_k, timeout=timeout)

    def search_market_context(
        self,
        top_k: int = 3,
        timeout: int = 30,
    ) -> list[dict]:
        """Search for general market context.

        Args:
            top_k: Number of results to return.
            timeout: Search timeout (seconds).

        Returns:
            List of search results.
        """
        all_results = []
        for query in _DEFAULT_QUERIES:
            results = self.search(query, top_k=top_k, timeout=timeout)
            all_results.extend(results)

        # Remove duplicates based on name
        seen = set()
        unique = []
        for r in all_results:
            name = r.get("name", "")
            if name not in seen:
                seen.add(name)
                unique.append(r)

        return unique[:top_k]

    def format_as_context(
        self,
        results: list[dict],
        max_chars: int = 2000,
    ) -> str:
        """Format search results as an LLM context string.

        Args:
            results: Results from the search().
            max_chars: Maximum number of characters.

        Returns:
            Context string to inject into the LLM prompt.
            Returns an empty string if no results are found.
        """
        if not results:
            return ""

        lines = ["[Knowledge Context from Mnemo SecondBrain]"]
        total_chars = 0

        for i, r in enumerate(results, 1):
            name = r.get("name", "unknown")
            snippet = r.get("snippet", "")
            source = r.get("source", "unknown")
            score = r.get("score", 0)

            entry = (
                f"\n--- Knowledge #{i} (source: {source}, relevance: {score:.1f}) ---\n"
                f"Title: {name}\n"
                f"{snippet}\n"
            )

            if total_chars + len(entry) > max_chars:
                remaining = max_chars - total_chars
                if remaining > 100:
                    lines.append(entry[:remaining] + "...")
                break

            lines.append(entry)
            total_chars += len(entry)

        return "\n".join(lines)

    def enrich_llm_context(
        self,
        symbol: str,
        existing_news: str = "",
        top_k: int = 3,
        timeout: int = 30,
    ) -> str:
        """Generate knowledge context for LLM analysis.

        Combines coin-related knowledge and general market knowledge to create a context string to inject into the LLM prompt.

        Args:
            symbol: Trading symbol. Example: "KRW-BTC".
            existing_news: Existing news text (to avoid duplicates).
            top_k: Number of search results per coin.
            timeout: Search timeout (seconds).

        Returns:
            Context string for LLM. Returns an empty string if Mnemo is not used.
        """
        if not self.is_available():
            return ""

        # Coin-specific searches
        coin_results = self.search_for_coin(symbol, top_k=top_k, timeout=timeout)

        # Format results
        context = self.format_as_context(coin_results, max_chars=2000)

        if context:
            logger.info(
                "Mnemo knowledge context created: symbol=%s, results=%d, chars=%d",
                symbol,
                len(coin_results),
                len(context),
            )

        return context