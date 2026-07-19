# 1C Rules — Installation, Migration and File Layout

This document describes the installation, update and migration mechanics of the `1c-rules` toolkit and the layout of files it manages.

## Installation channels

`1c-rules` ships with two equivalent channels. They produce the **same** on-disk layout and the **same** `.ai-rules.json` manifest:

1. **Agent-driven channel (default).** The AI agent reads this document and `adapters/*.yaml`, then places files into the project. No external CLI required. This is the default when the user asks the agent to install rules.
2. **PowerShell channel (fallback).** `install.ps1` implements the same protocol deterministically through a CLI. Use it when the agent is unavailable, the environment is restricted, or you want a reproducible CI/CD-friendly run.

A project installed by one channel can later be updated by the other.

## Agent protocol (read this if you are the agent)

If the user asks you to install or update `1c-rules`, follow this protocol from the **project root** (the directory where `AGENTS.md` should live).

### Project root is mandatory — no global installs

`1c-rules` is a **project-scoped** toolkit. Every supported tool (Cursor, Claude Code, Codex, OpenCode, Kilo Code, `other`) reads its always-on context from the project root, and every on-demand rule / agent / command / skill lands under a project-local tool directory (`.cursor/`, `.claude/`, `.kilo/`, `.codex/`, `.opencode/`, `.ai-agent/`). Installing into a tool's **global CLI configuration directory** (`~/.config/kilo/`, `~/.codex/`, `~/.claude/`, `~/.opencode/`, `%APPDATA%\…\<tool>\`, etc.) is **not supported and is forbidden**: such directories are owned by the CLI itself, the adapter targets (`.kilo/commands/`, `.kilo/agents/`, …) do not match what the CLI looks up globally, `AGENTS.md` path rewriting yields broken links, and `.dev.env` / OpenSpec / `.ai-rules.json` have no project to bind to. A "global" install is always wrong, even when the user has not opened a project — there is nothing meaningful for the rules to attach to.

Before doing **any** filesystem operation, resolve the project root:

