"""Шаблоны узлов для редактора: «элемент по умолчанию» в том виде, как его пишет платформа.

Узлы взяты из базовых копий форм платформы, в которых элемент положен на форму и ничего в нём не изменено. Шаблоны хранятся
готовыми JSON-файлами в `frm_codec/data/templates/`. Из шаблона удалено всё, что связывает узел с формой-источником: имя
(`name_block`), координаты (нули), привязки границ (значение «привязки нет»), списки зависимых элементов и хвост блока
координат. Остальное осталось так, как записала платформа: цвета, шрифт, флаги, версии блоков и единственная страница панели.
"""
import copy
import pathlib

from .json0 import loads
from .datapaths import TEMPLATES_DIR

DIR = TEMPLATES_DIR

# Классы типа реквизита, для которых есть образец колонки табличной части и колонки списка.
TABULAR_COLUMNS = ("row_number", "string", "decimal", "catalog", "boolean", "date", "datetime", "time", "document", "enum", "composite")
LIST_COLUMNS = ("picture", "code", "description", "date", "number")

NO_ANCHOR_SIDE = 6  # значение «привязки нет»: сторона 6 при объекте −1
NO_OBJECT = -1
ZERO_GUID = "00000000-0000-0000-0000-000000000000"


def clean_coords(coords):
    """Блок координат шаблона: голова такая же, как у платформы, а всё, что относится к исходной форме, удалено."""
    from . import edit
    out = copy.deepcopy(coords)
    for key in (edit.X, edit.Y, edit.WIDTH, edit.HEIGHT):
        out[key] = 0
    none_rule = {edit.RULE_OBJECT: NO_OBJECT, edit.RULE_SIDE: NO_ANCHOR_SIDE, edit.RULE_OFFSET: 0}
    for key in edit.ANCHORS:
        anchor = out.get(key)
        if not isinstance(anchor, dict):
            continue
        # У привязки два правила, и оба очищаются по имени.
        for rule_name in edit.RULES:
            rule = anchor.get(rule_name)
            if isinstance(rule, dict):
                rule.update(none_rule)
    for key in edit.DEPENDENTS + edit.EMPTY_LISTS:
        out[key] = []
    out[edit.PAGE] = out[edit.PAGE_SEQUENCE] = out[edit.TAB_ORDER] = 0
    return out


def clean_node(node):
    """Очищает узел элемента перед пересадкой на месте. Одно правило действует и для шаблона, и для узла, созданного по образцу
    соседа (`edit.add_element(like=…)`).
    """
    from . import edit
    node[edit.NAME_BLOCK][edit.NAME] = ""
    node[edit.COORDS] = clean_coords(node[edit.COORDS])
    # Вложенные элементы шаблон не содержит: их добавляют отдельными вызовами `add_element(holder=…)`.
    node[edit.ELEMENTS] = {edit.COUNT: 0, edit.ITEMS: []}
    # Голова блока действий командной панели у каждой новой панели своя. Если взять её из пула, две панели из шаблона на одной
    # форме получили бы одинаковую голову, как у копий. Поэтому она обнуляется, как у шаблона меню (`button-menu`), а выставляет её
    # `add_element`. У панели в пуле кнопок нет, и ссылок на голову внутри блока, кроме неё самой, тоже нет.
    for _bar, block in edit._bars(node):
        block[edit.ACTIONS_GUID] = {"guid": ZERO_GUID}
    return node


_CACHE = {}


def load(name):
    """Шаблон с диска. Возвращается копия, которую вызывающий вправе изменять. Если шаблона нет, отказ перечисляет известные."""
    if name not in _CACHE:
        path = DIR / f"{name}.json"
        if not path.exists():
            known = ", ".join(sorted(p.stem for p in DIR.glob("*.json"))) or "—"
            raise ValueError(f"шаблона {name!r} нет; есть: {known}")
        _CACHE[name] = loads(path.read_text(encoding="utf-8"))
    return copy.deepcopy(_CACHE[name])


def element(kind):
    """Узел элемента по имени шаблона."""
    return load(kind)["node"]


def table_bar_node():
    """Командная панель таблицы — как её пишет конструктор: шаблон пула `CommandBar` и пять отличий (против шаблона): горизонтальная ориентация,
    автозаполнение, счётчик действий 9, нулевой первый член набора, источник действий — таблица (его ставит `set_action_source`, когда таблица есть).
    Голову блока действий выдаёт `add_element`. Один код на `generate` и на `add_element(bar_for=<таблица>)`."""
    node = element("CommandBar")
    content = node["content"]["u1"]
    content["orientation"] = "Horizontal"
    content["auto_fill"] = True
    content["actions"]["last_number"] = 9
    content["actions"]["button_sets"][0]["L1+0"][0] = 0
    return node


