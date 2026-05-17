# 1C Metadata Manage — Compile, Edit, Info, Remove, Validate

Operations for creating, modifying, analyzing, removing, and validating 1C metadata objects from configuration XML export.

---
## 1. Compile — Create from JSON

Takes a JSON definition of a metadata object and generates XML + modules in the configuration export structure, then registers it in Configuration.xml.

## Parameters and Command

| Parameter | Description |
|-----------|-------------|
| `JsonPath` | Path to the JSON definition file |
| `OutputDir` | Root directory of the configuration export (where `Catalogs/`, `Documents/`, etc. are located) |

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-meta-compile/scripts/meta-compile.ps1 -JsonPath "<json>" -OutputDir "<ConfigDir>"
```

`OutputDir` — directory containing type subfolders (`Catalogs/`, `Documents/`, ...) and `Configuration.xml`.

## Supported Types (23)

### Reference Types
Catalog, Document, Enum, ExchangePlan, ChartOfAccounts, ChartOfCharacteristicTypes, ChartOfCalculationTypes, BusinessProcess, Task

### Registers
InformationRegister, AccumulationRegister, AccountingRegister, CalculationRegister

### Reports/DataProcessors
Report, DataProcessor

### Service Types
Constant, DefinedType, CommonModule, ScheduledJob, EventSubscription, DocumentJournal, HTTPService, WebService

## JSON DSL — Quick Reference

Full specification is split across three reference files in `tools/1c-meta-edit/`: [`json-dsl.md`](../tools/1c-meta-edit/json-dsl.md) (combined operations, key/type synonyms, supported object table), [`properties-reference.md`](../tools/1c-meta-edit/properties-reference.md) (object property operations), and [`child-operations.md`](../tools/1c-meta-edit/child-operations.md) (child-element operations).

### Root Structure

```json
{
  "type": "Catalog",
  "name": "Products",
  "synonym": "auto from name",
  ...type-specific...,
  "attributes": [...],
  "tabularSections": {...}
}
```

### Attributes — Shorthand

```
"AttributeName"                     — String without qualifiers
"AttributeName: Type"               — with type
"AttributeName: Type | req, index"  — with flags
```

Types: `String(100)`, `Number(15,2)`, `Boolean`, `Date`, `DateTime`, `CatalogRef.Xxx`, `DocumentRef.Xxx`, `EnumRef.Xxx`, `ChartOfAccountsRef.Xxx`, `ChartOfCharacteristicTypesRef.Xxx`, `ChartOfCalculationTypesRef.Xxx`, `ExchangePlanRef.Xxx`, `BusinessProcessRef.Xxx`, `TaskRef.Xxx`, `DefinedType.Xxx`.

Russian type synonyms: `Строка`, `Число`, `Булево`, `Дата`, `СправочникСсылка.Xxx`, `ДокументСсылка.Xxx`, `ПланСчетовСсылка.Xxx`.

Flags: `req`, `index`, `indexAdditional`, `nonneg`, `master`, `mainFilter`, `denyIncomplete`, `useInTotals`.

## Examples

### Catalog

```json
{ "type": "Catalog", "name": "Валюты" }
```

### Enum

```json
{ "type": "Enum", "name": "Статусы", "values": ["Новый", "Закрыт"] }
```

### Constant

```json
{ "type": "Constant", "name": "ОсновнаяВалюта", "valueType": "CatalogRef.Валюты" }
```

### Defined Type

```json
{ "type": "DefinedType", "name": "ДенежныеСредства", "valueTypes": ["CatalogRef.БанковскиеСчета", "CatalogRef.Кассы"] }
```

### Common Module

```json
{ "type": "CommonModule", "name": "ОбменДаннымиСервер", "context": "server", "returnValuesReuse": "DuringRequest" }
```

Context shortcuts: `"server"` → Server+ServerCall, `"client"` → ClientManagedApplication, `"serverClient"` → Server+ClientManagedApplication.

### Information Register

```json
{
  "type": "InformationRegister", "name": "КурсыВалют", "periodicity": "Day",
  "dimensions": ["Валюта: CatalogRef.Валюты | master, mainFilter, denyIncomplete"],
  "resources": ["Курс: Number(15,4)", "Кратность: Number(10,0)"]
}
```

### Exchange Plan

```json
{ "type": "ExchangePlan", "name": "ОбменССайтом", "attributes": ["АдресСервера: String(200)"] }
```

### Document Journal

```json
{
  "type": "DocumentJournal", "name": "Взаимодействия",
  "registeredDocuments": ["Document.Встреча", "Document.ТелефонныйЗвонок"],
  "columns": [{ "name": "Организация", "indexing": "Index", "references": ["Document.Встреча.Attribute.Организация"] }]
}
```

### HTTP Service

```json
{
  "type": "HTTPService", "name": "API", "rootURL": "api",
  "urlTemplates": { "Users": { "template": "/v1/users", "methods": { "Get": "GET", "Create": "POST" } } }
}
```

### Web Service

```json
{
  "type": "WebService", "name": "DataExchange", "namespace": "http://www.1c.ru/DataExchange",
  "operations": { "TestConnection": { "returnType": "xs:boolean", "handler": "ПроверкаПодключения", "parameters": { "ErrorMessage": { "type": "xs:string", "direction": "Out" } } } }
}
```

### Chart of Accounts

```json
{
  "type": "ChartOfAccounts", "name": "Хозрасчетный",
  "extDimensionTypes": "ChartOfCharacteristicTypes.ВидыСубконто", "maxExtDimensionCount": 3,
  "codeMask": "@@@.@@.@", "codeLength": 8,
  "accountingFlags": ["Валютный", "Количественный"],
  "extDimensionAccountingFlags": ["Суммовой", "Валютный"]
}
```

### Business Process

```json
{ "type": "BusinessProcess", "name": "Задание", "attributes": ["Описание: String(200)"] }
```

## What Gets Generated

- `{OutputDir}/{TypePlural}/{Name}.xml` — object metadata
- `{OutputDir}/{TypePlural}/{Name}/Ext/ObjectModule.bsl` — object module (Catalog, Document, Report, DataProcessor, ExchangePlan, ChartOfAccounts, ChartOfCharacteristicTypes, ChartOfCalculationTypes, BusinessProcess, Task)
- `{OutputDir}/{TypePlural}/{Name}/Ext/RecordSetModule.bsl` — record set module (4 register types)
- `{OutputDir}/{TypePlural}/{Name}/Ext/Module.bsl` — module (CommonModule, HTTPService, WebService)
- `{OutputDir}/{TypePlural}/{Name}/Ext/Content.xml` — exchange plan content (ExchangePlan)
- `{OutputDir}/{TypePlural}/{Name}/Ext/Flowchart.xml` — route map (BusinessProcess)
- `Configuration.xml` — automatic registration in `<ChildObjects>`

## Verification

```
1c-meta-info <OutputDir>/<TypePlural>/<Name>.xml    — check structure
1c-meta-validate <OutputDir>/<TypePlural>/<Name>.xml — validate XML
```

---
## 2. Edit — Modify Existing Object

Atomic modification operations on existing metadata object XML files.

## Command

### Inline Mode (simple operations)

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-meta-edit/scripts/meta-edit.ps1 -ObjectPath "<path>" -Operation <op> -Value "<val>"
```

