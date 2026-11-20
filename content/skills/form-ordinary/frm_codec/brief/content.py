"""Содержимое формы для досье: колонки таблиц, кнопки командных панелей, закладки панелей, группы переключателей, свойства элементов.

Всё это в структуре досье (`structure.recognize`) не видно: таблица там одна строка, панель команд — одна строка с пустой надписью.
Здесь они читаются из самих элементов:

* `table_columns` — колонки табличного поля: имя, заголовок, данные, тип значения, ширина, видимость, вложенный элемент;
* `bar_buttons` — кнопки командной панели с подменю (вложенность), действием (процедура модуля или стандартное действие) и доступностью;
* `strip_hidden` — панели и страницы формы с видом закладок «Не отображать»: страницы переключает код, закладок на экране нет;
* `radio_groups` — группы переключателей: данные и значение несёт первый переключатель группы;
* `element_marks` — свойства, нужные для разбора удобства: только просмотр, многострочность, пароль, подсказка (текст — у элемента без надписи; у остальных число в сводке), кнопки выбора и очистки.

Форму модуль не меняет и ничего, чего в файле нет, не додумывает: чего прочитать нельзя — поле пусто или слово «не определено».
"""
import collections

from .. import bar_platform, lstring, describe, render, schema, shell
from ..edit import base as ed_base, buttons as ed_buttons, columns as ed_columns, datapath as ed_datapath, platform as ed_platform, submenu as ed_submenu, names as N

SKIP_MARK = "пропускается при переходе клавишей Enter; Tab на него переходит"     # флаг «пропускать при вводе»: Tab — наблюдение в предприятии (поле «Фирма»), Enter не проверялся
TYPE_LETTERS = {"S": "строка", "N": "число", "D": "дата", "B": "булево", "#": "ссылка"}
CONTROL_WORDS = {"CheckBox": "флажок", "ComboBox": "поле выбора", "TextBox": "поле ввода", "PictureBox": "картинка", "Button": "кнопка",
                 "RadioButton": "переключатель"}
STANDARD_WORDS = bar_platform.ACTION_TEXT      # названия стандартных действий: палитра и наблюдения предприятия (`bar_platform`)
MENU_DEPTH = 6          # вложенность подменю глубже не читается: у настоящих форм она один-два уровня


def _int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _text_of(value):
    """Видимый текст списка строк на языках (`LocalizedString`, `lstring`) либо пустая строка."""
    text = lstring.visible_text(value)
    return text.strip() if text is not None else ""


def own_blocks(node):
    """Блоки действий командных панелей и меню самого элемента (вложенные элементы не читаются)."""
    def walk(value):
        if isinstance(value, dict):
            if N.ACTIONS in value and N.BUTTON_SETS in value:
                yield value
            for key, item in value.items():
                if key != N.ELEMENTS:
                    yield from walk(item)
        elif isinstance(value, list):
            for item in value:
                yield from walk(item)
    return list(walk(node))


# ── Колонки таблиц ──

def _value_type(vt):
    types = vt.get("types") if isinstance(vt, dict) else None
    out = []
    for block in types if isinstance(types, list) else ():
        if not isinstance(block, dict):
            continue
        kind = block.get(N.PATTERN_KIND)
        word = TYPE_LETTERS.get(kind)
        if word is None:
            continue
        if kind == "S" and _int(block.get(N.PATTERN_LENGTH)) and block[N.PATTERN_LENGTH] > 0:
            word += f"({block[N.PATTERN_LENGTH]})"
        elif kind == "N" and _int(block.get("digits")) and block["digits"] > 0:
            word += f"({block['digits']},{block.get('fraction_digits') or block.get('fraction') or 0})"
        out.append(word)
    return " | ".join(out)


def table_flags(item):
    """Флаги самого табличного поля (`header`, `read_only` …) либо `{}`: колонки пропускаются, у них свои флаги."""
    def walk(value):
        if isinstance(value, dict):
            flags = value.get("flags")
            if isinstance(flags, dict) and "read_only" in flags and "header" in flags:
                return flags
            for key, sub in value.items():
                if key in ("columns", N.ELEMENTS) or key == ed_columns.COLUMN_ITEMS:
                    continue
                found = walk(sub)
                if found:
                    return found
        return None
    return walk(item.node.get(N.CONTENT)) or {}


