# 1C Template Manage — Add/Remove Templates

Creates or removes a template (layout) of specified type and registers/unregisters it in the root XML of a 1C metadata object. Works with any object type that supports templates: DataProcessor, Document, Catalog, Report, etc.

## Adding a Template

```
1c-template-manage add <ObjectName> <TemplateName> <TemplateType>
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| ObjectName | yes | — | Object name, or absolute / relative path to the object's `.xml` file; alias `ProcessorName` |
| TemplateName | yes | — | Template name |
| TemplateType | yes | — | Type: HTML, Text, SpreadsheetDocument, BinaryData, DataCompositionSchema |
| Synonym | no | = TemplateName | Template synonym |
| SrcDir | no | `src` | Source directory |
| SetMainSKD | no | off | `DataCompositionSchema` on a Report / ExternalReport: also overwrite `MainDataCompositionSchema` when it already points at another template (see below) |

### Command (EPF)

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-template-manage/scripts/add-template.ps1 -ProcessorName "<ObjectName>" -TemplateName "<TemplateName>" -TemplateType "<TemplateType>" [-Synonym "<Synonym>"] [-SrcDir "<SrcDir>"]
```

### Command (configuration or extension object)

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-template-manage/scripts/add-template.ps1 -ObjectName "SNiS/Documents/эс_ПланПотребностейВМатериалах.xml" -TemplateName "ПФ_КомплектовочнаяВедомость" -TemplateType SpreadsheetDocument
```

A relative XML path is resolved from the current directory, then from `SrcDir`. The descriptor and content are created beside that XML under `<ObjectName>/Templates/`; `SrcDir` is not required for an existing XML path. Name-only calls retain EPF lookup and lookup in configuration object-type folders under `SrcDir`.

`meta-edit add-template` is refused before any mutation in both runtimes; use this scaffold and select `TemplateType` explicitly. This scaffold currently ships as PowerShell only.

### Type Mapping

User may specify type in free form. Determine the correct one from context:

| User Input | TemplateType | Extension | Content |
|------------|-------------|-----------|---------|
| HTML | HTMLDocument | `.html` | Empty HTML document |
| Text, text document | TextDocument | `.txt` | Empty file |
| SpreadsheetDocument, MXL, spreadsheet | SpreadsheetDocument | `.xml` | Minimal spreadsheet |
| BinaryData, binary | BinaryData | `.bin` | Empty file |
| DataCompositionSchema, DCS, SKD | DataCompositionSchema | `.xml` | Empty schema with one local data source (`ИсточникДанных1`) |

**`DataCompositionSchema`** creates only the scaffold: a schema with a data source and no data sets. Build the real content with `1c-skd-compile` straight into the created `Template.xml` ([skd-manage.md](skd-manage.md)), then run `1c-skd-validate`. For a `Report` or `ExternalReport` the script also fills `MainDataCompositionSchema` of the object with `<Report|ExternalReport>.<Name>.Template.<TemplateName>` when that property is empty; a property that already names a template is kept unless `-SetMainSKD` is passed. For other object types nothing besides the registration changes.

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

---

## Removing a Template

```
1c-template-manage remove <ObjectName> <TemplateName> [-DryRun | -Force]
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| ObjectName | yes | — | Object name |
| TemplateName | yes | — | Template name to remove |
| SrcDir | no | `src` | Source directory |
| DryRun | no | off | Print the parent XML and files that would change; do not mutate anything |
| Force | required to delete | off | Confirm the reviewed removal plan and perform it |

### Commands (preview first, then execute)

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-template-manage/scripts/remove-template.ps1 -ProcessorName "<ObjectName>" -TemplateName "<TemplateName>" [-SrcDir "<SrcDir>"] -DryRun
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-template-manage/scripts/remove-template.ps1 -ProcessorName "<ObjectName>" -TemplateName "<TemplateName>" [-SrcDir "<SrcDir>"] -Force
```

The script refuses a real deletion without `-Force`. It parses and serializes the parent XML before mutating the source tree, then removes the registration before deleting template files. Run the relevant metadata / MXL / DCS validator after execution.

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

For DataCompositionSchema: `1c-skd-compile` generates the content, then `1c-skd-validate` and `1c-skd-info` — see [skd-manage.md](skd-manage.md).

Scripts vendored from Nikolay-Shirokov/cc-1c-skills; sync history — `docs/CHANGELOG.md`.
