"""Подменю командной панели: кнопка-подменю с набором кнопок, пункты подменю и удаление подменю.

Строение (так пишет конфигуратор):

* кнопка-подменю — кнопка вида `Popup`; её запись действия называет ссылкой набор подменю: `(GUID головы блока, код набора)`;
* набор подменю — отдельный набор блока: GUID владельца — голова блока, код — номер кнопки-подменю плюс один;
* счётчик головы (`last_number`) занят и номером кнопки, и кодом набора: следующая кнопка получает номер на единицу больше кода;
* хвост набора, в котором лежит кнопка-подменю, перечисляет её тройкой `(голова, номер кнопки, 0)` после счётчика;
* пункты подменю — обычные кнопки в наборе подменю; подменю внутри подменю — кнопка `Popup` в наборе подменю, и ей заводится
  такой же набор.

Модуль зовут `add_button` (`kind`, `parent`) и `remove_button` из `edit.buttons`; импорт там отложен: модули ссылаются друг на друга.
"""

from .. import validate
from .names import (
    ACTIONS,
    ACT_KIND,
    ACT_SPEC,
    BTN_NAME,
    BTN_TEXT,
    BUTTONS,
    BUTTON_SETS,
    LS_COUNT,
    LS_ITEMS,
    LS_MARK,
    NUMBER,
    REF_CODE,
    REF_ID,
    SET_CODE,
    SET_REF,
    SPEC_MARK,
    _at,
    _maybe,
)
from .base import EditError, _action_of, _buttons

BTN_TYPE = _at("Element.CommandBarButton", 9)
BTN_PLACE = _maybe("Element.CommandBarButton", 5)  # u5: у разделителя 0, у кнопки и подменю 1
BTN_FLAG13 = _maybe("Element.CommandBarButton", 13)
SET_TAIL = "L1+0"  # хвост набора: `[-1, 0, [счётчик, голова, номер, 0, …]]`; у него нет имени в карте (`FORMAT.md`, ButtonSet)
POPUP, SEPARATOR = "Popup", "Separator"
SEPARATOR_REF = ("9d0a2e40-b978-11d4-84b6-008048da06df", 0)  # разделитель — служебная пара (`validate.SERVICE_REFS`)
SUBMENU_KIND = "кнопка-подменю"
KINDS = ("action", "submenu", "separator")

# Подменю внутри подменю: у 42 панелей 4 993 форм корпуса — 61 такое подменю из 4 595.
CORPUS_NESTED = (61, 4595)


def button_kind(kind):
    """Вид новой кнопки: `action` (умолчание), `submenu` или `separator`; иное — отказ словами."""
    if kind is None:
        return KINDS[0]
    if kind not in KINDS:
        raise EditError(f"kind — вид кнопки: {', '.join(KINDS)}; а назван {kind!r}")
    return kind


def check_arguments(kind, parent, donor, button_set, standard, procedure, action_donor, text):
    """Отказ, если ключи вида кнопки и места несовместимы. Вызывается до правки."""
    if kind != "action":
        named = [name for name, value in (("donor", donor), ("standard", standard), ("procedure", procedure),
                                          ("action_donor", action_donor)) if value is not None]
        if named:
            raise EditError(f"kind={kind!r} ставит кнопку целиком, а ключи {', '.join(named)} относятся к кнопке-"
                            "действию: уберите их (действие подменю — набор его кнопок, у разделителя действия нет)")
    if kind == "separator" and text is not None:
        raise EditError("у разделителя текста нет: уберите text")
    if parent is not None and button_set != -1:
        raise EditError("parent называет набор, в который встанет кнопка (набор подменю), а button_set — номер набора "
                        "панели: назовите что-то одно")


def submenu_sets(block):
    """`{id GUID кнопки: (набор подменю, пара)}` — подменю блока: кнопки вида `Popup`, чья запись называет набор этого блока."""
    pairs = {(item.get(SET_REF, {}).get("guid"), item.get(SET_CODE)): item
             for item in block.get(BUTTON_SETS) or [] if isinstance(item, dict)}
    out = {}
    for _set, button in _buttons(block):
        if button.get(BTN_TYPE) != POPUP:
            continue
        action = _action_of(block, button, "", button.get(BTN_NAME))
        pair = _spec_pair(action)
        if pair in pairs and _is_submenu_action(action):
            out[button["id"]["guid"]] = (pairs[pair], pair)
    return out