def _data_of(path, check, binder, item, kind, ts_name, column_name, column):
    """Слова о данных колонки: номер строки, реквизит табличной части или списка; `None` — данных у колонки нет (значение задаёт код)."""
    for one in (path, check):
        if one in (None, ed_datapath.NO_DATA):
            continue
        if one == [ed_datapath.ROW_NUMBER_ID]:
            return "номер строки"
        obj = binder.obj
        if obj is None:
            return "реквизит объекта (нет выгрузки)" if binder.ctx is None or binder.ctx.config is None else "реквизит вне выгрузки"
        if isinstance(one, list) and len(one) == 2 and one[0] == 0 and isinstance(one[1], dict):
            guid = one[1].get("guid")
            if ts_name:
                ts = next((t for t in obj.tables if t.name == ts_name), None)
                attr = next((a for a in (ts.attributes if ts else ()) if a.uuid == guid), None)
                if attr is not None:
                    return attr.name
            attr = next((a for a in obj.attributes if a.uuid == guid), None)
            return attr.name if attr is not None else "реквизит вне выгрузки"
        key = shell.list_column_key(one, column_name, obj)
        return key or "путь данных не расшифрован"
    return None


def table_columns(item, binder):
    """Колонки табличного поля: `{"kind", "source", "header_shown", "read_only", "columns": [...]}`; `None` — это не табличное поле.

    Колонка: `name`, `header` (заголовок, пустой — без заголовка), `data` (слова либо `None`), `type` (тип значения), `width` (px),
    `visible`, `read_only`, `control` (вложенный элемент словами: флажок, поле выбора; поле ввода и «нет» — `None`), `enabled`, `location`
    (положение колонки: `NewColumn`, `OnNextRow`, `SameColumn`).
    У таблицы на реквизит формы (таблицу значений) колонка не несёт пути данных: её данные — одноимённая колонка таблицы значений."""
    block = ed_columns.columns_of(item.node)
    if block is None:
        return None
    kind_words, source_words, ts_name = None, None, None
    if binder is not None and binder.ctx is not None:
        bound, words = binder.words(item)
        source_words = words
        if bound == "table":
            ts_name = words.split(" ", 2)[-1]
    flags = table_flags(item)
    columns = []
    for column in block[ed_columns.COLUMN_ITEMS]:
        if not isinstance(column, dict):
            continue
        guid = (column.get(ed_columns.COLUMN_TYPE) or {}).get("guid") if isinstance(column.get(ed_columns.COLUMN_TYPE), dict) else None
        kind_words = kind_words or ed_platform.COLUMN_KINDS.get(guid)
        base = ed_columns._column_base(column)
        head = base.get(ed_columns.COLUMN_HEAD) if isinstance(base, dict) else None
        if not isinstance(head, dict):
            columns.append({"name": None, "header": "", "data": None, "type": "", "width": None, "visible": True, "read_only": False,
                            "control": None, "enabled": True, "no_head": True})
            continue
        name = head.get(ed_columns.COLUMN_NAME)
        name = name if isinstance(name, str) else None
        col_flags = head.get("flags") if isinstance(head.get("flags"), dict) else {}
        control = (head.get(ed_columns.COLUMN_CONTROL_TYPE) or {}).get("guid") if isinstance(head.get(ed_columns.COLUMN_CONTROL_TYPE), dict) else None
        control_kind = schema.element_type_name(control) if control else None
        width = render.column_width(head)
        width = None if width is None else round(width)
        path = base.get(ed_datapath.COLUMN_PATH)
        check = base.get(ed_columns.COLUMN_CHECK_PATH)
        data = _data_of(path, check, binder, item, kind_words, ts_name, name, column) if binder is not None else None
        columns.append({"name": name, "header": _text_of(head.get(ed_columns.COLUMN_HEADER_TEXT)),
                        "data": data, "type": _value_type(head.get(ed_columns.COLUMN_VALUE_TYPE)), "width": width,
                        "visible": col_flags.get("visible") is not False, "read_only": col_flags.get("read_only") is True,
                        "location": head.get(ed_columns.COLUMN_LOCATION),
                        "control": CONTROL_WORDS.get(control_kind) if control_kind not in (None, "TextBox") else None,
                        "enabled": col_flags.get("enabled") is not False})
    return {"kind": kind_words, "source": source_words, "header_shown": flags.get("header") is not False if flags else None,
            "read_only": flags.get("read_only") is False if flags else False, "columns": columns}


