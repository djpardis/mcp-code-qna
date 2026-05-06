# mcp-code-qna

A small [Model Context Protocol](https://modelcontextprotocol.io)–style server that answers questions about a local Python repository.

It AST-parses the repo, embeds each class/function/method with [SentenceTransformers](https://sbert.net), retrieves with FAISS, and generates Markdown answers using intent-specific templates (purpose, implementation, parameter usage, error handling, statistics, etc.).

## Quickstart

```bash
pip install -e .
python -m spacy download en_core_web_sm

python scripts/generate_sample_repo.py /tmp/sample-python-repo
python -m app.mcp_web_server --repo-path /tmp/sample-python-repo
```

Open <http://localhost:8000> and ask "What does class `UserService` do?".

> The first run downloads a SentenceTransformer model (~270 MB) and caches it.

## Run the server

```bash
# With a default repo
python -m app.mcp_web_server --repo-path /path/to/repo

# Dynamic mode — clients pass `repo_path` per request
python -m app.mcp_web_server

# Custom port (default 8000)
python -m app.mcp_web_server --repo-path /path/to/repo --port 8002
```

## Ask from the CLI

```bash
python -m app.cli --repo-path /path/to/repo "What does class UserService do?"
```

## HTTP API

```bash
# Metadata
curl http://localhost:8000/.well-known/mcp

# List resources
curl http://localhost:8000/list_resources

# Ask a question (used by the web UI)
curl -X POST http://localhost:8000/question \
  -H 'Content-Type: application/json' \
  -d '{"question": "What does class UserService do?", "repo_path": "/path/to/repo"}'

# MCP-style read_resource
curl -X POST http://localhost:8000/read_resource \
  -H 'Content-Type: application/json' \
  -d '{"uri": "questions", "parameters": {"question": "...", "repo_path": "/path/to/repo"}}'
```

OpenAPI docs at <http://localhost:8000/docs>.

`repo_path` may be omitted when the server was started with `--repo-path`.

## Repository agent

With a server running, generate an architecture / dependency / design-pattern report in JSON, Markdown, and HTML:

```bash
python scripts/mcp_agent.py \
  --server-url http://localhost:8000 \
  --repo-path /path/to/repo \
  --repo-type other \
  --output-dir reports
```

Output: `reports/<repo-type>/<repo-name>_report_<ts>.{json,md,html}`.

## Evaluation

`run_test_evaluation.py` runs a fixed question set against the server and reports an **MCP Quality Score** (MQS) on a 0–10 scale, weighted 70% pass rate / 30% response time.

```bash
python evaluation_scripts/run_test_evaluation.py \
  --server-url http://localhost:8000 \
  --repo-path /tmp/sample-python-repo \
  --repo-type sample_repo
```

Two question banks ship: `sample_repo` (for the generated repo above) and `grip` (for a clone of [joeyespo/grip](https://github.com/joeyespo/grip)). Results are written to `evaluation_results/<repo-name>_<ts>.json`.

## Architecture

```
question ─► QuestionUnderstanding (intent + entities, spaCy)
                 │
                 ▼
            Retriever (FAISS, cosine on SentenceTransformer embeddings)
                 │
                 ▼
            AnswerGenerator (intent-specific Markdown templates)
                 │
                 ▼
              answer
```

The indexer caches embeddings and the FAISS index in `<repo>/.code_index/`, so subsequent runs against the same repo are fast.

## Layout

```
app/
  mcp_web_server.py    # FastAPI server + web UI (entry: `python -m app.mcp_web_server`)
  cli.py               # one-off CLI Q&A     (entry: `python -m app.cli`)
  indexer/             # AST parsing + embeddings + FAISS
  retriever/           # cosine-similarity search
  generator/           # question understanding + answer templates
  static/              # web UI assets
scripts/
  mcp_agent.py             # repo-analysis agent
  generate_sample_repo.py  # writes a tiny demo repo
evaluation_scripts/
  eval_framework.py        # shared POST + MQS + question banks
  run_test_evaluation.py   # `--repo-type sample_repo|grip`
  run_simple_evaluation.py # sample_repo bank only
  run_comprehensive_evaluation.py  # grip bank only
tests/                     # question-understanding tests
```

## Troubleshooting

- **First run is slow.** SentenceTransformer downloads ~270 MB on first use.
- **Port already in use.** Pass `--port 8001`, or `lsof -i :8000` to find the offender.
- **`OSError: en_core_web_sm`.** Run `python -m spacy download en_core_web_sm`.
- **`No repository path provided`.** Pass `--repo-path` to the server, or include `repo_path` in each request.

## License

MIT.