def _spec_pair(action):
    spec = action.get(ACT_SPEC)
    ref = spec.get(REF_ID) if isinstance(spec, dict) else None
    return (ref.get("guid") if isinstance(ref, dict) else None, spec.get(REF_CODE) if isinstance(spec, dict) else None)


def _is_submenu_action(action):
    spec = action.get(ACT_SPEC)
    return isinstance(spec, dict) and REF_ID in spec and REF_CODE in spec


def last_panel_set(block, sets):
    """Последний набор блока, который не набор подменю; если таких нет — последний набор."""
    named = {pair for _set, pair in submenu_sets(block).values()}
    own = [item for item in sets if (item.get(SET_REF, {}).get("guid"), item.get(SET_CODE)) not in named]
    return own[-1] if own else sets[-1]


def parent_set(block, bar, parent):
    """Набор подменю `parent` панели `bar`: `(набор, кнопка)`. Отказ, если такой кнопки нет или она не подменю."""
    found = [button for _set, button in _buttons(block) if button.get(BTN_NAME) == parent]
    if not found:
        known = ", ".join(str(b.get(BTN_NAME)) for _s, b in _buttons(block) if b.get(BTN_TYPE) == POPUP) or "—"
        raise EditError(f"parent={parent!r}: такой кнопки в панели {bar!r} нет; подменю здесь: {known}")
    if len(found) > 1:
        raise EditError(f"parent={parent!r}: в панели {bar!r} {len(found)} кнопок с этим именем — по имени не решить")
    button = found[0]
    sets = submenu_sets(block)
    if button["id"]["guid"] not in sets:
        raise EditError(f"parent={parent!r}: кнопка {parent!r} панели {bar!r} — не подменю (вид {button.get(BTN_TYPE)}), "
                        "пункты кладут только в набор подменю; подменю заводит add_button с kind=\"submenu\"")
    return sets[button["id"]["guid"]][0], button


def shape_separator(node, record):
    """Узел и запись разделителя — как их пишет платформа: кнопка вида `Separator` без текста, ссылка на служебную пару."""
    node[BTN_TYPE] = SEPARATOR
    node[BTN_TEXT] = {LS_MARK: 1, LS_COUNT: 0, LS_ITEMS: []}
    node[BTN_PLACE] = 0
    if BTN_FLAG13 in node:
        node[BTN_FLAG13] = 0
    record[ACT_SPEC] = {SPEC_MARK: 1, REF_ID: {"guid": SEPARATOR_REF[0]}, REF_CODE: SEPARATOR_REF[1]}


def shape_submenu(node):
    """Узел кнопки-подменю: вид `Popup`; ссылку записи действия ставит `register_submenu` — код набора ещё не известен."""
    node[BTN_TYPE] = POPUP
    if BTN_FLAG13 in node:
        node[BTN_FLAG13] = 0


def next_number(block, head, numbers, last):
    """Номер подменю: больше счётчика головы, номеров кнопок и кодов наборов с владельцем-головой."""
    codes = [item.get(SET_CODE) for item in block.get(BUTTON_SETS) or []
             if isinstance(item, dict) and (item.get(SET_REF) or {}).get("guid") == head
             and isinstance(item.get(SET_CODE), int)]
    return max(numbers + codes + [last if isinstance(last, int) and not isinstance(last, bool) else 0]) + 1


def register_submenu(block, head, target, node, record, number):
    """Набор подменю: заводит набор с кодом «номер + 1», ссылку записи действия и тройку в хвосте набора `target`.

    Возвращает код набора. Номер больше всех кодов наборов головы (`next_number`), поэтому код «номер + 1» свободен. Отказ, если
    хвост набора не как у платформы: он проверяется до первой правки.
    """
    code = number + 1
    tail = _tail(target)
    new_set = {"mark": 5, SET_REF: {"guid": head}, SET_CODE: code, "u3": 0, BUTTONS: [], SET_TAIL: [-1, 0, [0]]}
    block[BUTTON_SETS].append(new_set)
    record[ACT_SPEC] = {SPEC_MARK: 1, REF_ID: {"guid": head}, REF_CODE: code}
    tail[0] += 1
    tail += [{"guid": head}, number, 0]
    return code


