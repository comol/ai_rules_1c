"""Поля формы: надпись, поле ввода и поле выбора, кнопка формы, флажок, переключатель, поле табличного документа."""

from .. import edit, textwidth
from ..edit import datatype
from ..edit.names import DEFAULT_CONTROL, PATTERN_KIND
from . import field_glyphs, picture_bitmap, textmeasure, value_glyphs_data as vg
from .core import (
    EDGE, FIELD_BUTTON, FORM_BG, SCROLL_BAR, _caption, _clean, _color_of, _dig, _enabled, _first_text, _font_of, _form_enabled, _label_lines, _line_pitch, _n, _scroll_bar,
    _text, _vline)
from .bars import BUTTON_ICON, BUTTON_ICON_GAP, _icon

BUTTON_TEXT_SHIFT = 2    # подпись правее картинки стоит на 1 px правее середины места (пять кнопок: чернила на 1–2 px правее середины)
BUTTON_PICTURE_GAP = 2   # запас справа от картинки при усечении подписи: подпись «Кн PN…» у кнопки 66 px помещается до остатка 37–44 px при картинке 16 px, «Кн P…» — 29–36 при 22 px


def bound_elements(doc):
    """Индексы элементов с привязкой данных (`attributes/bindings`); форма с неразобранной таблицей привязок — пусто."""
    from ..edit import datapath
    attributes, _rows = datapath._attributes(doc)
    try:
        return {row.get(datapath.BIND_ELEMENT) for row in datapath.binding_rows(attributes)}
    except edit.EditError:
        return set()


def value_text(value):
    """Текст значения данных для надписи и поля: строка и число как есть; `Истина`/`Ложь` и «нет значения» — `None` (как булево значение показывает поле, не проверялось)."""
    return value[1] if value and value[0] in ("text", "number") else None


OPEN_DEFAULT_NOTE = ("значения при открытии, пока код их не задал (по снимкам предприятия, опыт e239v2): поле выбора, привязанное к реквизиту формы типа «Строка», со списком из простых строк показывает "
                     "первую строку списка; число — нуль по точности реквизита (`0`, `0,00`, `0,000`); переключатель группы, привязанной к числовому реквизиту, отмечен у того, чьё «ВыбираемоеЗначение» равно нулю. "
                     "Что ставит код при открытии, рендер без записей разбора кода не знает")


def _form_attribute_kind(doc, it):
    """Одиночный блок типа реквизита формы, к которому привязан элемент (`_attribute_blocks`), либо `None`."""
    blocks = _attribute_blocks(doc, it)
    return blocks[0] if blocks else None


def _zero_text(block):
    """Нуль числового реквизита в записи поля: знаков после запятой столько, сколько в точности (`0`, `0,00`, `0,000`); точность не задана — `None`."""
    fraction = block.get("fraction_digits")
    if not isinstance(fraction, int) or isinstance(fraction, bool) or fraction < 0:
        return None
    return "0" + ("," + "0" * fraction if fraction else "")


def _combo_first_value(it):
    """Первая строка списка выбора, если она простая (значение строкой, представления нет): `("text", значение)`, иначе `None` — какое значение показала бы платформа, не снималось."""
    lists = _dig(it.node, "content", "u1", "choice_list")
    first = lists[0] if isinstance(lists, list) and lists else None
    rows = _dig(first, "u2", "rows", "items")
    row = rows[0] if isinstance(rows, list) and rows else None
    value = row.get("value") if isinstance(row, dict) else None
    title = _dig(row, "presentation", "u2")
    if isinstance(value, dict) and value.get("kind") == "S" and isinstance(value.get("value"), str) and value["value"] and not (isinstance(title, list) and len(title) > 1):
        return ("text", value["value"])
    return None


def open_defaults(doc, form):
    """Значения полей при открытии формы, пока код их не задал: `{индекс элемента: значение}` в виде, который понимает рисунок (`("text", строка)`, `("number", "0,000")`).
    Только то, что снято в предприятии (опыт e239v2, 16 форм): поле выбора, привязанное к реквизиту формы типа «Строка», — первая простая строка непустого списка; числовое поле ввода,
    привязанное к реквизиту формы типа «Число», — нуль по точности; переключатели группы с первым, привязанным к реквизиту формы типа «Число», — значение 0 (отмечен тот, чьё выбираемое
    значение равно нулю). Остальные сочетания (булево, дата, ссылка, составной тип, привязка к объекту, поле без привязки, строка без списка) не снимались — их здесь нет."""
    out = {}
    for it in form.items.values():
        if it.type == "ComboBox":
            block = _form_attribute_kind(doc, it)
            first = _combo_first_value(it) if block and block.get(PATTERN_KIND) == "S" else None
            if first:
                out[it.index] = first
        elif it.type == "TextBox":
            block = _form_attribute_kind(doc, it)
            zero = _zero_text(block) if block and block.get(PATTERN_KIND) == "N" else None
            if zero:
                out[it.index] = ("number", zero)
    from ..brief.content import radio_groups          # группа переключателей — правило досье; импорт внутри: досье само зовёт рисунок
    for index, (head, _at, _size) in radio_groups(form).items():
        block = _form_attribute_kind(doc, head)
        if block and block.get(PATTERN_KIND) == "N":
            out[index] = ("number", "0")
    return out


