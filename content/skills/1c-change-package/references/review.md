# Review mode — the change as a diff

Read after choosing the review mode in [`../SKILL.md`](../SKILL.md); the common procedure, the evidence vocabulary and the boundaries live there.

## What the review must contain

- **BSL as a unified diff with context.** For each logical change: a few verbatim unchanged lines around it, removed lines with `-`, added lines with `+`, then the observable change in behaviour, the risk and the behaviour on failure. Several places → several diffs; a partial diff is labelled partial. The diff is for reading, not for copying — the copyable form is the manual mode.
- **Metadata and form properties as a table, never as a BSL diff:** «Сейчас / Предлагается» per owner and property — attribute type and qualifiers, form element kind, parent, data path, handlers, `Default*Form`, and so on. A current value you did not read is `unverified`, and the row then cannot claim «добавить» or «изменить».
- **Current and proposed behaviour are separate statements.** Claims about error branches follow the real call order in the source.

## Template

````markdown
# Ревью изменения

## Контекст

- Задача: …
- Конфигурация / расширение: …
- Объект / модуль / процедура: …
- Источник текущего кода: … (файл / инструмент MCP), отпечаток: …
- Платформа: …
- Статус: только ревью, изменения не внесены

## Кратко

Что меняется и что намеренно не входит.

## Изменение 1 — <кратко>

```diff
 неизменённая строка контекста
-удаляемая строка
+добавляемая строка
 неизменённая строка контекста
```

**Почему:** …
**Поведение при ошибке:** …

## Метаданные и форма

| Владелец и свойство | Сейчас | Предлагается | Причина |
|---|---|---|---|

## Нерешённые части

- … — `blocked — …` / `unverified`

## Проверки

| Проверка | Состояние | Чем подтверждено |
|---|---|---|
| Текущий код прочитан | `passed` | … |
| Актуальность исходника | `passed` / `blocked — …` / `unverified` | … |
| Типы и API | `passed` / `unverified` | … |
| Гейты на предлагаемом коде | `passed` / `not run — …` | … |
| Поведение (UI-подтверждение по `UI_TESTING`) | `not run — …` | до внесения не проверяется |

## Внесение

Изменение не внесено. Кто и как вносит (сам агент через `1c-metadata-manage` и правку модулей — если это разрешено; иначе — ручной пакет), какие гейты после внесения.
````

## A separate `.diff` file

Only on an explicit request **and** only when the current code was read from a local file: build it with a diff tool (`git diff --no-index` or `diff -u`), with `---` / `+++` headers and numeric hunk ranges (`@@ -12,4 +12,5 @@`), and check that it parses with `git apply --check --numstat` — that proves the patch format, not that the change works in 1C. A procedure body read through MCP has no file line numbers, so an MCP-sourced review stays in Markdown. Keep real tabs, line breaks and quotes; never write `\t`, `\n` or `\"` literally.

## Self-check before delivery

- Every change has an exact address and verbatim context lines from the re-read source.
- Metadata and form changes are in the table, with unread current values marked `unverified`.
- New API calls and variable types are proven or marked `unverified`.
- No check is reported that did not run; behaviour is `unverified` until UI confirmation or the owner's review after the change is applied.
