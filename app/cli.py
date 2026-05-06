"""Command-line interface for asking one-off questions about a repo.

Use the server (`python -m app.mcp_web_server`) when you want the HTTP API and web
UI; this CLI is for quick local Q&A without spinning up a server.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.generator.answer_generator import AnswerGenerator
from app.indexer.code_indexer import CodeIndexer
from app.retriever.retriever import Retriever


def ask(repo_path: str, question: str, *, rebuild_index: bool = False) -> str:
    indexer = CodeIndexer(repo_path=repo_path)
    if rebuild_index:
        indexer.build_index()
    else:
        indexer.load_or_build_index()
    retriever = Retriever(indexer=indexer)
    chunks = retriever.retrieve(question)
    return AnswerGenerator().generate(question, chunks)


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Ask a question about a Python code repository.")
    parser.add_argument("--repo-path", dest="repo_path", required=True, help="Path to the repository")
    parser.add_argument("--rebuild-index", action="store_true", help="Force rebuild of the index")
    parser.add_argument("question", help="The question to ask")
    args = parser.parse_args(argv)

    answer = ask(args.repo_path, args.question, rebuild_index=args.rebuild_index)
    print(answer)


if __name__ == "__main__":
    main()
