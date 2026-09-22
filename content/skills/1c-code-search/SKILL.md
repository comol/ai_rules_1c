---
name: 1c-code-search
description: "Find BSL code in a 1C project — routines by name, code by behaviour or exact literal, module layout, members of a context — through the graph and code-metadata MCP servers before any Grep. Use whenever a task needs to locate or read a fragment of BSL it does not yet have a path for."
argument-hint: "<what to find> [exact | semantic]"
allowed-tools: mcp__1c-graph-metadata-mcp__search_code, mcp__1c-code-metadata-mcp__codesearch, mcp__1c-code-metadata-mcp__search_function, mcp__1c-code-metadata-mcp__get_module_structure, mcp__1c-code-metadata-mcp__bsl_scope_members, mcp__1c-code-metadata-mcp__compact_symbol
---

# 1c-code-search — locate BSL code

Project-source search is MCP-first within verified contour coverage: graph → mapped code-metadata → `grep=true` retry → scoped native `Grep` with a one-line fallback note. Skip uncovered lanes; never substitute a neighboring contour's index. `content/rules/multi-contour-search.md` selects scope and server mappings for multiple roots; `content/rules/mcp-first-search.md` owns retrieval, freshness and native exceptions. This skill owns the calls below; any shared-server scope arguments must match its live contract.

## Tools and exact arguments

| Need | Call | Arguments (exact names) |
|---|---|---|
| Code by behaviour / intent | `search_code` (graph) | `query`, `search_type="semantic"`, `detail_level="L1"`, `top_k=3`, optional `filter_type` |
| Code by identifier / literal | `search_code` (graph) | `query`, `search_type="fulltext"`; miss → `codesearch(query, grep=true)` |
| Hybrid fallback | `codesearch` (code) | `query`, `limit=5`, `grep=false` — result count is `limit`, never `top_k` |
| Routine by name | `search_function` (code) | `name`, `exact=true`, `limit=10`, `grep=false` |
| Full routine body | `search_code` | `detail_level="L0"` for one routine; or `compact_symbol(name, include_body=true)` |
| Module layout before editing | `get_module_structure` (code) | `module_path` |
| Members of a context | `bsl_scope_members` (code) | `context` (`Справочник.Номенклатура`, `Глобальный`), `member_type="all" \| "methods" \| "properties" \| "events"` |

`query` is the only search input name on both servers — not `q`, `text`, `prompt`, `search_query`.

## Calls

```json
{"tool": "search_code", "args": {"query": "расчёт остатков по складу на дату", "search_type": "semantic", "detail_level": "L1", "top_k": 5}}
{"tool": "search_function", "args": {"name": "ОбработкаПроведения", "exact": true, "limit": 10}}
{"tool": "codesearch", "args": {"query": "ТекущаяДатаСеанса()", "limit": 5, "grep": true}}
{"tool": "get_module_structure", "args": {"module_path": "Documents/РеализацияТоваровУслуг/Ext/ObjectModule.bsl"}}
```

## Miss handling

1. Reformulate once (mode, `detail_level`, `top_k` / `limit`, `filter_type`) before switching tools.
2. `grep=true` only on `codesearch`, `search_function`, `metadatasearch`, `helpsearch`, `search_forms`, and only for literal material: identifier, query fragment, handler name, error text.
3. A typed server answer maps to an action by code — `content/rules/mcp-policy.md → C. Server answers → actions`; never probe the same gap through sibling tools.
4. Then native `Grep` / `Read`, with the note. Reading a file already located here is normal work.

Rare modes, response shapes, compact API paging: `content/skills/mcp-1c-tools/docs/1c-code-metadata-mcp.md`, `content/skills/mcp-1c-tools/docs/1c-graph-metadata-mcp.md`.
