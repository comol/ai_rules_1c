"""Привязка данных путём по метаданным: команда `bind` с параметром `data`.

Обычный `bind` по имени реквизита формы записывает путь из одного шага. Этот модуль записывает путь к реквизиту объекта
конфигурации, к табличной части и к колонке. Имя берётся из выгрузки XML (`frm_codec.metadata`), там же находятся id и GUID.
Правило записи получено по формам справочников и документов.

* Поле на реквизит объекта: `[{u0: M}, {u0: 0, u1: {guid: G}}]`. Здесь `M` — номер основного реквизита формы
  (`attributes/u0/main_attribute_id`), а `G` — `uuid` элемента `<Attribute>` верхнего уровня объекта.
* Стандартный реквизит: `[{u0: M}, {u0: -N}]`, GUID нет. Код и Номер имеют `-2`, Наименование и Дата — `-3`, Родитель — `-4`,
  Владелец — `-5` (`metadata.STANDARD_IDS`).
* Табличное поле на табличную часть: `[{u0: M}, {u0: 0, u1: {guid: G_ts}}]`, где `G_ts` — `uuid` элемента `<TabularSection>`.
* Колонка: путь лежит в самой колонке (`u1/u1/u2`). Запись `[0, {guid: G_col}]` — реквизит той же табличной части, `[-2]` —
  НомерСтроки, `[-1]` — «данные не заданы». Вложенному полю колонки путь не записывается.

Вид объекта определяется по типу основного реквизита, а не по имени. В описателе лежит GUID типа `СправочникОбъект.X` или
`ДокументОбъект.X`. В выгрузке объекта тот же GUID — это `TypeId` элемента `xr:GeneratedType` категории `Object`
(`Config.object_by_type_id`). Если тип основного реквизита не принадлежит категории `Object` (форма списка — `List`, выбора,
обработки, регистра), операция отказывает: такие объекты не проверялись.

Группа или элемент. У реквизитов и табличных частей справочника с группами есть свойство `Use`. Форма элемента привязывается
к `ForItem` и `ForFolderAndItem`, форма группы — к `ForFolder` и `ForFolderAndItem` (`MdObject.attributes_for`,
`tables_for`). Какая это форма, указывает параметр `form_use` (`"item"` или `"folder"`), потому что сама форма этого не
хранит. Если у объекта с группами реквизит имеет `Use`, отличный от `ForFolderAndItem`, а `form_use` не задан, операция
отказывает и просит назвать форму. У остальных объектов форма считается формой элемента.

Всё, что шире проверенного, приводит к отказу, который снимается ключом `unverified=True`. Это другой вид элемента и первый шаг,
не являющийся основным реквизитом формы. Исключение: поддерживается случай, когда первый шаг — реквизит формы типа
«обработка-объект», а объект берётся из выгрузки.

Кроме пути `bind` записывает тип. У поля ввода это описатель типа и зеркало квалификаторов (`frm_codec/edit/datatype.py`), у
табличного поля на табличную часть — тип значения поля (`TypeId` части по выгрузке; части без `TypeId` — отказ), у колонки табличной части —
тип колонки и вложенного поля ввода. Если сочетание «вид элемента и класс типа» не проверялось
(флажок на небулев реквизит, число в надписи, составной тип), операция отказывает, а ключ `unverified` отказ снимает. Таблица
привязывается к табличной части, только если все её колонки принадлежат виду колонки табличной части (`TABULAR_COLUMN`). На
форме группы допускаются только стандартные реквизиты `Наименование` и `Родитель`; `Код` и `Владелец` не проверялись. Колонку
табличной части можно создать сразу с данными (`add_column data="Объект.ТЧ.Реквизит"`); без данных она получает `[-1]`. Если у
колонки путь уже задан, `bind` отказывает, а с `replace=True` заменяет путь. Если форма уже привязана к реквизитам объекта,
которых нет в выгрузке, операция отказывает сообщением «выгрузка не этой формы».
"""

import copy
import dataclasses

from .. import metadata, schema
from . import datatype

from .names import (
    ATTR_HEAD,
    ATTR_ID,
    ATTR_LIST,
    ATTR_NAME,
    ATTR_PATTERN,
    BINDINGS,
    BIND_ELEMENT,
    BIND_PATH,
    COLUMN_BODY,
    COLUMN_ORDINALS,
    COLUMN_VALUE_TYPE,
    CONTENT,
    PATH_STEPS,
    PATTERN_KIND,
    PATTERN_TYPES,
    STEP_VALUE,
    _maybe,
)
from .base import EditError, find_element
from .elements import _type_words
from . import columns
from .columns import is_value_list_column


# Позиция пути в базе колонки (`Element.TableBoxColumn.u1.u1`): в карте у неё нет имени, поэтому ключ запасной.
COLUMN_PATH = _maybe("Element.TableBoxColumn.u1.u1", 2)
# Второе число шага `{0, GUID}`: сам GUID в виде блока.
STEP_GUID = _maybe("AttributePathStep", 1)
MAIN_ATTRIBUTE_ID = "main_attribute_id"
GUID, TYPE_GUID = "guid", "value_type"
# Первый сегмент пути, которым называется основной реквизит: и в коде, и в диалоге это «Объект».
OBJECT_WORD = "Объект"
ROW_NUMBER = "НомерСтроки"
ROW_NUMBER_ID = -2
NO_DATA = [-1]

