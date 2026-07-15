---
description: Project and process parameters from .dev.env — code generation, infobase operations, UI testing, subagent models, orchestration, and verification depth
alwaysApply: false
category: development
---

# Development Standards — Environment and Process Parameters

**When to load this file:** only when the current task depends on a project parameter, infobase / deployment operation, UI testing, subagent routing, quick-fix limit, debugging mode, verification depth, or the `caveman` communication-style toggle. Do not load it for a code-style-only question.

Section number 1 is preserved from the former monolithic `dev-standards-core.md` for stable references.

## 1. Project Parameters (.dev.env)

`.dev.env` is the **single source of truth** for project parameters across the whole rules set. There is no `infobasesettings.md`, no separate per-command settings file — all rules, on-demand instructions, slash commands and subagents read from `.dev.env`.

Read `.dev.env` **only when the current task actually depends on a parameter** (prefix / naming, modification comments, platform-version choices, metadata placement, infobase commands, deploy, UI tests). Guessing values is PROHIBITED.

### Global principle — no field is globally mandatory

No field in `.dev.env` blocks the entire ruleset. **Every parameter is task-scoped**: missing values matter only when a **specific** scheduled operation cannot proceed without them. Three classes:

- **Advisory** — empty is silently valid; a documented fallback applies. **MUST NOT be asked about**, ever (not at install time per task, not on apply phase, not in subagents).
- **Highly desirable for a specific operation** — empty does not block unrelated work, but the operation that needs the value cannot complete. Ask the user **only when that operation is in scope of the current task**. Do not gather empties up front "for completeness".
- **Defaulted** — empty resolves to a documented default; no question, no fallback noise.

### Code-generation parameters

| Parameter | Effect | Class | Behavior when empty |
|---|---|---|---|
| `{PREFIX}` | Prefix for ALL new metadata objects, attributes, form elements, roles | Advisory | No prefix on new objects; `{PREFIX}` in templates → empty string |
| `{COMPANY}` | Used in modification comment templates | Advisory | No modification markers emitted |
| `{DEVELOPER}` | Used in modification comment templates | Advisory | No modification markers emitted |
| `{PLATFORM_VERSION}` | Determines available platform features (e.g. `Асинх` / `Ждать` from 8.3.18 vs `ОписаниеОповещения` callbacks for older versions). See `dev-standards-architecture.md §3 → "Async and Modality"` | Highly desirable when generating platform-version-sensitive code | Ask only when the current task actually depends on version-specific behavior; otherwise proceed |
| `{COMMENT_OPEN}` / `{COMMENT_CLOSE}` | Modification comment templates with `{COMPANY}`, `{DEVELOPER}`, `{DATE}`, `{TASK}` placeholders | Highly desirable when markers are emitted | If `COMPANY` / `DEVELOPER` are also empty — markers are not emitted anyway; otherwise ask once |
| `{NEW_OBJECTS_IN}` | Where to place new objects: `main_configuration` or `extension` | Defaulted | Defaults to `main_configuration` |

### Advisory parameters — `PREFIX`, `COMPANY`, `DEVELOPER`

Both these parameters and the practices they govern — adding a project prefix to new objects (`PREFIX`) and stamping modification comments with company / developer attribution (`COMPANY`, `DEVELOPER`) — are **recommendations**, not hard requirements. They reflect a project convention; their absence is not a defect, code without a prefix or without modification banners is fully valid. When any of the three is empty in `.dev.env`, do **not** ask the user — apply the fallback below silently and proceed.

