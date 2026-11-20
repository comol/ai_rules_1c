"""Генерация формы СПИСКА справочника и документа (`catalog.list`, `document.list`).

Описание: `{"kind": "catalog.list", "object": "Справочник.Товары", "blocks": [{"command_bar": "top"}, {"table": "Список", "columns": [...]}]}`.

**Ключи описания.** `kind`, `object`, `title`, `size`, `blocks`, `tune`, `skipped`; `form_use` и `attributes` у списка — лишние ключи (форм элемента и
группы у списка нет, а основной реквизит — динамический список, новых реквизитов формы он не заводит).

**Блоки списка.** Только два: `command_bar` (верхняя) и `table` — одно табличное поле на динамический список объекта, `"table": "Список"` (слово, а не
путь: основной реквизит формы списка у платформы называется `СправочникСписок`/`ДокументСписок`, у переименованной формы иначе, а путь «Объект.…» у
списка не бывает). Колонки — имена: стандартные (справочник: `Картинка`, `Код`, `Наименование`; документ: `Картинка`, `Дата`, `Номер`) и реквизиты
объекта; без ключа `columns` — колонки конструктора (стандартные, какие объект включает). **Не поддерживается:**

* нижняя панель команд — у списков её почти нигде нет;
* `fields`, `group`, `tabs`, `spreadsheet` — поля над и под списком (отборы): общего скелета нет, нормы ритма нет;
* `bar` у блока `table` — своей командной панели у таблицы списка конструктор не ставит (панель формы `ДействияФормы` — верхняя);
* булева колонка, составной тип, `Родитель`, `Владелец`, `Проведен` — образца конструктора нет (`edit.listcols`).

**Исходная форма — форма списка конструктора** (основной реквизит — список ЭТОГО объекта; иначе отказ). Таблица исходной формы и её колонки, у которых путь данных
тот же, остаются как были (имя, индекс, привязка, обработчики и прочие свойства прежние); **переиспользованная таблица списка не двигается**: при
названном `size` растягивается по привязкам своих краёв (`move_element`; «растягивается» — на размер формы, «остаётся на месте» — нет, а привязки не из этих двух, как у
дерева групп, — отказ), сдвиг на норму — только когда дерево убрано. Колонки: колонки исходной формы, которых описание выразить не может
(`edit.listcols.classify` отказывает, путь не распознан, второй раз тот же путь), — нетронутые, остаются на местах; из прочих остаётся наибольшее
начало описания, идущее в исходной форме в том же порядке, остальные убираются, недостающие дописываются в конец (переставленные — заново, настройки
сброшены — отчёт говорит). Панель `ДействияФормы` исходной формы остаётся (источник действий и кнопки прежние), а без блока `command_bar` — убирается; нет её
в исходной форме — ставится ЗАПИСЬ панели конструктора формы списка (`templates` «CommandBar-list»). Прочие верхние элементы исходной формы (поля, рамки, закладки,
вторые таблицы) убираются, как у вида элемента.

**Дерево групп иерархического справочника**: табличное поле на ВТОРОЙ реквизит-список того же объекта и разделитель между ним и списком. Ключ `tree`
блока `table`: нет — дерево исходной формы и его геометрия остаются как есть (исходная форма имеет приоритет); `false` — дерево и разделитель убираются, список
встаёт на норму; `true` над исходной формой без дерева — отказ словами (постановка дерева не поддерживается: перехода «без дерева → с деревом» нет).

**Геометрия**: панель (0,0)–(ширина, 25), таблица от `(8, 33)` до `(ширина − 8, высота − 8)` с привязками вправо и вниз. Высота панели — норма вида
`patterns.json` (`top_bar_height`); размер формы — исходной формы, либо `size` `[ширина, высота]` (не меньше `LIST_MIN_W`×`LIST_MIN_H`; и ширина, и высота
исходной формы без `size` проверяются так же)."""
import dataclasses

from . import layout, metadata, patterns, shell as shell_mod, templates
from .edit import base, datapath, listcols
from .edit.base import EditError
from .edit.names import CAPTION
from .generate import BAR_NAMES, GenerateError, _is_int, _only

