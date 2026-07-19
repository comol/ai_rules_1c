---
description: Designing 1C registers — dimensions, resources, attributes, periodicity, indexes, balances vs turnovers, posting / reposting / sequence restoration. Load when creating or restructuring an information / accumulation / accounting register.
alwaysApply: false
category: development
---

# Register Design Rules

Registers are the spine of any non-trivial 1C configuration; mistakes here are expensive to undo because they are usually wired into document posting, RLS, and reports. This file consolidates the design decisions worth thinking through **before** running the metadata skill.

> **Scope.** This file owns *design* rules. XML / schema mechanics live in `content/skills/1c-metadata-manage/docs/meta-manage.md`. Queries against registers — start at the router `query-design.md` (hard rules in `dev-standards-architecture.md §3 → "Queries"`, anti-patterns in `anti-patterns.md`).

## 1. Choosing the register type

| Register type | Use when | Avoid when |
|---|---|---|
| **РегистрСведений** (Information) | Arbitrary tabular data indexed by dimensions, with optional periodicity. Read-modify-write patterns: settings, mappings, cached lookups, historical attribute values, exchange status, status of long-running operations. | The data is a **delta** that must be summable / aggregated as balances or turnovers — use accumulation. |
| **РегистрНакопления** (Accumulation, "Остатки") | Balances at a point in time (stock, debt, allocation). The register answers "how much is there now / on date X". | The data is per-period turnover only, never asked as a balance — use accumulation type "Обороты" or an information register. |
| **РегистрНакопления (Обороты only)** | Period-based turnover that is never asked as a balance (e.g. sales by period, traffic). | A balance question is realistic — losing balances later costs a full re-design. |
| **РегистрБухгалтерии** (Accounting) | Double-entry bookkeeping with a chart of accounts. | The "double-entry" abstraction is forced where it does not belong — use accumulation. |
| **РегистрРасчета** (Calculation) | Payroll / period-base recalculation with dependencies between charge types. | Anything that is not period-base salary / benefit recalculation. |

Default mental model: *"can a user ask for a balance on a date?"* → accumulation. *"is this just a typed indexed lookup?"* → information register. Anything else → think harder, do not start from accounting / calculation registers by reflex.

## 2. Dimensions

- **Cardinality first.** Place high-cardinality, narrow-filter dimensions first (e.g. `Контрагент`, `Договор`, `Номенклатура`); place low-cardinality ones (`Организация`, `Подразделение`) after. The order affects index usage on virtual-table queries.
- **Stable identity, not free text.** Dimensions must be of reference types (`СправочникСсылка.X`, `ДокументСсылка.X`, `Перечисление.X`, `Дата` for periodic). Strings or numeric codes as dimensions are an anti-pattern — they fork the data on every typo.
- **Periodicity.** Choose the coarsest periodicity that still answers the business question: `НеПериодический` (constants, mappings, current attribute values), `ВПределахСекунды` (default for movements), `ВПределахДня` (rates, status logs), `ВПределахМесяца` / `Год` (planning data). Finer periodicity inflates the table and slows everything.
- **`Ведущее` (Leading) measure** — set on a dimension whose deletion should cascade-delete the register record (e.g. set "leading" on `Контрагент` if records for a deleted counterparty should disappear). Do **not** set "leading" by default — most dimensions are not leading.

## 3. Resources

- **Resources are numeric / quantitative.** For accumulation registers they MUST be summable (`Количество`, `Сумма`, `КоличествоСтрок`). For information registers any type is allowed but stays "the value at this dimension key".
- **One resource — one unit.** Mixing `Сумма` (in different currencies) into one resource is a trap. Either split into per-currency resources or carry the currency as a dimension.
- **Negative values.** For accumulation registers — allowed and meaningful (returns, write-offs). For information registers — usually a code smell except for explicitly signed amounts.

## 4. Attributes

- Attributes are non-aggregable, non-filter data that travels with the record (e.g. `Комментарий`, `НомерЗаказа`). They are not indexed by default; do **not** filter queries by attribute fields in hot paths.
- If you find yourself filtering by an attribute repeatedly — promote it to a dimension.

## 5. Indexing

