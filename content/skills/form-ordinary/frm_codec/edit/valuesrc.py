"""Реквизиты формы «таблица / дерево / список значений» и табличное поле на них.

Тип реквизита формы — блок `{"#", GUID}` в описателе. Три GUID типов платформы карта читает именами (`schema.GUID_NAMES["AttributeType"]`):
`ValueTable` (таблица значений), `ValueTree` (дерево значений), `ValueList` (список значений). Запись в файле — прежний GUID.

Что пишет конструктор на таком реквизите (перепись основного снимка корпуса, 4 993 формы; числа — в `FORMAT-sources.md`, строка `PatternType.Ref/1`):

* **таблица значений** — табличное поле (`TableBox`), чей описатель типа (`u1` содержимого) называет `acf6192e-…`, источник данных (`u3`) —
  `342cf854-…` вида 5, биты слова флагов `0x20` и `0x200` сняты (563 привязки из 563; 647 полей с таким описателем, ни у одного этих битов нет);
* **дерево значений** — то же поле с описателем `e603c0f2-…`, источником `9ab3fa70-…` вида 4 (`{4, 1, 1, {0}}` у 184 полей из 232, `{4, 1, 0, {0}}` у 48),
  двумя поднятыми битами слова флагов (`0x20`, `0x200`; у всех 235 полей с этим описателем) и колонкой «Иерархия» (флаг `show_hierarchy`) —
  первой у 164 деревьев из 194 привязанных;
* **список значений** — поле списка (`ListBox`), содержимое ничем не отличается от шаблона; привязка — запись таблицы привязок реквизита.
  Табличное поле на список значений (колонки `fbacf851-…`, 29 полей корпуса) редактор не ставит: образец такой колонки не заведён.

Колонки таблицы и дерева значений — колонки вида `737535a4-…`. Колонке можно задать: имя (оно же Данные), заголовок, тип (`S`, `N`, `D`, `B`), ширину, выравнивание, формат
(`ЧДЦ=3`, `ДФ=dd.MM.yyyy`). Колонки и их типы хранит запись колонки в табличном поле (`value_type` головы и описатель её поля ввода); у реквизита формы в строке
реквизита колонок нет — там только тип `ValueTable`. Платформа создаёт колонки при открытии формы по этим записям, и `Колонки.Добавить` кода с тем же именем отказывает
(«Неверное имя колонки»): код такой таблицы только заполняет строки.
"""
import copy

from .. import schema
from .base import EditError, find_element
from .names import CONTENT, TABLE_SOURCE, TABLE_TYPE

VALUE_TABLE, VALUE_TREE, VALUE_LIST = "ValueTable", "ValueTree", "ValueList"
NAMES = tuple(schema.GUID_NAMES["AttributeType"])
GUID_OF = schema.GUID_NAMES["AttributeType"]
# Два бита слова флагов табличного поля (`u2/u1/flags/rest`), поднятые у всех полей с описателем дерева значений корпуса и снятые у всех полей с описателем таблицы.
TREE_BITS = 0x20 | 0x200
# Источник данных дерева значений — дословно как у большинства деревьев корпуса: 184 из 232 полей с источником `9ab3fa70-…`.
TREE_SOURCE = {"u0": {"guid": "9ab3fa70-d2e0-4e44-baac-730682272ed2"}, "u1": {"u0": 4, "u1": 1, "u2": 1, "u3": [0]}}
TREE_FORM_VERSION = 16       # дерево значений в корпусе проверено на формах поколения 16; у форм 10, 13, 15 узел-образец не сводился
ALIGNS = ("Auto", "Left", "Center", "Right")
COLUMN_KEYS = ("name", "header", "type", "width", "align", "header_align", "format", "hierarchy")


def attribute_source(row):
    """Имя типа платформы у реквизита формы — `ValueTable`, `ValueTree`, `ValueList`, если описатель — единственный блок такого типа; иначе `None`."""
    pattern = row.get("pattern") if isinstance(row, dict) else None
    types = pattern.get("types") if isinstance(pattern, dict) else None
    if not isinstance(types, list) or len(types) != 1 or not isinstance(types[0], dict) or types[0].get("kind") != "#":
        return None
    value = types[0].get("value_type")
    return value if isinstance(value, str) and value in NAMES else None


def _raw_type(node):
    content = node.get(CONTENT) if isinstance(node, dict) else None
    raw = content.get(TABLE_TYPE) if isinstance(content, dict) else None
    ok = isinstance(raw, list) and len(raw) == 2 and isinstance(raw[1], list) and len(raw[1]) == 2 and isinstance(raw[1][1], dict)
    return raw if ok else None


