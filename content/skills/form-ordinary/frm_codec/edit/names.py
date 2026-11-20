"""Имена полей карты, имена записей шрифта и кнопки-меню, границы корпуса.

Часть редактора. Все имена доступны через `frm_codec.edit`."""

from .. import validate, schema



"""Редактор формы: операции над документом уровня 1 поверх кодека.

## Зачем он есть

Кодек читает `form.frm` в JSON и собирает обратно; править JSON можно и руками. Но чтобы платформа форму
приняла, надо вести рукой много мелочей: сквозной номер кнопки и счётчик в голове блока действий, счётчик
списка элементов, сквозной индекс элемента и счётчик его выдачи, самоссылки привязок, страницу и порядок
обхода в хвосте блока координат, строки в списках панели или формы, на которой лежит элемент, имя и Данные колонки (два свойства, а не одно
имя в двух местах — см. `add_column`), процедуру в `form.bsl`. Здесь эти мелочи ведёт код, а не человек.

Забытая мелочь стоит по-разному: счётчик списка элементов ловит `validate`; единица на месте счётчика
пятого списка блока координат не ловится ничем, и конфигуратор не открывает обработку целиком; отставший
`last_index` не ловит никто — форма работает, но следующий элемент, заведённый в конфигураторе, получает
занятый индекс.

## Что операция обязана оставить после себя

Документ, проходящий `validate` без отказов и без предупреждений, которых сама операция могла не
порождать. Это проверяется на каждой операции.

## Правило состава: на чём стоит операция

Операцией становится приём, принятый платформой, либо приём, чью форму-результат подтверждает корпус.
Разница несущая: «платформа такие формы пишет» и «платформа приняла форму, которую собрал редактор» —
разные утверждения.

Платформа проверяла вариант, а не операцию целиком: реквизит одного типа (Строка без квалификаторов),
привязку у одного типа элемента (поле ввода), одно событие (`OnChange` там же), удаление кнопки с одним
видом действия (стандартное). Вызов шире операция делает — форму-результат подтверждает корпус, — но
называет это в отчёте: перечень вариантов `ON_CORPUS`, пометку ставит одно место (`_on_corpus`).
Молчаливого расширения «проверено» на непроверенное нет. Где корпус форму-результат не подтверждает —
отказ, а не пометка.

Приём без проверки платформой и без корпуса операцией не становится: он черновик и по умолчанию отказывает,
называя, чего не знает платформа (`unverified=True` снимает отказ). Таких три: `remove_page` и страницы
самой формы (`add_form_page`, `remove_form_page`: правило снято с корпуса, пары «до и после» нет).

«GUID» в карте не значит «уникальный». Кнопки-меню, собранные редактором, платформа открывает, сохраняет и
возвращает байт в байт, но меню в 1С:Предприятии не выпадает, пока у набора кнопок меню случайный GUID: у
всех меню корпуса он один и тот же (`schema.MENU_BUTTON_SET`). Выдавать GUID заново операция вправе только
там, где его выдаёт платформа (голова блока, кнопка). Владелец кнопки (`BTN_OWNER`) — голова её блока, и
ставит его операция, а не шаблон.

Шрифт проверялся иначе: платформе давали записи, которые карта не умела назвать, и смотрели, что покажет
палитра и диалог «Выбор шрифта». Все записи платформа приняла и при пересохранении вернула байт в байт. У
`set_font` поэтому две проверенные дороги; умолчание — та, что меньше вмешивается (`TYPEFACE_WAYS`).

## Имена полей — у карты, адреса — у строения

Литералов вида `"u7"` там, где у карты есть имя, нет: имя спрашивается у `schema.MAP` по позиции (`_at`),
как у `validate._reference_names`. Где имени у карты нет (имя страницы панели, имя и номер колонки, член
списка панели или формы), позиция называется запасным ключом.

Узлы ищутся строением, а не адресом: блок действий — по паре ключей (как в `meaning._bars`), держатель
страниц — поиском имени карты (`validate._pages_of`), держатель колонок — по ключу `columns`.

## Общие части с проверкой зовутся, а не копируются

`validate.PLACEMENT_NAMES`, `COMMANDBAR_NAMES`, `NUMBERING_NAMES`, `REFERENCE_NAMES`, `NO_REFERENCE`,
`_pages_of`: две копии одного правила, разойдясь, дали бы дыру в той, о которой забыли.
"""


# ── Имена карты ──

PAGE, PAGE_SEQUENCE, COORDS, ELEMENTS, ITEMS, PAGES = validate.PLACEMENT_NAMES
ACTIONS, BUTTON_SETS, BUTTONS, BUTTON_ID, ACTION_ID = validate.COMMANDBAR_NAMES
NUMBER, LAST_NUMBER, SET_REF, SET_CODE, REF_ID, REF_CODE = validate.NUMBERING_NAMES
TITLE_REF, LAST_INDEX, NEXT_ID, BINDINGS, ATTR_LIST, BIND_ELEMENT = validate.REFERENCE_NAMES
NO_REFERENCE = validate.NO_REFERENCE


def _at(type_name, index, expect=None):
    """Имя поля карты по позиции. Если имени нет, при импорте будет отказ со словами, а не `KeyError`.

    Имя не ищется по самому имени (`slot.name == "caption"`): позиция служит адресом, и на неё отвечает сама
    карта.
    """
    node = schema.MAP[type_name]
    slot = node.fields.get(index)
    if slot is None or (expect is not None and getattr(slot, "type", None) != expect):
        raise schema.SchemaError(
            f"редактор ждёт у {type_name} на позиции {index} "
            + (f"узел {expect}" if expect else "поле")
            + f", а карта держит там {slot!r}; правило устарело вместе с картой — поправьте его "
              "вместе с ней, а не обходите")
    return slot.name


def _maybe(type_name, index):
    """Имя позиции, если его дала карта, иначе запасной ключ `u<индекс>`, как при разборе.

    Запасной ключ нужен там, где у карты нет имени: имя страницы панели, имя и номер колонки, элемент в строке
    списка панели или формы. Когда карта назовёт позицию, редактор начнёт использовать это имя.
    """
    slot = schema.MAP[type_name].fields.get(index)
    return slot.name if slot is not None else f"u{index}"


