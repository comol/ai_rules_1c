---
name: 1c-metadata-manage
description: "Create, edit, validate and remove 1C metadata — catalogs, documents, registers, enums, managed forms, SKD, MXL, roles, EPF/ERF, CFE, CF, databases, subsystems, command interfaces, templates. Use for any change to 1C metadata structure."
---

# 1C Metadata Manage — Skill Dispatch

Use this skill when the task involves **1C metadata structure** (creating, editing, validating, or removing configuration objects, forms, reports, layouts, roles, extensions, or databases).

## Hard rule

The gate itself — every metadata-XML mutation and every infobase operation goes through this skill (dispatch below → domain doc → PowerShell tools) or the `1c-metadata-manager` subagent, hand-editing is a defect, repository-bound projects add the `1c-repository-manage` lock / commit discipline, EDT-format trees (`.mdo` / `.form`, never fed to these tools) route per `content/rules/edt-workflow.md` — is owned by `AGENTS.md → Skills and Subagents`; this skill's own canon is only the exceptions:

- **Unambiguous one-line fix** of an existing value that cannot break structure — a synonym / comment typo, a boolean flag flip on an existing element. Anything that adds / removes / reorders elements, touches UUIDs, or spans more than one line of XML is not "one-line".
- **Existing role** — not a hand-edit case: `role-edit` changes its rights, RLS, templates and flags in place and keeps the UUID ([role-manage.md](docs/role-manage.md)); `role-compile` is only for a new role. A locked role of a configuration on vendor support is not hand-edited either — [support-manage.md](docs/support-manage.md).
- **Skill not available in the session** (files not installed / not exposed) — state it once in one line, then hand-edit with `metadata-xml-workarounds.md` loaded and validate per `verification-gates.md → Gate 5`.
- **Read-only analysis** of metadata XML is not a mutation — reading files directly is fine (subject to `mcp-first-search.md` for locating them).

## Vendor support gate

Every mutating tool refuses to edit a locked ("на замке") object of a typical configuration on vendor support and refuses to delete one still on support — the run exits `1`, the refusal is the correct outcome (extension first, `support-edit` only as a stated decision): [support-manage.md](docs/support-manage.md).

## Path conventions

PowerShell examples in this skill (`SKILL.md` and every `docs/*.md`) use the prefix `skills/1c-metadata-manage/tools/...`. That prefix is **relative to the active tool's skills directory**, not to the repository root:

- After installation: the script lives under `<tool>/skills/1c-metadata-manage/tools/...` (e.g. `.cursor/skills/1c-metadata-manage/tools/...`, `.claude/skills/1c-metadata-manage/tools/...`, `.kilo/skills/1c-metadata-manage/tools/...`, `.ai-agent/skills/1c-metadata-manage/tools/...`). Active tools that load this skill resolve the prefix automatically.
- In the `1c-rules` source repository (when editing the skill itself): the same script lives under `content/skills/1c-metadata-manage/tools/...`. Prepend `content/` when running the example outside of an installed project.

The same convention applies to `docs/*.md` references like `skills/1c-metadata-manage/tools/1c-skd-info/modes-reference.md`.

## Runtime selection — Windows / Linux / macOS

XML saving in `form-edit`, `form-add`, `remove-form`, `form-compile` registration, `meta-edit`, `cf-edit`, `cfe-borrow` registration/merge, `skd-edit`, `subsystem-edit`, `subsystem-compile` registration, `interface-edit`, `role-edit`, `add-template` and `add-help` retains the input CRLF/LF style and uses Configurator's compact empty tags (`<Tag/>`). Formatting-only changes should not be repaired by a global replacement that can alter literal XML in comments or CDATA.

On Windows use the shipped `.ps1` entry points. Before selecting a Linux/macOS runtime, using a Python port, or resolving a missing runtime, read [runtime-selection.md](docs/runtime-selection.md) for the exact supported commands and limitations. A missing runtime never permits hand-editing metadata XML.

## Logical addressing and optional preview

`tools/_common/Invoke-1CEdit.ps1` accepts logical addresses, emits a unified diff and can preview its own script writes. Before using the wrapper, read [edit-preview.md](docs/edit-preview.md) for arguments, rollback boundaries and `METADATA_PREVIEW` modes.

