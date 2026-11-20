"""Перенос элемента к другому родителю или на другую страницу: `reparent`.

Платформа переносит элемент, не задавая вопросов: имя, индекс, привязка данных, события и оформление остаются, копии не
возникает. Меняются список элементов родителя, страница, координаты (они считаются от нового родителя) и привязки границ.

Что записывает платформа (форма и панель проверены в предприятии):

* индекс элемента и счётчик выдачи индексов не меняются; номер на странице (`page_sequence`) — последний на странице
  назначения, а на странице-источнике пересчитывается; порядок обхода (`tab_order`) — наибольший на странице назначения плюс один
  (у переноса на другую страницу того же родителя номер прежний);
* правило «на себя» (нижняя граница от своей верхней, правая от своей левой) не меняется;
* правило к краю прежнего родителя заменяется правилом к краю нового; смещение — всегда «граница минус край» в
  координатах нового места. У поля ввода правая граница с парой «левый край + пропорция до правого» (поле на форме) при
  переносе в панель становится одним правилом «правый край панели», а при обратном переносе на форму возвращается пара;
  у надписи, чьи границы привязаны к себе, привязки при любых переносах те же.

Всё, что сверх этого, операция не угадывает: правило к соседу через границу родителя, привязки по ручному стилю, края у
элементов других видов — отказ словами; `unverified=True` разрешает оставить вид правил как есть, пересчитав смещения
(не проверялось), а ключ `anchor` записывает привязки заново ролями (как у `move_element`).
"""
import copy

from .base import EditError, container, elements_of, find_element, holder_by_name, name_of, pages_count
from .names import (
    ANCHORS,
    COORDS,
    COUNT,
    TAB_ORDER,
    DEFAULT_CONTROL,
    DEPENDENTS,
    ELEMENTS,
    HEIGHT,
    INDEX,
    ITEMS,
    MANUAL_H,
    MANUAL_V,
    NO_ANCHOR,
    NO_REFERENCE,
    PAGE,
    RULES,
    RULE_OBJECT,
    RULE_OFFSET,
    RULE_SIDE,
    PAGE_SEQUENCE,
    WIDTH,
    X,
    Y,
)

# Положение, в которое платформа вставляет перенесённый элемент, когда его не указали: вставка из буфера ставит его
# в точку (21, 21) родителя (и на форму, и на страницу панели). Размер остаётся прежним.
PASTE_POINT = (21, 21)

# Стороны правила (`anchors.TOP`…): 0 верх, 1 низ, 2 лево, 3 право, 4 центр по вертикали, 5 центр по горизонтали.
TOP, BOTTOM, LEFT, RIGHT, CENTER_V, CENTER_H = range(6)
BORDER_AXIS = ("v", "v", "h", "h")                       # верх, низ, лево, право
SIDE_AXIS = {TOP: "v", BOTTOM: "v", CENTER_V: "v", LEFT: "h", RIGHT: "h", CENTER_H: "h"}
BORDER_WORDS = ("верхняя", "нижняя", "левая", "правая")

# Вид привязок, который платформа ставит сама (без «Ручной привязки») и при переносе пересчитывает по новому родителю:
# у поля ввода на форме правая граница — пара «левый край + пропорция до правого», в панели — одно правило к правому краю.
# Прочие границы поля ввода — «нет» (верх, лево) и «на себя» (низ). Эти два вида проверены в предприятии в обе стороны.
EDGE_PAIR, EDGE_SINGLE = "пара к краям", "правое к краю"
CHECKED_AUTO = {"TextBox": {"форма": EDGE_PAIR, "панель": EDGE_SINGLE}}


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _present(rule):
    """Правило, которое что-то значит: не «нет»."""
    return isinstance(rule, dict) and rule.get(RULE_OBJECT) not in (None, -1) and rule.get(RULE_SIDE) in range(6)


def _border_rules(coords, border):
    anchor = coords.get(ANCHORS[border])
    return [anchor[name] for name in RULES if isinstance(anchor, dict) and _present(anchor.get(name))]


