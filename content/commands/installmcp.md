---
description: Download the 1C MCP server distribution from vibecoding1c.ru and install all servers from it
---

# /installmcp — install MCP servers from the vibecoding1c.ru distribution

This command performs the first-time installation of 1C MCP servers. It downloads the distribution from `https://vibecoding1c.ru/mcpserver` via the (undocumented but stable) Tilda Members API — `POST /api/login/` → `POST /api/getpage/` → extract the Yandex Disk public link from the rendered HTML → fetch via the Yandex Disk Public API — all in pure PowerShell (~3 seconds, no browser). Falls back to a browser-automation MCP only if the Tilda API path fails (captcha, login_blocked, API change). The unpacked archive is then installed step by step per the bundled instructions.

The unpacked distribution layout is the canonical `MCP_Distr` layout (typical local example: `C:\Work\MCP_Distr`):

```
MCP_Distr/
├── INSTALL.md                          ← Main instruction (read in full)
├── config.env                          ← All settings (license keys, paths, API keys)
├── servers/
│   ├── 01_HelpSearchServer.md          ← 1C platform help
│   ├── 02_GraphMetadataSearch.md       ← Graph-based metadata search
│   ├── 03_CodeMetadataSearchServer.md  ← Metadata + code search
│   ├── 04_SSLSearchServer.md           ← SSL/БСП search
│   ├── 05_TemplatesSearchServer.md     ← 1C code templates
│   ├── 06_SyntaxCheckServer.md         ← BSL syntax check
│   └── 07_1CCodeChecker.md             ← 1С:Напарник code review
└── Graph_metadata_search/
    ├── docker-compose.yml              ← Compose for GraphMetadata + Neo4j
    └── .env                            ← Graph parameters (filled from config.env)
```

Use `/checkmcp` to inspect already installed servers. Use `/updatemcp` to update an already installed set (and to re-fetch a newer distribution + new license keys).

## Steps

### 1. Choose the target directory and download the distribution

Ask the user **one** thing first:

> Куда распаковать дистрибутив MCP серверов? По умолчанию — `C:\Work\MCP_Distr`. Если папка уже существует и содержит `INSTALL.md` — будет переиспользована (обновлять её предназначен `/updatemcp`, не `/installmcp`). Введите путь или нажмите Enter.

If the target directory already exists and already contains `INSTALL.md`, **stop** and tell the user:

> Папка `<TARGET>` уже содержит распакованный дистрибутив (`INSTALL.md` найден). Для обновления используйте `/updatemcp`. Если вы хотите переустановить с нуля — удалите папку или укажите другую.

Otherwise proceed to download.

#### 1.1. Download the archive — fully headless HTTP flow

The download URL is **not hardcoded** — it is published on `https://vibecoding1c.ru/mcpserver` behind a "Скачать" button (Yandex Disk) and rotates between releases. The page is a Tilda **members-only area**: a plain GET returns only the ~850-byte Tilda stub HTML (`<div id="allrecords" data-tilda-project-id="..." data-tilda-page-id="...">`); the actual content is fetched by Tilda's JS via two API calls. We replicate those two calls directly from PowerShell — no browser needed.

The pipeline (all HTTP, ~3 seconds end-to-end):

1. GET the stub HTML → extract `projectid` and `pageid`.
2. POST `https://members.tildaapi.com/api/login/` with credentials → receive a session `token`.
3. POST `https://members.tildaapi.com/api/getpage/` with `token` + `pageid` → receive the full rendered HTML in `data.html`.
4. Regex out the Yandex Disk public URL from the HTML.
5. Resolve the direct download URL via the Yandex Disk Public API, save the file with `Invoke-WebRequest`.

The Tilda Members API used here is the same one their own frontend uses (`tilda-members-init.min.js`, `tilda-members-sign.min.js`, `tilda-members-resources-page.min.js`). It is **not officially documented**, so treat it as best-effort — if any step fails, fall back to the browser path in step 1.1.f.

##### Step 1.1.a — Obtain Tilda credentials

