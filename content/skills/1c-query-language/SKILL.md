---
name: 1c-query-language
description: >
  Complete reference and verification playbook for the 1C:Enterprise query
  language (BSL queries): SELECT syntax, virtual tables of registers
  (Остатки, Обороты, ОстаткиИОбороты, СрезПоследних, СрезПервых), built-in
  query functions, batch queries with temporary tables (ПОМЕСТИТЬ,
  ИНДЕКСИРОВАТЬ ПО, ВТ_*), project hard rules, must-fix anti-patterns, and a
  verification checklist (manual review + validateQuery MCP). Load for ANY
  task that writes, optimizes, or reviews a 1C query: Запрос.Текст, выборка
  номенклатуры / артикула / контрагентов, остатки и обороты регистров,
  DCS/SKD (data composition) schemes, оптимизация медленных запросов,
  пакетные запросы с временными таблицами. Язык запросов 1С: синтаксис,
  виртуальные таблицы, функции, анти-паттерны, чек-лист проверки.
---

# 1C Query Language — Reference & Verification Playbook

Self-contained companion to `.ai-agent/rules/query-design.md`,
`.ai-agent/rules/dev-standards-architecture.md` (§3 "Queries") and
`.ai-agent/rules/anti-patterns.md`. This skill is the **how**: syntax tables,
virtual-table parameter shapes, functions, batch patterns, plus a step-by-step
verification checklist with both manual and MCP-based (`validatequery`) paths.

## When to use this skill

- Writing a new `Запрос.Текст` from scratch (any source: catalogs, documents,
  registers, virtual tables, query schema in reports).
- Optimizing / tuning an existing query (joins vs subqueries, temp tables,
  indexing, virtual-table filters).
- Reviewing a query before delivery — run the Verification Playbook (§7).
- Building a batch query (temp tables, `ПОМЕСТИТЬ`, `ИНДЕКСИРОВАТЬ ПО`).

---

## 1. SELECT structure and clause order

Fixed clause order in 1C query language:

```
ВЫБРАТЬ [ПЕРВЫЕ <N>] [РАЗЛИЧНЫЕ] <select list>
ИЗ <source> КАК <alias>
    [СОЕДИНЕНИЕ / ВНУТРЕННЕЕ СОЕДИНЕНИЕ / ЛЕВОЕ СОЕДИНЕНИЕ / ПРАВОЕ СОЕДИНЕНИЕ /
     ПОЛНОЕ СОЕДИНЕНИЕ] <source> КАК <alias> ПО <on-condition>
ГДЕ <predicate>
СГРУППИРОВАТЬ ПО <fields>
[ГРУППИРОВАТЬ ПО ИЕРАРХИИ ...]        (catalogs with hierarchy)
УПОРЯДОЧИТЬ ПО <fields> [АВТОУПОРЯДОЧИВАНИЕ]
АВТОУПОРЯДОЧИВАНИЕ
ИТОГИ [<aggregate list>] ПО <grouping fields>
```

Key points:

- `ВЫБРАТЬ ПЕРВЫЕ N` limits the result at DB level; **must be paired with
  `УПОРЯДОЧИТЬ ПО`** — without ordering the N rows are non-deterministic.
- `РАЗЛИЧНЫЕ` deduplicates; avoid it when a `СГРУППИРОВАТЬ ПО` over the same
  fields already deduplicates (double work). Внутри `ОБЪЕДИНИТЬ` operands
  `РАЗЛИЧНЫЕ` is redundant — `ОБЪЕДИНИТЬ` already deduplicates the union.
- Every field in the select list **must** carry a `КАК <alias>`.
- `ИЗ` source requires an alias (`КАК <alias>`) for every source table.

## 2. Virtual tables of registers

### Accumulation registers (РегистрНакопления)