# Виды элемента, которые встречаются на каждом пути. Остальные сочетания приводят к отказу, снимаемому ключом `unverified`.
KINDS_BY_PATH = {
    "attribute": ("TextBox", "ComboBox", "CheckBox", "Label"),
    "standard": ("TextBox",),
    "table": ("TableBox",),
}
PATH_WORDS = {"attribute": "реквизит объекта", "standard": "стандартный реквизит",
              "table": "табличная часть"}


@dataclasses.dataclass(frozen=True)
class Target:
    """Что называет путь `Объект.…`: вид (`attribute`, `standard` или `table`), шаг пути и цель."""
    kind: str
    name: str
    step: dict
    thing: object = None


# Объект формы по типу основного реквизита

def load_config(config):
    """`Config` как есть. Если передана строка или путь, это каталог выгрузки, и он читается через `metadata.load`."""
    if config is None:
        raise EditError("путь по метаданным называет реквизит объекта, а выгрузки конфигурации "
                        "нет: дайте --config КАТАЛОГ (каталог с Catalogs/ и Documents/); у внешней обработки или отчёта — "
                        "--root-xml <Имя>.xml (корневой XML выгрузки внешнего объекта)")
    if isinstance(config, metadata.Config):
        return config
    try:
        return metadata.load(config)
    except metadata.MetadataError as e:
        raise EditError(f"выгрузка конфигурации: {e}") from None


def _attributes(doc):
    attributes = doc.get("attributes") if isinstance(doc, dict) else None
    if not isinstance(attributes, dict):
        raise EditError("у формы не разобраны реквизиты")
    rows = (attributes.get(ATTR_LIST) or {}).get("items") if isinstance(
        attributes.get(ATTR_LIST), dict) else None
    if rows is not None and not (isinstance(rows, list) and all(isinstance(r, dict) for r in rows)):
        raise EditError("список реквизитов формы устроен не так, как у платформы (строка — не запись): "
                        "правленый руками документ?")
    return attributes, rows or []


def short_attribute_rows(rows):
    """Строки реквизитов формы из пяти позиций (форма версии 10). В них позиции 4 нет: имя лежит в `u3`, а описатель в сыром виде
    в `u4`. Читатель реквизитов (`FormAttributes`, `add_attribute`) такие строки не разбирает.
    """
    return [r for r in rows if isinstance(r, dict) and ATTR_NAME not in r]


def short_rows_words(rows):
    """Слова отказа про строки из пяти позиций: их число и причина."""
    short = short_attribute_rows(rows)
    return (f"строки реквизитов формы из пяти позиций ({len(short)} из {len(rows)}; такие строки у форм версии 10): "
            "имя и описатель типа лежат в них иначе, чем в строках из шести позиций, и редактор такие строки не разбирает")


def binding_rows(attributes):
    """Строки таблицы привязок формы устроены иначе, чем ожидается. В этом случае операция отказывает словами, а не трассировкой."""
    block = attributes.get(BINDINGS) if isinstance(attributes, dict) else None
    items = block.get("items") if isinstance(block, dict) else None
    if not isinstance(items, list) or not all(isinstance(r, dict) for r in items):
        raise EditError("у формы не разобрана таблица привязок данных (или строка в ней — не запись)")
    return items


def _id_of(row):
    value = row.get(ATTR_ID)
    return value[0] if isinstance(value, list) and value else None


def _type_guid(row):
    """GUID типа реквизита формы, у которого ровно один тип-ссылка (`#`). Иначе возвращается `None`."""
    pattern = row.get(ATTR_PATTERN)
    types = pattern.get(PATTERN_TYPES) if isinstance(pattern, dict) else None
    if not isinstance(types, list) or len(types) != 1 or not isinstance(types[0], dict) \
            or types[0].get(PATTERN_KIND) != "#":
        return None
    return schema.type_guid(types[0].get(TYPE_GUID))


@dataclasses.dataclass(frozen=True)
class FormObject:
    first: int          # номер реквизита формы — первый шаг пути
    name: str           # имя реквизита формы
    obj: object         # MdObject выгрузки


