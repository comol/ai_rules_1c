---
description: Entry point for 1C query work — pick the exact companion rules and skill docs for writing, optimizing, and reviewing queries. Load first for any non-trivial query task; load companions only via the routing table below.
alwaysApply: false
category: development
---

# Query Design — Entry Point

Router for query work: load it first, then only the companions the table selects. Hard rules live in `standards(name="dev-standards-architecture") §3 → "Queries"`; how-to composition and optimization in the `1c-metadata-manage` skill docs; severity and fix templates in `standards(name="anti-patterns")`.

## Routing

| Task | Load |
|---|---|
| Project hard rules (formatting, `КАК`, parameters, no queries in loops, intermediate result variable, virtual-table filters) | `standards(name="dev-standards-architecture") §3 → "Queries"` |
| Write a new query from scratch (skeleton, virtual tables, temp tables, joins, totals) | `content/skills/1c-metadata-manage/docs/query-writing.md` |
| Tune an existing query (joins vs subqueries, temp-table indexing, index alignment, composite-type deref, DCS specifics) | `content/skills/1c-metadata-manage/docs/query-optimization.md` — **mandatory for any «оптимизируй запрос» task**; walk its *Mandatory Optimization Checklist* item by item |
| Anti-patterns and severity (query in loop, correlated subquery, VT filter in WHERE, missing `ПЕРВЫЕ N`, unindexed temp table, redundant `РАЗЛИЧНЫЕ`, batch + temp table) | `standards(name="anti-patterns")` (§1, §3a, §4, §5, §5a, §7b, Optimized Patterns → Batch Query with Temp Table) |
| Query inside a DCS / SKD report | `standards(name="dcs-design")` + `content/skills/1c-metadata-manage/docs/query-optimization.md` (DCS section) |
| Query against a register being designed / restructured | `standards(name="registers-design")` first, then this router |

## Pre-flight (every non-trivial query)

1. **Verify metadata** before the first `ВЫБРАТЬ` — `metadatasearch` / `get_metadata_details` / `get_object_dossier`; never invent attribute or tabular-section names.
2. **Find a proven shape** — `templatesearch` (task text verbatim; a hit is the base — `AGENTS.md → MCP Tool Calling → A.8–A.9`), `codesearch` / `search_code` for local patterns.
3. **Pick the right source** — catalog / document / information-register slice / accumulation virtual table (`Остатки`, `Обороты`, `ОстаткиИОбороты`); a wrong source is a design defect, not a tuning problem.
4. **Apply the hard rules** of `standards(name="dev-standards-architecture") §3`; preserve slice semantics when moving virtual-table filters (`standards(name="anti-patterns") §4`).
5. **Temp-table / union checklist** for every multi-batch query: each temp table later used in a `СОЕДИНЕНИЕ` / `ОБЪЕДИНИТЬ` / `В (ВЫБРАТЬ …)` has `ИНДЕКСИРОВАТЬ ПО` on its join keys (the 2–3 most selective fields); no `РАЗЛИЧНЫЕ` inside `ОБЪЕДИНИТЬ` operands or on top of `СГРУППИРОВАТЬ ПО`; correlated subqueries replaced by an indexed temp table + join; virtual-table periodicity matches the join keys; a virtual table joined directly only when its parameters already narrow it (`content/skills/1c-metadata-manage/docs/query-optimization.md → Joins with Virtual Tables`).
6. **Smoke-check the finished text** — `validatequery` (`1c-data-mcp`) on every query before it lands in a module or a DCS scheme, when the server is exposed and the connected IB is a dev / test base (`verification-gates.md → Gate 3a`); mandatory right after a non-deterministic `rewrite_1c_code` / `modify_1c_code` output.

## Virtual-table parameters

- **The condition is one argument.** `СрезПоследних(&Период, Организация = &Организация И Валюта = &Валюта)` — predicates are joined with `И`; a comma after the period starts the *next* parameter, it is not a shorthand for `И` (`Остатки(&Момент, Склад = &Склад, Номенклатура = &Номенклатура)` is wrong).
- **`СрезПервых` / `СрезПоследних` exist only for periodic information registers** (`InformationRegisterPeriodicity` other than `Nonperiodical`); a non-periodic register is read as a plain table. Check the periodicity in the metadata card before writing the slice.
- **Resource fields of a virtual table are derived names** — `КоличествоОстаток`, `СуммаОборот`, `КоличествоНачальныйОстаток`, `КоличествоПриход` / `КоличествоРасход` — not the resource name itself. Take them from the register's metadata card (`get_metadata_details` / `get_object_dossier`, the virtual tables and their fields when the card lists them); never guess the suffix.

## Load order

`query-design.md` → `standards(name="dev-standards-architecture") §3 → "Queries"` (hard rules) → `content/skills/1c-metadata-manage/docs/query-writing.md` **or** `content/skills/1c-metadata-manage/docs/query-optimization.md` (how-to) → `standards(name="anti-patterns")` (only when reviewing / fixing).

## Out of scope

Metadata XML for registers / documents — `standards(name="registers-design")` / the `1c-metadata-manage` skill; form-module data loading — `forms.md` → `form-module.md`; lock / transaction boundaries around query + write — `standards(name="locks-and-transactions")`.
