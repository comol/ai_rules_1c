# edt-mcp — tool catalog

Live access to a running **1C:EDT** instance and its workspace: the in-memory model, validation markers, native navigation and refactoring, metadata and forms, application launch / DB update, debugging and profiling. Upstream: [DitriXNew/EDT-MCP](https://github.com/DitriXNew/EDT-MCP), installed into EDT itself by `content/commands/install-edt-mcp.md` and exposed over Streamable HTTP on loopback (default `http://127.0.0.1:8765/mcp`).

> Load this file only when the project uses EDT (`.dev.env` `USE_EDT=true`) **and** EDT-MCP tools are actually exposed in the current session. A client-config entry or a responding `/health` endpoint proves the plugin, not the session. Process rules for EDT projects — `content/rules/edt-workflow.md`; this file is the server-side catalog.

This server is **conditional**, unlike the 1C MCP bundle: it exists only on a workstation where EDT is installed, running, and holding the project workspace. A closed EDT means the tools disappear, not that the project changed.

## Parameters — ask the server, not this file

EDT-MCP ships its own live reference:

- **`get_tool_guide`** — the authoritative per-tool guide (what it does, every parameter, how it behaves), generated from the running server. Call it before the first non-obvious call to a tool; upstream's `docs/tools/` pages are generated from the same source.
- **`list_toolsets`** / **`enable_toolset`** — progressive disclosure. When it is on, only the core toolset appears in `tools/list`; call `list_toolsets` to see the groups, `enable_toolset` with the ids you need, then **re-request `tools/list`** to see the revealed tools. A tool that "does not exist" in an EDT session is usually a hidden toolset, not a missing feature.
- **`get_server_status`** / **`get_edt_version`** — confirm what you are actually connected to before reporting an EDT-side result.

This ruleset deliberately does not restate EDT-MCP parameter lists: the server version on the user's machine is the truth, and a stale copy here would be worse than no copy.

## Toolsets

| Toolset | Tools | Use for |
|---|---|---|
| **Core** | `get_edt_version`, `get_server_status`, `get_tool_guide`, `list_toolsets`, `enable_toolset`, `list_projects`, `list_modules`, `read_module_source`, `search_in_code`, `get_module_structure`, `get_metadata_objects`, `get_metadata_details` | Orientation inside the workspace: which projects / modules exist, what an object looks like, read a module. |
| **Code** | `read_method_source`, `write_module_source`, `find_references`, `go_to_definition`, `get_symbol_info`, `get_content_assist`, `get_method_call_hierarchy`, `get_outgoing_structures`, `validate_query` | Reading and writing BSL with EDT's own resolver; exact references and definitions as EDT sees them right now. |
| **Metadata** | `create_metadata`, `modify_metadata`, `delete_metadata`, `rename_metadata_object`, `adopt_metadata_object`, `get_configuration_properties`, `list_configurations`, `list_subsystems`, `get_subsystem_content`, `list_common_pictures`, `export_common_picture`, `create_launch_config`, `delete_launch_config` | Metadata mutations in an EDT-format tree — the EDT equivalent of the `1c-metadata-manage` gate (`content/rules/edt-workflow.md`). |
| **Project** | `get_project_errors`, `get_problem_summary`, `get_markers`, `get_check_description`, `revalidate_objects`, `apply_quick_fix`, `resync_to_disk`, `update_database`, `create_infobase`, `delete_infobase`, `set_infobase_credentials`, `export_configuration_to_xml`, `import_configuration_from_xml`, `build_external_objects`, `clean_project`, `create_project`, `delete_project`, `get_event_log`, `get_platform_documentation`, `get_mcp_history`, `validate_xdto_package` | EDT validation, model↔disk synchronization, format conversion, infobase and build operations. |
| **Git** | `git`, `list_git_branches`, `create_git_branch`, `switch_git_branch`, `set_branch_infobase` | Version control **inside** the workspace, including the branch↔infobase binding EDT maintains. |
| **Forms** | `get_form_layout_snapshot`, `get_form_screenshot`, `get_template_screenshot` | Inspecting what a form / template actually looks like after a change. |
| **Testing** | `get_job_status`, `cancel_job`, `ask_workmate` | `ask_workmate` delegates a question to the 1C:Workmate plugin as a background job. |
| **Debug** | `debug_launch`, `debug_status`, `get_applications`, `set_breakpoint`, `list_breakpoints`, `remove_breakpoint`, `resume`, `step`, `wait_for_break`, `get_variables`, `set_variable`, `evaluate_expression`, `terminate_launch` | Driving a real debug session against a running application. |
| **Profiling** | `start_profiling`, `stop_profiling`, `get_profiling_results` | Measuring instead of guessing on a performance task. |
| **Tags / Translation** | `get_tags`, `get_objects_by_tags`, `get_translation_project_info`, `generate_translation_strings`, `translate_configuration` | EDT tagging and the translation subsystem. |

Toolset composition and tool names follow the installed plugin version — `list_toolsets` is authoritative when this table and the session disagree.

## Which server first

EDT-MCP does **not** replace the 1C MCP bundle. The bundle owns indexed and external knowledge; EDT-MCP owns the live IDE.

| Question | Server |
|---|---|
| Semantic code search, impact analysis, call chains across the configuration, business search | `1c-graph-metadata-mcp` / `1c-code-metadata-mcp` |
| Platform documentation, БСП / SSL, ITS standards, code templates, project memory | `1C-docs-mcp`, `1c-ssl-mcp`, `1c-code-check-mcp`, `1c-templates-mcp` |
| BSL syntax / style / quality verdicts | `1c-syntax-checker-mcp`, `1c-code-check-mcp` (Gates 1–3 are unchanged in EDT projects) |
| What is broken **in the workspace right now**, per EDT's own validators | `edt-mcp` (`revalidate_objects` → `get_project_errors` / `get_problem_summary`) |
| Exact references / definitions as EDT resolves them; content assist at a caret | `edt-mcp` |
| Metadata mutation in an **EDT-format** (MDO) tree | `edt-mcp` |
| Metadata mutation in a **Designer XML dump** | `1c-metadata-manage` skill — unchanged hard gate |
| Applying configuration changes to an infobase from the IDE, launching, debugging, profiling | `edt-mcp` |
| Running BSL / a query against a live infobase without EDT | `1c-data-mcp` |

`search_in_code` is a literal / regex textual sweep and is **not** ru/en dialect aware — it misses the other BSL language variant. It does not satisfy the MCP-first search chain (`content/rules/mcp-first-search.md`); use the indexed servers for search and this tool for targeted textual confirmation.

## Safety and discipline

- **Destructive operations require consent by default** — `delete_metadata`, `rename_metadata_object`, `delete_project`, `delete_infobase`, `update_database`, and `modify_metadata` when it changes a data type. The prompt is the user's decision point. Never disable it on the user's behalf: the "Allow all" consent level and the `EDT_MCP_DESTRUCTIVE_CONSENT=allow` override are for unattended automation the user explicitly asked for, and you must say what they remove.
- **Full trust surface.** The server exposes filesystem, code-writing, DB-update and debug operations to every connected client. Loopback binding is the default and should stay; a non-loopback bind requires an auth token and a trusted network. Never print or commit that token.
- **The model is the authority, the disk lags.** `resync_to_disk` flushes model → disk and reports desync. Reconcile before mixing EDT-MCP with file-level tools, and never alternate owners on one artifact — canon: `content/rules/edt-workflow.md → Model vs disk — the synchronization rule`.
- **Background jobs are not blocking calls.** `ask_workmate` returns a job id; poll with `get_job_status`, stop with `cancel_job`. Do not re-launch a job because the first call returned before the run finished.
- **Debug / profiling / `update_database` act on a real application.** Confirm the target is a dev / test base first, exactly as the deployment slash commands require.
- **`import_configuration_from_xml` creates a new project**, it does not update the current one. Confirm with the user before any export/import round trip.
- **Budget rules are unchanged** (`AGENTS.md → MCP Tool Calling → B.1`, `C.1`): no repeated calls against unchanged state, and EDT markers do not open a retry loop of their own. `get_mcp_history` shows what this session already asked — use it instead of re-running a call to remember its result.
