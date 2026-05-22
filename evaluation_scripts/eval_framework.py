"""Shared helpers for local-first evidence evaluation scripts."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import difflib

SAMPLE_REPO_QUESTIONS: List[str] = [
    "What does this repository do?",
    "What does UserService do?",
    "Where is authentication implemented?",
    "What does Database do?",
    "What does OrderProcessor do?",
    "What files provide the main behavior?",
    "What dependencies does this project declare?",
    "How does user creation work?",
]

def post_question(
    question: str,
    server_url: str,
    repo_path: Optional[str],
    *,
    timeout: float = 60.0,
) -> Tuple[Dict[str, Any], float]:
    """POST to `/question`; return ``(body, elapsed_seconds)``."""
    import requests

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


def calculate_quality_metrics(results: List[Dict[str, Any]]) -> Dict[str, float]:
    """Evaluate grounded-answer quality signals exposed by the v2 API."""
    if not results:
        return {
            "quality_score": 0.0,
            "citation_rate": 0.0,
            "evidence_rate": 0.0,
            "groundedness_score": 0.0,
            "abstention_rate": 0.0,
            "avg_response_time": 0.0,
        }

    total = len(results)
    cited = 0
    evidenced = 0
    grounded = 0
    abstained = 0
    complete = 0
    for row in results:
        answer = (row.get("answer") or "").lower()
        citations = row.get("citations") or []
        evidence = row.get("evidence") or []
        if citations:
            cited += 1
        if evidence:
            evidenced += 1
        if evidence and citations:
            grounded += 1
        if "insufficient evidence" in answer or "could not find enough" in answer:
            abstained += 1
        if len(answer.split()) >= 25 or abstained:
            complete += 1

    citation_rate = cited / total
    evidence_rate = evidenced / total
    groundedness = grounded / total
    completeness = complete / total
    abstention_rate = abstained / total
    avg_rt = sum(r["response_time_seconds"] for r in results) / total
    quality = (
        citation_rate * 0.25
        + evidence_rate * 0.25
        + groundedness * 0.25
        + completeness * 0.15
        + max(0.0, 1.0 - min(avg_rt / 10.0, 1.0)) * 0.10
    ) * 10.0
    return {
        "quality_score": round(quality, 2),
        "citation_rate": round(citation_rate, 2),
        "evidence_rate": round(evidence_rate, 2),
        "groundedness_score": round(groundedness, 2),
        "answer_completeness": round(completeness, 2),
        "abstention_rate": round(abstention_rate, 2),
        "avg_response_time": round(avg_rt, 2),
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
            "citations": body.get("citations") or [],
            "evidence": body.get("evidence") or [],
            "confidence": (body.get("confidence") or body.get("metadata", {}).get("confidence")),
            "mode": body.get("metadata", {}).get("mode"),
            "provider": body.get("metadata", {}).get("provider"),
        }
        if reference_answers is not None and i <= len(reference_answers):
            row["similarity"] = similarity_ratio(ans, reference_answers[i - 1])
            print(f"     similarity(reference)={row['similarity']:.2f}")
        results.append(row)

    mqs: Optional[Dict[str, float]] = None
    quality = calculate_quality_metrics(results)
    if include_mqs and results:
        mqs = calculate_mqs(results)
        print("-" * 60)
        print(f"MQS {mqs['mqs']}/10  errors {mqs['error_rate']:.0%}  avg_rt {mqs['avg_response_time']}s")
        print(
            "Quality "
            f"{quality['quality_score']}/10  citations {quality['citation_rate']:.0%}  "
            f"evidence {quality['evidence_rate']:.0%}"
        )

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
        payload["quality"] = quality
        path = save_run_report(payload, output_dir, repo_name)
        print(f"Saved {path}")

    return results, mqs
