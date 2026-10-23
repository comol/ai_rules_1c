# 1c-metadata-manage — sync history of the vendored scripts

The PowerShell tools under `tools/` are vendored from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills) (MIT). This file holds the per-document sync notes that used to close each `docs/*.md` (what each upstream sync changed, what was cross-checked and what stays deliberately local). It is maintainer history — nothing loads it during a task; the operational description of every tool lives in the domain doc named by each heading.

## bsp-manage.md

### Upstream sync `2026-07-30`

Re-checked against upstream `epf-bsp-init` / `epf-bsp-add-command` at the `2026-07-30` sync: **no drift** — kinds, default command types, the `СведенияОВнешнейОбработке` skeleton, `Назначение` / `Модификатор` sections, `НСтр` literals for additional commands, and every handler template (`ВыполнитьКоманду` branches, `Печать` with `УправлениеПечатью.СведенияОПечатнойФорме`) still match Sections 1–2 below. Nothing to port; both skills remain no-script upstream.

### Earlier Additions (upstream `w-2026-05-17`)

The upstream `cc-1c-skills` skills `epf-bsp-init` and `epf-bsp-add-command` are no-script (the agent does the work directly via Read / Edit / Glob / Grep). Their content is already covered by Sections 1–2 of this document, in English. Cross-checked against upstream `w-2026-05-17`:

- Kind mapping (six kinds: `ДополнительнаяОбработка`, `ДополнительныйОтчет`, `ЗаполнениеОбъекта`, `Отчет`, `ПечатнаяФорма`, `СозданиеСвязанныхОбъектов`) — aligned.
- Default command type per kind — aligned.
- Free-form command types (open form, client method, server method, form filling, safe-mode script) — aligned.
- `СведенияОВнешнейОбработке` skeleton, `Назначение` section for assignable kinds, `Модификатор` for `ПечатнаяФорма` — aligned.
- Server handlers (`ВыполнитьКоманду` for `ЗаполнениеОбъекта` / `СозданиеСвязанныхОбъектов` / global processors, `Печать` for `ПечатнаяФорма`) — aligned.

No script files were brought into `tools/` — the operations are pure module-text edits performed by the agent, which is how upstream ships them as well.

## cf-manage.md

### Local fix `2026-10-19` — `add-childObject` follows `NEW_OBJECT_POSITION`

`cf-edit` v1.11 → **v1.12** (support ticket 4e6f4e67, item 4): `add-childObject` always inserted a new entry by name inside its kind group (culture-aware `-gt`), whatever `NEW_OBJECT_POSITION` said. It now resolves the setting as `meta-compile` does — `end` (default) after the last object of the kind, as Configurator; `byName` with the 1C-tree comparator; order-sensitive kinds never sorted. Pinned by `tools/tests/metadata-tools-regression.ps1`.

### Local fix `2026-10-01` — sibling validators are found

The auto-validation of `cf-edit`, `interface-edit`, `subsystem-compile` and `subsystem-edit` looked for the validator at upstream's `..\..\<validator>\scripts\` path, which does not exist in this layout, so it was skipped silently; `xdto-edit` looked for `xdto-decompile` / `xdto-compile` / `xdto-validate` the same way and refused every structural operation. All five now take the sibling script from their own `scripts` directory.

### Upstream sync `2026-07-30`

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `cf-edit` v1.4 → **v1.11**, `cf-info` v1.2 → **v1.4**, `cf-init` v1.2 → **v1.3**, `cf-validate` v1.3 → **v1.4**.

- **`cf-edit` now enforces the vendor support gate** — it refuses to edit a configuration whose "possibility of modification" is off, and points at `support-edit`. See [support-manage.md](support-manage.md).
- **`cf-info` reports the support state** of the configuration (read from `Ext/ParentConfigurations.bin`) — whether it is on vendor support and whether modification is allowed.

### Earlier Additions (upstream `w-2026-05-17`)

The PowerShell scripts under `tools/1c-cf-manage/scripts/` were refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights:

#### `cf-init`

- Generates a default panel layout aligned with stock ERP/БП ≥ 8.3.24: open windows on top, sections on the left. Without this layout the web client renders sections as icons only — `web-test` could not see them. Modern interface mode + 8.2-style backward compatibility is the default.

#### `cf-edit` — new operations

- **`set-panels`** — configure the configuration panels via JSON. Aliases by name (`sections`, `open`, `favorites`, `history`, `functions`), panel stacking via `{group: [...]}`, multiple panels side-by-side. Russian aliases (`Открытых`, `Разделов`, `Избранного`, `История`, `Функций`) are accepted and silently mapped to canonical English aliases.
- **`set-home-page`** — rewrite the home page: one or two columns, list of forms with height / visibility / role overrides.
- **`add-childObject`** — now requires the object file to exist on disk; otherwise the script fails with a hint to call `/meta-compile`, `/role-compile`, `/subsystem-compile` first. Previously `Configuration.xml` could end up referencing a missing file and the platform would silently refuse to load. The legacy mode (root XML lost while files survive) is preserved for the rare rollback scenario.

#### `cf-info`

- Configuration overview shows the panel layout (panel stacks within one side and side-by-side panels). With `-Section home-page` — full home page contents with layout and role overrides.

#### `cf-validate`

- Cross-references `Form` references in the home page and in default-form properties of configuration objects — broken links are now caught at validation time, not at load time.
- Platform 8.5 support — new compatibility-mode and interface-mode values plus the new XML header format. (Same upgrade in `cfe-validate`, `epf-validate`, `skd-validate`.)

## cfe-manage.md

### Local fix `2026-10-19` — an element `CommandSet` keeps its `ExcludedCommand` list

`cfe-borrow` v1.10 → **v1.11** (support ticket 2b392369, an addition to 4e6f4e67): `Borrow-Form` removed every `ExcludedCommand` inside `ChildItems`, so an element whose base form excludes standard commands (a tabular-section table without `Add` / `Copy`) got an empty `<CommandSet></CommandSet>` in the form and in `BaseForm`. Configurator keeps the element's `CommandSet` with its `ExcludedCommand` list in both parts and drops an empty one on load, so the check dump after a partial load differed from the source directory. The element `CommandSet` is now copied as is. Pinned by `tools/tests/cfe-borrow-regression.ps1`.

### Local fix `2026-10-18` — borrowing follows Configurator 2.20

