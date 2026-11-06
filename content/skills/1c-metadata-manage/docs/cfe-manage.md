# 1C Extension Manage — Init, Borrow, Diff, Patch, Validate

Comprehensive extension (CFE) management: create scaffold, borrow objects from configuration, analyze changes, generate method interceptors, validate correctness.

---

## 1. Init — Create Extension Scaffold

Use `init` only for an explicitly requested **new** extension. Existing-extension edits, folder moves, renames, updates and restores retain identifiers and borrowed links; they do not start from a new scaffold. Follow `content/rules/extension-workspace.md → Preserve extension identity`, including investigation of unexpected UUID changes before load/apply.

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-cfe-manage/scripts/cfe-init.ps1 -Name "МоёРасширение"
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `Name` | Extension name (required) | — |
| `Synonym` | Synonym | = Name |
| `NamePrefix` | Prefix for own objects | = Name + "_" |
| `OutputDir` | Output directory | `src` |
| `Purpose` | `Patch` / `Customization` / `AddOn` | `Customization` |
| `Version` | Extension version | — |
| `Vendor` | Vendor | — |
| `CompatibilityMode` | Compatibility mode; taken from the base configuration when `ConfigPath` is given | `Version8_3_24` |
| `ConfigPath` | Base configuration sources (auto: `.dev.env` `EXPORT_PATH`) — compatibility mode, interface mode and the default language come from there | — |
| `NoRole` | Without main role | false |

### What Gets Created

```
<OutputDir>/
├── Configuration.xml         # Extension properties
├── Languages/
│   └── <DefaultLanguage>.xml # The base configuration's default language (borrowed)
└── Roles/                    # If not -NoRole
    └── <Prefix>ОсновнаяРоль.xml
```

**Pass `-ConfigPath` whenever the base sources exist.** The borrowed language is the base configuration's `DefaultLanguage` — its name, UUID and `LanguageCode` — not a hard-coded `Русский`: the platform loads an extension whose default language differs but does not apply it («ОсновнойЯзык не совпадает»). Without `ConfigPath` the language is `Русский` with a zero UUID and a warning. On format 2.21 the root also gets `Caption` / `ShortCaption`.

**Preparation**: Before creating, get the base configuration version: `1c-cf-manage info <ConfigPath>`.

---

