---
description: Project and process parameters from .dev.env — code generation, infobase operations, EDT usage, UI testing, subagent models, the active-model profile, orchestration, and verification depth, and the support channel (SUPPORT_KEY / SUPPORT_EMAIL)
alwaysApply: false
category: development
---

# Development Standards — Environment and Process Parameters

**When to load this file:** when selecting tool policy (`TOOL_*`) or when the task depends on project parameters, infobase/deployment, EDT (`USE_EDT`), UI testing, subagent/model routing, triage/debugging, verification depth, metadata preview, communication style or support settings. Read only the relevant section; no code-style-only lookup.

Section number 1 is a stable anchor for `§1` references.

## 1. Project Parameters (.dev.env)

`.dev.env` is the **single source of truth** for project parameters across the whole rules set. There is no `infobasesettings.md`, no separate per-command settings file — all rules, on-demand instructions, slash commands and subagents read from `.dev.env`.

An optional source-contour catalog (`content/rules/multi-contour-search.md`) owns only source identities, search roles and index mappings. It neither duplicates operation defaults nor restricts source analysis to `EXTENSION_NAME`. It does not override `EXTENSION_NAMES` load order or the dump/load path conventions below; resolve the target through the operation's dedicated procedure.

For a shared main-configuration/extension project, load `content/rules/extension-workspace.md`. Keep one settings file: an explicitly selected operation target overrides the single-target default for that pass without rewriting `EXTENSION_NAME`, `EXTENSION_NAMES` or the configured roots. The recommended new-project `src/cf`, `src/cfe/<Name>` layout is an explicit setup choice; existing paths and the defaults below remain supported.

Read `.dev.env` **only when the current task actually depends on a parameter** (prefix / naming, modification comments, platform-version choices, metadata placement, infobase commands, deploy, UI tests). Guessing values is PROHIBITED.

### Global principle — no field is globally mandatory

No field in `.dev.env` blocks the entire ruleset. **Every parameter is task-scoped**: missing values matter only when a **specific** scheduled operation cannot proceed without them. Three classes:

- **Advisory** — empty is silently valid; a documented fallback applies. **MUST NOT be asked about**, ever (not at install time per task, not on apply phase, not in subagents).
- **Highly desirable for a specific operation** — empty does not block unrelated work, but the operation that needs the value cannot complete. Ask the user **only when that operation is in scope of the current task**. Do not gather empties up front "for completeness".
- **Defaulted** — empty resolves to a documented default; no question, no fallback noise.
- **Install-time selection** — the installer asks once while creating `.dev.env` (or once during migration of an older file), persists the answer, and regular tasks never re-ask it.

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
- **`COMPANY` or `DEVELOPER` is empty** — do **not** emit modification markers (`COMMENT_OPEN` / `COMMENT_CLOSE`) in any module, even when modifying typical (standard) code. Removed typical code is still commented out, not deleted, and new procedures in typical modules are still placed at the end of the relevant region — but without the surrounding `// +++ … / // --- …` banners. The single header block for entirely new (non-typical) modules described in §3 is also skipped when either parameter is empty.
- **Both fallbacks are independent** — an empty `PREFIX` does not suppress markers, and empty `COMPANY` / `DEVELOPER` does not enable a prefix.
- **`{TASK}` is irrelevant when markers are not emitted** — do not ask for it.

### Infobase / deployment parameters

Used by `/loadfrom1cbase`, `/update1cbase`, `/getconfigfiles`, `/deploy-and-test`, the full-cycle commands (`/initproject`, `/restore-testbase`, `/test-fix-loop`, `/build-release`) and the `1c-tester` subagent. **Not consulted at all for pure code, review, analysis, or documentation tasks** — pure code work proceeds even when this entire block is empty.

