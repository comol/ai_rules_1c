# Form Compile — DSL Reference

Detailed reference for the JSON DSL accepted by `1c-form-compile` (PowerShell script `tools/1c-form-compile/scripts/form-compile.ps1`). Companion of the brief Compile section in `form-manage.md`.

> Translated from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills) `form-compile/SKILL.md` (MIT). Paths and command examples adapted to the local dispatcher layout.
>
> **This file is the working subset** and the only place in the skill where the DSL is described (`form-manage.md` points here). The **complete, authoritative grammar** — every key, every element type, dynamic-list settings, conditional appearance, groupings, calculated fields — is vendored verbatim as [form-dsl-spec.md](../tools/1c-form-compile/form-dsl-spec.md) (Russian, upstream original, 126 KB). Open it **only when `form-compile` reports an unknown key or rejects a construct**, and only the matching section (`## 4. Elements`, `## 5. Attributes`, `## 8. Система типов`, …) — never the whole file.

`1c-form-compile` has two modes:

1. **JSON DSL** — generate Form.xml from a JSON definition.
2. **From object** (`-FromObject`) — generate a typical form from an object's metadata using the ERP preset.

> When designing a form from scratch (5+ elements or unclear requirements) — first fetch `standards(name="form-patterns")` on `1C-docs-mcp` (server not exposed → `content/rules/help-corpus-retrieval.md`). For simple forms (1–3 fields) it is not needed.

## Parameters

| Parameter   | Required | Description |
|-------------|:--------:|---|
| `JsonPath`  | mode 1   | Path to the JSON form definition |
| `OutputPath`| yes      | Path to the output `Form.xml` |
| `FromObject`| mode 2   | Switch (no value) — generate from object metadata |
| `Preset`    | no       | Preset name (default `erp-standard`); see "Presets" below |

## Command

```powershell
# Mode 1 — JSON DSL
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-form-compile/scripts/form-compile.ps1 -JsonPath "<json>" -OutputPath "<Form.xml>"

# Mode 2 — from-object (object name and purpose are derived from OutputPath; supports Catalog, Document, InformationRegister, AccumulationRegister, ChartOfCharacteristicTypes, ExchangePlan, ChartOfAccounts)
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-form-compile/scripts/form-compile.ps1 -FromObject -OutputPath "<.../TypePlural/ObjectName/Forms/FormName/Ext/Form.xml>"
```

## JSON DSL — Reference

### Top-Level Structure

```json
{
  "title": "Form title",
  "properties": { "autoTitle": false },
  "events": { "OnCreateAtServer": "ПриСозданииНаСервере" },
  "excludedCommands": ["Reread"],
  "elements": [],
  "attributes": [],
  "commands": [],
  "parameters": []
}
```

- `title` — form title (multilingual: string or `{ "ru": "...", "en": "..." }`). Can also live inside `properties`, but top-level is preferred.
- `properties` — form properties: `autoTitle`, `windowOpeningMode`, `commandBarLocation`, `saveDataInSettings`, `width`, `height`, etc.
- `events` — form event handlers (key: 1C event name, value: procedure name).
- `excludedCommands` — excluded standard commands.

**Key case.** In PowerShell every DSL key is case-insensitive (`"Name"` = `"name"`); the Python port matches that since upstream 57b0f95b (keys of the JSON input, presets and nested objects). Event names and enum **values** are a different matter — see below.

**Enum values** (`horizontalAlign`, `selectionMode`, `representation`, `windowOpeningMode`, `autoTime`, `usePostingMode`, `titleLocation`, …) are checked against the platform XSD per element type and written in the platform spelling: case is fixed silently (`right` → `Right`), known synonyms are mapped (`selectionMode: "single"` → `SingleRow`; a button's `TextPicture` → `PictureAndText`, a command's `PictureAndText` → `TextPicture`), an unknown value is a refusal (exit 1, nothing written). A value equal to the platform default is not written, as the Configurator does not write it. Element and command children are emitted in the platform's own order (e.g. a button: `Representation`, `DefaultButton`, `CommandName`, `Picture`, `Title`; a command: `Title`, `Shortcut`, `Picture`, `Action`, `Representation`) — another order is refused by the loader with an XDTO exception.

