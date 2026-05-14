# 1c-graph-metadata-mcp — tool catalog

Graph metadata server (Neo4j + Cypher). Tools are deterministic (no LLM) unless explicitly noted.

> Load this file only if the `1c-graph-metadata-mcp` server is actually available in the current session (its tools are exposed in the tool schema).

> **Argument naming for search tools — do not invent.** `search_metadata`, `search_metadata_by_description`, `execute_metadata_cypher`, `search_code`, `business_search` all take the search input as **`query`**. Forbidden hallucinations: `query_template`, `template`, `json_query`, `q`, `text`, `search_query`, `prompt`. For `search_metadata` the JSON template (`{"operation": "list_attributes", ...}`) is the **value** of `query`, not a separate parameter name — pass it as a JSON string. `answer_metadata_question` takes **`question`** (not `query`). `resolve_qualified_name` takes `qualified_name`, `find_by_guid` takes `guid`.

## Metadata search

| Tool | Parameters | Purpose | When to use |
|---|---|---|---|
| **search_metadata** | `query`, `project_name=None` | Template JSON queries (instant, deterministic) or natural language → Cypher (requires LLM). JSON format: `{"operation": "<name>", ...params}`. Operations: `list_attributes`, `list_tabular_parts`, `object_structure`, `list_objects_by_category`, `list_objects_by_name`, `list_forms`, `list_enum_values`, `list_resources`, `list_dimensions`, `get_attribute_type`, `list_attributes_with_type` | Structural queries. Prefer JSON templates for deterministic results. NL mode — when templates do not cover the query |
| **get_metadata_prompt** | *(none)* | Returns the Neo4j database schema, Cypher examples, and the list of available template operations | Before writing raw Cypher via `execute_metadata_cypher`. Also shows all available JSON template operations for `search_metadata` |
| **execute_metadata_cypher** | `query` | Execute raw Cypher on Neo4j | Complex graph queries not covered by templates. Always run `get_metadata_prompt` first to understand the schema |
| **search_metadata_by_description** | `query`, `top_k=10`, `filter_type=None`, `project_name=None`, `use_fuzzy=false`, `alpha=0.5` | Lucene fulltext (+ optional vector hybrid) over name, Синоним, Комментарий, Описание, Справка. `use_fuzzy=true` enables fuzzy matching. `alpha` controls vector/fulltext balance (0.0 = fulltext only, 1.0 = vector only) | Find metadata objects by Russian synonyms, comments, descriptions, or help text. Better than `search_metadata` when you have a descriptive phrase rather than a technical name |
| **resolve_qualified_name** | `qualified_name` | Resolve dot-notation 1C qualified names to graph nodes. Patterns: `Справочник.Контрагенты`, `Документ.РеализацияТоваровУслуг.ТабличнаяЧасть.Товары`, `Справочник.Контрагенты.Реквизит.ИНН` | Validate qualified name paths, navigate from category to object to attribute in the graph |
| **find_by_guid** | `guid` | Find any metadata node by its GUID. Returns node type, name, and all properties | Look up a specific metadata node when you have a GUID (e.g. from XML or a configuration dump) |

## Object analysis

> **Argument naming — do not invent.** The required parameter for object-scoped tools on this server is **`object_name`**. Forbidden hallucinations: `object_full_name`, `full_name`, `qualified_name`, `name`, `fullName`, `objectFullName`. The same `object_name` applies to `get_object_dossier`, `find_objects_using_object`, `find_usages_of_object`, `trace_impact`, `compare_base_and_extension`, and (optionally, for disambiguation) `trace_call_chain`. `find_register_movement_docs` uses **`register_name`**, `trace_call_chain` uses **`routine_name`**, `find_by_guid` uses **`guid`**, `resolve_qualified_name` uses **`qualified_name`**. The value of `object_name` is a 1C dotted qualified name — `Справочник.Контрагенты`, `Документ.РеализацияТоваровУслуг`, `РегистрНакопления.ТоварыНаСкладах`, `ОбщийМодуль.РаботаСКонтрагентамиКлиентСервер`, etc. — same shape that `resolve_qualified_name` accepts.

