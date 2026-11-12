---
description: UI testing routes — QA MCP (`1c-qa`) first, web client (agent-browser → built-in browser) as fallback, agent-desktop only for windows outside the client; bans home-grown screenshot/OCR
alwaysApply: false
category: tooling
---

# UI testing tools — QA MCP, browser and desktop automation

**When to load this file:** before any UI check of a 1C infobase (`1c-tester`, `/deploy-and-test` Step 4, behavioural confirmation under `UI_TESTING`, ad-hoc checks), or when choosing / installing a UI-automation tool.

Whether a UI check runs at all is gated by `UI_TESTING` — canon: `dev-standards-env.md → "UI_TESTING — UI-testing mode"`. This file answers **which route** drives the check once it is allowed, and the **mandatory preflight** before the first browser action.

## Route order (hard)

1. **QA MCP (`1c-qa`)** — the main route for checks in the 1C interface. It drives the thin client's forms through the platform testing model and reads structured state. With `TOOL_QA` enabled, interactive checks use the session's `qa_*` / `ui_*` tools and saved pytest tests use the runner below. Both need the project infobase (`INFOBASE_PATH`, `INFOBASE_ROLE`). Load `content/skills/1c-qa-testing/SKILL.md` and `content/rules/qa-testclient.md` (starting the test client, visible / hidden window, screenshots, data confirmation).
2. **Web client** — the fallback when QA MCP is absent, disabled, cannot connect or cannot cover a step, and the primary route for web-client-specific behaviour or a requested web screenshot. Needs `INFOBASE_PUBLISH_URL`; runs the preflight and driver order below, then `web-client-driving.md`.
3. **agent-desktop** — windows outside the testing model (OS and file dialogs, platform error windows the test client does not reach, other applications) under the cautions of `qa-testclient.md → agent-desktop`. Use QA MCP for thin-client forms and agent-browser for web pages.

State the chosen route, and the reason for a fallback, once in the report. `TOOL_QA=required` with the server missing or failing blocks the check; the web client does not satisfy it. A route that cannot run leaves its scenarios unverified; never report them passed.

## Saved regression suites

Reuse saved tests when they cover the behaviour being checked. Run them under `UI_TESTING` on the authorized dev/test target.

- **1C thin client:** native QA MCP 0.8.0+ runs saved pytest files through `qa-tests` under `TOOL_QA`. For authoring, test directory and rerun commands, see `content/skills/1c-qa-testing/SKILL.md → Save and rerun pytest tests`.
- **Web client:** `content/skills/1c-ui-regression/SKILL.md` covers saved suites with a verified project runner such as Playwright Test. `TOOL_BROWSER=off` disables this route, and `required` needs a working runner. A saved browser suite can execute without an agent-browser installation. Interactive web exploration and debugging follow the preflight and driver order below. Use observed stable locators and the interaction rules in `web-client-driving.md`.

## Preflight before web UI tests (hard gate)

Runs before an authorized interactive web UI test, once the web route is selected (saved suites use the preceding section). First apply `TOOL_AGENT_BROWSER` and `TOOL_BROWSER` (`content/rules/tool-policy.md`). In `auto`, use the preflight below. With `TOOL_AGENT_BROWSER=off`, skip its probes/install question and select an eligible built-in browser. With `required`, a missing agent-browser blocks execution. If no permitted web driver works, report the web test unrun; do not substitute desktop automation for a web scenario. A selected built-in driver's `required` failure also blocks the test.

1. **Detect `agent-browser`.** Available if **either**:
   - CLI on `PATH` (`agent-browser --version` succeeds), **or**
   - its MCP tools are callable in the current session (e.g. `agent_browser_open`, `agent_browser_snapshot`).
2. **If available** — proceed with preference order below. No prompt.
3. **If missing — stop before any browser action** and ask the user in Russian (one message, do not bury it in prose):

   > Для веб-тестов 1С рекомендую поставить `agent-browser` — браузер для агентов со снимками accessibility-дерева, сильно экономит токены по сравнению со скриншотами / vision. Установить сейчас через `/install-agent-browser`?  
   > - **да** — установлю и продолжу тесты  
   > - **нет** — продолжу на встроенном browser MCP (дороже по токенам)

4. **On «да» / yes / «установи»** — execute `/install-agent-browser` (`content/commands/install-agent-browser.md`) fully, then continue UI tests with `agent-browser` (after client restart if MCP tools are still missing — tell the user once and pause until they confirm restart, or fall back only if they refuse to restart and explicitly allow the built-in browser).
5. **On «нет» / no / decline** — continue with an eligible built-in browser; otherwise report the test unrun. Do not ask again in the same session unless the user starts a new UI-test request.
6. **Autonomous / batch / no operator** — do not auto-install. Use an eligible built-in browser and state the fallback once; if none exists, report the test unrun. Never invent a screenshotter/OCR stack.

This gate does **not** change `UI_TESTING` or `INFOBASE_PUBLISH_URL`. It only ensures the cheap driver is offered before an expensive run.

