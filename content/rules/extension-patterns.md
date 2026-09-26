---
description: Configuration extension (CFE) patterns — interceptor types, `ПродолжитьВызов` rules, change markers, adopted-object constraints. Load when writing or reviewing extension code.
alwaysApply: false
category: architecture
---

# 1C Extension Patterns (CFE)

BSL patterns for working with 1C configuration extensions.

Applies to: extension code (`**/Extensions/**/*.bsl` and similar).

Background reference: `standards(name="dev-standards-architecture") §2` (Extensions) — modification priority, directives, placement rules. This file is the **practical** companion: interceptor types, `ПродолжитьВызов` semantics, markers, and adopted-object constraints.

> **Naming convention used in examples.** Below, `Расш1_` / `МоеРасш_` denotes the **extension's own short alias** (set in the extension's properties — typically the `Имя` of the extension or an explicit alias), **not** `{PREFIX}` from `.dev.env`. `{PREFIX}` applies to new metadata objects and attributes; the extension alias applies to procedure / function names introduced by the extension and prevents name collisions between extensions. The two are independent: an extension can both add a new attribute `{PREFIX}Признак` to a typical object and define an interceptor procedure `Расш1_ПриЗаписи` in the same module.
>
> The alias itself MUST NOT contain the letter «ё» — see `standards(name="dev-standards-code-style") → Typography`. Use `МоеРасш_`, `Расш1_`, `MyExt_` or any «ё»-free form.

---

<!-- help-mcp-router -->

> **Retrieve through MCP only.** Call `standards(name="extension-patterns")` on `1C-docs-mcp` before applying this standard. Retrieval, paging, and unavailable-server policy: `content/rules/help-corpus-retrieval.md`. Headings below are retrieval targets, not summaries.

## Interceptor types

### Before / After — simple interceptors

### Вместо — full replacement

### ИзменениеИКонтроль — controlled body edit

## ПродолжитьВызов() rules

## Change markers

## Constraints on adopted (borrowed) objects

## Anti-patterns

### Direct edit of an adopted module

### Forgotten ПродолжитьВызов in &Вместо

### ПродолжитьВызов inside &ИзменениеИКонтроль

### No prefix in extension method names

## Extension purpose tag
