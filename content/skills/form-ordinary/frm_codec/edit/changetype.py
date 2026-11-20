"""Смена вида элемента: `change_type(element=…, to="<вид>")`.

Платформа вид элемента не меняет: в конфигураторе элемент удаляют и вставляют новый. Операция делает то же, но на месте старого
узла и с переносом того, что у нового вида есть. Узел нового вида берётся из шаблона вида `to` (в форме старой версии — сведённый к
версии формы, `old_versions`), оформление — по соседям того же вида, как у `add_element`; поверх идёт перенос.

**Что остаётся как было (сам узел старый, заменяется только содержимое):** индекс, имя, блок координат целиком — место, размер,
страница, номер на странице, порядок обхода, привязки границ и записи зависимых, флаги ручных привязок, видимость. Поэтому встречные
правила других элементов к этому элементу остаются, а связи, которые называют элемент индексом (привязка данных, контекстное меню,
«АктивизироватьПоУмолчанию», ссылка формы на кнопку), не переписываются. Порядок элемента в списке родителя тоже прежний.

**Что переносится, если у нового вида есть место и значение допустимо:**

* заголовок (`caption`), если он есть у обоих видов и ровно один;
* привязка данных — только к реквизиту формы тем же правилом, что у `bind`: вид нового элемента обязан быть из видов, у которых
  корпус привязки держит (`CORPUS_BIND_TYPES`), а тип реквизита — из подходящих виду (`DATA_FIT`); у поля ввода, флажка и
  переключателя тип поля пишет `bind(copy_type=True)` (отчёт говорит, прошёл ли он); у остальных видов тип в содержимом не
  пересобирается, и отчёт это называет. Путь по метаданным (больше одного шага) остаётся как был у видов, у которых такие пути бывают;
* события — те, чьё имя есть в перечислении событий нового вида и чья пара «вид + событие» подтверждена корпусом или кругом
  (`CORPUS_EVENT_PAIRS`, `ROUND_EVENT_PAIRS`; прочие — только под `unverified`); записи ложатся на место по коду, процедуры модуля
  не трогаются;
* общие свойства `TRANSFER` — теми же правилами и границами, что `set_property` (значение, которое у нового вида недопустимо, — в
  отчёт, а не в форму); шрифт — блоком целиком, если версия записи та же;
* связи контекстного меню: запись владельца остаётся (индекс прежний), но у видов без строки «КонтекстноеМеню» она убирается, а флаг
  «АвтоКонтекстноеМеню» у видов без этой строки становится 1; «АктивизироватьПоУмолчанию» у вида без этой строки снимается.

**Чего не переносится — отчёт:** события, которых нет у нового вида (с именами процедур), значения свойств вне `TRANSFER`, которые у
старого вида отличались от умолчания шаблона (первые десять), заголовок без места, привязка без подходящего вида или типа, связь по типу
и список выбора.

**Отказ:** тот же вид; вид без шаблона; панель, табличное поле и командная панель (вложенные элементы, колонки и кнопки не переносятся) —
и старым, и новым видом; узел со вложенными элементами. Форма при отказе не тронута.
"""
import collections
import copy

from .. import design as _design, props, templates as _templates
from . import ctxmenu as _ctxmenu, datapath as _datapath
from .base import EditError, _caption_places, control_slot, find_element, layout_block
from .data import _event_place, bind, event_code
from .elements import _old_version_node, _short, _siblings_pool, _title, _version_check
from .names import (
    ATTR_ID,
    ATTR_NAME,
    ATTR_PATTERN,
    BINDINGS,
    BIND_ELEMENT,
    BIND_PATH,
    CONTENT,
    COORDS,
    CORPUS_BIND_TYPES,
    CORPUS_EVENT_PAIRS,
    DEFAULT_CONTROL,
    ELEMENTS,
    EVENTS,
    EVENT_ACTION,
    EVENT_ITEMS,
    EVENT_NAME,
    FONT_KEYS,
    HANDLER,
    ITEMS,
    COUNT,
    INDEX,
    NAME_BLOCK,
    NO_REFERENCE,
    PATH_STEPS,
    PATTERN_KIND,
    PATTERN_TYPES,
    ROUND_EVENT_PAIRS,
    STEP_VALUE,
    TITLE_REF,
)
from .propbase import PROPERTY_OPS

