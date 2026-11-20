"""Свойства самой формы, которых нет среди строк палитры: обработчики событий формы и «Сохраняемые значения».

Шрифт формы пишет `set_font` с `form=True` (`edit.font`). Все имена доступны через фасад `frm_codec.edit`.

Обработчики и «Сохраняемые значения» записаны так, как их пишет платформа; числа — по образцам форм.
"""

import copy

from .. import props
from .base import EditError, _on_corpus
from .data import _put_event
from .module import procedure_name_refusal
from .names import EVENT_ITEMS, EVENT_NAME, EVENTS
from .. import validate

FORM_PAGES_EVENTS = "form/container/layout_holder/events"
FORM_SETTINGS_EVENTS = "main_attribute/u2/events"
SAVED_VALUES = "main_attribute/u2/saved_values"

# Событие формы: ключ в файле → (код, имя в палитре, синоним, параметры процедуры, где лежит список). Коды, имена, синонимы и
# параметры взяты с формы, на которой платформа создала процедуры сама (синоним лежит в трёх языковых строках описания
# обработчика); параметры совпадают со справочником `1c8-doc`, `forms-ordinary/Форма/Форма.md` (раздел событий). У события формы первым
# параметром НЕ идёт `Элемент`, в отличие от событий элементов; исключение — ПриСменеСтраницы (событие контейнера страниц).
PLACE_FORM, PLACE_PAGES, PLACE_SETTINGS = "form", "pages", "settings"
FORM_EVENTS = {
    "BeforeOpen": (70000, "ПередОткрытием", "Перед открытием", ("Отказ", "СтандартнаяОбработка"), PLACE_FORM),
    "OnOpen": (70001, "ПриОткрытии", "При открытии", (), PLACE_FORM),
    "BeforeClose": (70002, "ПередЗакрытием", "Перед закрытием", ("Отказ", "СтандартнаяОбработка"), PLACE_FORM),
    "OnClose": (70003, "ПриЗакрытии", "При закрытии", (), PLACE_FORM),
    "ChoiceProcessing": (70004, "ОбработкаВыбора", "Обработка выбора", ("ЗначениеВыбора", "Источник"), PLACE_FORM),
    "ObjectActivationProcessing": (70005, "ОбработкаАктивизацииОбъекта", "Обработка активизации объекта",
                                   ("АктивныйОбъект", "Источник"), PLACE_FORM),
    "NewObjectWriteProcessing": (70006, "ОбработкаЗаписиНовогоОбъекта", "Обработка записи нового объекта",
                                 ("Объект", "Источник"), PLACE_FORM),
    "NotificationProcessing": (70007, "ОбработкаОповещения", "Обработка оповещения",
                               ("ИмяСобытия", "Параметр", "Источник"), PLACE_FORM),
    "OnReopen": (70008, "ПриПовторномОткрытии", "При повторном открытии", ("СтандартнаяОбработка",), PLACE_FORM),
    "RefreshDisplay": (70009, "ОбновлениеОтображения", "Обновление отображения", (), PLACE_FORM),
    "ExternalEvent": (70010, "ВнешнееСобытие", "Внешнее событие", ("Источник", "Событие", "Данные"), PLACE_FORM),
    "AddInDetachmentOnError": (70011, "ОтключениеВнешнейКомпонентыПриОшибке",
                               "Отключение внешней компоненты при ошибке", ("Местоположение", "Имя"), PLACE_FORM),
    "FillCheckProcessing": (70012, "ОбработкаПроверкиЗаполнения", "Обработка проверки заполнения",
                            ("Отказ", "ПроверяемыеРеквизиты"), PLACE_FORM),
    # Событие контейнера страниц формы: в файле у него код 0, и список лежит не в корне, а в контейнере.
    0: (0, "ПриСменеСтраницы", "При смене страницы", ("Элемент", "ТекущаяСтраница"), PLACE_PAGES),
    # События настроек: список лежит в блоке основного реквизита формы отчёта и обработки, коды числовые.
    80000: (80000, "ПередСохранениемЗначений", "Перед сохранением значений", ("Отказ",), PLACE_SETTINGS),
    80001: (80001, "ПослеВосстановленияЗначений", "После восстановления значений", (), PLACE_SETTINGS),
}
_BY_NAME = {row[1]: key for key, row in FORM_EVENTS.items()}
# Сколько форм снимка из 4 993 несут событие. У двух событий формы образцов нет вовсе; события настроек считаются среди 2 567
# форм с блоком настроек.
CORPUS_FORM_EVENTS = {
    "BeforeOpen": 3158, "OnOpen": 3642, "BeforeClose": 1840, "OnClose": 1609, "ChoiceProcessing": 118,
    "ObjectActivationProcessing": 5, "NewObjectWriteProcessing": 33, "NotificationProcessing": 1804,
    "OnReopen": 49, "RefreshDisplay": 439, "ExternalEvent": 68, "AddInDetachmentOnError": 0,
    "FillCheckProcessing": 0, 0: 2, 80000: 32, 80001: 42,
}
# «Сохраняемые значения»: запись `{"#", GUID вида записи, {3, GUID реквизита, имя, признак[, {id}]}}`; GUID вида записи — один у всех 3 149 записей снимка. У записи реквизита формы признак 1 и номер реквизита (338
# записей), у записи реквизита объекта метаданных признак 0 и номера нет (2 811).
SAVED_KIND_GUID = "91f722a0-4cc1-11d6-a3c9-0050bae0a776"
SAVED_FORM_ATTRIBUTE = 3
CORPUS_SAVED_VALUES = {"реквизит формы": 338, "реквизит объекта": 2811}