1. Use the working directory the agent was launched in if it is plausibly a project root (contains `Configuration.xml`, `ConfigurationExtension.xml`, a `src/` / `cf/` source dump, a `.cursor/` / `.claude/` / `.kilo/` / `.codex/` / `.opencode/` / `.ai-agent/` directory, a `.git/`, or an existing `AGENTS.md` / `.ai-rules.json`).
2. If the working directory **is** a tool CLI config directory (path matches `~/.config/<tool>`, `~/.codex`, `~/.claude`, `~/.opencode`, `%APPDATA%\…\<tool>`, or contains the CLI's own marker files such as `kilo.jsonc`, `config.toml` next to `prompts/`, `package.json` with `@kilocode/plugin` / `@openai/codex` / etc., or `bun.lock` / `package-lock.json` shipped by the CLI installer) — **STOP**. Do not install there.
3. If the working directory is anonymous (user's home, `Documents`, `Desktop`, `Downloads`, `/tmp`, `$env:TEMP`) — **STOP**.
4. When stopping, ask the user once: *"Установить правила в текущий каталог `<path>` — это похоже на конфиг-каталог Kilo CLI / Codex CLI / домашнюю папку, а правила ставятся per-project. Укажите путь к корню 1C-проекта, в который ставить правила."* Do not proceed with a guessed path, do not "install globally as a workaround", do not create a synthetic project folder.

The same rule applies to the PowerShell fallback: `install.ps1` requires being run from the project root. If a user pipes the installer into a global config directory, refuse with the same message.

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
   - `rules`, `agents`, `commands`, `skills` — `copyTo` target paths (with `{name}` placeholder), `frontmatter.keep`/`drop`/`rename`/`addIf`/`toolsToPermission` operations, and copy `mode` (default per-file with frontmatter ops; `verbatim` for skills; `rebuild-toml` for Codex agents). `toolsToPermission` (OpenCode only) converts the source `tools` array into OpenCode's `permission` object — see *OpenCode agents: `tools` array → `permission` object* below.
   - `mcp` — how `content/mcp-servers.json` is rendered into the tool's MCP config.
   - `entry` — optional entry-point template (e.g. minimal `CLAUDE.md` pointing at `AGENTS.md`).

3. **Bulk-copy directories.** For each active tool, copy whole directories from `content/` to the adapter's target paths in one shell call each. Do **not** open file bodies during the copy:
   - `content/rules/` → `<rules.copyTo dir>/`
   - `content/agents/` → `<agents.copyTo dir>/`
   - `content/commands/` → `<commands.copyTo dir>/`
   - `content/skills/` → `<skills.copyTo dir>/` (mode `verbatim` — copy **every** skill folder as-is, no transformation). Copy the whole `content/skills/` directory; do **not** cherry-pick a subset. All skills are required, including the non-1C-domain ones (`caveman`, `prompt-enhancer`, `handoff`, `mermaid-diagrams`, `transcribe`, `md-to-docx`, `img-grid-analysis`) — `AGENTS.md` references them and silently skipping any of them leaves a degraded ruleset. Use a single directory copy, not per-skill judgement calls.
   - `content/openspec-bundle/<tool>/` → at the locations encoded in that snapshot, **skip-if-exists**.

4. **Apply frontmatter operations only where needed.** For sections that have `frontmatter.keep` / `drop` / `rename` / `addIf` / `toolsToPermission`:
   - For each placed file, read **only** the YAML frontmatter block (between the leading `---` markers — typically the first 5–20 lines). Do not read the body.
   - Rewrite the frontmatter according to the adapter ops and write it back; the body is left untouched.
   - **Agents: resolve `modelTier` first.** Source agent files declare an abstract `modelTier` (`coding` | `analysis` | `light`) instead of a concrete model name. Before applying the adapter ops, replace it with `modelHint: <concrete model>` taken from the project `.dev.env`: tier `coding` → `SUBAGENT_MODEL_CODING`, tier `analysis` → `SUBAGENT_MODEL_ANALYSIS`, tier `light` → `SUBAGENT_MODEL_LIGHT`. When the corresponding value is empty or `.dev.env` does not exist yet, simply **remove** `modelTier` and emit no model field — the AI client then uses its default model (all three parameters are DEFAULTED; never block or re-ask because of them). On first init the values may be asked once as part of the `.dev.env` bootstrap prompts — a benchmark-based profile picker offering `Balanced` / `Economy` / `Quality` (see *`.dev.env` bootstrap* below). After the resolution, the adapter ops apply as written (`keep`/`rename` reference `modelHint`).
   - For OpenCode agents (`agents.frontmatter.toolsToPermission`) — convert the source `tools` array into a `permission` object before applying `keep`/`drop`. See *OpenCode agents: `tools` array → `permission` object* below. **Never** copy the source `tools` array into an OpenCode agent file verbatim — an array fails OpenCode config validation and prevents OpenCode from (re)starting.
   - For sections with `mode: verbatim` (skills) — skip the frontmatter step entirely.
   - For Codex agents (`mode: rebuild-toml`) — render via the adapter's `template`. This is the one case that requires the body, but only for those agent files in `content/agents/` (a small set).

5. **Render the MCP config** from `content/mcp-servers.json` according to the adapter's `mcp.schema`. **External MCP check first:** before rendering anything, detect an external MCP installation (user env `BASESAI_MCP_GLOBAL_ROOT`, fallback `MCP_GLOBAL_ROOT` in the project `.dev.env`, pointing at a folder that contains `install.manifest.json`) — see *External MCP installation (INSTALL.md, режим 3)* below. When detected, **skip this step entirely for every tool** (do not write `.cursor/mcp.json` or any other `mcp.target`), sync the `mcp:install_forme` section of `USER-RULES.md` from the install artifacts, and record `integrations.mcp.mode = "external"` in `.ai-rules.json`. Otherwise render from `content/mcp-servers.json` according to the adapter's `mcp.schema` (mcpServers JSON dictionary, OpenCode `mcp[id]` schema, or Codex TOML `[mcp_servers.<id>]`). **OpenCode only:** normalize each server key to start with a letter before writing it under `mcp` — leading `1c`/`1C` → `onec` (so `1c-syntax-checker-mcp` → `onec-syntax-checker-mcp`, `1C-docs-mcp` → `onec-docs-mcp`), any other non-letter-leading id gets an `mcp-` prefix. OpenCode names MCP tools `<server-key>_<tool>` and providers like Moonshot/Kimi reject function names that do not start with a letter (`^[a-zA-Z_]…`), which otherwise breaks the whole request with *"function name is invalid, must start with a letter"*. Canonical ids in `content/mcp-servers.json` and the docs stay `1c-…`; only the OpenCode-rendered key changes. The other adapters keep the verbatim id (Cursor/Claude prefix tool names with `mcp_`/`mcp__`, so a digit-leading key is already safe there). **Target file & merge:** write each tool's MCP into the path declared by `mcp.target` — for OpenCode this is `opencode.json` at the **project root** (NOT `.opencode/opencode.json`, which OpenCode never reads; `.opencode/` holds only agents/commands/modes/plugins/skills/tools/themes), and for Kilo Code it is `.kilo/kilo.json` under the top-level `mcp` key. Both are **shared** user configs (`mcp.merge: true`): deep-merge **only** the top-level `mcp` key and preserve every other key the user has. **OpenCode validates each MCP entry with a strict schema** — emit only `{ type: "remote", url, enabled }` (or `{ type: "local", command: [...], enabled }`); any extra key such as `description` or `connection_id` makes OpenCode reject the whole config and the servers silently never load. After writing it, **recommend that the user restart the AI client** — see *Recommend a restart after MCP changes* below.

6. **Place the always-on layer** (`AGENTS.md`, `USER-RULES.md`, `memory.md`, `LLM-RULES.md`) — see the next section.

7. **Place `.dev.env`** at the project root if missing — see *.dev.env bootstrap* below. This is mandatory: `.dev.env` is the single source of truth for project parameters used by all rules / commands / subagents (code-generation params and infobase connection params, including the web-publish URL for UI tests).

8. **Scaffold OpenSpec.** Copy `openspec/` into the project in skip-if-exists mode (no overwrites).

9. **Write the manifest** `.ai-rules.json` at the project root: list all placed files with their content sources and `owners` (one or more active tools for shared paths), the active tools, the source version (`git describe --tags --always` from the clone), the protocol version (`1.1`), the canonical rules directory used for diagnostics / updates, and any detected foreign user-authored files under `foreignFiles`.

### OpenCode agents: `tools` array → `permission` object

The source agent files in `content/agents/*.md` declare capabilities as a `tools` **array** (e.g. `tools: ["Read", "Write", "Edit", "Grep", "Glob", "Shell", "MCP"]`). That shape is correct for Cursor and Claude Code, but **OpenCode rejects a `tools` array** — its `tools` field must be an object (`{write: true, ...}`) and is itself deprecated in favour of `permission` (OpenCode v1.1.1+). Copying the raw array into `.opencode/agent/<name>.md` fails OpenCode config validation and **prevents OpenCode from (re)starting**.

When OpenCode is an active tool, the `agents` adapter therefore declares `frontmatter.toolsToPermission`, which both installation channels MUST apply: convert the `tools` array into a `permission` object **before** the `keep`/`drop` step, then drop `tools` (it is absent from `keep`). The mapping is:

| Source tool | OpenCode permission key |
| --- | --- |
| `Read` | `read` |
| `Write`, `Edit` | `edit` |
| `Grep` | `grep` |
| `Glob` | `glob` |
| `Shell` | `bash` |
| `MCP` | *(no key — MCP tools are gated by their own names; leave them enabled by default)* |

Each mapped key granted by the source list is set to `allow`; every mapped key **not** granted is set to `deny`, so read-only agents (`1c-explorer`, `1c-code-reviewer`, `1c-arch-reviewer` — whose source `tools` omit `Write`/`Edit`/`Shell`) end up with `edit: deny` / `bash: deny` instead of silently inheriting OpenCode's permissive default tool set. Example for `1c-developer` (with `SUBAGENT_MODEL_CODING=anthropic/claude-sonnet-4-5` in `.dev.env`; when the parameter is empty the `model` line is omitted entirely and the subagent inherits the parent session's model):

```yaml
---
name: 1c-developer
description: "Expert 1C code developer agent. …"
model: anthropic/claude-sonnet-4-5
permission:
  read: allow
  edit: allow
  grep: allow
  glob: allow
  bash: allow
mode: subagent
---
```

**OpenCode model format.** OpenCode requires the `model` value in `provider/model` form (optional `#variant`, e.g. `anthropic/claude-sonnet-4-5#high`), using the ids shown by `/models` — a bare slug (`opus`, `glm-5.2-max`) does not resolve and an invalid id can make OpenCode reject the config and fail to start. The installer writes `SUBAGENT_MODEL_*` verbatim, so on OpenCode these keys **must** hold `provider/model` ids; the `/economymode` command enforces this when it asks for models. Cursor / Claude Code / Codex use their own bare-slug formats, so `.dev.env` model values are client-specific — set them for the client actually installed.

### Recommend a restart after MCP changes

After the MCP config is written (init / update / add), **recommend that the user restart their AI client** (CLI or IDE). Most clients — OpenCode in particular — read the MCP configuration and agent definitions only at startup, so newly added MCP servers and subagents will not appear in an already-running session until the client is restarted. This recommendation applies to all tools; the PowerShell installer prints it automatically at the end of `init` / `update` / `add` whenever at least one MCP server was configured.

### Announce the /economymode command

In the final report of a successful `init` — and of an `update` that placed `content/commands/economymode.md` into the project for the first time — include a short note (in Russian): режим экономии оркестратора включается командой `/economymode` — она записывает `ORCHESTRATION=economy` в `.dev.env`, после чего головной агент делегирует исполнение дешёвым субагентам (модели — по ярусам из `SUBAGENT_MODEL_*`), оставляя себе решения, спеки и верификацию; если модели ярусов не заданы, команда предложит выбрать их (профили по бенчу или свои слаги); действует на весь проект, включая новые чаты; выключение — `/economymode off` (правило `orchestrator-economy.md`). The PowerShell installer prints the equivalent announcement automatically.

### External MCP installation (INSTALL.md, режим 3)

When the MCP servers were installed by the MCP vendor distribution's **`INSTALL.md`** in multi-project mode (**режим 3** — `GLOBAL_ROOT` folder, `projects.registry.json`, dynamic per-project ports, two-level mcp.json: global in `%USERPROFILE%\.cursor\mcp.json` + per-project in `<path_code>\.cursor\mcp.json`), the installer must **not** overwrite any tool MCP config with `content/mcp-servers.json` — the static catalog (fixed ids, ports 8000–8008) would break the working per-project layout. The catalog stays authoritative only for **managed** installs.

**Detection (same order as `Detect-ExternalMcp` in `install.ps1`):**

1. User environment variable **`BASESAI_MCP_GLOBAL_ROOT`** (User scope, then process scope).
2. Fallback: **`MCP_GLOBAL_ROOT`** key in the project `.dev.env`.
3. External mode **only if** `<GLOBAL_ROOT>/install.manifest.json` exists. Env signal without the manifest → warn and fall back to managed.

**Artifact resolution — contract first, never hardcode.** Read `install.manifest.json` (`schema_version`, `artifacts`, `consumers`, `resolution`) and resolve all paths from it (placeholders `%USERPROFILE%`, `{global_root}`, `{path_code}`, `{mcp_root}`). A legacy manifest without `schema_version` resolves against the schema-v1 default contract (see `Get-DefaultMcpManifestContract` in `install.ps1`): registry at `<GLOBAL_ROOT>/projects.registry.json`, global servers in `%USERPROFILE%/.cursor/mcp.json`, project servers in `{path_code}/.cursor/mcp.json` (fallback `{mcp_root}/.cursor/mcp.json`). The current project is matched against `registry.projects[]` by `resolution.project_match` (default: normalized `path_code` == workspace root).

**In external mode the agent / installer must:**

- **Not create, not modify** `.cursor/mcp.json` or any other adapter `mcp.target` — for any tool.
- Read the **actual** server ids, urls, and descriptions from the resolved global + project mcp.json files; parse ports **from the `url`** (`localhost:<PORT>`), never from constants. Servers absent from the actual mcp.json are not listed (do not "fill in" from the 1c-rules catalog). Docker container names come **only** from `registry.projects[].containers.*`.
- Generate / refresh the block between `<!-- mcp:install_forme … -->` and `<!-- /mcp:install_forme -->` markers in `USER-RULES.md` with the resolved consumer paths and the actual server tables. Replace only the block; never touch content outside the markers. If the file contains `userModified: mcp:install_forme`, skip the regeneration and warn.
- Record in `.ai-rules.json`: `integrations.mcp` = `{ mode: "external", schemaVersion, contractSource, manifestPath, registryPath, registryProjectId, globalMcpConfig, projectMcpConfig, globalServerIds, projectServerIds, userRulesSection: "mcp:install_forme", detectedAt }`, and set `mcpServers` to `[]` (the external installation owns the server list; the restart recommendation does not apply since no config was rewritten).

**Install order to document for users:** 1) MCP via the distribution's `INSTALL.md` (режим 3; save `BASESAI_MCP_GLOBAL_ROOT` when offered), 2) `1c-rules` init in the project root (`path_code`), 3) restart the AI client. In this order the rules install never breaks the MCP links.

