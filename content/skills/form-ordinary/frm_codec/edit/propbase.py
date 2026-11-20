"""Свойства: таблицы операций, отказы и границы, заданные корпусом и платформой.

Часть редактора. Все имена доступны через `frm_codec.edit`."""

import copy

from .. import schema, design as _design, props, json0, validate

from .names import (
    BTN_NAME,
    BTN_OWNER,
    CAPTION,
    COLUMNS,
    COLUMN_CONTROL,
    COLUMN_CONTROL_TYPE,
    COLUMN_DATA,
    COLUMN_HEAD_NODES,
    COLUMN_NAME,
    COLUMN_VALUE_TYPE,
    COORDS,
    CORPUS_STAMP,
    DEFAULT_CONTROL,
    ELEMENTS,
    EVENTS,
    FONT_KEYS,
    INDEX,
    MENU,
    MENU_MODE,
    NAME,
    NAME_BLOCK,
    NUMBER,
    ON_CORPUS,
    ON_CORPUS_NOTE,
    PAGES,
    PAGE_ITEMS,
    PAGE_NAME,
    TEXTBOX_NUMBER,
    TEXTBOX_PATTERN,
    UNSEEN_NOTE,
    _at,
    _run,
)
from .base import EditError, _on_corpus, _panel_pages, find_button, find_element, set_text
from .buttons import CORPUS_SHORTCUT_BLOCKS, SHORTCUT_FIELD, _named
from .elements import TYPE_LINK, _short, _slot_type_name
from .columns import _column, column_control
from .formroot import (
    FORM_PICTURE_SET,
    FORM_PICTURE_SET_WORDS,
    FORM_REFUSALS,
    FORM_WRITES,
    _form_has,
    _form_trail,
    _form_written,
)


ACTIONS_BLOCK = _slot_type_name("CommandBarActions")
CHOICE_LIST = _run("Content.ComboBox.u1", schema.Counted, "ValueList")
TEXTBOX_PROPS_NODE = "Content.TextBox.u2.u0"
TEXTBOX_COMMON_NODE = schema._COMMON_BLOCKS["Element.TextBox"]
# Оба узла общего блока поля ввода зависят от версии: у версии 15 свой узел.
TEXTBOX_COMMON_NODES = tuple(schema.variants(schema.TEXTBOX_COMMON_FORK))
TEXTBOX_VALUE_NODE = f"{schema.TEXTBOX_VALUE_BLOCK}.v4"
COORDS_NAMES = tuple(sorted({getattr(slot, "name", None)
                             for _addr, slot in schema.node_slots(schema.MAP["Coords"])} - {None}))

# Поля, для которых есть отдельная операция. Если бы то же поле можно было менять двумя способами, они
# расходились бы, поэтому отказ называет нужную операцию. У этих полей кроме значения есть что вести: порядок по
# коду, язык строки, строение записи, счётчики и ссылки списка.
PROPERTY_OPS = {
    **{key: ("set_font", "шрифт пишется от противного — видом записи, маской и значениями по "
                         "битам, и set_font ведёт всё это разом, зная, какие записи видели платформа "
                         "и корпус") for key in FONT_KEYS},
    EVENTS: ("set_event", "обработчик — запись в списке событий, и встаёт она на место по коду "
                          "события; set_event знает и пары «тип + событие», какие видели "
                          "корпус и платформа"),
    CAPTION: ("set_caption", "заголовок — многоязычная строка; set_caption переписывает текст, "
                             "сохраняя язык"),
    TYPE_LINK: ("set_type_link", "связь по типу — запись-ссылка на реквизит (путь данных), а не "
                                 "значение; set_type_link пишет её строением, проверенным платформой"),
    MENU: ("set_menu_mode", "блок меню кнопки заводит и убирает режим меню вместе с постоянным "
                            "GUID набора"),
    MENU_MODE: ("set_menu_mode", "режим меню — ФЛАГ СТРОЕНИЯ: при Use и UseExtra в теле записи "
                                 "стоит блок меню, и флаг без блока платформа отвергает "
                                 "целиком"),
    COLUMN_CONTROL: ("set_column_control", "вложенный элемент колонки — не значение, а ТИП "
                                           "элемента с его телом"),
    COLUMN_CONTROL_TYPE: ("set_column_control", "ЭлементУправления — GUID ТИПА вложенного "
                                                "элемента, и сменить его, не сменив тело, "
                                                "значит собрать колонку, которой платформа не "
                                                "пишет (validate отвергает уровнем 2)"),
    COLUMNS: ("add_column, remove_column", "колонки — список со счётчиком, номерами и шапками"),
    ACTIONS_BLOCK: ("add_button, remove_button, set_button_text, set_button_action, "
                    "set_tool_tip, set_description, set_button_picture, set_button_shortcut",
                    "кнопки панели и их действия — блок "
                    "действий со сквозными номерами, GUID и владельцами"),
    PAGES: ("add_page, move_page, remove_page", "страницы — список со счётчиком, направляющими и числом "
                                                "АктивизироватьПоУмолчанию на каждую"),
    CHOICE_LIST: ("set_property choice_list=[…]", "список выбора поля выбора — ФЛАГ СТРОЕНИЯ: счётчик его "
                       "решает, стоит ли блок; блок целиком собирает set_property с именем choice_list "
                       "и списком строк"),
    _design.VIEW: ("set_view", "вид поля ввода «как в 8.2» или «как в 8.3» — свойство ФОРМЫ: "
                               "стили 8.2 и 8.3 в одной форме не мешать, и set_view "
                               "ставит его всем полям разом, досчитывая u43 правилом платформы"),
}


