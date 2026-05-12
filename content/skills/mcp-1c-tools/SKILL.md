---
name: mcp-1c-tools
description: "Catalog of MCP servers for 1C development — search, code navigation, metadata, code review, docs, ITS, templates. Use whenever a 1C task requires calling tools from any 1c-*-mcp / 1C-*-mcp server. Each server has its own detail file under `docs/` — load it when you are about to call tools from that server, and only if the server is actually available in the current session."
---

# MCP tools for 1C — dispatcher

This skill is the single entry point into the project's catalog of MCP servers. Detailed per-tool descriptions for each server live in separate files under `docs/`. **Load a specific `docs/<server>.md` when you are about to call tools from that server and want to tune parameters; the server must be actually available in the current session** (its tools are exposed in the tool schema; the mere presence of an entry in `mcp-servers.json` does not count as availability).

## What is mandatory vs. recommended

- **Mandatory: calling the MCP tool when it is needed.** If the task could benefit from an MCP tool and the server is exposed in the current session, calling it is non-optional. Not calling counts as a defect. See `AGENTS.md → Tool Calling Rules § A`.
- **Recommended: reading `docs/<server>.md` before parameter-rich calls.** Reading the schema is for parameter tuning, not a hard gate. Skipping it is acceptable only when the call is genuinely simple (a one-shot lookup with obvious arguments) and you are not invoking a parameter-rich tool listed below.

### Parameter-rich tools — read the doc first

For these tools default parameters are usually suboptimal; consult the server's `docs/<server>.md` before the first call in the session and adjust the parameters to the task:

- `1c-graph-metadata-mcp`: `search_code` (`search_type`, `detail_level`), `search_metadata` (JSON templates), `search_metadata_by_description` (`alpha`, `use_fuzzy`), `trace_impact` (`direction`, `depth`, `relationship_types`), `trace_call_chain` (`direction`, `depth`), `get_object_dossier` (`sections`), `business_search` (`include_structure`, `filter_type`).
- `1c-code-metadata-mcp`: `metadatasearch` (`object_type`, `names_only`), `get_method_call_hierarchy` (`direction`, `depth`), `graph_dependencies` (`direction`), `bsl_scope_members` (`member_type`).

If `docs/<server>.md` conflicts with the descriptor exposed by the current environment, the environment descriptor wins.

## When to use this skill

- Before writing code / a query / metadata XML — pick the MCP tool that best fits the task (template search, metadata check, syntax validation, code review).
- For impact analysis and code navigation — decide which server to use first (`graph` → `code-metadata` → `Grep` — see *Fallback chain* below).
- For ITS standards (`its_help` → `fetch_its`) and platform documentation (`docinfo` / `docsearch`).
- For code templates and project memory (`templatesearch`, `remember`, `recall`).

> Short tool-calling rules (priority, limits, no-duplicate-call discipline) — in `AGENTS.md → Tool Calling Rules`. This skill holds the catalog and per-server schemas.

## Server catalog

| Server (id) | Purpose | Details |
|---|---|---|
| **1c-graph-metadata-mcp** | Graph metadata (Neo4j / Cypher): structural object passport, impact analysis, call graph, usage search, business semantic search | [`docs/1c-graph-metadata-mcp.md`](docs/1c-graph-metadata-mcp.md) |
| **1c-code-metadata-mcp** | Metadata and BSL code search, navigation (modules, procedures, functions, call hierarchy), forms, XSD schemas, validation | [`docs/1c-code-metadata-mcp.md`](docs/1c-code-metadata-mcp.md) |
| **1c-templates-mcp** | Code template library + project vector memory (`remember` / `recall`) | [`docs/1c-templates-mcp.md`](docs/1c-templates-mcp.md) |
| **1c-ssl-mcp** | Standard Subsystems Library (БСП / SSL) search | [`docs/1c-ssl-mcp.md`](docs/1c-ssl-mcp.md) |
| **1C-docs-mcp** | 1C platform documentation (search by description / by exact name) | [`docs/1C-docs-mcp.md`](docs/1C-docs-mcp.md) |
| **1c-code-check-mcp** | 1С:Напарник — code review, technical check, AI rewrite/modify, ITS documentation | [`docs/1c-code-check-mcp.md`](docs/1c-code-check-mcp.md) |
| **1c-syntax-checker-mcp** | BSL syntax and style via BSL Language Server | [`docs/1c-syntax-checker-mcp.md`](docs/1c-syntax-checker-mcp.md) |

## Fallback chain (highest priority to lowest)

Before falling back to `Grep` / `rg`, **exhaust applicable MCP tools in this strict order**:

1. `1c-graph-metadata-mcp`
2. `1c-code-metadata-mcp`
3. `1c-templates-mcp`
4. `1c-ssl-mcp`
5. `1C-docs-mcp`
6. `1c-code-check-mcp` (`its_help` → `fetch_its` for ITS standards)
7. only then `Grep` / `rg` — with a mandatory short note in the response listing which MCP tools were tried and why they did not return what was needed.

## Quick map: "task → MCP tool"

| Task | First choice (graph) | Fallback (code-metadata) |
|---|---|---|
| BSL code search | `search_code` (`fulltext` / `semantic` / `hybrid`, `detail_level` L0–L3) | `codesearch` |
| Metadata object structure | `get_object_dossier` | `get_metadata_details` |
| Impact analysis before refactoring | `trace_impact` (recursive, depth 1–10) | `graph_dependencies` (single-level) |
| Call graph | `trace_call_chain` | `get_method_call_hierarchy` |
| Metadata search by name / structure | `search_metadata` (JSON templates) | `metadatasearch` |
| Object usage search | `find_objects_using_object` / `find_usages_of_object` | `graph_dependencies` (`direction="reverse"`) |
| Description / synonym / comment search | `search_metadata_by_description` | `metadatasearch` (`names_only=true`) |

Step-by-step playbooks per task type (writing code, review, architecture, error fixing, performance, refactoring, metadata XML, forms, integrations, documentation, comparing platform versions) — `tooling-playbooks.md`.
