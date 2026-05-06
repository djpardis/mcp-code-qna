# Roadmap

Future work, grouped by area. Completed items are no longer tracked here — see git history.

## Scaling and performance
- Support repos that don't fit in a single embedding batch (streaming / batched indexing).
- Cache responses for repeated questions.
- Incremental re-indexing on file changes.
- Optional GPU embedding generation.

## Retrieval and answering
- Hybrid sparse + dense retrieval (BM25 + embeddings).
- Cross-encoder reranking of top-k results.
- LLM-backed answer generation (today's templates are deterministic).
- Citations to specific files / line ranges in answers.
- Multi-language support beyond Python (TS / Go / Java).

## Question understanding
- Replace regex-driven intent matching with a small classifier.
- Better entity extraction for code identifiers (especially across naming conventions).
- Disambiguate questions that reference multiple matching symbols.

## Server / API
- Auth + rate limiting.
- Streaming responses for long answers.
- API versioning.

## Evaluation
- Wire up reference-answer comparison (e.g. against `Modelcode-ai/grip_qa`).
- Track MQS over time across commits.
- Per-question-type breakdown of error rate.

## DX
- Pre-commit hooks (ruff / black).
- CI (lint + tests).
- IDE plugins for inline Q&A.
