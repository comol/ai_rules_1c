"""Раздел «структура» досье: таблица элементов, колонки таблиц, кнопки командных панелей, страницы панелей, дерево узлов."""

import collections
import re

from .. import bar_platform, edit, render, shell
from .. import structure as structure_mod
from ..edit import columns as ed_columns
from . import content, facts, words as br_words, vocab
from .fmt import _list, _table
from .purpose import _effect_detail


def _page_nodes(structure):
    """`{(панель или None, номер страницы): (номер узла T, подпись)}` — узлы страниц структуры."""
    return {(n.holder, n.page): (n.id, n.caption) for n in structure.walk() if n.role == structure_mod.PAGE}


def _effect_marks(module):
    """`{элемент: слова}` — что код меняет у элемента (без кнопок, страниц и колонок: у них свои строки перечня). Видимость и текст, заданные кодом, названы с
    выражением и условием, из которых они вычисляются."""
    out = {}
    for effect in module["effects"]:
        if effect["part"] is None:
            out[effect["element"]] = ", ".join(p + (f" ({'; '.join(_effect_detail(effect, p, vocab.MARK_SHOWN))})" if _effect_detail(effect, p, vocab.MARK_SHOWN) else "")
                                               for p in effect["props"])
    return out


def _element_rows(structure, names, form, doc, binder, module, places=None):
    rows = []
    pages = _page_nodes(structure)
    radios = content.radio_groups(form)
    changed = _effect_marks(module)
    for node in structure.walk():
        for name in node.elements:
            item = names.item_of.get(name)
            if item is None:
                continue
            caption = (render.caption_text(item.node, item.type) or shell.caption_of(item.node) or "").strip()
            kind_, data = binder.words(item)
            order = item.coords.get(edit.TAB_ORDER) if item.coords else None
            marks = []
            if not item.visible:
                marks.append("скрыт")
            if not facts._enabled(item.node):
                marks.append("недоступен")
            if item.page:
                page = pages.get((names.of(item.owner) if item.owner is not None else None, item.page))
                marks.append("страница " + (f"{page[0]} «{page[1]}»" if page and page[1] else (page[0] if page else str(item.page))))
            paired = None
            if node.role == structure_mod.PAIR and node.kind == structure_mod.LABEL_FIELD and not caption:
                label = next((names.item_of[n] for n in node.elements if n in names.item_of and names.item_of[n].type == "Label"), None)
                paired = (render.caption_text(label.node, "Label") or "").strip() if label is not None else ""
            marks += content.element_marks(item, caption, paired)
            extra_tip = content.has_extra_tip(item, caption, paired)
            group = radios.get(item.index)
            if group is not None:
                first, at, size = group
                marks.append(f"переключатель группы из {size}" if at == 1 else f"переключатель {at}-й из {size} в группе")
                if at > 1 and data is None:
                    data = f"группа: данные у «{names.short(first)}»"
            if name in changed:
                marks.append(f"код меняет: {changed[name]}")
            marks += (places or {}).get(name, [])
            x, y, right, bottom = (int(round(v)) for v in item.box)
            in_file = None
            if item.stored is not None:
                fx, fy, fright, fbottom = (int(round(v)) for v in item.stored)
                if (fx, fy, fright, fbottom) != (x, y, right, bottom):
                    in_file = [fx, fy, fright - fx, fbottom - fy]
            if node.role == structure_mod.PAIR and node.kind:
                role = structure_mod.KIND_WORDS[node.kind]
            elif node.hint:
                role = f"подсказка к {node.hint}"
            else:
                role = None
            focus = facts._focused(item) or item.type == "Panel"
            if item.type == "Label" and data and caption and LABEL_STUB.fullmatch(caption):
                caption = ""          # «Надпись6» — текст, который платформа даёт новой надписи; у надписи с данными на экране текст приходит из данных
                marks.append("текст из данных (в файле заглушка платформы)")
            rows.append({"node": node.id, "role": role, "element": name, "short": names.short(name), "type": item.type,
                         "caption": caption or None, "data": data, "extra_tip": extra_tip,
                         "x": x, "y": y, "width": right - x, "height": bottom - y, **({"in_file": in_file} if in_file else {}),
                         "tab": order if isinstance(order, int) and not isinstance(order, bool) and focus else None,
                         "marks": marks})
    return rows