def _property_refusal(found, anchor, bit=None):
    """Отказ для поля, которое `set_property` не пишет, со словами; `None` — поле писать можно.

    Проверки идут от отдельной операции к строению: тот, кто назвал шрифт, узнаёт про `set_font`, а не про то,
    что шрифт — блок с отрезком по маске.

    Для корня самой формы решает перечень `_form_refusal`: форма пишет только строки своей палитры, у которых
    есть адрес, а строение проверяется тем же кодом ниже (якорь `None` — проверки, не зависящие от якоря)."""
    if anchor == props.FORM_ANCHOR:
        return _form_refusal(found, bit)
    key, slot = found.key, found.slot
    if anchor in (props.BUTTON_ANCHOR, props.MENU_ANCHOR) and key in BUTTON_REFUSALS:
        return BUTTON_REFUSALS[key]
    own = ANCHOR_PROPERTY_OPS.get((anchor, SHORTCUT_FIELD if found.node == SHORTCUT_NODE
                                   else key))
    if own is not None:
        return own[1]
    if isinstance(slot, schema.N) and slot.type in ELEMENT_PICTURE_SETS and bit is None:
        return picture_set_words(slot.type, found.holder.get(found.key))
    if anchor == props.PAGE_ANCHOR and key == PAGE_NAME:
        return ("имя страницы — её адрес: по нему её находят операции (add_page donor=…, "
                "remove_page, page=…) и код модуля; переименования страницы у редактора нет")
    if anchor == props.PAGE_ANCHOR and key == CAPTION:
        return None             # у страницы set_caption нет: заголовок страницы пишет эта операция
    if key in PROPERTY_OPS:
        op, why = PROPERTY_OPS[key]
        if op == "—":
            return why
        return f"у поля {key!r} своя операция — {op}: {why}. Две дороги к одному полю разошлись бы"
    if anchor != props.COLUMN_ANCHOR and found.trail == (NAME_BLOCK, NAME):
        return ("имя элемента правит rename_element: по имени его находят все операции, и "
                "переименование обязано остаться одним ходом")
    if anchor == props.COLUMN_ANCHOR:
        if key == COLUMN_NAME:
            return ("имя колонки — её адрес: по нему её находят операции (column=…) и код "
                    "модуля; переименования колонки у редактора нет, правьте JSON по адресу")
        if key == COLUMN_DATA:
            return ("Данные колонки — связь с колонкой данных табличного поля; редактор ставит "
                    "их только новой колонке (add_column data=…), а у существующей правка Данных "
                    "меняет, что колонка показывает, — платформой это не проверялось")
        if key == COLUMN_VALUE_TYPE:
            return ("тип значения колонки ведёт set_column_control там, где его меняет платформа "
                    "(флажок таблицы значений — Булево, поле выбора — пустой); отдельно от вида "
                    "элемента его правка разводит колонку с её же вложенным полем. У колонки ТАБЛИЦЫ ЗНАЧЕНИЙ тип ставит set_column_type (и ключ type у add_columns): "
                    "тип колонки и описатель её поля ввода пишутся вместе")
    if anchor == NESTED_TEXTBOX and (key == TEXTBOX_PATTERN
                                     or (found.node, key) in NESTED_DERIVED):
        return (f"{key!r} вложенного поля ввода колонки выводит платформа из типа КОЛОНКИ, и у "
                "колонки с данными из табличной части самостоятельным свойством он не является: "
                "при копировании формы разрядность вложенного поля переписывается по типу колонки "
                "(7 → 5 при N(5,0)); в палитре вложенного поля у колонки с данными из табличной "
                "части строк «Тип значения» и «Длина» нет вовсе, а поставленная разрядность на ввод "
                "не влияет — ограничивает реквизит; описатель вложенного поля равен "
                "описателю колонки. У колонки таблицы значений палитра эти строки показывает, и "
                "что они правят — тип колонки или свой, — не проверялось; операция не пишет ни то ни "
                "другое. Тип меняют у колонки: set_column_control там, где его меняет платформа. Колонке таблицы значений тип ставит set_column_type: тип колонки и описатель её поля ввода вместе, как у колонок корпуса")
    if key == TEXTBOX_PATTERN:
        return ("тип значения поля ввода — описатель, и отдельной операции у него нет: у поля "
                "формы он следует за данными (реквизит — add_attribute, привязка — bind), у "
                "вложенного элемента его ставит set_column_control. Квалификаторы — Длина, "
                "Точность, Неотрицательный, СоставДаты — ставит set_property их именами "
                f"({', '.join(TEXTBOX_NUMBER)}, {DATE_FRACTIONS}), и описатель вместе с ними")
    if found.trail == (INDEX,):
        return ("индекс элемента выдаёт счётчик формы (last_index), и на него ссылаются "
                "привязки данных, заголовок формы и списки зависимых соседей — правка числом "
                "разорвала бы их все")
    if found.trail == ("type",):
        return "тип элемента не меняют: у каждого типа своё строение содержимого"
    if found.trail == (COORDS,):
        return ("координаты и привязки — блок координат, а не свойство: его ведут операции "
                "размещения (add_element box=…), вместе со встречными записями привязок и "
                "порядком обхода по странице")
    if found.trail == (ELEMENTS,):
        return "вложенные элементы — список панели или формы: add_element и remove_element"
    if key == DEFAULT_CONTROL:
        return ("default_control — по числу на каждую страницу РОДИТЕЛЯ: у панели этот список "
                "про элементы внутри неё, а АктивизироватьПоУмолчанию самой панели лежит в списке "
                "раскладки её панели или формы; длину держат страницы, и операции у списка нет "
                "— правьте JSON панели или формы, validate сверит длину")
    if isinstance(slot, schema.F) and slot.kind == schema.BITS and bit is None:
        return (f"{key!r} — битовое слово, и ставят его ПО БИТАМ: {key}/<бит> "
                f"({', '.join(slot.bits)}); остаток {schema.BITS_REST} — биты, которых журнал не "
                "назвал, и по имени их не правят")
    if isinstance(slot, (schema.R, schema.Counted, schema.CountedPairs, schema.Flagged,
                         schema.Masked, schema.Along, schema.Gated)):
        return (f"{key!r} — список или отрезок раскладки, а не значение: его длину держат "
                "счётчик и соседи, и правка целиком — это правка строения; своей операции у "
                "него нет, правьте JSON по адресу, validate сверит строение")
    if props.is_container(slot):
        return (f"{key!r} — блок, содержащий свойства, а не свойство: строки палитры у него нет, есть "
                "его поля — называйте их")
    if bit is not None:
        return None
    fork = schema.FORKS.get(found.declared)
    if fork is not None and fork.key == key:
        return (f"{key!r} — ФЛАГ СТРОЕНИЯ: значение называет вариант узла {found.declared} "
                f"(сейчас {found.node}), и при другом значении у узла другие позиции. Меняют его "
                "вместе с узлом, а не числом")
    gates = {segment.by for segment in (schema.MAP[found.node].runs.segments
                                        if schema.MAP[found.node].runs else ())
             if isinstance(segment, schema.Gated)}
    if key in gates:
        return (f"{key!r} — ФЛАГ СТРОЕНИЯ: при одних его значениях за ним стоит блок, при других "
                "нет (флаг без блока платформа отвергает целиком)")
    if (found.node, key) in props.STRUCTURE_FLAGS:
        return (f"{key!r} — ФЛАГ СТРОЕНИЯ, которого карта флагом не объявила: "
                f"{STRUCTURE_FLAG_WORDS[(found.node, key)]}. Число здесь меняет строение блока — "
                "ставьте блок картинки целиком (его имя), и граница сверит строение вместе с "
                "этим полем")
    if isinstance(slot, schema.F) and slot.const is not None:
        return (f"{key!r} постоянно — {slot.const!r} у всех наблюдений корпуса; "
                "другое значение описывало бы узел, которого платформа не пишет")
    if key == "count" and schema.MAP[found.node].repeat is not None:
        return (f"{key!r} — счётчик: он равен длине списка {schema.MAP[found.node].repeat.name}, и "
                "validate сверяет их уровнем 2; меняют список, а не счётчик")
    if key in ("version", "record_version"):
        return (f"{key!r} — версия записи: за ней следует ДЛИНА записи, и другая версия — это "
                "другое строение узла, а не значение")
    derived = DERIVED.get((found.node, key))
    if derived is not None:
        return derived
    if schema.is_placeholder(slot):
        return f"{key!r} — безымянная позиция: смысла её карта не знает, и по имени её не правят"
    return None


