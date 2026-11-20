"""Визуальный осмотр: преобразование SVG в PNG и картинка «до | после» с пометками правки.

* `svg_to_png` преобразует SVG, полученный при рендере, в PNG первым найденным конвертером. Конвертер, который создаёт PNG
  другого размера, чем SVG, не используется (`qlmanage -t` вписывает рисунок в квадрат). Если конвертера нет, возникает
  `PngUnavailable` с указанием, что нужно установить.
* `compare` показывает две формы рядом по модели раскладки (`render.render`). Новые элементы обведены зелёным, сдвинутые или
  изменившие размер — оранжевым (на картинке «до» прежнее место обозначено пунктиром), удалённые — красным, переименованные — синим.
  Элементы сопоставляются по индексу (индекс при правке не меняется, его не повторяют два элемента формы), поэтому переименованный элемент —
  один элемент, а не «убран и новый»; элементы без индекса — по имени вместе с родителем (`Панель1/Поле`), а безымянные — по типу и порядку среди
  элементов с таким же именем у одного родителя.
"""
import os
import pathlib
import re
import shutil
import struct
import subprocess
import tempfile
from xml.sax.saxutils import escape

from frm_codec import render
from frm_codec.render import glyph_text

# Каталоги для поиска, кроме PATH: оболочка часто не знает про /opt/homebrew (macOS) и /usr/local.
EXTRA_DIRS = ("/opt/homebrew/bin", "/usr/local/bin")
WINDOWS_EXTS = (".exe", ".com")
INSTALL = "brew install librsvg (macOS), apt install librsvg2-bin (Debian/Ubuntu) или Inkscape / ImageMagick (Windows)"


def is_windows():
    return os.name == "nt"


def windows_dirs():
    """Обычные каталоги установки конвертеров на Windows: `%ProgramFiles%\\Inkscape\\bin`, `%ProgramFiles%\\ImageMagick-*` (и то же в `%ProgramFiles(x86)%`)."""
    out = []
    for var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        root = os.environ.get(var)
        if not root:
            continue
        out.append(os.path.join(root, "Inkscape", "bin"))
        out.extend(sorted(str(p) for p in pathlib.Path(root).glob("ImageMagick-*") if p.is_dir()))
    return tuple(dict.fromkeys(out))


def search_dirs():
    """Каталоги поиска сверх PATH: `EXTRA_DIRS`, на Windows ещё каталоги установки Inkscape и ImageMagick."""
    return tuple(EXTRA_DIRS) + (windows_dirs() if is_windows() else ())

NEW, MOVED, GONE, RENAMED, CHANGED = "#1b9e3a", "#e07b00", "#d32f2f", "#1565c0", "#7b1fa2"
MARGIN, GAP, TITLE, LEGEND = 12, 24, 20, 64


class PngUnavailable(ValueError):
    """PNG построить нельзя: конвертера нет или ни один из них не создал рисунок нужного размера. SVG при этом сохраняется."""


def find_tool(name):
    """Путь к программе: сначала ищется в PATH на момент вызова, затем в `EXTRA_DIRS`. Если программы нет, возвращается `None`."""
    found = shutil.which(name)
    if found:
        return found
    windows = is_windows()
    for folder in search_dirs():
        for ext in (WINDOWS_EXTS if windows else ("",)):       # на Windows право исполнения не показатель: файл ищется с расширением `.exe` или `.com`
            path = os.path.join(folder, name + ext)
            if os.path.isfile(path) and (windows or os.access(path, os.X_OK)):
                return path
    return None


def svg_size(svg):
    """Возвращает `(ширина, высота)` из корня SVG или `None`, если размеры прочитать не удалось."""
    root = re.search(r"<svg\b[^>]*>", svg)
    if not root:
        return None
    w = re.search(r"\bwidth=['\"]([0-9.]+)", root.group(0))
    h = re.search(r"\bheight=['\"]([0-9.]+)", root.group(0))
    return (round(float(w.group(1))), round(float(h.group(1)))) if w and h else None


def png_size(path):
    data = pathlib.Path(path).read_bytes()[:24]
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", data[16:24])


