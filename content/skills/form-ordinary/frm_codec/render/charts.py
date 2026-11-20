"""Диаграмма Ганта и индикатор: каркас по снимкам предприятия (опыт e239, формы 13 и 15; шрифт 8 pt, размеры клиента 1200×660 и 1300×714).

**Диаграмма Ганта без данных** (запись тела версии 74, рамка «Нет рамки», «Поддержка масштаба» — «Все данные», полный интервал определяется автоматически):

* заголовок диаграммы (позиция 29 тела) — по центру box (левый край — целая часть половины свободного места), основание строки на 10 px ниже верха, цвет текста темы;
* шкала дней — полоса в 16 равных клеток: заливка `#F7F7F7`, строки 15…31 от верха box (17 строк), разделители `#CED2CE` в столбцах `x + 1 + k·(w − 3)/16` (целая часть) от строки 14 до строки 33
  включительно, нижняя линия `#CED2CE` в строке 33 от `x + 1` до `x + w − 3`, правый край шкалы — линия `#A5A5A5` в столбце `x + w − 2` от строки 14 до `h − 2` включительно (до низа диаграммы);
  клетка шириной от разделителя + 2 до следующего − 2 (первая — с `x + 2`), подпись «ДД Дн» (число и день недели) от левого края клетки, основание на 28 px ниже верха, цвет `#4A4E4A`;
* ни рамки, ни заливки тела у диаграммы нет (виден фон формы). Число клеток — 16 при обеих ширинах (1184 и 1267 px): клетки растягиваются, а число дней берётся из полного интервала файла
  (позиции 12 и 13 блока содержимого: `ГГГГММДДЧЧММСС`; в снимке интервал — 16 целых суток с первого числа, подписи «01 Чт» … «16 Пт»).

Рисуется шкала только для этого случая: полный интервал — ровно 16 целых суток и «Поддержка масштаба» — «Все данные». Для другого интервала и масштаба число клеток и подписи не снимались.

**Индикатор** без значения: пустое поле без заливки (виден фон формы), рамка `#B5B184` в 1 px со скруглёнными углами радиуса 4 (пиксели углов — `CORNERS`, свои у каждого угла),
каким бы ни был признак «Нет рамки» в файле (снимок формы 15: индикатор 868×40, «Нет рамки», рамка есть).
"""
import datetime

from .. import diagrams, textwidth
from .core import FORM_BG, _dig, _n, _text

BODY_VERSION = 74
TITLE_AT = 29                                # позиция заголовка диаграммы в теле
DAYS = 16
GANTT_TITLE_BASE = 10
BAND_TOP, BAND_ROWS, SEP_TOP, LINE_AT, TEXT_BASE = 15, 17, 14, 33, 28
BAND_FILL, SEP_COLOR, END_COLOR, SCALE_TEXT = "#f7f7f7", "#ced2ce", "#a5a5a5", "#4a4e4a"
DAY_NAMES = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
SCALE_ALL_DATA = 2                           # «Поддержка масштаба»: Все данные

GANTT_NOTE = ("диаграмма Ганта нарисована по снимку предприятия без данных: заголовок и шкала из 16 суток полного интервала файла; рамки у диаграммы нет, тело пусто, данные и их интервалы не рисуются")
GANTT_SCALE_NOTE = ("шкала диаграммы Ганта не нарисована: число клеток и подписи сняты только для полного интервала из 16 целых суток при «Поддержке масштаба» «Все данные»")
PROGRESS_NOTE = "индикатор нарисован пустым полем с рамкой, как у поля ввода (по снимку предприятия); значение и стиль показа (`show_style`) не рисуются"


def gantt_title(it):
    """`(известна ли запись, заголовок)`: тело версии 74 с заголовком в позиции 29; иначе `(False, "")`."""
    body = diagrams.body(it.node)
    if body is None or body[0] != BODY_VERSION or len(body) <= TITLE_AT:
        return False, ""
    record = body[TITLE_AT]
    text = record[2][1] if isinstance(record, list) and len(record) > 2 and isinstance(record[2], list) and len(record[2]) > 1 else None
    return (isinstance(text, str), text if isinstance(text, str) else "")


def gantt_known(it):
    """Диаграмму Ганта этого вида рендер рисует каркасом (запись тела известна)."""
    return it.type == "GanttChart" and gantt_title(it)[0]


