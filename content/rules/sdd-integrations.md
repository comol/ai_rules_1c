---
description: "OpenSpec integration. Load when working with the openspec/ workspace (specs and change proposals)."
alwaysApply: false
category: integrations
---

# SDD Integration — OpenSpec

[OpenSpec](https://github.com/Fission-AI/OpenSpec) is the only SDD framework supported by this project. Do not generate or update artifacts for other SDD frameworks (Memory Bank, Spec Kit, TaskMaster, …), even if their folders or MCP servers happen to be present.

## Canonical sources

Layout, spec format, delta format, and the full workflow are described in the workspace itself — do not duplicate them here:

| Topic | File |
|-------|------|
| Workspace layout, slash commands, refresh policy | [`openspec/README.md`](../../openspec/README.md) |
| Spec format and conventions for `openspec/specs/` | [`openspec/specs/README.md`](../../openspec/specs/README.md) |
| Change-proposal layout and delta format for `openspec/changes/` | [`openspec/changes/README.md`](../../openspec/changes/README.md) |

Read those files before writing or editing OpenSpec artifacts.

## MCP discipline for OpenSpec authoring

OpenSpec artifacts (`proposal.md`, `design.md`, `tasks.md`, delta and current specs) are Markdown, but they make **factual claims about the 1C system** — metadata names, attributes, tabular sections, public API signatures, БСП subsystems, platform-version behaviour, project conventions. Every such claim must be grounded in MCP evidence, not memory or guessing. This is the **spec-authoring path** from `AGENTS.md → Development Procedure → Triage`.

### Spec size triage

Classify the change before any pre-author MCP call — evidence depth depends on the class; applying the full evidence set to a one-button change is the most common source of context bloat.

- **quick-spec** — touches **one** existing metadata object plus, optionally, 1-3 independent isolated additions (a constant, a data processor / settings form, an independent information register with no module). No new documents / accumulation or accounting registers / roles / event subscriptions / scheduled jobs; no changes to existing transactional paths, RLS conditions, posting code, or public common-module signatures; naming of new objects is the only architecturally novel decision.
  *Evidence minimum:* targeted attribute check (`resolve_qualified_name` or a `search_metadata` JSON template — check 2 below) **plus** one `ssl_search` if the spec relies on a БСП subsystem **plus** `recall` only if the change keywords overlap prior project work. `Context sources` block — one line.
- **full-spec** — everything else: new transactional code paths, new registers / documents / roles, modified posting or write paths, public API signatures, БСП integrations beyond a single known API, cross-module impact, performance NFRs, security / PII handling. Run the full pre-author checks below.

When in doubt — quick-spec wins until the second novel architectural decision shows up; then promote to full-spec.

### Mandatory pre-author checks

Run **before** writing the artifact, under `AGENTS.md → MCP Tool Calling → C` (no duplication, no blind chaining, no defensive calls). **The presumption is in favour of skipping** — include a check only when it materially closes a gap that affects a concrete `### Requirement:`. Per `AGENTS.md → A.3`, the `Context sources` block briefly notes (one short sentence) any check that was normally relevant for the change class but deliberately skipped; out-of-class checks need no mention.

1. **Project memory — `recall`** (`1c-templates-mcp`) — when the change keywords overlap anything already touched in the project: existing object names, known subsystems, recurring error messages, prior decisions on the same domain. Greenfield topics: optional; a short "`recall` skipped: greenfield topic" note is enough.
2. **Metadata facts — narrowest query first.** Single attribute / column existence and type — `resolve_qualified_name "Документ.<Name>.Реквизит.<Attr>"` or `search_metadata {"operation": "get_attribute_type", ...}` (by far the most common case). Lists of attributes / tabular parts / dimensions / resources / forms — `search_metadata` JSON templates (`list_attributes`, `object_structure`, `list_enum_values`, …): deterministic, much smaller payload than a dossier. Multi-facet passport — `get_object_dossier` with a `sections` filter; the all-sections default is a last resort. On empty / non-actionable results — fallback chain per `AGENTS.md → A.4`. Never invent attribute names from analogous documents or from memory.
3. **Platform APIs — `docinfo` / `docsearch` (`1C-docs-mcp`), ITS `its_help` → `fetch_its`.** Verify the exact name, signature, and version availability against the project's `CompatibilityMode` for every platform type / method the spec is normative about. Skip for hrestomatic APIs whose shape is fixed across supported versions when the spec does not pin a signature.
4. **БСП / SSL — `ssl_search` (`1c-ssl-mcp`).** When the spec mentions a БСП subsystem: confirm it exists in this project's БСП version, its real name in this configuration, and which public API / hook to call. **Required without exception** when the change stores secrets / tokens / API keys (confirm `БезопасноеХранилище`) or touches personal data (confirm `ЗащитаПерсональныхДанных`).
5. **Project source patterns — `search_code` / `codesearch` / `search_function`.** When the spec proposes a new module, function, or pattern — align naming, signature, and placement with an existing analog. Skip when genuinely first-of-its-kind.

**Stop criterion.** As soon as every `### Requirement:` can be written with concrete object, attribute, БСП, and platform names — no `<TBD>`, no "to clarify" — stop calling MCP and start writing. Additional calls only when a specific gap surfaces during drafting; repeating a check "just to be safe" violates `AGENTS.md → C.1`.

### Forbidden in OpenSpec artifacts

- **TODO / "to be clarified" / "уточнить" for a fact one MCP call closes.** Close it now. A TODO is allowed only for facts that genuinely depend on a human decision (business rule, naming preference, priority).
- **Invented metadata or attribute names** — nothing lands without metadata confirmation.
- **Platform-API signatures written from memory** where the spec is normative — cite the verified source.
- **Cross-version assumptions without a `CompatibilityMode` check** — if the spec assumes 8.3.21+ behaviour (async HTTP, `Ждать`, OpenSSL, structured logging), confirm the target version or scope the spec to the version in force.
- **Defensive MCP calls without a concrete gap** — a dossier "for completeness" when one `resolve_qualified_name` closes the only open question is the same defect as a missing call.

### Context sources block — compact, evidence-only

Every non-trivial artifact you author or substantially modify ends with a short `## Context sources` block: what was actually confirmed, plus a one-sentence note per deliberately skipped in-class check. No server names when obvious from the tool name, no narration, no "Skipped: X — irrelevant scope" filler.

Compact form — the default:

```markdown
## Context sources
Verified via MCP: `Документы.НачислениеЗарплаты.Комментарий` (Строка, 1024); БСП `ДлительныеОперации` v3.1.10; БСП `БезопасноеХранилище` available.
```

Multi-line form — only when more than 5 confirmations are listed or one confirmation needs a comment (version incompatibility, deliberate scoping); group by what was confirmed, not by which tool returned it.

A missing block on a non-trivial spec is a defect, the same way a missing `syntaxcheck` run is a defect for BSL; bloating it with skipped-tool noise is the opposite defect.

### Subagent obligations

The subagents that own OpenSpec artifacts (`1c-analytic`, `1c-architect`, `1c-planner`, `1c-explorer` — mapping below) inherit this discipline via this file and `AGENTS.md`; their prompts do not repeat it. Delivering a non-trivial spec without the `Context sources` block, or with a TODO an exposed MCP tool could have closed, is a failure.

## Question-asking discipline across phases — overview

Clarification questions are **front-loaded** into propose, batched into a single preflight round at apply start, and near-zero during the apply loop. By the time code is being written, the user must not be paying a clarification tax that belonged at design time.

| Phase | Ask | Do NOT ask |
|---|---|---|
| **Propose** (`/opsx:propose`, requirements / design / planning subagents) | **Aggressively** — every architectural decision, user-visible naming (metadata objects, public API exports), scope edge, error-handling strategy, transactional boundary, БСП / library choice, settings / secrets storage, role shape, performance NFR. Pin the answers in `proposal.md` / `design.md` now. | When the answer is already in `openspec/specs/**` / `memory.md` / `.dev.env`; when one MCP call closes it (make the call); when the user explicitly said "you decide"; private / internal naming — pin in `design.md` with a one-line rationale, do not ask. |
| **Apply preflight** (single round at the start of `/opsx:apply`) | **One consolidated batch** — every empty highly-desirable `.dev.env` field needed by this session's tasks **and** every `design.md → ## Open Questions` item whose dependent task is in this session. | Anything answered in the artifacts (locked); anything on the banned list below; anything outside the current session's scope. |
| **Apply loop** (mid-implementation) | **Critical only** — a live-state fact conflicts with a locked artifact decision (missing metadata, `CompatibilityMode` mismatch, absent БСП subsystem, blocking typical-form structure). Raise a `CONFUSION` block and pause. | Routine task ambiguity, default selection, name choice — these are propose-phase defects, not a license to interrupt the user. |

The hierarchy is non-negotiable: a question that **could** have been asked in propose and **could** have been batched into preflight **must not** be asked mid-loop.

## Propose-phase clarification discipline

The upstream OpenSpec default "prefer making reasonable decisions to keep momentum" is **overridden** for this project:

- **Architecturally meaningful and ambiguous — ask the user now.** Meaningful = the choice changes `design.md → ## Architecture decisions`, the shape of a delta requirement, a public export signature, placement (main configuration vs extension), secrets / settings storage, transactional boundaries, error-handling pattern, logging strategy, the БСП subsystem, or the platform-version target. Ask via the `CONFUSION` format from `AGENTS.md → Development Procedure → 1. Think Before Coding` — options with trade-offs, no prose paraphrase.
- **A default the user is unlikely to care about — pin it in `design.md` with a one-line rationale and proceed** (cache policy without an NFR, a private helper name, an internal module split).
- **Depends on a 1C fact — make the MCP call, do not ask.** The user is not a substitute for `resolve_qualified_name` / `search_metadata` / `ssl_search` / `recall`.

### Pre-finalization clarification gate

Before declaring "All artifacts created! Ready for implementation.", run a consolidation pass:

1. Every `### Requirement:` in delta `specs/` and every `design.md` decision — does the implementer need any further user input to code it? If yes → add to a single batched list.
2. `proposal.md → Constraints / Out of scope / Non-goals` — any edge ambiguous enough to be crossed accidentally? Sharpen the wording or batch a clarification.
3. Every `tasks.md` task — executable from the artifacts alone? Any "no" → batch the missing input.
4. `design.md → ## Open Questions` — close now everything closable; leave only items that genuinely depend on later facts.
5. Non-empty batch → one consolidated question round → apply the answers to the artifacts → re-run the gate. Repeat until the batch is empty.

Only then may the "Ready for implementation" message be emitted.

### Forbidden in proposal artifacts

- "TODO: clarify with the user during apply" / "уточнить при реализации" — decide now with the user, or capture a numbered `## Open Questions` item with the exact future question, the artifact section it will update, and the dependent task ID.
- "We'll decide once we see the code" — write a **trigger condition** instead ("if `Документы.<Name>.<Attr>` resolves to type X then path A, else path B").
- Vague verbs in delta `### Requirement:` blocks — "appropriately", "if needed", "as required", "по необходимости" — each hides a question; replace with concrete criteria or escalate to a clarification round.
- Phantom defaults — two equally weighted options ("Cache size: 100 or 500") without a written rationale. Pick one, write the rationale in `design.md`, move on.

### Open Questions discipline

`design.md → ## Open Questions` is the **only** allowed bridge from propose to apply. One numbered item per question: the exact question text, ≥2 options with consequences, the artifact section that will be updated, the dependent task ID(s). An item belongs here only if **all** of: no currently exposed MCP call can close it; the user genuinely cannot answer at propose time (the fact surfaces later — production data, measurements, a not-yet-implemented module's shape); leaving it open does not block authoring the rest of the spec. "I forgot to ask" / "let's see what apply finds" are propose-phase failures, not Open Questions.

## Apply-phase clarification discipline

`/opsx:apply` runs against approved artifacts — **their decisions are locked**. Apply implements them; it does not re-litigate them. The approved artifacts also satisfy the plan-approval gate of the subagent pipeline (`subagent-pipeline.md → Stage 2 → Plan approval gate`) — apply never runs a separate plan-approval round on top of them. This section kills two recurring failure modes: re-asking what `design.md` / `proposal.md` already records, and dribbling questions across the implementation loop instead of one consolidated preflight round.

### Read first, then ask

Before raising any apply-time clarification, check whether it is already answered: decisions in `design.md` (architecture, placement, storage, transactional boundaries, error handling, logging, БСП subsystem), requirements in delta `spec.md`, `Out of scope` / `Non-goals` / `Constraints`, providers / defaults in `proposal.md` — all **locked**. `design.md → ## Open Questions` is the only legitimate apply-time question surface, and only when the dependent task is actually next. If the answer is in the artifacts — quote the locked decision in one line and continue. Disagreeing with a locked decision is not a clarification — it is a request to amend the artifact, which the user must explicitly authorize.

### Preflight round (single consolidated batch at apply start)

Immediately after reading the context files and **before** any code, run a **single** preflight round consolidating every remaining legitimate question into one `AskUserQuestion` call:

- every empty highly-desirable `.dev.env` field required by a task in this session's plan (fields needed only by tasks this session will not reach → defer those task blocks instead — see the banned list);
- every `design.md → ## Open Questions` item whose dependent task is in this session's plan — quote it verbatim, then a `CONFUSION` block with options and consequences;
- **nothing else.** A candidate outside these two buckets belongs in propose (its absence there is a propose defect) or nowhere (banned / defaulted / advisory).

The round corresponds exactly to the `## Genuine blockers` block of the opening template below; if that block is empty, there is no preflight round at all. After the answers: update `.dev.env`, write resolved items into `design.md → ## Architecture decisions` and strike them from `## Open Questions`, then enter the implementation loop. **The loop has no more `AskUserQuestion` calls** except the critical exceptions below.

### Legitimate apply-phase pauses

A mid-loop pause-and-ask is justified **only** by:

- **A new fact from the live state conflicting with a locked artifact decision** — a metadata object missing from this configuration, a `CompatibilityMode` mismatch, an absent БСП subsystem, a typical-form structure or actual attribute type that blocks the planned approach. State the conflict concretely as a `CONFUSION` block.
- **User-explicit re-open** of a previously locked decision.

Everything else is handled without pausing: a deferred `.dev.env` field whose dependent task became next — defer that task (`deferred-to-user` in `tasks.md`), continue with the rest, surface the deferred block once in the closing summary; an Open Question triggered by a task outside the session plan — almost always a session-planning defect, widen the next preflight instead of pausing; routine ambiguity (helper name, function vs procedure, log level) — make a codebase-consistent choice, record it via `remember` or `memory.md` Captured-during-work, move on.

### Forbidden at apply time

- Re-asking about provider / trigger / data scope / settings storage / placement / key handling / module placement / role grants / БСП subsystem / transactional boundaries settled in `proposal.md` or `design.md`.
- Bundling a `.dev.env` audit (empty fields **only**) with locked-decision re-asks — different gates, never mixed.
- Asking about a default that `design.md` already names, or offering options A / B / C when `## Architecture decisions` already picked one with a written rationale.
- Pausing on a non-blocking item "just to confirm" — if the artifact says X, do X.
- **Closing an `## Open Questions` item with a self-justifying paragraph instead of a `CONFUSION` block.** Open Questions are unresolved by definition; the agent has no authority to close them unilaterally — doubly so when the picked option modifies typical (standard) configuration objects (roles, forms, modules, event subscriptions). Implementation of the dependent task block waits for the user's explicit choice.

### Banned questions at apply time — hard list

These questions MUST NEVER be asked during `/opsx:apply`, regardless of whether the corresponding `.dev.env` field is empty — the documented fallback is applied silently, no pause, no `AskUserQuestion`. Classification canon — `dev-standards-env.md`.

| Banned question | Instead |
|---|---|
| Value of `PREFIX` (Advisory) | Create objects without a prefix; `{PREFIX}` resolves to empty. Do not announce the fallback — just proceed. |
| Value of `COMPANY` / `DEVELOPER` (Advisory) | Emit no modification markers; do not invent placeholder names. |
| `{TASK}` number for modification comments | Markers are emitted only when `COMPANY` **and** `DEVELOPER` are non-empty; only then, if `{TASK}` alone is missing — ask once for `{TASK}` only, never bundled with Advisory fields. |
| Pre-emptive `INFOBASE_PATH` / `PLATFORM_PATH` / `INFOBASE_PUBLISH_URL` when no IB-bound or UI-test step is **next** on the queue | Defer the dependent task block (`deferred-to-user` in `tasks.md`), finish all non-IB-bound tasks, state the deferral once in the closing summary. |
| `IB_USER` / `IB_PASSWORD` / `LOG_PATH` before an IB-bound block (Defaulted) | Apply the defaults silently (empty credentials = no authentication — `/N` / `/P` omitted, valid for dev / test IBs; empty `LOG_PATH` = `$env:TEMP\1cv8.log`). Re-ask credentials only after an authentication error, `LOG_PATH` only if the resolved path is non-writable. |

If an artifact explicitly **requests** a prefix / marker style / developer name (overriding the `.dev.env` default) — follow the artifact: that is a locked decision, not a question.

### Apply-phase opening template (default)

The parent agent's first message at `/opsx:apply` follows this structure; `## Genuine blockers` **is** the preflight round.

```text
Using change: <name>.

## Locked from artifacts (proceeding without re-asking)
- <decision>: <one-line value> — `<file>:<section>`

## Plan for this session
- <ordered list of task ids for this run>

## Genuine blockers (preflight — single consolidated round)
- <empty .dev.env field needed by this session's plan> — required by tasks <ids>
- <design.md Open Question with an in-session dependent task> — CONFUSION block (quote + options with consequences + recommendation + "→ Which one to pick?")
```

Rules: `## Locked from artifacts` is mandatory on any non-trivial apply (its absence is a defect); `## Plan for this session` precedes blockers because it defines which questions matter now; if `## Genuine blockers` is empty after the filters (banned list, defaulted fields, in-session plan), omit the block entirely and proceed straight to implementation.

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

Subagent **selection** is owned elsewhere — do not duplicate it here: the catalog in `content/rules/subagents.md` and the stage-by-stage choice lists in `content/rules/subagent-pipeline.md`. The default `propose → apply → archive` workflow maps onto those stages directly; artifact ownership is fixed by the table above. OpenSpec-specific additions:

- **Verification phase** — `1c-tester` runs UI tests only when `UI_TESTING` allows it (canon — `dev-standards-env.md`); `1c-code-reviewer` — only on an explicit user request.
- **Documentation & archive phase** — `1c-doc-writer` derives user docs from `specs/`; then `/opsx:archive` merges deltas into `specs/` and moves the change to `changes/archive/`.
