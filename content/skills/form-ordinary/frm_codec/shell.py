"""Исходная форма — форма, созданная конструктором платформы, — как источник элементов для переиспользования.

`generate` оставляет элемент исходной формы, **привязанный к тем же данным, что блок описания**: движок меняет только место, размер, привязки краёв и страницу
(`edit.move_element`). Ищутся видимые элементы ПРЯМО НА ФОРМЕ (вложенные в панели и рамки не переиспользуются, такие элементы создаются заново):

* **поле ввода и флажок** — по привязке данных: реквизит объекта (`("object", Имя)`, в том числе стандартный) либо реквизит формы (`("form", Имя)`);
  одному реквизиту — один элемент (первый при обходе);
* **надпись поля** — ближайшая слева несвязанная надпись на той же высоте (правило `describe`: зазор не больше `MAX_LABEL_GAP`, нахлёст не больше
  `LABEL_OVERLAP`, общая высота не меньше половины меньшей), одна надпись — одному полю;
* **табличное поле** — по привязке к табличной части; **колонки** — по пути данных (`ShellColumn.key`: имя реквизита ТЧ, `НомерСтроки` у пути `[-2]`;
  колонка без пути или чужого вида ключа не имеет); **командная панель таблицы** — панель того же родителя, источник действий которой — индекс
  таблицы (`name_block.action_source`); панели с именами платформы для формы (`FORM_BAR_NAMES`) панелью таблицы не берутся.

Правило привязки данных (`resolve_binding`) одно на `describe` и `generate`."""
import dataclasses

from . import layout, lstring, metadata
from .edit import base as ed_base, columns as ed_columns, datapath
from .edit.names import ATTR_HEAD, ATTR_NAME, CONTENT

# Надпись и поле пары: надпись кончается левее начала поля (допуск на нахлёст 3 px), пересекается с полем по вертикали не меньше чем наполовину
# меньшей высоты и не дальше этого зазора (надпись дальше — обычно заголовок раздела, а не подпись).
MAX_LABEL_GAP = 40
LABEL_OVERLAP = 3
FIELD_TYPES = ("TextBox", "CheckBox")
# Имена панелей формы у платформы: верхняя и нижняя. Такая панель — панель ФОРМЫ, даже если её источник действий — таблица.
FORM_BAR_NAMES = ("ДействияФормы", "ОсновныеДействияФормы")


def _int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _dict(value):
    return value if isinstance(value, dict) else {}


def overlap(a_top, a_bottom, b_top, b_bottom):
    return min(a_bottom, b_bottom) - max(a_top, b_top)


def _text(block):
    """Видимый текст локализованной строки (`lstring`) без крайних пробелов либо `None`."""
    text = lstring.visible_text(block)
    return text.strip() if text is not None and text.strip() else None


def caption_of(node):
    """Подпись элемента: у него она одна, иначе (нет, несколько, узла нет) — `None`."""
    content = node.get(CONTENT) if isinstance(node, dict) else None
    found = list(ed_base._caption_places(content)) if isinstance(content, dict) else []
    return _text(found[0][1]) if len(found) == 1 else None


_NO_TEXT = " \t :"


def same_text(a, b):
    """Подписи равны без регистра, лишних пробелов и конечного двоеточия."""
    def norm(text):
        return " ".join(text.casefold().split()).rstrip(_NO_TEXT)
    return norm(a) == norm(b)


def find_label(field, labels):
    """Надпись пары поля ввода среди несвязанных `labels` либо `None`: ближайшая слева по зазору."""
    best = None
    for cand in labels:
        gap = field.box[0] - cand.box[2]
        if gap < -LABEL_OVERLAP or gap > MAX_LABEL_GAP:
            continue
        height = min(cand.box[3] - cand.box[1], field.box[3] - field.box[1])
        if height <= 0 or overlap(cand.box[1], cand.box[3], field.box[1], field.box[3]) * 2 < height:
            continue
        if best is None or gap < best[0]:
            best = (gap, cand)
    return best[1] if best is not None else None


