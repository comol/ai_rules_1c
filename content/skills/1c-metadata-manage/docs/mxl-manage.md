# 1C MXL Manage — Compile, Decompile, Info, Validate

Comprehensive spreadsheet document (MXL) management: create from JSON, reverse-engineer to JSON, analyze structure, validate correctness.

---
## 1. Compile — Create from JSON

Takes a compact JSON definition and generates a correct Template.xml for a 1C spreadsheet document. The agent describes *what* is needed (areas, parameters, styles), the script ensures XML *correctness* (palettes, indices, merges, namespaces).

### Usage

```
1c-mxl-compile <JsonPath> <OutputPath>
```

| Parameter | Required | Description |
|-----------|:--------:|-------------|
| JsonPath | yes | Path to JSON layout definition |
| OutputPath | yes | Path for generated Template.xml |

### Command

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-mxl-compile/scripts/mxl-compile.ps1 -JsonPath "<path>.json" -OutputPath "<path>/Template.xml"
```

### Workflow

1. Write JSON definition (Write tool) → `.json` file
2. Run `1c-mxl-compile` to generate Template.xml
3. Run `1c-mxl-validate` to verify correctness
4. Run `1c-mxl-info` to verify structure

**If creating a layout from an image** (screenshot, scanned print form) — first use `img-grid-analysis` skill to overlay a grid, determine column boundaries and proportions, then use `"Nx"` widths + `"page"` for automatic size calculation.

### JSON DSL Schema

Full format specification is embedded below.

Brief structure:

```
{ columns, page, defaultWidth, columnWidths,
  fonts: { name: { face, size, bold, italic, underline, strikeout } },
  styles: { name: { font, align, valign, border, borderWidth, wrap, format } },
  areas: [{ name, rows: [{ height, rowStyle, cells: [
    { col, span, rowspan, style, param, detail, text, template }
  ]}]}]
}
```

Key rules:
- `page` — page format (`"A4-landscape"`, `"A4-portrait"` or number). Automatically calculates `defaultWidth` from sum of `"Nx"` proportions
- `col` — 1-based column position
- `rowStyle` — auto-fills empty cells with style (borders across full width)
- Fill type is determined automatically: `param` → Parameter, `text` → Text, `template` → Template
- `rowspan` — vertical cell merging (rowStyle accounts for occupied cells)

---
## 2. Decompile — Extract to JSON

Takes a Template.xml of a 1C spreadsheet document and generates a compact JSON definition (DSL). Reverse operation of `1c-mxl-compile`.

### Usage

```
1c-mxl-decompile <TemplatePath> [OutputPath]
```

| Parameter | Required | Description |
|-----------|:--------:|-------------|
| TemplatePath | yes | Path to Template.xml |
| OutputPath | no | Path for JSON output (if not specified — stdout) |

### Command

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-mxl-decompile/scripts/mxl-decompile.ps1 -TemplatePath "<path>/Template.xml" [-OutputPath "<path>.json"]
```

### Workflow

Decompiling an existing layout for analysis or modification:

1. Run `1c-mxl-decompile` to get JSON from Template.xml
2. Analyze or modify JSON (add areas, change styles)
3. Run `1c-mxl-compile` to generate new Template.xml
4. Run `1c-mxl-validate` to verify

### JSON DSL Schema

Full format specification is in Section 1 above.

### Name Generation

The script automatically generates meaningful names:

- **Fonts**: `default`, `bold`, `header`, `small`, `italic` — or descriptive names by properties
- **Styles**: `bordered`, `bordered-center`, `bold-right`, `border-top`, etc. — by property combination

### rowStyle Detection

If a row has empty cells (no parameters/text) and all of them share the same format — that format is recognized as `rowStyle`, and empty cells are excluded from output.

---
## 3. Info — Analyze Structure

Reads Template.xml of a spreadsheet document and outputs a compact summary: named areas, parameters, column sets. Replaces the need to read thousands of XML lines.

### Usage

```
1c-mxl-info <TemplatePath>
1c-mxl-info <ProcessorName> <TemplateName>
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| TemplatePath | no | — | Direct path to Template.xml |
| ProcessorName | no | — | Processor name (alternative to path) |
| TemplateName | no | — | Template name (alternative to path) |
| SrcDir | no | `src` | Source directory |
| Format | no | `text` | Output format: `text` or `json` |
| WithText | no | false | Include static text and templates |
| MaxParams | no | 10 | Max parameters per area in listing |
| Limit | no | 150 | Max output lines (overflow protection) |
| Offset | no | 0 | Skip N lines (for pagination) |

Specify either `-TemplatePath`, or both `-ProcessorName` and `-TemplateName`.

### Command

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-mxl-info/scripts/mxl-info.ps1 -TemplatePath "<path>"
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

### Reading the Output

#### Areas — Sorted Top to Bottom

Areas are listed in document order (by row position), not alphabetically. This matches the area output order in fill code — top to bottom.

```
--- Named areas ---
  Header             Rows     rows 1-4     (1 params)
  Supplier           Rows     rows 5-6     (1 params)
  Row                Rows     rows 14-14   (8 params)
  Total              Rows     rows 16-17   (1 params)
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
  Footer             Rows     rows 30-34  (5 params) [colset 14cols]
  PageNumbering      Rows     rows 59-59  (0 params) [colset 4cols]
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

