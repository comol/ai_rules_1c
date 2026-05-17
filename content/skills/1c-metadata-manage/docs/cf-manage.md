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

---

## Typical Workflow

```
1c-cf-manage init        — create configuration scaffold
1c-cf-manage edit        — set properties, add objects
1c-cf-manage validate    — check correctness
1c-cf-manage info        — view structure summary
```

## Recent Additions (upstream `w-2026-05-17`)

The PowerShell scripts under `tools/1c-cf-manage/scripts/` were refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights:

### `cf-init`

- Generates a default panel layout aligned with stock ERP/БП ≥ 8.3.24: open windows on top, sections on the left. Without this layout the web client renders sections as icons only — `web-test` could not see them. Modern interface mode + 8.2-style backward compatibility is the default.

### `cf-edit` — new operations

- **`set-panels`** — configure the configuration panels via JSON. Aliases by name (`sections`, `open`, `favorites`, `history`, `functions`), panel stacking via `{group: [...]}`, multiple panels side-by-side. Russian aliases (`Открытых`, `Разделов`, `Избранного`, `История`, `Функций`) are accepted and silently mapped to canonical English aliases.
- **`set-home-page`** — rewrite the home page: one or two columns, list of forms with height / visibility / role overrides.
- **`add-childObject`** — now requires the object file to exist on disk; otherwise the script fails with a hint to call `/meta-compile`, `/role-compile`, `/subsystem-compile` first. Previously `Configuration.xml` could end up referencing a missing file and the platform would silently refuse to load. The legacy mode (root XML lost while files survive) is preserved for the rare rollback scenario.

### `cf-info`

- Configuration overview shows the panel layout (panel stacks within one side and side-by-side panels). With `-Section home-page` — full home page contents with layout and role overrides.

### `cf-validate`

- Cross-references `Form` references in the home page and in default-form properties of configuration objects — broken links are now caught at validation time, not at load time.
- Platform 8.5 support — new compatibility-mode and interface-mode values plus the new XML header format. (Same upgrade in `cfe-validate`, `epf-validate`, `skd-validate`.)

## MCP Integration

- **get_object_dossier** — Comprehensive structural passport of existing configuration objects (structure, forms, dependencies, code, roles) in one call.
- **metadatasearch** — Explore existing configuration structure, verify object names.
- **get_metadata_details** — Get full object structure for existing configuration objects.
- **metadatasearch** (`names_only=true`) — Find similar configuration objects as XML reference examples.
- **get_xsd_schema** — Get XSD schema for configuration XML. Use before generating Configuration.xml.
- **verify_xml** — Validate generated configuration XML against XSD.
- **compare_base_and_extension** — Compare configuration objects with their extension counterparts when working with configurations that have extensions.
- **docsearch** — Platform documentation on configuration properties.

## SDD Integration

When creating a new configuration as part of a project, update SDD artifacts if present (see `content/rules/sdd-integrations.md` for detection):

- **OpenSpec**: Create initial specs in `openspec/specs/` describing configuration purpose, compatibility, and scope.
