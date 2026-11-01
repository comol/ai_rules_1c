# 1C Subsystem Manage — Create, Edit, Analyze, Validate Subsystems

Comprehensive subsystem management: create from JSON, edit content/properties, analyze structure, validate correctness.

---

## 1. Compile — Create Subsystem from JSON

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-subsystem-manage/scripts/subsystem-compile.ps1 -Value '<json>' -OutputDir '<ConfigDir>'
```

| Parameter | Description |
|-----------|-------------|
| `DefinitionFile` | Path to JSON definition file |
| `Value` | Inline JSON string (alternative to DefinitionFile) |
| `OutputDir` | Export root (where `Subsystems/`, `Configuration.xml` are) |
| `Parent` | Path to parent subsystem XML (for nested subsystems) |
| `NoValidate` | Skip auto-validation |

### JSON Definition

```json
{
  "name": "МояПодсистема",
  "synonym": "Моя подсистема",
  "includeInCommandInterface": true,
  "picture": "CommonPicture.МояКартинка",
  "content": ["Catalog.Товары", "Document.Заказ"],
  "children": ["ChildA", "ChildB"]
}
```

Minimal: only `name` required. Everything else has defaults.

### What Gets Generated

- `{OutputDir}/Subsystems/{Name}.xml` — subsystem definition
- `{OutputDir}/Subsystems/{Name}/` — directory (if children exist)
- `Configuration.xml` or parent subsystem — registration in `<ChildObjects>`, inserted as raw text (the rest of the parent file stays byte-identical). In `Configuration.xml` the new subsystem goes to the end of the `Subsystem` group, never by name: subsystem order is the order of sections in the panel
- Stub files for declared `children` that do not exist yet; format version follows the configuration (`Configuration.xml`), including the `xmlns:pal` header of 2.21

Both `subsystem-compile` and `subsystem-edit` refuse to change a locked vendor configuration (support guard, [support-manage.md](support-manage.md)). Auto-validation runs `subsystem-validate` from the same `scripts` directory; its non-zero exit (or a missing validator) is the tool's exit code — the file is already written.

---

## 2. Edit — Modify Existing Subsystem

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-subsystem-manage/scripts/subsystem-edit.ps1 -SubsystemPath '<path>' -Operation <op> -Value '<value>'
```

| Parameter | Description |
|-----------|-------------|
| `SubsystemPath` | Path to subsystem XML file |
| `Operation` | Operation (see table) |
| `Value` | Value for operation |
| `DefinitionFile` | JSON file with operation array |
| `NoValidate` | Skip auto-validation |

### Operations

| Operation | Value | Description |
|-----------|-------|-------------|
| `add-content` | `"Catalog.X"` or `["Catalog.X","Document.Y"]` | Add objects to Content |
| `remove-content` | `"Catalog.X"` or `["Catalog.X"]` | Remove objects from Content |
| `add-child` | `"SubsystemName"` | Add child subsystem to ChildObjects |
| `remove-child` | `"SubsystemName"` | Remove child subsystem |
| `set-property` | `{"name":"prop","value":"val"}` | Change property (Synonym, IncludeInCommandInterface, etc.) |

Operation names are case-insensitive (`Add-Content` works). Content items accept Russian and plural kinds (`Справочник.X`, `Catalogs.X`) and are normalised to `Catalog.X`.

---

## 3. Info — Analyze Subsystem Structure

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-subsystem-manage/scripts/subsystem-info.ps1 -SubsystemPath "<path>"
```

| Parameter | Description |
|-----------|-------------|
| `SubsystemPath` | Path to subsystem XML, subsystem directory, or `Subsystems/` directory (for tree) |
| `Mode` | `overview` (default), `content`, `ci`, `tree`, `full` |
| `Name` | Drill-down: object type in content, section in ci, subsystem name in tree |

### Five Modes

| Mode | What It Shows |
|------|---------------|
| `overview` | Compact summary: properties, content (grouped by type), children, CI presence |
| `content` | Content list grouped by object type. `-Name Catalog` — catalogs only |
| `ci` | CommandInterface.xml breakdown: visibility, placement, command/subsystem/group order |
| `tree` | Recursive hierarchy tree with markers [CI], [OneCmd], [Hidden] |
| `full` | Full summary: overview + content + ci in one call |

---

## 4. Validate — Check Subsystem Correctness

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-subsystem-manage/scripts/subsystem-validate.ps1 -SubsystemPath '<path>'
```

| Parameter | Description |
|-----------|-------------|
| `SubsystemPath` | Subsystem XML (first positional argument) |
| `Detailed` | Show passing checks too |
| `MaxErrors` | Stop after N errors (default 30) |
| `OutFile` | Write the report to a file (UTF-8 BOM) |

### Checks (14)

1. XML well-formedness + root structure (MetaDataObject/Subsystem)
2. Properties — 9 required properties
3. Name — non-empty, valid identifier
4. Synonym — non-empty
5. Boolean properties — contain true/false
6. Content — xr:Item format, xsi:type
7. Content — no duplicates
8. ChildObjects — elements non-empty
9. ChildObjects — no duplicates
10. ChildObjects → files exist
11. CommandInterface.xml — well-formedness
12. Picture — reference format
13. UseOneCommand=true → exactly 1 Content element
14. Format version — every stamped body in `Subsystems/<Name>/Ext/*.xml` (`CommandInterface.xml`, `Help.xml`) has the descriptor's version (ERROR: the platform refuses mixed formats inside one object); a descriptor that differs from `Configuration.xml` is only a WARN (loads, but the dump is no longer uniform)

Exit code: 0 = OK, 1 = errors.

---

## Typical Workflow

```
1c-subsystem-manage compile   — create subsystem
1c-subsystem-manage validate  — check correctness
1c-subsystem-manage edit      — add objects to content
1c-subsystem-manage info      — view structure
```

Scripts vendored from Nikolay-Shirokov/cc-1c-skills; sync history — `docs/CHANGELOG.md`.
