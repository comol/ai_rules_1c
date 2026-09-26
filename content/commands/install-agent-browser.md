---
description: Install agent-browser (token-efficient headless browser CLI + MCP) for 1C web UI testing
userOnly: true
---

# /install-agent-browser — install token-efficient browser automation

Installs [agent-browser](https://github.com/vercel-labs/agent-browser) (Vercel Labs): a headless Chromium CLI with accessibility-tree snapshots. Preferred tool for 1C **web** UI testing — snapshots cost far fewer tokens than screenshot / vision loops (`cursor-ide-browser`, Playwright MCP, custom screenshot+OCR).

Policy and fallback order — `content/rules/ui-testing-tools.md`. Shell on Windows — `powershell-windows` skill.

This command does **not** install 1C MCP servers (use `/installmcp`) and does **not** enable UI testing by itself (`UI_TESTING` / `INFOBASE_PUBLISH_URL` stay as in `.dev.env`).

## Steps

### 1. Prerequisites

1. Confirm Node.js / npm are on `PATH`:

   ```powershell
   node --version
   npm --version
   ```

   If either fails — stop and ask the user to install Node.js LTS (https://nodejs.org/), then re-run. Do not invent a Node path.

2. Prefer a global install (shared across projects). If the user asks for a project-local pin — use `npm install agent-browser` in the project root instead of `-g`, then invoke via `npx agent-browser`.

### 2. Install the CLI and Chrome for Testing

```powershell
npm install -g agent-browser
if ($LASTEXITCODE -ne 0) { throw "npm install -g agent-browser failed" }
agent-browser install
if ($LASTEXITCODE -ne 0) { throw "agent-browser install (Chrome for Testing) failed" }
agent-browser --version
agent-browser doctor
```

On Linux only, if `doctor` reports missing system libraries:

```bash
agent-browser install --with-deps
```

### 3. Optional — coding-assistant skill stub

Offer once (default = yes if the user does not care):

```powershell
npx skills add vercel-labs/agent-browser
```

This adds a thin discovery stub that loads live skill content via `agent-browser skills get …` (stays in sync with the CLI). Skip if `npx` is unavailable or the user declines. Do **not** copy `SKILL.md` from `node_modules`.

### 4. Register the MCP server in the active client

Merge an `agent-browser` stdio entry into the active tool's MCP config. **Do not overwrite** existing servers (especially 1C catalog entries). Detect the client the same way `/doctor` / `/installmcp` Step 7 do.

| Client | Config path | Shape |
|---|---|---|
| Cursor | `.cursor/mcp.json` (prefer project) or `%USERPROFILE%\.cursor\mcp.json` | `mcpServers` |
| Claude Code | `.mcp.json` (project) or `~/.claude/mcp.json` | `mcpServers` |
| Command Code | `.mcp.json` (project) | `mcpServers` |
| Codex CLI | `.codex/config.toml` or `~/.codex/config.toml` | `[mcp_servers.<id>]` |
| OpenCode | `opencode.json` (project root) | top-level `mcp` |
| Qwen Code | `.qwen/settings.json` | `mcpServers` |
| Kimi Code CLI | `.kimi-code/mcp.json` | `mcpServers` |
| Cline | global Cline MCP settings only | `mcpServers` |
| Kilo Code | `.kilo/kilo.json` → top-level `mcp` | local stdio per Kilo docs; merge **only** the `mcp` key |
| Pi | — | no built-in MCP; CLI-only via Shell |

Canonical Cursor / Claude / Qwen / Cline fragment (`mcpServers`):

```json
{
  "mcpServers": {
    "agent-browser": {
      "command": "agent-browser",
      "args": ["mcp"]
    }
  }
}
```

Default tools profile is `core` (small context). Full CLI parity only if the user asks:

```json
"args": ["mcp", "--tools", "all"]
```

Codex (`config.toml`):

```toml
[mcp_servers.agent-browser]
command = "agent-browser"
args = ["mcp"]
```

OpenCode (`opencode.json` — merge only `mcp.agent-browser`; key must start with a letter):

```json
{
  "mcp": {
    "agent-browser": {
      "type": "local",
      "command": ["agent-browser", "mcp"],
      "enabled": true
    }
  }
}
```

If `agent-browser` is not on the client's `PATH` after install (common on Windows when the IDE was started before `npm`), resolve the absolute path and use it as `command`:

```powershell
(Get-Command agent-browser).Source
```

### 5. Verify

1. CLI: `agent-browser --version` succeeds; `agent-browser doctor` reports a usable Chrome.
2. Smoke (optional, ~5 s):

   ```powershell
   agent-browser open about:blank
   agent-browser snapshot
   agent-browser close
   ```

3. Ask the user to **restart the AI client** so the MCP session reloads.
4. After restart, confirm `agent-browser` tools appear (e.g. `agent_browser_open`, `agent_browser_snapshot`). If missing — re-check the config path/shape from Step 4.

### 6. Final report (Russian, short)

Tell the user:

- CLI version and that Chrome for Testing is installed;
- which MCP config file was updated (path) and that other servers were preserved;
- that web UI tests should prefer `agent-browser` (see `ui-testing-tools.md`);
- that `UI_TESTING` / `INFOBASE_PUBLISH_URL` were not changed;
- next step: restart the client, then run a UI test via `/deploy-and-test` when ready.

## Limits

- Do **not** remove or replace `cursor-ide-browser` / other browser MCPs — leave them; policy prefers `agent-browser` when both are present.
- Do **not** commit secrets, profiles, or saved auth state.
- Do **not** run UI tests as part of this command.
- On failure of `npm` / `agent-browser install` — stop, show the error, do not half-write MCP config.
