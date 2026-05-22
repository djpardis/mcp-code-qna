from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi.testclient import TestClient

from app.analysis import AnalysisEngine
from app.analysis.evidence import EvidenceItem
from app.mcp_web_server import ServerState, app


class _EchoProvider:
    """Test stub: echoes symbol names so no real model is needed."""

    name = "echo"

    def generate(self, question: str, evidence: List[EvidenceItem], repo_summary: str) -> str:
        symbols = [e.symbol for e in evidence if e.symbol]
        return f"Evidence includes: {', '.join(symbols) or 'none'}."


# Inject the stub before any test runs.
state = ServerState(engine=AnalysisEngine(provider=_EchoProvider()))

import app.mcp_web_server as _srv  # noqa: E402
_srv.state = state


def _write_sample_repo(root: Path) -> None:
    (root / "README.md").write_text("# Sample service\n\nA local-first billing tool.\n", encoding="utf-8")
    (root / "service.py").write_text(
        '''
class BillingService:
    """Builds customer billing reports."""

    def report_total(self, invoices):
        return sum(invoice.total for invoice in invoices)
'''.strip()
        + "\n",
        encoding="utf-8",
    )


def test_question_endpoint_returns_cited_evidence(tmp_path: Path) -> None:
    _write_sample_repo(tmp_path)
    state.set_default_repo(None)

    client = TestClient(app)
    status = client.get("/status")
    assert status.status_code == 200
    assert status.json()["mode"] == "v2"

    response = client.post(
        "/question",
        json={"question": "What does BillingService do?", "repo_path": str(tmp_path)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["mode"] == "v2"
    assert body["evidence"]
    assert body["citations"]
    assert body["citations"][0].startswith("service.py:")
