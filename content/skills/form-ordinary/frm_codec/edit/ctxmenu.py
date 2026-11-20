"""КонтекстноеМеню и АвтоКонтекстноеМеню элемента.

Оба свойства хранятся не в элементе, а в корне формы: `context_menu_links` — счётчик и записи по пять позиций
`(индекс владельца, индекс панели, набор кнопок панели, код набора, флаг)`. Первая запись лежит в полях `owner`, `menu`,
`kind`, `u4`, `u5`, запись с номером n — в полях `u{5n+1}` … `u{5n+5}`. Записи идут по возрастанию индекса владельца, у
владельца запись одна; запись формы (владелец 0) идёт первой.

**Флаг записи — это «АвтоКонтекстноеМеню» владельца** (1 — ☑, 0 — ☐); у видов без этой строки он 1. Состояние владельца —
пара «меню, автоменю» — лежит так:

    меню нет, автоменю ☑   записи нет
    меню нет, автоменю ☐   запись «снятое автоменю» (панели нет, вид `NO_AUTO_MENU_KIND`)
    меню есть              запись `(владелец, панель, набор, код набора, флаг автоменю)`

Меню — командная панель целиком (её основной набор кнопок) либо подменю этой панели (набор подменю и его код).
"""

from .base import EditError, element_names, find_element, holders
from .names import INDEX, NO_REFERENCE

NO_AUTO_MENU_KIND = "357c6a54-357d-425d-a2bd-22f4f6e86c87"
# Снятое АвтоКонтекстноеМеню без меню: запись без панели; вид связи и два последних значения платформа пишет одинаково у всех видов.
NO_AUTO_MENU_TAIL = (2147483647, 0)
# Виды, у которых в палитре нет строки «АвтоКонтекстноеМеню» (по снимкам палитр девяти типов шаблонов).
NO_AUTO_MENU = ("Splitter", "ProgressBar", "TrackBar", "CalendarBox", "RadioButton", "ListBox")
# То же у надписи и кнопки (палитра формы опыта); флаг записи меню у всех видов без этой строки всегда 1.
NO_AUTO_ROW = NO_AUTO_MENU + ("Label", "Button")
# Виды, у которых в палитре нет строки «КонтекстноеМеню».
NO_MENU_ROW = ("Splitter", "ProgressBar", "TrackBar", "CommandBar", "GroupBox")
# Виды, у которых связь меню проверена платформой; сама форма — владелец 0.
MEASURED = ("TextBox", "ComboBox", "RadioButton", "PictureBox", "ListBox", "TextDocumentField", "CalendarBox", "TableBox",
            "SpreadsheetDocumentField", "Label", "Button", "Panel")
FORM = "Form"
# Вид, у которого запись связи по устройству та же, что у проверенных видов, но платформа её для этого вида не писала: связь
# пишется, а отчёт говорит об этом словами (`UNCHECKED_WORDS`).
UNCHECKED_KINDS = ("HTMLDocumentField", "PDFDocumentField", "GeographicalSchemaField", "GraphicalSchemaField", "Chart", "GanttChart",
                   "Dendrogram", "PivotChart")
# Как отчёт называет такой вид в оговорке (`UNCHECKED_WORDS`).
UNCHECKED_NAMES = {"HTMLDocumentField": "поля HTML-документа", "PDFDocumentField": "поля PDF-документа",
                   "GeographicalSchemaField": "поля географической схемы", "GraphicalSchemaField": "поля графической схемы",
                   "Chart": "диаграммы", "GanttChart": "диаграммы Ганта", "Dendrogram": "дендрограммы",
                   "PivotChart": "сводной диаграммы"}
# Вид записи действия панели, которая называет набор подменю кнопки-подменю.
SUBMENU_ACTION_KIND = "abde0c9a-18a6-4e0c-bbaa-af26b911b3e6"
POPUP = "Popup"
MENU_FLAG = 1
NO_MENU_NAME = "Отсутствует"
MENU_SIZE = 24

_FIELDS = ("owner", "menu", "kind", "u4", "u5")


def _keys(count):
    """Имена полей блока по порядку: счётчик и записи."""
    names = ["count"] + list(_FIELDS)
    for n in range(1, count):
        names += [f"u{5 * n + i}" for i in range(1, 6)]
    return names


