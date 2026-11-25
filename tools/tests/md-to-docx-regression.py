#!/usr/bin/env python3
"""Generate real DOCX files and check list, image and alignment OOXML offline.

Requires Node.js and ``npm ci --prefix content/skills/md-to-docx``.
Run: python -B tools/tests/md-to-docx-regression.py
Set MD_TO_DOCX_NODE to choose Node; --keep-work-dir retains render fixtures.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile
import zlib


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "content/skills/md-to-docx/scripts/md_to_docx.js"
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "dc": "http://purl.org/dc/elements/1.1/",
}
W = "{" + NS["w"] + "}"
KEEP_WORK_DIR = False


def png(path: Path, width: int, height: int) -> None:
    """A valid solid RGB image with real dimensions; no imaging dependency."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    pixels = (b"\0" + b"\x46\x82\xb4" * width) * height
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(pixels))
        + chunk(b"IEND", b"")
    )


def text(paragraph: ET.Element) -> str:
    return "".join(part.text or "" for part in paragraph.findall(".//w:t", NS))


class Docx:
    def __init__(self, path: Path):
        with ZipFile(path) as archive:
            # Malformed XML in any part is a failure, not just document.xml.
            self.parts = {
                name: ET.fromstring(archive.read(name))
                for name in archive.namelist() if name.endswith((".xml", ".rels"))
            }
        self.document = self.parts["word/document.xml"]
        self.paragraphs = {text(p): p for p in self.document.findall(".//w:p", NS)}
        numbering = self.parts["word/numbering.xml"]
        abstracts = {n.get(W + "abstractNumId"): n for n in numbering.findall("w:abstractNum", NS)}
        self.numbers = {}
        for number in numbering.findall("w:num", NS):
            abstract_id = number.find("w:abstractNumId", NS).get(W + "val")
            self.numbers[number.get(W + "numId")] = (number, abstracts[abstract_id])

    def list_info(self, label: str) -> tuple[str, int, int, str]:
        properties = self.paragraphs[label].find("w:pPr/w:numPr", NS)
        if properties is None:
            raise AssertionError(f"Missing list numbering for {label!r}")
        num_id = properties.find("w:numId", NS).get(W + "val")
        level = int(properties.find("w:ilvl", NS).get(W + "val"))
        number, abstract = self.numbers[num_id]
        definition = abstract.find(f"w:lvl[@w:ilvl='{level}']", NS)
        start = definition.find("w:start", NS)
        override = number.find(f"w:lvlOverride[@w:ilvl='{level}']/w:startOverride", NS)
        start_value = int((override if override is not None else start).get(W + "val"))
        return num_id, level, start_value, definition.find("w:numFmt", NS).get(W + "val")

    def alignment(self, label: str) -> str | None:
        alignment = self.paragraphs[label].find("w:pPr/w:jc", NS)
        return None if alignment is None else alignment.get(W + "val")


class MarkdownDocxRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = os.environ.get("MD_TO_DOCX_NODE") or shutil.which("node")
        if not cls.node:
            raise RuntimeError("Node.js is required for the DOCX regressions")
        cls.work = Path(tempfile.mkdtemp(prefix="md-to-docx-regression-"))
        for name, width, height in [("tall", 400, 4000), ("wide", 2400, 400), ("small", 80, 40)]:
            png(cls.work / f"{name}.png", width, height)
        cls.source = cls.work / "fixture.md"
        cls.source.write_text("""<a id="overview"></a>
# Heading

Wrapped paragraph
continues here with **bold**, *italic*, `inline`, [internal](#overview) and [external](https://example.com).

Nested **bold `Catalog.Items` and [bold link](https://example.com)** with *italic `inner`* end.

4. Parent one
   continued line
   7. Child one
   1. Child two
1. Parent two
   - Child bullet
   3. Child three
   1. Child four
1. Parent three
   1. Child reset

1. Parent four

Separate paragraph.

1. New first
1. New second
   - Nested bullet
1. New third

- Bullet parent one
  5. Under bullet one
  1. Under bullet two
- Bullet parent two
  2. Under bullet reset

> 8. Quote first
>    wrapped quote line
>    3. Quote child first
>    1. Quote child second
> 1. Quote second

> 2. Separate quote

1. After quote

> Quote paragraph
> wraps here.
> - Quote bullet

| Column |
| --- |
| Cell `code` |

6. After table
1. After table second

```text
code block
```

0. After code
1. After code second

---

1. After rule

![Tall caption](tall.png)
![](tall.png)
![Wide caption](wide.png)
![Small caption](small.png)
![Missing caption](missing.png)
""", encoding="utf-8")
        cls.default = cls.generate("default")

    @classmethod
    def tearDownClass(cls):
        if KEEP_WORK_DIR:
            print(f"DOCX fixtures: {cls.work}")
        else:
            shutil.rmtree(cls.work)

    @classmethod
    def generate(cls, name, *flags):
        output = cls.work / f"{name}.docx"
        result = subprocess.run(
            [cls.node, str(SCRIPT), str(cls.source), str(output),
             "--author", "Regression Author", "--title", "Regression document", *flags],
            capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        if result.returncode:
            raise AssertionError(f"DOCX generation failed: {result.stdout}\n{result.stderr}")
        return Docx(output)

    def assert_list(self, labels, expected_start):
        items = [self.default.list_info(label) for label in labels]
        self.assertEqual(len({item[:2] for item in items}), 1, labels)
        self.assertEqual(items[0][2:], (expected_start, "decimal"))
        return items[0][0]

    def test_independent_and_nested_lists(self):
        scopes = [
            self.assert_list(["Parent one continued line", "Parent two", "Parent three", "Parent four"], 4),
            self.assert_list(["Child one", "Child two"], 7),
            self.assert_list(["Child three", "Child four"], 3),
            self.assert_list(["Child reset"], 1),
            self.assert_list(["New first", "New second", "New third"], 1),
            self.assert_list(["Under bullet one", "Under bullet two"], 5),
            self.assert_list(["Under bullet reset"], 2),
            self.assert_list(["After table", "After table second"], 6),
            self.assert_list(["After code", "After code second"], 0),
            self.assert_list(["After rule"], 1),
        ]
        self.assertEqual(len(set(scopes)), len(scopes), "Independent lists must have independent counters")
        self.assertEqual(self.default.list_info("Parent two")[1], 0)
        self.assertEqual(self.default.list_info("Child one")[1], 1)

    def test_quote_list_scopes(self):
        scopes = [
            self.assert_list(["Quote first wrapped quote line", "Quote second"], 8),
            self.assert_list(["Quote child first", "Quote child second"], 3),
            self.assert_list(["Separate quote"], 2),
            self.assert_list(["After quote"], 1),
        ]
        self.assertEqual(len(set(scopes)), len(scopes))
        for label in ["Quote second", "Quote bullet", "Quote paragraph wraps here."]:
            self.assertIsNotNone(self.default.paragraphs[label].find("w:pPr/w:pBdr/w:left", NS))

    def test_justify_flags_and_default(self):
        labels = ["Separate paragraph.", "New first", "Nested bullet", "Quote second", "Quote bullet", "Quote paragraph wraps here."]
        for label in labels:
            self.assertIsNone(self.default.alignment(label))
        for name, flags in [("justify", ["--justify"]), ("align-equals", ["--align=justify"]), ("align-value", ["--align", "justify"])]:
            with self.subTest(flags=flags):
                doc = self.generate(name, *flags)
                for label in labels:
                    self.assertEqual(doc.alignment(label), "both", label)
                for label in ["Heading", "Column", "Cell code", "code block"]:
                    self.assertIsNone(doc.alignment(label), label)
                self.assertEqual(doc.alignment("Tall caption"), "center")

    def test_images_fit_printable_page(self):
        doc = self.default.document
        size = doc.find("w:body/w:sectPr/w:pgSz", NS)
        margin = doc.find("w:body/w:sectPr/w:pgMar", NS)
        width = int(size.get(W + "w")) - int(margin.get(W + "left")) - int(margin.get(W + "right"))
        height = int(size.get(W + "h")) - int(margin.get(W + "top")) - int(margin.get(W + "bottom"))
        drawings = doc.findall(".//wp:inline", NS)
        self.assertEqual(len(drawings), 4)
        original_sizes = [(400, 4000), (400, 4000), (2400, 400), (80, 40)]
        extents = []
        for drawing, (source_w, source_h) in zip(drawings, original_sizes):
            extent = drawing.find("wp:extent", NS)
            cx, cy = int(extent.get("cx")), int(extent.get("cy"))
            self.assertGreater(cx, 0)
            self.assertGreater(cy, 0)
            self.assertLessEqual(cx, width * 635)
            self.assertLessEqual(cy + (120 + 120) * 635, height * 635)
            self.assertLessEqual(cx, source_w * 9525)
            self.assertLessEqual(cy, source_h * 9525)
            # Integer-pixel rounding permits at most one pixel of ratio error.
            self.assertLessEqual(abs(cx / 9525 - (cy / 9525) * source_w / source_h), 1 + source_w / source_h)
            extents.append((cx, cy))
        self.assertLess(extents[0][1], extents[1][1], "Caption must reserve height")
        self.assertEqual(extents[2][0], width * 635, "Width limit follows the page's actual margins")
        self.assertEqual(extents[3], (80 * 9525, 40 * 9525), "Small images must not be enlarged")
        self.assertIn("[Image: Missing caption]", self.default.paragraphs)

    def test_existing_document_features(self):
        doc = self.default
        paragraph = doc.paragraphs["Wrapped paragraph continues here with bold, italic, inline, internal and external."]
        self.assertIsNotNone(paragraph.find(".//w:b", NS))
        self.assertIsNotNone(paragraph.find(".//w:i", NS))
        self.assertIsNotNone(paragraph.find(".//w:shd", NS))
        self.assertEqual(paragraph.find("w:hyperlink[@w:anchor]", NS).get(W + "anchor"), "overview")
        heading = doc.paragraphs["Heading"]
        self.assertEqual(heading.find("w:bookmarkStart", NS).get(W + "name"), "overview")
        self.assertIsNotNone(heading.find("w:pPr/w:keepNext", NS))
        self.assertIsNotNone(doc.paragraphs["code block"].find("w:pPr/w:shd", NS))
        self.assertIsNotNone(doc.document.find(".//w:tbl/w:tr/w:tc/w:tcPr/w:shd", NS))
        core = doc.parts["docProps/core.xml"]
        self.assertEqual(core.find("dc:creator", NS).text, "Regression Author")
        self.assertEqual(core.find("dc:title", NS).text, "Regression document")
        self.assertIn("word/header1.xml", doc.parts)
        self.assertIn("word/footer1.xml", doc.parts)

    def test_markup_nested_in_bold_and_italic(self):
        # Without the nested parse the paragraph text keeps `...` and [..](..) literally.
        paragraph = self.default.paragraphs["Nested bold Catalog.Items and bold link with italic inner end."]
        runs = {"".join(t.text or "" for t in run.findall("w:t", NS)): run for run in paragraph.iter(W + "r")}
        code = runs["Catalog.Items"].find("w:rPr", NS)
        self.assertIsNotNone(code.find("w:b", NS), "code inside bold stays bold")
        self.assertEqual(code.find("w:rFonts", NS).get(W + "ascii"), "Consolas")
        self.assertIsNotNone(code.find("w:shd", NS))
        link = paragraph.find("w:hyperlink", NS)
        self.assertIsNotNone(link, "link inside bold is a hyperlink")
        self.assertIsNotNone(link.find("w:r/w:rPr/w:b", NS), "link inside bold stays bold")
        inner = runs["inner"].find("w:rPr", NS)
        self.assertIsNotNone(inner.find("w:i", NS), "code inside italic stays italic")
        self.assertEqual(inner.find("w:rFonts", NS).get(W + "ascii"), "Consolas")

    def test_no_shading_remains_independent_of_justify(self):
        doc = self.generate("no-shading", "--no-shading", "--justify")
        self.assertIsNone(doc.paragraphs["code block"].find("w:pPr/w:shd", NS))
        self.assertFalse(doc.document.findall(".//w:rPr/w:shd", NS))
        self.assertIsNotNone(doc.document.find(".//w:tbl/w:tr/w:tc/w:tcPr/w:shd", NS))
        self.assertEqual(doc.alignment("Separate paragraph."), "both")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-work-dir", action="store_true")
    options, remaining = parser.parse_known_args()
    KEEP_WORK_DIR = options.keep_work_dir
    unittest.main(argv=[__file__, *remaining], verbosity=2)