## 2. Borrow — Borrow Objects from Configuration

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-cfe-manage/scripts/cfe-borrow.ps1 -ExtensionPath src -ConfigPath <config> -Object "Catalog.Контрагенты"
```

| Parameter | Description |
|-----------|-------------|
| `ExtensionPath` | Path to extension directory (required) |
| `ConfigPath` | Path to source configuration (required) |
| `Object` | What to borrow (required), batch via `;;` |
| `Module` | Empty modules for a borrowed **object** item: `ObjectModule`, `ManagerModule`, `RecordSetModule`, `ValueManagerModule` (comma-separated) or `None`. `CommonModule`, `HTTPService` and `WebService` get their single `Module` without it (`None` opts out) |
| `BorrowMainAttribute` | Only with a form in `Object`; the value is required: `Form` / `All` / `Only` — see *Main attribute* below |

Pass `ConfigPath` explicitly; to find it, take `EXPORT_PATH` from `.dev.env` (the configuration XML export of the project). Hand the same path to `cfe-validate -ConfigPath` afterwards.

`Object` formats (Russian names are accepted too: `Документ`, `ОбщаяФорма` for the type, `Форма`, `Реквизит`, `ТабличнаяЧасть`, `Измерение`, `Ресурс`, `РеквизитАдресации`, `ПризнакУчета` for the kind):

| Format | Borrows |
|--------|---------|
| `Type.Name` — `Catalog.X`, `CommonModule.Y`, `Document.Z` | the object, as a shell; every top-level metadata kind |
| `Type.Name.Form.FormName` | a form of the object; the parent object is borrowed first when it is not yet |
| `CommonForm.Name` | a common form **with its content** — the same rules as an object form (below) |
| `Type.Name.<Kind>.<Name>` — `Attribute`, `TabularSection`, `Dimension`, `Resource`, `AddressingAttribute`, `AccountingFlag` | one subobject without a form |
| `Type.Name.TabularSection.TS.Attribute.A` | one tabular-section column (with its section) |

Batch: `"Catalog.X ;; CommonModule.Y ;; Document.Z.Attribute.W"`. Every item is parsed and every subobject is looked up in the source **before anything is written**: an unknown type or kind, a kind the object type does not have (a `Dimension` of a document), or a missing subobject refuses the whole call and leaves the extension unchanged.

Creates XML files with `ObjectBelonging=Adopted` and `ExtendedConfigurationObject`, adds to ChildObjects.

### Re-borrow never rewrites

An object that is already in the extension is **not rewritten** (`Already borrowed: … — XML сохранён без изменений`): its own attributes, borrowed subobjects, registered forms and property states survive. Only what is missing is added — a module asked for with `-Module`, attributes a form needs, columns of an already borrowed tabular section (merged into **that** section, never into another `ChildObjects`). Module files and existing `Module.bsl` files are never overwritten. Re-running a call is safe; it is also the way to add a module to an object borrowed earlier.

### What the borrowed XML looks like (Configurator, formats 2.20 / 2.21)

- **Extension `ChildObjects`** — a new entry goes after the last object of its kind (as Configurator appends a borrowed object), or by name with `NEW_OBJECT_POSITION=byName` in `.dev.env` (the same key `cf-edit` / `meta-compile` use; `.v8-project.json` `newObjectPosition` is only a fallback). A kind not yet present goes to its canonical place; `Subsystem`, `CommandGroup`, `CommonAttribute` and `Language` are never sorted by name.
- **Object shells** — every container kind carries `<ChildObjects/>` (catalogs, documents, data processors, reports, document journals, HTTP / web services, subsystems, …; the source object decides), and `InternalInfo` has the full generated-type set of its kind: `Characteristic` for a chart of characteristic types, `ExtDimensionTypes` for a chart of accounts, the calculation-type sets, `RoutePointRef` for a business process, `Manager` for a sequence, filter criterion, settings storage, integration service or WS reference. Properties that standard fields depend on are carried: `Owners` (the owner objects are borrowed too), `InformationRegisterPeriodicity` / `WriteMode`, `LanguageCode` of a language, the `<Type>` of a defined type (with shells of its member objects).
- **Document** — `Properties` end with an empty `<RegisterRecords/>` (local; the round-trip dump keeps it).
- **Subobject without a form** — `ExtendedConfigurationObject` is the source subobject's uuid; `<Type>` is the source `<Type>` with its own line layout. A bare `TabularSection.TS` comes with its generated types and **no columns** (add own columns with `meta-edit add-ts-attribute`); `TabularSection.TS.Attribute.A` brings the section with that column. The objects named in the type are borrowed as shells; nothing else cascades; object properties (`Hierarchical`, `CodeLength`, …) are not added. A borrowed tabular section of a chart of characteristic types, accounts or calculation types gets a `[WARN]`: the platform rejects own columns there on the database update (business processes and tasks accept them from 8.3.25). Extension code sees the source attributes without borrowing them; borrow them for a form of the extension (an own form sees only borrowed attributes — «Неверный путь к данным»).
- **Modules (`-Module`)** — an empty `Ext/<Kind>.bsl`, and from format 2.19 the matching `<xr:PropertyState>` (`<Kind>` / `Extended`) in the object's `InternalInfo`. Below 2.19 the platform drops that element, so it is not written.
- **Form metadata** `Forms/<Form>.xml` (`CommonForms/<Name>.xml` with a `<CommonForm>` root) — from format 2.19 `InternalInfo` carries the `Form` / `Extended` property state (block below). The uuid of an already borrowed form is kept.
- **Form `Ext/Form.xml`** — the `<Form>` tag and `BaseForm` carry the **extension's** format version (2.21 adds `xmlns:pal`). Every form property is copied into the form and into `BaseForm`, the form-level `CommandSet` with its `ExcludedCommand` list included; `Events`, `Attributes`, `Commands`, `Parameters`, `CommandInterface` and the properties that name a form attribute (`ReportResult`, `DetailsData`, `VariantAppearance`, `GroupList`) are dropped. The form's conditional appearance is copied into `<Attributes>` of both parts. Data paths are stripped the same way in both parts, unless the main attribute is borrowed (below).
- **Element `CommandSet`** (local, ticket 2b392369) — kept as is, with its `ExcludedCommand` list, in both parts **while the element keeps its `DataPath`** (a table on `Объект.Товары` with `-BorrowMainAttribute Form` / `All`; the round-trip dump writes it so). When the binding is stripped (no main attribute, or `Only`) the set is dropped whole: an unbound table has no `Add` / `Copy`, and 8.3.27 rejects it with «Неверное имя команды элемента формы». An empty `CommandSet` is never written.
- **Links** — `ChoiceParameterLinks` and `TypeLink` are not data paths: a readable `Объект.<Attribute>` stays only when that attribute is borrowed with the main attribute (`All`, or `Form` when the form references it). Otherwise the path becomes the source form's link code (`<source attribute id>/0:<uuid>`, a standard-field code such as `1/-2` for a document number, or the source main-attribute id alone when the main attribute is borrowed but the target is not). The borrowed form's own id `1000001` is never written into a link. `Items.<Table>.CurrentData.<Field>` stays readable when the main attribute is borrowed; otherwise it is coded from the source table id and the source column uuid. The same text is written into `BaseForm`. A path that cannot be coded is removed and reported.
- **Pictures** — a picture embedded in an element (`<xr:Abs>File</xr:Abs>`) is copied byte for byte to `Ext/Form/Items/<Element>/<File>` (without it the platform reports «Файл не найден»); an existing file is kept. A `PictureDecoration` loses its `<Picture>` in both parts, as in Configurator. `StdPicture.*` stays. A referenced `CommonPicture` is borrowed, or stripped when the source has none.
- **Form module** — no `Ext/Form/Module.bsl` until the module has code (local; `cfe-patch-method` creates it with the first interceptor). An existing module is kept on re-borrow.
- **Style item on a form** — the form items, the `AutoCommandBar`, the form properties and the conditional appearance are scanned. A referenced `StyleItem` that exists in the source is borrowed. A platform style item (`FormTextColor`, `FieldSelectionBackColor`, `ReportGroup1BackColor`, `ReportGroup2BackColor`, and the rest of the list in `cfe-validate`) stays and is not borrowed. If the style file is missing from the source export, the call fails and lists it: the reference is not removed. The same failure is raised for an object named by a type that is not in the export.
- **Form without `-BorrowMainAttribute`** — data paths are still removed (a skeleton). The call warns that this is not what Configurator writes for «Добавить в расширение»; that result is `-BorrowMainAttribute Form`.
- **`AdditionalColumns`** — columns are copied, their `<FunctionalOptions>` are not.
- **Dynamic list** — the object of a borrowed list's main table is borrowed as a shell. When the list's query (or, without a manual query, its field paths) uses something the extension does not have, the list's field paths get a `~` prefix in both parts, which the platform resolves after the extension is applied; a list that resolves in the extension gets none.

`InternalInfo` of a borrowed form's metadata:

```xml
<InternalInfo>
	<xr:PropertyState>
		<xr:Property>Form</xr:Property>
		<xr:State>Extended</xr:State>
	</xr:PropertyState>