LIST_KINDS = {"catalog.list": "catalog", "document.list": "document"}
LIST_TOP_KEYS = ("kind", "object", "title", "size", "blocks", "tune", "skipped")
LIST_BLOCKS = ("command_bar", "table")
LIST_SIDE = 8  # отступ таблицы слева и справа
LIST_BELOW_BAR = 8  # верх таблицы ниже нижнего края верхней панели: 33 = 25 + 8
LIST_BOTTOM = 8  # низ таблицы выше низа формы: 8
LIST_MIN_W = 2 * LIST_SIDE + 100  # ниже таблица не читается: ширина таблицы не меньше 100 (как у вида элемента, не проверялось)
LIST_MIN_H = 33 + 55 + LIST_BOTTOM      # панель и отступ над таблицей, таблица не ниже 55 (`generate.TABLE_MIN_H`), отступ снизу
TOP_BAR_KEYS = ("top_bar_x", "top_bar_y", "top_bar_height")
REFUSED = {
    "fields": "поля над и под списком (отборы): общего скелета у таких форм нет, нормы ритма у них нет",
    "group": "рамка у формы списка: общего вида нет",
    "tabs": "закладки у формы списка: общего вида нет",
    "spreadsheet": "поле табличного документа — у формы обработки, у списка его нет",
    "radio": "переключатели на реквизит формы: у формы списка своих реквизитов нет",
    "picture": "поле картинки у формы списка: общего вида нет",
    "row": "ряд полей у формы списка: общего вида нет",
    "beside": "блок справа от шапки у формы списка: общего вида нет",
    "split": "две области с разделителем у формы списка: общего вида нет",
}


def check(desc):
    """Проверка описания вида списка без метаданных: список причин (пустой — всё в порядке)."""
    problems = []
    _only(desc, LIST_TOP_KEYS, "описание списка", problems)
    blocks = desc.get("blocks")
    if not isinstance(blocks, list):
        return problems
    tables, bars = 0, []
    for at, block in enumerate(blocks):
        where = f"blocks[{at}]"
        if not isinstance(block, dict):
            problems.append(f"{where}: блок — объект с одним из ключей {', '.join(LIST_BLOCKS)}")
            continue
        found = [k for k in ("command_bar", "fields", "group", "tabs", "table", "spreadsheet", "radio", "picture", "row", "beside", "split") if k in block]
        if len(found) != 1:
            problems.append(f"{where}: блок называет ровно один вид ({', '.join(LIST_BLOCKS)}), а у него {found or 'ни одного'}")
            continue
        key = found[0]
        if key in REFUSED:
            problems.append(f"{where}: блок «{key}» у формы списка не делается — {REFUSED[key]}")
        elif key == "command_bar":
            _only(block, ("command_bar",), where, problems)
            if block["command_bar"] == "bottom":
                problems.append(f"{where}: нижней панели команд у списка нет — конструктор её не ставит, а у справочника норма нижней панели из двух конфигураций (13 форм из 440 (patterns.json)): "
                                "бывает только верхняя")
            elif block["command_bar"] != "top":
                problems.append(f"{where}: command_bar — \"top\", а пришло {block['command_bar']!r}")
            else:
                bars.append(at)
        else:
            tables += 1
            _only(block, ("table", "columns", "tree"), where, problems)
            if "tree" in block and not isinstance(block["tree"], bool):
                problems.append(f"{where}: tree — true или false (дерево групп иерархического справочника: оставить как в исходной форме либо убрать), а пришло {block['tree']!r}")
            if "bar" in block:
                problems.append(f"{where}: bar — у таблицы списка своей командной панели нет (панель формы «{BAR_NAMES['top']}» — блок command_bar)")
            if block["table"] != shell_mod.LIST_KEY:
                problems.append(f"{where}: table — «{shell_mod.LIST_KEY}» (динамический список формы), а пришло {block['table']!r}")
            columns = block.get("columns")
            if columns is not None and (not isinstance(columns, list) or not columns or not all(isinstance(c, str) and c for c in columns)):
                problems.append(f"{where}: columns — непустой массив имён колонок (или убрать ключ: тогда колонки конструктора)")
            elif columns is not None and len(set(columns)) != len(columns):
                problems.append(f"{where}: колонка названа дважды")
    if tables > 1:
        problems.append(f"таблица списка — один блок table, а их {tables}")
    if len(bars) > 1:
        problems.append("панель команд «top» названа дважды")
    if bars and bars[0] != 0:
        problems.append("верхняя панель команд — первый блок")
    size = desc.get("size", "content")
    if isinstance(size, list) and len(size) == 2 and all(_is_int(v) for v in size) and (size[0] < LIST_MIN_W or size[1] < LIST_MIN_H):
        problems.append(f"size: {size[0]}×{size[1]} мало — списку нужно не меньше {LIST_MIN_W}×{LIST_MIN_H} (панель, таблица не ниже 55, отступы)")
    return problems


