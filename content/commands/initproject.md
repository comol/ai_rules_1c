---
description: Initialize a 1C project — test infobase from an existing IB / .cf / .dt, full source dump (cf + all cfe) into a git repository, first commit
userOnly: true
argumentHint: "[from-ib|from-cf <file.cf>|from-dt <file.dt>]"
---

# /initproject — one-time 1C project initialization

Produce the working layout every other full-cycle command relies on: main-configuration sources in `{EXPORT_PATH}`, extension sources in `{EXTENSIONS_PATH}\<Name>\`, a git repository with the first snapshot commit, and a filled `.dev.env`. Run it once per project; after that use `/loadfrom1cbase`, `/update1cbase`, `/deploy-and-test`, `/restore-testbase`.

Read `content/rules/extension-workspace.md`: one project and settings file, separate source roots per target, separate binary output. For a new empty Designer project with no established path choices, persist `EXPORT_PATH=src/cf` and `EXTENSIONS_PATH=src/cfe`; retain existing configured layouts. Do not create a separate project/settings copy per extension. If MCP setup is part of the request, map these roots to the discovered base graph `project_id` and verified extension layers via `content/rules/multi-contour-search.md`; a directory layout alone does not establish index coverage.

**EDT guard.** This command lays out a **Designer XML dump**. If `.dev.env` `USE_EDT=true` — or the directory already holds an EDT workspace (`.project`, `DT-INF/`, `src/Configuration.mdo`) — stop and settle the layout with the user first: which tree is authoritative, and whether the XML dump goes into a separate directory. Never initialize a dump on top of an EDT workspace. Canon — `content/rules/edt-workflow.md → The one thing that really changes: source format`.

**Double-init guard.** If `{EXPORT_PATH}` already contains dumped sources (`Configuration.xml` at its root), the project is already initialized — stop and suggest `/loadfrom1cbase` (refresh sources from the IB) or `/restore-testbase` (refresh the IB from sources) instead. Re-initializing over an existing dump requires an explicit user request.

## Step 0. Check `.dev.env` parameters

`.dev.env` is the single source of truth (created by the 1c-rules installer). If it is missing, ask the user to run `install.ps1 init` or copy `.dev.env.example` to `.dev.env`.

Parameters, classes and defaults — `content/rules/dev-standards-env.md §1`; Defaulted keys are never asked for. Keys used: `PLATFORM_PATH` (**blocking**), `INFOBASE_PATH` / `INFOBASE_KIND` (blocking for scenario A; written by scenario B), `IB_USER` / `IB_PASSWORD`, `EXTENSION_NAMES` (asked once in Step 2), `EXPORT_PATH`, `EXTENSIONS_PATH`, `LOG_PATH`, `IBCMD_CONFIG`. Answers to blocking keys are persisted back into `.dev.env`.

## Step 1. Choose the source scenario

Resolve from the argument, or ask once when ambiguous:

- **A. `from-ib`** (default when `INFOBASE_PATH` is filled and no argument was given) — an existing infobase is the source of truth. It must be a dev/test base (`.dev.env` `INFOBASE_ROLE=dev|test`) or a base the user explicitly designates as the dump source; with `INFOBASE_ROLE=prod` only the read-only dump touches it; never run initialization against a production base without an explicit statement that only a *dump* (read-only Step 3) will touch it.
- **B. `from-cf <file>` / `from-dt <file>`** — create a **new** test infobase from the template via the `1c-metadata-manage` skill's `db-ops` script `db-create.ps1 -UseTemplate <file>` (the 1C-infobase-operations hard gate — `AGENTS.md → Skills and Subagents`; do not compose ad-hoc `ibcmd` / `1cv8` lines). Ask for the target base path if not derivable, then persist `INFOBASE_PATH` (and `INFOBASE_KIND=file`) into `.dev.env`. A `.dt` template already contains data + configuration; a `.cf` template produces an empty base with the configuration.

## Step 2. Extensions inventory (`EXTENSION_NAMES`)

The "effective snapshot" of the project is **main configuration (cf) + all its extensions (cfe)**, and `EXTENSION_NAMES` (comma-separated, order = load order) is its contract.

- If `EXTENSION_NAMES` is filled — use it as is.
- If empty — resolve the extension list from the explicit setup request or established project inventory; otherwise ask once which extensions belong to the snapshot (in load order), or confirm there are none. Persist the answer into `.dev.env`. Do **not** silently assume "none". Preserve `EXTENSION_NAME` as the single-target default; do not replace it with this list. Load order does not certify the platform's runtime layer order.
- Automatic discovery of extensions from the base is allowed only with the exact platform syntax first verified through the docs MCP (`docsearch`) — never composed from memory (platform-capability check).

## Step 3. Dump the snapshot into the repository

Run the `/loadfrom1cbase` procedure (`content/commands/loadfrom1cbase.md` — single source of truth for the dump command lines, tool selection ibcmd-vs-Designer, and the result check) in **full-snapshot mode** (`/loadfrom1cbase all`): main configuration into `{EXPORT_PATH}`, then each extension from `EXTENSION_NAMES` into `{EXTENSIONS_PATH}\<Name>\`. Its dirty-working-tree guard applies unchanged.

If the inventory explicitly contains no extensions, run a full **main** dump with the extension option omitted, even when a pre-existing `EXTENSION_NAME` names a single-target default. Preflight all destinations for overlap and local changes before the first pass; verify each resulting descriptor against its expected target.

On a dump error, follow that command's result-check step — show the log fragment and stop; do not proceed to Step 4 with a partial snapshot.

## Step 4. Git repository and the first commit

1. If the project directory is not a git repository — run `git init`.
2. Ensure `.gitignore` exists and covers at least `.dev.env`, local `build/` output and the resolved `{RELEASE_PATH}`. Extend an existing `.gitignore`, never overwrite it.
3. Create the first snapshot commit (e.g. `init: 1C configuration sources (cf + cfe)`). If the repository **already had commits**, ask the user before committing on top of the existing history.

## Step 5. Final report

Report: the scenario used (A/B), the infobase (created or existing), the snapshot layout (`{EXPORT_PATH}`, `{EXTENSIONS_PATH}\<Name>` per extension), which `.dev.env` keys were written, the commit created. Suggest the next steps: `/update1cbase all` / `/deploy-and-test` for the develop-deploy cycle, `/restore-testbase` for rebuilding the test base from the snapshot.
