"""Три уровня проверки JSON перед сборкой.

Уровень 1 проверяет форму против КАРТЫ, а не против `frm.schema.json` (тот генерируется из карты и служит редактору и человеку): второго описания
правил рядом с картой нет.

**Кому принадлежит ключ, решает `typed.slot_for` — тот же, что у записи.** Отказы разбора ключа приходят теми же словами, какими их скажет
`encode`, но собираются списком, а не роняют первым.

**Демоция здесь законна с обеих сторон.** Позиция, чьё значение виду карты не соответствует, теряет ИМЯ и зовётся `u<индекс>`: это не «неизвестный
ключ» и не «пропажа именованного». Требование структурное: на позиции стоит ровно одно поле, имя карты либо `u<индекс>`; удвоение и дыра называются
с адресом.

**Пропажей считается ДЫРА, а не короткий хвост.** Блок, у которого последних позиций нет вовсе, законен. Отказ идёт на позицию, ниже которой поля есть.

Уровень 2 сверяет связанное: счётчик списка с длиной списка, имена и индексы элементов, форму GUID:

* счётчик равен длине списка у ВСЯКОГО узла с повтором и полем `count`;
* имена элементов НА ВЕРХНЕМ УРОВНЕ формы не повторяются — повтор отказ. **Во вложенном списке** повтор — предупреждение (`_check_elements`);
* **сплошных индексов НЕ бывает, проверки на них нет намеренно**: индексы идут с пропусками (элемент удалён в конструкторе, номер остался за ним).
  Повтор индекса — отказ.

Предупреждение остаётся за четырьмя случаями. Первый — сырой узел: значение цело, но именами не разобрано; тип опознаётся по СОДЕРЖИМОМУ.
Второй — значение вне `seen`: отказ на невиданном числе запретил бы законную форму. **Где `seen` пуст, предупреждения нет** — непустой `seen`
у полей `version` формы, `dpi`, `mark` блока координат и у перечислений `Panel.PictureSize`, `Panel.ShowTabs`, `TableBox.InitialListView`
(у поля — перечень значений, у перечисления — пары «значение, сколько раз»). Третий — ДЛИНА блока вне виденных (`_check_lens`): короткий блок бывает
законным. Четвёртый — разошедшееся ЗЕРКАЛО: свойство палитры, лежащее по двум адресам одного якоря (ширина колонки, квалификаторы поля ввода, флаги
поля табличного документа), правят обычно по одному; платформа пишет оба вместе. Карта значения не синхронизирует: она описывает файл.

**Проверки привязок.** Встречные записи списков зависимых (`anchors.RECORD_LIST`) пишет редактор вместе с правилом; форма, собранная мимо операций
без записей, проходит `validate` молча, а без записи правило в предприятии мертво. Обратная сверка «запись называет существующий элемент» правилом
не становится: платформа не чистит ссылки на удалённых соседей. Проверяются страница в пределах родителя, сплошной порядок обхода и непустой пятый
или шестой список (`_check_placement`, `_check_coords`).

**Отказ уровня 1 на СЫРОМ узле один — блок координат** (`_coords_layout_broken`): блок с меткой 8, у которого счётчик списка обещает запись, а записи
нет, платформа читать отказывается целиком.

**Отказ уровня 1 на допустимом значении один — меню кнопки** (`_check_menu_sets`): GUID набора кнопок меню постоянный (`schema.MENU_BUTTON_SET`);
со случайным платформа форму открывает и сохраняет, но меню не выпадает. Рядом, уровнем 2, — владелец кнопки (`_check_owners`), GUID набора
КОМАНДНОЙ ПАНЕЛИ из словаря (`_check_panel_sets`) и ровно один набор у меню (`_check_menu_set_count`) — предупреждения: что ломает нарушение, не проверялось.

**Тип значения табличного поля** (`_check_table_types`, `frm_codec/tabletype.py`) — предупреждение уровня 2: тип поля, не равный типу
реквизита формы, к которому оно привязано (форма списка), и нулевой тип привязанного поля; с выгрузкой (`config`) — ещё тип таблицы на табличной
части, не равный `TypeId` части. С чужим типом платформа загружает форму, но колонки таблицы выбрасывает; разбор и сборка этого не видят.

**Вложенный элемент колонки проверяется в трёх местах.** Уровень 1 — форма конверта (`_check_packed`: содержимое есть, пустых кусков от нуля,
раскладка из двух имён) и неразобранный конверт (предупреждение с причиной: он соберётся теми же байтами). Уровень 2 — вид назван ДВАЖДЫ, GUID у
колонки и первым числом тела, и разошедшиеся — отказ (`_check_column_control`). Зеркала внутри тела считаются от элемента ЕГО вида
(`_mirrors_in_packed`).
"""
import json
import pathlib
from dataclasses import dataclass

from . import design, packed, schema, stat, typed
from .json0 import Dec, Json0Error, encode0
from .tokens import B64_LAYOUTS, B64_NORM, GUID_RE, NUM_RE
from .tree import Node, Scalar, render
from .datapaths import DATA_DIR

LEVELS = (1, 2, 3)

# Типы ЭЛЕМЕНТОВ формы — ответ карты на вопрос «что такое `Element`», взятый один раз. Свой разбор имени не годится: под префикс `Element.`
# попадают подэлементы и безымянные блоки. Это правило живёт в `schema.ABSTRACT["Element"]`.
ELEMENT_TYPES = frozenset(schema.variants("Element"))


def _commandbar_names():
    """Имена полей блока действий — спрошенные у карты, а не литералы: переименование отрезка иначе молча оставило бы проверку связей без дела.
    Берётся всё, где объявлено: два счётных списка блока действий, список пар и его ключ у набора кнопок, поле GUID у записи действия."""
    actions, button_sets = (s.name for s in schema.MAP["CommandBarActions"].runs.segments)
    buttons = schema.MAP["ButtonSet"].runs.segments[0]
    action_id = schema.MAP["CommandBarAction"].fields[1].name
    return actions, button_sets, buttons.name, buttons.key, action_id


COMMANDBAR_NAMES = _commandbar_names()


def _numbering_names():
    """Имена нумерации и ссылки — у карты: номер кнопки, последний выданный номер у головы блока, пара «GUID владельца + код» у набора и у описания
    действия. Ссылка названа ОДНИМИ словами у обоих видов описания (`ActionSpec.v1`, `ActionSpec.v4`), проверка берёт их у первого; совпадение
    имён проверяет `test_commandbar`."""
    number = schema.MAP["Element.CommandBarButton"].fields[7].name
    last_number = schema.MAP["CommandBarActions"].fields[2].name
    set_ref = schema.MAP["ButtonSet"].fields[1].name
    set_code = schema.MAP["ButtonSet"].fields[2].name
    ref_id = schema.MAP["ActionSpec.v1"].fields[1].name
    ref_code = schema.MAP["ActionSpec.v1"].fields[2].name
    return number, last_number, set_ref, set_code, ref_id, ref_code


NUMBERING_NAMES = _numbering_names()


def _owner_names():
    """Владелец кнопки, голова её блока и имя кнопки — у карты, ПО ПОЗИЦИЯМ. Голова позиции 1 имени не имеет, ключ у неё запасной. Владелец обязан
    быть GUID-полем."""
    fields = schema.MAP["Element.CommandBarButton"].fields
    owner = fields.get(6)
    if not isinstance(owner, schema.F) or owner.kind != schema.GUID:
        raise schema.SchemaError(
            "проверка владельца ждёт у Element.CommandBarButton на позиции 6 GUID-поле, а "
            f"карта держит там {owner!r}; правило устарело вместе с картой — поправьте его "
            "вместе с ней, а не обходите")
    head = schema.MAP["CommandBarActions"].fields.get(1)
    return owner.name, head.name if head is not None else "u1", fields[1].name


OWNER_NAMES = _owner_names()


def _carrier_names():
    """Блок имени элемента и имя в нём — у карты, по ТИПУ и ПОЗИЦИИ. Ими предупреждение о владельце называет РОДИТЕЛЬ кнопки — командную панель
    или кнопку-меню."""
    name_block = next(slot.name for slot in schema.MAP["Element.CommandBar"].fields.values()
                      if isinstance(slot, schema.N) and slot.type == "NameBlock")
    return name_block, schema.MAP["NameBlock"].fields[1].name


CARRIER_NAMES = _carrier_names()


def _carrier_of(doc, type_name, carrier):
    """Имя родителя для узла `type_name`: у элемента формы — его имя, у прочих — прежнее. Одно место на проверку формы (отказ на набор меню
    называет кнопку) и проверку связей (предупреждение о владельце называет родителя); заменяется на КАЖДОМ элементе — до блока действий доходит
    ближайший сверху."""
    if type_name not in ELEMENT_TYPES:
        return carrier
    name_block, name_key = CARRIER_NAMES
    block = doc.get(name_block) if isinstance(doc, dict) else None
    name = block.get(name_key) if isinstance(block, dict) else None
    return name if isinstance(name, str) else None


def _placement_names():
    """Имена размещения — у карты: страница и номер на странице (`page_sequence`) в блоке координат, сам блок координат у записи элемента, список элементов и его
    массив, поле-держатель страниц. Последние два ищутся ПО ТИПУ, а не по имени. Держатель страниц у формы и панели называется одинаково; берётся
    тот, что у формы."""
    coords_runs = schema.MAP["Coords"].runs.segments[-1].fields
    page, page_sequence = coords_runs[0].name, coords_runs[1].name
    element = schema.MAP["Element.Panel"].fields
    coords = next(slot.name for slot in element.values() if getattr(slot, "type", None) == "Coords")
    elements = next(slot.name for slot in element.values()
                    if getattr(slot, "type", None) == "Elements")
    items = schema.MAP["Elements"].repeat.name
    pages = next(slot.name for segment in schema.MAP["LayoutList"].runs.segments
                 if isinstance(segment, schema.Fixed)
                 for slot in segment.fields.values()
                 if getattr(slot, "type", None) == "PanelPages")
    return page, page_sequence, coords, elements, items, pages


PLACEMENT_NAMES = _placement_names()


def _page_names():
    """Узлы-списки страниц и имя поля «имя страницы» — у карты, по ТИПУ и ПОЗИЦИИ. Варианты выбора берутся все (`schema.variants`); имя поля —
    по позиции 6."""
    holders = tuple(name for name in schema.variants("PanelPages")
                    if getattr(schema.MAP[name].repeat, "type", None) == "Element.PanelPage")
    if not holders:
        raise schema.SchemaError("проверка страниц ждёт у выбора `PanelPages` вариант со "
                                 "списком `Element.PanelPage`, а карта его не держит")
    slot = schema.MAP["Element.PanelPage"].fields.get(6)
    if not isinstance(slot, schema.F):
        raise schema.SchemaError("проверка страниц ждёт у страницы поле на позиции 6 (имя), "
                                 f"а карта держит там {slot!r}")
    return holders, slot.name, schema.MAP[holders[0]].repeat.name


PAGE_HOLDERS, PAGE_NAME, PAGE_ITEMS = _page_names()


def _anchor_names():
    """Имена привязок и правил — у карты, ПО ПОЗИЦИЯМ: четыре стороны и оба правила (`Anchor` позиции 1 и 2) одним списком. Имя поля `object`
    берётся у `AnchorRule` — узел один на оба правила."""
    coords = schema.MAP["Coords"].fields
    anchors = tuple(slot.name for index, slot in sorted(coords.items())
                    if getattr(slot, "type", None) == "Anchor")
    if len(anchors) != 4:
        raise schema.SchemaError(
            f"проверка привязок ждёт у блока координат четыре стороны, а карта держит {anchors}")
    rules = tuple(slot.name for index, slot in sorted(schema.MAP["Anchor"].fields.items())
                  if getattr(slot, "type", None) == "AnchorRule")
    if not rules:
        raise schema.SchemaError("проверка привязок ждёт у привязки хотя бы одно правило "
                                 "(`AnchorRule`), а карта не держит ни одного")
    return anchors, rules, schema.MAP["AnchorRule"].fields[1].name


ANCHOR_NAMES = _anchor_names()

# −1 в файле формы — беззнаковое 4 294 967 295: так платформа отвечает «ссылки нет» в `NameBlock.action_source`, `default_control`, `title.u2`.
NO_REFERENCE = 4294967295


def _reference_names():
    """Имена ссылок на элемент вне блока координат — у карты, ПО ПОЗИЦИЯМ. Позиция 2 блока заголовка имени не имеет (ключ считается от её номера),
    но спрашивается у карты: литерал `u2` после появления имени искал бы то, чего в документе нет. Слоты берутся по ПОЗИЦИИ, а не поиском по имени —
    иначе карту не спрашивают, а утверждают ей имя. Промах любой строки — отказ СО СЛОВАМИ при импорте, а не `KeyError`."""
    def at(type_name, index, expect=None):
        node = schema.MAP[type_name]
        slot = node.fields.get(index)
        if slot is None or (expect is not None and getattr(slot, "type", None) != expect):
            raise schema.SchemaError(
                f"проверка ссылок ждёт у {type_name} на позиции {index} "
                + (f"узел {expect}" if expect else "поле")
                + f", а карта держит там {slot!r}; правило устарело вместе с картой — "
                  "поправьте его вместе с ней, а не обходите")
        return slot.name

    title = schema.MAP["Title"].fields
    reference = title[2].name if 2 in title else "u2"
    return (reference, at("Title", 1), at("Attributes", 1),
            at("Attributes", 3, "BindingList"), at("Attributes", 2, "AttributeList"),
            at("AttributeBinding", 0))


REFERENCE_NAMES = _reference_names()

