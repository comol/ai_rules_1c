---
description: Download the 1C MCP server distribution from vibecoding1c.ru and install all servers from it
userOnly: true
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

Use `/setupmcp` (`content/commands/setupmcp.md`) to connect already installed servers and available memory to a new repository by their actual addresses. Use `/checkmcp` to inspect those connections. Use `/updatemcp` to update an already installed set (and to re-fetch a newer distribution + new license keys).

Before selecting a target or running Docker, load `content/rules/mcp-deployment.md`. Local installation is the ordinary path; an optional shared Debian/Ubuntu Docker Engine host is equally valid. Resolve the target in the initial installation question, before downloading/unpacking; distinguish a local download staging directory from the installation root on the Docker host. Adapt shell/path syntax to the selected OS; the PowerShell download flow can run on a Windows client without making that client the Docker host. On a host without PowerShell use the documented browser/manual download fallback, not a Docker Desktop requirement. Existing endpoints route to `/setupmcp` without a download.

## Image variant (`IMAGE_VARIANT` / `IMAGE_TAG`)

**This section is the canon for image tags.** `/updatemcp`, `/checkmcp` and `/installtools` point here instead of repeating it.

Since 27.09.2026 the images have one channel — stable. Every 1C MCP server image is published under variant tags; the variant is **only the docker tag** — same repository, same container names, same ports, same `config.env`:

| Variant | Tag | Pick it when |
|---|---|---|
| full (default) | `latest` | обычная установка на x86-64 хосте |
| slim | `light` | нужен облегчённый образ; что именно из него исключено — только по `servers\NN_*.md` дистрибутива, не по догадке |
| ARM | `arm64` | хост на ARM64 (Apple Silicon, ARM-сервер) |

The variant lives in `<TARGET>\config.env`: `IMAGE_VARIANT` (`latest` / `light` / `arm64`), with an optional `IMAGE_TAG` that, when non-empty, overrides it verbatim (normally empty). The effective tag is `IMAGE_TAG` if set, else `IMAGE_VARIANT`. An older `config.env` with only `IMAGE_TAG` keeps working through that key. Never hardcode a tag into the `docker run` lines.

Tags with a `-beta` suffix (`latest-beta`, `light-beta`, `arm64-beta`) are **no longer published or supported**: the former beta images became the tags above. Never write such a tag; a `config.env` or container that still carries one is migrated by `/updatemcp` to the same variant without the suffix.

**External installs (`INSTALL.md` mode 3).** When the servers are managed outside this project (`BASESAI_MCP_GLOBAL_ROOT` / `MCP_GLOBAL_ROOT` + `install.manifest.json`), the keys live in the distribution's **global** `config.env` (`artifacts.global_config` of the manifest, default `<GLOBAL_ROOT>\config.env`) and the containers belong to that installer. Change the variant there, through the distribution's own `INSTALL.md` — do not recreate its containers from this command.

### Which tags exist

Verified on Docker Hub on **2026-09-29**; treat as a snapshot, not as a contract — always verify before pulling:

| Image | Tags |
|---|---|
| `comol/1c_help_mcp` | `latest`, `light`, `arm64` |
| `comol/1c_code_metadata_mcp` | `latest`, `light`, `arm64` |
| `comol/1c_graph_metadata` | `latest`, `light`, `arm64` |
| `comol/mcp_ssl_server` | `latest`, `light`, `arm64` |
| `comol/template-search-mcp` | `latest`, `light`, `arm64` |
| `comol/1c-code-checker` | `latest`, `light`, `arm64` |
| `comol/1c_syntaxcheck_mcp` | `latest`, `arm64` |

SyntaxCheckServer has no `light`: with `IMAGE_VARIANT=light` use `latest` for it on x86-64 (`arm64` on ARM). Other archival tags on Docker Hub (dated or build tags) are not install targets. **Image names come from `<TARGET>\servers\NN_*.md`, not from this table** — the table only says which tags that image publishes. When a per-server file pins the tag literally (`comol/1c_help_mcp:latest`), substitute **only the tag part** with the effective tag and leave the repository name exactly as the distribution wrote it.

