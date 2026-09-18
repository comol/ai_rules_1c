---
description: Configuration file synchronization — full, incremental and selected-object export, partial file import, and integration with repository refresh and database update. Load when extracting or synchronizing configuration sources with an infobase.
alwaysApply: false
category: workflow
---

# Exporting Objects from an Infobase to the Repository

## Configuration file synchronization contract

`/loadfrom1cbase` owns **infobase → source directory**; `/getconfigfiles` is its selected-object export procedure. `/update1cbase` owns **source directory → configuration → database configuration**; `/deploy-and-test` inherits that sequence. These are stages of one workflow, with the same infobase, main configuration or named extension, source directory and format throughout a pass.

Before a transfer, establish the direction, target and scope from the task and current files. Inspect local changes in every destination that may be overwritten, including `ConfigDumpInfo.xml`; preserve them or obtain explicit overwrite authorization. A partial dump is not a complete snapshot suitable for an unrestricted full load. An empty selection is a no-op, never permission to remove the selection flag and process everything. Never silently widen a partial request to a full transfer.

### Export modes — `/DumpConfigToFiles`

- **Full:** export into a new directory or deliberately refresh a full snapshot. `-Format Hierarchical` is the default; `Plain` must match the project's existing format.
- **Changes:** `-update` compares object versions with the destination's `ConfigDumpInfo.xml`, exports changed objects and updates that file. A missing version file or a different dump-format version is an error. Preserve the baseline; do not regenerate it from the infobase merely to suppress the error.
- **Full fallback:** `-force` with `-update` permits a full dump on a dump-format version mismatch; outside `-update` it is ignored. Use only when the full overwrite is within the authorized scope. The bundled `db-dump-xml -Mode Changes` adds `-force`, so use the Designer template without that flag when full fallback is not allowed.
- **Selected objects:** `-listFile <object-list>` exports listed objects regardless of whether they changed. Separate development objects (for example a form) must be listed explicitly when needed; selecting a root does not guarantee every child form or template was exported. Use the minimal closure below.
- **Change report:** `-getChanges <report-file>` writes the list of differences against the dump baseline. By itself this is a comparison, not a refreshed source directory. An empty report means no differences; it is not a failed export. Do not pass this report directly as an import file list.
- **Delta directory:** `-update -configDumpInfoForChanges <absolute-baseline-file>` exports changes against an external `ConfigDumpInfo.xml` into an **empty** output directory. The external baseline stays unchanged; a new version file is written in the delta directory, without checking the baseline's dump-format version against the current one. The parameter is used only with `-update` and/or `-getChanges`; a missing baseline is an error. Add `-getChanges <report-file>` to also obtain a report. Preserve the original snapshot and identify the delta as partial.

Use separate files for the object selection, change report and baseline. The script's `UpdateInfo` mode updates only version information; it does not refresh source files and cannot certify synchronization. Advanced comparison / delta modes use the documented Designer command; do not invent corresponding wrapper parameters.

### Import modes — `/LoadConfigFromFiles`

For a partial load, use **one** selector: `-files "<file1>,<file2>"` or `-listFile <file-list>`, plus explicit `-Format Hierarchical` / `Plain`. Import lists contain **file paths**, absolute or relative to the source directory, unlike export lists of metadata names. Write list files in UTF-8, one path per line, no blank lines; `REM` starts an ignored line. Check every selected file exists and belongs to the intended source tree. Use `-updateConfigDumpInfo` to update the dump baseline after loading; it does not apply the database configuration.

The separate `-partial` flag limits restoration of an object's description to the supplied pieces (including a form module alone); it is not a replacement for a file selector. The bundled `db-load-xml -Mode Partial` and `db-load-git` add it. Verify support in the target platform version before use. Keep integrity checks enabled.

