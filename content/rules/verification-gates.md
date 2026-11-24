---
description: "Closing gates for BSL and metadata — evidence reuse, syntax, logic, style, impact, XML, platform batch check. Load before declaring a full-cycle change done, or for a gate a quick-fix does not carry."
alwaysApply: false
category: quality
---

# Verification Gates — BSL, Impact, and Metadata

**When to load this file:** before validating or declaring a full-cycle BSL / metadata change done. Determine depth and promotion triggers first via `verification-policy.md`; a quick-fix closes on that file's *Quick-fix gate* and comes here only for a missing validator or the procedure of Gate 3a / 4 / 5 / 6.

Delivery-only soft gates and the final report contract live in `verification-delivery.md`.

All gates resolve `TOOL_*` through `content/rules/mcp-policy.md → Tool availability`. Evaluate task/depth triggers before tool presence: a needed `required` capability remains a blocker when absent. `off`/failed tools use only the gate's documented fallback; missing XML, impact, live-IB or EDT evidence is never a pass.

## Gate execution and evidence reuse

A gate is a requirement for the current artifact state, not a request to call the same tool
again. The agent that makes the final edit to an artifact owns its applicable validator run and
records the artifact path and content fingerprint (SHA-256 or Git blob ID), validator result,
run count and relevant execution context in the handoff / implementation report. A commit ID
alone does not identify uncommitted edits. Context includes the checked configuration / extension
and platform version when they affect the result.

The parent closing gate MUST reuse that evidence when the current fingerprint and relevant
context match the recorded state. Checking a fingerprint or reading the edit target is allowed;
it is not a repeated validator run.
It runs only missing or stale gates and MUST NOT repeat a validator against unchanged content
(`mcp-policy.md → C.1`). Any later edit invalidates the affected validator
evidence; the final editor becomes the new owner. The same rule applies to `verify_xml` and
impact-analysis evidence.


## Hard gates — run on every full-cycle change

You MUST run every applicable gate, in order. Gates 1–3 are selected by the task path and depth (next paragraph); Gates 3a, 4, 5 and 6 each run when their own trigger fires. Each gate has an explicit pass / fail criterion and an explicit retry budget. When a required validator is not exposed in the current session, follow the graceful-degradation subsections (after Gate 3 and inside Gate 4) instead of silently skipping. **Gates 3a and 6 also need a prerequisite** (an exposed server, or a reachable platform + infobase); neither ever replaces Gates 1–3.

The gate descriptions below state the `full` behaviour — the strictest level. When `VERIFICATION_DEPTH` is `standard` or `lite`, Gates 1–3 are modulated per `verification-policy.md → "Verification depth levels"`, promotion-trigger paths included: they are full-cycle and keep the `full` retry budget, but their gates follow the active depth.

### Gate 1 — Syntax (`syntaxcheck`)

- Run `syntaxcheck` on every touched `.bsl` module. No exceptions.
- **Check the saved file, not pasted text.** Default is `syntaxcheck_file` by path (optionally narrowed with `lines`). Code text is a fallback only when the file tool is unexposed or the fragment has no file yet — once written, confirm by path.
- Pass criterion: zero `error` items. `warning` items are reviewed in Gate 3.
- **`provenance.index` boundary:** without `index: ready` (including any text-mode call), `UnresolvedMethodCall`, `UnresolvedField` and `QueryToMissingMetadata` stay off, so Gate 1 proves syntax/local rules only and cross-module resolution stays for Gate 4 / IB checks. An index-less server still passes Gate 1 with no Risk line; never wait for `building`, infer mode from container names, or restart/reconfigure containers. Detail — `content/skills/mcp-1c-tools/docs/1c-syntax-checker-mcp.md → Validation boundary`.
- Retry budget — `verification-policy.md → Validator budget`: an `error` is blocking; after the fix obtain a clean confirming run on the changed module within that budget, otherwise Gate 1 fails. Gates 2 and 3 use the same policy with their own blocking severities.

### Gate 2 — Logic & performance (`check_1c_code`)

