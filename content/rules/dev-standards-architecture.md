---
description: Development standards — architecture patterns, extensions, platform standards, code smells
alwaysApply: false
category: development
---

# Development Standards — Architecture & Platform

## 1. Architecture Patterns

### Code Placement
- Business logic — **in common modules**, not in form modules
- Common-module names follow the БСП suffix convention: no suffix — server-only module (`РаботаСЗаказами`); `Клиент` — client-only (`РаботаСЗаказамиКлиент`); `КлиентСервер` — compiled on both sides; `ВызовСервера` — server module callable from the client; `Глобальный` — global client module; `ПовтИсп` — cached return values (повторное использование возвращаемых значений); `Переопределяемый` — project override hooks
- Server object modules — mandatory preprocessor: `#Если Сервер Или ТолстыйКлиентОбычноеПриложение Или ВнешнееСоединение Тогда`

### "Result-Structure" Pattern
Return compound results via Structure:

```bsl
Результат = Новый Структура;
Результат.Вставить("ПроверкаПройдена", ПроверкаПройдена);
Результат.Вставить("ТекстОшибки", ТекстОшибки);
Возврат Результат;
```

### "Early Return" Pattern
Reduce nesting by returning early on precondition failures:

```bsl
Если Отказ Тогда
	Возврат;
КонецЕсли;

Если Не ЗначениеЗаполнено(ДатаДействия) Тогда
	Возврат ЗначениеПоУмолчанию;
КонецЕсли;
```

### "Value Table Search" Pattern

```bsl
СтруктураОтбора = Новый Структура("ВидСпецодежды", ТекущаяСтрока.ВидСпецодежды);
НайденныеСтроки = ТаблицаДанных.НайтиСтроки(СтруктураОтбора);
Если НайденныеСтроки.Количество() = 0 Тогда
	Продолжить;
КонецЕсли;
```

### Event Subscriptions
Preferable over modifying typical modules. All subscription methods — via common module `{PREFIX}EventSubscriptions`.

### New Metadata Objects Placement
Determined by `{NEW_OBJECTS_IN}` parameter from `.dev.env`:

| `{NEW_OBJECTS_IN}` | Behavior |
|---|---|
| `main_configuration` | New objects go into main configuration. Extension — only for event interception |
| `extension` | New objects may be placed in extension. Main configuration not modified without explicit instruction |

Default: `main_configuration`.

### Background Jobs
Operations taking > 10 seconds — move to background jobs with progress indication. Do not block UI.

### Defensive Type Checking
BSL has no strict typing. Check type at function entry when critical:

```bsl
Если ТипЗнч(ДокументыИлиСсылка) <> Тип("Массив") Тогда
	Документы = Новый Массив;
	Документы.Добавить(ДокументыИлиСсылка);
Иначе
	Документы = ДокументыИлиСсылка;
КонецЕсли;
```

### Safe Structure Property Access
Always check key existence before access:

```bsl
Если ПараметрыОтчета.Свойство("ДатаНачала", ДатаНачала) Тогда
	// используем ДатуНачала
КонецЕсли;
```

### Collection Normalization
Normalize input to a single collection type for uniform processing. Use `ОбщегоНазначенияКлиентСервер.ЗначениеВМассиве()` (БСП) for single-to-array conversion.

## 2. Extensions

### Modification Priority
1. **Event subscriptions** (preferred)
2. **Extensions**
3. **Typical code modification** (last resort)

### Extension Directives
- `&Перед` / `&После` — preferred for simple interception
- `&ИзменениеИКонтроль` — only when the method body must be modified; change markers (`#Вставка` / `#Удаление`) and `ПродолжитьВызов()` are **mandatory** (without `ПродолжитьВызов()` the original method does not execute)
- Interceptor semantics, `ПродолжитьВызов()` rules, and extension anti-patterns — `extension-patterns.md` (practical companion)

### Placement Rules (when `{NEW_OBJECTS_IN} = main_configuration`)
- New metadata objects → main configuration
- New attributes of typical objects → main configuration
- Roles → main configuration

Regardless of `{NEW_OBJECTS_IN}`:
- Typical roles → DO NOT modify (create new ones with `{PREFIX}`)

### Forms in Extensions
Visual form editing in extensions — **minimize**. Changes — programmatically through code.

## 3. Platform Standards

### Async and Modality
- Modal calls are **PROHIBITED**: `Вопрос()`, `Предупреждение()`, `ВвестиЧисло()`, `ВвестиСтроку()`, `ВвестиДату()`, `ВвестиЗначение()`, `ОткрытьЗначение()` and any other synchronous-blocking dialogs.
- Approach depends on `{PLATFORM_VERSION}` from `.dev.env`:

