"""Основа рендера: отступы области страницы и каркас координат, цвета и шрифт, SVG-примитивы (`_text`, `_vline`, полоса прокрутки), перенос подписи, доступность.

Здесь нет ни одного вида элемента: поля, командные панели, таблицы, панели и закладки лежат в соседних модулях и берут отсюда общее."""
import re
from xml.sax.saxutils import escape

from .. import edit, layout, lstring, textgap, textwidth
from . import textmeasure


# Отступ области страницы панели от её левого верхнего пикселя: начало системы координат, в которой записаны
# Лево/Верх вложенных элементов. Вид закладок без строки здесь не проверялся: `absolute` отказывает словами,
# `render` вложенных не рисует и называет панель и вид в `notes` (форма при этом рисуется).
PAGE_AREA_OFFSET = {
    # «Сверху»: рамка 1 px, полоса закладок 18 px и снова рамка 1 px по вертикали; по горизонтали одна рамка. У
    # формы такой же отступ (`FORM_TABS_OFFSET`).
    "Top": (1, 19),
    # «Сверху (с прокруткой)»: рисуется так же, как «Сверху» (при двух коротких страницах прокрутки нет);
    # переполнение полосы закладок не проверялось.
    "TopScrolling": (1, 19),
    # «Снизу»: линия страницы y = 342, полоса закладок 18 px под ней.
    "Bottom": (1, 1),
    # «Слева (горизонтально)»: полоса закладок 71 px шириной (закладки столбиком, по 22 px высотой), линия
    # страницы на +70 от края панели. Ширина полосы снята с подписью «Страница1», зависимость от текста не
    # проверялась.
    "LeftHorizontal": (71, 1),
    # «Не отображать»: ни одной линии панели нет.
    "DontUse": (0, 0),
}
# Фразы для видов закладок с непроверенными особенностями: для каждой панели такого вида с видимыми вложенными
# элементами `render` пишет эту фразу в `notes`.
NESTED_NOTES = {
    "TopScrolling": "закладки, что не помещаются, обрезаются перед кнопками прокрутки (положение полосы после щелчка по кнопке не рисуется)",
    "BottomScrolling": "закладки, что не помещаются, обрезаются перед кнопками прокрутки (положение полосы после щелчка по кнопке не рисуется)",
    "LeftVertical": "вертикальные закладки сжимаются по высоте панели; усечение подписи оценено; у первой и последней закладки, сжатых до букв, предприятие подписи не показывает, рисунок тоже",
    "RightVertical": "вертикальные закладки сжимаются по высоте панели; усечение подписи оценено; у первой и последней закладки, сжатых до букв, предприятие подписи не показывает, рисунок тоже",
    "RightHorizontal": "столбец закладок справа зеркален «Слева»; кнопки ▲▼ при нехватке высоты нарисованы, прокрутка столбца — нет",
    "TopMultiLine": "ряды закладок набраны по порядку страниц и растянуты на ширину панели",
    "TopMultilineTransposition": "ряды набраны по порядку страниц; ряд выбранной закладки — ближний к странице (порядок рядов после щелчков по закладкам зависит от истории и не воспроизводится)",
    "BottomMultiLine": "ряды закладок набраны по порядку страниц и растянуты на ширину панели",
    "BottomMultilineTransposition": "ряды набраны по порядку страниц; ряд выбранной закладки — ближний к странице (порядок рядов после щелчков по закладкам зависит от истории и не воспроизводится)",
    13: "«Прокручиваемые страницы» (код 13): заголовки страниц друг под другом и полоса прокрутки; прокрутка не воспроизводится",
    "LeftHorizontal": "полоса закладок — ширина самой длинной подписи плюс 16 px (проверено у «Страница1» и «Фискальные регистраторы», шрифт "
                      "по умолчанию), высота области выведена, а не снята",
}
# Размер области вложенных элементов зависит от вида закладок (`layout.panel_area`): «Сверху», «Сверху (с прокруткой)» и «Снизу» —
# 682×60 при 684×80 («Сверху» с картинкой у закладки — 682×58), «Слева (горизонтально)» — 612×78 при подписи «Страница1», «Не отображать»
# — 684×80. Панель без рамки с такой областью модель считает от неё; область, которой не проверяли, — по `box` и росту, и расхождение
# выводится фразой «не проверялась» и замечанием «область вложенных» (`layout.nested_area_mismatches`).

