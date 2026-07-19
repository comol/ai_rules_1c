---
description: Orchestrator economy mode — while ORCHESTRATION=economy in .dev.env (toggled by /economymode), the parent agent delegates execution to cheaper-tier subagents and keeps decisions, specs, and verification
alwaysApply: false
category: workflow
---

# Orchestrator economy mode

**When to load this file:** `ORCHESTRATION=economy` in the project `.dev.env`; or the user runs `/economymode` (any argument) or asks about the mode in plain words ("режим экономии", "economy mode").

## When the mode is on

- **State** — the `ORCHESTRATION` key in `.dev.env` (**Defaulted**: missing file / missing key / empty / invalid value = `standard`, mode off; **never ask** for the value). `economy` switches the mode on for the whole project, including new chats.
- **Enable / disable** — the `/economymode` command (`on` writes `ORCHESTRATION=economy`, `off` writes `ORCHESTRATION=standard`); the command is the canonical editor of this key. An explicit user phrase in chat ("режим экономии" / "включи экономию" / "выключи экономию") overrides the setting **for the current session** without editing `.dev.env`.
- **Detection** — when deciding whether to delegate (loading `subagents.md`) on a non-trivial task, check `ORCHESTRATION` in `.dev.env`; on `economy`, apply this rule.
- **Models are out of scope** — the mode does not choose models. Concrete models per tier stay in `SUBAGENT_MODEL_CODING` / `SUBAGENT_MODEL_ANALYSIS` / `SUBAGENT_MODEL_LIGHT` and are resolved by the installer per `subagents.md → Model-tier routing`; the mode only shifts **who executes** toward subagents on those tiers. When the tier models are **empty**, subagents inherit the parent's model and the savings shrink to context offloading — that is why `/economymode on` checks the keys and offers to configure them (benchmark profiles or custom slugs) before enabling; the question is part of the command's explicit flow and does not weaken the never-ask policy for regular tasks.

## Principle

Parent-agent (orchestrator) tokens are the most expensive resource of the session — typically several times the price of a subagent on the `analysis` / `light` tier. While the mode is on, the parent **does not do anything itself that a subagent of an appropriate tier can do**: the parent thinks, decides, writes specs, and verifies; subagents do the reading and the writing.

## Division of labor

The parent keeps for itself:

- triage and task decomposition, the order of work;
- architectural decisions; decision forks go to the **user** via the `CONFUSION` format, never to a subagent;
- specs for subagents — with all accepted decisions inside (templates: `subagents.md → Bounded sidecar task templates`);
- spot-checking subagent reports against primary sources;
- integrating results, the verification gates, and the final report.

Delegated while the mode is on (tier per `subagents.md → Model-tier routing`):

- exploration, inventory, bulk reading of sources, impact lists — `1c-explorer` (`light`);
- implementation from a ready plan — `1c-developer` / `1c-metadata-manager` (`coding`);
- planning, analysis, documentation — `1c-planner` / `1c-analytic` / `1c-doc-writer` (`analysis`);
- mechanical multi-file edits — a bounded worker with a non-overlapping write scope (`worker-bounded-edit` template);
- quick error fixes — `1c-error-fixer` (`light`).

Output rule: the parent's own text stays minimal — decisions, specs, summaries. While the mode is on, the parent does not write file bodies for non-trivial changes; the quick-fix exception below still applies.

## Consistency with the existing orchestration rules

The mode changes **who executes**, never **which gates apply**. On any conflict, the stricter existing rule wins. Explicitly:

- **`subagent-pipeline.md` stays intact** — same stages, same hard gates. The mode only makes stage 2/3 delegation the default for full-cycle tasks and pushes bulk reads of stage 2 scouting to `1c-explorer`. Stages 4a (spec-compliance review) and 5 (verification gate) remain the parent's own work.
- **Triage from `AGENTS.md` is unchanged** — quick-fix and docs-fix tasks are still executed directly by the parent: launching a subagent for a trivial edit costs more than it saves (`subagents.md → Do not delegate`). The mode never forces delegation of trivial work.
- **`1c-code-reviewer` still runs only on an explicit user request** — the mode must not auto-trigger reviews.
- **UI testing is still gated** by `UI_TESTING` and `INFOBASE_PUBLISH_URL` — the mode does not enable `1c-tester` runs.
- **Model-tier routing from `subagents.md` still applies** — light-tier output remains working material, never the final authority for architecture, transactions, registers, security, or data integrity.
- **Validator obligations are unchanged** — whoever edits BSL / metadata runs the applicable chain (`syntaxcheck` → `check_1c_code` → `review_1c_code` / `verify_xml`); the parent still owns the closing gate from `verification-checklist.md`.
- **CONFUSION protocol is unchanged** — under-specified or conflicting requirements go to the user.

## Mode discipline

- A spec for a subagent contains ready decisions: the subagent executes, it does not invent. Handoffs between implementation subagents follow `subagent-pipeline.md → Handoff`.
- Independent tasks run in parallel; while subagents work, the parent does not idle and does not duplicate their work.
- Scouting reports are spot-checked against primary sources (a targeted read of a fragment) before decisions are based on them — light models hallucinate; verification is mandatory.
- Review of delegated results is selective (key files, the most contentious decisions), not a full re-read — a full re-read eats the savings.
- Escalation: if a subagent failed twice on a clear spec, the parent does the work itself — a third iteration costs more than direct execution. Record the escalation in the delivery summary.
- While the mode is on, note in the delivery summary that economy mode was active and which subagents executed the work.

## Applicability boundaries

- Trivial edits (quick-fix path) are not delegated — the launch overhead exceeds the saving.
- Answering user questions, discussion, and choosing between options are the parent's work; the mode does not affect them.
- Savings grow with volume: the more files are read and written, the more strictly the mode applies.
