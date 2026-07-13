# 1C Support State — vendor-lock guard and `Ext/ParentConfigurations.bin`

Covers the **support-guard** subsystem that protects vendor-supported ("на поддержке"/"на замке") metadata objects from silent edits, and the **support-edit** tool used to deliberately change that state.

> **Deviation from upstream (`cc-1c-skills`).** Upstream resolves the guard policy from a `.v8-project.json` field (`editingAllowedCheck`). In this project the policy source is **`.dev.env`**'s `SUPPORT_EDIT_POLICY` instead — `.dev.env` is the project's single source of truth for operational parameters (see `AGENTS.md` / `dev-standards-core.md §1`), and `.v8-project.json` here is documentation-only (no script reads it — see [db-manage.md](db-manage.md)). Everything else below (the `Ext/ParentConfigurations.bin` format, the block/flag semantics, the conservative multi-vendor fold) is unchanged from upstream.

---

## 1. Where the guard runs

The write-guard (`Assert-EditAllowed`) and the read-only status reporter (`Get-SupportStatusForPath`) live in one shared, dot-sourced helper: `tools/_shared/support-guard.ps1`. It is wired into:

- **Write tools** (block/warn before mutating a locked object): `cf-edit`, `role-compile`, `subsystem-compile`, `subsystem-edit`, `interface-edit`, `template-add`, `help-add`, `meta-compile`, `meta-edit`, `meta-remove` (requires the object to be *removed from support* before deletion), `form-add`, `form-compile`, `form-edit`, `skd-compile`, `skd-edit`, `mxl-compile`.
- **Read-only tools** (append a `"Поддержка: ..."` status line to their output, never block): `cf-info`, `role-info`, `subsystem-info`, `meta-info`, `mxl-info`, `skd-info`, `form-info`.

Guard errors always degrade to **allow** — a parsing failure or missing file never blocks an edit that would otherwise be fine.

## 2. `SUPPORT_EDIT_POLICY` (`.dev.env`)

| Value | Effect |
|---|---|
| `deny` (default) | Editing a locked/on-support object is blocked; the tool exits with an error and points to `cfe-borrow` / `cfe-patch-method` / `support-edit` as the correct path. |
| `warn` | Editing is allowed, but a warning is printed to stderr. |
| `off` | The check is fully disabled — `support-guard` always allows. |

The helper walks up from the current directory (and from the target config directory) up to 20 levels looking for `.dev.env`, same algorithm as upstream's `.v8-project.json` walk-up. If no `.dev.env` is found, or the field is absent/invalid, the default is `deny`.

## 3. `Ext/ParentConfigurations.bin` format

Specification of the `Ext/ParentConfigurations.bin` file from a 1C configuration XML dump (`DumpConfigToFiles`). The file stores the configuration's **support state**: a global "edit capability" flag, the list of vendor configurations it is on support for, and per-object support rules (locked / editable-with-support / removed-from-support).

This is the **only** source of support state in a dump — neither `Configuration.xml`, nor `ConfigDumpInfo.xml`, nor individual object files carry it.

> Reverse-engineered from annotated dumps (single-vendor and a multi-vendor sample), not from 1C documentation. Values marked **observed** are confirmed on concrete objects; values marked **(not fully reverse-engineered)** need more samples.

### 3.1 Location and presence

```
<configSrc>/
    Ext/
        ParentConfigurations.bin    # support state, present only when on vendor support
```

| State | File |
|---|---|
| Configuration **is on support** | present, hundreds of KB to a few MB (one entry per vendor object) |
| Support **fully removed** | present but truncated to ~16 bytes (empty container) |
| Own configuration (no vendor) | file absent |
| **Extension (CFE)** | file absent; extension source editing is never restricted by the base configuration's support state |

A rough "this is a vendor configuration" signal comes independently from `Configuration.xml`: non-empty `<Vendor>` + `<Version>`. An extension is recognized *positively* via `<ConfigurationExtensionPurpose>` (`Customization` / `Patch` / …) — more reliable than "bin absent", and it distinguishes an extension from "support fully removed" (where the bin is also nearly empty).

### 3.2 Encoding and overall shape

- Encoding: **UTF-8 with BOM** (`EF BB BF`). Despite the `.bin` extension, the content is text.
- Format: a 1C brace-container `{ ... }`, comma-separated elements, double-quoted strings with doubled internal quotes (`"Company ""1C"""`). Exactly one `{ }` pair for the whole file — no nesting.

```
{ 6, G, K,
    <vendor block 1>
    0,0
    <vendor block 2>
    0,0
    ...
    <vendor block K> }
```

- `6` — format marker.
- `G` — global "edit capability" flag (§3.3).
- `K` — number of vendor configurations on support (§3.5). `K = 1` for single-vendor support.
- Vendor blocks are separated by the two-token `0,0` (absent after the last block).

Each **vendor block**:

```
guidA, X, vendorGuid, "version", "vendor", "name", count,
   f1,f2,<uuidLocal>,<uuidVendor>,        ← object records, count of them
   f1,f2,<uuidLocal>,<uuidVendor>,
   ...
```

**Key gotcha: the `f1,f2` flags come BEFORE their uuid**, not after — easy to get wrong with a naive `uuid,uuid,int,int` regex.

### 3.3 Global edit capability (`G`)

Container token #2 (right after the `6` format marker):

- `G = 0` — vendor-configuration editing is **enabled**; check per-object rules `f1` (§3.4).
- `G = 1` — editing is **fully disabled**. The whole configuration is read-only regardless of per-object rules; `f1` is observed as `1` everywhere in this mode (uninformative).

