---
description: Subagent catalog — when to delegate to a specialized subagent vs. execute directly; model-tier routing and bounded sidecar task templates
alwaysApply: false
category: workflow
---

# Subagents — catalog and delegation rules

**When to load this file:** if a task feels large / multi-step / multi-module and you suspect it is worth delegating to a specialized subagent — read this file, check the availability of a suitable subagent in the table below, and decide whether to delegate or execute directly.

## Delegation principle

13 specialized subagents are available in the project. Source prompt files live in `content/agents/` and use short file names without the `1c-` prefix:

| Subagent id | Source prompt file |
|---|---|
| `1c-explorer` | `content/agents/explorer.md` |
| `1c-analytic` | `content/agents/analytic.md` |
| `1c-planner` | `content/agents/planner.md` |
| `1c-architect` | `content/agents/architect.md` |
| `1c-arch-reviewer` | `content/agents/arch-reviewer.md` |
| `1c-developer` | `content/agents/developer.md` |
| `1c-metadata-manager` | `content/agents/metadata-manager.md` |
| `1c-refactoring` | `content/agents/refactoring.md` |
| `1c-performance-optimizer` | `content/agents/performance-optimizer.md` |
| `1c-error-fixer` | `content/agents/error-fixer.md` |
| `1c-tester` | `content/agents/tester.md` |
| `1c-code-reviewer` | `content/agents/code-reviewer.md` |
| `1c-doc-writer` | `content/agents/doc-writer.md` |

**Delegate when:**

- the work is large enough to justify the subagent launch overhead;
- the task would otherwise drain the parent agent's context window (long traces, large files, mass edits);
- several independent checks can be run in parallel (most subagents have `allowParallel: true`).

**Do not delegate** when the task is a trivial single-file edit, or a medium full-cycle task that fits the parent's context comfortably — execute it directly (the standard path: the 5-step Development Procedure from `AGENTS.md` plus the closing gate). The pipeline in `subagent-pipeline.md` applies only when delegation is chosen here.

**Economy mode.** When `.dev.env` has `ORCHESTRATION=economy` (toggled by `/economymode`; empty / missing = `standard`), load `content/rules/orchestrator-economy.md`: delegation of execution becomes the default — the parent keeps decisions, specs, and verification, subagents do the reading and writing. Check the key when loading this file for a non-trivial task. The mode only widens delegation; every constraint of this file stays intact, and model selection still resolves from `SUBAGENT_MODEL_*` per tier.

## Common obligations

Every subagent inherits these obligations from `AGENTS.md` even when its own prompt does not repeat them. Parent agents and subagent authors must not weaken them.

### CONFUSION format

When the task forks **materially** (interpretations diverge on data integrity, transactions, metadata shape, public contracts, security / RLS, or anything hard to reverse), conflicts with existing code / БСП / `РежимСовместимости`, or is under-specified on a material edge case — raise the question in the `CONFUSION` format from `AGENTS.md → Development Procedure → 1. Think Before Coding`. Do **not** silently pick one interpretation, return a partial result, or paraphrase the question into free-form prose. For low-risk ambiguity (private naming, internal decomposition, defaults the user is unlikely to care about) — per the same `AGENTS.md` section: state the assumption in one line and proceed.

### MCP-first search

Before any `Grep` / `Glob` / `rg` on 1C project source, follow `content/rules/mcp-first-search.md` (graph → code-metadata → `grep=true` retry → `Grep`). State what was tried when falling back.

### Verification checklist (mutating agents)

Before declaring a non-trivial mutating change done, apply `content/rules/verification-checklist.md` (ordered hard gates: `syntaxcheck` → `check_1c_code` → `review_1c_code` → impact analysis → metadata XML validation, as applicable). For every mutated artifact, report each applicable validator's result and run count after the final edit; the parent reuses this evidence instead of repeating validators on unchanged content. Read-only agents (`1c-explorer`, `1c-analytic`, `1c-arch-reviewer`, `1c-code-reviewer`, `1c-doc-writer` when not writing project sources) skip the mutating gates but still follow CONFUSION and MCP-first search.

Each agent prompt ends with a short **Common obligations** pointer to this section — keep that pointer in sync when editing this file.

## Subagent catalog