# Закладки самой формы: при «Сверху» клиентская область сдвинута на (1, 19); без закладок (ключа нет) и при «Не
# отображать» смещения нет. Отступ добавляется и к командным панелям формы. Остальные виды закладок формы не
# проверялись; у формы с Рамкой отступ клиентской области не проверялся (`render` пишет об этом в `notes`).
FORM_TABS_OFFSET = {None: (0, 0), "DontUse": (0, 0), "Top": (1, 19)}

# Калибровка по снимкам предприятия: допуск по краю — 0 px. Проверена 392 стороны рамок на 17 кадрах, и все они
# совпали с рендером до пикселя, кроме двух известных расхождений модели: у вложенного поля в панели «Слева
# (горизонтально)» линия не найдена, а в панели «Не отображать» правый край смещён на +2 (направляющие панели
# записаны под вид «Сверху», а вложенные элементы предприятие размещает от области своего вида). `CALIBRATED` —
# типы с рамкой, чьи края совпали со снимками. Рамка остальных типов (поле выбора, поле табличного документа,
# панель вне проверенных видов, надпись) со снимком не сверена, и `render` называет такие типы в `notes`.
# `GroupBox` проверен на одном элементе с подписью: группа без подписи и с другим шрифтом не проверялась.
TOLERANCE = 0
CALIBRATED = frozenset({"Button", "GroupBox", "TableBox", "TextBox"})
# Рамка, о которой `notes` не пишет «не сверена»: у надписи в предприятии рамки нет (пунктир показывает только
# место). Рамка панели проверена по линиям страницы только для видов закладок из `PANEL_FRAME_MEASURED`; края
# панели отчёт по краям не ищет.
# Рамка индикатора снята по пикселям (углы и цвет), в таблицу `CALIBRATED` (по кадрам наложения) не входит.
FRAME_NOT_CLAIMED = frozenset({"Label", "ProgressBar"})
PANEL_FRAME_MEASURED = frozenset({"Top", "TopScrolling", "Bottom", "BottomScrolling", "LeftHorizontal", "RightHorizontal", "LeftVertical", "RightVertical",
                                  "TopMultiLine", "TopMultilineTransposition", "BottomMultiLine", "BottomMultilineTransposition", 13})

FONT = "font-family='Tahoma, sans-serif' font-size='11'"
FIELD_BUTTON = 15  # кнопка поля ввода: 15 px с чертой на x + w − 16
SCROLL_BAR = 16  # полоса прокрутки: 16 px внутри рамки
_BAD_XML = re.compile("[^\\u0009\\u000a\\u000d\\u0020-\\ud7ff\\ue000-\\ufffd\\U00010000-\\U0010ffff]")


class Unmeasured(ValueError):
    """Отступ области страницы панели не проверялся: вложенные нарисовать негде. `carrier` — панель словами."""

    def __init__(self, carrier, text):
        super().__init__(text)
        self.carrier = carrier


class Rendered:
    """`items` — `[(Item, (x, y, w, h))]`: нарисованные элементы с рамками в клиентской области (для `preview`)."""
    __slots__ = ("svg", "unknown", "notes", "items", "size")

    def __init__(self, svg, unknown, notes, items=(), size=None):
        self.svg, self.unknown, self.notes = svg, unknown, notes
        self.items, self.size = list(items), size


def _clean(text):
    """Строка без знаков, которых XML 1.0 не допускает (управляющие): подпись из файла правильный SVG не ломает."""
    return _BAD_XML.sub("", text) if isinstance(text, str) else ""


def _first_text(block):
    text = lstring.visible_text(block)
    return _clean(text) if text is not None else ""


def _caption(node):
    try:
        return _first_text(node["content"]["u1"]["caption"])
    except (KeyError, TypeError):
        return ""


