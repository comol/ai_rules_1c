---
description: Re-download the 1C MCP server distribution from vibecoding1c.ru, pull new images, refresh keys, and restart installed servers
---

# /updatemcp — update MCP servers from a fresh vibecoding1c.ru distribution

This command updates already installed 1C MCP servers. It re-downloads the latest distribution from `https://vibecoding1c.ru/mcpserver` via the (undocumented but stable) Tilda Members API — `POST /api/login/` → `POST /api/getpage/` → extract Yandex Disk public link → fetch via Yandex Disk Public API — all in pure PowerShell (~3 seconds, no browser). Falls back to a browser-automation MCP only if that path fails (captcha, login_blocked, API change). The new archive is unpacked into a **staging** directory, new license keys are merged into the existing `config.env`, fresh Docker images are pulled, and the running containers are recreated. Reindexing is preserved by reusing existing volumes whenever possible.

Use `/installmcp` for the very first installation (no existing containers, fresh `config.env`). Use `/checkmcp` to inspect the current state at any point.

## Steps

### 1. Locate the existing installation

Ask the user **one** thing first:

> Где лежит текущий распакованный дистрибутив (`INSTALL.md` + `config.env` + папка `servers/`)? По умолчанию — `C:\Work\MCP_Distr`. Введите путь или нажмите Enter.

Verify that `<EXISTING>\INSTALL.md` and `<EXISTING>\config.env` exist. If not — stop and tell the user that this looks like a fresh install (run `/installmcp` instead).

Read `<EXISTING>\config.env` into memory (parsed key=value); these are the **current** values that will be merged with the new archive in Step 3.

### 2. Download the fresh distribution — headless HTTP flow

