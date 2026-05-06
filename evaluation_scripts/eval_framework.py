"""Shared helpers for MCP server evaluation scripts (question banks, HTTP, MQS)."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import difflib
import requests

# Question banks aligned with tests/test_sample_repo_question_understanding.py and Grip smoke list.
SAMPLE_REPO_QUESTIONS: List[str] = [
    "How many functions are there in the codebase?",
    "Count the number of classes in the project",
    "What does the processData function do?",
    "Explain the purpose of UserManager class",
    "How is the authentication system implemented?",
    "What methods does the FileHandler class have?",
    "How do I use the connect_database function?",
    "Explain the user_authentication_service",
    "What does the UserAuthenticationService do?",
    "Explain the userAuthenticationService",
]

GRIP_QUESTIONS: List[str] = [
    "How do I run grip from command line on a specific port?",
    "Can I modify and distribute the Grip software, and are there any conditions I need to follow?",
    "What command-line arguments does grip accept?",
    "How do I install grip and its dependencies?",
    "How can I use grip to preview a specific markdown file?",
    "What is ReadmeNotFoundError exception? Please give a usage example.",
    "DirectoryReader - please explain the purpose of the class.",
    "What is the purpose of the app.py file?",
    "What does the render_content function do?",
    "What is the purpose of the path_type function?",
    "How does Grip handle the rendering of GitHub-style task lists?",
    "How does Grip handle GitHub API authentication for rate limiting?",
    "How does Grip parse command line arguments?",
    "How does Grip handle different markdown flavors?",
    "What is the implementation of the export feature?",
    "How does Grip implement caching for API responses?",
]

def post_question(
    question: str,
    server_url: str,
    repo_path: Optional[str],
    *,
    timeout: float = 60.0,
) -> Tuple[Dict[str, Any], float]:
    """POST to `/question`; return ``(body, elapsed_seconds)``."""
    started = time.perf_counter()
    payload: Dict[str, Any] = {"question": question}
    if repo_path:
        payload["repo_path"] = repo_path
    try:
        response = requests.post(
            f"{server_url.rstrip('/')}/question",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=timeout,
        )
        elapsed = time.perf_counter() - started
        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}"}, elapsed
        return response.json(), elapsed
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Request failed: {exc}"}, time.perf_counter() - started


def calculate_mqs(results: List[Dict[str, Any]]) -> Dict[str, float]:
    """Weighted 30% latency / 70% error-free rate, scaled to 0–10."""
    if not results:
        return {
            "mqs": 0.0,
            "avg_response_time": 0.0,
            "error_rate": 1.0,
            "time_score": 0.0,
            "error_score": 0.0,
        }
    times = [r["response_time_seconds"] for r in results]
    avg_rt = sum(times) / len(times)
    errs = sum(1 for r in results if "error" in (r.get("answer") or "").lower())
    err_rate = errs / len(results)
    time_score = max(0.0, 10.0 - avg_rt * 5.0) if avg_rt < 2.0 else 0.0
    err_score = 10.0 * (1.0 - err_rate)
    mqs = time_score * 0.3 + err_score * 0.7
    return {
        "mqs": round(mqs, 2),
        "avg_response_time": round(avg_rt, 2),
        "error_rate": round(err_rate, 2),
        "time_score": round(time_score, 2),
        "error_score": round(err_score, 2),
    }


def similarity_ratio(a: str, b: str) -> float:
    """Cheap text similarity for comparing an answer to a reference (0–1)."""

    def clean(text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        text = re.sub(r"#+\s+", "", text)
        text = re.sub(r"[*_`]", "", text)
        return re.sub(r"\s+", " ", text).strip().lower()

    return difflib.SequenceMatcher(None, clean(a), clean(b)).ratio()


def save_run_report(payload: Dict[str, Any], output_dir: str, repo_name: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{repo_name}_{int(time.time())}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    return path


def run_question_batch(
    questions: List[str],
    server_url: str,
    repo_path: Optional[str] = None,
    *,
    output_dir: Optional[str] = None,
    timeout: float = 60.0,
    reference_answers: Optional[List[str]] = None,
    include_mqs: bool = True,
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, float]]]:
    """Ping the server for each question; optionally compute MQS and write JSON."""
    print(f"Running {len(questions)} questions · {server_url} · repo={repo_path or 'default'}")
    print("-" * 60)
    results: List[Dict[str, Any]] = []
    for i, q in enumerate(questions, 1):
        print(f"[{i}/{len(questions)}] {q}")
        body, elapsed = post_question(q, server_url, repo_path, timeout=timeout)
        if "error" in body and "content" not in body:
            ans = f"ERROR: {body['error']}"
            print(f"  -> {ans}")
        else:
            ans = body.get("content") or "No content in response"
            print(f"  -> {elapsed:.2f}s")
        row: Dict[str, Any] = {
            "question_id": i,
            "question": q,
            "answer": ans,
            "response_time_seconds": round(elapsed, 3),
        }
        if reference_answers is not None and i <= len(reference_answers):
            row["similarity"] = similarity_ratio(ans, reference_answers[i - 1])
            print(f"     similarity(reference)={row['similarity']:.2f}")
        results.append(row)

    mqs: Optional[Dict[str, float]] = None
    if include_mqs and results:
        mqs = calculate_mqs(results)
        print("-" * 60)
        print(f"MQS {mqs['mqs']}/10  errors {mqs['error_rate']:.0%}  avg_rt {mqs['avg_response_time']}s")

    if output_dir and results:
        repo_name = os.path.basename(repo_path) if repo_path else "default"
        payload: Dict[str, Any] = {
            "total_questions": len(results),
            "repository_path": repo_path,
            "results": results,
        }
        if mqs:
            payload["average_response_time"] = mqs["avg_response_time"]
            payload["mqs"] = mqs
        path = save_run_report(payload, output_dir, repo_name)
        print(f"Saved {path}")

    return results, mqs
