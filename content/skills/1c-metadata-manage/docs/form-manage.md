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
| Purpose | no | primary form of the kind | Purpose — see the table below. Empty = the kind's primary form: object form of a catalog / document, record form of an information register, list form of a journal or an accumulation register |
| Synonym | no | = FormName | Form synonym |
| --set-default | no | auto | Set as default form (auto for the first form of that purpose) |

**Command:**
```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-form-scaffold/scripts/form-add.ps1 -ObjectPath "<ObjectPath>" -FormName "<FormName>" [-Purpose "<Purpose>"] [-Synonym "<Synonym>"] [-SetDefault]
```

The format version of `Form.xml` comes from the object's own root XML (or the nearest `Configuration.xml` / external-processor root); `xmlns:dcssch` in the form header follows the configuration's compatibility mode (declared always from 8.3.19, otherwise only when used).

#### Purpose — Form Assignment

| Purpose | Form | Default slot set for the first form |
|---------|------|-------------------------------------|
| `Object` | object form (item, document, data processor, report) | `DefaultObjectForm` (`DefaultForm` for DataProcessor / Report / external) |
| `Folder` | folder form | `DefaultFolderForm` |
| `List` | list form (`Список`, DynamicList with `MainTable`) | `DefaultListForm` (`DefaultForm` for a document journal / filter criterion) |
| `Choice` | choice form | `DefaultChoiceForm` |
| `FolderChoice` | folder choice form | `DefaultFolderChoiceForm` |
| `Record` | record form (`Запись`, `InformationRegisterRecordManager`) | `DefaultRecordForm` |
| `RecordSet` | record-set form (`Набор`, `*RecordSet`) | none — the platform has no such slot |
| `Save` / `Load` | settings storage save / load form | `DefaultSaveForm` / `DefaultLoadForm` |
| `Custom` | arbitrary form, no main attribute | none |

| Object kind | Purposes (primary first) |
|-------------|--------------------------|
| Catalog, ChartOfCharacteristicTypes | Object, Folder, List, Choice, FolderChoice, Custom |
| Document, ChartOfAccounts, ChartOfCalculationTypes, ExchangePlan, BusinessProcess, Task | Object, List, Choice, Custom |
| DataProcessor, Report, ExternalDataProcessor, ExternalReport | Object, Custom |
| InformationRegister | Record, List, RecordSet, Custom |
| AccumulationRegister, AccountingRegister, CalculationRegister | List, RecordSet, Custom |
| DocumentJournal, FilterCriterion | List, Custom |
| Enum | List, Choice, Custom |
| SettingsStorage | Save, Load, Custom |
| Table of an external data source (`ExternalDataSources/<Src>/Tables/<T>.xml`) | ObjectData: Object, List, Choice, Custom; NonobjectData: Record, List, Choice, Custom |

A purpose the kind does not have is refused with the list of valid ones (an information register has no `Object` form — use `Record`). Russian names and `…Form` spellings (`ФормаСписка`, `ListForm`) are accepted as synonyms. A constant has no own forms — use a common form.

#### What Gets Created

```
<ObjectDir>/Forms/
├── <FormName>.xml                    # Form metadata (UUID)
└── <FormName>/
    └── Ext/
        ├── Form.xml                  # Form description (logform namespace)
        └── Form/
            └── Module.bsl           # BSL module: 5 empty regions
```

#### What Gets Modified

- `<ObjectPath>` — adds `<Form>` to `ChildObjects` (before `<Template>` or `<TabularSection>`), updates Default*Form (auto if empty, or explicit with `--set-default`)

#### Details

- FormType: Managed
- UsePurposes: PlatformApplication, MobilePlatformApplication
- AutoCommandBar with id=-1
- Main attribute per the purpose table (`Объект`, `Список`, `Запись`, `Набор`; none for `Custom`) with `MainAttribute=true`
- BSL module (UTF-8 with BOM, CRLF) contains 5 empty regions: `ОбработчикиСобытийФормы`, `ОбработчикиСобытийЭлементовШапкиФормы`, `ОбработчикиКомандФормы`, `ОбработчикиОповещений`, `СлужебныеПроцедурыИФункции`; `form-compile` / `form-edit` later add handler stubs into them