def read(doc):
    """Записи связей как `[{owner, menu, kind, u4, u5}]`. Блок, строение которого не как у платформы, — отказ."""
    block = doc.get("context_menu_links")
    count = block.get("count") if isinstance(block, dict) else None
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise EditError("у формы не разобраны связи контекстных меню: правка не сделана")
    if list(block) != _keys(count)[:1 if count == 0 else None]:
        raise EditError(f"связи контекстных меню формы ({count}) лежат не так, как их пишет платформа (поля {', '.join(block)}): "
                        "правка не сделана, правьте JSON по адресу")
    names = _keys(count)
    rows = []
    for n in range(count):
        row = dict(zip(_FIELDS, (block[name] for name in names[1 + 5 * n:6 + 5 * n])))
        if not isinstance(row["kind"], dict) or not isinstance(row["kind"].get("guid"), str):
            raise EditError(f"в записи {n + 1} связей контекстных меню нет вида связи: правка не сделана")
        rows.append(row)
    return rows


def write(doc, rows):
    """Блок связей из записей. Без записей остаётся один счётчик, как у формы без контекстных меню."""
    block = {"count": len(rows)}
    for name, value in zip(_keys(len(rows))[1:], (row[field] for row in rows for field in _FIELDS)):
        block[name] = value
    doc["context_menu_links"] = block


def _insert(rows, row):
    """Запись на своё место: перед первой записью с большим индексом владельца."""
    at = next((n for n, other in enumerate(rows) if other["owner"] > row["owner"]), len(rows))
    rows.insert(at, row)


def forget(doc, gone):
    """Убирает связи, называющие удалённые индексы: у владельца пропадает меню (или снятое автоменю), у панели — все
    её владельцы; у владельца со снятым автоменю связь с удалённой панелью заменяется записью «снятое автоменю» (автоменю
    остаётся ☐). Возвращает слова для отчёта."""
    block = doc.get("context_menu_links")
    if not isinstance(block, dict) or not block.get("count"):
        return []
    rows = read(doc)
    kept, replaced = [], 0
    for row in rows:
        if row["owner"] in gone:
            continue
        if row["menu"] in gone:
            if row["u5"] == 0:
                kept.append(_off_row(row["owner"]))
                replaced += 1
            continue
        kept.append(row)
    if kept == rows:
        return []
    write(doc, kept)
    removed = len(rows) - len(kept) + replaced
    said = f"связей контекстных меню убрано {removed - replaced}" if removed > replaced else ""
    if replaced:
        said += (", " if said else "") + f"{replaced} заменено записью «снятое автоменю»"
    return [said]


def forget_sets(doc, block, pairs):
    """Снимает связи, называющие удалённые наборы подменю панели: `block` — её блок действий, `pairs` — `(GUID набора, код)`.

    Владелец, у которого было только меню, теряет запись; владелец со снятым автоменю (флаг 0) получает запись «снятое
    автоменю», как у `forget`. Блок меню кнопки формы и панель без связей слов не дают. Возвращает слова для отчёта.
    """
    links = doc.get("context_menu_links")
    if not pairs or not isinstance(links, dict) or not links.get("count"):
        return []
    panel = next((n for n in _panels(doc) if ((n.get("content") or {}).get("u1") or {}).get("actions") is block), None)
    if panel is None:
        return []
    rows = read(doc)
    kept, who, replaced = [], [], 0
    for row in rows:
        if row["menu"] == panel.get(INDEX) and (row["kind"]["guid"], row["u4"]) in pairs:
            who.append(row["owner"])
            if row["u5"] == 0:
                kept.append(_off_row(row["owner"]))
                replaced += 1
            continue
        kept.append(row)
    if not who:
        return []
    write(doc, kept)
    names = {}
    for _holder, holder in holders(doc):
        for item in (holder.get("elements") or {}).get("items") or []:
            if isinstance(item, dict):
                names[item.get(INDEX)] = (item.get("name_block") or {}).get("name")
    owners = ", ".join(repr(names.get(i)) if i else "форма" for i in who)
    said = f"связей контекстных меню с удалённым подменю снято {len(who)} (владельцы: {owners})"
    if replaced:
        said += f"; у {replaced} из них АвтоКонтекстноеМеню снято — связь заменена записью «снятое автоменю»"
    return [said]


