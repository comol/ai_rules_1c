# 1C MXL Render — PNG Sketch and A4 Width Verdict

Draws a spreadsheet layout (`Template.xml`) as a PNG and says whether its width fits an A4 page. It is a preview for the agent — to look at a layout it compiled, decompiled or is about to fill — not the platform's rendering. Tool: `mxl-render` v1.0, a local tool of this ruleset (not vendored from cc-1c-skills). The other MXL tools (compile, decompile, info, validate) are in [mxl-manage.md](mxl-manage.md).

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

```
=== MXL render: ВосстановлениеВДолжности.ПФ_MXL_ПриказОВосстановленииНаРаботе ===
PNG: C:\Users\...\Temp\mxl-render\ВосстановлениеВДолжности.ПФ_MXL_ПриказОВосстановленииНаРаботе.png (839 x 1260 px)
Rows drawn: 1-55 of 55
Width (units of mxl-compile 'page'; whole layout):
  default column set: width 792 (33 of 33 columns used, 55 rows)
  A4-portrait (540): does not fit, 792 > 540; fits at 68%
  A4-landscape (780): does not fit, 792 > 780; fits at 98%
Verdict: wider than A4 landscape: print needs a scale of at most 98% or fitToPage
Print settings of the layout: none (the code that prints may still set orientation or FitToPage)
```

A `Not drawn:` line lists what the picture leaves out for this layout (drawings, cell pictures, rotated text, style colours, hidden rows, header / footer).

### What the picture shows

- Column widths of every column set, row heights (explicit, or fitted to the text of the row), merges, fills, borders with their line style, fonts (face, size, bold, italic, underline), horizontal / vertical alignment, wrap, and `Auto` text spilling into empty neighbour cells.
- Cell content as the designer shows it: static text, a parameter as `<Name>`, a template text with its `[Name]` substitutions. Texts in the layout's current language.
- Row numbers and column numbers (default column set) in the margins; `Rows` areas as labelled bands on the left, `Columns` areas on top, `Rectangle` areas as dashed outlines; drawings as dashed outlines with their type and name; a red corner on cells with a note.
- Not drawn: picture contents, charts, rotated text (drawn horizontally), colours given by style elements (drawn neutral), header / footer, print area, row / column groups, conditional appearance.

### Width verdict

- The targets are mxl-compile's `page` targets — A4-portrait **540**, A4-landscape **780** — the widths the rules compile layouts to.
- A layout's width is the sum of its columns up to the last one that shows something: a text, a parameter, a fill, a line that is not `None`, a merge, a column or rectangle area. Format-only cells further right do not count (ZUP's SZV-KORR keeps them up to the 78th column of a 13-column set). Each column set is reported; the widest one is the verdict.
- Vendor print forms are usually wider than these targets and are printed scaled: the printing code sets `ТабличныйДокумент.АвтоМасштаб = Истина` (ZUP does so for the order in the example above). "Does not fit" states the width at 100 % and the scale it needs; it is not an error. The layout's own `printSettings` (orientation, scale, fitToPage, margins) are echoed for reference.

### Scale of the picture

Column width in the XML is 1/8 of the "average character" the platform measures widths in (`ОбластьЯчеекТабличногоДокумента.ШиринаКолонки`); it is drawn as one pixel at 96 dpi (0.75 pt). That is the scale at which the static texts of ZUP's vendor layouts fit the table cells they sit in (95 % of 2 148 measured cells). Row height in the XML is points × 4 (`ВысотаСтроки` is in points; single-line rows of a 9–10 pt font are 60–75 in the XML). Fonts are drawn at their point size. So the picture's proportions of text to cell follow the layout; its absolute size in millimetres is not claimed.

### Exit codes

`0` — the PNG is written. `1` — nothing written: not Windows, file not found, not a spreadsheet layout (for example a DCS template), unknown `-Area`, a bad parameter.
