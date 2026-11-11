---
description: Subagent catalog — when to delegate to a specialized subagent vs. execute directly; model-tier routing and bounded sidecar task templates
alwaysApply: false
category: workflow
---

# Subagents — catalog and delegation rules

**When to load this file:** if a task feels large / multi-step / multi-module and you suspect it is worth delegating to a specialized subagent — read this file, check the availability of a suitable subagent in the table below, and decide whether to delegate or execute directly.

## Delegation principle

13 specialized subagents are available (catalog below); the prompt of `1c-<name>` is `content/agents/<name>.md`, installed under the active tool.

**Delegate when at least one countable fact holds:**

First apply triage: standalone `docs-fix` and `quick-fix` tasks stay with the parent, including in economy mode. The thresholds below do not override those exceptions. Spec-authoring may delegate research and artifact drafting under `sdd-integrations.md`; it does not enter the implementation pipeline.

- the change touches **≥ 3 modules** or **≥ 2 metadata objects** (forms, layouts, roles and DCS schemas count as objects);
- an **independent read-only track** exists — exploration, impact listing or pattern search that `1c-explorer` can run while the parent continues, or a review the user explicitly requested;
- the task needs **≥ 5 files read** before the first edit or a **mechanical edit across ≥ 5 files** — the parent's context window is the bottleneck;
- `.dev.env` has `ORCHESTRATION=economy` (see below).

**Otherwise execute directly:** a single-file edit, or a full-cycle task under those thresholds, runs the 5-step Development Procedure from `AGENTS.md` plus the closing gate from `content/rules/verification-gates.md`. The pipeline in `subagent-pipeline.md` applies only when delegation is chosen here.

All 13 agents declare `allowParallel: true`. That licenses parallel **read-only** tracks; two mutating subagents run in parallel on one configuration only when their write scopes are provably disjoint — `subagent-pipeline.md → Stage 3`.

**Model profile.** The active-model profile may tune **how eagerly** you delegate within these criteria, never the criteria themselves, the "when NOT to call" column, the built-in-explorer ban or the common obligations. No profile authorises a subagent spawned to double-check your own work.

**Economy mode.** Check `ORCHESTRATION` when loading this file for a non-trivial task; on `economy` load `content/rules/orchestrator-economy.md`: delegation of execution becomes the default, and every constraint of this file stays intact.

## Host-tool built-in explorers (hard ban)

Hosts ship **built-in** explore helpers (Cursor Task `subagent_type: "explore"`, generic codebase scouts) with a fixed prompt that runs no MCP-first chain and none of this project's rules. **Hard rule for the parent:**

1. Delegated read-only exploration goes to **`1c-explorer`**, launched by its custom agent name (`/1c-explorer …`, a Task launch by name), never to a built-in explore type.
2. If the session can start only built-in types, do not substitute one: explore on the parent with MCP-first search, or tell the user that `1c-explorer` is not launchable here. A built-in explorer fallback is a defect — rules steer the parent, not that helper's prompt.

## Common obligations

Owned by `content/rules/subagent-core.md` — CONFUSION on material forks, MCP-first search, metadata / infobase / repository gates, validator chain, scope and done criteria, the Handoff block, report vocabulary, shell and SDD. Every subagent inherits `AGENTS.md` in full plus that file; every agent prompt opens with a one-line preamble pointing there. Parent agents and subagent authors must not weaken any item. Load it before writing a delegation brief or forwarding a Handoff.

## Subagent catalog