# Две служебные пары ссылки: «никуда» у кнопки без действия и разделитель. Набором кнопок они не являются, и требовать от них набора значило бы
# предупреждать о каждой второй записи. Пара названа СЛОВОМ (смысл — в карте, `ActionSpec.v1`); проверка спрашивает только `pair in SERVICE_REFS`.
def _column_control_names():
    """Имена вложенного элемента колонки — у карты, ПО ПОЗИЦИЯМ: `(узел головы колонки, поле GUID типа, поле блока, поле конверта, поле
    содержимого, ключ выбора)`."""
    head = schema.COLUMN_HEAD
    fields = schema.MAP[head].fields
    control = fields[39]
    if not isinstance(control, schema.N) or control.type != "TableBoxColumn.Control":
        raise schema.SchemaError(f"проверка вложенного элемента ждёт у {head} на позиции 39 узел "
                                 f"TableBoxColumn.Control, а карта держит там {control!r}")
    element = schema.MAP[control.type].fields[0]
    content = schema.MAP[element.type].fields[packed.CONTENT]
    return (head, fields[38].name, control.name, element.name, content.name,
            schema.FORKS[content.type].key)


COLUMN_CONTROL_NAMES = _column_control_names()
# Голова колонки — выбор по виду вложенного элемента: согласие GUID и тела спрашивается у обоих строений (пустой GUID с блоком элемента
# ведёт во второе).
COLUMN_HEADS = frozenset(schema.variants(schema.COLUMN_HEAD_FORK))
ZERO_GUID = schema.ZERO_GUID


SERVICE_REFS = {("357c6a54-357d-425d-a2bd-22f4f6e86c87", 2147483647): "кнопка без действия",
                ("9d0a2e40-b978-11d4-84b6-008048da06df", 0): "разделитель"}


@dataclass(frozen=True)
class Problem:
    level: int
    fatal: bool
    where: str
    text: str
    kind: str = None      # род замечания там, где его печатают сводкой: `LENS` — длина блока вне виденных корпусом


LENS = "lens"


def fatal(problems):
    return any(p.fatal for p in problems)


def _where(path):
    return "/".join(str(p) for p in path) if path else "корень"


def _say(out, level, is_fatal, path, text):
    """Замечание с адресом в начале текста: список читают целиком, и адрес только в поле `where` терялся бы при печати одного текста."""
    out.append(Problem(level, is_fatal, _where(path), f"{_where(path)}: {text}"))


# ── Уровень 1: форма ──────────────────────────────────────────────────────────────────────────

def _check_raw(raw, type_name, path, out):
    """Предупреждение о сыром узле — с именем типа, если его удалось опознать. `pick_doc` здесь бесполезен: у сырого узла в JSON одно поле, а имя —
    абстрактное (`Element`). Поэтому из содержимого собирается дерево уровня 0 и спрашивается та же `pick`, что у `decode`.

    Предупреждения различаются последствиями. Сырой узел НЕИЗВЕСТНОГО типа собирается обратно байт в байт. Сырой узел ИЗВЕСТНОГО типа, которого
    разбор не раскрыл (строение не сошлось с картой), — тоже: разбор сборки вернёт тот же сырой узел, отказа нет. Сырой узел ИЗВЕСТНОГО типа, который
    разбор раскрыл бы (его положили сырым в JSON руками), не соберётся: разбор вернёт из него поля по именам, проверка обратным разбором не сойдётся,
    и `encode` откажет самопроверкой."""
    try:
        node = encode0(raw, path)
    except Json0Error as e:
        _say(out, 1, True, path, f"сырой узел не читается: {e}")
        return
    if not isinstance(node, Node):
        _say(out, 1, True, path, "сырой узел — это блок, и пишут его массивом; "
                                 f"под {typed.RAW} лежит {raw!r}")
        return
    picked = schema.pick(type_name, node) if node.children else type_name
    unpacked = None
    if picked in schema.MAP and schema.MAP[picked].packed is not None:
        try:
            packed.unpack_node(node)
            unpacked = True
        except packed.PackedError as e:
            unpacked = str(e)
    if picked is None:
        _say(out, 1, False, path, "узел лежит сырым, тип не опознан — карта его не знает, "
                                  "и это ожидаемо")
    elif isinstance(unpacked, str):
        # Упакованный элемент, которого разбор не раскрыл, — не «узел, известный карте, но сырой»: он соберётся теми же байтами, отказа записи не будет.
        _say(out, 1, False, path, f"упакованный элемент не раскрыт: {unpacked}. Строка base64 "
                                  "переносится как есть и собирается теми же байтами, но имён у его "
                                  "полей нет")
    elif picked == "Coords" and _coords_layout_broken(node, path, out):
        return
    elif picked == BUTTON_BODY and _button_layout_broken(node, path, out):
        return
    elif picked in schema.MAP and (schema.MAP[picked].fields or schema.MAP[picked].runs):
        if typed.RAW in typed.decode(node, picked, path):
            # Сырым его оставил сам разбор: строение узла с картой не сошлось. Сборка вернёт те же байты, разбор сборки — тот же сырой узел.
            why = schema.runs_failure(schema.MAP[picked], node.children) if schema.MAP[picked].runs else None
            _say(out, 1, False, path, f"узел лежит сырым, хотя карта знает его тип ({picked}): разбор не узнал его строения"
                                      + (f" ({why})" if why else "") + " и оставил его как есть. Сборка вернёт его байт в байт, "
                                      "отказа записи нет; полей внутри него операции не видят, и операции, которым они нужны, откажут")
        else:
            # Узел, который разбор раскрыл бы, положили сырым руками: сборка разберётся ИМЕНАМИ, и проверка обратным разбором не сойдётся сама с собой.
            _say(out, 1, False, path, f"узел лежит сырым, хотя карта знает его тип ({picked}) — "
                                      "значение цело, но именами полей не разобрано; уровень 3 и "
                                      "запись такой документ ОТКАЖУТ: разбор вернёт поля по именам, "
                                      "и проверка обратным разбором не сойдётся, пока узел не разобран")


# Метка блока координат, чью раскладку карта описывает отрезками (`Coords`). У метки 3 раскладка другая (счётных списков нет, 15 скалярных
# позиций); такие блоки уезжают сырыми с обычным предупреждением.
COORDS_LAYOUT_MARK = 8


def _coords_layout_broken(node, path, out):
    """Сырой блок координат с меткой 8 — ОТКАЗ уровня 1, а не предупреждение. `True` — сказали.

    Платформа сама пишет блоки с меткой 3, они законны. Блок с меткой 8, у которого счётчик списка обещает запись, а записи нет, платформа читать
    ОТКАЗЫВАЕТСЯ (конфигуратор не открывает обработку целиком: «Ошибка формата потока»). Общий текст про сырой узел здесь был бы неправдой: проверка
    обратным разбором байт в байт сходится, и предупреждение дало бы записи зелёный свет."""
    first = node.children[0] if node.children else None
    if not (isinstance(first, Scalar) and first.kind == "INT"
            and first.text == str(COORDS_LAYOUT_MARK)):
        return False
    why = schema.runs_failure(schema.MAP["Coords"], node.children)
    if why is None:
        return False
    _say(out, 1, True, path,
         f"блок координат не читается раскладкой карты: {why}. Платформа такой файл отвергает "
         "ЦЕЛИКОМ — конфигуратор не открывает обработку и говорит «Ошибка формата потока». "
         "За головой блока идут шесть счётных списков зависимых, и счётчик каждого "
         "обязан быть равен числу записей за ним, а запись — блоком {0, индекс элемента, "
         "сторона}; номер страницы, номер на странице и порядок обхода лежат ПОСЛЕ них, "
         "полями `page`, `page_sequence` и `tab_order`, а не числом на месте счётчика")
    return True


# Тело записи кнопки формы: узел, у которого раскладка развилась на два строения.
BUTTON_BODY = "Content.Button.u1"


def _button_layout_broken(node, path, out):
    """Сырое тело записи кнопки — ОТКАЗ уровня 1, а не предупреждение. `True` — сказали.

    Файл с флагом строения (`menu_mode` = 1 или 2) без блока платформа не читает: конфигуратор не открывает обработку («Ошибка формата потока»).
    Сырых тел платформа не пишет, поэтому сырое тело — «файл, которого платформа не писала», а не «карта чего-то не знает»; предупреждение дало бы
    записи зелёный свет, потому что проверка обратным разбором байт в байт сходится."""
    why = schema.runs_failure(schema.MAP[BUTTON_BODY], node.children)
    if why is None:
        return False
    _say(out, 1, True, path,
         f"тело записи кнопки не читается раскладкой карты: {why}. Платформа такой файл "
         "отвергает ЦЕЛИКОМ — конфигуратор не открывает обработку и говорит «Ошибка формата "
         "потока». `menu_mode` — это ФЛАГ СТРОЕНИЯ: при «Use» и «UseExtra» "
         "за головой узла стоит блок выпадающего меню (поле `menu`, тот же узел, что у "
         "командной панели), и весь хвост записи уезжает на позицию; при «DontUse» блока нет "
         "вовсе. Менять одно без другого нельзя — ни в файле, ни в JSON")
    return True


# Блок выпадающего меню — необязательный отрезок тела записи кнопки. Спрошен у карты: по нему уровень 1 узнаёт, что набор перед ним — набор МЕНЮ.
MENU_GATE = next(segment for segment in schema.MAP[BUTTON_BODY].runs.segments
                 if isinstance(segment, schema.Gated))


def _check_menu_sets(block, path, out, carrier=None, mode=None):
    """GUID набора кнопок МЕНЮ — ПОСТОЯННЫЙ, иное значение ОТКАЗ уровня 1.

    Со случайным GUID конфигуратор открывает и пересохраняет форму байт в байт, но в предприятии меню не выпадает. Проверка обратным разбором байт в байт такой файл
    проходит, поэтому предупреждения мало. Уровень 1 — потому что это сверка с КАРТОЙ: постоянное объявлено в `schema.CONSTS` у места употребления.

    **Совет в отказе — двум читателям.** Правящему руками — какое значение поставить в `ref_id`; работающему редактором — какую операцию звать, с каким
    режимом (`mode` — флаг головы тела кнопки) и на какой кнопке (`carrier`): адрес вида `items/4/content/u1` человеку не говорит ничего."""
    _actions, sets_key, _buttons, _id, _action_id = COMMANDBAR_NAMES
    set_ref = NUMBERING_NAMES[2]
    if not isinstance(block, dict):
        return
    menu = f"у меню кнопки {carrier!r}" if carrier else "у меню кнопки"
    button = f"кнопке {carrier!r}" if carrier else "этой кнопке"
    same = f"тем же режимом {mode!r}" if isinstance(mode, str) else "тем же режимом"
    for i, item in enumerate(block.get(sets_key) or ()):
        ref = item.get(set_ref) if isinstance(item, dict) else None
        guid = ref.get("guid") if isinstance(ref, dict) else None
        if not isinstance(guid, str) or guid == schema.MENU_BUTTON_SET:
            continue  # о форме значения скажет проверка формы
        was = f"— {guid}" if guid else "ПУСТ"
        _say(out, 1, True, path + (sets_key, i, set_ref),
             f"{menu} GUID набора кнопок МЕНЮ {was}, а у набора меню он ПОСТОЯННЫЙ: "
             f"{schema.MENU_BUTTON_SET} (ButtonSet.MenuButtons). Платформа такую форму откроет и "
             "сохранит, но меню не выпадет — ни в конструкторе, ни в 1С:Предприятии. "
             f"Правка руками: поставьте в `{set_ref}` этого набора "
             f"{schema.MENU_BUTTON_SET}. Редактором: вызовите `set_menu_mode` с {same} на "
             f"{button} — на существующем меню она ставит набору постоянный GUID сама")


def _check_level0(value, path, out):
    """Значение безымянной позиции: смысла нет, но видом формата оно быть обязано. Спрашивается тем же `encode0`, которым пишет сборка, — иначе
    `float`, `None` и обёртка не того вида роняли бы писатель крахом Python."""
    try:
        encode0(value, path)
    except Json0Error as e:
        out.append(Problem(1, True, _where(path), str(e)))


def _check_value(slot, value, path, out):
    """Значение названной позиции: имя ОБЯЗЫВАЕТ. Порядок отказов тот же, что у `typed._json_to_scalar`: «булево, а пришло» и «имени у кода нет» —
    разные причины."""
    if slot.kind == schema.BOOL:
        if not isinstance(value, bool):
            _say(out, 1, True, path, f"поле {slot.name} булево, а пришло {value!r}; "
                                     "у флага два значения, третьего формат не знает")
        return
    if slot.kind == schema.BITS:
        # Своими словами: у слова маски пять способов не сойтись (не объект, флага нет, флаг лишний, флаг не булев, остаток задевает названный бит).
        problem = typed.bits_shape_error(slot, value)
        if problem:
            _say(out, 1, True, path, problem)
        return
    if slot.kind == schema.ENUM:
        enum = schema.ENUMS.get(slot.enum)
        if isinstance(value, bool):
            _say(out, 1, True, path, f"поле {slot.name} — перечисление {slot.enum}, "
                                     "а пришло булево")
            return
        if isinstance(value, int):
            for known_name, code in (enum.codes.items() if enum else ()):
                if code == value:
                    _say(out, 1, True, path, f"у кода {value} перечисления {slot.enum} есть имя "
                                             f"{known_name!r} — его и пишут, иначе разбор вернёт "
                                             "не то, что записано")
                    return
            return  # код без имени — законен; о невиданном скажет уровень 2
        if isinstance(value, str) and not isinstance(value, Dec):
            known = ("карта знает " + ", ".join(sorted(enum.codes))) if enum else \
                    f"перечисления {slot.enum} в карте нет вовсе"
            if not enum or value not in enum.codes:
                _say(out, 1, True, path, f"значения {value!r} у перечисления {slot.enum} нет; "
                                         f"{known}")
            return
    if slot.kind == schema.TYPE and not isinstance(value, str):
        # Строже, чем `fits_json`: обёртку `{"guid": …}` тот пропускает, а разбор вернёт ИМЯ, и самопроверка `encode` объявит ошибкой кодека правку
        # руками. Строка нужна для проверки ОДНОГО узла по его типу, где выбора нет.
        _say(out, 1, True, path, f"поле {slot.name} — имя типа элемента, а пришло {value!r}; "
                                 f"карта знает {', '.join(sorted(schema.ELEMENT_GUIDS))}")
        return
    if slot.kind == schema.GUID and getattr(slot, "names", None) and isinstance(value, dict) and set(value) == {"guid"} \
            and schema.guid_name(slot, value["guid"]) is not None:
        _say(out, 1, True, path, f"у типа {value['guid']} есть имя {schema.guid_name(slot, value['guid'])!r} — его и пишут, иначе разбор "
                                 "вернёт не то, что записано")
        return
    try:
        fits = typed.fits_json(slot, value, path)
    except Json0Error as e:
        out.append(Problem(1, True, _where(path), str(e)))
        return
    if not fits:
        _say(out, 1, True, path, f"поле {slot.name} карта объявила видом {slot.kind}, а пришло "
                                 f"{value!r}; под этим именем пишут только то, что виду подходит, "
                                 "иначе разбор вернёт значение как u…")


