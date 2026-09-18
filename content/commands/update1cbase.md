---
description: Load current repository files into the infobase defined in .dev.env and update the DB structure
argumentHint: "[full|partial|git|all]"
---

# /update1cbase — load repository into an infobase

Load the configuration (`/LoadConfigFromFiles`) from the current repository directory into the infobase defined in `.dev.env`, then update the database structure (`/UpdateDBCfg`). With the `all` argument (or an explicit "with extensions" request) the command loads the **full snapshot** — main configuration plus every extension from `EXTENSION_NAMES` — see "Full-snapshot mode" at the end.

Read `content/rules/getconfigfiles.md → Configuration file synchronization contract`. A partial load is a first-class branch of this update procedure: **load → checks → database apply → requested directory refresh**. Do not stop after importing files or merely offer the database update when the user has already requested it.

## Select load scope

- `full` / `all`: load a verified complete snapshot. A selected-object dump or a delta directory is not a full-load source.
- `partial`: load the task's exact file selection and required dependencies using `-files` or `-listFile`. Never pass the metadata-name list `repoobjects.txt` as the load list.
- `git`: use `db-load-git -DryRun` from `content/skills/1c-metadata-manage/docs/db-manage.md` to inspect the selected diff (`All`, `Staged`, `Unstaged` or `Commit`). Resolve deletions / renames and confirm the plan covers the requested change before loading. An empty plan ends as a no-op; it does not become a full load.
- No explicit mode: use the already established task scope. A known bounded set of changed files can use `partial`; a requested complete deployment uses `full`. If completeness or removal semantics are uncertain, resolve the scope before modifying the infobase.

Partial loads target the main configuration or **one named extension per pass**. Do not combine partial selection with `all` / platform `-AllExtensions`. Keep repository locks, support rules, validation and retry handling at the same strength as a full load.

This command does not run tests and does not publish the infobase. Use `/deploy-and-test` to run tests after loading.

## Step 0. Check `.dev.env` parameters

`.dev.env` is the single source of truth for connection parameters (created by the 1c-rules installer at the project root). If it is missing, ask the user to run `install.ps1 init` or manually copy `.dev.env.example` to `.dev.env`.

If the project still has legacy `infobasesettings.md`, migrate values to `.dev.env` (same key names, `KEY=value` format instead of a markdown list), preserving already-filled `.dev.env` keys, and delete the legacy file after successful migration. The ruleset has no other connection-settings location.

Parameters, classes and defaults — `content/rules/dev-standards-env.md §1`; Defaulted keys are never asked for. Keys read: `PLATFORM_PATH`, `INFOBASE_PATH` (**blocking** — if either is empty, ask once and write the value to `.dev.env`), `INFOBASE_KIND`, `IB_USER` / `IB_PASSWORD`, `EXTENSION_NAME`, `EXTENSION_NAMES` (`all` mode), `EXPORT_PATH`, `EXTENSIONS_PATH`, `LOG_PATH`, `RESULT_PATH`, `IBCMD_CONFIG`, `REPOSITORY_PATH` (repository gate below).

**Dev/test gate:** this command forcibly terminates sessions while applying the DB configuration (`--session-terminate=force` / `-SessionTerminate force`). The target must be an explicitly identified dev/test infobase. If the current context does not establish that, stop before Step 3 and ask the user to confirm the target — never infer that an arbitrary `.dev.env` points to a test base. On production, drop the forced termination (`--session-terminate=prompt`, or omit `-SessionTerminate`) and agree on an update window with the user.

**EDT gate:** when `.dev.env` `USE_EDT=true`, establish the source format before running. This command loads a **Designer XML dump**; it cannot load an EDT (`src/**/*.mdo`) tree. In an EDT-format project either produce a dump first (`export_configuration_to_xml`) or let EDT apply the change (`update_database`) — and keep **one deployment owner per run**, named in the `IB tooling:` line. Canon — `content/rules/edt-workflow.md → DB update, launches, external objects`.

**Repository gate:** when `REPOSITORY_PATH` is non-empty, the target infobase is bound to a configuration repository — the objects being loaded must be **locked in the repository first** (`1c-repository-manage` skill, process — its `docs/repo-sdlc.md`); otherwise the load fails or silently skips read-only objects. A "configuration is read-only / object locked" line in the load/update log routes to that skill, not into the retry loop below. **Never unbind** the configuration from the repository to make the load proceed.

