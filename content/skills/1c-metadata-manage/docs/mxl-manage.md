# 1C MXL Manage — Compile, Decompile, Info, Validate

Spreadsheet document (MXL) layouts: create from JSON, reverse-engineer to JSON, analyze structure, validate. Tools: `mxl-compile` v1.61, `mxl-decompile` v1.32, `mxl-info` v1.7, `mxl-validate` v1.11.

The JSON DSL the compiler reads and the decompiler writes is described in [mxl-dsl-spec.md](../tools/1c-mxl-compile/mxl-dsl-spec.md). Read the section the task needs (styles, column layouts, input cells, notes, groups, print, pictures), not the whole file.

---
## 1. Compile — Create from JSON

Takes a compact JSON definition and generates `Template.xml` of a spreadsheet document. The agent describes *what* is needed (areas, parameters, styles); the script produces correct XML (palettes, indices, merges, namespaces, element order).

### Usage

```
1c-mxl-compile <JsonPath> <OutputPath>
```

| Parameter | Required | Description |
|-----------|:--------:|-------------|
| JsonPath | yes | Path to the JSON definition (UTF-8; a BOM decides the encoding when present) |
| OutputPath | yes | Path of the generated `Template.xml`, relative or absolute. Missing directories are created |

### Command

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-mxl-compile/scripts/mxl-compile.ps1 -JsonPath "<path>.json" -OutputPath "<path>/Template.xml"
```

Parameters are named only (`-JsonPath`, `-OutputPath`); positional arguments are not bound.

### Workflow

1. Write the JSON definition (Write tool) → `.json` file
2. Run `1c-mxl-compile` to generate `Template.xml`
3. Run `1c-mxl-validate` to verify correctness
4. Run `1c-mxl-info` to verify structure

A new template object in the configuration is registered by `add-template` ([template-manage.md](template-manage.md)); `mxl-compile` only writes the layout body.

**If creating a layout from an image** (screenshot, scanned print form) — first use the `img-grid-analysis` skill to overlay a grid, determine column boundaries and proportions, then use `"Nx"` widths + `"page"` for automatic size calculation.

### DSL at a glance

```
{ columns, page, defaultWidth, columnWidths, columnStyles, textLanguages,
  fonts:  { name: { face, size, bold, italic, underline, strikeout } | { ref } },
  styles: { name: { font, horizontalAlignment, verticalAlignment, textPlacement,
                    border | leftBorder | topBorder | rightBorder | bottomBorder,
                    borderColor, backColor, textColor, format, ... } },
  areas: [ { name, columnSet, rows: [
    { height, hidden, rowStyle, empty, cells: [
      { col, span, rowspan, style, param, detail, text, template, note,
        valueType, controlType, value, pictureParameter } ] }
    | [ "text", "{Param}", ">", "|", null, { ...cell without col } ] ] } ],
  namedAreas, columnSets, rowGroups, columnGroups,
  header, footer, printSettings, pictures, drawings }
