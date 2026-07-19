# 1C Query Writing — Composing Queries from Scratch

Covers **writing** new 1C queries: structure, parameters, virtual tables, temporary tables, totals, joins with tabular sections, and the small set of patterns you need 90% of the time.

For tuning existing queries, joins versus subqueries, composite-type dereferencing, index alignment and DCS specifics — see [query-optimization.md](query-optimization.md).

For project-wide query rules — load the router `content/rules/query-design.md` first. Authoritative formatting, aliases, parameters, and the no-queries-in-loops ban live in `dev-standards-architecture.md §3 → "Queries"`; severity catalog — `anti-patterns.md` (§1 Query in Loop, §4 Virtual Table Filter in WHERE, §5 Missing ПЕРВЫЕ N, Batch Query with Temp Table).

## When to Use This Skill

- Writing a new query against existing metadata.
- Building a multi-step report or business calculation.
- Translating a business requirement into a query — choosing the right registers/virtual tables.
- Reviewing a query someone else wrote: was the right virtual table chosen? Are parameters used correctly? Are totals built up the right way?

## Pre-flight Checklist

Before writing the first line of `ВЫБРАТЬ`:

1. **Verify metadata** with `metadatasearch` / `get_metadata_details`: do the objects, attributes and tabular sections you assume actually exist? Right now? In the version installed in the project?
2. **Find similar queries** with `codesearch` / `templatesearch`. Reuse a proven shape rather than inventing one.
3. **Pick the right source**:
   - Reference data → catalog (`Справочник`).
   - Business event → document (`Документ`); for analytics over many docs — accumulation register (`РегистрНакопления`) instead.
   - State at a date / by dimensions → information register (`РегистрСведений`) virtual tables (`СрезПоследних`, `СрезПервых`).
   - Stocks / sums / movements → `.Остатки`, `.Обороты`, `.ОстаткиИОбороты` of an accumulation register.
4. **Decide on the result shape**: flat table, grouped, with totals, with hierarchical structure (`ИТОГИ ... ПО`).

## Canonical Skeleton

Copy this skeleton, then fill the parts you need:

```bsl
Запрос = Новый Запрос;
Запрос.Текст =
"ВЫБРАТЬ
|	// Поля результата с псевдонимами
|	Заказы.Ссылка КАК Заказ,
|	Заказы.Дата КАК Дата,
|	Заказы.Контрагент КАК Контрагент,
|	Заказы.СуммаДокумента КАК Сумма
|ИЗ
|	Документ.ЗаказКлиента КАК Заказы
|ГДЕ
|	Заказы.Дата МЕЖДУ &НачалоПериода И &КонецПериода
|	И НЕ Заказы.ПометкаУдаления
|УПОРЯДОЧИТЬ ПО
|	Дата";

Запрос.УстановитьПараметр("НачалоПериода", НачалоПериода);
Запрос.УстановитьПараметр("КонецПериода", КонецПериода);

РезультатЗапроса = Запрос.Выполнить();
Выборка = РезультатЗапроса.Выбрать();

Пока Выборка.Следующий() Цикл
    // ... обработка строк ...
КонецЦикла;
```

Always: query text on its own line at the same indent as the variable, alias every output column, use parameters, use an intermediate variable for the result.

## Parameters

`Запрос.УстановитьПараметр("Имя", Значение)` — single source of truth.

- **Never** concatenate values into the query text — SQL injection, broken caching, broken Russian/English keyword handling.
- For an `В (&Список)` predicate pass an `Array`, `ТаблицаЗначений`, `СписокЗначений` or query result. The platform handles the unfolding.
- For nullable filters use the constructor pattern: when a filter is empty, omit it or use `(&Значение = НЕОПРЕДЕЛЕНО ИЛИ Поле = &Значение)` carefully — a runtime `WHERE` rebuild is usually cleaner.

## Joins

Five join kinds: `СОЕДИНЕНИЕ` (= INNER), `ЛЕВОЕ`, `ПРАВОЕ`, `ПОЛНОЕ`, `КРОСС`. Always wrap each join with explicit `КАК` aliases:

```bsl
"ВЫБРАТЬ
|	Заказ.Ссылка КАК Заказ,
|	Контрагент.ИНН КАК ИНН
|ИЗ
|	Документ.ЗаказКлиента КАК Заказ
|		ЛЕВОЕ СОЕДИНЕНИЕ Справочник.Контрагенты КАК Контрагент
|		ПО Заказ.Контрагент = Контрагент.Ссылка"
```

For a join with a tabular section of the same document, address it via dotted notation as a separate table:

```bsl
"ВЫБРАТЬ
|	Заказ.Ссылка КАК Заказ,
|	Товары.Номенклатура КАК Номенклатура,
|	Товары.Количество КАК Количество
|ИЗ
|	Документ.ЗаказКлиента КАК Заказ
|		ВНУТРЕННЕЕ СОЕДИНЕНИЕ Документ.ЗаказКлиента.Товары КАК Товары
|		ПО Заказ.Ссылка = Товары.Ссылка"
```

