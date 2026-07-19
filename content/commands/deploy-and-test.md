---
description: Load the configuration into the test infobase from .dev.env and run UI tests in the web client
---

# /deploy-and-test — deploy to test infobase + UI tests

Deploy the current configuration to the test infobase defined in `.dev.env`, then optionally run UI tests in the web client at `INFOBASE_PUBLISH_URL`. UI testing is an opt-in step gated by `UI_TESTING` (default `manual` — run only on explicit request); see Step 4.

## Step 0. Check `.dev.env` parameters

`.dev.env` is the single source of truth for all parameters (created by the 1c-rules installer at the project root). If it is missing, ask the user to run `install.ps1 init` or copy `.dev.env.example` to `.dev.env`.

If the project still has legacy `infobasesettings.md`, migrate values to `.dev.env`, preserving already-filled `.dev.env` keys, and delete the legacy file after successful migration. The ruleset has no other location for connection settings or the web publication URL.

Used keys (behavior of an empty value in parentheses):

| Key | Purpose |
|---|---|
| `PLATFORM_PATH` | Platform installation directory containing `bin\1cv8.exe` — **blocking** |
| `INFOBASE_PATH` | File infobase path or server connection string — **blocking** |
| `INFOBASE_KIND` | `file` or `server` (empty = `file`) |
| `IB_USER` / `IB_PASSWORD` | Credentials (empty = no authentication / no password; `/N` / `/P` / `--user` / `--password` are omitted) |
| `EXTENSION_NAME` | Extension name (empty = main configuration) |
| `EXPORT_PATH` | Source directory (empty = repository root) |
| `LOG_PATH` | Designer log file (empty = `$env:TEMP\1cv8.log` on Windows / `$TMPDIR/1cv8.log` on POSIX) |
| `INFOBASE_PUBLISH_URL` | Test infobase web publication URL for UI tests (empty = skip UI tests, deploy only) |
| `UI_TESTING` | Web UI-testing mode: `manual` (empty = default) / `auto` / `off` — governs whether Step 4 runs (see Step 4) |
| `IBCMD_CONFIG` | Standalone server `config.yml` for `ibcmd` (empty = Designer fallback) |

Ask-policy (canon — `dev-standards-env.md`): only `INFOBASE_PATH` and `PLATFORM_PATH` are blocking — if either is empty, ask the user once and write the value to `.dev.env`. **Never ask up front** about the defaulted keys — apply the defaults from the table silently; re-ask `IB_USER` / `IB_PASSWORD` only if the platform itself returns an authentication error, `LOG_PATH` only if the resolved path turns out to be non-writable. An empty password is a fully valid configuration for dev / test infobases.

When substituting `.dev.env` values into the templates below:

- if `LOG_PATH` is empty, replace `{LOG_PATH}` with `"$env:TEMP\1cv8.log"` (PowerShell expands the env var when the string is double-quoted);
- resolve `{INFOBASE_FLAG}` once: `/F` for empty / `file`, `/S` for `server`; reject any other `INFOBASE_KIND`.

Before running, make sure `{EXPORT_PATH}` contains dumped configuration sources (for example, `Configuration.xml` at the root or in the extension subdirectory). If no sources exist, stop and tell the user.

This command uses forced session termination while applying the DB configuration. The target must be an explicitly identified dev/test infobase. If the current context does not establish that, stop before Step 3 and ask the user to confirm the target; never infer that an arbitrary `.dev.env` points to a test base.

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

`--session-terminate=force` forcibly terminates active sessions. It is allowed only after the dev/test confirmation above. On production, replace it with `--session-terminate=prompt` (or remove the key; default is `auto`) and agree on an update window with the user.

Read `{LOG_PATH}`. On errors, show the relevant log fragment and **do not run** UI tests. Continue to **Step 4**.

## Step 2b. Load configuration through Designer (fallback)

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

Remove empty optional keys (`/N`, `/P`, `-Extension`).

Read `{LOG_PATH}`; it must contain `Конфигурация успешно загружена` / `Configuration successfully loaded`. Wait 5-10 seconds.

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

`-SessionTerminate force` forcibly terminates active sessions. It is allowed only after the dev/test confirmation above. On production, remove this key and agree on an update window with the user.

Read `{LOG_PATH}`. On errors, show the relevant log fragment and **do not run** UI tests.

## Step 4. UI tests in the web client

UI testing is an **opt-in** step controlled by `UI_TESTING` (empty = `manual`; see `dev-standards-env.md → "UI_TESTING — web UI-testing mode"`). It burns a lot of tokens, so it is not run by default. Resolve whether to run this step:

- **`UI_TESTING=off`** — skip this step; finish with: "UI tests skipped: web testing is disabled in `.dev.env` (`UI_TESTING=off`)."
- **`UI_TESTING=manual`** (or empty / any invalid value) — run this step **only if the user explicitly asked to run UI tests** in the current request. Otherwise skip it and finish with: "UI tests skipped: `UI_TESTING=manual` — run only on explicit request."
- **`UI_TESTING=auto`** — run this step automatically (subject to the `INFOBASE_PUBLISH_URL` check below).

If UI testing is to run but `INFOBASE_PUBLISH_URL` is empty, skip this step and finish with: "UI tests skipped: `INFOBASE_PUBLISH_URL` is not set in `.dev.env`."

Otherwise open `{INFOBASE_PUBLISH_URL}` through the MCP browser and run the test scenarios. Rules:

- **MUST** use delayed human-like typing when filling fields.
- Use TAB to move between form fields.
- Wait for elements to load before interacting.
- Take screenshots at key steps for documentation.

## Step 5. Final report

Briefly report which infobase was updated, which tool was used (`ibcmd` or Designer), which test scenarios passed/failed, and list errors separately with log fragments and screenshots.