</InternalInfo>
```

### Main attribute — `-BorrowMainAttribute`

The form's **own** main attribute is copied whole from the source form — `Объект` (`<Kind>Object`, with `SavedData` / `UseAlways` / `Columns`) on an object form, `Список` (`DynamicList` with its settings) on a list form, `Запись` (`RecordManager`) on a register record form, and so on; only its id becomes `1000001`. Data paths rooted at it are kept. The attributes are borrowed from the object **in the main attribute's type**, which is usually the form's owner: a data processor form whose main attribute is `DocumentObject.X` borrows `X` and its attributes. When that object is missing from the source configuration, the call is refused before anything is written.

| Value | Main attribute | Object attributes borrowed with it | Data paths from it |
|-------|----------------|------------------------------------|--------------------|
| *(not given)* | — | none | stripped |
| `Form` | added | those the form references: data paths, `<Field>` references, `AdditionalColumns`, the words of a dynamic list's query text; a tabular section keeps only the columns a path names (`Объект.Товары.Колонка`, `Объект.Товары.CurrentData.Колонка`, `Items.<таблица>.CurrentData.Колонка`); a section named without a column still comes whole; deep paths borrow each target object with the sub-attribute; a composite type of references only becomes `cfg:AnyIBRef` and those objects are not borrowed; other type objects as shells | kept |
| `All` | added | all attributes and tabular sections (deep paths as in `Form`), type objects as shells | kept |
| `Only` | added, without `UseAlways` / `Columns` | none; the main-attribute object is borrowed as a shell when it is not the form's owner (local) | stripped, in the form and in `BaseForm` alike |

With `Form` / `All` the object shell also gets the properties its standard fields need: `Hierarchical`, `CodeLength`, `DescriptionLength`, `CodeType`, `CodeAllowedLength`, `NumberType`, `NumberLength`, `NumberAllowedLength`, and for a chart of accounts `ExtDimensionTypes` / `MaxExtDimensionCount` with the ext-dimension flags. `NumberPeriodicity` is **not** carried: the load passes, but `/UpdateDBCfg` then demands a `<Numerator/>` («отключать контролируемость свойства "Нумератор" недопустимо»). An attribute already in the extension — own or borrowed earlier — is never added twice; a tabular section borrowed earlier without the form gets only the columns the form needs.

A **common form** has no owner: with `-BorrowMainAttribute` the object comes from the main attribute's type — `<Kind>Object.X` / `<Kind>RecordManager.X` → `X`; `DynamicList` → the object of its `MainTable`; `ConstantsSet` → the constants the form references (with their types; their type objects as shells); a primitive or unnamed type → only the attribute itself.

`Only` together with `Type.Name.Attribute.X` items borrows the main attribute and exactly the attributes you name, without the cascade; add the bindings you need to the form afterwards.

For an already borrowed object, preserve its existing identifier and base-object link; do not recreate it to move/rename the source tree or to hide a mapping mismatch. Resolve the intended base and target before any change to the borrowing relationship.

---

## 3. Diff — Analyze Extension Changes

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-cfe-manage/scripts/cfe-diff.ps1 -ExtensionPath src -ConfigPath <config> -Mode A
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ExtensionPath` | Path to extension (required) | — |
| `ConfigPath` | Path to configuration (required) | — |
| `Mode` | `A` (overview) / `B` (transfer check) | `A` |

