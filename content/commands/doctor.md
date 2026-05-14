---
description: Diagnose whether 1c-rules is installed, connected, configured, and usable by the current agent
---

# /doctor — 1c-rules readiness diagnostic

Run a read-only health check for the current project. The goal is to answer one question: **will the current agent actually use this ruleset safely for 1C work?**

Do not modify files, install packages, start containers, or write secrets. If a fix is obvious, report the exact next action instead of applying it.

## Output format

Return a compact status table with these statuses:

| Status | Meaning |
|---|---|
| **OK** | Check passed. |
| **WARN** | Work can continue, but something is incomplete or degraded. |
| **FAIL** | The ruleset or current task environment is not ready. |
| **SKIP** | Check is not applicable to this repository or current tool. |

After the table, list only actionable fixes. Do not include secret values from `.dev.env`.

## Check 1. Current agent and rules loading

1. Identify the current AI tool when possible: Cursor, Claude Code, Codex, OpenCode, Kilo Code, or `other`.
2. Check that `AGENTS.md` exists at the project root and is readable.
3. Check that `USER-RULES.md` and `memory.md` exist at the project root.
4. If `.ai-rules.json` exists, read it and verify:
   - `activeTools` contains the current tool, or explain why the current tool is still supported through `other`;
   - managed files listed in the manifest still exist;
   - the canonical rules directory referenced by the manifest exists.
5. If `.ai-rules.json` is missing:
   - in an installed project, report **FAIL** and recommend `install.ps1 init`;
   - in the source repository of `1c-rules`, report **WARN** and continue with source-layout checks.
6. Verify that the current tool has the files it can actually load:
   - Cursor: `.cursor/rules/`, `.cursor/commands/`, `.cursor/mcp.json` when installed;
   - Claude Code: `.claude/rules/`, `.claude/agents/`, `.claude/commands/`, MCP config when installed;
   - Codex: `.codex/skills/`, `.codex/config.toml` when installed;
   - OpenCode: `.opencode/command/`, `.opencode/opencode.json` when installed;
   - Kilo Code: `.kilo/rules/`, `.kilo/commands/`, `.kilo/agents/`, `.kilo/skills/`, `.kilocode/mcp.json` when installed;
   - other: `.ai-agent/rules/`, `.ai-agent/agents/`, `.ai-agent/commands/`, `.ai-agent/skills/`, `.ai-agent/mcp.json`.

Pass criterion: the root always-on files exist, and either the installed tool layout is present or the repository is clearly the `1c-rules` source repository being edited directly.

## Check 2. Ruleset file integrity

Check that these source files or their installed copies exist:

- `content/rules/*.md` or the active tool rules directory;
- `content/agents/*.md` or the active tool agents directory;
- `content/commands/*.md` or the active tool commands directory;
- `content/skills/*/SKILL.md` or the active tool skills directory;
- `content/mcp-servers.json` or the active tool MCP config;
- `.dev.env.example`;
- `openspec/README.md`, `openspec/specs/README.md`, `openspec/changes/README.md`.

Also check:

- all command files have frontmatter with `description`;
- all skill entry files have frontmatter with `name` and `description`;
- the subagent count matches the catalog in `content/rules/subagents.md`;
- every on-demand rule referenced from `AGENTS.md → Additional rules` exists;
- files governed by the source language policy are written in English, except 1C identifiers, Russian platform messages, BSL examples, metadata names, and user-facing Russian strings that are explicitly quoted as data.

## Check 3. `.dev.env` existence and completeness

1. Check that `.dev.env` exists at the project root.
2. If missing, report **FAIL** for operational commands and recommend creating it from `.dev.env.example` or running `install.ps1 init`.
3. If present, verify that critical fields are non-empty:
   - `PLATFORM_PATH`;
   - `INFOBASE_KIND`;
   - `INFOBASE_PATH`;
   - `LOG_PATH`;
   - `EXPORT_PATH` when the repository root is not the configuration source directory;
   - `PLATFORM_VERSION` when platform-version-specific docs or checks are needed.