def _page_captions(node):
    block = edit.layout_block(node, need=False)
    pages = block.get("pages") if isinstance(block, dict) else None
    items = pages.get("items") if isinstance(pages, dict) else None
    if not isinstance(items, list):
        return []
    return [_first_text(p.get("caption")) if isinstance(p, dict) else "" for p in items]


def _form_tabs(form):
    block = edit.layout_block(edit.container(form.doc), need=False)
    return block.get(edit.SHOW_TABS) if isinstance(block, dict) else None


def _form_offset(form):
    tabs = _form_tabs(form)
    if not isinstance(tabs, (str, type(None))) or tabs not in FORM_TABS_OFFSET:
        raise Unmeasured("форма", f"отступ области страниц формы с закладками {tabs!r} не проверялся — "
                                  "элементы формы нарисовать негде")
    return FORM_TABS_OFFSET[tabs]


def _panel_offset(owner, doc=None, size=None):
    """Отступ области страницы панели от её левого верхнего пикселя. Для видов закладок с линиями страницы (`layout.panel_frame`) — внутри линий (на 1 px от
    рамки), при любой высоте полосы и числе рядов; для прочих — по таблице `PAGE_AREA_OFFSET`; код 13 — (0, 17): заголовок страницы 16 px и линия под ним."""
    tabs = layout._panel_tabs(owner)
    if tabs is None:  # блока раскладки у панели нет: вида закладок нет, а не «закладки None»
        raise Unmeasured(owner.qualified(),
                         f"у панели «{owner.qualified()}» блока раскладки нет (вида закладок не видно) — отступ области "
                         f"страницы не проверялся, вложенные элементы «{owner.qualified()}» нарисовать негде")
    if tabs == 13:
        return (0, 17)
    if doc is not None and size is not None and tabs != "DontUse":
        frame, _why = layout.panel_frame(doc, owner, size)
        if frame is not None:
            return frame[0] + 1, frame[1] + 1
    if not isinstance(tabs, str) or tabs not in PAGE_AREA_OFFSET:
        raise Unmeasured(owner.qualified(),
                         f"отступ области страницы у панели с закладками {tabs!r} не проверялся — "
                         f"вложенные элементы «{owner.qualified()}» нарисовать негде")
    return PAGE_AREA_OFFSET[tabs]


def absolute(form, lay, item):
    """`(x, y, w, h)` элемента в клиентской области формы: box из модели плюс угол каждой панели в цепочке
    вложенности и отступ области страницы по виду её закладок, а в конце — отступ самой формы. Если отступ для
    вида закладок неизвестен, выбрасывается `Unmeasured`."""
    x, y, w, h = lay.measured(item)
    owner = form.holders[item.holder].item
    while owner is not None:
        ox, oy, ow, oh = lay.measured(owner)
        dx, dy = _panel_offset(owner, form.doc, (ow, oh))
        x, y = x + ox + dx, y + oy + dy
        owner = form.holders[owner.holder].item
    dx, dy = _form_offset(form)
    return x + dx, y + dy, w, h


def _dig(node, *keys):
    """Значение по цепочке ключей либо `None`: узел испорченного вида не роняет рендер."""
    for key in keys:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _n(value):
    """Число для SVG: целое — целым, полпикселя — `.5` (рамка в 1 px ложится на пиксели, а не между ними)."""
    if value == int(value):
        return str(int(value))
    return f"{value:.1f}"


_FACE = re.compile(r"[\w .-]{1,40}")


