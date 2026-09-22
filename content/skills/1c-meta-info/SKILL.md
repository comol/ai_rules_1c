---
name: 1c-meta-info
description: "Read facts about 1C metadata objects — passport, attributes with types, tabular-part columns, forms, predefined items, objects by category or by Russian description — from the graph and code-metadata MCP servers. Use before writing code or metadata that depends on an object's structure, and to identify objects by synonym."
argument-hint: "<Kind.Name | description> [sections]"
allowed-tools: mcp__1c-graph-metadata-mcp__get_object_dossier, mcp__1c-graph-metadata-mcp__search_metadata, mcp__1c-graph-metadata-mcp__search_metadata_by_description, mcp__1c-graph-metadata-mcp__business_search, mcp__1c-graph-metadata-mcp__resolve_qualified_name, mcp__1c-graph-metadata-mcp__find_by_guid, mcp__1c-graph-metadata-mcp__run_graph_cypher_template, mcp__1c-code-metadata-mcp__metadatasearch, mcp__1c-code-metadata-mcp__get_metadata_details
---

# 1c-meta-info — facts about a metadata object

Facts only; a verdict about an object needs the validators of `1c-validate`. Search discipline and freshness — `content/rules/mcp-first-search.md`.

## Address

`object_name` on both servers is the dotted qualified name with the Russian kind prefix: `Справочник.Контрагенты`, `Документ.РеализацияТоваровУслуг`, `РегистрНакопления.ТоварыНаСкладах`, `ОбщийМодуль.РаботаСКонтрагентами`. There is no `full_name`, `object_full_name`, `qualified_name` or `name` parameter on these tools. The same address drives `Invoke-1CEdit.ps1 -Object` in `1c-metadata-manage`.

## Tools and exact arguments

| Need | Call | Arguments |
|---|---|---|
| Passport of a known object | `get_object_dossier` (graph) | `object_name`, optional `sections` |
| Header attributes, properties, predefined | `get_metadata_details` (code) | `object_name`, `sections="attributes,tabular_parts,properties,predefined"`, `detail_level="outline" \| "full"`, `max_items`, `cursor`, `include_provenance=false` |
| Tabular-part **columns** | `get_metadata_details` (code) | `sections="tabular_parts"` or `tabular_part="<name>"` — the graph indexes names only and warns `tabular_part_columns_not_indexed`; that warning routes here in one step |
| Objects by category / structure | `search_metadata` (graph) | `query` = JSON operation, e.g. `{"operation":"list_objects_by_category","category_name":"Документы"}` |
| Object by synonym / description | `search_metadata_by_description` (graph) | `query`, `top_k=10`, `filter_type` = Russian plural category (`Документы`, `Справочники`), `use_fuzzy`, `alpha` |
| Business-meaning search | `business_search` (graph) | `query`, `top_k`, `filter_type`, `include_structure` — only when `list_graph_capabilities` shows the lane |
| Identification fallback | `metadatasearch` (code) | `query`, `names_only=true`, `limit=5`, `object_type` |
| Identity | `resolve_qualified_name(qualified_name)`, `find_by_guid(guid)` | — |
| Cypher template | `run_graph_cypher_template` | `template_id`, `arguments.object_name` = bare name (`Контрагенты`), optional `arguments.category_name` |

## Calls

```json
{"tool": "get_object_dossier", "args": {"object_name": "Документ.НачислениеЗарплаты", "sections": "attributes,tabular_parts,forms"}}
{"tool": "get_metadata_details", "args": {"object_name": "Документ.НачислениеЗарплаты", "sections": "tabular_parts", "detail_level": "outline", "max_items": 200}}
{"tool": "search_metadata_by_description", "args": {"query": "начисление премии сотрудникам", "filter_type": "Документы", "top_k": 5}}
{"tool": "search_metadata", "args": {"query": "{\"operation\": \"list_attributes_with_type\", \"type_name\": \"СправочникСсылка.Контрагенты\"}"}}
{"tool": "metadatasearch", "args": {"query": "Контрагенты", "names_only": true, "limit": 5}}
```

## Rules

- Retrieve the smallest projection that answers: names for identification, one section for a field list; never expand a hit into a full dossier without need.
- Page with `cursor` until complete before claiming an exhaustive list; an empty page section does not prove absence.
- Configurations with extensions: when the graph covers the relevant layers, use one discovered base `project_id`; effective source version via `resolve_effective_entity`, layer diff via `compare_base_and_extension(object_name, extension_name)` — `1c-impact`. Uncovered contours use their mapped index or own files; scope and evidence boundaries — `content/rules/multi-contour-search.md`.
- Typed answers map to actions by code — `content/rules/mcp-policy.md → C. Server answers → actions`.

Paging contract, JSON operation catalogue, template list: `content/skills/mcp-1c-tools/docs/1c-graph-metadata-mcp.md`, `content/skills/mcp-1c-tools/docs/1c-code-metadata-mcp.md → Reading large metadata objects`.
