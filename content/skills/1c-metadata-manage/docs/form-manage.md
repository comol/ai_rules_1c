# 1C Form Manage — Patterns, Scaffold, Compile, Edit, Info, Validate

Comprehensive managed form management: design patterns reference, create/remove forms, compile from JSON, edit elements, analyze structure, validate correctness.

---

## 1. Patterns — Design Reference

**Canonical layout patterns:** fetch `standards(name="form-patterns")` on `1C-docs-mcp` (server not exposed → `content/rules/help-corpus-retrieval.md`) — project rule, Russian event / element names; nothing from it is duplicated here.

Also load the project forms router `content/rules/forms.md` first for any managed-form task (it selects `forms-add.md`, `form-module.md`, `standards(name="async-methods")`, …).

Fetch it **before** designing a form via `1c-form-compile` when user requirements do not specify element placement (5+ elements or unclear requirements). For simple 1–3 field forms it is not needed.

The canonical rule covers:

- **Archetypes** — Document, Data Processor, List, Catalog Item (Simple/Complex), Wizard.
- **Naming** — group / element / event-handler conventions (`ГруппаШапка`, `Отбор[Поле]` + `Использование`, …).
- **Layout principles** — reading order, two-column header, action buttons on `autoCmdBar`, totals near table, etc.
- **Advanced patterns** — collapsible groups, warning banners, popup menus, hyperlink labels, modal dialogs.

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
| FormName | yes | — | Form name — a 1C identifier (Latin / Cyrillic letters, digits, underscore, not starting with a digit); anything else, including path separators, is refused with exit 2 before any file is written |
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
| Record | InformationRegister | Запись (InformationRegisterRecordManager) | DefaultRecordForm |

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
1c-form-scaffold remove <ObjectName> <FormName> [SrcDir] [-DryRun | -Force]
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| ObjectName (alias `ProcessorName`) | yes | — | Object name (root XML lives at `<SrcDir>/<ObjectName>.xml`) |
| FormName | yes | — | Form name to remove |
| SrcDir | no | `src` | Source directory |
| DryRun | no | off | Print the root XML and files that would change; do not mutate anything |
| Force | required to delete | off | Confirm the reviewed removal plan and perform it |

**Commands (preview first, then execute):**
```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-form-scaffold/scripts/remove-form.ps1 -ObjectName "<ObjectName>" -FormName "<FormName>" [-SrcDir "<SrcDir>"] -DryRun
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-form-scaffold/scripts/remove-form.ps1 -ObjectName "<ObjectName>" -FormName "<FormName>" [-SrcDir "<SrcDir>"] -Force
```

The script refuses a real deletion without `-Force`. It parses and serializes the parent XML before mutating the source tree, then removes the registration before deleting the form files. After execution, run the form / metadata validator required by the main workflow.

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

# Preview, then remove a form (works for both config objects and EPF/ERF)
1c-form-scaffold remove MyProcessor OldForm -DryRun
1c-form-scaffold remove MyProcessor OldForm -Force
```

---

## 3. Compile — Generate from JSON or from Object Metadata

Two modes:

1. **JSON DSL** — generate `Form.xml` from a JSON definition.
2. **From-object** (`-FromObject`) — generate a typical form from an object's metadata (Catalog, Document, InformationRegister, AccumulationRegister, ChartOfCharacteristicTypes, ExchangePlan, ChartOfAccounts) using the active preset (default `erp-standard`).

> **Designing a form from scratch (5+ elements or unclear requirements)** — first fetch `standards(name="form-patterns")` on `1C-docs-mcp` (server not exposed → `content/rules/help-corpus-retrieval.md`). For simple forms (1–3 fields) it is not needed.

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

### JSON DSL — reference

The DSL — top-level structure, element keys, common properties, event names, per-element keys, attributes, commands, type system, bindings, patterns, from-object mode, presets, multilingual strings, auto-generation, EPF notes — is described **only** in [`form-compile-dsl.md`](form-compile-dsl.md); read it before writing the JSON, nothing is summarised here.

Only when `form-compile` reports an unknown key or rejects a construct — open the matching section of `tools/1c-form-compile/form-dsl-spec.md` (Russian upstream original: `## 4. Elements`, `## 5. Attributes`, `## 8. Система типов`, …), never the whole 126 KB file.

### Verification

`1c-form-validate <OutputPath>` (section 6) and `1c-form-info <OutputPath>` (section 5); MCP evidence set per `content/rules/tooling-playbooks.md`: `get_xsd_schema` / `verify_xml` with `object_type="Форма"`.

---

## 4. Edit — Add Elements, Attributes, Commands

Adds elements, attributes, and/or commands to an existing Form.xml. Automatically allocates IDs from the correct pool, generates companion elements (ContextMenu, ExtendedTooltip, etc.) and event handlers.

Saving uses Configurator-style compact empty tags (`<Tag/>`) and retains the existing CRLF or LF line endings. Literal text in CDATA, comments and processing instructions is excluded from empty-tag normalization.

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
    { "name": "TotalAmount", "type": "decimal(15,2)" },
    { "name": "LowerList", "type": "DynamicList", "settings": { "mainTable": "Catalog.Products" } }
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

#### Element keys, events, types

Same DSL as `1c-form-compile` — element keys, `command` / `stdCommand`, event names and attribute types are in [`form-compile-dsl.md`](form-compile-dsl.md); the companion elements each type receives (ContextMenu, ExtendedTooltip, AutoCommandBar, …) are listed in its *Auto-generation* section. Groups and tables support `children` / `columns` for nested elements.

A `DynamicList` attribute **must** carry `settings.mainTable` and/or `settings.query`. Without a source the designer accepts the XML, but the form fails to open (`Основная таблица динамического списка задана неверно`). `form-edit` refuses that JSON before writing; `form-validate` reports the same gap on an existing form. The `settings` keys are the ones in [`form-compile-dsl.md`](form-compile-dsl.md) (`mainTable`, `query`, `manualQuery`, `dynamicDataRead`). `form-edit` emits those four; filters / order / conditional appearance stay with `form-compile`.

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
| 1 | Root element `<Form>`; `version` equals `Configuration.xml` when one is found above the form (else 2.17 / 2.20 expected) | ERROR / WARN |
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
| 12 | Type values — known namespaces and `cfg:` prefixes; `cfg:Catalogs.X` (export folder name) is an error | ERROR / WARN |
| 12b | A default / auxiliary object, folder or record form of a catalog, document, chart, exchange plan, business process, task or information register has a main attribute of its owner's own type (`<Kind>Object.<Name>`, `InformationRegisterRecordManager.<Name>`); no `Description` / `Code` binding when the owner's length is 0 | ERROR |
| 13 | Handlers in `Ext/Form/Module.bsl` — every event handler and command `Action` declared exactly once (duplicate = error); missing handler, missing directive, wrong context (`*AtServer` event on a client procedure, client event or command on a server one), more mandatory parameters than the platform passes — warnings | ERROR / WARN |
| 14 | `РеквизитФормыВЗначение` / `ЗначениеВРеквизитФормы` only in `&НаСервере` (a procedure without a directive is server-side) | ERROR |

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

Scripts vendored from Nikolay-Shirokov/cc-1c-skills; sync history — `docs/CHANGELOG.md`.
