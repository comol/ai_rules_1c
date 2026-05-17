# Form Patterns — Managed Form Layout Reference

Reference of standard managed form design patterns for 1C. Load **before** designing a form via `1c-form-compile` (see `form-compile-dsl.md`) when user requirements do not specify element placement.

**How to use:** pick a matching archetype, apply naming conventions, use advanced patterns as needed.

> Adapted from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills) (`form-patterns/SKILL.md`, tag `w-2026-05-17`, MIT). Translated to English and aligned with the local dispatcher layout.

---

## Form Archetypes

### Document Form

```
Header (horizontal, 2 columns)
├─ Left  (vertical): NumberDate (H: Number + Date "от"), Counterparty, Contract
├─ Right (vertical): Organization, Department, PricesAndCurrency (hyperlink label)
Pages (pages)
├─ Goods: table Object.Goods
├─ Services: table Object.Services (optional)
└─ Additional: other attributes
Footer (vertical)
├─ Totals (horizontal): Total, VAT, Discount
└─ CommentResponsible (horizontal): Comment + Responsible
```

**Events:** `OnCreateAtServer`, `OnReadAtServer`, `OnOpen`, `BeforeWriteAtServer`, `AfterWriteAtServer`, `AfterWrite`, `NotificationProcessing`
**Properties:** `autoTitle=false`

### Data Processor Form

```
Parameters (vertical)
├─ Input fields group (Organization, Period, modes)
├─ Information labels (label, hyperlink)
Working area
├─ Data table or Pages with tabs
Main form auto command bar (autoCmdBar)
├─ Execute / Apply (defaultButton: true)
└─ Close (stdCommand: Close)
```

**Events:** `OnCreateAtServer`, `OnOpen`, `NotificationProcessing`
**Properties:** `windowOpeningMode=LockOwnerWindow` (when dialog), `autoTitle=false`

### List Form

```
Filters (group: alwaysHorizontal)
├─ FilterGroup[Field] (H): Checkbox + Input field (per filter)
List (table, DynamicList)
├─ Columns: labelField (not input — read-only data)
```

**Events:** `OnCreateAtServer`, `OnOpen`, `NotificationProcessing`, `OnLoadDataFromSettingsAtServer`
**Properties:** `autoSaveDataInSettings=Use`
**Filters:** one pair of attributes per filter — `Filter[Field]` (value) + `Filter[Field]Use` (boolean)

### Catalog Item Form

**Simple:**
```
AttributesGroup (horizontal)
├─ Description -> Object.Description
└─ Code -> Object.Code (when needed)
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

**Events:** `OnCreateAtServer`, `OnReadAtServer`, `BeforeWriteAtServer`, `NotificationProcessing`

### Wizard

```
Pages (pages, OnCurrentPageChange)
├─ Step1: description + parameters
├─ Step2: main work
└─ Step3: result
Main form auto command bar (autoCmdBar)
├─ Back, Next (defaultButton: true), Execute
└─ Close (stdCommand: Close)
```

**Properties:** `windowOpeningMode=LockOwnerWindow`

---

## Naming Conventions

### Groups

| Purpose | Name | Type |
|---------|------|------|
| Header | `HeaderGroup` | horizontal |
| Left column | `HeaderLeftGroup` | vertical |
| Right column | `HeaderRightGroup` | vertical |
| Number+Date | `NumberDateGroup` | horizontal |
| Footer | `FooterGroup` | vertical |
| Totals | `TotalsGroup` | horizontal |
| Main form command bar | `FormCommandBar` | autoCmdBar |
| Pages | `PagesGroup` / `Pages` | pages |
| Warning | `WarningGroup` | horizontal, `visible:false` |
| Additional section | `AdditionalGroup` / `OtherGroup` | vertical, `collapse` |

### Elements

| Purpose | Name |
|---------|------|
| Field in table | `[Table][Field]` |
| Total | `Totals[Field]` |
| Hyperlink label | `[Field]Label` |
| Filter | `Filter[Field]` |
| Filter checkbox | `Filter[Field]Use` |
| Command button | `[Command]Button` |
| Banner picture | `[Banner]Picture` |
| Banner label | `[Banner]Label` |
| Submenu | `Submenu[Action]` |

### Event Handlers

Handler name = element name + Russian suffix (BSL identifiers stay in Russian per project rules):

| Event | Suffix | Example |
|-------|--------|---------|
| OnChange | ПриИзменении | `ОрганизацияПриИзменении` |
| StartChoice | НачалоВыбора | `КонтрагентНачалоВыбора` |
| Click | Нажатие | `ЦеныИВалютаНажатие` |
| OnEditEnd | ПриОкончанииРедактирования | `ТоварыПриОкончанииРедактирования` |
| OnStartEdit | ПриНачалеРедактирования | `ТоварыПриНачалеРедактирования` |

Form-level handlers: `ПриСозданииНаСервере`, `ПриОткрытии`, `ПередЗакрытием`, `ОбработкаОповещения`.

---

## Layout Principles

1. **Reading order.** Top to bottom, left to right. Most important — at the top.
2. **Two-column header.** Business attributes on the left (counterparty, warehouse), organizational ones on the right (organization, department).
3. **Action buttons go on the main form `autoCmdBar`**, not in a separate horizontal group on the form. The main button — `defaultButton: true`. Close — always last.
4. **Tables are the main area.** Tabular sections take the bulk of the form, usually inside `pages`.
5. **Totals next to the table.** In the footer, horizontal group, all fields read-only.
6. **Filters as a separate zone.** Above the list, `alwaysHorizontal`, a "checkbox + field" pair per filter.
7. **Hidden elements for state-driven UI.** Banners, warnings — `visible: false`, shown programmatically.
8. **Hyperlink labels for child dialogs.** `labelField` with `hyperlink: true` and a `Click` event.

---

## Advanced Patterns (ERP-class)

### Collapsible Groups

For optional sections (signatures, additional, other):

```json
{ "group": "collapsible", "name": "SignaturesGroup", "title": "Signatures",
  "collapsed": true, "children": [] }
