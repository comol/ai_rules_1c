# 1C Role Manage — Compile, Edit, Info, Validate

Create, edit in place, analyze, and validate 1C roles (metadata + Rights.xml) for access rights management.

| Task | Tool |
|------|------|
| New role | `role-compile` (section 1) — new UUID, registers the role in `Configuration.xml` |
| Change an existing role — rights, RLS, templates, flags, synonym | `role-edit` (section 2) — UUID and every other entry stay as they are |
| Summary of a role | `role-info` (section 3) |
| Check a role | `role-validate` (section 4) — `role-edit` runs it automatically |

Never re-compile an existing role: `role-compile` issues a new UUID and rewrites `Rights.xml` whole. It refuses (exit 1, nothing written) when `Roles/<Name>.xml` already exists; `-Force` replaces the role deliberately (local gate, upstream overwrites).

---
## 1. Compile — Create Role

Creates `Roles/<Name>.xml` and `Roles/<Name>/Ext/Rights.xml` from a JSON description and registers `<Role>` in `Configuration.xml`. The full JSON DSL (Russian, upstream original) is [`dsl-reference.md`](../tools/1c-role-compile/dsl-reference.md).

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-role-compile/scripts/role-compile.ps1 -JsonPath "<role.json>" -OutputDir "<src-root-or-Roles>"
```

| Parameter | Description |
|-----------|-------------|
| `-JsonPath` | Path to the JSON role definition |
| `-OutputDir` | The configuration source root (`Roles/` is created) or a path that already ends with `Roles` |

The new `<Role>` entry goes into `<ChildObjects>` by `.dev.env` `NEW_OBJECT_POSITION` (`end` by default, after the last role; `byName` sorts it among the roles), the same rule as `meta-compile` / `cf-edit`.

### JSON DSL — Quick Reference

```json
{
  "name": "SalesManager",
  "synonym": "Sales manager",
  "objects": [
    "Catalog.Products: @view",
    "Document.SalesOrder: @edit",
    "InformationRegister.Prices: Read, Update",
    { "name": "Document.Sale", "preset": "view", "rights": { "Delete": false }, "rls": { "Read": "#ForObject(\"\")" } },
    { "name": "Catalog.Products.Attribute.Price", "rights": { "View": false } }
  ],
  "templates": [ { "name": "ForObject(Modifier)", "condition": "WHERE Company = &CurrentCompany" } ]
}
```

- Optional root keys: `comment` (`""`), `setForNewObjects` (`false`), `setForAttributesByDefault` (`true`), `independentRightsOfChildObjects` (`false`). `rights` is accepted as a synonym of `objects`.
- Shorthand: `"Type.Name: @preset"` or `"Type.Name: Right1, Right2"`. Object form: `preset` (without `@`) + `rights` (dict `{"Right": true/false}` or array) + `rls` (`{"Right": "condition"}`).
- Russian type and right names are accepted (`Справочник.Контрагенты: Чтение`); the canonical form is English.
- RLS: a template reference starts with `#` (`#ForObject("")`); `&` is escaped automatically.
- **Condition or template body from a file:** write `@path` as the value — `"rls": {"Read": "@condition.txt"}`, `"condition": "@template.txt"`. A relative path is looked up next to the JSON file, then in the current directory.
- Attributes, tabular sections, dimensions and resources inherit the rights of their object — give them a denial (`"rights": {"View": false}`) to close what they inherit.
- An extension role listed in `DefaultRoles` cannot grant rights on adopted objects (the platform refuses) — put such rights into a separate role.

### Services — rights live on nested objects

A right on a service as a whole does not exist: the platform checks the URL-template method, the web-service operation, the integration-service channel. A role with `HTTPService.X: Use` on the root loads, passes old validators and answers **403** on every route.

- Short form `"HTTPService.EDI: Use"` (also `WebService.X: Use`, `IntegrationService.X: Use`) is **expanded by `role-compile` / `role-edit`** from the service metadata of the configuration the role belongs to into one entry per leaf, e.g. `HTTPService.EDI.URLTemplate.NewDocs.Method.POST: Use`. No metadata found or no nested objects → refusal.
- Part of the routes — full paths: `HTTPService.API.URLTemplate.Files.Method.Get: Use`, `WebService.Exchange.Operation.Load: Use`, `IntegrationService.Bus.IntegrationServiceChannel.Orders: Use`.
- The segment after `Method.` is the **name of the Method object** in the metadata tree, not an HTTP verb (`Method.GET`, `Method.Установить`, …).

