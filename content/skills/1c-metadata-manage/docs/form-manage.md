# 1C Form Manage — Patterns, Scaffold, Compile, Edit, Info, Validate

Comprehensive managed form management: design patterns reference, create/remove forms, compile from JSON, edit elements, analyze structure, validate correctness.

---

## 1. Patterns — Design Reference

Full reference of managed-form layout archetypes, naming conventions, layout principles and advanced ERP-class patterns lives in [`form-patterns.md`](form-patterns.md).

Load `form-patterns.md` **before** designing a form via `1c-form-compile` when user requirements do not specify element placement (5+ elements or unclear requirements). For simple 1–3 field forms it is not needed.

The reference covers:

- **Archetypes** — Document, Data Processor, List, Catalog Item (Simple/Complex), Wizard.
- **Naming** — group / element / event-handler conventions.
- **Layout principles** — reading order, two-column header, action buttons on `autoCmdBar`, totals near table, etc.
- **Advanced patterns** — collapsible groups, warning banners, popup menus, hyperlink labels, modal dialogs.

<details>
<summary>Quick archetype index (full versions in <code>form-patterns.md</code>)</summary>

#### Document Form

```
Header (horizontal, 2 columns)
├─ Left (vertical): NumberDate (H: Number + Date), Contractor, Contract
├─ Right (vertical): Organization, Department, PricesAndCurrency (hyperlink label)
Pages (pages)
├─ Items: table Object.Items
├─ Services: table Object.Services (optional)
└─ Additional: other attributes
Footer (vertical)
├─ Totals (horizontal): Total, VAT, Discount
└─ CommentResponsible (horizontal): Comment + Responsible
```

**Events:** OnCreateAtServer, OnReadAtServer, OnOpen, BeforeWriteAtServer, AfterWriteAtServer, AfterWrite, NotificationProcessing
**Properties:** autoTitle=false

#### Data Processor Form

```
Parameters (vertical)
├─ Input fields group (Organization, Period, operating modes)
├─ Information labels (label, hyperlink)
Working area
├─ Data table or Pages with tabs
Action buttons
├─ Execute / Apply (defaultButton)
├─ Close (stdCommand: Close)
```

**Events:** OnCreateAtServer, OnOpen, NotificationProcessing
**Properties:** windowOpeningMode=LockOwnerWindow (if dialog), autoTitle=false

#### List Form

```
Filters (group: alwaysHorizontal)
├─ FilterGroup[Field] (H): Checkbox + InputField (for each filter)
List (table, DynamicList)
├─ Columns: labelField (not input — data is read-only)
```

**Events:** OnCreateAtServer, OnOpen, NotificationProcessing, OnLoadDataFromSettingsAtServer
**Properties:** autoSaveDataInSettings=Use
**Filters:** pair of attributes per filter — `Filter[Field]` (value) + `Filter[Field]Use` (boolean)

#### Catalog Item Form

**Simple:**
```
AttributeGroup (horizontal)
├─ Description -> Object.Description
└─ Code -> Object.Code (if needed)
```

**Complex:**
```
Main (vertical)
├─ Description -> Object.Description
├─ Parameters (horizontal, 2 columns)
│  ├─ Left: main attributes
│  └─ Right: additional attributes
└─ ContactInfo / Additional (vertical)
```

**Events:** OnCreateAtServer, OnReadAtServer, BeforeWriteAtServer, NotificationProcessing

#### Wizard

```
Pages (pages, OnCurrentPageChange)
├─ Step1: description + parameters
├─ Step2: main work
└─ Step3: result
Buttons (horizontal)
├─ Back (command), Next (command, defaultButton), Execute (command)
└─ Close (stdCommand: Close)
```

**Properties:** windowOpeningMode=LockOwnerWindow, commandBarLocation=None

---

### Naming Conventions

#### Groups

| Purpose | Name | Type |
|---------|------|------|
| Header | `HeaderGroup` | horizontal |
| Left column | `HeaderLeftGroup` | vertical |
| Right column | `HeaderRightGroup` | vertical |
| Number+Date | `NumberDateGroup` | horizontal |
| Footer | `FooterGroup` | vertical |
| Totals | `TotalsGroup` | horizontal |
| Buttons | `ButtonsGroup` | horizontal |
| Pages | `PagesGroup` / `Pages` | pages |
| Warning | `WarningGroup` | horizontal, visible:false |
| Additional section | `AdditionalGroup` / `OtherGroup` | vertical, collapse |

#### Elements

| Purpose | Name |
|---------|------|
| Field in table | `[Table][Field]` |
| Total | `Totals[Field]` |
| Hyperlink label | `[Field]Label` |
| Filter | `Filter[Field]` |
| Filter checkbox | `Filter[Field]Use` |
| Command button | `[Command]Button` |
| Banner image | `[Banner]Picture` |
| Banner label | `[Banner]Label` |
| Submenu | `Submenu[Action]` |

#### Event Handlers

Name = element name + Russian suffix:

| Event | Suffix | Example |
|-------|--------|---------|
| OnChange | ПриИзменении | `ОрганизацияПриИзменении` |
| StartChoice | НачалоВыбора | `КонтрагентНачалоВыбора` |
| Click | Нажатие | `ЦеныИВалютаНажатие` |
| OnEditEnd | ПриОкончанииРедактирования | `ТоварыПриОкончанииРедактирования` |
| OnStartEdit | ПриНачалеРедактирования | `ТоварыПриНачалеРедактирования` |

Form handlers: `ПриСозданииНаСервере`, `ПриОткрытии`, `ПередЗакрытием`, `ОбработкаОповещения`.

