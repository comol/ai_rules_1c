---
description: Implement tasks from an OpenSpec change (Experimental)
---

Implement tasks from an OpenSpec change.

**Input**: Optionally specify a change name (e.g., `/opsx-apply add-auth`). If omitted, check if it can be inferred from conversation context. If vague or ambiguous you MUST prompt for available changes.

## Question-asking discipline (read first)

Apply phase has a **single consolidated preflight round** at the start, then near-silence during the implementation loop. The user round-trip budget for apply is one batched question round upfront, not one micro-question per task.

- **Preflight (step 5b below)** — bundle every genuine remaining blocker into one `AskUserQuestion` call. Scope: empty highly-desirable `.dev.env` fields needed by tasks in this session's plan, plus `design.md → ## Open Questions` items whose dependent task is in this session's plan. Nothing else.
- **Implementation loop (step 6 below)** — **no mid-loop questions** except: a new fact surfaces from the live state that conflicts with a locked artifact decision (metadata missing, platform-version mismatch with `CompatibilityMode`, БСП subsystem absent, typical-form structure blocks the planned approach); or the user explicitly re-opens a decision. Routine ambiguity in a task ("what name for this private helper?", "function or procedure?", "what level of logging?") is **never** a legitimate mid-loop pause — it is a propose-phase defect that the propose-phase clarification gate should have caught. Make a reasonable, codebase-consistent choice and record it via `remember` or `memory.md` Captured-during-work.
- **The full rule lives in `content/rules/sdd-integrations.md → Apply-phase clarification discipline`. Load it on any non-trivial apply session.**

## Banned questions at apply time (hard list)

These questions MUST NEVER be asked during apply, regardless of whether the corresponding `.dev.env` field is empty. Asking any of them is an apply-phase defect — apply the documented fallback silently and proceed.

- **`PREFIX`** — Advisory. Empty = create new objects without a prefix; `{PREFIX}` placeholder resolves to empty string. Do not ask, do not announce the fallback.
- **`COMPANY`** — Advisory. Empty = do not emit `// +++ {COMPANY}; …` / `// --- {COMPANY}; …` modification markers in any module. Do not ask.
- **`DEVELOPER`** — Advisory. Empty = same as `COMPANY`, no markers. Do not ask, do not invent a placeholder developer name.
- **`{TASK}` number** — Required only when markers are emitted. With empty `COMPANY` or `DEVELOPER` markers are not emitted at all → `{TASK}` is irrelevant. Do not ask. Ask only when markers ARE being emitted (both fields non-empty) AND `{TASK}` is the only missing piece.
- **`INFOBASE_PATH` / `PLATFORM_PATH`** for the deploy / smoke-test block — do **not** ask pre-emptively when the IB-bound task block is not the **next** step. Mark the dependent block as `deferred-to-user` in `tasks.md`, finish every non-IB-bound task first, then state once in the closing summary that the deploy block is deferred until the value is provided. `IB_USER` / `IB_PASSWORD` / `LOG_PATH` are **Defaulted** — never ask, even when the IB-bound block is next: empty `IB_USER` / `IB_PASSWORD` = no authentication / no password, empty `LOG_PATH` = `$env:TEMP\1cv8.log`. Re-ask `IB_USER` / `IB_PASSWORD` only if the command later returns an auth error.
- **`INFOBASE_PUBLISH_URL`** — only ask when UI-test tasks are explicitly in scope and next on the queue. Otherwise UI tests are silently skipped.

If the artifact (`design.md` / `proposal.md`) explicitly **requests** a prefix / a marker style / a specific developer name (overriding the global `.dev.env` default), follow the artifact — that is a locked decision, not a question. The ban above only covers asking the user **at apply time** when the value is empty in `.dev.env` and no artifact pins it.

The `## Genuine blockers` block in the opening message lists only blockers that pass this filter; if every candidate falls into the banned list above, the block is empty and the agent proceeds straight to implementation. See `content/rules/sdd-integrations.md → Apply-phase clarification discipline → Banned questions at apply time` for the full rule and rationale.

## Required format for Open Questions: CONFUSION block

Items from `design.md → ## Open Questions` are **unresolved by definition** — the design phase deliberately deferred them to the user. The parent agent does **not** have authority to close them unilaterally at apply time. The only legitimate closure path is a `CONFUSION` block per `AGENTS.md → Development Procedure → 1. Think Before Coding`, then wait for the user's choice.

A self-justifying paragraph that picks an option ("принимаю минимальный и обратимый вариант — добавляем в роли X и Y") is a defect of the same severity as bypassing `syntaxcheck`, even if the option is genuinely the best one. **Doubly so** when the picked option modifies typical (standard) configuration objects — typical roles (`Roles\<типовая_роль>\Ext\Rights.xml`), typical forms, typical modules, typical event subscriptions — because that silently modifies the standard config without authorisation.

