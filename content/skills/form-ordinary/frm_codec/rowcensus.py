"""Перепись рядов и блоков «рядом»: числа, по которым `generate` ставит ряд, блок справа от шапки, переключатели в ряд и разделитель.

Одна запись на форму (`record`) и сведение всех записей в файл `data/row_norms.json` (`aggregate`, `write`); читает `rownorms`. Что меряется:

* **ряд** — звенья «надпись + поле», поле без надписи, флажок, кнопка формы, стоящие на одной высоте в одном родителе (форма, страница панели или
  «внутри» рамки группы); в ряду не меньше двух звеньев. Мера — зазор «конец предыдущего звена → начало следующего» по видам пары звеньев;
* **ширина поля в ряду** по составу типа поля (дата, время, дата и время, строка, число, ссылка, прочее), отдельно у полей, которые с окном не растягиваются;
* **кнопка формы в ряду полей** — высота и ширина против ширины подписи (`textwidth`);
* **переключатели в ряд** — зазор между соседними и шаг;
* **рамка с заголовком** — запас «ширина рамки − ширина заголовка» (жирным шрифтом, как рисует платформа), у рамок по содержимому — отдельно;
* **разделитель** — размеры частей по обе стороны от него.

Размеры в пикселях сравнимы только при DPI 96: форма с другим DPI в перепись не входит.
"""
import collections
import hashlib
import json
import pathlib

from . import census, layout, textgap, textwidth
from .datapaths import DATA_DIR
from .render import scene

ROW_NORMS_PATH = DATA_DIR / "row_norms.json"
ROW_TOL = 0.5  # звенья на одной высоте: вертикальное пересечение не меньше этой доли меньшего из двух
MAX_ROW_H = 40  # выше — не звено ряда (многострочное поле, таблица, картинка)
PAIR_MAX_GAP = 40  # надпись — подпись поля, если поле начинается не дальше этого от её правого края
RING_MAX_GAP = 120  # зазор между звеньями больше — это уже колонки формы, а не ряд: в распределение не идёт (доля сказана в таблице)
FIELD_TYPES = ("TextBox", "ComboBox")
LINK_TYPES = ("Label", "TextBox", "ComboBox", "CheckBox", "Button")
TIGHT_INSET = 12  # рамка «по содержимому»: от краёв содержимого до краёв рамки не больше этого
SPLIT_TOUCH = 3  # часть касается разделителя, если её край не дальше этого от края разделителя
TOP = 8


def field_class(node, type_):
    """Состав поля ввода для таблицы ширин: `Date`, `Time`, `DateTime`, `S` (строка), `N` (число), `#` (ссылка), `B`, `other` (составной тип, тип не записан)."""
    if type_ == "ComboBox":
        return "ComboBox"
    date = textgap.date_composition(node)
    if date is not None:
        return date
    pattern = node.get("content", {}).get(textgap.N.TEXTBOX_PATTERN) if isinstance(node, dict) else None
    types = pattern.get(textgap.N.PATTERN_TYPES) if isinstance(pattern, dict) else None
    if isinstance(types, list) and len(types) == 1 and isinstance(types[0], dict):
        letter = types[0].get(textgap.N.PATTERN_KIND)
        if letter in ("S", "N", "#", "B"):
            return letter
    return "other"


def _overlap(a, b):
    """Вертикальное пересечение двух ящиков как доля меньшего."""
    top, bottom = max(a[1], b[1]), min(a[3], b[3])
    least = min(a[3] - a[1], b[3] - b[1])
    return (bottom - top) / least if least > 0 else 0


def _rows(items):
    """Ряды контекста: элементы на одной высоте (пересечение с первым элементом ряда не меньше `ROW_TOL`), по x."""
    rows = []
    for it in sorted(items, key=lambda i: ((i.box[1] + i.box[3]), i.box[0])):
        for row in rows:
            if _overlap(row[0].box, it.box) >= ROW_TOL:
                row.append(it)
                break
        else:
            rows.append([it])
    return [sorted(r, key=lambda i: i.box[0]) for r in rows]