def _font_attrs(font):
    """Атрибуты шрифта подписи по действующему шрифту элемента (`textwidth.element_font`): `font-size` равен ppem
    (`textwidth.ppem_of`: 8 pt — 11, 10 pt — 13), `font-weight='700'` у жирного, `font-style='italic'` у курсивного,
    `text-decoration` — `underline` и/или `line-through` у подчёркнутого и зачёркнутого. Если описания нет (`None`) или
    размер неизвестен, подпись рисуется 11 px обычным шрифтом. Высота строки и базовая линия подписи при ppem ≠ 11
    считаются по той же формуле, что для 11 (`y + h − 5`, у кнопки `− 6`); по вертикали для других размеров это не
    проверялось. Масштаб шрифта (`scale`) не рисуется: его действие на экране не проверялось (`textwidth.measure` это называет)."""
    font = font or {}
    if font.get("size") is None:
        ppem = textwidth.DEFAULT_PPEM
    else:
        ppem = textwidth.ppem_of(font["size"])
    tail = ""
    if font.get("bold"):
        tail += " font-weight='700'"
    if font.get("italic"):
        tail += " font-style='italic'"
    lines = [name for flag, name in (("underline", "underline"), ("strikeout", "line-through")) if font.get(flag)]
    if lines:
        tail += f" text-decoration='{' '.join(lines)}'"
    face = font.get("face")
    if face and face not in textwidth.MEASURED_FACES and _FACE.fullmatch(face):
        return f"font-family='{face}, sans-serif' font-size='{ppem}'{tail}"  # переопределённая гарнитура рисуется своей, а не Tahoma
    return f"font-family='Tahoma, sans-serif' font-size='{ppem}'{tail}"


# Цвет текста по умолчанию — #423100 (тёмно-коричневый: так предприятие рисует подписи, закладки, шапки и кнопки в теме, по которой сверялся рендер);
# у недоступного элемента — #9C8C4A. Явный цвет из файла рисуется как есть.
TEXT_COLOR = "#423100"


def _text(x, y, text, anchor="start", font=None, fill=None, extra=""):
    paint = f" fill='{fill or TEXT_COLOR}'"
    return f"<text x='{_n(x)}' y='{_n(y)}' text-anchor='{anchor}' {_font_attrs(font)}{paint}{extra}>{escape(_clean(text))}</text>"


# Цвет текста подписи. Явный цвет в файле — `color_kind` 0, код — RGB (младший байт — красный: 32768 = 0x008000 — зелёный;
# проверено в предприятии). Вид 3 и 4 с кодом 0 — «автоматический» (цвет темы, `TEXT_COLOR`); вид 3 и 4 с другим кодом — цвет стиля или
# системный, его таблицы нет: подпись рисуется цветом темы, и `render` называет такую подпись в `notes`. Заголовок рамки группы
# предприятие может окрасить по свойству, которого карта не знает (у группы с явной рамкой «Скруглённая» заголовок на экране
# коричневый, а `text_color` в файле автоматический): рендер рисует его цветом темы и говорит об этом в `notes`.
COLOR_BLACK = "#000000"


def _color_record(node, key):
    """Запись цвета `key` (`text_color`, `back_color`) элемента — ближайшая к началу содержимого — либо `None`."""
    found = []

    def walk(block, depth):
        for name, value in block.items():
            if name == "elements" or not isinstance(value, dict):
                continue
            if name == key and "color_kind" in value:
                found.append((depth, value))
            else:
                walk(value, depth + 1)
    content = node.get("content") if isinstance(node, dict) else None
    if isinstance(content, dict):
        walk(content, 0)
    return min(found, key=lambda pair: pair[0])[1] if found else None


def _rgb_of(code):
    """`#rrggbb` по коду цвета файла (младший байт — красный)."""
    return "#%02x%02x%02x" % (code & 255, (code >> 8) & 255, (code >> 16) & 255)


FORM_STYLE_BACK = -1


def _back_of(node):
    """Цвет фона элемента (`ЦветФона`): `(вид, цвет, слова)`. Вид: `auto` — «Авто» (рисует вид элемента сам), `form` — цвет стиля «Фон формы» (вид 3, код −1: цвет фона формы,
    снято в предприятии: у командной панели с таким фоном заливки нет), `rgb` — явный цвет (`цвет` — `#rrggbb`), `other` — цвет стиля или системный, которого таблицы нет: рисуется как «Авто», слова называют его."""
    record = _color_record(node, "back_color")
    if record is None:
        return "auto", None, None
    kind, code = record.get("color_kind"), (record.get("value") or {}).get("code")
    if kind == 0 and isinstance(code, int):
        return "rgb", _rgb_of(code), None
    if kind in (3, 4) and code == 0:
        return "auto", None, None
    if kind == 3 and code == FORM_STYLE_BACK:
        return "form", None, None
    return "other", None, f"вид цвета {kind}, код {code}"


