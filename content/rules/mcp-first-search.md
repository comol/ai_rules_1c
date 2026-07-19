---
description: MCP-first search discipline — explicit priority of MCP project-index tools over Grep / Glob, with a mandatory "what was tried" note before any fallback. Load before any code / metadata / usage search in a 1C project.
alwaysApply: false
category: tooling
---

# MCP-first search discipline

For any 1C **project-source search** (code, metadata, usages, call chains, structure, forms, layouts) — MCP project-index tools come **first**. `Grep` / `Glob` are the **last resort**, gated by an explicit justification note.

Applies to every subagent except `1c-explorer`, which already encodes the same rule in its own prompt. The canonical fallback chain owner is `content/skills/mcp-1c-tools/SKILL.md → Fallback chain → Project-source search before Grep / rg`. This file does not redefine it — it makes the rule salient inside subagent prompts that previously only had a soft pointer.

---

## Hard rule

1. **Before any `Grep` / `Glob` call on project source**, you MUST first exhaust the project-index path:
   1. `1c-graph-metadata-mcp` — `search_code`, `search_metadata`, `search_metadata_by_description`, `get_object_dossier`, `trace_impact`, `trace_call_chain`, `find_objects_using_object`, `find_usages_of_object`, `business_search` as applicable.
   2. `1c-code-metadata-mcp` — `codesearch`, `metadatasearch`, `search_function`, `search_forms`, `get_module_structure`, `get_metadata_details`, `get_method_call_hierarchy`, `graph_dependencies`, `bsl_scope_members`, `inspect_form_layout`.
   3. `1c-code-metadata-mcp` with `grep=true` — substring retry inside the MCP index, **only** after step 2 returned not enough, and only on tools that expose the parameter (`codesearch`, `metadatasearch`, `search_function`, `helpsearch`, `search_forms`). Typical triggers: exact identifier, fragment of a query, metadata path, event-handler name, error text, literal string.
2. **Only then `Grep` / `Glob`** — and only when you can state, in one or two sentences inside the response, **which MCP attempts were tried and why they did not return what was needed**. Silent fallback to `Grep` / `Glob` is a defect.
3. **Tune the query before re-calling.** If the first MCP call returned nothing, do **not** immediately fall through to the next tool — reformulate: broaden / narrow the query, switch `search_type` (`fulltext` ↔ `semantic` ↔ `hybrid`), adjust `detail_level`, lower `exact`, raise `top_k`, drop or change `project_name` / category filters. Use the per-server parameter docs in `content/skills/mcp-1c-tools/docs/<server>.md`.
4. **No-change repeats are forbidden.** Do not re-run the same MCP call against the same unchanged state. A new call must change parameters substantively, or the project state must have changed (file edit, new generation, resumed session).

External-knowledge servers (`1c-templates-mcp`, `1c-ssl-mcp`, `1C-docs-mcp`, `1c-code-check-mcp`, `1c-syntax-checker-mcp`, `1c-data-mcp`) have **no `Grep` / `rg` equivalent** — they are called only when their knowledge is needed, not as part of the fallback above.

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
| Module structure overview | `get_module_structure(module_path)` | `inspect_form_layout` for forms |
| Form layout | `inspect_form_layout(object_name)` | `search_forms` |
| Canonical pattern / template | `templatesearch(query)` (+ `ssl_search` for БСП) | — |
| Platform API verification | `docinfo(name)` or `docsearch(query)` | `helpsearch` |
| ITS standards | `its_help(query)` → `fetch_its(id)` for **every** relevant doc | — |

`Grep` / `Glob` are absent from this table on purpose — they are not a first pick for any of these needs.

---

## When `Grep` / `Glob` are legitimately the right tool

The MCP-first rule applies to **1C project-source search**. `Grep` / `Glob` are appropriate, with no need for an MCP attempt first, when the target is **outside the MCP index**:

- non-BSL / non-metadata files: `.md` documentation, `.json` / `.yaml` configs, slash-command sources, rule files, `openspec/` artifacts, deployment logs;
- text fixtures, sample payloads, or generated reports under `handoffs/`, `dist/`, build output;
- a file you have already read in this session and are scanning for a literal string locally.

In all 1C project-source cases — follow the hard rule above.

---

## Response gate

Before delivering a result that involved `Grep` / `Glob` on project source, include a short line in the response, e.g.:

> *Tried `codesearch(query="...")` (empty), `search_function(name="...", exact=true)` (no match); fell back to `Grep` for the literal `<...>`.*

One or two sentences. No bullet list of every parameter tried.

---

## Success criteria

- ✅ MCP project-index path attempted before any `Grep` / `Glob` call on 1C project source.
- ✅ Each failed MCP call closed a concrete context gap before the next call (no blind chaining, no "just to be safe").
- ✅ `Grep` / `Glob` usage on project source is justified inline.
- ✅ No duplicated calls against unchanged state.