| Subagent | When to call | When NOT to call |
|---|---|---|
| **1c-explorer** | Read-only exploration across many files, metadata objects, dependencies, or "where/how/who calls" questions before planning, coding, or refactoring. **Mandatory** for delegated exploration — never the host built-in Explore (see *Host-tool built-in explorers*) | Narrow lookup that the parent can answer with one direct read/search; host-tool Cursor-guide / docs lookup (not 1C project source) |
| **1c-analytic** | User asks for a PRD, specification, or analysis of an existing area without writing code | Task is to write code |
| **1c-planner** | A multi-step implementation or refactoring plan is needed before coding | Task is small enough that the plan is 1–2 lines |
| **1c-architect** | Designing the architecture of a sizable modification (new subsystem, integration, multi-module change) | Single-procedure or single-module change |
| **1c-arch-reviewer** | **Only when the user explicitly asks** to validate an existing design and the reviewer model gate below is satisfied | Auto-triggering from a pipeline stage is forbidden; no architectural design exists yet; no explicitly selected reviewer model |
| **1c-developer** | Bulk code writing or modification across multiple modules that would otherwise drain the parent's context | Small local edit (Quick-fix path — see `AGENTS.md → Development Procedure`) |
| **1c-metadata-manager** | Creating, scaffolding, compiling, or multi-step / multi-domain metadata operations (objects, forms, reports, layouts, roles, extensions) | Single info lookup or single XML attribute fix — use a direct edit or the `1c-metadata-manage` skill |
| **1c-refactoring** | Dead-code cleanup, consolidation, or deduplication across multiple modules | Refactor is local to one procedure |
| **1c-performance-optimizer** | User reports slowness, or query / loop optimization is the explicit task | No performance concern was raised |
| **1c-error-fixer** | Fixing syntax / runtime errors / BSL LS warnings above the quick-fix line, without architectural changes (tier `coding` — it authors production code, often on transactional paths) | A quick-fix-eligible edit — the parent makes it; the fix requires architectural rework — escalate to `1c-architect` / `1c-developer` |
| **1c-tester** | Applicable UI verification with effective `UI_TESTING=essential` (important new or changed user-visible behaviour) or `auto`, or explicit UI-test request under `manual`; authorized dev/test target required (`dev-standards-env.md`) | No test infobase; purely static task; `off`, or `manual` without an explicit UI-test request |
| **1c-code-reviewer** | **Only when the user explicitly asks for a code review** and the reviewer model gate below is satisfied | Auto-triggering after edits is forbidden; no explicitly selected reviewer model |
| **1c-doc-writer** | User-facing documentation: user guides, admin manuals, tutorials, codemaps, API references | Inline code documentation (module / procedure headers) — that is the developer's responsibility |

## Tool declarations

The `tools` frontmatter of a source agent is an abstract capability list (`Read`, `Write`, `Edit`, `Grep`, `Glob`, `Shell`, `MCP`) that the installer maps per host (`AGENT-INSTALL.md → Lean placement`, step 4). An installed agent may see more tools than its list names; what the list guarantees is that a withheld capability is denied. **Never "fix" a subagent by deleting its `tools` line** — that strips the write and shell boundary of the read-only agents; a missing shell or MCP means re-running the installer mapping.

## Model-tier routing

