# 1C Query Optimization Skill (Advanced Patterns)

For project-wide query work — load the router `content/rules/query-design.md` first. Authoritative hard rules (formatting, aliases, parameters, no queries in loops) — `dev-standards-architecture.md §3 → "Queries"`. Anti-patterns with examples (query in loop, subquery in SELECT, virtual table filter in WHERE, missing `ПЕРВЫЕ N`) — `anti-patterns` rule.

## When to Use

Invoke this skill when:
- Working with complex multi-step data processing
- Optimizing joins and subqueries
- Implementing DCS reports
- Processing large datasets in portions

## Mandatory Optimization Checklist

Walk this list explicitly for **every** query-optimization task (and for every new multi-batch query). Each item is a known miss with a case below:

1. Virtual-table filters — in **parameters**, not `ГДЕ` (`anti-patterns.md §4`).
2. Virtual-table **periodicity matches the join granularity** — joining by `Регистратор` requires periodicity `Регистратор`, not `Авто`.
3. Every temp table later used in a `СОЕДИНЕНИЕ`, `ОБЪЕДИНИТЬ`, or `В (ВЫБРАТЬ …)` filter — created with `ИНДЕКСИРОВАТЬ ПО` on the join / dedup keys (see *Temporary Table Indexing* below).
4. No redundant deduplication — `РАЗЛИЧНЫЕ` inside `ОБЪЕДИНИТЬ` operands or on top of `СГРУППИРОВАТЬ ПО` (see *ОБЪЕДИНИТЬ vs ОБЪЕДИНИТЬ ВСЕ* below).
5. Correlated / per-row subqueries replaced with a pre-collected indexed temp table + join (see *Pre-collect and Index Before Join / Group*).
6. Heavy join feeding a `СГРУППИРОВАТЬ ПО` — narrowed and joined through an indexed temp table first.
7. Field lists minimal — temp tables carry only join keys + fields consumed downstream.
8. Composite references dereferenced via `ВЫРАЗИТЬ`; display-only fields via `ПРЕДСТАВЛЕНИЕ`.

## Temporary Tables

Use temporary tables for:
- Complex multi-step data processing
- Joining data from multiple sources
- Reusing intermediate results

### Temporary Table Indexing (ИНДЕКСИРОВАТЬ ПО) — mandatory cases

A temp table has **no indexes by default**. Creating one that later participates in a join is the single most common optimization miss. `ИНДЕКСИРОВАТЬ ПО` is **mandatory** when the temp table:

1. **Participates in a `СОЕДИНЕНИЕ`** — index the join-condition fields. This is the strongest case: an unindexed probe side forces a scan per joined row.
2. **Participates in an `ОБЪЕДИНИТЬ`** (without `ВСЕ`) — the dedup sort/merge over the combined result benefits from the index on the dedup keys.
3. **Feeds a `В (ВЫБРАТЬ …)` filter** over a large set — index the filtered field.

**Pick the 2–3 most selective fields — do not enumerate every column.** When a join spans many fields (e.g. `Номенклатура, Характеристика, Ячейка, Серия, Упаковка, Регистратор`), index the selective subset (`ИНДЕКСИРОВАТЬ ПО Номенклатура, Ячейка, Регистратор`) — a full-column index costs more to build than it saves, and the remaining equalities are cheap to check on the narrowed set.

```bsl
// ❌ SLOW: temp table joined/united later, no index
"ВЫБРАТЬ РАЗЛИЧНЫЕ
|	Товары.Номенклатура КАК Номенклатура,
|	Товары.Склад КАК Склад,
|	Товары.Заказ КАК Заказ
|ПОМЕСТИТЬ ВТ_ДвиженияПриЗаписи
|ИЗ
|	&ТаблицаТовары КАК Товары
|ГДЕ
|	Товары.Активность"

// ✅ OPTIMIZED: indexed by the selective join/dedup keys
"ВЫБРАТЬ РАЗЛИЧНЫЕ
|	Товары.Номенклатура КАК Номенклатура,
|	Товары.Склад КАК Склад,
|	Товары.Заказ КАК Заказ
|ПОМЕСТИТЬ ВТ_ДвиженияПриЗаписи
|ИЗ
|	&ТаблицаТовары КАК Товары
|ГДЕ
|	Товары.Активность
|ИНДЕКСИРОВАТЬ ПО
|	Номенклатура, Склад"
```

