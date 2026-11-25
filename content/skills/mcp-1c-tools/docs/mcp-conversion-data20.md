# 1c-kd20 (KD20) — tool catalog

Authoring, review and validation of exchange rules for «Конвертация данных» 2.0/2.1 (format 2.01: exchange, correspondent and registration rules) and read-only inspection of exchanges through the universal format (EnterpriseData, «Конвертация данных» 3); it also keeps the profiles of the two exchange bases (location, credentials, data server) and their launch strings. One of the nine main MCP servers (image `comol/1c_conversion_data_mcp`, port 8009, MCP connection name `1c-kd20`; runtime server name `1C Конвертация данных 2.0 — разработка правил обмена`), but it is installed separately and is needed only for exchange-rule tasks: it is not in `mcp-servers.json` and no normal development gate requires it.

> Load this file only for an exchange-rules task and only when the server's tools are visible in the current session. The live `tools/list` schema is authoritative for the connected version.

Contract checked against `servers/MCP_ConversionData20/src/kd20_mcp/server.py`, version 0.5.0, 2026-10-21: **71 tools**. Arguments use Python signature notation: no `=` means required; `None`, `True`, `False` correspond to JSON `null`, `true`, `false`; `dict` is a JSON object, `list[...]` an array. Paths are the agent machine's paths: in a container the server translates them through `KD20_PATH_MAP` and answers with the same paths.

## Scope, persistence and safety