```

```json
{
  "columns": 5,
  "columnWidths": { "1": 5, "2": 40, "3-5": 12 },
  "fonts": { "bold": { "face": "Arial", "size": 10, "bold": true } },
  "styles": {
    "head":  { "font": "bold", "horizontalAlignment": "Center", "textPlacement": "Wrap", "border": "Solid" },
    "cell":  { "border": "Solid" },
    "num":   { "border": "Solid", "horizontalAlignment": "Right", "format": "ЧЦ=15; ЧДЦ=2" },
    "total": { "font": "bold", "horizontalAlignment": "Right", "topBorder": "Solid" }
  },
  "areas": [
    { "name": "Title", "rows": [
      { "height": 20, "cells": [{ "col": 1, "span": 5, "style": "head", "param": "Title" }] }, {} ] },
    { "name": "TableHeader", "rows": [
      { "rowStyle": "head", "cells": ["N", "Item", "Qty", "Price", "Amount"] } ] },
    { "name": "Row", "rows": [
      { "rowStyle": "cell", "cells": [
        { "col": 1, "param": "LineNo" },
        { "col": 2, "param": "Item", "detail": "Nomenclature" },
        { "col": 3, "style": "num", "param": "Qty" },
        { "col": 4, "style": "num", "param": "Price" },
        { "col": 5, "style": "num", "param": "Amount" } ] } ] },
    { "name": "Total", "rows": [
      { "rowStyle": "total", "cells": [null, null, null, "Total:", "{Sum}"] } ] }
  ]
}
```

Key rules:
- `columns` and `areas` are required; every row / column number in the DSL is **1-based**.
- An area is a run of consecutive rows; with `name` it is reachable as `Template.GetArea("Name")`. Areas that are not row runs (column bands, rectangles, overlapping areas) go into `namedAreas`.
- Content of a cell is one of `param` / `text` / `template`; fill type is derived. `detail` is independent — a cell with only `detail` is kept.
- A row can be a positional list (`"text"`, `"{Param}"`, `">"` span, `"|"` rowspan, `null` skip, `{…}` cell without `col`). In an object row, either every cell has `col` or none has (then they are laid out left to right); mixing is an error.
- `rowStyle` covers the full row width (continuous table borders) and is also stored as the row's own format; a cell's `style` overrides it.
- Style keys are the platform property names (`horizontalAlignment`, `verticalAlignment`, `textPlacement`, `backColor`, …), all format properties are available. Borders: `"Solid"` or `{ "style": "Solid", "width": 2 }` on `border` or a side.
- A font reaches a cell only through a style's `font` key — `fonts.default` is **not** applied to styles that name no font.
- `text` / `template` may be a language object (`{ "ru": …, "en": … }`); a plain string is written for every language in `textLanguages` (default `["ru"]`).
- `page` — `"A4-landscape"` / `"A4-portrait"` / a number: derives `defaultWidth` from the `"Nx"` shares of `columnWidths`.

New in the DSL since the previous sync (all in [mxl-dsl-spec.md](../tools/1c-mxl-compile/mxl-dsl-spec.md)): column layouts (`columnSets` + area `columnSet`) and named areas bound to them; `columnStyles`; row format (`height`, `hidden`, `rowStyle`); every format property in styles; multilingual text and `textLanguages`; input-field cells (`valueType`, `controlType`, `value`); cell notes; row / column groups; header, footer and `printSettings`; pictures, the picture palette and drawings; font references and fractional sizes.

### What stops the compile

Exit code 1 with a one-line message on stderr, nothing written:

- `columns` or `areas` missing; the JSON file missing, invalid, or not UTF-8 without a BOM;
- an unknown **enum value** in a style (`verticalAlignment: "middle"`, `align: "centre"`), an unknown line style or border side, an unknown `controlType`, drawing `type` or `rowStyle.apply`;
- an unknown `printSettings` key;
- `col` outside the layout, cells with and without `col` mixed in one row, a positional row longer than `columns`, a `">"` / `"|"` with nothing to continue;
- `columnSet` not declared in `columnSets`; a `namedAreas` entry without a name or axes, or with a comma list;
- `rowGroups` / `columnGroups` that overlap partially;
- an input-field cell with `text` / `template`, `controlType` / `value` without `valueType`, or `control` that is not the base64 settings blob (local check — the control kind goes into `controlType`);
- the support guard refusing the target (below).

Not errors: an unknown style key (`WARNING`, ignored), an unknown top-level key (ignored), a style naming an undeclared font, a cell naming an undeclared style (the reference is dropped). Re-check names with `mxl-info` after compiling.

### Format version and namespaces

The XML root has no version attribute; the compiler takes it from the tree it writes into — the nearest `Configuration.xml`, or the root of an external data processor / report (`<Name>.xml` next to its directory). Outside a configuration it writes the 2.17 shape. At **2.21** (platform 8.5) it adds `xmlns:pal` to the root, as the platform does.

### Support guard

Before writing, the target is checked against the vendor support state (`Ext/ParentConfigurations.bin`) — a layout of an object "on lock" is refused. The reaction comes from `.dev.env` `SUPPORT_GUARD` (`deny` default, `warn`, `off`); an unreadable support file fails closed. The check runs before the destination directory is created. External data processors / reports are never guarded. Details: [support-manage.md](support-manage.md).

### Changes against the previous version (v1.4)

- **Stricter.** An unknown enum value was dropped silently and is now exit 1 (see above). Values v1.4 did not know are now honoured instead of ignored — e.g. `valign: "bottom"` produces `Bottom`.
- **Enum values are case-insensitive** (`"center"` = `"Center"`).
- **Old spellings are synonyms**: `align`, `valign`, `wrap: true`, `border` as a side list (`"all"`, `"left,top"`) with `borderWidth: "thin" | "thick"` still compile; the canonical key wins when both are present. JSON written for or decompiled by the old tools compiles; decompile again to get the canonical form.
- **Fonts**: a format carries a font only when its style names one; v1.4 wrote the `default` font into every format. Old JSON that relied on `fonts.default` must name `"font": "default"` in its styles.
- **Unstyled cells** reference no format at all (`<f>0</f>`), as the platform writes them.
- **Escaping**: `parameter`, `detailParameter`, area / drawing names and `faceName` are XML-escaped — a BSP output condition such as `Discount <> 0` gives a loadable layout (upstream #121).

---
## 2. Decompile — Extract to JSON

Takes a `Template.xml` of a spreadsheet document and generates the JSON DSL. Reverse operation of `1c-mxl-compile`.

### Usage

```
1c-mxl-decompile <TemplatePath> [OutputPath]
```

| Parameter | Required | Description |
|-----------|:--------:|-------------|
| TemplatePath | yes | Path to `Template.xml` |
| OutputPath | no | Path for the JSON, relative or absolute. Its directory must exist |

### Command

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-mxl-decompile/scripts/mxl-decompile.ps1 -TemplatePath "<path>/Template.xml" -OutputPath "<path>.json"
```