| `{PLATFORM_VERSION}` | Approach |
|---|---|
| < 8.3.18 | `ОписаниеОповещения` (callback) |
| ≥ 8.3.18 | `Асинх` / `Ждать` (preferred) |

- Inside `Асинх` procedures use ONLY async analogs. Mixing `Асинх` / `Ждать` with non-async methods is **PROHIBITED**.
- Any dialog calls on the server are **PROHIBITED**.

### Client-Server Interaction
- **`&НаСервереБезКонтекста` is MANDATORY** for all server methods that do not access form data. `&НаСервере` is allowed only when the method directly reads/writes form attributes or elements.
- If a method only needs a form attribute value — pass it as a parameter and use `&НаСервереБезКонтекста`.

### Security
- `Выполнить()` and `Вычислить()` — **PROHIBITED** without extreme necessity.
- **Hardcoded credentials are PROHIBITED** — passwords, tokens, API keys in code are FORBIDDEN. Store via secrets subsystem of БСП or write-protected configuration constants.
- **RLS** — design with access restriction requirements in mind.

### Error Handling
- String localization — `НСтр("ru = '...'")` with `СтроковыеФункцииКлиентСервер.ПодставитьПараметрыВСтроку()`.
- Error collection — into a single variable via `Символы.ПС`.
- Logging — `ПодробноеПредставлениеОшибки(ИнформацияОбОшибке())`, NOT `КраткоеПредставлениеОшибки()`.
- Empty exception handlers are **PROHIBITED** — always log or re-raise.

> **Positive companion — `logging-strategy.md`.** This section is the *bans and minimum standards* side of error handling. The positive side (when to write to the event log at all, severity levels, event-category naming `<Subsystem>.<Operation>.<Outcome>`, structured payload via `ДанныеЖурналаРегистрации`, secrets / PII bans, rotation) lives in `logging-strategy.md`. Read both whenever you add or review error-handling code.

### Dates
- On server — `ТекущаяДатаСеанса()` instead of `ТекущаяДата()`. See `platform-solutions.md §6 → "Time on the server"`.