#### Supported Object Types

Every kind of the purpose table above. The kind is the first element under `MetaDataObject`, not a name search.

---

### Removing a Form

Unified across configuration objects and EPF/ERF — pass the object name (or alias `ProcessorName` for backward compatibility).

```
1c-form-scaffold remove <ObjectName> <FormName> [SrcDir] [-DryRun | -Force] [-CleanReferences]
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| ObjectName (alias `ProcessorName`) | yes | — | Object name (root XML lives at `<SrcDir>/<ObjectName>.xml`) |
| FormName | yes | — | Form name to remove |
| SrcDir | no | `src` | Source directory |
| DryRun | no | off | Print the root XML and files that would change; do not mutate anything |
| Force | required to delete | off | Confirm the reviewed removal plan and perform it |
| CleanReferences | no | off | Also clear references to the form in **other** files of the configuration, in the same transaction. Without it such references stop the removal |

**Commands (preview first, then execute):**
```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-form-scaffold/scripts/remove-form.ps1 -ObjectName "<ObjectName>" -FormName "<FormName>" [-SrcDir "<SrcDir>"] -DryRun
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-form-scaffold/scripts/remove-form.ps1 -ObjectName "<ObjectName>" -FormName "<FormName>" [-SrcDir "<SrcDir>"] -Force
```

The script refuses a real deletion without `-Force`. It parses and serializes every XML it will change before mutating the source tree; the deletion and all rewrites are one transaction (renames into `.remove-form-quarantine`, rolled back as a whole on any failure). After execution, run the form / metadata validator required by the main workflow.

**References from the rest of the configuration.** Before deleting, the script scans every `*.xml` under the configuration root (`-SrcDir` or one of its three parents with `Configuration.xml`; without one — only the object's own directory) for the form's **full reference** `<Kind>.<Object>.Form.<Name>`: `ChoiceForm` / `Default*Form` slots of other objects, `ChoiceForm` / `SettingsStorage` inside other forms, home-page items. The plan lists every hit (`reference: <file> <Tag>`). With such references, `-Force` alone exits **2** and changes nothing; `-Force -CleanReferences` clears them: an object slot becomes `<Tag/>`, the property is removed inside a `Form.xml`, a home-page `Item` is cut out. A same-named form of another object (`DocumentJournal.J.Form.ФормаСписка`) or a `CommonForm.<Name>` is never touched — the match is on the full reference, not on the `Form.<Name>` tail. Upstream's own `-Force` cleans references implicitly; here the deletion gate and the cleaning are two explicit switches.

#### What Gets Removed

```
<SrcDir>/<ObjectName>/Forms/<FormName>.xml     # Form metadata
<SrcDir>/<ObjectName>/Forms/<FormName>/         # Form directory (recursive)
```

#### What Gets Modified

- `<SrcDir>/<ObjectName>.xml` — removes `<Form>` from `ChildObjects`
- Every slot of the object that holds the form's full reference (`Default*Form`, `Auxiliary*Form`, an attribute's `ChoiceForm`) becomes `<Tag/>`
- With `-CleanReferences` — the other files listed in the plan

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
# A catalog form other objects still point at: review, then clear the references too
1c-form-scaffold remove Товары ФормаВыбора src/cf/Catalogs -DryRun
1c-form-scaffold remove Товары ФормаВыбора src/cf/Catalogs -Force -CleanReferences
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

### Handler stubs in `Module.bsl`

After writing `Form.xml`, `form-compile` (and `form-edit`) appends an empty procedure to `<Form.xml dir>/Form/Module.bsl` for every bound handler — form and element events, command `action` — that the module does not declare yet. Directive and parameters come from the event catalog (commands: `&НаКлиенте`, `(Команда)`), the body is `// Вставить содержимое обработчика.`, the region follows the BSP standard (`ОбработчикиСобытийФормы`, `ОбработчикиСобытийЭлементовШапкиФормы`, `ОбработчикиСобытийЭлементовТаблицыФормы<Таблица>`, `ОбработчикиКомандФормы`; a missing region is created in standard order). An existing procedure is never changed; a module that is not UTF-8 is left alone with a `[WARN]`; a missing module is created from the form-add template only when `Form.xml` sits in an `Ext` directory. The output ends with `Handlers (<module>):` — `+` added, `=` already there (with line ranges), `?` not added and why. **There is no switch to turn this off**: expect the module to change and include it in the review (`Invoke-1CEdit.ps1 -Preview` restores both files).

