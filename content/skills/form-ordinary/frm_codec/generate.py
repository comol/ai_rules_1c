"""Описание формы и движок генерации.

Описание — JSON без координат: вид формы, объект выгрузки, блоки (`command_bar`, `fields`, `group`, `tabs`, `table`), доводка `tune`. Движок переводит
его в ПЕРЕЧЕНЬ ОПЕРАЦИЙ обычного редактора (`plan`) и исполняет их (`apply`): `remove_element` по прежнему содержимому исходной формы, размер формы,
`add_element` с `box` и привязками по ролям, `bind` по метаданным, `add_page`, `add_column`. Второй копии правил редактора здесь нет: всё, что умеет
редактор, он делает и здесь — со своими проверками и отказами.

**Исходная форма.** Генерация пишет СОДЕРЖИМОЕ существующей формы объекта: основной реквизит формы обязан быть типом `Object` того объекта выгрузки, что
назван в описании. Форма другого объекта (или списка, выбора, обработки) — отказ словами, а не чужой GUID в привязках. Элементы исходной формы с теми же
данными, что блок описания (поле, надпись пары, флажок, таблица на ту же табличную часть, её колонки и панель), **остаются** — имя, индекс, привязка
данных, обработчики и свойства прежние, `move_element` меняет место, размер, привязки краёв и страницу (`frm_codec/shell.py`); прочие удаляются,
реквизиты формы остаются как есть. Новые формы в метаданных не заводятся.

**Откуда числа.** Ритм пар (левый отступ, зазор «надпись → поле», высоты, шаг строк, правый отступ), место и высота панелей команд — НОРМЫ вида из
`patterns.json` (большинство форм в конфигурациях, `patterns.norm`); вид из меньше трёх конфигураций (`thin`) или показатель без нормы — отказ словами. Чего в нормах нет,
а геометрии формы нужно, — константы ниже. Числа ряда, блока справа от шапки, переключателей в ряд и разделителя — перепись корпуса (`data/row_norms.json`, `rownorms`).

**Обработка и отчёт** (`kind: "processing"`; объект отчёта — «ВнешнийОтчет.Имя» либо «Отчет.Имя» — тот же вид, а нормы раскладки берутся по виду `report`). Данные формы обработки — реквизиты ФОРМЫ (`source: "form"`: привязка `bind attribute=` с переносом типа в поле,
`bind(copy_type=True)`; новые — ключ `attributes` описания, операция `add_attribute`) и реквизиты самой обработки по выгрузке
(`DataProcessors/<Имя>.xml`): поле на реквизит объекта — тот же `bind data="Объект.Реквизит"`, что у справочника, но **только когда основной реквизит
исходной формы — объект ЭТОЙ обработки в выгрузке**. Нет выгрузки, нет основного реквизита или его тип не объект выгрузки — данные только реквизиты формы, и
поле `source: object` отказывает словами. Нормы вида — большинство форм в конфигурациях (`patterns.json`, «processing»). Блок `spreadsheet` — поле табличного
документа без привязки к данным.

**Что НЕ делает.** Тип значения привязанного поля и колонки пишет `bind`, не движок. Многострочное поле не ставится: по умолчанию однострочное.
Кнопок в командных панелях движок не ставит. Блок `command_bar` берёт панель ИСХОДНОЙ ФОРМЫ с её кнопками и двигает её под нормы; когда в исходной форме
верхней панели нет, ставится панель с автозаполнением и источником действий — формой (`templates.form_bar_node`), нижней — нижняя панель конструктора вида формы
(кнопки стандартных действий формы файлом, без автозаполнения: `templates.form_bottom_bar_node`); отчёт это называет. Панель ТАБЛИЦЫ (ключ `bar` блока `table`) — тоже с автозаполнением, источник действий — таблица. Новые элементы называются по правилу конструктора (поле — имя реквизита,
надпись — `Надпись<Имя>`, таблица — имя табличной части; занято — суффикс числом), таблица на табличную часть и её колонки — образцами конструктора
(`templates.tabular_table`, `tabular_column`). Списки (`catalog.list`, `document.list`) — свой движок `generate_list` (форма списка конструктора,
колонки списка — `edit.listcols`). Модуль формы не трогается: обработчики событий убранных элементов остаются в нём.

**Детерминизм.** Одно описание поверх одной исходной формы — одни байты: имена, координаты и порядок операций считаются из описания, а случайный GUID головы
блока действий панели (`add_element` берёт `uuid4`) на время сборки заменён производным от суммы описания (`_deterministic_guids`). Для ОДНОЙ
исходной формы: перегенерация поверх своего результата двигает номера элементов (платформа ведёт счётчик так же), поэтому «описание то же и файл равен
записанному» — «ничего не изменилось».

**Отметка перегенерации** лежит рядом с ОПИСАНИЕМ, не в дереве выгрузки (чужой файл там уехал бы в загрузку конфигурации): `{"desc_sha256",
"form_sha256", "shell_sha256"}` — суммы описания, ЗАПИСАННОЙ формы и исходной формы. Сверяется файл `-o`, который затирается (`check_target`): его сумма не
равна записанной — отказ словами, пока не дан ключ «затереть» (`overwrite`); отметки нет, а `-o` существует и не равен исходной форме — тоже отказ; API без
`desc_path` защиты нет — запись поверх существующего файла только с `overwrite=True`.
"""
import collections
import contextlib
import copy
import dataclasses
import fractions
import hashlib
import json
import math
import os
import pathlib
import re
import uuid

from . import blank as blank_mod, census, design, edit, layout, limits, metadata, patterns, rownorms, rowstyle, render as render_mod, schema, shell as shell_mod, templates, textwidth, typed, validate
from .edit import base as ed_base, columns as ed_columns, datapath, datatype, rowsa as ed_rowsa, valuesrc
from .edit.names import (ATTR_HEAD, ATTR_ID, ATTR_LIST, ATTR_NAME, ATTR_PATTERN, CONTENT, PATTERN_KIND, PATTERN_LENGTH, PATTERN_NUMBER, PATTERN_TYPES,
                         TABLE_TYPE, TEXTBOX_PATTERN)
from .edit.datatype import STRING_ALLOWED
from . import formsource, rowcensus
from .tree import parse, read_file, render


_REF = re.compile(r"^cfg:[A-Za-z]*Ref\.")      # ссылочный тип выгрузки: cfg:CatalogRef.X, cfg:EnumRef.X, cfg:DocumentRef.X…


class GenerateError(ValueError):
    """Отказ описания или генерации — словами, с перечнем возможного (подкласс `ValueError`: CLI печатает его как отказ)."""


# ── Что поддержано ────────────────────────────────────────────────────────────────────────────

KINDS = {"catalog.item": "catalog", "document.item": "document", "processing": "processing"}
KIND_WORDS = {"catalog": "справочник", "document": "документ", "processing": "обработка"}  # вид объекта выгрузки словами
LIST_KINDS = ("catalog.list", "document.list")
PROCESSING = "processing"
OBJECT_PREFIX = re.compile(r"^(Обработка|DataProcessor|ВнешняяОбработка|ExternalDataProcessor)\.\S+$")   # полное имя обработки в описании (внешней — «ВнешняяОбработка.Имя»)
REPORT_PREFIX = re.compile(r"^(Отч[её]т|Report|ВнешнийОтч[её]т|ExternalReport)\.\S+$")      # полное имя отчёта в описании (внешнего — «ВнешнийОтчет.Имя»); вид описания тот же — processing
REPORT_NORMS = "report"      # вид норм `patterns.json` формы отчёта: у описания с объектом-отчётом нормы берутся по нему, а не по «processing»
SKIPPED_KEYS = ("type", "name", "why", "in")  # запись `skipped` описания из формы (`describe`): движок её не читает
BLOCKS = ("command_bar", "fields", "group", "tabs", "table", "spreadsheet", "radio", "picture", "row", "beside", "split")
BAR_PLACES = ("top", "bottom")
RADIO_KEYS = ("radio", "caption", "options", "direction")
RADIO_DIRECTIONS = ("column", "row")
OPTION_KEYS = ("caption", "value")
PICTURE_KEYS = ("picture", "caption", "size", "align")
PICTURE_ALIGNS = ("left", "right")
PAGE_BLOCKS = ("fields", "group", "table", "spreadsheet", "radio", "picture", "row", "beside")    # блоки на странице панели закладок
FOOTER_BLOCKS = ("fields", "group", "radio", "picture", "row", "beside")      # блоки под растянутой таблицей или панелью закладок: «подвал» — прижимаются к низу с привязками вниз
GROUP_BLOCKS = ("fields", "row")      # блоки внутри рамки
ROW_KEYS = ("row", "stretch")
BUTTON_KEYS = ("button", "width", "name")
BESIDE_KEYS = ("beside", "blocks", "width")
BESIDE_RIGHT = ("radio", "picture", "group")      # блок справа от шапки
BESIDE_LEFT = ("fields", "row", "group", "radio", "picture")      # блоки шапки слева от него: в подвале любого блока шапки нет растягиваемого
SPLIT_KEYS = ("split", "first", "second", "first_size", "grows")
SPLIT_AXES = ("left_right", "top_bottom")      # разделитель вертикальный (части слева и справа) либо горизонтальный (сверху и снизу)
SPLIT_GROWS = ("first", "second", "both")
SPLIT_BLOCKS = ("fields", "row", "group", "tabs", "table", "spreadsheet", "radio", "picture", "beside")      # блоки части; сам `split` в части не вкладывается
CONTROLS = ("TextBox", "CheckBox")
MAX_COLUMNS = 3
ROLE_FORMS = ("item", "folder")
TOP_KEYS = ("kind", "object", "title", "size", "form_use", "blocks", "tune", "skipped", "attributes")
FIELD_KEYS = ("data", "control", "width", "height", "props", "anchors", "font", "caption", "source", "choice_list", "multi_line")
FIELD_SOURCES = ("object", "form")  # откуда реквизит: объекта (умолчание) либо ФОРМЫ — ключ даёт `describe`
FIELDS_KEYS = ("fields", "columns", "align")
SUPPORTED_TYPES = ("Булево — флажок", "Строка, Число, Дата — поле ввода", "ссылки (…Ref.…) — поле ввода с кнопкой выбора")

# Показатели из `patterns.json`, без которых форму не расставить, и показатели нижней панели.
NORM_KEYS = ("label_left", "label_field_gap", "label_height", "field_height", "field_right_margin", "pair_pitch")
TOP_BAR_KEYS = ("top_bar_x", "top_bar_y", "top_bar_height")
BOTTOM_BAR_KEYS = ("bottom_bar_x", "bottom_bar_height")

# Константы геометрии, которых в `patterns.json` нет (формы элемента справочника и документа):
# верх первой пары ниже нижнего края верхней панели — 8 (ровно 25 + 8 = 33); нижний край содержимого → верх нижней панели — 8; лево и право панели
# закладок, таблицы, рамки группы — 8; внутри рамки: лево 8, верх 17, право 8, низ 6 (у документа верх 14 — взят справочник); область страницы
# панели: лево 6, верх 6, право 6, низ 6.
FIRST_BELOW_BAR = 8  # верх первой пары ниже нижнего края верхней панели
BOTTOM_GAP = 8  # от нижнего края содержимого до верха нижней панели
SIDE_MARGIN = 8  # слева и справа у панели закладок, таблицы, рамки
RADIO_INSET = (12, 18, 12, 7)  # лево, верх, право, низ внутри рамки с переключателями: чаще всего в корпусе (12 групп переключателей, 6 столбиком — отступ слева 12 у 3, сверху 18 у 3, снизу 7 у 3)
RADIO_H = 19  # высота переключателя: как у поля (корпус: 15 у 17 переключателей, 19 у 6, 30 у 9 — по вкусу авторов; взята высота ряда пар)
RADIO_PITCH = 20  # шаг переключателей столбиком: самый частый в корпусе (20 у 5 групп из 12)
RADIO_GAP = rownorms.radio_gap()[0]  # зазор между переключателями в ряд: корпус (`row_norms.json`, `radio/gap`; `rownorms.radio_gap`)
PICTURE_INSET = (12, 18, 12, 7)  # лево, верх, право, низ рамки с заголовком вокруг поля картинки: те же отступы, что у рамки переключателей
PICTURE_BORDER = {"mark": 3, "color_kind": 0, "value": {"code": 0}, "border_type": "Single", "explicit": True, "u5": 0,
                  "style_item": {"guid": "48312c09-257f-4b29-b280-284dd89efc1e"}}  # «Одинарная» рамка поля картинки: запись платформы (`edit.cowrites.BORDER_STYLE_ITEM`); без рамки пустое поле в предприятии не видно
PICTURE_MIN = 16  # поле картинки не меньше 16×16: ниже — значок, а не поле
GROUP_INNER = (8, 17, 8, 6)  # лево, верх, право, низ внутри рамки
# «Рядом»: ряд, блок справа, две области с разделителем. Числа — перепись корпуса форм (`frm_codec/data/row_norms.json`, `rowcensus`), читает
# `rownorms`: у каждого число наблюдений и слово «большинство / большинства нет» (`rownorms.source`; строки — в `docs/generate.md`, «Числа ряда»).
ROW_BUTTON_H = rownorms.button("regular", "height")[0]  # высота кнопки ряда (подпись не уже `rowcensus.REGULAR_TW`): корпус, `button regular:height`
ROW_BUTTON_PAD = rownorms.button("regular", "pad")[0]  # кнопка шире подписи на столько: корпус, `button regular:pad`
ROW_BUTTON_MIN_W = rownorms.button("regular", "width")[0]  # наименьшая ширина обычной кнопки: нижняя граница корпуса, `button regular:width`
ROW_SHORT_BUTTON_H = rownorms.button("short", "height")[0]  # кнопка с подписью уже `rowcensus.REGULAR_TW` («…»): корпус, `button short:height`
ROW_SHORT_BUTTON_PAD = rownorms.button("short", "pad")[0]  # корпус, `button short:pad`
ROW_SHORT_BUTTON_MIN_W = rownorms.button("short", "width")[0]  # корпус, `button short:width`
BUTTON_ABS_MIN_W = rownorms.button_floor()[0]  # уже самой узкой кнопки ряда корпуса `width` не бывает
REGULAR_TW = rowcensus.REGULAR_TW
FIELD_CLASS_BY_TYPE = {"string": "S", "decimal": "N"}  # класс значения реквизита (`kind_words`) → состав ширины поля ряда (`rownorms.field_width`)
SIDE_GAP = rownorms.side_gap()[0]  # зазор между шапкой и блоком справа: корпус, `side_gap` (зазор «звено → звено» ряда — `rownorms.gap`)
FRAME_TITLE_PAD = rownorms.frame_title_pad()[0]  # заголовок рамки шире своего текста на отступы слева и справа полной рамки (`render.groupbox.FULL_INDENT`, измерено в предприятии); корпус уже заголовка с этим отступом рамок не знает
SPLIT_GAP = 6  # толщина разделителя: самая частая в корпусе (`anchors.SPLITTER_THICKNESS`: 6 px у 216 разделителей из 386)
SPLIT_MIN_PART = {axis: rownorms.split_min(axis)[0] for axis in ("left_right", "top_bottom")}  # первая часть не уже (не ниже): наименьшая таблица рядом с разделителем в корпусе (`split_table`)
NESTED = (layout.PAGE_INSET,) * 4  # лево, верх, право, низ области страницы панели: норма Конфигуратора, одна на навык (`layout.area.PAGE_INSET`)
# Область страницы «Сверху» — от левого верха панели; ширина = ширина панели − 2 (рамка по краям); высота = высота панели − 20 (полоса закладок 18 + рамки)
PANEL_AREA = render_mod.PAGE_AREA_OFFSET["Top"]  # (1, 19)
PANEL_AREA_W = 2
PANEL_AREA_H = 20
MIN_LABEL_W = layout.MIN_SIZE["Label"][0]  # минимум надписи платформы (`layout.MIN_SIZE`): 15
PLATFORM_MIN_FIELD_W = layout.MIN_SIZE["TextBox"][0]    # минимум поля ввода платформы: 11 — ниже заданная `width` отказ
# Высота НОВОГО флажка: конструктор ставит 15, а не 19 поля ввода (с 19 таблица под флажком получалась 51/52 вместо 55/56); оставленный флажок
# исходной формы высоту не меняет. Ширина флажка = текст по `textwidth` + `render.CHECK_CAPTION_PAD` (16).
FLAG_H = 15
MIN_FIELD_W = 100  # ниже — поле ввода не читается; не проверялось (ширину поля задаёт привязка к правому краю)
MIN_FORM_W = 400  # самая частая ширина формы элемента справочника — 400; у документа берётся та же
TABLE_CONTENT_H = 120  # высота таблицы «по содержимому»: однозначного значения нет, взято ближайшее круглое
TABLE_MIN_W = 100  # ниже таблица не читается (не проверялось)
# Минимум высоты растянутой таблицы при `size`: она берёт остаток высоты, но не меньше этого. Высота таблицы конструктора — остаток формы (55 и 56
# при шаге строк 25), а не константа; «шапка и две строки» (49, `layout.MIN_SIZE`) не правило платформы: в предприятии при 51/52 и при 55 видна ОДНА
# строка с прокруткой. Платформенный минимум 49 остаётся у `layout.MIN_SIZE` (растяжение окна).
TABLE_MIN_H = 55  # минимум высоты растянутой таблицы при `size`
TABLE_BAR_H = 24  # высота командной панели таблицы: конструктор ставит 24
TABLE_BAR_DEFAULT = True  # ключ `bar` блока `table` по умолчанию: панель, чей источник действий — эта таблица (так у большинства таблиц на ТЧ и у форм конструктора)
TABLE_BAR_NAME = "КоманднаяПанель"  # имя панели таблицы у конструктора — «КоманднаяПанель1»: основа и первый свободный номер

SHEET_CONTENT_H = 384  # поле табличного документа «по содержимому»: медиана форм вида processing — 384 (разброс 242…557)
SHEET_MIN_W = TABLE_MIN_W  # ниже поле табличного документа не читается (не проверялось)
SHEET = "SpreadsheetDocumentField"

# Стиль исходной формы имеет приоритет над стилем, общим для форм в конфигурациях. Если исходная форма содержит элементы того же рода, генерация берёт
# их стиль. Если таких элементов нет или стиль у них неоднороден, берётся то, что делает большинство форм в конфигурациях.
STYLE_MIN_PAIRS = 2  # колонка надписей у исходной формы есть, когда пар «надпись + поле» не меньше двух: одна пара колонки не показывает
STYLE_MAJORITY = fractions.Fraction(2, 3)  # явное большинство: доля не меньше двух третей; между третью и двумя третями явного большинства нет, и берётся стиль конструктора платформы
LABEL_COLON_VOICE = True  # двоеточие в подписи надписи пары, когда исходная форма надписей не содержит (или стиль у неё неоднороден): у справочника, обработки и документа так делает большинство
# Правая привязка НОВОГО поля выбирается по классу типа реквизита и виду формы. Решает большинство форм в конфигурациях, как и для норм
# `patterns.json`: каждая конфигурация учитывается один раз. В конфигурации класс считается растягивающимся, если растягивается строго больше половины его
# полей (при равенстве — не растягивается); повторы форм считаются один раз. Число конфигураций «за» и «против» оценивает `stretch_decision`:
# доля не меньше двух третей — класс растягивается, не больше трети — не растягивается; в промежутке, а также для класса из числа конфигураций
# меньше `STRETCH_THIN_CONFIGS` (то же число, что для `thin` в нормах) или с числом полей меньше `STRETCH_THIN_FIELDS` явного решения нет.
# Решения считаются по паре (вид формы, класс) в таком порядке: (1) решение по паре, если оно есть; (2) если по паре данных мало — решение по классу
# для всех видов (сводная строка `STRETCH_ALL`); (3) если и его нет — стиль конструктора платформы (`STRETCH_CONSTRUCTOR`); (4) если нет и его —
# поле растягивается. В выборке — все поля ввода, ПОСЛЕДНИЕ В СВОЁМ РЯДУ формы, где бы ни находился правый край: это кандидаты на растягивание, то
# есть поля, привязку которых выбирает движок (внутренние колонки не растягиваются никогда). Строки образуют ОДИН класс без порога по длине: единой
# границы между короткими и длинными строками нет.
STRETCH_THIN_CONFIGS = patterns.THIN_CONFIGS
STRETCH_THIN_FIELDS = 20  # класс тонкий и при малом числе полей: меньше 20 полей — решения нет
STRETCH_ALL = "*"  # сводная строка класса: оба вида формы вместе; используется, когда решения по паре нет
STRETCH_FORM_KINDS = {"catalog": "catalog.item", "document": "document.item"}  # вид объекта метаданных → вид формы таблицы (обработка и список в таблице не считаются)
STRETCH_VOTES = {  # (вид формы, класс) → (конфигураций за, против, полей всего); «за» — поле РАСТЯГИВАЕТСЯ (рост ширины `cR − cL` не меньше `layout.GROW_MIN`); стандартные реквизиты — свои классы по имени (длины в `metadata` нет)
    ("*", "catalog"): (3, 3, 436),
    ("*", "dateTime"): (0, 3, 42),
    ("*", "decimal"): (0, 6, 165),
    ("*", "document"): (0, 5, 23),
    ("*", "enum"): (2, 4, 40),
    ("*", "string"): (3, 3, 408),
    ("*", "Владелец"): (3, 1, 13),
    ("*", "Дата"): (0, 4, 90),
    ("*", "Код"): (0, 5, 95),
    ("*", "Наименование"): (4, 1, 91),
    ("*", "Номер"): (1, 3, 6),
    ("*", "Родитель"): (5, 0, 43),
    ("catalog.item", "catalog"): (4, 1, 122),
    ("catalog.item", "dateTime"): (0, 3, 18),
    ("catalog.item", "decimal"): (0, 5, 112),
    ("catalog.item", "document"): (1, 0, 7),
    ("catalog.item", "enum"): (3, 2, 22),
    ("catalog.item", "string"): (3, 1, 141),
    ("catalog.item", "Владелец"): (3, 1, 13),
    ("catalog.item", "Дата"): (0, 1, 1),
    ("catalog.item", "Код"): (0, 5, 95),
    ("catalog.item", "Наименование"): (4, 1, 91),
    ("catalog.item", "Номер"): (0, 1, 2),
    ("catalog.item", "Родитель"): (5, 0, 43),
    ("document.item", "catalog"): (0, 5, 314),
    ("document.item", "dateTime"): (0, 3, 24),
    ("document.item", "decimal"): (0, 3, 53),
    ("document.item", "document"): (0, 5, 16),
    ("document.item", "enum"): (0, 5, 18),
    ("document.item", "string"): (2, 4, 267),
    ("document.item", "Дата"): (0, 4, 89),
    ("document.item", "Номер"): (1, 2, 4)}
STRETCH_CONSTRUCTOR = {  # где решения нет — как конструктор
    "decimal": False,
    "dateTime": False,
    "Код": False,
    "Номер": False,
    "Дата": False}
STRETCH_STANDARD = ("Код", "Номер", "Дата", "Наименование", "Родитель", "Владелец")


def stretch_decision(pull, stay, fields):
    """Решение по числу конфигураций класса: `True` — растягивается (за ≥ 2/3), `False` — остаётся на месте (за ≤ 1/3), `None` — решения нет: конфигураций меньше
    `STRETCH_THIN_CONFIGS`, полей класса меньше `STRETCH_THIN_FIELDS` либо доля между третью и двумя третями. Точная дробь: граница не уходит в пыль float."""
    configs = pull + stay
    if configs < STRETCH_THIN_CONFIGS or fields < STRETCH_THIN_FIELDS:
        return None
    share = fractions.Fraction(pull, configs)
    if share >= STYLE_MAJORITY:
        return True
    return False if share <= 1 - STYLE_MAJORITY else None