def _table_kinds(form, binder):
    """Вид данных каждого табличного поля формы: номер элемента → «список», «табличная часть», «таблица значений», «список значений»; у таблицы без колонок — по привязке данных."""
    out = {}
    for item in form.items.values():
        if ed_columns.columns_of(item.node) is None:
            continue
        kind = render.table_kind_of(item)
        if kind is None and binder is not None and binder.words(item)[0] == "table":
            kind = bar_platform.TABLE_PART
        out[item.index] = kind
    return out


def _tables(form, names, binder):
    """Табличные поля формы с колонками: `[{element, short, node, hidden, kind, source, header_shown, read_only, columns}]`."""
    out = []
    for item in form.items.values():
        found = content.table_columns(item, binder)
        if found is None:
            continue
        name = names.of(item)
        _screen_widths(item, found["columns"])
        out.append({"element": name, "short": names.short(name), "node": names.node(name), "hidden": not item.visible, **found})
    return out


def _screen_widths(item, columns):
    """Колонкам, чья ширина на экране иная, чем в файле, — `screen_width` (px): платформа ужимает колонки, когда их сумма больше таблицы (ширина таблицы — на экране
    при размере формы, `item.box`)."""
    shown = render.column_screen_widths(item, int(round(item.box[2] - item.box[0])))
    mine = [c for c in columns if c["visible"] and not c.get("no_head")]
    if len(shown) != len(mine):
        return
    for column, width in zip(mine, shown):
        if column["width"] is not None and int(round(width)) != column["width"]:
            column["screen_width"] = int(round(width))


def _columns_by_code(tables, module):
    """Колонкам, чьё свойство задаёт код (`ЭлементыФормы.<Таблица>.Колонки.<Колонка>.Видимость = …`), — `by_code`: `[слова]`."""
    by = {}
    for effect in module["effects"]:
        if effect["part"] and effect["part"].startswith("колонка "):
            by.setdefault((effect["element"], effect["part"][len("колонка "):].casefold()), []).append(effect)
    for table in tables:
        for column in table["columns"]:
            found = by.get((table["element"], (column["name"] or "").casefold()))
            column["by_code"] = [p + (f" ({'; '.join(_effect_detail(e, p, vocab.MARK_SHOWN))})" if _effect_detail(e, p, vocab.MARK_SHOWN) else "")
                                 for e in found or [] for p in e["props"]]


def _bars(form, names, structure):
    """Командные панели формы в порядке чтения структуры: `[{element, short, node, type, hidden, auto_fill, count, buttons}]`."""
    place = {name: at for at, name in enumerate(structure.reading_order())}
    out = []
    for bar in content.bars(form, names):
        out.append({"element": bar["element"], "short": names.short(bar["element"]), "node": names.node(bar["element"]),
                    "type": bar["type"], "hidden": bar["hidden"], "auto_fill": bar["auto_fill"], "fill": bar["fill"],
                    "count": content.count_buttons(bar["buttons"]), "buttons": bar["buttons"]})
    return sorted(out, key=lambda b: place.get(b["element"], len(place)))


COLUMNS_SHOWN = 40       # колонок одной таблицы в «Структуре» называется не больше стольких (остальные — числом)


LABEL_STUB = re.compile(r"Надпись\d*")      # заглушка платформы в файле формы: подписью надписи не называется
PLACEHOLDER_TEXT = re.compile(r"Действие\d*")      # текст, который платформа даёт кнопке стандартного действия: «Действие», «Действие1»…


def _action_name(button):
    """Название стандартного действия кнопки: текст платформы, а у кода без текста в снимках — «стандартное действие №код»."""
    action = button.get("action") or ""
    return f"стандартное действие {action}" if action.startswith("№") else action


