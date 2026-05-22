---
description: Exporting configuration objects (metadata) from an infobase to the repository — `ibcmd infobase config export` (preferred) or Designer `/DumpConfigToFiles` fallback. Load when extracting source from a live infobase.
alwaysApply: false
category: workflow
---

# Exporting Objects from an Infobase to the Repository

## Parameters (defined in `.dev.env` or supplied by the user at task start)

| Placeholder | Purpose |
|---|---|
| `{PLATFORM_PATH}` | Path to the 1C platform installation directory (containing `bin\1cv8.exe`). Example: `C:\Program Files\1cv8\8.3.23.1997` |
| `{INFOBASE_PATH}` | Path to a file infobase or the connection string of a server infobase |
| `{IB_USER}` | Infobase user name; empty = no authentication, `/N` / `--user` is omitted. **Do not ask up front.** |
| `{IB_PASSWORD}` | Password; empty = no password, `/P` / `--password` is omitted. An empty password is a fully valid configuration for dev / test infobases — **do not ask up front**. Re-ask only if the platform itself returns an authentication error. |
| `{EXPORT_PATH}` | Directory where object sources are exported |
| `{EXTENSION_NAME}` | Extension name when exporting from an extension; otherwise omit the `-Extension` argument |
| `{LOG_PATH}` | Designer log file; empty resolves to `$env:TEMP\1cv8.log` (Windows) / `$TMPDIR/1cv8.log` (POSIX). **Do not ask up front** — any writable path works equally well. Re-ask only if the resolved path turns out to be non-writable. |
| `{IBCMD_CONFIG}` | Path to the standalone server `config.yml` for the `ibcmd` utility (optional) |

Only `INFOBASE_PATH` and `PLATFORM_PATH` are blocking — if either is empty, **ask the user** (do not guess) and write the value to `.dev.env`. For `IB_USER` / `IB_PASSWORD` / `LOG_PATH` apply the documented defaults from the table silently. When substituting templates: if `LOG_PATH` is empty, replace `{LOG_PATH}` with `"$env:TEMP\1cv8.log"`.

## Steps

**Step 1.** Compose the list of objects to export in `repoobjects.txt` (one full metadata-object name per line, e.g. `Справочник.Контрагенты`). Build the list via `metadatasearch` or `search_metadata` (see `content/skills/mcp-1c-tools/SKILL.md`).

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

**Step 2b.** Partial export via Designer (fallback). Objects are exported **in full**, strictly into the specified directory — **do NOT create new subdirectories**.

```powershell
& '{PLATFORM_PATH}\bin\1cv8.exe' DESIGNER `
    /F '{INFOBASE_PATH}' `
    /N '{IB_USER}' `
    /P '{IB_PASSWORD}' `
    /DisableStartupMessages `
    /DumpConfigToFiles {EXPORT_PATH} `
    -listFile repoobjects.txt `
    -Extension {EXTENSION_NAME} `
    /Out {LOG_PATH}
```

When exporting from the main configuration (not from an extension) — drop the `-Extension {EXTENSION_NAME}` argument.

**Step 3.** Inspect `{LOG_PATH}` for errors before starting any edits.
