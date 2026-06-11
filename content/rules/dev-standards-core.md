---
description: Development standards — project parameters, code style, modification comments, naming, documentation headers
alwaysApply: false
category: development
---

# Development Standards — Core

## 1. Project Parameters (.dev.env)

`.dev.env` is the **single source of truth** for project parameters across the whole rules set. There is no `infobasesettings.md`, no separate per-command settings file — all rules, on-demand instructions, slash commands and subagents read from `.dev.env`.

Read `.dev.env` **only when the current task actually depends on a parameter** (prefix / naming, modification comments, platform-version choices, metadata placement, infobase commands, deploy, UI tests). Guessing values is PROHIBITED.

### Global principle — no field is globally mandatory

No field in `.dev.env` blocks the entire ruleset. **Every parameter is task-scoped**: missing values matter only when a **specific** scheduled operation cannot proceed without them. Three classes:

- **Advisory** — empty is silently valid; a documented fallback applies. **MUST NOT be asked about**, ever (not at install time per task, not on apply phase, not in subagents).
- **Highly desirable for a specific operation** — empty does not block unrelated work, but the operation that needs the value cannot complete. Ask the user **only when that operation is in scope of the current task**. Do not gather empties up front "for completeness".
- **Defaulted** — empty resolves to a documented default; no question, no fallback noise.

### Code-generation parameters

| Parameter | Effect | Class | Behavior when empty |
|---|---|---|---|
| `{PREFIX}` | Prefix for ALL new metadata objects, attributes, form elements, roles | Advisory | No prefix on new objects; `{PREFIX}` in templates → empty string |
| `{COMPANY}` | Used in modification comment templates | Advisory | No modification markers emitted |
| `{DEVELOPER}` | Used in modification comment templates | Advisory | No modification markers emitted |
| `{PLATFORM_VERSION}` | Determines available platform features (e.g. `Асинх` / `Ждать` from 8.3.18 vs `ОписаниеОповещения` callbacks for older versions). See `dev-standards-architecture.md §3 → "Async and Modality"` | Highly desirable when generating platform-version-sensitive code | Ask only when the current task actually depends on version-specific behavior; otherwise proceed |
| `{COMMENT_OPEN}` / `{COMMENT_CLOSE}` | Modification comment templates with `{COMPANY}`, `{DEVELOPER}`, `{DATE}`, `{TASK}` placeholders | Highly desirable when markers are emitted | If `COMPANY` / `DEVELOPER` are also empty — markers are not emitted anyway; otherwise ask once |
| `{NEW_OBJECTS_IN}` | Where to place new objects: `main_configuration` or `extension` | Defaulted | Defaults to `main_configuration` |

### Advisory parameters — `PREFIX`, `COMPANY`, `DEVELOPER`

Both these parameters and the practices they govern — adding a project prefix to new objects (`PREFIX`) and stamping modification comments with company / developer attribution (`COMPANY`, `DEVELOPER`) — are **recommendations**, not hard requirements. They reflect a project convention; their absence is not a defect, code without a prefix or without modification banners is fully valid. When any of the three is empty in `.dev.env`, do **not** ask the user — apply the fallback below silently and proceed.

- **`PREFIX` is empty** — create new metadata objects, attributes, tabular sections, form elements, roles and subsystems **without a prefix**. Inside templates and examples, the placeholder `{PREFIX}` resolves to an empty string (`{PREFIX}ContractAmount` → `ContractAmount`, `{PREFIX}EventSubscriptions` → `EventSubscriptions`, `{PREFIX}AddedObjects` → `AddedObjects`). All other naming rules in §4 still apply (synonyms, role naming inside subsystems, etc.). Naming collisions with typical metadata become the user's responsibility — flag any collision you notice, but do not invent a prefix to avoid it.
- **`COMPANY` or `DEVELOPER` is empty** — do **not** emit modification markers (`COMMENT_OPEN` / `COMMENT_CLOSE`) in any module, even when modifying typical (standard) code. Removed typical code is still commented out, not deleted, and new procedures in typical modules are still placed at the end of the relevant region — but without the surrounding `// +++ … / // --- …` banners. The single header block for entirely new (non-typical) modules described in §3 is also skipped when either parameter is empty.
- **Both fallbacks are independent** — an empty `PREFIX` does not suppress markers, and empty `COMPANY` / `DEVELOPER` does not enable a prefix.
- **`{TASK}` is irrelevant when markers are not emitted** — do not ask for it.

### Infobase / deployment parameters

Used by `/loadfrom1cbase`, `/update1cbase`, `/getconfigfiles`, `/deploy-and-test` and the `1c-tester` subagent. **Not consulted at all for pure code, review, analysis, or documentation tasks** — pure code work proceeds even when this entire block is empty.

