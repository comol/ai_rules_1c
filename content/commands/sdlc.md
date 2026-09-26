---
description: Select a named SDLC QA profile — lite, standard or full — or report status; task triage remains risk-based
argumentHint: "[lite|standard|full|status]"
---

# /sdlc — named SDLC QA profiles

Select the project's verification profile through `VERIFICATION_DEPTH` in `.dev.env`. Load `content/rules/verification-policy.md` before acting; it owns gate selection and retry budgets. Parameters and defaults — `content/rules/dev-standards-env.md`.

## Profiles and task paths

Use these names in Russian confirmations:

- `lite` — **Облегчённый**: reduced checks for low-risk edits; selecting it also sets `UI_TESTING=off`.
- `standard` — **Стандартный**: the default verification depth.
- `full` — **Полный**: all three static validators for touched BSL, with the full retry budget.

The task path is selected separately by triage: `docs-fix` (правка документации), `spec-authoring` (подготовка спецификации), `quick-fix` (локальная правка), `full-cycle` (полный цикл разработки). A profile does not force a task path, enable delegation, create an OpenSpec change, deploy, or turn the SDLC off. In particular, `full` is a verification profile; `full-cycle` is a task path.

## Arguments

Trim whitespace and compare case-insensitively:

- Empty or `status` — read and report the effective profile and `UI_TESTING`; edit nothing.
- `lite`, `standard`, `full` — select that profile.
- Any other argument, including `on` / `off` — list the accepted profile names and make no changes. Legacy `on` / `off` belong to `/litemode` (`content/commands/litemode.md`).

## Apply a profile

1. Read the current `VERIFICATION_DEPTH` and `UI_TESTING`. Missing / empty / invalid values use their defaults from `dev-standards-env.md`.
2. Set `VERIFICATION_DEPTH` to the selected profile. For `lite`, also set `UI_TESTING=off`; for `standard` and `full`, preserve `UI_TESTING`. These profiles do not restore the pre-lite UI setting; report the resulting value explicitly.
3. Edit only these applicable keys in `.dev.env`, replacing the existing line or appending a missing key. Preserve all other content. If the file is missing, apply the choice to the current session only, say it is not persisted, and point to `install.ps1 init` for project setup; do not create a partial file or start installation as part of this command.
4. Apply the effective profile immediately. No re-render, `install.ps1 update`, or client restart is required.
5. Confirm in Russian: the profile's name and slug, project persistence or session-only scope, the applicable verification depth, and the effective `UI_TESTING` value. If selecting `lite` disables `auto` UI testing, state that automatic UI tests are now disabled.

## Status

Report the effective profile using its name and slug, its source (project setting, session-only override, or default), and what it checks. Report `UI_TESTING` as automatic, on request, or disabled. Use an active session-only override before the file/default; an empty command never changes the profile. Do not invent a task path when no development task is being assessed.

## Mandatory floor

Every profile preserves the safety floor in `verification-policy.md`: syntax validation on every touched BSL module, the full validator chain and full budget for promotion-trigger paths, and Gates 4 / 5 on their own triggers. Docs-fix remains structural verification only. `UI_TESTING=off` has the same meaning as a manually configured value; the profile does not change the UI-testing policy itself.
