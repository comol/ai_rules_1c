"""Кнопки поля ввода: заливка с градиентом, левая черта и значки «…», лупа, крестик, календарь, калькулятор, ▾, регулирование, «T» выбора типа.

Всё снято по пикселям с экрана предприятия (формы опытов, 25 полей и поля высотой 19…40 в обоих видах; карты значков — `field_glyph_data`). Кнопка — 15 px: черта слева
1 px и заливка 14 px. **Высота кнопки зависит от высоты поля.** Поле до `WRAP_MAX` (31) px высотой — рамка охватывает кнопки: заливка идёт на всю внутреннюю высоту (`h − 2`), нижняя линия рамки
проходит под кнопками, градиент растянут по высоте, значок стоит ниже вместе с серединой. Поле выше — кнопка остаётся 19 px в рамке (17 px заливки у верха), под ней фон формы, а рамка
поля ниже кнопки идёт по левому краю полосы кнопок. Заливка 8.3 — градиент по строкам (`FILL_ROWS`), черта — свой, более тёмный градиент (`LINE_ROWS`); у 8.2 заливка одна, `#F7F7DE`, черта
`#B5B184`. Правая кнопка поля срезана по углам рамки поля (`RIGHT_CORNERS`) у вида 8.3; у вида 8.2 углы прямые. У части кнопок на экране градиент сдвинут на одну строку (на экране 12 кнопок из 49),
от чего это зависит — не установлено; рисуется вид большинства.
"""
from . import field_glyph_data as data
from . import field_gradient_data as grad

BUTTON_H = 17
# высота кнопки в рамке 19 px: 17 внутри и две линии
BOX_H = 19
# последняя высота поля, у которой рамка охватывает кнопки (снято: 31 охватывает, 32 нет)
WRAP_MAX = 31
# заливка: (первая строка, последняя, цвет) — строки внутри рамки поля, 1…17
FILL_ROWS = ((1, 1, "#fffff7"), (2, 2, "#fffbf7"), (3, 5, "#f7fbef"), (6, 8, "#f7f7e7"), (9, 10, "#f7f3de"), (11, 11, "#eff3de"), (12, 12, "#efefde"),
             (13, 15, "#efefd6"), (16, 17, "#efebce"))
# черта слева от заливки: цвет каждой строки 1…17
LINE_ROWS = ("#eff3e7", "#efefde", "#efebd6", "#e7e7ce", "#e7e2c6", "#dedebd", "#dedab5", "#d6d6b5", "#d6d2ad", "#d6d2ad", "#d6d2ad", "#d6d2ad", "#d6d2ad",
             "#d6d6ad", "#d6d6ad", "#d6d6ad", "#d6d6ad")
# срез углов у правой кнопки: пиксели (смещение от черты, строка от верха поля; 15 — рамка поля) — цвет; фон формы за углом рисуется отдельно
RIGHT_CORNERS = {(13, 0): "#bdb994", (14, 0): "#d6d6b5", (14, 1): "#d6d6bd", (15, 1): "#d6d6b5", (15, 2): "#bdb994",
                 (15, 16): "#bdb994", (14, 17): "#d6d2b5", (15, 17): "#d6d6b5", (13, 18): "#bdb994", (14, 18): "#d6d6b5"}
RIGHT_BACK = ((15, 0), (15, 18))
# два пикселя сглаживания у нижнего угла (сдвигаются вместе с низом кнопки): второй у полей высотой 22…31 темнее, `#EFEBD6`, у остальных (19…21 и от 32) — `#EFEFD6`
RIGHT_SOFT = {(14, 16): "#efefd6", (13, 17): "#efefd6"}
SOFT_WRAP_MAX = 21
SOFT_WRAP_DARK = "#efebd6"
DISABLED = "#a5a594"
# недоступное поле (одна правая кнопка трёх в снимке): заливка бледнее, значок серый #A5A594
DISABLED_ROWS = ((1, 4, "#ffffff"), (5, 8, "#fffff7"), (9, 9, "#ffffef"), (10, 12, "#fffbef"), (13, 15, "#f7fbef"), (16, 17, "#f7f7e7"))
# вид 8.2: заливка плоская, черта цвета рамки, рамка недоступного поля светлая
FLAT_FILL, FLAT_LINE, FLAT_DISABLED_FRAME = "#f7f7de", "#b5b184", "#fffbce"
FLAT_DISABLED_DOTS, FLAT_DISABLED_CROSS = "#949494", "#a5a594"
# скруглённый угол рамки поля вида 8.3: пиксели от угла (x, y) — цвет; (0, 0) — фон формы; остальные углы — зеркально
CORNER = {(1, 0): "#d6d6b5", (2, 0): "#bdb994", (0, 1): "#d6d6b5", (1, 1): "#cec6a5", (2, 1): "#f7fbf7", (0, 2): "#bdb994", (1, 2): "#f7fbef"}
# значки вида 8.2 (у «…» и крестика — чёрные, без сглаживания; остальные значки этого вида не снимались, рисуются как у 8.3): (столбец, строка) внутри кнопки, как в `field_glyph_data`
DOTS_82 = {(c, r): "#000000" for c in (3, 6, 9) for r in (10, 11)}
CROSS_82 = {(c, r): "#000000" for r, cols in ((6, (3, 4, 8, 9)), (7, (4, 5, 7, 8)), (8, (5, 6, 7)), (9, (5, 6, 7)), (10, (4, 5, 7, 8)), (11, (3, 4, 8, 9))) for c in cols}


