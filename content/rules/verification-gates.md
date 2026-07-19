---
description: Verification execution gates for BSL and metadata — evidence reuse, syntax, logic, style, impact analysis, and XML validation
alwaysApply: false
category: quality
---

# Verification Gates — BSL, Impact, and Metadata

**When to load this file:** before validating or declaring a BSL / metadata change done. Determine depth and promotion triggers first via `verification-policy.md`.

Delivery-only soft gates and the final report contract live in `verification-delivery.md`.

## Gate execution and evidence reuse

A gate is a requirement for the current artifact state, not a request to call the same tool
again. The agent that makes the final edit to an artifact owns its applicable validator run and
records the artifact path, validator result and run count in the handoff / implementation report.

The parent closing gate MUST reuse that evidence when it was produced after the latest edit.
It runs only missing or stale gates and MUST NOT repeat a validator against unchanged content
(`AGENTS.md → MCP Tool Calling → C.2`). Any later edit invalidates the affected validator
evidence; the final editor becomes the new owner. The same rule applies to `verify_xml` and
impact-analysis evidence.


## Hard gates — run on every full-cycle change

You MUST run all five gates in order. Each gate has an explicit pass / fail criterion and an explicit retry budget. When a required validator is not exposed in the current session, follow the graceful-degradation subsections (after Gate 3 and inside Gate 4) instead of silently skipping.

The gate descriptions below state the `full` (default) behaviour. When `VERIFICATION_DEPTH` is `standard` or `lite`, Gates 1–3 are modulated per `verification-policy.md → "Verification depth levels"` — but a full-cycle change on any promotion-trigger path always runs the complete chain regardless of the level (the safety floor).

### Gate 1 — Syntax (`syntaxcheck`)

- Run `syntaxcheck` on every touched `.bsl` module. No exceptions.
- Pass criterion: zero `error` items. `warning` items are reviewed in Gate 3.
- Retry budget: canon — `AGENTS.md → MCP Tool Calling → B.1`. An `error` is blocking: after fixing it, obtain a clean confirming run on the changed module. Under `full`, allow 3 calls total; under `standard`, 2. If the limit is exhausted without a clean pass on the latest state, Gate 1 fails. Gates 2 and 3 use the same policy with their own blocking severities.

### Gate 2 — Logic & performance (`check_1c_code`)

- Run on every touched module. Always after Gate 1 passes — never before, otherwise the AI checker drowns in syntax noise.
- Pass criterion: no `critical` or `error` severity items.
- `warning` items: triage. Inside-scope warnings (introduced by your change) — fix. Pre-existing warnings outside your scope — leave alone (Surgical Changes).
- AI non-determinism rule: if `check_1c_code` returns inconsistent results across runs on the **same** code, do not loop on it. Take the strictest result, fix what is fixable, document the rest.

### Gate 3 — Style & ITS compliance (`review_1c_code`)

- Run on every touched module after Gate 2 passes.
- Pass criterion: no `error` severity items.
- `warning` items: same triage rule as Gate 2.
- For specific warnings that are intentional and justified: add a `//BSLLS:<rule>` suppression with a 1-line explanation, per `dev-standards-code-style.md → "Formatting"`. Blanket suppressions without justification are forbidden.

### Graceful degradation for Gates 1–3 — when a validator is not exposed

Gates 1–3 are mandatory only when the corresponding validator is exposed in the current session (`AGENTS.md → MCP Tool Calling → A.1`: a server counts as available only when its tools are visible in the tool schema). When a validator is missing, do **not** silently skip its gate:

1. Record the fact in the delivery summary under **Risks** as a fixed line: *"Gate N skipped — `<tool>` (`<server>`) not exposed in this session."*
2. Compensate with what is available: for Gate 1 — a careful manual syntax review of every touched module (paired keywords, directives, parameter lists); for Gates 2–3 — the internal review checklist from `dev-standards-code-style.md §8` (style, readability, correctness, edge cases, security, concurrency / locks / transactions).
3. Delivery is not blocked, but a transactional / metadata / public-API change that went through without Gate 2 must be flagged as needing a follow-up validation run in a session where the server is exposed.

Skipping a gate without recording it under Risks is a defect — the same rule as Gate 4's graceful degradation below.

### Gate 4 — Impact analysis (only when public surface changed)

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

- **`verify_xml`** on every modified XML file. Pass criterion: zero schema violations.
- For non-trivial metadata edits (new objects, attributes, tabular sections, forms): prefer the `1c-metadata-manage` skill over hand-edited XML. If hand edits were used, additionally cross-check `metadata-xml-workarounds.md` for the recurring traps (LineNumber, PagesGroupExtInfo, Page.enabled, UID uniqueness).
- For `Form.xml` edits: also confirm the form opens in Configurator without warnings — schema validity is necessary but not sufficient.
