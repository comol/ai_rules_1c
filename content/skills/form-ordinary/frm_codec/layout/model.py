"""Модель раскладки: константы, правила, элементы, родители и разбор блоков координат формы."""
from .. import anchors, edit, lstring


# Граница элемента: 0 верх, 1 низ, 2 лево, 3 право — порядок привязок блока координат.
BORDERS = ("верхняя", "нижняя", "левая", "правая")
BORDER_KEYS = ("top", "bottom", "left", "right")
AXES = ("ширина", "высота")
AXES_AT = ("ширине", "высоте")  # «при ширине 750»
AXES_OF = ("ширины", "высоты")  # «предел высоты»
# Порядок осей, которым окно приходит к размеру: `wh` — ширина, потом высота; `hw` — высота, потом ширина. Предел второй оси
# считается при фактическом росте первой.
ORDERS = ("wh", "hw")
# Сторона объекта в правиле: 0 верх, 1 низ, 2 лево, 3 право, 4 центр по вертикали, 5 центр по горизонтали, 6 — нет.
# У родителя начало оси не сдвигается (0), дальний край идёт с ним (1), центр — ½.
HOLDER_SIDE = {0: 0.0, 1: 1.0, 2: 0.0, 3: 1.0, 4: 0.5, 5: 0.5}
SIDE_CH = {0: "t", 1: "b", 2: "l", 3: "r", 4: "c4", 5: "c5", 6: "-"}
CENTER_SIDES = (4, 5)

# Отступ, ближе которого раскладка не подпускает элемент к краю клиентской области при сжатии. У элемента, стоящего в проекте
# ближе, берётся его проектный отступ: иначе раскладка перестала бы меняться уже при проектном размере.
MARGIN = 8

# Допуск столкновения: элементы сталкиваются, когда округлённые края пересеклись больше чем на 0,5 px. Правило эмпирическое: у границы к центру и у двух идущих дробных границ оно приближённое.
COLLISION_SLACK = 0.5
# Минимальный размер элемента `(ширина, высота)`: тип не сжимается меньше минимума, и раскладка перестаёт меняться на пределе
# `размер ≥ минимум − MIN_SLACK`. `0` — минимум по оси не проверялся (сжатие до нуля). Типы вне таблицы — до нуля. Кнопка: высота 17,
# ширина по подписи (`BUTTON_MIN_BY_CAPTION`); панель — по виду закладок (`PANEL_MIN`).
# Ширина минимума поля ввода растёт с кнопками справа: 11 px и по 15 px на видимую кнопку (кнопка 14 px и разделитель 1 px; проверено в предприятии:
# четыре поля без кнопок и с одной, двумя, тремя встали на одной ширине 56 = 11 + 15·3, когда до минимума дошло поле с тремя кнопками).
TEXTBOX_BUTTONS = ("choice_list_button", "choice_button", "clear_button", "open_button")
TEXTBOX_BUTTON_WIDTH = 15
MIN_SIZE = {"TextBox": (11, 19), "Label": (15, 15), "Button": (46, 17), "TableBox": (20, 49)}
# Минимум панели `(ширина, высота)` по виду закладок `show_tabs`: «Сверху» и «Снизу» 19×37, «Слева (горизонтально)» 89×19
# (ширина зависит от подписи закладки), «Не отображать» 17×17. Остальные виды закладок не проверялись: сжатие до нуля.
PANEL_MIN = {"Top": (19, 37), "Bottom": (19, 37), "LeftHorizontal": (89, 19), "DontUse": (17, 17)}
# Ширина кнопки при минимуме зависит от подписи. Проверены подписи слово в слово: «ОК» 25, «кнопка» 46, «Кнопка с п» 65,
# «Кнопка с подписью дл» 124, «Кнопка с подписью для проверки» 181, «Очень длинная подпись кнопки для проверки минимума» 298, подпись
# из 70 знаков 404. Формулы нет. Для других подписей расчёт берёт 46, а `relayout` отказывает кнопке, которая сужается
# (`_button_caption_refusal`). Минимум выше проектной ширины (298 и 404 против 200): кнопка, начавшая с проектных 200, не сжимается;
# расчёт берёт проектную ширину (`BUTTON_ABOVE_PROJECT`). При DPI не 96 и шрифте не по умолчанию минимумы типов, кроме поля ввода,
# не проверялись.
BUTTON_MIN_BY_CAPTION = {"ОК": 25, "кнопка": 46, "Кнопка с п": 65, "Кнопка с подписью дл": 124, "Кнопка с подписью для проверки": 181,
                         "Очень длинная подпись кнопки для проверки минимума": 298,
                         "Кнопка с подписью для проверки минимума по длине текста и ещё немного ": 404}
