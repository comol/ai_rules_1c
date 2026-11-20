"""Ширина текста надписи в пикселях по метрике шрифта форм 8.x.

Шрифт формы по умолчанию (`font.source = Auto`) — «MS Sans Serif» 8 пунктов. В предприятии он отображается метрикой
Microsoft Sans Serif на 11 px; это вывод из наблюдений, а не измерение шрифта предприятия. Ширины знаков берутся из таблиц
`hdmx` файла `Microsoft Sans Serif.ttf` (это целые ширины, как их рисует GDI) для латиницы, цифр, кириллицы и знаков
препинания: всего 200 знаков, в том числе «…» шириной 6 и неразрывный пробел шириной 3. Таблицы для ppem 9…24 лежат в
`textwidth_data.BY_PPEM`, а `WIDTHS` и `ADVANCE` — это срез для ppem 11. Знак, которого нет в таблице, считается самым широким
для данного ppem (`UNKNOWN` при 11 px), чтобы надпись не обрезалась.

Размер и жирность. Шрифт элемента может отличаться от шрифта формы (например, шрифт стиля `NormalTextFont` 10 pt жирный). В
предприятии подтверждено: подпись из 17 знаков (например, «Основание отказа:») помещается целиком при ширине 142 для 10 pt жирного, 114
для 8 pt жирного и 126 для 10 pt обычного. Модель такая:

* ppem = MulDiv(pt, 96, 72) с округлением до ближайшего (половина округляется вверх): 8 pt даёт 11, 10 pt даёт 13. Ширина
  равна сумме значений `hdmx` для этого ppem.
* Жирный шрифт добавляет 1 px на знак: у Microsoft Sans Serif нет жирного начертания, и GDI утолщает его искусственно.

Не проверялось. В этих случаях `measure` возвращает `exact=False` и причину словами, а число является оценкой: курсив, имя
шрифта кроме «Microsoft Sans Serif» и «MS Sans Serif», масштаб не равный 100 %, ppem вне диапазона 9…24 (оценка берёт ширины
для 11 px пропорционально ppem), шрифт стиля без размера в переопределениях (и без насыщенности — то же), системный шрифт
(`SystemFont`) и абсолютный шрифт (`Absolute`). Подчёркивание и зачёркивание, как принято считать, ширину не меняют.

Ширина надписи у конструктора платформы равна ширине текста подписи вместе с двоеточием, без запаса.

Действующий шрифт элемента определяют `element_font` (шрифт элемента или колонки по записи кодека) и `form_font` (шрифт
формы: `form.container.layout_holder.layout_list.layout.font`, `FORMAT.md`, узлы `Layout10` и `Layout13`, поле 4 `font`).
Значение `Auto` берёт шрифт формы, но только абсолютный (`Absolute`: гарнитура, размер, вес — «Arial 13 полужирный» действует на
все элементы «Авто»). Шрифт формы вида «шрифт стиля с переопределениями» и «Авто» с переопределениями (вес 700, размер) элементы «Авто»
не наследуют: у них шрифт по умолчанию, 8 pt обычный (проверено в предприятии: шрифт формы «Авто» с весом 700 — надписи «Авто» на экране обычные).
"""
from .textwidth_data import BY_PPEM

# срез для ppem 11 (сверяется с `textwidth_data` и со шрифтом)
WIDTHS = BY_PPEM[11]
ADVANCE = {ch: width for width, chars in WIDTHS.items() for ch in chars}
UNKNOWN = max(WIDTHS)  # знака нет в таблице: берётся самая большая ширина, чтобы надпись не обрезалась

PPEM_MIN, PPEM_MAX = min(BY_PPEM), max(BY_PPEM)
DEFAULT_PPEM = 11  # шрифт формы по умолчанию: 8 pt
DEFAULT_SIZE = 8
MEASURED_FACES = ("Microsoft Sans Serif", "MS Sans Serif")
BOLD_WEIGHT = 700  # насыщенность: 400 — обычный, 700 — полужирный (`Font.v0.weight`); значения от 700 считаются жирными

_ADVANCE_BY_PPEM = {ppem: {ch: w for w, chars in table.items() for ch in chars} for ppem, table in BY_PPEM.items()}
_UNKNOWN_BY_PPEM = {ppem: max(table) for ppem, table in BY_PPEM.items()}