def _converters(src, dst, size):
    """Возвращает список `[(имя, команда, продолжение)]` в порядке перебора. Команда — список аргументов, первый из которых — путь к
    программе.
    """
    out = []
    rsvg = find_tool("rsvg-convert")
    if rsvg:
        out.append(("rsvg-convert", [rsvg, str(src), "-o", str(dst)], None))
    for name in (("magick",) if is_windows() else ("magick", "convert")):       # на Windows `convert.exe` в System32 — программа преобразования дисков, не ImageMagick
        found = find_tool(name)
        if found:
            out.append((name, [found, str(src), str(dst)], None))
    inkscape = find_tool("inkscape")
    if inkscape:
        out.append(("inkscape", [inkscape, str(src), "--export-type=png", f"--export-filename={dst}"], None))
    ql = find_tool("qlmanage")
    if ql:
        out.append(("qlmanage", [ql, "-t", "-s", str(max(size)), "-o", str(pathlib.Path(dst).parent), str(src)],
                    pathlib.Path(dst).parent / (pathlib.Path(src).name + ".png")))
    return out


def svg_to_png(svg, png_path):
    """Записывает `png_path` из текста `svg` первым подходящим конвертером и возвращает его имя. Конвертер подходит, если созданный
    им PNG существует и по размеру равен SVG. Если конвертера нет или все создали неподходящий рисунок, возникает
    `PngUnavailable` с причинами. Недописанный PNG не остаётся.
    """
    size = svg_size(svg)
    if size is None:
        raise PngUnavailable("в SVG не прочитан размер корня — переводить в PNG нечего")
    png_path = pathlib.Path(png_path)
    tried = []
    with tempfile.TemporaryDirectory(prefix="frm_preview_") as work:
        src = pathlib.Path(work, "in.svg")
        src.write_text(glyph_text.exact(svg), encoding="utf-8")     # надписи по знакам: ширина по метрике шрифта форм, а не запасного шрифта растеризатора
        for name, cmd, produced in _converters(src, pathlib.Path(work, "out.png"), size):
            target = produced or pathlib.Path(work, "out.png")
            try:
                run = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
            except (OSError, subprocess.SubprocessError) as why:
                tried.append(f"{name}: не запустился ({why})")
                continue
            if run.returncode != 0 or not target.is_file():
                last = (run.stderr or "").strip().splitlines()[-1:]
                tried.append(f"{name}: отказал (код {run.returncode}" + (f", {last[0][:120]}" if last else "") + ")")
                continue
            got = png_size(target)
            if got != size:
                tried.append(f"{name}: размер рисунка {got} не равен размеру SVG {size}")
                continue
            png_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(target, png_path)
            return name
    if not tried:
        raise PngUnavailable(f"нет конвертера SVG → PNG (искал rsvg-convert, magick, convert, inkscape, qlmanage в PATH и в "
                             f"{', '.join(search_dirs())}): поставьте {INSTALL}")
    raise PngUnavailable("ни один конвертер SVG → PNG не дал рисунка нужного размера: " + "; ".join(tried)
                         + f". Поставьте {INSTALL}")


def write_picture(svg, out):
    """Сохраняет рисунок в `out`: для расширения `.png` используется конвертер, иначе записывается SVG. Возвращает `(путь, слова)`.
    Слова пусты или объясняют, почему PNG нет; в этом случае рядом записан SVG с расширением `.svg`, и `путь` указывает на него.
    """
    out = pathlib.Path(out)
    if out.suffix.lower() != ".png":
        out.write_text(svg, encoding="utf-8")
        return out, ""
    try:
        svg_to_png(svg, out)
        return out, ""
    except PngUnavailable as why:
        spare = out.with_suffix(".svg")
        spare.write_text(svg, encoding="utf-8")
        return spare, f"PNG не построен: {why}. SVG записан: {spare}"



def keyed(rendered):
    """Возвращает `{ключ: (Item, box)}` по нарисованным элементам. Ключ — имя вместе с родителем; у безымянных элементов — `<Тип>`, а
    повторы получают суффикс `#2`.
    """
    out, seen = {}, {}

    def path(item):
        label = item.name or f"<{item.type}>"
        return label if item.owner is None else f"{path(item.owner)}/{label}"

    for item, box in rendered.items:
        key = path(item)
        seen[key] = seen.get(key, 0) + 1
        out[key if seen[key] == 1 else f"{key}#{seen[key]}"] = (item, box)
    return out


