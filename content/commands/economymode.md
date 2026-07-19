---
description: Toggle orchestrator economy mode via ORCHESTRATION in .dev.env; on enable, offers to configure per-tier subagent models and to set up the rtk output-compression proxy
argumentHint: "[on|off|status|models|rtk]"
---

# /economymode — orchestrator economy mode

Toggle the orchestrator economy mode for the **project** by writing the `ORCHESTRATION` key in `.dev.env`. Canonical behavior of the mode — the `orchestrator-economy.md` rule (installed copy; match by file name per the path convention in `AGENTS.md`). Load that rule before acting.

Parse the argument: empty or `on` — enable; `off` — disable; `status` — report the current state; `models` — (re)configure per-tier subagent models without changing the mode; `rtk` — set up (or uninstall) the rtk output-compression proxy without changing the mode.

The command edits **only** the `ORCHESTRATION` and (when the user confirms) `SUBAGENT_MODEL_CODING` / `SUBAGENT_MODEL_ANALYSIS` / `SUBAGENT_MODEL_LIGHT` lines in `.dev.env` — never other keys, never other files. Asking about models **inside this command** is allowed and expected: it is part of an explicit user-invoked configuration flow, not "task time" (the never-ask policy of `dev-standards-env.md` continues to apply to regular tasks).

## on (default)

