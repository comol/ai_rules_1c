---
description: MCP-first search discipline — bounded priority of MCP project-index tools over native discovery tools (Grep, Glob / file search, directory listing, Read-scanning, full-module Read), with a mandatory "what was tried" note before fallback. Not a ban — without exposed servers or after an MCP miss, native tools apply immediately. Load before any code / metadata / usage / file-location search in a 1C project.
alwaysApply: false
globs: ["**/*.bsl", "**/*.xml"]
category: tooling
---

# MCP-first search discipline

For any 1C **project-source search** (code, metadata, usages, call chains, structure, forms, layouts, **and locating the source files themselves**) — MCP project-index tools come **first**. Native discovery tools — `Grep` / `rg`, `Glob` / file search by pattern (`**/*.bsl`, `**/*.xml`), directory listing, semantic codebase search, sequential `Read`-scanning of modules — are the **last resort**, gated by an explicit justification note.

**What counts as search.** Any action whose goal is to *locate* code, metadata, or files you do not yet have an exact path or qualified name for — including "getting oriented" sweeps at the start of a task (globbing the source tree, listing directories, reading modules one after another to see what is there). All of it falls under the hard rule below. Reading a specific file **already located via MCP** — to edit it, or to see a found fragment in full context — is normal work, not search, and needs no justification.

Applies to every subagent except `1c-explorer`, which already encodes the same rule in its own prompt. The canonical fallback chain owner is `content/skills/mcp-1c-tools/SKILL.md → Fallback chain → Project-source search before Grep / Glob / rg`. This file does not redefine it — it makes the rule salient inside subagent prompts that previously only had a soft pointer.

---

## Hard rule

1. **Before any native discovery call on project source** (`Grep` / `rg`, `Glob` / file search, directory listing, semantic codebase search, `Read`-scanning, full-module `Read` for the sake of one routine — see *Full-file `Read` — fragment first* below), you MUST first exhaust the project-index path:
   1. `1c-graph-metadata-mcp` — `search_code`, `search_metadata`, `search_metadata_by_description`, `get_object_dossier`, `trace_impact`, `trace_call_chain`, `find_objects_using_object`, `find_usages_of_object`, `business_search` as applicable.
   2. `1c-code-metadata-mcp` — `codesearch`, `metadatasearch`, `search_function`, `search_forms`, `get_module_structure`, `get_metadata_details`, `get_method_call_hierarchy`, `graph_dependencies`, `bsl_scope_members`, `inspect_form_layout`.
   3. `1c-code-metadata-mcp` with `grep=true` — substring retry inside the MCP index, **only** after step 2 returned not enough, and only on tools that expose the parameter (`codesearch`, `metadatasearch`, `search_function`, `helpsearch`, `search_forms`). Typical triggers: exact identifier, fragment of a query, metadata path, event-handler name, error text, literal string.
2. **Only then `Grep` / `Glob` or another native discovery tool** — and only when you can state, in one or two sentences inside the response, **which MCP attempts were tried and why they did not return what was needed**. Silent fallback is a defect regardless of which native tool it lands on — `Grep`, a file-pattern search, or a chain of `Read` calls used as a manual scanner. **"Exhaust" is bounded:** one well-tuned call per applicable angle plus the documented reformulation / `grep=true` retry — not an open-ended loop. Once that missed (nothing found, irrelevant hits, non-actionable output), falling back to native tools is the **correct next move**, not a defect; burning further MCP calls just to satisfy this rule is blind chaining (`AGENTS.md → A.4`).
3. **Tune the query before re-calling.** If the first MCP call returned nothing, do **not** immediately fall through to the next tool — reformulate: broaden / narrow the query, switch `search_type` (`fulltext` ↔ `semantic` ↔ `hybrid`), adjust `detail_level`, lower `exact`, raise `top_k`, drop or change `project_name` / category filters. Use the per-server parameter docs in `content/skills/mcp-1c-tools/docs/<server>.md`.
4. **No-change repeats are forbidden.** Do not re-run the same MCP call against the same unchanged state. A new call must change parameters substantively, or the project state must have changed (file edit, new generation, resumed session).

