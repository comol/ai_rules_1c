"""Свёрнутая панель (`Свертка` = `Лево`, `Право`, `Верх`, `Низ`) в модели раскладки.

В предприятии свёрнутая панель исчезает целиком (ни полосы, ни рамки, ни стрелки), а соседи, привязанные к её краю, занимают её место (проверено в предприятии:
сосед справа от панели слева 278 → 8 — левый край панели, сосед под панелью сверху 171 → 40 — верх панели плюс смещение 7; противоположные края стоят на месте; растяжение окна
идёт по тем же правилам; между открытиями свёртка не запоминается). Модель: у панели нулевая протяжённость у начального края стороны свёртки —
`Лево` и `Верх` сжимают дальний край к ближнему, `Право` и `Низ` — ближний к дальнему. Правила соседей к краю панели от этого сами считаются от
начального края, пределы раскладки — как у формы без панели.

`fold_doc(doc, folded)` — копия документа с такими панелями; сам документ не меняется. Саму панель с вложенными элементами из рисунка убирает вызывающий (`render`).
"""
import copy

from .. import edit
from ..edit import names as N

# сторона → (имя режима в коде, ось 0 — по ширине, 1 — по высоте, сжимаемый край: 0 — ближний к дальнему, 1 — дальний к ближнему)
MODES = {"Лево": (0, 1), "Право": (0, 0), "Верх": (1, 1), "Низ": (1, 0)}


def _sides(axis):
    """`(ближняя граница, дальняя граница)` оси: индексы в `edit.ANCHORS` (верхняя, нижняя, левая, правая) и ключи `X/Y/WIDTH/HEIGHT` координат."""
    return ((2, 3, N.X, N.WIDTH) if axis == 0 else (0, 1, N.Y, N.HEIGHT))


def fold_doc(doc, folded):
    """`folded` — `{индекс панели: режим}` (`Лево`, `Право`, `Верх`, `Низ`); режим `Нет` не сворачивает. Панель, чей край привязан не к краю родителя и не к
    другому элементу (правила нет), сжимается в координатах: `box` нулевой, правило не пишется."""
    out = copy.deepcopy(doc)
    changed = []
    wanted = {i: m for i, m in folded.items() if m in MODES}
    if not wanted:
        return out
    for _name, holder in edit.holders(out):
        block = holder.get(edit.ELEMENTS)
        for item in (block.get(edit.ITEMS) or []) if isinstance(block, dict) else []:
            mode = wanted.get(item.get(edit.INDEX)) if isinstance(item, dict) else None
            coords = item.get(edit.COORDS) if mode else None
            if not isinstance(coords, dict):
                continue
            axis, collapse_far = MODES[mode]
            near_i, far_i, near_key, far_key = _sides(axis)
            keep, drop = (near_i, far_i) if collapse_far else (far_i, near_i)
            keep_key, drop_key = (near_key, far_key) if collapse_far else (far_key, near_key)
            coords[drop_key] = coords[keep_key]
            changed.append((block, item))
            kept, dropped = coords[edit.ANCHORS[keep]], coords[edit.ANCHORS[drop]]
            for rule_name in edit.RULES:
                dropped[rule_name] = copy.deepcopy(kept[rule_name])
    for block, item in changed:
        _follow(block.get(edit.ITEMS) or [], item)
    return out


_SIDE_KEY = (N.Y, N.HEIGHT, N.X, N.WIDTH)      # стороны правил: 0 — верх, 1 — низ, 2 — лево, 3 — право


def _follow(items, start):
    """Элементы, чьи границы привязаны к сторонам сдвинувшегося, встают на их новое место (`край объекта + смещение`) и тянут свои цепочки дальше: проектные `box`
    вместе с правилами остаются согласованными, и модель считает рост от нового места."""
    queue, seen = [start], set()
    while queue:
        mover = queue.pop()
        index = mover.get(edit.INDEX)
        if index in seen:
            continue
        seen.add(index)
        edges = mover[edit.COORDS]
        for other in items:
            if other is mover or not isinstance(other, dict) or not isinstance(other.get(edit.COORDS), dict):
                continue
            coords, moved = other[edit.COORDS], False
            for border, key in zip(edit.ANCHORS, _SIDE_KEY):
                for rule_name in edit.RULES[:1]:
                    rule = (coords.get(border) or {}).get(rule_name) or {}
                    side = rule.get(edit.RULE_SIDE)
                    if rule.get(edit.RULE_OBJECT) == index and side in (0, 1, 2, 3):
                        want = edges[_SIDE_KEY[side]] + rule.get(edit.RULE_OFFSET, 0)
                        if coords[key] != want:
                            coords[key], moved = want, True
            if moved:
                queue.append(other)


def descendants(doc, indexes):
    """Индексы панелей и всех их вложенных элементов: на рисунке свёрнутая панель не видна целиком."""
    found = set()

    def walk(node, inside):
        block = node.get(edit.ELEMENTS)
        for item in (block.get(edit.ITEMS) or []) if isinstance(block, dict) else []:
            if not isinstance(item, dict):
                continue
            mine = inside or item.get(edit.INDEX) in indexes
            if mine and isinstance(item.get(edit.INDEX), int):
                found.add(item[edit.INDEX])
            walk(item, mine)

    walk(edit.container(doc), False)
    return found
