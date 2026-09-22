# MCP_ConversionData20 — optional PRE-ALPHA tool catalog

Offline authoring and inspection of rules for «Конвертация данных» 2.0/2.1. This experimental server is **outside the seven main MCP servers** and is not a required dependency. Load this reference only for a relevant task when its tools are exposed. Runtime server name: `1C Конвертация данных 2.0 — разработка правил обмена`; client aliases may differ. The live `tools/list` schema is authoritative for the connected version.

Contract checked against `pre-alpha/MCP_ConversionData20/src/kd20_mcp/server.py` plus workspace/import/export implementations in the MCP development checkout, 2026-09-22: **32 tools**. Arguments use Python signature notation: no `=` means required; shown defaults are optional; `None`, `True`, `False` correspond to JSON `null`, `true`, `false`. `dict` means a JSON object; `list[...]` means an array. Paths refer to the server host.

## Scope and persistence

The server reads configuration dumps and stores configuration snapshots, editable JSON rulesets, XML exports and a search index. These tools do not perform an exchange in a live infobase. Loading/applying the output to an infobase is a separate authorized operation under the existing infobase and integration procedures. Handlers/algorithms are BSL: generated or edited code still requires the applicable [verification gates](../../../rules/verification-gates.md), and XML needs its applicable checks. `validate_ruleset` is not a substitute for BSL validators, runtime exchange tests or decisions about matching and deleting business data.

`KD20_DATA` selects saved configuration/ruleset storage; `KD20_OUTPUT` selects export output; `KD20_DB` selects the search database. Explicit input/output paths are checked against `KD20_ALLOWED_ROOTS` (semicolon-separated); the source defaults to the server project and `C:/Work`. Do not change these roots to evade a refusal. Creating/drafting/importing under an existing name can replace that ruleset; importing a configuration under the same alias replaces its snapshot. Sanitized-name collisions with a different stored owner are rejected. Inspect existing names before authorized writes.

## Configuration snapshots and matching

| Tool | Arguments | Behavior / result |
|---|---|---|
| **load_configuration** | `path: str, alias: str` | **Writes snapshot:** parse a Configurator dump (`Configuration.xml`) or EDT project (`Configuration.mdo`) and save under `alias`. Returns name/version, source format and object counts; does not load an infobase. |
| **list_configurations** | none | List stored aliases and snapshot summaries. |
| **list_metadata** | `alias: str, kind: str='', name_filter: str='', limit: int=100` | List objects; `kind` is a Russian kind or English class, `name_filter` matches name/synonym substrings. Returns total and bounded items; `limit` has a minimum of 1. |
| **describe_object** | `alias: str, name: str` | Full snapshot description by metadata full name or reference type: attributes/types, tabular sections, enum values, flags and export selection object. Missing object raises an error. |
| **suggest_object_mappings** | `source_alias: str, target_alias: str, classes: list[str] \| None=None, threshold: float=0.55, limit_per_object: int=3, only: list[str] \| None=None, limit: int=200` | Rank object pairs with scores/reasons. `classes` uses English class names; `only` uses full source object names. Results are candidates, not a decision to transfer data. |
| **suggest_property_mappings** | `source_alias: str, target_alias: str, source_object: str, target_object: str, threshold: float=0.55` | Suggest attribute/tabular-section pairs and return unmatched properties for both objects. Source/target object arguments accept full names or reference types. |

## Rulesets and object/property rules

