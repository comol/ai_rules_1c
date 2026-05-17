# 1C Role Manage — Compile, Info, Validate

Create, analyze, and validate 1C roles (metadata + Rights.xml) for access rights management.

---
## 1. Compile — Create Role

Creates role files (metadata + Rights.xml) from a JSON description.

> **Preferred path** — invoke the PowerShell script `tools/1c-role-compile/scripts/role-compile.ps1` (added from upstream `cc-1c-skills` `w-2026-05-17`). The full JSON DSL for the script lives in `tools/1c-role-compile/dsl-reference.md` (legacy Russian — to be translated separately).
>
> The XML templates below remain for manual fallback when the script is not applicable (e.g. one-off rights-only edits).

## Usage

```
1c-role-compile <RolePath> <OutputDir>
```

- **RolePath** — path to the JSON role definition.
- **OutputDir** — either the configuration source root (the script creates `Roles/` itself) or a path that already ends with `Roles`.

**Command:**
```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-role-compile/scripts/role-compile.ps1 -RolePath "<role.json>" -OutputDir "<src-root-or-Roles>"
```

The script accepts the DSL keys `objects` (canonical) or its synonym `rights`. UUIDs and registration in `Configuration.xml` are handled automatically.

## File Structure and Registration

```
Roles/
  RoleName.xml           ← metadata (uuid, name, synonym)
  RoleName/
    Ext/
      Rights.xml         ← rights definition
```

Add `<Role>RoleName</Role>` to `<ChildObjects>` section in `Configuration.xml`.

## Metadata Template: Roles/RoleName.xml

```xml
<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses"
        xmlns:v8="http://v8.1c.ru/8.1/data/core"
        xmlns:xr="http://v8.1c.ru/8.3/xcf/readable"
        xmlns:xs="http://www.w3.org/2001/XMLSchema"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        version="2.17">
    <Role uuid="GENERATE-UUID-HERE">
        <Properties>
            <Name>RoleName</Name>
            <Synonym>
                <v8:item>
                    <v8:lang>ru</v8:lang>
                    <v8:content>Display role name</v8:content>
                </v8:item>
            </Synonym>
            <Comment/>
        </Properties>
    </Role>
</MetaDataObject>
```

**UUID:** `powershell.exe -Command "[guid]::NewGuid().ToString()"`

## Rights Template: Roles/RoleName/Ext/Rights.xml

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Rights xmlns="http://v8.1c.ru/8.2/roles"
        xmlns:xs="http://www.w3.org/2001/XMLSchema"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xsi:type="Rights" version="2.17">
    <setForNewObjects>false</setForNewObjects>
    <setForAttributesByDefault>true</setForAttributesByDefault>
    <independentRightsOfChildObjects>false</independentRightsOfChildObjects>
    <!-- <object> blocks -->
</Rights>
```

NB: namespace `http://v8.1c.ru/8.2/roles` (historically 8.2, not 8.3).

## Rights Block Format

```xml
<object>
    <name>Catalog.Products</name>
    <right><name>Read</name><value>true</value></right>
    <right><name>View</name><value>true</value></right>
</object>
```

Object name — dot notation: `ObjectType.Name[.NestedType.NestedName]`.

## Common Rights Sets

### Catalog / ExchangePlan

| Set | Rights |
|-----|--------|
| Read | Read, View, InputByString |
| Full | Read, Insert, Update, Delete, View, Edit, InputByString, InteractiveInsert, InteractiveSetDeletionMark, InteractiveClearDeletionMark |

### Document

| Set | Rights |
|-----|--------|
| Read | Read, View, InputByString |
| Full | Read, Insert, Update, Delete, View, Edit, InputByString, Posting, UndoPosting, InteractiveInsert, InteractiveSetDeletionMark, InteractiveClearDeletionMark, InteractivePosting, InteractivePostingRegular, InteractiveUndoPosting, InteractiveChangeOfPosted |

### InformationRegister / AccumulationRegister / AccountingRegister

| Set | Rights |
|-----|--------|
| Read | Read, View |
| Full | Read, Update, View, Edit |

TotalsControl — only for totals management, usually not needed.

### Simple Types

| Type | Rights |
|------|--------|
| `DataProcessor` / `Report` | Use, View |
| `Constant` | Read, Update, View, Edit (read-only: Read, View) |
| `CommonForm` / `CommonCommand` / `Subsystem` / `FilterCriterion` | View |
| `DocumentJournal` | Read, View |
| `Sequence` | Read, Update |
| `SessionParameter` | Get (+ Set if writes) |
| `CommonAttribute` | View (+ Edit if edits) |
| `WebService` / `HTTPService` / `IntegrationService` | Use |
| `CalculationRegister` | Read, View |

### Rare Reference Types

