---
description: Extract configuration objects from infobase to files for editing
---

# /getconfigfiles — extract configuration objects from an infobase

The full procedure — parameters, `repoobjects.txt`, the `ibcmd` / Designer tool selection, the PowerShell templates, and the log check — is owned by the rule **`getconfigfiles.md`**. Read it from the canonical rules directory (source: `content/rules/getconfigfiles.md`) and follow it exactly; do not improvise flags that are not in the rule.

Quick facts (details and templates — in the rule):

- All parameters come from `.dev.env`. Parameters, classes and defaults — `content/rules/dev-standards-env.md §1`; Defaulted keys are never asked for. Only `INFOBASE_PATH` and `PLATFORM_PATH` are blocking — if either is empty, ask the user once and write the value to `.dev.env`. Also read: `IB_USER` / `IB_PASSWORD`, `LOG_PATH`, `IBCMD_CONFIG`.
- Build `repoobjects.txt` from verified metadata names in the selected export tool's notation, one per line. Remove empty entries and duplicates; an empty selection must not trigger a full dump. Include separate development objects only when needed.
- The `ibcmd` path requires both `{PLATFORM_PATH}\bin\ibcmd.exe` and a filled `IBCMD_CONFIG`; clustered server infobases always use Designer.
- Inspect `{LOG_PATH}` for errors before starting any edits.
- **EDT projects** (`.dev.env` `USE_EDT=true`): the export is a Designer XML dump. If the working tree is an EDT (`src/**/*.mdo`) workspace, export to a separate directory and never mix the two trees — `content/rules/edt-workflow.md`.
- `/loadfrom1cbase partial` delegates its selected-object refresh here and retains the dirty-directory guard. After editing, `/update1cbase partial` loads a separate list of **file paths**, runs checks, then updates the database. Never reuse `repoobjects.txt` as the load list; follow the rule's synchronization contract.
