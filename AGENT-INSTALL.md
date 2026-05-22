# 1C Rules — Installation, Migration and File Layout

This document describes the installation, update and migration mechanics of the `1c-rules` toolkit and the layout of files it manages.

## Installation channels

`1c-rules` ships with two equivalent channels. They produce the **same** on-disk layout and the **same** `.ai-rules.json` manifest:

1. **Agent-driven channel (default).** The AI agent reads this document and `adapters/*.yaml`, then places files into the project. No external CLI required. This is the default when the user asks the agent to install rules.
2. **PowerShell channel (fallback).** `install.ps1` implements the same protocol deterministically through a CLI. Use it when the agent is unavailable, the environment is restricted, or you want a reproducible CI/CD-friendly run.

A project installed by one channel can later be updated by the other.

## Agent protocol (read this if you are the agent)

If the user asks you to install or update `1c-rules`, follow this protocol from the **project root** (the directory where `AGENTS.md` should live).

### Defaults — no questions when the answer is obvious

- **Channel** — agent-driven by default. Do not ask the user to choose between the agent and PowerShell channels. If you cannot perform filesystem operations, fall back to PowerShell silently.
- **Source** — local clone of `1c-rules` if the user pointed at one; otherwise `https://github.com/comol/ai_rules_1c` (default).
- **Active tools** — auto-detect from the project. A tool is "active" if its `detection:` block in `adapters/<tool>.yaml` matches (e.g. `.cursor/` for Cursor, `CLAUDE.md` or `.claude/` for Claude Code, etc.).
  - **Exactly one tool detected** — proceed silently with that tool. Do not ask.
  - **Zero tools detected** — ask once: "No AI tool directory detected. Which tools should I install for? (`cursor`, `claude-code`, `codex`, `opencode`, `kilocode`, `other`)". The `other` option is a universal fallback for any AI client that is not in the explicit list — it places `AGENTS.md` at the project root and writes on-demand rules / agents / commands / skills / MCP config under `.ai-agent/` in a portable, tool-agnostic layout.
  - **Two or more tools detected** — ask once: "Detected: `<list>`. Press Enter to install for all, or specify a subset.".
- **`other` is never auto-detected.** It is selected only when the user explicitly types it in the prompt above or passes `-Tools other` to the PowerShell installer. When `other` is combined with a "real" tool, `AGENTS.md` still references the real tool's rules directory (priority order `cursor → claude-code → kilocode → opencode → codex → other`); `.ai-agent/rules/` becomes the canonical referenced directory only when `other` is the sole active tool.
- **Confirmation** — only required when migrating an existing user-modified `AGENTS.md`/`CLAUDE.md`, or when the operation would overwrite user-modified managed files. See *Confirm before destructive actions* below.

### Lean placement — do not read every file

The agent SHOULD NOT read the body of every rule/agent/command/skill file before placing it. Token budget on agent-driven installs is dominated by such reads, and the placement protocol does not require knowing the body — only the YAML frontmatter (and only for files that have one).

Use this lean sequence:

1. **Resolve the source.** If only a URL was given, clone it locally (`git clone https://github.com/comol/ai_rules_1c.git <cache-dir>/1c-rules`) or reuse an existing clone.

2. **Read adapters only.** For each active tool open `adapters/<tool>.yaml` from the clone. These files are small and define, in a closed schema:
   - `detection` — how to confirm the tool is active.
   - `rules`, `agents`, `commands`, `skills` — `copyTo` target paths (with `{name}` placeholder), `frontmatter.keep`/`drop`/`rename`/`addIf` operations, and copy `mode` (default per-file with frontmatter ops; `verbatim` for skills; `rebuild-toml` for Codex agents).
   - `mcp` — how `content/mcp-servers.json` is rendered into the tool's MCP config.
   - `entry` — optional entry-point template (e.g. minimal `CLAUDE.md` pointing at `AGENTS.md`).

3. **Bulk-copy directories.** For each active tool, copy whole directories from `content/` to the adapter's target paths in one shell call each. Do **not** open file bodies during the copy:
   - `content/rules/` → `<rules.copyTo dir>/`
   - `content/agents/` → `<agents.copyTo dir>/`
   - `content/commands/` → `<commands.copyTo dir>/`
   - `content/skills/` → `<skills.copyTo dir>/` (mode `verbatim` — copy each skill folder as-is, no transformation)
   - `content/openspec-bundle/<tool>/` → at the locations encoded in that snapshot, **skip-if-exists**.

