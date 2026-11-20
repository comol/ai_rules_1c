"""Масштаб правки: сколько существующих элементов затронул перечень операций и не стала ли правка пересборкой дизайна.

Перечень операций, которые могут оказаться пересборкой дизайна (`REBUILD_OPS`), один на код и документы: `SKILL.md`, `docs/brief.md`,
`docs/edit-rules.md` и раздел 9 досье называют те же имена. Ничего не блокируется: правило для модели — словами (пересборка только по явной
просьбе пользователя), итог в отчёте `edit` делает объём правки видимым.
"""
from .base import EditError

# Операции, которые по своей природе меняют форму целиком (если не ограничены ключом `elements` или `panel`).
# `set_view` приводит все поля ввода к одному виду, поэтому он меняет форму целиком всегда и ключа-ограничения не имеет.
WHOLE_OPS = ("relayout", "normalize_anchors", "repair_anchors", "normalize_guides", "normalize_page_edges", "set_view")
# Операции, которые становятся пересборкой, когда затрагивают много элементов (порог — `MASS_ELEMENTS`, `MASS_SHARE`).
COUNTED_OPS = ("set_tab_order", "move_element", "set_font", "set_property", "change_type", "reparent",
               "remove_element", "remove_page", "remove_column", "remove_button", "remove_form_page")
REBUILD_OPS = WHOLE_OPS + COUNTED_OPS

MASS_ELEMENTS = 5       # затронуто больше элементов — пересборка
MASS_SHARE = 4          # или больше 1/MASS_SHARE всех элементов формы (но не меньше MASS_MIN)
MASS_MIN = 3

_LIMITING = {"relayout": (), "normalize_anchors": ("elements",), "repair_anchors": ("elements",), "normalize_guides": (), "normalize_page_edges": ("panel",), "set_view": ()}
_SIZE_NAMES = ("width", "height", "device_width", "device_height")
_ADDING = ("add_element", "add_pair", "add_button", "add_column", "add_page", "add_attribute", "add_form_page", "add_period_choice", "add_collapsible_panel", "copy_layer")
_NAMING = COUNTED_OPS + ("rename_element", "set_caption", "set_anchors", "set_event", "bind")

RULE_LINE = ("**Правило.** Форма меняется только по просьбе пользователя, в объёме просьбы и минимальным числом операций; замечания разбора — предложения, "
             "а не задание. Пересборка дизайна (операции с пометкой «пересборка» ниже) — только по явной просьбе пользователя.")

REBUILD_WORDS = "Это пересборка дизайна: нужна явная просьба пользователя."


def rebuild_note(op):
    """Пометка у операции в таблице раздела 9 досье: `None`, если операция к пересборке не относится."""
    if op in WHOLE_OPS:
        return "пересборка (без ограничения `elements`/`panel`) — только по явной просьбе"
    if op in COUNTED_OPS:
        return f"пересборка при правке больше {MASS_ELEMENTS} элементов — только по явной просьбе"
    return None


# Элементы заготовок `new` (`frm_codec/data/blanks`): панели формы и табличное поле списка. Форма, где нет ничего кроме них (или нет элементов вовсе),
# дизайна ещё не имеет: «пересобирать» в ней нечего, и просьба пользователя на правку такой формы — просьба на её построение.
BLANK_ELEMENTS = frozenset({("ДействияФормы", "CommandBar"), ("ОсновныеДействияФормы", "CommandBar"),
                            ("СправочникСписок", "TableBox"), ("ДокументСписок", "TableBox")})


def is_blank(doc):
    """Исходная форма — заготовка `new` или пустая форма: все её элементы (на любой глубине) из `BLANK_ELEMENTS` либо элементов нет."""
    form = doc.get("form") if isinstance(doc, dict) else None
    holder = form.get("container") if isinstance(form, dict) else None
    if not isinstance(holder, dict):
        return False
    found = []

    def walk(node):
        block = node.get("elements") if isinstance(node, dict) else None
        for item in (block.get("items") if isinstance(block, dict) else None) or ():
            if isinstance(item, dict):
                found.append(((item.get("name_block") or {}).get("name"), item.get("type")))
                walk(item)
    walk(holder)
    return all(pair in BLANK_ELEMENTS for pair in found)


