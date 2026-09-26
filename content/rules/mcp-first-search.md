---
description: MCP-first search — project-index MCP tools get a bounded attempt before Grep, Glob, directory listing or Read-scanning, with a one-line "what was tried" note on fallback. Load before any code, metadata, usage or file search in a 1C project.
alwaysApply: false
category: tooling
---

# MCP-first search discipline

For any 1C **project-source search** (code, metadata, usages, call chains, structure, forms, layouts, **and locating the source files themselves**) — MCP project-index tools come **first**. Native discovery tools — `Grep` / `rg`, `Glob` / file search by pattern (`**/*.bsl`, `**/*.xml`), directory listing, semantic codebase search, sequential `Read`-scanning of modules — are the **last resort**, gated by an explicit justification note.

**What counts as search.** Any action whose goal is to *locate* code, metadata, or files you do not yet have an exact path or qualified name for — including "getting oriented" sweeps at the start of a task (globbing the source tree, listing directories, reading modules one after another to see what is there). All of it falls under the hard rule below. Reading a specific file **already located via MCP** — to edit it, or to see a found fragment in full context — is normal work, not search, and needs no justification.

This file is the single owner of the search discipline and of the project-source fallback chain; `AGENTS.md → MCP Tool Calling → A.4`, the `mcp-1c-tools` router, the operation skills and every subagent prompt point here. It applies to the parent and to every subagent.

**Policy and scope before tools.** Apply `TOOL_GRAPH` / `TOOL_CODE` (`content/rules/mcp-policy.md → Tool availability`). For multiple contours, use `content/rules/multi-contour-search.md` for mappings, coverage and selectors. Skip `off` or uncovered lanes without probes. Without an eligible index, scoped native search starts immediately; a missing/wrong-scope `required` index remains an unmet requirement even if local reads gather context. A catalog is optional for one contour.

**Explicit project on scoped calls.** Extension work and a graph serving multiple projects require a verified mapping from the current project/source roots to `list_graph_projects`' returned base `project_id`. State the selected project and relevant layer once, and supply that `project_id` on every project-data call that accepts it, including retries, evidence, comparisons and cursor pages. Never rely on an omitted/default scope, the first returned project, a configuration display name, or `EXTENSION_NAME`. A legacy `project_name` filter is not scope. Follow the live schema for other servers and layer selectors; do not invent or copy unsupported arguments. Resolve ambiguity from existing mappings/descriptors, then ask only if still unresolved; meanwhile scoped local work can continue.

---

## Hard rule

1. **Before any native discovery call on project source** (`Grep` / `rg`, `Glob` / file search, directory listing, semantic codebase search, `Read`-scanning, full-module `Read` for the sake of one routine — see *Full-file `Read` — fragment first* below), you MUST first exhaust the eligible project-index path for that contour:
   1. `1c-graph-metadata-mcp` — `search_code`, `search_metadata`, `search_metadata_by_description`, `get_object_dossier`, `trace_impact`, `trace_call_chain`, `find_objects_using_object`, `find_usages_of_object`, `business_search` as applicable.
   2. `1c-code-metadata-mcp` — `codesearch`, `metadatasearch`, `search_function`, `search_forms`, `get_module_structure`, `get_metadata_details`, `get_method_call_hierarchy`, `graph_dependencies`, `bsl_scope_members`, `inspect_form_layout`.
   3. Read the Code server's retrieval/fallback evidence. Current `codesearch`, `metadatasearch`, `search_function`, `helpsearch` and `search_forms` have **no `grep` input**: file scanning is an internal fallback, reported as `search_layer: "grep"`. Do not send a guessed switch or repeat an unchanged call to force that lane. An older server's explicit search mode may be used only when its live schema exposes it and a literal retry can answer the question.