> Each vendor block also carries a token `X` (right after `guidA`) that in all samples **equals `G`**. It cannot be distinguished from `G` with the available samples — treating `G` alone is sufficient for the guard. **(not fully reverse-engineered)**

### 3.4 Vendor block and per-object rules

| Field | Meaning |
|---|---|
| `guidA` | block GUID, changes between dumps (snapshot identifier) |
| `X` | flag, observed equal to `G` (§3.3) |
| `vendorGuid` | stable GUID of the vendor configuration |
| `"version"` | vendor configuration version |
| `"vendor"` | vendor name |
| `"name"` | vendor configuration name |
| `count` | number of object records that follow |

Each object record: `f1, f2, <uuidLocal>, <uuidVendor>`.

- `uuidLocal` — the object's uuid in the **current** configuration (matches the `uuid="…"` on the object file's root element).
- `uuidVendor` — the object's uuid in the **vendor's** configuration. Usually equal to `uuidLocal` for single-vendor support; can differ.
- The block's first record is the configuration root; for single-vendor support it is recorded with one uuid (no `uuidVendor` pair).
- Sub-elements (attributes, tabular sections, forms, etc.) get their own records too — the record count is a multiple of the top-level object count.

**Support rule `f1` (when `G = 0`):**

| `f1` | 1C rule | Editing |
|---|---|---|
| `0` | vendor object **is not editable** (locked) | forbidden |
| `1` | vendor object is **editable with support retained** | allowed |
| `2` | object is **removed from support** / not covered by this vendor | allowed |

`f2` is `0` in every sample so far (secondary flag; no toggle case observed — **(not fully reverse-engineered)**).

### 3.5 Multiple vendors (`K > 1`)

When a configuration is on support from several vendor configurations, `K > 1` and `K` blocks follow in sequence (separated by `0,0`). Each block is its own vendor with its own `count` and record set.

The same object (by `uuidLocal`) can appear in multiple blocks with **different** `f1` rules — one rule per vendor. The **effective, conservative rule** used for the gate decision:

> an object is treated as **locked** if `f1 = 0` for at least one vendor; otherwise editing is allowed (`1`/`2` for every vendor that includes it).

The exact "effective" semantics shown by Configurator itself on a vendor conflict is not confirmed from available samples — **(not fully reverse-engineered)**. The conservative fold above is what the guard implements.

### 3.6 Static "can this object be edited" algorithm

```
1. Read the ParentConfigurations.bin header in configSrc.
     file absent / ~16 bytes  → no support             → editing ALLOWED
     G = 1                    → capability disabled     → everything read-only (blocked)
     G = 0                    → go to step 2
2. Resolve the edited file to its object's root .xml:
     - the object file itself (Catalogs/X.xml, Documents/Y.xml) carries the uuid
       on its root element;
     - a file inside the object's directory (Catalogs/X/Ext/ObjectModule.bsl,
       Catalogs/X/Forms/F/Ext/Form.xml) → walk up to the root Catalogs/X.xml.
   ConfigDumpInfo.xml is NOT needed for this (it may be absent from the dump/git tree).
3. Collect f1 for this uuid (as uuidLocal) across ALL vendor blocks:
     f1 = 0 for at least one vendor  → locked            → editing FORBIDDEN
     otherwise (only 1/2)            → editable/removed   → ALLOWED
     uuid not found in any block     → not on support      → ALLOWED
```

A sub-element (a single attribute, a form) does not need a separate check — its XML cannot be edited without touching the object file, so the top-level object's rule is sufficient.

## 4. `support-edit` — toggling the state

Use when you deliberately want to unlock an object or the whole configuration for editing (instead of routing the change through an extension via `cfe-borrow`/`cfe-patch-method`).

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-support-edit/scripts/support-edit.ps1 -Path <target> -Set editable|off-support|locked
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-support-edit/scripts/support-edit.ps1 -Path <target> -Capability on|off
```

| Parameter | Meaning |
|---|---|
| `-Path` (alias `-TargetPath`, mandatory) | Path to the object file/directory, or to the configuration root. |
| `-Set editable\|off-support\|locked` | Per-object toggle: rewrites `f1` for the resolved object's uuid to `1`/`2`/`0`. Requires the global capability (`G`) to already be `0` (enabled). |
| `-Capability on\|off` | Global toggle: `on` sets `G = 0` and locks every object (`f1 = 0`) as a safe starting point; `off` sets `G = 1`, making the whole configuration read-only and resetting per-object rules. |

Exactly one of `-Set` / `-Capability` is required. If `-Path` has no `Ext/ParentConfigurations.bin` above it (own configuration, or support already fully removed), the tool reports there is nothing to toggle and exits cleanly.

**Typical unlock sequence** for an object that is locked while the whole configuration has editing disabled (`G = 1`):

```
1. support-edit -Path <configSrc> -Capability on      — enable edit capability (every object stays locked)
2. support-edit -Path <object>    -Set editable        — open this one object for editing
```

## 5. Companion rules

| Concern | File |
|---|---|
| `.v8-project.json` / `.dev.env` relationship | [db-manage.md §Part 1](db-manage.md) |
| Preferred alternative to editing a locked object | [cfe-manage.md](cfe-manage.md) (`cfe-borrow`, `cfe-patch-method`) |
| Extension patterns in general | `extension-patterns.md` (rule, load on demand) |