This means: parameter `Product` displays a value, and when clicked opens `Nomenclature` (drill-down object).

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

### Overflow Protection

Output is limited to 150 lines by default. When exceeded:
```
[TRUNCATED] Shown 150 of 220 lines. Use -Offset 150 to continue.
```

Use `-Offset N` and `-Limit N` for paginated viewing.

---
## 4. Validate — Check Correctness

Checks Template.xml for structural errors that the 1C platform may silently ignore (potentially causing data loss or layout corruption).

### Usage

```
1c-mxl-validate <TemplatePath>
1c-mxl-validate <ProcessorName> <TemplateName>
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| TemplatePath | no | — | Direct path to Template.xml |
| ProcessorName | no | — | Processor name (alternative to path) |
| TemplateName | no | — | Template name (alternative to path) |
| SrcDir | no | `src` | Source directory |
| MaxErrors | no | 20 | Stop after N errors |

Specify either `-TemplatePath`, or both `-ProcessorName` and `-TemplateName`.

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
| 3 | Cell format indices (`<f>`) within format palette | ERROR |
| 4 | Row/column `<formatIndex>` within palette | ERROR |
| 5 | Cell column indices (`<i>`) within column count (accounting for column set) | ERROR |
| 6 | Row `<columnsID>` references existing column set | ERROR |
| 7 | Merge/namedItem `<columnsID>` references existing set | ERROR |
| 8 | Named area ranges within document boundaries | ERROR |
| 9 | Merge ranges within document boundaries | ERROR |
| 10 | Font indices in formats within font palette | ERROR |
| 11 | Border line indices in formats within line palette | ERROR |
| 12 | Drawing `pictureIndex` references existing picture | ERROR |

### Output

```
=== Validation: TemplateName ===

[OK]    height (40) >= max row index + 1 (40), rowsItem count=34
[OK]    Font refs: max=3, palette size=4
[ERROR] Row 15: cell format index 38 > format palette size (37)
[OK]    Column indices: max in default set=32, default column count=33
---
Errors: 1, Warnings: 0
```

Return code: 0 = all checks passed, 1 = errors found.

### When to Use

- **After layout generation**: run validator to find structural errors before building
- **After editing Template.xml**: ensure indices and references remain valid
- **When debugging**: fix found issues and re-run until all checks pass

### Overflow Protection

Stops after 20 errors by default (configurable via `-MaxErrors`). Summary line with error/warning counts is always shown.

---
## Typical Workflow

1. **Create new layout**: Write JSON definition → `1c-mxl-compile` → `1c-mxl-validate` → `1c-mxl-info` to verify structure
2. **Modify existing layout**: `1c-mxl-decompile` to get JSON → analyze/modify JSON → `1c-mxl-compile` → `1c-mxl-validate`
3. **Before writing fill code**: Run `1c-mxl-info` to understand area names and parameters, then write BSL output code following area order top to bottom
4. **After generation or editing**: Run `1c-mxl-validate` to find structural errors before building

---
## Recent Additions (upstream `w-2026-05-17`)

The PowerShell script `tools/1c-mxl-validate/scripts/mxl-validate.ps1` was refreshed from [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills). Highlights:

- **Universal validator improvements** — one-liner output by default (`-Detailed` for the full per-check trace); accepts both `Template.xml` and a folder path; universal `-Path` parameter alongside legacy `-TemplatePath`.

The compile/decompile/info scripts (`mxl-compile`, `mxl-decompile`, `mxl-info`) were not refreshed — no significant upstream changes for them in this period.

## MCP Integration

- **metadatasearch** — Verify object names used in parameters; find template paths in the configuration.
- **get_metadata_details** — Get attribute types for objects whose data will populate the layout.
- **get_xsd_schema** — Get XSD schema for layout XML (`object_type="Макет"`). Use before generating MXL XML.
- **verify_xml** — Validate generated layout XML against XSD.
- **templatesearch** — Find existing layout examples in the codebase.

## SDD Integration

When creating or modifying MXL spreadsheet layouts as part of a feature, update SDD artifacts if present (see `content/rules/sdd-integrations.md` for detection):

- **OpenSpec**: Add spec deltas describing layout purpose, areas, and parameters in `openspec/changes/`.
