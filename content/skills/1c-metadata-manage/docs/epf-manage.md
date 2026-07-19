# 1C EPF/ERF Manage — Scaffold, Build, Dump, Validate

Comprehensive external data processor (EPF) and external report (ERF) management: create empty scaffold, compile from XML, disassemble to XML, validate correctness.

---

## 1. Scaffold EPF — Create Empty Data Processor

Generates the minimal set of XML source files for a 1C external data processor: root metadata file and the processor directory structure.

### Usage

```
1c-epf-scaffold <Name> [Synonym] [SrcDir]
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| Name | yes | — | Processor name (Latin/Cyrillic) |
| Synonym | no | = Name | Synonym (display name) |
| SrcDir | no | `src` | Source directory relative to CWD |

### Command

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-epf-scaffold/scripts/init.ps1 -Name "<Name>" [-Synonym "<Synonym>"] [-SrcDir "<SrcDir>"]
```

### What Gets Created

```
<SrcDir>/
├── <Name>.xml          # Root metadata file (4 UUIDs)
└── <Name>/
    └── Ext/
        └── ObjectModule.bsl  # Object module with 3 regions
```

- Root XML contains `MetaDataObject/ExternalDataProcessor` with empty `DefaultForm` and `ChildObjects`
- ClassId is fixed: `c3831ec8-d8d5-4f93-8a22-f9bfae07327f`
- File is created in UTF-8 with BOM

### Next Steps

After scaffolding, use these skills to build out the processor:

- **Add a form**: `1c-form-scaffold` skill
- **Add a template/layout**: `1c-template-manage` skill
- **Register with SSL (BSP)**: `bsp-manage.md` section 1 «Registration»
- **Build EPF**: `1c-epf-build` skill
- **Validate**: `1c-epf-validate` skill

---

## 2. Scaffold ERF — Create Empty External Report

Generates the minimal set of XML source files for a 1C external report: root metadata file, the report directory structure, and optionally an empty Data Composition Schema (DCS).

### Usage

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-erf-scaffold/scripts/init.ps1 -Name "<Name>" [-Synonym "<Synonym>"] [-SrcDir "<SrcDir>"] [-WithSKD]
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| Name | yes | — | Report name (Latin/Cyrillic) |
| Synonym | no | = Name | Synonym (display name) |
| SrcDir | no | `src` | Source directory relative to CWD |
| WithSKD | no | — | Create empty DCS and bind to MainDataCompositionSchema |

### What Gets Created

```
<SrcDir>/
├── <Name>.xml          # Root metadata file (4 UUIDs)
└── <Name>/
    └── Ext/
        └── ObjectModule.bsl  # Object module with 3 regions
```

With `--WithSKD` additionally:

```
<SrcDir>/<Name>/
    Templates/
    ├── ОсновнаяСхемаКомпоновкиДанных.xml        # Template metadata
    └── ОсновнаяСхемаКомпоновкиДанных/
        └── Ext/
            └── Template.xml                      # Empty DCS
```

- Root XML contains `MetaDataObject/ExternalReport` with empty `DefaultForm`, `MainDataCompositionSchema`, and `ChildObjects`
- With `--WithSKD` — `MainDataCompositionSchema` is filled with template reference, `ChildObjects` contains `<Template>`
- ClassId is fixed: `e41aff26-25cf-4bb6-b6c1-3f478a75f374`
- File is created in UTF-8 with BOM

### Next Steps

After scaffolding, use these skills to build out the report:

- **Add a form**: `1c-form-scaffold` skill
- **Add/edit DCS**: `1c-skd-compile` or `1c-skd-edit` skill
- **Add a template/layout**: `1c-template-manage` skill
- **Add help**: `1c-help-manage` skill
- **Build ERF**: `1c-epf-build` skill (same script for EPF and ERF)
- **Validate**: `1c-epf-validate` skill (auto-detects ERF)

---

## 3. Build — Compile from XML Sources

Builds an EPF or ERF file from XML sources using the 1C platform. The same script handles both data processors and reports.