Always pass `-OutputPath`: without it the JSON goes to stdout followed by two summary lines (`Areas: …`, `Fonts: …`), so captured stdout is not valid JSON.

### Workflow

1. Run `1c-mxl-decompile` to get JSON from `Template.xml`
2. Analyze or modify the JSON (add areas, change styles)
3. Run `1c-mxl-compile` to generate the new `Template.xml`
4. Run `1c-mxl-validate`, then compare with `1c-mxl-info` (or a diff) against the original

### What the output looks like

- **Canonical keys** — the same names the DSL reference uses (`horizontalAlignment`, `textPlacement`, …), never the old synonyms.
- **Positional cells** — a row without its own properties is written as a list (`["N", "{Item}", ">", null]`); cells that need `style`, `detail` and the like stay objects without `col`.
- **Generated names.** Fonts: palette entry 0 is `default`; others `bold`, `italic`, `underline`, `header` (larger bold), `small`, the reference name for `{ ref }` fonts, or `<face>-<size>-bold…`. Styles are labelled by their visible traits — font name, `bordered` / `border-left,top`, `center` / `right`, `vcenter` / `vtop`, `wrap`, `bg`, `fmt` (e.g. `bold-bordered-center-wrap`, `bordered-right-fmt`); a style of inconspicuous properties only is `style`; clashes get `2`, `3`, …. Names are labels — rename freely, keeping references consistent.
- **Row styles** may come back as `{ "style": …, "apply": "row" | "cells" }`, column layouts keyed by their original UUID, and further keys that exist only for the round trip (`languages`, `controlType: "none"`, base64 `control`, `note.anchor`, drawing `id` / `zOrder`). Leave them in place — they are listed in the DSL reference, § "Keys you meet only in decompiled JSON".

### Round trip: what survives

Everything the DSL expresses is read back: texts in every language, parameters, templates, drill-down parameters (also on cells without a parameter), input-field type / value / control settings, every format property (fonts with fractional sizes and references, colours, patterns, borders, protection, masks), row height and hiding, column widths and styles, column layouts and the binding of areas to them, named areas of every type, cell-bound merges, notes, row / column groups, header and footer, print settings, pictures and drawings, the layout's language declaration.

