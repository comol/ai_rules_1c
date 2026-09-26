---
description: Programmatic БСП access-group profiles and rights — profile structure, role references, assignment to users, right / role / RLS checks. Load when code creates, updates or assigns access profiles or checks rights in a БСП configuration.
alwaysApply: false
category: development
---

# БСП access-group profiles and rights — programmatic API

Applies to БСП / SSL 3.x configurations (ЗУП 3.1, БП 3.x, ERP 2.x, УТ 11.x): creating and updating `Справочник.ПрофилиГруппДоступа` from a code console or an update handler, assigning profiles to users, and checking rights, roles and RLS access.

> **Scope.** This file owns the *programmatic* side of access rights. Role **design** — which rights a role grants, RLS templates, role composition — lives in `content/skills/1c-metadata-manage/docs/role-manage.md`. Privileged-mode discipline in reports — `standards(name="dcs-design") §6`.

<!-- help-mcp-router -->

> **Retrieve through MCP only.** Call `standards(name="bsp-access-rights")` on `1C-docs-mcp` before applying this standard. Retrieval, paging, and unavailable-server policy: `content/rules/help-corpus-retrieval.md`. Headings below are retrieval targets, not summaries.

## 1. `Роли.Роль` is a reference, not a string

## 2. Extension roles live in a different catalog

## 3. Create / update template

## 4. Assigning a profile to a user

## 5. Checking rights, roles and RLS

## 6. Anti-patterns

## 7. Companion rules
