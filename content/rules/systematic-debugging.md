---
description: "Debugging 1C defects — runtime errors, regressions, wrong results, slowdowns, DEBUG_FAST_PATH. Load before diagnosing a bug, directly or through 1c-error-fixer / 1c-performance-optimizer."
alwaysApply: false
category: quality
---

# Systematic Debugging — 1C Adaptation

**When to load this file:** any task that involves diagnosing a bug, runtime error, regression, performance regression, or unexpected behavior — whether the parent agent is debugging directly or delegating to the `1c-error-fixer` / `1c-performance-optimizer` subagent.

**Goal:** replace ad-hoc trial-and-error with a structured root-cause loop. Skipping a phase is a defect — unless the bug qualifies for the **fast path** below, which is a documented shortcut, not a skipped phase.

The methodology is adapted from the `systematic-debugging` skill of [obra/superpowers](https://github.com/obra/superpowers) and combined with 1C platform mechanics (debugger, `ЖурналРегистрации`, `ОтчетПоЖурналуРегистрации`, `ПоказатьЗначение`, `СообщитьПользователю`, `Replay` of background jobs, technological log).

<!-- help-mcp-router -->

> **Retrieve through MCP only.** Call `standards(name="systematic-debugging")` on `1C-docs-mcp` before applying this standard. Retrieval, paging, and unavailable-server policy: `content/rules/help-corpus-retrieval.md`. Headings below are retrieval targets, not summaries.

## Core principle

## Fast path — for directly evidenced root causes

## The four phases (full loop)

### Phase 1 — Reproduce

### Phase 2 — Hypothesize

### Phase 3 — Experiment

### Phase 4 — Fix

## Anti-patterns

## Process flow

## Companion rules
