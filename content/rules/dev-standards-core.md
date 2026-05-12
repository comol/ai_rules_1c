---
description: Development standards — project parameters, code style, modification comments, naming, documentation headers
alwaysApply: false
category: development
---

# Development Standards — Core

## 1. Project Parameters (.dev.env)

**Before starting any code task**, read the `.dev.env` file from the project root. If it does not exist — **stop and request parameters from the user** (or run the 1c-rules installer, which creates `.dev.env` from the template). Guessing values is PROHIBITED.

`.dev.env` is the **single source of truth** for project parameters across the whole rules set. There is no `infobasesettings.md`, no separate per-command settings file — all rules, on-demand instructions, slash commands and subagents read from `.dev.env`.

### Code-generation parameters (mandatory for any code task)

| Parameter | Effect |
|---|---|
| `{PREFIX}` | Prefix for ALL new metadata objects, attributes, form elements, roles |
| `{COMPANY}` | Used in modification comment templates |
| `{DEVELOPER}` | Used in modification comment templates |
| `{PLATFORM_VERSION}` | Determines available platform features (e.g. `Асинх` / `Ждать` from 8.3.18 vs `ОписаниеОповещения` callbacks for older versions). See `dev-standards-architecture.md §3 "Async and Modality"` |
| `{COMMENT_OPEN}` | Opening modification comment template with placeholders `{COMPANY}`, `{DEVELOPER}`, `{DATE}`, `{TASK}` |
| `{COMMENT_CLOSE}` | Closing modification comment template |
| `{NEW_OBJECTS_IN}` | Where to place new objects: `main_configuration` (default) or `extension` |

### Infobase / deployment parameters (mandatory for IB-bound commands and tests)

Used by `/loadfrom1cbase`, `/update1cbase`, `/getconfigfiles`, `/deploy-and-test` and the `1c-tester` subagent. Not required for pure code tasks.

| Parameter | Effect |
|---|---|
| `{PLATFORM_PATH}` | 1C platform install dir (must contain `bin\1cv8.exe`); used as the executable for all Designer-mode commands |
| `{INFOBASE_KIND}` | `file` → `/F`, `server` → `/S` flag for Designer |
| `{INFOBASE_PATH}` | Path to file infobase or connection string of server infobase |
| `{IB_USER}` / `{IB_PASSWORD}` | Optional credentials (`/N`, `/P`); empty values omit the flags |
| `{EXTENSION_NAME}` | Optional `-Extension` argument; empty = main configuration |
| `{EXPORT_PATH}` | Source-export directory; empty = current repository root |
| `{LOG_PATH}` | Designer log file (must be writable) |
| `{INFOBASE_PUBLISH_URL}` | Web-publish URL of the test infobase for `1c-tester` UI tests; empty = UI tests are skipped |

Task number `{TASK}` is **only required when modification comment markers are produced** — i.e. when the change touches **typical (standard) configuration code** and the templates `{COMMENT_OPEN}` / `{COMMENT_CLOSE}` reference `{TASK}`. For new objects with `{PREFIX}` (no per-method markers) and for review / analysis / documentation tasks `{TASK}` is **not required** — do not block on it.

When `{TASK}` is required and not provided — ask the user once and reuse the same value across the whole change.

> For tasks without code generation (review, analysis, documentation) — code-generation parameters are not blocking. Infobase parameters are only consulted by IB-bound commands.

See `.dev.env.example` for the template.

## 2. Code Style (single source of truth — referenced from `AGENTS.md`)

### Formatting
- **Indentation:** TAB only (not spaces).
- **Line length:** ≤ 120 characters when the line can be wrapped correctly. Don't introduce a line break that leaves a single variable on a new line.
- **One statement per line.** Single-line constructs with complex logic are prohibited.
- In conditions and loops, add blank lines before and after the code inside the block for better readability.
- Follow linter / BSL Language Server recommendations. Use `//BSLLS:` comments for targeted, justified suppressions.

### Alignment
- For groups of similar assignments **into local variables** — align `=` with spaces.
- **DO NOT** align when setting object properties via dot notation — use single space around `=`.

### Quality Metrics

| Metric | Limit | Strictness |
|---|---|---|
| Method length | ≤ 200 lines (exception: query texts) | hard limit |
| Method length | > 100 lines — candidate for decomposition | review trigger |
| Control structure nesting | < 5 levels | hard limit |
| Cognitive complexity | < 15 | review trigger |
| Method parameters | ≤ 5 (additional via Structure as 6th) | hard limit |

