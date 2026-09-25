# Manual mode — package for applying the change in the Configurator

Read after choosing the manual mode in [`../SKILL.md`](../SKILL.md); the common procedure, the evidence vocabulary and the boundaries live there.

## What the package must contain

A self-contained instruction a person follows in the Configurator without the chat history. No diff markers inside copyable blocks.

- **Every change of existing BSL is a pair:** «Найти» — the current block verbatim, as re-read in step 6; «Заменить целиком на» — the complete new block, compilable as it stands. No `+` / `-` prefixes, no `...`, no «остальной код без изменений», no placeholders.
- **An insertion** names a verbatim anchor, «до» or «после» it, and the expected number of matches. Count the matches in the re-read source; if you could not count them, write `unverified` and tell the person to stop when the count differs — never «заменить все вхождения».
- **A new procedure or function** is shown whole, with its directive, region and documentation comment, and the place it goes (region, after which procedure).
- **A change that cannot be written correctly** is `blocked — <what is missing>`; the rest of the package still ships. Never close the package with a summary in place of blocks.
- **Line numbers are orientation only.** The identity of a place is its full address plus the verbatim block or anchor.

## Metadata and forms

- **Attributes / metadata:** one table row per new or changed attribute, tabular section, dimension or resource — owner, action, name, synonym, type with qualifiers (length, digits / fraction, composite types, date parts), fill checking, default / fill value, purpose and where it is used. A current value you did not read is `unverified` together with the Configurator place where the person checks it.
- **Form elements:** name, kind, parent group, data path (`Объект.<Имя>` / `Запись.<Имя>` — never a same-named form attribute, `content/rules/form-module.md → Form Data`), title, position among siblings, event handlers. Handlers go in the module part of the package with their directives.
- **Order matters:** metadata first, then form attributes and elements, then modules — a step never uses something a later step creates.
- An ordinary (binary) form is described the same way; say explicitly that it is edited in the form editor, not as `Form.xml`.

## Template

````markdown
# Инструкция ручного внесения

## Контекст

- Задача: …
- Конфигурация / расширение: …
- Платформа: …
- Почему вручную: … (объект на замке / обычная форма / объект захвачен в хранилище пользователем … / доступ только через MCP / запрос пользователя)
- Источник текущего кода: … (файл / инструмент MCP), отпечаток: …, прочитано: …
- Статус: пакет, изменения не внесены

## Что должно получиться

Наблюдаемое поведение после внесения и что намеренно не входит.

## Порядок внесения

1. Метаданные — …
2. Форма — …
3. Модули — …
4. Проверки — раздел «Проверка после внесения».

## Изменение 1 — <кратко>

**Где:** <Вид>.<Имя> → <модуль / форма> → <процедура>.
**Действие:** заменить блок целиком.
**Ожидаемых совпадений:** 1 (или `unverified` — при другом числе остановиться).

### Найти

```bsl
<текущий блок дословно>
```

### Заменить целиком на

```bsl
<полный новый блок>
```

**Почему:** …
**Зависимости и риски:** …

## Реквизиты и метаданные

| Владелец | Действие | Имя | Синоним | Тип и квалификаторы | Проверка заполнения | Назначение |
|---|---|---|---|---|---|---|

## Элементы формы

| Действие | Имя | Вид | Родитель | Путь к данным | Заголовок | События |
|---|---|---|---|---|---|---|

## Нерешённые части

- … — `blocked — …` / `unverified`

## Проверки пакета

| Проверка | Состояние | Чем подтверждено |
|---|---|---|
| Текущий код прочитан | `passed` | файл / инструмент, отпечаток |
| Актуальность исходника перед выдачей | `passed` / `blocked — …` / `unverified` | повторное чтение, отпечаток |
| Типы и API | `passed` / `unverified` | docinfo / bsl_scope_members … |
| Синтаксис новых блоков (Gate 1) | `passed` / `not run — …` | syntaxcheck … |
| Логика и стиль (Gates 2–3) | `passed` / `not run — …` | … |

## Проверка после внесения

1. Конфигуратор: синтаксический контроль изменённых модулей и проверка конфигурации (`/CheckModules`, `/CheckConfig` — `designer-batch-checks.md`) — без ошибок.
2. Выгрузка обновлённых исходников → гейты на внесённом коде: `syntaxcheck_file` → `check_1c_code` → `review_1c_code`, для метаданных и форм — `verify_xml` и валидаторы `1c-metadata-manage`.
3. Поведение: UI-подтверждение по `UI_TESTING` (`1c-tester`, `/deploy-and-test`) — сценарий: …; ожидаемое состояние: … Если подтверждение не выполнялось — «не проверено».

## Откат

Какие блоки вернуть (исходные блоки — в разделах «Найти»), какие реквизиты и элементы удалить, в каком порядке. Резервную копию упоминать, только если пользователь её сделал.
````

Keep only the sections the change needs: no metadata table when no metadata changes, no form table when the form does not change structurally.

## Self-check before delivery

- Every «Найти» block occurs verbatim in the re-read source, with the stated match count or `unverified`.
- Every «Заменить целиком на» block is complete, has no diff markers or placeholders, and passed Gate 1 as text (or says `not run — <reason>`).
- Every type behind a `Переменная.Метод()` call is proven or the call is `unverified`.
- The order never uses an entity before a step creates it.
- Every attribute and element is either read from the source or created by the package.
- The post-apply section names gates and UI confirmation, not tests, and marks what nobody confirmed as «не проверено».
- Rollback returns every changed block and removes every added entity.