### Elements (key picks the type)

| DSL key        | XML element        | Key value |
|----------------|--------------------|-----------|
| `"group"`      | UsualGroup         | `"horizontal"` / `"vertical"` / `"alwaysHorizontal"` / `"alwaysVertical"` / `"collapsible"` |
| `"columnGroup"`| ColumnGroup        | `"horizontal"` / `"vertical"` / `"inCell"` — only inside a table's `columns` |
| `"input"`      | InputField         | element name |
| `"check"`      | CheckBoxField      | name |
| `"radio"`      | RadioButtonField   | name |
| `"label"`      | LabelDecoration    | name (text via `title`) |
| `"labelField"` | LabelField         | name |
| `"table"`      | Table              | name |
| `"pages"`      | Pages              | name |
| `"page"`       | Page               | name |
| `"button"`     | Button             | name |
| `"picture"`    | PictureDecoration  | name |
| `"picField"`   | PictureField       | name |
| `"calendar"`   | CalendarField      | name |
| `"cmdBar"`     | CommandBar         | name |
| `"autoCmdBar"` | Form AutoCommandBar | name — fills the main form auto command bar (id=-1), does not appear in `<ChildItems>` |
| `"popup"`      | Popup              | name |

### Common Properties (any element type)

| Key | Description |
|-----|-------------|
| `name` | Override the name (default = the type-key value) |
| `title` | Element title |
| `visible: false` | Hide (synonym: `hidden: true`) |
| `enabled: false` | Disable (synonym: `disabled: true`) |
| `readOnly: true` | Read-only |
| `events: {...}` | **Canonical.** Event → handler name: `{ "OnChange": "MyHandler" }`; `null` / `""` = auto-name. In an extension form the value may be `{ "handler": …, "callType": "Before" \| "After" \| "Override" }` or a list of them |
| `on: [...]` | Legacy. Events with auto-named handlers — accepted, equivalent to `events` with `null` values |
| `handlers: {...}` | Legacy. Explicit handler names: `{ "OnChange": "MyHandler" }`; works **with or without** `on` |

### Event formats — one contract, no silent winner

All three spellings below produce exactly the same `<Events>` block; `events` is the canonical one and the only one new forms should use:

```jsonc
{ "events":   { "OnActivateRow": "ТАктивизация" } }               // canonical
{ "on": ["OnActivateRow"], "handlers": { "OnActivateRow": "ТАктивизация" } }  // legacy pair
{ "handlers": { "OnActivateRow": "ТАктивизация" } }               // legacy, standalone
{ "on": ["OnActivateRow"] }                                       // auto-named handler
```

Refusals (exit `1`, nothing written) — the compiler never picks one format and drops the other:

- `events` together with `on` and/or `handlers` on the same element;
- a key in `handlers` that is not listed in `on` (that is the typo that used to make a handler disappear);
- an event name that no element of the platform has (not in the event catalog at all — `OnEndEdit` instead of `OnEditEnd`, the obsolete `Drop`). This refusal is local; upstream only warns.

### Event names — the event catalog

Events are checked against the event catalog upstream generated from the vendor configurations (BP, ERP, UNF, UT — 28.5k forms) and from load tests on 8.3.24 / 8.3.27 / 8.5. Names are case-sensitive. Beyond the refusal above, `form-compile` writes the event and prints a `[WARN]` when the event exists in the catalog but not for this element (the platform drops it on load), when it appears only in a later platform than the form's format (`OnHover`, `OnSelectedRowsSetChange` of a table and `Click` of a usual group — 8.5 only), or when it exists only for a table bound to a dynamic list (`OnGetDataAtServer`, `URLGetProcessing`, the user-settings events). Elements without events (button, page, column group, command bar, popup) get a `[WARN]` for any event given.

**Form** (`events`): `OnCreateAtServer`, `OnOpen`, `BeforeClose`, `OnClose`, `NotificationProcessing`, `ChoiceProcessing`, `OnReadAtServer`, `BeforeWriteAtServer`, `OnWriteAtServer`, `AfterWriteAtServer`, `BeforeWrite`, `AfterWrite`, `FillCheckProcessingAtServer`, `BeforeLoadDataFromSettingsAtServer`, `OnLoadDataFromSettingsAtServer`, `OnSaveDataInSettingsAtServer`, `URLProcessing`, `ExternalEvent`, `OnReopen`, `NewWriteProcessing`, `NavigationProcessing`, and the report / settings `…AtServer` events. A form event outside the catalog needs an explicit handler name.

