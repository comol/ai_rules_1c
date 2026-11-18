---
name: 1c-templates-memory
description: "Reusable 1C code templates from the templates MCP. Use when the selected 1C workflow needs a template; memory-only work enters through project-memory.md."
argument-hint: "<task description | memory query>"
allowed-tools: mcp__1c-templates-mcp__templatesearch, mcp__1c-templates-mcp__get_template, mcp__1c-templates-mcp__list_templates, mcp__1c-templates-mcp__recall, mcp__1c-templates-mcp__remember
---

# 1c-templates-memory — templates and project memory

Template obligations and rejection criteria: `content/rules/mcp-policy.md → A. Priority and obligation`, items 8–9. Memory is a separate route below.

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

For memory-only work, load `content/rules/project-memory.md` directly. It owns provider selection, exact ordinary calls, recall scope, durable writes, bounded recovery and the `Memory:` line; this template workflow adds no memory prerequisites.
