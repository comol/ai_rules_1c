# 1C SKD Manage — Compile, Edit, Info, Validate, Decompile

Comprehensive Data Composition Schema (DCS/SKD) management: create from JSON, modify existing schemas, analyze structure, validate correctness (including the platform XSD), decompile to a DSL draft.

> The **complete JSON DSL grammar** for `skd-compile` — data sets, fields, resources, calculated fields, parameters, settings, filters, conditional appearance, nested schemas — is vendored verbatim as [`skd-dsl-spec.md`](../tools/1c-skd-compile/skd-dsl-spec.md) (Russian, upstream original). This document is the working guide; read the spec when a key is missing here or the compiler rejects a construct.

---
## 1. Compile — Create from JSON

Takes a JSON definition of a Data Composition Schema and generates Template.xml (DataCompositionSchema).

### Parameters and Command

| Parameter | Description |
|-----------|-------------|
| `DefinitionFile` | Path to JSON definition file (mutually exclusive with Value) |
| `Value` | JSON string with DCS definition (mutually exclusive with DefinitionFile) |
| `OutputPath` | Path to output Template.xml |

```powershell
# From file
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-skd-compile/scripts/skd-compile.ps1 -DefinitionFile "<json>" -OutputPath "<Template.xml>"

# From string (no intermediate file)
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-skd-compile/scripts/skd-compile.ps1 -Value '<json-string>' -OutputPath "<Template.xml>"
```

### JSON DSL — Quick Reference

Full specification is embedded below.

#### Root Structure

```json
{
  "dataSets": [...],
  "calculatedFields": [...],
  "totalFields": [...],
  "parameters": [...],
  "dataSetLinks": [...],
  "settingsVariants": [...]
}
```

