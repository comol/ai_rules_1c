---
description: 1C Data Composition System (СКД / DCS) design rules — data sets, computed fields vs resources, parameters, settings, variants, programmatic override patterns. Load when designing or reviewing a DCS-based report.
alwaysApply: false
category: development
---

# DCS / СКД — Report Design Rules

The 1C Data Composition System (СхемаКомпоновкиДанных, СКД) is the canonical engine for reports. The rules below cover design decisions that recur in code review and that the structural skill (`content/skills/1c-metadata-manage/docs/skd-manage.md`) intentionally does not opine on.

> **Scope.** This file owns *report design* rules. XML / schema mechanics for `.dcs` files live in the `content/skills/1c-metadata-manage/docs/skd-manage.md` skill (XML structure, datasets API, query parameters API). Anti-patterns of slow queries inside a DCS — `anti-patterns.md` and `dev-standards-architecture.md §3 → "Queries"`.

## 1. Choosing the data-set type

| Data-set type | Use when |
|---|---|
| **Запрос** (Query) | Default. The data already lives in metadata and a query expresses what is needed. |
| **Объединение** (Union) | Combining two or more independent queries that produce the same column shape (e.g. движения + остатки). |
| **Объект** (Object) | The data is computed in BSL (external system, complex aggregation, table built procedurally) and exposed as a `ТаблицаЗначений`. Use sparingly — loses index pushdown and parameter pushdown. |

Default: **Запрос** for everything you can express as a query. Promote to **Объединение** only when shape really matches. Use **Объект** only when no query expression is possible.

## 2. Computed fields vs resources

Two different mechanisms — choose by **when the value is materialized**, not by "ease of typing".

| Mechanism | When evaluated | Use for |
|---|---|---|
| **Вычисляемое поле** (Computed field) | Per row, after the query produces the row | Per-row derivations (representation, concatenation, casts, simple arithmetic on existing fields). |
| **Ресурс** (Resource) | At aggregation, on the engine's totals | Quantities that must be summed / averaged / counted across groupings. Resources participate in totals; computed fields do not unless wrapped in `Вычислить()`. |
| **Поле запроса** (Query field) | Once, when the query runs on the DBMS | Anything the DBMS can compute — preferred for everything except presentation-only and aggregation-only logic. |

Default order of preference: **query field → ресурс → вычисляемое поле**. Pushing computation into the query reduces the row count the engine has to ship to the client.

Anti-pattern: aggregating in `Вычисляемое поле` via `Вычислить("Сумма(...)", ...)` — losing index usage and forcing a full row scan. Use a **Ресурс** instead.

## 3. Parameters

- **`Параметр` vs `ПараметрВыбора`.** `Параметр` is bound to the query / dataset; `ПараметрВыбора` is a UI-level filter. They are not interchangeable. Use `Параметр` for inputs the query needs (e.g. `&Период`); use `ПараметрВыбора` for restricting the user's choice in a selection field.
- **Periodicity parameters** for register virtual tables (`Остатки(&Период, ...)`, `ОстаткиИОбороты(&НачалоПериода, &КонецПериода, ...)`) — **always** parameter-driven, never literal dates in the query text.
- **`Доступен` (Available) flag** — set to `Ложь` for parameters that are computed programmatically (e.g. current user, current date) and must not be editable by the user.
- **`Использование` (Use)** — `ВсегдаИспользовать` only for parameters that genuinely cannot be empty; otherwise `Авто` so the engine can drop unused parameters from the plan.

## 4. Variants and settings

- **Variants** are *separate report shapes*, not user filters. Use them to split fundamentally different presentations of the same report (e.g. "By document" vs "By counterparty"). Adding a variant for "the same report with a different default filter" is wrong — that is what user settings are for.
- **User settings** (`Настройки пользователя`) — keep the set minimal. Every user setting is a maintenance contract; reduce surface by:
  - marking everything that is **not** intended as a user knob as `Недоступен` (Not available);
  - using `БыстрыеНастройки` (quick settings) for the 3–5 fields the user actually changes;
  - defaulting `Авто` instead of empty values for `Период`, `Организация`, etc.

## 5. Programmatic override

For non-trivial reports the canonical pattern is **programmatic override of the composition** — not editing the schema for each report variant. Hook points in priority order:

1. **`ПриКомпоновкеРезультата`** (object module of the report) — preferred. Modify the composition before / after the standard composer runs.
2. **`ПриЗагрузкеПользовательскихНастроекНаСервере` / `ПриЗагрузкеНастроекНаСервере`** — programmatic setting injection (filters, parameters) at form load.
3. **`КомпоновщикНастроек.Настройки`** — direct manipulation of the settings tree.