def stretch_class(key, form_kind=None):
    """Растягивается ли поле класса `key` при растяжении окна в форме вида `form_kind` (`STRETCH_VOTES`; «растягивается» — рост ширины `cR − cL` не меньше
    `layout.GROW_MIN`, а не привязка правого края к форме): решение по паре (вид, класс); где пара тонкая или «между» — решение по классу по всем видам; где и его
    нет — конструктор; где нет и его — `None` (класса нет: растягивается). `form_kind` — `catalog.item`/`document.item`; иной или `None` (обработка, вид не
    назван) — сразу решение по классу. `False` — «не растягивается»: движок пишет привязку влево, поле не сдвигается. Не поддерживается поле, у которого сдвигаются обе границы
    (обе границы идут с краем формы): ширины такого нового поля движок не знает; «пропорционально» (пропорциональная шапка) — только стилем рядов ИСХОДНОЙ ФОРМЫ (`rowstyle`, `_Layout.row_anchors`),
    решением по классу — нет."""
    for kind in (form_kind, STRETCH_ALL) if form_kind in STRETCH_FORM_KINDS.values() else (STRETCH_ALL,):
        voted = stretch_decision(*STRETCH_VOTES[(kind, key)]) if (kind, key) in STRETCH_VOTES else None
        if voted is not None:
            return voted
    return STRETCH_CONSTRUCTOR.get(key)


SIZE_WAY_OUT = ("образец несёт `size` — размер формы платформы; добавили поля или блоки — снимите `size` (форма возьмёт размер по содержимому) "
                "или поднимите {side} до {need}")  # «добавили реквизит — сгенерировали заново» ломается на размере образца, выход назван в отказе
BAR_NAMES = dict(zip(("top", "bottom"), shell_mod.FORM_BAR_NAMES))      # имена панелей формы — у `shell` (одно место: им же `scan` отличает панель таблицы)

# Объявление нового реквизита формы (ключ `attributes` описания вида processing)
ATTR_KEYS = ("name", "type", "length", "fixed", "digits", "fraction", "nonnegative", "date")
ATTR_TYPES = ("string", "number", "date", "boolean")
PLATFORM_TYPES = valuesrc.NAMES      # ValueTable, ValueTree, ValueList: типы платформы без квалификаторов
DATE_PARTS = tuple(datatype.DATE_LETTERS)      # Date, Time, DateTime


# ── Нормы ─────────────────────────────────────────────────────────────────────────────────────

def norms_of(table, kind, bottom=False, top=False):
    """Меры вида из `patterns.json` (большинство форм в конфигурациях) словарём; нет вида, вид `thin` или нет показателя — отказ словами."""
    block = (table.get("kinds") or {}).get(kind)
    if not block:
        raise GenerateError(f"в нормах (patterns.json) нет вида «{kind}»; виды: {', '.join(sorted(table.get('kinds') or {}))}")
    if block.get("thin"):
        raise GenerateError(f"у вида «{kind}» норм нет: он из {block.get('configs')} конфигураций (меньше "
                            f"{patterns.THIN_CONFIGS}), и ритм одной-двух конфигураций нормой не служит")
    keys = NORM_KEYS + (TOP_BAR_KEYS if top else ()) + (BOTTOM_BAR_KEYS if bottom else ())
    out, missing = {}, []
    for key in keys:
        value = patterns.norm(table, kind, key)
        if value is None:
            missing.append(key)
        out[key] = value
    if missing:
        raise GenerateError(f"у вида «{kind}» нет нормы для {', '.join(missing)}: форму без них расставить нечем")
    out["label_column_width"] = patterns.norm(table, kind, "label_column_width")      # не обязательна: нужна только `align`
    out["multiline_height"] = multiline_height(table)      # не обязательна: нужна полю с `multi_line` без `height`
    check_pitch(out, kind)
    return out


def norms_kind(desc, obj=None):
    """Вид норм `patterns.json` для описания: у вида processing с объектом-отчётом — `report` (форма отчёта; объект выгрузки, а без него имя в описании),
    иначе вид описания."""
    if desc["kind"] != PROCESSING:
        return desc["kind"]
    if obj is not None:
        return REPORT_NORMS if obj.kind == "report" else PROCESSING
    return REPORT_NORMS if REPORT_PREFIX.match(str(desc.get("object", "")).strip()) else PROCESSING


def multiline_height(table):
    """Высота многострочного поля без названной `height`: самая частая высота полей не меньше двух строк по конфигурациям корпуса (общая строка
    `multiline_field_height` таблицы норм, у одного вида данных мало). Нормой вида она не служит: большинства среди форм нет (`lint`). Строки нет — `None`."""
    row = (table.get(patterns.SHARED) or {}).get("multiline_field_height")
    return row["by_config"][0][0] if row and row.get("by_config") else None


def check_pitch(norms, kind):
    """Шаг строк не меньше высоты поля (и после замены высоты по соседям — тоже)."""
    if norms["pair_pitch"] < norms["field_height"]:
        raise GenerateError(f"нормы вида «{kind}» противоречат друг другу: шаг строк {norms['pair_pitch']} меньше высоты "
                            f"поля {norms['field_height']}")


# ── Описание: проверка вида ───────────────────────────────────────────────────────────────────

def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _only(obj, allowed, where, problems):
    extra = sorted(set(obj) - set(allowed))
    if extra:
        problems.append(f"{where}: лишние ключи {', '.join(map(repr, extra))}; допустимы {', '.join(allowed)}")


def _strip_object(path):
    return path[len(datapath.OBJECT_WORD) + 1:] if path.startswith(datapath.OBJECT_WORD + ".") else path


# ── Модель, собранная из описания и метаданных ────────────────────────────────────────────────

@dataclasses.dataclass
class FieldSpec:
    name: str                    # реквизит или стандартный реквизит
    data: str                    # путь для `bind`: «Объект.Имя»
    control: str                 # TextBox | CheckBox
    choice: bool                 # кнопка выбора у поля ввода (ссылка, дата)
    text: str                    # подпись надписи (у флажка — сам заголовок)
    width: object = None
    height: object = None
    props: dict = None
    anchors: object = None
    font: object = None
    label_name: str = None
    field_name: str = None
    attribute: str = None        # у поля на реквизит ФОРМЫ (вид processing) — его имя; `data` тогда пуст
    shell: object = None  # `shell.ShellField` — поле исходной формы с теми же данными: остаётся, меняются место, размер, привязки и страница
    new_caption: str = None      # у переиспользованной надписи: подпись, названная описанием и отличная от стоящей в исходной форме
    tip: str = None  # подсказка нового поля реквизита объекта: конструктор пишет в неё синоним реквизита (стандартным реквизитам не пишет)
    stretch: object = None  # привязка правого края нового поля по классу типа: True — растягивается, False — нет, `None` — класс не назван (растягивается)
    date: str = None  # состав даты нового поля ввода на дату (`Date`, `Time`, `DateTime`); `None` — поле не на дату
    choice_list: list = None  # список выбора: поле ставится ПОЛЕМ ВЫБОРА (`change_type` в `ComboBox`, затем `choice_list`); `None` — поле ввода
    multi_line: bool = False  # многострочное поле ввода на строку: `set_property multi_line`; высота без `height` — норма многострочного поля (`MULTILINE_HEIGHT_KEY`)
    type_class: str = None  # класс значения реквизита (`kind_words`: `string`, `decimal`, …); `None` — стандартный реквизит или составной тип: ширина поля ряда — как у «прочих»


@dataclasses.dataclass
class Bar:
    where: str


@dataclasses.dataclass
class Fields:
    items: list
    columns: int = 1
    align: bool = False          # поля колонки начинаются в одном x (большинство форм в конфигурациях — не выравнивать: `field_x_aligned` 0)


@dataclasses.dataclass
class Group:
    title: str
    name: str
    blocks: list


@dataclasses.dataclass
class RadioSpec:
    name: str                    # имя рамки: Рамка<N>
    attribute: str               # реквизит формы: число, одно значение — выбранный переключатель
    title: str                   # заголовок рамки
    options: list                # [(подпись, значение, имя переключателя)]
    row: bool = False            # переключатели в ряд, а не столбиком
    font: object = None          # шрифт переключателей: по соседям, `_Layout.fonts["CheckBox"]`


@dataclasses.dataclass
class PictureSpec:
    name: str                    # имя поля картинки
    title: str = None            # заголовок рамки вокруг поля; `None` — без рамки (граница у самого поля)
    size: tuple = (0, 0)         # ширина и высота поля
    right: bool = False          # прижато к правому краю колонки, привязка вправо
    frame_name: str = None


@dataclasses.dataclass
class ButtonSpec:
    caption: str                 # подпись кнопки своей команды
    name: str                    # имя кнопки на форме (умолчание — подпись без знаков вне идентификатора)
    width: object = None         # ширина: названная либо по подписи


@dataclasses.dataclass
class Row:
    items: list                  # [FieldSpec | ButtonSpec] слева направо: пара «надпись + поле», флажок или кнопка
    stretch: object = None       # поле ряда, берущее остаток ширины (привязка «растягивать»); `None` — ряд не растягивается


@dataclasses.dataclass
class Beside:
    left: list                   # блоки шапки слева (ширина фиксирована, привязки влево)
    right: object                # блок справа: рамка, переключатели или поле картинки (привязки вправо)
    width: object = None         # ширина блока справа не меньше названной


@dataclasses.dataclass
class Split:
    axis: str                    # `left_right` (вертикальный разделитель) | `top_bottom` (горизонтальный)
    first: list                  # блоки левой (верхней) части
    second: list                 # блоки правой (нижней) части
    size: object = None          # ширина (высота) первой части; `None` — по содержимому
    grows: str = "both"          # какая часть берёт прирост окна по оси разделителя: first | second | both


@dataclasses.dataclass
class Tabs:
    name: str
    pages: list                  # [(заголовок, имя страницы, [блоки])]


@dataclasses.dataclass
class TableSpec:
    name: str
    data: str                    # «Объект.ТЧ»
    ts: object                   # metadata.Table
    columns: list                # [(имя колонки, заголовок, путь данных, образец колонки)]
    bar: bool = True             # командная панель над таблицей (ключ `bar`, умолчание `TABLE_BAR_DEFAULT`)
    shell: object = None         # `shell.ShellTable` исходной формы — таблица остаётся (колонки добавляются и убираются), когда состав и порядок колонок позволяют
    bar_name: str = None
    keep: list = None            # у переиспользованной: ключи колонок исходной формы, которые остаются
    drop: list = None            # у переиспользованной: имена колонок исходной формы, которых в описании нет
    add: list = None             # у переиспользованной: колонки описания, которых в исходной форме нет (дописываются в конец)
    bar_kept: bool = False       # панель таблицы — панель исходной формы (остаётся); иначе новая, и источник действий ей ставит `set_action_source`
    form_attr: str = None        # таблица на реквизит ФОРМЫ (`source: form`): имя реквизита типа ValueTable либо ValueTree; `ts` тогда `None`, колонки — словари `valuesrc`
    tree: bool = False           # у таблицы на реквизит формы: дерево значений


@dataclasses.dataclass
class SheetSpec:
    name: str                    # имя поля табличного документа (без привязки к данным)


IDENT = re.compile(r"^[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё_0-9]*$")      # имя реквизита и поля табличного документа: идентификатор 1С


def _identifier(text):
    """Имя элемента из подписи: знаки вне букв, цифр и подчёркивания выброшены (`Смена` + `Дневная, до 18:00` → `СменаДневнаяДо1800`); начинается не с цифры — иначе
    добавляется подчёркивание."""
    name = re.sub(r"[^A-Za-zА-Яа-яЁё_0-9]", "", text)
    return name if IDENT.match(name) else "_" + name


class FormAttributes:
    """Реквизиты ФОРМЫ обработки: строки исходной формы и объявленные описанием (`attributes`).

    Тип реквизита формы — описатель `Pattern` (буква `S`/`N`/`D`/`B`/`#`, квалификаторы), а не метаданные; здесь он сведён к `metadata.Attr` с теми же
    полями, чтобы вид элемента решал тот же `_Resolver.control_of`, что у реквизита объекта. `#` — ссылка: справочник или документ ВЫГРУЗКИ узнаются по GUID
    (`Config.object_by_type_id`, категория `Ref`); прочий GUID (перечисление, тип платформы — таблица значений, список значений) вида элемента не
    получает — отказ словами. Описатель из нескольких блоков — составной тип, пустой — произвольный: поле на них не ставится."""

    def __init__(self, form_doc, config=None):
        self.config = config
        self.rows, self.main, self.declared = {}, None, {}
        try:
            attributes, rows = datapath._attributes(form_doc)
        except ed_base.EditError as e:
            raise GenerateError(f"реквизиты исходной формы не разобраны: {e}") from None
        head = attributes.get(ATTR_HEAD)
        main_id = head.get(datapath.MAIN_ATTRIBUTE_ID) if isinstance(head, dict) else None
        self.short = datapath.short_rows_words(rows) if datapath.short_attribute_rows(rows) else None
        for row in rows:
            name = row.get(ATTR_NAME)
            if not isinstance(name, str):
                continue
            ident = datapath._id_of(row)
            self.rows[name] = row
            if ident is not None and ident == main_id:
                self.main = name

    def names(self):
        return [n for n in list(self.rows) + list(self.declared) if n != self.main]

    def platform_kind(self, name):
        """`ValueTable`, `ValueTree` либо `ValueList`, если реквизит формы `name` — единственный блок такого типа (объявленный описанием или строка формы); иначе `None`."""
        if name in self.declared:
            block = self.declared[name][1]
            return block.get("value_type") if isinstance(block, dict) and block.get("value_type") in PLATFORM_TYPES else None
        return valuesrc.attribute_source(self.rows.get(name))

    def types_of(self, name):
        pattern = self.rows[name].get(ATTR_PATTERN)
        types = pattern.get(PATTERN_TYPES) if isinstance(pattern, dict) else None
        return types if isinstance(types, list) else []

    def attr(self, name):
        """Реквизит формы `name` как `metadata.Attr` либо `GenerateError` словами (нет такого, основной, тип без вида элемента)."""
        if name == self.main:
            raise GenerateError(f"«{name}» — основной реквизит формы (объект обработки): поля на реквизиты обработки — "
                                "source: object, а не form")
        kind = self.platform_kind(name)
        if kind is not None:
            raise GenerateError(f"реквизит формы «{name}» — {kind}: поле ввода на него не ставится. "
                                + ("Таблицу и дерево значений показывает блок table с \"source\": \"form\"" if kind != valuesrc.VALUE_LIST
                                   else "Список значений показывает поле списка (`add_element` с `template` ListBox и `bind` в `tune`/правке), генерация его не ставит"))
        if name in self.declared:
            return self.declared[name][0]
        if name not in self.rows:
            if self.short:
                raise GenerateError(f"реквизит формы «{name}» не найден: {self.short}")
            known = ", ".join(self.names()) or "нет"
            raise GenerateError(f"у формы нет реквизита «{name}»; реквизиты формы: {known}; новый — в ключе attributes описания")
        return self._attr_of(name, self.types_of(name))

    def _ref_name(self, name, guid):
        hit = self.config.object_by_type_id(guid) if self.config is not None and guid else None
        if hit and hit[1].lower() == "ref" and hit[0].kind in ("catalog", "document"):
            return f"cfg:{'CatalogRef' if hit[0].kind == 'catalog' else 'DocumentRef'}.{hit[0].name}"
        why = "выгрузки нет" if self.config is None else "это не справочник и не документ выгрузки"
        raise GenerateError(f"реквизит формы «{name}»: ссылочный тип {guid or 'без GUID'} — {why} (перечисление или тип платформы: "
                            "таблица значений, список значений…); вид элемента для него в константах движка не назван")

    def _attr_of(self, name, types):
        if not types:
            raise GenerateError(f"реквизит формы «{name}» произвольного типа (описатель пуст): вид элемента для него в константах движка не назван")
        if len(types) > 1:
            # составной тип у реквизита ФОРМЫ: поле берёт тип `bind(copy_type)` — одиночным блоком (`block_mirror`); порядок блоков составного известен только для реквизитов объекта (`edit.datatype.composite_order`), чужой составной описатель в поле формы не переносится
            raise GenerateError(f"реквизит формы «{name}»: составной тип ({len(types)} блоков описателя): поле на реквизит формы берёт одиночный блок "
                                "(`copy_type`: S, N, D, #), составной описатель реквизита формы вида элемента не получает")
        names, q = [], {}
        for block in types:
            if not isinstance(block, dict):
                raise GenerateError(f"реквизит формы «{name}»: описатель типа устроен не так, как у платформы (блок — не запись): "
                                    "правленый руками документ?")
            letter = block.get(PATTERN_KIND)
            if letter == "S":
                names.append("xs:string")
                q["string_length"] = block.get(PATTERN_LENGTH)
                q["allowed_length"] = {1: "Variable", 0: "Fixed"}.get(block.get(STRING_ALLOWED))
            elif letter == "N":
                if any(block.get(k) is None for k in PATTERN_NUMBER):
                    raise GenerateError(f"реквизит формы «{name}»: число без квалификаторов в описателе (разрядность, дробная часть, знак) — "
                                        "зеркало в поле писать нечем")
                names.append("xs:decimal")
                q.update(digits=block.get(PATTERN_NUMBER[0]), fraction=block.get(PATTERN_NUMBER[1]),
                         allowed_sign="Nonnegative" if block.get(PATTERN_NUMBER[2]) else "Any")
            elif letter == "D":
                names.append("xs:dateTime")
            elif letter == "B":
                names.append("xs:boolean")
            else:  # «#»: других букв карта не знает (`schema.FORKS["PatternType"]` — S, N, D, B, #)
                ref = block.get(datatype.TYPE_GUID)
                guid = schema.type_guid(ref)
                names.append(self._ref_name(name, guid) if len(types) == 1 else f"#{guid}")
        return metadata.Attr(name, "", tuple(names), (), q.get("string_length"), q.get("allowed_length"), q.get("digits"),
                             q.get("fraction"), q.get("allowed_sign"), None, None, name)

    def declare(self, entries, where, problems):
        """Объявленные реквизиты (`attributes` описания) → операции `add_attribute`; проблемы копятся, а не бросаются."""
        ops = []
        if not isinstance(entries, list) or not entries:
            problems.append(f"{where}: attributes — непустой массив реквизитов {{\"name\", \"type\", …}}")
            return ops
        for at, entry in enumerate(entries):
            here = f"{where}/{at}"
            if not isinstance(entry, dict) or not isinstance(entry.get("name"), str) or not isinstance(entry.get("type"), str):
                problems.append(f"{here}: реквизит — объект с name и type (строки), а пришло {entry!r}")
                continue
            name, kind = entry["name"].strip(), entry["type"].strip()
            if not IDENT.match(name) or name == datapath.OBJECT_WORD:
                problems.append(f"{here}: имя «{name}» — идентификатор 1С (буквы, цифры, подчёркивание; не с цифры) и не "
                                f"«{datapath.OBJECT_WORD}»")
                continue
            if name in self.rows or name in self.declared:
                problems.append(f"{here}: реквизит «{name}» у формы уже есть (исходная форма или повтор в attributes): заводить второй "
                                "нечем — привязывайте поле к имеющемуся (source: form)")
                continue
            made = self._declared(entry, name, kind, here, problems)
            if made is None:
                continue
            self.declared[name] = made
            ops.append({"op": "add_attribute", "name": name, "pattern": {"mark": "Pattern", "types": [copy.deepcopy(made[1])]}})
        return ops

    def _declared(self, entry, name, kind, where, problems):
        if "fraction_digits" in entry:     # синоним `fraction` (так ключ зовётся в описателе типа и у колонок): одно имя в записи
            if "fraction" in entry and entry["fraction"] != entry["fraction_digits"]:
                problems.append(f"{where}: знаки после запятой названы дважды разно: fraction ({entry['fraction']!r}) и fraction_digits "
                                f"({entry['fraction_digits']!r}) — оставьте один ключ")
                return None
            entry = {**{k: v for k, v in entry.items() if k != "fraction_digits"}, "fraction": entry["fraction_digits"]}
        own = {"string": {"length", "fixed"}, "number": {"digits", "fraction", "nonnegative"}, "date": {"date", "date_fractions"}}
        ref = kind.partition(".")[0] in ("Справочник", "Документ") and "." in kind
        if kind not in ATTR_TYPES and kind not in PLATFORM_TYPES and not ref:
            problems.append(f"{where}: type — {', '.join(ATTR_TYPES + PLATFORM_TYPES)} либо «Справочник.Имя»/«Документ.Имя» (ссылка на объект выгрузки), "
                            f"а пришло {kind!r}")
            return None
        stray = sorted(set(entry) - ({"name", "type"} | own.get(kind, set())))
        if stray:
            problems.append(f"{where}: к типу «{kind}» не относятся ключи {', '.join(map(repr, stray))}")
            return None
        for key in ("length", "digits", "fraction"):
            value = entry.get(key)
            if value is not None and not (_is_int(value) and value >= (0 if key == "fraction" else 1)):
                problems.append(f"{where}: {key} — целое {'неотрицательное' if key == 'fraction' else 'положительное'}, "
                                f"а пришло {value!r}")
                return None
        for key in ("fixed", "nonnegative"):
            if key in entry and not isinstance(entry[key], bool):
                problems.append(f"{where}: {key} — true или false, а пришло {entry[key]!r}")
                return None
        if kind in PLATFORM_TYPES:     # тип платформы без квалификаторов: таблица, дерево или список значений
            return metadata.Attr(name, "", (f"platform:{kind}",), synonym=name), {PATTERN_KIND: "#", "value_type": kind}
        if kind == "string":
            if entry.get("fixed") and not entry.get("length"):
                problems.append(f"{where}: fixed — у строки с длиной (length): строка без длины неограниченная")
                return None
            attr = metadata.Attr(name, "", ("xs:string",), (), entry.get("length"),
                                 ("Fixed" if entry.get("fixed") else "Variable") if entry.get("length") else None, synonym=name)
        elif kind == "number":
            if entry.get("digits") is None or entry.get("fraction") is None:
                problems.append(f"{where}: у числа назовите digits (разрядность) и fraction (знаков после запятой): догадываться нельзя")
                return None
            if entry["fraction"] > entry["digits"]:
                problems.append(f"{where}: fraction {entry['fraction']} больше разрядности digits {entry['digits']}")
                return None
            attr = metadata.Attr(name, "", ("xs:decimal",), (), None, None, entry["digits"], entry["fraction"],
                                 "Nonnegative" if entry.get("nonnegative") else "Any", synonym=name)
        elif kind == "date":
            try:
                part = datatype.date_part(entry)          # один разбор состава даты с колонками таблицы значений и описателем реквизита
            except ed_base.EditError as e:
                problems.append(f"{where}: {e}")
                return None
            if part is None:
                problems.append(f"{where}: у даты назовите date — {', '.join(DATE_PARTS)} (либо date_fractions: D — дата, T — время), а пришло {entry.get('date')!r}")
                return None
            attr = metadata.Attr(name, "", ("xs:dateTime",), date_fractions=part, synonym=name)
        elif kind == "boolean":
            attr = metadata.Attr(name, "", ("xs:boolean",), synonym=name)
        else:
            if self.config is None:
                problems.append(f"{where}: ссылка «{kind}» — тип объекта выгрузки, а выгрузки нет (--config)")
                return None
            prefix, _dot, rest = kind.partition(".")
            attr = metadata.Attr(name, "", (f"cfg:{'CatalogRef' if prefix == 'Справочник' else 'DocumentRef'}.{rest}",), synonym=name)
        try:
            block, _mirror, _cls = datatype.pattern_block(attr, self.config)
        except datatype.TypeNotWritten as e:
            problems.append(f"{where}: {e}")
            return None
        return attr, block


@dataclasses.dataclass
class ShellStyle:
    """Стиль исходной формы: что у неё одно и то же у однородных элементов — колонка надписей пар, двоеточие в подписях, флажки во всю строку."""
    label_w: int = None              # ширина колонки надписей: у всех пар исходной формы одна, а поля пар стоят с одного x; `None` — разнобой, пар меньше двух или исходной формы нет
    label_gap: int = None            # зазор «надпись → поле» колонки исходной формы (у неё один у всех пар); `None` — колонки нет
    colon: bool = LABEL_COLON_VOICE  # двоеточие в подписи надписи новых полей
    colon_from: str = "корпус"       # откуда двоеточие: «исходная форма» либо «корпус»
    pairs: int = 0                   # сколько пар «надпись + поле» нашлось у исходной формы
    flag_rights: tuple = ()          # правые края флажков исходной формы
    form_width: int = None
    row_style: str = None  # вид, которым записаны ряды полей исходной формы в несколько колонок (`rowstyle.style_of`): `prop_pos`, `split` либо `None` — стиля рядов нет
    row_votes: tuple = (0, 0)        # рядов этого вида и рядов из двух и больше полей у исходной формы всего (для отчёта)
    field_right: int = None          # правый край «строки» исходной формы — до него идут её флажки: ширина формы минус правый отступ ТЯНУЩИХСЯ полей ввода (коэффициент 1);
                                     # `None` — тянущихся полей ввода у исходной формы нет

    def flags_full(self, margin):
        """Флажки исходной формы идут во всю строку колонки — все и их не меньше одного. Край строки — по тянущимся полям ввода ИСХОДНОЙ ФОРМЫ (сверка с исходной формой, а
        не с нормой вида); тянущихся полей у неё нет — ширина формы минус отступ `margin` нормы вида."""
        if not self.flag_rights:
            return False
        edge = self.field_right if self.field_right is not None else (self.form_width - margin if self.form_width is not None else None)
        return edge is not None and all(r == edge for r in self.flag_rights)


