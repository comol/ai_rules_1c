---
description: Verification execution gates for BSL and metadata — evidence reuse, syntax, logic, style, impact analysis, XML validation, and the platform batch check before an infobase apply
alwaysApply: false
category: quality
---

# Verification Gates — BSL, Impact, and Metadata

**When to load this file:** before validating or declaring a BSL / metadata change done. Determine depth and promotion triggers first via `verification-policy.md`.

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
(`AGENTS.md → MCP Tool Calling → C.1`). Any later edit invalidates the affected validator
evidence; the final editor becomes the new owner. The same rule applies to `verify_xml` and
impact-analysis evidence.


## Hard gates — run on every full-cycle change

You MUST run all five gates in order. Each gate has an explicit pass / fail criterion and an explicit retry budget. When a required validator is not exposed in the current session, follow the graceful-degradation subsections (after Gate 3 and inside Gate 4) instead of silently skipping. **Gates 3a and 6 are conditional** — each runs only when its own trigger fires and its prerequisite (an exposed server, or a reachable platform + infobase) is present; neither ever replaces Gates 1–3.

The gate descriptions below state the `full` behaviour — the strictest level, and the one a promotion-trigger path always gets. When `VERIFICATION_DEPTH` is `standard` or `lite`, Gates 1–3 are modulated per `verification-policy.md → "Verification depth levels"` — but a full-cycle change on any promotion-trigger path always runs the complete chain regardless of the level (the safety floor).

### Gate 1 — Syntax (`syntaxcheck`)

- Run `syntaxcheck` on every touched `.bsl` module. No exceptions.
- **Check the saved file, not pasted text.** The default form of this gate is `syntaxcheck_file`: save the module, then check it by path (optionally narrowed with `lines` to the edited procedure). Reading a module into the prompt only to paste its body back into `syntaxcheck` buys the same answer for the price of the whole module. Code text is the fallback for two cases only — the file tool is not exposed in this session, or the code has no file yet (a fragment just generated). A fragment checked as text still gets its Gate 1 evidence by path once it is written to the module: the gate is evidence about what will be loaded into the infobase, and that is the on-disk state.
- Pass criterion: zero `error` items. `warning` items are reviewed in Gate 3.
- **What a clean pass proves depends on `provenance.index`.** Without a full-configuration index — `absent`, `building` or `failed`, and *any* text-mode `syntaxcheck` call, which the index never answers — the server keeps `UnresolvedMethodCall`, `UnresolvedField` and `QueryToMissingMetadata` switched off, so the gate is evidence for syntax and local rules only and cross-module resolution stays an open question for Gate 4 and a configuration-level test. On a `syntaxcheck_file` call answered with `index: ready` those three checks are part of the evidence. **An index-less server passes Gate 1 exactly as before** — the mode is an optional addition, its absence is the ordinary state, not a validator failure and not a graceful-degradation case (the validator *is* exposed), so it needs no Risk line. `building` is likewise read, never waited for: indexing a configuration runs for hours while the container keeps answering, so never hold a check or a delivery for it. Read the field in the answer you actually got; never infer the mode from a container name, and never restart or reconfigure the container to obtain it — that is an operator decision. Detail — `content/skills/mcp-1c-tools/docs/1c-syntax-checker-mcp.md → Validation boundary`.
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
2. Compensate with what is available. **The platform itself is the first fallback** when `PLATFORM_PATH` and `INFOBASE_PATH` are configured **and the checked configuration contains the current artifact**. Establish the source-to-IB match per `content/rules/designer-batch-checks.md → Bind the check to the current artifact` before running its check ladder. `/CheckModules` supplies syntax / context evidence for the loaded modules; `/CheckConfig` supplies structural evidence, not a replacement for business-logic or ITS review. Record the artifact fingerprint, target, platform / modes, process exit code, log path and `/DumpResult` code. A pass against an older configuration never verifies local changes. If a matching dev/test state cannot be established through an authorized workflow, record that limitation and use manual syntax review (paired keywords, directives, parameter lists) for Gate 1 and the internal checklist for Gates 2–3.

   **Minimum internal review checklist.** These independent checks remain available when a validator is missing. They do not reproduce a routed standard or prove compliance with standards that were not retrieved through MCP; report that evidence gap and follow `content/rules/help-corpus-retrieval.md` for any required standard.

   - **Quick-fix** — correctness and edge cases of the changed fragment; plus locks / transactions when the edit sits near transactional code. That is enough — do not run the full checklist on a 10-line fix.
   - **Full-cycle** — the full list: style, readability, correctness, edge cases, security, concurrency / locks / transactions, BSL-LS compliance.
   - Always consider whether an external transaction already exists (e.g. an object-write transaction) before opening a new one.
   - Findings follow `verification-policy.md → Validator budget` (a blocking defect needs a clean confirming run on the changed state; style noise does not start another loop; budget exhausted = unverified).