Required `CONFUSION` shape for an Open Question (verbatim from `AGENTS.md → 1.`):

```text
CONFUSION: <Open Question quoted from design.md>
Options:
A) <option> — <consequences / compatibility / scope / risk / cost>
B) <option> — <consequences / compatibility / scope / risk / cost>
C) <option, if any> — <…>
→ Which one to pick?
```

The agent MAY include its own preference inside the block as a recommendation ("Recommendation: B — minimal and reversible"), but the block ends with the explicit question, not with a decision. Implementation of the dependent task block does not start until the user answers.

**Steps**

1. **Select the change**

   If a name is provided, use it. Otherwise:
   - Infer from conversation context if the user mentioned a change
   - Auto-select if only one active change exists
   - If ambiguous, run `openspec list --json` to get available changes and use the **AskUserQuestion tool** to let the user select

   Always announce: "Using change: <name>" and how to override (e.g., `/opsx-apply <other>`).

2. **Check status to understand the schema**
   ```bash
   openspec status --change "<name>" --json
   ```
   Parse the JSON to understand:
   - `schemaName`: The workflow being used (e.g., "spec-driven")
   - Which artifact contains the tasks (typically "tasks" for spec-driven, check status for others)

3. **Get apply instructions**

   ```bash
   openspec instructions apply --change "<name>" --json
   ```

   This returns:
   - Context file paths (varies by schema)
   - Progress (total, complete, remaining)
   - Task list with status
   - Dynamic instruction based on current state

   **Handle states:**
   - If `state: "blocked"` (missing artifacts): show message, suggest using `/opsx-continue`
   - If `state: "all_done"`: congratulate, suggest archive
   - Otherwise: proceed to implementation

4. **Read context files**

   Read the files listed in `contextFiles` from the apply instructions output.
   The files depend on the schema being used:
   - **spec-driven**: proposal, specs, design, tasks
   - Other schemas: follow the contextFiles from CLI output

5. **Show current progress and emit the opening message (preflight round)**

   a. Display:
   - Schema being used
   - Progress: "N/M tasks complete"
   - Remaining tasks overview
   - Dynamic instruction from CLI

   b. **Emit the apply-phase opening message** following the template in `content/rules/sdd-integrations.md → Apply-phase opening template`:

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

   c. **Preflight scope filter** — for each candidate question, include in `## Genuine blockers` only if it passes **all** of:
   - **Not** in the "Banned questions at apply time" hard list above.
   - **Not** answered in `proposal.md` / `design.md` / delta `specs/` / `tasks.md` (those decisions are locked — quote them in `## Locked from artifacts` instead).
   - **Not** an advisory field (`PREFIX`, `COMPANY`, `DEVELOPER`) or a defaulted field (`INFOBASE_KIND`, `EXTENSION_NAME`, `EXPORT_PATH`, `NEW_OBJECTS_IN`, `IBCMD_CONFIG`).
   - **In scope of the current session's plan** — required by a task that this apply run will actually reach.

   d. **If `## Genuine blockers` is empty** after the filter — omit the block entirely and proceed straight to step 6. An empty block is not a question.

   e. **If `## Genuine blockers` is non-empty** — submit the consolidated `AskUserQuestion` round (one call, all questions in it). On the user's response, apply the answers to the artifacts: write resolved Open Questions into `design.md → ## Architecture decisions` and strike them from `## Open Questions`; persist `.dev.env` values. Then enter the implementation loop. **The preflight round is the only apply-time question surface** — no further `AskUserQuestion` calls during step 6 except for the narrow critical exceptions below.