def table_source(node):
    """Тип платформы, на который указывает описатель табличного поля (`u1` содержимого): `ValueTable`, `ValueTree`, `ValueList` или `None`."""
    raw = _raw_type(node)
    if raw is None:
        return None
    guid = raw[1][1].get("guid")
    return next((name for name, value in GUID_OF.items() if value == guid), None)


def _flags(node):
    content = node.get(CONTENT)
    block = (content.get("u2") or {}).get("u1") if isinstance(content, dict) and isinstance(content.get("u2"), dict) else None
    flags = block.get("flags") if isinstance(block, dict) else None
    return flags if isinstance(flags, dict) and isinstance(flags.get("rest"), int) else None


def _first_column(node):
    from . import columns as _columns
    holder = _columns.columns_of(node)
    members = holder.get("items") if holder else None
    return members[0] if members else None


def _hierarchy_flags(column):
    from . import columns as _columns
    head = _columns._column_body(column)
    flags = head.get("flags") if isinstance(head, dict) else None
    return flags if isinstance(flags, dict) and "show_hierarchy" in flags else None


def to_tree(doc, node, unverified=False):
    """Табличное поле таблицы значений → поле дерева значений: описатель, источник данных, два бита слова флагов, «Иерархия» у первой колонки.
    Возвращает слова для отчёта."""
    from .. import design as _design
    version = _design.form_version(doc)
    if version != TREE_FORM_VERSION and not unverified:
        raise EditError(f"дерево значений записано по образцу форм поколения {TREE_FORM_VERSION}, а у формы версия общего блока {version}: "
                        "для форм 10, 13 и 15 узел-образец дерева не сводился. Позвать всё же можно — unverified=True")
    raw = _raw_type(node)
    flags = _flags(node)
    if raw is None or flags is None or not isinstance(node.get(CONTENT, {}).get(TABLE_SOURCE), dict):
        raise EditError("у табличного поля не разобраны описатель типа, источник данных или слово флагов — дерево значений на нём не собрать")
    raw[1][1] = {"guid": GUID_OF[VALUE_TREE]}
    node[CONTENT][TABLE_SOURCE] = copy.deepcopy(TREE_SOURCE)
    flags["rest"] = flags["rest"] | TREE_BITS
    said = "табличное поле стало полем дерева значений (описатель e603c0f2-…, источник 9ab3fa70-… вида 4, биты 0x20 и 0x200 слова флагов)"
    first = _first_column(node)
    column_flags = _hierarchy_flags(first) if first is not None else None
    if column_flags is not None and not column_flags["show_hierarchy"]:
        column_flags["show_hierarchy"] = True
        said += "; первой колонке включена «Иерархия» (так у 164 деревьев из 194 привязанных в корпусе)"
    return said


def to_table(node):
    """Поле дерева значений → поле таблицы значений (обратный ход `to_tree`). Возвращает слова для отчёта."""
    from .. import templates as _templates
    raw = _raw_type(node)
    flags = _flags(node)
    if raw is None or flags is None:
        raise EditError("у табличного поля не разобраны описатель типа или слово флагов — таблицу значений на нём не собрать")
    raw[1][1] = {"guid": GUID_OF[VALUE_TABLE]}
    node[CONTENT][TABLE_SOURCE] = copy.deepcopy(_templates.element("TableBox")[CONTENT][TABLE_SOURCE])
    flags["rest"] = flags["rest"] & ~TREE_BITS
    said = "табличное поле стало полем таблицы значений (описатель acf6192e-…, источник 342cf854-… вида 5, биты 0x20 и 0x200 сняты)"
    first = _first_column(node)
    column_flags = _hierarchy_flags(first) if first is not None else None
    if column_flags is not None and column_flags["show_hierarchy"]:
        column_flags["show_hierarchy"] = False
        said += "; у первой колонки «Иерархия» снята (у таблицы значений её нет: 524 колонки из 525)"
    return said


def on_bind(doc, place, row, attribute, unverified=False):
    """Привязка элемента к реквизиту формы, у которого тип платформы: что допустимо и что надо привести. Вызывается до записи привязки,
    отказ оставляет форму прежней. Возвращает слова для отчёта (пусто, если реквизит другого типа)."""
    source = attribute_source(row)
    if source is None:
        return ""
    kind = place.element.get("type")
    node = place.element
    if kind == "TableBox":
        if source == VALUE_LIST:
            raise EditError(f"табличное поле на список значений ({attribute!r}): колонки у него другого вида (`fbacf851-…`, 29 полей корпуса), образец такой "
                            "колонки у редактора не заведён и источник данных поля — тоже. Список значений показывает поле списка "
                            "(`add_element` с `template` ListBox, затем `bind`)")
        current = table_source(node)
        if current == source:
            return f"; тип поля уже {source}"
        if current not in (VALUE_TABLE, VALUE_TREE):
            raise EditError(f"табличное поле {place.element.get('name_block', {}).get('name')!r} показывает не таблицу и не дерево значений "
                            f"(описатель типа {current or 'другой'}); реквизит {attribute!r} — {source}. Таблицу значений на нём не собрать: "
                            "поставьте поле заново (`add_element` с `template` TableBox либо TreeBox)")
        said = to_tree(doc, node, unverified) if source == VALUE_TREE else to_table(node)
        return f"; {said}"
    if kind == "ListBox":
        if source != VALUE_LIST:
            raise EditError(f"поле списка (ListBox) показывает список значений, а реквизит {attribute!r} — {source}: "
                            "таблицу и дерево значений показывает табличное поле (`add_element` с `template` TableBox либо TreeBox)")
        return "; поле списка на реквизит ValueList"
    return ""