def form_event_key(event):
    """Ключ события формы по названному: английский код карты, имя из палитры или число (80000/80001). `None` — не знаем."""
    if isinstance(event, bool):
        return None
    if isinstance(event, int):
        return event if event in FORM_EVENTS else None
    if isinstance(event, str):
        if event in FORM_EVENTS:
            return event
        return _BY_NAME.get(event)
    return None


def _event_list(doc, key):
    """Список обработчиков события: `(блок списка, где лежит словами)` или отказ словами."""
    place = FORM_EVENTS[key][4]
    if place == PLACE_FORM:
        block, where = doc.get(EVENTS), "events"
    elif place == PLACE_PAGES:
        node = doc
        for part in ("form", "container", "layout_holder"):
            node = node.get(part) if isinstance(node, dict) else None
        block, where = (node.get(EVENTS) if isinstance(node, dict) else None), FORM_PAGES_EVENTS
    else:
        kind = props.form_settings(doc)
        if kind != "настройки":
            guid = ((doc.get("main_attribute") or {}).get("main_attribute_type") or {}).get("guid", "—")
            shape = {"без блока": "нет вовсе",
                     "события объекта": f"несёт события объекта (тип основного реквизита `{guid}`)",
                     "иное": f"другого строения (тип основного реквизита `{guid}`)"}[kind]
            raise EditError(
                f"события {FORM_EVENTS[key][1]} живут в блоке НАСТРОЕК основного реквизита (`{FORM_SETTINGS_EVENTS}`), "
                f"а у этой формы этот блок {shape} — это не блок настроек. Блок настроек со «Сохраняемыми значениями» "
                "стоит только у форм отчёта и обработки; у формы объекта на тех же позициях события объекта, и писать "
                "сюда значило бы править другое")
        block, where = doc["main_attribute"]["u2"].get(EVENTS), FORM_SETTINGS_EVENTS
    if not isinstance(block, dict) or not isinstance(block.get(EVENT_ITEMS), list):
        raise EditError(f"у формы не разобран список обработчиков `{where}` — править его именами нечем")
    return block, where


def _procedure_words(key):
    code, ru, _text, params, _place = FORM_EVENTS[key]
    return f"{ru}({', '.join(params)})"