Pattern for programmatic filter injection (full template — error handling, structured logging, no double-output on the standard handler):

```bsl
Процедура ПриКомпоновкеРезультата(ДокументРезультат, ПараметрыВывода, СтандартнаяОбработка)

	// We render the result ourselves; the platform must NOT also run the default composition.
	СтандартнаяОбработка = Ложь;

	КомпоновщикНастроек.ЗагрузитьНастройки(СхемаКомпоновкиДанных.НастройкиПоУмолчанию);
	УстановитьПараметр("Период",       ПериодОтчета);
	УстановитьФильтр("Организация",    Организация);

	Попытка

		МакетКомпоновки = Новый КомпоновщикМакетаКомпоновкиДанных().Выполнить(
			СхемаКомпоновкиДанных, КомпоновщикНастроек.Настройки, , , Тип("ГенераторМакетаКомпоновкиДанных"));

		ПроцессорКомпоновки = Новый ПроцессорКомпоновкиДанных;
		ПроцессорКомпоновки.Инициализировать(МакетКомпоновки);

		ПроцессорВывода = Новый ПроцессорВыводаРезультатаКомпоновкиДанныхВТабличныйДокумент;
		ПроцессорВывода.УстановитьДокумент(ДокументРезультат);
		ПроцессорВывода.Вывести(ПроцессорКомпоновки);

	Исключение

		ДанныеОшибки = Новый Структура;
		ДанныеОшибки.Вставить("Отчет",     Метаданные().Имя);
		ДанныеОшибки.Вставить("Период",    ПериодОтчета);
		ДанныеОшибки.Вставить("Подробно",  ПодробноеПредставлениеОшибки(ИнформацияОбОшибке()));

		ЗаписьЖурналаРегистрации(
			"Отчет." + Метаданные().Имя + ".Ошибка",
			УровеньЖурналаРегистрации.Ошибка,
			Метаданные(),
			,
			НСтр("ru = 'Не удалось сформировать отчет.'"),
			ДанныеОшибки);

		ВызватьИсключение;

	КонецПопытки;

КонецПроцедуры
```

Notes:

- `СтандартнаяОбработка = Ложь` is set **before** the `Попытка` block — if a handler exits via `ВызватьИсключение` mid-render, the platform must not silently fall back to the default composition and produce a half-baked second document.
- Logging follows `logging-strategy.md §3-§5`: dotted event name (`Отчет.<Имя>.Ошибка`), structured `Данные = Структура`, `ПодробноеПредставлениеОшибки` (not `КраткоеПредставлениеОшибки`), and re-raise so the caller still sees the failure.
- `УстановитьПараметр` and `УстановитьФильтр` are project-local helpers — extract them into the report's manager module to keep the override compact.

## 6. RLS interaction

- DCS queries run under the user's roles by default; any restriction `ОграничениеДоступа` of the involved metadata objects applies.
- If a report intentionally needs full visibility (regulatory reports for accounting / payroll), wrap the composition in `УстановитьПривилегированныйРежим(Истина)` **only** in the `ПриКомпоновкеРезультата` handler, and always pair it with `УстановитьПривилегированныйРежим(Ложь)` in a `Попытка`/`КонецПопытки` even if the inner code is supposed to be safe. Document the reason inline.
- Do not silently widen visibility — every privileged-mode use must be justified in the report's description or PRD.

## 7. Performance checklist

- **Indexed filter fields** — every parameter pushed into a query `ГДЕ` must hit an index. Check via the configurator's "Анализ производительности" or `СтруктураХраненияБазыДанных`.
- **Virtual tables** — filter through parameters (`Остатки(&Период, Условие)`), never through `ГДЕ` after the virtual call. Hard rule (owner: `dev-standards-architecture.md §3 → "Queries"`; catalog entry with fix template: `anti-patterns.md §4`).
- **`ПЕРВЫЕ N`** when the report is paginated or "top-N" by nature — push the limit into the query, not into the row-formatting hook.
- **Avoid `ВЫРАЗИТЬ` on the left side of `ГДЕ`** — it disables index usage.
- **`Объект`-typed datasets** that pull large `ТаблицаЗначений` from BSL are the most common performance trap; consider materializing into a temporary information register if the data must be reused.

## 8. Companion rules

| Concern | File |
|---|---|
| XML / schema mechanics for `.dcs` | `content/skills/1c-metadata-manage/docs/skd-manage.md` (skill) |
| Query anti-patterns | `anti-patterns.md` |
| Authoritative query rules | `dev-standards-architecture.md §3 → "Queries"` |
| Long-running report execution | `platform-solutions.md §2 → "Long-running operations"` |
| Register design (data side) | `registers-design.md` |