### JSON Mode (complex/combined operations)

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-meta-edit/scripts/meta-edit.ps1 -DefinitionFile "<json>" -ObjectPath "<path>"
```

| Parameter | Description |
|-----------|-------------|
| ObjectPath | XML file or object directory (required, auto-resolves `<dirName>.xml`) |
| Operation | Inline operation (alternative to DefinitionFile) |
| Value | Value for inline operation |
| DefinitionFile | JSON file with operations (alternative to Operation) |
| NoValidate | Skip meta-validate after editing |

## Operations — Summary Table

Batch via `;;` in all operations. Detailed syntax in linked reference files.

### Child Elements — [child-operations.md](../tools/1c-meta-edit/child-operations.md)

| Operation | Value Format | Example |
|-----------|-------------|---------|
| `add-attribute` | `Name: Type \| flags` | `"Сумма: Number(15,2) \| req, index"` |
| `add-ts` | `TS: Attr1: Type1, Attr2: Type2` | `"Товары: Ном: CatalogRef.Ном, Кол: Number(15,3)"` |
| `add-dimension` | `Name: Type \| flags` | `"Организация: CatalogRef.Организации \| master"` |
| `add-resource` | `Name: Type` | `"Сумма: Number(15,2)"` |
| `add-enumValue` | `Name` | `"Value1 ;; Value2"` |
| `add-column` | `Name: Type` | `"Тип: EnumRef.ТипыДокументов"` |
| `add-form` / `add-template` / `add-command` | `Name` | `"ItemForm"` |
| `add-ts-attribute` | `TS.Name: Type` | `"Товары.Скидка: Number(15,2)"` |
| `remove-*` | `Name` | `"OldAttribute ;; AnotherOne"` |
| `remove-ts-attribute` | `TS.Name` | `"Товары.ObsoleteAttr"` |
| `modify-attribute` | `Name: key=value` | `"OldName: name=NewName, type=String(500)"` |
| `modify-ts-attribute` | `TS.Name: key=value` | `"Товары.Attr: name=NewName"` |
| `modify-ts` | `TS: key=value` | `"Товары: synonym=Product Items"` |

Positional insert: `"Склад: CatalogRef.Склады >> after Организация"`.

### Object Properties — [properties-reference.md](../tools/1c-meta-edit/properties-reference.md)

| Operation | Value Format | Example |
|-----------|-------------|---------|
| `modify-property` | `Key=Value` | `"CodeLength=11 ;; DescriptionLength=150"` |
| `add-owner` | `MetaType.Name` | `"Catalog.Контрагенты ;; Catalog.Организации"` |
| `add-registerRecord` | `MetaType.Name` | `"AccumulationRegister.ОстаткиТоваров"` |
| `add-basedOn` | `MetaType.Name` | `"Document.ЗаказКлиента"` |
| `add-inputByString` | `Field path` | `"StandardAttribute.Description"` |
| `set-owners` / `set-registerRecords` / `set-basedOn` / `set-inputByString` | Replace entire list | `"Catalog.Орг ;; Catalog.Контр"` |
| `remove-owner` / `remove-registerRecord` / ... | Remove from list | `"Catalog.Контрагенты"` |

### JSON DSL — [json-dsl.md](../tools/1c-meta-edit/json-dsl.md)

For combined operations (add + remove + modify in one file), key/type synonyms, supported object table.

## Quick Examples

```powershell
# Add attributes
-Operation add-attribute -Value "Комментарий: String(200) ;; Сумма: Number(15,2) | index"