FIELD_VALUE_BOOL = {True: "Да", False: "Нет"}      # Булево в поле ввода показано «Да» (снимок e230); «Нет» у Ложь не снималось


def _combo_list_values(it):
    """Значения строк списка выбора поля выбора без представления: `[(вид, значение)]`; у строки с представлением платформа может показывать его — такую строку не берём."""
    lists = _dig(it.node, "content", "u1", "choice_list")
    first = lists[0] if isinstance(lists, list) and lists else None
    rows = _dig(first, "u2", "rows", "items")
    out = []
    for row in rows if isinstance(rows, list) else []:
        value, title = row.get("value"), _dig(row, "presentation", "u2")
        if isinstance(value, dict) and not (isinstance(title, list) and len(title) > 1):
            out.append((value.get("kind"), value.get("value")))
    return out


def field_text(it, value):
    """Текст значения данных в поле ввода и поле выбора, как его показала платформа (e230, T162–T163), либо `None` — не рисуется.
    Строка, число и дата (текстом) — как есть; Булево — «Да»; поле выбора показывает значение, только когда оно есть в списке выбора (без списка поле пусто — снято
    при «Ввод текста» включённом и пустом списке); прочие сочетания не снимались и не рисуются."""
    if not value:
        return None
    text = value_text(value) or (FIELD_VALUE_BOOL.get(value[1]) if value[0] == "bool" else None)
    if text and it.type == "ComboBox":
        if value[0] != "text" or ("S", text) not in _combo_list_values(it):
            return None
    return text


LABEL_TEXT_ROOM = 19     # надпись с картинкой «Автоматический размер»: ширина картинки не больше ширины надписи минус 19 (надпись 34 px — картинка 16 сжата до 15; надпись 66 px — картинка 32 остаётся 32)
LABEL_PICTURE_GAP = 0    # подпись надписи начинается сразу правее картинки (см. `docs/layout.md`, «Картинки: закладка, надпись, поле картинки, форма, панель»)


def label_bitmap(it):
    """Картинка надписи (`content/u1/pictures/picture`, файл или конфигурация) — `Bitmap` либо `None`."""
    return picture_bitmap.data_uri(_dig(it.node, "content", "u1", "pictures", "picture"))


def label_picture(it, x, y, w, h):
    """`(разметка картинки, левый край подписи, правый край подписи)` надписи с картинкой, либо `None`, если картинки нет или она не читается.
    «Автоматический размер» (`AutoSize`, снято у двух надписей): картинка сжимается до рамки надписи — высота не больше высоты, ширина не больше ширины − 19, вся картинка
    растягивается в этот прямоугольник со сглаживанием, по вертикали по центру; «Реальный размер» — свой размер, обрезанный рамкой надписи. «Слева» (умолчание) — картинка у левого края,
    подпись правее; «Справа» — у правого края, подпись левее; «По центру» — картинка по центру надписи, подпись на всю ширину поверх неё (снято у надписей с картинкой 16 и 32 px)."""
    bitmap = label_bitmap(it)
    if not bitmap:
        return None
    iw, ih = picture_bitmap.size_of(bitmap)
    auto = _dig(it.node, "content", "u1", "picture_size") == "AutoSize"
    dw, dh = (min(iw, max(w - LABEL_TEXT_ROOM, 0)), min(ih, h)) if auto else (iw, ih)
    top = y + (h - dh) // 2
    clip = None if auto else (x, y, w, h)
    where = _dig(it.node, "content", "u1", "picture_location")
    if where == "Right":
        at = x + w - dw
        return picture_bitmap.scaled_at(at, top, dw, dh, bitmap, "area", "icon label-bitmap", clip=clip), x, at - LABEL_PICTURE_GAP
    if where == "Center":
        at = x + (w - dw) // 2          # по центру надписи; подпись остаётся на всей ширине и ложится поверх картинки (снято: «H PNG32a» целиком, буквы поверх синего значка)
        return picture_bitmap.scaled_at(at, top, dw, dh, bitmap, "area", "icon label-bitmap", clip=clip), x, x + w
    return picture_bitmap.scaled_at(x, top, dw, dh, bitmap, "area", "icon label-bitmap", clip=clip), x + dw + LABEL_PICTURE_GAP, x + w