def _occupy(at, index, name, path, out):
    if index in at:
        _say(out, 1, True, path, f"позиция {index} занята дважды — ключами {at[index]!r} и "
                                 f"{name!r}; у каждого значения файла ровно одно поле JSON")
        return False
    at[index] = name
    return True


def _gap_hint(node_type, path, carrier):
    """Совет к пропаже поля там, где пропажу чинит операция редактора: `{имя поля: совет}`. Случай один: у набора МЕНЮ кнопки пропал `ref_id` —
    `set_menu_mode` с режимом меню ставит постоянный GUID. Набор меню узнаётся местом: прямо в блоке меню (`MENU_GATE`)."""
    if node_type.name != "ButtonSet" or len(path) < 3 or path[-3] != MENU_GATE.name:
        return {}
    button = f"кнопке {carrier!r}" if carrier else "этой кнопке"
    return {NUMBERING_NAMES[2]: (
        f"У набора МЕНЮ кнопки значение здесь ПОСТОЯННОЕ — {schema.MENU_BUTTON_SET}. Правка "
        "руками: поставьте его. Редактором: вызовите `set_menu_mode` с тем же режимом на "
        f"{button} — на существующем меню она ставит набору постоянный GUID сама")}


def _check_gaps(at, node_type, path, out, spots=None, hint=None):
    """Дыра в середине: позиция без ключа там, где ниже неё ключи есть. Имя берётся у карты, если оно есть; у узла со счётными списками — из раскладки
    (`spots`). `hint` — совет к пропаже, которую чинит операция редактора (`_gap_hint`)."""
    for index in range(max(at, default=-1) + 1):
        if index in at:
            continue
        if spots is None:
            slot, fallback = schema.slot_at(node_type, index), f"u{index}"
            # Номер позиции у обычного блока постоянен; у блока со счётными списками он у каждой формы свой и в отказе читался бы как адрес.
            where = f" (позиция {index})"
        else:
            fallback, slot = spots.get(index, (f"u{index}", None))
            where = ""
        name = slot.name if isinstance(slot, (schema.F, schema.N)) else fallback
        tail = f". {hint[name]}" if hint and name in hint else ""
        _say(out, 1, True, path, f"нет поля {name}{where} — значение брать неоткуда, "
                                 f"а порядок детей блока держит формат{tail}")


def _check_shape(doc, type_name, path, out, carrier=None):
    """Форма узла против карты. `carrier` — имя ближайшего элемента сверху: его называет отказ на набор меню, у блока меню своего имени нет."""
    if not isinstance(doc, dict):
        _say(out, 1, True, path, f"карта ждёт здесь блок {type_name}, а пришло {doc!r}; "
                                 "блок пишут объектом с полями")
        return
    if set(doc) == {typed.RAW}:
        _check_raw(doc[typed.RAW], type_name, path, out)
        return
    try:
        picked = schema.pick_doc(type_name, doc)
    except schema.SchemaError as e:
        out.append(Problem(1, True, _where(path), f"{_where(path)}: {e}"))
        return
    if picked is None and type_name in schema.ABSTRACT:
        # Отказ называет ВЫБОР, а не первый ключ: иначе человек шёл бы искать пропавшее поле, которое у него на месте.
        _say(out, 1, True, path, "тип узла не опознан по значениям, которые его называют; "
                                 f"карта знает {', '.join(schema.variants(type_name))}")
        return
    type_name = picked or type_name
    node_type = schema.MAP.get(type_name)
    if node_type is None:
        _say(out, 1, True, path, f"карта не знает типа узла {type_name}")
        return
    carrier = _carrier_of(doc, type_name, carrier)
    if type_name == schema.COLUMN_HEAD_BARE and isinstance(doc.get(COLUMN_CONTROL_NAMES[2]), dict):
        _say_bare_head(path, out)
        return
    if node_type.runs is not None:
        _check_runs_shape(doc, node_type, type_name, path, out, carrier)
        return
    by_name = {slot.name: (index, slot) for index, slot in node_type.fields.items()}
    repeat = node_type.repeat
    at = {}
    for name, value in doc.items():
        if repeat is not None and name == repeat.name:
            if not isinstance(value, list):
                _say(out, 1, True, path, f"{name} — список узлов {repeat.type}, "
                                         f"а пришло {value!r}")
                continue
            for i, item in enumerate(value):
                if _occupy(at, repeat.start + i, f"{name}[{i}]", path, out):
                    _check_shape(item, repeat.type, path + (name, i), out, carrier)
            continue
        try:
            index, slot = typed.slot_for(node_type, type_name, by_name, name, value, path)
        except ValueError as e:
            # Отказы разбора ключа (`TypedError`) и уровня 0 (`Json0Error`) уже несут адрес и причину.
            out.append(Problem(1, True, _where(path), str(e)))
            continue
        if not _occupy(at, index, name, path, out):
            continue
        if isinstance(slot, schema.N):
            _check_shape(value, slot.type, path + (name,), out, carrier)
        elif slot is None:
            _check_level0(value, path + (name,), out)
        else:
            _check_value(slot, value, path + (name,), out)
    _check_gaps(at, node_type, path, out)
    if node_type.packed is not None:
        _check_packed(doc, node_type, path, out)


def _say_bare_head(path, out):
    """Пустой GUID вложенного элемента при блоке элемента — ОТКАЗ уровня 1. Пустой GUID ведёт в ДРУГОЕ строение (`schema.COLUMN_HEAD_BARE`) —
    без блока элемента, с хвостом на позицию ближе и зеркалом ширины на 44; блок на позиции 39 ему чужой, платформа такой головы не пишет.
    Здесь названа причина, а не следствие общего разбора."""
    type_key, control_key = COLUMN_CONTROL_NAMES[1], COLUMN_CONTROL_NAMES[2]
    _say(out, 1, True, path + (control_key,),
         f"вложенный элемент есть, а тип у колонки пустой ({type_key} — нулевой GUID); при пустом "
         "типе голова колонки другого строения: блока элемента в ней нет, и всё, что за ним, "
         "стоит на позицию ближе — зеркало ширины на 44, а не на 45 (выбор "
         f"{schema.COLUMN_HEAD_FORK}). Сменить вид элемента — set_column_control; снять элемент у колонки "
         "операцией нечем")


def _check_packed(doc, node_type, path, out):
    """Упакованный элемент: то, чего вид поля карты не говорит. Содержимое обязательно; число пустых кусков — целое от нуля; раскладка — одно из двух
    имён. Отказы те же, что у записи (`packed.pack_node`), но списком."""
    fields = node_type.fields
    content, empty, layout = (fields[packed.CONTENT].name, fields[packed.EMPTY].name,
                              fields[packed.LAYOUT].name)
    if content not in doc:
        _say(out, 1, True, path, f"нет поля {content} — упакованный элемент без содержимого "
                                 "собрать нечем")
    count = doc.get(empty)
    if empty not in doc:
        _say(out, 1, True, path, f"нет поля {empty} — число пустых кусков за телом записывается всегда, "
                                 "даже нулём: из содержимого оно не выводится")
    elif isinstance(count, int) and not isinstance(count, bool) and count < 0:
        _say(out, 1, True, path + (empty,), f"пустых кусков {count}, а их бывает от нуля")
    mark = doc.get(layout)
    if layout in doc and (mark not in B64_LAYOUTS or mark == B64_NORM):
        _say(out, 1, True, path + (layout,),
             f"раскладки base64 {mark!r} здесь не бывает: признак ставят, когда она не норма — "
             f"{', '.join(x for x in B64_LAYOUTS if x != B64_NORM)}; норму пишут молчанием")


def _check_runs_shape(doc, node_type, type_name, path, out, carrier=None):
    """Форма узла со счётными списками. Раскладку считает та же `schema.doc_runs`, что и запись: второй вычислитель разошёлся бы с первым.
    Отказ раскладки (списка нет, длина парного отрезка не сошлась со страницами) останавливает разбор — без раскладки у ключей нет позиций."""
    try:
        spots, lists = schema.doc_runs(node_type, doc)
    except schema.SchemaError as e:
        _say(out, 1, True, path, str(e))
        return
    by_name, by_fallback = {}, {}
    for index, (fallback, slot) in spots.items():
        by_fallback[fallback] = (index, slot)
        if slot is not None:
            by_name[slot.name] = (index, slot)
    runs = {segment.name: (segment, start, members) for segment, start, members in lists}
    at = {}
    for name, value in doc.items():
        if name in runs:
            segment, start, members = runs[name]
            counter = schema.counter_index(segment, start)
            if counter is not None:
                at[counter] = f"счётчик {name}"
            if isinstance(segment, schema.Flagged):
                at[start] = f"слово флагов {name}"
                picked = [bit for bit in segment.bits if bit in value]
                for bit, index in zip(picked, members):
                    if _occupy(at, index, f"{name}.{bit}", path, out):
                        _check_shape(value[bit], segment.bits[bit][1],
                                     path + (name, bit), out, carrier)
                continue
            if isinstance(segment, schema.Masked):
                # Слово маски занимает позицию, а объектом не бывает: биты со значением проверяются каждый своим видом, биты без значения `doc_runs` уже потребовала булевыми.
                at[start] = f"слово маски {name}"
                picked = [bit for bit in segment.bits if bit in value]
                for bit, index in zip(picked, members):
                    if _occupy(at, index, f"{name}.{bit}", path, out):
                        _check_value(schema.masked_slot(segment, bit), value[bit],
                                     path + (name, bit), out)
                continue
            if isinstance(segment, schema.Gated):
                # Мест либо одно, либо ни одного, и решил это флаг головы: `doc_runs` уже отказала, если документ с ним не сходится.
                for index in members:
                    if _occupy(at, index, name, path, out):
                        _check_shape(value, segment.type, path + (name,), out, carrier)
                        if segment == MENU_GATE:
                            _check_menu_sets(value, path + (name,), out, carrier,
                                             doc.get(segment.by))
                continue
            if isinstance(segment, schema.CountedPairs):
                for i, (index, item) in enumerate(zip(members, value)):
                    key_at = schema.pair_key_index(index)
                    if not _occupy(at, key_at, f"{name}[{i}].{segment.key}", path, out) \
                            or not _occupy(at, index, f"{name}[{i}]", path, out):
                        continue
                    if not isinstance(item, dict):
                        _say(out, 1, True, path + (name, i),
                             f"член списка {name} — объект с полями узла {segment.type} и "
                             f"ключом {segment.key}, а пришло {item!r}")
                        continue
                    if segment.key not in item:
                        _say(out, 1, True, path + (name, i),
                             f"у члена списка {name} нет поля {segment.key} — этим ключом он "
                             "связан с записью действия, и взять его больше неоткуда")
                        continue
                    _check_value(typed.pair_key_slot(segment), item[segment.key],
                                 path + (name, i, segment.key), out)
                    _check_shape({k: v for k, v in item.items() if k != segment.key},
                                 segment.type, path + (name, i), out, carrier)
                continue
            for i, (index, item) in enumerate(zip(members, value)):
                if not _occupy(at, index, f"{name}[{i}]", path, out):
                    continue
                if isinstance(segment, schema.Counted):
                    _check_shape(item, segment.type, path + (name, i), out, carrier)
                else:
                    _check_value(typed.along_slot(segment), item, path + (name, i), out)
            continue
        try:
            index, slot = typed.slot_in_runs((by_name, by_fallback), type_name, name, value, path)
        except ValueError as e:
            out.append(Problem(1, True, _where(path), str(e)))
            continue
        if not _occupy(at, index, name, path, out):
            continue
        if isinstance(slot, schema.N):
            _check_shape(value, slot.type, path + (name,), out, carrier)
        elif slot is None:
            _check_level0(value, path + (name,), out)
        else:
            _check_value(slot, value, path + (name,), out)
    _check_gaps(at, node_type, path, out, spots=spots,
                hint=_gap_hint(node_type, path, carrier))


# ── Уровень 2: связи ──────────────────────────────────────────────────────────────────────────

