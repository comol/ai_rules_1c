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
- `Configuration.xml` or parent subsystem — registration in `<ChildObjects>`

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

### Checks (13)

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

Exit code: 0 = OK, 1 = errors.

---

## Typical Workflow

```
1c-subsystem-manage compile   — create subsystem
1c-subsystem-manage validate  — check correctness
1c-subsystem-manage edit      — add objects to content
1c-subsystem-manage info      — view structure
```

## Recent Additions (upstream `w-2026-05-17`)

The PowerShell scripts under `tools/1c-subsystem-manage/scripts/` were refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights:

- **`subsystem-compile` / `subsystem-edit`** — content of a subsystem accepts Russian and plural prefixes (`Справочник`, `Справочники`, `Catalogs`) and normalises them to the canonical `Catalog`. `subsystem-validate` flags surviving plural forms as an error.
- **Stub-files for child subsystems** are created automatically when the parent declares a child. Previously the `<Subsystems>` reference existed but the file did not — the platform silently ignored it, and stricter loaders started failing.
- Subsystem `objects` accepts `content` as a synonym (and vice versa).
- Validators got the universal improvements described in `role-manage.md` → "Recent Additions" (one-liner output by default, `-Detailed`, folder path auto-resolution).

## MCP Integration

- **get_object_dossier** — Comprehensive structural passport of objects before inclusion (structure, forms, dependencies, subscriptions, roles).
- **metadatasearch** — Verify that objects referenced in subsystem content exist in the configuration.
- **get_metadata_details** — Get structure of objects being included in the subsystem.
- **trace_impact** — Recursive dependency analysis for subsystem composition: find all objects that depend on or are depended upon by the objects being included (preferred over `graph_dependencies` for deep analysis).
- **graph_dependencies** — Flat dependency overview between objects.
- **business_search** — Find related objects to include by natural language description.

## SDD Integration

When creating or modifying subsystems as part of a feature, update SDD artifacts if present (see `content/rules/sdd-integrations.md` for detection):

- **OpenSpec**: Add spec deltas describing subsystem purpose and included objects in `openspec/changes/`.