def form_object(doc, config, first_name, unverified=False):
    """Реквизит формы, который называет первый сегмент пути, и объект выгрузки по типу этого реквизита."""
    attributes, rows = _attributes(doc)
    head = attributes.get(ATTR_HEAD)
    main = head.get(MAIN_ATTRIBUTE_ID) if isinstance(head, dict) else None
    main_row = next((r for r in rows if _id_of(r) == main), None)
    if main_row is None:
        raise EditError("у формы нет основного реквизита (номер в `attributes/u0/main_attribute_id` "
                        "не называет ни одного реквизита) — путь «Объект.…» адресовать не от чего")
    if first_name == OBJECT_WORD or first_name == main_row.get(ATTR_NAME):
        row = main_row
    else:
        row = next((r for r in rows if r.get(ATTR_NAME) == first_name), None)
        if row is None:
            known = ", ".join(str(r.get(ATTR_NAME)) for r in rows) or "—"
            raise EditError(f"первый сегмент пути — «{OBJECT_WORD}» (основной реквизит формы, "
                            f"{main_row.get(ATTR_NAME)!r}) или имя реквизита формы; {first_name!r} "
                            f"не то и не другое. Реквизиты формы: {known}")
        if not unverified:
            raise EditError(
                f"Путь начинается с реквизита формы {first_name!r}, а не с основного "
                f"({main_row.get(ATTR_NAME)!r}). Такой путь встречается в образцах форм только для реквизита типа "
                "«обработка-объект», а не для объекта выгрузки; для него редактор не проверялся. "
                "Чтобы всё же выполнить операцию, передайте unverified=True; результат придётся проверить самостоятельно.")
    guid = _type_guid(row)
    obj = _object_of_type(config, guid, row.get(ATTR_NAME))
    if row is main_row:
        _same_dump(attributes, main, obj, config, unverified)
    return FormObject(_id_of(row), row.get(ATTR_NAME), obj)


def _same_dump(attributes, main, obj, config, unverified):
    """Проверяет, что выгрузка относится к этой форме. Если у формы уже есть привязки `[основной, {0, GUID}]`, все их GUID должны
    найтись у объекта. Копии одной конфигурации имеют общий `TypeId`, а реквизит, созданный в двух базах независимо, получает
    разные `uuid`, поэтому выгрузка другой базы записала бы несуществующий GUID без предупреждения.
    """
    known = {x.uuid for x in list(obj.attributes) + list(obj.tables)}
    foreign = []
    for row in binding_rows(attributes):
        path = row.get(BIND_PATH)
        steps = path.get(PATH_STEPS) if isinstance(path, dict) else None
        if not isinstance(steps, list) or len(steps) != 2 or not isinstance(steps[0], dict) \
                or steps[0].get(STEP_VALUE) != main or not isinstance(steps[1], dict):
            continue
        ref = steps[1].get(STEP_GUID)
        if isinstance(ref, dict) and ref.get(GUID) not in known:
            foreign.append(ref.get(GUID))
    if foreign and not unverified:
        raise EditError(
            f"у формы уже есть привязки к реквизитам или табличным частям объекта, которых у "
            f"«{obj.full_name}» в выгрузке «{config.root}» нет ({len(foreign)}: {', '.join(foreign[:3])}"
            f"{'…' if len(foreign) > 3 else ''}): выгрузка не относится к этой форме. Копии одной конфигурации имеют общий "
            "тип объекта, а реквизит, созданный в двух базах независимо, получает разные uuid, поэтому `bind` записал бы несуществующий "
            "GUID без предупреждения. Возможно также, что реквизит удалён из конфигурации, а форма не обновлена. "
            "Чтобы всё же выполнить операцию, передайте unverified=True; результат придётся проверить самостоятельно.")


def _object_of_type(config, guid, form_attribute):
    """Объект выгрузки по GUID типа реквизита формы. Допускается только категория `Object`, иначе операция отказывает словами."""
    hit = config.object_by_type_id(guid) if guid else None
    if hit is not None and hit[1].lower() == "object":
        return hit[0]
    if hit is not None:
        raise EditError(
            f"тип реквизита формы {form_attribute!r} — не объект, а тип категории «{hit[1]}» объекта "
            f"«{hit[0].full_name}» (форма списка, выбора и т. п.). Путь по метаданным проверялся только для форм "
            "объекта справочника и документа, у которых основной реквизит имеет тип категории Object.")
    source = f"выгрузки «{config.root}»" if config.has_dump else "корневого XML внешнего объекта"
    raise EditError(
        f"тип реквизита формы {form_attribute!r} ({guid or 'не один тип-ссылка'}) — не объект {source}: путь по метаданным "
        "проверялся только для форм объекта справочника, документа, обработки и отчёта (регистр выгрузка не называет). Метаданные называют объекты: "
        + ", ".join(sorted(config.objects))
        + (f". Не прочитаны (файл обработки не разобран): {'; '.join(f'{k} — {v}' for k, v in sorted(config.failed.items()))}"
           if config.failed else ""))


# Разбор пути `Объект.Имя[.Имя]`

def split_path(data):
    if not isinstance(data, str) or not data.strip():
        raise EditError('data — путь строкой вида "Объект.Артикул"')
    parts = [p.strip() for p in data.split(".")]
    if not all(parts):
        raise EditError(f"в пути {data!r} пустой сегмент")
    return parts


def scope(obj, role):
    """Реквизиты и табличные части, которые видны форме: `(реквизиты, табличные части, названа ли форма)`. Параметр `role` равен
    `item`, `folder` или `None`. Если у объекта с группами форма не названа, видно всё, а отказывает уже сам выбранный реквизит
    (`check_use`). У остальных объектов форма считается формой элемента.
    """
    try:
        if role is None:
            if obj.has_folders():
                return obj.attributes, obj.tables, False
            return obj.attributes_for("item"), obj.tables_for("item"), True
        return obj.attributes_for(role), obj.tables_for(role), True
    except metadata.MetadataError as e:
        raise EditError(str(e)) from None