def _unique_indexes(keyed_items):
    """`{индекс: ключ}` по элементам с индексом, который в форме не повторяется; прочие сопоставляются по ключу."""
    seen, dup = {}, set()
    for key, (item, _box) in keyed_items.items():
        index = getattr(item, "index", None)
        if not isinstance(index, int) or isinstance(index, bool):
            continue
        if index in seen:
            dup.add(index)
        seen[index] = key
    return {index: key for index, key in seen.items() if index not in dup}


def pair_items(kb, ka):
    """Пары `(ключ до, ключ после)` одного и того же элемента: по индексу, а у элементов без однозначного индекса — по ключу (имя с родителем)."""
    ib, ia = _unique_indexes(kb), _unique_indexes(ka)
    pairs, taken_a = [], set()
    for index, key_b in ib.items():
        if index in ia:
            pairs.append((key_b, ia[index]))
            taken_a.add(ia[index])
    matched_b = {b for b, _a in pairs}
    by_index_b, by_index_a = set(ib.values()), set(ia.values())
    for key in kb:
        if key in matched_b or key in by_index_b or key not in ka or key in taken_a or key in by_index_a:
            continue
        pairs.append((key, key))
    return pairs


class Comparison:
    """Итог сравнения: `new`, `moved` (имя, было, стало), `gone`, `same` (число), `renamed` (было, стало), `svg` (картинка) и `lines` (слова)."""

    def __init__(self, new, moved, gone, same, svg, notes, renamed=(), views=(), tabs=(), local=None):
        self.new, self.moved, self.gone, self.same, self.svg, self.notes = new, moved, gone, same, svg, notes
        # `local` — `{"до"/"после": {ключ: (страница, (x, y, ширина, высота))}}`: координаты вложенных элементов в системе, которую ждёт `box`
        # (от области страницы панели), рядом с координатами формы, в которых рисует модель раскладки.
        self.local = local or {"до": {}, "после": {}}
        self.renamed = list(renamed)
        self.views = list(views)     # (имя, было, стало): вид поля ввода 8.2 / 8.3
        self.tabs = list(tabs)       # (имя, было, стало): номер в порядке обхода страницы родителя
        self.lines = self._lines()

    def _lines(self):
        def box(b):
            return "(" + ",".join(str(v) for v in b) + ")"

        def here(key, side):
            """Координаты вложенного элемента для `box`: от области страницы панели (не от формы)."""
            got = self.local[side].get(key)
            return f"{got[0]}: {box(got[1])}" if got else ""

        def one(key, b, side):
            local = here(key, side)
            return f"{key} {box(b)}" + (f" [box на странице {local}]" if local else "")

        def two(key, a, b):
            before, after = here(key, "до"), here(key, "после")
            tail = f" [box на странице {after.split(':')[0]}: {before.split(': ', 1)[-1] if before else '—'} → {after.split(': ', 1)[-1]}]" if after else ""
            return f"{key} {box(a)} → {box(b)}{tail}"
        parts = ["новые: " + (", ".join(one(k, b, "после") for k, b in self.new) or "нет"),
                 "сдвинуты: " + (", ".join(two(k, a, b) for k, a, b in self.moved) or "нет"),
                 "убраны: " + (", ".join(one(k, b, "до") for k, b in self.gone) or "нет")]
        if self.renamed:
            parts.append("переименованы: " + ", ".join(f"{a} → {b}" for a, b in self.renamed))
        parts.append(f"прочие {self.same} не тронуты")
        out = ["; ".join(parts)]
        if self.views:
            out.append("вид поля (8.2 / 8.3), было → стало: " + ", ".join(f"{k} {a} → {b}" for k, a, b in self.views))
        if self.tabs:
            out.append("порядок обхода (Tab), номер на странице, было → стало: " + ", ".join(f"{k} {a} → {b}" for k, a, b in self.tabs))
        return out


