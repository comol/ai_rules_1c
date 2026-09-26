---
description: MCP obligations and evidence policy — tool availability, risk-bearing scope, platform-first, template reuse, validator budgets, call discipline, server answers. Load before choosing 1C MCP tools; AGENTS.md indexes it by the same section numbers.
alwaysApply: false
category: tooling
---

# MCP Policy — Obligations and Evidence

This file owns the obligations summarized in `AGENTS.md → MCP Tool Calling`. Routing and schemas: `content/skills/mcp-1c-tools/SKILL.md`; validator budgets and triage: `verification-policy.md`.

## Tool availability

All availability-driven routing checks BOTH policy and runtime. **Exposed** describes the live tool schema; exposure alone never overrides policy. Before selecting tools, read applicable `TOOL_*` keys in `.dev.env`; names: `content/rules/dev-standards-env.md → Tool policy`. Commands, skills and subagents inherit this filter, including instructions phrased as «when exposed/connected».

- `auto` (missing / empty default): use eligible tools; on absence or failure follow the operation's documented fallback.
- `off`: do not call, probe, recommend installing, or bypass the provider through aliases, HTTP or CLI. Record `disabled by policy` when it affects required evidence; then use the documented fallback.
- `required`: when task/depth/routing selects this provider, it must supply the needed capability. Missing tools, failed calls or unsuitable scope block that step; alternatives can gather context but cannot satisfy it. Continue independent work. Do not downgrade or auto-install. This does not invoke unrelated providers, inactive workflows or already-unneeded fallbacks.
- An invalid non-empty value leaves that provider's dependent step blocked until corrected; never interpret a typo as permission. Settings are case-insensitive. Installation/status commands may inspect a disabled tool on explicit request; installation does not change policy. A specific user override applies only to its stated scope.

Runtime evidence is operation-specific: MCP tools must be callable in this session; CLI tools must already exist and run; read and write capabilities are separate. Config entries, healthy endpoints and `required` do not prove capability. Select verified project/layer/IB scope and check freshness before relying on results. Tool failures follow section C, not a new retry loop. Re-evaluate after policy, session or target changes; pass policy and evidence to children, which check their own exposed tools.

These switches select execution paths, never waive hard gates. `auto`/`off` fallbacks keep their own limitations: unavailable standards stay unverified/blocked, missing validators require compensating checks, memory falls back locally, metadata/IB/repository tooling gates remain. `USE_EDT` and `UI_TESTING` still decide whether those workflows apply; a tool flag cannot activate them. Report relevant gaps with policy, capability and consequence, distinguishing disabled, absent, failed and wrong/stale scope.

### A. Priority and obligation

