---
description: Formalized subagent pipeline for delegated full-cycle 1C changes — planner → developer → spec-compliance review → optional code-reviewer → verification gate
alwaysApply: false
category: workflow
---

# Subagent Pipeline — Full-Cycle Flow

**When to load this file:** a **full-cycle** task (per `AGENTS.md → Triage: Quick-fix vs Docs-fix vs Spec-authoring vs Full-cycle`: over the quick-fix line budget, more than one module, any metadata change **except an isolated addition allowed by that triage**, any architectural impact, any non-trivial bug) **for which delegation to subagents has been chosen** per `subagents.md` — or is the default because `ORCHESTRATION=economy`.

Full-cycle alone does **not** trigger the pipeline. The **standard path** for a full-cycle task is the parent agent executing the 5-step Development Procedure from `AGENTS.md` directly: plan stated in chat → implementation → closing gate from `verification-checklist.md`. It is usually faster for medium tasks that fit the parent's context; the pipeline pays off when the work is bulky enough to justify subagent launches (`subagents.md → Delegation principle`). For quick-fix tasks the pipeline is unnecessary overhead — use a direct edit plus the strict quick-fix gate from `verification-checklist.md`.

**Companion files:** `subagents.md` (catalog of subagents and when to delegate), `verification-checklist.md` (the closing gate of the pipeline), `orchestrator-economy.md` (optional project mode — `ORCHESTRATION=economy` in `.dev.env`, toggled by `/economymode` — makes stage 2/3 delegation the default and shifts bulk reads to subagents; stages and gates are unchanged).