---

### Layout Principles

1. **Reading order.** Top to bottom, left to right. Most important — at top.
2. **Two-column header.** Main attributes on left (contractor, warehouse), organizational on right (organization, department).
3. **Action buttons at bottom.** Main button — `defaultButton: true`. Close — always last.
4. **Tables are the main area.** Tabular sections occupy most of the form, usually on Pages.
5. **Totals near table.** In footer, horizontal group, all fields readOnly.
6. **Filters as separate zone.** Above list, alwaysHorizontal, pair of "checkbox + field" per filter.
7. **Hidden elements for states.** Banners, warnings — `visible: false`, shown programmatically.
8. **Hyperlink labels for dialogs.** `labelField` with `hyperlink: true` and Click event.

---

### Advanced Patterns

#### Collapsible Groups

For optional sections (signatures, additional, other):

```json
{ "group": "vertical", "name": "SignaturesGroup", "title": "Signatures",
  "behavior": "Collapsible", "collapsed": true, "children": [...] }
```

#### Warning Banner

Group "image + label", hidden by default, shown programmatically:

```json
{ "group": "horizontal", "name": "WarningGroup", "showTitle": false,
  "visible": false, "children": [
    { "picture": "WarningPicture" },
    { "label": "WarningLabel", "title": "Text", "maxWidth": 76, "autoMaxWidth": false }
]}
```

#### Popup Menu in Command Bar

Grouping related commands (print, send) in one button with icon:

```json
{ "cmdBar": "CommandBar", "children": [
    { "popup": "SubmenuPrint", "title": "Print",
      "picture": "StdPicture.Print", "representation": "Picture", "children": [
        { "button": "PrintInvoice", "command": "Print" },
        { "button": "PrintReceipt", "command": "PrintReceipt" }
    ]}
]}
```

#### Form Without Standard Command Bar

For modal dialogs and wizards:

```json
{ "properties": { "commandBarLocation": "None", "windowOpeningMode": "LockWholeInterface" } }
```

#### Hyperlink Label

Instead of a button for opening subforms (PricesAndCurrency, AccountingPolicy):

```json
{ "labelField": "PricesAndCurrencyLabel", "path": "PricesAndCurrency", "hyperlink": true, "on": ["Click"] }
```

---

### Full DSL Example: Data Processor Form

```json
{
  "title": "CSV Data Import",
  "properties": { "autoTitle": false, "windowOpeningMode": "LockOwnerWindow" },
  "events": { "OnCreateAtServer": "OnCreateAtServerHandler" },
  "elements": [
    { "group": "vertical", "name": "ParametersGroup", "children": [
      { "input": "ImportFile", "path": "ImportFile", "title": "File", "clearButton": true, "horizontalStretch": true, "on": ["StartChoice"] },
      { "input": "Encoding", "path": "Encoding" },
      { "input": "Delimiter", "path": "Delimiter", "title": "Column Delimiter" }
    ]},
    { "table": "Data", "path": "Object.Data", "on": ["OnStartEdit"], "columns": [
      { "input": "DataRowNumber", "path": "Object.Data.LineNumber", "readOnly": true, "title": "No." },
      { "input": "DataName", "path": "Object.Data.Name" },
      { "input": "DataQuantity", "path": "Object.Data.Quantity", "on": ["OnChange"] },
      { "input": "DataAmount", "path": "Object.Data.Amount", "readOnly": true }
    ]},
    { "group": "horizontal", "name": "ButtonsGroup", "children": [
      { "button": "Import", "command": "Import", "title": "Import from File", "defaultButton": true },
      { "button": "Clear", "command": "Clear", "title": "Clear Table" },
      { "button": "Close", "stdCommand": "Close" }
    ]}
  ],
  "attributes": [
    { "name": "Object", "type": "ExternalDataProcessorObject.CSVImport", "main": true },
    { "name": "ImportFile", "type": "string" },
    { "name": "Encoding", "type": "string(20)" },
    { "name": "Delimiter", "type": "string(5)" }
  ],
  "commands": [
    { "name": "Import", "action": "ImportHandler" },
    { "name": "Clear", "action": "ClearHandler" }
  ]
}
```

</details>

---

## 2. Scaffold — Create or Remove Form

Creates a managed form (metadata XML + Form.xml + Module.bsl) and registers it in the root XML of a 1C metadata object. A single unified script handles both configuration objects (Document, Catalog, InformationRegister, …) and standalone External Data Processors / Reports (EPF/ERF). The same is true for removal.

> **Note:** the previous EPF-specific entry points (`add-form.ps1` taking `-ProcessorName`, and the EPF-only variant of `remove-form.ps1`) were merged into the unified `form-add.ps1` / `remove-form.ps1` scripts (`ObjectPath` / `ObjectName`). The unified scripts auto-detect the object kind from the XML root and apply the right scaffolding rules — EPF/ERF forms get `ExtendedPresentation`, regular config objects do not.

### Adding a Form