# ── Командные панели ──

def _standard_words(spec):
    """Имя стандартного действия кнопки; у кода без имени — `№код`."""
    code = spec.get(N.STANDARD_ACTION) if isinstance(spec, dict) else None
    return STANDARD_WORDS.get(code, f"№{code}" if code is not None else "без номера")


def _action_words(block, button):
    """`(вид, слова, процедура)` действия кнопки: `procedure`, `standard`, `submenu`, `none` или `unknown`."""
    try:
        action = ed_base._action_of(block, button, "", button.get(N.BTN_NAME))
    except ed_base.EditError:
        return "none", None, None
    kind = ed_buttons._action_kind(block, action)
    spec = action.get(N.ACT_SPEC)
    if kind == ed_buttons.PROCEDURE_KIND:
        handler = spec.get(N.HANDLER) if isinstance(spec, dict) else None
        return "procedure", handler, handler if isinstance(handler, str) and handler else None
    if kind == ed_buttons.STANDARD_KIND:
        return "standard", _standard_words(spec), None
    if kind == "кнопка-подменю":
        return "submenu", None, None
    return ("none", None, None) if kind in (None,) else ("unknown", kind, None)


MAIN_SET = ("b78f2e80-ec68-11d4-9dcf-0050bae2bc79", 4)          # основной набор панели: у каждой панели формы стоит под этой парой (ссылка, код); подменю лежат под своими


def top_set(block):
    """Верхний набор блока действий. Первый набор, на который не ссылается кнопка-подменю (`render._own_set`), бывает пустым двойником подменю (в файле он стоит раньше основного, с кодом 1549):
    тогда кнопки панели лежат в основном наборе (`MAIN_SET`), и читается он."""
    top = render._own_set(block)
    if top is not None and (top.get(N.BUTTONS) or []):
        return top
    for item in block.get(N.BUTTON_SETS) or []:
        ref = item.get(ed_buttons.SET_REF) if isinstance(item, dict) else None
        if isinstance(ref, dict) and (ref.get("guid"), item.get(ed_buttons.SET_CODE)) == MAIN_SET and (item.get(N.BUTTONS) or []):
            return item
    return top


def bar_buttons(block):
    """Кнопки блока действий: `[{name, text, kind, action, procedure, enabled, check, depth, children, representation, picture, view, view_checked}]`
    верхнего набора, `children` — пункты подменю (пункты меню `view` не называют: как показан пункт, не проверялось)."""
    submenus = ed_submenu.submenu_sets(block)
    top = top_set(block)

    def read(button_set, depth, seen):
        out = []
        for button in (button_set or {}).get(N.BUTTONS) or []:
            if not isinstance(button, dict):
                continue
            kind_type = button.get(ed_submenu.BTN_TYPE)
            entry = {"name": button.get(N.BTN_NAME), "text": _text_of(button.get(N.BTN_TEXT)), "depth": depth, "children": [],
                     "enabled": button.get("enabled") is not False, "check": button.get("check") is True,
                     "representation": button.get("representation"), "shown": None, "origin": None, "std_code": None, "menu": None}
            if kind_type == ed_submenu.SEPARATOR:
                entry.update(kind="separator", action=None, procedure=None, picture=False, view=None, view_checked=True)
            else:
                how, words, procedure = _action_words(block, button)
                entry.update(kind="submenu" if kind_type == ed_submenu.POPUP else how, action=words, procedure=procedure)
                entry["picture"] = render.button_has_picture(block, button)
                entry["shown"], entry["origin"] = render.shown_text(block, button)
                entry["std_code"] = render.button_standard(block, button)
                entry["menu"] = render.button_menu_pair(block, button) if kind_type == ed_submenu.POPUP else None
                entry["view"], entry["view_checked"] = (render.button_view(entry["representation"], entry["picture"], entry["std_code"] is not None)
                                                        if depth == 0 and kind_type != ed_submenu.POPUP else (None, True))
                guid = (button.get("id") or {}).get("guid") if isinstance(button.get("id"), dict) else None
                if kind_type == ed_submenu.POPUP and guid in submenus and depth < MENU_DEPTH and guid not in seen:
                    entry["children"] = read(submenus[guid][0], depth + 1, seen | {guid})
            out.append(entry)
        return out
    return read(top, 0, frozenset())