4. **Apply frontmatter operations only where needed.** For sections that have `frontmatter.keep` / `drop` / `rename` / `addIf`:
   - For each placed file, read **only** the YAML frontmatter block (between the leading `---` markers — typically the first 5–20 lines). Do not read the body.
   - Rewrite the frontmatter according to the adapter ops and write it back; the body is left untouched.
   - For sections with `mode: verbatim` (skills) — skip the frontmatter step entirely.
   - For Codex agents (`mode: rebuild-toml`) — render via the adapter's `template`. This is the one case that requires the body, but only for those agent files in `content/agents/` (a small set).

5. **Render the MCP config** from `content/mcp-servers.json` according to the adapter's `mcp.schema` (mcpServers JSON dictionary, OpenCode `mcp[id]` schema, or Codex TOML `[mcp_servers.<id>]`).

6. **Place the always-on layer** (`AGENTS.md`, `USER-RULES.md`, `memory.md`) — see the next section.

7. **Place `.dev.env`** at the project root if missing — see *.dev.env bootstrap* below. This is mandatory: `.dev.env` is the single source of truth for project parameters used by all rules / commands / subagents (code-generation params and infobase connection params, including the web-publish URL for UI tests).

8. **Scaffold OpenSpec.** Copy `openspec/` into the project in skip-if-exists mode (no overwrites).

9. **Write the manifest** `.ai-rules.json` at the project root: list all placed files with their content sources, the active tools, the source version (`git describe --tags --always` from the clone), the protocol version (`1.0`), the canonical rules directory used for diagnostics / updates, and any detected foreign user-authored files under `foreignFiles`.

### Always-on layer placement

`AGENTS.md`, `USER-RULES.md`, and `memory.md` always live at the **project root**. This is required: every supported tool (Cursor, Claude Code, Codex, OpenCode, Kilo Code) reads `AGENTS.md` from the project root as its always-on context. Placing them under `.cursor/`, `.claude/` etc. would prevent the tools from picking them up.

`AGENTS.md` placement is a readable-copy step with deterministic path rewriting:

1. Read the source `AGENTS.md` from the clone. It is maintained as a human-readable source document with explicit source-repository paths (`content/rules/<name>.md`, `content/agents/<name>.md`, `content/commands/<name>.md`, `content/skills/<rest>`), not as an opaque placeholder-heavy template.
2. Resolve the **canonical artefact layout** per section. For each of `rules`, `agents`, `commands`, `skills`, walk the priority order `cursor → claude-code → kilocode → opencode → codex → other` and pick the first active tool whose adapter declares `<section>.copyTo`. The result is, per section, a `(directory, extension)` pair derived by stripping `{name}...` from the `copyTo` template. Record the canonical rules directory in `.ai-rules.json` for diagnostics and update logic; the other sections are recomputed on every refresh from the active tool set.
3. Rewrite the source text by substituting `content/<section>/...` paths with the per-section canonical installed paths so every path in the file resolves to an existing project-local file:
   - `content/rules/<name>.md` → `<rulesDir>/<name>.<rulesExt>` (e.g. `.cursor/rules/<name>.mdc`, `.claude/rules/<name>.md`).
   - `content/agents/<name>.md` → `<agentsDir>/<name>.<agentsExt>` (e.g. `.codex/agents/<name>.toml` when Codex is canonical).
   - `content/commands/<name>.md` → `<commandsDir>/<name>.<commandsExt>` (Codex commands resolve to `~/.codex/prompts/<name>.md` when Codex is the only active tool).
   - `content/skills/<rest>` → `<skillsDir>/<rest>` — skills are copied verbatim, so any subpath after `content/skills/` (`SKILL.md`, `docs/<file>.md`, `tools/...`) is preserved untouched.
   - The name regex matches both real names and prose placeholders like `<name>`, so illustrative paths in the body are also rewritten consistently.