def _inner(svg, tag=""):
    """Содержимое корня SVG без самого корневого элемента. `tag` — приставка к идентификаторам (`clipPath` панелей): когда в один рисунок вставлено несколько кадров, одинаковый
    `id` у двух кадров не различим, браузер берёт первое определение, и подписи кнопок второго кадра обрезаются по рамке первого."""
    inner = re.sub(r"^\s*<svg\b[^>]*>", "", svg, count=1).rsplit("</svg>", 1)[0]
    if tag:
        for ident in sorted(set(re.findall(r"\bid='([^']+)'", inner)), key=len, reverse=True):
            inner = inner.replace(f"id='{ident}'", f"id='{tag}{ident}'").replace(f"url(#{ident})", f"url(#{tag}{ident})")
    return inner


def _mark(box, color, name, kind, dashed=False):
    x, y, w, h = box
    dash = " stroke-dasharray='4 3'" if dashed else ""
    return (f"<rect class='mark {kind}' data-name='{escape(name, {chr(39): '&apos;'})}' x='{x + 0.5}' y='{y + 0.5}' "
            f"width='{max(w - 1, 0)}' height='{max(h - 1, 0)}' fill='{color}' fill-opacity='{0 if dashed else 0.12}' "
            f"stroke='{color}' stroke-width='2'{dash}/>")


def _changed_attributes(kb, ka, pairs):
    """Что поменялось у парных элементов и не видно на каркасе: вид поля ввода (8.2 / 8.3) и номер в порядке обхода: `(виды, номера)` как `[(имя, было, стало)]`."""
    from . import design as _design, edit as _edit
    views, tabs = [], []
    for b, a in pairs:
        item_b, item_a = kb[b][0], ka[a][0]
        node_b, node_a = getattr(item_b, "node", None), getattr(item_a, "node", None)
        if isinstance(node_b, dict) and isinstance(node_a, dict):
            was, now = _design.textbox_view(node_b), _design.textbox_view(node_a)
            if was is not None and now is not None and was != now:
                views.append((a, was, now))
        coords_b, coords_a = getattr(item_b, "coords", None), getattr(item_a, "coords", None)
        if isinstance(coords_b, dict) and isinstance(coords_a, dict):
            was, now = coords_b.get(_edit.TAB_ORDER), coords_a.get(_edit.TAB_ORDER)
            if isinstance(was, int) and isinstance(now, int) and was != now and item_b.holder == item_a.holder and item_b.page == item_a.page:
                tabs.append((a, was, now))
    return views, tabs


def _badge(box, text, color):
    """Пометка у элемента «после»: короткая подпись над левым верхним углом."""
    x, y, _w, _h = box
    width = 6 * len(text) + 6
    return (f"<g class='badge'><rect x='{x}' y='{max(y - 12, 0)}' width='{width}' height='12' fill='{color}' fill-opacity='0.9'/>"
            f"<text x='{x + 3}' y='{max(y - 3, 9)}' font-family='Tahoma, sans-serif' font-size='9' fill='white'>{escape(text)}</text></g>")


def _local_boxes(keyed_items):
    """`{ключ: (номер страницы, (x, y, ширина, высота))}` вложенных элементов: координаты в той системе, что ждёт `box` (от левого верха
    области страницы панели), а не от формы."""
    out = {}
    for key, (item, _box) in keyed_items.items():
        edges = getattr(item, "box", None)
        if item.owner is not None and isinstance(edges, tuple) and len(edges) == 4:
            out[key] = (item.page, (edges[0], edges[1], edges[2] - edges[0], edges[3] - edges[1]))
    return out