def list_norms(table, kind):
    """Показатели верхней панели из `patterns.json` (большинство форм в конфигурациях); нет вида, вид `thin` либо нет показателя — отказ словами."""
    block = (table.get("kinds") or {}).get(kind)
    if not block:
        raise GenerateError(f"в нормах (patterns.json) нет вида «{kind}»")
    if block.get("thin"):
        raise GenerateError(f"у вида «{kind}» норм нет: он из {block.get('configs')} конфигураций (меньше {patterns.THIN_CONFIGS})")
    out, missing = {}, []
    for key in TOP_BAR_KEYS:
        out[key] = patterns.norm(table, kind, key)
        if out[key] is None:
            missing.append(key)
    if missing:
        raise GenerateError(f"у вида «{kind}» нет нормы для {', '.join(missing)}: верхнюю панель расставить нечем")
    return out


@dataclasses.dataclass
class Plan:
    ops: list
    notes: list


def _object(desc, config):
    try:
        obj = config.object(desc["object"])
    except metadata.MetadataError as e:
        raise GenerateError(f"object: {e}") from None
    if obj.kind != LIST_KINDS[desc["kind"]]:
        word = {"catalog": "справочник", "document": "документ", "processing": "обработка"}
        raise GenerateError(f"вид «{desc['kind']}» — {word[LIST_KINDS[desc['kind']]]}, а объект «{obj.full_name}» — {word.get(obj.kind, obj.kind)}")
    return obj


def _form_attribute(form_doc, obj, config):
    """Имя основного реквизита исходной формы; он обязан быть списком ЭТОГО объекта (категория `List`) — иначе отказ словами."""
    try:
        attributes, rows = datapath._attributes(form_doc)
    except EditError as e:
        raise GenerateError(f"форма не годится исходной формой: {e}") from None
    head = attributes.get(datapath.ATTR_HEAD)
    main = head.get(datapath.MAIN_ATTRIBUTE_ID) if isinstance(head, dict) else None
    row = next((r for r in rows if datapath._id_of(r) == main), None)
    if row is None:
        raise GenerateError("форма не годится исходной формой списка: у неё нет основного реквизита")
    guid = datapath._type_guid(row)
    hit = config.object_by_type_id(guid) if guid else None
    if hit is None or hit[0] is not obj or hit[1].lower() != listcols.LIST_CATEGORY:
        said = (f"тип категории «{hit[1]}» объекта «{hit[0].full_name}»" if hit is not None else f"тип {guid or 'не из одного типа-ссылки'}, которого в выгрузке нет")
        raise GenerateError(f"форма — не список объекта «{obj.full_name}»: основной реквизит «{row.get(datapath.ATTR_NAME)}» — {said}; исходная форма списка — форма списка этого объекта "
                            "(основной реквизит — тип категории List), её создаёт конструктор платформы")
    return row.get(datapath.ATTR_NAME)


def default_columns(obj):
    """Колонки конструктора по умолчанию: стандартные, какие объект включает (справочник — Картинка, Код, Наименование; документ — Картинка, Дата, Номер)."""
    return [k for k in listcols.STD_TEMPLATES[obj.kind] if k == "Картинка" or k in obj.standard]


def _column_plan(shell_cols, want, expressible):
    """`(остаются, убрать, добавить, нетронутые)`. Колонки исходной формы, которых описание выразить не может (`expressible` — нет: путь не распознан,
    булева, `Владелец`, ссылка вне выгрузки…) либо которые встали второй раз, — НЕТРОНУТЫЕ: `describe` их пропускает, и это не перестановка; остаются на
    своих местах. Из прочих остаётся наибольшее начало описания, которое идёт в исходной форме в том же относительном порядке (подпоследовательность): новые
    колонки дописываются в конец, и порядок описания сходится, только если остающиеся — его начало; остальные колонки исходной формы убираются, остальные
    колонки описания ставятся (переставленные — заново, их настройки сбрасываются)."""
    seen, ours, untouched = set(), [], []
    for column in shell_cols:
        if column.key is not None and column.key not in seen and expressible(column.key):
            seen.add(column.key)
            ours.append(column)
        else:
            untouched.append(column)
    k, stay = 0, []
    for column in ours:
        if k < len(want) and column.key == want[k]:
            k += 1
            stay.append(column)
    drop = [c for c in ours if not any(c is x for x in stay)]
    return stay, drop, want[k:], untouched


