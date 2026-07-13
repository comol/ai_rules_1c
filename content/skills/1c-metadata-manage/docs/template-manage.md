# 1C Template Manage — Add/Remove Templates

Creates or removes a template (layout) of specified type and registers/unregisters it in the root XML of a 1C metadata object. Works with any object type that supports templates: DataProcessor, Document, Catalog, Report, etc.

## Adding a Template

```
1c-template-manage add <ObjectName> <TemplateName> <TemplateType>
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| ObjectName (alias `ProcessorName`) | yes | — | Object name (for EPF) or object path |
| TemplateName | yes | — | Template name |
| TemplateType | yes | — | Type: HTML, Text, SpreadsheetDocument, BinaryData, DataCompositionSchema |
| Synonym | no | = TemplateName | Template synonym |
| SrcDir | no | `src` | Source directory |
| SetMainSKD | no | — | Force-set `MainDataCompositionSchema` even if it already has a value (see below) |

### Command (EPF)

```powershell
pwsh -NoProfile -File skills/1c-metadata-manage/tools/1c-template-manage/scripts/add-template.ps1 -ObjectName "<ObjectName>" -TemplateName "<TemplateName>" -TemplateType "<TemplateType>" [-Synonym "<Synonym>"] [-SrcDir "<SrcDir>"] [-SetMainSKD]
```

### Type Mapping

User may specify type in free form. Determine the correct one from context:

| User Input | TemplateType | Extension | Content |
|------------|-------------|-----------|---------|
| HTML | HTMLDocument | `.html` | Empty HTML document |
| Text, text document | TextDocument | `.txt` | Empty file |
| SpreadsheetDocument, MXL, spreadsheet | SpreadsheetDocument | `.xml` | Minimal spreadsheet |
| BinaryData, binary | BinaryData | `.bin` | Empty file |
| DataCompositionSchema, DCS | DataCompositionSchema | `.xml` | Minimal DCS schema |

### MainDataCompositionSchema (Automatic)

When adding a `DataCompositionSchema` template to an `ExternalReport` or `Report`:
- If `MainDataCompositionSchema` is empty, it is automatically filled with a reference to the new template.
- Use `-SetMainSKD` to overwrite an existing value.

### Print Form Naming Convention

For **print form** templates (SpreadsheetDocument type), apply the prefix `PF_MXL_`:

| Context | Name Format | Example |
|---------|-------------|---------|
| Print form (additional data processor of PrintForm kind, or user explicitly says "print form") | `PF_MXL_<ShortName>` | `PF_MXL_M11`, `PF_MXL_Invoice`, `PF_MXL_EnvelopeDL` |
| Other templates (data import, service, settings) | No prefix | `ImportTemplate`, `PrintSettings` |

If user provides a name without prefix but context is a print form, **add the `PF_MXL_` prefix automatically** and notify.

### What Gets Created

```
<SrcDir>/<ObjectName>/Templates/
├── <TemplateName>.xml              # Template metadata (1 UUID)
└── <TemplateName>/
    └── Ext/
        └── Template.<ext>          # Template content
```

### What Gets Modified

- `<SrcDir>/<ObjectName>.xml` — adds `<Template>` to the end of `ChildObjects`
- For ExternalReport/Report: `MainDataCompositionSchema` may be updated (see above)

---

## Removing a Template

```
1c-template-manage remove <ObjectName> <TemplateName>
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| ObjectName | yes | — | Object name |
| TemplateName | yes | — | Template name to remove |
| SrcDir | no | `src` | Source directory |

### Command (EPF)

```powershell
pwsh -NoProfile -File skills/1c-metadata-manage/tools/1c-template-manage/scripts/remove-template.ps1 -ProcessorName "<ObjectName>" -TemplateName "<TemplateName>" [-SrcDir "<SrcDir>"]
```

### What Gets Removed

```
<SrcDir>/<ObjectName>/Templates/<TemplateName>.xml     # Template metadata
<SrcDir>/<ObjectName>/Templates/<TemplateName>/         # Template directory (recursive)
```

### What Gets Modified

- `<SrcDir>/<ObjectName>.xml` — removes `<Template>` from `ChildObjects`

---

## Workflow

1. `1c-template-manage add` — create template scaffold
2. For SpreadsheetDocument: use `1c-mxl-compile` to generate the template content
3. `1c-mxl-validate` — validate template structure
4. `1c-mxl-info` — analyze template structure

## MCP Integration

- **metadatasearch** — Verify the parent object exists and supports templates.
- **get_metadata_details** — Get parent object structure to confirm template compatibility.
- **templatesearch** — Find similar template implementations.
