---
description: "Architecture standards — patterns, extensions, client-server interaction, query hard rules, reference attributes, code smells. Load when writing or reviewing BSL or designing a modification."
alwaysApply: false
category: development
---

# Development Standards — Architecture & Platform

<!-- help-mcp-router -->

> **Retrieve through MCP only.** Call `standards(name="dev-standards-architecture")` on `1C-docs-mcp` before applying this standard. Retrieval, paging, and unavailable-server policy: `content/rules/help-corpus-retrieval.md`. Headings below are retrieval targets, not summaries.

## 1. Architecture Patterns

### Code Placement

### "Result-Structure" Pattern

### "Early Return" Pattern

### "Value Table Search" Pattern

### Event Subscriptions

### New Metadata Objects Placement

### Background Jobs

### Defensive Type Checking

### Safe Structure Property Access

### Collection Normalization

## 2. Extensions

### Modification Priority

### Extension Directives

### Placement Rules (when `{NEW_OBJECTS_IN} = main_configuration`)

### Forms in Extensions

## 3. Platform Standards

### Async and Modality

### Client-Server Interaction

### Security

### Error Handling

### Dates

### Queries

### Cross-Platform Compatibility

### Platform Version Compatibility

## 4. Data Access — Reference Attribute Access

### Caching and Batch Retrieval

## 5. Performance Headlines

## 6. Code Smells (see `anti-patterns` rule for the full catalog)