`cfe-borrow` v1.9 → **v1.10**, `cfe-validate` v1.4 → **v1.5** (support ticket 4e6f4e67):

- A borrowed form's `Forms/<Form>.xml` gets the `InternalInfo` `PropertyState` (`Form` / `Extended`) instead of an empty `<InternalInfo/>`.
- `CommandSet` no longer ends the form-property copy: it, its `ExcludedCommand` list and every property after it up to `AutoCommandBar` reach the form and `BaseForm`.
- One attribute (`Type.Name.Attribute.A`) or one tabular-section column (`Type.Name.TabularSection.T.Attribute.A`) can be borrowed: source uuid, source `<Type>`, type objects as shells, no cascade. `-BorrowMainAttribute Only` adds the form attribute `Объект` without the cascade and strips the data paths in both parts.
- A new extension `ChildObjects` entry is appended to the end of its type group instead of being sorted by name. `cf-edit` / `meta-compile` keep the by-name order (APK:1108) for the main configuration.
- No empty `Ext/Form/Module.bsl` for a borrowed form; an existing module is kept.
- A borrowed `Document` gets an empty `<RegisterRecords/>`.
- `cfe-validate` check 12 reports an unborrowed `CommonPicture` or a `StyleItem` outside the platform style list as an error (the form will not load with `Configuration.xml`); check 11 no longer warns about a borrowed form without `Module.bsl`. `cfe-borrow` borrows a referenced style item when the source file exists, and strips a `style:` reference that is neither borrowed nor a platform style item.
- `Detect-FormatVersion` takes the string length after reading. A short UTF-8 `Configuration.xml` with Cyrillic no longer throws on `Substring` (file length is bytes).

Pinned by `tools/tests/cfe-borrow-regression.ps1`.

### Local fix `2026-10-01` — `BaseForm` keeps multi-line texts

`cfe-borrow` shifted every line of the borrowed `AutoCommandBar` / `ChildItems` one tab deeper for `BaseForm`, including the continuation line of a multi-line `v8:content`, so the copy of the base form no longer matched the configuration (support ticket bc42b89c). Only line breaks between two tags are indentation now; the texts keep their bytes.

### Recent Additions (upstream sync `2026-07-30`)

The PowerShell scripts under `tools/1c-cfe-manage/scripts/` were refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights of this sync (previous base: late May 2026):

#### `cfe-patch-method` — v1.1 → v2.5, the biggest change in this group

- **Source-aware generation**: the original method is read from the source configuration (`-ConfigPath`, auto-detectable via `.dev.env` `EXPORT_PATH`), so the interceptor gets the real signature, context directive and — for `ModificationAndControl` — the full original body. `ModulePath` may now be a path to the source `.bsl` instead of a logical name.
- **`Instead` (`&Вместо`)** interceptor type with a `ПродолжитьВызов(...)` scaffold; works for functions too.
- **Drift control** — `-Check` / `-Actualize` over controlled (`&ИзменениеИКонтроль`) methods, extension-wide or narrowed to a module / method. Re-applies your `#Вставка` / `#Удаление` edits onto a changed vendor original, reports what moved, what conflicted and what the vendor has already adopted. Conflicts land in a merge workspace with anchored `conflict.md` files instead of being lost. **Run `-Check` after every vendor update** — the platform never reports this drift itself.
- Repeated interception of an already patched method is skipped instead of duplicated.

Full description in section 4 above.

#### `cfe-borrow` — borrowing forms now matches Configurator output

- The borrowed form gets the **complete `ChildItems` tree** (not the previously empty skeleton). Loadable into the target base without manual XML fixes for complex ERP forms.
- **Dependencies are auto-borrowed**: shared pictures, style elements, enums, and enum values used by the borrowed form. No more cascade of "object not found" errors after the first load.
- `DataPath`, `Events`, `TitleDataPath`, `TypeLink`, `CommandName` are stripped from the borrowed form (these caused "invalid data path" / "event not loaded" errors on real ERP forms, also for command-bar buttons).
- Form-level properties (`AutoTitle`, `WindowOpeningMode`, …) are preserved both in the main section and in `BaseForm`.
- **`-BorrowMainAttribute`** (`Form` or `All`) — borrows the form's main attribute (`Object`) and transitively all its attributes, tabular sections, and dependent types. Closes the manual-collection workflow when adding an attribute to a borrowed form.

#### `cfe-validate`

- New checks for borrowed-form structure, their dependencies (shared pictures, style elements, enums), and the extension's own subobjects (attributes, tabular sections, enum values, forms).
- False positives removed: `DataPath` / `TitleDataPath` inside `BaseForm` are correct (Configurator emits them); the extension's own subobjects (own attributes, own enum values) are no longer validated as borrowed.

#### `cfe-init`

- Interface mode and compatibility mode are inherited from the base configuration (resolved via `-ConfigPath`). The extension matches the base's behaviour by default.

#### Vendor support

An extension is the **default answer** when a typical object on vendor support needs a change: support state stays untouched and vendor updates keep flowing. The mutating tools of this skill now enforce that — they refuse to edit a locked object directly and point here. See [support-manage.md](support-manage.md).

## db-manage.md

### Local fix `2026-10-20` — `-Dynamic` takes `auto` / `disable`

`db-update` v1.13 → **v1.14** (support ticket 7557c7cf): through `powershell.exe -File` a lone `-Dynamic "-"` never reaches the script — Windows PowerShell 5.1 exits with a non-zero code and no output, so the agent saw a silent failure instead of `/UpdateDBCfg -Dynamic-`. `-Dynamic` now also accepts `auto` and `disable` (the ibcmd spellings), mapped to `+` / `-`; `+` / `-` keep working in-process, and `-Dynamic:-` works through `-File` as well. Checked on a throwaway 8.3.27.2130 file base: `-File … -Dynamic disable` → `-Dynamic-`, `auto` → `-Dynamic+`, both exit 0.

### Recent Additions (upstream sync `2026-07-30`)

The PowerShell scripts under `tools/1c-db-ops/scripts/` were refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights of this sync (previous base: late May 2026):