def wraps(h):
    """Рамка охватывает кнопки: поле выше 19 и не выше `WRAP_MAX`."""
    return BOX_H < h <= WRAP_MAX


def inner_h(h):
    """Высота заливки кнопки внутри рамки: у поля, которое рамка охватывает, — вся внутренняя высота, иначе 17."""
    return h - 2 if wraps(h) else BUTTON_H


def _hex(rgb):
    return "#" + "".join(f"{round(v):02x}" for v in rgb)


def _rgb(color):
    return [int(color[i:i + 2], 16) for i in (1, 3, 5)]


def _expand(runs):
    out = []
    for first, end, color in runs:
        out += [color] * (end - first + 1)
    return out


def _stretch(base, n):
    """Градиент из строк `base` на `n` строк: линейно между строками (для высот, которых на экране не снимали)."""
    if n == len(base):
        return list(base)
    out = []
    for r in range(n):
        t = r * (len(base) - 1) / (n - 1) if n > 1 else 0
        i = min(int(t), len(base) - 2)
        f = t - i
        a, b = _rgb(base[i]), _rgb(base[i + 1])
        out.append(_hex([a[k] * (1 - f) + b[k] * f for k in range(3)]))
    return out


def _runs_of(colors):
    out = []
    for row, color in enumerate(colors, 1):
        if out and out[-1][2] == color:
            out[-1] = (out[-1][0], row, color)
        else:
            out.append((row, row, color))
    return out


def fill_rows(h, flat=False, disabled=False):
    """Заливка кнопки по строкам: `[(первая, последняя, цвет)]`, строки внутри рамки поля с 1. Снятые высоты — как на экране, остальные растянуты."""
    n = inner_h(h)
    if flat:
        return [(1, n, FLAT_FILL)]
    if disabled:
        return _runs_of(_stretch(_expand(DISABLED_ROWS), n))
    if n == BUTTON_H:
        return list(FILL_ROWS)
    return list(grad.FILL[h]) if h in grad.FILL else _runs_of(_stretch(_expand(FILL_ROWS), n))


def line_rows(h, flat=False):
    """Цвет черты слева от заливки по строкам 1…n."""
    n = inner_h(h)
    if flat:
        return [FLAT_LINE] * n
    if n == BUTTON_H:
        return list(LINE_ROWS)
    return _expand(grad.LINE[h]) if h in grad.LINE else _stretch(list(LINE_ROWS), n)


def glyph_shift(h, flat=False):
    """На сколько строк значок ниже, чем в поле высотой 19 (снято у «…» и крестика): 8.3 — `(h − 18) // 2`, 8.2 — `(h − 19) // 2`; у поля выше `WRAP_MAX` значок не сдвигается."""
    if not wraps(h):
        return 0
    return (h - 19) // 2 if flat else (h - 18) // 2


