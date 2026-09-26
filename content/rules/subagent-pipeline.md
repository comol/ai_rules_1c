---
description: Delegated full-cycle flow — plan → implementation → review and testing → Definition of Done
alwaysApply: false
category: workflow
---

# Subagent Pipeline — Full-Cycle Flow

**When to load this file:** a **full-cycle** task (per `AGENTS.md → Triage: Quick-fix vs Docs-fix vs Spec-authoring vs Full-cycle`: over the quick-fix line budget, more than one module, any metadata change **except an isolated addition allowed by that triage**, any architectural impact, any non-trivial bug) **for which delegation to subagents has been chosen** per `subagents.md` — or is the default because `ORCHESTRATION=economy`.

Full-cycle alone does **not** trigger the pipeline. The **standard path** is the parent executing the 5-step Development Procedure from `AGENTS.md`: plan → implementation → testing, review and closing gates. For OpenSpec, approved artifacts are the plan and `sdd-integrations.md` owns DoD completion. Delegation is chosen under `subagents.md → Delegation principle`; quick-fix uses `verification-policy.md → Quick-fix gate`.

**Companion files:** `subagents.md` (catalog, delegation criteria), `subagent-core.md` (common obligations including the Handoff format), `verification-gates.md` (the closing gate of the pipeline), `orchestrator-economy.md` (optional project mode — `ORCHESTRATION=economy` in `.dev.env`, toggled by `/economymode` — makes stage 2/3 delegation the default and shifts bulk reads to subagents; stages and gates are unchanged).

## The pipeline

1. **Triage** — parent agent: quick-fix vs full-cycle; only delegated full-cycle work continues.
2. **Plan** — `1c-planner` (or `1c-architect` when architectural; `1c-analytic` / `1c-explorer` / `1c-arch-reviewer` by task shape) → an approved plan.
3. **Implement** — `1c-developer` (or `1c-metadata-manager` / `1c-refactoring` / `1c-performance-optimizer` / `1c-error-fixer` by task shape), with a Handoff block between chained subagents.
4. **Review** — 4a spec compliance by the parent; 4b code quality by the parent unless explicitly waived, delegated only on an explicit review request when `subagents.md → Reviewer model gate` is satisfied.
5. **Verification gate** — parent reconciles DoD, UI-confirmation and review results and `verification-gates.md`, reusing fresh evidence → deliver with completion status.

## Per-stage rules

### Stage 1 — Triage (parent agent)

Apply the matrix from `AGENTS.md → Triage: Quick-fix vs Docs-fix vs Spec-authoring vs Full-cycle`. **Only** full-cycle tasks for which delegation was chosen enter the pipeline; other full-cycle tasks follow the standard path (direct execution by the parent per `AGENTS.md`, same closing gate). If the task is a quick-fix, edit directly and run the strict applicable gate from `verification-gates.md` (Gates 1–3 for BSL; Gate 5 for pure metadata XML; both when metadata embeds BSL). Tasks on the **docs-fix** path (Markdown / rules / docs only) bypass the pipeline and the BSL validators — apply the structural checks from `AGENTS.md → Triage` instead. Tasks on the **spec-authoring** path (OpenSpec artifacts with 1C facts) also bypass the pipeline but carry the MCP evidence obligations from `sdd-integrations.md`.

The detailed promotion triggers (transactional paths, public exports, adopted objects, subscriptions / jobs / RLS, wired metadata) and the isolated-metadata-addition eligibility are owned by `verification-policy.md → Triage details` — apply them as written. When in doubt, full-cycle wins.

### Stage 2 — Plan (delegate to a planning subagent)

Choose by task shape:

- **`1c-analytic`** — when a written PRD / specification / area study is needed before any plan exists. Output: a written analysis, no code.
- **`1c-explorer`** — for broad read-only mapping before the plan: locating related modules, metadata, entry points, dependencies, and callers. Use this project agent only — never the host built-in Explore / `explore` (`subagents.md → Host-tool built-in explorers`).
- **`1c-architect`** — for new subsystems, multi-module designs, integrations, or extension boundaries. Output: an architecture document with module boundaries and data flow.
- **`1c-arch-reviewer`** — when an architectural design already exists and needs validation before implementation, subject to `subagents.md → Reviewer model gate`. If disabled, omit the pipeline-only review; an explicit user review request is handled by the parent.
- **`1c-planner`** — for everything else that fits in one feature: produces a numbered task list.