```
РегистрНакопления.<Имя>.Остатки(<Период>, <Условие>)
РегистрНакопления.<Имя>.Обороты(<НачалоПериода>, <КонецПериода>, <Периодичность>, <Условие>)
РегистрНакопления.<Имя>.ОстаткиИОбороты(<НачалоПериода>, <КонецПериода>, <Периодичность>, <МетодДополненияПериодов>, <Условие>)
```

- `<Условие>` — a boolean expression over **dimensions** (e.g.
  `Склад = &Склад И Номенклатура = &Номенклатура`). Fields filtered here must
  NOT be re-filtered in `ГДЕ` — filtering a virtual table in `ГДЕ` forces a
  full calculation first (HIGH anti-pattern §6).
- `<Периодичность>` for «Обороты» can be `День`, `Месяц`, `Год`, `Авто`,
  or a date field / query parameter of `ГраницаПериода`.
- Virtual-table columns use suffixes: `КоличествоОстаток`, `КоличествоОборот`,
  `СуммаОборот`, `СуммаОстаток` (тип объёма + движение, see register structure).
- Available fields include dimensions, resources, and `Регистратор` (for
  registers with movement).

### Information registers (РегистрСведений)

- Period-independent (независимые): `РегистрСведений.<Имя>` — direct table.
- Slice tables:
  - `РегистрСведений.<Имя>.СрезПоследних(<Период>, <Условие>)` — latest slice
    as of a date (or the last record overall if `<Период>` omitted).
  - `РегистрСведений.<Имя>.СрезПервых(<Период>, <Условие>)` — first slice.
  - `РегистрСведений.<Имя>.СрезПоследнихВключаяГраницы(<Период>, ...)` — as of
    the period including records on the boundary; not needed in most cases.
- `<Условие>` — boolean expression over **dimensions** only (not resources).
  Do NOT filter dimensions in `ГДЕ` instead of the slice condition.

### Register query common rules

- Dimension filters go into the virtual-table `<Условие>` — never `ГДЕ`.
- Periodic resources are selected as `Остаток`, `Оборот`, or for information
  registers as the period-resource value; dimension + period fields are
  grouped automatically in virtual tables with hierarchy/periods only when
  explicitly requested via `Периодичность`.

## 3. Built-in functions and operators

### Arithmetic / aggregate

- `СУММА(<field>)`, `СУММА(<field> КАК ЧИСЛО)` — sum (the `КАК ЧИСЛО` cast
  avoids type-union sum errors on mixed types).
- `МИНИМУМ(...)`, `МАКСИМУМ(...)`, `СРЕДНЕЕ(...)`, `КОЛИЧЕСТВО(*)`,
  `КОЛИЧЕСТВО(<field>)`, `КОЛИЧЕСТВО(РАЗЛИЧНЫЕ <field>)`.

### Conditional / value conversion

- `ВЫБОР КОГДА <cond> ТОГДА <value> ИНАЧЕ <value> КОНЕЦ` — CASE.
- `ЕСТЬNULL(<expr>, <replace>)` — replace `NULL` (from left/outer joins).
- `ВЫРАЗИТЬ(<expr> КАК <Тип>)` — cast / dereference composite types
  (`ВЫРАЗИТЬ(Исходный.Значение КАК Строка(100))`).
- `ЗНАЧЕНИЕ(<enum>.<item>)` — enum literal (`ЗНАЧЕНИЕ(Перечисление.Тип.Элемент)`).
- `ТИПЗНАЧЕНИЯ(<expr>)`, `ТИП(<"Строка">)` — type checks.
- `ССЫЛКА(<type>)`: `ССЫЛКА(Справочник.Номенклатура)` — magic char, typeof check
  on a reference field.
- `ПРЕДСТАВЛЕНИЕ(<field>)` / `ПРЕДСТАВЛЕНИЕССЫЛКИ(<ref>)` — string representation.

### String / date / other

