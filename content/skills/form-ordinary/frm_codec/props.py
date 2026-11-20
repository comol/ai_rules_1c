"""Поля элемента именами карты: обход с адресами и граница корпуса.

У редактора операции есть не у каждого свойства палитры. Шрифт, события, подписи, кнопки, колонки,
страницы, привязки — своими операциями; а КнопкаВыбора, Маска, ФиксДробнаяЧасть, цвета, флажки и
сотни прочих строк палитры, чей адрес карта знает, правятся общей операцией свойств
(`edit.set_property`). Её держат две вещи отсюда:

* **обход элемента по карте** (`fields`): каждое поле JSON со своим слотом карты, путём ключей и
  адресом файла от якоря. Адрес нужен ради зеркал — у зеркала в карте указан адрес первичного поля
  (`mirror_of`), и найти пару по одним именам нельзя;
* **граница «что видел корпус»** (`CORPUS_PATH`, `corpus_table`): у каждого поля каждого типа —
  какие значения в корпусе встречаются и сколько раз. Файл порождается обходом корпуса
  (`collect` → `summary`), лежит рядом со сводкой корпуса и сверяется корпусной проверкой.

Разбор ключей — тот же, что у записи: какой ключ JSON какой позиции файла принадлежит, решают
`typed.slot_for` и `typed.slot_in_runs`, как у `encode` и `validate`. У узла со счётными списками
номер позиции считается по самому документу (`schema.doc_runs`).

Чего обход не делает: в списки он не заходит вовсе — ни в повтор карты, ни в счётные списки, ни в
отрезки по битам и маске, ни в необязательный блок. Всё, что лежит за списком, — колонки, кнопки,
страницы, обработчики, записи шрифта по битам — у каждого своя операция или свой адрес, и доходить
до них по имени значило бы править чужое тем же словом, что своё.
"""
import collections
import hashlib
import json
import pathlib

from . import schema, stat, typed
from .json0 import Dec, dumps_line
from .datapaths import DATA_DIR

# Слот поля по имени: запись обхода. `trail` — путь ключей JSON от корня обхода, `addr` — путь
# позиций файла от якоря (элемента, колонки, вложенного элемента), `node` — конкретный тип узла,
# которому поле принадлежит, `declared` — тип, которым узел объявлен у родителя (если у узла несколько
# вариантов, это абстрактное имя, и вариант узнаётся по ключу).
Found = collections.namedtuple("Found", "trail addr key slot holder node declared")


def keyed(doc, type_name):
    """`(конкретный тип, [(ключ, позиция файла, слот)])` узла-словаря — разбором записи.

    Слот `None` — позиция безымянная (карта её не называет или имя снято демоцией). Узел, чей тип не
    опознан (сырой или без подходящего варианта), отдаёт пустой список: править в нём по имени нечего.
    """
    if not isinstance(doc, dict) or set(doc) == {typed.RAW}:
        return None, []
    picked = schema.pick_doc(type_name, doc)
    node = schema.MAP.get(picked) if picked else None
    if node is None:
        return picked, []
    out = []
    if node.runs is not None:
        spots, lists = schema.doc_runs(node, doc)
        by_name, by_fallback = {}, {}
        for index, (fallback, slot) in spots.items():
            by_fallback[fallback] = (index, slot)
            if slot is not None:
                by_name[slot.name] = (index, slot)
        runs = {segment.name: (segment, start) for segment, start, _members in lists}
        for key, value in doc.items():
            if key in runs:
                segment, start = runs[key]
                out.append((key, start, segment))
                continue
            index, slot = typed.slot_in_runs((by_name, by_fallback), picked, key, value, ())
            out.append((key, index, slot))
        return picked, out
    by_name = {slot.name: (index, slot) for index, slot in node.fields.items()}
    for key, value in doc.items():
        if node.repeat is not None and key == node.repeat.name:
            out.append((key, node.repeat.start, node.repeat))
            continue
        if key in PAIR_KEYS and key not in by_name:
            continue            # ключ пары (`id` кнопки): он лежит в члене списка, а не в узле
        index, slot = typed.slot_for(node, picked, by_name, key, value, ())
        out.append((key, index, slot))
    return picked, out


# Ключи списков пар: лежат внутри объекта члена рядом с полями узла (`schema.CountedPairs`) и узлу не
# принадлежат — у кнопки командной панели это `id`, её связь с записью действия.
PAIR_KEYS = frozenset(segment.key for node in schema.MAP.values()
                      for segment in (node.runs.segments if node.runs else ())
                      if isinstance(segment, schema.CountedPairs))


def _anchor_trail(anchor_type, at):
    """Ключи JSON у якоря по адресу `at`: у колонки с обёрткой база лежит на `1/1` — `u1/u1`."""
    out, node = [], schema.MAP[anchor_type]
    for index in at:
        slot = schema.slot_at(node, index)
        out.append(slot.name)
        node = schema.MAP.get(getattr(slot, "type", None)) if isinstance(slot, schema.N) else None
    return tuple(out)


