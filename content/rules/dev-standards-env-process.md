---
description: Process and model parameters from .dev.env — subagent model tiers, AGENT_MODEL, ORCHESTRATION, CODE_OWNER, quick-fix budget, debugging fast path, VERIFICATION_DEPTH, CAVEMAN, METADATA_PREVIEW, support channel
alwaysApply: false
category: development
---

# Development Standards — Process and Model Parameters

**When to load this file:** a task or command depends on subagent / model routing, orchestration, code ownership, triage or debugging defaults, verification depth, metadata preview, communication style or the support channel. Parameter classes and the ask-policy — `content/rules/dev-standards-env.md → Global principle`; every key below is **Defaulted** unless its row says otherwise, and the agent **must not** ask for a Defaulted value. Infobase, EDT and UI-testing keys stay in `dev-standards-env.md`; `TOOL_*` keys — `content/rules/tool-policy.md`.

## Subagent model parameters

Consumed by the **installer** when rendering subagent files (source agents declare an abstract `modelTier: coding | analysis | light` instead of a concrete model — see `content/rules/subagents.md → Model-tier routing`). At task time, `SUBAGENT_MODEL_ANALYSIS` also controls reviewer eligibility (`content/rules/subagents.md → Reviewer model gate`); empty / missing means review subagents are disabled unless the user explicitly selects a model for that invocation. Other agents retain the defaults below. On first install the installer offers a benchmark-based profile (`Balanced` / `Economy` / `Quality`, from <https://onec-llm-bench.lovable.app/>) that fills all three values; any of them may still be overridden or left empty.

| Parameter | Effect | Class | Behavior when empty |
|---|---|---|---|
| `{SUBAGENT_MODEL_CODING}` | Concrete model for tier `coding` (code / metadata authorship, architecture design: `1c-developer`, `1c-metadata-manager`, `1c-architect`, `1c-performance-optimizer`, `1c-refactoring`, `1c-error-fixer`) | Defaulted | Empty = the model field is omitted from installed agent files; the AI client uses its default model. **Never ask at task time**; re-render via `install.ps1 update` after editing. |
| `{SUBAGENT_MODEL_ANALYSIS}` | Concrete model for tier `analysis` (planning / analysis / review / testing / docs: `1c-planner`, `1c-analytic`, `1c-arch-reviewer`, `1c-code-reviewer`, `1c-doc-writer`, `1c-tester`) | Defaulted | Installer: same as above; legacy 2-tier files with no key fall back to `SUBAGENT_MODEL_CODING`. Dispatch: inherited / fallback models do not enable review subagents — apply the reviewer model gate. |
| `{SUBAGENT_MODEL_LIGHT}` | Concrete model for tier `light` (small bounded read-only tasks: repo scouting, search, impact lists, mechanical checks: `1c-explorer`) | Defaulted | Same as above |

These three describe the models **subagents** run on. The model the **parent agent** runs on is a different parameter — `AGENT_MODEL` in the table below — and the two never affect each other.

## `ORCHESTRATION` — orchestrator economy mode

Controls how eagerly the parent agent delegates execution to subagents. It is **Defaulted** — missing file / missing key / empty / invalid value resolves to `standard`, and the agent **must not** ask for the value at task time. The canonical editor of this key is the `/economymode` slash command (`on` / `off` / `models`); manual edits are allowed but not required. Inside that command's explicit flow, asking the user which per-tier models to use (`SUBAGENT_MODEL_*`) **is** allowed — an invoked configuration command is not "task time"; the never-ask policy for regular tasks stays intact.

| Value | Meaning |
|---|---|
| `standard` (default / empty) | Regular delegation policy from `subagents.md`: delegate when the task is large enough to justify the overhead, execute directly otherwise. |
| `economy` | Orchestrator economy mode (`content/rules/orchestrator-economy.md`): the parent keeps decisions, specs, and verification; reading and writing are delegated to subagents per tier. Model selection is unaffected — models still come from `SUBAGENT_MODEL_*` by tier. |

## Process-tuning parameters

Consumed by the triage and debugging rules at task time. All are **Defaulted** — empty / missing / invalid resolves to the documented default; the agent **must not** ask for the values.

| Parameter | Effect | Class | Behavior when empty |
|---|---|---|---|
| `{QUICKFIX_MAX_LINES}` | Line budget of the quick-fix path (`AGENTS.md → Triage`): the maximum changed BSL lines for which a one-logical-change-in-one-module edit may stay quick-fix. Promotion triggers (`verification-policy.md → Triage details`) always win over the budget. | Defaulted | Empty / invalid = `40`. Raise for teams comfortable with larger direct edits; lower for stricter projects. |
| `{DEBUG_FAST_PATH}` | Debugging fast-path mode (`standards(name="systematic-debugging") → Fast path`): `standard` \| `extended` \| `off`. Controls when a directly evidenced bug may skip the full 4-phase loop. | Defaulted | Empty / invalid = `standard` |
| `{VERIFICATION_DEPTH}` | SDLC QA profile: `lite` \| `standard` \| `full`. Selects the Gates 1–3 set for every task path; the semantics live only in `verification-policy.md → "Verification depth levels"`. Set by `/sdlc`; `/litemode` remains a compatibility alias. Every depth preserves `UI_TESTING`. | Defaulted | Empty / invalid = `standard` |
| `{CAVEMAN}` | `caveman` style auto-activation (`content/skills/caveman/SKILL.md`): `auto` \| `on` \| `off` (details below) | Defaulted | Empty / invalid = `auto` |
| `{METADATA_PREVIEW}` | Wrapper `-Preview` on `Invoke-1CEdit.ps1` before a metadata write: `auto` \| `on` \| `off` (toggled by `/previewmode`; canon — `content/skills/1c-metadata-manage/docs/edit-preview.md → When preview runs`; never relaxes native `-DryRun` / `-Force` on deletions) | Defaulted | Empty / invalid = `auto` — preview only a `-Force` re-compile replacing an existing artifact whole |
| `{AGENT_MODEL}` | Fallback and off switch of the active-model profile layer (`AGENTS.md → Active model adaptation`, `model-adaptation.md → Selecting the profile`): `opus5` \| `sonnet5` \| `fable5` \| `gpt56` \| `gpt6` \| `off`. Read at task time; edited by `/rulesmodel`. | Defaulted | Empty / unrecognised = profile by self-knowledge, or base ruleset |

### `CAVEMAN` — caveman auto-activation

Presentation only — procedure, verification depth and mandatory report structure are unchanged.

- **`auto` (default / empty)** — on for development (writing / editing / refactoring, debugging, deploy, shell), off for analysis / review / documentation.
- **`on`** — active on all tasks (subject to the skill's safety switches).
- **`off`** — no auto-activation; explicit session force still works.

**Precedence:** session force ("caveman please" / "stop caveman" / `/caveman lite|full|ultra`) overrides `.dev.env`; persistent editor — `/caveman on|auto|off` (`content/commands/caveman.md`).

### `METADATA_PREVIEW` — wrapper dry-run before a metadata write

Canonical editor: `/previewmode on|auto|off|once` (`once` = single session-scoped preview). Semantics and rollback boundaries: `content/skills/1c-metadata-manage/docs/edit-preview.md → When preview runs`.

## `CODE_OWNER` — who owns the code

Names the owner of the project's code and so whose rules govern its design. Current models weigh ownership heavily: code presented as theirs gets restructured, code presented as someone else's gets extended as it stands, and a scope rule elsewhere does not cancel an ownership statement. **Install-time selection** with one exception to that class: the installer asks while creating `.dev.env` **and** when an update, add or init finds an existing `.dev.env` without the key. A run where nobody can answer (`-NonInteractive`, redirected console input) writes `user` and reports it. Never asked at task time; a present key is never re-asked or rewritten. Empty / invalid = `user`.

| Value | Meaning |
|---|---|
| `user` (default / empty) | The user owns the code and sets its design. Follow the design and conventions already in the code (`AGENTS.md → Core Principles`); `Surgical Changes` applies as written, and unrelated defects are reported, not fixed. A prompt or subagent brief never presents the code as the agent's. |
| `agent` | The agent owns and maintains the project's own code and sets its design. Within the area the task touches it merges duplicated code, fixes related structure and may replace a local convention it judges wrong; `Surgical Changes` and the cleanup clause of `Simplicity First` yield to this there. Subagent briefs state `CODE_OWNER=agent`; the delivery report lists every change beyond the request. |

**Unchanged under both values:** vendor (typical) code stays the vendor's (`content/rules/dev-standards-change-markers.md`, `AGENTS.md → Skills and Subagents → Vendor support`); whatever `AGENTS.md → Core Principles` says never yields; the hard gates, triage and the validator chain; `CONFUSION` on material forks — a change to existing behaviour or a public contract beyond the request is one; no speculative features, tests, logging or abstractions; confirmation of destructive actions.

## Support-channel parameters

Consumed by `/support`, `/supportstatus` and `/checkupdates` (contract — `support-feedback.md`). The channel is a **hard AND**: a ticket is sent only when `SUPPORT_KEY` **and** `SUPPORT_EMAIL` are both non-empty. Neither is asked at install time — the installer only appends the empty keys, because the key itself ships with the MCP distribution and the e-mail is the user's own.

| Parameter | Effect | Class | Behavior when empty |
|---|---|---|---|
| `{SUPPORT_KEY}` | Shared support key, sent as the `X-Support-Key` header. Ships with the MCP distribution (`config.env`, section 6); a fresh one comes from the personal cabinet at https://vibecoding1c.ru/. **Secret**: never echoed into chat, logs, ticket text, or `context`. | Highly desirable for `/support` | `/support` and `/supportstatus` send nothing and report which of the two values is missing and where to get it. Never invent a key, never borrow one from another project. |
| `{SUPPORT_EMAIL}` | Working e-mail of the ticket author. The operator answers to it; `/supportstatus` filters your tickets by it. | Highly desirable for `/support` | Same as above. The e-mail is the user's own — ask for it only when `/support` is actually being invoked. |
| `{SUPPORT_API_URL}` | Endpoint of the support service. | Defaulted | Empty = `http://104.249.10.238:18082`. Fill in only for a dedicated instance. |

A ticket is created with status `новый` and is moved to `закрыт` by the operator. The whole section is inert for development work: an empty support block blocks no code, review, or infobase task.
