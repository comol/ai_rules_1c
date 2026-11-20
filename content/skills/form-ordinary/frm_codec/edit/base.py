"""Навигация по документу, значения, локализованная строка, родитель элемента и исключение `EditError`. Все имена доступны через
фасад `frm_codec.edit`. Родитель элемента — это форма или панель, на которой он лежит.
"""

import copy
import types

from .. import lstring, schema

from .names import (
    ACTIONS,
    ACTION_ID,
    BTN_NAME,
    BTN_TEXT,
    BUTTONS,
    BUTTON_ID,
    BUTTON_SETS,
    CAPTION,
    CONTENT,
    COORDS,
    CORPUS_STAMP,
    DEFAULT_CONTROL,
    DESC_BIT,
    ELEMENTS,
    EXTRAS,
    GUIDES,
    GUIDE_COORD,
    GUIDE_ORDER,
    GUIDE_PAGE,
    INDEX,
    ITEMS,
    LANG,
    LAYOUT_LISTS,
    LS_COUNT,
    LS_ITEMS,
    LS_MARK,
    MENU,
    MENU_MODE,
    NAME,
    NAME_BLOCK,
    NO_REFERENCE,
    ON_CORPUS,
    ON_CORPUS_NOTE,
    PAGE,
    PAGES,
    PAGE_ITEMS,
    SEPARATE_BY_PAGE,
    SHOW_TABS,
    PAGE_SEQUENCE,
    TEXT,
    TOOL_TIP,
    UNSEEN_NOTE,
    _maybe,
)


def _on_corpus(variant, what, seen, counted="таких"):
    """Хвост отчёта для вызова шире проверенного. Пометка ставится только здесь.

    Параметр `seen` — число встреч именно этого случая среди образцов форм (в отчёт не попадает). `None` означает, что случай не встретился
    ни разу. Фраза «стоит на корпусе» говорит, что платформа сама пишет такую форму, а «не встретилось ни разу» — что подтверждения нет. Если
    вызов может привести ко второму, операция по умолчанию отказывает, и сюда доходит только вызов с `unverified=True`. Это
    привязка к элементу неизвестного вида и пара «тип + событие», которой в образцах нет.

    Единственное исключение — `set_font/value`: имя шрифта и размер приходят с `None` без отказа, потому что имя ставит система,
    а не файл. Отказывают только две границы формы записи: чей это шрифт и сочетание «вид записи + маска».

    Параметр `counted` только называет, что считали; число и название в отчёт не попадают.
    """
    if seen is None:
        return (f"; {what}: {UNSEEN_NOTE}; "
                + ON_CORPUS[variant])
    return f"; {what}: {ON_CORPUS_NOTE}; {ON_CORPUS[variant]}"


class EditError(ValueError):
    """Отказ операции: что не так и что сделать. Класс наследует `ValueError`, как и все названные отказы кодека, поэтому команда
    командной строки ловит их одним обработчиком.
    """


# Локализованная строка

def localized(text, lang="ru"):
    """Локализованная строка из одного текста."""
    return {LS_MARK: 1, LS_COUNT: 1, LS_ITEMS: [{LANG: lang, TEXT: text}]}


def set_text(block, text):
    """Переписывает видимый текст локализованной строки на месте. Видимый член выбирает `lstring.visible_member` (у строки
    `{"#","Надпись"},{"ru","Касса/Счет:"}` платформа показывает `ru`, опыт T108); остальные члены остаются как были, поэтому строка
    не теряет языков. Строка без членов получает один член `ru`. Какой член переписан, называет `rewritten_note` (сразу после вызова).
    """
    member = lstring.visible_member(block)
    if member is None:
        block.clear()
        block.update(localized(text))
        _LAST[0] = (None, 0)
        return block
    member[TEXT] = text
    _LAST[0] = (member.get(LANG), len(block.get(LS_ITEMS) or []))
    return block


_LAST = [(None, 0)]


def rewritten_note():
    """Слова для отчёта операции: какой член многоязычной строки переписала последняя `set_text`; у строки из одного члена — пусто."""
    lang, count = _LAST[0]
    if count < 2:
        return ""
    return f"; у строки на {count} языках переписан член «{lang}» (видимый в предприятии), остальные оставлены как были"


# Навигация

