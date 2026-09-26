---
description: Managed locks, transaction boundaries, lock ordering, deadlock prevention, lock modes. Load when designing posting or multi-document operations, debugging lock conflicts, or extending a transactional path.
alwaysApply: false
category: quality
---

# Locks and Transactions — Design Rules

The 1C platform offers two locking subsystems (automatic / managed) and an implicit-transaction model around object writes. Most production lock incidents come from mixing the two, opening unintended transactions, or holding locks across user dialogs. This file is the canonical home for those rules.

> **Scope.** This file owns the design rules. The narrow case "set a lock before reading balances during posting" lives as a worked example in `standards(name="platform-solutions") §9 → "Managed locks and deadlock prevention"` — that section now points back here for the general theory.

<!-- help-mcp-router -->

> **Retrieve through MCP only.** Call `standards(name="locks-and-transactions")` on `1C-docs-mcp` before applying this standard. Retrieval, paging, and unavailable-server policy: `content/rules/help-corpus-retrieval.md`. Headings below are retrieval targets, not summaries.

## 1. Lock mode of the configuration

## 2. Transaction boundaries

### Implicit transactions

### Explicit transactions in calling code

### Forbidden inside transactions

## 3. Managed-lock primitives

### Modes

## 4. Lock ordering — the deadlock contract

## 5. Locking patterns

### Pattern: posting a document that touches several registers

### Pattern: mass operation across many documents

### Pattern: status update outside posting

## 6. Diagnosing lock conflicts and deadlocks

### Symptoms

### Diagnostic tools

## 7. Companion rules