def _run_of(type_name, kind, node_type=None):
    """Отрезок узла целиком, выбранный по виду отрезка и типу члена, а не по литералу.

    Он нужен там, где спрашивают не только имя: у отрезка по маске — таблицу битов и порядок значений, у
    необязательного блока — оба набора значений флага.
    """
    for segment in schema.MAP[type_name].runs.segments:
        if isinstance(segment, kind) and (node_type is None
                                          or getattr(segment, "type", None) == node_type):
            return segment
    raise schema.SchemaError(f"редактор ждёт у {type_name} отрезок {kind.__name__}"
                             + (f" из {node_type}" if node_type else "")
                             + ", а карта его не держит")


def _run(type_name, kind, node_type=None):
    """Имя отрезка узла."""
    return _run_of(type_name, kind, node_type).name


# Элемент: имена полей одинаковы у всех двадцати пяти вариантов, а позиции различаются (у поля географической
# схемы и диаграммы координаты стоят четвёртыми). Имена берутся у панели, как в `validate`.
INDEX = _at("Element.Panel", 1)
CONTENT = _at("Element.Panel", 2)
NAME_BLOCK = _at("Element.Panel", 4, "NameBlock")
NAME = _at("NameBlock", 1)
COUNT = _at("Elements", 0)

CAPTION = _at("Title", 0, "LocalizedString")
LS_MARK, LS_COUNT = _at("LocalizedString", 0), _at("LocalizedString", 1)
LS_ITEMS = schema.MAP["LocalizedString"].repeat.name
LANG, TEXT = _at("LangText", 0), _at("LangText", 1)

X, Y, WIDTH, HEIGHT = (_at("Coords", i) for i in (1, 2, 3, 4))
ANCHORS = tuple(_at("Coords", i, "Anchor") for i in (6, 7, 8, 9))
RULE, RULE2 = _at("Anchor", 1, "AnchorRule"), _at("Anchor", 2, "AnchorRule")
# У привязки два правила, и операции должны знать оба из одного перечня. Платформа читает второе правило и
# создаёт встречную запись так же, как для первого, поэтому при удалении элемента эта запись не должна
# оставаться.
RULES = (RULE, RULE2)
RULE_OBJECT, RULE_SIDE, RULE_OFFSET = (_at("AnchorRule", i) for i in (1, 2, 3))
NO_ANCHOR = {RULE_OBJECT: -1, RULE_SIDE: 6, RULE_OFFSET: 0}
DEP_MARK, DEP_ELEMENT, DEP_SIDE = (_at("CoordsDependent", i) for i in (0, 1, 2))
_COORDS_RUNS = schema.MAP["Coords"].runs.segments
DEPENDENTS = tuple(segment.name for segment in _COORDS_RUNS[:4])
EMPTY_LISTS = tuple(segment.name for segment in _COORDS_RUNS[4:6])
_TAIL = _COORDS_RUNS[-1].fields
# Порядок обхода — позиция `L6+2` хвоста блока координат (опыты T120/T121); позиция `L6+1` — номер на странице
# (`PAGE_SEQUENCE`), порядком обхода она НЕ является.
TAB_ORDER = _TAIL[2].name
MANUAL_H, MANUAL_V = _TAIL[3].name, _TAIL[4].name

BTN_NAME = _at("Element.CommandBarButton", 1)
BTN_TEXT = _at("Element.CommandBarButton", 4, "LocalizedString")
ACT_KIND = _at("CommandBarAction", 3)
ACT_SPEC = _at("CommandBarAction", 4, "ActionSpec")
EXTRAS = _run("CommandBarAction", schema.Flagged)
SPEC_MARK = _at("ActionSpec.v1", 0)
HANDLER = _at("EventAction.v3", 1)
DESCRIPTION = _at("EventAction.v3", 2, "ActionDescription")
DESC_NAME = _at("ActionDescription", 1)
STANDARD_ACTION = _at("EventAction.v6", 3)
STANDARD_MARK = schema.MAP["EventAction.v6"].fields[0].const
PROCEDURE_MARK = schema.MAP["EventAction.v3"].fields[0].const
REF4_MARK = schema.MAP["ActionSpec.v4"].fields[0].const
TOOL_TIP, DESC_BIT, SHORTCUT = "tool_tip", "description", "shortcut"
# Свойства соседа, которые снимает `like`: ИсточникДействий, КнопкаПоУмолчанию и сочетание клавиш. Они названы
# именами карты, а не литералами.
ACTION_SOURCE = _at("NameBlock", 2)
DEFAULT_BUTTON = _at("Content.Button.u1", 5)
SHORTCUT_KEY, SHORTCUT_MODIFIERS = _at("Shortcut", 1), _at("Shortcut", 2)

PAGES_COUNT = _at("PanelPages.v1", 1)
PAGE_ITEMS = schema.MAP["PanelPages.v1"].repeat.name
GUIDE_COORD, GUIDE_ORDER, GUIDE_PAGE = (_maybe("Guide", i) for i in (1, 4, 5))

EVENTS = _at("Content.Label", 2, "EventList.Label")
EVENT_ITEMS = schema.MAP["EventList.Label"].repeat.name
EVENT_NAME, EVENT_KIND, EVENT_ACTION = (_at("EventHandler.Label", i) for i in (0, 1, 2))
ATTR_NAME = _at("Attribute", 4)
ATTR_PATTERN = _at("Attribute", 5, "Pattern")
# Блоки типа внутри описателя (`{"S",150,1}`, `{"N",9,0,1}`, `{"#",<GUID>}`). Карта выбирает вариант блока по
# букве. У описателя это список: у составного типа несколько блоков, у произвольного — ни одного. По букве
# видно, к какому типу относится описатель.
PATTERN_MARK = _at("Pattern", 0)
PATTERN_TYPES = schema.MAP["Pattern"].repeat.name
PATTERN_KIND = _at("PatternType.S", 0)      # имя буквы одно у всех вариантов
ATTR_ID = _maybe("Attribute", 0)          # id реквизита: блок из одного числа, имени карта не даёт
ATTR_HEAD = _maybe("Attributes", 0)       # блок из одного числа — номер основного реквизита
BIND_PATH = _at("AttributeBinding", 1, "AttributePath")
PATH_STEPS = _run("AttributePath", schema.Counted)
STEP_VALUE = _maybe("AttributePathStep", 0)

