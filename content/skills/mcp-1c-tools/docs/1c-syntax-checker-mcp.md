# 1c-syntax-checker-mcp — tool catalog

BSL syntax and style validation via BSL Language Server.

> Load this file only if the `1c-syntax-checker-mcp` server is actually available in the current session.

| Tool | Purpose | When to use |
|---|---|---|
| **syntaxcheck** | Check a BSL code snippet passed as text | After writing code — verify no errors, when `syntaxcheck_file` is not exposed or the code is not yet saved to a file. **One clean pass on the latest state is required; after fixing an error, use the confirmation budget below** |
| **syntaxcheck_file** *(conditional)* | Check a BSL file on disk by path, optionally restricted to specific lines | **Preferred over `syntaxcheck` when exposed** — checking by path is cheaper (no need to read the module and paste its text) and validates the file exactly as saved. Same call budget as `syntaxcheck` |

## Choosing the tool

- `syntaxcheck_file` is registered on the server **only** when a sources directory is mounted (`FILES_DIR`). Treat it as available only if it is actually exposed in the current session's tool schema; otherwise use `syntaxcheck` with code text.
- When `syntaxcheck_file` is exposed, prefer it for any module that exists on disk: pass the path instead of pasting the module body — this is more economical and avoids copy-paste drift between the prompt and the file.
- `syntaxcheck` and `syntaxcheck_file` are the **same validator** for budgeting purposes: the per-cycle limit below applies to their combined calls, not to each tool separately.

## Input format

### `syntaxcheck`

- `syntaxcheck` принимает **только текст BSL-кода** в параметре запроса. Передача путей к файлам (`.bsl`, `.os` и т.п.) или ссылок на модули в репозитории не поддерживается — такой ввод будет интерпретирован как код и приведёт к ложным синтаксическим ошибкам.
- Перед вызовом прочитайте нужный модуль (или его фрагмент) через `Read` и передайте полученный текст как код. Для крупных модулей допустимо проверять отдельный изменённый фрагмент, обрамлённый минимально необходимым контекстом (объявление процедуры/функции целиком).

### `syntaxcheck_file`

- `file_path` — path to the BSL file **relative to the mounted sources directory** (usually the project root mounted into the server's container), not an absolute workspace path. If the call fails with "file not found", do not retry with path variations more than once — fall back to `syntaxcheck` with the code text.
- `lines` — optional 1-based line selection, e.g. `"5, 10-20, 35"`; empty string checks the whole file. For a small edit inside a large module, pass the edited range (the whole procedure/function) to keep the report focused; line-filtering affects only the report, the file is still parsed in full, so surrounding-context errors are not masked within the selected lines.
- Save the file before calling — the tool checks the on-disk state, not the editor buffer.

## Notes on the limit

- A **cycle** is one logical edit of one module, from the first edit until either a clean `syntaxcheck` / `syntaxcheck_file` run is achieved or the limit is exhausted.
- **Default budget** — one clean call on the latest saved state.
- A syntax `error` is blocking. After editing the module to fix it, a clean confirming run is mandatory: `full` allows 3 calls total; `standard` allows the initial call plus one confirmation (2 total). Promotion-trigger changes always use the `full` budget.
- Syntax / style warnings alone do not justify another run. If the warning is fixed by editing BSL, the saved state changed and still needs final clean syntax evidence under the applicable budget.
- The same policy applies to `check_1c_code` and `review_1c_code` from `1c-code-check-mcp`.
- If the limit is exhausted without a clean pass on the latest state, the syntax gate failed: report the module as unverified and do not declare the change done. Style warnings alone remain non-blocking.
- It only makes sense to re-run `syntaxcheck` / `syntaxcheck_file` after an actual code edit — re-runs without changes are forbidden (see `AGENTS.md → MCP Tool Calling`).
