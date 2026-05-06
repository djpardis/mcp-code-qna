#!/usr/bin/env python3
"""CLI: run evaluations with built-in sample_repo / grip question banks."""

from __future__ import annotations

import argparse
from typing import List, Optional

from eval_framework import QUESTION_BANKS, run_question_batch


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Run MCP evaluation against a fixed question bank.")
    parser.add_argument("--server-url", default="http://localhost:8000")
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--output-dir", default="evaluation_results")
    parser.add_argument(
        "--repo-type",
        choices=sorted(QUESTION_BANKS.keys()),
        required=True,
    )
    args = parser.parse_args(argv)
    questions = QUESTION_BANKS[args.repo_type]
    run_question_batch(questions, args.server_url, args.repo_path, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