def set_form_event(doc, event, procedure=None, text=None, remove=False):
    """Обработчик события самой формы: процедура модуля; `remove=True` снимает обработчик.

    `event` — английский код карты (`BeforeOpen`…`FillCheckProcessing`, тринадцать событий формы), имя из палитры
    (`ПередОткрытием`, `ПриСменеСтраницы`, `ПередСохранениемЗначений`…) либо число 80000/80001. События лежат в трёх списках
    (`FORM_EVENTS`): тринадцать — в корне формы, ПриСменеСтраницы — у встроенного контейнера страниц, ПередСохранениемЗначений
    и ПослеВосстановленияЗначений — в блоке настроек основного реквизита (только у форм отчёта и обработки; у других форм
    отказ называет, что лежит на этом месте). Новая запись встаёт на своё место по коду, как у элементов, прежняя заменяется
    на месте.

    Запись и описание — те же, что у обработчиков элементов (`set_event`); текст описания по умолчанию — синоним события из
    палитры (так записывает платформа), `text` его заменяет. Процедуру в модуль дописывает `append_procedure`:
    сигнатуру события называет отчёт (у событий формы первым параметром НЕ идёт `Элемент`, исключение — ПриСменеСтраницы).
    """
    key = form_event_key(event)
    if key is None:
        known = ", ".join(f"{k} ({row[1]})" for k, row in FORM_EVENTS.items())
        raise EditError(f"события формы {event!r} нет; есть: {known}")
    code, ru, synonym, _params, place = FORM_EVENTS[key]
    block, where = _event_list(doc, key)
    items = block[EVENT_ITEMS]
    value = key if place == PLACE_FORM else code
    seen = CORPUS_FORM_EVENTS[key]
    who = f"форма ({where})"
    if remove:
        if procedure is not None or text is not None:
            raise EditError("remove=true снимает обработчик, а procedure и text называют новый: это две разные правки — "
                            "снимите обработчик одним вызовом, поставьте другим")
        at = next((i for i, row in enumerate(items)
                   if isinstance(row, dict) and row.get(EVENT_NAME) == value), None)
        if at is None:
            have = ", ".join(str(row.get(EVENT_NAME)) for row in items if isinstance(row, dict)) or "—"
            raise EditError(f"обработчика события {ru} у формы нет; в списке `{where}`: {have}")
        del items[at]
        block["count"] = len(items)
        return (f"{who}: обработчик события {ru} снят; процедура в модуле остаётся — уберите её сами"
                + _on_corpus("set_form_event/remove", f"событие {ru}", 1))
    if not isinstance(procedure, str) or not procedure:
        raise EditError("procedure — имя процедуры модуля формы; чтобы снять обработчик, передайте remove=true")
    refused = procedure_name_refusal(procedure)
    if refused:
        raise EditError(refused)
    kind = "Form"
    said = _put_event({EVENTS: block}, kind, value, procedure, synonym if text is None else text, who,
                      "", f"формы ({where})")
    said = said.replace(f"событие {value}", f"событие {ru}", 1)
    tail = f"; сигнатура процедуры: {_procedure_words(key)}"
    if place == PLACE_PAGES:
        tail += " — контейнер страниц, поэтому первым параметром идёт Элемент"
    elif place == PLACE_FORM:
        tail += " — у события формы первым параметром Элемента нет"
    note = _on_corpus("set_form_event/handler", f"событие {ru}", seen if seen else None)
    return said + tail + note


# ── «Сохраняемые значения» ──

def _saved_block(doc):
    """Блок списка «Сохраняемые значения» или отказ словами: список есть только у блока настроек."""
    kind = props.form_settings(doc)
    if kind != "настройки":
        guid = ((doc.get("main_attribute") or {}).get("main_attribute_type") or {}).get("guid", "—")
        shape = {"без блока": "нет вовсе",
                 "события объекта": f"несёт события объекта (тип основного реквизита `{guid}`)",
                 "иное": f"другого строения (тип основного реквизита `{guid}`)"}[kind]
        raise EditError(
            f"«Сохраняемые значения» живут в блоке НАСТРОЕК основного реквизита (`{SAVED_VALUES}`), а у этой формы этот "
            f"блок {shape} — это не блок настроек. Блок настроек стоит только у форм отчёта и обработки; у формы объекта на "
            "том же месте события объекта, и писать сюда значило бы править другое")
    return doc["main_attribute"]["u2"]


def _saved_name(row):
    pair = row.get("u2") if isinstance(row, dict) else None
    return pair[2] if isinstance(pair, list) and len(pair) > 2 and isinstance(pair[2], str) else None