- Run on every touched module. Always after Gate 1 passes — never before, otherwise the AI checker drowns in syntax noise.
- Pass criterion: no `critical` or `error` severity items.
- `warning` items: triage. Inside-scope warnings (introduced by your change) — fix. Pre-existing warnings outside your scope — leave alone (Surgical Changes).
- AI non-determinism rule: if `check_1c_code` returns inconsistent results across runs on the **same** code, do not loop on it. Take the strictest result, fix what is fixable, document the rest.

### Gate 3 — Style & ITS compliance (`review_1c_code`)

- Run on every touched module after Gate 2 passes.
- Pass criterion: no `error` severity items.
- `warning` items: same triage rule as Gate 2.
- For specific warnings that are intentional and justified: add a `//BSLLS:<rule>` suppression with a 1-line explanation, per `standards(name="dev-standards-code-style") → "Formatting"`. Blanket suppressions without justification are forbidden.

### Graceful degradation for Gates 1–3 — when a validator is not exposed

Apply `TOOL_SYNTAX` / `TOOL_CHECKER` (`content/rules/mcp-policy.md → Tool availability`) at the active depth. An unavailable `required` validator blocks its gate. For `auto` absence/failure or `off`, use the compensation below and report the actual reason; policy never produces a passing verdict:

1. Record: *"Gate N unverified — `<tool>` (`<server>`): `<disabled by policy / not exposed / failed / unsuitable scope>`."*
2. Compensate with what is available. **The platform itself is the first fallback** when `PLATFORM_PATH` and `INFOBASE_PATH` are configured **and the checked configuration contains the current artifact**: bind the artifact and run the check ladder per `content/rules/designer-batch-checks.md → Bind the check to the current artifact` (`/CheckModules` for syntax/context; `/CheckConfig` for structural evidence — not business-logic or ITS review; pass against an older configuration never verifies local edits). Record fingerprint, target, platform/modes, exit code, log path and `/DumpResult`. Without a verified dev/test match, record that limitation and run manual syntax review (paired keywords, directives, parameter lists) for Gate 1 and the internal review checklist (`standards(name="dev-standards-code-style") §8`: quick-fix — changed fragment + nearby locks/transactions; full-cycle — full list + outer-transaction check) for Gates 2–3. Manual checks never prove compliance with unretrieved routed standards (`content/rules/help-corpus-retrieval.md`) and follow `verification-policy.md → Validator budget`.
3. `auto`/`off` allow delivery with these limitations; `required` leaves the dependent verification incomplete. A transactional / metadata / public-API change without Gate 2 needs a follow-up validation run.

Skipping a gate without recording it under Risks is a defect — the same rule as Gate 4's graceful degradation below.

### Gate 3a — Live-IB smoke check (conditional, `1c-data-mcp`)

Gate 3a supplies narrowly scoped evidence from a dev/test infobase. When eligible `1c-data-mcp` tools are available, the agent selects focused behavioural checks needed to resolve a concrete correctness question; UI policy, verification depth and orchestration do not disable them. Distinguish **query parsing**, **metadata resolution**, and **result correctness**: these are separate checks. A clean `vcvalidatequery` result proves parsing only; it does not close the metadata or result questions left by static validation.

**Triggers — run when all of the following hold:**

1. The change authored or modified 1C **query text** (module code, DCS scheme, dynamic list), a self-contained side-effect-free BSL function whose result the static validators cannot confirm, **or** the agent identifies a concrete behavioural result / boundary case requiring a read-only check. State the expected outcome before execution; do not add unrelated test runs.
2. The required `1c-data-mcp` capability is exposed in this session and allowed by tool policy (`vcvalidatequery`, `vcexecutequery` or `vcexecutecode`, as applicable).
3. The connected infobase is a development / test base (`INFOBASE_ROLE`). **On a production infobase this gate is not run** — record the skip and move on.

**Execution:**

