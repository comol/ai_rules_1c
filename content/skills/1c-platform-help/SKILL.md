---
name: 1c-platform-help
description: "External knowledge for 1C work — platform syntax reference by name or description, the platform-capability check before hand-rolling a specialized mechanism, БСП / SSL reusable APIs, routed project standards, file-format specifications, ITS standards and configuration documentation — through the docs, SSL and code-check MCP servers. Use only when a versioned platform fact, a БСП API or a standard affects the task."
argument-hint: "<name | capability description> [version]"
allowed-tools: mcp__1C-docs-mcp__docsearch, mcp__1C-docs-mcp__docinfo, mcp__1C-docs-mcp__standards, mcp__1C-docs-mcp__formatspec, mcp__1c-ssl-mcp__ssl_search, mcp__1c-code-check-mcp__its_help, mcp__1c-code-check-mcp__fetch_its, mcp__1c-code-check-mcp__search_1c_documentation, mcp__1c-code-check-mcp__config_help, mcp__1c-code-metadata-mcp__helpsearch
---

# 1c-platform-help — platform, БСП, standards, ITS

Conditional knowledge: call when the task depends on versioned platform behaviour, a reusable БСП API or standards compliance; never for prose cleanup. Model memory is not evidence of a platform feature's absence.

## Tools and exact arguments

| Need | Call | Arguments |
|---|---|---|
| Known type / method | `docinfo` | `name` (`"ТаблицаЗначений"`, `"Массив.Найти"`), optional `doc_type`, `scope`, `detail_level="compact"` |
| Feature by description | `docsearch` | `query` (Russian description of the capability), `top_k`, `scope="syntax" \| "docs" \| "all"` |
| Routed project standard | `standards` | `name="<rule stem>"` (`anti-patterns`, `dev-standards-architecture`); `query=` searches the collection; no args = catalogue — never `docsearch` for a standard |
| On-disk XML format | `formatspec` | `name=` / `query=` |
| БСП reusable API | `ssl_search` | `query` (exact symbol or Russian description), `limit=5`, `detail="compact"`; fetch one hit with `doc_id`, `detail="full"` |
| ITS standard | `its_help` → `fetch_its` | `query` → `id` for **every** document relied on |
| Version-specific docs | `search_1c_documentation` | `query`, `version="v8.3.25"`; changes between versions — `diff_1c_documentation_versions` |
| Typical-configuration docs | `config_help` | `query` |
| Project help articles | `helpsearch` (code) | `query`, `limit`, `grep` |

There is no `corpus` argument on the docs server; `scope` never reaches `standards` / `formatspec`.

## Calls

```json
{"tool": "docinfo", "args": {"name": "ХранилищеЗначения", "detail_level": "compact"}}
{"tool": "docsearch", "args": {"query": "решение системы линейных уравнений", "scope": "all", "top_k": 5}}
{"tool": "standards", "args": {"name": "locks-and-transactions"}}
{"tool": "ssl_search", "args": {"query": "ОбщегоНазначения.ЗначениеРеквизитаОбъекта", "detail": "compact"}}
{"tool": "its_help", "args": {"query": "длительные операции"}}
{"tool": "fetch_its", "args": {"id": "<id from its_help>"}}
```

## Platform-capability check (hard gate, `AGENTS.md → A.7`)

Before a custom implementation in a specialized domain (cryptography, СЛАУ, data analysis, collaboration system / bots, integration bus / queues, full-text search, regex, archives, geo, background work): `docsearch` by capability, 1–2 reformulations → `docinfo` for every exact name found → `ssl_search` where a БСП solution is plausible. Found and usable → build on it, custom code for glue only. Partial fit → `CONFUSION`. Rejecting a found mechanism needs doc-confirmed incompatibility, stated in the answer.

## Reading the answers

`outcome: "not_found"` on the docs server and `not_found` on SSL are finished answers, not retries; `ambiguous_name` on SSL returns candidates — refine by signature. Documents are paged (`next_cursor`), a first page is not the whole standard. Typed answers map to actions by code — `content/rules/mcp-policy.md → C. Server answers → actions`.

Details: `content/skills/mcp-1c-tools/docs/1C-docs-mcp.md`, `content/skills/mcp-1c-tools/docs/1c-ssl-mcp.md`, `content/skills/mcp-1c-tools/docs/1c-code-check-mcp.md → Documentation & knowledge base`, `content/rules/help-corpus-retrieval.md`.
