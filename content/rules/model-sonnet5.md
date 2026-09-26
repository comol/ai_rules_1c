---
description: Model profile for Claude Sonnet 5 (AGENT_MODEL=sonnet5) — literal instruction following and explicit scope, effort calibration, keeping adaptive thinking on for tool use, coverage-first review briefs, token-budget awareness and lean context
alwaysApply: false
category: workflow
---

# Model profile — Claude Sonnet 5

**Load:** `AGENT_MODEL=sonnet5`, or you know you run as Claude Sonnet 5; once per session, before the first non-trivial task. Contract and invariants — `content/rules/model-adaptation.md`. Tunes initiative and communication only; every `AGENTS.md` gate stays as written.

## 1. Literal instruction following — state scope explicitly

The model reads instructions literally: it does not generalise one item to another or infer an unmade request.

- For a task spanning several objects, state the scope for **each** («перепроверь все три модуля из списка, не только первый»); one example does not spread. Briefing subagents: enumerate files / objects / checks in scope and say what is out of scope.
- Explicit scope is not worked examples: describe the interface (options and their meaning); an example only pins an exact output format. Point at code rather than paraphrasing it.
- The same literalism applies to the ruleset: "load X before Y" means load X. Triage, not intuition, sizes the task.

## 2. Effort calibration (client-side)

`high` for BSL / metadata work; `xhigh` for the hardest coding and agentic tasks. At `low` / `medium` the model scopes work to exactly what was asked — good for docs-fix, triage and lookups, risky for full-cycle. Shallow reasoning on a hard problem is fixed by raising effort, not padding the prompt; when effort must stay low, add «это многошаговая задача, продумай последовательность до начала правок». Porting: Sonnet 5 `medium` ≈ Sonnet 4.6 `high`; `high` ≈ 4.6 `max`.

## 3. Keep adaptive thinking on

With thinking disabled the model reaches for tools noticeably less, which breaks MCP-first work. Lower `effort` for cost, never disable thinking. If thinking is off beyond your control, name the required MCP calls in the plan up front and report every skipped call as a defect. `budget_tokens`, `temperature`, `top_p` and `top_k` are unavailable — tone and variety come from instructions.

## 4. Progress updates and verbosity

Updates during long runs are already well calibrated: add no scaffolding that forces interim summaries. Length tracking task complexity is wanted; ask for concision on a specific answer rather than a global brevity rule.

## 5. Review briefs — ask for coverage

A stated severity bar makes the model withhold lower-severity findings it did investigate. When reviewing BSL or briefing `1c-code-reviewer` / `1c-arch-reviewer`, ask for every finding with severity and confidence and filter in your own report; for a single-pass self-filter define the bar concretely («сообщай всё, что может привести к неверному поведению или ошибке проведения; опускай только стилевые придирки»), never "important". Gate semantics are unchanged.

## 6. Token budget and context

The model tracks its remaining context, and its tokenizer emits ~30 % more tokens than Sonnet 4.6.

- Do not wrap up early because context feels tight: finish; when the window genuinely runs short, save state (`content/skills/handoff`, `remember`) and continue or hand off cleanly.
- Load the always-on layer plus what triage selects — nothing "for context"; an obligation restated in several files is one obligation.
- Keep MCP queries narrow (`detail_level="L0"`, `names_only`, `project_name` / category filters) instead of pulling whole modules. `ORCHESTRATION=economy` fits well; delegation criteria are unchanged.