- **`db-dump-dt` / `db-load-dt`** — new: full infobase snapshot (configuration + data). See sections 9 and 10.
- **All `db-*` / `epf-*`** — `-AdditionalV8Arguments` / `-AdditionalIbcmdArguments` with per-engine validation and secret masking (see *Common Parameters*); project-wide defaults via `v8args` / `ibcmdargs` in `.v8-project.json`.
- **Platform resolution** — unified across the scripts: explicit `-V8Path` → project config → auto-detect the newest `C:\Program Files\1cv8\*\bin\1cv8.exe`. Locally patched so the project config is read from **`.dev.env`** (`PLATFORM_PATH`, `PLATFORM_ARGS`, `IBCMD_ARGS`, `SUPPORT_GUARD`) before upstream's `.v8-project.json`, and so a **version install directory** — the shape `PLATFORM_PATH` uses — resolves via `bin\1cv8.exe`.
- **`db-load-xml`** — strict log parsing. Catches "Неверное свойство объекта метаданных", "Неизвестное имя типа" and similar messages that the platform writes to the log despite a formal "success" exit. Previously a partial silent metadata loss was reported as a green run.
- **`db-load-xml` / `db-load-git`** — `-UpdateDB` flag combines load + database update in a single Configurator launch (was two separate calls).
- **`db-load-git`** — picks up changes to HTML help (`ru.html` and similar) via partial load even without the accompanying `Help.xml` in the commit. Previously such edits were silently dropped and the help text in the base stayed stale. Fixed search for changed files when sources live in a nested folder of the repo (`src/cf` etc.); path normalisation for the configuration directory is corrected.
- **db-list** — already fully described in Part 1 of this doc (registry of `.v8-project.json`). It is a no-script skill in upstream — the agent reads / writes the JSON directly. No script files were added under `tools/`.

## epf-manage.md

### Local fix `2026-10-07` — common forms in external reports

External reports and data processors may name configuration common forms in `DefaultForm` / `DefaultSettingsForm` / `DefaultVariantForm` (БСП reports: `CommonForm.ФормаОтчета`). Checked on 8.3.27.2130: such an ERF builds in an infobase that has the form, and the reference survives a dump in another infobase with a same-named form (it is stored by name); without the form the build fails with «Неизвестный объект метаданных».

- `epf-validate` check 5 accepts `CommonForm.<Name>` in `DefaultForm` instead of warning about an unexpected prefix.
- `stub-db-create` creates an empty managed common form for every `CommonForm.<Name>` named by those properties, so a build without an explicit infobase passes.
- `erf-init` gained `-BspForms`: the three main forms are the БСП common forms.

### Upstream sync `2026-07-30`

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `epf-build` v1.0 → **v1.12**, `epf-dump` v1.0 → **v1.11**, `stub-db-create` v1.0 → **v1.7**, `erf-init` → **v1.1** (full ERF scaffold — the local copy was a truncated variant).

- **Build / dump via `ibcmd`** — full EPF *and* ERF assembly and disassembly without launching the Designer, when the platform path points at `ibcmd`.
- **`-AdditionalV8Arguments` / `-AdditionalIbcmdArguments`** with per-engine validation and secret masking — same contract as the `db-*` tools ([db-manage.md](db-manage.md)).
- Platform resolution unified with the `db-*` tools (explicit path → `.dev.env` → `.v8-project.json` → auto-detect), locally patched to accept the version install directory shape used by `.dev.env` `PLATFORM_PATH`.
- Autonomous external objects (EPF/ERF) are explicitly exempt from the vendor support gate — they are never part of a configuration on support.

### Earlier Additions (upstream `w-2026-05-17`)

The PowerShell script `tools/1c-epf-validate/scripts/epf-validate.ps1` was refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights:

- **Format version auto-detection** from the nearest `Configuration.xml` (8.3.27+, 8.5).
- **Platform 8.5** support across `epf-validate` and `erf-validate` (new compatibility-mode and interface-mode values, new XML header format).
- **Universal validator improvements** — one-liner output by default (`-Detailed` for the full per-check trace); accepts both an XML file and a folder path as the primary argument; universal `-Path` parameter alongside legacy `-ObjectPath`.
- The same script handles `erf-validate` — upstream `erf-validate` is a thin pass-through to `epf-validate.ps1`, the script auto-detects `ExternalReport` vs `ExternalDataProcessor` from the root XML element. No separate `erf-validate.ps1` is shipped.

## form-manage.md

### Local fix `2026-10-23` — form-edit conditional appearance

`form-compile` writes the form's conditional appearance from the top-level `conditionalAppearance` key (last child of `<Attributes>`), but `form-edit` had no such key: an item could only be added by editing `Form.xml` by hand (the journal workaround), where the namespaces of its colours (`web`, `style`, `dcsset`, `dcscor`, `v8ui`) are easily forgotten on a form that does not declare them. Worse, an attribute added to a form that already had the block was written after it, a child order the platform refuses on load. `form-edit` v1.9 → **v1.10**: `conditionalAppearance` takes the grammar of `form-compile` (form-dsl-spec 7c), compiles the items and appends them to the form's own `<ConditionalAppearance>` (created, with `<Attributes>`, when absent; an extension form keeps its own block, `BaseForm` is not touched), declares the prefixes once on `<Form>`, and warns (`[WARN]`, no refusal — the compiler does not check it either) about a `selection` field that is no element of the form. A new attribute now goes before an existing `<ConditionalAppearance>`. Pinned by `tools/tests/metadata-tools-regression.ps1`.

### Local fix `2026-10-23` — form-edit move and remove

`form-edit` could neither put an existing element into another place nor remove one: both were hand edits of `Form.xml` (the journal workarounds), with ids, companions, the indent of the moved subtree and an emptied `ChildItems` left to the editor, and nothing warned that a removed table was still the source of another table's `AdditionSource`, the target of a `Form.Item.<Name>.StandardCommand` button or used in the module as `Элементы.<Name>`. `form-edit` v1.8 → **v1.9**: `move` (`{ "elements": [...], "into" | "after" | "before" }`) takes the elements with their subtree and ids to the target resolved and checked as for new elements (the target lookup of the additions is one function now), re-indents the subtree, removes the whitespace it leaves and an emptied `ChildItems` (the platform writes a group without children without it); an element that is a companion, named twice or also removed, `after` with `before`, an anchor outside the target container and a move into itself or its own descendant are refused. `remove` (`["Name", ...]`, `"force"`) takes an element with its subtree, companions and the whitespace before it, drops an emptied `ChildItems` (an emptied command bar becomes a self-closing tag) and refuses, writing nothing, when the element or something inside it is still referenced from outside the removed subtrees: `AdditionSource/Item`, a `CommandName` with `Form.Item.<Name>.`, `AssociatedTableElementId`, a field of the form's `ConditionalAppearance` selection, any text with `Items.<Name>` (`DataPath`, `TitleDataPath`, `RowPictureDataPath`, `FooterDataPath`, `TypeLink`, ...; the forms were checked against the vendor dumps) and `Элементы.<Name>` / `Items.<Name>` in `Ext/Form/Module.bsl` outside comments and string literals; `"force": true` removes with a `[WARN]` per reference. The event handlers of the removed subtree that are still procedures in the module are listed as `[INFO]`. Order of one JSON: `remove`, `move`, `set`, then the additions. The report gets `Removed:` and `Moved:` sections. Pinned by `tools/tests/metadata-tools-regression.ps1`.