The plan must satisfy these acceptance criteria before stage 3:

- Each task is **one coherent unit of work** that an enthusiastic junior 1C developer with no project context can execute: a procedure / function, an event handler, a form, a register, or a coherent group of related edits within one module. Do not shred the plan into ≤20-line fragments — over-fragmentation multiplies verification points and handoffs without adding safety.
- Each task names exact file paths and exact procedure names — no "update the related modules".
- Verification points are attached per module / coherent group (`syntaxcheck`, an MCP query, an assertion, a manual reproduction) — not per every few lines.
- DoD links acceptance criteria to verification (gates, UI confirmation) and final review tasks; explicit waivers are recorded (`sdd-integrations.md` for OpenSpec).
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
- **`1c-error-fixer`** — runtime / syntax error fixing without architectural rework. Use the `standards(name="systematic-debugging")` methodology inside.

The implementation subagent is bound by the plan from stage 2; out-of-plan changes and defects found beside the plan follow `subagent-core.md → Scope and done criteria` (report, do not fix). If the plan turns out wrong, return to stage 2 on the subagent's `CONFUSION`; stage 3 never rewrites the plan.

Stage 3 is **sequential by default**: 1C metadata is densely cross-referenced, and parallel subagents on the same configuration corrupt UUIDs and break references. Parallelize only subtasks that are provably independent (e.g. one new report plus one new common-module function with no shared metadata).

The implementation subagent is responsible for:

- editing the BSL / XML;
- running the ordered validator chain on every touched module — `syntaxcheck` → `check_1c_code` → `review_1c_code` — and recording per-artifact fingerprints, validator results, run counts and relevant execution context after the final edit so Stage 5 can reuse matching evidence without duplicate calls;
- preserving module headers, regions and the project's code style (`standards(name="dev-standards-code-style")`);
- removing only the imports / variables / procedures **that its own changes made unused** — never pre-existing dead code;
- summarizing the diff against the plan, file by file;
- producing a structured **Handoff** block when the same change continues under another implementation subagent (next section).

### Stage 3 — Handoff between implementation subagents

When stage 3 is split across multiple implementation subagents inside the same change (typical chain: `1c-metadata-manager` produces stubs and metadata, then `1c-developer` fills the BSL bodies; or `1c-developer` writes the bulk and `1c-refactoring` consolidates), the parent avoids repeated discovery of unchanged inventory and decisions. The downstream agent still reads its current edit target and verifies evidence fingerprints: shared-workspace files may have changed after the handoff. Saving context never justifies editing stale content.

The block format and the subagent-side rules (emit at the very top of the report; preserve decisions, check current artifact state) — `subagent-core.md → Handoff in / out (implementation subagents)`. Parent agent obligations:

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
- BSL LS warnings via `review_1c_code`;
- query patterns, transactional safety, lock granularity, posting boundaries.

Report `critical` / `major` / `minor` findings (`subagent-core.md → Report vocabulary`). Resolve critical / major issues and confirm affected checks before completion; minor issues are informational.

### Stage 5 — Verification gate (parent agent)

Run the closing gate from `verification-gates.md`. This is non-negotiable for full-cycle tasks. Apply its **Gate execution and evidence reuse** rule: accept fresh Stage 3 evidence for Gates 1–3, run only missing or stale gates, then complete every other applicable hard / soft gate (`verification-delivery.md`).

Run planned UI confirmation as `UI_TESTING` allows unless explicitly cancelled, fix failures and reconcile DoD against current evidence (`sdd-integrations.md`). An implementation handoff or completed task list alone is not completion. Blocked checks remain open; only the user can waive UI confirmation or review.

## When to deviate

Once inside the pipeline, deviate from its stages only with an explicit reason:

- pure documentation changes — `1c-doc-writer` directly, no plan / dev / review pipeline;
- pure UI test runs against an existing build — `1c-tester` directly, only when `UI_TESTING` allows it (`verification-delivery.md → Soft gate D`);
- a pure architectural review with no code change — `1c-arch-reviewer` directly when the reviewer model gate is satisfied; otherwise the parent performs the requested review.

Document the deviation in the delivery summary so the user can audit the choice.