def _check_elements(items, path, out, nested=False):
    """Имена и индексы элементов списка. Про пропуски в индексах см. описание модуля.

    **Повтор ИМЕНИ во вложенном списке — предупреждение, а не отказ**: на верхнем уровне формы повторов нет, внутри панели они бывают (в одной
    панели две «Надпись3»), и отказ запретил бы собрать обратно то, что платформа написала сама. Повтор ИНДЕКСА — отказ везде: индекс уникален по
    всей форме, а не только внутри списка."""
    names, indexes = {}, {}
    for i, item in enumerate(items):
        if not isinstance(item, dict) or typed.RAW in item:
            continue
        name_block = item.get("name_block")
        if isinstance(name_block, dict) and isinstance(name_block.get("name"), str):
            names.setdefault(name_block["name"], []).append(i)
        index = item.get("index")
        if isinstance(index, int) and not isinstance(index, bool):
            indexes.setdefault(index, []).append(i)
    for name, at in sorted(names.items()):
        if len(at) > 1:
            _say(out, 2, not nested, path,
                 f"имя элемента {name!r} стоит у {len(at)} элементов "
                 f"(места {', '.join(str(i) for i in at)}); по имени элемент ищут и билет, и "
                 "генератор" + (", и найдут они один из них. Внутри вложенного списка такое "
                                "бывает в настоящих формах, поэтому предупреждение; на "
                                "верхнем уровне формы это отказ" if nested else ""))
    for index, at in sorted(indexes.items()):
        if len(at) > 1:
            _say(out, 2, True, path, f"индекс {index} стоит у {len(at)} элементов "
                                     f"(места {', '.join(str(i) for i in at)}); "
                                     "пропуски в индексах законны, повторы — нет")


def _element_indexes(doc):
    """Индексы ВСЕХ элементов формы, любой глубины. Пустое множество — форма не разобрана."""
    _page, _order, _coords, elements_name, items_name, _pages = PLACEMENT_NAMES
    out = set()

    def walk(items):
        for item in items or ():
            if not isinstance(item, dict):
                continue
            index = item.get("index")
            if isinstance(index, int) and not isinstance(index, bool):
                out.add(index)
            holder = item.get(elements_name)
            walk(holder.get(items_name) if isinstance(holder, dict) else None)

    block = doc.get("form")
    container = block.get("container") if isinstance(block, dict) else None
    holder = container.get(elements_name) if isinstance(container, dict) else None
    walk(holder.get(items_name) if isinstance(holder, dict) else None)
    return out


def _elements_with_paths(doc, path):
    """Записи элементов любой глубины вместе с адресом в документе. Пара к `_element_indexes`: правилам, которые говорят словами, нужен адрес."""
    _page, _order, _coords, elements_name, items_name, _pages = PLACEMENT_NAMES

    def walk(holder, here):
        items = holder.get(items_name) if isinstance(holder, dict) else None
        for i, item in enumerate(items or ()):
            if not isinstance(item, dict):
                continue
            at = here + (items_name, i)
            yield at, item
            yield from walk(item.get(elements_name), at + (elements_name,))

    block = doc.get("form")
    container = block.get("container") if isinstance(block, dict) else None
    if isinstance(container, dict):
        yield from walk(container.get(elements_name),
                        path + ("form", "container", elements_name))


def _check_anchor_rules(doc, indexes, path, out):
    """Правило привязки, называющее элемент, которого в форме нет, — уровень 2. Правил у привязки ДВА (узел `AnchorRule` один), проверка одна.
    Висячую ссылку в правиле оставляет только правка мимо операций редактора.

    С записями списков зависимых это не путать: платформа не чистит ссылки на удалённых соседей, поэтому предупреждения о них нет.

    Предупреждение, а не отказ: платформа такую форму открывает (ссылку на удалённую кнопку она терпит и сбрасывает сама)."""
    anchors, rules, object_name = ANCHOR_NAMES
    offset_name = schema.MAP["AnchorRule"].fields[3].name
    for at, item in _elements_with_paths(doc, path):
        coords = item.get(PLACEMENT_NAMES[2])
        if not isinstance(coords, dict):
            continue
        for side in anchors:
            anchor = coords.get(side)
            if not isinstance(anchor, dict):
                continue
            for rule_name in rules:
                rule = anchor.get(rule_name)
                value = rule.get(object_name) if isinstance(rule, dict) else None
                shift = rule.get(offset_name) if isinstance(rule, dict) else None
                if value == -1 and isinstance(shift, int) and not isinstance(shift, bool) and shift != 0:
                    # Пересчёт привязок не пишет шаг в ПУСТОЕ правило: платформа так не пишет; влияние на предприятие не проверялось.
                    _say(out, 2, False, at + (PLACEMENT_NAMES[2], side, rule_name, offset_name),
                         f"пустое правило привязки (объект −1) несёт смещение {shift}: платформа пишет пустое правило {{-1, 6, 0}}")
                    continue
                if not isinstance(value, int) or isinstance(value, bool) \
                        or value <= 0 or value in indexes:
                    continue
                _say(out, 2, False,
                     at + (PLACEMENT_NAMES[2], side, rule_name, object_name),
                     f"привязка называет элемент {value}, а элемента с таким индексом в форме "
                     "нет. «Привязки нет» пишется правилом {2, -1, 6, 0}")


def _check_references(doc, path, out):
    """Ссылки на элемент ВНЕ блока координат и реквизиты формы — уровень 2.

    * `title.u2` — ссылка на элемент по индексу; удалённую кнопку платформа сбрасывает в −1;
    * `last_index` не меньше наибольшего индекса элемента;
    * привязка данных называет существующий элемент;
    * `next_id` больше наибольшего id реквизита.

    Ни одно не отказ: платформа это ТЕРПИТ (форму с ссылкой на удалённую кнопку открывает и правит число сама; отставший счётчик оставляет
    отставшим даже после пересохранения). Записи зависимого в блоке координат «называет существующий элемент» здесь НЕТ — висячие там
    обычны. Правило для САМИХ правил привязки — `_check_anchor_rules`.

    Проверки реквизитов идут и тогда, когда элементов не нашлось: повтор id и `next_id` элементам не нужны."""
    reference, last_index_name, next_id_name, bindings_name, rows_name, element_name = \
        REFERENCE_NAMES
    indexes = _element_indexes(doc)
    if indexes:
        _check_anchor_rules(doc, indexes, path, out)
    block = doc.get("form")
    title = block.get("title") if isinstance(block, dict) else None
    if isinstance(title, dict) and indexes:
        value = title.get(reference)
        if isinstance(value, int) and not isinstance(value, bool) \
                and value != NO_REFERENCE and value not in indexes:
            _say(out, 2, False, path + ("form", "title", reference),
                 f"ссылка на элемент {value}, а элемента с таким индексом в форме нет. "
                 f"«Ссылки нет» пишется числом {NO_REFERENCE}; висячую платформа терпит и "
                 "сбрасывает сама при первом сохранении, но до тех пор это ссылка в "
                 "никуда")
        last_index = title.get(last_index_name)
        if isinstance(last_index, int) and not isinstance(last_index, bool) \
                and last_index < max(indexes):
            _say(out, 2, False, path + ("form", "title", last_index_name),
                 f"{last_index_name} = {last_index}, а наибольший индекс элемента "
                 f"{max(indexes)}: следующий заведённый элемент получит номер, который уже "
                 "занят. Платформа это терпит (отставший счётчик пересохранение не "
                 "поднимает), поэтому предупреждение, а не отказ")
    attributes = doc.get("attributes")
    if not isinstance(attributes, dict):
        return
    rows = attributes.get(rows_name)
    items = rows.get("items") if isinstance(rows, dict) else None
    ids = []
    for row in items or ():
        head = row.get("u0") if isinstance(row, dict) else None
        if isinstance(head, list) and len(head) == 1 and isinstance(head[0], int) \
                and not isinstance(head[0], bool):
            ids.append(head[0])
    seen = {}
    for i, value in enumerate(ids):
        seen.setdefault(value, []).append(i)
    for value, at in sorted(seen.items()):
        if len(at) > 1:
            _say(out, 2, False, path + ("attributes", rows_name),
                 f"id реквизита {value} стоит у {len(at)} реквизитов (места "
                 f"{', '.join(str(i) for i in at)}); привязка данных адресует реквизит этим "
                 "числом, и по двойнику она попадёт в один из них наугад")
    next_id = attributes.get(next_id_name)
    if ids and isinstance(next_id, int) and not isinstance(next_id, bool) \
            and next_id <= max(ids):
        _say(out, 2, False, path + ("attributes", next_id_name),
             f"{next_id_name} = {next_id}, а наибольший id реквизита {max(ids)}: следующий "
             "заведённый реквизит получит номер, который уже занят")
    bindings = attributes.get(bindings_name)
    members = bindings.get("items") if isinstance(bindings, dict) else None
    for i, bind in enumerate(members or ()):
        value = bind.get(element_name) if isinstance(bind, dict) else None
        if isinstance(value, int) and not isinstance(value, bool) and value not in indexes:
            _say(out, 2, False, path + ("attributes", bindings_name, i, element_name),
                 f"привязка данных называет элемент {value}, а элемента с таким индексом в "
                 "форме нет (в отличие от списков зависимых блока координат, висячих "
                 "ссылок здесь не бывает)")


def _pages_of(value, pages_name, depth=3):
    """Сколько страниц у родителя: ищем держатель страниц в его собственном блоке. `None` — нет. Поиском, а не адресом: у контейнера формы держатель
    лежит через `layout_holder/layout_list`, у панели — внутри блока содержимого под безымянной позицией (`u1`)."""
    if not isinstance(value, dict) or depth < 0:
        return None
    holder = value.get(pages_name)
    if isinstance(holder, dict) and isinstance(holder.get("items"), list):
        return len(holder["items"])
    for key, inner in value.items():
        if isinstance(inner, dict):
            found = _pages_of(inner, pages_name, depth - 1)
            if found is not None:
                return found
    return None


def _check_placement(doc, pages, path, out):
    """Страница и порядок обхода у элементов ОДНОГО родителя — уровень 2:

    * номер страницы укладывается в число страниц родителя;
    * порядок обхода у каждой пары «родитель, страница» идёт СПЛОШНЯКОМ 0…N−1.

    Предупреждение, а не отказ: обе величины платформа досчитывает сама. Но страница вне родителя прячет элемент, а повтор порядка обхода уводит
    Tab не туда."""
    page_name, order_name, coords_name, _elements, _items, _pages = PLACEMENT_NAMES
    by_page = {}
    for i, item in enumerate(doc):
        coords = item.get(coords_name) if isinstance(item, dict) else None
        if not isinstance(coords, dict) or typed.RAW in coords:
            continue
        page, order = coords.get(page_name), coords.get(order_name)
        if isinstance(page, int) and not isinstance(page, bool):
            if pages is not None and not 0 <= page < pages:
                _say(out, 2, False, path + (i, coords_name, page_name),
                     f"страница {page}, а у родителя их {pages} (счёт с нуля): такой элемент "
                     "лежит на странице, которой нет, и в конструкторе его не видно")
            if isinstance(order, int) and not isinstance(order, bool):
                by_page.setdefault(page, []).append((order, i))
    for page, seen in sorted(by_page.items()):
        orders = sorted(o for o, _i in seen)
        if orders == list(range(len(orders))):
            continue
        _say(out, 2, False, path,
             f"порядок обхода на странице {page} — {', '.join(str(o) for o in orders)}, а он "
             f"идёт сплошняком 0…{len(orders) - 1} в пределах страницы родителя. Платформа пересчитает его при первом сохранении — "
             "то есть собранный файл откроется, но Tab пойдёт не туда, пока его не пересчитали")


def _check_pages(items, path, out):
    """Имена страниц одного родителя не повторяются — уровень 2. По имени страницу ищет редактор (`add_page`, `remove_page`), повтор увёл бы
    правку в первую попавшуюся. Предупреждение, а не отказ: платформа сама пишет формы с двумя страницами с ПУСТЫМ именем."""
    names = {}
    for i, item in enumerate(items):
        if not isinstance(item, dict) or typed.RAW in item:
            continue
        name = item.get(PAGE_NAME)
        if isinstance(name, str):
            names.setdefault(name, []).append(i)
    for name, at in sorted(names.items()):
        if len(at) > 1:
            _say(out, 2, False, path,
                 f"имя страницы {name!r} стоит у {len(at)} страниц родителя "
                 f"(места {', '.join(str(i) for i in at)}); по имени страницу ищет редактор, и "
                 "найдёт он первую. Платформа сама пишет формы с двумя страницами с пустым "
                 "именем, поэтому предупреждение, а не отказ")


def _check_coords(doc, path, out):
    """Пятый и шестой счётные списки блока координат — уровень 2. Они пусты у всех виденных блоков: запись туда даёт файл, которого платформа не
    писала; тип члена объявлен по строению отрезка, а не по наблюдению. Не отказ («не видели» не значит «нельзя»), но единица на месте этого
    счётчика ломает форму для платформы."""
    for name in ("list5", "list6"):
        members = doc.get(name)
        if isinstance(members, list) and members:
            _say(out, 2, False, path + (name,),
                 f"{schema.plural(len(members), 'запись', 'записи', 'записей')} в списке "
                 f"{name}, а платформа его не заполняет: членов в нём не видел "
                 "никто, и тип члена карта объявила по строению отрезка, а не по наблюдению")


def _pattern_names():
    """Имена квалификаторов блока типа — у карты, по ПОЗИЦИЯМ вариантов выбора: у Числа длина 1 и точность 2, у Строки длина 1."""
    number = schema.MAP["PatternType.N"].fields
    string = schema.MAP["PatternType.S"].fields
    return (schema.variants("PatternType"), number[0].name,
            number[1].name, number[2].name, string[1].name)


PATTERN_TYPES, PATTERN_KIND, PATTERN_DIGITS, PATTERN_FRACTION, PATTERN_LENGTH = _pattern_names()


