"""Колонки табличного поля списка справочника и документа.

Табличное поле формы списка привязано к основному реквизиту формы — динамическому списку (тип категории `List` объекта
выгрузки), а не к табличной части. Путь привязки состоит из одного шага `[основной]`. Колонка такого списка имеет вид
`48a6ebc3-…` (`schema.LIST_COLUMN`), а её данные задаются путём в самой колонке (`u1/u1/u2`): `[-1]` — картинка, `[-2]` — код
справочника или номер документа, `[-3]` — наименование или дата, `[0, {guid реквизита объекта}]` — реквизит.

Образец. Стандартные колонки (Картинка, Код, Наименование — для справочника; Картинка, Дата, Номер — для документа)
конструктор формы списка создаёт сам (`templates.LIST_COLUMNS`). Колонок реквизитов конструктор не создаёт, поэтому колонка
реквизита строится из образца колонки табличной части того же класса (`templates.tabular_column`) тремя правками: вид колонки
становится `48a6ebc3-…`, из тела колонки убирается четвёртый член `u3`, а признак `1` заменяется на `4`, и путь `[0, {guid}]`
записывается в Данные. Остальное остаётся как в образце.

Операция отказывает и объясняет причину для следующих случаев: булев реквизит, составной тип, стандартные колонки
`Родитель`, `Владелец`, `Проведен`, `ПометкаУдаления`, `Ссылка`, а также код и номер числового типа.

Ширина. Конструктор ставит ширину текстовой колонки равной 7 пикселям на знак ширины `width_computed` (Код — 63 при 9
знаках, Номер — 77 при 11, Дата — 140 при 20, Наименование — 350 при 50; Картинка — фиксированная 24). Для строки число
знаков ширины равно её длине, но не больше 50. Целое с нулями на конце записывается экспонентой, как у платформы
(`json0.int_exp_text`: `350` → `3.5e2`). Это правило конструктора, а для колонок реквизитов оно не обязательно: ширину колонки
реквизита обычно задаёт автор формы. Операция принимает такие значения по умолчанию: для строки длину реквизита, но не больше
50, а без длины — 15; для числа 13, для даты 14, для ссылки 18, для даты со временем 20, для времени 14 (как для даты,
других данных нет). Это значения по умолчанию: ширину уточняют через `set_property` колонки или `tune` описания, а отчёт
генерации сообщает об этом словами `WIDTH_NOTE`.

Порядковый номер колонки равен наибольшему существующему плюс один, как у `add_column` для колонки табличной части.
Порядковые номера реквизита в голове колонки (`COLUMN_ORDINALS`) у колонок списка равны `-1`.
"""
from .. import design as _design, json0, metadata, schema
from . import datapath
from . import datatype
from .base import EditError, find_element, set_text
from . import columns
from .names import (COLUMN_BODY, COLUMN_HEADER_TEXT, COLUMN_ITEMS, COLUMN_NAME, COLUMN_ORDER, COLUMN_ORDINALS, COLUMN_TYPE, COLUMNS_COUNT)

LIST_CATEGORY = "list"
PX_PER_CHAR = 7  # пикселей на знак ширины у конструктора: 63/9, 77/11, 140/20, 350/50, 24/4
STRING_CHARS_CAP = 50  # знаков ширины у строки равно длине, но не больше 50 (Наименование 100 → 50)
STRING_CHARS_NO_LENGTH = 15  # строка без длины
# Слова для отчёта генерации о ширине новых колонок реквизитов: что взято и что это значение по умолчанию.
WIDTH_NOTE = ("ширина колонки — 7 пикселей на каждый знак ширины (так задаёт конструктор форм); для строки знаков ширины столько же, сколько в её длине, но не больше 50, а без длины — 15; "
              "для числа 13, для даты 14, для времени 14 (так же, как для даты), для даты со временем 20, для ссылки 18")
CLASS_CHARS = {"decimal": 13, "date": 14, "time": 14, "datetime": 20, "catalog": 18, "document": 18, "enum": 18}
# Образец стандартной колонки по имени и по пути данных. Имя совпадает с именем стандартного реквизита, а у справочника и
# документа виды колонок разные.
STD_TEMPLATES = {"catalog": {"Картинка": "picture", "Код": "code", "Наименование": "description"},
                 "document": {"Картинка": "picture", "Дата": "date", "Номер": "number"}}