def _placed(picked, key, index, trail, addr):
    """`(путь ключей, адрес файла)` поля — в облике якоря.

    Колонка списка значений (`schema.COLUMN_ANCHOR`) кладёт базу на свою позицию 1, а колонка с
    обёрткой — на `1/1`; зеркала карты и таблицы границы считают от второй. Поэтому у базы колонки
    без обёртки путь и адрес — те, что у колонки с обёрткой: голова одна и та же (один узел карты),
    и значение «Ширина» у неё то же поле `u1/u1/u1/width` с той же границей корпуса.
    """
    anchor = schema.COLUMN_ANCHOR.get(picked)
    if anchor is not None and index == anchor[1]:
        return trail + _anchor_trail(anchor[0], anchor[2]), addr + anchor[2]
    return trail + (key,), addr + (index,)


def demoted(doc, type_name, trail=(), addr=(), stop=()):
    """Позиции, чьё имя карты снято демоцией: ключ `u<индекс>`, а карта позицию называет.

    Значение там не того вида, что объявила карта (у ширины колонки — `1e2`, умолчание платформы), и
    потому JSON зовёт позицию запасным ключом. Править такое поле по имени законно — значение
    нужного вида вернёт позиции имя (`edit.set_property`). `Found.slot` — слот карты на этой
    позиции, `Found.key` — запасной ключ документа.
    """
    picked, keys = keyed(doc, type_name)
    node = schema.MAP.get(picked) if picked else None
    if node is None:
        return
    spots = schema.doc_runs(node, doc)[0] if node.runs is not None else None
    for key, index, slot in keys:
        value = doc.get(key)
        if slot is None:
            named = spots.get(index, (None, None))[1] if spots is not None \
                else schema.slot_at(node, index)
            if isinstance(named, schema.F):
                yield Found(trail + (key,), addr + (index,), key, named, doc, picked, type_name)
            continue
        if key in stop or not isinstance(slot, schema.N) or not isinstance(value, dict):
            continue
        inner = schema.MAP.get(slot.type)
        if inner is not None and inner.packed is not None:
            continue
        yield from demoted(value, slot.type, *_placed(picked, key, index, trail, addr), stop)


def fields(doc, type_name, trail=(), addr=(), stop=()):
    """Все названные поля узла и его блоков — `Found` на каждое, сверху вниз, в порядке файла.

    Спускается только в блоки (`schema.N`) со значением-объектом; в списки и отрезки раскладки не
    заходит (см. описание модуля). `stop` — ключи, в чьё значение спускаться не надо: поле само
    отдаётся, а его внутренность — нет (шрифт, события, вложенный элемент колонки).

    Упакованный узел (конверт вложенного элемента) адресов файла внутри себя не имеет: позиции карты
    лежат в строке base64. Обход в него не спускается — вложенный элемент правят отдельным корнем
    (`edit.column_control`), и адрес там считается от элемента его вида.
    """
    picked, keys = keyed(doc, type_name)
    for key, index, slot in keys:
        if slot is None:
            continue
        here, where = _placed(picked, key, index, trail, addr)
        yield Found(here, where, key, slot, doc, picked, type_name)
        value = doc.get(key)
        if key in stop or not isinstance(slot, schema.N) or not isinstance(value, dict):
            continue
        inner = schema.MAP.get(slot.type)
        if inner is not None and inner.packed is not None:
            continue
        yield from fields(value, slot.type, here, where, stop)


def bit_slot(slot, bit):
    """Псевдослот ОДНОГО бита битового слова: имя бита, вид — булево, источник поля."""
    return schema.F(bit, schema.BOOL, slot.source)


def is_container(slot):
    """Блок-родитель свойств, а не свойство: безымянный блок (`u1`), содержимое элемента и блок имени.
    У родителя нет строки палитры — есть его поля, и ставить его целиком значило бы править разом
    всё, что в нём лежит.
    """
    if not isinstance(slot, schema.N):
        return False
    return schema.is_placeholder(slot) or slot.type.startswith("Content.") \
        or slot.type == "NameBlock" or slot.type in FORM_CARRIERS


# Родители свойств у корня формы: блок формы, заголовок (текст и счётчик индексов), контейнер, его
# держатель, блок содержимого, общий блок свойств, основной реквизит и реквизиты. Строки палитры у
# них нет — есть их поля, — а строение у каждой формы своё (в контейнере лежат все элементы формы):
# считай граница такой блок значением, таблица держала бы по строке на форму.
FORM_CARRIERS = frozenset({"FormBlock", "Title", "Container", "LayoutHolder", "LayoutList",
                           "Layout", "MainAttribute", "Attributes"})


# ── Класс значения: чем значение отличается для границы корпуса ───────────────────────────────

