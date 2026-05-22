<img src="app/static/logo.svg" width="80" height="80" alt="mcp-code-qna logo">

# mcp-code-qna

![CI](https://github.com/djpardis/mcp-code-qna/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

Ask questions about a code repository and get answers grounded in cited source evidence.

`mcp-code-qna` retrieves relevant code snippets first, then asks a model to synthesise an answer from that evidence. Every answer includes the source files and line ranges it was derived from. The retrieval always runs locally. Only the selected snippets are sent to a hosted model.

Selecting a repo builds an in-memory index of symbols extracted via AST (Python) or regex (JS/TS), a BM25 token index, and a repo map. Each question is classified by type, scored against the symbol and token indexes, and the top-ranked snippets are sent to the model as a grounding prompt. The model sees only those excerpts, not the full repository, to keep context focused and avoid hitting token limits.

## Quick start

Requires [uv](https://docs.astral.sh/uv/):

```bash
brew install uv          # macOS; see docs.astral.sh/uv for other platforms
uv sync
```

Configure a model provider (see [LLM providers](#llm-providers)), then:

```bash
uv run mcp-server
```

Open the URL printed in the terminal, pick a repository, and start asking questions.

## LLM providers

Set `MCP_CODE_QNA_LLM_PROVIDER` before starting the server.

**Local via Ollama:**

```bash
brew install ollama
ollama serve
ollama pull qwen2.5-coder:7b

export MCP_CODE_QNA_LLM_PROVIDER=local
export MCP_CODE_QNA_LOCAL_MODEL=qwen2.5-coder:7b
uv run mcp-server
```

Any OpenAI-compatible local server works. Override the default Ollama endpoint with `MCP_CODE_QNA_LOCAL_BASE_URL`.

**Hosted OpenAI-compatible:**

```bash
export MCP_CODE_QNA_LLM_PROVIDER=openai
export MCP_CODE_QNA_OPENAI_BASE_URL=<base-url>
export MCP_CODE_QNA_OPENAI_API_KEY=<api-key>
export MCP_CODE_QNA_OPENAI_MODEL=<model-name>
uv run mcp-server
```

## CLI

For one-off questions without starting a server:

```bash
uv run mcp-ask --repo-path /path/to/repo "What does UserService do?"
```

## Limitations

**Retrieval may be unnecessary for small repos with large-context models.** Most small-to-medium codebases fit within the context window of modern models (128k+ tokens). The retrieval step adds the most value when the repo is too large for context, when you want inspectable cited evidence, or when minimising what leaves your machine matters. For a local 7B model like [qwen2.5-coder:7b](https://ollama.com/library/qwen2.5-coder) or [deepseek-coder-v2](https://ollama.com/library/deepseek-coder-v2) on a small repo, dumping the full repo into context would often give equal or better results.

**JS/TS symbol extraction is regex-based.** Python uses the AST for accurate symbol boundaries. JS/TS uses regex patterns, which can miss some constructs. The right fix is a [tree-sitter](https://tree-sitter.github.io/) parser.

**Indexes are in-memory and not persisted.** The index is built on first use and dropped on server restart. Large repos can be slow to index.

**No vector search or embeddings.** Retrieval is lexical and symbol-based. It works well when the question shares terms with the code, but can miss conceptual or paraphrased questions. Dense retrieval is not included by default to keep the install lightweight; adding it as an optional extra is planned.

**Answer quality depends on the model.** Small local models (7B and below) can give sparse answers on complex architecture questions. Larger hosted models produce noticeably better synthesis.

**File size cap.** Files over 512 KB are skipped. Override with `MCP_CODE_QNA_MAX_FILE_BYTES`.

## License

MIT. See [LICENSE](LICENSE).
