---
description: Designing 1C registers — dimensions, resources, periodicity, indexes, balances vs turnovers, posting/sequences. Load when creating or restructuring a register.
alwaysApply: false
category: development
---

# Register Design Rules

Registers are the spine of any non-trivial 1C configuration; mistakes here are expensive to undo because they are usually wired into document posting, RLS, and reports. This file consolidates the design decisions worth thinking through **before** running the metadata skill.

> **Scope.** This file owns *design* rules. XML / schema mechanics live in `content/skills/1c-metadata-manage/docs/meta-manage.md`. Queries against registers — start at the router `query-design.md` (hard rules in `standards(name="dev-standards-architecture") §3 → "Queries"`, anti-patterns in `standards(name="anti-patterns")`).

<!-- help-mcp-router -->

> **Retrieve through MCP only.** Call `standards(name="registers-design")` on `1C-docs-mcp` before applying this standard. Retrieval, paging, and unavailable-server policy: `content/rules/help-corpus-retrieval.md`. Headings below are retrieval targets, not summaries.

## 1. Choosing the register type

## 2. Dimensions

## 3. Resources

## 4. Attributes

## 5. Indexing

## 6. Subordination to a registrar (only for accumulation / accounting / calculation)

## 7. Balances, turnovers, slices

## 8. Posting / reposting

## 9. Querying registers

## 10. RLS

## 11. Companion rules