# Путь к колонкам внутри содержимого табличного поля — три позиции карты подряд. Искать только по ключу
# `columns` нельзя: он есть и у списка выбора (`ValueList`) в том же поддереве.
COLUMNS_PATH = (_at("Content.TableBox", 2, "Content.TableBox.u2"),
                _at("Content.TableBox.u2", 1, "Content.TableBox.u2.u1"),
                _at("Content.TableBox.u2.u1", 23, "TableBoxColumns"))
COLUMNS = COLUMNS_PATH[-1]
COLUMN_ITEMS = schema.MAP["TableBoxColumns"].repeat.name
COLUMNS_COUNT = _at("TableBoxColumns", 0)
COLUMN_TYPE = _at("Element.TableBoxColumn", 0)
COLUMN_BODY = _at("Element.TableBoxColumn", 1, "Element.TableBoxColumn.u1")
COLUMN_INNER = _at("Element.TableBoxColumn.u1", 1, "Element.TableBoxColumn.u1.u1")
# Голова колонки зависит от вида вложенного элемента: у колонки с элементом это узел `schema.COLUMN_HEAD`, без
# элемента — `schema.COLUMN_HEAD_BARE`. Поля у них общие, имена спрашиваются у первого узла.
COLUMN_HEAD = _at("Element.TableBoxColumn.u1.u1", 1, schema.COLUMN_HEAD_FORK)
COLUMN_HEAD_NODES = tuple(schema.variants(schema.COLUMN_HEAD_FORK))
assert set(COLUMN_HEAD_NODES) == {schema.COLUMN_HEAD, schema.COLUMN_HEAD_BARE}, \
    "голова колонки перестала иметь два строения"
COLUMN_HEADER_TEXT = _at("Element.TableBoxColumn.u1.u1.u1", 1, "LocalizedString")
COLUMN_WIDTH = _at("Element.TableBoxColumn.u1.u1.u1", 4)
# У колонки списка значений база `{8, голова, …}` лежит на позиции 1 без обёртки с Данными, поэтому голова
# находится на уровень ближе. Узел базы тот же, что у остальных колонок на `1/1` (`_at` проверяет это при
# импорте), и имена головы остаются прежними.
VALUE_LIST_BASE = _at("TableBoxColumn.ValueList", 1, "Element.TableBoxColumn.u1.u1")
PAGE_CAPTION = _at("Element.PanelPage", 1, "LocalizedString")
GUIDES = _run("LayoutList", schema.Counted, "Guide")
DEFAULT_CONTROL = _run("LayoutList", schema.Along)
# Флаг «Распределять по страницам»: без него «АктивизироватьПоУмолчанию» — одно число на весь родитель (`Along.one_unless`).
SEPARATE_BY_PAGE = next(segment.one_unless for segment in schema.MAP["LayoutList"].runs.segments if isinstance(segment, schema.Along))
SHOW_TABS = next(slot.name for segment in schema.MAP["LayoutList"].runs.segments
                 if isinstance(segment, schema.Fixed) and segment.length == 7
                 for i, slot in segment.fields.items() if i == 1)
LAYOUT_LISTS = tuple(segment.name for segment in schema.MAP["LayoutList"].runs.segments
                     if isinstance(segment, schema.Counted) and segment.type == "LayoutRun")

# Позиции, у которых карта не даёт имени. Ключ вычисляется по карте (`_maybe`), а не пишется литералом. Имя
# страницы панели берётся из карты (`Element.PanelPage/name`) через `_at`; если карта перестанет содержать там
# поле, импорт отказывает.
PAGE_NAME = _at("Element.PanelPage", 6)  # имя страницы панели
COLUMN_ORDER = _maybe("Element.TableBoxColumn.u1.u1.u1", 5)  # номер колонки
# У колонки табличной части три позиции для пути данных: Данные (`u2`), ДанныеФлажка (`u3`), ДанныеКартинки
# (`u4`). Путь записан в одной из них, в остальных `[-1]`. В голове колонки три порядковых числа (`u6`, `u7`,
# `u8`), по одному на каждый путь. В позиции с данными это порядковый номер реквизита в табличной части (у
# НомерСтроки в позиции Данных — −2), в остальных −1.
COLUMN_CHECK_PATH = _maybe("Element.TableBoxColumn.u1.u1", 3)
COLUMN_PICTURE_PATH = _maybe("Element.TableBoxColumn.u1.u1", 4)
COLUMN_ORDINALS = tuple(_maybe("Element.TableBoxColumn.u1.u1.u1", i) for i in (6, 7, 8))
# Блок содержимого табличного поля: тип значения (`u1`; для табличной части — описатель с `TypeId` табличной
# части) и вид источника данных (`u3`).
TABLE_TYPE = _maybe("Content.TableBox", 1)
TABLE_SOURCE = _maybe("Content.TableBox", 3)
# Вид источника данных — первый скаляр блока источника (`u3/u1/u0`): у таблицы значений 5, у дерева значений 4, у табличной
# части 2, 6 и 7, у списка 1, 3, 10, 11, 12 и прочих (число — по виду данных, а не по виду колонки).
TABLE_SOURCE_BLOCK = _at("Content.TableBox.u3", 1, schema.TABLE_BOX_SOURCE_BLOCK)
TABLE_SOURCE_KIND = schema.FORKS[schema.TABLE_BOX_SOURCE_BLOCK].key

# Имя колонки и её Данные — два разных свойства. У колонок таблицы значений они обычно совпадают, но не всегда.
# Имена обеих позиций берутся из карты (позиция `1/2` — Данные).
COLUMN_NAME = _at("Element.TableBoxColumn.u1.u1.u1", 30)
COLUMN_DATA_AT = 2
COLUMN_DATA = _at("Element.TableBoxColumn.u1", COLUMN_DATA_AT)
# У колонки списка на месте Данных лежит другое свойство — флаг «ОтображатьСтандартнуюКартинку», и на уровне 1
# имя поэтому не выдаётся: ключ там `u2`. Операции учитывают оба случая, иначе для исправных колонок списка они
# отказывали бы с сообщением «такого места нет».
COLUMN_DATA_KEYS = (COLUMN_DATA, f"u{COLUMN_DATA_AT}")
# «ДанныеФлажка» колонки таблицы значений — строка на позиции 3 тела колонки: у колонки с флажком там имя колонки, а «Данные» пусты.
COLUMN_CHECK_DATA = _at("Element.TableBoxColumn.u1", 3)


