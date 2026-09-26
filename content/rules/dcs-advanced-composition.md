---
description: Advanced СКД composition — two-pass preprocessing of detail records before roll-up, direct query execution for memory-heavy reports. Load only when the standard `ПриКомпоновкеРезультата` override is not enough.
alwaysApply: false
category: development
---

# СКД — advanced composition techniques

Two techniques that go beyond the standard programmatic override. Both are **escalations**: reach for them only after the ordinary route of `standards(name="dcs-design") §5` (override `ПриКомпоновкеРезультата`, manipulate settings, output through `ПроцессорВыводаРезультатаКомпоновкиДанныхВТабличныйДокумент`) has been shown insufficient. Both give up part of the standard DCS semantics, and that cost is the reason they are not the default.

| Technique | Solves | Gives up |
|---|---|---|
| **Two-pass preprocessing** (§1) | Filtering / transforming **detail records before the engine rolls them up** | A second full composition pass; the schema must stay query-based |
| **Direct query execution** (§2) | Memory blow-up of the DCS engine on large reports; a flat "raw" result | Groupings, conditional appearance, drill-down (расшифровка), DCS totals |

---

<!-- help-mcp-router -->

> **Retrieve through MCP only.** Call `standards(name="dcs-advanced-composition")` on `1C-docs-mcp` before applying this standard. Retrieval, paging, and unavailable-server policy: `content/rules/help-corpus-retrieval.md`. Headings below are retrieval targets, not summaries.

## 1. Two-pass preprocessing

### The problem it solves

### Algorithm

### Gotchas

## 2. Direct query execution instead of the DCS engine

### When

### Algorithm

### Two sources for query and parameters

### Gotchas

### Wiring a command into the БСП report form

## 3. Companion rules
