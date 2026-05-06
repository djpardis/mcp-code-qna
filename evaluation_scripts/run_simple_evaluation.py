#!/usr/bin/env python3
"""Quick eval: sample-repo question list only (no --repo-type)."""

from __future__ import annotations

import argparse
from typing import List, Optional

from eval_framework import SAMPLE_REPO_QUESTIONS, run_question_batch


def main(argv: Optional[List[str]] = None) -> None:
    p = argparse.ArgumentParser(description="Run sample-repo smoke questions against the server.")
    p.add_argument("--server-url", default="http://localhost:8000")
    p.add_argument("--repo-path")
    p.add_argument("--output-dir", default="evaluation_results")
    p.add_argument("--timeout", type=float, default=60.0, help="Per-request HTTP timeout (seconds)")
    args = p.parse_args(argv)
    run_question_batch(
        SAMPLE_REPO_QUESTIONS,
        args.server_url,
        args.repo_path,
        output_dir=args.output_dir,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    main()