Add required parent descriptors / registrations for new objects and dependencies from evidence. A deleted or renamed path cannot simply be omitted from a Git-derived list and reported as deployed: resolve the required removal / parent change, or explicitly choose a full load from a complete snapshot. Do not load `ConfigDumpInfo.xml` itself as a metadata object. If the resulting selection is empty, stop before loading and updating the database.

`-AllExtensions` is incompatible with import `-files` / `-listFile`. Process partial extension changes one named extension per pass. Command-level `all` means main configuration **and** the configured extensions; platform `-AllExtensions` covers extensions only.

### End-to-end sequence

1. Refresh source from the infobase only when that direction is required: full, changes or selected objects. Check the export result before editing.
2. Edit and validate the intended XML / BSL. Build the import list from actual changed files and the required dependencies, not from `repoobjects.txt` or an unexamined change report.
3. Follow `/update1cbase`: load the selected files or full snapshot, inspect the result, run the applicable checks (extension applicability before apply), then update the database configuration. A successful load alone is not a successful database update.
4. After successful apply, a requested directory refresh uses `/loadfrom1cbase` with the same target and an appropriate scope. Protect local edits even during this return pass. If no refresh is needed, retain the load's updated version file; do not run `UpdateInfo` to hide a failed load / apply or claim that unrelated files are synchronized.
5. Report load, checks, database update and any export separately. On failure stop the dependent stages; retain logs and the last trustworthy baseline. A version file alone does not prove that database apply succeeded.

