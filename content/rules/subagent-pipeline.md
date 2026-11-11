---
description: Delegated full-cycle flow — plan → implementation → review and testing → Definition of Done
alwaysApply: false
category: workflow
---

# Subagent Pipeline — Full-Cycle Flow

**When to load this file:** a **full-cycle** task (per `AGENTS.md → Triage: Quick-fix vs Docs-fix vs Spec-authoring vs Full-cycle`: over the quick-fix line budget, more than one module, any metadata change **except an isolated addition allowed by that triage**, any architectural impact, any non-trivial bug) **for which delegation to subagents has been chosen** per `subagents.md` — or is the default because `ORCHESTRATION=economy`.

Full-cycle alone does **not** trigger the pipeline. The **standard path** is the parent executing the 5-step Development Procedure from `AGENTS.md`: plan → implementation → testing, review and closing gates. For OpenSpec, approved artifacts are the plan and `sdd-apply.md` owns DoD completion. Delegation is chosen under `subagents.md → Delegation principle`; quick-fix uses `verification-policy.md → Quick-fix gate`.

**Companion files:** `subagents.md` (catalog, delegation criteria), `subagent-core.md` (common obligations including the Handoff format), `verification-gates.md` (the closing gate of the pipeline), `orchestrator-economy.md` (optional project mode — `ORCHESTRATION=economy` in `.dev.env`, toggled by `/economymode` — makes stage 2/3 delegation the default and shifts bulk reads to subagents; stages and gates are unchanged).

## The pipeline

1. **Triage** — parent agent: quick-fix vs full-cycle; only delegated full-cycle work continues.
2. **Plan** — `1c-planner` (or `1c-architect` when architectural; `1c-analytic` / `1c-explorer` by task shape) → an approved plan.
3. **Implement** — `1c-developer` (or `1c-metadata-manager` / `1c-refactoring` / `1c-performance-optimizer` / `1c-error-fixer` by task shape), with a Handoff block between chained subagents.
4. **Review** — 4a spec compliance by the parent; 4b code quality by the parent unless explicitly waived, delegated only on an explicit review request when `subagents.md → Reviewer model gate` is satisfied.
5. **Verification gate** — parent reconciles DoD, UI-confirmation and review results and `verification-gates.md`, reusing fresh evidence → deliver with completion status.

## Per-stage rules

### Stage 1 — Triage (parent agent)

**Only** full-cycle tasks for which delegation was chosen (`subagents.md → Delegation principle`) enter the pipeline. Every other task — direct full-cycle, quick-fix, docs-fix, spec-authoring — follows its own path from `AGENTS.md → Triage` and `verification-policy.md`, which also owns the promotion triggers. When in doubt, full-cycle wins.

### Stage 2 — Plan (delegate to a planning subagent)

Choose by task shape:

- **`1c-analytic`** — when a written PRD / specification / area study is needed before any plan exists. Output: a written analysis, no code.
- **`1c-explorer`** — for broad read-only mapping before the plan: locating related modules, metadata, entry points, dependencies, and callers — this project agent only (`subagents.md → Host-tool built-in explorers`).
- **`1c-architect`** — for new subsystems, multi-module designs, integrations, or extension boundaries. Output: an architecture document with module boundaries and data flow.
- **`1c-arch-reviewer`** — only when the user explicitly asked to validate an existing design and `subagents.md → Reviewer model gate` is satisfied; the pipeline never launches it on its own. With the gate not satisfied the parent performs the requested review.
- **`1c-planner`** — for everything else that fits in one feature: produces a numbered task list.

The plan must satisfy these acceptance criteria before stage 3:

- Each task is **one coherent unit of work** that an enthusiastic junior 1C developer with no project context can execute: a procedure / function, an event handler, a form, a register, or a coherent group of related edits within one module. Do not shred the plan into ≤20-line fragments — over-fragmentation multiplies verification points and handoffs without adding safety.
- Each task names exact file paths and exact procedure names — no "update the related modules".
- Verification points are attached per module / coherent group (`syntaxcheck`, an MCP query, an assertion, a manual reproduction) — not per every few lines.
- DoD links acceptance criteria to verification (gates, behavioural confirmation, UI where applicable) and final review tasks; explicit waivers are recorded (`sdd-propose.md` for OpenSpec).
- Risks and rollback are explicit, especially for metadata changes (UUID stability, register movements, role grants).
- The plan is approved — see the approval gate below.

**Plan approval gate — scaled by risk.**

- **User approval is a hard gate** when the plan touches any promotion trigger from `verification-policy.md → Triage details`: metadata wired into existing behavior, transactional paths, public common-module contracts, RLS / roles / event subscriptions / scheduled jobs, adopted extension objects — or anything hard to reverse. Do not proceed to stage 3 without it.
- **Approved OpenSpec artifacts count as the approval.** When the pipeline runs inside the OpenSpec **apply** phase (an active `openspec/changes/<change-name>/` with `proposal.md` / `design.md` / `tasks.md` exists — the common case on this workflow), those artifacts **are** the approved plan: do not run a separate plan-approval round, quote the locked decisions and proceed (`sdd-apply.md → Apply-phase clarification discipline`). Deviating from the artifacts still requires explicit user authorization.
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
- **`1c-error-fixer`** — runtime / syntax error fixing without architectural rework. Use the `standards(name="systematic-debugging")` methodology inside.