| Type | Specifics (relative to Catalog) |
|------|--------------------------------|
| `ChartOfAccounts`, `ChartOfCharacteristicTypes`, `ChartOfCalculationTypes` | + Predefined rights (InteractiveDeletePredefinedData, etc.) |
| `BusinessProcess` | + Start, InteractiveStart, InteractiveActivate |
| `Task` | + Execute, InteractiveExecute, InteractiveActivate |

### Types WITHOUT Rights in Roles

Enum, FunctionalOption, DefinedType, CommonModule, CommonPicture, CommonTemplate — do not appear in Rights.xml.

### Nested Objects (rights: View, Edit)

```
Catalog.Contractors.Attribute.TIN
Document.Sales.StandardAttribute.Posted
Document.Sales.TabularSection.Items
InformationRegister.Prices.Dimension.Product
InformationRegister.Prices.Resource.Price
Catalog.Contractors.Command.OpenCard          ← View only
Task.Assignment.AddressingAttribute.Performer
```

Used for granular denial: `<value>false</value>` on a specific attribute.

### Configuration

Object: `Configuration.ConfigName`. Key rights: Administration, DataAdministration, ThinClient, WebClient, ThickClient, MobileClient, ExternalConnection, Output, SaveUserData, InteractiveOpenExtDataProcessors, InteractiveOpenExtReports, MainWindowModeNormal, MainWindowModeWorkplace, MainWindowModeEmbeddedWorkplace, MainWindowModeFullscreenWorkplace, MainWindowModeKiosk, AnalyticsSystemClient.

> DataHistory rights (ReadDataHistory, UpdateDataHistory, etc.) exist for Catalog, Document, Register, Constant — but are rarely used in standard roles.

## RLS (Row-Level Security)

Inside `<right>`, after `<value>`. Applies to Read, Update, Insert, Delete.

```xml
<right>
    <name>Read</name>
    <value>true</value>
    <restrictionByCondition>
        <condition>#TemplateName("Param1", "Param2")</condition>
    </restrictionByCondition>
</right>
```

Templates — at the end of Rights.xml, after all `<object>` blocks:

```xml
<restrictionTemplate>
    <name>TemplateName(Param1, Param2)</name>
    <condition>Template text</condition>
</restrictionTemplate>
```

`&` in conditions → `&amp;`. Typical templates: ForObject, ByValues, ForRegister.

## Example: Role for a Scheduled Job

```xml
<object>
    <name>Catalog.Currencies</name>
    <right><name>Read</name><value>true</value></right>
</object>
<object>
    <name>InformationRegister.CurrencyRates</name>
    <right><name>Read</name><value>true</value></right>
    <right><name>Update</name><value>true</value></right>
</object>
<object>
    <name>Constant.MainCurrency</name>
    <right><name>Read</name><value>true</value></right>
</object>
```

Background jobs do not require Interactive/View/Edit rights or configuration rights (ThinClient, WebClient, etc.) — only programmatic rights (Read, Insert, Update, Delete, Posting).

---
## 2. Info — Analyze Rights

Parses a role's `Rights.xml` and outputs a compact summary: objects grouped by type, showing only allowed rights. Compression: thousands of XML lines → 50–150 lines of text.

## Usage

```
1c-role-info <RightsPath>
```

**RightsPath** — path to the role's `Rights.xml` file (typically `Roles/RoleName/Ext/Rights.xml`).

## Command

```powershell
powershell.exe -File skills/1c-metadata-manage/tools/1c-role-info/scripts/role-info.ps1 -RightsPath <path> -OutFile <output.txt>
```

### Parameters

| Parameter | Required | Description |
|-----------|:--------:|-------------|
| `-RightsPath` | yes | Path to Rights.xml |
| `-ShowDenied` | no | Show denied rights (hidden by default) |
| `-Limit` | no | Max output lines (default `150`). `0` = unlimited |
| `-Offset` | no | Skip N lines — for pagination (default `0`) |
| `-OutFile` | no | Write result to file (UTF-8 BOM). Without this — console output |

**Important:** Always use `-OutFile` and read result via Read tool. Direct console output may corrupt Cyrillic characters.

For large roles with truncated output:
```powershell
... -Offset 150            # pagination: skip first 150 lines
```

## Output Format

```
=== Role: BasicRightsBP --- "Basic Rights: Enterprise Accounting" ===

Properties: setForNewObjects=false, setForAttributesByDefault=true, independentRightsOfChildObjects=false

Allowed rights:

  Catalog (8):
    Contractors: Read, View, InputByString
    Banks: Read, View, InputByString
    ...

  Document (12):
    SalesInvoice: Read, View, Posting, InteractivePosting
    ...

  InformationRegister (6):
    ProductPrices: Read [RLS], Update
    ...

Denied: 18 rights (use -ShowDenied to list)

RLS: 4 restrictions
Templates: ForRegister, ByValues

---
Total: 138 allowed, 18 denied

[TRUNCATED] Shown 150 of 220 lines. Use -Offset 150 to continue.
```

Use `-Offset N` and `-Limit N` for paginated viewing.

### Notation