def resolve_binding(steps, main, form_attrs, obj):
    """Что называет путь привязки элемента: `(вид, имя)`.

    * `("none", None)` — привязки нет; `("form", Имя)` — реквизит формы; `("object", Имя)` — реквизит или стандартный реквизит объекта;
    * `("table", Имя)` — табличная часть; `("object_unresolved", None)` — путь на объект, а объекта (выгрузки) нет; `("other", None)` — иное.

    `steps` — шаги пути (`None` — привязки нет), `main` — номер основного реквизита формы, `form_attrs` — `{номер: имя}` реквизитов формы,
    `obj` — `metadata.MdObject` либо `None`."""
    if steps is None:
        return ("none", None)
    if len(steps) == 1 and steps[0].get("u0") != main and steps[0].get("u0") in form_attrs:
        name = form_attrs[steps[0]["u0"]]
        return ("form", name) if name else ("other", None)
    if len(steps) == 2 and main is not None and steps[0].get("u0") == main:
        step = steps[1]
        if obj is None:
            return ("object_unresolved", None)
        ref = step.get("u1")
        if step.get("u0") == 0 and isinstance(ref, dict):
            guid = ref.get("guid")
            attr = next((a for a in obj.attributes if a.uuid == guid), None)
            if attr:
                return ("object", attr.name)
            table = next((t for t in obj.tables if t.uuid == guid), None)
            return ("table", table.name) if table else ("other", None)
        if _int(step.get("u0")) and step["u0"] < 0:
            name = next((n for n in obj.standard if metadata.STANDARD_IDS[n] == step["u0"]), None)
            return ("object", name) if name else ("other", None)
    return ("other", None)


@dataclasses.dataclass
class ShellField:
    """Поле ввода или флажок исходной формы и его надпись."""
    key: tuple
    name: str
    type: str
    index: int
    node: dict
    label: object = None
    box: tuple = None  # место поля `(лево, верх, право, низ)`
    right_coef: object = None  # коэффициент правой границы (`layout.coefficients`): 1 — идёт с правым краем формы, 0 — остаётся на месте; `None` — в цикле правил
    left_coef: object = None  # коэффициент левой границы: «растягивается» — рост ширины `cR − cL`; поле, у которого сдвигаются обе границы, не растягивается

    @property
    def behaviour(self):
        """Поведение поля при растяжении окна (`layout.horizontal_behaviour`): `layout.GROWS`, `STANDS`, `MOVES`, `PARTLY` (слова — `layout.behaviour_words`); `None` — в цикле правил."""
        return layout.horizontal_behaviour(self.left_coef, self.right_coef)


@dataclasses.dataclass
class ShellColumn:
    key: object  # имя реквизита ТЧ, `НомерСтроки` у пути `[-2]`, `None` — путь не распознан (колонка лишняя)
    name: str
    slot: object = None


@dataclasses.dataclass
class ShellTable:
    """Табличное поле исходной формы на табличную часть, его колонки и панель."""
    ts: str
    name: str
    index: int
    node: dict
    columns: list
    bar: object = None          # `layout.Item` командной панели таблицы либо `None`


@dataclasses.dataclass
class Shell:
    lists: list = dataclasses.field(default_factory=list)  # табличные поля ФОРМЫ СПИСКА: привязаны к основному реквизиту — динамическому списку объекта
    trees: list = dataclasses.field(default_factory=list)  # дерево групп формы списка иерархического справочника: табличное поле на ВТОРОЙ реквизит-список
                                                                 # того же объекта (тип категории `List`; `ts` — имя этого реквизита)
    fields: dict = dataclasses.field(default_factory=dict)
    tables: dict = dataclasses.field(default_factory=dict)
    form_width: int = None  # ширина исходной формы («флажок во всю строку» считается от неё)
    nested: dict = dataclasses.field(default_factory=dict)  # элементы в панелях и рамках исходной формы с теми же данными (не переиспользуются):
                                                                 # ключ реквизита или `("table", имя ТЧ)` → (имя элемента, имя родителя)