4. Write the rewritten text to the project root as `AGENTS.md`. Refresh on update only if the local file is unmodified since the previous installer write (manifest hash matches) — preserve user edits otherwise.
5. If no active tool defines a rules directory (degenerate install set), skip the rewriting step and warn — the source paths are kept as-is so the file at least documents the intended layout.

`USER-RULES.md` and `memory.md` are created from the templates on first install and **never** overwritten thereafter.

### `.dev.env` bootstrap

`.dev.env` is mandatory and must be created at the project root on first install. It is the single source of truth for project parameters across all rules, on-demand instructions, slash commands and subagents — both code-generation parameters (`PREFIX`, `COMPANY`, `DEVELOPER`, `PLATFORM_VERSION`, comment templates, `NEW_OBJECTS_IN`) and infobase connection parameters used by `/loadfrom1cbase`, `/update1cbase`, `/getconfigfiles`, `/deploy-and-test` and the `1c-tester` subagent (`PLATFORM_PATH`, `INFOBASE_KIND`, `INFOBASE_PATH`, `IB_USER`, `IB_PASSWORD`, `EXTENSION_NAME`, `EXPORT_PATH`, `LOG_PATH`, `INFOBASE_PUBLISH_URL`).

Bootstrap procedure:

1. If `.dev.env` already exists at the project root — leave it untouched, just record the entry in `.ai-rules.json` (`template: true`). User values are sacred.
2. If missing — read the source `.dev.env.example`, then auto-fill what can be detected without asking the user:
   - `PLATFORM_VERSION` ← `CompatibilityMode` from `Configuration.xml` (or `ConfigurationExtension.xml`).
   - `PLATFORM_PATH` ← scan `C:\Program Files\1cv8\<version>\bin\1cv8.exe` (and `(x86)`) for the highest installed version that matches or exceeds `PLATFORM_VERSION`.
   - `PREFIX` ← `NamePrefix` from `ConfigurationExtension.xml` when the project is an extension.
3. In interactive mode (agent channel, or PowerShell installer without `-NonInteractive`) — offer a one-time setup prompt for the **highly-desirable** fields that the user is most likely to need: `INFOBASE_PATH` (критично для `/update1cbase`, `/getconfigfiles`, `/loadfrom1cbase`, `/deploy-and-test`), `INFOBASE_PUBLISH_URL` (критично для UI-тестирования через `1c-tester`), and the defaulted `INFOBASE_KIND`, `IB_USER` / `IB_PASSWORD` (empty = no authentication, the `/N` / `/P` flags are simply omitted — fully valid for dev / test infobases), `LOG_PATH` (empty = `$env:TEMP\1cv8.log` / `$TMPDIR/1cv8.log` — fully valid). Each prompt must have an obvious "skip" option — **leaving any of them empty is always valid**, it just means the corresponding command will use the documented default (`IB_USER` / `IB_PASSWORD` / `LOG_PATH`), ask later when it is actually invoked (`INFOBASE_PATH`), or silently skip UI tests (`INFOBASE_PUBLISH_URL`). Advisory fields (`PREFIX`, `COMPANY`, `DEVELOPER`) may also be offered with the same skip choice, but they MUST NOT be re-asked on every task per `content/rules/dev-standards-core.md §1 → "Advisory parameters"`. **No field in `.dev.env` is mandatory at install time** — the installer must never block install over a missing parameter.
4. In non-interactive mode (`-NonInteractive` / agent without ability to ask) — leave non-detected critical fields empty and emit a clear WARNING listing them. Do not block installation.
5. Write the file to the project root and record it in `.ai-rules.json` with `template: true` so the file is never overwritten by subsequent updates.

The legacy `infobasesettings.md` file (used by earlier versions of `/loadfrom1cbase`, `/update1cbase`, `/deploy-and-test`, `1c-tester`) is no longer supported. If you find it during install or update, migrate its values into `.dev.env` (key names match; convert markdown/list entries to `KEY=value`), preserve any existing `.dev.env` values unless the legacy value fills an empty key, and delete `infobasesettings.md` only after a successful migration.

### Update / add / remove

