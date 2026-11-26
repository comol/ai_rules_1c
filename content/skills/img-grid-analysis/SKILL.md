---
name: img-grid-analysis
description: "Overlay a numbered grid on an image to determine column proportions for layout generation. Use when creating MXL spreadsheet layouts from screenshots or scanned print forms."
---

# Image Grid Analysis — Grid Overlay for Layout Design

## Usage

```
img-grid-analysis <ImagePath> [-c COLS] [-o OUTPUT]
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| ImagePath | yes | — | Path to image (PNG, JPG) |
| -c COLS | no | 50 | Number of vertical divisions |
| -r ROWS | no | auto | Number of horizontal divisions (auto = square cells) |
| -o OUTPUT | no | `<name>-grid.<ext>` | Output path |

## Command

`<skill-dir>` below is the directory of this skill: `content/skills/img-grid-analysis/` in the `1c-rules` source repo, or `<tool>/skills/img-grid-analysis/` after installation (e.g. `.cursor/skills/img-grid-analysis/`).

```bash
python <skill-dir>/scripts/overlay-grid.py "<ImagePath>" [-c 50] [-o "<OutputPath>"]
```

Requires Python 3 with Pillow library (`pip install Pillow`).

## What It Does

1. Draws semi-transparent vertical (red) and horizontal (blue) lines
2. Numbers lines in separate fields at top and left (does not overlap content)
3. Every 5th and 10th line is brighter for easier counting

## How to Use the Result

### 1. Determine Column Boundaries

Look at the gridded image and note vertical boundary coordinates of each table column (in grid line numbers).

### 2. Find the Base Grid

If the form has multiple tables with different layouts (e.g., document header and main table), combine all boundary points. Each segment between adjacent boundaries is one MXL column.

Example for form M-11:
- Header: boundaries 0, 2, 4, 9, 14, 21, 28, 34, 40, 48
- Table: boundaries 0, 2, 4, 11, 16, 19, 23, 28, 32, 36, 42, 48
- Union: 0, 2, 4, 9, 11, 14, 16, 19, 21, 23, 28, 32, 34, 36, 40, 42, 48
- Result: **16 base columns** with proportions 2, 2, 5, 2, 3, 2, 3, 2, 2, 5, 4, 2, 2, 4, 2, 6

### 3. Write in JSON DSL

```json
{
  "columns": 16,
  "page": "A4-landscape",
  "columnWidths": {
    "1": "2x", "2": "2x", "3": "5x", "4": "2x", "5": "3x",
    "6": "2x", "7": "3x", "8": "2x", "9": "2x", "10": "5x",
    "11": "4x", "12": "2x", "13": "2x", "14": "4x", "15": "2x", "16": "6x"
  }
}
```

The `"page"` field allows the compiler to automatically calculate absolute widths from proportions.

### 4. Compile

`1c-mxl-compile` → `1c-mxl-validate` → `1c-mxl-info`

### 5. Compare with the source

On Windows, `1c-mxl-render` draws the compiled layout as a PNG (`1c-metadata-manage/docs/mxl-render.md`): put it beside the source image to check column proportions and wrapping.