def name_of(item):
    """Имя элемента из его блока имени. Если узел не является записью или имени нет, возвращается `None`."""
    block = item.get(NAME_BLOCK) if isinstance(item, dict) else None
    name = block.get(NAME) if isinstance(block, dict) else None
    return name if isinstance(name, str) else None


class Place:
    """Найденный элемент и всё, что нужно для его правки. Поле `holder` — родитель (контейнер формы или элемент-панель), `items` —
    список родителя, в котором лежит элемент, `at` — место элемента в списке. Счётчик списка, число страниц и порядок обхода
    считаются в пределах родителя, а не всей формы.
    """

    __slots__ = ("element", "holder", "items", "at", "path")

    def __init__(self, element, holder, items, at, path):
        self.element, self.holder, self.items, self.at, self.path = \
            element, holder, items, at, path

    @property
    def index(self):
        return self.element.get(INDEX)

    @property
    def name(self):
        return name_of(self.element)

    @property
    def page(self):
        coords = self.element.get(COORDS)
        return coords.get(PAGE) if isinstance(coords, dict) else None


def container(doc):
    """Контейнер формы — родитель верхнего уровня. Если форма не разобрана, операция отказывает с пояснением."""
    block = doc.get("form")
    node = block.get("container") if isinstance(block, dict) else None
    if not isinstance(node, dict) or not isinstance(node.get(ELEMENTS), dict):
        raise EditError("в документе нет контейнера формы со списком элементов — "
                        "это либо уровень 0 (сырое дерево), либо форма, которую карта не "
                        "разобрала; править нечего")
    return node


def holders(doc):
    """Список `[(имя родителя или None, узел)]`: контейнер формы и каждый элемент со вложенными. Родителем считается любой узел со
    списком элементов, в том числе панель внутри панели.
    """
    out = []

    def walk(node, name):
        out.append((name, node))
        holder = node.get(ELEMENTS)
        for item in (holder.get(ITEMS) or []) if isinstance(holder, dict) else []:
            if isinstance(item, dict):
                walk(item, name_of(item))

    walk(container(doc), None)
    return out


def holder_by_name(doc, name):
    """Родитель по имени; `None` означает контейнер формы. Если родителя нет, отказ перечисляет родителей со страницами."""
    if name is None:
        return container(doc)
    found = [node for holder_name, node in holders(doc) if holder_name == name]
    if not found:
        known = ", ".join(sorted(n for n, node in holders(doc)[1:] if n)) or "—"
        raise EditError(f"родителя {name!r} в форме нет. Элементы принимают: {known}. "
                        "Если родитель не указан, элемент кладётся прямо на форму.")
    if len(found) > 1:
        raise EditError(f"имя {name!r} носят {len(found)} узла, и по имени нельзя понять, какой из них родитель. "
                        "Переименуйте один из них (`rename_element`).")
    return found[0]


def elements_of(holder):
    """Список элементов родителя (массив `items`). Если у родителя его нет, операция отказывает."""
    block = holder.get(ELEMENTS)
    if not isinstance(block, dict) or not isinstance(block.get(ITEMS), list):
        raise EditError("У этого родителя нет разобранного списка элементов, поэтому вкладывать в него нечего.")
    return block[ITEMS]


def find_element(doc, name):
    """Элемент по имени на любой глубине. Если такого нет, отказ приводит список имён."""
    found = []
    for holder_name, holder in holders(doc):
        block = holder.get(ELEMENTS)
        items = block.get(ITEMS) if isinstance(block, dict) else None
        for at, item in enumerate(items or []):
            if isinstance(item, dict) and name_of(item) == name:
                found.append(Place(item, holder, items, at,
                                   (holder_name + "/" + name) if holder_name else name))
    if not found:
        raise EditError(f"элемента {name!r} в форме нет. Есть: {', '.join(element_names(doc))}")
    if len(found) > 1:
        # Имя элемента уникально на верхнем уровне, а внутри панелей повторяется. Поэтому повтор — это отказ операции, а не проверки:
        # по имени нельзя решить, какой из двух элементов править. Операция ищет по всей форме.
        where = ", ".join(place.path for place in found)
        raise EditError(f"имя {name!r} носят {len(found)} элемента ({where}) — какой из них "
                        "править, по имени не решить; переименуйте один (`rename_element`)")
    return found[0]