2. **Only then `Grep` / `Glob` or another native discovery tool** — and only when you can state, in one or two sentences inside the response, **which MCP attempts were tried and why they did not return what was needed**. Silent fallback is a defect regardless of which native tool it lands on — `Grep`, a file-pattern search, or a chain of `Read` calls used as a manual scanner. **"Exhaust" is bounded:** one well-tuned call per applicable angle, with one reformulation only when it can help — not an open-ended loop. Once that missed (nothing found, irrelevant hits, non-actionable output), falling back to native tools is the **correct next move**, not a defect; burning further MCP calls just to satisfy this rule is blind chaining (`AGENTS.md → A.4`).
3. **Tune the query before re-calling.** If the first MCP search returned nothing and query reformulation can help, reformulate once: broaden / narrow the query, switch an exposed search mode, adjust detail level or result limits, or correct scope/category filters. Use only parameters exposed by that tool, with the names from the operation skill (`1c-code-search`, `1c-meta-info`, `1c-impact`, `1c-form-inspect`). An explicitly disabled capability or confirmed missing indexed structure is not a query-wording problem: proceed to the next applicable lane without a reformulation retry.
   **A lane closed by the server stays closed.** A typed error or a warning naming a missing index is the server's answer for this session: take the action its code maps to in `content/rules/mcp-policy.md → C. Server answers → actions` in one step. Probing the same gap through sibling tools is blind chaining, not diligence.
4. **No-change repeats are forbidden.** Do not re-run the same MCP call against the same unchanged state. A new call must change parameters substantively, or the project state must have changed (file edit, new generation, resumed session).
5. **A negative result needs freshness evidence.** An empty search response proves "not found" only when generation / readiness information available from the response or server shows that the index represents the relevant project state. On Graph, `get_indexing_status().source_refresh.drift` means the export has moved ahead even if tasks say `completed`; missing drift information does not certify freshness. Incremental refresh may retain removed metadata objects/forms, so verify their current existence from source before relying on an old hit. When evidence is absent, stale, degraded, or contradicted by fresh local edits, call the result inconclusive and continue to the next documented MCP or disk fallback. Do not add a health call merely to decorate a search whose absence you do not rely on.

External-knowledge servers (`1c-templates-mcp`, `1c-ssl-mcp`, `1C-docs-mcp`, `1c-code-check-mcp`, `1c-syntax-checker-mcp`, `1c-data-mcp`) have **no `Grep` / `rg` equivalent** — they are called only when their knowledge is needed, not as part of the fallback above.

**Read-only metadata questions:** honor an explicitly requested server; otherwise use the priority above. Retrieve only what answers the question: names/synonyms for object identification, bounded structure pages for a field list. Do not expand an identification hit into a full dossier unless its structure or evidence is needed. Code paging, payload shape and completeness checks are documented in `content/skills/mcp-1c-tools/docs/1c-code-metadata-mcp.md → Reading large metadata objects`.

One of them also holds **this project's own routed standards**: the `1c-standards` collection of `1C-docs-mcp`, reached with the `standards` tool (never with `docsearch` / `docinfo`, which cannot see it). That is a *rule* lookup, not a project-source search — it is outside the chain above and has its own contract in `content/rules/help-corpus-retrieval.md`. Reading a rule file on disk is likewise ordinary work, not search.

---

## Full-file `Read` — fragment first

`Read` of a whole BSL module to *find or understand one routine* is the same fallback as `Grep`. When the need is a fragment — retrieve at fragment level first: `get_module_structure(module_path)` for the layout, `search_code` (`detail_level="L0"`) or `search_function` for the full body of a specific routine, `bsl_scope_members` for available members of a context.

Full-file `Read` is **normal work** — no MCP attempt, no justification note — when:

- the file is your **direct edit target** (reading before editing is mandatory, not a fallback);
- the file is small (a few screens) — slicing it via MCP costs more than reading it;
- you (or the user) **just edited** the file — the MCP index may lag behind the disk; the disk state is the authority;
- whole-module context genuinely is the task (module-wide review, refactor, region restructuring);
- the fragment returned by MCP is truncated or insufficient and full context is needed to proceed.

---

## Quick first-pick table

