# MCP_Test — optional PRE-ALPHA tool catalog

Native test-client recording, scenario authoring and replay. This experimental server is **outside the seven main MCP servers** and is not a required dependency. Load this reference only when the task needs it and its tools are exposed in the current session. The runtime server name is `1C Visual UI Test`; a client configuration alias may differ. The live `tools/list` schema takes precedence over this source snapshot.

Contract checked against `pre-alpha/MCP_Test/src/mcp_1c_ui_test/server.py` and its `runner.py`, `core.py`, `harness.py` implementations in the MCP development checkout, 2026-09-22: **26 tools**. Arguments below use Python signature notation: no `=` means required; shown defaults are optional; `None`, `True`, `False` correspond to JSON `null`, `true`, `false`. Paths are on the MCP server host, not necessarily the agent host.

## Scope and gates

Knowledge lookup and scenario inspection do not authorize starting an infobase session. Building a harness, recording or replaying requires an authorized test task, resolved target/manager connections and the existing [UI testing preflight](../../../rules/ui-testing-tools.md) and infobase procedures. Recorded/replayed UI actions may change business data. Generated BSL and harness changes remain subject to [verification gates](../../../rules/verification-gates.md); API-name checking and scenario lint are not replacements for BSL validation or a test verdict.

## Knowledge and platform discovery

| Tool | Arguments | Behavior / result |
|---|---|---|
| **search_testing_kb** | `query: str, limit: int=8, kind: str=''` | Search indexed API objects/members and curated guides. `kind` can filter `method`, `property`, `object`, or `guide`; returns matching records. |
| **get_kb_entry** | `entry_id: str` | Full record for an `api:...` / `guide:...` ID returned by search; may return `null`. |
| **list_tested_objects** | none | List indexed automated-testing objects and member counts. |
| **get_tested_object** | `name: str` | Describe methods/properties by Russian or English object name; may return `null`. |
| **kb_status** | none | Report indexed platform version/index size and discovered local syntax-help paths. Check build compatibility before relying on indexed API names. |
| **index_platform_syntax_help** | `version: str='', lang: str='ru', group: str=''` | **Writes:** rebuilds and overwrites the API index from local syntax help, then reloads it. Empty `group` selects automated testing. Missing help returns `ok=false`; use only for an authorized index-maintenance task. |
| **inspect_1c_platform** | none | Discover installed thin/thick clients, selected executable, runtime directories and harness availability; does not launch a client. |

## Harness and managed processes

| Tool | Arguments | Behavior / result |
|---|---|---|
| **build_harness** | `output: str='', designer_base: str='', executable: str='', timeout: float=300.0` | **Runs platform and writes:** builds `MCPTestRunner.epf`; may create a build infobase and retains it. Existing output is deleted before building. Returns `ok`, harness path/size, exit code and logs; `ok` depends on a nonempty output file, not exit code alone. |
| **start_test_client** | `connection: str, port: int=1538, user: str='', password: str='', executable: str='', additional_args: list[str] \| None=None` | **Starts session:** launch `/TestClient` and return a managed process record. `connection` is an existing file-base directory or server connection value. `additional_args` is a JSON string array. |
| **start_test_manager** | `connection: str, user: str='', password: str='', executable: str='', execute: str='', startup_parameter: str='', additional_args: list[str] \| None=None` | **Starts session / may execute code:** launch `/TestManager`; `execute` selects an external processor and `startup_parameter` is passed through `/C`. Returns a managed process record. |
| **wait_test_client** | `host: str='127.0.0.1', port: int=1538, timeout: float=30.0` | Wait for TCP acceptance; returns availability/error. An open port does not prove that the application is ready or that a test passed. |
| **list_test_processes** | none | List only processes registered by this MCP, with current status. |
| **get_test_process** | `process_id: str` | Status of one MCP-managed process, using its returned `id` as `process_id`. |
| **stop_test_process** | `process_id: str, force: bool=False` | **Stops session:** request window close first; if necessary terminate. `force=True` skips graceful close. Returns `stopped` and method/reason; confirm success instead of assuming shutdown. |
| **read_test_log** | `process_id: str, tail_lines: int=200` | Return the managed process log tail. Treat logs as potentially sensitive application output. |

## Recording and import

