# 1C Metadata Manage — Compile, Edit, Info, Remove, Validate

Operations for creating, modifying, analyzing, removing, and validating 1C metadata objects from configuration XML export.

---
## 1. Compile — Create from JSON

Takes a JSON definition of a metadata object and generates XML + modules in the configuration export structure, then registers it in Configuration.xml.

## Parameters and Command

| Parameter | Description |
|-----------|-------------|
| `JsonPath` | Path to the JSON definition file (one object, or a JSON array of objects — batch mode) |
| `OutputDir` | Root directory of the configuration export (where `Catalogs/`, `Documents/`, etc. are located) |
| `Force` | Replace an object whose XML already exists (see below). Without it such an object is refused |

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-meta-compile/scripts/meta-compile.ps1 -JsonPath "<json>" -OutputDir "<ConfigDir>"
```

`OutputDir` — directory containing type subfolders (`Catalogs/`, `Documents/`, ...) and `Configuration.xml`.

## Existing objects are refused (local, stronger than upstream)

`meta-compile` creates objects; it does not update them. If `<TypePlural>/<Name>.xml` already exists, the tool **exits 1 before writing anything** and names `meta-edit`. A recompile would replace the file whole and give the object a **new uuid**: the link to the object already in the infobase and every reference to it (code, subsystem content, attribute types) break, and files of children the new JSON does not name stay behind as orphans. Upstream only warns here.

- Change an existing object — `meta-edit` (attributes, tabular sections, properties, external-data-source tables and functions).
- Replace it deliberately (a throwaway object that is not yet in any infobase) — pass `-Force`; the warning about the new uuid is still printed. In batch mode `-Force` applies to every item.

Exit codes: `0` — compiled and registered; `1` — refused or failed (existing object without `-Force`, unknown type name, invalid DSL value, support guard), nothing written; `3` — files written but **not registered** (no `Configuration.xml` / `<ChildObjects>` under `OutputDir`) — not a success.

## Supported Types (38)

### Reference Types
Catalog, Document, Enum, ExchangePlan, ChartOfAccounts, ChartOfCharacteristicTypes, ChartOfCalculationTypes, BusinessProcess, Task

### Registers
InformationRegister, AccumulationRegister, AccountingRegister, CalculationRegister

### Reports/DataProcessors
Report, DataProcessor

### Service Types
Constant, DefinedType, CommonModule, ScheduledJob, EventSubscription, DocumentJournal, HTTPService, WebService, FunctionalOption, FunctionalOptionsParameter, Sequence, FilterCriterion, DocumentNumerator, SettingsStorage, CommonForm, SessionParameter, CommonCommand, CommandGroup, CommonAttribute, WSReference, CommonPicture, CommonTemplate

### External Data Sources
ExternalDataSource — the source, its tables (`<Source>/Tables/<Table>.xml`, one file per table) and functions in one definition (spec §18). The source is described **whole**: tables and functions are added to an existing source with `meta-edit` (`add.tables` / `add.functions`), a table is removed with `meta-remove ExternalDataSource.<Source>.Table.<Table>`.

Format versions 2.17–2.21 are written (taken from the nearest `Configuration.xml`; 2.21 = platform 8.5, adds the palette namespace and a few 8.5-only properties).

## JSON DSL — Quick Reference

Full `meta-edit` operation reference is split across three files in `tools/1c-meta-edit/`: [`json-dsl.md`](../tools/1c-meta-edit/json-dsl.md) (combined operations, key/type synonyms, supported object table), [`properties-reference.md`](../tools/1c-meta-edit/properties-reference.md) (object property operations), and [`child-operations.md`](../tools/1c-meta-edit/child-operations.md) (child-element operations).

The **complete `meta-compile` DSL grammar** — every object type with its type-specific keys, all property spellings, version-dependent properties (format 2.20 / platform 8.3.27 included) — is vendored verbatim as [`meta-dsl-spec.md`](../tools/1c-meta-compile/meta-dsl-spec.md) (Russian, upstream original). The quick reference below covers the common cases; read the spec when a key is missing here or the compiler rejects a construct.

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

Russian type synonyms: `Строка`, `Число`, `Булево`, `Дата`, `СправочникСсылка.Xxx`, `ДокументСсылка.Xxx`, `ПланСчетовСсылка.Xxx`. The labels `meta-info` prints are accepted as input too (`ДокументОбъект.Заказ`, `ПВХСсылка.ВидыСубконто`, `Характеристика.Виды`, `НаборЗаписейРС.X`, …), so its output can be carried back into a definition.

Type-name rules:
- A bare name that is not a known form (a typo such as `Nubmer(15,2)`) is **refused** with the list of valid forms; nothing is written. A name with a namespace prefix (`v8:ValueTable`, `ent:AccountType`, `v8ui:Color`) passes as is and is judged by `meta-validate` check 22.
- DBMS spellings are translated: `integer`/`int`/`int4` → `Number(10,0)`, `bigint` → `Number(19,0)`, `smallint` → `Number(5,0)`, `numeric(p,s)` → `Number(p,s)`, `varchar(n)` / `character varying(n)` → `String(n)`, `timestamp` → `DateTime`, `bytea` → `BinaryData` (`ДвоичныеДанные` / `BinaryData` is its own type, not `ValueStorage`; `base64Binary` still means `ValueStorage`).
- A `Constant` without `valueType` is `String(10)` (the object kind no longer leaks into the value type).
- `numberLength: 0` on a document, business process or task drops `Number` from the default `InputByString`.

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
- `{OutputDir}/ExternalDataSources/{Name}/Tables/{Table}.xml` — one file per external-source table
- `Configuration.xml` — automatic registration in `<ChildObjects>`

## Placement in `Configuration.xml`

Registration adds exactly one `<Kind>Name</Kind>` line; the rest of the file is kept byte-for-byte (BOM, EOL, declaration case, `<Tag/>` form, indentation). Where the line goes inside its own kind group is `NEW_OBJECT_POSITION` in `.dev.env`:

| Value | Placement |
|-------|-----------|
| `end` (default / empty) | After the last object of the same kind — what Configurator does |
| `byName` | Alphabetically inside the kind group, by the deterministic 1C-tree comparator (standard АПК:1108) |

Regardless of the value: a group of a kind **not yet present** in the file is inserted in canonical kind order rather than appended to the end of the block, and the order-sensitive kinds (`Subsystem`, `CommandGroup`, `CommonAttribute`, `Language`) are never sorted by name. Objects already registered are never moved. Parameter class and default — `content/rules/dev-standards-env.md §1` (Infobase / deployment table).

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
| NoValidate | Skip the automatic validation after editing — the only opt-out |

## Results, Refusals and Validation

- **A failed operation is exit 1 with nothing written** (upstream 1.73): editing or removing an element that does not exist, an invalid enum value, a property the object kind does not have, a list property on a borrowed object of an extension. The whole definition is refused, not applied partly. `[WARN]` with exit 0 remains only for no-op cases — already added, nothing to delete, `>> after` / `before` anchor not found.
- `add-form` / `add-template` are refused (exit 2) before any write; removing a form or template through `meta-edit` is refused too (exit 1) — use `form-add` / `remove-form` and `add-template` / `remove-template`.
- After a successful edit the validator runs automatically and **its exit code is the run's result**: `meta-validate` from `1c-meta-validate` for configuration objects, `epf-validate` from `1c-epf-validate` for an external data processor / report. A missing validator is a refusal raised before the edit is written, never a silent skip. The Python runtime has no `epf-validate.py`: for an EPF / ERF it runs `epf-validate.ps1` through `pwsh` (or Windows PowerShell) and refuses before the write when no PowerShell host exists.
- `modify-property` writes canonical XML: enum values are normalized (synonyms, case) and unknown ones rejected, the key is matched case-insensitively and written in its canonical case, an empty multilingual property is written as XML, `CodeLength` / `NumberLength` `0` also drops `Code` / `Number` from `InputByString`. In an extension a missing `RegisterRecords` is created on a borrowed document.
- **External data sources**: on a source file `meta-edit` adds fields, tables (`add.tables` creates `<Source>/Tables/<Table>.xml` and registers it) and functions with the `meta-compile` syntax; removing a table is `meta-remove ExternalDataSource.<Source>.Table.<Table>`. Re-running `meta-compile` over an existing source is refused without `-Force` (it would give the source a new uuid).

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
| `add-command` | `Name` | `"Command1"` |
| ~~`add-template`~~ | — | **refused (exit 2)** before any write, including mixed JSON and accepted key aliases — use `add-template.ps1` with an object XML path and explicit `TemplateType`, see [template-manage.md](template-manage.md) |
| ~~`add-form`~~ | — | **refused (exit 2)** in every accepted key spelling (`add` / `Add` / `добавить`, `forms` / `формы`), checked across the whole definition before any write — use `form-add`, see [form-manage.md](form-manage.md) |
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

`-Name` — drill-down: expand a specific object element (tabular section, attribute, **standard attribute**, URL template, web service operation, external-source table). A composite type is folded into a counter in the summary; the drill-down lists every type (`-Name ТипЗначения` on a chart of characteristic types, `-Name Владелец` on a subordinate catalog).

What the summary shows (upstream 1.16):
- **Standard attributes** block in the same `name — type — [flags]` form as attributes: `Владелец`, `Код`, `Наименование`, `Дата`, `Номер`, `ТипЗначения` in `overview`; `Ссылка`, `ПометкаУдаления`, `Родитель`, `ЭтоГруппа` in `full`. Code / number type and length are visible, so code written from the summary sets the owner and the right key.
- **Type sets** (`v8:TypeSet`) are printed as types: a subscription whose source is a defined type or a whole class ("all documents") has a source line, a defined type shows its composition, and a single-member defined type shows the member (`ОпределяемыйТип.ДенежнаяСумма` → `Число(15,2)`).
- Command names are clean (no glued XML); `xs:base64Binary` prints as `ДвоичныеДанные`, storage as `ХранилищеЗначения`.
- **External data sources**: the source shows its lock mode, tables and functions; a table shows its kind, source name, key / presentation / parent fields and the field list.

The type labels it prints (`ДокументОбъект.Заказ`, `ПВХСсылка.X`, `НаборЗаписейРС.X`, `Характеристика.X`, …) are accepted as input by `meta-compile` and `meta-edit`.

## Supported Types

**Reference:** Catalog, Document, Enum, BusinessProcess, Task, ExchangePlan, ChartOfAccounts, ChartOfCharacteristicTypes, ChartOfCalculationTypes
**Registers:** InformationRegister, AccumulationRegister, AccountingRegister, CalculationRegister
**Service:** Report, DataProcessor, HTTPService, WebService, CommonModule, ScheduledJob, EventSubscription
**Other:** Constant, DocumentJournal, DefinedType, ExternalDataSource (and its tables)

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
| Object | yes | Type and name: `Catalog.Товары`, `Document.Заказ`, etc. An external-source table takes four parts: `ExternalDataSource.PG.Table.products` |
| DryRun | no | Only show what would be deleted, no changes |
| KeepFiles | no | Don't delete files, only unregister |
| Force | no | Delete despite found references; form slots that point at the removed object's forms are cleared |

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

Catalog, Document, Enum, Constant, InformationRegister, AccumulationRegister, AccountingRegister, CalculationRegister, ChartOfAccounts, ChartOfCharacteristicTypes, ChartOfCalculationTypes, BusinessProcess, Task, ExchangePlan, DocumentJournal, Report, DataProcessor, CommonModule, ScheduledJob, EventSubscription, HTTPService, WebService, DefinedType, Role, Subsystem, CommonForm, CommonTemplate, CommonPicture, CommonAttribute, SessionParameter, FunctionalOption, FunctionalOptionsParameter, Sequence, FilterCriterion, SettingsStorage, XDTOPackage, WSReference, StyleItem, Language, ExternalDataSource (whole source or one table)

The support guard applies: an object of a vendor configuration "on the lock" is not removed (`SUPPORT_GUARD` in `.dev.env`, fail-closed on an unreadable support state) — see [support-manage.md](support-manage.md).

## Reference Check Categories

| Category | Search Patterns |
|----------|----------------|
| XML attribute types | `CatalogRef.Name`, `DocumentRef.Name`, `EnumRef.Name`, etc. |
| BSL code (Russian) | `Справочники.Name`, `Документы.Name`, `Перечисления.Name`, etc. |
| BSL code (English) | `Catalogs.Name`, `Documents.Name`, `Enums.Name`, etc. |
| Common modules | `Name.` (method calls), `<Handler>Name.`, `<MethodName>Name.` |

`Configuration.xml` is scanned like any other file: configuration-level slots (`DefaultReportForm` and its neighbours, home-page items) that name the object or its forms are **listed as references** and cleared only with `-Force` — before, the file was skipped and such slots stayed dangling, so the configuration no longer loaded. The `<ChildObjects>` entry, `ConfigDumpInfo.xml` and subsystem content are not blocking — they are cleaned automatically. Type references and `.bsl` calls are never rewritten.

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

Checks a metadata object XML from a configuration export for structural errors: root structure, InternalInfo, properties, allowed values, StandardAttributes, ChildObjects, forms, name uniqueness, tabular sections, cross-properties, nested HTTP/Web service structures, references, type names and format versions.

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

## Supported Types

**Deep-checked (25):** Catalog, Document, Enum, ExchangePlan, ChartOfAccounts, ChartOfCharacteristicTypes, ChartOfCalculationTypes, BusinessProcess, Task, InformationRegister, AccumulationRegister, AccountingRegister, CalculationRegister, Report, DataProcessor, CommonModule, ScheduledJob, EventSubscription, HTTPService, WebService, Constant, DocumentJournal, DefinedType, ExternalDataSource and its tables.
**Structural only** (root, uuid, Name): the remaining valid kinds, including IntegrationService and Bot — they are no longer an "Unrecognized metadata type" error.

## Checks Performed

| # | Check | Severity |
|---|-------|----------|
| 1 | XML well-formed, root structure; a version outside the tested 2.17–2.21 range is a warning | ERROR / WARN |
| 2 | InternalInfo / GeneratedType: every category present, name exactly `<Type><Category>.<Name>` (external-source table: `ExternalDataSourceTable<Cat>.<Source>.<Table>`, a missing category only warns) | ERROR / WARN |
| 3 | Properties: Name, Synonym; `FormType` / `TemplateType` of form and template descriptors | ERROR / WARN |
| 4 | Enum property values (root, attributes, tabular sections, common-attribute content); scalar root `<Type>` | ERROR |
| 5 | StandardAttributes | ERROR / WARN |
| 6 | ChildObjects: allowed element types and order | ERROR / WARN |
| 6a–6d | Form registrations: scalar reference, descriptor on disk, parseable, same name | ERROR |
| 6f | Default / auxiliary object, folder, record and list forms of this object have that role (main attribute type); whether the reference resolves is check 20 | ERROR |
| 6g | A form binds `Description` / `Code` only when the length is > 0 | ERROR |
| 6h | The default object form shows a mandatory `Description`, or a module assigns it | WARN |
| 7 | Attributes / dimensions / resources / enum values / columns: uuid, Name, Type (an empty `<Type/>` is valid; no Type block warns) | ERROR / WARN |
| 7b | Own name equals a standard attribute of the kind (EN/RU); tabular-section column `LineNumber` / `Ref` | ERROR |
| 8 | Name uniqueness, case-insensitive; attributes, tabular sections, dimensions, resources, addressing attributes and accounting flags share one namespace; each clash reported once | ERROR |
| 9 | Tabular sections: internal structure | ERROR / WARN |
| 10 | Cross-property consistency | ERROR / WARN |
| 11 | HTTPService / WebService nested structure (`ReuseSessions` = `DontUse` / `Use` / `AutoUse`) | ERROR / WARN |
| 12 | Forbidden properties per kind (InformationRegister: `Periodicity`, `DefaultRecordSetForm`) | ERROR |
| 13 | `EventSubscription.Handler` / `ScheduledJob.MethodName` resolve to a common module and an export method | ERROR / WARN |
| 14 | DocumentJournal column content | ERROR |
| 15 | Commands: uuid, group set and valid, no parameter type in a section group, name not equal to a standard command | ERROR |
| 16 | `CatalogRef.X`-style types resolve: absent from the configuration is ERROR, registered but missing from the dump is WARN; subscription sources given as a type set (`v8:TypeSet`) and `xr:Item` journal content are understood | ERROR / WARN |
| 16a | Export folder name used as a type (`cfg:Catalogs.X`) | ERROR |
| 17 | `MDObjectRef` names an object, not a type (`CatalogRef.X`) | ERROR / WARN |
| 18 | A property newer than the file's format version (`TypeReductionMode` 2.18, `LineNumberLength` 2.20, 2.21 properties) | ERROR |
| 19 | `LineNumberLength` within 5..9 | ERROR |
| 20 | `Default*Form` / `Auxiliary*Form` / `ChoiceForm` references resolve (own, foreign, common, external-source forms) | ERROR / WARN |
| 21 | External-source table: field references and key fields | ERROR / WARN |
| 22 | Type-name grammar (missing prefix, DBMS type name) is ERROR; an unknown or non-storable type for the owner is WARN | ERROR / WARN |
| 23 | Type set inside a defined type is ERROR; a bare metatype in a characteristic-types chart or a composite defined type / characteristic warns | ERROR / WARN |
| 24 | A body (`Ext/*.xml`, Help, Predefined, Rights, Form, `<BaseForm>`) stamped with a version different from its descriptor is ERROR; an object or form whose version differs from the dump (`Configuration.xml` or the EPF/ERF root) is WARN — measured on 8.3.27: a whole object in another format version loads, a body out of step with its descriptor does not | ERROR / WARN |
| 25 | Multilingual string holding plain text instead of `<v8:item>` | ERROR |

Local checks (not in upstream): 6a–6d, 6f, 6g, 6h, 12, 16a, and the stricter 2 and 8. The former local 1e / 6e ("every file carries the `Configuration.xml` version", ERROR) are retired in favour of 24. Both runtimes (`.ps1` / `.py`) print the same messages; the Python runtime takes named arguments (`-ObjectPath <path>`).

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

MCP evidence set (`content/rules/tooling-playbooks.md`): `get_xsd_schema` with `object_type` = the metadata type (`Справочник`, `Документ`, `РегистрСведений`, …) before generating, `verify_xml` on the result.

---

Scripts vendored from Nikolay-Shirokov/cc-1c-skills; sync history — `docs/CHANGELOG.md`.