### Verify the tag before pulling

A missing tag fails the pull with `manifest unknown` after the user already confirmed a multi-GB download. Check first:

```powershell
function Get-McpImageTags {
    param([string]$Repo)                      # e.g. 'comol/1c_help_mcp'
    try {
        (Invoke-RestMethod "https://hub.docker.com/v2/repositories/$Repo/tags?page_size=100" -TimeoutSec 10).results |
            Sort-Object last_updated -Descending | Select-Object name, last_updated
    } catch { $null }                          # registry unreachable — fall through to docker manifest inspect
}
Get-McpImageTags 'comol/1c_help_mcp' | Format-Table -AutoSize

# Offline / proxied environments: non-zero exit code means the tag does not exist.
docker manifest inspect comol/1c_help_mcp:light | Out-Null; $LASTEXITCODE
```

If the requested variant tag is missing for one server, do **not** silently substitute another tag: name the server and the missing tag and ask which variant to use for it (SyntaxCheckServer's missing `light` is the documented exception above).

### Boundaries

- Never leave the variant implicit — every install report names the effective tag per server.
- **Same containers, same ports, same volumes** when the variant changes; only the tag changes.
- **Index volumes.** If a container log reports an index / schema mismatch after a variant or image change, point that one server at a separate directory under `PATH_BASES` and let it reindex — **never** delete the existing index directory to make room.

## Steps

### 1. Choose the target directory and download the distribution

In one question combine the deployment choice from `content/rules/mcp-deployment.md` with the installation directory; omit already confirmed fields. Use an OS-appropriate path example (`C:\Work\MCP_Distr` on Windows, `/srv/mcp/MCP_Distr` on Linux), never a Windows default before the host is known:

> Установить MCP на этом компьютере (обычный вариант), на общем сервере Debian/Ubuntu с Docker или подключить уже работающие серверы? Для общего сервера укажите DNS/IP вместо 127.0.0.1 и доступ для установки. В какой каталог выбранного хоста распаковать дистрибутив? Свободные порты я проверю и подберу сам.

If the target directory already exists and already contains `INSTALL.md`, **stop** and tell the user:

> Папка `<TARGET>` уже содержит распакованный дистрибутив (`INSTALL.md` найден). Для обновления используйте `/updatemcp`. Если вы хотите переустановить с нуля — удалите папку или укажите другую.

Otherwise proceed to download.

#### 1.1. Distribution download flow (canon)

**This section is the canon for the download flow** — Tilda login → getpage → Yandex Disk public link → download → unpack, with the browser / manual fallback and the credentials policy. `/updatemcp` points here instead of repeating it; its two differences (a staging directory, a change check before the download) live there.

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

- **Scope:** `/installmcp`, `/updatemcp` and `/installdsh` slash commands. Used by the headless Tilda Members API flow (`POST /api/login/` → `POST /api/getpage/`) and, on fallback, by any browser-automation MCP (e.g. `cursor-ide-browser` in Cursor).
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

**Variant.** Simple mode keeps `IMAGE_VARIANT` from the archive's `config.env` (`latest` when it is missing) and does not ask. Detailed mode asks once, defaulting to the archive's value:

> Вариант образов: **latest** (полный, amd64), **light** (облегчённый, embeddings через внешний API) или **arm64** (ARM64)? По умолчанию — как в `config.env` дистрибутива.

Either way the variant is written to `IMAGE_VARIANT` in Step 5 — not pasted into the `docker run` lines.

### 4. Verify preconditions

1. **Selected Docker host.** Follow `content/rules/mcp-deployment.md`: inspect the chosen context/SSH target, daemon OS, `docker info` and `docker compose version`. Reuse a working Engine. Debian/Ubuntu uses native Docker Engine + Compose; Docker Desktop/WSL setup applies only to a selected local Windows deployment that actually needs it. An unreachable remote daemon is not a reason to install Docker locally. Verify mount paths on the daemon host and have the agent select free host ports there before launch.
2. **Detailed mode only — embedding model choice.** The shipped default is RouterAI with `EMBEDDING_MODEL=qwen/qwen3-embedding-8b`; keep it unless the user deliberately picks something else. Briefly explain the alternatives (LM Studio + Qwen3 Embedding with NVIDIA GPU / OpenRouter or OpenAI API / CPU mode) and reference `https://docs.onerpa.ru/mcp-servery-1c/embedding-modeli`. For users in Russia, note that `huggingface.co` may be blocked — recommend RouterAI or LM Studio.

### 5. Fill in `config.env`

Open `<TARGET>\config.env`. **Do not** invent values. For every parameter that is **empty**, prepare a single consolidated question to the user (do not ask one parameter per message). Use these prompts (skip a row if the parameter is already filled in the file):

Paths below belong to the selected Docker host; Windows paths are illustrative only. Obtain Linux paths for a Linux deployment and verify required files there. Persist host, bind address and selected port mappings using the deployment rule; add no unsupported keys to `config.env`.

| Parameter | Ask when | Prompt to the user |
|---|---|---|
| `EMBEDDING_API_KEY` | empty | Нужен ключ RouterAI (или OpenRouter / OpenAI) для embedding-моделей. Используется большинством серверов для семантического поиска. Регистрация: https://routerai.ru/ |
| `EMBEDDING_MODEL` | **never ask** | Default is `qwen/qwen3-embedding-8b` with `EMBEDDING_API_BASE=https://routerai.ru/api/v1`. Write that pair if either key is missing or empty in `config.env`; keep a value the user already set. Only replace it when the user explicitly chose another provider, and then use that provider's model name from `INSTALL.md`. |
| `PATH_1C_BIN` | empty | Путь к папке `bin` платформы 1С, например `C:\Program Files (x86)\1cv8\8.3.27.1936\bin`. |
| `PATH_METADATA` | empty | Необязательный путь к текстовому отчёту по конфигурации. Нужен только в legacy-режиме `METADATA_SOURCE=report` и для Graph + EDT; Designer XML работает без отчёта. |
| `PATH_CODE` | empty | Путь к Designer XML-выгрузке или каталогу EDT — основной источник CodeMetadata и Graph. |
| `PATH_BASES` | empty | Каталог для баз серверов, например `E:\bases\mcp`. Внутри будут созданы подкаталоги. |
| `ONEC_AI_TOKEN` | empty | Токен 1С:Напарник. Если нет — сервер `1CCodeChecker` будет пропущен. |
| `CHAT_API_KEY` | empty | Если `EMBEDDING_API_KEY` уже введён и провайдер тот же (по умолчанию RouterAI) — **используй тот же ключ автоматически**, не спрашивай. Иначе спроси отдельно. |
| `IMAGE_VARIANT` / `IMAGE_TAG` | **never ask** in simple mode | `IMAGE_VARIANT` — `latest` / `light` / `arm64` per `## Image variant`; leave `IMAGE_TAG` empty unless the user names an exact tag. Add `IMAGE_VARIANT` if the archive's `config.env` lacks it; replace any `*-beta` value with the same variant without the suffix. |

If the user says a parameter is unavailable (no metadata dump, no token, etc.) — mark the dependent servers as **skipped** and explicitly tell the user which ones and why. In simple mode install **all** servers that have all required data; in detailed mode also ask which optional servers to install and discuss `USE_GPU` and `SSL_VERSION` per `INSTALL.md` (the variant is already settled above — do not re-open it here).

After collecting answers, **save** them back to `<TARGET>\config.env` so that `/updatemcp` and re-runs do not ask again. **License keys (`LICENSE_KEY_*`) come from the archive — never invent or copy them between fields.**

### 6. Install servers

Servers are listed in order of importance per `INSTALL.md`. For each server in the table below:

The port column contains preferred **host** ports, not mandatory assignments. Allocate available host ports automatically per `content/rules/mcp-deployment.md`, retaining the container ports from each bundled instruction. Apply this to Compose publications too; preserve the existing installer's ownership of registry-assigned ports.

| # | Server | Per-server file | Container | Port | Required inputs |
|---|--------|-----------------|-----------|------|-----------------|
| 1 | HelpSearchServer        | `servers/01_HelpSearchServer.md`        | `1c_help_mcp`              | 8003 | `LICENSE_KEY_HELP`, `PATH_1C_BIN` |
| 2 | GraphMetadataSearch     | `servers/02_GraphMetadataSearch.md`     | Compose stack + Neo4j      | 8006 | Designer XML: `PATH_CODE`; EDT: ещё `PATH_METADATA`; embedding key для light |
| 3 | CodeMetadataSearchServer| `servers/03_CodeMetadataSearchServer.md`| `1c_code_metadata_mcp`     | 8000 | `PATH_CODE`; legacy report mode: ещё `PATH_METADATA` |
| 4 | SSLSearchServer         | `servers/04_SSLSearchServer.md`         | `1c_ssl_mcp`               | 8008 | `SSL_VERSION` |
| 5 | TemplatesSearchServer   | `servers/05_TemplatesSearchServer.md`   | `1c_templates_mcp`         | 8004 | — |
| 6 | SyntaxCheckServer       | `servers/06_SyntaxCheckServer.md`       | `1c_syntax_checker_mcp`    | 8002 | — (optional sources mount, see below) |
| 7 | 1CCodeChecker           | `servers/07_1CCodeChecker.md`           | `1c_code_checker_mcp`      | 8007 | `ONEC_AI_TOKEN` |

**SyntaxCheckServer, two optional switches (canon — `/checkmcp` points here).** Mounting the project sources read-only and setting `FILES_DIR` registers the `syntaxcheck_file` tool — the default form of the syntax gate, because a check by path costs a path instead of the whole module body; without the mount only `syntaxcheck` (code as text) exists. The second switch is **optional**: `FULLINDEX=true` plus an index volume (`/index`, `INDEX_DIR` moves it) makes the container index those sources and additionally answer `UnresolvedMethodCall`, `UnresolvedField` and `QueryToMissingMetadata`, which are off in every other state. Indexing a real configuration runs for hours — the container answers calls the whole time, and the volume keeps the index across restarts — and a file check with the index costs seconds instead of milliseconds. A server without it is a normal, fully working install, so offer it as a capability the operator may want, never as a fix.

For every server:

1. Read the per-server `servers\NN_*.md` file in full.
2. Substitute `{{...}}` placeholders in the `docker run` block from `<TARGET>\config.env` (`{{LICENSE_KEY_HELP}}` → value of `LICENSE_KEY_HELP`, etc.). **Do not echo license keys or API keys back to the user** — show command templates with placeholders unsubstituted, or with secrets masked (`-e LICENSE_KEY="***"`).
3. **Apply the image tag.** The image reference ends as `<repo-from-the-per-server-file>:<effective tag>` — substitute `{{IMAGE_TAG}}` where the file uses a placeholder, and replace the tag part where it pins one literally (`comol/1c_help_mcp:latest` → `comol/1c_help_mcp:light`). Never change the repository name. For a variant other than `latest`, verify the tag exists first (`## Image variant → Verify the tag before pulling`); a missing tag is reported and decided with the user.
4. Apply the selected host bind address and allocated host ports to the command/Compose config; this deployment adaptation does not change the image's internal ports or application contract. Show the target host and resolved command with secrets masked, then **wait for confirmation** before running it. Images may be several GB; first launch is heavy. Recheck candidate ports immediately before launch.
5. For `GraphMetadataSearch` use Compose: `cd <TARGET>\Graph_metadata_search; docker-compose up -d` after merging `config.env` values into `<TARGET>\Graph_metadata_search\.env` — the effective tag goes into that `.env` too, so the stack pulls the same variant (Neo4j keeps its own pinned tag; the variant applies to the `comol/*` image only).
6. If `USE_GPU=true`, add `--gpus all` right after `docker run -d` per the per-server file note.
7. After each launch, verify redacted logs on the selected host, actual port mappings and the client-reachable endpoint, then persist the successful deployment record. If the log reports an index / schema mismatch, apply `## Image variant → Boundaries`.

Skip servers whose required inputs are missing and explicitly list them in the final report.

**Volume warning.** Always pass `-v "<PATH_BASES>/<subdir>:/app/..."` exactly as written in the per-server file. Initial indexing of RAG servers (`1C-docs-mcp`, `1c-code-metadata-mcp`, `1c-graph-metadata-mcp`, `1c-ssl-mcp`) can take many hours up to a day; without volumes the indexes are lost on restart.

### 7. Per-client MCP config — register servers in the active tool

**This section is the canon for the per-client MCP config placement** — file path, top-level key, per-server shape, the Kilo legacy-file warning and the OpenCode `onec-` key rule. `/updatemcp`, `/checkmcp`, `/doctor` and the optional-tool installers point here; `install.ps1` renders the same placement.

After containers are up, write the MCP config for the active client. **The file path and JSON shape differ per client** — using the wrong combination (most commonly: writing Cursor-style `mcpServers` into a Kilo / OpenCode file) results in a silently empty MCP list in `/mcps` and missing tools in the agent session. The canonical fragment from `INSTALL.md` STEP 4 covers Cursor only; for the other clients use the table below.

All localhost URLs below are shape examples. Replace them with the full verified URLs from the deployment record: selected DNS/IP, allocated host ports and actual transport paths (or proxy URLs). Merge selected entries, preserving unrelated connections and auth references; never regenerate custom endpoints from the static catalog.

| Client | Config file | Top-level key | Per-server shape |
|---|---|---|---|
| Cursor | `.cursor/mcp.json` (project) or `%USERPROFILE%\.cursor\mcp.json` (global) | `mcpServers` | `{ "url": "...", "connection_id": "..." }` |
| Claude Code | `.mcp.json` (project) or `~/.claude/mcp.json` (global) | `mcpServers` | `{ "type": "http", "url": "..." }` |
| Command Code | `.mcp.json` (project; shared with Claude Code) or `~/.commandcode/mcp.json` (user) | `mcpServers` | `{ "type": "http", "url": "..." }` (`type` aliases `transport`) |
| Kilo Code (v7.x+) | `.kilo/kilo.json` (project) — also `kilo.json` / `kilo.jsonc` / `.kilo/kilo.jsonc`; global `~/.config/kilo/kilo.json` | `mcp` | `{ "type": "remote", "url": "...", "enabled": true }` |
| OpenCode | `opencode.json` (project) or `~/.config/opencode/opencode.json` (global) | `mcp` | `{ "type": "remote", "url": "..." }` |
| Codex CLI | `.codex/config.toml` (project) or `~/.codex/config.toml` (global) | `[mcp_servers."<id>"]` | TOML keys `url = ...`, `connection_id = ...` |
| Qwen Code | `.qwen/settings.json` (project) or `~/.qwen/settings.json` (user) | `mcpServers` | HTTP: `{ "httpUrl": "..." }`; SSE: `{ "url": "..." }`; stdio: `{ "command", "args?" }` |
| Kimi Code CLI | `.kimi-code/mcp.json` (project) | `mcpServers` | `{ "url": "..." }` |
| ZCode | `.zcode/config.json` (project) | `mcp.servers` | HTTP `{ "type": "http", "url": "...", "headers"?: {} }`; stdio `{ "type": "stdio", "command": "...", "args"?: [], "env"?: {} }` |
| MiMo Code | `mimocode.json` (project; `mimocode.jsonc` overrides it) | `mcp` | HTTP `{ "type": "remote", "url": "...", "enabled": true }`; stdio `{ "type": "local", "command": ["..."], "environment"?: {}, "enabled": true }` |
| Cline | `~/.cline/mcp.json` or `~/.cline/data/settings/cline_mcp_settings.json` (**global only** — no project MCP file) | `mcpServers` | `{ "url": "..." }` or stdio `{ "command", "args?" }` |
| Pi | — | — | No built-in MCP; use a Pi extension if needed |

ZCode and MiMo Code use strict native schemas: omit catalog-only `connection_id` and `description`. Preserve other settings and user-owned MCP entries; the adapters' `mergeServers` / `managedServers` contract is defined in `AGENT-INSTALL.md`. ZCode's `.agents/mcp.json` fallback is ignored when native servers exist, so write to `.zcode/config.json`. Sources: [ZCode MCP](https://zcode.z.ai/en/docs/mcp-services), [MiMo MCP](https://mimo.xiaomi.com/mimocode/mcp-servers), [MiMo config precedence](https://mimo.xiaomi.com/mimocode/config-overrides).

Canonical fragments (Cursor / Claude Code — `mcpServers`):

```json
{
  "mcpServers": {
    "1c-docs-mcp":          { "url": "http://localhost:8003/mcp", "connection_id": "1c_docs_service_001" },
    "1c-graph-metadata-mcp":{ "url": "http://localhost:8006/mcp", "connection_id": "1c_graph_metadata_001" },
    "1c-code-metadata-mcp": { "url": "http://localhost:8000/mcp", "connection_id": "1c_metadata_service_001" },
    "1c-ssl-mcp":           { "url": "http://localhost:8008/mcp", "connection_id": "1c_ssl_service_001" },
    "1c-templates-mcp":     { "url": "http://localhost:8004/mcp", "connection_id": "1c_templates_service_001", "headers": { "Authorization": "Bearer <value from MCP_OPERATOR_TOKEN>" } },
    "1c-syntax-checker-mcp":{ "url": "http://localhost:8002/mcp", "connection_id": "1c_lsp_service_001" },
    "1c-code-checker-mcp":  { "url": "http://localhost:8007/mcp", "connection_id": "1c_code_checker_001" }
  }
}
```

Kilo Code (`mcp` key, per-server `type` + `enabled`, see https://kilo.ai/docs/automate/mcp/using-in-cli):

```json
{
  "mcp": {
    "1c-docs-mcp":           { "type": "remote", "url": "http://localhost:8003/mcp", "enabled": true },
    "1c-graph-metadata-mcp": { "type": "remote", "url": "http://localhost:8006/mcp", "enabled": true },
    "1c-code-metadata-mcp":  { "type": "remote", "url": "http://localhost:8000/mcp", "enabled": true },
    "1c-ssl-mcp":            { "type": "remote", "url": "http://localhost:8008/mcp", "enabled": true },
    "1c-templates-mcp":      { "type": "remote", "url": "http://localhost:8004/mcp", "headers": { "Authorization": "Bearer <value from MCP_OPERATOR_TOKEN>" }, "enabled": true },
    "1c-syntax-checker-mcp": { "type": "remote", "url": "http://localhost:8002/mcp", "enabled": true },
    "1c-code-checker-mcp":   { "type": "remote", "url": "http://localhost:8007/mcp", "enabled": true }
  }
}
```

For Kilo Code do **not** write into the legacy `.kilocode/mcp.json` with the `mcpServers` dictionary — current Kilo CLI / Kilo Code (v7.x+) does not read that file, and the result is a silently empty `/mcps` listing. `.kilo/kilo.json` is the shared Kilo config (carries `instructions`, `skills.paths`, `permission`, custom agent overrides…). If the file already exists with such keys, **merge only the top-level `mcp` key** — do not overwrite the whole file.

OpenCode (`mcp` key) — **the server key MUST start with a letter**. OpenCode names MCP tools `<server-key>_<tool>` and some providers (Moonshot/Kimi) reject function names that do not start with a letter, failing the whole request with *"function name is invalid, must start with a letter"*. Use `onec-` instead of the leading `1c`/`1C`:

```json
{
  "mcp": {
    "onec-docs-mcp":           { "type": "remote", "url": "http://localhost:8003/mcp" },
    "onec-graph-metadata-mcp": { "type": "remote", "url": "http://localhost:8006/mcp" },
    "onec-code-metadata-mcp":  { "type": "remote", "url": "http://localhost:8000/mcp" },
    "onec-ssl-mcp":            { "type": "remote", "url": "http://localhost:8008/mcp" },
    "onec-templates-mcp":      { "type": "remote", "url": "http://localhost:8004/mcp", "headers": { "Authorization": "Bearer <value from MCP_OPERATOR_TOKEN>" } },
    "onec-syntax-checker-mcp": { "type": "remote", "url": "http://localhost:8002/mcp" },
    "onec-code-check-mcp":     { "type": "remote", "url": "http://localhost:8007/mcp" }
  }
}
```

Qwen Code (merge only `mcpServers` into `.qwen/settings.json`; HTTP uses `httpUrl`):

```json
{
  "mcpServers": {
    "1c-docs-mcp":           { "httpUrl": "http://localhost:8003/mcp" },
    "1c-graph-metadata-mcp": { "httpUrl": "http://localhost:8006/mcp" },
    "1c-code-metadata-mcp": { "httpUrl": "http://localhost:8000/mcp" },
    "1c-ssl-mcp":            { "httpUrl": "http://localhost:8008/mcp" },
    "1c-templates-mcp":      { "httpUrl": "http://localhost:8004/mcp", "headers": { "Authorization": "Bearer <value from MCP_OPERATOR_TOKEN>" } },
    "1c-syntax-checker-mcp": { "httpUrl": "http://localhost:8002/mcp" },
    "1c-code-check-mcp":     { "httpUrl": "http://localhost:8007/mcp" }
  }
}
```

Register only the servers actually installed, preserving unrelated existing entries. Replace the Templates placeholder through the client's supported secret mechanism; never print the token or commit it in client config. Ordinary memory calls follow the Templates authentication contract in `/checkmcp`; gated template mutations use the operator header when enabled. Merge the actual deployment URLs even if `.ai-rules.json` exists; do not re-render through `/updaterules`, which can restore catalog localhost/default ports. Ask the user to restart the client so the MCP session is reinitialized. For Cline, configure MCP once in the global Cline settings (the rules installer does not write a project MCP file).

### 8. Final check

After the client restart, run `/checkmcp`. All installed servers should reach **TOOLS_OK** (or **HTTP_OK** while initial indexing is still running). If anything remains **TOOLS_MISSING** / **HTTP_DOWN**, return to Steps 5-6 and compare the executed steps with the bundled instruction.

## Final report

Short user summary:

- download flow used (headless API / browser fallback / manual) and target unpack directory;
- archive file name + size after download;
- `INSTALL.md` version / date (if shown in the file);
- the image variant written to `config.env` and the effective tag of each server (SyntaxCheckServer without `light`);
- deployment host/OS and servers actually started (container name, bind address, host/container ports, full client URL, image, tag), plus the deployment record path;
- servers skipped and why (no `LICENSE_KEY_*`, no metadata dump, no `ONEC_AI_TOKEN`, separate setup required, etc.);
- whether `config.env` was updated and where it is stored;
- next steps if indexing is still running.

## Limits

- The command **does not invent** installation steps that are not in `<TARGET>\INSTALL.md` and `<TARGET>\servers\*.md`. If the bundled instruction lacks something, ask the user instead of filling gaps from memory.
- The command **does not echo or persist license keys / API tokens** in chat, in the repo, or in any committed file. Keys live only in `<TARGET>\config.env` and in container environment variables.
- The command **may** store Tilda member-area credentials (`tilda_login`, `tilda_password`) in `memory.md`, but **only** after explicit user consent on the run that introduced them (canon for the credentials policy — `/updatemcp` points here). Treat the credentials as low-sensitivity per the user's own statement — scope is access to a public distribution link, not payment / billing. Credentials are re-used by every `/installmcp` / `/updatemcp` run (the Tilda session token is short-lived and obtained fresh each time, not cached).
- The command **does not run** `docker run` / `docker compose up` / `docker pull` without explicit user confirmation; images may be several GB.
- The command **never installs a `*-beta` tag**: those tags are no longer published.
- The graph server (`1c-graph-metadata-mcp`) requires Neo4j and the Compose stack from `<TARGET>\Graph_metadata_search\`. Execute it strictly by `servers/02_GraphMetadataSearch.md`, not by generic recipes from `/checkmcp`.
