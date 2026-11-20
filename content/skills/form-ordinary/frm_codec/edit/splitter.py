"""Разделитель между двумя элементами: `add_element(template="Splitter", between=[слева, справа])`.

Строение — самое частое в корпусе: разделитель лежит в зазоре между двумя соседями и занимает его целиком,
вдоль разделителя — на протяжении обоих соседей; граница каждого соседа, обращённая к нему, привязана к стороне разделителя
(`anchors.plan`, роль `{"splitter": …}`); сам разделитель по оси движения — роль `slide` (дальняя граница долей между краями
родителя, ближняя от неё, размер держится), по поперечной оси — повторяет соседей (`{"as": <сосед>}`), если они привязаны одинаково.
Что корпус не подтверждает — отказ словами: зазор вне корпусных толщин, соседи не рядом, соседи на разных страницах и разные
поперечные привязки (их выбирает человек: `anchor={"v": …}` / `{"h": …}`).
"""
import copy

from .. import anchors, edit, layout
from ..layout import drag

# Толщина разделителя корпуса — `anchors.SPLITTER_THICKNESS`; здесь только слова.
AXIS_WORDS = {"h": "вертикальный разделитель между левым и правым соседом", "v": "горизонтальный разделитель между верхним и нижним соседом"}


def _find(doc, holder_node, name):
    item = anchors._find_named(doc, holder_node, name, "соседа")
    if anchors._coords(item).get(edit.PAGE) is None:
        raise edit.EditError(f"у соседа {name!r} блок координат не разобран — края взять неоткуда")
    return item


def _box(item):
    c = anchors._coords(item)
    return c[edit.X], c[edit.Y], c[edit.WIDTH], c[edit.HEIGHT]


def _cross_sig(item, axis):
    """Правила поперечной оси соседа без смещений: по границам — набор (объект, сторона); объект — край родителя, сам элемент или индекс."""
    c = anchors._coords(item)
    me = anchors._index(item)
    near, far = (anchors.LEFT, anchors.RIGHT) if axis == "h" else (anchors.TOP, anchors.BOTTOM)
    out = []
    for border in (near, far):
        rules = []
        for rule_name in edit.RULES:
            rule = (c.get(edit.ANCHORS[border]) or {}).get(rule_name)
            if not isinstance(rule, dict):
                continue
            obj, side = rule.get(edit.RULE_OBJECT), rule.get(edit.RULE_SIDE)
            if obj == -1 or side == anchors.NO_SIDE:
                continue
            rules.append(("F" if obj == 0 else "S" if obj == me else obj, side))
        out.append(tuple(rules))
    return tuple(out)


def _other_border_words(item, axis, before):
    """Что делает вторая граница соседа (ту, что к разделителю не привязана): правила словами."""
    c = anchors._coords(item)
    border = {("h", True): anchors.LEFT, ("h", False): anchors.RIGHT, ("v", True): anchors.TOP, ("v", False): anchors.BOTTOM}[(axis, before)]
    rules = [anchors.rule_text(c[edit.ANCHORS[border]][r], anchors._index(item)) for r in edit.RULES
             if c[edit.ANCHORS[border]][r].get(edit.RULE_OBJECT) != -1]
    return "|".join(rules) if rules else "правила нет, граница остаётся на месте"


# Внешняя граница соседа (у левого/верхнего — ближняя к краю родителя, у правого/нижнего — дальняя) при перетаскивании разделителя стоит на месте:
# сосед с ближней стороны растёт, с дальней сжимается. Роль оси, которая этого достигает: левому — `left`/`top` (граница остаётся), правому — `right`/`bottom`
# (граница к краю родителя, как у соседей в формах платформы: правая граница правого соседа — к правому краю формы).
OUTER = {("h", True): (anchors.LEFT, "left"), ("h", False): (anchors.RIGHT, "right"),
         ("v", True): (anchors.TOP, "top"), ("v", False): (anchors.BOTTOM, "bottom")}


def _hold_outer_borders(doc, splitter_name, before, after, axis, holder_node):
    """Если внешняя граница соседа идёт за сдвигом разделителя (по модели перетаскивания), ставит ей роль, держащую её на месте;
    возвращает слова о поставленном."""
    said = []
    for item, is_before in ((before, True), (after, False)):
        border, role = OUTER[(axis, is_before)]
        form = layout.read(doc)
        splitter = drag._splitter(form, splitter_name)
        coef = drag.coefficients(form, splitter).get(anchors._index(item))
        if coef is None or coef[border] == 0:
            continue
        name = edit.name_of(item)
        edit.set_anchors(doc, name, **{axis: role})
        edit.set_anchors(doc, name, **{axis: {"splitter": splitter_name}})
        said.append(f"«{name}»: внешняя граница держится на месте (роль {role}), граница к разделителю — к его стороне")
    return said