STD_PATHS = {"Картинка": [-1], "Код": [-2], "Наименование": [-3], "Номер": [-2], "Дата": [-3]}
STD_HEADERS = {"Картинка": "", "Код": "Код", "Наименование": "Наименование", "Номер": "Номер", "Дата": "Дата"}
STD_REFUSED = {"Родитель": "образца конструктора нет: конструктор не создаёт такую колонку",
               "Владелец": "образца конструктора нет: конструктор не создаёт такую колонку",
               "Проведен": "стандартной колонки с путём не встречается: колонки с таким именем создаются без данных (путь [-1])",
               "ПометкаУдаления": "стандартной колонки с путём в образцах форм нет",
               "Ссылка": "стандартной колонки с путём в образцах форм нет"}
SUPPORTED_ATTRIBUTE_CLASSES = ("string", "decimal", "dateTime", "catalog", "document", "enum")


def list_attribute(doc, table_place, config):
    """Возвращает `(строка реквизита формы, объект выгрузки)` для табличного поля, привязанного к основному реквизиту, то есть к
    динамическому списку объекта выгрузки (тип категории `List`). Если таблица не относится к списку или привязки нет, `None`.
    """
    if not isinstance(config, metadata.Config):
        return None
    attributes, rows = datapath._attributes(doc)
    head = attributes.get(datapath.ATTR_HEAD)
    main = head.get(datapath.MAIN_ATTRIBUTE_ID) if isinstance(head, dict) else None
    bound = [r for r in datapath.binding_rows(attributes) if r.get(datapath.BIND_ELEMENT) == table_place.index]
    path = bound[0].get(datapath.BIND_PATH) if bound else None
    steps = path.get(datapath.PATH_STEPS) if isinstance(path, dict) else None
    if not isinstance(steps, list) or len(steps) != 1 or not isinstance(steps[0], dict) or steps[0].get(datapath.STEP_VALUE) != main:
        return None
    row = next((r for r in rows if datapath._id_of(r) == main), None)
    guid = datapath._type_guid(row) if row is not None else None
    hit = config.object_by_type_id(guid) if guid else None
    if hit is None or hit[1].lower() != LIST_CATEGORY:
        return None
    return row, hit[0]


def std_attribute(obj, name):
    """Условный `metadata.Attr` стандартного реквизита (тип и длина берутся из свойств объекта) для записи типа колонки. Для
    числового кода и номера операция отказывает.
    """
    typed = obj.std_types.get(name)
    if typed is None:
        return None
    kind, length, allowed = typed
    if kind != "String":
        raise EditError(f"стандартный реквизит «{name}» объекта «{obj.full_name}» — тип «{kind or 'не назван'}», а колонку списка движок пишет только для строки: квалификаторы числа "
                        "у стандартных реквизитов не проверялись")
    return metadata.Attr(name, "", ("xs:string",), (), length, allowed or "Variable")


def column_chars(attr, template):
    """Число знаков ширины колонки (`width_computed`) по классу реквизита (см. описание модуля)."""
    if template == "string":
        return min(attr.string_length, STRING_CHARS_CAP) if attr.string_length else STRING_CHARS_NO_LENGTH
    return CLASS_CHARS[template]


def _set_width(head, chars):
    px = json0.int_exp_text(PX_PER_CHAR * chars)  # целое с нулями на конце платформа записывает экспонентой (`350` → `3.5e2`)
    head["width"] = px
    if "width_mirror" in head:  # у колонок формы версии 10 зеркала ширины нет (позиция появилась позже): новую позицию форме старой версии не дописывают
        head["width_mirror"] = px
    head["width_computed"] = chars


def _check_path_names(parts, form_name, table):
    if len(parts) != 2:
        raise EditError(f"путь колонки списка — «{form_name}.<Колонка>» (два сегмента: реквизит формы, к которому привязана таблица, и колонка), а пришло {'.'.join(parts)!r}; более длинный путь "
                        "(`Список.Реквизит.Поле`) не поддерживается")
    if parts[0] != form_name:
        raise EditError(f"путь колонки списка начинается с имени реквизита формы, к которому привязана таблица «{table}»: «{form_name}»; пришло {parts[0]!r}")


