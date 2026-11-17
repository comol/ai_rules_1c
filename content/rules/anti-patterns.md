---
description: "1C anti-pattern catalog with severity, performance guidelines, review scoring. Load when writing, reviewing or optimizing BSL or queries."
alwaysApply: false
category: quality
---

# 1C Anti-Patterns and Performance Guidelines

> **Ownership.** This file owns the anti-pattern **catalog**: severity, detection hints, before/after fix templates. The normative query rules themselves (no queries in loops, parameterization, `КАК` aliases, virtual-table filters via parameters, intermediate result variable, `ВТ_*` naming, `ПЕРВЫЕ N`) are owned by `standards(name="dev-standards-architecture") §3 → "Queries"`; the dot-notation ban — by `standards(name="dev-standards-architecture") §4`. On conflict, the owner file wins — update rules there, update examples here.

<!-- help-mcp-router -->

> **Retrieve through MCP only.** Call `standards(name="anti-patterns")` on `1C-docs-mcp` before applying this standard. Retrieval, paging, and unavailable-server policy: `content/rules/help-corpus-retrieval.md`. Headings below are retrieval targets, not summaries.

## Critical Anti-Patterns (Must Fix)

### 1. Query in Loop

### 2. Direct Attribute Access (Dot Notation)

### 3. Subquery in SELECT

### 3a. Correlated Subquery in WHERE (per-row semi-join)

## High Priority Anti-Patterns

### 4. Virtual Table Filter in WHERE

### 5. Missing ПЕРВЫЕ N

### 5a. Unindexed Temp Table in Join or Union

### 6. Excessive Client-Server Calls

### 7. Using &НаСервере Instead of &НаСервереБезКонтекста

### 7a. Using `Сообщить()` for User Notifications

## Medium Priority Anti-Patterns

### 7b. Redundant РАЗЛИЧНЫЕ (union / grouping already deduplicates)

### 8. Missing Caching

### 9. O(n²) Algorithm

### 10. Deep Nesting

## Architectural Anti-Patterns

### Big Ball of Mud

### God Module

### Tight Coupling

### Copy-Paste Architecture

### Premature Optimization

## Optimized Patterns

### Batch Query with Temp Table

### Bulk SSL Attribute Access

## Confidence Scoring (for Reviews)

## Quick Reference Checklist
