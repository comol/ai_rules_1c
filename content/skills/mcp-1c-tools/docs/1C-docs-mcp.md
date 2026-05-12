# 1C-docs-mcp — tool catalog

1C platform documentation: search by description (vector + BM25) and exact lookup by name.

> Load this file only if the `1C-docs-mcp` server is actually available in the current session.

| Tool | Purpose | When to use |
|---|---|---|
| **docsearch** | Search the platform documentation by description (hybrid: vector + BM25). Single argument: `query` (string) | Find built-in functions by description, look up platform features when the exact name is unknown |
| **docinfo** | Look up platform documentation by exact object / method name | Get documentation for a known name (`"ТаблицаЗначений"`, `"Массив.Найти"`, `"Запрос"`) |

## Notes

- **Prefer `docinfo` for known names** — exact lookup is faster and more precise than semantic search.
- **`docsearch` is for fuzzy / semantic search** when the exact name is unknown.
- When verifying a platform method / type during writing or review — always cross-check against the documentation; functions and signatures change between platform versions.