### Usage

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-epf-build/scripts/epf-build.ps1 <parameters>
```

| Parameter | Required | Description |
|-----------|:--------:|-------------|
| `-V8Path <path>` | no | Platform bin directory (auto-detect if not set) |
| `-InfoBasePath <path>` | * | File infobase |
| `-InfoBaseServer <server>` | * | 1C server (for server databases) |
| `-InfoBaseRef <name>` | * | Database name on server |
| `-UserName <name>` | no | User name |
| `-Password <password>` | no | Password |
| `-SourceFile <path>` | yes | Path to root XML source file |
| `-OutputFile <path>` | yes | Path to output EPF/ERF file |

> `*` — either `-InfoBasePath` or the `-InfoBaseServer` + `-InfoBaseRef` pair is required.

### Database Resolution

Read `.v8-project.json` from the project root (see `1c-db-manage` skill for the full algorithm). If no databases are configured — create an empty infobase in `./base`.

### Return Codes

| Code | Description |
|------|-------------|
| 0 | Successful build |
| 1 | Error (check log) |

### Reference Types

If the processor/report uses configuration reference types (`CatalogRef.XXX`, `DocumentRef.XXX`) — building in an empty database will fail with an XDTO error. Register a database with the target configuration via `1c-db-manage add`.

### Examples

```powershell
# Build data processor (file database)
... -InfoBasePath "C:\Bases\MyDB" -SourceFile "src\МояОбработка.xml" -OutputFile "build\МояОбработка.epf"

# Build report (server database)
... -InfoBaseServer "srv01" -InfoBaseRef "MyDB" -UserName "Admin" -Password "secret" -SourceFile "src\МойОтчёт.xml" -OutputFile "build\МойОтчёт.erf"
```

### Verification

After building, test by running: `1c-db-ops db-run ... -Execute build/MyProcessor.epf`

---

## 4. Dump — Disassemble to XML Sources

Disassembles an EPF or ERF file into XML sources using the 1C platform (hierarchical format). The same script handles both data processors and reports.

### Usage

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-epf-dump/scripts/epf-dump.ps1 <parameters>
```

| Parameter | Required | Description |
|-----------|:--------:|-------------|
| `-V8Path <path>` | no | Platform bin directory (auto-detect if not set) |
| `-InfoBasePath <path>` | * | File infobase |
| `-InfoBaseServer <server>` | * | 1C server |
| `-InfoBaseRef <name>` | * | Database name on server |
| `-UserName <name>` | no | User name |
| `-Password <password>` | no | Password |
| `-InputFile <path>` | yes | Path to EPF/ERF file |
| `-OutputDir <path>` | yes | Directory for XML source output |
| `-Format <format>` | no | `Hierarchical` (default) / `Plain` |

> `*` — either `-InfoBasePath` or the `-InfoBaseServer` + `-InfoBaseRef` pair is required.

### Database Resolution

Read `.v8-project.json` from the project root (see `1c-db-manage` skill). If no databases — create an empty infobase in `./base`.

### Hierarchical Format Output

```
<OutDir>/
├── <Name>.xml                    # Root file
└── <Name>/
    ├── Ext/
    │   └── ObjectModule.bsl      # Object module (if exists)
    ├── Forms/
    │   ├── <FormName>.xml
    │   └── <FormName>/
    │       └── Ext/
    │           ├── Form.xml
    │           └── Form/
    │               └── Module.bsl
    └── Templates/
        ├── <TemplateName>.xml
        └── <TemplateName>/
            └── Ext/
                └── Template.<ext>
```

### Return Codes

| Code | Description |
|------|-------------|
| 0 | Successful dump |
| 1 | Error (check log) |

### Examples

```powershell
# Dump data processor
... -InfoBasePath "C:\Bases\MyDB" -InputFile "build\МояОбработка.epf" -OutputDir "src"

# Dump report
... -InfoBasePath "C:\Bases\MyDB" -InputFile "build\МойОтчёт.erf" -OutputDir "src"
```

---

## 5. Validate — Check Correctness

Checks structural correctness of XML sources for external data processors (EPF) and external reports (ERF): root structure, InternalInfo, properties, ChildObjects, attributes, tabular sections, name uniqueness, form/template file existence.