def _links(row):
    """Звенья ряда слева направо: `(вид, первый элемент, последний элемент)`. Вид: `pair` (надпись + поле), `field`, `check`, `button`, `text` (надпись без поля).

    Ящик элемента — `(x1, y1, x2, y2)`, как у элемента раскладки.
    """
    out, at = [], 0
    while at < len(row):
        it = row[at]
        nxt = row[at + 1] if at + 1 < len(row) else None
        if it.type == "Label":
            if nxt is not None and nxt.type in FIELD_TYPES and 0 <= nxt.box[0] - it.box[2] <= PAIR_MAX_GAP:
                out.append(("pair", it, nxt))
                at += 2
                continue
            out.append(("text", it, it))
        elif it.type in FIELD_TYPES:
            out.append(("field", it, it))
        elif it.type == "CheckBox":
            out.append(("check", it, it))
        elif it.type == "Button":
            out.append(("button", it, it))
        at += 1
    return out


class _Box:
    """Элемент с ящиком `[x1, y1, x2, y2]`: то, что нужно переписи, от элемента раскладки."""
    __slots__ = ("type", "name", "box", "node", "stretch")

    def __init__(self, item, stretch):
        self.type, self.name, self.node = item.type, item.name, item.node
        self.box = tuple(item.box)
        self.stretch = stretch


def record(doc, rel):
    """Запись о форме: `{path, kind, config, ...}` и наблюдения (списки). Форма не при DPI 96 — `None`."""
    if (doc.get("form") or {}).get("dpi") not in (None, 96):
        return None
    form = layout.read(doc)
    try:
        coefs = layout.coefficients(form, hide=False)
    except Exception:  # noqa: BLE001 — форма, которую раскладка не читает: поведение полей неизвестно
        coefs = {}
    behaviour = {}
    for index, c in coefs.items():
        b = layout.horizontal_behaviour(c[2], c[3])
        behaviour[index] = b not in (layout.STANDS, layout.MOVES)
    klass, obj, form_name = census.where(rel)
    kind = census.kind_of(klass, obj, form_name, census.main_attribute(doc))
    rec = {"path": rel, "kind": kind, "config": census.config_of(rel), "gaps": [], "fields": [], "buttons": [], "radios": [], "frames": [], "splits": [], "sides": []}
    pages = _pages(form, behaviour)
    for ctx in pages:
        _measure_context(doc, rec, ctx)
    return rec


def _pages(form, behaviour):
    """Контексты формы: список `(элементы без рамок внутри, [(рамка, элементы внутри)])`: на каждую страницу родителя — один контекст верхнего уровня
    и по контексту на рамку."""
    out = []
    for holder in form.holders.values():
        by_page = collections.defaultdict(list)
        for it in holder.children:
            if it.visible and not it.raw:
                by_page[it.page].append(_Box(it, behaviour.get(it.index, False)))
        for items in by_page.values():
            frames = [i for i in items if i.type == "GroupBox"]
            owner = {}
            for it in items:
                if it.type == "GroupBox":
                    continue
                inside = [g for g in frames if g.box[0] <= it.box[0] and g.box[1] <= it.box[1] and g.box[2] >= it.box[2] and g.box[3] >= it.box[3]]
                if inside:
                    owner[id(it)] = min(inside, key=lambda g: (g.box[2] - g.box[0]) * (g.box[3] - g.box[1]))
            top = [i for i in items if id(i) not in owner]
            inner = {id(g): [i for i in items if owner.get(id(i)) is g] for g in frames}
            out.append((top, [(g, inner[id(g)]) for g in frames]))
    return out


def _text_start(doc, label):
    """x начала текста надписи: слева — её левый край, справа и по центру — конец текста минус его ширина (`textgap.label_text_end`); нет — `None`."""
    if textgap.alignment(label.node) == "Left":
        return label.box[0]
    got = textgap.label_text_end(label.node, doc, label.box)
    return None if got is None else got[0] - got[1]