- **Update** — re-read the source clone, re-place all managed files, refresh `AGENTS.md` (template substitution against the current active tool set, idempotent on repeated updates). Files marked `userModified` in the existing `.ai-rules.json` are preserved. As part of update, **migrate** any legacy `.ai-rules/rules/*` entries (from earlier installer versions): delete those files and remove them from the manifest. If the user modified any of them, ask before deleting.
- **Add `<tool>`** — same as init but for one additional tool only; merge into the existing manifest. After adding, refresh `AGENTS.md` against the **full** active tool set — the canonical rules dir may shift if the new tool has higher priority.
- **Remove `[<tool>]`** — delete files this tool owns according to the manifest. With no tool argument — delete every managed file and the manifest itself (the user keeps `USER-RULES.md`, `memory.md`, OpenSpec content, and any `*.bak.md`).

### Confirm before destructive actions

If a target file already exists with user modifications (different from any prior managed copy), ask the user before overwriting. Default for ambiguous cases — keep the user's version. The legacy `.ai-rules/rules/` migration step is the one place where a user-modified file in that legacy directory triggers an explicit confirmation before deletion.

### Important constraints

- **Do not edit `AGENTS.md` directly** in the project — it is refreshed on every update from the source `AGENTS.md` when safe.
- **Do not modify `USER-RULES.md` or `memory.md`** outside the migration markers — they belong to the user/project.
- **Manifest is authoritative** — if `.ai-rules.json` exists, trust it for "what is currently managed". A file not in the manifest is a foreign file: record it under `foreignFiles`, do not touch it.
- **Skip-if-exists for OpenSpec** — never overwrite specs or change proposals.

## PowerShell fallback (`install.ps1`)

If the agent cannot do the placement (no FS access, restricted environment, CI run), use the PowerShell channel:

```powershell
git clone https://github.com/comol/ai_rules_1c.git $env:TEMP\1c-rules
& $env:TEMP\1c-rules\install.ps1 init -Source $env:TEMP\1c-rules
```

The script implements the protocol above. Notes:

- `-Source` accepts a local path or a Git source URL (`https://...`, `git@...`, or a value ending with `.git`). URL sources are cloned into the installer's cache before placement.
- Run from the **project root**; the script writes there.
- Commands: `init` / `update` / `add <tool>` / `remove [<tool>]` / `doctor` (read-only diagnostic) / `eject` (delete the manifest, leave files in place).
- Flags: `-Tools cursor,claude-code` (explicit list), `-NonInteractive` (auto-resolve prompts), `-AssumeYes` (answer yes to confirmations but still pause on destructive conflicts unless `-NonInteractive` is also set).

### Do NOT pipe `install.ps1` into `Invoke-Expression`

`install.ps1` declares `[CmdletBinding()]` and `param(...)` at the top. These are valid only at the top of a `.ps1` file executed as a script — they are **not** valid inside `Invoke-Expression` (`iex`) of raw text. The following one-liners will fail with `Unexpected attribute 'CmdletBinding'` / `Unexpected token 'param'` and **must not be used**:

```powershell
# WRONG — will throw "Unexpected attribute 'CmdletBinding'"
iex (irm https://raw.githubusercontent.com/comol/ai_rules_1c/main/install.ps1)
iex "$(irm https://raw.githubusercontent.com/comol/ai_rules_1c/main/install.ps1) init"
```

Always run the script as a local file. If a no-`git` environment forces a one-liner, use a script block — it preserves `param(...)` semantics — but the script still needs a resolvable `-Source` value:

```powershell
$tmp = Join-Path $env:TEMP '1c-rules'
git clone https://github.com/comol/ai_rules_1c.git $tmp
& ([scriptblock]::Create((Get-Content "$tmp\install.ps1" -Raw))) init -Source $tmp
```

Do not execute raw script text from GitHub with `Invoke-Expression`; download or clone the repository first so `install.ps1` can read `content/` and `adapters/`.

## File ownership