def scan(doc, obj):
    """Что исходная форма `doc` даёт для переиспользования: `Shell`. `obj` — объект выгрузки либо `None` (тогда поля на реквизиты объекта и таблицы
    не находятся)."""
    form = layout.read(doc)
    attributes, rows = datapath._attributes(doc)
    head = _dict(attributes.get(ATTR_HEAD))
    main = head.get(datapath.MAIN_ATTRIBUTE_ID)
    main = main if _int(main) else None
    form_attrs = {}
    for row in rows:
        ident = datapath._id_of(row)
        if _int(ident):
            form_attrs[ident] = row.get(ATTR_NAME) if isinstance(row.get(ATTR_NAME), str) else None
    bound = {}
    for row in datapath.binding_rows(attributes):
        steps = _dict(row.get("path")).get("steps")
        element = row.get(datapath.BIND_ELEMENT)
        if _int(element) and isinstance(steps, list) and element not in bound:
            bound[element] = [s if isinstance(s, dict) else {} for s in steps]
    shell = Shell(form_width=form.width)
    list_main = _is_list_main(rows, main, obj)
    list_attrs = _list_attributes(rows, main, obj) if list_main else {}
    coefs = layout.coefficients(form, hide=False)
    items = [i for i in form.holders[0].children if i.visible and i.name]      # только элементы прямо на форме (не вложенные в панели)
    labels = [i for i in items if i.type == "Label" and i.index not in bound]
    for item in items:
        kind, name = resolve_binding(bound.get(item.index), main, form_attrs, obj)
        if item.type == "TableBox" and list_main and _is_main_step(bound.get(item.index), main):
            shell.lists.append(ShellTable(LIST_KEY, item.name, item.index, item.node, _list_columns(item.node, obj), None))    # у списка панель формы, своей панели таблицы нет
        elif item.type == "TableBox" and list_main and _step_of(bound.get(item.index)) in list_attrs:
            shell.trees.append(ShellTable(list_attrs[_step_of(bound.get(item.index))], item.name, item.index, item.node, [], None))    # дерево групп: колонок для описания не несёт
        elif item.type in FIELD_TYPES and kind in ("object", "form") and (kind, name) not in shell.fields:
            label = None
            if item.type == "TextBox":
                label = find_label(item, labels)
                if label is not None:
                    labels.remove(label)
            found = coefs.get(item.index)
            shell.fields[(kind, name)] = ShellField((kind, name), item.name, item.type, item.index, item.node, label, tuple(item.box),
                                                    found[3] if found else None, found[2] if found else None)
        elif item.type == "TableBox" and kind == "table" and name not in shell.tables:
            bars = [b for b in items if b.type == "CommandBar" and b.name not in FORM_BAR_NAMES
                    and _dict(b.node.get("name_block")).get("action_source") == item.index]
            bar = nearest_bar(item, bars) if bars else None
            shell.tables[name] = ShellTable(name, item.name, item.index, item.node, _columns(item.node, obj, name), bar)
    for holder in form.holders.values():
        if holder is form.holders[0]:
            continue
        for item in holder.children:
            if not (item.visible and item.name):
                continue
            kind, name = resolve_binding(bound.get(item.index), main, form_attrs, obj)
            key = (kind, name) if item.type in FIELD_TYPES and kind in ("object", "form") else (
                ("table", name) if item.type == "TableBox" and kind == "table" else None)
            if key is not None:
                shell.nested.setdefault(key, (item.name, holder.name))
    return shell


LIST_KEY = "Список"       # ключ таблицы списка у `Shell.tables` и в блоке `table` описания


def _is_main_step(steps, main):
    """Путь привязки из ОДНОГО шага — основной реквизит формы (табличное поле на динамический список)."""
    return main is not None and isinstance(steps, list) and len(steps) == 1 and steps[0].get("u0") == main


def _step_of(steps):
    """Номер реквизита формы, если путь привязки — ОДИН шаг на реквизит (`u0`), иначе `None`."""
    if isinstance(steps, list) and len(steps) == 1 and isinstance(steps[0], dict) and _int(steps[0].get("u0")):
        return steps[0]["u0"]
    return None


def _list_attributes(rows, main, obj):
    """Прочие реквизиты формы того же типа-списка, что основной, — `{номер: имя}`: у формы списка иерархического справочника второй реквизит
    (тип категории `List` того же объекта) — дерево групп слева от списка."""
    out = {}
    for row in rows:
        ident = datapath._id_of(row)
        if ident != main and _int(ident) and datapath._type_guid(row) == obj.type_ids.get("List") and isinstance(row.get(ATTR_NAME), str):
            out[ident] = row[ATTR_NAME]
    return out