Select the contour and verify route coverage first. The table names tool roles; use the mapped server/scope, skipping an uncovered graph for the contour's code index or scoped native fallback. A shared server's scope selectors come from its live contract (`content/rules/multi-contour-search.md`).

| Need | First call (MCP) | If empty — next |
|---|---|---|
| Find BSL code by behaviour / description | `search_code` (`semantic`, `detail_level=L1`) | `search_code` (`hybrid`) → `codesearch` |
| Find BSL code by exact identifier / literal | `search_code` (`fulltext`) | `codesearch(query=...)` → scoped `Grep` after a bounded miss |
| Find a routine by name | `search_function(name, exact=true)` | Refine name / `module_path` once when useful, then scoped `Grep`; no `grep` input |
| Understand a metadata object | `get_object_dossier(object_name=...)` | `get_metadata_details(object_name=...)` |
| Columns of tabular parts (реквизиты табличных частей) | `get_object_dossier(object_name=..., sections=["structure"])`; use indexed columns when present | On `tabular_part_columns_not_indexed`, go directly to `get_metadata_details(object_name=..., sections="tabular_parts")` (or `tabular_part="<name>"`); no further Graph attempts for missing columns |
| Metadata search by name / structure | `search_metadata` (JSON template) | `metadatasearch` (`names_only=true`) |
| Metadata search by Russian description / synonym | `search_metadata_by_description(query, filter_type="Документы")` — category in Russian plural; `business_search` only when `list_graph_capabilities` shows the lane enabled | `metadatasearch` |
| Usages of an object | `find_usages_of_object(object_name=...)` / `find_objects_using_object(object_name=...)` | `graph_dependencies(object_name=..., direction="reverse")` |
| Impact of an object change | `trace_impact(object_name=..., direction="downstream", depth=3)` | `graph_dependencies(object_name=...)` (single-level) |
| Call graph (who calls / who is called) | `trace_call_chain(routine_name=..., object_name=..., direction="callers" \| "callees", depth=3)` | `get_method_call_hierarchy(method_name=...)` |
| Locate the source files / modules of an object | `get_object_dossier(object_name=...)` (paths in the passport) → `get_module_structure(module_path)` | `search_metadata` / `metadatasearch(names_only=true)` |
| "Get oriented" in an unfamiliar configuration | `search_metadata` (list by category) / `business_search` | `metadatasearch(names_only=true)` — **not** `Glob **/*.bsl` |
| Module structure overview | `get_module_structure(module_path)` | `inspect_form_layout` for forms |
| Form layout | `inspect_form_layout(object_name)` | `search_forms` |
| Canonical pattern / template | **`templatesearch` only** — task description verbatim; pre-flight `1c-templates-mcp.md → Query formulation (templatesearch only)` (`AGENTS.md → A.8`) (+ `ssl_search` for БСП) | — |
| Platform API verification | `docinfo(name)` or `docsearch(query)` | `helpsearch` |
| A routed project standard (`anti-patterns`, `dev-standards-architecture`, …) | `standards(name="<rule stem>")` — **not** `docsearch`; `content/rules/help-corpus-retrieval.md` | `standards(query=…)` → `standards()` catalogue |
| On-disk XML shape of a form / role / DCS / MXL | `formatspec(name=…)` or `formatspec(query=…)` | `get_xsd_schema` |
| Does the platform ship a mechanism for X (СЛАУ, crypto, data analysis, bus, bots, …)? | `docsearch(capability description)` → `docinfo` per found name (`AGENTS.md → A.7`) | `ssl_search` for a БСП-level solution |
| ITS standards | `its_help(query)` → `fetch_its(id)` for **every** relevant doc | — |

Native discovery tools (`Grep`, `Glob` / file search, directory listing, bulk `Read`) are absent from this table on purpose — they are not a first pick for any of these needs.

---

## Configurations with extensions

