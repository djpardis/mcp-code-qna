"""Command-line interface for asking one-off questions about a repo.

Use the server (`python -m app.mcp_web_server`) when you want the HTTP API and web
UI; this CLI is for quick local question answering without spinning up a server.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.analysis import AnalysisEngine


def ask(repo_path: str, question: str, *, rebuild_index: bool = False) -> str:
    # v2 indexes are in-memory, so rebuild_index is kept for CLI compatibility.
    return AnalysisEngine().answer(question, repo_path).content


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Ask a grounded question about a code repository.")
    parser.add_argument("--repo-path", dest="repo_path", required=True, help="Path to the repository")
    parser.add_argument("--rebuild-index", action="store_true", help="Force rebuild of the index")
    parser.add_argument("question", help="The question to ask")
    args = parser.parse_args(argv)

    answer = ask(args.repo_path, args.question, rebuild_index=args.rebuild_index)
    print(answer)


if __name__ == "__main__":
    main()