def _kind_word(holder, doc):
    return "форма" if holder is container(doc) else "панель"


def _target(doc, to):
    """`(узел родителя, имя или None, страница)` по параметру `to`; отказ словами."""
    hint = ("`to` — \"form\" (форма, страница 0), {\"form\": true, \"page\": N} или {\"panel\": \"<имя панели>\", "
            "\"page\": N}; страницы считаются с нуля")
    if to == "form":
        return container(doc), None, 0
    if not isinstance(to, dict) or not (set(to) <= {"panel", "form", "page"}) or ("panel" in to) == ("form" in to):
        raise EditError(f"to: {to!r} не понял; {hint}")
    page = to.get("page", 0)
    if not (_is_int(page) or isinstance(page, str)):
        raise EditError(f"to.page — номер страницы с нуля (целое) или её имя (строка), а пришло {page!r}")
    if "form" in to:
        if to["form"] is not True:
            raise EditError(f"to.form — true (форма), а пришло {to['form']!r}; {hint}")
        return container(doc), None, _page_number(container(doc), page, "формы")
    name = to["panel"]
    if not isinstance(name, str):
        raise EditError(f"to.panel — имя панели строкой, а пришло {name!r}; {hint}")
    target = holder_by_name(doc, name)
    if pages_count(target) is None:
        raise EditError(f"элемент {name!r} — {target.get('type')}, а не панель: перенос проверен только на форму и на страницы панели; "
                        "родителем бывают они")
    return target, name, _page_number(target, page, f"панели {name!r}")


def _page_number(target, page, who):
    from .pages import page_number
    return page_number(target, page, who)


def _default_control_words(holder, page, index):
    """Слова отказа, если элемент — «АктивизироватьПоУмолчанию» своей страницы (флаг лежит в списке прежнего родителя)."""
    from .base import control_slot, layout_block
    block = layout_block(holder, need=False)
    control = block.get(DEFAULT_CONTROL) if isinstance(block, dict) else None
    page = control_slot(block, page) if isinstance(page, int) else page
    if isinstance(control, list) and isinstance(page, int) and 0 <= page < len(control) and control[page] == index:
        return (f"элемент — «АктивизироватьПоУмолчанию» своей страницы: флаг лежит в списке прежнего родителя, и что платформа делает с ним при "
                "переносе, не проверялось. Снимите его (`set_property` с `default_control: false`), перенесите элемент и поставьте флаг "
                "заново, если он нужен")
    return None


def _shape(coords, index):
    """Вид правил элемента: `{граница: ("нет" | "себя" | "край" | "сосед", …)}` — только по объекту и стороне, без смещений."""
    out = {}
    for border in range(4):
        out[border] = tuple(sorted(
            ("край", rule[RULE_SIDE]) if rule[RULE_OBJECT] == 0 else
            ("себя", rule[RULE_SIDE]) if rule[RULE_OBJECT] == index else
            ("сосед", rule[RULE_OBJECT], rule[RULE_SIDE]) for rule in _border_rules(coords, border)))
    return out


def _auto_name(shape, coords, kind):
    """Вид, который платформа ставит полю ввода сама, — `EDGE_PAIR`/`EDGE_SINGLE`, либо `None`: привязки иные."""
    if kind != "TextBox" or coords.get(MANUAL_H) or coords.get(MANUAL_V):
        return None
    rest = {0: (), 1: (("себя", TOP),), 2: ()}
    if any(shape[border] != rest[border] for border in rest):
        return None
    if shape[RIGHT] == (("край", LEFT), ("край", RIGHT)):
        return EDGE_PAIR
    if shape[RIGHT] == (("край", RIGHT),):
        return EDGE_SINGLE
    return None