def check_use(obj, thing, what, role, named):
    """Форма элемента привязывается к реквизитам элемента, а форма группы — к реквизитам группы. Перекрёстных привязок не бывает."""
    use = thing.use or metadata.DEFAULT_USE
    if named or use == "ForFolderAndItem":
        return
    raise EditError(f"у объекта «{obj.full_name}» есть группы, а {what} «{thing.name}» — только для "
                    f"{'элементов' if use == 'ForItem' else 'групп'} (Use = {use}): форма элемента привязывается "
                    "к реквизитам элемента, форма группы — группы, и форма не говорит, какая она. Назовите её: "
                    'form_use "item" или "folder"')


# На форме группы из стандартных реквизитов доступны только `Наименование` (-3) и `Родитель` (-4). Для `Код` и `Владелец`
# такие привязки не проверялись.
FOLDER_STANDARD = ("Наименование", "Родитель")


def resolve(obj, name, role=None, unverified=False):
    """Что называет `Объект.<имя>`: реквизит, стандартный реквизит или табличную часть."""
    attrs_all, tabs_all, named = scope(obj, role)
    attrs = [a for a in attrs_all if a.name == name]
    std = name in obj.standard
    tabs = [t for t in tabs_all if t.name == name]
    if len(attrs) + int(std) + len(tabs) > 1:
        raise EditError(f"у объекта «{obj.full_name}» имя {name!r} называет больше одного "
                        "(реквизит, стандартный реквизит, табличную часть) — какой из них, по имени "
                        "не решить")
    if attrs:
        check_use(obj, attrs[0], "реквизит", role, named)
        return Target("attribute", name, {STEP_VALUE: 0, STEP_GUID: {GUID: attrs[0].uuid}}, attrs[0])
    if std:
        if role == "folder" and name not in FOLDER_STANDARD and not unverified:
            raise EditError(
                f"Стандартный реквизит «{name}» на форме группы не встречается: из стандартных реквизитов "
                f"на форме группы бывают только {' и '.join('«' + n + '»' for n in FOLDER_STANDARD)}, а реквизит «{name}» не проверялся. Как подчинение владельцу "
                "(`SubordinationUse`) влияет на формы группы, не проверялось. "
                "Чтобы всё же выполнить операцию, передайте unverified=True; результат придётся проверить самостоятельно.")
        return Target("standard", name, {STEP_VALUE: metadata.STANDARD_IDS[name]})
    if tabs:
        check_use(obj, tabs[0], "табличная часть", role, named)
        return Target("table", name, {STEP_VALUE: 0, STEP_GUID: {GUID: tabs[0].uuid}}, tabs[0])
    hidden = [x for x in list(obj.attributes) + list(obj.tables) if x.name == name]
    if hidden:
        raise EditError(f"у объекта «{obj.full_name}» «{name}» есть, но для другой формы: Use = "
                        f"{hidden[0].use}, а форма — {'группы' if role == 'folder' else 'элемента'} "
                        "(перекрёстных привязок не бывает)")
    if name in metadata.STANDARD_IDS:
        raise EditError(f"у объекта «{obj.full_name}» стандартного реквизита «{name}» нет "
                        f"(в выгрузке его длина или признак не включают); стандартные: "
                        f"{', '.join(obj.standard) or 'нет'}")
    raise EditError(
        f"у объекта «{obj.full_name}» нет реквизита, стандартного реквизита или табличной части "
        f"«{name}». Реквизиты: {', '.join(a.name for a in attrs_all) or 'нет'}; стандартные: "
        f"{', '.join(obj.standard) or 'нет'}; табличные части: "
        f"{', '.join(t.name for t in tabs_all) or 'нет'}")


def kind_gate(path_kind, element_kind, unverified, who):
    """Сравнивает вид элемента с видом пути. Допустимые сочетания перечислены в `KINDS_BY_PATH`, остальные приводят к отказу,
    снимаемому ключом `unverified`.
    """
    if element_kind in KINDS_BY_PATH[path_kind] or unverified:
        return ""
    raise EditError(
        f"{who} — {PATH_WORDS[path_kind]}, а у элемента вида {element_kind} такой путь не встречается "
        f"(он встречается у {', '.join(KINDS_BY_PATH[path_kind])}). "
        "Чтобы всё же выполнить операцию, передайте unverified=True; результат придётся проверить самостоятельно.")


# Привязка элемента

# Сколько привязок по метаданным каждого вида встречается в различных формах: `(вид элемента, путь)` и число.
CORPUS_BIND_DATA = {
    ("TextBox", "attribute"): 1068, ("CheckBox", "attribute"): 439, ("Label", "attribute"): 302,
    ("ComboBox", "attribute"): 7, ("TextBox", "standard"): 353, ("TableBox", "table"): 260,
}