**CLI override:** `install.ps1 init|update -McpMode managed` forces the catalog render even when the external installation is detected; `-McpMode external` requires the external installation and fails fast when the signal or manifest is missing; default `-McpMode auto` detects.

### Always-on layer placement

`AGENTS.md`, `USER-RULES.md`, `memory.md`, and `LLM-RULES.md` always live at the **project root**. This is required: every supported tool (Cursor, Claude Code, Codex, OpenCode, Kilo Code) reads `AGENTS.md` from the project root as its always-on context. Placing them under `.cursor/`, `.claude/` etc. would prevent the tools from picking them up.

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

`USER-RULES.md`, `memory.md`, and `LLM-RULES.md` are created from the templates on first install (or on the first `update` for pre-existing installs) and **never** overwritten thereafter.

### `.dev.env` bootstrap

`.dev.env` is mandatory and must be created at the project root on first install. It is the single source of truth for project parameters across all rules, on-demand instructions, slash commands and subagents — both code-generation parameters (`PREFIX`, `COMPANY`, `DEVELOPER`, `PLATFORM_VERSION`, comment templates, `NEW_OBJECTS_IN`) and infobase connection parameters used by `/loadfrom1cbase`, `/update1cbase`, `/getconfigfiles`, `/deploy-and-test` and the `1c-tester` subagent (`PLATFORM_PATH`, `INFOBASE_KIND`, `INFOBASE_PATH`, `IB_USER`, `IB_PASSWORD`, `EXTENSION_NAME`, `EXPORT_PATH`, `LOG_PATH`, `INFOBASE_PUBLISH_URL`).