# Вложенное поле ввода колонки: описатель типа и квалификаторы в свойствах поля платформа выводит из типа
# колонки. При копировании формы она переписывает разрядность вложенного поля по типу колонки. У колонки с
# данными из табличной части в палитре вложенного поля нет строк «Тип значения» и «Длина», а разрядность,
# поставленная редактором, на ввод не влияет. У большинства полей корпуса описатель вложенного поля равен
# описателю колонки. У колонки таблицы значений эти две строки в палитре есть, но описатель там тоже равен
# описателю колонки; что именно меняет строка — тип колонки или собственный тип поля, не проверялось, поэтому
# операция не пишет ни то ни другое.
NESTED_TEXTBOX = props.NESTED_ANCHOR + "TextBox"
NESTED_DERIVED = {(TEXTBOX_PROPS_NODE, key) for key in TEXTBOX_NUMBER} | {
    _named(TEXTBOX_PROPS_NODE, "date_fractions")}
NESTED_PATTERN_SAME = (28171, 28337)


# Кнопка командной панели: поля её узла, которые `set_property` не пишет. У каждого из них своя операция или
# своё строение. Подсказка, пояснение, картинка и сочетание клавиш кнопки хранятся в записи её действия по
# битам, и обход узла кнопки до них не доходит.
BUTTON_REFUSALS = {
    BTN_NAME: ("имя кнопки — её адрес: по нему её находят операции (element=панель, button=имя) и "
               "код модуля; переименования кнопки у редактора нет"),
    _at("Element.CommandBarButton", 4, "LocalizedString"):
        "у поля 'text' своя операция — set_button_text: текст кнопки — многоязычная строка, и "
        "операция сохраняет её язык. Две дороги к одному полю разошлись бы",
    NUMBER: ("сквозной номер кнопки выдаёт add_button вместе со счётчиком last_number головы "
             "блока; правка числом дала бы повтор номера (у корпуса их нет ни одного)"),
    BTN_OWNER: ("владелец кнопки — GUID головы её блока действий: его ставят операции кнопок, а "
                "у меню чинит set_menu_mode"),
    _at("Element.CommandBarButton", 9): (
        "ТипКнопки — вид кнопки: у подменю запись ДЕЙСТВИЯ — ссылка на набор кнопок, и копии "
        "журнала вместе с видом гасили позицию 13; сменить вид, не сменив действие, значит "
        "собрать кнопку, которой платформа не пишет, а подменю редактор не заводит"),
    _at("Element.CommandBarButton", 0): (
        "метка записи кнопки — за ней следует ДЛИНА записи (8 — шестнадцать позиций, 7 — "
        "тринадцать), и другая метка — это другое строение, а не значение"),
}


# ── Сочетание кнопки формы и набор картинок элемента по имени ──

# Набор картинок элемента (надпись, поле картинки, панель — `PictureSet.*`) не является строкой палитры, а
# содержит несколько строк, как и у формы. Картинка и РазмерКартинки пишутся по своим именам, а рядом лежат
# версия записи и безымянные позиции (вторая и третья картинки, хвост). Граница блока проверяет только строение:
# набор, собранный целиком, согласован сам с собой, и запись целиком пропустила бы набор другой версии и чужие
# значения безымянных позиций. Набор формы отказывает своими словами (`FORM_PICTURE_SET_WORDS`), остальные —
# здесь.
ELEMENT_PICTURE_SETS = frozenset(name for name in schema.MAP
                                 if name.startswith("PictureSet.") and name != "PictureSet.Form")
# Наибольшая длина набора картинок элемента — девять позиций. У надписи версии 3 — три, версии 4 — пять, версии
# 7 — восемь, версии 8 — девять; у панели так же; у поля картинки версии 3 бывает восемь и девять позиций.
# Длиннее девяти наборов нет.
PICTURE_SET_LENGTH = 9
CORPUS_ELEMENT_PICTURE_SETS = {"PictureSet.Label": 33374, "PictureSet.Panel": 9143,
                               "PictureSet.PictureBox": 3269}

SHORTCUT_NODE = "Shortcut"
SHORTCUT_PARTS = tuple(slot.name for index, slot in sorted(schema.MAP[SHORTCUT_NODE].fields.items())
                       if slot.const is None)

FORM_BUTTON_SHORTCUT_WORDS = (
    "сочетание клавиш кнопки ФОРМЫ пишет set_button_shortcut с element=<кнопка> (key=<клавиша>, "
    "modifiers=[…], либо remove=true): блок тот же, что у записи действия кнопки панели, — три "
    "позиции с меткой 0 — и операция ведёт "
    "имена клавиш и модификаторов, границу по клавише и по модификаторам порознь и повтор "
    "сочетания в форме; здесь блок писался бы сырым числом без всего этого. Две дороги к одному "
    "полю разошлись бы")
# Поле, для которого у одного якоря есть отдельная операция (у остальных якорей то же имя пишет `set_property`):
# `(якорь, поле) → (операция, слова отказа)`. Подполя блока (`shortcut/key`) отказывают теми же словами.
ANCHOR_PROPERTY_OPS = {("Button", SHORTCUT_FIELD): ("set_button_shortcut",
                                                    FORM_BUTTON_SHORTCUT_WORDS)}