def corpus_words(kind, path_kind):
    """Хвост отчёта: для такого вида элемента путь по метаданным встречается в образцах форм, но в предприятии не проверялся."""
    seen = CORPUS_BIND_DATA.get((kind, path_kind))
    if seen is None:
        return (f"; элемент вида {kind} с путём по метаданным («{PATH_WORDS[path_kind]}»): такого вида "
                "нет в образцах форм, и он не проверялся")
    return (f"; элемент вида {kind} с путём по метаданным («{PATH_WORDS[path_kind]}»): встречается в образцах форм, "
            "но в предприятии не проверялся")


@dataclasses.dataclass(frozen=True)
class Plan:
    """Что `bind` запишет в элемент: шаги пути, слова отчёта и, если есть, тип поля ввода.

    `type_edit` — это `(блок описателя, зеркало, класс)` или `None`, `table_type` — тип значения табличного поля на табличной части (`TypeId`
    части) или `None`, а `notes` — оговорки для отчёта.
    """
    steps: list
    said: str
    type_edit: object = None
    notes: tuple = ()
    path_kind: str = ""
    table_type: object = None


def element_steps(doc, data, place, config, unverified, who, form_use=None):
    """План привязки элемента формы по `data`. Все отказы возникают до какой-либо правки документа."""
    kind = place.element.get("type")
    cfg = load_config(config)
    parts = split_path(data)
    if len(parts) != 2:
        raise EditError(
            f"путь {data!r}: после «{parts[0]}» ожидается ровно одно имя: реквизит, стандартный "
            "реквизит или табличная часть. Более длинные пути (`Объект.Реквизит.Поле`, `Объект.ТЧ.Колонка` у "
            "элемента) не поддерживаются; колонку таблицы задаёт `bind` с table и column")
    found = form_object(doc, cfg, parts[0], unverified)
    target = resolve(found.obj, parts[1], form_use, unverified)
    kind_gate(target.kind, kind, unverified, f"{data!r}")
    said = f"{found.obj.full_name}.{target.name} — {PATH_WORDS[target.kind]}"
    type_edit, table_type, notes = None, None, []
    if target.kind == "attribute":
        type_edit, notes = type_plan(place, kind, target.thing, cfg, unverified, data)
    elif target.kind == "standard":
        if kind == "TextBox":
            notes.append("тип поля не пишется: выгрузка не называет типов стандартных реквизитов "
                         "(Код, Наименование — длина и вид кода; Родитель и Владелец — ссылки) — тип "
                         "остаётся прежним, у платформы он следует за реквизитом")
        if form_use == "folder" and target.name not in FOLDER_STANDARD:
            notes.append(f"«{target.name}» на форме группы не проверялся (unverified)")
    elif target.kind == "table":
        table_columns_gate(place.element, unverified, data)
        table_type, notes = table_type_plan(place, target.thing, unverified, data)
    return Plan([{STEP_VALUE: found.first}, dict(target.step)], said, type_edit, tuple(notes), target.kind, table_type)


def table_type_plan(place, ts, unverified, who):
    """Тип значения табличного поля на табличную часть `ts`: `(TypeId части, оговорки)`. Так пишет конструктор, а с нулевым или чужим типом
    платформа загружает форму, но колонки таблицы выбрасывает (`frm_codec/tabletype.py`). Части без `TypeId` (в выгрузке нет `InternalInfo`
    части) и неразобранный блок типа поля — отказ, снимаемый `unverified`: тогда пишется только путь."""
    from .. import tabletype
    have = tabletype.type_of(place.element)
    if have is None or not ts.type_id:
        why = ("у табличного поля не разобран блок типа значения (`content/u1`)" if have is None else
               f"у табличной части «{ts.name}» в выгрузке нет TypeId (xr:GeneratedType category=\"TabularSection\" в InternalInfo части)")
        if not unverified:
            raise EditError(f"{who!r}: {why} — тип значения табличного поля записать нельзя, а с нулевым или чужим типом платформа загружает форму, "
                            "но колонки таблицы выбрасывает. Позвать всё же можно — unverified=True: запишется только путь, тип поля останется прежним")
        return None, [f"тип табличного поля не записан и остался {have or 'неразобранным'}: {why}"]
    return ts.type_id, []


def table_columns_gate(item, unverified, who):
    """Таблица на табличную часть допускается только с колонками вида колонки табличной части."""
    block = columns.columns_of(item)
    if block is None:
        if unverified:
            return
        raise EditError(f"{who!r}: колонок табличного поля не разобрано: привязка к табличной части требует колонок вида "
                        "`c2cf1953…`, и проверить их нечем. Отказ снимается ключом unverified=True")
    wrong = [(columns._column_name(c), (c.get(columns.COLUMN_TYPE) or {}).get(GUID, "?"))
             for c in block[columns.COLUMN_ITEMS]
             if (c.get(columns.COLUMN_TYPE) or {}).get(GUID) != schema.TABULAR_COLUMN]
    if wrong and not unverified:
        listed = ", ".join(f"{name} ({str(guid)[:8]}…)" for name, guid in wrong[:4])
        raise EditError(
            f"{who!r} — табличная часть, а у табличного поля колонки не вида «колонка табличной части» "
            f"({schema.TABULAR_COLUMN[:8]}…): {listed}{'…' if len(wrong) > 4 else ''}. В образцах форм у таблиц, "
            "привязанных к табличной части объекта, все колонки именно этого вида (колонок списка `48a6ebc3…` и "
            "таблицы значений `737535a4…` у них нет); сочетание «таблица на табличной части и другие колонки» "
            "не проверялось. Чтобы всё же выполнить операцию, передайте unverified=True; результат придётся проверить самостоятельно.")


