---
description: Load the configuration into the test infobase from .dev.env and check the result in the 1C interface — QA MCP first, the web client as fallback
---

# /deploy-and-test — deploy to test infobase + UI tests

Deploy the current configuration to the test infobase defined in `.dev.env`, then check the result in the 1C interface: through QA MCP in the thin client when it is connected, otherwise in the web client at `INFOBASE_PUBLISH_URL`. UI testing is gated by `UI_TESTING`; see Step 4.

Resolve project, main/named-extension target and source root through `content/rules/extension-workspace.md` before substitution. Keep that target through deployment, applicability checks and scenarios; a single-extension task uses its own root, and does not rewrite the primary `EXTENSION_NAME`. MCP-backed test preparation must use the same verified project/layer; confirm the live test connection is the intended infobase before attributing its results.

When the user asks to deploy the full snapshot ("all" / "with extensions"), resolve inventory even if `EXTENSION_NAMES` is empty, then run Steps 2–3 as main followed by each selected extension per `/update1cbase → Full-snapshot mode` (`content/commands/update1cbase.md`). Confirmed no extensions means main only; a stored single-extension default cannot narrow `all`.

**Load scope is owned by `/update1cbase → Select load scope`.** For partial / Git deployment, follow that command's complete load → checks → apply sequence, including file-list validation and baseline handling, then continue here at Step 4. Do not execute the full-load examples below as well. A failed load or apply blocks UI tests. A requested return export follows `/loadfrom1cbase` after apply with the same target and scope guards (`content/rules/config-sync-contract.md`).

## Step 0. Check `.dev.env` parameters

`.dev.env` is the single source of truth for all parameters (created by the 1c-rules installer at the project root). If it is missing, ask the user to run `install.ps1 init` or copy `.dev.env.example` to `.dev.env`.

If the project still has legacy `infobasesettings.md`, migrate values to `.dev.env`, preserving already-filled `.dev.env` keys, and delete the legacy file after successful migration. The ruleset has no other location for connection settings or the web publication URL.

Parameters, classes and defaults — `content/rules/dev-standards-env.md §1`; Defaulted keys are never asked for. Keys read: `PLATFORM_PATH`, `INFOBASE_PATH` (**blocking** — if either is empty, ask once and write the value to `.dev.env`), `INFOBASE_KIND`, `IB_USER` / `IB_PASSWORD`, `EXTENSION_NAME`, `EXTENSION_NAMES` (full-snapshot deploy), `EXPORT_PATH`, `EXTENSIONS_PATH`, `LOG_PATH`, `RESULT_PATH`, `INFOBASE_PUBLISH_URL`, `UI_TESTING`, `MCP_QA_CLIENT_VISIBLE` and `TOOL_QA` (Step 4), `IBCMD_CONFIG`.

When substituting `.dev.env` values into the templates below, resolve `{INFOBASE_FLAG}` once from the effective `INFOBASE_KIND` (`/F` for `file`, `/S` for `server`; reject any other value), and substitute resolved `{LOG_PATH}` / `{RESULT_PATH}` values that contain `$env:` double-quoted — single quotes do not expand it. Delete a stale `{RESULT_PATH}` file before every Designer launch.

Before running, inherit `/update1cbase`'s source-identity, completeness and selection preflight for every chosen target. A `Configuration.xml` somewhere under `EXPORT_PATH` alone is insufficient, and a partial dump cannot feed a full deployment.