Look up the `memory.md` entry titled `MCP Distribution — vibecoding1c.ru credentials` (`tilda_login` + `tilda_password`). If present — reuse silently.

If absent — ask the user in chat, in a single message:

> Для скачивания дистрибутива MCP нужно войти в личный кабинет `https://vibecoding1c.ru/`. Введите email (логин) и пароль. Сохранить их в `memory.md`, чтобы на следующих запусках входить автоматически? (Чувствительность низкая — это доступ только к публичной ссылке на дистрибутив, не к платёжным данным.)

If the user agrees to save — write the entry to `memory.md` per the template in step 1.1.g. If declined — keep credentials only for the current session.

##### Step 1.1.b — Extract `projectid` and `pageid` from the Tilda stub

```powershell
$stub = Invoke-WebRequest -Uri 'https://vibecoding1c.ru/mcpserver' -UseBasicParsing
$projectid = [regex]::Match($stub.Content, 'data-tilda-project-id="(\d+)"').Groups[1].Value
$pageid    = [regex]::Match($stub.Content, 'data-tilda-page-id="(\d+)"').Groups[1].Value
if (-not $projectid -or -not $pageid) { throw "Tilda stub HTML did not expose project-id / page-id; layout may have changed." }
"projectid=$projectid, pageid=$pageid"
```

##### Step 1.1.c — Log in to the Tilda Members API

The `Origin` and `Referer` headers are **mandatory** — without them `/api/login/` returns `access_denied` even with valid credentials. The `User-Agent` is recommended (Tilda may classify "exotic" clients as bot traffic). Use the project's official root zone (`.com` mirrors are exposed by Tilda; `.ru` works equivalently).

```powershell
$headers = @{
    'Origin'     = 'https://vibecoding1c.ru'
    'Referer'    = 'https://vibecoding1c.ru/members/login'
    'User-Agent' = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0'
}

$loginBody = @{
    login     = $tildaLogin
    password  = $tildaPassword
    projectid = $projectid
    pageurl   = 'https://vibecoding1c.ru/members/login?redirecturl=mcpserver'
} | ConvertTo-Json -Compress

$loginResp = Invoke-RestMethod -Uri 'https://members.tildaapi.com/api/login/' -Method Post `
    -Body $loginBody -ContentType 'application/json; charset=UTF-8' -Headers $headers

if ($loginResp.status -ne 'ok') {
    throw "Tilda login failed: status=$($loginResp.status), code=$($loginResp.code). Drop the cached credentials in memory.md and ask the user again, or fall back to step 1.1.f (browser path)."
}
$token = $loginResp.data.token
```

Error codes that this branch can return (from `tilda-members-sign.min.js`):

- `access_denied` — wrong credentials, or missing `Origin`/`Referer` headers.
- `login_blocked` — too many failed attempts (`data.hours` / `data.minutes` field tells the timeout).
- `need_captcha` — Tilda escalated to captcha; this flow cannot complete it. Fall back to the browser path (1.1.f).

##### Step 1.1.d — Fetch the rendered page HTML

```powershell
$pageBody = @{
    projectid = $projectid
    token     = $token
    tzoffset  = (Get-Date).ToUniversalTime().Subtract((Get-Date)).TotalMinutes
    pageurl   = 'https://vibecoding1c.ru/mcpserver'
    pageid    = $pageid
} | ConvertTo-Json -Compress

$headers['Referer'] = 'https://vibecoding1c.ru/mcpserver'
$pageResp = Invoke-RestMethod -Uri 'https://members.tildaapi.com/api/getpage/' -Method Post `
    -Body $pageBody -ContentType 'application/json; charset=UTF-8' -Headers $headers

if ($pageResp.status -ne 'ok' -or -not $pageResp.data.html) {
    throw "Tilda getpage failed: status=$($pageResp.status), code=$($pageResp.code). If code='unauthorized' — drop the cached credentials and retry; otherwise fall back to step 1.1.f."
}

$publicUrl = [regex]::Match($pageResp.data.html, 'https?://(?:disk\.yandex\.[a-z]+|yadi\.sk)/d/[A-Za-z0-9_\-]+').Value
if (-not $publicUrl) { throw "No Yandex Disk public link found in the rendered HTML — page layout may have changed." }
"Yandex Disk public link: $publicUrl"
```