The implementation subagent is bound by the plan from stage 2; out-of-plan changes and defects found beside the plan follow `subagent-core.md → Scope and done criteria` (report, do not fix). If the plan turns out wrong, return to stage 2 on the subagent's `CONFUSION`; stage 3 never rewrites the plan.

Stage 3 is **sequential by default**: 1C metadata is densely cross-referenced, and parallel subagents on the same configuration corrupt UUIDs and break references. Parallelize only subtasks that are provably independent (e.g. one new report plus one new common-module function with no shared metadata).

The implementation subagent's own duties — the gates its depth selects with fingerprinted evidence after the final edit, scope, the file-by-file diff summary and the Handoff block — are `subagent-core.md → Validator chain (mutating agents)`, `Scope and done criteria` and `Handoff in / out (implementation subagents)`. Stage 5 reuses that evidence instead of repeating calls.

### Stage 3 — Handoff between implementation subagents

When stage 3 is split across implementation subagents inside one change (typical chain: `1c-metadata-manager` produces stubs and metadata, then `1c-developer` fills the BSL bodies), the Handoff block carries the inventory and the decisions so nobody rediscovers them; its format and the subagent-side rules are in `subagent-core.md`. Parent agent obligations:

- include the upstream Handoff block **verbatim** in the next subagent's prompt under a heading `## Upstream Handoff` — no paraphrasing, re-formatting or selective omission; paraphrasing is the dominant source of drift between stages;
- put the parent's own additional instructions (extra constraints, new user feedback) in a separate section **after** `## Upstream Handoff`, never mixed into it;
- do not re-list the artifacts in the prompt prose — the Handoff is the inventory;
- reject a Handoff that only says "see files above" and request it again — it must list the artifacts and the public surface, not point at a diff.

### Stage 4a — Spec-compliance review (parent agent, cheap)

The parent agent — **not** a subagent — runs this stage. It is a structural check, not a code review.

Checklist:

- Every task in the plan was executed; no task was silently skipped.
- No file outside the plan was edited (use `git diff --name-only` to verify).
- The names, parameter types, return types of new public procedures match the plan.
- New / removed metadata objects match the plan; UUIDs were preserved on edits, not regenerated.
- Module headers (the `// Возвращает / Параметры` comment blocks per `standards(name="dev-standards-code-style") → "Procedure/Function Documentation"`) are present on new public procedures.

If anything fails — return to stage 3 with a precise delta. Run 4b after 4a passes, unless the user explicitly waived review.

Record the 4a result (checked items, diff-vs-plan verdict). Stage 5's plan-adherence check (`verification-delivery.md → Soft gate B`) **reuses this evidence** — it confirms the 4a result is still fresh (no edits after the review) instead of re-running the file-by-file diff.

### Stage 4b — Code-quality review (parent by default)

Required for full-cycle unless explicitly prohibited by the user (`verification-delivery.md → Soft gate C`). The parent reviews by default; `1c-code-reviewer` runs only on an explicit review request with the reviewer model gate satisfied (`subagents.md`). Disabling the subagent does not waive this stage. Reuse fresh Stage 3 validator evidence; do not repeat calls against unchanged content.

The reviewer (eligible subagent or parent) checks requirements, correctness and regressions, plus applicable domain concerns:

- anti-patterns from `standards(name="anti-patterns")` and `standards(name="platform-solutions")`;
- ITS standards via `its_help` → `fetch_its`;
- style / ITS findings from the Stage 3 `review_1c_code` evidence when the active depth selected Gate 3 (`verification-policy.md`) — this stage adds no validator call of its own;
- query patterns, transactional safety, lock granularity, posting boundaries.

Report `critical` / `major` / `minor` findings (`subagent-core.md → Report vocabulary`). Resolve critical / major issues and confirm affected checks before completion; minor issues are informational.

### Stage 5 — Verification gate (parent agent)

Run the closing gate from `verification-gates.md`. This is non-negotiable for full-cycle tasks. Apply its **Gate execution and evidence reuse** rule: accept fresh Stage 3 evidence for Gates 1–3, run only missing or stale gates, then complete every other applicable hard / soft gate (`verification-delivery.md`).

Run planned behavioural confirmation, including UI as `UI_TESTING` allows, fix failures and reconcile DoD against current evidence (`verification-delivery.md → Full-cycle Definition of Done`; OpenSpec — `sdd-apply.md`). An implementation handoff or completed task list alone is not completion. Blocked checks remain open; only the user can waive UI confirmation or review.

## When to deviate

Inside a delegated change, a documentation subtask may go to `1c-doc-writer` and the UI confirmation of Stage 5 to `1c-tester` when `UI_TESTING` allows it. Work that is not a delegated full-cycle change — a docs-fix, a UI run against an existing build, an architectural review the user asked for — does not enter the pipeline at all. Record any deviation from the stages, with its reason, in the delivery summary.
