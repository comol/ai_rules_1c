---
name: update
description: Update an existing 1c-rules install. Use when the user asks to update 1C rules, /updaterules, or refresh 1c-rules after a marketplace plugin update.
---

# Update 1c-rules

Do not overwrite `USER-RULES.md`, `memory.md`, or `LLM-RULES.md`. If PowerShell is available, call `install.ps1 update` through the plugin wrapper (`powershell.exe` on Windows, `pwsh` on macOS or Linux):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<plugin>/scripts/invoke-install.ps1" -Action update -ProjectRoot "<project-root>"
```

If neither PowerShell executable is available, clone or update the source repository, then follow its `AGENT-INSTALL.md` agent-driven update protocol using the installed tools' adapters. Preserve user-modified managed files according to `.ai-rules.json` and run the protocol's post-placement gates.

If `.ai-rules.json` is missing, this is a first install: use the `install` skill (`-Action init`), not update.
