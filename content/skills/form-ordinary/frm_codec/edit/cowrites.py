"""Свойства: согласованные поля, преднастройки и перевёрнутые флаги. Все имена доступны через фасад `frm_codec.edit`."""

import copy

from .. import schema, design as _design
from ..props import FORM_ANCHOR
from ..guids import (TEXT_DOCUMENT_BUILTIN_RECORD_GUID, TEXT_DOCUMENT_EXTENSIONS,
                    TEXT_DOCUMENT_EXTENSION_LABELS)

from .names import (
    ATTR_HEAD,
    ATTR_ID,
    ATTR_LIST,
    ATTR_NAME,
    ATTR_PATTERN,
    BINDINGS,
    BIND_ELEMENT,
    BIND_PATH,
    CORPUS_STAMP,
    PATH_STEPS,
    PATTERN_KIND,
    PATTERN_LENGTH,
    PATTERN_NUMBER,
    PATTERN_TYPES,
    STEP_VALUE,
    TEXTBOX_LENGTH,
    TEXTBOX_NUMBER,
    TEXTBOX_PATTERN,
    _at,
    _maybe,
)
from .base import EditError, find_element
from .platform import LIST_CHOICE_CHECKED
from .buttons import _named
from .elements import (
    CORPUS_LIST_CHOICE_DATA,
    LIST_CHOICE_MODE,
    _short,
    _type_words,
)
from .columns import _type_letters
from .formroot import MAIN_ATTRIBUTE_ID
from .propbase import (
    DATE_FRACTIONS,
    DERIVED,
    DERIVED_BY,
    SIDE_POSITIONS,
    SIDE_POSITIONS_ADDED,
    SIDE_WORDS,
    SIDE_WORDS_ADDED,
    TEXTBOX_COMMON_NODES,
    TEXTBOX_PROPS_NODE,
    TEXTBOX_VALUE_NODE,
    _find_one,
)


# Согласованные поля: что платформа записывает вместе с полем

# Зеркала (`mirror_of`) карта называет сама. Здесь описано остальное: поля, которые платформа записывает одной правкой палитры
# и которые встречаются в образцах форм только вместе (`CORPUS_COWRITES`). Числа показывают, в скольких случаях из всех они
# согласованы, для поля ввода формы и для вложенного поля ввода колонки.
CORPUS_COWRITES = {
    # маска поля ввода лежит дважды: среди свойств и в блоке значения (вариант 4)
    ("TextBox", "mask"): (13493, 13493), ("ColumnControl.TextBox", "mask"): (14405, 14405),
    # при непустой маске АвтоПереносСтрок снят у всех полей
    ("TextBox", "wrap"): (136, 136), ("ColumnControl.TextBox", "wrap"): (14, 14),
    # тройка «multi_line, зеркало, код» согласована
    ("TextBox", "multi_line"): (13464, 13493), ("ColumnControl.TextBox", "multi_line"): (14397, 14405),
    # квалификаторы числа лежат и среди свойств, и в описателе
    ("TextBox", "digits"): (3872, 3918), ("ColumnControl.TextBox", "digits"): (4330, 4342),
    ("TextBox", "fraction_digits"): (3912, 3918),
    ("ColumnControl.TextBox", "fraction_digits"): (4337, 4342),
    ("TextBox", "nonnegative"): (3906, 3918), ("ColumnControl.TextBox", "nonnegative"): (4337, 4342),
    # длина строки лежит и среди свойств, и в описателе
    ("TextBox", "length"): (6590, 6759), ("ColumnControl.TextBox", "length"): (7961, 8010),
    # состав даты записан кодом среди свойств и буквой в описателе
    ("TextBox", "date_fractions"): (2835, 2835), ("ColumnControl.TextBox", "date_fractions"): (1756, 1756),
    # отображение дерева записывается вместе с битом «Дерево» источника данных
    ("TableBox", "initial_tree_view"): (50, 54),
    # РежимВыбораИзСписка ☑ записывается вместе с блоком редактирования, кнопкой списка выбора и снятыми кнопками выбора и очистки.
    # Число показывает, у скольких полей с u9 = 1 спутник записан так, как его ставит платформа.
    ("TextBox", "list_choice_mode/edit_block"): (313, 318),
    ("ColumnControl.TextBox", "list_choice_mode/edit_block"): (56, 56),
    ("TextBox", "list_choice_mode/choice_list_button"): (316, 318),
    ("ColumnControl.TextBox", "list_choice_mode/choice_list_button"): (55, 56),
    ("TextBox", "list_choice_mode/choice_button"): (315, 318),
    ("ColumnControl.TextBox", "list_choice_mode/choice_button"): (55, 56),
    ("TextBox", "list_choice_mode/clear_button"): (267, 318),
    ("ColumnControl.TextBox", "list_choice_mode/clear_button"): (40, 56),
}

EDIT_BLOCK = ("Content.TextBox.u3", _maybe("Content.TextBox.u3", 1))
LIST_CHOICE_EDIT_GUID = "763308b0-510d-4302-8689-9d9f2a562598"
LIST_CHOICE_EDIT = {_maybe("Content.TextBox.u3.u1", 0): {"guid": LIST_CHOICE_EDIT_GUID},
                    _maybe("Content.TextBox.u3.u1", 1): {"u0": 0}}
# Кнопки, которые платформа ставит вместе с режимом: `(ключ, значение, чем подтверждено)`. Кнопки выбора и очистки относятся
# только к полю формы. У вложенного поля платформа их не показала, поэтому операция их там не снимает
# (`LIST_CHOICE_NESTED_KEEPS`).
LIST_CHOICE_BUTTONS = (
    ("choice_list_button", True, "так у вложенного поля и у поля формы"),
    ("choice_button", False, "так у поля формы"),
    ("clear_button", False, "так у поля формы"),
)
LIST_CHOICE_NESTED_KEEPS = ("choice_button", "clear_button")

CORPUS_LIST_CHOICE_LENGTH = (61, 71)
CORPUS_LIST_CHOICE_SHARED = (0, 374)
LIST_CHOICE_LENGTH = 255

