---
description: Toggle orchestrator economy mode via ORCHESTRATION in .dev.env; on enable, offers to configure per-tier subagent models and to set up the rtk output-compression proxy
userOnly: true
argumentHint: "[on|off|status|models|rtk]"
---

# /economymode — orchestrator economy mode

Toggle the orchestrator economy mode for the **project** by writing the `ORCHESTRATION` key in `.dev.env`. Canonical behavior of the mode — the `orchestrator-economy.md` rule (installed copy; match by file name per the path convention in `AGENTS.md`). Load that rule before acting.

Parameters, classes and defaults — `content/rules/dev-standards-env.md §1`; Defaulted keys are never asked for. Asking about models **inside this command** is allowed and expected: it is part of an explicit user-invoked configuration flow, not "task time".

Parse the argument: empty or `on` — enable; `off` — disable; `status` — report the current state; `models` — (re)configure per-tier subagent models without changing the mode; `rtk` — run `/install-rtk` (`content/commands/install-rtk.md`) without changing the mode.

The command edits **only** the `ORCHESTRATION` and (when the user confirms) `SUBAGENT_MODEL_CODING` / `SUBAGENT_MODEL_ANALYSIS` / `SUBAGENT_MODEL_LIGHT` lines in `.dev.env` — never other keys, never other files. Rewrite the `KEY=` line in place, or append `KEY=value` at the end; if `.dev.env` is missing, run the installer (`install.ps1 init`) instead of creating a partial file — until then apply the mode for the current session only.

## on (default)

1. Read `.dev.env`: `ORCHESTRATION` and the three `SUBAGENT_MODEL_*` keys.
2. **Model check.** Economy mode pays off only when subagents run on cheaper models than the parent; with empty `SUBAGENT_MODEL_*` subagents inherit the parent's model and the saving shrinks to context offloading. The installer renders `SUBAGENT_MODEL_*` into the active client's agent files (Cursor `.cursor/agents/`, Claude Code `.claude/agents/`, Codex `.codex/agents/*.toml`, OpenCode `.opencode/agent/`, Kilo `.kilo/agents/`), so each value must be a model id **in that client's own format**.
   - If **all three** tier models are set — do not ask; show the current tier → model mapping in the confirmation.
   - If **any** tier model is empty — determine the active AI client (from `.ai-rules.json` `activeTools`; several active → ask which one; none recorded → ask the user). Then ask **one** question: a model per tier, plus "keep inheriting". Tier meaning is the same everywhere: `coding` = strongest (writes production code / metadata), `analysis` = value / mid (plan / review / test / docs), `light` = cheapest and fastest (scouting / search / quick fixes). There is no canonical slug catalog in the ruleset: the canonical ids are whatever the client accepts — take them from the client's own model list (e.g. Cursor's model picker, OpenCode `/models`) or from the ids the user gives, and verify an id against that list before writing it. **OpenCode** ids have a mandatory `provider/model` format (optional `#variant` for reasoning effort); a bare slug does not resolve, and an invalid id can make OpenCode reject the whole config and fail to start. Which model fits which tier — the 1C benchmark (<https://onec-llm-bench.lovable.app/>) is the reference; the user may always pick their own.
   - **Keep inheriting** is a valid answer: do not write the models, and warn that subagents will run on the parent's model, so the saving is limited to context offloading.
   - Write the chosen values into `.dev.env`. Fill **empty** keys; overwrite already-filled keys only when the user explicitly said so.
3. Set `ORCHESTRATION=economy`.
4. **Re-render note.** `SUBAGENT_MODEL_*` are consumed by the installer when rendering subagent files — editing `.dev.env` alone does not change the already-installed agent files. If models were written in step 2, offer to re-render right away: in the `1c-rules` source repo — `./install.ps1 update`; in an installed project — the `/updaterules` flow. In Cursor the user may instead set the model per subagent in the UI. **OpenCode** (and Kilo / Codex) read agent definitions only at startup — after the re-render, tell the user to restart the client for the new subagent models to take effect. `ORCHESTRATION` itself needs **no** re-render — rules read it directly from `.dev.env`.
5. **Optional companion — `rtk`.** Economy mode saves orchestrator tokens by delegating; `rtk` compresses the output of shell commands before it reaches the model. Ask once whether to set it up now (skip is always valid); on yes run `/install-rtk` (`content/commands/install-rtk.md`), which also states its limits.
6. Load the `orchestrator-economy.md` rule and apply it immediately — from this message on, in this session, without any restart.
7. Confirm to the user in 3–4 lines, in Russian:
   - режим экономии включён и записан в `.dev.env` (`ORCHESTRATION=economy`) — действует для проекта, включая новые чаты;
   - карта ярусов: `coding` / `analysis` / `light` → фактические модели (или «наследование от родителя» с предупреждением);
   - если настроили `rtk` — вывод shell-команд теперь сжимается (после перезапуска клиента);
   - решения, спеки и верификация остаются за головным агентом; выключение — `/economymode off`.

## off

1. In the project `.dev.env`: set `ORCHESTRATION=standard` (same edit rule as above; if `.dev.env` is missing there is nothing to persist). Do not touch `SUBAGENT_MODEL_*` — configured models stay.
2. Stop applying the mode immediately in this session and confirm: режим экономии выключен (`ORCHESTRATION=standard`), действует обычная политика делегирования из `subagents.md` (делегировать крупное, мелкое исполнять напрямую).

## status

Read `.dev.env` and report, without editing anything:

- the `ORCHESTRATION` value (or the default when the file / key is absent or the value is invalid) and what it means;
- the tier → model mapping from `SUBAGENT_MODEL_*` (or «наследование от родителя»);
- whether `rtk` is installed (`rtk --version`) and, if not, that `/economymode rtk` (= `/install-rtk`) can set it up.

## models

Run the model question from step 2 of `on` (same options, same write rules, same re-render note) without changing `ORCHESTRATION`. Use when the user wants to switch models later.

## rtk

Run `/install-rtk` (`content/commands/install-rtk.md`) — install, wire into the active client, verify, or uninstall the `rtk` output-compression proxy — without changing `ORCHESTRATION`. `rtk` is a third-party, user-global tool: it is not recorded in `.dev.env` and works regardless of the economy mode.

## Constraints (always)

The mode never overrides stricter rules: quick-fix / docs-fix tasks stay with the parent, `1c-code-reviewer` runs only on an explicit user request, UI testing stays gated by `UI_TESTING`, validator chains and the verification gate are unchanged, model-tier routing stays authoritative. Details — `orchestrator-economy.md → Consistency with the existing orchestration rules`.