##### Step 1.1.e — Download via the Yandex Disk Public API

```powershell
$encoded = [Uri]::EscapeDataString($publicUrl)

$meta = Invoke-RestMethod -Uri "https://cloud-api.yandex.net/v1/disk/public/resources?public_key=$encoded"
"File: {0} ({1:N0} bytes, modified {2})" -f $meta.name, $meta.size, $meta.modified

$resp      = Invoke-RestMethod -Uri "https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key=$encoded"
$directUrl = $resp.href
if (-not $directUrl) { throw "Yandex Disk API did not return a download href for $publicUrl" }

$archive = Join-Path $env:TEMP $meta.name             # e.g. $env:TEMP\MCP_Distr.zip
Invoke-WebRequest -Uri $directUrl -OutFile $archive -UseBasicParsing
"Downloaded: {0} ({1:N0} bytes)" -f $archive, (Get-Item $archive).Length
```

Show file name + size to the user **before** the `Invoke-WebRequest` call and ask for explicit confirmation — the archive can be several hundred MB on some releases.

##### Step 1.1.f — Fallback: browser-automation MCP

When the headless flow above fails (captcha, login_blocked, Tilda API change, or no PowerShell support), drive a browser instead. Look up the browser-automation MCP server exposed in the current session (Cursor → `cursor-ide-browser`; Claude Code / Codex / OpenCode → `browser-use` / `playwright`-style MCP). All expose the same primitives: open a tab, navigate, snapshot the DOM, fill a form field, click. Map the actions below to whatever tool names your environment provides.

```text
<tabs>(action="new", position="side")                                            → viewId
<navigate>(url="https://vibecoding1c.ru/mcpserver", viewId=<viewId>)
<snapshot>(viewId=<viewId>)                                                       # if /members/login — log in
<fill>(ref="<email-ref>",    value="<tilda_login>",    viewId=<viewId>)
<fill>(ref="<password-ref>", value="<tilda_password>", viewId=<viewId>)
<click>(ref="<login-button-ref>", viewId=<viewId>)
<snapshot>(viewId=<viewId>)                                                       # after redirect
<click>(ref="<download-link-ref>", viewId=<viewId>)                               # opens a YD tab; the YD tab URL is the public link
<tabs>(action="list")                                                             # find the disk.yandex.* tab; take its URL
<tabs>(action="close", index=<yd-tab-index>)
<tabs>(action="close", index=<mcpserver-tab-index>)
```

**Do not** click "Скачать" inside the Yandex Disk page — depending on browser policy this triggers a system "Save As" dialog that an MCP agent cannot dismiss. We only need the URL of the YD tab; with it, jump back to step 1.1.e for the actual download.

If no browser-automation MCP is available either, ask the user to open `https://vibecoding1c.ru/mcpserver` manually (`Start-Process` it), copy the URL of the Yandex Disk tab that opens after clicking "Скачать", paste it back, then continue with step 1.1.e.

##### Step 1.1.g — Save credentials to `memory.md` (consent-only)

Add the credentials entry **only** if the user explicitly agreed in step 1.1.a. The user has flagged these credentials as low-sensitivity (access to a public distribution link), so plaintext in `memory.md` is acceptable per their explicit consent. Do **not** add the entry silently. Replace any previous entry with the same title — keep only the latest.

