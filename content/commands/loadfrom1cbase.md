---
description: Dump the configuration from the infobase defined in .dev.env into the current repository files
argumentHint: "[full|changes|partial|all]"
---

# /loadfrom1cbase — dump from infobase to repository

Refresh configuration files from the infobase defined in `.dev.env`: full dump, incremental refresh or selected-object export. Read `content/rules/getconfigfiles.md → Configuration file synchronization contract` before choosing the scope. With `all` (or an explicit "with extensions" request), dump the **full snapshot** — main configuration plus every extension from `EXTENSION_NAMES`; see "Full-snapshot mode" below.

This is the directory-refresh stage of the workflow shared with `/update1cbase`. It does not load files into the infobase or apply the database configuration.

## Select scope

- `full` / `all`: deliberately dump a complete snapshot.
- `changes`: update an existing dump from its `ConfigDumpInfo.xml`; Designer uses `-update`, `ibcmd` uses `--sync`. Without a usable baseline, stop this mode and prepare a full dump into a new directory or obtain authorization for overwriting the existing one. Do not add `-force` as an automatic retry.
- `partial`: follow `/getconfigfiles` with the selected objects in `repoobjects.txt`; then return to this command's result report. This is a supported branch of directory refresh, not a full dump followed by file filtering.
- No explicit mode: use the scope already established by the task; selected objects imply `partial`, a repeated refresh of a complete dump with a valid baseline implies `changes`, and a first complete export implies `full`. State the choice. An explicit partial request never falls back to full automatically.

For a change report (`-getChanges`) or a delta directory (`-configDumpInfoForChanges`), use the Designer modes from the same contract. A report-only operation does not count as refreshing the directory.

**EDT gate:** the dump this command writes is in **Designer XML format**. In a project developed in 1C:EDT (`.dev.env` `USE_EDT=true`) whose working tree is an EDT (`src/**/*.mdo`) workspace, dumping into that tree is wrong — pick a separate target directory and state that the result is a dump, not the workspace; bringing changes back into EDT is a separate, confirmed step (`content/rules/edt-workflow.md`).

## Step 0. Check `.dev.env` parameters

`.dev.env` is the single source of truth for connection parameters (created by the 1c-rules installer at the project root). If it is missing, ask the user to run `install.ps1 init` or manually copy `.dev.env.example` to `.dev.env`.

If the project still has legacy `infobasesettings.md`, migrate values to `.dev.env` (same key names, `KEY=value` format instead of a markdown list), preserving already-filled `.dev.env` keys, and delete the legacy file after successful migration. The ruleset has no other connection-settings location.

Parameters, classes and defaults — `content/rules/dev-standards-env.md §1`; Defaulted keys are never asked for. Keys read: `PLATFORM_PATH`, `INFOBASE_PATH` (**blocking** — if either is empty, ask once and write the value to `.dev.env`), `INFOBASE_KIND`, `IB_USER` / `IB_PASSWORD`, `EXTENSION_NAME`, `EXTENSION_NAMES` (`all` mode), `EXPORT_PATH`, `EXTENSIONS_PATH`, `LOG_PATH`, `IBCMD_CONFIG`.

When substituting `.dev.env` values into the templates below, resolve `{INFOBASE_FLAG}` once from the effective `INFOBASE_KIND` (`/F` for `file`, `/S` for `server`; reject any other value), and substitute a resolved `{LOG_PATH}` that contains `$env:` double-quoted — single quotes do not expand it.

Before every dump mode, inspect `git status --short` for the resolved destination (and inspect existing files if it is not under Git). The dump may overwrite source files and the version baseline. If affected files contain local changes, preserve them in a separate destination or obtain explicit overwrite authorization; never discard them silently. In a single-extension run, use that extension's source directory consistently.

## Step 1. Choose tool: `ibcmd` or Designer