# ── Вложенный элемент колонки ──

# Тип значения колонки и два поля вложенного элемента — GUID его типа и сам элемент. Элемент хранится в конверте
# (`ColumnControl.Packed`) с тремя полями: содержимое, пустые куски, раскладка. Имена берутся из карты по
# позициям.
COLUMN_VALUE_TYPE = _at("Element.TableBoxColumn.u1.u1.u1", 35, "Pattern")
COLUMN_CONTROL_TYPE = _at("Element.TableBoxColumn.u1.u1.u1", 38)
COLUMN_CONTROL = _at("Element.TableBoxColumn.u1.u1.u1", 39, "TableBoxColumn.Control")
# Позиция блока вложенного элемента в голове колонки. У колонки без элемента на ней стоит число 0, а всё, что идёт дальше
# (в том числе зеркало ширины), стоит на одну позицию ближе: голова с элементом на одну позицию длиннее.
COLUMN_CONTROL_AT = 39
# Расположение колонки (`location`): первая колонка табличного поля стоит «в новой колонке» — так у всех колонок корпуса,
# стоящих первыми; у прочих бывают и «в той же колонке», и «на новой строке».
COLUMN_LOCATION = _at("Element.TableBoxColumn.u1.u1.u1", 26)
NEW_COLUMN = "NewColumn"
assert schema.MAP[schema.COLUMN_HEAD].fields[COLUMN_CONTROL_AT].name == COLUMN_CONTROL
CONTROL_ELEMENT = _at("TableBoxColumn.Control", 0, "ColumnControl.Packed")
CONTROL_LINKS = _run("TableBoxColumn.Control", schema.Counted, "TypeLinkEntry")
PACKED_CONTENT = _at("ColumnControl.Packed", 0, "ColumnControl")
PACKED_EMPTY = _at("ColumnControl.Packed", 1)
PACKED_LAYOUT = _at("ColumnControl.Packed", 2)
CONTROL_KIND = schema.FORKS["ColumnControl"].key
# Вид вложенного элемента → первое число его тела. Перечень видов задан в карте, а не здесь.
CONTROL_KINDS = {variant[len("Content."):]: code
                 for code, variant in schema.FORKS["ColumnControl"].names.items()}
TEXTBOX_PATTERN = _at("Content.TextBox", 1, "Pattern")
TEXTBOX_PROPS = (_at("Content.TextBox", 2, "Content.TextBox.u2"),
                 _at("Content.TextBox.u2", 0, "Content.TextBox.u2.u0"))
# Квалификаторы типа поля ввода хранятся в двух местах: в описателе типа и в свойствах поля (`digits` — основной
# адрес строки палитры «Длина»). У тела из шаблона «N» оба места совпадают по трём числам, у тела из шаблона «S»
# — по одному: длина строки в описателе равна `digits`.
TEXTBOX_NUMBER = tuple(_at("Content.TextBox.u2.u0", i) for i in (14, 15, 16))
TEXTBOX_LENGTH = TEXTBOX_NUMBER[0]
PATTERN_NUMBER = tuple(_at("PatternType.N", i) for i in (1, 2, 3))
PATTERN_LENGTH = _at("PatternType.S", 1)
PATTERN_REF = _at("PatternType.Ref", 1)       # GUID типа у ссылки (`#`)


# ── Имена записи шрифта ──

# Все имена берутся из карты и не переписаны словами: отдельный перечень молча разошёлся бы с разбором.
FONT_SOURCE = _at("Font.v3", 1)
FONT_VERSION = _at("Font.v3", 0)
_FONT_RUN = next(segment for segment in schema.MAP["Font.v3"].runs.segments
                 if isinstance(segment, schema.Masked))
OVERRIDES = _FONT_RUN.name
# Порядок битов совпадает с порядком значений в файле, а не с возрастанием масок: бит имени (1) стоит последним.
# Порядок ключей восстанавливает `_order_overrides`.
FONT_BITS = tuple(_FONT_RUN.bits)
SCALE_SET = next(iter(_FONT_RUN.flags))
# Вид значения для каждого бита задан картой. У бита без значения (512) вида в карте нет, он записывается
# булевым полем, так как отрезок построен именно так. Бит входит в общий перечень, чтобы `scale_set` проверялся
# тем же правилом и теми же словами, что соседние флаги.
FONT_KINDS = {name: kind for name, (_mask, kind) in _FONT_RUN.bits.items()}
FONT_KINDS[SCALE_SET] = "bool"
FONT_SCALE = next(slot.name for segment in schema.MAP["Font.v3"].runs.segments
                  if isinstance(segment, schema.Fixed)
                  for i, slot in segment.fields.items() if i == 1)
FONT_REF = next(slot.name for slot in _run_of("Font.v2", schema.Masked).lead)
STYLE_FONT = _at("StyleFontRef", 0)
SYSTEM_FONT = _at("SystemFontRef", 0)
FONT_SOURCES = schema.ENUMS[schema.MAP["Font.v3"].fields[1].enum].codes
STYLE_FONTS = schema.ENUMS[schema.MAP["StyleFontRef"].fields[0].enum].codes
SYSTEM_FONTS = schema.ENUMS[schema.MAP["SystemFontRef"].fields[0].enum].codes
# Вид записи, который операция не пишет и не правит. У абсолютного шрифта все свойства лежат в своих позициях, а
# слово маски читается целиком (`Font.v0.flags`); что оно значит, не установлено. Имя берётся из карты для кода
# 0.
ABSOLUTE = next(name for name, code in FONT_SOURCES.items() if code == 0)
AUTO = next(name for name, code in FONT_SOURCES.items() if code == 3)
# Поля, в которых карта хранит запись шрифта, названы именами, а не адресами: `font` у семнадцати типов и у
# формы, `header_font` и `footer_font` у табличного поля, `text_font` у его колонки. Они находятся обходом
# карты, поэтому новый адрес попадёт в операцию автоматически.
FONT_KEYS = tuple(sorted({slot.name for node in schema.MAP.values()
                          for slot in (node.fields or {}).values()
                          if isinstance(slot, schema.N) and slot.type == "Font"}))