def _check_columns(columns, tree):
    """Описание колонок → нормальный вид либо отказ словами до изменения формы."""
    if not isinstance(columns, list) or not columns:
        raise EditError("columns — непустой массив колонок {\"name\": …, \"header\": …, \"width\": …, \"align\": …, \"format\": …}")
    out, seen = [], set()
    for at, spec in enumerate(columns):
        if isinstance(spec, str):
            spec = {"name": spec}
        if not isinstance(spec, dict):
            raise EditError(f"columns/{at}: колонка — имя строкой либо объект {{\"name\": …}}, а пришло {spec!r}")
        stray = sorted(set(spec) - set(COLUMN_KEYS))
        if stray:
            raise EditError(f"columns/{at}: ключи {', '.join(map(repr, stray))} колонке таблицы значений не принадлежат; бывают {', '.join(COLUMN_KEYS)}")
        name = spec.get("name")
        if not isinstance(name, str) or not name.strip():
            raise EditError(f"columns/{at}: нужно имя колонки (name), оно же её Данные")
        if name in seen:
            raise EditError(f"columns/{at}: колонка {name!r} названа дважды")
        seen.add(name)
        if spec.get("type") is not None:
            from .columns import column_type_block
            try:
                column_type_block(spec["type"])
            except EditError as e:
                raise EditError(f"columns/{at}: type: {e}") from None
        width = spec.get("width")
        if width is not None and (not isinstance(width, int) or isinstance(width, bool) or width < 1):
            raise EditError(f"columns/{at}: width — целое число пикселей больше нуля, а пришло {width!r}")
        for key in ("align", "header_align"):
            if spec.get(key) is not None and spec[key] not in ALIGNS[(1 if key == "header_align" else 0):]:
                raise EditError(f"columns/{at}: {key} — {', '.join(ALIGNS[(1 if key == 'header_align' else 0):])}, а пришло {spec[key]!r}")
        if spec.get("format") is not None and not isinstance(spec["format"], str):
            raise EditError(f"columns/{at}: format — строка формата (`ЧДЦ=3`), а пришло {spec['format']!r}")
        if "hierarchy" in spec:
            if not isinstance(spec["hierarchy"], bool):
                raise EditError(f"columns/{at}: hierarchy — true или false, а пришло {spec['hierarchy']!r}")
            if spec["hierarchy"] and not tree:
                raise EditError(f"columns/{at}: «Иерархия» — колонка дерева значений; у таблицы значений её нет")
        out.append({"name": name, **{k: v for k, v in spec.items() if k != "name"}})
    return out


def _need_hierarchy(specs, tree):
    if tree and not any(s.get("hierarchy", i == 0) for i, s in enumerate(specs)):
        raise EditError("у дерева значений ни одна колонка не с «Иерархией»: такое дерево в предприятии открывается плоской таблицей — одна корневая строка без значка "
                        "раскрытия и без вложенных строк (проверено). В корпусе «Иерархия» стоит у первой колонки (164 дерева из 194) либо у второй (15 из 194). "
                        "Уберите `\"hierarchy\": false` у первой колонки или поставьте `\"hierarchy\": true` другой")


