---
description: 1C:EDT branch of the ruleset — EDT project format, metadata / infobase gates, EDT-MCP routing, validation and DB update in an EDT workspace. Load when USE_EDT=true, the sources are in EDT format, or EDT-MCP tools are exposed.
alwaysApply: false
category: tooling
---

# 1C:EDT workflow

This file is the **EDT branch** of the ruleset. Everything else in `content/rules/` is written for the Designer-oriented default; this file states exactly what changes when the project is developed in **1C:EDT**, and nothing more.

## Activation — the master switch

`.dev.env` `USE_EDT` is the project's explicit statement about EDT (canon — `content/rules/dev-standards-env.md → USE_EDT — project uses 1C:EDT`):

- **`USE_EDT=true`** → this file applies. Load it before the first metadata mutation, infobase operation, or source-format-sensitive action in the session.
- **`USE_EDT=false` or missing** → this file does **not** apply. Do not propose EDT, do not offer EDT-MCP, do not reshape a task around EDT. An EDT installation found on the workstation, or an `edt-mcp` entry left in some client config, is **not** a project preference — only `USE_EDT` is.
- **User says the project moved to EDT** (or explicitly asks for EDT work) → ask once, set `USE_EDT=true` without touching other keys, then continue under this file.

`USE_EDT=true` without EDT-MCP is valid. Generic work continues; dependent steps use the alternatives below or remain unverified. Recommend `/install-edt-mcp` at most once per session when relevant and policy permits; never recommend it for `TOOL_EDT=off`.

Apply `TOOL_EDT` (`content/rules/mcp-policy.md → Tool availability`): `off` suppresses calls and installation recommendations; `required` blocks an EDT-MCP-dependent step if its capability is missing. Neither activates `USE_EDT`. Tools must be callable in this session; config/health alone is insufficient. Catalog: `content/skills/mcp-1c-tools/docs/edt-mcp.md`.

## The one thing that really changes: source format

EDT and Designer store the same configuration in **two different on-disk formats**. Establish which one the working tree holds **before** any metadata action — do not infer it from `USE_EDT` alone (a team can develop in EDT and still keep a Designer XML dump in git).

| Marker in the working tree | Format | Consequence |
|---|---|---|
| `Configuration.xml` at the root, `<Type>/<Name>.xml`, modules under `<Name>/Ext/…`, forms as `Forms/<Name>/Ext/Form.xml` | **Designer XML dump** | The whole ruleset applies **unchanged**. EDT is merely the human's editor; `1c-metadata-manage` remains the mutation gate. |
| `.project` + `DT-INF/` + `src/Configuration.mdo`, objects as `src/<Type>/<Name>/<Name>.mdo`, forms as `…/Forms/<Name>/Form.form`, modules as sibling `*.bsl` | **EDT format (MDO)** | The XML toolchain of `1c-metadata-manage` does **not** address these files. Route metadata mutations per *Mutating metadata in an EDT-format tree* below. |
| Both present in one repo (XML dump plus a separate EDT workspace) | **Hybrid** | Name the authoritative one before editing, edit only there, and regenerate the other side through the documented conversion. Editing both by hand guarantees a silent divergence. |

Hard rules for the EDT format:

- **Never hand-edit `*.mdo`, `*.form`, or anything under `DT-INF/`.** They are a generated projection of EDT's model; a hand edit is the same class of defect as hand-editing metadata XML (`AGENTS.md → Skills and Subagents`), with none of the recovery tooling.
- **Never point the `1c-metadata-manage` XML tools at `src/`.** They expect Designer XML; feeding MDO to them produces a broken tree, not an error message you can trust.
- BSL modules are ordinary `.bsl` files in **both** formats. Reading and editing BSL is unchanged — subject to *Model vs disk* below.

## Mutating metadata in an EDT-format tree

In order of preference:

1. **EDT-MCP, when exposed** — `create_metadata`, `modify_metadata`, `delete_metadata`, `rename_metadata_object`, `adopt_metadata_object` (borrowing a base object into an extension), `write_module_source` for module code. EDT owns the model, so EDT performs the change. This is the EDT-format equivalent of the `1c-metadata-manage` hard gate, and it carries the same reporting duty.
2. **The EDT UI, by the user** — when EDT-MCP is absent, hand the user a precise, ordered instruction (object, properties, exact names) instead of editing files. Slower for the user, but it is the only correct path left inside EDT format.
3. **Export → XML toolchain → import** — only when the change genuinely requires the XML tools and the user accepts the round trip. `export_configuration_to_xml` produces a Designer dump; work on it with `1c-metadata-manage`; bring it back with the platform / EDT import path. **Confirm first:** `import_configuration_from_xml` creates a **new** EDT project rather than updating the current one, so an unconfirmed round trip can strand the workspace. Never start this silently to route around option 1 or 2.