The download pipeline is identical to `/installmcp` step 1.1 (full description there), with two changes: the new archive is unpacked into a **staging** directory (it must not overwrite the user's filled-in `config.env`), and a change-detection check is added before the actual download to avoid a no-op update.

#### 2.1. Reuse credentials from `memory.md` (or ask once)

Look up the `memory.md` entry `MCP Distribution — vibecoding1c.ru credentials` (`tilda_login` + `tilda_password`). If present — reuse silently. If absent — ask the user in chat in a single message:

> Сессия личного кабинета `https://vibecoding1c.ru/` нужна для скачивания свежего дистрибутива. Введите email (логин) и пароль. Сохранить их в `memory.md` для следующих запусков? (Чувствительность низкая — это доступ только к публичной ссылке на дистрибутив.)

If the user agrees — write the entry per the template in `/installmcp` step 1.1.g.

#### 2.2. Extract `projectid` and `pageid` from the Tilda stub

```powershell
$stub = Invoke-WebRequest -Uri 'https://vibecoding1c.ru/mcpserver' -UseBasicParsing
$projectid = [regex]::Match($stub.Content, 'data-tilda-project-id="(\d+)"').Groups[1].Value
$pageid    = [regex]::Match($stub.Content, 'data-tilda-page-id="(\d+)"').Groups[1].Value
if (-not $projectid -or -not $pageid) { throw "Tilda stub HTML did not expose project-id / page-id; layout may have changed." }
```

#### 2.3. Log in and fetch the rendered page

Execute the same two POSTs as `/installmcp` steps 1.1.c-d. The `Origin` and `Referer` headers are **mandatory** — without them `/api/login/` returns `access_denied`.

```powershell
$headers = @{
    'Origin'     = 'https://vibecoding1c.ru'
    'Referer'    = 'https://vibecoding1c.ru/members/login'
    'User-Agent' = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0'
}

$loginResp = Invoke-RestMethod -Uri 'https://members.tildaapi.com/api/login/' -Method Post `
    -Body (@{ login=$tildaLogin; password=$tildaPassword; projectid=$projectid;
              pageurl='https://vibecoding1c.ru/members/login?redirecturl=mcpserver' } | ConvertTo-Json -Compress) `
    -ContentType 'application/json; charset=UTF-8' -Headers $headers
if ($loginResp.status -ne 'ok') {
    throw "Tilda login failed: status=$($loginResp.status), code=$($loginResp.code). On code='login_blocked' wait the timeout from `\$loginResp.data.hours/minutes`. On code='need_captcha' or persistent failure — fall back to step 2.5 (browser path)."
}
$token = $loginResp.data.token

$headers['Referer'] = 'https://vibecoding1c.ru/mcpserver'
$pageResp = Invoke-RestMethod -Uri 'https://members.tildaapi.com/api/getpage/' -Method Post `
    -Body (@{ projectid=$projectid; token=$token;
              tzoffset=(Get-Date).ToUniversalTime().Subtract((Get-Date)).TotalMinutes;
              pageurl='https://vibecoding1c.ru/mcpserver'; pageid=$pageid } | ConvertTo-Json -Compress) `
    -ContentType 'application/json; charset=UTF-8' -Headers $headers
if ($pageResp.status -ne 'ok' -or -not $pageResp.data.html) {
    throw "Tilda getpage failed: status=$($pageResp.status), code=$($pageResp.code). On code='unauthorized' — drop cached credentials and retry; else fall back to step 2.5."
}

$publicUrl = [regex]::Match($pageResp.data.html, 'https?://(?:disk\.yandex\.[a-z]+|yadi\.sk)/d/[A-Za-z0-9_\-]+').Value
if (-not $publicUrl) { throw "No Yandex Disk public link found in rendered HTML." }
"Yandex Disk public link: $publicUrl"
```

#### 2.4. Change check + download via Yandex Disk Public API

Inspect metadata first; only download if there is something newer than the current installation.

```powershell
$encoded = [Uri]::EscapeDataString($publicUrl)
$meta = Invoke-RestMethod -Uri "https://cloud-api.yandex.net/v1/disk/public/resources?public_key=$encoded"
"New archive on YD: {0} ({1:N0} bytes, modified {2})" -f $meta.name, $meta.size, $meta.modified
```

**Sanity check — is there anything to update?** Compare `$meta.modified` against the modification time of `<EXISTING>\INSTALL.md` (or any record kept from the previous installation). If the archive on Yandex Disk is older or equal, ask the user:

> На Яндекс.Диске лежит архив `<NAME>` от `<MODIFIED>`, размер `<SIZE>`. Текущая установка в `<EXISTING>` уже использует эту же или более свежую версию. `/updatemcp` может ничего не дать. Продолжать обновление (полезно если нужен `docker pull` под двигающимися тегами типа `latest`) или прервать команду?

If the user proceeds:

```powershell
$resp      = Invoke-RestMethod -Uri "https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key=$encoded"
$directUrl = $resp.href
if (-not $directUrl) { throw "Yandex Disk API did not return a download href for $publicUrl" }

$archive = Join-Path $env:TEMP $meta.name             # e.g. $env:TEMP\MCP_Distr.zip
Invoke-WebRequest -Uri $directUrl -OutFile $archive -UseBasicParsing
"Downloaded: {0} ({1:N0} bytes)" -f $archive, (Get-Item $archive).Length
```

#### 2.5. Fallback: browser-automation MCP or manual

When the headless flow fails (captcha, login_blocked, Tilda API change, or no PowerShell support), fall back to the browser flow described in `/installmcp` step 1.1.f. The result is the same — a Yandex Disk public URL — and step 2.4 then runs on it for the actual download. If neither headless nor browser MCP works, ask the user to open `https://vibecoding1c.ru/mcpserver` in their default OS browser (`Start-Process` it), copy the URL of the Yandex Disk tab, paste it back, then run step 2.4.

#### 2.6. Unpack into a staging directory (do not overwrite `config.env` in place)

```powershell
$existing = '<EXISTING_DIR>'                                                   # e.g. C:\Work\MCP_Distr
$staging  = "$existing.new_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
$archive  = '<PATH_TO_DOWNLOADED_ZIP>'                                         # from step 2.4
New-Item -ItemType Directory -Force -Path $staging | Out-Null
Expand-Archive -LiteralPath $archive -DestinationPath $staging -Force
Get-ChildItem -LiteralPath $staging -Force | Select-Object Mode, Name, Length | Format-Table -AutoSize
```

Verify that `$staging\INSTALL.md`, `$staging\config.env`, `$staging\servers\` and `$staging\Graph_metadata_search\` exist. If not — the archive layout changed; stop and ask the user to recheck the source.

### 3. Merge `config.env` (keys-only update, do not lose user data)

Open `$staging\config.env` and `<EXISTING>\config.env` and merge them with the following rules:

| Field class | Source of truth | Action |
|---|---|---|
| `LICENSE_KEY_*` | new archive | **always overwrite** existing values with values from `$staging\config.env` (these are the new license keys included in the release) |
| `IMAGE_TAG`, `USE_GPU`, `SSL_VERSION` and other release-version-coupled parameters | new archive default + user confirmation | show old vs new, ask explicitly whether to keep the user's existing value or switch to the new default |
| `PATH_1C_BIN`, `PATH_METADATA`, `PATH_CODE`, `PATH_BASES`, `EMBEDDING_API_KEY`, `EMBEDDING_API_BASE`, `EMBEDDING_MODEL`, `CHAT_API_KEY`, `ONEC_AI_TOKEN` and any other user-supplied data | existing file | **keep** the user's values; never overwrite from the archive (archive ships them empty) |
| any new variable present in `$staging\config.env` but missing in `<EXISTING>\config.env` | new archive | **add** it to the existing file; if it is empty and looks user-required, ask the user (one consolidated message), then save |

After merging, write the result back to `<EXISTING>\config.env`. **Never print license keys or tokens to the user**; refer to them by name (`LICENSE_KEY_HELP updated`, etc.).

Once `<EXISTING>\config.env` is updated, also overwrite supporting files from the staging copy:

- `<EXISTING>\INSTALL.md` ← `$staging\INSTALL.md`
- `<EXISTING>\servers\*.md` ← `$staging\servers\*.md`
- `<EXISTING>\Graph_metadata_search\docker-compose.yml` ← `$staging\Graph_metadata_search\docker-compose.yml`
- `<EXISTING>\Graph_metadata_search\.env` — re-render from the merged `<EXISTING>\config.env` per `servers\02_GraphMetadataSearch.md` (do **not** blindly copy `.env` from staging — it ships with empty values).

After all files are in place, the staging directory can be deleted (or kept as a backup for one cycle, user choice).

### 4. Capture pre-update state

Before changing any container, record the current state so there is something to compare against and roll back from:

```powershell
docker version --format '{{.Server.Version}}'
docker ps --all --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
docker images --format 'table {{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.CreatedSince}}\t{{.Size}}'
```

For each MCP container the distribution knows about (`1c_help_mcp`, `1c_code_metadata_mcp`, `1c_ssl_mcp`, `1c_templates_mcp`, `1c_syntax_checker_mcp`, `1c_code_checker_mcp`, plus the GraphMetadata Compose stack), check whether it exists:

```powershell
docker ps -a --filter "name=<container_name>" --format "{{.Names}} {{.Status}} {{.Image}} {{.Mounts}}"
```

If a container is absent, it was not installed previously — `/updatemcp` will **not** install it (use `/installmcp` for that) and will mark it as skipped in the final report.

### 5. Plan the update

Briefly summarize for the user (3-7 lines):

- which servers will be updated (only those present in `docker ps -a`);
- which images will be pulled (image:tag from per-server `servers\NN_*.md`, with `IMAGE_TAG` from `config.env`);
- whether reindexing is needed and roughly how long;
- which `LICENSE_KEY_*` changed (by name only, never the value);
- explicitly: volumes are reused by default (no reindexing, indexes preserved).

Risky steps that must be called out: volume deletion, manual DB migration, stopping a container during active indexing, changing an `IMAGE_TAG` that drops index-format compatibility. Ask for explicit confirmation before continuing.

### 6. Execute the update — one container at a time

For each installed container, perform the standard `INSTALL.md` update cycle:

#### 6.1. Stop and back up the old container

```powershell
docker stop <container_name>
$stamp = Get-Date -Format 'yyyyMMdd'
docker rename <container_name> "<container_name>_backup_$stamp"
```

Tell the user explicitly:

> Старый контейнер `<container_name>` остановлен и сохранён как `<container_name>_backup_<YYYYMMDD>`. Откатиться можно командой `docker start <container_name>_backup_<YYYYMMDD>` (после остановки нового).

#### 6.2. Confirm volume policy

> У старого контейнера были примонтированы тома (базы данных).
>
> 1. Использовать **те же базы** для нового контейнера (рекомендуется — данные сохранятся, не нужна переиндексация).
> 2. Создать **новые базы** в другом каталоге (старые останутся нетронутыми при старом контейнере).

Default to option 1 unless the user explicitly chooses 2 or the release notes require a fresh index.

#### 6.3. Pull the new image

```powershell
docker pull <image>:<IMAGE_TAG_from_config_env>
```

Pull is **mandatory** on update — this is the whole point of the command. Pull also the GraphMetadata stack via `docker-compose pull` in `<EXISTING>\Graph_metadata_search\` (it has multiple images: app + Neo4j).

#### 6.4. Start the new container

Use the exact `docker run` block from `<EXISTING>\servers\NN_*.md`, substituting `{{...}}` placeholders from the merged `<EXISTING>\config.env`. Show the command to the user with secrets masked (`-e LICENSE_KEY="***"`) and wait for confirmation. For GraphMetadata use `docker-compose up -d` in `<EXISTING>\Graph_metadata_search\`.

If `USE_GPU=true`, add `--gpus all` right after `docker run -d` per the per-server file note.

#### 6.5. Verify

```powershell
docker logs <container_name> --tail 50
```

If the log shows `LICENSE` / `license key` errors:

- Tell the user: "Лицензионный ключ для `<server>` не принят. Возможно, в `<EXISTING>\config.env` нужно обновить значение `LICENSE_KEY_*` из свежего архива — повторите Шаг 3, либо скачайте актуальный ключ в личном кабинете https://vibecoding1c.ru/."
- Re-merge and re-run the container.

Report per server: image → new image+tag (digest if shown), container status (`Up X seconds`), volumes touched.

### 7. Reconcile the active tool MCP config

After all containers restart:

1. If `INSTALL.md` or `servers\*.md` introduced new ports, service names, or new servers — reconcile against the active client config (`.cursor/mcp.json` / `.mcp.json` / `.opencode/opencode.json` / `.codex/config.toml`). The canonical fragment is identical to `/installmcp` Step 7 and lives in `INSTALL.md` STEP 4.
2. If `.ai-rules.json` is present in the project, prefer re-rendering via `/updaterules` (it will produce the config by adapter) — but only if changes are compatible with `content/mcp-servers.json`. Otherwise edit the active config manually per the bundled instruction.
3. Ask the user to restart the client (Cursor / Claude Code / Codex / OpenCode / Kilo Code) so it reinitializes the MCP session.

### 8. Final check

After the client restart, run `/checkmcp`. All updated servers should reach **TOOLS_OK** (or **HTTP_OK** while reindexing is still running). If anything remains **TOOLS_MISSING** / **HTTP_DOWN**, return to Step 6 for the failing container and compare the executed steps with `<EXISTING>\servers\NN_*.md`.

## Rollback

If the update broke the working state:

1. Stop and remove the new container:

   ```powershell
   docker stop <container_name>
   docker rm <container_name>
   ```

2. Start the backup created in Step 6.1:

   ```powershell
   docker rename "<container_name>_backup_<YYYYMMDD>" <container_name>
   docker start <container_name>
   ```

3. For GraphMetadata revert to the previous Compose state with `docker-compose down` + restoring the previous `docker-compose.yml` and `.env` (the staging copy contains them as a baseline if you kept it).
4. Restore the previous `<EXISTING>\config.env` if you saved a backup before Step 3 (recommended — copy it to `<EXISTING>\config.env.bak.<YYYYMMDD>` before merging).
5. Tell the user that rollback is complete and run `/checkmcp` again.

## Final report

Short user summary:

- download flow used (headless API / browser fallback / manual), staging directory, and final unpack directory;
- archive file name + size after download;
- new `INSTALL.md` version / date (if shown in the file);
- which `LICENSE_KEY_*` changed (by name only, never the value);
- servers actually updated (container name, port, previous → new image+tag);
- servers skipped and why (not installed, no `LICENSE_KEY_*`, no metadata dump, no `ONEC_AI_TOKEN`, etc.);
- backup containers kept (`<name>_backup_<YYYYMMDD>`);
- next steps if reindexing is still running.

## Limits

- The command **does not invent** update steps that are not in `<EXISTING>\INSTALL.md` and `<EXISTING>\servers\*.md`. If the bundled instruction lacks something, ask the user instead of filling gaps from memory.
- The command **does not echo or persist license keys / API tokens** in chat, in the repo, or in any committed file. Keys live only in `<EXISTING>\config.env` and in container environment variables.
- The command **may** store Tilda member-area credentials (`tilda_login`, `tilda_password`) in `memory.md`, but **only** after explicit user consent on the run that introduced them. Treat the credentials as low-sensitivity per the user's own statement — scope is access to a public distribution link, not payment / billing. Credentials are re-used by every `/installmcp` / `/updatemcp` run (the Tilda session token is short-lived and obtained fresh each time, not cached).
- The command **does not install** servers that are not already in `docker ps -a` — use `/installmcp` for that.
- The command **does not run** `docker pull` / `docker compose up` / `docker rm` / `docker volume rm` without explicit user confirmation.
