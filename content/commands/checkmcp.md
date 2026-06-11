---
description: Check availability of 1C MCP servers and install/start the missing ones
---

# /checkmcp — check and install 1C MCP servers

This command checks that all MCP servers from the project catalog (`content/mcp-servers.json`; after 1c-rules installation, rendered into the active tool config such as `.cursor/mcp.json` / `.mcp.json` / `.kilo/kilo.json` / `opencode.json` / `.codex/config.toml`) are actually available in the current session, and helps start or install missing ones. For Kilo Code the rendered file uses the top-level `mcp` key with per-server `{ "type": "remote", "url": "...", "enabled": true }` — **not** the legacy `.kilocode/mcp.json` with `mcpServers` (current Kilo CLI / Kilo Code v7.x+ does not read that file).

**External MCP installation (INSTALL.md, режим 3).** If `.ai-rules.json` has `integrations.mcp.mode = "external"` (or the env `BASESAI_MCP_GLOBAL_ROOT` points at a folder with `install.manifest.json`), the server set, ids, urls, and ports come from the **actual install artifacts**, not from the catalog or the default table below: read `install.manifest.json`, resolve paths via its `artifacts` / `consumers` / `resolution` contract (legacy manifest without `schema_version` → schema-v1 defaults: registry at `<GLOBAL_ROOT>/projects.registry.json`, global servers in `%USERPROFILE%/.cursor/mcp.json`, project servers in `<path_code>/.cursor/mcp.json`), then merge global + project `mcpServers` (project keys win on duplicate id). Ports are parsed **only from each server's `url`** (`localhost:<PORT>`); Docker container names come from the registry's project row (`containers.*`). The `mcp:install_forme` section of `USER-RULES.md` holds the rendered tables as a convenient cache. The catalog and the default ports below apply only to **managed** installs.

