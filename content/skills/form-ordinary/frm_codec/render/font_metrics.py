"""Ширины знаков шрифта растеризатора (TrueType: `head`, `hhea`, `hmtx`, `cmap` формата 4), чтобы подогнать знак PNG под ширину по таблице форм (`glyph_text`).

В предприятии знак рисуется с хинтингом и занимает ячейку `hdmx` целиком; растеризатор рисует контур без хинтинга, и у широких знаков («Ф», «Ж», «/») между знаком и
следующим остаётся зазор. `advance(ch, ppem)` — ширина знака у растеризатора в px (дробная) либо `None`: шрифта нет, знака в нём нет, файл не разобран."""
import functools
import os
import pathlib
import struct
import subprocess

FACE = "Microsoft Sans Serif"
FALLBACKS = ("/System/Library/Fonts/Supplemental/Microsoft Sans Serif.ttf", "/Library/Fonts/Microsoft Sans Serif.ttf",
             "/usr/share/fonts/truetype/msttcorefonts/micross.ttf", "/usr/share/fonts/truetype/microsoft/micross.ttf")
WINDOWS_FONT_FILES = {False: "micross.ttf", True: "tahomabd.ttf"}      # каталог шрифтов Windows: `%WINDIR%\Fonts` (путь берётся из переменной окружения, не «C:»)


def windows_fonts(bold=False):
    """Путь к шрифту в `%WINDIR%\\Fonts` либо `None`, если переменной `WINDIR` нет или файла нет."""
    root = os.environ.get("WINDIR") or os.environ.get("SystemRoot")
    if not root:
        return None
    path = pathlib.Path(root) / "Fonts" / WINDOWS_FONT_FILES[bool(bold)]
    return str(path) if path.is_file() else None

# Жирная подпись в PNG рисуется Tahoma жирным (у Microsoft Sans Serif жирного начертания нет; `glyph_text.PNG_FACE_BOLD`), её ширины знаков — из этого файла.
FACE_BOLD = "Tahoma"
FALLBACKS_BOLD = ("/System/Library/Fonts/Supplemental/Tahoma Bold.ttf", "/Library/Fonts/Tahoma Bold.ttf",
                  "/usr/share/fonts/truetype/msttcorefonts/tahomabd.ttf", "/usr/share/fonts/truetype/microsoft/tahomabd.ttf")


def _path(bold=False):
    face, fallbacks = (FACE_BOLD, FALLBACKS_BOLD) if bold else (FACE, FALLBACKS)
    try:
        run = subprocess.run(["fc-match", "-f", "%{file}|%{family}|%{style}", f"{face}:bold" if bold else face], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
        file, _sep, rest = run.stdout.partition("|")
        family, _sep, style = rest.partition("|")
        if run.returncode == 0 and face.casefold() in family.casefold() and (not bold or "bold" in style.casefold()) and pathlib.Path(file).is_file():
            return file
    except (OSError, subprocess.SubprocessError):
        pass
    return next((p for p in fallbacks if pathlib.Path(p).is_file()), None) or windows_fonts(bold)


@functools.lru_cache(maxsize=2)
def _font(bold=False):
    """`(unitsPerEm, {код знака: ширина в единицах})` либо `None`."""
    path = _path(bold)
    if path is None:
        return None
    try:
        data = pathlib.Path(path).read_bytes()
        count = struct.unpack(">H", data[4:6])[0]
        tables = {data[12 + 16 * k:16 + 16 * k].decode("latin-1"): struct.unpack(">II", data[20 + 16 * k:28 + 16 * k]) for k in range(count)}
        upm = struct.unpack(">H", data[tables["head"][0] + 18:tables["head"][0] + 20])[0]
        metrics = struct.unpack(">H", data[tables["hhea"][0] + 34:tables["hhea"][0] + 36])[0]
        hmtx = tables["hmtx"][0]
        widths = [struct.unpack(">H", data[hmtx + 4 * g:hmtx + 4 * g + 2])[0] for g in range(metrics)]
        cmap = tables["cmap"][0]
        subtables = [struct.unpack(">HHI", data[cmap + 4 + 8 * k:cmap + 12 + 8 * k]) for k in range(struct.unpack(">H", data[cmap + 2:cmap + 4])[0])]
        offset = next(o for plat, enc, o in subtables if (plat, enc) in ((3, 1), (0, 3), (0, 4)))
        at = cmap + offset
        if struct.unpack(">H", data[at:at + 2])[0] != 4:
            return None
        segs = struct.unpack(">H", data[at + 6:at + 8])[0] // 2
        ends = struct.unpack(f">{segs}H", data[at + 14:at + 14 + 2 * segs])
        starts = struct.unpack(f">{segs}H", data[at + 16 + 2 * segs:at + 16 + 4 * segs])
        deltas = struct.unpack(f">{segs}h", data[at + 16 + 4 * segs:at + 16 + 6 * segs])
        range_at = at + 16 + 6 * segs
        ranges = struct.unpack(f">{segs}H", data[range_at:range_at + 2 * segs])
        out = {}
        for k in range(segs):
            for code in range(starts[k], ends[k] + 1):
                if code == 0xFFFF:
                    continue
                if ranges[k] == 0:
                    glyph = (code + deltas[k]) & 0xFFFF
                else:
                    pos = range_at + 2 * k + ranges[k] + 2 * (code - starts[k])
                    glyph = struct.unpack(">H", data[pos:pos + 2])[0]
                    glyph = (glyph + deltas[k]) & 0xFFFF if glyph else 0
                if glyph:
                    out[code] = widths[min(glyph, metrics - 1)]
        return upm, out
    except (OSError, KeyError, StopIteration, struct.error, UnicodeDecodeError, IndexError):
        return None


def advance(ch, ppem, bold=False):
    """Ширина знака `ch` у растеризатора при `ppem` px (дробная) либо `None`; `bold` — у жирной гарнитуры (Tahoma жирный)."""
    font = _font(bold)
    if font is None or len(ch) != 1:
        return None
    width = font[1].get(ord(ch))
    return None if width is None else width * ppem / font[0]