3. `auto`/`off` allow delivery with these limitations; `required` leaves the dependent verification incomplete. A transactional / metadata / public-API change without Gate 2 needs a follow-up validation run.

Skipping a gate without recording it under Risks is a defect — the same rule as Gate 4's graceful degradation below.

### Gate 3a — Live-IB smoke check (conditional, `1c-data-mcp`)

Gate 3a supplies narrowly scoped evidence from a dev/test infobase. Distinguish **query parsing**, **metadata resolution**, and **result correctness**: these are separate checks. A clean `validatequery` result proves parsing only; it does not close the metadata or result questions left by static validation.

**Triggers — run when all of the following hold:**

1. The change authored or modified 1C **query text** (module code, DCS scheme, dynamic list) **or** a self-contained BSL function with no side effects whose result the static validators cannot confirm.
2. `1c-data-mcp` is exposed in the current session (`validatequery` / `vcexecutecode` visible in the tool schema).
3. The connected infobase is a development / test base (`INFOBASE_ROLE`). **On a production infobase this gate is not run** — record the skip and move on.

**Execution:**

- **Query parsing → `validatequery`.** Pass criterion: `"нет ошибок"`. This parses the query and discovers parameter names; it does **not** execute it, verify that tables / fields exist, check parameter values or evaluate RLS (`content/skills/mcp-1c-tools/docs/1c-data-mcp.md`).
- **Metadata references / runtime resolution.** Reuse current metadata lookups to confirm referenced tables, fields and types; those lookups alone do not prove the whole query resolves at runtime. If runtime resolution is the open question, use a bounded read-only `vcexecutequery` against a dev/test IB with the relevant current metadata / extensions and representative safe parameter values; record that state and the technical user's rights. A successful run proves resolution only for that tested query and context.
- **Result correctness → expected-value comparison.** For a query, compare returned rows / values against the stated scenario; for a pure function use a **read-only** `vcexecutecode` fragment returning the value via `Результат`. `"ошибок нет"` without an expected-value comparison proves absence of a runtime exception only. A run under the technical user does not prove RLS behaviour for other users.
- **Mutations are out of scope for this gate.** No `Записать()` / `Удалить()` / `НачатьТранзакцию` / register movements — the read-only discipline and the consent rules of `content/skills/mcp-1c-tools/docs/1c-data-mcp.md → Safety and discipline` apply unchanged. If confirming the change requires a mutation, that is a task for `1c-tester` against a test base, not for this gate.
- **Budget:** one call per applicable tool / artifact state; run only the checks needed to close an open question. Re-run after a relevant artifact or test-state change only — the no-change-repeat rule (`AGENTS.md → MCP Tool Calling → C.1`) applies.

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