# Виды, между которыми смена идёт. Остальные шаблоны — со вложенным содержимым (колонки, кнопки, страницы), которое не переносится.
NOT_SWAPPABLE = {
    "Panel": "панель — вложенные элементы и страницы не переносятся",
    "TableBox": "табличное поле — колонки не переносятся",
    "CommandBar": "командная панель — кнопки и их действия не переносятся",
}

# Пары «из → в», для которых перенос проверен тестом таблицы: узел нового вида, имя, место, привязки
# своих и встречных, данные, события, подпись, круг «собрал → разобрал» и `validate`. Прочие пары выполняются тем же правилом, а отчёт говорит,
# что пара тестом не проверялась.
CHECKED_PAIRS = (
    ("TextBox", "ComboBox"), ("ComboBox", "TextBox"), ("TextBox", "ListBox"), ("TextBox", "Label"), ("Label", "TextBox"),
    ("TextBox", "CalendarBox"), ("CalendarBox", "TextBox"), ("TextBox", "CheckBox"), ("CheckBox", "TextBox"),
    ("CheckBox", "RadioButton"), ("RadioButton", "CheckBox"), ("Label", "Button"), ("Button", "Label"),
    ("PictureBox", "Label"), ("Label", "PictureBox"),
)

# Буквы описателя типа реквизита формы, которые вид элемента принимает как данные (по `edit.datatype.CLASSES_BY_KIND` и заметкам видов).
DATA_FIT = {
    "TextBox": ("S", "N", "D", "#"),
    "CheckBox": ("B",),
    "RadioButton": ("N",),
    "ComboBox": ("B", "N", "S"),
    "Label": ("S", "D", "#"),
    "ProgressBar": ("N",),
    "TrackBar": ("N",),
    "CalendarBox": ("D",),
}
# Виды, у которых тип поля по реквизиту формы пишет `bind(copy_type=True)`.
COPY_TYPE_KINDS = ("TextBox", "CheckBox", "RadioButton")
# Виды, у которых бывают пути по метаданным (`edit.datapath.KINDS_BY_PATH`).
PATH_KINDS = ("TextBox", "ComboBox", "CheckBox", "Label")

# Общие свойства, которые переносятся через `set_property` (у каждого свои границы корпуса и платформы).
TRANSFER = ("enabled", "tool_tip", "transparent", "back_color", "text_color", "border_color", "border", "field_back_color",
            "field_text_color", "button_back_color", "button_text_color", "read_only", "horizontal_align", "vertical_align")
# Имена, которые в отчёт «не перенесено» не идут: служебные и те, у которых своя операция.
QUIET = frozenset({"mark", "type", "index", "content_kind", "version", "record_version", "source", "overrides", "scale"})
QUIET_TRAIL = frozenset(FONT_KEYS) | {EVENTS, "pattern", "events"}
LEFT_LIMIT = 10


def _name_of(node):
    return (node.get(NAME_BLOCK) or {}).get("name")


def _fields(node):
    return list(props.fields(node, "Element", stop=tuple(props.ELEMENT_STOP) + tuple(PROPERTY_OPS)))


def _by_name(fields, name):
    return [found for found in fields if getattr(found.slot, "name", None) == name and found.key == name]


def _pristine(kind):
    """Значения полей шаблона вида по путям ключей: `{путь: значение}` — «умолчание платформы» для сравнения."""
    node = _templates.element(kind)
    return {found.trail: found.holder.get(found.key) for found in _fields(node)}


def _caption_of(node):
    found = list(_caption_places(node.get(CONTENT) or {}))
    return found[0][1] if len(found) == 1 else None


