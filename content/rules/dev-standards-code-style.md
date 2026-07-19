---
description: BSL code style — formatting, quality metrics, forbidden constructs, naming, public API documentation, typography, comments, and internal review
alwaysApply: false
category: development
---

# Development Standards — BSL Code Style

**When to load this file:** before writing or reviewing BSL when formatting, naming, forbidden constructs, quality limits, public procedure documentation, typography, comment quality, or the internal review baseline is relevant.

Section numbers 2 and 5–8 are preserved from the former monolithic `dev-standards-core.md` for stable references.

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
- `Выполнить()` and `Вычислить()` are **PROHIBITED** without extreme necessity (see `dev-standards-architecture.md §3 → "Security"`).
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

Goal: cut LLM noise and keep only useful comments. See also `content/rules/coding-standards.md → "Comments"` for the headline rule (anchor from `AGENTS.md → Coding Standards`).

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

After any code change, perform a brief internal review. Scale it to the path:

- **Quick-fix** — correctness and edge cases of the changed fragment; plus locks / transactions when the edit sits near transactional code. That is enough — do not run the full checklist on a 10-line fix.
- **Full-cycle** — the full list: style, readability, correctness, edge cases, security, concurrency / locks / transactions, BSL-LS compliance.

If issues are found, apply the validator budget from `AGENTS.md → MCP Tool Calling → B.1`: a blocking defect requires a clean confirming run on the changed state; non-blocking style noise does not start another AI-review loop. If the limit is exhausted without a clean pass after a blocking fix, do not declare the gate passed; report the artifact as unverified.

Always consider whether an external transaction already exists (e.g. an object-write transaction) before opening a new one. See `platform-solutions.md` for the canonical templates.