### Local fix `2026-10-23` — form-edit set

`form-edit` could add things but not change them: a property or an event of an existing element (`choiceButton`, `clearButton`, a `Title`, `choiceParameterLinks`, `StartChoice` on an input, `AfterDeleteRow` on a table) and the form's own title, properties and events could only be changed by editing `Form.xml` by hand — the workaround recorded in the skill-gap journal, with the risk of a property in the wrong place (the platform refuses a wrong child order on load). `form-edit` v1.7 → **v1.8**: the new top-level key `set` takes `{ "element": "<name>", <DSL keys of form-compile>, "on": [...], "off": [...] }` and `{ "form": true, "title", "properties", "on", "off" }`. The keys are compiled by `form-compile` (a one-element temporary DSL, `title: ""` added when there is none) and the compiled property nodes replace the node of the same tag or are inserted at its schema position; `null`, `[]`, `{}` — or a value the compiler treats as the default (`visible: true`) — remove the property; block keys (`choiceParameters`, `choiceList`, `format`, ...) replace the whole block. `on` merges events into `<Events>` (the same name and `callType` is replaced; a string gets the compiler's handler name, an object takes `handler` / `callType`), `off` removes them and an emptied `<Events>`; a form event needs an explicit handler. Ids, companions and `ChildItems` are never touched, nothing is renumbered; an unknown element, a structural key (`children`, `columns`, `contextMenu`, ...), a key that is no property of the tag, an unsupported tag and a string form event are refused before anything is written. The schema position comes from the vendor dumps: there is no XSD in the repository, so the child order of 18 tags (the supported elements and the form root) was derived from the pairwise precedence of child tags in 29727 `Form.xml` (14917 distinct, 473382 elements) and sits in `form-edit.ps1` as a table; a tag outside it goes before the companions with a `[WARN]`. The report gets a `Changed:` section (`~ [InputField] Name: +ChoiceButton, -Title, +event StartChoice`). `set` runs first and sees only the elements the form had before the edit. `form-edit` also numbers all columns of a new attribute 1..n, those inside `AdditionalColumns` too (they kept the compiler's global counter). Pinned by `tools/tests/metadata-tools-regression.ps1`.

### Local fix `2026-10-23` — form-edit compiles new elements with form-compile; before; command-bar targets

`form-edit` kept a reduced copy of the element emitters, so every DSL key `form-compile` understands and the copy did not was dropped with «unknown key … ignored»: `textEdit`, `maxWidth`, `chooseType`, `minValue` / `maxValue`, `choiceParameters`, `choiceParameterLinks`, `choiceList`, `format`, `save` on an attribute, the `AdditionSource` of the search / status / control additions of a new table, and more. A button could not be put into the command bar of a table, a popup or the form's own `AutoCommandBar` (`into` found elements only through `ChildItems`, and a button given `into` the table itself landed among its columns), and there was no `before`. `form-edit` v1.6 → **v1.7**: elements and attributes are written into a temporary DSL, compiled by `form-compile.ps1` in a child process of the same PowerShell edition, and the compiled nodes are renumbered from the free id pools of the form, re-indented and inserted, so the keys, the defaults and the warnings are the compiler's; the prefixes the nodes use are declared once on `<Form>` when it lacks them. Commands, `formEvents` and `elementEvents` keep `form-edit`'s own emitters (the compiler writes command children in the order the platform refused, see `2026-10-01`). New: `before` (excludes `after`); `into` takes a command bar, context menu, popup, button group, a table's `<Table>КоманднаяПанель` and the form's `ФормаКоманднаяПанель` (the items are compiled as children of a command bar, a missing `ChildItems` is created, a self-closing bar is opened); a button, button group or popup given `into` a Table, and a non-button given `into` a command bar, are refused before anything is written. Behaviour that comes with the compiler: an element or attribute without `title` gets one derived from its name (`title: ""` suppresses it), explicit `false` / `true` values are written as given, an unknown event name is a refusal; `main: false` is set on attributes without a `main` key so the compiler does not infer a main attribute. Buttons now come from `form-compile`, so its `Emit-Button` writes the children in the platform order too (`Type`, `Visible`, `Representation`, `DefaultButton`, `SkipOnInput`, `Enabled`, layout, `Check`, `CommandName`, `Parameter`, `DataPath`, `TextColor` …, `Picture`, `Title`, `ToolTip`, `LocationInCommandBar`, `ExtendedTooltip`; 168762 buttons in 29738 `Form.xml` of the vendor dumps) and spells a button's `TextPicture` as `PictureAndText`, in the PowerShell and the Python compiler alike. The buttons of the form's own command bar now count when the next edit takes its ids. Pinned by `tools/tests/metadata-tools-regression.ps1` and `tools/tests/python-ports-regression.py`.

### Local fix `2026-10-14` — input-field events and pass-through keys

`form-compile` refused the input-field events `Tuning` (Регулирование), `Opening` and `StartListChoice`, which vendor forms use (ZUP dump: 333, 195 and 2 input fields; support ticket 0225a24c, ERP 2.5 `Документ.НачислениеЗарплаты.ФормаДокумента`). They are allowed for `input` in the PowerShell and Python compilers and in `form-edit`, with the handler suffixes `Регулирование` / `НачалоВыбораИзСписка`. The pass-through scalars of `genericScalars` (`markNegatives`, `threeState`, `choiceListHeight` and 30 more) were written to `Form.xml` yet reported as «unknown key … ignored»; they now count as known keys. `form-compile-dsl.md` lists the `input` and `picField` events separately, as the compiler checks them.

### Local fix `2026-10-01` — button and command order, command `Representation`

`form-edit` wrote a button's `CommandName` before its `Representation`, a command's `Action` before its `Picture` and a command's picture-and-text `Representation` as `PictureAndText`; the platform refused such a borrowed form with «Исключение XDTO произошло при чтении файла» (support ticket bc42b89c, 8.3.27.2170). Button children now follow the platform order (`Type`, `Visible`, `Representation`, `DefaultButton`, `Enabled`, `CommandName`, `Picture`, `Title`, `LocationInCommandBar`) and command children `Title`, `Shortcut`, `Picture`, `Action`, `Representation`, taken from every `Form.xml` of the ZUP dump; a command's `PictureAndText` is written as `TextPicture` (and a button's `TextPicture` as `PictureAndText`). `form-validate` check 15 reports a `Representation` outside the element's own enumeration. `form-compile` still writes a command's `Action` before `Shortcut` / `Picture` and a button's `Representation` after `CommandName` — not changed here.

### Local fix `2026-09-25` — vendor-shaped defaults, closed enum values, Form.xml against Module.bsl

Rules taken from the static checks of [AzeevAN/mcp-1c](https://github.com/AzeevAN/mcp-1c) (Apache-2.0; rules re-implemented, no code copied) and calibrated on the ERP (8.3.27) and ZUP Designer dumps so that vendor forms raise no errors.

- **`form-compile` v1.176** (both runtimes): the from-object document choice form sets `ChoiceMode` on its list table like the catalog one; the `document.item` preset (hard-coded default and `presets/erp-standard.json`) writes `AutoTime=CurrentOrLast`, `UsePostingMode=Auto`, `RepostOnWrite=true` in Configurator order; `Description` is bound only when `DescriptionLength > 0`. `windowOpeningMode` / `autoTime` / `usePostingMode` accept only the platform enum values — `form-dsl-spec.md` listed `Modeless`, `Current`, `Postings`, `Movements`, which do not exist. A missing `Configuration.xml` is a `[WARN]` naming the assumed 2.17 instead of a silent guess.
- **`form-add` v1.12** (both runtimes): `-FormName` must be a 1C identifier (exit 2 before any path or XPath is built from it); the object form of an information register names its `RecordManager` main attribute `Запись`, as the Configurator does.
- **`form-validate` v1.10**: version equal to `Configuration.xml` (check 1); `cfg:Catalogs.X` is an error (12); owner type of the main attribute in default object / record forms and no zero-length `Description` / `Code` binding (12b); handlers against `Module.bsl` (13 — duplicate declaration is an error, the rest are warnings because ERP ships them); `РеквизитФормыВЗначение` / `ЗначениеВРеквизитФормы` only in `&НаСервере` (14).

### Local fix `2026-09-14` — compact XML across the reported writers

`form-edit.ps1` normalizes empty tags to Configurator's `<Tag/>` spelling and retains the input EOL. The same save-time behavior covers `form-add`, `remove-form`, parent registration by `form-compile`, `cf-edit`, object registration/merge by `cfe-borrow`, `subsystem-edit`, parent registration by `subsystem-compile`, `interface-edit`, `add-template` and `add-help`. `skd-edit` already normalized tags; its normalization now protects CDATA, comments and processing instructions. No shared runtime dependency was added.

Focused regressions exercise each reported writer on temporary fixtures. Command-add checks compare unrelated form text byte-for-byte for LF and CRLF; template checks cover absolute/relative XML paths and the existing name/EPF lookup. The remove-form quarantine and rollback remain intact.

### Local fix `2026-09-10` — DynamicList settings in `form-edit`

`form-edit` v1.5 wrote a `DynamicList` attribute as Type only. The platform then opened the form with «не задан ни текст запроса, ни основная таблица». `form-edit` v1.6 requires `settings.mainTable` or `settings.query` and emits `<Settings xsi:type="DynamicList">` (`ManualQuery`, `DynamicDataRead`, optional `QueryText`, `MainTable`). `form-validate` v1.9 reports the same gap on an existing form. Full DCS list settings remain `form-compile`.

### Python runtime for `form-remove` (`2026-09-04`)

`remove-form.py` is vendored from the same upstream repository, pinned at commit `ecd289fe11733028d87b55284ea9fb5feff8f513` — the state the PowerShell family below was synced from, so both runtimes are the same tool generation. It exists so a Linux / macOS install is not left with a script it cannot run.

The upstream port needed the same local hardening the PowerShell script carries, and one ordering fix on top: upstream rejects `-DryRun` as an unknown argument, deletes without `-Force`, and deletes the form files **before** parsing the root XML, so a parse failure leaves a half-removed tree. The vendored copy follows the shipped contract instead — parse → plan → gate → atomic root-XML write → delete. Both runtimes are pinned against each other by `tools/tests/python-ports-regression.py`.

The safety hardening is applied to **both** runtimes, so a Windows user is not left with the weaker tool: identifier validation, path containment and the transactional mutation path live in `remove-form.ps1` as well.

The Python port keeps upstream's round-trip style preservation (BOM, EOL, `encoding` case, `<Tag/>`). Since the local 2026-09-14 fix, `remove-form.ps1` also keeps the input EOL and compact empty tags when it stages the parent XML; the quarantine and rollback sequence is unchanged. The `ChildObjects` indentation is identical in both.

Licence: the vendored upstream code is MIT; the full notice ships with the skill as [`NOTICE.md`](../NOTICE.md) and is installed alongside it.

### Upstream sync `2026-07-30`

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `form-compile` v1.23 → **v1.175**, `form-add` v1.5 → **v1.11**, `form-edit` v1.0 → **v1.5**, `form-info` v1.3 → **v1.5**, `form-validate` v1.6 → **v1.8**, `form-remove` → **v1.4**.

- **`form-compile` is the big one** — 150+ upstream releases since the previous base. The DSL grew well past what [form-compile-dsl.md](form-compile-dsl.md) describes: dynamic-list settings (filters, order, conditional appearance, groupings, calculated fields, typed parameter values), forgiving platform types (`StandardPeriod`, `StandardBeginningDate`, `UUID`), roles by GUID for borrowed / extension forms, `SettingsStorage`. **The complete grammar is vendored as [`form-dsl-spec.md`](../tools/1c-form-compile/form-dsl-spec.md)** — read it when a key is missing from the local reference.
- **Support gate** — `form-compile`, `form-edit`, `form-add` refuse to touch a form of a locked object of a typical configuration. See [support-manage.md](support-manage.md).
- **`form-add`** — `DocumentJournal` support.
- **`form-validate`** — dangling-binding checks; paired with the `cfe-borrow` re-borrow idempotency fix.
- **`form-info`** — prints the object's support state.
- **`form-remove`** — clears **every** `Default*Form` slot pointing at the removed form (previously only the generic `DefaultForm`, which left a dangling reference to a deleted form). Local `-DryRun` / `-Force` safety gate is preserved on top.

### Earlier Additions (upstream `w-2026-05-17`)

In addition to the form-compile / form-info / form-add / form-edit / form-remove changes already documented in sections 2–5, **`form-validate`** got the following improvements (script `tools/1c-form-validate/scripts/form-validate.ps1`):

- Stops false-flagging real ERP and БП forms — `Items.<Table>.CurrentData.<Field>` and `~<DynamicList>.<Field>` paths are now correctly resolved through the table's data attribute. Missing table → error; third segment ≠ `CurrentData` → warning.
- Opaque platform paths (`"10"`, `"1000003"`, `"N/M: "`) are skipped without an error. Previously Check 5 reported "attribute not found" on these.
- New attribute-type check in `data`: error on intentionally invalid types, warning on unrecognised ones. Context is honoured — `ExternalDataProcessorObject` / `ExternalReportObject` are valid only inside an external data processor / report; in regular configuration object forms it is an error with a hint to use the inner object type.
- Platform 8.5 support — new compatibility / interface mode values and the new XML header format.
- Brief output by default; full per-check trace via `-Detailed`. The `-Path` parameter accepts both a `Form.xml` file and a `Forms/<Name>` folder (auto-resolves to `Forms/<Name>/Ext/Form.xml`).

### What's New in `form-compile` (vs the previous local snapshot)

- **`-FromObject` mode** — produces a typical form from object metadata; purpose (`Object`/`List`/`Choice`/`Folder`/`Record`) is inferred from `OutputPath`. Document list forms get the standard `Number` and `Date` columns automatically; ChartOfAccounts pulls accounting flags / sub-account kinds correctly.
- **New element types** — `radio` (RadioButtonField with `radioButtonType`: `Auto` / `RadioButtons` / `Tumbler`, `choiceList`); `autoCmdBar` (fills the form's main AutoCommandBar id=-1); `columnGroup` (column grouping inside table `columns` — `horizontal` / `vertical` / `inCell`, nestable).
- **New input keys** — `textEdit: false` (disable free text editing on reference fields), `maxWidth` / `maxHeight` (hard caps, usually with `autoMaxWidth: false`).
- **New group key** — `collapsed: true` for `"group": "collapsible"` (group starts collapsed).
- **Multilingual strings** — any title / presentation may be `{ "ru": "...", "en": "..." }`.
- **Auto-titles** — attributes, commands, pages, popups and decorations without explicit `title` get a humanised title from the name (`НомерСчёта` → "Номер счёта").
- **Format version** — auto-detected from the nearest `Configuration.xml` (8.3.27+, 8.5).
- **Presets** — `tools/1c-form-compile/presets/erp-standard.json` is shipped; project-level override at `<projectRoot>/presets/skills/form/<name>.json`.
- **Defaults aligned with real ERP/БП forms** — multi-line inputs are not auto-width-bounded by default; checkbox title is on the right; `autoTitle` is suppressed when `title` is set; objects with editable state save the input state (`Esc → confirm`).

## help-manage.md

### Upstream sync `2026-07-30`

Script refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `help-add` v1.4 → **v1.9**. It now enforces the vendor support gate — adding help to a locked object of a typical configuration is refused with a pointer to `support-edit` ([support-manage.md](support-manage.md)).

## interface-manage.md

### Upstream sync `2026-07-30`

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `interface-edit` v1.3 → **v1.8**, `interface-validate` → **v1.1**. `interface-edit` now enforces the vendor support gate — it refuses to edit the command interface of a locked typical configuration ([support-manage.md](support-manage.md)).

### Earlier Additions (upstream `w-2026-05-17`)

The PowerShell scripts under `tools/1c-interface-manage/scripts/` were refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights:

- **`interface-edit`** — operations `place` / `order` accept the value as an object (not only as a string). Command names in `hide` / `show` / `place` / `order` are normalised: `Catalogs.X` and `Справочник.X` map to canonical `Catalog.X`.
- **`interface-validate`** — universal validator improvements (one-liner output by default, `-Detailed`, folder path auto-resolution) — see `role-manage.md` → "Recent Additions".

## meta-manage.md

### Local fix `2026-09-25` — versions, generated types, default forms, name clashes

`meta-validate` v1.13, both runtimes with identical messages: object, form descriptor and `Form.xml` versions equal `Configuration.xml` (1e, 6e); every GeneratedType category is required and named exactly (2); `Default*Form` / `Auxiliary*Form` resolve to a declared form of the right role (6f); no `Description` / `Code` binding when the length is 0 (6g) and a warning when the default object form hides a mandatory `Description` nobody assigns (6h); case-insensitive name uniqueness shared by attributes, tabular sections, dimensions and resources (8); `Periodicity` and `DefaultRecordSetForm` forbidden in an information register (12); `cfg:Catalogs.X` is an error (16a). Over all 10 965 ERP objects none of the new error checks fires; 6h warns on 6 attached-file / exchange catalogs.

### Local fix `2026-09-13` — refuse false-success template additions

Both `meta-edit` runtimes refuse `add-template` before any write, including aliases and mixed JSON. The error points to the existing PowerShell template scaffold and requires an explicit template type. No partial registration is presented as a completed template.

### Upstream sync `2026-07-30`

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `meta-compile` v1.12 → **v1.68**, `meta-edit` v1.6 → **v1.23**, `meta-validate` v1.3 → **v1.12**, `meta-info` v1.2 → **v1.4**, `meta-remove` v1.1 → **v1.5**.

- **Support gate** — `meta-edit` / `meta-compile` refuse to touch an object of a typical configuration that is locked ("на замке"); `meta-remove` refuses to delete an object still on support. See [support-manage.md](support-manage.md).
- **`meta-compile`** — many more object types authorable from the DSL (`CommonPicture`, `CommonTemplate`, `SessionParameter`, `CommonCommand`, `CommandGroup`, `CommonAttribute`, `FunctionalOptionsParameter`, `WSReference`), format 2.20 properties (platform 8.3.27), command-group validation, better auto-synonym derivation. Full grammar: [`meta-dsl-spec.md`](../tools/1c-meta-compile/meta-dsl-spec.md).
- **`meta-edit`** — structural attribute properties are now editable point-wise: `Format` / `EditFormat` / `ToolTip` / `ChoiceForm`, `MinValue` / `MaxValue`, `LinkByType` / `ChoiceParameterLinks`, `ChoiceParameters`, `FillValue`; list properties `DataLockFields` / `RegisteredDocuments`; `add-predefined` for predefined items; create-if-missing for properties with a type guard.
- **`meta-validate`** — checks that referenced types exist, validates object commands (group + parameter rule), version-dependent properties and the `LineNumberLength` range, `MDObjectRef` reference shape, and rejects reserved attribute names in a type-aware way.
- **`meta-info`** — prints the object's support state and the type presentation for reference objects.

### Earlier Additions (upstream `w-2026-05-17`)

The PowerShell scripts under `tools/1c-meta-{compile,edit,info,remove,validate}/scripts/` were refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights:

#### `meta-compile` — new properties and stricter type rules

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

#### `meta-edit`

- Same synonym dictionary and case-insensitivity for system enum values, applied in `modify-attribute` / `modify-property` and when parsing `fillChecking` / `indexing`.

#### `meta-validate`

- Empty register check (no dimensions, no resources, no attributes — platform refuses to load).
- Document-movements pointing to a non-existent register are reported.

#### `meta-remove`

- Returns exit code 1 when the object is not found (was silently 0).

## mxl-manage.md

### Upstream sync `2026-07-30`

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `mxl-compile` v1.1 → **v1.4**, `mxl-info` v1.0 → **v1.2**; `mxl-decompile` / `mxl-validate` unchanged. `mxl-compile` enforces the vendor support gate ([support-manage.md](support-manage.md)); `mxl-info` prints the support state of the layout's owner.

### Earlier Additions (upstream `w-2026-05-17`)

The PowerShell script `tools/1c-mxl-validate/scripts/mxl-validate.ps1` was refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights:

- **Universal validator improvements** — one-liner output by default (`-Detailed` for the full per-check trace); accepts both `Template.xml` and a folder path; universal `-Path` parameter alongside legacy `-TemplatePath`.

The compile/decompile/info scripts (`mxl-compile`, `mxl-decompile`, `mxl-info`) were not refreshed — no significant upstream changes for them in this period.

## role-manage.md

### Local fix `2026-10-14` — `role-validate` parameters, rights-only edits

The validate section described `-MetadataPath`, which `role-validate.ps1` does not have (the call failed with a PowerShell parameter error; support ticket d3372592): the metadata file is located from the `Rights.xml` path. The section now lists the real parameters (`-RightsPath` / `-Path`, `-OutFile`, `-Detailed`, `-MaxErrors`). The manual fallback for rights-only edits of an existing role contradicted `SKILL.md → Hard rule`; it is now one of its documented exceptions, because no tool edits a role in place.

### Upstream sync `2026-07-30`

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `role-compile` v1.5 → **v1.8**, `role-info` v1.0 → **v1.2**, `role-validate` → **v1.1**. `role-compile` enforces the vendor support gate ([support-manage.md](support-manage.md)); `role-info` prints the support state.

### Earlier Additions (upstream `w-2026-05-17`)

The PowerShell scripts under `tools/1c-role-{compile,info,validate}/scripts/` were refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights:

- **`role-compile`** — `OutputDir` now accepts the source root of the configuration; `Roles/` is created automatically. Legacy behaviour (path already ending in `Roles`) is preserved. The DSL key `rights` is accepted as a synonym of `objects`.
- **`role-validate`** — auto-discovers metadata from the path to `Rights.xml`; `-MetadataPath` is no longer required, metadata-driven checks always run when the file is present.
- **All 10 validators** (`role-validate`, `meta-validate`, `epf-validate`, `skd-validate`, `cf-validate`, `cfe-validate`, `form-validate`, `mxl-validate`, `subsystem-validate`, `interface-validate`) now emit a single one-liner by default; the full per-check trace is available via `-Detailed`. Each accepts a folder path as the primary file argument and resolves to the canonical XML file (e.g. `Roles/MyRole` → `Roles/MyRole/Ext/Rights.xml`). The universal `-Path` parameter is supported in addition to the legacy named parameters (`-RolePath`, `-FormPath`, `-TemplatePath`, `-ObjectPath`, …).

## skd-manage.md

### Upstream sync `2026-07-30`

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `skd-compile` v1.104 → **v1.109**, `skd-edit` v1.24 → **v1.30**, `skd-info` v1.5 → **v1.8**, `skd-decompile` v0.90 → **v0.91**, `skd-validate` → **v1.2**.

- **Support gate** — `skd-compile` / `skd-edit` refuse to modify a schema of a locked typical configuration ([support-manage.md](support-manage.md)).
- **`skd-edit`** — parameter value lists in shorthand (paired with `skd-compile`).
- **`skd-info`** — `-Raw` flag for lossless round-trip extraction of the query text; prints the support state.
- Full DSL grammar vendored as [`skd-dsl-spec.md`](../tools/1c-skd-compile/skd-dsl-spec.md).

### Earlier Additions (upstream sync `w-2026-05-31`)

The PowerShell scripts under `tools/1c-skd-{compile,edit,info,validate}/scripts/` were refreshed again from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills) (`skd-compile` → v1.104, `skd-edit` → v1.24, `skd-info` → v1.5, `skd-validate` → v1.2), and the new `1c-skd-decompile` tool (draft, v0.90 — see section 5) was added. Highlights from the prior `w-2026-05-17` batch still apply:

#### `skd-edit` — new operations and flags

- `set-field-role` — replace a field role in one line with flag tokens (`@balance`, `@dimension`, `@account`, `@period`, `@required`, `@autoOrder`, `@ignoreNullValues`) and kv params (`balanceGroupName`, `balanceType`, `accountTypeExpression`, …). Closes the "temporarily disable role to debug" pattern.
- `modify-structure` — change groupings by name while preserving selection, order, filters, and conditional appearance.
- `clear-conditionalAppearance` — drop conditional appearance for a field.
- `add-drilldown` — wire detail processing to DCS resources across all named templates.
- `rename-parameter` — atomically rename a parameter and update `&Name` references in other parameters and in all variants.
- `reorder-parameters` — partial list (named ones go first in the given order, the rest keep relative order).
- `modify-parameter` — `use`, `denyIncompleteValues`, `availableValues` (single shot replaces the full list).
- `patch-query` `@once` flag — fail when the substring is missing or appears more than once. Multiline replacements are now correct; empty replacement (`old =>`) deletes the substring.
- `add-total` shortcut: `Func`, `Func(expr)`, or just a field name (non-aggregate functions become an identity expression).
- `set-structure`: comma in shorthand for several fields on one level; quotes in `@name=` are stripped on write; reference parameter types serialise with the right `xsi:type`; batch with `;;` is trimmed.
- `add-selection` accepts `@group=Name` and nested `Folder(...)`.
- `modify-filter` / `modify-dataParameter` preserve `Use=false` when the `@off` / `@on` flag is omitted (no longer silently flipped).
- `conditionalAppearance` — `OrGroup`, `DesignTimeValue`, `Format`. `#noFilter` / `#noOrder` / `#noGroup` flags now also work in `add-calculated-field`.

#### `skd-compile` — DSL upgrades

- `@autoDates` emits the canonical БСП pattern (`НачалоПериода` / `КонецПериода`, two date pickers, `useRestriction`). Shortcut requires the period filled (`use=Always` + `denyIncompleteValues=true`).
- Composite reference types: `"type": ["CatalogRef.A", "CatalogRef.B"]`.
- Multilingual titles / presentations: `{ "ru": "...", "en": "..." }`.
- Horizontal cell merge in templates via `>` (mirror of `|` for vertical) — two-level headers without hand-editing XML.
- Parameters: shorthand `[Title]`, array `availableValues`, `denyIncompleteValues`, flag `@hidden` (auto-`useRestriction`), `@valueList` / `valueListAllowed`, `dataParameters: "auto"` (preserves defaults across all parameter kinds).
- Templates: `drilldown` via `DetailsAreaTemplateParameter`, `groupHeaderTemplate`, `groupName`.
- Structure: `"GroupName[Field] > details"` for named groupings; object form `{ "items": [...] }`; `useRestriction` as an object `{ field: true }`.
- Reference values (chart of accounts, catalog, enum, document) in filters and conditional appearance auto-receive predefined presentations. `Format` parameter as multilingual string. `OrGroup` in conditional appearance via `or`.
- `Folder(Title: f1, f2)` in selection — for `SelectedItemFolder` with nested fields.
- Standard period parameter always serialised in canonical form — no diff after first re-save in Configurator.
- External SQL files via `"@path/to/file.sql"`.
- Compact area templates DSL: `rows`, `widths`, `style` with built-in presets (`header` / `data` / `subheader` / `total`), vertical merging, parameters in cells.
- Project-level user style preset at `<projectRoot>/presets/skills/skd/skd-styles.json` (auto-discovered by `skd-compile`).
- `dataSetLinks` accepts both DSL keys (`sourceExpr`, `destExpr`, `source`, `dest`) and XML keys (`sourceExpression`, `destinationExpression`, ...).
- `--from-object`-like discovery: pass a path to a report or processor folder to `skd-info`, the script finds the embedded DCS template by itself; if multiple — it lists them.
- 8.5 platform support across `cf-validate`, `cfe-validate`, `epf-validate`, `skd-validate`.

#### `skd-info`

- Field detail view (`-Mode fields -Name <Field>`) prints kv role parameters (`balanceGroupName`, `balanceType`, `accountTypeExpression`, …) on the Role line.
- Section `query` of `-Mode full` prints external dataset names when no queries exist (no more anonymous "(no query datasets)").

## subsystem-manage.md

### Upstream sync `2026-07-30`

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `subsystem-compile` v1.5 → **v1.9**, `subsystem-edit` v1.2 → **v1.7**, `subsystem-info` v1.0 → **v1.2**, `subsystem-validate` → **v1.2**.

- **Support gate** — `subsystem-compile` / `subsystem-edit` refuse to modify subsystems of a locked typical configuration; see [support-manage.md](support-manage.md).
- **`subsystem-info`** — prints the support state of the subsystem.

### Earlier Additions (upstream `w-2026-05-17`)

The PowerShell scripts under `tools/1c-subsystem-manage/scripts/` were refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights:

- **`subsystem-compile` / `subsystem-edit`** — content of a subsystem accepts Russian and plural prefixes (`Справочник`, `Справочники`, `Catalogs`) and normalises them to the canonical `Catalog`. `subsystem-validate` flags surviving plural forms as an error.
- **Stub-files for child subsystems** are created automatically when the parent declares a child. Previously the `<Subsystems>` reference existed but the file did not — the platform silently ignored it, and stricter loaders started failing.
- Subsystem `objects` accepts `content` as a synonym (and vice versa).
- Validators got the universal improvements described in `role-manage.md` → "Recent Additions" (one-liner output by default, `-Detailed`, folder path auto-resolution).

## template-manage.md

### Local fix `2026-09-13` — object XML paths

`add-template.ps1 -ObjectName` accepts absolute and relative object XML paths and places the template beside the resolved object. Name-only configuration lookup and the EPF `ProcessorName` alias remain supported.

### Upstream sync `2026-07-30`

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `template-add` v1.5 → **v1.10**, `template-remove` → **v1.3**. `template-add` enforces the vendor support gate — it refuses to add a template to a locked object of a typical configuration ([support-manage.md](support-manage.md)). `template-remove` keeps the local hardening (preflight parse, atomic root-XML write, `-DryRun` / `-Force`).

## web-manage.md

### Local fix `2026-10-01` — extension HTTP services are published

`web-publish` (both runtimes) writes `publishExtensionsByDefault="true"` on `httpServices` in `default.vrd`, as the platform's own publication does; without it the HTTP services of the infobase's extensions were not published.

### Upstream sync `2026-07-30`

Scripts refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): `web-publish` v1.2 → **v1.4**; `web-info` / `web-stop` unchanged; `web-unpublish` keeps the local `-DryRun` / `-Force` safety gate.

- **OData is enabled correctly in `default.vrd`** — via the `<standardOdata enable="true"/>` child element instead of the old `enableStandardOdata` attribute, which the platform ignored. Publications that need the standard OData interface actually get it now.
- Platform path resolution follows the `db-*` chain (explicit → `.dev.env` → `.v8-project.json` → auto-detect), locally patched to also accept the version install directory shape used by `.dev.env` `PLATFORM_PATH` (resolves `bin\` for `wsap24.dll`).
