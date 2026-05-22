# Roadmap

Future work after the v2 evidence-first rebuild. Completed items are no longer tracked here; see git history and releases.

## Indexing and retrieval
- Persist v2 indexes to disk and add incremental re-indexing.
- Add full parsers for JS/TS and other high-value languages.
- Add call graph and import graph extraction.
- Add optional cross-encoder reranking for top evidence.

## Answer quality
- Add judge-assisted evals for citation correctness and completeness.
- Add streaming responses for long hosted or local LLM answers.
- Improve abstention when evidence is low-confidence or contradictory.

## Product
- Add saved conversations and exportable evidence reports.
- Add repository ignore/include controls from the UI.
- Add authentication and rate limiting for shared deployments.

## Open source
- Track eval scores across releases.
- Add more fixture repositories that model real-world project shapes.
- Publish reproducible release notes for each alpha, beta, and stable version.
