---
description: Common XML generation pitfalls for 1C metadata and managed forms (`TabularSection` `LineNumber`, `PagesGroupExtInfo` typo, `Page.enabled`, UID uniqueness, post-edit validation). Load when authoring or fixing metadata XML or `Form.xml` by hand.
alwaysApply: false
category: metadata
---

# Common XML Generation Pitfalls (Metadata and Forms)

Concrete recurring mistakes when generating or editing 1C metadata XML / MDO and managed-form XML by hand or with scripts. Apply when authoring metadata XML directly (rather than via the `1c-metadata-manage` skill).

> **Hand-editing is the exception, not a parallel path.** Mutating metadata XML goes through the `1c-metadata-manage` skill or the `1c-metadata-manager` subagent (see `content/agents/metadata-manager.md`) — hard gate per `AGENTS.md → Skills and Subagents`. This file applies only inside the documented exceptions (`content/skills/1c-metadata-manage/SKILL.md → Hard rule`: one-line fix, skill unavailable) and for reviewing existing files.

---

## 1. TabularSections — no `LineNumber` standard attribute

Tabular sections (`табличные части`) **must not** contain a `<standardAttributes>` block with `LineNumber`. The platform adds it automatically; an explicit copy will cause a load error or duplication.

```xml
<!-- WRONG — remove this block from <tabularSections> -->
<standardAttributes>
  <dataHistory>Use</dataHistory>
  <name>LineNumber</name>
  <fillValue xsi:type="core:UndefinedValue"/>
  <fullTextSearch>Use</fullTextSearch>
  <minValue xsi:type="core:UndefinedValue"/>
  <maxValue xsi:type="core:UndefinedValue"/>
</standardAttributes>
```

The same rule applies to MDO (EDT format) `*.mdo` files — do not add a `LineNumber` standardAttribute to tabular sections; the EDT toolchain provides it implicitly.

---

## 2. `Pages` group — correct extInfo type name

The extInfo type is `PagesGroupExtInfo` (with letter "**s**"), not `PageGroupExtInfo`:

```xml
<!-- CORRECT -->
<type>Pages</type>
<extInfo xsi:type="form:PagesGroupExtInfo">
  <pagesRepresentation>Auto</pagesRepresentation>
  <currentRowUse>Auto</currentRowUse>
</extInfo>
```

A misspelled `PageGroupExtInfo` will silently break the form — the page group will not load in Designer / EDT.

---

## 3. `Page` element — must include `<enabled>true</enabled>`

For each `Page` element inside a `Pages` group, the `<enabled>` flag is required. Without it, Designer treats the page as disabled (or the form fails validation).

```xml
<type>Page</type>
<enabled>true</enabled>
```

---

## 4. UID / UUID — must be globally unique

All UIDs and UUIDs of new metadata objects, attributes, tabular sections must be **globally unique** across the configuration.

- Generate each UUID separately via `[guid]::NewGuid()` (PowerShell) or `uuid.uuid4()` (Python).
- Never reuse a UUID by copy-paste.
- Never use placeholder / sequential UUIDs (`a1b2c3d4...`, `b2c3d4e5...`).
- After bulk metadata generation, run a duplicate-UUID check across the source tree.

When adding metadata objects — also update `Configuration.xml` (`<childObjects>` ordering matters).

---

## 5. Validation hook

Whenever editing metadata XML by hand, after the change run:

- `verify_xml` from `1c-code-metadata-mcp` against the appropriate XSD (`get_xsd_schema` first if unsure of the type).
- Then a sanity load via `1c-metadata-manage/tools/1c-meta-validate/scripts/meta-validate.ps1`.

This catches structural issues (missing required elements, wrong type names, broken references) before they reach the platform.
