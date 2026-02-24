# -*- coding: utf-8 -*-
"""
maiupbit.analysis.knowledge
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Mnemo(MAISECONDBRAIN) 지식그래프 연동 모듈.

Obsidian 볼트 + MAIBOT memory에서 투자 관련 지식을 검색하여
LLM 분석 컨텍스트를 강화합니다.

Mnemo가 설치되어 있지 않거나 검색 실패 시 graceful degradation:
빈 결과를 반환하여 기존 분석 파이프라인에 영향을 주지 않습니다.

사용 예::

    provider = KnowledgeProvider()
    context = provider.search("비트코인 시장 전망")
    enriched = provider.enrich_llm_context("BTC 분석 데이터...", "KRW-BTC")

환경 변수::

    MNEMO_VAULT_PATH   - Obsidian 볼트 경로 (필수)
    MNEMO_MEMORY_PATH  - MAIBOT memory 경로 (필수)
    MNEMO_CACHE_DIR    - Mnemo 캐시 디렉토리 (기본: .mnemo)
    MNEMO_USE_RERANKER - 리랭커 사용 여부 (기본: true)
    MNEMO_ENABLED      - 지식 검색 활성화 (기본: true)
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Mnemo 프로젝트 경로
_DEFAULT_MNEMO_PATH = r"C:\TEST\MAISECONDBRAIN"
_DEFAULT_VAULT_PATH = r"C:\Users\jini9\OneDrive\Documents\JINI_SYNC"
_DEFAULT_MEMORY_PATH = r"C:\MAIBOT\memory"

# 투자/시장 관련 검색어 확장 매핑
_COIN_KEYWORDS: dict[str, list[str]] = {
    "BTC": ["비트코인", "bitcoin", "BTC", "암호화폐", "디지털 자산"],
    "ETH": ["이더리움", "ethereum", "ETH", "스마트컨트랙트"],
    "XRP": ["리플", "ripple", "XRP"],
    "SOL": ["솔라나", "solana", "SOL"],
    "DOGE": ["도지코인", "dogecoin", "DOGE"],
}

# 기본 투자 관련 검색 쿼리
_DEFAULT_QUERIES: list[str] = [
    "암호화폐 시장 전망 투자 전략",
    "퀀트 투자 모멘텀 변동성",
]


class KnowledgeProvider:
    """Mnemo 지식그래프 검색 래퍼.

    MAISECONDBRAIN의 integrated_search.py를 subprocess로 호출하여
    Obsidian 볼트 + MAIBOT memory에서 관련 지식을 검색합니다.

    Attributes:
        enabled: 지식 검색 활성화 여부.
        mnemo_path: MAISECONDBRAIN 프로젝트 경로.
    """

    def __init__(
        self,
        mnemo_path: Optional[str] = None,
        vault_path: Optional[str] = None,
        memory_path: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        """KnowledgeProvider 초기화.

        Args:
            mnemo_path: MAISECONDBRAIN 프로젝트 경로. None이면 기본값.
            vault_path: Obsidian 볼트 경로. None이면 환경변수 또는 기본값.
            memory_path: MAIBOT memory 경로. None이면 환경변수 또는 기본값.
            enabled: 활성화 여부. None이면 MNEMO_ENABLED 환경변수 (기본 true).
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
        """Mnemo 검색이 사용 가능한지 확인.

        Returns:
            True면 사용 가능.
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
        """Mnemo 지식그래프에서 검색.

        Args:
            query: 검색 쿼리.
            top_k: 반환할 최대 결과 수.
            timeout: 검색 타임아웃 (초).

        Returns:
            검색 결과 리스트. 각 항목::

                {
                    'name': str,       # 문서 이름
                    'score': float,    # 관련성 점수
                    'snippet': str,    # 문서 스니펫
                    'source': str,     # 'vault' 또는 'memory'
                    'path': str,       # 파일 경로
                }

            검색 실패 시 빈 리스트 반환.
        """
        if not self.is_available():
            logger.debug("Mnemo 지식 검색 비활성화 또는 미설치")
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

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.mnemo_path),
                env=env,
                encoding="utf-8",
            )

            # JSON 출력 파싱 (stdout에서 JSON 배열 추출)
            stdout = result.stdout.strip()
            if not stdout:
                logger.warning("Mnemo 검색 결과 비어있음 (query=%s)", query)
                return []

            # stdout에 JSON 이외의 로그가 섞일 수 있으므로 [ ] 블록 추출
            json_start = stdout.find("[")
            json_end = stdout.rfind("]") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = stdout[json_start:json_end]
                results = json.loads(json_str)
                logger.info(
                    "Mnemo 검색 완료: query='%s', results=%d",
                    query, len(results),
                )
                return results

            logger.warning("Mnemo 출력에서 JSON 배열을 찾을 수 없음")
            return []

        except subprocess.TimeoutExpired:
            logger.error("Mnemo 검색 타임아웃 (%ds): query='%s'", timeout, query)
            return []
        except json.JSONDecodeError as exc:
            logger.error("Mnemo JSON 파싱 실패: %s", exc)
            return []
        except Exception as exc:  # noqa: BLE001
            logger.error("Mnemo 검색 실패: %s", exc)
            return []

    def search_for_coin(
        self,
        symbol: str,
        top_k: int = 5,
        timeout: int = 30,
    ) -> list[dict]:
        """특정 코인에 대한 지식 검색.

        코인 심볼에서 관련 키워드를 생성하여 검색합니다.

        Args:
            symbol: 거래 심볼. 예: "KRW-BTC".
            top_k: 반환할 최대 결과 수.
            timeout: 검색 타임아웃 (초).

        Returns:
            검색 결과 리스트.
        """
        ticker = symbol.split("-")[-1] if "-" in symbol else symbol
        keywords = _COIN_KEYWORDS.get(ticker, [ticker])

        query = " ".join(keywords[:3]) + " 시장 전망 투자"
        return self.search(query, top_k=top_k, timeout=timeout)

    def search_market_context(
        self,
        top_k: int = 3,
        timeout: int = 30,
    ) -> list[dict]:
        """일반 시장 컨텍스트 검색.

        투자 전략, 시장 동향 등 일반적인 지식을 검색합니다.

        Args:
            top_k: 반환할 최대 결과 수.
            timeout: 검색 타임아웃 (초).

        Returns:
            검색 결과 리스트.
        """
        all_results = []
        for query in _DEFAULT_QUERIES:
            results = self.search(query, top_k=top_k, timeout=timeout)
            all_results.extend(results)

        # 중복 제거 (이름 기준)
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
        """검색 결과를 LLM 컨텍스트 문자열로 포매팅.

        Args:
            results: search() 반환값.
            max_chars: 최대 문자 수.

        Returns:
            LLM 프롬프트에 주입할 컨텍스트 문자열.
            결과가 없으면 빈 문자열.
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
        """LLM 분석을 위한 지식 컨텍스트 생성.

        코인 관련 지식 + 일반 시장 지식을 결합하여
        LLM 프롬프트에 주입할 컨텍스트를 생성합니다.

        Args:
            symbol: 거래 심볼. 예: "KRW-BTC".
            existing_news: 기존 뉴스 텍스트 (중복 방지).
            top_k: 코인별 검색 결과 수.
            timeout: 검색 타임아웃 (초).

        Returns:
            LLM 컨텍스트 문자열. Mnemo 미사용 시 빈 문자열.
        """
        if not self.is_available():
            return ""

        # 코인별 검색
        coin_results = self.search_for_coin(symbol, top_k=top_k, timeout=timeout)

        # 결과 포매팅
        context = self.format_as_context(coin_results, max_chars=2000)

        if context:
            logger.info(
                "Mnemo 지식 컨텍스트 생성: symbol=%s, results=%d, chars=%d",
                symbol, len(coin_results), len(context),
            )

        return context