Lost on decompile → compile (not in the DSL): merges not bound to a cell (full height or width of the document), chart contents of `Chart` / `GanttChart` drawings (the drawing itself survives), the print area and print-repeat ranges. Set those in Configurator after a rebuild.

**Byte-for-byte.** On upstream's control set of layouts saved by the platform, 7 of 10 rebuild byte-for-byte. The other three differ in one thing only — leftovers of earlier edits: a cell's format still points at a palette entry carrying a column `width` from before the columns were resized. Such values describe nothing in the final document and are not reproduced — the content is identical, the bytes are not. Re-run with the tools of this sync over the 14 Configurator-saved layouts upstream keeps as round-trip fixtures: 13 rebuild byte-for-byte; the 14th, a vendor (УТ) print form, keeps its areas, texts and drill-down conditions, but its format palette shrinks from 18 to 10 entries — its cell formats carry column widths and row heights of earlier states, and some rows point at a zero-height format; none of that is reproduced. Long-edited vendor layouts show more of this, so the diff after a rebuild is often wider than the edit itself. A rebuild is always a full regeneration, not a patch: if the task is to keep a vendor layout as is and change a little, check the result with `mxl-info` or a diff.

Checked on 2026-11-01 with a throwaway file infobase: a layout compiled by `mxl-compile` (header / footer, print settings, input-field and checkbox cells, a note, a row group, an extra column layout bound to an area, a column-band named area, a picture and a rectangle, `<` / `&` in parameters, details and names, a fractional font size) built into an EPF and dumped back on **8.3.27** and **8.5.1**. The platform's dump then decompiled and recompiled byte-for-byte on both — on 8.5.1 into the 2.21 tree, including `xmlns:pal`. The platform's rewrite of the freshly *authored* file differs from the compiler output only in the font palette order, the line wrapping of picture base64 and the print margins it fills in (`1000`).

---
## 3. Info — Analyze Structure

Reads `Template.xml` of a spreadsheet document and outputs a compact summary: named areas, parameters, column sets. Replaces the need to read thousands of XML lines.

### Usage

```
1c-mxl-info <TemplatePath>
1c-mxl-info <ProcessorName> <TemplateName>
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| TemplatePath | no | — | Path to `Template.xml` (alias `-Path`) |
| ProcessorName | no | — | Processor name (alternative to path) |
| TemplateName | no | — | Template name (alternative to path) |
| SrcDir | no | `src` | Source directory |
| Format | no | `text` | Output format: `text` or `json` |
| WithText | no | false | Include static text and templates |
| MaxParams | no | 10 | Max parameters per area in listing |
| Limit | no | 150 | Max output lines (overflow protection) |
| Offset | no | 0 | Skip N lines (for pagination) |

Specify either `-TemplatePath` (the file itself — unlike `mxl-validate`, a template directory is not resolved), or both `-ProcessorName` and `-TemplateName`. A malformed XML file gives a location block (line, position, excerpt) and exit 1.

### Command

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-mxl-info/scripts/mxl-info.ps1 -TemplatePath "<path>/Ext/Template.xml"
```

Or by processor/template name:
```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-mxl-info/scripts/mxl-info.ps1 -ProcessorName "<Name>" -TemplateName "<Template>" [-SrcDir "<dir>"]
```

Additional flags:
```powershell
... -WithText              # include text cell content
... -Format json           # JSON output for programmatic processing
... -MaxParams 20          # show more parameters per area
... -Offset 150            # pagination: skip first 150 lines
```

The header line also prints the support state of the layout's owner.

### Reading the Output

#### Areas — Sorted Top to Bottom

Areas are listed in document order (by row position), not alphabetically. This matches the area output order in fill code — top to bottom. Row and column numbers here are the XML's **0-based** indices (the DSL counts from 1).

```
--- Named areas ---
  Header             Rows     rows 0-3     (1 params)
  Supplier           Rows     rows 4-5     (1 params)
  Row                Rows     rows 13-13   (8 params)
  Total              Rows     rows 15-16   (1 params)
```