def _text_w(doc, label):
    """Ширина текста надписи или `None` (в несколько строк, шире рамки, шрифт не проверен)."""
    got = textgap.label_text_end(label.node, doc, label.box)
    return None if got is None else got[1]


def _font(doc, it):
    return textwidth.element_font(it.node, doc)


def _measure_context(doc, rec, ctx):
    top, frames = ctx
    _measure_rows(doc, rec, top)
    _measure_splits(rec, top)
    _measure_side(rec, top)
    for g, inside in frames:
        _measure_rows(doc, rec, inside)
        _measure_frame(doc, rec, g, inside)


def _measure_rows(doc, rec, items):
    cand = [i for i in items if i.type in LINK_TYPES and i.box[3] - i.box[1] <= MAX_ROW_H and not (i.type == "TextBox" and textgap.is_multi_line(i.node))]
    for row in _rows(cand):
        links = _links(row)
        real = [l for l in links if l[0] != "text"]
        if len(real) < 2:
            continue
        for kind, a, b in links:
            if kind in ("pair", "field"):
                f = b
                rec["fields"].append([field_class(f.node, f.type), f.box[2] - f.box[0], int(f.stretch), kind])
        for (k1, _a1, b1), (k2, a2, _b2) in zip(links, links[1:]):
            if k1 == "text" or k2 == "text":
                continue
            start = _text_start(doc, a2) if k2 == "pair" else a2.box[0]
            if start is None:  # подпись в несколько строк, шире рамки или шрифт не проверен: начала текста нет
                continue
            rec["gaps"].append([k1 if k1 != "pair" else "field", k2 if k2 != "pair" else "label", start - b1.box[2], _text_w(doc, a2) if k2 == "pair" else None])
        has_fields = any(l[0] in ("pair", "field") for l in links)
        for kind, a, _b in links:
            if kind == "button":
                caption = scene.caption_text(a.node, "Button")
                if caption:
                    tw = textwidth.width(caption, _font(doc, a))
                    rec["buttons"].append([a.box[3] - a.box[1], a.box[2] - a.box[0], tw, int(has_fields)])
    # переключатели в ряд — отдельно: внутри рамки они не «звенья» с надписью
    radios = [i for i in items if i.type == "RadioButton"]
    for row in _rows(radios):
        for a, b in zip(row, row[1:]):
            rec["radios"].append([b.box[0] - a.box[2], b.box[0] - a.box[0]])


def _measure_side(rec, items):
    """Рамка группы справа от шапки: зазор от правого края ближайшего слева элемента (на высоте рамки, не сама рамка), до левого края рамки."""
    for g in (i for i in items if i.type == "GroupBox"):
        left = [i.box[2] for i in items if i is not g and i.type != "GroupBox" and i.box[2] <= g.box[0] and min(i.box[3], g.box[3]) > max(i.box[1], g.box[1])]
        if left:
            rec["sides"].append(g.box[0] - max(left))


def _measure_frame(doc, rec, g, inside):
    title = scene.caption_text(g.node, "GroupBox")
    if not title or not inside:
        return
    font = _font(doc, g)
    bold = {**textwidth.DEFAULT_FONT, "bold": True}
    width = g.box[2] - g.box[0]
    left = min(i.box[0] for i in inside) - g.box[0]
    right = g.box[2] - max(i.box[2] for i in inside)
    rec["frames"].append([width, textwidth.width(title, bold), textwidth.width(title, font), int(max(left, right) <= TIGHT_INSET)])


