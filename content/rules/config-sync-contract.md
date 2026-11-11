---
description: Configuration file synchronization contract — directions, export and import modes, partial loads, end-to-end order of dump, edit, load, check and DB update. Load before /loadfrom1cbase, /update1cbase, /getconfigfiles or a db-ops load or dump.
alwaysApply: false
category: workflow
---

# Configuration file synchronization contract

`/loadfrom1cbase` owns **infobase → source directory**; `/getconfigfiles` is its selected-object export procedure (`content/rules/getconfigfiles.md`). `/update1cbase` owns **source directory → configuration → database configuration**; `/deploy-and-test` inherits that sequence. These are stages of one workflow, with the same infobase, main configuration or named extension, source directory and format throughout a pass.

Resolve the current project and exact target through `content/rules/extension-workspace.md` before transfer. In the command templates, `EXPORT_PATH` and `EXTENSION_NAME` are the resolved source-root/extension values for that pass, not an instruction to rewrite settings. Metadata discovery for the selection uses that same project's verified MCP scope and extension layer (`content/rules/multi-contour-search.md`); identical object names in another project or the base do not establish the extension's export list.

Before a transfer, establish the direction, target and scope from the task and current files. Inspect local changes in every destination that may be overwritten, including `ConfigDumpInfo.xml`; preserve them or obtain explicit overwrite authorization. A partial dump is not a complete snapshot suitable for an unrestricted full load. An empty selection is a no-op, never permission to remove the selection flag and process everything. Never silently widen a partial request to a full transfer.

## Export modes — `/DumpConfigToFiles`

- **Full:** export into a new directory or deliberately refresh a full snapshot. `-Format Hierarchical` is the default; `Plain` must match the project's existing format.
- **Changes:** `-update` compares object versions with the destination's `ConfigDumpInfo.xml`, exports changed objects and updates that file. A missing version file or a different dump-format version is an error. Preserve the baseline; do not regenerate it from the infobase merely to suppress the error.
- **Full fallback:** `-force` with `-update` permits a full dump on a dump-format version mismatch; outside `-update` it is ignored. Use only when the full overwrite is within the authorized scope. The bundled `db-dump-xml -Mode Changes` runs `-update` without `-force` and fails on a dump-format version mismatch instead of silently dumping everything; `-Mode Full` is the deliberate full overwrite.
- **Selected objects:** `-listFile <object-list>` exports listed objects regardless of whether they changed. Separate development objects (for example a form) must be listed explicitly when needed; selecting a root does not guarantee every child form or template was exported. Use the minimal closure of `getconfigfiles.md`.
- **Change report:** `-getChanges <report-file>` writes the list of differences against the dump baseline. By itself this is a comparison, not a refreshed source directory. An empty report means no differences; it is not a failed export. Do not pass this report directly as an import file list.
- **Delta directory:** `-update -configDumpInfoForChanges <absolute-baseline-file>` exports changes against an external `ConfigDumpInfo.xml` into an **empty** output directory. The external baseline stays unchanged; a new version file is written in the delta directory, without checking the baseline's dump-format version against the current one. The parameter is used only with `-update` and/or `-getChanges`; a missing baseline is an error. Add `-getChanges <report-file>` to also obtain a report. Preserve the original snapshot and identify the delta as partial.

Use separate files for the object selection, change report and baseline. The script's `UpdateInfo` mode updates only version information; it does not refresh source files and cannot certify synchronization. Advanced comparison / delta modes use the documented Designer command; do not invent corresponding wrapper parameters.

## Import modes — `/LoadConfigFromFiles`

For a partial load, use **one** selector: `-files "<file1>,<file2>"` or `-listFile <file-list>`, plus explicit `-Format Hierarchical` / `Plain`. Import lists contain **file paths**, absolute or relative to the source directory, unlike export lists of metadata names. Write list files in UTF-8, one path per line, no blank lines; `REM` starts an ignored line. Check every selected file exists and belongs to the intended source tree. Use `-updateConfigDumpInfo` to update the dump baseline after loading; it does not apply the database configuration.

The separate `-partial` flag limits restoration of an object's description to the supplied pieces (including a form module alone); it is not a replacement for a file selector. The bundled `db-load-xml -Mode Partial` and `db-load-git` add it. Verify support in the target platform version before use. Keep integrity checks enabled.

Add required parent descriptors / registrations for new objects and dependencies from evidence. A deleted or renamed path cannot simply be omitted from a Git-derived list and reported as deployed: resolve the required removal / parent change, or explicitly choose a full load from a complete snapshot. Do not load `ConfigDumpInfo.xml` itself as a metadata object. If the resulting selection is empty, stop before loading and updating the database.

`-AllExtensions` is incompatible with import `-files` / `-listFile`. Process partial extension changes one named extension per pass. Command-level `all` means main configuration **and** the configured extensions; platform `-AllExtensions` covers extensions only.

## End-to-end sequence

1. Refresh source from the infobase only when that direction is required: full, changes or selected objects. Check the export result before editing.
2. Edit and validate the intended XML / BSL. Build the import list from actual changed files and the required dependencies, not from `repoobjects.txt` or an unexamined change report.
3. Follow `/update1cbase`: load the selected files or full snapshot, inspect the result, run the applicable checks (extension applicability before apply), then update the database configuration. A successful load alone is not a successful database update.
4. After successful apply, a requested directory refresh uses `/loadfrom1cbase` with the same target and an appropriate scope. Protect local edits even during this return pass. If no refresh is needed, retain the load's updated version file; do not run `UpdateInfo` to hide a failed load / apply or claim that unrelated files are synchronized.
5. Report load, checks, database update and any export separately. On failure stop the dependent stages; retain logs and the last trustworthy baseline. A version file alone does not prove that database apply succeeded.

Every Designer launch of these stages reads its verdict from three signals — `content/rules/designer-batch-checks.md → The verdict is three signals, not the exit code`.

Reference: 1C:Enterprise 8.3.27 Administrator Guide, [batch configuration commands](https://kb.1ci.com/1C_Enterprise_Platform/Guides/Administrator_Guides/1C_Enterprise_8.3.27_Administrator_Guide/Appendix_7._Startup_command-line_options_of_1C_Enterprise/7.4._Running_Designer_in_batch_mode/7.4.4._Configurations_and_extensions/?language=tr). Check version-dependent options against the target platform's installed help if the online guide is unavailable.