### Queries
- Verify metadata attributes (existence, names, types) **before** writing a query — see `AGENTS.md → MCP Tool Calling` (rule #3 «verify before writing»; metadata-first via `get_object_dossier` / `metadatasearch`).
- Look for existing query examples before writing complex queries (`templatesearch`, `search_code`).
- Query text formatting — on a new line at the same indentation level as the variable declaration:

```bsl
Запрос = Новый Запрос;
Запрос.Текст =
"ВЫБРАТЬ
|	Контрагенты.Ссылка КАК Ссылка,
|	Контрагенты.ИНН КАК ИНН
|ИЗ
|	Справочник.Контрагенты КАК Контрагенты";
```

- Always use an intermediate variable for query results. Method chaining is **PROHIBITED**:
  - Correct: `РезультатЗапроса = Запрос.Выполнить();`
  - Incorrect: `Запрос.Выполнить().Выгрузить()` / `Запрос.Выполнить().Выбрать()`.
- Always use `КАК` aliases for query fields (e.g. `Контрагенты.ИНН КАК ИНН`).
- **Queries inside loops are PROHIBITED.** Use batch queries with temporary tables. See `anti-patterns.md §1` and "Batch Query with Temp Table" template.
- Use `Запрос.УстановитьПараметр()` instead of string concatenation — prevents SQL injection and improves plan caching.
- For complex data retrieval prefer batch queries with temporary tables over multiple separate queries.
- Temporary tables — prefixed with `ВТ_`.
- Choose the join type from the required result semantics. Use `ВНУТРЕННЕЕ СОЕДИНЕНИЕ` when
  rows without a match must be discarded. Use `ЛЕВОЕ СОЕДИНЕНИЕ` when source rows must be
  preserved, and handle `NULL` explicitly.
- When accessing registers — filter by dimensions first (in virtual table parameters, not in `ГДЕ`).
- Do not modify register movements directly — only via the posting mechanism.
- When a limited result set is needed — use `ПЕРВЫЕ N`.
- Index all fields that participate in filters/joins via metadata.

### Cross-Platform Compatibility
- **COM objects** (`Новый COMОбъект(...)`) are **PROHIBITED** unless explicitly specified in the task.
- For Excel — use spreadsheet document or БСП, not `Excel.Application`.
- File paths — use `/` or platform functions; do not hardcode `\`.

### Platform Version Compatibility
- Before using any platform API method, verify it exists in `{PLATFORM_VERSION}` from `.dev.env`.
- Using methods from newer versions without checking is **PROHIBITED**.

## 4. Data Access — Reference Attribute Access

**Direct dot-notation access on references** (e.g. `Контрагент.ИНН`) loads the entire object from the database. **[Project rule — stricter than ITS standard.]** Outside trivial single-call handlers, the rule is a hard ban; in simple, non-loop code with one or two attributes ITS allows it, but the project default is to use dedicated БСП methods.

Use these methods instead:

| Method | Purpose | Example |
|--------|---------|---------|
| `ОбщегоНазначения.ЗначениеРеквизитаОбъекта` | Single attribute from one ref | `ОбщегоНазначения.ЗначениеРеквизитаОбъекта(Контрагент, "ИНН")` |
| `ОбщегоНазначения.ЗначенияРеквизитовОбъекта` | Multiple attributes from one ref | `ОбщегоНазначения.ЗначенияРеквизитовОбъекта(Контрагент, "ИНН, Наименование")` |
| `ОбщегоНазначения.ЗначениеРеквизитаОбъектов` | Same attribute from multiple refs | `ОбщегоНазначения.ЗначениеРеквизитаОбъектов(Контрагенты, "ИНН")` |
| `ОбщегоНазначения.ЗначенияРеквизитовОбъектов` | Multiple attributes from multiple refs | `ОбщегоНазначения.ЗначенияРеквизитовОбъектов(Контрагенты, "ИНН, КПП")` |

### Caching and Batch Retrieval

- Cache repeated reference-attribute lookups via `Соответствие` (Map). Full example — `anti-patterns.md §8 → "Missing Caching"`.
- For multiple references prefer batch queries (`ОбщегоНазначения.ЗначенияРеквизитовОбъектов`, or `ВЫБРАТЬ ... ГДЕ Ссылка В (&МассивСсылок)`) over per-reference calls in loops. Temp-table template — `anti-patterns.md → "Batch Query with Temp Table"`.

## 5. Performance Headlines

Mandatory baseline. Detailed anti-pattern catalog with severity — in `anti-patterns.md`. Platform pitfalls (long-running ops, temporary storage, collection search, external components) — in `platform-solutions.md`. Managed-lock theory and transaction patterns (configuration lock mode, implicit vs explicit transactions, canonical lock ordering, deadlock prevention, technological-log diagnostics) — in **`locks-and-transactions.md`**.

- **Server-side bulk.** Run mass operations on the server; avoid client-server round trips inside loops. Server methods that do not access form data — `&НаСервереБезКонтекста`.
- **Queries.** Never inside loops — use batch queries and temporary tables. Use `ПЕРВЫЕ N` when only a subset is needed. Index every filter/join field in metadata.
- **Privileged mode.** `УстановитьПривилегированныйРежим(Истина)` — only when needed and always paired with `УстановитьПривилегированныйРежим(Ложь)`. Check current state via `ПривилегированныйРежим()`.
- **Caching.** Cache repeated computations — `Соответствие` per call, session parameters per session, information registers cross-session. Reference attributes — via `ОбщегоНазначения.ЗначенияРеквизитов*` with a cache.
- **Collections.** Bulk fill — `ЗаполнитьЗначенияСвойств()`. Search: ≤ ~100 elements — `Найти()` / `НайтиПоЗначению()` is fine; ≥ ~1000 elements or inside a loop — index on `Соответствие` (O(1)) or `ТаблицаЗначений.Индексы.Добавить(...)` + `НайтиСтроки()`. See `platform-solutions.md §7 → "Searching in collections: choosing by complexity"`.
- **Transactions and managed locks.** Keep transactions short; no user interaction, no long-running operations, no external services inside. Account for implicit transactions (object write opens its own). Lock managed data **before** reading it, then read, then write — see `locks-and-transactions.md` for the full pattern set (posting with several registers, mass operations, status-log updates) and the project-wide lock-ordering contract. The worked posting example also lives in `platform-solutions.md §9 → "Managed locks and deadlock prevention"`.

## 6. Code Smells (see `anti-patterns` rule for the full catalog)

| Smell | Signs | Fix |
|---|---|---|
| **Data Clumps** | Same 3+ parameters passed together in multiple methods | Combine into Structure via constructor function |
| **Primitive Obsession** | Strings instead of enums, numeric codes instead of references | Use `Enum`, `CatalogRef`, `DefinedType` |
| **Divergent Change** | One module constantly changed for different reasons | Split module: each handles one responsibility (SRP) |
| **Shotgun Surgery** | One business logic change requires edits in 5+ places | Consolidate related logic into one common module |
| **Feature Envy** | Form module method heavily works with data of another object | Move method to the common module of that object |
| **Variable Reuse** | One variable stores different values at different stages | Create separate variable for each value |
