---
name: 1c-live-ib
description: "Answer questions only the running infobase can answer — does this query parse, what does it return on real data, does this BSL fragment run on this platform, what error did the event log record — through the 1c-data-mcp HTTP service published on the infobase. Read-only by default; every mutation needs explicit user consent."
argument-hint: "<query text | bsl fragment | lasterror>"
allowed-tools: mcp__1c-data-mcp__validatequery, mcp__1c-data-mcp__vcexecutequery, mcp__1c-data-mcp__vcexecutecode, mcp__1c-data-mcp__vcloggetlasterror
---

# 1c-live-ib — the running infobase

Escalate here only when the configuration dump, the static validators and the docs cannot answer: "does it run *now* in *this* IB". Never a replacement for `1c-validate`. Available only when the tools are exposed in the session; a configured URL proves nothing, and fake "execution output" is a defect.

## Tools and exact arguments

| Need | Call | Arguments | Pass criterion |
|---|---|---|---|
| Does the query parse | `validatequery` | `querytext` | `"нет ошибок"` — parse only, no metadata or RLS check |
| What does it return on real data | `vcexecutequery` | `querytext` with parameters embedded in the text | text table |
| Does the fragment run on this platform | `vcexecutecode` | `bslcode`; assign `Результат = …` to get a value back | `"ошибок нет"` or the error text |
| Last error in the event log | `vcloggetlasterror` | — (24 h window, level `Ошибка`, one record) | formatted record or `"ошибок не найдено"` |

## Calls

```json
{"tool": "validatequery", "args": {"querytext": "ВЫБРАТЬ Т.Ссылка ИЗ Справочник.Контрагенты КАК Т ГДЕ Т.ИНН = \"7701234567\""}}
{"tool": "vcexecutequery", "args": {"querytext": "ВЫБРАТЬ ПЕРВЫЕ 5 Т.Ссылка, Т.ИНН ИЗ Справочник.Контрагенты КАК Т"}}
{"tool": "vcexecutecode", "args": {"bslcode": "Результат = Строка(Метаданные.Справочники.Контрагенты.Реквизиты.ИНН.Тип.КвалификаторыСтроки.Длина);"}}
{"tool": "vcloggetlasterror", "args": {}}
```

## Safety

- Read-only first: `validatequery` → `vcexecutequery`; non-mutating fragments for `vcexecutecode`.
- No `Записать()`, `Удалить()`, `НачатьТранзакцию`, register movements without asking the user, naming the object and having a rollback plan; on a production IB refuse and request a copy.
- No secrets or personal data in `bslcode` / `querytext` — they travel over HTTP and may be logged.
- Validate AI-generated text first (`validatequery`, `syntaxcheck`), then run it here.
- Gate 3a (`content/rules/verification-gates.md`) uses only the read-only tools.

Where it sits in the playbooks: error fixing step 2 and 6, performance step 5, new-code step 5 — `content/rules/tooling-playbooks.md`. Setup and 401/403 troubleshooting — `content/commands/checkmcp.md`. Details: `content/skills/mcp-1c-tools/docs/1c-data-mcp.md`.