def picture_set_words(type_name, block=None):
    """Отказ для набора картинок элемента целиком; названы строки, которые пишутся по своим именам.

    Производное поле и безымянные позиции определяются по самому блоку `block`: у набора версии 3 три позиции
    (версия, РазмерКартинки, Картинка), и ни `border_state`, ни безымянных позиций у него нет. Если блока нет,
    позиции определяются по карте до наибольшей длины набора (`PICTURE_SET_LENGTH`)."""
    node = schema.MAP[type_name]
    length = len(block) if isinstance(block, dict) else PICTURE_SET_LENGTH
    present = {slot.name for index, slot in node.fields.items() if index < length}
    mirror = next((slot for slot in node.fields.values()
                   if getattr(slot, "mirror_of", None)), None)
    rows = ["Картинка (pictures/picture)"]
    if "picture_size" in present:
        rows.append("РазмерКартинки (pictures/picture_size" + (
            f" — зеркало строки у элемента, операция пишет оба адреса" if mirror else "") + ")")
    near = ["версия записи (version: за ней следует длина набора, и метка картинки ходит с ней "
            "парой)"]
    if "border_state" in present:
        near.append("производное border_state (его досчитывает платформа)")
    unnamed = [index for index in range(3, length) if index not in node.fields]
    if unnamed:
        near.append(f"безымянные позиции (u{', u'.join(str(i) for i in unnamed)} — вторая и "
                    "третья картинки и хвост), смысла которых карта не знает")
    listed = near[0] if len(near) == 1 else ", ".join(near[:-1]) + " и " + near[-1]
    version = block.get("version") if isinstance(block, dict) else None
    alone = "" if unnamed else (f"; безымянных позиций у этого набора нет — позиций в нём "
                                f"{length}" + (f" (версия {version})" if version is not None
                                               else ""))
    return ("набор картинок целиком по имени не пишется: это не строка палитры, а контейнер её "
            f"строк — {' и '.join(rows)} пишутся своими именами, — а рядом с ними {listed}"
            f"{alone}. Записью целиком прошёл бы и набор чужой версии, и чужие значения безымянных "
            "позиций: граница блока сверяет только строение (у формы тот же отказ)")


def _unnamed_position(root, found_all, name, whose):
    """Отказ «безымянная позиция» для корня элемента, колонки, страницы или кнопки. Он выдаётся, когда последний
    шаг пути — `u<индекс>`, такая позиция в блоке есть, а карта её не называет; иначе возвращается `None`.

    Позиция в наборе существует, у неё только нет имени; для формы такой же отказ даёт `_form_missing`. Позицию,
    которую карта называет, а JSON именует `u<индекс>` (имя снято при несовпадении вида), этот отказ не
    затрагивает: её ищут по имени."""
    parts = [part for part in str(name).split("/") if part]
    last = parts[-1] if parts else ""
    if len(parts) < 2 or last[:1] != "u" or not last[1:].isdigit():
        return None
    if not _form_has(root, found_all, parts):
        return None
    head, sets = parts[:-1], False
    for found in found_all:
        value = found.holder.get(found.key)
        if not (isinstance(value, dict) and last in value and isinstance(found.slot, schema.N)
                and _form_trail(found).split("/")[-len(head):] == head):
            continue
        node = schema.MAP.get(schema.pick_doc(found.slot.type, value) or found.slot.type)
        slot = node.fields.get(int(last[1:])) if node is not None and node.runs is None else None
        if slot is not None and not schema.is_placeholder(slot):
            return None
        sets = sets or found.slot.type in ELEMENT_PICTURE_SETS
    return (f"{name!r} у {whose} — безымянная позиция: смысла её карта не знает, и по имени её не "
            "правят" + (" (как и набор картинок, в котором она лежит, целиком)" if sets else "")
            + " — правьте JSON по адресу, validate сверит строение")


# Картинки с источником 3 в корпусе (`CORPUS_STAMP`): у всех тело лежит на позиции 7, у картинок с другим
# источником тела нет (флаг строения вне карты, `props.STRUCTURE_FLAGS`). У кнопки формы таких картинок 2 327, у
# поля картинки 525, у надписи 351.
CORPUS_PICTURE_BODIES = 3441
# Всего картинок в корпусе. У каждой по длине записи однозначно определяется метка: у каждого поля каждого якоря
# при одном источнике одной длине соответствует одна метка.
CORPUS_PICTURES = 276241
# Слова отказа для флагов строения вне карты, по одному на каждый (`props.STRUCTURE_FLAGS`).
STRUCTURE_FLAG_WORDS = {
    ("Picture", "source"): (
        "у блока картинки источник 3 — картинка, вложенная в форму, и позиция 7 тогда несёт её "
        "ТЕЛО (`#base64`), а при прочих — число; тело есть у каждой картинки с источником 3 "
        "и ни у одной с другим"),
    ("Picture", "mark"): (
        "за меткой картинки следует ДЛИНА её записи — метки 3 и 7 стоят у записи без хвостовой "
        "позиции, 4 и 8 — у записи с ней, 0 — у пустой картинки поля картинки; длина называет метку однозначно, и метка 4 при длине метки "
        "3 — запись, которой платформа не пишет. Метка ещё и ходит парой с версией "
        "записи-владельца (у кнопки версии 10 — 3, у 13 и 14 — 4)"),
}
assert set(STRUCTURE_FLAG_WORDS) == props.STRUCTURE_FLAGS, "у флага строения нет слов отказа"