def _color_of(node):
    """`(цвет, слова)`: `#rrggbb` либо `None` (автоматический), и пояснение, если цвет задан стилем или системой."""
    record = _color_record(node, "text_color")
    if record is None:
        return None, None
    kind, code = record.get("color_kind"), (record.get("value") or {}).get("code")
    if kind == 0 and isinstance(code, int):
        return _rgb_of(code), None
    if kind in (3, 4) and code == 0:
        return None, None
    return None, f"вид цвета {kind}, код {code}"


def _font_of(doc, it):
    """Действующий шрифт подписи элемента (`textwidth.element_font`: шрифт элемента, `Auto` — шрифт формы, иначе
    умолчание 8 pt)."""
    return textwidth.element_font(it.node, doc)


# Недоступный элемент: в файле свойство «Доступность» снято (`enabled` ложно). Предприятие рисует его текст и значки серым, а фон поля
# ввода — цветом формы. Цвет текста недоступного — #9C8C4A; квадрат флажка и круг переключателя — карты снимка (`value_glyphs_data`); текст значения поля — #848484. Доступность, которую задаёт код, рендер без записей разбора кода не знает; с ними безусловную `Ложь` рисует серой.
# Фон формы — #FFFFEF: клиентская область и фон недоступного поля ввода (проверено по пикселям в предприятии).
FORM_BG = "#ffffef"
DISABLED_TEXT, DISABLED_FIELD = "#9c8c4a", FORM_BG
# Картинка недоступной кнопки панели: платформа сводит цвет каждого канала к `0,24·цвет + 146` (белый становится #D0D2D0, тёмное светлеет, оттенок остаётся), прозрачность прежняя.
# Снимки T280 (форма D0: «Найти в списке», «Перечитать», «Отмена проведения» недоступны): средняя ошибка по трём картинкам 2,8 из 255 на канал при шаге 16-битного цвета 4–8;
# пиксель в пиксель совпала треть точек — точное правило платформы неизвестно.
OFF_FILTER_ID = "icon-off"
OFF_FILTER = (f"<defs><filter id='{OFF_FILTER_ID}' color-interpolation-filters='sRGB' x='0' y='0' width='100%' height='100%'><feComponentTransfer>"
              "<feFuncR type='linear' slope='0.24' intercept='0.5725'/><feFuncG type='linear' slope='0.24' intercept='0.5725'/>"
              "<feFuncB type='linear' slope='0.24' intercept='0.5725'/></feComponentTransfer></filter></defs>")
DISABLED_NOTE = ("недоступные элементы (Доступность снята в файле у элемента или у формы) нарисованы серым (текст #9C8C4A, значения полей #848484, квадрат флажка и круг переключателя — по снимку); "
                 "доступность, которую задаёт код, рендер без записей разбора кода (`--code-notes`) не рисует, а с ними рисует серой безусловную `Ложь`; элементы внутри недоступных групп и страниц не серые "
                 "(наследование не проверялось)")
_NOT_OWN = frozenset({"control", "actions", "pages", "elements", "columns"})


def _enabled(node):
    """Значение «Доступность» элемента по файлу (`enabled`): `False` — снята. Берётся ближайшая к узлу запись, списки действий,
    страниц и колонок и вложенные элементы не просматриваются (у кнопок панели своя запись — `_file_entries`)."""
    found = []

    def walk(block, depth):
        if not isinstance(block, dict):
            return
        for name, value in block.items():
            if name in _NOT_OWN or isinstance(value, list):
                continue
            if name == "enabled" and isinstance(value, bool):
                found.append((depth, value))
            else:
                walk(value, depth + 1)
    walk(node.get("content") if isinstance(node, dict) else None, 0)
    return min(found, key=lambda pair: pair[0])[1] if found else True


def _form_enabled(doc):
    """«Доступность» самой формы (`form…layout.enabled`): снята — в предприятии все элементы серые, ввести нельзя."""
    return _dig(doc, "form", "container", "layout_holder", "layout_list", "layout", "enabled") is not False