| Tool | Arguments | Behavior / result |
|---|---|---|
| **start_ui_log_recorder** | `connection: str, name: str='recording', port: int=1538, user: str='', password: str='', executable: str='', output_file: str=''` | **Starts session and writes:** launches `/UILogRecorder` for human actions; creates output directory and deletes an existing output file. Returns process record/output path. Finish recording in the client panel before collection. |
| **collect_recording** | `process_id: str='', output_file: str='', name: str='recorded', dialect: str='default', stop: bool=True, wait_seconds: float=20.0` | Supply `process_id` or `output_file`. **Writes** a scenario and, with default `stop=True`, **stops** the specified recorder. Returns coverage, unmapped count/sample and lint, or `ok=false` when no log appears. Stopping a process does not guarantee the platform saved its recording. |
| **inspect_ui_log** | `path: str, dialect: str='default'` | Inspect actual XML structure and dialect mapping coverage before parsing an unfamiliar recording; does not start a client. |
| **parse_ui_log** | `path: str, name: str='recorded', dialect: str='default', host: str='127.0.0.1', port: int=1538, save: bool=True` | Parse using a chosen dialect; returns step count, coverage, lint and up to 20 unmapped entries. Default `save=True` **writes** the scenario JSON; otherwise returns the document. |
| **list_ui_log_dialects** | none | List available dialects, including those configured via `MCP_1C_UILOG_DIALECTS`. |
| **import_bsl_scenario** | `path: str, name: str=''` | Parse a BSL test module and **save** scenario JSON. Returns lint plus unrecognised count/sample; imported steps do not imply full coverage of the source module. |

## Scenario authoring and replay

| Tool | Arguments | Behavior / result |
|---|---|---|
| **list_scenario_actions** | none | Return supported actions, their parameters and scope. Use this schema to construct `steps` instead of guessing action fields. |
| **create_scenario** | `name: str, steps: list[dict[str, Any]], host: str='127.0.0.1', port: int=1538, language: str='ru', save: bool=True, connect_timeout: int=60` | Build/validate/lint a document. `steps` is an array of action objects. Returns `ok`, step count and lint; writes JSON only when `save=True` and no blocking lint errors, otherwise returns `scenario`. |
| **lint_scenario** | `path: str='', scenario: dict[str, Any] \| None=None` | Read a file or use the supplied nonempty `scenario` object. Returns errors, warnings and info, including fragile locators, missing waits and absent assertions. An empty dict falls back to `path`. |
| **generate_bsl** | `path: str='', scenario: dict[str, Any] \| None=None, wrapper: str='function', procedure: str='', save: bool=True` | Read `path` or nonempty `scenario`. `wrapper="function"` generates an exported-function module; `"inline"` produces harness statements. Checks emitted calls against the API index. Default `save=True` **writes** BSL and returns its path; otherwise returns `bsl`. |
| **replay_scenario** | `scenario_path: str, target_connection: str, manager_connection: str, harness: str='', port: int=1538, user: str='', password: str='', manager_user: str='', manager_password: str='', executable: str='', port_timeout: float=60.0, run_timeout: float=300.0, settle: float=120.0` | **Runs live sessions, executes scenario and writes artifacts:** starts client then manager/harness, reads JSON verdict and attempts to stop both processes in `finally`. Returns `ok`, `stage`, verdict/result paths and failed-step detail when finished; setup/runtime failures include stage-specific evidence. |

## Recording, readiness and result handling

1. Inspect `kb_status` and `inspect_1c_platform`; use the relevant indexed API build and an existing harness or an authorized `build_harness` operation. Empty `harness` resolves through `MCP_1C_HARNESS`, then the default built artifact; missing harness yields `ok=false`, `stage="setup"`.
2. For a recording, finish it in the application panel, inspect coverage and resolve unmapped/unrecognised actions before claiming equivalent replay. `collect_recording` and import can save an incomplete scenario; `ok=true` on collection means a log was processed, not that all actions were understood.
3. Inspect actions, lint, review generated BSL and apply applicable validation before replay. Named scenario outputs can overwrite earlier JSON/BSL; replay also removes the previous same-name result JSON. Select task-specific names and retain required evidence before rerunning.
4. Readiness has distinct bounds: `port_timeout` waits for TCP, `settle` bounds the application-window wait (`0` skips it), scenario `connect_timeout` bounds manager connection retries, and `run_timeout` waits for the harness result. The scenario's stored `connection.port` overrides the replay call's `port`; verify the stored host/port.
5. Empty `manager_user` / `manager_password` fall back to the target credentials. Pass only credentials already authorized for the selected test bases; never copy them into rules, logs or reports. `additional_args` and startup parameters are passed through to the process and must remain within the authorized test scope.
6. `stage="finished"` alone is not success: `ok` is derived from verdict `Success`; inspect `failed_step` and result/log evidence. Process cleanup is attempted, not guaranteed; use process status if an operation fails or sessions may remain. Do not kill unrelated 1C processes to make a replay succeed.

The source entry point defaults to `stdio`; other `MCP_TRANSPORT` values select streamable HTTP at `MCP_HOST` (default `127.0.0.1`), `MCP_PORT` (default `8013`), path `/mcp`. This describes the implementation, not proof of a connected server. Do not launch or reconfigure it merely because this reference is present.
