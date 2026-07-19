---
description: Systematic 4-phase debugging methodology adapted for 1C (reproduce → hypothesize → experiment → fix), with a fast path for directly evidenced root causes (DEBUG_FAST_PATH in .dev.env)
alwaysApply: false
category: quality
---

# Systematic Debugging — 1C Adaptation

**When to load this file:** any task that involves diagnosing a bug, runtime error, regression, performance regression, or unexpected behavior — whether the parent agent is debugging directly or delegating to the `1c-error-fixer` / `1c-performance-optimizer` subagent.

**Goal:** replace ad-hoc trial-and-error with a structured root-cause loop. Skipping a phase is a defect — unless the bug qualifies for the **fast path** below, which is a documented shortcut, not a skipped phase.

The methodology is adapted from the `systematic-debugging` skill of [obra/superpowers](https://github.com/obra/superpowers) and combined with 1C platform mechanics (debugger, `ЖурналРегистрации`, `ОтчетПоЖурналуРегистрации`, `ПоказатьЗначение`, `СообщитьПользователю`, `Replay` of background jobs, technological log).

## Core principle

> **Reproduce first, hypothesize second, change code last.**

If you cannot reproduce the defect deterministically, you have no signal that any fix worked. Every "it should be fixed now" without a reproduction step is a regression waiting to happen.

## Fast path — for directly evidenced root causes

The full 4-phase loop earns its cost on non-obvious bugs. Forcing it onto a bug whose cause is already in front of you is process for its own sake. Take the fast path when **all** of the following hold:

- the root cause is **directly evidenced** by the available material — the error text / stack trace / validator finding points at a concrete location, and the defect is evident from reading that code (missing `КонецЕсли`, an unchecked `Неопределено`, a typo in an attribute name, a wrong parameter order, an obvious off-by-one);
- the fix is **local** and fits the quick-fix constraints (one logical change in one module, within `QUICKFIX_MAX_LINES`);
- no promotion trigger from `verification-policy.md → Triage details` is touched (transactional paths, public contracts, wired metadata, RLS / subscriptions / jobs, adopted objects);
- the failing scenario is known concretely enough to re-check after the fix (from the error message, the user's report, or the log entry).

Fast-path procedure: state the evidence for the root cause in 1–2 lines → apply the minimal fix → re-check the original failing scenario → run the applicable validator gate (`verification-checklist.md`). No hypothesis list, no experiment protocol, no full Phase 1 passport. If the "obvious" fix does not eliminate the symptom on the first attempt — the cause was not obvious; stop patching and enter the full loop at Phase 1.

**`DEBUG_FAST_PATH` (`.dev.env`, Defaulted — empty / missing / invalid = `standard`, never ask):**

| Value | Meaning |
|---|---|
| `standard` (default / empty) | Fast path exactly as defined above. |
| `extended` | Two criteria are relaxed: a **user-supplied reproduction** (exact steps / data / error text in the report) may be trusted as the failing scenario without reproducing it independently first; and a **regression introduced by the immediately preceding change in the same session** may take the fast path even when the defect is not evident from one location — the diff of that change is treated as the evidence base. Everything else (locality, no promotion triggers, re-check after fix) still applies. |
| `off` | Fast path disabled — every bug goes through the full 4-phase loop. For teams that want maximum rigor regardless of bug shape. |

## The four phases (full loop)

You MUST complete all four phases in order for every bug that does not qualify for the fast path. Do not jump to phase 4 ("write the fix") before phases 1–3 have produced verifiable artifacts.

### Phase 1 — Reproduce

Goal: a deterministic, minimal reproduction case in a controlled environment.

Required outputs of this phase — **in the scope relevant to the bug** (a pure code-level logic error rarely needs the role set or locale; a rights / RLS / session bug always does):

- exact infobase (file or SQL — record the connection string), platform version, configuration / extension versions;
- exact user, role set, session parameters, locale;
- exact input data (document number / catalog reference / register record key) — copy or anonymize, do not paraphrase;
- exact reproduction steps (UI clicks, form, command, or API call);
- exact observed result (error message, stack trace, wrong value, slow timing);
- exact expected result.

Tools to use:

- **`vcloggetlasterror`** (`1c-data-mcp`, when the server is exposed in the session) — pull the most recent error from `ЖурналРегистрации` of the live IB without leaving the agent: timestamp, event, affected metadata object, data presentation, full description. Run it immediately after the user's repro attempt to confirm an error landed in the log and on what object. Limitation: only the single most recent record with `УровеньЖурналаРегистрации.Ошибка` in the last 24 h. Wider filters / older records → fall back to the Configurator's `ОтчетПоЖурналуРегистрации` or to a custom `ВыгрузитьЖурналРегистрации` wrapped in `vcexecutecode`.
- **Configurator → Debug** (`Отладка → Подключиться`) to attach to the running session, capture the call stack, inspect locals.
- **`ЖурналРегистрации`** filter by date range / user / event / metadata to find the failing call. For high-volume errors prefer `ВыгрузитьЖурналРегистрации` to a `ТаблицаЗначений` for offline analysis.
- **Technological log** (`logcfg.xml`) for platform-level events (DBMS errors, deadlocks, lock conflicts, timeouts) when the application log is not enough.
- **`ОбработкаПроведения`** + the `Replay` mechanism for documents — re-post the failing document under the debugger.
- **MCP**: `codesearch` / `search_code` to find the exact procedure that printed the error message, `search_function` to locate it by name, `get_module_structure` to get its surroundings.

If you cannot reproduce, **stop**. Ask the user for missing input data, screenshots, the exact step sequence, or a copy of the infobase. Do not guess.

### Phase 2 — Hypothesize

Goal: a small set of falsifiable hypotheses about the root cause, ranked by likelihood.

For each hypothesis state:

- **Statement** — exactly which code path / metadata / data state causes the symptom.
- **Falsifying experiment** — what would prove the hypothesis wrong (a log line that should appear but doesn't; a value that should be `Неопределено`; a query that should return an empty result; a lock that should not be acquired).
- **Cost of the experiment** — cheap (read-only query / `ПоказатьЗначение`) vs. expensive (rebuild infobase, reload data).

Tools to use:

- **`trace_call_chain(routine_name=..., object_name=..., direction="callers")`** to map all call paths that reach the failing routine; use `direction="callees"` to map routines it calls.
- **`trace_impact(object_name=...)`** only for object-level dependencies of the owning module / metadata object (registers, referenced objects, movements), not as a routine-call query.
- **`get_method_call_hierarchy`** as a fallback when the graph server is unavailable.
- **`docinfo`** to verify that a built-in function actually does what you assume — many bugs are platform-version-dependent (`ТекущаяДатаСеанса` vs `ТекущаяДата`, `НайтиПоНаименованию` collation, `ПолучитьСтруктуруХраненияБазыДанных` differences across versions).
- **`its_help` → `fetch_its`** to verify the documented behaviour of the platform mechanism you suspect.
- **`ask_1c_ai`** as a hint generator (treat as a draft — do not let an AI hint replace the falsifying experiment).

Produce at least 2 hypotheses. In the full loop a single hypothesis is anchoring bias — challenge it with a competing one even when it feels right (a bug that genuinely admits only one explanation belongs on the fast path, not here).

### Phase 3 — Experiment

Goal: confirm or reject each hypothesis with concrete evidence, **without changing production code**.

Allowed experimental tools (read-only or scoped to a copy of the infobase):

- **debugger watches** (`Просмотр → Локальные`, `Выражение`) at the suspected line.
- **`ЗаписьЖурналаРегистрации("Debug.<Module>", УровеньЖурналаРегистрации.Информация, , , <Структура>)`** — temporary log lines, removed before the fix is committed.
- **`ПоказатьЗначение(Неопределено, <Объект>)`** for client-side diagnostics; **`СообщитьПользователю` / `Сообщение.Сообщить()`** for server-side.
- **read-only queries** in the configurator's `Console of queries` (`Консоль запросов`) against the failing data — never mutate.
- **`validatequery`** → **`vcexecutequery`** (`1c-data-mcp`, when the server is exposed) — parse-check, then execute a falsifying query against the live IB without leaving the agent. Always read-only. Cheap evidence for a data-state hypothesis ("does this register really have a non-zero balance for this dimension set", "does this attribute really equal X for this reference").
- **`vcexecutecode`** (`1c-data-mcp`, when exposed) — run a small **read-only** BSL fragment to verify a platform-version-specific or metadata-state hypothesis (type checks, `ЗначениеЗаполнено`, `Метаданные.НайтиПоПолномуИмени`, `ПолучитьФункциональнуюОпцию`). Default to read-only; **never** wrap `Записать()` / `Удалить()` / `НачалоТранзакции` / DML in `vcexecutecode` without explicit user consent and a rollback plan — and only on a copy IB. See `content/skills/mcp-1c-tools/docs/1c-data-mcp.md → Safety` for full rules.
- **`КопироватьИнформационнуюБазу`** or a SQL snapshot **before** any destructive experiment. The rule is: experiments either run on a copy or do not run at all.

Forbidden during experiments:

- Editing production code "to test a theory". Every code change must come from a confirmed hypothesis in phase 4.
- `Удалить()` / `Записать()` / `ЗаписатьИзменения()` / direct SQL DML against a live infobase.
- Disabling roles, profile or session parameter changes that affect other users.

After the experiment, write down the result:

> Hypothesis: `<...>` — **confirmed** by `<observed evidence>` / **rejected** by `<observed evidence>`.

If all hypotheses are rejected, return to phase 2 and produce new ones. Do not weaken the hypotheses to fit the data.

### Phase 4 — Fix

Goal: minimal code change that addresses the **confirmed** root cause, plus a regression guard.

Required:

- The fix touches only the code paths involved in the confirmed hypothesis (Surgical Changes principle from `AGENTS.md`).
- A regression guard exists: a query, a `ЖурналРегистрации` event, an `Утверждение`, or — at minimum — a documented manual reproduction step in the change description.
- All temporary `ЗаписьЖурналаРегистрации("Debug.*"`, `ПоказатьЗначение`, hard-coded values, breakpoints, and TODO markers introduced in phase 3 are removed.
- Verification chain runs cleanly: `syntaxcheck` → `check_1c_code` → `review_1c_code`, followed by the applicable routine-level (`trace_call_chain`) or object-level (`trace_impact`) Gate 4 branch from `verification-gates.md`.
- The original reproduction case from phase 1 no longer triggers the symptom.

If the fix requires architectural rework (signature changes in shared common modules, metadata edits, a new register), escalate — call the `1c-architect` or `1c-developer` subagent rather than expanding the scope of the bug fix yourself.

## Anti-patterns

- **"Probably this `Если` should be `Иначе`"** without a reproduction or experiment — a guess. The fast path is not a license for guesses: it requires stated direct evidence, not a hunch.
- **Stretching the fast path** — declaring a cause "obvious" without naming the evidence, or staying on the fast path after the first fix attempt failed to eliminate the symptom.
- **Adding `Попытка / Исключение` to silence the error** without identifying the cause — hides the bug, does not fix it.
- **Re-posting / re-recording / `Записать(РежимЗаписиДокумента.Запись)`** as a fix instead of investigating why the data is wrong.
- **Restarting the user session** as a fix.
- **Reindexing / `Тестирование и исправление`** as a fix without documenting which specific structural inconsistency was repaired.
- **Disabling the failing test / removing the failing assertion** instead of fixing the code under test.
- **"Works on my machine"** when the user reports the bug — you do not have a reproduction yet, you have a hypothesis. Go back to phase 1.

## Process flow

```
[bug] ── fast-path criteria hold? ──► yes: evidence ► fix ► re-check ► gate
   │                                        │
   no                                       └─ symptom persists ► full loop
   ▼
Reproduce ──► Hypothesize ──► Experiment ──► Fix
   ▲              ▲                │            │
   │              │                ▼            │
   │              └── new hypotheses ◄── all hypotheses rejected
   │
   └── cannot reproduce ── ASK USER, do not proceed
```

## Companion rules

- `verification-checklist.md` — the post-fix gate.
- `subagent-pipeline.md` — when to delegate the bug to `1c-error-fixer` vs. handle it directly.
- `tooling-playbooks.md → Error Fixing` — concrete MCP tool sequence for each phase.
- `anti-patterns.md` — to recognize anti-patterns that produce bugs in the first place.
