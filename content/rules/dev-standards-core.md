---
description: Router for development standards — directs project parameters, BSL style, and modification/naming work to focused companion rules
alwaysApply: false
category: development
---

# Development Standards — Core Router

This file is a compatibility router. It contains no duplicated normative rules. Load only the companion that matches the current task:

| Need | Canonical rule |
|---|---|
| `.dev.env`, deployment / IB parameters, UI tests, subagent models, orchestration, process tuning | [`dev-standards-env.md`](dev-standards-env.md) |
| BSL formatting, quality limits, forbidden constructs, naming, API documentation, typography, comments, internal review | [`dev-standards-code-style.md`](dev-standards-code-style.md) |
| Modification markers, metadata naming, object-type selection | [`dev-standards-change-markers.md`](dev-standards-change-markers.md) |

Existing references to `dev-standards-core.md §N` remain valid through the compatibility headings below. The linked companion is authoritative.

## 1. Project Parameters (.dev.env)

Canonical content: [`dev-standards-env.md §1`](dev-standards-env.md).

### Global principle — no field is globally mandatory

See [`dev-standards-env.md §1`](dev-standards-env.md).

### Code-generation parameters

See [`dev-standards-env.md §1`](dev-standards-env.md).

### Advisory parameters — `PREFIX`, `COMPANY`, `DEVELOPER`

See [`dev-standards-env.md §1`](dev-standards-env.md).

### Infobase / deployment parameters

See [`dev-standards-env.md §1`](dev-standards-env.md).

#### `UI_TESTING` — web UI-testing mode

See [`dev-standards-env.md §1`](dev-standards-env.md).

### Subagent model parameters

See [`dev-standards-env.md §1`](dev-standards-env.md).

#### `ORCHESTRATION` — orchestrator economy mode

See [`dev-standards-env.md §1`](dev-standards-env.md).

### Process-tuning parameters

See [`dev-standards-env.md §1`](dev-standards-env.md).

#### `VERIFICATION_DEPTH` — static code-verification depth

See [`dev-standards-env.md §1`](dev-standards-env.md).

## 2. Code Style (single source of truth — referenced from `AGENTS.md`)

Canonical content: [`dev-standards-code-style.md §2`](dev-standards-code-style.md).

### Formatting

See [`dev-standards-code-style.md §2`](dev-standards-code-style.md).

### Alignment

See [`dev-standards-code-style.md §2`](dev-standards-code-style.md).

### Quality Metrics

See [`dev-standards-code-style.md §2`](dev-standards-code-style.md).

### String Building

See [`dev-standards-code-style.md §2`](dev-standards-code-style.md).

### Forbidden Calls and Constructs

See [`dev-standards-code-style.md §2`](dev-standards-code-style.md).

### Naming

See [`dev-standards-code-style.md §2`](dev-standards-code-style.md).

### Conditions

See [`dev-standards-code-style.md §2`](dev-standards-code-style.md).

### Function Parameters

See [`dev-standards-code-style.md §2`](dev-standards-code-style.md).

## 3. Modification Comments

Canonical content: [`dev-standards-change-markers.md §3`](dev-standards-change-markers.md).

### Format

See [`dev-standards-change-markers.md §3`](dev-standards-change-markers.md).

### Typical Code Modification

See [`dev-standards-change-markers.md §3`](dev-standards-change-markers.md).

### New Procedures in Typical Modules

See [`dev-standards-change-markers.md §3`](dev-standards-change-markers.md).

### Entirely New (Non-Typical) Objects

See [`dev-standards-change-markers.md §3`](dev-standards-change-markers.md).

### General Rules

See [`dev-standards-change-markers.md §3`](dev-standards-change-markers.md).

## 4. Metadata Naming

Canonical content: [`dev-standards-change-markers.md §4`](dev-standards-change-markers.md).

### Object Type Selection

See [`dev-standards-change-markers.md §4`](dev-standards-change-markers.md).

## 5. Procedure/Function Documentation

Canonical content: [`dev-standards-code-style.md §5`](dev-standards-code-style.md).

## 6. Typography

Canonical content: [`dev-standards-code-style.md §6`](dev-standards-code-style.md).

## 7. Comments — OK / NOT OK Examples

Canonical content: [`dev-standards-code-style.md §7`](dev-standards-code-style.md).

### NOT OK — code paraphrase and noise

See [`dev-standards-code-style.md §7`](dev-standards-code-style.md).

### OK — motivation, context, constraints

See [`dev-standards-code-style.md §7`](dev-standards-code-style.md).

### Verification rule

See [`dev-standards-code-style.md §7`](dev-standards-code-style.md).

## 8. Internal Code Review After Each Edit

Canonical content: [`dev-standards-code-style.md §8`](dev-standards-code-style.md).