# Производные поля. Первое операция ставит вместе с основным (правило и числа — у согласованных полей ниже,
# `_cowrites`). Два других платформа досчитывает при сохранении, поэтому ставить их вручную бессмысленно. Если
# назвать любое из них, будет отказ со ссылкой на поле, от которого оно зависит.
DERIVED = {
    _named(TEXTBOX_PROPS_NODE, "multi_line_code"):
        "multi_line_code — производное от multi_line (2 при истине, 0 при лжи): ставьте "
        "multi_line, и операция поставит его сама вместе с зеркалом",
    **{_named(head, "width_computed"):
       "width_computed — состояние КОНСТРУКТОРА: платформа досчитывает его сама (−1 → 15 при "
       "нетронутой колонке) вместе с шириной, а единицы не проверялись — ставьте width, это "
       "число платформа перепишет"
       for head in COLUMN_HEAD_NODES},
    _named("PictureSet.Label", "border_state"):
        "border_state — производное состояние, которое платформа считает сама: поставленные 0 и "
        "1 пересохранение заменяет своим; Рамка и ЦветаРамки двигают его следом (заметка поля "
        "в карте)",
}
# Когда правится поле, от которого зависит производное, отчёт сообщает, что производное не изменено, и объясняет
# почему. Иначе расхождение с формой платформы можно принять за недосмотр операции.
DERIVED_BY = {
    **{_named(head, "width"): _named(head, "width_computed") for head in COLUMN_HEAD_NODES},
    _named("Content.Label.u1.u0", "border"): _named("PictureSet.Label", "border_state"),
    _named("Content.Label.u1.u0", "border_color"): _named("PictureSet.Label", "border_state"),
}
# Безымянные позиции, которые платформа меняет вслед за полем: какие значения она туда пишет, не проверялось, а имени у
# позиции нет. Операция эти позиции не трогает и сообщает об этом. Ключ — поле, значение — позиция относительно
# содержимого элемента.
SIDE_POSITIONS = {
    _named("Content.CheckBox.u1.u0.u0", "border"): "u1/u0/u8",
    _named("Content.CheckBox.u1.u0.u0", "border_color"): "u1/u0/u8",
    _named("Content.ComboBox.u1.u0", "border_color"): "u1/L1+17",
}
# Те же позиции у переключателя: платформа ставит ей 0 при любой рамке, кроме «Без рамки» и «Одинарная», и при явном цвете рамки,
# иначе — 1. Операция позицию не пишет и называет, как у флажка.
SIDE_POSITIONS_ADDED = {
    _named("Content.RadioButton.u2.u0.u0", "border"): "u2/u0/u8",
    _named("Content.RadioButton.u2.u0.u0", "border_color"): "u2/u0/u8",
}
SIDE_WORDS_ADDED = {
    key: "позиция равна 1 при рамке «Без рамки» или «Одинарная» с цветом «Авто» и 0 при любой другой рамке или явном цвете рамки"
    for key in SIDE_POSITIONS_ADDED
}
# Что известно о позиции сверх «копия её сдвинула»: это спутник позиции 16 у поля выбора. У поля ввода такой же
# спутник (`u43`) операция пишет по правилу платформы, а у поля выбора его вид не проверялся, и правило на него
# не переносится.
SIDE_WORDS = {
    _named("Content.ComboBox.u1.u0", "border_color"):
        "это спутник позиции 16 (`L1+17`, пара жёсткая у всех полей выбора корпуса), и "
        "копия дала ему 1 при явном цвете рамки (2 → 1); у поля ввода такой же спутник — u43 — "
        "платформа досчитывает, и операция пишет его правилом, а у поля выбора вид платформой не "
        "проверялся, RGB-рамок в корпусе нет, и подтверждение одно — наблюдение на одной форме",
}


def _property_root(doc, element, column, nested, page=None, button=None):
    """`(корень, тип корня, якорь, стоп-ключи, адрес корня от якоря, чьими словами)`.

    Корней пять, и у каждого свой якорь границы: элемент (`TextBox`), колонка (`TableBoxColumn`), вложенный
    элемент колонки (`ColumnControl.TextBox`), страница панели (`PanelPage`) и кнопка командной панели
    (`CommandBarButton`). Адрес корня нужен для зеркал: карта считает зеркала от элемента, а у вложенного
    элемента корнем служит его содержимое — позиция 2 элемента."""
    if sum(value is not None and value is not False
           for value in (column, page, button)) > 1:
        raise EditError("страница, колонка и кнопка — разные адреса: page — у панели, column — у "
                        "табличного поля, button — у командной панели; назовите один")
    if button is not None:
        _block, _set, node, _action = find_button(doc, element, button)
        # У пунктов меню кнопки формы свой якорь границы: узел тот же, что у кнопки панели, но корпус видел
        # пункты меню, а не кнопки панелей.
        try:
            owner = find_element(doc, element).element.get("type")
        except EditError:
            owner = None
        if owner == "Button":
            return (node, "Element.CommandBarButton", props.MENU_ANCHOR, (), (),
                    f"пункта {button!r} меню кнопки {element!r}")
        return (node, "Element.CommandBarButton", props.BUTTON_ANCHOR, (), (),
                f"кнопки {button!r} панели {element!r}")
    place = find_element(doc, element)
    kind = place.element.get("type")
    if page is not None:
        if nested:
            raise EditError("страница и колонка — разные адреса: page — у панели, column — у "
                            "табличного поля; назовите один")
        _place, block = _panel_pages(doc, element)
        if isinstance(page, int) and not isinstance(page, bool):
            # Номер страницы с нуля — то же, что имя: у страниц, созданных платформой, имена «Страница1»…, и угадывать их не нужно.
            items = block[PAGES][PAGE_ITEMS]
            if not 0 <= page < len(items):
                known = ", ".join(f"{i}: {item.get(PAGE_NAME)!r}" for i, item in enumerate(items))
                raise EditError(f"страницы с номером {page} у {element!r} нет (счёт с нуля); есть {known}")
            return (items[page], "Element.PanelPage", props.PAGE_ANCHOR, (), (),
                    f"страницы {page} ({items[page].get(PAGE_NAME)!r}) панели {element!r}")
        found = [item for item in block[PAGES][PAGE_ITEMS] if item.get(PAGE_NAME) == page]
        if len(found) != 1:
            known = ", ".join(str(item.get(PAGE_NAME)) for item in block[PAGES][PAGE_ITEMS])
            raise EditError(f"страниц {page!r} у {element!r} — {len(found)}; есть: {known}")
        return (found[0], "Element.PanelPage", props.PAGE_ANCHOR, (), (),
                f"страницы {page!r} панели {element!r}")
    if nested:
        if column is None:
            raise EditError("nested=true — это вложенный элемент КОЛОНКИ: назовите column")
        _head, nested_kind, content = column_control(doc, element, column)
        return (content, "ColumnControl", props.NESTED_ANCHOR + nested_kind, (), (2,),
                f"вложенного элемента ({nested_kind}) колонки {column!r} поля {element!r}")
    if column is not None:
        item = _column(doc, element, column)
        return (item, props.COLUMN_TYPE, props.COLUMN_ANCHOR, props.COLUMN_STOP, (),
                f"колонки {column!r} поля {element!r}")
    return (place.element, "Element", kind, props.ELEMENT_STOP, (),
            f"элемента {element!r} ({kind})")


def _addr_text(base, found):
    return "/".join(str(index) for index in base + found.addr)


def _property_matches(found_all, name, whose):
    """`[(поле, бит или None)]` по имени: просто имя (`mask`), путь (`u2/u0/mask`) или бит
    (`flags/default_control`; если бит один на весь корень — просто `default_control`)."""
    parts = [part for part in str(name).split("/") if part]
    if not parts:
        raise EditError("name — имя поля карты (как в FORMAT.md) или путь к нему, а пришло пусто")
    out = []
    for found in found_all:
        trail = found.trail
        if trail[-len(parts):] == tuple(parts):
            out.append((found, None))
            continue
        bits = getattr(found.slot, "bits", None) if isinstance(found.slot, schema.F) else None
        if bits and parts[-1] in bits and (len(parts) == 1
                                           or trail[-(len(parts) - 1):] == tuple(parts[:-1])):
            out.append((found, parts[-1]))
    return out