def _measure_splits(rec, items):
    for s in (i for i in items if i.type == "Splitter"):
        sw, sh = s.box[2] - s.box[0], s.box[3] - s.box[1]
        vertical = sh >= sw
        others = [i for i in items if i is not s and i.type not in ("Splitter", "GroupBox", "Label")]
        parts = []
        for side in (0, 1):
            found = []
            for i in others:
                if vertical:
                    touch = abs((i.box[2] - s.box[0]) if side == 0 else (i.box[0] - s.box[2]))
                    along = _overlap_axis((i.box[1], i.box[3]), (s.box[1], s.box[3]))
                else:
                    touch = abs((i.box[3] - s.box[1]) if side == 0 else (i.box[1] - s.box[3]))
                    along = _overlap_axis((i.box[0], i.box[2]), (s.box[0], s.box[2]))
                if touch <= SPLIT_TOUCH and along >= 0.5:
                    size = (i.box[2] - i.box[0]) if vertical else (i.box[3] - i.box[1])
                    found.append((size, i.type))
            parts.append(max(found) if found else None)
        if parts[0] and parts[1]:
            rec["splits"].append(["v" if vertical else "h", parts[0][0], parts[0][1], parts[1][0], parts[1][1]])


def _overlap_axis(a, b):
    least = min(a[1] - a[0], b[1] - b[0])
    return (min(a[1], b[1]) - max(a[0], b[0])) / least if least > 0 else 0


def record_path(path):
    """Запись по пути или `{path, kind: "error"}` (отказ не прерывает перепись) либо `None` (DPI не 96)."""
    from . import typed
    from .tree import read_file
    path = pathlib.Path(path)
    try:
        rec = record(typed.decode(read_file(path)), str(path))
        if rec is not None:
            rec["sha"] = hashlib.sha256(path.read_bytes()).hexdigest()
        return rec
    except Exception as exc:  # noqa: BLE001
        return {"path": str(path), "kind": "error", "error": f"{type(exc).__name__}: {exc}"[:200]}


# ── сведение записей в таблицу ─────────────────────────────────────────────────────────────

JOINT_TW = 15  # надпись-«связка» («с», «по», «до»): текст не шире этого; после поля у неё свой зазор
REGULAR_TW = 13  # кнопка с подписью не уже этого — обычная; уже — кнопка выбора вида «…»
RING_GAP = (0, 60)  # звенья ряда — зазор в этих пределах; меньше нуля — наложение, больше — колонки формы (число таких в таблице называется)
BY_KIND_MIN = 100  # вид формы получает свою строку, если у него не меньше стольких наблюдений
KIND_DIFF = 2  # медиана вида отличается от общей больше чем на столько px — «виды различаются»
FLOOR_SHARE = 0.01  # наименьшее значение: ниже него не больше этой доли наблюдений (как нижняя граница зазора «текст → поле»)
STAMP = "снимок корпуса форм"