**Mode A** — overview: For each object shows `[BORROWED]` (interceptors, own attributes/TS/forms) or `[OWN]` (counts).

**Mode B** — transfer check: For each `&ИзменениеИКонтроль`, extracts `#Вставка`/`#КонецВставки` blocks and searches for them in the configuration module. Statuses: `[TRANSFERRED]`, `[NOT_TRANSFERRED]`, `[NEEDS_REVIEW]`.

Both modes cover every borrowable kind, including `HTTPService`, `WebService`, `XDTOPackage`, `Style`, `WSReference` and `Bot`, the interceptors in common-form modules, and English BSL keywords.

---

## 4. Patch — Generate Method Interceptor

Reads the original method **from the source configuration** and generates the `.bsl` interceptor of the borrowed object: correct context directive, full signature, framing preprocessor instructions and regions. For `ModificationAndControl` it copies the whole original body. Creates the module file, appends to an existing one, or re-syncs an already intercepted method.

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-cfe-manage/scripts/cfe-patch-method.ps1 -ExtensionPath src\cfe\ИмяРасширения -ConfigPath src\cf -ModulePath "Catalog.Контрагенты.ObjectModule" -MethodName "ПриЗаписи" -InterceptorType Before
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ExtensionPath` | Path to extension (required) | — |
| `ConfigPath` | Source configuration sources — the original method is read from there | required, unless `ModulePath` is a file path |
| `ModulePath` | Logical name (`Type.Name.Module`) **or** a path to a source `.bsl` module | required for generation |
| `MethodName` | Method to intercept | required for generation |
| `InterceptorType` | `Before` / `After` / `Instead` / `ModificationAndControl` | required for generation |
| `Check` | Report drift of controlled methods (report only) | — |
| `Actualize` | Re-sync drifted controlled methods | — |

`NamePrefix` is taken from the extension's `Configuration.xml`. **Auto-detecting `ConfigPath`**: take `EXPORT_PATH` from `.dev.env` — the configuration XML export directory of this project (empty = repository root); ask the user only when it is not set and no source dump is discoverable. When `ModulePath` is a path to the source `.bsl`, `-ConfigPath` is unnecessary — the original is read from that file and the extension module path is derived automatically.

### ModulePath Format

| ModulePath | File |
|------------|------|
| `Catalog.X.ObjectModule` | `Catalogs/X/Ext/ObjectModule.bsl` |
| `Catalog.X.ManagerModule` | `Catalogs/X/Ext/ManagerModule.bsl` |
| `Catalog.X.Form.Y` | `Catalogs/X/Forms/Y/Ext/Form/Module.bsl` |
| `CommonForm.X` | `CommonForms/X/Ext/Form/Module.bsl` (borrow it first with `cfe-borrow -Object CommonForm.X`) |
| `CommonModule.X` | `CommonModules/X/Ext/Module.bsl` |

Same shape for `Document`, `Report`, `DataProcessor`, `InformationRegister` and other types. A borrowed form has no `Module.bsl` until the first interceptor: `cfe-patch-method` creates it.

Modules written in English BSL (`Procedure`, `&AtServer`, `#Insert` / `#EndInsert`, `&ChangeAndValidate`, …) are read as such, and the interceptor is emitted in the spelling the module uses.