1. Check whether the utility exists: `Test-Path '{PLATFORM_PATH}\bin\ibcmd.exe'`.
2. Check whether `IBCMD_CONFIG` is filled in `.dev.env`.
3. If **both conditions are true**, use **Step 2a (`ibcmd`)**.
4. Otherwise use **Step 2b (Designer)**.

`ibcmd infobase config` does not apply to 1C cluster infobases; for server cluster infobases always use Designer.

## Step 2a. Export through `ibcmd` (preferred)

```powershell
& '{PLATFORM_PATH}\bin\ibcmd.exe' infobase config export `
    --config='{IBCMD_CONFIG}' `
    --user='{IB_USER}' `
    --password='{IB_PASSWORD}' `
    --extension={EXTENSION_NAME} `
    '{EXPORT_PATH}' *>&1 | Tee-Object -FilePath '{LOG_PATH}'
```

Remove empty optional keys (`--user`, `--password`, `--extension`). Add `--sync` for the selected `changes` mode only; omit it for `full` / `all`. Partial export follows `/getconfigfiles`. Use Designer for comparison / external-baseline delta modes rather than inventing `ibcmd` flags.

`ibcmd` writes diagnostics to stdout/stderr; `Tee-Object` duplicates it into `{LOG_PATH}`. Continue to **Step 3**.

## Step 2b. Export through Designer (fallback)

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
    /DumpConfigToFiles '{EXPORT_PATH}' `
    -Format Hierarchical `
    -Extension {EXTENSION_NAME} `
    /Out '{LOG_PATH}' `
    /DumpResult '{RESULT_PATH}'
```

Remove empty optional keys (`/N`, `/P`, `-Extension`). When exporting the main configuration, remove `-Extension {EXTENSION_NAME}` entirely. Use the existing dump format (`Plain` when applicable). For `changes`, add `-update`; for `full`, add neither `-update` nor `-listFile`. For `partial`, run the selected-object template in `/getconfigfiles` instead. Resolve `RESULT_PATH` from `.dev.env` / its documented default and remove a stale result before each launch.

The specified directory is the dump root; preserve the selected format's object subdirectories. Keep log, result and selection files outside that tree (especially an empty delta destination).

## Step 3. Check result

1. Read the complete log and process exit code; for Designer also require a fresh `{RESULT_PATH}` with `0`. Classify success phrases before error stems per `content/rules/designer-batch-checks.md`. Check the expected artifacts for the selected mode: source files for full / partial, a valid baseline for changes, or the report file for comparison (an empty report is valid).
2. If errors exist, show the relevant log fragment to the user and stop.
3. Briefly list which top-level object directories appeared or changed according to `git status`, without content diffs.
4. Report the target, direction, scope, baseline and result. When called after `/update1cbase`, distinguish successful database apply from successful directory refresh; a failed export does not undo a completed apply.

## Full-snapshot mode (`/loadfrom1cbase all`) — optional

Dumps the **effective snapshot**: main configuration + every extension from `EXTENSION_NAMES` (`.dev.env`, comma-separated, order preserved). Used by `/initproject` and whenever the user asks for a dump "with extensions".

- If `EXTENSION_NAMES` is empty, fall back to the regular single-target run above and note that in the report.
- **Pass 1 — main configuration:** Steps 2–3 as written, into `{EXPORT_PATH}`, without `-Extension` / `--extension`.
- **Pass per extension**, in `EXTENSION_NAMES` order: the same Step 2a/2b template with `-Extension <Name>` / `--extension=<Name>`, target directory `{EXTENSIONS_PATH}\<Name>\` (create missing directories). Run the Step 3 check after **every** pass.
- `all` selects full exports for every pass. Selected-object and incremental runs use an explicit single-target scope; do not carry one object's list or one baseline across different extensions.
- The Step 0 dirty-working-tree guard covers `{EXTENSIONS_PATH}` as well as `{EXPORT_PATH}`.
- A failed pass stops the mode — do not continue to the next extension over a broken dump; report which passes completed.
