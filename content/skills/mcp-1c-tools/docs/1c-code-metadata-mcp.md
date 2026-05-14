# 1c-code-metadata-mcp — tool catalog

Metadata and BSL code search, module navigation, forms, XSD schemas, XML validation. Fallback for `1c-graph-metadata-mcp` when the latter is unavailable.

> Load this file only if the `1c-code-metadata-mcp` server is actually available in the current session.

> **Argument naming — do not invent.** Object-scoped tools on this server take **`object_name`** (the same shape as on `1c-graph-metadata-mcp` — a 1C dotted qualified name like `Справочник.Контрагенты`, `Документ.РеализацияТоваровУслуг`, `РегистрНакопления.ТоварыНаСкладах`, `ОбщийМодуль.РаботаСКонтрагентамиКлиентСервер`): `get_metadata_details`, `graph_dependencies`, `inspect_form_layout` (plus `form_name=""`). Forbidden hallucinations on these tools: `object_full_name`, `full_name`, `qualified_name`, `name`, `fullName`, `objectFullName`. Other tools use **different** parameter names — do not generalise `object_name` to all of them: `search_function` takes **`name`** (the routine name, not a qualified object), `get_module_structure` takes **`module_path`**, `get_method_call_hierarchy` takes **`method_name`**, `bsl_scope_members` takes **`context`**, `get_xsd_schema` and `verify_xml` take **`object_type`** (+ `xml_content` for `verify_xml`). Search inputs on `metadatasearch`, `codesearch`, `search_forms`, `helpsearch` go into **`query`** — not `q`, `text`, `prompt`, or `search_query`. If a Pydantic / schema validator rejects the call as `Missing required argument` or `Unexpected keyword argument`, re-read this file before retrying — do not paraphrase the parameter.

## `grep=true` retry rule

Use `grep=true` as a targeted substring retry **only after** indexed / semantic / exact search did not find enough and the query is likely to benefit from literal matching: exact identifier, query fragment, metadata path, event handler name, error text, or string literal.

Applies only to tools that expose a `grep` parameter: `codesearch`, `metadatasearch`, `search_function`, `helpsearch`, `search_forms`. If the query is conceptual or the first result is already sufficient, do not spend an extra call on `grep=true`.

## Metadata search

| Tool | Parameters | Purpose | When to use |
|---|---|---|---|
| **metadatasearch** | `query`, `limit=5`, `object_type=""`, `names_only=false` | Semantic / FTS search over metadata XML files. `object_type` filters by category (`Справочники`, `Документы`, etc.). `names_only=true` returns a compact list (`full_path`, `object_type`, `synonym`) instead of raw chunks. Prefer `names_only` to find objects, then use `get_metadata_details` for details | Metadata search, existence check, relationships. Use exact configuration names (`'Справочники.Контрагенты.Реквизиты'`) |
| **get_metadata_details** | `object_name` | Full structure: attributes with types, tabular parts, synonyms, properties | When the object name is known (`'Номенклатура'`, `'Документ.РеализацияТоваровУслуг'`) |

## Code search & navigation

| Tool | Parameters | Purpose | When to use |
|---|---|---|---|
| **codesearch** | `query`, `limit=5` | Hybrid search over BSL object modules and common modules | Find patterns, check usages, verify implementations. `query` — code, function name, or comment |
| **search_function** | `name`, `exact=true`, `limit=10` | Find BSL procedures/functions through a structural FTS index. `exact=true` — case-insensitive with auto-fallback to fuzzy | Find a specific procedure / function (`'ОбработкаПроведения'`, `'ПриСозданииНаСервере'`) |
| **get_module_structure** | `module_path` | Full module structure: procedures, functions, regions, statistics | Understand a module before editing, overview of contents |
| **get_method_call_hierarchy** | `method_name`, `direction="both"`, `depth=3` | Call graph: who calls (`callers`), what it calls (`callees`), or `both` | Call chains, impact analysis, hot paths |
| **graph_dependencies** | `object_name`, `direction="both"`, `limit=50` | Dependency graph: `forward` (what it uses), `reverse` (who uses it), `both` | Impact analysis before refactoring, relationships between objects |
| **bsl_scope_members** | `context`, `member_type="all"` | Available methods / properties / events for a BSL context. `member_type`: `all`, `methods`, `properties`, `events` | Discover an object's API (`'Справочник.Номенклатура'`, `'Глобальный'`) |

## Help search

| Tool | Parameters | Purpose | When to use |
|---|---|---|---|
| **helpsearch** | `query`, `limit=5` | Search over HTML help and user documentation | Help topics, purpose of metadata objects, functional descriptions |

## Forms

| Tool | Parameters | Purpose | When to use |
|---|---|---|---|
| **search_forms** | `query`, `limit=10` | Search across all configuration forms (elements, attributes, commands) | Find existing forms as examples before generating new ones (`'Номенклатура'`, `'ФормаЭлемента'`) |
| **inspect_form_layout** | `object_name`, `form_name=""` | Full element tree: hierarchy, attributes, commands, event handlers, bindings, visibility, accessibility | Study the layout before modification or as a reference for a new form |

## XSD schemas & validation

| Tool | Parameters | Purpose | When to use |
|---|---|---|---|
| **get_xsd_schema** | `object_type` | Generated XSD for a metadata type (`Справочник`, `Документ`, `РегистрСведений`, `РегистрНакопления`, `Роль`) or sub-type (`Форма`, `СКД`, `Макет`). English aliases accepted | Get XML structure rules before generating / modifying metadata XML |
| **verify_xml** | `xml_content`, `object_type` | Validate XML against XSD. Returns `status` (`valid` / `invalid` / `error` / `not_found`) and `errors` list | Validate generated / modified XML before committing |

## Administration

| Tool | Parameters | Purpose | When to use |
|---|---|---|---|
| **reindex** | `force=false` | Background reindexation. `force=true` wipes and rebuilds all indexes from scratch | After configuration changes, when search results seem stale |
| **stats** | *(none)* | Index statistics: document counts per collection, embedding provider, last indexation time, reindex schedule | Diagnostics, verify indexing status |
