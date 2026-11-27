---
name: 1c-layout-from-excel
description: "Convert an Excel (.xlsx) print-form template into a 1C MXL layout via OfficeCLI structural inspection and 1c-metadata-manage mxl-compile, with a tabular data contract check."
---

# 1C Layout from Excel (via OfficeCLI)

Use this skill when a print form or report layout specification is supplied as an Excel file (`.xlsx`). Do **not** convert an `.xlsx` to a screenshot and fall back to `img-grid-analysis` by default — Excel already holds exact sheets, cells, merges, widths, borders, fonts, and number formats.

## 1. Preflight OfficeCLI

Verify `officecli` without triggering background updates (`OFFICECLI_SKIP_UPDATE=1`):

1. Resolve `officecli` from `PATH` or `%LOCALAPPDATA%\OfficeCLI\officecli.exe` (Windows) / `~/.local/bin/officecli` (macOS/Linux).
2. Probe `officecli --version` with `OFFICECLI_SKIP_UPDATE=1`.
3. If `officecli` is not installed, ask the user whether to install it via `content/commands/install-officecli.md` (`/install-officecli`). Do not install silently and do not pretend an uninspected `.xlsx` was read.

## 2. Structural Inspection with OfficeCLI

Inspect the workbook structure layer-by-layer using JSON output:

```powershell
$env:OFFICECLI_SKIP_UPDATE = '1'
officecli get "template.xlsx" / --json
officecli get "template.xlsx" /Sheet1 --json
officecli get "template.xlsx" /Sheet1/A1:M60 --json
```

Extract and record before drafting MXL JSON DSL:

- sheet name and active print range;
- column count, relative column widths, row heights;
- merged cell spans (`col`, `span`, `rowspan`);
- fonts, alignments, wrap flags, borders, fill colors, number/date formats;
- static labels vs dynamic placeholders (`[Param]` / `{Param}` / demo values) and repeating row blocks (header, table header, table row, totals, footer).

When visual confirmation of a complex block is genuinely needed, render a bounded preview with `officecli view "template.xlsx" screenshot --range "Sheet1!A1:M40" -o preview.png`.

## 3. Honest Fidelity Boundary (What Transfers vs What Does Not)

Separate the visual scaffold from runtime 1C logic:

- **Transfers into `mxl-compile` JSON DSL:** grid, merges, column widths (`columnWidths` / `columnSets`), row heights, fonts, borders, fills, alignments, text wrap, number formats, static texts, parameters (`param`) and template strings (`template`).
- **Does NOT transfer automatically:** Excel formulas (must be replaced by BSL / DCS calculations), freeze panes, auto-filters, conditional formatting rules, embedded charts, and 1C named areas (`ПолучитьОбласть("Шапка")`, `"Строка"`, `"Итого"`).

Never claim that an imported or converted Excel sheet is a finished DCS (`СКД`) layout or a lossless Excel round-trip.

## 4. Build and Validate `Template.xml`

Route all metadata and XML mutations through `content/skills/1c-metadata-manage/SKILL.md` (`docs/mxl-manage.md` and `docs/template-manage.md`) — never hand-write `Template.xml`:

1. Register a new template object with `add-template` when it does not exist yet.
2. Author the compact MXL JSON DSL definition (named `areas` top-to-bottom: `Title` / `Header` / `TableHeader` / `Row` / `Total` / `Footer`, `styles`, `fonts`, `columnWidths`).
3. Compile via `mxl-compile` → validate via `mxl-validate` → inspect areas and parameters via `mxl-info -WithText`.
4. Verify XML via Gate 5 (`verify_xml` with `object_type="Макет"`) when MCP is exposed.

## 5. Tabular Output Data Contract (Before Writing Fill Code)

Visual fidelity does not prove data correctness. Before writing BSL fill code or DCS binding for the new layout, establish a concise **data contract** and confirm the underlying query/dataset (via `1c-data-mcp` Gate 3a on a dev/test base when available):

| Layout parameter / column | Source field / expression | Empty / NULL rule | Row key / cardinality | Control total |
|---|---|---|---|---|
| `<ParamName>` | `<QueryField / Calc>` | `<required / 0 / "">` | `<unique key, 1 or N>` | `<sum / count / n/a>` |

Check six invariants on the dataset: (1) all fields exist with expected types, (2) row count matches active filters/period, (3) NULLs and empty refs handled, (4) no unintended duplicates by business key, (5) aggregate totals match independent query sums (not just sample rows), (6) sample boundary rows inspected. If no dev/test IB is available, record data-contract runtime verification as unverified under **Risks**.