def _mirror_group(found_all, target, base):
    """Основное поле и его зеркала: `(основное, [зеркала])`.

    Зеркало определяется по `mirror_of` — адресу основного поля от якоря. Если назвали само зеркало, основным
    становится поле по этому адресу."""
    primary = target
    mirror_of = getattr(target.slot, "mirror_of", None)
    if mirror_of:
        primary = next((found for found in found_all if _addr_text(base, found) == mirror_of),
                       target)
    address = _addr_text(base, primary)
    mirrors = [found for found in found_all if getattr(found.slot, "mirror_of", None) == address
               and found is not primary]
    return primary, mirrors


def _block_mirror(found_all, target, base):
    """Подполе блока-зеркала: `(подполе основного блока, [то же подполе во всех местах блока], длина пути блока)`.

    Зеркало карта называет у блока (`mirror_of` у `back_color` панели: основное `content/u1/u0/back_color`,
    зеркало `content/u1/back_color`), у подполей своего `mirror_of` нет. Блок целиком операция записывает в оба
    места, и подполе должна записывать так же, иначе `validate` сообщит, что правка записана только в одно из
    двух мест. Относительный путь подполя в обоих местах одинаков. Для поля вне блока с зеркалом возвращается
    `(target, [], 0)`."""
    for depth in range(len(target.trail) - 1, 0, -1):
        block = next((found for found in found_all if found.trail == target.trail[:depth]
                      and isinstance(found.slot, schema.N)), None)
        if block is None:
            continue
        primary, mirrors = _mirror_group(found_all, block, base)
        if not mirrors:
            continue
        rest = target.trail[depth:]
        places = []
        for other in [primary] + mirrors:
            twin = next((found for found in found_all if found.trail == other.trail + rest), None)
            if twin is None:
                raise EditError(f"{'/'.join(target.trail)}: блок {'/'.join(block.trail)} лежит в "
                                f"файле дважды, а у места {'/'.join(other.trail)} подполя "
                                f"{'/'.join(rest)} нет — места разошлись строением, и править "
                                "подполе в одном из них значило бы развести их ещё дальше; "
                                "ставьте блок целиком")
            places.append(twin)
        return places[0], places, depth
    return target, [], 0


def _find_one(found_all, node, name):
    return next((found for found in found_all if found.node == node and found.key == name), None)


DATE_FRACTIONS = _named(TEXTBOX_PROPS_NODE, "date_fractions")[1]


# ── Граница: что видел корпус и что проверила платформа ──

def _property_bounds(anchor, path, slot_kind, text, value, what, unverified):
    """Хвост отчёта по трём источникам границы — корпус, формы, проверенные платформой, или отсутствие данных,
    тогда отказ.

    Корпус хранит значения перечнем, а если их больше `props.VALUES_KEPT` — диапазоном (целое, дробное) или
    видом (строка пустая или нет, любой GUID). Фраза «такого RGB в корпусе не было» ничего не утверждает, а
    «такая ширина колонки больше любой в корпусе» утверждает. Если значения нет ни в корпусе, ни среди
    проверенных платформой, операция отказывает; отказ снимает `unverified=True`."""
    row = props.corpus_table().get(anchor, {}).get(path)
    seen = dict(row["values"]) if row else {}
    platform = props.fixture_table().get(anchor, {}).get(path, {})
    # Вид поля может зависеть от значения (выбранное значение переключателя — целое, булево или строка,
    # `props.summary`), поэтому граница определяет вид по значению, а не по строке.
    kinds = props.row_kinds(row)
    tail = ""
    if text in seen:
        tail = _on_corpus("set_property/value", what, seen[text],
                          counted="блоков этого строения" if slot_kind == "node" else "таких")
    elif row and schema.STR in kinds and isinstance(value, str):
        # Строка — это содержимое (маска, подсказка, формат), а не строение, поэтому граница для неё
        # определяется видом: пустая или нет. Фраза «такой маски в корпусе нет» ничего не утверждает о
        # платформе, а «у этого поля масок не бывает» утверждает.
        empty = row["empty"] if "empty" in row else seen.get('""', 0)
        count = empty if value == "" else row.get("strings", row["n"]) - empty
        if count:
            tail = (f"; {what}: {ON_CORPUS_NOTE} — {'пустая' if value == '' else 'непустая'} "
                    "строка такого вида встречается в образцах форм; "
                    + ON_CORPUS["set_property/value"])
    elif row and row.get("open"):
        number = props._number(text)
        if kinds & props.NUMBER_KINDS and number is not None and "range" in row \
                and row["range"][0] <= number <= row["range"][1]:
            tail = (f"; {what}: {ON_CORPUS_NOTE} — внутри диапазона значений образцов форм "
                    f"{row['range'][0]}…{row['range'][1]}; "
                    + ON_CORPUS["set_property/value"])
        elif schema.GUID in kinds:
            tail = (f"; {what}: {ON_CORPUS_NOTE} — у поля в образцах форм много разных GUID, "
                    "и ни один не повторяется настолько, чтобы считаться допустимым значением; "
                    + ON_CORPUS["set_property/value"])
    if not tail and text in platform:
        tail = (f"; {what}: в образцах форм такого нет, а платформа это значение писала сама; "
                + ON_CORPUS["set_property/value"])
    if tail:
        return tail
    if not unverified:
        known = ", ".join(str(t) for t, _n in (row or {}).get("values", [])[:8]) or "—"
        extent = f"; диапазон {row['range'][0]}…{row['range'][1]}" if row and "range" in row else ""
        raise EditError(
            f"{what} в образцах форм нет, и платформа его не писала: у этого поля {anchor} встречаются {known}{extent}. Такую "
            "форму не подтверждает ни платформа, ни корпус. Позвать всё же можно — "
            "unverified=True, — и тогда результат проверяете вы")
    return _on_corpus("set_property/value", what, None)