def _label(doc, it, x, y, w, h, data_bound=False, value=None):
    text = _clean(_caption(it.node))
    if data_bound and value_text(value):
        text = _clean(value_text(value))          # значение данных, которое код ставит при открытии: на экране оно, а не заголовок из файла (снимок e230)
    elif data_bound:
        return []           # значения нет: на экране текст данных (пусто), а не заголовок из файла — ни заглушка «НадписьN», ни настоящий заголовок (снимок e239, форма 15 «Статус»); рамка без текста
    # Выравнивание надписи берётся из карты (`content/u1/horizontal_align`): `Right` и `Center` отсчитываются от
    # правого края и середины box, остальное (`Left`, `Auto`; у текста — слева) — от левого края. С кадром по
    # пикселям это не сверялось. Подпись шире надписи усекается с «…» по ширине из `textmeasure`; у
    # переключателя, кнопки и заголовка рамки усечение с кадра не снято, и они рисуются целиком.
    align = _dig(it.node, "content", "u1", "horizontal_align")
    # Ширина и вид текста определяются действующим шрифтом надписи (проверены 10 pt жирный, 8 pt жирный и 10 pt
    # обычный).
    font = _font_of(doc, it)
    pic = label_picture(it, x, y, w, h)
    lead = [pic[0]] if pic else []
    if pic:
        x, w = pic[1], pic[2] - pic[1]            # подпись занимает остаток правее (левее) картинки
    lines = _label_lines(it, w, h, font, text)
    if lines is not None:  # высота вмещает несколько строк: перенос по словам, строки сверху вниз
        pitch = _line_pitch(font)
        at = {"Right": (x + w - 2, "end"), "Center": (x + w / 2, "middle")}.get(align, (x, "start"))
        paint = _color_of(it.node)[0]
        return lead + [_text(at[0], y + pitch * (k + 1), line, at[1], font, paint) for k, line in enumerate(lines)]
    caption = textmeasure.fit(text, w, font)[0]  # не влезает — «Ном…»
    paint = _color_of(it.node)[0]
    base = y + h - 5 if not pic else y + (h - BUTTON_CAP) // 2 + BUTTON_CAP        # надпись с картинкой: по вертикали по центру (снято при высоте 15 и 22; без картинки — прежняя линия h − 5)
    if align == "Right":
        return lead + [_text(x + w - 2, base, caption, "end", font, paint)]
    if align == "Center":
        return lead + [_text(x + w / 2, base, caption, "middle", font, paint)]
    return lead + [_text(x, base, caption, font=font, fill=paint)]


# Кнопки поля ввода — флаги карты (`content/u2/u0` у поля ввода, `content/u1` у поля выбора; флага `choice_list_button` у поля выбора нет). На экране слева направо они идут в порядке
# позиций флагов — список (6), выбор (7), очистка (8), регулирование (9), открытие (10); `FIELD_BUTTONS` перечисляет их справа налево. ▾ поля выбора — левее всех и у поля
# выбора всегда (и с пустым списком). Кнопка выбора — «…»; у поля даты — календарь, у числа — калькулятор, у составного типа с `choose_type` — «T» (на месте «…», «…» тогда нет;
# без флага выбора кнопки нет совсем). Каждая кнопка — 15 px, высотой 17 px у верха поля, с градиентом: `field_glyphs` (всё снято по экрану, опыт на 25 полях).
FIELD_BUTTONS = ("open_button", "spin_button", "clear_button", "choice_button", "choice_list_button")
# имена кнопок, ширина и значок которых не сняты по экрану (их называет заметка `render`): сняты все
FIELD_BUTTON_NAMES = {}


def _field_flags(it):
    """Какие кнопки поля ввода или поля выбора включены: `[имя флага]` справа налево."""
    block = _dig(it.node, "content", "u2", "u0") if it.type == "TextBox" else _dig(it.node, "content", "u1")
    return [name for name in FIELD_BUTTONS if _dig(block, name) is True]


# Поле выбора (`ComboBox`): ▾ — кнопка раскрытия списка.
COMBO_ARROW = "combo_list"


def _combo_has_list(it):
    """У поля выбора непустой список выбора (`choice_list/…/rows`). На рисунок кнопки не влияет: ▾ стоит у поля выбора всегда."""
    lists = _dig(it.node, "content", "u1", "choice_list")
    first = lists[0] if isinstance(lists, list) and lists else None
    rows = _dig(first, "u2", "rows", "count")
    return isinstance(rows, int) and not isinstance(rows, bool) and rows > 0


def _attribute_blocks(doc, it):
    """Блоки типа реквизита формы, к которому поле привязано одним шагом (`path/steps`), если у реквизита один блок простого типа (`S`, `N`, `D`); иначе `None`.
    Основной реквизит формы (объект) не берётся. Поле, привязанное к реквизиту формы, показывает его тип, а не тот, что записан в самом поле (снимок e239: поле с описателем
    «Строка» у реквизита-даты — маска даты и календарь)."""
    from ..edit import datapath
    from ..edit.names import ATTR_HEAD, ATTR_PATTERN, BIND_ELEMENT, BIND_PATH, PATH_STEPS, PATTERN_TYPES, STEP_VALUE
    try:
        attributes, rows = datapath._attributes(doc)
        bindings = [row for row in datapath.binding_rows(attributes) if isinstance(row, dict)]
    except edit.EditError:
        return None
    mine = next((row for row in bindings if row.get(BIND_ELEMENT) == it.index), None)
    steps = (mine.get(BIND_PATH) or {}).get(PATH_STEPS) if mine else None
    if not isinstance(steps, list) or len(steps) != 1 or not isinstance(steps[0], dict):
        return None
    first = steps[0].get(STEP_VALUE)
    head = attributes.get(ATTR_HEAD)
    if isinstance(head, dict) and first == head.get(datapath.MAIN_ATTRIBUTE_ID):
        return None
    found = [row for row in rows if datapath._id_of(row) == first]
    pattern = found[0].get(ATTR_PATTERN) if len(found) == 1 else None
    blocks = pattern.get(PATTERN_TYPES) if isinstance(pattern, dict) else None
    if isinstance(blocks, list) and len(blocks) == 1 and isinstance(blocks[0], dict) and blocks[0].get(PATTERN_KIND) in datatype.FORM_LETTER_CLASS:
        return blocks
    return None


