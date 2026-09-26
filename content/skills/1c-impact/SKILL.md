---
name: 1c-impact
description: "Usages, dependencies, call chains and change impact of 1C objects and routines — callers, downstream breakage, register movements, extension changes — via the graph MCP with code-metadata fallback. Mandatory before renames, removals, refactoring and public-contract changes (Gate 4)."
argument-hint: "<Kind.Name | routine> [callers | callees | downstream] [depth]"
allowed-tools: mcp__1c-graph-metadata-mcp__trace_impact, mcp__1c-graph-metadata-mcp__trace_call_chain, mcp__1c-graph-metadata-mcp__find_usages_of_object, mcp__1c-graph-metadata-mcp__find_objects_using_object, mcp__1c-graph-metadata-mcp__find_register_movement_docs, mcp__1c-graph-metadata-mcp__get_register_writers, mcp__1c-graph-metadata-mcp__find_object_referrers, mcp__1c-graph-metadata-mcp__affected_subgraph, mcp__1c-graph-metadata-mcp__list_graph_projects, mcp__1c-graph-metadata-mcp__resolve_effective_entity, mcp__1c-graph-metadata-mcp__compare_base_and_extension, mcp__1c-code-metadata-mcp__graph_dependencies, mcp__1c-code-metadata-mcp__get_method_call_hierarchy
---

# 1c-impact — usages, call graph, change impact

Evidence for `content/rules/verification-gates.md → Gate 4` and for the pre-refactor analysis of `content/rules/tooling-playbooks.md → Refactoring`. Refactoring blind when these servers are exposed is a defect; when they are not, follow Gate 4 graceful degradation.

All graph project-data calls require the explicit returned `project_id` bound to the current roots; substitute `<resolved-project-id>` in the examples. Reuse it for searches, impact, evidence and pagination, with verified layer provenance for an extension. Follow the live schema for tools without this selector and for code-server scope; use verified fixed/session/entity scope or another scoped route, never invent arguments (`content/rules/multi-contour-search.md`).

## Tools and exact arguments

| Need | Call (graph first) | Fallback (code) |
|---|---|---|
| What breaks if the object changes | `trace_impact(object_name, direction="downstream", depth=3, relationship_types?)` | `graph_dependencies(object_name, direction="both" \| "forward" \| "reverse", limit=50)` |
| Who calls / what is called | `trace_call_chain(routine_name, object_name?, direction="callers" \| "callees", depth=3)` | `get_method_call_hierarchy(method_name, direction="both", depth=3)` |
| Attributes that reference an object | `find_usages_of_object(object_name)` | `graph_dependencies(..., direction="reverse")` |
| Objects that use a type | `find_objects_using_object(object_name)` | same |
| Documents declaring movements into a register | `find_register_movement_docs(register_name)` or `get_register_writers(register, direction="incoming")` | `codesearch(query="Движения.<Регистр>")` (source evidence only) |
| Direct BSL access / targets shared by several objects | `find_object_referrers(object_name?, access?, min_referrers=1)`; `access="read"` / `"write"`, omit for both | Bounded `codesearch` then scoped native source search |
| Release-level transitive impact | `affected_subgraph(roots, max_depth?, direction?, edge_types?)` with entity references from `resolve_graph_entity` | — |

Object/call tools use `object_name`, `routine_name`, `register_name`, `method_name`; `get_register_writers` instead uses `register` / `document`. Do not invent aliases. Recorder movements and direct BSL access are separate relations: an independent register can have no recorders but still have BSL writers. `find_object_referrers` proves static access with file/line evidence; a record-set factory is write intent, not proof of a committed write.

## Calls

```json
{"tool": "trace_impact", "args": {"project_id": "<resolved-project-id>", "object_name": "РегистрНакопления.ТоварыНаСкладах", "direction": "downstream", "depth": 3}}
{"tool": "trace_call_chain", "args": {"project_id": "<resolved-project-id>", "routine_name": "ПровестиДокумент", "object_name": "ОбщийМодуль.ПроведениеСервер", "direction": "callers", "depth": 3}}
{"tool": "find_usages_of_object", "args": {"project_id": "<resolved-project-id>", "object_name": "Справочник.Контрагенты"}}
{"tool": "find_register_movement_docs", "args": {"project_id": "<resolved-project-id>", "register_name": "РегистрНакопления.ТоварыНаСкладах"}}
{"tool": "get_method_call_hierarchy", "args": {"method_name": "ПровестиДокумент", "direction": "callers", "depth": 3}}
{"tool": "find_object_referrers", "args": {"project_id": "<resolved-project-id>", "object_name": "РегистрСведений.ПлановыеЕжегодныеОтпуска", "access": "write", "min_referrers": 1}}
{"tool": "affected_subgraph", "args": {"project_id": "<resolved-project-id>", "roots": ["РегистрНакопления.ТоварыНаСкладах"], "max_depth": 2, "direction": "downstream"}}
```

## Configurations with extensions

When the graph covers the relevant base/extension layers: `list_graph_projects`, match the current roots, keep the base `project_id`, and never register extensions as projects. Repeat discovery only when workspace/server context changes or the mapping becomes invalid. Effective implementation in that index — `resolve_effective_entity(project_id, object_name, entity_kind="MetadataObject", entity_name?)`; what one indexed extension changed — `compare_base_and_extension(project_id, object_name, extension_name)`. Keep the base and extension comparison inside that same project. Neither a plain hit nor an indexed effective view alone proves what runs in a named infobase.

For separate indexes or missing graph layers, use each contour's mapped code tools or own files. Account for base, primary, secondary and relevant infrastructure contours before project-wide impact/absence claims; disclose missing coverage. Routing and runtime-evidence boundaries — `content/rules/multi-contour-search.md`.

## Rules

- Read `truncated`, `exhaustive` (including `data.exhaustive`), `degraded` and `warnings`; an exhaustive claim needs a complete page set, verified scope and current sources. `source_refresh.drift` invalidates a Graph freshness claim even when tasks are `completed`; removed metadata/forms can survive an incremental refresh. See the graph catalog's refresh boundaries before relying on an old hit or requesting maintenance.
- Callers of a public `Экспорт` routine are a promotion trigger (`content/rules/verification-policy.md`); the caller list belongs in the delivery evidence.
- Typed answers map to actions by code — `content/rules/mcp-policy.md → C. Server answers → actions`.

Evidence-first tools (`find_graph_path`, `explain_graph_evidence`, `compare_graph_scope`), domain relations (rights, subscriptions, DCS lineage): `content/skills/mcp-1c-tools/docs/1c-graph-metadata-mcp.md`.