def _block_bounds(anchor, trail, slot, new, outer, shown, unverified):
    """Граница блока-значения по подполям: хвост отчёта либо отказ.

    Строение блока (`props.shape`) целые числа не различает: у цвета вид, метка и код — одинаково `int`. Поэтому
    блок с видом, которого нет в корпусе, прошёл бы по строению, а то же значение по имени подполя было бы
    отказом. Правило одно при любом способе записи: каждое скалярное подполе проверяется по своей строке таблицы
    — той же, что при записи подполя по имени (`_property_bounds`; для полей, которые проверяются в паре,
    дополнительно `_pair_bounds`: метка картинки — вместе с версией записи, код цвета — вместе с видом цвета из
    того же блока, код ссылки картинки — вместе с источником). Строение проверяется для списков и устройства
    блока. Постоянное подполе с другим значением — отказ теми же словами, что и при записи по имени;
    `unverified` его не снимает. В хвост попадает только то, что шире корпуса: значение, которое записывала
    только платформа, или невиданное значение с `unverified`."""
    tails = []
    inner = list(props.fields(new, slot.type, trail, stop=props.NOT_COUNTED))
    by_trail = {found.trail: found for found in inner}
    for sub in inner:
        if sub.key in props.NOT_COUNTED or not isinstance(sub.slot, schema.F):
            continue
        value = sub.holder.get(sub.key)
        label = "/".join((shown,) + sub.trail[len(trail):])
        if sub.slot.const is not None and value != sub.slot.const:
            raise EditError(f"{label} = {_short(value)}: {_property_refusal(sub, anchor)}")
        if sub.slot.kind == schema.BITS and isinstance(value, dict):
            items = [(bit, "bit", json0.dumps_line(value[bit], bools=True), value[bit])
                     for bit in sub.slot.bits if bit in value]
        else:
            items = [(None, sub.slot.kind, props.value_text(sub.slot, value), value)]
        for bit, kind, text, item in items:
            path = "/".join(sub.trail) + (f"/{bit}" if bit else "")
            what = f"{label}{'/' + bit if bit else ''} = {_short(item)}"
            tail = _property_bounds(anchor, path, kind, text, item, what, unverified)
            if ON_CORPUS_NOTE not in tail:
                tails.append(tail)
        partner = props.partner_of((sub.node, sub.key),
                                   outer + props.holders(by_trail, sub.trail, len(trail)))
        if partner is not None:
            tails.append(_pair_bounds(anchor, "/".join(sub.trail),
                                      props.value_text(sub.slot, value),
                                      f"{label} = {_short(value)}", partner, unverified,
                                      (sub.node, sub.key)))
    return "".join(tails)


# Какие поля проверяются в паре (`props.PAIRED`): словами отказа и отчёта объясняется, с чем пара и почему.
PAIR_WORDS = {
    props.VERSION: ("с версией своей записи", "у записей этой версии"),
    "color_kind": ("с видом цвета: код значит разное у разных видов — RGB при 0, номер веб-цвета "
                   "при 2, элемент стиля при 3, при 4 (авто) почти всегда 0", "при этом виде"),
    "source": ("с источником картинки: код стандартной картинки платформы бывает только у "
               "источника 1 без GUID, у прочих источников код — 0", "при этом источнике"),
}


def _pair_words(field):
    spec = props.PAIRED[field]
    return PAIR_WORDS[spec if spec == props.VERSION else spec[1]]


def _pair_bounds(anchor, path, text, what, partner, unverified, field, said=False):
    """Граница для поля, которое проверяется в паре с другим полем (`props.PAIRED`).

    Одиночная граница смотрит на значение отдельно и пропускает сочетание, которого нет в корпусе: метку 3 у
    кнопки версии 14 (метки 3 и 4 порознь есть в корпусе) или цвет вида 3 с кодом 0 у поля ввода. Строка пары
    (`путь@ключ=значение`) считается тем же обходом, что и одиночная (`props.collect`). `partner` равен `None`,
    если у поля нет партнёра (версию записи карта не называет): тогда граница одиночная. `said` — нужен ли
    хвост, когда значение есть в корпусе (поле названо по имени); иначе хвост не печатается. `field` — `(узел,
    ключ)` поля, по нему берутся слова о паре."""
    if partner is None:
        return ""
    pair = props.paired_path(path, partner)
    row = props.corpus_table().get(anchor, {}).get(pair)
    seen = dict(row["values"]) if row else {}
    where = f"{partner[0]} = {partner[1]}"
    with_what, among = _pair_words(field)
    if text in seen:
        return f"; такая пара ({where}) встречается в образцах форм" if said else ""
    # Если разных значений в паре больше `props.VALUES_KEPT` (например, RGB при виде 0 у надписи), граница, как
    # и у одиночной строки, задаётся диапазоном: «такого RGB в паре нет» ничего не утверждает.
    number = props._number(text)
    if row and row.get("open") and "range" in row and number is not None \
            and row["range"][0] <= number <= row["range"][1]:
        return (f"; в паре ({where}) — внутри диапазона значений образцов форм {row['range'][0]}…"
                f"{row['range'][1]}" if said else "")
    platform = props.fixture_table().get(anchor, {}).get(pair, {})
    if text in platform:
        return (f"; {what} при {where}: в образцах форм такой пары нет, а платформа её писала сама")
    if not unverified:
        known = ", ".join(str(t) for t, _n in (row or {}).get("values", [])[:12]) or "—"
        extent = f"; диапазон {row['range'][0]}…{row['range'][1]}" if row and "range" in row else ""
        raise EditError(
            f"{what} при {where} в образцах форм нет: поле ходит ПАРОЙ "
            f"{with_what}, и {among} у {anchor} встречаются {known}{extent}. Порознь значения "
            "в образцах есть, а вместе — нет, и такую форму не подтверждает ни платформа, ни образцы форм. "
            "Позвать всё же можно — unverified=True")
    return f"; {what} при {where}: {UNSEEN_NOTE}"


def _partner_bounds(anchor, found_all, target, new, unverified):
    """Поле, которое само является партнёром в паре (вид цвета): пара проверяется с его новым значением.

    Смена вида цвета по имени меняет смысл соседнего кода, хотя сам код остаётся прежним. Вид 3 с кодом 0 у
    `text_color` поля ввода в корпусе не встречается, поэтому блок `{вид 3, код 0}` операция отвергает. Оба
    способа записи одного сочетания отвечают одинаково. Зависимое поле ищется под держателем партнёра: код цвета
    лежит прямо в блоке своего вида (`Color`/`Border` → `value/code`), вложенных цветов карта не знает."""
    wanted = props.dependents((target.node, target.key))
    head = target.trail[:-1]
    tails = []
    for found in found_all if wanted else ():
        field = (found.node, found.key)
        if field not in wanted or found.trail[:len(head)] != head:
            continue
        value = found.holder.get(found.key)
        label = "/".join(found.trail[max(len(head) - 1, 0):])
        tails.append(_pair_bounds(anchor, "/".join(found.trail),
                                  props.value_text(found.slot, value), f"{label} = {_short(value)}",
                                  (target.key, new), unverified, field))
    return "".join(tails)