def element_names(doc):
    """Имена всех элементов формы сверху вниз в порядке списков."""
    out = []
    for _holder_name, holder in holders(doc):
        block = holder.get(ELEMENTS)
        for item in (block.get(ITEMS) or []) if isinstance(block, dict) else []:
            name = name_of(item)
            if isinstance(name, str):
                out.append(name)
    return out


def tree(doc):
    """Дерево элементов в виде строк: отступ, индекс, тип, имя, страница и порядок обхода. Правка начинается отсюда: имя элемента
    берётся из этого дерева.
    """
    lines = []

    def walk(items, depth):
        for item in items or []:
            if not isinstance(item, dict):
                lines.append("  " * depth + "(узел не разобран)")
                continue
            coords = item.get(COORDS) if isinstance(item.get(COORDS), dict) else {}
            lines.append("  " * depth + f"#{item.get(INDEX)} {item.get('type')} "
                         f"{(item.get(NAME_BLOCK) or {}).get(NAME)!r} "
                         f"{PAGE}={coords.get(PAGE)} {PAGE_SEQUENCE}={coords.get(PAGE_SEQUENCE)}")
            block = item.get(ELEMENTS)
            walk(block.get(ITEMS) if isinstance(block, dict) else None, depth + 1)

    walk(elements_of(container(doc)), 0)
    return lines


def _bars(doc):
    """Блоки действий командных панелей вместе с именем панели. Блок находится по строению, а не по адресу: он узнаётся по паре
    ключей `actions` и `button_sets`, как в `meaning._bars`. Так он находится и у панели внутри панели, и у формы любого строения.
    """
    def walk(value, name):
        if isinstance(value, dict):
            here = (value.get(NAME_BLOCK) or {}).get(NAME) or name
            if ACTIONS in value and BUTTON_SETS in value:
                yield here, value
            for item in value.values():
                yield from walk(item, here)
        elif isinstance(value, list):
            for item in value:
                yield from walk(item, name)

    yield from walk(doc, None)


def find_bar(doc, bar):
    """Блок действий панели по её имени. По нему же находится меню кнопки: меню — это такой же узел `CommandBarActions`, как у
    панели, и он лежит в теле записи кнопки. Поэтому параметр `bar` содержит либо имя командной панели, либо имя кнопки-меню, и
    все операции над кнопками работают в обоих случаях.
    """
    found = [block for name, block in _bars(doc) if name == bar]
    if not found:
        known = ", ".join(sorted({name for name, _block in _bars(doc) if name})) or "—"
        raise EditError(f"командной панели {bar!r} в форме нет; есть: {known} (кнопка-меню "
                        "тоже годится — её меню это тот же блок действий, что у панели; "
                        "завести меню кнопке можно операцией set_menu_mode)")
    if len(found) > 1:
        raise EditError(f"имя {bar!r} носят {len(found)} панели — какую из них править, "
                        "по имени не решить")
    return found[0]


def find_button(doc, bar, name):
    """Возвращает `(блок действий, набор, кнопка, запись действия)` по имени кнопки. Запись действия ищется по GUID: на ней у кнопки
    держатся подсказка, пояснение, картинка и сочетание клавиш. Если записи нет, операция отказывает, а не возвращает `None`.
    """
    block = find_bar(doc, bar)
    found = []
    for button_set in block.get(BUTTON_SETS) or []:
        for button in (button_set.get(BUTTONS) or []) if isinstance(button_set, dict) else []:
            if isinstance(button, dict) and button.get(BTN_NAME) == name:
                found.append((button_set, button))
    if not found:
        known = ", ".join(button.get(BTN_NAME) for _s, button in _buttons(block))
        raise EditError(f"кнопки {name!r} в панели {bar!r} нет; есть: {known or '—'}")
    if len(found) > 1:
        raise EditError(f"в панели {bar!r} кнопок с именем {name!r} — {len(found)}; "
                        "имя кнопки внутри набора уникальным не объявлено ничем, и какую из "
                        "них править, по имени не решить")
    button_set, button = found[0]
    return block, button_set, button, _action_of(block, button, bar, name)


def _buttons(block):
    """Список `[(набор, кнопка)]` по всем наборам блока действий в порядке файла."""
    out = []
    for button_set in block.get(BUTTON_SETS) or []:
        if isinstance(button_set, dict):
            out += [(button_set, button) for button in button_set.get(BUTTONS) or []
                    if isinstance(button, dict)]
    return out