### Pre-collect and Index Before Join / Group

Two related patterns that replace per-row work with one indexed pass:

**A. Correlated subquery → indexed temp table + join.** A `ГДЕ ИСТИНА В (ВЫБРАТЬ ПЕРВЫЕ 1 …)` (or any subquery referencing outer-query fields) executes per source row — quadratic on large tables. The subquery's data set usually does **not** depend on the row: collect it once, index it, join.

```bsl
// ❌ SLOW: semi-join subquery executed for EVERY row of РегистрСведений
"ВЫБРАТЬ РАЗЛИЧНЫЕ
|	Значения.ТипЗначений КАК ТипЗначений
|ПОМЕСТИТЬ ВТ_Значения
|ИЗ
|	РегистрСведений.ЗначенияПоУмолчанию КАК Значения
|ГДЕ
|	ИСТИНА В (ВЫБРАТЬ ПЕРВЫЕ 1 ИСТИНА
|		ИЗ Справочник.ГруппыДоступа.Пользователи КАК ГруппыПользователи
|		ГДЕ ГруппыПользователи.Ссылка = Значения.ГруппаДоступа
|			И ГруппыПользователи.Пользователь = &Пользователь)"

// ✅ OPTIMIZED: collect the independent set once, index, inner join
"ВЫБРАТЬ РАЗЛИЧНЫЕ
|	ГруппыПользователи.Ссылка КАК ГруппаДоступа
|ПОМЕСТИТЬ ВТ_ГруппыПользователя
|ИЗ
|	Справочник.ГруппыДоступа.Пользователи КАК ГруппыПользователи
|ГДЕ
|	ГруппыПользователи.Пользователь = &Пользователь
|ИНДЕКСИРОВАТЬ ПО
|	ГруппаДоступа
|;
|ВЫБРАТЬ РАЗЛИЧНЫЕ
|	Значения.ТипЗначений КАК ТипЗначений
|ПОМЕСТИТЬ ВТ_Значения
|ИЗ
|	РегистрСведений.ЗначенияПоУмолчанию КАК Значения
|	ВНУТРЕННЕЕ СОЕДИНЕНИЕ ВТ_ГруппыПользователя КАК Группы
|	ПО Группы.ГруппаДоступа = Значения.ГруппаДоступа"
```

**B. Narrow keys → virtual table with parameters → join → group.** When a virtual table (`Обороты` / `Остатки`) is joined with a data set and then grouped: build a small key temp table first (`РАЗЛИЧНЫЕ` + `ИНДЕКСИРОВАТЬ ПО`), push the selective filters into the **virtual-table parameters** via `В (ВЫБРАТЬ … ИЗ ВТ_Ключи)`, and only then join and group. Also set the virtual-table **periodicity to match the join**: joining by `Регистратор` with periodicity `Авто` breaks the plan — use explicit `Регистратор`.

```bsl
// ✅ Key steps of the pattern
"ВЫБРАТЬ РАЗЛИЧНЫЕ
|	Движения.Номенклатура КАК Номенклатура,
|	Движения.Ячейка КАК Ячейка,
|	Движения.Регистратор КАК Регистратор
|ПОМЕСТИТЬ ВТ_Ключи
|ИЗ
|	ВТ_ДвиженияПоНазначению КАК Движения
|ИНДЕКСИРОВАТЬ ПО
|	Номенклатура, Ячейка, Регистратор
|;
|ВЫБРАТЬ
|	Обороты.Номенклатура КАК Номенклатура,
|	СУММА(Обороты.КоличествоОборот) КАК КоличествоОборот
|ИЗ
|	РегистрНакопления.ТоварыВЯчейках.Обороты(
|		, , Регистратор,
|		Номенклатура В (ВЫБРАТЬ Ключи.Номенклатура ИЗ ВТ_Ключи КАК Ключи)
|			И Ячейка В (ВЫБРАТЬ Ключи.Ячейка ИЗ ВТ_Ключи КАК Ключи)) КАК Обороты
|	ВНУТРЕННЕЕ СОЕДИНЕНИЕ ВТ_Ключи КАК Ключи
|	ПО Обороты.Номенклатура = Ключи.Номенклатура
|		И Обороты.Ячейка = Ключи.Ячейка
|		И Обороты.Регистратор = Ключи.Регистратор
|СГРУППИРОВАТЬ ПО
|	Обороты.Номенклатура"
```