# Флаги строения, которых карта флагом не объявила: значение решает, что лежит на соседних позициях,
# а нескольких вариантов узла или необязательного блока под это в карте нет. Такое поле по имени не пишется
# (`edit._property_refusal`, слова у каждого — `edit.STRUCTURE_FLAG_WORDS`), а в строении блока учитывается
# значением: блок с флагом, при котором соседей у него не столько, — другое строение, и граница его
# не видела.
#
# * источник картинки 3 — картинка, вложенная в форму, и позиция 7 тогда несёт тело (`#base64`), а
#   при 0, 1 и 2 — число (`edit.CORPUS_PICTURE_BODIES`);
# * метка картинки — за ней следует длина записи: метки 3 и 7 бывают у записи без хвостовой позиции,
#   4 и 8 — у записи с ней, 0 — у пустой картинки поля картинки; длина называет метку однозначно
#   (`edit.CORPUS_PICTURES`). Метка 4 при длине метки 3 — запись, которой платформа не пишет.
STRUCTURE_FLAGS = frozenset({("Picture", "source"), ("Picture", "mark")})
# Версия записи — строение по правилу самой операции (за версией следует длина, и по имени её не
# пишут): в строении блока она учитывается значением, как флаги выше. У набора картинок надписи и панели
# версия называет длину однозначно (3 — три позиции, 4 — пять, 7 — восемь, 8 — девять).
VERSION_KEYS = ("record_version", "version")
# Версия записи безымянная: карта позицию не называет, а по ней видно, какой записи держатель. У
# головы колонки первое число — 15…19, и метка картинок колонки ходит парой с ним: при 15 — 3, при
# 17, 18 и 19 — 4, при 16 — и 3, и 4. Голова у колонки двух строений (варианты
# `schema.COLUMN_HEAD_FORK`), и версия у обоих — первое число.
UNNAMED_VERSIONS = {name: "u0" for name in schema.variants(schema.COLUMN_HEAD_FORK)}
# Набор картинок самой формы (`layout_list/pictures`): позиция 0 — версия его записи, как у наборов
# надписи, панели и поля картинки, только карта её не назвала. 3 при версии общего блока 10, 4 при
# 13, 7 при 15, 8 при 16 — и длина набора следует за ней (3, 5, 8, 9 позиций). Без неё партнёром
# метки картинки формы стала бы версия всей формы.
UNNAMED_VERSIONS["PictureSet.Form"] = "u0"
# Поля, чьё значение ходит парой с другим полем. Граница у такого поля двойная: одиночная строка
# (`путь`) и строка пары (`путь@ключ=значение`, `paired_path`) — её `collect` пишет рядом. Партнёр —
# `VERSION` (версия ближайшей записи по дороге к полю, `version_of`) либо `(узлы-держатели, ключ)`:
# ближайший держатель одного из этих узлов и значение под ключом. Сочетания, которые строение блока
# различает само (перечисления и флаги учитываются в нём значением), сюда не входят: тут только целые,
# смысл которых зависит от другого поля:
#
# * метка картинки ↔ версия записи-владельца (у кнопки при `record_version` 10 — 3, при 13 и 14 — 4;
#   у надписи и панели — при `version` 3 против 4, 7, 8; у поля картинки при версии 3 — ноль,
#   картинка пуста; у колонки — при первом числе головы, `UNNAMED_VERSIONS`);
# * код цвета ↔ вид цвета (у цвета и у рамки): код значит разное у разных видов — RGB при 0, номер
#   веб-цвета при 2, элемент стиля (отрицательный) при 3, при 4 (авто) почти всегда 0;
# * код ссылки картинки ↔ источник: код стандартной картинки платформы (−8, −9, …) бывает только у
#   источника 1 без GUID, у прочих источников код — 0 (у заголовка страницы панели — 3 и 4).
VERSION = "версия записи"
PAIRED = {
    ("Picture", "mark"): VERSION,
    ("ColorValue", "code"): (("Color", "Border"), "color_kind"),
    ("PictureRef", "code"): (("Picture",), "source"),
}


def holders(by_trail, trail, start=0):
    """Держатели по дороге к полю: `(узел, словарь)` каждого шага `trail[:k]` при `k > start`.

    `by_trail` — `{путь: Found}` одного обхода; шаг, которому поля не досталось (колонка списка
    значений кладёт базу двумя ключами на одну позицию, `_placed`), пропускается. Узел нужен версии,
    которую карта не называет (`UNNAMED_VERSIONS`), и партнёру пары (`PAIRED`).
    """
    return [(by_trail[trail[:k]].node, by_trail[trail[:k]].holder)
            for k in range(start + 1, len(trail) + 1) if trail[:k] in by_trail]


def _int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def version_of(chain):
    """Версия БЛИЖАЙШЕЙ записи по дороге к полю: `(ключ, значение)` или `None`."""
    for node, holder in reversed(chain):
        if not isinstance(holder, dict):
            continue
        for key in VERSION_KEYS + ((UNNAMED_VERSIONS[node],) if node in UNNAMED_VERSIONS else ()):
            if _int(holder.get(key)):
                return key, holder[key]
    return None