- `ПОДСТРОКА(<str>, <start>, <length>)` — substring; `start` is 1-based.
- `ПОДСТРОКА` with a parameter allows horizontal slicing on the server
  (`ПОДСТРОКА(Таб.Поле, &Начало, &Длина)`), useful with `ВЫБРАТЬ ПЕРВЫЕ`.
- `ДАТАВРЕМЯ(<год>, <месяц>, <день>)` — date literal
  (`ДАТАВРЕМЯ(2024, 1, 1)`); `ДАТАВРЕМЯ(1, 1, 1)` — empty date.
- `СЕГОДНЯ()`, `ТЕКУЩАЯДАТА()`, `ТЕКУЩАЯУНИКАЛЬНАЯДАТА()` (server).
- `НАЧАЛОПЕРИОДА(<date>, <period>)` / `КОНЕЦПЕРИОДА(<date>, <period>)` with
  `ДЕНЬ`, `МЕСЯЦ`, `КВАРТАЛ`, `ГОД`.
- `ДОБАВИТЬКДАТЕ(<date>, <period>, <amount>)`.
- `РАЗНЦАДАТ(<d1>, <d2>, <period>)`.
- `ЕСТЬ NULL` handled by `ЕСТЬNULL`; `ИСТИНА` / `ЛОЖЬ` / `НЕ` / `И` / `ИЛИ` —
  boolean logic.
- References: direct equality with a query parameter
  (`ГДЕ Номенклатура = &Номенклатура`), membership
  (`ГДЕ Ссылка В (&МассивСсылок)`), `ИЕРАРХИЯ В (&Группа)`.

## 4. Batch queries and temporary tables

A batch is a single `Запрос.Текст` with several statements separated by `;`.
Temp tables created with `ПОМЕСТИТЬ ВТ_*` are available in subsequent
statements of the same batch.

```
ВЫБРАТЬ <fields>
ПОМЕСТИТЬ ВТ_Ключи
ИЗ <source> КАК Т
ГДЕ ...
ИНДЕКСИРОВАТЬ ПО <join-keys>          -- optional, see rules below
;
ВЫБРАТЬ ...
ИЗ <main> КАК М
    ВНУТРЕННЕЕ СОЕДИНЕНИЕ ВТ_Ключи КАК К
    ПО К.Ключ = М.Ключ
```

Rules (project canon):

- Temp table names are prefixed `ВТ_`.
- A temp table that later participates in a `СОЕДИНЕНИЕ`, feeds an
  `ОБЪЕДИНИТЬ`, or backs a `В (ВЫБРАТЬ ...)` filter **must** carry
  `ИНДЕКСИРОВАТЬ ПО` on its join / dedup keys — the **2–3 most selective
  fields**, not the whole column list.
- Prefer **pre-collect → index → join** over correlated/per-row subqueries
  (`ИСТИНА В (ВЫБРАТЬ ПЕРВЫЕ 1 ...)` in `ГДЕ` is CRITICAL). Collect the
  independent set once into an indexed temp table, then `ВНУТРЕННЕЕ СОЕДИНЕНИЕ`.
- When a join feeds a large `СГРУППИРОВАТЬ ПО` — join into an indexed temp
  table first, group afterwards.

## 5. Project hard rules (canon — dev-standards-architecture.md §3)

1. **Verify metadata before the first `ВЫБРАТЬ`** — attribute/table names via
   `get_object_dossier` / `metadatasearch` (or native research when MCP is not
   exposed). Never invent names.
2. **Look for a proven template first** — `templatesearch` / `search_code`
   before writing a complex query from scratch.
3. **Formatting** — `Запрос.Текст =` on a new line, text at the same
   indentation as the variable declaration, `|` line prefixes.
4. **Intermediate variable** — `РезультатЗапроса = Запрос.Выполнить();`.
   Chaining `Запрос.Выполнить().Выгрузить()` / `.Выбрать()` is PROHIBITED.
5. **Every field has `КАК` alias**.
6. **No queries in loops** — batch queries + temp tables instead
   (`anti-patterns.md §1`).