## Virtual Tables of Registers

These are the high-leverage tools — most reporting queries are built around them.

| Register kind | Virtual table | Returns |
|---|---|---|
| Accumulation (turnovers) | `РегистрНакопления.<Имя>.Обороты(&НачалоПериода, &КонецПериода, Период, <отбор>)` | Net delta per dimension over a period. |
| Accumulation (balances) | `РегистрНакопления.<Имя>.Остатки(&МоментВремени, <отбор>)` | Stock on a date. |
| Accumulation (both) | `РегистрНакопления.<Имя>.ОстаткиИОбороты(&Н, &К, Период, <отбор>)` | Opening balance + turnovers + closing balance. |
| Information register | `РегистрСведений.<Имя>.СрезПоследних(&Дата, <отбор>)` | Latest record per dimension up to date. |
| Information register | `РегистрСведений.<Имя>.СрезПервых(&Дата, <отбор>)` | First record per dimension on or after date. |

**Pass parameters to the virtual table itself**, not as a separate `ГДЕ`:

```bsl
// ❌ filter applied AFTER materialisation — slow
"ВЫБРАТЬ ...
|ИЗ
|	РегистрНакопления.ТоварыНаСкладах.Остатки(&МоментВремени) КАК Остатки
|ГДЕ
|	Остатки.Склад = &Склад"

// ✅ filter pushed into the virtual table
"ВЫБРАТЬ ...
|ИЗ
|	РегистрНакопления.ТоварыНаСкладах.Остатки(&МоментВремени, Склад = &Склад) КАК Остатки"
```

The second form is the canonical one — see `query-optimization.md` for why.

## Temporary Tables and Batch Queries

Temporary tables are the way to compose multi-step queries instead of nested subqueries:

```bsl
МенеджерВТ = Новый МенеджерВременныхТаблиц;

Запрос = Новый Запрос;
Запрос.МенеджерВременныхТаблиц = МенеджерВТ;
Запрос.Текст =
"ВЫБРАТЬ
|	Товары.Номенклатура КАК Номенклатура,
|	СУММА(Товары.Количество) КАК Количество
|ПОМЕСТИТЬ ВТНоменклатураЗаказа
|ИЗ
|	Документ.ЗаказКлиента.Товары КАК Товары
|ГДЕ
|	Товары.Ссылка = &Заказ
|СГРУППИРОВАТЬ ПО
|	Товары.Номенклатура
|ИНДЕКСИРОВАТЬ ПО
|	Номенклатура
|;
|////////////////////////////////////////////////////////////////////////////////
|ВЫБРАТЬ
|	ВТ.Номенклатура КАК Номенклатура,
|	ВТ.Количество КАК Заказано,
|	ЕСТЬNULL(Остатки.КоличествоОстаток, 0) КАК ВНаличии
|ИЗ
|	ВТНоменклатураЗаказа КАК ВТ
|		ЛЕВОЕ СОЕДИНЕНИЕ
|			РегистрНакопления.ТоварыНаСкладах.Остатки(
|				&МоментВремени,
|				Номенклатура В (ВЫБРАТЬ Номенклатура ИЗ ВТНоменклатураЗаказа)
|			) КАК Остатки
|		ПО ВТ.Номенклатура = Остатки.Номенклатура";

Запрос.УстановитьПараметр("Заказ", Заказ);
Запрос.УстановитьПараметр("МоментВремени", МоментВремени);

РезультатЗапроса = Запрос.Выполнить();
Выборка = РезультатЗапроса.Выбрать();
```

Rules of thumb:

- Always `ИНДЕКСИРОВАТЬ ПО` the columns you join on.
- A batch query separator is the `;` plus a comment ruler — no semantic role, just visual separation.
- Pass the temporary-table set into a virtual table via `В (ВЫБРАТЬ ... ИЗ ВТ...)` to push the filter to the lowest possible level.
- A single `Запрос` instance with one `МенеджерВременныхТаблиц` is enough; do **not** create a query per batch step.

## Totals

Use `ИТОГИ ... ПО` when the consumer needs hierarchical results (typical for reports):

```bsl
"ВЫБРАТЬ
|	Продажи.Период КАК Период,
|	Продажи.Контрагент КАК Контрагент,
|	Продажи.СуммаОборот КАК Сумма
|ИЗ
|	РегистрНакопления.Продажи.Обороты(&Н, &К, Месяц,) КАК Продажи
|ИТОГИ
|	СУММА(Сумма)
|ПО
|	ОБЩИЕ,
|	Контрагент,
|	Период"
```

Reading totals: `Выборка = РезультатЗапроса.Выбрать(ОбходРезультатаЗапроса.ПоГруппировкам)` and recurse into nested levels.

## `ВЫБОР` and `ЕСТЬNULL`