Bootstrap procedure:

1. If `.dev.env` already exists at the project root — leave it untouched, just record the entry in `.ai-rules.json` (`template: true`). User values are sacred.
2. If missing — read the source `.dev.env.example`, then auto-fill what can be detected without asking the user:
   - `PLATFORM_VERSION` ← `CompatibilityMode` from `Configuration.xml` (or `ConfigurationExtension.xml`).
   - `PLATFORM_PATH` ← scan `C:\Program Files\1cv8\<version>\bin\1cv8.exe` (and `(x86)`) for the highest installed version that matches or exceeds `PLATFORM_VERSION`.
   - `PREFIX` ← `NamePrefix` from `ConfigurationExtension.xml` when the project is an extension.
3. In interactive mode (agent channel, or PowerShell installer without `-NonInteractive`) — offer a one-time setup prompt for the **highly-desirable** fields that the user is most likely to need: `INFOBASE_PATH` (критично для `/update1cbase`, `/getconfigfiles`, `/loadfrom1cbase`, `/deploy-and-test`), `INFOBASE_PUBLISH_URL` (критично для UI-тестирования через `1c-tester`), and the defaulted `INFOBASE_KIND`, `IB_USER` / `IB_PASSWORD` (empty = no authentication, the `/N` / `/P` flags are simply omitted — fully valid for dev / test infobases), `LOG_PATH` (empty = `$env:TEMP\1cv8.log` / `$TMPDIR/1cv8.log` — fully valid), `SUBAGENT_MODEL_CODING` / `SUBAGENT_MODEL_ANALYSIS` / `SUBAGENT_MODEL_LIGHT` (empty = the AI client's default model; a benchmark-based profile picker fills all three at once; used to resolve the agents' `modelTier` — see *Lean placement*, step 4). Each prompt must have an obvious "skip" option — **leaving any of them empty is always valid**, it just means the corresponding command will use the documented default (`IB_USER` / `IB_PASSWORD` / `LOG_PATH` / `SUBAGENT_MODEL_*`), ask later when it is actually invoked (`INFOBASE_PATH`), or silently skip UI tests (`INFOBASE_PUBLISH_URL`). Advisory fields (`PREFIX`, `COMPANY`, `DEVELOPER`) may also be offered with the same skip choice, but they MUST NOT be re-asked on every task per `content/rules/dev-standards-env.md → "Advisory parameters"`. **No field in `.dev.env` is mandatory at install time** — the installer must never block install over a missing parameter.
4. In non-interactive mode (`-NonInteractive` / agent without ability to ask) — leave non-detected critical fields empty and emit a clear WARNING listing them. Do not block installation.
5. Write the file to the project root and record it in `.ai-rules.json` with `template: true` so the file is never overwritten by subsequent updates.