Each agent declares an abstract `modelTier` (`coding` / `analysis` / `light`); the installer resolves it from `SUBAGENT_MODEL_CODING` / `_ANALYSIS` / `_LIGHT` (`dev-standards-env-process.md → "Subagent model parameters"`; empty = the client's default model). Model names live only in project settings, never in rules or agent prompts. Host adapters may not honour a per-agent model (the Kimi Code runtime ignores it) — follow the adapter.

The three tiers:

- **`coding`** — code / metadata authorship and design: writing or editing BSL and metadata, architecture design, error fixes. Agents: `1c-developer`, `1c-metadata-manager`, `1c-architect`, `1c-performance-optimizer`, `1c-refactoring`, `1c-error-fixer`. Warrants the strongest model — this tier mutates production code.
- **`analysis`** — reasoning without production-code authorship: planning, analysis, review, testing, documentation. Agents: `1c-planner`, `1c-analytic`, `1c-arch-reviewer`, `1c-code-reviewer`, `1c-doc-writer`, `1c-tester`. A strong-value model is usually enough.
- **`light`** — small bounded read-only tasks where a cheaper / faster model saves limits without hurting quality: repo scouting, search, impact lists, mechanical post-edit checks. Agent: `1c-explorer`. Bounded edits may still be routed down per invocation (below), but no code-writing agent declares this tier.

Routing rules:

- **Good candidates for the `light` tier** (when the active tool supports a per-invocation model override, the parent may route these down even to a `coding`-tier agent): initial project-source scouting and candidate lists; navigation / reference gathering for objects, modules, forms, procedures; impact lists ("where is X used"); mechanical verification after edits; small bounded edits in strictly assigned files.
- **Never use the `light` tier as the final authority** for architecture, metadata / form design, transactions, registers, complex queries, security, data integrity, or release-critical decisions. Output of a light-tier run is working material, not a source of truth — the parent agent owns decomposition, source boundaries, the final decision, verification, and integration.
- **Do not delegate trivial single-step tasks at all** — the launch overhead exceeds the saving.
- The tier system does not change validation obligations: whatever tier produced the change, the gates `verification-policy.md` selects still apply.

## Reviewer model gate

`1c-code-reviewer` and `1c-arch-reviewer` are **disabled unless a reviewer model is explicitly selected**: a non-empty `SUBAGENT_MODEL_ANALYSIS` in `.dev.env`, or a concrete model explicitly chosen by the user for this review invocation. An absent file / key, an empty value, the client's default model, and the legacy fallback to `SUBAGENT_MODEL_CODING` do not enable reviewers. Do not ask for a model merely to complete an ordinary development task.

Before dispatch, confirm that the active client's reviewer definition or supported invocation override selects that model. A setting that has not been rendered into the installed agent is insufficient; never silently substitute inheritance or another model. This is a launch condition, not a change to installer tier resolution for other agents.

When the gate is not satisfied, skip the review subagent. If the user requested a review, the parent performs it directly and states that no separate reviewer ran; do not replace it with another subagent. No pipeline stage launches a reviewer on its own, and an explicitly selected model does not itself trigger a review: the catalog's request conditions still apply.

This gate does **not** disable `review_1c_code`, other MCP validators, the parent's spec-compliance check, or full-cycle review by the parent (`verification-delivery.md → Soft gate C`).

## Bounded sidecar task templates

When delegating, the launch prompt must make the task **bounded and self-contained**. Every delegation prompt includes:

- **bounded responsibility** — one verifiable goal, not "help with the task";
- **allowed and forbidden sources** — which MCP servers / files to use; the MCP-first search discipline (`mcp-first-search.md`) applies to subagents too;
- **read/write scope** — explicitly read-only, or an explicit list of files the subagent may edit;
- **expected output format** — what the report must contain;
- a reminder that the subagent **is not alone in the codebase**: it must not revert or overwrite changes outside its scope and must not delete files without an explicit instruction.

Reusable templates (fill in `<...>`; they slot into the matching subagent from the catalog):

### explorer-impact — read-only impact analysis (`1c-explorer`, light-tier candidate)

```text
Read-only impact analysis. Find all references to <object / procedure / attribute>.
Follow the project MCP fallback chain (graph metadata → code metadata → scoped Grep after a bounded miss).
Thoroughness: <quick | medium>. Do not edit files.
Return: locations with file/line references and qualified 1C names, usage categories
(call / query / RLS / form / subscription), risky dependencies, and gaps you could not verify.
```

### explorer-patterns — find existing implementations (`1c-explorer`, light-tier candidate)

```text
Read-only pattern search. Find existing implementations similar to <task>.
Prefer templatesearch / ssl_search / search_code over raw grep. Do not edit files.
Return: 3–7 best examples with paths and qualified names, which pattern to reuse, and what NOT to copy.
```

### metadata-scout — inspect an object / form before a change (`1c-explorer`, light-tier candidate)

```text
Read-only metadata/form scout. Inspect <metadata object / form / layout> via get_object_dossier /
get_metadata_details / inspect_form_layout; confirm against the source XML/BSL when in doubt.
Do not edit files. Return: object structure, form elements / commands / events, related modules,
validation risks, and a suggested write scope for the implementation step.
```

### worker-bounded-edit — implementation within fixed boundaries (`1c-developer` / `1c-error-fixer`)

```text
Bounded implementation. You are not alone in the codebase; do not revert or overwrite edits
outside your scope. Edit only: <files>. Implement <specific change> per the approved plan.
Follow project rules (dev-standards-code-style, module-structure). For BSL select the applicable
gates and budget from verification-policy.md using the supplied task path, depth and risk;
run selected validators in syntaxcheck → check_1c_code → review_1c_code order.
For metadata XML run verify_xml; embedded/generated BSL also needs its applicable BSL gates.
Return: changed files, diff summary against the plan, checks performed, unresolved risks.
```

### reviewer-risk — independent review (`1c-code-reviewer`, **only when the user explicitly asked for a review and the reviewer model gate is satisfied**)

```text
Independent review of the current change for bugs, regressions, missing checks, and project-rule
violations. Review scope: <parent-provided git diff and/or explicit file list>. Do not edit files.
The reviewer has no Shell and must not infer an absent scope. High-confidence
findings only, ordered by severity, with file/line references; then residual risk.
```

### smoke-check — mechanical post-change verification (`1c-explorer`, light-tier candidate)

```text
Read-only smoke check. Verify that <feature / rule / artifact> is discoverable and consistent through
its intended entry points (referenced paths exist, names match, wiring is complete). Do not edit files.
Return: exact checks performed, observed result, pass/fail per item.
```
