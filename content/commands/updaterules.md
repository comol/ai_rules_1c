---
description: Update the 1c-rules ruleset from GitHub (https://github.com/comol/ai_rules_1c)
---

# /updaterules — update 1c-rules

Source: `https://github.com/comol/ai_rules_1c`.

Action: update managed files in the current installation to the latest repository version (on-demand rules, subagent descriptions, slash commands, SKILL packages, MCP config, OpenSpec bundle, rendered `AGENTS.md`). Preserve:

- `USER-RULES.md`, `memory.md`, and `LLM-RULES.md` — one-time templates, never overwritten (a missing `LLM-RULES.md` on an older install is placed by this update);
- contents of `openspec/specs/` and `openspec/changes/` — copied in skip-if-exists mode;
- any managed file marked `userModified: true` in `.ai-rules.json`.

## Steps

1. Make sure `.ai-rules.json` exists at the project root. If it is missing, this is a first install: run `init` by `AGENT-INSTALL.md`, not `/updaterules`.

2. Run the PowerShell channel from the project root. `install.ps1` expects a local path in `-Source`, so first clone or update the source into a cache under `$env:TEMP`:

```powershell
$src = Join-Path $env:TEMP '1c-rules'
if (Test-Path (Join-Path $src '.git')) {
    git -C $src fetch --depth 1 origin HEAD
    git -C $src reset --hard FETCH_HEAD
} else {
    git clone --depth 1 https://github.com/comol/ai_rules_1c.git $src
}
& "$src\install.ps1" update -Source $src -AssumeYes
```

3. Check installer output:
   - `Update complete.` — success;
   - `User-modified files detected: N` — files with local edits; they are marked `userModified` and preserved;
   - `Verification OK` / `Verification found N mismatch(es)` — state of freshly placed files.

4. If PowerShell is unavailable (restricted environment, no `git`/`pwsh`), execute *Update / add / remove* from `AGENT-INSTALL.md` through the agent channel: re-place managed files from the updated clone, re-render `AGENTS.md`, and update `version` and `updatedAt` in `.ai-rules.json`. Do not touch `USER-RULES.md`, `memory.md`, or `LLM-RULES.md` (place the latter from the template only if absent).

## Parameters

- `-AssumeYes` — answers "yes" to confirmations and keeps user edits (`keep`) on conflicting files. For a fully automated run (CI), add `-NonInteractive`.
- `-Tools cursor,claude-code` — not needed: active tools are read from `.ai-rules.json`.