def _button_label(button):
    """Кнопка в строке панели: что на ней видно на экране (а не имя кнопки и не заглушка файла) и как она показана, когда это не просто текст.

    Имя-заглушка файла (`"#"`: «Подменю1», «Действие2», «Кн записать») платформа заменяет своим: у подменю — названием стандартного меню («Действия», «Перейти»),
    у стандартного действия — его текстом; у кнопки без текста со стандартным действием на экране значок, и называется он действием (`bar_platform`)."""
    kind, view, origin = button["kind"], button.get("view"), button.get("origin")
    shown, file_text = button.get("shown") or "", button["text"]
    if kind == "submenu":
        return f"«{file_text}»" if origin == "stub" else f"«{shown or file_text}»"
    if kind == "standard" and view == render.VIEW_PICTURE:
        said = f"значок: {_action_name(button)}"
        if origin == "file" and file_text:
            said += f" (текст «{file_text}» на экране не виден: у кнопки значок)"
        return said
    notes = []
    if kind == "standard" and origin == "action":
        text = f"«{shown}»"
        notes.append("текст стандартного действия" + (f", в файле заглушка «{button['text']}»" if button["text"] and button["text"] != shown else ""))
    elif kind == "standard" and origin == "stub":
        text = f"«{file_text}»" if file_text else _action_name(button)
        if file_text:
            notes.append("заглушка платформы, а не заголовок кнопки: текст стандартного действия в предприятии не наблюдался")
    elif not shown:
        text = "без текста"
    else:
        text = f"«{shown}»"
        if kind == "standard" and origin == "file" and PLACEHOLDER_TEXT.fullmatch(file_text):
            notes.append("заглушка платформы, а не заголовок кнопки")
    if view == render.VIEW_PICTURE:
        notes.append("картинкой")
    elif view == render.VIEW_BOTH:
        notes.append("картинкой и текстом")
    elif view == "пусто":
        notes.append("отображение «Картинка», а картинки нет: на панели пусто")
    elif view == render.VIEW_TEXT and button.get("picture"):
        notes.append("только текстом, картинка у кнопки есть, но не видна")
    return text + (" (" + "; ".join(notes) + ")" if notes else "")


def _submenu_note(button):
    """Слова о названии подменю, когда оно не из файла: у подменю с именем-заглушкой название ставит платформа."""
    if button.get("origin") == "menu":
        return f"название меню ставит платформа, в файле заглушка «{button['text']}»; "
    if button.get("origin") == "stub":
        return "имя-заглушка подменю без текста: что показывает платформа, в предприятии не наблюдалось; "
    return ""


def _bar_code_marks(module, element):
    """`(метки кнопок, слова о панели)` — что код делает с кнопками панели `element`: метки `{имя кнопки без регистра: [слова]}` (удаляет, прячет, меняет
    доступность) и слова о добавленных кнопках и очистке панели."""
    marks, added = {}, []
    for e in module["effects"] if module else ():
        if e["element"] != element:
            continue
        name = e["part"][len("кнопка "):] if e["part"] and e["part"].startswith("кнопка ") else None
        for prop, values in e["props"].items():
            if prop == "удаляет кнопку" and name:
                marks.setdefault(name.casefold(), []).append("код удаляет её" + (f" ({', '.join(e['procedures'])})" if e["procedures"] else ""))
            elif prop == "видимость" and name:
                hide = "Ложь" in values
                marks.setdefault(name.casefold(), []).append(("код прячет её" if values == ["Ложь"] else "код меняет её видимость")
                                                              + (f" (видимость = {', '.join(values)}" if hide or values else "") + (")" if hide or values else "")
                                                              + (f"; {'; '.join(_effect_detail(e, prop))}" if _effect_detail(e, prop) else ""))
            elif prop == "доступность" and name:
                marks.setdefault(name.casefold(), []).append("код меняет её доступность")
            elif prop.startswith("добавляет") or prop == "очищает все кнопки":
                said = (prop + (f" «{name}»" if name else "") + (f" ({'; '.join(v for v in values if v)})" if any(values) else ""))
                added.append(said)
    return marks, list(dict.fromkeys(added))


def _buttons_text(buttons, procedures, known, marks=None):
    parts, i = [], 0
    live = [b for b in buttons if b["kind"] != "separator"]
    while i < len(live):
        b = live[i]
        group = [b]
        if b["kind"] == "procedure" and not b["children"]:
            while (i + len(group) < len(live) and live[i + len(group)]["kind"] == "procedure" and not live[i + len(group)]["children"]
                   and live[i + len(group)]["procedure"] == b["procedure"]):
                group.append(live[i + len(group)])
        i += len(group)
        text = ", ".join(_button_label(x) for x in group[:vocab.FOLD_LISTED]) + (f" и ещё {len(group) - vocab.FOLD_LISTED}" if len(group) > vocab.FOLD_LISTED else "")
        flags = [w for x in group for w in ([] if x["enabled"] else ["недоступна"]) + (["отмечена"] if x["check"] else [])
                 + (marks or {}).get((x["name"] or "").casefold(), [])]
        if b["kind"] == "procedure":
            text += f" → {b['procedure']}" + (" (процедуры нет в модуле)" if known and b["procedure"].casefold() not in procedures else "")
        elif b["kind"] == "standard":
            if not text.startswith("значок:") and not text.startswith("стандартное действие"):
                text += f" → стандартное действие " + (b["action"] if b["action"].startswith("№") else f"«{b['action']}»")
        elif b["kind"] == "submenu":
            text += " ▾ (" + _submenu_note(b) + "подменю: " + (_buttons_text(b["children"], procedures, known, marks) or "пусто") + ")"
        elif b["kind"] == "none":
            text += " (без действия)"
        if flags:
            text += " (" + ", ".join(dict.fromkeys(flags)) + ")"
        parts.append(text)
    return "; ".join(parts)


