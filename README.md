# mcp-code-qna

A small [Model Context Protocol](https://modelcontextprotocol.io)-style server that answers questions about local code repositories.

It parses code into chunks, embeds each class/function/method with [SentenceTransformers](https://sbert.net), retrieves with FAISS, and generates concise Markdown answers using intent-specific templates (purpose, implementation, parameter usage, error handling, statistics, and more).

## How it works

1. You provide a repository path and ask a question.
2. The server indexes source files into code chunks (functions/classes/methods) and stores vector embeddings.
3. For normal Q&A, it retrieves the most relevant chunks with FAISS similarity search, then generates a concise answer.
4. For direct analysis questions (stats, framework detection, repository purpose), it uses deterministic repository scanning and fallback logic.

## Quick start

```bash
pip install -e .
python -m spacy download en_core_web_sm

python scripts/generate_sample_repo.py /tmp/sample-python-repo
python -m app.mcp_web_server --repo-path /tmp/sample-python-repo
```

> The first run downloads a SentenceTransformer model (~270 MB) and caches it.

## Run the server

```bash
# With a default repo
python -m app.mcp_web_server --repo-path /path/to/repo

# Dynamic mode — clients pass `repo_path` per request
python -m app.mcp_web_server
```

## Ask from the CLI

```bash
python -m app.cli --repo-path /path/to/repo "What does class UserService do?"
```

## HTTP API

```bash
# Get server metadata
curl -sS <server-url>/.well-known/mcp

# List available resources
curl -sS <server-url>/list_resources

# Ask a question
curl -sS -X POST <server-url>/question \
  -H 'Content-Type: application/json' \
  -d '{"question":"What does this repository do?","repo_path":"/path/to/repo"}'

# Read the MCP "questions" resource
curl -sS -X POST <server-url>/read_resource \
  -H 'Content-Type: application/json' \
  -d '{"uri":"questions","parameters":{"question":"Summarize the main service","repo_path":"/path/to/repo"}}'
```

Use your running server address for `<server-url>`.
You can omit `repo_path` in requests when the server was started with a default `--repo-path`.

## Repository agent

With a server running, generate an architecture/dependency/design-pattern report in JSON, Markdown, and HTML:

```bash
python scripts/mcp_agent.py \
  --server-url <server-url> \
  --repo-path /path/to/repo \
  --output-dir reports
```

Output: `reports/<repo-name>_report_<ts>.{json,md,html}`.

## Evaluation

`run_test_evaluation.py` runs a fixed question set against the server and reports an **MCP Quality Score** (MQS) on a 0-10 scale, weighted 70% pass rate and 30% response time.

```bash
python evaluation_scripts/run_test_evaluation.py \
  --server-url <server-url> \
  --repo-path /tmp/sample-python-repo
```

Evaluation results are written to `evaluation_results/<repo-name>_<ts>.json`.

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

The indexer caches embeddings and the FAISS index in `<repo>/.code_index/`, so subsequent runs against the same repository are faster.

## Works best with

- **Python repos**: strongest support (AST chunking + retrieval).
- **JS/TS repos**: basic-to-good support for Q&A and stats.
- **Template-heavy sites** (`.html`, `.htm`, `.njk`): stats include template macros and inline `<script>` JS.
- **Mixed repos**: generally fine, but retrieval quality depends on how much source code vs assets/docs the repo contains.

## Known issues and limits

- Statistics for non-Python repositories are heuristic, because JS/TS/template counts use regex patterns and may be approximate.
- Template-heavy repositories may include many asset and documentation files, so file-type distribution can dominate results.
- Very large repositories can take longer on first run because embedding generation and indexing are compute-heavy.
- Non-code folders (for example, asset backups or media dumps) can still be selected, which may produce low-signal answers.
- The project does not yet include a full multi-language parser; Python uses AST parsing, while JS/TS/template analysis remains heuristic.

## Project layout

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
  run_test_evaluation.py   # default evaluation question batch
  run_simple_evaluation.py # sample-repo question batch
  run_comprehensive_evaluation.py  # Grip-style question batch
tests/                     # question-understanding tests
```

## License

This project is released under the MIT License. See `LICENSE` for details.
