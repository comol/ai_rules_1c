"""Поле календаря (`CalendarBox`): сетка месяцев, как её рисует предприятие.

Размеры сняты со снимков окна «Производственный календарь» (поле 440×339 и то же окно, развёрнутое на экран 1920×1080), координаты отсчитываются от левого
верхнего угла поля (рамка — пиксель 0):

* блок месяца 126 px шириной: полоса заголовка 15 px (рамка #E7E7CE, заливка #F7F7DE, название и год по центру), строка дней недели (базовая линия на 27 px от верха
  полосы), чёрная черта под ней на 29, семь столбцов по 18 px и шесть строк по 18 px от 30 (цифра по центру ячейки, базовая линия на 14 px от верха ячейки);
* шаг блоков — 141 px по горизонтали и 138 по вертикали; первая полоса стоит на 16 px правее и на 24 ниже угла поля при ширине 440;
* столбцов умещается `(ширина − 126 − 32) // 141 + 1` (при 440 — три, при 1900 — тринадцать), блоки отступают от краёв поровну: `(ширина − 126 − 141·(столбцов − 1)) / 2`
  (16 и 41 px по снимкам); месяцев рисуется не больше двенадцати, строк — сколько вмещает высота: `(высота − 63) // 138` (при 339 — две; в развёрнутом окне двенадцать
  месяцев при тринадцати столбцах стоят в одной строке);
* внизу, на 39 px выше нижнего края поля, полоса даты на ширину всех столбцов (15 px) с текстом справа и треугольником ▾ (10×5, #5A4200).

Данных у рендера нет: год, число и название месяцев в файле не заданы, поэтому рисуется условный 2026 год с января, выделение сегодняшнего дня, цвета выходных и красная
рамка текущего дня на снимке развёрнутого окна не рисуются. Об этом пишет `NOTE`.
"""
import calendar

from .core import _n, _text

BLOCK_W, BLOCK_H, COL_STEP, ROW_STEP = 126, 15, 141, 138
CELL = 18
MARGIN_MIN, TOP, BOTTOM = 16, 24, 39
YEAR = 2026
MONTHS = ("Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь")
DAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
BAND_EDGE, BAND_FILL, DAY_COLOR, HEAD_COLOR = "#e7e7ce", "#f7f7de", "#7b7b7b", "#423100"
STRIP_TEXT = f"1 января {YEAR} г."
NOTE = (f"поле календаря нарисовано условным {YEAR} годом с января (год, месяцы и числа в файле не заданы): сетка месяцев, шаги и число месяцев по размеру поля — по снимкам; "
        "выделение выбранного дня, цвета выходных и праздников и рамка текущего дня не нарисованы")


def grid(w, h):
    """`(столбцов, строк, отступ слева)`: сколько блоков месяцев умещается в поле шириной `w` и высотой `h` и где стоит первый."""
    cols = max((w - BLOCK_W - 2 * MARGIN_MIN) // COL_STEP + 1, 1)
    rows = max(min(-(-12 // cols), (h - TOP - BOTTOM) // ROW_STEP), 0)
    margin = max((w - BLOCK_W - COL_STEP * (cols - 1)) / 2, MARGIN_MIN) if cols > 1 else MARGIN_MIN
    return cols, rows, margin


def _month(x, y, month):
    out = [f"<rect class='cal-head' x='{_n(x + 0.5)}' y='{_n(y + 0.5)}' width='{BLOCK_W - 1}' height='{BLOCK_H - 1}' fill='{BAND_FILL}' stroke='{BAND_EDGE}'/>",
           _text(x + BLOCK_W / 2, y + 12, f"{MONTHS[month - 1]} {YEAR}", "middle", None, HEAD_COLOR)]
    out += [_text(x + CELL * c + CELL / 2, y + 27, name, "middle", None, "#000000") for c, name in enumerate(DAYS)]
    out.append(f"<rect class='cal-days' x='{_n(x)}' y='{_n(y + 29)}' width='{BLOCK_W}' height='1' fill='#000'/>")
    first = calendar.monthrange(YEAR, month)
    for day in range(1, first[1] + 1):
        slot = first[0] + day - 1
        out.append(_text(x + CELL * (slot % 7) + CELL / 2, y + 30 + CELL * (slot // 7) + 14, str(day), "middle", None, DAY_COLOR))
    return out


def draw(doc, it, x, y, w, h):
    cols, rows, margin = grid(w, h)
    out = []
    for k in range(min(12, cols * rows)):
        out += _month(x + margin + COL_STEP * (k % cols), y + TOP + ROW_STEP * (k // cols), k + 1)
    left, right = x + margin, x + margin + COL_STEP * (cols - 1) + BLOCK_W
    top = y + h - BOTTOM
    if right - left > 0 and top > y + TOP:
        out.append(f"<rect class='cal-strip' x='{_n(left + 0.5)}' y='{_n(top + 0.5)}' width='{_n(right - left - 1)}' height='{BLOCK_H - 1}' fill='{BAND_FILL}' stroke='{BAND_EDGE}'/>")
        out.append(_text(right - 22, top + 12, STRIP_TEXT, "end", None, HEAD_COLOR))
        out.append(f"<path class='cal-arrow' d='M{_n(right - 11)} {_n(top + 5)}h10l-5 5z' fill='#5a4200'/>")
    return out
