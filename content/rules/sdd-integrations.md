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

### Mandatory pre-author checks

Run these **before** writing the artifact when a related server is exposed in the current session — not after, not when reviewing. Skip a check only when its scope is genuinely irrelevant to the artifact, and state why in the artifact (one short sentence under "Context sources" — see below).

1. **Project memory — `1c-templates-mcp` `recall`.** Always run first for any non-trivial spec. Query with the actual identifiers and concepts the spec will use: object names (`НачислениеЗарплаты`, `ПродажиТовары`), subsystem keywords (`ИИ`, `OpenAI`, `HTTP интеграция`), error messages, prior decisions. Catches existing project conventions, prompt templates, naming quirks, settled architectural choices. Missing this step is the most common source of contradictions between specs and reality.
2. **Metadata facts — `1c-graph-metadata-mcp` (`get_object_dossier`, `search_metadata`) → `1c-code-metadata-mcp` fallback.** Every metadata object the spec names — confirm its real attributes, tabular sections, attribute names of those tabular sections, types, and which standard attributes (`Дата`, `ПериодРегистрации`, `МесяцНачисления`, …) actually exist on it. Do not invent attribute names from analogous documents or from memory. Follow the fallback order from `AGENTS.md → Tooling & Standards → A.4` (graph → code-metadata hybrid → `grep=true` retry → `Grep`).
3. **Platform APIs — `1C-docs-mcp` (`docinfo`, `docsearch`) and ITS (`its_help` → `fetch_its`).** Every platform type, method, or behaviour the spec relies on (`HTTPСоединение`, `ЗащищённоеСоединениеOpenSSL`, `ЗаписатьJSON` / `ПрочитатьJSON`, `ДлительныеОперации`, async / `Ждать`, role permissions, etc.) — verify the exact name, signature, and version availability against the project's `CompatibilityMode`. Memory-written API signatures are not evidence.
4. **БСП / SSL — `1c-ssl-mcp` (`ssl_search`).** When the spec mentions integrating with a БСП subsystem (`Администрирование`, `ИнтернетПоддержкаПользователей`, `ПолучениеФайловИзИнтернета`, `ЦифроваяПодпись`, `ДлительныеОперации`, `ОчередьЗаданий`, …), confirm the subsystem actually exists in this project's БСП version, its real name in this configuration, and which public API to call. Does the spec assume a generic settings form mounting point? Verify the БСП hook (`ПриОпределенииПодсистемСКоторымиВозможнаИнтеграция`, `ПриДобавленииЭлементовФормы`, etc.) exists in this БСП version.
5. **Project source patterns — `search_code` / `codesearch` / `search_function`.** When the spec proposes a new module, function, or pattern, check whether the project already has a similar one to align naming, signature, and placement. Saves the implementation phase from re-deciding what the spec should have nailed down.

### Forbidden in OpenSpec artifacts

- **TODO / "to be clarified" / "уточнить" for a fact one MCP call closes.** If you can answer it now via `recall` / `get_object_dossier` / `docinfo` / `ssl_search`, do it now. A TODO is allowed only for facts that genuinely depend on a human decision (business rule, naming preference, priority).
- **Invented metadata or attribute names.** No `Документ.НачислениеЗарплаты.Реквизит` value without metadata confirmation. No tabular-section column name without confirmation.
- **Platform-API signatures written from memory** when the spec is normative (design.md decisions, tasks.md acceptance criteria). Cite the verified source.
- **Cross-version assumptions without `CompatibilityMode` check.** If the spec assumes 8.3.21+ behaviour (async HTTP, `Ждать`, OpenSSL secure connections, structured logging), confirm `openspec/project.md` / `.dev.env` actually targets that version, or scope the spec to the version that is in force.

### Context sources block — mandatory for non-trivial spec authoring

At the end of every non-trivial OpenSpec artifact you author or substantially modify (`proposal.md`, `design.md`, `tasks.md`, delta `specs/`), append a short `## Context sources` block listing the MCP tools actually consulted and what each closed:

```markdown
## Context sources

- `recall` (`1c-templates-mcp`) — searched "<keys>"; found <X notes used> / no relevant notes.
- `get_object_dossier` (`1c-graph-metadata-mcp`) — confirmed shape of `Документ.<Name>` (attributes: …, tabular sections: …).
- `docinfo` (`1C-docs-mcp`) — verified `<TypeOrMethod>` for `CompatibilityMode=<…>`.
- `ssl_search` (`1c-ssl-mcp`) — confirmed БСП subsystem `<Name>` is present (version `<…>`).
- Skipped: `<tool>` — <one-sentence reason: irrelevant scope, server not exposed, evidence already in `openspec/project.md`>.
```

This block is the artifact-level analogue of the "list context sources actually used" rule from `AGENTS.md → Tooling & Standards → A.3`. It is the visible proof that the spec is grounded; its absence on a non-trivial spec is a defect, the same way a missing `syntaxcheck` run is a defect for BSL changes.

### Subagent obligations

The subagents that own OpenSpec artifacts (`1c-analytic`, `1c-architect`, `1c-planner`, `1c-explorer` — see the mapping table below) inherit this discipline. Their prompts in `content/agents/` do not have to repeat these rules; they are bound by this file and by `AGENTS.md`. A subagent that delivers a non-trivial spec without the `Context sources` block, or with a TODO that an exposed MCP tool could have closed, has failed the same way a developer subagent fails if it skips `syntaxcheck`.

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
