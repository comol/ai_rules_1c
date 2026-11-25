---
name: install
description: Install 1c-rules into this project
---

Use the PowerShell wrapper when available; otherwise follow the agent-driven channel in `AGENT-INSTALL.md`. Both channels adapt rules for this host.

1. Project root = the current 1C repository. Refuse home / CLI config directories. Note whether `.ai-rules.json` already exists: the optional dump offer below belongs only to a first install.
2. Tool id: Cursor `cursor`, Claude Code `claude-code`, Codex `codex`, OpenCode `opencode`, Kilo `kilocode`.
3. On Windows run the following command. On macOS or Linux use `pwsh -NoProfile -File` in place of `powershell.exe -NoProfile -ExecutionPolicy Bypass -File`. If neither executable exists, clone or reuse the source repository and follow its `AGENT-INSTALL.md` agent-driven protocol with `adapters/<tool-id>.yaml`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<plugin>/scripts/invoke-install.ps1" -Action init -Tool <tool-id> -ProjectRoot "<project-root>"
```

4. After a successful first install, follow `AGENT-INSTALL.md` → `Optional first source dump`: if `.dev.env` has `INFOBASE_PATH` and no project sources exist, offer **«Выгрузить» / «Пропустить»** in chat. The wrapper uses unattended flags, so its skipped export is not the user's refusal. On acceptance execute the installed `/loadfrom1cbase full` procedure; on refusal finish installation. Never repeat a choice already answered, or offer on an update / re-init.

Run the protocol's post-placement gates. Do not copy `content/` verbatim. Restart the client if MCP config changed.