### Refusal before writing

Every problem in the description is collected and reported at once, then the run exits `1` — no role files are written and `Configuration.xml` is not touched:

- a type that has no rights in roles (`Enum`, `CommonModule`, … — section 5) or an unknown type (typo). A rights block on an enum makes the configuration hang on load without a message;
- a right that does not exist for the type, a nested kind impossible for the type, a right not allowed for the nested kind;
- a service root that cannot be expanded; an extension default role granting rights on adopted objects.

### What is written

- **Rights closure.** The platform completes the set on load (`Edit` → `Read`, `Update`, `View`; interactive rights → their base set; `View` of a data processor / report → `Use`), so the closure is written right away. From format 2.19 (8.3.26) a right equal to the role default (`setForNewObjects`) is not stored.
- **Platform order.** `<right>` order inside `<object>` is fixed per type; `<object>` nodes go by the UUID of the metadata object (nested — by the attribute / command UUID). An object not found in the dump is written last with a notice.
- **Format version** of both files = the `Configuration.xml` version (or the EPF/ERF root).

---
## 2. Edit — Change an Existing Role

Changes rights, RLS, templates, flags, synonym or comment of an existing role in place: the UUID, the other rights, RLS and templates are kept, the file's BOM / EOL style is preserved.

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-role-edit/scripts/role-edit.ps1 -RolePath "<role>" -Operation <op> -Value "<value>"
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-role-edit/scripts/role-edit.ps1 -RolePath "<role>" -DefinitionFile "<ops.json>"
```

| Parameter | Description |
|-----------|-------------|
| `-RolePath` (aliases `-Path`, `-RightsPath`) | Role folder `Roles/<Name>`, `Roles/<Name>.xml` or `Roles/<Name>/Ext/Rights.xml` |
| `-Operation` | One operation from the table below |
| `-Value` | Operation value; several values of the same operation — separated by `;;` |
| `-DefinitionFile` | JSON array `[{"operation": "...", "value": "..."}, …]` — several different operations in one call (instead of `-Operation`) |
| `-NoValidate` | Do not run `role-validate` after the edit |

Operations are applied in the order given.

| Operation | `Value` | Effect |
|-----------|---------|--------|
| `add-rights` | `Type.Name: Right1, Right2` or `Type.Name: @preset` | Add rights, keep the existing ones |
| `set-rights` | same | Replace the object's rights set |
| `remove-rights` | `Type.Name: Right1` — remove rights; `Type.Name` — remove the object | Remove rights; an object left without granted rights is removed |
| `deny-rights` | `Type.Name: Right1, Right2` | Deny on an attribute / tabular section that otherwise inherits the object's rights |
| `set-rls` | `Type.Name.Right: condition`, `Type.Name.Right[Field1, Field2]: condition` | Row-level restriction; the right must already be granted |
| `remove-rls` | `Type.Name.Right` — all rows; `Type.Name.Right[Field1]` — one row | Remove a restriction, keep the right |
| `add-template` / `set-template` | `Name(Params): condition` | Add / replace (or add) an RLS template |
| `remove-template` | `Name(Params)` or `Name` | Remove a template |
| `modify-property` | `setForNewObjects=true`, `setForAttributesByDefault=false`, `independentRightsOfChildObjects=true` | Global role flags |
| `set-synonym` / `set-comment` | text | Role synonym / comment |

```powershell
... -RolePath "src/Roles/Manager" -Operation add-rights -Value "InformationRegister.Prices: Read, Update"
... -RolePath "src/Roles/Manager" -Operation add-rights -Value "Catalog.Products: @view ;; Document.Order: @edit"
... -RolePath "src/Roles/Manager" -Operation deny-rights -Value "Catalog.Products.Attribute.Price: View"
```

- Object and right names, presets, nested paths and the service short form are the same as in `role-compile`; the rights tables of both tools are identical.
- `remove-rights` / `deny-rights` cascade: rights that need the removed one go too (remove `Read` → `Update`, `View`, `Edit` go); the cascade is listed in the output.
- **RLS rows.** An RLS right is a list of rows, like the "Data access restrictions" table of the role editor: a row without fields applies to all other fields, a row with fields — only to them. A row with the same field set is replaced, a new set is added. Typical: close the table and keep the reference presentation fields open — `Catalog.Products.Read: WHERE FALSE`, then `Catalog.Products.Read[Ref, Code, Description]: ` (empty condition).
- **Value from a file:** `@path` in place of an RLS condition, template body, synonym or comment (`-Value "Catalog.Products.Read: @condition.txt"`). A relative path is looked up next to `-DefinitionFile` (otherwise next to the role's `Rights.xml`), then in the current directory; `;;` inside the file is plain text.
- An error in any value is a refusal **before writing** — nothing changes. A locked role of a configuration on vendor support is refused ([support-manage.md](support-manage.md)).
- Auto-validation: `role-validate` runs after the write and its exit code is the result of the run. A missing validator is refused before the edit; `-NoValidate` is the only opt-out.

---
## 3. Info — Analyze Rights

Parses a role's `Rights.xml` and outputs a compact summary: objects grouped by type, showing only allowed rights. Compression: thousands of XML lines → 50–150 lines of text.

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-role-info/scripts/role-info.ps1 -RightsPath <path> -OutFile <output.txt>
```

