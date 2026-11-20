"""Операция «Выбор периода»: набор из пяти элементов, двух реквизитов формы и процедуры модуля — так его ставит мастер конструктора.

Часть редактора. Мастер вставляет в форму сразу весь набор: надпись «Период с:», поле ввода даты, надпись «по:», второе поле ввода
даты, кнопку «...» с обработчиком нажатия; для двух полей он заводит реквизиты формы типа Дата и привязывает поля к ним, а в
модуль дописывает процедуру, которая открывает окно настройки периода. Образец — форма, которую записал конструктор (выход
мастера на пустой форме, имена и место заданы). Операция воспроизводит его: форма и модуль после неё равны образцу, кроме
привязок границ — их при записи формы пересчитывают АвтоПравила (`edit.AUTO_RULES_SELF_WORDS`).

Операция правит и форму, и модуль, поэтому стоит в отдельном перечне `COMBINED_OPS` (`edit.ops`): функция получает документ и
байты модуля и возвращает `(слова, новый модуль)`.
"""
import copy
import re

from .. import textwidth
from .base import EditError, element_names, find_element
from .elements import add_element
from .data import add_attribute, bind, set_event
from .module import append_procedure
from .setprop import set_property
from .. import design as _design
from . import datatype as _datatype

# Подписи надписей и обработчик, как их задаёт мастер.
FROM_TEXT = "Период с:"
TO_TEXT = "по:"
END_NAME = "КонПериода"
BUTTON_NAME = "КнопкаВыбораПериода"
HANDLER = "ВыбПериодНажатие"
BUTTON_TEXT = "..."
# Размеры и зазоры набора в пикселях: ширина поля даты, высота всех пяти элементов, ширина кнопки; зазор надпись → поле, поле →
# надпись и поле → кнопка. Ширина надписи — ширина текста плюс 1 (у надписей «Период с:» и «по:» образца это 51 и 16 при ширине текста
# 50 и 15).
FIELD_W, ROW_H, BUTTON_W = 83, 19, 21
GAP_LABEL, GAP_FIELD, GAP_BUTTON = 5, 5, 7
LABEL_PAD = 1
# Описатель типа реквизитов набора: Дата, состав «Дата».
DATE_PATTERN = {"mark": "Pattern", "types": [{"kind": "D", "date_fractions": "D"}]}
# Строка реквизита, которую заводит мастер, несёт `u1` = 1 (у основного реквизита обработки он 0).
ATTRIBUTE_U1 = 1
# Номер версии общего блока формы, на которой снят образец.
FORM_VERSION = 16


def procedure_body(first, last):
    """Тело процедуры нажатия: окно настройки периода над двумя реквизитами формы. Строки — как в модуле образца."""
    return (
        "НастройкаПериода = Новый НастройкаПериода;",
        "НастройкаПериода.РедактироватьКакИнтервал = Истина;",
        "НастройкаПериода.РедактироватьКакПериод = Истина;",
        "НастройкаПериода.ВариантНастройки = ВариантНастройкиПериода.Период;",
        f"НастройкаПериода.УстановитьПериод({first}, ?({last}='0001-01-01', {last}, КонецДня({last})));",
        "Если НастройкаПериода.Редактировать() Тогда",
        f"\t{first} = НастройкаПериода.ПолучитьДатуНачала();",
        f"\t{last} = НастройкаПериода.ПолучитьДатуОкончания();",
        "КонецЕсли;")


def humanize(name):
    """Описание обработчика, как его заполняет платформа по имени процедуры: слова по заглавным буквам, кроме первого — строчные
    («ВыбПериодНажатие» → «Выб период нажатие»)."""
    words = re.sub(r"(?<=[а-яa-z0-9])(?=[А-ЯA-Z])", " ", name).split(" ")
    return " ".join([words[0]] + [w[:1].lower() + w[1:] for w in words[1:]])