7. **Parameters, not string concatenation** — `Запрос.УстановитьПараметр()`;
   string concatenation into `Текст` is PROHIBITED (SQL injection + broken
   plan cache).
8. **Registers: filter dimensions in virtual-table parameters**, not in `ГДЕ`.
9. **Do not modify register movements directly** — only through the posting
   mechanism.
10. **`ПЕРВЫЕ N`** when only a subset is needed; pair with `УПОРЯДОЧИТЬ ПО`.
11. **Join type from semantics** — `ВНУТРЕННЕЕ СОЕДИНЕНИЕ` discards
    non-matching rows; `ЛЕВОЕ СОЕДИНЕНИЕ` preserves source rows — handle
    `NULL` explicitly (`ЕСТЬNULL`).
12. **Cross-platform** — no COM objects; file paths via `/` or platform
    functions.

## 6. Must-fix query anti-patterns (canon — anti-patterns.md)

| Severity | Anti-pattern | Fix |
|---|---|---|
| CRITICAL | **Query in loop** (`Для Каждого ... Запрос ... Выполнить()`) | collect keys → one batch query with `ГДЕ Ссылка В (&Список)` (array parameter) |
| CRITICAL | **Subquery in SELECT** (scalar `(ВЫБРАТЬ СУММА(...) ... ГДЕ ...)` per row) | aggregate once → `ЛЕВОЕ СОЕДИНЕНИЕ` on aggregated subquery, `ЕСТЬNULL` for missing |
| CRITICAL | **Correlated subquery in `ГДЕ`** (`ИСТИНА В (ВЫБРАТЬ ПЕРВЫЕ 1 ИСТИНА ... ГДЕ ...)`) | pre-collect the set into indexed temp table → `ВНУТРЕННЕЕ СОЕДИНЕНИЕ` |
| HIGH | **Virtual-table filter in `ГДЕ`** | move dimension filter into virtual-table parameters (`Остатки(, Склад = &Склад)`) |
| HIGH | **Missing `ПЕРВЫЕ N`** when only a subset is needed | add `ПЕРВЫЕ N` + `УПОРЯДОЧИТЬ ПО` |
| HIGH | **Unindexed temp table** used in join / union / `В (...)` | add `ИНДЕКСИРОВАТЬ ПО` on the 2–3 most selective join/dedup keys |
| MED | **`РАЗЛИЧНЫЕ` inside `ОБЪЕДИНИТЬ` or on top of `СГРУППИРОВАТЬ ПО`** | drop `РАЗЛИЧНЫЕ`; prefer `ОБЪЕДИНИТЬ ВСЕ` when duplicates are impossible |
| MED | **String concatenation into `Запрос.Текст`** | `Запрос.УстановитьПараметр()` |

## 7. Verification playbook

### 7.1 Manual review checklist (no runtime required)

Run these checks item by item before delivery:

1. **Pre-flight done?** Metadata names verified; template searched
   (`templatesearch`); query written only after those two when the rule applies.
2. **Ban scan** — no query inside a loop; all parameters via
   `УстановитьПараметр()`; no string concatenation into `Текст`.
3. **Aliases & formatting** — every field has `КАК`; text formatted on a new
   line with `|` prefixes; `Запрос.Выполнить()` stored into an intermediate
   variable.
4. **Sources** — catalog / document / register / virtual table is the correct
   one for the task (slicing issues are design defects, not tuning).
5. **Virtual tables** — dimension filters inside `<Условие>`, not in `ГДЕ`;
   period parameters correct (`НачалоПериода`/`КонецПериода` or single
   `<Период>` for `Остатки`).
6. **Batch queries** — every `ВТ_*` that feeds a join/`ОБЪЕДИНИТЬ`/`В (ВЫБРАТЬ)`
   has `ИНДЕКСИРОВАТЬ ПО` on selective keys; no `ПОМЕСТИТЬ` without later use.
