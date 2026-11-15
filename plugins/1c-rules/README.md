# 1c-rules plugin

Thin marketplace wrapper. It does **not** ship `content/rules` as plugin rules. With PowerShell available, `scripts/invoke-install.ps1` calls the real `install.ps1`. Without PowerShell, the install/update skills use the agent-driven protocol in `AGENT-INSTALL.md`. Both paths apply the host adapter to files placed in the project.

## What the plugin contains

- Install and update skills
- Matching slash commands
- Claude Code / Cursor hooks and the OpenCode plugin that run `ensure` on a 1C project when PowerShell is installed (init or `add` the host tool; never auto-update)
- Codex install/update skills; Codex does not run the Claude Code `SessionStart` hook
- `plugin.mjs` for OpenCode and Kilo CLI
- Claude Code only: the experimental, opt-in support-guard hook (below)

## Support-guard hook (experimental, Claude Code, off by default)

The mutating tools of `1c-metadata-manage` refuse to change an object of a vendor configuration that is locked by support (`docs/support-manage.md` of that skill). A direct `Edit` / `Write` / `MultiEdit` of the dump bypasses them. `hooks/support-guard.mjs` closes that gap as a `PreToolUse` hook:

- **Opt-in:** `SUPPORT_GUARD_HOOK=on` in the project's `.dev.env`. Without it, or without a `.dev.env`, `hooks/support-guard.sh` exits at once and never starts Node.
- **Reaction:** `SUPPORT_GUARD` from the same `.dev.env` — `deny` (default) refuses the edit with the ready `support-edit` / extension advice, `warn` lets it through with a warning to the user, `off` skips the check. `.v8-project.json` is not read.
- **Rule:** the same as the tools' guard — `Ext/ParentConfigurations.bin` next to `Configuration.xml`, the object's own record, fail-closed on a support-state file that cannot be parsed. Only files of the dump are checked (`Configuration.xml`, `ConfigDumpInfo.xml`, `Ext/`, the metadata folders); notes kept beside a dump are not.
- **Runtime:** Node 18+ on `PATH` and a POSIX `sh` (Git Bash on Windows, as for the installer hook). An opted-in project without Node gets one notice per edit and the edit proceeds; a hook error never blocks.
- **Hosts:** Claude Code only, with this plugin enabled. Other hosts and a plain `install.ps1` install keep the tools' own guard.

Port of upstream cc-1c-skills `hooks/support-guard.mjs` (MIT) — notice in `hooks/NOTICE.md`. Tests: `tools/tests/support-guard-hook.ps1` (the hook against the PowerShell guard on the same synthetic dumps).

## Local check

On macOS or Linux, use `pwsh -NoProfile -File` if PowerShell is installed. If it is absent, invoke the install/update skill in Codex; `invoke-install.sh` exits with an error instead of reporting success.

```powershell
# Plan only
powershell.exe -NoProfile -File .\plugins\1c-rules\scripts\invoke-install.ps1 -Action ensure -Tool cursor -ProjectRoot . -DryRun

# Claude Code, this checkout
claude --plugin-dir .\plugins\1c-rules

# Support-guard hook
powershell.exe -NoProfile -File .\tools\tests\support-guard-hook.ps1
```