def whole_form_ops(ops):
    """Имена операций перечня, которые меняют форму целиком: `WHOLE_OPS` без ограничения, `set_view`, `set_tab_order` без родителя, размер формы."""
    out = []
    for op in ops:
        if not isinstance(op, dict):
            continue
        name = op.get("op")
        if name in WHOLE_OPS and not any(op.get(key) for key in _LIMITING[name]):
            out.append(name)
        elif name == "set_tab_order" and op.get("holder") in (None, "", "форма"):
            out.append(name)
        elif name == "set_property" and op.get("form") and str(op.get("name")) in _SIZE_NAMES:
            out.append("смена размера формы (set_property)")
    return list(dict.fromkeys(out))


def _targets(ops):
    """Имена существующих элементов, названные операциями (кроме операций, что заводят новое)."""
    names = []
    for op in ops:
        if op.get("op") in _ADDING:
            continue
        for key in ("element", "name"):
            if isinstance(op.get(key), str) and op.get("op") in _NAMING:
                names.append(op[key])
        if isinstance(op.get("elements"), list):
            names += [n for n in op["elements"] if isinstance(n, str)]
    return names


def is_mass(touched, total):
    """Правка велика: затронуто больше `MASS_ELEMENTS` элементов либо не меньше `MASS_MIN` и больше доли `1/MASS_SHARE` всех."""
    return touched > MASS_ELEMENTS or (touched >= MASS_MIN and touched * MASS_SHARE > total)


def summarize(original, final, ops):
    """Строки итога масштаба для конца отчёта `edit`: одна или две. Расчёт по модели раскладки, как у картинки «до | после»."""
    from .. import preview, render
    ops = [op for op in ops if isinstance(op, dict)]
    whole = whole_form_ops(ops)
    blank = is_blank(original)       # заготовка и пустая форма: слов о пересборке дизайна нет, итог масштаба остаётся
    try:
        before, after = render.render(original), render.render(final)
        kb, ka = preview.keyed(before), preview.keyed(after)
        pairs = preview.pair_items(kb, ka)
        views, tabs = preview._changed_attributes(kb, ka, pairs)
    except (ValueError, LookupError, TypeError, EditError) as why:
        head = f"Масштаб правки: по раскладке не оценён ({why})"
        if whole:
            return [head + "; операции, меняющие форму целиком: " + ", ".join(whole)] + ([] if blank else [REBUILD_WORDS])
        return [head]
    after_of = dict(pairs)
    before_of = {a: b for b, a in pairs}
    new = [k for k in ka if k not in before_of]
    touched = {b for b, a in pairs if kb[b][1] != ka[a][1] or kb[b][0].name != ka[a][0].name}
    touched |= {k for k in kb if k not in after_of}
    touched |= {before_of[a] for a, _was, _now in views + tabs if a in before_of}
    names = set(_targets(ops))
    touched |= {k for k, (item, _box) in kb.items() if item.name in names}
    total = len(kb)
    count = total if whole else len(touched)
    owners = {(kb[k][0].owner.name if kb[k][0].owner is not None else "") or "форма" for k in kb if whole or k in touched}
    mass = (bool(whole) or is_mass(count, total)) and not blank
    head = (f"Масштаб правки: затронуто {count} из {total} существующих элементов (панелей и страниц формы с затронутыми элементами: {len(owners)}); "
            f"добавлено новых: {len(new)}; операции, меняющие форму целиком: {', '.join(whole) if whole else 'нет'}")
    return [head] + ([REBUILD_WORDS] if mass else [])