# Панель формы. Верхняя — с автозаполнением: запись панели конструктора формы списка (`ДействияФормы`: автозаполнение, источник действий — форма, подчёркивание,
# кнопки слева, «Вспомогательная»); у верхних панелей формы с автозаполнением в корпусе это оформление у всех видов. Нижняя — как у конструктора, БЕЗ автозаполнения:
# кнопки файлом со стандартными действиями формы по виду (корпус: нижней панели формы с автозаполнением нет ни одной; панель с автозаполнением внизу повторяет верхнюю:
# у документа тот же набор, у обработки без основного реквизита одна «?»).
FORM_BOTTOM_KINDS = ("document.item", "catalog.item", "processing")


def form_bar_node(place="top"):
    """Верхняя панель формы с автозаполнением и источником действий — формой (`place` — только `top`; нижняя — `form_bottom_bar_node`)."""
    if place != "top":
        raise ValueError(f"панель формы с автозаполнением — только верхняя (top), а пришло {place!r}: нижняя панель ставится кнопками конструктора (form_bottom_bar_node)")
    return element("CommandBar-list")


def form_bottom_bar_node(kind):
    """Нижняя панель формы конструктора вида `kind` (`FORM_BOTTOM_KINDS`): кнопки стандартных действий формы файлом (документ и элемент справочника — «ОК», «Записать»,
    «Закрыть»; обработка — «Закрыть»), без автозаполнения, источник действий — форма, кнопки справа, линия сверху. Запись берётся из заготовки формы конструктора
    (`frm_codec/data/blanks`, `blank.load`): второй копии нет. Узел очищен, как шаблон: голова блока действий и владельцы кнопок — нулевые, `add_element` выдаёт новую голову."""
    from . import blank, edit
    if kind not in FORM_BOTTOM_KINDS:
        raise KeyError(kind)
    doc = blank.load(kind)
    bar = next(item for item in edit.elements_of(edit.container(doc)) if edit.name_of(item) == blank.BOTTOM_BAR)
    node = clean_node(copy.deepcopy(bar))
    numbers = set()
    for _name, block in edit._bars(node):
        for _set, button in edit._buttons(block):
            button[edit.BTN_OWNER] = {"guid": ZERO_GUID}
            numbers.add(button.get(edit.NUMBER))
    content = node[edit.CONTENT]["u1"]
    if content.get("default_button") not in numbers:
        content["default_button"] = 0       # заготовка обработки убрала «Выполнить», а номер кнопки по умолчанию остался на ней; корпус у «Закрыть» без неё — 0
    return node


def button():
    """Возвращает `(узел кнопки, запись действия)` с нулевыми GUID и нулевым владельцем. Всё это выставляет `add_button`, а
    владельцем становится голова блока, в который помещена кнопка.
    """
    value = load("CommandBarButton")
    return value["node"], value["action"]


def action(kind):
    """Запись действия-образца. Сейчас вид один — `procedure`."""
    return load(f"action-{kind}")["action"]


def menu():
    """Пустой блок меню кнопки. Голова блока нулевая (её ставит `set_menu_mode`), набор постоянный."""
    return load("button-menu")["menu"]


def table_first_column():
    """Первая колонка таблицы значений: колонка шаблона `TableBox`, очищенная от имени и Данных. Возвращается копия.

    Шаблон `TableBox` и так несёт одну колонку, и это та же колонка: так платформа пишет колонку таблицы значений с полем ввода
    строки, «в новой колонке», ширина 100, порядковый номер 0.
    """
    from . import edit
    block = edit.columns_of(load("TableBox")["node"])
    return copy.deepcopy(block[edit.COLUMN_ITEMS][0])


def tabular_table():
    """Узел табличного поля на табличную часть в том виде, как его пишет конструктор: без колонок, `TypeId` части нулевой. Возвращается копия."""
    return load("TableBox-tabular")["node"]


def tabular_column(kind):
    """Колонка табличной части по классу типа (`TABULAR_COLUMNS`): очищенный образец конструктора. Возвращается копия."""
    if kind not in TABULAR_COLUMNS:
        raise ValueError(f"образца колонки «{kind}» нет; есть: {', '.join(TABULAR_COLUMNS)}")
    return load(f"column-tabular-{kind}")["node"]


def list_column(kind):
    """Стандартная колонка списка (`LIST_COLUMNS`): очищенный образец конструктора. Возвращается копия."""
    if kind not in LIST_COLUMNS:
        raise ValueError(f"образца стандартной колонки списка «{kind}» нет; есть: {', '.join(LIST_COLUMNS)}")
    return load(f"column-list-{kind}")["node"]


def class_record(host, cls):
    """Запись класса типа для поля шапки (`host == "field"`) или вложенного поля колонки (`"column"`). Возвращается копия или
    `None`, если у класса записи нет (булево).
    """
    record = load("class-records")[host].get(cls)
    return copy.deepcopy(record) if record is not None else None


def column_control(key):
    """Возвращает `(содержимое, тип значения колонки образца)` вложенного элемента по ключу."""
    value = load(f"column-control-{key}")
    return value["content"], value["value_type"]
