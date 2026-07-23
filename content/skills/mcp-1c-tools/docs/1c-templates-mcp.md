# 1c-templates-mcp — tool catalog

Code template library (`templatesearch`) and project vector memory (`remember` / `recall`). Memory routing rules live in `AGENTS.md → Project memory`.

> Load this file only if the `1c-templates-mcp` server is actually available in the current session.

| Tool | Parameters | Purpose | When to use |
|---|---|---|---|
| **templatesearch** | `query` | Hybrid search (semantic + fulltext) over the code-template library (2000+ entries) of ready-made solution patterns | Find architectural patterns and implementation examples **before** writing code; pass `query` per *Query formulation (`templatesearch`) only* below |
| **remember** | `content` (≥ 5 chars) | Save a free-form note to project memory (vector-indexed) | Persist a project-specific fact, user correction, standing working condition, or non-obvious decision that should survive across tasks |
| **recall** | `query` | Vector search over saved notes | At the start of any non-trivial task — recall earlier corrections, decisions, and project-specific quirks |

## Query formulation (`templatesearch` only)

> **Scope — read first.** Everything in this section applies **only** to the **`templatesearch`** tool on this server. It does **not** apply to `docsearch`, `codesearch`, `search_code`, `metadatasearch`, `ssl_search`, `recall`, or any other MCP tool — those keep their own query registers (keywords, identifiers, Lucene, chapter titles, etc.). **Do not** pass task-description prose to `docsearch` / `codesearch` because of this rule, and **do not** pass keyword salad to `templatesearch` because other tools accept keywords.

Templates are **ready-made solutions to typical tasks**, indexed by how tasks are described. For **`templatesearch` only**, the `query` argument must be the **user's task description** — Russian prose stating what to achieve — not a compressed keyword line and not query-language tokens.

### Pre-flight (mandatory before every `templatesearch` call)

Run on the `query` string **before** invoking **`templatesearch`**. If any check fails — rewrite; **do not call**.

1. **Tool check.** You are about to call **`templatesearch`** — not `docsearch`, not `codesearch`. This checklist applies to **`templatesearch` only**.
2. **Verbatim-first (first call).** If the user gave the task in natural language — pass that text **verbatim** (trim outer whitespace only) or a multi-clause paraphrase with the same goal. Do not invent a shorter "search phrase".
3. **Sentence test.** The `query` must read as one or more complete Russian sentences (subject + goal). Tag lists and «topic + topic + запрос + TOKEN» lines **fail**.
4. **No query-language tokens** unless the user literally wrote them: `ВЫБРАТЬ`, `ПОМЕСТИТЬ`, `СОЕДИНЕНИЕ`, `КОЛИЧЕСТВО`, `ГДЕ`, `ЛЕВОЕ`, `ОБЪЕДИНИТЬ`, …
5. **Anti-pattern spot-check** — if the `query` looks like any **Defect** row, **stop and rewrite** as the full task description:

| Defect — do not call `templatesearch` | Pass — call `templatesearch` |
|---|---|
| `уровень иерархии группы справочника запрос` | «Есть справочник с неограниченной иерархией. Нужно запросом вывести все группы и уровень иерархии каждой группы» |
| `уровень иерархии справочник запрос ПОМЕСТИТЬ` | user's task description — no `ПОМЕСТИТЬ` |
| `уровень иерархии группы справочника запрос КОЛИЧЕСТВО` | user's task description — no `КОЛИЧЕСТВО` |
| `иерархия справочник запрос группы` | full task description as prose |

Calling **`templatesearch`** with keyword salad is a **defect equal to skipping** the tool.

### What to pass (`templatesearch` only)

- **Query = task description.** Copy or lightly trim the user's wording; keep subject, context, and required outcome.
- **Good example.** User: «Есть справочник номенклатура с неограниченным числом уровней иерархии. Нужно запросом вывести все его группы и уровень иерархии каждой» → `query`: the same text verbatim (preferred) or an equivalent prose paraphrase.
- **Do not invent a "search phrase".** Wrong model habit: compressing the task into doc-search keywords — forbidden **for `templatesearch` only**.

### If the first `templatesearch` query misses

Reformulate as a **different task description** (rephrase the goal, add one clause from the user text) — up to 2 attempts. **Never** append keywords or query tokens. **Do not** switch to keyword style used for `docsearch` / `codesearch`.

## Using a found template (`templatesearch` only)

> Canon for `AGENTS.md → MCP Tool Calling → A.9`. Applies **after** a successful **`templatesearch`** — not to `docsearch` / platform docs (those follow `1C-docs-mcp.md → Using a found platform mechanism`).

When **`templatesearch`** returns a template that matches the task (same goal: e.g. «вывести группы справочника и уровень иерархии», «обход иерархии запросом», «HTTP JSON интеграция»):