def _owner(doc, element):
    """`(вид, индекс)` владельца; `element=None` — сама форма (индекс 0)."""
    if element is None:
        return FORM, 0
    place = find_element(doc, element)
    index = place.element.get(INDEX)
    if not isinstance(index, int) or isinstance(index, bool):
        raise EditError(f"у элемента {element!r} нет индекса: связь контекстного меню записать нельзя")
    return place.element.get("type"), index


def _who(element):
    return element if element is not None else "форма"


def _check_kind(kind):
    if kind in NO_MENU_ROW:
        raise EditError(f"у элемента вида {kind} в палитре нет строки «КонтекстноеМеню»")
    if kind not in (FORM, *UNCHECKED_KINDS) and kind not in MEASURED:
        raise EditError(f"КонтекстноеМеню у элемента вида {kind} не проверялось. Проверено у {', '.join(MEASURED)} и у самой формы")


def _is_off(row):
    return row["kind"]["guid"] == NO_AUTO_MENU_KIND


def _flag(row, who):
    if row["u5"] not in (0, 1) or isinstance(row["u5"], bool):
        raise EditError(f"у связи контекстного меню {who} флаг {row['u5']!r}, а платформа пишет 0 или 1: правка не сделана, "
                        "правьте JSON по адресу")
    return row["u5"]


def _off_row(index):
    return {"owner": index, "menu": NO_REFERENCE, "kind": {"guid": NO_AUTO_MENU_KIND},
            "u4": NO_AUTO_MENU_TAIL[0], "u5": NO_AUTO_MENU_TAIL[1]}


def _panel_head(node, name):
    """Основной набор командной панели: `(индекс, блок действий, набор, код, вспомогательная)`."""
    head = (node.get("content") or {}).get("u1")
    actions = (head or {}).get("actions")
    sets = (actions or {}).get("button_sets")
    ref = ((head or {}).get("u8") or {}).get("guid")
    code = (head or {}).get("u9")
    if not isinstance(head, dict) or not isinstance(sets, list) or not isinstance(ref, str):
        raise EditError(f"у панели {name!r} не разобран набор кнопок: связь меню не записана")
    if (ref, code) not in [((s.get("ref_id") or {}).get("guid"), s.get("code")) for s in sets if isinstance(s, dict)]:
        raise EditError(f"набор кнопок панели {name!r} ({ref}, код {code}) не входит в её наборы: связь меню с такой панелью "
                        "платформа не писала, правьте JSON по адресу")
    return node.get(INDEX), actions, ref, code, bool(head.get("secondary"))


def _text_of(button):
    items = (button.get("text") or {}).get("items") or []
    return [i.get("text") for i in items if isinstance(i, dict)]


def _panels(doc):
    """Командные панели формы (на любой глубине) — узлы."""
    found = []
    for _name, holder in holders(doc):
        block = holder.get("elements")
        for item in (block.get("items") if isinstance(block, dict) else None) or []:
            if isinstance(item, dict) and item.get("type") == "CommandBar":
                found.append(item)
    return found


def _popups(doc):
    """Кнопки-подменю основных наборов командных панелей: `[(узел панели, кнопка, имя панели)]`."""
    out = []
    for node in _panels(doc):
        name = (node.get("name_block") or {}).get("name")
        _idx, actions, ref, code, _sec = _panel_head(node, name)
        for s in actions["button_sets"]:
            if isinstance(s, dict) and (s.get("ref_id") or {}).get("guid") == ref and s.get("code") == code:
                out += [(node, b, name) for b in s.get("buttons") or [] if isinstance(b, dict) and b.get("button_type") == POPUP]
    return out