def _check_pattern(doc, path, out):
    """Квалификаторы блока типа — уровень 2:

    * **точность не больше длины** (у блоков с буквой `N`): правило проверено по формам, а не взято из справки по языку;
    * **отрицательных квалификаторов формы не содержат**: длина числа от 0 до 42, точность от 0 до 12, длина строки от 1 до 1 024; проверка называет
      этот предел.

    Предупреждение, а не отказ: что платформа покажет в палитре для такого описателя, не проверялось."""
    for name in (PATTERN_DIGITS, PATTERN_FRACTION, PATTERN_LENGTH):
        value = doc.get(name)
        if isinstance(value, int) and not isinstance(value, bool) and value < 0:
            _say(out, 2, False, path + (name,),
                 f"{name} = {value}, а квалификаторы не бывают отрицательными: длина "
                 "числа от 0 до 42, точность от 0 до 12, длина строки от 1 до 1 024")
    digits, fraction = doc.get(PATTERN_DIGITS), doc.get(PATTERN_FRACTION)
    if all(isinstance(v, int) and not isinstance(v, bool) for v in (digits, fraction)) \
            and fraction > digits:
        _say(out, 2, False, path,
             f"{PATTERN_FRACTION} = {fraction} больше, чем {PATTERN_DIGITS} = {digits}: у блоков "
             "с буквой N точность не может превышать длину")


_SHAPES = []


def pattern_shapes():
    """Таблица форм записи блоков типа и типизированных значений по корпусу (`pattern_shapes.json`; считается по корпусу) — один раз на процесс."""
    if not _SHAPES:
        path = DATA_DIR / "pattern_shapes.json"
        _SHAPES.append(json.loads(path.read_text(encoding="utf-8")))
    return _SHAPES[0]


def _text_of(value):
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, str)):
        return str(value)
    return None


def _check_shape_seen(doc, picked, path, out):
    """Форма блока типа и типизированного значения — уровень 2, ОТКАЗ.

    Число позиций блока при данной букве и значения позиций с малым набором (второе число строки — 0 или 1, состав даты — `D` или `T`, знак числа,
    булево значение) обязаны быть виденными корпусом: блок типа — маленький и читается платформой жёстко. `{"S",20}` (длина без второго числа) в корпусе
    нет ни разу, и платформа такую форму не открыла: «Ошибка формата потока». Остальные блоки с буквой (число, дата, булево, ссылка, типизированное
    значение) проверяются тем же правилом: не виденная корпусом форма отказ, а не замечание."""
    table = pattern_shapes()
    seen = table["shapes"].get(picked)
    if seen is None:
        return
    count = len(doc)
    if str(count) not in seen:
        sizes = ", ".join(sorted(seen, key=int))
        hint = (" Строка без длины — `{\"S\"}`, с длиной — `{\"S\", длина, 0 или 1}`." if picked == "PatternType.S" else "")
        _say(out, 2, True, path,
             f"в блоке {picked} позиций: {count}, а корпус видел блоки из {sizes} "
             "(буква входит в число позиций): такую форму платформа не читает («Ошибка формата потока»)." + hint)
        return
    node_type = schema.MAP[picked]
    for at, allowed in (table["values"].get(picked) or {}).items():
        at = int(at)
        slot = node_type.fields.get(at)
        key = slot.name if slot is not None else f"u{at}"
        if key not in doc:
            continue
        text = _text_of(doc[key])
        if text is not None and text not in allowed:
            _say(out, 2, True, path + (key,),
                 f"{key} = {doc[key]!r}, а корпус видел в этой позиции блока {picked} только {', '.join(sorted(allowed))}: "
                 "другое значение платформа не читала")


_PICTURE_SHAPES = []


def picture_shapes():
    """Таблица форм записи блока картинки по корпусу (`picture_shapes.json`, считается по корпусу) — один раз на процесс."""
    if not _PICTURE_SHAPES:
        _PICTURE_SHAPES.append(json.loads((DATA_DIR / "picture_shapes.json").read_text(encoding="utf-8")))
    return _PICTURE_SHAPES[0]


_KIND_LETTER = ((bool, "b"), (int, "i"), (str, "s"), (dict, "d"), (list, "l"))


def _shape_of_picture(block):
    letters = []
    for name, value in block.items():
        letters.append(f"{name}:" + next((letter for kind, letter in _KIND_LETTER if isinstance(value, kind)), "?"))
    return ",".join(letters)


def _check_picture_shapes(value, path, out):
    """Форма записи блока картинки — уровень 2, ОТКАЗ. Блок (`mark`, `source`, `ref` и позиции за ними) короткий и жёсткий: число позиций и вид каждой при данной метке и
    источнике обязаны быть виденными корпусом. Блок, переделанный из картинки «из файла» в ссылку правкой JSON, оставлял лишние позиции (десять вместо девяти) —
    загрузка проходила, а форма не открывалась: «Ошибка формата потока». Ходит по ЗНАЧЕНИЮ, как проверка GUID."""
    if isinstance(value, dict):
        if isinstance(value.get("mark"), int) and isinstance(value.get("source"), int) and isinstance(value.get("ref"), dict) \
                and not isinstance(value["mark"], bool) and not isinstance(value["source"], bool):
            seen = picture_shapes()["shapes"].get(f"{value['mark']}|{value['source']}")
            shape = _shape_of_picture(value)
            if seen is None:
                _say(out, 2, True, path, f"блок картинки с меткой {value['mark']} и источником {value['source']}: такого сочетания корпус не видел; платформа "
                     "такую запись не читала («Ошибка формата потока»)")
            elif shape not in seen:
                _say(out, 2, True, path, f"блок картинки (метка {value['mark']}, источник {value['source']}) записан позициями {shape} ({len(value)}), а корпус видел "
                     + "; ".join(f"{known} ({len(known.split(','))})" for known in sorted(seen, key=lambda k: -seen[k]))
                     + ": другую запись платформа не читает («Ошибка формата потока»). Блок картинки платформы по метке 4 — девять позиций, строка "
                     "`{4,1,{код},\"\",-1,-1,1,0,\"\"}`; собирайте его операцией редактора, а не правкой JSON")
        for key, item in value.items():
            _check_picture_shapes(item, path + (key,), out)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _check_picture_shapes(item, path + (i,), out)


_DEC_PLACES = []


def dec_places():
    """Адреса, где корпус держит дробное число и ни разу строку (`dec_places.json`, считается по корпусу): путь по именам ключей, индексы списков — `[]`."""
    if not _DEC_PLACES:
        _DEC_PLACES.append(frozenset(json.loads((DATA_DIR / "dec_places.json").read_text(encoding="utf-8"))["decimal_places"]))
    return _DEC_PLACES[0]


def _check_dec_places(value, path, out, key=()):
    """Дробное число в кавычках — уровень 2, ОТКАЗ. Дробное уровня 0 (`Dec`, маска `1e2`, ширина `93.75`) в JSON пишется без кавычек; строка с тем же текстом ложится в файл
    в кавычках, и форма не открывается («Ошибка формата потока») — загрузка проходит. Место, где корпус видел только дробные числа и ни разу строку, строки не принимает.
    Ходит по значению, адрес — имена ключей без индексов."""
    if isinstance(value, dict):
        if set(value) <= {"guid", "base64", "num", "layout"}:
            return
        for name, item in value.items():
            _check_dec_places(item, path + (name,), out, key + (str(name),))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _check_dec_places(item, path + (i,), out, key + ("[]",))
    elif isinstance(value, str) and not isinstance(value, Dec) and NUM_RE.fullmatch(value) and any(c in value for c in ".eE") \
            and "/".join(key) in dec_places():
        _say(out, 2, True, path, f"дробное число {value!r} записано строкой (в кавычках): в этом месте корпус видел только дробные числа без кавычек, а строку — ни разу; в файл она ляжет "
             "в кавычках, и платформа форму не откроет («Ошибка формата потока»). JSON писали не `json0.dumps`? Читать надо `json0.loads` (parse_float=Dec), писать — `json0.dumps`")


FONT_RECORDS = ("Font.v0", "Font.v1", "Font.v2", "Font.v3")


def _check_font(doc, path, out):
    """Версия записи шрифта и масштаб ходят ПАРОЙ — уровень 2: у записей версии 7 позиция масштаба есть, у записей версии 6 её нет. Длина записи
    считается по набору ключей, версия говорит о ней независимо. Правило одно на ВСЕ четыре вида записи, включая абсолютный (масштаб у него стоит
    числом, позиция 18).

    Отказ, а не предупреждение: платформа такой файл не пишет, а проверка обратным разбором байт в байт его ПРОЙДЁТ — он сверяет нашу запись с нашим чтением. Версию, которой
    формы не показали, правило не проверяется."""
    version, has_scale = doc.get("version"), "scale" in doc
    if version == 7 and not has_scale:
        _say(out, 2, True, path, "у записи шрифта версии 7 нет поля scale, а масштаб стоит "
                                 "последней позицией у всех таких записей")
    if version == 6 and has_scale:
        _say(out, 2, True, path, "у записи шрифта версии 6 поля scale не бывает: позиции для "
                                 "масштаба в ней нет вовсе, и лишнее поле уехало бы в файл лишним "
                                 "числом")


def _check_commandbar(doc, path, out, carrier=None):
    """Кнопка без записи действия и запись без кнопки — предупреждение уровня 2. `carrier` — имя элемента, в котором блок лежит (командной панели
    или кнопки-меню): блок действий имени не несёт.

    Множества GUID кнопок и записей у командной панели совпадают: подсказка, пояснение, картинка и сочетание клавиш кнопки лежат в записи действия
    и находятся только по GUID. Предупреждение, а не отказ: форму, которую платформа написала сама, отказ запретил бы собрать обратно.

    **Повтор GUID кнопки правилом не становится:** он есть в исправных формах платформы."""
    act_key, sets_key, btn_key, id_key, action_id = COMMANDBAR_NAMES
    actions, buttons = {}, {}
    for i, item in enumerate(doc.get(act_key) or ()):
        if isinstance(item, dict) and isinstance(item.get(action_id), dict):
            actions.setdefault(item[action_id].get("guid"), i)
    for s, item in enumerate(doc.get(sets_key) or ()):
        if not isinstance(item, dict):
            continue
        for i, button in enumerate(item.get(btn_key) or ()):
            if isinstance(button, dict) and isinstance(button.get(id_key), dict):
                buttons.setdefault(button[id_key].get("guid"), (s, i))
    for guid, (s, i) in sorted(buttons.items(), key=lambda kv: kv[1]):
        if guid not in actions:
            _say(out, 2, False, path + (sets_key, s, btn_key, i),
                 f"у кнопки с id {guid} нет записи действия: подсказка, пояснение, картинка и "
                 "сочетание клавиш кнопки лежат именно там, и взять их больше неоткуда")
    for guid, i in sorted(actions.items(), key=lambda kv: kv[1]):
        if guid not in buttons:
            _say(out, 2, False, path + (act_key, i),
                 f"запись действия с id {guid} ничьей кнопкой не названа")
    _check_numbering(doc, path, out)
    _check_refs(doc, path, out)
    _check_owners(doc, path, out, carrier)
    _check_set_pairs(doc, path, out, carrier)
    if path and path[-1] == MENU_GATE.name:
        _check_menu_set_count(doc, path, out, carrier)
    else:
        _check_panel_sets(doc, path, out, carrier)


def _check_set_pairs(doc, path, out, carrier=None):
    """Два набора ОДНОГО блока с одной парой «GUID + код» — предупреждение уровня 2. Набор адресуется парой (ею его называют ссылки описаний), и у
    двух наборов с одной парой ссылки неразличимы; код может повторяться, различает пара. Сюда приводит рука либо починка меню с двумя наборами
    одного кода (`set_menu_mode` ставит постоянный GUID обоим; отчёт операции говорит об этом). Что платформа делает с такими наборами, не проверялось."""
    _act_key, sets_key, _btn_key, _id_key, _action_id = COMMANDBAR_NAMES
    set_ref, set_code = NUMBERING_NAMES[2], NUMBERING_NAMES[3]
    seen = {}
    kind = "меню кнопки" if path and path[-1] == MENU_GATE.name else "командной панели"
    where = f"{kind} {carrier!r}" if carrier else kind
    for i, item in enumerate(doc.get(sets_key) or ()):
        ref = item.get(set_ref) if isinstance(item, dict) else None
        guid = ref.get("guid") if isinstance(ref, dict) else None
        if not isinstance(guid, str):
            continue
        pair = (guid, item.get(set_code))
        if pair in seen:
            _say(out, 2, False, path + (sets_key, i, set_ref),
                 f"у {where} наборы кнопок {seen[pair]} и {i} с одной парой «GUID + код» "
                 f"({guid}, {pair[1]}): набор адресуется парой, и ссылки на них неразличимы. Что "
                 "платформа делает с такими наборами, не проверялось")
        else:
            seen[pair] = i


# Описание действия у записи и его метка у ссылки вида 1 («кнопки-подменю», `ActionSpec.v1`): по ней набор панели узнаётся как подменю.
# Спрошены у карты по позициям (`edit.ACT_SPEC`, `edit.SPEC_MARK`).
ACTION_SPEC = schema.MAP["CommandBarAction"].fields[4].name
SUBMENU_MARK = schema.MAP["ActionSpec.v1"].fields[0]


def _submenu_pairs(doc):
    """Пары «GUID + код», которые называют описания ВИДА 1 блока, — наборы-подменю. Только вид 1 и только описание самой записи: ссылки вида 4 и
    источник внутри стандартного действия называют постоянные наборы (`ActionSpec.v4`)."""
    act_key = COMMANDBAR_NAMES[0]
    ref_id, ref_code = NUMBERING_NAMES[4:]
    pairs = set()
    for item in doc.get(act_key) or ():
        spec = item.get(ACTION_SPEC) if isinstance(item, dict) else None
        if isinstance(spec, dict) and spec.get(SUBMENU_MARK.name) == SUBMENU_MARK.const \
                and isinstance(spec.get(ref_id), dict):
            pairs.add((spec[ref_id].get("guid"), spec.get(ref_code)))
    return pairs