def _date(code):
    """`ГГГГММДДЧЧММСС` (целое) → `(дата, время ЧЧММСС)` либо `None`."""
    if not isinstance(code, int) or isinstance(code, bool) or code < 10 ** 13:
        return None
    day, clock = divmod(code, 10 ** 6)
    try:
        return datetime.date(day // 10000, day // 100 % 100, day % 100), clock
    except ValueError:
        return None


def scale_days(it):
    """Даты клеток шкалы (16 суток подряд от начала полного интервала) либо `None`: интервал не из 16 целых суток или масштаб не «Все данные»."""
    content = _dig(it.node, "content")
    first, last = _date(_dig(content, "u12")), _date(_dig(content, "u13"))
    if first is None or last is None or first[1] != 0 or last[1] != 235959 or _dig(content, "u8") != SCALE_ALL_DATA:
        return None
    if (last[0] - first[0]).days + 1 != DAYS:
        return None
    return [first[0] + datetime.timedelta(days=k) for k in range(DAYS)]


def _gantt(doc, it, x, y, w, h):
    known, title = gantt_title(it)
    out = []
    if title:
        out.append(_text(x + (w - textwidth.measure(title).px) // 2, y + GANTT_TITLE_BASE, title, "start"))
    days = scale_days(it)
    if days is None:
        return out
    seps = [int(x + 1 + k * (w - 3) / DAYS) for k in range(DAYS)] + [x + w - 2]        # k = 16 — край шкалы
    out.append(f"<rect class='gantt-line' x='{_n(x + 1)}' y='{_n(y + LINE_AT)}' width='{max(w - 3, 0)}' height='1' fill='{SEP_COLOR}'/>")
    for k, day in enumerate(days):
        left = x + 2 if k == 0 else seps[k] + 2
        right = seps[k + 1] - 2
        out.append(f"<rect class='gantt-cell' x='{_n(left)}' y='{_n(y + BAND_TOP)}' width='{max(right - left + 1, 0)}' height='{BAND_ROWS}' fill='{BAND_FILL}'/>")
        out.append(_text(left, y + TEXT_BASE, f"{day.day:02d} {DAY_NAMES[day.weekday()]}", "start", None, SCALE_TEXT))
        if k:
            out.append(f"<rect class='gantt-sep' x='{_n(seps[k])}' y='{_n(y + SEP_TOP)}' width='1' height='{LINE_AT - SEP_TOP + 1}' fill='{SEP_COLOR}'/>")
    out.append(f"<rect class='gantt-end' x='{_n(seps[DAYS])}' y='{_n(y + SEP_TOP)}' width='1' height='{max(h - 2 - SEP_TOP + 1, 0)}' fill='{END_COLOR}'/>")
    return out


# Углы рамки индикатора (по снимку 868×40): пиксели, которые отличаются от прямой линии `#B5B184`; ключ — `(шаг по горизонтали, шаг по вертикали)` от угла внутрь.
# Не те же, что у поля ввода: радиус 4, у каждого угла свои оттенки, светлее на пиксель с отступом 4 (у верхнего правого — 3 на боковой стороне).
_L, _D, _M = "#efefde", "#cec6a5", "#bdb994"
_BL_LIGHT, _BL_MID = "#efebd6", "#c6bd9c"
CORNERS = {
    "tl": {(0, 0): FORM_BG, (1, 0): _L, (2, 0): _D, (4, 0): _M, (0, 1): _L, (0, 2): _D, (0, 4): _M},
    "tr": {(0, 0): FORM_BG, (1, 0): _L, (2, 0): _D, (4, 0): _M, (0, 1): _L, (0, 2): _D, (0, 3): _M},
    "bl": {(0, 0): FORM_BG, (1, 0): _BL_LIGHT, (2, 0): _M, (4, 0): _M, (0, 1): _BL_LIGHT, (0, 2): _BL_MID, (0, 4): _M},
    "br": {(0, 0): FORM_BG, (1, 0): _BL_LIGHT, (2, 0): _M, (4, 0): _M, (0, 1): _BL_LIGHT, (0, 2): _BL_MID, (0, 4): _M},
}
MIN_SIDE = 10          # меньшие размеры не снимались: углы не рисуются


def _progress(doc, it, x, y, w, h):
    """Индикатор: рамка рисуется общей (`_frame`), здесь скруглённые углы по снимку."""
    if w < MIN_SIDE or h < MIN_SIDE:
        return []
    out = []
    for name, pixels in CORNERS.items():
        for (dx, dy), color in pixels.items():
            px = x + dx if name in ("tl", "bl") else x + w - 1 - dx
            py = y + dy if name in ("tl", "tr") else y + h - 1 - dy
            out.append(f"<rect class='progress-corner' x='{px}' y='{py}' width='1' height='1' fill='{color}'/>")
    return out


DRAW = {"GanttChart": _gantt, "ProgressBar": _progress}