def _text_of(block):
    items = block.get("items") if isinstance(block, dict) else None
    return " / ".join(str(i.get("text")) for i in items or [] if isinstance(i, dict)) or "пусто"


def _events(old, node, new_kind, unverified, said, left):
    """Обработчики старого вида → список нового: только имена из перечисления нового вида и подтверждённые пары."""
    block = (old.get(CONTENT) or {}).get(EVENTS)
    rows = block.get(EVENT_ITEMS) if isinstance(block, dict) else None
    rows = [r for r in rows or [] if isinstance(r, dict)]
    if not rows:
        return
    target = (node.get(CONTENT) or {}).get(EVENTS)
    items = target.get(EVENT_ITEMS) if isinstance(target, dict) else None

    def proc(row):
        spec = row.get(EVENT_ACTION)
        return (spec.get(HANDLER) if isinstance(spec, dict) else None) or "?"

    moved = []
    for row in rows:
        name = row.get(EVENT_NAME)
        label = f"{name} → {proc(row)}"
        if not isinstance(items, list):
            left.append(f"событие {label}: у вида {new_kind} событий нет")
        elif event_code(new_kind, name) is None or isinstance(name, int):
            left.append(f"событие {label}: у вида {new_kind} такого события нет")
        elif (new_kind, name) not in CORPUS_EVENT_PAIRS and (new_kind, name) not in ROUND_EVENT_PAIRS and not unverified:
            left.append(f"событие {label}: пара {new_kind}.{name} в образцах форм и среди проверенного платформой не встречалась (unverified=True перенесёт)")
        else:
            at = _event_place(new_kind, items, name)
            items.insert(at, copy.deepcopy(row))
            moved.append(label)
    if moved:
        target["count"] = len(items)
        said.append("события: " + ", ".join(moved))


def _data(doc, old, node, kind, new_kind, unverified, said, left):
    """Судьба строки привязки данных: `(оставить, имя реквизита для copy_type)`; отчёт — в `said`/`left`."""
    attributes = doc.get("attributes")
    bindings = attributes.get(BINDINGS) if isinstance(attributes, dict) else None
    rows = bindings.get("items") if isinstance(bindings, dict) else None
    row = next((r for r in rows or [] if isinstance(r, dict) and r.get(BIND_ELEMENT) == old.get(INDEX)), None)
    if row is None:
        return None
    if new_kind not in CORPUS_BIND_TYPES or new_kind == "TableBox":
        if not unverified:
            rows.remove(row)
            left.append(f"привязка данных снята: привязок данных у вида {new_kind} образцы форм не держат "
                        "(unverified=True оставит строку привязки как была)")
            return None
        said.append(f"привязка данных оставлена по unverified: у вида {new_kind} образцы форм привязок не держат")
        return None
    path = row.get(BIND_PATH)
    steps = path.get(PATH_STEPS) if isinstance(path, dict) else None
    if isinstance(steps, list) and len(steps) == 1 and isinstance(steps[0], dict):
        _attrs, attr_rows = _datapath._attributes(doc)
        attr = next((r for r in attr_rows if _datapath._id_of(r) == steps[0].get(STEP_VALUE)), None)
        if attr is None:
            return None  # висячая привязка: платформа её терпит, операция её не трогает
        pattern = attr.get(ATTR_PATTERN)
        types = pattern.get(PATTERN_TYPES) if isinstance(pattern, dict) else None
        letters = [b.get(PATTERN_KIND) for b in types if isinstance(b, dict)] if isinstance(types, list) else []
        fit = DATA_FIT.get(new_kind)
        name = attr.get(ATTR_NAME)
        if fit is None or len(letters) != 1 or letters[0] not in fit:
            reason = (f"у вида {new_kind} для привязки подходящих типов не определено" if fit is None else
                      f"тип реквизита формы {name!r} — {'+'.join(map(str, letters)) or 'пустой'}, а виду {new_kind} подходит {', '.join(fit)}")
            if not unverified:
                rows.remove(row)
                left.append(f"привязка к реквизиту формы {name!r} снята: {reason} (unverified=True оставит строку как была)")
                return None
            said.append(f"привязка к реквизиту формы {name!r} оставлена по unverified: {reason}")
            return None
        if new_kind in COPY_TYPE_KINDS:
            return name
        said.append(f"привязка к реквизиту формы {name!r} оставлена; тип в содержимом поля вида {new_kind} не пересобирался "
                    "(у поля ввода, флажка и переключателя его пишет bind copy_type, у остальных видов такая пара не проверялась)")
        return None
    if kind in PATH_KINDS and new_kind in PATH_KINDS:
        said.append("привязка данных (путь по метаданным) оставлена как была; тип поля не пересобирался — класс типа "
                    "и вид поля сверяет `bind(data=…)` на новом элементе")
        return None
    if not unverified:
        rows.remove(row)
        left.append(f"привязка данных (путь по метаданным) снята: у видов {kind} и {new_kind} такие пути вместе не проверялись "
                    "(unverified=True оставит строку как была)")
    else:
        said.append("привязка данных (путь по метаданным) оставлена по unverified")
    return None