def shell_style(shell):
    """Стиль исходной формы по её полям (`shell.Shell`); исходной формы нет (`None`) или полей нет — большинство форм корпуса (пустой стиль)."""
    style = ShellStyle()
    if shell is None:
        return style
    fields = list(shell.fields.values())
    pairs = [f for f in fields if f.type == "TextBox" and f.label is not None and f.box is not None]
    style.pairs = len(pairs)
    if len(pairs) >= STYLE_MIN_PAIRS:
        widths = {f.label.box[2] - f.label.box[0] for f in pairs}
        starts = {f.box[0] for f in pairs}
        lefts = {f.label.box[0] for f in pairs}
        if len(widths) == 1 and len(starts) == 1 and len(lefts) == 1:
            gap = min(starts) - (min(lefts) + min(widths))
            if gap >= 0:                         # поле не наползает на надпись
                style.label_w, style.label_gap = min(widths), gap
    captions = [shell_mod.caption_of(f.label.node) for f in pairs]
    captions = [c for c in captions if c]
    if captions:
        share = fractions.Fraction(sum(1 for c in captions if c.rstrip().endswith(":")), len(captions))      # точная дробь: граница в две трети и треть — не пыль float
        if share >= STYLE_MAJORITY:
            style.colon, style.colon_from = True, "исходная форма"
        elif share <= 1 - STYLE_MAJORITY:
            style.colon, style.colon_from = False, "исходная форма"
    style.flag_rights = tuple(f.box[2] for f in fields if f.type == "CheckBox" and f.box is not None)
    margins = collections.Counter(shell.form_width - f.box[2] for f in fields
                                  if f.type == "TextBox" and f.box is not None and f.behaviour == layout.GROWS and shell.form_width is not None)
    if margins:      # отступ, что встретился чаще всех; при равенстве — больший (край строки левее: флажок не вылезает за самое узкое поле)
        style.field_right = shell.form_width - max(margins.items(), key=lambda kv: (kv[1], kv[0]))[0]
    style.form_width = shell.form_width
    rowed = [{"box": f.box, "cl": f.left_coef, "cr": f.right_coef} for f in fields if f.type == "TextBox" and f.box is not None]
    kind, rows, total = rowstyle.style_of(rowed, shell.form_width, STYLE_MAJORITY)
    style.row_style, style.row_votes = kind, (rows, total)
    return style


def style_note(style, margin, widths=()):
    """Слова для отчёта: что взято у исходной формы, а что — у корпуса. `widths` — ширины колонки, какие легли в форму."""
    if style.label_w is not None:
        stands = sorted(widths)
        if not stands:
            column = (f"у исходной формы колонка надписей {style.label_w} px, зазор {style.label_gap}, но в этой форме она не применена (явный `align: false` снимает её целиком — "
                      "и ширину, и зазор — либо блоков с парами нет): надписи по тексту подписи, зазор — норма вида")
        else:
            shown = (f"{stands[0]} px" if stands == [style.label_w] else
                     f"{', '.join(str(w) for w in stands)} px (у исходной формы {style.label_w}; раздвинута самой длинной НОВОЙ подписью по `textwidth`)")
            column = f"колонка надписей {shown}, зазор до поля {style.label_gap} (пар у исходной формы {style.pairs}, поля с одного x) — `align` по умолчанию истина"
    elif style.pairs:
        column = f"надписи пар у исходной формы разной ширины, а поля не с одного x или пар меньше {STYLE_MIN_PAIRS} (пар {style.pairs}) — надписи по тексту подписи (большинство форм корпуса)"
    else:
        column = "надписей пар у исходной формы нет — надписи по тексту подписи (большинство форм корпуса)"
    flags = (f"флажки исходной формы {'во всю строку колонки' if style.flags_full(margin) else 'по тексту'}" if style.flag_rights else "флажков у исходной формы нет — по тексту")
    return (f"стиль исходной формы имеет приоритет: {column}; двоеточие в подписях новых надписей — {'есть' if style.colon else 'нет'} ({style.colon_from}); {flags}; "
            f"{row_style_note(style)}; "
            "правая привязка поля: у оставленного своя, пока колонка та же, у нового — по классу типа (корпус)")


ROW_STYLE_WORDS = {"prop_pos": "каждая граница надписи и поля — долей своего положения (роль `proportional`)",
                   "split": "шапка колонок: левая граница первого поля остаётся на месте, правая — долей, следующее идёт за соседом слева, последнее — до края формы"}


def row_style_note(style):
    """Слова про ряды в несколько колонок: какой стиль у исходной формы и пишется ли им."""
    rows, total = style.row_votes
    if style.row_style is None:
        return ("ряды в несколько колонок — как прежде (стиля рядов у исходной формы нет"
                + (f": {rows} из {total} рядов одного вида — меньше двух третей или двух рядов)" if total else ": рядов из двух и больше полей нет)"))
    return (f"ряды в несколько колонок — стилем исходной формы «{style.row_style}» ({rows} из {total} её рядов): {ROW_STYLE_WORDS[style.row_style]}; "
            "полный ряд из пар «надпись + поле» без названной ширины и привязок — им, прочие — решением по классу")


