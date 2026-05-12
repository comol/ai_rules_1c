---
name: 1c-metadata-manage
description: "1C metadata management — create, edit, validate, and remove configuration objects (catalogs, documents, registers, enums), managed forms, data composition schemas (SKD), spreadsheet layouts (MXL), roles, external processors (EPF/ERF), extensions (CFE), configurations (CF), databases, subsystems, command interfaces, templates. Use when working with 1C metadata structure."
---

# 1C Metadata Manage — Skill Dispatch

Use this skill when the task involves **1C metadata structure** (creating, editing, validating, or removing configuration objects, forms, reports, layouts, roles, extensions, or databases).

> **Recommendation.** For any change to metadata XML — prefer this skill (or the `metadata-manager` subagent) over hand-editing `Configuration.xml`, `Form.xml`, `Role.xml` and similar files. The PowerShell tools under `tools/` handle BOM, encodings, UUID regeneration, ChildObjects ordering and cross-references that are easy to break manually. Direct XML edits are acceptable only for unambiguous one-line fixes (e.g. correcting a synonym typo).

## Dispatch Strategy

Determine task complexity, then choose the execution mode:

### Direct execution — simple / read-only tasks

Use when the task is a **single lightweight query**: checking metadata info, a quick lookup, one validation call. In this case identify the task domain from the table below, read the corresponding file, and follow its instructions directly.

### Subagent delegation — complex / mutation tasks

Delegate to the **`/metadata-manager`** subagent (defined in `@agents/metadata-manager.md`) when **any** of the following is true:

- The task **creates, scaffolds, or compiles** metadata (objects, forms, SKD, MXL, roles, EPF, CF, CFE, databases)
- The task **edits multiple files** or **spans multiple domains**
- The task involves a **multi-step workflow** (create → edit → validate → fix → re-validate)
- The task requires **reading large domain docs** (forms, meta-manage, SKD, MXL, roles, EPF, DB — each 200–800 lines)

The subagent already knows how to read the skill docs, execute PowerShell scripts, and validate results. Provide it with the full task description including object names, attributes, types, and any business context from the conversation.

## Task Domain Table

| Task Domain | Keywords | File |
|---|---|---|
| Metadata objects — create, edit, analyze, remove, validate | catalog, document, register, enum, constant, module, attribute, tabular section | [meta-manage.md](docs/meta-manage.md) |
| Managed forms — design, create, edit, analyze, validate | form, Form.xml, UI, elements, commands, events | [form-manage.md](docs/form-manage.md) |
| Data Composition Schema (DCS/SKD) — create, edit, analyze, validate | report, DCS, SKD, data composition, data set, query | [skd-manage.md](docs/skd-manage.md) |
| Spreadsheet documents (MXL) — create, decompile, analyze, validate | MXL, spreadsheet, template, print form, layout | [mxl-manage.md](docs/mxl-manage.md) |
| Roles and access rights — create, analyze, validate | role, rights, RLS, access, permissions | [role-manage.md](docs/role-manage.md) |
| External processors/reports (EPF/ERF) — scaffold, build, dump, validate | EPF, ERF, data processor, external report, build, dump | [epf-manage.md](docs/epf-manage.md) |
| BSP/SSL registration and commands | BSP, SSL, ExternalDataProcessorInfo, registration, command | [bsp-manage.md](docs/bsp-manage.md) |
| Configuration (CF) — create, edit, analyze, validate | configuration, Configuration.xml, CF | [cf-manage.md](docs/cf-manage.md) |
| Extensions (CFE) — create, borrow, diff, patch, validate | extension, CFE, borrow, interceptor, patch | [cfe-manage.md](docs/cfe-manage.md) |
| Databases — registry, create, run, load, dump | database, infobase, .v8-project.json, create DB, run 1C | [db-manage.md](docs/db-manage.md) |
| Subsystems — create, edit, analyze, validate | subsystem, command interface, ChildObjects | [subsystem-manage.md](docs/subsystem-manage.md) |
| Command interface — edit, validate | CommandInterface.xml, commands visibility, groups | [interface-manage.md](docs/interface-manage.md) |
| Templates/layouts management — add, remove | template, layout, SpreadsheetDocument, HTML template | [template-manage.md](docs/template-manage.md) |
| Help pages — add, manage | help, built-in help, documentation | [help-manage.md](docs/help-manage.md) |
| SSL/BSP subsystems patterns | SSL patterns, standard subsystems, BSP events | [ssl-patterns.md](docs/ssl-patterns.md) |
| Query writing — compose new queries from scratch | write query, build query, query template, ВЫБРАТЬ, ИЗ, СОЕДИНЕНИЕ, virtual tables, batch queries | [query-writing.md](docs/query-writing.md) |
| Query optimization | query, temporary table, join, DCS optimization | [query-optimization.md](docs/query-optimization.md) |
| Web publishing — publish, unpublish, status, smoke test | web, publish, Apache, IIS, web client, webdav, default.vrd | [web-manage.md](docs/web-manage.md) |
| Unpack / rebuild CF, CFE, EPF binaries without 1C platform | v8unpack, binary unpack, headless extract, no platform | [v8unpack-cf.md](docs/v8unpack-cf.md) |

**If the task spans multiple domains**, the subagent will read all relevant docs automatically (or read each one directly for simple tasks).
