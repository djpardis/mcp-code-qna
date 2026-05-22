"""High-level v2 analysis engine."""

from __future__ import annotations

import logging
import os
import time
from typing import Dict, Optional, Tuple

log = logging.getLogger(__name__)

from app.analysis.evidence import AnswerResult
from app.analysis.index import RepositoryIndex
from app.analysis.llm import LLMProvider, provider_from_env
from app.analysis.retrieval import RetrievalPlanner


class AnalysisEngine:
    """Build indexes, retrieve evidence, and generate grounded answers."""

    def __init__(self, provider: Optional[LLMProvider] = None) -> None:
        self.provider = provider or provider_from_env()
        self._cache: Dict[str, Tuple[RepositoryIndex, RetrievalPlanner]] = {}

    def answer(self, question: str, repo_path: str, *, top_k: int = 8) -> AnswerResult:
        if not question.strip():
            return AnswerResult(
                content="Please provide a question.",
                evidence=[],
                citations=[],
                confidence="none",
                mode="v2",
                provider=self.provider.name,
                limitations=["No question was provided."],
            )

        t0 = time.monotonic()
        index, retriever = self._get_or_build(repo_path)
        log.info("[1/3] index  repo=%s  files=%s  chunks=%s",
                 repo_path, index.repo_map.get("file_count"), index.repo_map.get("chunk_count"))

        retrieval = retriever.retrieve(question, top_k=top_k)
        log.info("[2/3] retrieve  query_type=%s  tokens=%s  evidence=%s",
                 retrieval.query_type, retrieval.metadata.get("query_tokens"), len(retrieval.evidence))
        for i, item in enumerate(retrieval.evidence[:5]):
            log.info("       #%d score=%.2f  %s:%s  [%s]  %r",
                     i + 1, item.score, item.rel_path, item.start_line, item.evidence_type, item.symbol)

        repo_summary = self._repo_summary(index)

        model_label = getattr(self.provider, "model", self.provider.name)
        log.info("[3/3] llm  provider=%s  model=%s", self.provider.name, model_label)
        content = self.provider.generate(question, retrieval.evidence, repo_summary)
        log.info("      done  elapsed=%.2fs", time.monotonic() - t0)

        # Warn when the response doesn't reference any retrieved symbol or file —
        # a sign the model may be drawing from training data instead of evidence.
        limitations = []
        if retrieval.evidence and not self._is_grounded(content, retrieval.evidence):
            limitations.append(
                "Model response may not be grounded in retrieved evidence. "
                "Check the evidence snippets below and consider rephrasing the question."
            )

        if not retrieval.evidence:
            limitations.append("No source evidence was retrieved for this question.")
        elif len(retrieval.evidence) < 3:
            limitations.append("Only a small amount of source evidence was retrieved.")
        if retrieval.query_type == "repo" and not any(
            item.evidence_type == "documentation" for item in retrieval.evidence
        ):
            limitations.append("Repository-level answer has limited documentation evidence.")

        citations = []
        seen = set()
        for item in retrieval.evidence:
            citation = item.citation()
            if citation not in seen:
                citations.append(citation)
                seen.add(citation)

        confidence = "high" if len(retrieval.evidence) >= 5 else "medium" if retrieval.evidence else "low"
        return AnswerResult(
            content=content,
            evidence=retrieval.evidence,
            citations=citations,
            confidence=confidence,
            mode="v2",
            provider=self.provider.name,
            limitations=limitations,
            metadata={
                "repo_path": os.path.abspath(repo_path),
                "query_type": retrieval.query_type,
                "retrieval": retrieval.metadata,
                "repo_map": index.repo_map,
            },
        )

    def _provider_info(self) -> Dict[str, object]:
        info: Dict[str, object] = {"name": self.provider.name}
        if hasattr(self.provider, "model"):
            info["model"] = self.provider.model
        if hasattr(self.provider, "base_url"):
            info["base_url"] = self.provider.base_url
        return info

    def status(self, repo_path: Optional[str] = None) -> Dict[str, object]:
        provider = self.provider.name
        provider_info = self._provider_info()
        if repo_path:
            repo_path = os.path.abspath(repo_path)
            cached = repo_path in self._cache
            if cached:
                index = self._cache[repo_path][0]
                return {**provider_info, "repo_path": repo_path, "indexed": True, "repo_map": index.repo_map}
            return {**provider_info, "repo_path": repo_path, "indexed": False}
        return {**provider_info, "cached_repositories": sorted(self._cache)}

    def build_repo(self, repo_path: str) -> Dict[str, object]:
        index, _ = self._get_or_build(repo_path)
        return index.repo_map

    def _get_or_build(self, repo_path: str) -> Tuple[RepositoryIndex, RetrievalPlanner]:
        abs_path = os.path.abspath(repo_path)
        if abs_path in self._cache:
            return self._cache[abs_path]
        log.info("building index for %s", abs_path)
        index = RepositoryIndex(abs_path).build()
        log.info("index ready: %s files, %s chunks, %s symbols",
                 index.repo_map.get("file_count"), index.repo_map.get("chunk_count"),
                 index.repo_map.get("symbol_count"))
        retriever = RetrievalPlanner(index)
        self._cache[abs_path] = (index, retriever)
        return index, retriever

    def _is_grounded(self, response: str, evidence: list) -> bool:
        """Return True if the response references at least one symbol or file from evidence."""
        response_lower = response.lower()
        for item in evidence:
            if item.symbol and item.symbol.lower() in response_lower:
                return True
            filename = os.path.basename(item.rel_path).lower() if item.rel_path else ""
            if filename and filename in response_lower:
                return True
        return False

    def _repo_summary(self, index: RepositoryIndex) -> str:
        """Build a code-aware summary for the LLM prompt.

        Surfaces top-level symbols and their docstrings so the model understands
        what the repository does before reading the evidence.
        """
        import re

        repo_map = index.repo_map
        files = repo_map.get("top_level_files") or []
        deps = repo_map.get("dependencies") or []

        symbol_lines = []
        for chunk in index.chunks:
            if chunk.chunk_type not in {"class", "function"}:
                continue
            if not chunk.symbol:
                continue
            depth = chunk.file.rel_path.count("/")
            if depth > 1:
                continue
            doc_match = re.search(r'"""(.*?)"""', chunk.text, re.DOTALL) or \
                        re.search(r"'''(.*?)'''", chunk.text, re.DOTALL)
            desc = ""
            if doc_match:
                desc = re.sub(r"\s+", " ", doc_match.group(1)).strip()
                desc = desc.split(".")[0].strip()
            entry = f"  - {chunk.chunk_type} `{chunk.symbol}`"
            if desc:
                entry += f": {desc}"
            symbol_lines.append((depth, entry))

        symbol_lines.sort(key=lambda x: x[0])
        symbol_text = "\n".join(s for _, s in symbol_lines[:12])

        dep_text = f"\nDependencies: {', '.join(deps[:8])}" if deps else ""
        files_text = f"\nTop-level files: {', '.join(files[:10])}" if files else ""
        symbols_text = f"\nKey symbols:\n{symbol_text}" if symbol_text else ""

        return f"Repository at {index.repo_path}.{files_text}{symbols_text}{dep_text}"