### String Building
Use `СтрШаблон()` for composing strings, **NOT** concatenation via `+`.
Exception: simple `Prefix + Suffix` is acceptable when it reads better.

### Forbidden Calls and Constructs

- `Попытка ... Исключение` around DB reads/writes is **PROHIBITED**, except for explicit, well-justified transaction control.
- `ЗаписьЖурналаРегистрации()` is **PROHIBITED** unless explicitly requested by the task.
- `Сообщить()` for user notifications is **PROHIBITED**. Use `ОбщегоНазначения.СообщитьПользователю` (server) / `ОбщегоНазначенияКлиент.СообщитьПользователю` (client).
- `Выполнить()` and `Вычислить()` are **PROHIBITED** without extreme necessity (see `dev-standards-architecture.md §3`).
- Hardcoded credentials (passwords, tokens, API keys) in code are **PROHIBITED**.
- `?(Условие, Значение1, Значение2)` ternary operator is **PROHIBITED in any form**, including the simple non-nested case. Use `Если ... Иначе` or extract a small helper function. Rationale: keeps logic visible in step-debugger and code review. **[Project rule — stricter than ITS standard.]**
- Boolean comparisons against `Истина` / `Ложь` are forbidden — use the boolean expression directly.
- Yoda syntax (`Если 0 = Сумма`) is **PROHIBITED**.

### Naming

- **Variable names MUST reflect business meaning and role.** Type suffixes are allowed only when they remove ambiguity and do not turn into Hungarian notation.
- Hungarian notation (`МассивКонтрагентов`, `ТаблицаДанных`) is **PROHIBITED** — use the business name (`Контрагенты`, `Данные`).
- Names from the 1C global context (`Документы`, `Справочники`, `Пользователи`, `Регистры`, `Метаданные`, `Константы`, etc.) MUST NOT be used as local variables — they cause name collisions and reduce readability.
- The `Получить*` prefix in function names is discouraged when the return value is obvious from the name or when the function returns a collection (`Контрагенты()` over `ПолучитьКонтрагентов()`). Acceptable when delegating directly to a platform call or implementing a БСП-compatible API contract.
- **Boolean variables — positive names only** (`ПроверкаПройдена`, not `ПроверкаНеПройдена`).
- **"Magic numbers" are PROHIBITED** — extract into named variables/constants.
- **String value enumerations** — in alphabetical order.

### Conditions
- Complex conditions (3+ constructs) — extract into a separate method.

### Function Parameters
- Function parameter MUST NOT be used as additional output — all output via return value.
- For additional parameters — use constructor function pattern:

```bsl
Функция ПараметрыЗаполнения() Экспорт
	Параметры = Новый Структура;
	Параметры.Вставить("Дата");
	Параметры.Вставить("Валюта");
	Параметры.Вставить("ПересчитыватьСумму", Истина);
	Возврат Параметры;
КонецФункции
```

## 3. Modification Comments

Modification markers are used **only when modifying typical (standard) code** in typical configuration modules.

### Format
- Opening comment: value of `{COMMENT_OPEN}` from `.dev.env`
- Closing comment: value of `{COMMENT_CLOSE}` from `.dev.env`
- A space is mandatory after `//`

### Typical Code Modification
Removed typical code — **comment out, DO NOT delete**:

```bsl
// {COMMENT_OPEN}
НовоеЗначение = {PREFIX}ПреобразоватьЗначение(Значение1);
// ТиповаяПроцедура(Значение1, Значение2);
ТиповаяПроцедура(НовоеЗначение, Значение2);
// {COMMENT_CLOSE}
```

### New Procedures in Typical Modules
Comment is placed **inside** the procedure, after the header:

```bsl
Функция НоваяФункция(Параметр) Экспорт
	// {COMMENT_OPEN}
	// ... code ...
	Возврат Результат;
	// {COMMENT_CLOSE}
КонецФункции
```

### Entirely New (Non-Typical) Objects
In modules of new objects (with `{PREFIX}`) — markers per method are **NOT NEEDED**. Instead — **a single block at the module header** describing the object.

### General Rules
- `TODO` / `FIXME` must contain a task reference: `// TODO No.14752: description`
- **Pseudo-regions via comments are PROHIBITED** — use only `#Область` / `#КонецОбласти`

## 4. Metadata Naming

| Element | Rule |
|---|---|
| New metadata objects | Prefix `{PREFIX}` in name (e.g., `{PREFIX}ContractAmount`) |
| Object synonyms | No prefix. If conflicts — add `({COMPANY})` |
| New roles | Prefix `{PREFIX}` |
| Subsystems | `{PREFIX}AddedObjects` and `{PREFIX}ModifiedObjects` |
| Attributes of typical objects | Prefix `{PREFIX}` |
| Form elements on typical forms | Prefix `{PREFIX}` |

