---
description: Verification delivery gates — reproduction, plan adherence, full-cycle review, UI confirmation, and final report
alwaysApply: false
category: quality
---

# Verification Delivery — Soft Gates and Reporting

**When to load this file:** after the hard gates of a full-cycle change — for reproduction, plan adherence, testing, review or delivery. A quick-fix delivery is defined by `verification-policy.md → Quick-fix gate`.

Hard validator, impact, and XML gates live in `verification-gates.md`; task depth and triage live in `verification-policy.md`.

## Soft gates — run when applicable

These gates are not always required, but their absence in the listed scenarios is a defect.

### Soft gate A — Reproduction case (debug tasks only)

For any change that originated as a bug fix:

- The exact reproduction case from `standards(name="systematic-debugging") → Phase 1` was rerun **after** the fix and no longer triggers the symptom. For fast-path fixes (`standards(name="systematic-debugging") → Fast path`) the original failing scenario (from the error message, the user's report, or the log entry) serves as the reproduction case — re-check it after the fix.
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
- OpenSpec: reconcile DoD with current verification/review evidence before completion (`sdd-apply.md`). Checkboxes and CLI `all_done` alone never suffice; record explicit waivers and unfinished criteria. A behaviour change the deltas do not describe goes through `/opsx:update`, never a silent delta edit.
- For the subagent pipeline specifically: Stage 4a (spec-compliance review by the parent agent) was executed and passed before Stage 5. **Reuse its evidence** — when 4a passed after the latest edit, this gate is satisfied by confirming that result is still fresh; do not re-run the file-by-file diff comparison (same principle as `verification-gates.md → "Gate execution and evidence reuse"`).

### Soft gate C — Code review

Full-cycle: review is required unless the user explicitly prohibits it; otherwise only when requested. The parent reviews requirements, correctness, regressions and security. Invoke `1c-code-reviewer` only on explicit request with the reviewer model gate satisfied (`subagents.md`). Fix critical / major findings; report minor ones. Reuse fresh evidence. Disabling the subagent does not waive review or MCP gates.

### Soft gate D — UI confirmation policy

Behaviour needs expected-vs-actual evidence (Gate 3a or UI), not static checks/review alone. `/uitests` sets `UI_TESTING`: `essential` / empty = the important new or changed user-visible behaviour, automatically once the change is on the dev/test base; `auto` = every applicable scenario automatically; `manual` = explicit request; `off` = disabled. Routes: QA MCP first, the web client (`INFOBASE_PUBLISH_URL`) as fallback. Canon: `dev-standards-env.md`; routes and drivers: `ui-testing-tools.md`. Unconfirmed DoD-linked scenarios stay unverified.

## Full-cycle Definition of Done

A full-cycle change is done when all three hold on the final artifact state:

1. every acceptance criterion of the task has expected-vs-actual evidence — a hard-gate result, a Gate 3a check, UI confirmation where the criterion is user-visible (Soft gate D), or the rerun reproduction case;
2. the applicable hard gates of `verification-gates.md` passed;
3. the final review ran (Soft gate C).

Report each criterion as `passed`, `failed`, `blocked / unverified` or `waived by user`. Only the user waives UI confirmation or review, and waiving one waives nothing else; a depth setting, `UI_TESTING=off`, a disabled reviewer subagent or a missing tool is not a waiver. Anything short of this is reported as partial work with the open criteria named. When the change runs through OpenSpec, the artifacts carry the same contract — `sdd-integrations.md → Full-cycle Definition of Done`.

## Delivery summary — what the user sees

After all gates pass, the delivery report MUST contain:

1. **What was done** — 1–3 lines, no preamble.
2. **Files changed** — every path in backticks, one line per file describing the nature of the change.
3. **Context sources** — required for non-trivial BSL / metadata changes (per `mcp-policy.md → A.3`). List the sources actually used (templates, project code, metadata, platform / БСП / ITS docs, ITS standards) and briefly state why any normally relevant source was skipped. Skipping a relevant source silently counts as a defect. Omit this section only for docs-fix / quick-fix tasks where no BSL / metadata change was made.
   - **Metadata tooling** — when the change mutated metadata / forms / layouts, one line naming the execution path: `Metadata tooling: <1c-metadata-manage tool / 1c-metadata-manager>` or `hand-edit — <documented exception>` (hard gate — `AGENTS.md → Skills and Subagents`, exceptions — `content/skills/1c-metadata-manage/SKILL.md → Hard rule`). Name a preview only when one actually ran (`… (preview shown, then applied)` — `content/skills/1c-metadata-manage/docs/edit-preview.md`). Most writes carry no preview clause (`METADATA_PREVIEW=auto` reserves it for the risky cases), and its absence is not a gap.
   - **Docs** — when a claim about platform behaviour, an API signature or a development standard came from documentation rather than from the project's own code, one line naming what answered and for which platform: `Docs: docsearch "ЗначениеЗаполнено" → ОбщегоНазначения (8.3.27)`, `Docs: standards(name="dev-standards-code-style")`, `Docs: its_help + fetch_its <document>`. The point is that the reader can reopen the same page: name the tool and the document, not "the documentation says". A version-sensitive answer without a platform version is incomplete — say which version the page applied to, and say so explicitly when it differs from the project's. Omit the line only when no documentation was consulted, which for a version-sensitive claim is itself a gap worth stating under **Risks**.
4. **Risks / nuances** — only real ones. For tool-dependent gaps name the `TOOL_*` policy, actual state (disabled / absent / failed / unsuitable scope), fallback evidence and remaining unverified requirement. `required` remains incomplete; `off` is never reported as a passing check. Use `verification-gates.md` wording for degraded gates. Omit when no risk applies.
5. **Follow-ups** — any defects observed but **not** fixed (out-of-scope dead code, pre-existing lints, downstream callers flagged by Gate 4 that need future review). Empty = omit.

**Evidence lines are conditional, never placeholders.** Each of `Memory:`, `Template:`, `Typical reuse:`, `Docs:`, `Metadata tooling:`, `IB tooling:`, `Repository tooling:` appears only when its channel applied to this task: `Memory:` on every non-trivial task (`project-memory.md → Gates (hard)`); `Template:` whenever `templatesearch` ran or was owed (`mcp-policy.md → A.9`, including «no fitting template»); `Typical reuse:` for each new helper covered by `coding-standards.md → Check reuse before a new helper`, using `<method> — <source/query> → reused <public API> | not found | rejected: <reason> | limited: <unavailable source and remaining gap>` (only an actual search supports "not found"); `Docs:` when documentation answered a claim; the three tooling lines only when a metadata mutation, infobase operation or repository operation happened. Never write `IB tooling: n/a` or similar filler — an absent line already means «not applicable». A typical quick-fix delivery is: what was done, the file, the validators run, the `Memory:` line, and Risks only if real.

Do not include in the delivery summary:

- a retelling of the user's request;
- a list of which tools you called (unless that list IS the **Context sources** section above);
- thanks, apologies, introductions, conclusions;
- markdown sections added "for structure" with no content.

**Package instead of an edit.** When a person must apply the change (vendor lock kept, ordinary form, repository lock held by someone else, MCP-only sources) or the user asks for a diff / review, the deliverable is the package of `content/skills/1c-change-package/SKILL.md`.