def _links(doc, place, new_kind, left, said):
    """Связи, которые называют элемент индексом: контекстное меню, «АктивизироватьПоУмолчанию», ссылка формы на кнопку."""
    from .setprop import NO_DEFAULT_CONTROL  # edit.setprop сам импортирует edit.elements: наверху файла получился бы круг
    index = place.index
    block = doc.get("context_menu_links")
    if isinstance(block, dict) and block.get("count"):
        try:
            rows = _ctxmenu.read(doc)
        except EditError as e:
            left.append(f"связи контекстных меню не разобраны, остались как были: {e}")
            rows = None
        if rows is not None and any(r["owner"] == index for r in rows):
            kept, words = [], []
            has_menu = new_kind not in _ctxmenu.NO_MENU_ROW
            has_auto = new_kind not in _ctxmenu.NO_AUTO_ROW
            for row in rows:
                if row["owner"] != index:
                    kept.append(row)
                    continue
                if _ctxmenu._is_off(row):
                    if has_auto:
                        kept.append(row)
                    else:
                        words.append("запись «снятое автоменю» убрана: у вида нет строки АвтоКонтекстноеМеню")
                elif not has_menu:
                    if has_auto and row["u5"] == 0:
                        kept.append(_ctxmenu._off_row(index))
                        words.append("меню снято (у вида нет строки КонтекстноеМеню), «АвтоКонтекстноеМеню» ☐ осталось")
                    else:
                        words.append("меню снято: у вида нет строки КонтекстноеМеню")
                else:
                    if not has_auto and row["u5"] != 1:
                        row = dict(row, u5=1)
                        words.append("флаг АвтоКонтекстноеМеню стал 1: у вида такой строки нет")
                    if new_kind not in _ctxmenu.MEASURED:
                        words.append(f"связь меню у вида {new_kind} платформа не проверяла")
                    kept.append(row)
            if kept != rows:
                _ctxmenu.write(doc, kept)
            if words:
                said.append("контекстное меню: " + "; ".join(words))
            else:
                said.append("связь контекстного меню осталась (индекс прежний)")
    try:
        layout = layout_block(place.holder, need=False)
    except EditError:
        layout = None
    control = layout.get(DEFAULT_CONTROL) if isinstance(layout, dict) else None
    page = control_slot(layout, place.page) if isinstance(place.page, int) else None
    if isinstance(control, list) and isinstance(page, int) and 0 <= page < len(control) and control[page] == index:
        if new_kind in NO_DEFAULT_CONTROL:
            control[page] = NO_REFERENCE
            left.append(f"«АктивизироватьПоУмолчанию» снято: у вида {new_kind} такой строки нет")
        else:
            said.append("«АктивизироватьПоУмолчанию» осталось (индекс прежний)")
    title = _title(doc)
    if isinstance(title, dict) and title.get(TITLE_REF) == index and new_kind != "Button":
        title[TITLE_REF] = NO_REFERENCE
        left.append("ссылка формы на кнопку (form.title) сброшена в «ссылки нет»: новый вид — не кнопка")