| Tool | Arguments | Behavior / result |
|---|---|---|
| **create_ruleset** | `name: str, source_alias: str, target_alias: str, title: str='', comment: str=''` | **Writes:** create an empty ruleset bound to two loaded snapshots; returns saved path and statistics. |
| **draft_ruleset** | `name: str, source_alias: str, target_alias: str, classes: list[str] \| None=None, threshold: float=0.7, pairs: list[dict] \| None=None, sync_by_id: bool=False, title: str='', comment: str=''` | **Writes:** draft automatic same-class matches or explicit `pairs=[{"source": "...", "target": "..."}]`. Returns statistics, validation summary and object rules; matching/search semantics still need review. |
| **list_rulesets** | none | List saved rulesets and statistics. |
| **describe_ruleset** | `name: str, rule_code: str=''` | Summary by `name`; with `rule_code`, return one full object-conversion rule (ПКО). Missing code raises an error. |
| **set_object_rule** | `ruleset_name: str, code: str, source: str='', target: str='', name: str='', flags: dict \| None=None, handlers: dict \| None=None, search_in_tabular_sections: str='', replace: bool=False` | **Writes:** create/update ПКО; `source`/`target` are reference types. `flags` and `handlers` are objects keyed by supported names. Default update merges nonempty fields and preserves nested rules; `replace=True` replaces the whole ПКО, including properties/value mappings. |
| **delete_object_rule** | `ruleset_name: str, code: str` | **Writes:** delete the matching ПКО; returns whether removed. Does not cascade into referencing rules; validate afterward. |
| **set_property_rule** | `ruleset_name: str, rule_code: str, code: str, source_name: str='', target_name: str='', source_type: str='', target_type: str='', source_kind: str='Реквизит', target_kind: str='Реквизит', kind: str='property', search: bool=False, conversion_rule: str='', group_code: str='', handlers: dict \| None=None, order: int=0, do_not_replace: bool=False, get_from_incoming_data: bool=False, cast_to_length: int=0, parameter_name: str='', search_by_date_equality: bool=False, disable: bool=False, name: str=''` | **Writes:** upsert ПКС (`kind="property"`) or ПКГС (`kind="group"`); `group_code` selects an existing parent group. `search=True` marks a search property. Rebuilds the item from supplied/default arguments; existing group children are preserved for group updates. |
| **delete_property_rule** | `ruleset_name: str, rule_code: str, code: str, group_code: str=''` | **Writes:** remove ПКС/ПКГС from the selected object rule or specified parent group; returns removal status. |
| **set_value_map** | `ruleset_name: str, rule_code: str, values: list[dict]` | **Writes:** replace the entire ПКО value map with `values`, an array of `{"source": "...", "target": "..."}` objects; returns its count. |

## Export, clearing and handler rules

| Tool | Arguments | Behavior / result |
|---|---|---|
| **set_export_rule** | `ruleset_name: str, code: str, selection_object: str='', conversion_rule: str='', name: str='', order: int=0, data_selection_method: str='СтандартнаяВыборка', single_query: bool=True, disable: bool=False, handlers: dict \| None=None` | **Writes:** upsert ПВД using a selection type and a ПКО code. Rebuilds the rule from supplied/default values; returns action and code. |
| **delete_export_rule** | `ruleset_name: str, code: str` | **Writes:** delete a ПВД; returns removal status. |
| **set_clear_rule** | `ruleset_name: str, code: str, selection_object: str='', name: str='', order: int=0, data_selection_method: str='СтандартнаяВыборка', delete_for_period: bool=False, directly: bool=False, disable: bool=False, handlers: dict \| None=None` | **Writes rule definition:** upsert ПОД, including period/direct-deletion flags. Does not delete infobase data now; the resulting rule can do so when later executed by an exchange. |
| **set_conversion_handler** | `ruleset_name: str, node: str, text: str` | **Writes:** set a supported global conversion-handler node; empty/whitespace `text` removes it. Invalid node raises an error; retrieve the interface first. |
| **set_parameter** | `ruleset_name: str, name: str, title: str='', value_type: str='', set_in_dialog: bool=False, used_on_import: bool=False, pass_on_export: bool=False, conversion_rule: str='', after_load_algorithm: str=''` | **Writes:** upsert a parameter by case-insensitive name, rebuilding fields from arguments/defaults. Returns action and name. |
| **set_algorithm** | `ruleset_name: str, name: str, text: str, used_on_import: bool=False` | **Writes:** upsert algorithm text by case-insensitive name, including `used_on_import`; returns action and name. |
| **set_query** | `ruleset_name: str, name: str, text: str, used_on_import: bool=False` | **Writes:** upsert query text by case-insensitive name, including `used_on_import`; returns action and name. |

## Validation, import and export

