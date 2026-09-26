---
description: One project for the main configuration and named extensions — source and build layout, explicit operation targets, transfer boundaries and MCP project scope
alwaysApply: false
category: workflow
---

# Main configuration and extensions in one project

**When to load:** working with extension sources, initializing a shared CF/CFE project, or dumping, loading, building or investigating a named extension. This rule owns target selection; command procedures own execution, and `content/rules/multi-contour-search.md` owns verified MCP routing.

## Shared layout and settings

Keep one project root, one `.dev.env`, and shared project instructions, knowledge and `openspec/` when used. A new Designer XML project may use:

```text
project/
  .dev.env
  src/
    cf/                     # main configuration; EXPORT_PATH
    cfe/                    # EXTENSIONS_PATH
      Доработки/
      Интеграция/
  build/                    # local binary build output
    cf/
    cfe/
      Доработки/
      Интеграция/
  openspec/                 # shared tasks, if used
```

During requested setup of a new empty project, persist `EXPORT_PATH=src/cf` and `EXTENSIONS_PATH=src/cfe` in the existing `.dev.env`. Resolve relative paths against the project root. These are setup choices, not new global defaults: preserve existing configured paths and legacy single-extension layouts; do not move sources during ordinary work or a rules update. `content/rules/dev-standards-env.md` retains the defaults when keys are empty.

Each Designer dump root owns its `Configuration.xml`, `ConfigDumpInfo.xml` and object tree. Keep baselines and selected-object/file lists separate per target. Do not merge identically named base and extension objects into one file. Keep logs, result files and binary output outside source roots; exclude build/release output from source indexing and Git source commits. For EDT, preserve the existing project descriptors and base/extension references; use its export/update workflow (`content/rules/edt-workflow.md`), never place Designer XML over `.mdo` sources.

`EXTENSION_NAME` is the default/primary target for a single-target operation, not the inventory of the project. `EXTENSION_NAMES` is the ordered full-snapshot list. It neither restricts source search nor defines the platform's runtime layer order. Do not rewrite either setting merely because one task selects another extension. No second file of connection parameters is needed; an optional source-contour catalog records only identity and search routing.

For an explicit `all` / full-project snapshot, an empty `EXTENSION_NAMES` is not permission to fall back to `EXTENSION_NAME`. Resolve inventory from the request, established project inventory or a verified target listing. When no extensions is established, process main only; when the requested inventory remains unknown, resolve that narrow ambiguity before claiming or mutating a full snapshot. Ordinary single-target calls without `all` retain their existing default behavior.

## Resolve the target before work

Resolve and state one compact context: **project root → main or named extension → source root and format → operation and scope**; add the named infobase for IB operations and the verified server/project/layer for MCP work. These are distinct identities, not interchangeable names.

1. Prefer the user's explicit target; otherwise use the task's file ownership and verified project mapping. Use `EXTENSION_NAME` only as the single-target default when the task has not selected a target; empty means main. A request for the whole snapshot uses main plus `EXTENSION_NAMES`. Resolve a remaining material ambiguity before writing/loading; do not silently pick the first folder or extension.
2. In the shared layout, main resolves to `EXPORT_PATH`, and a named extension to `EXTENSIONS_PATH/<Name>`. An established legacy single-extension project may instead use `EXPORT_PATH` for that extension: retain it only when its descriptor and project context establish the mapping. Never pair the base directory with an extension flag, or the extension directory with a main-configuration operation.
3. Confirm target kind/name from its existing root descriptor and mappings, not directory spelling alone. For a new dump destination, use the verified source-IB target and check the resulting descriptor. Distinct targets must not write to the same or overlapping dump roots. When a legacy main dump is the repository root with CFE subdirectories, preserve it but use a separate main dump staging directory for a refresh that could overwrite those subdirectories; do not migrate the layout silently.
4. Template placeholders `EXPORT_PATH` and `EXTENSION_NAME` in the transfer commands mean the **resolved values for this pass**. Pass them explicitly to wrappers under their actual parameter names; do not edit `.dev.env` to switch passes. For main, omit the extension option and ensure a wrapper cannot restore a nonempty extension default. A missing-extension error never permits dropping the option or switching to main.
5. Fix existing code in its owning contour. Place new objects according to `NEW_OBJECTS_IN` and the resolved extension target; follow repository/support and metadata-tooling guards. Search can span the project without granting writes to every contour. Creating another extension requires an explicit task to do so.

## Preserve extension identity

Distinguish creating a new extension from editing, moving, renaming, updating or restoring an existing one. Preserve the existing extension and metadata-object identifiers and borrowed-object links during ordinary changes. Moving a source folder is not a reason to run `init` / `create`, regenerate UUIDs or borrow the same objects afresh. Use the existing metadata tools for an authorized rename; a changed name/path alone does not authorize replacing the extension's identity.

