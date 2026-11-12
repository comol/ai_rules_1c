---
name: 1c-qa-testing
description: "Check the 1C thin client through QA MCP (`1c-qa`): drive forms interactively, assert observed results, and save or rerun repeatable UI scenarios as pytest files on native QA MCP 0.8.0+."
argument-hint: "<feature or scenario to check>"
---

# 1c-qa-testing — UI checks through QA MCP

QA MCP (connection `1c-qa`) is the 1C test manager: it connects to a 1C test client (`/TestClient`) and drives its forms through the platform testing model — windows, fields, tables, commands, messages. It reads structured state, not pixels, so it is the main route for checking behaviour in the 1C interface. The web client (`content/rules/ui-testing-tools.md`) is the fallback.

## When this route applies

All of these hold:

- `UI_TESTING` allows the check (`content/rules/dev-standards-env.md → UI_TESTING`): `essential` / `auto` after the change reached the dev/test infobase, `manual` on an explicit request, never under `off`.
- `TOOL_QA` is not `off` (`content/rules/mcp-policy.md → Tool availability`).
- For interactive checks, the `qa_*` / `ui_*` tools are exposed in this session and `qa_status` answers. For saved tests, the runner connects to QA MCP itself.
- The target is an authorized dev/test infobase (`INFOBASE_ROLE`), the one in `.dev.env`.

Otherwise use the web fallback of `ui-testing-tools.md`, or report the check unrun with the reason. `TOOL_QA=required` with the server missing blocks the check; the web client does not replace it.

**Before the first action load `content/rules/qa-testclient.md`.** It owns what the server does not do: starting and stopping the test client, visible or hidden window, screenshots, agent-desktop, and confirming data through `1c-data-mcp`. Tool argument names come from the exposed schemas; `qa_playbook` returns the sequence for the current executor.

## Other MCP servers in a check

When a check needs metadata, form structure, impact, error source or live data, load the matching entry in [context-sources.md](docs/context-sources.md). Use indexes only when they cover the configuration loaded into the tested infobase; confirm element names in the live window.

## Session

1. `qa_status` — the executor decides who starts 1C:

   | `executor` | What it is | Test client |
   |---|---|---|
   | `native` | The container is the test manager and speaks the test-client protocol; no 1C platform inside | The agent starts it by `qa-testclient.md`; the server only connects |
   | `platform` | Windows manager next to the platform | `qa_start` starts it itself |

2. Start or find the test client (`qa-testclient.md`), then `qa_start(connection="<session name>")`; `port=` overrides the port of `MCP_QA_TESTCLIENT`. No Windows account is needed: the test client accepts the channel's Windows authentication from any identity (8.3.27.2130); the 1C sign-in happens when the client starts.
3. `qa_status` again: executor, link, target. A `test client is already connected to another manager` answer means another agent owns the client — a conflict to resolve, not a client to close.
4. At the end: `qa_stop`. In `native` it only disconnects; the client is closed by the tool that started it (`qa-testclient.md`). A new MCP session or a restarted client needs a new `qa_start`; `save_as` aliases and `ui_here` pins do not survive it.

After `/update1cbase`, `/deploy-and-test` or `/restore-testbase` the update ends the sessions of the infobase: a client started before it is stale. Start a fresh client, `qa_start`, and read the main window before the first step.

## Observe → act → read the change → assert

1. Read before acting: `ui_active_window`, then `ui_window_tree(detail="lite")` or `ui_inspect`. Use the names and paths they return; never invent element names.
2. One purposeful action: `ui_open`, `ui_click`, `ui_set` / `ui_input`, `ui_field`, `ui_table`, `ui_list`, `ui_command`, `ui_dialog`, `ui_form`.
3. Read the result: `ui_window_changes`, `ui_wait` (form, element or closing), `ui_messages`, `ui_errors`.
4. Assert on read values: `ui_get_text`, `ui_find`, table rows from `ui_table` / `ui_list`. A command accepted is not an effect observed.
5. Re-read the window after navigation, a closed form or anything that invalidates the tree; earlier snapshots and `ui_here` pins are stale then.

The first form may still be loading right after the client starts: repeat read-only reads within a bounded wait.

### Forms

- `ui_open(kind=, metadata_name=)` without `form_name` opens and recognises the default form, including one defined in the configuration (`Вид.Объект.Форма.<Имя>`). When the configuration opens another form instead (ZUP: the employee list is a data-processor form), the single new form is accepted and the answer carries `substituted_for`. A failed open lists the forms that did appear. `ui_open(link="e1cib/…", target_title=…)` opens by navigation link.
- `e1cib/data/<Type>.<Name>` without `?ref` opens a new object; the auto-generated object form is `<Type>.<Name>.ФормаОбъекта`, without `.Форма.`.
- `ui_close_form` closes the named form (`form=`, `title=`, `name=`, `form_name=`) or the active non-main window. It never closes the main window and closes nothing when the named form is not found.
- The MCPQAClient extension enables `ui_form_schema`, `qa_data_candidates` and `ui_open` through `ОткрытьФорму`; without it `ui_open` opens forms by navigation link. Installing it is a change of the test infobase (`qa-testclient.md → MCPQAClient extension`).