class Measured(tuple):
    """`(px, exact, why)`: ширина, признак «проверено» и причина «не проверялось» словами (у проверенного шрифта пусто)."""
    __slots__ = ()
    px = property(lambda self: self[0])
    exact = property(lambda self: self[1])
    why = property(lambda self: self[2])

    def __new__(cls, px, exact, why=""):
        return super().__new__(cls, (px, exact, why))


def ppem_of(size):
    """Размер в ppem по размеру в пунктах: MulDiv(pt, 96, 72) с округлением до ближайшего, половина вверх (целая арифметика по
    десятым долям пункта).
    """
    return (round(size * 10) * 96 + 360) // 720


def measure(text, font=None):
    """`Measured(px, exact, why)`: ширина текста для шрифта `font` и признак «проверено».

    `font` — описание шрифта: словарь с ключами `size` (пункты; `None` — размер неизвестен), `bold`, `italic`, `face`, `scale` и
    `unmeasured` (причина, если шрифт уже при разборе записи признан непроверенным, см. `element_font`). Если ключа нет, берётся
    значение по умолчанию (8 pt, обычный, прямой, 100 %). `font=None` означает шрифт формы по умолчанию, он проверен.

    Шрифт считается проверенным, если выполнены все условия: ppem в диапазоне 9…24, шрифт не курсивный, имя шрифта входит в
    `MEASURED_FACES` или не задано, масштаб равен 100 и причины `unmeasured` нет. Тогда ширина равна сумме `hdmx` для этого ppem
    плюс по пикселю на знак для жирного шрифта. Иначе результат — оценка: ширины для 11 px пропорционально ppem (если размер
    неизвестен, берётся 11 px), у жирного шрифта по-прежнему добавляется 1 px на знак, а `why` перечисляет все причины через «; ».
    """
    font = font or {}
    reasons = []
    if font.get("unmeasured"):
        reasons.append(font["unmeasured"])
    size = font.get("size", DEFAULT_SIZE)
    if size is None:
        ppem = DEFAULT_PPEM
        if not font.get("unmeasured"):
            reasons.append("размер шрифта не известен")
    else:
        ppem = ppem_of(size)
        if not PPEM_MIN <= ppem <= PPEM_MAX:
            reasons.append(f"размер {size:g} pt даёт {ppem} px, таблицы только для {PPEM_MIN}…{PPEM_MAX}")
    if font.get("italic"):
        reasons.append("курсив не проверялся")
    face = font.get("face")
    if face and face not in MEASURED_FACES:
        reasons.append(f"шрифт «{face}» не проверялся (проверялся только Microsoft Sans Serif)")
    scale = font.get("scale", 100)
    if scale not in (None, 100):
        reasons.append(f"масштаб {scale} % не проверялся")
    if PPEM_MIN <= ppem <= PPEM_MAX:
        advance, unknown = _ADVANCE_BY_PPEM[ppem], _UNKNOWN_BY_PPEM[ppem]
        px = sum(advance.get(ch, unknown) for ch in text)
    else:
        px = -(-sum(ADVANCE.get(ch, UNKNOWN) for ch in text) * ppem // DEFAULT_PPEM)
    if font.get("bold"):
        px += len(text)
    return Measured(px, not reasons, "; ".join(reasons))


def width(text, font=None):
    """Ширина текста в пикселях. Без `font` используется шрифт формы по умолчанию (11 px), а знак вне таблицы считается самым
    широким. С `font` результат тот же, что у `measure(text, font).px`. Для непроверенного шрифта это оценка, а признак
    «проверено» и причину возвращает только `measure`.
    """
    return measure(text, font).px


# Действующий шрифт элемента

DEFAULT_FONT = {"source": "Auto", "size": DEFAULT_SIZE, "bold": False, "italic": False, "underline": False, "strikeout": False,
                "face": None, "scale": 100}


def _form_font_record(doc):
    """Запись шрифта формы или `None`: `form.container.layout_holder.layout_list.layout.font` (`FORMAT.md`, `Layout10` и `Layout13`)."""
    node = doc
    for key in ("form", "container", "layout_holder", "layout_list", "layout", "font"):
        node = node.get(key) if isinstance(node, dict) else None
    return node if isinstance(node, dict) and "source" in node else None


def _own_font_record(element, key):
    """Запись шрифта `key` в содержимом элемента или колонки, самая близкая по вложенности. В списки и в `control` колонки поиск не заходит."""
    found = []

    def walk(node, depth):
        for name, value in node.items():
            if name == "control" or not isinstance(value, dict):
                continue
            if name == key and "source" in value:
                found.append((depth, value))
            else:
                walk(value, depth + 1)
    if isinstance(element, dict):
        walk(element, 0)
    return min(found, key=lambda pair: pair[0])[1] if found else None


def _describe(record, base):
    """Описание шрифта по записи кодека. Параметр `base` — описание шрифта формы, которое берёт значение `Auto`."""
    source = record.get("source")
    over = record.get("overrides") or {}
    out = {"source": source, "size": None, "bold": False, "italic": False, "underline": False, "strikeout": False,
           "face": over.get("face"), "scale": record.get("scale", 100)}
    why = None
    if source == "Auto":
        out.update(size=base["size"], bold=base["bold"], italic=base["italic"], underline=base.get("underline", False),
                   strikeout=base.get("strikeout", False), face=over.get("face", base["face"]))
        why = base.get("unmeasured")
    elif source == "StyleFont":
        style = (record.get("ref") or {}).get("style_font", "?")
        if "size10" not in over:
            why = f"шрифт стиля {style} без размера в переопределениях: размер стиля не проверялся"
        elif "weight" not in over:
            why = f"шрифт стиля {style} без насыщенности в переопределениях: вес стиля не проверялся"
    elif source == "SystemFont":
        why = "системный шрифт (SystemFont) не проверялся"
    else:
        why = f"шрифт вида {source} (абсолютный) не проверялся"
        out.update(face=record.get("face"), italic=bool(record.get("italic")), underline=bool(record.get("underline")),
                   strikeout=bool(record.get("strikeout")),
                   bold=(record.get("weight") or 400) >= BOLD_WEIGHT)
        if record.get("size10") is not None:
            out["size"] = record["size10"] / 10
        out["unmeasured"] = why
        return out
    if "size10" in over:
        out["size"] = over["size10"] / 10
    if "weight" in over:
        out["bold"] = over["weight"] >= BOLD_WEIGHT
    if "italic" in over:
        out["italic"] = bool(over["italic"])
    for flag in ("underline", "strikeout"):
        if flag in over:
            out[flag] = bool(over[flag])
    if why:
        out["unmeasured"] = why
    return out


def form_font(doc):
    """Описание шрифта формы по записи `form…layout.font`. Если записи нет, берётся значение по умолчанию (8 pt, обычный)."""
    record = _form_font_record(doc) if isinstance(doc, dict) else None
    return _describe(record, dict(DEFAULT_FONT)) if record else dict(DEFAULT_FONT)


STYLE_AUTO_NOTE = ("шрифт формы — шрифт стиля: «Авто» у элементов равен этому шрифту стиля без переопределений формы "
                   "(жирность проверена в предприятии; размер — по тому же признаку «Начертание → Из стиля», не проверялся)")


def auto_font(form):
    """Что значит «Авто» у элемента: абсолютный шрифт формы он наследует целиком, а когда шрифт формы —
    шрифт стиля, «Авто» берёт этот стиль БЕЗ переопределений формы: жирность и размер формы не наследуются (проверено в предприятии:
    шрифт формы «Шрифт текста» полужирный, надписи и флажки «Авто» — обычные). Размер при этом не проверялся (`STYLE_AUTO_NOTE`, его называет `render`)."""
    record = _form_font_record(form) if isinstance(form, dict) else None
    if record is not None and record.get("source") in ("StyleFont", "Auto"):  # «Авто» формы с переопределением — то же (проверено: вес 700)
        return dict(DEFAULT_FONT)
    return form_font(form) if form is not None else dict(DEFAULT_FONT)


def element_font(element, form=None, key="font"):
    """Возвращает действующий шрифт элемента или колонки по записи кодека (`key="text_font"` — шрифт текста ячейки в режиме показа).

    `element` — узел элемента или колонки из документа (`doc["form"]["container"]["elements"]["items"][i]`). `form` — документ
    целиком, из него `Auto` берёт абсолютный шрифт формы (`auto_font`); без `form` используется значение по умолчанию 8 pt. Если у узла нет записи
    шрифта, действует шрифт формы. Результат — описание для `measure`: `source`, `size` (pt; `None`, если неизвестен), `bold`,
    `italic`, `underline`, `strikeout`, `face`, `scale` и `unmeasured` (причина словами, если шрифт не проверен).
    """
    base = auto_font(form)
    record = _own_font_record(element, key)
    return _describe(record, base) if record else base
