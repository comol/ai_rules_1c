---
description: Toggle the caveman communication style — set CAVEMAN (on|auto|off) in .dev.env for the whole project; on|off|auto persist, lite|full|ultra switch the session level
argumentHint: "[on|off|auto|status|lite|full|ultra]"
---

# /caveman — communication style toggle

Control the terse `caveman` answer style. Canonical behaviour of the style and its modes — the `caveman` skill (`content/skills/caveman/SKILL.md`) and `content/rules/dev-standards-env.md → "CAVEMAN — caveman auto-activation"` (installed copies; match by file name per the path convention in `AGENTS.md`). Load the skill before acting.

Two scopes, do not mix them:

- **Persistent (project-wide, edits `.dev.env`):** `on` / `off` / `auto` write the `CAVEMAN` key and take effect in every chat, including new ones.
- **Session-only (no file change):** `lite` / `full` / `ultra` switch the verbosity level for this chat; the natural-language phrases "caveman please" (force on) and "stop caveman" / "normal mode" / "обычный режим" (force off) force the state until session end. A forced session state always overrides the `.dev.env` value.

Parse the argument: `on` (or empty) → set `on`; `off` → set `off`; `auto` → set `auto`; `status` → report without editing; `lite` / `full` / `ultra` → switch the session level only. The command edits **only** the `CAVEMAN` line in `.dev.env` — never other keys, never other files.

## What the values mean (summary — canon in the skill)

- `on` (default) — caveman is active for **all** tasks (development and analysis / review / documentation alike); only the skill's safety switches apply (code, error text, destructive / security / ordered blocks stay in normal grammar).
- `auto` — task-type auto-classification: on for development (writing / editing / refactoring code, debugging, deploy, shell), off for analysis / review / documentation.
- `off` — no automatic activation on any task; caveman turns on only via an explicit session force ("caveman please").

## on (default) / off / auto

1. Read `.dev.env`: the `CAVEMAN` key.
2. Set `CAVEMAN=<value>` (`on` | `off` | `auto`). If the key line exists — replace its value; if absent — append the line at the end of the file with a one-line comment `# Стиль общения caveman: on | auto | off (переключается командой /caveman)`.
3. If `.dev.env` does not exist: do **not** create a partial file (the installer's `Place-DevEnv` places the full template only when the file is missing — a stub would permanently block it). Apply the mode for the current session only, and tell the user to run `install.ps1 init` (or copy `.dev.env.example` to `.dev.env`) to make it persistent.
4. **No re-render needed.** `CAVEMAN` is read directly from `.dev.env` by the skill at task time — editing the file is enough, no `install.ps1 update` and no client restart.
5. Apply the new mode immediately — from this message on, in this session.
6. Confirm to the user in 2–3 lines, in Russian:
   - что записано в `.dev.env` (`CAVEMAN=<value>`) и что действует для проекта, включая новые чаты;
   - что это значит (`on` — краткий стиль на всех задачах; `auto` — только на разработке; `off` — сам не включается);
   - как переключить обратно (`/caveman on|auto|off`), и что разово можно форсить фразами «caveman please» / «stop caveman».

## lite / full / ultra

Switch the **session** verbosity level only (no `.dev.env` write): `lite` — drop filler / hedging; `full` (default) — classic caveman; `ultra` — telegraphic. Level holds until session end or another switch. Confirm the new level in one line.

## status

Read `.dev.env` and report, without editing anything:

- `CAVEMAN` (missing file / missing key / empty / invalid value = `on`) and what it means;
- the current session state if a force command or level switch was issued in this chat.

## Constraints (always)

The toggle changes only presentation. It never affects the five-step development procedure, model selection, verification depth, tool-calling rules, or the mandatory report structure from `AGENTS.md`. The skill's safety switches (code / error text verbatim, destructive / security / ordered blocks in normal grammar) hold in every mode, including `on`.