_TEXT_TAG = re.compile(r"<text\b[^>]*>")


def _grey(parts, color=None):
    """Строки SVG недоступного элемента: подписи — серым (цвет из файла платформа у недоступного не показывает); значения полей уже серые. `color` — другой серый (кнопка без действия)."""
    def paint(match):
        if "class='field-value'" in match.group(0):
            return match.group(0)           # значение поля недоступного поля уже серое (#848484, снимок), не цвет подписи
        tag = re.sub(r" fill='[^']*'", "", match.group(0))
        return tag[:-1] + f" fill='{color or DISABLED_TEXT}'>"
    return [_TEXT_TAG.sub(paint, part) for part in parts]


def _vline(x, y1, y2, color="#999"):
    return f"<line x1='{_n(x)}' y1='{_n(y1)}' x2='{_n(x)}' y2='{_n(y2)}' stroke='{color}'/>"


def _line_pitch(font):
    """Шаг строк многострочной надписи: ppem шрифта + 2 (13 px при 8 pt: по снимку предприятия основания двух строк стоят в 13 px друг от друга)."""
    size = (font or {}).get("size")
    return max(textwidth.ppem_of(size if isinstance(size, (int, float)) and size > 0 else textwidth.DEFAULT_SIZE) + 2, 1)   # размер ≤ 0 — как у шрифта по умолчанию