Notes: the virtual-table parameter filter uses only the **selective** key fields (not all join fields); the join condition then applies the full key. If a field (e.g. `Регистратор`) is not actually needed by the business logic — drop it from both the join and the periodicity: cheaper still.

### Join vs Subquery

```bsl
// ✅ PREFERRED: Join (usually faster)
"ВЫБРАТЬ
|	Заказы.Ссылка КАК Заказ,
|	Контрагенты.ИНН КАК ИНН
|ИЗ
|	Документ.ЗаказКлиента КАК Заказы
|		ЛЕВОЕ СОЕДИНЕНИЕ Справочник.Контрагенты КАК Контрагенты
|		ПО Заказы.Контрагент = Контрагенты.Ссылка"

// ⚠️ AVOID: Subquery in SELECT (N+1 problem)
"ВЫБРАТЬ
|	Заказы.Ссылка КАК Заказ,
|	(ВЫБРАТЬ К.ИНН ИЗ Справочник.Контрагенты КАК К 
|	 ГДЕ К.Ссылка = Заказы.Контрагент) КАК ИНН
|ИЗ
|	Документ.ЗаказКлиента КАК Заказы"
```

### Avoid Aggregation in Subqueries

```bsl
// ❌ SLOW: Subquery with aggregation
"ВЫБРАТЬ
|	Номенклатура.Ссылка,
|	(ВЫБРАТЬ СУММА(Остатки.Количество) ...) КАК Остаток
|ИЗ
|	Справочник.Номенклатура КАК Номенклатура"

// ✅ FAST: Join with pre-aggregated data
"ВЫБРАТЬ
|	Номенклатура.Ссылка КАК Номенклатура,
|	ЕСТЬNULL(Остатки.КоличествоОстаток, 0) КАК Остаток
|ИЗ
|	Справочник.Номенклатура КАК Номенклатура
|		ЛЕВОЕ СОЕДИНЕНИЕ РегистрНакопления.ТоварыНаСкладах.Остатки КАК Остатки
|		ПО Номенклатура.Ссылка = Остатки.Номенклатура"
```

## DCS (Data Composition System) Optimization

### Efficient DCS Queries

1. **Use parameters in query text:**
   ```bsl
   // Pass parameters to virtual table
   РегистрНакопления.Остатки.Остатки(&Период, Склад = &Склад)
   ```

2. **Limit data at source:**
   ```bsl
   // Add conditions in DataSet query, not in DCS settings
   ГДЕ Период >= &НачалоПериода
   ```

3. **Use ЕСТЬNULL for outer joins:**
   ```bsl
   ЕСТЬNULL(Остатки.Количество, 0) КАК Количество
   ```

## Composite Type Dereferencing (ITS Standard)

Avoid dereferencing composite type reference fields directly — the system creates queries for **ALL** possible types.

```bsl
// ❌ SLOW: Dereferences ALL registrar types (can be hundreds)
"ВЫБРАТЬ
|	ТоварыНаСкладах.Регистратор.Дата КАК ДатаДокумента
|ИЗ
|	РегистрНакопления.ТоварыНаСкладах КАК ТоварыНаСкладах"

// ✅ FAST: Use ВЫРАЗИТЬ to specify exact type
"ВЫБРАТЬ
|	ВЫРАЗИТЬ(ТоварыНаСкладах.Регистратор КАК Документ.ПоступлениеТоваровУслуг).Дата КАК ДатаДокумента
|ИЗ
|	РегистрНакопления.ТоварыНаСкладах КАК ТоварыНаСкладах"

// ✅ For multiple known types, use ВЫБОР/КОГДА
"ВЫБРАТЬ
|	ВЫБОР
|		КОГДА ТоварыНаСкладах.Регистратор ССЫЛКА Документ.ПоступлениеТоваровУслуг
|			ТОГДА ВЫРАЗИТЬ(ТоварыНаСкладах.Регистратор КАК Документ.ПоступлениеТоваровУслуг).Дата
|		КОГДА ТоварыНаСкладах.Регистратор ССЫЛКА Документ.РеализацияТоваровУслуг
|			ТОГДА ВЫРАЗИТЬ(ТоварыНаСкладах.Регистратор КАК Документ.РеализацияТоваровУслуг).Дата
|	КОНЕЦ КАК ДатаДокумента
|ИЗ
|	РегистрНакопления.ТоварыНаСкладах КАК ТоварыНаСкладах"
```