1. **Treat it as the primary artifact** — the template body (query text, procedure skeleton, pattern) is the starting point, not a hint to ignore.
2. **Adapt, do not reinvent** — change only what the task requires: substitute metadata / attribute names, adjust filters, wire into the target module, wrap in project conventions (regions, export, error handling per project rules). Keep the proven structure (virtual tables, temp-table shape, join order, platform API calls).
3. **Do not rewrite from scratch** when the template already solves the core problem. Reimplementing the same algorithm «in your own words» is a defect equal to skipping **`templatesearch`**.
4. **No match after honest search** — only then design from project code (`codesearch`) or from platform docs (`docsearch` / `docinfo`). Say briefly that no fitting template was found.

### Template disposition (lightweight)

The obligation is scoped to **goal-matching** templates only. Vector search always returns *something* — irrelevant hits need no analysis, no justification, no per-candidate reporting. Scan the top results for a goal match and move on.

1. **Match found → copy-then-adapt.** Start the draft by **pasting the template body** (query / code), then edit it toward the task. Do not write a fresh draft «по мотивам»: if the delivered query / code shares no recognizable structure with the template you built on (temp-table chain, join order, algorithm skeleton, platform API calls), the delivery is defective — redo it from the template. In the final answer, name the base in one line: `Template: <short name> — used as base`.
2. **No match → one short note.** «Подходящего шаблона не нашлось» (item 4 above) is enough; do not enumerate or critique the non-matching candidates.
3. **Rejecting a goal-matching template needs a narrow reason**: a platform-version / `РежимСовместимости` incompatibility confirmed by docs, or an explicit user requirement the template contradicts. «Мне удобнее по-другому», style preference, distrust of the template's shape, or the urge to rewrite are **not** valid reasons. A template that solves the core task but needs adaptation is a **match** — adapt it (item 1 above), do not reject it.

**Good:** template has a hierarchical-catalog query → paste/adapt its query, rename `Справочник.Номенклатура` and output fields to the task; final answer says which template was the base.

**Good:** search returned 5 candidates, none solves the task's goal → one line «no fitting template found», solution designed from project code / docs; no candidate-by-candidate review.

**Defect:** template returned the standard «groups + hierarchy level» query → agent writes a different query from memory instead.

**Defect:** template found and goal-matching → agent silently ignores it and delivers a hand-rolled equivalent.

### Other tools — not covered here

| Tool | `query` register (unchanged by this file) |
|---|---|
| **`docsearch`** | Platform-doc topic / capability name |
| **`codesearch` / `search_code`** | Identifier, literal, metadata path |
| **`recall`** | Key terms from the task |
| **`ssl_search`** | Capability / API description |

## Notes on `remember`

- Write in English, one self-contained fact per note, preserving original 1C identifiers and affected object / module names as-is.
- Do not save secrets or PII.
- Call `remember` proactively: when the user corrects you, clarifies a non-obvious detail, or adjusts your interpretation of the task.
- **Standing working conditions are remember-worthy too**, not only object-level facts. If the user states a condition that will shape *future* tasks — "I am benchmarking you", "objects from task statements may not exist in the configuration", "always prefer built-in platform mechanisms" — save it immediately, in the same turn where it was said. The test: *would the next session behave differently if it knew this?* If yes and it is not already in the rules — `remember` now; deferring to "later" loses it.
- Call `recall` at the start of any non-trivial task with key terms (object name, subsystem, error message). Since standing conditions are also stored, add a generic pass when starting a new session's first task: `recall` with terms like `working conditions`, `benchmark`, `conventions` alongside the task-specific query.

### Memory gates — hard checks (canon: `AGENTS.md → Project memory → Memory gates`)

1. **Correction-capture gate.** Any user message that corrects your output, rejects an approach, clarifies a non-obvious fact, or states a standing condition **must produce a `remember` call in the same turn** (fallback: `memory.md → Captured during work` when the server is unavailable). Before ending such a turn, run the check: *did this message change how I or the next session should work? → saved?* Replying to the correction without saving it is a defect — the correction is lost for every future session.
2. **Recall-first gate.** For any non-trivial 1C task, `recall` runs **before** solution design — same standing as `templatesearch` in the pre-flight. Skipping it while the server is exposed is a defect.
3. **Memory line in the final answer.** Non-trivial tasks report memory usage in one line: `Memory: recalled <n> notes / nothing relevant; saved <n> notes / nothing to save`. This makes silent skips visible and reviewable.

**Defect:** the user says «я же просил использовать шаблон» (a correction of behavior) → agent apologizes, fixes the code, ends the turn — no `remember` (`rule-friction:` note per `AGENTS.md → Rules self-improvement`), no trace for the next session.

**Good:** same situation → agent fixes the code **and** in the same turn saves `rule-friction: user corrected: template from templatesearch was found but ignored; must use matched templates as code base (task: transitive closure query)`.

## Availability check

Treat the server as **available** only if the `remember` and `recall` tools are actually present in the current session's tool schema. The mere presence of `1c-templates-mcp` in `mcp-servers.json` does not prove availability. If `recall` returns a connection error — switch to memory fallback mode (see `AGENTS.md → Project memory → Availability`).
