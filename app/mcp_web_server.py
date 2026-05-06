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
import sys
from typing import Any, Dict, List, Optional, Tuple

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
    has_count_word = any(w in q for w in ("how many", "count", "number of", "statistics", "total"))
    has_unit = any(w in q for w in ("function", "method", "class", "file", "module", "line"))
    return has_count_word and has_unit


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

    for root, dirs, files in os.walk(repo_path):
        _prune_walk_dirs(dirs)
        for name in files:
            ext = os.path.splitext(name)[1].lstrip(".") or "(none)"
            file_types[ext] = file_types.get(ext, 0) + 1
            if name.endswith(".py"):
                python_files.append(os.path.join(root, name))

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

    return {
        "counts": counts,
        "python_file_count": len(python_files),
        "file_types": file_types,
    }


def _format_statistics_answer(stats: Dict[str, Any]) -> str:
    counts = stats["counts"]
    file_count = stats["python_file_count"]
    code_lines = counts["lines"] - counts["empty_lines"] - counts["comment_lines"]
    parts = [
        "## Code Statistics",
        f"- **{counts['function']}** standalone functions",
        f"- **{counts['method']}** class methods",
        f"- **{counts['class']}** classes",
        f"- **{file_count}** Python files",
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
    return "\n".join(parts)


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
            "content": _format_statistics_answer(stats),
            "metadata": {"question": question, "format": "text/markdown"},
        }

    chunks = retriever.retrieve(question)
    answer = state.generator.generate(question, chunks)
    return {
        "content": answer,
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
