---
description: Detect and optionally install the supported 1C development tools through one guided menu
userOnly: true
---

# /installtools — guided tool installation

Use this command after installing the rules, and again after an update announces new tool installers. It detects the supported tools, explains what each one is for, asks one compact selection question, and then runs the corresponding standalone installer procedures.

This command is an orchestrator. Do not duplicate installation steps here and do not silently install anything.

## Tool catalog and order

Always show tools in this order. The 1C MCP bundle is always first.

| # | Tool | Purpose | Recommend when | Standalone command |
|---|---|---|---|---|
| 1 | 1C MCP server bundle | Documentation, metadata and code search, syntax checks, templates/project memory, BSP search, graph analysis and code review | Recommended for every 1C project; this is the primary ruleset tool bundle and requires a purchased distribution | `/installmcp` (`/installmcp beta` for the beta image channel) |
| 2 | Cognee memory MCP | Persistent agent memory; primary write destination whenever connected | Recommended when the user wants general cross-session memory; optional to install | `/install-cognee` |
| 3 | OpenViking memory MCP | Persistent agent memory and context retrieval; searched alongside Cognee and other connected memory providers | Recommended when the user wants OpenViking context retrieval or a primary memory store without Cognee | `/install-openviking` |
| 4 | EDT-MCP | Live access to the EDT workspace, errors, native refactoring, metadata/forms, launches and debugging | Recommended only when the user develops in a locally installed 1C:EDT | `/install-edt-mcp` |
| 5 | agent-browser | Token-efficient browser automation based on accessibility snapshots | Recommended for automated tests of a published 1C web client | `/install-agent-browser` |
| 6 | Windows-MCP | Windows desktop, mouse and keyboard automation | Last resort for thick-client or other non-web UI flows | `/install-windows-mcp` |
| 7 | rtk | Third-party, user-global shell-output compression proxy — fewer tokens on every shell call (git, docker, platform commands) | Optional; only on explicit selection — also offered by `/economymode` | `/install-rtk` |
| 8 | Atlassian MCP | Access to Jira issues and Confluence pages in Cloud or Server/Data Center | Optional for projects using Jira or Confluence | `/install-atlassian-mcp` |
| 9 | OfficeCLI | Create, read and edit Word, Excel and PowerPoint files without Microsoft Office | Optional; recommended when the workflow includes `.docx`, `.xlsx` or `.pptx` documents | `/install-officecli` |

Do not list an optional tool as required merely because its installer exists.

Memory routing follows `content/rules/project-memory.md`, after `TOOL_*` policy (`content/rules/mcp-policy.md → Tool availability`). Installation, policy and runtime capability are separate: installing a provider neither enables it nor proves its tools callable.

## Steps

### 1. Read-only detection

Inspect the active client and host without changing state. Classify each tool as `installed`, `not installed`, or `uncertain`; show its `auto / off / required` policy and session capability separately. Explicit status/install requests allow read-only detection even for `off`; never recommend/preselect those tools or rewrite policy as a side effect. The MCP bundle has separate provider keys, so preserve mixed settings.

Read `USE_EDT` from the project `.dev.env` before evaluating EDT tools. It is a project preference, not an installation probe:

- `true` — the project uses EDT; mark EDT-MCP as recommended.
- `false` — the project does not use EDT; keep EDT-MCP visible but do not recommend or preselect it.
- missing, empty or invalid — in the normal interactive command, ask once whether the project uses EDT and persist `USE_EDT=true|false` without changing any other `.dev.env` key. In `/installtools status`, report `USE_EDT: unknown` and do not ask or write.

- **1C MCP bundle:** check the current tool schema for known 1C MCP tools; then check client MCP configuration, `BASESAI_MCP_GLOBAL_ROOT` / `MCP_GLOBAL_ROOT` plus `install.manifest.json`, and relevant Docker containers. A ruleset-generated MCP config alone does not prove the purchased servers are installed or running.
- **Cognee:** check for exposed Cognee memory tools, a `cognee` / `cognee-memory` MCP entry, a `cognee-mcp` container, and the configured health endpoint (the standalone command defaults to `http://127.0.0.1:8010/health`).
- **OpenViking:** check for exposed OpenViking memory tools and an `openviking` MCP entry; inspect the configured installation manifest, `openviking-server --version` when already installed, and the configured health endpoint (default `http://127.0.0.1:1933/health`). For Docker inspect the existing container; for a remote endpoint do not require a local package/container. A healthy HTTP process alone does not verify model access or MCP memory operations. Do not install packages or start the service during detection.
- **EDT-MCP:** check for an `edt-mcp` / `EDT MCP Server` client entry and `http://127.0.0.1:8765/health`. A stopped EDT makes health inconclusive; do not report the plugin missing solely because EDT is closed.
- **agent-browser:** check `agent-browser --version` and the client MCP entry.
- **Windows-MCP:** on Windows, inspect the client MCP entry and exposed tools; do not use `uvx windows-mcp --help` for detection because it may install/run the package. On non-Windows, mark it `not applicable`.
- **rtk:** check `rtk --version` and `rtk init --show` (user-global; nothing in the project or in `.dev.env`).
- **Atlassian MCP:** inspect the active client's configuration for `mcp-atlassian` or another entry running the same server, and exposed Jira / Confluence tools. Check the configured local executable or Docker image without starting it; remote connections do not require a local package. Configuration alone does not prove service access. Do not run `uvx mcp-atlassian --help`, pull images, or request credentials during detection.
- **OfficeCLI:** follow the read-only detection in `content/commands/install-officecli.md` (the `status` path): resolve the executable, then probe `officecli --version` with temporary `OFFICECLI_SKIP_UPDATE=1`. Check its native install location if it is missing from `PATH`; never run bare `officecli` or `officecli install` during detection. CLI availability and installed agent skills are separate states; no MCP entry is required.