```markdown
## YYYY-MM-DD — MCP Distribution — vibecoding1c.ru credentials

- **Scope:** `/installmcp`, `/updatemcp` slash commands. Used by the headless Tilda Members API flow (`POST /api/login/` → `POST /api/getpage/`) and, on fallback, by any browser-automation MCP (e.g. `cursor-ide-browser` in Cursor).
- **Rule:** authenticate to `https://vibecoding1c.ru/` with `tilda_login=<email>` and `tilda_password=<password>`. Both flows need fresh credentials on every run (no long-lived session is cached here on purpose — the token is re-issued each time).
- **Why:** the user explicitly authorized storing these credentials in `memory.md` on `<YYYY-MM-DD>`, noting the access scope is limited to fetching a public MCP distribution link.
- **Source:** user during `/installmcp`.
```

##### Step 1.1.h — Unpack into the target directory

```powershell
$target  = '<TARGET_DIR>'                              # e.g. C:\Work\MCP_Distr
$archive = '<PATH_TO_DOWNLOADED_ZIP>'                  # the file from step 1.1.e, e.g. $env:TEMP\MCP_Distr.zip
New-Item -ItemType Directory -Force -Path $target | Out-Null
Expand-Archive -LiteralPath $archive -DestinationPath $target -Force
Get-ChildItem -LiteralPath $target -Force | Select-Object Mode, Name, Length | Format-Table -AutoSize
```

Verify that `<TARGET>\INSTALL.md`, `<TARGET>\config.env`, `<TARGET>\servers\` and `<TARGET>\Graph_metadata_search\` exist. The unpacked tree may also contain a nested `MCP_1C_Distr.zip` artifact alongside `INSTALL.md` — leave it as is, it is part of the published bundle and `INSTALL.md` does not require unpacking it. If the required files are missing, stop and ask the user to recheck the source. Optionally remove the downloaded archive: `Remove-Item $archive`.

### 2. Read the bundled instructions

Read `<TARGET>\INSTALL.md` **fully** — this is the canonical source of truth. Also pre-open files that will be referenced:

- `<TARGET>\config.env` — central configuration (license keys, paths, API keys).
- `<TARGET>\servers\01_HelpSearchServer.md` … `<TARGET>\servers\07_1CCodeChecker.md` — per-server `docker run` commands.
- `<TARGET>\Graph_metadata_search\docker-compose.yml` and `<TARGET>\Graph_metadata_search\.env` — Compose stack for GraphMetadata + Neo4j.

The source of truth at this step is **only files inside `<TARGET>`**. Do not replace them with instructions from `/checkmcp`, `https://docs.onerpa.ru/mcp-servery-1c`, `https://vibecoding1c.ru/`, `content/mcp-servers.json`, etc. Those sources may only be used to cross-check an already executed step.

### 3. Ask for installation mode

Before touching anything (per `INSTALL.md` STEP 0), ask the user:

> Выберите режим установки:
> 1. **Простая установка** — задам минимум вопросов, настрою всё по умолчанию.
> 2. **Детальная настройка** — пройдёмся по всем параметрам и требованиям.

Wait for an explicit answer.

### 4. Verify preconditions

1. **Docker Desktop.** Run `docker info`. If Docker is missing or the daemon is not running:
   - Check WSL2: `wsl --list --verbose`. If absent — `wsl --install` (reboot required).
   - Install Docker Desktop: `winget install Docker.DockerDesktop`.
   - Ask the user to start Docker Desktop and wait for it to be ready.
   - Re-run `docker info`.
2. **Detailed mode only — embedding model choice.** Briefly explain three options (LM Studio + Qwen with NVIDIA GPU / OpenRouter API / CPU mode) and reference `https://docs.onerpa.ru/mcp-servery-1c/embedding-modeli`. For users in Russia, note that `huggingface.co` may be blocked — recommend LM Studio or OpenRouter.

### 5. Fill in `config.env`

Open `<TARGET>\config.env`. **Do not** invent values. For every parameter that is **empty**, prepare a single consolidated question to the user (do not ask one parameter per message). Use these prompts (skip a row if the parameter is already filled in the file):

