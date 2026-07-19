---
description: Aggregate accumulated rule-friction signals into user-approved behavior rules in LLM-RULES.md (ruleset self-improvement loop)
argumentHint: "[note <text>|show]"
---

# /evolve — ruleset self-improvement via LLM-RULES.md

Turn friction observed during work (user corrections of agent behavior, demonstrably redundant mandated steps, conflicting rules) into explicit, user-approved rules in `LLM-RULES.md` at the project root.

This command is the **only** legitimate writer of `LLM-RULES.md`. During regular tasks agents never edit it, `AGENTS.md`, or the installed rule files inline — they capture friction signals and, when signals accumulate, recommend running this command. The capture discipline and the recommendation trigger are canon in `AGENTS.md → Rules self-improvement`; this file owns everything from aggregation onward.

Precedence reminder: `LLM-RULES.md` overrides `AGENTS.md` and the on-demand rules; `USER-RULES.md` and `memory.md` override `LLM-RULES.md`.

Parse the argument: empty — full pass (collect → cluster → propose → approve → write); `note <text>` — record one friction signal and stop; `show` — report the current state, no writes.

## Full pass (default)

### 1. Collect signals

Gather friction signals from, in order:

1. **Current session** — corrections and steers the user gave in this chat that contradict or refine behavior mandated by the active ruleset.
2. **`recall`** (`1c-templates-mcp`, only when exposed) — query for `rule-friction` notes; refine with behavior keywords if the first query is too broad. Respect the no-blind-chaining discipline of `AGENTS.md → MCP Tool Calling → C`.
3. **`memory.md → ## Captured during work`** — behavior-steering entries recorded while `remember` was unavailable.
4. **User input** passed with the command invocation.

Skip episodes already consumed by an earlier pass: consumed episodes are cited in the `Evidence` lines of existing `LLM-RULES.md` entries, and notes older than the `Last /evolve run:` date are suspect — re-check them against existing entries before reuse.

### 2. Cluster and apply the evidence threshold

- Group signals by the behavior they target (the same re-asked question, the same redundant step, the same naming correction), one cluster → at most one proposed entry.
- **Threshold:** ≥ 2 independent episodes → propose. A single episode is proposable only when the user explicitly requested a permanent change ("always…", "never…", "запомни…") — otherwise keep it as **pending**: report it in the closing summary, write nothing.
- A proposal that conflicts with `USER-RULES.md` or `memory.md` is not proposed at all — those layers outrank `LLM-RULES.md`. Report the conflict instead.

### 3. Protected areas — higher bar

Proposals that **weaken** any of the following are safety-relevant: the verification chain (`syntaxcheck` / `check_1c_code` / `review_1c_code`, validator budgets, the verification-checklist gates), transactions / locks discipline, security / RLS / secrets / PII handling, `CONFUSION` gates on material forks, MCP evidence gates for BSL / metadata / spec authoring.

For such proposals:

- mark the entry `[safety-relevant]` and present it **separately** — never bundled into a blanket "approve all" with routine entries;
- state what the weakened gate currently catches and what will catch it instead;
- prefer narrowing the scope or introducing a `.dev.env` parameter (the `VERIFICATION_DEPTH` / `QUICKFIX_MAX_LINES` pattern) over deleting or relaxing the rule text;
- never propose a blanket disable of a verification or safety mechanism.

The model is a poor judge of the usefulness of gates that constrain the model — that asymmetry is exactly why this section exists.

### 4. Approval gate

Present every surviving proposal as a numbered list; per proposal: the rule text, scope, evidence episodes (one line), what base rule or `AGENTS.md` section it refines or overrides, and the `[safety-relevant]` flag where applicable. Then one consolidated question round with per-entry approve / reject / edit. Safety-relevant entries require their own explicit confirmation.

No approval — no write. For rejected proposals, record one `remember` note (`rule-friction: rejected — <behavior>`) so the same proposal is not re-raised from the same episodes.

### 5. Write to `LLM-RULES.md`

If the file is absent (older install), create it first with the template structure: the `# LLM Rules` title with its one-line pointer, the `Last /evolve run:` line, `## Active rules`, `## Superseded`.

Entry format (English, imperative, original 1C identifiers as-is, no secrets / PII):

```markdown
### R-007 — <short title> (YYYY-MM-DD)

- **Rule:** <imperative behavior rule>
- **Scope:** <when / where it applies>
- **Evidence:** <episodes in one line>
- **Refines:** <`AGENTS.md → <section>` / `<rule-file>.md` / none>
```

- Ids are sequential `R-NNN` across the whole file, including superseded entries.
- **Dedupe on write:** a proposal targeting the same behavior as an existing active entry merges into it (update the text, extend `Evidence`); a proposal contradicting an existing entry **replaces** it — move the old entry under `## Superseded` with a `Superseded by R-NNN (YYYY-MM-DD)` line. Two conflicting active entries must never coexist.
- Update the `Last /evolve run:` line to today's date.
- **Entropy budget:** when active entries exceed ~20, the pass must open with a consolidation proposal (merge, generalize, or retire entries) before any new entry is added.

### 6. Post-run

- Delete `memory.md → ## Captured during work` items now represented by written entries (migration, per `AGENTS.md → Project memory`).
- Closing summary in Russian: entries written, merged, superseded; proposals rejected; pending signals below the threshold.
- **Upstream hint:** if an approved rule is not project-specific (it would improve the base ruleset for every project), say so — the fix belongs in the `1c-rules` source repo (`AGENTS.md` / `content/rules/**`) through its normal change process; `LLM-RULES.md` stays the project-local layer either way.

## note <text>

Record one friction signal without running the pass: a single self-contained `remember` note prefixed `rule-friction:` — target behavior / rule, what happened, date (fallback when `remember` is not exposed: `memory.md → ## Captured during work`). Confirm in one line; no other writes.

## show

Read-only report: active `LLM-RULES.md` entries (ids + titles), `Last /evolve run:` date, pending friction signals found via `recall` / `memory.md`, and whether the recommendation threshold (≥ 2 signals for one behavior) is currently met.

## Constraints (always)

- The command writes **only** `LLM-RULES.md` (plus the `memory.md` migration and `remember` notes described above) — never `AGENTS.md`, `USER-RULES.md`, `content/rules/**`, installed rule copies, or `.dev.env`.
- Every written entry has explicit per-entry user approval from this run; editing or removing an existing entry also goes through the approval round.
- The command never runs unasked. Recommending it during regular work is one line at the end of an answer, at most once per session (canon — `AGENTS.md → Rules self-improvement`).