# Картинки колонки — заголовок, строки, подвал: у головы колонки их три, и их метки одинаковы у всех колонок
# корпуса (`CORPUS_COLUMN_PICTURE_MARKS`). Метка — флаг строения картинки (за ней следует длина записи), и в
# одной колонке платформа пишет все три картинки одной версией: при первом числе головы 16 встречаются и 3, и 4,
# но не вперемешку.
COLUMN_PICTURES = tuple(_named(schema.COLUMN_HEAD, name)[1]
                        for name in ("header_picture", "rows_pictures", "footer_picture"))
PICTURE_MARK = _named("Picture", "mark")[1]
CORPUS_COLUMN_PICTURE_MARKS = 35935


def _column_marks(target, new, unverified):
    """Блок картинки колонки: метка должна совпадать с меткой двух соседних картинок, иначе отказ."""
    if target.node not in COLUMN_HEAD_NODES or target.key not in COLUMN_PICTURES \
            or not isinstance(new, dict):
        return ""
    mark = new.get(PICTURE_MARK)
    differ = {key: target.holder[key].get(PICTURE_MARK) for key in COLUMN_PICTURES
              if key != target.key and isinstance(target.holder.get(key), dict)
              and target.holder[key].get(PICTURE_MARK) != mark}
    if not differ:
        return ""
    words = ", ".join(f"у {key} — {value}" for key, value in differ.items())
    if not unverified:
        raise EditError(
            f"{target.key} с меткой {mark}: у соседних картинок колонки метка другая ({words}), а "
            f"метки трёх картинок колонки ({', '.join(COLUMN_PICTURES)}) у платформы "
            "всегда равны: за меткой следует длина записи картинки, и в одной колонке "
            "платформа пишет три картинки одной версией. Возьмите блок картинки с той же меткой, "
            "что у соседей, — или позовите с unverified=True")
    return (f"; {target.key} = метка {mark} при соседях {words}: {UNSEEN_NOTE} — "
            "метки трёх картинок колонки у платформы всегда равны")


def _inner_mirrors(found_all, target, new, base):
    """Зеркала подполей блока, которые лежат вне блока: то же значение записывается и туда.

    У набора картинок поля картинки внутри блока лежит `picture_size`, зеркало которого —
    `content/u1/picture_size` (`mirror_of` карты). При записи по имени `picture_size` операция пишет оба адреса,
    и блок целиком должен делать то же, иначе `validate` сообщит, что правка записана только в одно из двух
    мест. Основное поле внутри блока с зеркалом снаружи ведётся по тому же правилу. Набор картинок целиком по
    имени не пишется (`picture_set_words`), поэтому записываемого блока с зеркалом внутри сейчас нет; проверка
    оставлена на случай, когда такой блок появится (недописанное зеркало `validate` называет ошибкой уровня 2).

    Подполе в новом блоке есть всегда: обход карты идёт только по названным позициям блоков, а блок без такой
    позиции `_property_value` отвергает раньше («значение брать неоткуда»)."""
    size = len(target.trail)
    out, done = [], set()
    for sub in found_all:
        if len(sub.trail) <= size or sub.trail[:size] != target.trail:
            continue
        primary, mirrors = _mirror_group(found_all, sub, base)
        for other in [primary] + mirrors:
            if other.trail[:size] == target.trail or id(other) in done:
                continue
            value = new
            for step in sub.trail[size:]:
                value = value[step]
            done.add(id(other))
            rel = "/".join(sub.trail[size:])
            out.append((other.holder, other.key, copy.deepcopy(value),
                        f"подполе {rel} блока {target.key} — зеркало этого адреса (`mirror_of` "
                        "карты), то же значение, как при правке подполя по имени",
                        "/".join(other.trail)))
    return out


def _property_value(slot, bit, value, current, name, whose):
    """Значение, приведённое к виду поля и проверенное картой; при ошибке отказ со словами.

    Многоязычную строку можно передать просто текстом: переписывается видимый член прежней строки, как в `set_caption`. Блок
    проверяется целиком тем же `validate`, что и форма: строение, связи и проверка обратным разбором («собрали —
    разобрали — получили то же»)."""
    if bit is not None:
        if not isinstance(value, bool):
            raise EditError(f"{name} — бит слова {slot.name}: это ГАЛОЧКА, true или false, а "
                            f"пришло {value!r}")
        return value
    if isinstance(slot, schema.N):
        if slot.type == "LocalizedString" and isinstance(value, str):
            block = copy.deepcopy(current) if isinstance(current, dict) else {}
            return set_text(block, value)
        if not isinstance(value, dict):
            raise EditError(f"{name} у {whose} — блок {slot.type}, и пишут его объектом (как в "
                            f"decode), а пришло {value!r}")
        fatal = [problem.text for problem in validate.validate(value, type_name=slot.type)
                 if problem.fatal]
        if fatal:
            raise EditError(f"{name}: значение не того строения, что блок {slot.type} — "
                            + "; ".join(fatal[:3]))
        return copy.deepcopy(value)
    out = []
    validate._check_value(slot, value, (name,), out)
    if slot.kind == schema.TYPE:
        out.append(validate.Problem(1, True, name, f"{name} — тип элемента, его не меняют"))
    fatal = [problem.text for problem in out if problem.fatal]
    if fatal:
        raise EditError(f"{name} у {whose}: " + "; ".join(fatal))
    return value


# «Значение не передано» нужно отличать от `None`: у Стиля формы `None` означает «Авто» (позиции нет).
NO_VALUE = object()


def _form_refusal(found, bit):
    """Отказ для поля корня формы со словами; `None` — поле входит в перечень строк палитры (`FORM_WRITES`).

    Сначала проверяются поля с отдельной операцией (`FORM_REFUSALS`: заголовок, шрифт, страницы, обработчики,
    реквизиты, связи контекстного меню, производные поля и счётчики), затем строение тем же кодом, что для
    элементов (флаг строения, версия, постоянное значение, список, контейнер), и последним — «у формы такой
    строки палитры нет»."""
    trail = _form_trail(found)
    if trail == FORM_PICTURE_SET:
        # Ровно сам набор: его строки (`…/pictures/picture`, `…/picture_size`) задаются перечнем.
        return FORM_PICTURE_SET_WORDS
    for refused, words in FORM_REFUSALS.items():
        if trail == refused or trail.startswith(refused + "/"):
            return words
    structural = _property_refusal(found, None, bit)
    if _form_written(trail)[0] is not None:
        return structural
    if structural is not None:
        return structural
    rows = ", ".join(sorted({row[0] for row in FORM_WRITES.values()}))
    return (f"{found.key!r} у формы по имени не пишется: у самой формы set_property пишет только "
            f"строки её палитры с адресом ({rows}; Стиль — style), и это поле среди них не "
            "значится")