def plan_notes(desc, form_doc, config, norms, heights=None):
    """Описание списка → `(операции редактора, заметки)`; отказ — `GenerateError` со всеми найденными причинами."""
    if not isinstance(config, metadata.Config):
        raise GenerateError("config — выгрузка конфигурации (metadata.load): форма списка привязывает колонки к реквизитам объекта выгрузки")
    obj = _object(desc, config)
    form_name = _form_attribute(form_doc, obj, config)
    try:
        shell = shell_mod.scan(form_doc, obj)
    except EditError as e:
        raise GenerateError(f"исходная форма не разобрана: {e}") from None
    if len(shell.lists) != 1:
        raise GenerateError(f"в исходной форме табличных полей на динамический список {len(shell.lists)}, а переиспользуется ровно одно (форма списка конструктора): "
                            + ("таблицы списка нет — форма не конструктора?" if not shell.lists else
                               f"их {', '.join(t.name for t in shell.lists)} — какая из них список, по форме не решить (форма с деревом групп?)"))
    table = shell.lists[0]
    block = next((b for b in desc["blocks"] if "table" in b), None)
    if block is None:
        raise GenerateError("описание не годится: в нём нет блока table — форма списка без таблицы бессмысленна (describe не нашёл на форме табличного поля на список: "
                            "такое описание формы-образца для генерации не годится)")
    tree_flag = block.get("tree")
    if tree_flag is True and not shell.trees:
        raise GenerateError("tree: true — в исходной форме дерева групп нет, а ставить его движок не умеет: перехода «список БЕЗ дерева → с деревом» нет "
                            "(как пишутся привязки краёв, номер и `u1` нового реквизита). Дерево конструктора: (8, 33)–(153, h−8), список (159, 33)–(w−8, h−8), "
                            "зазор 6, ширина дерева 145 при ширине формы 400 (граница дерева пропорциональная, левый край списка идёт за правым краем дерева). "
                            "Берите исходной формой форму списка иерархического справочника с деревом (дерево переиспользуется как есть) либо уберите tree")
    keep_tree = bool(shell.trees) and tree_flag is not False
    want = list(block["columns"]) if "columns" in block else default_columns(obj)
    problems = []
    for key in want:
        try:
            listcols.classify(obj, key, config)
        except EditError as e:
            problems.append(f"колонка «{key}»: {e}")
    if problems:
        raise GenerateError("описание не годится: " + "; ".join(f"{i}) {p}" for i, p in enumerate(problems, 1)))
    bar_wanted = any(b.get("command_bar") == "top" for b in desc["blocks"] if "command_bar" in b)
    form = layout.read(form_doc)
    size = desc.get("size", "content")
    width, height = (form.width, form.height) if size == "content" else tuple(size)
    n = list_norms(norms, desc["kind"]) if bar_wanted else {}
    notes = []
    top = n["top_bar_y"] + n["top_bar_height"] + LIST_BELOW_BAR if bar_wanted else LIST_SIDE
    if width < LIST_MIN_W:
        raise GenerateError(f"size: ширина {width} мала — таблице списка нужно не меньше 100 (с отступами {LIST_MIN_W}); размер{' исходной формы' if size == 'content' else ' формы'} {width}×{height}")
    if height - top - LIST_BOTTOM < 55:
        raise GenerateError(f"size: высота {height} мала — таблице списка после панели остаётся {height - top - LIST_BOTTOM}, а нужно не меньше 55")
    holder = form.holders[0].children
    splitters = [c.name for c in holder if c.type == "Splitter" and c.name]
    ops = []
    kept_names = {table.name}
    if keep_tree:
        kept_names |= {t.name for t in shell.trees} | set(splitters)
    bar = next((c for c in holder if c.type == "CommandBar" and c.name == BAR_NAMES["top"]), None)
    if bar_wanted and bar is not None:
        kept_names.add(bar.name)
    removed = []
    for name in _top_names(form_doc):
        if name not in kept_names:
            ops.append({"op": "remove_element", "name": name})
            removed.append(name)
    if size != "content":
        ops += [{"op": "set_property", "form": True, "name": "width", "value": width},
                {"op": "set_property", "form": True, "name": "height", "value": height}]
    if desc.get("title") and desc["title"] != _form_title(form_doc):
        ops.append({"op": "set_form_title", "text": desc["title"]})
    on_place = []
    table_item = next(c for c in holder if c.index == table.index)
    if shell.trees and not keep_tree:
        # дерево убрано (`tree: false`): список встаёт на норму — единственный случай, когда ПЕРЕИСПОЛЬЗОВАННАЯ таблица списка сдвигается на норму
        table_box = [LIST_SIDE, top, width - 2 * LIST_SIDE, height - top - LIST_BOTTOM]
        if _stands(table_item, table_box):
            on_place.append(table.name)
        else:
            ops.append({"op": "move_element", "name": table.name, "box": table_box, "anchor": {"h": "stretch", "v": "stretch"}})
        notes.append(f"дерево групп убрано ({', '.join(t.name for t in shell.trees)}) вместе с разделителями: список встал на норму ({LIST_SIDE}, {top})–({width - LIST_SIDE}, {height - LIST_BOTTOM}); "
                     f"реквизит формы «{shell.trees[0].ts}» остался (его снимает человек в конфигураторе)")
    else:
        # исходная форма имеет приоритет: таблица списка и дерево остаются на своих местах; при названном размере растягиваются по привязкам краёв, как у форм объекта
        stretched = []
        parts = [(table_item, table.name)] + [(next(c for c in holder if c.index == t.index), t.name) for t in (shell.trees if keep_tree else [])]
        for item, label in parts:
            op = _stretch_op(form, item, label, width - form.width, height - form.height) if size != "content" else None
            if op is not None:
                ops.append(op)
                stretched.append(label)
            else:
                on_place.append(label)
        if stretched:
            notes.append(f"при названном размере растянуты по привязкам краёв исходной формы: {', '.join(stretched)}")
        if keep_tree:
            notes.append(f"дерево групп ({', '.join(t.name for t in shell.trees)}"
                         + (f", разделитель {', '.join(splitters)}" if splitters else "") + ") осталось из исходной формы как было: геометрия дерева и списка — исходной формы")
    if bar_wanted:
        box = [n["top_bar_x"], n["top_bar_y"], width - n["top_bar_x"], n["top_bar_height"]]
        if bar is not None:
            if _stands(bar, box):
                on_place.append(bar.name)
            else:
                ops.append({"op": "move_element", "name": bar.name, "box": box, "anchor": {"h": "stretch", "v": "top"}})
            notes.append(f"верхняя панель команд «{bar.name}» осталась из исходной формы (кнопки и источник действий прежние)")
        else:
            ops.append({"op": "add_element", "template": _list_bar_template(notes), "name": BAR_NAMES["top"], "box": box, "anchor": {"h": "stretch", "v": "top"}})
    elif bar is not None:
        notes.append(f"панель команд «{bar.name}» исходной формы убрана: в описании нет блока command_bar")
    if on_place:
        notes.append(f"на месте по нормам уже стоят или не двигались: {', '.join(on_place)} — привязки краёв прежние (у конструктора они автоматические: платформа досчитывает их при сохранении)")
    stay, drop, add, untouched = _column_plan(table.columns, want, _expressible(obj, config))
    survivors = [c for c in table.columns if not any(c is d for d in drop)]
    clash = [k for k in add if k in {c.name for c in survivors}]
    if clash:
        raise GenerateError(f"описание не годится: колонка «{clash[0]}» стоит в исходной форме под этим именем у другого пути данных — имя занято, а имя колонки ключ описания не переименовывает")
    drops_all = len(drop) == len(table.columns)
    clash = [k for k in add if drops_all and k in {c.name for c in drop}]
    if clash:
        raise GenerateError(f"описание не годится: все колонки исходной формы уходят, и колонка «{clash[0]}» ставится заново под тем же именем, пока прежняя не убрана; "
                            "оставьте в описании первой колонкой одну из колонок исходной формы")
    adds = [{"op": "add_column", "table": table.name, "name": k, "data": f"{form_name}.{k}"} for k in add]
    drops = [{"op": "remove_column", "table": table.name, "name": c.name} for c in drop]
    ops += (adds + drops) if drops_all else (drops + adds)
    redone = [c.name for c in drop if c.key in add]
    notes.append(f"таблица «{table.name}» осталась из исходной формы: колонок осталось {len(stay)}, убрано {len(drop)}, поставлено {len(add)}"
                 + (f" (убраны и поставлены заново: {', '.join(redone)} — их порядок в исходной форме не тот, что в описании, либо перед ними встала новая колонка, а новые колонки идут "
                    "в конец; их настройки сброшены)" if redone else "")
                 + (f"; колонки исходной формы, которых описание не выражает, не тронуты: {', '.join(c.name for c in untouched)}" if untouched else ""))
    if removed:
        notes.append(f"из исходной формы убраны элементы: {', '.join(removed)}")
    if any(listcols.classify(obj, k, config)[0] == "attr" for k in add):
        notes.append(f"ширина новых колонок реквизитов — умолчание движка, не результат подсчёта по корпусу ({listcols.WIDTH_NOTE}): конструктор колонок реквизитов не ставит — `tune` (set_property колонки) доводит")
    if heights:
        notes.append("высоты по соседям (--siblings) списку не нужны: полей ввода в нём нет")
    ops += [dict(op) for op in desc.get("tune", [])]
    return ops, notes