**input**: `OnChange`, `StartChoice`, `StartListChoice`, `ChoiceProcessing`, `AutoComplete`, `TextEditEnd`, `Clearing`, `Opening`, `Creating`, `EditTextChange`, `Tuning`, `MultipleValueOpening`, `MultipleValueURLProcessing`, `MultipleValuesAdd`, `MultipleValuesDelete`.

**check / radio**: `OnChange`.

**table**: `Selection`, `OnActivateRow`, `OnActivateCell`, `OnActivateField`, `BeforeAddRow`, `BeforeDeleteRow`, `AfterDeleteRow`, `BeforeRowChange`, `OnStartEdit`, `OnEditEnd`, `BeforeEditEnd`, `OnChange`, `ChoiceProcessing`, `ValueChoice`, `BeforeExpand`, `BeforeCollapse`, `Drag`, `DragStart`, `DragCheck`, `DragEnd`, `OnCurrentParentChange`, `RefreshRequestProcessing`, `NewWriteProcessing`; dynamic-list tables only: `OnGetDataAtServer`, `URLGetProcessing`, `BeforeLoadUserSettingsAtServer`, `OnLoadUserSettingsAtServer`, `OnSaveUserSettingsAtServer`, `OnUpdateUserSettingSetAtServer`.

**label**: `Click`, `URLProcessing`. **labelField**: `Click`, `URLProcessing`, `OnChange`.

**picture**: `Click`, `Drag`, `DragCheck`. **picField**: `Click`, `OnChange`, `Drag`, `DragCheck`.

**calendar**: `OnChange`, `Selection`, `OnActivateDate`, `OnPeriodOutput`. **pages**: `OnCurrentPageChange`.

Spreadsheet, HTML, formatted / text document, chart, Gantt, planner, graphical schema and track-bar fields have their own sets — `form-dsl-spec.md` § 4.2.

### Handler auto-names

`null` / `""` / `on` without a name produce `<ElementName><Suffix>`; a form event gets the suffix alone (`ПриСозданииНаСервере`). The suffix comes from the catalog — it follows the vendor-configuration convention and depends on the element kind; an event without a convention gets `<ElementName><EventName>`. PowerShell and Python use the same table.

| Element | Event → suffix |
|---------|----------------|
| input | `OnChange` → `ПриИзменении`, `StartChoice` → `НачалоВыбора`, `StartListChoice` → `НачалоВыбораИзСписка`, `ChoiceProcessing` → `ОбработкаВыбора`, `Clearing` → `Очистка`, `AutoComplete` → `АвтоПодбор`, `TextEditEnd` → `ОкончаниеВводаТекста`, `Opening` → `Открытие`, `Tuning` → `Регулирование`, `Creating` → `Создание`, `EditTextChange` → `ИзменениеТекстаРедактирования` |
| table | `Selection` → `Выбор`, `OnActivateRow` → `ПриАктивизацииСтроки`, `BeforeAddRow` → `ПередНачаломДобавления`, `BeforeDeleteRow` → `ПередУдалением`, `AfterDeleteRow` → `ПослеУдаления`, `BeforeRowChange` → `ПередНачаломИзменения`, `OnStartEdit` → `ПриНачалеРедактирования`, `OnEditEnd` → `ПриОкончанииРедактирования`, `BeforeEditEnd` → `ПередОкончаниемРедактирования`, `OnChange` → `ПриИзменении`, `DragStart` → `НачалоПеретаскивания`, `DragCheck` → `ПроверкаПеретаскивания`, `Drag` → `Перетаскивание`, `DragEnd` → `ОкончаниеПеретаскивания`, `ValueChoice` → `ВыборЗначения` |
| label, picture, labelField | `Click` → `Нажатие`, `URLProcessing` → `ОбработкаНавигационнойСсылки` |
| pages | `OnCurrentPageChange` → `ПриСменеСтраницы` |
| calendar | `Selection` → `Выбор`, `OnActivateDate` → `ПриАктивизацииДаты` |

