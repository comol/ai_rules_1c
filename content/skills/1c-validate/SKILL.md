---
name: 1c-validate
description: "Validate changed 1C artifacts — BSL modules by path through BSL Language Server, logic and performance through 1С:Напарник check, style and ITS compliance through review, metadata XML against its XSD — with the retry budget of the verification policy. Use after every BSL or metadata edit; the gates and budgets are owned by verification-gates.md / verification-policy.md."
argument-hint: "<module path | xml> [lines]"
allowed-tools: mcp__1c-syntax-checker-mcp__syntaxcheck_file, mcp__1c-syntax-checker-mcp__syntaxcheck, mcp__1c-code-check-mcp__check_1c_code, mcp__1c-code-check-mcp__review_1c_code, mcp__1c-code-metadata-mcp__verify_xml
---

# 1c-validate — the validator chain

Order for touched BSL: `syntaxcheck_file` → `check_1c_code` → `review_1c_code`, at the depth of `VERIFICATION_DEPTH` and within the budget of `content/rules/verification-policy.md → Validator budget` (one clean pass on the latest state; after a blocking fix one confirmation at `standard`, up to two at `full`; never a run on unchanged content). Pure metadata XML without BSL: `verify_xml` once. Which gates a change needs — `content/rules/verification-gates.md`.

## Tools and exact arguments

| Gate | Call | Arguments |
|---|---|---|
| 1 Syntax — saved file (default) | `syntaxcheck_file` | `file_path` relative to the mounted sources root, optional `lines="5, 10-20"` — save first; a failed path is retried once, then fall back to text |
| 1 Syntax — text (fallback) | `syntaxcheck` | `code` — only when the file tool is not exposed or the fragment has no file yet; confirm by path once written |
| 2 Logic & performance | `check_1c_code` | exactly one of `code` or `files` (list of saved paths under the declared workspace roots) |
| 3 Style & ITS | `review_1c_code` | same shape as `check_1c_code` |
| 5 Metadata XML | `verify_xml` | `xml_content`, `object_type` (`Справочник`, `Документ`, `Форма`, `Роль`, `СКД`, `Макет`) |

`syntaxcheck` and `syntaxcheck_file` are one validator for budgeting. Never feed syntax-broken code to the AI validators.

## Calls

```json
{"tool": "syntaxcheck_file", "args": {"file_path": "Documents/РеализацияТоваровУслуг/Ext/ObjectModule.bsl", "lines": "120-185"}}
{"tool": "check_1c_code", "args": {"files": ["Documents/РеализацияТоваровУслуг/Ext/ObjectModule.bsl"]}}
{"tool": "review_1c_code", "args": {"files": ["Documents/РеализацияТоваровУслуг/Ext/ObjectModule.bsl"]}}
{"tool": "verify_xml", "args": {"object_type": "Справочник", "xml_content": "<MetaDataObject …>"}}
```

## Reading the answers

- Blocking: any `error` from syntax; `critical` / `error` from check; `error` from review; a logic, data-integrity, security, transaction or performance defect named by the validator. Style noise never starts another AI pass.
- `provenance.index` on a syntax answer says what a clean report proves: `absent` / `building` / `failed` = syntax and local rules only; `ready` = cross-module resolution included. Read it, never wait for it.
- A check of a large module may run for minutes; the server retries transport failures itself — do not resend.
- Rewrites from `rewrite_1c_code` / `modify_1c_code` are drafts and re-enter this chain.
- A missing validator is graceful degradation with a `Risk:` line, never a silent skip. Typed answers map to actions by code — `content/rules/mcp-policy.md → C. Server answers → actions`.

Details: `content/skills/mcp-1c-tools/docs/1c-syntax-checker-mcp.md`, `content/skills/mcp-1c-tools/docs/1c-code-check-mcp.md`, `content/skills/mcp-1c-tools/docs/1c-code-metadata-mcp.md → XSD schemas & validation`.
