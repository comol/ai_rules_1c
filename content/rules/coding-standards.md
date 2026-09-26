---
description: Coding standards index — which rule or routed standard owns forbidden constructs, naming, comments, module regions, queries, data access, performance, forms, and reuse; load before writing or reviewing BSL or metadata
alwaysApply: false
category: development
---

# Coding Standards — index

Load the owner that matches the task; do not preload the whole set. Routed standards (`standards(name="…")`) are fetched from `1C-docs-mcp` per `AGENTS.md → Path convention`. Precedence: where the code you edit already follows a different convention in a purely stylistic matter, the codebase wins (`AGENTS.md → Core Principles → "Codebase conventions first"`); ВерблюжьяНотация for identifiers and every non-style rule never yield.

| Topic | Owner |
|---|---|
| Formatting, quality limits, **forbidden constructs** (ternary `?(...)`, `Выполнить()` / `Вычислить()`, hardcoded credentials, `Сообщить()`, `ЗаписьЖурналаРегистрации()` without a task, `Попытка` around DB reads / writes, comparison with `Истина` / `Ложь`, Yoda syntax), **naming** (ВерблюжьяНотация; no Hungarian notation, global-context names, magic numbers, negative booleans) | `standards(name="dev-standards-code-style") §2` |
| Public procedure / function documentation | `standards(name="dev-standards-code-style") §5` |
| Typography (no «ё» in identifiers, quotes, dashes) | `standards(name="dev-standards-code-style") §6` |
| Comments — only motivation, non-trivial algorithm, constraints, `TODO No.<task>` markers, platform hacks; never paraphrase or author / history banners | `standards(name="dev-standards-code-style") §7` |
| Internal review after each edit (quick-fix: changed fragment + locks / transactions nearby; full-cycle: full list); outer-transaction check | `standards(name="dev-standards-code-style") §8`; budget — `verification-policy.md → Validator budget` |
| Change markers in typical code, metadata naming, object-type selection | `dev-standards-change-markers.md` |
| Module regions (Russian, БСП-style; no regions inside procedures) | `module-structure.md` |
| Architecture patterns, extensions, `COMОбъект` ban, client-server interaction, **query hard rules** (no queries in loops, parameters, `КАК` aliases, semantically equivalent virtual-table filter placement, `РезультатЗапроса = Запрос.Выполнить()`) | `standards(name="dev-standards-architecture") §2–§3` |
| Reference attributes — never dot notation (`Контрагент.ИНН`); `ОбщегоНазначения.ЗначениеРеквизитаОбъекта` and the batch variants **[Project rule — stricter than ITS standard]** | `standards(name="dev-standards-architecture") §4` |
| Performance baseline; anti-pattern catalog with severity; platform pitfalls | `standards(name="dev-standards-architecture") §5`, `standards(name="anti-patterns")`, `standards(name="platform-solutions")` |
| Queries — routing and pre-flight | `query-design.md` (load first for any non-trivial query) |
| Managed forms — routing | `forms.md` (load first; companions via its table) |
| Locks and transactions · logging · extensions · registers · СКД · БСП access rights | `standards(name="locks-and-transactions")` · `standards(name="logging-strategy")` · `standards(name="extension-patterns")` · `standards(name="registers-design")` · `standards(name="dcs-design")` (advanced two-pass composition — `standards(name="dcs-advanced-composition")`) · `standards(name="bsp-access-rights")` |

## Code reuse

Before writing new code: `search_function`, `ssl_search`, `templatesearch`, `codesearch` — an existing export method, a БСП API or a template beats new code. A `templatesearch` hit for the same task is the base (`AGENTS.md → MCP Tool Calling → A.9`); a specialized capability (cryptography, СЛАУ, data analysis, collaboration system, integration bus, full-text search, regex) triggers the platform-capability check before any custom implementation (`AGENTS.md → MCP Tool Calling → A.7`).

## Project rules stricter than the ITS standard

Rules tagged **`[Project rule — stricter than ITS standard]`** are project decisions, not ITS requirements: refer to them as such, state the delta vs ITS when asked, and never weaken them silently "to match ITS" — raise the question and let the user decide. Following the convention already used by the code you edit is not weakening.