def _font(old, node, said, left):
    """Шрифт целиком, если запись той же версии; иначе — в отчёт."""
    old_fields, new_fields = _fields(old), _fields(node)
    for key in FONT_KEYS:
        olds, news = _by_name(old_fields, key), _by_name(new_fields, key)
        if len(olds) != 1 or len(news) != 1:
            continue
        was, now = olds[0].holder.get(key), news[0].holder.get(key)
        pristine = _pristine(old.get("type")).get(olds[0].trail)
        if not isinstance(was, dict) or was == now or was == pristine:
            continue
        theirs = now.get("version") if isinstance(now, dict) else None
        if was.get("version") != theirs:
            left.append(f"шрифт {key}: версия записи у видов разная ({was.get('version')} / {theirs}), блок не переносился")
            continue
        news[0].holder[key] = copy.deepcopy(was)
        said.append(f"шрифт {key} перенесён блоком целиком")


def _properties(doc, name, old, kind, new_kind, unverified, said, left):
    """Общие свойства `TRANSFER` через `set_property`; отказ значения идёт в отчёт, форму не останавливает."""
    old_fields = _fields(old)
    pristine = _pristine(kind)
    moved = []
    for prop in TRANSFER:
        found = _by_name(old_fields, prop)
        if not found:
            continue
        values = {repr(f.holder.get(f.key)) for f in found}
        if len(values) != 1:
            left.append(f"{prop}: у старого вида значение записано в двух местах по-разному — не переносилось")
            continue
        value = found[0].holder.get(found[0].key)
        if value == pristine.get(found[0].trail):
            continue  # умолчание шаблона старого вида — переносить нечего
        try:
            from .setprop import set_property
            set_property(doc, name, prop, copy.deepcopy(value), unverified=unverified)
            moved.append(prop)
        except EditError as e:
            left.append(f"{prop} = {_short(value)}: {str(e).split(';')[0][:160]}")
    if moved:
        said.append("свойства: " + ", ".join(moved))


def _leftovers(old, kind, left):
    """Значения полей старого вида, отличные от умолчания шаблона и не названные ни переносом, ни отказом: первые `LEFT_LIMIT`."""
    pristine = _pristine(kind)
    out = []
    for found in _fields(old):
        name = getattr(found.slot, "name", None)
        if found.trail[0] != CONTENT or name is None or name in QUIET or name in TRANSFER or set(found.trail) & QUIET_TRAIL:
            continue
        if any(part in TRANSFER for part in found.trail):
            continue
        if found.key != name or hasattr(found.slot, "fields"):
            continue
        value = found.holder.get(found.key)
        if isinstance(value, dict) or found.trail not in pristine or value == pristine[found.trail]:
            continue
        out.append(f"{name} = {_short(value)}")
    if out:
        more = f" и ещё {len(out) - LEFT_LIMIT}" if len(out) > LEFT_LIMIT else ""
        left.append("значения старого вида вне переносимых: " + "; ".join(out[:LEFT_LIMIT]) + more)


