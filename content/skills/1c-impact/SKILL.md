---
name: 1c-impact
description: "Usages, dependencies, call chains and change impact for 1C objects and routines — who uses an object, who calls a routine, what breaks downstream, which documents move a register, what an extension changes — through the graph MCP with the code-metadata fallback. Mandatory before renames, removals, refactoring and public-contract changes (Gate 4)."
argument-hint: "<Kind.Name | routine> [callers | callees | downstream] [depth]"
allowed-tools: mcp__1c-graph-metadata-mcp__trace_impact, mcp__1c-graph-metadata-mcp__trace_call_chain, mcp__1c-graph-metadata-mcp__find_usages_of_object, mcp__1c-graph-metadata-mcp__find_objects_using_object, mcp__1c-graph-metadata-mcp__find_register_movement_docs, mcp__1c-graph-metadata-mcp__affected_subgraph, mcp__1c-graph-metadata-mcp__list_graph_projects, mcp__1c-graph-metadata-mcp__resolve_effective_entity, mcp__1c-graph-metadata-mcp__compare_base_and_extension, mcp__1c-code-metadata-mcp__graph_dependencies, mcp__1c-code-metadata-mcp__get_method_call_hierarchy
---

# 1c-impact — usages, call graph, change impact

Evidence for `content/rules/verification-gates.md → Gate 4` and for the pre-refactor analysis of `content/rules/tooling-playbooks.md → Refactoring`. Refactoring blind when these servers are exposed is a defect; when they are not, follow Gate 4 graceful degradation.

## Tools and exact arguments

| Need | Call (graph first) | Fallback (code) |
|---|---|---|
| What breaks if the object changes | `trace_impact(object_name, direction="downstream", depth=3, relationship_types?)` | `graph_dependencies(object_name, direction="both" \| "forward" \| "reverse", limit=50)` |
| Who calls / what is called | `trace_call_chain(routine_name, object_name?, direction="callers" \| "callees", depth=3)` | `get_method_call_hierarchy(method_name, direction="both", depth=3)` |
| Attributes that reference an object | `find_usages_of_object(object_name)` | `graph_dependencies(..., direction="reverse")` |
| Objects that use a type | `find_objects_using_object(object_name)` | same |
| Documents moving a register | `find_register_movement_docs(register_name)` | `codesearch(query="Движения.<Регистр>")` |
| Release-level transitive impact | `affected_subgraph(roots, depth?, direction?, edge_types?)` with refs from `resolve_graph_entity` | — |

Parameter names are `object_name`, `routine_name`, `register_name`, `method_name` — never `full_name`, `name` or `query` on these tools.

## Calls

```json
{"tool": "trace_impact", "args": {"object_name": "РегистрНакопления.ТоварыНаСкладах", "direction": "downstream", "depth": 3}}
{"tool": "trace_call_chain", "args": {"routine_name": "ПровестиДокумент", "object_name": "ОбщийМодуль.ПроведениеСервер", "direction": "callers", "depth": 3}}
{"tool": "find_usages_of_object", "args": {"object_name": "Справочник.Контрагенты"}}
{"tool": "find_register_movement_docs", "args": {"register_name": "РегистрНакопления.ТоварыНаСкладах"}}
{"tool": "get_method_call_hierarchy", "args": {"method_name": "ПровестиДокумент", "direction": "callers", "depth": 3}}
```

## Configurations with extensions

One base graph project with ordered layers: `list_graph_projects` once per session, keep the base `project_id`, never register extensions as projects. Which version runs — `resolve_effective_entity(object_name, entity_kind="MetadataObject", entity_name?)`; what one extension changed — `compare_base_and_extension(object_name, extension_name)`. A plain search hit proves a version exists, not that the platform executes it.

## Rules

- Read `truncated`, `exhaustive`, `degraded` and `warnings`; an exhaustive claim needs a complete page set and a ready generation.
- Callers of a public `Экспорт` routine are a promotion trigger (`content/rules/verification-policy.md`); the caller list belongs in the delivery evidence.
- Typed answers map to actions by code — `content/rules/mcp-policy.md → C. Server answers → actions`.

Evidence-first tools (`find_graph_path`, `explain_graph_evidence`, `compare_graph_scope`), domain relations (rights, subscriptions, DCS lineage): `content/skills/mcp-1c-tools/docs/1c-graph-metadata-mcp.md`.
