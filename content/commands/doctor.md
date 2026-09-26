---
description: Diagnose whether 1c-rules is installed, connected, configured, and usable by the current agent
userOnly: true
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
3. Check that `USER-RULES.md` and `memory.md` exist at the project root. Check `LLM-RULES.md` too, but report a missing `LLM-RULES.md` as **WARN**, not FAIL — older installs predate it; it is placed by `install.ps1 update` or created by the first `/evolve` write.
4. If `.ai-rules.json` exists, read it and verify:
   - `activeTools` contains the current tool, or explain why the current tool is still supported through `other`;
   - managed files listed in the manifest still exist;
   - the canonical rules directory referenced by the manifest exists.
5. If `.ai-rules.json` is missing:
   - in an installed project, report **FAIL** and recommend `install.ps1 init`;
   - in the source repository of `1c-rules`, report **WARN** and continue with source-layout checks.
6. Verify that the current tool has the files it can actually load:
   - Cursor: `.cursor/rules/`, `.cursor/commands/`, `.cursor/mcp.json` when installed;
   - Claude Code: `.claude/rules-1c/` (on-demand rules referenced through `AGENTS.md` — deliberately **not** `.claude/rules/`, which Claude Code v2.0.64+ auto-loads in full at session start), `.claude/agents/`, `.claude/commands/`, MCP config when installed; managed rule files left in `.claude/rules/` from older installs are **legacy** and the `update` flow removes them (user-authored files there are kept);
   - Codex: `.codex/skills/`, `.codex/config.toml` when installed;
   - OpenCode: `.opencode/command/`, `.opencode/agent/` (also accept `.opencode/agents/` if present), `.opencode/rules/`, and `opencode.json` at the **project root** (top-level `mcp` key) when installed — MCP lives in the root `opencode.json`, **not** `.opencode/opencode.json` (OpenCode does not read a config file under `.opencode/`); a leftover `.opencode/opencode.json` from older installs is **legacy** and the `update` flow removes it;
   - **OpenCode agent frontmatter hard gate** (when `.opencode/agent/` or `.opencode/agents/` exists): every `*.md` agent file must **not** have a `tools` **array** in its YAML frontmatter (`tools: ["Read", …]`). OpenCode validates `tools` as object | undefined; a Cursor-style array makes it reject the whole config and refuse to start (`Configuration is invalid … Expected object | undefined, got […] tools`). Correct installed shape uses a `permission` object (`read`/`edit`/`grep`/`glob`/`bash`: `allow`|`deny`) and `mode: subagent`|`primary` — produced by `adapters/opencode.yaml → toolsToPermission`. Any file still carrying a `tools` array → **FAIL**. Repair: `install.ps1 update -Source <clone> -AssumeYes -ForcePaths .opencode/agent/*` (or re-apply the adapter transform on the agent channel). Do **not** confuse source `content/agents/*.md` (arrays are correct there) with installed `.opencode/agent/*.md`. Quick check:

     ```powershell
     Get-ChildItem .opencode\agent, .opencode\agents -Filter *.md -File -ErrorAction SilentlyContinue |
       ForEach-Object {
         if ((Get-Content $_.FullName -Raw) -match '(?ms)\A---\r?\n.*?^tools:\s*\[') { "FAIL: $($_.Name)" }
       }
     ```
   - **Agent tool vocabulary hard gate** (when `.claude/agents/`, `.kimi-code/agents/`, `.qwen/agents/`, `.cursor/agents/`, `.commandcode/agents/`, `.zcode/agents/` or `.mimocode/agents/` exists): no `*.md` agent file there may name an abstract tool (`Shell`, `MCP`) in its `tools` or `disallowedTools` frontmatter. Claude Code / Kimi / Qwen match tool names literally, so an abstract name grants nothing: the subagent launches with no shell and no MCP server at all (`1c-metadata-manager` → `BLOCKED - toolchain cannot be executed in this session`; `1c-explorer` reduced to `Grep` / `Glob`). Cursor ignores the field entirely, so there the array silently leaves the read-only agents unrestricted. Correct installed shape uses native restrictions: a `disallowedTools` string for Claude Code / Kimi / Qwen / ZCode / Command Code, `readonly: true` for Cursor, or `permission.edit: deny` / `permission.bash: deny` for MiMo Code. Command Code also requires `tools: "*"`; the other listed adapters omit `tools`. Apply the adapter's `toolsToDenylist` / `toolsToFlag` / `toolsToPermission` transform. Any file still naming `Shell` / `MCP` → **FAIL**; so is a read-only agent (`explorer`, `code-reviewer`, `arch-reviewer`) that carries none of the applicable restriction fields, since someone deleted the `tools` line by hand. Repair: `install.ps1 update -Source <clone> -AssumeYes -ForcePaths .claude/agents/*` (substitute the affected directory). Do **not** confuse source `content/agents/*.md` (the abstract vocabulary is correct there) with the installed copies. Quick check:

     ```powershell
     Get-ChildItem .claude\agents, .kimi-code\agents, .qwen\agents, .cursor\agents, .commandcode\agents, .zcode\agents, .mimocode\agents -Filter *.md -File -ErrorAction SilentlyContinue |
       ForEach-Object {
         if ((Get-Content $_.FullName -Raw) -match '(?m)^(tools|disallowedTools):.*\b(Shell|MCP)\b') { "FAIL: $($_.Name)" }
       }
     ```
   - Kilo Code: `.kilo/rules-1c/` (on-demand rules referenced through `AGENTS.md`), `.kilo/commands/`, `.kilo/agents/`, `.kilo/skills/`, `.kilo/kilo.json` (top-level `mcp` key) when installed; a leftover `.kilocode/mcp.json` from older installs is **legacy** (why — `/installmcp` → *Step 7. Per-client MCP config*) and the `update` flow removes it;
   - other: `.ai-agent/rules/`, `.ai-agent/agents/`, `.ai-agent/commands/`, `.ai-agent/skills/`, `.ai-agent/mcp.json`.

