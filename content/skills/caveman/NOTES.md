# caveman — maintainer notes

Companion of `SKILL.md` in this directory. Nothing here is a rule and nothing loads it at runtime: the skill file is the only text an agent reads. This file keeps what the audit found inert in the skill — the measurements behind the style, the deliberate deviations from upstream (so the next sync does not "fix" them), and the worked examples.

## Upstream

Adapted from https://github.com/JuliusBrussee/caveman (MIT), tracked against upstream **v2.2.0** (20.08.2026). Upstream's non-skill surface (proxy / engine / CLI / `caveman learn` / `/caveman-compress` / hooks, v2.x) is out of scope: this repo adapts the skill only, which upstream keeps MIT and unchanged by the v2 engine release.

## Honest numbers

The 65% is the upstream-measured average **output**-token reduction on chat prose against an unprompted baseline (range 22–87%). The style itself costs ~1–1.5k input tokens per turn, and on agentic coding runs the independently measured net effect is single-digit (JetBrains: 8.5% across 86 SkillsBench tasks, no detectable quality change). Use it for signal density, not as a token-budget lever.

## Upstream deviations (deliberate)

Kept against upstream v2.2.0 with a stated reason — do not "re-sync" them away on the next update:

- **Causal arrows stay allowed at `ultra`.** Upstream bans `→` because in English it costs its own token and saves nothing. In Russian it replaces a 2–3-token connector (`из-за чего`, `поэтому`), so the saving is real. Ambiguity is still governed by *Auto-clarity*.
- **Wenyan levels (`wenyan-lite` / `-full` / `-ultra`) are not ported** — the answer language is Russian per `AGENTS.md`; a classical-Chinese register has no use here.
- **Scope gating, `CAVEMAN` values and the boundary list are project-specific** — upstream has no `.dev.env`, no task-type classification and no BSL / metadata artifacts.
- **The "Never drop" list is project-specific** — it enumerates the evidence lines this ruleset mandates in a delivery report (`Metadata tooling:`, `Memory:`, `Template:`, the MCP-attempt note, gate-skip risk lines). Upstream has no such obligations; the list exists so that compression cannot be mistaken for permission to omit them.

## Worked examples

### Levels — "Почему форма медленно открывается?"

- lite: «Форма открывается медленно, потому что в `ПриСозданииНаСервере` идёт запрос внутри цикла по строкам табличной части. Вынести запрос наружу.»
- full: «`ПриСозданииНаСервере`: запрос внутри цикла по ТЧ → N запросов вместо одного. Вынести наружу, передавать массив ссылок.»
- ultra: «`ПриСозданииНаСервере` запрос в цикле ТЧ → N+1. Вынести → один запрос, массив ссылок.»

### Core pattern — `[вещь] [действие] [причина]. [следующий шаг].`

Bad: «Скорее всего, проблема в том, что в обработчике события `ПриЗаписи` вы создаёте новый объект на каждом вызове, и это приводит к лишним движениям регистра.»
Good: «Баг в `ПриЗаписи`: новый объект на каждом вызове → лишние движения регистра. Кешировать ссылку в реквизите формы.»

Bad: «Сначала, если вы не возражаете, я бы хотел уточнить, какой именно режим совместимости используется в вашей конфигурации, чтобы корректно подобрать вариант реализации.»
Good: «Какой `РежимСовместимости`? От него зависит выбор реализации.»

## Detail moved out of `SKILL.md` (2026-09-25, context-economy trim)

The skill loads into almost every development session under `CAVEMAN=auto`, so it was cut from ~10 KB to ≤4 KB and its description to ≤300 B (`tools/validate-rules.ps1` description budget). The rules kept their meaning; the illustrations and owner pointers below moved here.

- **Canon of the setting** — `content/rules/dev-standards-env.md → "CAVEMAN — caveman auto-activation"`; toggle — `content/commands/caveman.md`.
- **`auto` scope, long form.** On: writing / editing BSL, metadata XML, forms; refactoring; bug fixing; shell, deploy, infobase loads; lint / syntax triage; short technical Q&A. Off: PRDs, specifications, OpenSpec artifacts, user / admin docs, codemaps, API references, code / architecture / rule review, audit reports, handoffs, summaries and explanations longer than a couple of sentences, "why" / "compare" / "trade-offs" answers.
- **Force phrases, full list.** On: "caveman please", "как пещерный", "use caveman", "be brief", "коротко", "меньше токенов", `/caveman`. Off: "stop caveman", "normal mode", "обычный режим". Example of a non-trigger: «что делает caveman?». Level commands tolerate case and trailing punctuation (`/caveman Ultra.`).
- **Drop — Russian examples.** Filler: «просто», «в целом», «фактически», «по сути», «так сказать». Pleasantries: «конечно», «безусловно», «с радостью помогу», «хороший вопрос». Hedging: «возможно», «вероятно», «как правило», «скорее всего». Meta-narration: «сейчас я сделаю…», «далее я расскажу…», «подытоживая, …».
- **Never-drop owners.** `Metadata tooling:` / `IB tooling:` / `Repository tooling:` — `AGENTS.md → Skills and Subagents`; `Memory:` — `content/rules/project-memory.md`; `Template:` — `content/skills/mcp-1c-tools/docs/1c-templates-mcp.md`; context sources — `AGENTS.md → Development Procedure`, `content/rules/sdd-integrations.md → Context sources`; MCP-attempt note — `content/rules/mcp-first-search.md → Response gate`; gate-skip / standard-not-retrieved lines — `content/rules/verification-gates.md`, `content/rules/help-corpus-retrieval.md`; delivery report — `AGENTS.md → Deliver Clearly`.
- **Negations and abbreviations.** Scope words also include `нет`, `никогда`. Established acronyms: `БД`, `ИБ`, `ТЧ`, `ПКО`, `РС`, `РН`, `СКД`, `БСП`, `API`, `HTTP`; ad-hoc truncations to avoid: `конф`, `обр`, `рег`, `рекв` (decode cost, some ambiguous).
- **Naming the style** is allowed when the user asks about the mode or a rule requires it: the `/caveman` confirmation, a model profile recommending a level (`content/rules/model-fable5.md`). Never a "Caveman:" recap.
- **Tool calls.** After a result — the next call or the answer, unannounced. If the host mandates an opening line before the first call, one sentence is the whole budget.
- **Levels, long form.** `full` — "баг" not "проблема", "правка" not "внесение изменений". `ultra` — one word where one is enough; established 1C acronyms only.
- **Auto-clarity, full trigger list.** Also: changing metadata composition, an extension with `&ИзменениеИКонтроль`; ordered procedures of the «сначала…, затем…, только после этого…» kind.
- **Boundaries, long form.** Region headers are verbatim too; header documentation per `standards(name="dev-standards-code-style") §5`. «Заведи дефект» is the same case as «открой issue» — the body goes to people, so it is normal prose.

## Removed on purpose

The former "Quick checklist before sending a reply" restated *Core rules* and *Boundaries* item by item and was dropped; the rules themselves are the checklist.
