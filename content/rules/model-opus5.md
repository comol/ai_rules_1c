---
description: Claude Opus 5 profile (AGENT_MODEL=opus5) — report shape and verbosity, narration cadence, no self-invented verification, damped subagent spawning, coverage-first review briefs, effort and thinking settings, lean context
alwaysApply: false
category: workflow
---

# Model profile — Claude Opus 5

**Load:** `AGENT_MODEL=opus5`, or you know you run as Claude Opus 5; once per session, before the first non-trivial task. Contract and invariants — `content/rules/model-adaptation.md`. Tunes initiative and communication only; every `AGENTS.md` gate stays as written. The model runs the ruleset well; these are the behaviours that most often need tuning.

## 1. Verbosity and the delivery report

Answers run longer than on prior Opus models, and lower `effort` cuts thinking, not visible output — ask for length explicitly. Delivery report: outcome, then files, then risks; no task restatement or process recap; one line per caveat. Answer questions at summary depth, expand on request. Written artefacts (OpenSpec, handoffs, `1c-doc-writer` output, review reports) follow the same calibration — length is not thoroughness.

## 2. Narration during work

One sentence before the first tool call of a task, then an update only on a material finding or change of direction. No narration per MCP call, no re-summaries between calls; the required evidence one-liners are the report.

## 3. No self-invented verification, no widened scope

- Add no verification the ruleset did not ask for: no extra pass over your own diff, no second read of an unchanged file, never a subagent to check your own work. The mandated validator chain, `verify_xml` and the gates are tool evidence and stay at full strength.
- Deliver what was asked at the scope asked. If the request looks mistaken or a better approach exists, say so in a sentence and continue; `CONFUSION` only on a material fork.

## 4. Delegation

The model delegates readily. Within `content/rules/subagents.md` lean toward direct execution: a handful of tool calls, a single-module edit or work you need in your own head — do it yourself. One subagent with a wide brief beats fan-out; never delegate verification of your own output. Under `ORCHESTRATION=economy` the mode's routing wins, but the low spawn count stays.

## 5. Correction narration

Correct an earlier statement only when the error would change the user's code, conclusions or decisions — plainly, in a sentence. Slips that change nothing are fixed without a tally or apology. Validator failures, skipped steps and unverified artefacts are always reported.

## 6. Review briefs — ask for coverage

A stated severity bar is followed literally: "only critical issues" yields fewer findings, not a better filter. When reviewing BSL or briefing `1c-code-reviewer` / `1c-arch-reviewer`, ask for every finding with severity and confidence and filter in your own report. Gate semantics are unchanged.

## 7. Effort, thinking and context (client-side)

- `high` fits most 1C work; `xhigh` for multi-module full-cycle changes, architecture, metadata surgery and hard debugging; `low` / `medium` are strong for docs-fix, triage, quick-fix and lookups.
- Keep thinking enabled: without it the model can emit a tool call as plain text or leak internal tags — fatal for MCP-driven work. Lower `effort` for cost; never write "do not think / skip the reasoning" into a prompt, brief or skill.
- The 1M-token context lets you keep fetched evidence instead of re-querying; it is no licence to bulk-read modules or glob source trees.

## 8. Lean context

Over-constraint and repeated instructions cost this model more than they buy. Load the always-on layer plus what triage selects — nothing "for context"; an obligation restated in several files is one obligation. Context you author (briefs, memory notes, handoffs, OpenSpec) carries intent, constraints, scope, done-when and the interface — worked examples only to pin an output format; point at code instead of paraphrasing it.
