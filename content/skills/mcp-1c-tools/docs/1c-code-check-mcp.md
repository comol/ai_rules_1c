# 1c-code-check-mcp — tool catalog

1С:Напарник: code review and technical code checking, AI rewrite / modify, platform documentation by version, ITS standards, configuration documentation.

> Load this file only if the `1c-code-check-mcp` server is actually available in the current session.

## Code analysis & modification

| Tool | Purpose | When to use |
|---|---|---|
| **check_1c_code** | `code` **or** `files`; technical check: syntax, logic, performance | After writing code — find bugs and performance issues |
| **review_1c_code** | `code` **or** `files`; code review: style, ITS standards, naming, structure | After writing code — verify standards compliance |
| **rewrite_1c_code** | `code` **or** `files`, optional `goal`; AI rewrite proposal | When code needs significant improvement. **Non-deterministic — mandatory re-validation** via `syntaxcheck` + `check_1c_code` + `review_1c_code` |
| **modify_1c_code** | required `instruction`, optional `code` **or** `files`; modify/generate proposal | Targeted fixes, specific bug fixes, feature additions. **Non-deterministic — mandatory re-validation** |
| **ask_1c_ai** | required `question`, `create_new_session=false`, optional `files` | Architectural questions, concept explanations, advice. **Non-deterministic — treat as a hint, not authority** |

## Passing code with `files`

- Prefer `files` for a saved large module. The server reads at most 20 regular files from declared `ONEC_AI_WORKSPACE_ROOTS`, enforces `ONEC_AI_WORKSPACE_MAX_FILE_BYTES`, resolves links before containment checks, and writes nothing.
- For code tools other than `ask_1c_ai`, pass exactly one of `code` or `files`, never both. `modify_1c_code` may omit both only when generating new code from `instruction`.
- Paths may be relative to a declared root or absolute inside the container. A Windows/UNC client path is accepted only through an operator-declared `ONEC_AI_WORKSPACE_PATH_MAP`; never guess a mapping or retry arbitrary path variants.
- A one-file call preserves the file text and returns `sources[].text_sha256`; rewrite/modify proposals carry the matching `original_hash`. Two or more files are concatenated with context headers and are not one directly applicable patch target.
- One invalid/out-of-root/oversized file refuses the entire call. Do not assume that the remaining files were sent upstream.

## Timeouts and transport retries

The image published since 2026-08-24 bounds a whole upstream operation by one budget (`ONEC_AI_OPERATION_TIMEOUT`, default 300 s) and retries a transport failure — network error, single-request timeout, HTTP 5xx/429 — up to `ONEC_AI_TRANSPORT_RETRIES` times (default 2) on a fresh discussion, inside that budget. `ONEC_AI_TIMEOUT` (30 s) no longer cuts the event stream, so a large module no longer fails with an empty `Ошибка сети при отправке сообщения:`.

- A check of a large module may legitimately run for minutes. Do not re-issue the same call because it is slow — the server is already retrying, and a manual retry spends the call budget above on nothing.
- When a call does fail, the diagnostic, the fallback reason and the telemetry state how many attempts were made and name the exception class. Report that instead of guessing, and treat a budget-exhausted failure as an operator/configuration matter, not something to work around by resending.

## Documentation & knowledge base

| Tool | Purpose | When to use |
|---|---|---|
| **search_1c_documentation** | Search platform documentation for a specific version (`v8.3.25`) | Verify method signatures in a specific version, version-specific platform features |
| **its_help** | Search the ITS knowledge base (standards, methodology) | Find ITS standards, best practices. **Returns document IDs → use `fetch_its`** |
| **fetch_its** | Read the full content of an ITS document by ID | **Always after `its_help`** — read every found article. Special IDs: `root`, `v8std` |
| **diff_1c_documentation_versions** | Compare documentation between platform versions | Changes between versions (`v8.3.25` → `v8.5.1`) |
| **config_help** | Search documentation for specific configurations (ERP, БП, ЗУП, УТ) | Configuration-specific business logic, object descriptions |

## Key ITS workflow

`its_help` → get document IDs → `fetch_its` for each ID → read the full content. **Never ignore ITS article references without `fetch_its`.**

## Notes on AI tools

`ask_1c_ai`, `rewrite_1c_code`, `modify_1c_code` are non-deterministic. Their output is a draft hint, not authority. Generated / rewritten code is **always** re-validated: `syntaxcheck` + `check_1c_code` + `review_1c_code`.

`rewrite_1c_code` and `modify_1c_code` return a **proposal**, never write the workspace. Apply it only when `safe_to_apply` is true, validation is acceptable, and the current source hash still equals `original_hash`; then run the validators against the actual saved result.

## Call limit

Budget, blocking severities (`critical` / `error` for `check_1c_code`, `error` for `review_1c_code`) and the confirmation rule are owned by `content/rules/verification-policy.md → Validator budget`. Tool-specific: never re-call against unchanged code; for pure metadata-XML changes with no BSL touched use `verify_xml` instead.