def count_buttons(buttons):
    """Сколько кнопок (без разделителей, с пунктами подменю) в списке `bar_buttons`."""
    return sum((0 if b["kind"] == "separator" else 1) + count_buttons(b["children"]) for b in buttons)


def _form_kind_of(doc):
    return render._form_kind(doc)


def platform_fill(item, doc=None):
    """Что платформа ставит на панель с автозаполнением по наблюдению (`bar_platform.fill`): `{"head": […], "tail": […], "words": слова либо None}`;
    у панели без автозаполнения — `None`. Запись — `(вид, текст)`: `popup`, `icon`, `sep`."""
    if not render._auto_fill_flag(item.node):
        return None
    head, tail, words, source = render._platform_fill(item.node, doc)
    ctx = bar_platform.current()
    bottom = render.bars._is_bottom(item.node) and not render._action_source_is_table(item.node)
    return {"head": [list(e) for e in head if e[0] != "sep"], "tail": [list(e) for e in tail if e[0] != "sep"], "words": words,
            "menu": bar_platform.menu_items(_form_kind_of(doc), ctx.get("groups"), render._action_source_is_table(item.node),
                                            render._table_data_kind(item.node, doc), render.bars.has_saved_values(doc), render.bars._has_main_attribute(doc), bottom),
            "source": source if head or tail else None}


def bars(form, names):
    """Командные панели формы: `[{element, item, auto_fill, fill, hidden, buttons}]` в порядке элементов; у кнопки-меню — её меню. `auto_fill` — у панели
    нет кнопок в файле и включено автозаполнение (состав задаёт платформа); `fill` — состав платформы у панели с автозаполнением (`platform_fill`),
    и когда кнопки в файле есть (платформа ставит свои до и после них)."""
    out = []
    for item in form.items.values():
        found = own_blocks(item.node)
        if not found:
            continue
        for block in found:
            out.append({"element": names.of(item), "item": item, "type": item.type,
                        "auto_fill": render._dig(item.node, "content", "u1", "auto_fill") is True and not bar_buttons(block),
                        "fill": platform_fill(item), "hidden": not item.visible, "buttons": bar_buttons(block)})
    return out


# ── Закладки ──

def strip_hidden(form, names):
    """Панели и форма, у которых вид закладок «Не отображать»: `{имя панели в структуре, у формы — ""}`; страницы переключает код."""
    out = set()
    for holder in form.holders.values():
        block = holder.block
        if holder.item is None:
            pages = block.get(N.PAGES) if isinstance(block, dict) else None
            items = pages.get(N.PAGE_ITEMS) if isinstance(pages, dict) else None
            if form.pages_off and isinstance(items, list) and len(items) > 1:
                out.add("")
        elif isinstance(block, dict) and block.get(N.SHOW_TABS) == "DontUse":
            out.add(names.of(holder.item))
    return out


def page_names(form, names):
    """`{(имя панели или None, номер страницы): имя страницы}` — имена страниц для разбора кода (`Страницы.<Имя>`)."""
    out = {}
    for holder in form.holders.values():
        block = holder.block
        pages = block.get(N.PAGES) if isinstance(block, dict) else None
        items = pages.get(N.PAGE_ITEMS) if isinstance(pages, dict) else None
        for at, page in enumerate(items if isinstance(items, list) else ()):
            if isinstance(page, dict):
                name = page.get(N.PAGE_NAME)
                out[(None if holder.item is None else names.of(holder.item), at)] = name if isinstance(name, str) else None
    return out