4. Verify that `PLATFORM_PATH` contains `bin\1cv8.exe`.
5. Verify that `INFOBASE_KIND` is `file` or `server`.
6. Never print `IB_PASSWORD`, tokens, license keys, or full connection strings. Report only whether they are set.

Pass criterion: `.dev.env` exists, has the critical operational fields needed for load/dump/deploy/test commands, and does not require guessing.

## Check 4. OpenSpec workspace and `project.md`

1. Check that `openspec/README.md`, `openspec/specs/README.md`, and `openspec/changes/README.md` exist.
2. Check that `openspec/project.md` exists and is not empty.
3. If `Configuration.xml` or `ConfigurationExtension.xml` exists in the source tree, `openspec/project.md` must contain generated project context such as configuration name, compatibility mode / platform version, form mode, BSP version when known, top-level subsystems, and metadata counts.
4. If the repository is not a 1C source dump and has no `Configuration.xml` / `ConfigurationExtension.xml`, absence of rich project context is **WARN**, not **FAIL**.
5. If `openspec/project.md` is missing or empty in a 1C source dump, report **FAIL** and recommend running the project-context generation step from `install.ps1 init` / `install.ps1 update`.

Pass criterion: OpenSpec exists, and `openspec/project.md` is present and meaningful whenever a 1C source dump is available.

## Check 5. MCP session connectivity

Check MCP at two levels:

1. **Current session tools** — verify that expected tools are visible in the current agent tool schema when the server is configured:
   - `syntaxcheck` for `1c-syntax-checker-mcp`;
   - `templatesearch`, `remember`, `recall` for `1c-templates-mcp`;
   - `ssl_search` for `1c-ssl-mcp`;
   - `docinfo`, `docsearch` for `1C-docs-mcp`;
   - `metadatasearch`, `codesearch`, `search_function`, `get_module_structure` for `1c-code-metadata-mcp`;
   - `search_metadata`, `get_object_dossier`, `trace_impact`, `trace_call_chain` for `1c-graph-metadata-mcp`;
   - `check_1c_code`, `review_1c_code`, `its_help`, `fetch_its` for `1c-code-check-mcp`.
2. **Transport fallback** — when tools are missing but MCP config lists the server, run the `/checkmcp` algorithm: HTTP endpoint check, Docker state, and exact next action.

Pass criterion: required MCP tools for the expected 1C workflow are visible in the current session. HTTP-only availability is **WARN** because the agent still cannot call the tools until the client reconnects.

## Check 6. Active rules suitability

Evaluate whether the installed rules match the current repository and current agent:

1. If the repository contains 1C source files or metadata XML, confirm the 1C ruleset is appropriate.
2. If the repository is only the `1c-rules` source repository, report that BSL validators are not applicable to docs-only edits unless BSL examples are changed.
3. Confirm that `AGENTS.md` points to source or installed on-demand rules that the current agent can read.
4. Confirm that command names in `content/commands/` are available in the active tool's command location after installation.
5. Confirm that `caveman` is dev-only: enabled for implementation / debugging / deployment, off for review / analysis / documentation.

Pass criterion: the current agent has the always-on rules, can reach on-demand rules or their source copies, and the rule triggers match the current task type.

## Check 7. Cross-reference and Markdown integrity

Static check that the rule corpus is internally consistent. Operate on the **source layout** when running inside the `1c-rules` source repository, or on the installed copies under the canonical rules directory when running inside an installed project.

Scope:

1. **Rule index completeness.** Every file under `content/rules/*.md` (source) or the canonical rules directory (installed) is listed in `AGENTS.md → Additional rules`. Any file present on disk but missing from the index is an **orphan**; any name in the index without a matching file is a **dangling reference**. Report both.
2. **Subagent index completeness.** Every file under `content/agents/*.md` is listed in `content/rules/subagents.md → Subagent catalog`. The subagent count claimed in `AGENTS.md` and `subagents.md` matches the actual file count.
3. **Skill index completeness.** Every SKILL package under `content/skills/<name>/SKILL.md` is mentioned at least once in `AGENTS.md` (in the always-on or supplementary skill list) or in `README.md → Сопутствующие скиллы`.
4. **Inline path references resolve.** For every reference in the form `` `content/rules/<name>.md` ``, `` `content/agents/<name>.md` ``, `` `content/skills/<name>/SKILL.md` ``, `` `content/skills/<name>/docs/<doc>.md` ``, `` `<name>.md` `` (rule-style bare references), or `` `<name>` `` (skill alias) inside `AGENTS.md`, `README.md`, `AGENT-INSTALL.md`, files under `content/rules/`, `content/agents/`, `content/skills/`, the target file exists.
5. **Anchor convention.** Every section reference of the form `<file>.md §N` and `<file>.md §N → "Title"` resolves: `§N` corresponds to a `## N. ...` heading in the target file; `§N → "Title"` corresponds to a `### Title` (or any `###`/`####` whose stripped title matches) inside that `## N.` section. References that mix old styles (`§3 Queries` without quotes, `§3 "Queries"` without arrow, `§3.6 Queries`) are reported as **stale**.
6. **Markdown link integrity.** Standard `[text](path)` and `[text](path#anchor)` links resolve to existing files; anchors normalize (lowercase, spaces → `-`, punctuation stripped) and must match a heading in the target file.
7. **Script path integrity.** PowerShell examples in skill docs reference scripts that exist under the source skill folder or the active tool's installed skill folder. Examples must not point to a non-existent root-level `skills/` directory unless that directory is part of the installed layout.
8. **Adapter-layout consistency.** Paths mentioned in `README.md`, `AGENT-INSTALL.md`, `openspec/README.md`, command docs, and skill docs match `adapters/*.yaml`. Check Codex, Kilo Code, OpenCode, and `other` explicitly because their command / skill / MCP locations differ from the common `.cursor` / `.claude` layout.
9. **Policy drift.** Flag duplicate or conflicting rule wording for the same behavior, especially `.dev.env`, `infobasesettings.md` migration, MCP fallback order, and docs-fix vs BSL validation.
10. **Convention checks.** Topics declared as a single source of truth (`.dev.env`, `mcp-1c-tools` skill, `dev-standards-core.md §2 → "Forbidden Calls and Constructs"`, `dev-standards-architecture.md §3 → "Queries"`, `coding-standards.md` as the index of detail files, etc.) are claimed by **exactly one** file; the same topic is not declared authoritative in two different places. Flag any duplicate authoritative claims.

For each finding, report file and line. Group by severity: **FAIL** for broken paths, dangling index entries, orphan rules, missing scripts, and stale adapter-layout descriptions; **WARN** for stale anchor styles, missing skill mentions, policy drift, and conventional-style violations. Do not auto-fix — produce a fix list with concrete edits. External HTTP links are **SKIP** unless the user explicitly asks for live link checking.

This check is read-only. Implementation hint for the agent: a single PowerShell or shell pass with `Select-String`/`rg` over the relevant directories is sufficient — there is no need for a parser.

## Check 8. Final recommendation

Classify the project:

- **Ready** — all required checks are **OK** or non-blocking **SKIP**.
- **Usable with warnings** — at least one **WARN**, no **FAIL**.
- **Not ready** — at least one **FAIL**.

For **Not ready**, provide the shortest safe repair path, for example:

1. Run `install.ps1 init` or `/updaterules`.
2. Fill `.dev.env` critical fields.
3. Fix Markdown integrity findings from Check 7.
4. Generate or refresh `openspec/project.md`.
5. Start/reconnect MCP servers with `/checkmcp`.
6. Restart the AI client so MCP tools and rules are reloaded.
