"""Командная панель с автозаполнением одной операцией: `add_element(template="CommandBar", bar_for=…)`.

Панели таблиц и панели формы ставятся с автозаполнением: стандартные кнопки (Добавить, Изменить, Удалить, Вверх, Вниз, ОК, Записать, Закрыть…)
ставит платформа сама, своими кнопками ставят только свои команды формы. `bar_for` называет назначение панели:

* имя табличного поля — панель таблицы вплотную над ней, как у конструктора (`templates.table_bar_node`, один код с `generate`): горизонтальная,
  автозаполнение, источник действий — таблица; место — x и ширина таблицы, высота 24; привязки — таблицы по горизонтали, к верху;
* `form_top` — верхняя панель формы `ДействияФормы`: автозаполнение, источник действий — форма, кнопки слева; место и высота — нормы вида формы;
* `form_bottom` — нижняя панель формы `ОсновныеДействияФормы` КАК У КОНСТРУКТОРА: без автозаполнения, кнопки файлом со стандартными действиями формы по виду (документ и
  элемент справочника — «ОК», «Записать», «Закрыть»; обработка — «Закрыть»), источник действий — форма, кнопки справа, линия сверху, у нижнего края формы. Панель с
  автозаполнением внизу повторяет верхнюю (у документа тот же набор, у обработки без основного реквизита одна «?»), поэтому внизу автозаполнение не ставится. Вид формы —
  ключ `kind` (`document.item`, `catalog.item`, `processing`) либо по основному реквизиту; у вида без образца конструктора — отказ.

`buttons_alignment` (`Left`, `Center`, `Right`) — выравнивание кнопок панели; умолчание — как у конструктора для места панели. Корпус:
таблица — Left; верхняя панель формы — Left; нижняя — Right.
"""
from .. import layout, place as _place, templates
from . import base as _base
from .base import EditError, holder_by_name
from .names import ACTION_SOURCE, COORDS, ELEMENTS, ITEMS, NAME, NAME_BLOCK, PAGE, WIDTH, HEIGHT, X, Y

TABLE_BAR_H = 24                    # высота панели таблицы: конструктор ставит 24
TABLE_BAR_NAME = "КоманднаяПанель"  # имя панели таблицы у конструктора: `КоманднаяПанель<N>`
FORM_PLACES = {"form_top": ("top", "ДействияФормы"), "form_bottom": ("bottom", "ОсновныеДействияФормы")}
ALIGNMENTS = ("Left", "Center", "Right")
DEFAULT_ALIGNMENT = {"table": "Left", "top": "Left", "bottom": "Right"}
FALLBACK_BAR_H = 25                 # высота панели формы, когда вид формы не определён (норма большинства видов)
NO_SOURCE = 4294967295


def _visible_over(holder_node, page, box, skip=()):
    """Имена видимых элементов родителя на странице, пересекающих `box = (x, y, w, h)`."""
    left, top, width, height = box
    out = []
    for item in holder_node[ELEMENTS][ITEMS]:
        coords = item.get(COORDS) if isinstance(item, dict) else None
        if not isinstance(coords, dict) or coords.get(PAGE) != page or coords.get("visible", True) is False:
            continue
        name = (item.get(NAME_BLOCK) or {}).get(NAME)
        if name in skip:
            continue
        if coords[X] < left + width and left < coords[WIDTH] and coords[Y] < top + height and top < coords[HEIGHT]:
            out.append(name or f"#{item.get('index')}")
    return out


def _free_name(doc, base):
    used = set(_base.element_names(doc))
    number = 1
    while f"{base}{number}" in used:
        number += 1
    return f"{base}{number}"


def _behaviour(doc, table_index):
    """Поведение таблицы по горизонтали при растяжении окна: роль панели над ней (`stretch` либо `left`)."""
    try:
        form = layout.read(doc)
        coef = layout.coefficients(form, hide=False)[table_index]
        behaviour = layout.horizontal_behaviour(coef[2], coef[3])
    except Exception:  # noqa: BLE001 — раскладка формы не читается: как у конструктора
        return "stretch"
    return "left" if behaviour in (layout.STANDS, layout.MOVES) else "stretch"


def _beside_splitter(doc, table_index):
    """Таблица привязана по горизонтали к разделителю (правило её левой или правой границы называет `Splitter`): панель над ней идёт за ней."""
    try:
        form = layout.read(doc)
        item = form.items[table_index]
        return any(rule is not None and getattr(form.items.get(rule.obj), "type", None) == "Splitter"
                   for border in (2, 3) for rule in item.rules[border])
    except Exception:  # noqa: BLE001 — раскладка формы не читается: как у конструктора
        return False