The source of truth for images, ports, and environment variables is [docs.onerpa.ru/mcp-servery-1c](https://docs.onerpa.ru/mcp-servery-1c) and [vibecoding1c.ru/mcp_server](https://vibecoding1c.ru/mcp_server).

## Target server catalog

| id | Port | Docker image | Purpose | Requires data |
|---|---|---|---|---|
| `1c-syntax-checker-mcp` | 8002 | `comol/1c_syntaxcheck_mcp:latest` | BSL syntax (BSL Language Server) | No |
| `1c-templates-mcp` | 8004 | `comol/1c_templates_mcp:latest` | Templates and project memory (`remember`/`recall`) | No |
| `1c-ssl-mcp` | 8008 | `comol/mcp_ssl_server:latest` | BSP/SSL search | No (`SSL_VERSION`) |
| `1C-docs-mcp` | 8003 | `comol/1c_help_mcp:latest` | 1C platform help (RAG) | Yes — platform `bin` folder |
| `1c-code-metadata-mcp` | 8000 | `comol/1c_code_metadata_mcp:latest` | Metadata/code/forms/XSD | Yes — configuration dump |
| `1c-graph-metadata-mcp` | 8006 | `comol/1c_graph_metadata_mcp:latest` | Graph search (Neo4j) | Yes — dump + Neo4j |
| `1c-code-check-mcp` | 8007 | `comol/1c_code_checker_mcp:latest` | 1C:Assistant, ITS | No (Assistant token) |
| `1c-data-mcp` | 80 / project | — (HTTP service on the infobase, **not** docker) | 1C data management and analysis (HTTP service published on the infobase itself) | Yes — `INFOBASE_PUBLISH_URL` in `.dev.env` + `mcp` HTTP service published on the infobase **with anonymous access** |

> Exact image names may differ by version. If `docker pull` fails with `manifest unknown`, check the current list at [docs.onerpa.ru/mcp-servery-1c/servery.md](https://docs.onerpa.ru/mcp-servery-1c/servery.md).

> In **external** mode the ports differ from this table by design (per-project port blocks like 8200/8206; versioned Help/SSL keys like `1c-docs-mcp-8-3-27`, `1c-ssl-mcp-3-1-11` with their own host ports). Match servers by id prefix (`1c-docs-mcp` / `1C-docs-mcp`, `1c-ssl-mcp`, `1c-code-metadata-mcp`, `1c-graph-metadata-mcp`, …) and always probe the url from the resolved mcp.json, not the port column above.

> `1c-data-mcp` is **not** a docker container — it is an HTTP service (`hs/mcp`) published on the project's infobase. The 1c-rules installer derives its URL from `INFOBASE_PUBLISH_URL` in `.dev.env`: `<INFOBASE_PUBLISH_URL_BASE>/hs/mcp` (trailing `/` and trailing locale segment like `/ru/`, `/en/` are stripped). Docker / `docker ps` / `docker run` steps in this file do not apply to it — instead, verify that the HTTP service `mcp` is published on the infobase and that the URL responds. If `INFOBASE_PUBLISH_URL` is empty when the installer runs, the MCP config will contain the literal placeholder `{INFOBASE_PUBLISH_URL}/hs/mcp` — fill in `.dev.env` and re-run `install.ps1 update` (or edit the MCP config manually).
>
> **Authentication.** The `1c-data-mcp` endpoint MUST be reachable WITHOUT a password — the MCP client does not send an `Authorization` header to `/hs/mcp`. If the publication requires Basic auth, the HTTP probe below returns **401** or **403** and the server's tools never appear in the agent's session. Fix in `default.vrd` of the web publication:
>
> ```xml
> <!-- default.vrd — fragment that enables anonymous access for HTTP services -->
> <point xmlns="http://v8.1c.ru/8.2/virtual-resource-system"
>        xmlns:xs="http://www.w3.org/2001/XMLSchema"
>        base="/zup_test_forconf"
>        ib="File=&quot;C:\bases\zup_test_forconf&quot;;">
>   <usr name="MCPUser" pwd=""/>           <!-- technical IB user without password -->
>   <ws publishByDefault="true"/>          <!-- publish HTTP / Web services -->
> </point>
> ```
>
> `MCPUser` must exist in the infobase, have an empty password, and own a role that grants `Use` for the `mcp` HTTP service object plus `Read` for the metadata objects it touches. After editing `default.vrd`, restart the web server (`iisreset` for IIS; `apachectl restart` / `systemctl restart httpd|apache2` for Apache). The 1c-rules installer probes this URL automatically right after rendering the MCP config and surfaces a warning when it sees 401 / 403.

## Algorithm

### Step 1. Determine the server set

1. **External first.** Read `.ai-rules.json` → `integrations.mcp`. If `mode = "external"` (or env `BASESAI_MCP_GLOBAL_ROOT` + `<GLOBAL_ROOT>/install.manifest.json` exists):
   - Resolve paths from the manifest contract (`artifacts.registry`, `consumers.cursor_global_mcp`, `consumers.cursor_project_mcp`); `integrations.mcp` already carries the resolved `registryPath` / `globalMcpConfig` / `projectMcpConfig`.
   - Parse the resolved **project** and **global** mcp.json → list `{ id, url, port-from-url }`; merge (project keys win on duplicate id). **Do not** assume ports 8000/8006 for project servers.
   - Docker container names for Step 4 — from the registry's project row (`containers.*`, matched by `resolution.project_match`, default `path_code` == workspace root), **not** the default names below.

   Helper (PowerShell) — build the probe list from the resolved mcp.json files:

   ```powershell
   function Get-McpServersFromJson {
       param([string]$Path)
       $list = @()
       if (-not $Path -or -not (Test-Path $Path)) { return $list }
       $j = Get-Content -Raw $Path | ConvertFrom-Json
       foreach ($p in $j.mcpServers.PSObject.Properties) {
           $url = [string]$p.Value.url
           $port = if ($url -match ':(\d+)(/|$)') { $Matches[1] } else { '' }
           $list += [PSCustomObject]@{ Id = $p.Name; Url = $url; Port = $port }
       }
       return $list
   }
   $mcpInfo  = (Get-Content -Raw '.ai-rules.json' | ConvertFrom-Json).integrations.mcp
   $project  = Get-McpServersFromJson $mcpInfo.projectMcpConfig
   $global   = Get-McpServersFromJson $mcpInfo.globalMcpConfig
   $servers  = @($project) + @($global | Where-Object { $_.Id -notin $project.Id })
   ```

2. Else, if the project has `.ai-rules.json`, take the catalog from the active tool config referenced by the manifest (`.cursor/mcp.json` / `.mcp.json` / `.kilo/kilo.json` under the `mcp` key / `opencode.json` under the `mcp` key / `.codex/config.toml` under `[mcp_servers."<id>"]`). A leftover `.kilocode/mcp.json` is **legacy** — ignore it; current Kilo CLI / Kilo Code (v7.x+) does not read it. In `opencode.json` the server keys are letter-normalized to `onec-...` (e.g. `onec-syntax-checker-mcp`) because OpenCode names tools `<server-key>_<tool>` and providers like Moonshot/Kimi reject digit-leading function names — match them to the canonical `1c-...` ids by the bare tool names below, not by the prefix.
3. Otherwise use `content/mcp-servers.json` from the rules repository.
4. If neither source exists, use the table above as the default set.

### Step 2. Check availability in the current agent session

For each `id`, determine **TOOLS_OK** / **TOOLS_MISSING**:

- **TOOLS_OK** — this server's tools are visible in the current session tool schema (for example, `syntaxcheck` for `1c-syntax-checker-mcp`, `templatesearch`/`recall` for `1c-templates-mcp`, `ssl_search` for `1c-ssl-mcp`, `docinfo`/`docsearch` for `1C-docs-mcp`, `metadatasearch`/`codesearch` for `1c-code-metadata-mcp`, `search_metadata`/`get_object_dossier` for `1c-graph-metadata-mcp`, `check_1c_code`/`its_help` for `1c-code-check-mcp`).
- **TOOLS_MISSING** — no tools are visible in the schema.

If status is **TOOLS_OK**, treat the server as working and do not check it further.

### Step 3. Check HTTP endpoint

For servers with **TOOLS_MISSING**, call the HTTP endpoint. **External mode:** probe `$s.Url` from the Step 1 list (the actual url from mcp.json), not the hardcoded port table below — the snippet below applies to managed installs only. PowerShell (Windows):

```powershell
$servers = @(
    @{ Id = '1c-code-metadata-mcp';   Port = 8000 },
    @{ Id = '1c-syntax-checker-mcp';  Port = 8002 },
    @{ Id = '1C-docs-mcp';            Port = 8003 },
    @{ Id = '1c-templates-mcp';       Port = 8004 },
    @{ Id = '1c-graph-metadata-mcp';  Port = 8006 },
    @{ Id = '1c-code-check-mcp';      Port = 8007 },
    @{ Id = '1c-ssl-mcp';             Port = 8008 }
)
foreach ($s in $servers) {
    $url = "http://localhost:$($s.Port)/mcp"
    try {
        $r = Invoke-WebRequest -Uri $url -Method Get -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        Write-Host ("{0,-26} {1,-5} HTTP {2}" -f $s.Id, $s.Port, $r.StatusCode)
    } catch {
        $code = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { 'down' }
        Write-Host ("{0,-26} {1,-5} {2}" -f $s.Id, $s.Port, $code)
    }
}
```

Any HTTP response (even `405`/`400`/`406`) means a container is listening on the port — status **HTTP_OK**. Full timeout / `Connection refused` means **HTTP_DOWN**.

For `1c-data-mcp` (HTTP service on the infobase, no docker container), check the URL rendered by the installer into the active client's MCP config:

```powershell
$infobasePublishUrl = (Select-String -Path '.dev.env' -Pattern '^INFOBASE_PUBLISH_URL=(.+)$' |
    Select-Object -First 1).Matches.Groups[1].Value.Trim().TrimEnd('/')
# Strip trailing locale segment (/ru, /en, /uk, …) — mirrors the installer.
if ($infobasePublishUrl -match '/([a-z]{2,3})$' -and
    @('ru','en','uk','kk','be','de','fr','es','it','pl','tr','vi','zh','ja',
      'ka','lt','lv','hu','bg','ro','sk','cs','sl','hr','sr','et','fi','sv',
      'no','da','nl','pt','el','az','hy','mn','mk','th','ko','ar','he') -contains $Matches[1]) {
    $infobasePublishUrl = $infobasePublishUrl.Substring(0, $infobasePublishUrl.LastIndexOf('/'))
}
if (-not $infobasePublishUrl) {
    Write-Host '1c-data-mcp                — INFOBASE_PUBLISH_URL пуст в .dev.env; пропустите проверку'
} else {
    $url = "$infobasePublishUrl/hs/mcp"
    try {
        $r = Invoke-WebRequest -Uri $url -Method Get -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        $code = [int]$r.StatusCode
    } catch {
        $code = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { 'down' }
    }
    Write-Host ("{0,-26} {1,-5} {2}" -f '1c-data-mcp', '-', $code)
    switch -Regex ([string]$code) {
        '^401$' { Write-Warning "1c-data-mcp ответил HTTP 401 — публикация требует Basic-аутентификацию. MCP-клиент НЕ передаёт пароль; в default.vrd добавьте <usr name=`"...`" pwd=`"`"/> (технический пользователь без пароля) и перезапустите веб-сервер." }
        '^403$' { Write-Warning "1c-data-mcp ответил HTTP 403 — у пользователя по умолчанию нет прав на HTTP-сервис mcp. Добавьте роль с правом `Использование` на HTTP-сервис в назначения роли пользователя из default.vrd." }
        '^(200|201|204|400|405|406)$' { } # endpoint reachable anonymously
        '^404$' { Write-Warning "1c-data-mcp ответил HTTP 404 — HTTP-сервис `mcp` не опубликован на ИБ (либо не указано publishByDefault=`"true`" в default.vrd)." }
    }
}
```

For `1c-data-mcp`:

- **`HTTP 401` / `HTTP 403`** = the publication requires authentication. The MCP client does not pass `Authorization`, so it cannot connect. Fix the publication (`default.vrd`) per the catalog note above and re-run `/checkmcp`. Docker steps below the snippet do **not** apply.
- **`HTTP 404`** = the `mcp` HTTP service is not published on the infobase (Configurator → HTTP-сервисы → Опубликовать, or `publishByDefault="true"` in `default.vrd`).
- **`HTTP_DOWN`** = the web publication itself is not running (IIS / Apache stopped, or the published path is wrong). Not a docker problem — start the web server / fix the published path.
- **`HTTP 200` / `400` / `405` / `406`** = the endpoint is reachable anonymously; MCP transport-level handshake will continue from the agent on its own.

### Step 4. Check Docker state

If at least one server is **HTTP_DOWN**:

```powershell
docker version --format '{{.Server.Version}}'
docker ps --all --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
```

Possible outcomes:

- `docker version` fails with an engine connection error → **DOCKER_DOWN** (Docker Desktop is not running). Ask the user to start Docker Desktop and repeat `/checkmcp`.
- The container is visible in `docker ps -a`, but its state is `Exited` → **CONTAINER_STOPPED**. Start it:

  ```powershell
  docker start <container_name>
  ```

  Default names: `1c_syntaxcheck_mcp`, `1c_templates_mcp`, `mcp_ssl_server`, `1c_help_mcp`, `1c_code_metadata_mcp`, `1c_graph_metadata_mcp`, `1c_code_checker_mcp` (check the actual name in `docker ps -a`). **External mode:** take the project container names from `projects.registry.json` → project row → `containers.*` (e.g. `mcp_<id>_code_metadata`), not from the defaults.

- The container is absent from `docker ps -a` → **CONTAINER_MISSING**. The image may already be cached (`docker images`), but the container was not created. Create and start it — see Step 5.

### Step 5. Install missing server

**External mode:** install/recreate missing servers via the MCP distribution's **`INSTALL.md`** (it owns the registry, port assignment, and container naming) — do not `docker run` on port 8000 when the registry says 8200. The templates below apply to managed installs.

**Do not run `docker run` silently.** First ask the user for:

- `LICENSE_KEY` — shared MCP server license key.
- Local data paths for servers that need them:
  - `1C-docs-mcp` — platform `bin` folder path (for example, `C:\Program Files\1cv8\8.3.23.1997\bin`).
  - `1c-code-metadata-mcp`, `1c-graph-metadata-mcp` — configuration dump directory (`DumpConfigToFiles`).
  - `1c-ssl-mcp` — BSP/SSL version (`SSL_VERSION`, for example `3.1.11`).
  - `1c-code-check-mcp` — 1C:Assistant token, if it will be used.
- Index volume directory (`-v ...:/app/chroma_db`) — common folder such as `E:\bases\mcp_<id>`.

Command templates (minimal set without data preparation):

```powershell
# 1c-syntax-checker-mcp
# Optional: mount the project sources read-only and set FILES_DIR to enable the
# 'syntaxcheck_file' tool (file check by path — cheaper than passing code text).
# Without the mount only 'syntaxcheck' (code as text) is available.
docker run -d -p 8002:8002 --name 1c_syntaxcheck_mcp `
  -e LICENSE_KEY={LICENSE_KEY} `
  -e FILES_DIR=/files `
  -v "{PROJECT_ROOT}:/files:ro" `
  comol/1c_syntaxcheck_mcp:latest

# 1c-templates-mcp
docker run -d -p 8004:8004 --name 1c_templates_mcp `
  -e LICENSE_KEY={LICENSE_KEY} `
  -v "{DATA_ROOT}\mcp_templates:/app/chroma_db" `
  comol/1c_templates_mcp:latest

# 1c-ssl-mcp
docker run -d -p 8008:8008 --name mcp_ssl_server `
  -e LICENSE_KEY={LICENSE_KEY} `
  -e SSL_VERSION={SSL_VERSION} `
  -v "{DATA_ROOT}\mcp_ssl:/app/chroma_db" `
  comol/mcp_ssl_server:latest

# 1C-docs-mcp
docker run -d -p 8003:8003 --name 1c_help_mcp `
  -e LICENSE_KEY={LICENSE_KEY} `
  -v "{PLATFORM_BIN}:/1c_docs" `
  -v "{DATA_ROOT}\mcp_docs:/app/chroma_db" `
  comol/1c_help_mcp:latest

# 1c-code-metadata-mcp
docker run -d -p 8000:8000 --name 1c_code_metadata_mcp `
  -e LICENSE_KEY={LICENSE_KEY} `
  -v "{EXPORT_PATH}:/app/configuration" `
  -v "{DATA_ROOT}\mcp_code_metadata:/app/chroma_db" `
  comol/1c_code_metadata_mcp:latest

# 1c-graph-metadata-mcp — separate Neo4j setup, see docs
# https://docs.onerpa.ru/mcp-servery-1c/servery/graph-metadata-search.md

# 1c-code-check-mcp
docker run -d -p 8007:8007 --name 1c_code_checker_mcp `
  -e NAPARNIK_TOKEN={NAPARNIK_TOKEN} `
  comol/1c_code_checker_mcp:latest
```

Exact current commands for each server are on the server-specific documentation page:

- [HelpSearchServer](https://docs.onerpa.ru/mcp-servery-1c/servery/help-search-server.md)
- [CodeMetadataSearchServer](https://docs.onerpa.ru/mcp-servery-1c/servery/code-metadata-search.md)
- [Graph Metadata Search](https://docs.onerpa.ru/mcp-servery-1c/servery/graph-metadata-search.md)
- [SSLSearchServer](https://docs.onerpa.ru/mcp-servery-1c/servery/ssl-search-server.md)
- [SyntaxCheckServer](https://docs.onerpa.ru/mcp-servery-1c/servery/syntax-check-server.md)
- [TemplatesSearchServer](https://docs.onerpa.ru/mcp-servery-1c/servery/templates-search-server.md)
- [1CCodeChecker](https://docs.onerpa.ru/mcp-servery-1c/servery/code-checker.md)

### Step 6. After install/start

1. Wait 5-15 seconds (the container needs warm-up; RAG-indexed servers may need tens of minutes or hours on first launch, monitor with `docker logs -f <name>`).
2. Repeat Step 3 (HTTP check); all statuses should become **HTTP_OK**.
3. If the server is absent from the active tool MCP config, add the entry (1c-rules installer should already have rendered it; if installation was not run, add it manually using `adapters/<tool>.yaml → mcp.schema`).
4. Restart the client (Cursor / Claude Code / Codex / OpenCode / Kilo Code) so it reinitializes the MCP session.
5. Run `/checkmcp` again; Step 2 statuses should become **TOOLS_OK**.

## Final report

Summary table for the user:

| Server | Session tools | HTTP | Container | Action |
|---|---|---|---|---|
| `...` | OK / missing | OK / down | running / stopped / missing | none / `docker start` / `docker run` / reconnect client |

Under the table, list clear next steps with copy-ready commands. Do not list items that already work.

## Limits

- The command does not run `docker run` without user confirmation; it needs `LICENSE_KEY`, data paths, and consent to download images (several GB).
- `/checkmcp` is read-only with respect to MCP configs — never rewrite `.cursor/mcp.json` (or another tool's MCP target) during the check. In external mode the configs belong to the MCP distribution's installer.
- External multi-project layout: global servers live in the user-profile `mcp.json`, project servers in the workspace `mcp.json` — the client must load both levels; a server missing from the session may simply mean the client was not restarted after the MCP install.
- Graph MCP (`1c-graph-metadata-mcp`) requires separate Neo4j setup and indexing. This is a multi-step process; execute it by the server documentation page, not from this command.
- RAG-indexed servers (`1C-docs-mcp`, `1c-code-metadata-mcp`, `1c-graph-metadata-mcp`, `1c-ssl-mcp`) may respond over HTTP before becoming useful while primary indexing is still running. This is normal; monitor progress with `docker logs -f <name>`.