def _label_lines(it, w, h, font, text=None):
    """Строки надписи, переносящей текст по словам (`textgap.wraps`: высота вмещает больше одной строки), либо `None` — надпись в одну
    строку. Число строк — высота, делённая на шаг строк; не поместившееся в последнюю строку усекается с «…». Первая строка стоит у
    верхнего края надписи (вертикальное выравнивание сверху; другие значения карты не читаются). `text` — текст вместо подписи из файла (значение данных надписи)."""
    if not textgap.wraps((0, 0, w, h), font):
        return None
    text = _clean(_caption(it.node)) if text is None else text
    if not text:
        return None
    return textmeasure.wrap(text, w, font, max(2, h // _line_pitch(font)))


# Полоса прокрутки (проверено на трёх формах): 16 px, линия #B5B184 со стороны поля, на концах кнопки со стрелкой — вертикальная 20 px по высоте, горизонтальная 21 px
# по ширине (заливка #F7F7E7, граница #B5B184), между ними бегунок-дорожка с градиентом поперёк полосы (#F7F7E7 → #F7EBCE → #E7DEB5). Стрелка: треугольник 7×4,
# светло-серая у кнопки, дальше которой прокручивать нельзя (начало), тёмно-серая у другой. Длину бегунка рендер не знает (зависит от данных): дорожка залита целиком,
# граница бегунка не рисуется. Размеры кнопок и цвета проверены на двух формах; бегунок с данными и кнопки прокрутки в других состояниях не проверялись.
SCROLL_BUTTON_V, SCROLL_BUTTON_H = 20, 21
SCROLL_LIGHT, SCROLL_DARK = "#c8c8b8", "#6e6e6e"


def _scroll_arrow(cx, cy, direction, color):
    """Треугольник 7×4 (вершиной вверх, вниз, влево или вправо) с центром в (cx, cy)."""
    pts = {"up": ((cx - 3.5, cy + 2), (cx + 3.5, cy + 2), (cx, cy - 2)), "down": ((cx - 3.5, cy - 2), (cx + 3.5, cy - 2), (cx, cy + 2)),
           "left": ((cx + 2, cy - 3.5), (cx + 2, cy + 3.5), (cx - 2, cy)), "right": ((cx - 2, cy - 3.5), (cx - 2, cy + 3.5), (cx + 2, cy))}[direction]
    return f"<path class='scroll-arrow' d='M{_n(pts[0][0])} {_n(pts[0][1])}L{_n(pts[1][0])} {_n(pts[1][1])}L{_n(pts[2][0])} {_n(pts[2][1])}Z' fill='{color}'/>"


def _scroll_bar(x, y, w, h):
    vertical = h >= w
    gid = f"sb{_n(x)}_{_n(y)}".replace(".", "p")
    grad = (f"<defs><linearGradient id='{gid}' x1='0' y1='0' x2='{1 if vertical else 0}' y2='{0 if vertical else 1}'>"
            "<stop offset='0' stop-color='#f7f7e7'/><stop offset='0.5' stop-color='#f7ebce'/><stop offset='1' stop-color='#e7deb5'/></linearGradient></defs>")
    out = [grad, f"<rect class='scroll-bar' x='{_n(x + 0.5)}' y='{_n(y + 0.5)}' width='{max(w - 1, 0)}' height='{max(h - 1, 0)}' "
                 f"fill='url(#{gid})' stroke='{EDGE}'/>"]
    size = SCROLL_BUTTON_V if vertical else SCROLL_BUTTON_H
    if (h if vertical else w) < 2 * size + 2:
        return "".join(out)                              # полоса короче двух кнопок: только дорожка
    for first in (True, False):
        if vertical:
            by = y if first else y + h - size
            out.append(f"<rect x='{_n(x + 1)}' y='{_n(by + (0 if first else 1))}' width='{max(w - 2, 0)}' height='{size - 1}' fill='#f7f7e7' stroke='none'/>")
            line = by + size - 0.5 if first else by + 0.5
            out.append(f"<line x1='{_n(x)}' y1='{_n(line)}' x2='{_n(x + w)}' y2='{_n(line)}' stroke='{EDGE}'/>")
            out.append(_scroll_arrow(x + w / 2, by + size / 2, "up" if first else "down", SCROLL_LIGHT if first else SCROLL_DARK))
        else:
            bx = x if first else x + w - size
            out.append(f"<rect x='{_n(bx + (0 if first else 1))}' y='{_n(y + 1)}' width='{size - 1}' height='{max(h - 2, 0)}' fill='#f7f7e7' stroke='none'/>")
            line = bx + size - 0.5 if first else bx + 0.5
            out.append(f"<line x1='{_n(line)}' y1='{_n(y)}' x2='{_n(line)}' y2='{_n(y + h)}' stroke='{EDGE}'/>")
            out.append(_scroll_arrow(bx + size / 2, y + h / 2, "left" if first else "right", SCROLL_LIGHT if first else SCROLL_DARK))
    return "".join(out)


NO_FRAME = {"Splitter", "CommandBar", "CheckBox", "RadioButton"}


PICTURE_UNSEEN_NOTE = "поле картинки без картинки и без рамки не нарисовано: в предприятии на его месте пусто (рамку и белое поле оно показывает, только когда задана рамка поля)"


def picture_box_empty(it):
    """Поле картинки без картинки (источник не задан): рамка, если она есть, обводит фон формы — белой заливки внутри нет (снимки e239v2, формы 02 и 04: внутри `#FFFFEF`)."""
    return it.type == "PictureBox" and _dig(it.node, "content", "u1", "pictures", "picture", "source") in (None, 0)


def picture_box_unseen(it):
    """Поле картинки без картинки и без рамки: в предприятии его не видно (снимки e239, формы 02, 04, 10: ни рамки, ни заливки). Рамка рисуется, только когда она задана свойством «Рамка»
    поля (`border_type`, не «Нет рамки»); поле с картинкой, но без рамки, не снималось — рисуется как раньше (белое поле с рамкой на месте картинки)."""
    if it.type != "PictureBox":
        return False
    border = _dig(it.node, "content", "u1", "u0", "border", "border_type")
    source = _dig(it.node, "content", "u1", "pictures", "picture", "source")
    return border in (None, "WithoutBorder") and source in (None, 0)
# Цвет рамок поля ввода, таблицы, группы и страницы панели — #B5B184 (проверено по пикселям у полей восьми форм, у рамки списка и у рамки группы).
EDGE = "#b5b184"
STRIP, LEFT_STRIP, LEFT_TAB, GROUP_TOP = 18, 71, 22, 7  # полоса «Сверху»/«Снизу», «Слева», закладка «Слева», верх рамки группы