def _is_list_main(rows, main, obj):
    """Основной реквизит формы — динамический список ЭТОГО объекта (тип категории `List` из выгрузки)."""
    if obj is None or main is None:
        return False
    row = next((r for r in rows if datapath._id_of(r) == main), None)
    guid = datapath._type_guid(row) if row is not None else None
    return bool(guid) and guid == obj.type_ids.get("List")


def list_column_key(path, name, obj):
    """Ключ колонки списка по пути данных: стандартная — имя стандартного реквизита объекта (`[-1]` — только колонка «Картинка»), реквизит — его имя
    по `[0, {guid}]`; `None` — путь не распознан (колонка лишняя)."""
    if path == [-1]:
        return "Картинка" if name == "Картинка" else None
    if isinstance(path, list) and len(path) == 1 and isinstance(path[0], int):
        std = next((n for n in (obj.standard if obj is not None else ()) if metadata.STANDARD_IDS[n] == path[0]), None)
        return std
    if isinstance(path, list) and len(path) == 2 and path[0] == 0 and isinstance(path[1], dict) and obj is not None:
        attr = next((a for a in obj.attributes if a.uuid == path[1].get("guid")), None)
        return attr.name if attr is not None else None
    return None


def _list_columns(node, obj):
    """Колонки таблицы списка исходной формы: ключ — по пути данных (`list_column_key`)."""
    out = []
    for column in _dict(ed_columns.columns_of(node)).get(ed_columns.COLUMN_ITEMS) or []:
        if not isinstance(column, dict):
            continue
        name = ed_columns._column_name(column)
        base = ed_columns._column_base(column)
        path = _dict(base).get(datapath.COLUMN_PATH)
        key = list_column_key(path, name, obj) if (column.get(ed_columns.COLUMN_TYPE) or {}).get("guid") == ed_columns.schema.LIST_COLUMN else None
        out.append(ShellColumn(key, name, datapath.COLUMN_PATH))
    return out


def nearest_bar(table, bars):
    """Панель таблицы из нескольких с источником — этой таблицей: ближайшая к таблице (зазор между рамками по обеим осям), при равенстве — та, что над
    таблицей (как ставит `generate`: вплотную сверху), потом — раньше по порядку. Одно правило для `scan` и `describe` (блок `table` показывает одну
    панель, остальные — в `skipped`)."""
    def key(at_bar):
        at, bar = at_bar
        gap_x = max(bar.box[0] - table.box[2], table.box[0] - bar.box[2], 0)
        gap_y = max(bar.box[1] - table.box[3], table.box[1] - bar.box[3], 0)
        return (gap_x + gap_y, 0 if bar.box[3] <= table.box[1] + 1 else 1, at)
    return min(enumerate(bars), key=key)[1]


def _columns(node, obj, ts_name):
    """Колонки таблицы исходной формы: ключ — по пути данных."""
    ts = next((t for t in obj.tables if t.name == ts_name), None) if obj is not None else None
    out = []
    block = ed_columns.columns_of(node)
    for column in _dict(block).get(ed_columns.COLUMN_ITEMS) or []:
        if not isinstance(column, dict):
            continue
        name = ed_columns._column_name(column)
        key, slot = None, None
        base = ed_columns._column_base(column)
        if (column.get(ed_columns.COLUMN_TYPE) or {}).get("guid") == ed_columns.schema.TABULAR_COLUMN and isinstance(base, dict) and ts is not None:
            for slot_name in (datapath.COLUMN_PATH, ed_columns.COLUMN_CHECK_PATH):
                path = base.get(slot_name)
                if path == [datapath.ROW_NUMBER_ID] and slot_name == datapath.COLUMN_PATH:
                    key, slot = datapath.ROW_NUMBER, slot_name
                elif isinstance(path, list) and len(path) == 2 and path[0] == 0 and isinstance(path[1], dict):
                    attr = ts.attribute_by_uuid(path[1].get("guid"))
                    if attr is not None:
                        key, slot = attr.name, slot_name
                if key is not None:
                    break
        out.append(ShellColumn(key, name, slot))
    return out
