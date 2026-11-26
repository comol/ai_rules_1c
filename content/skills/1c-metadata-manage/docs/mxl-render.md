# 1C MXL Render — PNG Sketch and A4 Width

Draws a spreadsheet layout (`Template.xml`) as a PNG and says how its width prints on A4. It is a preview for the agent — to look at a layout it compiled, decompiled or is about to fill — not the platform's rendering. Tool: `mxl-render` v1.2, a local tool of this ruleset (not vendored from cc-1c-skills). The other MXL tools (compile, decompile, info, validate) are in [mxl-manage.md](mxl-manage.md).

**Windows only.** Drawing uses System.Drawing (GDI+). Under `pwsh` on Linux / macOS the script exits `1` before writing anything; use `mxl-info` for the structure there.

### Usage

```
1c-mxl-render <TemplatePath> [-OutputPath <png>] [-Area <name>]
1c-mxl-render <ProcessorName> <TemplateName>
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| TemplatePath | no | — | `Template.xml`, the template directory (`Templates/<Name>` → `Ext/Template.xml`) or its descriptor `Templates/<Name>.xml` (alias `-Path`) |
| ProcessorName / TemplateName / SrcDir | no | `src` | Name-based path, as in `mxl-validate` |
| OutputPath | no | `%TEMP%\mxl-render\<Owner>.<Template>[.<Area>].png` | Where the PNG goes. Keep it outside the source tree: a file next to `Template.xml` would end up in the dump |
| Area | no | — | Draw only the rows of this named area (`Rows` / `Rectangle`); an unknown name lists the existing ones and exits `1` |
| Zoom | no | `1.0` | Scale of the picture (0–4]. A layout wider than 15 000 px is zoomed out automatically |
| MaxHeight | no | `16000` | Picture height limit in pixels; rows below it are left out and the run says `TRUNCATED` |

### Command

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-mxl-render/scripts/mxl-render.ps1 -TemplatePath "<path>/Ext/Template.xml"
```

Then open the PNG the run names (the Read tool shows images).

### Output

A portrait print form without print settings of its own:

```
=== MXL render: ВосстановлениеВДолжности.ПФ_MXL_ПриказОВосстановленииНаРаботе ===
PNG: C:\Users\...\Temp\mxl-render\ВосстановлениеВДолжности.ПФ_MXL_ПриказОВосстановленииНаРаботе.png (740 x 1306 px)
Rows drawn: 1-55 of 55
Width (whole layout):
  default column set: 792 units (33 of 33 columns used, 55 rows)
  layout: 792 units, about 183 mm (1 unit = 1/8 character = 0.2315 mm, measured against 1C page breaking)
mxl-compile targets (A4-portrait 820, A4-landscape 1196 units - what the rules compile new layouts to): within the portrait target
Print settings stored in the layout: none
A4: portrait, 190 mm print width - fits at 100%; landscape, 277 mm - fits at 100%
Verdict: at 100% it fits A4 portrait
```

A layout that stores `fitToPage` (the last lines):

```
Print settings stored in the layout: orientation Portrait, fitToPage true, scale 100%, margins 10 + 10 mm
A4: portrait, 190 mm print width - does not fit at 100%, fitted to the page width about 94%; landscape, 277 mm - fits at 100%
Verdict: the layout is set to fit the page width (fitToPage): A4 portrait, reduced to about 94%
```

A `Not drawn:` line lists what the picture leaves out for this layout (drawings, cell pictures, rotated text, style colours, hidden rows, header / footer).

### What the picture shows

- Column widths of every column set, row heights (explicit, or fitted to the text of the row), merges, fills, borders with their line style, fonts (face, size, bold, italic, underline), horizontal / vertical alignment, wrap, and `Auto` text spilling into empty neighbour cells.
- Cell content as the designer shows it: static text, a parameter as `<Name>`, a template text with its `[Name]` substitutions. Texts in the layout's current language.
- Row numbers and column numbers (default column set) in the margins; `Rows` areas as labelled bands on the left, `Columns` areas on top, `Rectangle` areas as dashed outlines; drawings as dashed outlines with their type and name; a red corner on cells with a note.
- Not drawn: picture contents, charts, rotated text (drawn horizontally), colours given by style elements (drawn neutral), header / footer, print area, row / column groups, conditional appearance.

### Width

- **Units.** A layout's width is the sum of its columns up to the last one that shows something: a text, a parameter, a fill, a line that is not `None`, a merge, a column or rectangle area. Format-only cells further right do not count (ZUP's SZV-KORR keeps them up to the 78th column of a 13-column set). Each column set is reported; the widest one is the layout's width.
- **Millimetres.** A column-width unit in the XML is 1/8 of `ОбластьЯчеекТабличногоДокумента.ШиринаКолонки` (an "average character": `ШиринаКолонки = 10` is written as `80`), that is 7/8 of a pixel at 96 dpi = 0.2315 mm. Measured on 1C 8.3.27 (26.11.2026): the layout loaded into `ТабличныйДокумент` through `СериализаторXDTO`, page breaking at 100 % on the `Microsoft Print to PDF` printer, the left margin widened until the sheet splits — six ZUP layouts gave 0.2313–0.2335 mm per unit (the order above: 792 units, 183.2 mm), and the page count on A4 portrait with 10 mm margins matched this width for all six.
- **mxl-compile targets.** 820 / 1 196 units are the widths mxl-compile gives a new layout with `"page": "A4-portrait"` / `"A4-landscape"`: the A4 print width with 10 mm margins (190 / 277 mm). Layouts compiled to them measured 189.0 mm (portrait target, 817 units) and 274.7 mm (landscape target, 1 187 units) and printed one page wide.
- **Print settings.** A spreadsheet `Template.xml` may store `printSettings` — orientation, `fitToPage`, scale, margins (in ZUP 729 of 2 882 layouts, 579 of them with `fitToPage` true). The A4 line takes the margins from there (10 mm a side when absent); the verdict follows them: `fitToPage` → the reduction to the page width; a fixed orientation and scale → whether the print width is exceeded.
- **The printing code decides last.** A printed form is a new spreadsheet the code fills from the layout; it may set `ТабличныйДокумент.АвтоМасштаб = Истина` (`FitToPage`) or the orientation itself. ZUP does so in 208 places in 110 modules (and in the common print context of `УправлениеПечатьюБЗК`), which is why vendor forms wider than the sheet print fine. The tool does not read code: without stored settings it gives the width at 100 % and the reduction a fit to the page width would apply.

### Scale of the picture

A column-width unit is drawn as 7/8 of a pixel at zoom 1 (0.2315 mm at 96 dpi, as measured above). Row height in the XML is points × 4 (`ВысотаСтроки` is in points; single-line rows of a 9–10 pt font are 60–75 in the XML). Fonts are drawn at their point size. So the proportions of text to cell follow the layout; the picture's absolute size is not a claim.

### Exit codes

`0` — the PNG is written. `1` — nothing written: not Windows, file not found, not a spreadsheet layout (for example a DCS template), unknown `-Area`, a bad parameter.