Pass criterion: the root always-on files exist, and either the installed tool layout is present or the repository is clearly the `1c-rules` source repository being edited directly.

## Check 2. Ruleset file integrity — mechanical (`tools/validate-rules.ps1`)

Frontmatter, `content/...` path references, Markdown links, `<file>.md → Section` anchors, routed-standards heading parity, and the `AGENTS.md` always-on byte budget are owned by the validator script — do **not** re-derive them by hand. In the `1c-rules` source repository run:

```powershell
powershell -NoProfile -File tools\validate-rules.ps1
```

and report its output: every `ERRORS` line → **FAIL**, every `WARNINGS` line → **WARN**, with the file and line exactly as printed; `OK` → **OK**. In an installed project the script is not shipped — report **SKIP**; file presence there is covered by the manifest check in Check 1.

## Check 3. `.dev.env` existence and completeness

1. Check that `.dev.env` exists at the project root.
2. If missing, report **FAIL** for operational commands and recommend creating it from `.dev.env.example` or running `install.ps1 init`.
3. If present, verify that critical fields are non-empty:
   - `PLATFORM_PATH`;
   - `INFOBASE_PATH`;
   - `EXPORT_PATH` when the repository root is not the configuration source directory;
   - `PLATFORM_VERSION` when platform-version-specific docs or checks are needed.

   Advisory and Defaulted keys are never critical — report an empty one as "uses default" (naming the default from `dev-standards-env.md §1`), not as a missing value.