def add_columns(doc, table, columns, unverified=False):
    """Колонки таблицы или дерева значений одной операцией: `columns` — `[{"name", "header", "width", "align", "header_align", "format", "hierarchy"}]`.

    Поле берётся пустым или с одной безымянной колонкой шаблона (она снимается). Колонки ставит `add_column` без `template` (первая — из шаблона редактора,
    остальные — её копии), свойства — `set_property` после всех колонок: иначе копия унесла бы свойства предыдущей. Заголовок без `header` — имя колонки.
    «Иерархия» у дерева значений — первой колонке, если `hierarchy` не названо; `"hierarchy": false` у первой колонки дерева её не включает.
    `type` — тип колонки (`{"kind": "N", "digits": 15, "fraction": 3}`, `S` с `length`, `D`, `B`): тип колонки и описатель её поля ввода пишутся вместе (`set_column_type`)."""
    from . import columns as _columns
    from .setprop import set_property
    place = find_element(doc, table)
    source = table_source(place.element)
    if place.element.get("type") != "TableBox" or source not in (VALUE_TABLE, VALUE_TREE):
        raise EditError(f"add_columns ставит колонки таблицы и дерева значений, а {table!r} — {place.element.get('type')} с описателем "
                        f"{source or 'другого типа'}; привяжите поле к реквизиту таблицы значений (`bind`)")
    tree = source == VALUE_TREE
    specs = _check_columns(columns, tree)
    _need_hierarchy(specs, tree)
    holder = _columns._columns_of(doc, table)
    members = holder["items"]
    names = [_columns._column_name(c) for c in members]
    clash = [s["name"] for s in specs if s["name"] in names and s["name"] != ""]
    if clash:
        raise EditError(f"у {table!r} колонки уже есть: {', '.join(map(repr, clash))}")
    words = []
    if names == [""]:
        words.append(_columns.remove_column(doc, table, ""))
    elif names:
        raise EditError(f"у {table!r} колонки уже есть ({', '.join(repr(n) for n in names)}): add_columns ставит колонки пустому полю либо полю с одной "
                        "безымянной колонкой шаблона; недостающую колонку добавляет add_column")
    for spec in specs:
        words.append(_columns.add_column(doc, table, spec["name"], header=spec.get("header", spec["name"]), unverified=unverified))
    for index, spec in enumerate(specs):
        if spec.get("type") is not None:
            words.append(_columns.set_column_type(doc, table, spec["name"], spec["type"], unverified))
        props = []
        if spec.get("width") is not None:
            props.append(("width", spec["width"]))
        if spec.get("align") is not None:
            props.append(("horizontal_align_in_column", spec["align"]))
        if spec.get("header_align") is not None:
            props.append(("header_horizontal_align", spec["header_align"]))
        if spec.get("format") is not None:
            props.append(("format", spec["format"]))
        hierarchy = spec.get("hierarchy", tree and index == 0)
        if "hierarchy" in spec or hierarchy:
            props.append(("show_hierarchy", hierarchy))
        for name, value in props:
            words.append(set_property(doc, element=table, column=spec["name"], name=name, value=value, unverified=unverified))
    return (f"{table}: колонок {len(specs)} ({', '.join(s['name'] for s in specs)})" + "".join(f"; {w}" for w in words))


def add_table(doc, add_element, args, attribute, columns, tree_alias):
    """`add_element` табличного поля с реквизитом и колонками одним вызовом: поле → `bind` → `add_columns`. `args` — аргументы `add_element` без `attribute`
    и `columns`; `tree_alias` — шаблон назван `TreeBox`."""
    from .data import bind
    if args.get("template") not in ("TableBox", "TreeBox"):
        raise EditError(f"attribute и columns — у табличного поля (template TableBox либо TreeBox), а template {args.get('template')!r}")
    if columns is not None:
        _need_hierarchy(_check_columns(columns, tree_alias), tree_alias)
    if attribute is not None:
        attributes = doc.get("attributes")
        holder = attributes.get("list") if isinstance(attributes, dict) else None
        rows = holder.get("items") if isinstance(holder, dict) else None
        if not isinstance(rows, list):
            raise EditError("у формы нет разобранного списка реквизитов — привязывать поле не к чему (`add_attribute` заводит реквизит)")
        rows = [r for r in rows if isinstance(r, dict)]
        row = next((r for r in rows if r.get("name") == attribute), None)
        source = attribute_source(row) if row is not None else None
        if row is None:
            known = ", ".join(str(r.get("name")) for r in rows) or "—"
            raise EditError(f"реквизита {attribute!r} у формы нет; есть: {known}")
        if source not in (VALUE_TABLE, VALUE_TREE):
            raise EditError(f"реквизит {attribute!r} — не таблица и не дерево значений ({source or 'другой тип'}): табличное поле с колонками значений "
                            "собирается только на ValueTable либо ValueTree")
        if columns is not None and source == VALUE_TREE and not tree_alias:
            _need_hierarchy(_check_columns(columns, True), True)
        if tree_alias and source != VALUE_TREE:
            raise EditError(f"template TreeBox — поле дерева значений, а реквизит {attribute!r} — {source}; для таблицы значений template TableBox")
    unverified = bool(args.get("unverified"))
    args = dict(args, template="TableBox")
    said = add_element(doc, **args)
    name = args["name"]
    if tree_alias:
        place = find_element(doc, name)
        if table_source(place.element) != VALUE_TREE:
            said += "; " + to_tree(doc, place.element, unverified)
    if attribute is not None:
        said += "; " + bind(doc, element=name, attribute=attribute, unverified=unverified)
    if columns is not None:
        said += "; " + add_columns(doc, name, columns, unverified)
    return said