Area types:
- **Rows** — horizontal area (row range). Access: `Template.GetArea("Name")`
- **Columns** — vertical area (column range). Access: `Template.GetArea("Name")`
- **Rectangle** — fixed area (rows + columns). Usually uses a separate column set.
- **Drawing** — named drawing/barcode.

#### Column Sets

When the layout has multiple column sets, their sizes are shown in the header and per area:

```
  Column sets: 7 (default=19 cols + 6 additional)
    f01e015f...: 17 cols
    0adf41ed...: 4 cols
  ...
  Footer             Rows     rows 29-33  (5 params) [colset 14cols]
  PageNumbering      Rows     rows 58-58  (0 params) [colset 4cols]
```

#### Intersections

When both Rows and Columns areas exist (labels, price tags), the script outputs intersection pairs:

```
--- Intersections (use with GetArea) ---
  LabelHeight|LabelWidth
```

In BSL: `Template.GetArea("LabelHeight|LabelWidth")`

#### Parameters and detailParameter

Parameters are listed per area. If a parameter has a `detailParameter` (drill-down), it is shown below:

```
--- Parameters by area ---
  Supplier: SupplierPresentation
    detail: SupplierPresentation->Supplier
  Row: RowNumber, Product, Quantity, Price, Amount, ... (+3)
    detail: Product->Nomenclature
```

This means: parameter `Product` displays a value, and when clicked opens `Nomenclature` (drill-down object). A drill-down on a cell without a fill parameter is not listed here.

In BSL:
```bsl
Area.Parameters.Product = TableRow.Nomenclature;
Area.Parameters.ProductDrillDown = TableRow.Nomenclature; // detailParameter
```

#### Template Parameters (suffix `[tpl]`)

Some parameters are embedded in template text: `"Inv No. [InventoryNumber]"`. They are filled via fillType=Template, not fillType=Parameter. The script always extracts them and marks with suffix `[tpl]`:

```
  PageNumbering: Number [tpl], Date [tpl], PageNumber [tpl]
```

In BSL, template parameters are filled the same way as regular ones:
```bsl
Area.Parameters.Number = DocumentNumber;
Area.Parameters.Date = DocumentDate;
```

Numeric substitutions like `[5]`, `[6]` (footnote references in official forms) are ignored.

#### Text Content (`-WithText`)

Shows static text (labels, headers) and template strings with substitutions `[Parameter]`:

```
--- Text content ---
  TableHeader:
    Text: "No.", "Product", "Unit", "Qty", "Price", "Amount"
  Row:
    Templates: "Inv No. [InventoryNumber]"
```

- **Text** — static labels (fillType=Text). Useful for understanding column purposes.
- **Templates** — text with substitutions `[ParameterName]` (fillType=Template). Parameter inside `[]` is filled programmatically.

### When to Use

- **Before writing fill code**: run `1c-mxl-info` to understand area names and parameter lists, then write BSL output code following area order top to bottom
- **With `-WithText`**: when context is needed — column headers, labels near parameters, template strings
- **With `-Format json`**: when structured data is needed for programmatic processing
- **For existing layouts**: analyze loaded or configuration layouts without reading raw XML
- **After a rebuild**: compare areas and parameters with the original

### Overflow Protection

Output is limited to 150 lines by default. When exceeded:
```
[TRUNCATED] Shown 150 of 220 lines. Use -Offset 150 to continue.
```

Use `-Offset N` and `-Limit N` for paginated viewing.

---
## 4. Validate — Check Correctness

Checks `Template.xml` for structural errors that the 1C platform may silently ignore or reject at load time (data loss, layout corruption, XDTO errors).

### Usage