### Verification

`1c-form-validate <OutputPath>` (section 6) and `1c-form-info <OutputPath>` (section 5); MCP evidence set per `content/rules/tooling-playbooks.md`: `get_xsd_schema` / `verify_xml` with `object_type="Форма"`.

---

## 4. Edit — Change an Existing Form

Applies a JSON list of edits to an existing `Form.xml` and leaves everything else in the file as it was. Moved or changed elements keep their `id`, so handlers and module references keep working. Elements are written by the same emitters as `form-compile` (all its element keys, companions, enum spelling, child order), ids come from the form's own pools.

Saving uses Configurator-style compact empty tags (`<Tag/>`) and keeps the file's BOM and CRLF / LF. Literal text in CDATA, comments and processing instructions is excluded from empty-tag normalization.

### Usage

```
1c-form-edit <FormPath> <JsonPath>
```

| Parameter | Required | Description |
|-----------|:--------:|-------------|
| FormPath | yes | Path to existing Form.xml |
| JsonPath | yes | Path to the JSON with the edits (UTF-8, or UTF-16 with BOM; a cp1251 file is refused with the byte position instead of silently mangling Cyrillic) |

### Command

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-form-edit/scripts/form-edit.ps1 -FormPath "<path>" -JsonPath "<path>"
```

### What can be edited

| Key | Edit |
|-----|------|
| `elements` | List of element operations, applied in order (below) |
| `attributes` | Add; `set` — change; `rename` + `to` — rename; `remove` — delete. A column by path `Table.Column` (or `Объект.ТЧ.Column` for a form-side column of a tabular section) |
| `commands` | Add, `set`, `rename`, `remove` |
| `parameters` | Form parameters: add, `set`, `rename`, `remove` |
| `title` | Form title (string or `{ru, en}`); `null` removes it |
| `properties` | Form properties, `{ "windowOpeningMode": "LockOwnerWindow" }`; `null` removes one |
| `events` | Form event handlers, `{ "OnOpen": "ПриОткрытии" }`; `null` value = conventional name |
| `excludedCommands` | Exclude standard commands `["Copy"]`; bring back `{ "remove": ["Copy"] }` |
| `conditionalAppearance` | Add conditional appearance rules |
| `commandInterface` | Add commands to the form's command interface |

All keys are optional and combine freely. Take names from `1c-form-info`.

#### Element operations

| Key | Operation |
|-----|-----------|
| element type (`input`, `group`, `table`, …) | Add a new element — same keys as in `form-compile` |
| `move` | Move a name or a list of names (kept together, in that order) with their content; a position is required |
| `set` | Change properties of a name or a list of names; `null` resets a property; a string `title` changes the Russian text only; `group` changes a group's orientation; `events` adds handlers. Name, element type, data path and a button's command are not changed by `set` — remove and add again |
| `remove` | Delete a name or a list; a group / page / table with its content. Refused while `Module.bsl` still references what is being removed |
| `autoCmdBar` | Properties of the form command bar: `{ "autoCmdBar": "ФормаКоманднаяПанель", "autofill": false }`, `horizontalAlign` |

| Position keys | Where |
|---------------|-------|
| `after: "X"` / `before: "X"` | Next to X, in X's group |
| `into: "G"` | At the end of group / page / table / command bar G |
| `into: "G", first: true` | At the start of G |

A new element without a position goes to the end of the form; the next one without a position follows it.

```json
{
  "attributes": [
    { "name": "Срочно", "type": "boolean" },
    { "name": "СписокТоваров", "type": "DynamicList", "settings": { "mainTable": "Catalog.Товары" } }
  ],
  "commands": [ { "name": "Пересчитать", "action": "ПересчитатьОбработка" } ],
  "elements": [
    { "group": "alwaysHorizontal", "name": "ГруппаОтгрузка", "after": "Контрагент" },
    { "move": ["Склад", "Организация"], "into": "ГруппаОтгрузка" },
    { "check": "Срочно", "path": "Срочно", "into": "ГруппаОтгрузка" },
    { "button": "Пересчитать", "command": "Пересчитать", "into": "ФормаКоманднаяПанель" },
    { "set": "Контрагент", "title": "Покупатель", "events": { "OnChange": null } },
    { "remove": "Комментарий" }
  ],
  "events": { "OnOpen": null }
}
```

#### Attributes, commands, parameters: change and rename

- `set` takes the same keys as adding; `type` replaces the type as a whole. The kind of an attribute (table / value / dynamic list) and the main attribute's type are not changed. `settings` of a dynamic list changes only the parts given.
- `{ "rename": "Данные", "to": "Строки", "renameInModule": true }` — data paths, conditional appearance and the command interface follow the new name; `renameInModule` also rewrites `Module.bsl`, without it the tool lists the module lines to fix. Element and handler names are not renamed.

#### Extension forms

A borrowed form (`<BaseForm>`) is detected automatically. Name the extension's own elements, attributes and commands with the extension prefix (`Расш1_…`) and give them a `title`. Every handler gets a call type `callType`: `Before`, `After` or `Override` (default `Before`, as the platform reads it); `events` / `actions` take `{ "handler": …, "callType": … }` or a list of them. An auto-named handler is `<prefix><Element><Suffix><Перед|После|Вместо>` — it never collides with the base form's procedure.

#### Element keys, events, types

Same DSL as `1c-form-compile` — element keys, `command` / `stdCommand`, event names and attribute types are in [`form-compile-dsl.md`](form-compile-dsl.md); the companion elements each type receives are listed in its *Auto-generation* section. Unlike `form-compile`, an event outside the catalog is only a `[WARN]` here (upstream behaviour). Handler stubs for new bindings are appended to `Module.bsl` exactly as `form-compile` does (§3).

A `DynamicList` attribute **must** carry `settings.mainTable` and/or `settings.query` (local rule). Without a source the designer accepts the XML, but the form fails to open (`не задан ни текст запроса, ни основная таблица`). `form-edit` refuses that JSON before writing; `form-validate` reports the same gap on an existing form. All `settings` keys of `form-compile` are accepted (filters, order, conditional appearance, fields, parameters).

### Output

```
=== form-edit: ФормаДокумента ===