def _submenu(node, button, name):
    """Набор подменю кнопки: `(GUID набора, код)`. Его называет запись действия панели с тем же id, что у кнопки."""
    actions = _panel_head(node, name)[1]
    gid = (button.get("id") or {}).get("guid")
    refs = [a for a in actions.get("actions") or []
            if isinstance(a, dict) and (a.get("id") or {}).get("guid") == gid and (a.get("kind") or {}).get("guid") == SUBMENU_ACTION_KIND]
    ref = (refs[0].get("action") or {}) if refs else {}
    guid, code = (ref.get("ref_id") or {}).get("guid"), ref.get("ref_code")
    sets = [((s.get("ref_id") or {}).get("guid"), s.get("code")) for s in actions["button_sets"] if isinstance(s, dict)]
    if len(refs) != 1 or not isinstance(guid, str) or (guid, code) not in sets:
        raise EditError(f"у подменю {button.get('name')!r} панели {name!r} не найден набор кнопок подменю: связь меню не записана, "
                        "правьте JSON по адресу")
    return guid, code


def _target(doc, value):
    """Меню по имени: командная панель, её подменю («Панель.Текст подменю») либо имя кнопки-подменю.
    Возвращает `(индекс панели, GUID набора, код, вспомогательная, слова)`."""
    node = None
    if value in element_names(doc):
        node = find_element(doc, value).element
        if node.get("type") == "CommandBar":
            idx, _a, ref, code, secondary = _panel_head(node, value)
            return idx, ref, code, secondary, f"панель {value}"
    found = []
    if "." in value:
        panel, text = value.split(".", 1)
        found = [(n, b, pn) for n, b, pn in _popups(doc) if pn == panel and text in _text_of(b)]
    if not found:
        found = [(n, b, pn) for n, b, pn in _popups(doc) if b.get("name") == value]
    if len(found) > 1:
        raise EditError(f"меню {value!r} называют {len(found)} подменю — какое из них, по имени не решить: назовите кнопку "
                        "по имени (`Панель_Подменю`)")
    if found:
        pnode, button, pn = found[0]
        guid, code = _submenu(pnode, button, pn)
        idx, _a, _ref, _code, secondary = _panel_head(pnode, pn)
        return idx, guid, code, secondary, f"подменю {pn}.{(_text_of(button) or [button.get('name')])[0]}"
    if node is not None:
        raise EditError(f"меню — это командная панель формы или её подменю, а {value!r} — {node.get('type')}: панель-меню ставит "
                        "add_element с template=\"CommandBar\" и box 24×24 (context_menu=true)")
    known = ", ".join([(p.get("name_block") or {}).get("name") or "?" for p in _panels(doc)]
                      + [f"{pn}.{(_text_of(b) or ['?'])[0]}" for _n, b, pn in _popups(doc)]) or "—"
    raise EditError(f"меню {value!r} в форме нет: меню — имя командной панели, подменю вида «Панель.Текст подменю» либо имя кнопки-"
                    f"подменю; есть: {known}")


def set_context_menu(doc, element, value):
    """КонтекстноеМеню элемента (`element=None` — формы): имя командной панели либо подменю или `null`/«Отсутствует».

    Пишет одну запись в `context_menu_links` на своё место по порядку владельцев; узел элемента не меняется. Флаг записи —
    текущее АвтоКонтекстноеМеню владельца: меню назначается и при снятом автоменю (запись «снятое автоменю» становится записью
    меню с флагом 0), а снятое меню при снятом автоменю возвращает запись «снятое автоменю». Одну панель можно назначить
    нескольким владельцам.
    """
    kind, index = _owner(doc, element)
    who = _who(element)
    _check_kind(kind)
    rows = read(doc)
    mine = next((row for row in rows if row["owner"] == index), None)
    if value is None or value == NO_MENU_NAME:
        if mine is None or _is_off(mine):
            return f"{who}: КонтекстноеМеню — Отсутствует (уже)"
        keep = _flag(mine, who) == 0 and kind not in NO_AUTO_ROW
        if keep:
            rows[rows.index(mine)] = _off_row(index)
        else:
            rows.remove(mine)
        write(doc, rows)
        return (f"{who}: КонтекстноеМеню → Отсутствует: "
                + ("запись связи заменена записью «снятое автоменю» (АвтоКонтекстноеМеню ☐ осталось)" if keep else "запись связи убрана")
                + f", у формы связей контекстных меню {len(rows)}")
    if not isinstance(value, str):
        raise EditError(f"КонтекстноеМеню — имя командной панели формы, подменю или null, а не {value!r}")
    menu, ref, code, secondary, what = _target(doc, value)
    auto_off = mine is not None and (_is_off(mine) or _flag(mine, who) == 0) and kind not in NO_AUTO_ROW
    flag = 0 if auto_off else MENU_FLAG
    row = {"owner": index, "menu": menu, "kind": {"guid": ref}, "u4": code, "u5": flag}
    if mine:
        rows[rows.index(mine)] = row
    else:
        _insert(rows, row)
    write(doc, rows)
    notes = ""
    if not secondary:
        notes += ("; панель не вспомогательная: связь записана, но в списке палитры такая панель стоит ли, не проверялось "
                  "(в образцах форм связи с такими панелями есть)")
    shared = [r for r in rows if r["menu"] == menu and r["owner"] != index and r["kind"]["guid"] == ref and r["u4"] == code]
    if shared:
        notes += f"; это меню служит ещё {len(shared)} владельцам (общее меню допустимо)"
    return (f"{who}: КонтекстноеМеню → {value} ({what}): связь записана (владелец — индекс {index}, панель — индекс {menu}, "
            f"флаг {flag} = АвтоКонтекстноеМеню {'☑' if flag else '☐'}), у формы связей контекстных меню {len(rows)}; "
            f"узел элемента не менялся{notes}")