def _field_class(it, doc=None):
    """Класс типа поля ввода (`dateTime`, `decimal`, …) либо `None`; с `doc` — по реквизиту формы, к которому поле привязано (`_attribute_blocks`), иначе по описателю самого поля."""
    if it.type != "TextBox":
        return None
    blocks = _attribute_blocks(doc, it) if doc is not None else None
    if blocks:
        return datatype.FORM_LETTER_CLASS[blocks[0].get(PATTERN_KIND)]
    return datatype.content_class(_dig(it.node, "content"))


def _date_fractions(doc, it):
    """Состав даты поля типа «дата» буквой описателя: `None` — «дата и время» (у этого состава буквы нет), `"D"` — дата, `"T"` — время; тип поля не «дата» — `False`."""
    from ..edit import cowrites
    from ..edit.names import PATTERN_TYPES, TEXTBOX_PATTERN
    blocks = _attribute_blocks(doc, it)
    if not blocks:
        pattern = _dig(it.node, "content", TEXTBOX_PATTERN)
        blocks = pattern.get(PATTERN_TYPES) if isinstance(pattern, dict) else None
    if not (isinstance(blocks, list) and len(blocks) == 1 and isinstance(blocks[0], dict) and blocks[0].get(PATTERN_KIND) == "D"):
        return False
    return blocks[0].get(cowrites.PATTERN_DATE)


# Маска пустого значения поля даты (снимки e239, формы 03, 06–08, 10–12, 14: шрифт 8 pt, знаки по 3 px): «дата» — `__.__.____` пробелами и точками, «дата и время» — с временем `__:__:__`.
# Пробелы и точки стоят там же, где у текста поля (левый отступ `FIELD_TEXT_X`, основание строки то же), чернила точки — на 1 px правее начала знака. Время (`T`) без даты не снималось — маски нет.
DATE_MASK = {"D": "  .  .", None: "  .  .       :  :"}
DATE_MASK_NOTE = "у поля даты без маски пустого значения (недоступное поле, вид «как в 8.2», «Время» без даты) маска не нарисована: в предприятии она там не снималась"


def _date_mask(doc, it, x, y, h, font, color):
    """Знаки маски пустого значения поля «дата» (по одному `<text>` на точку или двоеточие, чтобы место знака не зависело от растеризатора); `[]` — не рисуется."""
    fractions = _date_fractions(doc, it)
    if fractions is False or fractions not in DATE_MASK:
        return []
    mask = DATE_MASK[fractions]
    base = y + min(h, field_glyphs.BOX_H) - 5
    return [_text(x + FIELD_TEXT_X + textwidth.measure(mask[:k], font).px, base, ch, "start", font, color).replace("<text ", "<text class='date-mask' ", 1)
            for k, ch in enumerate(mask) if not ch.isspace()]


def _own_choice_picture(it):
    """Картинка кнопки выбора из файла (`choice_button_picture`, источник 3) — `data:`-адрес либо `None`."""
    return picture_bitmap.data_uri(_dig(it.node, "content", "u2", "u0", "choice_button_picture"))


def field_button_chain(it, kind=None):
    """Кнопки поля справа налево: `[(имя, значок)]`, значок — `lupa`, `cross`, `dots`, `calendar`, `calc`, `type`, `picture`, `drop`, `spin`. `kind` — класс типа, если он известен
    по реквизиту формы (`_field_class(it, doc)`); без него — по описателю самого поля."""
    chain = []
    for name in _field_flags(it):
        if name == "choice_button":
            kind = kind or _field_class(it)
            if _own_choice_picture(it):
                icon = "picture"
            elif kind == "composite" and _dig(it.node, "content", "choose_type") is True:
                icon = "type"
            else:
                icon = {"dateTime": "calendar", "decimal": "calc"}.get(kind, "dots")
        else:
            icon = {"open_button": "lupa", "clear_button": "cross", "spin_button": "spin", "choice_list_button": "drop"}[name]
        chain.append((name, icon))
    if it.type == "ComboBox":
        chain.append((COMBO_ARROW, "drop"))
    return chain


def _field_view(it):
    """Вид поля ввода: `82` (позиция 16 общего блока — `As82`), `83` (`As83`, `As83Alt`) либо `None` — у поля выбора и у формы, где позиция безымянна (вид не проверялся)."""
    if it.type != "TextBox":
        return None
    view = _dig(it.node, "content", "u2", "u0", "u0", "view")
    return 82 if view == "As82" else 83 if view in ("As83", "As83Alt") else None


FIELD_TEXT_X = 3        # левый отступ текста значения в поле ввода: по снимку e230 между рамкой и стойкой «П» 3 пустых px, основание текста — строка 13 при высоте 19
FIELD_VALUE_DISABLED = "#848484"      # цвет текста значения в недоступном поле (самый тёмный пиксель снимка e230)


