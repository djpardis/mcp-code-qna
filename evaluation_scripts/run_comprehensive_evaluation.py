#!/usr/bin/env python3
"""Grip-style question list against a clone of joeyespo/grip."""

from __future__ import annotations

import argparse
from typing import List, Optional

from eval_framework import GRIP_QUESTIONS, run_question_batch


def main(argv: Optional[List[str]] = None) -> None:
    p = argparse.ArgumentParser(description="Run Grip-themed question batch.")
    p.add_argument("--server-url", default="http://localhost:8000")
    p.add_argument("--repo-path", help="Path to a Grip checkout")
    p.add_argument("--output-dir", default="evaluation_results")
    p.add_argument("--timeout", type=float, default=60.0)
    args = p.parse_args(argv)
    run_question_batch(
        GRIP_QUESTIONS,
        args.server_url,
        args.repo_path,
        output_dir=args.output_dir,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    main()
