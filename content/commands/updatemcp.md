---
description: Re-download the 1C MCP server distribution from vibecoding1c.ru, pull new images, refresh keys, restart installed servers, and switch the image channel between stable and beta
userOnly: true
argumentHint: "[stable|beta]"
---

# /updatemcp — update MCP servers from a fresh vibecoding1c.ru distribution

This command updates already installed 1C MCP servers. It re-downloads the latest distribution from `https://vibecoding1c.ru/mcpserver` (download flow — `/installmcp` → *1.1. Distribution download flow*), unpacks the new archive into a **staging** directory, merges new license keys into the existing `config.env`, pulls fresh Docker images, and recreates the running containers. Reindexing is preserved by reusing existing volumes whenever possible.

Use `/installmcp` for the very first installation (no existing containers, fresh `config.env`). Use `/checkmcp` to inspect the current state at any point.

## Release channel — switching between stable and beta

The channel contract (tag matrix `latest` / `light` / `arm64` × the `-beta` suffix, where `IMAGE_TAG` lives, which tags exist, how to verify a tag, the boundaries) is defined once in **`/installmcp` → `## Release channel — stable or beta (IMAGE_TAG)`**. Read it there; this command only switches between the channels it defines.

`/updatemcp` takes one optional argument:

- **empty** — keep the current channel. Read `IMAGE_TAG` from `<EXISTING>\config.env`, update within that channel, and **never** move a stable install onto beta (or back) as a side effect of an update.
- `beta` / `-beta` / `бета` — switch to beta: `IMAGE_TAG` becomes the `-beta` twin of the current variant tag (`latest` → `latest-beta`, `light` → `light-beta`, `arm64` → `arm64-beta`). Already on beta — no-op, say so and continue with the normal update.
- `stable` / `latest` / `стабильный` — switch back: strip the `-beta` suffix from the current tag (`light-beta` → `light`). Already on stable — no-op, say so and continue.
- anything else — do not guess; show the current channel and ask.

A channel switch is a **separate, confirmed decision** on top of the update. Ask once, before any pull:

> Сейчас установлен канал `<CURRENT_TAG>`, переключаю на `<TARGET_TAG>`. Контейнеры пересоздаются на образах нового канала, тома (индексы) переиспользуются, старые контейнеры остаются как `<name>_backup_<YYYYMMDD>`. Откат — `/updatemcp <обратный канал>` или запуск backup-контейнера. Переключаем?

Before pulling, verify the target tag exists for **every** server being switched (`/installmcp` → *Verify the tag before pulling*). If it is missing for one server, name that server and ask: leave it on the current channel (a documented mixed set) or abort the switch. Do not substitute a neighbouring tag on your own.

## Steps

### 1. Locate the existing installation

Ask the user **one** thing first:

> Где лежит текущий распакованный дистрибутив (`INSTALL.md` + `config.env` + папка `servers/`)? По умолчанию — `C:\Work\MCP_Distr`. Введите путь или нажмите Enter.

Verify that `<EXISTING>\INSTALL.md` and `<EXISTING>\config.env` exist. If not — stop and tell the user that this looks like a fresh install (run `/installmcp` instead).

Read `<EXISTING>\config.env` into memory (parsed key=value); these are the **current** values that will be merged with the new archive in Step 3.

### 2. Download the fresh distribution

Download and unpack — `/installmcp` → *1.1. Distribution download flow* (`content/commands/installmcp.md`): Tilda credentials from `memory.md` or asked once (storage only with consent — the policy is owned there), stub → `POST /api/login/` → `POST /api/getpage/` → Yandex Disk public link → Yandex Disk Public API → `Invoke-WebRequest`, with the browser-automation / manual fallback. Run it with two update-specific differences:

#### 2.1. Change check before the download

After the archive metadata is resolved (`$meta` from the Yandex Disk Public API), compare `$meta.modified` against the modification time of `<EXISTING>\INSTALL.md` (or any record kept from the previous installation). If the archive on Yandex Disk is older or equal, ask the user:

> На Яндекс.Диске лежит архив `<NAME>` от `<MODIFIED>`, размер `<SIZE>`. Текущая установка в `<EXISTING>` уже использует эту же или более свежую версию. `/updatemcp` может ничего не дать. Продолжать обновление (полезно если нужен `docker pull` под двигающимися тегами типа `latest`) или прервать команду?

Download only if the user proceeds (name + size are shown and confirmed before `Invoke-WebRequest`, as in the canon).

#### 2.2. Unpack into a staging directory (never over the user's `config.env`)

```powershell
$existing = '<EXISTING_DIR>'                                                   # e.g. C:\Work\MCP_Distr
$staging  = "$existing.new_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
$archive  = '<PATH_TO_DOWNLOADED_ZIP>'                                         # from the download step
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
| `IMAGE_TAG` | **the channel argument, else the existing file** | An explicit `beta` / `stable` argument wins and writes the resolved tag. Without an argument, **keep the installed value** — an archive shipping `IMAGE_TAG=latest` must not silently pull a beta install back to stable, or the reverse. Show old vs new only when the archive default differs from the kept value, and treat any change as the confirmed channel switch above. |
| `USE_GPU`, `SSL_VERSION` and other release-version-coupled parameters | new archive default + user confirmation | show old vs new, ask explicitly whether to keep the user's existing value or switch to the new default |
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
- the channel: `<current tag>` → `<target tag>`, or "канал не меняется" when there is no channel argument;
- which images will be pulled (image:tag from per-server `servers\NN_*.md`, with `IMAGE_TAG` from `config.env`);
- whether reindexing is needed and roughly how long;
- which `LICENSE_KEY_*` changed (by name only, never the value);
- explicitly: volumes are reused by default (no reindexing, indexes preserved).

Risky steps that must be called out: volume deletion, manual DB migration, stopping a container during active indexing, and a channel switch — beta may change the index format, and moving to beta is not covered by any compatibility promise. Ask for explicit confirmation before continuing.

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

Pull is **mandatory** on update — this is the whole point of the command. Pull also the GraphMetadata stack via `docker-compose pull` in `<EXISTING>\Graph_metadata_search\` (it has multiple images: app + Neo4j) after writing the merged `IMAGE_TAG` into that folder's `.env`, so the stack follows the same channel.

On a channel switch the tag is already verified (see `## Release channel`); if the pull still fails with `manifest unknown`, **stop for that server**, leave the previous state in place (the old container was only stopped and renamed in 6.1 — start the backup again), and report it. Never fall back to the other channel's tag silently.

