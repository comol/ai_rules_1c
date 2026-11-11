---
description: Project parameters from .dev.env — classes and ask-policy, code generation, infobase / deployment keys, INFOBASE_ROLE, repository binding, UI_TESTING, USE_EDT. Process and model keys — dev-standards-env-process.md
alwaysApply: false
category: development
---

# Development Standards — Environment Parameters

**When to load this file:** when the task depends on project parameters, infobase / deployment, EDT (`USE_EDT`) or UI testing. Read only the relevant section; no code-style-only lookup. `TOOL_*` keys — `content/rules/tool-policy.md`. Subagent / model routing, orchestration, triage and debugging defaults, verification depth, metadata preview, communication style and the support channel — `content/rules/dev-standards-env-process.md`.

Section number 1 is a stable anchor for `§1` references.

## 1. Project Parameters (.dev.env)

`.dev.env` is the **single source of truth** for project parameters across the whole rules set. There is no `infobasesettings.md`, no separate per-command settings file — all rules, on-demand instructions, slash commands and subagents read from `.dev.env`.

An optional source-contour catalog (`content/rules/multi-contour-search.md`) owns only source identities, search roles and index mappings. It neither duplicates operation defaults nor restricts source analysis to `EXTENSION_NAME`. It does not override `EXTENSION_NAMES` load order or the dump/load path conventions below; resolve the target through the operation's dedicated procedure.

For a shared main-configuration/extension project, load `content/rules/extension-workspace.md`. Keep one settings file: an explicitly selected operation target overrides the single-target default for that pass without rewriting `EXTENSION_NAME`, `EXTENSION_NAMES` or the configured roots. The recommended new-project `src/cf`, `src/cfe/<Name>` layout is an explicit setup choice; existing paths and the defaults below remain supported.

Read `.dev.env` **only when the current task actually depends on a parameter** (prefix / naming, modification comments, platform-version choices, metadata placement, infobase commands, deploy, UI tests). Guessing values is PROHIBITED. **Read the key lines, not the commentary:** `Grep` `^[A-Z]` over `.dev.env` returns every `KEY=value` line; the comments in the file repeat these rules and cost many times more than the values.

### Global principle — no field is globally mandatory

No field in `.dev.env` blocks the entire ruleset. **Every parameter is task-scoped**: missing values matter only when a **specific** scheduled operation cannot proceed without them. Four classes:

- **Advisory** — empty is silently valid; a documented fallback applies. **MUST NOT be asked about**, ever (not at install time per task, not on apply phase, not in subagents).
- **Highly desirable for a specific operation** — empty does not block unrelated work, but the operation that needs the value cannot complete. Ask the user **only when that operation is in scope of the current task**. Do not gather empties up front "for completeness".
- **Defaulted** — empty resolves to a documented default; no question, no fallback noise.
- **Install-time selection** — the installer asks once while creating `.dev.env`, persists the answer, and regular tasks never re-ask it.

### Code-generation parameters

| Parameter | Effect | Class | Behavior when empty |
|---|---|---|---|
| `{PREFIX}` | Prefix for ALL new metadata objects, attributes, form elements, roles | Advisory | No prefix on new objects; `{PREFIX}` in templates → empty string |
| `{COMPANY}` | Used in modification comment templates | Advisory | No modification markers emitted |
| `{DEVELOPER}` | Used in modification comment templates | Advisory | No modification markers emitted |
| `{PLATFORM_VERSION}` | Determines available platform features (e.g. `Асинх` / `Ждать` from 8.3.18 vs `ОписаниеОповещения` callbacks for older versions). See `standards(name="dev-standards-architecture") §3 → "Async and Modality"` | Highly desirable when generating platform-version-sensitive code | Ask only when the current task actually depends on version-specific behavior; otherwise proceed |
| `{COMMENT_OPEN}` / `{COMMENT_CLOSE}` | Modification comment templates with `{COMPANY}`, `{DEVELOPER}`, `{DATE}`, `{TASK}` placeholders | Highly desirable when markers are emitted | If `COMPANY` / `DEVELOPER` are also empty — markers are not emitted anyway; otherwise ask once |
| `{NEW_OBJECTS_IN}` | Where to place new objects: `main_configuration` or `extension` | Defaulted | Defaults to `main_configuration` |

### Advisory parameters — `PREFIX`, `COMPANY`, `DEVELOPER`