def _runs(pixels):
    """Горизонтальные отрезки одного цвета: `[(столбец, строка, длина, цвет)]`."""
    out = []
    for (c, r), color in sorted(pixels.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        if out and out[-1][1] == r and out[-1][0] + out[-1][2] == c and out[-1][3] == color:
            out[-1] = (out[-1][0], r, out[-1][2] + 1, color)
        else:
            out.append((c, r, 1, color))
    return out


def _draw(pixels, x, y, name):
    body = "".join(f"<rect x='{x + c}' y='{y + r}' width='{n}' height='1' fill='{color}'/>" for c, r, n, color in _runs(pixels))
    return f"<g class='field-glyph {name}'>{body}</g>"


def face(line_x, top, last, form_bg, disabled=False, h=BOX_H, flat=False):
    """Кнопка: `line_x` — пиксель черты, `top` — верхняя рамка поля, `h` — высота поля. Заливка полосами, черта по строкам; у правой кнопки (`last`) углы срезаны (вид 8.3).
    Поле выше `WRAP_MAX`: под заливкой линия низа кнопки не здесь (её ведёт `under_line`)."""
    out = [f"<rect class='field-fill' x='{line_x + 1}' y='{top + first}' width='14' height='{end - first + 1}' fill='{color}' stroke='none'/>"
           for first, end, color in fill_rows(h, flat, disabled)]
    for row, color in enumerate(line_rows(h, flat), 1):
        out.append(f"<rect class='field-line' x='{line_x}' y='{top + row}' width='1' height='1' fill='{color}'/>")
    if last and not flat:
        shift = h - BOX_H if wraps(h) else 0
        low = lambda r: r + shift if r >= 16 else r  # noqa: E731  нижние углы идут за низом кнопки
        for (c, r) in RIGHT_BACK:
            out.append(f"<rect class='field-corner' x='{line_x + c}' y='{top + low(r)}' width='1' height='1' fill='{form_bg}'/>")
        corners_here = dict(RIGHT_CORNERS)
        corners_here.update(RIGHT_SOFT)
        if wraps(h) and h > SOFT_WRAP_MAX:
            corners_here[(13, 17)] = SOFT_WRAP_DARK
        out += [f"<rect class='field-corner' x='{line_x + c}' y='{top + low(r)}' width='1' height='1' fill='{color}'/>" for (c, r), color in corners_here.items()]
    return out


def under_line(left, right, top, color):
    """Нижняя линия кнопок у поля выше `WRAP_MAX`: на строке 18 от левого края полосы кнопок до столбца перед срезом правого угла."""
    return f"<rect class='field-under' x='{left}' y='{top + BOX_H - 1}' width='{max(right - left, 0)}' height='1' fill='{color}'/>"


def _mirror(px, x, y, w, h, flip_x, flip_y):
    return {(x + (w - 1 - dx if flip_x else dx), y + (h - 1 - dy if flip_y else dy)): color for (dx, dy), color in px.items()}


def corners(x, y, w, h, form_bg, left=True, right=True, bottom_right_at=None):
    """Скруглённые углы рамки поля вида 8.3. `right=False` — правые углы рисует кнопка; `bottom_right_at` — столбец левой линии полосы кнопок у поля выше `WRAP_MAX`:
    скруглён нижний правый угол той части поля, что левее полосы."""
    pix = {}
    places = []
    if left:
        places += [(x, y, False, False), (x, y, False, True)]
    if right:
        places += [(x, y, True, False), (x, y, True, True)]
    if bottom_right_at is not None:
        places.append((x, y, "edge", True))
    out = []
    for px, py, fx, fy in places:
        if fx == "edge":
            width = bottom_right_at - x + 1
            origin = _mirror(CORNER, x, py, width, h, True, fy)
            back = (bottom_right_at, y + h - 1)
        else:
            origin = _mirror(CORNER, px, py, w, h, fx, fy)
            back = (px + (w - 1 if fx else 0), py + (h - 1 if fy else 0))
        out.append(f"<rect class='field-corner' x='{back[0]}' y='{back[1]}' width='1' height='1' fill='{form_bg}'/>")
        pix.update(origin)
    out += [f"<rect class='field-corner' x='{cx}' y='{cy}' width='1' height='1' fill='{color}'/>" for (cx, cy), color in sorted(pix.items(), key=lambda kv: (kv[0][1], kv[0][0]))]
    return out


GLYPHS = {"dots": data.DOTS, "drop": data.DROP, "lupa": data.LUPA, "cross": data.CROSS, "spin": data.SPIN, "type": data.TYPE, "calendar": data.CALENDAR, "calc": data.CALC}
FLAT_GLYPHS = {"dots": DOTS_82, "cross": CROSS_82}


def glyph(name, x, y, disabled=False, flat=False):
    """Значок `name` в кнопке, чья внутренность начинается в (x, y); недоступное поле — серый #A5A594 (8.3) или #949494 у «…» и #A5A594 у крестика (8.2)."""
    pixels = (FLAT_GLYPHS if flat else {}).get(name) or GLYPHS[name]
    if disabled:
        gray = (FLAT_DISABLED_DOTS if name == "dots" else FLAT_DISABLED_CROSS) if flat and name in FLAT_GLYPHS else DISABLED
        pixels = {key: gray for key in pixels}
    return _draw(pixels, x, y, f"glyph-{name}")