def _action_of(block, button, bar, name):
    guid = (button.get(BUTTON_ID) or {}).get("guid")
    for action in block.get(ACTIONS) or []:
        if isinstance(action, dict) and (action.get(ACTION_ID) or {}).get("guid") == guid:
            return action
    raise EditError(f"у кнопки {name!r} панели {bar!r} нет записи действия (id {guid}); "
                    "подсказка, пояснение, картинка и сочетание клавиш кнопки лежат именно "
                    "там, и взять их больше неоткуда — форму надо чинить, а не править")


# Значения

def set_form_title(doc, text):
    """Заголовок формы. Автоматический заголовок (`АвтоЗаголовок`) поверх заданного не подставляется."""
    block = doc.get("form")
    title = block.get("title") if isinstance(block, dict) else None
    caption = title.get(CAPTION) if isinstance(title, dict) else None
    if not isinstance(caption, dict):
        raise EditError("у формы нет разобранного блока заголовка — заголовок правится в нём")
    set_text(caption, text)
    return f"заголовок формы → {text!r}" + rewritten_note()


def _caption_places(node, trail=()):
    """Заголовки самого элемента. Обход спускается только в словари и не заходит в списки: заголовки страниц панели, колонок,
    кнопок и вложенных элементов лежат в счётных списках (`{count, items: […]}`) и принадлежат другим элементам.
    """
    for key, value in node.items() if isinstance(node, dict) else ():
        if key == CAPTION and isinstance(value, dict) and LS_ITEMS in value:
            yield trail + (key,), value
        elif isinstance(value, dict):
            yield from _caption_places(value, trail + (key,))


def caption_slot(node, element):
    """Единственный заголовок элемента-узла (его блок `caption`). Если заголовка нет или их несколько, операция отказывает с
    пояснением. Функция вынесена, чтобы `add_element` мог проверить заголовок до раздвигания рядов.
    """
    found = list(_caption_places(node.get(CONTENT) or {}))
    if not found:
        raise EditError(f"у элемента {element!r} ({node.get('type')}) заголовка нет — "
                        f"поле {CAPTION!r} в его содержимом не встречается")
    if len(found) > 1:
        where = ", ".join("/".join(part) for part, _value in found)
        raise EditError(f"у элемента {element!r} заголовков несколько ({where}) — какой из них "
                        "ваш, карта не различает; правьте JSON по адресу")
    return found[0][1]


# `[True]` на время перечня операций, который проверяет подписи в конце (`edit.ops.apply(..., final_captions=True)`).
DEFER_FIT = [False]


def set_caption(doc, element, text):
    """Заголовок элемента (надпись, кнопка, флажок, рамка группы и т. д.). Адрес заголовка зависит от типа элемента: у кнопки это
    `content/u1/caption`, у флажка `content/u1/u0/caption`. Поэтому заголовок ищется по имени из карты внутри содержимого, а при
    неудаче отказ приводит список найденного.
    """
    from . import font
    place = find_element(doc, element)
    slot = caption_slot(place.element, element)
    set_text(slot, text)
    if DEFER_FIT[0]:
        # Перечень операций проверяет подписи один раз, по итоговой форме (`edit.final.caption_lines`): ширину и зазор могут поменять следующие операции.
        return f"{element}: заголовок → {text!r}" + rewritten_note()
    fit = font.node_fit(doc, place.element)
    return f"{element}: заголовок → {text!r}" + rewritten_note() + font.new_text_words(fit)


def set_button_text(doc, bar, button, text):
    """Текст кнопки панели. Он лежит в самой кнопке и не совпадает с её именем: то, что видно на панели, и то, что вызывается в
    коде, — разные строки.
    """
    _block, _set, node, _action = find_button(doc, bar, button)
    if not isinstance(node.get(BTN_TEXT), dict):
        node[BTN_TEXT] = localized(text)
        _LAST[0] = (None, 0)
    else:
        set_text(node[BTN_TEXT], text)
    return f"{bar}/{button}: текст → {text!r}" + rewritten_note()


