---
description: Install DitriX EDT-MCP into a local 1C:EDT installation and connect the active AI client
userOnly: true
---

# /install-edt-mcp — install EDT-MCP

Installs the upstream [DitriXNew/EDT-MCP](https://github.com/DitriXNew/EDT-MCP) plugin into a local 1C:EDT installation and registers its Streamable HTTP endpoint in the active AI client.

EDT-MCP must run inside the same EDT process that owns the workspace. Do **not** put this plugin into the 1C MCP Docker bundle. Containerizing it is useful only when EDT itself, its workspace, runtime dependencies and UI/headless lifecycle are deliberately containerized; for a normal developer workstation it adds isolation problems and no useful portability.

Use this command when the user develops in EDT and needs live IDE state, EDT diagnostics, native refactoring, metadata/forms, application launch/update or debugging. It complements the 1C MCP bundle; it does not replace documentation, templates, BSP, code index or graph search.

Upstream currently ships a single build compiled against 1C:EDT `2026.1` and tested on `2026.2`. Verify the compatibility note in the upstream README at install time rather than assuming a version matrix from memory — it moves with EDT releases.

Once installed, the project's EDT branch of the ruleset applies: `content/rules/edt-workflow.md` (process — source format, model↔disk, validation, deployment owner) and `content/skills/mcp-1c-tools/docs/edt-mcp.md` (server catalog and routing).

## Steps

### 0. Check the project preference

Read `USE_EDT` from `.dev.env` before installation.

- `true` — continue.
- `false` — the explicit command is allowed, but ask whether this project should now use EDT. Continue only after confirmation and set `USE_EDT=true` without changing other keys.
- missing, empty or invalid — ask once and persist `true` when the user confirms installation. If `.dev.env` is missing, run the installer (`install.ps1 init`) instead of creating a partial file.

Do not infer project policy merely from an EDT executable found elsewhere on the workstation.

### 1. Detect EDT and an existing plugin

1. Locate `1cedt.exe` / the EDT launcher. On Windows, inspect the standard `1C\1CE\components\1c-edt-*-x86_64` locations under Program Files, then any path already configured by the project/user. On other systems inspect the normal EDT installation roots.
2. If zero or several installations match, ask the user to select the exact launcher. Show version and absolute path.
3. Check `http://127.0.0.1:8765/health` and the active client's MCP config. A stopped EDT is inconclusive.
4. If the plugin is already installed, do not reinstall. Offer the EDT update flow (`Help → About → Installation Details → MCP → Update`) and verify configuration.

### 2. Choose installation method

Prefer the EDT UI when the agent cannot prove the launcher path or EDT process state:

1. `Help → Install New Software...`
2. Add `https://ditrixnew.github.io/EDT-MCP/`
3. Select `EDT MCP Server Feature`
4. Complete installation and fully restart EDT.

For an unattended Windows installation, require EDT to be fully closed and obtain confirmation before invoking the p2 director. Never kill EDT automatically; it may contain unsaved work.

```powershell
$edtExe = 'C:\Program Files\1C\1CE\components\1c-edt-<version>-x86_64\1cedt.exe' # confirmed path

if (Get-Process -Name '1cedt' -ErrorAction SilentlyContinue) {
    throw 'EDT is running. Close it cleanly and rerun /install-edt-mcp.'
}

& $edtExe -nosplash `
  -application org.eclipse.equinox.p2.director `
  -repository 'https://ditrixnew.github.io/EDT-MCP/' `
  -installIU 'com.ditrix.edt.mcp.server.feature.feature.group' `
  -profileProperties 'org.eclipse.update.reconcile=true'
if ($LASTEXITCODE -ne 0) { throw "EDT p2 installation failed with exit code $LASTEXITCODE" }
```

Do not guess the EDT version inside the path.

### 3. Configure EDT safely

After EDT restarts, open `Window → Preferences → MCP Server` and recommend:

- bind to loopback, default port `8765`;
- enable auto-start;
- consent level `Ask always` for destructive operations — that is the default, and it stays;
- begin with the `Analysis Only` or `Code Review` tool preset; enable write/debug groups deliberately (`All Tools` / `Development` only on request);
- enable progressive disclosure when the client benefits from a smaller initial tool list (the core toolset is exposed first; the client reveals groups with `list_toolsets` → `enable_toolset` → re-request `tools/list`);
- for Cursor, enable `Plain text mode (Cursor compatibility)`.

Keep remote access disabled by default. If the user enables non-loopback access, require an auth token and a trusted network. Treat every connected client as fully trusted because EDT-MCP includes filesystem, code-writing, database-update and debug operations.

Operations classified as destructive — `delete_metadata`, `rename_metadata_object`, `delete_project`, `delete_infobase`, `update_database`, and `modify_metadata` when it changes a data type — prompt for consent. Do not weaken this on the user's behalf: the `Allow all` level and the `EDT_MCP_DESTRUCTIVE_CONSENT=allow` environment override exist for unattended automation only, and if the user asks for them, state plainly what they remove.

Optional form screenshots need this JVM property after `-vmargs` in the selected installation's `1cedt.ini`:

```text
-DnativeFormBufferedLayoutRender=true
```

Offer this edit only when form screenshot/layout tools are wanted. Back up the exact INI file before changing it and do not create duplicate properties.

### 4. Register the active AI client

Merge, never replace, an HTTP MCP entry named `edt-mcp` pointing to `http://127.0.0.1:8765/mcp`. Preserve all 1C bundle, Cognee and user-defined servers.

Canonical `mcpServers` fragment:

```json
{
  "mcpServers": {
    "edt-mcp": {
      "type": "http",
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

For Cursor, a URL-only entry is accepted. For OpenCode use its strict remote schema; for Codex use the corresponding TOML table. If the user configured an EDT auth token, use the client's supported header/secret mechanism and never print or commit the token.

Do not configure both a direct EDT endpoint and the multi-EDT proxy unless the user intentionally needs several concurrent EDT instances. For several instances, use upstream `edt-mcp-proxy` and one stable client endpoint instead of ambiguous duplicate servers.

### 5. Verify

1. Fully restart EDT and the AI client.
2. Verify health:

   ```powershell
   Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 10
   ```

3. Verify the client exposes core EDT tools and run a read-only call: `get_edt_version` / `get_server_status`, then `list_projects`. With progressive disclosure on, `list_toolsets` shows which groups are hidden; `get_tool_guide` is the authoritative per-tool parameter reference for later work.
4. Report the selected EDT path/version, plugin endpoint, client config path, preset, and whether screenshot support was enabled.
5. Confirm `.dev.env` holds `USE_EDT=true` (step 0) and tell the user in one line that the EDT rules are now active — `content/rules/edt-workflow.md`.

If health works but tools do not appear, re-check client schema, authentication headers and restart. If health fails, inspect EDT's Error Log before changing the client configuration.