## Use ПРЕДСТАВЛЕНИЕ for Display (ITS Standard)

When you only need text representation, use `ПРЕДСТАВЛЕНИЕ()` to avoid extra joins:

```bsl
// ❌ Creates additional subquery for Справочник.Склады
"ВЫБРАТЬ
|	ТоварыНаСкладах.Склад.Наименование
|ИЗ
|	РегистрНакопления.ТоварыНаСкладах КАК ТоварыНаСкладах"

// ✅ Optimal: No extra join
"ВЫБРАТЬ
|	ПРЕДСТАВЛЕНИЕ(ТоварыНаСкладах.Склад) КАК СкладПредставление
|ИЗ
|	РегистрНакопления.ТоварыНаСкладах КАК ТоварыНаСкладах"
```

## Avoid Joins with Subqueries (ITS Standard)

Never use subqueries in JOIN — use temporary tables instead:

```bsl
// ❌ WRONG: Join with subquery
"ВЫБРАТЬ ...
|ИЗ
|	Документ.Заказ КАК Заказы
|		ЛЕВОЕ СОЕДИНЕНИЕ (
|			ВЫБРАТЬ Товары.Заказ, СУММА(Товары.Сумма) КАК Сумма
|			ИЗ Документ.Заказ.Товары КАК Товары
|			СГРУППИРОВАТЬ ПО Товары.Заказ
|		) КАК ИтогиТоваров
|		ПО Заказы.Ссылка = ИтогиТоваров.Заказ"

// ✅ CORRECT: Use temporary table
"ВЫБРАТЬ
|	Товары.Ссылка КАК Заказ,
|	СУММА(Товары.Сумма) КАК Сумма
|ПОМЕСТИТЬ ИтогиТоваров
|ИЗ
|	Документ.Заказ.Товары КАК Товары
|СГРУППИРОВАТЬ ПО
|	Товары.Ссылка
|ИНДЕКСИРОВАТЬ ПО
|	Заказ
|;
|ВЫБРАТЬ ...
|ИЗ
|	Документ.Заказ КАК Заказы
|		ЛЕВОЕ СОЕДИНЕНИЕ ИтогиТоваров КАК ИтогиТоваров
|		ПО Заказы.Ссылка = ИтогиТоваров.Заказ"
```

## Avoid Joins with Virtual Tables (ITS Standard)

Extract virtual table results to temporary table before joining:

```bsl
// ⚠️ May be slow: Direct join with virtual table
"ВЫБРАТЬ ...
|ИЗ
|	Справочник.Номенклатура КАК Номенклатура
|		ЛЕВОЕ СОЕДИНЕНИЕ РегистрНакопления.ТоварыНаСкладах.Остатки(&Дата,) КАК Остатки
|		ПО Номенклатура.Ссылка = Остатки.Номенклатура"

// ✅ BETTER: First extract to temporary table
"ВЫБРАТЬ
|	Остатки.Номенклатура КАК Номенклатура,
|	Остатки.КоличествоОстаток КАК Остаток
|ПОМЕСТИТЬ ВТОстатки
|ИЗ
|	РегистрНакопления.ТоварыНаСкладах.Остатки(&Дата,) КАК Остатки
|ИНДЕКСИРОВАТЬ ПО
|	Номенклатура
|;
|ВЫБРАТЬ ...
|ИЗ
|	Справочник.Номенклатура КАК Номенклатура
|		ЛЕВОЕ СОЕДИНЕНИЕ ВТОстатки КАК Остатки
|		ПО Номенклатура.Ссылка = Остатки.Номенклатура"
```