**EDT gate:** when `.dev.env` `USE_EDT=true`, the same source-format check as `/update1cbase` applies — Steps 2–3 load a Designer XML dump, not an EDT `src/**/*.mdo` tree, and only one deployment owner (this command **or** EDT's `update_database`) may act on the infobase in a run. Canon — `content/rules/edt-workflow.md`.

This command uses forced session termination while applying the DB configuration. The target must be an explicitly identified dev/test infobase: `.dev.env` `INFOBASE_ROLE=dev|test` identifies it, `prod` refuses the deploy steps (canon `content/rules/dev-standards-env.md → INFOBASE_ROLE`). If the role is empty and the current context does not establish it, stop before Step 2 and ask the user to confirm the target — the load already changes the infobase configuration; never infer that an arbitrary `.dev.env` points to a test base.

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
    /DisableStartupMessages /DisableStartupDialogs `
    /LoadConfigFromFiles '{EXPORT_PATH}' `
    -updateConfigDumpInfo `
    -Extension {EXTENSION_NAME} `
    /Out '{LOG_PATH}' `
    /DumpResult '{RESULT_PATH}'
```

Remove empty optional keys (`/N`, `/P`, `-Extension`).

Read the verdict from all three signals (`{RESULT_PATH}` = `0`, exit code, `{LOG_PATH}` containing `Конфигурация успешно загружена` / `Configuration successfully loaded`). Wait 5-10 seconds.

## Step 3b. Update DB structure through Designer

```powershell
& '{PLATFORM_PATH}\bin\1cv8.exe' DESIGNER `
    {INFOBASE_FLAG} '{INFOBASE_PATH}' `
    /N '{IB_USER}' `
    /P '{IB_PASSWORD}' `
    /DisableStartupMessages /DisableStartupDialogs `
    /UpdateDBCfg -Dynamic+ -SessionTerminate force `
    -Extension {EXTENSION_NAME} `
    /Out '{LOG_PATH}' `
    /DumpResult '{RESULT_PATH}'
```

`-SessionTerminate force` forcibly terminates active sessions. It is allowed only after the dev/test confirmation above. On production, remove this key and agree on an update window with the user.

Read the verdict from all three signals (`{RESULT_PATH}`, exit code, `{LOG_PATH}`). On errors, show the relevant log fragment and **do not run** UI tests.

## Step 3c. Applicability check — mandatory when an extension is deployed

Whenever this run loads an extension (`EXTENSION_NAME` filled, or a full-snapshot pass over `EXTENSION_NAMES`), run `/update1cbase → Step 2c` (`content/commands/update1cbase.md` — the `/CheckModules` → `/CheckCanApplyConfigurationExtensions` → `/CheckConfig` ladder with the three-signal verdict) **between the load (Step 2) and the DB update (Step 3)**, in the `ibcmd` path as well. Stop at the first failure and do not run Step 3. For the main configuration alone the ladder is optional — run `/CheckModules` and `/CheckConfig` (without `-Extension`) when the change is large (whole-snapshot deploy, release build) or when the Gate 1–3 MCP validators were not exposed in this session.

## Failure handling for Steps 2–3 — retry loop

Apply the **Update retry loop** from `/update1cbase` (`content/commands/update1cbase.md → Update retry loop`) verbatim: read `{LOG_PATH}` after every attempt (diagnostics in the log override exit code 0 — classify the platform's success phrases first, `content/rules/designer-batch-checks.md → The success-phrase trap`); on failure terminate the hung / failed Configurator by its own PID only (never blanket-kill `1cv8` processes); fix the logged cause before any retry (re-running unchanged is forbidden); after a failed load restart from Step 2; at most 3 full attempts, then stop and report. UI tests (Step 4) run only after a clean pass.

## Step 4. UI tests

UI testing is controlled by `UI_TESTING` (values and default — `dev-standards-env.md → "UI_TESTING — UI-testing mode"`). Resolve the effective value and act on it:

- **`off`** — skip this step; report the effective policy and point to `/uitests essential`, `/uitests on` or `/uitests manual`. Apply an explicit enable-and-run instruction through `/uitests` before resolving this branch; it needs no second toggle confirmation.
- **`manual`** — run this step **only if the user explicitly asked to run UI tests** in the current request. Otherwise skip it and finish with: "UI tests skipped: `UI_TESTING=manual` — run only on explicit request."
- **`essential`** (default) — run automatically, limited to the important new or changed user-visible behaviour of the deployed change; name what was left unchecked.
- **`auto`** — run every applicable scenario automatically.

Pick the route by `ui-testing-tools.md → Route order`: QA MCP (Step 4a) when its tools are exposed and `TOOL_QA` allows it, else the web client (Steps 4b–4c). If no route is available — no QA MCP and an empty `INFOBASE_PUBLISH_URL` — skip an automatic run and mark affected criteria unverified with this reason. For an explicitly requested UI run, ask for the missing prerequisite and continue independent work; do not claim the tests passed. Policy `off` takes precedence and does not trigger this question.

### Step 4a. QA MCP in the thin client (main route)

Load `content/skills/1c-qa-testing/SKILL.md` and `content/rules/qa-testclient.md`. The DB update of Step 3 ended the infobase sessions, so a test client started before it is stale: check `qa-testclient.ps1 status`, close a client you started with `stop`, and start a fresh one for `INFOBASE_PATH` with the window from `MCP_QA_CLIENT_VISIBLE`. Then `qa_start`, run the scenarios by the skill's observe → act → assert loop with a journal, confirm data effects through `1c-data-mcp` where the form does not show them, and stop the client you started. A step QA MCP cannot cover falls back to the web client for that step only.

### Step 4b. Browser-tool preflight (web route, before any navigation)

Load `content/rules/ui-testing-tools.md` and run its **Preflight before web UI tests** gate. Short form:

1. Check CLI (`agent-browser --version`) and/or MCP tools (`agent_browser_*`).
2. If missing — **stop**, ask in Russian whether to run `/install-agent-browser` now (saves tokens vs screenshot/vision). Do not open `{INFOBASE_PUBLISH_URL}` until the user answers.
3. On yes — execute `/install-agent-browser`, then continue.
4. On no — continue with the built-in browser MCP; note the higher token cost once.
5. Silent skip of this ask = defect.

### Step 4c. Run web scenarios

Open `{INFOBASE_PUBLISH_URL}` with the tool chosen in 4b. Prefer **`agent-browser`** (a11y snapshots); built-in browser MCP only after decline / no-operator fallback; **`agent-desktop`** (`/install-agent-desktop`) only for native windows outside the 1C testing model — never for a web page, never a home-grown screenshotter/OCR. Rules:

Driving rules — `content/rules/web-client-driving.md`: headed run, snapshot / refs observe loop, human-like typing with its paste fallback, TAB between fields, waits, screenshots of key steps as evidence.

## Step 5. Final report

Briefly report which infobase was updated, which tool was used (`ibcmd` or Designer), which UI route ran (QA MCP with its executor, or the web client, and why), which test scenarios passed/failed or stayed unverified, the journal path, and list errors separately with log fragments and screenshots.

Identify the project and each main/extension pass, its load/check/apply outcome and relevant active-extension mismatches. UI success does not prove that an omitted extension was deployed or that another MCP project's sources describe this infobase.

Update the extension's existing README or delivery description with the checked combination and actual evidence per `content/rules/extension-workspace.md → Checked compatibility`. Keep source, loaded configuration, applied DB and MCP freshness distinct in any continuation handoff; skipped tests stay unrun, and this target's result does not certify other extensions.

When scenarios failed and the user wants the failures driven to green, do not improvise ad-hoc retries — suggest `/test-fix-loop` (`content/commands/test-fix-loop.md`): the closed deploy → test → fix → redeploy loop with its own iteration budget and no-change-repeat rules. It runs only on explicit invocation.