A graph that ingested the base and its extensions holds them as **ordered layers of one base `project_id`**: select it via `list_graph_projects` matched to the current roots, keep it explicit on base and extension searches, never register an extension as a separate project and never pass an extension name as `project_id`. A plain search hit shows that a version exists, not that the platform executes it — use `resolve_effective_entity` / `compare_base_and_extension` (`content/skills/1c-impact/SKILL.md`). Absence in an extension needs a current ready generation with the expected layer present and response provenance matching the selected project and layer; a registered project, a fast `completed` refresh or an empty layer list is not that evidence. Uncovered contours take their own routes; claims about a running infobase need evidence for that named target. Canon — `content/skills/mcp-1c-tools/docs/1c-graph-metadata-mcp.md → Base configuration and extension layers`, routing — `content/rules/multi-contour-search.md`.

---

## EDT workspaces

With `USE_EDT=true` the chain above is unchanged; `edt-mcp` is an **additional** live-workspace source, and its literal, non-dialect-aware `search_in_code` ranks with `Grep`, not with `search_code`. Reconcile EDT model and disk before trusting either — `content/rules/edt-workflow.md → Model vs disk — the synchronization rule`; tool choice — `edt-workflow.md → Search and navigation`.

---

## When `Grep` / `Glob` / `Read` are legitimately the right tool

This rule is a **bounded priority, not a prohibition** — the agent must always stay operational without MCP and must be free to search on its own after an MCP miss. Native tools are appropriate, with no need for an MCP attempt first, when:

- no project-index MCP server exposed in the current session has **verified coverage of the selected contour** — the chain for that contour collapses; search its own files and state the missing route once, in one line;
- an MCP result **looks wrong or stale** (contradicts known facts, predates fresh local edits) — verifying or overriding it against the disk state via `Grep` / `Read` is legitimate; after local edits the disk is the authority, not the index;
- the target is **outside the MCP index**: non-BSL / non-metadata files (`.md` documentation, `.json` / `.yaml` configs, slash-command sources, rule files, `openspec/` artifacts, deployment logs), text fixtures, sample payloads, generated reports under `handoffs/` / `dist/` / build output;
- a file you have already read in this session and are scanning for a literal string locally;
- reading a file whose path came from an MCP result (edit target, full context of a found fragment) — see also *Full-file `Read` — fragment first* above.

And after an MCP attempt that **missed** (tuned call + documented retry returned nothing relevant) — fall back immediately with the one-line "what was tried" note; no further MCP calls are owed to this rule.

In all remaining 1C project-source cases — follow the hard rule above.

---

## Response gate

Before delivering a result that involved any native discovery tool (`Grep` / `Glob` / file search / `Read`-scanning) on project source, include a short line in the response, e.g.:

> *Tried `codesearch(query="...")` (empty), `search_function(name="...", exact=true)` (no match); fell back to `Grep` for the literal `<...>`.*

One or two sentences. No bullet list of every parameter tried.

---

## Success criteria

- ✅ Eligible MCP project-index path attempted before any native discovery call (`Grep` / `Glob` / file search / directory listing / `Read`-scanning) on 1C project source — when exposed indexes cover the selected contour.
- ✅ No "getting oriented" sweeps (source-tree globbing, bulk module reading) while an eligible project-index route covers that scope.
- ✅ Fragment-level retrieval preferred over full-module `Read` when the need is one routine — outside the normal-work cases listed above.
- ✅ Each failed MCP call closed a concrete context gap before the next call (no blind chaining, no "just to be safe").
- ✅ After a missed MCP attempt — or with servers not exposed — fallback proceeded immediately; no ritual MCP calls made only to satisfy this rule.
- ✅ A typed error or a named missing-index warning was treated as the final answer of that lane; no sibling-tool probing of the same gap.
- ✅ Native-tool usage on project source is justified inline.
- ✅ No duplicated calls against unchanged state.
- ✅ A definitive "not found" conclusion is backed by current generation / readiness evidence; otherwise the MCP miss is reported as inconclusive and the documented fallback is used.
- ✅ For a unified layered graph, the base `project_id` and relevant layers were used; uncovered contours took their own routes. Source/index conclusions were distinguished from evidence about a running infobase.