1. **Mandatory scope.** When a relevant server is exposed, MCP calls are mandatory for risk-bearing 1C work: BSL / metadata edits or review, metadata XML, forms, integrations, refactoring, performance, runtime errors, platform API checks, impact analysis, syntax / quality validation, project-memory operations, and OpenSpec spec authoring that references concrete 1C facts (`content/rules/sdd-integrations.md`). Prose-only Markdown / rules work needs no 1C MCP calls — validate structure, links, paths and consistency instead.
2. **Conditional external knowledge.** Platform docs, БСП / SSL and ITS tools — when the task depends on versioned platform behaviour, reusable БСП APIs, or standards compliance; not for prose cleanup.
3. **Verify before writing BSL / metadata / specs.** Use the minimum evidence set from `content/rules/tooling-playbooks.md → Minimum Evidence Matrix`: quick-fix — the directly relevant code / syntax context; full-cycle — templates, existing project code, metadata, and platform / БСП / ITS docs when they affect correctness; metadata XML / forms — schema, examples, metadata validation; spec authoring — `recall` plus the MCP tools that confirm every referenced 1C fact. The final answer of a non-trivial BSL / metadata change or spec lists the context sources actually used; skipping a relevant source silently is a defect.
4. **No blind chaining; MCP-first search.** Every call closes a concrete context gap (section C). On 1C project source the eligible project-index tools come before native discovery, within verified contour coverage, with a bounded miss → native fallback and a "what was tried" note; an empty result proves absence only with coverage and freshness evidence. Never invent a `grep` argument (Code's file-scan fallback is internal) and never substitute a neighbouring contour's index. Canon, including contour scope, the fragment-first `Read` rule and the fallback note — `content/rules/mcp-first-search.md → Hard rule`; multiple roots — `content/rules/multi-contour-search.md`.
5. **Validate changed 1C code.** After BSL / metadata edits: `syntaxcheck` → `check_1c_code` → `review_1c_code` within the budget of section B; metadata XML — `verify_xml`; metadata **mutations** go through the `1c-metadata-manage` skill (`AGENTS.md → Skills and Subagents`). `syntaxcheck` means the `1c-syntax-checker-mcp` step, and its default form is **`syntaxcheck_file`** — check the saved module by path whenever that tool is exposed; pass code text only when the file tool is not exposed or the code has no file yet, then confirm by path once written (`content/skills/mcp-1c-tools/docs/1c-syntax-checker-mcp.md`).
6. **ITS documents.** Follow `its_help` with `fetch_its` for every returned document ID you rely on.
7. **Platform-capability check — hard gate for specialized domains.** Before designing a custom implementation of cryptography / digital signatures, СЛАУ and numerical methods, data analysis / ML, the collaboration system and its bots, integration buses / queues, full-text search, regular expressions, or any similar platform-level feature: ask `1C-docs-mcp` (`docsearch` by capability → `docinfo` for every exact name found) and `ssl_search` where a БСП solution is plausible. Model memory is not evidence of absence. A found, usable mechanism is the foundation — custom code only for glue; near-fit is not rejection; a genuine partial fit → `CONFUSION` (platform + glue vs custom), and when asking is impossible — default to the platform mechanism and note the residual gap. Rejecting a found mechanism on your own authority requires hard evidence (version / `РежимСовместимости` incompatibility, doc-confirmed functional mismatch), stated in the final answer. Hand-rolling without the check, or despite a usable find, is a defect. Query patterns and the domain list — `content/skills/mcp-1c-tools/docs/1C-docs-mcp.md → Platform capability discovery`.
8. **`templatesearch` query — this tool only.** Pass the user's task text verbatim or a same-goal prose paraphrase; on a miss reformulate as another task description, never keywords. Pre-flight and examples — `content/skills/mcp-1c-tools/docs/1c-templates-mcp.md → Query formulation`. Other search tools keep their own query conventions.
9. **`templatesearch` — reuse, do not reinvent.** A returned template that solves the same task is the base: adapt only metadata names, filters, placement, call site. Rejection needs a named reason (doc-confirmed version incompatibility, explicit user requirement, a nameable project-rule violation in the template — fixed inside the template when local, full rejection only when it is the core algorithm); «I'd rather write it differently» is not one. Report in one line: `Template: <name> — used as base` / `— used as base, fixed: <anti-pattern>` / `— rejected: <reason>`, or «no fitting template». Canon — `content/skills/mcp-1c-tools/docs/1c-templates-mcp.md → Using a found template`.

### B. Limits and non-determinism

1. **Verification budget.** One clean pass per validator on the latest artifact state; a blocking defect needs a fix and a clean confirming run within the depth budget; never a run against unchanged content or a loop for style noise; budget exhausted without a clean pass = gate failed, artifact unverified. Canon (blocking severities, 2 / 3 call limits, pure-XML case, promotion-trigger floor) — `content/rules/verification-policy.md → Validator budget`.
2. **AI-based MCP tools are non-deterministic.** `ask_1c_ai`, `rewrite_1c_code`, `modify_1c_code`, `answer_metadata_question` produce drafts, not authority; re-validate their output with the chain above before delivery.

### C. Call discipline and server answers

1. **Every call adds information** that is not already in the collected context; «just to be safe» is not a reason. **No-change repeats:** the same search, validator input or file against the same unchanged state is forbidden; repeat only when parameters change substantially, the state changed (edit, generation, resumed session, user edit), or freshness matters before a destructive action / final verification. Independent opening calls (memory recall, `templatesearch`, first index search) go out as one parallel batch.
2. **Tune each query to the tool's schema** before calling a parameter-rich tool (`search_type`, `detail_level`, `object_type`, `direction`, `depth`, `names_only`, `exact`, `top_k`, `project_name`); on a miss reformulate once before switching tools. Call quality never relaxes the obligation to call.
3. **Prefer structural tools over manual grep** — `search_function`, `get_module_structure`, `get_method_call_hierarchy` before substring search (`content/rules/mcp-first-search.md → Full-file Read — fragment first`).
4. **Argument names come from the operation skill**, never from intuition: `content/skills/1c-code-search`, `1c-meta-info`, `1c-impact`, `1c-form-inspect`, `1c-validate`, `1c-platform-help`, `1c-templates-memory`, `1c-live-ib` (`SKILL.md` each). A tool named there needs no schema fetch; fetch a schema (`get_graph_tool_schema` and the like) at most once per tool per session, only for a tool no skill names or after a schema rejection. `list_graph_projects` once per session.
5. **A server answer maps to an action by its code, not by prose.** The table is the whole recovery strategy; confirming the same gap through sibling tools is blind chaining (`content/rules/mcp-first-search.md → Hard rule 3`).

#### C. Server answers → actions

| Answer (code, field or text) | Servers | Action |
|---|---|---|
| `Missing required argument` / `Unexpected keyword argument` / `invalid_argument` naming a parameter | all | Re-read the argument table of the operation skill, retry **once** with the corrected name; never a second alias guess |
| `invalid_argument` naming a missing template / index / operation | graph | The lane is closed for this session: take the documented fallback in one step (`1c-meta-info`, `1c-impact`) |
| `lane_disabled`, a tool absent from `tools/list`, `degraded: true` | graph | Closed lane: change lanes, do not rephrase; `list_graph_capabilities` once if the state is unclear |
| `tabular_part_columns_not_indexed`, `form_not_indexed` warnings | graph, code | One call to the named fallback (`get_metadata_details(..., sections="tabular_parts")`, `search_forms`); no further graph attempts |
| `timeout` (`error.code`) | graph, checker | Do not resend: narrow the query, lower `max_items`, or switch to a structural tool; a first-call `fetch failed` is a transport reconnect — repeat that one call once |
| `not_found`, `outcome: "not_found"`, empty `items` with a ready generation | docs, ssl, graph, code | A finished negative answer: reformulate once if wording can help, then the next lane; with no freshness evidence report «inconclusive», not «absent» |
| `ambiguous_name` with candidates | ssl, docs | Refine by signature or fetch the intended `doc_id`; never pick an overload silently |
| `stale_cursor`, `invalid_cursor` | ssl, graph | Restart that search without the cursor, keeping the same verified scope and query; do not mix pages from different generations |
| `stale_generation` | graph | Restart without the obsolete `generation` and cursor, keeping the verified `project_id` and query; read the active generation and discard old pages |
| `source_refresh.drift` is set, including with tasks `completed` | graph | The graph lags behind its export. Use current source or another verified index; do not claim freshness or force a refresh as search recovery |
| `ingestion_busy`, `refresh_in_progress` | graph administration | No new refresh was started. Report the busy state; do not loop or launch a competing writer |
| `truncated: true`, `exhaustive: false`, `next_cursor` | all paged tools | Continue paging with identical arguments before any exhaustive claim |
| `project_not_registered`, `refresh_capability_unavailable` | graph | Operator matter: report, do not register projects or force refreshes from the agent |
| `mutation_auth_required` | templates | For gated `add_template` / `plugin_reload`, repair the operator connection; never print tokens or retry blindly. Current `remember` is ungated; if an older deployment rejects it, record that observed contract and use the memory fallback |
| `provenance.index` = `absent` / `building` / `failed` | syntax | Read the boundary (syntax and local rules only); never wait, restart or reconfigure |
| `status: invalid` with `errors` | code `verify_xml` | Fix the XML, one confirming `verify_xml` |
| Blocking `error` / `critical` from a validator | syntax, checker | Fix, then the confirmation budget of `verification-policy.md`; after the budget the gate failed and the artifact is unverified |
| HTTP 401 / 403, tools not exposed | data, any | The server is unavailable in this session: say so once, use the documented degradation, never synthesise its output |
| Untyped prose error | any | Treat as `timeout`-class: one reformulation, then the next lane, and name the text in the delivery |