# Add tabular section with attributes
-Operation add-ts -Value "Товары: Ном: CatalogRef.Ном | req, Кол: Number(15,3), Цена: Number(15,2)"

# Remove attribute
-Operation remove-attribute -Value "ObsoleteAttribute"

# Rename + change type
-Operation modify-attribute -Value "OldName: name=NewName, type=String(500)"

# Modify object properties
-Operation modify-property -Value "CodeLength=11 ;; DescriptionLength=150"

# Catalog owners
-Operation set-owners -Value "Catalog.Контрагенты ;; Catalog.Организации"
```

## Verification

```
1c-meta-validate <ObjectPath>    — validate after editing
1c-meta-info <ObjectPath>        — visual summary
```

---
## 3. Info — Analyze Structure

Reads a metadata object XML from a 1C configuration export and outputs a compact structure description.

## Parameters and Command

| Parameter | Description |
|-----------|-------------|
| `ObjectPath` | Path to the object XML file or directory (auto-resolves `<name>/<name>.xml`) |
| `Mode` | Mode: `overview` (default), `brief`, `full` |
| `Name` | Drill-down by element name (attribute, tabular section, enum value, URL template, operation) |
| `Limit` / `Offset` | Pagination (default 150 lines) |
| `OutFile` | Write result to file (UTF-8 BOM) |

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-meta-info/scripts/meta-info.ps1 -ObjectPath "<path>"
```

## Three Modes

| Mode | What It Shows |
|------|---------------|
| `overview` *(default)* | Header + key properties + structure without expanding details |
| `brief` | Everything in one-two lines: field names, counters |
| `full` | Everything expanded: TS columns, subscription sources, register records, forms |

