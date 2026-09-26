---
description: Install rtk (third-party shell-output compression proxy) and wire it into the active AI client; uninstall on request
userOnly: true
---

# /install-rtk — install the rtk output-compression proxy

Installs [rtk](https://github.com/rtk-ai/rtk): a CLI proxy that compresses the output of **shell** commands (git, docker, build / lint, `ls` / `grep` / `cat`) by 60–90 % before it reaches the model. A complementary lever to `/economymode`: economy mode saves orchestrator tokens by delegating, `rtk` saves them on every shell call. It works regardless of the `ORCHESTRATION` value.

`rtk` is a **third-party, user-global** tool: it installs a binary and per-client hooks in the user's home config, **not** in the project, and it is **not** recorded in `.dev.env`. Shell on Windows — `powershell-windows` skill.

**Honest limitation — state it up front.** The rtk hook rewrites only **shell / Bash** tool calls. Built-in `Read` / `Grep` / `Glob` and MCP tools bypass it, so the savings apply to steps that shell out (git, platform / `ibcmd` commands, tests, docker, `/deploy-and-test`), not to pure built-in-tool reads.

**Discipline.** Installing a binary and wiring global hooks are system-changing actions — always show the exact commands and run them **only after the user confirms** (`AGENT-INSTALL.md → Confirm before destructive actions`); never install silently. Prefer running the commands in the project's shell so the user sees the output.

## Steps

### 1. Check for an existing install

`rtk --version` (`rtk 0.28.2`+). If present, skip Step 2 and go to wiring.

### 2. Install the binary (once per machine)

- **Windows** (this project's default shell): download `rtk-x86_64-pc-windows-msvc.zip` from the releases page (<https://github.com/rtk-ai/rtk/releases>), place `rtk.exe` on `PATH` (e.g. `C:\Users\<user>\.local\bin`), and keep ripgrep on `PATH` (`winget install BurntSushi.ripgrep.MSVC`) — some filters shell out to `rg`. The auto-rewrite hook runs as a native binary (v0.37.2+), no Unix shell needed.
- **macOS / Linux**: `brew install rtk`, or `curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh`, or `cargo install --git https://github.com/rtk-ai/rtk`.

### 3. Wire it into the active AI client

Detect the client from `.ai-rules.json` `activeTools` (several active → ask which one; none recorded → ask the user):

- Claude Code — `rtk init -g`;
- Cursor — `rtk init -g --agent cursor`;
- Codex — `rtk init -g --codex`;
- OpenCode — `rtk init -g --opencode`;
- Kilo Code — `rtk init --agent kilocode` (project-scoped, no `-g`).

Then ask the user to **restart** the AI client — hooks / plugins are read at startup.

### 4. Verify

`rtk init --show` (integration) and `rtk gain` (savings stats).

### 5. Uninstall (on request)

`rtk init -g --uninstall` removes the hook / integration; then `brew uninstall rtk` / `cargo uninstall rtk` (or delete `rtk.exe` on Windows) for the binary.

## Notes

- Telemetry is **off by default** (opt-in via `rtk init` / `rtk telemetry enable`); mention it only if the user asks.
- Do not touch `.dev.env`, MCP configs, or project files — `rtk` lives in the user's home config only.
- Do not run any other installer from here; the tool menu is `/installtools`.

## Final report (Russian, short)

- `rtk` version and where the binary lives;
- which client was wired (`rtk init --show`) and that a client restart is needed;
- the limitation: сжимается только вывод shell-команд; встроенные `Read` / `Grep` / `Glob` и MCP-инструменты не затрагиваются.