## Recipes

Before list navigation, field entry, table editing, save/post or dialog actions, read the matching recipe and its pitfalls in [interaction-recipes.md](docs/interaction-recipes.md). Read-only window inspection needs no recipe. Two failed attempts by one method require a fresh window read, then another method or an explicit unverified result; never vary arguments blindly.

## Save and rerun pytest tests

For a recurring workflow or a reproduced regression, look for a matching `test_*.py` in the project's tests first. Rerun or extend that case. If none covers the behaviour, save the verified actions and expected results as a pytest test in the project's version-controlled tests directory. Use observed form and control names. The agent writes the Python file. The `qa-tests` runner in native QA MCP 0.8.0+ executes it through the MCP endpoint, including in CI.

```python
from mcp_qa_testing import expect


def test_currency_list(app):
    form = app.open(kind="catalog", metadata_name="Валюты")
    form.here()
    expect(form.table("Список")).to_exist(timeout=10)
```

For the distribution's `servers/qa-compose.yml`, set `QA_TESTS` to the absolute path of the project's test directory, or put the file in the default `servers/qa-tests/` directory. With the configured QA service and a signed-in TestClient on the authorized dev/test base, run the saved file from the distribution root:

```sh
docker compose --env-file config.env -f servers/qa-compose.yml run --rm qa-tests pytest /tests/test_currency_list.py
```

On later runs, select the file or case that covers the change under `UI_TESTING`. The `app` fixture closes secondary windows before each test, and writes to the test base persist across runs. Use independent test data for scenarios that write. Report the file, the pytest result and any failure artifacts. If the test was only saved, report it as unrun. [QA MCP pytest guide](https://docs.onerpa.ru/mcp-servery-1c/servery/qa#sokhranyonnye-testy-na-pytest)

## Platform behaviour (8.3.27.2130, measured)

Before asserting changed field values, navigating table rows/tabs, writing/posting, deleting, or diagnosing a lost link/message, read the relevant behaviour in [platform-behaviour.md](docs/platform-behaviour.md). Command acceptance never proves the effect; the unknown-outcome rules below always apply.

## Unknown outcome

- A timed-out or interrupted action has an unknown outcome: it may have written data. Never repeat a save, post, delete or command blindly.
- Call `qa_command_status` (`channel="client"` for the extension). In `native` a failed link blocks new calls until `qa_command_status` acknowledges it; then `qa_reconnect(force=True)` and read the window (`ui_window_tree`) before deciding.
- A read that times out is not repeated in a loop either; follow the same path.

## Test journal and verdicts

Keep a journal of every check so that another session can continue it after a crash, a lost link or a context reset. A one-off request to open or show something — no change under check, no data written — needs no journal and no screenshot: answer with what was read.

- Where: the task's output directory; otherwise `%TEMP%\qa-runs\<YYYY-MM-DD>-<short name>\journal.md`. Screenshots go next to it. Give the path in the report.
- Write it as you go, after each step:
  - header: scenario, infobase and its role, executor, test-client port, window mode (visible / hidden), start time;
  - per step: number, tool and key arguments, what was observed, verdict, evidence (tool answer or screenshot path);
  - test data the check created (object kind, number or code, key fields, why), written when created;
  - one state line: active window, open dialogs or unsaved changes, whether the client is alive.
- To continue: read the journal, `qa_status` (`qa_reconnect(force=True)` if the link is gone), read the window, go on from the first step without a verdict. Repeat a data-changing step only when the journal and the data show it did not happen.
- Verdict per step: `passed` / `failed` / `not verified`, each with evidence.
  - Evidence: a value read back, an error text from `ui_errors`, the form name of the window that opened, a message text, a data read through `1c-data-mcp`, or a screenshot — whichever shows the result better.
  - An answer that only confirms the command was sent (`clicked`, `added`, `deleted`, `ok`) is not evidence of its effect. A step without evidence is `not verified`, never `passed`.
- Quote messages and error texts verbatim, in the interface language.
- An unplanned refusal that blocks the next steps: record the step `failed` with the text, mark the rest `not verified`, and stop.
- Expected numbers belong in the scenario; a number the agent calculates goes into the journal with the calculation.
- Reuse test data from earlier runs (see the journal) before creating new. Delete test data only when the person asks.

## Not available in `native`

`qa_setup` and `qa_install_client` answer `executor_capability`. `ui_eval` / `qa_run_script` are replaced by `1c-data-mcp`, `ui_screenshot` and the hidden desktop by the Windows side of `qa-testclient.md`. Do not emulate anything else; report the gap. A tool that is missing from the list is not replaced by `ui_eval` or another workaround.

## Report

Use the scenario and report templates of `content/agents/tester.md`. Name the route (`QA MCP`, executor), the infobase, the journal path, the screenshots by step number, every step whose outcome was not confirmed, and data checks done or not done. Transport success, `/healthz` or a tool list is not a passing check.
