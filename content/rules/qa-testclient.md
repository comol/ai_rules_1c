---
description: "1C test client for QA MCP checks — start and stop (qa-testclient.ps1), visible or hidden window, screenshots, agent-desktop, developer-licence trap, extension safe mode, data confirmation through 1c-data-mcp"
alwaysApply: false
category: tooling
---

# Test client: launch, window, screenshots, data confirmation

**When to load:** with the skill `content/skills/1c-qa-testing/SKILL.md`, before starting or stopping a 1C test client, hiding or showing it, taking a screenshot of it, or confirming what a UI step wrote. Whether a check runs at all is `UI_TESTING` (`dev-standards-env.md`); the driver order is `ui-testing-tools.md`.

These are not QA MCP functions. The server drives forms only. Everything on the Windows machine — starting the test client, the hidden desktop and screenshots in `native`, the MCPQAClient pointer, installing the extension — is done by the agent with the project's tools under this rule: the `qa-testclient.ps1` script of the `1c-qa-testing` skill (`scripts/qa-testclient.ps1`, found by file name in the installed skills folder), PowerShell, a project launcher script, agent-desktop, Designer in batch mode. Do not write a home-grown screenshotter, OCR or window automation.

## Windows scenario (`native`)

Settle two facts once per session:

- **Own shell there:** the agent's shell runs on the Windows machine of the test client (the usual local setup: Docker Desktop and 1C on the same PC).
- **agent-desktop:** its tools are exposed and `TOOL_AGENT_DESKTOP` is not `off`.

| Scenario | Start and stop | Hidden window | Screenshot |
|---|---|---|---|
| **A.** Own shell + agent-desktop | `qa-testclient.ps1` | `start -Hidden` | `qa-testclient.ps1 capture`; agent-desktop for windows outside the client |
| **B.** Own shell, no agent-desktop | `qa-testclient.ps1` | `start -Hidden` | `qa-testclient.ps1 capture` |
| **C.** agent-desktop only (the agent works elsewhere) | Launch the client executable with `desktop_launch` and separate arguments; hand off any step that needs a shell | none: agent-desktop sees only the visible desktop | `desktop_screenshot` targeting the visible client window or its display (see the maximised 8.5 caveat below) |
| **D.** Neither | the person, with the command line the agent gives | none | the person on request; otherwise the visual check is reported not done |

`platform` executor: `qa_start` starts the client itself, `qa_start(hidden_desktop=True)` hides it, `ui_screenshot` takes screenshots; connection string and password come from a profile (`qa_profiles`), never from the chat.

## `qa-testclient.ps1`

PowerShell 5.1 (`powershell`) and PowerShell 7 (`pwsh`), `-NoProfile -ExecutionPolicy Bypass -File <path>\qa-testclient.ps1 …`. On 7, `-ReferencedAssemblies` replaces the default compiler references, so the script compiles its helper from all reference assemblies in `$PSHome\ref`, `System.Drawing.Common` and the available `System.Private.Windows.*` assemblies in `$PSHome` (falling back to the reference folder or Windows Desktop shared framework for `System.Drawing.Common`). A `System.Drawing` facade alone is insufficient.

```
qa-testclient.ps1 start -Base "<file infobase>" | -Server "<server>\<infobase>" [-User <name>] [-PasswordEnv <VAR>] [-Hidden] [-Execute <file.epf>] [-MaxSeconds <n>] [-Port 1538] [-Version <x.y.z.b>]
qa-testclient.ps1 capture [-Port 1538] [-Out <file.png>]
qa-testclient.ps1 stop [-Port 1538] [-CloseTimeoutSec 60] [-Force]
qa-testclient.ps1 status [-Port 1538]
```

