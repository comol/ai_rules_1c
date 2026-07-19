---
description: Entry point for 1C query work — pick the exact companion rules and skill docs for writing, optimizing, and reviewing queries. Load first for any non-trivial query task; load companions only via the routing table below.
alwaysApply: false
category: development
---

# Query Design — Entry Point

This file is the **router** for query work. Load it first, then load only the companion sources selected by the table below — companions are not auto-attached by file pattern.

> **Scope.** This file owns *routing and load order*. Authoritative hard rules (formatting, aliases, parameters, bans) live in `dev-standards-architecture.md §3 → "Queries"`. How-to composition and optimization live in the `1c-metadata-manage` skill docs. Severity catalog and fix templates — `anti-patterns.md`.

## Routing

| Task | Load |
|---|---|
| Project hard rules (formatting, `КАК`, parameters, no queries in loops, intermediate result variable, virtual-table filters) | `dev-standards-architecture.md §3 → "Queries"` |
| Write a new query from scratch (skeleton, virtual tables, temp tables, joins, totals) | `content/skills/1c-metadata-manage/docs/query-writing.md` |
| Tune an existing query (joins vs subqueries, index alignment, composite-type deref, DCS specifics) | `content/skills/1c-metadata-manage/docs/query-optimization.md` |
| Anti-patterns and severity (query in loop, VT filter in WHERE, missing `ПЕРВЫЕ N`, batch + temp table) | `anti-patterns.md` (§1, §4, §5, Optimized Patterns → Batch Query with Temp Table) |
| Query inside a DCS / SKD report | `dcs-design.md` + `query-optimization.md` (DCS section) |
| Query against a register being designed / restructured | `registers-design.md` first, then this router |

Each companion is self-contained — load only the ones that match the task. Do not preload the whole set "to be safe".

## Pre-flight (every non-trivial query)

1. **Verify metadata** before the first `ВЫБРАТЬ` — `metadatasearch` / `get_metadata_details` / `get_object_dossier`. Do not invent attribute or tabular-section names.
2. **Find a proven shape** — `templatesearch` / `codesearch` / `search_code` before inventing a new skeleton.
3. **Pick the right source** — catalog / document / information-register slice / accumulation virtual table (`Остатки`, `Обороты`, `ОстаткиИОбороты`). Wrong source is a design defect, not a tuning problem.
4. **Apply hard bans** from `dev-standards-architecture.md §3` — no queries in loops, always parameterize, always `КАК`, filter virtual tables by parameters (not `ГДЕ`), intermediate variable for `Запрос.Выполнить()`.

## Load order (recommended)

```
query-design.md (this file)
  → dev-standards-architecture.md §3 → "Queries"   # hard rules
  → query-writing.md OR query-optimization.md      # how-to
  → anti-patterns.md                               # only when reviewing / fixing
```

## Out of scope

- Metadata XML for registers / documents — `registers-design.md` / `1c-metadata-manage` skill.
- Form-module data loading patterns — `forms.md` → `form-module.md`.
- Lock / transaction boundaries around query + write — `locks-and-transactions.md`.