def _table_plan(doc, table_name, name, box, holder, page, anchor):
    place = _base.find_element(doc, table_name)
    table = place.element
    if table.get("type") != "TableBox":
        raise EditError(f"bar_for {table_name!r} — {table.get('type')}: панель с автозаполнением ставится над табличным полем (TableBox), "
                        "для панели формы bar_for — \"form_top\" или \"form_bottom\"")
    index = table.get("index")
    for other in _base.holders(doc):
        for item in (other[1].get(ELEMENTS) or {}).get(ITEMS) or []:
            if isinstance(item, dict) and item.get("type") == "CommandBar" and (item.get(NAME_BLOCK) or {}).get(ACTION_SOURCE) == index:
                have = (item.get(NAME_BLOCK) or {}).get(NAME)
                raise EditError(f"у таблицы {table_name!r} уже есть панель {have!r} (источник действий — таблица); автозаполнение у неё включает "
                                f"set_property element={have!r} name=auto_fill value=true — вторая панель задвоила бы кнопки")
    where = place.path.rsplit("/", 1)[0] if "/" in place.path else None
    if holder is not None and holder != where or (page and page != table[COORDS][PAGE]):
        raise EditError(f"панель таблицы лежит там же, где таблица ({where or 'форма'}, страница {table[COORDS][PAGE]}): holder и page не называйте")
    holder, page = where, table[COORDS][PAGE]
    c = table[COORDS]
    if box is None:
        box = [c[X], c[Y] - TABLE_BAR_H, c[WIDTH] - c[X], TABLE_BAR_H]
        if box[1] < 0:
            raise EditError(f"над таблицей {table_name!r} нет места для панели (верх таблицы {c[Y]}, панели нужно {TABLE_BAR_H}); сдвиньте таблицу вниз "
                            "(move_element) или назовите box")
        busy = _visible_over(holder_by_name(doc, holder), page, box, skip=(table_name,))
        if busy:
            raise EditError(f"над таблицей {table_name!r} место для панели ({tuple(box)}) занято: {', '.join(busy)}; сдвиньте таблицу и соседей "
                            "(move_element) или назовите box")
    if anchor is None:
        # таблица рядом с разделителем: панель повторяет её правила, а не только поведение (как в корпусе: 61 из 77 панелей над таблицей
        # повторяют её горизонтальные правила), иначе при сдвиге разделителя панель остаётся на месте, а таблица уходит
        anchor = {"h": {"as": table_name} if _beside_splitter(doc, index) else _behaviour(doc, index), "v": "top"}
    return name or _free_name(doc, TABLE_BAR_NAME), box, holder, page, anchor, templates.table_bar_node(), table_name


def _form_plan(doc, which, name, box, holder, page, anchor, kind, replace=False):
    place, default_name = FORM_PLACES[which]
    if holder is not None or page:
        raise EditError("панель формы лежит на самой форме, на странице 0: holder и page не называйте")
    form = layout.read(doc)
    words = ""
    for item in (_base.container(doc)[ELEMENTS].get(ITEMS) or []):
        if isinstance(item, dict) and item.get("type") == "CommandBar" and (item.get(NAME_BLOCK) or {}).get(ACTION_SOURCE) == 0:
            have = (item.get(NAME_BLOCK) or {}).get(NAME)
            c = item[COORDS]
            if (c[Y] < 12) == (place == "top") and (place == "top" or c[HEIGHT] >= form.height - 2):
                if replace:
                    from . import elements as _elements
                    lost = _button_words(item) if (item.get("content") or {}).get("u1", {}).get("actions") else ""
                    words = (f"прежняя {'верхняя' if place == 'top' else 'нижняя'} панель {have!r} убрана ({_elements.remove_element(doc, have)})"
                             + (f"; её кнопки ушли вместе с ней: {lost}" if lost else "") + "; ")
                    break
                way = (f"автозаполнение у неё включает set_property element={have!r} name=auto_fill value=true, кнопки слева/справа — name=buttons_alignment"
                       if place == "top" else f"кнопки справа или слева — set_property element={have!r} name=buttons_alignment")
                raise EditError(f"{'верхняя' if place == 'top' else 'нижняя'} панель формы уже есть: {have!r}; {way}")
    replaced, words = words, ""
    refused_kind = _place._norm(doc, kind, f"{place}_bar_x")[1]
    if box is None:
        x, found = _place._norm(doc, kind, f"{place}_bar_x")
        h, _found = _place._norm(doc, kind, f"{place}_bar_height")
        if x is None or h is None:
            x, h, words = 0, FALLBACK_BAR_H, "вид формы не определён (kind), норм панели нет: x 0, высота 25"
        else:
            words = f"x и высота — нормы вида «{found}»"
        top = 0 if place == "top" else form.height - h
        box = [x, top, form.width - x, h]
        busy = _visible_over(holder_by_name(doc, None), 0, box)
        if busy:
            raise EditError(f"место панели формы ({tuple(box)}) занято: {', '.join(busy)}; освободите его (move_element) или назовите box")
    if anchor is None:
        anchor = {"h": "stretch", "v": "top" if place == "top" else "bottom"}
    if place == "bottom":
        node = _bottom_node(doc, kind, refused_kind)
        words += _bottom_kind_words(doc, kind or refused_kind)
    else:
        node = templates.form_bar_node(place)
    return name or default_name, box, None, 0, anchor, node, replaced + words, place


