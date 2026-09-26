---
description: Install Windows-MCP (desktop UI automation MCP) as a last-resort alternative to home-grown screenshot/OCR
userOnly: true
---

# /install-windows-mcp — install Windows desktop UI MCP

Installs [Windows-MCP](https://github.com/CursorTouch/Windows-MCP) (`uvx windows-mcp`): an MCP server for Windows UI automation (mouse/keyboard, window state, optional browser DOM mode).

**Policy (mandatory):** this is a **last resort**, not the default for 1C testing.

- Prefer **web** UI testing via `agent-browser` (`/install-agent-browser`) against `INFOBASE_PUBLISH_URL`.
- Do **not** recommend vision / screenshot / CV loops for routine 1C form checks.
- If desktop / thick-client / non-web automation is unavoidable — use Windows-MCP instead of making the model write a custom screenshotter + OCR.
- Full policy — `content/rules/ui-testing-tools.md`.

Shell on Windows — `powershell-windows` skill. This command does **not** change `UI_TESTING` / `INFOBASE_PUBLISH_URL`.

## Steps

### 1. OS gate

Windows-MCP needs a real Windows host (Win7+). If the session is not Windows:

1. Stop.
2. Tell the user the tool is Windows-only.
3. For web UI tests point them to `/install-agent-browser`.

WSL note: if the AI client runs inside WSL, the MCP process must still execute on the **Windows** side (`uvx.exe` / `powershell.exe` bridge). Prefer installing from a Windows PowerShell / Cursor-on-Windows session.

### 2. Prerequisites — Python tooling via `uv`

1. Check `uv` / `uvx`:

   ```powershell
   uv --version
   uvx --version
   ```

2. If missing — install `uv` (Astral) with the official Windows script, then refresh `PATH` for the current session:

   ```powershell
   irm https://astral.sh/uv/install.ps1 | iex
   $env:Path = "$env:USERPROFILE\.local\bin;$env:USERPROFILE\.cargo\bin;$env:Path"
   uv --version
   ```

   If install fails — stop and ask the user to install `uv` manually (https://docs.astral.sh/uv/); do not guess paths.

3. Upstream requires **Python 3.13+** (pulled by `uvx` as needed). English UI language is preferred by upstream; other locales may need App-Tool disabled — mention only if the user hits that issue.

### 3. Smoke-pull the package

First run may take 1–2 minutes while dependencies resolve. Ignore a one-off MCP client timeout on first connect; restart the server/client afterward.

```powershell
uvx windows-mcp --help
if ($LASTEXITCODE -ne 0) { throw "uvx windows-mcp failed" }
```

Do **not** leave a long-running `serve` process hanging in the install chat unless the user asks — the MCP client will spawn `uvx windows-mcp serve` itself.

Optional (user asked for login autostart):

```powershell
uvx windows-mcp install
```

Creates a per-user Scheduled Task `windows-mcp-server`. Uninstall later with `uvx windows-mcp uninstall`. Default for this slash command: **skip** autostart unless requested.

### 4. Register the MCP server in the active client

Merge a `windows-mcp` stdio entry. **Do not overwrite** existing servers. Client → path → shape table is the same as `/install-agent-browser` Step 4 / `/installmcp` Step 7.

Canonical Cursor / Claude / Qwen / Cline fragment:

```json
{
  "mcpServers": {
    "windows-mcp": {
      "command": "uvx",
      "args": ["windows-mcp", "serve"]
    }
  }
}
```

Codex:

```toml
[mcp_servers.windows-mcp]
command = "uvx"
args = ["windows-mcp", "serve"]
```

OpenCode (merge only `mcp.windows-mcp`):

```json
{
  "mcp": {
    "windows-mcp": {
      "type": "local",
      "command": ["uvx", "windows-mcp", "serve"],
      "enabled": true
    }
  }
}
```

Claude Code CLI alternative (if the user prefers the CLI over editing JSON):

```powershell
claude mcp add --transport stdio windows-mcp -- uvx windows-mcp serve
```

If the IDE does not inherit user `PATH` (Store / sandboxed clients), resolve absolute paths:

```powershell
(Get-Command uvx).Source
```

and put that path in `command` (args stay `["windows-mcp", "serve"]`).

Security: prefer **stdio / localhost** only. Do not expose `--transport sse|streamable-http` on `0.0.0.0` unless the user explicitly asks and understands the risk.

### 5. Verify

1. `uvx windows-mcp --help` works.
2. Ask the user to **restart the AI client**.
3. After restart, confirm Windows-MCP tools are listed. First connect may time out while deps finish — retry once.
4. Remind: for 1C **web** client tests, keep using `agent-browser`; use Windows-MCP only when desktop automation is required.

### 6. Final report (Russian, short)

- `uv` / `uvx` status;
- MCP config path updated; other servers preserved;
- explicit warning: CV / desktop automation is last resort — preferred path is `/install-agent-browser` + web publication;
- ban reminder: do not hand-roll screenshotter/OCR while Windows-MCP is available;
- restart client next.

## Limits

- Windows host only.
- Do not enable remote HTTP transport by default.
- Do not use this command as a substitute for fixing a missing `INFOBASE_PUBLISH_URL` web publication.
- Do not run destructive UI actions during install (no clicking through the user's desktop "to test").