4. Verify that `PLATFORM_PATH` contains `bin\1cv8.exe`.
5. For every key with an enumerated value set (`INFOBASE_KIND`, `UI_TESTING`, `VERIFICATION_DEPTH`, `CAVEMAN`, `DEBUG_FAST_PATH`, `ORCHESTRATION`, `SUPPORT_GUARD`), a non-empty value outside the set listed in `dev-standards-env.md §1` is **WARN** — the default applies.
6. `AGENT_MODEL`: a recognised non-empty value must have its rule file (`model-<slug>.md`, or `.mdc` on Cursor) in the rules directory — missing = **FAIL** (the install is incomplete — run `/updaterules`). An unrecognised value is **WARN** with the fix `/rulesmodel <модель>`. When the value names a model different from the one you are running, report **WARN**, say which profile you actually apply per `model-adaptation.md §2`, and suggest `/rulesmodel auto`. Empty is **OK** ("uses default"), never a WARN.
7. **Optional UI tooling (non-blocking).** When `UI_TESTING=auto` or the user is about to run web UI tests: if `agent-browser` is not on `PATH` and no `agent-browser` MCP entry is in the active client config — report **WARN** and suggest `/install-agent-browser` (token-efficient default per `ui-testing-tools.md`). Absence of `windows-mcp` is not a WARN (desktop CV is last resort only).
8. **EDT flag (non-blocking).** Report `USE_EDT` as `true` / `false` / `unknown` (missing or invalid). When `true`: check that `edt-workflow.md` exists in the rules directory (missing = **FAIL**, the install is incomplete — run `/updaterules`), and report whether EDT-MCP tools are exposed in this session (not exposed = **WARN** with the fix `/install-edt-mcp`; a closed EDT is a valid reason, not a broken install). Also report a **WARN** when `USE_EDT=true` but the working tree looks like a Designer XML dump only, or when it holds an EDT workspace (`.project`, `DT-INF/`, `src/Configuration.mdo`) while `USE_EDT` is `false` / `unknown` — the flag and the tree disagree, and the fix is one line in `.dev.env`. When `USE_EDT=false` and no EDT workspace is present, say nothing about EDT.
9. **Support channel (non-blocking).** Report whether `SUPPORT_KEY` and `SUPPORT_EMAIL` are set — never their values. Both set = **OK**. Both empty = **OK** ("канал поддержки не настроен"), not a WARN: the channel is optional and blocks no development task. Exactly one of the two set = **WARN**, because `/support` needs both — the fix is one line in `.dev.env` (`SUPPORT_KEY` — раздел 6 `config.env` дистрибутива MCP, `SUPPORT_EMAIL` — рабочий e-mail пользователя). A non-empty `SUPPORT_API_URL` that is not an `https://` URL is a **WARN**; empty is **OK** (default endpoint).
10. Never print `IB_PASSWORD`, `SUPPORT_KEY`, tokens, license keys, or full connection strings. Report only whether they are set.

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

1. **Current session tools** — verify that the expected tools of every configured server are visible in the current agent tool schema. The tool-name → server map and the `1C-docs-mcp` partial-exposure rule (`docsearch` present, `standards` missing = a **WARN** of its own) are owned by `/checkmcp` → *Step 2* (`content/commands/checkmcp.md`) — apply them as written there.
2. **Transport fallback** — when tools are missing but MCP config lists the server, run the `/checkmcp` algorithm: HTTP endpoint check, Docker state, and exact next action.

Pass criterion: required MCP tools for the expected 1C workflow are visible in the current session. HTTP-only availability is **WARN** because the agent still cannot call the tools until the client reconnects.