Both these parameters and the practices they govern — adding a project prefix to new objects (`PREFIX`) and stamping modification comments with company / developer attribution (`COMPANY`, `DEVELOPER`) — are **recommendations**, not hard requirements. They reflect a project convention; their absence is not a defect, code without a prefix or without modification banners is fully valid. When any of the three is empty in `.dev.env`, do **not** ask the user — apply the fallback below silently and proceed.

- **`PREFIX` is empty** — create new metadata objects, attributes, tabular sections, form elements, roles and subsystems **without a prefix**. Inside templates and examples, the placeholder `{PREFIX}` resolves to an empty string (`{PREFIX}ContractAmount` → `ContractAmount`, `{PREFIX}EventSubscriptions` → `EventSubscriptions`, `{PREFIX}AddedObjects` → `AddedObjects`). All other naming rules in `dev-standards-change-markers.md §4` still apply (synonyms, role naming inside subsystems, etc.). Naming collisions with typical metadata become the user's responsibility — flag any collision you notice, but do not invent a prefix to avoid it.
- **`COMPANY` or `DEVELOPER` is empty** — do **not** emit modification markers (`COMMENT_OPEN` / `COMMENT_CLOSE`) in any module, even when modifying typical (standard) code. Removed typical code is still commented out, not deleted, and new procedures in typical modules are still placed at the end of the relevant region — but without the surrounding `// +++ … / // --- …` banners. The single header block for entirely new (non-typical) modules described in `dev-standards-change-markers.md §3` is also skipped when either parameter is empty.
- **Both fallbacks are independent** — an empty `PREFIX` does not suppress markers, and empty `COMPANY` / `DEVELOPER` does not enable a prefix.
- **`{TASK}` is irrelevant when markers are not emitted** — do not ask for it.

Task number `{TASK}` is **only required when modification comment markers are produced** — i.e. when the change touches **typical (standard) configuration code** and the templates `{COMMENT_OPEN}` / `{COMMENT_CLOSE}` reference `{TASK}`. For new objects with `{PREFIX}` (no per-method markers), review / analysis / documentation tasks, and any task where `COMPANY` / `DEVELOPER` are empty (markers skipped) — `{TASK}` is **not required**. Do not block on it. When `{TASK}` is required and not provided — ask the user once and reuse the same value across the whole change.

### Infobase / deployment parameters

Used by `/loadfrom1cbase`, `/update1cbase`, `/getconfigfiles`, `/deploy-and-test`, the full-cycle commands (`/initproject`, `/restore-testbase`, `/test-fix-loop`, `/build-release`) and the `1c-tester` subagent. **Not consulted at all for pure code, review, analysis, or documentation tasks** — pure code work proceeds even when this entire block is empty.