BUTTON_ABOVE_PROJECT = frozenset({"Очень длинная подпись кнопки для проверки минимума",
                                  "Кнопка с подписью для проверки минимума по длине текста и ещё немного "})
BUTTON_LONG = ("Очень длинная подпись кнопки для проверки минимума", 200, 298)  # (подпись, ширина в проекте, минимум при открытии в 910×546)
MIN_WHERE_BUTTON_HEIGHT = "высота проверена у кнопки с подписью «кнопка»; зависимость высоты от подписи не проверялась"
MIN_WHERE = {"Button": "проверено на кнопках с подписями «ОК» (25), «кнопка» (46), «Кнопка с п» (65), «Кнопка с подписью дл» (124), «Кнопка с подписью для "
                       "проверки» (181) и в 50 (298) и 70 знаков (404): минимум зависит от подписи — ширина текста, формулы нет",
             "TableBox": "проверено у таблицы с шапкой в одну строку, без подвала"}
PANEL_WHERE = {"Top": "проверено у панели с закладками «Сверху»", "Bottom": "проверено у панели с закладками «Снизу»",
               "LeftHorizontal": "проверено у панели с закладками «Слева (горизонтально)» при подписи закладки «Страница1»; ширина 89 "
                                 "зависит от подписи — при более длинной она больше, и модель допустит размер, которого платформа не даёт",
               "DontUse": "проверено у панели без закладок"}
MIN_SLACK = 0.5
# Типы, у которых ближний предел 0 проверен: надпись, кнопка, поле ввода — только по ширине и только у элемента формы
# (`Лево` 100 → 0, раскладка перестаёт меняться на 600). У прочих типов, по высоте и внутри панели предел считается по аналогии,
# и `relayout` без `unverified` отказывает на нём словами.
NEAR_MEASURED = frozenset({"Label", "Button", "TextBox"})
# Ближний предел у границы, идущей к центру родителя: проверен у надписи по ширине. У границы-доли предела нет: она стоит на доле
# остановленной раскладки. Предел центра действует и у панели: внутренняя раскладка панели перестаёт меняться на размере
# `ширина панели − 16`, содержимое панели прокручивается.
NEAR_CENTER_MEASURED = frozenset({"Label"})
# Доля, начиная с которой замораживание у границы-доли проверено (k ≈ 0,99); у меньших долей не проверялось.
SHARE_OBSERVED = 0.9
# Элементы, чей проект меньше минимума, а раскладка при сжатии по этой оси не сжимается вовсе: `(тип, ось)`. Проверено у таблицы
# по высоте: проект 46 < 49, раскладка остаётся на проектных значениях, а не уходит «до нуля» и не встаёт на минимум.
FROZEN_BELOW_MIN = frozenset({("TableBox", 1)})
# Полоса прокрутки: раскладка выше окна — ширина клиентской области на 16 меньше, шире окна — высота на 16 меньше.
SCROLL = 16
# Насколько близко к краю окна элемент верхнего уровня (не командная панель) должен подойти, чтобы раскладка, которую держит
# минимум размера, дала полосу прокрутки (`Layout.bar_appears`): `(по ширине, по высоте)`. Полоса есть при расстоянии не больше
# 7 px по ширине и меньше 33 px по высоте.
SCROLL_REACH = (MARGIN, 33)

SIDE_WORDS = {0: "верхнему краю родителя", 1: "нижнему краю родителя", 2: "левому краю родителя",
              3: "правому краю родителя", 4: "центру родителя по вертикали",
              5: "центру родителя по горизонтали"}

EPS = 1e-9