Default `auto`: preview DSL generation or a tool/operation new to this project; ordinary edits apply immediately. Native deletion gates (`-DryRun`, then `-Force`) and validation always remain. Direct tool invocation is valid; name a preview on `Metadata tooling:` only when it ran. Do not stash or commit another person's changes to force a preview.

## Dispatch Strategy

Determine task complexity, then choose the execution mode:

### Direct execution — simple / read-only tasks

Use when the task is a **single lightweight query**: checking metadata info, a quick lookup, one validation call. In this case identify the task domain from the table below, read the corresponding file, and follow its instructions directly.

### Subagent delegation — complex / mutation tasks

Delegate to the **`1c-metadata-manager`** subagent (defined in `content/agents/metadata-manager.md`, or in the installed agents directory for the active tool) when **any** of the following is true:

- The task **creates, scaffolds, or compiles** metadata (objects, forms, SKD, MXL, roles, EPF, CF, CFE, databases)
- The task **edits multiple files** or **spans multiple domains**
- The task involves a **multi-step workflow** (create → edit → validate → fix → re-validate)
- The task requires **reading large domain docs** (forms, meta-manage, SKD, MXL, roles, EPF, DB — each 200–800 lines)

The subagent already knows how to read the skill docs, execute PowerShell scripts, and validate results. Provide it with the full task description including object names, attributes, types, and any business context from the conversation.

## Task Domain Table

| Task domain | Read before the operation |
|---|---|
| Metadata objects — create, edit, analyze, remove, validate | [meta-manage.md](docs/meta-manage.md) |
| UUID integrity — duplicate identities in an XML dump | [uuid-check.md](docs/uuid-check.md) |
| Managed forms — design, create, edit, analyze, validate | [form-manage.md](docs/form-manage.md) |
| Managed-form layout patterns — archetypes, naming conventions, advanced patterns | fetch `standards(name="form-patterns")` on `1C-docs-mcp` (server not exposed → `content/rules/help-corpus-retrieval.md`) |
| Form-compile DSL reference — full JSON DSL spec for `1c-form-compile`, `--from-object` mode, presets | [form-compile-dsl.md](docs/form-compile-dsl.md) |
| Data Composition Schema (DCS/SKD) — create, edit, analyze, decompile, validate | [skd-manage.md](docs/skd-manage.md) |
| Spreadsheet documents (MXL) — create, decompile, analyze, validate | [mxl-manage.md](docs/mxl-manage.md) |
| Roles and access rights — create, edit, analyze, validate | [role-manage.md](docs/role-manage.md) |
| External processors/reports (EPF/ERF) — scaffold, build, dump, validate | [epf-manage.md](docs/epf-manage.md) |
| BSP/SSL registration and commands | [bsp-manage.md](docs/bsp-manage.md) |
| Configuration (CF) and complete dump integrity (CF/CFE) — create, edit, analyze, validate | [cf-manage.md](docs/cf-manage.md) |
| Extensions (CFE) — create, borrow, diff, patch, validate | [cfe-manage.md](docs/cfe-manage.md) |
| Vendor support state — "на замке", editability, off-support | [support-manage.md](docs/support-manage.md) |
| XDTO packages — analyze, create from XSD, export, edit, validate | [xdto-manage.md](docs/xdto-manage.md) |
| Databases — create, run, load, dump, DT backup, extensions in the infobase (list, check, properties, delete) | [db-manage.md](docs/db-manage.md) |
| Subsystems — create, edit, analyze, validate | [subsystem-manage.md](docs/subsystem-manage.md) |
| Command interface — edit, validate | [interface-manage.md](docs/interface-manage.md) |
| Templates/layouts management — add, remove | [template-manage.md](docs/template-manage.md) |
| Help pages — add, manage | [help-manage.md](docs/help-manage.md) |
| SSL/BSP subsystems patterns | `standards(name="dev-standards-architecture") §4` + `content/skills/mcp-1c-tools/docs/1c-ssl-mcp.md` |
| Query writing — compose new queries from scratch | [query-writing.md](docs/query-writing.md) |
| Query optimization | [query-optimization.md](docs/query-optimization.md) |
| Web publishing — publish, unpublish, status, smoke test | [web-manage.md](docs/web-manage.md) |
| Unpack / rebuild CF, CFE, EPF binaries without 1C platform | [v8unpack-cf.md](docs/v8unpack-cf.md) → standalone skill `v8unpack-cf` |

**If the task spans multiple domains**, the subagent will read all relevant docs automatically (or read each one directly for simple tasks).