Added elements:
  + [CheckBoxField] Пометка -> Пометка {OnChange} → ГруппаНомерДата, после Номер
Form events:
  + event OnOpen -> ПриОткрытии
Added attributes:
  + Пометка: boolean (id=61)

Handlers (…/Ext/Form/Module.bsl):
  + ПриОткрытии — added, lines 3-6
  + ПометкаПриИзменении — added, lines 12-15
```

### When to Use

- **After `1c-form-compile`**: add, move or change elements without regenerating the form
- **Modifying existing forms**: vendor-shaped forms keep everything not named in the JSON
- **Batch edits**: one JSON can combine elements, attributes, commands, parameters and form properties

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
| `Handlers` | no | off | Switch. Shows each bound handler (form and element events, command actions) with its line range in `Ext/Form/Module.bsl`; a handler missing from the module is marked |

### Command

```powershell
# Default — pages collapsed, main command bar shown as a separate section
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-form-info/scripts/form-info.ps1 -Path "<path to Form.xml>"

# Expand a specific page
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-form-info/scripts/form-info.ps1 -Path "<path>" -Expand "Goods"

# Expand all pages
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-form-info/scripts/form-info.ps1 -Path "<path>" -Expand "*"
```

Handlers with their module lines (before editing the module):
```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-form-info/scripts/form-info.ps1 -Path "<path>" -Handlers
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
| Detailed | no | off | Print every check, not only problems |
| MaxErrors | no | 30 | Stop after N errors |