class Rule:
    """Правило привязки: `(объект, сторона, смещение)`; объект 0 — родитель, иначе индекс."""
    __slots__ = ("obj", "side", "off")

    def __init__(self, obj, side, off):
        self.obj, self.side, self.off = obj, side, off

    def text(self, me=None):
        """`F.b-8` (родитель, низ, −8), `S.t+25` (сам), `#12.r+4` — запись отчёта привязок."""
        who = "F" if self.obj == 0 else ("S" if self.obj == me else f"#{self.obj}")
        return f"{who}.{SIDE_CH.get(self.side, self.side)}{self.off:+d}"


class Item:
    """Элемент с блоком координат: края в проекте, четыре привязки, встречные записи. `path` — его адрес в документе уровня 1."""
    __slots__ = ("index", "name", "type", "holder", "page", "box", "visible", "rules",
                 "deps", "manual", "node", "coords", "raw", "path", "owner", "lazy", "stored", "min_note", "caption", "from_area")

    def label(self):
        return f"{self.name}" if self.name else f"#{self.index}"

    def qualified(self):
        """Имя с родителем: `Панель1/ПолеВПанели` — во вложенных бывают одинаковые имена."""
        return self.label() if self.owner is None else f"{self.owner.qualified()}/{self.label()}"


class Holder:
    """Родитель элемента: контейнер формы (ключ 0) или панель (ключ — её индекс). `size` — размер в проекте, `rows` — строки списков
    блока раскладки по сторонам или `None`, если блок не разобран, `inner` — край для предела «к краю» по страницам детей
    `{страница: (право, низ)}` (`anchors.holder_edges` или оценка `_inner`; тогда `inner_note` — «край оценён: …»).
    """
    __slots__ = ("key", "node", "name", "item", "size", "rows", "children", "inner",
                 "inner_note", "block", "area")

    def edge(self, page):
        """Край родителя `(право, низ)` на странице `page` — той, где стоит ребёнок. У панели без рамки проверенного вида закладок это
        область панели (`area`), а не направляющая страницы: предприятие считает правила от видимой области.
        """
        return self.area.get(page) or self.inner[page]


def _items_of(node):
    """Элементы родителя списком; пусто, если списка нет или он не массив (документ правили руками, `validate` называет это отказом)."""
    block = node.get(edit.ELEMENTS) if isinstance(node, dict) else None
    items = block.get(edit.ITEMS) if isinstance(block, dict) else None
    return items if isinstance(items, list) else []


def _int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _pair(a, b):
    """`(элемент, граница)` записи — только из двух целых; иное (испорченное руками) — `None`."""
    return (a, b) if _int(a) and _int(b) else None


def textbox_buttons(node):
    """Сколько кнопок справа у поля ввода видимо: выбор из списка, выбор, очистка, открытие (`TEXTBOX_BUTTONS`); счётчик не считается — не проверялся."""
    try:
        block = node["content"]["u2"]["u0"]
    except (KeyError, TypeError):
        return 0
    return sum(1 for key in TEXTBOX_BUTTONS if isinstance(block, dict) and block.get(key) is True)


def min_size(item):
    """`(ширина, высота)` минимума типа; `0` по оси — минимум не проверялся (сжатие до нуля). Проверены поле ввода, надпись, кнопка
    (ширина по подписи, `BUTTON_MIN_BY_CAPTION`; для иной подписи расчёт берёт 46), таблица и панель по виду закладок (`PANEL_MIN`).
    При DPI не 96 и шрифте не по умолчанию минимумы всех типов, кроме поля ввода, не проверялись (`item.min_note`).
    """
    least = MIN_SIZE.get(item.type, (0, 0))
    if item.type == "TextBox":
        return least[0] + TEXTBOX_BUTTON_WIDTH * textbox_buttons(item.node), least[1]
    if item.min_note:
        return 0, 0
    if item.type == "Panel":
        return PANEL_MIN.get(_panel_tabs(item), (0, 0))
    if item.type == "Button":
        width = BUTTON_MIN_BY_CAPTION.get(item.caption, least[0])
        if item.caption in BUTTON_ABOVE_PROJECT:
            # минимум выше проекта: кнопка, начавшая с проектной ширины, не сжимается совсем; в расчёте минимум — её проектная ширина
            width = min(width, item.box[2] - item.box[0])
        return width, least[1]
    return least