| Parameter | Required | Description |
|-----------|:--------:|-------------|
| `-RightsPath` (alias `-Path`) | yes | Path to `Rights.xml` (positional) |
| `-ShowDenied` | no | Show denied rights (hidden by default) |
| `-Limit` | no | Max output lines (default `150`). `0` = unlimited |
| `-Offset` | no | Skip N lines — for pagination (default `0`) |
| `-OutFile` | no | Write result to file (UTF-8 BOM). Without this — console output |

**Important:** Always use `-OutFile` and read result via Read tool. Direct console output may corrupt Cyrillic characters.

```
=== Role: BasicRightsBP --- "Basic Rights: Enterprise Accounting" ===

Properties: setForNewObjects=false, setForAttributesByDefault=true, independentRightsOfChildObjects=false

Allowed rights:

  Catalog (8):
    Contractors: Read, View, InputByString
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

`[RLS]` — right with a row-level restriction; `-View`, `-Edit` — denied rights (with `-ShowDenied`); nested objects shown with a suffix: `Contractors.StandardAttribute.PredefinedDataName`.

---
## 4. Validate — Check Correctness

Checks a role's `Rights.xml`: XML format, namespace, global flags, object types, right names, nested kinds, RLS, templates, and — when `Roles/<RoleName>.xml` is found next to it (located from the `Rights.xml` path, there is no parameter for it) — the role metadata, the format version and the registration in `Configuration.xml`.

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-role-validate/scripts/role-validate.ps1 -RightsPath <path> [-OutFile <output.txt>] [-Detailed] [-MaxErrors <n>]
```

| Parameter | Required | Description |
|-----------|:--------:|-------------|
| `-RightsPath` (alias `-Path`) | yes | `Rights.xml` of the role, or the role folder `Roles/RoleName` (resolved to `Ext/Rights.xml`). The only positional parameter |
| `-OutFile` | no | Write result to file (UTF-8 BOM) — by name only |
| `-Detailed` | no | Print every passed check, not only the one-line summary |
| `-MaxErrors` | no | Stop after this many errors (default 30); the summary says the check stopped |

A second positional argument is a parameter error — it no longer binds to `-OutFile` and overwrites that file (for example `Roles/X.xml`) with the report.

**Errors** (exit `1`):

- invalid XML, wrong root element, object without `<name>`, `<right>` without `<name>`, a value other than `true` / `false`;
- a type without rights in roles (`Enum`, `CommonModule`, `CommonPicture`, `ScheduledJob`, …) or an unknown type;
- a right that does not exist for the type (with a suggestion), a nested kind impossible for the type or owned by another type, a right not allowed for the nested kind;
- a right on a whole service (`HTTPService.X`, `WebService.X`, `IntegrationService.X`) — the routes would answer 403;
- metadata: no `<Role>` element, invalid UUID, empty `<Name>`;
- the `Rights.xml` format version differs from `Roles/<Name>.xml` — the platform refuses to load parts of one object in different formats.

**Warnings**: namespace other than `http://v8.1c.ru/8.2/roles`, a missing / non-boolean global flag, an empty RLS condition, a template without name or condition, an empty synonym, a role version different from the dump (`Configuration.xml`; loads, but the dump is no longer uniform), the role not registered in `Configuration.xml`.

Exit code: `0` — no errors (warnings may exist), `1` — errors found. For Cyrillic paths use `-OutFile` and read the result via the Read tool.

---
## 5. Rights Reference

