"""Рамка группы (`GroupBox`) по виду рамки (`border/border_type`), высоте и шрифту заголовка.

Платформа рисует рамку группы с заголовком двумя способами. **Полная рамка** — заголовок на своём месте, линии по краям рамки. **Сжатая** — когда высоты
не хватает для полной: заголовок у левого края, линия (или линии) справа от него или под ним. Порог зависит от вида рамки и высоты строки заголовка
`lh`; сжатая рамка (кроме «Подчёркивания», «Двойного подчёркивания» и «Надчёркивания») центрирует заголовок по вертикали. Нулевая высота — не рисуется
ничего, а всё, что не вмещается в высоту, срезается краем рамки. Меры сняты по двум шрифтам (Tahoma 8 pt полужирный и Arial 12 pt курсив): высота строки
`lh` = ⌊1,18·ppem + ½⌋ (13 и 19 px), строки знаков заглавной `cap` = ⌊0,6·ppem + 2,4 + ½⌋ (9 и 12), у других шрифтов обе меры — оценка.
"""
from xml.sax.saxutils import escape

from .. import textwidth
from . import textmeasure
from .core import EDGE, _caption, _clean, _color_of, _dig, _n, _text

GROUP_TITLE = "#9c6700"            # заголовок «Авто» — цвет заголовка рамки в стиле предприятия
EMBOSS_LIGHT, EMBOSS_DARK = "#ffffff", "#b5b19c"
ROUND_R = 3.5                      # радиус скругления «Скруглённой» рамки (прямой угол при высоте меньше ROUND_MIN_H)
ROUND_MIN_H = 12                   # скругление проверено при 12 и выше; при 6 углы прямые, между ними не проверялось
FULL_INDENT = {"Single": 10, "Rounded": 10, "Double": 12, "Embossed": 5, "Indented": 5, "Underline": 9, "DoubleUnderline": 9, "WithoutBorder": 9}


