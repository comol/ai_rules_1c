---
description: Install Vercel Labs agent-desktop and register its local stdio MCP server for native desktop automation
userOnly: true
---

# /install-agent-desktop — Vercel Labs desktop automation

Install on the machine whose desktop the agent will operate. QA MCP drives 1C thin-client forms. Use agent-browser for web pages and agent-desktop for native windows and dialogs. Keep the project's `UI_TESTING` and tool policies in effect.

## Install the CLI

1. Inspect the active client's configuration and look for an existing executable. Run `agent-desktop --version` if present. Reuse a working installation.
2. For a selected installation with Node.js and npm, run `npm install --global agent-desktop`. A matching native archive from [official releases](https://github.com/vercel-labs/agent-desktop/releases) also works. Keep any platform helpers beside the executable.
3. Windows uses UI Automation in the signed-in user's interactive desktop. On Linux use the signed-in user's graphical session and its AT-SPI accessibility bus. An SSH-only host or headless container can expose the MCP tool catalog without having access to a desktop. Review the [Windows](https://agent-browser.dev/desktop/platforms/windows) or [Linux](https://agent-browser.dev/desktop/platforms/linux) platform guide for prerequisites and capture limits.

## Register MCP

Merge the `agent-desktop` stdio entry into the selected client and scope. Keep other servers and their settings. When replacing a previous desktop server, remove its registration in that scope once the new entry passes the protocol check. Preserve any explicit tool-policy choice during the migration.

Use the executable name on a host that can resolve it. For a Windows client that starts native processes directly or has a different PATH, set `command` to the absolute native executable from the release or npm package. For npm, find the global package root with `npm root -g` and select the host architecture's executable from `agent-desktop/bin/` (for example `agent-desktop-win32-x64.exe`). Keep the server argument as a separate string.

JSON clients with `mcpServers`:

```json
{"mcpServers":{"agent-desktop":{"command":"agent-desktop","args":["mcp"]}}}
```

Codex:

```toml
[mcp_servers.agent-desktop]
command = "agent-desktop"
args = ["mcp"]
```

OpenCode:

```json
{"mcp":{"agent-desktop":{"type":"local","command":["agent-desktop","mcp"],"enabled":true}}}
```

Use the active client's supported config shape for other agents. Each MCP client starts the executable on demand. The default uses semantic actions. Configure headed physical input only when the requested workflow and the user's consent permit it.

## Verify

- Verify the actual executable with `--version`. Reload the client's MCP configuration or reconnect as needed.
- Use MCP initialization and `tools/list` to confirm `desktop_list_windows`, `desktop_snapshot`, and `desktop_screenshot` are registered. This verifies the connection. Checking actual window access starts a Computer Use session and follows the user's separate consent rules.
- Report the actual version, client, config scope and verification result. For shell commands with output and exit status, use the host's terminal.

[Upstream MCP guide](https://agent-browser.dev/desktop/guides/mcp)