| Parameter | Effect | Class | Behavior when empty |
|---|---|---|---|
| `{PLATFORM_PATH}` | 1C platform install dir (must contain `bin\1cv8.exe`); used as the executable for all Designer-mode commands | Highly desirable for any IB-bound command | Ask when an IB-bound command is scheduled; the command cannot run without it |
| `{INFOBASE_KIND}` | `file` → `/F`, `server` → `/S` flag for Designer | Defaulted | Defaults to `file` (per `.dev.env.example`) |
| `{INFOBASE_PATH}` | Path to file infobase or connection string of server infobase | **Highly desirable** for configuration load / dump operations | Ask only when `/loadfrom1cbase`, `/update1cbase`, `/getconfigfiles`, `/deploy-and-test` is invoked; otherwise stay silent |
| `{INFOBASE_ROLE}` | Role of the project infobase: `dev` \| `test` \| `prod`. The role covers the base at `INFOBASE_PATH` and its web publication `INFOBASE_PUBLISH_URL`, which `1c-data-mcp` and UI tests use. It is the explicit answer every "identified dev/test infobase" gate asks for | Defaulted | Empty = role unknown: each dev/test gate asks the user once before its first mutating step, as it always has. **Never set, lower or clear it yourself**; see the note below |
| `{IB_USER}` / `{IB_PASSWORD}` | Optional credentials (`/N`, `/P`); empty values omit the flags | Defaulted | Empty = no credentials, the `/N` / `/P` (or `--user` / `--password`) flags are omitted. **Never ask up front.** Re-ask only if the command itself fails with an authentication error from the platform. An empty password is a fully valid configuration for dev / test infobases. |
| `{EXTENSION_NAME}` | Default/primary extension for a single-target operation; the resolved pass supplies `-Extension` | Defaulted | Empty = main configuration unless the task explicitly selects another target; never overwrite this setting just to switch a pass |
| `{EXTENSION_NAMES}` | Comma-separated extension list defining the **full snapshot** (cf + cfe), order = load order, not runtime application order; consumed by full-snapshot commands | Defaulted | Ordinary single-target calls use `EXTENSION_NAME`. Explicit `all` / full-snapshot work resolves inventory via `extension-workspace.md`; confirmed no extensions means main only, never a silent single-extension fallback. **Never ask up front**; resolve missing inventory only when the full snapshot is requested |
| `{EXPORT_PATH}` | Main source-export directory in a shared project; established legacy single-extension source root remains valid | Defaulted | Empty = current repository root; commands resolve the chosen target's actual root before substituting templates |
| `{EXTENSIONS_PATH}` | Root directory of extension sources — each extension from `EXTENSION_NAMES` lives in `{EXTENSIONS_PATH}\<Name>\` | Defaulted | Empty = the `cfe` directory at the repository root |
| `{DT_SNAPSHOT_PATH}` | `.dt` snapshot (data + configuration) used by `/restore-testbase` as the data baseline | Defaulted | Empty = `/restore-testbase` skips the data step and refreshes configuration only |
| `{RELEASE_PATH}` | Output directory for `/build-release` artifacts (`.cf` / `.cfe` / `.cfu`) | Defaulted | Empty = the `release` directory at the repository root |
| `{LOG_PATH}` | Designer log file (must be writable) | Defaulted | Empty = `$env:TEMP\1cv8.log` (Windows) / `$TMPDIR/1cv8.log` (POSIX). The directory always exists; any writable path works equally well — **never ask up front**. Re-ask only if the resolved path turns out to be non-writable at runtime. |
| `{RESULT_PATH}` | `/DumpResult` file of every Designer batch launch — the numeric verdict (`0` = success) read next to the exit code and the `/Out` log (`designer-batch-checks.md → The verdict is three signals`) | Defaulted | Empty = `$env:TEMP\1cv8.result` (Windows) / `$TMPDIR/1cv8.result` (POSIX). Deleted before each launch; a missing file after a launch is a failed launch — **never ask** |
| `{INFOBASE_PUBLISH_URL}` | Web-publish URL of the test infobase for `1c-tester` UI tests | **Highly desirable** for UI testing | Empty = UI tests are silently skipped, the rest of `/deploy-and-test` still runs; only ask if the user explicitly requested UI tests |
| `{UI_TESTING}` | Web UI-testing mode for `1c-tester` / `/deploy-and-test` Step 4: `manual` \| `auto` \| `off` | Defaulted | Empty = `manual` (see the classification below) |
| `{IBCMD_CONFIG}` | Path to standalone-server `config.yml` for `ibcmd`-based ops | Defaulted | Empty = fallback to Designer (per `.dev.env.example`) |
| `{PLATFORM_ARGS}` / `{IBCMD_ARGS}` | Extra launch arguments (comma-separated) appended to every `1cv8.exe` / `ibcmd` run by the `1c-metadata-manage` `db-*` / `epf-*` tools | Defaulted | Empty = no extra arguments. **Never ask.** Arguments the tool owns itself (`/F`, `/S`, `/N`, `/P`, `/UpdateDBCfg`, `--db-path`, …) are rejected by the scripts — pass those as regular parameters |
| `{SUPPORT_GUARD}` | Reaction of the vendor-support guard in the `1c-metadata-manage` mutating tools when the target is an object of a typical configuration "на замке": `deny` \| `warn` \| `off` | Defaulted | Empty = `deny` — the edit is refused with a diagnostic. **Never ask**; see the note below |
| `{NEW_OBJECT_POSITION}` | Where the creating tools of `1c-metadata-manage` put a new object inside `<ChildObjects>` of `Configuration.xml`: `end` \| `byName` | Defaulted | Empty = `end` — appended after the last object of the same kind, as Configurator does. **Never ask**; see the note below |
| `{REPOSITORY_PATH}` | Configuration repository (хранилище) address — local path or `tcp://server/alias`. **Master switch of repository mode**: non-empty activates the `1c-repository-manage` skill and the lock-before-edit / commit-after-verify SDLC discipline | Defaulted (see the note below) | Empty = the configuration is not repository-bound; the skill and repository steps stay inactive. **Never ask up front**; ask once only when the user explicitly requests a repository operation and the value is missing |
| `{REPOSITORY_USER}` / `{REPOSITORY_PASSWORD}` | Repository credentials (`/ConfigurationRepositoryN` / `/ConfigurationRepositoryP`); empty values omit the flags | Defaulted | Empty = no repository authentication flags. **Never ask up front**; re-ask only after a repository authentication error |
| `{REPOSITORY_ALLOW_FORCE}` | First half of the double opt-in for `-force` repository operations in the `repo-ops` script (forced get/commit, forced unlock discarding uncommitted changes) | Defaulted | Empty = `false` — every `-Force` call is refused. **Never ask, never set it yourself**: the value is the user's decision for an approved maintenance window |

