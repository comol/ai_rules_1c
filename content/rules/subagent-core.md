---
description: Common obligations of every 1C subagent — CONFUSION, MCP-first search, mutation gates, validator evidence, done criteria, Handoff block. Loaded by every subagent at start and by a parent writing a delegation brief.
alwaysApply: false
category: workflow
---

# Subagent core

**When to load this file:** every subagent loads it once at start (its prompt preamble points here); the parent loads it when writing a delegation brief or forwarding a Handoff. Choosing *whether* and *to whom* to delegate is `subagents.md`, which a subagent does not need to read.

## Common obligations

Every subagent inherits `AGENTS.md` in full — its hard gates are not repeated in agent prompts. This section adds only what is **subagent-specific**; every agent prompt opens with a one-line preamble pointing here. Parent agents and subagent authors must not weaken any item.

### CONFUSION on material forks

Canon — `AGENTS.md → Development Procedure → 1. Think Before Coding` (triggers, format, low-risk assumption rule). Material fork = data integrity, transactions / posting, metadata shape, public contracts, security / RLS, anything hard to reverse, a conflict with existing code / БСП / `РежимСовместимости`, or an under-specified material edge case.

Subagent-specific: never resolve a material fork by silently picking one interpretation, returning a partial result, or paraphrasing the question into prose — raise the block and stop. Low-risk ambiguity: state the assumption in one line and proceed.

### MCP-first search

Canon — `content/rules/mcp-first-search.md` (chain graph → code-metadata → native tools after a bounded miss; bounded priority, not a ban). Tool routing and parameter names — `content/skills/mcp-1c-tools/SKILL.md`.

Subagent-specific: the chain binds subagents exactly as it binds the parent; when you fall back to a native discovery tool, state in the report which MCP attempts were tried and why they missed. `1c-arch-reviewer` and `1c-code-reviewer` have no Shell by design — their `Grep` / `Glob` only read sources the parent already pointed at, and any wider search is requested via the parent or `1c-explorer`.

### Metadata, infobase and repository hard gates (mutating agents)

Canon — `AGENTS.md → Skills and Subagents` (metadata mutations through the `1c-metadata-manage` skill, infobase operations through the slash commands / `db-ops`, repository operations through `1c-repository-manage`, vendor-support refusals); exceptions only per `content/skills/1c-metadata-manage/SKILL.md → Hard rule`.

Subagent-specific: the gates bind **every** mutating subagent, not only `1c-metadata-manager`. A `1c-developer` / `1c-error-fixer` / `1c-refactoring` / `1c-performance-optimizer` task that turns out to require a form or metadata change either drives it through the skill itself or reports it back to the parent for delegation — it never hand-edits the XML. In EDT projects (`.dev.env` `USE_EDT=true`) establish the source format before the first mutation and route per `content/rules/edt-workflow.md`; hand-editing `*.mdo` / `*.form` is a defect with no exception. Name the path used in the report: `Metadata tooling: …`, `EDT tooling: …`, `Repository tooling: …`.

### Validator chain (mutating agents)

Canon — `content/rules/verification-gates.md` (ordered hard gates: `syntaxcheck` → `check_1c_code` → `review_1c_code` → impact analysis → metadata XML validation, as applicable; graceful degradation when a validator is not exposed — the skip is recorded in the report, never silent). Retry budget — `content/rules/verification-policy.md → "Validator budget"`.

Subagent-specific: the agent that makes the final edit owns the validator run; for every mutated artifact report its content fingerprint, each applicable validator's result and run count **after the final edit**, and relevant execution context per `verification-gates.md → Gate execution and evidence reuse`. The parent reuses matching evidence instead of repeating validators on unchanged content. Read-only agents (`1c-explorer`, `1c-analytic`, `1c-arch-reviewer`, `1c-code-reviewer`, `1c-doc-writer` when not writing project sources) skip the mutating gates but follow every other item of this section.

### Scope and done criteria

