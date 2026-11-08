---
name: update
description: Update 1c-rules in this project
---

If `.ai-rules.json` is missing, run `/1c-rules:install` instead.

On Windows run the following command. On macOS or Linux use `pwsh -NoProfile -File` in place of `powershell.exe -NoProfile -ExecutionPolicy Bypass -File`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<plugin>/scripts/invoke-install.ps1" -Action update -ProjectRoot "<project-root>"
```

If neither executable exists, clone or update the source repository and follow its `AGENT-INSTALL.md` agent-driven update protocol using the installed tool adapters. Verify the post-placement gates.

Keep `USER-RULES.md`, `memory.md`, and `LLM-RULES.md` untouched.
