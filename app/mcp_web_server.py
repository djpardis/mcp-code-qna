"""FastAPI server for the lightweight, local-first v2 code question answering tool."""

from __future__ import annotations

import argparse
import logging
import os
from typing import Any, Dict, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.analysis import AnalysisEngine

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


class ServerState:
    """Small in-memory state for repository analysis."""

    def __init__(self, engine: Optional[AnalysisEngine] = None) -> None:
        self.default_repo_path: Optional[str] = None
        self._engine: Optional[AnalysisEngine] = engine

    @property
    def engine(self) -> AnalysisEngine:
        if self._engine is None:
            self._engine = AnalysisEngine()
        return self._engine

    def set_default_repo(self, repo_path: Optional[str], *, build: bool = False) -> None:
        if not repo_path:
            self.default_repo_path = None
            return
        self.default_repo_path = os.path.abspath(repo_path)
        if build:
            self.engine.build_repo(self.default_repo_path)

    def answer(self, question: str, repo_path: Optional[str]) -> Dict[str, Any]:
        requested_repo = repo_path or self.default_repo_path
        if not question.strip():
            return {
                "content": "Please provide a question.",
                "evidence": [],
                "citations": [],
                "limitations": ["No question was provided."],
                "metadata": {"format": "text/markdown", "mode": "v2", "error": "Empty question"},
            }
        if not requested_repo:
            return {
                "content": "No repository path provided. Start the server with `--repo-path` or include `repo_path`.",
                "evidence": [],
                "citations": [],
                "limitations": ["No repository path was provided."],
                "metadata": {
                    "format": "text/markdown",
                    "mode": "v2",
                    "error": "No repository path provided",
                },
            }
        try:
            return self.engine.answer(question, requested_repo).to_response(question)
        except ValueError as exc:
            return {
                "content": str(exc),
                "evidence": [],
                "citations": [],
                "limitations": [str(exc)],
                "metadata": {"format": "text/markdown", "mode": "v2", "error": str(exc)},
            }

    def status(self, repo_path: Optional[str] = None) -> Dict[str, Any]:
        requested_repo = repo_path or self.default_repo_path
        return {
            "server": "mcp-code-qna",
            "version": "2.0.0-alpha.1",
            "product_thesis": (
                "A lightweight, local-first evidence engine for repositories: "
                "index source locally, retrieve cited evidence, and use optional provider synthesis."
            ),
            "mode": "v2",
            "default_repo_path": self.default_repo_path,
            "analysis": self.engine.status(requested_repo),
        }


state = ServerState()  # engine is lazy — provider_from_env() runs on first request

app = FastAPI(
    title="MCP Code Repository Question Answering",
    description="Local-first repository evidence and cited answer generation.",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/.well-known/mcp")
async def get_mcp_metadata():
    return {
        "api_version": "0.2.0",
        "server_name": "local-first-code-evidence",
        "server_version": "2.0.0-alpha.1",
        "capabilities": ["list_resources", "read_resource", "question", "status"],
        "description": "Lightweight local-first repository question answering with cited evidence.",
    }


@app.get("/list_resources")
async def list_resources():
    return {
        "resources": [
            {
                "uri": "questions",
                "title": "Repository question answering",
                "description": "Ask grounded questions about a local repository.",
                "metadata": {
                    "repo_path": state.default_repo_path,
                    "mode": "v2",
                    "provider": state.engine.provider.name,
                    "supports_evidence": True,
                    "local_first": True,
                },
            }
        ],
        "cursor": None,
    }


@app.get("/status")
async def status(repo_path: Optional[str] = None):
    return state.status(repo_path)


@app.post("/index")
async def build_index(request: Request):
    """Pre-build the index for a repo so the status panel shows file/chunk counts immediately."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"detail": "Invalid JSON body"})
    repo_path = (data.get("repo_path") or "").strip()
    if not repo_path or not os.path.isdir(repo_path):
        return JSONResponse(status_code=400, content={"detail": "Invalid or missing repo_path"})
    repo_map = state.engine.build_repo(repo_path)
    return {"repo_path": repo_path, "repo_map": repo_map}


@app.get("/list_repo_candidates")
async def list_repo_candidates(root: Optional[str] = None, limit: int = 200):
    """Return local directory candidates for the repo picker UI."""
    base = os.path.abspath(root or os.path.expanduser("~/Documents"))
    if not os.path.isdir(base):
        return {"root": base, "repos": []}

    repos = []
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
    return state.answer(question, repo_path)


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
    return state.answer(question, repo_path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local-first code evidence server")
    parser.add_argument(
        "--repo-path",
        "-r",
        dest="repo_path",
        help="Default repository path. Omit to run in dynamic mode.",
    )
    parser.add_argument("--rebuild", action="store_true", help="Build the in-memory index on startup")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    return parser


def main(argv: Optional[list[str]] = None) -> None:
    args = _build_parser().parse_args(argv)
    state.set_default_repo(args.repo_path, build=args.rebuild)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
