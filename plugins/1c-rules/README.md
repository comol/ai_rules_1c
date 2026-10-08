# 1c-rules plugin

Thin marketplace wrapper. It does **not** ship `content/rules` as plugin rules. With PowerShell available, `scripts/invoke-install.ps1` calls the real `install.ps1`. Without PowerShell, the install/update skills use the agent-driven protocol in `AGENT-INSTALL.md`. Both paths apply the host adapter to files placed in the project.

## What the plugin contains

- Install and update skills
- Matching slash commands
- Claude Code / Cursor hooks and the OpenCode plugin that run `ensure` on a 1C project when PowerShell is installed (init or `add` the host tool; never auto-update)
- Codex install/update skills; Codex does not run the Claude Code `SessionStart` hook
- `plugin.mjs` for OpenCode and Kilo CLI

## Local check

On macOS or Linux, use `pwsh -NoProfile -File` if PowerShell is installed. If it is absent, invoke the install/update skill in Codex; `invoke-install.sh` exits with an error instead of reporting success.

```powershell
# Plan only
powershell.exe -NoProfile -File .\plugins\1c-rules\scripts\invoke-install.ps1 -Action ensure -Tool cursor -ProjectRoot . -DryRun

# Claude Code, this checkout
claude --plugin-dir .\plugins\1c-rules
```