When **no** 1C MCP tools are visible and `.dev.env` `SUPPORT_KEY` is empty and `integrations.mcp.mode` is not `external`, add the same MCP-effectiveness reminder as after install / `/updaterules` / `/checkupdates` (https://vibecoding1c.ru/mcp_server). This is **WARN**, not FAIL — the ruleset has graceful fallbacks. If the key or an external install is present but tools are still missing, report **WARN** with `/installmcp` or a client restart, without the purchase page.

## Check 6. Active rules suitability

Evaluate whether the installed rules match the current repository and current agent:

1. If the repository contains 1C source files or metadata XML, confirm the 1C ruleset is appropriate.
2. If the repository is only the `1c-rules` source repository, report that BSL validators are not applicable to docs-only edits unless BSL examples are changed.
3. Confirm that `AGENTS.md` points to source or installed on-demand rules that the current agent can read.
4. Confirm that command names in `content/commands/` are available in the active tool's command location after installation.
5. Confirm that the `caveman` behaviour in force matches the `.dev.env` `CAVEMAN` value (semantics — `dev-standards-env.md → "CAVEMAN — caveman auto-activation"`).
6. Confirm the active-model layer: report which profile is in force (`AGENT_MODEL` from `.dev.env`, or none) and whether it matches the model you are running. State in one line the 2–3 behaviour deltas currently applied. If no profile is set and the model you run has one (`opus5` / `sonnet5` / `fable5` / `gpt56` / `gpt6`), report **WARN** — not FAIL — and suggest `/rulesmodel auto`; the base ruleset is fully functional without it. Never report a profile as weakening a gate: if a profile file appears to relax a hard gate, that is a **FAIL** on the ruleset, per `model-adaptation.md §4`.

Pass criterion: the current agent has the always-on rules, can reach on-demand rules or their source copies, and the rule triggers match the current task type.

## Check 7. Index completeness and policy drift (not covered by the script)

Source repository only (installed project → **SKIP**). Read-only; a single `Select-String` / `rg` pass over `AGENTS.md`, `content/` and `adapters/` is enough. Everything mechanical (paths, links, anchors, frontmatter, routed standards, the `AGENTS.md` budget) is Check 2 — do not repeat it here.

1. **Index completeness.** Every `content/rules/*.md` is reachable from `AGENTS.md` — named there directly, or through a rule it names (router companions, domain standards routed by `coding-standards.md`, `model-<slug>` profiles); an unreachable file is an orphan — **WARN**; every `content/agents/*.md` is listed in `content/rules/subagents.md → Subagent catalog` and the subagent count claimed in `AGENTS.md` / `subagents.md` matches the file count (**FAIL**); every `content/skills/<name>/SKILL.md` is mentioned in `AGENTS.md` or `README.md` (**WARN**).
2. **Script path integrity.** PowerShell examples in skill docs reference scripts that exist under the skill folder or the active tool's installed skill folder (**FAIL**).
3. **Adapter-layout consistency.** Paths in `README.md`, `AGENT-INSTALL.md`, `openspec/README.md`, command docs and skill docs match `adapters/*.yaml` — check Codex, Kilo Code, OpenCode, Qwen, Command Code, Cline, ZCode, MiMo Code, Pi and `other` explicitly (**FAIL**).
4. **Policy drift / single owner.** A topic declared authoritative in two places is **WARN** with both locations — `.dev.env` parameter semantics (owner `dev-standards-env.md §1`), per-client MCP config placement (owner `/installmcp` → *Step 7*), MCP fallback order, docs-fix vs BSL validation. A routed owner (`help-mcp-router` marker) counts as the single owner. Also confirm no rule instructs retrieval of the standards through `docsearch` / `docinfo` or with a `corpus` argument (`content/rules/help-corpus-retrieval.md`).
5. **Language policy.** Files governed by the source language policy are written in English, except 1C identifiers, Russian platform messages, BSL examples, metadata names, and user-facing Russian strings explicitly quoted as data (**WARN**).

For each finding, report file and line. Do not auto-fix — produce a fix list with concrete edits. External HTTP links are **SKIP** unless the user explicitly asks for live link checking.

## Check 8. Final recommendation

Classify the project:

- **Ready** — all required checks are **OK** or non-blocking **SKIP**.
- **Usable with warnings** — at least one **WARN**, no **FAIL**.
- **Not ready** — at least one **FAIL**.

For **Not ready**, provide the shortest safe repair path, for example:

1. Run `install.ps1 init` or `/updaterules`.
2. If OpenCode agent frontmatter gate failed — re-run `install.ps1 update -Source <clone> -AssumeYes -ForcePaths .opencode/agent/*` (do not copy `content/agents/*.md` verbatim).
3. If the agent tool vocabulary gate failed — re-run `install.ps1 update -Source <clone> -AssumeYes -ForcePaths .claude/agents/*` (substitute the affected agents directory). Deleting the `tools` line is not a repair.
4. Fill `.dev.env` critical fields.
5. Fix the validator findings (Check 2) and the index / drift findings (Check 7).
6. Generate or refresh `openspec/project.md`.
7. Start/reconnect MCP servers with `/checkmcp`.
8. Restart the AI client so MCP tools and rules are reloaded.