The **vendor-support** rules (`content/skills/1c-metadata-manage/docs/support-manage.md`) and the **extension-first** answer for typical configurations are unchanged in EDT — only the mechanism differs (`adopt_metadata_object` instead of `cfe-borrow`).

## Model vs disk — the synchronization rule

EDT's authority is its **in-memory model**, not the files in `src/`. `resync_to_disk` flushes model → disk and reports desync; there is no symmetrical "disk wins" operation you may assume.

- **While an EDT workspace is open on this project, EDT-MCP writes are the default** for anything EDT owns (metadata, module source). A file written behind EDT's back is at best invisible to EDT until it refreshes, at worst overwritten by the model.
- **Before** reading `src/` with native tools, indexing or validating it — use `resync_to_disk` when eligible. With EDT-MCP absent/disabled in `auto`/`off`, obtain the user's save/synchronization in EDT and confirmation of the current disk state; until then dependent reads/checks remain unverified. `required` cannot be satisfied by this substitute. Never invent a disk-to-model sync or trust stale files.
- **After** an external change to the tree (git checkout, a script, a slash command), EDT-MCP results are stale until the workspace is refreshed; re-establish state before trusting `get_project_errors` or a module read.
- **One owner per artifact per session.** Do not alternate between EDT-MCP writes and direct file writes on the same module — pick the path, state it in the report.

## Search and navigation

`content/rules/mcp-first-search.md` is unchanged: the 1C project-index servers (`1c-graph-metadata-mcp`, `1c-code-metadata-mcp`) stay the first pick for code / metadata / usage / impact search, and native discovery tools stay the justified last resort.

EDT-MCP is the better source when the question is about the **live workspace** rather than the indexed snapshot:

| Need | Prefer |
|---|---|
| Semantic / cross-configuration search, impact analysis, call chains, business search | 1C bundle (`search_code`, `trace_impact`, `trace_call_chain`, `find_usages_of_object`) |
| Current errors and validation state of the project | EDT-MCP (`get_project_errors`, `get_problem_summary`, `get_markers`) |
| Exact references to a metadata object as EDT resolves them right now | EDT-MCP (`find_references`) |
| Definition / symbol / completion at a caret in an open module | EDT-MCP (`go_to_definition`, `get_symbol_info`, `get_content_assist`) |
| The index is stale against fresh EDT-side edits, or the bundle is not exposed | EDT-MCP (`read_module_source`, `read_method_source`, `search_in_code`) |

`search_in_code` is literal / regex and **not** ru/en dialect aware — a query written in one BSL language variant will miss the other. Use it as a last-resort textual sweep, not as a replacement for the indexed search.

## Validation

BSL validation is **format-agnostic**: Gates 1–3 (`syntaxcheck` → `check_1c_code` → `review_1c_code`) run unchanged on every touched `.bsl`, in EDT projects too (`content/rules/verification-gates.md`).

What changes:

- **Gate 5 (`verify_xml`) does not apply to MDO.** Use EDT's validation: `revalidate_objects` → `get_project_errors` / `get_problem_summary`. In `auto`/`off` without MCP, request the corresponding validation in EDT by the user, bound to the current saved state; until results arrive it is unverified. `required` remains blocked without its tool evidence. Report the actual source of validation.
- **`apply_quick_fix`** applies EDT's official auto-fix to **one** marker. Apply deliberately, one at a time, and re-validate — it is a code change like any other, not a formatting nicety. `get_check_description` explains what a check code actually means before you "fix" it.
- **Budget discipline is unchanged** (`AGENTS.md → MCP Tool Calling → B.1`): re-validating unchanged state is forbidden, and EDT markers do not open a new retry loop of their own.
- `validate_query` (EDT-MCP) checks query text against the **project's metadata** — syntax and semantic errors with line numbers, without touching an infobase. It satisfies Gate 3a's query branch when `1c-data-mcp` is not exposed, and complements it when it is: EDT resolves tables and fields, `1c-data-mcp` answers what the live base returns. State which one produced the evidence.