When substituting `.dev.env` values into the templates below, resolve `{INFOBASE_FLAG}` once from the effective `INFOBASE_KIND` (`/F` for `file`, `/S` for `server`; reject any other value), and substitute resolved `{LOG_PATH}` / `{RESULT_PATH}` values that contain `$env:` double-quoted — single quotes do not expand it. Delete a stale `{RESULT_PATH}` file before every Designer launch.

Before running, resolve the source directory for the selected main configuration / extension. Full mode requires a complete dump with `Configuration.xml`; partial mode requires a non-empty validated file list in the matching format and a suitable existing target configuration. Check source completeness and dependencies; never infer a full snapshot from the presence of `Configuration.xml` alone. Preserve the existing `ConfigDumpInfo.xml` before the load changes it; after a failed load / apply it is not evidence of a synchronized database.

## Step 1. Choose tool: `ibcmd` or Designer

1. Check whether the utility exists: `Test-Path '{PLATFORM_PATH}\bin\ibcmd.exe'`.
2. Check whether `IBCMD_CONFIG` is filled in `.dev.env`.
3. If **both conditions are true**, use **Steps 2a and 3a (`ibcmd`)**.
4. Otherwise use **Steps 2b and 3b (Designer)**.

`ibcmd infobase config` does not apply to 1C cluster infobases; for server cluster infobases always use Designer.

For partial / Git loads, use the bundled `db-load-xml -Mode Partial -Files ...` / `-ListFile ...` or `db-load-git` after its plan, or the Designer template below. The `ibcmd` full-import template is not a partial-import substitute: use its verified `config import files` path in the skill only when suitable. Keep one load owner; do not execute the wrapper and raw template for the same load. In this procedure omit wrapper `-UpdateDB`: apply is a separate stage so extension checks can run first.

## Step 2a. Load configuration through `ibcmd` (preferred)

```powershell
& '{PLATFORM_PATH}\bin\ibcmd.exe' infobase config import `
    --config='{IBCMD_CONFIG}' `
    --user='{IB_USER}' `
    --password='{IB_PASSWORD}' `
    --extension={EXTENSION_NAME} `
    '{EXPORT_PATH}' *>&1 | Tee-Object -FilePath '{LOG_PATH}'
```

Remove empty optional keys (`--user`, `--password`, `--extension`). On errors, show the relevant log fragment to the user and **do not continue** to Step 3a.

## Step 3a. Update DB structure through `ibcmd`

```powershell
& '{PLATFORM_PATH}\bin\ibcmd.exe' infobase config apply `
    --config='{IBCMD_CONFIG}' `
    --user='{IB_USER}' `
    --password='{IB_PASSWORD}' `
    --force `
    --dynamic=auto `
    --session-terminate=force `
    --extension={EXTENSION_NAME} *>&1 | Tee-Object -FilePath '{LOG_PATH}'
```

`--session-terminate=force` is allowed only after the dev/test gate of Step 0. When an extension is loaded through `ibcmd`, run **Step 2c** (Designer batch check against the same infobase) before this step — `ibcmd` has no applicability check of its own.

Continue to **Step 4**.

## Step 2b. Load configuration from files through Designer (fallback)

Map `.dev.env` keys to Designer flags:

| Field | Flag |
|---|---|
| `INFOBASE_KIND=file` | `/F '{INFOBASE_PATH}'` |
| `INFOBASE_KIND=server` | `/S '{INFOBASE_PATH}'` |
| `IB_USER` when not empty | `/N '{IB_USER}'` |
| `IB_PASSWORD` when not empty | `/P '{IB_PASSWORD}'` |
| `EXTENSION_NAME` when not empty | `-Extension {EXTENSION_NAME}` |

```powershell
& '{PLATFORM_PATH}\bin\1cv8.exe' DESIGNER `
    {INFOBASE_FLAG} '{INFOBASE_PATH}' `
    /N '{IB_USER}' `
    /P '{IB_PASSWORD}' `
    /DisableStartupMessages `
    /LoadConfigFromFiles '{EXPORT_PATH}' `
    -updateConfigDumpInfo `
    -Extension {EXTENSION_NAME} `
    /Out '{LOG_PATH}' `
    /DumpResult '{RESULT_PATH}'