Reference: 1C:Enterprise 8.3.27 Administrator Guide, [batch configuration commands](https://kb.1ci.com/1C_Enterprise_Platform/Guides/Administrator_Guides/1C_Enterprise_8.3.27_Administrator_Guide/Appendix_7._Startup_command-line_options_of_1C_Enterprise/7.4._Running_Designer_in_batch_mode/7.4.4._Configurations_and_extensions/?language=tr). Check version-dependent options against the target platform's installed help if the online guide is unavailable.

## Parameters (defined in `.dev.env` or supplied by the user at task start)

| Placeholder | Purpose |
|---|---|
| `{PLATFORM_PATH}` | 1C platform installation directory containing `bin\1cv8.exe` — **blocking**: ask once when empty |
| `{INFOBASE_PATH}` | File infobase path or server connection string — **blocking**: ask once when empty |
| `{INFOBASE_FLAG}` | Resolve from `INFOBASE_KIND`: `/F` for `file`, `/S` for `server`; reject other values |
| `{IB_USER}` / `{IB_PASSWORD}` | Credentials; empty omits `/N` / `/P` (`--user` / `--password`) |
| `{EXPORT_PATH}` | Directory where object sources are exported |
| `{EXTENSION_NAME}` | Extension name when exporting from an extension; otherwise omit the `-Extension` argument |
| `{LOG_PATH}` | Designer log file |
| `{RESULT_PATH}` | Designer batch result file; remove a stale file before each launch |
| `{IBCMD_CONFIG}` | Standalone server `config.yml` for `ibcmd`; empty = Designer |

Classes, defaults and the ask-policy (Defaulted keys are never asked for; credentials re-asked only after an authentication error, `LOG_PATH` only when non-writable) — `dev-standards-env.md §1`.

## Steps

**Step 1.** Follow the synchronization contract above and the `.dev.env`, dirty-directory and EDT preflight in `content/commands/loadfrom1cbase.md`. Compose `repoobjects.txt` from verified metadata identifiers (not synonyms), in the notation accepted by the selected tool and platform help; do not assume that an MCP's Russian display name is already the Designer list syntax. Build the list via `metadatasearch` or `search_metadata` (see `content/skills/mcp-1c-tools/SKILL.md`). Write UTF-8, one object per line, remove blank entries and duplicates, and reject an empty selection before launching the platform.

### Minimal closure — expand the list from evidence, not from guessing

A partial export is only cheaper than a full dump if the list stays small. Do not pre-emptively list every form, template and command an object owns, and do not fall back to a full `/DumpConfigToFiles` "to be safe" — that trades a 30-second export for a multi-minute one and buries the relevant files.

1. Export the **root objects** only (MCP identities such as `Справочник.Контрагенты`, `Документ.ЗаказПокупателя`, `РегистрСведений.ЦеныНоменклатуры`; resolve the export-tool notation before writing the list).
2. Read the exported root XML to see which forms, commands and templates actually exist.
3. Read only the modules relevant to the task, and search *those files* for concrete references to other metadata and common modules.
4. Run a **second** export listing only the names that evidence turned up — a child form as `Справочник.Контрагенты.Форма.ФормаЭлемента`, a common module as `ОбщийМодуль.<Имя>`.
5. Repeat until every conclusion has source behind it.

Which children matter depends on the task: an object-manager change rarely needs any form; a form-event change needs that exact form and usually no templates.

**Two accuracy rules.** A name the platform rejects is *unresolved*, not misspelled — confirm it from `metadatasearch` or ask, instead of trying spelling variants in a loop. And names here are **metadata names, not synonyms** shown to users.

**Stated limit.** Static inspection cannot find dynamic dispatch — `Вычислить`, string-built metadata lookup, behaviour selected by functional options, or a handler wired only at runtime. When a conclusion depends on one of those, say so and confirm it with a focused check against a live base (`verification-gates.md → Gate 3a`) rather than presenting a text search as complete.

**Step 2.** Choose the export tool:

- If `Test-Path '{PLATFORM_PATH}\bin\ibcmd.exe'` succeeds **and** `IBCMD_CONFIG` is set in `.dev.env` — use **Step 2a (ibcmd)**.
- Otherwise — use **Step 2b (Designer)**. `ibcmd infobase config` does not work with clustered server infobases — for those, always use Designer.

**Step 2a.** Partial export via `ibcmd`. The object list is read from `repoobjects.txt` and passed as positional arguments:

```powershell
$objects = Get-Content repoobjects.txt | Where-Object { $_.Trim() -ne '' }
& '{PLATFORM_PATH}\bin\ibcmd.exe' infobase config export objects `
    --config='{IBCMD_CONFIG}' `
    --user='{IB_USER}' `
    --password='{IB_PASSWORD}' `
    --recursive `
    --out='{EXPORT_PATH}' `
    --extension={EXTENSION_NAME} `
    @objects *>&1 | Tee-Object -FilePath '{LOG_PATH}'
```

Drop unset optional flags (`--user`, `--password`, `--extension`). `--recursive` exports subordinate objects (attributes, tabular sections, forms, templates).

**Step 2b.** Partial export via Designer (fallback). Use the specified directory as the dump root; preserve the selected dump format's hierarchy. Separate development objects need their own list entries, as described above.

```powershell
& '{PLATFORM_PATH}\bin\1cv8.exe' DESIGNER `
    {INFOBASE_FLAG} '{INFOBASE_PATH}' `
    /N '{IB_USER}' `
    /P '{IB_PASSWORD}' `
    /DisableStartupMessages `
    /DumpConfigToFiles '{EXPORT_PATH}' `
    -Format Hierarchical `
    -listFile 'repoobjects.txt' `
    -Extension {EXTENSION_NAME} `
    /Out '{LOG_PATH}' `
    /DumpResult '{RESULT_PATH}'
```

Remove empty credentials and the extension argument for the main configuration; quote populated extension names. Use `Plain` instead when it is the established dump format. Expand resolved `$env:` paths in double quotes. Keep list/result/log files outside the dump tree.

**Step 3.** Inspect the result before starting any edits: the process exit code, the number in `{RESULT_PATH}` (`0` = success), and `{LOG_PATH}`. All three must agree — and in the log, classify the platform's success phrases (`Ошибок не обнаружено`, `Предупреждений: 0`) before its error stems, or a clean export reads as a failure. Canon — `content/rules/designer-batch-checks.md → The verdict is three signals, not the exit code`. Delete a stale `{RESULT_PATH}` before the run; an old file reads as this run's verdict.