def _caption(element):
    """Подпись кнопки (видимый член списка подписей, `lstring`) или `None`: от неё зависит минимум ширины (`BUTTON_MIN_BY_CAPTION`)."""
    try:
        block = element["content"]["u1"]["caption"]
    except (KeyError, TypeError):
        return None
    return lstring.visible_text(block)


def caption_measured(item):
    """Проверен ли минимум ширины этой кнопки по подписи: не кнопка — всегда да (подпись ни при чём)."""
    return item.type != "Button" or item.caption in BUTTON_MIN_BY_CAPTION


def _panel_tabs(item):
    """Вид закладок панели (`show_tabs`: `Top`, `Bottom`, `LeftHorizontal`, `DontUse`, …) или `None`: он выбирает пару минимума."""
    block = edit.layout_block(item.node, need=False)
    return block.get(edit.SHOW_TABS) if isinstance(block, dict) else None


def _min_note(form_note, element):
    """Почему минимум типов этого элемента не проверялся: слова или `None`. DPI не 96 — у всей формы; шрифт не по умолчанию
    (`source` не `Auto`) — у элемента.
    """
    if form_note:
        return form_note
    try:
        font = element["content"]["u1"]["u0"]["font"]
    except (KeyError, TypeError):
        return None
    if isinstance(font, dict) and font.get("source", "Auto") != "Auto":
        return "шрифт не по умолчанию"
    return None


def _item(element, holder):
    item = Item()
    item.from_area = False
    item.index = element.get(edit.INDEX)
    names = element.get(edit.NAME_BLOCK)
    item.name = names.get(edit.NAME) if isinstance(names, dict) else None
    item.type = element.get("type")
    item.holder = holder
    item.node = element
    coords = element.get(edit.COORDS)
    item.coords = coords
    item.raw = not (_int(item.index) and isinstance(coords, dict) and edit.ANCHORS[0] in coords
                    and all(_int(coords.get(k)) for k in (edit.X, edit.Y, edit.WIDTH, edit.HEIGHT)))
    if item.raw:
        item.page = item.box = item.visible = item.rules = item.deps = item.manual = None
        item.lazy = False
        item.stored = None
        item.min_note = None
        item.caption = None
        return item
    item.page = coords.get(edit.PAGE)
    item.box = (coords[edit.X], coords[edit.Y], coords[edit.WIDTH], coords[edit.HEIGHT])
    item.visible = coords.get("visible", True) is not False
    item.rules = []
    for key in edit.ANCHORS:
        anchor = coords.get(key)
        pair = []
        for rule_name in edit.RULES:
            rule = anchor.get(rule_name) if isinstance(anchor, dict) else None
            pair.append(_rule(rule))
        item.rules.append(tuple(pair))
    item.deps = []
    for key in edit.DEPENDENTS:
        members = coords.get(key)
        if members is None:
            item.deps.append(set())
        elif not isinstance(members, list):
            item.deps.append(None)
        else:
            item.deps.append({pair for pair in (_pair(m.get(edit.DEP_ELEMENT),
                                                      m.get(edit.DEP_SIDE))
                                                for m in members if isinstance(m, dict))
                              if pair is not None})
    item.manual = (coords.get(edit.MANUAL_H) is True, coords.get(edit.MANUAL_V) is True)
    item.min_note = None
    item.caption = _caption(element) if item.type == "Button" else None
    return item


def _rule(rule):
    if not isinstance(rule, dict):
        return None
    obj, side, off = (rule.get(edit.RULE_OBJECT), rule.get(edit.RULE_SIDE),
                      rule.get(edit.RULE_OFFSET))
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (obj, side, off)):
        return None
    if obj == -1 or side == 6:
        return None
    return Rule(obj, side, off)


# ── Списки родителя ──