| Parameter | Effect | Class | Behavior when empty |
|---|---|---|---|
| `{PLATFORM_PATH}` | 1C platform install dir (must contain `bin\1cv8.exe`); used as the executable for all Designer-mode commands | Highly desirable for any IB-bound command | Ask when an IB-bound command is scheduled; the command cannot run without it |
| `{INFOBASE_KIND}` | `file` → `/F`, `server` → `/S` flag for Designer | Defaulted | Defaults to `file` (per `.dev.env.example`) |
| `{INFOBASE_PATH}` | Path to file infobase or connection string of server infobase | **Highly desirable** for configuration load / dump operations | Ask only when `/loadfrom1cbase`, `/update1cbase`, `/getconfigfiles`, `/deploy-and-test` is invoked; otherwise stay silent |
| `{INFOBASE_ROLE}` | Role of the project infobase: `dev` \| `test` \| `prod`. The role covers the base at `INFOBASE_PATH` and its web publication `INFOBASE_PUBLISH_URL`, which `1c-data-mcp` and UI tests use. It is the explicit answer every "identified dev/test infobase" gate asks for | Highly desirable for operations that change the infobase | Empty = role unknown: each dev/test gate asks the user once before its first mutating step — a configuration load included. **Never set, lower or clear it yourself**; see the note below |
| `{IB_USER}` / `{IB_PASSWORD}` | Optional credentials (`/N`, `/P`); empty values omit the flags | Defaulted | Empty = no credentials, the `/N` / `/P` (or `--user` / `--password`) flags are omitted. **Never ask up front.** Re-ask only if the command itself fails with an authentication error from the platform. An empty password is a fully valid configuration for dev / test infobases. |
| `{EXTENSION_NAME}` | Default/primary extension for a single-target operation; the resolved pass supplies `-Extension` | Defaulted | Empty = main configuration unless the task explicitly selects another target; never overwrite this setting just to switch a pass |
| `{EXTENSION_NAMES}` | Comma-separated extension list defining the **full snapshot** (cf + cfe), order = load order, not runtime application order; consumed by full-snapshot commands | Defaulted | Ordinary single-target calls use `EXTENSION_NAME`. Explicit `all` / full-snapshot work resolves inventory via `extension-workspace.md`; confirmed no extensions means main only, never a silent single-extension fallback. **Never ask up front**; resolve missing inventory only when the full snapshot is requested |
| `{EXPORT_PATH}` | Main source-export directory in a shared project; established legacy single-extension source root remains valid | Defaulted | Empty = current repository root; commands resolve the chosen target's actual root before substituting templates |
| `{EXTENSIONS_PATH}` | Root directory of extension sources — each extension from `EXTENSION_NAMES` lives in `{EXTENSIONS_PATH}\<Name>\` | Defaulted | Empty = the `cfe` directory at the repository root |
| `{DT_SNAPSHOT_PATH}` | `.dt` snapshot (data + configuration) used by `/restore-testbase` as the data baseline | Defaulted | Empty = `/restore-testbase` skips the data step and refreshes configuration only |
| `{RELEASE_PATH}` | Output directory for `/build-release` artifacts (`.cf` / `.cfe` / `.cfu`) | Defaulted | Empty = the `release` directory at the repository root |
| `{LOG_PATH}` | Designer log file (must be writable) | Defaulted | Empty = `$env:TEMP\1cv8.log` (Windows) / `$TMPDIR/1cv8.log` (POSIX). The directory always exists; any writable path works equally well — **never ask up front**. Re-ask only if the resolved path turns out to be non-writable at runtime. |
| `{RESULT_PATH}` | `/DumpResult` file of every Designer batch launch — the numeric verdict (`0` = success) read next to the exit code and the `/Out` log (`designer-batch-checks.md → The verdict is three signals`) | Defaulted | Empty = `$env:TEMP\1cv8.result` (Windows) / `$TMPDIR/1cv8.result` (POSIX). Deleted before each launch; a missing file after a launch is a failed launch — **never ask** |
| `{INFOBASE_PUBLISH_URL}` | Web-publish URL of the test infobase for web-client UI tests | **Highly desirable** for web UI testing | Empty = the web route is skipped; ask only for a requested UI test that has no other route |
| `{UI_TESTING}` | UI-testing mode: `essential` \| `auto` \| `manual` \| `off` | Defaulted | Empty = `essential`; invalid = `manual` (see below) |
| `{MCP_QA_CLIENT_VISIBLE}` | Window of a 1C test client the agent starts for QA MCP checks | Defaulted | Empty / missing / invalid = visible; `false`, `0`, `no`, `off` = hidden desktop |
| `{IBCMD_CONFIG}` | Path to standalone-server `config.yml` for `ibcmd`-based ops | Defaulted | Empty = fallback to Designer (per `.dev.env.example`) |
| `{PLATFORM_ARGS}` / `{IBCMD_ARGS}` | Extra launch arguments (comma-separated) appended to every `1cv8.exe` / `ibcmd` run by the `1c-metadata-manage` `db-*` / `epf-*` tools | Defaulted | Empty = no extra arguments. **Never ask.** Arguments the tool owns itself (`/F`, `/S`, `/N`, `/P`, `/UpdateDBCfg`, `--db-path`, …) are rejected by the scripts — pass those as regular parameters |
| `{SUPPORT_GUARD}` | Reaction of the vendor-support guard (`1c-metadata-manage` tools, the hook below) to an object "на замке": `deny` \| `warn` \| `off` | Defaulted | Empty = `deny`. **Never ask**; see the note below |
| `{SUPPORT_GUARD_HOOK}` | `on` = that guard also on direct `Edit` / `Write` of dump files (experimental Claude Code plugin hook) | Defaulted | Empty = off. **Never ask or set it yourself** |
| `{NEW_OBJECT_POSITION}` | Where the creating tools of `1c-metadata-manage` put a new object inside `<ChildObjects>` of `Configuration.xml`: `end` \| `byName` | Defaulted | Empty = `end` — appended after the last object of the same kind, as Configurator does. **Never ask**; the scripts read the key, canon — `content/skills/1c-metadata-manage/docs/meta-manage.md` |
| `{V8_XSD_PATH}` | Platform XSD dir for `skd-validate` (`content/skills/1c-metadata-manage/docs/skd-manage.md`); never commit it | Defaulted | Empty = `.v8-xsd` |
| `{REPOSITORY_PATH}` | Configuration repository (хранилище) address — local path or `tcp://server/alias`. **Master switch of repository mode**: non-empty activates the `1c-repository-manage` skill and the lock-before-edit / commit-after-verify SDLC discipline | Defaulted (see the note below) | Empty = the configuration is not repository-bound; the skill and repository steps stay inactive. **Never ask up front**; ask once only when the user explicitly requests a repository operation and the value is missing |
| `{REPOSITORY_USER}` / `{REPOSITORY_PASSWORD}` | Repository credentials (`/ConfigurationRepositoryN` / `/ConfigurationRepositoryP`); empty values omit the flags | Defaulted | Empty = no repository authentication flags. **Never ask up front**; re-ask only after a repository authentication error |
| `{REPOSITORY_ALLOW_FORCE}` | First half of the double opt-in for `-force` repository operations in the `repo-ops` script (forced get/commit, forced unlock discarding uncommitted changes) | Defaulted | Empty = `false` — every `-Force` call is refused. **Never ask, never set it yourself**: the value is the user's decision for an approved maintenance window |