def _free_name(doc, stem, taken):
    """Первое свободное имя `<stem><n>`, n с единицы: так платформа называет надписи."""
    names = set(element_names(doc)) | set(taken)
    number = 1
    while f"{stem}{number}" in names:
        number += 1
    return f"{stem}{number}"


def add_period_choice(doc, bsl, name, box=None, end_name=END_NAME, button_name=BUTTON_NAME, handler=HANDLER,
                      from_label=None, to_label=None, after=None, kind=None, grow=False, shrink=False, unverified=False):
    """Набор «Выбор периода» (мастер конструктора): надпись «Период с:», поле ввода даты `name`, надпись «по:», поле ввода даты
    `end_name`, кнопка «...» `button_name`; два реквизита формы типа Дата с теми же именами, привязка полей к ним, обработчик
    «Нажатие» кнопки `handler` и процедура этого обработчика в конце модуля. Возвращает `(слова отчёта, новый модуль)`.

    `name` — имя первого поля, его вводят в окне мастера; оно же имя первого реквизита. Остальные имена по умолчанию как у мастера:
    второе поле `КонПериода`, кнопка `КнопкаВыбораПериода`, процедура `ВыбПериодНажатие`, надписи — первые свободные `Надпись<n>`
    (`from_label`, `to_label` называют их явно).

    **Место.** `box` — `[лево, верх]` левого края первой надписи: пять элементов идут в одну строку правее, высота 19, зазоры
    мастера (надпись → поле 5, поле → надпись 5, поле → кнопка 7); ширина надписи — ширина текста плюс 1, поля — 83, кнопки — 21.
    Без `box` первая надпись ставится как `add_element` без `box` (по соседям формы; `after`, `kind`, `grow`, `shrink` — его параметры
    места), остальные — в её строку; ширину надписи тогда даёт `add_element` (ширина текста), а не мастер. Привязки границ новых элементов — «к себе», как у `add_element` с `box`:
    АвтоПравила формы пересчитывают их при записи.

    Условия и отказы. Нужен модуль формы (`--bsl`). Форма — поколения 16: мастер снят на ней, для других версий общего блока и
    строк реквизитов из пяти позиций операция отказывает. Имена элементов, реквизитов и процедуры не должны быть заняты;
    отказ до правки, форма и модуль остаются прежними. Окно настройки периода в 1С:Предприятии не запускалось: проверено
    только то, что конфигуратор принял форму с набором и создал процедуру (`unverified` принимается и ничего не меняет).
    """
    if bsl is None:
        raise EditError("операция дописывает процедуру в модуль формы, а модуль не назван: дайте --bsl и --bsl-out")
    if not isinstance(name, str) or not name or not isinstance(end_name, str) or not end_name:
        raise EditError("name (первое поле) и end_name (второе поле) — непустые имена")
    version = _design.form_version(doc)
    if version != FORM_VERSION:
        raise EditError(f"мастер «Выбор периода» снят на форме поколения {FORM_VERSION}, а у этой формы общий блок версии {version}: "
                        "набор строится из шаблонов этого поколения, на другой версии его реквизиты и поля не проверялись")
    if box is not None and not (isinstance(box, (list, tuple)) and len(box) == 2
                                and all(isinstance(v, int) and not isinstance(v, bool) for v in box)):
        raise EditError("box — [лево, верх] левого края первой надписи: два целых числа (высоту и ширины набор берёт у мастера)")
    attributes = doc.get("attributes") or {}
    rows = (attributes.get("list") or {}).get("items")
    if not isinstance(rows, list) or not rows:
        raise EditError("у формы нет разобранного списка реквизитов — завести реквизиты нечем")
    taken_attrs = {row.get("name") for row in rows if isinstance(row, dict)}
    clash = [n for n in (name, end_name) if n in taken_attrs]
    if clash:
        raise EditError(f"реквизит {', '.join(map(repr, clash))} у формы уже есть: имена полей набора совпадают с реквизитами формы, "
                        "которые завёл бы мастер; назовите поля иначе")
    if name == end_name:
        raise EditError("name и end_name — два разных поля, а имя одно")
    names = [name, end_name, button_name]
    if len(set(names)) != 3:
        raise EditError(f"имена полей и кнопки различны, а пришло {names}")
    from_label = from_label or _free_name(doc, "Надпись", names)
    to_label = to_label or _free_name(doc, "Надпись", names + [from_label])
    if len({from_label, to_label, *names}) != 5:
        raise EditError("пять элементов набора носят пять разных имён")
    busy = [n for n in (from_label, name, to_label, end_name, button_name) if n in element_names(doc)]
    if busy:
        raise EditError(f"элементы {', '.join(map(repr, busy))} в форме уже есть: переименуйте их или назовите набор иначе")
    # Модуль проверяется первым: отказ по имени процедуры не должен оставить форму с наполовину поставленным набором.
    new_bsl = append_procedure(bsl, handler, ("Элемент",), procedure_body(name, end_name), unverified=unverified)
    snapshot = copy.deepcopy(doc)
    try:
        said = _build(doc, name, end_name, button_name, from_label, to_label, handler, box, dict(after=after, kind=kind, grow=grow, shrink=shrink))
    except Exception:
        doc.clear()
        doc.update(snapshot)
        raise
    return said, new_bsl


