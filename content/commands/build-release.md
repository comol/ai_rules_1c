---
description: Build release artifacts from committed sources — .cf for the main configuration and .cfe per extension, with optional version bump, changelog and git tag
argumentHint: "[<version>] [--no-tag]"
---

# /build-release — release artifacts from the git snapshot

Build real binary artifacts from the **committed** sources of the selected targets: `.cf` for main, `.cfe` for each named extension, with an optional version bump, `CHANGELOG.md` entry and git tag. Resolve targets through `content/rules/extension-workspace.md`: an explicit main/extension task wins; a requested full snapshot uses main plus `EXTENSION_NAMES`; without a task restriction, a populated list selects that snapshot, otherwise use the single-target default. An extension-only build must not materialize one extension and then dump the unrelated main `.cf`. The command ends at artifacts + tag; it never deploys to production itself (see the checklist at the end).

## Step 0. Check `.dev.env` parameters

Parameters, classes and defaults — `content/rules/dev-standards-env.md §1`; Defaulted keys are never asked for. Blocking: `PLATFORM_PATH`, `INFOBASE_PATH` (the assembly base — a dev/test base used to materialize the git snapshot; the dev/test confirmation of `/deploy-and-test` applies). Also read: `INFOBASE_KIND`, `IB_USER` / `IB_PASSWORD`, `EXTENSION_NAME`, `EXTENSION_NAMES`, `EXPORT_PATH`, `EXTENSIONS_PATH`, `RELEASE_PATH`, `LOG_PATH`, `RESULT_PATH`, `IBCMD_CONFIG`. Resolve each target's source root, descriptor and completeness before any base mutation. EDT sources require the verified export/assembly route in `content/rules/edt-workflow.md`; never feed `.mdo` sources into the XML loader.

## Step 1. Clean-tree gate

A release artifact must be reproducible from a commit. Check `git status --short` for the resolved source roots of every selected target and any required source dependencies: uncommitted source changes → stop and ask the user to commit or stash. Verify the inputs are tracked in that commit; a selected-object dump is not a complete assembly input. Record `git rev-parse --short HEAD` — it goes into the report.

## Step 2. Version

Read `Version` from each selected target's `Configuration.xml`. For the optional version argument, the target is main in a full snapshot, or the selected target in a single-target build. Do not bump every extension implicitly. Keep extension versions independent; record a fallback to the main version only when the extension has no version and that main version is verified.

- No argument → build with the current version as is; offer a bump only if the version equals the previous release tag.
- `<version>` argument (or an explicit bump request) → update the `Version` property in the sources. This is a metadata edit: go through the `1c-metadata-manage` tooling where it covers configuration properties; otherwise a minimal hand edit of the single property value is acceptable — run `verify_xml` on the file afterwards and state `Metadata tooling: hand-edit — Version property` in the report (`verification-gates.md → Gate 5` exception discipline). Commit the bump before building (it is part of the released state).

## Step 3. Materialize the snapshot in the assembly base

Before materialization, follow `content/rules/extension-workspace.md → Preserve extension identity`: retain the known extension/object identifiers and borrowed links, and investigate unexpected identifier changes in the selected inputs.

Run the `/update1cbase` procedure (single source of truth for command lines, tool selection, checks and the Update retry loop) for **exactly the selected targets**: full-snapshot mode only for the full snapshot, otherwise an explicitly resolved main or named-extension pass. For an extension-only build, establish the assembly base's expected main configuration and relevant dependencies before applicability checks; do not silently deploy other project targets. A failed load, validation or apply stops the build before dumping artifacts. This ties output to the materialized committed source state; do not certify unrelated extensions already in the assembly base as part of this build.

## Step 4. Dump the artifacts

Resolve the output root: an explicit local build destination (for example `build/`) for this invocation, otherwise `{RELEASE_PATH}` and its documented default. Create the required directories; keep them outside source roots and in `.gitignore`. Use the existing artifact layout if established; otherwise separate `cf/` and `cfe/<Name>/`. In the examples below `{OUTPUT_ROOT}` denotes this resolved local value, not a new environment key. Via the `db-ops` scripts (the 1C-infobase-operations hard gate — `AGENTS.md → Skills and Subagents`), dump only the targets successfully materialized in Step 3:

- selected main configuration: `db-dump-cf.ps1 -OutputFile "{OUTPUT_ROOT}\cf\<ConfigName>_<Version>.cf"` with no effective extension option;
- each selected extension, in the resolved load sequence: `db-dump-cf.ps1 -Extension <Name> -OutputFile "{OUTPUT_ROOT}\cfe\<Name>\<Name>_<ExtVersion>.cfe"`, with that extension's exact name and version.

Pass the same resolved assembly connection to every wrapper; its ordinary defaults must not retarget the dump. Use a fresh output path or preserve/check any existing binary before replacement, so a stale file cannot pass the result check. Verify each output was produced by this successful run, exists and is non-empty. Read exit/log evidence and, for Designer, the fresh numeric result per `content/skills/1c-metadata-manage/docs/db-manage.md` and `content/rules/designer-batch-checks.md`; preserve per-target evidence. XML export alone, a failed launch with an old binary, or a nonempty file without a successful verdict is not a completed build.

## Step 5. Optional `.cfu` (update file)

Only for a selected main-configuration build, on an explicit user request **and** when a previous-release `.cf` is available (in the resolved output layout or supplied by the user): build the update file with Designer `/CreateDistributionFiles`. Verify the exact flag syntax for the installed platform version through the docs MCP (`docsearch`) before composing the line — do not write it from memory (platform-capability check). Otherwise skip and note the skip in the report.

## Step 6. Changelog and tag (confirm before any git action)

Unless `--no-tag` was passed, offer in one question: append a `## <Version> — <date>` section to `CHANGELOG.md` built from `git log <last-release-tag>..HEAD --oneline` (create the file if missing), commit it, and tag `v<Version>`. On decline — skip both. Never push unless the user explicitly asks.

## Step 7. Production delivery — checklist only

This command does **not** apply anything to production. Print the checklist for the human-driven delivery instead:

1. Backup of the production base (`.dt` via `db-dump-dt` for file bases / DBMS backup for server bases) taken and verified.
2. Update window agreed with the users.
3. Apply per the `/update1cbase` procedure with the **production overrides stated there**: no forced session termination (`-SessionTerminate` removed / `--session-terminate=prompt`), dynamic-update decision made consciously.
4. Extensions applied in `EXTENSION_NAMES` order after the main configuration.
5. Post-update verification: log check, key user scenario walked through.

## Step 8. Final report

For each selected extension, update its existing README or delivery description with `content/rules/extension-workspace.md → Checked compatibility`: exact checked CF/platform/CFE versions and source revision, required extensions, and references to applicability, borrowed-method and scenario evidence. Keep declared requirements separate; a successful binary dump proves neither a supported version range nor unrun runtime tests.

Report: project, selected main/extension targets, source roots, versions and commit built, actual artifact paths with sizes and build/check verdicts, tag / changelog status, skipped optional steps (`.cfu`, tag) with reasons, retry-loop attempts in Step 3, and the `IB tooling:` line required by `AGENTS.md → Skills and Subagents`. Record missing/failed targets explicitly; do not label a partial build a complete snapshot or claim a source-only validation produced `.cf`/`.cfe`.