def _text_box(doc, it, x, y, w, h, value=None):
    out = []
    bitmap = _own_choice_picture(it)
    off = _enabled(it.node) is False or not _form_enabled(doc)
    chain = field_button_chain(it, _field_class(it, doc))
    view = _field_view(it)
    flat = view == 82
    tall = bool(chain) and h > field_glyphs.WRAP_MAX
    frame_color = field_glyphs.FLAT_DISABLED_FRAME if flat and off else EDGE
    if frame_color != EDGE:  # недоступное поле 8.2: рамка светлая, на неё ложатся кнопки с чертой цвета рамки
        out.append(f"<rect class='field-frame' x='{_n(x + 0.5)}' y='{_n(y + 0.5)}' width='{max(w - 1, 0)}' height='{max(h - 1, 0)}' fill='none' stroke='{frame_color}'/>")
    inner = field_glyphs.inner_h(h) if chain else field_glyphs.BUTTON_H
    shift = field_glyphs.glyph_shift(h, flat)
    for k, (name, icon) in enumerate(chain):
        left = x + w - 1 - FIELD_BUTTON * (k + 1)  # пиксель черты: у первой x + w − 16, дальше вплотную влево
        out.append(f"<rect class='field-button' data-button='{name}' x='{_n(left + 1)}' y='{_n(y + 1)}' width='{FIELD_BUTTON - 1}' "
                   f"height='{inner}' fill='{field_glyphs.FLAT_FILL if flat else '#f7f3de'}' stroke='none'/>")
        out += field_glyphs.face(left, y, k == 0, FORM_BG, off, h, flat)
        gy = y + 1 + (0 if icon == "spin" else shift)
        if icon == "picture":
            out.append(_icon(left + 1 + (FIELD_BUTTON - 1 - BUTTON_ICON) // 2, gy + (field_glyphs.BUTTON_H - BUTTON_ICON) // 2, bitmap=bitmap))
        else:
            out.append(field_glyphs.glyph(icon, left + 1, gy, off, flat))
    edge = x + w - 1 - FIELD_BUTTON * len(chain) if chain else None
    if tall:
        # поле выше кнопки: кнопка 19 px в рамке у верха, ниже неё фон формы, рамка поля идёт по левому краю полосы кнопки
        last = x + w - 1 - FIELD_BUTTON  # черта правой кнопки: линия низа кнопок кончается перед срезом правого угла
        out.append(f"<rect class='field-below' x='{edge + 1}' y='{y + field_glyphs.BOX_H}' width='{x + w - edge - 1}' height='{h - field_glyphs.BOX_H}' fill='{FORM_BG}' stroke='none'/>")
        out.append(_vline(edge + 0.5, y + field_glyphs.BOX_H - 1, y + h, frame_color))
        out.append(field_glyphs.under_line(edge, last + (16 if flat else 13), y, frame_color))
    if view == 83:
        out += field_glyphs.corners(x, y, w, h, FORM_BG, left=True, right=not chain, bottom_right_at=edge if tall else None)
    text = field_text(it, value)
    if text:
        font = _font_of(doc, it)
        room = (edge if edge is not None else x + w - 1) - (x + FIELD_TEXT_X) - 2          # до кнопок поля либо до правой рамки
        shown = textmeasure.fit(_clean(text), room, font)[0]
        right = _field_class(it, doc) == "decimal"          # число прижато к правому краю поля (снимки e239v2, формы 02, 04, 10, 15)
        base = y + min(h, field_glyphs.BOX_H) - 5
        if right and h > field_glyphs.BOX_H:          # число в поле выше обычного стоит посередине по высоте: цифра 0,716 ppem (снимок e239v2, форма 15, шрифт 22 pt в поле 38 px)
            base = y + 1 + round((h + 0.716 * textwidth.ppem_of((font or {}).get("size") or textwidth.DEFAULT_SIZE)) / 2)
        out.append(_text(x + FIELD_TEXT_X + room if right else x + FIELD_TEXT_X, base, shown, "end" if right else "start", font,
                         FIELD_VALUE_DISABLED if off else _color_of(it.node)[0]).replace("<text ", "<text class='field-value' ", 1))
    elif not off and not flat and it.type == "TextBox" and _field_class(it, doc) == "dateTime":
        out += _date_mask(doc, it, x, y, h, _font_of(doc, it), _color_of(it.node)[0])          # значения нет — маска пустой даты (недоступное поле и вид 8.2 не снимались)
    return out


# Место под подпись кнопки равно ширине минус 4 (кнопки формы — элемент `Button`, высота 23): подпись помещается
# при ширине не меньше «текст + 4», а при «текст + 2» и «текст + 3» усекается («Сформирова…», «О…»). Это единое
# правило для вставки без `box` (`place._caption_pad`) и для усечения при рендере. Кнопки командной панели
# (`CommandBarButton`) не под него подпадают: их ширину определяет платформа (`_bar_buttons`).
BUTTON_CAPTION_PAD = 4


def element_button_picture(node):
    """У кнопки формы есть картинка (блок `content/u1/picture` не пуст)."""
    picture = _dig(node, "content", "u1", "picture")
    return isinstance(picture, dict) and picture.get(edit.buttons.PIC_SOURCE) not in (None, 0)


def _has_picture(it):
    return element_button_picture(it.node)


def _own_bitmap(it):
    """Картинка кнопки формы, вложенная в файл (`data:`-адрес PNG), либо `None`."""
    return picture_bitmap.data_uri(_dig(it.node, "content", "u1", "picture"))


BUTTON_CAP = 9   # высота прописных (11 px): строки чернил от верха прописной до базовой линии
BUTTON_TOP_BASELINE = 11   # `Top`: верх прописных на строке 2 от верхней рамки, базовая линия на 11
BUTTON_BOTTOM_GAP = 2   # `Bottom`: базовая линия последней строки на 2 выше нижней рамки (высота − 2)
BUTTON_CUT_X = 3   # левый отступ усечённой подписи без переноса
BUTTON_PAD = 3   # запас на строку при подсчёте числа строк, умещающихся по высоте


def _button_baselines(it, h, font, lines):
    """Базовые линии строк подписи кнопки от верха кнопки (опыт на экране: кнопки 23, 40 и 60 px, `Top`, `Center`, `Bottom`; одна строка и две с шагом 13).
    `Top` — первая на 11; `Bottom` — последняя на `h − 2`; `Center` (умолчание) — блок чернил (от верха прописных первой до базовой линии последней) по центру,
    лишняя строка при нечётной разности уходит вниз: верх прописных на `(h − чернила) // 2`. Другой размер шрифта не мерили (шаг — `_line_pitch`)."""
    pitch = _line_pitch(font)
    align = _dig(it.node, "content", "u1", "vertical_align")
    if align == "Top":
        first = BUTTON_TOP_BASELINE
    elif align == "Bottom":
        first = h - BUTTON_BOTTOM_GAP - pitch * (lines - 1)
    else:
        first = (h - (pitch * (lines - 1) + BUTTON_CAP)) // 2 + BUTTON_CAP
    return [first + pitch * k for k in range(lines)]


def _button_lines(it, caption, room, h, font):
    """Строки подписи кнопки: перенос по словам, когда в карте включена «Многострочность» (`multi_line`) и высота вмещает больше одной строки; иначе одна."""
    if _dig(it.node, "content", "u1", "multi_line") is True and isinstance(caption, str) and caption.strip():
        count = max((h - 2 * BUTTON_PAD) // _line_pitch(font), 1)
        if count > 1:
            return textmeasure.wrap(caption, room, font, count)
    return None


BUTTON_PICTURE_PAD = 3     # картинка кнопки: левый (при «Справа» — правый) отступ от рамки в px; у картинки 32 px предприятие ставит её на 2 px от рамки (снято у одной кнопки)


def _picture_mark(x, y, bitmap, box=BUTTON_ICON, size=None, clip=None):
    """Картинка кнопки с левым верхним углом (x, y): файл, платформа или конфигурация — в своём размере либо в `size` (пересчёт по площади); без картинки (заглушка) — серый квадрат `box`×`box`."""
    if bitmap:
        w, h = size or picture_bitmap.size_of(bitmap, box)
        return picture_bitmap.scaled_at(x, y, w, h, bitmap, "area", clip=clip)
    return _icon(x, y)


def _button(doc, it, x, y, w, h):
    caption = _caption(it.node)
    font = _font_of(doc, it)  # размер и жирность кнопки
    paint = _color_of(it.node)[0]
    picture = _has_picture(it)
    bitmap = _own_bitmap(it) if picture else None
    iw, ih = picture_bitmap.size_of(bitmap) if bitmap else (BUTTON_ICON, BUTTON_ICON)
    own_w = iw
    mode = _dig(it.node, "content", "u1", "picture_size")
    if picture_bitmap.is_placeholder(bitmap):
        mode = None                                  # серый квадрат стоит в своём размере
    if bitmap and mode == "Stretch":
        ih = max(h - 2, 1)                           # «Растянуть»: по высоте внутрь рамки (на 1 px от верха и низа), ширина своя
    elif bitmap and mode == "Proportionally":
        iw, ih = max(round(own_w * h / ih), 1), h    # «Пропорционально»: вписана в высоту кнопки
    pad = BUTTON_PICTURE_PAD - (1 if iw >= 32 else 0)          # у нарисованной картинки в 32 px отступ 2 (у вписанной в 22 px — 3)
    room = w - BUTTON_CAPTION_PAD - ((pad + iw + BUTTON_PICTURE_GAP) if picture and caption.strip() else 0)
    lines = _button_lines(it, caption, room, h, font)
    if lines is not None and len(lines) > 1:
        base = _button_baselines(it, h, font, len(lines))
        if not picture:
            return [_text(x + w // 2, y + b, line, "middle", font, paint) for line, b in zip(lines, base)]
    cut_text = False
    if isinstance(caption, str):
        caption, cut, _known = textmeasure.fit(caption, room, font, keep_space=picture)  # не влезает — «Сформирова…»; у кнопки с картинкой пробел перед «…» остаётся («Кн …»)
        cut_text = cut and _dig(it.node, "content", "u1", "multi_line") is not True and len(caption) > 2
        if cut and len(caption) <= 1 and _caption(it.node).strip():
            caption = _caption(it.node).strip()[0] + textmeasure.ELLIPSIS  # «ОК» при 17 и 18 — «О…»: хотя бы буква с «…»
    base_y = y + _button_baselines(it, h, font, 1)[0]
    if not picture:
        if cut_text:  # не влезло и не переносится: усечено «…» и прижато влево (чернила от 3–4 px левой рамки)
            return [_text(x + BUTTON_CUT_X, base_y, caption, "start", font, paint)]
        return [_text(x + w // 2, base_y, caption, "middle", font, paint)]
    top = y + (h - ih) // 2
    inner = (x + 1, y + 1, max(w - 2, 0), max(h - 2, 0))      # картинка выше кнопки обрезается её рамкой (снято: значок 32 px на кнопке 22 px — прямоугольник между верхней и нижней линией)
    if not caption.strip():
        return [_picture_mark(x + (w - iw) // 2, top, bitmap, size=(iw, ih), clip=inner)]
    shown = textwidth.measure(caption, font).px
    if _dig(it.node, "content", "u1", "picture_location") == "Right":
        at = x + w - pad - iw                              # картинка у правого края, подпись по центру места слева от неё
        # усечённая подпись прижата влево (чернила на 3 px от рамки, на 1 px левее, чем у кнопки без картинки); целая — по центру места слева от картинки (центровка не сверена)
        text_x = x + BUTTON_CUT_X - 1 if cut_text else x + max((at - x - shown) // 2, 0)
        return [_text(text_x, base_y, caption, font=font, fill=paint), _picture_mark(at, top, bitmap, size=(iw, ih), clip=inner)]
    at = x + pad                                            # картинка у левого края, подпись по центру места справа от неё («Кн ICO»: картинка на 3 px от рамки, подпись в остатке)
    area = x + w - (at + iw)
    return [_picture_mark(at, top, bitmap, size=(iw, ih), clip=inner), _text(at + iw + max((area + BUTTON_TEXT_SHIFT - shown) // 2, 0), base_y, caption, font=font, fill=paint)]


# Подпись флажка в платформе начинается на 15 px правее левого края box (квадрат — с x = 8 формы, чернила первой
# буквы — с x = 23 формы; текст начинается от x). Для переключателя (`_radio_button`) так не измеряли, там
# остаётся +20.
CHECK_TEXT_X = 15
# Место под подпись флажка равно ширине минус 16: подпись помещается при ширине не меньше 16 + текст (отступ 15
# плюс 1 px справа). Это единое правило для вставки без `box` (`place`), для генерации (`generate._flag_w`) и
# для усечения при рендере. Для переключателя не проверялось.
CHECK_CAPTION_PAD = 16


CHECK_TEXT_LEFT_X = 1  # заголовок слева от квадрата: подпись начинается у левого края (чернила на 2 px, по снимку предприятия)


def _title_text(x, y, w, h, caption, font, title_left, align, start_right, pad, fill=None):
    """Подпись флажка или переключателя при заголовке справа (`TitleRight`, подпись после значка — `start_right` от левого края) или слева
    (`TitleLeft`, значок у правого края, подпись от левого края): область подписи — между краем и значком; выравнивание `align`
    (`Left`, `Right`, `Center`) ставит текст в области. Слева-слева сверено по снимку предприятия, остальные сочетания — нет."""
    left = x + CHECK_TEXT_LEFT_X if title_left else x + start_right
    right = x + w - pad if title_left else x + w
    base = y + h - 5 if h <= 19 else y + (h + 9) // 2          # вертикально по центру: при высоте 22 основание на 15 px ниже верха (снимок e230), до 19 — как у надписи (h − 5)
    if align == "Right":
        return _text(right - 2, base, caption, "end", font, fill)
    if align == "Center":
        return _text((left + right) / 2, base, caption, "middle", font, fill)
    return _text(left, base, caption, font=font, fill=fill)


def _check_box(doc, it, x, y, w, h, value=None):
    """Флажок: квадрат и подпись. Подпись флажка — `content/u1/u0/caption` (у кнопки — `content/u1/caption`); положение заголовка
    (`title_location`: `TitleRight` — подпись справа от квадрата, `TitleLeft` — квадрат у правого края, подпись слева) и выравнивание
    подписи (`horizontal_align`) — там же, в `content/u1/u0`."""
    block = _dig(it.node, "content", "u1", "u0")
    caption = _first_text(_dig(block, "caption"))
    font = _font_of(doc, it)  # размер и жирность флажка
    if isinstance(caption, str):
        caption = textmeasure.fit(caption, w - CHECK_CAPTION_PAD, font)[0]  # не влезает — «Подроб…»
    left = _dig(block, "title_location") == "TitleLeft"
    off = _enabled(it.node) is False or not _form_enabled(doc)
    square = x + w - 13 if left else x                     # квадрат 13×13: у правого края — x + w − 13 … x + w − 1
    top = y + (h - 13 + 1) // 2                            # на 5 px ниже верха при высоте 22 (снимок предприятия e230); при нечётной разности — округление вверх
    out = [field_glyphs._draw(vg.BOX_OFF if off else vg.BOX, square, top, "check-box")]
    if value == ("bool", True):          # отметка: галочка 7×8 из снимка предприятия
        out.append(field_glyphs._draw(vg.MARK_OFF if off else vg.MARK, square, top, "check-mark"))
    return [*out,
            _title_text(x, y, w, h, caption, font, left, _dig(block, "horizontal_align"), CHECK_TEXT_X, CHECK_CAPTION_PAD,
                        _color_of(it.node)[0])]


# Подпись переключателя, как у флажка, начинается на 15 px правее левого края box (окружность 13×13, чернила первой буквы с x = 24 при круге с x = 8; снимок e230);
# место под подпись — ширина минус 16, как у флажка.
RADIO_TEXT_X = 15
RADIO_CAPTION_PAD = 16


def radio_selected(it, value):
    """Переключатель выбран значением данных: `True`/`False`, либо `None` — сравнить нечем. Число, строка и булево значение сравниваются с «ВыбираемымЗначением» переключателя
    (`selected_value`) того же вида; `("select", флаг)` — выбор переключателя прямо, так просят в `--state`."""
    chosen = _dig(it.node, "content", "selected_value")
    kind, own = (chosen.get("kind"), chosen.get("value")) if isinstance(chosen, dict) else (None, None)
    if value is None:
        return None
    if value[0] == "select":
        return value[1]
    if value[0] == "bool":
        return value[1] == bool(own) if kind == "B" else None
    try:
        if value[0] == "number" and kind == "N":
            return float(value[1]) == float(own)
    except (TypeError, ValueError):
        return None
    return value[1] == own if value[0] == "text" and kind == "S" else None


def _radio_button(doc, it, x, y, w, h, value=None):
    """Переключатель: круг и подпись. Подпись берётся из `content/u2/u0/caption`; положение заголовка (`title_location`) и выравнивание
    читаются, как у флажка: `TitleLeft` — круг у правого края (x + w − 8), подпись слева. Отступ и круг не проверялись (`notes`)."""
    block = _dig(it.node, "content", "u2", "u0")
    caption = _first_text(_dig(block, "caption"))
    left = _dig(block, "title_location") == "TitleLeft"
    off = _enabled(it.node) is False or not _form_enabled(doc)
    circle = x + w - 13 if left else x                     # окружность 13×13 (как квадрат флажка): на 5 px ниже верха при высоте 22
    top = y + (h - 13 + 1) // 2
    out = [field_glyphs._draw(vg.CIRCLE_OFF if off else vg.CIRCLE, circle, top, "radio-circle")]
    if radio_selected(it, value):
        out.append(field_glyphs._draw(vg.DOT_OFF if off else vg.DOT, circle, top, "radio-dot"))
    return [*out,
            _title_text(x, y, w, h, caption, _font_of(doc, it), left, _dig(block, "horizontal_align"), RADIO_TEXT_X, RADIO_CAPTION_PAD,
                        _color_of(it.node)[0])]


# Клетка поля табличного документа: чёрная рамка 64×16 в точке (box + 1, box + 1) — сверху и слева 1 px, справа
# и снизу 3 px; внутри белая линия 1 px и заливка #D6DEEF (сетка и заголовки выключены, выделение «WhenActive»).
# При включённых сетке и заголовках вид не проверялся (об этом пишется в `notes`). Рамка текущей клетки есть на экране ТОЛЬКО у поля, которое получает
# фокус при открытии (элемент, назначенный «активным» на своей странице: `default_control`); у остальных клетки не видно — поле пустое (снимки пяти форм:
# рамка у поля с фокусом, у четырёх прочих её нет). Фокус без назначенного элемента (обход по порядку) не проверялся: клетка не рисуется.
CELL = (1, 1, 64, 16)


def sheet_focused(doc, it):
    """Поле табличного документа активно при открытии: его индекс стоит в `default_control` своего родителя на его странице."""
    holder = it.owner.node if getattr(it, "owner", None) is not None else edit.container(doc)
    block = edit.layout_block(holder, need=False)
    control = block.get(DEFAULT_CONTROL) if isinstance(block, dict) else None
    slot = edit.control_slot(block, it.page or 0)
    return isinstance(control, list) and slot < len(control) and control[slot] == it.index


def _sheet_box(doc, it, x, y, w, h):
    out = []
    content = _dig(it.node, "content")
    cx, cy, cw, ch = x + CELL[0], y + CELL[1], CELL[2], CELL[3]
    if cw + CELL[0] < w and ch + CELL[1] < h and sheet_focused(doc, it):
        out += [f"<rect class='cell' x='{cx}' y='{cy}' width='{cw}' height='{ch}' fill='#000'/>",
                f"<rect x='{cx + 1}' y='{cy + 1}' width='{cw - 4}' height='{ch - 4}' fill='#fff'/>",
                f"<rect x='{cx + 2}' y='{cy + 2}' width='{cw - 6}' height='{ch - 6}' fill='#d6deef'/>"]
    # полосы прокрутки поля — по флагам карты, 16 px внутри рамки
    vertical = _dig(content, "vertical_scroll_bar") is True
    horizontal = _dig(content, "horizontal_scroll_bar") is True
    if vertical:
        out.append(_scroll_bar(x + w - 1 - SCROLL_BAR, y + 1, SCROLL_BAR, h - 2 - (SCROLL_BAR if horizontal else 0)))
    if horizontal:
        out.append(_scroll_bar(x + 1, y + h - 1 - SCROLL_BAR, w - 2 - (SCROLL_BAR if vertical else 0), SCROLL_BAR))
    return out
