---
description: Selected-object export from an infobase — minimal closure of the object list, ibcmd or Designer export, verdict check. Load for /getconfigfiles or a partial export; the synchronization contract is config-sync-contract.md.
alwaysApply: false
category: workflow
---

# Exporting Objects from an Infobase to the Repository

The direction, modes and end-to-end order of every dump and load — `content/rules/config-sync-contract.md`. This file is the selected-object export procedure of `/getconfigfiles`.

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

**Step 1.** Follow `content/rules/config-sync-contract.md` and the `.dev.env`, dirty-directory and EDT preflight in `content/commands/loadfrom1cbase.md`. Compose `repoobjects.txt` from verified metadata identifiers (not synonyms), in the notation accepted by the selected tool and platform help; do not assume that an MCP's Russian display name is already the Designer list syntax. Build the list via `metadatasearch` or `search_metadata` (see `content/skills/mcp-1c-tools/SKILL.md`). Write UTF-8, one object per line, remove blank entries and duplicates, and reject an empty selection before launching the platform.

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
    /DisableStartupMessages /DisableStartupDialogs `
    /DumpConfigToFiles '{EXPORT_PATH}' `
    -Format Hierarchical `
    -listFile 'repoobjects.txt' `
    -Extension {EXTENSION_NAME} `
    /Out '{LOG_PATH}' `
    /DumpResult '{RESULT_PATH}'
```

Remove empty credentials and the extension argument for the main configuration; quote populated extension names. Use `Plain` instead when it is the established dump format. Expand resolved `$env:` paths in double quotes. Keep list/result/log files outside the dump tree.

**Step 3.** Inspect the result before starting any edits: the process exit code, the number in `{RESULT_PATH}` (`0` = success), and `{LOG_PATH}`. All three must agree — and in the log, classify the platform's success phrases (`Ошибок не обнаружено`, `Предупреждений: 0`) before its error stems, or a clean export reads as a failure. Canon — `content/rules/designer-batch-checks.md → The verdict is three signals, not the exit code`. Delete a stale `{RESULT_PATH}` before the run; an old file reads as this run's verdict.