The legacy `infobasesettings.md` file (used by earlier versions of `/loadfrom1cbase`, `/update1cbase`, `/deploy-and-test`, `1c-tester`) is no longer supported. If you find it during install or update, migrate its values into `.dev.env` (key names match; convert markdown/list entries to `KEY=value`), preserve any existing `.dev.env` values unless the legacy value fills an empty key, and delete `infobasesettings.md` only after a successful migration.

### Update / add / remove

- **Update** — re-read the source clone, re-place all managed files, refresh `AGENTS.md` (template substitution against the current active tool set, idempotent on repeated updates). The `userModified` contract is **uniform across every placement branch** — artefact files (rules / agents / commands), the MCP config (`.mcp.json` / `opencode.json` / `.kilo/kilo.json` / …), the `entry` file (`CLAUDE.md`), and individual skill files: any file whose on-disk hash diverges from the recorded `installedHash` is flagged `userModified` and **preserved untouched**, never silently overwritten. In particular, a user who trimmed or reformatted the MCP server list keeps that trim across updates (the full catalogue is not silently restored), and a customised `CLAUDE.md` or edited skill file survives. The update report explicitly lists which files were **left at their previous version** so "Update complete" never hides a stranded file.
  - **Escape hatch** — `-Force` overwrites every drifted file with the shipped version ("take theirs"); `-ForcePaths <path>[,<path>…]` (comma-separated, implies `-Force`) restricts the overwrite to specific files (exact path or `*`/`?` wildcard, e.g. `.claude/skills/*`), leaving all other user edits intact. This is the supported way to pull updates into a file that drifted (including files mis-flagged by an older installer build) without hand-editing `.ai-rules.json`.
  - **Skill files** are synced per-file rather than wiped-and-recopied: shipped files are refreshed, files dropped from the source are pruned, user-modified skill files are preserved, and files the user added into the skill directory themselves (never tracked by us) are always kept.
  - As part of update, **migrate** any legacy `.ai-rules/rules/*` entries (from earlier installer versions): delete those files and remove them from the manifest. If the user modified any of them, ask before deleting.