In an extension form (`<BaseForm>`) a handler with a `callType` is named `<NamePrefix><Element><Suffix><Перед|После|Вместо>` (the prefix is the extension's `NamePrefix`), so it never matches the base form's procedure.

### Input Field

| Key | Description | Example |
|-----|-------------|---------|
| `path` | DataPath — data binding | `"Object.Organization"` |
| `titleLocation` | Title location | `"none"`, `"left"`, `"top"` |
| `multiLine: true` | Multi-line field | text field, comment |
| `passwordMode: true` | Password mode (asterisks) | password |
| `choiceButton: true` | Choice button ("...") | reference field |
| `clearButton: true` | Clear button ("X") | |
| `spinButton: true` | Spin button | numeric fields |
| `dropListButton: true` | Drop-down button | |
| `markIncomplete: true` | Mark as incomplete | required field |
| `skipOnInput: true` | Skip on Tab traversal | |
| `inputHint` | Empty-state hint | `"Enter name…"` |
| `width` / `height` | Size | numbers |
| `autoMaxWidth: false` | Disable auto-width (field stretches) | |
| `maxWidth` / `maxHeight` | Hard size cap | numbers; usually paired with `autoMaxWidth: false` |
| `horizontalStretch: true` | Stretch horizontally | |
| `textEdit: false` | Disable free text editing — leaves only choice from a list | reference fields used as picklists |
| `autoEditMode: true` / `false` | `<AutoEditMode>` (local; format 2.21 / 8.5 only — refused in an older form). JSON boolean only — `"true"` or `1` is refused. Written at its XSD place: after the field properties, before `Width`. PowerShell runtime only (`form-compile.py` does not know it yet) | |

### Checkbox

| Key | Description |
|-----|-------------|
| `path` | DataPath |
| `titleLocation` | Title location |

### Radio Button Field

Radio buttons or a tumbler for picking one of N values.

| Key | Description | Example |
|-----|-------------|---------|
| `path` | DataPath — bound attribute | `"ExchangeRateMode"` |
| `radioButtonType` | Visual kind | `"Auto"` (default), `"RadioButtons"`, `"Tumbler"` |
| `columnsCount` | Number of layout columns | `1`, `2`, … |
| `titleLocation` | Title location | default `"none"` |
| `choiceList` | Variants: array of `{value, presentation}` | see below |

`choiceList[*]`:

| Key | Description |
|-----|-------------|
| `value` | Variant value. String / number / boolean; for an enum — `"Enum.TypeName.EnumValue.ItemName"` |
| `presentation` | Text next to the radio button. String (Russian) or object `{ru, en, …}` for multilingual |

```json
{
  "radio": "ExchangeRateMode",
  "path": "Object.ExchangeRateMode",
  "radioButtonType": "Auto",
  "choiceList": [
    { "value": "Enum.ExchangeRateModes.EnumValue.Auto",   "presentation": { "ru": "Автоматически", "en": "Automatic" } },
    { "value": "Enum.ExchangeRateModes.EnumValue.Manual", "presentation": "manual" }
  ]
}
```

### Label Decoration

| Key | Description |
|-----|-------------|
| `title` | Label text (required) |
| `hyperlink: true` | Make it a hyperlink |
| `width` / `height` | Size |

### Group

The key value sets the orientation: `"horizontal"`, `"vertical"`, `"alwaysHorizontal"`, `"alwaysVertical"`, `"collapsible"`.

| Key | Description |
|-----|-------------|
| `showTitle` | Without the key a usual group shows its title only when `title` or `titleDataPath` is given, otherwise the title is hidden (`<ShowTitle>false`, as in 92 % of vendor usual groups) — upstream af28bbb8 / 36ae6195 / 5f9490b2 changed this default; a collapsible group keeps the platform default (shown). `showTitle: true` / `false` overrides |
| `united: false` | Left edge of input fields aligns only inside this group (default `true` — alignment runs through neighbouring groups by the longest title) |
| `collapsed: true` | Only for `"group": "collapsible"` — start collapsed |
| `representation` | `"none"`, `"normal"`, `"weak"`, `"strong"` |
| `children: [...]` | Nested elements |

### Table

**Important:** a table needs a backing form attribute of type `ValueTable` with columns (see "Bindings").

| Key | Description |
|-----|-------------|
| `path` | DataPath (binds to the table attribute) |
| `columns: [...]` | Columns — array of elements (usually `input`) |
| `changeRowSet: true` | Allow add/remove rows |
| `changeRowOrder: true` | Allow row reorder |
| `height` | Height in rows |
| `header: false` | Hide the header |
| `footer: true` | Show the footer |
| `commandBarLocation` | `"None"`, `"Top"`, `"Auto"` |
| `searchStringLocation` | `"None"`, `"Top"`, `"Auto"` |
| `choiceMode: true` | Choice mode (for choice forms) |
| `initialTreeView` | `"ExpandTopLevel"` etc. (hierarchical lists) |
| `enableDrag: true` | Allow drag |
| `enableStartDrag: true` | Allow start of drag |
| `rowPictureDataPath` | Path to the row picture (e.g. `"List.DefaultPicture"`) |
| `tableAutofill: false` | Control autofill of the inner AutoCommandBar |

Columns can be grouped via `columnGroup` (see below).

### Column Group

Used only inside a table's `columns`. The key value sets orientation: `"horizontal"`, `"vertical"`, `"inCell"` (merges columns into a single header cell). `columnGroup` may be nested.

| Key | Description |
|-----|-------------|
| `name` | Element name (recommended explicit) |
| `title` | Group title |
| `showTitle: false` | Hide the group title |
| `showInHeader: true/false` | Show/hide the group in the table header |
| `width` | Width |
| `horizontalStretch: false` | Stretch toggle |
| `children: [...]` | Columns (`input`, `labelField`, `picField`, nested `columnGroup`, …) |

```json
{ "table": "List", "path": "List", "columns": [
    { "columnGroup": "horizontal", "name": "DueGroup", "title": "Due", "children": [
        { "input": "DueDate",   "path": "List.DueDate" },
        { "labelField": "Late", "path": "List.Late" }
    ]},
    { "columnGroup": "inCell", "name": "ExecutorGroup", "showInHeader": true, "children": [
        { "input": "Executor", "path": "List.Executor" }
    ]},
    { "input": "Comment", "path": "List.Comment" }
]}
```

### Pages (pages + page)

| Key (pages) | Description |
|-------------|-------------|
| `pagesRepresentation` | `"None"`, `"TabsOnTop"`, `"TabsOnBottom"`, … |
| `children: [...]` | Array of `page` |

| Key (page) | Description |
|------------|-------------|
| `title` | Tab title |
| `group` | Orientation inside the page |
| `children: [...]` | Page content |

### Button

| Key | Description |
|-----|-------------|
| `command` | Form command name → `Form.Command.Name` |
| `stdCommand` | Standard command: `"Close"` → `Form.StandardCommand.Close`; with a dot: `"Goods.Add"` → `Form.Item.Goods.StandardCommand.Add` |
| `defaultButton: true` | Default button |
| `type` | `"usual"`, `"hyperlink"`, `"commandBar"`. Default `"usual"`. The exact XML kind (UsualButton/Hyperlink/CommandBarButton/CommandBarHyperlink) is picked from context |
| `picture` | Button picture |
| `representation` | `"Auto"`, `"Text"`, `"Picture"`, `"PictureAndText"` |
| `locationInCommandBar` | `"Auto"`, `"InCommandBar"`, `"InAdditionalSubmenu"` |

### Command Bar (`cmdBar`)

A custom command bar, placed inside the form layout as a normal element.

| Key | Description |
|-----|-------------|
| `autofill: true` | Auto-fill with standard commands |
| `children: [...]` | Bar buttons |

### Main Form Auto Command Bar (`autoCmdBar`)

Fills the form's built-in AutoCommandBar (id=-1) with custom buttons. Specify only if you need to add custom buttons to the main bar or explicitly control autofill.

| Key | Description |
|-----|-------------|
| `autofill: true/false` | Auto-fill with standard commands |
| `horizontalAlign` | `"Left"` / `"Center"` / `"Right"` |
| `children: [...]` | Buttons / popup |

```json
{ "autoCmdBar": "FormCommandBar", "autofill": true, "children": [
   { "button": "ChangeSelected", "command": "ChangeSelected",
     "locationInCommandBar": "InAdditionalSubmenu" }
]}
```

Place primary action buttons and submenus here, not in a separate horizontal group on the form. Buttons in the form layout itself are reserved for cases where they are logically tied to a specific field or group.

### Popup Menu

| Key | Description |
|-----|-------------|
| `title` | Submenu title |
| `children: [...]` | Submenu buttons |

Used inside `cmdBar` to group buttons:
```json
{ "cmdBar": "Panel", "children": [
  { "popup": "Add", "title": "Add", "children": [
    { "button": "AddRow",          "stdCommand": "Goods.Add" },
    { "button": "AddFromDocument", "command": "AddFromDocument", "title": "From document" }
  ]}
]}
```

### Attributes

```json
{ "name": "Object", "type": "DataProcessorObject.Import", "main": true }
{ "name": "List",   "type": "DynamicList", "main": true, "settings": {
    "mainTable": "Catalog.Products", "dynamicDataRead": true
}}
{ "name": "Total",  "type": "decimal(15,2)" }
{ "name": "Table",  "type": "ValueTable", "columns": [
    { "name": "Product",  "type": "CatalogRef.Products" },
    { "name": "Quantity", "type": "decimal(10,3)" }
]}
```

- `savedData: true` — saved data.
- `main: true` — the form's main attribute (e.g. the primary `*Object.*`, `DynamicList`, `*RecordSet.*`).

### Commands

```json
{ "name": "Import", "action": "ЗагрузитьОбработка", "shortcut": "Ctrl+Enter" }
```

- `title` — title (when different from `name`).
- `picture` — command picture.

### Type System

**Primitives:**

| DSL | XML |
|-----|-----|
| `"string"` / `"string(100)"` | `xs:string` + StringQualifiers |
| `"decimal(15,2)"` | `xs:decimal` + NumberQualifiers |
| `"decimal(10,0,nonneg)"` | with `AllowedSign=Nonnegative` |
| `"boolean"` | `xs:boolean` |
| `"date"` / `"dateTime"` / `"time"` | `xs:dateTime` + DateFractions |

**Reference and object types (`cfg:Prefix.Name`):**

| DSL | Description |
|-----|-------------|
| `"CatalogRef.XXX"` / `"CatalogObject.XXX"` | Catalog |
| `"DocumentRef.XXX"` / `"DocumentObject.XXX"` | Document |
| `"EnumRef.XXX"` | Enum |
| `"DataProcessorObject.XXX"` / `"ReportObject.XXX"` | Data processor / Report |
| `"InformationRegisterRecordSet.XXX"` | Information register record set |
| `"AccumulationRegisterRecordSet.XXX"` | Accumulation register record set |
| `"DynamicList"` | Dynamic list |

Also allowed: `ChartOfAccountsRef/Object`, `ChartOfCharacteristicTypesRef/Object`, `ChartOfCalculationTypesRef/Object`, `ExchangePlanRef/Object`, `BusinessProcessRef/Object`, `TaskRef/Object`, `AccountingRegisterRecordSet`, `InformationRegisterRecordManager`, `ConstantsSet`.

**Platform types:**

| DSL | XML |
|-----|-----|
| `"ValueTable"` | `v8:ValueTable` |
| `"ValueTree"` | `v8:ValueTree` |
| `"ValueList"` | `v8:ValueListType` |
| `"TypeDescription"` | `v8:TypeDescription` |
| `"UUID"` | `v8:UUID` |
| `"FormattedString"` | `v8ui:FormattedString` |
| `"Picture"` / `"Color"` / `"Font"` | `v8ui:*` |
| `"DataCompositionSettings"` | `dcsset:DataCompositionSettings` |
| `"Type1 \| Type2"` | composite type (multiple `<v8:Type>`) |

**Forbidden types (XDTO error on load):**

> `FormDataStructure`, `FormDataCollection`, `FormDataTree` — runtime types, do not exist in the XML schema. Use `CatalogObject.XXX`, `DocumentObject.XXX`, `DataProcessorObject.XXX`, `ValueTable`, `ValueTree` instead.

## Bindings: Element + Attribute

A table and some fields require an associated attribute. The element refers to the attribute via `path`.

**Table** — a `table` element + a `ValueTable` attribute:
```json
{
  "elements": [
    { "table": "Goods", "path": "Object.Goods", "columns": [
      { "input": "Product", "path": "Object.Goods.Product" }
    ]}
  ],
  "attributes": [
    { "name": "Object", "type": "DataProcessorObject.Import", "main": true,
      "columns": [
        { "name": "Goods", "type": "ValueTable", "columns": [
          { "name": "Product", "type": "CatalogRef.Products" }
        ]}
      ]
    }
  ]
}
```

Or, when the table is bound to a form attribute (not `Object`):
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

## Patterns

### File Import Dialog

```json
{
  "title": "Import from file",
  "properties": { "autoTitle": false },
  "events": { "OnCreateAtServer": "ПриСозданииНаСервере" },
  "elements": [
    { "group": "horizontal", "name": "FileGroup", "children": [
      { "input": "FileName",         "path": "FileName", "title": "File", "inputHint": "Pick a file…", "choiceButton": true, "on": ["StartChoice"] },
      { "check": "FirstRowIsHeader", "path": "FirstRowIsHeader" }
    ]},
    { "input": "Result", "path": "Result", "multiLine": true, "height": 8, "readOnly": true, "title": "Log" },
    { "autoCmdBar": "FormCommandBar", "children": [
      { "button": "Import", "command": "Import", "defaultButton": true },
      { "button": "Close",  "stdCommand": "Close" }
    ]}
  ],
  "attributes": [
    { "name": "Object",            "type": "ExternalDataProcessorObject.FileImport", "main": true },
    { "name": "FileName",          "type": "string" },
    { "name": "FirstRowIsHeader",  "type": "boolean" },
    { "name": "Result",            "type": "string" }
  ],
  "commands": [
    { "name": "Import", "action": "ЗагрузитьОбработка", "shortcut": "Ctrl+Enter" }
  ]
}
```

### Wizard with Steps

```json
{
  "title": "Setup wizard",
  "properties": { "autoTitle": false },
  "elements": [
    { "pages": "WizardPages", "pagesRepresentation": "None", "children": [
      { "page": "Step1", "title": "Parameters", "children": [
        { "input": "Param1", "path": "Param1" }
      ]},
      { "page": "Step2", "title": "Result", "children": [
        { "input": "Outcome", "path": "Outcome", "readOnly": true }
      ]}
    ]},
    { "autoCmdBar": "FormCommandBar", "children": [
      { "button": "Back", "command": "Back",  "title": "< Back" },
      { "button": "Next", "command": "Next",  "title": "Next >", "defaultButton": true }
    ]}
  ],
  "attributes": [
    { "name": "Object",  "type": "ExternalDataProcessorObject.Wizard", "main": true },
    { "name": "Param1",  "type": "string" },
    { "name": "Outcome", "type": "string" }
  ],
  "commands": [
    { "name": "Back", "action": "НазадОбработка" },
    { "name": "Next", "action": "ДалееОбработка" }
  ]
}
```

### List With Filter and Table

```json
{
  "title": "Data viewer",
  "elements": [
    { "group": "horizontal", "name": "Filter", "children": [
      { "input": "Period",       "path": "Period",       "on": ["OnChange"] },
      { "input": "Organization", "path": "Organization", "on": ["OnChange"] }
    ]},
    { "table": "Data", "path": "Data", "changeRowSet": true, "columns": [
      { "input": "Date",    "path": "Data.Date" },
      { "input": "Amount",  "path": "Data.Amount" },
      { "input": "Comment", "path": "Data.Comment" }
    ]}
  ],
  "attributes": [
    { "name": "Object",       "type": "ExternalDataProcessorObject.Viewer", "main": true },
    { "name": "Period",       "type": "date" },
    { "name": "Organization", "type": "string" },
    { "name": "Data",         "type": "ValueTable", "columns": [
      { "name": "Date",    "type": "date" },
      { "name": "Amount",  "type": "decimal(15,2)" },
      { "name": "Comment", "type": "string(200)" }
    ]}
  ]
}
```

## From-Object Mode

`-FromObject` reads the object's XML, applies the active preset and emits a typical form for that object kind.

**Supported assignments** (purpose is detected from `OutputPath`):

- `Object` — item form (Catalog, Document, ChartOfCharacteristicTypes, ExchangePlan, ChartOfAccounts).
- `List` — list form (Catalog, Document, InformationRegister, AccumulationRegister, ChartOfCharacteristicTypes, ExchangePlan, ChartOfAccounts).
- `Choice` — choice form.
- `Folder` — group/folder form for catalogs.
- `Record` — record form for InformationRegister.

Special handling baked in:

- Document list forms automatically include the standard `Number` and `Date` columns.
- The reference column in list forms is hidden via `UserVisible=false` (the user can re-enable it and expand sub-columns through dotted notation).
- ChartOfAccounts forms pull accounting-flag and sub-account-kind names into the form correctly.

## Presets

Forms generated via `-FromObject` follow the `erp-standard` preset by default (`tools/1c-form-compile/presets/erp-standard.json` — same level as `scripts/`). Override at project level by placing your own preset at `<projectRoot>/presets/skills/form/<name>.json`.

The preset controls default attributes for input fields, list columns, and standard buttons. Detailed keys are in `tools/1c-form-compile/presets/README.md`.

## Multilingual Strings

Any title/presentation may be either a string or an object:

```json
{ "title": { "ru": "Сумма документа", "en": "Document amount" } }
```

This works for: form `title`, element `title`, group titles, button titles, `radio` `choiceList[*].presentation`, etc.

## Auto-generation

- **Companion elements** — emitted automatically per element type, by `form-compile` and `form-edit` alike (`form-validate` check 6 expects them): `input` / `check` / `label` / `labelField` → `ContextMenu` + `ExtendedTooltip`; `group` / `pages` / `page` / `button` → `ExtendedTooltip`; `table` → `ContextMenu`, `AutoCommandBar`, `Search*`, `ViewStatus*`.
- **Defaults aligned with real ERP/БП forms** — multi-line inputs are not auto-width-bounded by default; checkbox title is on the right; `autoTitle` is suppressed when `title` is set; objects with editable state save the input state (`Esc → confirm`).
- **Event handlers** — `"on": ["OnChange"]` → `ОрганизацияПриИзменении` (suffix table above).
- **Handler stubs** — every bound handler / command action missing from `<Form.xml dir>/Form/Module.bsl` is appended there as an empty procedure with the catalog directive and parameters, in the standard BSP region; existing procedures are never changed. No switch turns it off — see `form-manage.md` §3.
- **Namespaces** — all 17 namespace declarations.
- **IDs** — sequential numbering, AutoCommandBar = id="-1".
- **Format version** — from the nearest `Configuration.xml` (or the external processor's own root); without one a `[WARN]` names the assumed 2.17 (local).
- **Auto-titles** — attributes, commands, pages, popups and decorations without an explicit `title` get a title derived from the name (e.g. `НомерСчёта` → "Номер счёта").
- **Unknown keys** — a warning is printed for unrecognized keys.

## Workflow

1. **Compile** — `1c-form-compile` generates `Form.xml`, appends handler stubs to `Module.bsl` and registers `<Form>` in the parent object's top-level `ChildObjects` (when `OutputPath` follows the `.../TypePlural/ObjectName/Forms/FormName/Ext/Form.xml` convention; the Python port no longer inserts into a tabular section's nested block — upstream 11602f8b).
2. **Form metadata** (`<FormName>.xml`) and `Module.bsl` are created by `1c-form-add` (skill `form-manage.md` §2). Run `1c-form-add` first or after compile if metadata is missing — it will not overwrite an existing `Form.xml`.
3. **Verify** — `1c-form-validate` and `1c-form-info` (sections 5–6 in `form-manage.md`).

## EPF Notes (External Data Processors)

- **Main attribute type**: `ExternalDataProcessorObject.<ProcessorName>` (not `DataProcessorObject`).
- **DataPath**: use form attributes (`AttributeName`), not `Object.AttributeName` — external processors have no object attributes in metadata.
- **Reference types**: `CatalogRef.XXX`, `DocumentRef.XXX` are valid in XML, but to build the EPF you need a base configuration with the matching types (see EPF docs).
