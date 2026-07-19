---
name: md-to-docx
description: "Convert a Markdown file to DOCX (Word). Use when the user asks to convert .md to .docx, generate a Word document from Markdown, or export Markdown notes to Word."
---

# md-to-docx — Markdown to DOCX conversion

Converts a Markdown file to a Word document (`.docx`) preserving headings, tables, lists, code blocks, links and inline images.

## Usage

```
/md-to-docx <input.md> [output.docx] [--author "Name"] [--title "Title"] [--no-shading]
```

| Parameter | Required | Description |
|-----------|:--------:|-------------|
| `input.md` | yes | Path to the source Markdown file |
| `output.docx` | no | Path to the output file (default: alongside source, `.md` → `.docx`) |
| `--author` | no | Document author. Written to core properties (`dc:creator` + `cp:lastModifiedBy`). Also accepts the `--author=Name` form |
| `--title` | no | Document title in core properties and in the header. Default: input file name without extension |
| `--no-shading` | no | Disables the grey background for inline `code` and fenced ``` code blocks. Alias: `--shading=off`. On by default. Does not affect the table header (it keeps its structural fill) |

If the path is not provided — ask the user. The `--author`, `--title`, `--no-shading` flags are optional — pass them only when the user explicitly asks for an author, a custom title, or removal of code shading.

## Dependencies

- **Node.js** — to run the script
- **npm package `docx`** — pinned by this skill's `package-lock.json`; install locally with `npm ci --prefix "<skill-dir>"`

## Command

`<skill-dir>` below is the directory of this skill: `content/skills/md-to-docx/` in the `1c-rules` source repo, or `<tool>/skills/md-to-docx/` after installation (e.g. `.cursor/skills/md-to-docx/`, `.claude/skills/md-to-docx/`).

PowerShell (Windows, default for this project):

```powershell
npm ci --prefix "<skill-dir>"
node "<skill-dir>/scripts/md_to_docx.js" "<input.md>" "[output.docx]"

# With author and title
node "<skill-dir>/scripts/md_to_docx.js" "<input.md>" "[output.docx]" --author "I. Ivanov" --title "Analytical note"

# Without the grey code background
node "<skill-dir>/scripts/md_to_docx.js" "<input.md>" "[output.docx]" --no-shading
```

Bash (macOS / Linux):

```bash
npm ci --prefix "<skill-dir>"
node "<skill-dir>/scripts/md_to_docx.js" "<input.md>" "[output.docx]"
```

## Supported Markdown features

- Headings (H1–H6) with styles and colors
- Tables with header row
- Code blocks (monospace font, gray background)
- Lists: bulleted and numbered (with nesting)
- Inline formatting: **bold**, *italic*, `code`, [links](url)
- Internal anchor links: `<a id="name"></a>` before a heading becomes a bookmark; `[text](#name)` links resolve to it (external `http(s)` / `mailto:` links stay external)
- Images (`![alt](path)`) — resolved relative to the source MD folder
- Horizontal rules (`---`)
- Headers/footers: title in the top, page number in the bottom
- Core properties: author and title (via `--author` / `--title`)

If an image is not found — a red text placeholder is inserted.

## Output example

```
Created: output.docx (45231 bytes, 42 blocks)
```
