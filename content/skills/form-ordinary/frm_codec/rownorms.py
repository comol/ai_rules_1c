"""Числа ряда и блоков «рядом» для `generate`: чтение `data/row_norms.json` (перепись — `rowcensus`, пересборка — скрипт в репозитории навыка).

Число из таблицы — медиана наблюдений (у значения с большинством это оно само); к нему идёт слово об источнике (`source`): сколько наблюдений и форм, есть ли у
самого частого значения большинство. Строка, где наблюдений меньше `THIN_OBS`, помечена «мало данных»; для таких строк есть замена из соседней строки (`gap`, `field_width`),
которую называет то же слово. Что корпус не мерит, здесь не живёт: числа без замера остаются в `generate` с пометкой «не проверялось».
"""
import functools

from .datapaths import DATA_DIR
from . import rowcensus

THIN_OBS = 30  # меньше наблюдений в строке — «мало данных»: число остаётся, но с пометкой, а где есть соседняя строка, берётся она
FIELD_CLASSES = ("Date", "Time", "DateTime", "S", "N", "#", "other")
JOINT_TW = rowcensus.JOINT_TW


@functools.lru_cache(maxsize=1)
def table():
    return rowcensus.load()


def _pct(share):
    return f"{share * 100:.1f}".replace(".", ",") + " %"


def source(row, unit="px"):
    """Слова об источнике числа строки: `корпус: N наблюдений в M формах` и про большинство."""
    if row["n"] == 0:
        return "корпус: наблюдений нет"
    words = f"корпус: {row['n']} набл. в {row['forms']} формах"
    value, share, _count = row["top"][0]
    if row["majority"]:
        words += f"; у значения {value} {unit} большинство — {_pct(share)}"
    else:
        words += f"; по корпусу большинства нет, самое частое {value} {unit} — {_pct(share)}"
    if row["n"] < THIN_OBS:
        words += f"; мало данных (меньше {THIN_OBS})"
    return words


def _row(path):
    node = table()
    for key in path:
        node = node[key]
    return node


def gap(prev, nxt, text_w=None):
    """Зазор между звеньями ряда: `(px, слова об источнике)`. `prev` — `field` (поле или пара), `check` (флажок), `button`; `nxt` — `label` (следующая пара), `check`, `button`;
    `text_w` — ширина текста надписи следующей пары: короткая («с», «по», «до») ставится ближе. Строка с малым числом наблюдений заменяется строкой после поля."""
    if nxt == "label" and prev == "field" and text_w is not None and text_w <= JOINT_TW:
        key = "field>label_joint"
    else:
        key = f"{prev}>{nxt}"
    gaps = table()["gap"]
    row = gaps.get(key)
    if row is None or row["n"] < THIN_OBS:
        fallback = gaps.get(f"field>{nxt}")
        if fallback is not None and fallback["n"] >= THIN_OBS:
            return fallback["median"], f"строка {key}: {source(row) if row else 'наблюдений нет'}; взята строка field>{nxt}: {source(fallback)}"
    return row["median"], f"{key}: {source(row)}"


def field_width(cls):
    """Ширина поля ряда, которое не растягивается, по составу типа: `(px, слова)`. `cls` — `Date`, `Time`, `DateTime`, `S`, `N`, `#`, `other`. «Только время» — мало данных: берётся ширина даты."""
    rows = table()["field_width"]
    row = rows.get(f"{cls}:fixed")
    if row is None or row["n"] < THIN_OBS:
        if cls == "Time":
            base = rows["Date:fixed"]
            return base["median"], f"Time:fixed: {source(row)}; взята ширина даты Date:fixed: {source(base)}"
    return row["median"], f"{cls}:fixed: {source(row)}"


def button(size, what):
    """Кнопка формы в ряду полей: `(px, слова)`. `size` — `regular` (подпись не уже `rowcensus.REGULAR_TW`) или `short` (кнопка «…»); `what` — `height`, `width`, `pad`
    (ширина кнопки минус ширина подписи), для `width` у обычной — берётся нижняя граница (`floor`)."""
    row = table()["button"][f"{size}:{what}"]
    value = row["floor"] if what == "width" and size == "regular" else row["median"]
    note = " (нижняя граница: ниже неё не больше 1 % наблюдений)" if what == "width" and size == "regular" else ""
    return value, f"{size}:{what}{note}: {source(row)}"


def button_floor():
    """Самая узкая кнопка формы в ряду полей корпуса: `(px, слова)` — уже её `width` кнопки не бывает."""
    row = table()["button"]["short:width"]
    return row["min"], f"button short:width, наименьшее: {source(row)}"


def radio_gap():
    row = table()["radio"]["gap"]
    return row["median"], f"radio/gap: {source(row)}"


def side_gap():
    row = table()["side_gap"]
    return row["median"], f"side_gap: {source(row)}"


def frame_title_pad():
    """Запас рамки с заголовком: заголовок полной рамки начинается с отступом `FULL_INDENT` слева и кончается им же справа (`render.groupbox`, измерено в предприятии), корпус
    запас не уточняет: у самой узкой рамки он больше (`frame_title_margin.min`)."""
    from .render import groupbox
    pad = 2 * groupbox.FULL_INDENT["Single"]
    row = table()["frame_title_margin"]
    return pad, (f"render.groupbox.FULL_INDENT: отступ {groupbox.FULL_INDENT['Single']} px с каждой стороны (измерено в предприятии); корпус: {row['n']} рамок с заголовком в {row['forms']} формах, "
                 f"наименьший запас {row['min']} px — ни одна рамка не уже заголовка с этим отступом")


def split_min(axis):
    """Наименьшая часть таблицы рядом с разделителем: `(px, слова)`. `axis` — `left_right` (ширина) или `top_bottom` (высота)."""
    row = table()["split_table"][axis]
    return row["min"], f"split_table/{axis}: наименьшая {'ширина' if axis == 'left_right' else 'высота'} таблицы рядом с разделителем; {source(row)}"


def doc_lines():
    """Строки раздела «Числа ряда» для `docs/generate.md`: по строке на число, которым пользуется `generate` (из файла таблицы)."""
    out = []
    for prev, nxt, tw in (("field", "label", 99), ("field", "label", JOINT_TW), ("field", "check", None), ("field", "button", None),
                          ("check", "label", None), ("check", "check", None), ("check", "button", None),
                          ("button", "label", None), ("button", "check", None), ("button", "button", None)):
        value, words = gap(prev, nxt, tw)
        out.append(f"- зазор {prev} → {nxt}{' (связка, текст ≤ ' + str(JOINT_TW) + ' px)' if tw == JOINT_TW else ''}: {value} px — {words}")
    for cls in FIELD_CLASSES:
        value, words = field_width(cls)
        out.append(f"- ширина поля ряда {cls}: {value} px — {words}")
    for size in ("regular", "short"):
        for what in ("height", "width", "pad"):
            value, words = button(size, what)
            out.append(f"- кнопка {size} {what}: {value} px — {words}")
    for fn in (radio_gap, side_gap, frame_title_pad):
        value, words = fn()
        out.append(f"- {fn.__name__}: {value} px — {words}")
    for axis in ("left_right", "top_bottom"):
        value, words = split_min(axis)
        out.append(f"- split_min {axis}: {value} px — {words}")
    return out