`-Name` — drill-down: expand a specific object element (tabular section, attribute, URL template, web service operation).

## Supported Types (23)

**Reference:** Catalog, Document, Enum, BusinessProcess, Task, ExchangePlan, ChartOfAccounts, ChartOfCharacteristicTypes, ChartOfCalculationTypes
**Registers:** InformationRegister, AccumulationRegister, AccountingRegister, CalculationRegister
**Service:** Report, DataProcessor, HTTPService, WebService, CommonModule, ScheduledJob, EventSubscription
**Other:** Constant, DocumentJournal, DefinedType

## Examples

```powershell
# Catalog — overview
... -ObjectPath Catalogs/Валюты/Валюты.xml

# Document — full summary with TS columns, register records, forms
... -ObjectPath Documents/АвансовыйОтчет/АвансовыйОтчет.xml -Mode full

# Information register — brief
... -ObjectPath InformationRegisters/КурсыВалют/КурсыВалют.xml -Mode brief

# Drill-down into a document tabular section
... -ObjectPath Documents/АвансовыйОтчет/АвансовыйОтчет.xml -Name Товары

# Common module — context flags and return value reuse
... -ObjectPath CommonModules/ОбщегоНазначения/ОбщегоНазначения.xml

# HTTP service — URL templates and methods
... -ObjectPath HTTPServices/ExternalAPI/ExternalAPI.xml

# Drill-down into a URL template
... -ObjectPath HTTPServices/ExternalAPI/ExternalAPI.xml -Name АктуальныеЗадачи
```

---
## 4. Remove — Delete Object

Safely removes an object from a 1C configuration XML export. Before deletion, checks for references to the object in attributes, code, and other metadata. If references are found, deletion is blocked.

## Usage

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-meta-remove/scripts/meta-remove.ps1 -ConfigDir "<path>" -Object "Catalog.Товары"
```

## Parameters

| Parameter | Required | Description |
|-----------|:--------:|-------------|
| ConfigDir | yes | Root directory of the export (where Configuration.xml is) |
| Object | yes | Type and name: `Catalog.Товары`, `Document.Заказ`, etc. |
| DryRun | no | Only show what would be deleted, no changes |
| KeepFiles | no | Don't delete files, only unregister |
| Force | no | Delete despite found references |

## What It Does

1. **Finds object files**: `{TypePlural}/{Name}.xml` and `{TypePlural}/{Name}/`
2. **Checks references** (blocks if found, unless `-Force`):
   - XML types in other object attributes: `CatalogRef.Name`, `DocumentRef.Name`, etc.
   - BSL code: `Справочники.Name`, `Catalogs.Name`, common module calls
   - Document journals, event subscriptions, defined types
3. **Removes from Configuration.xml**: removes from `<ChildObjects>`
4. **Cleans subsystems**: recursively removes from `<Content>`
5. **Deletes files**: XML file and object directory

## Supported Types

Catalog, Document, Enum, Constant, InformationRegister, AccumulationRegister, AccountingRegister, CalculationRegister, ChartOfAccounts, ChartOfCharacteristicTypes, ChartOfCalculationTypes, BusinessProcess, Task, ExchangePlan, DocumentJournal, Report, DataProcessor, CommonModule, ScheduledJob, EventSubscription, HTTPService, WebService, DefinedType, Role, Subsystem, CommonForm, CommonTemplate, CommonPicture, CommonAttribute, SessionParameter, FunctionalOption, FunctionalOptionsParameter, Sequence, FilterCriterion, SettingsStorage, XDTOPackage, WSReference, StyleItem, Language

## Reference Check Categories

| Category | Search Patterns |
|----------|----------------|
| XML attribute types | `CatalogRef.Name`, `DocumentRef.Name`, `EnumRef.Name`, etc. |
| BSL code (Russian) | `Справочники.Name`, `Документы.Name`, `Перечисления.Name`, etc. |
| BSL code (English) | `Catalogs.Name`, `Documents.Name`, `Enums.Name`, etc. |
| Common modules | `Name.` (method calls), `<Handler>Name.`, `<MethodName>Name.` |

References from Configuration.xml, ConfigDumpInfo.xml, and subsystems are NOT blocking — they are cleaned automatically.

## Examples

```powershell
# Dry run — check references
... -ConfigDir src/cf -Object "Catalog.Obsolete" -DryRun