- **`PREFIX` is empty** — create new metadata objects, attributes, tabular sections, form elements, roles and subsystems **without a prefix**. Inside templates and examples, the placeholder `{PREFIX}` resolves to an empty string (`{PREFIX}ContractAmount` → `ContractAmount`, `{PREFIX}EventSubscriptions` → `EventSubscriptions`, `{PREFIX}AddedObjects` → `AddedObjects`). All other naming rules in `dev-standards-change-markers.md §4` still apply (synonyms, role naming inside subsystems, etc.). Naming collisions with typical metadata become the user's responsibility — flag any collision you notice, but do not invent a prefix to avoid it.
- **`COMPANY` or `DEVELOPER` is empty** — do **not** emit modification markers (`COMMENT_OPEN` / `COMMENT_CLOSE`) in any module, even when modifying typical (standard) code. Removed typical code is still commented out, not deleted, and new procedures in typical modules are still placed at the end of the relevant region — but without the surrounding `// +++ … / // --- …` banners. The single header block for entirely new (non-typical) modules described in §3 is also skipped when either parameter is empty.
- **Both fallbacks are independent** — an empty `PREFIX` does not suppress markers, and empty `COMPANY` / `DEVELOPER` does not enable a prefix.
- **`{TASK}` is irrelevant when markers are not emitted** — do not ask for it.

### Infobase / deployment parameters

Used by `/loadfrom1cbase`, `/update1cbase`, `/getconfigfiles`, `/deploy-and-test` and the `1c-tester` subagent. **Not consulted at all for pure code, review, analysis, or documentation tasks** — pure code work proceeds even when this entire block is empty.

| Parameter | Effect | Class | Behavior when empty |
|---|---|---|---|
| `{PLATFORM_PATH}` | 1C platform install dir (must contain `bin\1cv8.exe`); used as the executable for all Designer-mode commands | Highly desirable for any IB-bound command | Ask when an IB-bound command is scheduled; the command cannot run without it |
| `{INFOBASE_KIND}` | `file` → `/F`, `server` → `/S` flag for Designer | Defaulted | Defaults to `file` (per `.dev.env.example`) |
| `{INFOBASE_PATH}` | Path to file infobase or connection string of server infobase | **Highly desirable** for configuration load / dump operations | Ask only when `/loadfrom1cbase`, `/update1cbase`, `/getconfigfiles`, `/deploy-and-test` is invoked; otherwise stay silent |
| `{IB_USER}` / `{IB_PASSWORD}` | Optional credentials (`/N`, `/P`); empty values omit the flags | Defaulted | Empty = no credentials, the `/N` / `/P` (or `--user` / `--password`) flags are omitted. **Never ask up front.** Re-ask only if the command itself fails with an authentication error from the platform. An empty password is a fully valid configuration for dev / test infobases. |
| `{EXTENSION_NAME}` | Optional `-Extension` argument | Defaulted | Empty = operations apply to main configuration |
| `{EXPORT_PATH}` | Source-export directory | Defaulted | Empty = current repository root |
| `{LOG_PATH}` | Designer log file (must be writable) | Defaulted | Empty = `$env:TEMP\1cv8.log` (Windows) / `$TMPDIR/1cv8.log` (POSIX). The directory always exists; any writable path works equally well — **never ask up front**. Re-ask only if the resolved path turns out to be non-writable at runtime. |
| `{INFOBASE_PUBLISH_URL}` | Web-publish URL of the test infobase for `1c-tester` UI tests | **Highly desirable** for UI testing | Empty = UI tests are silently skipped, the rest of `/deploy-and-test` still runs; only ask if the user explicitly requested UI tests |
| `{UI_TESTING}` | Web UI-testing mode for `1c-tester` / `/deploy-and-test` Step 4: `manual` \| `auto` \| `off` | Defaulted | Empty = `manual` (see the classification below) |
| `{IBCMD_CONFIG}` | Path to standalone-server `config.yml` for `ibcmd`-based ops | Defaulted | Empty = fallback to Designer (per `.dev.env.example`) |

#### `UI_TESTING` — web UI-testing mode

Browser UI testing (via the `1c-tester` subagent and Step 4 of `/deploy-and-test`) burns a lot of tokens and is not always effective, so it is **not** an automatic step by default. `UI_TESTING` makes it a configurable, opt-in stage. It is **Defaulted** — empty resolves to `manual`, and the agent **must not** ask for the value.

| Value | Meaning |
|---|---|
| `manual` (default / empty) | UI tests run **only on an explicit user request**. The subagent pipeline and the verification phase never trigger them automatically. Deployment (`/deploy-and-test` Steps 1–3) still runs; Step 4 (UI tests) is skipped unless the user asked for it. |
| `auto` | UI tests run automatically in the verification phase / after a successful deploy, **provided `INFOBASE_PUBLISH_URL` is set**. This is the only mode where UI testing is a routine step. |
| `off` | Web testing is fully disabled. Do not run it even when `INFOBASE_PUBLISH_URL` is set; on an explicit user request, report that it is disabled in `.dev.env` and ask the user to switch to `manual` / `auto` before proceeding. |