def _set_extra(doc, bar, button, bit, text):
    """Блок записи действия, который стоит по своему биту: подсказка или пояснение. Слово флагов не бывает полем JSON, потому что
    оно равно набору ключей, и его собирает `encode`. Порядок ключей задан картой (`Flagged.bits`).
    """
    _block, _set, _node, action = find_button(doc, bar, button)
    extras = dict(action.get(EXTRAS) or {})
    if isinstance(extras.get(bit), dict) and LS_ITEMS in extras[bit]:
        set_text(extras[bit], text)
    else:
        extras[bit] = localized(text)
    action[EXTRAS] = _order_extras(extras)
    return extras[bit]


def _order_extras(extras):
    """Ключи блоков по биту в порядке карты. Если ключ неизвестен, операция отказывает и приводит список известных ключей."""
    bits = _extras_bits()
    unknown = [key for key in extras if key not in bits]
    if unknown:
        raise EditError(f"в блоках записи действия нет ключей {', '.join(sorted(unknown))}; "
                        f"карта знает {', '.join(bits)}")
    return {key: extras[key] for key in bits if key in extras}


def _extras_bits():
    for segment in schema.MAP["CommandBarAction"].runs.segments:
        if isinstance(segment, schema.Flagged):
            return list(segment.bits)
    raise schema.SchemaError("у записи действия пропал отрезок по битам")


def set_tool_tip(doc, bar, button, text):
    """Подсказка кнопки панели. Это блок по биту 2 записи действия, а не поле самой кнопки. У пункта меню палитра подсказку
    показывает, а всплывающая подсказка в 1С:Предприятии не проявилась.
    """
    _set_extra(doc, bar, button, TOOL_TIP, text)
    return f"{bar}/{button}: подсказка → {text!r}" + _menu_extra_note(doc, bar, TOOL_TIP)


def set_description(doc, bar, button, text):
    """Пояснение кнопки панели. Это блок по биту 4 той же записи. У пункта меню пояснение выводится в строке состояния."""
    _set_extra(doc, bar, button, DESC_BIT, text)
    return f"{bar}/{button}: пояснение → {text!r}" + _menu_extra_note(doc, bar, DESC_BIT)


# Родитель: страницы, направляющие, списки

def layout_block(holder, need=True):
    """Блок раскладки родителя, в котором лежат страницы, направляющие и шесть списков. У контейнера формы он лежит через
    `layout_holder/layout_list`, у панели — внутри блока содержимого под позицией без имени. Он ищется по имени из карты
    (`pages`), а не по адресу, как и в `validate._pages_of`.

    При `need=False` результат `None` допустим. Причин две: у поля табличного документа страниц нет вовсе, а у части панелей
    карта блок раскладки не разбирает.
    """
    found = _find_pages(holder)
    if found is None and need:
        raise EditError("У этого родителя не разобран блок раскладки, поэтому страницы и направляющие в нём не видны.")
    return found


def _find_pages(value, depth=3):
    if not isinstance(value, dict) or depth < 0:
        return None
    holder = value.get(PAGES)
    if isinstance(holder, dict) and isinstance(holder.get(PAGE_ITEMS), list):
        return value
    for inner in value.values():
        if isinstance(inner, dict):
            found = _find_pages(inner, depth - 1)
            if found is not None:
                return found
    return None


def pages_of(holder):
    """Список страниц родителя."""
    return layout_block(holder)[PAGES][PAGE_ITEMS]


def pages_count(holder):
    """Число страниц родителя. `None` означает, что страниц у такого родителя не бывает. Ответ совпадает с ответом проверки
    (`validate._pages_of`).
    """
    block = layout_block(holder, need=False)
    return None if block is None else len(block[PAGES][PAGE_ITEMS])


def no_pages_words(holder):
    """Почему у родителя не видно страниц: у панели, чей блок раскладки лежит сырым, страницы есть, но их не видно; у прочих их не бывает."""
    content = holder.get(CONTENT) if isinstance(holder, dict) and holder.get("type") == "Panel" else None
    if isinstance(content, dict) and any(isinstance(v, dict) and set(v) == {"raw"} for v in content.values()):
        return ("страницы у этой панели есть, но её блок раскладки лежит сырым (разбор не узнал его строения, `validate` называет причину), "
                "и страниц редактор не видит")
    return "страниц не бывает вовсе"