| Parameter | Effect | Class | Behavior when empty |
|---|---|---|---|
| `{PLATFORM_PATH}` | 1C platform install dir (must contain `bin\1cv8.exe`); used as the executable for all Designer-mode commands | Highly desirable for any IB-bound command | Ask when an IB-bound command is scheduled; the command cannot run without it |
| `{INFOBASE_KIND}` | `file` → `/F`, `server` → `/S` flag for Designer | Defaulted | Defaults to `file` (per `.dev.env.example`) |
| `{INFOBASE_PATH}` | Path to file infobase or connection string of server infobase | **Highly desirable** — критично для обновления / выгрузки конфигурации | Ask only when `/loadfrom1cbase`, `/update1cbase`, `/getconfigfiles`, `/deploy-and-test` is invoked; otherwise stay silent |
| `{IB_USER}` / `{IB_PASSWORD}` | Optional credentials (`/N`, `/P`); empty values omit the flags | Defaulted | Empty = no credentials, the `/N` / `/P` (or `--user` / `--password`) flags are omitted. **Never ask up front.** Re-ask only if the command itself fails with an authentication error from the platform. An empty password is a fully valid configuration for dev / test infobases. |
| `{EXTENSION_NAME}` | Optional `-Extension` argument | Defaulted | Empty = operations apply to main configuration |
| `{EXPORT_PATH}` | Source-export directory | Defaulted | Empty = current repository root |
| `{LOG_PATH}` | Designer log file (must be writable) | Defaulted | Empty = `$env:TEMP\1cv8.log` (Windows) / `$TMPDIR/1cv8.log` (POSIX). The directory always exists; any writable path works equally well — **never ask up front**. Re-ask only if the resolved path turns out to be non-writable at runtime. |
| `{INFOBASE_PUBLISH_URL}` | Web-publish URL of the test infobase for `1c-tester` UI tests | **Highly desirable** — критично для UI-тестирования | Empty = UI tests are silently skipped, the rest of `/deploy-and-test` still runs; only ask if the user explicitly requested UI tests |
| `{IBCMD_CONFIG}` | Path to standalone-server `config.yml` for `ibcmd`-based ops | Defaulted | Empty = fallback to Designer (per `.dev.env.example`) |

### Subagent model parameters

Consumed by the **installer** when rendering subagent files (source agents declare an abstract `modelTier: coding | light` instead of a concrete model — see `content/rules/subagents.md → Model-tier routing`). Not consulted at task time.

| Parameter | Effect | Class | Behavior when empty |
|---|---|---|---|
| `{SUBAGENT_MODEL_CODING}` | Concrete model for tier `coding` (coding / architecture / planning / analysis / review subagents) | Defaulted | Empty = the model field is omitted from installed agent files; the AI client uses its default model. **Never ask at task time**; re-render via `install.ps1 update` after editing. |
| `{SUBAGENT_MODEL_LIGHT}` | Concrete model for tier `light` (small bounded tasks: quick error fixes, scouting, mechanical checks) | Defaulted | Same as above |

Task number `{TASK}` is **only required when modification comment markers are produced** — i.e. when the change touches **typical (standard) configuration code** and the templates `{COMMENT_OPEN}` / `{COMMENT_CLOSE}` reference `{TASK}`. For new objects with `{PREFIX}` (no per-method markers), review / analysis / documentation tasks, and any task where `COMPANY` / `DEVELOPER` are empty (markers skipped) — `{TASK}` is **not required**. Do not block on it.

When `{TASK}` is required and not provided — ask the user once and reuse the same value across the whole change.

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

## 3. Modification Comments

Modification markers are used **only when modifying typical (standard) code** in typical configuration modules **and only when both `COMPANY` and `DEVELOPER` are set in `.dev.env`**. If either parameter is empty — skip markers entirely (see §1 → "Advisory parameters"); removed typical code is still commented out instead of deleted, but without the `// +++ … / // --- …` banners.

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

**When `PREFIX` is empty in `.dev.env`** — the placeholder `{PREFIX}` resolves to an empty string in every rule above (e.g. `{PREFIX}ContractAmount` → `ContractAmount`, `{PREFIX}AddedObjects` → `AddedObjects`). The `({COMPANY})` synonym disambiguator also disappears if `COMPANY` is empty. See §1 → "Advisory parameters".

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

Goal: cut LLM noise and keep only useful comments. See also `content/rules/coding-standards.md § Comments` for the headline rule (anchor from `AGENTS.md → Coding Standards`).

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

After any code change, perform a brief internal review covering: style, readability, correctness, edge cases, security, concurrency / locks / transactions, BSL-LS compliance. If issues are found — fix them and re-run the cycle, staying within the verification budget from `AGENTS.md → MCP Tool Calling → B.1` (one call per validator by default, up to 3 only on substantive defects). After the budget is exhausted — fix the substantive issues and report any remaining style noise instead of looping further.

Always consider whether an external transaction already exists (e.g. an object-write transaction) before opening a new one. See `platform-solutions.md` for the canonical templates.