def _fill_items(items):
    return ", ".join(("«" + e[1] + "» ▾") if e[0] == "popup" else ("«" + e[1] + "» (кнопка с текстом, подсказка «" + e[2] + "»)" if e[0] == "text" and len(e) > 2 else
                      "«" + e[1] + "» (кнопка с текстом)" if e[0] == "text" else "значок «" + e[1] + "»") for e in items)


def _md_bars(structure, module):
    procedures = {p.casefold() for p in module.get("procedure_names", [])}
    known = module["present"]
    lines = ["", "Командные панели (кнопки: текст, действие — процедура модуля или стандартное, подменю вложено; "
             "признака «скрыта» и «по умолчанию» у кнопки панели в файле нет; в скобках — как кнопка показана, когда это не просто текст: "
             "картинкой, картинкой и текстом; «значок: …» — на экране один значок стандартного действия, текста нет, а имя кнопки — в коде формы; "
             "«Действия» и «Перейти» у подменю — названия, которые ставит платформа вместо имени-заглушки файла; кнопка без текста названа так):", ""]
    for bar in structure["bars"]:
        head = f"- «{bar['short']}» ({bar['node'] or '?'})" + (", панель скрыта" if bar["hidden"] else "") + ": "
        fill = bar.get("fill")
        marks, added = _bar_code_marks(module, bar["element"])
        file_text = _buttons_text(bar["buttons"], procedures, known, marks) if bar["buttons"] else None
        if fill is not None and (fill["head"] or fill["tail"]):
            parts = [f"автозаполнение: платформа ставит сама (по наблюдению в предприятии: {fill['source']}) {_fill_items(fill['head'])}"
                     + (f"; в файле: {file_text}" if file_text else "; в файле кнопок нет")
                     + (f"; после подменю «Перейти» (если его в файле нет — после своих значков) платформа ставит ещё {_fill_items(fill['tail'])}" if fill["tail"] else "")]
            if fill.get("menu"):
                parts.append(f"меню «Действия» (по наблюдению в предприятии): {fill['menu']}")
            if fill["words"]:
                parts.append(f"неизвестно: {fill['words']}")
            lines.append(head + "; ".join(parts))
        elif fill is not None:
            lines.append(head + ("в файле: " + file_text + "; кроме них " if file_text else "кнопок в файле нет, ")
                         + "состав ставит платформа (автозаполнение: у этого вида формы состав в предприятии не наблюдался)")
        elif bar["auto_fill"]:
            lines.append(head + "кнопок в файле нет, состав задаёт платформа (автозаполнение)")
        elif not bar["buttons"]:
            lines.append(head + "кнопок нет")
        else:
            lines.append(head + file_text)
        if added:
            lines[-1] += "; код меняет панель: " + "; ".join(added)
    return lines


LOCATION_WORDS = {"OnNextRow": "на следующей строке", "SameColumn": "в той же колонке"}     # «В новой колонке» — обычное положение, его не называют


SCREEN_WIDTH_NOTE = ("«Ш в файле» — ширина колонки, записанная в файле; «на экране» — ширина при размере формы: платформа подгоняет колонки под ширину таблицы "
                     "(сжимает, когда их сумма больше таблицы, — не меньше 0,75 записанной, и растягивает, когда меньше). Заголовки в разделе 7 сверяются с шириной на экране.")