#### `INFOBASE_ROLE` — what the agent may do to the project infobase

The role is the project's statement about its infobase, not the agent's guess from a path, a name or a user list. Every command that says "the target must be an explicitly identified dev/test infobase" reads it first: `/update1cbase`, `/deploy-and-test`, `/restore-testbase`, `/initproject from-ib`, the Designer batch check ladder, Gates 3a and 6, and the live-IB write rules.

| Value | Meaning |
|---|---|
| `dev`, `test` | The base is identified as dev/test. The gates pass without the confirmation question, forced session termination included. |
| `prod` | The agent does **not** change this base. Refused: configuration and extension loads, DB configuration apply (`/UpdateDBCfg`, extension apply), `.dt` restore, `/RollbackCfg`, repository `lock -Revised` / `update` / `commit` through it, and writes through `1c-data-mcp`. Allowed: read-only work — dumps (`/loadfrom1cbase`, `/getconfigfiles`), repository `status` / `history` / `diff`, and live-IB queries on the user's explicit request (Gate 3a does not run). A change that must reach this base is handed to the user as exact commands with the production overrides of `/update1cbase` and the `/build-release` Step 7 checklist. |
| empty | Unknown. Each dev/test gate asks the user once before its first mutating step; the answer holds for the current task only. |

- Only the user sets the value. Record `dev` / `test` / `prod` in `.dev.env` only when the user states the role explicitly. Never lower `prod`, never clear it, and never repoint `INFOBASE_PATH` / `INFOBASE_PUBLISH_URL` to get past a refusal. A refusal on `prod` is the correct outcome, not an obstacle.
- The role applies to the base these keys name. Work on a copy only when the user supplies the copy's connection; that copy is identified on its own terms.

#### `REPOSITORY_PATH` — configuration repository binding

A non-empty `REPOSITORY_PATH` is the project's explicit statement "we work with a 1C configuration repository". It changes the SDLC: objects must be locked in the repository before mutation and committed after verification, `/update1cbase` requires locks on the loaded objects, and every repository operation runs through the `1c-repository-manage` skill (`content/skills/1c-repository-manage/SKILL.md` — hard gate per `AGENTS.md → Skills and Subagents`). Process canon — the skill's `docs/repo-sdlc.md`. **While the parameter is set, disconnecting the configuration from the repository is forbidden** (`/ConfigurationRepositoryUnbindCfg` and any equivalent) — canon `SKILL.md → Safety invariants`. When the parameter is empty, none of this applies and the agent must not raise the topic.

#### `SUPPORT_GUARD` — editing a typical configuration on vendor support

Every mutating tool of the `1c-metadata-manage` skill checks whether the target belongs to a configuration on vendor support (recognized by `Ext/ParentConfigurations.bin` next to `Configuration.xml`) and whether the object is locked. Direct edits of such objects silently break future vendor updates, so the default is a hard refusal — **a refusal is the correct outcome, not an obstacle to route around by hand-editing XML**.