Defaults: `dataSources` → auto `ИсточникДанных1/Local`. Without `settingsVariants` the compiler builds the variant "Основной" so the report shows data: `selection` = the declared fields of the data sets and the calculated fields (minus `#noField`, folders' Auto, disabled fields), `structure` = detail records; it prints an `[INFO]` line naming the chosen fields. A variant that has `selection` but no `structure` gets detail records. A `[WARN]` after the summary means the report will be empty or show only grouping columns — no fields declared, all excluded, or a `structure` without `selection`: add `settings.selection`. Keys given explicitly, even empty, are never touched.

#### Data Sets

Type by key: `query` → DataSetQuery, `objectName` → DataSetObject, `items` → DataSetUnion.

```json
{ "name": "Продажи", "query": "ВЫБРАТЬ ...", "fields": [...] }
```

Query data-set flags, both on by default — set them only when the task needs it:
- `"autoFillFields": false` — the platform stops marking up the query: a field is available only if the query text marks it as `{ВЫБРАТЬ …}`, a filter reaches the query only where `{ГДЕ …}` (or a braced condition in virtual-table parameters) gives it a place, otherwise it applies to the query result.
- `"useQueryGroupIfPossible": false` — no `СГРУППИРОВАТЬ ПО` added from the settings groupings: the query reads detail rows, the composition computes totals.

**Field aliases.** When a data-set field's value differs from the same-named field of its source (a temp-table column, a virtual-table dimension), give it a different name — otherwise a settings filter is applied to the source field, not to the data-set field. An explicit `{ГДЕ}` fixes it only with `autoFillFields: false`.

#### Fields — Shorthand

```
"Наименование"                              — just name
"Количество: decimal(15,2)"                  — name + type
"Организация: CatalogRef.Организации @dimension"  — + role
"Служебное: string #noFilter #noOrder"       — + restrictions
```

Types: `string`, `string(N)`, `decimal(D,F)`, `boolean`, `date`, `dateTime`, `CatalogRef.X`, `DocumentRef.X`, `EnumRef.X`, `StandardPeriod`. Reference types are emitted with inline namespace `d5p1:` (`http://v8.1c.ru/8.1/data/enterprise/current-config`). Building an EPF with reference types requires a database with the corresponding configuration.

**Type synonyms** (Russian and alternatives): `число` = decimal, `строка` = string, `булево` = boolean, `дата` = date, `датаВремя` = dateTime, `СтандартныйПериод` = StandardPeriod, `СправочникСсылка.X` = CatalogRef.X, `ДокументСсылка.X` = DocumentRef.X, `int`/`number` = decimal, `bool` = boolean. Case-insensitive.

Roles: `@dimension`, `@account`, `@balance`, `@period`.
Restrictions: `#noField`, `#noFilter`, `#noGroup`, `#noOrder`. In the object form of a data-set or calculated field the same flags go in `restrict` or `useRestriction` — an object (`{ "field": true, "group": true }`), an array or a flag string. Object-form fields also take `availableValues` (`"value": null` = empty value).

Element order inside every emitted node follows the platform XSD (calculated field: `title`, `useRestriction`, `appearance`, `availableValue`, `valueType` last); a schema in the wrong order is not read by XDTO ("Нарушен порядок следования значений свойств").

#### Totals (shorthand)

```json
"totalFields": ["Количество: Сумма", "Стоимость: Сумма(Кол * Цена)"]
```

#### Parameters (shorthand + @autoDates)

```json
"parameters": [
  "Период: StandardPeriod = LastMonth @autoDates"
]
```

`@autoDates` — automatically generates `ДатаНачала` and `ДатаОкончания` parameters with expressions `&Период.ДатаНачала` / `&Период.ДатаОкончания` and `availableAsField=false`. Replaces 5 lines with 1.

#### Filters — Shorthand

```json
"filter": [
  "Организация = _ @off @user",
  "Дата >= 2024-01-01T00:00:00",
  "Статус filled"
]
```

Format: `"Field operator value @flags"`. Value `_` = empty (placeholder). Flags: `@off` (use=false), `@user` (userSettingID=auto), `@quickAccess`, `@normal`, `@inaccessible`.

#### Structure — String Shorthand

```json
"structure": "Организация > details"
"structure": "Организация > Номенклатура > details"
```

`>` separates grouping levels. `details` (or `детали`) = detail records.

#### Settings Variants

```json
"settingsVariants": [{
  "name": "Основной",
  "settings": {
    "selection": ["Номенклатура", "Количество", "Auto"],
    "filter": ["Организация = _ @off @user"],
    "order": ["Количество desc", "Auto"],
    "conditionalAppearance": [
      {
        "filter": ["Просрочено = true"],
        "appearance": { "ЦветТекста": "style:ПросроченныеДанныеЦвет" },
        "presentation": "Highlight overdue",
        "viewMode": "Normal",
        "userSettingID": "auto"
      }
    ],
    "outputParameters": { "Заголовок": "My Report" },
    "dataParameters": ["Период = LastMonth @user"],
    "structure": "Организация > details"
  }
}]
```

`dataParameters` items: `"Имя [= значение] @flags"`; several values separated by commas form a list (quote a value that contains a comma) — `"Статусы = Перечисление.СтатусыЗаказов.Новый, Перечисление.СтатусыЗаказов.ВРаботе @user"`; object form `{ "parameter": "Суммы", "value": [100, 200] }`. Each list item becomes its own `<dcscor:value>` (a single glued `"A B C"` string makes `В (&Параметр)` find nothing). Without `valueType` the value takes the type declared by the schema parameter, so numbers stay `xs:decimal`; references to predefined values become `dcscor:DesignTimeValue`. `"dataParameters": "auto"` lists every non-hidden parameter with a `userSettingID`; defaults (lists included) stay active, parameters without a default are switched off.

### Examples

#### Minimal

```json
{
  "dataSets": [{
    "query": "ВЫБРАТЬ Номенклатура.Наименование КАК Наименование ИЗ Справочник.Номенклатура КАК Номенклатура",
    "fields": ["Наименование"]
  }]
}
```

#### With Resources, Parameters, and @autoDates

```json
{
  "dataSets": [{
    "query": "ВЫБРАТЬ Продажи.Номенклатура, Продажи.Количество, Продажи.Сумма ИЗ РегистрНакопления.Продажи КАК Продажи",
    "fields": ["Номенклатура: СправочникСсылка.Номенклатура @dimension", "Количество: число(15,3)", "Сумма: число(15,2)"]
  }],
  "totalFields": ["Количество: Сумма", "Сумма: Сумма"],
  "parameters": ["Период: СтандартныйПериод = LastMonth @autoDates"],
  "settingsVariants": [{
    "name": "Основной",
    "settings": {
      "selection": ["Номенклатура", "Количество", "Сумма", "Auto"],
      "filter": ["Организация = _ @off @user"],
      "dataParameters": ["Период = LastMonth @user"],
      "structure": "Организация > details"
    }
  }]
}
```

---
## 2. Edit — Modify Existing Schema

Atomic modification operations on an existing Data Composition Schema: add, remove, and modify fields, totals, filters, parameters, variant settings, structure management, query replacement.

### Parameters and Command

| Parameter | Description |
|-----------|-------------|
| `TemplatePath` | Path to Template.xml (or folder — auto-completes to Ext/Template.xml) |
| `Operation` | Operation (see list below) |
| `Value` | Operation value (shorthand string or query text) |
| `DataSet` | (opt.) Data set name (default: first) |
| `Variant` | (opt.) Settings variant name (default: first) |
| `NoSelection` | (opt.) Don't add field to variant selection |

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-skd-edit/scripts/skd-edit.ps1 -TemplatePath "<path>" -Operation <op> -Value "<value>"
```

### Batch Mode

Multiple values in one call via `;;` separator:

```powershell
-Operation add-field -Value "Цена: decimal(15,2) ;; Количество: decimal(15,3) ;; Сумма: decimal(15,2)"
```

Works for all operations except `set-query`, `set-structure`, and `add-dataSet`.

### Operations

#### add-field — Add Field to Data Set

Shorthand: `"Name [Title]: type @role #restriction"`.

#### add-total — Add Total

```
"Цена: Среднее"
"Стоимость: Сумма(Кол * Цена)"
```

#### add-calculated-field — Add Calculated Field

Shorthand: `"Name [Title]: type = Expression"`.

#### add-parameter — Add Parameter

```
"Период: StandardPeriod = LastMonth @autoDates"
```

#### add-filter — Add Filter to Variant

Shorthand: `"Field operator value @flags"`. Flags: `@off`, `@user`, `@quickAccess`, `@normal`, `@inaccessible`.

#### add-dataParameter — Add Data Parameter to Variant

Shorthand: `"Name [= value] @flags"`. Several values separated by commas form a list, one `<dcscor:value>` each (quote a value that contains a comma); predefined-value references are written as `dcscor:DesignTimeValue`.

#### add-order — Add Sort Order

Shorthand: `"Field [desc]"`. Default is asc. `Auto` — auto element.

#### add-selection — Add Selection Element

#### add-dataSetLink — Add Data Set Link

Shorthand: `"Source > Target on SrcExpr = DstExpr [param Name]"`.

#### add-dataSet — Add Data Set

Shorthand: `"Name: QUERY_TEXT"` or `"QUERY_TEXT"` (auto-name). Does not support batch mode.

#### add-variant — Add Settings Variant

Shorthand: `"Name [Presentation]"`.

#### add-conditionalAppearance — Add Conditional Appearance

Shorthand: `"Parameter = value [when condition] [for Field1, Field2]"`.

#### set-query — Replace Query Text

Value = full query text. Does not support batch mode.

#### set-outputParameter — Set Output Parameter

```
"Заголовок = My Report"
```

#### set-structure — Set Variant Structure

Shorthand: `"Field1 > Field2 > details"`. Replaces entire structure. Does not support batch mode.

#### modify-field — Modify Existing Field

Same shorthand as `add-field`. Finds by dataPath, merges properties.

#### modify-filter / modify-dataParameter — Modify Existing Filter/Parameter

Same shorthand as the `add-*` operation. `modify-dataParameter` replaces every previous value of a list; new values, `use`, `viewMode` and `userSettingID` are placed in schema order (`use`, `parameter`, `value`…, `viewMode`, `userSettingID`; a filter: `use`, `left`, `comparisonType`, `right`, `viewMode`, `userSettingID`). All `skd-edit` insertions — settings, structure, field roles — go to their XSD position, not to the end of the element: an element after `userSettingID` fails XDTO loading ("Проверка свойства 'value'").

#### remove-* and clear-*

| Operation | Value | Action |
|-----------|-------|--------|
| `remove-field` | dataPath | Remove field from set + variant selection |
| `remove-total` | dataPath | Remove total |
| `remove-calculated-field` | dataPath | Remove calculated field + selection |
| `remove-parameter` | name | Remove parameter |
| `remove-filter` | field | Remove first filter with this field |
| `clear-selection` | `*` | Clear all selection elements |
| `clear-order` | `*` | Clear all order elements |
| `clear-filter` | `*` | Clear all filter elements |

---
## 3. Info — Analyze Structure

Reads a Template.xml Data Composition Schema (DCS) and outputs a compact summary. Replaces the need to read thousands of XML lines.

### Parameters and Command

| Parameter | Description |
|-----------|-------------|
| `TemplatePath` | Path to Template.xml or template directory (auto-resolves to `Ext/Template.xml`) |
| `Mode` | Analysis mode (default `overview`) |
| `Name` | Name of data set (query), field (fields/calculated/resources/trace), variant (variant), or grouping/field (templates) |
| `Batch` | Query batch number, 0 = all (query mode only) |
| `Limit` / `Offset` | Pagination (default 150 lines) |
| `OutFile` | Write result to file (UTF-8 BOM) |

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-skd-info/scripts/skd-info.ps1 -TemplatePath "<path>"
```

With mode specified:
```powershell
... -Mode query -Name DataSetName
... -Mode fields -Name FieldName
... -Mode trace -Name "Field Title"
... -Mode variant -Name 1
```

### Modes

| Mode | Without `-Name` | With `-Name` |
|------|-----------------|--------------|
| `overview` | Navigation map of the schema + Next hints | — |
| `query` | — | Query text of the data set (with batch index) |
| `fields` | Map: field names by data set | Field detail: set, type, role, format |
| `links` | All data set links | — |
| `calculated` | Map: calculated field names | Expression + title + restrictions |
| `resources` | Map: resource field names (`*` = group formulas) | Aggregation formulas by groupings |
| `params` | Parameters table: type, value, visibility | — |
| `variant` | Variant list | Grouping structure + filters + `DataParams` (a list value as `[...]`) + output |
| `templates` | Template binding map (field/group) | Template content: rows, cells, expressions |
| `trace` | — | Full chain: data set → calculation → resource |
| `full` | Full summary: overview + query + fields + resources + params + variant | — |

Pattern: without `-Name` — map/index, with `-Name` — detail of a specific element. `full` mode combines 6 key modes in one call.

Detailed output examples for each mode are in `skills/1c-metadata-manage/tools/1c-skd-info/modes-reference.md`.

---
## 4. Validate — Check Correctness

Checks structural correctness of a Template.xml Data Composition Schema. Detects format errors, broken references, duplicate names; with the platform XSD schemas present, also element order, types and values.

### Parameters and Command

| Parameter | Description |
|-----------|-------------|
| `TemplatePath` (alias `Path`) | Path to Template.xml, template directory or template descriptor (auto-resolves to `Ext/Template.xml`) |
| `Detailed` | Print every check, including passed ones |
| `MaxErrors` | Max errors before stopping (default 20) |
| `OutFile` | Write result to file |

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-skd-validate/scripts/skd-validate.ps1 -TemplatePath "<path>"
```

### Checks (~30)

| Group | What Is Checked |
|-------|-----------------|
| **Root** | XML parse, root element `DataCompositionSchema`, default namespace, ns prefixes |
| **DataSource** | Presence, name not empty, type valid (Local/External), name uniqueness |
| **DataSet** | Presence, xsi:type valid, name not empty, uniqueness, dataSource reference, query not empty |
| **Fields** | dataPath not empty, field not empty, dataPath uniqueness per set |
| **Links** | source/dest reference existing sets, expressions not empty |
| **CalcFields** | dataPath not empty, expression not empty, uniqueness, collisions with set fields |
| **TotalFields** | dataPath not empty, expression not empty |
| **Parameters** | name not empty, uniqueness |
| **Templates** | name not empty, uniqueness |
| **GroupTemplates** | template references existing template, templateType valid |
| **Variants** | Presence, name not empty, settings element present |
| **Settings** | selection/filter/order reference known fields, comparisonType valid, structure items typed |
| **Values** | `xs:boolean` only `true` / `false` / `1` / `0` (checked without schemas) |
| **XSD** | Order, types and enum values against the platform XSD of the dump's format version (see below) |

### XSD Check

The template is checked against the XSD of its dump's format version — the `version` of the nearest `Configuration.xml` (or of the external report root) above it. Schema directory: `.dev.env` `V8_XSD_PATH` (relative to the `.dev.env` directory), else `.v8-project.json` `xsdPath`, else `.v8-xsd` next to `.dev.env` (`content/rules/dev-standards-env.md`). Fill it with `v8-xsd-fetch` (section 6).

- **No schemas** — the summary ends with `XSD not checked: <reason>` (`no schemas in '<dir>'`, `template outside a dump`). That is not "everything checked": when the platform reports "Нарушен порядок следования значений свойств" or XDTO conversion errors, fetch the schemas and run again.
- **Exact version** — violations are `[ERROR]`: `XSD <ver>, line N: <parent>/<element>: <hint>`. `must come before <X>` — move the element right before `<X>`, content unchanged; `duplicate` — delete the repeat; `not allowed in <P>` — the element does not belong there; otherwise the invalid value is named.
- **Only a newer version present** — `[WARN]` with `(no schemas for <ver>)`: a pointer, not a verdict. No version ≥ the dump's — `[WARN] XSD: no schemas for format <ver>`.
- A violation in a template that `skd-compile` / `skd-edit` has just written is a tool defect — report it to the user instead of hand-fixing the XML.

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | No errors (warnings may exist) |
| 1 | Errors found |

---
## 5. Decompile — Extract JSON DSL from Template.xml (draft)

Reverse of `1c-skd-compile`: reads an existing `Template.xml` (DataCompositionSchema) and reconstructs the JSON DSL consumed by `1c-skd-compile`. Use it to capture an existing report's schema as editable DSL, diff two schemas, or bootstrap a new schema from a working sample.

> **The output is a draft, not a lossless representation.** Use it to scaffold a new report from a sample or for structural refactoring; for point edits of an existing report use `1c-skd-edit` (a decompile → compile cycle rewrites the whole template). The round-trip keeps the "Основной" variant (its `selection` / `structure` are always written, `[]` when absent), `autoFillFields` / `useQueryGroupIfPossible`, the data-set `source`, value lists and their types. A construct the DSL cannot express becomes a sentinel `__unsupported__` node — `skd-compile` refuses the JSON until each one is replaced or deleted; they are listed in `<basename>.warnings.md` next to `OutputPath`. Always re-validate (`1c-skd-validate`) and compare (`1c-skd-info`) after the cycle.

### Parameters and Command

| Parameter | Description |
|-----------|-------------|
| `TemplatePath` (alias `Path`) | Path to the `Template.xml` of a Data Composition Schema |
| `OutputPath` | (opt.) Write JSON DSL to this file; prints to stdout when omitted |

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-skd-decompile/scripts/skd-decompile.ps1 -TemplatePath "<Template.xml>" [-OutputPath "<schema.json>"]
```

Fails fast (exit 2) when the root element is not `DataCompositionSchema` (e.g. a spreadsheet document — use `1c-mxl-decompile` instead); exit 3 on a construct it cannot take as a sample at all (picture cells, value storage, nested schemas) — use `1c-skd-edit` on such a report.

---
## 6. XSD Schemas — `v8-xsd-fetch`

Downloads the platform XSD schemas of the dump format, by format version, into the project's schema directory (same resolution as section 4: `-OutPath`, else `V8_XSD_PATH`, else `.v8-project.json` `xsdPath`, else `.v8-xsd` next to `.dev.env`). `skd-validate` uses them; no platform install is needed.

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-v8-xsd-fetch/scripts/v8-xsd-fetch.ps1 -Versions "2.20"
```

| Parameter | Description |
|-----------|-------------|
| `-Versions "<list>"` | Format versions, comma-separated. Without it — every available version (~600 KB each) |
| `-List` | Show the available versions and which are present locally; downloads nothing |
| `-OutPath <dir>` | Another schema directory — only when the user names one |
| `-Ref <ref>` | Branch, tag or commit of the source repository (default `main`) |
| `-Force` | Re-download files already present |

- **Which version** — the `version` attribute of the dump's `Configuration.xml` root (e.g. `2.20`), not the platform release. Fetch the versions of the dumps the project works with.
- **Source** — the third-party GitHub repository [yellow-hammer/namespace-forest](https://github.com/yellow-hammer/namespace-forest), `schemas/designer/<version>/`, through `api.github.com` and `raw.githubusercontent.com`. The ref is resolved to a commit first; `source.json` records repository, ref, commit and time per version.
- **Licence** — the schemas are part of 1C:Enterprise 8, property of 1C-Soft LLC, under the 1C licence agreement. They are never committed: the tool writes `.gitignore` (`*`) into the schema directory; keep the directory in the project's `.gitignore` as well.
- **Offline** — on a network error the tool exits `1` and names the target directory. Copy the `schemas/designer/<version>/` directories of the same repository by hand, or put schemas exported from your own platform there (`ФабрикаXDTO.ЭкспортСхемыXML`; file names do not matter, a schema is found by `targetNamespace`). The MCP `get_xsd_schema` tool answers single lookups without any download.

---
## Typical Workflow

1. **Create new DCS**: `1c-skd-compile` from JSON → `1c-skd-validate` → `1c-skd-info` for visual summary
2. **Modify existing DCS**: `1c-skd-edit` with operations → `1c-skd-validate` → `1c-skd-info`
   - `XSD not checked` in the summary and an order / XDTO question at stake → `v8-xsd-fetch -Versions <dump version>` once per project, then validate again
3. **Analyze structure**: `1c-skd-info` overview → `1c-skd-info -Mode trace -Name <field>` for field calculation chain → `1c-skd-info -Mode query -Name <dataset>` for query text → `1c-skd-info -Mode variant -Name <N>` for variant groupings and filters
4. **Capture existing DCS as DSL**: `1c-skd-decompile` → edit the JSON → `1c-skd-compile` → `1c-skd-validate` (round-trip, draft)
5. **MCP evidence set** (`content/rules/tooling-playbooks.md`): `get_xsd_schema` / `verify_xml` with `object_type="СКД"`

---

Scripts vendored from Nikolay-Shirokov/cc-1c-skills; sync history — `docs/CHANGELOG.md`.