def partner_of(field, chain):
    """Партнёр поля, что ходит парой (`PAIRED`): `(ключ, значение)` или `None`.

    `field` — `(узел, ключ)` поля, `chain` — держатели по дороге к нему (`holders`)."""
    spec = PAIRED.get(field)
    if spec is None:
        return None
    if spec == VERSION:
        return version_of(chain)
    nodes, key = spec
    for node, holder in reversed(chain):
        if node in nodes and isinstance(holder, dict):
            return (key, holder[key]) if _int(holder.get(key)) else None
    return None


def dependents(field):
    """Поля, чей партнёр — это поле: `[(узел, ключ)]` (у вида цвета — код цвета)."""
    node, key = field
    return [pair for pair, spec in PAIRED.items()
            if spec != VERSION and node in spec[0] and key == spec[1]]


def paired_path(path, partner):
    """Путь строки ПАРЫ «поле + партнёр» в таблице границы."""
    return f"{path}@{partner[0]}={partner[1]}"


def shape(value, type_name):
    """Строение значения-блока для границы корпуса — строкой, одной на одинаково устроенные.

    Строение — про устройство блока, а не про значения: перечисления, флаги, флаги строения вне
    карты (`STRUCTURE_FLAGS`) и версии записи (`VERSION_KEYS`) учитываются значением, а числа, строки и
    GUID — видом; список — множеством строений своих членов (у многоязычной строки «одна запись» и
    «две записи» одного строения, а «пусто» и «есть» — разного). Значений целых подполей строение не
    различает, поэтому граница блока строением не кончается: каждое скалярное подполе сверяется по
    своей строке таблицы, той же, что при записи подполя по имени (`edit._block_bounds`), а поле,
    что ходит парой (`PAIRED`), — ещё и строкой пары.
    """
    picked, keys = keyed(value, type_name) if isinstance(value, dict) else (None, [])
    if not isinstance(value, dict):
        return _scalar_shape(None, value)
    slots = {key: slot for key, _index, slot in keys}
    parts = []
    for key, item in value.items():
        slot = slots.get(key)
        if ((picked, key) in STRUCTURE_FLAGS or key in VERSION_KEYS) \
                and not isinstance(item, (dict, list)):
            parts.append(f"{key}:{dumps_line(item, bools=True)}")
        elif isinstance(slot, schema.N) and isinstance(item, dict):
            parts.append(f"{key}:{shape(item, slot.type)}")
        elif isinstance(slot, (schema.R, schema.Counted)) and isinstance(item, list):
            parts.append(f"{key}:[" + "|".join(sorted({shape(member, slot.type)
                                                       for member in item})) + "]")
        elif isinstance(item, list):
            parts.append(f"{key}:[" + "|".join(sorted({_scalar_shape(None, member)
                                                       for member in item})) + "]")
        else:
            parts.append(f"{key}:{_scalar_shape(slot, item)}")
    return "{" + ",".join(parts) + "}"