| Value | Meaning |
|---|---|
| `deny` (default / empty) | The edit is refused, exit code `1`, with the ready-made `support-edit` command for this exact case |
| `warn` | Warning to stderr, the edit proceeds — for projects that knowingly work off-support |
| `off` | No check at all |

The standard answer to a refusal is a change **in an extension** (`cfe-borrow` / `cfe-patch-method`); a deliberate support-state change is the skill's `support-edit` tool. Canon — `content/skills/1c-metadata-manage/docs/support-manage.md`.

#### `NEW_OBJECT_POSITION` — placement of a new object in `Configuration.xml`

When a creating tool of the `1c-metadata-manage` skill registers a new object, it adds one `<Kind>Name</Kind>` line to `<ChildObjects>` of `Configuration.xml`. This parameter decides **where** inside its own kind group that line goes. It is **Defaulted** — empty / missing / invalid resolves to `end`, and the agent **must not** ask for the value.

| Value | Meaning |
|---|---|
| `end` (default / empty) | After the last object of the same kind — what Configurator itself does. Backward-compatible behaviour. |
| `byName` | Alphabetically inside its own kind group, using the deterministic 1C-tree comparator (case-insensitive, `_` before digits before letters, Latin before Cyrillic, `ё` collated as `е`). Matches the platform standard **АПК:1108**, which expects metadata to be ordered by name in the configuration tree. |

Two behaviours are **not** configurable and apply in both modes:

