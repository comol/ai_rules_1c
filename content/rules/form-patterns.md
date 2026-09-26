---
description: Managed-form layout patterns — archetypes (document, data processor, list, catalog item, wizard), naming, layout principles. Load when designing a form layout from scratch or when element placement is unspecified.
alwaysApply: false
category: forms
---

# Managed-Form Layout Patterns

Design guidance for managed forms, distilled from typical 1C configurations. Use when building a form and the user's requirements do not spell out where elements go. This is layout knowledge — it applies whether the form is edited via the `1c-metadata-manage` skill, EDT, or Designer. It complements the entry point `forms.md` and the hand-editing gotchas in `metadata-xml-workarounds.md`.

Element and group names below (`ГруппаШапка`, `Отбор[Поле]`, …) are the conventional 1C identifiers — keep them in Russian as shown; they are real names, not prose.

<!-- help-mcp-router -->

> **Retrieve through MCP only.** Call `standards(name="form-patterns")` on `1C-docs-mcp` before applying this standard. Retrieval, paging, and unavailable-server policy: `content/rules/help-corpus-retrieval.md`. Headings below are retrieval targets, not summaries.

## Form archetypes

### Document form

### Data-processor form (DataProcessor)

### List form

### Catalog item form

### Wizard

## Naming conventions

### Groups

### Elements

### Event handlers

## Layout principles

## Advanced patterns (ERP)

### Collapsible groups

### Status banner

### Popup menu in the command bar

### Form without a standard command bar

### Hyperlink label to open subforms

## Source