def _guide_pattern(block):
    """Четыре направляющие первой страницы как образец, выбранные по номерам 1…4. Нельзя брать первые четыре в списке, потому что
    человек мог добавить свои направляющие.
    """
    guides = block.get(GUIDES)
    if not isinstance(guides, list):
        raise EditError("У родителя не разобран список направляющих.")
    first = min((g.get(GUIDE_PAGE) for g in guides if isinstance(g, dict)), default=None)
    pattern = {}
    for guide in guides:
        if isinstance(guide, dict) and guide.get(GUIDE_PAGE) == first \
                and guide.get(GUIDE_ORDER) in (1, 2, 3, 4):
            pattern.setdefault(guide[GUIDE_ORDER], guide)
    if sorted(pattern) != [1, 2, 3, 4]:
        raise EditError("Направляющие первой страницы не опознаны: ожидались четыре с номерами "
                        f"1…4, найдены {sorted(pattern)}. Образца для новой страницы нет, "
                        "а придумывать направляющие нельзя.")
    return pattern


# Направляющие новой страницы по положению закладок. Правая и нижняя направляющие страницы несут край области страницы: координата плюс отступ
# (позиция 7 записи) равна размеру панели минус вычет. Вычеты — область страницы, снятая в предприятии (`layout.area`, раздел «Закладки панели»
# в `docs/layout.md`), и они же держат направляющие страниц в корпусе (`docs/edit-rules.md`). Отступ берётся у первой
# страницы: у стандартной четвёрки он 6, и тогда правая направляющая равна ширине минус 8, нижняя при «Сверху» — высоте минус 26.
GUIDE_OFFSET_KEY = _maybe("Guide", 7)
# `measured` — запись платформы проверена в предприятии; `corpus` — вычет держит корпус, в предприятии положение не проверялось; `open` — формула от области,
# корпус её не держит или почти не видел: без `unverified` операция отказывает. Таблица меняется только по проверке в предприятии.
GUIDE_LEVEL_MEASURED, GUIDE_LEVEL_CORPUS, GUIDE_LEVEL_OPEN = "measured", "corpus", "open"
GUIDE_STRIP, GUIDE_STRIP_PICTURE = 20, 22   # вычет по высоте при закладках сверху/снизу: полоса 18 + 2; с картинкой у закладки 20 + 2
GUIDE_SIDE_CUT = (22, 2)                    # вертикальные закладки: полоса 20 px и линия 2 (так записано у всех панелей корпуса)
# Проверено в предприятии (панели 300x160, три страницы без картинок, подписи до «Страница1», один ряд закладок) подтвердил край всех положений, кроме кода 13.
GUIDE_LEVELS = {
    "Top": GUIDE_LEVEL_MEASURED, "TopScrolling": GUIDE_LEVEL_MEASURED, "DontUse": GUIDE_LEVEL_MEASURED,
    "Bottom": GUIDE_LEVEL_MEASURED, "BottomScrolling": GUIDE_LEVEL_MEASURED,
    "LeftVertical": GUIDE_LEVEL_MEASURED, "RightVertical": GUIDE_LEVEL_MEASURED,
    "LeftHorizontal": GUIDE_LEVEL_MEASURED, "RightHorizontal": GUIDE_LEVEL_MEASURED,
    "TopMultiLine": GUIDE_LEVEL_MEASURED, "TopMultilineTransposition": GUIDE_LEVEL_MEASURED,
    "BottomMultiLine": GUIDE_LEVEL_MEASURED, "BottomMultilineTransposition": GUIDE_LEVEL_MEASURED,
}


