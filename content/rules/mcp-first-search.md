---
description: "Searching 1C project source — code, metadata, usages, files; project-index MCP versus Grep, Glob and Read. Load before any code, metadata, usage or file search in a 1C project."
alwaysApply: false
category: tooling
---

# MCP-first search discipline

For any 1C **project-source search** (code, metadata, usages, call chains, structure, forms, layouts, **and locating the source files themselves**) — MCP project-index tools come **first**. Native discovery tools — `Grep` / `rg`, `Glob` / file search by pattern (`**/*.bsl`, `**/*.xml`), directory listing, semantic codebase search, sequential `Read`-scanning of modules — are the **last resort**, gated by an explicit justification note.

**What counts as search.** Any action whose goal is to *locate* code, metadata, or files you do not yet have an exact path or qualified name for — including "getting oriented" sweeps at the start of a task (globbing the source tree, listing directories, reading modules one after another to see what is there). All of it falls under the hard rule below. Reading a specific file **already located via MCP** — to edit it, or to see a found fragment in full context — is normal work, not search, and needs no justification.

This file is the single owner of the search discipline and of the project-source fallback chain; `mcp-policy.md → A.4`, the `mcp-1c-tools` router, the operation skills and every subagent prompt point here. It applies to the parent and to every subagent.

**Policy and scope before tools.** Apply `TOOL_GRAPH` / `TOOL_CODE` (`content/rules/mcp-policy.md → Tool availability`). For multiple contours, use `content/rules/multi-contour-search.md` for mappings, coverage and selectors. Skip `off` or uncovered lanes without probes. Without an eligible index, scoped native search starts immediately; a missing/wrong-scope `required` index remains an unmet requirement even if local reads gather context. A catalog is optional for one contour.

**Explicit project on scoped calls.** For extensions or a multi-project graph, map current roots to `list_graph_projects`' returned base `project_id`, state it once and pass it on every supported project-data call (retries, comparisons, cursors included). Never omit scope or substitute list order, display name, `EXTENSION_NAME` or legacy `project_name`. Extensions are layers of one base `project_id`, never separate projects; follow each server's live schema (`content/rules/multi-contour-search.md`, `content/rules/extension-workspace.md`). Resolve ambiguity from descriptors before asking; local work with known scope continues.

---

## Hard rule

1. **Before any native discovery call on project source** (`Grep` / `rg`, `Glob` / file search, directory listing, semantic codebase search, `Read`-scanning, full-module `Read` for the sake of one routine — see *Full-file `Read` — fragment first* below), you MUST first exhaust the eligible project-index path for that contour. Only a content query counts: `list_graph_projects`, schema or status lookups and memory `recall` are not the index attempt.
   1. `1c-graph-metadata-mcp` — `search_code`, `search_metadata`, `search_metadata_by_description`, `get_object_dossier`, `trace_impact`, `trace_call_chain`, `find_objects_using_object`, `find_usages_of_object`, `business_search` as applicable.
   2. `1c-code-metadata-mcp` — `codesearch`, `metadatasearch`, `search_function`, `search_forms`, `get_module_structure`, `get_metadata_details`, `get_method_call_hierarchy`, `graph_dependencies`, `bsl_scope_members`, `inspect_form_layout`.
   3. Current Code search tools (`codesearch`, `metadatasearch`, `search_function`, `helpsearch`, `search_forms`) have **no `grep` input** — file scanning is an internal fallback (`search_layer: "grep"`). Never pass a guessed switch or repeat unchanged calls; use an explicit mode only if an older server's live schema exposes it.
2. **Only then `Grep` / `Glob` or another native discovery tool** — with a 1–2 sentence note in the response naming what MCP attempts missed. Silent fallback is a defect. **"Exhaust" is bounded:** one tuned call per angle + at most one useful reformulation; after a miss, native fallback is the right move, not blind chaining (`mcp-policy.md → A.4`).
3. **Tune once before switching lanes.** Reformulate only if wording/filters can help, using documented arguments from the operation skill (`1c-code-search`, `1c-meta-info`, `1c-impact`, `1c-form-inspect`). **A lane closed by the server stays closed** (disabled capability, missing index): follow `content/rules/mcp-policy.md → C. Server answers → actions` in one step without probing sibling tools.
4. **No-change repeats are forbidden** (`mcp-policy.md → C.1`): re-run only when parameters or project state changed.
5. **Negative results require freshness evidence.** An empty hit proves absence only with matching generation/readiness evidence (`source_refresh.drift` means stale even if tasks show `completed` — `mcp-policy.md → C. Server answers → actions`; incremental refresh may retain removed objects, so verify old hits against source). Otherwise call it inconclusive and move to the next lane; do not add routine health calls when not relying on absence.

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
| Canonical pattern / template | **`templatesearch` only** — task description verbatim; pre-flight `1c-templates-mcp.md → Query formulation (templatesearch only)` (`mcp-policy.md → A.8`) (+ `ssl_search` for БСП) | — |
| Platform API verification | `docinfo(name)` or `docsearch(query)` | `helpsearch` |
| A routed project standard (`anti-patterns`, `dev-standards-architecture`, …) | `standards(name="<rule stem>")` — **not** `docsearch`; `content/rules/help-corpus-retrieval.md` | `standards(query=…)` → `standards()` catalogue |
| On-disk XML shape of a form / role / DCS / MXL | `formatspec(name=…)` or `formatspec(query=…)` | `get_xsd_schema` |
| Does the platform ship a mechanism for X (СЛАУ, crypto, data analysis, bus, bots, …)? | `docsearch(capability description)` → `docinfo` per found name (`mcp-policy.md → A.7`) | `ssl_search` for a БСП-level solution |
| ITS standards | `its_help(query)` → `fetch_its(id)` for **every** relevant doc | — |

Native discovery tools (`Grep`, `Glob` / file search, directory listing, bulk `Read`) are absent from this table on purpose — they are not a first pick for any of these needs.

---

## Configurations with extensions

Keep the explicit base `project_id` above; a plain search hit proves existence, not runtime execution — use `resolve_effective_entity` / `compare_base_and_extension` (`content/skills/1c-impact/SKILL.md`). Absence in an extension requires a ready generation with the expected layer and matching provenance; uncovered contours take their own routes, and live-IB claims require named-target evidence. Canon — `content/skills/mcp-1c-tools/docs/1c-graph-metadata-mcp.md → Base configuration and extension layers`, routing — `content/rules/multi-contour-search.md`.

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