# ── Имена кнопки-меню ──

# Режим меню — флаг строения: при значениях «Use» и «UseExtra» в теле записи кнопки лежит блок меню, а весь
# хвост сдвигается на позицию. Оба набора значений описаны в карте отрезком, и имена режимов берутся по кодам
# этих наборов, а не литералами.
_MENU_RUN = _run_of("Content.Button.u1", schema.Gated)
MENU, MENU_MODE = _MENU_RUN.name, _MENU_RUN.by
MENU_MODES = schema.ENUMS[next(slot.enum for slot in schema.MAP["Content.Button.u1"].fields
                               .values() if slot.name == _MENU_RUN.by)].codes
MENU_WITH = tuple(name for name, code in MENU_MODES.items() if code in _MENU_RUN.when)
MENU_WITHOUT = tuple(name for name, code in MENU_MODES.items() if code in _MENU_RUN.without)
# GUID в голове блока действий и владелец кнопки — ссылка на эту голову. Имена берутся из проверки, которая
# сравнивает их между собой (`validate.OWNER_NAMES`). Карта голову не называет, поэтому ключ запасной. Платформа
# выдаёт новый GUID каждому блоку, а шаблон меню его обнуляет.
BTN_OWNER, ACTIONS_GUID = validate.OWNER_NAMES[:2]
# GUID набора кнопок меню, напротив, постоянный: он один у всех меню корпуса и у платформы. Литерал хранится в
# карте (`schema.CONSTS`), здесь только его имя.
MENU_SET_GUID = schema.MENU_BUTTON_SET