class _Resolver:
    """Описание + метаданные → блоки модели; все отказы копятся и называются разом.

    Вид `processing`: `form` — реквизиты формы (`FormAttributes`), `obj` — обработка выгрузки либо `None` (данных объекта нет: поле `source: object` и
    таблица на табличную часть отказывают)."""

    def __init__(self, obj, role, config=None, form=None, shell=None):
        self.obj, self.role, self.config, self.form = obj, role, config, form
        self.shell = shell  # `shell.Shell` исходной формы: поля, таблицы и колонки для переиспользования; `None` — исходной формы нет; рядом — стиль исходной формы
        self.style = shell_style(shell)
        self.processing = form is not None
        self.problems = []
        self.notes = []              # слова для отчёта: что пропущено и почему (булева колонка «всех реквизитов»)
        self.data = {}               # путь данных → где использован
        self.counters = {"Рамка": 0, "Панель": 0}
        self.declare_ops = []        # `add_attribute` реквизитов, которые завёл сам блок (переключатели: число с цифрами по значениям)
        self.tables = []
        self.sheets = []
        self.no_object = "объект не назван"          # причина «объекта нет» для processing (ставит plan_notes)

    def use(self, data, where):
        if data in self.data:
            self.problems.append(f"«{data}» в описании дважды ({self.data[data]} и {where}): одному реквизиту — одно поле")
        else:
            self.data[data] = where

    # блоки
    def blocks(self, blocks, where, allowed):
        out = []
        if not isinstance(blocks, list) or not blocks:
            self.problems.append(f"{where}: блоки — непустой массив")
            return out
        for at, block in enumerate(blocks):
            here = f"{where}/{at}"
            if not isinstance(block, dict):
                self.problems.append(f"{here}: блок — объект с одним из ключей {', '.join(BLOCKS)}, а пришло {block!r}")
                continue
            kinds = [k for k in BLOCKS if k in block]
            if len(kinds) != 1:
                self.problems.append(f"{here}: в блоке ровно один из ключей {', '.join(BLOCKS)}, а есть: "
                                     f"{', '.join(sorted(block)) or 'ни одного'}")
                continue
            kind = kinds[0]
            if kind not in allowed:
                self.problems.append(f"{here}: блок «{kind}» здесь не бывает; бывают {', '.join(allowed)}")
                continue
            made = getattr(self, f"_{kind}")(block, here)
            if made is not None:
                out.append(made)
        return out

    def _command_bar(self, block, where):
        _only(block, ("command_bar",), where, self.problems)
        place = block["command_bar"]
        if place not in BAR_PLACES:
            self.problems.append(f"{where}: command_bar — {' или '.join(map(repr, BAR_PLACES))}, а пришло {place!r}")
            return None
        return Bar(place)

    def _fields(self, block, where):
        _only(block, FIELDS_KEYS, where, self.problems)
        align = block.get("align")          # не названо — по исходной форме (одна колонка надписей — выравнивать), иначе большинство форм корпуса: не выравнивать
        if align is None:
            align = self.style.label_w is not None
        elif not isinstance(align, bool):
            self.problems.append(f"{where}: align — true или false (выровнять поля колонки в один x), а пришло {align!r}")
            align = False
        columns = block.get("columns", 1)
        if not _is_int(columns) or not 1 <= columns <= MAX_COLUMNS:
            self.problems.append(f"{where}: columns — целое от 1 до {MAX_COLUMNS}, а пришло {columns!r}")
            columns = 1
        raw = block["fields"]
        if not isinstance(raw, list) or not raw:
            self.problems.append(f"{where}: fields — непустой массив реквизитов")
            return None
        items = []
        for at, entry in enumerate(raw):
            item = self._field(entry, f"{where}/fields/{at}")
            if item is not None:
                items.append(item)
        return Fields(items, columns, align)

    def _field(self, entry, where):
        if isinstance(entry, str):
            entry = {"data": entry}
        if not isinstance(entry, dict) or not isinstance(entry.get("data"), str) or not entry["data"].strip():
            self.problems.append(f"{where}: поле — имя реквизита строкой либо объект с ключом data, а пришло {entry!r}")
            return None
        _only(entry, FIELD_KEYS, where, self.problems)
        source = entry.get("source", "object")
        if source not in FIELD_SOURCES:
            self.problems.append(f"{where}: source — {' или '.join(map(repr, FIELD_SOURCES))}, а пришло {source!r}")
            return None
        attribute = None
        if source == "form":
            if not self.processing:
                self.problems.append(f"{where}: «{entry['data'].strip()}» — реквизит ФОРМЫ (source: form): форма объекта привязывает поля к "
                                     "реквизитам объекта, а привязка к реквизитам формы — вид processing")
                return None
            name = attribute = entry["data"].strip()
            try:
                target = datapath.Target("formattr", name, {}, self.form.attr(name))
            except GenerateError as e:
                self.problems.append(f"{where}: {e}")
                return None
            data = None
            self.use(f"форма.{name}", where)
        else:
            if self.obj is None:
                self.problems.append(f"{where}: «{entry['data'].strip()}» — реквизит ОБЪЕКТА (source: object), а объекта обработки у формы "
                                     f"нет: {self.no_object}. Данные формы без объекта — реквизиты формы: {{\"data\": …, \"source\": \"form\"}}"
                                     + (f" ({', '.join(self.form.names()) or 'у оболочки их нет'})" if self.form else ""))
                return None
            name = _strip_object(entry["data"].strip())
            try:
                target = datapath.resolve(self.obj, name, self.role)
            except ed_base.EditError as e:
                self.problems.append(f"{where}: {e}")
                return None
            if target.kind == "table":
                self.problems.append(f"{where}: «{name}» — табличная часть; её показывает блок table, а не поле")
                return None
            data = f"{datapath.OBJECT_WORD}.{name}"
            self.use(data, where)
        try:
            control, choice = self.control_of(target)
        except GenerateError as e:
            self.problems.append(f"{where}: {e}")
            return None
        reason = self.type_problem(target, control)
        if reason:
            self.problems.append(f"{where}: {reason}")
            return None
        want = entry.get("control")
        if want is not None and want != control:
            self.problems.append(f"{where}: control {want!r}, а для «{name}» нормы дают {control} "
                                 f"(допустимы значения: {', '.join(CONTROLS)}; тип привязанного поля следует за реквизитом)")
            return None
        for key in ("width", "height"):
            value = entry.get(key)
            if value is not None and (not _is_int(value) or value <= 0):
                self.problems.append(f"{where}: {key} — целое положительное число пикселей, а пришло {value!r}")
        width = entry.get("width")
        if _is_int(width) and 0 < width < PLATFORM_MIN_FIELD_W:
            self.problems.append(f"{where}: width {width} меньше минимума поля ввода платформы ({PLATFORM_MIN_FIELD_W}): "
                                 "платформа такое поле не сожмёт, а надписи рядом оно не оставит места")
        for key, kind in (("props", dict), ("font", dict)):
            if entry.get(key) is not None and not isinstance(entry[key], kind):
                self.problems.append(f"{where}: {key} — объект, а пришло {entry[key]!r}")
        if entry.get("anchors") is not None and not (isinstance(entry["anchors"], dict) and entry["anchors"]
                                                    and set(entry["anchors"]) <= {"h", "v"}):
            self.problems.append(f"{where}: anchors — объект {{\"h\": …, \"v\": …}}, а пришло {entry['anchors']!r}")
        if entry.get("caption") is not None and not isinstance(entry["caption"], str):
            self.problems.append(f"{where}: caption — строка, а пришло {entry['caption']!r}")
        explicit = entry.get("caption") if isinstance(entry.get("caption"), str) else None
        text = explicit if explicit is not None else self.text_of(target)
        if explicit is None and control == "TextBox" and self.style.colon and not text.rstrip().endswith(":"):
            text += ":"  # подпись надписи пары — с двоеточием, как у исходной формы (или у корпуса, когда надписей у исходной формы нет)
        kind_words = self.kind_words(target, control)
        choice_list, multi_line = self.choice_list_of(entry, where, name, kind_words), self.multi_line_of(entry, where, name, kind_words)
        if choice_list is not None and multi_line:
            self.problems.append(f"{where}: choice_list и multi_line вместе: поле выбора со списком в одну строку, а многострочное — поле ввода без списка; "
                                 "оставьте одно из двух")
            return None
        spec = FieldSpec(name, data, control, choice, text, entry.get("width"), entry.get("height"),
                         entry.get("props"), entry.get("anchors"), entry.get("font"), attribute=attribute)
        spec.choice_list, spec.multi_line = choice_list, multi_line
        spec.stretch = self.stretch_of(target, control, self.stretch_kind())
        spec.date = self.date_of(target, control)
        spec.type_class = kind_words[0]
        spec.field_name = name           # правило конструктора: поле и флажок названы именем реквизита (занято — суффикс, `_assign_names`)
        if target.kind == "attribute":
            # подсказка поля = синоним реквизита; пустой синоним подсказки не получает (что платформа пишет в таком случае, не проверялось)
            spec.tip = target.thing.synonym or None
        if control == "TextBox":
            spec.label_name = f"Надпись{name}"
        self._reuse(spec, target, control, explicit, ("form" if attribute else "object", name))
        return spec

    @staticmethod
    def kind_words(target, control):
        """Класс значения поля для ключей `choice_list` и `multi_line`: `(класс типа либо None, как назвать реквизит в отказе)`. Класс — `datatype.type_class`
        (`string`, `decimal`, `dateTime`, `boolean`, ссылочный); у стандартного реквизита и составного типа класса нет."""
        if control == "CheckBox":
            return "boolean", "булев реквизит (флажок)"
        if target.kind == "standard":
            return None, "стандартный реквизит"
        try:
            cls = datatype.type_class(target.thing)
        except datatype.TypeNotWritten:
            return None, "реквизит составного или невыразимого типа"
        return cls, ("реквизит типа «" + datatype.CLASS_WORDS[cls] + "»") if cls in datatype.CLASS_WORDS else "реквизит ссылочного типа"

    def choice_list_of(self, entry, where, name, kind_words):
        """Ключ `choice_list` поля: список строк (скаляр или `{"value", "presentation"}`) — поле выбора на строку или число. Правило строк — то же, что у
        `set_property choice_list` (`edit.rowsa.check_rows`); вид значения обязан совпасть с типом реквизита (строки — у строки, целые — у числа). Булев,
        дата, ссылка, стандартный реквизит и составной тип — отказ: поле выбора на них не проверялось, список выбора ссылки — другая запись."""
        if "choice_list" not in entry:
            return None
        value = entry["choice_list"]
        cls, said = kind_words
        if cls not in ("string", "decimal"):
            self.problems.append(f"{where}: choice_list у «{name}» — {said}: список выбора ставится полю выбора на СТРОКУ или ЧИСЛО (поле выбора на "
                                 "булево, дату и ссылку генерация не ставит; ссылку выбирают кнопкой выбора, а не списком)")
            return None
        if not isinstance(value, list) or not value:
            self.problems.append(f"{where}: choice_list — непустой массив значений (строка, целое либо {{\"value\": …, \"presentation\": …}}), "
                                 f"а пришло {value!r}")
            return None
        try:
            kinds = ed_rowsa.check_rows(value, name)
        except ed_base.EditError as e:
            self.problems.append(f"{where}: {e}")
            return None
        want = "S" if cls == "string" else "N"
        if any(k != want for k in kinds):
            self.problems.append(f"{where}: choice_list у «{name}» ({said}): значения списка — {'строки' if want == 'S' else 'целые числа'}, а в списке есть "
                                 "значения другого вида: вид значения строки списка обязан совпасть с типом реквизита")
            return None
        return copy.deepcopy(value)

    def multi_line_of(self, entry, where, name, kind_words):
        """Ключ `multi_line` поля: многострочное поле ввода — только у реквизита-строки (число, дата, ссылка в несколько строк не показываются)."""
        if "multi_line" not in entry:
            return False
        value = entry["multi_line"]
        if not isinstance(value, bool):
            self.problems.append(f"{where}: multi_line — true или false (многострочное поле ввода), а пришло {value!r}")
            return False
        cls, said = kind_words
        if value and cls != "string":
            self.problems.append(f"{where}: multi_line у «{name}» — {said}: многострочным бывает поле ввода на СТРОКУ")
            return False
        return value

    def _reuse(self, spec, target, control, explicit, key):
        """Поле исходной формы с теми же данными остаётся (`ShellField`): его имя и имя его надписи берутся из исходной формы, а подпись надписи остаётся исходной формы,
        пока описание не назвало другую (`caption`, отличную от стоящей). Не переиспользуется (и называется в заметках) поле другого вида элемента, чем ставит
        описание, и поле, чей тип не тот, что у реквизита (его описатель типа правит только `bind` нового поля)."""
        found = self.shell.fields.get(key) if self.shell is not None else None
        if found is None:
            inside = self.shell.nested.get(key) if self.shell is not None else None
            if inside is not None:
                self.notes.append(f"«{inside[0]}» (данные «{key[1]}») лежит в «{inside[1]}» исходной формы — внутри панели или рамки поля не "
                                  "переиспользуются: создан заново (обработчики прежнего остаются в модуле без элемента)")
            return
        if found.type != control:
            self.notes.append(f"«{found.name}» исходной формы — {found.type}, а реквизит «{key[1]}» описание ставит как {control}: поле исходной формы не "
                              "переиспользовано, элемент создан заново (обработчики прежнего остаются в модуле без элемента)")
            return
        if not self._shell_type_ok(found, target, control):
            self.notes.append(f"тип поля «{found.name}» исходной формы не равен типу реквизита «{key[1]}» по выгрузке: поле не переиспользовано, "
                              "создано заново (описатель типа и его зеркало ставит `bind`, у существующего поля операции для этого нет)")
            return
        spec.shell = found
        spec.field_name = found.name
        shown = shell_mod.caption_of(found.node if control == "CheckBox" else (found.label.node if found.label is not None else None))
        if control == "TextBox":
            if found.label is not None:
                spec.label_name = found.label.name
            else:
                shown = None
        if shown is not None:
            if explicit is not None and not shell_mod.same_text(shown, explicit):
                spec.new_caption = explicit
            else:
                spec.text = shown

    def _shell_type_ok(self, found, target, control):
        """Описатель типа поля исходной формы равен тому, что `bind` записал бы по реквизиту объекта (`pattern_block`). Флажок, стандартный реквизит,
        реквизит формы и случай без выгрузки не сверяются (там типа к сверке нет) — поле остаётся."""
        if control != "TextBox" or target.kind != "attribute" or self.config is None:
            return True
        try:
            block, _mirror, _cls = datatype.pattern_block(target.thing, self.config)
        except datatype.TypeNotWritten:
            return True                  # отказ про тип скажет `type_problem`, а не молчаливое «не то»
        content = found.node.get(CONTENT)
        pattern = content.get(TEXTBOX_PATTERN) if isinstance(content, dict) else None
        types = pattern.get(PATTERN_TYPES) if isinstance(pattern, dict) else None
        return types == datatype.blocks_of(block)

    def column_problem(self, attr):
        """Реквизит табличной части, которого колонка с путём не выразит (`add_column`, 99b): причина словами либо `None`."""
        if self.config is None:
            return None
        try:
            datatype.pattern_block(attr, self.config)
        except datatype.TypeNotWritten as e:
            return f"{e}; `add_column` типа такого реквизита не пишет"
        return None  # булев реквизит — колонка-флажок по образцу конструктора: отказа нет

    def type_problem(self, target, control):
        """Тип реквизита, который `bind` в запись не выразит, — причина словами либо `None`. То же правило, что у редактора (`edit.datatype.pattern_block`):
        отказ описания СРАЗУ, одним списком с прочими."""
        if target.kind in ("standard", "formattr") or self.config is None:
            return None            # реквизит формы: тип в поле копирует `bind(copy_type=True)` целиком, `pattern_block` не нужен
        try:
            if control == "CheckBox":
                datatype.type_class(target.thing)
            else:
                datatype.pattern_block(target.thing, self.config)
        except datatype.TypeNotWritten as e:
            return f"{e}; `bind` типа такого реквизита не пишет, и поле осталось бы с типом шаблона"
        return None

    def stretch_kind(self):
        """Вид формы для решения о правой привязке (`STRETCH_FORM_KINDS`): форма справочника — `catalog.item`, документа — `document.item`; обработка и всё, чего в таблице нет, — `None` (решение по классу)."""
        return None if self.processing else STRETCH_FORM_KINDS.get(self.obj.kind)

    @staticmethod
    def stretch_of(target, control, form_kind=None):
        """Растягивается ли НОВОЕ поле ввода вправо вместе с формой — по классу типа реквизита и виду формы (`stretch_class`: решение по паре, по классу, стиль конструктора);
        `None` — класса нет (реквизит формы, составной тип, определяемый тип, класс без решения и без стиля конструктора): растягивается, как прежде."""
        if control != "TextBox":
            return None
        if target.kind == "standard":
            return stretch_class(target.name, form_kind)
        if target.kind != "attribute":
            return None
        try:
            cls = datatype.type_class(target.thing)
        except datatype.TypeNotWritten:
            return None
        return stretch_class(cls, form_kind)

    @staticmethod
    def date_of(target, control):
        """Состав даты поля ввода (`Date`, `Time`, `DateTime`) либо `None`: реквизит не на дату, составной тип, флажок. Стандартный реквизит «Дата» — дата со временем."""
        if control != "TextBox":
            return None
        if target.kind == "standard":
            return "DateTime" if target.name == "Дата" else None
        if target.kind not in ("attribute", "formattr"):
            return None
        try:
            cls = datatype.type_class(target.thing)
        except datatype.TypeNotWritten:
            return None
        return target.thing.date_fractions if cls == "dateTime" and target.thing.date_fractions in DATE_PARTS else None

    def text_of(self, target):
        if target.kind == "standard":
            return self.obj.standard_synonyms.get(target.name) or target.name
        return target.thing.synonym or target.name

    def control_of(self, target):
        """Вид элемента по типу: `(вид, кнопка выбора)` либо отказ с перечнем."""
        if target.kind == "standard":
            if target.name in ("Код", "Номер", "Наименование", "Дата"):
                return "TextBox", False  # у Даты кнопка стоит у меньшинства форм — по большинству нет
            return "TextBox", True  # Родитель, Владелец — ссылки
        attr = target.thing
        if attr.type_sets:
            raise GenerateError(f"тип «{', '.join(attr.type_sets)}» (определяемый тип или набор): раскрывать его модуль не "
                                "умеет, и вид элемента для него в константах движка (не `patterns.json`) не назван")
        if not attr.types:
            raise GenerateError(f"реквизит «{attr.name}» произвольного типа (в выгрузке `<Type/>` без типов): вид элемента для него в константах движка не назван")
        if len(attr.types) != 1:
            if datatype.composite_ok(attr):
                return "TextBox", True  # составной тип известного набора (`edit.datatype.composite_ok`): поле с кнопкой выбора — как у конструктора
            raise GenerateError(f"составной тип ({', '.join(attr.types)}): вид элемента для него в константах движка (не `patterns.json`) не назван; "
                                "порядок блоков описателя известен для наборов из булева, строки, даты (состав Date), числа и ссылок (`COMPOSITE_PLACES`) — этот набор вне их")
        kind = attr.types[0]
        if kind == "xs:boolean":
            return "CheckBox", False  # флажок — у булева реквизита, поле выбора — редко; без надписи слева — у большинства флажков
        if kind == "xs:string":
            return "TextBox", False  # однострочное поле: у большинства без кнопки; многострочное не ставится
        if kind == "xs:decimal":
            return "TextBox", False  # кнопки нет
        if kind == "xs:dateTime":
            return "TextBox", True  # с кнопкой (календарь)
        if _REF.match(kind):
            return "TextBox", True  # ссылка: поле с кнопкой выбора — у большинства полей
        raise GenerateError(f"тип «{kind}»: вида элемента для него в константах движка (не `patterns.json`) нет. Поддержаны: {'; '.join(SUPPORTED_TYPES)}")

    def _radio(self, block, where):
        """Блок `radio`: рамка с заголовком и переключатели на один реквизит ФОРМЫ — число, значение которого — выбранный переключатель. Запись та же, что у правок
        (`GroupBox`, `RadioButton`, `first_in_group`, `bind` с `copy_type`, `selected_value`); реквизита нет — блок заводит его сам: число без дробной части и без знака, разрядность
        по наибольшему значению."""
        _only(block, RADIO_KEYS, where, self.problems)
        if not self.processing:
            self.problems.append(f"{where}: блок radio — переключатели на реквизит ФОРМЫ, а реквизиты формы заводит вид processing; у формы объекта реквизиты — метаданные, "
                                 "переключатель на реквизит объекта платформа не проверялась")
            return None
        name = block["radio"]
        if not isinstance(name, str) or not IDENT.match(name.strip()):
            self.problems.append(f"{where}: radio — имя реквизита формы (идентификатор 1С), число которого выбирает переключатель, а пришло {name!r}")
            return None
        name = name.strip()
        direction = block.get("direction", "column")
        if direction not in RADIO_DIRECTIONS:
            self.problems.append(f"{where}: direction — {' или '.join(map(repr, RADIO_DIRECTIONS))} (переключатели столбиком либо в ряд), а пришло {direction!r}")
            direction = "column"
        raw = block.get("options")
        if not isinstance(raw, list) or len(raw) < 2:
            self.problems.append(f"{where}: options — не меньше двух переключателей: строкой подписи либо {{\"caption\": …, \"value\": …}}, а пришло {raw!r}")
            return None
        options, values, captions = [], [], set()
        for at, option in enumerate(raw):
            here = f"{where}/options/{at}"
            if isinstance(option, str):
                option = {"caption": option}
            if not isinstance(option, dict):
                self.problems.append(f"{here}: переключатель — строка подписи либо объект {{\"caption\", \"value\"}}, а пришло {option!r}")
                continue
            _only(option, OPTION_KEYS, here, self.problems)
            caption, value = option.get("caption"), option.get("value", at)
            if not isinstance(caption, str) or not caption.strip():
                self.problems.append(f"{here}: caption — подпись переключателя непустой строкой, а пришло {caption!r}")
                continue
            if not _is_int(value) or value < 0:
                self.problems.append(f"{here}: value — выбираемое значение, целое неотрицательное (по умолчанию номер переключателя с нуля), а пришло {value!r}")
                continue
            if value in values:
                self.problems.append(f"{here}: значение {value} уже у другого переключателя группы")
                continue
            if caption in captions:
                self.problems.append(f"{here}: подпись «{caption}» названа дважды")
                continue
            captions.add(caption)
            values.append(value)
            options.append((caption, value))
        if len(options) != len(raw):
            return None
        if options[0][1] != 0:
            self.problems.append(f"{where}/options/0: первый переключатель группы платформа ставит с выбираемым значением 0 (данные получает только он), а названо {options[0][1]}: "
                                 "поставьте нулевое значение первым либо не называйте value")
            return None
        digits = max(1, len(str(max(values))))
        title = block.get("caption")
        if title is not None and (not isinstance(title, str) or not title.strip()):
            self.problems.append(f"{where}: caption — заголовок рамки непустой строкой, а пришло {title!r}")
            return None
        known = name in self.form.rows or name in self.form.declared
        if known:
            try:
                attr = self.form.attr(name)
            except GenerateError as e:
                self.problems.append(f"{where}: {e}")
                return None
            if attr.types != ("xs:decimal",) or attr.fraction != 0 or (attr.digits or 0) < digits:
                self.problems.append(f"{where}: реквизит формы «{name}» не годится группе переключателей: нужно число без дробной части и разрядностью не меньше {digits} "
                                     "(по наибольшему значению), а реквизит — "
                                     + (f"число {attr.digits},{attr.fraction}" if attr.types == ("xs:decimal",) else "другого типа")
                                     + "; назовите другой реквизит либо опустите его в attributes — блок заведёт сам")
                return None
            title = title or attr.synonym or name
        else:
            before = len(self.problems)
            made = self.form.declare([{"name": name, "type": "number", "digits": digits, "fraction": 0, "nonnegative": True}], where, self.problems)
            if len(self.problems) != before:
                return None
            self.declare_ops += made
            title = title or name
        self.use(f"форма.{name}", where)
        self.counters["Рамка"] += 1
        names = [(caption, value, _identifier(name + caption)) for caption, value in options]
        return RadioSpec(f"Рамка{self.counters['Рамка']}", name, title, names, direction == "row")

    def _picture(self, block, where):
        """Блок `picture`: поле картинки заданного размера с «Одинарной» рамкой самого поля (без рамки пустое поле в предприятии не видно); с `caption` — ещё и рамка с заголовком вокруг.
        Картинку (данные поля) блок не задаёт: поле ставится пустым."""
        _only(block, PICTURE_KEYS, where, self.problems)
        name, size = block["picture"], block.get("size")
        if not isinstance(name, str) or not IDENT.match(name.strip()):
            self.problems.append(f"{where}: picture — имя поля картинки (идентификатор 1С), а пришло {name!r}")
            return None
        if not (isinstance(size, list) and len(size) == 2 and all(_is_int(v) and v >= PICTURE_MIN for v in size)):
            self.problems.append(f"{where}: size — [ширина, высота] поля картинки целыми не меньше {PICTURE_MIN}, а пришло {size!r}: размер картинки зависит от неё, догадываться нельзя")
            return None
        align = block.get("align", "left")
        if align not in PICTURE_ALIGNS:
            self.problems.append(f"{where}: align — {' или '.join(map(repr, PICTURE_ALIGNS))} (край колонки, к которому прижато поле), а пришло {align!r}")
            return None
        title = block.get("caption")
        if title is not None and (not isinstance(title, str) or not title.strip()):
            self.problems.append(f"{where}: caption — заголовок рамки вокруг поля непустой строкой, а пришло {title!r}")
            return None
        spec = PictureSpec(name.strip(), title, tuple(size), align == "right")
        if title is not None:
            self.counters["Рамка"] += 1
            spec.frame_name = f"Рамка{self.counters['Рамка']}"
        return spec

    def _button(self, entry, where):
        """Кнопка своей команды в ряду: подпись, необязательные `width` (по подписи, если не названа) и `name` (по подписи). Обработчик ставит `tune` (`set_event`)."""
        _only(entry, BUTTON_KEYS, where, self.problems)
        caption = entry["button"]
        if not isinstance(caption, str) or not caption.strip():
            self.problems.append(f"{where}: button — подпись кнопки непустой строкой, а пришло {caption!r}")
            return None
        width = entry.get("width")
        if width is not None and (not _is_int(width) or width < BUTTON_ABS_MIN_W):
            self.problems.append(f"{where}: width кнопки — целое число пикселей не меньше {BUTTON_ABS_MIN_W} (уже кнопки ряда в корпусе нет), а пришло {width!r}")
            return None
        name = entry.get("name", _identifier(caption.strip()) if re.search(r"[A-Za-zА-Яа-яЁё0-9]", caption) else "")
        if not isinstance(name, str) or not IDENT.match(name.strip()):
            self.problems.append(f"{where}: name кнопки — идентификатор 1С (по подписи «{caption.strip()}» его не получить: назовите кнопку сами), а пришло {name!r}")
            return None
        return ButtonSpec(caption.strip(), name.strip(), width)

    def _row(self, block, where):
        """Блок `row`: несколько пар «надпись + поле», флажков и кнопок своих команд В ОДНУ СТРОКУ. Поле без `width` берёт ширину по виду (дата 80, «дата и время» 120, прочие
        100); одно поле — названное в `stretch` либо последнее без `width`, у которого нет кнопки выбора (дата, ссылка) и которое по классу типа не «не растягивать» (число: `STRETCH_VOTES`) — берёт остаток ширины, элементы за ним привязаны вправо."""
        _only(block, ROW_KEYS, where, self.problems)
        raw = block["row"]
        if not isinstance(raw, list) or not raw:
            self.problems.append(f"{where}: row — непустой массив элементов ряда: реквизит строкой либо объектом поля, {{\"button\": \"Подпись\"}} — кнопка своей команды")
            return None
        items = []
        for at, entry in enumerate(raw):
            here = f"{where}/row/{at}"
            if isinstance(entry, dict) and "button" in entry:
                item = self._button(entry, here)
            else:
                item = self._field(entry, here)
            if item is not None:
                items.append(item)
        if len(items) != len(raw):
            return None
        fields = [i for i in items if isinstance(i, FieldSpec) and i.control == "TextBox"]
        stretch = block.get("stretch")
        if stretch is not None:
            name = _strip_object(stretch.strip()) if isinstance(stretch, str) else None
            found = next((i for i in fields if i.name == name), None)
            if found is None:
                self.problems.append(f"{where}: stretch — имя поля ввода этого ряда (реквизит), которое берёт остаток ширины; в ряду: "
                                     f"{', '.join(i.name for i in fields) or 'полей ввода нет'}; пришло {stretch!r}")
                return None
            if found.width:
                self.problems.append(f"{where}: stretch «{found.name}», а у поля задана width {found.width}: поле с шириной не растягивается — уберите одно из двух")
                return None
            return Row(items, found)
        auto = [i for i in fields if not i.width and not i.anchors and i.stretch is not False and not i.choice]
        return Row(items, auto[-1] if auto else None)

    def _beside(self, block, where):
        """Блок `beside`: блок справа (`beside` — рамка, переключатели или поле картинки) и блоки шапки слева (`blocks`). Шапка сужена до блока справа, её ширина фиксирована;
        блок справа привязан к правому краю; блоки после идут под обоими на всю ширину."""
        _only(block, BESIDE_KEYS, where, self.problems)
        right_raw = block["beside"]
        if not isinstance(right_raw, dict):
            self.problems.append(f"{where}: beside — блок справа объектом: один из {', '.join(BESIDE_RIGHT)}, а пришло {right_raw!r}")
            return None
        if not isinstance(block.get("blocks"), list) or not block["blocks"]:
            self.problems.append(f"{where}: у блока справа нет шапки — blocks (блоки слева, рядом с которыми он стоит): {', '.join(BESIDE_LEFT)}; "
                                 "одиночный блок справа без соседа слева ставится обычным блоком, а прижать его к правому краю можно align: right у поля картинки")
            return None
        width = block.get("width")
        if width is not None and (not _is_int(width) or width < PICTURE_MIN):
            self.problems.append(f"{where}: width — ширина блока справа целым числом не меньше {PICTURE_MIN}, а пришло {width!r}")
            width = None
        right = self.blocks([right_raw], f"{where}/beside", BESIDE_RIGHT)
        left = self.blocks(block["blocks"], f"{where}/blocks", BESIDE_LEFT)
        if len(right) != 1 or not left:
            return None
        return Beside(left, right[0], width)

    def _split(self, block, where):
        """Блок `split`: две части (`first` и `second` — блоки словаря) и разделитель между ними: `left_right` — части слева и справа, `top_bottom` — сверху и снизу. Каждая
        часть заканчивается (или начинается — у нижней) растягиваемым блоком: таблицей, панелью закладок либо полем табличного документа; разделитель встаёт между ними
        (`add_element(between=…)`)."""
        _only(block, SPLIT_KEYS, where, self.problems)
        axis = block["split"]
        if axis not in SPLIT_AXES:
            self.problems.append(f"{where}: split — {' или '.join(map(repr, SPLIT_AXES))} (части слева и справа либо сверху и снизу), а пришло {axis!r}")
            return None
        grows = block.get("grows", "both")
        if grows not in SPLIT_GROWS:
            self.problems.append(f"{where}: grows — какая часть берёт прирост окна по оси разделителя: {', '.join(map(repr, SPLIT_GROWS))}; пришло {grows!r}")
            grows = "both"
        size = block.get("first_size")
        if size is not None and (not _is_int(size) or size < SPLIT_MIN_PART[axis]):
            self.problems.append(f"{where}: first_size — {'ширина' if axis == 'left_right' else 'высота'} первой части целым числом не меньше {SPLIT_MIN_PART[axis]} "
                                 f"(таблицы рядом с разделителем уже в корпусе нет), а пришло {size!r}")
            size = None
        parts = []
        for key in ("first", "second"):
            raw = block.get(key)
            if not isinstance(raw, list) or not raw:
                self.problems.append(f"{where}: {key} — непустой массив блоков части (split разделяет ДВЕ части: first и second), а пришло {raw!r}")
                continue
            made = self.blocks(raw, f"{where}/{key}", SPLIT_BLOCKS)
            if len(made) != len(raw):
                continue
            at = _Layout.stretch_index(made)
            if at is None:
                self.problems.append(f"{where}/{key}: часть должна содержать растягиваемый блок — таблицу, панель закладок или поле табличного документа (после него допустимы только поля, "
                                     "рамка, переключатели и поле картинки): разделитель ставится между такими блоками")
                continue
            if axis == "top_bottom" and key == "first" and at != len(made) - 1:
                self.problems.append(f"{where}/first: у горизонтального разделителя растягиваемый блок верхней части — последний в ней (под ним вплотную разделитель), а за ним блоки")
                continue
            if axis == "top_bottom" and key == "second" and at != 0:
                self.problems.append(f"{where}/second: у горизонтального разделителя растягиваемый блок нижней части — первый в ней (над ним вплотную разделитель), а перед ним блоки")
                continue
            parts.append(made)
        if len(parts) != 2:
            return None
        return Split(axis, parts[0], parts[1], size, grows)

    def _group(self, block, where):
        _only(block, ("group", "blocks"), where, self.problems)
        title = block["group"]
        if not isinstance(title, str) or not title.strip():
            self.problems.append(f"{where}: group — заголовок рамки непустой строкой, а пришло {title!r}")
            return None
        self.counters["Рамка"] += 1
        name = f"Рамка{self.counters['Рамка']}"
        inner = self.blocks(block.get("blocks"), f"{where}/blocks", GROUP_BLOCKS)
        return Group(title, name, inner)

    def _tabs(self, block, where):
        _only(block, ("tabs",), where, self.problems)
        pages = block["tabs"]
        if not isinstance(pages, list) or not pages:
            self.problems.append(f"{where}: tabs — непустой массив страниц {{\"page\": …, \"blocks\": […]}}")
            return None
        self.counters["Панель"] += 1
        name = f"Панель{self.counters['Панель']}"
        out, titles = [], set()
        for at, page in enumerate(pages):
            here = f"{where}/tabs/{at}"
            if not isinstance(page, dict) or not isinstance(page.get("page"), str) or not page["page"].strip():
                self.problems.append(f"{here}: страница — объект с заголовком page (строка) и blocks, а пришло {page!r}")
                continue
            _only(page, ("page", "blocks"), here, self.problems)
            if page["page"] in titles:
                self.problems.append(f"{here}: страница «{page['page']}» названа дважды")
            titles.add(page["page"])
            blocks = self.blocks(page.get("blocks"), f"{here}/blocks", PAGE_BLOCKS)
            out.append((page["page"], f"Страница{at + 1}", blocks))
        return Tabs(name, out)

    def _spreadsheet(self, block, where):
        _only(block, ("spreadsheet",), where, self.problems)
        name = block["spreadsheet"]
        if not self.processing:
            self.problems.append(f"{where}: блок spreadsheet — поле табличного документа — ставится на формы обработок (вид processing); "
                                 "у формы элемента справочника и документа его не мерили")
            return None
        if not isinstance(name, str) or not IDENT.match(name.strip()):
            self.problems.append(f"{where}: spreadsheet — имя поля табличного документа (идентификатор 1С), а пришло {name!r}")
            return None
        name = name.strip()
        if name in [s.name for s in self.sheets]:
            self.problems.append(f"{where}: поле табличного документа «{name}» названо дважды")
            return None
        spec = SheetSpec(name)
        self.sheets.append(spec)
        return spec

    def _form_table(self, block, where, bar):
        """Таблица на РЕКВИЗИТ ФОРМЫ типа ValueTable либо ValueTree (`"source": "form"`): колонки — словари `valuesrc` (имя, заголовок, ширина, выравнивание,
        формат); тип колонки — ключ `type` (`S`, `N`, `D`, `B`)."""
        name = block["table"]
        if not self.processing:
            self.problems.append(f"{where}: source form — у вида processing: реквизиты формы есть у формы обработки, а у вида этой формы они объявлены метаданными")
            return None
        if not isinstance(name, str) or not name.strip():
            self.problems.append(f"{where}: table — имя реквизита формы строкой, а пришло {name!r}")
            return None
        name = name.strip()
        if name == self.form.main or (name not in self.form.rows and name not in self.form.declared):
            known = ", ".join(n for n in self.form.names() if self.form.platform_kind(n) in (valuesrc.VALUE_TABLE, valuesrc.VALUE_TREE)) or "нет"
            self.problems.append(f"{where}: у формы нет реквизита-таблицы «{name}»; таблицы и деревья значений формы: {known}; новый — в ключе attributes "
                                 "(type ValueTable либо ValueTree)")
            return None
        kind = self.form.platform_kind(name)
        if kind not in (valuesrc.VALUE_TABLE, valuesrc.VALUE_TREE):
            self.problems.append(f"{where}: реквизит «{name}» — {kind or 'не таблица и не дерево значений'}: таблицу показывает реквизит ValueTable, дерево — ValueTree"
                                 + (" (список значений показывает поле списка, генерация его не ставит)" if kind == valuesrc.VALUE_LIST else ""))
            return None
        raw = block.get("columns")
        if raw is None:
            self.problems.append(f"{where}: columns — колонки таблицы значений: имена строками либо объекты "
                                 "{\"name\", \"header\", \"width\", \"align\", \"format\"}; у реквизита формы колонок в метаданных нет, взять их неоткуда")
            return None
        try:
            columns = valuesrc._check_columns(raw, kind == valuesrc.VALUE_TREE)
        except ed_base.EditError as e:
            self.problems.append(f"{where}: {e}")
            return None
        self.use(f"{name}", where)
        spec = TableSpec(name, name, None, columns, bar, form_attr=name, tree=kind == valuesrc.VALUE_TREE)
        self.tables.append(spec)
        return spec

    def _table(self, block, where):
        _only(block, ("table", "columns", "bar", "source"), where, self.problems)
        bar = block.get("bar", TABLE_BAR_DEFAULT)
        if not isinstance(bar, bool):
            self.problems.append(f"{where}: bar — true или false (командная панель над таблицей; по умолчанию {str(TABLE_BAR_DEFAULT).lower()}), "
                                 f"а пришло {bar!r}")
            bar = TABLE_BAR_DEFAULT
        source = block.get("source", "object")
        if source not in ("object", "form"):
            self.problems.append(f"{where}: source — object (табличная часть объекта; по умолчанию) или form (реквизит формы — таблица или дерево значений), а пришло {source!r}")
            return None
        if source == "form":
            return self._form_table(block, where, bar)
        path = block["table"]
        if not isinstance(path, str) or not path.strip():
            self.problems.append(f"{where}: table — путь к табличной части строкой («Объект.Цены»), а пришло {path!r}")
            return None
        if self.obj is None:
            self.problems.append(f"{where}: table «{path.strip()}» — табличная часть ОБЪЕКТА, а объекта обработки у формы нет: "
                                 f"{self.no_object}. Таблица на реквизит формы (таблица значений) не ставится")
            return None
        name = _strip_object(path.strip())
        try:
            target = datapath.resolve(self.obj, name, self.role)
        except ed_base.EditError as e:
            self.problems.append(f"{where}: {e}")
            return None
        if target.kind != "table":
            self.problems.append(f"{where}: «{name}» — не табличная часть объекта «{self.obj.full_name}» "
                                 f"({datapath.PATH_WORDS[target.kind]}); табличные части: "
                                 f"{', '.join(t.name for t in self.obj.tables) or 'нет'}")
            return None
        ts = target.thing
        data = f"{datapath.OBJECT_WORD}.{name}"
        self.use(data, where)
        table_name = name                # правило конструктора: табличное поле названо табличной частью (занято — суффикс, `_assign_names`)
        raw = block.get("columns")
        if raw is None:
            names = [a.name for a in ts.attributes]  # все реквизиты части в порядке метаданных
            if not names:
                self.problems.append(f"{where}: у табличной части «{name}» нет реквизитов — таблице нечего показать")
        elif not isinstance(raw, list) or not raw or not all(isinstance(c, str) for c in raw):
            self.problems.append(f"{where}: columns — непустой массив имён колонок (или убрать ключ: тогда все реквизиты части)")
            names = []
        else:
            names = list(raw)
        columns, seen = [], set()
        for column in names:
            if column in seen:
                self.problems.append(f"{where}: колонка «{column}» названа дважды")
                continue
            seen.add(column)
            if column == datapath.ROW_NUMBER:
                columns.append((column, "N", f"{data}.{column}", "row_number"))      # заголовок «N» — как у конструктора
                continue
            found = next((a for a in ts.attributes if a.name == column), None)
            if found is None:
                self.problems.append(f"{where}: в табличной части «{name}» нет колонки «{column}»; реквизиты: "
                                     f"{', '.join(a.name for a in ts.attributes) or 'нет'}; {datapath.ROW_NUMBER} — номер строки")
                continue
            reason = self.column_problem(found)
            if reason is not None:
                self.problems.append(f"{where}: колонка «{column}»: {reason}")
                continue
            kind = ed_columns.template_kind(found) if self.config is not None else None
            columns.append((column, found.synonym or found.name, f"{data}.{column}", kind))
        if raw is None and names and not columns:
            self.problems.append(f"{where}: у табличной части «{name}» нет ни одного реквизита, который колонка выразит")
        spec = TableSpec(table_name, data, ts, columns, bar)
        self._reuse_table(spec)
        self.tables.append(spec)
        return spec

    def _reuse_table(self, spec):
        """Таблица исходной формы на ту же табличную часть остаётся: колонки с теми же данными стоят как были, недостающие дописываются в конец, лишние
        убираются. Состав и порядок обязаны это позволять: оставшиеся колонки идут в порядке описания, а недостающие — только после последней
        оставшейся (вставки в середину у редактора нет) и не называются, как лишняя; иначе таблица создаётся заново и это названо."""
        found = self.shell.tables.get(spec.ts.name) if self.shell is not None else None
        if found is None:
            inside = self.shell.nested.get(("table", spec.ts.name)) if self.shell is not None else None
            if inside is not None:
                self.notes.append(f"таблица «{inside[0]}» (часть «{spec.ts.name}») лежит в «{inside[1]}» исходной формы — внутри панели или рамки "
                                  "таблицы не переиспользуются: создана заново (обработчики прежней остаются в модуле без элемента)")
            return
        want = [c[0] for c in spec.columns]
        kept, drop = [], []
        for column in found.columns:
            if column.key is not None and column.key in want and column.key not in kept:
                kept.append(column.key)
            else:
                drop.append(column.name)
        in_order = [k for k in want if k in kept]
        last = max((want.index(k) for k in kept), default=-1)
        new_names = {c[0] for c in spec.columns if c[0] not in kept}
        why = None
        if kept != in_order:
            why = "колонки исходной формы идут в ином порядке, чем в описании"
        elif any(want[i] not in kept for i in range(last + 1)):
            why = "колонка описания стоит ВЫШЕ колонки исходной формы, а вставки в середину у редактора нет"
        elif any(name in new_names for name in drop):
            why = "имя лишней колонки исходной формы занято колонкой описания"
        if why is not None:
            self.notes.append(f"таблица «{found.name}» исходной формы не переиспользована: {why}; создана заново (обработчики колонок и таблицы остаются в "
                              "модуле без элемента)")
            return
        spec.shell, spec.keep, spec.drop = found, kept, drop
        spec.add = [c for c in spec.columns if c[0] not in kept]
        spec.name = found.name
        spec.bar_kept = spec.bar and found.bar is not None
        spec.bar_name = found.bar.name if spec.bar_kept else None