def _edge_position(side, edges):
    right, bottom = edges
    return {TOP: 0, LEFT: 0, BOTTOM: bottom, RIGHT: right, CENTER_V: bottom // 2, CENTER_H: right // 2}[side]


def _rule(target, side, offset):
    return {RULE_OBJECT: target, RULE_SIDE: side, RULE_OFFSET: int(offset)}


def _put_rules(coords, border, rules):
    anchor = coords[ANCHORS[border]]
    chosen = list(rules) + [dict(NO_ANCHOR)] * (2 - len(rules))
    for name, rule in zip(RULES, chosen):
        anchor[name].update(rule)


def _carry(coords, index, box, edges):
    """Правила к краю: смещение заново — «граница минус край нового места»; вид правил не меняется."""
    x, y, x2, y2 = box
    coordinate = (y, y2, x, x2)
    for border in range(4):
        for rule in _border_rules(coords, border):
            if rule[RULE_OBJECT] != 0:
                continue
            if SIDE_AXIS[rule[RULE_SIDE]] != BORDER_AXIS[border]:
                raise EditError(f"{BORDER_WORDS[border]} граница привязана к краю по другой оси (сторона {rule[RULE_SIDE]}): такое правило "
                                "операция не пересчитывает")
            rule[RULE_OFFSET] = coordinate[border] - _edge_position(rule[RULE_SIDE], edges)


def _is_dense(holder, page):
    """Номера порядка обхода элементов страницы идут подряд с единицы: так их держит платформа у почти всех форм."""
    from .elements import _on_page
    numbers = [c.get(TAB_ORDER) for c in _on_page(holder, page)]
    return all(_is_int(n) for n in numbers) and sorted(numbers) == list(range(1, len(numbers) + 1))


def _compact(holder, page):
    """Номера порядка обхода страницы заново подряд с единицы, в прежнем порядке."""
    from .elements import _on_page
    for number, coords in enumerate(sorted(_on_page(holder, page), key=lambda c: c.get(TAB_ORDER) or 0), 1):
        coords[TAB_ORDER] = number


def reparent(doc, name, to, box=None, anchor=None, unverified=False):
    """Элемент к другому родителю — на форму или на страницу панели, либо на другую страницу того же родителя.

    `to`: `"form"`, `{"form": true, "page": N}` или `{"panel": "<имя>", "page": N}`; страницы считаются с нуля. `box` — `(лево,
    верх, ширина, высота)` в пикселях нового родителя; без него размер прежний, а положение — точка вставки платформы (21, 21).

    Имя, индекс (и счётчик выдачи), привязка данных, события и оформление остаются. Элемент уходит из списка прежнего
    родителя в список нового, получает последний номер на странице назначения (на прежней номера пересчитываются);
    порядок обхода — наибольший на странице назначения плюс один (на прежней странице, где номера шли подряд, они снова идут подряд); встречные записи
    прежних и новых правил ведутся.

    Привязки границ — как их переносит платформа (`docs/edit-rules.md`): правила «на себя» остаются; правило к краю прежнего
    родителя становится правилом к краю нового со смещением «граница минус край»; у поля ввода правая граница с парой «левый
    край + пропорция до правого» (на форме) в панели одно правило «правый край», а при обратном переносе возвращается пара.
    Отказ словами: правило к соседу (связь через границу родителя), привязки по ручному стилю или у элементов других видов,
    чьё правило к краю платформа в переносе не показывала, — `unverified=True` оставляет вид правил и пересчитывает смещения;
    `anchor` (роли, как у `move_element`) записывает привязки заново.

    Правила других элементов на переносимый при смене родителя повисают и снимаются в «нет», заметка называет их. Расчёт идёт
    ДО правок: отказ оставляет форму прежней. Отказы: элемент с вложенными; родитель — сам элемент или не панель; страницы нет; элемент
    уже там; он — «АктивизироватьПоУмолчанию» своей страницы.
    """
    from .. import anchors as _anchors, templates as _templates
    from .elements import _on_page, _renumber, _set_anchors
    place = find_element(doc, name)
    node, old_holder = place.element, place.holder
    target, panel_name, page = _target(doc, to)
    if target is node:
        raise EditError(f"элемент {name!r} не может стать родителем самого себя")
    if (node.get(ELEMENTS) or {}).get(ITEMS):
        raise EditError(f"у элемента {name!r} ({node.get('type')}) есть вложенные элементы: вместе с ними операция элемент не переносит "
                        "(платформа переносит и их, но запись вложенных координат не проверялась)")
    pages = pages_count(target)
    if pages is not None and not 0 <= page < pages:
        raise EditError(f"страницы {page} {'у формы' if panel_name is None else f'у панели {panel_name!r}'} нет: страниц {pages} (счёт с нуля)")
    coords = node.get(COORDS)
    index = node.get(INDEX)
    if not isinstance(coords, dict) or not all(_is_int(coords.get(key)) for key in (X, Y, WIDTH, HEIGHT)) or not _is_int(index):
        raise EditError(f"у элемента {name!r} нет разобранного блока координат или индекса (форма правлена руками?): переносить нечего")
    old_page = place.page
    same_holder = target is old_holder
    if same_holder and page == old_page:
        raise EditError(f"элемент {name!r} уже лежит там ({'форма' if panel_name is None else panel_name!r}, страница {page}); "
                        "по месту его двигает `move_element`")
    if box is None:
        size = (coords[WIDTH] - coords[X], coords[HEIGHT] - coords[Y])
        box = (PASTE_POINT[0], PASTE_POINT[1], size[0], size[1])
        placed = f"положение — точка вставки платформы {PASTE_POINT}, размер прежний"
    else:
        if not (isinstance(box, (list, tuple)) and len(box) == 4 and all(_is_int(v) for v in box)):
            raise EditError("box — четыре целых (лево, верх, ширина, высота) в пикселях нового родителя")
        if box[2] <= 0 or box[3] <= 0:
            raise EditError(f"box {tuple(box)}: ширина и высота — положительные")
        placed = "положение по box"
    left, top, width, height = box
    edges_box = (left, top, left + width, top + height)
    flag = _default_control_words(old_holder, old_page, index)
    if flag:
        raise EditError(flag)

    # Расчёт привязок — на копии: отказ оставляет форму прежней.
    new = copy.deepcopy(coords)
    new.update({X: left, Y: top, WIDTH: left + width, HEIGHT: top + height})
    notes = []
    if anchor is not None:
        scratch = _templates.clean_coords(coords)
        scratch.update({X: left, Y: top, WIDTH: left + width, HEIGHT: top + height})
        words = _set_anchors(scratch, index, width, height, anchor, doc, target, page, unverified, name)
        new = scratch
        notes.append(f"привязки записаны заново по `anchor`" + (f": {words}" if words else ""))
    else:
        shape = _shape(coords, index)
        for border in range(4):
            for item in shape[border]:
                if item[0] == "сосед":
                    others = {name_of(e): _anchors._index(e) for e in elements_of(old_holder)}
                    who = next((n for n, i in others.items() if i == item[1]), f"индекс {item[1]}")
                    raise EditError(
                        f"{BORDER_WORDS[border]} граница привязана к элементу {who!r}, соседу по прежнему родителю: после переноса это связь через "
                        "границу родителя (или страницы), и платформа такое правило в переносе не показывала. Задайте привязки заново ключом "
                        "`anchor` (роли, как у `move_element`) либо перенесите соседей вместе")
        has_edge = any(item[0] == "край" for border in range(4) for item in shape[border])
        if has_edge:
            edges = _anchors.file_edges(doc, target, page, unverified)[:2]
            old_auto = _auto_name(shape, coords, node.get("type"))
            checked = CHECKED_AUTO.get(node.get("type"), {})
            if (not same_holder and old_auto is not None and old_auto == checked.get(_kind_word(old_holder, doc))
                    and _kind_word(old_holder, doc) != _kind_word(target, doc)):
                # Вид привязок, который платформа сама пересчитывает при переносе между формой и панелью.
                want = checked[_kind_word(target, doc)]
                if want == EDGE_SINGLE:
                    _put_rules(new, RIGHT, [_rule(0, RIGHT, edges_box[2] - edges[0])])
                    notes.append(f"правая граница: пара к краям формы → одно правило к правому краю панели (смещение {edges_box[2] - edges[0]}); "
                                 "пропорция ушла")
                else:
                    pair = _anchors.form_pair(doc, target, page, edges_box, unverified)[RIGHT]
                    _put_rules(new, RIGHT, pair)
                    notes.append("правая граница: правило к правому краю панели → пара «левый край + пропорция до правого» формы")
            elif same_holder or unverified:
                _carry(new, index, edges_box, edges)
                notes.append("правила к краю пересчитаны на новое место (вид тот же)" if same_holder else
                             "правила к краю пересчитаны на новое место, вид правил оставлен — платформа такой перенос не показывала")
            else:
                border = next(b for b in range(4) if any(i[0] == "край" for i in shape[b]))
                raise EditError(
                    f"{BORDER_WORDS[border]} граница привязана к краю прежнего родителя, и такой вид привязок при переносе "
                    f"«{_kind_word(old_holder, doc)} → {_kind_word(target, doc)}» у элемента вида {node.get('type')} не проверялся "
                    "(проверены правая граница поля ввода без «Ручной привязки» между формой и панелью, перенос на другую страницу "
                    "того же родителя и привязки «на себя»). unverified=True оставит вид правил и пересчитает смещения; "
                    "`anchor` запишет привязки заново ролями")
    if not same_holder:
        # Встречные записи правил на переносимый остались у соседей прежнего родителя: правило соседа теперь называет элемент чужого родителя.
        for key in DEPENDENTS:
            new[key] = []
    new[PAGE] = page
    source_dense = _is_dense(old_holder, old_page)

    neighbours = []
    if not same_holder:
        for other in elements_of(old_holder):
            other_coords = other.get(COORDS) if other is not node else None
            if not isinstance(other_coords, dict):
                continue
            for border, key in enumerate(ANCHORS):
                anchor_block = other_coords.get(key)
                for rule_name in RULES:
                    rule = anchor_block.get(rule_name) if isinstance(anchor_block, dict) else None
                    if isinstance(rule, dict) and rule.get(RULE_OBJECT) == index:
                        neighbours.append((other, border, rule))

    # Правки.
    place.items.pop(place.at)
    old_holder[ELEMENTS][COUNT] = len(place.items)
    _renumber(old_holder)
    if source_dense:
        _compact(old_holder, old_page)
    new[PAGE_SEQUENCE] = len(_on_page(target, page))
    new[TAB_ORDER] = max([c.get(TAB_ORDER) or 0 for c in _on_page(target, page)] + [0]) + 1
    node[COORDS] = new
    items = elements_of(target)
    items.append(node)
    target[ELEMENTS][COUNT] = len(items)
    _renumber(target)
    _anchors.sync(doc, index)
    cut = []
    for other, border, rule in neighbours:
        rule.update(NO_ANCHOR)
        cut.append(f"«{name_of(other)}»/{_anchors.BORDER_WORDS[border]}")
    if cut:
        notes.append(f"родитель сменился — привязки соседей к элементу сняты в «нет» ({len(cut)}: {', '.join(cut)}); при необходимости задайте их заново")
    if same_holder and not notes:
        notes.append("привязки без правил к краю не менялись")
    elif not notes:
        notes.append("привязки не менялись (правила «на себя»)")
    return (f"{'форма' if panel_name is None else panel_name}: элемент {name!r} ({node.get('type')}) перенесён с "
            f"{'формы' if old_holder is container(doc) else repr(name_of(old_holder))} (страница {old_page}), индекс {index} прежний, страница {page}, "
            f"box {tuple(box)} ({placed}); " + "; ".join(notes))