- `AGENTS.md` — copied from the readable source `AGENTS.md` with per-section path rewriting (see *Always-on layer placement* above) and refreshed on every update when safe. The shipped file points at `content/<section>/...` paths in the source repo; the installed file in the project root points at the active tool's installed paths (e.g. `.cursor/rules/...mdc`, `.claude/skills/...`, `.kilo/agents/...`) so every link resolves to an existing project-local file. **Do not edit it directly** — your edits may be overwritten on the next update if the file is still installer-managed and unmodified.
- `USER-RULES.md` — created empty by the installer on first install and **never** overwritten thereafter. Project- or team-specific conventions go here.
- `memory.md` — project memory file at the project root. Created on first install and not overwritten by the installer.
- `.dev.env` — single source of truth for project parameters (code generation + infobase connection + web-publish URL for tests). Created on first install with auto-detected values where possible (PLATFORM_VERSION, PLATFORM_PATH, PREFIX) and prompts for the rest in interactive mode. **Never** overwritten by the installer; gitignored by default.
- On-demand rule files — placed under each active tool's `rules.copyTo` directory (`.cursor/rules/*.mdc`, `.claude/rules/*.md`, `.kilo/rules/*.md`, `.codex/rules/*.md`, `.opencode/rules/*.md`, `.ai-agent/rules/*.md` for `other`). All copies contain the same authoritative text; per-tool frontmatter differs (e.g. Cursor keeps `globs`/`alwaysApply`; `other` keeps only the minimum portable subset `description` + `alwaysApply`). `AGENTS.md` references one canonical directory — the highest-priority active tool's. Other active tools' rules dirs are still populated so that tool-native auto-loading (Cursor's `.cursor/rules/*.mdc` indexing) keeps working.
- `content/agents/*.md` — full role descriptions and prompts for the 13 specialized subagents. Source file names use short names such as `developer.md` / `explorer.md`; the installed agent id is defined by each file's frontmatter. Each AI tool discovers them from its own agents directory after install.

## USER-RULES.md

AI agents read `USER-RULES.md` together with `AGENTS.md`, so anything added there becomes part of the always-on context.

Typical contents:

- Project- or team-specific conventions and review rules.
- `@-imports` of supplementary files maintained in tool-native locations, for example:

  ```markdown
  @.cursor/rules/<your-rule>.mdc
  @.claude/agents/<your-agent>.md
  ```

The installer detects foreign (user-authored) files and records them in `.ai-rules.json` under `foreignFiles`, but it does **not** modify `AGENTS.md` or `USER-RULES.md` to reference them — such imports must be added manually to `USER-RULES.md`.

## Migration on first install

If at first install the project already had an `AGENTS.md` or `CLAUDE.md` with custom content, the installer renames those files to `AGENTS.md.bak.md` / `CLAUDE.md.bak.md` and inlines their original content into `USER-RULES.md` between migration markers. The migrated block should be reviewed: keep what is needed and remove the rest.

## Migration from earlier `1c-rules` versions

Earlier versions of `1c-rules` created a shared `.ai-rules/rules/` mirror at the project root. The current version no longer creates it — on-demand rules live under the active tool's directory and `AGENTS.md` is rendered to point there. On `update`, the installer detects the legacy mirror and removes it. If you have manual edits in `.ai-rules/rules/`, the installer will warn before deleting and ask for confirmation (or skip in `-NonInteractive` mode unless `-AssumeYes` is set).

## OpenSpec workspace

The project ships an [OpenSpec](https://github.com/Fission-AI/OpenSpec) workspace at the repository root. The `1c-rules` installer scaffolds it unconditionally on first install (skip-if-exists; existing files are never overwritten) and records the result in `.ai-rules.json` under `integrations.openspec`.

OpenSpec slash commands (`/opsx:propose`, `/opsx:apply`, `/opsx:archive`, `/opsx:explore`) and the matching SKILLs are placed automatically by the `1c-rules` installer for every active tool from a bundled snapshot of `openspec init` output (see `content/openspec-bundle/`); no `npm` and no OpenSpec CLI are required at install time. The snapshot's CLI version is recorded in `.ai-rules.json` under `integrations.openspec.artifactsBundleVersion` and is refreshed whenever `1c-rules` is updated.

Bundles are shipped for `cursor`, `claude-code`, `codex`, `opencode`, `kilocode`. The `other` adapter (universal fallback) has no OpenSpec bundle — its users continue to read `openspec/specs/` and `openspec/changes/` directly and invoke OpenSpec workflows manually, without project-rendered slash commands. This is recorded in `.ai-rules.json` under `integrations.openspec.bundleSkipped` for transparency.