| Parameter | Ask when | Prompt to the user |
|---|---|---|
| `EMBEDDING_API_KEY` | empty | Нужен ключ OpenRouter (или OpenAI) для embedding-моделей. Используется большинством серверов для семантического поиска. Регистрация: https://openrouter.ai/ |
| `PATH_1C_BIN` | empty | Путь к папке `bin` платформы 1С, например `C:\Program Files (x86)\1cv8\8.3.27.1936\bin`. |
| `PATH_METADATA` | empty | Путь к текстовому отчёту по конфигурации (Конфигуратор → Конфигурация → Отчёт по конфигурации). Если нет — серверы `CodeMetadata` и `Graph` будут пропущены. |
| `PATH_CODE` | empty | Путь к выгрузке конфигурации в файлы (или каталог EDT). Если нет — `CodeMetadata` и `Graph` будут пропущены. |
| `PATH_BASES` | empty | Каталог для баз серверов, например `E:\bases\mcp`. Внутри будут созданы подкаталоги. |
| `ONEC_AI_TOKEN` | empty | Токен 1С:Напарник. Если нет — сервер `1CCodeChecker` будет пропущен. |
| `CHAT_API_KEY` | empty | Если `EMBEDDING_API_KEY` уже введён и провайдер тот же (OpenRouter) — **используй тот же ключ автоматически**, не спрашивай. Иначе спроси отдельно. |

If the user says a parameter is unavailable (no metadata dump, no token, etc.) — mark the dependent servers as **skipped** and explicitly tell the user which ones and why. In simple mode install **all** servers that have all required data; in detailed mode also ask which optional servers to install and discuss `IMAGE_TAG`, `USE_GPU`, `SSL_VERSION` per `INSTALL.md`.

After collecting answers, **save** them back to `<TARGET>\config.env` so that `/updatemcp` and re-runs do not ask again. **License keys (`LICENSE_KEY_*`) come from the archive — never invent or copy them between fields.**

### 6. Install servers

Servers are listed in order of importance per `INSTALL.md`. For each server in the table below:

| # | Server | Per-server file | Container | Port | Required inputs |
|---|--------|-----------------|-----------|------|-----------------|
| 1 | HelpSearchServer        | `servers/01_HelpSearchServer.md`        | `1c_help_mcp`              | 8003 | `LICENSE_KEY_HELP`, `PATH_1C_BIN` |
| 2 | GraphMetadataSearch     | `servers/02_GraphMetadataSearch.md`     | Compose stack + Neo4j      | 8006 | `PATH_METADATA`, `EMBEDDING_API_KEY` |
| 3 | CodeMetadataSearchServer| `servers/03_CodeMetadataSearchServer.md`| `1c_code_metadata_mcp`     | 8000 | `PATH_METADATA`, `PATH_CODE` |
| 4 | SSLSearchServer         | `servers/04_SSLSearchServer.md`         | `1c_ssl_mcp`               | 8008 | `SSL_VERSION` |
| 5 | TemplatesSearchServer   | `servers/05_TemplatesSearchServer.md`   | `1c_templates_mcp`         | 8004 | — |
| 6 | SyntaxCheckServer       | `servers/06_SyntaxCheckServer.md`       | `1c_syntax_checker_mcp`    | 8002 | — |
| 7 | 1CCodeChecker           | `servers/07_1CCodeChecker.md`           | `1c_code_checker_mcp`      | 8007 | `ONEC_AI_TOKEN` |

For every server:

1. Read the per-server `servers\NN_*.md` file in full.
2. Substitute `{{...}}` placeholders in the `docker run` block from `<TARGET>\config.env` (`{{LICENSE_KEY_HELP}}` → value of `LICENSE_KEY_HELP`, etc.). **Do not echo license keys or API keys back to the user** — show command templates with placeholders unsubstituted, or with secrets masked (`-e LICENSE_KEY="***"`).
3. Show the command to the user and **wait for confirmation** before running it. Images may be several GB; first launch is heavy.
4. For `GraphMetadataSearch` use Compose: `cd <TARGET>\Graph_metadata_search; docker-compose up -d` after merging `config.env` values into `<TARGET>\Graph_metadata_search\.env`.
5. If `USE_GPU=true`, add `--gpus all` right after `docker run -d` per the per-server file note.
6. After each `docker run`, verify with `docker logs --tail 50 <container_name>` and report the first lines to the user.