def _md_columns(table):
    cols = table["columns"]
    if not cols:
        return []
    visible = [c for c in cols if c["visible"]]
    hidden = [c for c in cols if not c["visible"]]
    head = (f"**«{table['short']}»** ({table['node'] or '?'}): " + "; ".join(x for x in (table["kind"], table["source"]) if x)
            + f"; колонок {len(cols)}, видимых {len(visible)}"
            + ("; шапка таблицы не показывается" if table["header_shown"] is False else "")
            + ("; таблица только для просмотра" if table["read_only"] else "") + (", таблица скрыта" if table["hidden"] else ""))
    with_data = any(c["data"] and c["data"] != c["name"] for c in cols)       # данные, совпавшие с именем колонки, колонкой не повторяются
    composite = any(c.get("location") in LOCATION_WORDS for c in visible)       # составные колонки: столбец «Положение» нужен только им
    header = ["Колонка", "Заголовок"] + (["Данные"] if with_data else []) + ["Тип", "Ш в файле"] + (["Положение"] if composite else []) + ["Пометки"]
    rows = []
    for c in visible[:COLUMNS_SHOWN]:
        marks = [m for m in (c["control"], "только просмотр" if c["read_only"] else None, None if c["enabled"] else "недоступна") if m]
        marks += [f"код меняет: {w}" for w in c.get("by_code") or []]
        data = "" if c["data"] == c["name"] else (c["data"] or "")
        width = c["width"] if c.get("screen_width") is None else f"{c['width']} (на экране {c['screen_width']})"
        rows.append([c["name"] or "", c["header"]] + ([data] if with_data else []) + [c["type"], width]
                    + ([LOCATION_WORDS.get(c.get("location"), "")] if composite else []) + [", ".join(marks)])
    lines = ["", head, ""] + _table(header, rows)
    if len(visible) > COLUMNS_SHOWN:
        lines.append(f"…и ещё колонок: {len(visible) - COLUMNS_SHOWN}.")
    if hidden:
        shown_by_code = [c for c in hidden if any(w.startswith("видимость") for w in c.get("by_code") or [])]
        lines += ["", "Скрытые колонки (пользователь их не видит): " + ", ".join(c["name"] or "?" for c in hidden) + "."
                  + (" Видимость задаёт код у колонок: " + ", ".join(c["name"] or "?" for c in shown_by_code) + "." if shown_by_code else "")]
    coded = [c for c in visible if any(w.startswith("видимость") for w in c.get("by_code") or [])]
    if coded:
        lines += ["", "Видимость колонок, видимых в файле, задаёт код (в предприятии их может не быть): " + ", ".join(c["name"] or "?" for c in coded) + "."]
    return lines


def _md_pages(structure):
    by_panel = collections.OrderedDict()
    for p in structure["pages"]:
        by_panel.setdefault(p["panel"], []).append(p)
    lines = []
    for panel, pages in by_panel.items():
        where = "формы" if not panel else f"панели «{panel.split('/')[-1]}»"
        listed = "; ".join(f"{p['node']} — «{p['caption']}»" + (f" ({p['by_code']})" if p.get("by_code") else "") for p in pages)
        if pages[0]["tabs_shown"]:
            lines.append(f"Закладки страниц {where}: {listed}.")
        else:
            lines.append(f"Страницы {where} без закладок (закладки не отображаются, страницы переключает модуль): {listed}.")
    return lines


DEFAULT_PAIR = structure_mod.KIND_WORDS[structure_mod.LABEL_FIELD]      # обычная пара: её вид назван деревом и в строках таблицы не повторяется


DATA_PREFIX = (("реквизит объекта ", "объект: "), ("реквизит формы ", "форма: "), ("табличная часть ", "табл. часть: "))


def _data_cell(words):
    """Данные элемента в таблице структуры: короткая приставка вместо «реквизит объекта …» (полные слова — в brief.json)."""
    if words and words.startswith("реквизит объекта (имя без выгрузки"):
        return "объект: имя неизвестно (нет выгрузки)"
    for long, short in DATA_PREFIX:
        if words and words.startswith(long):
            return short + words[len(long):]
    return words