DATE_LETTERS = {"Date": "D", "Time": "T", "DateTime": None}
# Маска лежит в двух узлах под одним именем: среди свойств поля и в блоке значения (вариант 4). Первым указан первичный адрес
# (`2/2/0/21`), второй изменяется вслед за ним.
MASK_NODES = (_named(TEXTBOX_PROPS_NODE, "mask"), _named(TEXTBOX_VALUE_NODE, "mask"))
WRAP = _named(TEXTBOX_PROPS_NODE, "wrap")[1]
MULTI_LINE = _named(TEXTBOX_VALUE_NODE, "multi_line")[1]

PATTERN_DATE = _at("PatternType.D", 1)
TREE_VIEW = _named("Content.TableBox.u2.u1", "initial_tree_view")[1]
TREE_FLAGS = _named(f"{schema.TABLE_BOX_SOURCE_BLOCK}.v12", "flags")[1]


def _pattern_single(found_all):
    """Единственный блок типа в описателе поля ввода: `(блок, буква, путь блока)`; иначе `(None, буквы, None)`."""
    found = next((found for found in found_all if found.key == TEXTBOX_PATTERN), None)
    pattern = found.holder.get(found.key) if found is not None else None
    types = pattern.get(PATTERN_TYPES) if isinstance(pattern, dict) else None
    if not isinstance(types, list) or len(types) != 1 or not isinstance(types[0], dict):
        return None, _type_letters(pattern), None
    return types[0], types[0].get(PATTERN_KIND), "/".join(found.trail + (PATTERN_TYPES, "0"))


def _list_choice_check(found_all, old, new, whose):
    """РежимВыбораИзСписка: что операция записывает, а что нет. В остальных случаях она отказывает с пояснением.

    Включение: когда платформа включает режим, она заменяет блок редактирования поля целиком (`LIST_CHOICE_EDIT`); поле без
    блока редактирования режим не получает. Снятие устроено отдельно (`_list_choice_off`): оно зависит от строения поля.
    """
    if new is True and old is not True and _find_one(found_all, *EDIT_BLOCK) is None:
        raise EditError(
            f"{LIST_CHOICE_MODE} у {whose}: у поля нет блока редактирования (u3/u1), а платформа "
            "записывает режим выбора из списка вместе с этим блоком. У полей с этим режимом блок всегда есть, "
            "поэтому у поля без блока строение такое, какого платформа не создаёт (так выглядит и поле, с которого режим снят: блока "
            "у него нет, и операция его не восстанавливает)")


def _list_choice_off(doc, element, anchor, found_all, whose, unverified):
    """РежимВыбораИзСписка ☐ у поля ввода формы: что платформа пишет, когда режим снимают.

    Возвращает `(записи, оговорки, вид данных)` либо отказывает. Проверено у поля, привязанного к своему реквизиту формы путём
    из одного шага, у которого режим был включён и тип пуст («Произвольный»): режим и КнопкаСпискаВыбора ставятся в ложь, блок
    редактирования убирается целиком (`u3/u0` 1 → 0, блока `u3/u1` нет), а тип остаётся произвольным и Длина остаётся 255. Тип
    не возвращается, а операции, которая вернула бы строку, у редактора нет. Остальное операция отказывает (вложенное поле колонки, блок редактирования не
    тот, что ставит включение, прочие виды данных); отказ по виду данных снимает `unverified`, и тогда записывается то же.
    """
    if anchor != "TextBox":
        raise EditError(
            f"{LIST_CHOICE_MODE} у {whose}: снятие режима проверялось только у поля ввода формы, а у вложенного поля "
            "колонки блок редактирования и тип выводятся из колонки, и что платформа пишет при снятии, не проверялось. "
            "Снимите режим в конфигураторе")
    block = _find_one(found_all, *EDIT_BLOCK)
    if block is None:
        raise EditError(f"{LIST_CHOICE_MODE} у {whose}: у поля нет блока редактирования (u3/u1): режим включён, а блока, "
                        "который платформа ставит вместе с ним, нет — такое строение платформа не создаёт, и что она "
                        "напишет при снятии, неизвестно")
    if block.holder.get(block.key) != LIST_CHOICE_EDIT:
        raise EditError(
            f"{LIST_CHOICE_MODE} у {whose}: блок редактирования поля не тот, что платформа ставит при включении режима "
            f"(`{LIST_CHOICE_EDIT_GUID[:8]}…` с вариантом 0): у 5 полей из 318 с этим режимом в образцах форм стоит прежний блок, "
            "и что платформа пишет при снятии у такого поля, не проверялось")
    place = find_element(doc, element)
    attributes = doc.get("attributes") if isinstance(doc, dict) else None
    head_attr = attributes.get(ATTR_HEAD) if isinstance(attributes, dict) else None
    main = head_attr.get(MAIN_ATTRIBUTE_ID) if isinstance(head_attr, dict) else None
    rows = [row for row in _bindings(doc) if row.get(BIND_ELEMENT) == place.index]
    steps = ((rows[0].get(BIND_PATH) or {}).get(PATH_STEPS) or []) if rows else []
    first = steps[0].get(STEP_VALUE) if steps and isinstance(steps[0], dict) else None
    pattern = _find_one(found_all, "Content.TextBox", TEXTBOX_PATTERN)
    types = pattern.holder.get(pattern.key).get(PATTERN_TYPES) if pattern is not None \
        and isinstance(pattern.holder.get(pattern.key), dict) else None
    if not steps:
        kind, what = "без привязки", "поле без привязки данных"
    elif first == main:
        kind, what = "через основной", "поле показывает реквизит объекта через основной реквизит формы"
    elif len(steps) > 1:
        kind, what = "через реквизит формы", "путь привязки идёт через реквизит формы в несколько шагов"
    elif types:
        kind, what = "реквизит формы другого вида", "у поля с режимом задан тип значения"
    else:
        kind, what = LIST_CHOICE_CHECKED, None
    notes = []
    if what is not None:
        if not unverified:
            raise EditError(
                f"{LIST_CHOICE_MODE} у {whose}: {what}. Снятие режима проверялось у поля, привязанного к своему реквизиту формы "
                "путём из одного шага, с пустым типом («Произвольный»); у этого поля вид другой, и что платформа напишет "
                "при снятии, не проверялось. Чтобы всё же выполнить операцию, передайте unverified=True: операция запишет то же, "
                "а результат придётся проверить самостоятельно")
        notes.append(f"{what}: запись снятия перенесена с поля, привязанного к своему реквизиту формы; для этого вида она "
                     "не проверялась")
    why = "платформа снимает КнопкуСпискаВыбора вместе с режимом"
    writes = []
    button = _find_one(found_all, TEXTBOX_PROPS_NODE, "choice_list_button")
    if button is not None and button.holder.get(button.key) is not False:
        writes.append((button.holder, button.key, False, why, "/".join(button.trail)))
    count = _maybe(EDIT_BLOCK[0], 0)
    if block.holder.get(count) != 0:
        writes.append((block.holder, count, 0, "блок редактирования платформа убирает целиком: счётчик блока 1 → 0",
                       "/".join(block.trail[:-1] + (count,))))
    writes.append((block.holder, block.key, None, "блок редактирования поля убран (было "
                   f"`{LIST_CHOICE_EDIT_GUID[:8]}…` с вариантом 0)", "/".join(block.trail)))
    notes.append((f"тип значения пуст и остаётся произвольным, Длина остаётся 255, как у платформы; " if not types else
                  "тип значения не тронут; ") + "тип полю возвращает операция `set_field_type` (строка — длина и блок "
                  "редактирования записываются, как у платформы при выборе типа в палитре)")
    notes.append("в палитре платформы вместе с режимом пропадают АвтоВыборНезаполненного и РежимВыбораНезаполненного — "
                 "их значения в файле остаются")
    # Пометка проверки — только у проверенного строения; у перенесённого под `unverified` её нет.
    return writes, notes, (kind if what is None else None)