### Interceptor Types

| Type | Decorator | Purpose | Applies to |
|------|-----------|---------|------------|
| `Before` | `&Перед` | Code before the original method call | procedures |
| `After` | `&После` | Code after the original method call | procedures |
| `Instead` | `&Вместо` | Replaces the method; body scaffolds `ПродолжитьВызов(...)` | procedures and functions |
| `ModificationAndControl` | `&ИзменениеИКонтроль` | Copy of the original body, edited with `#Вставка` / `#Удаление` markers | procedures and functions |

Re-running `Before` / `After` / `Instead` on an already intercepted method does not create a duplicate (`[ПРОПУЩЕН]`).

### `#Вставка` / `#Удаление` markers (ModificationAndControl)

`&ИзменениеИКонтроль` inserts a **copy of the original body**; every change you make must be marked, because that is how the platform tells your edit from the untouched original:

- **Adding code** → wrap it in `#Вставка` … `#КонецВставки`.
- **Removing original code** → wrap the lines in `#Удаление` … `#КонецУдаления` **and keep the lines between the markers** — the platform compares them against the original.
- **Replacing** → `#Удаление` old `#КонецУдаления` immediately followed by `#Вставка` new `#КонецВставки`.

Rules: markers go on their **own line at column 0** (no indentation), even inside indented code or query text (`|…`); **unmarked lines must match the original verbatim** — that is the "control" part; touch only your own inserts and deletions.

### Drift control — `-Check` / `-Actualize`

When the vendor changes the original, an `&ИзменениеИКонтроль` interceptor silently desynchronizes — the unmarked context no longer matches. The platform says nothing about it on load, so check it yourself, **routinely after every vendor update**:

```powershell
# Report drift across all controlled methods of the extension (exit 1 on drift/conflict)
... cfe-patch-method.ps1 -ExtensionPath src\cfe\ИмяРасширения -ConfigPath src\cf -Check

# Re-apply the edits onto the new original, extension-wide
... cfe-patch-method.ps1 -ExtensionPath src\cfe\ИмяРасширения -ConfigPath src\cf -Actualize
```

Narrow the scope with `-ModulePath` (one module) or `-ModulePath` + `-MethodName` (one method).

`[АКТУАЛЕН]` follows the platform's own comparison rule (measured on 8.3.24 / 8.3.27): every line is trimmed and blank lines are ignored, everything else is compared byte for byte and **case-sensitively** — whitespace between tokens, string literals and comments count. A changed parameter list of the original is drift too. A marker line may carry a trailing comment (`#Вставка // ТЗ-142`); `-Actualize` writes the marker lines back as they were, comment included. `CommonForm.X` modules are covered like any other.

| Status | Meaning |
|--------|---------|
| `[АКТУАЛЕН]` | Original unchanged, nothing to do |
| `[АКТУАЛИЗИРОВАН]` | Body updated against the new original, edits preserved |
| `[АКТУАЛИЗИРОВАН-ЧАСТИЧНО]` | Some edits could not be placed (anchor changed). They are **not lost** — marked `// [РЕСИНК-КОНФЛИКТ]` in the module; the output gives the merge workspace path (start at `index.md`, then each `conflict.md`, place the blocks manually) |
| `[ПЕРЕНЕСЕНО В ОСНОВНУЮ]` | The edit is already in the new original (vendor adopted it) — removed from the body as obsolete. If that happens to every edit of a method, the interceptor can be deleted. Does not fail `-Check` |

