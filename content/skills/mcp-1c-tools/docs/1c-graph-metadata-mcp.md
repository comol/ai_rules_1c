# 1c-graph-metadata-mcp — tool catalog

Graph metadata server: scoped Neo4j graph, BSL call graph, forms, evidence, impact and project lifecycle. Structural/template tools are deterministic; `answer_metadata_question` and natural-language `search_metadata` require an LLM unless the deployment is in graph-only mode.

> Load this file only if `1c-graph-metadata-mcp` is actually exposed in the current session. The published surface varies with `MCP_TOOL_PROFILE` and feature gates; `list_graph_capabilities` / `get_graph_tool_schema` are authoritative.

## Contract and scope — read before calling

1. Published beta responses use the slim `contract_version: "2.0"` envelope; stable tags still expose 1.x. Always-present fields are `contract_version`, `context`, `total`, `returned`; optional empty/false/null fields are omitted. Payload is in `items`, `text`, `nodes`/`edges`, or `data` depending on the tool.
2. Every tool accepts contract paging controls `cursor` and `max_items`. Project-data tools also accept `project_id` and optional `generation`. Get a valid project through `list_graph_projects`; do not invent it.
3. `project_id` is the security/data scope. A legacy domain argument named `project_name` on some search functions is only an in-graph filter and must never be used as a substitute for scope.
4. If `truncated` is true, read `truncation_reason` / `limits` and continue with the opaque cursor using exactly the same project, generation and query. A cursor is bound to the tool, query, generation and plugin epoch.
5. Errors are typed (`project_not_registered`, `stale_generation`, `invalid_argument`, `invalid_cursor`, `timeout`, etc.). Do not retry with guessed argument names.
6. `warnings` on an answer describe **that answer** (a failed lane, a missing index such as `tabular_part_columns_not_indexed`); installation-wide notices live in `list_graph_capabilities`. `degraded: true` means a lane this answer needed was unavailable — record it, do not re-run the same call hoping for a different lane.
7. `execute_metadata_cypher` has been removed. Never ask for or attempt arbitrary client Cypher. Use `run_graph_cypher_template(template_id, arguments)` with an allow-listed read-only template, or a typed graph tool.
8. Resolve an ambiguous entity once with `resolve_graph_entity`, then pass its returned stable reference to path/evidence/domain tools. Do not reconstruct `node_id`, keys or edge refs by hand.

### Base configuration and extension layers

1. When the server's extension catalog has ingested the relevant sources, the base and discovered extensions are ordered **layers of the same `project_id`**. Extension names are not project IDs. Call `list_graph_projects`, choose the base project's returned `project_id`, and keep that scope on all project-data calls. A project search catalog does not establish ingestion: a base-only graph answers only within that coverage; uncovered contours follow `content/rules/multi-contour-search.md`.
2. Never call `register_graph_project` once per extension and never invent a `project_id` from `EXTENSION_NAME`. That creates isolated project scopes and cannot build the base↔extension `EXTENDS` / `OVERRIDES` relationships required for effective-runtime answers.
3. For the indexed effective implementation, call `resolve_effective_entity(object_name, entity_kind, entity_name)`. Use `entity_kind="MetadataObject"` with no `entity_name` for an object; for a routine/form/module, pass its kind and its own `entity_name`. Inspect `data.layers`, `effective`, `superseded`, `wrapping`, `extending`, warnings and `ambiguous_order` rather than selecting the last search hit yourself. A claim about a running infobase additionally needs evidence tying those sources, active extensions and order to that named target; source analysis alone remains a source conclusion.
4. For “what did one named extension change?”, call `compare_base_and_extension(object_name, extension_name)`. This is a layer comparison inside the selected base-project scope, not a cross-project comparison.
5. The catalog order is purpose-first (`Исправление` → `Адаптация` → `Дополнение`) and manifest/name order within one purpose. If the response says the order was assumed or ambiguous, report that uncertainty; do not turn it into a proven runtime order.
6. Before an exhaustive claim about extensions, require a ready/current generation and verify that the expected layers are present. A registered project or a fast `completed` refresh alone does not prove that extension sources were ingested.