def change_type(doc, element=None, to=None, unverified=False, siblings=None):
    """Смена вида элемента на месте: удаление и вставка нового вида с тем же именем, местом, привязками, данными, событиями и
    общими свойствами (что именно и что идёт в отчёт — в шапке `frm_codec.edit.changetype`).

    `element` — имя элемента, `to` — вид нового (имя шаблона: `TextBox`, `ComboBox`, `CheckBox`, `RadioButton`, `ListBox`,
    `CalendarBox`, `ProgressBar`, `TrackBar`, `PictureBox`, `Label`, `Button`, `GroupBox`, `Splitter`, `SpreadsheetDocumentField`,
    `TextDocumentField`). Панель, табличное поле и командная панель — отказ в обе стороны. `unverified=True` разрешает перенос
    событий и привязок, которых корпус для нового вида не подтверждает, и версию общего блока, отличную от версии формы.
    """
    if element is None or to is None:
        raise EditError("change_type — элемент (element) и вид, который ему нужен (to)")
    place = find_element(doc, element)
    old = place.element
    kind = old.get("type")
    if to == kind:
        raise EditError(f"элемент {element!r} уже вида {kind}: менять нечего")
    for what, label in ((kind, "старого"), (to, "нового")):
        if what in NOT_SWAPPABLE:
            raise EditError(f"вид {what} {label} элемента не меняется: {NOT_SWAPPABLE[what]}. Платформа тоже не меняет вид — "
                            "элемент удаляют и вставляют новый; здесь это remove_element и add_element с нужным вложенным")
    if any(isinstance(item, dict) for item in ((old.get(ELEMENTS) or {}).get(ITEMS) or [])):
        raise EditError(f"у элемента {element!r} есть вложенные элементы: их индексы сквозные, переносить их нельзя")
    try:
        node = _templates.element(to)
    except ValueError as e:
        raise EditError(f"вида {to!r} нет: {e}") from None
    if not isinstance(old.get(COORDS), dict) or set(old[COORDS]) != set(node[COORDS]):
        raise EditError(f"блок координат элемента {element!r} устроен не так, как у шаблона вида {to}: перенос места не проверялся")
    node, said_old = _old_version_node(doc, to, node, unverified)
    said_version = _version_check(doc, _design.node_versions(node), "change_type", unverified, kind=to)
    snapshot = copy.deepcopy(doc)
    try:
        said_design = _design.by_neighbours(doc, node, "шаблона", _siblings_pool(siblings))
        node[INDEX] = old[INDEX]
        node[NAME_BLOCK] = copy.deepcopy(old[NAME_BLOCK])
        node[COORDS] = copy.deepcopy(old[COORDS])
        said, left = [], []
        _events(old, node, to, unverified, said, left)
        was, now = _caption_of(old), _caption_of(node)
        if was is not None and now is not None:
            now.clear()
            now.update(copy.deepcopy(was))
            said.append(f"заголовок: {_text_of(was)!r}")
        elif was is not None:
            left.append(f"заголовок {_text_of(was)!r}: у вида {to} его нет")
        _font(old, node, said, left)
        copy_attr = _data(doc, old, node, kind, to, unverified, said, left)
        place.items[place.at] = node
        _links(doc, place, to, left, said)
        if copy_attr is not None:
            bindings = doc["attributes"][BINDINGS]["items"]
            at = next(i for i, r in enumerate(bindings) if r.get(BIND_ELEMENT) == node[INDEX])
            row = bindings.pop(at)
            try:
                bind(doc, element, attribute=copy_attr, copy_type=True)
                said.append(f"привязка данных: реквизит формы {copy_attr!r}, тип поля — по реквизиту (bind copy_type)")
            except EditError as e:
                bindings.insert(at, row)
                left.append(f"тип поля по реквизиту {copy_attr!r} не записан, строка привязки осталась: {str(e).split(';')[0][:200]}")
        _properties(doc, element, old, kind, to, unverified, said, left)
        _leftovers(old, kind, left)
        if (kind, to) not in CHECKED_PAIRS:
            said.append(f"пара {kind} → {to} тестом таблицы не проверялась: перенос выполнен тем же правилом")
    except EditError:
        doc.clear()
        doc.update(snapshot)
        raise
    tail = "".join(f"; {w}" for w in (said_old, said_design, said_version) if w)
    return (f"{element}: вид {kind} → {to}, индекс {node[INDEX]}, место, привязки (свои и встречные), порядок обхода прежние"
            + ("; перенесено — " + "; ".join(said) if said else "")
            + ("; НЕ ПЕРЕНЕСЕНО — " + "; ".join(left) if left else "") + tail)