**Prerequisite**: Object must be borrowed first (`cfe-borrow`); the source configuration must be reachable via `-ConfigPath`.

---

## 5. Validate — Check Extension Correctness

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-cfe-manage/scripts/cfe-validate.ps1 -ExtensionPath src\cfe\ИмяРасширения -ConfigPath src\cf
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ExtensionPath` | Extension directory or its `Configuration.xml` (required, positional) | — |
| `ConfigPath` | Source configuration the objects were borrowed from (auto: `.dev.env` `EXPORT_PATH`) — enables check 18 | — |
| `Detailed` | Print every check, the passing ones too | — |
| `MaxErrors` | Stop after N errors (the summary says so) | 30 |
| `OutFile` | Also write the report to a file | — |

**Always pass `-ConfigPath` when the source sources are reachable.** Without it check 18 is skipped with an `[INFO]` line, and an extension that the platform will load but not apply (wrong UUID link, a name differing only in case, another default language) passes validation.

### Checks (19 steps)

| # | Check | Severity |
|---|-------|----------|
| 1 | XML well-formedness, MetaDataObject/Configuration, version | ERROR |
| 2 | InternalInfo: 7 ContainedObject, valid ClassId | ERROR |
| 3 | Extension properties: ObjectBelonging=Adopted, Name, Purpose, NamePrefix, KeepMapping | ERROR |
| 4 | Enum values: CompatibilityMode, DefaultRunMode, ScriptVariant, InterfaceCompatibilityMode | ERROR |
| 5 | ChildObjects: valid types, no duplicates, canonical type order | ERROR/WARN |
| 6 | DefaultLanguage references Language in ChildObjects | ERROR |
| 7 | Language files exist | WARN |
| 8 | Object directories exist | WARN |
| 9 | Borrowed objects: ObjectBelonging=Adopted, a valid ExtendedConfigurationObject UUID, the **complete GeneratedType set** of the kind (missing categories — ERROR). An own object of a kind the platform will not add to the database — ERROR (WARN when only older platforms refuse it). Borrowed elements without any ExtendedConfigurationObject are summarized in one WARN: the platform binds them by name, so a recreated source object is picked up silently | ERROR/WARN |
| 10 | Borrowed sub-items: attributes, tabular sections with `TabularSection` + `TabularSectionRow` generated types, enum values, form metadata files. An own subobject in a borrowed object of a kind the platform refuses on the database update — ERROR (business process / task below 8.3.25 — WARN) | ERROR/WARN |
| 11 | Forms (object and common): ExtendedConfigurationObject, FormType, `Ext/Form.xml`, `BaseForm` version. A missing `Module.bsl` is reported only for an own form (local: a borrowed form has none until its first interceptor) | ERROR/WARN |
| 12 | Form dependencies not borrowed: a `CommonPicture` or a `StyleItem` outside the platform style list — ERROR (local), the platform refuses to load the form; `AdditionalColumns` of a tabular section that is neither borrowed nor own — ERROR; an enum or enum value — WARN | ERROR/WARN |
| 13 | `TypeLink` with a human-readable `Items.*` path (`cfe-borrow` rewrites or removes these) | WARN |
| 14 | Data paths of every extension form, borrowed and own, against the object **as described in the extension**: the path root must be an attribute declared in the form; the main attribute's object must be in the extension; each attribute, tabular section and column must be borrowed or own (standard fields by the main attribute's type; reference paths continue on the target object; settings composer and defined-type paths included). `BaseForm` is not checked — the platform resolves it against the configuration | ERROR |
| 15 | A role in `DefaultRoles` grants rights on a borrowed object («Назначение прав доступа на заимствованные объекты основными ролями в расширениях недопустимо») | ERROR |
| 16 | From format 2.19: a borrowed object's module file and its `<xr:PropertyState>` mark agree | WARN |
| 17 | Format version: an object's parts (descriptor, `Form.xml`, `BaseForm`) stamped differently — ERROR, the platform refuses the load; a part differing from the extension's version — WARN | ERROR/WARN |
| 18 | With `-ConfigPath`: the default language matches the source; every borrowed object and subobject exists in the source with the same name case and the same UUID (`ExtendedConfigurationObject`); a zero UUID — WARN; an own subobject named like an unborrowed source subobject — ERROR | ERROR/WARN |
| 19 | References to objects that are not in the extension. A **type** (attribute, column, constant, dimension, command parameter, form attribute, borrowed defined-type content) — WARN: below 8.3.25 «Неизвестное имя типа», from 8.3.25 allowed. An **object reference** (owners, register records, input on basis, journal, subsystem content, chart of accounts of a register, …) — ERROR: from 8.3.25 it loads, but the link is empty at run time. Role rights on such an object — ERROR, the platform drops them. The type of an own defined type, a subscription source, ext-dimension types, a borrowed defined type with such content in an own object — ERROR, the extension never loads | ERROR/WARN |

Exit code: 0 = OK, 1 = errors.

For a complete hierarchical extension dump, additionally run
`tools/1c-cf-manage/scripts/dump-validate.ps1 -ConfigPath "<extension-directory>"`.
It checks the extension's own file inventory, nested subsystems, versions,
selected references and optional `ConfigDumpInfo.xml`. JSON output and exact
coverage: [Complete dump integrity](cf-manage.md#complete-dump-integrity).
This check does not compare the extension with its base configuration.

### What `cfe-validate` cannot see — the platform check is a separate step

All checks read **source**: XML shape, ClassIds, ChildObjects ordering, adopted-object markers. They are silent about the one failure mode that actually breaks a base — an interceptor whose target method no longer exists in the main configuration. `&Вместо ПриЗаписи` against a method the vendor renamed is perfectly valid XML and perfectly valid BSL; the platform rejects it only at apply time, and an `&После` in the same position may just stop firing with no error at all.

Before loading an extension into any infobase, run the platform's own ladder — canon `content/rules/designer-batch-checks.md`:

```
/CheckModules -ThinClient -Server -ExternalConnection -Extension <Name>
/CheckCanApplyConfigurationExtensions -Extension <Name>
/CheckConfig -ConfigLogIntegrity -IncorrectReferences ... -Extension <Name>
```

Read the verdict from three signals (process exit code, `/DumpResult`, `/Out` diagnostics) and classify the platform's success phrases before its error stems — `Ошибок не обнаружено` contains the word `ошибок`. `Не найден метод` in the log is a failure even at exit code 0.

For a `&ИзменениеИКонтроль`-heavy extension, `-Check` (section 4) and the applicability check answer related questions from opposite ends: drift detection names the *method* whose original moved, the platform names the *error*. Run `-Check` first — it is cheaper and its output is more actionable.

Record the exact checked combination and evidence in the existing extension README or delivery description (`content/rules/extension-workspace.md → Checked compatibility`). Source/drift validation is not evidence of an applied or tested infobase. Reuse the authorized `/update1cbase` load → checks → apply sequence and any executed scenarios; record missing checks without widening the workflow.

### Backup and rollback before replacing an existing extension

Loading over an existing extension is a replacement with no platform-side undo. Dump both forms first — `/DumpCfg -Extension <Name>` (editable) and `/DumpDBCfg -Extension <Name>` (database, what running sessions execute) — and recover with `/RollbackCfg -Extension <Name>` before the DB update, or by reloading the saved `.cfe` after it. **Never delete a pre-existing extension as a rollback**: deletion drops its own objects and every mapping along with your change. Details — `content/rules/designer-batch-checks.md → Extension apply and rollback`.

---

## Typical Extension Workflow

The `init` step below is for a new extension only; an existing target starts from its current sources/backup and preserves its identity. Recheck root/graph mappings and evidence after a move, rename or restore.

```
1c-cf-manage info <config>          — get base config version/compatibility
1c-cfe-manage init                  — create extension scaffold
1c-cfe-manage borrow               — borrow objects to modify
1c-cfe-manage patch                 — generate interceptors
1c-cfe-manage validate -ConfigPath   — check correctness (source-level, against the source config)
1c-cfe-manage diff -Mode A          — review changes overview
1c-cfe-manage diff -Mode B          — check transfer status
1c-cfe-manage patch -Check          — drift against the vendor original
   ↓ before loading into any infobase
/CheckModules → /CheckCanApplyConfigurationExtensions → /CheckConfig
                                    — platform-level ladder, designer-batch-checks.md
```

Scripts vendored from Nikolay-Shirokov/cc-1c-skills; sync history — `docs/CHANGELOG.md`.