A role has rights on exactly 27 types; any other type is refused by `role-compile` / `role-edit` and is an error in `role-validate`. Full per-type lists: `$knownRights` in `role-compile.ps1` (the same table is in `role-edit.ps1`).

| Type | Rights |
|------|--------|
| `Configuration` | Administration, DataAdministration, UpdateDataBaseConfiguration, ConfigurationExtensionsAdministration, ActiveUsers, EventLog, ExclusiveMode, ThinClient, ThickClient, WebClient, MobileClient, ExternalConnection, Automation, Output, SaveUserData, TechnicalSpecialistMode, InteractiveOpenExtDataProcessors, InteractiveOpenExtReports, AnalyticsSystemClient, CollaborationSystemInfoBaseRegistration, MainWindowModeNormal, MainWindowModeWorkplace, MainWindowModeEmbeddedWorkplace, MainWindowModeFullscreenWorkplace, MainWindowModeKiosk |
| `Catalog`, `ChartOfCharacteristicTypes` | Read, Insert, Update, Delete, View, Edit, InputByString, Interactive* (Insert, SetDeletionMark, ClearDeletionMark, Delete, DeleteMarked), *PredefinedData, *DataHistory* |
| `Document` | the same + Posting, UndoPosting, InteractivePosting, InteractivePostingRegular, InteractiveUndoPosting, InteractiveChangeOfPosted |
| `ChartOfAccounts`, `ChartOfCalculationTypes`, `ExchangePlan` | Read, Insert, Update, Delete, View, Edit, InputByString, Interactive*, *DataHistory* |
| `BusinessProcess` | Read, Insert, Update, Delete, View, Edit, InputByString, Start, InteractiveInsert, InteractiveSetDeletionMark, InteractiveClearDeletionMark, InteractiveDelete, InteractiveDeleteMarked, InteractiveActivate, InteractiveStart, *DataHistory* |
| `Task` | the same, Execute / InteractiveExecute instead of Start / InteractiveStart |
| `InformationRegister` | Read, Update, View, Edit, TotalsControl, *DataHistory* |
| `AccumulationRegister`, `AccountingRegister` | Read, Update, View, Edit, TotalsControl |
| `CalculationRegister` | Read, Update, View, Edit |
| `Constant` | Read, Update, View, Edit, *DataHistory* |
| `DocumentJournal` | Read, View |
| `Sequence` | Read, Update |
| `DataProcessor`, `Report` | Use, View |
| `WebService`, `HTTPService`, `IntegrationService` | none on the root — only on nested objects (below) |
| `CommonForm`, `CommonCommand`, `Subsystem`, `FilterCriterion` | View |
| `CommonAttribute` | View, Edit |
| `SessionParameter` | Get, Set |
| `ExternalDataSource` | Use, Administration, StandardAuthenticationChange, SessionStandardAuthenticationChange, SessionOSAuthenticationChange |

### Nested objects

A path longer than two segments addresses part of an object; the next-to-last segment (the kind) sets the rights.

| Kind | Rights |
|------|--------|
| `Attribute`, `StandardAttribute`, `TabularSection`, `StandardTabularSection`, `Dimension`, `Resource`, `AccountingFlag`, `ExtDimensionAccountingFlag`, `AddressingAttribute` | View, Edit |
| `Command`, nested `Subsystem` | View |
| `Operation` (WebService), `Method` (HTTPService, under `URLTemplate`), `IntegrationServiceChannel` (IntegrationService) | Use |
| `Recalculation` (CalculationRegister) | Read, Update |
| `ExternalDataSource.X.Table.T` | Read, Insert, Update, Delete, View, Edit, InputByString, InteractiveInsert, InteractiveDelete |
| `…Table.T.Field.F`, `…Cube.C.DimensionTable.T.Field.F` | View, Edit |
| `ExternalDataSource.X.Cube.C`, `…Cube.C.DimensionTable.T` | Read, View |
| `…Cube.C.Dimension.D`, `…Cube.C.Resource.R`, `…Table.T.Command.K` (and Cube / DimensionTable commands) | View |
| `ExternalDataSource.X.Function.F` | Use, View |

`Operation`, `Method`, `IntegrationServiceChannel`, `Recalculation` and the external-data-source kinds (`Table`, `Cube`, `Function`, `Field`, `DimensionTable`) exist only under their own parent type. Document-journal columns (`DocumentJournal.J.Column.C`) have no rights. Examples: `Catalog.Contractors.Attribute.TIN: View, Edit`, `Document.Sales.TabularSection.Items.Attribute.Price: View`.

