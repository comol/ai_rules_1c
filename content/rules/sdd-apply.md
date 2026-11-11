---
description: "OpenSpec apply phase — apply until the Definition of Done is satisfied, locked artifact decisions, one preflight question round, archive readiness. Load for /opsx:apply, /opsx:archive, /opsx:sync or when implementing an openspec change."
alwaysApply: false
category: integrations
---

# OpenSpec — apply phase

Router, artifact ownership and the Definition of Done contract — `content/rules/sdd-integrations.md`. Propose-phase rules (authoring artifacts, MCP evidence for spec facts) live in `content/rules/sdd-propose.md` and are not needed while applying.

## Apply until DoD is satisfied

1. Read the DoD and linked specs along with the CLI context. Include outstanding verification in the execution plan even when every implementation task is checked. CLI `all_done` and completed checkboxes describe task tracking; they are not evidence that DoD passed. Inspect current evidence before emitting completion or suggesting archive.
2. Implement and run the applicable gates and planned behavioural confirmation against the current artifact, including UI checks when permitted. Honour infobase authorization and `UI_TESTING` policy; if a DoD-linked scenario cannot be verified through an allowed method, leave it open and report the exact missing prerequisite. Continue independent work. Do not invent a pass, silently shrink coverage, or bypass a disabled tool.
3. Perform a final change review unless explicitly prohibited by the user: requirements, correctness, regressions and security/data integrity. The parent owns this by default; `1c-code-reviewer` still requires an explicit review request and the reviewer model gate (`subagents.md`). For each new helper covered by `coding-standards.md → Check reuse before a new helper`, confirm its `Typical reuse:` evidence; if missing, perform 1–2 targeted searches or state the actual source limitation. Existing fresh review evidence may be reused; MCP style review alone does not establish acceptance.
4. Fix in-scope verification failures and blocking review findings; confirm the affected checks on the changed state within `verification-policy.md` budgets. A later edit invalidates affected evidence. Exhausted budgets, failed checks and unavailable required evidence leave DoD incomplete; they do not become waivers.
5. Reconcile every DoD criterion with evidence in `tasks.md`: criterion ID, checked artifact state, check/review performed, expected vs actual result and log/report reference. Use `passed`, `failed`, `blocked/unverified` or `waived by user`. Check a verification task only after its obligation was performed, or annotate an explicitly waived task so a checkbox cannot be mistaken for a pass.

Declare apply complete and suggest archive only when every criterion is passed or explicitly waived within the user's scope, and all mandatory gates are satisfied. Report verification results, review verdict and any waivers. Otherwise report partial implementation and the remaining criteria. Delivering partial work under a tool's graceful-degradation rule does not establish DoD completion or archive readiness. `/opsx:archive` must check the same evidence before describing a change as complete; an explicit request to archive unfinished work must retain its incomplete status and gaps.

**Approved requirements are not rewritten to fit the code.** When the implementation shows that a delta spec, a DoD criterion or a design decision must change, report it to the parent and the user; the artifact changes only through `/opsx:update`, which the user authorizes.

## Apply-phase clarification discipline

`/opsx:apply` runs against approved artifacts — **their decisions are locked**. Apply implements them; it does not re-litigate them. The approved artifacts also satisfy the plan-approval gate of the subagent pipeline (`subagent-pipeline.md → Stage 2 → Plan approval gate`) — apply never runs a separate plan-approval round on top of them. This section kills two recurring failure modes: re-asking what `design.md` / `proposal.md` already records, and dribbling questions across the implementation loop instead of one consolidated preflight round.

**This section outranks the bundled OpenSpec apply skill on when to pause.** Where that skill says to pause and ask on an unclear or ambiguous task, pause only in the cases under *Legitimate apply-phase pauses* below; routine ambiguity is resolved from the artifacts and the codebase.

### Read first, then ask

Before raising any apply-time clarification, check whether it is already answered: decisions in `design.md` (architecture, placement, storage, transactional boundaries, error handling, logging, БСП subsystem), requirements in delta `spec.md`, `Out of scope` / `Non-goals` / `Constraints`, providers / defaults in `proposal.md` — all **locked**. `design.md → ## Open Questions` is the only legitimate apply-time question surface, and only when the dependent task is actually next. If the answer is in the artifacts — quote the locked decision in one line and continue. Disagreeing with a locked decision is not a clarification — it is a request to amend the artifact, which the user must explicitly authorize.

