# 1c-templates-mcp — tool catalog

Code template library (`templatesearch`) and project vector memory (`remember` / `recall`), both governed by `TOOL_TEMPLATES`. Memory search scope and write fallback follow `content/rules/project-memory.md`; do not expand quick-fix to all providers or bypass a required provider failure. Tool mappings: `content/skills/mcp-1c-tools/docs/memory-providers.md`.

> Load this file only if `1c-templates-mcp` is actually available in the current session. The expanded catalogue below is published in beta; stable tags expose an older surface. `tools/list` is authoritative.

| Tool | Parameters | Purpose | When to use |
|---|---|---|---|
| **templatesearch** | `query` | Hybrid search (semantic + fulltext) over the code-template library (2000+ entries) of ready-made solution patterns | Find architectural patterns and implementation examples **before** writing code; pass `query` per *Query formulation (`templatesearch`) only* below |
| **list_templates** | `limit=50`, `offset=0` | Bounded catalogue page without source code; follow `next_offset` until `null` | Browse the library without an unbounded payload |
| **get_template** | `template_id` | Full template body by ID | Fetch code for a catalogue/search hit |
| **recall** | `query` | Vector search over saved notes | At the start of any non-trivial task — recall earlier corrections, decisions, and project-specific quirks |
| **plugin_state** | none | Plugin hooks/tables, errors and derived-index fingerprint | Diagnose extensions without mutating the server |
| **add_template** | `description`, `code` (both ≥ 10 chars) | Persist and index a template | Conditional mutation; only on an explicit request |
| **remember** | `content` (≥ 5 chars) | Save a free-form note to project memory (vector-indexed) | Always registered; persist a durable project fact without an operator token |
| **plugin_reload** | none | Atomically reload plugins | Conditional live mutation; only on an explicit operator request |

`remember` is always registered on the current server, independently of `MCP_ENABLE_WRITE_TOOLS` and `MCP_OPERATOR_TOKEN`, and needs no `Authorization` header. It still validates note content. Only `add_template` and `plugin_reload` are gated: they are registered when `MCP_ENABLE_WRITE_TOOLS=true` and a valid `MCP_OPERATOR_TOKEN` is configured, and their calls require the matching bearer header in the MCP client configuration. A gated call without that header returns `mutation_auth_required`; do not retry blindly or expose the token in output. `plugin_reload` changes live behavior and can invalidate derived indexes, so routine searches must never invoke it.

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
3. **Rejecting a goal-matching template needs a narrow, nameable reason.** Exactly three are valid:
   - a platform-version / `РежимСовместимости` incompatibility confirmed by docs;
   - an explicit user requirement the template contradicts;
   - **a project-rule violation you can name** — an anti-pattern from `standards(name="anti-patterns")`, a forbidden construct from `standards(name="dev-standards-code-style") §2`, or a documented ITS-standard violation. Naming it is mandatory: "выглядит неоптимально" is not a reason, «запрос в цикле (`standards(name="anti-patterns") §1`)» is.

   «Мне удобнее по-другому», style preference, distrust of the template's shape, or the urge to rewrite are **not** valid reasons. A template that solves the core task but needs adaptation is a **match** — adapt it (item 1 above), do not reject it.

4. **A project-rule violation is a reason to fix the template, not usually to drop it.** Most findings are local — a missing `ПЕРВЫЕ N`, a redundant `РАЗЛИЧНЫЕ`, an unindexed temp table, a `Сообщить()` call, a `Попытка` around a DB read. Keep the template's proven structure and repair the defect in place; report it as `Template: <short name> — used as base, fixed: <anti-pattern>`. Full rejection is correct only when the violation **is** the structure (the template's core algorithm is a query in a loop, a correlated subquery per row, an object read inside a posting loop) — there the salvageable part is the intent, not the code. Report that as `Template: <short name> — rejected: <anti-pattern / rule>`.

   The template library is not a source of truth about project standards: a template that predates a rule still returns as a match. This item is the only legitimate channel for that case — silently hand-rolling an equivalent and saying nothing remains a defect (item 2 of *Using a found template*).

**Good:** template has a hierarchical-catalog query → paste/adapt its query, rename `Справочник.Номенклатура` and output fields to the task; final answer says which template was the base.

**Good:** search returned 5 candidates, none solves the task's goal → one line «no fitting template found», solution designed from project code / docs; no candidate-by-candidate review.

**Good:** goal-matching template selects the whole table without `ПЕРВЫЕ N` → keep the template's structure, add the limit, report `Template: <name> — used as base, fixed: missing ПЕРВЫЕ N (anti-patterns §5)`.

**Good:** goal-matching template's core algorithm reads each document object inside a loop → structural anti-pattern, rebuild as a set-based query, report `Template: <name> — rejected: object read in a loop (anti-patterns §1)`.

**Defect:** template returned the standard «groups + hierarchy level» query → agent writes a different query from memory instead.

**Defect:** agent rejects a goal-matching template as «неоптимальный» without naming the rule it violates — an unnamed objection is a style preference, not a reason.

**Defect:** template found and goal-matching → agent silently ignores it and delivers a hand-rolled equivalent.

### Other tools — not covered here

| Tool | `query` register (unchanged by this file) |
|---|---|
| **`docsearch`** | Platform-doc topic / capability name |
| **`codesearch` / `search_code`** | Identifier, literal, metadata path |
| **`recall`** | Key terms from the task |
| **`ssl_search`** | Capability / API description |

## Notes on `remember`

- Before calling `remember`, confirm that the tool is exposed; do not require an operator token or Authorization pre-flight. The connected surface and actual answer govern compatibility with older deployments: if the tool is absent or the call returns `mutation_auth_required`, use the documented memory fallback instead of looping or assuming the current server requires authentication.
- Write in English, one self-contained fact per note, preserving original 1C identifiers and affected object / module names as-is.
- A `stored=true` / `index_pending=true` answer with an `id` is already durable even if `success=false`; indexing is pending, so do not repeat the write or create a fallback copy.
- Do not save secrets or PII.
- What to save, when to call `recall` / `remember`, the two hard gates (recall-first, correction-capture) and the `Memory:` line are owned by `content/rules/project-memory.md`; standing working conditions («I am benchmarking you», «objects from the task may not exist») are saved in the same turn like any correction.

**Defect:** the user says «я же просил использовать шаблон» → agent apologizes, fixes the code, ends the turn — no `remember` (`rule-friction:` note per `AGENTS.md → Rules self-improvement`), no trace for the next session. **Good:** same situation → agent fixes the code **and** in the same turn saves `rule-friction: user corrected: template from templatesearch was found but ignored; must use matched templates as code base (task: transitive closure query)`.

## Availability check

Check each capability separately. Template search is available when `templatesearch` is exposed. Memory read is available when `recall` is exposed. An exposed `remember` can be called without a token pre-flight; confirm persistence from its actual write result. The mere presence of `1c-templates-mcp` in `mcp-servers.json` proves none of these. For older deployments, follow the exposed schema and actual response. If `recall` fails, or `remember` is absent or definitively rejects the write, switch the affected operation to memory fallback mode (`content/rules/project-memory.md → Availability and fallback`). A timeout or ambiguous write is unconfirmed and must be reconciled before another write.