#### `INFOBASE_ROLE` — what the agent may do to the project infobase

The role is the project's statement about its infobase, not the agent's guess from a path, a name or a user list. Every command that says "the target must be an explicitly identified dev/test infobase" reads it first: `/update1cbase`, `/deploy-and-test`, `/restore-testbase`, `/initproject from-ib`, the Designer batch check ladder, Gates 3a and 6, and the live-IB write rules.

| Value | Meaning |
|---|---|
| `dev`, `test` | The base is identified as dev/test. The gates pass without the confirmation question, forced session termination included. |
| `prod` | The agent does **not** change this base. Refused: configuration and extension loads, DB configuration apply (`/UpdateDBCfg`, extension apply), `.dt` restore, `/RollbackCfg`, repository `lock -Revised` / `update` / `commit` through it, and writes through `1c-data-mcp`. Allowed: read-only work — dumps (`/loadfrom1cbase`, `/getconfigfiles`), repository `status` / `history` / `diff`, and live-IB queries on the user's explicit request (Gate 3a does not run). A change that must reach this base is handed to the user as exact commands with the production overrides of `/update1cbase` and the `/build-release` Step 7 checklist. |
| empty | Unknown. Each dev/test gate asks the user once before its first mutating step — the configuration load, not only the DB update; the answer holds for the current task only. |

- Only the user sets the value. Record `dev` / `test` / `prod` in `.dev.env` only when the user states the role explicitly. Never lower `prod`, never clear it, and never repoint `INFOBASE_PATH` / `INFOBASE_PUBLISH_URL` to get past a refusal. A refusal on `prod` is the correct outcome, not an obstacle.
- The role applies to the base these keys name. Work on a copy only when the user supplies the copy's connection; that copy is identified on its own terms.

#### `REPOSITORY_PATH` — configuration repository binding

A non-empty `REPOSITORY_PATH` is the project's explicit statement "we work with a 1C configuration repository". It changes the SDLC: objects must be locked in the repository before mutation and committed after verification, `/update1cbase` requires locks on the loaded objects, and every repository operation runs through the `1c-repository-manage` skill (`content/skills/1c-repository-manage/SKILL.md` — hard gate per `AGENTS.md → Skills and Subagents`). Process canon — the skill's `docs/repo-sdlc.md`. **While the parameter is set, disconnecting the configuration from the repository is forbidden** (`/ConfigurationRepositoryUnbindCfg` and any equivalent) — canon `SKILL.md → Safety invariants`. When the parameter is empty, none of this applies and the agent must not raise the topic.

#### `SUPPORT_GUARD` — editing a typical configuration on vendor support

Every mutating tool of the `1c-metadata-manage` skill checks whether the target belongs to a configuration on vendor support (`Ext/ParentConfigurations.bin` next to `Configuration.xml`) and is locked. Editing such an object silently breaks vendor updates, so the default is a hard refusal — **a refusal is the correct outcome, not an obstacle to route around by hand-editing XML**.

Answer a refusal with a change **in an extension** (`cfe-borrow` / `cfe-patch-method`); a deliberate support-state change is `support-edit`. Reaction modes (`deny` default, `warn`, `off`) and canon — `content/skills/1c-metadata-manage/docs/support-manage.md`.