- A group of a **kind not yet present** in the file is inserted in canonical kind order (before the first group of a kind that sorts later), never appended to the end of the block — otherwise the platform reorders it on the first dump and produces a diff nobody asked for.
- Kinds whose tree order carries meaning are never sorted by name: `Subsystem` and `CommandGroup` (their tree order drives the command interface until they are listed in `<SubsystemsOrder>` / `<GroupsOrder>`), `CommonAttribute` (the standard's own exception — separator attributes are applied in tree order), and `Language`.

The parameter only chooses a place for a **new** entry; it never reorders objects already registered.

> **`.dev.env` is the single source of truth for the skill's scripts too.** The `1c-metadata-manage` tools are vendored from upstream `cc-1c-skills`, which natively reads its own `.v8-project.json`. They are patched locally to read `.dev.env` **first** — `PLATFORM_PATH`, `PLATFORM_ARGS`, `IBCMD_ARGS`, `SUPPORT_GUARD`, `NEW_OBJECT_POSITION` — so a project never maintains a second config file. `.v8-project.json` remains supported only as a fallback for projects that deliberately keep the upstream multi-base registry. The second local patch is the batch verdict: every Designer launch of the skill (`db-dump-*`, `db-load-*`, `db-update`, `epf-build`, `epf-dump`) passes `/DumpResult` beside `/Out` and fails the run when the result is non-zero or the file was never written, so a batch command that fails while `1cv8` exits 0 is not reported as success (`designer-batch-checks.md → The verdict is three signals`).

#### `UI_TESTING` — web UI-testing mode

Browser UI testing (via the `1c-tester` subagent and Step 4 of `/deploy-and-test`) burns a lot of tokens and is not always effective, so it is **not** an automatic step by default. `UI_TESTING` makes it a configurable, opt-in stage. It is **Defaulted** — empty resolves to `manual`, and the agent **must not** ask for the value.

| Value | Meaning |
|---|---|
| `manual` (default / empty) | UI tests run **only on an explicit user request**. The subagent pipeline and the verification phase never trigger them automatically. Deployment (`/deploy-and-test` Steps 1–3) still runs; Step 4 (UI tests) is skipped unless the user asked for it. |
| `auto` | UI tests run automatically in the verification phase / after a successful deploy, **provided `INFOBASE_PUBLISH_URL` is set**. This is the only mode where UI testing is a routine step. |
| `off` | Web testing is fully disabled. Do not run it even when `INFOBASE_PUBLISH_URL` is set; on an explicit user request, report that it is disabled in `.dev.env` and ask the user to switch to `manual` / `auto` before proceeding. |

`UI_TESTING` gates **whether** UI testing runs; `INFOBASE_PUBLISH_URL` supplies **where** it runs. Both must be satisfied for a run: an empty `INFOBASE_PUBLISH_URL` skips UI tests regardless of mode, and `UI_TESTING=off` skips them regardless of the URL. Any invalid value is treated as `manual`.

**Which tool drives the browser** is separate from this gate — canon: `ui-testing-tools.md`. Default for the web client: `agent-browser` (`/install-agent-browser`). Desktop CV / `Windows-MCP` (`/install-windows-mcp`) is last resort only.

#### `USE_EDT` — project uses 1C:EDT

`USE_EDT=true|false` is an **Install-time selection** and the durable project-level signal for the EDT branch of the ruleset. The installer asks once, **only while creating** `.dev.env`, among the other setup questions. A project whose existing `.dev.env` predates the key gets `USE_EDT=false` appended **without a question** — on an update that would be the single interactive prompt of an otherwise unattended run — and `-NonInteractive` writes the same conservative default.

| Value | Meaning |
|---|---|
| `true` | The project is developed in 1C:EDT. `content/rules/edt-workflow.md` applies: source-format check before metadata actions, EDT-MCP routing, model↔disk synchronization, EDT validation, and the EDT deployment path. `/installtools` recommends EDT-MCP. |
| `false` | EDT is not part of the project workflow. `edt-workflow.md` does not apply, EDT-MCP is not recommended or preselected, and EDT is never proposed as a way to do a task. |

Missing, empty or invalid values are `unknown`, not proof that EDT is absent. Only `/installtools`, `/install-edt-mcp`, or an explicit user statement that the project moved to EDT may ask and persist the choice; ordinary development tasks must not interrupt work to ask. An EDT installation found on the workstation, or a leftover `edt-mcp` entry in a client config, is evidence about the machine — not about the project.

### Tool policy

`TOOL_*` parameters control whether a provider may be used, separately from whether it is installed or callable. Values: `auto` (default when missing/empty), `off`, `required`; resolution and failure handling belong to `content/rules/mcp-policy.md → Tool availability`. No per-task questionnaire. Invalid non-empty values block only the dependent provider step. Older `.dev.env` files retain automatic routing; the installer appends missing keys as `auto` without overwriting choices.

| Parameter | Provider / capability |
|---|---|
| `TOOL_COGNEE` | Cognee memory, including `cognee-memory` aliases |
| `TOOL_OPENVIKING` | OpenViking memory/context |
| `TOOL_TEMPLATES` | `1c-templates-mcp`: both code templates and memory |
| `TOOL_GRAPH` | `1c-graph-metadata-mcp`: indexed project discovery and impact |
| `TOOL_CODE` | `1c-code-metadata-mcp`: code/metadata/form search and XML validation |
| `TOOL_DOCS` | `1C-docs-mcp`: platform help, routed standards and formats |
| `TOOL_SSL` | `1c-ssl-mcp`: БСП APIs |
| `TOOL_SYNTAX` | `1c-syntax-checker-mcp`: syntax validation |
| `TOOL_CHECKER` | `1c-code-check-mcp`: code checks, reviews, AI/ITS tools |
| `TOOL_DATA` | `1c-data-mcp`: live-IB checks |
| `TOOL_EDT` | EDT-MCP; workflow still requires `USE_EDT=true` |
| `TOOL_AGENT_BROWSER` | agent-browser, MCP and CLI |
| `TOOL_BROWSER` | Active client's built-in browser tools |
| `TOOL_WINDOWS_MCP` | Windows-MCP desktop automation |
| `TOOL_UI_TEST` | Optional `MCP_Test` / `1C Visual UI Test` |
| `TOOL_CONVERSION` | Optional `MCP_ConversionData20` |

Examples: `TOOL_COGNEE=off` excludes Cognee while other memory providers remain eligible; `TOOL_SYNTAX=required` blocks syntax verification when its tool is missing; `TOOL_AGENT_BROWSER=off` selects an eligible browser fallback without an installation question. No key switches off the shipped metadata/IB/repository procedures. `rtk` remains a user-global shell proxy managed by `/install-rtk`, not project tool routing.

### Subagent model parameters

Consumed by the **installer** when rendering subagent files (source agents declare an abstract `modelTier: coding | analysis | light` instead of a concrete model — see `content/rules/subagents.md → Model-tier routing`). At task time, `SUBAGENT_MODEL_ANALYSIS` also controls reviewer eligibility (`content/rules/subagents.md → Reviewer model gate`); empty / missing means review subagents are disabled unless the user explicitly selects a model for that invocation. Other agents retain the defaults below. On first install the installer offers a benchmark-based profile (`Balanced` / `Economy` / `Quality`, from <https://onec-llm-bench.lovable.app/>) that fills all three values; any of them may still be overridden or left empty.

| Parameter | Effect | Class | Behavior when empty |
|---|---|---|---|
| `{SUBAGENT_MODEL_CODING}` | Concrete model for tier `coding` (code / metadata authorship, architecture design: `1c-developer`, `1c-metadata-manager`, `1c-architect`, `1c-performance-optimizer`, `1c-refactoring`) | Defaulted | Empty = the model field is omitted from installed agent files; the AI client uses its default model. **Never ask at task time**; re-render via `install.ps1 update` after editing. |
| `{SUBAGENT_MODEL_ANALYSIS}` | Concrete model for tier `analysis` (planning / analysis / review / testing / docs: `1c-planner`, `1c-analytic`, `1c-arch-reviewer`, `1c-code-reviewer`, `1c-doc-writer`, `1c-tester`) | Defaulted | Installer: same as above; legacy 2-tier files with no key fall back to `SUBAGENT_MODEL_CODING`. Dispatch: inherited / fallback models do not enable review subagents — apply the reviewer model gate. |
| `{SUBAGENT_MODEL_LIGHT}` | Concrete model for tier `light` (small bounded read-only tasks: repo scouting, search, impact lists, mechanical checks: `1c-explorer`) | Defaulted | Same as above |

These three describe the models **subagents** run on. The model the **parent agent** runs on is a different parameter — `AGENT_MODEL` below — and the two never affect each other.

#### `AGENT_MODEL` — active-model profile of the parent agent

Selects the behaviour profile applied to the model that actually executes this ruleset (`AGENTS.md → Active model adaptation`; router — `model-adaptation.md`). Consumed **at task time** by the agent, not by the installer: all profile files are installed as ordinary on-demand rules, so changing the value needs no re-render and no client restart. It is **Defaulted** — missing file / missing key / empty / unrecognised value = no profile, the base (model-neutral) ruleset applies; the agent **must not** ask for the value. The canonical editor is the `/rulesmodel` slash command, which accepts a model name in any spelling and normalises it; manual edits are allowed. On first install the installer offers the choice (or leaves it empty in `-NonInteractive`).

| Value | Meaning |
|---|---|
| `opus5` | Claude Opus 5 → `model-opus5.md` (shorter reports, less narration, no self-invented extra verification, damped subagent spawning, keep thinking on, lean context and described interfaces over examples) |
| `sonnet5` | Claude Sonnet 5 → `model-sonnet5.md` (literal instruction following — state scope explicitly, described interfaces over examples, effort calibration, adaptive thinking stays on for tool use, coverage-first review briefs, lean context) |
| `fable5` | Claude Fable 5 / Mythos 5 → `model-fable5.md` (act instead of overplanning, lean context and described interfaces over examples, evidence-audited progress claims, stated boundaries and checkpoints, no self-narrated reasoning, parallel subagents, memory-first) |
| `gpt56` | GPT-5.6 → `model-gpt56.md` (lean context — each instruction once, reasoning-effort and verbosity calibration, autonomy boundaries, intent-level briefs) |
| `gpt6` | GPT-6 Astra → `model-gpt6.md` (explicit completion criteria, follow-through within authorization, precise skill selection and progressive disclosure, concise prose, bounded delegation and verification) |
| *empty / other* | No profile. The base ruleset is complete on its own; a model without a profile never borrows a neighbouring one. |

**Boundary:** a profile tunes initiative and communication only (report length, narration cadence, planning depth, delegation eagerness, self-invented extra passes) and can never weaken a hard gate — metadata / infobase tooling gates, MCP-first search, the platform-capability check, `templatesearch` / `recall` and the memory gates, the validator chain and its budget, triage, `CONFUSION`, or the delivery report. Precedence and the model-agnostic prompting baseline — `model-adaptation.md → §4`, `§5`.

#### `ORCHESTRATION` — orchestrator economy mode

Controls how eagerly the parent agent delegates execution to subagents. It is **Defaulted** — missing file / missing key / empty / invalid value resolves to `standard`, and the agent **must not** ask for the value at task time. The canonical editor of this key is the `/economymode` slash command (`on` / `off` / `models`); manual edits are allowed but not required. Inside that command's explicit flow, asking the user which per-tier models to use (`SUBAGENT_MODEL_*`) **is** allowed — an invoked configuration command is not "task time"; the never-ask policy for regular tasks stays intact.

| Value | Meaning |
|---|---|
| `standard` (default / empty) | Regular delegation policy from `subagents.md`: delegate when the task is large enough to justify the overhead, execute directly otherwise. |
| `economy` | Orchestrator economy mode (`content/rules/orchestrator-economy.md`): the parent keeps decisions, specs, and verification; reading and writing are delegated to subagents per tier. Model selection is unaffected — models still come from `SUBAGENT_MODEL_*` by tier. |

### Process-tuning parameters

Consumed by the triage and debugging rules at task time. All are **Defaulted** — empty / missing / invalid resolves to the documented default; the agent **must not** ask for the values.

| Parameter | Effect | Class | Behavior when empty |
|---|---|---|---|
| `{QUICKFIX_MAX_LINES}` | Line budget of the quick-fix path (`AGENTS.md → Triage`): the maximum changed BSL lines for which a one-logical-change-in-one-module edit may stay quick-fix. Promotion triggers (`verification-policy.md → Triage details`) always win over the budget. | Defaulted | Empty / invalid = `40`. Raise for teams comfortable with larger direct edits; lower for stricter projects. |
| `{DEBUG_FAST_PATH}` | Debugging fast-path mode (`standards(name="systematic-debugging") → Fast path`): `standard` \| `extended` \| `off`. Controls when a directly evidenced bug may skip the full 4-phase loop. | Defaulted | Empty / invalid = `standard` |
| `{VERIFICATION_DEPTH}` | SDLC QA profile (`verification-policy.md → "Verification depth levels"`): `lite` \| `standard` \| `full`. Tunes Gates 1–3 for low-risk edits, independently of task triage. Set by `/sdlc`; `/litemode` remains a compatibility alias. | Defaulted | Empty / invalid = `standard` |
| `{CAVEMAN}` | caveman communication-style auto-activation (`content/skills/caveman/SKILL.md`): `on` \| `auto` \| `off`. Controls whether the terse style turns on automatically and for which tasks. Does not affect the mandatory report structure or verification. | Defaulted | Empty / invalid = `auto` |
| `{METADATA_PREVIEW}` | When wrapper `-Preview` on `Invoke-1CEdit.ps1` runs before a metadata write: `auto` \| `on` \| `off`. Toggled by `/previewmode`. Does not relax native `-DryRun` / `-Force` on deletions. | Defaulted | Empty / invalid = `auto` — preview only for DSL generation and an operation new to the project |
| `{AGENT_MODEL}` | Active-model behaviour profile of the parent agent (`model-adaptation.md`): `opus5` \| `sonnet5` \| `fable5` \| `gpt56` \| `gpt6`. Tunes verbosity, narration, planning depth, delegation eagerness and self-invented extra passes; never weakens a hard gate. Toggled by `/rulesmodel`. Full description — `#### AGENT_MODEL` above. | Defaulted | Empty / unrecognised = no profile; the base model-neutral ruleset applies |

#### `VERIFICATION_DEPTH` — static code-verification depth

Select the SDLC QA profile via `/sdlc lite|standard|full` (`/litemode` remains compatible). `VERIFICATION_DEPTH` tunes Gates 1–3 for **low-risk** edits; missing / empty / invalid = `standard`, never ask at task time. Selecting `lite` also sets `UI_TESTING=off`; manual edits are allowed. Canonical semantics — `verification-policy.md → "Verification depth levels"`.

| Value | Meaning |
|---|---|
| `full` | All three validators on every change; up to 3 calls total per validator after blocking fixes. Always applied to promotion-trigger paths regardless of this setting. |
| `standard` (default / empty) | Full-cycle: all three validators. Quick-fix-eligible edit: `syntaxcheck` + `check_1c_code`; `review_1c_code` on a promotion trigger or explicit request. One mandatory confirmation after a blocking fix (2 calls total). |
| `lite` | Full-cycle: `syntaxcheck` + `check_1c_code`. Quick-fix-eligible edit: `syntaxcheck` only. `review_1c_code` on a promotion trigger or explicit request. |

**Safety floor:** `syntaxcheck` is always run at every level, and any change on a promotion-trigger path (transactions, public `Экспорт` contracts, wired metadata, RLS, subscriptions / scheduled jobs — `verification-policy.md → Triage details`) always runs the full chain regardless of the level. `lite` / `standard` lighten only the checks already applied to low-risk edits; they do not weaken the control of dangerous paths. Gates 4 (impact) / 5 (XML) are unaffected.

#### `CAVEMAN` — caveman auto-activation

Controls **whether** the terse `caveman` communication style (`content/skills/caveman/SKILL.md`) turns on **automatically** and for **which** tasks. It is **Defaulted** — empty / invalid resolves to `auto`, and the agent **must not** ask for the value. It affects only presentation: model selection, the five-step development procedure, verification depth, and the mandatory report structure are all unchanged.

| Value | Meaning |
|---|---|
| `auto` (default / empty) | The skill auto-classifies by task type: on for development (writing / editing / refactoring code, debugging, deploy, shell), off for analysis / review / documentation — where readable prose is the deliverable. |
| `on` | `caveman` is active for **all** tasks — development and analysis / review / documentation alike. Only the skill's safety switches apply (code, error text, destructive / security / ordered blocks stay in normal grammar). |
| `off` | Automatic activation is disabled — `caveman` never turns on by itself on any task. It can still be enabled by an explicit in-session force ("caveman please"), which holds until session end. |

**Precedence:** an explicit session force always wins over `CAVEMAN`; otherwise the `CAVEMAN` value applies (`on` → all tasks, `auto` → by task type, `off` → no auto-on). The persistent value is edited by the `/caveman on|auto|off` command (`content/commands/caveman.md`); session-only force uses the phrases "caveman please" / "stop caveman" or a `/caveman lite|full|ultra` level switch.

#### `METADATA_PREVIEW` — wrapper dry-run before a metadata write

Controls **when** `Invoke-1CEdit.ps1 -Preview` (run the tool, show a unified diff, restore the tree) precedes the same call without `-Preview`. It is **Defaulted** — empty / invalid resolves to `auto`, and the agent **must not** ask for the value. The canonical editor is the `/previewmode` slash command (`on` / `auto` / `off`, plus `once` for a single session-scoped preview).

| Value | Meaning |
|---|---|
| `auto` (default / empty) | Preview only where the write's shape is unpredictable: generation from a DSL (`form-compile`, `meta-compile`, `role-compile`, `skd-edit` batches) and a tool or `-Operation` not yet run in this project. Everything else applies immediately. |
| `on` | Preview before every wrapper-driven write. |
| `off` | Only on an explicit user request (`/previewmode once`). |

The wrapper previews its own script writes only; host-made edits and BSL rewrite proposals never pass through it, a dirty tree applies with a note, deletions keep native `-DryRun` / `-Force`, and no mode turns preview into a verification gate. Canon — `content/skills/1c-metadata-manage/docs/edit-preview.md → When preview runs`.

Task number `{TASK}` is **only required when modification comment markers are produced** — i.e. when the change touches **typical (standard) configuration code** and the templates `{COMMENT_OPEN}` / `{COMMENT_CLOSE}` reference `{TASK}`. For new objects with `{PREFIX}` (no per-method markers), review / analysis / documentation tasks, and any task where `COMPANY` / `DEVELOPER` are empty (markers skipped) — `{TASK}` is **not required**. Do not block on it.

When `{TASK}` is required and not provided — ask the user once and reuse the same value across the whole change.

### Support-channel parameters

Consumed by `/support`, `/supportstatus` and `/checkupdates` (contract — `support-feedback.md`). The channel is a **hard AND**: a ticket is sent only when `SUPPORT_KEY` **and** `SUPPORT_EMAIL` are both non-empty. Neither is asked at install time — the installer only appends the empty keys, because the key itself ships with the MCP distribution and the e-mail is the user's own.

| Parameter | Effect | Class | Behavior when empty |
|---|---|---|---|
| `{SUPPORT_KEY}` | Shared support key, sent as the `X-Support-Key` header. Ships with the MCP distribution (`config.env`, section 6); a fresh one comes from the personal cabinet at https://vibecoding1c.ru/. **Secret**: never echoed into chat, logs, ticket text, or `context`. | Highly desirable for `/support` | `/support` and `/supportstatus` send nothing and report which of the two values is missing and where to get it. Never invent a key, never borrow one from another project. |
| `{SUPPORT_EMAIL}` | Working e-mail of the ticket author. The operator answers to it; `/supportstatus` filters your tickets by it. | Highly desirable for `/support` | Same as above. The e-mail is the user's own — ask for it only when `/support` is actually being invoked. |
| `{SUPPORT_API_URL}` | Endpoint of the support service. | Defaulted | Empty = `https://d5ds85pood7ob80g5fd9.nnekmrav.apigw.yandexcloud.net`. Fill in only for a dedicated instance. |

A ticket is created with status `новый` and is moved to `закрыт` by the operator. The whole section is inert for development work: an empty support block blocks no code, review, or infobase task.

See `.dev.env.example` for the template.
