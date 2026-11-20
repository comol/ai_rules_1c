"""Раздел «поведение» досье: предел раскладки, что растягивается и что остаётся на месте."""

import collections

from .. import layout, structure as structure_mod
from . import words, vocab
from .fmt import _list, _pct, _table


ROW_ROLES = (structure_mod.CONTENT, structure_mod.TOP_BAR, structure_mod.BOTTOM_BAR, structure_mod.COLUMN, structure_mod.GROUP,
             structure_mod.PAGE, structure_mod.BUTTONS)     # узлы, у которых в «Поведении» своя строка (кроме узлов верхнего уровня)


def _share(c, axis):
    """Доля роста окна, которую забирает размер элемента по оси (0 — ширина, 1 — высота): ширина растёт на `правая − левая` коэффициентов."""
    return (c[3] - c[2]) if axis == 0 else (c[1] - c[0])


def _group_behaviour(names, coef, items, axis):
    groups = collections.OrderedDict()
    for name in names:
        item = items.get(name)
        c = coef.get(item.index) if item is not None else None
        if c is None:
            word = None
        else:
            word = (layout.horizontal_behaviour(c[2], c[3]) if axis == 0 else layout.vertical_behaviour(c[0], c[1]))
        groups.setdefault(word, []).append(name)
    return groups


def _shares(groups, coef, items, axis):
    """`{имя: доля}` у пропорциональных элементов групп."""
    out = {}
    for name in groups.get(layout.PARTLY, ()):
        c = coef.get(items[name].index)
        if c is not None:
            out[name] = round(_share(c, axis), 2)
    return out


def _named(word, members, shares, short):
    if word == layout.PARTLY and shares:
        return ", ".join(f"{short(n)} ({_pct(shares[n])})" if n in shares else short(n) for n in members[:vocab.LISTED]) + (
            f" и ещё {len(members) - vocab.LISTED}" if len(members) > vocab.LISTED else "")
    return _list([short(n) for n in members])


def _behaviour_text(groups, axis, shares, short):
    if len(groups) == 1:
        (word, members), = groups.items()
        if word is None or len(members) == 1:
            text = layout.behaviour_words(word, axis, layout.SENTENCE)
            if word == layout.PARTLY and members[0] in shares:
                text += f": {_pct(shares[members[0]])} прироста окна"
            return text
        head = "все " + layout.behaviour_words(word, axis, layout.LISTED)
        if word == layout.PARTLY and shares:
            head += ": " + _named(word, members, shares, short)
        return head
    return "; ".join(f"{layout.behaviour_words(word, axis, layout.LISTED)}: {_named(word, members, shares, short)}"
                     for word, members in groups.items())


def _row_nodes(structure):
    """Узлы, у которых в «Поведении» своя строка: верхнего уровня и узлы ролей `ROW_ROLES`."""
    top = set(id(n) for n in structure.root.children)
    return [n for n in structure.walk() if n.id != "A0" and (id(n) in top or n.role in ROW_ROLES)]


def _own_members(node, rows, names):
    """Элементы узла и тех его потомков, у которых своей строки нет: элемент входит ровно в одну строку, без строк-объединений."""
    out = [n for n in node.elements if n in names.item_of]
    for child in node.children:
        if id(child) not in rows:
            out += _own_members(child, rows, names)
    return out


def _behavior(doc, form, structure, names, facts):
    coef = layout.coefficients(form, hide=False)
    (w_lo, w_hi), (h_lo, h_hi), limits = layout.form_range(form, coef)
    section = {"size": [form.width, form.height],
               "range": {"width": [w_lo, w_hi], "height": [h_lo, h_hi]},
               "resize_forbidden": doc.get("size_change") == "DontChange"}
    lim = []
    for axis in (0, 1):
        for direction in (1, -1):
            found = limits.get((axis, direction)) or []
            if found:
                lim.append(names.text(words.plain_limit(layout.limit_line(form, coef, axis, direction, found[0]))))
    section["limits"] = lim
    section["words"] = (f"раскладка следует за окном: ширина {layout._size_words(w_lo, w_hi)}, высота "
                        f"{layout._size_words(h_lo, h_hi)}")
    rows = []
    row_nodes = _row_nodes(structure)
    own = {id(n) for n in row_nodes}
    for node in row_nodes:
        members = _own_members(node, own, names)
        if not members:
            continue
        wide = _group_behaviour(members, coef, names.item_of, 0)
        high = _group_behaviour(members, coef, names.item_of, 1)
        sw, sh = _shares(wide, coef, names.item_of, 0), _shares(high, coef, names.item_of, 1)
        rows.append({"node": node.id, "role": node.role, "elements": len(members),
                     "width": {str(k): v for k, v in wide.items()}, "height": {str(k): v for k, v in high.items()},
                     "width_shares": sw, "height_shares": sh,
                     "width_words": _behaviour_text(wide, 0, sw, names.short), "height_words": _behaviour_text(high, 1, sh, names.short)})
    section["nodes"] = rows
    problems = [f for f in facts if f.kind in vocab.IN_BEHAVIOR]
    section["problems"] = [{"kind": f.kind, "node": f.node, "element": f.element, "numbers": f.numbers, "words": f.words}
                           for f in problems]
    return section


def _md_behavior(behavior):
    lines = ["## 4. Поведение", "", f"Размер {behavior['size'][0]}×{behavior['size'][1]}; {behavior['words']}."]
    if behavior["resize_forbidden"]:
        lines.append("Изменение размера окна у формы запрещено («Изменять размер» снято, кнопки «развернуть» у окна нет): поведение ниже следует из привязок, в работе окно не "
                     "растягивается; на картинке поведения один кадр — размер из файла.")
    for line in behavior["limits"]:
        lines.append(f"- Предел: {line}")
    if behavior["nodes"] and behavior["resize_forbidden"]:
        lines += ["", "Таблицы растяжения нет: окно не меняется, привязки к краям формы ничего не растягивают."]
    elif behavior["nodes"]:
        lines += ["", "Что делают узлы при растяжении окна (в строке узла — его элементы и элементы без своей строки; доля у пропорциональных — "
                  "сколько прироста окна забирает размер элемента):", ""]
        lines += _table(["Узел", "Роль", "По ширине", "По высоте"],
                        [[n["node"], structure_mod.ROLE_WORDS[n["role"]], n["width_words"], n["height_words"]] for n in behavior["nodes"]])
    if behavior["problems"]:
        lines += ["", "Проблемы раскладки:"]
        for p in behavior["problems"]:
            lines.append(f"- {p['node'] or 'форма'}: {p['words']}")
    else:
        lines += ["", "Поломок раскладки (залипание, наезды при размере окна, повреждённые привязки) не найдено."
                  + (" Столкновение на пределе окна из строк «Предел» — граница раскладки, а не поломка при обычном размере."
                     if any("столкновение" in line for line in behavior["limits"]) else "")]
    return lines + [""]