def _build(doc, name, end_name, button_name, from_label, to_label, handler, box, where):
    steps = []
    label_w = [textwidth.width(FROM_TEXT) + LABEL_PAD, textwidth.width(TO_TEXT) + LABEL_PAD]
    if box is not None:
        left, top = box
        if any(v for v in where.values()):
            raise EditError("after, kind, grow и shrink называют, откуда взять место без box, а box место уже назвал: уберите box либо их")
        steps.append(add_element(doc, "Label", from_label, [left, top, label_w[0], ROW_H], caption=FROM_TEXT))
    else:
        steps.append(add_element(doc, "Label", from_label, caption=FROM_TEXT, **where))
        first = find_element(doc, from_label).element["coords"]
        left, top = first["x"], first["y"]
        label_w[0] = first["right"] - first["x"]
    x = left + label_w[0] + GAP_LABEL
    steps.append(add_element(doc, "TextBox", name, [x, top, FIELD_W, ROW_H]))
    x += FIELD_W + GAP_FIELD
    steps.append(add_element(doc, "Label", to_label, [x, top, label_w[1], ROW_H], caption=TO_TEXT))
    x += label_w[1] + GAP_LABEL
    steps.append(add_element(doc, "TextBox", end_name, [x, top, FIELD_W, ROW_H]))
    x += FIELD_W + GAP_BUTTON
    steps.append(add_element(doc, "Button", button_name, [x, top, BUTTON_W, ROW_H], caption=BUTTON_TEXT))
    for label in (from_label, to_label):
        set_property(doc, element=label, name="horizontal_align", value="Right")
    for field in (name, end_name):
        add_attribute(doc, field, pattern=copy.deepcopy(DATE_PATTERN))
        row = next(r for r in doc["attributes"]["list"]["items"] if r.get("name") == field)
        row["u1"] = ATTRIBUTE_U1
        bind(doc, element=field, attribute=field, copy_type=True)
        content = find_element(doc, field).element["content"]
        _datatype.apply_record(content, "dateTime", "field", field, was="string")
    set_event(doc, button_name, "Click", handler, text=humanize(handler))
    return (f"Выбор периода: надписи {from_label!r} и {to_label!r}, поля {name!r} и {end_name!r} (реквизиты формы типа Дата, "
            f"привязка полей к ним), кнопка {button_name!r} с обработчиком нажатия {handler!r}; процедура {handler!r} дописана в "
            f"модуль. Место: левый край {left}, верх {top}, высота {ROW_H}"
            + ("" if box is not None else "; первая надпись поставлена по соседям, как у add_element без box")
            + ". Набор повторяет выход мастера конструктора (форма и модуль совпадают с образцом, кроме привязок границ: их при "
              "записи формы пересчитывают АвтоПравила). Окно периода в предприятии не запускалось")