def _bottom_node(doc, kind, found):
    """Нижняя панель конструктора по виду формы (`kind` либо по основному реквизиту); вида нет или образца у него нет — отказ словами."""
    kind = kind or found
    if kind is None:
        raise EditError("вид формы не определён (нет основного реквизита вида формы объекта или обработки): назовите kind — "
                        f"{', '.join(templates.FORM_BOTTOM_KINDS)}; нижняя панель ставится кнопками конструктора этого вида")
    if kind not in templates.FORM_BOTTOM_KINDS:
        raise EditError(f"у вида формы «{kind}» образца нижней панели конструктора нет (есть: {', '.join(templates.FORM_BOTTOM_KINDS)}): "
                        "панель с автозаполнением внизу повторяет верхнюю, поэтому её не ставят; кнопки панели — add_element с шаблоном CommandBar и add_button")
    return templates.form_bottom_bar_node(kind)


def _bottom_kind_words(doc, chosen):
    """Слова у нижней панели, поставленной на форму не того вида: «ОК» и «Записать» — действия объекта формы. Начертание «ОК» от вида формы не зависит: у конструктора «ОК» со
    стандартным действием не жирная ни на форме объекта, ни на форме обработки; жирной бывает только кнопка по умолчанию со своей процедурой."""
    from . import formactions
    if chosen not in ("document.item", "catalog.item"):
        return ""
    have = formactions.form_kind(doc)
    if have == chosen:
        return ""
    where = f"основной реквизит формы — «{have}»" if have else "основного реквизита вида объекта у формы нет"
    return (f"; ВНИМАНИЕ: панель вида «{chosen}», а {where}: «ОК» и «Записать» — действия объекта формы. «ОК» в предприятии не жирная (так и у конструктора: жирной бывает только кнопка "
            "по умолчанию со своей процедурой, у стандартного действия она обычная)")


def _button_words(node):
    """Подписи кнопок-действий узла панели одной строкой."""
    names = []
    for button_set in node["content"]["u1"]["actions"]["button_sets"]:
        for button in button_set.get("buttons") or []:
            if button.get("button_type") != "Separator":
                items = (button.get("text") or {}).get("items") or []
                names.append(f"«{items[0]['text']}»" if items else repr(button.get("name")))
    return ", ".join(names)


def prepare(doc, bar_for, add_args, buttons_alignment):
    """Разбор `bar_for` до записи: `(аргументы add_element, дописать в отчёт, источник действий — таблица или None)`."""
    for key in ("like", "after", "grow", "shrink", "date_mode", "caption", "between"):
        if add_args.get(key) not in (None, False):
            raise EditError(f"bar_for и {key} вместе не бывают: у панели с автозаполнением место и привязки выводятся из назначения")
    if add_args.get("context_menu"):
        raise EditError("bar_for и context_menu вместе не бывают: панель контекстного меню — другая панель")
    if add_args.get("template") not in (None, "CommandBar"):
        raise EditError(f"bar_for — только с template=\"CommandBar\", а пришло {add_args.get('template')!r}")
    if not isinstance(bar_for, str) or not bar_for:
        raise EditError("bar_for — имя табличного поля, \"form_top\" или \"form_bottom\"")
    if buttons_alignment is not None and buttons_alignment not in ALIGNMENTS:
        raise EditError(f"buttons_alignment — {', '.join(ALIGNMENTS)}, а пришло {buttons_alignment!r}")
    args = dict(add_args)
    replace = args.pop("replace", False)
    if replace and bar_for not in FORM_PLACES:
        raise EditError("replace — только у панели формы (bar_for \"form_top\" или \"form_bottom\"): панель таблицы, уже стоящую над таблицей, "
                        "убирают remove_element, и тогда ставят новую")
    if bar_for in FORM_PLACES:
        name, box, holder, page, anchor, node, words, place = _form_plan(doc, bar_for, args["name"], args["box"], args["holder"], args["page"],
                                                                         args["anchor"], args.get("kind"), replace)
        source, kind = None, place
        if place == "top":
            said = (f"панель формы с автозаполнением (источник действий — форма): стандартные кнопки формы ставит платформа сама, своими кнопками ставят только "
                    f"свои команды с обработчиком в модуле; {words}")
        else:
            said = (f"нижняя панель формы как у конструктора (источник действий — форма, без автозаполнения): кнопки файлом со стандартными действиями формы — "
                    f"{_button_words(node)}; панель с автозаполнением внизу повторяет верхнюю; своих команд с обработчиком панель не несёт — «Выполнить» и прочие ставит "
                    f"add_button с procedure; {words}")
    else:
        name, box, holder, page, anchor, node, source = _table_plan(doc, bar_for, args["name"], args["box"], args["holder"], args["page"], args["anchor"])
        kind = "table"
        said = (f"панель таблицы {bar_for!r} с автозаполнением (источник действий — таблица): стандартные кнопки (Добавить, Изменить, Удалить, Вверх, Вниз…) "
                "ставит платформа сама; набор для таблицы значений в предприятии не наблюдался")
    align = buttons_alignment or DEFAULT_ALIGNMENT[kind]
    node["content"]["u1"]["buttons_alignment"] = align
    said += f"; кнопки: {align}"
    args.update(name=name, box=box, holder=holder, page=page, anchor=anchor, template=node)
    args.pop("kind", None)
    return args, said, source