- **Query parsing → `vcvalidatequery`.** Pass criterion: `"нет ошибок"`. This parses the query and discovers parameter names; it does **not** execute it, verify that tables / fields exist, check parameter values or evaluate RLS (`content/skills/mcp-1c-tools/docs/1c-data-mcp.md`).
- **Metadata references / runtime resolution.** Reuse current metadata lookups to confirm referenced tables, fields and types; those lookups alone do not prove the whole query resolves at runtime. If runtime resolution is the open question, use a bounded read-only `vcexecutequery` against a dev/test IB with the relevant current metadata / extensions and representative safe parameter values; record that state and the technical user's rights. A successful run proves resolution only for that tested query and context.
- **Result correctness → expected-value comparison.** For a query, compare returned rows / values against the stated scenario; for a pure function use a **read-only** `vcexecutecode` fragment returning the value via `Результат`. `"ошибок нет"` without an expected-value comparison proves absence of a runtime exception only. A run under the technical user does not prove RLS behaviour for other users.
- **Mutations are out of scope for this gate.** No `Записать()` / `Удалить()` / `НачатьТранзакцию` / register movements — the read-only discipline and the consent rules of `content/skills/mcp-1c-tools/docs/1c-data-mcp.md → Safety and discipline` apply unchanged. If confirming the change requires a mutation, that is a task for `1c-tester` against a test base, not for this gate.
- **Budget:** one call per applicable tool / artifact state; run only the checks needed to close an open question. Re-run after a relevant artifact or test-state change only — the no-change-repeat rule (`mcp-policy.md → C.1`) applies.

**Failure is blocking for the artifact,** the same as a Gate 1 `error`: fix the query / fragment and re-run once against the changed state.

**When a trigger fired but the gate could not run** (server not exposed, production IB, or stale / unknown test state), record one line under **Risks**: *"Gate 3a not run — `<reason>`; `<remaining checks>` unverified."* When only parsing ran, report *"Gate 3a: parsing passed; metadata resolution / result correctness unverified"* unless separate evidence closes those questions. Delivery is not blocked by unavailable tooling, but never report an unperformed check as passed. This gate never substitutes for Gates 1–3 and never justifies lowering them.

### Gate 4 — Impact analysis (only when public surface changed)

This gate also checks callers of an internally edited export and verifies that a new metadata
addition is unwired. Such a bounded check does **not** itself promote quick-fix to full-cycle;
promotion depends on the risks it discovers (`verification-policy.md → Quick-fix gate`).

Skip this gate **only** when the change is fully internal:

- a private procedure of a non-export common module;
- a procedure of a form module that has no `Экспорт`;
- a comment / docstring / `//BSLLS:` suppression edit.

In every other case run impact analysis:

- For every changed export procedure / function, use **`trace_call_chain(routine_name=..., object_name=..., direction="callers")`** to find callers; use `direction="callees"` only when the routine's dependencies may have changed. Fallback to **`get_method_call_hierarchy(method_name=...)`**.
- For a changed metadata or module object, use **`trace_impact(object_name=..., direction="downstream")`** to find dependents; use `direction="upstream"` when its dependency tree also needs review. Fallback to **`graph_dependencies(object_name=...)`**.
- For metadata changes (new attribute, renamed object, removed attribute): **`find_objects_using_object`** + **`find_usages_of_object`** to list every metadata reference that needs to be reviewed.

Pass criterion: every caller / dependent listed by impact analysis was either not affected by the change, or explicitly handled in the plan, or explicitly noted as a follow-up risk in the delivery summary. Silent breakage of downstream code is a defect.

**Graceful degradation — when no applicable impact-analysis tool is exposed.** For routine changes, the applicable pair is `trace_call_chain` / `get_method_call_hierarchy`; for object changes it is `trace_impact` / `graph_dependencies`, plus `find_objects_using_object` / `find_usages_of_object` for metadata references. If neither tool in the applicable branch is available, do **not** silently skip the gate. Instead:

1. State the fact explicitly in the Delivery summary under **Risks** as a fixed line: *"Impact analysis not run — no graph / code-metadata MCP exposed in this session; downstream callers and metadata references were not enumerated."*
2. For metadata changes, perform a best-effort manual review based on what the agent already knows about the change (which forms / modules / queries touch the affected object) — list those callers as candidates that still need review, marked as such.
3. Do not promote a quick-fix to "verified" if a metadata or public-API change went through without impact analysis. If the change is risky and the user cannot accept the residual risk, hand off to a session that has the MCP exposed.

Skipping the gate without recording it under Risks is a defect.

### Gate 5 — Metadata XML validation (only when XML was edited)

Skip this gate **only** when no metadata XML was touched.

When XML was edited:

- **Changed-file set.** Check every file the mutation changed, not only the files passed to the tools: the tools also write registrations — `Configuration.xml`, the owner object's XML, subsystem content. Take the set from the dump's `git status` against its state before your first write (changes already there are not yours) or from the wrapper's diff; without git, from the paths the tools printed. A changed file that belongs to no object of the plan (`content/skills/1c-metadata-manage/SKILL.md → Plan unit`) is explained in the delivery report; revert only your own write, never a change that predates it.
- **`verify_xml`** on every XML file of that set. Pass criterion: zero schema violations. If unavailable in `auto`/`off`, run the skill's applicable local validator and report its actual coverage; parsing alone is not schema validation. Uncovered checks stay unverified. In `required`, substitutes do not close the gate.
- **Execution-path check.** Metadata mutations (new objects, attributes, tabular sections, forms, layouts) must have gone through the `1c-metadata-manage` skill / `1c-metadata-manager` subagent — hard gate per `AGENTS.md → Skills and Subagents`. If hand edits were used, this gate passes only when the exception is one of those documented in `SKILL.md → Hard rule` **and** is stated in the delivery summary (`Metadata tooling: hand-edit — <exception>`); additionally cross-check `metadata-xml-workarounds.md` for the recurring traps (UID uniqueness, `Configuration.xml` registration, post-edit validation). Hand-edited metadata without a stated documented exception is a gate failure — the same class as a skipped validator.
- For `Form.xml` edits: schema validity is necessary but not sufficient — whether the form loads cleanly is platform evidence. When the change reaches an infobase, Gate 6 (`/CheckConfig` on the loaded configuration) supplies it; otherwise record under **Risks**: *"Form load not verified on the platform — open `<form>` in Configurator / run `/CheckConfig` before release."* Never claim the form opens without that evidence.

**EDT-format sources (`USE_EDT=true`, MDO tree).** `verify_xml` does not apply to `*.mdo` / `*.form`; use EDT validation (`revalidate_objects` → `get_project_errors` / `get_problem_summary`) and EDT-side mutation/deployment per `content/rules/edt-workflow.md → Validation` (hand-edited `*.mdo` is a gate failure with no exception; Gates 1–3 on `.bsl` are unchanged; never run the Designer batch ladder as a second deployment owner).

### Gate 6 — Platform batch check (only when the change reaches an infobase)

Run before applying an **extension** (`/deploy-and-test`, `/update1cbase`, `/restore-testbase`, `/build-release`, `db-ops` — catches broken `&Вместо` / `&ИзменениеИКонтроль` interceptors via `/CheckCanApplyConfigurationExtensions`) or before applying a **main configuration** when changes exceed MCP validator coverage (full-snapshot deploy, large refactor, release build).

Procedure, artifact binding, ladder (`/CheckModules` → `/CheckCanApplyConfigurationExtensions` → `/CheckConfig`), three-signal verdict (exit code + `/DumpResult` + `/Out`; warnings fail) and evidence reuse — `content/rules/designer-batch-checks.md`. Record fingerprint, source-to-IB match, target, platform/modes, exit code, log path and `/DumpResult`.

**When triggered but unable to run** (no `PLATFORM_PATH` / `INFOBASE_PATH`, or production IB with no dev/test copy), add under **Risks**: *"Gate 6 not run — `<reason>`; extension applicability was not verified against an infobase."* Delivery is not blocked, but the gap must be explicit. Never substitutes for Gates 1–5.