7. **Auto-check** — if MCP is exposed: `validatequery` on the query text
   before it lands in a module or DCS scheme (`verification-gates.md → Gate 3a`);
   after a `rewrite_1c_code` / `modify_1c_code` result validate unconditionally.
   If the validator is not available, state it once and rely on this checklist.

### 7.2 Runtime tools

| Tool | Where | When |
|---|---|---|
| `validatequery` | `1c-data-mcp` (dev/test IB) | Every query text before it reaches a module / DCS scheme |
| `syntaxcheck_content` / `syntaxcheck_file` | `1c-syntax-checker-mcp` | Module code around the query (BSL), surface-level |
| Constructor query | 1C platform UI | Interactive one-off check without MCP |
| Консоль запросов (БСП) | Processing on a dev IB | Execute & inspect result shape |

## 8. Reference examples

**Oстатки with virtual-table dimension filter (parameters, aliases, intermediate
variable — pattern per §5):**

```bsl
Запрос = Новый Запрос;
Запрос.УстановитьПараметр("ДатаОстатков", ДатаОстатков);
Запрос.УстановитьПараметр("Склад", Склад);
Запрос.УстановитьПараметр("Номенклатура", Номенклатура);
Запрос.УстановитьПараметр("КоличествоЗаписей", КоличествоЗаписей);

Запрос.Текст =
"ВЫБРАТЬ ПЕРВЫЕ &КоличествоЗаписей
|	Остатки.Номенклатура КАК Номенклатура,
|	Остатки.Склад КАК Склад,
|	Остатки.КоличествоОстаток КАК Количество
|ПОМЕСТИТЬ ВТ_Остатки
|ИЗ
|	РегистрНакопления.ТоварыНаСкладах.Остатки(
|			&ДатаОстатков,
|			Склад = &Склад И Номенклатура = &Номенклатура) КАК Остатки
|ИНДЕКСИРОВАТЬ ПО
|	Номенклатура,
|	Склад
|;
|////////////////////////////////////////////////////////////////////////////////
|ВЫБРАТЬ
|	ВТ_Остатки.Номенклатура КАК Номенклатура,
|	ВТ_Остатки.Склад КАК Склад,
|	ВТ_Остатки.Количество КАК Количество
|ИЗ ВТ_Остатки КАК ВТ_Остатки
|УПОРЯДОЧИТЬ ПО
|	Количество УБЫВ";

РезультатЗапроса = Запрос.Выполнить();
Возврат РезультатЗапроса.Выгрузить();
```

**Replace correlated subquery with indexed temp table + join (§4, §6):**

```bsl
// Pre-collect the independent set once, index it, inner join.
ВЫБРАТЬ РАЗЛИЧНЫЕ ГП.Ссылка КАК ГруппаДоступа
ПОМЕСТИТЬ ВТ_ГруппыПользователя
ИЗ Справочник.ГруппыДоступа.Пользователи КАК ГП
ГДЕ ГП.Пользователь = &Пользователь
ИНДЕКСИРОВАТЬ ПО ГруппаДоступа
;
ВЫБРАТЬ ...
ИЗ РегистрСведений.ЗначенияПоУмолчанию КАК Значения
    ВНУТРЕННЕЕ СОЕДИНЕНИЕ ВТ_ГруппыПользователя КАК Группы
    ПО Группы.ГруппаДоступа = Значения.ГруппаДоступа
```

## References

- `content/rules/query-design.md` — routing & load order for query tasks.
- `content/rules/dev-standards-architecture.md` §3 — normative query bans.
- `content/rules/anti-patterns.md` — severity catalog & fix templates.
- `content/skills/1c-metadata-manage/docs/query-writing.md`,
  `query-optimization.md` — how-to composition / optimization (load on demand).
- `docs.onerpa.ru` and the 1C platform documentation via `1C-docs-mcp`
  (`docinfo` / `docsearch`) when a version-specific signature must be confirmed.