```

`collapsed: true` means the group is created collapsed; the user can still expand it at runtime.

### Warning Banner

Group "picture + label", hidden by default, shown programmatically:

```json
{ "group": "horizontal", "name": "WarningGroup", "showTitle": false,
  "visible": false, "children": [
    { "picture": "WarningPicture" },
    { "label": "WarningLabel", "title": "Text", "maxWidth": 76, "autoMaxWidth": false }
]}
```

### Popup Menu in the Command Bar

Group related commands (print, send) under one button with an icon:

```json
{ "cmdBar": "CommandBar", "children": [
    { "popup": "SubmenuPrint", "title": "Print",
      "picture": "StdPicture.Print", "representation": "Picture", "children": [
        { "button": "PrintInvoice", "command": "Print" },
        { "button": "PrintReceipt", "command": "PrintReceipt" }
    ]}
]}
```

### Form Without a Standard Command Bar

For modal dialogs and wizards:

```json
{ "properties": { "commandBarLocation": "None", "windowOpeningMode": "LockWholeInterface" } }
```

### Hyperlink Label

Instead of a button, to open child forms (PricesAndCurrency, AccountingPolicy):

```json
{ "labelField": "PricesAndCurrencyLabel", "path": "PricesAndCurrency", "hyperlink": true, "on": ["Click"] }
```

---

## Full DSL Example: Data Processor Form

```json
{
  "title": "CSV Import",
  "properties": { "autoTitle": false, "windowOpeningMode": "LockOwnerWindow" },
  "events": { "OnCreateAtServer": "ПриСозданииНаСервере" },
  "elements": [
    { "group": "vertical", "name": "ParametersGroup", "children": [
      { "input": "ImportFile", "path": "ImportFile", "title": "File", "clearButton": true, "horizontalStretch": true, "on": ["StartChoice"] },
      { "input": "Encoding",   "path": "Encoding" },
      { "input": "Delimiter",  "path": "Delimiter", "title": "Column delimiter" }
    ]},
    { "table": "Data", "path": "Object.Data", "on": ["OnStartEdit"], "columns": [
      { "input": "DataLineNumber", "path": "Object.Data.LineNumber", "readOnly": true, "title": "#" },
      { "input": "DataName",       "path": "Object.Data.Name" },
      { "input": "DataQuantity",   "path": "Object.Data.Quantity", "on": ["OnChange"] },
      { "input": "DataAmount",     "path": "Object.Data.Amount", "readOnly": true }
    ]},
    { "autoCmdBar": "FormCommandBar", "children": [
      { "button": "Import", "command": "Import", "title": "Import from file", "defaultButton": true },
      { "button": "Clear",  "command": "Clear",  "title": "Clear table" },
      { "button": "Close",  "stdCommand": "Close" }
    ]}
  ],
  "attributes": [
    { "name": "Object",      "type": "ExternalDataProcessorObject.CSVImport", "main": true },
    { "name": "ImportFile",  "type": "string" },
    { "name": "Encoding",    "type": "string(20)" },
    { "name": "Delimiter",   "type": "string(5)" }
  ],
  "commands": [
    { "name": "Import", "action": "ЗагрузитьОбработка" },
    { "name": "Clear",  "action": "ОчиститьОбработка" }
  ]
}
```
