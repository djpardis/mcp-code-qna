#!/usr/bin/env python3
"""
MCP-style FastAPI server for code repository question answering.

Exposes:
  GET  /                     web UI (static index.html)
  GET  /.well-known/mcp      server metadata
  GET  /list_resources       MCP-style resource listing
  POST /read_resource        MCP-style resource read (uri="questions")
  POST /question             convenience endpoint used by the web UI
"""

from __future__ import annotations

import argparse
import ast
import logging
import os
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.generator.answer_generator import AnswerGenerator
from app.indexer.code_indexer import CodeIndexer
from app.retriever.retriever import Retriever

logger = logging.getLogger("mcp_web_server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


# --------------------------------------------------------------------------- #
# State                                                                       #
# --------------------------------------------------------------------------- #

class ServerState:
    """Holds the default repo's indexer/retriever and a per-repo cache."""

    def __init__(self) -> None:
        self.default_repo_path: Optional[str] = None
        self.default_indexer: Optional[CodeIndexer] = None
        self.default_retriever: Optional[Retriever] = None
        self.generator: AnswerGenerator = AnswerGenerator()
        self._cache: Dict[str, Tuple[CodeIndexer, Retriever]] = {}

    def initialise_default(self, repo_path: str, rebuild: bool) -> None:
        logger.info("Initialising default repo: %s", repo_path)
        indexer = CodeIndexer(repo_path=repo_path)
        if rebuild:
            indexer.build_index()
        else:
            indexer.load_or_build_index()
        retriever = Retriever(indexer=indexer)
        self.default_repo_path = indexer.repo_path
        self.default_indexer = indexer
        self.default_retriever = retriever
        self._cache[indexer.repo_path] = (indexer, retriever)

    def get_or_build(self, repo_path: str) -> Tuple[CodeIndexer, Retriever]:
        """Return (indexer, retriever) for ``repo_path``, building/caching as needed."""
        repo_path = os.path.abspath(repo_path)
        if repo_path in self._cache:
            return self._cache[repo_path]
        if not os.path.isdir(repo_path):
            raise ValueError(f"Repository path {repo_path!r} is not a directory")
        logger.info("Building index for %s", repo_path)
        indexer = CodeIndexer(repo_path=repo_path)
        indexer.load_or_build_index()
        retriever = Retriever(indexer=indexer)
        self._cache[repo_path] = (indexer, retriever)
        return indexer, retriever

    def resolve(self, requested: Optional[str]) -> Tuple[CodeIndexer, Retriever]:
        """Pick the right indexer/retriever for a request."""
        if requested:
            return self.get_or_build(requested)
        if self.default_indexer and self.default_retriever:
            return self.default_indexer, self.default_retriever
        raise ValueError(
            "No repository path provided. Pass --repo-path when starting the "
            "server or include 'repo_path' in the request."
        )


state = ServerState()


# --------------------------------------------------------------------------- #
# Statistics                                                                  #
# --------------------------------------------------------------------------- #

class _CodeVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.classes = 0
        self.functions = 0
        self.methods = 0
        self._in_class = 0

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802 - ast API
        self.classes += 1
        self._in_class += 1
        self.generic_visit(node)
        self._in_class -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        if self._in_class:
            self.methods += 1
        else:
            self.functions += 1
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        if self._in_class:
            self.methods += 1
        else:
            self.functions += 1
        self.generic_visit(node)


def _is_statistics_question(question: str) -> bool:
    q = question.lower()
    has_count_word = any(
        w in q for w in ("how many", "count", "number of", "statistics", "total", "list", "show me")
    )
    has_unit = any(w in q for w in ("function", "method", "class", "file", "module", "line"))
    return has_count_word and has_unit


def _is_listing_question(question: str) -> bool:
    q = question.lower()
    return (
        any(w in q for w in ("what classes", "list classes", "show classes"))
        or any(w in q for w in ("what functions", "list functions", "show functions"))
        or any(w in q for w in ("what files", "list files", "show files"))
    )


def _is_framework_question(question: str) -> bool:
    q = question.lower()
    return any(p in q for p in ("what framework", "which framework", "what stack", "what tech stack"))


def _is_auth_question(question: str) -> bool:
    q = question.lower()
    return any(
        p in q
        for p in (
            "auth",
            "authentication",
            "authorize",
            "authorization",
            "login",
            "signin",
            "sign in",
            "oauth",
            "jwt",
            "token",
            "password",
            "session",
        )
    )


def _is_purpose_question(question: str) -> bool:
    q = question.lower()
    return any(
        phrase in q
        for phrase in (
            "purpose",
            "what is this",
            "what does this",
            "what is the purpose",
            "what is the repo",
            "what is this repository",
            "what does this repository do",
        )
    )


SKIP_DIR_NAMES = frozenset({
    ".git",
    ".code_index",
    "__pycache__",
    "venv",
    ".venv",
    "env",
    ".mypy_cache",
    ".pytest_cache",
    "node_modules",
    "dist",
    "build",
})


def _prune_walk_dirs(dirs: List[str]) -> None:
    dirs[:] = sorted(d for d in dirs if d not in SKIP_DIR_NAMES and not d.startswith("."))


def _compute_statistics(repo_path: str) -> Dict[str, Any]:
    counts: Dict[str, Any] = {
        "function": 0,
        "method": 0,
        "class": 0,
        "lines": 0,
        "empty_lines": 0,
        "comment_lines": 0,
    }
    file_types: Dict[str, int] = {}
    python_files: list[str] = []
    js_like_files: list[str] = []
    template_files: list[str] = []
    code_file_count = 0
    language_file_counts = {"python": 0, "javascript_typescript": 0, "template": 0}

    for root, dirs, files in os.walk(repo_path):
        _prune_walk_dirs(dirs)
        for name in files:
            ext = os.path.splitext(name)[1].lstrip(".") or "(none)"
            file_types[ext] = file_types.get(ext, 0) + 1
            if name.endswith(".py"):
                python_files.append(os.path.join(root, name))
                code_file_count += 1
                language_file_counts["python"] += 1
            elif ext in {"js", "jsx", "ts", "tsx", "mjs", "cjs"}:
                js_like_files.append(os.path.join(root, name))
                code_file_count += 1
                language_file_counts["javascript_typescript"] += 1
            elif ext in {"html", "htm", "njk"}:
                template_files.append(os.path.join(root, name))
                code_file_count += 1
                language_file_counts["template"] += 1

    for path in python_files:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
        except OSError as exc:
            logger.warning("Skipping %s: %s", path, exc)
            continue
        lines = content.split("\n")
        counts["lines"] += len(lines)
        for line in lines:
            stripped = line.strip()
            if not stripped:
                counts["empty_lines"] += 1
            elif stripped.startswith("#"):
                counts["comment_lines"] += 1
        try:
            tree = ast.parse(content)
        except SyntaxError as exc:
            logger.info("Could not parse %s: %s", path, exc)
            continue
        visitor = _CodeVisitor()
        visitor.visit(tree)
        counts["function"] += visitor.functions
        counts["method"] += visitor.methods
        counts["class"] += visitor.classes

    js_class_pattern = re.compile(r"\bclass\s+[A-Za-z_\$][A-Za-z0-9_\$]*")
    js_function_patterns = [
        re.compile(r"\bfunction\s+[A-Za-z_\$][A-Za-z0-9_\$]*\s*\("),
        re.compile(r"\b(?:const|let|var)\s+[A-Za-z_\$][A-Za-z0-9_\$]*\s*=\s*(?:async\s*)?\([^)]*\)\s*=>"),
        re.compile(r"\b(?:const|let|var)\s+[A-Za-z_\$][A-Za-z0-9_\$]*\s*=\s*(?:async\s*)?[A-Za-z_\$][A-Za-z0-9_\$]*\s*=>"),
    ]
    js_method_pattern = re.compile(r"^\s*(?:async\s+)?[A-Za-z_\$][A-Za-z0-9_\$]*\s*\([^)]*\)\s*\{", re.MULTILINE)

    for path in js_like_files:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
        except OSError as exc:
            logger.warning("Skipping %s: %s", path, exc)
            continue
        lines = content.split("\n")
        counts["lines"] += len(lines)
        for line in lines:
            stripped = line.strip()
            if not stripped:
                counts["empty_lines"] += 1
            elif stripped.startswith("//"):
                counts["comment_lines"] += 1

        counts["class"] += len(js_class_pattern.findall(content))
        counts["method"] += len(js_method_pattern.findall(content))
        for pat in js_function_patterns:
            counts["function"] += len(pat.findall(content))

    macro_pattern = re.compile(r"\{%\s*macro\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
    script_block_pattern = re.compile(r"<script[^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL)
    for path in template_files:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
        except OSError as exc:
            logger.warning("Skipping %s: %s", path, exc)
            continue
        lines = content.split("\n")
        counts["lines"] += len(lines)
        for line in lines:
            stripped = line.strip()
            if not stripped:
                counts["empty_lines"] += 1
            elif stripped.startswith(("<!--", "{#", "//")):
                counts["comment_lines"] += 1

        # Nunjucks macros are function-like and are common in .njk codebases.
        counts["function"] += len(macro_pattern.findall(content))

        # Parse inline JavaScript in templates.
        for script in script_block_pattern.findall(content):
            counts["class"] += len(js_class_pattern.findall(script))
            counts["method"] += len(js_method_pattern.findall(script))
            for pat in js_function_patterns:
                counts["function"] += len(pat.findall(script))

    return {
        "counts": counts,
        "python_file_count": len(python_files),
        "js_file_count": len(js_like_files),
        "template_file_count": len(template_files),
        "code_file_count": code_file_count,
        "language_file_counts": language_file_counts,
        "file_types": file_types,
    }


def _format_statistics_answer(stats: Dict[str, Any]) -> str:
    counts = stats["counts"]
    py_count = stats["python_file_count"]
    js_count = stats["js_file_count"]
    template_count = stats["template_file_count"]
    file_count = stats["code_file_count"]
    code_lines = counts["lines"] - counts["empty_lines"] - counts["comment_lines"]
    if file_count == 0:
        return (
            "## Code Statistics\n"
            "I couldn't find Python or JS/TS source files in this folder.\n\n"
            "Tip: pick your actual app/code repository folder (not a backups/assets folder)."
        )
    parts = [
        "## Code Statistics",
        f"- **{counts['function']}** standalone functions",
        f"- **{counts['method']}** class methods",
        f"- **{counts['class']}** classes",
        f"- **{file_count}** analyzed files ({py_count} Python, {js_count} JS/TS, {template_count} templates)",
        f"- **{counts['lines']}** total lines (**{code_lines}** code, "
        f"**{counts['comment_lines']}** comment, **{counts['empty_lines']}** empty)",
    ]
    if counts["class"]:
        parts.append(f"- avg methods per class: **{counts['method'] / counts['class']:.1f}**")
    if file_count:
        parts.append(f"- avg lines per file: **{counts['lines'] / file_count:.1f}**")
    if stats["file_types"]:
        parts.append("\n### File-type distribution")
        ranked = sorted(stats["file_types"].items(), key=lambda kv: kv[1], reverse=True)[:5]
        for ext, count in ranked:
            parts.append(f"- **{ext}**: {count}")
    parts.append(
        "\n*Note: JS/TS and template counts use regex heuristics (good for rough analysis, not a full parser).*"
    )
    return "\n".join(parts)


def _build_repo_purpose_summary(repo_path: str, stats: Dict[str, Any]) -> str:
    """Best-effort repository purpose summary when semantic retrieval has no hits."""
    file_types = stats.get("file_types", {})
    dominant = sorted(file_types.items(), key=lambda kv: kv[1], reverse=True)[:5]
    dominant_text = ", ".join(f"{ext or '(none)'} ({count})" for ext, count in dominant) or "unknown"

    readme_hint = None
    for name in ("README.md", "README.MD", "readme.md"):
        p = os.path.join(repo_path, name)
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    # Pull first meaningful non-heading line.
                    for line in fh.read().splitlines():
                        s = line.strip()
                        if s and not s.startswith("#"):
                            readme_hint = s
                            break
            except OSError:
                pass
            break

    lines = [
        "## Repository Purpose (Best Effort)",
        "I couldn't infer purpose from retrievable code chunks, so here's a repository-level summary.",
    ]
    if readme_hint:
        lines.append(f"- README hint: {readme_hint}")
    lines.append(f"- Dominant file types: {dominant_text}")
    lines.append(
        "- This folder appears to be primarily "
        + (
            "template/content assets."
            if stats.get("template_file_count", 0) > stats.get("js_file_count", 0) + stats.get("python_file_count", 0)
            else "application/source code."
        )
    )
    return "\n".join(lines)


def _build_entity_purpose_summary(question: str, chunks: List[Dict[str, Any]]) -> str:
    """Build a concise, explanation-first purpose answer for symbol-level queries."""
    q = question.lower()
    target_terms = [w for w in re.findall(r"[a-zA-Z_][a-zA-Z0-9_\.:-]*", q) if len(w) > 2]

    ranked: List[tuple[int, str, str, str, str, str]] = []
    for chunk in chunks:
        if isinstance(chunk, dict):
            name = str(chunk.get("name", "")).strip()
            ctype = str(chunk.get("type", "")).strip() or "code block"
            path = str(chunk.get("path", "")).strip()
            content = str(chunk.get("content", "")).strip()
            docstring = str(chunk.get("docstring", "")).strip()
        else:
            raw = getattr(chunk, "chunk", chunk)
            name = str(getattr(raw, "name", "")).strip()
            ctype = str(getattr(raw, "type", "") or getattr(chunk, "chunk_type", "") or getattr(chunk, "type", "")).strip() or "code block"
            path = str(getattr(raw, "file_path", "") or getattr(raw, "path", "") or getattr(chunk, "file_path", "")).strip()
            content = str(getattr(raw, "content", "") or getattr(chunk, "content", "")).strip()
            docstring = str(getattr(raw, "docstring", "")).strip()
        score = 0
        low_name = name.lower()
        low_path = path.lower()
        for term in target_terms:
            if term in low_name:
                score += 2
            if term in low_path:
                score += 1
        ranked.append((score, name, ctype, path, content, docstring))

    ranked.sort(key=lambda row: row[0], reverse=True)
    top = ranked[:3]
    if not top:
        return "## Purpose Summary\nI couldn't identify a specific component purpose from retrieved matches."

    lines = ["## Purpose Summary", "This component appears to do the following:"]
    for _, name, ctype, path, content, docstring in top:
        label = name or "unnamed symbol"
        file_name = os.path.basename(path) if path else "unknown file"
        summary = docstring if len(docstring) >= 12 else ""
        signature = ""
        for raw in content.splitlines():
            candidate = raw.strip()
            if candidate.startswith(("def ", "class ", "function ", "const ", "let ", "var ", "export ")):
                signature = candidate
                break
        for raw in content.splitlines():
            s = raw.strip().strip("\"'`#/* ")
            if len(s) >= 20 and not any(
                tok in s for tok in ("{", "}", "=>", "function", "class ", "def ", "=", ".read_", ".write_")
            ):
                summary = s
                break
        if summary:
            lines.append(f"- `{label}` ({ctype}, `{file_name}`): {summary}")
        elif signature:
            lines.append(f"- `{label}` ({ctype}, `{file_name}`): Defines `{signature}` and contributes to this feature flow.")
        else:
            lines.append(f"- `{label}` ({ctype}, `{file_name}`): Handles core behavior related to this feature.")
    lines.append("If you want, I can break down request flow and dependencies next.")
    return "\n".join(lines)


def _detect_frameworks(repo_path: str, file_types: Dict[str, int]) -> List[str]:
    frameworks: List[str] = []
    files = set()
    try:
        files = set(os.listdir(repo_path))
    except OSError:
        return frameworks

    if "package.json" in files:
        frameworks.append("Node.js")
    if ".eleventy.js" in files or ".eleventy.cjs" in files or "njk" in file_types:
        frameworks.append("Eleventy (11ty)")
    if "next.config.js" in files or "next.config.mjs" in files:
        frameworks.append("Next.js")
    if "vite.config.js" in files or "vite.config.ts" in files:
        frameworks.append("Vite")
    if "astro.config.mjs" in files or "astro.config.js" in files:
        frameworks.append("Astro")
    if "requirements.txt" in files or "pyproject.toml" in files:
        frameworks.append("Python")
    return frameworks


def _build_listing_answer(question: str, stats: Dict[str, Any]) -> str:
    q = question.lower()
    counts = stats["counts"]
    py_count = stats["python_file_count"]
    js_count = stats["js_file_count"]
    template_count = stats["template_file_count"]

    if "class" in q:
        return (
            "## Class Summary\n"
            f"- **{counts['class']}** class declarations found\n"
            f"- **{counts['method']}** class methods found\n"
            f"- analyzed files: **{py_count}** Python, **{js_count}** JS/TS, **{template_count}** templates"
        )
    if "function" in q:
        return (
            "## Function Summary\n"
            f"- **{counts['function']}** standalone functions found\n"
            f"- **{counts['method']}** class methods found\n"
            f"- analyzed files: **{py_count}** Python, **{js_count}** JS/TS, **{template_count}** templates"
        )
    if "file" in q:
        top = sorted(stats["file_types"].items(), key=lambda kv: kv[1], reverse=True)[:8]
        lines = ["## File Summary", f"- **{stats['code_file_count']}** analyzed code/template files", "", "### Top file types"]
        for ext, count in top:
            lines.append(f"- **{ext}**: {count}")
        return "\n".join(lines)
    return _format_statistics_answer(stats)


def _build_framework_answer(repo_path: str, stats: Dict[str, Any]) -> str:
    frameworks = _detect_frameworks(repo_path, stats.get("file_types", {}))
    if frameworks:
        return "## Detected Frameworks\n" + "\n".join(f"- {f}" for f in frameworks)
    return "## Detected Frameworks\nI couldn't confidently detect a framework from this repository structure."


def _build_no_auth_answer() -> str:
    return (
        "## Authentication\n"
        "I couldn't find an authentication function or auth flow in this repository."
    )


def _chunks_look_like_auth(chunks: List[Any]) -> bool:
    pattern = re.compile(
        r"\b(authentication|authorize|authorization|login|signin|sign[ -]?in|oauth|jwt|token|password|session|access[_ -]?token|refresh[_ -]?token)\b",
        re.IGNORECASE,
    )
    for chunk in chunks:
        raw = chunk if isinstance(chunk, dict) else getattr(chunk, "chunk", chunk)
        name = str(raw.get("name", "") if isinstance(raw, dict) else getattr(raw, "name", "")).lower()
        path = str(raw.get("file_path", "") if isinstance(raw, dict) else getattr(raw, "file_path", "")).lower()
        content = str(raw.get("content", "") if isinstance(raw, dict) else getattr(raw, "content", "")).lower()
        haystack = f"{name}\n{path}\n{content}"
        if pattern.search(haystack):
            return True
    return False


def _build_auth_summary(chunks: List[Any]) -> str:
    lines = ["## Authentication Summary", "I found authentication-related logic in these components:"]
    added = 0
    for chunk in chunks[:4]:
        raw = chunk if isinstance(chunk, dict) else getattr(chunk, "chunk", chunk)
        name = str(raw.get("name", "") if isinstance(raw, dict) else getattr(raw, "name", "")).strip() or "unnamed symbol"
        ctype = str(raw.get("type", "") if isinstance(raw, dict) else getattr(raw, "type", "")).strip() or "code block"
        path = str(raw.get("file_path", "") if isinstance(raw, dict) else getattr(raw, "file_path", "")).strip()
        doc = str(raw.get("docstring", "") if isinstance(raw, dict) else getattr(raw, "docstring", "")).strip()
        file_name = os.path.basename(path) if path else "unknown file"
        if doc:
            lines.append(f"- `{name}` ({ctype}, `{file_name}`): {doc}")
        else:
            lines.append(f"- `{name}` ({ctype}, `{file_name}`): Participates in authentication/session handling.")
        added += 1
    if added == 0:
        return _build_no_auth_answer()
    return "\n".join(lines)


SEARCHABLE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".html", ".htm", ".njk", ".md", ".json", ".yml", ".yaml", ".css",
}


STOPWORDS: Set[str] = {
    "what", "where", "when", "how", "why", "who", "show", "list", "tell",
    "is", "are", "the", "a", "an", "in", "of", "to", "for", "this", "that",
    "does", "do", "it", "on", "and", "or", "with", "repo", "repository",
    "project", "code", "function", "functions", "class", "classes",
}


def _extract_query_tokens(question: str) -> List[str]:
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_\-]{2,}", question.lower())
    deduped: List[str] = []
    seen: Set[str] = set()
    for token in tokens:
        if token in STOPWORDS:
            continue
        if token not in seen:
            deduped.append(token)
            seen.add(token)
    return deduped[:8]


def _collect_searchable_files(repo_path: str, limit: int = 400) -> List[str]:
    files: List[str] = []
    for root, dirs, names in os.walk(repo_path):
        _prune_walk_dirs(dirs)
        for name in names:
            ext = os.path.splitext(name)[1].lower()
            if ext not in SEARCHABLE_EXTENSIONS:
                continue
            files.append(os.path.join(root, name))
            if len(files) >= limit:
                return files
    return files


def _search_repo_text(question: str, repo_path: str, max_files: int = 4) -> List[Dict[str, Any]]:
    tokens = _extract_query_tokens(question)
    if not tokens:
        return []
    matches: List[Dict[str, Any]] = []
    for path in _collect_searchable_files(repo_path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            continue
        lowered = content.lower()
        score = sum(lowered.count(token) for token in tokens)
        if score == 0:
            continue
        snippet_lines: List[str] = []
        for line in content.splitlines():
            ll = line.lower()
            if any(token in ll for token in tokens):
                snippet_lines.append(line.strip())
            if len(snippet_lines) >= 3:
                break
        matches.append(
            {
                "path": path,
                "score": score,
                "snippets": snippet_lines,
            }
        )
    matches.sort(key=lambda m: m["score"], reverse=True)
    return matches[:max_files]


def _build_search_fallback_answer(question: str, repo_path: str) -> str:
    hits = _search_repo_text(question, repo_path)
    if not hits:
        return "I couldn't find strong matches for that question in this repository."
    lines = [
        "## Best-Effort Repository Match",
        "I couldn't answer from indexed chunks, so I searched repository files directly.",
    ]
    for hit in hits:
        rel = os.path.relpath(hit["path"], repo_path)
        lines.append(f"\n### `{rel}` (score: {hit['score']})")
        if hit["snippets"]:
            lines.append("- Relevant text was found in this file.")
    return "\n".join(lines)


def _to_explanation_only(answer: str) -> str:
    """Remove raw code dumps and keep explanation-oriented content."""
    if not answer:
        return answer
    # Remove fenced code blocks and HTML details blocks commonly used for raw dumps.
    answer = re.sub(r"```[\s\S]*?```", "", answer)
    answer = re.sub(r"<details>[\s\S]*?</details>", "", answer, flags=re.IGNORECASE)
    # Collapse excessive blank lines after stripping.
    answer = re.sub(r"\n{3,}", "\n\n", answer).strip()
    return answer or "I found relevant information, but code dumps were removed. Ask for a summary of behavior or purpose."


# --------------------------------------------------------------------------- #
# Core question handling                                                      #
# --------------------------------------------------------------------------- #

def _answer(question: str, repo_path: Optional[str]) -> Dict[str, Any]:
    """Compute an answer dict for a (question, repo_path) pair."""
    if not question:
        return {
            "content": "Please provide a question.",
            "metadata": {"format": "text/markdown", "error": "Empty question"},
        }
    try:
        indexer, retriever = state.resolve(repo_path)
    except ValueError as exc:
        return {
            "content": str(exc),
            "metadata": {"question": question, "format": "text/markdown", "error": str(exc)},
        }

    if _is_statistics_question(question):
        stats = _compute_statistics(indexer.repo_path)
        return {
            "content": _to_explanation_only(_format_statistics_answer(stats)),
            "metadata": {"question": question, "format": "text/markdown"},
        }

    if _is_listing_question(question):
        stats = _compute_statistics(indexer.repo_path)
        return {
            "content": _to_explanation_only(_build_listing_answer(question, stats)),
            "metadata": {"question": question, "format": "text/markdown"},
        }

    if _is_framework_question(question):
        stats = _compute_statistics(indexer.repo_path)
        return {
            "content": _to_explanation_only(_build_framework_answer(indexer.repo_path, stats)),
            "metadata": {"question": question, "format": "text/markdown"},
        }

    chunks = retriever.retrieve(question)
    if _is_auth_question(question):
        if not chunks or not _chunks_look_like_auth(chunks):
            return {
                "content": _to_explanation_only(_build_no_auth_answer()),
                "metadata": {"question": question, "format": "text/markdown"},
            }
        return {
            "content": _to_explanation_only(_build_auth_summary(chunks)),
            "metadata": {"question": question, "format": "text/markdown"},
        }
    if _is_purpose_question(question):
        stats = _compute_statistics(indexer.repo_path)
        q_lower = question.lower()
        is_repo_level = any(token in q_lower for token in ("repo", "repository", "this project", "whole project"))
        if is_repo_level:
            return {
                "content": _to_explanation_only(_build_repo_purpose_summary(indexer.repo_path, stats)),
                "metadata": {"question": question, "format": "text/markdown"},
            }
        if chunks:
            return {
                "content": _to_explanation_only(_build_entity_purpose_summary(question, chunks)),
                "metadata": {"question": question, "format": "text/markdown"},
            }
        return {
            "content": _to_explanation_only(_build_repo_purpose_summary(indexer.repo_path, stats)),
            "metadata": {"question": question, "format": "text/markdown"},
        }
    if not chunks:
        return {
            "content": _to_explanation_only(_build_search_fallback_answer(question, indexer.repo_path)),
            "metadata": {"question": question, "format": "text/markdown"},
        }
    answer = state.generator.generate(question, chunks)
    return {
        "content": _to_explanation_only(answer),
        "metadata": {"question": question, "format": "text/markdown"},
    }


# --------------------------------------------------------------------------- #
# FastAPI app                                                                 #
# --------------------------------------------------------------------------- #

app = FastAPI(title="MCP Code Repository Q&A", description="Answer questions about Python code repositories.")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/.well-known/mcp")
async def get_mcp_metadata():
    return {
        "api_version": "0.1.0",
        "server_name": "code-repository-qa",
        "server_version": "0.2.0",
        "capabilities": ["list_resources", "read_resource"],
        "description": "MCP-style server that answers questions about code repositories.",
    }


@app.get("/list_resources")
async def list_resources():
    return {
        "resources": [
            {
                "uri": "questions",
                "title": "Repository Q&A",
                "description": "Ask questions about the code repository",
                "metadata": {"repo_path": state.default_repo_path},
            }
        ],
        "cursor": None,
    }


@app.get("/list_repo_candidates")
async def list_repo_candidates(root: Optional[str] = None, limit: int = 200):
    """Return local directory candidates for the repo picker UI."""
    base = os.path.abspath(root or os.path.expanduser("~/Documents"))
    if not os.path.isdir(base):
        return {"root": base, "repos": []}

    repos: List[str] = []
    try:
        for entry in sorted(os.listdir(base)):
            if entry.startswith("."):
                continue
            full_path = os.path.join(base, entry)
            if os.path.isdir(full_path):
                repos.append(full_path)
                if len(repos) >= max(1, limit):
                    break
    except OSError:
        repos = []

    return {"root": base, "repos": repos}


@app.post("/question")
async def handle_question(request: Request):
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"detail": "Invalid JSON body"})
    question = (data.get("question") or "").strip()
    repo_path = data.get("repo_path")
    return _answer(question, repo_path)


