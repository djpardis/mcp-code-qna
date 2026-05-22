# Security

## Supported versions

Security fixes target the latest released version.

## Reporting a vulnerability

Please open a private security advisory on GitHub or contact the maintainer through GitHub.

## Local code and LLM providers

`mcp-code-qna` analyzes local repositories. With a local provider (Ollama), source snippets stay on your machine. In hosted LLM mode, retrieved evidence snippets are sent to the configured provider. Use local provider mode for private or sensitive repositories.

Never commit API keys, tokens, provider secrets, real `.env` files, generated indexes, or local model configuration that contains secrets.
