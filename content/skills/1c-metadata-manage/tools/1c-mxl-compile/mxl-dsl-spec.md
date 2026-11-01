# MXL DSL — JSON definition of a spreadsheet layout

Reference for the JSON that `mxl-compile` reads and `mxl-decompile` writes (tools synced to [cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills) `2e75b0f`: `mxl-compile` v1.61, `mxl-decompile` v1.32). Written for this skill from upstream's `docs/mxl-dsl-spec.md` and `.claude/skills/mxl-compile/reference/*.md`. How to run the tools, exit codes and round-trip fidelity: [mxl-manage.md](../../docs/mxl-manage.md).

Read the section for the task at hand, not the whole file: the map and §1–§6 cover a typical print form.

## Map

```
{ columns, page, defaultWidth, columnWidths, columnStyles, textLanguages,
  fonts:  { name: { face, size, bold, italic, underline, strikeout } | { ref } },
  styles: { name: { font, horizontalAlignment, verticalAlignment, textPlacement,
                    border, leftBorder, topBorder, rightBorder, bottomBorder,
                    borderColor, backColor, textColor, format, ... } },
  areas: [ { name, columnSet, rows: [
    { height, hidden, rowStyle, empty, cells: [
      { col, span, rowspan, style, param, detail, text, template, note,
        valueType, controlType, value, pictureParameter } ] } ] } ],
  namedAreas, columnSets, rowGroups, columnGroups,
  header, footer, printSettings, pictures, drawings }
```

Only `columns` and `areas` are required. All row and column numbers in the DSL are **1-based**.

## 1. Top level

| Key | Default | Meaning |
|---|---|---|
| `columns` | — (required) | Column count of the default column layout. `0` is allowed when every row lives in a `columnSets` layout |
| `page` | — | `"A4-landscape"` (780), `"A4-portrait"` (540) or a number: derives `defaultWidth` from the `"Nx"` shares in `columnWidths` |
| `defaultWidth` | `10` | Width of a column not listed in `columnWidths` |
| `columnWidths` | `{}` | Keys `"1"`, `"3-14"`, `"5,7,9"`; value a number or `"Nx"` (multiple of `defaultWidth`, e.g. `"0.5x"`) |
| `columnStyles` | — | Same keys; value a style name — the whole column carries it (§7) |
| `textLanguages` | `["ru"]` | Languages a plain-string text expands to (§3) |
| `fonts`, `styles` | — | Named fonts and styles (§5, §6) |
| `areas` | — (required) | Row ranges in document order (§2) |
| `namedAreas`, `columnSets` | — | Areas by coordinates, extra column layouts (§7) |
| `rowGroups`, `columnGroups` | — | Collapsible groups (§10) |
| `header`, `footer`, `printSettings` | — | Print setup (§11) |
| `pictures`, `drawings` | — | Picture palette and objects over the grid (§12) |

An unknown top-level key is ignored silently — check spelling against this table.

## 2. Areas, rows, cells

**Area** (`areas[]`): `name` (optional — with it the rows become a named area, `Template.GetArea("Name")`), `columnSet` (§7), `rows`. An area without a name is just a piece of the grid.

**Row** (`rows[]`): `height`, `hidden`, `rowStyle`, `cells`. `{}` is an empty row; `{ "empty": 3 }` stands for three. `height` and `hidden` belong to the row, not to its cells.

**Cell** (`cells[]`):

| Key | Meaning |
|---|---|
| `col` | Column, 1-based. Omit it in **every** cell of a row and the cells are laid out left to right (honouring `span` and columns taken by a `rowspan` from above); mixing cells with and without `col` in one row is an error |
| `span` / `rowspan` | Merge to the right / downwards |
| `style` | Style name; overrides `rowStyle` for this cell |
| `param` | Fill parameter — `Area.Parameters.Name = …` |
| `text` | Static text: a string or a `{ "ru": …, "en": … }` object |
| `template` | Text with `[Parameter]` substitutions; string or language object |
| `detail` | Drill-down parameter. Stands on its own: a cell with only `detail` (no `param`, empty or with text) is kept |
| `note` | Tooltip note (§9) |
| `valueType`, `controlType`, `value` | Input-field cell (§8) |
| `pictureParameter` | Parameter that supplies a picture inside the cell (§12) |

