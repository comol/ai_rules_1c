# 1c-syntax-checker-mcp — tool catalog

BSL syntax and style validation via BSL Language Server.

> Load this file only if the `1c-syntax-checker-mcp` server is actually available in the current session.

| Tool | Purpose | When to use |
|---|---|---|
| **syntaxcheck_file** *(conditional)* | Check a BSL file on disk by path, optionally restricted to specific lines | **The default check for anything that exists on disk** — including a module you have just edited and saved. Costs a path (plus an optional line range) instead of the module body, validates the file exactly as saved, and is the only mode the full-configuration index can answer. Exposed only when a sources directory is mounted |
| **syntaxcheck** | Check a BSL code snippet passed as text | **Fallback** — `syntaxcheck_file` is not exposed, or the code has no file yet (just generated, not yet written to the module). **One clean pass on the latest state is required; after fixing an error, use the confirmation budget below** |
| **plugin_state** | Inspect loaded plugins, hooks, tables and errors | Diagnose plugin behavior without mutation |
| **plugin_reload** | Atomically reload plugins | Live mutation; call only on an explicit operator request |

## Choosing the tool

**The default is `syntaxcheck_file`.** If the module exists on disk, check it by path. Passing its text to `syntaxcheck` instead means reading the whole module into the prompt first and paying for the body twice — once to read it, once to send it — while the file call spends a path and, at most, a line range. On a large module that is the difference between tens of tokens and the entire module. It also validates exactly what is saved, with no copy-paste drift between the prompt and the file.

Use `syntaxcheck` (code as text) **only** when one of these holds:

- `syntaxcheck_file` is **not exposed** in the current session's tool schema. The server registers it only when a sources directory is mounted (`FILES_DIR`); treat it as available only when it is actually visible in the schema.
- The code **has no file yet** — a fragment just generated in the conversation and not yet written to a module. This is what the text tool is for. Once the fragment is written and saved, the confirming run is a `syntaxcheck_file` call: the gate is evidence about the on-disk state, which is what will be loaded into the infobase.
- The file lies **outside the mounted sources directory**, or a path call already failed once with "file not found" — fall back then, and do not keep trying path variations.

`syntaxcheck` and `syntaxcheck_file` are the **same validator** for budgeting purposes: the per-cycle limit below applies to their combined calls, not to each tool separately.

## Validation boundary

The published beta analyzer configuration disables `UnresolvedMethodCall`, `UnresolvedField`, and `QueryToMissingMetadata`. A standalone temporary module has no full-configuration symbol context, so those cross-module diagnostics produce false positives on normal 1C code. They are disabled in `bsl-analyzer.toml`, not filtered by the server, so `filters.suppression_applied` remains false. Treat a clean result as evidence for syntax and enabled local rules — **not** as proof that methods, fields, or query metadata resolve across the whole configuration. Use CodeMetadata/GraphMetadata navigation and a real configuration-level test for that claim.

**Read `provenance.index` before deciding what a clean report proves.** The published beta adds an optional full-index mode (`FULLINDEX=true` with a mounted `FILES_DIR`) in which those three checks are answered from an index of the whole configuration. The mode is an addition, not a requirement: a server without an index is the ordinary setup and works normally — every other diagnostic is produced exactly the same way, and only those three are missing. Every answer declares the state it was produced in:

| `provenance.index` | What a clean report proves |
|---|---|
| `absent` | Mode off — the ordinary state, not a defect. Syntax and enabled local rules only; the boundary above applies in full |
| `building` | Index not ready yet; the three checks are still off. Same boundary as `absent` — a state to read, never a state to wait for |
| `ready` | The three cross-module checks were answered from the index and are part of the evidence |
| `failed` | The index could not be built; same boundary as `absent` |

Never infer the mode from a container name, a compose file, or an earlier call — read the field in the answer you actually got. On stable `latest` the field is not published at all; a missing `provenance.index` means the mode does not exist in that build — read it as `absent`. Do not restart or reconfigure the container to obtain `ready`; that is an operator decision, and the mode is optional. Indexing a whole configuration runs for hours, and the container answers calls the entire time — so `building` never justifies holding a check, looping on retries or delaying delivery: run the check, read the state, and report the boundary it came with. A check answered from the index costs seconds where a check without one costs milliseconds, and the first call after `ready` is slower still — that is the mode working, not a hang, so do not treat a slow call as a failure and re-issue it.