def classify(obj, key, config=None):
    """Определяет, что представляет собой колонка списка с именем `key` у объекта `obj`: `("std", ключ образца)` либо
    `("attr", реквизит, образец колонки табличной части)`. Если колонку нельзя записать, возникает `EditError` с пояснением.

    Функцию используют `add_list_column` и проверка описания (`generate_list`), поэтому отказ описания и отказ редактора
    формулируются одинаково. Если передана выгрузка `config`, проверяется и сам тип: ссылка на объект, которого нет в выгрузке,
    приводит к отказу до правок.
    """
    std = STD_TEMPLATES.get(obj.kind, {})
    if key in std:
        if key != "Картинка" and key not in obj.standard:
            raise EditError(f"колонка «{key}»: у объекта «{obj.full_name}» такого стандартного реквизита нет (стандартные: {', '.join(obj.standard) or 'нет'}) — её включают свойства объекта")
        if key in ("Код", "Номер", "Наименование"):
            std_attribute(obj, key)  # числовой код и номер: отказ
        return "std", std[key]
    attr = next((a for a in obj.attributes if a.name == key), None)
    if attr is None and (key in STD_REFUSED or key in metadata.STANDARD_IDS):  # реквизит с именем стандартного реквизита другого вида (`Дата` у справочника) считается обычным реквизитом, а не отказом
        why = STD_REFUSED.get(key) or "стандартная колонка этого вида у объекта называется иначе (у справочника — Картинка, Код, Наименование; у документа — Картинка, Дата, Номер)"
        raise EditError(f"колонка «{key}» списка «{obj.full_name}»: {why}; в описание такие колонки не берутся")
    if attr is None:
        names = ", ".join(list(std) + [a.name for a in obj.attributes])
        raise EditError(f"у объекта «{obj.full_name}» нет реквизита «{key}» для колонки списка; колонки: {names}")
    try:
        template = columns.template_kind(attr)
        cls = datatype.type_class(attr)
    except datatype.TypeNotWritten as e:
        raise EditError(f"колонка «{key}» списка: {e}") from None
    if cls not in SUPPORTED_ATTRIBUTE_CLASSES:
        raise EditError(f"колонка «{key}» списка «{obj.full_name}»: тип «{datatype.CLASS_WORDS[cls]}» колонка списка не пишет — "
                        + ("булев реквизит в образцах форм встречается без вложенного элемента, и образца такой колонки нет"
                           if cls == "boolean" else "составной тип в колонках списка не проверялся"))
    if config is not None:
        try:
            datatype.pattern_block(attr, config)
        except datatype.TypeNotWritten as e:
            raise EditError(f"колонка «{key}» списка: {e}") from None
    return "attr", attr, template


def build_column(obj, form_name, table, name, data, config=None, unverified=False, old=None):
    """Новая колонка списка по пути `data` (`Реквизит.Колонка`): `(узел колонки, описание пути, слова, заголовок по умолчанию,
    реквизит или None)`. У колонки пока нет ни имени, ни заголовка, ни порядкового номера.

    `old` — функция `(колонка, образец) → (колонка, фраза)` формы старой версии общего блока (`edit.columns.old_column`): образец сводится к версии формы сразу после
    взятия, до правок пути, типа и ширины. У колонки реквизита образец — колонка табличной части, превращённая в колонку списка (`convert_tabular`); сведение такой колонки
    корпус не проверял (образцы списка и табличной части выведены порознь), и в форме старой версии она — отказ (`old(None, "attribute")`).
    """
    from .. import templates
    parts = datapath.split_path(data)
    _check_path_names(parts, form_name, table)
    key = parts[1]
    found = classify(obj, key, config)
    notes = []
    if found[0] == "std":
        column = templates.list_column(found[1])
        if old is not None:
            column, said_old = old(column, f"column-list-{found[1]}")
            if said_old:
                notes.append(said_old)
        base = columns._column_base(column)
        head = columns._column_body(column)
        base[datapath.COLUMN_PATH] = list(STD_PATHS[key])
        if key == "Картинка":
            return column, f"{obj.full_name}.{key} — картинка списка (путь {STD_PATHS[key]})", ["колонка-картинка — образец конструктора без изменений"] + notes, STD_HEADERS[key], None
        attr = std_attribute(obj, key) if key != "Дата" else None
        if attr is not None:
            plan = datapath.column_type_plan(column, attr, None, unverified, f"колонка {name!r}")
            notes.append(datapath.apply_column_type(column, plan[0], f"колонки {name!r}").lstrip("; "))
            notes += plan[1]
            _set_width(head, column_chars(attr, "string"))
        return column, f"{obj.full_name}.{key} — стандартный реквизит (путь {STD_PATHS[key]})", notes, obj.standard_synonyms.get(key) or STD_HEADERS[key], None
    _kind, attr, template = found
    column = templates.tabular_column(template)
    if old is not None:
        old(None, "attribute")
    convert_tabular(column)
    base = columns._column_base(column)
    head = columns._column_body(column)
    base[datapath.COLUMN_PATH] = [0, {datapath.GUID: attr.uuid}]
    for slot in COLUMN_ORDINALS:
        head[slot] = -1
    _set_width(head, column_chars(attr, template))
    return column, f"{obj.full_name}.{key} — реквизит объекта", notes, attr.synonym or attr.name, attr