def _list_choice_data(doc, element, anchor, found_all, whose, unverified):
    """РежимВыбораИзСписка ☑ у поля ввода формы: что делается с типом поля, зависит от вида данных поля.

    Возвращает `(записи, оговорки, вид данных)` для отчёта либо отказывает. Вид данных — это строение, по которому ставится
    пометка «проверено» (`_round_structure`, `LIST_CHOICE_CHECKED`). У реквизита формы с путём из одного шага платформа снимает
    тип у поля и у реквизита и ставит длину 255. Если путь идёт через основной реквизит, тип не меняется
    (`CORPUS_LIST_CHOICE_DATA`). Проверен один вид: строка у поля и у реквизита. В остальных случаях операция отказывает:

    * Если реквизит формы использует и другая привязка, отказ нельзя снять через `unverified`: снятие типа у общего реквизита
      изменило бы и эту привязку, а это не проверялось.
    * Если тип поля или реквизита не является одной строкой либо у поля нет привязки, отказ снимается ключом `unverified`: правило
      переносится на другой вид данных, и отчёт сообщает, что это не проверялось.

    У вложенного поля колонки платформа выводит тип из типа колонки, поэтому там ничего не меняется.
    """
    if anchor != "TextBox":
        return [], [], None
    place = find_element(doc, element)
    attributes = doc.get("attributes") if isinstance(doc, dict) else None
    head = attributes.get(ATTR_HEAD) if isinstance(attributes, dict) else None
    main = head.get(MAIN_ATTRIBUTE_ID) if isinstance(head, dict) else None
    rows = [row for row in _bindings(doc) if row.get(BIND_ELEMENT) == place.index]
    steps = ((rows[0].get(BIND_PATH) or {}).get(PATH_STEPS) or []) if rows else None
    first = steps[0].get(STEP_VALUE) if steps and isinstance(steps[0], dict) else None
    kept, empty = CORPUS_LIST_CHOICE_DATA["через основной"]
    if steps and first == main:
        return [], [f"тип поля не изменён: поле показывает реквизит через основной реквизит формы "
                    f"(путь из {len(steps)} {'шага' if len(steps) == 1 else 'шагов'}); у "
                    "таких полей платформа тип не "
                    f"меняет, и в образцах форм тип есть у {kept} полей из {kept + empty} с этим "
                    "режимом"], "через основной"
    if steps and len(steps) > 1:
        return [], [f"тип поля не изменён: путь привязки идёт через реквизит формы в "
                    f"{schema.plural(len(steps), 'шаг', 'шага', 'шагов')}, как путь через "
                    "основной реквизит; такого "
                    "поля с этим режимом в образцах форм нет, и что сделала бы "
                    "платформа, не проверялось"], "через реквизит формы"
    pattern = _find_one(found_all, "Content.TextBox", TEXTBOX_PATTERN)
    length = _find_one(found_all, TEXTBOX_PROPS_NODE, TEXTBOX_LENGTH)
    if pattern is None or length is None:
        raise EditError(f"{LIST_CHOICE_MODE} у {whose}: у поля нет описателя типа или Длины "
                        "(`digits`): платформа переписывает их при этом режиме, а у полей "
                        "ввода формы они всегда есть")
    attr = None
    if steps:
        shared = [row.get(BIND_ELEMENT) for row in _bindings(doc)
                  if row.get(BIND_ELEMENT) != place.index
                  and isinstance(((row.get(BIND_PATH) or {}).get(PATH_STEPS) or [None])[0], dict)
                  and row[BIND_PATH][PATH_STEPS][0].get(STEP_VALUE) == first]
        items = ((attributes.get(ATTR_LIST) or {}).get("items") or []) \
            if isinstance(attributes, dict) else []
        found = [item for item in items if item.get(ATTR_ID) == [first]]
        if len(found) != 1:
            raise EditError(f"{LIST_CHOICE_MODE} у {whose}: привязка ведёт к реквизиту формы с "
                            f"номером {first}, а таких реквизитов у формы {len(found)}")
        attr = found[0]
        if shared:
            raise EditError(
                f"{LIST_CHOICE_MODE} у {whose}: поле показывает реквизит формы "
                f"{attr.get(ATTR_NAME)!r}, а его держат ещё "
                f"{schema.plural(len(shared), 'привязка', 'привязки', 'привязок')} (элементы с "
                f"индексами {', '.join(str(i) for i in shared)}). Вместе с этим режимом платформа "
                "снимает тип у поля и у его реквизита формы, а снятие типа у общего реквизита изменило бы и их; это не "
                f"проверялось. Ставьте режим в конфигураторе")
    field_type = pattern.holder.get(pattern.key)
    attr_type = attr.get(ATTR_PATTERN) if attr is not None else None
    measured = attr is not None and _one_string(field_type) and _one_string(attr_type)
    notes = []
    if not measured:
        what = ("поле без привязки данных (у такого поля с этим режимом и у реквизита тип пуст)"
                if attr is None else
                f"тип поля {_type_words(field_type)}, реквизита формы {_type_words(attr_type)}")
        if not unverified:
            raise EditError(
                f"{LIST_CHOICE_MODE} у {whose}: {what}. Этот режим проверялся только у поля строкового "
                "типа, привязанного к реквизиту формы тоже строкового типа: платформа сняла тип у поля и у реквизита и поставила "
                f"Длину {LIST_CHOICE_LENGTH}. У этого поля вид другой, и что платформа сделает с "
                "ним (и с квалификаторами числа и даты среди свойств), не проверялось. Чтобы всё же "
                "выполнить операцию, передайте unverified=True: операция перенесёт это правило, "
                "а результат придётся проверить самостоятельно")
        notes.append(f"{what}: правило (тип снят, Длина {LIST_CHOICE_LENGTH}) перенесено "
                     f"со строки, привязанной к своему реквизиту формы; "
                     "для этого вида оно не проверялось, а квалификаторы среди "
                     "свойств, кроме Длины, операция не изменяет")
    why = ("вместе с РежимомВыбораИзСписка у поля, привязанного к своему реквизиту формы, "
           "платформа снимает тип: у такого поля с этим режимом тип пуст")
    writes = []
    field_pattern = copy.deepcopy(pattern.holder.get(pattern.key))
    field_pattern[PATTERN_TYPES] = []
    writes.append((pattern.holder, pattern.key, field_pattern, why, "/".join(pattern.trail)))
    if attr is not None:
        attr_pattern = copy.deepcopy(attr.get(ATTR_PATTERN))
        attr_pattern[PATTERN_TYPES] = []
        writes.append((attr, ATTR_PATTERN, attr_pattern,
                       f"тип реквизита формы {attr.get(ATTR_NAME)!r} снят вместе с типом поля: "
                       "описатель реквизита стал пустым, как у поля",
                       f"реквизит {attr.get(ATTR_NAME)!r}/{ATTR_PATTERN}"))
    writes.append((length.holder, length.key, LIST_CHOICE_LENGTH,
                   f"Длину платформа ставит {LIST_CHOICE_LENGTH} (было 0, стало "
                   f"{LIST_CHOICE_LENGTH})", "/".join(length.trail)))
    kind = LIST_CHOICE_CHECKED if measured else \
        "без привязки" if attr is None else "реквизит формы другого вида"
    return writes, notes, kind


