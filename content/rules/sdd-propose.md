---
description: "OpenSpec propose phase — DoD in the artifacts, MCP evidence for 1C facts, spec size triage, clarification before apply. Load for /opsx:propose, /opsx:update or when authoring proposal.md, design.md, tasks.md or delta specs."
alwaysApply: false
category: integrations
---

# OpenSpec — propose phase

Router, artifact ownership and the Definition of Done contract — `content/rules/sdd-integrations.md`. Formats: read `openspec/specs/README.md` and `openspec/changes/README.md` before writing or editing an artifact. Apply-phase rules live in `content/rules/sdd-apply.md` and are not needed while proposing.

## Specify completion before apply

- Delta specs MUST state observable acceptance criteria in requirements and scenarios, including relevant negative / boundary cases. Each affected requirement carries a **Definition of Done** verification criterion (method and expected result) inside its requirement block, so sync/archive preserves it with the requirement.
- `proposal.md` MUST contain `## Definition of Done`: a checklist of criterion IDs linked to those requirements/scenarios, applicable validation gates, behavioural confirmation (UI evidence for criteria that require it), and a final review with no unresolved blocking findings. Name the verification method, expected result and required environment; a list of commands without expected outcomes is insufficient.
- `tasks.md` MUST include implementation, verification (gates and behavioural confirmation), review, any necessary fixes, and final DoD reconciliation. Link verification tasks to criterion IDs. Plan scenarios with inputs/actions, expected outcomes and an allowed verification method; test planning is supported.
- An explicit user waiver of UI confirmation or review MUST be recorded with its source, scope and affected criterion IDs in the DoD and corresponding task. Waiving one does not waive the other or mandatory validator/security/metadata gates. Record it as `waived by user`, never `passed`. A depth setting, `UI_TESTING=off`, disabled reviewer subagent, missing tools or missing environment is not a waiver.

Reusable test authoring and execution workflows are available through `content/skills/1c-business-tests/SKILL.md` and `content/skills/1c-ui-regression/SKILL.md`. The model chooses them when persistent coverage adds value; they are not an implicit full-cycle obligation and need no explicit skill invocation. Reuse a verified project framework/runner; the ruleset does not bundle a test framework, browser or test extension. Missing dependencies leave execution unverified. Whether a saved suite is useful or not, compare expected and actual outcomes through an applicable infobase check (Gate 3a) or UI confirmation under `UI_TESTING`. Static validators and review are separate evidence; neither alone proves runtime behaviour. UI-specific criteria require UI evidence unless explicitly waived; disabling UI does not waive other checks. Skill selection does not authorize deployment or data mutations.

When eligible `1c-data-mcp` capabilities are available, plan focused result checks wherever they close a concrete correctness gap; execute them during apply verification under Gate 3a's read-only dev/test scope. `UI_TESTING=off`, a lower verification depth or economy orchestration does not disable these checks. The absence of a test-suite framework is not a reason to omit them.

Propose is ready only when each criterion has a verification task and executable acceptance conditions. Preserve this mapping during `/opsx:update`; do not weaken approved criteria to fit the implementation. If an older change lacks DoD or verification tasks, derive them from its approved requirements and this contract before apply. Ask only when that exposes a material unresolved decision; adding the required checks alone needs no new approval.

## MCP discipline for OpenSpec authoring

OpenSpec artifacts (`proposal.md`, `design.md`, `tasks.md`, delta and current specs) are Markdown, but they make **factual claims about the 1C system** — metadata names, attributes, tabular sections, public API signatures, БСП subsystems, platform-version behaviour, project conventions. Every such claim must be grounded in MCP evidence, not memory or guessing. This is the **spec-authoring path** from `AGENTS.md → Development Procedure → Triage`.

### Spec size triage

Classify the change before any pre-author MCP call — evidence depth depends on the class; applying the full evidence set to a one-button change is the most common source of context bloat.

- **quick-spec** — touches **one** existing metadata object plus, optionally, 1-3 independent isolated additions (a constant, a data processor / settings form, an independent information register with no module). No new documents / accumulation or accounting registers / roles / event subscriptions / scheduled jobs; no changes to existing transactional paths, RLS conditions, posting code, or public common-module signatures; naming of new objects is the only architecturally novel decision.
  *Evidence minimum:* targeted attribute check (`resolve_qualified_name` or a `search_metadata` JSON template — check 2 below) **plus** one `ssl_search` if the spec relies on a БСП subsystem **plus** `recall` only if the change keywords overlap prior project work. `Context sources` block — one line.