Compare an update or restore with its known source revision or backup. Investigate unexpected identifier changes, especially widespread UUID churn, before loading/applying the affected target: establish whether the input is the intended existing extension, a different extension or an explicitly requested replacement. Do not repair the discrepancy by bulk UUID substitution. Judge the actual diff; do not assume every export/import round trip changes identifiers. After a move, rename or restore, recheck source-root/target mappings, graph project/layer attribution and affected evidence before reuse; retain unknowns instead of silently remapping to a similarly named target.

## Checked compatibility

Keep a short **checked combination** entry in the extension's existing README or delivery description; reuse that location, without a separate registry or new configuration schema. Record:

- exact main-configuration version and source revision when known, exact platform version, extension version and checked source revision (include local-edit fingerprints when not committed);
- required other extensions and their checked versions/revisions, or explicitly established none / unknown; a load list alone is not proof of dependencies;
- applicability, relevant borrowed-method/drift checks and executed scenarios, each with its outcome and evidence reference tied to this target and combination. Label source-only checks separately from checks in the named test infobase; use a non-secret target alias, not a connection string.

Keep declared compatibility requirements or supported ranges separate from observed results. One passing combination does not prove a version range, compatibility with another base, or a pass for every project extension. Reuse evidence already obtained by the authorized workflow; do not add IB operations merely to fill this entry. Mark unrun/unknown checks explicitly, and do not carry a previous pass forward after relevant source, dependency, platform or target-state changes without establishing that it still applies.

## Handoff and resume

For CF/CFE work continuing in another session or subagent, preserve a compact context in the existing Handoff (`content/skills/handoff/SKILL.md`, `content/rules/subagent-core.md`): project root; writable targets and read-only contours with source roots; verified graph server/project ID and extension layers (or unresolved mapping). Refer to project settings rather than copying `.dev.env`, credentials or connection strings.

Record these states **separately per target**, with revision/fingerprint and evidence references where known: local source edits; last export and its full/partial scope; loaded editable configuration; applied database configuration; MCP generation/coverage/freshness. Distinguish completed, failed, not run and unknown; a completed export or load does not imply apply, and apply does not imply a fresh index. A successful extension pass does not certify the whole project.

On resume, check the current project root, writable scope, target identity and graph/root mapping against the handoff before dependent mutations. Reuse evidence only while its source and relevant target state still match; otherwise mark it stale or unknown and resolve only the gap needed next. A handoff is not authorization to reload, apply, restore or reindex. Continue independent source work when an IB/index state is unknown, within the already authorized scope.

## Transfer and build contract

- **Dump:** `/loadfrom1cbase` exports the chosen target; `all` exports main and each listed extension into separate roots. Preserve local changes. `changes` uses that target's baseline; selected-object/delta dumps remain partial. `content/rules/getconfigfiles.md` owns the exact selection and synchronization rules.
- **Load:** `/update1cbase` imports only the resolved target and selection, checks it, then applies the database configuration. Extension applicability checks stay between load and apply. For `all`, preflight all source roots and identities before the first mutation, then load main and the listed extensions sequentially, stopping at failure. Keep completed/failed stages explicit. A partial export, a lone `Configuration.xml`, or a stale build file is not a verified full snapshot.
- **Build:** `/build-release` materializes the selected committed sources in the explicitly identified assembly infobase, runs the inherited validation, then produces a real `.cf` for main or `.cfe` for each selected extension via `db-dump-cf`. Merely exporting XML or renaming a directory/file is not a binary build. Under the configured output root use `cf/` and `cfe/<Name>/`; an existing artifact layout remains valid. For a local build the root may be `build/` as an explicit invocation choice; release output continues to use `RELEASE_PATH` and its documented default. Do not persist a temporary output choice over release settings.
- **Evidence:** retain target/source state, validation verdict, fresh output path and nonzero size for each built artifact. An old binary at that path cannot prove success. `.cf`/`.cfe` are configuration artifacts; a `.dt` data restore remains the separate destructive procedure in `/restore-testbase`.

The source snapshot defines the targets to process, not permission to delete other extensions already installed in the infobase. Establish relevant active extensions before claiming a reproducible runtime state; report extras/mismatches and do not remove them automatically. Load order is not proof of runtime application order: use the target's actual extension purposes/order when that behavior matters.

## MCP project and layer are explicit

Before extension or multi-project graph work, resolve the current project through `list_graph_projects` and verified root mappings (`content/rules/multi-contour-search.md`). Pass the returned base `project_id` explicitly to every project-data call supported by its live schema, including searches, usages, comparisons and pagination. The extension is a layer of that project; neither its name nor an MCP client server label is the project ID.

Example: the current roots map to the returned Accounting project and the task edits `Доработки`. Keep Accounting's returned `project_id` for the extension lookup, base lookup and comparison; select/attribute the `Доработки` layer through the tool's actual contract. Do not invent a universal layer argument. A ready Accounting base-only graph or an empty result from another project proves nothing about `Доработки`. Use that extension's verified code index or its source directory when layer coverage is unavailable. Multiple projects without a verified mapping to the current roots require resolving the ambiguity, never selecting the first/default project.

Queries do not authorize registration, reindexing or database operations. Record source roots/layers and any stale or missing coverage; source/index evidence alone does not certify the running infobase.
