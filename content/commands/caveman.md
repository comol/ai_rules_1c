---
description: Toggle the caveman communication style — set CAVEMAN (on|auto|off) in .dev.env for the whole project; on|off|auto persist, lite|full|ultra switch the session level
userOnly: true
argumentHint: "[on|off|auto|status|lite|full|ultra]"
---

# /caveman — communication style toggle

Control the terse `caveman` answer style. Canonical behaviour of the style and its modes — the `caveman` skill (`content/skills/caveman/SKILL.md`); the `CAVEMAN` key, its values and default — `content/rules/dev-standards-env.md → "CAVEMAN — caveman auto-activation"` (installed copies; match by file name per the path convention in `AGENTS.md`). Load the skill before acting.

Parameters, classes and defaults — `content/rules/dev-standards-env.md §1`; Defaulted keys are never asked for.

Two scopes, do not mix them:

- **Persistent (project-wide, edits `.dev.env`):** `on` / `off` / `auto` write the `CAVEMAN` key and take effect in every chat, including new ones.
- **Session-only (no file change):** `lite` / `full` / `ultra` switch the verbosity level for this chat; the natural-language phrases "caveman please" (force on) and "stop caveman" / "normal mode" / "обычный режим" (force off) force the state until session end. A negated mention ("не надо caveman", "без caveman") means **off**, never on. A forced session state always overrides the `.dev.env` value.

Parse the argument: `on` (or empty) → set `on`; `off` → set `off`; `auto` → set `auto`; `status` → report without editing; `lite` / `full` / `ultra` → switch the session level only. Matching is case-insensitive and tolerates trailing punctuation (`/caveman Ultra.`); an unrecognised argument is reported back, never guessed. The command edits **only** the `CAVEMAN` line in `.dev.env` — never other keys, never other files. Rewrite the `CAVEMAN=` line in place, or append `CAVEMAN=<value>` at the end; if `.dev.env` is missing, run the installer (`install.ps1 init`) instead of creating a partial file — until then apply the mode for the current session only.

## on (default) / off / auto

1. Read `.dev.env`: the `CAVEMAN` key.
2. Set `CAVEMAN=<value>` (`on` | `off` | `auto`).
3. **No re-render needed.** `CAVEMAN` is read directly from `.dev.env` by the skill at task time — editing the file is enough, no `install.ps1 update` and no client restart.
4. Apply the new mode immediately — from this message on, in this session.
5. Confirm to the user in 2–3 lines, in Russian:
   - что записано в `.dev.env` (`CAVEMAN=<value>`) и что действует для проекта, включая новые чаты;
   - что означает записанное значение — одной строкой по канону скилла;
   - как переключить обратно (`/caveman on|auto|off`), и что разово можно форсить фразами «caveman please» / «stop caveman».

## lite / full / ultra

Switch the **session** verbosity level only (no `.dev.env` write): `lite` — drop filler / hedging; `full` (default) — classic caveman; `ultra` — telegraphic. Level holds until session end or another switch. Confirm the new level in one line.

## status

Read `.dev.env` and report, without editing anything:

- the `CAVEMAN` value (or the default when the file / key is absent or the value is invalid) and what it means;
- the current session state if a force command or level switch was issued in this chat.

## Constraints (always)

The toggle changes only presentation. It never affects the five-step development procedure, model selection, verification depth, tool-calling rules, or the mandatory report structure from `AGENTS.md`. The skill's safety switches (code / error text verbatim, destructive / security / ordered blocks in normal grammar) hold in every mode, including `on`.