Content is exactly one of `param` / `text` / `template`; none = an empty cell (useful for borders). `"text": ""` is an empty text, not an absent one. Fill type is derived — there is no `fillType` key.

### Positional cell list

A row (or a row's `cells`) may be a plain array; the position is the index:

| Element | Means |
|---|---|
| `"text"` | Static text |
| `{ "ru": "…", "en": "…" }` | Multilingual text — an object whose keys are not cell keys |
| `"{Name}"` | Fill parameter |
| `">"` | Continues the cell on the left (`span` + 1) |
| `"|"` | Continues the cell above (`rowspan` + 1) |
| `null` | Skip the column |
| `{ … }` | A cell object **without** `col` — for `style`, `detail`, `template`, `valueType`, … |

```json
"rows": [
  ["Kind", "Balance", ">", "Total"],
  ["|",    "start",   "end", "|"],
  ["{Kind}", "{Start}", "{End}", "{Total}"]
]
```

Row properties need the object form with the list in `cells`: `{ "rowStyle": "total", "cells": [null, null, "Total:", "{Sum}"] }`. Text equal to `">"`, `"|"` or `"{…}"` must be written as `{ "text": … }`. More elements than `columns` → error.

## 3. Multilingual text

`text`, `template`, header/footer slots, note texts, group and drawing names accept a string or a language object. A language object gives one entry per key, in key order. A string is written under every language in `textLanguages` (default `["ru"]`):

```json
{ "columns": 2, "textLanguages": ["ru", "en"],
  "areas": [ { "rows": [ ["Name", { "ru": "Поставщик", "en": "Supplier" }] ] } ] }
```

`textLanguages` is only the expansion list; it does not read the configuration's languages.

## 4. `rowStyle`

A row style covers the **whole width** of the row: columns without an explicit cell get it too (continuous borders in a table row), and it becomes the format of the row itself. A cell's `style` overrides it; columns taken by a `rowspan` from an earlier row are skipped.

## 5. Fonts — `fonts.<name>`

`face` (`Arial`), `size` (`10`, fractional allowed: `8.3`), `bold`, `italic`, `underline`, `strikeout`. Or a reference instead of a description: `{ "ref": "style:TextFont" }`, `{ "ref": "sys:DefaultGUIFont" }`.

A format gets a font **only through a style's `font` key**. A style without `font` — and a cell without a style — writes no font, so the platform's default font applies; `fonts.default` is *not* applied implicitly any more. Name `"font": "default"` (or any font) in every style that needs it. A font no style references is not written to the palette.

## 6. Styles — `styles.<name>`

A style key is the platform's property name as it appears in the dump. Enum values are **case-insensitive** (`"center"` = `"Center"`).

| Key | Value |
|---|---|
| `font` | Name from `fonts` |
| `horizontalAlignment` | `Left`, `Center`, `Right`, `Justify`, `Auto` |
| `verticalAlignment` | `Top`, `Center`, `Bottom` |
| `textPlacement` | `Wrap`, `Cut`, `Block`, `Auto` |
| `textOrientation` | Integer, tenths of a degree (`900` = 90°) |
| `indent`, `autoIndent` | Integer |
| `format`, `editFormat`, `mask` | 1C format string, e.g. `"ЧЦ=15; ЧДЦ=2"`, `"ДФ=dd.MM.yyyy"` (expanded to the layout languages) |
| `markNegatives` | Boolean |
| `textColor`, `backColor`, `patternColor`, `borderColor` | Colour (below) |
| `pattern` | `WithoutPattern`, `Solid`, `Pattern1` … `Pattern17` |
| `border`, `leftBorder`, `topBorder`, `rightBorder`, `bottomBorder` | Line (below) |
| `hidden`, `protection`, `print`, `hyperLink` | Boolean |
| `detailsUse` | `Cell`, `Row`, `WithoutProcessing` |
| `autoMarkIncomplete`, `bySelectedColumns`, `autoWidthCalculation` | Boolean |
| `columnSizeChange` | `Normal`, `QuickChange` |
| `widthWeightFactor` | Integer |
| `picIndex` | 1-based entry of `pictures` (§12) |
| `pictureSizeMode` | `AutoSize`, `Proportionally`, `RealSize` |
| `picHorizontalAlignment` | `Auto`, `Center`, `Left`, `Right` |
| `picVerticalAlignment` | `Top`, `Center`, `Bottom` |
| `textPosition` | `Auto`, `Top`, `Right`, `Bottom` — text relative to the cell picture |

**Colour** — platform notation: `#RRGGBB`, `style:Name` (style item), `web:Name`, `win:Name`. A name that does not exist is rejected by the platform at load time, not by the compiler.

**Line** — `"Solid"` (width 1) or `{ "style": "Solid", "width": 2 }`. Styles: `None`, `Solid`, `Dotted`, `Dashed`, `DashDotted`, `DashDottedDotted`, `ThinDashed`, `LargeDashed`, `ThickDashed`, `Double`; `thin` / `thick` mean Solid 1 / 2. Four equal sides are folded into one `border` automatically.

**Older spellings are synonyms** (case and spaces ignored; the canonical key wins when both are given): `align` / `halign` / `textAlign` → `horizontalAlignment`; `valign` / `verticalAlign` → `verticalAlignment`; `wrap: true` → `textPlacement: Wrap`; `background` / `bgColor` → `backColor`; `color` / `foreColor` → `textColor`; `borderLeft` / `border-left` (and the other sides) → `leftBorder` …; `protected` → `protection`; Russian names (`ЦветФона`, `Защита`, `Отступ`, …). The old border form still works: `"border": "all"` or `"left,top"` plus `"borderWidth": "thin" | "thick"`.

Not style keys: `width` (use `columnWidths`), `height` (row key), `fillType` (derived), `valueType` / `controlType` (cell keys), drawing lines (drawing keys `line` / `sides`).

An unknown style key gives a `WARNING` and is ignored; an unknown **enum value** or line style stops the compile (exit 1). A style that names an undeclared font, or a cell that names an undeclared style, is not an error — the reference is dropped; check the result with `mxl-info`.

## 7. Column layouts, column styles, areas by coordinates

**`columnSets`** — extra column layouts ("individual column widths" for a group of rows). The document's `columns` / `columnWidths` / `columnStyles` describe the default layout; each extra layout has the same three keys, and an area selects it with `columnSet`:

```json
{ "columns": 52, "columnWidths": { "1": 8 },
  "columnSets": { "table": { "columns": 52, "columnWidths": { "1": 7, "2-52": 24 } } },
  "areas": [ { "name": "Header", "rows": [["Sales report"]] },
             { "name": "Table", "columnSet": "table", "rows": [["N", "Item"]] } ] }
```

All rows of an area share its layout; `col` / `span` are checked against that layout's width. The key is any name when authoring (the compiler turns it into a deterministic UUID) or the UUID kept by `mxl-decompile`. An undeclared `columnSet` → error.

**`columnStyles`** — `{ "1": "centered", "4": "hidden-col" }`: a column carries a style like a cell or row; width and style are independent.

**`namedAreas`** — areas that are not a run of consecutive rows:

| Key | Meaning |
|---|---|
| `name` | Required |
| `rows` / `cols` | Number or `"N-M"` (no comma lists); at least one axis |
| `columnSet` | Layout the area is bound to. Omitted — derived from the covered rows; `""` — not bound |

The area type follows from the axes, as in `SpreadsheetDocument.Area()`: rows only → Rows, columns only → Columns, both → Rectangle (single values on both → one cell).

```json
"namedAreas": [ { "name": "PrintHeight", "rows": "1-48" },
                { "name": "LabelWidth", "cols": "1-35" },
                { "name": "Stamp", "rows": 9, "cols": "16-17", "columnSet": "table" } ]
```

## 8. Input-field cells

A cell with `valueType` accepts a value from the user instead of showing text:

| `valueType` | Type |
|---|---|
| `Boolean` | Boolean |
| `String`, `String(10)`, `String(10,fixed)` | String; no length = unlimited |
| `Number`, `Number(15,3)`, `Number(15,3,nonneg)` | Number |
| `Date`, `DateTime`, `Time` | Date qualifiers |
| `CatalogRef.Currencies`, `DocumentRef.Sale`, `EnumRef.Status`, `DefinedType.Amount` | Reference type |
| `CatalogRef`, `DocumentRef`, `AnyRef` | Any reference of that kind |
| `A + B` | Composite (no repeated primitive) |
| `""` | "Contains a value", type not restricted |

Russian names are accepted: `Число(15,3)`, `Строка(10)`, `СправочникСсылка.Валюты`.

- `controlType`: `input` (default — fits every type, Boolean included) or `checkbox`. Russian `ПолеВвода` / `Флажок` are accepted. Only together with `valueType`.
- `value`: the stored value, typed by the JSON literal (string, number, `true`/`false`) — not converted to the declared type. `""` = the empty value of the declared type; a date is `"YYYY-MM-DDThh:mm:ss"` and becomes a date only in a cell declared as a date.
- `text` / `template` are not allowed in such a cell (error); `param` and `detail` are.
- `control` is **not** the control kind: it is the platform's serialized control settings (base64) that `mxl-decompile` keeps. A kind such as `"checkbox"` there is refused (local check) — use `controlType`.

## 9. Cell notes

`note` — a string, a language object, or the full form:

```json
{ "col": 1, "text": "Total", "note": "Without VAT" }
{ "col": 2, "note": { "text": "max 20%", "style": "hint" } }
{ "col": 3, "note": { "text": "…", "autoSize": false,
                      "box": { "top": 58, "left": -175, "bottom": 362, "right": 478 } } }
```

An object with any of `text`, `style`, `box`, `autoSize`, `anchor` is the full form; otherwise its keys are languages. `style` defaults to the Configurator tooltip look; `autoSize` defaults to `true`; `box` holds the window offsets (`top` / `left` position, `bottom` / `right` size). `anchor` is round-trip only.

## 10. Row and column groups

```json
"rowGroups":    [ { "rows": "2-4" }, { "rows": 3 },
                  { "rows": 5, "name": "Totals", "collapsed": true, "titleLocation": "begin" } ],
"columnGroups": [ { "cols": "2-3", "name": { "ru": "Показатели", "en": "Values" } } ]
```

Flat list; nesting is a range inside another. Ranges must nest or be disjoint — a partial overlap is an error. `collapsed` defaults to `false`, `titleLocation` to `auto` (`begin`, `end`, `auto`). Order in the list does not matter.

## 11. Header, footer, print settings

```json
"header": { "font": "small", "verticalAlignment": "Bottom", "startPage": 2,
            "left": "Line one\nline two",
            "center": "Стр. [&НомерСтраницы] из [&СтраницВсего]",
            "right": { "ru": "Справа", "en": "Right" } },
"footer": { "show": false, "center": { "formatted": "<b>Total</> <colorstyle -16>red</>" } },
"printSettings": { "pageOrientation": "Landscape", "topMargin": 500, "fitToPage": true }
```

Header / footer: slots `left`, `center`, `right` (string, language object or `{ "formatted": … }` with inline markup such as `<b>…</>`, `<fontsize 12>`, `<colorstyle -16>`), plus `font` (name from `fonts`), `verticalAlignment`, `show` (default `true`), `startPage` (default `1`). Slot text may be multi-line (`\n` in the JSON string) and contain the fields the platform fills at print time: `[&НомерСтраницы]`, `[&СтраницВсего]`, `[&Дата]`, `[&Время]`.

`printSettings` keys (the dump's own names; any other key is an error): `pageOrientation`, `scale`, `collate`, `copies`, `perPage`, `topMargin`, `leftMargin`, `bottomMargin`, `rightMargin`, `headerSize`, `footerSize`, `fitToPage`, `blackAndWhite`, `printerName`, `paper`, `paperSource`, `pageWidth`, `pageHeight`, `duplexType`, `pagePlacementAlternation`, `firstPageNumber`. When the platform saves the layout it fills in the margins left out (observed on 8.3.27: `1000`), so a rebuilt file shows them.

Not in the DSL: the print area and "repeat at the top of every page" — set them in Configurator.

## 12. Pictures and drawings

```json
"pictures": { "stop": { "ref": "v8ui:Стоп48" },
              "logo": { "data": "iVBORw0KGgo...", "transparent": { "x": 24, "y": 29 } } },
"drawings": [
  { "type": "Picture", "picture": "logo", "name": "Logo",
    "begin": { "row": 1, "col": 1 }, "end": { "row": 3, "col": 2, "dy": 34, "dx": 115 },
    "pictureSize": "Proportionally", "detail": "LogoDetail" },
  { "type": "Rectangle", "style": "fill", "line": { "style": "Dashed", "width": 2 },
    "sides": { "left": true, "top": true, "right": false, "bottom": false },
    "begin": { "row": 5, "col": 1 }, "end": { "row": 6, "col": 3 } } ]
```

- `pictures` entry: `ref` (platform or common picture, both `v8ui:Name`) or base64 `data`; `transparent`: `false` or the `{ x, y }` pixel whose colour is transparent; `{}` = no picture. One entry can serve many drawings.
- Drawing: `type` (`Picture` default, `Rectangle`, `Ellipse`, `Line`, `Text`, `Chart`, `GanttChart`), anchors `begin` / `end` (`row`, `col`, offsets `dy` / `dx` in points), `picture`, `pictureSize` (`Stretch` default, `AutoSize`, `Proportionally`, `RealSize`), `text`, `name` (code access), `detail`, `style`, `line`, `sides`, `id` / `zOrder` (default: list order).
- Picture **inside a cell**: a style with `picIndex` (1-based, declaration order of `pictures`) plus `picHorizontalAlignment` / `picVerticalAlignment` / `pictureSizeMode` / `textPosition`; the cell key `pictureParameter` names the parameter that supplies the picture from code and can coexist with text.

## 13. Keys you meet only in decompiled JSON

`mxl-decompile` writes some keys that carry state the authoring DSL does not need. Do not remove them from a decompiled file — the compiler takes them back as they are, and without them the layout changes:

- `languages`, `currentLanguage`, `defaultLanguage` — the layout's language declaration (not the same as `textLanguages`);
- `rowStyle: { "style": …, "apply": "both" | "row" | "cells" }` — where the row style was stored;
- `controlType: "none"` or a GUID — no control tag / an unknown control kept as is; `control` — base64 control settings;
- `note.anchor`, drawing `id` / `zOrder`, zero `dy` / `dx`, a `columnStyles` entry with `null`, an empty `pictures` entry `{}`;
- `columnSets` keyed by the original UUID, `namedAreas[].columnSet` when the binding differs from the covered rows.

## 14. Not expressible (lost on decompile → compile)

- merges not bound to a cell (full height or width of the document);
- chart contents (`Chart`, `GanttChart` — the drawing survives, its data does not);
- the print area and print-repeat ranges.