def set_auto_context_menu(doc, element, value):
    """АвтоКонтекстноеМеню элемента (`element=None` — формы). Без меню — запись «снятое автоменю» (при ☐) или её отсутствие
    (при ☑); при назначенном меню меняется флаг той же записи, меню остаётся."""
    if not isinstance(value, bool):
        raise EditError(f"АвтоКонтекстноеМеню — флаг: значение true или false, а не {value!r}")
    kind, index = _owner(doc, element)
    who = _who(element)
    if kind in NO_AUTO_ROW:
        raise EditError(f"у элемента вида {kind} в палитре нет строки «АвтоКонтекстноеМеню»")
    if kind not in (FORM, *UNCHECKED_KINDS) and kind not in MEASURED:
        raise EditError(f"АвтоКонтекстноеМеню у элемента вида {kind} не проверялось. Проверено у {', '.join(MEASURED)} и у самой формы")
    rows = read(doc)
    mine = next((row for row in rows if row["owner"] == index), None)
    mark = "☑" if value else "☐"
    same = f"{who}: АвтоКонтекстноеМеню {mark} ({'уже стояла' if value else 'уже снята'}); связей контекстных меню не менялось"
    if mine is None or _is_off(mine):
        if value == (mine is None):
            return same
        if value:
            rows.remove(mine)
            write(doc, rows)
            return f"{who}: АвтоКонтекстноеМеню ☑: запись связи убрана, у формы связей контекстных меню {len(rows)}"
        _insert(rows, _off_row(index))
        write(doc, rows)
        return (f"{who}: АвтоКонтекстноеМеню ☐: записана связь (владелец — индекс {index}, меню нет, вид — снятое "
                f"автоменю), у формы связей контекстных меню {len(rows)}; командная панель контекстного меню не назначена")
    if _flag(mine, who) == int(value):
        return same
    mine["u5"] = int(value)
    write(doc, rows)
    return (f"{who}: АвтоКонтекстноеМеню {mark}: у записи связи с меню флаг стал {int(value)}, меню осталось "
            f"(индекс панели {mine['menu']}), у формы связей контекстных меню {len(rows)}")


NAMES = ("context_menu", "auto_context_menu")


UNCHECKED_WORDS = ("; у {name} платформа эту связь не проверяла: запись та же, что у проверенных видов, "
                   "а как меню и автоменю работают в предприятии у этого элемента, проверьте на форме")


def set_by_name(doc, element, name, value):
    """Вход `set_property`: имя свойства — `context_menu` (КонтекстноеМеню) или `auto_context_menu` (АвтоКонтекстноеМеню);
    `element=None` — свойство самой формы. У полей HTML-документа, PDF-документа, схем и четырёх диаграмм отчёт добавляет слова, что платформа связь для них
    не проверяла."""
    said = (set_context_menu if name == "context_menu" else set_auto_context_menu)(doc, element, value)
    if element is not None:
        kind = _owner(doc, element)[0]
        if kind in UNCHECKED_KINDS:
            said += UNCHECKED_WORDS.format(name=UNCHECKED_NAMES[kind])
    return said