Never expose secrets found in MCP configuration or environment files.

For `/installtools status`, report these states and stop here: no questions, policy writes or installation steps.

### 2. Show the compact menu

Show all tools from the catalog with status, the one-line purpose, recommendation, and standalone command. Keep the MCP bundle first even when it is already installed. Distinguish memory tools that are connected now from installed providers awaiting startup or client restart. For tools without a `TOOL_*` setting (including Atlassian MCP and OfficeCLI), show policy as `not configured` rather than inventing a key.

If the 1C MCP bundle is not clearly installed and at least one of its providers is permitted, ask first:

> Have you purchased the 1C MCP server bundle, and should I install it now with `/installmcp`?

If the user has not purchased it, provide the product page `https://vibecoding1c.ru/mcp_server` (download after login is `https://vibecoding1c.ru/mcpserver`) and continue with the optional tools. Do not ask for Tilda credentials unless the user selected the MCP bundle.

Then ask one consolidated question for remaining permitted `not installed` or `uncertain` tools (`off` only on explicit selection):

> Which additional tools should I install? Reply with numbers, `recommended`, `all`, or `none`. Each selected installer may ask only for settings it actually needs.

Treat `recommended` contextually:

- Cognee: select only if the user wants general memory beyond `1c-templates-mcp` project memory.
- OpenViking: select when the user requests OpenViking or its context retrieval. Do not infer a request to install both memory servers from a request for general memory alone.
- EDT-MCP: select when `USE_EDT=true`. If the flag is `false`, select only on an explicit numbered choice; a detected local EDT installation alone does not change the project preference.
- agent-browser: select when a published web-client URL or web UI testing is expected.
- Windows-MCP: never include automatically; it requires an explicit selection.
- rtk: never include automatically; it requires an explicit selection.
- Atlassian MCP: select when the user wants the agent to work with Jira or Confluence. Do not infer this from Git hosting or the presence of an installer alone.
- OfficeCLI: select when the user needs to create, read or edit Office documents; do not preselect it for a purely BSL/metadata workflow.

### 3. Run selected standalone procedures

Execute selected installers sequentially in catalog order by loading and following their command files:

1. `installmcp.md`
2. `install-cognee.md`
3. `install-openviking.md`
4. `install-edt-mcp.md`
5. `install-agent-browser.md`
6. `install-windows-mcp.md`
7. `install-rtk.md`
8. `install-atlassian-mcp.md`
9. `install-officecli.md`

If a slash-command dispatcher cannot invoke another slash command directly, execute that command file as the procedure. Do not tell the user to repeat the same selection manually.

Skip tools already proven installed unless the user explicitly requests repair or reinstall. When installed MCP servers or memory need connecting to this repository, route that selected setup to `content/commands/setupmcp.md`; collect actual endpoints without reinstalling services. For Atlassian MCP, use `content/commands/install-atlassian-mcp.md` to reuse the existing runtime and configure the selected account/services. For an installed 1C MCP bundle, offer `/updatemcp` only when an update is requested; do not replace it with `/installmcp`.

**MCP release channel.** The bundle installs the **stable** image channel by default. Pass the channel through only when the user asks for it — `/installmcp beta` for a fresh beta install, `/updatemcp beta` / `/updatemcp stable` to switch an installed set. Do not raise the beta option on your own, and never select it for the user; the contract is `/installmcp` → `## Release channel — stable or beta (IMAGE_TAG)`.

Stop only the failing installer, report its blocker, and continue with other independently selected tools when safe.

### 4. Report and restart

Return one line per tool: `installed`, `already present`, `configured; awaiting restart/credentials`, `skipped`, or `failed: <reason>`. Mention the standalone command for later use. Do not report a prepared package as a verified service connection.

When MCP configuration, EDT plugins, or client-side tools changed, ask for one restart at the end rather than after every item. EDT-MCP additionally requires a full EDT restart.

When `USE_EDT` ends the run as `true`, state in one line that the EDT branch of the ruleset is active (`content/rules/edt-workflow.md`) — source-format check before metadata work, EDT-MCP routing, one deployment owner. When it ends as `false`, say nothing about EDT.

## Parameters

- `/installtools` — detect, show the menu, and ask what to install.
- `/installtools recommended` — ask about the MCP bundle when its policy permits, then preselect permitted, contextually recommended optional tools.
- `/installtools status` — detection and descriptions only; do not install.