def _element_table(elements):
    """Строки таблицы элементов: надпись пары «надпись → поле» уходит в строку поля, место и размер — в двух ячейках."""
    out, skip = [], set()
    by_node = collections.defaultdict(list)
    for at, e in enumerate(elements):
        by_node[e["node"]].append(at)
    for node, at_list in by_node.items():
        rows = [elements[a] for a in at_list]
        if len(rows) == 2 and all(r["role"] == DEFAULT_PAIR for r in rows) and rows[0]["type"] == "Label":
            skip.add(at_list[0])
    for at, e in enumerate(elements):
        if at in skip:
            continue
        caption = e["caption"]
        if at - 1 in skip and elements[at - 1]["node"] == e["node"]:
            caption = elements[at - 1]["caption"]
        marks = list(e["marks"]) + ([e["role"]] if e["role"] and e["role"] != DEFAULT_PAIR else [])
        if e.get("in_file"):
            marks.append("в файле {},{} {}×{}".format(*e["in_file"]))
        out.append([e["node"], e["short"], e["type"], caption, _data_cell(e["data"]), f"{e['x']},{e['y']}", f"{e['width']}×{e['height']}", e["tab"],
                    ", ".join(marks)])
    return out


def md_columns(structure):
    """Колонки всех таблиц формы (`--detail columns`): таблицы по очереди, пояснения к столбцам — один раз в конце."""
    lines = ["## Колонки таблиц", ""]
    tables = [t for t in structure["tables"] if t["columns"]]
    if not tables:
        return lines + ["Таблиц с колонками на форме нет.", ""]
    for table in tables:
        lines += _md_columns(table)
    if any(c.get("screen_width") is not None for t in tables for c in t["columns"] if c["visible"]):
        lines += ["", SCREEN_WIDTH_NOTE]
    if any(c.get("location") in LOCATION_WORDS for t in tables for c in t["columns"] if c["visible"]):
        lines += ["", "«Положение»: колонка «на следующей строке» стоит под предыдущей в одной составной колонке, «в той же колонке» — правее предыдущей в её строке; "
                  "составная колонка занимает ширину своей самой широкой строки, шапка таблицы — столько строк, сколько в самой высокой составной колонке. "
                  "Колонка без значения в этом столбце стоит в новой колонке."]
    lines += ["", "Колонки «Данные» у таблицы нет, когда данные колонки совпадают с её именем: у таблицы на реквизит формы пути данных у колонок "
              "нет, их данные — одноимённые колонки таблицы значений; у табличной части колонка названа по реквизиту."]
    return lines + [""]


def _md_structure(structure, images, module):
    lines = ["## 3. Структура", "", "Дерево узлов: номер, роль, элементы, место узла (лево,верх–право,низ) в координатах родителя; у пары и одиночного элемента "
             "места нет — оно в таблице ниже. Имена элементов короткие: полное имя (с панелями) — только у тёзок.", "", "```"] + structure["lines"] + ["```", ""]
    lines += _table(["Узел", "Элемент", "Вид", "Надпись", "Данные", "x,y", "Ш×В", "Обход", "Пометки"], _element_table(structure["elements"]))
    tips = sum(1 for e in structure["elements"] if e.get("extra_tip"))
    lines += ["", ("Подсказка, отличная от надписи, задана ещё у " + br_words.counted(tips, "элемента", "элементов", "элементов")
                   + " с надписью. " if tips else "") + "У пары «надпись → поле» надпись показана в строке поля (её имя, место и размер — в brief.json). "
              "Обход — номер элемента в порядке обхода клавишей Tab (число «Форма → Порядок обхода…», с единицы; у формы с автопорядком обхода его ведёт платформа по "
              "положению) внутри своего контейнера (форма или страница панели): в разных контейнерах номера повторяются, в одном бывают пропуски; у панели показано её место среди элементов формы."]
    pages = _md_pages(structure)
    if pages:
        lines += [""] + pages
    if structure["bars"]:
        lines += _md_bars(structure, module)
    if structure["raw"]:
        lines += ["", "Элементы без блока координат (в дерево не входят): " + _list(structure["raw"], 99) + "."]
    unclear = [n for n in _flat(structure["tree"]) if n["role"] == "unclear"]
    if unclear:
        lines += ["", "Неясные места (" + ", ".join(n["id"] for n in unclear) + "): причины — перекрытия и выходы за край — названы в разделе 7."]
    drawn = images.get("not_drawn") or []
    if drawn:
        lines += ["", "Узлов нет на картинках (страницы, которые не показаны, скрытые элементы и варианты на том же месте): " + ", ".join(drawn) + "."]
    return lines + [""]


def _flat(node):
    yield node
    for child in node.get("children") or []:
        yield from _flat(child)
