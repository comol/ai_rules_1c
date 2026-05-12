#!/usr/bin/env node
/**
 * md_to_docx.js — Convert Markdown to DOCX with hyperlinks, tables, code blocks, images.
 *
 * Usage: NODE_PATH=<global_node_modules> node md_to_docx.js input.md [output.docx]
 *        If output is omitted, replaces .md with .docx
 *
 * Requires: npm install -g docx
 */

const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, ExternalHyperlink, ImageRun,
  HeadingLevel, BorderStyle, WidthType, ShadingType, PageNumber,
  LevelFormat, PageBreak
} = require("docx");

// --- Args ---
const inputPath = process.argv[2];
if (!inputPath) {
  console.error("Usage: node md_to_docx.js input.md [output.docx]");
  process.exit(1);
}
const outputPath = process.argv[3] || inputPath.replace(/\.md$/i, ".docx");
const docTitle = path.basename(inputPath, path.extname(inputPath));
const inputDir = path.dirname(path.resolve(inputPath));

if (!fs.existsSync(inputPath)) {
  console.error(`Error: file not found: ${inputPath}`);
  process.exit(1);
}
const md = fs.readFileSync(inputPath, "utf-8");
// Strip YAML front matter (---...---)
let content = md;
if (content.startsWith("---\n") || content.startsWith("---\r\n")) {
  const endIdx = content.indexOf("\n---", 3);
  if (endIdx !== -1) {
    content = content.slice(content.indexOf("\n", endIdx + 4) + 1);
  }
}
const lines = content.split("\n");

// --- Parse markdown into blocks ---
const blocks = [];
let i = 0;
let inCodeBlock = false;
let codeLines = [];
let codeLang = "";
let inTable = false;
let tableRows = [];

function flushTable() {
  if (inTable && tableRows.length > 0) {
    blocks.push({ type: "table", rows: tableRows });
    tableRows = [];
    inTable = false;
  }
}

while (i < lines.length) {
  const line = lines[i];

  // Code block fences
  if (line.startsWith("```")) {
    if (inCodeBlock) {
      blocks.push({ type: "code", text: codeLines.join("\n"), lang: codeLang });
      codeLines = [];
      inCodeBlock = false;
      codeLang = "";
    } else {
      flushTable();
      inCodeBlock = true;
      codeLang = line.slice(3).trim();
    }
    i++;
    continue;
  }
  if (inCodeBlock) {
    codeLines.push(line);
    i++;
    continue;
  }

  // Table row
  if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
    if (!inTable) inTable = true;
    // Skip separator rows (|---|---|)
    if (/^\|[\s\-:|]+\|$/.test(line.trim())) { i++; continue; }
    const cells = line.split("|").slice(1, -1).map(c => c.trim());
    tableRows.push(cells);
    i++;
    continue;
  } else {
    flushTable();
  }

  // Heading
  const hMatch = line.match(/^(#{1,6})\s+(.*)/);
  if (hMatch) {
    blocks.push({ type: "heading", level: hMatch[1].length, text: hMatch[2] });
    i++;
    continue;
  }

  // Horizontal rule
  if (/^---+\s*$/.test(line.trim())) {
    blocks.push({ type: "hr" });
    i++;
    continue;
  }

  // Empty line
  if (line.trim() === "") { i++; continue; }

  // List item (bullet)
  const bulletMatch = line.match(/^(\s*)[-*]\s+(.*)/);
  if (bulletMatch) {
    const indent = Math.floor((bulletMatch[1] || "").length / 2);
    blocks.push({ type: "bullet", indent, text: bulletMatch[2] });
    i++;
    continue;
  }

  // List item (numbered)
  const numMatch = line.match(/^(\s*)\d+\.\s+(.*)/);
  if (numMatch) {
    const indent = Math.floor((numMatch[1] || "").length / 2);
    blocks.push({ type: "numbered", indent, text: numMatch[2] });
    i++;
    continue;
  }

  // Standalone image line: ![alt](path)
  const imgMatch = line.match(/^!\[([^\]]*)\]\(((?:[^()]*|\([^)]*\))*)\)\s*$/);
  if (imgMatch) {
    blocks.push({ type: "image", alt: imgMatch[1], src: imgMatch[2] });
    i++;
    continue;
  }

  // Regular paragraph
  blocks.push({ type: "paragraph", text: line });
  i++;
}
flushTable();

