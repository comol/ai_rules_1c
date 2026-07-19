---
description: Verification delivery gates — reproduction, plan adherence, explicit review, UI testing, final report, and anti-patterns
alwaysApply: false
category: quality
---

# Verification Delivery — Soft Gates and Reporting

**When to load this file:** after the applicable hard gates have run, when checking reproduction / plan adherence / optional review / UI testing or preparing the final delivery report.

Hard validator, impact, and XML gates live in `verification-gates.md`; task depth and triage live in `verification-policy.md`.

## Soft gates — run when applicable

These gates are not always required, but their absence in the listed scenarios is a defect.

### Soft gate A — Reproduction case (debug tasks only)

For any change that originated as a bug fix:

- The exact reproduction case from `systematic-debugging.md → Phase 1` was rerun **after** the fix and no longer triggers the symptom. For fast-path fixes (`systematic-debugging.md → Fast path`) the original failing scenario (from the error message, the user's report, or the log entry) serves as the reproduction case — re-check it after the fix.
- The reproduction case is documented in the delivery summary so the user can verify it.
- All temporary `ЗаписьЖурналаРегистрации("Debug.*"`, `ПоказатьЗначение`, breakpoints, hard-coded test values introduced during debugging were removed.

### Soft gate B — Plan adherence (any change with a written plan)

Triggers — apply this gate when any of the following is true:

- The change went through `subagent-pipeline.md` (Stage 4a "spec-compliance review").
- The change is an OpenSpec **apply** of an active proposal — there is a `openspec/changes/<id>/tasks.md` (and optionally `design.md` / `proposal.md` / delta `specs/`).
- The user explicitly approved a written plan in chat before implementation (numbered steps, file paths, verification points).

Checklist (same shape regardless of plan source):

- Every task / step in the plan was executed; no task was silently skipped.
- The diff against the plan was summarized file by file in the delivery report (use `git diff --name-only` to verify).
- No file outside the plan was edited; if it was, the deviation is explicitly justified in the delivery summary.
- For OpenSpec specifically: `tasks.md` ticks reflect actual completion; spec deltas under `changes/<id>/specs/` are updated when behaviour observably changed (per `sdd-integrations.md`).
- For the subagent pipeline specifically: Stage 4a (spec-compliance review by the parent agent) was executed and passed before Stage 5. **Reuse its evidence** — when 4a passed after the latest edit, this gate is satisfied by confirming that result is still fresh; do not re-run the file-by-file diff comparison (same principle as `verification-gates.md → "Gate execution and evidence reuse"`).

### Soft gate C — User-explicit code review (only when user asks)

Only on an explicit user request (canon — `subagents.md`): invoke `1c-code-reviewer`, address critical / major issues before delivery, summarize minor ones. Without such a request gates 2–3 already cover the routine quality bar — never auto-trigger the reviewer.

### Soft gate D — UI testing (configurable, off by default)

Web UI testing (`1c-tester` / `/deploy-and-test` Step 4) is opt-in, gated by `UI_TESTING` in `.dev.env` — canon: `dev-standards-env.md §1 → "UI_TESTING — web UI-testing mode"` (`manual` / empty = only on an explicit user request; `auto` = routine step when `INFOBASE_PUBLISH_URL` is set; `off` = never). Not running UI tests is not a gate failure and needs no **Risks** note when no run was requested; the static hard gates in `verification-gates.md` remain the quality baseline.

## Delivery summary — what the user sees

After all gates pass, the delivery report MUST contain:

1. **What was done** — 1–3 lines, no preamble.
2. **Files changed** — every path in backticks, one line per file describing the nature of the change.
3. **Context sources** — required for non-trivial BSL / metadata changes (per `AGENTS.md → MCP Tool Calling → A.3`). List the sources actually used (templates, project code, metadata, platform / БСП / ITS docs, ITS standards) and briefly state why any normally relevant source was skipped. Skipping a relevant source silently counts as a defect. Omit this section only for docs-fix / quick-fix tasks where no BSL / metadata change was made.
4. **Risks / nuances** — only real ones. If any gate fell back to graceful-degradation mode (validator or impact-analysis MCP not exposed — see `verification-gates.md` Gates 1–4), record it here verbatim. If there are no real risks, omit the section.
5. **Follow-ups** — any defects observed but **not** fixed (out-of-scope dead code, pre-existing lints, downstream callers flagged by Gate 4 that need future review). Empty = omit.

Do not include in the delivery summary:

- a retelling of the user's request;
- a list of which tools you called (unless that list IS the **Context sources** section above);
- thanks, apologies, introductions, conclusions;
- markdown sections added "for structure" with no content.

## Anti-patterns

- **Skipping Gate 1** "because the edit was tiny" — `syntaxcheck` is the cheapest gate; skipping it never saves time.
- **Running gates in the wrong order** — running `check_1c_code` before `syntaxcheck` wastes the AI checker on syntax-broken code.
- **Looping on AI non-determinism** — if `check_1c_code` returns different items each run on the **same** code, take the strictest set and stop. Do not burn the 3-call budget on noise.
- **Marking the task done** with un-removed `Debug.*` log entries or temporary `ПоказатьЗначение` calls — soft gate A failure.
- **Auto-running `1c-code-reviewer`** when the user did not ask — soft gate C failure, and a direct violation of `subagents.md`.
