"""Правила привязок: живое или мёртвое правило (по встречной записи)."""
from .. import anchors, edit
from .model import CENTER_SIDES, SIDE_WORDS, ALIVE, DEAD, UNKNOWN


def rule_state(form, item, border, rule):
    """Действует ли правило в предприятии: `(ALIVE | DEAD | UNKNOWN, почему)`. Критерий — встречная запись: у соседа в списке
    зависимых той стороны, к которой привязались; у родителя в списке блока раскладки его стороны. Без записи правило мёртвое.
    """
    if rule.obj == 0:
        holder = form.holder_of(item)
        if holder.rows is None:
            return UNKNOWN, "у родителя не разобран блок раскладки — строк не проверить"
        listed = anchors.RECORD_LIST.get(rule.side)
        if listed is None:
            return UNKNOWN, f"сторона {rule.side} карте не известна — строки не проверить"
        rows = holder.rows.get(listed)
        if rows is None:
            return UNKNOWN, (f"списка {edit.LAYOUT_LISTS[listed]} у родителя нет или он не массив "
                             "— строк не проверить")
        if (item.index, border) in rows:
            return ALIVE, None
        where = "формы" if holder.item is None else f"панели «{holder.name}»"
        edge = SIDE_WORDS[rule.side]
        example = ("центр без строки у родителя" if rule.side in CENTER_SIDES
                   else "правила есть, строк нет")
        return DEAD, (f"нет строки ({item.index}, {border}) в списке {edit.LAYOUT_LISTS[listed]} "
                      f"{where} — к {edge} без неё в предприятии не держится ({example})")
    target = form.items.get(rule.obj)
    if target is None and rule.obj in {item.index for item in form.raw}:
        return UNKNOWN, (f"правило называет элемент {rule.obj}, чей блок координат лежит сырым "
                         "— его записей не прочесть; модель держит границу на месте")
    if target is None:
        return DEAD, f"элемента с индексом {rule.obj} в форме нет — ссылка висячая"
    if target.holder != item.holder:
        return UNKNOWN, (f"правило называет элемент другого родителя ({target.label()}) — "
                         "такого в формах не встречалось")
    listed = anchors.RECORD_LIST.get(rule.side)
    if listed is None:
        return UNKNOWN, f"сторона {rule.side} карте не известна — записи не проверить"
    if target.deps[listed] is None:
        return UNKNOWN, (f"список {edit.DEPENDENTS[listed]} у «{target.label()}» не массив — "
                         "записи не проверить")
    if (item.index, border) in target.deps[listed]:
        return ALIVE, None
    who = "в своём списке" if target is item else f"у «{target.label()}» в списке"
    return DEAD, (f"нет встречной записи ({item.index}, {border}) {who} "
                  f"{edit.DEPENDENTS[listed]} — без неё в предприятии правило не действует")


def _live(form, item, border, rule):
    """Правило есть и не мёртвое: граница идёт за ним (`coefficients`, `Layout._round`)."""
    return rule is not None and rule_state(form, item, border, rule)[0] != DEAD


def dead_rules(form):
    """Все мёртвые правила формы: `[(элемент, граница, «первое»/«второе», правило, почему)]`."""
    out = []
    for item in _all_items(form):
        for border, pair in enumerate(item.rules):
            for which, rule in zip(("первое", "второе"), pair):
                if rule is None:
                    continue
                state, why = rule_state(form, item, border, rule)
                if state == DEAD:
                    out.append((item, border, which, rule, why))
    return out


def _all_items(form):
    for key in form.holders:
        yield from form.holders[key].children