def _rows(block):
    """Строки четырёх первых списков блока раскладки: `{сторона 0…3: {(элемент, граница)}}`. `None` целиком — блока нет; `None` у
    стороны — списка нет или он не массив. Прежние имена списков — отказ словами (`anchors.side_lists`).
    """
    lists = anchors.side_lists(block)
    if lists is None:
        return None
    out = {}
    for side, rows in enumerate(lists):
        if not isinstance(rows, list):
            out[side] = None
        else:
            out[side] = {pair for pair in (_pair(row.get(anchors.ROW_ELEMENT),
                                                 row.get(anchors.ROW_SIDE))
                                           for row in rows if isinstance(row, dict))
                         if pair is not None}
    return out


def _inner(form, holder):
    """Край родителя для предела «к краю» по страницам детей: `({страница: (право, низ)}, слова | None)`.

    Правило одно с привязками — `anchors.holder_edges`. У формы это клиентская область: размер; при рамке «Одинарная» размер − 2;
    при видимых закладках «Сверху» (DPI 96) область страниц `(W−2, H−20)`; при прочих закладках, рамках и DPI не 96 — отказ, который
    снимает `unverified` (тогда берутся направляющие). У панели — направляющие 3 и 4 страницы, где стоит ребёнок (`Holder.edge`).
    Запасная оценка (`_estimate`) нужна, когда правило края не даёт (нет направляющих у панели, неизвестная рамка формы).
    """
    pages = sorted({child.page for child in holder.children}, key=repr)
    out, refused = {}, []
    for page in pages:
        try:
            right, bottom, _words = anchors.holder_edges(form.doc, holder.node, page)
        except edit.EditError as e:
            why = str(e).split(" — ")[0].split(":")[0]
            if not isinstance(holder.block, dict):
                why += " (блок раскладки панели не разобран)"
            refused.append((page, why))
            continue
        out[page] = (right, bottom)
    if not refused:
        return out, None
    estimate, how = _estimate(holder)
    for page, _why in refused:
        out[page] = estimate
    more = (f" (и так ещё на страницах: {', '.join(str(p) for p, _w in refused[1:])})"
            if len(refused) > 1 else "")
    return out, (f"край оценён: {refused[0][1]}{more} — правило края родителя "
                 f"(`anchors.holder_edges`) его не даёт; взят {how}: "
                 f"{estimate[0]}×{estimate[1]}")


def _estimate(holder):
    """Запасная оценка края: `((право, низ), как оценён)`. У формы — её размер; у панели — самое частое «край ребёнка − смещение» у
    привязок детей к её краю, а где таких нет — размер − 2. Влияет только на пределы «к краю» и замечание «к себе в панели».
    """
    if holder.item is None:
        return holder.size, "размер формы"
    found, how = [], []
    for axis, side, border, word, cut in ((0, 3, 3, "правый", "ширина − 2"),
                                          (1, 1, 1, "нижний", "высота − 2")):
        votes = {}
        for child in holder.children:
            for rule in child.rules[border]:
                if rule is not None and rule.obj == 0 and rule.side == side:
                    edge = (child.stored or child.box)[2 if border == 3 else 3]
                    votes[edge - rule.off] = votes.get(edge - rule.off, 0) + 1
        if votes:
            found.append(max(votes, key=lambda v: (votes[v], v)))
            how.append(f"{word} — по привязкам детей к краю панели")
        else:
            found.append(holder.size[axis] - 2)
            how.append(f"{word} — {cut}: к краю не привязан ни один элемент")
    return tuple(found), "; ".join(how)


def _edge_words(holder):
    """Край родителя словами: `682×60` — один на все страницы, иначе по страницам."""
    values = sorted(set(holder.inner.values()))
    if not values:
        return "— (элементов в раскладке нет)"
    if len(values) == 1:
        return f"{values[0][0]}×{values[0][1]}"
    return ", ".join(f"страница {page} — {w}×{h}" for page, (w, h) in
                     sorted(holder.inner.items(), key=lambda kv: repr(kv[0])))


# ── Живые и мёртвые правила ──

ALIVE, DEAD, UNKNOWN = "живое", "мёртвое", "не проверить"

# Допуск несогласованности `box` с правилами: ровно 1 px (рамка страницы и округление центра дают единицу).
BOX_TOLERANCE = 1


def _num(value):
    return int(value) if value == int(value) else round(value, 1)


_EDGE = (1, 3, 0, 2)  # граница → индекс края в (x, y, x2, y2)