`UI_TESTING` gates **whether** UI testing runs; `INFOBASE_PUBLISH_URL` supplies **where** it runs. Both must be satisfied for a run: an empty `INFOBASE_PUBLISH_URL` skips UI tests regardless of mode, and `UI_TESTING=off` skips them regardless of the URL. Any invalid value is treated as `manual`.

### Subagent model parameters

Consumed by the **installer** when rendering subagent files (source agents declare an abstract `modelTier: coding | analysis | light` instead of a concrete model — see `content/rules/subagents.md → Model-tier routing`). Not consulted at task time. On first install the installer offers a benchmark-based profile (`Balanced` / `Economy` / `Quality`, from <https://onec-llm-bench.lovable.app/>) that fills all three values; any of them may still be overridden or left empty.

| Parameter | Effect | Class | Behavior when empty |
|---|---|---|---|
| `{SUBAGENT_MODEL_CODING}` | Concrete model for tier `coding` (code / metadata authorship, architecture design: `1c-developer`, `1c-metadata-manager`, `1c-architect`, `1c-performance-optimizer`, `1c-refactoring`) | Defaulted | Empty = the model field is omitted from installed agent files; the AI client uses its default model. **Never ask at task time**; re-render via `install.ps1 update` after editing. |
| `{SUBAGENT_MODEL_ANALYSIS}` | Concrete model for tier `analysis` (planning / analysis / review / testing / docs: `1c-planner`, `1c-analytic`, `1c-arch-reviewer`, `1c-code-reviewer`, `1c-doc-writer`, `1c-tester`) | Defaulted | Same as above. Legacy 2-tier `.dev.env` files with no `SUBAGENT_MODEL_ANALYSIS` key fall back to `SUBAGENT_MODEL_CODING` for this tier. |
| `{SUBAGENT_MODEL_LIGHT}` | Concrete model for tier `light` (small bounded tasks: repo scouting, search, quick error fixes, mechanical checks: `1c-explorer`, `1c-error-fixer`) | Defaulted | Same as above |

#### `ORCHESTRATION` — orchestrator economy mode

Controls how eagerly the parent agent delegates execution to subagents. It is **Defaulted** — missing file / missing key / empty / invalid value resolves to `standard`, and the agent **must not** ask for the value at task time. The canonical editor of this key is the `/economymode` slash command (`on` / `off` / `models`); manual edits are allowed but not required. Inside that command's explicit flow, asking the user which per-tier models to use (`SUBAGENT_MODEL_*`) **is** allowed — an invoked configuration command is not "task time"; the never-ask policy for regular tasks stays intact.

| Value | Meaning |
|---|---|
| `standard` (default / empty) | Regular delegation policy from `subagents.md`: delegate when the task is large enough to justify the overhead, execute directly otherwise. |
| `economy` | Orchestrator economy mode (`content/rules/orchestrator-economy.md`): the parent keeps decisions, specs, and verification; reading and writing are delegated to subagents per tier. Model selection is unaffected — models still come from `SUBAGENT_MODEL_*` by tier. |

### Process-tuning parameters

Consumed by the triage and debugging rules at task time. Both are **Defaulted** — empty / missing / invalid resolves to the documented default; the agent **must not** ask for the values.

| Parameter | Effect | Class | Behavior when empty |
|---|---|---|---|
| `{QUICKFIX_MAX_LINES}` | Line budget of the quick-fix path (`AGENTS.md → Triage`): the maximum changed BSL lines for which a one-logical-change-in-one-module edit may stay quick-fix. Promotion triggers (`verification-policy.md → Triage details`) always win over the budget. | Defaulted | Empty / invalid = `40`. Raise for teams comfortable with larger direct edits; lower for stricter projects. |
| `{DEBUG_FAST_PATH}` | Debugging fast-path mode (`systematic-debugging.md → Fast path`): `standard` \| `extended` \| `off`. Controls when a directly evidenced bug may skip the full 4-phase loop. | Defaulted | Empty / invalid = `standard` |
| `{VERIFICATION_DEPTH}` | Static code-verification depth (`verification-policy.md → "Verification depth levels"`): `full` \| `standard` \| `lite`. Tunes the depth of Gates 1–3 for low-risk edits. Toggled by `/litemode`. | Defaulted | Empty / invalid = `full` |
| `{CAVEMAN}` | caveman communication-style auto-activation (`content/skills/caveman/SKILL.md`): `on` \| `auto` \| `off`. Controls whether the terse style turns on automatically and for which tasks. Does not affect the mandatory report structure or verification. | Defaulted | Empty / invalid = `on` |

#### `VERIFICATION_DEPTH` — static code-verification depth

Tunes **how deep** the validator chain (`syntaxcheck → check_1c_code → review_1c_code`) runs for **low-risk** edits. It is **Defaulted** — empty / invalid resolves to `full`, and the agent **must not** ask for the value. The canonical editor is the `/litemode` slash command (which also sets `UI_TESTING=off` at level `lite`); manual edits are allowed but not required. Canonical semantics — `verification-policy.md → "Verification depth levels"`.

| Value | Meaning |
|---|---|
| `full` (default / empty) | All three validators; one clean pass on the latest state is required, with up to 3 calls total after blocking fixes (`AGENTS.md → MCP Tool Calling → B.1`). |
| `standard` | All three validators; normally one clean pass, with exactly one mandatory confirmation after a blocking fix (2 calls total, no open-ended retry loop). |
| `lite` | Low-risk edits: `syntaxcheck` stays mandatory, `check_1c_code` / `review_1c_code` run only for high-risk changes (promotion triggers) or on explicit request. |

**Safety floor:** `syntaxcheck` is always run at every level, and any change on a promotion-trigger path (transactions, public `Экспорт` contracts, wired metadata, RLS, subscriptions / scheduled jobs — `verification-policy.md → Triage details`) always runs the full chain regardless of the level. `lite` / `standard` lighten only the checks already applied to low-risk edits; they do not weaken the control of dangerous paths. Gates 4 (impact) / 5 (XML) are unaffected.

#### `CAVEMAN` — caveman auto-activation

Controls **whether** the terse `caveman` communication style (`content/skills/caveman/SKILL.md`) turns on **automatically** and for **which** tasks. It is **Defaulted** — empty / invalid resolves to `on`, and the agent **must not** ask for the value. It affects only presentation: model selection, the five-step development procedure, verification depth, and the mandatory report structure are all unchanged.

| Value | Meaning |
|---|---|
| `on` (default / empty) | `caveman` is active for **all** tasks — development and analysis / review / documentation alike. Only the skill's safety switches apply (code, error text, destructive / security / ordered blocks stay in normal grammar). |
| `auto` | The skill auto-classifies by task type: on for development (writing / editing / refactoring code, debugging, deploy, shell), off for analysis / review / documentation. |
| `off` | Automatic activation is disabled — `caveman` never turns on by itself on any task. It can still be enabled by an explicit in-session force ("caveman please"), which holds until session end. |

**Precedence:** an explicit session force always wins over `CAVEMAN`; otherwise the `CAVEMAN` value applies (`on` → all tasks, `auto` → by task type, `off` → no auto-on). The persistent value is edited by the `/caveman on|auto|off` command (`content/commands/caveman.md`); session-only force uses the phrases "caveman please" / "stop caveman" or a `/caveman lite|full|ultra` level switch.

Task number `{TASK}` is **only required when modification comment markers are produced** — i.e. when the change touches **typical (standard) configuration code** and the templates `{COMMENT_OPEN}` / `{COMMENT_CLOSE}` reference `{TASK}`. For new objects with `{PREFIX}` (no per-method markers), review / analysis / documentation tasks, and any task where `COMPANY` / `DEVELOPER` are empty (markers skipped) — `{TASK}` is **not required**. Do not block on it.

When `{TASK}` is required and not provided — ask the user once and reuse the same value across the whole change.

See `.dev.env.example` for the template.

