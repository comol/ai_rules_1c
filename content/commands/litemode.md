---
description: Toggle lightweight QA mode — set VERIFICATION_DEPTH (full|standard|lite) in .dev.env and, at level lite, disable UI testing (UI_TESTING=off)
argumentHint: "[on|off|full|standard|lite|status]"
---

# /litemode — lightweight QA mode

Toggle how much static verification and UI testing the agent runs for the **project** by writing `VERIFICATION_DEPTH` (and, coupled, `UI_TESTING`) in `.dev.env`. Canonical behaviour of the depth levels — `content/rules/verification-policy.md → "Verification depth levels"` and `content/rules/dev-standards-env.md §1` (installed copy; match by file name per the path convention in `AGENTS.md`). Load `verification-policy.md` before acting.

Parse the argument: empty or `on` / `lite` — enable lite; `standard` — set the standard level; `off` / `full` — restore full verification; `status` — report the current state without editing.

The command edits **only** the `VERIFICATION_DEPTH` and (as described below) `UI_TESTING` lines in `.dev.env` — never other keys, never other files.

## What the levels mean (summary — canon in `verification-policy.md`)

- `full` (default) — all three validators (`syntaxcheck → check_1c_code → review_1c_code`); one clean pass on the latest state is required, with up to 3 calls total after blocking fixes (`AGENTS.md → MCP Tool Calling → B.1`).
- `standard` — all three validators; normally one clean pass, with exactly one mandatory confirmation after a blocking fix (2 calls total, no open-ended retry loop).
- `lite` — for **low-risk** edits `syntaxcheck` on every touched module stays mandatory; `check_1c_code` + `review_1c_code` run only for high-risk changes (transactions, public `Экспорт` contract, wired metadata, RLS, subscriptions / scheduled jobs) or on explicit request. Full-cycle promotion triggers always get the full chain. Gates 4/5 (impact / XML) are unchanged.

## on / lite (default)

1. Read `.dev.env`: `VERIFICATION_DEPTH` and `UI_TESTING`.
2. Set `VERIFICATION_DEPTH=lite`. If the key line exists — replace its value; if absent — append the line at the end of the file with a one-line comment `# Глубина проверок кода: full | standard | lite (переключается командой /litemode)`.
3. **UI-testing coupling.** Lite means "minimal QA, no browser UI tests". Set `UI_TESTING=off`. Before overwriting, if `UI_TESTING` was `auto`, note in the confirmation that automatic UI testing is now disabled (so the user is aware it will not run after a deploy).
4. If `.dev.env` does not exist: do **not** create a partial file (the installer's `Place-DevEnv` places the full template only when the file is missing — a stub would permanently block it). Enable the mode for the current session only, and tell the user to run `install.ps1 init` (or copy `.dev.env.example` to `.dev.env`) to make it persistent.
5. **No re-render needed.** `VERIFICATION_DEPTH` and `UI_TESTING` are read directly from `.dev.env` by the rules at task time — editing the file is enough, no `install.ps1 update` and no client restart.
6. Load the `verification-policy.md` rule and apply the lite semantics immediately — from this message on, in this session.
7. Confirm to the user in 3–4 lines, in Russian:
   - режим облегчённых проверок включён и записан в `.dev.env` (`VERIFICATION_DEPTH=lite`) — действует для проекта, включая новые чаты;
   - что именно облегчается: `syntaxcheck` остаётся обязательным на всех задетых модулях, `check_1c_code` / `review_1c_code` — только для высокорисковых правок; транзакции и публичные контракты по-прежнему проверяются полной цепочкой;
   - UI-тесты отключены (`UI_TESTING=off`);
   - выключение — `/litemode off`.

## standard

1. Set `VERIFICATION_DEPTH=standard` (same edit rules as step 2 above). Do **not** touch `UI_TESTING` — report its current effective value.
2. Apply immediately and confirm: все три валидатора обычно выполняются одним чистым прогоном; после исправления блокирующей ошибки обязателен один подтверждающий прогон, без дальнейшего цикла повторов.

## off / full

1. Set `VERIFICATION_DEPTH=full` (same edit rules; if `.dev.env` or the key is absent, there is nothing to persist — full is already the default).
2. **UI-testing restore.** If `UI_TESTING` is currently `off`, set it back to `manual` (the default) so UI tests are again available on explicit request; if it holds any other value, leave it untouched. State the resulting `UI_TESTING` value in the confirmation (if the user previously ran `auto`, they must re-set it manually — the command cannot know the pre-lite value).
3. Stop applying the lite/standard semantics immediately in this session and confirm: полная глубина проверок восстановлена (`VERIFICATION_DEPTH=full`), действует канон бюджета валидаторов из `AGENTS.md → MCP Tool Calling → B.1`.

## status

Read `.dev.env` and report, without editing anything:

- `VERIFICATION_DEPTH` (missing file / missing key / empty / invalid value = `full`) and what it means;
- `UI_TESTING` (empty / invalid = `manual`) and whether UI tests run automatically, on request, or are disabled.

## Constraints (always)

The mode never overrides stricter safety rules:

- `syntaxcheck` (Gate 1) is **always** run on every touched BSL module, at every level — it is the cheapest gate and is never skipped.
- Changes on **promotion-trigger** paths (`verification-policy.md → Triage details`: transactions, public `Экспорт` contracts, wired metadata, RLS, event subscriptions / scheduled jobs) always run the full `syntaxcheck → check_1c_code → review_1c_code` chain regardless of `VERIFICATION_DEPTH` — lite lightens only the checks that were already applied to low-risk, quick-fix-eligible edits.
- Gate 4 (impact analysis) and Gate 5 (metadata XML) are risk-gated by their own triggers and are unaffected by `VERIFICATION_DEPTH`.
- `UI_TESTING=off` set by lite behaves exactly like a manually set `off` (canon: `dev-standards-env.md → "UI_TESTING"`): on an explicit UI-test request the agent reports it is disabled and asks the user to switch to `manual` / `auto`.
