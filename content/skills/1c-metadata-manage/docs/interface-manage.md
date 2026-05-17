# 1C Interface Manage — Edit and Validate Command Interface

Edit and validate CommandInterface.xml files for 1C subsystems.

---

## 1. Edit — Modify CommandInterface.xml

Operations: hide, show, place, order, subsystem-order, group-order. Full reference: [reference.md](../tools/1c-interface-manage/reference.md).

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-interface-manage/scripts/interface-edit.ps1 -CIPath '<path>' -Operation <op> -Value '<value>'
```

| Parameter | Description |
|-----------|-------------|
| CIPath | Path to CommandInterface.xml |
| DefinitionFile | JSON file with operation array |
| Operation | Single operation: hide, show, place, order, subsystem-order, group-order |
| Value | Value for operation |
| CreateIfMissing | Create file if it doesn't exist |
| NoValidate | Skip auto-validation |

### Operations

| Operation | Value | Description |
|-----------|-------|-------------|
| hide | Cmd.Name or array | Hide command (CommandsVisibility, false) |
| show | Cmd.Name or array | Show command (visibility, true) |
| place | `{"command":"...","group":"CommandGroup.X"}` | Place command in group |
| order | `{"group":"...","commands":[...]}` | Set command order in group |
| subsystem-order | `["Subsystem.X.Subsystem.A",...]` | Order of child subsystems |
| group-order | `["NavigationPanelOrdinary",...]` | Order of groups |

### Examples

```powershell
# Hide a command
... -Operation hide -Value "Catalog.Товары.StandardCommand.OpenList"

# Show a command
... -Operation show -Value "Report.Продажи.Command.Отчёт"

# Place in group
... -Operation place -Value '{"command":"Report.X.Command.Y","group":"CommandGroup.Отчеты"}'

# Set subsystem order
... -Operation subsystem-order -Value '["Subsystem.X.Subsystem.A","Subsystem.X.Subsystem.B"]'
```

Auto-validation runs after each operation. Suppress with `-NoValidate`.

---

## 2. Validate — Check CommandInterface.xml Correctness

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-interface-manage/scripts/interface-validate.ps1 -CIPath '<path>'
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| CIPath | yes | — | Path to CommandInterface.xml |
| MaxErrors | no | 30 | Stop after N errors |
| OutFile | no | — | Write result to file (UTF-8 BOM) |

### Checks (13)

| # | Check | Severity |
|---|-------|----------|
| 1 | XML well-formedness + root element (CommandInterface, version, namespace) | ERROR |
| 2 | Allowed child elements (only 5 sections) | ERROR |
| 3 | Section order correct | ERROR |
| 4 | No duplicate sections | ERROR |
| 5 | CommandsVisibility — Command.name + Visibility/xr:Common | ERROR |
| 6 | CommandsVisibility — no duplicates by name | WARN |
| 7 | CommandsPlacement — Command.name + CommandGroup + Placement | ERROR |
| 8 | CommandsOrder — Command.name + CommandGroup | ERROR |
| 9 | SubsystemsOrder — Subsystem non-empty, format Subsystem.X | ERROR |
| 10 | SubsystemsOrder — no duplicates | WARN |
| 11 | GroupsOrder — Group non-empty | ERROR |
| 12 | GroupsOrder — no duplicates | WARN |
| 13 | Command reference format | WARN |

Exit code: 0 = all checks passed, 1 = errors found.

## Recent Additions (upstream `w-2026-05-17`)

The PowerShell scripts under `tools/1c-interface-manage/scripts/` were refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights:

- **`interface-edit`** — operations `place` / `order` accept the value as an object (not only as a string). Command names in `hide` / `show` / `place` / `order` are normalised: `Catalogs.X` and `Справочник.X` map to canonical `Catalog.X`.
- **`interface-validate`** — universal validator improvements (one-liner output by default, `-Detailed`, folder path auto-resolution) — see `role-manage.md` → "Recent Additions".

## MCP Integration

- **metadatasearch** — Verify command and subsystem names referenced in the interface configuration.
- **get_metadata_details** — Get object structure for verifying command targets.