// --- Inline markdown parser ---
// Handles: **bold**, *italic*, `code`, [text](url) with balanced parens in URLs
function parseInline(text) {
  const runs = [];
  const re = /(\*\*(.+?)\*\*)|(\[([^\]]+)\]\(((?:[^()]*|\([^)]*\))*)\))|(`([^`]+)`)|(\*(.+?)\*)/g;
  let lastIndex = 0;
  let m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > lastIndex) {
      runs.push({ text: text.slice(lastIndex, m.index) });
    }
    if (m[1]) {
      runs.push({ text: m[2], bold: true });
    } else if (m[3]) {
      runs.push({ text: m[4], link: m[5] });
    } else if (m[6]) {
      runs.push({ text: m[7], code: true });
    } else if (m[8]) {
      runs.push({ text: m[9], italic: true });
    }
    lastIndex = re.lastIndex;
  }
  if (lastIndex < text.length) {
    runs.push({ text: text.slice(lastIndex) });
  }
  return runs;
}

// Convert parsed inline to docx TextRun/ExternalHyperlink
function makeRuns(text, fontSize) {
  const sz = fontSize || 22;
  const parsed = parseInline(text);
  return parsed.map(r => {
    if (r.link) {
      if (r.link.startsWith("#")) {
        // Anchor links -> plain text (no bookmark targets in generated docs)
        return new TextRun({ text: r.text, font: "Arial", size: sz });
      }
      let link = r.link;
      if (!/^https?:\/\//.test(link) && !/^mailto:/.test(link)) {
        link = decodeURIComponent(link);
      }
      return new ExternalHyperlink({
        children: [new TextRun({ text: r.text, style: "Hyperlink", font: "Arial", size: sz })],
        link,
      });
    }
    const opts = { text: r.text, font: r.code ? "Consolas" : "Arial", size: r.code ? sz - 2 : sz };
    if (r.bold) opts.bold = true;
    if (r.italic) opts.italics = true;
    if (r.code) opts.shading = { type: ShadingType.CLEAR, fill: "F0F0F0" };
    return new TextRun(opts);
  });
}

// --- Image helpers ---
function resolveImagePath(src) {
  if (path.isAbsolute(src)) return src;
  // Decode percent-encoding
  const decoded = decodeURIComponent(src);
  return path.resolve(inputDir, decoded);
}

function getImageType(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  const map = { ".png": "png", ".jpg": "jpg", ".jpeg": "jpeg", ".gif": "gif", ".bmp": "bmp", ".svg": "svg" };
  return map[ext] || "png";
}

function tryLoadImage(src) {
  const filePath = resolveImagePath(src);
  if (!fs.existsSync(filePath)) {
    console.warn(`  Warning: image not found: ${filePath}`);
    return null;
  }
  const data = fs.readFileSync(filePath);
  const type = getImageType(filePath);
  // Get dimensions (simple approach: fit within content width)
  // Default: max 600px wide, auto height (assume 4:3 if unknown)
  let width = 600;
  let height = 450;
  // Try to read PNG/JPEG dimensions from header
  if (type === "png" && data.length >= 24) {
    width = data.readUInt32BE(16);
    height = data.readUInt32BE(20);
  } else if ((type === "jpg" || type === "jpeg") && data.length > 2) {
    // Simple JPEG dimension reader
    let off = 2;
    while (off < data.length - 1) {
      if (data[off] !== 0xFF) break;
      const marker = data[off + 1];
      if (marker === 0xC0 || marker === 0xC2) {
        height = data.readUInt16BE(off + 5);
        width = data.readUInt16BE(off + 7);
        break;
      }
      const segLen = data.readUInt16BE(off + 2);
      off += 2 + segLen;
    }
  }
  // Scale to fit content width (max ~6 inches = 576px at 96dpi)
  const maxWidth = 576;
  if (width > maxWidth) {
    const scale = maxWidth / width;
    width = maxWidth;
    height = Math.round(height * scale);
  }
  return { data, type, width, height };
}

// --- Build document ---
const children = [];
const headingMap = {
  1: HeadingLevel.HEADING_1, 2: HeadingLevel.HEADING_2,
  3: HeadingLevel.HEADING_3, 4: HeadingLevel.HEADING_4,
  5: HeadingLevel.HEADING_5, 6: HeadingLevel.HEADING_6,
};
const border = { style: BorderStyle.SINGLE, size: 1, color: "999999" };
const cellBorders = { top: border, bottom: border, left: border, right: border };
const PAGE_WIDTH = 12240; // US Letter
const MARGIN = 1440; // 1 inch
const CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN; // 9360

for (const block of blocks) {
  switch (block.type) {
    case "heading":
      children.push(new Paragraph({
        heading: headingMap[block.level],
        children: makeRuns(block.text),
        spacing: { before: block.level <= 2 ? 360 : 240, after: 120 },
      }));
      break;

    case "paragraph":
      children.push(new Paragraph({
        children: makeRuns(block.text),
        spacing: { before: 80, after: 80 },
      }));
      break;

    case "bullet":
      children.push(new Paragraph({
        numbering: { reference: "bullets", level: Math.min(block.indent, 1) },
        children: makeRuns(block.text),
        spacing: { before: 40, after: 40 },
      }));
      break;

    case "numbered":
      children.push(new Paragraph({
        numbering: { reference: "numbers", level: Math.min(block.indent, 1) },
        children: makeRuns(block.text),
        spacing: { before: 40, after: 40 },
      }));
      break;

    case "code": {
      const codeRuns = block.text.split("\n").flatMap((line, idx, arr) => {
        const parts = [new TextRun({ text: line || " ", font: "Consolas", size: 18 })];
        if (idx < arr.length - 1) parts.push(new TextRun({ font: "Consolas", size: 18, break: 1 }));
        return parts;
      });
      children.push(new Paragraph({
        children: codeRuns,
        shading: { type: ShadingType.CLEAR, fill: "F5F5F5" },
        spacing: { before: 120, after: 120 },
        indent: { left: 360 },
      }));
      break;
    }

    case "table": {
      const numCols = block.rows[0] ? block.rows[0].length : 1;
      const colWidth = Math.floor(CONTENT_WIDTH / numCols);
      const colWidths = Array(numCols).fill(colWidth);
      colWidths[numCols - 1] = CONTENT_WIDTH - colWidth * (numCols - 1);

      const tRows = block.rows.map((cells, rowIdx) =>
        new TableRow({
          children: cells.map((cell, colIdx) => {
            const isHeader = rowIdx === 0;
            return new TableCell({
              borders: cellBorders,
              width: { size: colWidths[colIdx], type: WidthType.DXA },
              shading: isHeader ? { type: ShadingType.CLEAR, fill: "D9E2F3" } : undefined,
              margins: { top: 40, bottom: 40, left: 80, right: 80 },
              children: [new Paragraph({
                children: isHeader
                  ? [new TextRun({ text: cell, bold: true, font: "Arial", size: 20 })]
                  : makeRuns(cell, 20),
                spacing: { before: 20, after: 20 },
              })],
            });
          }),
        })
      );

      children.push(new Table({
        width: { size: CONTENT_WIDTH, type: WidthType.DXA },
        columnWidths: colWidths,
        rows: tRows,
      }));
      break;
    }

    case "image": {
      const img = tryLoadImage(block.src);
      if (img) {
        children.push(new Paragraph({
          children: [new ImageRun({
            type: img.type,
            data: img.data,
            transformation: { width: img.width, height: img.height },
            altText: { title: block.alt || "Image", description: block.alt || "", name: block.alt || "image" },
          })],
          spacing: { before: 120, after: 120 },
          alignment: AlignmentType.CENTER,
        }));
        // Caption if alt text exists
        if (block.alt) {
          children.push(new Paragraph({
            children: [new TextRun({ text: block.alt, font: "Arial", size: 18, italics: true, color: "666666" })],
            alignment: AlignmentType.CENTER,
            spacing: { before: 40, after: 120 },
          }));
        }
      } else {
        // Fallback: show as text placeholder
        children.push(new Paragraph({
          children: [new TextRun({ text: `[Image: ${block.alt || block.src}]`, font: "Arial", size: 20, color: "CC0000" })],
          spacing: { before: 80, after: 80 },
        }));
      }
      break;
    }

    case "hr":
      children.push(new Paragraph({
        border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "CCCCCC", space: 1 } },
        spacing: { before: 200, after: 200 },
        children: [],
      }));
      break;
  }
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: "Arial", color: "1F3864" },
        paragraph: { spacing: { before: 360, after: 120 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, font: "Arial", color: "2E75B6" },
        paragraph: { spacing: { before: 300, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Arial", color: "404040" },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 2 } },
      { id: "Heading4", name: "Heading 4", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: "404040" },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 3 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets",
        levels: [
          { level: 0, format: LevelFormat.BULLET, text: "\u2013", alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
          { level: 1, format: LevelFormat.BULLET, text: "-", alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 1440, hanging: 360 } } } },
        ] },
      { reference: "numbers",
        levels: [
          { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
          { level: 1, format: LevelFormat.DECIMAL, text: "%2.", alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 1440, hanging: 360 } } } },
        ] },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: PAGE_WIDTH, height: 15840 },
        margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          children: [new TextRun({ text: docTitle, font: "Arial", size: 18, color: "999999" })],
          alignment: AlignmentType.RIGHT,
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          children: [
            new TextRun({ text: "Стр. ", font: "Arial", size: 18, color: "999999" }),
            new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 18, color: "999999" }),
          ],
          alignment: AlignmentType.CENTER,
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outputPath, buffer);
  console.log(`Created: ${outputPath} (${buffer.length} bytes, ${children.length} blocks)`);
}).catch(err => {
  console.error("Error:", err.message);
  process.exit(1);
});