def set_saved_values(doc, name, remove=False, guid=None, unverified=False, config=None, object_attribute=False):
    """Список «Сохраняемые значения» формы отчёта и обработки: добавить реквизит формы или реквизит обработки, либо снять запись.

    `remove=True` снимает запись по имени реквизита (как в диалоге «Выбор объекта»); счётчик ведёт операция. Платформой
    снятие не проверялось (список с меньшим числом записей и пустой список в образцах форм есть). Флажок «Сохранять значения»
    операция не трогает (`set_property` с `save_values`): в образцах форм список бывает и при снятом флажке, и отчёт называет
    состояние флажка.

    Добавление — запись реквизита ФОРМЫ в виде, который пишет платформа: `{"#", GUID вида, {3, GUID реквизита, имя, 1, {номер}}}`, номер
    берётся из списка реквизитов формы. GUID реквизита платформа берёт из своих метаданных, в файле формы его больше нигде
    нет (так у всех 338 записей образцов с реквизитом формы), поэтому операция принимает его только параметром `guid` и
    только с `unverified=True`; без него — отказ. Запись реквизита объекта (признак 0; GUID — метаданных объекта) берёт
    GUID из выгрузки конфигурации, см. ниже. Основной реквизит
    формы диалог не предлагает (в списке диалога «основного реквизита нет»), и запись о нём — отказ.

    Реквизит ОБЪЕКТА (обработки) — тот же вызов с выгрузкой конфигурации (`--config`; в API — `config`): GUID записи равен
    `uuid` реквизита в выгрузке (`<Attribute uuid>` в `DataProcessors/<Обработка>.xml`), имя — имя реквизита, признак 0, номера
    реквизита формы в записи нет: `{"#", GUID вида, {3, uuid, имя, 0}}`. Так платформа записала оба реквизита, выбранных в
    диалоге. Объект формы берётся по типу основного реквизита (`edit.datapath.form_object`), и выгрузка, не относящаяся к форме, отвергается
    тем же правилом, что у `bind`. Имя, которого у реквизитов формы нет, ищется у объекта; если имя есть и у формы, и у объекта, реквизит
    объекта называют `object_attribute=true`. Табличная часть обработки («Табличная часть.<Имя>» в диалоге) записывается так же:
    GUID — `uuid` `<TabularSection>` в выгрузке, имя — имя табличной части, признак 0 (так платформа записала «Строки»).
    """
    if not isinstance(name, str) or not name:
        raise EditError("name — имя реквизита формы, как его показывает диалог «Выбор объекта»")
    block = _saved_block(doc)
    saved = block["saved_values"]
    items = saved["items"]
    names = [_saved_name(row) for row in items]
    flag = "☑" if block.get("save_values") else "☐"
    state = (f"; флажок «Сохранять значения» {flag}"
             + ("" if block.get("save_values") else " — пока он снят, список не действует (поставьте set_property save_values)"))
    if remove:
        if guid is not None:
            raise EditError("remove=true снимает запись по имени; guid нужен только при добавлении")
        if name not in names:
            raise EditError(f"в списке «Сохраняемые значения» {name!r} нет; есть: {', '.join(map(str, names)) or '—'}")
        del items[names.index(name)]
        saved["count"] = len(items)
        return (f"«Сохраняемые значения»: запись {name!r} снята, записей {len(items)}" + state
                + _on_corpus("set_saved_values/remove", "снятие записи", 1))
    if name in names:
        raise EditError(f"в списке «Сохраняемые значения» {name!r} уже есть")
    attributes = (doc.get("attributes") or {}).get("list", {}).get("items", [])
    found = [row for row in attributes if isinstance(row, dict) and row.get("name") == name]
    if object_attribute or (not found and config is not None):
        if guid is not None:
            raise EditError("guid у реквизита обработки не нужен: он берётся из выгрузки конфигурации (uuid реквизита)")
        return _add_object_attribute(doc, saved, name, config, unverified, state)
    if not found:
        raise EditError(
            f"реквизита формы {name!r} нет. Реквизит ОБЪЕКТА (обработки) операция заводит с выгрузкой конфигурации: "
            f"дайте --config КАТАЛОГ — GUID записи берётся из неё (записей реквизитов объекта в снимке "
            f"{CORPUS_SAVED_VALUES['реквизит объекта']}). Реквизиты формы: "
            + (", ".join(str(row.get("name")) for row in attributes) or "—"))
    main_id = ((doc.get("attributes") or {}).get("u0") or {}).get("main_attribute_id")
    ident = found[0].get("u0")
    number = ident[0] if isinstance(ident, list) and ident and isinstance(ident[0], int) else None
    if number is None:
        raise EditError(f"у реквизита {name!r} не разобран номер (`u0`) — запись собрать нечем")
    if number == main_id:
        raise EditError(f"{name!r} — основной реквизит формы: диалог «Выбор объекта» его не предлагает "
                        "(в списке диалога основного реквизита нет), и запись о нём платформа не писала")
    if guid is None:
        raise EditError(
            f"у записи нужен GUID реквизита {name!r}: платформа берёт его из своих метаданных, в файле формы его нет "
            "(у всех 338 записей образцов с реквизитом формы он нигде больше не встречается). Назвать его операции "
            "можно параметром guid вместе с unverified=true — тогда запись собрана по строению, которое пишет платформа, а GUID "
            "проверяете вы; без него добавьте запись в диалоге «Сохраняемые значения» конфигуратора")
    if not isinstance(guid, str) or not props_guid(guid):
        raise EditError(f"guid — строка вида xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx, а пришло {guid!r}")
    if not unverified:
        raise EditError(
            "GUID реквизита операция проверить не может: ни файл формы, ни образцы его не хранят. Платформа приняла "
            "запись только с тем GUID, что дала сама. Чтобы всё же добавить запись, передайте unverified=true")
    row = {"u0": "#", "u1": {"guid": SAVED_KIND_GUID},
           "u2": [SAVED_FORM_ATTRIBUTE, {"guid": guid}, name, 1, [number]]}
    items.append(copy.deepcopy(row))
    saved["count"] = len(items)
    return (f"«Сохраняемые значения»: добавлена запись {name!r} (реквизит формы №{number}, GUID {guid}), записей {len(items)}"
            + state + _on_corpus("set_saved_values/add", "запись реквизита формы", 1))


