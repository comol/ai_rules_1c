---
name: mcp-1c-tools
description: "Catalog of MCP servers for 1C development — search, code navigation, metadata, code review, docs, ITS, templates. Use whenever a 1C task requires calling tools from any 1c-*-mcp / 1C-*-mcp server. Each server has its own detail file under `docs/` — load it when you are about to call tools from that server, and only if the server is actually available in the current session."
---

# MCP tools for 1C — dispatcher

This skill is the single source of truth for the project's MCP server catalog, task→tool mapping, fallback order, and project-index search retries. Detailed per-tool descriptions for each server live in separate files under `docs/`. **Load a specific `docs/<server>.md` when you are about to call tools from that server and want to tune parameters; the server must be actually available in the current session** (its tools are exposed in the tool schema; the mere presence of an entry in `mcp-servers.json` does not count as availability).

## What is mandatory vs. conditional

- **Mandatory for risk-bearing 1C work.** If a relevant server is exposed, call the fitting MCP tool for BSL / metadata edits or review, metadata XML, forms, integrations, refactoring, performance, runtime errors, platform API checks, impact analysis, syntax / quality validation, and project-memory operations.
- **Conditional for external knowledge.** Use platform docs, БСП / SSL, and ITS MCP tools when the task depends on versioned platform behavior, reusable БСП APIs, or standards compliance. Do not call them for generic prose cleanup or rule-file editing unless such a fact is actually needed.
- **Not required for Markdown / rules / documentation-only work.** For rule files, README, commands documentation, and similar prose-only edits, validate structure, links, paths, and internal consistency instead of calling 1C project MCP tools.
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

> Short obligation rules and verification budgets live in `AGENTS.md → MCP Tool Calling` (sections A, B, C). This skill owns the MCP catalog, routing, and fallback details.

## Server catalog

| Server (id) | Purpose | Details |
|---|---|---|
| **1c-graph-metadata-mcp** | Graph metadata (Neo4j / Cypher): structural object passport, impact analysis, call graph, usage search, business semantic search | [`docs/1c-graph-metadata-mcp.md`](docs/1c-graph-metadata-mcp.md) |
| **1c-code-metadata-mcp** | Metadata and BSL code search, navigation (modules, procedures, functions, call hierarchy), forms, XSD schemas, validation | [`docs/1c-code-metadata-mcp.md`](docs/1c-code-metadata-mcp.md) |
| **1c-templates-mcp** | Code template library + project vector memory (`remember` / `recall`) | [`docs/1c-templates-mcp.md`](docs/1c-templates-mcp.md) |
| **1c-ssl-mcp** | Standard Subsystems Library (БСП / SSL) search | [`docs/1c-ssl-mcp.md`](docs/1c-ssl-mcp.md) |
| **1C-docs-mcp** | 1C platform documentation (search by description / by exact name) | [`docs/1C-docs-mcp.md`](docs/1C-docs-mcp.md) |
| **1c-code-check-mcp** | 1С:Напарник — code review, technical check, AI rewrite/modify, ITS documentation | [`docs/1c-code-check-mcp.md`](docs/1c-code-check-mcp.md) |
| **1c-syntax-checker-mcp** | BSL syntax and style via BSL Language Server: `syntaxcheck` (code as text) and `syntaxcheck_file` (check a file on disk by path, optionally line-filtered; exposed only when a sources directory is mounted — prefer it over `syntaxcheck` when available, it is cheaper) | [`docs/1c-syntax-checker-mcp.md`](docs/1c-syntax-checker-mcp.md) |
| **1c-data-mcp** | Live-IB execution: BSL fragment run (`vcexecutecode`), query run (`vcexecutequery`), query parse-check (`validatequery`), last event-log error (`vcloggetlasterror`) | [`docs/1c-data-mcp.md`](docs/1c-data-mcp.md) |

## Fallback chain (highest priority to lowest)

Use only the applicable branch; stop as soon as the collected evidence is sufficient. Before each call, check that it closes a concrete context gap and is not a duplicate of an earlier call.

### Project-source search before `Grep` / `rg`

`Grep` / `rg` substitute only the project-indexing layer. Before falling back to them for 1C project-source search, exhaust:

1. `1c-graph-metadata-mcp` — `search_code`, `search_metadata`, `search_metadata_by_description`, `get_object_dossier`, `trace_impact`, `trace_call_chain` as appropriate.
2. `1c-code-metadata-mcp` — default indexed search / navigation (`codesearch`, `metadatasearch`, `search_function`, `search_forms`, `get_module_structure`, etc.).
3. `1c-code-metadata-mcp` with `grep=true` — substring retry inside the MCP index **only after** indexed / semantic / exact search did not find enough and only for tools that expose the parameter: `codesearch`, `metadatasearch`, `search_function`, `helpsearch`, `search_forms`. Typical scenarios: exact identifier, fragment of a query, metadata path, event handler name, error text, or literal string where semantic search is likely to miss.
4. Only then `Grep` / `rg` — with a mandatory short note in the response listing which project-index MCP attempts were tried and why they did not return what was needed.

### External knowledge

These servers have no `Grep` / `rg` equivalent; call them only when their knowledge is needed:

1. `1c-templates-mcp` — code templates and project memory (`templatesearch`, `remember`, `recall`).
2. `1c-ssl-mcp` — БСП / SSL reusable APIs and patterns.
3. `1C-docs-mcp` — versioned platform documentation.
4. `1c-code-check-mcp` — 1С:Напарник checks, ITS standards (`its_help` → `fetch_its` for every document used), AI drafts.
5. `1c-syntax-checker-mcp` — BSL syntax / style validation after edits (prefer `syntaxcheck_file` over `syntaxcheck` when it is exposed — file check by path is more economical than passing code text).
6. `1c-data-mcp` — execution against the **live** infobase (run a BSL fragment, run a query, parse-check a query, fetch the last event-log error). No `Grep` / `rg` equivalent — there is no offline substitute for "what does this running IB do right now". Call only when the question genuinely requires the live IB; default to read-only fragments and ask before any mutation. Details — [`docs/1c-data-mcp.md`](docs/1c-data-mcp.md).

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

Step-by-step playbooks per task type (writing code, review, architecture, error fixing, performance, refactoring, metadata XML, forms, integrations, documentation, comparing platform versions) — `content/rules/tooling-playbooks.md`.