#### 6.4. Start the new container

Use the exact `docker run` block from `<EXISTING>\servers\NN_*.md`, substituting `{{...}}` placeholders from the merged `<EXISTING>\config.env`. Show the command to the user with secrets masked (`-e LICENSE_KEY="***"`) and wait for confirmation. For GraphMetadata use `docker-compose up -d` in `<EXISTING>\Graph_metadata_search\`.

If `USE_GPU=true`, add `--gpus all` right after `docker run -d` per the per-server file note.

#### 6.5. Verify

```powershell
docker logs <container_name> --tail 50
```

On a switch to beta, also read the log for index / schema mismatch messages. If one appears, do **not** delete the stable index: point that server's volume at a separate directory (`<PATH_BASES>\<server>_beta`), recreate the container, and let it reindex — the stable index then survives a `/updatemcp stable` rollback intact.

If the log shows `LICENSE` / `license key` errors:

- Tell the user: "Лицензионный ключ для `<server>` не принят. Возможно, в `<EXISTING>\config.env` нужно обновить значение `LICENSE_KEY_*` из свежего архива — повторите Шаг 3, либо скачайте актуальный ключ в личном кабинете https://vibecoding1c.ru/."
- Re-merge and re-run the container.

Report per server: image → new image+tag (digest if shown), container status (`Up X seconds`), volumes touched.

### 7. Reconcile the active tool MCP config

After all containers restart:

1. If `INSTALL.md` or `servers\*.md` introduced new ports, service names, or new servers — reconcile against the active client config. File path, top-level key and per-server shape per client, the Kilo legacy `.kilocode/mcp.json` warning and the OpenCode `onec-` key rule — `/installmcp` → *Step 7. Per-client MCP config* (`content/commands/installmcp.md`); `install.ps1` renders the same placement. When editing by hand, replace only the MCP key of the client file and keep every other key intact.
2. If `.ai-rules.json` is present in the project, prefer re-rendering via `/updaterules` (the installer renders the per-client placement, deep-merging Kilo's `mcp` key into an existing `.kilo/kilo.json` and removing the legacy `.kilocode/mcp.json`) — but only if changes are compatible with `content/mcp-servers.json`. Otherwise edit the active config manually per the bundled instruction and the canon above.
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

3. **Wrong channel** (beta turned out unusable): the fastest correct rollback is `/updatemcp stable` — it resolves `IMAGE_TAG` back to the stable tag, re-pulls, and recreates the containers over the same volumes. The backup containers from Step 6.1 are the immediate fallback when even that pull is unavailable (no network, image not cached).
4. For GraphMetadata revert to the previous Compose state with `docker-compose down` + restoring the previous `docker-compose.yml` and `.env` (the staging copy contains them as a baseline if you kept it).
5. Restore the previous `<EXISTING>\config.env` if you saved a backup before Step 3 (recommended — copy it to `<EXISTING>\config.env.bak.<YYYYMMDD>` before merging) — this is also what restores the previous `IMAGE_TAG`.
6. Tell the user that rollback is complete and run `/checkmcp` again.

## Final report

Short user summary:

- download flow used (headless API / browser fallback / manual), staging directory, and final unpack directory;
- archive file name + size after download;
- new `INSTALL.md` version / date (if shown in the file);
- which `LICENSE_KEY_*` changed (by name only, never the value);
- **release channel**: `<previous tag>` → `<current tag>`, or "без изменений"; any server deliberately left on the other channel and why;
- servers actually updated (container name, port, previous → new image+tag);
- servers skipped and why (not installed, no `LICENSE_KEY_*`, no metadata dump, no `ONEC_AI_TOKEN`, etc.);
- backup containers kept (`<name>_backup_<YYYYMMDD>`);
- next steps if reindexing is still running.

## Limits

- The command **does not invent** update steps that are not in `<EXISTING>\INSTALL.md` and `<EXISTING>\servers\*.md`. If the bundled instruction lacks something, ask the user instead of filling gaps from memory.
- The command **does not echo or persist license keys / API tokens** in chat, in the repo, or in any committed file. Keys live only in `<EXISTING>\config.env` and in container environment variables.
- Tilda member-area credentials (`tilda_login`, `tilda_password`) are reused from `memory.md` or asked once; the storage / consent policy is owned by `/installmcp` → *Limits* and *1.1. Distribution download flow*.
- The command **does not install** servers that are not already in `docker ps -a` — use `/installmcp` for that.
- The command **does not change the release channel** without an explicit `beta` / `stable` argument plus the confirmation above. An update with no argument stays on the channel the project already runs, whatever the fresh archive's `config.env` defaults to.
- The command **does not run** `docker pull` / `docker compose up` / `docker rm` / `docker volume rm` without explicit user confirmation.