def _check_panel_sets(doc, path, out, carrier=None):
    """GUID набора КОМАНДНОЙ ПАНЕЛИ — из словаря; иначе предупреждение уровня 2. У меню набор со случайным GUID платформа открывает, а меню не
    выпадает; у панели то же место (`ButtonSet.ref_id`) держит словарь: все наборы, которых не называет кнопка-подменю своего блока, несут один из четырёх
    постоянных (`schema.PANEL_BUTTON_SETS`) или GUID головы своего блока. Набор, названный подменю, из правила вынут: у него свой GUID.

    Предупреждение, а не отказ: что платформа сделает с панелью, чей набор вне словаря, не проверялось. Редактор наборов панели не заводит — сюда
    приводит только рука."""
    _act_key, sets_key, _btn_key, _id_key, _action_id = COMMANDBAR_NAMES
    head_key, set_ref, set_code = OWNER_NAMES[1], NUMBERING_NAMES[2], NUMBERING_NAMES[3]
    head = doc.get(head_key)
    head = head.get("guid") if isinstance(head, dict) else None
    submenus = _submenu_pairs(doc)
    where = f"командной панели {carrier!r}" if carrier else "командной панели"
    for i, item in enumerate(doc.get(sets_key) or ()):
        ref = item.get(set_ref) if isinstance(item, dict) else None
        guid = ref.get("guid") if isinstance(ref, dict) else None
        if not isinstance(guid, str) or guid in schema.PANEL_BUTTON_SETS or guid == head \
                or (guid, item.get(set_code)) in submenus:
            continue
        menu = (" (это GUID набора МЕНЮ кнопки формы — у панели его не бывает)"
                if guid == schema.MENU_BUTTON_SET else "")
        _say(out, 2, False, path + (sets_key, i, set_ref),
             f"у {where} GUID набора кнопок {guid}{menu} — вне словаря: это не один из четырёх "
             f"постоянных панели ({', '.join(schema.PANEL_BUTTON_SETS)}), не голова своего "
             f"блока ({head}) и не подменю, которое называла бы кнопка этого блока. Что "
             "платформа делает с таким набором панели, не проверялось (у меню кнопки форма "
             "открывается и сохраняется, а меню не выпадает)")


def _check_menu_set_count(doc, path, out, carrier=None):
    """Набор у меню кнопки ровно ОДИН; иначе предупреждение уровня 2. Меню без набора или с двумя редактор не собирает — приводит только рука.
    Какое меню платформа покажет при нуле или двух наборах, не проверялось."""
    _act_key, sets_key, _btn_key, _id_key, _action_id = COMMANDBAR_NAMES
    sets = doc.get(sets_key)
    count = len(sets) if isinstance(sets, list) else 0
    if count == 1:
        return
    where = f"у меню кнопки {carrier!r}" if carrier else "у меню кнопки"
    _say(out, 2, False, path + (sets_key,),
         f"{where} наборов кнопок {count}, а у меню набор ровно один. Что платформа "
         "покажет у такого меню, не проверялось")


def _check_owners(doc, path, out, carrier=None):
    """Владелец кнопки — голова СВОЕГО блока; иначе предупреждение уровня 2. Правило одно у панели и у меню.

    Предупреждение, а не отказ: на выпадение меню владелец не влияет (форму с владельцем чужой панели платформа открывает и пересохраняет), а что
    ломает чужой владелец, не проверялось. Нарушить правило может только рука — шаблон или копия кнопки из чужой панели."""
    _act_key, sets_key, btn_key, _id_key, _action_id = COMMANDBAR_NAMES
    owner_key, head_key, name_key = OWNER_NAMES
    head = doc.get(head_key)
    head = head.get("guid") if isinstance(head, dict) else None
    if not isinstance(head, str):
        return
    kind = "меню кнопки" if path and path[-1] == MENU_GATE.name else "командной панели"
    where = f"{kind} {carrier!r}" if carrier else kind
    for s, item in enumerate(doc.get(sets_key) or ()):
        for i, button in enumerate((item.get(btn_key) or ()) if isinstance(item, dict) else ()):
            owner = button.get(owner_key) if isinstance(button, dict) else None
            owner = owner.get("guid") if isinstance(owner, dict) else None
            if not isinstance(owner, str) or owner == head:
                continue
            _say(out, 2, False, path + (sets_key, s, btn_key, i, owner_key),
                 f"у кнопки {button.get(name_key)!r} {where} владелец {owner}, а голова её блока "
                 f"— {head}. Владелец кнопки — ссылка на голову блока-родителя. "
                 "Предупреждение, а не отказ: платформа такую форму открывает и пересохраняет, "
                 "не исправляя, и на выпадение меню владелец не влияет, а что он ломает — не "
                 "проверялось. `add_button` ставит его сам")


def _check_numbering(doc, path, out):
    """Номера кнопок в панели не повторяются, а голова блока не меньше наибольшего из них.

    Нужна потому, что **номера выдаёт не кодек**: скопированная целиком запись кнопки даёт второй экземпляр номера; в файле это молчит, а платформа
    адресует кнопку именно им (хвост набора перечисляет подменю номерами). Предупреждение, а не отказ: форму платформы отказ запретил бы собрать обратно."""
    _act_key, sets_key, btn_key, _id_key, _action_id = COMMANDBAR_NAMES
    number_key, last_key, _set_ref, _set_code, _ref_id, _ref_code = NUMBERING_NAMES
    seen = {}
    for s, item in enumerate(doc.get(sets_key) or ()):
        if not isinstance(item, dict):
            continue
        for i, button in enumerate(item.get(btn_key) or ()):
            number = button.get(number_key) if isinstance(button, dict) else None
            if not isinstance(number, int) or isinstance(number, bool):
                continue
            if number in seen:
                where = seen[number]
                _say(out, 2, False, path + (sets_key, s, btn_key, i),
                     f"номер кнопки {number} уже стоит у кнопки {where[0]}/{where[1]}: номера "
                     "в панели сквозные и не повторяются, а хвост набора адресует подменю именно ими")
            else:
                seen[number] = (s, i)
    last = doc.get(last_key)
    if seen and isinstance(last, int) and not isinstance(last, bool) and last < max(seen):
        _say(out, 2, False, path + (last_key,),
             f"{last_key} = {last}, а наибольший номер кнопки {max(seen)}: это счётчик "
             "последнего выданного номера, и меньше выданного он не бывает")


def _check_refs(doc, path, out):
    """Ссылка действия называет набор кнопок ЭТОЙ панели — либо служебную пару.

    Ссылка — пара «GUID владельца + код» (`ref_id`, `ref_code`), адресует набор, называющий себя той же парой. Мест у неё в записи ТРИ, ищутся обходом:
    описание вида 1 (кнопка-подменю), описание вида 4 и ссылка на источник ВНУТРИ описания стандартного действия (`ActionRef`).

    Подменю, потерявшее набор, — кнопка остаётся, а меню под ней не откроется. Отказом не делается: такие записи написала сама платформа.
    Записи обработчиков событий сюда не попадают: они лежат у элемента, а не в панели."""
    act_key, sets_key, _btn_key, _id_key, _action_id = COMMANDBAR_NAMES
    _number, _last, set_ref, set_code, ref_id, ref_code = NUMBERING_NAMES
    pairs = set()
    for item in doc.get(sets_key) or ():
        if isinstance(item, dict) and isinstance(item.get(set_ref), dict):
            pairs.add((item[set_ref].get("guid"), item.get(set_code)))
    known = ", ".join(f"{guid} / {code}" for guid, code in sorted(pairs, key=str)) or "—"
    for i, item in enumerate(doc.get(act_key) or ()):
        spec = item.get("action") if isinstance(item, dict) else None
        for pair in _refs_in(spec, ref_id, ref_code):
            if pair in SERVICE_REFS or pair in pairs:
                continue
            _say(out, 2, False, path + (act_key, i),
                 f"ссылка {pair[0]} / {pair[1]} не называет ни одного набора кнопок этой панели "
                 f"(есть {known}) и не является служебной парой «никуда» или «разделитель»")


def _refs_in(value, ref_id, ref_code):
    """Пары «GUID + код» внутри описания действия, на любой глубине: у трёх видов описания ссылка лежит на разных этажах, перечень адресов разошёлся
    бы с картой."""
    if isinstance(value, dict):
        if isinstance(value.get(ref_id), dict):
            yield (value[ref_id].get("guid"), value.get(ref_code))
        for item in value.values():
            yield from _refs_in(item, ref_id, ref_code)
    elif isinstance(value, list):
        for item in value:
            yield from _refs_in(item, ref_id, ref_code)


def _check_seen(slot, value, path, out):
    """Значение, которого корпус на этом месте не видел, — предупреждение с перечнем виденного."""
    if slot.kind == schema.ENUM:
        enum = schema.ENUMS.get(slot.enum)
        if enum is None or not isinstance(value, int) or isinstance(value, bool):
            return
        if value in enum.codes.values():
            return
        seen = [pair[0] for pair in enum.seen]
        if value in seen:
            return
        known = ", ".join(f"{name} = {code}" for name, code in sorted(enum.codes.items()))
        corpus = ("; в корпусе встречались и " + ", ".join(str(v) for v in seen)) if seen else ""
        _say(out, 2, False, path, f"{slot.name} = {value}: имени у этого кода нет, "
                                  f"карта знает {known}{corpus}")
        return
    if slot.seen and value not in slot.seen:
        _say(out, 2, False, path, f"{slot.name} = {value!r}, а в корпусе встречалось "
                                  + ", ".join(repr(v) for v in slot.seen))


def _check_links(doc, type_name, path, out, owner=None, carrier=None):
    """`owner` — тип узла, ИЗ КОТОРОГО пришли; нужен одному правилу. Список элементов (`Elements`) стоит у контейнера формы (верхний уровень) и у
    записи элемента (вложенные); повтор имени там и там проверяется по-разному (`_check_elements`), и различить их можно только по тому, кто позвал.

    `carrier` — имя БЛИЖАЙШЕГО элемента сверху: предупреждение о владельце кнопки называет командную панель или кнопку-меню, у блока действий своего
    имени нет. Заменяется на каждом элементе."""
    if not isinstance(doc, dict) or set(doc) == {typed.RAW}:
        return
    try:
        picked = schema.pick_doc(type_name, doc) or type_name
    except schema.SchemaError:
        return                       # об этом уже сказал уровень 1, и сказал точнее
    node_type = schema.MAP.get(picked)
    if node_type is None:
        return
    carrier = _carrier_of(doc, picked, carrier)
    # Родитель — тот, у кого В ОДНОМ блоке лежат и страницы, и список элементов: контейнер формы и всякий элемент со вложенными. Ниже числа страниц нет, выше неясно, чей список.
    if picked == "Container" or picked in ELEMENT_TYPES:
        _elements_name, _items = PLACEMENT_NAMES[3], PLACEMENT_NAMES[4]
        holder = doc.get(_elements_name)
        items = holder.get(_items) if isinstance(holder, dict) else None
        if isinstance(items, list) and items:
            where = doc.get("content") if picked in ELEMENT_TYPES else doc
            _check_placement(items, _pages_of(where, PLACEMENT_NAMES[5]),
                             path + (_elements_name, _items), out)
    if picked == "Coords":
        _check_coords(doc, path, out)
    if picked in COLUMN_HEADS:
        _check_column_control(doc, path, out)
    if picked == "Element.TableBox":
        _check_value_list_source(doc, path, out)
    if picked in PATTERN_TYPES:
        _check_pattern(doc, path, out)
    if picked in pattern_shapes()["shapes"]:
        _check_shape_seen(doc, picked, path, out)
    if picked in FONT_RECORDS:
        _check_font(doc, path, out)
    # Корень — единственное место, где рядом лежат и элементы, и то, что на них ссылается:
    # заголовок формы и таблица привязок данных.
    if picked == "Form":
        _check_references(doc, path, out)
        _check_design(doc, path, out)
        _check_shortcut_repeats(doc, path, out)
    if node_type.runs is not None:
        _links_in_runs(doc, node_type, path, out, picked, carrier)
        return
    by_name = {slot.name: slot for slot in node_type.fields.values()}
    repeat = node_type.repeat
    items = doc.get(repeat.name) if repeat is not None else None
    if isinstance(items, list):
        count = doc.get("count")
        if isinstance(by_name.get("count"), schema.F) and isinstance(count, int) \
                and not isinstance(count, bool) and count != len(items):
            _say(out, 2, True, path, f"счётчик {count} против {len(items)} узлов в списке "
                                     f"{repeat.name}; по нему платформа и читает список")
        if picked == "Elements":
            _check_elements(items, path + (repeat.name,), out, nested=owner in ELEMENT_TYPES)
        if picked in PAGE_HOLDERS:
            _check_pages(items, path + (repeat.name,), out)
    for name, value in doc.items():
        slot = by_name.get(name)
        if repeat is not None and name == repeat.name and isinstance(value, list):
            for i, item in enumerate(value):
                _check_links(item, repeat.type, path + (name, i), out, picked, carrier)
            continue
        if isinstance(slot, schema.N):
            _check_links(value, slot.type, path + (name,), out, picked, carrier)
        elif isinstance(slot, schema.F):
            _check_seen(slot, value, path + (name,), out)


