---
description: 1C СКД / DCS design rules — data sets, computed fields vs resources, parameters, settings, variants, programmatic overrides. Load when designing or reviewing DCS reports.
alwaysApply: false
category: development
---

# DCS / СКД — Report Design Rules

The 1C Data Composition System (СхемаКомпоновкиДанных, СКД) is the canonical engine for reports. The rules below cover design decisions that recur in code review and that the structural skill (`content/skills/1c-metadata-manage/docs/skd-manage.md`) intentionally does not opine on.

> **Scope.** This file owns *report design* rules. XML / schema mechanics for `.dcs` files live in the `content/skills/1c-metadata-manage/docs/skd-manage.md` skill (XML structure, datasets API, query parameters API). Anti-patterns of slow queries inside a DCS — `standards(name="anti-patterns")` and `standards(name="dev-standards-architecture") §3 → "Queries"`.

<!-- help-mcp-router -->

> **Retrieve through MCP only.** Call `standards(name="dcs-design")` on `1C-docs-mcp` before applying this standard. Retrieval, paging, and unavailable-server policy: `content/rules/help-corpus-retrieval.md`. Headings below are retrieval targets, not summaries.

## 1. Choosing the data-set type

## 2. Computed fields vs resources

## 3. Parameters

## 4. Variants and settings

## 5. Programmatic override

## 6. RLS interaction

## 7. Performance checklist

## 8. Companion rules