```
1c-form-scaffold add <ObjectPath> <FormName> [Purpose] [Synonym] [--set-default]
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| ObjectPath | yes | — | Path to the object XML file (e.g. `Documents/Doc.xml`) or directory; for EPF/ERF — path to the processor/report root XML (`src/MyProcessor.xml` or its directory) |
| FormName | yes | — | Form name |
| Purpose | no | Object | Purpose: `Object`, `List`, `Choice`, `Record`, `Folder` |
| Synonym | no | = FormName | Form synonym |
| --set-default | no | auto | Set as default form (auto for the first form of that purpose) |

**Command:**
```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-form-scaffold/scripts/form-add.ps1 -ObjectPath "<ObjectPath>" -FormName "<FormName>" [-Purpose "<Purpose>"] [-Synonym "<Synonym>"] [-SetDefault]
```

The script auto-detects the format version of `Form.xml` from the nearest `Configuration.xml` (8.3.27+, 8.5).

#### Purpose — Form Assignment

| Purpose | Allowed Object Types | Main Attribute | DefaultForm Property |
|---------|---------------------|---------------|---------------------|
| Object | Document, Catalog, DataProcessor, Report, ChartOf*, ExchangePlan, BusinessProcess, Task | Object (type: *Object.Name) | DefaultObjectForm (DefaultForm for DataProcessor/Report) |
| List | All except DataProcessor | List (DynamicList) | DefaultListForm |
| Choice | Document, Catalog, ChartOf*, ExchangePlan, BusinessProcess, Task | List (DynamicList) | DefaultChoiceForm |
| Record | InformationRegister | Record (InformationRegisterRecordManager) | DefaultRecordForm |

#### What Gets Created

```
<ObjectDir>/Forms/
├── <FormName>.xml                    # Form metadata (UUID)
└── <FormName>/
    └── Ext/
        ├── Form.xml                  # Form description (logform namespace)
        └── Form/
            └── Module.bsl           # BSL module with 5 regions + OnCreateAtServer
```

#### What Gets Modified

- `<ObjectPath>` — adds `<Form>` to `ChildObjects` (before `<Template>` or `<TabularSection>`), updates Default*Form (auto if empty, or explicit with `--set-default`)

#### Details

- FormType: Managed
- UsePurposes: PlatformApplication, MobilePlatformApplication
- AutoCommandBar with id=-1
- "Object" attribute with MainAttribute=true
- BSL module contains 5 regions: FormEventHandlers, FormItemEventHandlers, FormCommandHandlers, NotificationHandlers, PrivateProceduresAndFunctions

#### Supported Object Types

Document, Catalog, DataProcessor, Report, InformationRegister, ChartOfAccounts, ChartOfCharacteristicTypes, ExchangePlan, BusinessProcess, Task

---

### Removing a Form

Unified across configuration objects and EPF/ERF — pass the object name (or alias `ProcessorName` for backward compatibility).

```
1c-form-scaffold remove <ObjectName> <FormName> [SrcDir]
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| ObjectName (alias `ProcessorName`) | yes | — | Object name (root XML lives at `<SrcDir>/<ObjectName>.xml`) |
| FormName | yes | — | Form name to remove |
| SrcDir | no | `src` | Source directory |

**Command:**
```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-form-scaffold/scripts/remove-form.ps1 -ObjectName "<ObjectName>" -FormName "<FormName>" [-SrcDir "<SrcDir>"]
```

#### What Gets Removed

```
<SrcDir>/<ObjectName>/Forms/<FormName>.xml     # Form metadata
<SrcDir>/<ObjectName>/Forms/<FormName>/         # Form directory (recursive)
```

#### What Gets Modified

- `<SrcDir>/<ObjectName>.xml` — removes `<Form>` from `ChildObjects`
- If the removed form was Default*Form — the corresponding default property is cleared

---

### Examples

```bash
# Document form
1c-form-scaffold add Documents/SalesOrder.xml DocumentForm --purpose Object

# Catalog list form
1c-form-scaffold add Catalogs/Contractors.xml ListForm --purpose List

# Information register record form
1c-form-scaffold add InformationRegisters/CurrencyRates.xml RecordForm --purpose Record

# Choice form with synonym
1c-form-scaffold add Catalogs/Products.xml ChoiceForm --purpose Choice --synonym "Product Selection"

# Set as default form
1c-form-scaffold add Documents/Order.xml NewDocumentForm --purpose Object --set-default

# EPF / ERF form (same unified script — pass the path to the EPF root XML)
1c-form-scaffold add src/MyProcessor.xml MainForm --synonym "Main Form" --set-default

# Remove a form (works for both config objects and EPF/ERF)
1c-form-scaffold remove MyProcessor OldForm
```

---

## 3. Compile — Generate from JSON or from Object Metadata

Two modes:

1. **JSON DSL** — generate `Form.xml` from a JSON definition.
2. **From-object** (`-FromObject`) — generate a typical form from an object's metadata (Catalog, Document, InformationRegister, AccumulationRegister, ChartOfCharacteristicTypes, ExchangePlan, ChartOfAccounts) using the active preset (default `erp-standard`).

> **Designing a form from scratch (5+ elements or unclear requirements)** — load [`form-patterns.md`](form-patterns.md) first. For simple forms (1–3 fields) it is not needed.
>
> **Full DSL reference** — see [`form-compile-dsl.md`](form-compile-dsl.md). The block below is a quick summary.

### What's New (vs the previous local snapshot)

