---
description: Orchestrator economy mode — while ORCHESTRATION=economy in .dev.env (toggled by /economymode), the parent agent delegates execution to cheaper-tier subagents and keeps decisions, specs, and verification
alwaysApply: false
category: workflow
---

# Orchestrator economy mode

**When to load this file:** `ORCHESTRATION=economy` in the project `.dev.env`; or the user runs `/economymode` (any argument) or asks about the mode in plain words ("режим экономии", "economy mode").

## State

`ORCHESTRATION=economy` switches the mode on for the whole project; anything else is `standard` (key semantics — `dev-standards-env-process.md`, never asked for). `/economymode on|off` is the canonical editor. An explicit chat request ("включи экономию" / "выключи экономию") overrides the setting for the current session without editing `.dev.env`; asking about the mode does not switch it.

The mode chooses **who executes**, not models: tier models stay in `SUBAGENT_MODEL_*` (`subagents.md → Model-tier routing`). With empty tier models subagents inherit the parent's model and the saving shrinks to context offloading — `/economymode on` offers to configure them inside its own flow.

## Principle

Parent-agent tokens are the most expensive resource of the session — typically several times the price of an `analysis` / `light` subagent. Within the triage and delegation boundaries below, the parent thinks, decides, writes delegation briefs and verifies; subagents do the reading and the writing.

## Division of labor

The parent keeps for itself:

- triage and task decomposition, the order of work;
- architectural decisions; decision forks go to the **user** via the `CONFUSION` format, never to a subagent;
- specs for subagents — with all accepted decisions inside (templates: `subagents.md → Bounded sidecar task templates`);
- spot-checking subagent reports against primary sources;
- integrating results, the verification gates, and the final report.

Delegated while the mode is on (tier per `subagents.md → Model-tier routing`):

- exploration, inventory, bulk reading of sources, impact lists — `1c-explorer` (`light`) only; never the host built-in Explore / `explore` (`subagents.md → Host-tool built-in explorers`);
- implementation from a ready plan — `1c-developer` / `1c-metadata-manager` (`coding`);
- planning, analysis, documentation — `1c-planner` / `1c-analytic` / `1c-doc-writer` (`analysis`);
- mechanical multi-file edits — a bounded worker with a non-overlapping write scope (`worker-bounded-edit` template);
- error fixes above the quick-fix line — `1c-error-fixer` (`coding` — it authors production code).

Output rule: the parent's own text stays minimal — decisions, specs, summaries. While the mode is on, the parent does not write file bodies for non-trivial changes.

## What the mode does not change

The mode changes **who executes**, never **which gates apply**; on any conflict the stricter existing rule wins.

- **Triage** — standalone quick-fix and docs-fix tasks are executed by the parent; a subagent launch for a trivial edit costs more than it saves.
- **Pipeline** — `subagent-pipeline.md` keeps its stages and gates; the mode only makes stage 2/3 delegation the default for full-cycle tasks and moves stage 2 bulk reads to `1c-explorer`. Stages 4a (spec compliance), 4b (code-quality review) and 5 (verification gate) remain the parent's own work.
- **Spec-authoring** stays outside the implementation pipeline: the parent owns decisions and acceptance; bounded research and artifact drafting may be delegated by `sdd-integrations.md → Subagent → OpenSpec artifact mapping`. Authoring a spec does not authorize apply.
- **Gates** — `VERIFICATION_DEPTH`, `UI_TESTING`, the reviewer model gate and every validator obligation apply as written; whoever edits BSL / metadata runs the gates its depth selects, and the parent owns the closing gate. Light-tier output stays working material, never the final authority for architecture, transactions, registers, security or data integrity.

## Mode discipline

- A spec for a subagent contains ready decisions: the subagent executes, it does not invent. Handoffs follow `subagent-core.md → Handoff in / out (implementation subagents)`.
- Independent tasks run in parallel; while subagents work, the parent does not idle and does not duplicate their work.
- Scouting reports are spot-checked against primary sources (a targeted read of a fragment) before decisions are based on them — light models hallucinate. Spot-checks stay selective (key files, the most contentious decisions); the Stage 4b review of a full-cycle change still covers the whole delegated diff.
- Escalation: if a subagent failed twice on a clear spec, the parent does the work itself and records the escalation in the delivery summary.
- Answering questions, discussion and choosing between options stay with the parent. Savings grow with volume: the more files are read and written, the more strictly the mode applies.
- While the mode is on, note in the delivery summary that economy mode was active and which subagents executed the work.
