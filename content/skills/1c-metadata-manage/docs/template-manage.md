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
| Lang | no | `ru` | HTML only: language code of the page. A second call with another `-Lang` on an existing HTML template adds a page. Letters, digits, `-`, `_`; paths and Windows device names are refused before any write |
| SrcDir | no | `src` | Source directory |
| SetMainSKD | no | off | DataCompositionSchema on a Report / ExternalReport: overwrite a non-empty `MainDataCompositionSchema` (an empty one is always filled) |

### Command (EPF)

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-template-manage/scripts/add-template.ps1 -ProcessorName "<ObjectName>" -TemplateName "<TemplateName>" -TemplateType "<TemplateType>" [-Synonym "<Synonym>"] [-Lang "<lang>"] [-SrcDir "<SrcDir>"] [-SetMainSKD]
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
| HTML | HTMLDocument | `Template.xml` + `Template/<lang>.html` | Descriptor + empty HTML page |
| Text, text document | TextDocument | `.txt` | Empty file |
| SpreadsheetDocument, MXL, spreadsheet | SpreadsheetDocument | `.xml` | Minimal spreadsheet |
| BinaryData, binary | BinaryData | `.bin` | Empty file |
| DataCompositionSchema, DCS, СКД | DataCompositionSchema | `.xml` | Minimal schema with one local data source |

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
        ├── Template.<ext>          # Template content (HTML: the page descriptor)
        └── Template/<lang>.html    # HTML only: the page itself
```

**HTML layout.** The platform stores an HTML template like help: `Ext/Template.xml` is an `extrnprops` `<Help>` descriptor listing `<Page>` entries, the text lives in `Ext/Template/<lang>.html` (pictures beside it in `_files/`). A single `Ext/Template.html` — what older versions of this tool wrote — is **silently ignored**: the load succeeds and the template is empty. Adding a language to such a template migrates the old file to `Template/ru.html` with a `[WARN]`; if both the old file and `Template/ru.html` exist, the tool refuses and leaves the choice to you. An existing page is never overwritten; a language that is already listed and has its page is refused.

**Format version** of the template metadata and the HTML descriptor is the owner's (`<ObjectName>.xml`, an EPF/ERF root included), then `Configuration.xml`; `2.21` adds the `xmlns:pal` header.

An existing template is refused (except an HTML template getting another language), and so is a locked vendor object (support guard, [support-manage.md](support-manage.md)).

### What Gets Modified

- `<SrcDir>/<ObjectName>.xml` — adds `<Template>` to `ChildObjects`: after the last existing template, otherwise at the canonical place of the owner kind (before `Command`; for an external data source table — after it). Already registered — skipped. Other bytes of the file are kept (BOM, EOL, compact `<a/>` tags)
- Report / ExternalReport with a DataCompositionSchema template — `MainDataCompositionSchema`, see `SetMainSKD`

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

The script refuses a real deletion without `-Force` (exit `2`) and a template that is not registered in `ChildObjects` (exit `1`). It parses and serializes the parent XML before mutating the source tree, writes it through a temporary file, then deletes the template files. An emptied `ChildObjects` becomes `<ChildObjects/>`, the file keeps its EOL and compact tags. Run the relevant metadata / MXL / DCS validator after execution. There is no support guard on removal — check the object's support state yourself before removing a template from a typical configuration.

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

Scripts vendored from Nikolay-Shirokov/cc-1c-skills; sync history — `docs/CHANGELOG.md`.