### Preflight round (single consolidated batch at apply start)

Immediately after reading the context files and **before** any code, run a **single** preflight round consolidating every remaining legitimate question into one question message (the host's question tool where it has one):

- every empty highly-desirable `.dev.env` field required by a task in this session's plan (fields needed only by tasks this session will not reach → defer those task blocks instead — see the banned list);
- every `design.md → ## Open Questions` item whose dependent task is in this session's plan — quote it verbatim, then a `CONFUSION` block with options and consequences;
- **nothing else.** A candidate outside these two buckets belongs in propose (its absence there is a propose defect) or nowhere (banned / defaulted / advisory).

The round corresponds exactly to the `## Genuine blockers` block of the opening template below; if that block is empty, there is no preflight round at all. After the answers: update `.dev.env`, write resolved items into `design.md → ## Architecture decisions` and strike them from `## Open Questions`, then enter the implementation loop. **The loop asks no more questions** except the critical exceptions below.

### Legitimate apply-phase pauses

A mid-loop pause-and-ask is justified **only** by:

- **A new fact from the live state conflicting with a locked artifact decision** — a metadata object missing from this configuration, a `CompatibilityMode` mismatch, an absent БСП subsystem, a typical-form structure or actual attribute type that blocks the planned approach. State the conflict concretely as a `CONFUSION` block.
- **User-explicit re-open** of a previously locked decision.

Everything else is handled without pausing: a `.dev.env` field the preflight did not cover because its task was outside the session plan — defer that task (`deferred-to-user` in `tasks.md`), continue with the rest, surface the deferred block once in the closing summary; an Open Question triggered by a task outside the session plan — almost always a session-planning defect, widen the next preflight instead of pausing; routine ambiguity (helper name, function vs procedure, log level) — make a codebase-consistent choice, record it via `remember` (`project-memory.md`) when it should hold for later sessions, move on.

### Forbidden at apply time

- Re-asking about provider / trigger / data scope / settings storage / placement / key handling / module placement / role grants / БСП subsystem / transactional boundaries settled in `proposal.md` or `design.md`.
- Bundling a `.dev.env` audit (empty fields **only**) with locked-decision re-asks — different gates, never mixed.
- Asking about a default that `design.md` already names, or offering options A / B / C when `## Architecture decisions` already picked one with a written rationale.
- Pausing on a non-blocking item "just to confirm" — if the artifact says X, do X.
- **Closing an `## Open Questions` item with a self-justifying paragraph instead of a `CONFUSION` block.** Open Questions are unresolved by definition; the agent has no authority to close them unilaterally — doubly so when the picked option modifies typical (standard) configuration objects (roles, forms, modules, event subscriptions). Implementation of the dependent task block waits for the user's explicit choice.

### Banned questions at apply time — hard list

These questions MUST NEVER be asked during `/opsx:apply`, regardless of whether the corresponding `.dev.env` field is empty — the documented fallback is applied silently, no pause, no question. Classification canon — `dev-standards-env.md`.

| Banned question | Instead |
|---|---|
| Value of `PREFIX` (Advisory) | Create objects without a prefix; `{PREFIX}` resolves to empty. Do not announce the fallback — just proceed. |
| Value of `COMPANY` / `DEVELOPER` (Advisory) | Emit no modification markers; do not invent placeholder names. |
| `{TASK}` number for modification comments | Markers are emitted only when `COMPANY` **and** `DEVELOPER` are non-empty; only then, if `{TASK}` alone is missing — ask once for `{TASK}` only, never bundled with Advisory fields. |
| `INFOBASE_PATH` / `PLATFORM_PATH` when no IB-bound step is in this session's plan; `INFOBASE_PUBLISH_URL` unless the user explicitly requested a UI run that has no other route | Defer the dependent task block (`deferred-to-user` in `tasks.md`), finish all non-IB-bound tasks, state the deferral once in the closing summary. |
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