# Delete object with no references
... -ConfigDir src/cf -Object "Catalog.Obsolete"

# Force delete despite references
... -ConfigDir src/cf -Object "Catalog.Obsolete" -Force

# Only unregister (keep files)
... -ConfigDir src/cf -Object "Report.Old" -KeepFiles
```

Exit code: 0 = success, 1 = errors or references found.

---
## 5. Validate — Check Correctness

Checks a metadata object XML from a configuration export for structural errors: root structure, InternalInfo, properties, allowed values, StandardAttributes, ChildObjects, name uniqueness, tabular sections, cross-properties, nested HTTP/Web service structures.

## Parameters and Command

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| ObjectPath | yes | — | Path to the XML file or object directory |
| MaxErrors | no | 30 | Stop after N errors |
| OutFile | no | — | Write result to file (UTF-8 BOM) |

`ObjectPath` auto-resolve: if a directory is given — looks for `<dirName>/<dirName>.xml`.

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-meta-validate/scripts/meta-validate.ps1 -ObjectPath "<path>"
```

## Supported Types (23)

**Reference:** Catalog, Document, Enum, ExchangePlan, ChartOfAccounts, ChartOfCharacteristicTypes, ChartOfCalculationTypes, BusinessProcess, Task
**Registers:** InformationRegister, AccumulationRegister, AccountingRegister, CalculationRegister
**Reports/DataProcessors:** Report, DataProcessor
**Service:** CommonModule, ScheduledJob, EventSubscription, HTTPService, WebService
**Other:** Constant, DocumentJournal, DefinedType

## Checks Performed

| # | Check | Severity |
|---|-------|----------|
| 1 | XML well-formedness + root structure | ERROR |
| 2 | InternalInfo / GeneratedType | ERROR / WARN |
| 3 | Properties — Name, Synonym | ERROR / WARN |
| 4 | Properties — enum property values | ERROR |
| 5 | StandardAttributes | ERROR / WARN |
| 6 | ChildObjects — allowed element types | ERROR |
| 7 | Attributes/Dimensions/Resources — UUID, Name, Type | ERROR |
| 8 | Name uniqueness | ERROR |
| 9 | TabularSections — internal structure | ERROR / WARN |
| 10 | Cross-property consistency | ERROR / WARN |
| 11 | HTTPService/WebService — nested structure | ERROR |

Exit code: 0 = all checks passed, 1 = errors found.

## Examples

```powershell
# Catalog from configuration export
... -ObjectPath upload/acc_8.3.24/Catalogs/Банки/Банки.xml

# Auto-resolve from directory
... -ObjectPath upload/acc_8.3.24/Documents/АвансовыйОтчет

# With error limit
... -ObjectPath Catalogs/Номенклатура.xml -MaxErrors 10
```

## Verification Workflow

```
1c-meta-compile <JsonPath> <OutputDir>              — generate XML
1c-meta-validate <OutputDir>/<Type>/<Name>.xml      — check result
1c-meta-info <OutputDir>/<Type>/<Name>.xml          — visual summary
```

## When to Use

- **After `1c-meta-compile`**: verify generated XML correctness
- **After manual editing**: ensure structure is not broken
- **After merge/import**: detect conflicts and broken references
- **When debugging**: find structural errors before EPF build

---
## Typical Workflow

```
1c-meta-compile <JsonPath> <OutputDir>     — create object from JSON
1c-meta-validate <ObjectPath>              — validate generated XML
1c-meta-info <ObjectPath>                  — review structure
1c-meta-edit <ObjectPath> -Operation ...   — modify as needed
1c-meta-validate <ObjectPath>              — validate after editing
1c-meta-remove -ConfigDir <path> -Object   — remove when obsolete
```

---
## Recent Additions (upstream `w-2026-05-17`)

The PowerShell scripts under `tools/1c-meta-{compile,edit,info,remove,validate}/scripts/` were refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights:

### `meta-compile` — new properties and stricter type rules