# Варианты вызова, которые шире проверенного платформой. Платформа приняла приём только в одном виде, остальные
# виды подтверждены корпусом: «платформа такие формы пишет», а не «платформа приняла форму, собранную
# редактором».
#
# Перечень составлен по вариантам, а не по операциям: у операции, названной проверенной, часть случаев может не
# быть проверена. Ключ — `<операция>/<чем вызов шире>`.
#
# Числа получены на снимке трёх корпусов (`CORPUS_STAMP`).
ON_CORPUS = {
    "add_attribute/pattern":
        "платформа проверяла реквизит ОДНОГО типа — Строка без квалификаторов; реквизиты с прочими "
        "описателями типа (ссылка `#`, `S`, `N`, `B`, `D`) в образцах форм есть, но платформой не проверялись",
    "bind/element":
        "платформа проверяла привязку данных к ПОЛЮ ВВОДА; в образцах форм привязки лежат у десяти видов "
        "элемента, больше всего у TextBox",
    "set_event/handler":
        "платформа проверяла ОДНО событие одного типа — OnChange у поля ввода; в образцах форм "
        "обработчики приходятся на 53 пары «тип элемента + событие» со строковым именем события, "
        "больше всего на Button.Click, на втором месте TextBox.OnChange. Ещё 17 пар, которых в образцах форм нет, платформа приняла — "
        "у них пометка своя",
    "set_event/remove":
        "снятие обработчика элемента платформой не проверялось: запись удаляется из списка событий, а процедура в модуле "
        "остаётся; список с меньшим числом записей платформа пишет сама",
    "remove_button/action":
        "платформа проверяла удаление кнопки со СТАНДАРТНЫМ действием; в образцах форм действия бывают "
        "стандартные, разделители, процедуры, подменю и ссылки без набора в панели",
    "set_font/place":
        "платформа проверяла шрифт НАДПИСИ — шестнадцать записей, и все шестнадцать "
        "приняла и вернула из пересохранения байт в байт; адресов шрифта в карте "
        "двадцать два: у колонки табличного поля три шрифта, у надписи, поля ввода и кнопки по одному",
    "set_font/record":
        "платформа проверяла четырнадцать сочетаний «вид записи + маска» (одно — `StyleFont` с "
        "маской 572 — записала сама), и все ВЕРСИИ 7. В образцах форм бывает пятьдесят сочетаний "
        "«версия + вид + маска», самое частое — «Авто без переопределений» версии 7",
    "set_font/value":
        "имена шрифтов и размеры взяты из образцов форм ПЕРЕЧНЕМ, а не законом: имён семь (чаще всего "
        "Arial, Verdana, MS Shell Dlg), размеров двадцать два (чаще всего 8, 9 и 10 пунктов). Значение "
        "вне перечня здесь не отказ, и это решение: имя шрифта берёт СИСТЕМА, а не файл, и «такого "
        "в образцах нет» тут наблюдение, а не утверждение о платформе",
    "button/menu":
        "платформа проверяла в меню кнопки формы только пункты-процедуры: меню раскрывается, пункты "
        "срабатывают в 1С:Предприятии; пункты других видов не проверялись. В меню образцов форм "
        "бывают процедуры и разделители, а стандартных действий, подменю и кнопок "
        "без действия нет. Блок меню — тот же CommandBarActions, что у панели",
    "button/menu-remove":
        "платформа проверяла добавление пунктов в меню, но не удаление; в образцах форм бывают пустые "
        "меню — то есть меню без пунктов платформа пишет сама",
    "set_menu_mode/off":
        "платформа проверяла создание меню, но не его снятие; кнопка без меню — обычная кнопка формы, "
        "и на каждой форме образцов с кнопкой снятие возвращает документ к исходному до буквы",
    # Вложенный элемент колонки: платформа проверила по одному варианту каждой операции (`ROUND10_*`). Всё, что
    # шире, подтверждено только корпусом и формами, которые написала сама платформа.
    "set_column_control/control":
        "платформа проверяла ОДНО сочетание — у колонки табличной части с числом поле ввода → поле "
        "выбора из шаблона редактора; смену того же сочетания сама платформа делает так же: меняются "
        "GUID типа и конверт, больше ничего. Прочие сочетания платформой не проверялись. Вложенные "
        "элементы в образцах форм — поле ввода, флажок и поле выбора, и поле выбора не бывает "
        "ни у одной колонки СПИСКА",
    # Колонки: ни одно из пяти действий платформа не проверяла, они держатся на образцах форм.
    "set_column_control/nested":
        "заведение и снятие вложенного элемента колонки платформой не проверялись. В образцах форм есть колонки "
        "обоих строений: голова без вложенного элемента на одну позицию короче, и блок элемента стоит на позиции 39, "
        "а всё, что за ним (в том числе зеркало ширины), — на одну позицию дальше. Операция переносит голову из одного "
        "строения в другое по этой разнице и больше ничего не меняет; что платформа переписывает при смене "
        "«ЭлементУправления» на пустую строку и обратно, кроме типа и конверта, не проверялось",
    "add_column/first":
        "платформа не проверяла первую колонку таблицы значений. Колонка берётся из шаблона редактора (колонка таблицы "
        "значений с полем ввода строки) и ложится в таблицу без колонок; в образцах форм такие таблицы есть, а первая "
        "колонка любого вида стоит «в новой колонке» (`NewColumn`) и в шаблоне так же",
    "set_column_type":
        "платформа не проверяла тип колонки таблицы значений, который записал редактор. Запись — по колонкам образцов форм: тип колонки (`value_type` головы) равен "
        "описателю её поля ввода, а поле ввода числа и даты отличается от поля строки разрядностью, переносом и (у даты) кнопкой выбора; "
        "в предприятии подтверждено только, что колонки таблицы значений создаются при открытии формы по записи формы",
    "remove_column/last":
        "платформа не проверяла снятие последней колонки. Таблица значений и дерево значений без колонок в образцах "
        "форм встречаются, и поля самого табличного поля у них те же, что у таблиц с колонками",
    "add_column/value-list":
        "платформа не проверяла колонку списка значений, которую завёл редактор. Колонки этого вида в образцах форм "
        "есть, но образца конструктора нет: колонка строится по записи образцов форм",
    "remove_column/value-list":
        "платформа не проверяла снятие колонки списка значений. В образцах форм у таблиц со списком значений бывает от "
        "одной до трёх колонок, и номера оставшихся колонок не пересчитываются",
    "set_font/control":
        "шрифт вложенного ПОЛЯ ВВОДА — шрифт ячейки в режиме редактирования (в показе ячейку "
        "рисует шрифт КОЛОНКИ, ШрифтТекста); «Авто» с битом полужирного хранится и виден в "
        "палитре, а в режиме редактирования не применяется, запись диалога (шрифт стиля «Шрифт "
        "текста», начертание группой, scale_set) применяется; прочие записи и шрифт флажка и поля "
        "выбора не проверялись. Запись та же, что у элементов формы, и в образцах форм она есть "
        "у каждого вложенного элемента",
    "set_event/control":
        "платформа проверяла у вложенных элементов ОДНО событие — ПриИзменении поля ввода (вызван в "
        "предприятии) и поля выбора (принято, не вызван: ввод не принят); прочие пары не "
        "проверялись. В образцах форм у вложенных элементов тринадцать пар «вид + событие», "
        "чаще всего ПриИзменении поля ввода",
    # Общая операция свойств проверена платформой на своих правках (`ROUND11_*`, `ROUND12_*`), и для них пометка
    # своя. Для остальных вызовов значение берётся из образцов форм.
    "set_property/value":
        "платформа проверяла общую операцию свойств на тринадцати правках (кнопки выбора и очистки, "
        "ЦветТекстаПоля, ГоризонтальноеПоложение и связь по типу поля ввода, Подсказка кнопки, "
        "РежимВыделенияСтроки табличного поля, Ширина колонки, Стиль формы, РежимВыбораИзСписка, "
        "Маска поля ввода) и на тридцати двух строках палитры САМОЙ формы (`edit.ROUND15_FORM`: "
        "размеры, окно, сетка, закладки, цвета, картинки, Доступность); этого поля этого типа с "
        "этим значением в этом строении она не проверяла",
    "set_type_link/path":
        "связь по типу, собранную РЕДАКТОРОМ, платформа проверила у поля ввода ФОРМЫ строением "
        "`{id реквизита},{0,GUID}`; прочие строения стоят только на образцах форм",
    # Свойства самой формы: обработчики событий, шрифт, «Сохраняемые значения».
    "set_form_event/handler":
        "платформа завела все шестнадцать обработчиков формы сама (лупа строки палитры создала "
        "процедуру, форма вернулась из пересохранения), и запись операции повторяет её до буквы; вызов "
        "обработчика в 1С:Предприятии не проверялся. В образцах форм обработчики встречаются у "
        "одиннадцати из тринадцати событий формы, у контейнера страниц (ПриСменеСтраницы) и у настроек "
        "(ПередСохранениемЗначений, ПослеВосстановленияЗначений)",
    "set_form_event/remove":
        "снятие обработчика платформой не проверялось: запись удаляется из списка, а процедура в модуле "
        "остаётся. Список с меньшим числом записей и пустой список в образцах форм есть",
    "set_font/form":
        "платформа проверяла шрифт ФОРМЫ одной правкой — абсолютный Arial 13 полужирный из «Авто»; запись «Авто» с переопределением, шрифт стиля и системный шрифт формы стоят на образцах "
        "форм; абсолютного шрифта у формы в образцах нет",
    "set_saved_values/add":
        "платформа проверяла ОДНУ запись — реквизит формы, выбранный в диалоге «Выбор объекта»; "
        "GUID записи платформа берёт из своих метаданных, в файле формы его больше нет, поэтому операция "
        "принимает его только от вас и только с unverified",
    "set_saved_values/remove":
        "снятие записи платформой не проверялось; список с меньшим числом записей и пустой список в "
        "образцах форм есть",
    # Страница самой формы: элементы проверялись на форме (страница 0) и на второй странице панели; на второй
    # странице формы не проверялись.
    "add_element/form-page":
        "элементы клались на первую страницу формы и на вторую страницу ПАНЕЛИ (порядок обхода и "
        "номер на странице платформа записала сама); на страницу формы после "
        "первой — не проверялось. Страниц формы больше одной у немногих форм образцов, и у их "
        "элементов порядок обхода идёт 1…N в пределах страницы формы, а номер на странице "
        "сплошняком от нуля; операция ведёт оба так же, как на странице панели",
}
ON_CORPUS_NOTE = "стоит на корпусе, в предприятии не проверялось"
UNSEEN_NOTE = "корпус такого не видел ни разу, в предприятии не проверялось"
# Одна подпись для всех чисел модуля: наборы, текст вариантов и отказы получены на снимке трёх
# корпусов.
CORPUS_STAMP = "по образцам форм"