| Subagent | When to call | When NOT to call |
|---|---|---|
| **1c-explorer** | Read-only exploration across many files, metadata objects, dependencies, or "where/how/who calls" questions before planning, coding, or refactoring | Narrow lookup that the parent can answer with one direct read/search |
| **1c-analytic** | User asks for a PRD, specification, or analysis of an existing area without writing code | Task is to write code |
| **1c-planner** | A multi-step implementation or refactoring plan is needed before coding | Task is small enough that the plan is 1–2 lines |
| **1c-architect** | Designing the architecture of a sizable modification (new subsystem, integration, multi-module change) | Single-procedure or single-module change |
| **1c-arch-reviewer** | User asks to review or validate an architectural decision before implementation | No architectural design exists yet |
| **1c-developer** | Bulk code writing or modification across multiple modules that would otherwise drain the parent's context | Small local edit (Quick-fix path — see `AGENTS.md → Development Procedure`) |
| **1c-metadata-manager** | Creating, scaffolding, compiling, or multi-step / multi-domain metadata operations (objects, forms, reports, layouts, roles, extensions) | Single info lookup or single XML attribute fix — use a direct edit or the `1c-metadata-manage` skill |
| **1c-refactoring** | Dead-code cleanup, consolidation, or deduplication across multiple modules | Refactor is local to one procedure |
| **1c-performance-optimizer** | User reports slowness, or query / loop optimization is the explicit task | No performance concern was raised |
| **1c-error-fixer** | Quick fix of syntax / runtime errors / BSL LS warnings without architectural changes (tier `light` — runs on the small-tasks model when one is configured) | The fix requires architectural rework — escalate to `1c-architect` / `1c-developer` |
| **1c-tester** | User asks to verify changes via deploy + UI automation against a test infobase, **and** `UI_TESTING` allows it (canon — `dev-standards-env.md`) | No test infobase; purely static task; `UI_TESTING=off`, or `manual` without an explicit UI-test request — never auto-trigger |
| **1c-code-reviewer** | **Only when the user explicitly asks for a code review** | Auto-triggering after edits is forbidden |
| **1c-doc-writer** | User-facing documentation: user guides, admin manuals, tutorials, codemaps, API references | Inline code documentation (module / procedure headers) — that is the developer's responsibility |

## Model-tier routing

Subagent source files do **not** hard-code model names. Each agent declares an abstract tier in its frontmatter — `modelTier: coding`, `modelTier: analysis`, or `modelTier: light` — and the installer resolves the tier into a concrete model from `.dev.env` (`SUBAGENT_MODEL_CODING` / `SUBAGENT_MODEL_ANALYSIS` / `SUBAGENT_MODEL_LIGHT`, all Defaulted: empty = the AI client's default model; see `dev-standards-env.md → "Subagent model parameters"`). Model names live only in project settings, never in rules or agent prompts. On first install the installer proposes a benchmark-based profile (`Balanced` / `Economy` / `Quality`, derived from <https://onec-llm-bench.lovable.app/>); the recommendation lives in the installer / `.dev.env`, not here.

The three tiers:

- **`coding`** — code / metadata authorship and design: writing or editing BSL and metadata, architecture design. Agents: `1c-developer`, `1c-metadata-manager`, `1c-architect`, `1c-performance-optimizer`, `1c-refactoring`. Warrants the strongest model — this tier mutates production code.
- **`analysis`** — reasoning without production-code authorship: planning, analysis, review, testing, documentation. Agents: `1c-planner`, `1c-analytic`, `1c-arch-reviewer`, `1c-code-reviewer`, `1c-doc-writer`, `1c-tester`. A strong-value model is usually enough.
- **`light`** — small bounded tasks where a cheaper / faster model saves limits without hurting quality: repo scouting, search, impact lists, quick error fixes, mechanical post-edit checks. Agents: `1c-explorer`, `1c-error-fixer`.

Routing rules:

- **Good candidates for the `light` tier** (when the active tool supports a per-invocation model override, the parent may route these down even to a `coding`-tier agent): initial project-source scouting and candidate lists; navigation / reference gathering for objects, modules, forms, procedures; impact lists ("where is X used"); mechanical verification after edits; small bounded edits in strictly assigned files.
- **Never use the `light` tier as the final authority** for architecture, metadata / form design, transactions, registers, complex queries, security, data integrity, or release-critical decisions. Output of a light-tier run is working material, not a source of truth — the parent agent owns decomposition, source boundaries, the final decision, verification, and integration.
- **Do not delegate trivial single-step tasks at all** — the launch overhead exceeds the saving.
- The tier system does not change validation obligations: whatever tier produced the change, the applicable validator chain and closing gate from `verification-checklist.md` still apply, including quick-fixes.

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
Follow the project MCP fallback chain (graph metadata → code metadata → grep=true retry → Grep).
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
Follow project rules (dev-standards-core, module-structure). For BSL run syntaxcheck →
check_1c_code → review_1c_code on every touched module within the verification budget;
for metadata XML run verify_xml (and both chains when it embeds BSL).
Return: changed files, diff summary against the plan, checks performed, unresolved risks.
```

### reviewer-risk — independent review (`1c-code-reviewer`, **only when the user explicitly asked for a review**)

```text
Independent review of the current change for bugs, regressions, missing checks, and project-rule
violations. Review scope: <parent-provided git diff and/or explicit file list>. Do not edit files.
The reviewer has no Shell / Grep / Glob access and must not infer an absent scope. High-confidence
findings only, ordered by severity, with file/line references; then test gaps and residual risk.
```

### smoke-check — mechanical post-change verification (`1c-explorer`, light-tier candidate)

```text
Read-only smoke check. Verify that <feature / rule / artifact> is discoverable and consistent through
its intended entry points (referenced paths exist, names match, wiring is complete). Do not edit files.
Return: exact checks performed, observed result, pass/fail per item.
```