- **`verify_xml`** on every modified XML file. Pass criterion: zero schema violations. If unavailable in `auto`/`off`, run the skill's applicable local validator and report its actual coverage; parsing alone is not schema validation. Uncovered checks stay unverified. In `required`, substitutes do not close the gate.
- **Execution-path check.** Metadata mutations (new objects, attributes, tabular sections, forms, layouts) must have gone through the `1c-metadata-manage` skill / `1c-metadata-manager` subagent — hard gate per `AGENTS.md → Skills and Subagents`. If hand edits were used, this gate passes only when the exception is one of those documented in `SKILL.md → Hard rule` **and** is stated in the delivery summary (`Metadata tooling: hand-edit — <exception>`); additionally cross-check `metadata-xml-workarounds.md` for the recurring traps (LineNumber, PagesGroupExtInfo, Page.enabled, UID uniqueness). Hand-edited metadata without a stated documented exception is a gate failure — the same class as a skipped validator.
- For `Form.xml` edits: schema validity is necessary but not sufficient — whether the form loads cleanly is platform evidence. When the change reaches an infobase, Gate 6 (`/CheckConfig` on the loaded configuration) supplies it; otherwise record under **Risks**: *"Form load not verified on the platform — open `<form>` in Configurator / run `/CheckConfig` before release."* Never claim the form opens without that evidence.

**EDT-format sources (`USE_EDT=true`, MDO tree).** `verify_xml` does not apply to `*.mdo` / `*.form`. The equivalent evidence is EDT's own validation — `revalidate_objects` on the changed objects → `get_project_errors` / `get_problem_summary` — recorded in the delivery summary exactly as `verify_xml` evidence is. The execution-path check is unchanged in spirit: the mutation must have gone through EDT (EDT-MCP, the EDT UI, or a confirmed export/import round trip), and a hand-edited `*.mdo` is a gate failure with no documented exception. Canon — `content/rules/edt-workflow.md → Validation`. Gates 1–3 on BSL are unaffected: modules are plain `.bsl` in both formats. The same substitution applies to Gate 6 below: EDT's validation and `update_database` are that project's applicability evidence, and the batch ladder must not run as a second deployment owner in the same run.

### Gate 6 — Platform batch check (only when the change reaches an infobase)

Gates 1–5 read source. They cannot answer the question the platform answers: does this configuration or extension **apply** to the target infobase. Run this gate when either trigger fires:

1. **An extension is about to be applied** to an infobase — by `/deploy-and-test`, `/update1cbase`, `/restore-testbase`, `/build-release`, or a `db-ops` load. A `&Вместо` / `&ИзменениеИКонтроль` interceptor naming a method that no longer exists in the vendor original passes Gates 1–5 untouched: the source is well-formed and the XML is schema-valid. Only `/CheckCanApplyConfigurationExtensions` sees it.
2. **The main configuration is about to be loaded and applied**, and the change touched metadata or module code that the MCP validators did not cover (a whole-snapshot deploy, a large refactor, a release build).

Execution and pass criterion — `content/rules/designer-batch-checks.md`: first bind the current artifact to the checked configuration, then the ladder (`/CheckModules` → `/CheckCanApplyConfigurationExtensions` → `/CheckConfig`), stop at the first failure, and the **three-signal verdict** (process exit code + `/DumpResult` + `/Out` diagnostics). Success phrases neutralize only their own fragment, never other diagnostics on the same line. Warnings fail this gate — `-WarningsAsErrors` will reject the same content at apply time.

Evidence includes the artifact fingerprint and source-to-IB match, target configuration / extension,
platform / modes, process exit code, log path and `/DumpResult` code. Reuse it only while the
artifact and relevant target state still match; a later load or source edit invalidates it.

**When the trigger fired but the gate could not run** (no `PLATFORM_PATH` / `INFOBASE_PATH`, or the base is production and no dev/test copy is available), record one line under **Risks**: *"Gate 6 not run — `<reason>`; extension applicability was not verified against an infobase."* Delivery is not blocked, but an extension change delivered without it must be flagged as unverified against a real base. This gate never substitutes for Gates 1–5.
