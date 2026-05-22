---
description: Load the configuration into the test infobase from .dev.env and run UI tests in the web client
---

# /deploy-and-test — deploy to test infobase + UI tests

Deploy the current configuration to the test infobase defined in `.dev.env`, then run UI tests in the web client at `INFOBASE_PUBLISH_URL`.

## Step 0. Check `.dev.env` parameters

`.dev.env` is the single source of truth for all parameters (created by the 1c-rules installer at the project root). If it is missing, ask the user to run `install.ps1 init` or copy `.dev.env.example` to `.dev.env`.

If the project still has legacy `infobasesettings.md`, migrate values to `.dev.env`, preserving already-filled `.dev.env` keys, and delete the legacy file after successful migration. The ruleset has no other location for connection settings or the web publication URL.

Used keys:

| Key | Purpose |
|---|---|
| `PLATFORM_PATH` | Platform installation directory containing `bin\1cv8.exe` |
| `INFOBASE_KIND` | `file` or `server` |
| `INFOBASE_PATH` | File infobase path or server connection string |
| `IB_USER` / `IB_PASSWORD` | Credentials; empty = no authentication, `/N` / `/P` (or `--user` / `--password`) are omitted. An empty password is a fully valid configuration for dev / test infobases — **do not ask up front**. Re-ask only if the platform itself returns an authentication error. |
| `EXTENSION_NAME` | Extension name; empty means main configuration |
| `EXPORT_PATH` | Source directory; empty means repository root |
| `LOG_PATH` | Designer log file; empty resolves to `$env:TEMP\1cv8.log` (Windows) / `$TMPDIR/1cv8.log` (POSIX). **Do not ask up front** — any writable path works equally well. Re-ask only if the resolved path turns out to be non-writable. |
| `INFOBASE_PUBLISH_URL` | Test infobase web publication URL for UI tests. If empty, skip UI tests and only deploy |
| `IBCMD_CONFIG` | Path to standalone server `config.yml` for `ibcmd`, optional |

Critical deploy fields are `INFOBASE_PATH` and `PLATFORM_PATH`. If either is empty, ask the user and write the value to `.dev.env`. **Do not** ask about `IB_USER` / `IB_PASSWORD` / `LOG_PATH` when they are empty; apply the documented defaults silently.

When substituting `.dev.env` values into the templates below: if `LOG_PATH` is empty, replace `{LOG_PATH}` with `"$env:TEMP\1cv8.log"` (PowerShell expands the env var when the string is double-quoted).

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

Remove empty optional keys (`--user`, `--password`, `--extension`). On errors, show the relevant log fragment and **do not run** Step 3a.

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

Read `{LOG_PATH}`. On errors, show the relevant log fragment and **do not run** UI tests. Continue to **Step 4**.

## Step 2b. Load configuration through Designer (fallback)

```powershell
& '{PLATFORM_PATH}\bin\1cv8.exe' DESIGNER `
    /F '{INFOBASE_PATH}' `
    /N '{IB_USER}' `
    /P '{IB_PASSWORD}' `
    /DisableStartupMessages `
    /LoadConfigFromFiles '{EXPORT_PATH}' `
    -Extension {EXTENSION_NAME} `
    /Out '{LOG_PATH}'
```

Remove empty optional keys (`/N`, `/P`, `-Extension`). For a server infobase, use `/S` instead of `/F`.

Read `{LOG_PATH}`; it must contain `Конфигурация успешно загружена` / `Configuration successfully loaded`. Wait 5-10 seconds.

## Step 3b. Update DB structure through Designer

```powershell
& '{PLATFORM_PATH}\bin\1cv8.exe' DESIGNER `
    /F '{INFOBASE_PATH}' `
    /N '{IB_USER}' `
    /P '{IB_PASSWORD}' `
    /DisableStartupMessages `
    /UpdateDBCfg -Dynamic+ -SessionTerminate force `
    -Extension {EXTENSION_NAME} `
    /Out '{LOG_PATH}'
```

Read `{LOG_PATH}`. On errors, show the relevant log fragment and **do not run** UI tests.

## Step 4. UI tests in the web client

If `INFOBASE_PUBLISH_URL` is empty, skip this step and finish with: "UI tests skipped: `INFOBASE_PUBLISH_URL` is not set in `.dev.env`."

Otherwise open `{INFOBASE_PUBLISH_URL}` through the MCP browser and run the test scenarios. Rules:

- **MUST** use delayed human-like typing when filling fields.
- Use TAB to move between form fields.
- Wait for elements to load before interacting.
- Take screenshots at key steps for documentation.

## Step 5. Final report

Briefly report which infobase was updated, which tool was used (`ibcmd` or Designer), which test scenarios passed/failed, and list errors separately with log fragments and screenshots.
