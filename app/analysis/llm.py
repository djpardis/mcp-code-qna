"""LLM provider abstraction for grounded answer generation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Protocol

from app.analysis.evidence import EvidenceItem


class LLMProvider(Protocol):
    name: str

    def generate(self, question: str, evidence: List[EvidenceItem], repo_summary: str) -> str:
        """Return a Markdown answer grounded in the supplied evidence."""


@dataclass
class OpenAICompatibleProvider:
    """Hosted or local provider that speaks the OpenAI chat-completions API."""

    name: str
    base_url: str
    model: str
    api_key: str = ""
    timeout: float = 60.0

    def generate(self, question: str, evidence: List[EvidenceItem], repo_summary: str) -> str:
        import requests

        prompt = build_grounded_prompt(question, evidence, repo_summary)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = requests.post(
            f"{self.base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a code analyst helping developers understand a codebase. "
                            "Prioritise the source code evidence provided — quote and cite it directly. "
                            "You may use your general knowledge to interpret or explain patterns you see "
                            "in the evidence (e.g. what a design pattern means, how a framework works), "
                            "but every factual claim about *this* codebase must be backed by a snippet. "
                            "Cite sources inline as `file:start-end`. "
                            "If the evidence does not contain enough to answer, say so and explain "
                            "what you can infer from what is available."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


def provider_from_env() -> LLMProvider:
    provider = os.getenv("MCP_CODE_QNA_LLM_PROVIDER", "").strip().lower()
    if provider in {"openai", "hosted"}:
        return OpenAICompatibleProvider(
            name="hosted",
            base_url=os.getenv("MCP_CODE_QNA_OPENAI_BASE_URL", "https://api.openai.com/v1"),
            model=os.getenv("MCP_CODE_QNA_OPENAI_MODEL", "gpt-4o-mini"),
            api_key=os.getenv("MCP_CODE_QNA_OPENAI_API_KEY", ""),
            timeout=float(os.getenv("MCP_CODE_QNA_LLM_TIMEOUT", "60")),
        )
    if provider in {"local", "ollama", "lmstudio", "openai-compatible"}:
        return OpenAICompatibleProvider(
            name="local",
            base_url=os.getenv("MCP_CODE_QNA_LOCAL_BASE_URL", "http://localhost:11434/v1"),
            model=os.getenv("MCP_CODE_QNA_LOCAL_MODEL", "llama3.1"),
            api_key=os.getenv("MCP_CODE_QNA_LOCAL_API_KEY", ""),
            timeout=float(os.getenv("MCP_CODE_QNA_LLM_TIMEOUT", "120")),
        )
    raise RuntimeError(
        "No model provider configured. "
        "Set MCP_CODE_QNA_LLM_PROVIDER to 'local' or 'openai' and configure the matching env vars. "
        "See README.md § LLM providers."
    )


def build_grounded_prompt(question: str, evidence: List[EvidenceItem], repo_summary: str) -> str:
    evidence_blocks = []
    for idx, item in enumerate(evidence, 1):
        block = "\n".join([
            f"[{idx}] {item.citation()} ({item.evidence_type}, symbol: {item.symbol or 'n/a'})",
            "```",
            item.snippet[:3000].strip(),
            "```",
        ])
        evidence_blocks.append(block)

    evidence_text = "\n\n".join(evidence_blocks)

    return (
        f"Repository context: {repo_summary}\n\n"
        "SOURCE EVIDENCE:\n\n"
        f"{evidence_text}\n\n"
        "INSTRUCTIONS:\n"
        "- Ground your answer in the evidence above. Cite inline as `file:start-end`.\n"
        "- Be direct and concise. Skip preamble — start with the answer.\n"
        "- You may explain patterns or conventions using general knowledge, but only to clarify what the evidence shows.\n"
        "- If the evidence is sparse, give your best answer from what is available and note any gaps.\n\n"
        f"Question: {question}"
    )