def _add_object_attribute(doc, saved, name, config, unverified, state):
    """Запись реквизита или табличной части обработки: GUID — `uuid` из выгрузки конфигурации, признак 0, номера реквизита формы нет."""
    if config is None:
        raise EditError(
            f"{name!r} — не реквизит формы; запись реквизита ОБЪЕКТА (обработки) берёт GUID из выгрузки конфигурации, а выгрузки "
            "нет: нужна выгрузка конфигурации (--config КАТАЛОГ с DataProcessors/<Обработка>.xml). Без неё добавьте запись "
            "в диалоге «Сохраняемые значения» конфигуратора")
    from .. import metadata
    from . import datapath
    config = datapath.load_config(config)
    fo = datapath.form_object(doc, config, datapath.OBJECT_WORD, unverified=unverified)
    obj = fo.obj
    if obj.kind != "processing":
        raise EditError(
            f"основной реквизит формы — «{obj.full_name}», а запись реквизита объекта проверена только у обработки: "
            "у объекта другого вида диалог мог бы предложить иное")
    tables = [t for t in obj.tables if t.name == name]
    try:
        attr = obj.attribute(name)
    except metadata.MetadataError:
        if not tables:
            raise EditError(f"у «{obj.full_name}» в выгрузке нет реквизита или табличной части {name!r}; реквизиты: "
                            f"{', '.join(a.name for a in obj.attributes) or '—'}; табличные части: "
                            f"{', '.join(t.name for t in obj.tables) or '—'}") from None
        attr = tables[0]
    kind = "табличной части" if tables and attr is tables[0] else "реквизита"
    row = {"u0": "#", "u1": {"guid": SAVED_KIND_GUID}, "u2": [SAVED_FORM_ATTRIBUTE, {"guid": attr.uuid}, name, 0]}
    saved["items"].append(row)
    saved["count"] = len(saved["items"])
    what = "uuid табличной части" if kind == "табличной части" else "uuid реквизита"
    return (f"«Сохраняемые значения»: добавлена запись {kind} обработки {name!r} (GUID {attr.uuid} из выгрузки), "
            f"записей {saved['count']}; запись такая же, как записала платформа (признак 0, GUID — {what} из выгрузки)" + state)


def props_guid(text):
    return validate.GUID_RE.fullmatch(text) is not None