# ── Размещение ────────────────────────────────────────────────────────────────────────────────

@dataclasses.dataclass
class Placed:
    """Элемент к постановке: что, где (box — лево, верх, ширина, высота), как привязан и что при нём."""
    template: object
    name: str
    box: list
    anchor: dict
    holder: str = None
    page: int = 0
    caption: str = None
    bind: str = None
    field: FieldSpec = None
    table: TableSpec = None
    panel: Tabs = None
    page_blocks: list = None      # у панели: по странице — её расставленные элементы
    expand: bool = False          # растянутый блок (таблица или панель, за которой в её списке блоков только поля): при явном
                                  # размере забирает остаток высоты
    below: list = None            # у растянутого блока: элементы полей под ним — их верх привязан к низу родителя, и остаток высоты
                                  # сдвигает их вниз
    reuse: bool = False           # элемент исходной формы: остаётся (`name` — его имя в исходной форме), движок только переносит его (`move_element`)
    bar_of: object = None         # у командной панели таблицы — её `TableSpec`
    new_caption: str = None       # у переиспользованной надписи: новая подпись (названа описанием и отличается от исходной формы)
    radio: RadioSpec = None       # у переключателя группы: блок `radio`, которому он принадлежит
    radio_at: int = None          # у переключателя: номер в группе (0 — первый: он несёт данные и `first_in_group`)
    picture: PictureSpec = None   # у поля картинки блока `picture`: рамка самого поля ставится `set_property border`
    split: object = None          # у разделителя блока `split`: `SplitPlan` — соседи, рост частей и кто берёт прирост


@dataclasses.dataclass
class SplitPlan:
    """Разделитель блока `split`: соседи (`add_element(between=…)`), растущие элементы частей и то, как делится прирост высоты формы."""
    axis: str
    grows: str
    near: Placed                 # сосед до разделителя (слева, сверху)
    far: Placed                  # сосед после разделителя
    first: Placed                # растущий элемент первой части (таблица, панель закладок, поле табличного документа)
    second: Placed
    second_items: list           # элементы второй части на уровне разделителя: у горизонтального разделителя сдвигаются вниз вместе с ростом первой части
    sizes: tuple                 # высоты частей на момент раскладки (у горизонтального разделителя прирост делится в их пропорции)
    fixed_first: bool = False    # высота первой части названа (`first_size`): прирост высоты формы при расчёте целиком у второй, `grows` решает только поведение при растяжении окна


def _text_w(text, font=None):
    """Ширина надписи: ровно по тексту подписи — ширины знаков шрифта форм (`textwidth`: Microsoft Sans Serif 11 px, `hdmx`), так конструктор платформы и
    ставит ширину («Наименование:» 79 px, «Комментарий:» 73; «Номер» и «Сумма» — 34, «Дата» — 26). Рендер усекает подпись по той же мере (`textmeasure`,
    без запаса). `font` — действующий шрифт надписи (`textwidth.element_font`): у надписи стиля 10 pt жирной ширина другая; нет описания — шрифт формы по
    умолчанию."""
    return max(MIN_LABEL_W, textwidth.width(text, font))


def _flag_w(text, font=None):
    from . import render
    return textwidth.width(text, font) + render.CHECK_CAPTION_PAD  # подпись целиком при ширине ≥ 16 + текст; `font` — как у `_text_w`


def _field_specs(blocks):
    """Все `FieldSpec` блоков, в том числе внутри рамок и страниц панелей."""
    for block in blocks:
        if isinstance(block, Fields):
            yield from block.items
        elif isinstance(block, Row):
            yield from (i for i in block.items if isinstance(i, FieldSpec))
        elif isinstance(block, Group):
            yield from _field_specs(block.blocks)
        elif isinstance(block, Beside):
            yield from _field_specs([*block.left, block.right])
        elif isinstance(block, Split):
            yield from _field_specs([*block.first, *block.second])
        elif isinstance(block, Tabs):
            for _title, _name, inner in block.pages:
                yield from _field_specs(inner)


def _kept_nodes(blocks, kind):
    """Узлы исходной формы, что остаются в форме (`item.shell`), у полей `Fields` во вложенных блоках: надписи (`kind` «Label») либо флажки («CheckBox»)."""
    for block in blocks:
        if isinstance(block, (Fields, Row)):
            for item in block.items:
                if not isinstance(item, FieldSpec) or item.shell is None:
                    continue
                if kind == "Label" and item.control == "TextBox" and item.shell.label is not None:
                    yield item.shell.label.node
                elif kind == "CheckBox" and item.control == "CheckBox":
                    yield item.shell.node
        elif isinstance(block, Group):
            yield from _kept_nodes(block.blocks, kind)
        elif isinstance(block, Beside):
            yield from _kept_nodes([*block.left, block.right], kind)
        elif isinstance(block, Split):
            yield from _kept_nodes([*block.first, *block.second], kind)
        elif isinstance(block, Tabs):
            for _title, _name, inner in block.pages:
                yield from _kept_nodes(inner, kind)


def _new_fonts(form_doc, blocks):
    """Шрифт новых надписей и флажков: их оформит `add_element` по соседям, а соседи на тот момент — оставленные узлы исходной формы (остальные
    `remove_element` ушли первыми), поэтому решают они; нет их — шрифт шаблона (у него `Auto` — шрифт формы)."""
    return {kind: design.neighbour_font(form_doc, kind, list(_kept_nodes(blocks, kind))) for kind in ("Label", "CheckBox")}


def _font_notes(fonts):
    """Слова про шрифт новых подписей: не умолчание — ширины надписей и флажков считаны по нему; не проверялся — по оценке."""
    from . import place
    out = []
    for kind, word in (("Label", "надписей"), ("CheckBox", "флажков")):
        font = fonts.get(kind) or textwidth.DEFAULT_FONT
        got = textwidth.measure("", font)
        if font.get("unmeasured") or not got.exact:
            out.append(f"шрифт новых {word} ({place.font_words(font)}, по соседям) не проверялся ({font.get('unmeasured') or got.why}): ширины подписей по оценке — "
                       "проверьте их в конструкторе")
        elif font.get("size") != textwidth.DEFAULT_SIZE or font.get("bold") or font.get("italic"):
            out.append(f"шрифт новых {word} — {place.font_words(font)} (по соседям оформления, `textwidth.element_font`): ширины подписей считаны по нему")
    return out


def _cells(fields, c):
    """Поля колонки `c` блока: строки по порядку чтения, колонки слева направо."""
    return [i for at, i in enumerate(fields.items) if at % fields.columns == c]