def stat(values):
    """Строка таблицы: `{n, forms, top, median, floor, min, majority}` по наблюдениям `[(значение, номер формы)]`. `top` — до `TOP` самых частых значений
    `[значение, доля, число]`; `median` — нижняя из двух средних; `floor` — наименьшее значение, ниже которого не больше `FLOOR_SHARE` наблюдений; `majority` — у самого
    частого значения доля больше половины (тогда оно и есть медиана). Число для генерации — `median`."""
    vals = sorted(v for v, _ in values)
    n = len(vals)
    if not n:
        return {"n": 0, "forms": 0, "top": [], "median": None, "floor": None, "min": None, "majority": False}
    counts = collections.Counter(vals)
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP]
    floor, below = vals[-1], 0
    for value in sorted(counts):
        if (below + counts[value]) / n > FLOOR_SHARE:
            floor = value
            break
        below += counts[value]
    return {"n": n, "forms": len({f for _, f in values}), "top": [[v, round(c / n, 4), c] for v, c in top], "median": vals[(n - 1) // 2],
            "floor": floor, "min": vals[0], "majority": top[0][1] / n > 0.5}


def _gap_key(prev, nxt, tw):
    if nxt == "label":
        return "field>label_joint" if prev == "field" and tw is not None and tw <= JOINT_TW else f"{prev}>label"
    return f"{prev}>{nxt}"


def aggregate(records, stamp=STAMP):
    """Таблица норм ряда по записям: формы-повторы (по sha256 `form.frm`) считаются один раз, регламентированная отчётность и отказы не входят."""
    kept, seen, excluded = [], set(), collections.Counter()
    for rec in sorted((r for r in records if r is not None), key=lambda r: r["path"]):
        if rec["kind"] in ("regulated", "error"):
            excluded[rec["kind"]] += 1
            continue
        if rec.get("sha") in seen:
            excluded["duplicate"] += 1
            continue
        seen.add(rec.get("sha"))
        kept.append(rec)
    gaps = collections.defaultdict(list)
    outside = collections.Counter()
    by_kind = collections.defaultdict(lambda: collections.defaultdict(list))
    widths = collections.defaultdict(list)
    buttons = collections.defaultdict(list)
    radios = {"gap": [], "step": []}
    sides, margins, splits = [], [], collections.defaultdict(list)
    for i, rec in enumerate(kept):
        for prev, nxt, gap, tw in rec["gaps"]:
            key = _gap_key(prev, nxt, tw)
            if gap < RING_GAP[0]:
                outside[(key, "overlap")] += 1
            elif gap > RING_GAP[1]:
                outside[(key, "wide")] += 1
            else:
                gaps[key].append((gap, i))
                by_kind[key][rec["kind"]].append((gap, i))
        for cls, w, stretch, _kind in rec["fields"]:
            widths[f"{cls}:{'stretch' if stretch else 'fixed'}"].append((w, i))
        for h, w, tw, has_fields in rec["buttons"]:
            if has_fields:
                size = "regular" if tw >= REGULAR_TW else "short"
                buttons[f"{size}:height"].append((h, i))
                buttons[f"{size}:width"].append((w, i))
                buttons[f"{size}:pad"].append((w - tw, i))
        for gap, step in rec["radios"]:
            if RING_GAP[0] <= gap <= RING_GAP[1]:
                radios["gap"].append((gap, i))
                radios["step"].append((step, i))
        for gap in rec["sides"]:
            if RING_GAP[0] <= gap <= RING_GAP[1]:
                sides.append((gap, i))
        for width, bold, _own, _tight in rec["frames"]:
            margins.append((width - bold, i))
        for orient, a, ta, b, tb in rec["splits"]:
            for size, kind in ((a, ta), (b, tb)):
                if kind == "TableBox":
                    splits["left_right" if orient == "v" else "top_bottom"].append((size, i))
    table = {"stamp": stamp, "forms": len(kept), "excluded": dict(sorted(excluded.items())), "ring_gap": list(RING_GAP), "gap": {}}
    for key in sorted(gaps):
        row = stat(gaps[key])
        row["outside"] = {kind: n for (k, kind), n in sorted(outside.items()) if k == key}
        kinds = {kind: stat(vals) for kind, vals in sorted(by_kind[key].items()) if len(vals) >= BY_KIND_MIN}
        row["by_kind"] = {k: {"n": v["n"], "median": v["median"], "top": v["top"][:3]} for k, v in kinds.items()}
        row["kinds_differ"] = any(abs(v["median"] - row["median"]) > KIND_DIFF for v in kinds.values())
        table["gap"][key] = row
    table["field_width"] = {key: stat(widths[key]) for key in sorted(widths)}
    table["button"] = {key: stat(buttons[key]) for key in sorted(buttons)}
    table["radio"] = {key: stat(vals) for key, vals in radios.items()}
    table["side_gap"] = stat(sides)
    table["frame_title_margin"] = stat(margins)
    table["split_table"] = {key: stat(vals) for key, vals in sorted(splits.items())}
    return table


def write(table, path=ROW_NORMS_PATH):
    pathlib.Path(path).write_text(json.dumps(table, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def load(path=ROW_NORMS_PATH):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def first_difference(have, want, path=""):
    """Первое различие двух таблиц словами с путём (`gap/field>label/median: было … → стало …`)."""
    if isinstance(have, dict) and isinstance(want, dict):
        for key in sorted(set(have) | set(want)):
            if key not in have or key not in want:
                return f"{path}/{key}: {'нет в файле' if key not in have else 'нет в пересборке'}"
            if have[key] != want[key]:
                return first_difference(have[key], want[key], f"{path}/{key}")
    return f"{path.lstrip('/')}: было {have!r} → стало {want!r}"