def _check_design(doc, path, out):
    """Один дизайн формы — три предупреждения уровня 2:

    * **Смесь версий общего блока у элементов.** Версия общего блока — свойство ФОРМЫ: у каждого элемента она та же, что у контейнера
      (`design.CORPUS_MIXED_FORMS`), а платформа при пересохранении поднимает смешанную форму до своей версии целиком. Смесь платформа открывает и
      рисует — предупреждение, а не отказ.
    * **Смесь у вложенных элементов колонок — вне трёх пар, которые пишет платформа:** 15 → 16, 16 → 15, 16 → 10 (`design.CORPUS_NESTED_ALIEN`).
      О прочих (например 10 → 16, собранной `set_column_control` по `unverified`) проверка говорит.
    * **Пара (позиция 16, спутник) у поля ввода и поля выбора, которой платформа не пишет** (`design.SEEN_PAIRS`; своих и вложенных). Спутник ходит с
      позицией 16 жёстко, и пару вроде (1, 2) даёт правка одной из двух. У поля ввода позиция 16 — его вид (`view`: 1 — 8.2, 0 и 2 — 8.3), а спутник
      `u43` платформа досчитывает при сохранении (`design.u43_rule`): вид такая пара не портит, но это не та запись, что пишет платформа; у поля выбора
      влияние не проверялось. Критерий — пары, которые платформа ПИСАЛА, а не правило досчёта: у отдельных полей `u43` против правила, и проверка
      краснела бы на формах платформы.
"""
    version, alien = design.mixed(doc)
    if alien:
        _say(out, 2, False, path, design.mix_words(version, alien))
    nested = design.nested_mix(doc)
    if nested:
        _say(out, 2, False, path, design.nested_mix_words(version, nested))
    for who, kind, block_version, pair in design.hidden_pairs(doc):
        if pair not in design.SEEN_PAIRS.get((kind, block_version), {pair}):
            _say(out, 2, False, path, design.pair_words(who, kind, block_version, pair))


def _check_shortcut_repeats(doc, path, out):
    """Одно сочетание у двух кнопок формы — предупреждение уровня 2. Три класса пар:

    * **форма ↔ панель**: срабатывает кнопка, чей элемент стоит в списке элементов РАНЬШЕ (`edit.buttons.REPEAT_FORM_PANEL`, `_form_panel_here`); у
      панели таблицы победителя называет фокус;
    * **форма ↔ форма** и **панель ↔ панель в ОДНОЙ панели с разными обработчиками**: срабатывает одна из них, правило не установлено
      (`REPEAT_SAME_CLASS`);
    * **повтор в РАЗНЫХ панелях** — побеждает стоящая раньше, панель таблицы — при фокусе в ней (`REPEAT_OTHER_PANELS`); **один обработчик** у всех
      записей пары (кнопка в двух наборах) — молчание.

    Предупреждение третьего класса срабатывает и на формах платформы. Предупреждение, а не отказ: форму платформа открывает и рисует, человек мог
    хотеть именно этого. Поиск пар — `edit.buttons.form_panel_repeats` и `same_class_repeats`, тот же, что говорит о повторе в отчёте операций (модуль
    берётся внутри функции: `edit.buttons` сам читает `validate` при импорте)."""
    from .edit import buttons as ed_buttons
    for pair, forms, panel in ed_buttons.form_panel_repeats(doc):
        _say(out, 2, False, path,
             f"сочетание {ed_buttons._shortcut_words(*pair)} стоит и у кнопки формы "
             f"{', '.join(forms)}, и у кнопки панели {', '.join(panel)}: по сочетанию сработает "
             f"одна из двух кнопок, не обязательно кнопка формы; "
             + ed_buttons._form_panel_here(doc, pair, forms, panel) + "; "
             + ed_buttons.REPEAT_FORM_PANEL)
    for pair, side, places, verdict in ed_buttons.same_class_repeats(doc):
        what = "кнопок панели" if side == "панель" else "кнопок формы"
        words = ed_buttons.REPEAT_OTHER_PANELS if verdict == "panels" \
            else ed_buttons.REPEAT_SAME_CLASS
        _say(out, 2, False, path,
             f"сочетание {ed_buttons._shortcut_words(*pair)} стоит у {len(places)} {what}: "
             f"{', '.join(places)}; " + words)


def _check_column_control(doc, path, out):
    """Вид вложенного элемента колонки назван ДВАЖДЫ, и два места обязаны сходиться: GUID типа у колонки (`control_type`) и первое число тела в самом
    элементе (`content_kind`: 9 поле ввода, 1 флажок, 2 поле выбора; `schema.FORKS["ColumnControl"]`). Разошедшиеся — ОТКАЗ: тело одного вида под GUID
    другого платформа прочтёт чужими правилами, а проверка обратным разбором байт в байт такое пропустит. Пустой GUID ходит БЕЗ блока, непустой — с блоком. Непустой без блока —
    предупреждение: что сделает платформа, не проверялось. Пустой с блоком — отказ уровня 1 (`_say_bare_head`)."""
    _head, type_key, control_key, element_key, content_key, kind_key = COLUMN_CONTROL_NAMES
    guid = (doc.get(type_key) or {}).get("guid") if isinstance(doc.get(type_key), dict) else None
    if guid is None:
        return
    control = doc.get(control_key)
    if guid == ZERO_GUID:
        # Пустой тип при блоке элемента — отказ уровня 1 (`_say_bare_head`); до этого уровня такой документ не доходит.
        return
    if not isinstance(control, dict):
        _say(out, 2, False, path + (type_key,),
             f"тип вложенного элемента {guid} назван, а самого элемента нет")
        return
    element = control.get(element_key)
    content = element.get(content_key) if isinstance(element, dict) else None
    if not isinstance(content, dict) or typed.RAW in content:
        return                       # сырое тело — сверять не с чем; о нём сказал уровень 1
    body = schema.FORKS["ColumnControl"].names.get(content.get(kind_key))
    named = schema.element_type_name(guid)
    if body is None or body[len("Content."):] != named:
        _say(out, 2, True, path + (type_key,),
             f"тип вложенного элемента колонки — {named or guid}, а тело у него "
             f"{body or 'неизвестного вида'} ({kind_key} = {content.get(kind_key)!r}); два места "
             "обязаны называть один вид, и тело "
             "под чужим GUID платформа прочтёт чужими правилами. Сменить вид целиком — "
             "`set_column_control`")


def _check_value_list_source(doc, path, out):
    """Колонки табличного поля — колонки списка значений (`fbacf851-…`), а источник данных поля (`2/3`) не «список значений». Так собранное
    поле платформа при записи лишает ВСЕХ колонок: они не соответствуют источнику. У всех полей конфигураций с такими колонками источник один
    (`schema.VALUE_LIST_SOURCE`, вид 2). Предупреждение, а не отказ: форма читается и собирается, но платформа её колонок не оставит."""
    from .edit import columns
    why = columns.value_list_source_problem(doc)
    if why is not None:
        _say(out, 2, False, path + ("content",),
             f"колонки поля — колонки списка значений, а {why}; платформа при записи формы снимает все такие колонки. "
             "Источник данных такого поля — блок `2/3` со списком значений (`edit.columns.value_list_source_block`)")


def _check_table_types(doc, out, config=None):
    """Тип значения табличных полей формы против данных их привязки (`tabletype.findings`): предупреждения уровня 2 с адресом «поле/content/u1»."""
    from . import tabletype
    for found in tabletype.findings(doc, config):
        _say(out, 2, False, (found.element, "content", "u1"), found.text)


def _links_in_runs(doc, node_type, path, out, owner=None, carrier=None):
    """Связи внутри узла со счётными списками. Счётчик здесь не сверяется: в JSON его нет, он равен длине массива. «Счётчик против длины» — у
    списков с `count` (`Elements`, `PanelPages.v1`)."""
    try:
        spots, lists = schema.doc_runs(node_type, doc)
    except schema.SchemaError:
        return                       # об этом уже сказал уровень 1, и сказал точнее
    if node_type.name == "CommandBarActions":
        _check_commandbar(doc, path, out, carrier)
    for segment, _start, _members in lists:
        if isinstance(segment, schema.Flagged):
            picked = doc.get(segment.name)
            for name, value in (picked or {}).items():
                if name in segment.bits:
                    _check_links(value, segment.bits[name][1],
                                 path + (segment.name, name), out, owner, carrier)
            continue
        if isinstance(segment, schema.Masked):
            # Спускаться некуда: за битом скаляр. Спросить можно то же, что у поля головы, — видело ли такое значение.
            picked = doc.get(segment.name)
            for name, value in (picked or {}).items():
                if name in segment.bits:
                    _check_seen(schema.masked_slot(segment, name), value,
                                path + (segment.name, name), out)
            continue
        if isinstance(segment, schema.Gated):
            # Блок либо есть, либо нет: связи спрашиваются у него самого, согласие с флагом головы проверила `doc_runs`.
            block = doc.get(segment.name)
            if isinstance(block, dict):
                _check_links(block, segment.type, path + (segment.name,), out, owner, carrier)
            continue
        if not isinstance(segment, (schema.Counted, schema.CountedPairs)):
            continue
        items = doc.get(segment.name) or ()
        # Предельное число записей объявлено у счётного списка и только у него; `getattr` принял бы опечатку в имени поля за «предела нет».
        cap = segment.at_most if isinstance(segment, schema.Counted) else None
        if cap is not None and len(items) > cap:
            # Предельное число записей объявлено КАРТОЙ; здесь только сверка. Отказ, а не предупреждение: платформа такой файл не пишет, а проверка обратным разбором байт в байт его пройдёт.
            _say(out, 2, True, path + (segment.name,),
                 f"членов {len(items)}, а в файле их бывает не больше {cap}: счётчик у списка "
                 f"{segment.name} один, и платформа читает по нему")
        for i, item in enumerate(items):
            _check_links(item, segment.type, path + (segment.name, i), out, owner, carrier)
    for _index, (_fallback, slot) in sorted(spots.items()):
        if slot is None or slot.name not in doc:
            continue
        if isinstance(slot, schema.N):
            _check_links(doc[slot.name], slot.type, path + (slot.name,), out, owner, carrier)
        elif isinstance(slot, schema.F):
            _check_seen(slot, doc[slot.name], path + (slot.name,), out)


_CORPUS = []


def corpus_summary():
    """Сводка корпуса — один раз на процесс: `validate` зовут в цикле, а файл за прогон не меняется. Имя публичное, чтобы тест мог подставить
    свою сводку."""
    if not _CORPUS:
        _CORPUS.append(stat.load_summary())
    return _CORPUS[0]


def _lens_list(lens, limit=10):
    order = sorted(lens, key=int)
    shown = ", ".join(k for k in order[:limit])
    return shown + (f" и ещё длин {len(order) - limit}" if len(order) > limit else "")


def _is_anchor(type_name):
    """Узел, от которого считаются адреса журнала и зеркал: форма, элемент, подэлемент. Правило то же, что у `propose.anchor_of`: `Form` или
    `Element.<Тип>` ровно с одной точкой. Безымянный блок внутри элемента якорем не становится."""
    return type_name == stat.KIND_FORM or (type_name.startswith("Element.")
                                           and type_name.count(".") == 1)


def _mirror_problem(slot, item, anchor_node, anchor_type, path, out):
    """Зеркало против первичного адреса. Предупреждение, а не отказ: расхождение бывает законным (какая из позиций ведущая, известно у одного типа,
    у формы другого строения на втором адресе может лежать своё), а файл уже такой, и отказ запретил бы собрать обратно написанное платформой.

    Текст говорит про правку РУКАМИ: у части зеркал платформа пишет оба адреса вместе, у других (`multi_line_mirror` и соседи у поля ввода) — только
    первичный. Общее одно: в файле два адреса, и правка по одному уезжает в базу наполовину."""
    address = tuple(int(part) for part in slot.mirror_of.split("/"))
    primary_slot = schema.resolve_any(anchor_type, address)
    if not isinstance(primary_slot, schema.F):
        return
    node = anchor_node
    for index in address:
        if not isinstance(node, Node) or index >= len(node.children):
            return                   # блок короче — первичного адреса в этом файле нет вовсе
        node = node.children[index]
    if isinstance(node, Node) or not typed.fits_scalar(primary_slot, node) \
            or not typed.fits_scalar(slot, item):
        return                       # одно из двух имён снято демоцией — сверять нечего
    if node.text == item.text:
        return
    _say(out, 2, False, path, f"{slot.name} = {item.text}, а первичное поле "
                              f"{primary_slot.name} ({slot.mirror_of} от {anchor_type}) = "
                              f"{node.text}; одно свойство палитры лежит в файле по обоим "
                              "адресам, и правка по одному из двух уезжает в базу наполовину")


def _mirror_block_problem(slot, child, anchor_node, anchor_type, path, out):
    """Зеркало целым БЛОКОМ: ЦветФона контейнера формы и панели лежит по двум адресам. Сверяется поддерево целиком (у цвета вид и значение живут
    врозь). Предупреждение, а не отказ — по причине скалярного зеркала."""
    address = tuple(int(part) for part in slot.mirror_of.split("/"))
    primary_slot = schema.resolve_any(anchor_type, address)
    if not isinstance(primary_slot, schema.N):
        return
    node = anchor_node
    for index in address:
        if not isinstance(node, Node) or index >= len(node.children):
            return                   # блок короче — первичного адреса в этом файле нет вовсе
        node = node.children[index]
    if not isinstance(node, Node) or render(node) == render(child):
        return
    _say(out, 2, False, path, f"{slot.name} разошёлся с первичным блоком {primary_slot.name} "
                              f"({slot.mirror_of} от {anchor_type}); одно свойство палитры лежит "
                              "в файле по обоим адресам, и правка по одному из двух уезжает в "
                              "базу наполовину")


def _walk_mirrors(node, type_name, anchor_node, anchor_type, out, path):
    picked = schema.pick(type_name, node) if node.children else \
        (None if type_name in schema.ABSTRACT else type_name)
    if picked is None or picked not in schema.MAP:
        return
    if _is_anchor(picked):
        anchor_node, anchor_type = node, picked
    elif picked in schema.COLUMN_ANCHOR:
        anchor_type, anchor_node = _column_anchor(picked, node)
    node_type = schema.MAP[picked]
    if node_type.packed is not None:
        _mirrors_in_packed(node, node_type, out, path)
        return
    if node_type.runs is not None:
        _mirrors_in_runs(node, node_type, anchor_node, anchor_type, out, path)
        return
    for i, child in enumerate(node.children):
        slot = schema.slot_at(node_type, i)
        _mirror_at(slot, child, anchor_node, anchor_type, out, path, i)