- **Add `<tool>`** — same as init but for one additional tool only; merge into the existing manifest. After adding, refresh `AGENTS.md` against the **full** active tool set — the canonical rules dir may shift if the new tool has higher priority.
- **Remove `[<tool>]`** — delete files this tool owns according to the manifest. Manifest entries carry an `owners` list because two tools may intentionally share one path (currently Claude Code and OpenCode share `.claude/skills/`); removing one owner keeps the file until the last owner is removed. With no tool argument — delete every managed file and the manifest itself (the user keeps the placed-once templates — `USER-RULES.md`, `memory.md`, `LLM-RULES.md`, `.dev.env` — plus OpenSpec content and any `*.bak.md`).

### Anti-patterns observed in the wild — do not repeat

Failures from past agent-driven installs that the protocol explicitly forbids:

- **Installing into the CLI's global config directory.** Symptom: files copied to `~/.config/<tool>/`, `~/.codex/`, `~/.claude/`, `~/.opencode/` or `%APPDATA%\…\<tool>\`. See *Project root is mandatory — no global installs* above.
- **Inventing directory names instead of reading the adapter.** The on-disk layout per tool is **only** what `adapters/<tool>.yaml` declares under `rules.copyTo`, `agents.copyTo`, `commands.copyTo`, `skills.copyTo`, `mcp.target`. Do not paraphrase: Kilo uses `.kilo/commands/` and `.kilo/agents/` (plural) — never `.kilo/command/` / `.kilo/agent/` (singular). The strings `commands`, `agents` are part of the targeted CLI's lookup contract.
- **Overwriting an externally-managed MCP config with the static catalog.** Symptom: after installing the rules, `.cursor/mcp.json` of a project set up via the MCP distribution's `INSTALL.md` (режим 3) suddenly points at ports 8000/8006 instead of the project's registry-assigned ports (8200/8206, …), and the MCP tools stop responding. The MCP phase MUST run the external-installation detection first (see *External MCP installation (INSTALL.md, режим 3)* above) and skip rendering when `BASESAI_MCP_GLOBAL_ROOT` + `install.manifest.json` are present. `content/mcp-servers.json` is a default catalog for managed installs, not a source of truth that may overwrite a working configuration.
- **Writing OpenCode MCP into `.opencode/opencode.json` instead of the root `opencode.json`.** OpenCode reads its project config (including the `mcp` key) only from `opencode.json` at the project root. `.opencode/` is for agents/commands/modes/plugins/skills/tools/themes, never the main config file, so MCP written under `.opencode/` is silently ignored — `/mcp` shows nothing and no MCP tools are exposed. Write to the root `opencode.json` and deep-merge only the `mcp` key (per `adapters/opencode.yaml > mcp.target` + `mcp.merge`).
- **Injecting unknown keys into an OpenCode MCP entry (`description`, `connection_id`, …).** OpenCode validates each entry with a strict schema; an extra key makes it reject the whole config and load no servers. Emit only the documented keys: `{ type: "remote", url, enabled }` / `{ type: "local", command, enabled, environment? }`.
- **Cherry-picking which skills to copy.** Symptom: some skills (often the non-1C-domain ones — `caveman`, `prompt-enhancer`, `handoff`) missing from the tool's skills directory because the agent decided they were "not 1C". The protocol copies **every** folder under `content/skills/` verbatim in one directory copy; there is no per-skill relevance judgement at install time.
- **Emitting a Claude Code HTTP MCP entry without `"type": "http"`.** Claude Code's `.mcp.json` requires an explicit `"type": "http"` on every remote (URL-based) server; without it the current Claude Code (VS Code extension and CLI) silently does not load the server and it never appears in the tool list. Emit `{ "type": "http", "url": … }` (optionally `headers`), and do **not** copy the Cursor-only `connection_id` / `description` keys into the Claude Code config — they are not part of its schema. Local servers use `{ "command", "args", "env" }`.
- **Writing Kilo MCP into the legacy `.kilocode/mcp.json` with the `mcpServers` dictionary.** Current Kilo CLI / Kilo Code (v7.x+) does not read that file — MCP must go into `.kilo/kilo.json` (per `adapters/kilocode.yaml > mcp.target`) under the top-level `mcp` key with per-server entries `{ "type": "remote"|"local", "url"|"command": …, "enabled": true }` (see https://kilo.ai/docs/automate/mcp/using-in-cli). Writing the legacy shape silently disables MCP discovery; `/mcps` shows an empty list and agent tool calls fail because no MCP tools are exposed. The installer deep-merges only the `mcp` key into `.kilo/kilo.json`, so user-added `instructions` / `skills.paths` / `permission` keys in that file are preserved across `update`.
- **Dumping the whole `1c-rules` repo into the project as a vendor subfolder.** Symptom: `./1c-rules/AGENTS.md`, `./1c-rules/content/...` appearing under the project / config directory and being referenced from the tool's entry config. The protocol places files **per section** at the adapter's `copyTo` targets; the source clone is only a staging area outside the project. Vendoring the source tree leaves `AGENTS.md` with unrewritten `content/...` paths and the tool with no skill discovery.
- **Hand-rolling frontmatter transforms with `node -e` / inline scripts.** Symptom: ad-hoc one-liners that only convert `modelHint → model` and forget `frontmatter.drop` / `addIf` rules. Use the adapter operations as a whole (read the YAML once, apply `keep` / `drop` / `rename` / `addIf` in one pass, write back) or run `install.ps1`, which already implements them.
- **Hooking up the tool entry config (`kilo.jsonc`, `.codex/config.toml`, `claude_desktop_config.json`, …) by hand.** The tool entry is whatever the adapter declares (e.g. `AGENTS.md` at the project root for tools that read it, the rendered MCP file at `mcp.target`). Do not add custom `instructions` / `skills.paths` arrays pointing at the staging clone — they bypass adapter-rewritten paths.
- **Skipping `AGENTS.md` rewriting, `.dev.env` bootstrap, OpenSpec scaffold, or `.ai-rules.json` manifest.** All four are mandatory steps of the lean sequence. An install that completes without them is incomplete and will fail later updates / diagnostics.
- **Using `Invoke-Expression` on the raw `install.ps1` URL** — see *Do NOT pipe `install.ps1` into `Invoke-Expression`* below.

### Confirm before destructive actions

If a target file already exists with user modifications (different from any prior managed copy), ask the user before overwriting. Default for ambiguous cases — keep the user's version. The legacy `.ai-rules/rules/` migration step is the one place where a user-modified file in that legacy directory triggers an explicit confirmation before deletion.

### Important constraints

- **Do not edit `AGENTS.md` directly** in the project — it is refreshed on every update from the source `AGENTS.md` when safe.
- **Do not modify `USER-RULES.md`, `memory.md`, or `LLM-RULES.md`** outside the migration markers — they belong to the user/project (`LLM-RULES.md` is maintained solely by the `/evolve` command).
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
- Flags: `-Tools cursor,claude-code` (explicit list), `-NonInteractive` (auto-resolve prompts), `-AssumeYes` (answer yes to confirmations but still pause on destructive conflicts unless `-NonInteractive` is also set), `-Force` (on `update`: overwrite user-modified files with the shipped version), `-ForcePaths <path>[,<path>…]` (on `update`: restrict the overwrite to the listed project-relative paths, comma-separated; exact match or `*`/`?` wildcard; implies `-Force`), `-McpMode auto|managed|external` (MCP phase behaviour — see *External MCP installation* above; default `auto` detects an external installation and leaves MCP configs untouched when found).

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
- `LLM-RULES.md` — agent-maintained self-improvement rule layer at the project root, written only by the `/evolve` command with per-entry user approval (precedence and capture discipline — `AGENTS.md → Rules self-improvement`). Created on first install (template) and **never** overwritten by the installer.
- `.dev.env` — single source of truth for project parameters (code generation + infobase connection + web-publish URL for tests). Created on first install with auto-detected values where possible (PLATFORM_VERSION, PLATFORM_PATH, PREFIX) and prompts for the rest in interactive mode. **Never** overwritten by the installer; gitignored by default.
- On-demand rule files — placed under each active tool's `rules.copyTo` directory (`.cursor/rules/*.mdc`, `.claude/rules/*.md`, `.kilo/rules-1c/*.md`, `.codex/rules/*.md`, `.opencode/rules/*.md`, `.ai-agent/rules/*.md` for `other`). Kilo intentionally uses `rules-1c` rather than the eagerly auto-loaded `.kilo/rules/`; its rules are loaded through the rewritten paths in `AGENTS.md`. All copies contain the same authoritative text; per-tool frontmatter differs (e.g. Cursor keeps `globs`/`alwaysApply`; `other` keeps only the minimum portable subset `description` + `alwaysApply`). `AGENTS.md` references one canonical directory — the highest-priority active tool's. Other active tools' rules dirs are still populated for their own discovery or explicit path loading.
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

If at first install the project already had an `AGENTS.md` or `CLAUDE.md` with custom content, the installer renames those files to `AGENTS.md.bak.md` / `CLAUDE.md.bak.md` and inlines their original content into `USER-RULES.md` between migration markers. If the default backup name already exists, a numeric suffix is added instead of overwriting it. The migrated block should be reviewed: keep what is needed and remove the rest.

## Migration from earlier `1c-rules` versions

Earlier versions of `1c-rules` created a shared `.ai-rules/rules/` mirror at the project root. The current version no longer creates it — on-demand rules live under the active tool's directory and `AGENTS.md` is rendered to point there. On `update`, the installer detects the legacy mirror and removes it. If you have manual edits in `.ai-rules/rules/`, the installer will warn before deleting and ask for confirmation (or skip in `-NonInteractive` mode unless `-AssumeYes` is set).

## OpenSpec workspace

The project ships an [OpenSpec](https://github.com/Fission-AI/OpenSpec) workspace at the repository root. The `1c-rules` installer scaffolds it unconditionally on first install (skip-if-exists; existing files are never overwritten) and records the result in `.ai-rules.json` under `integrations.openspec`.

OpenSpec slash commands (`/opsx:propose`, `/opsx:apply`, `/opsx:archive`, `/opsx:explore`) and the matching SKILLs are placed automatically by the `1c-rules` installer for every active tool from a bundled snapshot of `openspec init` output (see `content/openspec-bundle/`); no `npm` and no OpenSpec CLI are required at install time. The snapshot's CLI version is recorded in `.ai-rules.json` under `integrations.openspec.artifactsBundleVersion` and is refreshed whenever `1c-rules` is updated.

Bundles are shipped for `cursor`, `claude-code`, `codex`, `opencode`, `kilocode`. The `other` adapter (universal fallback) has no OpenSpec bundle — its users continue to read `openspec/specs/` and `openspec/changes/` directly and invoke OpenSpec workflows manually, without project-rendered slash commands. This is recorded in `.ai-rules.json` under `integrations.openspec.bundleSkipped` for transparency.