- **full-spec** — everything else: new transactional code paths, new registers / documents / roles, modified posting or write paths, public API signatures, БСП integrations beyond a single known API, cross-module impact, performance NFRs, security / PII handling. Run the full pre-author checks below.

When in doubt — quick-spec wins until the second novel architectural decision shows up; then promote to full-spec.

### Mandatory pre-author checks

Run **before** writing the artifact, under `AGENTS.md → MCP Tool Calling → C` (no duplication, no blind chaining, no defensive calls). **The presumption is in favour of skipping** applies to these spec-authoring checks, not to the helper-reuse search during implementation (`coding-standards.md → Check reuse before a new helper`). Include a pre-author check only when it materially closes a gap that affects a concrete `### Requirement:`. Per `mcp-policy.md → A.3`, the `Context sources` block briefly notes (one short sentence) any check that was normally relevant for the change class but deliberately skipped; out-of-class checks need no mention.

1. **Project memory — `recall`** (search all connected providers per `content/rules/project-memory.md`) — when the change keywords overlap anything already touched in the project: existing object names, known subsystems, recurring error messages, prior decisions on the same domain. Greenfield topics: optional; a short "`recall` skipped: greenfield topic" note is enough.
2. **Metadata facts — narrowest query first.** Single attribute / column existence and type — `resolve_qualified_name "Документ.<Name>.Реквизит.<Attr>"` or `search_metadata {"operation": "get_attribute_type", ...}` (by far the most common case). Lists of attributes / tabular parts / dimensions / resources / forms — `search_metadata` JSON templates (`list_attributes`, `object_structure`, `list_enum_values`, …): deterministic, much smaller payload than a dossier. Multi-facet passport — `get_object_dossier` with a `sections` filter; the all-sections default is a last resort. On empty / non-actionable results — fallback chain per `mcp-policy.md → A.4`. Never invent attribute names from analogous documents or from memory.
3. **Platform APIs — `docinfo` / `docsearch` (`1C-docs-mcp`), ITS `its_help` → `fetch_its`.** Verify the exact name, signature, and version availability against the project's `CompatibilityMode` for every platform type / method the spec is normative about. Skip for hrestomatic APIs whose shape is fixed across supported versions when the spec does not pin a signature.
4. **БСП / SSL — `ssl_search` (`1c-ssl-mcp`).** When the spec mentions a БСП subsystem: confirm it exists in this project's БСП version, its real name in this configuration, and which public API / hook to call. **Required without exception** when the change stores secrets / tokens / API keys (confirm `БезопасноеХранилище`) or touches personal data (confirm `ЗащитаПерсональныхДанных`).
5. **Project source patterns — `search_code` / `codesearch` / `search_function`.** When the spec proposes a new module, function, or pattern — align naming, signature, and placement with an existing analog. Skip when genuinely first-of-its-kind.

**Stop criterion.** As soon as every `### Requirement:` can be written with concrete object, attribute, БСП, and platform names — no `<TBD>`, no "to clarify" — stop calling MCP and start writing. Additional calls only when a specific gap surfaces during drafting; repeating a check "just to be safe" violates `mcp-policy.md → C.1`.

### Forbidden in OpenSpec artifacts

- **TODO / "to be clarified" / "уточнить" for a fact one MCP call closes.** Close it now. A TODO is allowed only for facts that genuinely depend on a human decision (business rule, naming preference, priority).
- **Invented metadata or attribute names** — nothing lands without metadata confirmation.
- **Platform-API signatures written from memory** where the spec is normative — cite the verified source.
- **Cross-version assumptions without a `CompatibilityMode` check** — if the spec assumes 8.3.21+ behaviour (async HTTP, `Ждать`, OpenSSL, structured logging), confirm the target version or scope the spec to the version in force.
- **Defensive MCP calls without a concrete gap** — a dossier "for completeness" when one `resolve_qualified_name` closes the only open question is the same defect as a missing call.

### Context sources block — compact, evidence-only

Every non-trivial artifact you author or substantially modify ends with a short `## Context sources` block: what was actually confirmed, plus a one-sentence note per deliberately skipped in-class check. No server names when obvious from the tool name, no narration, no "Skipped: X — irrelevant scope" filler.

Compact form — the default:

```markdown
## Context sources
Verified via MCP: `Документы.НачислениеЗарплаты.Комментарий` (Строка, 1024); БСП `ДлительныеОперации` v3.1.10; БСП `БезопасноеХранилище` available.
```

Multi-line form — only when more than 5 confirmations are listed or one confirmation needs a comment (version incompatibility, deliberate scoping); group by what was confirmed, not by which tool returned it.

A missing block on a non-trivial spec is a defect, the same way a missing `syntaxcheck` run is a defect for BSL; bloating it with skipped-tool noise is the opposite defect.

### Subagent obligations

The subagents that own OpenSpec artifacts (`1c-analytic`, `1c-architect`, `1c-planner`, `1c-explorer` — `sdd-integrations.md → Subagent → OpenSpec artifact mapping`) inherit this discipline via this file and `AGENTS.md`; their prompts do not repeat it. Delivering a non-trivial spec without the `Context sources` block, or with a TODO an exposed MCP tool could have closed, is a failure.

## Propose-phase clarification discipline

Questions belong here, not in apply: by the time code is being written, the user must not be paying a clarification tax that belonged at design time. This project is stricter than the bundled OpenSpec propose skill about asking:

- **Architecturally meaningful and ambiguous — ask the user now.** Meaningful = the choice changes `design.md → ## Architecture decisions`, the shape of a delta requirement, a public export signature or other user-visible naming (metadata objects, public API exports), a scope edge, placement (main configuration vs extension), secrets / settings storage, role shape, transactional boundaries, error-handling pattern, logging strategy, the БСП subsystem, a performance NFR, or the platform-version target. Ask via the `CONFUSION` format from `AGENTS.md → Development Procedure → 1. Think Before Coding` — options with trade-offs, no prose paraphrase.
- **A default the user is unlikely to care about — pin it in `design.md` with a one-line rationale and proceed** (cache policy without an NFR, a private helper name, an internal module split).
- **Depends on a 1C fact — make the MCP call, do not ask.** The user is not a substitute for `resolve_qualified_name` / `search_metadata` / `ssl_search` / `recall`.
- **Already answered — do not ask:** the answer is in `openspec/specs/**`, `memory.md` or `.dev.env`, or the user explicitly said "you decide".

### Pre-finalization clarification gate

Before the final propose summary, run a consolidation pass:

1. Every `### Requirement:` in delta `specs/` and every `design.md` decision — does the implementer need any further user input to code it? If yes → add to a single batched list.
2. `proposal.md → Constraints / Out of scope / Non-goals` — any edge ambiguous enough to be crossed accidentally? Sharpen the wording or batch a clarification.
3. Every `tasks.md` task — executable from the artifacts alone? Every DoD criterion mapped to a gate/behavioural-confirmation/review task or explicit waiver? Any "no" → close the gap or batch genuinely missing input.
4. `design.md → ## Open Questions` — close now everything closable; leave only items that genuinely depend on later facts.
5. Non-empty batch → one consolidated question round → apply the answers to the artifacts → re-run the gate. Repeat until the batch is empty.

Only then may the summary declare the artifacts ready for implementation.

### Forbidden in proposal artifacts

- "TODO: clarify with the user during apply" / "уточнить при реализации" — decide now with the user, or capture a numbered `## Open Questions` item with the exact future question, the artifact section it will update, and the dependent task ID.
- "We'll decide once we see the code" — write a **trigger condition** instead ("if `Документы.<Name>.<Attr>` resolves to type X then path A, else path B").
- Vague verbs in delta `### Requirement:` blocks — "appropriately", "if needed", "as required", "по необходимости" — each hides a question; replace with concrete criteria or escalate to a clarification round.
- Phantom defaults — two equally weighted options ("Cache size: 100 or 500") without a written rationale. Pick one, write the rationale in `design.md`, move on.

### Open Questions discipline

`design.md → ## Open Questions` is the **only** allowed bridge from propose to apply. One numbered item per question: the exact question text, ≥2 options with consequences, the artifact section that will be updated, the dependent task ID(s). An item belongs here only if **all** of: no currently exposed MCP call can close it; the user genuinely cannot answer at propose time (the fact surfaces later — production data, measurements, a not-yet-implemented module's shape); leaving it open does not block authoring the rest of the spec. "I forgot to ask" / "let's see what apply finds" are propose-phase failures, not Open Questions.
