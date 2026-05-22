# Contributing

Thanks for helping improve `mcp-code-qna`.

## Local setup

```bash
brew install uv
uv sync --extra dev
uv run python scripts/generate_sample_repo.py /tmp/sample-repo
```

Start the server against the sample repo:

```bash
export MCP_CODE_QNA_LLM_PROVIDER=local
export MCP_CODE_QNA_LOCAL_MODEL=qwen2.5-coder:7b
uv run mcp-server
```

## Tests and linting

```bash
uv run pytest
uv run ruff check .
```

Tests must not require a real API key or network access. Use the `_EchoProvider` stub (see `tests/test_api.py`) unless a test is explicitly testing provider integration.

## Evaluation

Run the built-in question batch against a running server:

```bash
uv run python evaluation_scripts/run_test_evaluation.py \
  --server-url <server-url> \
  --repo-path /tmp/sample-repo
```

Results are written to `evaluation_results/`. Metrics: citation rate, evidence coverage, groundedness score, abstention rate, average response time.

## Codebase layout

```
app/
  analysis/
    index.py        ingestion, symbol extraction, repo map
    retrieval.py    symbol + lexical + repo-map retrieval, query classification
    evidence.py     evidence and answer data contracts
    llm.py          OpenAI-compatible hosted and local providers
    engine.py       orchestration: index → retrieve → synthesise
  mcp_web_server.py FastAPI server and HTTP endpoints
  cli.py            one-shot CLI (mcp-ask entry point)
  static/           web UI (HTML, CSS, JS, SVG assets)
scripts/
  generate_sample_repo.py   generates a small Python repo for testing
evaluation_scripts/
  eval_framework.py         shared eval utilities and question bank
  run_test_evaluation.py    CLI runner for the default question batch
tests/
```

## HTTP API reference

```bash
# Status
curl <server-url>/status

# Ask a question
curl -X POST <server-url>/question \
  -H 'Content-Type: application/json' \
  -d '{"question":"Where are the API endpoints defined?","repo_path":"/path/to/repo"}'

# Pre-build the index for a repo
curl -X POST <server-url>/index \
  -H 'Content-Type: application/json' \
  -d '{"repo_path":"/path/to/repo"}'
```

## What good changes include

- New retrieval behaviour should include fixture-backed tests.
- New answer behaviour should preserve citations and insufficient-evidence handling.
- Provider changes must not commit secrets, real repository paths, or operator-specific config.
- README claims about quality should be backed by an eval result.

## Eval fixtures

Prefer small repositories where the expected evidence is obvious. Include both questions that should be answered and questions where the correct behaviour is to abstain.