def metrics(font):
    """`(lh, cap, top0)` шрифта заголовка: высота строки, строки знаков заглавной, верхняя строка знаков в рамке с нижним краем под заголовком."""
    size = (font or {}).get("size")
    ppem = textwidth.ppem_of(size) if size is not None else textwidth.DEFAULT_PPEM
    lh = int(1.18 * ppem + 0.5)
    cap = int(0.6 * ppem + 2.4 + 0.5)
    return lh, cap, -(-(lh - cap) // 2)


# Гарнитуры, у которых при 10 pt (13 px) полная рамка с вынесенной подписью (Single, Rounded, Double) при высоте 24 не рисуется — рисуется сжатая (проверено в предприятии
# для Tahoma, Arial и Courier New; у Times New Roman при 10 pt полная). Порог у них выше расчётного на `FULL_EXTRA` px: точное значение не проверялось, известно только, что оно больше 24.
TALL_FACES = frozenset({"tahoma", "arial", "courier new"})
FULL_EXTRA = 2


def full_extra(kind, font):
    """Прибавка к порогу полной рамки: у гарнитур из `TALL_FACES` при 13 px строка выше расчётной (у остальных шрифтов и размеров прибавки нет)."""
    font = font or {}
    size = font.get("size")
    if kind not in ("Single", "Rounded", "Double") or size is None or textwidth.ppem_of(size) != 13:
        return 0
    return FULL_EXTRA if (font.get("face") or "").casefold() in TALL_FACES else 0


def _explicit_border_color(it):
    """Явный `border_color` группы (`#rrggbb`) либо `None`: цвет линий и автоматического заголовка."""
    record = _dig(it.node, "content", "u1", "u0", "border_color")
    if isinstance(record, dict) and record.get("color_kind") == 0:
        code = (record.get("value") or {}).get("code")
        if isinstance(code, int):
            return "#%02x%02x%02x" % (code & 255, (code >> 8) & 255, (code >> 16) & 255)
    return None


def title_color(it):
    """Цвет заголовка: явный цвет текста; иначе явный цвет рамки; иначе `GROUP_TITLE`."""
    color, _why = _color_of(it.node)
    return color or _explicit_border_color(it) or GROUP_TITLE


def frame_color(it):
    return _explicit_border_color(it) or EDGE


def full_threshold(kind, lh, line_full):
    """Наименьшая высота, с которой платформа рисует полную рамку; ниже — сжатую."""
    if kind == "WithoutBorder":
        return lh + 2
    if kind == "Underline":
        return lh + 5
    if kind == "DoubleUnderline":
        return lh + 7
    if kind in ("Embossed", "Indented"):
        return lh + 9
    return line_full + lh                # Single, Rounded, Double: нижняя линия не ближе высоты строки к верхней


def plan(it, w, h, font):
    """Рисунок рамки группы: `{"title": (x, baseline, текст) | None, "lines": [(цвет, путь SVG)], "empty": bool}`; координаты от левого верхнего угла box."""
    kind = _dig(it.node, "content", "u1", "border", "border_type")
    caption = _clean(_caption(it.node))
    out = {"title": None, "lines": [], "kind": kind, "caption": caption}
    if h <= 0 or w <= 0:
        return out
    color = frame_color(it)
    lh, cap, top0 = metrics(font)
    half = -(-cap // 2)
    lines = out["lines"]

    def hline(c, row, a, b):
        if b >= a:
            lines.append((c, f"M{_n(a)} {_n(row + 0.5)}H{_n(b + 1)}"))

    def vline(c, col, a, b):
        if b >= a:
            lines.append((c, f"M{_n(col + 0.5)} {_n(a)}V{_n(b + 1)}"))

    def title(origin, top, room):
        text, cut, _known = textmeasure.fit(caption, room, font) if caption else ("", False, True)
        out["title"] = (origin, top + cap, text) if text else None
        out["cut"] = cut
        return room if cut else (textwidth.measure(text, font).px if text else 0)   # усечённый заголовок занимает всё отведённое место

    if not caption:
        _no_caption(kind, w, h, color, hline, vline, lines)
        return out
    line_full = top0 + half
    if kind == "Overline":
        hline(color, 0, 0, w - 1)
        title(0, top0 + 1, w - 6)
        return out
    full = h >= full_threshold(kind, lh, line_full) + full_extra(kind, font)
    if full:
        origin = FULL_INDENT.get(kind, 10)
        width = title(origin, top0 + 4 if kind in ("Embossed", "Indented") else top0, w - 2 * origin if kind not in ("Embossed", "Indented") else w - 10)
        resume = origin + width + 1
        if kind in ("Single", "Rounded"):
            _boxed(kind, w, h, color, line_full, resume, lines)
        elif kind == "Double":
            _double(w, h, color, line_full, resume, hline, vline)
        elif kind in ("Embossed", "Indented"):
            _emboss(kind == "Embossed", w, h, hline, vline)
        elif kind == "Underline":
            hline(color, h - 1, 0, w - 1)
        elif kind == "DoubleUnderline":
            hline(color, h - 3, 0, w - 1)
            hline(color, h - 1, 0, w - 1)
        return out
    c = (h + 2) // 2            # сжатая рамка: линия на середине высоты, заголовок центрирован по ней
    if kind in ("Underline", "DoubleUnderline"):
        title(0, top0, w - 4)
        for row in (lh + 1, lh + 3)[:1 if kind == "Underline" else 2]:
            if row < h:
                hline(color, row, 0, w - 1)
        return out
    origin = 1 if kind in ("Embossed", "Indented") else 0
    width = title(origin, max(top0, c - half), w - 4)
    resume = origin + width + 1
    if kind in ("Single", "Rounded"):
        hline(color, c, resume, w - 1)
    elif kind == "Double":
        hline(color, c - 1, resume, w - 1)
        hline(color, c + 1, resume, w - 1)
    elif kind in ("Embossed", "Indented"):
        first, second = (EMBOSS_LIGHT, EMBOSS_DARK) if kind == "Embossed" else (EMBOSS_DARK, EMBOSS_LIGHT)
        hline(first, c, resume, w - 2)
        hline(second, c + 1, resume + 1, w - 1)
    return out


def _no_caption(kind, w, h, color, hline, vline, lines):
    """Рамка без заголовка: рамка по краям box, у подчёркиваний линии у нижнего края, у надчёркивания у верхнего. Высоту меньше 8 платформа рисует иначе: у «Двойного
    подчёркивания» линии на строках 0 и 2, у «Выпуклой» и «Вдавленной» пара линий по середине (проверена одна высота — 6)."""
    if kind == "WithoutBorder":
        return
    if kind == "Overline":
        hline(color, 0, 0, w - 1)
    elif kind == "Underline":
        hline(color, h - 1, 0, w - 1)
    elif kind == "DoubleUnderline":
        rows = (0, 2) if h < 8 else (h - 3, h - 1)
        for row in rows:
            hline(color, row, 0, w - 1)
    elif kind in ("Embossed", "Indented"):
        first, second = (EMBOSS_LIGHT, EMBOSS_DARK) if kind == "Embossed" else (EMBOSS_DARK, EMBOSS_LIGHT)
        if h < 8:
            hline(first, h // 2 - 1, 0, w - 2)
            hline(second, h // 2, 1, w - 1)
        else:
            _emboss(kind == "Embossed", w, h, hline, vline)
    elif kind == "Double":
        _double(w, h, color, None, None, hline, vline)
    else:                                     # Single, Rounded
        _boxed(kind, w, h, color, 0, None, lines)


def _emboss(raised, w, h, hline, vline):
    """«Выпуклая» (`raised`) — светлые верх и лево, тёмные низ и право; «Вдавленная» — наоборот."""
    first, second = (EMBOSS_LIGHT, EMBOSS_DARK) if raised else (EMBOSS_DARK, EMBOSS_LIGHT)
    hline(first, 0, 0, w - 2)
    vline(first, 0, 0, h - 2)
    hline(second, h - 1, 1, w - 1)
    vline(second, w - 1, 1, h - 1)


def _boxed(kind, w, h, color, top, resume, lines):
    """Рамка-прямоугольник (у «Скруглённой» углы радиуса `ROUND_R` при высоте не меньше `ROUND_MIN_H`) с верхней линией на строке `top`; `resume` — столбец, где верхняя
    линия возобновляется после заголовка (`None` — заголовка нет, линия сплошная); слева линия кончается на 8-м столбце."""
    r = ROUND_R if kind == "Rounded" and h >= ROUND_MIN_H and h - top >= 2 * ROUND_R + 1 else 0
    if not r:        # прямые углы: отрезки по пикселям (углы закрашены целиком)
        a = [(top, 0, 7 if resume is not None else w - 1)] + ([(top, resume, w - 1)] if resume is not None and resume <= w - 1 else [])
        d = "".join(f"M{_n(x1)} {_n(row + 0.5)}H{_n(x2 + 1)}" for row, x1, x2 in a)
        d += f"M0.5 {_n(top)}V{_n(h)}M{_n(w - 0.5)} {_n(top)}V{_n(h)}M0 {_n(h - 0.5)}H{_n(w)}"
        lines.append((color, d))
        return
    t, left, right, bottom = top + 0.5, 0.5, w - 0.5, h - 0.5
    arc = (lambda dx, dy: f"A{r} {r} 0 0 1 {_n(dx)} {_n(dy)}") if r else (lambda dx, dy: f"L{_n(dx)} {_n(dy)}")
    if resume is None:
        head = f"M{_n(left)} {_n(t + r)}{arc(left + r, t)}H{_n(right - r)}"
    else:
        head = f"M{_n(left)} {_n(t + r)}{arc(left + r, t)}H{_n(min(8, right))}M{_n(min(resume, right - r))} {_n(t)}H{_n(right - r)}"
    d = f"{head}{arc(right, t + r)}V{_n(bottom - r)}{arc(right - r, bottom)}H{_n(left + r)}{arc(left, bottom - r)}V{_n(t + r)}"
    lines.append((color, d))


def _double(w, h, color, line_full, resume, hline, vline):
    """«Двойная» рамка: внешний прямоугольник по краям box и внутренний на 2 px внутрь; у заголовка (`line_full` — строка линии заголовка) верхние линии лежат на
    `line_full − 1` и `line_full + 1` и разорваны до `resume`."""
    if line_full is None:
        hline(color, 0, 0, w - 1)
        hline(color, h - 1, 0, w - 1)
        vline(color, 0, 0, h - 1)
        vline(color, w - 1, 0, h - 1)
        hline(color, 2, 2, w - 3)
        hline(color, h - 3, 2, w - 3)
        vline(color, 2, 2, h - 3)
        vline(color, w - 3, 2, h - 3)
        return
    o, i = line_full - 1, line_full + 1
    hline(color, o, 0, 9)
    hline(color, o, resume, w - 1)
    hline(color, i, 2, 9)
    hline(color, i, resume, w - 3)
    vline(color, 0, o, h - 1)
    vline(color, w - 1, o, h - 1)
    vline(color, 2, i, h - 3)
    vline(color, w - 3, i, h - 3)
    hline(color, h - 1, 0, w - 1)
    hline(color, h - 3, 2, w - 3)


def frame(it, x, y, w, h, font):
    """Линии рамки: пути SVG, сдвинутые на (x, y) группой `<g transform>` не нужны — координаты уже абсолютные."""
    out = []
    for color, d in plan(it, w, h, font)["lines"]:
        out.append(f"<path class='frame' d='{shift(d, x, y)}' fill='none' stroke='{color}'/>")
    return out


def shift(d, x, y):
    """Путь SVG `d` (команды M, H, V, L, A) со сдвигом на (x, y)."""
    import re
    tokens = re.findall(r"[MHVLA]|-?\d+(?:\.\d+)?", d)
    res, cmd, args = [], None, []

    def flush():
        if cmd is None:
            return
        if cmd == "H":
            res.append("H" + _n(float(args[0]) + x))
        elif cmd == "V":
            res.append("V" + _n(float(args[0]) + y))
        elif cmd in ("M", "L"):
            res.append(f"{cmd}{_n(float(args[0]) + x)} {_n(float(args[1]) + y)}")
        elif cmd == "A":
            res.append(f"A{args[0]} {args[1]} {args[2]} {args[3]} {args[4]} {_n(float(args[5]) + x)} {_n(float(args[6]) + y)}")
    for tok in tokens:
        if tok in ("M", "H", "V", "L", "A"):
            flush(); cmd, args = tok, []
        else:
            args.append(tok)
    flush()
    return "".join(res)


def title_parts(doc, it, x, y, w, h, font):
    """Заголовок рамки: текст со срезом по рамке (платформа не рисует ничего вне box)."""
    p = plan(it, w, h, font)
    if not p["title"]:
        return []
    at, base, text = p["title"]
    ident = f"gb{it.index}"
    clip = f"<clipPath id='{ident}'><rect x='{_n(x)}' y='{_n(y)}' width='{_n(w)}' height='{_n(h)}'/></clipPath>"
    return [clip, f"<g clip-path='url(#{ident})'>{_text(x + at, y + base, text, font=font, fill=title_color(it))}</g>"]
