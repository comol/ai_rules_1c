---
description: "OpenSpec integration. Load when working with the openspec/ workspace (specs and change proposals)."
alwaysApply: false
category: integrations
---

# SDD Integration — OpenSpec

[OpenSpec](https://github.com/Fission-AI/OpenSpec) is the only SDD framework supported by this project. Other SDD frameworks (Memory Bank, Spec Kit, TaskMaster, etc.) are **not** supported — do not generate or update artifacts for them, even if the corresponding folders or MCP servers happen to be present.

## Canonical sources

Layout, spec format, delta format, and the full workflow are described in the workspace itself — do not duplicate them here:

| Topic | File |
|-------|------|
| Workspace layout, slash commands, refresh policy | [`openspec/README.md`](../../openspec/README.md) |
| Spec format and conventions for `openspec/specs/` | [`openspec/specs/README.md`](../../openspec/specs/README.md) |
| Change-proposal layout and delta format for `openspec/changes/` | [`openspec/changes/README.md`](../../openspec/changes/README.md) |

Read those files before writing or editing OpenSpec artifacts.

## MCP discipline for OpenSpec authoring

OpenSpec artifacts (`proposal.md`, `design.md`, `tasks.md`, delta specs under `changes/<id>/specs/` and current specs under `specs/`) are Markdown, but they make **factual claims about the 1C system** — metadata names, attributes, tabular sections, public API signatures, БСП subsystem names, platform-version behaviour, project conventions. Every such claim must be grounded in evidence from the relevant MCP tools, not from memory or guessing. This is the **spec-authoring path** from `AGENTS.md → Development Procedure → Triage`.

### Spec size triage

Before any pre-author MCP call, classify the change. The evidence depth depends on the class — applying the full evidence set to a one-button change is the most common source of context bloat.

- **quick-spec** — change touches **one** existing metadata object **plus**, optionally, 1-3 independent isolated additions (a new constant, a new data processor / settings form, a new independent information register with no module). No new documents / accumulation or accounting registers / roles / event subscriptions / scheduled jobs. No changes to existing transactional paths, RLS conditions, posting code, or public common-module signatures. Naming of new objects is the only architecturally novel decision.
  *Evidence minimum:* targeted attribute check via `resolve_qualified_name` or `search_metadata` JSON template (see check 2 below) **plus** one `ssl_search` if the spec relies on a БСП subsystem **plus** `recall` only if the change keywords overlap with prior project work. `Context sources` block — one line.
- **full-spec** — everything else: new transactional code paths, new registers / documents / roles, modifications to existing posting or write paths, public API signatures, БСП-subsystem integrations beyond a single known API, cross-module impact, performance NFRs, security / PII handling beyond a whitelist. Run the full `Mandatory pre-author checks` below.

When in doubt — quick-spec wins until the second novel architectural decision shows up; then promote to full-spec.

### Mandatory pre-author checks

These checks operate under `AGENTS.md → Tooling & Standards → C` (no duplication, no blind chaining, no defensive calls). **The presumption is in favour of skipping** — include a check only when it materially closes a gap that will affect a concrete `### Requirement:` in the spec. Per `AGENTS.md → A.3`, the `Context sources` block briefly notes any check that **was normally relevant for the change class but deliberately skipped** (one short sentence — see the block format below); checks that fall outside the class baseline (e.g. `recall` on a greenfield topic in a quick-spec) need no mention at all.

Apply these to **full-spec** changes (the `Evidence minimum` of `quick-spec` is enough for quick changes). Run **before** writing the artifact, not after.

1. **Project memory — `1c-templates-mcp` `recall`.** Run when the change keywords overlap with anything already touched in the project: existing object names (`НачислениеЗарплаты`, `ПродажиТовары`), known subsystems (`Документооборот`, `ИнтернетПоддержка`), recurring error messages, prior architectural decisions on the same domain. For genuinely greenfield topics — a domain the project has never touched — `recall` is optional; a single short note in `Context sources` ("`recall` skipped: greenfield topic") is enough. Catches existing project conventions, prompt templates, naming quirks, settled architectural choices.
2. **Metadata facts — prefer targeted queries over full dossiers.** Choose the narrowest method that closes the gap:
   - **Single attribute / tabular-section column existence and type** — `resolve_qualified_name "Документ.<Name>.Реквизит.<Attr>"` (one call, minimal output) or `search_metadata {"operation": "get_attribute_type", ...}`. Use this for "does object X have attribute Y of type T?" — by far the most common case.
   - **List of attributes / tabular parts / dimensions / resources / forms** — `search_metadata` JSON templates: `list_attributes`, `list_tabular_parts`, `list_dimensions`, `list_resources`, `list_forms`, `list_enum_values`, `object_structure`, `list_attributes_with_type`. Deterministic, no LLM, much smaller payload than a dossier.
   - **Structural passport across many facets** — `get_object_dossier object_name=... sections=["structure"]` (or `["structure","dependencies"]`, …). Use the `sections` filter to drop unused facets. Default (all sections) is a last resort for objects the session has never inspected.
   - **Fallback chain on empty / non-actionable results** — `1c-code-metadata-mcp` hybrid → `grep=true` retry → `Grep` (per `AGENTS.md → Tooling & Standards → A.4`).
   Do not invent attribute names from analogous documents or from memory.
3. **Platform APIs — `1C-docs-mcp` (`docinfo`, `docsearch`) and ITS (`its_help` → `fetch_its`).** Every platform type, method, or behaviour the spec relies on (`HTTPСоединение`, `ЗащищённоеСоединениеOpenSSL`, `ЗаписатьJSON` / `ПрочитатьJSON`, `ДлительныеОперации`, async / `Ждать`, role permissions, etc.) — verify the exact name, signature, and version availability against the project's `CompatibilityMode` **when the spec is normative about that API**. Memory-written API signatures are not evidence. Skip for hrestomatic APIs whose shape is fixed across all supported versions and where the spec does not pin a specific signature.
4. **БСП / SSL — `1c-ssl-mcp` (`ssl_search`).** When the spec mentions integrating with a БСП subsystem (`Администрирование`, `ИнтернетПоддержкаПользователей`, `ПолучениеФайловИзИнтернета`, `ЦифроваяПодпись`, `ДлительныеОперации`, `ОчередьЗаданий`, `БезопасноеХранилище`, `ЗащитаПерсональныхДанных`, …), confirm the subsystem actually exists in this project's БСП version, its real name in this configuration, and which public API to call. Verify the БСП hook (`ПриОпределенииПодсистемСКоторымиВозможнаИнтеграция`, `ПриДобавленииЭлементовФормы`, etc.) exists in this БСП version. **Required without exception when the change introduces storage of secrets, tokens, or API keys** (confirm `БезопасноеХранилище` shape) **or touches personal data** (confirm `ЗащитаПерсональныхДанных` hooks).
5. **Project source patterns — `search_code` / `codesearch` / `search_function`.** When the spec proposes a new module, function, or pattern, check whether the project already has a similar one to align naming, signature, and placement. Skip when the new code has no analog in the project (genuinely first-of-its-kind).

**Stop criterion.** Once every `### Requirement:` in the planned spec can be written with concrete object names, attribute names, БСП API names, and platform types — without any `<TBD>` or "to clarify" placeholders — stop calling MCP and start writing. Additional calls are allowed only if a specific gap surfaces during drafting. Repeating a check "just to be safe" violates `AGENTS.md → Tooling & Standards → C.1`.

### Forbidden in OpenSpec artifacts

- **TODO / "to be clarified" / "уточнить" for a fact one MCP call closes.** If you can answer it now via `recall` / `resolve_qualified_name` / `search_metadata` / `docinfo` / `ssl_search`, do it now. A TODO is allowed only for facts that genuinely depend on a human decision (business rule, naming preference, priority).
- **Invented metadata or attribute names.** No `Документ.НачислениеЗарплаты.Реквизит` value without metadata confirmation. No tabular-section column name without confirmation.
- **Platform-API signatures written from memory** when the spec is normative (design.md decisions, tasks.md acceptance criteria). Cite the verified source.
- **Cross-version assumptions without `CompatibilityMode` check.** If the spec assumes 8.3.21+ behaviour (async HTTP, `Ждать`, OpenSSL secure connections, structured logging), confirm `openspec/project.md` / `.dev.env` actually targets that version, or scope the spec to the version that is in force.
- **Defensive MCP calls without a concrete gap.** Calling `get_object_dossier` "for completeness" when a single `resolve_qualified_name` would close the only open question — same defect as a missing call.

### Context sources block — compact, evidence-only

At the end of every non-trivial OpenSpec artifact you author or substantially modify (`proposal.md`, `design.md`, `tasks.md`, delta `specs/`), append a short `## Context sources` block. It lists what was actually used and what each call closed, plus a one-sentence note for any check that **was normally relevant for the change class but deliberately skipped**. Out-of-class checks (e.g. БСП check on a change that touches no БСП subsystem) get no mention. **No MCP server names when they are obvious from the tool name, no narration, no "Skipped: X — irrelevant scope" filler for tools that were never going to be called.**

Compact form — preferred default, fits most quick-spec and small full-spec changes:

```markdown
## Context sources
Verified via MCP: `Документы.НачислениеЗарплаты.Комментарий` (Строка, 1024); БСП `ДлительныеОперации` v3.1.10; БСП `БезопасноеХранилище` available.
```

Multi-line form — only when more than 5 confirmations are listed, or when a single confirmation requires a comment (version incompatibility, non-standard behaviour, deliberate scoping). Group by what was confirmed, not by which tool returned it:

```markdown
## Context sources

- Metadata: `Документы.НачислениеЗарплаты.Комментарий` (Строка, 1024); standard `Дата`, `Организация`, `МесяцНачисления` present.
- БСП: `ДлительныеОперации` v3.1.10, `БезопасноеХранилище` v3.1.10 — both available in target version.
- Platform: `HTTPСоединение.ОтправитьДляОбработки` available at `CompatibilityMode=Версия8_3_21`.
- Project memory: no prior notes on AI / OpenAI integration in this configuration (greenfield).
```

This block is the artifact-level analogue of the "list context sources actually used" rule from `AGENTS.md → Tooling & Standards → A.3`. Its absence on a non-trivial spec is a defect, the same way a missing `syntaxcheck` run is a defect for BSL changes. Bloating it with skipped-tool entries or per-call narration is the opposite defect — it carries noise into every downstream phase that re-reads the artifact.

### Subagent obligations

The subagents that own OpenSpec artifacts (`1c-analytic`, `1c-architect`, `1c-planner`, `1c-explorer` — see the mapping table below) inherit this discipline. Their prompts in `content/agents/` do not have to repeat these rules; they are bound by this file and by `AGENTS.md`. A subagent that delivers a non-trivial spec without the `Context sources` block, or with a TODO that an exposed MCP tool could have closed, has failed the same way a developer subagent fails if it skips `syntaxcheck`.

## Question-asking discipline across phases — overview

Clarification questions must be **front-loaded** into the propose phase, with a single consolidated preflight round at the start of apply, and effectively zero questions during the apply implementation loop. This is the inverse of the "ask whenever in doubt" default — by the time code is being written, the user must not be paying a clarification tax that should have been paid at design time.

| Phase | When to ask | When NOT to ask |
|---|---|---|
| **Propose** (`/opsx:propose`, exploration, requirements / design / planning subagents) | **Aggressively** — every architectural decision, naming choice, scope ambiguity, error-handling strategy, transactional boundary, library / БСП subsystem choice, settings storage, role / permission shape, performance NFR. Pin them in `proposal.md` / `design.md` **now**. | Almost never. The only acceptable "no question" cases are: the answer is already in `openspec/specs/**` / `memory.md` / `.dev.env`; the answer can be derived from one MCP call (then make the call); the user explicitly said "you decide". |
| **Apply preflight** (single round at the start of `/opsx:apply`, before any code is written) | **In one consolidated batch** — every `.dev.env` field needed by tasks in the current session **and** every legitimate `design.md → ## Open Questions` item whose dependent task is in the current session. One round, all questions together. | Anything answered in `proposal.md` / `design.md` / delta `specs/` / `tasks.md` — those decisions are locked. Anything banned by the "Banned questions at apply time" hard list below. Anything outside the scope of the **current** apply session. |
| **Apply loop** (mid-implementation, between `tasks.md` items) | **Only in critical cases** — a new fact surfaces from the live state that conflicts with a locked artifact decision (metadata missing, platform-version mismatch with `CompatibilityMode`, БСП subsystem absent, typical-form structure blocks the planned approach). Frame it as a `CONFUSION` block per `AGENTS.md → 1.` and pause. | Routine ambiguity in a task description, default value selection, name choice, "did you mean X or Y" — these are propose-time / preflight defects, not apply-time questions. If such a gap shows up mid-loop, treat it as a defect of the upstream phase, not as a license to interrupt the user. |

The remainder of this section spells out each phase. The hierarchy is non-negotiable: a question that **could** have been asked in propose, and **could** have been batched into preflight, **must not** be asked mid-loop.

## Propose-phase clarification discipline

`/opsx:propose` (and the requirements / design / planning subagents — `1c-analytic`, `1c-architect`, `1c-planner`) is the phase where every clarifiable decision **must** be settled. Apply phase is not the time for clarifications. The user round-trip cost is the same whether the question is asked now or later, but settling it now keeps the implementation aligned with a written, reviewable artifact instead of with a forgotten chat exchange.

### Ask now, do not defer

The default "If context is critically unclear, ask the user — but prefer making reasonable decisions to keep momentum" guidance from the upstream OpenSpec CLI is **overridden** for this project. The substitute rule:

- **If the decision is architecturally meaningful and ambiguous — ask the user now.** Architecturally meaningful = the choice changes `design.md → ## Architecture decisions`, the shape of a delta spec requirement, the public signature of a common-module export, the placement (main configuration vs. extension), the storage of secrets / settings, the transactional boundaries, the error-handling pattern, the logging strategy, the БСП subsystem to integrate with, the platform-version target.
- **If the decision is a default that the user is unlikely to care about — pin it in `design.md` with a one-line rationale, then proceed.** Examples: cache-eviction policy when no NFR exists, name of a private helper function, internal split between two service modules.
- **If the decision depends on a 1C fact that one MCP call could close — make the call, do not ask.** The user is not a substitute for `resolve_qualified_name` / `search_metadata` / `ssl_search` / `recall`.

When you must ask, use the `CONFUSION` format from `AGENTS.md → Development Procedure → 1. Think Before Coding`. List options with trade-offs; do not paraphrase the question into prose.

### Pre-finalization clarification gate

**Before declaring "All artifacts created! Ready for implementation."**, the agent (or driving subagent) must run a final consolidation pass:

1. Re-read every `### Requirement:` in delta `specs/` and every decision in `design.md`. For each one, check: does the implementer need any additional input from the user to write the code that satisfies this requirement / decision? If yes, add it to a single batched question list.
2. Re-read `proposal.md → Constraints` / `Out of scope` / `Non-goals`. For each scope edge, check: is the edge ambiguous enough that an implementer might cross it accidentally? If yes, sharpen the wording or batch a clarification.
3. Re-read `tasks.md`. For each task, ask: can the implementer execute this task from the current artifacts alone, without a follow-up question to the user? Any "no" → batch the missing input.
4. Re-read `design.md → ## Open Questions`. **This list is the only legitimate apply-time question surface.** Anything that lands here is a promise that the user will be asked again at apply time when the dependent task is next. If a question can be closed now, close it now and remove it from `## Open Questions`. Leave only items that genuinely depend on later facts (e.g. a value that depends on production data not yet available).
5. If the batched question list is non-empty — present it to the user in one consolidated `AskUserQuestion` round (open-ended for free-text answers, preset options where applicable). Apply the answers to the artifacts. Then re-run the gate. Repeat until the batched list is empty.

Only after this gate passes — empty batched list, every artifact internally consistent, `## Open Questions` only contains genuine human-decision-at-later-time items — may the agent emit the "Ready for implementation" message.

### Forbidden in proposal artifacts

These shortcuts smuggle apply-phase questions into the future and must not appear in `proposal.md` / `design.md` / `tasks.md` / delta `specs/`:

- "TODO: clarify with the user during apply" / "уточнить при реализации" — every such marker is an admission that the propose phase failed. Either decide now with the user, or capture the decision as a numbered item in `design.md → ## Open Questions` with the exact text of the future question, the artifact section it will update, and the task ID that depends on it.
- "We'll decide once we see the code" / "будем смотреть по ходу" — almost never legitimate. If the decision genuinely depends on the live state, write down the **trigger condition** (e.g. "if `Документы.<Name>.<Attr>` resolves to type X then path A, else path B") instead of leaving it open.
- Vague verbs in delta `### Requirement:` blocks — "appropriately", "if needed", "as required", "по необходимости", "при необходимости". They each hide a question. Replace with concrete criteria or escalate to a clarification round.
- Phantom defaults — listing two equally weighted options ("Cache size: 100 or 500") without a written rationale for the default. Pick one, write the rationale in `design.md`, move on.

The presence of any of the above in a finalized artifact is a propose-phase defect of the same severity as a missing `Context sources` block.

### Open Questions discipline

`design.md → ## Open Questions` is the **only** allowed bridge from propose to apply. Use it sparingly:

- One numbered list item per question, with: the exact question text, the trade-offs (≥2 options with consequences), the artifact section that will be updated once answered, the task ID(s) that depend on the answer.
- An item belongs here only if **all** of: the question cannot be closed by any MCP call currently exposed; the question cannot be closed by the user at propose time because the answer genuinely depends on facts that surface later (production data, performance measurements, a not-yet-implemented module's actual shape); leaving it open does not block authoring the rest of the spec.
- "I forgot to ask" / "user wasn't sure yet" / "let's see what apply finds" — **not** legitimate reasons to land here. Those are propose-phase failures.

Items in `## Open Questions` are the legitimate apply-time question surface — and only those items. At apply time, the agent asks them in the preflight round (see below) when their dependent tasks enter the current session, **not** during the implementation loop.

## Apply-phase clarification discipline

`/opsx:apply` runs against an already-approved set of artifacts (`proposal.md`, `design.md`, `tasks.md`, deltas under `changes/<id>/specs/`). **Their decisions are locked.** Apply implements them, it does not re-litigate them.

The recurring failure mode at apply time is the parent agent re-asking the user about choices that `design.md` or `proposal.md` already records — placement (main configuration vs. extension), provider, data scope, settings storage, key handling, transactional boundaries, error-handling pattern, logging strategy. Each such re-ask wastes a user round-trip, drifts the implementation away from the agreed design, and signals that the artifacts are not trusted as the source of truth.

The second recurring failure mode is dribbling questions across the implementation loop — one question between tasks 2 and 3, another between tasks 5 and 6 — each pretending to be "just one quick clarification". The user is forced into N micro-rounds where a single batched preflight round at the start would have done the same job in one. The apply-phase rule is therefore: **one consolidated preflight round upfront, then mid-loop silence except for true live-state surprises.**

### Read first, then ask

`/opsx:apply` step 4 already mandates reading the context files (`proposal.md`, `design.md`, `tasks.md`, current deltas). **Use them.** Before raising any clarification at apply time, check whether the question is already answered:

- a stated decision in `design.md` (architecture, placement, storage choice, transactional boundaries, error-handling pattern, logging strategy, library / БСП subsystem) — **locked**;
- a stated requirement in a delta `spec.md` (`### Requirement:` block, scenarios) — **locked**;
- a stated `Out of scope` / `Non-goals` / `Constraints` line — **locked**;
- a stated provider / library / default in `proposal.md` (including default values for empty optional parameters) — **locked**;
- the `## Open Questions` block in `design.md` — **only those** items are legitimate apply-time questions, and only when the implementation step that depends on them is actually next on the queue.

If the answer is in the artifacts, do not ask. Quote the locked decision in one line ("`design.md → ## Architecture decisions → "Размещение в основной конфигурации"` — proceeding accordingly") and continue. Disagreeing with a locked decision is **not** a clarification — it is a request to amend `design.md` / `proposal.md`, and the user must explicitly authorize the amendment before any implementation deviates from the artifact.

### Preflight round (single consolidated batch at apply start)

Immediately after `/opsx:apply` step 4 (read context files) and **before** any code is written, the agent runs a **single** preflight round that consolidates every remaining legitimate question into one `AskUserQuestion` call. This is the **only** apply-time surface for non-critical questions. Everything that does not surface in preflight is committed to silence for the rest of the session.

Preflight scope — what goes in the single round:

- **Every empty highly-desirable `.dev.env` field that is required by a task in the current session's plan.** Aggregate them all into the same round. Skip fields needed only by tasks the current session will not reach (defer those task blocks instead — see "Banned questions" below).
- **Every `design.md → ## Open Questions` item whose dependent task is in the current session's plan.** Quote the item verbatim, then add a `CONFUSION` block per `AGENTS.md → 1.` with options and consequences. The agent's recommendation is allowed inside the block, but it does not substitute for the user's choice.
- **Nothing else.** If a candidate question does not fit one of the two buckets above, it does not belong in preflight — it either belongs in propose-phase (where the propose-phase clarification gate should have caught it; missing it is a propose defect, not an apply ask) or it does not belong anywhere (banned-questions hard list, defaulted fields, advisory fields).

Preflight format — the opening message of `/opsx:apply` follows the template in `### Apply-phase opening template (default)` below. The preflight round corresponds exactly to the `## Genuine blockers` block of that template. If `## Genuine blockers` is empty, **there is no preflight round at all** — proceed straight to implementation.

After the user answers the preflight round, apply the answers (update `.dev.env`, write the resolved Open Question into `design.md → ## Architecture decisions` and strike it from `## Open Questions`), then enter the implementation loop. **The implementation loop has no more `AskUserQuestion` calls** except for the narrowly-defined critical exceptions in the next subsection.

### Legitimate apply-phase pauses

A pause-and-ask **during the implementation loop** (after preflight) is justified **only** when one of the following holds:

- **New fact surfaced from the live state** — the implementation revealed something not foreseen at design time and not catchable in preflight: a metadata object missing from this configuration, a platform-version mismatch with `CompatibilityMode`, a typical-form structure that blocks the planned approach, a БСП subsystem missing in this configuration, an attribute or tabular section whose actual type contradicts what `design.md` assumed. State the new fact and its conflict with the artifact concretely as a `CONFUSION` block per `AGENTS.md → 1.`, not a generic clarification. This is the **only** routine reason to pause mid-loop.
- **User-explicit re-open** — the user asks to revisit a previously locked decision.

That is it. Two categories. Everything else that previously looked like a legitimate mid-loop pause must now be handled differently:

- **Empty highly-desirable `.dev.env` field needed by a task that is no longer the next step** (the preflight round either resolved it or deferred the dependent block). If a task that depends on a deferred field becomes "next" because earlier tasks completed faster than expected, **defer that task** rather than pausing — mark it `deferred-to-user` in `tasks.md`, continue with the remaining tasks, and surface the deferred block once at the end of the session in the closing summary. Do not pause to re-ask about a value that the user already declined to provide in preflight.
- **`design.md → ## Open Questions` item that was not in the preflight round because its dependent task was not in the session plan, but a later task on the queue triggered it.** If you genuinely could not have foreseen this at preflight time, raise a `CONFUSION` block now — but this is rare; almost always the original session plan was wrong. The correct response is to widen the preflight scope on the next apply session, not to make a habit of mid-loop pauses.
- **Routine task ambiguity** ("what name should I use for this private helper?", "should this be a function or a procedure?", "what level of logging here?") — **never** a legitimate mid-loop pause. These are propose-phase defects: the design did not pin enough. Make a reasonable choice consistent with the codebase, log it as a `Captured during work` note in `memory.md` or via `remember`, and move on. The user did not sign up for a clarification on every line.

Anything outside the two narrowly-defined categories above is an apply-phase defect, equivalent to skipping `syntaxcheck` after a BSL edit.

### Forbidden at apply time

- Re-asking about provider / trigger / data scope / settings storage / placement / key storage / module placement / role grants / БСП subsystem / transactional boundaries when the question is settled in `proposal.md` or `design.md`.
- Bundling a `.dev.env` audit with locked-decision re-ask — they are different gates and must be split. The `.dev.env` audit asks about empty fields **only**.
- Asking "what to do with default X" when `design.md` already names the default. Use the named default.
- Pausing on a non-blocking item just to "confirm" — confirmation is not a question. If the artifact says X, do X.
- Asking the user to choose between options A / B / C when `design.md → ## Architecture decisions` already picked one of them with a written rationale — the choice is closed, the rationale is the answer.
- **Closing an item from `design.md → ## Open Questions` with a self-justifying paragraph instead of a `CONFUSION` block.** Open Questions are by definition unresolved at design time; the agent does not have authority to close them unilaterally. A 1-2 paragraph rationale that picks an option (even a "minimal and reversible" one) is a defect of the same severity as bypassing `syntaxcheck`, and is doubly so when the picked option modifies typical (standard) configuration objects (typical roles, typical forms, typical modules, typical event subscriptions). The only legitimate closure path is a `CONFUSION` block per `AGENTS.md → 1. Think Before Coding`, followed by the user's explicit choice. Implementation of the dependent task block does not start until that choice arrives.

### Banned questions at apply time — hard list

These questions MUST NEVER be asked during `/opsx:apply`, regardless of whether the corresponding `.dev.env` field is empty. Asking any of them is an apply-phase defect of the same severity as skipping `syntaxcheck` after a BSL edit. The fallback is documented and applied silently — no question, no pause, no `AskUserQuestion` round.

| Banned question | Why banned | What to do instead |
|---|---|---|
| "What value should I use for `PREFIX`?" / asking the user to pick a prefix | `PREFIX` is **Advisory** per `dev-standards-core.md §1`. Empty value is silently valid. | Apply the documented fallback: create new objects without a prefix; `{PREFIX}` placeholder in templates resolves to empty string. Do not announce the fallback either — just proceed. |
| "What value should I use for `COMPANY`?" / asking for company name for modification markers | `COMPANY` is **Advisory**. Empty = no markers. | Skip emitting `// +++ {COMPANY}; …` / `// --- {COMPANY}; …` markers entirely. Procedure / module headers remain per `dev-standards-core.md §3` only when also non-empty. |
| "What value should I use for `DEVELOPER`?" / asking for developer ID / FIO | `DEVELOPER` is **Advisory**. Empty = no markers. | Same as `COMPANY`: no markers. Do not invent a placeholder developer name. |
| "What `{TASK}` number should I use for the modification comment?" | `{TASK}` is only required when markers are emitted. With empty `COMPANY` / `DEVELOPER` markers are not emitted at all. | Do not ask. If markers ARE being emitted (both `COMPANY` and `DEVELOPER` non-empty) and `{TASK}` is the only missing piece — ask once for `{TASK}` only, never bundled with the three Advisory fields. |
| "Should I pause now to get `INFOBASE_PATH` for the deploy block later?" | `INFOBASE_PATH` is **Highly desirable** — but only when an IB-bound command is the **next** step. Asking it pre-emptively when deploy / smoke-test tasks are 3-5 steps away is premature. | Skip the deploy block silently — mark its tasks as `deferred-to-user` in `tasks.md`, finish all non-IB-bound tasks first, then in the closing summary state once that the deploy block is deferred until `INFOBASE_PATH` is provided. Do not stop earlier tasks. |
| Same for `PLATFORM_PATH` / `INFOBASE_PUBLISH_URL` when no IB-bound or UI-test step is **next** on the queue | Same rationale — premature. | Same: defer the dependent task block, proceed with everything else. |
| "Should I ask the user to fill in `IB_USER` / `IB_PASSWORD` / `LOG_PATH` before running the IB-bound block?" | These three are **Defaulted** per `content/rules/dev-standards-core.md §1`. Empty `IB_USER` / `IB_PASSWORD` = no authentication / no password (the `/N` / `/P` flags are simply omitted, fully valid for dev / test infobases); empty `LOG_PATH` = `$env:TEMP\1cv8.log`. | **Do not ask, ever** — apply the documented defaults silently. Re-ask `IB_USER` / `IB_PASSWORD` only if the IB-bound command later returns an authentication error; re-ask `LOG_PATH` only if the resolved path turns out to be non-writable. |

If the artifact (`design.md` / `proposal.md`) explicitly **requests** a prefix / a marker style / a specific developer name (overriding the global `.dev.env` default), follow the artifact — that is a locked decision, not a question. The ban above only covers asking the user **at apply time** when the value is empty in `.dev.env` and no artifact pins it.

The opening message of `/opsx:apply` therefore lists only **genuine** blockers in the `## Genuine blockers` block; if every "blocker" candidate falls into the banned list above, the block is empty and the agent proceeds straight to implementation.

### Apply-phase opening template (default)

To make the discipline above mechanical, the parent agent's first message at `/opsx:apply` follows this structure. The `## Genuine blockers` block **is** the preflight round — its items are the entire apply-time question surface for the session.

```text
Using change: <name>.

## Locked from artifacts (proceeding without re-asking)
- <decision>: <one-line value> — `<file>:<section>`
- ...

## Plan for this session
- <ordered list of task ids that will be executed in this run>

## Genuine blockers (preflight — single consolidated round)
- <empty .dev.env field needed by a task in this session's plan> — required by tasks <ids>
- <design.md Open Question whose dependent task is in this session's plan> — CONFUSION block (quote question + list options with consequences + the agent's recommendation + "→ Which one to pick?")
- ...
```

Rules for the template:

- **`## Locked from artifacts`** is non-negotiable — its absence on a non-trivial `/opsx:apply` is a defect. List the architectural / placement / scope / storage / library / БСП decisions that `design.md` and `proposal.md` already pin, with their source location.
- **`## Plan for this session`** precedes `## Genuine blockers` because the plan defines the scope of "questions that matter now". Questions about tasks outside the plan do not belong in preflight.
- **`## Genuine blockers`** holds **all** legitimate apply-time questions in a single batch. After this round, the implementation loop is silent except for the two critical exceptions above.
- If `## Genuine blockers` is empty after the preflight scope is correctly applied (banned-questions filter, defaulted-fields filter, in-session-plan filter), **omit the block entirely** and proceed straight to implementation. An empty block is not a question.

## Subagent → OpenSpec artifact mapping

Each subagent owns specific OpenSpec artifacts. Use this table to decide where a given subagent must write.

| Subagent | Reads | Writes |
|----------|-------|--------|
| **1c-explorer** | `specs/`, current codebase, metadata graph | read-only findings for `proposal.md`, `design.md`, or `tasks.md` authors; no artifact writes |
| **1c-analytic** | existing `specs/` for context | `changes/<id>/proposal.md`, new entries under `specs/` (via deltas) |
| **1c-planner** | `specs/`, `changes/<id>/proposal.md`, `design.md` | `changes/<id>/tasks.md` |
| **1c-architect** | `specs/`, `changes/<id>/proposal.md` | `changes/<id>/design.md` |
| **1c-arch-reviewer** | `changes/<id>/design.md`, `proposal.md`, `specs/` | review notes (no artifact writes) |
| **1c-developer** | `specs/`, active `changes/<id>/` | code; updates `changes/<id>/specs/` deltas and ticks `tasks.md` |
| **1c-metadata-manager** | `specs/`, active `changes/<id>/` | metadata XML/forms; spec deltas under `changes/<id>/specs/` for new/changed metadata objects |
| **1c-refactoring** | `specs/`, active `changes/<id>/` | code; updates deltas only when observable behaviour changes |
| **1c-performance-optimizer** | `specs/` (NFR/perf requirements) | code; deltas only when a perf NFR changes |
| **1c-error-fixer** | active `changes/<id>/` | code; usually no spec changes (bug fix preserves intended behaviour) |
| **1c-tester** | `specs/` (scenarios), `changes/<id>/tasks.md` | test results, ticks in `tasks.md` |
| **1c-code-reviewer** | `specs/`, `changes/<id>/specs/` deltas | review verdict against requirements (no artifact writes) |
| **1c-doc-writer** | `specs/`, `changes/archive/` | user-facing docs derived from specs |

## Phase → subagent mapping

The default `propose → apply → archive` workflow maps to subagents as follows:

| Phase | Driver subagent(s) | Output |
|-------|-------------------|--------|
| Exploration | `1c-explorer` when broad code / metadata context is needed | read-only findings for the next phase |
| Requirements | `1c-analytic` | `proposal.md` + initial deltas under `changes/<id>/specs/` |
| Design | `1c-architect` (optionally reviewed by `1c-arch-reviewer`) | `design.md` |
| Planning | `1c-planner` | `tasks.md` |
| Implementation | `1c-developer`, `1c-metadata-manager`, `1c-refactoring`, `1c-performance-optimizer`, `1c-error-fixer` | code + updated deltas + ticked `tasks.md` |
| Verification | `1c-tester`, `1c-code-reviewer` | test results, review verdict |
| Documentation & archive | `1c-doc-writer`, then `/opsx:archive` | user docs; deltas merged into `specs/`, change moved to `changes/archive/` |