**Inside non-typical (new) objects** (name already has `{PREFIX}`):
- Attributes, tabular sections, form elements, commands, procedures — **WITHOUT prefix**

- Place all new objects into subsystems
- Composite types used repeatedly — via `DefinedType`

### Object Type Selection

| Task | Object Type |
|---|---|
| Reference data | `Catalog` |
| Business transactions | `Document` |
| Quantity/amount accumulation | `AccumulationRegister` |
| Arbitrary data with dimensions | `InformationRegister` |
| User reports | `Report` (with DCS) |
| Data processing | `DataProcessor` |
| Fixed set of values | `Enum` |

## 5. Procedure/Function Documentation

Mandatory for all `Экспорт` procedures/functions (except predefined handlers):

```bsl
// Возвращает спецодежду для должности на указанную дату.
//
// Параметры:
//  ДатаДействия - Дата
//  Должность - СправочникСсылка.Должности
//
// Возвращаемое значение:
//  СправочникСсылка.{PREFIX}СпецодеждаДляДолжностей
//
Функция АктуальнаяСпецодеждаДляДолжности(ДатаДействия, Должность) Экспорт
```

- Description starts with a verb: "Возвращает...", "Проверяет...", "Рассчитывает..."
- DO NOT start with "Процедура...", "Функция..." or the function name
- For structure parameters — describe keys via `*`
- For arrays — specify element type

## 6. Typography

These rules apply only to 1C code artifacts: modules, in-module comments, identifiers, string literals, metadata synonyms / presentations and user-facing messages. Project markdown files and rule documentation are out of scope.

- **Do not use the letter «ё»** in 1C code and user-facing configuration text. Replace it with «е» in module comments, metadata synonyms, presentations and user messages. Rationale: keyboard-layout drift across the team and in baseline configurations breaks text search.
- **Do not use the em-dash** `—`. Replace it with a hyphen `-`. Rationale: encoding mismatches in the 1C toolchain (especially in event log and platform logs) turn the em-dash into `?`.
- For user-facing text use guillemet quotes `«...»`. In code string literals — standard `"..."`.
- Do not use non-breaking spaces or other invisible Unicode characters in code.

## 7. Comments — OK / NOT OK Examples

Goal: cut LLM noise and keep only useful comments. See also `AGENTS.md → Comments` for the headline rule.

### NOT OK — code paraphrase and noise

```bsl
// Получаем массив контрагентов
Контрагенты = ПолучитьКонтрагентов();

// Цикл по строкам таблицы
Для Каждого Строка Из Таблица Цикл

// Возвращаем результат
Возврат Результат;
```

```bsl
//////////////////////////////////////////////////////////////////
// Модуль: ОбщегоНазначения
// Автор: Иванов И.И.
// Дата: 15.03.2024
// Описание: Общие функции
// История изменений:
//   15.03.2024 — добавлено
//   17.03.2024 — исправлено
//////////////////////////////////////////////////////////////////
```

Decorative `///` banners and module headers with authorship / change history are forbidden — git already tracks that information.

### OK — motivation, context, constraints

```bsl
// НДС не начисляется при экспорте, см. ст. 164 НК РФ
Если Контрагент.Резидент И Не Документ.Экспорт Тогда

// Кеш используется потому, что метод вызывается ~10000 раз при проведении
// крупных накладных и каждый вызов делает запрос к регистру цен.
ИндексЦен = Новый Соответствие;

// Хак: платформа 8.3.23 не возвращает корректный тип в РазделительИБ
// при первом вызове после старта сеанса - повторяем запрос один раз.
Тип = Метаданные.ОбщиеРеквизиты.РазделительИБ.Тип;
Если Тип.Типы().Количество() = 0 Тогда
    Тип = Метаданные.ОбщиеРеквизиты.РазделительИБ.Тип;
КонецЕсли;

// TODO No.14752: после миграции на платформу 8.3.25 убрать обходной путь.
```

### Verification rule

Before keeping a comment, answer: **"What does this comment tell the reader that the code itself does not?"** If the answer is "nothing" — delete the comment.

## 8. Internal Code Review After Each Edit

After any code change, perform a brief internal review covering: style, readability, correctness, edge cases, security, concurrency / locks / transactions, BSL-LS compliance. If issues are found — fix them and re-run the cycle until the code is clean.

Always consider whether an external transaction already exists (e.g. an object-write transaction) before opening a new one. See `platform-solutions.md` for the canonical templates.
