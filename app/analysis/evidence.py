"""Shared evidence and answer data structures for v2 code question answering."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class EvidenceItem:
    """A line-addressable source snippet used to ground an answer."""

    id: str
    path: str
    rel_path: str
    start_line: int
    end_line: int
    evidence_type: str
    snippet: str
    score: float
    source: str
    symbol: Optional[str] = None
    language: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def citation(self) -> str:
        if self.start_line and self.end_line:
            return f"{self.rel_path}:{self.start_line}-{self.end_line}"
        return self.rel_path

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AnswerResult:
    """Generated answer plus metadata needed by API, UI, and evals."""

    content: str
    evidence: List[EvidenceItem]
    citations: List[str]
    confidence: str
    mode: str
    provider: str
    limitations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_response(self, question: str) -> Dict[str, Any]:
        return {
            "content": self.content,
            "evidence": [item.to_dict() for item in self.evidence],
            "citations": self.citations,
            "confidence": self.confidence,
            "limitations": self.limitations,
            "metadata": {
                "question": question,
                "format": "text/markdown",
                "mode": self.mode,
                "provider": self.provider,
                **self.metadata,
            },
        }
