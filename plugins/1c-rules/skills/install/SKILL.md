---
name: install
description: Install 1c-rules into the current 1C project. Use when the user asks to install 1C rules, поставить правила 1С, or bootstrap 1c-rules after adding the marketplace plugin.
---

# Install 1c-rules

This plugin does not load `content/rules` from the plugin cache. The PowerShell and agent-driven channels both adapt the source files through `adapters/*.yaml` into the current project.

## Host tool id

| Host | `-Tool` |
| --- | --- |
| Cursor | `cursor` |
| Claude Code | `claude-code` |
| Codex | `codex` |
| OpenCode | `opencode` |
| Kilo Code / Kilo CLI | `kilocode` |

## Steps

1. Resolve the **project root** (the 1C repo, never `~/.claude`, `~/.cursor`, `~/.config/kilo`, or the user home).
2. If PowerShell is available, run the plugin script from this plugin's `scripts/` directory. On Windows use `powershell.exe`; on macOS or Linux use `pwsh`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<plugin>/scripts/invoke-install.ps1" -Action init -Tool <tool-id> -ProjectRoot "<project-root>"
```

The script finds the local `1c-rules` checkout when you are developing this repo; otherwise it clones `https://github.com/comol/ai_rules_1c.git` and runs that `install.ps1`. If neither PowerShell executable is available, clone that repository (or reuse a local checkout), then follow its `AGENT-INSTALL.md` agent-driven installation channel with `adapters/<tool-id>.yaml`. It produces the same project layout and manifest; do not install PowerShell just for this task.

3. Verify the selected channel's result using `AGENT-INSTALL.md` post-placement gates. For the PowerShell channel, success ends with the `install.ps1` verification lines. Do not claim success if a gate failed.
4. Tell the user to restart the AI client if MCP configs changed.

Do not copy `content/` verbatim into a host directory or the plugin cache. Follow the selected adapter's transforms. Do not put on-demand rules into `.claude/rules/` or `.kilo/rules/`.