### Command

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-form-validate/scripts/form-validate.ps1 -FormPath "<path>"
```

### Checks Performed

The structural checks (upstream 1–11) run first and print no number; from 12 on every `[ERROR]` / `[WARN]` line starts with its check number. Numbers up to 27 are upstream's; 28 and 29 are local and come after upstream's last number, so an upstream refresh does not renumber them.

| # | Check | Severity |
|---|-------|----------|
| — | Root element `<Form>`; `version` well-formed and inside the tested range 2.17–2.21 | ERROR / WARN |
| — | `<AutoCommandBar>` present (id other than `-1` is a warning — vendor forms have it) | ERROR / WARN |
| — | Element / attribute / column / command / parameter id and name uniqueness (separate pools); a DynamicList attribute without `MainTable` and `QueryText` (local) | ERROR |
| — | Companion elements (ContextMenu, ExtendedTooltip, …) | ERROR |
| — | `DataPath` and other bindings reach an existing attribute (`Items.<Table>.CurrentData.*` resolved; base-form paths of a borrowed form included) | ERROR / WARN |
| — | Button `CommandName` references an existing command | ERROR |
| — | Events have non-empty handler names | ERROR |
| — | A command without `Action` (assigned at runtime in vendor forms) | WARN |
| — | At most one `MainAttribute`; multilingual `Title` | ERROR |
| — | Extension form: `BaseForm` version, valid `callType`, extension ids ≥ 1000000 | ERROR / WARN |
| 12 | Type values — known namespaces and `cfg:` prefixes; `cfg:Catalogs.X` (export folder name, local) and `External*` types in a configuration are errors | ERROR / WARN |
| 13 | Namespace prefixes used in types and `xsi:type` are declared in the file | ERROR |
| 14 | Format version equals the form descriptor `Forms/<Name>.xml` (and the `<BaseForm version>` stamp of a borrowed form); differing from the rest of the dump is only a warning | ERROR / WARN |
| 15 | Enum property values in the platform spelling (wrong case, a button's `TextPicture` / a command's `PictureAndText` are errors; old names are warnings) | ERROR / WARN |
| 16 | Element property order as the platform writes it | WARN |
| 17 | Dynamic-list `Field` / `CalculatedField` / `Parameter` under compatibility mode below 8.3.19 | WARN |
| 18 | Element tag known for the format version | ERROR / WARN |
| 19 | Companions match the element type | ERROR |
| 20 | Properties belong to the element type | ERROR / WARN |
| 21 | Element allowed in its container | WARN |
| 22 | `Ext/Form/Module.bsl`: every bound handler and command action exists (missing = error); declared once (duplicate = error, local); compilation directive present and matching the event, no more mandatory parameters than the platform passes (warnings, local); procedures bound nowhere and not referenced (warning) | ERROR / WARN |
| 23 | `AdditionSource` of search / view-status / search-control additions points at the right item | ERROR / WARN |
| 24 | A module variable named like a form attribute | ERROR |
| 25 | Conditional appearance fields exist | WARN |
| 26 | `Enum.X.EnumValue.Y` design-time values (the platform never matches them) | ERROR |
| 27 | `web:` / `win:` colors from the platform palette | ERROR |
| 28 | (local, was 12b) A default / auxiliary object, folder or record form of a catalog, document, chart, exchange plan, business process, task or information register has a main attribute of its owner's own type; no `Description` / `Code` binding when the owner's length is 0 | ERROR |
| 29 | (local, was 14) `РеквизитФормыВЗначение` / `ЗначениеВРеквизитФормы` only in `&НаСервере` (a procedure without a directive is server-side) | ERROR |

### Output

Brief by default — only problems and the verdict:

```
=== Validation OK: Form.ФормаДокумента (29 checks) ===
```

`-Detailed` prints every check (`[OK]    14. Format version: 2.20, matches the descriptor and the dump`, …) and the totals line.

Return code: 0 = no errors (warnings allowed), 1 = errors found.

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