```

Remove empty optional keys (`/N`, `/P`, `-Extension`). For the main configuration, remove `-Extension {EXTENSION_NAME}` entirely.

For **partial** mode, insert one of the following selector fragments after `/LoadConfigFromFiles '{EXPORT_PATH}'` in that same launch:

```text
-listFile '<validated UTF-8 file list>' -Format Hierarchical
-files "CommonModules/РаботаСДанными/Ext/Module.bsl" -Format Hierarchical
```

Use only one fragment, resolve its real paths and use `Plain` for a flat dump. For loading only supplied pieces of an object's description, add `-partial` only after confirming support in the target platform help (the bundled partial-load tools already add it). Keep `-updateConfigDumpInfo` in full and partial Designer loads. It updates the version baseline, not the database configuration. After a clean partial load, continue to Step 2c when applicable and then Step 3b; never report the update complete at this point.

Read the verdict (`{RESULT_PATH}`, exit code, `{LOG_PATH}` — see the retry loop below). On errors, show the relevant log fragment to the user and **do not continue** to Step 3b.

Wait 5-10 seconds so the platform releases the configuration lock.

## Step 2c. Applicability check — mandatory when an extension is loaded

Whenever this run loads an extension (`EXTENSION_NAME` filled, or an extension pass of the full-snapshot mode), run the batch check ladder **between the load (Step 2) and the DB update (Step 3)** — canon `content/rules/designer-batch-checks.md → The check ladder`, verification contract `content/rules/verification-gates.md → Gate 6`:

```powershell
& '{PLATFORM_PATH}\bin\1cv8.exe' DESIGNER `
    {INFOBASE_FLAG} '{INFOBASE_PATH}' `
    /N '{IB_USER}' `
    /P '{IB_PASSWORD}' `
    /DisableStartupMessages `
    /CheckModules -ThinClient -Server -ExternalConnection -Extension {EXTENSION_NAME} `
    /Out '{LOG_PATH}' `
    /DumpResult '{RESULT_PATH}'
```

then the same launch with `/CheckCanApplyConfigurationExtensions -Extension {EXTENSION_NAME}` in place of `/CheckModules …`. Read the verdict from all three signals after each launch; stop at the first failure and do not run Step 3. An interceptor pointing at a method the vendor renamed loads without complaint and only fails at apply time — or silently stops intercepting; this check is the only step in the pipeline that names it. The check is the same in single-extension and full-snapshot runs, and it is what `/deploy-and-test`, `/restore-testbase` and `/build-release` inherit by calling this procedure.

For the main configuration alone the ladder is optional — run `/CheckConfig` when the change is large (whole-snapshot deploy, release build) or when the Gate 1–3 MCP validators were not exposed in this session.

## Step 3b. Update DB structure through Designer

```powershell
& '{PLATFORM_PATH}\bin\1cv8.exe' DESIGNER `
    {INFOBASE_FLAG} '{INFOBASE_PATH}' `
    /N '{IB_USER}' `
    /P '{IB_PASSWORD}' `
    /DisableStartupMessages `
    /UpdateDBCfg -Dynamic+ -SessionTerminate force `
    -Extension {EXTENSION_NAME} `
    /Out '{LOG_PATH}' `
    /DumpResult '{RESULT_PATH}'
```

`-SessionTerminate force` is allowed only after the dev/test gate of Step 0.

Read the verdict: `{RESULT_PATH}` = `0`, exit code `0`, and `{LOG_PATH}` containing `Обновление информационной базы выполнено` / `Database configuration update completed` with no diagnostic lines.

## Update retry loop — mandatory failure handling for Steps 2–3

Loading and updating rarely succeed on a dirty state at the first attempt. Handle failures **iteratively**, never by re-running the same command blindly and never by declaring success from the exit code alone.

**1. Log first — after every attempt, success or not.** Read `{LOG_PATH}` in full after each Step 2 / Step 3 run. The platform can write errors to the log while formally exiting 0 (typical: `Неверное свойство объекта метаданных`, `Неизвестное имя типа`, `Ошибка при обновлении конфигурации базы данных`, `Конфигурация не соответствует`). A diagnostic line in the log = failed attempt, regardless of exit code.