def _guide_cut(node, block, doc, width, height):
    """`((вычет по ширине, вычет по высоте), уровень, слова)` для панели с закладками `block[SHOW_TABS]`. Положение, для которого формулы нет, — отказ
    словами. Для рядов закладок «в несколько строк» и столбца «Слева/Справа (горизонтально)» область зависит от подписей закладок, и без
    измеренной ширины подписи вычет не считается.
    """
    from ..layout import area as _area
    tabs = block.get(SHOW_TABS)
    pictures = any(_area.tab_pictures(node))
    owner = types.SimpleNamespace(node=node, box=(0, 0, width, height))
    if tabs in ("Top", "TopScrolling", "Bottom", "BottomScrolling"):
        cut = (2, GUIDE_STRIP_PICTURE if pictures else GUIDE_STRIP)
        level = GUIDE_LEVELS[tabs]
        if pictures:
            # с картинкой у закладки в предприятии положение не проверялось; «Сверху» держит корпус
            level = GUIDE_LEVEL_CORPUS if tabs in ("Top", "TopScrolling") else GUIDE_LEVEL_OPEN
        return cut, level, ""
    if tabs == "DontUse":
        return (0, 0), GUIDE_LEVELS["DontUse"], ""
    if tabs in _area.VERTICAL_KINDS:
        return GUIDE_SIDE_CUT, (GUIDE_LEVEL_OPEN if pictures else GUIDE_LEVELS[tabs]), ""
    if tabs in _area.SIDE_KINDS:
        strip = _area.left_strip(doc, owner, width)
        if strip is None:
            raise EditError(f"закладки {tabs!r}: ширина подписи не измерена (шрифт или знаки не из проверенных), поэтому край страницы не считается; "
                            "unverified этого отказа не снимает")
        return (strip + 1, 2), (GUIDE_LEVEL_OPEN if pictures else GUIDE_LEVELS[tabs]), ""
    if tabs in _area.ROWS_TOP or tabs in _area.ROWS_BOTTOM:
        frame, why = _area.panel_frame(doc, owner, (width, height))
        if frame is None:
            raise EditError(f"закладки {tabs!r}: {why or 'ряды закладок не посчитаны'}; unverified этого отказа не снимает")
        cut = (width - (frame[2] - 2), height - (frame[3] - 2))
        # снят один ряд закладок без картинок (вычет по высоте 20); несколько рядов и картинки в предприятии не проверялись
        return cut, (GUIDE_LEVELS[tabs] if cut[1] <= GUIDE_STRIP and not pictures else GUIDE_LEVEL_OPEN), ""
    if tabs == 13:
        return (2, GUIDE_STRIP), GUIDE_LEVEL_OPEN, ("код 13 («Прокручиваемые страницы»): заголовки страниц идут друг под другом, "
                                                    "полоса прокрутки занимает 16 px ширины, нижний край не измерен; корпус записывает нижний край "
                                                    "по-разному (H−20, H−19, H+8), взят H−20")
    raise EditError(f"ОтображениеЗакладок {tabs!r}: для такого положения край страницы не известен, операция отказывает; unverified этого отказа не снимает")


def _make_guides(block, pattern, page, width, height, node=None, doc=None, unverified=False, words=None):
    """Четыре направляющие одной страницы: образец, номер страницы и размер. Левая и верхняя остаются прежними (как у первой страницы), правая и
    нижняя несут край области страницы данного положения закладок (`_guide_cut`): координата равна размеру минус вычет минус отступ из образца.
    Платформа при добавлении страницы «Сверху» пишет правую равной ширине минус 8, нижнюю — высоте минус 26; это тот же вычет (2, 20) при
    отступе 6. Положения, где корпус формулы не держит или почти не видел, без `unverified` отказывают (`GUIDE_LEVEL_OPEN`).
    """
    if node is None:
        tabs = block.get(SHOW_TABS)
        if tabs != "Top":
            raise EditError(f"Направляющие новой страницы без панели считаются только при закладках сверху ({SHOW_TABS} = 'Top'), а здесь {tabs!r}.")
        cut, level, note = (2, GUIDE_STRIP), GUIDE_LEVEL_MEASURED, ""
    else:
        cut, level, note = _guide_cut(node, block, doc, width, height)
    if level == GUIDE_LEVEL_OPEN and not unverified:
        raise EditError(f"Направляющие новой страницы при ОтображенииЗакладок {block.get(SHOW_TABS)!r}: край страницы (ширина − {cut[0]}, высота − {cut[1]}) "
                        "получен от области страницы и корпус его не подтверждает; в предприятии положение не проверялось. "
                        "Позвать всё же можно с unverified=True: операция выполнится, а исход не проверялся")
    if words is not None:
        words.append(f"направляющие новой страницы: край (ширина − {cut[0]}, высота − {cut[1]})" + {
            GUIDE_LEVEL_MEASURED: " — как пишет платформа",
            GUIDE_LEVEL_CORPUS: " — по корпусу, в предприятии не проверялось",
            GUIDE_LEVEL_OPEN: " — не проверялось (формула от области страницы)"}[level] + (f"; {note}" if note else ""))
    out = []
    for order in (1, 2, 3, 4):
        guide = copy.deepcopy(pattern[order])
        guide[GUIDE_PAGE] = page
        out.append(guide)
    for at, size, deduct in ((2, width, cut[0]), (3, height, cut[1])):
        offset = out[at].get(GUIDE_OFFSET_KEY)
        offset = offset if isinstance(offset, int) else 0
        out[at][GUIDE_COORD] = size - deduct - offset
    return out