The pipeline is adapted from the `subagent-driven-development` skill of [obra/superpowers](https://github.com/obra/superpowers) and combined with the 13 specialized 1C subagents already shipped in `content/agents/`.

## Why a fixed pipeline

Without a fixed pipeline, the parent agent tends to:

- start writing code before the plan is verified;
- skip structural verification because "the code is small and obvious";
- merge spec compliance and routine quality validation into one fuzzy review and miss both.

The pipeline removes those failure modes by separating **what to build** (planner), **how to build it** (developer), **spec compliance** (parent structural review), optional user-requested code review, and the final verification gate.

## The pipeline

```
[user request]
      │
      ▼
┌─────────────────────────────┐
│ 1. Triage                   │  parent agent
│    quick-fix vs full-cycle  │
└──────────────┬──────────────┘
               │ full-cycle
               ▼
┌─────────────────────────────┐
│ 2. Plan                     │  delegate → 1c-planner
│    plan.md / tasks.md       │  (or 1c-architect if architectural)
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ 3. Implement                │  delegate → 1c-developer
│    code + metadata edits    │  (or 1c-metadata-manager for XML-heavy)
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ 4a. Spec-compliance review  │  parent agent (cheap, structural)
│     does it match the plan? │
└──────────────┬──────────────┘
               │  passes
               ▼
╭ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ╮
  4b. Code-quality review       OPTIONAL — only when the user
      style, anti-patterns,     explicitly asks for code review.
      ITS standards             Delegate → 1c-code-reviewer.
                                Skip otherwise; gates 2/3 of stage 5
                                already cover routine quality.
╰ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ╯
               │
               ▼
┌─────────────────────────────┐
│ 5. Verification gate        │  parent agent
│    verification-checklist   │
└──────────────┬──────────────┘
               │  pass
               ▼
        deliver to user
```

## Per-stage rules

### Stage 1 — Triage (parent agent)

Apply the matrix from `AGENTS.md → Triage: Quick-fix vs Docs-fix vs Spec-authoring vs Full-cycle`. **Only** full-cycle tasks for which delegation was chosen enter the pipeline; other full-cycle tasks follow the standard path (direct execution by the parent per `AGENTS.md`, same closing gate). If the task is a quick-fix, edit directly and run the strict applicable gate from `verification-checklist.md` (Gates 1–3 for BSL; Gate 5 for pure metadata XML; both when metadata embeds BSL). Tasks on the **docs-fix** path (Markdown / rules / docs only) bypass the pipeline and the BSL validators — apply the structural checks from `AGENTS.md → Triage` instead. Tasks on the **spec-authoring** path (OpenSpec artifacts with 1C facts) also bypass the pipeline but carry the MCP evidence obligations from `sdd-integrations.md`.

The detailed promotion triggers (transactional paths, public exports, adopted objects, subscriptions / jobs / RLS, wired metadata) and the isolated-metadata-addition eligibility are owned by `verification-policy.md → Triage details` — apply them as written. When in doubt, full-cycle wins.

### Stage 2 — Plan (delegate to a planning subagent)

Choose by task shape:

- **`1c-analytic`** — when a written PRD / specification / area study is needed before any plan exists. Output: a written analysis, no code.
- **`1c-explorer`** — for broad read-only mapping before the plan: locating related modules, metadata, entry points, dependencies, and callers.
- **`1c-architect`** — for new subsystems, multi-module designs, integrations, or extension boundaries. Output: an architecture document with module boundaries and data flow.
- **`1c-arch-reviewer`** — when an architectural design already exists and needs validation before implementation.
- **`1c-planner`** — for everything else that fits in one feature: produces a numbered task list.

The plan must satisfy these acceptance criteria before stage 3:

- Each task is **one coherent unit of work** that an enthusiastic junior 1C developer with no project context can execute: a procedure / function, an event handler, a form, a register, or a coherent group of related edits within one module. Do not shred the plan into ≤20-line fragments — over-fragmentation multiplies verification points and handoffs without adding safety.
- Each task names exact file paths and exact procedure names — no "update the related modules".
- Verification points are attached per module / coherent group (`syntaxcheck`, an MCP query, an assertion, a manual reproduction) — not per every few lines.
- Risks and rollback are explicit, especially for metadata changes (UUID stability, register movements, role grants).
- The plan is approved — see the approval gate below.

**Plan approval gate — scaled by risk.**

- **User approval is a hard gate** when the plan touches any promotion trigger from `verification-policy.md → Triage details`: metadata wired into existing behavior, transactional paths, public common-module contracts, RLS / roles / event subscriptions / scheduled jobs, adopted extension objects — or anything hard to reverse. Do not proceed to stage 3 without it.
- **Approved OpenSpec artifacts count as the approval.** When the pipeline runs inside the OpenSpec **apply** phase (an active `openspec/changes/<change-name>/` with `proposal.md` / `design.md` / `tasks.md` exists — the common case on this workflow), those artifacts **are** the approved plan: do not run a separate plan-approval round, quote the locked decisions and proceed (`sdd-integrations.md → Apply-phase clarification discipline`). Deviating from the artifacts still requires explicit user authorization.
- **Medium pure-code full-cycle tasks** with no trigger from the risk list: publish the plan in chat and proceed without waiting for an approval round-trip — the user can interrupt or correct. State in one line that implementation continues on this plan.
- An explicit user pre-approval ("plan and implement without confirmation", a pre-approving launch prompt) is always honored; record it in the final report as the approval source.

**Unattended runs.** When approval **is** required by the risk list above and no human is in the loop (autonomous / scheduled / CI-style run), do **not** self-approve: stop after stage 2 and deliver the plan itself as the run's result, marked as awaiting approval. Approved OpenSpec artifacts or an explicit pre-approval in the launch prompt satisfy the gate — record the approval source in the final report.

For projects on the OpenSpec workflow (`/opsx:propose`), the plan lives in `openspec/changes/<change-name>/tasks.md` and the design in `design.md`. The pipeline does not replace OpenSpec — it slots into the **apply** phase of OpenSpec, and its stage 2 is normally already done there (the artifacts replace a fresh plan; re-planning an approved change is a defect).

### Stage 3 — Implement (delegate to an implementation subagent)

Choose by task shape:

- **`1c-developer`** — bulk BSL changes across modules, common modules, server / client procedures.
- **`1c-metadata-manager`** — when the bulk of the change is metadata: new objects, forms, reports, layouts, roles, extensions, tabular sections, attributes.
- **`1c-refactoring`** — dead-code cleanup, deduplication, extraction across multiple modules.
- **`1c-performance-optimizer`** — when the explicit task is to optimize a slow query / loop / posting / report.
- **`1c-error-fixer`** — runtime / syntax error fixing without architectural rework. Use the `systematic-debugging.md` methodology inside.

The implementation subagent is bound by the plan from stage 2. Out-of-plan changes ("while we're here") are forbidden — if the developer notices a real defect orthogonal to the plan, it must be reported back to the parent agent, not silently fixed.

The implementation subagent is responsible for:

- editing the BSL / XML;
- running the ordered validator chain on every touched module:
  `syntaxcheck` → `check_1c_code` → `review_1c_code`;
- recording per-artifact validator results and run counts after the final edit so Stage 5 can
  reuse them without duplicate calls;
- preserving module headers, regions and the project's code style (`dev-standards-code-style.md`);
- removing only the imports / variables / procedures **that its own changes made unused** — never pre-existing dead code;
- summarizing the diff against the plan, file by file;
- producing a structured **Handoff** block (see "Stage 3 — Handoff between implementation subagents" below) when the same change is going to continue under another implementation subagent.

### Stage 3 — Handoff between implementation subagents

When stage 3 is split across multiple implementation subagents inside the same change (typical chain: `1c-metadata-manager` produces stubs and metadata, then `1c-developer` fills the BSL bodies; or `1c-developer` writes the bulk and `1c-refactoring` consolidates), the parent agent **must** prevent the downstream subagent from re-reading what the upstream subagent has already produced. Re-reading bloats the downstream context, wastes minutes per file, and is a recurring failure mode of informal chains.

The mechanism is a fixed-format **Handoff** block that every upstream implementation subagent puts at the top of its final report, that the parent forwards verbatim, and that the downstream subagent treats as authoritative inventory.

**Mandatory Handoff format (emitted by the upstream subagent at the very top of its final report):**

```text
## Handoff for the next subagent

### Artifacts
- <full repo path> — <one-line role> [stub | done | edited]
- ...

### Public surface
- <ObjectName>.<RoutineName>(<params>) → <return type> — <one-line purpose>
- <Metadata.Object> — <attribute / tabular section / form name>: <type / role>
- ...

### Open TODOs / stubs for the next subagent
- <file>:<region or routine> — <what to implement> — <signature hint, if pre-agreed>
- ...

### Locked decisions (do not revisit without approval)
- <decision> — <one-line rationale>
- ...

### Open questions raised
- <CONFUSION-id> — <one-line summary> — <status: resolved / pending>
```

The block is **not** a marketing summary — it is a machine-readable inventory. Keep each line short (≤120 chars), one fact per line, no prose paragraphs inside the block.

**Parent agent obligations:**

- When invoking the next implementation subagent on the same change, the parent **must** include the upstream Handoff block verbatim in the new subagent's prompt under a heading `## Upstream Handoff`. No paraphrasing, no re-formatting, no selective omission — paraphrasing is the dominant source of drift between stages.
- If the parent has its own additional instructions (extra constraints, new user feedback), they go in a separate section **after** `## Upstream Handoff`, not mixed into it.
- The parent does **not** re-list the artifacts in its own prompt prose — the Handoff is the inventory.

**Downstream subagent obligations:**

- The downstream subagent **must** read the `## Upstream Handoff` block first and treat `### Artifacts`, `### Public surface`, and `### Locked decisions` as authoritative. Re-deriving them by reading files is forbidden.
- The downstream subagent **must not** call `Read`, `get_module_structure`, `metadatasearch`, `get_metadata_details`, `inspect_form_layout`, or `Glob` on objects / files already listed in the Handoff "for context" or "to verify". A targeted call is allowed **only** when a concrete detail needed for the current edit is missing from the Handoff (e.g. exact UUID, exact line of a TODO marker inside an existing region, full attribute list of a tabular section the upstream summarized as `<attribute / tabular section …>`). Before such a call, the subagent must state in one sentence which detail is missing and why the Handoff alone is insufficient.
- The downstream subagent **must** preserve `### Locked decisions` unless the user (not the parent) explicitly authorizes a revision. If a locked decision turns out to block correct implementation, raise a `CONFUSION` instead of silently overriding it.
- The downstream subagent appends its own Handoff block at the top of **its** report if a further implementation subagent is expected; otherwise its report goes straight into stage 4a.

**Anti-patterns:**

- Downstream subagent opens with `Read` on every file in `### Artifacts` "to load context" — the inventory **is** the context.
- Parent paraphrases the Handoff into its own words "to make it shorter" — paraphrasing erases the very precision the format is for.
- Upstream emits a Handoff that just says "see files above" — that defeats the purpose; the Handoff must list the artifacts and the public surface, not point at a diff.
- Upstream embeds prose explanations inside `### Locked decisions` — keep one rationale line; long discussion belongs in the report body, not the inventory.

### Stage 4a — Spec-compliance review (parent agent, cheap)

The parent agent — **not** a subagent — runs this stage. It is a structural check, not a code review.

Checklist:

- Every task in the plan was executed; no task was silently skipped.
- No file outside the plan was edited (use `git diff --name-only` to verify).
- The names, parameter types, return types of new public procedures match the plan.
- New / removed metadata objects match the plan; UUIDs were preserved on edits, not regenerated.
- Module headers (the `// Возвращает / Параметры` comment blocks per `dev-standards-code-style.md → "Procedure/Function Documentation"`) are present on new public procedures.

If anything fails — bounce back to stage 3 with a precise delta. If optional 4b is applicable, do not proceed to it until 4a is clean. This is the cheap gate; running 4b before 4a is wasted compute.

Record the 4a result (checked items, diff-vs-plan verdict). Stage 5's plan-adherence check (`verification-delivery.md → Soft gate B`) **reuses this evidence** — it confirms the 4a result is still fresh (no edits after the review) instead of re-running the file-by-file diff.

### Stage 4b — Code-quality review (delegate to `1c-code-reviewer`, when applicable)

Constraints: `1c-code-reviewer` runs **only when the user explicitly asks for a code review** (canon — `subagents.md`); auto-triggering is forbidden. For non-review-requested tasks the Stage 3 agent supplies the routine validator evidence; the parent checks its freshness in Stage 5 and runs only missing or stale gates.

When the user asks for a review, the subagent looks at:

- anti-patterns from `anti-patterns.md` and `platform-solutions.md`;
- ITS standards via `its_help` → `fetch_its`;
- BSL LS warnings via `review_1c_code`;
- query patterns, transactional safety, lock granularity, posting boundaries.

The subagent reports issues by severity (critical / major / minor). Critical issues block delivery; minor issues are informational.

### Stage 5 — Verification gate (parent agent)

Run the closing gate from `verification-checklist.md`. This is non-negotiable for full-cycle
tasks. Apply its **Gate execution and evidence reuse** rule: accept fresh Stage 3 evidence for
Gates 1–3, run only missing or stale gates, then complete every other applicable hard / soft gate.

## Anti-patterns of the pipeline

- **Skipping stage 2** "because the change is small" — if it is small, it should have been a quick-fix or the standard path (direct execution) in stage 1, not a pipeline with holes.
- **Letting the implementation subagent re-plan** — if the plan turns out wrong, return to stage 2, do not let stage 3 silently rewrite it.
- **Running optional 4b before 4a** — wastes the code-reviewer subagent on a structurally wrong implementation.
- **Auto-triggering `1c-code-reviewer`** — explicitly forbidden by `subagents.md`.
- **Parallelizing stage 3** by default — 1C metadata is densely cross-referenced; parallel subagents on the same configuration tend to corrupt UUIDs and break references. Parallelize only when the subtasks are provably independent (e.g., one new report + one new common-module function with no shared metadata).
- **"I'll just fix this lint while I'm in the file"** during stage 3 — Surgical Changes; report it, do not fix it.

## When to deviate

The pipeline is the default for **delegated** full-cycle tasks (a non-delegated full-cycle task follows the standard path — see the top of this file). Once inside the pipeline, deviate from its stages only with an explicit reason:

- pure documentation changes — `1c-doc-writer` directly, no plan / dev / review pipeline;
- pure UI test runs against an existing build — `1c-tester` directly, **only when `UI_TESTING` allows it** (see below);
- a pure architectural review with no code change — `1c-arch-reviewer` directly.

**UI testing is never an automatic stage of this pipeline.** It is opt-in, gated by `UI_TESTING` in `.dev.env` (canon — `dev-standards-env.md → "UI_TESTING — web UI-testing mode"`; see also `verification-delivery.md → Soft gate D`). Stage 5 relies on the static validator chain and impact analysis; it does **not** require a UI-test run unless `UI_TESTING=auto` or the user explicitly asked.

Document the deviation in the delivery summary so the user can audit the choice.