# Наборы, посчитанные по корпусу, лежат рядом с текстом вариантов и заменяют его там, где нужен код.
#
# Пометка «на корпусе» ставится по набору. Это позволяет отличить «таких форм 2 295» от «таких форм нет». Во
# втором случае форму не подтверждает ни платформа, ни корпус, и по правилу состава операция должна отказать, а
# не ставить пометку. Набор считается тем же обходом, которым операция его запрашивает.
CORPUS_BIND_TYPES = {
    "TextBox": 18948, "TableBox": 4334, "CheckBox": 3499, "ComboBox": 2449, "Label": 2295,
    "RadioButton": 329, "ListBox": 74, "ProgressBar": 24, "TrackBar": 7, "CalendarBox": 5,
}

# Пары «тип элемента + событие» со строковым именем события. Записи, где имя события — число (все у
# `HTMLDocumentField`, коды 2, 3, 8, 10, 11, 17), в набор не входят: у них нет имени, а операция принимает имя.
CORPUS_EVENT_PAIRS = {
    ("Button", "Click"): 12790, ("TextBox", "OnChange"): 7820,
    ("SpreadsheetDocumentField", "OnChangeAreaContent"): 3660,
    ("SpreadsheetDocumentField", "Selection"): 3433, ("ComboBox", "OnChange"): 2273,
    ("TextBox", "StartChoice"): 2248, ("SpreadsheetDocumentField", "OnActivate"): 1815,
    ("Label", "Click"): 1697, ("TextBox", "Clearing"): 1696, ("CheckBox", "OnChange"): 1562,
    ("ComboBox", "Clearing"): 1268, ("TableBox", "OnRowOutput"): 909,
    ("TableBox", "OnDataGet"): 836, ("Panel", "OnCurrentPageChange"): 698,
    ("TableBox", "Selection"): 594, ("TableBox", "OnActivateRow"): 579,
    ("TextBox", "StartListChoice"): 527, ("TableBox", "BeforeAddRow"): 440,
    ("TableBox", "BeforeRowChange"): 336, ("RadioButton", "OnChange"): 323,
    ("TableBox", "OnStartEdit"): 323, ("TextBox", "Opening"): 303,
    ("TableBox", "BeforeDeleteRow"): 299, ("TableBox", "OnEditEnd"): 298,
    ("TextBox", "ChoiceProcessing"): 290, ("TextBox", "TextEditEnd"): 276,
    ("PictureBox", "Click"): 257, ("SpreadsheetDocumentField", "DetailProcessing"): 211,
    ("TableBox", "AfterDeleteLine"): 188, ("TableBox", "BeforeEditEnd"): 184,
    ("TableBox", "OnCheckChange"): 172, ("TextBox", "AutoCompleteText"): 161,
    ("TableBox", "ChoiceProcessing"): 139, ("TextBox", "Tuning"): 74,
    ("TableBox", "DragCheck"): 45, ("TableBox", "Drag"): 37, ("ListBox", "OnActivateRow"): 35,
    ("TableBox", "DragEnd"): 32, ("TableBox", "OnActivateCell"): 29,
    ("TableBox", "DragStart"): 28, ("TableBox", "NewObjectWriteProcessing"): 18,
    ("TableBox", "OnActivateColumn"): 12, ("ComboBox", "ChoiceProcessing"): 8,
    ("ComboBox", "StartListChoice"): 8, ("ListBox", "OnCheckChange"): 6,
    ("TrackBar", "OnChange"): 6, ("ListBox", "Selection"): 5, ("TableBox", "ValueChoice"): 5,
    ("HTMLDocumentField", "DocumentComplete"): 3, ("PictureBox", "DragStart"): 3,
    ("CalendarBox", "OnChange"): 2, ("CalendarBox", "OnPeriodOutput"): 2,
    ("CalendarBox", "Selection"): 1,
}

# Пары «тип + событие», которых нет в корпусе, но которые платформа приняла. Структура та же, что у набора
# корпуса: ключ — пара. Вместо числа указана отметка проверки и условие, без которого обработчик в
# 1С:Предприятии не вызывается. Условие не является ни отказом, ни правкой: операция пишет обработчик, а не
# свойства элемента, и лишь сообщает, что обработчик сработает при этом условии.
#
# Редактор назначил все семнадцать пар, конструктор открыл форму без сообщений, и в 1С:Предприятии сработали все
# семнадцать обработчиков; часть из них — только при условии из свойств элементов (ниже).
ROUND9 = "r9"
ROUND_EVENT_NOTE = "проверено — принято платформой, обработчик вызывается в предприятии"
_DRAG_START = ("приходит ИСТОЧНИКУ, у которого РазрешитьНачалоПеретаскивания ☑ (у поля "
               "календаря и поля картинки по умолчанию снято)")
_DRAG_CHECK = ("приходит ПРИЁМНИКУ, у которого РазрешитьПеретаскивание ☑ (у поля календаря и "
               "поля картинки по умолчанию снято)")
# Условие броска для поля календаря и поля картинки нельзя переносить на поле табличного документа: оно
# принимает бросок стандартной обработкой даже при пустой проверке. Совет «`СтандартнаяОбработка = Ложь`» для
# табличного документа вредит: он отключает обработку, которая кладёт значение в ячейку. Это не проверялось.
_DRAG = ("приходит приёмнику, только если ЕГО ПроверкаПеретаскивания разрешила действие — "
         "`СтандартнаяОбработка = Ложь; ПараметрыПеретаскивания.Действие = "
         "ДействиеПеретаскивания.Копирование;`; без этого бросок отвергается и обработчик "
         "молчит (проверено у поля календаря и поля картинки); у приёмника — "
         "РазрешитьПеретаскивание ☑")
_DRAG_SHEET = ("приходит приёмнику с РазрешитьПеретаскивание ☑ (у поля табличного документа "
               "стоит по умолчанию), и проверка может быть ПУСТОЙ: стандартная обработка поля "
               "бросок принимает сама — выделение, перетащенное внутри поля, и дата из "
               "календаря, легшая в ячейку. Условие поля "
               "календаря и поля картинки сюда не переносится: `СтандартнаяОбработка = Ложь` в "
               "проверке отключила бы ту обработку, что кладёт значение в ячейку, — это не "
               "проверялось")