```bsl
"ВЫБРАТЬ
|	Заказ.Ссылка КАК Заказ,
|	ВЫБОР
|		КОГДА Заказ.СуммаДокумента > 100000 ТОГДА ""Крупный""
|		КОГДА Заказ.СуммаДокумента > 10000 ТОГДА ""Средний""
|		ИНАЧЕ ""Малый""
|	КОНЕЦ КАК Категория,
|	ЕСТЬNULL(Контрагент.ИНН, """") КАК ИНН
|ИЗ
|	Документ.ЗаказКлиента КАК Заказ
|		ЛЕВОЕ СОЕДИНЕНИЕ Справочник.Контрагенты КАК Контрагент
|		ПО Заказ.Контрагент = Контрагент.Ссылка"
```

Use `ЕСТЬNULL` on every column that comes through `ЛЕВОЕ`/`ПРАВОЕ` join — otherwise `NULL` leaks into business logic and breaks comparisons.

## Limits and Modifiers

- `ПЕРВЫЕ N` — top N rows. Always pair with `УПОРЯДОЧИТЬ ПО`, otherwise the platform may return any N rows.
- `РАЗЛИЧНЫЕ` — distinct rows. Cheap on small result sets, expensive on large ones — prefer `СГРУППИРОВАТЬ ПО` for large sets.
- `ДЛЯ ИЗМЕНЕНИЯ` — pessimistic lock; only inside an explicit transaction, only when really needed.
- `РАЗРЕШЁННЫЕ` — silently filter out rows the user has no rights to read. Use only when the consumer is prepared for a partial result.
- `АВТОУПОРЯДОЧИВАНИЕ` — adds platform-default ordering for hierarchical refs. Heavy; usually avoidable by explicit `УПОРЯДОЧИТЬ ПО Ссылка`.

## Anti-patterns to avoid while writing

These are mistakes you make at write time, not at optimisation time. Optimisation patterns are in `query-optimization.md`.

- **String concatenation for parameters** — see *Parameters* above.
- **No alias for output columns** — breaks consumer readability and DCS.
- **`Запрос.Выполнить().Выгрузить()` chain** — use an intermediate variable.
- **Querying inside a loop** — restructure as a batch query with a temporary table of input keys.
- **Selecting `*`** — there is no `ВЫБРАТЬ *` in 1C, but the moral equivalent is selecting many fields you do not need. Each extra field is extra DB traffic and extra type resolution.
- **Comparing reference type via `<> Неопределено`** — use `ЗначениеЗаполнено(...)` in BSL or `Поле <> ЗНАЧЕНИЕ(Тип.ПустаяСсылка)` in the query.
- **Ignoring `NULL` from outer joins** — wrap with `ЕСТЬNULL`.
- **Mixing `ОБЪЕДИНИТЬ` and `ОБЪЕДИНИТЬ ВСЕ` arbitrarily** — `ОБЪЕДИНИТЬ` adds a hidden dedup step; pick `ВСЕ` unless you really need dedup.

## Quick Reference: Common Recipes

**Latest record per key in an information register:**

```bsl
"ВЫБРАТЬ
|	Курсы.Валюта КАК Валюта,
|	Курсы.Курс КАК Курс
|ИЗ
|	РегистрСведений.КурсыВалют.СрезПоследних(&Дата,) КАК Курсы"
```

**Stocks at a date with a filter pushed into the virtual table:**

```bsl
"ВЫБРАТЬ
|	Остатки.Номенклатура КАК Номенклатура,
|	Остатки.Склад КАК Склад,
|	Остатки.КоличествоОстаток КАК Количество
|ИЗ
|	РегистрНакопления.ТоварыНаСкладах.Остатки(
|		&МоментВремени,
|		Склад = &Склад И Номенклатура В (&Номенклатура)
|	) КАК Остатки"
```

**Header + tabular section in one pass:**

```bsl
"ВЫБРАТЬ
|	Заказ.Ссылка КАК Заказ,
|	Заказ.Дата КАК Дата,
|	Заказ.Контрагент КАК Контрагент,
|	Товары.Номенклатура КАК Номенклатура,
|	Товары.Количество КАК Количество,
|	Товары.Цена КАК Цена
|ИЗ
|	Документ.ЗаказКлиента КАК Заказ
|		ВНУТРЕННЕЕ СОЕДИНЕНИЕ Документ.ЗаказКлиента.Товары КАК Товары
|		ПО Заказ.Ссылка = Товары.Ссылка
|ГДЕ
|	Заказ.Ссылка = &Заказ
|УПОРЯДОЧИТЬ ПО
|	Товары.НомерСтроки"
```

**Group with totals:**

```bsl
"ВЫБРАТЬ
|	Продажи.Контрагент КАК Контрагент,
|	Продажи.Номенклатура КАК Номенклатура,
|	СУММА(Продажи.СуммаОборот) КАК Сумма
|ИЗ
|	РегистрНакопления.Продажи.Обороты(&Н, &К,,) КАК Продажи
|СГРУППИРОВАТЬ ПО
|	Продажи.Контрагент,
|	Продажи.Номенклатура
|ИТОГИ
|	СУММА(Сумма)
|ПО
|	ОБЩИЕ,
|	Контрагент"
```

---

**See also:** [query-optimization.md](query-optimization.md) for join strategy, virtual-table tuning, composite-type dereferencing and index alignment.
