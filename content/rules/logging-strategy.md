---
description: Positive logging strategy for 1C — when to write to the event log, severity levels, category names, structured payload, secrets / PII bans. Load when code writes to the event log or a task asks for logging.
alwaysApply: false
category: development
---

# Logging Strategy

`standards(name="dev-standards-code-style") → "Forbidden Calls and Constructs"` bans `ЗаписьЖурналаРегистрации` without an explicit task; `standards(name="dev-standards-architecture") §3 → "Error Handling"` bans empty `Попытка / Исключение`. This file is the **positive** companion: when logging *is* explicitly requested, this is how to do it.

<!-- help-mcp-router -->

> **Retrieve through MCP only.** Call `standards(name="logging-strategy")` on `1C-docs-mcp` before applying this standard. Retrieval, paging, and unavailable-server policy: `content/rules/help-corpus-retrieval.md`. Headings below are retrieval targets, not summaries.

## 1. When to log

## 2. Severity levels

## 3. Event-category naming

## 4. Structured payload

## 5. Error / exception logging

## 6. What MUST NOT go into the log

## 7. Rotation and retention

## 8. Companion rules