- `[RLS]` — right with row-level security restriction (restrictionByCondition)
- `-View`, `-Edit` — denied rights (in Denied section, with `-ShowDenied`)
- Nested objects shown with suffix: `Contractors.StandardAttribute.PredefinedDataName`

---
## 3. Validate — Check Correctness

Checks correctness of a role's `Rights.xml`: XML format, namespace, global flags, object types, right names, RLS restrictions, templates. Optionally checks role metadata (UUID, name, synonym).

## Usage

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-role-validate/scripts/role-validate.ps1 -RightsPath <path> [-MetadataPath <path>] [-OutFile <output.txt>]
```

### Parameters

| Parameter | Required | Description |
|-----------|:--------:|-------------|
| `-RightsPath` | yes | Path to `Rights.xml` of the role |
| `-MetadataPath` | no | Path to role metadata (`Roles/RoleName.xml`) |
| `-OutFile` | no | Write result to file (UTF-8 BOM). Without this — console output |

**Important:** For Cyrillic paths, use `-OutFile` and read the result via the Read tool.

## Checks

### Rights.xml
1. XML well-formed — parses without errors
2. Root element `<Rights>` with namespace `http://v8.1c.ru/8.2/roles`
3. Three global flags: `setForNewObjects`, `setForAttributesByDefault`, `independentRightsOfChildObjects`
4. For each `<object>`:
   - `<name>` is not empty
   - Object type is recognized (Catalog, Document, InformationRegister, etc.)
   - Each `<right>` has `<name>` and `<value>` (`true`/`false`)
   - Right name is valid for the object type (with suggestion on typo)
5. Nested objects (3+ segments via `.`): only View, Edit allowed (or Use for IntegrationServiceChannel)
6. RLS `<restrictionByCondition>`: `<condition>` is not empty
7. Templates `<restrictionTemplate>`: `<name>` and `<condition>` are not empty

### Metadata (optional)
- `<Role>` element found
- UUID in correct format
- `<Name>` is not empty
- `<Synonym>` is present

## Message Levels

| Marker | Meaning |
|--------|---------|
| `OK` | Check passed |
| `WARN` | Warning (unknown object type, suspicious right name) |
| `ERR` | Error (invalid XML, missing required elements) |

Exit code: `0` — no errors, `1` — errors found.

## Examples

### Rights.xml Only

```powershell
... -RightsPath Roles/БазовыеПраваБП/Ext/Rights.xml
```

### With Metadata Check

```powershell
... -RightsPath Roles/МояРоль/Ext/Rights.xml -MetadataPath Roles/МояРоль.xml
```

### Verification After role-compile

```
1c-role-compile role.json Roles/
1c-role-validate -RightsPath Roles/МояРоль/Ext/Rights.xml -MetadataPath Roles/МояРоль.xml
```

---
## Typical Workflow

```
1c-role-compile <RoleName> <RolesDir>                    — create role from description
1c-role-validate -RightsPath <path> -MetadataPath <path>  — validate correctness
1c-role-info <RightsPath>                                — analyze existing role before modification
```

---
## Recent Additions (upstream `w-2026-05-17`)

The PowerShell scripts under `tools/1c-role-{compile,info,validate}/scripts/` were refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights:

- **`role-compile`** — `OutputDir` now accepts the source root of the configuration; `Roles/` is created automatically. Legacy behaviour (path already ending in `Roles`) is preserved. The DSL key `rights` is accepted as a synonym of `objects`.
- **`role-validate`** — auto-discovers metadata from the path to `Rights.xml`; `-MetadataPath` is no longer required, metadata-driven checks always run when the file is present.
- **All 10 validators** (`role-validate`, `meta-validate`, `epf-validate`, `skd-validate`, `cf-validate`, `cfe-validate`, `form-validate`, `mxl-validate`, `subsystem-validate`, `interface-validate`) now emit a single one-liner by default; the full per-check trace is available via `-Detailed`. Each accepts a folder path as the primary file argument and resolves to the canonical XML file (e.g. `Roles/MyRole` → `Roles/MyRole/Ext/Rights.xml`). The universal `-Path` parameter is supported in addition to the legacy named parameters (`-RolePath`, `-FormPath`, `-TemplatePath`, `-ObjectPath`, …).

## MCP Integration

- **metadatasearch** — Verify metadata object names when defining rights; verify objects referenced in role rights exist in the configuration.
- **get_metadata_details** — Get full object structure to understand which attributes/tabular parts need specific access rights.
- **get_xsd_schema** — Get XSD schema for role XML (`object_type="Роль"`). Use before generating role definitions.
- **verify_xml** — Validate generated role XML against XSD.
- **ssl_search** — Find SSL role patterns.

## SDD Integration

When creating or modifying roles as part of a feature, update SDD artifacts if present (see `content/rules/sdd-integrations.md` for detection):

- **OpenSpec**: Add spec deltas describing role purpose, access scope, and RLS rules in `openspec/changes/`.