- Input is configuration dumps (Designer `Configuration.xml` or EDT `Configuration.mdo`) and rule files (`ExchangePlans/<План>/Templates/<Макет>/Ext/Template.txt`, `ExchangeRules.xml`, `RegistrationRules.xml`), not infobases. The server stores configuration snapshots, editable rulesets, registration rule sets, output files and a search index (`KD20_DATA`, `KD20_OUTPUT`, `KD20_DB`); paths outside `KD20_ALLOWED_ROOTS` are refused — do not widen the roots to evade a refusal.
- Writes: tools marked **Writes** change a stored snapshot/ruleset or write a file. Importing or creating under an existing name replaces it; check `list_configurations` / `list_rulesets` / `describe_registration_rules` first. Write output to a separate reviewed artifact, not over the configuration's `Template.txt`, unless the task is exactly that replacement under the project's procedures.
- Import is lossless (rule groups, `Обработки`, search variants, unknown nodes, the source file's BOM/line endings/indent); `generate_rules_xml(style="kd")` writes the КД 2.1 style for `Template.txt`.
- Sandbox tools (`check_rules_in_1c`, `dump_rules_from_1c`, `exchange_plans_in_1c`, `check_registration_in_1c`) call the data server of a **copy** of an infobase (`1c-data-mcp`, `…/hs/mcp` with `vcexecutecode`, from `KD20_SANDBOX_DATA_URL`, `data_server_url` or the profile named by `base`; rollback checks by `base` need `sandbox=True` in that profile). They are optional: without a data server they refuse. Use them only on a sandbox the user named for this task ([1c-live-ib](../../1c-live-ib/SKILL.md)); never point them at a production base. `dump_rules_from_1c` and `exchange_plans_in_1c` only read; `check_rules_in_1c` and `check_registration_in_1c` run inside a transaction that is always cancelled, but side effects of subscriptions outside the database (files, external calls, messages) are not rolled back.
- Exchange base profiles (`set_base`) keep the base user's password in plain text under `KD20_DATA/bases`; answers mask it. Take credentials only from the user, mark a profile `sandbox=True` only for a copy the user named as such, and use `base_launch_string(include_password=True)` only to start the base — never put the real password into reports, files or commits.
- The server never executes found BSL on its own side, never runs a live exchange, never launches a base (the agent runs the launch string) and never loads rules into a «Конвертация данных» base. КД 3 tools read and check the exchange manager module; they do not write it.
- Handler code is BSL: generated or edited handlers still need the verification gates of `content/rules/verification-gates.md` (`export_handlers_bsl` → syntax checker → `locate_handler_line`). `validate_ruleset` is not a substitute for BSL validation, an exchange run or decisions about matching and deleting business data.

## Before editing exchange rules

- Import handlers run from the receiver's stored **copy** of the sender's rules (the correspondent rules), not from the rules inside the message: a fix to loading touches two files (sender rules and the receiver's correspondent rules) and the rule set must be reloaded in the receiver.
- Edit rules only with the server's tools, not by text edits of the XML; review the change with `diff_rulesets` against the original file.
- Physical deletion during an exchange (clearing rules, receiving deletion) is a material decision: ask the user explicitly; the default is marking for deletion.
- The rules loaded in a base may differ from the configuration's template: `dump_rules_from_1c` + `diff_rulesets` show what actually runs.
- Exchange pitfalls (duplicates, objects sent only by reference, transactions, registration, error codes of the exchange protocol, «complaint → what to check first», handler phases and `Отказ`, EnterpriseData) are served by the server: `kd20_format_reference(section="грабли" | "протокол" | "жалобы" | "фазы" | "кд3_грабли")` and `search_kd20`. Do not restate them from memory.

## Configurations and matching

| Tool | Arguments | Behavior / result |
|---|---|---|
| **load_configuration** | `path: str, alias: str` | **Writes snapshot:** parse a Designer dump or EDT project and save it under `alias`; returns name/version, format and object counts. |
| **list_configurations** | none | Stored aliases and summaries. |
| **list_metadata** | `alias: str, kind: str='', name_filter: str='', limit: int=100` | Objects of a snapshot; `kind` is a Russian kind or English class, `name_filter` matches name/synonym. |
| **describe_object** | `alias: str, name: str` | Attributes with types, tabular sections, enum values, flags (hierarchy, posting) of one object. |
| **compare_configurations** | `old_alias: str, new_alias: str, kind: str='', limit: int=200` | Removed/added objects, attributes, tabular sections, enum values and changed types between two versions. |
| **suggest_object_mappings** | `source_alias: str, target_alias: str, classes: list[str] \| None=None, threshold: float=0.55, limit_per_object: int=3, only: list[str] \| None=None, limit: int=200` | Ranked object pairs with reasons. An object with no name candidate gets a renamed candidate by attribute composition (≥70 % shared, `по_составу: true`); drafts never take those automatically. |
| **suggest_property_mappings** | `source_alias: str, target_alias: str, source_object: str, target_object: str, threshold: float=0.55` | Attribute/tabular-section pairs and unmatched properties of both sides. |

## Rulesets: ПКО, ПКС, ПКЗ, ПВД, ПОД

| Tool | Arguments | Behavior / result |
|---|---|---|
| **create_ruleset** | `name: str, source_alias: str, target_alias: str, title: str='', comment: str=''` | **Writes:** empty ruleset bound to two snapshots. |
| **draft_ruleset** | `name: str, source_alias: str, target_alias: str, classes: list[str] \| None=None, threshold: float=0.7, pairs: list[dict] \| None=None, sync_by_id: bool \| None=None, title: str='', comment: str=''` | **Writes:** draft by automatic same-class matching or explicit `pairs=[{"source": "...", "target": "..."}]` (omitted or empty `pairs` = automatic). `sync_by_id` omitted = КД 2.1 defaults: identifier sync for ПКО with a reference (non-enum) target, search fields only for rules without it, «Обязательное» on `ЭтоГруппа`; listed in `по_умолчанию`. For the first sync of bases that already hold data, sync by identifier alone creates duplicates: pass `sync_by_id=false` or add search properties with search continuation. ПКС the runtime would skip are created disabled (`выключенные_ПКС`). |
| **list_rulesets** | none | Saved rulesets and statistics. |
| **describe_ruleset** | `name: str, rule_code: str=''` | Summary, or one full ПКО by code. |
| **set_object_rule** | `ruleset_name: str, code: str, source: str='', target: str='', name: str='', flags: dict \| None=None, handlers: dict \| None=None, search_in_tabular_sections: str='', replace: bool=False, group: str='', priority: str='', comment: str=''` | **Writes:** create/update a ПКО (`source`/`target` are reference types, `group` is the КД tree path, `priority` `Ниже`/`Совпадает`). Default merges and keeps properties; `replace=True` replaces the whole rule. A new rule with a reference target gets identifier sync unless `flags` says otherwise. |
| **set_object_rules_flags** | `ruleset_name: str, flags: dict \| None=None, codes: list[str] \| None=None, source_kind: str='', preset: str=''` | **Writes:** flags on many ПКО; `preset="НСИ"`. |
| **delete_object_rule** | `ruleset_name: str, code: str` | **Writes:** removes a ПКО without cascading; validate afterwards. |
| **set_property_rule** | `ruleset_name: str, rule_code: str, code: str, source_name: str='', target_name: str='', source_type: str='', target_type: str='', source_kind: str='Реквизит', target_kind: str='Реквизит', kind: str='property', search: bool=False, conversion_rule: str='', group_code: str='', handlers: dict \| None=None, order: int=0, do_not_replace: bool=False, get_from_incoming_data: bool=False, cast_to_length: int=0, parameter_name: str='', search_by_date_equality: bool=False, disable: bool=False, name: str='', required: bool \| None=None` | **Writes:** upsert ПКС (`kind="property"`) or ПКГС (`kind="group"`). The item is rebuilt from the arguments — inspect it first; omitted options reset, except `required`, which is kept when omitted. |
| **delete_property_rule** | `ruleset_name: str, rule_code: str, code: str, group_code: str=''` | **Writes:** removes a ПКС/ПКГС (a group with its contents). |
| **set_value_map** | `ruleset_name: str, rule_code: str, values: list[dict]` | **Writes:** replaces the whole ПКЗ list (`[{"source": "...", "target": "..."}]`). |
| **set_export_rule** | `ruleset_name: str, code: str, selection_object: str='', conversion_rule: str='', name: str='', order: int=0, data_selection_method: str='СтандартнаяВыборка', single_query: bool=True, disable: bool=False, handlers: dict \| None=None, group: str=''` | **Writes:** upsert a ПВД. |
| **delete_export_rule** | `ruleset_name: str, code: str` | **Writes:** removes a ПВД. |
| **set_clear_rule** | `ruleset_name: str, code: str, selection_object: str='', name: str='', order: int=0, data_selection_method: str='СтандартнаяВыборка', delete_for_period: bool=False, directly: bool=False, disable: bool=False, handlers: dict \| None=None` | **Writes rule definition:** upsert a ПОД. Deletes nothing now; an exchange through a БСП exchange plan does not execute ПОД at all (only the universal data processor does). |
| **set_conversion_handler** | `ruleset_name: str, node: str, text: str` | **Writes:** global conversion handler; empty `text` removes it. |
| **set_parameter** | `ruleset_name: str, name: str, title: str='', value_type: str='', set_in_dialog: bool=False, used_on_import: bool=False, pass_on_export: bool=False, conversion_rule: str='', after_load_algorithm: str=''` | **Writes:** upsert a parameter (rebuilt from arguments). |
| **set_algorithm** | `ruleset_name: str, name: str, text: str, used_on_import: bool=False` | **Writes:** upsert an algorithm (`Выполнить(Алгоритмы.Имя);`). |
| **set_query** | `ruleset_name: str, name: str, text: str, used_on_import: bool=False` | **Writes:** upsert a query (`Запросы.Имя`). |
| **bind_configurations** | `ruleset_name: str, source_alias: str='', target_alias: str=''` | **Writes:** binds snapshots for metadata checks; empty argument keeps that side. |
| **draft_correspondent_ruleset** | `name: str, from_ruleset: str, rule_codes: list[str] \| None=None, target_alias: str='', with_export_rules: bool=True` | **Writes:** reverse-direction draft by mirroring ПКО/ПКС/ПКЗ; handlers are returned as a «transfer manually» list. A base, not finished rules. |

## Validation, files and comparison

| Tool | Arguments | Behavior / result |
|---|---|---|
| **validate_ruleset** | `ruleset_name: str, level: str='', limit: int=200, registration_name: str=''` | Format, metadata of both bound snapshots and the behaviour of the БСП runtime for exchange through an exchange plan (errors E…, warnings W…, notes I…). `level` filters the list, the summary covers everything; `registration_name` accounts for the «when needed» export mode. Check `конфигурации_доступны`: without bound snapshots metadata checks do not run. |
| **generate_rules_xml** | `ruleset_name: str, path: str='', allow_errors: bool=False, style: str=''` | **Writes XML:** refuses while validation has errors unless `allow_errors=True` (a diagnostic escape hatch, not a pass). `style="kd"` — КД 2.1 style for `Template.txt`. |
| **preview_rules_xml** | `ruleset_name: str, max_chars: int=6000` | Beginning of the XML without writing a file. |
| **import_rules_xml** | `path: str, ruleset_name: str` | **Writes ruleset:** lossless import of an exchange-rules file or template; bind snapshots afterwards. |
| **diff_rulesets** | `left: str, right: str, limit: int=200` | Semantic diff of two rulesets or rule files (ПКО, ПКС, ПКЗ per value, ПВД, ПОД, algorithms, parameters, handlers changed with line counts); two registration rule sets/files are compared by object. |
| **pack_rules_zip** | `ruleset_name: str='', correspondent_ruleset: str='', registration_name: str='', path: str=''` | **Writes ZIP:** deterministic archive for manual loading in the exchange-plan rules form (`ExchangeRules.xml` + `CorrespondentExchangeRules.xml` as a pair, plus `RegistrationRules.xml`, or registration alone); SHA-256 in the answer. |
| **export_handlers_bsl** | `ruleset_name: str, directory: str=''` | **Writes files:** every handler and algorithm as a BSL module with the handler's parameters, for the syntax checker. |
| **locate_handler_line** | `file: str, line: int` | Line of an exported BSL file → rule, handler and line inside it. |

## Exchange bases and exchanges

| Tool | Arguments | Behavior / result |
|---|---|---|
| **set_base** | `name: str, file_path: str='', server: str='', ref: str='', web_url: str='', user: str='', password: str \| None=None, platform: str='', data_server_url: str='', data_server_auth: bool \| None=None, sandbox: bool \| None=None, dump_path: str='', configuration_alias: str='', comment: str='', replace: bool=False` | **Writes base profile:** location is one of `file_path`, `server` + `ref` (cluster `host` or `host:port` and the base name), `web_url`; `platform` is a version, folder or `1cv8.exe` for the launch string; `data_server_auth=True` sends the base login to the data server (Basic), the standard `…/hs/mcp` publication is anonymous; `sandbox=True` allows rollback checks by `base`. An existing profile is merged: an empty argument keeps the stored value, `password=None` keeps the password, `password=""` removes it; `replace=True` rebuilds the profile. |
| **describe_bases** | `name: str=''` | Bases with location, data server, sandbox flag and their exchanges, or one base with its connection string (password masked). No passwords in the answer. |
| **delete_base** | `name: str` | **Writes:** removes the profile and its password; refused while an exchange refers to the base. |
| **base_launch_string** | `name: str, mode: str='ENTERPRISE', client: str='thick', include_password: bool=False` | `команда`, `программа` + `аргументы` (to start without a shell) and `строка_соединения` (`File=…;` / `Srvr=…;Ref=…;` / `ws=…;`) for `ENTERPRISE` or `DESIGNER`, `thick` (1cv8) or `thin` (1cv8c). Password masked unless `include_password=True`. |
| **check_base_in_1c** | `name: str, exchange_plan: str=''` | Read-only through the base's data server: configuration and version, platform, БСП version, connection string, session user, the universal XML exchange data processor, and per exchange plan (the base's exchanges and `exchange_plan`) — presence, БСП connection, technology, EnterpriseData versions; mismatches with the profile (location, snapshot, technology, format version) in `замечания`. |
| **set_exchange** | `name: str, source_base: str='', target_base: str='', technology: str='', source_exchange_plan: str='', target_exchange_plan: str='', ruleset_name: str='', correspondent_ruleset: str='', registration_name: str='', format_version: str='', comment: str='', replace: bool=False` | **Writes exchange:** source → target pair of `set_base` profiles, `technology` `КД2` (XML rules, default) or `КД3` (EnterpriseData), the БСП exchange plans of both sides. КД 2: `ruleset_name` (this direction, exported by the source), `correspondent_ruleset` (reverse direction, the target's own rules), `registration_name` (source registration). КД 3: `format_version` (`1.20`). Merges like `set_base`; returns `шаги` — KD20 calls for this exchange. |
| **describe_exchanges** | `name: str=''` | Exchanges, or one exchange with both bases (no passwords), technology, plans, rules and `шаги`. |
| **delete_exchange** | `name: str` | **Writes:** removes the exchange; bases and rules stay. |

## Sandbox infobase through its data server (optional)

| Tool | Arguments | Behavior / result |
|---|---|---|
| **check_rules_in_1c** | `ruleset_name: str, exchange_plan: str, correspondent_ruleset: str='', registration_name: str='', data_server_url: str='', base: str=''` | Loads the rules with the standard БСП method (`ПравилаДляОбменаДанными.ЗагрузитьПравила`) into an in-memory record inside a cancelled transaction; answers whether the rules load and why not (БСП message, exception, event log). |
| **dump_rules_from_1c** | `exchange_plan: str, directory: str='', import_as: str='', data_server_url: str='', base: str=''` | Read-only: rules currently active in the base (source — template or file, loaded or not, rule info, XML of exchange/correspondent/registration rules in chunks with SHA-256), written as the БСП file set; **Writes** rulesets `import_as`, `import_as_корреспондент` and registration rules `import_as` when `import_as` is given. |
| **exchange_plans_in_1c** | `exchange_plan: str='', nodes_limit: int=20, data_server_url: str='', base: str=''` | Read-only overview: БСП connection, XML or universal format, nodes, plan templates, rules register records, version-mismatch warning and selective-registration settings, data sync constant. |
| **check_registration_in_1c** | `object_name: str, ref: str='', code: str='', exchange_plan: str='', write: bool=True, data_server_url: str='', base: str=''` | Where an object is registered: recipients by the active registration rules (`ОбменДаннымиСобытия.ОпределитьПолучателей`) and, with `write=True`, a normal write inside a transaction that is always cancelled (registration is compared before/after). Unchanged objects are not registered under selective registration — read `получатели_по_правилам`. |

## Registration rules

| Tool | Arguments | Behavior / result |
|---|---|---|
| **import_registration_rules** | `path: str, name: str` | **Writes:** lossless import of a registration-rules file (filters, handlers). |
| **build_registration_rules** | `name: str, configuration_alias: str, exchange_plan: str, ruleset_name: str='', objects: list[str \| dict] \| None=None, base: str=''` | **Writes:** rules from the ruleset's ПВД or `objects` and the plan content (Designer dump `ExchangePlans/<План>/Ext/Content.xml`). An `objects` item is a name or `{"object", "plan_filter", "object_filter", "unload_mode", "name", "comment"}` with filter groups `{"operator": "И"|"ИЛИ", "items": [...]}`, constants (`value`) and `[ТЧ].Реквизит`; `base` keeps existing rules, a given key replaces that field. |
| **validate_registration_rules** | `name: str, configuration_alias: str, ruleset_name: str=''` | Objects in the configuration and the plan, filter properties, export-mode attribute, how the БСП loader will read the filters, `Валидное`; with `ruleset_name` — ПВД objects without a registration rule and registered objects without an enabled ПВД (codes R…). |
| **describe_registration_rules** | `name: str='', object_name: str=''` | List of registration rule sets, a summary or one rule with filters and handlers. |
| **generate_registration_xml** | `name: str, path: str='', style: str=''` | **Writes XML:** registration-rules file; `style="kd"` for the plan template. |

## Navigating existing rules

| Tool | Arguments | Behavior / result |
|---|---|---|
| **search_ruleset_code** | `ruleset_name: str, text: str, regex: bool=False, limit: int=50, offset: int=0, owner: str='', rule: str='', handler: str='', registration_name: str='', mappings: bool=True` | Search in handlers, events, algorithms, queries, ПКС mappings and (with `registration_name`) registration handlers and filters; place and line number; `следующее_смещение` for paging. |
| **read_handler** | `ruleset_name: str, owner: str, code: str, handler: str, property_code: str='', start_line: int=1, max_lines: int=200` | One handler page by page with line numbers (`следующая_строка`). |
| **trace_object** | `ruleset_name: str, object_name: str, registration_name: str='', depth: int=1, limit: int=100` | Path of an object: ПВД, ПКО, cascades of values to `depth` (whole object or only by reference), calls of its ПКО from code with the algorithm chain, shadowed ПВД, registration, what appears in the receiver. |
| **handler_queries** | `ruleset_name: str, owner: str, code: str='', handler: str='', property_code: str='', max_query_chars: int=3000` | Queries in handler code: packets, temporary tables and dependencies, parameters, executions, which query `Результат[n]` reads; text built by expressions or branches is marked incomplete. |

## Exchange through the universal format (КД 3, EnterpriseData), read-only

| Tool | Arguments | Behavior / result |
|---|---|---|
| **ed_open** | `path: str, module: str=''` | Opens an exchange manager module (`Module.bsl`, the common module folder, or the dump root with `module`, e.g. `МенеджерОбменаЧерезУниверсальныйФормат`); returns `project_id` and rule counts by direction. |
| **ed_overview** | `project_id: str` | Counts by direction, manager interface version, required export procedures and events, share recognised. |
| **ed_list** | `project_id: str, kind: str, text: str='', format_object: str='', metadata_object: str='', direction: str='', offset: int=0, limit: int=50` | Entities with addresses: `pko`, `pks`, `pktch`, `pod`, `pkpd`, `parameter`, `handler`, `algorithm`, `event`, `dispatcher`, `service`, `builder`, `diagnostic`. |
| **ed_get** | `project_id: str, address: str, include_text: bool=False, text_offset: int=0, text_limit: int=2000, offset: int=0, limit: int=50` | Entity by address (`ПКО/<Имя>`, `ПКО/<Имя>/ПКС/<Свойство>`, `ПОД/<Имя>`, `Обработчик/<Имя>`, …) with children, handlers, calls and optional source text. |
| **ed_locate** | `project_id: str, line: int` | What is on a module line (rule, ПКС, procedure, rules a handler is assigned to). |
| **ed_validate** | `project_id: str, schema_id: str='', configuration_alias: str='', direction: str='', level: str='', check_prefix: str='', address_prefix: str='', section: str='issues', offset: int=0, limit: int=50` | Checks by the БСП runtime (`ОбменДаннымиXDTOСервер`): module connectivity; with `schema_id` — against the format schema; with `configuration_alias` — against the configuration (codes EDE/EDW/EDI). `section="skipped"` lists what was not checked, `section="checks"` the checks and their basis. Extension layers and format-version routes are not read. |
| **ed_close** | `project_id: str` | Closes the snapshot. |
| **ed_schema_open** | `path: str, package: str='', imports: dict \| None=None` | Opens an EnterpriseData XDTO package (`Package.bin`, `Package.xdto`, the package `.xml` or the dump root with `package`); imports from neighbouring packages; returns `schema_id` and format version. |
| **ed_schema_types** | `schema_id: str, text: str='', kind: str='', namespace: str='', offset: int=0, limit: int=50` | Types of the schema (`object` or `value`). |
| **ed_schema_type** | `schema_id: str, name: str, section: str='properties', offset: int=0, limit: int=50` | One type: `properties`, `effective` (names as ПКС use them), `tables`, `values`, `facets`. |
| **ed_schema_close** | `schema_id: str` | Closes the schema snapshot. |

## Reference and search

| Tool | Arguments | Behavior / result |
|---|---|---|
| **handler_interface** | `owner: str, node: str=''` | Handlers of an owner (`Конвертация`, `ПКО`, `ПКС`, `ПКГС`, `ПВД`, `ПОД`) or one handler's exact parameters and scaffold. |
| **kd20_format_reference** | `section: str=''` | Format sections (`корень`, `ПКО`, `ПКС`, `ПКГС`, `ПВД`, `ПОД`, `типы`, `регистрация`) and text sections `грабли`, `протокол`, `жалобы`, `фазы`, `кд3_грабли`. The loader stops on an unknown node name — never go beyond these lists. |
| **search_kd20** | `query: str, limit: int=8` | Search in the indexed references, rules and sources with attribution; an empty result proves only an index miss. |
| **explain_kd20** | `question: str, limit: int=6` | Retrieved evidence for an answer; answer only from the cited sources. |
| **index_kd20_path** | `path: str` | **Writes search index:** indexes an allowed documentation folder, dump, BSL or ZIP. |

## Typical sequences

1. New rules: `load_configuration` ×2 → `suggest_object_mappings` / `suggest_property_mappings` → `draft_ruleset` or `create_ruleset` → `set_*` → `validate_ruleset` → handler code through `export_handlers_bsl` and the syntax checker → `generate_rules_xml` → `build_registration_rules` → `validate_registration_rules` → `generate_registration_xml` → optionally `check_rules_in_1c` / `pack_rules_zip`.
2. Changing existing rules: `import_rules_xml` of the template → `bind_configurations` → `validate_ruleset` (remember the existing findings) → `trace_object`, `search_ruleset_code`, `read_handler`, `handler_queries` → edits → `validate_ruleset` (no new findings) → `diff_rulesets(ruleset, path_to_template)` → `generate_rules_xml(style="kd")`.
3. After a configuration update: load the new dump under a new alias → `compare_configurations` → `bind_configurations` → `validate_ruleset`.
4. EnterpriseData: `ed_open` → `ed_overview` / `ed_list` / `ed_get` → `ed_schema_open` of the format version → `ed_validate(project_id, schema_id, configuration_alias)`.
5. Two bases of an exchange: `set_base` for each base → `set_exchange(name, source_base, target_base, technology, plans of both sides, rules)` → `check_base_in_1c` for each base (fix every `замечания` item first) → `describe_exchanges(name)` and follow its `шаги`; sandbox tools take `base` instead of `data_server_url`.

Report exactly which artifacts were produced and which checks ran; a clean `validate_ruleset` is not proof that the exchange works. The source entry point uses `MCP_TRANSPORT` (default `stdio`); do not install, start or reconfigure the server merely because this catalog exists.