## DB update, launches, external objects

- **`update_database`** applies configuration changes to an infobase from EDT (full or incremental, targeted by launch configuration or project + application). It is a **destructive** operation in EDT-MCP's own classification and requires consent.
- The infobase hard gate (`AGENTS.md → Skills and Subagents`) is unchanged in intent: **one owner per deployment**. Either the EDT path (`update_database`, launch configurations, `create_infobase` / `set_infobase_credentials`) or the platform path (`/update1cbase`, `/deploy-and-test`, `db-ops`) — never both against the same infobase in one flow, and never an ad-hoc `1cv8.exe` line. State which path ran in the mandatory `IB tooling:` line.
- The slash commands remain valid for an EDT project **when the tree they load from is a Designer XML dump** (repo-stored dump, or a fresh `export_configuration_to_xml`). They cannot load `src/` MDO directly.
- **External processors / reports** in an EDT external-object project are built with `build_external_objects` (compiles to `.epf` / `.erf`), not with the `1c-epf-build` tools of `1c-metadata-manage`.

## Forms

- **`get_form_layout_snapshot`** returns the calculated layout as text — the default choice for "what does this form look like / did my change land". It is far cheaper than an image and diffable between states.
- **`get_form_screenshot`** / `get_template_screenshot` need EDT started with `-DnativeFormBufferedLayoutRender=true` (`/install-edt-mcp`, step 3). Use them for genuine visual questions only.
- Layout knowledge itself is format-independent — `standards(name="form-patterns")` applies unchanged.

## Git and the configuration repository

- EDT-MCP exposes `git` plus `list_git_branches` / `create_git_branch` / `switch_git_branch` / `set_branch_infobase`. Prefer them over a raw terminal `git` **inside an EDT workspace**: EDT tracks the branch↔infobase binding, and a branch switch behind its back leaves the workspace pointing at the wrong base.
- Branch switching in EDT rebuilds the model — treat the workspace as stale afterwards (see *Model vs disk*).
- **Do not confuse git with the 1C configuration repository (хранилище).** When `.dev.env` `REPOSITORY_PATH` is set, lock-before-edit / commit-after-verify still belongs to the `1c-repository-manage` skill; EDT's git tools have nothing to do with it and must not be used as a substitute.

## Safety

- EDT-MCP includes filesystem, code-writing, database-update and debug operations, and treats every connected client as fully trusted. Keep it bound to loopback; a non-loopback bind requires an auth token and a trusted network (`/install-edt-mcp`, step 3).
- Operations EDT-MCP classifies as **destructive** — `delete_metadata`, `rename_metadata_object`, `delete_project`, `delete_infobase`, `update_database`, and `modify_metadata` when it changes a data type — prompt for consent by default. That prompt is a feature: it is the user's decision point, not an obstacle. **Never** disable it on the user's behalf (the `EDT_MCP_DESTRUCTIVE_CONSENT=allow` override, or the "Allow all" consent level) — propose it only if the user asks for unattended automation, and say what it removes.
- Debug and profiling tools (`debug_launch`, `set_breakpoint`, `start_profiling`, …) act on a running application. Confirm the target is a dev / test base first, exactly as the deployment commands require.

## Reporting

A task that used EDT-MCP names it in the final answer in one line: `EDT tooling: <tools used>` (e.g. `EDT tooling: modify_metadata, revalidate_objects, update_database`). This sits alongside — not instead of — the existing `Metadata tooling:` and `IB tooling:` lines; when EDT performed the metadata mutation or the DB update, those lines name the EDT path.

## Success criteria

- ✅ `USE_EDT` checked before any EDT-specific decision; nothing EDT-related proposed when it is `false`.
- ✅ Source format established from the tree (XML dump / MDO / hybrid) before the first metadata action.
- ✅ No hand edits of `*.mdo` / `*.form` / `DT-INF/`, and no XML tools pointed at `src/`.
- ✅ Metadata mutations in an MDO tree went through EDT-MCP, the EDT UI, or a confirmed export/import round trip.
- ✅ Model↔disk state reconciled before cross-tool reads or validation.
- ✅ BSL gates run unchanged; EDT validation recorded where `verify_xml` does not apply.
- ✅ One deployment owner named in the `IB tooling:` line; destructive-consent prompts left intact.