_DRAG_END = ("приходит ИСТОЧНИКУ в конце жеста, начатого в нём, — нужно "
             "РазрешитьНачалоПеретаскивания ☑ у источника")
ROUND_EVENT_PAIRS = {
    ("ComboBox", "StartChoice"): (ROUND9, ""),
    ("ComboBox", "Opening"): (ROUND9, ""),
    ("ComboBox", "Tuning"): (ROUND9, "вызывается, только если у элемента КнопкаРегулирования "
                                     "☑ — без неё кнопки ⇕ на поле нет"),
    ("ComboBox", "TextEditEnd"): (ROUND9, ""),
    ("ComboBox", "AutoCompleteText"): (ROUND9, ""),
    ("CalendarBox", "OnActivateDate"): (ROUND9, ""),
    ("CalendarBox", "DragStart"): (ROUND9, _DRAG_START),
    ("CalendarBox", "DragCheck"): (ROUND9, _DRAG_CHECK),
    ("CalendarBox", "Drag"): (ROUND9, _DRAG),
    ("CalendarBox", "DragEnd"): (ROUND9, _DRAG_END),
    ("PictureBox", "DragCheck"): (ROUND9, _DRAG_CHECK),
    ("PictureBox", "Drag"): (ROUND9, _DRAG),
    ("PictureBox", "DragEnd"): (ROUND9, _DRAG_END),
    ("SpreadsheetDocumentField", "DragStart"): (ROUND9, _DRAG_START),
    ("SpreadsheetDocumentField", "DragCheck"): (ROUND9, _DRAG_CHECK),
    ("SpreadsheetDocumentField", "Drag"): (ROUND9, _DRAG_SHEET),
    ("SpreadsheetDocumentField", "DragEnd"): (ROUND9, _DRAG_END),
}

# События поля HTML-документа. Платформа пишет «ДокументСформирован» именем `DocumentComplete`, а остальные 62 события палитры —
# числами 1…62 в порядке строк палитры. Имя `onproperychange` в палитре без «t», как и здесь. Платформа приняла все 63 записи:
# конструктор открыл форму без сообщений и завёл процедуры. Вызов обработчиков в предприятии этим не проверялся.
HTML_EVENT_NAMES = (
    "onhelp", "onclick", "ondblclick", "onkeypress", "onkeydown", "onkeyup", "onmouseout", "onmouseover", "onmousemove",
    "onmousedown", "onmouseup", "onmousewheel", "onselectstart", "onfilterchange", "ondragstart", "onbeforeupdate",
    "onafterupdate", "onerrorupdate", "onrowexit", "onrowenter", "ondatasetchanged", "ondataavailable", "ondatasetcomplete",
    "onlosecapture", "onproperychange", "onscroll", "onfocus", "onblur", "ondrag", "ondragend", "ondragenter", "ondragover",
    "ondragleave", "ondrop", "onbeforecut", "oncut", "onbeforecopy", "oncopy", "onbeforepaste", "onpaste", "oncontextmenu",
    "onrowsdelete", "onrowsinserted", "oncellchange", "onreadystatechange", "onlayoutcomplete", "onpage", "onmouseenter",
    "onmouseleave", "onactivate", "ondeactivate", "onbeforedeactivate", "onbeforeactivate", "onfocusin", "onfocusout", "onmove",
    "oncontrolselect", "onmovestart", "onmoveend", "onresizestart", "onresizeend", "onresize")
HTML_EVENT_CODES = {name: at for at, name in enumerate(HTML_EVENT_NAMES, 1)}
HTML_DOCUMENT_COMPLETE = ("DocumentComplete", "ДокументСформирован")
HTML_EVENT_NOTE = ("принято платформой — форма открыта конструктором, процедура создана; вызов обработчика в предприятии "
                   "не проверялся")
# Параметры процедуры-обработчика, которые платформа создаёт по лупе: у «ДокументСформирован» один, у остальных два.
HTML_EVENT_PARAMS = {"DocumentComplete": ("Элемент",), **{name: ("Элемент", "pEvtObj") for name in HTML_EVENT_NAMES}}


def html_event(event):
    """`(как записать в файле, имя события)` для события поля HTML-документа; `None` — такого события нет.

    Принимает имя из палитры, `DocumentComplete` или `ДокументСформирован` и число 1…62 (код события)."""
    if event in HTML_DOCUMENT_COMPLETE or event == 0 and not isinstance(event, bool):
        return "DocumentComplete", "DocumentComplete"
    if isinstance(event, int) and not isinstance(event, bool):
        return (event, HTML_EVENT_NAMES[event - 1]) if 1 <= event <= len(HTML_EVENT_NAMES) else None
    if isinstance(event, str) and event in HTML_EVENT_CODES:
        return HTML_EVENT_CODES[event], event
    return None


# Буква типа в описателе реквизита и число описателей корпуса с этой буквой. Считается буква, а не весь блок: за
# буквой идут квалификаторы (`{"S",150,1}`), набор блоков не закрыт, а набор букв закрыт. Для `add_attribute`
# незнакомая буква даёт пометку со словами, а не отказ: корпус подтверждает случай «буква та же, квалификаторы
# другие» и не подтверждает «такого блока в корпусе нет».
CORPUS_PATTERN_LETTERS = {"#": 7531, "S": 4168, "N": 2530, "B": 1998, "D": 668}

# Виды действия кнопки и число записей каждого вида в корпусе (у командных панелей и у меню кнопок). Отчёт об
# удалении называет, сколько раз корпус видел такую форму, а не просто «обычная».
#
# Считает их `_action_kind` — та же функция, которой отчёт называет вид: запись вида 4, у которой в панели есть
# набор, она называет «кнопкой-подменю».
#
# Три вида заданы константами, потому что их слова нужны ещё и границе пунктов меню.
STANDARD_KIND, PROCEDURE_KIND, NO_ACTION_KIND = (
    "стандартное действие", "действие-процедура", "кнопка без действия")
CORPUS_ACTION_KINDS = {
    STANDARD_KIND: 29157, PROCEDURE_KIND: 26868, "разделитель": 31606,
    "кнопка-подменю": 8189, NO_ACTION_KIND: 4, "ссылка вида 4": 5,
    "ссылка, набора которой в панели нет": 5,
}
