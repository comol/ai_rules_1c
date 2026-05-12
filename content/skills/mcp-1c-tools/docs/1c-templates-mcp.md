# 1c-templates-mcp — tool catalog

Code template library (`templatesearch`) and project vector memory (`remember` / `recall`). Memory routing rules — `AGENTS.md → Project Memory`.

> Load this file only if the `1c-templates-mcp` server is actually available in the current session.

| Tool | Parameters | Purpose | When to use |
|---|---|---|---|
| **templatesearch** | `query` | Hybrid search (semantic + fulltext) over the code-template library (2000+ entries) | Find architectural patterns and implementation examples **before** writing code |
| **remember** | `content` (≥ 5 chars) | Save a free-form note to project memory (vector-indexed) | Persist a project-specific fact, user correction, or non-obvious decision that should survive across tasks |
| **recall** | `query` | Vector search over saved notes | At the start of any non-trivial task — recall earlier corrections, decisions, and project-specific quirks |

## Notes on `remember`

- Write in Russian, one self-contained fact per note, including the affected object / module.
- Do not save secrets or PII.
- Call `remember` proactively: when the user corrects you, clarifies a non-obvious detail, or adjusts your interpretation of the task.
- Call `recall` at the start of any non-trivial task with key terms (object name, subsystem, error message).

## Availability check

Treat the server as **available** only if the `remember` and `recall` tools are actually present in the current session's tool schema. The mere presence of `1c-templates-mcp` in `mcp-servers.json` does not prove availability. If `recall` returns a connection error — switch to memory fallback mode (see `AGENTS.md → Project Memory → Fallback`).
