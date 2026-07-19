# 1C Query Optimization Skill (Advanced Patterns)

For project-wide query work — load the router `content/rules/query-design.md` first. Authoritative hard rules (formatting, aliases, parameters, no queries in loops) — `dev-standards-architecture.md §3 → "Queries"`. Anti-patterns with examples (query in loop, subquery in SELECT, virtual table filter in WHERE, missing `ПЕРВЫЕ N`) — `anti-patterns` rule.

## When to Use

Invoke this skill when:
- Working with complex multi-step data processing
- Optimizing joins and subqueries
- Implementing DCS reports
- Processing large datasets in portions

## Temporary Tables

Use temporary tables for:
- Complex multi-step data processing
- Joining data from multiple sources
- Reusing intermediate results

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
