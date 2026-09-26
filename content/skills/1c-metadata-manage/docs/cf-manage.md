# 1C Configuration Manage — Init, Edit, Info, Validate

Comprehensive configuration management: create scaffold, edit properties/composition, analyze structure, validate correctness.

---

## 1. Init — Create Configuration Scaffold

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-cf-manage/scripts/cf-init.ps1 -Name "<Name>" [-OutputDir "<path>"]
```

Creates minimal configuration structure: `Configuration.xml`, `Languages/Русский.xml`, and basic directory structure.

---

## 2. Edit — Modify Configuration Properties

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-cf-manage/scripts/cf-edit.ps1 -ConfigPath '<path>' -Operation <op> -Value '<value>'
```

| Parameter | Description |
|-----------|-------------|
| `ConfigPath` | Path to Configuration.xml or export directory |
| `Operation` | Operation (see table) |
| `Value` | Value (batch via `;;`) |
| `DefinitionFile` | JSON file with operation array |
| `NoValidate` | Skip auto-validation |

### Operations

| Operation | Value Format | Description |
|-----------|-------------|-------------|
| `modify-property` | `Key=Value` (batch `;;`) | Change property |
| `add-childObject` | `Type.Name` (batch `;;`) | Add object to ChildObjects |
| `remove-childObject` | `Type.Name` (batch `;;`) | Remove object from ChildObjects |
| `add-defaultRole` | `Role.Name` or `Name` | Add default role |
| `remove-defaultRole` | `Role.Name` or `Name` | Remove default role |
| `set-defaultRoles` | Names via `;;` | Replace default roles list |

Full property reference: [cf-edit-reference.md](../tools/1c-cf-manage/cf-edit-reference.md).

### Examples

```powershell
# Change version and vendor
... -Operation modify-property -Value "Version=1.0.0.1 ;; Vendor=Company"

# Add objects
... -Operation add-childObject -Value "Catalog.Товары ;; Document.Заказ"

# Default roles
... -Operation set-defaultRoles -Value "ПолныеПрава ;; Администратор"
```

---

## 3. Info — Analyze Configuration Structure

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-cf-manage/scripts/cf-info.ps1 -ConfigPath "<path>"
```

Displays configuration properties, object counts by type, compatibility mode, version, and other key information.

---

## 4. Validate — Check Configuration Correctness

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-cf-manage/scripts/cf-validate.ps1 -ConfigPath "<path>"
```

| Parameter | Description |
|-----------|-------------|
| `ConfigPath` | Path to Configuration.xml or export directory |
| `MaxErrors` | Stop after N errors (default: 30) |
| `OutFile` | Write result to file (UTF-8 BOM) |

### Checks Performed

| # | Check | Severity |
|---|-------|----------|
| 1 | XML well-formedness, MetaDataObject/Configuration, version 2.17/2.20 | ERROR |
| 2 | InternalInfo: 7 ContainedObject, valid ClassId, uniqueness | ERROR |
| 3 | Properties: Name non-empty, Synonym, DefaultLanguage, DefaultRunMode | ERROR/WARN |
| 4 | Properties: enum values (11 properties) | ERROR |
| 5 | ChildObjects: valid type names (44 types), no duplicates, type order | ERROR/WARN |
| 6 | DefaultLanguage references existing Language in ChildObjects | ERROR |
| 7 | Language files Languages/<name>.xml exist | WARN |
| 8 | Object directories from ChildObjects exist (spot-check) | WARN |

Exit code: 0 = OK, 1 = errors.

### Complete dump integrity

For a **complete hierarchical Designer XML dump**, run the read-only composition
check after `cf-validate` (or `cfe-validate` for an extension):

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-cf-manage/scripts/dump-validate.ps1 -ConfigPath "<dump-directory>" -Format Json
```

`ConfigPath` also accepts `Configuration.xml`. `Format` is `Text` by default or
`Json` for automation. Optional `OutFile` saves the same result as UTF-8 with BOM;
it must be outside the checked dump, so a report cannot overwrite its sources.
The command does not repair, delete or regenerate any source file.

Coverage:

- Declared root metadata objects and recursively declared nested subsystems:
  missing descriptor files, orphan descriptor files, duplicate declarations,
  unknown composition types, invalid names, unreadable XML and mismatched names.
- Each scanned descriptor's format version against `Configuration.xml`.
- Object references in configuration `Default*` properties and subsystem
  `Content`. Nested subsystem references resolve to their own descriptor.
- Optional `ConfigDumpInfo.xml`: root/format, version and records whose owning
  metadata object is absent. Attribute/module records are resolved to their
  owner; their individual existence is outside this check. Absence of
  `ConfigDumpInfo.xml` alone is not an error.

JSON has `schema_version: 1`, `status` (`valid`, `invalid`, `error`), `root`,
`objects_checked` and `findings`. Each finding has stable `kind`, `severity`,
relative `path`, qualified `object` and human-readable `message`. Consumers use
`kind`, never parse `message`. Main integrity codes are `missing-file`,
`orphan-file`, `duplicate-entry`, `unknown-type`, `version-mismatch`,
`dangling-reference`, `dump-info-version` and `dump-info-extra`; malformed input
and an incomplete scan also return findings. Exit 0 means no findings within
this coverage; exit 1 means findings or an incomplete scan.

Do not run this on a partial export or automatically during intermediate
scaffolding: unexported objects would correctly appear as missing. This is a
separate check from per-object/schema validation, UUID checking and platform
loading. It does not inspect forms/templates internals, BSL, all metadata
references or extension applicability. Supplier configurations under `Ext` are
not traversed. Object ordering remains the responsibility of `cf-validate` /
`cfe-validate`; there is no new alphabetical-order requirement.

---

## Typical Workflow

```
1c-cf-manage init        — create configuration scaffold
1c-cf-manage edit        — set properties, add objects
1c-cf-manage validate    — check correctness
1c-cf-manage info        — view structure summary
```

Scripts vendored from Nikolay-Shirokov/cc-1c-skills; sync history — `docs/CHANGELOG.md`.