def _scalar_shape(slot, value):
    """Скаляр в строении блока: перечисление и флаг — значением, остальное — видом."""
    kind = getattr(slot, "kind", None)
    if isinstance(value, bool) or kind in (schema.ENUM, schema.BOOL):
        return dumps_line(value, bools=True)
    if isinstance(value, dict):
        if set(value) == {"guid"}:
            return "guid"
        return "{" + ",".join(f"{k}:{_scalar_shape(None, v)}" for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + "|".join(sorted({_scalar_shape(None, v) for v in value})) + "]"
    if isinstance(value, Dec):
        return "dec"
    if isinstance(value, int):
        return "int"
    if isinstance(value, str):
        return "str"
    return "null" if value is None else type(value).__name__


# ── Корни правки: элемент, колонка, вложенный элемент ──────────
# Якорь — то, чьим именем зовётся поле в таблице границы: тип элемента (`TextBox`), колонка
# (`TableBoxColumn`) и вложенный элемент колонки (`ColumnControl.TextBox`). У вложенного якорь свой
# нарочно: палитра у него своя, и что видел корпус у поля ввода формы, о поле ввода в колонке ничего
# не говорит.
COLUMN_ANCHOR = "TableBoxColumn"
# Тип корня колонки — абстрактный, конкретный вариант определяется по GUID вида: колонка с обёрткой разбирается узлом
# `Element.TableBoxColumn`, колонка списка значений — своим. Назови корень конкретным типом, и обход
# колонки списка значений читал бы её ключи чужим узлом.
COLUMN_TYPE = "TableBoxColumn"
assert COLUMN_TYPE in schema.FORKS, "у колонки табличного поля в карте больше нет нескольких вариантов"
NESTED_ANCHOR = "ColumnControl."
PAGE_ANCHOR = "PanelPage"
BUTTON_ANCHOR = "CommandBarButton"
# Пункт меню кнопки формы — узел тот же, что у кнопки панели, а якорь свой: у пунктов меню своя
# граница (`edit.CORPUS_MENU_ITEMS`); что видел корпус у кнопок панелей, о пунктах меню не говорит.
MENU_ANCHOR = "CommandBarButton.Menu"
# Имена наборов и кнопок в блоке действий — у карты, а не литералом.
BUTTON_KEYS = (schema.MAP["CommandBarActions"].runs.segments[1].name,
               schema.MAP["ButtonSet"].runs.segments[0].name)
# Блок меню кнопки формы — необязательный блок её тела (флаг строения — режим меню).
MENU_BLOCK = next(segment.name for segment in schema.MAP["Content.Button.u1"].runs.segments
                  if isinstance(segment, schema.Gated))
# Ключи, в которые обход элемента не спускается: блок координат (его ведут операции размещения, а не
# правка свойства) и список вложенных элементов (у каждого свой корень). У колонки — её вложенный
# элемент: он отдельный корень со своим якорем.
ELEMENT_STOP = ("coords", "elements")
COLUMN_STOP = ("control",)
# Корень самой формы: якорь границы — `Form`, корень — весь документ. Обход не заходит в элементы
# (свои корни), в списки обработчиков, в страницы формы (её встроенный контейнер страниц), в
# реквизиты с привязками (`add_attribute`, `bind`), в связи контекстного меню (плоский список
# записей всех элементов, у формы — владелец 0) и в «Сохраняемые значения» (список записей, а у
# формы объекта на этом месте события объекта — заметка узла `SavedValues`). Сами эти ключи обход
# отдаёт, и `set_property` отвечает на них словами.
FORM_ANCHOR = "Form"
FORM_TYPE = "Form"
FORM_STOP = ("elements", "events", "pages", "attributes", "context_menu_links", "saved_values")
# Блок основного реквизита (`main_attribute/u2`) — блок настроек сохранения значений только у форм
# отчёта и обработки: там «Сохраняемые значения» — список со счётчиком. У формы объекта на тех же
# позициях другое (события объекта, флаг, которого палитра формы объекта не показывает), и граница
# поля `save_values` у такой формы не считается: иначе «в корпусе таких N» складывало бы два разных
# свойства под одним именем.
FORM_SETTINGS_PATH = ("main_attribute", "u2")


def form_settings(doc):
    """Строение блока основного реквизита формы: «настройки», «события объекта», «иное» или «без блока»
    (числа корпуса — `edit.CORPUS_FORM_SETTINGS`).
    """
    main = doc.get(FORM_SETTINGS_PATH[0]) if isinstance(doc, dict) else None
    block = main.get(FORM_SETTINGS_PATH[1]) if isinstance(main, dict) else None
    if not isinstance(block, dict):
        return "без блока"
    saved = block.get("saved_values")
    if not isinstance(saved, dict):
        return "иное"
    return "настройки" if "count" in saved else "события объекта"


def _repeat_name(type_name):
    return schema.MAP[type_name].repeat.name


def elements(doc):
    """Все элементы формы на любой глубине — в порядке файла."""
    form = doc.get("form") if isinstance(doc, dict) else None
    holder = form.get("container") if isinstance(form, dict) else None
    out = []
    items_key = _repeat_name("Elements")

    def walk(node):
        block = node.get("elements") if isinstance(node, dict) else None
        for item in (block.get(items_key) or []) if isinstance(block, dict) else []:
            if isinstance(item, dict) and isinstance(item.get("type"), str):
                out.append(item)
                walk(item)

    walk(holder)
    return out


def columns(element):
    """Колонки табличного поля — узлы `Element.TableBoxColumn`, найденные обходом карты."""
    for found in fields(element, "Element", stop=ELEMENT_STOP):
        if isinstance(found.slot, schema.N) and found.slot.type == "TableBoxColumns":
            block = found.holder.get(found.key)
            return [item for item in (block.get(_repeat_name("TableBoxColumns")) or [])
                    if isinstance(item, dict)] if isinstance(block, dict) else []
    return []


def buttons(element):
    """Кнопки командной панели — узлы `Element.CommandBarButton` всех её наборов, по порядку.

    Только панели: у кнопки формы меню лежит в необязательном блоке, и его пункты — кнопки того же
    узла, но граница у них своя (`edit.CORPUS_MENU_ITEMS`), и в якорь панели их мешать нельзя.
    """
    out = []
    for found in fields(element, "Element", stop=ELEMENT_STOP):
        if isinstance(found.slot, schema.N) and found.slot.type == "CommandBarActions":
            out += _set_buttons(found.holder.get(found.key))
    return out


def _set_buttons(block):
    """Кнопки всех наборов блока действий, по порядку."""
    out = []
    sets_key, buttons_key = BUTTON_KEYS
    for button_set in (block.get(sets_key) or []) if isinstance(block, dict) else []:
        for item in (button_set.get(buttons_key) or []) if isinstance(button_set, dict) else []:
            if isinstance(item, dict):
                out.append(item)
    return out


def menu_items(element):
    """Пункты меню кнопки ФОРМЫ — узлы `Element.CommandBarButton` блока меню её тела.

    Обход карты в необязательный блок не заходит (см. описание модуля), поэтому блок меню берётся
    по имени отрезка у тела кнопки — ровно тем же путём, каким его заводит `set_menu_mode`."""
    for found in fields(element, "Element", stop=ELEMENT_STOP):
        if isinstance(found.slot, schema.N) and found.slot.type == "Content.Button.u1":
            body = found.holder.get(found.key)
            return _set_buttons(body.get(MENU_BLOCK)) if isinstance(body, dict) else []
    return []


def pages(element):
    """Страницы панели — узлы `Element.PanelPage`, найденные обходом карты."""
    for found in fields(element, "Element", stop=ELEMENT_STOP):
        if isinstance(found.slot, schema.N) and found.slot.type == "PanelPages":
            block = found.holder.get(found.key)
            picked = schema.pick_doc("PanelPages", block) if isinstance(block, dict) else None
            items = block.get(_repeat_name(picked)) if picked in schema.MAP else None
            return [item for item in items or [] if isinstance(item, dict)]
    return []


def nested(column):
    """Содержимое вложенного элемента колонки и его вид: `(содержимое, вид)` или `None`.

    Конверт раскрыт — содержимое лежит объектом; сырым (не раскрылся на этой машине) или без
    элемента вовсе (пустой тип) — `None`: по имени там править нечего."""
    content_key = schema.MAP["ColumnControl.Packed"].fields[0].name
    for found in fields(column, COLUMN_TYPE):
        if isinstance(found.slot, schema.N) and found.slot.type == "ColumnControl.Packed":
            value = found.holder.get(found.key)
            content = value.get(content_key) if isinstance(value, dict) else None
            picked = schema.pick_doc("ColumnControl", content) \
                if isinstance(content, dict) and set(content) != {typed.RAW} else None
            if picked is None:
                return None
            return content, picked[len("Content."):]
    return None


def roots(doc):
    """`(якорь, корень, тип корня, стоп-ключи, адрес корня от якоря)` — всё, что правится по имени.

    Адрес корня нужен ради зеркал: у вложенного элемента корнем обхода служит его содержимое, а
    адреса зеркал карта считает от элемента того же вида (`schema.packed_anchor`), где содержимое —
    позиция 2.

    Первым идёт корень самой формы: свойства формы граница считает под своим якорем (`FORM_ANCHOR`),
    как у элемента, — а в элементы, реквизиты, страницы и списки обработчиков обход от корня формы
    не заходит (`FORM_STOP`): у каждого свой корень или своя операция.
    """
    if isinstance(doc, dict) and isinstance(doc.get("form"), dict):
        yield FORM_ANCHOR, doc, FORM_TYPE, FORM_STOP, ()
    for element in elements(doc):
        yield element["type"], element, "Element", ELEMENT_STOP, ()
        for page in pages(element):
            yield PAGE_ANCHOR, page, "Element.PanelPage", (), ()
        for button in buttons(element):
            yield BUTTON_ANCHOR, button, "Element.CommandBarButton", (), ()
        for item in menu_items(element):
            yield MENU_ANCHOR, item, "Element.CommandBarButton", (), ()
        for column in columns(element):
            yield COLUMN_ANCHOR, column, COLUMN_TYPE, COLUMN_STOP, ()
            inner = nested(column)
            if inner is not None:
                content, kind = inner
                yield NESTED_ANCHOR + kind, content, "ColumnControl", (), (2,)


# ── Граница корпуса: что встречается у каждого поля каждого якоря ────────────────────────────

CORPUS_PATH = DATA_DIR / "corpus_props.json"
# Сколько значений держать поимённо. Больше — и поле читается диапазоном (целое, дробное) или видом
# (строка — пустая или непустая, GUID — любой): перечень сотен чисел и тысяч строк был бы не
# границей, а архивом.
VALUES_KEPT = 30
# Строение блока длиннее этого — хешем: граница спрашивает «такое строение встречалось?», а не
# «какое».
SHAPE_CHARS = 400
# Ключи, чьи значения граница не ведёт вовсе: у каждого своя операция или своё строение, и
# `set_property` отказывает на них раньше, чем спросит корпус (`edit.PROPERTY_OPS`).
# Виды, у которых значение — число: граница у такого поля при многих значениях читается диапазоном.
# Одно место на сводку и на операцию: вид целого двумя записями (`int-exp`) в одном из двух перечней
# отправил бы ширину колонки «такого не видели» при любом новом числе.
NUMBER_KINDS = frozenset({schema.INT, schema.DEC, schema.INT_EXP, schema.INT_DEC})
NOT_COUNTED = ("events", "font", "header_font", "footer_font", "text_font",
               "type_link", "columns", "actions", "pages", "menu", "name", "index", "type",
               "coords", "elements", "control", "control_type", "choice_list",
               "view")  # вид поля ввода — свойство формы, его пишет `set_view`


def value_text(slot, value):
    """Значение поля одной строкой — ключ таблицы границы. У блока — его строение (`shape`)."""
    if isinstance(slot, schema.N):
        text = "shape:" + shape(value, slot.type)
        if len(text) > SHAPE_CHARS:
            text = "shape#" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
        return text
    return dumps_line(value, bools=True)


def collect(doc):
    """Одна форма → `Counter` по `(якорь, путь ключей, вид, значение строкой)`.

    Вид — вид поля карты (`bool`, `enum`, `int`, …, `node` у блока, `bit` у бита слова): по нему
    сводка решает, держать значения поимённо или диапазоном. Бит битового слова считается отдельным
    полем (`путь/бит`): правят его по одному, и граница у каждого своя. Поле, что ходит парой
    (`PAIRED`: с версией своей записи, с видом цвета, с источником картинки), считается ещё и
    строкой пары (`путь@ключ=значение`).
    """
    out = collections.Counter()
    for anchor, root, root_type, stop, _base in roots(doc):
        by_trail = {}
        foreign = anchor == FORM_ANCHOR and form_settings(root) != "настройки"
        for found in fields(root, root_type, stop=stop + NOT_COUNTED):
            by_trail[found.trail] = found
            # Стоп-ключ корня обход отдаёт, но граница его не считает: у элемента это координаты и
            # вложенные (они и так в `NOT_COUNTED`), у формы — ещё реквизиты, связи контекстного
            # меню и «Сохраняемые значения» (`FORM_STOP`).
            if found.key in NOT_COUNTED or found.key in stop:
                continue
            if foreign and found.trail[:2] == FORM_SETTINGS_PATH:
                continue
            value = found.holder.get(found.key)
            path = "/".join(found.trail)
            slot = found.slot
            if isinstance(slot, schema.F):
                if slot.kind == schema.BITS and isinstance(value, dict):
                    for bit in slot.bits:
                        if bit in value:
                            out[(anchor, f"{path}/{bit}", "bit",
                                 dumps_line(value[bit], bools=True))] += 1
                    continue
                out[(anchor, path, slot.kind, value_text(slot, value))] += 1
                partner = partner_of((found.node, found.key), holders(by_trail, found.trail))
                if partner is not None:
                    out[(anchor, paired_path(path, partner), slot.kind,
                         value_text(slot, value))] += 1
            elif isinstance(slot, schema.N) and isinstance(value, dict) \
                    and not is_container(slot):
                out[(anchor, path, "node", value_text(slot, value))] += 1
    return out


def is_text_data(text):
    """Значение-строка, которое написал автор формы (имя, подпись, маска), а не платформа: непустая строка вне
    `stat.PLATFORM_STRINGS`. В таблицу границы такие значения не идут: граница у поля-строки читается видом (пустая или
    непустая строка, `strings`, `empty`). Строки перечислений (`kind` равен `enum`) сюда не попадают — их вызывает только
    поле вида `str`."""
    if not text.startswith('"'):
        return False
    try:
        value = json.loads(text)
    except ValueError:
        return False
    return isinstance(value, str) and value not in stat.PLATFORM_STRINGS


def is_foreign_guid(text, common=frozenset()):
    """Значение содержит GUID, которого нет ни среди постоянных платформы (`stat.PLATFORM_GUIDS`), ни среди общих
    (`stat.common_guids`, не меньше чем в трёх конфигурациях): идентификатор картинки, стиля, меню или типа из конфигурации.
    Такие значения в таблицу границы не идут: пользователю перечень чужих идентификаторов бесполезен, а значение без записи
    граница читает как невиданное."""
    return any(g.lower() not in stat.PLATFORM_GUIDS and g.lower() not in common for g in stat.GUID_TEXT.findall(text))


def summary(counter, common=frozenset()):
    """Счёт по корпусу → таблица границы: `{якорь: {путь: запись}}`.

    Запись — вид поля, число наблюдений `n`, число разных значений `distinct` и сами значения
    (`values`, по убыванию частоты, не больше `VALUES_KEPT`; строки, написанные автором формы, и GUID, не общие для
    конфигураций, в них не входят — `is_text_data`, `is_foreign_guid`; `common` — множество общих GUID). Когда разных значений больше, у целого
    и дробного добавляется диапазон (`range`), у строки — сколько пустых (`empty`), и граница
    читается уже по ним, а не по перечню: это сказано полем `open`.

    Вид у поля бывает разным от значения к значению — у выбранного значения переключателя вид
    называет соседняя буква (`N` — целое, `B` — булево, `S` — строка). Тогда `kind` — все виды через
    `|` (`kinds`), диапазон считается по числам при любом виде строки, а строк — сколько их
    (`strings`): иначе целое, которое платформа писала, отвергалось бы как «строка», а «непустых
    строк» насчитывались бы заодно и целые с булевыми.
    """
    rows = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    kinds = collections.defaultdict(set)
    for (anchor, path, kind, text), count in counter.items():
        rows[anchor][path][text] += count
        kinds[(anchor, path)].add(kind)
    out = {}
    for anchor in sorted(rows):
        table = {}
        for path in sorted(rows[anchor]):
            values = rows[anchor][path]
            every = kinds[(anchor, path)]
            kind = "|".join(sorted(every))
            ordered = sorted(values.items(), key=lambda kv: (-kv[1], kv[0]))
            # Строения блока держатся все: их у поля единицы и десятки, а граница у блока по
            # строению и есть — «такого строения корпус не видел» надо уметь сказать про любое.
            kept = len(ordered) if kind == "node" else VALUES_KEPT
            entry = {"kind": kind, "n": sum(values.values()), "distinct": len(values),
                     "values": [[text, count] for text, count in ordered[:kept]
                                if not (schema.STR in every and is_text_data(text)) and not is_foreign_guid(text, common)]}
            if len(every) > 1 and schema.STR in every:
                entry["strings"] = sum(count for text, count in values.items()
                                       if text.startswith('"'))
            if len(values) > kept:
                entry["open"] = True
                numbers = [_number(text) for text in values]
                numbers = [number for number in numbers if number is not None]
                if every & NUMBER_KINDS and numbers:
                    entry["range"] = [min(numbers), max(numbers)]
                if schema.STR in every:
                    entry["empty"] = values.get('""', 0)
            table[path] = entry
        out[anchor] = table
    return out


def row_kinds(row):
    """Виды поля строки таблицы — множеством (у поля переменного вида их несколько, `summary`)."""
    return set(row["kind"].split("|")) if row else set()


def _number(text):
    """Число из значения строкой; `None` — не число. Дробное записывается строкой `Dec` — берём как есть."""
    try:
        value = json.loads(text)
    except ValueError:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if float(value).is_integer() else value
    return None


def write(table, path=CORPUS_PATH):
    """Таблица на диск: по строке на поле, ключи по порядку — чтобы дифф показывал, КАКОЕ поле
    изменилось, а не «файл переписан»."""
    lines = ["{"]
    anchors = list(table)
    for a, anchor in enumerate(anchors):
        lines.append(f" {json.dumps(anchor, ensure_ascii=False)}: {{")
        paths = list(table[anchor])
        for p, key in enumerate(paths):
            tail = "," if p < len(paths) - 1 else ""
            lines.append(f"  {json.dumps(key, ensure_ascii=False)}: "
                         f"{json.dumps(table[anchor][key], ensure_ascii=False, sort_keys=True)}"
                         f"{tail}")
        lines.append(" }" + ("," if a < len(anchors) - 1 else ""))
    lines.append("}")
    pathlib.Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


_TABLES = {}


def corpus_table():
    """Таблица границы из git — одна на процесс."""
    return _load(CORPUS_PATH)


def _load(path):
    if path not in _TABLES:
        _TABLES[path] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return _TABLES[path]


# ── Что писала платформа в проверенных формах ─────────────────────────────────────────────────
# Второй ярус границы: значение, которого корпус не держит, но которое платформа записала сама —
# копией палитры в пуле, формой, собранной в предприятии, или пересохранением. Это наблюдение, а не догадка, и отказ на
# нём был бы утверждением «платформа такого не пишет», которое её же форма опровергает. Формы кодека
# (`*.codec*.frm`) сюда не идут: их писали мы.
FIXTURES_PATH = DATA_DIR / "fixture_props.json"
FIXTURES_ROOT = pathlib.Path(__file__).resolve().parents[1] / "fixtures"


def fixture_forms(root=FIXTURES_ROOT):
    """Формы, которые записала платформа (исходные и пересохранённые)."""
    out = sorted((root / "pool").glob("*/*.frm")) + sorted((root / "experiments").glob("*/*.frm"))
    for form in sorted((root / "rounds").glob("*/*.frm")):
        stem = form.name
        if ".platform" in stem or ".resaved" in stem:
            out.append(form)
    return out


def fixture_summary(counted_by_form, root=FIXTURES_ROOT):
    """`[(путь формы, Counter collect)]` → `{якорь: {путь: [значения]}}` — значения, которые платформа записала в этом поле,
    по возрастанию.
    """
    out = {}
    for _form, counted in counted_by_form:
        for (anchor, path, _kind, text) in sorted(counted):
            out.setdefault(anchor, {}).setdefault(path, set()).add(text)
    return {anchor: {path: sorted(texts) for path, texts in sorted(paths.items())}
            for anchor, paths in sorted(out.items())}


def fixture_table():
    """Таблица второго яруса из git — одна на процесс."""
    return _load(FIXTURES_PATH)