| Tool | Arguments | Behavior / result |
|---|---|---|
| **validate_ruleset** | `ruleset_name: str, level: str='', limit: int=200` | Validate format and available source/target snapshots. `level` filters diagnostics (`ошибка`, `предупреждение`, `замечание`); the summary covers all levels. Returns snapshot availability and total/shown counts; minimum `limit` is 1. |
| **generate_rules_xml** | `ruleset_name: str, path: str='', allow_errors: bool=False` | **Writes XML:** validate first; errors yield `выгружено=false` unless `allow_errors=True`. Empty `path` selects the output directory and sanitized ruleset name. Success returns file/size/statistics/summary; an existing destination is overwritten. |
| **preview_rules_xml** | `ruleset_name: str, max_chars: int=6000` | Serialize without writing a file; returns total characters and a prefix (at least 500 characters requested). Does not call validation. |
| **import_rules_xml** | `path: str, ruleset_name: str` | **Writes ruleset:** parse existing XML, return statistics and unrecognised root-node names. Imported configuration names do not bind snapshots; use `bind_configurations` for metadata validation. |
| **bind_configurations** | `ruleset_name: str, source_alias: str='', target_alias: str=''` | **Writes:** bind nonempty source/target aliases to loaded snapshots. Empty arguments keep that side unchanged; returns both side descriptors. |

## Format reference and search

| Tool | Arguments | Behavior / result |
|---|---|---|
| **handler_interface** | `owner: str, node: str=''` | List handlers for `owner`, or retrieve one `node` interface, parameter names and a comment scaffold. Owners: `Конвертация`, `ПКО`, `ПКС`, `ПКГС`, `ПВД`, `ПОД`; unknown owner/node is an error. |
| **kd20_format_reference** | `section: str=''` | Return supported format sections; empty `section` returns all. Named sections: `корень`, `ПКО`, `ПКС`, `ПКГС`, `ПВД`, `ПОД`, `типы`. |
| **search_kd20** | `query: str, limit: int=8` | Search indexed documentation/rules/source with attribution; clamps `limit` to 1–20. An empty result proves only an index miss. |
| **explain_kd20** | `question: str, limit: int=6` | Return question and retrieved evidence with an instruction to answer only from cited sources; clamps `limit` to 1–12. This is retrieval context, not an independently verified explanation. |
| **index_kd20_path** | `path: str` | **Writes search index:** index an authorized documentation directory, configuration dump, BSL or ZIP within allowed roots. Missing path is an error; indexing does not bind configuration aliases to a ruleset. |

## Safe authoring sequence and limitations

1. Resolve the source/target dump paths and inspect existing aliases/ruleset names. Load both snapshots, inspect actual objects and retrieve format/handler interfaces before constructing rules. Do not infer that a missing snapshot property is absent in a live infobase.
2. Review suggested matches and unmatched properties. A draft does not settle object identity, duplicate handling, skipped fields or clearing behavior. Apply the project's material-fork rule when those decisions are unspecified. Both omitted `pairs` and `pairs=[]` enable automatic matching; pass a nonempty list of reviewed pairs when controlling the mapping.
3. Inspect the current item before every update. Except for the merging branch of `set_object_rule`, setters generally construct a complete item from arguments/defaults; omitted values can reset stored options. Deleting a group removes its nested contents; deleting an object rule can leave references that validation must detect.
4. After import, inspect `непрочитанные_узлы`. The importer records unknown root names, not their full XML; it also skips `Обработки` and `ПравилаРегистрацииОбъектов`. The writer does not preserve arbitrary original XML. Do not overwrite an original exchange file on the assumption of lossless round-trip; export to a separate reviewed artifact.
5. Check `конфигурации_доступны` as well as the complete validation summary. Unbound/unavailable snapshots reduce metadata-check coverage; no reported format errors alone is insufficient. Filtered/truncated diagnostics do not hide the summary's errors. Correct errors before normal export; `allow_errors=True` is an explicit diagnostic escape hatch, not a passing validation result or permission to use invalid exchange rules.
6. Verify generated XML and embedded BSL with the applicable existing tooling, then report exact artifact/check coverage. No tool in this catalog executes data transfer, supplies runtime safety proof or authorizes production import.

The source entry point uses `MCP_TRANSPORT` (default `stdio`). Do not infer a connected endpoint, launch the service, reindex unrelated data or modify installation settings merely because this catalog exists.