```
1c-mxl-validate <TemplatePath>
1c-mxl-validate <ProcessorName> <TemplateName>
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| TemplatePath | no | — | `Template.xml`, the template directory (`Templates/<Name>` → `Ext/Template.xml`) or its descriptor `Templates/<Name>.xml` (alias `-Path`) |
| ProcessorName | no | — | Processor name (alternative to path) |
| TemplateName | no | — | Template name (alternative to path) |
| SrcDir | no | `src` | Source directory |
| Detailed | no | — | Print every check, including passed ones |
| MaxErrors | no | 20 | Stop after N errors |

### Command

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-mxl-validate/scripts/mxl-validate.ps1 -TemplatePath "<path>"
```

Or by processor/template name:
```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-mxl-validate/scripts/mxl-validate.ps1 -ProcessorName "<Name>" -TemplateName "<Template>" [-SrcDir "<dir>"]
```

### Checks Performed

| # | Check | Severity |
|---|-------|----------|
| 1 | `<height>` >= max row index + 1 | ERROR |
| 2 | `<vgRows>` <= `<height>` | WARN |
| 3 | Cell and note format indices (`<f>`, note `<formatIndex>`) within the format palette | ERROR |
| 4 | Row / column `<formatIndex>` within the palette | ERROR |
| 5 | Cell column indices (`<i>`) within the column count of the row's column set | ERROR |
| 6 | Row `<columnsID>` references an existing column set | ERROR |
| 7 | Named area `<columnsID>` references an existing set | ERROR |
| 8 | Named area ranges within document boundaries | ERROR |
| 9 | Merge ranges within document boundaries; merge `<columnsID>` exists | ERROR |
| 10 | Font indices in formats within the font palette | ERROR |
| 11 | Border line indices in formats within the line palette | ERROR |
| 12 | Drawing `pictureIndex` within the picture palette; drawing `formatIndex` within the format palette | ERROR |
| 13 | Input-field cells: `valueType` ⇔ `containsValue`, only type tags inside `valueType`, a cell value / control only with a value format, no value and text in one cell | ERROR |
| 13 | Unknown `controlType` GUID; checkbox on a type other than Boolean / Number; a row, column or `defaultFormatIndex` pointing at a value format | WARN |
| 14 | Row / column groups: `<b>` present, range not reversed, no partial overlap | ERROR |
| 14 | A row group starting beyond the document height | WARN |

### Output

No findings — one line:
```
=== Validation OK: Template.Invoice (12 checks) ===
```

With findings (or `-Detailed`, which also prints `[OK]` lines):
```
[ERROR] Row 15: cell format index 38 > format palette size (37)

=== Result: 1 errors, 0 warnings (12 checks) ===
```

Malformed XML — the location and an excerpt instead of a parser trace, the other checks skipped:
```
[ERROR] Not well-formed XML (line 1, position 15):
        Unexpected end of file while parsing Name has occurred.
        1 | <document><bad
                          ^

=== Result: 1 errors, 0 warnings (other checks skipped) ===
```

Return code: 0 = no errors (warnings allowed), 1 = errors found.

### When to Use

- **After layout generation**: run validator to find structural errors before building
- **After editing Template.xml**: ensure indices and references remain valid
- **When debugging**: fix found issues and re-run until all checks pass

### Overflow Protection

Stops after 20 errors by default (configurable via `-MaxErrors`). The summary line with error/warning counts is always shown.

---
## Typical Workflow

1. **Create new layout**: Write JSON definition → `1c-mxl-compile` → `1c-mxl-validate` → `1c-mxl-info` to verify structure
2. **Modify existing layout**: `1c-mxl-decompile -OutputPath` → edit the JSON → `1c-mxl-compile` → `1c-mxl-validate` → compare `1c-mxl-info` with the original; restore by hand what the DSL cannot carry (§2 "Round trip")
3. **Before writing fill code**: Run `1c-mxl-info` to understand area names and parameters, then write BSL output code following area order top to bottom
4. **After generation or editing**: Run `1c-mxl-validate` to find structural errors before building
5. **MCP evidence set** (`content/rules/tooling-playbooks.md`): `get_xsd_schema` / `verify_xml` with `object_type="Макет"`

---

Scripts vendored from Nikolay-Shirokov/cc-1c-skills; sync history — `docs/CHANGELOG.md`.