def type_plan(place, kind, attr, cfg, unverified, who):
    """Тип элемента по реквизиту: `(type_edit, оговорки)`. Всё, что шире проверенного, приводит к отказу, снимаемому `unverified`."""
    classes = datatype.CLASSES_BY_KIND.get(kind)
    if classes is None:
        return None, [f"тип элемента вида {kind} не записывается: привязки у элементов этого вида не встречаются"]
    cls, reason = None, None
    try:
        cls = datatype.type_class(attr)
    except datatype.TypeNotWritten as e:
        reason = str(e)
    if cls is not None and cls not in classes and not unverified:
        raise EditError(
            f"{who!r}: реквизит «{attr.name}» типа «{datatype.CLASS_WORDS[cls]}», а у элемента вида {kind} "
            f"привязки на такой тип не встречаются; они встречаются на {', '.join(datatype.CLASS_WORDS[c] for c in classes)} "
            f"({datatype.KIND_NOTES[kind]}). Чтобы всё же выполнить операцию, передайте unverified=True; результат придётся проверить самостоятельно.")
    if kind != "TextBox":
        if reason is not None and not unverified:
            raise EditError(f"{who!r}: {reason}; у элемента вида {kind} такой реквизит не встречается "
                            "(отказ снимается ключом unverified=True)")
        return None, [f"тип элемента отдельно не пишется: у {kind} описателя типа нет, вид элемента и есть тип"
                      + (f"; {reason}" if reason else "")]
    content = place.element.get(CONTENT)
    datatype.textbox_type_places(content, f"поля {who!r}")
    try:
        block, mirror, cls = datatype.pattern_block(attr, cfg)
    except datatype.TypeNotWritten as e:
        if not unverified:
            raise EditError(f"{who!r}: {e}. Путь записать можно, но тип поля по такому реквизиту операция не "
                            "записывает: с unverified=True будет записан только путь, а тип поля останется прежним") from None
        return None, [f"тип поля НЕ записан и остался {datatype.current_type_words(content)}: {e}"]
    datatype.check_record(content, cls, "field", f"поля {who!r}")  # отказ до правки: строку привязки и тип записывать уже нельзя
    return (block, mirror, cls), []


def apply_type(place, plan, who):
    """Записывает тип поля ввода (у табличного поля на табличной части — тип таблицы) по плану и возвращает слова для отчёта (пусто, если
    записывать нечего)."""
    if plan.table_type is not None:
        from .. import tabletype
        was = tabletype.set_type(place.element, plan.table_type)
        return "" if was == plan.table_type else f"; тип табличного поля: {was} → {plan.table_type} (TypeId табличной части по выгрузке)"
    if plan.type_edit is None:
        return ""
    block, mirror, cls = plan.type_edit
    content = place.element.get(CONTENT)
    was = datatype.current_type_words(content)
    out = f"; тип поля: {was} → {_type_words({PATTERN_TYPES: datatype.blocks_of(block)})} (из реквизита, зеркало квалификаторов записано)"
    return out + datatype.write_type_and_record(content, block, mirror, cls, "field", f"поля {who!r}")


def table_target(doc, table_place):
    """Привязка табличного поля к табличной части: `(реквизит формы, GUID его типа, GUID табличной части)`."""
    if columns.columns_of(table_place.element) is None:
        raise EditError(f"у элемента ({table_place.element.get('type')}) колонок нет — колонки "
                        "бывают у табличного поля")
    attributes, rows = _attributes(doc)
    index = table_place.index
    bound = [r for r in binding_rows(attributes) if r.get(BIND_ELEMENT) == index]
    path = bound[0].get(BIND_PATH) if bound else None
    steps = path.get(PATH_STEPS) if isinstance(path, dict) else None
    if not isinstance(steps, list) or len(steps) != 2 or not isinstance(steps[1], dict) \
            or steps[1].get(STEP_VALUE) != 0 or not isinstance(steps[1].get(STEP_GUID), dict):
        raise EditError("колонка привязывается ОТНОСИТЕЛЬНО табличной части, а у табличного поля "
                        "нет привязки вида «Объект.ТабличнаяЧасть»: сначала `bind` самой таблицы "
                        "(element, data=\"Объект.ИмяТЧ\")")
    row = next((r for r in rows if _id_of(r) == steps[0].get(STEP_VALUE)), None)
    guid = _type_guid(row) if row is not None else None
    return row, guid, steps[1][STEP_GUID].get(GUID)