**The index answers `syntaxcheck_file` only.** The three cross-module diagnostics are merged into the report of the file tool; a `syntaxcheck` (code-as-text) answer never carries them, even when its own `provenance.index` reads `ready` — the field reports the container's state, not what the call used. A text-mode clean report is therefore bounded by the paragraph above whatever the index says. That is the second reason the file tool is the default: it is the only mode in which the full check can happen at all.

**Platform names are checked in both tools, index or not.** The published beta reads the platform model from its own analyzer and reports names the platform does not have: `UnknownPlatformMethod` (a method of a local created by `Новый <Тип>` and assigned nothing else in that method), `UnknownPlatformProperty` (a property of such a local when the type has none — `Массив`, `Соответствие`), `UnknownSystemEnumValue`, `UnknownPlatformType` (`Новый <Имя>`) — all `Critical` — and, for `syntaxcheck` only, `PlatformApiUnavailableOnClient` (`Major`: a server-only type or global function in a `&НаКлиенте` method; the file tool gets the analyzer's own `UnavailableInEnvironment` from the form module's path instead). `provenance.platform_names` says whether the model was `ready` for the call; `loading` or `unavailable` means those names were not checked. The check is deliberately narrow: bare calls (`КонецТранзакции()`), members of typed values that were not created by `Новый` in the same method, properties of types that have any, and `Структура`/`COMОбъект` members are never reported — a clean report does not prove them.

## Output channel

Read the structured result (`diagnostics`, `diagnostic_asides`, `summary`, `filters`, `provenance`, `request_rewrite`) rather than reparsing text. Published beta `latest-beta` / `arm64-beta` changed the successful text half from JSONL to one TOON document under `events`; stable `latest` still uses JSONL. The event values/order and structured content did not change, but a JSONL parser is incompatible with beta text. Analyzer stdout remains internal JSONL before publication.

Beta answers are capped (`RESPONSE_MAX_CHARS`, 32768 bytes by default). `summary.truncated=true` with `returned < total` means the most severe findings were kept and the rest did not fit — not that the module is clean beyond them: re-check the lines you changed with `syntaxcheck_file` and `lines` before calling the module clean.

A diagnostic's row carries primitive values only. A non-primitive field — `tags` from the analyzer, or a plugin annotation — is carried beside the list in `diagnostic_asides`: one entry per value, naming its diagnostic by its 0-based index in `diagnostics`. The structured half always declares the key and carries an empty list when nothing was moved; the text half omits it when empty. Do not expect `tags` inside a diagnostic entry, and do not treat its absence there as the analyzer not having reported it.

`plugin_reload` changes live server behavior. Never call it as a validation retry or routine recovery step; use it only when the operator explicitly asks to reload plugins.

## Input format

### `syntaxcheck_file` (default)

- `file_path` — path to the BSL file **relative to the mounted sources directory** (usually the project root mounted into the server's container), not an absolute workspace path. If the call fails with "file not found", do not retry with path variations more than once — fall back to `syntaxcheck` with the code text.
- `lines` — optional 1-based line selection, e.g. `"5, 10-20, 35"`; empty string checks the whole file. For a small edit inside a large module, pass the edited range (the whole procedure/function) to keep the report focused; line-filtering affects only the report, the file is still parsed in full, so surrounding-context errors are not masked within the selected lines.
- Save the file before calling — the tool checks the on-disk state, not the editor buffer.

### `syntaxcheck` (fallback)

- `syntaxcheck` принимает **только текст BSL-кода** в параметре запроса. Передача путей к файлам (`.bsl`, `.os` и т.п.) или ссылок на модули в репозитории не поддерживается — такой ввод будет интерпретирован как код и приведёт к ложным синтаксическим ошибкам.
- Перед вызовом прочитайте нужный модуль (или его фрагмент) через `Read` и передайте полученный текст как код. Для крупных модулей допустимо проверять отдельный изменённый фрагмент, обрамлённый минимально необходимым контекстом (объявление процедуры/функции целиком).
- `file_name` — optional **bare** module name for the submitted text (`ObjectModule.bsl`, `ManagerModule.bsl`, `Module.bsl`). Pass it whenever the fragment's module kind is known: the analyzer then reads the code as that kind of module, and every location in the report names it instead of the server's temporary path. It is a name and never a location — a path separator, a parent segment, a drive letter or an extension the analyzer does not read is refused (`invalid_file_name`), not quietly repaired.

## Notes on the limit

Budget, blocking severities and the confirmation rule are owned by `content/rules/verification-policy.md → Validator budget`. Tool-specific: a warning fixed by editing BSL changes the saved state and needs fresh clean syntax evidence; a re-run without an actual code edit is forbidden.
