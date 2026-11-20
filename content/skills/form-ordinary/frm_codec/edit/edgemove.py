"""Размер формы с переносом элементов вместе с краем (`set_property` с `form: true`, `width`/`height` и ключом `move_with_edge`).

Платформа при смене размера палитрой элементы не двигает: смещения их привязок к краю формы она переписывает так, чтобы край элемента остался на
месте (`setprop.ROUND15_SIZE`). Мышью за край формы в конфигураторе тот же край уходит вместе с рукой: элементы, привязанные к правому
или нижнему краю, сдвигаются за ним, смещения привязок остаются прежними. Ключ воспроизводит второе.

Для элемента верхнего уровня каждая привязка с объектом 0 (форма) и стороной 3 (правая) или 1 (нижняя) называет границу элемента (верх, низ, лево,
право); граница получает `+Δ`, смещение не меняется — «край = размер + смещение» держится, как у платформы. Если край панели при этом сдвинулся,
её размер вдоль оси изменился на Δ' — и вложенные элементы, привязанные к тому же краю ПАНЕЛИ (объект 0 у вложенного — родитель), получают `+Δ'`;
так по цепочке вглубь.

Отказ словами, пока результат не вычислить без догадки: у сдвинутой границы стоят зависимые элементы (они держатся за неё правилом, и их места
платформа пересчитала бы сама, а в файле они остались бы прежними), или элемент после сдвига получает нулевой или отрицательный размер. Первый отказ
снимает `unverified` — зависимые остаются на местах, отчёт их называет; второй не снимает ничего.
"""
from .base import EditError, elements_of
from .names import (ANCHORS, COORDS, DEPENDENTS, DEP_ELEMENT, ELEMENTS, HEIGHT, INDEX, NAME, NAME_BLOCK, RULES, RULE_OBJECT, RULE_OFFSET, RULE_SIDE, WIDTH, X, Y)

# Граница привязки → ключ координаты (порядок привязок в блоке координат: верх, низ, лево, право).
EDGE_OF = dict(zip(ANCHORS, (Y, HEIGHT, X, WIDTH)))
# Ось → (сторона привязки, ключ ближней границы, ключ дальней границы).
AXIS = {"width": (3, X, WIDTH), "height": (1, Y, HEIGHT)}


def _name(element):
    return (element.get(NAME_BLOCK) or {}).get(NAME)


def _moving_edges(element, side):
    """Ключи координат границ элемента, которые держит привязка к стороне `side` родителя (объект 0)."""
    coords = element.get(COORDS)
    out = []
    if not isinstance(coords, dict):
        return out
    for anchor_key, edge_key in EDGE_OF.items():
        anchor = coords.get(anchor_key)
        if not isinstance(anchor, dict):
            continue
        for rule_key in RULES:
            rule = anchor.get(rule_key)
            if (isinstance(rule, dict) and rule.get(RULE_OBJECT) == 0 and rule.get(RULE_SIDE) == side
                    and isinstance(rule.get(RULE_OFFSET), int) and not isinstance(rule.get(RULE_OFFSET), bool)):
                if edge_key not in out:
                    out.append(edge_key)
    return out


def _dependents(element):
    """Индексы элементов, которые держатся за границы этого."""
    coords = element.get(COORDS) or {}
    found = set()
    for key in DEPENDENTS:
        for entry in coords.get(key) or ():
            if isinstance(entry, dict) and isinstance(entry.get(DEP_ELEMENT), int):
                found.add(entry[DEP_ELEMENT])
    return found


def plan(doc_container, axis, delta):
    """`(записи, слова, зависимые)` для оси `axis` и приращения `delta`: записи — `(блок координат, ключ, новое число, пометка, где)` в том же виде,
    что у остальных записей размера формы. `doc_container` — контейнер формы (верхний уровень); зависимые — `{имя: [имена зависимых]}`, о них отчёт говорит
    и без ключа отказывает вызывающий."""
    side, near, far = AXIS[axis]
    writes, moved_names = [], []
    clashes = []

    def walk(holder, shift, owner):
        items = [item for item in (elements_of(holder) if isinstance(holder.get(ELEMENTS), dict) else ()) if isinstance(item, dict)]
        by_index = {item.get(INDEX): item for item in items}
        moved = {}
        for item in items:
            edges = _moving_edges(item, side)
            if not edges:
                continue
            coords = item[COORDS]
            if not all(isinstance(coords.get(key), int) and not isinstance(coords.get(key), bool) for key in (near, far)):
                raise EditError(f"{axis} у формы: у элемента «{_name(item)}» границы ({near}, {far}) в блоке координат не числа — сдвигать их вместе с краем нечем")
            new = {key: coords[key] + shift for key in edges if isinstance(coords.get(key), int)}
            before = coords[far] - coords[near]
            after = new.get(far, coords[far]) - new.get(near, coords[near])
            if after <= 0:
                raise EditError(f"{axis} у формы: «{_name(item)}» после сдвига вместе с краем получил бы размер {after} (был {before}): край уехал бы за противоположную "
                                "границу. Сначала уменьшите размер меньшим шагом либо перенесите элемент вручную (`move_element`)")
            moved[item.get(INDEX)] = (item, new, after - before)
        for index, (item, new, grew) in moved.items():
            coords = item[COORDS]
            for key, value in new.items():
                writes.append((coords, key, value, None, f"{owner}{_name(item)}/{key}"))
            moved_names.append(f"{owner}{_name(item)}")
            left = sorted(by_index[i] and _name(by_index[i]) or str(i) for i in _dependents(item) if i not in moved and i in by_index)
            if left:
                clashes.append((f"{owner}{_name(item)}", left))
            if grew and isinstance(item.get(ELEMENTS), dict):
                walk(item, grew, f"{owner}{_name(item)}/")
    walk(doc_container, delta, "")
    return writes, moved_names, clashes