# Кто берёт прирост окна по оси разделителя: роль оси движения разделителя. `before` — левый (верхний) сосед растёт, правый (нижний) держит размер:
# разделитель идёт вместе с дальним краем родителя (`right`/`bottom`); `after` — разделитель стоит у ближнего края (`left`/`top`), растёт дальний сосед;
# `both` — прирост делится долей (`slide`, самое частое строение корпуса среди разделителей между табличными полями).
GROWTH_ROLES = {"both": {"h": "slide", "v": "slide"}, "before": {"h": "right", "v": "bottom"}, "after": {"h": "left", "v": "top"}}


def _bars(holder_node, page, item):
    """Панели с автозаполнением соседа (источник действий — он) той же страницы, чьё протяжение вдоль разделителя совпадает с соседом: `[имя]`."""
    me = anchors._index(item)
    c = anchors._coords(item)
    out = []
    for other in holder_node[edit.ELEMENTS][edit.ITEMS]:
        oc = other.get(edit.COORDS) if isinstance(other, dict) else None
        if (isinstance(oc, dict) and other.get("type") == "CommandBar" and oc.get(edit.PAGE) == page
                and (other.get(edit.NAME_BLOCK) or {}).get(edit.ACTION_SOURCE) == me
                and (oc[edit.X], oc[edit.WIDTH]) == (c[edit.X], c[edit.WIDTH])):
            out.append(edit.name_of(other))
    return out


