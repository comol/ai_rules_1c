---
name: md-to-docx
description: "Convert a Markdown file to DOCX (Word). Use when the user asks to convert .md to .docx, generate a Word document from Markdown, or export Markdown notes to Word."
---

# md-to-docx — Markdown to DOCX conversion

Converts a Markdown file to a Word document (`.docx`) preserving headings, tables, lists, code blocks, links and inline images.

## Usage

```
/md-to-docx <input.md> [output.docx]
```

| Parameter | Required | Description |
|-----------|:--------:|-------------|
| `input.md` | yes | Path to the source Markdown file |
| `output.docx` | no | Path to the output file (default: alongside source, `.md` → `.docx`) |

If the path is not provided — ask the user.

## Dependencies

- **Node.js** — to run the script
- **npm package `docx`** — install globally: `npm install -g docx`

## Command

PowerShell (Windows, default for this project):

```powershell
$env:NODE_PATH = (npm root -g)
node skills/md-to-docx/scripts/md_to_docx.js "<input.md>" "[output.docx]"
```

Bash (macOS / Linux):

```bash
NODE_MODULES=$(npm root -g)
NODE_PATH="$NODE_MODULES" node skills/md-to-docx/scripts/md_to_docx.js "<input.md>" "[output.docx]"
```

## Supported Markdown features

- Headings (H1–H6) with styles and colors
- Tables with header row
- Code blocks (monospace font, gray background)
- Lists: bulleted and numbered (with nesting)
- Inline formatting: **bold**, *italic*, `code`, [links](url)
- Images (`![alt](path)`) — resolved relative to the source MD folder
- Horizontal rules (`---`)
- Headers/footers: filename in the top, page number in the bottom

If an image is not found — a red text placeholder is inserted.

## Output example

```
Created: output.docx (45231 bytes, 42 blocks)
```