Skip servers whose required inputs are missing and explicitly list them in the final report.

**Volume warning.** Always pass `-v "<PATH_BASES>/<subdir>:/app/..."` exactly as written in the per-server file. Initial indexing of RAG servers (`1C-docs-mcp`, `1c-code-metadata-mcp`, `1c-graph-metadata-mcp`, `1c-ssl-mcp`) can take many hours up to a day; without volumes the indexes are lost on restart.

### 7. Register servers in the active tool

After containers are up, write the MCP config for the active client. The canonical fragment from `INSTALL.md` STEP 4 (Cursor — `%USERPROFILE%\.cursor\mcp.json` or `.cursor/mcp.json` in the project):

```json
{
  "mcpServers": {
    "1c-docs-mcp":          { "url": "http://localhost:8003/mcp", "connection_id": "1c_docs_service_001" },
    "1c-graph-metadata-mcp":{ "url": "http://localhost:8006/mcp", "connection_id": "1c_graph_metadata_001" },
    "1c-code-metadata-mcp": { "url": "http://localhost:8000/mcp", "connection_id": "1c_metadata_service_001" },
    "1c-ssl-mcp":           { "url": "http://localhost:8008/mcp", "connection_id": "1c_ssl_service_001" },
    "1c-templates-mcp":     { "url": "http://localhost:8004/mcp", "connection_id": "1c_templates_service_001" },
    "1c-syntax-checker-mcp":{ "url": "http://localhost:8002/mcp", "connection_id": "1c_lsp_service_001" },
    "1c-code-checker-mcp":  { "url": "http://localhost:8007/mcp", "connection_id": "1c_code_checker_001" }
  }
}
```

Keep only the servers that were actually installed. If the project has `.ai-rules.json`, the MCP config is rendered by the 1c-rules installer — re-render through `/updaterules` instead of editing the file manually. Ask the user to restart the client (Cursor / Claude Code / Codex / OpenCode / Kilo Code) so the MCP session is reinitialized.

### 8. Final check

After the client restart, run `/checkmcp`. All installed servers should reach **TOOLS_OK** (or **HTTP_OK** while initial indexing is still running). If anything remains **TOOLS_MISSING** / **HTTP_DOWN**, return to Steps 5-6 and compare the executed steps with the bundled instruction.

## Final report

Short user summary:

- download flow used (headless API / browser fallback / manual) and target unpack directory;
- archive file name + size after download;
- `INSTALL.md` version / date (if shown in the file);
- servers actually started (container name, port, image, tag);
- servers skipped and why (no `LICENSE_KEY_*`, no metadata dump, no `ONEC_AI_TOKEN`, separate setup required, etc.);
- whether `config.env` was updated and where it is stored;
- next steps if indexing is still running.

## Limits

- The command **does not invent** installation steps that are not in `<TARGET>\INSTALL.md` and `<TARGET>\servers\*.md`. If the bundled instruction lacks something, ask the user instead of filling gaps from memory.
- The command **does not echo or persist license keys / API tokens** in chat, in the repo, or in any committed file. Keys live only in `<TARGET>\config.env` and in container environment variables.
- The command **may** store Tilda member-area credentials (`tilda_login`, `tilda_password`) in `memory.md`, but **only** after explicit user consent on the run that introduced them. Treat the credentials as low-sensitivity per the user's own statement — scope is access to a public distribution link, not payment / billing. Credentials are re-used by every `/installmcp` / `/updatemcp` run (the Tilda session token is short-lived and obtained fresh each time, not cached).
- The command **does not run** `docker run` / `docker compose up` / `docker pull` without explicit user confirmation; images may be several GB.
- The graph server (`1c-graph-metadata-mcp`) requires Neo4j and the Compose stack from `<TARGET>\Graph_metadata_search\`. Execute it strictly by `servers/02_GraphMetadataSearch.md`, not by generic recipes from `/checkmcp`.