- **`-FromObject` mode** — produces a typical form from object metadata; purpose (`Object`/`List`/`Choice`/`Folder`/`Record`) is inferred from `OutputPath`. Document list forms get the standard `Number` and `Date` columns automatically; ChartOfAccounts pulls accounting flags / sub-account kinds correctly.
- **New element types** — `radio` (RadioButtonField with `radioButtonType`: `Auto` / `RadioButtons` / `Tumbler`, `choiceList`); `autoCmdBar` (fills the form's main AutoCommandBar id=-1); `columnGroup` (column grouping inside table `columns` — `horizontal` / `vertical` / `inCell`, nestable).
- **New input keys** — `textEdit: false` (disable free text editing on reference fields), `maxWidth` / `maxHeight` (hard caps, usually with `autoMaxWidth: false`).
- **New group key** — `collapsed: true` for `"group": "collapsible"` (group starts collapsed).
- **Multilingual strings** — any title / presentation may be `{ "ru": "...", "en": "..." }`.
- **Auto-titles** — attributes, commands, pages, popups and decorations without explicit `title` get a humanised title from the name (`НомерСчёта` → "Номер счёта").
- **Format version** — auto-detected from the nearest `Configuration.xml` (8.3.27+, 8.5).
- **Presets** — `tools/1c-form-compile/presets/erp-standard.json` is shipped; project-level override at `<projectRoot>/presets/skills/form/<name>.json`.
- **Defaults aligned with real ERP/БП forms** — multi-line inputs are not auto-width-bounded by default; checkbox title is on the right; `autoTitle` is suppressed when `title` is set; objects with editable state save the input state (`Esc → confirm`).

### Usage

```
1c-form-compile <JsonPath> <OutputPath>            # JSON DSL mode
1c-form-compile -FromObject <OutputPath>           # from-object mode
```

| Parameter | Required | Description |
|-----------|:--------:|-------------|
| `JsonPath`   | mode 1 | Path to the form JSON definition |
| `OutputPath` | yes    | Path to the output `Form.xml` |
| `FromObject` | mode 2 | Switch — generate from object metadata |
| `Preset`     | no     | Preset name (default `erp-standard`) |

### Command

```powershell
# JSON DSL
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-form-compile/scripts/form-compile.ps1 -JsonPath "<json>" -OutputPath "<xml>"

# From-object (Catalog / Document / Register / ChartOf* / ExchangePlan)
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-form-compile/scripts/form-compile.ps1 -FromObject -OutputPath "<.../TypePlural/ObjectName/Forms/FormName/Ext/Form.xml>"
```

### JSON DSL Quick Summary

#### Top-Level Structure

```json
{
  "title": "Form Title",
  "properties": { "autoTitle": false, ... },
  "events": { "OnCreateAtServer": "OnCreateAtServerHandler" },
  "excludedCommands": ["Reread"],
  "elements": [ ... ],
  "attributes": [ ... ],
  "commands": [ ... ],
  "parameters": [ ... ]
}
```

- `title` — form title (multilingual). Can also be in `properties`, but top-level is preferred
- `properties` — form properties: `autoTitle`, `windowOpeningMode`, `commandBarLocation`, `saveDataInSettings`, `width`, `height`, etc.
- `events` — form event handlers (key: 1C event name, value: procedure name)
- `excludedCommands` — excluded standard commands

#### Elements (key determines type)

| DSL Key | XML Element | Key Value |
|---------|-------------|-----------|
| `"group"` | UsualGroup | `"horizontal"` / `"vertical"` / `"alwaysHorizontal"` / `"alwaysVertical"` / `"collapsible"` |
| `"input"` | InputField | element name |
| `"check"` | CheckBoxField | name |
| `"label"` | LabelDecoration | name (text set via `title`) |
| `"labelField"` | LabelField | name |
| `"table"` | Table | name |
| `"pages"` | Pages | name |
| `"page"` | Page | name |
| `"button"` | Button | name |
| `"picture"` | PictureDecoration | name |
| `"picField"` | PictureField | name |
| `"calendar"` | CalendarField | name |
| `"cmdBar"` | CommandBar | name |
| `"popup"` | Popup | name |

#### Common Properties (all element types)

| Key | Description |
|-----|-------------|
| `name` | Override name (default = type key value) |
| `title` | Element title |
| `visible: false` | Hide (synonym: `hidden: true`) |
| `enabled: false` | Disable (synonym: `disabled: true`) |
| `readOnly: true` | Read-only |
| `on: [...]` | Events with auto-named handlers |
| `handlers: {...}` | Explicit handler names: `{"OnChange": "MyHandler"}` |

#### Allowed Event Names (`on`)

The compiler warns about unknown events. Names are case-sensitive — use exactly as shown.

**Form** (`events`): `OnCreateAtServer`, `OnOpen`, `BeforeClose`, `OnClose`, `NotificationProcessing`, `ChoiceProcessing`, `OnReadAtServer`, `BeforeWriteAtServer`, `OnWriteAtServer`, `AfterWriteAtServer`, `BeforeWrite`, `AfterWrite`, `FillCheckProcessingAtServer`, `BeforeLoadDataFromSettingsAtServer`, `OnLoadDataFromSettingsAtServer`, `ExternalEvent`, `Opening`

**input / picField**: `OnChange`, `StartChoice`, `ChoiceProcessing`, `AutoComplete`, `TextEditEnd`, `Clearing`, `Creating`, `EditTextChange`

**check**: `OnChange`

**table**: `OnStartEdit`, `OnEditEnd`, `OnChange`, `Selection`, `ValueChoice`, `BeforeAddRow`, `BeforeDeleteRow`, `AfterDeleteRow`, `BeforeRowChange`, `BeforeEditEnd`, `OnActivateRow`, `OnActivateCell`, `Drag`, `DragStart`, `DragCheck`, `DragEnd`

**label / picture**: `Click`, `URLProcessing`

**labelField**: `OnChange`, `StartChoice`, `ChoiceProcessing`, `Click`, `URLProcessing`, `Clearing`

**button**: `Click`

**pages**: `OnCurrentPageChange`

#### Input Field

| Key | Description | Example |
|-----|-------------|---------|
| `path` | DataPath — data binding | `"Object.Organization"` |
| `titleLocation` | Title location | `"none"`, `"left"`, `"top"` |
| `multiLine: true` | Multi-line field | text field, comment |
| `passwordMode: true` | Password mode (asterisks) | password input |
| `choiceButton: true` | Choice button ("...") | reference field |
| `clearButton: true` | Clear button ("X") | |
| `spinButton: true` | Spin button | numeric fields |
| `dropListButton: true` | Drop-down list button | |
| `markIncomplete: true` | Mark as incomplete | required fields |
| `skipOnInput: true` | Skip on Tab traversal | |
| `inputHint` | Hint in empty field | `"Enter name..."` |
| `width` / `height` | Size | numbers |
| `autoMaxWidth: false` | Disable auto-width | for fixed fields |
| `horizontalStretch: true` | Stretch horizontally | |

#### Checkbox

| Key | Description |
|-----|-------------|
| `path` | DataPath |
| `titleLocation` | Title location |

#### Label Decoration

| Key | Description |
|-----|-------------|
| `title` | Label text (required) |
| `hyperlink: true` | Make it a hyperlink |
| `width` / `height` | Size |

#### Group

Value of the key sets orientation: `"horizontal"`, `"vertical"`, `"alwaysHorizontal"`, `"alwaysVertical"`, `"collapsible"`.

| Key | Description |
|-----|-------------|
| `showTitle: true` | Show group title |
| `united: false` | Do not unite border |
| `representation` | `"none"`, `"normal"`, `"weak"`, `"strong"` |
| `children: [...]` | Nested elements |

#### Table

**Important**: a table requires an associated form attribute of type `ValueTable` with columns (see "Bindings" section).

| Key | Description |
|-----|-------------|
| `path` | DataPath (binding to table attribute) |
| `columns: [...]` | Columns — array of elements (usually `input`) |
| `changeRowSet: true` | Allow adding/removing rows |
| `changeRowOrder: true` | Allow row reordering |
| `height` | Height in table rows |
| `header: false` | Hide header |
| `footer: true` | Show footer |
| `commandBarLocation` | `"None"`, `"Top"`, `"Auto"` |
| `searchStringLocation` | `"None"`, `"Top"`, `"Auto"` |

#### Pages (pages + page)

| Key (pages) | Description |
|-------------|-------------|
| `pagesRepresentation` | `"None"`, `"TabsOnTop"`, `"TabsOnBottom"`, etc. |
| `children: [...]` | Array of `page` elements |

| Key (page) | Description |
|------------|-------------|
| `title` | Tab title |
| `group` | Orientation inside page |
| `children: [...]` | Page content |

#### Button

| Key | Description |
|-----|-------------|
| `command` | Form command name → `Form.Command.Name` |
| `stdCommand` | Standard command: `"Close"` → `Form.StandardCommand.Close`; with dot: `"Items.Add"` → `Form.Item.Items.StandardCommand.Add` |
| `defaultButton: true` | Default button |
| `type` | `"usual"`, `"hyperlink"`, `"commandBar"` |
| `picture` | Button picture |
| `representation` | `"Auto"`, `"Text"`, `"Picture"`, `"PictureAndText"` |
| `locationInCommandBar` | `"Auto"`, `"InCommandBar"`, `"InAdditionalSubmenu"` |

#### Command Bar (cmdBar)

| Key | Description |
|-----|-------------|
| `autofill: true` | Auto-fill with standard commands |
| `children: [...]` | Bar buttons |

#### Popup Menu

| Key | Description |
|-----|-------------|
| `title` | Submenu title |
| `children: [...]` | Submenu buttons |

Used inside `cmdBar` to group buttons:
```json
{ "cmdBar": "Panel", "children": [
  { "popup": "Add", "title": "Add", "children": [
    { "button": "AddRow", "stdCommand": "Items.Add" },
    { "button": "AddFromDocument", "command": "AddFromDocument", "title": "From Document" }
  ]}
]}
```

#### Attributes

```json
{ "name": "Object", "type": "DataProcessorObject.Import", "main": true }
{ "name": "Total", "type": "decimal(15,2)" }
{ "name": "Table", "type": "ValueTable", "columns": [
    { "name": "Product", "type": "CatalogRef.Products" },
    { "name": "Quantity", "type": "decimal(10,3)" }
]}
```

- `savedData: true` — saved data

#### Commands

```json
{ "name": "Import", "action": "ImportHandler", "shortcut": "Ctrl+Enter" }
```

- `title` — title (if different from name)
- `picture` — command picture

#### Type System

| DSL | XML |
|-----|-----|
| `"string"` / `"string(100)"` | `xs:string` + StringQualifiers |
| `"decimal(15,2)"` | `xs:decimal` + NumberQualifiers |
| `"decimal(10,0,nonneg)"` | with AllowedSign=Nonnegative |
| `"boolean"` | `xs:boolean` |
| `"date"` / `"dateTime"` / `"time"` | `xs:dateTime` + DateFractions |
| `"CatalogRef.XXX"` | `cfg:CatalogRef.XXX` |
| `"DocumentRef.XXX"` | `cfg:DocumentRef.XXX` |
| `"ValueTable"` | `v8:ValueTable` |
| `"ValueList"` | `v8:ValueListType` |
| `"Type1 \| Type2"` | composite type |

### Bindings: Element + Attribute

Tables and some fields require an associated attribute. Elements reference attributes via `path`.

**Table** — `table` element + `ValueTable` attribute:
```json
{
  "elements": [
    { "table": "Items", "path": "Object.Items", "columns": [
      { "input": "Product", "path": "Object.Items.Product" }
    ]}
  ],
  "attributes": [
    { "name": "Object", "type": "DataProcessorObject.Import", "main": true,
      "columns": [
        { "name": "Items", "type": "ValueTable", "columns": [
          { "name": "Product", "type": "CatalogRef.Products" }
        ]}
      ]
    }
  ]
}
```

Or, if table is bound to a form attribute (not Object):
```json
{
  "elements": [
    { "table": "DataTable", "path": "DataTable", "columns": [
      { "input": "Name", "path": "DataTable.Name" }
    ]}
  ],
  "attributes": [
    { "name": "DataTable", "type": "ValueTable", "columns": [
      { "name": "Name", "type": "string(150)" }
    ]}
  ]
}
```

### Auto-generation

- **Companion elements**: ContextMenu, ExtendedTooltip, etc. are created automatically
- **Event handlers**: `"on": ["OnChange"]` → auto-named handler
- **Namespace**: all 17 namespace declarations
- **IDs**: sequential numbering, AutoCommandBar = id="-1"
- **Unknown keys**: warning about unrecognized keys

### Verification

```
1c-form-validate <OutputPath>    — check XML correctness
1c-form-info <OutputPath>        — visual structure summary
```

### Notes for External Data Processors (EPF)

- **Main attribute type**: `ExternalDataProcessorObject.ProcessorName` (not `DataProcessorObject`)
- **DataPath**: use form attributes (`AttributeName`), not `Object.AttributeName` — external data processors have no object attributes in metadata
- **Reference types**: `CatalogRef.XXX`, `DocumentRef.XXX`, etc. may not build in an empty infobase — use `string` or basic types for standalone builds

---

## 4. Edit — Add Elements, Attributes, Commands

Adds elements, attributes, and/or commands to an existing Form.xml. Automatically allocates IDs from the correct pool, generates companion elements (ContextMenu, ExtendedTooltip, etc.) and event handlers.

### Usage

```
1c-form-edit <FormPath> <JsonPath>
```

| Parameter | Required | Description |
|-----------|:--------:|-------------|
| FormPath | yes | Path to existing Form.xml |
| JsonPath | yes | Path to JSON with additions |

### Command

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-form-edit/scripts/form-edit.ps1 -FormPath "<path>" -JsonPath "<path>"
```

### JSON Format

```json
{
  "into": "HeaderGroup",
  "after": "Contractor",
  "elements": [
    { "input": "Warehouse", "path": "Object.Warehouse", "on": ["OnChange"] }
  ],
  "attributes": [
    { "name": "TotalAmount", "type": "decimal(15,2)" }
  ],
  "commands": [
    { "name": "Calculate", "action": "CalculateHandler" }
  ]
}
```

#### Element Positioning

| Key | Default | Description |
|-----|---------|-------------|
| `into` | root ChildItems | Name of group/table/page to insert into |
| `after` | at end | Name of element to insert after |

#### Element Types

Same DSL keys as in `1c-form-compile`:

| Key | XML Tag | Companions |
|-----|---------|------------|
| `input` | InputField | ContextMenu, ExtendedTooltip |
| `check` | CheckBoxField | ContextMenu, ExtendedTooltip |
| `label` | LabelDecoration | ContextMenu, ExtendedTooltip |
| `labelField` | LabelField | ContextMenu, ExtendedTooltip |
| `group` | UsualGroup | ExtendedTooltip |
| `table` | Table | ContextMenu, AutoCommandBar, Search*, ViewStatus* |
| `pages` | Pages | ExtendedTooltip |
| `page` | Page | ExtendedTooltip |
| `button` | Button | ExtendedTooltip |

Groups and tables support `children`/`columns` for nested elements.

#### Buttons: command and stdCommand

- `"command": "CommandName"` → `Form.Command.CommandName`
- `"stdCommand": "Close"` → `Form.StandardCommand.Close`
- `"stdCommand": "Items.Add"` → `Form.Item.Items.StandardCommand.Add` (standard item command)

#### Allowed Events (`on`)

The compiler warns about errors in event names. Main events:

- **input**: `OnChange`, `StartChoice`, `ChoiceProcessing`, `Clearing`, `AutoComplete`, `TextEditEnd`
- **check**: `OnChange`
- **table**: `OnStartEdit`, `OnEditEnd`, `OnChange`, `Selection`, `BeforeAddRow`, `BeforeDeleteRow`, `OnActivateRow`
- **label/picture**: `Click`, `URLProcessing`
- **pages**: `OnCurrentPageChange`
- **button**: `Click`

#### Type System (for attributes)

`string`, `string(100)`, `decimal(15,2)`, `boolean`, `date`, `dateTime`, `CatalogRef.XXX`, `DocumentObject.XXX`, `ValueTable`, `DynamicList`, `Type1 | Type2` (composite).

### Output

```
=== form-edit: FormName ===

Added elements (into HeaderGroup, after Contractor):
  + [Input] Warehouse -> Object.Warehouse {OnChange}

Added attributes:
  + TotalAmount: decimal(15,2) (id=12)

---
Total: 1 element(s) (+2 companions), 1 attribute(s)
Run 1c-form-validate to verify.
```

### When to Use

- **After `1c-form-compile`**: add elements not included in the original JSON
- **Modifying existing forms**: add a field, attribute, or command to a form from configuration
- **Batch additions**: one JSON can contain elements + attributes + commands

---

## 5. Info — Analyze Structure

Reads a Form.xml of a managed form and outputs a compact summary: element tree, typed attributes, commands, events. Replaces the need to read thousands of XML lines.

> **Behavioural note.** Pages are collapsed by default to a `(N items)` summary — to keep large forms scannable. Use `-Expand <name|*>` to expand specific pages (or `*` for all). The main form auto command bar is rendered as a separate section, separately from the layout tree.

### Usage

```
1c-form-info <FormPath>
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| `Path` (alias `FormPath`) | yes | — | Path to `Form.xml` (also accepts a folder, the script resolves to `Forms/<Name>/Ext/Form.xml`) |
| `Expand` | no | — | Page names to expand: list of names, single name, or `*` for all |
| `Limit` | no | `150` | Max output lines (overflow protection) |
| `Offset` | no | `0` | Skip N lines (for pagination) |

### Command

```powershell
# Default — pages collapsed, main command bar shown as a separate section
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-form-info/scripts/form-info.ps1 -Path "<path to Form.xml>"

# Expand a specific page
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-form-info/scripts/form-info.ps1 -Path "<path>" -Expand "Goods"

# Expand all pages
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-form-info/scripts/form-info.ps1 -Path "<path>" -Expand "*"
```

With pagination:
```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-form-info/scripts/form-info.ps1 -Path "<path>" -Offset 150
```

### Reading the Output

#### Header

```
=== Form: DocumentForm — "Sales of Goods and Services" (Documents.SalesInvoice) ===
```

Form name, Title, and object context are determined from the file path and XML.

#### Properties — Form Properties

Only non-default properties are shown. Title is shown in the header, not here:

```
Properties: AutoTitle=false, WindowOpeningMode=LockOwnerWindow, CommandBarLocation=Bottom
```

#### Events — Form Event Handlers

```
Events:
  OnCreateAtServer -> OnCreateAtServerHandler
  OnOpen -> OnOpenHandler
```

#### Elements — UI Element Tree

Compact tree with types, data bindings, flags, and events:

```
Elements:
  ├─ [Group:AH] HeaderGroup
  │  ├─ [Input] Organization -> Object.Organization {OnChange}
  │  └─ [Input] Contract -> Object.Contract [visible:false] {StartChoice}
  ├─ [Table] Items -> Object.Items
  │  ├─ [Input] Product -> Object.Items.Product {OnChange}
  │  └─ [Input] Amount -> Object.Items.Amount [ro]
  └─ [Pages] Pages
     ├─ [Page] Main (5 items)
     └─ [Page] Print (2 items)
```

**Element Type Abbreviations:**

| Abbreviation | Element |
|---|---|
| `[Group:V]` | UsualGroup Vertical |
| `[Group:H]` | UsualGroup Horizontal |
| `[Group:AH]` | UsualGroup AlwaysHorizontal |
| `[Group:AV]` | UsualGroup AlwaysVertical |
| `[Group]` | UsualGroup (default orientation) |
| `[Input]` | InputField |
| `[Check]` | CheckBoxField |
| `[Label]` | LabelDecoration |
| `[LabelField]` | LabelField |
| `[Picture]` | PictureDecoration |
| `[PicField]` | PictureField |
| `[Calendar]` | CalendarField |
| `[Table]` | Table |
| `[Button]` | Button |
| `[CmdBar]` | CommandBar |
| `[Pages]` | Pages |
| `[Page]` | Page (shows item count instead of expanding by default; use `-Expand` to drill in) |
| `[Popup]` | Popup |
| `[BtnGroup]` | ButtonGroup |
| `[AutoCmdBar]` | Form AutoCommandBar (id=-1) — rendered as a separate "Main Form Command Bar" section, not in the layout tree |

**Flags** (only when deviating from default):
- `[visible:false]` — element is hidden (Visible=false)
- `[enabled:false]` — element is disabled (Enabled=false)
- `[ro]` — ReadOnly=true
- `,collapse` — Behavior=Collapsible (for groups)

**Data binding**: `-> Object.Field` — DataPath

**Command binding**: `-> CommandName [cmd]` — form command, `-> Close [std]` — standard command

**Events**: `{OnChange, StartChoice}` — handler names

**Title**: `[title:Text]` — only if different from element name

#### Attributes — Form Attributes

```
Attributes:
  *Object: DocumentObject.SalesInvoice (main)
  Currency: CatalogRef.Currencies
  Total: decimal(15,2)
  Table: ValueTable [Product: CatalogRef.Products, Qty: decimal(10,3)]
  List: DynamicList -> Catalog.Users
```

- `*` and `(main)` — main form attribute (MainAttribute)
- ValueTable/ValueTree types expand columns in `[...]`
- DynamicList shows MainTable via `->`

#### Parameters — Form Parameters

```
Parameters:
  Key: DocumentRef.PurchaseOrder (key)
  Basis: DocumentRef.*
```

- `(key)` — key parameter (KeyParameter)

#### Commands — Form Commands

```
Commands:
  Print -> PrintDocumentHandler [Ctrl+P]
  Fill -> FillHandler
```

Format: `Name -> Handler [Shortcut]`

### What Gets Skipped

The script removes 80%+ of XML volume:
- Visual properties (Width, Height, Color, Font, Border, Align, Stretch)
- Auto-generated ExtendedTooltip and ContextMenu
- Multilingual wrappers (v8:item/v8:lang/v8:content)
- Namespace declarations
- ID attributes

For detailed inspection — use grep on element name from the summary.

### When to Use

- **Before modifying a form**: understand structure, find the right group for inserting an element
- **Form analysis**: which attributes, commands, handlers are used
- **Navigating large forms**: 28K lines of XML → 50-100 lines of context

### Overflow Protection

Output is limited to 150 lines by default. When exceeded:
```
[TRUNCATED] Shown 150 of 220 lines. Use -Offset 150 to continue.
```

Use `-Offset N` and `-Limit N` for paginated viewing.

---

## 6. Validate — Check Correctness

Checks Form.xml of a managed form for structural errors: ID uniqueness, companion element presence, DataPath and command reference correctness.

### Usage

```
1c-form-validate <FormPath>
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| FormPath | yes | — | Path to Form.xml file |
| MaxErrors | no | 30 | Stop after N errors |

### Command

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-form-validate/scripts/form-validate.ps1 -FormPath "<path>"
```

### Checks Performed

| # | Check | Severity |
|---|-------|----------|
| 1 | Root element `<Form>`, version="2.17" | ERROR / WARN |
| 2 | `<AutoCommandBar>` present, id="-1" | ERROR |
| 3 | Element ID uniqueness (separate pool) | ERROR |
| 4 | Attribute ID uniqueness (separate pool) | ERROR |
| 5 | Command ID uniqueness (separate pool) | ERROR |
| 6 | Companion elements (ContextMenu, ExtendedTooltip, etc.) | ERROR |
| 7 | DataPath → references existing attribute | ERROR |
| 8 | Button CommandName → references existing command | ERROR |
| 9 | Events have non-empty handler names | ERROR |
| 10 | Commands have Action (handler) | ERROR |
| 11 | No more than one MainAttribute | ERROR |

### Output

```
=== Validation: DocumentForm ===

[OK]    Root element: Form version=2.17
[OK]    AutoCommandBar: name='FormCommandBar', id=-1
[OK]    Unique element IDs: 96 elements
[OK]    Unique attribute IDs: 38 entries
[OK]    Unique command IDs: 5 entries
[OK]    Companion elements: 86 elements checked
[OK]    DataPath references: 53 paths checked
[OK]    Command references: 2 buttons checked
[OK]    Event handlers: 41 events checked
[OK]    Command actions: 5 commands checked
[OK]    MainAttribute: 1 main attribute

---
Total: 96 elements, 38 attributes, 5 commands
All checks passed.
```

Return code: 0 = all checks passed, 1 = errors found.

### When to Use

- **After `1c-form-compile`**: verify correctness of generated form
- **After manual Form.xml editing**: ensure IDs are unique, companions are present, references are valid
- **When debugging**: identify structural errors before building

---

## Typical Workflow

1. `1c-form-manage patterns` — review design patterns
2. `1c-form-manage scaffold` — create/remove form
3. `1c-form-manage compile` — generate Form.xml from JSON
4. `1c-form-manage edit` — add elements to existing form
5. `1c-form-manage info` — analyze form structure
6. `1c-form-manage validate` — check correctness

## Recent Additions (upstream `w-2026-05-17`)

In addition to the form-compile / form-info / form-add / form-edit / form-remove changes already documented in sections 2–5, **`form-validate`** got the following improvements (script `tools/1c-form-validate/scripts/form-validate.ps1`):

- Stops false-flagging real ERP and БП forms — `Items.<Table>.CurrentData.<Field>` and `~<DynamicList>.<Field>` paths are now correctly resolved through the table's data attribute. Missing table → error; third segment ≠ `CurrentData` → warning.
- Opaque platform paths (`"10"`, `"1000003"`, `"N/M: "`) are skipped without an error. Previously Check 5 reported "attribute not found" on these.
- New attribute-type check in `data`: error on intentionally invalid types, warning on unrecognised ones. Context is honoured — `ExternalDataProcessorObject` / `ExternalReportObject` are valid only inside an external data processor / report; in regular configuration object forms it is an error with a hint to use the inner object type.
- Platform 8.5 support — new compatibility / interface mode values and the new XML header format.
- Brief output by default; full per-check trace via `-Detailed`. The `-Path` parameter accepts both a `Form.xml` file and a `Forms/<Name>` folder (auto-resolves to `Forms/<Name>/Ext/Form.xml`).

## MCP Integration

- **get_object_dossier** — Comprehensive structural passport of the metadata object including all its forms, attributes, dependencies, and code in one call. Use as the first step before form design.
- **search_forms** — Find similar existing forms in the configuration by object name, form name, or title. Use as a starting point for new form design.
- **inspect_form_layout** — Get full form structure: element hierarchy with types and data bindings, form attributes, commands, event handlers, visibility, accessibility. Use to study existing forms before creating or modifying.
- **metadatasearch** — Verify metadata object existence and structure before creating forms; verify object types, attribute names, and metadata types when defining attributes. Use `names_only=true` to get compact object lists.
- **get_metadata_details** — Get full attribute types, tabular parts, synonyms for the metadata object the form belongs to.
- **get_xsd_schema** — Get XSD schema for form XML (`object_type="Форма"`). Use before generating or modifying Form.xml to know valid structure.
- **verify_xml** — Validate generated or modified Form.xml against XSD (`object_type="Форма"`). Always validate before committing.
- **templatesearch** — Find real form examples in the codebase, similar form implementations, and patterns when designing forms.

## SDD Integration

When creating or modifying managed forms as part of a feature, update SDD artifacts if present (see `content/rules/sdd-integrations.md` for detection):

- **OpenSpec**: Add spec deltas describing the form purpose, key UI elements, and user scenarios in `openspec/changes/`.
