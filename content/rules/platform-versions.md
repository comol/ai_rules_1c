---
description: "1C:Enterprise 8.3 and 8.5 versions, XML dump formats 2.13-2.22, and compatibility-mode reasoning (CompatibilityMode, Extension, Interface). Load on version-sensitive work."
alwaysApply: false
category: development
---

# Platform Versions (8.3 / 8.5) and Compatibility Modes

Load when a task depends on platform version behavior (`PLATFORM_VERSION`, 8.3.x vs 8.5.x), XML dump format versions (`2.13`–`2.22`), or configuration / extension / interface compatibility modes.

## XML Dump Format Preservation (8.3.x and 8.5.x)

| Platform line | Typical XML dump format | Notable XML traits |
|---|---|---|
| 8.3.20–8.3.23 | `2.13`–`2.16` | Legacy mobile/property lists; `2.16` adds `DefaultReportAppearanceTemplate`, `DatabaseTablespacesUseMode` |
| 8.3.24–8.3.27 | `2.17`–`2.20` | Standard 8.3 baseline across `1c-metadata-manage` |
| 8.5.1.x | `2.21` | Adds `xmlns:pal` palette namespace and `TextToSpeech` |
| 8.5.4.x | `2.22` | 8.5.4 dump format |

- **Format-preservation invariant:** always edit a source tree in its **existing** `formatVersion` (detected from `Configuration.xml` or the root external object XML). Never silently upgrade or downgrade a dump between `2.17`–`2.22` without explicit user confirmation.
- **Base + extension:** a base configuration and its extension may legitimately sit on different minor dump formats within a compatible platform line; keep each tree's own `formatVersion`.
- **Single-tree consistency:** every stamped `Ext/*.xml` body inside one configuration dump must carry the same `formatVersion` as its `Configuration.xml` (mixed versions fail platform load).
- Do not confuse the XML dump format (`2.21` / `2.22`) with the runtime platform line (`8.5.1` / `8.5.4`) or with `CompatibilityMode`.

## Three Separate Compatibility Mode Families

Never conflate these three properties:

| Property | Scope | Interpretation |
|---|---|---|
| `CompatibilityMode` | Configuration runtime behavior, APIs, metadata and persisted behavior | `DontUse` → runtime platform line; `VersionX` → `X` |
| `ConfigurationExtensionCompatibilityMode` | Extension capabilities and extension-specific behavior | Normalize its own literal; code living in an extension does **not** make this property replace `CompatibilityMode` for general configuration behavior |
| `InterfaceCompatibilityMode` | Client UI / interface behavior | Interpret the exact enum literal from target-platform documentation; do not apply the `DontUse`/`VersionX` formula |

## Decision Workflow and Stop Rules

1. Establish the **runtime platform line** (`.dev.env` `PLATFORM_VERSION` or confirmed target environment) and read the exact mode literal from configuration / extension metadata.
2. Normalize `CompatibilityMode` (`DontUse` → runtime line; `VersionX` → `X`) to the **effective compatibility version**.
3. Verify the exact feature boundary and enum literal validity via `1C-docs-mcp` (`docsearch` / `docinfo`) for the target platform version — never assume that platform `8.5.4` guarantees a literal named `Version8_5_4` or that a standard (`standards(...)`) proves platform runtime behavior (`mcp-policy.md → A.2`).
4. **Equivalence boundary:** `8.3.24 + DontUse` and `8.3.27 + Version8_3_24` (or `8.5.4 + Version8_3_24`, if supported) share only the documented **compatibility-controlled** behavior for that feature — never full runtime equivalence (fixes, performance, and non-gated features still differ).
5. When comparing environments or modes, present a compact matrix: `runtime platform | literal mode | effective version | feature result | evidence`.

**Stop rules:**
- Never give a hard version-sensitive verdict without runtime version, exact mode literal, owning metadata object, and doc-confirmed feature boundary.
- Never compare mode strings lexically (`"Version8_3_9" > "Version8_3_27"` is false lexically).
- Never invent future compatibility-mode enum values; if platform docs for the target version are unavailable, report the exact version gap under **Risks**.