def _one_string(pattern):
    """Описатель состоит ровно из одной строки (`{"S"}` с длиной или без неё)."""
    types = pattern.get(PATTERN_TYPES) if isinstance(pattern, dict) else None
    return isinstance(types, list) and len(types) == 1 and isinstance(types[0], dict) \
        and types[0].get(PATTERN_KIND) == "S"


# ── Поле текстового документа: «Расширение» ──
# Узел блока содержимого и имена его полей. Значение «Встроенный язык» платформа пишет вместе со счётной записью на позиции 4
# (`u4`): у остальных значений там `[0]`.
TEXT_DOCUMENT_NODE = "Content.TextDocumentField"
EXTENSION = "extension"
EXTENSION_RECORD = "u4"
EXTENSION_BUILTIN = TEXT_DOCUMENT_EXTENSIONS["BuiltInLanguage"]
EXTENSION_WORDS = {**TEXT_DOCUMENT_EXTENSIONS,
                   **{label.lower(): TEXT_DOCUMENT_EXTENSIONS[word]
                      for word, label in TEXT_DOCUMENT_EXTENSION_LABELS.items()}}


def _extension_value(value, name, whose):
    """Значение «Расширения» в виде блока GUID: слово (`HTML`, `TextLayout`, … или подпись палитры по-русски) становится
    `{"guid": …}`; блок GUID идёт как есть и дальше проверяется границей. Слово, которого нет среди пяти, — отказ со списком."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        guid = EXTENSION_WORDS.get(value) or EXTENSION_WORDS.get(value.lower())
        if guid is not None:
            return {"guid": guid}
    shown = ", ".join(f"{word} ({TEXT_DOCUMENT_EXTENSION_LABELS[word]})" for word in TEXT_DOCUMENT_EXTENSIONS)
    raise EditError(f"{name} у {whose}: значение {value!r} не из значений палитры. Расширение поля текстового документа "
                    f"задают словом — {shown} — или блоком {{\"guid\": …}}; GUID, которого платформа не писала, "
                    "операция не принимает (его снимает только unverified=True)")


def _extension_record(guid):
    """Запись на позиции 4, которую платформа пишет рядом с этим расширением."""
    if guid == EXTENSION_BUILTIN:
        return [1, {"guid": TEXT_DOCUMENT_BUILTIN_RECORD_GUID}]
    return [0]


def _extension_word(guid):
    for word, known in TEXT_DOCUMENT_EXTENSIONS.items():
        if known == guid:
            return f"{word} ({TEXT_DOCUMENT_EXTENSION_LABELS[word]})"
    return f"GUID {guid}"


# ── «Точность» и «Неотрицательный» индикатора и полосы регулирования ──
# В узле элемента этих свойств нет: платформа пишет их квалификаторами числового типа реквизита формы, к которому привязан
# элемент (`{"Pattern",{"N",<длина>,<точность>,<неотрицательный>}}`), а элемент не меняется. Длина (`digits`) не трогается.
NUMBER_QUALIFIER_ANCHORS = ("ProgressBar", "TrackBar")
NUMBER_QUALIFIERS = {"precision": (PATTERN_NUMBER[1], "Точность"),
                     "fraction_digits": (PATTERN_NUMBER[1], "Точность"),
                     "nonnegative": (PATTERN_NUMBER[2], "Неотрицательный"),
                     "nonnegative": (PATTERN_NUMBER[2], "Неотрицательный")}
# Значения, которые платформа показала парой «по умолчанию → правка»: точность 0 → 2, «Неотрицательный» ☑ → ☐.
NUMBER_QUALIFIER_MEASURED = {PATTERN_NUMBER[1]: (0, 2), PATTERN_NUMBER[2]: (True, False)}
NUMBER_QUALIFIER_PROOF = ("платформа показала точность 0 и 2 и «Неотрицательный» ☑ и ☐ (пара «по умолчанию → одно "
                          "свойство» у индикатора и у полосы регулирования)")


def _bound_number_attribute(doc, element, name, whose):
    """Реквизит формы числового типа, к которому привязан элемент: `(реквизит, элементы, делящие реквизит)` либо отказ со
    словами — что именно не так с привязкой и почему квалификатор тогда не поставить."""
    place = find_element(doc, element)
    attributes = doc.get("attributes") if isinstance(doc, dict) else None
    head = attributes.get(ATTR_HEAD) if isinstance(attributes, dict) else None
    main = head.get(MAIN_ATTRIBUTE_ID) if isinstance(head, dict) else None
    rows = [row for row in _bindings(doc) if row.get(BIND_ELEMENT) == place.index]
    steps = ((rows[0].get(BIND_PATH) or {}).get(PATH_STEPS) or []) if rows else []
    first = steps[0].get(STEP_VALUE) if steps and isinstance(steps[0], dict) else None
    why = (f"{name} у {whose} — квалификатор числового типа реквизита формы, к которому привязан элемент, "
           "а не свойство элемента: ")
    if not rows or not steps:
        raise EditError(why + "у элемента нет привязки данных, и менять нечего. Привяжите элемент к реквизиту формы "
                              "числового типа (операция bind) и повторите")
    if len(steps) != 1 or first is None or first == main:
        raise EditError(why + "элемент привязан не к реквизиту формы, а "
                              + ("к основному реквизиту формы или к его реквизитам" if first == main
                                 else "к реквизиту объекта метаданных или через несколько шагов пути")
                              + ". Тип такого значения лежит в конфигурации, а не в форме, и операция его не правит")
    items = ((attributes.get(ATTR_LIST) or {}).get("items") or []) if isinstance(attributes, dict) else []
    found = [item for item in items if item.get(ATTR_ID) == [first]]
    if len(found) != 1:
        raise EditError(why + f"привязка ведёт к реквизиту формы с номером {first}, а таких реквизитов у формы {len(found)}")
    attr = found[0]
    types = (attr.get(ATTR_PATTERN) or {}).get(PATTERN_TYPES)
    if not (isinstance(types, list) and len(types) == 1 and isinstance(types[0], dict)
            and types[0].get(PATTERN_KIND) == "N"):
        raise EditError(why + f"реквизит формы {attr.get(ATTR_NAME)!r} имеет тип {_type_words(attr.get(ATTR_PATTERN))}, "
                              "а не одно число: у других типов таких квалификаторов нет (точность и знак бывают только у "
                              "числа), а составной тип операция не правит")
    shared = [row.get(BIND_ELEMENT) for row in _bindings(doc)
              if row.get(BIND_ELEMENT) != place.index
              and isinstance(((row.get(BIND_PATH) or {}).get(PATH_STEPS) or [None])[0], dict)
              and row[BIND_PATH][PATH_STEPS][0].get(STEP_VALUE) == first]
    return attr, types[0], shared


def _number_qualifier(doc, element, anchor, name, value):
    """`set_property precision|nonnegative` у индикатора и полосы регулирования: правит квалификатор числового типа
    реквизита формы, к которому привязан элемент. Элемент не меняется. Отчёт называет реквизит."""
    key, label = NUMBER_QUALIFIERS[name]
    whose = f"{anchor} {element!r}"
    if key == PATTERN_NUMBER[1]:
        if isinstance(value, bool) or not isinstance(value, int):
            raise EditError(f"{name} у {whose}: точность — целое число, а пришло {value!r}")
    elif not isinstance(value, bool):
        raise EditError(f"{name} у {whose}: «Неотрицательный» — галочка, true или false, а пришло {value!r}")
    attr, block, shared = _bound_number_attribute(doc, element, name, whose)
    notes = []
    if key == PATTERN_NUMBER[1]:
        digits = block.get(PATTERN_NUMBER[0])
        if value < 0 or (isinstance(digits, int) and value > digits):
            raise EditError(f"{name} у {whose}: точность {value} не укладывается в длину {digits} числа реквизита формы "
                            f"{attr.get(ATTR_NAME)!r} — она от 0 до длины. Длину операция не меняет")
    if value not in NUMBER_QUALIFIER_MEASURED[key]:
        notes.append(f"не проверялось: значение {_short(value)} платформе не показывали ({NUMBER_QUALIFIER_PROOF}); "
                     "квалификатор записан по правилу числового типа")
    old = block.get(key)
    block[key] = value
    if shared:
        notes.append("реквизит формы делят ещё элементы с индексами " + ", ".join(str(i) for i in shared)
                     + ": квалификатор принадлежит реквизиту, и у них он изменится тоже")
    said = (f"{whose}: {name} {_short(old)} → {_short(value)} ({label}) — квалификатор числового типа реквизита формы "
            f"{attr.get(ATTR_NAME)!r}, к которому привязан элемент; в узле элемента этого свойства нет, элемент не меняется")
    if old == value:
        said += " (то же значение, что стояло)"
    return "; ".join([said] + notes) + (f"; {NUMBER_QUALIFIER_PROOF}" if not notes else "")


# Рамка элемента, заданная стилем: в шаблоне блок рамки стоит «как у стиля» (голова — цвет стиля −18, `explicit` ложь, элемента
# стиля нет), а платформа, поставив любой вид рамки, переписывает блок целиком: голова — «Авто», `explicit` истина, `style_item`
# — элемент стиля «Рамка элемента». У типов, чей шаблон уже несёт элемент стиля, она переписывает только `explicit` (и у
# разделителя код головы −18 → 0). Записи платформы — копии `<Тип>__Border__<Вид>` пула у девяти типов шаблонов и у прежних видов.
BORDER_STYLE_ITEM = "48312c09-257f-4b29-b280-284dd89efc1e"
BORDER_NULL_ITEM = "00000000-0000-0000-0000-000000000000"
BORDER_DEFAULT_U5 = 3
# «Без рамки» у типов с элементом стиля платформа оставляет записью шаблона (`explicit` ложь), у типов со стилем рамки пишет явной;
# «Скруглённая» (`Rounded`) в палитре этих типов не выставляется — копия остаётся записью шаблона.
BORDER_KEEPS_STYLE_RECORD = ("WithoutBorder", "Rounded")


def _border_explicit_writes(target, value):
    """Что платформа пишет в блок рамки элемента вместе с видом рамки, если рамка шаблона — стиль (`explicit` ложь):
    `[(словарь, ключ, значение, причина, путь)]`. Блок уже явный (`explicit` истина) — ничего."""
    holder = target.holder
    if not isinstance(holder, dict) or not isinstance(value, str):
        return []
    trail = "/".join(target.trail[:-1])
    if holder.get("explicit") is True:
        out = []
        # У поля текстового документа шаблон уже явный («Одинарная», нулевой элемент стиля): на любой другой вид платформа
        # ставит элемент стиля «Рамка элемента», на «Одинарная» оставляет нулевой.
        item = holder.get("style_item")
        if isinstance(item, dict) and item.get("guid") == BORDER_NULL_ITEM and value not in ("Single", "Rounded"):
            out.append((holder, "style_item", {"guid": BORDER_STYLE_ITEM},
                        "платформа ставит любому виду рамки, кроме «Одинарная», элемент стиля «Рамка элемента» (нулевой элемент "
                        "остаётся у «Одинарная»)", trail + "/style_item"))
        # У поля географической схемы рамка по умолчанию — «Нет рамки» с позицией 5, равной 3; «Одинарная» и «Двойная» платформа пишет с нулём.
        if holder.get("u5") == BORDER_DEFAULT_U5 and holder.get("border_type") == "WithoutBorder" and value not in ("WithoutBorder", "Rounded"):
            out.append((holder, "u5", 0, "платформа, сменив умолчание «Нет рамки» (позиция 5 равна 3) на вид рамки, пишет позицию 5 нулём "
                        "(проверено на «Одинарная» и «Двойная»)", trail + "/u5"))
        return out
    if holder.get("explicit") is not False:
        return []
    head = holder.get("color_kind"), (holder.get("value") or {}).get("code")
    styled = "style_item" not in holder
    if value in BORDER_KEEPS_STYLE_RECORD and not (styled and value == "WithoutBorder"):
        return []
    why = ("платформа, поставив вид рамки, пишет блок целиком, как у копий пула: признак «рамка задана явно» истина"
           + (", голова — «Авто» (цвет 0, код 0), элемент стиля «Рамка элемента»" if styled else ""))
    out = []
    if styled:
        out.append((holder, "color_kind", 0, why, trail + "/color_kind"))
        out.append((holder["value"], "code", 0, why, trail + "/value/code"))
        out.append((holder, "style_item", {"guid": BORDER_STYLE_ITEM}, why, trail + "/style_item"))
    elif head[1] == -18:
        out.append((holder["value"], "code", 0, why, trail + "/value/code"))
    out.append((holder, "explicit", True, why, trail + "/explicit"))
    return out


def _cowrites(found_all, target, value, anchor):
    """Определяет, что записать вместе с полем: `[(словарь, ключ, значение, причина, путь)]` и оговорки.

    Правила включают только то, что платформа показала и что встречается в образцах форм. Если правило чего-то не знает, оно
    этого не трогает и сообщает об этом словами (`notes`). Значение `None` в записи означает, что ключа быть не должно: у типа
    «дата и время» буквы в описателе нет.
    """
    out, notes = [], []
    here = CORPUS_COWRITES
    key, node = getattr(target.slot, "name", None) or target.key, target.node
    measured = anchor if anchor in ("TextBox", "ColumnControl.TextBox") else "TextBox"

    def put(found, new, why):
        out.append((found.holder, found.key, new, why, "/".join(found.trail)))

    if (node, key) == ("Border", "border_type") and anchor != FORM_ANCHOR:
        out += _border_explicit_writes(target, value)
    if (node, key) == (TEXT_DOCUMENT_NODE, EXTENSION) and isinstance(value, dict):
        record = _extension_record(value.get("guid"))
        if target.holder.get(EXTENSION_RECORD) != record:
            out.append((target.holder, EXTENSION_RECORD, record,
                        "платформа пишет рядом с расширением счётную запись: у «Встроенного языка» это одна запись с GUID, "
                        "у остальных значений — `[0]`",
                        "/".join(target.trail[:-1] + (EXTENSION_RECORD,))))
    if (node, key) in MASK_NODES:
        for other_node, other_key in MASK_NODES:
            twin = _find_one(found_all, other_node, other_key)
            if twin is not None and twin is not target:
                put(twin, value, "маска лежит и в блоке значения: платформа пишет оба места, "
                                 "и значения в них совпадают")
        wrap = _find_one(found_all, TEXTBOX_PROPS_NODE, WRAP)
        if value and wrap is not None and wrap.holder.get(WRAP) is True:
            put(wrap, False, "с маской платформа снимает АвтоПереносСтрок (было 1, стало 0)")
    if node in TEXTBOX_COMMON_NODES and key == "border_color" and isinstance(value, dict):
        # `u43` зависит от вида поля и от ЦветаРамки: платформа меняет его значение с 2 на 1, и операция записывает его по тому же
        # правилу (`design.u43_rule`) для блока в том виде, каким он станет. Сам цвет позже запишет общий цикл `set_property`.
        holder = next((found.holder for found in found_all if found.node == TEXTBOX_PROPS_NODE),
                      None)
        after = dict(target.holder)
        after[target.key] = value
        want = _design.u43_rule(after)
        if isinstance(holder, dict) and _design.TEXTBOX_U43 in holder and want is not None:
            if holder[_design.TEXTBOX_U43] != want:
                trail = next(found.trail for found in found_all if found.holder is holder)
                own = measured == "TextBox"
                # Версия блока определяется самим блоком (у версии 15 свой узел, `TextBoxCommon.v15`), и числа правила берутся для той же версии.
                version = 15 if node == schema.TEXTBOX_COMMON_15 else 16
                out.append((holder, _design.TEXTBOX_U43, want,
                            f"{_design.U43_WORDS}",
                            "/".join(trail[:-1] + (_design.TEXTBOX_U43,))))
    if (node, key) == (TEXTBOX_VALUE_NODE, MULTI_LINE):
        code = _find_one(found_all, TEXTBOX_PROPS_NODE, "multi_line_code")
        if code is not None and isinstance(value, bool):
            put(code, 2 if value else 0,
                "производное (2 при истине, 0 при лжи); тройка «multi_line, зеркало, код» "
                "согласована. Палитра платформы пишет только "
                "первичное значение, а операция пишет и производные, как платформа")
    if node == TEXTBOX_PROPS_NODE and key in TEXTBOX_NUMBER + (DATE_FRACTIONS,):
        block, letter, where = _pattern_single(found_all)
        if block is None:
            notes.append(f"описатель типа поля составной или пустой (буквы {letter}) — "
                         f"квалификатор {key} поставлен только среди свойств")
        elif key == DATE_FRACTIONS:
            if letter == "D" and value in DATE_LETTERS:
                out.append((block, PATTERN_DATE, DATE_LETTERS[value],
                            "состав даты лежит и в описателе буквой (Дата — D, Время — T, "
                            "ДатаВремя — буквы нет): платформа пишет оба места и держит их согласованными",
                            f"{where}/{PATTERN_DATE}"))
            elif letter != "D":
                notes.append(f"тип поля не Дата (буква {letter}) — в описателе состава даты нет, "
                             "поставлен только код среди свойств")
        elif letter == "N":
            qualifier = PATTERN_NUMBER[TEXTBOX_NUMBER.index(key)]
            out.append((block, qualifier, value,
                        "квалификатор числа лежит и в описателе: "
                        "платформа пишет оба места, и значения в них совпадают",
                        f"{where}/{qualifier}"))
        elif letter == "S" and key == TEXTBOX_LENGTH:
            if PATTERN_LENGTH in block:
                out.append((block, PATTERN_LENGTH, value,
                            "у строки «Длина» — это длина строки в описателе; платформа держит "
                            "оба значения равными", f"{where}/{PATTERN_LENGTH}"))
            else:
                notes.append("у строки без длины в описателе позиции длины нет вовсе, поэтому она "
                             "поставлена только среди свойств (сколько позиций заводит платформа "
                             "у ограниченной строки, не проверялось)")
        else:
            notes.append(f"квалификатор {key} — число, а тип поля {letter}: в описателе ему "
                         "места нет, поставлен только среди свойств")
    if (node, key) == ("Content.TableBox.u2.u1", TREE_VIEW) and isinstance(value, str):
        flags = next((found for found in found_all if found.key == TREE_FLAGS
                      and found.node == f"{schema.TABLE_BOX_SOURCE_BLOCK}.v12"), None)
        word = flags.holder.get(TREE_FLAGS) if flags is not None else None
        if isinstance(word, dict) and word.get("tree") is False:
            new = dict(word)
            new["tree"] = True
            put(flags, new, "конструктор включает Дерево сам, когда задают его отображение: "
                            "платформа поднимает бит tree")
    if (node, key) == ("Content.TextBox", LIST_CHOICE_MODE) and value is True \
            and target.holder.get(target.key) is not True:
        block = _find_one(found_all, *EDIT_BLOCK)
        if block is not None and block.holder.get(block.key) != LIST_CHOICE_EDIT:
            put(block, copy.deepcopy(LIST_CHOICE_EDIT),
                "блок редактирования поля платформа при РежимеВыбораИзСписка заменяет целиком: "
                f"`{LIST_CHOICE_EDIT_GUID[:8]}…` с вариантом 0; без этого режима такого блока нет")
        nested = measured == "ColumnControl.TextBox"
        for name, new, shown in LIST_CHOICE_BUTTONS:
            if nested and name in LIST_CHOICE_NESTED_KEEPS:
                continue
            button = _find_one(found_all, TEXTBOX_PROPS_NODE, name)
            if button is None or button.holder.get(name) is new:
                continue
            put(button, new, f"платформа ставит вместе с РежимомВыбораИзСписка: {shown}")
        if nested:
            kept = [f"{'КнопкаВыбора' if name == 'choice_button' else 'КнопкаОчистки'} ☐"
                    for name in LIST_CHOICE_NESTED_KEEPS]
            notes.append("у вложенного поля платформа при режиме кнопки выбора и очистки не показала "
                         "(до правки обе были сняты); в образцах форм: "
                         f"{', '.join(kept)} — операция их не трогает")
            notes.append("тип вложенного поля не изменён: платформа выводит его из типа колонки, "
                         "и при этом режиме он не менялся")
        else:
            notes.append("платформа при этом режиме попутно перевязывает правую привязку поля и "
                         "соседей; операция привязки не изменяет")
    derived = DERIVED_BY.get((node, key))
    if derived is not None and _find_one(found_all, *derived) is not None:
        notes.append(f"{derived[1]} не тронут: {DERIVED[derived]}")
    side = SIDE_POSITIONS.get((node, key)) or SIDE_POSITIONS_ADDED.get((node, key))
    if side is not None:
        notes.append(f"при этой правке платформа изменила ещё безымянную позицию "
                     f"{side}; операция её не изменяет: "
                     + (SIDE_WORDS.get((node, key)) or SIDE_WORDS_ADDED.get((node, key))
                        or "что платформа туда пишет, не проверялось"))
    return out, notes


# Связанные строки палитры: преднастройки

# Строка палитры может быть доступна только при определённом значении соседней. Например, «ПоложениеКартинки» у панели
# недоступна, пока «РазмерКартинки» равен «Растянуть». Операция такую связь не исправляет, потому что менять соседнее значение
# за человека означало бы угадывать его намерение. Она сообщает, что значение записано, но строка в палитре при текущем
# соседнем значении недоступна. Учитываются только связи, названные в справочнике (`preset`) или проверенные, и только те,
# которые можно проверить на самом узле.
LINKED = {
    _named(TEXTBOX_PROPS_NODE, "digits"): ("pattern", {"N", "S"},
                                            "ТипЗначения — Число или Строка (по справочнику, преднастройка)"),
    _named(TEXTBOX_PROPS_NODE, "fraction_digits"): ("pattern", {"N"},
                                                     "ТипЗначения = Число (по справочнику, преднастройка)"),
    _named(TEXTBOX_PROPS_NODE, "nonnegative"): ("pattern", {"N"},
                                                  "ТипЗначения = Число (по справочнику, преднастройка)"),
    _named(TEXTBOX_PROPS_NODE, "mark_negatives"): ("pattern", {"N"},
                                                    "ТипЗначения = Число (по справочнику, преднастройка)"),
    _named(TEXTBOX_PROPS_NODE, "fixed_fraction_digits"): ("pattern", {"N"},
                                                           "ТипЗначения = Число (по справочнику)"),
    _named(TEXTBOX_PROPS_NODE, "format"): ("pattern", {"N"},
                                            "ТипЗначения = Число (по справочнику, преднастройка)"),
    _named(TEXTBOX_PROPS_NODE, "date_fractions"): ("pattern", {"D"},
                                                    "ТипЗначения = Дата (по справочнику, преднастройка)"),
    _named(TEXTBOX_VALUE_NODE, "extended_edit"): (
        _named(TEXTBOX_VALUE_NODE, "multi_line"), {True},
        "МногострочныйРежим = Истина (по справочнику, преднастройка)"),
    _named(TEXTBOX_PROPS_NODE, "choice_button_picture"): (
        _named(TEXTBOX_PROPS_NODE, "choice_button"), {True},
        "КнопкаВыбора ☑ (без неё строка палитры недоступна)"),
    _named("Content.PictureBox.u1", "shortcut"): (
        _named("Content.PictureBox.u1", "hyperlink"), {True},
        "Гиперссылка ☑ (без неё строка палитры недоступна)"),
    _named("Content.TableBox.u2.u1", "row_selection_mode"): (
        _named("Content.TableBox.u2.u1", "selection_mode"), {"SingleLine"},
        "РежимВыделения = Одиночный (только при нём строка палитры доступна)"),
    _named("Content.Panel.u1", "picture_location"): (
        _named("PictureSet.Panel", "picture_size"), "не Stretch",
        "РазмерКартинки ≠ Растянуть (иначе строка палитры недоступна)"),
    _named("Content.Panel.u1.u0", "border"): (
        _named("Content.Panel.u1", "show_tabs"), {"DontUse"},
        "ОтображениеЗакладок = Не отображать (по справочнику, преднастройка)"),
    # У формы действует та же преднастройка, что у панели: «ПоложениеКартинки» недоступна при «РазмерКартинки», равном «Растянуть»
    # (у формы это число 1).
    _named("LayoutList", "picture_location"): (
        _named("PictureSet.Form", "picture_size"), ("≠", 1),
        "РазмерКартинки ≠ Растянуть (у формы, как у панели, иначе строка палитры недоступна)"),
}


def _linked_warning(found_all, target):
    """Предупреждение, если строка палитры при текущем соседнем значении недоступна; иначе пусто."""
    rule = LINKED.get((target.node, target.key))
    if rule is None:
        return ""
    where, allowed, words = rule
    if where == "pattern":
        letters = set(_type_letters(next((found.holder.get(found.key) for found in found_all
                                          if found.key == TEXTBOX_PATTERN), None)).split("+"))
        if letters & allowed:
            return ""
        return (f"; ВНИМАНИЕ: строка палитры живая только при {words}, а тип поля — "
                f"{'+'.join(sorted(letters))}; значение записано, но конструктор покажет строку "
                "недоступной, и действует ли оно, не проверялось")
    node, key = where
    other = _find_one(found_all, node, key)
    if other is None:
        return ""
    now = other.holder.get(key)
    if allowed == "не Stretch":
        fine = now != "Stretch"
    elif isinstance(allowed, tuple) and allowed[0] == "≠":
        fine = now != allowed[1]
    else:
        fine = now in allowed
    if fine:
        return ""
    return (f"; ВНИМАНИЕ: строка палитры живая только при {words}, а сейчас {key} = "
            f"{_short(now)}; значение записано, но конструктор покажет строку недоступной, и "
            "действует ли оно, не проверялось")


# Перевёрнутые флаги: что покажет палитра

# Карта описывает файл, поэтому значение флага в ней — файловое. У девяти полей единица в файле означает снятую галочку в
# палитре (заметки полей в `schema.py`: «ПЕРЕВЁРНУТ», «ОБРАТНОЕ», «1 = … ЗАПРЕЩЕНО / РАЗРЕШЕНО»). Отчёт называет галочку в
# палитре. Ключ — `(узел, поле, бит)`, значение — `(строка палитры, свидетельство)`. У всех девяти единица означает снятую
# галочку.
INVERTED_FLAGS = {
    ("LayoutList", "use_visible_area_only", None): (
        "Исп. только видимую область", "проверено в предприятии"),
    ("Content.Panel.u1", "use_visible_area_only", None): (
        "Исп. только видимую область", "так пишет платформа"),
    ("Content.TextBox.u2.u0", "text_edit", None): (
        "РедактированиеТекста", "так пишет платформа"),
    ("Content.ComboBox.u1", "text_edit", None): (
        "РедактированиеТекста", "так пишет платформа"),
    ("Content.TableBox.u2.u1", "flags", "read_only"): (
        "ТолькоПросмотр", "так пишет платформа"),
    ("Content.TableBox.u2.u1", "flags", "enable_drag"): (
        "РазрешитьПеретаскивание", "так пишет платформа"),
    ("Element.TableBoxColumn.u1.u1.u1", "flags", "change_visible"): (
        "ИзменятьВидимость", "так пишет платформа"),
    ("TableBoxColumnHead.NoControl", "flags", "change_visible"): (
        "ИзменятьВидимость", "так пишет платформа"),
    ("Content.ListBox.u1.u1", "flags", "read_only"): (
        "ТолькоПросмотр", "так пишет платформа"),
}


def _inverted_words(target, bit, new):
    """Слова о галочке в палитре для перевёрнутого флага; если поле не перевёрнуто, пусто. Бит указывается сам по себе
    (`flags/read_only`), потому что битовое слово целиком `set_property` не записывает.
    """
    spec = INVERTED_FLAGS.get((target.node, target.slot.name, bit))
    if spec is None or not isinstance(new, bool):
        return ""
    row, why = spec
    shown = "СНЯТА (☐)" if new else "СТОИТ (☑)"
    return (f"в палитре «{row}» галочка {shown} — флаг в файле перевёрнут "
            f"({'единица' if new else 'ноль'} файла = {'☐' if new else '☑'}; {why}); значение "
            "здесь файловое, как его описывает карта")


def _bindings(doc):
    attributes = doc.get("attributes")
    block = attributes.get(BINDINGS) if isinstance(attributes, dict) else None
    return (block.get("items") or []) if isinstance(block, dict) else []
