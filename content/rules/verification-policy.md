---
description: Verification policy — depth levels, quick-fix eligibility, promotion triggers, and the quick-fix gate
alwaysApply: false
category: quality
---

# Verification Policy — Depth and Triage

**When to load this file:** during task triage, when deciding quick-fix vs. full-cycle, resolving `VERIFICATION_DEPTH`, or determining which gates a low-risk edit requires.

The closing gates themselves live in `verification-gates.md`; delivery-only checks live in `verification-delivery.md`.

## Verification depth levels (`VERIFICATION_DEPTH`)

The `VERIFICATION_DEPTH` parameter in `.dev.env` (`dev-standards-env.md → "Process-tuning parameters"`) tunes **how deep** Gates 1–3 run for **low-risk** edits. It is **Defaulted** — empty / invalid = `full`; the canonical editor is the `/litemode` slash command (which also flips `UI_TESTING` at level `lite`); the agent must not ask for the value. Three levels:

| Level | Gates 1–3 behaviour |
|---|---|
| `full` (default) | Run `syntaxcheck → check_1c_code → review_1c_code`. One clean pass on the latest state is required; after a blocking fix, allow up to 3 calls total per validator (`AGENTS.md → MCP Tool Calling → B.1`). |
| `standard` | Run all three validators. Normally one clean pass each; after a blocking fix, allow exactly one mandatory confirmation (2 calls total), with no open-ended retry loop. |
| `lite` | For a **low-risk** edit (quick-fix-eligible per Triage details below): Gate 1 (`syntaxcheck`) stays mandatory on every touched module; Gates 2–3 (`check_1c_code`, `review_1c_code`) are **skipped** unless the user explicitly asks for them. For any change that hits a **promotion trigger** (see Triage details) the full `full`-level chain runs regardless of the setting. |

**Safety floor — never crossed by any level:**

- Gate 1 (`syntaxcheck`) is mandatory on every touched BSL module at every level. It is never skipped.
- Promotion-trigger changes (transactional code paths, public `Экспорт` contract changes, wired metadata, RLS conditions, event subscriptions / scheduled jobs — see Triage details) always run the full `syntaxcheck → check_1c_code → review_1c_code` chain with the retry budget, **regardless of `VERIFICATION_DEPTH`**. `lite` / `standard` lighten only the checks that were already being applied to low-risk, quick-fix-eligible edits — they do not weaken the control of dangerous paths.
- Gate 4 (impact analysis) and Gate 5 (metadata XML) are gated by their own triggers and are unaffected by `VERIFICATION_DEPTH`.
- The graceful-degradation and AI-non-determinism rules in `verification-gates.md` apply unchanged within whatever level is active.

When in doubt about whether a change is low-risk — treat it as promotion-triggering and run the full chain.

## Triage details — quick-fix eligibility and promotion triggers

Referenced from `AGENTS.md → Development Procedure → Triage`. Path definitions live there; this section owns the detailed metadata criteria.

**Isolated metadata addition (allowed as quick-fix).** A metadata change qualifies as quick-fix **only** when **all** of the following hold:

- it is a **new** isolated object — independent information register (`Независимый`, no registrar) with ≤3 dimensions / ≤2 resources / no module; defined type; enumeration; constant; new attribute on an existing reference object **that is not yet referenced from any code, query, RLS condition, fill-check, or form**;
- no existing module / query / RLS condition / event subscription / scheduled job is modified in the same change;
- no posting (`ОбработкаПроведения`) / `ПередЗаписью` / `ПриЗаписи` / extension interceptor / role permission is touched;
- the object does not participate in БСП-managed subsystems requiring `ПриОпределенииПодсистемСКоторымиВозможнаИнтеграция` registration in the same change.

If the same task also wires the new object into existing code (a query, a movement, a form, an export) — that wiring is a separate change; either keep the wiring out of this task (deliver the isolated object first), or promote the whole task to full-cycle.

**Promote to full-cycle even if the change looks small.** Escalate from quick-fix when the change touches any of:

- metadata wired into existing behavior — renaming or removing an object / attribute / tabular section / form / role; modifying an existing posting / write path because of the metadata change; adding a metadata object immediately used by existing modules in the same change; changes to RLS conditions, indexing of an existing dimension, fill-checks, or event subscriptions;
- a transactional code path (`ОбработкаПроведения`, `ПередЗаписью` / `ПриЗаписи`, anything inside `НачалоТранзакции`);
- a **contract change** of a public `Экспорт` procedure / function of a common module — signature, return type, or observable behaviour that external callers rely on. A purely internal fix inside an export routine that preserves the contract (same inputs → same outputs for callers, the defect itself excepted) stays quick-fix within the line budget;
- an adopted object of an extension (`ObjectBelonging=Adopted`);
- an event subscription, scheduled / background job, or RLS condition.

When in doubt — full-cycle wins.

## Quick-fix gate

Quick-fix reduces planning and delegation overhead, **not** verification depth — the depth of Gates 1–3 is instead an explicit, project-wide opt-in via `VERIFICATION_DEPTH` (see "Verification depth levels" above). At the default `full`, quick-fix runs the applicable gates from `verification-gates.md` in full:

- BSL quick-fix — run Gates 1–3 in order (`syntaxcheck` → `check_1c_code` → `review_1c_code`).
- Pure metadata XML quick-fix — run Gate 5 (`verify_xml`).
- Metadata XML that embeds or generates BSL — run Gates 1–3 for every touched module, then Gate 5.
- Gate 4 is skipped only because the quick-fix definition excludes public-surface, transactional, wired-metadata, RLS, subscription, scheduled-job, and other impact-bearing changes. If impact analysis is relevant, the task was misclassified — promote it to full-cycle before editing.

The validator availability and retry-budget rules in `verification-gates.md` apply unchanged. Missing validators use the same documented graceful degradation; they are never silently skipped.
