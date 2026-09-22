---
name: 1c-templates-memory
description: "Reuse before reinventing — search the code-template library with the user's task description, adapt a fitting template as the base, and recall / save project memory across the connected providers (Cognee, OpenViking, templates MCP). Use at the start of every non-trivial 1C task and in the same turn as any user correction."
argument-hint: "<task description | memory query>"
allowed-tools: mcp__1c-templates-mcp__templatesearch, mcp__1c-templates-mcp__get_template, mcp__1c-templates-mcp__list_templates, mcp__1c-templates-mcp__recall, mcp__1c-templates-mcp__remember
---

# 1c-templates-memory — templates and project memory

Two separate obligations. Policy owners: templates — `AGENTS.md → MCP Tool Calling → A.8–A.9`; memory — `content/rules/project-memory.md` (recall-first, correction-capture, write priority Cognee → OpenViking → templates, `memory.md` as the strict fallback).

## Templates

| Need | Call | Arguments |
|---|---|---|
| Find a ready pattern | `templatesearch` | `query` = the user's task **as Russian prose**, verbatim or a same-goal paraphrase — never keywords, never query-language tokens |
| Read a hit in full | `get_template` | `template_id` |
| Browse | `list_templates` | `limit=50`, `offset=0`, follow `next_offset` |
| Persist a pattern (explicit request only) | `add_template` | `description`, `code` |

Pre-flight before every `templatesearch`: the query reads as complete sentences with subject and goal; no `ВЫБРАТЬ` / `ПОМЕСТИТЬ` / `СОЕДИНЕНИЕ` unless the user wrote them; on a miss rephrase as another task description, at most two attempts. Keyword salad is a defect equal to skipping the tool.

A goal-matching hit is the base: paste its body, adapt names, filters, placement and call site, keep the proven structure. Reject only for doc-confirmed incompatibility, an explicit requirement or a named rule violation. Report one line: `Template: <name> — used as base` / `— used as base, fixed: <anti-pattern>` / `— rejected: <reason>` / «no fitting template».

```json
{"tool": "templatesearch", "args": {"query": "Есть справочник с неограниченной иерархией. Нужно запросом вывести все группы и уровень иерархии каждой группы"}}
{"tool": "get_template", "args": {"template_id": "<id from the hit>"}}
```

## Memory

| Need | Call | Arguments |
|---|---|---|
| Recall (every provider, every non-trivial task) | `recall` | `query` = key terms of the task; Cognee: `search_type="CHUNKS"`; OpenViking: `search(query)` |
| Save a durable fact / correction | `remember` | Cognee `data`, `dataset_name`; OpenViking `messages=[{"role":"user","content":…}]`; templates `content` (≥ 5 chars) |

```json
{"tool": "recall", "args": {"query": "проведение реализации резерв склад"}}
{"tool": "remember", "args": {"content": "Проект ЗУП: движения по регистру ТоварыНаСкладах формируются только в ОбщийМодуль.ПроведениеСервер, не в модуле документа (исправление пользователя 2026-09-18)"}}
```

`remember` on the current templates server is always registered and needs no operator token or write-tools opt-in. `add_template` and `plugin_reload` remain conditional on enabled write tools and the operator bearer header. Use the live tool surface for older deployments; an absent `remember` or an actual authorization rejection follows the documented memory fallback, with no blind retry or token pre-flight. A `stored=true` / `index_pending=true` answer is durable. No secrets or PII in notes. Report the `Memory:` evidence line.

Typed answers map to actions by code — `content/rules/mcp-policy.md → C. Server answers → actions`. Details: `content/skills/mcp-1c-tools/docs/1c-templates-mcp.md`, `content/skills/mcp-1c-tools/docs/memory-providers.md`.