def compare(doc_before, doc_after, width=None, height=None, shown=None, marks=(None, None)):
    """Сравнивает две формы по модели раскладки при одном размере окна (`width` на `height`; по умолчанию берётся размер формы). `marks` — пометки кода
    «до» и «после» (`brief.module_marks`)."""
    before = render.render(doc_before, width, height, shown, marks=marks[0])
    after = render.render(doc_after, width, height, shown, marks=marks[1])
    kb, ka = keyed(before), keyed(after)
    pairs = pair_items(kb, ka)
    after_of, before_of = dict(pairs), {a: b for b, a in pairs}
    new = [(k, ka[k][1]) for k in ka if k not in before_of]
    gone = [(k, kb[k][1]) for k in kb if k not in after_of]
    moved = [(a, kb[b][1], ka[a][1]) for b, a in pairs if kb[b][1] != ka[a][1]]
    same = sum(1 for b, a in pairs if kb[b][1] == ka[a][1])
    renamed = [(b, a) for b, a in pairs if kb[b][0].name != ka[a][0].name]
    views, tabs = _changed_attributes(kb, ka, pairs)
    local = {"до": _local_boxes(kb), "после": _local_boxes(ka)}

    (bw, bh), (aw, ah) = before.size, after.size
    top = MARGIN + TITLE
    xb, xa = MARGIN, MARGIN + bw + GAP
    total_w = xa + aw + MARGIN
    total_h = top + max(bh, ah) + LEGEND + (16 if renamed else 0) + (16 if views else 0) + (16 if tabs else 0) + MARGIN
    parts = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{total_w}' height='{total_h}'>",
             f"<rect width='{total_w}' height='{total_h}' fill='white'/>",
             f"<text x='{xb}' y='{MARGIN + 13}' font-family='Tahoma, sans-serif' font-size='13' font-weight='bold'>до ({bw}x{bh})</text>",
             f"<text x='{xa}' y='{MARGIN + 13}' font-family='Tahoma, sans-serif' font-size='13' font-weight='bold'>после ({aw}x{ah})</text>"]
    for x, (w, h), pic, tag in ((xb, (bw, bh), before, "b_"), (xa, (aw, ah), after, "a_")):
        parts.append(f"<svg x='{x}' y='{top}' width='{w}' height='{h}'>{_inner(pic.svg, tag)}</svg>")
        parts.append(f"<rect x='{x - 0.5}' y='{top - 0.5}' width='{w + 1}' height='{h + 1}' fill='none' stroke='#888'/>")
    for k, box in gone:
        parts.append(f"<g transform='translate({xb},{top})'>{_mark(box, GONE, k, 'gone')}</g>")
    for k, was, now in moved:
        parts.append(f"<g transform='translate({xb},{top})'>{_mark(was, MOVED, k, 'moved-was', dashed=True)}</g>")
        parts.append(f"<g transform='translate({xa},{top})'>{_mark(now, MOVED, k, 'moved')}</g>")
    for k, box in new:
        parts.append(f"<g transform='translate({xa},{top})'>{_mark(box, NEW, k, 'new')}</g>")
    ly = top + max(bh, ah) + 18
    for b, a in renamed:
        parts.append(f"<g transform='translate({xa},{top})'>{_mark(ka[a][1], RENAMED, f'{b} → {a}', 'renamed')}</g>")
    legend = [(NEW, f"новые на «после» ({len(new)})"),
              (MOVED, f"сдвинуты или изменили размер ({len(moved)}); на «до» — прежнее место пунктиром"),
              (GONE, f"убраны, обведены на «до» ({len(gone)})")]
    if renamed:
        legend.append((RENAMED, f"переименованы, обведены на «после» ({len(renamed)})"))
    badges = {}
    for k, was, now in views:
        badges.setdefault(k, []).append(f"вид {was}→{now}")
    for k, was, now in tabs:
        badges.setdefault(k, []).append(f"обход {was}→{now}")
    for k, texts in badges.items():
        parts.append(f"<g transform='translate({xa},{top})'>{_badge(ka[k][1], ', '.join(texts), CHANGED)}</g>")
    if views:
        legend.append((CHANGED, f"сменился вид поля 8.2 / 8.3, подпись «вид было→стало» над полем ({len(views)})"))
    if tabs:
        legend.append((CHANGED, f"сменился номер в порядке обхода, подпись «обход было→стало» над элементом ({len(tabs)})"))
    for color, text in legend:
        parts.append(f"<rect x='{MARGIN}' y='{ly - 10}' width='12' height='12' fill='{color}' fill-opacity='0.25' stroke='{color}' stroke-width='2'/>")
        parts.append(f"<text x='{MARGIN + 18}' y='{ly}' font-family='Tahoma, sans-serif' font-size='12'>{escape(text)}</text>")
        ly += 16
    parts.append("</svg>")
    notes = list(dict.fromkeys(before.notes + after.notes))
    return Comparison(new, moved, gone, same, "\n".join(parts), notes, renamed, views, tabs, local)
