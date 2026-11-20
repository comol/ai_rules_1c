"""Порядок обхода страницы списком одной операцией: `set_tab_order`.

`set_property tab_order` ставит один элемент на место и перенумеровывает страницу; чтобы выстроить обход по порядку чтения, их нужно столько, сколько
элементов на странице. Здесь тот же результат — номера 1…N по странице родителя — задаётся одним перечнем имён либо порядком чтения структуры досье.
"""
from .base import EditError, container, find_element, holder_by_name, holders, name_of, pages_count
from .rowsa import auto_tab_order


def _page_group(target, page):
    from . import elements as ee
    items = ee.elements_of(target)
    return [item for item in items if isinstance(item, dict) and isinstance(item.get(ee.COORDS), dict) and item[ee.COORDS].get(ee.PAGE) == page]


def _number(item):
    from . import elements as ee
    value = item[ee.COORDS].get(ee.TAB_ORDER)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _reading(doc, group):
    """Элементы `group`, принимающие фокус, в порядке чтения структуры досье: `[элемент]`."""
    from .. import layout, structure as structure_mod
    from ..brief import facts
    from . import elements as ee
    form = layout.read(doc)
    names = facts._Names(form, structure_mod.recognize(doc))
    place = {name: at for at, name in enumerate(names.structure.reading_order())}
    focused = [item for item in group if (found := form.items.get(item[ee.INDEX])) is not None and facts._focused(found)]
    return sorted(focused, key=lambda item: place.get(names.by_item.get(item[ee.INDEX]), len(place)))


def set_tab_order(doc, holder=None, page=0, order=None, by=None, unverified=False):
    """Порядок обхода (Tab) страницы родителя: одним перечнем либо по порядку чтения.

    `holder` — имя родителя (панель); без него — форма (`""` и `"форма"` — то же). `page` — страница родителя, с нуля (умолчание 0).

    * `order` — имена элементов по порядку обхода. Названные элементы занимают, в этом порядке, места, которые занимали сами (места не названных не
      меняются); список может быть неполным, но имя в нём — один раз и только элемент этого родителя на этой странице.
    * `by: "reading"` — элементы страницы, принимающие фокус, встают в порядке чтения структуры досье (досье `brief`, строка «по чтению»
      в факте о порядке обхода); не принимающие фокус (надписи, рамки, невидимые) остаются на своих местах.

    Номера страницы после операции — 1…N подряд (как платформа нумерует при перестановке в диалоге «Настройка порядка обхода…»). При включённом
    АвтоПорядокОбхода родителя — отказ, как у `set_property tab_order`: платформа ведёт порядок по положению, а конфигуратор при нём отказывает;
    `unverified` пишет номера всё равно. Отчёт называет «было → стало» по каждому элементу, у которого номер изменился.
    """
    if (order is None) == (by is None):
        raise EditError("set_tab_order: задайте ровно одно — order (имена элементов по порядку обхода) или by (\"reading\": порядок чтения структуры досье)")
    if by is not None and by != "reading":
        raise EditError(f"set_tab_order: by принимает только \"reading\" (порядок чтения структуры досье), а пришло {by!r}")
    if order is not None and (not isinstance(order, list) or not order or not all(isinstance(n, str) for n in order)):
        raise EditError(f"set_tab_order: order — непустой список имён элементов по порядку обхода, а пришло {order!r}")
    if holder is None or (holder in ("", "форма") and not any(n == holder for n, _h in holders(doc))):
        target, where = container(doc), "формы"
    else:
        target, where = holder_by_name(doc, holder), f"панели «{holder}»"
    from .pages import page_number
    try:
        page = page_number(target, page, where)
    except EditError as e:
        raise EditError(f"set_tab_order: {e}") from None
    pages = pages_count(target)
    if (pages is None and page) or (pages is not None and not 0 <= page < pages):
        raise EditError(f"set_tab_order: страницы {page} у {where} нет" + (f": страниц {pages} (счёт с нуля)" if pages is not None else " — страниц не бывает вовсе"))
    group = _page_group(target, page)
    if not group:
        raise EditError(f"set_tab_order: на странице {page} {where} нет элементов")
    auto = auto_tab_order(target)
    if auto and not unverified:
        raise EditError(f"set_tab_order: у {where} включён АвтоПорядокОбхода — платформа ведёт порядок по положению элементов, а конфигуратор при нём "
                        "отказывает («Невозможно изменить порядок, так как установлено свойство автопорядок обхода»); сначала `set_property` "
                        "`auto_tab_order` = false у этого родителя (form=true, если это форма), либо unverified — номера запишутся, но платформа может "
                        "пересчитать их по положению")
    current = sorted(group, key=lambda item: (_number(item), item.get("index") if isinstance(item.get("index"), int) else 0))
    if order is not None:
        chosen = []
        for name in order:
            found = [item for item in group if name_of(item) == name]
            if not found:
                others = [name_of(item) for item in current if name_of(item)]
                raise EditError(f"set_tab_order: элемента {name!r} нет среди элементов {where} на странице {page}; там: {', '.join(others)}")
            if len(found) > 1:
                raise EditError(f"set_tab_order: имя {name!r} носят {len(found)} элемента этого родителя — по имени не решить; переименуйте один (`rename_element`)")
            if any(found[0] is item for item in chosen):
                raise EditError(f"set_tab_order: элемент {name!r} назван в order дважды")
            chosen.append(found[0])
    else:
        chosen = _reading(doc, group)
        if not chosen:
            raise EditError(f"set_tab_order: на странице {page} {where} нет элементов, принимающих фокус, — порядок чтения ставить некому")
    slots = [at for at, item in enumerate(current) if any(item is c for c in chosen)]
    final = list(current)
    for at, item in zip(slots, chosen):
        final[at] = item
    from . import elements as ee
    was = {id(item): _number(item) for item in group}
    for number, item in enumerate(final, 1):
        item[ee.COORDS][ee.TAB_ORDER] = number
    changed = [(item, was[id(item)], number) for number, item in enumerate(final, 1) if was[id(item)] != number]
    tail = "; у родителя включён АвтоПорядокОбхода, платформа может пересчитать номера по положению (unverified)" if auto else ""
    if not changed:
        return f"порядок обхода {where}, страница {page}: уже в этом порядке; номера 1…{len(final)}{tail}"
    shown = "; ".join(f"«{name_of(item) or item.get('index')}» {old or '—'} → {new}" for item, old, new in changed[:40])
    more = f"; и ещё {len(changed) - 40}" if len(changed) > 40 else ""
    return (f"порядок обхода {where}, страница {page}: номера заново 1…{len(final)}, изменились у {len(changed)} из {len(final)} (было → стало): {shown}{more}; "
            "как пойдёт Tab в предприятии по этой записи, платформа не проверяла" + tail)
