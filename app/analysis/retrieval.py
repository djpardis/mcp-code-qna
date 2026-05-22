"""Local-first lexical/symbol retrieval and evidence-pack assembly."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Dict, List, Sequence

from app.analysis.evidence import EvidenceItem
from app.analysis.index import RepositoryIndex, SourceChunk, tokenise


# Only strip grammatical noise. Keep "how", "what", "when", "why" — they
# carry query semantics that influence classification and scoring.
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by",
    "do", "does", "for", "from", "i", "in", "is", "it",
    "of", "on", "or", "the", "to",
}

# Terms that signal the user wants a high-level view of the whole repo.
_REPO_TERMS = {
    "summarize", "summary", "overview", "describe", "purpose",
    "architecture", "structure", "organized", "layout", "codebase",
    "project", "repository", "repo", "what does this", "what is this",
    "tell me about", "high level", "high-level",
}

_DEPENDENCY_TERMS = {
    "dependency", "dependencies", "libraries", "framework",
    "package", "packages", "imports", "requires",
}

_ARCHITECTURE_TERMS = {
    "architecture", "components", "modules", "organized",
    "structure", "layers", "services", "design",
}


@dataclass(frozen=True)
class RetrievalResult:
    evidence: List[EvidenceItem]
    query_type: str
    metadata: Dict[str, object]


class RetrievalPlanner:
    """Query multiple indexes and merge them into cited evidence."""

    def __init__(self, index: RepositoryIndex, *, top_k: int = 10) -> None:
        self.index = index
        self.top_k = top_k
        self._idf = self._build_idf(index.chunks)

    def retrieve(self, question: str, *, top_k: int | None = None) -> RetrievalResult:
        limit = top_k or self.top_k
        query_tokens = [tok for tok in tokenise(question) if tok not in STOPWORDS]
        query_type = self._classify(question, query_tokens)

        # For repo-level queries, generic structural terms like "repo" and
        # "repository" match almost every chunk and add noise to lexical
        # scoring. Remove them from the token list used for BM25 so that
        # more specific tokens (class names, file names, etc.) can surface.
        lexical_tokens = query_tokens
        if query_type in {"repo", "architecture"}:
            _REPO_NOISE = {"repo", "repository", "codebase", "project", "code"}
            lexical_tokens = [t for t in query_tokens if t not in _REPO_NOISE]

        candidates: Dict[str, tuple[SourceChunk, float, str]] = {}

        if query_type in {"repo", "architecture", "dependencies"}:
            # Repo-context provides structural anchors (README, entry files,
            # classes). We also run lexical search so that specific code
            # relevant to the question (API handlers, data-passing functions,
            # dependency wiring) can surface alongside the structural overview.
            for chunk, score in self._repo_context(query_type):
                self._add(candidates, chunk, score, "repo-map")
            # Scale lexical scores down so repo-context anchors still lead,
            # but specific matching code is not completely buried.
            for chunk, score in self._symbol_matches(query_tokens):
                self._add(candidates, chunk, score * 0.7, "symbol")
            for chunk, score in self._lexical_matches(lexical_tokens):
                self._add(candidates, chunk, score * 0.6, "lexical")
        else:
            # Specific questions: symbol + lexical together.
            for chunk, score in self._symbol_matches(query_tokens):
                self._add(candidates, chunk, score, "symbol")
            for chunk, score in self._lexical_matches(lexical_tokens):
                self._add(candidates, chunk, score, "lexical")

        # Fallback: if nothing was retrieved, surface the most important
        # chunks from the index so the user always gets something useful.
        if not candidates:
            for chunk, score in self._fallback_context():
                self._add(candidates, chunk, score, "fallback")

        ranked = sorted(candidates.values(), key=lambda row: row[1], reverse=True)[:limit]
        evidence = [chunk.to_evidence(score, source) for chunk, score, source in ranked]
        return RetrievalResult(
            evidence=evidence,
            query_type=query_type,
            metadata={
                "query_tokens": query_tokens,
                "candidate_count": len(candidates),
                "retrieval_modes": sorted({item.source for item in evidence}),
            },
        )

    # ------------------------------------------------------------------
    # Merge helper
    # ------------------------------------------------------------------

    def _add(
        self,
        candidates: Dict[str, tuple[SourceChunk, float, str]],
        chunk: SourceChunk,
        score: float,
        source: str,
    ) -> None:
        old = candidates.get(chunk.id)
        if old is None:
            candidates[chunk.id] = (chunk, score, source)
            return
        old_chunk, old_score, old_source = old
        merged_source = old_source if source in old_source.split("+") else f"{old_source}+{source}"
        candidates[chunk.id] = (old_chunk, old_score + score, merged_source)

    # ------------------------------------------------------------------
    # Query classification
    # ------------------------------------------------------------------

    def _classify(self, question: str, tokens: Sequence[str]) -> str:
        lowered = question.lower()
        if any(term in lowered for term in _DEPENDENCY_TERMS):
            return "dependencies"
        if any(term in lowered for term in _ARCHITECTURE_TERMS):
            return "architecture"
        if any(term in lowered for term in _REPO_TERMS):
            return "repo"
        if any(term in tokens for term in ("summarize", "summary", "overview", "describe")):
            return "repo"
        return "general"

    # ------------------------------------------------------------------
    # Retrieval strategies
    # ------------------------------------------------------------------

    def _symbol_matches(self, tokens: Sequence[str]) -> List[tuple[SourceChunk, float]]:
        matches: List[tuple[SourceChunk, float]] = []
        for token in tokens:
            for symbol, chunks in self.index.symbols.items():
                if token == symbol:
                    score = 8.0
                elif token in symbol or symbol in token:
                    score = 4.0
                else:
                    continue
                for chunk in chunks:
                    matches.append((chunk, score))
        return matches

    def _lexical_matches(self, tokens: Sequence[str]) -> List[tuple[SourceChunk, float]]:
        if not tokens:
            return []
        matches: List[tuple[SourceChunk, float]] = []
        for chunk in self.index.chunks:
            haystack = f"{chunk.symbol or ''} {chunk.file.rel_path} {chunk.text}".lower()
            chunk_tokens = tokenise(haystack)
            if not chunk_tokens:
                continue
            counts: Dict[str, int] = {}
            for tok in chunk_tokens:
                counts[tok] = counts.get(tok, 0) + 1
            score = 0.0
            for token in tokens:
                tf = counts.get(token, 0)
                if tf:
                    score += (1.0 + math.log(tf)) * self._idf.get(token, 1.0)
                elif token in haystack:
                    score += 0.8
            if score:
                # Boost when the symbol name itself matches a query token.
                if chunk.symbol and any(tok in chunk.symbol.lower() for tok in tokens):
                    score += 2.5
                # Boost when the file path matches a query token.
                if any(tok in chunk.file.rel_path.lower() for tok in tokens):
                    score += 1.5
                matches.append((chunk, score))
        return matches

    def _repo_context(self, query_type: str) -> List[tuple[SourceChunk, float]]:
        """Return high-priority structural chunks for repo/architecture queries.

        Scores are set high enough that these chunks always appear in the
        top-k alongside any symbol/lexical matches.

        README files are only boosted if they contain meaningful content
        (more than a title line). A near-empty README is less informative
        than the actual top-level symbols and should not crowd them out.
        """
        entry_names = {
            "pyproject.toml", "package.json", "setup.py",
            "requirements.txt", "app.py", "main.py", "index.py",
            "index.ts", "index.js",
        }
        readme_names = {"readme.md", "readme.rst", "readme.txt"}

        # Files that are never useful for code Q&A — skip them entirely.
        noise_names = {
            "robots.txt", ".gitignore", ".gitattributes", ".editorconfig",
            "license", "licence", "license.md", "licence.md",
            "license.txt", "licence.txt", ".env.example", ".nvmrc",
            "thumbs.db", ".ds_store", "cname",
        }

        # Docs that describe the repo purpose rank above auxiliary docs.
        primary_doc_names = readme_names
        auxiliary_doc_names = {
            "contributing.md", "contributing.rst",
            "changelog.md", "changelog.rst", "changes.md",
            "security.md", "authors.md", "history.md",
        }

        matches: List[tuple[SourceChunk, float]] = []
        for chunk in self.index.chunks:
            base = os.path.basename(chunk.file.path).lower()
            if base in noise_names:
                continue
            depth = chunk.file.rel_path.replace("\\", "/").count("/")

            if base in primary_doc_names:
                if depth > 0:
                    # Nested README — penalise by depth, never crowd out root.
                    base_score = max(0.5, 2.0 - depth * 0.4)
                    matches.append((chunk, base_score))
                    continue
                non_empty = [l for l in chunk.text.splitlines() if l.strip()]
                if len(non_empty) <= 3:
                    # Nearly empty root README — low value.
                    matches.append((chunk, 2.0))
                    continue
                # Root README: boost earlier sections more. The intro and goal
                # sections appear in the first ~50 lines and are the most
                # relevant for "what does this repo do" questions.
                position_bonus = max(0.0, 3.0 - chunk.start_line / 20.0)
                matches.append((chunk, 8.0 + position_bonus))

            elif base in auxiliary_doc_names and depth == 0:
                # Root-level auxiliary docs — useful but lower priority than README.
                matches.append((chunk, 2.5))

            elif base in entry_names:
                matches.append((chunk, 6.0))

            elif chunk.chunk_type in {"documentation", "config"} and depth <= 1:
                matches.append((chunk, 3.0))

            elif chunk.chunk_type == "class":
                score = 5.0 if depth == 0 else 3.0
                matches.append((chunk, score))

            elif chunk.chunk_type in {"function", "method"}:
                score = 3.0 if depth == 0 else 1.5
                matches.append((chunk, score))

        return matches

    def _fallback_context(self) -> List[tuple[SourceChunk, float]]:
        """Return a minimal set of useful chunks when retrieval finds nothing.

        This guarantees the user always gets at least some source context
        instead of an "Insufficient Evidence" dead end.
        """
        priority = {"documentation": 5.0, "config": 4.0, "class": 3.0, "function": 2.0}
        matches: List[tuple[SourceChunk, float]] = []
        for chunk in self.index.chunks:
            base_score = priority.get(chunk.chunk_type, 1.0)
            depth = chunk.file.rel_path.replace("\\", "/").count("/")
            # Boost root-level chunks; penalise deeply nested ones so build
            # artifacts and nested component docs don't crowd out root context.
            if depth == 0:
                base_score += 1.5
            else:
                base_score -= min(depth * 0.4, base_score - 0.1)
            matches.append((chunk, base_score))
        # Return the top 10 by priority.
        matches.sort(key=lambda row: row[1], reverse=True)
        return matches[:10]

    # ------------------------------------------------------------------
    # IDF table
    # ------------------------------------------------------------------

    def _build_idf(self, chunks: Sequence[SourceChunk]) -> Dict[str, float]:
        doc_count = max(1, len(chunks))
        dfs: Dict[str, int] = {}
        for chunk in chunks:
            seen = set(tokenise(f"{chunk.symbol or ''} {chunk.file.rel_path} {chunk.text}"))
            for tok in seen:
                dfs[tok] = dfs.get(tok, 0) + 1
        return {tok: math.log((doc_count + 1) / (df + 1)) + 1.0 for tok, df in dfs.items()}