| Tool | Parameters | Purpose | When to use |
|---|---|---|---|
| **get_object_dossier** | `object_name` (required, qualified name like `Документ.РеализацияТоваровУслуг`), `sections=None` | Comprehensive structural passport in one call — no LLM. Sections: `structure` (attributes, tabular parts, dimensions, resources, commands, layouts), `forms`, `subscriptions`, `roles`, `dependencies` (USED_IN upstream/downstream, register movements), `code` (module procedures/functions with signatures), `business_info`. Default: all sections | **First step** when you need to understand any metadata object. Replaces multiple separate queries. Use the `sections` filter to reduce output |
| **find_objects_using_object** | `object_name`, `project_name=None` | All metadata objects where the given object is used as a type reference in attributes, dimensions, or resources (via USED_IN) | Answer "Where is catalog X used?" — at the object level |
| **find_usages_of_object** | `object_name`, `project_name=None` | Specific attributes, dimensions, and resources that reference the given object, with the owner object and full type information | Answer "In which attributes is X referenced?" — attribute-level detail (in contrast to `find_objects_using_object`) |
| **find_register_movement_docs** | `register_name`, `project_name=None` | All documents that make movements into the given register | Answer "Which documents post to register X?" — essential for understanding document-register relationships |

## Dependency & impact analysis

| Tool | Parameters | Purpose | When to use |
|---|---|---|---|
| **trace_impact** | `object_name`, `depth=3`, `direction="downstream"`, `relationship_types=None`, `project_name=None` | Recursive impact analysis across USED_IN, DO_MOVEMENTS_IN, CALLS. `direction`: `downstream` (who depends on me), `upstream` (what I depend on), `both`. `depth`: 1–5 for metadata, 1–10 for CALLS. `relationship_types`: optional filter (`USED_IN`, `DO_MOVEMENTS_IN`, `CALLS`) | **Before refactoring**: "If I change X, what else is affected?" `downstream` for impact, `upstream` for the dependency tree. Preferred over `graph_dependencies` for deep multi-level analysis |
| **trace_call_chain** | `routine_name`, `object_name=None`, `direction="callees"`, `depth=3` | Recursive BSL call graph traversal. `direction`: `callees` (what does this routine call), `callers` (who calls this routine). `depth`: 1–10. `object_name` disambiguates when multiple routines share a name | Trace call chains across metadata objects. `callers` — before refactoring a routine. `callees` — to understand what a routine depends on |

## Code search

| Tool | Parameters | Purpose | When to use |
|---|---|---|---|
| **search_code** | `query`, `search_type="hybrid"`, `top_k=3`, `filter_type=None`, `project_name=None`, `detail_level="L1"` | BSL code search across all metadata objects. `search_type`: `fulltext` (exact / Lucene), `semantic` (by meaning), `hybrid` (both, default — returns up to 2×top_k). `detail_level`: **L0** — full procedure code without truncation; **L1** — signature + description + callees (default); **L2** — card (name, owner, module, export, directive); **L3** — name and score only (minimal tokens). `filter_type` — category filter (`Справочники`, `Документы`, `ОбщиеМодули`) | **Primary tool for BSL code search.** `fulltext` for exact function names and Lucene syntax (`Процедура AND Скидк*`). `semantic` to find code by purpose. `L3` + high `top_k` for overview lists, `L0` for full code |

## Semantic search & Q&A

| Tool | Parameters | Purpose | When to use |
|---|---|---|---|
| **business_search** | `query`, `top_k=10`, `filter_type=None`, `include_structure=true`, `project_name=None` | Vector-based semantic search on business documentation. When `include_structure=true` (default), enriches results with graph context: attributes, tabular parts, forms, USED_IN. Falls back to fulltext if the vector index is unavailable | Find a metadata object by business description when the technical name is unknown (e.g. "объект для хранения информации о клиентах"). Use `filter_type` to narrow the category |
| **answer_metadata_question** | `question`, `max_tokens=4000`, `include_code=true`, `project_name=None` | Natural language Q&A about metadata (requires LLM). Returns structured answer with sources, confidence, and processing metadata | Complex questions about how metadata objects work, their purpose, and relationships. Questions usually in Russian. **Non-deterministic — treat as a hint, not authority** |

## Extension analysis

| Tool | Parameters | Purpose | When to use |
|---|---|---|---|
| **compare_base_and_extension** | `object_name`, `extension_name` | Structural diff: attributes, forms, and routines added / overridden / unchanged by the extension vs base. Requires both base and extension to be loaded into the same Neo4j database | Compare a base configuration object with its extension counterpart after borrowing. Verify what the extension changes |