def column_path(doc, table_place, column_name, data, config, unverified, form_use=None):
    """Новое значение пути колонки по `data`: `(значение, описание, реквизит табличной части или None, порядковый номер)`.

    Порядковый номер — это место реквизита в табличной части по выгрузке (с нуля). У `НомерСтроки` он равен `-2`. Платформа
    записывает его в голову колонки рядом с путём (`COLUMN_ORDINALS`).
    """
    cfg = load_config(config)
    row, guid, ts_guid = table_target(doc, table_place)
    obj = _object_of_type(cfg, guid, row.get(ATTR_NAME) if row is not None else None)
    ts = obj.table_by_uuid(ts_guid)
    if ts is None:
        raise EditError(f"привязка таблицы ({ts_guid}) не называет табличную часть объекта "
                        f"«{obj.full_name}»; табличные части: "
                        f"{', '.join(t.name for t in obj.tables) or 'нет'}")
    if form_use is not None and ts not in scope(obj, form_use)[1]:
        raise EditError(f"табличная часть «{ts.name}» (Use = {ts.use}) не видна форме "
                        f"{'группы' if form_use == 'folder' else 'элемента'}: перекрёстных привязок не бывает")
    parts = split_path(data)
    attributes, _rows = _attributes(doc)
    head = attributes.get(ATTR_HEAD)
    main = head.get(MAIN_ATTRIBUTE_ID) if isinstance(head, dict) else None
    # «Объект» называет основной реквизит. Если таблица привязана к другому реквизиту формы, в пути стоит имя этого реквизита.
    first_names = (OBJECT_WORD, row.get(ATTR_NAME)) if _id_of(row) == main else (row.get(ATTR_NAME),)
    if parts[0] not in first_names:
        who = (f"«{OBJECT_WORD}» либо реквизит формы {row.get(ATTR_NAME)!r}, к которому привязана таблица"
               if len(first_names) == 2 else
               f"имя реквизита формы {row.get(ATTR_NAME)!r}, к которому привязана таблица: он не основной, "
               f"и «{OBJECT_WORD}» его не называет")
        raise EditError(f"путь колонки — «{first_names[0]}.{ts.name}.<Колонка>» (первый сегмент — {who}), "
                        f"а пришло {data!r}")
    if len(parts) != 3:
        raise EditError(f"путь колонки {data!r}: ожидается «{first_names[0]}.{ts.name}.<Колонка>», то есть три "
                        "сегмента; более длинный путь (`Объект.ТЧ.Реквизит.Поле`) не поддерживается")
    if parts[1] != ts.name:
        if any(t.name == parts[1] for t in obj.tables):
            raise EditError(f"колонка {parts[2]!r} названа из табличной части {parts[1]!r}, а "
                            f"таблица формы привязана к {ts.name!r}: колонка берёт реквизит ТОЙ ЖЕ "
                            "табличной части, что и у таблицы")
        raise EditError(f"у объекта «{obj.full_name}» нет табличной части {parts[1]!r}; таблица "
                        f"формы привязана к {ts.name!r}")
    if parts[2] == ROW_NUMBER:
        return [ROW_NUMBER_ID], f"{obj.full_name}.{ts.name}.{ROW_NUMBER} — номер строки", None, ROW_NUMBER_ID
    for k, a in enumerate(ts.attributes):
        if a.name == parts[2]:
            return [0, {GUID: a.uuid}], \
                f"{obj.full_name}.{ts.name}.{a.name} — реквизит табличной части", a, k
    raise EditError(f"у табличной части «{ts.name}» нет реквизита «{parts[2]}»; реквизиты: "
                    f"{', '.join(a.name for a in ts.attributes) or 'нет'}; {ROW_NUMBER} — номер строки")


# Классы типа у колонок табличной части с путём `[0, {guid}]`. Булева нет: для такой колонки платформа ставит флажок.
COLUMN_CLASSES = ("string", "decimal", "dateTime", "catalog", "document", "enum", "composite")