The script auto-detects the type (ExternalDataProcessor or ExternalReport).

### Usage

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-epf-validate/scripts/epf-validate.ps1 -ObjectPath "<path>"
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| ObjectPath | yes | — | Path to root XML or processor/report directory |
| MaxErrors | no | 30 | Stop after N errors |
| OutFile | no | — | Write result to file (UTF-8 BOM) |

`ObjectPath` auto-resolve: if a directory is given — looks for `<dirName>/<dirName>.xml`.

### Checks Performed

| # | Check | Severity |
|---|-------|----------|
| 1 | Root structure: MetaDataObject/ExternalDataProcessor or ExternalReport | ERROR |
| 2 | InternalInfo: ClassId, ContainedObject, GeneratedType | ERROR / WARN |
| 3 | Properties: Name (identifier), Synonym, DefaultForm, MainDataCompositionSchema (ERF) | ERROR / WARN |
| 4 | ChildObjects: allowed types, order | ERROR / WARN |
| 5 | Cross-references: DefaultForm → Form, MainDCS → Template (ERF) | ERROR / WARN |
| 6 | Attributes: UUID, Name, Type | ERROR |
| 7 | TabularSections: UUID, Name, GeneratedType, Attributes | ERROR / WARN |
| 8 | Name uniqueness (Attribute, TS, Form, Template, Command) | ERROR |
| 9 | Files: forms (.xml + Ext/Form.xml), templates | ERROR |
| 10 | Form descriptors: root structure, uuid, Name, FormType | ERROR / WARN |

Exit code: 0 = all checks passed, 1 = errors found.

### When to Use

- **After scaffolding**: verify the scaffold
- **After adding form/template**: ensure ChildObjects, files, and references are correct
- **After manual XML editing**: detect structural errors before building
- **When debugging builds**: find the cause of Designer errors

---

## Typical Workflow

### Data Processor

```
1c-epf-scaffold <Name>                — create processor
1c-epf-validate src/<Name>.xml        — check result
1c-epf-build <Name>                   — build EPF
```

### Report

```
1c-erf-scaffold <Name> --with-skd    — create report with DCS
1c-epf-validate src/<Name>.xml        — check result (same script)
1c-epf-build <Name>                   — build ERF
```

### Fix a Bug in a Data Processor

1. Dump: `db-dump-xml` or use `1c-epf-dump`
2. Edit BSL files
3. Build: `1c-epf-build`
4. Test: `db-run` with the built EPF

---

## Recent Additions (upstream `w-2026-05-17`)

The PowerShell script `tools/1c-epf-validate/scripts/epf-validate.ps1` was refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights:

- **Format version auto-detection** from the nearest `Configuration.xml` (8.3.27+, 8.5).
- **Platform 8.5** support across `epf-validate` and `erf-validate` (new compatibility-mode and interface-mode values, new XML header format).
- **Universal validator improvements** — one-liner output by default (`-Detailed` for the full per-check trace); accepts both an XML file and a folder path as the primary argument; universal `-Path` parameter alongside legacy `-ObjectPath`.
- The same script handles `erf-validate` — upstream `erf-validate` is a thin pass-through to `epf-validate.ps1`, the script auto-detects `ExternalReport` vs `ExternalDataProcessor` from the root XML element. No separate `erf-validate.ps1` is shipped.

## MCP Integration

- **metadatasearch** — Verify metadata object names and types when setting up the processor/report for integration with existing configuration objects.
- **get_metadata_details** — Get full structure of target metadata objects for integration.
- **check_1c_code** — Verify BSL code for syntax, logic and performance issues before building; analyze code in extracted modules after dumping.
- **review_1c_code** — Check code style and ITS standards compliance before building.
- **syntaxcheck** — BSL syntax verification before building.
- **docsearch** — Look up valid property values when investigating validation errors.

## SDD Integration

When creating external processors or reports as part of a feature, update SDD artifacts if present (see `content/rules/sdd-integrations.md` for detection):

- **OpenSpec**: Add spec deltas describing the processor/report purpose, parameters, and target objects in `openspec/changes/`.
