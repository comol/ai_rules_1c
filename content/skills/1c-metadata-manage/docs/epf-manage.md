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
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-epf-scaffold/scripts/init.ps1 -Name "<Name>" [-Synonym "<Synonym>"] [-SrcDir "<SrcDir>"] [-FormatVersion "2.17"]
```

`-FormatVersion` (default `2.17`) is the dump format of the scaffold: a standalone EPF has no `Configuration.xml` to inherit it from, and the form / template / help tools read the version from this root file. Tested range `2.17`–`2.21`; outside it the scaffold is still emitted, with a warning on stderr; a malformed value exits 1. Use the version of the platform that will build it (`2.17` = 8.3.24, `2.21` = 8.5). The synonym is XML-escaped (`&`, `<`, `>`).

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
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-erf-scaffold/scripts/init.ps1 -Name "<Name>" [-Synonym "<Synonym>"] [-SrcDir "<SrcDir>"] [-WithSKD] [-BspForms] [-FormatVersion "2.17"]
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| Name | yes | — | Report name (Latin/Cyrillic) |
| Synonym | no | = Name | Synonym (display name) |
| SrcDir | no | `src` | Source directory relative to CWD |
| WithSKD | no | — | Create empty DCS and bind to MainDataCompositionSchema |
| BspForms | no | — | Main, settings and variant forms = БСП common forms `CommonForm.ФормаОтчета` / `ФормаНастроекОтчета` / `ФормаВариантаОтчета` |
| FormatVersion | no | `2.17` | Dump format version, as for the EPF scaffold above |

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
- With `-BspForms` — `DefaultForm`, `DefaultSettingsForm`, `DefaultVariantForm` name the БСП common forms. External reports may reference common forms of the configuration (Designer: «Формы → Основные»); the reference resolves by name in the infobase the report is built in or opened from
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
| `-Checks <list>` | no | Source check before the build: `modules` (syntax), `handlers` (form handlers exist), `unreferenced`, `empty-handlers`, `config` (integrity, references); `off` — no check. Default `modules,handlers` |
| `-Context <list>` | no | Contexts of the `modules` check. Default `ThinClient,Server` |
| `-ConfigSrc <path>` | no | XML dump of the configuration the processor will run in — its common modules become visible to the check. Default: `.dev.env` `EXPORT_PATH`, then `configSrc` of the `.v8-project.json` record |

> `*` — optional. Without a connection the script creates a temporary stub infobase (metadata stubs for the referenced types) and deletes it after the build.

### Database Resolution

Take the infobase and platform from `.dev.env` (`INFOBASE_PATH`, `PLATFORM_PATH`; see [db-manage.md](db-manage.md) for the full resolution order). If no infobase is configured, omit the connection: the stub infobase is created automatically.

### Source Check Before the Build

`/LoadExternalDataProcessorOrReportFromFiles` only packs XML and modules — it compiles nothing, so a broken module used to reach the user and fail when the processor was opened. The platform has no "check an external processor" command, but it checks a **configuration** object. So by default `epf-build` embeds the processor into the configuration of a temporary stub infobase (`stub-db-create -EmbedSourceFile`; the copy gets its own GUIDs) and runs `/CheckConfig` (with `/DumpResult`) before building:

- Findings cancel the build (exit 1, no output file). Each platform line is printed with the source file it points to (`-> …\Ext\ObjectModule.bsl`).
- With an explicit `-InfoBasePath` the check runs in its own temporary infobase — the processor is never put into the configuration of your base — and the build then runs in your base.
- Common modules: code that calls a configuration common module (`ОбщегоНазначения.…`) fails the check as «Переменная не определена» unless the check sees the configuration dump. The stub gets an empty double (real context flags, no body) of every common module the code names that exists in `-ConfigSrc` / `EXPORT_PATH` / `configSrc`; a name missing from the dump stays an error, with a `[hint]`. Code calling methods of a **global** common module without the module name fails even with the dump — build it with `-Checks off`.
- Common forms (`CommonForm.<Name>` in `DefaultForm` etc.) get empty stubs in the check infobase too, so БСП reports pass (checked on 8.3.27.2130 with `erf-init -BspForms`).
- **Cost**: on 8.3.27.2130 a minimal processor took ~11 s with the check against ~4–5 s with `-Checks off` (stub with the embedded object + `/CheckConfig`; with `-InfoBasePath` a separate check infobase is created, ~12 s against ~4 s). Larger processors and dumps add to that.
- **Switching it off**: `-Checks off` for one build; `.v8-project.json` `externalCheck: false` for the project. Keep it on for anything that is handed to a user.

The check runs through 1cv8 only: an `ibcmd` build takes the `1cv8.exe` next to it and skips the check with a note when there is none.

### Return Codes

| Code | Description |
|------|-------------|
| 0 | Successful build |
| 1 | Error (check log), findings of the source check, any unhandled script error |

### Reference Types

If the processor/report uses configuration reference types (`CatalogRef.XXX`, `DocumentRef.XXX`), the stub infobase gets metadata stubs for them (catalogs, documents, registers with the record-set columns forms use, defined types…). The stub configuration takes its dump format from the sources (never newer than `2.17`) and the matching compatibility mode (`2.13` → `Version8_3_20` … `2.16` → `Version8_3_23`, otherwise `Version8_3_24`), so sources dumped by an older platform build on that platform. When the stubs cannot describe the configuration well enough, build against an infobase with the target configuration (`-InfoBasePath`).

### Common Forms

`DefaultForm` / `DefaultSettingsForm` / `DefaultVariantForm` (and the auxiliary ones) may be `CommonForm.<Name>` — a common form of the configuration, as БСП reports use. The platform refuses the build in an infobase without that form («Неизвестный объект метаданных - CommonForm.<Name>»). Without an explicit infobase the stub database gets an empty common form of each referenced name, so the build passes; the reference is stored by name and resolves to the real form of the configuration the report is opened in (checked on 8.3.27).

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

Take the infobase and platform from `.dev.env` (see [db-manage.md](db-manage.md)). If no infobase is configured — create an empty infobase in `./base`.

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

`ObjectPath` auto-resolve: if a directory is given — looks for `<dirName>/<dirName>.xml`. Check 5 accepts `CommonForm.<Name>` in `DefaultForm` (a configuration common form, resolved by name in the build infobase).

### Checks Performed

| # | Check | Severity |
|---|-------|----------|
| 1 | Root structure: MetaDataObject/ExternalDataProcessor or ExternalReport | ERROR |
| 2 | InternalInfo: ClassId, ContainedObject, GeneratedType | ERROR / WARN |
| 3 | Properties: Name (identifier), Synonym, DefaultForm, MainDataCompositionSchema (ERF) | ERROR / WARN |
| 4 | ChildObjects: allowed types, order; a `Command` is an error (external objects have no object commands — the platform drops it on build) | ERROR / WARN |
| 5 | Cross-references: DefaultForm → Form, MainDCS → Template (ERF) | ERROR / WARN |
| 6 | Attributes: UUID, Name, Type | ERROR |
| 7 | TabularSections: UUID, Name, GeneratedType, Attributes | ERROR / WARN |
| 8 | Name uniqueness (Attribute, TS, Form, Template, Command) | ERROR |
| 9 | Files: forms (.xml + Ext/Form.xml), templates; `Ext/ManagerModule.bsl` is an error (no manager module — the platform drops it silently) | ERROR |
| 10 | Form descriptors: root structure, uuid, Name, FormType | ERROR / WARN |
| 11 | Format version: a stamped body (`Ext/Form.xml`, `Ext/Template.xml`, `Ext/Help.xml`) in another version than its descriptor is an error (the platform refuses the build); a form or template in another version than the root is a warning | ERROR / WARN |

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

Scripts vendored from Nikolay-Shirokov/cc-1c-skills; sync history — `docs/CHANGELOG.md`.
