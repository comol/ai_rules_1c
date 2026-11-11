---
description: "OpenSpec integration — router: phase files, canonical sources, Definition of Done mapping, artifact ownership. Load before OpenSpec work (/opsx:* or an openspec/changes/<id>/ change), then the file of the phase."
alwaysApply: false
category: integrations
---

# SDD Integration — OpenSpec

[OpenSpec](https://github.com/Fission-AI/OpenSpec) is the only SDD framework supported by this project. Do not generate or update artifacts for other SDD frameworks (Memory Bank, Spec Kit, TaskMaster, …), even if their folders or MCP servers happen to be present.

This file applies when the task works with OpenSpec — an `/opsx:*` command, an existing `openspec/changes/<id>/` change, or an explicit request for an OpenSpec artifact. The mere presence of an `openspec/` folder does not make an ordinary change an OpenSpec change.

## Phase routing

Load the file of the phase you are in; neither is needed for the other phase.

| Phase | Load |
|---|---|
| `/opsx:propose`, `/opsx:update`, authoring or revising `proposal.md` / `design.md` / `tasks.md` / delta specs (the spec-authoring path of `AGENTS.md → Triage`) | `content/rules/sdd-propose.md` — DoD in the artifacts, MCP evidence for 1C facts, clarification before apply |
| `/opsx:apply`, `/opsx:archive`, `/opsx:sync`, implementing or closing a change | `content/rules/sdd-apply.md` — apply until DoD is satisfied, locked decisions, the single preflight round |

Clarification questions are **front-loaded** into propose, batched into a single preflight round at apply start, and near-zero during the apply loop: a question that **could** have been asked in propose and **could** have been batched into preflight **must not** be asked mid-loop.

## Canonical sources

Layout, spec format, delta format, and the full workflow are described in the workspace itself — do not duplicate them here:

| Topic | File |
|-------|------|
| Spec format and conventions for `openspec/specs/` | [`openspec/specs/README.md`](../../openspec/specs/README.md) |
| Change-proposal layout and delta format for `openspec/changes/` | [`openspec/changes/README.md`](../../openspec/changes/README.md) |

Read those two files before writing or editing OpenSpec artifacts. [`openspec/README.md`](../../openspec/README.md) is an overview for people (layout, slash commands, refresh policy) and is not required reading.

## Full-cycle Definition of Done

When a full-cycle change runs through OpenSpec, `propose → apply → archive` means specify → implement, verify and review → archive, and the artifacts carry the contract of `verification-delivery.md → Full-cycle Definition of Done`: criteria with expected-vs-actual evidence, the hard gates on the final state, the final review, statuses `passed` / `failed` / `blocked/unverified` / `waived by user`, waivers only from the user. The contract applies whether the parent implements directly or delegates. Propose writes it into the artifacts (`sdd-propose.md → Specify completion before apply`); apply is complete only when it is satisfied (`sdd-apply.md → Apply until DoD is satisfied`). A full-cycle change without OpenSpec artifacts follows `verification-delivery.md` directly; quick-fix and docs-fix keep their own triage gates.

## Subagent → OpenSpec artifact mapping

Each subagent owns specific OpenSpec artifacts. Use this table to decide where a given subagent must write. Approved delta specs change only through `/opsx:update`: an implementation subagent reports a needed change, it does not edit the delta to match its code.

| Subagent | Reads | Writes |
|----------|-------|--------|
| **1c-explorer** | `specs/`, current codebase, metadata graph | read-only findings for `proposal.md`, `design.md`, or `tasks.md` authors; no artifact writes |
| **1c-analytic** | existing `specs/` for context | `changes/<id>/proposal.md`, new entries under `specs/` (via deltas) |
| **1c-planner** | `specs/`, `changes/<id>/proposal.md`, `design.md` | `changes/<id>/tasks.md` |
| **1c-architect** | `specs/`, `changes/<id>/proposal.md` | `changes/<id>/design.md` |
| **1c-arch-reviewer** | `changes/<id>/design.md`, `proposal.md`, `specs/` | review notes (no artifact writes) |
| **1c-developer** | `specs/`, active `changes/<id>/` | code; ticks `tasks.md`; reports to the parent any delta change the implementation needs |
| **1c-metadata-manager** | `specs/`, active `changes/<id>/` | metadata XML/forms; reports to the parent the delta changes that new or changed metadata objects need |
| **1c-refactoring** | `specs/`, active `changes/<id>/` | code; reports to the parent when observable behaviour changes |
| **1c-performance-optimizer** | `specs/` (NFR/perf requirements) | code; reports to the parent when a perf NFR changes |
| **1c-error-fixer** | active `changes/<id>/` | code; usually no spec changes (bug fix preserves intended behaviour) |
| **1c-tester** | `specs/` (scenarios), `changes/<id>/tasks.md` | test results for the parent, who ticks `tasks.md` (the tester has no write tools) |
| **1c-code-reviewer** | `specs/`, `changes/<id>/specs/` deltas | review verdict against requirements (no artifact writes) |
| **1c-doc-writer** | `specs/`, `changes/archive/` | user-facing docs derived from specs |

## Phase → subagent mapping

Subagent **selection** is owned elsewhere — do not duplicate it here: the catalog in `content/rules/subagents.md` and the stage-by-stage choice lists in `content/rules/subagent-pipeline.md`. The default `propose → apply → archive` workflow maps onto those stages directly; artifact ownership is fixed by the table above. OpenSpec-specific additions:

- **Verification phase** — full-cycle verification and review follow the DoD above; the parent owns them unless delegated. `1c-tester` runs UI tests only when `UI_TESTING` allows it (`dev-standards-env.md`); `1c-code-reviewer` still requires an explicit request and the reviewer model gate.
- **Documentation & archive phase** — `1c-doc-writer` derives user docs from `specs/`; then `/opsx:archive` merges deltas into `specs/` and moves the change to `changes/archive/`.
- **Revising a change** — `/opsx:update` is the sanctioned way to reopen a locked decision: it revises the change's planning artifacts, and the new content follows the Propose-phase rules (ask up front, confirm every concrete 1C fact through MCP) before apply resumes. `/opsx:sync` merges delta specs into `specs/` without archiving; the same traceability and fact-confirmation rules as for `/opsx:archive` apply.