- **Catalog properties** are now driven by JSON (no more hard-coded values): `limitLevelCount`, `levelCount`, `foldersOnTop`, `subordinationUse`, `codeSeries`, `quickChoice`, `choiceMode`. Hand-edit of XML is no longer required for non-default settings.
- **`owners`** — array of catalog owners with shorthand syntax.
- **`multiLine: true`** (or flag `| multiline`) on an attribute marks it as multiline.
- **`choiceHistoryOnInput`** on attributes — controls history-based auto-completion when entering a reference value.
- **Default for `quickChoice`** aligned with real configurations: catalogs / chart-of-characteristic-types / chart-of-accounts / chart-of-calculation-types / exchange plans default to `false`; enums default to `true` (≈95% / ≈99% match across real configs).
- **Manager modules** are now created alongside the object module for **reports and data processors** — required for reports that override `НастроитьВариантыОтчета`. Constants get manager and value-manager modules; enums get a manager module.
- **Empty `Ext/` folders** no longer created for constants, enums and document journals — they previously caused the platform to wipe extension modules on load.
- **Register-attribute properties** are filtered by register kind: AccumulationRegister / AccountingRegister / CalculationRegister attributes no longer get attribute-only properties the platform silently dropped. InformationRegister keeps the full set.
- **System enum values** in properties (`RegisterType`, `WriteMode`, `Periodicity`, …≈20 more) now accept synonyms and are case-insensitive — typical model errors like `Balances` → `Balance` or Russian variants no longer break the build.
- **Strict validation of enum values**: an unknown value for a known property gives a clear error instead of leaking into XML.
- **Format version** auto-detected from the nearest `Configuration.xml` (8.3.27+, 8.5).

### `meta-edit`

- Same synonym dictionary and case-insensitivity for system enum values, applied in `modify-attribute` / `modify-property` and when parsing `fillChecking` / `indexing`.

### `meta-validate`

- Empty register check (no dimensions, no resources, no attributes — platform refuses to load).
- Document-movements pointing to a non-existent register are reported.

### `meta-remove`

- Returns exit code 1 when the object is not found (was silently 0).

## MCP Integration

- **get_object_dossier** — Comprehensive structural passport in one call: structure, forms, subscriptions, roles, dependencies, code modules, business info. Use as the first step before creating/modifying/removing objects.
- **metadatasearch** — Verify object names don't conflict, find objects to remove and their relationships. Use `object_type` filter to narrow results.
- **get_metadata_details** — Get full object structure: attribute types, tabular parts, synonyms, properties. Use for verifying attribute types and references.
- **metadatasearch** (`names_only=true`) — Find similar metadata objects for XML reference before generating new XML.
- **get_xsd_schema** — Get XSD schema for the metadata type to validate generated XML structure.
- **verify_xml** — Validate generated or modified metadata XML against XSD before committing.
- **search_code** — Find BSL code references to objects (prefer over `codesearch` and Grep; supports semantic/fulltext/hybrid search with detail levels L0–L3).
- **codesearch** — Find code references in raw BSL files (fallback when `search_code` is not available).
- **trace_impact** — Recursive multi-level impact analysis before removal or modification (preferred over `graph_dependencies` for deep dependency chains).
- **find_objects_using_object** — Find all objects referencing the given object in their attributes/dimensions/resources before removal.
- **find_usages_of_object** — Attribute-level reference analysis: which specific attributes reference the object.
- **graph_dependencies** — Flat dependency overview (who uses this / what it uses).
- **docsearch** — Look up platform documentation for metadata type properties and valid property values when investigating validation errors.
- **business_search** — Semantic search of related objects when creating configuration objects.
- **answer_metadata_question** — Natural-language questions about object structure (meta-info provides more detailed structural analysis).
- **check_1c_code** — Verify BSL code in object modules after fixing structural issues (syntax, logic, performance).
- **review_1c_code** — Check code style and ITS standards compliance in object modules.

## SDD Integration

When creating or modifying configuration objects as part of a larger feature, update SDD artifacts if present (see `content/rules/sdd-integrations.md` for detection):

- **OpenSpec**: Add or update spec deltas in `openspec/changes/<change-id>/specs/` describing the new object, its attributes, and purpose.