class _Layout:
    def __init__(self, norms, sized=False, style=None, doc=None, fonts=None):
        self.n = norms
        self.style = style or ShellStyle()
        self.doc = doc  # исходная форма: шрифт оставленной надписи (`textwidth.element_font`) берётся из её узла
        self.fonts = fonts or {}           # вид → шрифт НОВОГО элемента по соседям (`design.neighbour_font`); нет вида — шрифт формы по умолчанию
        self.column_widths = set()  # ширины колонки надписей исходной формы, какие легли в форму (заметка называет ширину, которая стоит)
        self.sized = sized         # размер формы назван: растянутая таблица ставится минимальной высоты, остаток высоты забирает она (`_grow`)
        self.gap = norms["pair_pitch"] - norms["field_height"]  # зазор между блоками: производная нормы
        self.col_gap = norms["label_left"]  # зазор между колонками пар блока `fields`: отступ слева вида; формы конструктора выгрузок (круг `describe` → `generate` байт в байт) стоят на нём, на 10 (замер ряда) круг расходится
        self.pin = None            # внутри блока `beside`: "left" — шапка слева (ширина фиксирована, привязки влево), "right" — блок справа (привязки вправо); иначе обычные правила

    def _h(self, normal):
        """Горизонтальная привязка элемента: внутри `beside` — край, к которому прижат блок (ширина фиксирована, растягиваться нечему), иначе `normal`."""
        return self.pin or normal

    def label_font(self, item):
        """Шрифт надписи поля: оставленной — её собственный (`new_caption` меняет текст, шрифт остаётся), новой — по соседям."""
        node = getattr(getattr(item.shell, "label", None), "node", None)
        if node is not None and self.doc is not None:
            return textwidth.element_font(node, self.doc)
        return self.fonts.get("Label")

    def label_text(self, item):
        """Подпись надписи поля, какой она будет в форме: оставленная без новой подписи — ТА, что стоит в исходной форме (у платформенных форм перед ней бывает
        пробел), а не синоним реквизита; иначе — текст описания."""
        node = getattr(getattr(item.shell, "label", None), "node", None)
        if node is not None and item.new_caption is None:
            return render_mod.caption_text(node, "Label") or item.text
        return item.text

    def flag_text(self, item):
        """То же у флажка: оставленный без новой подписи несёт подпись исходной формы (` Архив` с пробелом), и ширина — по ней."""
        node = getattr(item.shell, "node", None)
        if node is not None and item.new_caption is None:
            return render_mod.caption_text(node, "CheckBox") or item.text
        return item.text

    def flag_font(self, item):
        node = getattr(item.shell, "node", None)
        if node is not None and self.doc is not None:
            return textwidth.element_font(node, self.doc)
        return self.fonts.get("CheckBox")

    # ширина надписи поля: по ЕЁ подписи (поле начинается после своей надписи); при `align` — одна на колонку: самая длинная подпись, не уже нормы `label_column_width`
    def label_w(self, fields, c, item):
        if not fields.align:
            return _text_w(self.label_text(item), self.label_font(item))
        labels = [_text_w(self.label_text(i), self.label_font(i)) for i in _cells(fields, c) if i.control == "TextBox"]
        if self.style.label_w is not None:
            # колонка исходной формы имеет приоритет: ширина не меньше её ширины и не уже самой длинной НОВОЙ подписи. Подпись ОСТАВЛЕННОЙ надписи колонку не раздвигает: надпись
            # уже стоит в колонке исходной формы (у платформы такая надпись многострочная или усечена в колонке)
            fresh = [_text_w(i.text, self.label_font(i)) for i in _cells(fields, c) if i.control == "TextBox" and (i.shell is None or i.shell.label is None or i.new_caption is not None)]
            width = max(fresh + [self.style.label_w])
            self.column_widths.add(width)
            return width
        floor = self.n.get("label_column_width")
        floor = max(MIN_LABEL_W, floor - self.n["label_field_gap"]) if floor else 0
        return max(labels + [floor])

    def pair_gap(self, fields):
        """Зазор «надпись → поле»: у исходной формы с колонкой надписей, когда блок её применяет (`align`), — её (у конструктора 6, а норма документа — 2: поле стояло
        бы на 4 px левее), иначе норма вида. Явный `align: false` снимает стиль колонки целиком — и ширину надписей, и зазор."""
        if self.style.label_w is not None and self.style.label_gap is not None and fields.align:
            return self.style.label_gap
        return self.n["label_field_gap"]

    def column_need(self, fields, c):
        """Ширина колонки пар по ЕЁ нужде: надпись + зазор + поле самой требовательной пары либо самый широкий флажок."""
        n = self.n
        cells = _cells(fields, c)
        narrow = max([i.width or _flag_w(self.flag_text(i), self.flag_font(i)) for i in cells if i.control == "CheckBox"] or [0])
        wide = max([self.label_w(fields, c, i) + self.pair_gap(fields) + (i.width or MIN_FIELD_W)
                    for i in cells if i.control == "TextBox"] or [0])
        return max(narrow, wide)

    @staticmethod
    def frame_title_w(title):
        """Ширина заголовка рамки: жирный шрифт (+1 px на знак), отступы слева и справа — `FRAME_TITLE_PAD`. Рамка, чья ширина берётся по содержимому (`beside`), не уже заголовка."""
        return textwidth.width(title, {**textwidth.DEFAULT_FONT, "bold": True}) + FRAME_TITLE_PAD

    # минимальная ширина содержимого блока (без полей по краям)
    def need(self, block):
        if isinstance(block, Fields):
            return sum(self.column_need(block, c) for c in range(block.columns)) + self.col_gap * (block.columns - 1)
        if isinstance(block, Group):
            return max(max([self.need(b) for b in block.blocks] or [0]) + GROUP_INNER[0] + GROUP_INNER[2], self.frame_title_w(block.title))
        if isinstance(block, Tabs):
            inside = max([self.need(b) for _t, _n, blocks in block.pages for b in blocks] or [0])
            return inside + NESTED[0] + NESTED[2] + PANEL_AREA_W
        if isinstance(block, TableSpec):
            return TABLE_MIN_W
        if isinstance(block, SheetSpec):
            return SHEET_MIN_W
        if isinstance(block, RadioSpec):
            widths = [self.radio_w(block, caption) for caption, _v, _n in block.options]
            return max(RADIO_INSET[0] + RADIO_INSET[2] + (sum(widths) + RADIO_GAP * (len(widths) - 1) if block.row else max(widths)), self.frame_title_w(block.title))
        if isinstance(block, PictureSpec):
            if block.title:
                return max(block.size[0] + PICTURE_INSET[0] + PICTURE_INSET[2], self.frame_title_w(block.title))
            return block.size[0]
        if isinstance(block, Row):
            chunks = self.row_chunks(block)
            return sum(self.chunk_w(c) for c in chunks) + sum(self.row_gaps(chunks))
        if isinstance(block, Beside):
            return max([self.need(b) for b in block.left] or [0]) + SIDE_GAP + max(block.width or 0, self.need(block.right))
        if isinstance(block, Split):
            first = max([self.need(b) for b in block.first] or [0])
            second = max([self.need(b) for b in block.second] or [0])
            if block.axis == "top_bottom":
                return max(first, second)
            return max(block.size or 0, first, TABLE_MIN_W) + SPLIT_GAP + max(second, TABLE_MIN_W)
        return 0

    @staticmethod
    def stretch_index(blocks):
        """Номер блока, который растягивается вниз вместе с родителем, либо `None`: таблица или панель закладок, за которой в списке блоков родителя (формы без
        нижней панели команд, страницы панели) идут ТОЛЬКО блоки подвала (`FOOTER_BLOCKS`: поля, рамка с полями, переключатели, поле картинки). Под таблицей одни
        блоки подвала — низ идёт с низом формы; под панелью закладок так же; элементы под растянутой, и вложенные в рамку тоже, сдвигаются вниз все и привязаны вниз. За таблицей
        другая таблица или панель — не проверялось: стопка таблиц делит рост долями, и растягивается только последний блок."""
        at = len(blocks) - 1
        while at >= 0 and isinstance(blocks[at], (Fields, Group, RadioSpec, PictureSpec, Row, Beside)):
            at -= 1
        return at if at >= 0 and isinstance(blocks[at], (Tabs, TableSpec, SheetSpec, Split)) else None

    def blocks(self, blocks, fields_x, other_x, y, holder=None, page=0, under=False):
        """Блоки сверху вниз: `(элементы, нижний край, растянутый элемент либо None)`. Между блоками — зазор строк (шаг − высота поля). `fields_x` и
        `other_x` — левый и правый края для пар и для прочих блоков (у формы поля пар и панелей разные; внутри рамки и страницы — одни). Растянутый блок —
        `stretch_index`; поля под ним привязаны верхом к низу родителя."""
        items, grower = [], None
        stretch = self.stretch_index(blocks)
        bottom = y
        for at, block in enumerate(blocks):
            top = y if at == 0 else bottom + self.gap
            x0, x1 = fields_x if isinstance(block, (Fields, Row)) else other_x
            footer = under or (stretch is not None and at > stretch)       # подвал: привязки вниз, сдвигается вниз с ростом родителя
            if isinstance(block, Fields):
                made, bottom = self.fields(block, x0, x1, top, holder, page, footer)
            elif isinstance(block, Group):
                made, bottom = self.group(block, x0, x1, top, holder, page, footer)
            elif isinstance(block, RadioSpec):
                made, bottom = self.radio(block, x0, x1, top, holder, page, footer)
            elif isinstance(block, PictureSpec):
                made, bottom = self.picture(block, x0, x1, top, holder, page, footer)
            elif isinstance(block, Row):
                made, bottom = self.row(block, x0, x1, top, holder, page, footer)
            elif isinstance(block, Beside):
                made, bottom = self.beside(block, fields_x, other_x, top, holder, page, footer)
            elif isinstance(block, Split):
                made, bottom = self.split(block, x0, x1, top, holder, page)
            elif isinstance(block, Tabs):
                made, bottom = self.tabs(block, x0, x1, top, holder, page, at == stretch)
            elif isinstance(block, SheetSpec):
                made, bottom = self.sheet(block, x0, x1, top, holder, page, at == stretch)
            else:
                made, bottom = self.table(block, x0, x1, top, holder, page, at == stretch)
            if at == stretch:
                grower = made[-1] if isinstance(block, Split) else next(i for i in made if i.expand)         # у таблицы с панелью растягивается таблица, а не панель над ней; у разделителя — сам разделитель (он ведёт обе части)
                grower.below = []
            elif grower is not None:
                grower.below += made
            items += made
        return items, bottom, grower

    @staticmethod
    def flag_h(item):
        """Высота флажка: названная описанием; у оставленного флажка исходной формы — его собственная; новый — `FLAG_H` (как у конструктора)."""
        if item.height:
            return item.height
        coords = ((item.shell.node.get("coords") if item.shell is not None else None) or {})
        if isinstance(coords.get("y"), int) and isinstance(coords.get("bottom"), int) and coords["bottom"] > coords["y"]:
            return coords["bottom"] - coords["y"]
        return FLAG_H

    @staticmethod
    def right_anchor(item, right):
        """Привязка правого края поля последней колонки: оставленное поле — своя, если раскладка не поменяла его правый край (колонку) и поведение поля у
        платформы однозначно; иначе — по классу типа (`FieldSpec.stretch`; нет класса — растягивается). «Своя» определяется по РОСТУ ширины
        (`layout.horizontal_behaviour`), а не по правому коэффициенту: поле, у которого сдвигаются обе границы (cL = cR = 1: ширина постоянна), не растягивается и
        растягиваться не должно; поле, которое меняется пропорционально росту окна, и цикл правил своей привязки не дают."""
        kept = item.shell
        if kept is not None and kept.box is not None and kept.box[2] == right and kept.behaviour in (layout.GROWS, layout.STANDS, layout.MOVES):
            return "stretch" if kept.behaviour == layout.GROWS else "left"
        return "left" if item.stretch is False else "stretch"

    def row_anchors(self, row, cols, v):
        """Привязки ряда по стилю рядов исходной формы: `[(привязка надписи, привязка поля)]` по колонкам либо `None` — стиля нет или ряд им не пишется. Пишется
        только ПОЛНЫЙ ряд из пар «надпись + поле» (колонок две и больше, ячеек столько же, все — поля ввода), у которого ни одно поле не несёт ширины и привязок
        из описания: названное описанием стоит как названо. Прочие ряды — решением по классу (`right_anchor`).

        `prop_pos` — роль `proportional` у надписи и у поля каждой колонки. `split` — шапка колонок: первая надпись `self`, первое поле `column`; следующая
        надпись идёт за полем слева (`after`), следующее поле — за ним с дальней границей долей (`after` + `column`), последнее — за ним с дальней границей у
        края формы (`after` + `stretch`)."""
        kind = self.style.row_style
        if kind is None or cols < 2 or len(row) != cols or any(i.control != "TextBox" or i.width or i.anchors for i in row):
            return None
        if kind == "prop_pos":
            both = {"h": "proportional", "v": v}
            return [(dict(both), dict(both)) for _ in row]
        out = []
        for c, item in enumerate(row):
            prev = row[c - 1] if c else None  # сосед — ОБЪЕКТОМ поля, а не именем: имя новому полю даёт `_assign_names` позже и может поменять; имя подставляет `_resolve_neighbours`
            label = {"h": "self" if c == 0 else {"after": prev}, "v": v}
            if c == 0:
                field = {"h": "column", "v": v}
            else:
                field = {"h": {"after": prev, "role": "column" if c < cols - 1 else "stretch"}, "v": v}
            out.append((label, field))
        return out

    def fields(self, block, x0, x1, y, holder, page, under=False):
        """Сетка пар. Ширина колонки — по её нужде (`column_need`), свободное место делится поровну между колонками, а не режет доступную ширину на равные
        ячейки: широкой колонке не хватало бы ровно того, что узкой не нужно."""
        n = self.n
        v = "bottom" if under else "top"          # под растянутой таблицей или панелью поле сдвигается вниз с родителем
        cols = block.columns
        need = [self.column_need(block, c) for c in range(cols)]
        free = max(0, (x1 - x0) - self.col_gap * (cols - 1) - sum(need))
        cells, left = [], x0
        for c in range(cols):
            last = c == cols - 1
            width = x1 - left if last else need[c] + free // cols
            cells.append((left, left + width))
            left += width + self.col_gap
        rows = [block.items[i:i + cols] for i in range(0, len(block.items), cols)]
        items, top = [], y
        bottom = y
        for r, row in enumerate(rows):
            # флажок в ряду с полем ввода — высоты поля (как прежде: шаг рядов пар остаётся нормой); флажок один в ряду — своей высоты (`flag_h`)
            alone = all(i.control == "CheckBox" for i in row)

            def high(item):
                if item.control == "CheckBox" and alone:
                    return self.flag_h(item)
                return item.height or (n["multiline_height"] if item.multi_line else n["field_height"])
            row_h = max(high(i) for i in row)
            styled = None if self.pin else self.row_anchors(row, cols, v)
            for c, item in enumerate(row):
                left, right = cells[c]
                if item.control == "CheckBox":
                    full = self.style.flags_full(n["field_right_margin"])  # флажки исходной формы во всю строку — и этот во всю строку колонки
                    width = item.width or (right - left if full else min(_flag_w(self.flag_text(item), self.flag_font(item)), right - left))
                    kept = item.shell is not None
                    items.append(Placed("CheckBox", item.field_name, [left, top, width, high(item)],
                                        item.anchors or {"h": self._h("left"), "v": v}, holder, page, None if kept else item.text,
                                        bind=item.data or item.attribute, field=item, reuse=kept, new_caption=item.new_caption))
                    continue
                label = self.label_w(block, c, item)
                kept_label = item.shell is not None and item.shell.label is not None
                items.append(Placed("Label", item.label_name, [left, top, label, n["label_height"]],
                                    styled[c][0] if styled else {"h": self._h("left"), "v": v}, holder, page, None if kept_label else item.text, reuse=kept_label,
                                    new_caption=item.new_caption))
                fx = left + label + self.pair_gap(block)
                if styled:                                 # ряд пишется стилем исходной формы (`row_anchors`): ширина — до границы колонки, привязки — стиля
                    width, anchor = right - fx, styled[c][1]
                elif item.width or c < cols - 1:           # заданная ширина и внутренние колонки стоят: растягивается только последняя
                    width, anchor = item.width or right - fx, {"h": self._h("left"), "v": v}
                else:
                    width, anchor = right - fx, {"h": self._h(self.right_anchor(item, right)), "v": v}
                items.append(Placed("TextBox", item.field_name, [fx, top, width, high(item)],
                                    item.anchors or anchor, holder, page, bind=item.data or item.attribute, field=item,
                                    reuse=item.shell is not None))
            bottom = top + row_h
            top = bottom + self.gap
        return items, bottom

    def group(self, block, x0, x1, y, holder, page, under=False):
        left, up, right, down = GROUP_INNER
        inside = (x0 + left, x1 - right)
        inner, bottom, _grower = self.blocks(block.blocks, inside, inside, y + up, holder, page, under)
        height = bottom + down - y
        frame = Placed("GroupBox", block.name, [x0, y, x1 - x0, height], {"h": self._h("stretch"), "v": "bottom" if under else "top"}, holder, page, block.title)
        return [frame] + inner, y + height

    def radio_w(self, block, caption):
        """Ширина переключателя: подпись целиком — как у флажка (рисунок и отступ подписи те же), шрифт новых флажков по соседям."""
        return _flag_w(caption, self.fonts.get("CheckBox"))

    def radio(self, block, x0, x1, y, holder, page, under=False):
        """Группа переключателей: рамка с заголовком на всю колонку и переключатели внутри — столбиком (шаг `RADIO_PITCH`) либо в ряд (зазор `RADIO_GAP`). Отступы рамки — корпус
        (`RADIO_INSET`). Первый переключатель несёт данные, остальные — выбираемое значение (`_ops_of`)."""
        left, up, right, down = RADIO_INSET
        v = "bottom" if under else "top"
        items, x, top = [], x0 + left, y + up
        for at, (caption, _value, name) in enumerate(block.options):
            width = self.radio_w(block, caption)
            items.append(Placed("RadioButton", name, [x, top, width, RADIO_H], {"h": self._h("left"), "v": v}, holder, page, caption, radio=block, radio_at=at))
            if block.row:
                x += width + RADIO_GAP
            else:
                top += RADIO_PITCH
        bottom = y + up + RADIO_H + down if block.row else top - RADIO_PITCH + RADIO_H + down
        frame = Placed("GroupBox", block.name, [x0, y, x1 - x0, bottom - y], {"h": self._h("stretch"), "v": v}, holder, page, block.title)
        return [frame] + items, bottom

    def picture(self, block, x0, x1, y, holder, page, under=False):
        """Поле картинки: без `caption` — само поле у левого либо правого края колонки; с `caption` — внутри рамки с заголовком (рамка по размеру поля, отступы — `PICTURE_INSET`)."""
        w, h = block.size
        v = "bottom" if under else "top"
        right = block.right or self.pin == "right"          # блок справа от шапки прижат к правому краю, что бы ни было в align
        side = {"h": self._h("right" if right else "left"), "v": v}
        if block.title is None:
            x = x1 - w if right else x0
            return [Placed("PictureBox", block.name, [x, y, w, h], side, holder, page, picture=block)], y + h
        left, up, right, down = PICTURE_INSET
        fw, fh = max(w + left + right, self.frame_title_w(block.title)), h + up + down
        fx = x1 - fw if right else x0
        frame = Placed("GroupBox", block.frame_name, [fx, y, fw, fh], side, holder, page, block.title)
        return [frame, Placed("PictureBox", block.name, [fx + left, y + up, w, h], side, holder, page, picture=block)], y + fh

    # ── ряд, блок справа, две области ──────────────────────────────────────────────────────────
    def row_field_class(self, item):
        """Состав типа поля ряда для таблицы ширин: `Date`, `Time`, `DateTime`, `S` (строка), `N` (число), `#` (ссылка: поле с кнопкой выбора), `other`."""
        if item.date:
            return item.date
        if item.type_class in FIELD_CLASS_BY_TYPE:
            return FIELD_CLASS_BY_TYPE[item.type_class]
        return "#" if item.choice else "other"

    def row_field_w(self, item):
        """Ширина поля ввода ряда без `width`, не растягивающегося: медиана ширин таких полей корпуса по составу типа (`rownorms.field_width`; «только время» — как дата)."""
        return rownorms.field_width(self.row_field_class(item))[0]

    @staticmethod
    def row_button_size(text_w):
        """Кнопка ряда по ширине подписи: `(высота, прибавка к подписи, наименьшая ширина)` — обычная (подпись не уже `REGULAR_TW`) либо короткая («…»)."""
        if text_w >= REGULAR_TW:
            return ROW_BUTTON_H, ROW_BUTTON_PAD, ROW_BUTTON_MIN_W
        return ROW_SHORT_BUTTON_H, ROW_SHORT_BUTTON_PAD, ROW_SHORT_BUTTON_MIN_W

    def row_chunks(self, block):
        """Звенья ряда слева направо: `("pair", поле, (ширина надписи, ширина поля))`, `("flag", поле, ширина)`, `("button", кнопка, ширина)`."""
        out = []
        for item in block.items:
            if isinstance(item, ButtonSpec):
                text = textwidth.width(item.caption, None)
                _h, pad, least = self.row_button_size(text)
                out.append(("button", item, item.width or max(least, text + pad)))
            elif item.control == "CheckBox":
                out.append(("flag", item, item.width or _flag_w(self.flag_text(item), self.flag_font(item))))
            else:
                out.append(("pair", item, (_text_w(self.label_text(item), self.label_font(item)), item.width or self.row_field_w(item))))
        return out

    @staticmethod
    def row_gap(prev, nxt):
        """Зазор между двумя звеньями ряда: корпус (`rownorms.gap`) по виду предыдущего (поле или пара, флажок, кнопка) и следующего (надпись пары, флажок, кнопка); у надписи — по
        ширине её текста (связка «с», «по» ближе)."""
        kind_prev = {"pair": "field", "flag": "check", "button": "button"}[prev[0]]
        kind_next = {"pair": "label", "flag": "check", "button": "button"}[nxt[0]]
        return rownorms.gap(kind_prev, kind_next, nxt[2][0] if nxt[0] == "pair" else None)[0]

    def row_gaps(self, chunks):
        return [self.row_gap(a, b) for a, b in zip(chunks, chunks[1:])]

    def chunk_w(self, chunk):
        kind, _item, w = chunk
        return w[0] + self.n["label_field_gap"] + w[1] if kind == "pair" else w

    def row(self, block, x0, x1, y, holder, page, under=False):
        """Ряд: звенья слева направо с зазором по виду соседей (`row_gap`), по высоте — по центру строки. Растягиваемое поле (`Row.stretch`) берёт остаток ширины, звенья за ним привязаны вправо;
        внутри `beside` (`pin`) ряд не растягивается."""
        n = self.n
        v = "bottom" if under else "top"
        chunks = self.row_chunks(block)
        stretch = None if self.pin else block.stretch
        gaps = self.row_gaps(chunks) + [0]
        total = sum(self.chunk_w(c) for c in chunks) + sum(gaps)
        extra = max(0, (x1 - x0) - total) if stretch is not None else 0

        def field_h(item):
            return item.height or (n["multiline_height"] if item.multi_line else n["field_height"])

        def high(chunk):
            kind, item, _w = chunk
            if kind == "button":
                return self.row_button_size(textwidth.width(item.caption, None))[0]
            if kind == "flag":
                return item.height or self.flag_h(item)
            return max(n["label_height"], field_h(item))
        row_h = max(high(c) for c in chunks)
        items, x, after = [], x0, False
        for at, chunk in enumerate(chunks):
            kind, item, w = chunk
            mine = stretch is not None and kind == "pair" and item is stretch
            side = self._h("right" if after else "left")
            if kind == "button":
                height = self.row_button_size(textwidth.width(item.caption, None))[0]
                items.append(Placed("Button", item.name, [x, y + (row_h - height) // 2, w, height], {"h": side, "v": v}, holder, page, item.caption))
                x += w
            elif kind == "flag":
                kept = item.shell is not None
                height = item.height or self.flag_h(item)
                items.append(Placed("CheckBox", item.field_name, [x, y + (row_h - height) // 2, w, height], item.anchors or {"h": side, "v": v}, holder, page,
                                    None if kept else item.text, bind=item.data or item.attribute, field=item, reuse=kept, new_caption=item.new_caption))
                x += w
            else:
                lw, fw = w
                fw += extra if mine else 0
                kept_label = item.shell is not None and item.shell.label is not None
                items.append(Placed("Label", item.label_name, [x, y + (row_h - n["label_height"]) // 2, lw, n["label_height"]], {"h": side, "v": v}, holder, page,
                                    None if kept_label else item.text, reuse=kept_label, new_caption=item.new_caption))
                fx = x + lw + n["label_field_gap"]
                anchor = {"h": "stretch" if mine else side, "v": v}
                items.append(Placed("TextBox", item.field_name, [fx, y + (row_h - field_h(item)) // 2, fw, field_h(item)],
                                    item.anchors or anchor, holder, page, bind=item.data or item.attribute, field=item, reuse=item.shell is not None))
                x = fx + fw
            x += gaps[at]
            if mine:
                after = True
        return items, y + row_h

    def beside(self, block, fields_x, other_x, y, holder, page, under=False):
        """Шапка слева (`block.left`) и блок справа (`block.right`) от верха `y`; блок справа — по краю `other_x[1]`, его ширина — по содержимому (не меньше `width`), шапка
        сужена до зазора `SIDE_GAP` перед ним. Низ — нижний из двух."""
        gap = SIDE_GAP
        right_w = max(block.width or 0, self.need(block.right))
        rx0 = other_x[1] - right_w
        left_x, left_o = (fields_x[0], rx0 - gap), (other_x[0], rx0 - gap)
        was = self.pin
        try:
            self.pin = "left"
            left_items, left_bottom, _grower = self.blocks(block.left, left_x, left_o, y, holder, page, under)
            self.pin = "right"
            right = block.right
            call = self.group if isinstance(right, Group) else self.radio if isinstance(right, RadioSpec) else self.picture
            right_items, right_bottom = call(right, rx0, other_x[1], y, holder, page, under)
        finally:
            self.pin = was
        return left_items + right_items, max(left_bottom, right_bottom)

    def split(self, block, x0, x1, y, holder, page):
        """Две части с разделителем. Вертикальный: первая часть шириной `size` (по содержимому, не уже `TABLE_MIN_W`), разделитель `SPLIT_GAP`, вторая — остаток; обе части одной
        высоты (растягиваемый элемент короткой части дотянут до низа). Горизонтальный: первая часть высотой `size` (по содержимому), разделитель, вторая. Разделитель — последний в
        списке элементов блока: он ставится после обоих соседей (`add_element(between=…)`), его растущие части — в `Placed.split`."""
        first_need = max([self.need(b) for b in block.first] or [0])
        if block.axis == "left_right":
            width = block.size or max(first_need, TABLE_MIN_W)
            if width < first_need:
                raise GenerateError(f"split: first_size {width} мало — содержимому первой части нужно не меньше {first_need}")
            left, right = (x0, x0 + width), (x0 + width + SPLIT_GAP, x1)
            one, bottom1, grow1 = self.blocks(block.first, left, left, y, holder, page)
            two, bottom2, grow2 = self.blocks(block.second, right, right, y, holder, page)
            bottom = max(bottom1, bottom2)
            for grower, low in ((grow1, bottom1), (grow2, bottom2)):
                if low < bottom:
                    _grow(grower, bottom - low)         # короткая часть дотянута до низа длинной
            top = min(grow1.box[1], grow2.box[1])
            low = max(grow1.box[1] + grow1.box[3], grow2.box[1] + grow2.box[3])
            box = [x0 + width, top, SPLIT_GAP, low - top]
            near, far = grow1, grow2
            sizes = (bottom - y, bottom - y)
        else:
            inside = (x0, x1)
            one, bottom1, grow1 = self.blocks(block.first, inside, inside, y, holder, page)
            if block.size is not None:
                if block.size < bottom1 - y:
                    raise GenerateError(f"split: first_size {block.size} мало — содержимому первой части нужно не меньше {bottom1 - y}")
                if block.size > bottom1 - y:
                    _grow(grow1, block.size - (bottom1 - y))
                    bottom1 = y + block.size
            two, bottom, grow2 = self.blocks(block.second, inside, inside, bottom1 + SPLIT_GAP, holder, page)
            box = [x0, bottom1, x1 - x0, SPLIT_GAP]
            near, far = grow1, two[0]
            sizes = (bottom1 - y, bottom - bottom1 - SPLIT_GAP)
        plan = SplitPlan(block.axis, block.grows, near, far, grow1, grow2, two, sizes, block.size is not None)
        sp = Placed("Splitter", "Разделитель", box, None, holder, page, expand=True, split=plan)
        return one + two + [sp], bottom

    def tabs(self, block, x0, x1, y, holder, page, stretched):
        width = x1 - x0
        area = width - PANEL_AREA_W
        pages, tallest, growers = [], 0, []
        for title, _name, blocks in block.pages:
            inside = (NESTED[0], area - NESTED[2])
            inner, bottom, grower = self.blocks(blocks, inside, inside, NESTED[1], block.name, len(pages))
            pages.append(inner)
            growers.append((grower, bottom + NESTED[3]))
            tallest = max(tallest, bottom + NESTED[3])
        # Страница ниже самой высокой своей растянутой таблицей (панелью, полем) доходит до низа области страницы: высоту панели задаёт самая высокая страница, и без
        # этого под таблицей короткой страницы оставалась полоса в разницу высот (форма с панелью закладок разной высоты страниц, до 67 px). Зазор до низа — `NESTED[3]`, как у самой высокой страницы
        for grower, low in growers:
            if grower is not None and low < tallest:
                _grow(grower, tallest - low)
        height = tallest + PANEL_AREA_H
        panel = Placed("Panel", block.name, [x0, y, width, height],
                       {"h": "stretch", "v": "stretch" if stretched else "top"}, holder, page, panel=block,
                       page_blocks=pages, expand=stretched)
        return [panel], y + height

    def sheet(self, block, x0, x1, y, holder, page, stretched):
        item = Placed(SHEET, block.name, [x0, y, x1 - x0, SHEET_CONTENT_H],
                      {"h": "stretch", "v": "stretch" if stretched else "top"}, holder, page, expand=stretched)
        return [item], y + SHEET_CONTENT_H

    def table(self, block, x0, x1, y, holder, page, stretched):
        """Таблица и (по ключу `bar`) командная панель над ней — вплотную, как у конструктора. Высота таблицы — по содержимому (`TABLE_CONTENT_H`), а при
        названном размере формы растянутая берёт минимум `TABLE_MIN_H`, и остаток высоты добавляет `_grow`."""
        high = TABLE_MIN_H if (stretched and self.sized) else TABLE_CONTENT_H
        items, top = [], y
        if block.bar:
            items.append(Placed("CommandBar", block.bar_name, [x0, y, x1 - x0, TABLE_BAR_H], {"h": "stretch", "v": "top"}, holder, page,
                                bar_of=block, reuse=block.bar_name is not None))
            top = y + TABLE_BAR_H
        items.append(Placed("TableBox", block.name, [x0, top, x1 - x0, high],
                            {"h": "stretch", "v": "stretch" if stretched else "top"}, holder, page, bind=None if block.form_attr else block.data, table=block,
                            expand=stretched, reuse=block.shell is not None))
        return items, top + high


def _grow(item, delta):
    """Растянуть элемент вниз на `delta`, а поля под ним сдвинуть вниз на столько же; у панели — и растянутый блок каждой её
    страницы (со своими полями под ним); у разделителя блока `split` — обе части: у вертикального обе растут на `delta`, у горизонтального прирост делится между частями
    по `grows` (вторая часть сдвигается вниз вместе с ростом первой)."""
    if item.split is not None:
        plan = item.split
        if plan.axis == "left_right":
            item.box[3] += delta
            _grow(plan.first, delta)
            _grow(plan.second, delta)
        else:
            if plan.fixed_first:
                first = 0
            elif plan.grows == "first":
                first = delta
            elif plan.grows == "second":
                first = 0
            else:
                first = round(delta * plan.sizes[0] / (plan.sizes[0] + plan.sizes[1])) if sum(plan.sizes) else 0
            _grow(plan.first, first)
            for other in plan.second_items:
                other.box[1] += first
            item.box[1] += first
            _grow(plan.second, delta - first)
        for under in item.below or ():
            under.box[1] += delta
        return
    item.box[3] += delta
    for under in item.below or ():
        under.box[1] += delta
    for inner in item.page_blocks or ():
        for stretched in inner:
            if stretched.expand:
                _grow(stretched, delta)


def _flat(items):
    """Элементы подряд: за панелью — её вложенные по страницам."""
    for item in items:
        yield item
        for inner in item.page_blocks or ():
            yield from _flat(inner)


# Табличное поле на табличную часть и панель над ним — как у конструктора

def tabular_table_node(ts):
    """Узел `TableBox` на табличную часть `ts` — как его пишет конструктор платформы (`templates.tabular_table`): без колонок, тип значения — `TypeId`
    табличной части по выгрузке. Колонки ставит `add_column(template=…)`.

    Шаблон пула `TableBox-01` для табличной части не годится: таблица на нём в предприятии пустая (вид источника данных и тип значения у таблицы значений
    другие, колонки без вложенного поля ввода). Нет `TypeId` у части (у `TabularSection` в выгрузке нет `InternalInfo`) — отказ: тип значения таблицы
    взять неоткуда, а нулевой GUID в запись не пишется."""
    if not ts.type_id:
        raise GenerateError(f"у табличной части «{ts.name}» в выгрузке нет TypeId (xr:GeneratedType category=\"TabularSection\" в InternalInfo части): "
                            "тип значения табличного поля взять неоткуда; переиспользуется только таблица исходной формы на эту часть — а её нет")
    node = templates.tabular_table()
    node[CONTENT][TABLE_TYPE][1][1] = {"guid": ts.type_id}
    return node


def table_bar_node():
    """Командная панель таблицы — как её пишет конструктор (`templates.table_bar_node`: один код с `add_element(bar_for=<таблица>)`)."""
    return templates.table_bar_node()


# ── Операции ──────────────────────────────────────────────────────────────────────────────────

def _ops_of(item, role, ops):
    """Операции постановки одного элемента (и его вложенных): новый — `add_element` с привязкой данных, элемент исходной формы — `move_element`."""
    if item.reuse:
        _move_ops(item, role, ops)
        return
    if item.split is not None:       # разделитель блока `split`: место и привязки выводятся из соседей (`add_element(between=…)`), стоит после обоих
        kw = {"op": "add_element", "template": "Splitter", "name": item.name, "between": [item.split.near.name, item.split.far.name]}
        taken = {"first": "before", "second": "after"}.get(item.split.grows)
        if taken is not None:
            kw["takes_growth"] = taken
        ops.append(kw)
        return
    kw = {"op": "add_element", "name": item.name, "box": list(item.box), "anchor": item.anchor}
    if item.holder is not None:
        kw["holder"], kw["page"] = item.holder, item.page
    if item.table is not None and item.table.form_attr:     # таблица на реквизит формы: поле, привязка и колонки одной операцией (`edit.valuesrc`)
        kw["template"] = "TreeBox" if item.table.tree else "TableBox"
        kw["attribute"], kw["columns"] = item.table.form_attr, copy.deepcopy(item.table.columns)
    elif item.table is not None:
        kw["template"] = tabular_table_node(item.table.ts)
    elif item.bar_of is not None:
        kw["template"] = table_bar_node()
    else:
        kw["template"] = item.template
    if item.caption is not None:
        kw["caption"] = item.caption
    ops.append(kw)
    if item.radio is not None:
        _radio_ops(item, ops)
    if item.picture is not None:
        ops.append({"op": "set_property", "element": item.name, "name": "border", "value": copy.deepcopy(PICTURE_BORDER)})
    form_use = {"form_use": role} if role else {}
    if item.bind is not None and item.table is None:
        field = item.field
        if field is not None and field.attribute is not None:
            ops.append({"op": "bind", "element": item.name, "attribute": field.attribute, "copy_type": True})
        else:
            ops.append({"op": "bind", "element": item.name, "data": item.bind, **form_use})
        if field is not None and field.choice and "choice_button" not in (field.props or {}):
            ops.append({"op": "set_property", "element": item.name, "name": "choice_button", "value": True})
        if field is not None and field.tip is not None and "tool_tip" not in (field.props or {}):
            ops.append({"op": "set_property", "element": item.name, "name": "tool_tip", "value": field.tip})
        _field_tune_ops(item, ops)
    if item.table is not None and item.table.form_attr:
        _bar_source_op(item.table, item.name, ops)
    elif item.table is not None:
        _table_ops(item, role, ops)
    if item.panel is not None:
        ops.append({"op": "set_property", "element": item.name, "page": "Страница1", "name": "caption",
                    "value": item.panel.pages[0][0]})
        for title, name, _blocks in item.panel.pages[1:]:
            ops.append({"op": "add_page", "panel": item.name, "name": name, "caption": title})


def _radio_ops(item, ops):
    """Переключатель группы после постановки: первый — «первый в группе» и данные (реквизит формы, тип поля копируется), остальные — выбираемое значение; голое число
    приводится редактором к объекту по типу группы (`docs/edit-rules.md`, «Ввод без угадывания»)."""
    group = item.radio
    if item.radio_at == 0:
        ops.append({"op": "set_property", "element": item.name, "name": "first_in_group", "value": True})
        ops.append({"op": "bind", "element": item.name, "attribute": group.attribute, "copy_type": True})
    else:
        ops.append({"op": "set_property", "element": item.name, "name": "selected_value", "value": group.options[item.radio_at][1]})


def _field_tune_ops(item, ops):
    """Свойства и шрифт, названные описанием у поля (`props`, `font`): и у нового, и у переиспользованного."""
    field = item.field
    if field is not None:
        if field.choice_list is not None:      # поле выбора со списком: смена вида и список — теми же операциями, что правка человека (`change_type`, `set_property choice_list`)
            ops.append({"op": "change_type", "element": item.name, "to": "ComboBox"})
            ops.append({"op": "set_property", "element": item.name, "name": "choice_list", "value": copy.deepcopy(field.choice_list)})
        if field.multi_line:
            ops.append({"op": "set_property", "element": item.name, "name": "multi_line", "value": True})
        for name, value in (field.props or {}).items():
            ops.append({"op": "set_property", "element": item.name, "name": name, "value": value})
        if field.font:
            ops.append({"op": "set_font", "element": item.name, **field.font})


def _move_ops(item, role, ops):
    """Элемент исходной формы остаётся: меняются место, размер, привязки краёв и страница (`move_element`); имя, индекс, привязка данных, события и
    прочие свойства прежние. Подпись — только если описание назвало другую."""
    kw = {"op": "move_element", "name": item.name, "box": list(item.box), "anchor": item.anchor if item.anchor is not None else "self"}  # без привязки — «к себе», перебор привязок не нужен
    if item.holder is not None:
        kw["holder"], kw["page"] = item.holder, item.page
    ops.append(kw)
    if item.new_caption is not None:
        ops.append({"op": "set_caption", "element": item.name, "text": item.new_caption})
    _field_tune_ops(item, ops)
    if item.table is not None:
        _table_columns_ops(item, role, ops)


def _column_op(item, column, role):
    name, header, data, template = column
    return {"op": "add_column", "table": item.name, "name": name, "header": header, "data": data, "template": template,
            **({"form_use": role} if role else {})}


def _table_ops(item, role, ops):
    """Новая таблица на табличную часть: узел-образец конструктора без колонок → `bind` таблицы на ТЧ → колонки по описанию, каждая — своим
    образцом конструктора (`add_column(template=…)`: путь, тип, вложенное поле ввода и номера сразу) → источник действий панели таблицы."""
    form_use = {"form_use": role} if role else {}
    ops.append({"op": "bind", "element": item.name, "data": item.bind, **form_use})
    for column in item.table.columns:
        ops.append(_column_op(item, column, role))
    _bar_source_op(item.table, item.name, ops)


def _table_columns_ops(item, role, ops):
    """Таблица исходной формы остаётся: недостающие колонки дописываются в конец (образец конструктора), лишние убираются — после, чтобы последней
    колонкой таблица не оставалась пустой."""
    for column in item.table.add:
        ops.append(_column_op(item, column, role))
    for name in item.table.drop:
        ops.append({"op": "remove_column", "table": item.name, "name": name})
    _bar_source_op(item.table, item.name, ops)


def _bar_source_op(table, table_name, ops):
    """Новая панель таблицы получает источник действий — таблицу; панель исходной формы его уже несёт."""
    if table.bar and not table.bar_kept:
        ops.append({"op": "set_action_source", "bar": table.bar_name, "source": table_name})


def _shell_names(form_doc):
    """Имена элементов ВЕРХНЕГО уровня исходной формы: вложенные уходят вместе с родителем."""
    names = []
    for item in ed_base.elements_of(ed_base.container(form_doc)):
        name = ed_base.name_of(item)
        if not name:
            raise GenerateError("у элемента исходной формы нет имени — убрать его по имени нечем; правьте форму (rename_element)")
        names.append(name)
    return names


def _unique(base, used):
    """Имя без повтора: занято — суффикс числом с единицы (`Код`, `Код1`, `Код2`) — как платформа называет второй элемент с тем же именем."""
    if base not in used:
        return base
    k = 1
    while f"{base}{k}" in used:
        k += 1
    return f"{base}{k}"


def _assign_names(flat, kept, reserved):
    """Имена НОВЫХ элементов — по правилу конструктора платформы (поле и флажок — имя реквизита, надпись `Надпись<Имя>`, таблица — имя табличной
    части, панель таблицы — `КоманднаяПанель<N>`, рамка и панель закладок — `Рамка<N>` и `Панель<N>`); занято — суффикс числом (`_unique`).
    Заняты: имена оставленных элементов исходной формы (`kept`), панели формы (`reserved`) и имена, названные описанием (поле табличного документа —
    его не переименовывают молча: занятое имя — отказ). Слова отказа — список; пустой — всё названо."""
    used = set(kept) | set(reserved)
    problems = []
    named = [i for i in flat if i.template == SHEET and not i.reuse]
    for item in named:
        if item.name in used:
            problems.append(f"имя поля табличного документа «{item.name}» занято: оно совпадает с именем, которое движок даёт сам, либо с "
                            "элементом исходной формы, который остаётся, — назовите поле иначе")
        used.add(item.name)
    for item in flat:
        if item.reuse or any(item is n for n in named):
            continue
        if item.bar_of is not None:
            number = 1
            while f"{TABLE_BAR_NAME}{number}" in used:
                number += 1
            item.name = item.bar_of.bar_name = f"{TABLE_BAR_NAME}{number}"
        else:
            item.name = _unique(item.name, used)
        used.add(item.name)
    return problems


def _resolve_neighbours(flat):
    """Цепочки `{"after": <поле>}` рядов стиля `split` (`_Layout.row_anchors`) — после окончательного именования (`_assign_names`): сосед назван
    объектом поля, имя берётся у его элемента на форме, а не из описания — занятое имя нового поля сменилось бы суффиксом, и цепочка привязала бы колонку
    к чужому элементу исходной формы."""
    placed = {id(i.field): i for i in flat if i.field is not None and i.table is None and i.bar_of is None}

    def name_of(value):
        if isinstance(value, FieldSpec):
            if id(value) not in placed:
                raise GenerateError("ряд стиля «split»: соседа по цепочке привязок нет среди поставленных элементов (ошибка движка, а не описания)")
            return placed[id(value)].name
        return value
    for item in flat:
        anchor = item.anchor
        if not isinstance(anchor, dict) or not any(isinstance(a, dict) and isinstance(a.get("after"), FieldSpec) for a in anchor.values()):
            continue
        item.anchor = {axis: ({**a, "after": name_of(a["after"])} if isinstance(a, dict) and "after" in a else a) for axis, a in anchor.items()}


def _reuse_notes(flat):
    """Что из исходной формы осталось (слова для отчёта): число полей, надписей, флажков, таблиц и их колонок."""
    kinds = collections.Counter(i.template for i in flat if i.reuse and i.bar_of is None and i.table is None)
    tables = [i for i in flat if i.reuse and i.table is not None]
    bars = sum(1 for i in flat if i.reuse and i.bar_of is not None)
    parts = [f"{kinds[k]} {word}" for k, word in (("TextBox", "полей ввода"), ("Label", "надписей"), ("CheckBox", "флажков")) if kinds[k]]
    for t in tables:
        parts.append(f"таблица «{t.name}» (колонок осталось {len(t.table.keep)}, дописано {len(t.table.add)}, убрано {len(t.table.drop)})")
    if bars:
        parts.append(f"панелей таблицы {bars}")
    if not parts:
        return []
    return ["из исходной формы остались (имя, индекс, привязка данных, обработчики и свойства прежние; перенесены, изменены размер и привязки краёв): "
            + ", ".join(parts)]


def _object_of(desc, form_doc, cfg):
    """Объект описания и объект исходной формы: совпадают, иначе отказ."""
    try:
        named = cfg.object(desc["object"])
    except metadata.MetadataError as e:
        raise GenerateError(f"object: {e}") from None
    try:
        found = datapath.form_object(form_doc, cfg, datapath.OBJECT_WORD).obj
    except ed_base.EditError as e:
        raise GenerateError(f"форма не годится исходной формой: {e}") from None
    if found is not named:
        raise GenerateError(f"форма — объекта «{found.full_name}» (по типу её основного реквизита), а описание — объекта "
                            f"«{named.full_name}»: генерация не пишет чужие GUID реквизитов в чужую форму")
    return named


def _processing_scope(desc, form_doc, config):
    """Вид `processing`: `(объект обработки либо None, реквизиты формы, причина «объекта нет»)`.

    **Сначала исходная форма, потом имя**: имя в описании сверяется с ТИПОМ основного реквизита исходной формы, а не с выгрузкой вслепую.
    * Основной реквизит — `Object` обработки выгрузки: описание обязано называть ЭТУ обработку (иначе отказ «чужие GUID»); объект есть.
    * Основной реквизит — объект ДРУГОГО объекта выгрузки (справочник, документ, другая обработка): отказ «чужие GUID».
    * Основной реквизит — тип не из выгрузки (внешняя обработка, диалог задания, тип платформы), нет основного реквизита, выгрузки не дано, либо
      обработка выгрузки не прочитана: объекта нет, выгрузка служит только типам-ссылкам, данные формы — реквизиты формы. Если описание при этом
      называет обработку, которая в выгрузке ЕСТЬ, — отказ «форма не этой обработки»: собственное имя обработки в выгрузке не бывает."""
    form = FormAttributes(form_doc, config)
    if form.short:
        raise GenerateError(form.short + " — форма версии 10 генерацией не собирается")
    if config is None:
        return None, form, "выгрузки конфигурации не дано (--config)"
    if not isinstance(config, metadata.Config):
        raise GenerateError("config — выгрузка конфигурации (metadata.load)")
    if form.main is None:
        return None, form, "у формы нет основного реквизита"
    try:
        named = config.object(desc["object"])
    except metadata.MetadataError:
        named = None
    guid = datapath._type_guid(form.rows[form.main])
    hit = config.object_by_type_id(guid) if guid else None
    if hit is None or hit[1].lower() != "object":
        if named is not None and named.external:      # развилку ведёт объект описания, а не наличие выгрузки: с --config и --root-xml вместе слова те же
            raise GenerateError(f"основной реквизит формы «{form.main}» — не тип Object внешнего объекта «{named.full_name}» из корневого XML: "
                                f"форма не {'этого внешнего отчёта' if named.kind == 'report' else 'этой внешней обработки'}")
        if not config.has_dump:
            return None, form, (f"основной реквизит формы «{form.main}» — не тип Object внешнего объекта из корневого XML; данные формы — "
                                "реквизиты формы")
        if named is not None:
            raise GenerateError(f"основной реквизит формы «{form.main}» — не объект выгрузки «{config.root}» (внешняя обработка или отчёт, "
                                f"диалог задания, тип платформы), а описание называет {'отчёт' if named.kind == 'report' else 'обработку'} выгрузки "
                                f"«{named.full_name}»: форма не {'этого отчёта' if named.kind == 'report' else 'этой обработки'}. У внешней "
                                "обработки или отчёта в описании собственное имя (в выгрузке его нет), данные формы — только реквизиты формы")
        said = config.failed_reason(desc["object"])
        return None, form, (f"основной реквизит формы «{form.main}» — не объект выгрузки «{config.root}»; объекта "
                            f"{'отчёта' if REPORT_PREFIX.match(desc['object'].strip()) else 'обработки'} «{desc['object']}» в выгрузке нет"
                            + (f" (файл {'отчёта' if REPORT_PREFIX.match(desc['object'].strip()) else 'обработки'} не прочитан: {said})" if said else ""))
    if hit[0].external:
        if not metadata.same_object_name(desc["object"], hit[0].full_name):
            raise GenerateError(f"описание называет «{desc['object']}», а форма (тип её основного реквизита) и корневой XML — «{hit[0].full_name}»: "
                                f"в описании это имя или «{metadata.KINDS[hit[0].kind][2]}.{hit[0].name}»")
        named = hit[0]
    elif hit[0] is not named:
        raise GenerateError(f"форма — объекта «{hit[0].full_name}» (по типу её основного реквизита), а описание — "
                            f"«{desc['object']}»: генерация не пишет чужие GUID реквизитов в чужую форму")
    try:
        datapath.form_object(form_doc, config, datapath.OBJECT_WORD)      # заодно «выгрузка этой формы?» (`_same_dump`)
    except ed_base.EditError as e:
        raise GenerateError(f"форма не годится исходной формой: {e}") from None
    return named, form, ""


def check_description(desc):
    """Структура описания без метаданных: отказ словами со ВСЕМИ найденными причинами."""
    problems = []
    if not isinstance(desc, dict):
        raise GenerateError("описание — JSON-объект с ключами kind, object, blocks (необязательны title, size, form_use, tune)")
    old = typed.old_field_places(desc)  # поле карты в описании реквизита названо прежним именем — отказ словами, без совместимости
    if old:
        raise GenerateError(old[0][1])
    _only(desc, TOP_KEYS, "описание", problems)
    kind = desc.get("kind")
    if kind in LIST_KINDS:  # форма списка: свои блоки и свои отказы — `generate_list`
        from . import generate_list
        problems = [p for p in problems if not p.startswith("описание: лишние ключи")] + generate_list.check(desc)
    elif kind not in KINDS:
        problems.append(f"kind — {', '.join((*KINDS, *LIST_KINDS))}, а пришло {kind!r}")
    if not isinstance(desc.get("object"), str) or not desc.get("object", "").strip():
        problems.append("object — полное имя объекта выгрузки («Справочник.Номенклатура»; у обработки «Обработка.Имя»)")
    elif kind == PROCESSING and not (OBJECT_PREFIX.match(desc["object"].strip()) or REPORT_PREFIX.match(desc["object"].strip())):
        problems.append(f"object — полное имя обработки «Обработка.Имя» (внешней — «ВнешняяОбработка.Имя») либо отчёта «Отчет.Имя» (внешнего — "
                        f"«ВнешнийОтчет.Имя»), а пришло {desc['object']!r}")
    if kind == PROCESSING and desc.get("form_use") is not None:
        problems.append("form_use — у обработки форм элемента и группы нет")
    if "attributes" in desc and kind != PROCESSING and kind not in LIST_KINDS:
        problems.append("attributes — новые реквизиты ФОРМЫ заводит вид processing; у формы объекта реквизиты — метаданные")
    if "title" in desc and (not isinstance(desc["title"], str) or not desc["title"].strip()):
        problems.append(f"title — непустая строка, а пришло {desc['title']!r}")
    size = desc.get("size", "content")
    if size != "content" and not (isinstance(size, list) and len(size) == 2 and all(_is_int(v) and v > 0 for v in size)):
        problems.append(f"size — \"content\" (по содержимому) или [ширина, высота] целыми, а пришло {size!r}")
    if desc.get("form_use") not in (None, *ROLE_FORMS) and kind not in LIST_KINDS:
        problems.append(f"form_use — {' или '.join(ROLE_FORMS)}, а пришло {desc['form_use']!r}")
    if not isinstance(desc.get("blocks"), list) or not desc.get("blocks"):
        problems.append("blocks — непустой массив блоков")
    tune = desc.get("tune", [])
    if not isinstance(tune, list) or not all(isinstance(o, dict) and isinstance(o.get("op"), str) for o in tune):
        problems.append("tune — массив операций редактора {\"op\": …, …} по именам элементов")
    skipped = desc.get("skipped", [])
    if not isinstance(skipped, list) or not all(
            isinstance(e, dict) and isinstance(e.get("type"), str) and e["type"] and isinstance(e.get("why"), str)
            and set(e) <= set(SKIPPED_KEYS)
            and all(isinstance(v, str) and v for v in e.values()) for e in skipped):
        problems.append("skipped — массив записей {\"type\", \"name\", \"why\", \"in\"} НЕПУСТЫМИ строками (то, что `describe` не "
                        "смог показать блоками; движок его не читает)")
    if problems:
        raise GenerateError("описание не годится: " + "; ".join(f"{i}) {p}" for i, p in enumerate(problems, 1)))


def plan(desc, form_doc, config, norms, heights=None):
    """Описание → перечень операций редактора. Только расчёт: форма и выгрузка не меняются.

    `form_doc` — документ уровня 1 исходной формы, `config` — `metadata.Config`, `norms` — таблица `patterns.load()`,
    `heights` — высоты по соседям (`sibling_heights`), необязательно. Отказ — `GenerateError` со всеми найденными причинами.
    Слова для отчёта (что пропущено, откуда взята высота и панели) — `plan_notes`."""
    return plan_notes(desc, form_doc, config, norms, heights)[0]


def plan_notes(desc, form_doc, config, norms, heights=None):
    """То же, что `plan`, и слова для отчёта: `(операции, заметки)`. Заметки — чего в описании не было, но что движок
    решил сам: панель команд из исходной формы или новая пустая, пропущенная булева колонка, источник высоты поля."""
    check_description(desc)
    if desc["kind"] in LIST_KINDS:
        from . import generate_list
        return generate_list.plan_notes(desc, form_doc, config, norms, heights)
    processing = desc["kind"] == PROCESSING
    if processing:
        obj, form, no_object = _processing_scope(desc, form_doc, config)
        role = None
    else:
        if not isinstance(config, metadata.Config):
            raise GenerateError("config — выгрузка конфигурации (metadata.load)")
        obj = _object_of(desc, form_doc, config)
        if obj.kind != KINDS[desc["kind"]]:
            raise GenerateError(f"вид «{desc['kind']}» — {KIND_WORDS[KINDS[desc['kind']]]}, а объект «{obj.full_name}» — "
                                f"{KIND_WORDS.get(obj.kind, obj.kind)}" + (f" (вид processing)" if obj.kind == "processing" else ""))
        role = desc.get("form_use")
        if role is not None:
            try:
                obj.attributes_for(role)
            except metadata.MetadataError as e:
                raise GenerateError(f"form_use: {e}") from None
        form, no_object = None, ""
    try:
        shell = shell_mod.scan(form_doc, obj)
        shell_note = None
    except ed_base.EditError as e:
        shell, shell_note = shell_mod.Shell(), (f"исходная форма не разобрана для переиспользования элементов ({e}): элементы созданы заново, "
                                                "обработчики прежних остаются в модуле без элемента")
    resolver = _Resolver(obj, role, config, form, shell)
    if processing:
        resolver.no_object = no_object
        attribute_ops = form.declare(desc["attributes"], "attributes", resolver.problems) if "attributes" in desc else []
    blocks = resolver.blocks(desc["blocks"], "blocks", BLOCKS)
    bars = [b for b in blocks if isinstance(b, Bar)]
    for place in BAR_PLACES:
        if sum(1 for b in bars if b.where == place) > 1:
            resolver.problems.append(f"панель команд «{place}» названа дважды")
    if bars and any(b.where == "top" for b in bars) and not isinstance(blocks[0], Bar):
        resolver.problems.append("верхняя панель команд — первый блок")
    if any(b.where == "bottom" for b in bars) and not (isinstance(blocks[-1], Bar) and blocks[-1].where == "bottom"):
        resolver.problems.append("нижняя панель команд — последний блок")
    for spec in resolver.tables:
        if spec.ts is not None and spec.shell is None and not spec.ts.type_id:
            resolver.problems.append(
                f"таблица на табличную часть «{spec.ts.name}»: у части в выгрузке нет TypeId (xr:GeneratedType category=\"TabularSection\"), "
                "тип значения табличного поля взять неоткуда, а таблицы исходной формы на эту часть, которую можно оставить, нет")
    if resolver.problems:
        raise GenerateError("описание не годится: " + "; ".join(f"{i}) {p}" for i, p in enumerate(resolver.problems, 1)))
    top = next((b for b in bars if b.where == "top"), None)
    bottom = next((b for b in bars if b.where == "bottom"), None)
    body = [b for b in blocks if not isinstance(b, Bar)]
    if not body:
        raise GenerateError("описание не годится: в нём одни панели команд — нечего показывать, добавьте fields, group, tabs или table"
                            + (" (у обработки ещё spreadsheet)" if processing else ""))
    norm_kind = norms_kind(desc, obj)
    n = norms_of(norms, norm_kind, bottom=bottom is not None, top=top is not None)
    notes = list(resolver.notes)
    style_at = len(notes)
    notes.append(None)                      # место заметки о стиле исходной формы: её слова зависят от раскладки (колонка могла раздвинуться) — пишется после неё
    if processing:
        notes.append((f"данные формы: объект {'отчёта' if obj.kind == 'report' else 'обработки'} «{obj.full_name}» ({'корневой XML' if obj.external else 'выгрузка'}) и реквизиты формы"
                      if obj is not None else f"данные формы: только реквизиты формы — объекта {'отчёта' if REPORT_PREFIX.match(desc['object'].strip()) else 'обработки'} нет ({no_object})")
                     + (f"; новые реквизиты формы: {', '.join(form.declared)}" if form.declared else ""))
    ml_auto = [f for f in _field_specs(blocks) if f.multi_line and not f.height]
    if ml_auto and n.get("multiline_height") is None:
        raise GenerateError("описание не годится: у многострочного поля без height высоты взять неоткуда — в таблице норм нет общей строки "
                            f"multiline_field_height; назовите height у: {', '.join(f.name for f in ml_auto)}")
    if heights:
        n = {**n, **heights["values"]}
        check_pitch(n, norm_kind)
        notes.append(heights["note"])
    else:
        notes.append(f"высота поля {n['field_height']} и надписи {n['label_height']} — норма вида «{norm_kind}» "
                     "(большинство форм в конфигурациях); соседних форм не дано (--siblings)")
    if ml_auto:
        notes.append(f"высота многострочного поля без height — {n['multiline_height']}: самая частая высота полей не меньше {patterns.MULTILINE_MIN_LINES} строк по "
                     f"конфигурациям корпуса (общая строка multiline_field_height таблицы норм; нормой вида она не является: большинства нет, см. lint): "
                     f"{', '.join(f.name for f in ml_auto)}")
    size = desc.get("size", "content")
    lay = _Layout(n, sized=size != "content", style=resolver.style, doc=form_doc, fonts=_new_fonts(form_doc, blocks))
    notes += _font_notes(lay.fonts)
    # ширина формы: по содержимому (не меньше MIN_FORM_W) либо названная
    needs = []
    for b in body:
        side = n["label_left"] if isinstance(b, (Fields, Row, Beside)) else SIDE_MARGIN
        right = n["field_right_margin"] if isinstance(b, (Fields, Row, Beside)) else SIDE_MARGIN
        needs.append(side + lay.need(b) + right)
    need_w = max(MIN_FORM_W, *needs)
    if size == "content":
        width = need_w
    else:
        width = size[0]
        if width < max(needs):
            raise GenerateError(f"size: ширина {width} мала — содержимому нужно не меньше {max(needs)}; {SIZE_WAY_OUT.format(side='ширину', need=max(needs))}")
    # содержимое сверху вниз; у пар свои поля слева и справа, у прочих блоков свои
    y = n["top_bar_y"] + n["top_bar_height"] + FIRST_BELOW_BAR if top is not None else n["label_left"]
    items, bottom_edge, grower = lay.blocks(body, (n["label_left"], width - n["field_right_margin"]),
                                          (SIDE_MARGIN, width - SIDE_MARGIN), y)
    bar_h = n["bottom_bar_height"] if bottom is not None else 0
    need_h = bottom_edge + BOTTOM_GAP + bar_h
    if size == "content":
        height = need_h
    else:
        height = size[1]
        if height < need_h:
            stretched_table = grower is not None and grower.table is not None
            raise GenerateError(f"size: высота {height} мала — содержимому нужно не меньше {need_h}"
                                + (f" (растянутая таблица — не ниже {TABLE_MIN_H}: высота таблицы конструктора)" if stretched_table else "")
                                + f"; {SIZE_WAY_OUT.format(side='высоту', need=need_h)}")
        if height > need_h and grower is not None:
            _grow(grower, height - need_h)           # остаток высоты забирает растянутый блок, поля под ним сдвигаются вниз
    notes[style_at] = style_note(resolver.style, n["field_right_margin"], lay.column_widths)
    problems = _geometry_problems(items)
    flat = list(_flat(items))
    kept = {i.name for i in flat if i.reuse}
    problems += _assign_names(flat, kept, {BAR_NAMES[b.where] for b in bars})
    _resolve_neighbours(flat)
    if problems:
        raise GenerateError("раскладка не сошлась: " + "; ".join(f"{i}) {p}" for i, p in enumerate(problems, 1)))
    if shell_note:
        notes.append(shell_note)
    notes += _reuse_notes(flat)
    ops = [{"op": "remove_element", "name": name} for name in _shell_names(form_doc) if name not in kept]
    if processing:
        ops += attribute_ops + resolver.declare_ops
    ops += [{"op": "set_property", "form": True, "name": "width", "value": width},
            {"op": "set_property", "form": True, "name": "height", "value": height}]
    if desc.get("title"):
        ops.append({"op": "set_form_title", "text": desc["title"]})
    if top is not None:
        ops.append({"op": "add_element", "template": _bar_template(form_doc, "top", notes), "name": BAR_NAMES["top"],
                    "box": [n["top_bar_x"], n["top_bar_y"], width - n["top_bar_x"], n["top_bar_height"]],
                    "anchor": {"h": "stretch", "v": "top"}})
    for item in _flat(items):
        _ops_of(item, role, ops)
    if bottom is not None:
        ops.append({"op": "add_element", "template": _bar_template(form_doc, "bottom", notes, desc["kind"]), "name": BAR_NAMES["bottom"],
                    "box": [n["bottom_bar_x"], height - bar_h, width - n["bottom_bar_x"], bar_h],
                    "anchor": {"h": "stretch", "v": "bottom"}})
    ops += copy.deepcopy(desc.get("tune", []))
    return ops, notes


# Фрагменты обработок по скелетам вида

# Скелет формы — строки верхнего уровня, в каждой набор видов элементов (`patterns._skeleton`). Фрагментами
# заведены два скелета: `pairs_run` — верх формы из одних пар «надпись + поле» и флажков, нижняя панель последней строкой; `params_sheet` — пары, панели
# и поле табличного документа, больше ничего (нижняя панель есть чаще, верхняя реже, обеих разом нет — умолчание `bar` «bottom»). Скелеты с таблицами,
# панелями закладок и прочие сложные фрагментами не заведены: общего вида у них нет.
FRAGMENTS = {
    "pairs_run": "сетка пар и нижняя панель команд (в ней «Выполнить» — из исходной формы)",
    "params_sheet": "параметры (сетка пар) и поле табличного документа",
}
FRAGMENT_BARS = (*BAR_PLACES, "none")
FRAGMENT_SHEET = "ТабличныйДокумент"          # имя поля `params_sheet` по умолчанию
FRAGMENT_BAR = "bottom"  # панель `params_sheet` по умолчанию: нижняя (чаще, чем верхняя)


def fragment(name, object_name, fields, title=None, columns=1, sheet=None, bar=None):
    """Описание формы обработки по скелету вида — заготовка, которую доводят `tune` и правкой блоков; отказ — `GenerateError`.

    `pairs_run` — `fields` (`columns` колонок пар) и нижняя панель команд; `sheet` и `bar` у него — отказ (молча проглоченный ключ называл бы выбором то,
    чего никто не делал). `params_sheet` — `fields`, поле табличного документа `sheet` (умолчание `FRAGMENT_SHEET`) и панель команд `bar`: `"top"` —
    первой, `"bottom"` — последней (умолчание), `"none"` — без неё. `fields` — то же, что в блоке `fields`: имена реквизитов обработки либо объекты
    `{"data", "source": "form", …}`. Движок описание проверит, как любое."""
    if name not in FRAGMENTS:
        raise GenerateError(f"фрагмента «{name}» нет; есть: {', '.join(f'{k} — {v}' for k, v in FRAGMENTS.items())}")
    if not isinstance(fields, list) or not fields:
        raise GenerateError("fields — непустой массив реквизитов (имя либо {\"data\": …, \"source\": \"form\"})")
    if not _is_int(columns) or not 1 <= columns <= MAX_COLUMNS:
        raise GenerateError(f"columns — целое от 1 до {MAX_COLUMNS}, а пришло {columns!r}")
    if bar is not None and bar not in FRAGMENT_BARS:
        raise GenerateError(f"bar — {', '.join(repr(b) for b in FRAGMENT_BARS)}, а пришло {bar!r}")
    if name == "pairs_run" and (sheet is not None or bar is not None):
        raise GenerateError("pairs_run: ключи sheet и bar ему не нужны (у него нет поля табличного документа, а панель одна — нижняя); "
                            "нужны они фрагменту params_sheet")
    grid = {"fields": copy.deepcopy(fields), **({"columns": columns} if columns != 1 else {})}
    if name == "pairs_run":
        blocks = [grid, {"command_bar": "bottom"}]
    else:
        bar = FRAGMENT_BAR if bar is None else bar
        blocks = [{"command_bar": "top"}] if bar == "top" else []
        blocks += [grid, {"spreadsheet": FRAGMENT_SHEET if sheet is None else sheet}]
        blocks += [{"command_bar": "bottom"}] if bar == "bottom" else []
    desc = {"kind": PROCESSING, "object": object_name, **({"title": title} if title else {}), "blocks": blocks}
    check_description(desc)
    return desc


# Командные панели: из исходной формы

def shell_bar(form_doc, place):
    """Командная панель исходной формы места `top`/`bottom` (копия узла) либо `None`. Сначала по имени платформы (`ДействияФормы`,
    `ОсновныеДействияФормы`), иначе по месту, как её видит перепись нормы (верх у верха формы; низ у низа формы)."""
    form = layout.read(form_doc)
    tables = {c.index for c in form.holders[0].children if c.type == "TableBox"}
    bars = [c for c in form.holders[0].children if c.type == "CommandBar"]
    # имя платформы важнее источника действий: панель `ДействияФормы` с источником-таблицей — всё равно панель формы
    named = next((c for c in bars if c.name == BAR_NAMES[place]), None)
    if named is None:
        # прочая панель с источником-таблицей — панель ТАБЛИЦЫ, формой не служит, как бы ни стояла: она остаётся таблице
        named = next((c for c in bars if (c.node.get("name_block") or {}).get("action_source") not in tables
                      and (c.box[1] < 12 if place == "top" else c.box[3] >= form.height - 2)), None)
    return copy.deepcopy(named.node) if named is not None else None


def _bar_template(form_doc, place, notes, kind=None):
    """Узел панели для `add_element`: панель ИСХОДНОЙ ФОРМЫ с её кнопками и автозаполнением (платформа ставит туда Записать, ОК,
    Закрыть, «Действия»), подвинутая под нормы; новая пустая — только когда в исходной форме такой нет, и это названо."""
    node = shell_bar(form_doc, place)
    if node is None:
        if place == "bottom":
            notes.append(f"в исходной форме нет нижней панели команд («{BAR_NAMES[place]}»): поставлена нижняя панель конструктора вида «{kind}» (источник действий — форма, "
                         "без автозаполнения): кнопки файлом со стандартными действиями формы (ОК, Записать, Закрыть у документа и элемента; Закрыть у обработки); "
                         "панель с автозаполнением внизу повторяет верхнюю; свои команды с обработчиком, в том числе «Выполнить», доводит `tune` (`add_button`)")
            return templates.form_bottom_bar_node(kind)
        notes.append("в исходной форме нет верхней панели команд («ДействияФормы»): поставлена панель с автозаполнением (источник действий — форма): "
                     "стандартные кнопки формы ставит платформа сама; свои команды с обработчиком доводит `tune` (`add_button`)")
        return templates.form_bar_node(place)
    notes.append(f"{'верхняя' if place == 'top' else 'нижняя'} панель команд «{BAR_NAMES[place]}» взята из исходной формы "
                 "вместе с её кнопками и автозаполнением")
    block = node.get("name_block") if isinstance(node.get("name_block"), dict) else {}
    tables = {c.index: c.name for c in layout.read(form_doc).holders[0].children if c.type == "TableBox"}
    if block.get("action_source") in tables:
        # панель формы с источником действий — таблицей: у новой копии индекс таблицы мог бы повиснуть
        notes.append(f"источник действий панели «{BAR_NAMES[place]}» исходной формы — табличное поле «{tables[block['action_source']]}», у панели формы "
                     "источник — форма: поставлен он")
        block["action_source"] = 0
    return node


# ── Самопроверка геометрии ────────────────────────────────────────────────────────────────────

def _inside(inner, outer):
    return (inner[0] >= outer[0] and inner[1] >= outer[1] and inner[0] + inner[2] <= outer[0] + outer[2]
            and inner[1] + inner[3] <= outer[1] + outer[3])


def _overlap(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _geometry_problems(items):
    """Соседи на одном родителе и одной странице не пересекаются (рамка с её полями — исключение), заданная ширина поля не
    меньше минимума платформы. Нарушение — слова, а не молча записанная форма: `layout.problems` статического наложения не ловит."""
    out = []
    groups = {}
    for item in _flat(items):
        groups.setdefault((item.holder, item.page), []).append(item)
        if item.template == "TextBox" and item.box[2] < PLATFORM_MIN_FIELD_W:
            out.append(f"поле «{item.name}» шириной {item.box[2]} уже минимума поля ввода платформы ({PLATFORM_MIN_FIELD_W})")
    for _where, there in groups.items():
        for at, a in enumerate(there):
            for b in there[at + 1:]:
                if "GroupBox" in (a.template, b.template):
                    frame, other = (a, b) if a.template == "GroupBox" else (b, a)
                    if _inside(other.box, frame.box):
                        continue
                if _overlap(a.box, b.box):
                    out.append(f"«{a.name}» {tuple(a.box)} и «{b.name}» {tuple(b.box)} налезают друг на друга")
    return out


# Высота поля по соседям

SIBLING_MIN_PAIRS = 10  # меньше пар во всех соседних формах — по ним вывода нет, остаётся норма вида (оценка)


def _pair_heights(path):
    """Высоты пар одной формы соседей: `(поля, надписи)`; нечитаемая форма — `None` (воркер пула процессов)."""
    if pathlib.Path(path).name.lower() == "form.bin":
        try:
            rec = census.record(typed.decode(formsource.read_form_node(path)), str(path))
        except Exception as exc:  # noqa: BLE001 — нечитаемый контейнер: сосед не учитывается
            return None
    else:
        rec = census.record_path(path)
    if rec.get("kind") == "error":
        return None
    found = patterns._measures(rec)
    return found.get("field_height", []), found.get("label_height", [])


def sibling_heights(root, mine=()):
    """Высота поля и надписи по соседям: самая частая у форм той же конфигурации (`*.frm` под каталогом, кроме `mine`).

    `{"values": {…}, "note": слова}`; соседей мало (меньше `SIBLING_MIN_PAIRS` пар) — `values` пусто, норма вида остаётся, и `note` говорит почему.
    Платформа ведёт высоту поля формы одну на конфигурацию (19 или 22), а не на вид объекта."""
    root = pathlib.Path(root)
    if not root.is_dir():
        raise GenerateError(f"каталога соседей нет: {root}")
    paths = formsource.sibling_paths(root, mine)
    bare = sum(1 for p in paths if p.name.lower() == "form.bin")
    if len(paths) > 20:
        import concurrent.futures
        with concurrent.futures.ProcessPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) - 2)) as workers:
            read = list(workers.map(_pair_heights, paths, chunksize=8))
    else:
        read = [_pair_heights(p) for p in paths]
    fields = collections.Counter(h for r in read if r for h in r[0])
    labels = collections.Counter(h for r in read if r for h in r[1])
    values, said = {}, []
    for key, counter in (("field_height", fields), ("label_height", labels)):
        total = sum(counter.values())
        if total < SIBLING_MIN_PAIRS:
            said.append(f"{key}: соседи дали {total} пар (меньше {SIBLING_MIN_PAIRS}) — норма вида")
            continue
        mode, count = min(counter.items(), key=lambda kv: (-kv[1], kv[0]))
        values[key] = mode
        said.append(f"{key} {mode} ({count} из {total} пар)")
    lost = sum(1 for r in read if r is None)
    return {"values": values, "note": f"высота по соседям — {root}: форм {len(paths)}"
            + (f" (из них {bare} прочитано из Form.bin без form.frm рядом)" if bare else "")
            + (f", не прочитано {lost}" if lost else "") + "; " + "; ".join(said)}


# ── Исполнение ────────────────────────────────────────────────────────────────────────────────

@dataclasses.dataclass
class Report:
    ops: int
    log: list
    warnings: list               # замечания проверки (уровень ниже отказа) и раскладки, появившиеся при генерации
    desc_sha256: str
    form_sha256: str
    out_path: str
    stamp_path: object
    size: int
    elements: dict               # вид элемента → число
    notes: list = dataclasses.field(default_factory=list)    # решения движка: панели из исходной формы, пропущенные колонки, источник высоты
    unchanged: bool = False      # описание и файл те же, что при прошлой генерации — файл не тронут
    mode: str = ""  # режим и почему: первая строка отчёта CLI; пусто — «ничего не изменилось»


def desc_sha256(desc):
    return hashlib.sha256(json.dumps(desc, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def stamp_path_of(desc_path):
    """`описание.json` → `описание.stamp.json` рядом с описанием."""
    path = pathlib.Path(desc_path)
    return path.with_name(path.stem + ".stamp.json")


@contextlib.contextmanager
def _deterministic_guids(seed):
    """`uuid.uuid4` на время сборки — производный от суммы описания: головы блоков действий новых панелей одинаковы от запуска к
    запуску. Подмена касается ВСЕГО процесса: для CLI и пула процессов верно, для потоков нет (два `apply` в потоках делили бы
    счётчик). У `add_element` параметра «GUID» нет — у `add_button` он есть; когда понадобятся потоки, ставить его туда."""
    counter = [0]

    def fake():
        counter[0] += 1
        return uuid.uuid5(uuid.NAMESPACE_URL, f"frm-json-v8/generate/{seed}/{counter[0]}")
    real, uuid.uuid4 = uuid.uuid4, fake
    try:
        yield
    finally:
        uuid.uuid4 = real


BLANK_MODE_LINE = ("Исходная форма — заготовка навыка (frm_json.py new): раскладка полная, бережный режим не включается — беречь в заготовке нечего")


def blank_kind_of(desc):
    """Вид заготовки под описание: у вида processing с объектом-отчётом (`ВнешнийОтчет.Имя`, `Отчет.Имя`) — `report`, иначе вид описания."""
    if desc["kind"] == PROCESSING and REPORT_PREFIX.match(str(desc.get("object", "")).strip()):
        return "report"
    return desc["kind"]


def blank_for_description(desc, config=None, config_dir=None, type_id=None, root_xml=None, dialog=False):
    """Заготовка формы под описание, когда исходной формы нет (`generate` без `--form`): `blank.Blank` либо `GenerateError`.

    Вид и объект берутся из описания; выгрузка — `config` (готовая) либо `config_dir`. Тип основного реквизита формы внешней обработки без
    выгрузки — `type_id` (GUID), `root_xml` (корневой XML выгрузки обработки) либо `dialog` (форма без основного реквизита); ни одного
    источника у вида `processing` — отказ (`blank.build`). GUID панелей выдаются от суммы описания, но в своём
    пространстве (`:blank`): с теми, что выдаст сама генерация, они не совпадут, а повторный вызов даёт ту же заготовку байт в байт."""
    check_description(desc)
    if config is None and config_dir is not None:
        try:
            config = metadata.load(config_dir)
        except metadata.MetadataError as e:
            raise GenerateError(f"выгрузка конфигурации: {e}") from None
    try:
        with _deterministic_guids(desc_sha256(desc) + ":blank"):
            # Названный ключ типа — источник типа заготовки; выгрузка у `generate` — справочник ссылочных типов и ему не мешает: заготовке её не отдают.
            keyed = type_id is not None or root_xml is not None or dialog
            blank_kind = blank_kind_of(desc)
            return blank_mod.build(blank_kind, object_name=desc["object"], config=None if keyed else config, type_id=type_id,
                                   root_xml=root_xml, dialog=dialog, for_generate=True)
    except blank_mod.BlankError as e:
        raise GenerateError(f"исходной формы нет, заготовка не собралась: {e}") from None


STAMP_KEYS = ("desc_sha256", "form_sha256", "shell_sha256")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _read_stamp(path):
    try:
        stamp = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise GenerateError(f"отметка перегенерации {path} не читается ({e}): удалите её или поправьте") from None
    if not (isinstance(stamp, dict) and set(stamp) == set(STAMP_KEYS) and all(isinstance(v, str) for v in stamp.values())):
        raise GenerateError(f"отметка {path}: ожидаются ровно ключи {', '.join(STAMP_KEYS)} строками")
    return stamp


def _elements_in(data):
    """Число элементов формы в файле (слова отказа); не разобралась — `None`."""
    try:
        doc = typed.decode(parse(data.decode("utf-8")))
        return sum(len((holder.get(edit.ELEMENTS) or {}).get(edit.ITEMS) or []) for _n, holder in ed_base.holders(doc))
    except Exception:  # noqa: BLE001 — слова отказа, а не проверка: форма, которую не разобрать, число не называет
        return None


def _loss(out_path, data):
    count = _elements_in(data)
    what = f"{count} элементов формы" if count is not None else "форму"
    return f"Перегенерация затёрла бы {what} {out_path} и все правки в ней (обработчики убранных элементов в form.bsl останутся)"


def check_target(stamp_path, out_path, shell_bytes, desc_hash, overwrite):
    """Что затирается и можно ли: сверяется файл `-o` (а не `--form`) с отметкой.

    `(слова, не менялось)`: «не менялось» — описание то же, а `-o` равен записанному прошлой генерацией (и дана та же исходная форма либо сам результат),
    файл трогать не надо. Отказ — `GenerateError` без `overwrite`:

    * отметки нет, а `-o` есть и это не та же исходная форма, что `--form`: форма без отметки — возможно, правлена руками;
    * отметка есть, а сумма `-o` не равна записанной: файл правили после генерации (или это не тот файл);
    * описание не названо (API без `desc_path`): отметки нет совсем, любая запись поверх существующего файла — только по ключу."""
    out = pathlib.Path(out_path)
    data = out.read_bytes() if out.exists() else None
    now = _sha(data) if data is not None else None
    if stamp_path is None:
        if data is None:
            return "описание не названо (desc_path): отметка не пишется, защиты правок нет", False
        if overwrite:
            return f"описание не названо (desc_path): файл {out_path} затёрт по ключу overwrite", False
        raise GenerateError(f"запись поверх существующего файла {out_path} без описания (desc_path): отметки перегенерации нет, "
                            f"и сверить файл не с чем. {_loss(out_path, data)}; дайте overwrite=True, если так и надо")
    if not pathlib.Path(stamp_path).exists():
        if data is None:
            return "отметки перегенерации нет, файла для записи нет — форма считается исходной формой", False
        if now == _sha(shell_bytes):
            return "отметки перегенерации нет; файл для записи — сама исходная форма (--form) — первая генерация", False
        if overwrite:
            return f"отметки перегенерации нет, файл {out_path} — не исходная форма --form: затёрт по ключу overwrite", False
        raise GenerateError(f"отметки {stamp_path} нет, а файл {out_path} существует и не равен исходной форме --form: форма без "
                            f"отметки — возможно, правлена руками (либо описание переименовали, и отметка осиротела). "
                            f"{_loss(out_path, data)}; дайте ключ --overwrite (overwrite=True), если так и надо, либо "
                            "перенесите правки в tune описания")
    stamp = _read_stamp(stamp_path)
    if data is None:
        return "файл для записи ещё не существует — генерация по отметке прошлого раза", False
    if now == stamp["form_sha256"]:
        same = stamp["desc_sha256"] == desc_hash and _sha(shell_bytes) in (stamp["shell_sha256"], stamp["form_sha256"])
        if same and not overwrite:
            return ("ничего не изменилось: описание то же, а файл равен записанному прошлой генерацией — файл не тронут "
                    "(метаданные и нормы в счёт не идут: сменились они — дайте --overwrite)"), True
        return "файл равен записанному прошлой генерацией — перегенерация", False
    if overwrite:
        return (f"файл {out_path} не равен записанному прошлой генерацией ({now[:12]} вместо {stamp['form_sha256'][:12]}) — "
                "затёрт по ключу overwrite"), False
    raise GenerateError(
        f"файл {out_path} правили после генерации: его сумма {now[:12]}…, а отметка {stamp_path} помнит "
        f"{stamp['form_sha256'][:12]}… (либо это не тот файл, что вышел в прошлый раз). {_loss(out_path, data)}; дайте ключ "
        "--overwrite (overwrite=True), если так и надо, либо перенесите правки в tune описания")


def _write_pair(pairs):
    """Файлы ПАРОЙ: временные рядом, потом переименование. Отказ ДО переименований (запись временных) оставляет диск прежним; сбой второго
    переименования — нет: первый файл уже на месте (форма записана, отметка прежняя либо её нет), и это названо в исключении."""
    made = []
    try:
        for path, data in pairs:
            target = pathlib.Path(path)
            tmp = target.with_name(target.name + ".tmp")
            tmp.write_bytes(data)
            made.append((tmp, target))
    except OSError:
        for tmp, _target in made:
            tmp.unlink(missing_ok=True)
        raise
    for at, (tmp, target) in enumerate(made):
        try:
            os.replace(tmp, target)
        except OSError as e:
            for rest, _t in made[at:]:
                rest.unlink(missing_ok=True)
            if at:
                raise GenerateError(f"{made[0][1]} уже записан, а {target} записать не удалось ({e}): форма и отметка разошлись — "
                                    "запустите генерацию снова с --overwrite") from None
            raise


def apply(desc, form_path, config_dir, out_path, overwrite=False, desc_path=None, norms=None, config=None, siblings=None, relayout=False, gentle_only=False, edit_of=None, edit_place=None, from_blank=False):
    """Описание → форма: исходная форма `form_path` + выгрузка `config_dir` → `out_path`; `Report`.

    Порядок несущий, как у `frm_json.py edit`: сначала вся работа и проверка, потом запись ПАРОЙ (форма и отметка). `desc_path` — файл описания: рядом с
    ним лежит отметка перегенерации; **без него защиты правок нет** — запись поверх существующего файла возможна только с `overwrite=True` (CLI
    `desc_path` передаёт всегда). Сверяется файл `out_path`, а не `form_path`. Описание то же и файл равен записанному — «ничего не изменилось», файл не
    тронут (`Report.unchanged`). `norms` — таблица норм (умолчание — `patterns.json`), `config` — готовая выгрузка вместо каталога, `siblings` — каталог
    соседних форм той же конфигурации: высота поля и надписи — самая частая у них.

    **Режим.** Исходная форма, не проходящая проверку обратным разбором «её `describe` → `generate`» (форма человека), правится БЕРЕЖНО: разница описаний `describe(исходной формы)` →
    `desc` становится операциями над ней, прочее не двигается (`generate_gentle`); форма движка и форма списка — как прежде. `relayout=True` — полная
    раскладка явно, для любой исходной формы. Слова о режиме — `Report.mode`. `edit_of` — имена реквизитов, добавленных поверх описания формы (команда `add-field`): вместо проверки «форма читается как описание» в бережном режиме проверяется, что `describe` после правки равен `describe` до неё плюс эти поля (`generate_gentle.edit_problems`). `gentle_only=True` — режим движка исключён (отказ вместо него; команда `add-field`); с `relayout` вместе не берётся."""
    check_description(desc)
    form_bytes = pathlib.Path(form_path).read_bytes()
    stamp = stamp_path_of(desc_path) if desc_path else None
    seed = desc_sha256(desc)
    said, unchanged = check_target(stamp, out_path, form_bytes, seed, overwrite)
    if unchanged:
        data = pathlib.Path(out_path).read_bytes()
        return Report(0, [said], [], seed, _sha(data), str(out_path), str(stamp), len(data), {}, [], True)
    if config is None and config_dir is None and desc.get("kind") != PROCESSING:
        raise GenerateError("выгрузка конфигурации (--config) нужна: вид «%s» привязывает поля к реквизитам объекта выгрузки; "
                            "без неё генерируется только вид processing (поля — реквизиты формы)" % desc.get("kind"))
    if config is None and config_dir is not None:
        try:
            config = metadata.load(config_dir)
        except metadata.MetadataError as e:
            raise GenerateError(f"выгрузка конфигурации: {e}") from None
    doc = typed.decode(read_file(form_path))
    shell_doc = copy.deepcopy(doc)
    table = norms if norms is not None else patterns.load()
    heights = sibling_heights(siblings, (form_path, out_path)) if siblings else None
    from . import generate_gentle
    if relayout and gentle_only:
        raise GenerateError("relayout и gentle_only вместе не берутся: одно включает полную раскладку, другое исключает её")
    if from_blank:
        verdict = generate_gentle.Verdict(False, BLANK_MODE_LINE)
    elif relayout:
        verdict = generate_gentle.Verdict(False, "Режим: полная раскладка — по ключу --relayout (форма перекладывается целиком по нормам вида)")
    else:
        verdict = generate_gentle.choose(desc, doc, config, table, heights, only=gentle_only)
    if verdict.gentle:
        ops, notes = generate_gentle.plan_notes(desc, doc, config, table, heights, verdict, edit_of=edit_of, edit_place=edit_place)
    else:
        ops, notes = plan_notes(desc, doc, config, table, heights)
        notes = notes + ["привязки новых элементов — роли движка по нормам вида; перебор вариантов привязки на модели раскладки применяется только в бережном режиме, "
                         "где элемент встаёт в форму человека"]
    try:
        with _deterministic_guids(seed):
            doc, _bsl, log = edit.apply(doc, ops, config=config)
    except ed_base.EditError as e:
        raise GenerateError(f"редактор отказал на операции из описания: {e}") from None
    problems = validate.validate(doc, config=config)
    if validate.fatal(problems):
        first = [p.text for p in problems if p.fatal][:3]
        raise GenerateError("собранная форма не проходит проверку: " + "; ".join(first))
    narrowed = limits.compare(shell_doc, doc)
    # Ужатая таблица (`shrink`) по замыслу поднимает минимальную высоту формы не больше чем на своё ужатие: отчёт места это называет, и отказом такое сужение не считается.
    refusing = limits.unforgiven(narrowed)
    if verdict.gentle and refusing:
        raise GenerateError(f"бережный режим: {limits.narrowed_words(refusing)}. Выходы: операция `set_anchors` в блоке "
                            "`tune` описания — явная роль или образец `{\"as\": \"<имя элемента>\"}` у нового элемента, либо `--relayout` (форма перекладывается целиком)")
    node = typed.encode(doc)                                  # самопроверка кодека: разбор своей сборки равен входу
    data = render(node).encode("utf-8")
    warnings = [p.text for p in problems if not p.fatal]
    warnings += [f"раскладка: {text}" for _kind, _path, text in layout.problems(doc)]
    notes = notes + [words for words in (limits.narrowed_words(narrowed), limits.widened_words(narrowed)) if words]
    form_sha = _sha(data)
    pairs = [(out_path, data)]
    if stamp is not None:
        mark = {"desc_sha256": seed, "form_sha256": form_sha, "shell_sha256": _sha(form_bytes)}
        pairs.append((stamp, (json.dumps(mark, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8")))
    _write_pair(pairs)
    kinds = {}
    for _name, holder in ed_base.holders(doc):
        for item in (holder.get(edit.ELEMENTS) or {}).get(edit.ITEMS) or []:
            kinds[item.get("type")] = kinds.get(item.get("type"), 0) + 1
    return Report(len(ops), [said] + log, warnings, seed, form_sha, str(out_path), str(stamp) if stamp else None, len(data), kinds,
                  notes, mode=verdict.line)