def _tail(target):
    """Список хвоста набора `[счётчик, (голова, номер, 0)…]`; отказ, если хвост не такой, как пишет платформа."""
    tail = target.get(SET_TAIL)
    items = tail[2] if isinstance(tail, list) and len(tail) == 3 and isinstance(tail[2], list) else None
    if not items or not isinstance(items[0], int) or isinstance(items[0], bool) or len(items) != 1 + 3 * items[0]:
        raise EditError(f"хвост набора кнопок ({target.get(SET_REF)}, код {target.get(SET_CODE)}) не такой, как пишет "
                        f"платформа ({tail!r}): подменю в такой набор не кладётся, правьте JSON по адресу")
    return items


def forget_tail(target, number):
    """Убирает из хвоста набора тройку кнопки-подменю с этим номером. Возвращает, была ли она."""
    tail = target.get(SET_TAIL)
    items = tail[2] if isinstance(tail, list) and len(tail) == 3 and isinstance(tail[2], list) else None
    if not items or not isinstance(items[0], int) or len(items) != 1 + 3 * items[0]:
        return False
    for at in range(1, len(items), 3):
        if items[at + 1] == number:
            del items[at:at + 3]
            items[0] -= 1
            return True
    return False


def nested_note():
    nested, total = CORPUS_NESTED
    return (f"; подменю внутри подменю: корпус такое строение держит ({nested} из {total} подменю), платформа сама его "
            "пишет; в предприятии оно раскрывается, пункт вызывает свою процедуру")


def submenu_note(bar, name, number, code):
    return (f"; подменю: набор кнопок с кодом {code} (владелец — голова блока), счётчик головы занят и номером кнопки "
            f"{number}, и кодом набора; запись такая же, как у подменю, созданного в конфигураторе; пункты — add_button "
            f"с parent={name!r}")


def plan_remove(block, head, record):
    """Что уберёт удаление подменю, — до правки: `[(пара, набор, [(кнопка, запись)])]` и слова о наборах, которые остались.

    Запись самой кнопки-подменю считается уже убранной. Набор убирается, если на него больше никто не ссылается; набор с чужим
    владельцем (не голова блока) и первый набор панели не трогаются: подменю с таким набором платформа пишет редко, и что с ним
    делать, неизвестно. Записи собираются до правки: у кнопки без записи отказ приходит до первого изменения документа.
    """
    plan, kept, gone = [], [], {id(record)}

    def walk(pair):
        sets = block[BUTTON_SETS]
        target = next((item for item in sets if (item.get(SET_REF, {}).get("guid"), item.get(SET_CODE)) == pair), None)
        if target is None or pair[0] != head or sets.index(target) == 0 or any(p == pair for p, _t, _e in plan):
            return
        left = {p for item in block.get(ACTIONS) or [] if id(item) not in gone
                for p in validate._refs_in(item.get(ACT_SPEC), REF_ID, REF_CODE)}
        if pair in left:
            kept.append(f"набор подменю {pair[1]} оставлен: на него ссылается ещё одна запись действия")
            return
        entries = [(button, _action_of(block, button, "", button.get(BTN_NAME))) for button in target.get(BUTTONS) or []]
        plan.append((pair, target, entries))
        gone.update(id(rec) for _b, rec in entries)
        for button, rec in entries:
            if button.get(BTN_TYPE) == POPUP and _is_submenu_action(rec):
                walk(_spec_pair(rec))

    walk(_spec_pair(record))
    return plan, kept


def apply_remove(block, button_set, node, plan, kept):
    """Убирает набор подменю с пунктами и тройку кнопки из хвоста набора, в котором она лежала. Возвращает слова для отчёта."""
    words = []
    if forget_tail(button_set, node.get(NUMBER)):
        words.append(f"тройка подменю убрана из хвоста набора {button_set.get(SET_CODE)}")
    for pair, target, entries in plan:
        for _button, rec in entries:
            block[ACTIONS].remove(rec)
        block[BUTTON_SETS].remove(target)
        names = ", ".join(str(button.get(BTN_NAME)) for button, _rec in entries) or "—"
        words.append(f"набор подменю {pair[1]} убран вместе с кнопками: {names}")
    return words + kept
