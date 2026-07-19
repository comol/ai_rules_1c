---
description: Coding standards — forbidden constructs, comments, code review, module regions, queries, data access, performance (headlines + pointers)
alwaysApply: false
category: development
---

# Coding Standards (headlines)

Authoritative content for code style, naming, comments, queries, data access and performance lives in the detailed on-demand rules: `dev-standards-code-style.md`, `dev-standards-change-markers.md`, `dev-standards-architecture.md`, `module-structure.md`, `anti-patterns.md`, `platform-solutions.md`, `locks-and-transactions.md`, `logging-strategy.md`. Project / process parameters live separately in `dev-standards-env.md`; `dev-standards-core.md` is only their compatibility router. Managed-form work — start at the router `forms.md`, then load companions it selects (`form-patterns.md`, `forms-add.md`, `form-module.md`, `async-methods.md`, …). Query work — start at the router `query-design.md`. This file is the index of headlines and anchors. **Before writing or reviewing code, load the relevant detail file.**

## Forbidden Calls and Constructs (project-wide)

Single source of truth — `dev-standards-code-style.md §2 → "Forbidden Calls and Constructs"` (ternary `?(...)`, `Выполнить()` / `Вычислить()`, hardcoded credentials, `Сообщить()`, `ЗаписьЖурналаРегистрации()` without explicit task, `Попытка ... Исключение` around DB reads/writes, boolean comparison against `Истина` / `Ложь`, Yoda syntax). Naming bans (Hungarian notation, names from the 1C global context, magic numbers, negative boolean names) and the `[Project rule — stricter than ITS standard]` markers also live there. The `COMОбъект` ban is owned by `dev-standards-architecture.md §3 → "Cross-Platform Compatibility"`.

Do not duplicate the lists here — when a rule changes, only its owning file (`dev-standards-code-style.md §2` or `dev-standards-architecture.md §3`) is updated.

## Comments

Prefer self-documenting code. Comments are appropriate only when they add value: motivation, non-trivial algorithm, constraints / side effects, technical-debt markers (`TODO No.<task>: ...`), platform hacks. Comments that paraphrase the code or decorate modules with author / history banners are forbidden — git tracks that. Examples and the verification rule — `dev-standards-code-style.md §7`.

## Code Review After Each Edit

After any code edit, perform an internal review scaled to the path: quick-fix — correctness and edge cases of the changed fragment (plus locks / transactions when near transactional code); full-cycle — the full list (style, readability, correctness, edge cases, security, concurrency, locks, transactions). Always consider whether an outer transaction already exists (e.g., the object-write transaction) before opening a new one. A blocking validator defect requires a clean confirming run on the changed state within the budget from `AGENTS.md`; non-blocking style noise does not start another AI-review loop. Full guidance — `dev-standards-code-style.md §8`.

## Code Reuse

Before writing new code — check common and manager modules for an existing export method that can be reused. Use `search_function`, `ssl_search`, `templatesearch`, and `codesearch` **before** writing.

## Module Regions

Canonical region names — Russian, БСП-style. Templates per module type (common module, object / manager module, form module) — `module-structure.md`. Regions inside procedures / functions are forbidden; pseudo-regions via comments are forbidden.

## Managed Forms

Entry point — `forms.md` (load first for any form task). Companions selected by its routing table:

| Task | Load |
|---|---|
| Layout from scratch / unspecified placement | `form-patterns.md` |
| Create or structurally modify `Form.xml` | `forms-add.md`, `metadata-xml-workarounds.md` |
| Form-module code / event handlers / reserved names | `form-module.md` |
| Client-side `Асинх` / `Ждать` | `async-methods.md` |

Do not preload the whole set "to be safe" — follow the router.

## Queries

Entry point — `query-design.md` (load first for any non-trivial query task). Authoritative formatting and hard bans — `dev-standards-architecture.md §3 → "Queries"`. Headlines:

- Verify metadata before writing a query (`metadatasearch` / `get_metadata_details`).
- No queries inside loops — use batch queries with temporary tables (`ВТ_*`).
- Always parameterize (`Запрос.УстановитьПараметр()`), never concatenate strings.
- Always use `КАК` aliases. Use `ПЕРВЫЕ N` when only a subset is needed.
- Filter virtual tables by parameters, not by `ГДЕ`.
- Always use an intermediate variable for the query result (`РезультатЗапроса = Запрос.Выполнить();`); method chaining is forbidden.

## Data Access — Reference Attributes

Do not access reference attributes via dot notation (`Контрагент.ИНН`). Use `ОбщегоНазначения.ЗначениеРеквизитаОбъекта` / `ЗначенияРеквизитовОбъекта` / `ЗначениеРеквизитаОбъектов` / `ЗначенияРеквизитовОбъектов`. **[Project rule — stricter than ITS standard.]** Full method table and caching / batch templates — `dev-standards-architecture.md §4 → "Data Access — Reference Attribute Access"`.

## Performance

Authoritative baseline (server-side bulk, queries, privileged mode, caching, collections, transactions, managed locks) — `dev-standards-architecture.md §5`. Detailed anti-pattern catalog with severity — `anti-patterns.md`. Platform pitfalls (long-running operations, temporary storage, transactions, deadlocks, dates, collection search, external components) — `platform-solutions.md`.

## Project Rules Stricter Than the ITS Standard

Some project rules are intentionally **stricter** than the official 1C ITS standard. Each such rule in this file and in the on-demand rules is tagged with **`[Project rule — stricter than ITS standard]`**. When discussing such a rule with the user or in code review:

- Refer to it as a **project decision**, not as an ITS requirement.
- If asked — explicitly state the delta vs the ITS standard.
- Do not silently weaken these rules "to match ITS"; raise the question and let the user decide.
