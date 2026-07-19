---
description: Load current repository files into the infobase defined in .dev.env and update the DB structure
---

# /update1cbase — load repository into an infobase

Load the configuration (`/LoadConfigFromFiles`) from the current repository directory into the infobase defined in `.dev.env`, then update the database structure (`/UpdateDBCfg`).

This command does not run tests and does not publish the infobase. Use `/deploy-and-test` to run tests after loading.

## Step 0. Check `.dev.env` parameters

`.dev.env` is the single source of truth for connection parameters (created by the 1c-rules installer at the project root). If it is missing, ask the user to run `install.ps1 init` or manually copy `.dev.env.example` to `.dev.env`.

If the project still has legacy `infobasesettings.md`, migrate values to `.dev.env` (same key names, `KEY=value` format instead of a markdown list), preserving already-filled `.dev.env` keys, and delete the legacy file after successful migration. The ruleset has no other connection-settings location.

Used `.dev.env` keys (behavior of an empty value in parentheses):

| Key | Purpose |
|---|---|
| `PLATFORM_PATH` | Platform installation directory containing `bin\1cv8.exe` — **blocking** |
| `INFOBASE_PATH` | File infobase path or server connection string — **blocking** |
| `INFOBASE_KIND` | `file` or `server` (empty = `file`) |
| `IB_USER` / `IB_PASSWORD` | Credentials (empty = no authentication / no password; `/N` / `/P` / `--user` / `--password` are omitted) |
| `EXTENSION_NAME` | Extension name (empty = main configuration) |
| `EXPORT_PATH` | Source directory (empty = repository root) |
| `LOG_PATH` | Designer log file (empty = `$env:TEMP\1cv8.log` on Windows / `$TMPDIR/1cv8.log` on POSIX) |
| `IBCMD_CONFIG` | Standalone server `config.yml` for `ibcmd` (empty = Designer fallback) |

Ask-policy (canon — `dev-standards-env.md`): only `INFOBASE_PATH` and `PLATFORM_PATH` are blocking — if either is empty, ask the user once and write the value to `.dev.env`. **Never ask up front** about the defaulted keys — apply the defaults from the table silently; re-ask `IB_USER` / `IB_PASSWORD` only if the platform itself returns an authentication error, `LOG_PATH` only if the resolved path turns out to be non-writable. An empty password is a fully valid configuration for dev / test infobases.

When substituting `.dev.env` values into the templates below:

- if `LOG_PATH` is empty, replace `{LOG_PATH}` with `"$env:TEMP\1cv8.log"` (PowerShell expands the env var when the string is double-quoted);
- resolve `{INFOBASE_FLAG}` once: `/F` for empty / `file`, `/S` for `server`; reject any other `INFOBASE_KIND`.

Before running, make sure `{EXPORT_PATH}` contains dumped configuration sources (for example, `Configuration.xml` at the root or in the extension subdirectory). If no sources exist, stop and tell the user.

## Step 1. Choose tool: `ibcmd` or Designer

1. Check whether the utility exists: `Test-Path '{PLATFORM_PATH}\bin\ibcmd.exe'`.
2. Check whether `IBCMD_CONFIG` is filled in `.dev.env`.
3. If **both conditions are true**, use **Steps 2a and 3a (`ibcmd`)**.
4. Otherwise use **Steps 2b and 3b (Designer)**.

`ibcmd infobase config` does not apply to 1C cluster infobases; for server cluster infobases always use Designer.

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

`--session-terminate=force` forcibly terminates active sessions. Use it only on a dev/test infobase. On production, replace it with `--session-terminate=prompt` (or remove the key; default is `auto`) and agree on an update window with the user.

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
    -Extension {EXTENSION_NAME} `
    /Out '{LOG_PATH}'
```

Remove empty optional keys (`/N`, `/P`, `-Extension`). For the main configuration, remove `-Extension {EXTENSION_NAME}` entirely.

Read `{LOG_PATH}`. On errors, show the relevant log fragment to the user and **do not continue** to Step 3b.

Wait 5-10 seconds so the platform releases the configuration lock.

## Step 3b. Update DB structure through Designer

```powershell
& '{PLATFORM_PATH}\bin\1cv8.exe' DESIGNER `
    {INFOBASE_FLAG} '{INFOBASE_PATH}' `
    /N '{IB_USER}' `
    /P '{IB_PASSWORD}' `
    /DisableStartupMessages `
    /UpdateDBCfg -Dynamic+ -SessionTerminate force `
    -Extension {EXTENSION_NAME} `
    /Out '{LOG_PATH}'
```

`-SessionTerminate force` forcibly terminates active sessions. Use it only on a dev/test infobase. On production, remove this key and agree on an update window with the user.

Read `{LOG_PATH}`. Success means `Обновление информационной базы выполнено` / `Database configuration update completed`.

## Step 4. Final report

Briefly report which infobase was updated, which directory was loaded, which tool was used (`ibcmd` or Designer), and whether dynamic update was applied or restructuring was required (visible in the log). List errors separately.