- Mark dimensions as `Индексировать` only when they participate in queries / virtual-table parameters that do **not** include all preceding dimensions. The first dimension does not need an explicit index — the platform builds it.
- For information registers used as a lookup by a non-leading dimension subset, mark exactly those dimensions as `Индексировать`. Do not "index everything just in case" — every index slows writes.
- For accounting registers — special handling, see ITS.

## 6. Subordination to a registrar (only for accumulation / accounting / calculation)

- **`Подчинение регистратору` is the default** for accumulation registers — the register is fed by document movements through `ОбработкаПроведения`.
- **`Независимый`** information register without registrar — for data with no source document (settings, mappings, current values).
- **Mixed access mode** for an information register (`Независимый` with registrar) is occasionally useful for status logs; treat as advanced and document the rationale.

## 7. Balances, turnovers, slices

When a register has balances, the platform exposes virtual tables:

| Table | Purpose |
|---|---|
| `Остатки(&Период, Условие)` | Balance at `&Период` for the given filter. |
| `Обороты(&НачалоПериода, &КонецПериода, ..., Условие)` | Turnover within the period. |
| `ОстаткиИОбороты(...)` | Start balance + turnover + end balance in one shot. |
| `СрезПервых(&Период, Условие)` (info reg.) | First record on or after the date. |
| `СрезПоследних(&Период, Условие)` (info reg.) | Last record on or before the date. |

**Filter virtual tables via parameters, not `ГДЕ` after the call** — hard rule (owner: `dev-standards-architecture.md §3 → "Queries"`; catalog entry with fix template: `anti-patterns.md §4`). Putting the filter into the parameter pushes it into the engine and uses indexes; putting it into `ГДЕ` reads the full virtual table first.

## 8. Posting / reposting

- **`ОбработкаПроведения`** lives in the document's object module. Inside it: lock first, read second, write third (see `locks-and-transactions.md`). Do not call user dialogs, long-running operations, or external services inside the procedure.
- **`Движения.X.Записывать = Истина`** controls whether the platform writes the in-memory tabular section to the register on commit. Set it once; do not toggle inside loops.
- **Do not modify movements outside `ОбработкаПроведения` / `ОбработкаУдаленияПроведения`.** Direct manipulation of `Движения.X` from external code (e.g. a data processor) bypasses sequencing logic and creates inconsistent data.
- **Re-posting (`ОбработкаЗаполнения` is not it).** For mass re-post operations, use `Документы.X.Выбрать()` + `Записать(РежимЗаписиДокумента.Проведение)` in a transaction-per-document loop with explicit cancellation on errors.
- **`Последовательности`** — when document order matters across documents (delivery before payment, etc.), set up a `Последовательность` rather than relying on insertion order.

## 9. Querying registers

- **Always use the virtual tables** for balance / turnover questions. Do not roll your own aggregation over the physical table.
- **Index dimension filters in metadata**, not in BSL.
- **`ВЫБРАТЬ ПЕРВЫЕ 1 ... УПОРЯДОЧИТЬ ПО ... УБЫВ`** as a "last value" pattern is fine for an information register without periodicity — for periodic registers use `СрезПоследних` instead.
- **Aggregation modes**. For accumulation registers `ВклАгрегаты` and `АгрегатыЭтоПлоский` may already accelerate the query; do not disable aggregates without measurement.

## 10. RLS

- Register access restrictions follow the same RLS pattern as catalogs / documents.
- For registers that join several typical objects via dimensions, the restriction template can become long — extract repeated `И` clauses into a reusable predicate via the БСП access-management subsystem.
- Test the restriction with a non-admin role before merging — admin role bypasses RLS and hides bugs.

## 11. Companion rules

| Concern | File |
|---|---|
| XML / schema mechanics for register objects | `content/skills/1c-metadata-manage/docs/meta-manage.md` (skill) |
| Query anti-patterns (loops, dot-notation, subselects) | `anti-patterns.md` |
| Authoritative query rules | `dev-standards-architecture.md §3 → "Queries"` |
| Locks during posting | `locks-and-transactions.md` |
| Reporting against registers (DCS) | `dcs-design.md` |