def _column_anchor(type_name, node):
    """`(тип якоря, узел якоря)` для колонки без обёртки (`schema.COLUMN_ANCHOR`). Колонка списка значений кладёт базу `{8, голова, …}` на
    позицию 1, колонка с обёрткой — на `1/1`, адреса журнала и зеркал считаются от второй. Якорь строится на месте как у упакованного элемента
    (`_mirrors_in_packed`): база встаёт туда, где у якоря она лежит, обёртка вокруг — пустая; иначе зеркало ширины искало бы первичное поле на уровень глубже."""
    anchor_type, own, at = schema.COLUMN_ANCHOR[type_name]
    inner = node.children[own]
    for index in reversed(at[1:]):
        inner = Node([Scalar("INT", "0")] * index + [inner])
    children = list(node.children)
    children[at[0]] = inner
    return anchor_type, Node(children)


def _mirrors_in_packed(node, node_type, out, path):
    """Зеркала внутри упакованного элемента: у содержимого СВОЙ якорь — элемент его вида. Адрес зеркала считается от элемента (`Element.TextBox`
    → `2/2/0/12`), а у вложенного элемента колонки записи элемента нет, только содержимое; поэтому якорь строится на месте: `{GUID типа, 0,
    содержимое}`. Не раскрылся конверт — сверять нечего: о сыром узле сказал уровень 1."""
    try:
        virtual = packed.unpack_node(node)
    except packed.PackedError:
        return
    content = virtual.children[packed.CONTENT]
    slot = node_type.fields[packed.CONTENT]
    picked = schema.pick(slot.type, content) if content.children else None
    anchor_type = schema.packed_anchor(picked) if picked else None
    if anchor_type is None:
        return
    guid = schema.ELEMENT_GUIDS[anchor_type[len("Element."):]]
    anchor = Node([Scalar("GUID", guid), Scalar("INT", "0"), content])
    _walk_mirrors(content, slot.type, anchor, anchor_type, out, path + (packed.CONTENT,))


def _mirror_at(slot, child, anchor_node, anchor_type, out, path, index):
    """Одна позиция обхода зеркал: спуск в блок или сверка со вторым адресом. Общая для обычного блока и узла со счётными списками."""
    if isinstance(child, Node):
        if isinstance(slot, (schema.N, schema.R)):
            _walk_mirrors(child, slot.type, anchor_node, anchor_type, out, path + (index,))
        if isinstance(slot, schema.N) and slot.mirror_of and anchor_node is not None:
            _mirror_block_problem(slot, child, anchor_node, anchor_type, path + (index,), out)
    elif isinstance(slot, schema.F) and slot.mirror_of and anchor_node is not None:
        _mirror_problem(slot, child, anchor_node, anchor_type, path + (index,), out)


def _mirrors_in_runs(node, node_type, anchor_node, anchor_type, out, path):
    plan = schema.read_runs(node_type, node.children)
    if plan is None:
        return                       # узел уехал сырым; про это сказал уровень 1
    spots, lists = plan
    for segment, start, members in lists:
        # Спуск в члены отрезка знает ВСЕ виды отрезка-списка: пропущенный вид — зеркало, которого проверка не увидит. У парного отрезка (`Along`) члены скаляры.
        if isinstance(segment, (schema.Counted, schema.CountedPairs, schema.Gated)):
            for i in members:
                _walk_mirrors(node.children[i], segment.type, anchor_node, anchor_type,
                              out, path + (i,))
        elif isinstance(segment, schema.Flagged):
            names = segment.raised(int(node.children[start].text))
            for name, i in zip(names or (), members):
                _walk_mirrors(node.children[i], segment.bits[name][1], anchor_node, anchor_type,
                              out, path + (i,))
        # Отрезок по МАСКЕ не назван нарочно: за битом скаляр, зеркало объявляется полем карты (`mirror_of`), у значения по биту слота нет. Слоты ПЕРЕД значениями зеркало нести могут — их обходит цикл по `spots`.
    for index, (_fallback, slot) in sorted(spots.items()):
        _mirror_at(slot, node.children[index], anchor_node, anchor_type, out, path, index)


def _check_mirrors(doc, type_name, out, root=None):
    """Зеркала: одно свойство палитры по нескольким адресам одного якоря. Считается по ДЕРЕВУ, а не по документу: адрес зеркала — позиции файла."""
    if root is None:
        try:
            root = typed.encode(doc, type_name, check=False)
        except ValueError:
            return                   # об этом уже сказал уровень 1, и сказал точнее
    _walk_mirrors(root, type_name, None, None, out, ())


def _check_lens(doc, type_name, out, corpus=None, root=None):
    """Длина блока против длин, виденных на этой позиции. Предупреждение, не отказ.

    **Единственная проверка на удаление ХВОСТОВОГО поля `u…`, и она нарочно слабая.** Дыру посреди блока ловит уровень 1; короткий хвост он пропускает:
    длин блоков карта не знает, и блок, который короче по праву, от обрезанного не отличить. Отказа нет и быть не может (`encode` на удалённом `u…`
    не отказывает; расхождение названо в `SKILL.md` и в шапке `FORMAT.md`).

    Проверку ведёт СВОДКА корпуса (длины считает `stat`). Две границы: сводка спрашивается только у ЦЕЛОЙ формы, и там, где позиции в сводке нет, проверка
    МОЛЧИТ («не видели» — значит «сказать нечего»). Дерево строится тем же `typed.encode`, считается тем же `stat.collect_root`."""
    if type_name != stat.KIND_FORM:
        return
    corpus = corpus_summary() if corpus is None else corpus
    if not corpus:
        return
    if root is None:
        try:
            root = typed.encode(doc, type_name, check=False)
        except ValueError:
            return                   # об этом уже сказал уровень 1, и сказал точнее
    unseen = []
    for (kind, path), pos in sorted(stat.collect_root(root).items()):
        row = (corpus.get(kind) or {}).get(path)
        seen = row.get("lens") if row else None
        if not seen:
            continue
        unseen += [(kind, path, length, seen) for length in sorted(pos.lens) if str(length) not in seen]
    platform = _platform_notes(root, unseen) if unseen else {}
    for kind, path, length, seen in unseen:
        where = f"{kind} {path}"
        note = platform.get((kind, path, length))
        head = f"{where}: в блоке детей {length}, а корпус на этой позиции видел длину {_lens_list(seen)}; длин блоков карта не знает, "
        if note and note[0] == "platform":
            tail = ("но такую длину платформа записывает сама (она есть в формах, сохранённых конфигуратором): запись навыка совпадает с записью "
                    "платформы, длина редкая для корпуса; на работу формы не влияет")
        elif note:
            what = "список страниц" if note[0] == "pages" else "запись страницы"
            tail = (f"но это {what} ({', '.join(str(n) for n in note[1])} стр.): список страниц стоит на разных позициях (перед ним разное число "
                    "списков стиля), и корпус на этой позиции видел чужие блоки; такие списки и записи страниц платформа записывает сама (они есть в формах, "
                    "сохранённых конфигуратором) — запись навыка совпадает с записью платформы, на работу формы не влияет")
        else:
            tail = ("и блок короче по праву здесь неотличим от блока, у которого убрали последнее поле u… — сверяйте с исходным файлом")
        out.append(Problem(2, False, where, head + tail, LENS))


_PLATFORM = []


def platform_lens():
    """Длины, которые записывала платформа и которых нет в корпусе (данные `platform_lens.json`), — один раз на процесс."""
    if not _PLATFORM:
        _PLATFORM.append(stat.load_platform_lens())
    return _PLATFORM[0]


def _platform_notes(root, unseen):
    """`{(якорь, адрес, длина): (источник, подробность)}` для длин, которые корпус не видел, но платформа писала сама: слова называют это, и предупреждение
    перестаёт читаться как поломка. Два источника.

    * Та же длина на той же позиции у формы, сохранённой конфигуратором (`platform_lens.json`, `lens`).
    * Список страниц панели и запись страницы: он стоит на разных позициях тела панели (перед ним числом списков стиля сдвинуто), и корпус на
      этой позиции видел чужие блоки. Узнаётся по строению (`stat.pages_list`), число страниц и длина записи — те, что платформа писала
      (`panel_pages`).

    Блок, не подтверждённый ни тем, ни другим, остаётся с прежним текстом: длины блоков карта не знает."""
    data = platform_lens()
    if not data:
        return {}
    lens, pages = data.get("lens") or {}, data.get("pages") or {}
    wanted = {(kind, path, length) for kind, path, length, _seen in unseen}
    notes = {}
    for key in wanted:
        kind, path, length = key
        if length in ((lens.get(kind) or {}).get(path) or ()):
            notes[key] = ("platform", None)
    found = {}
    for kind, path, node, parent in stat.walk_blocks(root):
        length = len(node.children)
        key = (kind, path, length)
        if key not in wanted or key in notes:
            continue
        rule = pages.get(kind) or {}
        counts, record_lens = rule.get("counts", ()), rule.get("record_lens", ())
        parts = path.split("/")
        if stat.pages_slot(kind, path):
            count = stat.pages_list(node)
            if count is not None and count in counts and len(node.children[2].children) in record_lens:
                found.setdefault(key, []).append(("pages", count))
                continue
        elif len(parts) > 1 and stat.pages_slot(kind, "/".join(parts[:-1])):
            count = stat.pages_list(parent)
            if count is not None and count in counts and length in record_lens:
                found.setdefault(key, []).append(("record", count))
                continue
        found.setdefault(key, []).append(None)
    for key, items in found.items():
        if items and all(item is not None for item in items):
            notes[key] = (items[0][0], tuple(sorted({count for _what, count in items})))
    return notes


def _check_guids(value, path, out):
    """Форма GUID — у всякой обёртки, где бы она ни лежала. По карте не сделать: GUID лежат и в СЫРЫХ узлах, до которых обход по именам не доходит;
    поэтому проверка ходит по ЗНАЧЕНИЮ. Отказ: текст не по форме GUID писатель положит без кавычек, и обратно он прочитается не тем видом скаляра или
    не прочитается вовсе."""
    if isinstance(value, dict):
        if set(value) == {"guid"}:
            guid = value["guid"]
            if not isinstance(guid, str) or not GUID_RE.fullmatch(guid):
                _say(out, 2, True, path, f"{guid!r} не по форме GUID "
                                         "(8-4-4-4-12 шестнадцатеричных знаков)")
            return
        for key, item in value.items():
            _check_guids(item, path + (key,), out)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _check_guids(item, path + (i,), out)


# ── Уровень 3: проверка обратным разбором ───────────────────────────────────────────────────────────────────────────

def _check_round_trip(doc, type_name, out):
    """Та же проверка, что внутри `encode`, но спрошенная отдельно и без записи на диск. Самопроверка `encode` не зовётся: её отказ винит КОДЕК, а
    здесь спрашивают про документ — расхождение обычно значит, что значение соберётся и разберётся иначе."""
    try:
        again = typed.decode(typed.encode(doc, type_name, check=False), type_name)
    except ValueError as e:
        out.append(Problem(3, True, "обратный разбор", str(e)))
        return
    if again != doc:
        difference = typed.first_difference(doc, again)
        out.append(Problem(3, True, difference.split(":")[0],
                           "разбор собственной сборки не совпал с входом — "
                           f"{difference}"))


def _level_shape(doc, type_name, out):
    _check_shape(doc, type_name, (), out)


def _level_links(doc, type_name, out, config=None):
    _check_links(doc, type_name, (), out)
    if type_name == "Form":
        _check_table_types(doc, out, config)
    _check_guids(doc, (), out)
    _check_picture_shapes(doc, (), out)
    _check_dec_places(doc, (), out)
    # Дерево собирается ОДИН раз на обе проверки, которым оно нужно.
    try:
        root = typed.encode(doc, type_name, check=False)
    except ValueError:
        root = None                  # об этом уже сказал уровень 1, и сказал точнее
    if root is not None:
        _check_mirrors(doc, type_name, out, root=root)
        _check_lens(doc, type_name, out, root=root)


def _level_round_trip(doc, type_name, out):
    _check_round_trip(doc, type_name, out)


def validate(doc, levels=LEVELS, type_name="Form", config=None):
    """Замечания по документу: форма (1), связи (2), проверка обратным разбором (3). Следующий уровень не спрашивается, если предыдущий нашёл отказ. Список замечаний, а не
    первое: JSON правят руками. Несуществующий уровень — отказ: пустой список читается как «всё хорошо». `config` — выгрузка конфигурации
    (`metadata.Config`): с ней уровень 2 сверяет ещё тип таблицы на табличной части с `TypeId` части."""
    unknown = [level for level in levels if level not in LEVELS]
    if unknown:
        raise ValueError(f"уровня проверки {', '.join(str(level) for level in unknown)} нет; "
                         "их три: 1 — форма, 2 — связи, 3 — проверка обратным разбором")
    out = []
    # Прежние имена краёв блока координат (`width`, `height`) больше не читаются: отказ уровня 1 на КАЖДОЕ место.
    old = typed.old_coords_places(doc) + typed.old_field_places(doc)
    if old:
        return [Problem(1, True, where, text) for where, text in old]
    # Проверка «дальше не идём» одна на все три уровня: отдельные условия разошлись бы.
    for level, step in ((1, _level_shape), (2, lambda d, t, o: _level_links(d, t, o, config)), (3, _level_round_trip)):
        if level in levels and not fatal(out):
            step(doc, type_name, out)
    return out