def _form_title(form_doc):
    """Заголовок исходной формы (первый непустой текст) либо `None`: прежний не переписывается."""
    title = ((form_doc.get("form") or {}).get("title") or {}).get(CAPTION) if isinstance(form_doc, dict) else None
    return shell_mod._text(title)


def _stands(item, box):
    """Элемент уже стоит в `box = [лево, верх, ширина, высота]`: двигать нечего, а привязки его краёв конструктора не переписываются."""
    return tuple(item.box) == (box[0], box[1], box[0] + box[2], box[1] + box[3])


def _top_names(form_doc):
    names = []
    for item in base.elements_of(base.container(form_doc)):
        name = base.name_of(item)
        if not name:
            raise GenerateError("у элемента исходной формы нет имени — убрать его по имени нечем; правьте форму (rename_element)")
        names.append(name)
    return names


def _expressible(obj, config):
    """Колонка исходной формы с этим ключом выражается описанием (`edit.listcols.classify` её принимает) — что с ней будет, решает описание; прочие не трогаются."""
    def check(key):
        try:
            listcols.classify(obj, key, config)
            return True
        except EditError:
            return False
    return check


def _stretch_op(form, item, label, dw, dh):
    """`move_element`, растягивающий переиспользованный элемент по привязкам краёв исходной формы при смене размера формы на `(dw, dh)` (граница идёт со
    своей стороной формы на долю `layout.coefficients`), либо `None` (размер не менялся либо у элемента нечему растягиваться). Привязки не из
    «остаётся на месте / растягивается» (у дерева групп граница пропорциональная — коэффициент 0,3825 у конструктора, и право дерева с левым краем списка идут вместе)
    `move_element` записать не умеет: отказ словами, а не молчаливо неверный размер."""
    if not dw and not dh:
        return None
    coef = layout.coefficients(form, hide=False).get(item.index)
    if coef is None:
        raise GenerateError(f"size: привязки краёв «{label}» в цикле правил — как она растянется при другом размере формы, не посчитать; оставьте размер исходной формы")
    c_top, c_bottom, c_left, c_right = coef
    h = {(0, 1): "stretch", (0, 0): "left"}.get((c_left, c_right))
    v = {(0, 1): "stretch", (0, 0): "top"}.get((c_top, c_bottom))
    if h is None or v is None:
        raise GenerateError(f"size: у «{label}» привязки краёв (верх {c_top}, низ {c_bottom}, лево {c_left}, право {c_right}) — ни «остаётся на месте», ни «растягивается» (так у дерева групп: граница "
                            "пропорциональная); растянуть их по правилам платформы операция move_element не умеет — оставьте размер исходной формы")
    if not dw * c_right and not dh * c_bottom:
        return None
    left, top, right, bottom = item.box
    box = [left, top, int(right + dw * c_right - left), int(bottom + dh * c_bottom - top)]
    return {"op": "move_element", "name": label, "box": box, "anchor": {"h": h, "v": v}}


def _list_bar_template(notes):
    """Верхняя панель команд списка, которой в исходной форме нет: ЗАПИСЬ панели конструктора формы списка (шаблон `CommandBar-list`: автозаполнение, источник действий — форма,
    рамка — как у конструктора); панель формы ЭЛЕМЕНТА (`generate._bar_template`) списку не годится: её пустая копия — без автозаполнения и без источника действий."""
    notes.append("в исходной форме нет верхней панели команд («ДействияФормы»): поставлена панель конструктора формы списка (автозаполнение, источник действий — форма) — "
                 "кнопок в файле у неё нет, полосу заполняет платформа")
    return templates.form_bar_node("top")