> **`.dev.env` is the single source of truth for the skill's scripts too.** The vendored `1c-metadata-manage` tools (upstream `cc-1c-skills` reads `.v8-project.json`) are patched to read `.dev.env` **first** — `PLATFORM_PATH`, `PLATFORM_ARGS`, `IBCMD_ARGS`, `SUPPORT_GUARD`, `NEW_OBJECT_POSITION`, `REPOSITORY_*` (repository credentials of the `db-*` tools, password masked), `EXPORT_PATH` (common modules for the `epf-build` source check), `V8_XSD_PATH` (platform XSD for `skd-validate`) — so a project never maintains a second config file; `.v8-project.json` is only a fallback. Order and key map: `content/skills/1c-metadata-manage/docs/db-manage.md → Part 1`. The second local patch is the batch verdict: every Designer launch of the skill passes `/DumpResult` beside `/Out` and fails the run when the result is non-zero or the file was never written (`designer-batch-checks.md → The verdict is three signals`).

#### `UI_TESTING` — UI-testing mode

UI checks confirm behaviour in the 1C interface: through QA MCP (`1c-qa`) in the thin client when it is connected, or through the web client as the more token-expensive fallback. `UI_TESTING` decides **whether** and **how much** is checked. It is **Defaulted** — empty resolves to `essential`, an invalid value to `manual`; the agent **must not** ask for the value.

Explicit editor: `/uitests essential|on|manual|off|status` (`content/commands/uitests.md`); `on` / `auto` writes `auto`. Resolve a session-only override before the project value. All QA profiles and orchestration modes preserve UI policy. Changing policy alone does not run tests or authorize deployment; dev/test target and tool-policy gates still apply.

| Value | Meaning |
|---|---|
| `essential` (default / empty) | Once the change is on the dev/test infobase (load + DB update), check automatically **only the important new or changed user-visible behaviour**: the main scenario of each new or changed form, command, document, report or workflow, plus the case the task is about. No regression sweep, no cosmetic or refactoring-only checks; non-visual results go to Gate 3a / `1c-data-mcp`; the rest on request. |
| `auto` | Every applicable UI scenario runs automatically in the verification phase / after each successful deploy. |
| `manual` | UI tests run **only on an explicit user request**; the pipeline and the verification phase never trigger them. `/deploy-and-test` Steps 1–3 still run; Step 4 is skipped unless requested. |
| `off` | UI testing is disabled on every route. A run request alone does not enable it; point to `/uitests essential`, `/uitests on` or `/uitests manual`. An explicit enable-and-run instruction satisfies the switch without a second confirmation; execution gates still apply. |

Resolve `off` first: it blocks UI regardless of routes and starts no setup questionnaire. Loading the change for a check follows `INFOBASE_ROLE` and `/update1cbase` / `/deploy-and-test`. The route supplies **where**: QA MCP — the test client of `INFOBASE_PATH`; web — `INFOBASE_PUBLISH_URL`. An automatic run with no available route is skipped and affected criteria stay unverified with that reason; for an explicitly requested run, ask for the missing prerequisite and continue independent work.

**Route and tool** — `ui-testing-tools.md`: QA MCP → web client → `agent-desktop` for windows outside the client. `MCP_QA_CLIENT_VISIBLE` (`/uitests visible|hidden`) sets the test-client window, never `UI_TESTING` — `qa-testclient.md → Visible or hidden window`.

#### `USE_EDT` — project uses 1C:EDT

`USE_EDT=true|false` is an **Install-time selection** and the durable project-level signal for the EDT branch of the ruleset. The installer asks once, **only while creating** `.dev.env`, among the other setup questions. A project whose existing `.dev.env` predates the key gets `USE_EDT=false` appended **without a question** — on an update that would be the single interactive prompt of an otherwise unattended run — and `-NonInteractive` writes the same conservative default.

| Value | Meaning |
|---|---|
| `true` | The project is developed in 1C:EDT. `content/rules/edt-workflow.md` applies: source-format check before metadata actions, EDT-MCP routing, model↔disk synchronization, EDT validation, and the EDT deployment path. `/installtools` recommends EDT-MCP. |
| `false` | EDT is not part of the project workflow: EDT-MCP is not recommended or preselected, and EDT is never proposed as a way to do a task. Because the installer can write this value unasked, it is not proof of the source format — an EDT-format tree keeps the protection of `edt-workflow.md → The one thing that really changes: source format`. |

Missing, empty or invalid values are `unknown`, not proof that EDT is absent. Only `/installtools`, `/install-edt-mcp`, or an explicit user statement that the project moved to EDT may ask and persist the choice; ordinary development tasks must not interrupt work to ask. An EDT installation found on the workstation, or a leftover `edt-mcp` entry in a client config, is evidence about the machine — not about the project.

See `.dev.env.example` for the template.
