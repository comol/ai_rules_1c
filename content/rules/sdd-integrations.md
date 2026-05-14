---
description: "OpenSpec integration. Load when working with the openspec/ workspace (specs and change proposals)."
alwaysApply: false
category: integrations
---

# SDD Integration — OpenSpec

[OpenSpec](https://github.com/Fission-AI/OpenSpec) is the only SDD framework supported by this project. Other SDD frameworks (Memory Bank, Spec Kit, TaskMaster, etc.) are **not** supported — do not generate or update artifacts for them, even if the corresponding folders or MCP servers happen to be present.

## Canonical sources

Layout, spec format, delta format, and the full workflow are described in the workspace itself — do not duplicate them here:

| Topic | File |
|-------|------|
| Workspace layout, slash commands, refresh policy | [`openspec/README.md`](../../openspec/README.md) |
| Spec format and conventions for `openspec/specs/` | [`openspec/specs/README.md`](../../openspec/specs/README.md) |
| Change-proposal layout and delta format for `openspec/changes/` | [`openspec/changes/README.md`](../../openspec/changes/README.md) |

Read those files before writing or editing OpenSpec artifacts.

## MCP discipline for OpenSpec authoring

OpenSpec artifacts (`proposal.md`, `design.md`, `tasks.md`, delta specs under `changes/<id>/specs/` and current specs under `specs/`) are Markdown, but they make **factual claims about the 1C system** — metadata names, attributes, tabular sections, public API signatures, БСП subsystem names, platform-version behaviour, project conventions. Every such claim must be grounded in evidence from the relevant MCP tools, not from memory or guessing. This is the **spec-authoring path** from `AGENTS.md → Development Procedure → Triage`.

### Spec size triage

Before any pre-author MCP call, classify the change. The evidence depth depends on the class — applying the full evidence set to a one-button change is the most common source of context bloat.

- **quick-spec** — change touches **one** existing metadata object **plus**, optionally, 1-3 independent isolated additions (a new constant, a new data processor / settings form, a new independent information register with no module). No new documents / accumulation or accounting registers / roles / event subscriptions / scheduled jobs. No changes to existing transactional paths, RLS conditions, posting code, or public common-module signatures. Naming of new objects is the only architecturally novel decision.
  *Evidence minimum:* targeted attribute check via `resolve_qualified_name` or `search_metadata` JSON template (see check 2 below) **plus** one `ssl_search` if the spec relies on a БСП subsystem **plus** `recall` only if the change keywords overlap with prior project work. `Context sources` block — one line.
- **full-spec** — everything else: new transactional code paths, new registers / documents / roles, modifications to existing posting or write paths, public API signatures, БСП-subsystem integrations beyond a single known API, cross-module impact, performance NFRs, security / PII handling beyond a whitelist. Run the full `Mandatory pre-author checks` below.

When in doubt — quick-spec wins until the second novel architectural decision shows up; then promote to full-spec.

### Mandatory pre-author checks

These checks operate under `AGENTS.md → Tooling & Standards → C` (no duplication, no blind chaining, no defensive calls). **The presumption is in favour of skipping** — include a check only when it materially closes a gap that will affect a concrete `### Requirement:` in the spec. Per `AGENTS.md → A.3`, the `Context sources` block briefly notes any check that **was normally relevant for the change class but deliberately skipped** (one short sentence — see the block format below); checks that fall outside the class baseline (e.g. `recall` on a greenfield topic in a quick-spec) need no mention at all.

Apply these to **full-spec** changes (the `Evidence minimum` of `quick-spec` is enough for quick changes). Run **before** writing the artifact, not after.

1. **Project memory — `1c-templates-mcp` `recall`.** Run when the change keywords overlap with anything already touched in the project: existing object names (`НачислениеЗарплаты`, `ПродажиТовары`), known subsystems (`Документооборот`, `ИнтернетПоддержка`), recurring error messages, prior architectural decisions on the same domain. For genuinely greenfield topics — a domain the project has never touched — `recall` is optional; a single short note in `Context sources` ("`recall` skipped: greenfield topic") is enough. Catches existing project conventions, prompt templates, naming quirks, settled architectural choices.
2. **Metadata facts — prefer targeted queries over full dossiers.** Choose the narrowest method that closes the gap:
   - **Single attribute / tabular-section column existence and type** — `resolve_qualified_name "Документ.<Name>.Реквизит.<Attr>"` (one call, minimal output) or `search_metadata {"operation": "get_attribute_type", ...}`. Use this for "does object X have attribute Y of type T?" — by far the most common case.
   - **List of attributes / tabular parts / dimensions / resources / forms** — `search_metadata` JSON templates: `list_attributes`, `list_tabular_parts`, `list_dimensions`, `list_resources`, `list_forms`, `list_enum_values`, `object_structure`, `list_attributes_with_type`. Deterministic, no LLM, much smaller payload than a dossier.
   - **Structural passport across many facets** — `get_object_dossier object_name=... sections=["structure"]` (or `["structure","dependencies"]`, …). Use the `sections` filter to drop unused facets. Default (all sections) is a last resort for objects the session has never inspected.
   - **Fallback chain on empty / non-actionable results** — `1c-code-metadata-mcp` hybrid → `grep=true` retry → `Grep` (per `AGENTS.md → Tooling & Standards → A.4`).
   Do not invent attribute names from analogous documents or from memory.
3. **Platform APIs — `1C-docs-mcp` (`docinfo`, `docsearch`) and ITS (`its_help` → `fetch_its`).** Every platform type, method, or behaviour the spec relies on (`HTTPСоединение`, `ЗащищённоеСоединениеOpenSSL`, `ЗаписатьJSON` / `ПрочитатьJSON`, `ДлительныеОперации`, async / `Ждать`, role permissions, etc.) — verify the exact name, signature, and version availability against the project's `CompatibilityMode` **when the spec is normative about that API**. Memory-written API signatures are not evidence. Skip for hrestomatic APIs whose shape is fixed across all supported versions and where the spec does not pin a specific signature.
4. **БСП / SSL — `1c-ssl-mcp` (`ssl_search`).** When the spec mentions integrating with a БСП subsystem (`Администрирование`, `ИнтернетПоддержкаПользователей`, `ПолучениеФайловИзИнтернета`, `ЦифроваяПодпись`, `ДлительныеОперации`, `ОчередьЗаданий`, `БезопасноеХранилище`, `ЗащитаПерсональныхДанных`, …), confirm the subsystem actually exists in this project's БСП version, its real name in this configuration, and which public API to call. Verify the БСП hook (`ПриОпределенииПодсистемСКоторымиВозможнаИнтеграция`, `ПриДобавленииЭлементовФормы`, etc.) exists in this БСП version. **Required without exception when the change introduces storage of secrets, tokens, or API keys** (confirm `БезопасноеХранилище` shape) **or touches personal data** (confirm `ЗащитаПерсональныхДанных` hooks).
5. **Project source patterns — `search_code` / `codesearch` / `search_function`.** When the spec proposes a new module, function, or pattern, check whether the project already has a similar one to align naming, signature, and placement. Skip when the new code has no analog in the project (genuinely first-of-its-kind).

**Stop criterion.** Once every `### Requirement:` in the planned spec can be written with concrete object names, attribute names, БСП API names, and platform types — without any `<TBD>` or "to clarify" placeholders — stop calling MCP and start writing. Additional calls are allowed only if a specific gap surfaces during drafting. Repeating a check "just to be safe" violates `AGENTS.md → Tooling & Standards → C.1`.

### Forbidden in OpenSpec artifacts

- **TODO / "to be clarified" / "уточнить" for a fact one MCP call closes.** If you can answer it now via `recall` / `resolve_qualified_name` / `search_metadata` / `docinfo` / `ssl_search`, do it now. A TODO is allowed only for facts that genuinely depend on a human decision (business rule, naming preference, priority).
- **Invented metadata or attribute names.** No `Документ.НачислениеЗарплаты.Реквизит` value without metadata confirmation. No tabular-section column name without confirmation.
- **Platform-API signatures written from memory** when the spec is normative (design.md decisions, tasks.md acceptance criteria). Cite the verified source.
- **Cross-version assumptions without `CompatibilityMode` check.** If the spec assumes 8.3.21+ behaviour (async HTTP, `Ждать`, OpenSSL secure connections, structured logging), confirm `openspec/project.md` / `.dev.env` actually targets that version, or scope the spec to the version that is in force.
- **Defensive MCP calls without a concrete gap.** Calling `get_object_dossier` "for completeness" when a single `resolve_qualified_name` would close the only open question — same defect as a missing call.

### Context sources block — compact, evidence-only

At the end of every non-trivial OpenSpec artifact you author or substantially modify (`proposal.md`, `design.md`, `tasks.md`, delta `specs/`), append a short `## Context sources` block. It lists what was actually used and what each call closed, plus a one-sentence note for any check that **was normally relevant for the change class but deliberately skipped**. Out-of-class checks (e.g. БСП check on a change that touches no БСП subsystem) get no mention. **No MCP server names when they are obvious from the tool name, no narration, no "Skipped: X — irrelevant scope" filler for tools that were never going to be called.**

Compact form — preferred default, fits most quick-spec and small full-spec changes:

```markdown
## Context sources
Verified via MCP: `Документы.НачислениеЗарплаты.Комментарий` (Строка, 1024); БСП `ДлительныеОперации` v3.1.10; БСП `БезопасноеХранилище` available.
```

Multi-line form — only when more than 5 confirmations are listed, or when a single confirmation requires a comment (version incompatibility, non-standard behaviour, deliberate scoping). Group by what was confirmed, not by which tool returned it:

```markdown
## Context sources

- Metadata: `Документы.НачислениеЗарплаты.Комментарий` (Строка, 1024); standard `Дата`, `Организация`, `МесяцНачисления` present.
- БСП: `ДлительныеОперации` v3.1.10, `БезопасноеХранилище` v3.1.10 — both available in target version.
- Platform: `HTTPСоединение.ОтправитьДляОбработки` available at `CompatibilityMode=Версия8_3_21`.
- Project memory: no prior notes on AI / OpenAI integration in this configuration (greenfield).
```

This block is the artifact-level analogue of the "list context sources actually used" rule from `AGENTS.md → Tooling & Standards → A.3`. Its absence on a non-trivial spec is a defect, the same way a missing `syntaxcheck` run is a defect for BSL changes. Bloating it with skipped-tool entries or per-call narration is the opposite defect — it carries noise into every downstream phase that re-reads the artifact.

### Subagent obligations

The subagents that own OpenSpec artifacts (`1c-analytic`, `1c-architect`, `1c-planner`, `1c-explorer` — see the mapping table below) inherit this discipline. Their prompts in `content/agents/` do not have to repeat these rules; they are bound by this file and by `AGENTS.md`. A subagent that delivers a non-trivial spec without the `Context sources` block, or with a TODO that an exposed MCP tool could have closed, has failed the same way a developer subagent fails if it skips `syntaxcheck`.

## Apply-phase clarification discipline

`/opsx:apply` runs against an already-approved set of artifacts (`proposal.md`, `design.md`, `tasks.md`, deltas under `changes/<id>/specs/`). **Their decisions are locked.** Apply implements them, it does not re-litigate them.

The recurring failure mode at apply time is the parent agent re-asking the user about choices that `design.md` or `proposal.md` already records — placement (main configuration vs. extension), provider, data scope, settings storage, key handling, transactional boundaries, error-handling pattern, logging strategy. Each such re-ask wastes a user round-trip, drifts the implementation away from the agreed design, and signals that the artifacts are not trusted as the source of truth.

### Read first, then ask

`/opsx:apply` step 4 already mandates reading the context files (`proposal.md`, `design.md`, `tasks.md`, current deltas). **Use them.** Before raising any clarification at apply time, check whether the question is already answered:

- a stated decision in `design.md` (architecture, placement, storage choice, transactional boundaries, error-handling pattern, logging strategy, library / БСП subsystem) — **locked**;
- a stated requirement in a delta `spec.md` (`### Requirement:` block, scenarios) — **locked**;
- a stated `Out of scope` / `Non-goals` / `Constraints` line — **locked**;
- a stated provider / library / default in `proposal.md` (including default values for empty optional parameters) — **locked**;
- the `## Open Questions` block in `design.md` — **only those** items are legitimate apply-time questions, and only when the implementation step that depends on them is actually next on the queue.

If the answer is in the artifacts, do not ask. Quote the locked decision in one line ("`design.md → ## Architecture decisions → "Размещение в основной конфигурации"` — proceeding accordingly") and continue. Disagreeing with a locked decision is **not** a clarification — it is a request to amend `design.md` / `proposal.md`, and the user must explicitly authorize the amendment before any implementation deviates from the artifact.

### Legitimate apply-phase pauses

A pause-and-ask block is justified **only** when one of the following holds:

- **`.dev.env` blocker** — a field actually required by an upcoming task is empty (`PREFIX`, `COMPANY`, `DEVELOPER`, `INFOBASE_PATH`, `IB_USER`, `INFOBASE_PUBLISH_URL`, `PLATFORM_VERSION`, `PLATFORM_PATH`). Ask only about fields blocking tasks scheduled in this run; do not gather all empties up front "for completeness". Asking about an empty `INFOBASE_PATH` when block 9 (deploy / smoke tests) is not yet in scope is premature.
- **Open question listed in `design.md → ## Open Questions`**, and the corresponding implementation step is next.
- **New fact surfaced from the live state** — the implementation revealed something not foreseen at design time (a metadata object missing from this configuration, a platform-version mismatch with `CompatibilityMode`, a typical-form structure that blocks the planned approach, a БСП subsystem missing in this configuration). State the new fact and its conflict with the artifact concretely; this is a `CONFUSION` block per `AGENTS.md → 1.`, not a generic clarification.
- **User-explicit re-open** — the user asks to revisit a previously locked decision.

Anything outside these four categories is an apply-phase defect, equivalent to skipping `syntaxcheck` after a BSL edit.

### Forbidden at apply time

- Re-asking about provider / trigger / data scope / settings storage / placement / key storage / module placement / role grants / БСП subsystem / transactional boundaries when the question is settled in `proposal.md` or `design.md`.
- Bundling a `.dev.env` audit with locked-decision re-ask — they are different gates and must be split. The `.dev.env` audit asks about empty fields **only**.
- Asking "what to do with default X" when `design.md` already names the default. Use the named default.
- Pausing on a non-blocking item just to "confirm" — confirmation is not a question. If the artifact says X, do X.
- Asking the user to choose between options A / B / C when `design.md → ## Architecture decisions` already picked one of them with a written rationale — the choice is closed, the rationale is the answer.

### Apply-phase opening template (default)

To make the discipline above mechanical, the parent agent's first message at `/opsx:apply` follows this structure:

```text
Using change: <name>.

## Locked from artifacts (proceeding without re-asking)
- <decision>: <one-line value> — `<file>:<section>`
- ...

## Genuine blockers (must resolve before proceeding)
- <empty .dev.env field needed by next task> — required by tasks <ids>
- <design.md Open Question that is next on the queue> — quoted
- <new fact surfaced now that conflicts with the artifact> — CONFUSION block
- ...

## Plan for this session
- <ordered list of task ids that will be executed in this run>
```

The "Locked from artifacts" block is non-negotiable — its absence on a non-trivial `/opsx:apply` is a defect. The "Genuine blockers" block is empty when nothing legitimate is open; in that case the parent proceeds straight to implementation without a question round at all.

## Subagent → OpenSpec artifact mapping

Each subagent owns specific OpenSpec artifacts. Use this table to decide where a given subagent must write.

| Subagent | Reads | Writes |
|----------|-------|--------|
| **1c-explorer** | `specs/`, current codebase, metadata graph | read-only findings for `proposal.md`, `design.md`, or `tasks.md` authors; no artifact writes |
| **1c-analytic** | existing `specs/` for context | `changes/<id>/proposal.md`, new entries under `specs/` (via deltas) |
| **1c-planner** | `specs/`, `changes/<id>/proposal.md`, `design.md` | `changes/<id>/tasks.md` |
| **1c-architect** | `specs/`, `changes/<id>/proposal.md` | `changes/<id>/design.md` |
| **1c-arch-reviewer** | `changes/<id>/design.md`, `proposal.md`, `specs/` | review notes (no artifact writes) |
| **1c-developer** | `specs/`, active `changes/<id>/` | code; updates `changes/<id>/specs/` deltas and ticks `tasks.md` |
| **1c-metadata-manager** | `specs/`, active `changes/<id>/` | metadata XML/forms; spec deltas under `changes/<id>/specs/` for new/changed metadata objects |
| **1c-refactoring** | `specs/`, active `changes/<id>/` | code; updates deltas only when observable behaviour changes |
| **1c-performance-optimizer** | `specs/` (NFR/perf requirements) | code; deltas only when a perf NFR changes |
| **1c-error-fixer** | active `changes/<id>/` | code; usually no spec changes (bug fix preserves intended behaviour) |
| **1c-tester** | `specs/` (scenarios), `changes/<id>/tasks.md` | test results, ticks in `tasks.md` |
| **1c-code-reviewer** | `specs/`, `changes/<id>/specs/` deltas | review verdict against requirements (no artifact writes) |
| **1c-doc-writer** | `specs/`, `changes/archive/` | user-facing docs derived from specs |

## Phase → subagent mapping

The default `propose → apply → archive` workflow maps to subagents as follows:

| Phase | Driver subagent(s) | Output |
|-------|-------------------|--------|
| Exploration | `1c-explorer` when broad code / metadata context is needed | read-only findings for the next phase |
| Requirements | `1c-analytic` | `proposal.md` + initial deltas under `changes/<id>/specs/` |
| Design | `1c-architect` (optionally reviewed by `1c-arch-reviewer`) | `design.md` |
| Planning | `1c-planner` | `tasks.md` |
| Implementation | `1c-developer`, `1c-metadata-manager`, `1c-refactoring`, `1c-performance-optimizer`, `1c-error-fixer` | code + updated deltas + ticked `tasks.md` |
| Verification | `1c-tester`, `1c-code-reviewer` | test results, review verdict |
| Documentation & archive | `1c-doc-writer`, then `/opsx:archive` | user docs; deltas merged into `specs/`, change moved to `changes/archive/` |