- It prints one JSON object; an `error` field and exit code 1 mean failure. State and logs live in `%LOCALAPPDATA%\mcp_qa_testclient\` (`<port>.json`, `<port>.log`).
- Parameters come from `.dev.env`: `INFOBASE_KIND` + `INFOBASE_PATH` → `-Base` (file) or `-Server` (server); `IB_USER` → `-User`; `PLATFORM_PATH` → `-Version` = its version folder (the newest installed platform otherwise). The password is read from the environment variable named by `-PasswordEnv`: load `IB_PASSWORD` into that variable in the launching shell, never type it into the chat or the command line; omit `-PasswordEnv` for an empty password.
- `start` waits until the main window opens; the port opens earlier, before the licence and sign-in checks. A client that exits during start-up returns 1C's own message from the log: report it, do not retry in a loop. No main window before the timeout means a start-up dialog is waiting — `capture` shows it, then `stop`.
- `-Execute <file.epf>` appends `/Execute` for that file on the same client (the same pid, hidden desktop, deadline and `stop`). The file must already exist. A missing file is an error before the client starts.
- `-MaxSeconds <n>` closes the client `n` seconds after launch even if the agent does not come back, and ends the process if it does not close by itself; use it when the project bounds test sessions, and never extend a deadline through relaunch loops.
- `capture` saves a PNG of the client's own windows and popups only, on the hidden desktop too, and also for a client the person started (found by port). The port listens before the main window exists: a capture right after the port opens finds no windows. On 8.5 a maximised client painted through `PrintWindow` hangs (a core busy, the test link dead until `stop -Force`; measured on 8.5.1.1522): `capture` restores such windows for the shot and maximises them again (`maximized_restored_for_capture`). Do not shoot a maximised 8.5 client window with other PrintWindow-based tools; use an authorized display capture (`agent-desktop screenshot --screen N`) instead of requesting a window capture in this case.
- `stop` closes only a client this script started, through its main window, and refuses a client the person started. It waits `-CloseTimeoutSec` for the process to exit and answers `how: closed` with `port_free`. While it waits it clicks a window whose text is «Завершить работу» when the exit question «Завершить работу с программой?» is open, including on the hidden desktop. If that question is visible but the button is not a window the script can click, the answer is `how: exit question`. If a new owned `V8TopLevelFrameSDIsec` dialog appears after the close request but its text and buttons are not exposed as windows, `stop` immediately returns `how: exit question` and preserves the process and state. This structural signal does not identify the dialog text: connect to that same client with `qa_start`, inspect `ui_dialog`, and answer only the confirmed exit question; never send Enter to an unknown dialog. A client that has not closed and has neither signal answers `how: still closing`. In both cases there is an `error`: `capture`, then `stop` again. `-Force` ends the process; use it only when the person agrees (licence trap below).
- `status` answers `started_here: true` only while that client is alive. A client the person closed, or one that exited, is forgotten with its deadline watchdog and reported once as `gone`. A closed client can take over a minute to exit (seen on a large configuration): `alive` or a refused `start` right after closing means "wait and ask `status` again", not a conflict.

## Starting and connecting

- Start a test client only for an infobase whose `INFOBASE_ROLE` is `dev` or `test`, or that the person confirmed as a test copy; otherwise ask once and wait. Never switch infobases silently.
- If the port already listens, run `status` first. A client of the same infobase on that port is connected to with `qa_start`; a client of another base, or one owned by another agent, is a conflict to resolve — never close it.
- Start with the project launcher if there is one, else `qa-testclient.ps1 start` (A, B), or this command line (C: pass the absolute executable path and individual launch arguments via agent-desktop, D: give the command to the person):

  ```
  1cv8c ENTERPRISE /F"<infobase path>" /TestClient -TPort1538 /DisableStartupDialogs
  ```

  Add `/N<user>` only when the infobase needs it; the person types the password themselves. A web client under test: `…/<base>/?TestClient&TestClientID=<id>` with the same id in the server's `MCP_QA_TESTCLIENT_ID`.
- Then `qa_start` (skill `1c-qa-testing`).
- Close only a client you started: `qa_stop`, then `qa-testclient.ps1 stop`, or leave it to its `-MaxSeconds` deadline. Leave a client the person started running.
- **Never kill a client by force** (`Stop-Process`, `taskkill`). Under the 1C developer licence a killed client keeps its place in the client count of a file infobase while another process holds the base open — for example the IIS application pool of its web publication — and further clients exit with «Превышено ограничение лицензии для разработчиков на количество клиентов информационной базы». Restarting that process frees the place, only with the person's consent. One test client per infobase at a time unless the licence allows more.

## Visible or hidden window

`MCP_QA_CLIENT_VISIBLE` in `.dev.env` sets the window of a client the agent starts (canon: `dev-standards-env.md`). Default: visible. Only `false`, `0`, `no` or `off` hides it; missing, empty or invalid values mean visible. `/uitests visible|hidden` switches it. Read it before every launch; never change it to suit the agent.

- **Visible:** `start` without `-Hidden`; `platform`: `qa_start(hidden_desktop=False)`.
- **Hidden:** `start -Hidden` (A, B) — the client runs on a separate hidden desktop; `platform`: `qa_start(hidden_desktop=True)`. In C and D there is no hidden launch: start visible and say so once.
- A step that needs agent-desktop (a window outside the testing model) runs with a visible client.

Windows cannot move a window between desktops. **The client becomes visible** by restarting it visible:

- **The person asks to show it** ("покажи", "хочу посмотреть", "сам покликаю"): warn that open forms and unsaved input are lost, then `qa_stop`, `stop`, `start` without `-Hidden`, `qa_start`, and bring the client back to the form in question by navigation link. Continue in observation mode.
- **An error while hidden** — a 1C error window, an unexpected refusal, a failed assertion or a lost link:
  1. Keep the evidence first: `capture` to the journal folder, `ui_errors` / `ui_messages`, the journal entry. Do not close dialogs or retry anything before that.
  2. Restart the client visible as above and open the form where the error happened. Never repeat a data-changing step to reproduce the error; the screenshot shows the original state.
  3. Leave the visible client open for the person (observation mode) and say what was lost by the restart.
  A client that exited or failed to start cannot be shown: report 1C's message and the log. A project rule that forbids relaunches (a bounded benchmark, a deadline) wins: then keep the screenshot and report.
- Never switch the person's screen to the hidden desktop (`SwitchDesktop`) and never move windows between desktops.

## Observation mode

When the person wants to watch or click themselves:

- Start the client visible. A deadline meant for unattended runs is too short to watch: ask how long to keep the client and pass that as `-MaxSeconds`; when asking is not possible, keep it for 30 minutes (`-MaxSeconds 1800`) and say so.
- Bring the form to the requested state and stop. Do not close forms or the client; say which form is open and in what state. Close them only when the person says so.
- The person's clicks do not break the link. Before continuing, read the window again: earlier snapshots and `ui_here` pins are stale.
- Do not send agent-desktop input while the person works in the client.

## Screenshots

- Observe and assert through structured reads (`ui_window_tree`, `ui_inspect`, `ui_get_text`). A screenshot is for layout questions (overlaps, clipped text) and as evidence of key states — form opened, data entered, save or posting, error, completion — never after every action and never as the observe loop.
- Take it by the scenario: `qa-testclient.ps1 capture -Out <journal folder>\<step>.png` (A, B), agent-desktop (C, and in A for windows outside the client), the person (D), `ui_screenshot` (`platform`). When none is possible, the report says the visual check was not done.
- Save screenshots next to the journal and reference them by step number. Look at the PNG with the agent's image viewer when there is one.
- A task that asks for a screenshot needs a real one of the updated infobase — a client capture, or a web-client screenshot through the browser driver. Structured results, SVG, HTML or mock images do not replace it.

## agent-desktop

Windows outside the testing model — platform error dialogs it does not reach, OS and file dialogs, other applications — are handled with agent-desktop (A, C), on the visible desktop only. In B and D such a step is reported not done. A platform security warning is handed to the person. Follow the user's desktop-session consent policy before observing or acting.

- On Windows, select the intended window with `desktop_list_windows` and inspect it with `desktop_snapshot`. For supported controls, use semantic actions on fresh refs. Re-snapshot after an action to verify its result. Coordinate any physical input with the person and check the foreground target before sending it.
- Capture the authorized window by ID. A display screenshot also captures other visible content; use it only when the requested evidence requires it. For the hidden test desktop use `qa-testclient.ps1 capture`.
- QA MCP remains responsible for thin-client forms. Use the host's shell for command output and exit status. Agent Desktop's launch tool starts an executable and reports the process.

## MCPQAClient extension

- Needed for `ui_form_schema`, `qa_data_candidates` and `ui_open` through `ОткрытьФорму`; install it only in a test copy: `qa_install_client` (`platform`) or Designer in batch mode (`native`, `content/rules/designer-batch-checks.md`), then turn off its safe mode (next section).
- `native`: after each `qa_start`, write `client_hook.pointer` from its answer into `%TEMP%\mcp_qa_client_spool.txt` on the test-client machine. The extension re-reads it every 5 s; `qa_status` then shows `client_hook.available: true`.

## Extensions under test: safe mode

Any extension loaded from sources (`LoadConfigFromFiles … -Extension`, `db-load-xml` / `db-load-git -Extension`) comes up in safe mode. In safe mode the platform refuses its interception of object modules **silently**: the check runs the base code and passes or fails for the wrong reason; only the event log names the cause («…подключено в безопасном режиме»). Before checking an extension that intercepts object or manager modules, read its properties with the `db-cfe-admin` tool (`list`) and turn safe mode off on the test copy (`set-properties -Name <extension> -SafeMode off`; `content/skills/1c-metadata-manage/docs/db-manage.md`). The change goes through `ibcmd` and needs exclusive access to the base: close clients and stop its web publication first. Every reload from sources resets it — check again.

## Confirming data through 1c-data-mcp

A UI step that writes data — a record created, a document posted, register movements, balances — is confirmed through `1c-data-mcp` when the result matters to the check and the form does not show it. `ui_eval` and `qa_run_script` are unavailable in `native`; their jobs go here, under `content/skills/1c-live-ib/SKILL.md` and its Safety section:

- `vcvalidatequery`, then `vcexecutequery` — read-only. Find objects the check created by a marker the check entered itself (a comment, a code), since queries take no parameters.
- A value computed on the server: a read-only `vcexecutecode` fragment.
- After a failing or refused step: `vcloggetlasterror`. Its limits go into the report: only the most recent error of 24 hours, not filtered by session.
- Preparing or cleaning test data through `1c-data-mcp` changes the base: only with the person's explicit consent and never on `INFOBASE_ROLE=prod`.
- Check first that `1c-data-mcp` is published on the same infobase the test client opened; otherwise its answer proves nothing about the UI step. It sees written data only — no open forms, no unsaved input.
- Without `1c-data-mcp` (or with `TOOL_DATA=off`) check the data through the UI where it is visible, or report the data check not done.
