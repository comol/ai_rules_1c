---
description: Formalized subagent pipeline for non-trivial 1C changes — planner → developer → spec-compliance review → optional code-reviewer → verification gate
alwaysApply: false
category: workflow
---

# Subagent Pipeline — Full-Cycle Flow

**When to load this file:** any task that exceeds the **quick-fix** threshold defined in `AGENTS.md → Triage: Quick-fix vs Full-cycle` (more than ~20 changed lines, more than one module, any metadata change, any architectural impact, any non-trivial bug). For quick-fix tasks the pipeline is unnecessary overhead — a direct edit + `syntaxcheck` is enough.

**Companion files:** `subagents.md` (catalog of subagents and when to delegate), `verification-checklist.md` (the closing gate of the pipeline).

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

Apply the matrix from `AGENTS.md → Triage: Quick-fix vs Full-cycle`. **Only** full-cycle tasks enter the pipeline. If the task is a quick-fix, edit directly and skip to stage 5 with a minimal verification (`syntaxcheck` only).

If the user asks for a small change that **looks** like a quick-fix but the change touches a transactional path, a public common-module export, an extension's adopted object, an event subscription / scheduled job / RLS condition, or metadata wired into existing behavior (rename / remove / immediate-use, RLS / indexing / fill-check changes) — promote it to full-cycle. **Isolated metadata additions** that satisfy the "Isolated metadata addition" clause in `AGENTS.md → Triage` (new independent register / defined type / enumeration / constant / unwired attribute, with no consumer touched in the same change) stay on the quick-fix path. When in doubt, full-cycle wins.

### Stage 2 — Plan (delegate to a planning subagent)

Choose by task shape:

- **`1c-analytic`** — when a written PRD / specification / area study is needed before any plan exists. Output: a written analysis, no code.
- **`1c-explorer`** — for broad read-only mapping before the plan: locating related modules, metadata, entry points, dependencies, and callers.
- **`1c-architect`** — for new subsystems, multi-module designs, integrations, or extension boundaries. Output: an architecture document with module boundaries and data flow.
- **`1c-arch-reviewer`** — when an architectural design already exists and needs validation before implementation.
- **`1c-planner`** — for everything else that fits in one feature: produces a numbered task list.

The plan must satisfy these acceptance criteria before stage 3:

- Each task is small enough that an enthusiastic junior 1C developer with no project context can execute it: typically 1 file / 1 procedure / ≤ ~20 changed lines per task.
- Each task names exact file paths and exact procedure names — no "update the related modules".
- Each task has a verification step (`syntaxcheck`, an MCP query, an assertion, a manual reproduction).
- Risks and rollback are explicit, especially for metadata changes (UUID stability, register movements, role grants).
- The plan is reviewed by the user. The user's approval is a hard gate — do not proceed to stage 3 without it.

For projects on the OpenSpec workflow (`/opsx:propose`), the plan lives in `openspec/changes/<change-name>/tasks.md` and the design in `design.md`. The pipeline does not replace OpenSpec — it slots into the **apply** phase of OpenSpec.

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
- running its own pre-handoff `syntaxcheck` on every touched module;
- preserving module headers, regions and the project's code style (`dev-standards-core.md`);
- removing only the imports / variables / procedures **that its own changes made unused** — never pre-existing dead code;
- summarizing the diff against the plan, file by file;
- producing a structured **Handoff** block (see "Stage 3 — Handoff between implementation subagents" below) when the same change is going to continue under another implementation subagent.

### Stage 3 — Handoff between implementation subagents

When stage 3 is split across multiple implementation subagents inside the same change (typical chain: `1c-metadata-manager` produces stubs and metadata, then `1c-developer` fills the BSL bodies; or `1c-developer` writes the bulk and `1c-refactoring` consolidates), the parent agent **must** prevent the downstream subagent from re-reading what the upstream subagent has already produced. Re-reading bloats the downstream context, wastes minutes per file, and is a recurring failure mode of informal chains.

The mechanism is a fixed-format **Handoff** block that every upstream implementation subagent puts at the top of its final report, that the parent forwards verbatim, and that the downstream subagent treats as authoritative inventory.

**Mandatory Handoff format (emitted by the upstream subagent at the very top of its final report):**

```text
## Handoff (для следующего субагента)

### Artifacts
- <full repo path> — <one-line role> [stub | done | edited]
- ...

### Public surface
- <ObjectName>.<RoutineName>(<params>) → <return type> — <one-line purpose>
- <Metadata.Object> — <attribute / tabular section / form name>: <type / role>
- ...

### Open TODOs / stubs (для следующего субагента)
- <file>:<region or routine> — <what to implement> — <signature hint, if pre-agreed>
- ...

### Locked decisions (не пересматривать без согласования)
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
- Module headers (`/// <summary>` or `// Возвращает / Параметры`) are present on new public procedures per `dev-standards-core.md`.

If anything fails — bounce back to stage 3 with a precise delta. If optional 4b is applicable, do not proceed to it until 4a is clean. This is the cheap gate; running 4b before 4a is wasted compute.

### Stage 4b — Code-quality review (delegate to `1c-code-reviewer`, when applicable)

Two important constraints from the existing `subagents.md`:

- The `1c-code-reviewer` subagent runs **only when the user explicitly asks for a code review**. Auto-triggering after every edit is forbidden.
- For non-review-requested tasks, the parent agent still runs `check_1c_code` + `review_1c_code` itself in stage 5 — this is enough for routine work.

When the user asks for a review, the subagent looks at:

- anti-patterns from `anti-patterns.md` and `platform-solutions.md`;
- ITS standards via `its_help` → `fetch_its`;
- BSL LS warnings via `review_1c_code`;
- query patterns, transactional safety, lock granularity, posting boundaries.

The subagent reports issues by severity (critical / major / minor). Critical issues block delivery; minor issues are informational.

### Stage 5 — Verification gate (parent agent)

Run the closing gate from `verification-checklist.md`. This is non-negotiable for full-cycle tasks.

## Anti-patterns of the pipeline

- **Skipping stage 2** "because the change is small" — if it is small, it should have been quick-fix in stage 1.
- **Letting the implementation subagent re-plan** — if the plan turns out wrong, return to stage 2, do not let stage 3 silently rewrite it.
- **Running optional 4b before 4a** — wastes the code-reviewer subagent on a structurally wrong implementation.
- **Auto-triggering `1c-code-reviewer`** — explicitly forbidden by `subagents.md`.
- **Parallelizing stage 3** by default — 1C metadata is densely cross-referenced; parallel subagents on the same configuration tend to corrupt UUIDs and break references. Parallelize only when the subtasks are provably independent (e.g., one new report + one new common-module function with no shared metadata).
- **"I'll just fix this lint while I'm in the file"** during stage 3 — Surgical Changes; report it, do not fix it.

## When to deviate

The pipeline is the default for full-cycle tasks. Deviate only with an explicit reason:

- pure documentation changes — `1c-doc-writer` directly, no plan / dev / review pipeline;
- pure UI test runs against an existing build — `1c-tester` directly;
- a pure architectural review with no code change — `1c-arch-reviewer` directly.

Document the deviation in the delivery summary so the user can audit the choice.