6. **Run the 1C pipeline and implement tasks (loop until done or blocked)**

   Before the first edit, load `content/rules/subagent-pipeline.md` and
   `content/rules/verification-checklist.md`, then classify the current session plan using
   `AGENTS.md → Triage`. Quick-fix / docs-fix / spec-authoring work follows its dedicated
   route. Full-cycle work runs either the standard path (direct execution by the parent per
   `AGENTS.md → Development Procedure`) or the pipeline when delegation is chosen per
   `content/rules/subagents.md` (the default under `ORCHESTRATION=economy`). Either way the
   approved OpenSpec artifacts are the approved plan — do not ask for duplicate approval —
   and the spec-compliance review (pipeline Stage 4a) plus the closing verification gate
   (`verification-checklist.md`) still run.

   For each pending task:
   - Show which task is being worked on
   - Make the code changes required
   - Keep changes minimal and focused
   - Run the task-local checks named in `tasks.md` and retain fresh validator evidence
   - Record the task as implemented, but leave `- [ ]` unchanged until step 7 passes
   - Continue to next task

   **Mid-loop pause is reserved for true live-state surprises only.** Pause if **and only if**:
   - **New fact from live state conflicts with a locked artifact decision** — metadata object missing from this configuration, platform-version mismatch with `CompatibilityMode`, БСП subsystem absent, typical-form structure blocks the planned approach, an attribute / tabular-section actual type contradicts what `design.md` assumed. Raise a `CONFUSION` block per `AGENTS.md → 1.` with the new fact, the locked artifact it contradicts, and the resolution options. This is the only routine reason to pause mid-loop.
   - **User-explicit re-open** — the user asks to revisit a previously locked decision.
   - **Error or hard blocker** — a tool / build / validator returns a result that genuinely blocks progress (not a style warning, not a routine BSL defect — fix those and continue).
   - **User interrupts** — obvious.

   **Forbidden mid-loop pauses** (each is an apply-phase defect of the same severity as skipping `syntaxcheck`):
   - "Task is unclear" — propose-phase defect. Make a reasonable, codebase-consistent choice and record it via `remember` (project memory) or `memory.md` Captured-during-work. Do not interrupt the user.
   - "What name for this private helper?" / "function or procedure?" / "what logging level?" / "should I add a comment here?" — same.
   - "Should I pause now to re-confirm decision X from `design.md`?" — never. Confirmation is not a question.
   - "Should I pause for an empty `.dev.env` field that the user already declined in preflight?" — never. The dependent block is marked `deferred-to-user` in `tasks.md`; proceed with everything else.

7. **Run spec-compliance and closing verification**

   Before marking any implemented task complete:
   - Run Stage 4a from `content/rules/subagent-pipeline.md` against the implemented task set.
   - Run Stage 4b only when the user explicitly requested a code review.
   - Run Stage 5 via `content/rules/verification-checklist.md`, including every applicable hard
     and soft gate.
   - Reuse fresh validator evidence produced after the latest edit. Run only missing or stale
     gates; never repeat a validator against unchanged content.
   - If a gate finds a defect, fix it and rerun only the affected stale gate within its budget.
     If verification is blocked, keep the affected tasks unchecked and report the blocker.
   - Only after Stage 4a and the closing gate pass, update each verified task:
     `- [ ]` → `- [x]`.

8. **On completion or pause, show status**

   Display:
   - Tasks completed this session
   - Overall progress: "N/M tasks complete"
   - If all done: suggest archive
   - If paused: explain why and wait for guidance

**Output During Implementation**

```
## Implementing: <change-name> (schema: <schema-name>)

Working on task 3/7: <task description>
[...implementation happening...]
Implementation complete; closing verification pending

Working on task 4/7: <task description>
[...implementation happening...]
Implementation complete; closing verification pending
```

**Output On Completion**

```
## Implementation Complete

**Change:** <change-name>
**Schema:** <schema-name>
**Progress:** 7/7 tasks complete ✓
**Verification:** Stage 4a and all applicable closing gates passed

### Completed This Session
- [x] Task 1
- [x] Task 2
...

All tasks complete! You can archive this change with `/opsx-archive`.
```

**Output On Pause (Issue Encountered)**

```
## Implementation Paused

**Change:** <change-name>
**Schema:** <schema-name>
**Progress:** 4/7 tasks complete

### Issue Encountered
<description of the issue>

**Options:**
1. <option 1>
2. <option 2>
3. Other approach

What would you like to do?
```

**Guardrails**
- Keep going through tasks until done or blocked
- Always read context files before starting (from the apply instructions output)
- **Bundle every legitimate question into the single preflight round at step 5b — no mid-loop questions except for the narrow critical exceptions in step 6.** "If task is ambiguous, pause and ask" is **not** the apply rule for this project — the rule is in `content/rules/sdd-integrations.md → Apply-phase clarification discipline`. Routine ambiguity is a propose-phase defect; make a reasonable, codebase-consistent choice and record it via `remember` or `memory.md` Captured-during-work.
- If a live-state fact conflicts with a locked artifact decision, raise a `CONFUSION` block and pause; this is the only routine mid-loop pause.
- Keep code changes minimal and scoped to each task
- Load `subagent-pipeline.md` and `verification-checklist.md` before the first edit
- Update task checkboxes only after step 7 passes; implementation alone is not completion
- Pause on hard errors / blockers (failing validator with a substantive defect, missing metadata, deadlock), never on routine style warnings or naming choices
- Use contextFiles from CLI output, don't assume specific file names

**Fluid Workflow Integration**

This skill supports the "actions on a change" model:

- **Can be invoked anytime**: Before all artifacts are done (if tasks exist), after partial implementation, interleaved with other actions
- **Allows artifact updates**: If implementation reveals design issues, suggest updating artifacts - not phase-locked, work fluidly