def _fit_guides(node, width, height, doc=None, unverified=False):
    """Перестраивает направляющие всех страниц под размер родителя. Вызывается, когда родитель получен из шаблона: его направляющие
    несут размер исходной формы. Операции `add_page` и `remove_page` соседние страницы не трогают, потому что направляющих на
    странице может быть больше четырёх (их добавил человек).
    """
    block = layout_block(node)
    pattern = _guide_pattern(block)
    pages = len(pages_of(node))
    out = []
    for page in range(pages):
        out += _make_guides(block, pattern, page, width, height, node=node, doc=doc, unverified=unverified)
    block[GUIDES] = out
    # по числу `АктивизироватьПоУмолчанию` на страницу, а без «Распределять по страницам» — одно на родитель
    current = block.get(DEFAULT_CONTROL)
    if isinstance(current, list):
        wanted = min(pages, 1) if one_default_control(block) else pages
        block[DEFAULT_CONTROL] = (current + [NO_REFERENCE] * wanted)[:wanted]
    return pages


def one_default_control(block):
    """`True`, если «АктивизироватьПоУмолчанию» родителя — одно число на весь родитель: так платформа пишет его без «Распределять по
    страницам» (`separate_by_page`), сколько бы ни было страниц. Иначе — по числу на страницу."""
    return isinstance(block, dict) and block.get(SEPARATE_BY_PAGE) is False


def control_slot(block, page):
    """Место элемента со страницы `page` в списке «АктивизироватьПоУмолчанию» родителя: номер страницы, а у родителя без «Распределять по
    страницам» — единственное число."""
    return 0 if one_default_control(block) else page


def _layout_rows(holder):
    """Шесть списков родителя, в которых у элементов есть строки. Позицию, называющую элемент, задаёт `LayoutRun/element`; имя поля
    берётся у привязок (`anchors.ROW_ELEMENT`). Строки удалённого элемента убираются, платформа при пересохранении пишет списки
    так же.
    """
    block = layout_block(holder, need=False)
    return {} if block is None else \
        {name: block[name] for name in LAYOUT_LISTS if isinstance(block.get(name), list)}


def _panel_pages(doc, panel):
    """Блок раскладки панели по имени. Если блока нет, отказ называет тип элемента."""
    place = find_element(doc, panel)
    block = layout_block(place.element, need=False)
    if block is None:
        if no_pages_words(place.element) != "страниц не бывает вовсе":
            raise EditError(f"у элемента {panel!r}: {no_pages_words(place.element)}")
        raise EditError(f"у элемента {panel!r} ({place.element.get('type')}) страниц не бывает "
                        "— страницы бывают у панели и у контейнера формы")
    return place, block


def _menu_blocks(doc):
    """Блоки действий, которые лежат в меню кнопки: `{id(блока)}`. Они нужны для отчёта: кнопка в меню — это вызов шире
    проверенного, потому что проверялась кнопка в командной панели. Блок у панели и блок у меню — один и тот же узел, поэтому
    сравнение идёт по `id`.
    """
    out = set()

    def walk(value):
        if isinstance(value, dict):
            block = value.get(MENU)
            if MENU_MODE in value and isinstance(block, dict):
                out.add(id(block))
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(doc)
    return out


# Пояснение пункта меню платформа показала в строке состояния. Подсказку палитра показала, а всплывающая подсказка в
# предприятии не проявилась. Это означает «не наблюдалось», а не «не работает».
ROUND8_MENU_EXTRAS = {
    TOOL_TIP: "подсказка пункта меню записана и показана в палитре, но всплывающая подсказка в "
              "1С:Предприятии не появилась; работает ли она у пункта меню, не установлено",
    DESC_BIT: "пояснение пункта меню проверено в 1С:Предприятии: оно выводится в строке "
              "состояния, пока пункт выделен",
}


def _menu_extra_note(doc, bar, bit):
    """Хвост отчёта о подсказке или пояснении, если кнопка — пункт меню."""
    if id(find_bar(doc, bar)) not in _menu_blocks(doc):
        return ""
    return f"; {ROUND8_MENU_EXTRAS[bit]}"
