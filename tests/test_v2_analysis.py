from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.analysis import AnalysisEngine
from app.analysis.evidence import EvidenceItem
from app.analysis.index import RepositoryIndex, tokenise
from app.analysis.llm import LLMProvider
from app.analysis.retrieval import RetrievalPlanner


class _EchoProvider:
    """Test stub: echoes back the symbols from evidence as a simple answer."""

    name = "echo"

    def generate(self, question: str, evidence: list[EvidenceItem], repo_summary: str) -> str:
        symbols = [e.symbol for e in evidence if e.symbol]
        return f"Evidence includes: {', '.join(symbols) or 'none'}. {repo_summary[:80]}"
from evaluation_scripts.eval_framework import calculate_quality_metrics


def _write_sample_repo(root: Path) -> None:
    (root / "README.md").write_text("# Sample service\n\nA FastAPI app for billing reports.\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "sample-service"\ndependencies = ["fastapi>=0.110"]\n',
        encoding="utf-8",
    )
    (root / "app.py").write_text(
        '''
from fastapi import FastAPI

app = FastAPI()

class BillingService:
    """Builds customer billing reports."""

    def report_total(self, invoices):
        return sum(invoice.total for invoice in invoices)
'''.strip()
        + "\n",
        encoding="utf-8",
    )


def test_repository_index_extracts_docs_config_and_symbols(tmp_path: Path) -> None:
    _write_sample_repo(tmp_path)
    (tmp_path / "package-lock.json").write_text('{"large":"lock file"}', encoding="utf-8")
    index = RepositoryIndex(str(tmp_path)).build()

    assert index.repo_map["file_count"] == 3
    assert "billingservice" in index.symbols
    assert any(chunk.chunk_type == "documentation" for chunk in index.chunks)
    assert any(chunk.chunk_type == "config" for chunk in index.chunks)
    assert not any(source.rel_path == "package-lock.json" for source in index.files)


def test_tokenise_splits_code_identifiers() -> None:
    tokens = tokenise("UserAuthenticationService user_authentication_service")

    assert "userauthenticationservice" in tokens
    assert "user" in tokens
    assert "authentication" in tokens
    assert "service" in tokens


def test_hybrid_retrieval_returns_line_cited_evidence(tmp_path: Path) -> None:
    _write_sample_repo(tmp_path)
    index = RepositoryIndex(str(tmp_path)).build()
    result = RetrievalPlanner(index).retrieve("What does BillingService do?")

    assert result.evidence
    assert result.evidence[0].rel_path == "app.py"
    assert result.evidence[0].start_line >= 1
    assert "symbol" in result.evidence[0].source or "lexical" in result.evidence[0].source


def test_analysis_engine_returns_grounded_response(tmp_path: Path) -> None:
    _write_sample_repo(tmp_path)
    result = AnalysisEngine(provider=_EchoProvider()).answer(
        "What does BillingService do?",
        str(tmp_path),
    )

    response = result.to_response("What does BillingService do?")
    assert response["metadata"]["mode"] == "v2"
    assert response["evidence"]
    assert response["citations"]
    assert "BillingService" in response["content"]


def test_quality_metrics_score_citations_and_evidence() -> None:
    metrics = calculate_quality_metrics(
        [
            {
                "answer": "The service builds billing reports using cited source evidence.",
                "citations": ["app.py:5-9"],
                "evidence": [{"rel_path": "app.py"}],
                "response_time_seconds": 0.2,
            }
        ]
    )

    assert metrics["citation_rate"] == 1.0
    assert metrics["evidence_rate"] == 1.0
    assert metrics["quality_score"] > 8.0