External-knowledge servers (`1c-templates-mcp`, `1c-ssl-mcp`, `1C-docs-mcp`, `1c-code-check-mcp`, `1c-syntax-checker-mcp`, `1c-data-mcp`) have **no `Grep` / `rg` equivalent** — they are called only when their knowledge is needed, not as part of the fallback above.

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

| Need | First call (MCP) | If empty — next |
|---|---|---|
| Find BSL code by behaviour / description | `search_code` (`semantic`, `detail_level=L1`) | `search_code` (`hybrid`) → `codesearch` |
| Find BSL code by exact identifier / literal | `search_code` (`fulltext`) | `codesearch(grep=true)` → only then `Grep` |
| Find a routine by name | `search_function(name, exact=true)` | `search_function(grep=true)` → `Grep` |
| Understand a metadata object | `get_object_dossier(object_name=...)` | `get_metadata_details(object_name=...)` |
| Metadata search by name / structure | `search_metadata` (JSON template) | `metadatasearch` (`names_only=true`) |
| Metadata search by Russian description / synonym | `search_metadata_by_description` or `business_search` | `metadatasearch` |
| Usages of an object | `find_usages_of_object(object_name=...)` / `find_objects_using_object(object_name=...)` | `graph_dependencies(object_name=..., direction="reverse")` |
| Impact of an object change | `trace_impact(object_name=..., direction="downstream", depth=3)` | `graph_dependencies(object_name=...)` (single-level) |
| Call graph (who calls / who is called) | `trace_call_chain(routine_name=..., object_name=..., direction="callers" \| "callees", depth=3)` | `get_method_call_hierarchy(method_name=...)` |
| Locate the source files / modules of an object | `get_object_dossier(object_name=...)` (paths in the passport) → `get_module_structure(module_path)` | `search_metadata` / `metadatasearch(names_only=true)` |
| "Get oriented" in an unfamiliar configuration | `search_metadata` (list by category) / `business_search` | `metadatasearch(names_only=true)` — **not** `Glob **/*.bsl` |
| Module structure overview | `get_module_structure(module_path)` | `inspect_form_layout` for forms |
| Form layout | `inspect_form_layout(object_name)` | `search_forms` |
| Canonical pattern / template | **`templatesearch` only** — task description verbatim; pre-flight `1c-templates-mcp.md → Query formulation (templatesearch only)` (`AGENTS.md → A.8`) (+ `ssl_search` for БСП) | — |
| Platform API verification | `docinfo(name)` or `docsearch(query)` | `helpsearch` |
| Does the platform ship a mechanism for X (СЛАУ, crypto, data analysis, bus, bots, …)? | `docsearch(capability description)` → `docinfo` per found name (`AGENTS.md → A.7`) | `ssl_search` for a БСП-level solution |
| ITS standards | `its_help(query)` → `fetch_its(id)` for **every** relevant doc | — |

Native discovery tools (`Grep`, `Glob` / file search, directory listing, bulk `Read`) are absent from this table on purpose — they are not a first pick for any of these needs.

---

## When `Grep` / `Glob` / `Read` are legitimately the right tool

This rule is a **bounded priority, not a prohibition** — the agent must always stay operational without MCP and must be free to search on its own after an MCP miss. Native tools are appropriate, with no need for an MCP attempt first, when:

- the project-index MCP servers (`1c-graph-metadata-mcp`, `1c-code-metadata-mcp`) are **not exposed** in the current session — the whole chain collapses; work with native tools normally and state the unavailability once, in one line;
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

- ✅ MCP project-index path attempted before any native discovery call (`Grep` / `Glob` / file search / directory listing / `Read`-scanning) on 1C project source — when the servers are exposed.
- ✅ No "getting oriented" sweeps (source-tree globbing, bulk module reading) while project-index MCP servers are exposed.
- ✅ Fragment-level retrieval preferred over full-module `Read` when the need is one routine — outside the normal-work cases listed above.
- ✅ Each failed MCP call closed a concrete context gap before the next call (no blind chaining, no "just to be safe").
- ✅ After a missed MCP attempt — or with servers not exposed — fallback proceeded immediately; no ritual MCP calls made only to satisfy this rule.
- ✅ Native-tool usage on project source is justified inline.
- ✅ No duplicated calls against unchanged state.