Once a driver is chosen, load `web-client-driving.md` before the first action — it owns how the 1C web client itself behaves (snapshot reading, lists / trees / grids, reports, dialogs, anti-loop limits), independently of which driver won the preference order above.

## Web driver order (hard)

1. **`agent-browser`** (https://github.com/vercel-labs/agent-browser) — **default for 1C web client tests**. Use accessibility-tree snapshots (`snapshot` / MCP equivalents), refs (`@eN`), and typed interactions. Screenshots only for evidence in the test report, not as the primary observe loop. Run it headed (`--headed`) for the 1C web client (`web-client-driving.md → 1`). Install: `/install-agent-browser`.
2. **Built-in browser MCP** of the active client (`cursor-ide-browser`, Playwright / `browser-use`, etc.) — eligible fallback after the preflight above (agent-browser disabled, declined, or absent with no operator). Same interaction rules — `web-client-driving.md → 5. Filling fields`.

Never invent a parallel stack (PowerShell screenshot loops, custom OCR, ad-hoc vision pipelines) while a tool from this list can cover the need.

## agent-browser MCP wrapper and CLI

Observed failure mode (agent-browser 0.37.1, MCP `core` profile, 1C web client, twice in independent sessions): every MCP call returned nothing until the client's timeout (`no response or progress for 1800s`) while Chrome was alive and the page had loaded. The cause was a JavaScript `confirm` raised by the page (`web-client-driving.md → Pitfalls measured on a live publication`). The CLI named the pending dialog at once; the `core` profile has no dialog tool — those are in the `tabs` profile, and whether `agent-browser mcp --tools core,tabs` avoids the hang is unverified.

Workaround that held: drive the run through the CLI binary with the shell's own timeout per call — `agent-browser dialog status`, `agent-browser dialog accept` clear the page; on a shared host use your own `--namespace`. Take CLI syntax from the version-matched `agent-browser skills get core`, not from MCP argument names: the `screenshot` path is positional (`--path` fails with `Element not found: --path`), and `find` has no double-click action. In Windows PowerShell 5.1 call the binary directly (`& agent-browser eval $js`) — `Start-Process -ArgumentList` re-splits arguments with spaces and the JavaScript arrives cut. The CLI's stderr shows up as `NativeCommandError` records: that is its message, often the useful one, not a crash — judge by `$LASTEXITCODE` and do not add `2>&1`.

## Token discipline

- Prefer **structured snapshots** (a11y tree / DOM refs) over images. Vision on full-page screenshots is the expensive path that `agent-browser` exists to avoid.
- Re-snapshot after navigation or DOM-changing actions; do not reuse stale refs.
- Keep MCP tool profiles small (`agent-browser mcp` default `core` profile). Escalate to `--tools all` only when a missing tool blocks the scenario.
- `UI_TESTING` decides whether a run happens — do not "warm up" a browser or start a test client outside an allowed run.
- QA MCP answers are already structured: read the window tree (`detail="lite"`) instead of screenshots, and screenshot key states only (`qa-testclient.md → Screenshots`).

## agent-desktop — when and when not

| Use agent-desktop | Do not use agent-desktop |
|---|---|
| OS, file and platform error dialogs outside the testing model (the web client's native file dialog may be invisible to it: `web-client-driving.md → Login as another user, file choice`) | Driving 1C forms — QA MCP does that, and the thin client exposes no controls to UI Automation |
| Native applications on the target desktop | Routine checks of the **web** client at `INFOBASE_PUBLISH_URL` |
| User explicitly requires desktop automation | "Because screenshots feel easier", or as a substitute for publishing the web client |

Apply `TOOL_AGENT_DESKTOP` before using Vercel Labs agent-desktop. Follow the user's Computer Use consent policy before observing a window, taking a screenshot or sending input. Use the MCP tools or the installed CLI in the authorized desktop session. Select the intended window, take a structured snapshot, act on a ref from that snapshot, and verify the resulting state. Prefer headless semantic actions; physical input can take focus and requires headed mode. Capture the requested window or display only. Use the host shell for commands that need output and exit status. See the [platform guides](https://agent-browser.dev/desktop) for Windows UI Automation and Linux AT-SPI session requirements.

## Install commands

| Need | Command |
|---|---|
| UI checks in the thin client | QA MCP: Docker image `comol/qa_mcp` from the MCP server distribution, client connection `1c-qa`; the ruleset's MCP installers do not set it up yet |
| Web UI testing, token-efficient browser | `/install-agent-browser` |
| Native desktop automation | `/install-agent-desktop` |

Installing a tool does not change `UI_TESTING` or `TOOL_*` and does not set `INFOBASE_PUBLISH_URL`.

## Interaction rules (web tools)

Owner — `web-client-driving.md` (headed run, typing and its paste fallback, TAB, waits, anti-loop limit). Screenshots of key states (open, filled, saved / posted, errors) are report evidence, not the observe loop.