- Edit only the files / objects in the assigned scope: no "while we're here" changes, no reverting or overwriting edits outside the scope, no deleting files without an explicit instruction — the subagent is not alone in the codebase.
- A real defect orthogonal to the assigned task (wrong logic, missing check, security or performance issue) is **reported** to the parent in the final report, never fixed within the task.
- Every assigned item is implemented or explicitly listed as not done. A plan that turns out wrong goes back to the parent as a `CONFUSION`; the subagent does not re-plan.
- If a criterion or a gate cannot be met, say so in the report — never present a partial result as complete.

### Handoff in / out (implementation subagents)

When one change is split across several implementation subagents (`1c-metadata-manager`, `1c-developer`, `1c-refactoring`, `1c-performance-optimizer`, `1c-error-fixer` — typical chain: metadata stubs first, BSL bodies next), the upstream subagent puts a fixed-format **Handoff** block at the very top of its final report. The parent's `## Upstream Handoff` copy preserves decisions and the reported artifact snapshot; current file contents remain the source of truth for the next edit. Parent-side forwarding rules — `subagent-pipeline.md → Stage 3 — Handoff between implementation subagents`.

**Handoff out** — emit whenever a further implementation subagent is expected (when unsure, emit). Machine-readable: one fact per line, ≤ 120 chars, no prose paragraphs; explanations belong in the report body.

```text
## Handoff for the next subagent

### CF/CFE context (when applicable)
- Project: <root>; write: <targets + source roots>; read-only: <contours + roots>
- Graph: <server / verified project_id / layers or unknown>; evidence: <reference>
- Per target: <source revision/edits>; export: <scope/result>; loaded: <state>; applied: <state>
- MCP: <coverage/generation/freshness or unknown>; evidence: <references>

### Artifacts
- <full repo path> — <one-line role> [stub | done | edited]

### Verification evidence
- <file> — <content fingerprint> — <validator, result, run count>
- <relevant configuration / extension, platform / modes, source-to-IB match when applicable>

### Public surface
- <ObjectName>.<RoutineName>(<params>) → <return type> — <one-line purpose>
- <Metadata.Object> — <attribute / tabular section / form / command>: <type / role>

### Open TODOs / stubs for the next subagent
- <file>:<region or routine> — <what to implement> — <signature hint, if pre-agreed>

### Locked decisions (do not revisit without approval)
- <decision> — <one-line rationale>

### Open questions raised
- <CONFUSION-id> — <one-line summary> — <status: resolved / pending>
```

**Handoff in** — read `## Upstream Handoff` first; reuse its decisions, inventory and public-contract intent instead of rediscovering them. Before editing, read the current target fragment and the context needed to preserve intervening changes; a fingerprint check or targeted `Read` is normal work, not forbidden re-exploration. Reuse validation only when the current content fingerprint and relevant execution context match the recorded evidence (`verification-gates.md → Gate execution and evidence reuse`). A missing / changed fingerprint makes affected evidence stale: inspect the change and run only missing or invalidated gates. Additional discovery still follows `mcp-first-search.md`; avoid bulk re-reads of unchanged files. If current contents contradict a locked decision or public contract materially, raise `CONFUSION`; never overwrite another agent's edits or silently revise the decision.

For CF/CFE context, keep failed, not-run and unknown stages distinct, with no secrets or copied connection settings. Before dependent mutations, recheck root/target identity, write boundaries, graph mapping and evidence per `content/rules/extension-workspace.md → Handoff and resume`. Handoff alone authorizes no reload/apply/reindex; one target's pass never certifies the whole project.

### Report vocabulary

Severity of findings: `critical` (blocks delivery) / `major` (must be addressed or consciously accepted) / `minor` (informational). Status line: implementers report `✅ DONE / ⚠️ PARTIAL / ❌ BLOCKED`; reviewers and the tester report `✅ APPROVE / ⚠️ CONCERNS / ❌ BLOCK`. Each agent keeps its own report skeleton; no other scale is used.

### Shell and SDD

- Agents whose frontmatter lists `Shell` follow the `powershell-windows` skill for every shell command.
- If the project has an `openspec/` workspace — `content/rules/sdd-integrations.md` (MCP evidence for 1C facts, `Subagent → OpenSpec artifact mapping`, traceability updates after implementation).

