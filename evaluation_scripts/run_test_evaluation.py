#!/usr/bin/env python3
"""CLI: run a default evaluation question batch."""

from __future__ import annotations

import argparse
from typing import List, Optional

from eval_framework import SAMPLE_REPO_QUESTIONS, run_question_batch


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Run MCP evaluation against the default question bank.")
    parser.add_argument("--server-url", default="http://localhost:8000")
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--output-dir", default="evaluation_results")
    args = parser.parse_args(argv)
    run_question_batch(SAMPLE_REPO_QUESTIONS, args.server_url, args.repo_path, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