## Avoid OR in WHERE — Use ОБЪЕДИНИТЬ ВСЕ (ITS Standard)

`OR` in `WHERE` prevents index usage. Split into UNION queries:

```bsl
// ❌ SLOW: OR prevents index usage
"ВЫБРАТЬ
|	Товары.Ссылка
|ИЗ
|	Справочник.Номенклатура КАК Товары
|ГДЕ
|	Товары.Артикул = &Артикул
|	ИЛИ Товары.Код = &Код"

// ✅ FAST: Two indexed queries with UNION
"ВЫБРАТЬ
|	Товары.Ссылка
|ИЗ
|	Справочник.Номенклатура КАК Товары
|ГДЕ
|	Товары.Артикул = &Артикул
|
|ОБЪЕДИНИТЬ ВСЕ
|
|ВЫБРАТЬ
|	Товары.Ссылка
|ИЗ
|	Справочник.Номенклатура КАК Товары
|ГДЕ
|	Товары.Код = &Код"
```

## ОБЪЕДИНИТЬ vs ОБЪЕДИНИТЬ ВСЕ (ITS Standard)

Prefer `ОБЪЕДИНИТЬ ВСЕ` when no duplicate rows expected:

```bsl
// ⚠️ SLOWER: ОБЪЕДИНИТЬ performs additional grouping
"ВЫБРАТЬ ... ИЗ Документ.Приход
|ОБЪЕДИНИТЬ
|ВЫБРАТЬ ... ИЗ Документ.Расход"

// ✅ FASTER: ОБЪЕДИНИТЬ ВСЕ skips grouping
"ВЫБРАТЬ ... ИЗ Документ.Приход
|ОБЪЕДИНИТЬ ВСЕ
|ВЫБРАТЬ ... ИЗ Документ.Расход"
```

### No РАЗЛИЧНЫЕ inside ОБЪЕДИНИТЬ operands

`ОБЪЕДИНИТЬ` (without `ВСЕ`) already collapses duplicates over the **combined** result. `РАЗЛИЧНЫЕ` in the operands adds a second sort/group over the same data for nothing:

```bsl
// ❌ Redundant: three dedup passes (2 × РАЗЛИЧНЫЕ + union collapse)
"ВЫБРАТЬ РАЗЛИЧНЫЕ Поля... ИЗ ВТ_Движения
|ОБЪЕДИНИТЬ
|ВЫБРАТЬ РАЗЛИЧНЫЕ Поля... ИЗ РегистрНакопления.Запасы"

// ✅ One dedup pass — the union's own collapse
"ВЫБРАТЬ Поля... ИЗ ВТ_Движения
|ОБЪЕДИНИТЬ
|ВЫБРАТЬ Поля... ИЗ РегистрНакопления.Запасы"
```

Keep `РАЗЛИЧНЫЕ` only where it does unique work — e.g. when first materializing the temp table. The same logic bans `РАЗЛИЧНЫЕ` on top of `СГРУППИРОВАТЬ ПО` over the same fields: grouping already yields unique rows.

## Index Alignment (ITS Standard)

Ensure query conditions match available indexes:

**Index requirements:**
1. Index must contain **all fields** from the condition
2. Fields must be at the **beginning** of the index
3. Fields must be **consecutive** (no gaps)

```bsl
// Given index: (Организация, Контрагент, Дата)

// ✅ Index will be used — fields are at the beginning
"ГДЕ Организация = &Орг И Контрагент = &Контр"

// ❌ Index NOT used — skipped first field
"ГДЕ Контрагент = &Контр И Дата = &Дата"

// ⚠️ Partial use — gap in fields
"ГДЕ Организация = &Орг И Дата = &Дата"
```

**Creating additional indexes:**
- Set "Индексировать" = "Индексировать с доп. упорядочиванием" for frequently filtered attributes
- Add `ИНДЕКСИРОВАТЬ ПО` for temporary tables used in joins

---

**Reference**: [ITS Query Optimization Standards](https://its.1c.ru/db/v8std/browse/13/-1/26/28)

**Remember**: Verify metadata attributes exist using `metadatasearch` and `get_metadata_details` (for exact types and indexes) before writing queries.