def column_type_plan(column, attr, cfg, unverified, who, checkbox=False):
    """Тип колонки и её вложенного поля ввода по реквизиту табличной части: `(type_edit, оговорки)`. Отказ возникает до правок.

    Параметр `column` — сама колонка (в документе или копия донора в `add_column`). Параметр `checkbox` означает колонку-флажок:
    реквизит обязан быть булевым, тип значения колонки и вложенного флажка не записывается (остаётся умолчание: строка 10, у
    флажка описателя типа нет), а данные записываются в слот ДанныеФлажка (`COLUMN_CHECK_PATH`).
    """
    if attr is None:
        return None, []
    try:
        block, mirror, cls = datatype.pattern_block(attr, cfg)
    except datatype.TypeNotWritten as e:
        if not unverified:
            raise EditError(f"{who}: {e}. Путь записать можно, но тип колонки по такому реквизиту операция не "
                            "записывает: с unverified=True будет записан только путь, а тип колонки останется прежним") from None
        return None, [f"тип колонки и её поля НЕ записан: {e}"]
    if checkbox:
        if cls != "boolean":
            raise EditError(f"{who}: колонка-флажок — для булева реквизита, а «{attr.name}» — «{datatype.CLASS_WORDS[cls]}»")
        return None, ["колонка-флажок по образцу конструктора: данные — в слоте ДанныеФлажка, тип значения колонки остаётся умолчанием "
                      "(строка 10), вложенный элемент — флажок без описателя типа"]
    if cls not in COLUMN_CLASSES and not unverified:
        raise EditError(f"{who}: реквизит «{attr.name}» типа «{datatype.CLASS_WORDS[cls]}», а у колонки табличной "
                        f"части с путём встречаются только {', '.join(datatype.CLASS_WORDS[c] for c in COLUMN_CLASSES)}. "
                        "Для булева реквизита платформа ставит флажок, и колонки с путём такого типа не бывает. "
                        "Чтобы всё же выполнить операцию, передайте unverified=True; результат придётся проверить самостоятельно.")
    head = columns._column_body(column)
    if not isinstance(head.get(COLUMN_VALUE_TYPE), dict) or PATTERN_TYPES not in head[COLUMN_VALUE_TYPE]:
        raise EditError(f"{who}: у колонки нет описателя типа значения, хотя у колонок табличной части он всегда есть. "
                        "Возможно, документ правили вручную.")
    notes = []
    nested = None
    try:
        kind, content = columns.nested_control(head, who)
    except EditError:
        notes.append("вложенного элемента у колонки нет: тип записан только колонке")
    else:
        if kind == "TextBox":
            datatype.textbox_type_places(content, f"вложенного поля {who}")
            datatype.check_record(content, cls, "column", f"вложенного поля {who}")  # отказ до правки
            nested = content
        else:
            notes.append(f"вложенный элемент — {kind}, у колонок с путём в образцах форм бывает только поле ввода, "
                         "поэтому его тип не изменён")
    return (block, mirror, cls, nested), notes


def apply_column_type(column, type_edit, who):
    """Записывает тип колонки и вложенного поля ввода и возвращает слова для отчёта."""
    if type_edit is None:
        return ""
    block, mirror, cls, nested = type_edit
    head = columns._column_body(column)
    was = _type_words(head[COLUMN_VALUE_TYPE])
    head[COLUMN_VALUE_TYPE][PATTERN_TYPES] = datatype.blocks_of(block)
    out = f"; тип колонки: {was} → {_type_words({PATTERN_TYPES: datatype.blocks_of(block)})}"
    if nested is not None:
        out += " (и вложенного поля ввода, зеркало квалификаторов записано)"
        out += datatype.write_type_and_record(nested, block, mirror, cls, "column", f"вложенного поля {who}")
    return out


def check_column_kind(found, table, column, unverified):
    """Путь по метаданным у колонки допустим только для вида «колонка табличной части». Для другого вида операция отказывает, и
    отказ снимается ключом `unverified`.
    """
    if (found.get(columns.COLUMN_TYPE) or {}).get(GUID) != schema.TABULAR_COLUMN and not unverified:
        raise EditError(
            f"колонка {column!r} у {table!r} — вид {(found.get(columns.COLUMN_TYPE) or {}).get(GUID)}, а "
            f"путь «Объект.ТЧ.Реквизит» встречается только у колонок табличной части "
            f"({schema.TABULAR_COLUMN}). Чтобы всё же выполнить операцию, передайте unverified=True; "
            "результат придётся проверить самостоятельно.")


def bind_column(doc, table, column, data, config, unverified, form_use=None, replace=False):
    """Привязка данных колонки табличного поля к реквизиту табличной части: путь и тип."""
    place = find_element(doc, table)
    found = columns._column(doc, table, column)
    if is_value_list_column(found):
        raise EditError(f"колонка {column!r} у {table!r} — колонка СПИСКА ЗНАЧЕНИЙ: её данные лежат "
                        "не путём, а ссылкой в базе, и такая колонка не проверялась")
    new, said, attr, ordinal = column_path(doc, place, column, data, config, unverified, form_use)
    check_column_kind(found, table, column, unverified)
    base = columns._column_base(found)
    if not isinstance(base, dict) or COLUMN_PATH not in base:
        raise EditError(f"у колонки {column!r} нет места пути данных — строение не такое, как у "
                        "обычных колонок")
    now = base[COLUMN_PATH]
    if now != NO_DATA and not replace:
        raise EditError(f"у колонки {column!r} данные уже заданы ({now}) — вторую привязку платформа "
                        "не писала ни разу, и редактор не молчит о ней: замена — bind с replace=true "
                        "(путь и тип колонки перепишутся по новому реквизиту); снять привязку в [-1] "
                        "редактор не умеет")
    type_edit, notes = column_type_plan(found, attr, load_config(config), unverified, f"колонка {column!r}")
    base[COLUMN_PATH] = new
    columns._column_body(found)[COLUMN_ORDINALS[0]] = ordinal
    out = f"привязка колонки: {table}/{column} → {said}; путь колонки {new}, порядковый номер {ordinal}"
    if now != NO_DATA:
        out += f" (заменён прежний {now})"
    out += apply_column_type(found, type_edit, f"колонки {column!r}")
    return out + "".join(f"; {n}" for n in notes)