1. Read `.dev.env`: `ORCHESTRATION` and the three `SUBAGENT_MODEL_*` keys.
2. **Model check.** Economy mode pays off only when subagents run on cheaper models than the parent; empty `SUBAGENT_MODEL_*` means subagents inherit the parent's (expensive) model and the savings shrink to context offloading only. This is client-independent — the installer renders `SUBAGENT_MODEL_*` into the active client's agent files (Cursor `.cursor/agents/`, Claude Code `.claude/agents/`, Codex `.codex/agents/*.toml`, OpenCode `.opencode/agent/`, Kilo `.kilo/agents/`), so the model choice must be made in **that client's own model-id format**.
   - If **all three** tier models are set — do not ask; show the current tier → model mapping in the confirmation.
   - If **any** tier model is empty — first determine the active AI client (from `.ai-rules.json` `activeTools`; if several are active, ask which one; if none is recorded, ask the user). Then ask **one** question offering that client's profile presets plus "custom slugs" and "keep inheriting". Tier meaning is the same everywhere: `coding` = strongest (writes production code / metadata), `analysis` = value/mid (plan / review / test / docs), `light` = cheapest & fastest (scouting / search / quick fixes). Suggested slugs per client (`coding` / `analysis` / `light`):

     | Client | Economy | Balanced (реком.) | Quality |
     |---|---|---|---|
     | Cursor | `glm-5.2-max` / `glm-5.2-max` / `composer-2.5-fast` | `gpt-5.6-sol-max` / `glm-5.2-max` / `composer-2.5-fast` | `claude-opus-4-8-thinking-high` / `gpt-5.6-sol-max` / `cursor-grok-4.5-high-fast` |
     | Claude Code | `sonnet` / `sonnet` / `haiku` | `opus` / `sonnet` / `haiku` | `opus` / `opus` / `sonnet` |
     | Codex | `gpt-5.6-terra` / `gpt-5.6-terra` / `gpt-5.6-luna` | `gpt-5.6-sol` / `gpt-5.6-terra` / `gpt-5.6-luna` | `gpt-5.6-sol` / `gpt-5.6-sol` / `gpt-5.6-terra` |

     For **OpenCode** there is no fixed catalog (models are provider-scoped), and the id has a **mandatory format**: `provider/model`, with an optional `#variant` for reasoning effort (e.g. `#high`). A bare slug like `glm-5.2-max` or `opus` will **not** resolve, and an invalid id can make OpenCode reject the whole config and fail to (re)start — so use the exact ids shown by OpenCode's `/models` (not provider display names). Same three tiers (`coding` / `analysis` / `light` = strong / value / cheap); examples by provider (verify the exact id against `/models` before writing):
       - Anthropic: `anthropic/claude-opus-4-5` / `anthropic/claude-sonnet-4-5` / `anthropic/claude-haiku-4-5`;
       - OpenAI: `openai/gpt-5.6-sol` / `openai/gpt-5.6-terra` / `openai/gpt-5.6-luna`;
       - other providers (GLM, Grok, …): the id from `/models`, e.g. `zhipuai/glm-4.6`, `xai/grok-4`.

     For **`other`** or any client not in the table: enter the model ids in that client's own format, following the same three tiers.

     The presets are guidance based on the 1C benchmark (<https://onec-llm-bench.lovable.app/>), not a hard rule — the user may always pick custom slugs.
   - **Keep inheriting** is a valid answer: do not write the models, and warn that subagents will run on the parent's model, so the saving is limited to context offloading.
   - Write the chosen values into `.dev.env`. Fill **empty** keys; overwrite already-filled keys only when the user explicitly said so (e.g. chose a profile and confirmed replacing existing values).
3. Set `ORCHESTRATION=economy`. If the key line exists — replace its value; if absent — append the line at the end of the file with a one-line comment `# Режим оркестрации: standard | economy (переключается командой /economymode)`.
   - If `.dev.env` does not exist: do **not** create a partial file (the installer's `Place-DevEnv` places the full template only when the file is missing — a stub would permanently block it). Enable the mode for the current session only, and tell the user to run `install.ps1 init` (or copy `.dev.env.example` to `.dev.env`) to make it persistent.
4. **Re-render note.** `SUBAGENT_MODEL_*` are consumed by the installer when rendering subagent files — editing `.dev.env` alone does not change the already-installed agent files. If models were written in step 2, offer to re-render right away: in the `1c-rules` source repo — `./install.ps1 update`; in an installed project — the `/updaterules` flow (clone/refresh the source into `$env:TEMP`, then `install.ps1 update -Source <clone> -AssumeYes`). In Cursor the user may instead set the model per subagent in the UI. **OpenCode** (and Kilo / Codex) read agent definitions only at startup — after the re-render, tell the user to restart the client for the new subagent models to take effect. `ORCHESTRATION` itself needs **no** re-render — rules read it directly from `.dev.env`.
5. **Optional token-saving companion — `rtk`.** Economy mode saves orchestrator tokens by delegating; `rtk` (<https://github.com/rtk-ai/rtk>) is a complementary lever — a CLI proxy that compresses the output of **shell** commands (git, tests, docker, build / lint, `ls` / `grep` / `cat`) by 60–90% before it reaches the model. Ask the user whether to set it up now (skip is always valid). If yes, follow the `## rtk` section below. Note up front the honest limitation so expectations are correct: the rtk hook rewrites only **shell / Bash** tool calls — built-in `Read` / `Grep` / `Glob` and MCP tools bypass it, so the savings apply to steps that shell out (git, platform / `ibcmd` commands, tests, docker, `/deploy-and-test`), not to pure built-in-tool reads.
6. Load the `orchestrator-economy.md` rule and apply it immediately — from this message on, in this session, without any restart.
7. Confirm to the user in 3–4 lines, in Russian:
   - режим экономии включён и записан в `.dev.env` (`ORCHESTRATION=economy`) — действует для проекта, включая новые чаты;
   - карта ярусов: `coding` / `analysis` / `light` → фактические модели (или «наследование от родителя» с предупреждением);
   - если настроили `rtk` — вывод shell-команд теперь сжимается (после перезапуска клиента);
   - решения, спеки и верификация остаются за головным агентом; выключение — `/economymode off`.

## off

1. In the project `.dev.env`: set `ORCHESTRATION=standard` (same edit rules as above; if `.dev.env` or the key is absent, there is nothing to persist — the mode is already off by default). Do not touch `SUBAGENT_MODEL_*` — configured models stay.
2. Stop applying the mode immediately in this session and confirm: режим экономии выключен (`ORCHESTRATION=standard`), действует обычная политика делегирования из `subagents.md` (делегировать крупное, мелкое исполнять напрямую).

## status

Read `.dev.env` and report, without editing anything:

- `ORCHESTRATION` (missing file / missing key / empty / invalid value = `standard`) and what it means;
- the tier → model mapping from `SUBAGENT_MODEL_*` (empty = «наследование от родителя»);
- whether `rtk` is installed (`rtk --version`) and, if not, that `/economymode rtk` can set it up.

## models

Run the model question from step 2 of `on` (same options, same write rules, same re-render note) without changing `ORCHESTRATION`. Use when the user wants to switch profiles or slugs later.

## rtk

Set up (or remove) the `rtk` output-compression proxy (<https://github.com/rtk-ai/rtk>) without changing `ORCHESTRATION`. `rtk` is a **third-party, user-global** tool: it installs a binary and per-client hooks in the user's home config, **not** in the project, and it is **not** recorded in `.dev.env`. It works regardless of the economy mode's on/off state.

**Discipline:** installing a binary and wiring global hooks are system-changing actions — always show the exact commands and run them **only after the user confirms** (per `AGENT-INSTALL.md → Confirm before destructive actions`); never install silently. Prefer running the commands in the project's shell so the user sees the output.

1. **Check** whether it is already present: `rtk --version` (`rtk 0.28.2`+). If present, skip install and go to wiring.
2. **Install the binary** (once per machine):
   - **Windows** (this project's default shell): download `rtk-x86_64-pc-windows-msvc.zip` from the releases page, place `rtk.exe` on `PATH` (e.g. `C:\Users\<user>\.local\bin`), and keep ripgrep on `PATH` (`winget install BurntSushi.ripgrep.MSVC`) — some filters shell out to `rg`. The auto-rewrite hook runs as a native binary (v0.37.2+), no Unix shell needed.
   - **macOS / Linux**: `brew install rtk`, or `curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh`, or `cargo install --git https://github.com/rtk-ai/rtk`.
3. **Wire it into the active AI client** (detect the client as in step 2 of `on`):
   - Claude Code — `rtk init -g`;
   - Cursor — `rtk init -g --agent cursor`;
   - Codex — `rtk init -g --codex`;
   - OpenCode — `rtk init -g --opencode`;
   - Kilo Code — `rtk init --agent kilocode` (project-scoped, no `-g`).
   Then **restart** the AI client — hooks / plugins are read at startup.
4. **Verify:** `rtk init --show` (integration) and `rtk gain` (savings stats).
5. **Uninstall** on request: `rtk init -g --uninstall` (removes the hook / integration), then `brew uninstall rtk` / `cargo uninstall rtk` for the binary.

Telemetry is **off by default** (opt-in via `rtk init` / `rtk telemetry enable`); mention it only if the user asks. Repeat the honest limitation from step 5 of `on`: only shell / Bash calls are rewritten; built-in `Read` / `Grep` / `Glob` and MCP tools are not.

## Constraints (always)

The mode never overrides stricter rules: quick-fix / docs-fix tasks stay with the parent, `1c-code-reviewer` runs only on an explicit user request, UI testing stays gated by `UI_TESTING`, validator chains and the verification gate are unchanged, model-tier routing stays authoritative. Details — `orchestrator-economy.md → Consistency with the existing orchestration rules`.