def add_between(doc, between, add_element, *, template, name, holder, page, anchor, unverified, others, takes_growth=None):
    """Разделитель в зазоре между двумя элементами; `add_element` — функция добавления (кольцо импортов). Отказ оставляет форму прежней.

    `others` — названные вызовом параметры, которые с `between` не совмещаются (`box`, `after`, `kind`, `grow`, `shrink`, `like`, `date_mode`,
    `context_menu`): место и привязки разделителя выводятся из соседей.
    """
    if template not in (None, "Splitter"):
        raise edit.EditError(f"between ставит разделитель между двумя элементами; шаблон {template!r} — не разделитель")
    if not (isinstance(between, (list, tuple)) and len(between) == 2 and all(isinstance(n, str) for n in between)) or between[0] == between[1]:
        raise edit.EditError(f"between — два разных имени соседей, [\"слева или сверху\", \"справа или снизу\"], а пришло {between!r}")
    if takes_growth is not None and takes_growth not in GROWTH_ROLES:
        raise edit.EditError(f"takes_growth — кто берёт прирост окна: {', '.join(repr(k) for k in GROWTH_ROLES)}; пришло {takes_growth!r}")
    busy = [key for key, value in others.items() if value]
    if busy:
        raise edit.EditError(f"between называет место разделителя (зазор между соседями), и {', '.join(busy)} вместе с ним не нужны: уберите их")
    if anchor is not None and not (isinstance(anchor, dict) and anchor and set(anchor) <= {"h", "v"}):
        raise edit.EditError(f"у разделителя между соседями привязку задают осями — {{\"h\": …, \"v\": …}} (роли set_anchors) либо не задают: он "
                             f"привязывается по строению корпуса; пришло {anchor!r}")
    holder_node = edit.holder_by_name(doc, holder)
    first, second = (_find(doc, holder_node, n) for n in between)
    for item, n in ((first, between[0]), (second, between[1])):
        if anchors._coords(item).get(edit.PAGE) != page:
            raise edit.EditError(f"сосед {n!r} лежит на странице {anchors._coords(item).get(edit.PAGE)}, а разделитель — на {page}: страницу "
                                 "разделителя называет page")
        if item.get("type") == "Splitter":
            raise edit.EditError(f"сосед {n!r} — сам разделитель: между разделителями разделитель не ставят")
    a, b = _box(first), _box(second)
    axis = None
    for axis_key, (lo, hi), (cross_lo, cross_hi) in (("h", (0, 2), (1, 3)), ("v", (1, 3), (0, 2))):
        for left, right, pair in ((a, b, (first, second)), (b, a, (second, first))):
            overlap = min(left[cross_hi], right[cross_hi]) - max(left[cross_lo], right[cross_lo])
            if left[hi] <= right[lo] and overlap > 0:
                axis, before, after = axis_key, *pair
                boxes = (left, right)
    if axis is None:
        raise edit.EditError("соседи не стоят рядом: один должен лежать целиком левее (выше) другого и пересекаться с ним по другой оси; "
                             "разделитель в зазоре между такими элементами не поставить — подвиньте их (move_element)")
    left, right = boxes
    lo, hi = (0, 2) if axis == "h" else (1, 3)
    cross_lo, cross_hi = (1, 3) if axis == "h" else (0, 2)
    gap = right[lo] - left[hi]
    thin, thick = anchors.SPLITTER_THICKNESS
    if not thin <= gap <= thick:
        raise edit.EditError(f"зазор между соседями {gap} px, а разделители корпуса — от {thin} до {thick} px: раздвиньте или сдвиньте соседей "
                             "(move_element) так, чтобы зазор подошёл, либо ставьте разделитель с box")
    top = min(left[cross_lo], right[cross_lo])
    bottom = max(left[cross_hi], right[cross_hi])
    box = (left[hi], top, gap, bottom - top) if axis == "h" else (top, left[hi], bottom - top, gap)
    cross = "v" if axis == "h" else "h"
    given = anchor or {}
    if takes_growth is not None and given.get(axis) is not None:
        raise edit.EditError(f"takes_growth и anchor[{axis!r}] называют одно — поведение разделителя по оси движения: оставьте одно из двух")
    roles = {axis: given.get(axis) or GROWTH_ROLES[takes_growth or "both"][axis]}
    if given.get(cross) is not None:
        roles[cross] = given[cross]
    else:
        sig_before, sig_after = _cross_sig(before, cross), _cross_sig(after, cross)
        if sig_before != sig_after:
            raise edit.EditError(f"соседи привязаны по {'вертикали' if cross == 'v' else 'горизонтали'} по-разному, и разделитель повторил бы "
                                 f"одного из них, какого — по положению не решить; задайте anchor={{\"{cross}\": роль}} (роль set_anchors, "
                                 f"{{\"as\": \"<сосед>\"}} копирует правила соседа)")
        roles[cross] = {"as": edit.name_of(before)}
    snapshot = copy.deepcopy(doc)
    try:
        said = add_element(doc, template="Splitter", name=name, box=box, anchor={"h": roles.get("h"), "v": roles.get("v")}, holder=holder,
                           page=page, unverified=unverified)
        from .elements import TYPE_NOTES
        said = said.replace(f"; {TYPE_NOTES['Splitter']}", "")
        parts = [edit.set_anchors(doc, edit.name_of(item), **{axis: {"splitter": name}}) for item in (before, after)]
    except edit.EditError:
        doc.clear()
        doc.update(snapshot)
        raise
    first_name, second_name = edit.name_of(before), edit.name_of(after)
    fixed = _hold_outer_borders(doc, name, before, after, axis, holder_node)
    parts += fixed
    if axis == "h":  # панели таблиц соседей идут за таблицами, как в корпусе (панель повторяет горизонтальные правила своей таблицы)
        for item in (before, after):
            for bar in _bars(holder_node, page, item):
                edit.set_anchors(doc, bar, h={"as": edit.name_of(item)})
                parts.append(f"панель «{bar}» таблицы «{edit.name_of(item)}» повторяет её горизонтальные правила (идёт за разделителем вместе с таблицей)")
    far = (f"внешние границы соседей остаются на месте при сдвиге разделителя: «{first_name}» — {_other_border_words(before, axis, True)}; "
           f"«{second_name}» — {_other_border_words(after, axis, False)}"
           + ("; правило внешней границы поставлено, потому что прежнее шло бы за сдвигом" if fixed else ""))
    return (f"{AXIS_WORDS[axis]} «{name}» между «{first_name}» и «{second_name}»: зазор {gap} px занят целиком, вдоль разделителя — "
            f"протяжение обоих соседей, поперечная привязка — {'как у «' + first_name + '»' if isinstance(roles[cross], dict) else 'по вашей роли'}, "
            f"по оси движения — {'роль slide (дальняя граница долей между краями родителя, размер держится)' if roles[axis] == 'slide' else 'роль ' + str(roles[axis])}; {far}. "
            f"Шаги: {said}; " + "; ".join(parts))