**Classify success phrases before error stems** — the platform reports success with the same words (`Ошибок не обнаружено`, `Предупреждений: 0`), so a bare "contains `Ошибка` / `Error`" test flags a clean run as broken and starts a fix loop against working code. Order and full pattern list — `content/rules/designer-batch-checks.md → The success-phrase trap`. The Designer templates above carry **`/DumpResult '{RESULT_PATH}'`**: the file holds the batch result as a number (`0` = success) and is the cheapest of the three signals to read (same rule, *The verdict is three signals*); a missing file after a launch is a failed launch. `ibcmd` returns a reliable exit code and needs no equivalent.

**2. Terminate the Configurator before the next attempt.** A failed or hung Designer launch can stay alive and hold the configuration lock — every following attempt then dies with `База данных заблокирована` / exclusive-access errors that look like new problems but are not. For retry-aware runs launch Designer with a known process handle and a timeout:

```powershell
$p = Start-Process -FilePath '{PLATFORM_PATH}\bin\1cv8.exe' -ArgumentList $designerArgs -PassThru
if (-not $p.WaitForExit(600000)) { Stop-Process -Id $p.Id -Force }   # 10 min — raise for large configurations
```

Kill **only the PID started by this command**. Never blanket-kill `Get-Process 1cv8 | Stop-Process` — that would take down the user's own open Designer or client sessions. If the lock persists after your process is confirmed dead, the lock is foreign: report it and ask the user instead of killing anything else.

**3. Fix before retry.** Re-running against unchanged sources is forbidden (same no-change-repeat rule as for validators). Read the exact error from the log, fix its cause first — source XML/BSL defects are fixed through the `1c-metadata-manage` skill / normal code editing and re-validated (`verify_xml` / `syntaxcheck`) before the next attempt; parameter/connection errors are fixed in `.dev.env` or the command line. After a failed **load**, restart from Step 2 (load), not from Step 3 — the half-loaded state is not trustworthy; after a clean load with a failed **update**, retrying Step 3 alone is fine.

**4. Bounded budget — 3 full attempts.** If the third attempt still fails, stop: report the last log fragment, what was fixed between attempts, and the remaining error. Do not loop further and do not present a failed update as done.

## Full-snapshot mode (`/update1cbase all`) — optional

Loads the **effective snapshot**: main configuration + every extension from `EXTENSION_NAMES` (`.dev.env`, comma-separated, order = load order). Used by `/restore-testbase`, `/build-release` and whenever the user asks to deploy "with extensions".

- If `EXTENSION_NAMES` is empty, fall back to the regular single-target run above and note that in the report.
- **Pass 1 — main configuration:** Steps 2–3 as written, from `{EXPORT_PATH}`, without `-Extension` / `--extension`.
- **Pass per extension**, in `EXTENSION_NAMES` order: the same Steps 2–3 with `-Extension <Name>` / `--extension=<Name>`, sources from `{EXTENSIONS_PATH}\<Name>\`.
- **Every extension pass runs Step 2c between load and update**; a failure stops that pass before `/UpdateDBCfg`.
- A listed extension whose sources directory is missing or empty breaks the snapshot contract — stop and ask the user (skip it or abort); never skip silently.
- The **Update retry loop** applies to every pass with its own 3-attempt budget. A pass that exhausts its budget stops the mode; report which passes completed and which failed.

## Step 4. Final report

If the task also requests refreshing the source directory after the update, first complete all required apply stages, then follow `/loadfrom1cbase` with the same targets and appropriate scopes. Do not overwrite local changes or perform an unconditional full return dump. Without a requested refresh, no extra dump is required; report any baseline not maintained by the selected load tool before the next incremental export.

Briefly report the infobase, main configuration / extension, source directory, load scope (full / selected files / Git diff), tool, checks, apply result and any directory refresh separately. Include retry attempts, fixes and dynamic update / restructuring from the log. In full-snapshot mode, list every pass. A successful load with failed apply, or successful apply with failed return export, remains a partially completed workflow; list errors explicitly.