@app.post("/read_resource")
async def read_resource(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"detail": "Invalid JSON body"})
    if body.get("uri") != "questions":
        return JSONResponse(status_code=404, content={"detail": f"Resource {body.get('uri')!r} not found"})
    parameters = body.get("parameters") or {}
    question = (parameters.get("question") or "").strip()
    repo_path = parameters.get("repo_path")
    if not question:
        return JSONResponse(status_code=400, content={"detail": "No question provided"})
    return _answer(question, repo_path)


# --------------------------------------------------------------------------- #
# CLI entry point                                                             #
# --------------------------------------------------------------------------- #

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the MCP code-repository Q&A server")
    parser.add_argument(
        "--repo-path", "-r",
        dest="repo_path",
        help="Default repository path. Omit to run in dynamic mode (clients pass repo_path per request).",
    )
    parser.add_argument("--rebuild", action="store_true", help="Force a rebuild of the index")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    return parser


def main(argv: Optional[list[str]] = None) -> None:
    args = _build_parser().parse_args(argv)
    if args.repo_path:
        try:
            state.initialise_default(args.repo_path, rebuild=args.rebuild)
        except Exception as exc:  # pragma: no cover - surfaced to operator
            logger.error("Failed to initialise default repo %s: %s", args.repo_path, exc)
            logger.warning("Server will start without a default repository.")
    else:
        logger.info("No --repo-path supplied. Running in dynamic mode.")
    logger.info("Listening on http://%s:%s", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
