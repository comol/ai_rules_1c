---
description: Extract configuration objects from infobase to files for editing
---

# /getconfigfiles — extract configuration objects from an infobase

The full procedure — parameters, `repoobjects.txt`, the `ibcmd` / Designer tool selection, the PowerShell templates, and the log check — is owned by the rule **`getconfigfiles.md`**. Read it from the canonical rules directory (source: `content/rules/getconfigfiles.md`) and follow it exactly; do not improvise flags that are not in the rule.

Quick facts (details and templates — in the rule):

- All parameters come from `.dev.env` (classification and ask-policy — `dev-standards-env.md`). Only `INFOBASE_PATH` and `PLATFORM_PATH` are blocking — if either is empty, ask the user once and write the value to `.dev.env`.
- `IB_USER` / `IB_PASSWORD` / `LOG_PATH` are **Defaulted** — empty = no authentication / no password (`/N` / `/P` / `--user` / `--password` omitted) / `$env:TEMP\1cv8.log` (Windows) or `$TMPDIR/1cv8.log` (POSIX). Apply silently, **never ask up front**; re-ask `IB_USER` / `IB_PASSWORD` only on a platform authentication error, `LOG_PATH` only if the resolved path is non-writable.
- Build the object list in `repoobjects.txt` (one fully qualified metadata-object name per line) via `metadatasearch` / `search_metadata` before exporting.
- The `ibcmd` path requires both `{PLATFORM_PATH}\bin\ibcmd.exe` and a filled `IBCMD_CONFIG`; clustered server infobases always use Designer.
- Inspect `{LOG_PATH}` for errors before starting any edits.