# ── Переключатели ──

def radio_groups(form):
    """`{индекс переключателя: (первый переключатель группы, номер в группе с единицы, размер группы)}`.

    Группа — первый переключатель с признаком «первый в группе» и все следующие за ним в том же родителе на той же странице до
    следующего первого. Переключатель без найденного начала группы в словарь не входит."""
    out = {}
    for holder in form.holders.values():
        by_page = collections.defaultdict(list)
        for item in holder.children:
            if item.type == "RadioButton":
                by_page[item.page or 0].append(item)
        for items in by_page.values():
            groups, current = [], None
            for item in items:
                block = item.node.get(N.NAME_BLOCK)
                first = isinstance(block, dict) and block.get("first_in_group") is True
                if first:
                    current = [item]
                    groups.append(current)
                elif current is not None:
                    current.append(item)
            for group in groups:
                for at, item in enumerate(group, 1):
                    out[item.index] = (group[0], at, len(group))
    return out


# ── Свойства элементов ──

def _own_values(node, key):
    """Значения под ключом `key` в самом элементе: вложенные элементы, колонки таблицы, кнопки и действия панелей — не его свойства."""
    skip = (N.ELEMENTS, N.ACTIONS, N.BUTTON_SETS, ed_columns.COLUMN_ITEMS)

    def walk(value):
        if isinstance(value, dict):
            for k, v in value.items():
                if k in skip:
                    continue
                if k == key:
                    yield v
                else:
                    yield from walk(v)
        elif isinstance(value, list):
            for v in value:
                yield from walk(v)
    return list(walk(node))


def tool_tip(item):
    """Текст подсказки элемента (свойство «Подсказка») либо пустая строка."""
    for value in _own_values(item.node, "tool_tip"):
        text = _text_of(value)
        if text:
            return text
    return ""


def has_extra_tip(item, caption, paired=None):
    """У элемента с надписью задана подсказка, отличная от надписи, парной надписи и имени: в сводке досье такие элементы считаются числом."""
    tip = tool_tip(item)
    known = {caption, item.name, (paired or "").rstrip(": ").strip(), (paired or "").strip()}
    return bool(tip) and tip not in known and bool(caption or paired is not None)


def element_marks(item, caption, paired=None):
    """Свойства для разбора удобства словами: `[слова]`. `paired` — надпись пары «надпись → поле», у которой поле своей надписи не имеет
    (`None` — элемент не в паре). Подсказка, совпадающая с надписью, парной надписью или именем, не называется."""
    marks = []
    if item.type in ("TextBox", "ComboBox"):
        if any(v is True for v in _own_values(item.node, "read_only")):
            marks.append("только просмотр")
        if describe._multiline(item):
            marks.append("многострочное")
        if any(v is True for v in _own_values(item.node, "password_mode")):
            marks.append("пароль")
        if any(v is True for v in _own_values(item.node, "choice_button")):
            marks.append("кнопка выбора")
        if any(v is True for v in _own_values(item.node, "clear_button")):
            marks.append("кнопка очистки")
    elif item.type == "Button":
        marks.append("с картинкой" if render.element_button_picture(item.node) else "без картинки")      # кнопка формы показывает и текст, и картинку; без текста — одну картинку
        if not caption:
            marks.append("без текста")
    elif item.type == "TableBox" and table_flags(item).get("read_only") is False:
        marks.append("только просмотр")        # бит «только просмотр» у табличного поля в файле перевёрнут: 0 — свойство включено
    block = item.node.get(N.NAME_BLOCK)
    if isinstance(block, dict) and block.get("skip_on_input") is True and item.type not in ("Label", "GroupBox"):
        marks.append(SKIP_MARK)
    tip = tool_tip(item)
    known = {caption, item.name, (paired or "").rstrip(": ").strip(), (paired or "").strip()}
    if tip and tip not in known and not caption and paired is None:
        # у элемента без надписи (кнопка с картинкой) подсказка — единственный текст: она называется; у остальных — только числом в сводке
        marks.append("подсказка «" + (tip if len(tip) <= 40 else tip[:39].rstrip() + "…") + "»")
    return marks