def convert_tabular(column):
    """Колонка табличной части становится колонкой списка: меняются вид, признак тела и отсутствие четвёртого члена тела."""
    column[COLUMN_TYPE] = {datapath.GUID: schema.LIST_COLUMN}
    body = column[COLUMN_BODY]
    body["u0"] = 4
    body.pop("u3", None)
    return column


def _old_column(doc, table_node, column, template, unverified):
    """Образец колонки списка для формы старой версии: `(колонка, фраза)`; форма версии 16 — как есть. Колонка реквизита (`template == "attribute"`) в форме старой версии — отказ."""
    from .. import old_versions as _old
    version = _design.form_version(doc)
    if version not in _old.VERSIONS or not _old.enabled():
        return column, None
    if template == "attribute":
        if unverified:
            return column, None
        raise EditError(f"колонка списка по реквизиту объекта в форме версии {version} не строится: образец — колонка табличной части, превращённая в колонку списка, а сведение такой "
                        "колонки к версии формы корпус не подтверждает. Дорога — стандартная колонка списка (Картинка, Код, Наименование, Дата, Номер) либо donor: колонка этой же таблицы "
                        "(add_column без data по пути списка). Позвать всё же можно — unverified=True (образец версии 16 в форме версии "
                        f"{version}: при первом сохранении в конфигураторе форма целиком уйдёт в версию платформы)")
    return columns.old_column(doc, table_node, column, template, unverified)


def add_list_column(doc, table, name, header, data, config, form_use, unverified, template, donor):
    """`add_column` для табличного поля списка: стандартная колонка конструктора либо колонка реквизита объекта (см. описание
    модуля). Возвращает слова для отчёта.
    """
    if donor is not None:
        raise EditError("donor у колонки списка не берётся: стандартная колонка — образец конструктора, колонка реквизита — образец колонки табличной части того же класса")
    if template is not None:
        raise EditError(f"template у колонки списка не называют ({template!r}): образец выбирает движок по пути `data` (стандартная колонка или класс реквизита)")
    if form_use is not None:
        raise EditError("form_use у колонки списка не нужен: форма списка — не форма элемента и не форма группы")
    if data is None:
        raise EditError(f"у колонки списка путь данных — обязательный: data=\"<реквизит формы>.<колонка>\" (колонка списка без данных — `[-1]`, как картинка, — отдельным образцом не берётся); "
                        f"колонка {name!r}")
    place = find_element(doc, table)
    block = columns._columns_of(doc, table)
    members = block[COLUMN_ITEMS]
    if name in [columns._column_name(c) for c in members]:
        raise EditError(f"колонка {name!r} у {table!r} уже есть")
    row, obj = list_attribute(doc, place, datapath.load_config(config))  # вызывающий (`add_column`) уже проверил, что таблица является списком
    column, said, notes, default_header, attr = build_column(obj, row.get(datapath.ATTR_NAME), table, name, data, datapath.load_config(config), unverified,
                                                              old=lambda column, template: _old_column(doc, place.element, column, template, unverified))
    head = columns._column_body(column)
    head[COLUMN_NAME] = name
    head[COLUMN_ORDER] = max([columns._column_body(c).get(COLUMN_ORDER) or 0 for c in members], default=-1) + 1
    title = default_header if header is None else header
    if title:  # у картинки заголовка нет вовсе (`count 0`), как у конструктора: пустая запись языка — это не то же самое
        set_text(head[COLUMN_HEADER_TEXT], title)
    if attr is not None:
        plan = datapath.column_type_plan(column, attr, datapath.load_config(config), unverified, f"колонка {name!r}")
        notes.append(datapath.apply_column_type(column, plan[0], f"колонки {name!r}").lstrip("; "))
        notes += plan[1]
    members.append(column)
    block[COLUMNS_COUNT] = len(members)
    return (f"{table}: колонка списка {name!r}, номер {head[COLUMN_ORDER]}, путь данных {columns._column_base(column)[datapath.COLUMN_PATH]} ({said})"
            + "".join(f"; {n}" for n in notes if n))