### Tools not automatically project-scoped

Discovery/health/contract tools (`get_metadata_prompt`, `get_indexing_status`, `health_graph`, `get_graph_capabilities`, `list_graph_capabilities`, `get_graph_tool_schema`, `metadata_report`), project lifecycle tools, plugin reload, and ordinary-form file tools receive only universal paging controls from the wrapper. A `project_id` shown in their own schema is a normal domain argument.

## Recommended workflow

These are conditional steps, not a mandatory preamble for every lookup. Reuse the selected project, resolved identity and known tool schema within the session; discover only the missing contract information. Check schemas again after a contract change or validation error.

**Schema lookups are not free.** `get_graph_tool_schema` / the client's tool-schema lookup is for a tool that is absent from this file and from the operation skills (`1c-meta-info`, `1c-impact`, `1c-code-search`, `1c-form-inspect`), or after an `invalid_argument` / schema rejection — never before every call. One project list per session: `list_graph_projects` once, then keep `project_id`. The analysed sessions spent a third of all calls on schema and project lookups that returned nothing new.

**Time budget.** The server answers with a typed `error.code = "timeout"` after `GRAPH_TOOL_TIMEOUT_SECONDS` (default 25 s, below the client's 30 s). Do not resend the same call: narrow the query, lower `max_items`, or switch to a structural tool. A client-side `fetch failed` on the first call of a session is a transport reconnect, not a server answer — repeat that one call once.

1. `health_graph(project_id=...)` when availability is uncertain; it separates process liveness, Neo4j, providers and exact/fulltext/vector/hybrid/traversal lanes.
2. `list_graph_projects` → choose `project_id`; `get_graph_project_status` if ingestion/generation readiness matters.
3. `resolve_graph_entity(reference=...)` for a named/path/code reference.
4. Use the narrow typed tool (`get_object_dossier`, domain relation, path, impact, comparison) rather than broad search.
5. Use `explain_graph_evidence` / `explain_path` when a decision depends on provenance. A structural answer without evidence is not automatically a release proof.
6. Page until complete when the answer claims exhaustiveness. `truncated`, `exhaustive=false`, `degraded=true`, or unknown readiness forbids a “nothing else exists” conclusion.

### Tabular-part attributes

The graph model has `MetadataObject → HAS_TABULAR_PART → TabularPart → HAS_ATTRIBUTE → Attribute`, but a generation built from a text report or by an older loader holds only the tabular-part **names**. The tools now say so instead of answering with empty lists: `object_tabular_parts`, the `list_tabular_parts` operation and `get_object_dossier` carry the warning `tabular_part_columns_not_indexed` when the part has no indexed columns. Treat that warning as a closed lane: do not try other graph tools for the columns, take them from `1c-code-metadata-mcp` `get_metadata_details(object_name=..., sections="tabular_parts")` (or `tabular_part="<name>"` for one part) and say so in the response. Names of the parts stay valid graph evidence; a refresh of the project (`refresh_graph_project`) rebuilds the columns when the source export contains them.

## Search and object navigation

| Tool | Primary domain arguments | Use |
|---|---|---|
| `search_metadata` | `query`, optional legacy `project_name` | JSON operation in the **value** of `query` (preferred, deterministic — catalogue below) or natural language (LLM / hybrid lanes, slower, needs an embeddings provider) |
| `search_metadata_by_description` | `query`, `top_k=10`, `filter_type`, `use_fuzzy=false`, `alpha=0.5` | Name/synonym/comment/help fulltext + vector search |
| `business_search` | `query`, `top_k=10`, `filter_type`, `include_structure=true` | Business-semantic search; published only when the business-info lane is enabled (`CALCULATE_BUSINESS_INFO=true`); absent from `tools/list` otherwise — check `list_graph_capabilities`, do not call it by habit |
| `search_code` | `query`, `search_type="hybrid"`, `top_k=3`, `filter_type`, `detail_level="L1"` | BSL routine search. Use fulltext for identifiers, semantic for intent; request full code only when needed |
| `answer_metadata_question` | `question`, `max_tokens=4000`, `include_code=true` | LLM/RAG synthesis; non-deterministic hint, verify sources |
| `get_object_dossier` | `object_name`, optional `sections` | First call for a known qualified object; bounded multi-section passport |
| `resolve_qualified_name` | `qualified_name` | Resolve a 1C dotted qualified name |
| `find_by_guid` | `guid` | Find metadata by GUID |
| `resolve_graph_entity` | `reference`, optional `kinds`, `max_candidates` | Convert name/path/code reference to stable graph identity |
| `explain_graph_entity` | `reference`, optional relation filter/direction/group limit | Compact entity card and grouped relations |
| `fetch_graph_nodes` | `node_ids` | Expand compact node IDs returned by graph/path tools |

**Argument naming:** search inputs are `query`; Q&A uses `question`; dossier/object-relationship tools use `object_name`; call traversal uses `routine_name`; movement lookup uses `register_name`. Do not invent `q`, `text`, `prompt`, `full_name`, `object_full_name`, or `query_template`.

**Value formats that fail silently when guessed:**

- `filter_type` (`search_metadata_by_description`, `business_search`) and `category` in JSON operations is the **category name as the graph stores it — Russian plural**: `Документы`, `Справочники`, `РегистрыСведений`, `РегистрыНакопления`, `ПланыВидовРасчета`, `Перечисления`, `ОбщиеМодули`, `Обработки`, `Отчеты`, `Константы`. Singular Russian (`Документ`) and English MCP names (`Document`, `Catalog`, `InformationRegister`) are normalised by current builds and rejected with `invalid_argument` on older ones; never pass them expecting a different scope.
- `entity_kind` (`explain_graph_entity`, `resolve_effective_entity`, `find_test_artifacts`) is one of `MetadataObject`, `Symbol`, `Form`, `SourceUnit`, `Chunk` — a graph node kind, **not** a 1C object kind (`Document` is rejected).
- `reference` for `resolve_graph_entity` / `explain_graph_entity` accepts a dotted qualified name including a tabular part: `Документ.НачислениеЗарплаты.ТабличнаяЧасть.Начисления`.
- `object_name` in `run_graph_cypher_template` arguments is the bare object name **without** the category prefix (`НачислениеЗарплаты`, not `Документ.НачислениеЗарплаты`); pass `category_name="Документы"` when the same name exists in several categories (`Начисления` is both a tabular part and a `ПланВидовРасчета`).
- `object_name` in the JSON operations (`list_attributes`, `list_tabular_parts`, `object_structure`, …) is matched **exactly** when such an object exists; a typed prefix (`Документ.Премия`) becomes a category filter. Only when no exact match exists does the old partial `CONTAINS` match apply — so a fragment still yields candidates, but `Премия` no longer brings the catalog `ПремияПрисоединенныеФайлы` along. `list_objects_by_name` stays a partial search.

### `search_metadata` JSON operations

`{"operation": "<name>", ...params}` as the value of `query`. The full catalogue with parameter aliases is returned by `get_metadata_prompt` (large; read it once per session only when an operation below does not fit). Structure and search:

| Operation | Params | Answers |
|---|---|---|
| `object_structure` | `object_name` | Header attributes + tabular-part names of one object (paged; the text is `kind: Реквизит / ТабличнаяЧасть` lines) |
| `list_attributes` | `object_name` | Header attributes only |
| `list_tabular_parts` | `object_name` | Tabular parts; columns only when indexed (see *Tabular-part attributes*) |
| `get_attribute_type` | `object_name`, `attribute_name` | Type of one attribute |
| `list_attributes_with_type` | `type_name` (`Документ.Премия` or `ДокументСсылка.Премия`) | Attributes of that **type** across the configuration — not the attributes of an object; `object`/`object_name` are not accepted |
| `list_objects_by_category` | `category_name` | Objects of a category |
| `list_objects_by_name` | `object_name` (CONTAINS), optional `category` | Name search |
| `list_forms` / `list_enum_values` / `list_resources` / `list_dimensions` / `list_commands` / `list_layouts` / `list_predefined_of_object` | `object_name` | Per-object collections |
| `find_objects_using_object` / `find_usages_of_object` / `find_documents_making_movements_into_register` | `object_name` | Usages and movements |
| `resolve_qn` / `find_by_guid` | `qualified_name` / `guid` | Identity |
| `list_modules_of_owner`, `list_module_routines` (`object_name`, `module_type?`), `list_common_module_routines` (`module_name`), `find_routines_by_name` (`routine_name`), `get_routine_body`, `list_callers_of_routine`, `list_callees_of_routine`, `call_graph_subtree` (`routine_name`, `depth?`, `direction?`) | — | BSL code graph |
| `list_form_controls` / `list_form_events` / `list_form_commands` / `list_form_bindings` / `list_form_attributes` | `object_name`, `form_name` | Forms |
| `list_roles_with_access_to_target` (`object_name`), `list_access_targets_of_role` (`role_name`), `get_access_of_role_to_target` | — | Rights |
| `list_extension_objects` (`extension_name`), `find_base_object`, `list_overrides_of_object`, `compare_base_and_extension` | `object_name`, `extension_name` | Extensions |

`list_attributes_with_type` is an operation of `search_metadata`, not a `template_id` of `run_graph_cypher_template`; the two catalogues are separate.

### `run_graph_cypher_template` templates

`run_graph_cypher_template(template_id=..., arguments={...})` — allow-listed read-only Cypher; the current list is also in `get_metadata_prompt` and in the `invalid_argument` error of a wrong id:

| `template_id` | `arguments` | Returns |
|---|---|---|
| `object_attributes` | `object_name` (bare name), optional `category_name` | Header attributes: `name`, `type`, `synonym`, `comment` |
| `object_attribute_properties` | `object_name`, optional `category_name` | Every stored property of each header attribute (~1 KB per attribute — only when a property other than type/synonym matters) |
| `object_tabular_parts` | `object_name`, optional `category_name` | Tabular parts with their columns as `{name, type}` (or the `tabular_part_columns_not_indexed` warning) |
| `object_forms` / `object_modules` | `object_name` | Forms / modules of the object |
| `object_neighbours` | `object_name` | Adjacent nodes grouped by relationship |
| `objects_by_name` | `name_pattern` | Objects whose name contains the pattern |
| `objects_in_category` | `category_name` | Objects of one category |
| `object_counts_by_category` | — | Counts per category |

Values travel in `arguments`; `project_id` stays a top-level contract parameter and is refused inside `arguments`.

## Relationships and classic impact

| Tool | Primary domain arguments | Use |
|---|---|---|
| `find_objects_using_object` | `object_name` | Objects that use a type reference |
| `find_usages_of_object` | `object_name` | Exact attributes/dimensions/resources that reference it |
| `find_register_movement_docs` | `register_name` | Documents making movements into a register |
| `trace_impact` | `object_name`, `depth=3`, `direction="downstream"`, optional `relationship_types` | Legacy recursive impact by graph relations |
| `trace_call_chain` | `routine_name`, optional `object_name`, `direction="callees"`, `depth=3` | BSL callers/callees |
| `find_test_artifacts` | `references`, optional `test_kinds` | Locate indexed tests covering named graph entities; does not execute tests |

## Evidence-first path, release impact and comparison

These tools take structured refs returned by `resolve_graph_entity`, not guessed strings.

| Tool | Primary domain arguments | Use |
|---|---|---|
| `find_graph_path` | `from_ref`, `to_ref`, `direction="undirected"`, optional `edge_types`, `max_depth`, `max_paths` | K shortest grounded paths; inspect `exhaustive` and per-edge evidence |
| `explain_path` | `steps` from a path result | Explain each path step without re-encoding it |
| `affected_subgraph` | `roots`, optional `node_kinds`, `depth`, `direction`, `edge_types`, `stop_kinds` | Release-oriented transitive impact with related tests and bounded frontier |
| `explain_graph_evidence` | exactly one of `node_ref` or `edge_ref` | Provenance for one graph fact |
| `compare_graph_scope` | structured `base`, `target`, optional `node_kinds` | Compare projects/generations/layers; do not interpret an incomparable/truncated kind as deleted |
| `compare_base_and_extension` | `object_name`, `extension_name` | Named layer vs. base object diff inside the selected project |
| `resolve_effective_entity` | `object_name`, `entity_kind="MetadataObject"`, optional/required-by-kind `entity_name` | Effective, superseded, wrapping and extending variants across all ordered layers |

## 1C domain relations

| Tool | Primary domain arguments | Use |
|---|---|---|
| `get_access_rights` | `object_ref`, optional `right`, `role`, `field` | Role rights on object/field |
| `get_event_subscriptions` | `source_ref`, optional `event`, `handler` | Source → subscription → handler chain |
| `find_predefined_values` | `object_ref`, optional `parent_ref`, `name` | Predefined hierarchy |
| `get_register_writers` | `ref`, `direction="both"` | Register writers in either direction |
| `get_data_links` | `ref`, `direction="both"`, optional `link_kind` | Data-reference paths |
| `get_report_dcs_lineage` | `report_ref` | Report → DCS → datasets/queries/fields lineage |

## Forms

| Tool | Primary domain arguments | Use |
|---|---|---|
| `search_forms` | `query=""`, `form_kind="all"`, optional `owner_ref` | Search managed/ordinary forms |
| `get_form_structure` | `form_ref`, optional `include`, `max_depth` | Elements, attributes, commands, events |
| `find_form_links` | `form_ref`, `direction="both"`, optional `link_kinds` | Handlers, bindings, owner/module links |
| `unpack_ordinary_form` | `form_path`, `workspace_path`, `overwrite=false`, `include="summary"`, `max_chars=4000` | Admin-profile file operation: unpack `Form.bin` |
| `build_ordinary_form` | `workspace_path`, `output_path`, `overwrite=false`, `verify=true` | Admin-profile file operation: rebuild and logically verify `Form.bin` |

An ordinary `Form.bin` is a binary container, not XML. Do not edit it directly. A rebuilt binary may differ in bytes because of timestamps; `verification.status == "match"` is the round-trip criterion.

## Observability, contract and safe templates

| Tool | Purpose |
|---|---|
| `health_graph` | Process, Neo4j, provider and per-lane readiness; pass `project_id` for exact lane state |
| `get_indexing_status` | Background task status/restart-loop protection |
| `get_graph_schema` | Node and edge kinds in the selected project |
| `get_graph_stats` | Graph/evidence counters; optional label filter |
| `list_graph_indexes` | Neo4j index state/population |
| `get_graph_capabilities` | Local analysis vs delegated capabilities and graph-only degradation |
| `list_graph_capabilities` | Published tools, contract version/profile/feature gates/limits, disabled lanes (e.g. business search) and the installation notices (`GRAPH_SCOPE_ENFORCED`, `REFERENCE_EVIDENCE_ENABLED`, active generation) — these are reported here once, not on every answer |
| `get_graph_tool_schema` | Exact JSON Schema, annotations and example for one tool — after a schema rejection, or for a tool this file does not describe; not a preamble |
| `get_metadata_prompt` | Graph schema, the JSON operation catalogue and the Cypher template list (~40 KB); read once per session at most, only when the tables above do not answer; does **not** authorize raw Cypher |
| `run_graph_cypher_template` | Execute one allow-listed read-only `template_id`; values travel separately in `arguments`, and project-scope names are forbidden there |
| `list_plugins` | Loaded plugins, hooks/tables/presets, failures and plugin epoch |
| `metadata_report` | Tombstone explaining replacements for the removed monolithic report |

In graph-only mode, structural graph/template/fulltext functions continue while LLM/vector-dependent lanes report explicit degradation. Do not call missing providers a total outage; inspect `health_graph` and capabilities.

A disabled business-search lane is absent from `tools/list` on current builds and answers with a typed `lane_disabled` error on older ones; either way it is closed for the configuration — change lanes instead of rephrasing. Tool names, JSON operations and template IDs are three separate catalogues: `list_attributes_with_type` is a `search_metadata` operation, not a `template_id`; `compact_metadata` belongs to the Code server.

## Project lifecycle and profiles

| Tool | Primary arguments | Use |
|---|---|---|
| `list_graph_projects` | none | Registered projects in this namespace |
| `get_graph_project_status` | `project_id`, optional `operation_id` | Active/staging generations, readiness and operation progress |
| `register_graph_project` | `project_id`, `source_descriptor`, `operation_id` | Register a source; idempotent operation ID |
| `refresh_graph_project` | `project_id`, `operation_id` | Build staging generation, validate, then promote |
| `delete_graph_project` | `project_id`, `operation_id` | Destructive scoped deletion |
| `reload_plugins` | `operation_id` | Atomic plugin reload; derived-state hooks affect the next build and invalidate old cursors |

`MCP_TOOL_PROFILE=admin` publishes lifecycle, plugin reload and ordinary-form write tools. `read-only` omits them from `tools/list`; do not attempt to call hidden tools. Plugins are enabled by default in current source. Call-scoped hooks affect the next call; derived-state hooks change the build fingerprint and require a new generation.

Lifecycle tools own independent base-project sources. They do not turn separately registered projects into extension layers. If the deployment uses an extension catalog, ingest the catalog through the server deployment and query every layer under the returned base `project_id`.

For the beta manager-call fix with CALLS relation version 3 (14 September 2026), an ordinary restart over the existing data and export rebuilds the outdated CALLS lane once. With BSL loading enabled, unchanged modules, their embeddings and completed register-access relations are preserved. Do not request full refresh, delete the graph or enable source-unit manifests merely to apply this fix. `refresh_capability_unavailable` is a protection against losing derived data; do not bypass it.

For a legacy extension whose base is missing from `list_graph_projects`, check both instances' Neo4j connection, `MCP_NAMESPACE` and exact base project ID before concluding that the graph is empty. The fixed beta can discover existing scoped data for the base explicitly named by `EXTENSION_BASE_PROJECT_ID` (or `EXTENSION_BASE_PROJECT`) even without an old ingestion checkpoint. This does not grant access to another namespace, staging data or a corrupt checkpoint; a missing base is not a reason to re-embed the whole configuration.

## Source preparation

- A Designer XML export in `CODE_EXPORT_PATH` is sufficient: with `METADATA_SOURCE=auto`, the server prefers a supplied text report and otherwise synthesizes/caches one from XML in the background. `METADATA_SOURCE=xml` deliberately ignores a stale report; `report` requires one.
- Report synthesis does not support 1C:EDT. For EDT, use the source-format adapter plus a supplied text report for the metadata-report lane.
- The MCP_Distr deployment enables the extension catalog by default (`EXTENSION_CATALOG_ENABLED=true`). It always scans exactly one directory level: each direct child with Designer `Configuration.xml` or EDT `src/Configuration/Configuration.mdo` whose descriptor declares an extension purpose becomes a layer. Ordinary base-source directories and the base export itself are ignored by extension discovery. Disable the catalog explicitly only for the legacy declared-single-extension mode.
- `extensions_order.json` (or `extension_order.json`) may contain either a JSON list of extension names or `{ "order": [...] }`. It controls order only within one purpose; without it, name order is deterministic but reported as assumed.
- Published beta HTTP probes are `/healthz` for liveness and `/readyz` for Neo4j + published tool readiness. Newer source also carries `/health` and `/ready` aliases, but deployment checks must use the routes exposed by the running image.