### Types without rights in roles

`Enum`, `CommonModule`, `DefinedType`, `CommonPicture`, `CommonTemplate`, `Language`, `FunctionalOption`, `FunctionalOptionsParameter`, `EventSubscription`, `ScheduledJob`, `StyleItem`, `Style`, `SettingsStorage`, `XDTOPackage`, `WSReference`, `DocumentNumerator` — absent from the role editor tree; a rights entry on them is refused / an error.

### Presets

| Preset | Type | Rights |
|--------|------|--------|
| `@view` | Catalog, ExchangePlan, Document, ChartOf*, BusinessProcess, Task | Read, View, InputByString |
| | InformationRegister, AccumulationRegister, AccountingRegister, CalculationRegister, Constant, DocumentJournal | Read, View |
| | Sequence | Read |
| | CommonForm, CommonCommand, Subsystem, FilterCriterion, CommonAttribute | View |
| | DataProcessor, Report | Use, View |
| | SessionParameter | Get |
| | Configuration | ThinClient, WebClient, Output, SaveUserData, MainWindowModeNormal |
| `@edit` | Catalog, ExchangePlan, ChartOf* | Read, Insert, Update, Delete, View, Edit, InputByString, InteractiveInsert, InteractiveSetDeletionMark, InteractiveClearDeletionMark |
| | Document | the same + Posting, UndoPosting, InteractivePosting, InteractivePostingRegular, InteractiveUndoPosting, InteractiveChangeOfPosted |
| | BusinessProcess / Task | the catalog set + Start, InteractiveActivate, InteractiveStart / Execute, InteractiveActivate, InteractiveExecute |
| | InformationRegister, AccumulationRegister, AccountingRegister, Constant | Read, Update, View, Edit |
| | DocumentJournal / Sequence / SessionParameter / CommonAttribute | Read, View / Read, Update / Get, Set / View, Edit |

No presets for services and external data sources — give the rights explicitly. Background jobs need only programmatic rights (Read, Insert, Update, Delete, Posting) — no Interactive / View / Edit and no client rights on `Configuration`.

---
## 6. Rights.xml Format (for reading)

```
Roles/
  RoleName.xml           ← metadata (uuid, name, synonym)
  RoleName/
    Ext/
      Rights.xml         ← rights definition
```

```xml
<Rights xmlns="http://v8.1c.ru/8.2/roles" xmlns:xs="http://www.w3.org/2001/XMLSchema"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="Rights" version="2.17">
    <setForNewObjects>false</setForNewObjects>
    <setForAttributesByDefault>true</setForAttributesByDefault>
    <independentRightsOfChildObjects>false</independentRightsOfChildObjects>
    <object>
        <name>Catalog.Products</name>
        <right><name>Read</name><value>true</value>
            <restrictionByCondition><condition>#ForObject("")</condition></restrictionByCondition>
            <restrictionByCondition><field>Ref</field><field>Code</field><condition/></restrictionByCondition>
        </right>
    </object>
    <restrictionTemplate>
        <name>ForObject(Modifier)</name>
        <condition>Template text</condition>
    </restrictionTemplate>
</Rights>
```

- Namespace `http://v8.1c.ru/8.2/roles` (historically 8.2); `version` equals the role descriptor's version.
- Object name — dot notation `ObjectType.Name[.NestedKind.NestedName]`.
- Only values different from the role default are stored (from format 2.19): with `setForNewObjects=false` the top level holds grants, with `true` — denials; nested attribute kinds follow `setForAttributesByDefault`.
- `<restrictionByCondition>` may repeat; `<field>` limits a row to those fields (standard attributes in English: `Ref`, `Code`, `Description`, `Date`, `Number`, …); an empty `<condition/>` means no restriction for them.

---
## Typical Workflow

```
1c-role-compile -JsonPath role.json -OutputDir <src>        — create a new role
1c-role-edit -RolePath <src>/Roles/<Name> -Operation ...    — change an existing role (runs role-validate)
1c-role-validate -RightsPath <src>/Roles/<Name>             — validate
1c-role-info -RightsPath <src>/Roles/<Name>/Ext/Rights.xml  — analyze before / after a change
```

MCP evidence set (`content/rules/tooling-playbooks.md`): `get_xsd_schema` / `verify_xml` with `object_type="Роль"`.

---

Scripts vendored from Nikolay-Shirokov/cc-1c-skills; sync history — `docs/CHANGELOG.md`.
