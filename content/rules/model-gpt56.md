---
description: Model profile for GPT-5.6 (AGENT_MODEL=gpt56) — lean context and each instruction once, reasoning-effort and verbosity calibration, autonomy boundaries for local vs. external actions, intent-level briefs, no contradictory instructions
alwaysApply: false
category: workflow
---

# Model profile — GPT-5.6

**Load:** `AGENT_MODEL=gpt56`, or you know you run as GPT-5.6; once per session, before the first non-trivial task. Contract and invariants — `content/rules/model-adaptation.md`. Tunes initiative and communication only; every `AGENTS.md` gate stays as written. The model is concise, proactive, good at inferring intent, and does measurably better with lean context than with repeated emphasis.

## 1. Lean context — each instruction once

Load the minimum rule set triage selects — docs-fix nothing beyond the always-on layer, quick-fix the one relevant rule, full-cycle the routers it needs — and never re-read overlapping files inside one task (an index points at its owner; read the owner). An obligation restated in several files is **one** obligation. Call the MCP tools the task needs and no more; for unclear parameters read the one server doc that covers them. Leanness never trims a mandated call.

## 2. Reasoning effort and verbosity (client-side)

- `reasoning_effort`: `low` / `none` for docs-fix and lookups; `medium` for quick-fix BSL and routine metadata; `high` for full-cycle; `xhigh` / `max` for architecture, cross-subsystem refactors and hard debugging. Coming from GPT-5.5 / 5.4, try one level lower.
- `text.verbosity` controls length; the model is already concise, so drop blanket brevity instructions carried over from older prompts.
- Delivery report: conclusion, evidence, material caveat, next action; the file list with paths in backticks stays. Where these parameters are not exposed, state the intended depth once at the start of the plan.

## 3. Autonomy boundaries

Draw the boundary; do not suppress the initiative.

- **Proceed without asking** on safe, local, reversible work: MCP reads and searches, project-file edits, validators, `1c-metadata-manage` tools, OpenSpec artefacts, memory notes.
- **Ask first** for anything that changes state outside your own edits or is hard to reverse: infobase mutations (`/update1cbase`, `/loadfrom1cbase`, `/UpdateDBCfg`, publication), deletions, `git push` / history rewrite, anything reaching an external system, any material scope expansion. A destructive-action confirmation is a one-line question; `CONFUSION` is for genuine forks.
- Never use a destructive shortcut past an obstacle — no bypassed checks, no discarding files you did not create, no rewriting a failing validation away.

## 4. Intent-level briefs, not micro-steps

The model infers goal and level of work from context. Brief a subagent with goal, constraints, scope and definition of done; keep a step list only where order matters (say "validators per `verification-policy.md → Validator budget`", not the three call names). Underspecified low-risk requests: infer the most useful reading, state the assumption in one line, proceed. One-line preamble before a batch of tool calls; no narration per call.

## 5. Conflicts inside the ruleset

A conflict inside the ruleset is a friction signal (`remember` with the `rule-friction:` prefix, then recommend `/evolve`), not something to patch inline. Structure long briefs with named sections (`<task>`, `<constraints>`, `<scope>`, `<done_when>`) so nothing has to be restated.

## 6. Levers worth knowing (client-side)

Pro mode suits hard, quality-critical tasks — architecture reviews and risky refactors, not routine edits. Programmatic tool calling suits bounded workflows where code processes several tool results at once (validating a batch of modules, aggregating findings). Both are the user's choices: recommend in one line when clearly useful, then proceed.
