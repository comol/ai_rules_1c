"""Тип поля ввода, привязанного к своему реквизиту формы: `set_field_type(element, pattern)`.

Платформа меняет тип поля такого вида в палитре («Тип значения»): тип реквизита формы и тип поля становятся одним и тем же, а у
поля с пустым типом («Произвольный», так выглядит поле после снятия `РежимВыбораИзСписка`) вместе с типом записываются длина и
блок редактирования строки. Операция делает то же и называет, что записала.

**Проверено платформой.** Поле без типа («Произвольный», режим выбора из списка снят) → «Строка 10»: описатель поля и
реквизита — `{"S", 10, 1}`, `digits` поля — 10, блок редактирования `u3` — блок строки (`9a7643d2…`, вариант 4, счётчик 0 → 1);
остальное у поля не изменилось. Поле без типа → «Число 12,2»: описатель `{"N", 12, 2, 0}`, `digits` 12, `fraction_digits` 2, `wrap` ☐,
`u22` 1, блок редактирования записан целиком. Строка → «Дата»: `{"D", "D"}`, кнопка выбора ☑, `u22` 2, `wrap` ☐. Строка → «Число
15,2»: `{"N", 15, 2, 0}`, `digits` 15, `u22` 1, `wrap` ☐. Запись операции совпадает с этими записями узел в узел.

**Смена вида типа между строкой, числом и датой.** Платформа ставит «КнопкаВыбора» по виду типа, а прежнее значение (в том числе
поставленное вручную) не сохраняет: дата — ☑, число и строка — ☐. `u22`: строка 0, число 1, дата 2; `digits`: у строки длина, у числа
разрядность, у даты 0; `wrap` при переходе к строке из числа или даты не меняется (операция его тоже не трогает). Пары, снятые на
платформе: дата → число, число с включённой кнопкой выбора → строка 20, число → дата.

**Без `unverified` операция пишет то, что подтверждено:** строку в поле без типа; число и дату (состав `D`) в поле без типа; смену вида
типа между `S`, `N`, `D` у поля с типом (кнопка выбора — по виду типа, при любом прежнем значении); новый тип того же класса:
описатель поля повторяет описатель реквизита, а `digits` и состав даты — зеркало типа (`edit.datatype.block_mirror`). Остальное —
поле с включённой кнопкой очистки (платформа её при смене вида типа не трогала в опыте) и дата с составом не `D` — только с
`unverified=true`; отчёт это называет.

**Отказ:** не поле ввода; нет привязки или она не из одного шага к реквизиту формы (путь по метаданным — тип пишет `bind`); основной
реквизит формы; реквизит держит ещё один элемент (его тип изменился бы вместе с ним); у поля включён `РежимВыбораИзСписка`
(сначала снять его: `set_property`); у поля составной тип, ссылка или булево (у булева реквизита флажок, а не поле ввода); тип
в `pattern` — не одиночная буква `S`, `N`, `D` (булево — флажок, ссылка и составной тип — `bind` по метаданным). Форма при отказе
не тронута.
"""

import copy
import re

from . import datatype
from . import datapath
from .base import EditError, find_element
from .data import _complete_string_blocks, _pattern_doc
from .elements import LIST_CHOICE_MODE
from .names import (
    ATTR_ID,
    ATTR_NAME,
    ATTR_PATTERN,
    BIND_ELEMENT,
    BIND_PATH,
    CONTENT,
    PATH_STEPS,
    PATTERN_KIND,
    PATTERN_MARK,
    PATTERN_TYPES,
    STEP_VALUE,
)

# Буквы, которые умеет записать поле ввода: булево — флажок, ссылка и составной тип приходят из метаданных (`bind data=`).
LETTERS = ("S", "N", "D")
LETTER_WORDS = {"S": "строка", "N": "число", "D": "дата"}
CLASS_OF_LETTER = datatype.FORM_LETTER_CLASS


def _letter_words(types):
    if not isinstance(types, list) or not types:
        return "пустой («Произвольный»)"
    return "+".join(str(b.get(PATTERN_KIND)) if isinstance(b, dict) else "?" for b in types)


def _own_attribute(doc, place, element):
    """Реквизит формы, к которому поле привязано одним шагом, и число других привязок к нему: `(строка реквизита, главный ли)` либо отказ."""
    attributes, rows = datapath._attributes(doc)
    bindings = [row for row in datapath.binding_rows(attributes) if isinstance(row, dict)]
    mine = [row for row in bindings if row.get(BIND_ELEMENT) == place.index]
    if not mine:
        raise EditError(
            f"у поля {element!r} нет привязки данных: тип поля следует за реквизитом формы, а привязать поле к нему можно "
            "операцией `bind` (с `copy_type` — вместе с типом реквизита)")
    steps = (mine[0].get(BIND_PATH) or {}).get(PATH_STEPS)
    if not isinstance(steps, list) or len(steps) != 1 or not isinstance(steps[0], dict):
        count = len(steps) if isinstance(steps, list) else "?"
        raise EditError(
            f"поле {element!r} показывает данные путём из {count} шагов (реквизит объекта, стандартный реквизит или путь через "
            "реквизит формы), а не свой реквизит формы: его тип задаёт объект конфигурации, а не форма. Тип такого поля "
            "пишет `bind` с путём по метаданным (`data`, `replace` у колонки)")
    first = steps[0].get(STEP_VALUE)
    head = attributes.get(datapath.ATTR_HEAD)
    main = head.get(datapath.MAIN_ATTRIBUTE_ID) if isinstance(head, dict) else None
    found = [row for row in rows if datapath._id_of(row) == first]
    if len(found) != 1:
        raise EditError(f"привязка поля {element!r} ведёт к реквизиту формы с номером {first}, а таких реквизитов у формы {len(found)}")
    row = found[0]
    if ATTR_PATTERN not in row:
        raise EditError(f"у реквизита формы {row.get(ATTR_NAME)!r} описателя типа нет вовсе (короткая строка из пяти позиций): "
                        "кодек такую строку с типом не собирает")
    if first == main:
        raise EditError(
            f"поле {element!r} привязано к основному реквизиту формы {row.get(ATTR_NAME)!r}: его тип — объект формы, а не тип "
            "значения; тип основного реквизита операция не меняет")
    shared = [r.get(BIND_ELEMENT) for r in bindings if r is not mine[0]
              and isinstance(((r.get(BIND_PATH) or {}).get(PATH_STEPS) or [None])[0], dict)
              and r[BIND_PATH][PATH_STEPS][0].get(STEP_VALUE) == first]
    if shared:
        raise EditError(
            f"реквизит формы {row.get(ATTR_NAME)!r} держат ещё элементы с индексами {', '.join(map(str, shared))}: тип реквизита "
            f"изменился бы и у них (у флажка, переключателя или колонки он значит другое), а что платформа делает с остальными "
            "элементами реквизита, не проверялось. Меняйте тип в конфигураторе")
    return row


def _one_block(pattern, element):
    """Описатель, который просит вызов: ровно один блок `S`, `N` или `D`, в нынешней форме; строка с длиной дополняется вторым числом."""
    if not isinstance(pattern, dict):
        raise EditError('pattern — описатель типа, как у add_attribute: {"types": [{"kind": "S", "length": 10}]}')
    pattern = copy.deepcopy(_pattern_doc(pattern))
    types = pattern.get(PATTERN_TYPES)
    if not isinstance(types, list) or len(types) != 1 or not isinstance(types[0], dict):
        raise EditError(
            f"pattern поля {element!r} называет {_letter_words(types)}: поле ввода получает один тип — {', '.join(LETTERS)}. "
            "Составной тип и ссылку на объект пишет `bind` с путём по метаданным, а «Произвольный» поле получает вместе с "
            "РежимомВыбораИзСписка (`set_property`)")
    letter = types[0].get(PATTERN_KIND)
    if letter == "B":
        raise EditError(
            f"булев тип у поля {element!r} — флажок, а не поле ввода: у поля ввода на булев реквизит платформа рисует "
            "флажок. Смените вид элемента операцией `change_type` (to CheckBox)")
    if letter == "#":
        raise EditError(
            f"ссылка на объект у поля {element!r}: её GUID и блок редактирования (справочник, документ, перечисление — у "
            "каждого свои) берутся из выгрузки конфигурации. Привяжите поле через `bind` с путём по метаданным (`data`, `--config`)")
    if letter not in LETTERS:
        raise EditError(f"тип {letter!r}: поле ввода получает {', '.join(LETTERS)}")
    notes = _complete_string_blocks(pattern, element)
    pattern.setdefault(PATTERN_MARK, "Pattern")
    return pattern, notes


def _checked_field(doc, element):
    """`(место, содержимое, «поля X», реквизит формы)` — предпосылки `set_field_type`, не зависящие от нового типа; отказ словами."""
    place = find_element(doc, element)
    kind = place.element.get("type")
    if kind != "TextBox":
        raise EditError(f"set_field_type меняет тип поля ввода (TextBox), а у элемента {element!r} вид {kind}")
    content = place.element.get(CONTENT)
    who = f"поля {element!r}"
    datatype.textbox_type_places(content, who)
    if content.get(LIST_CHOICE_MODE) is True:
        raise EditError(
            f"у поля {element!r} включён РежимВыбораИзСписка: этот режим держит тип пустым, и платформа при выборе типа его "
            "снимает вместе с блоком редактирования. Снимите режим (`set_property`, РежимВыбораИзСписка = false), потом задайте тип")
    row = _own_attribute(doc, place, element)
    return place, content, who, row


def _class_check(content, element):
    """`(класс типа поля, тип пуст)`; отказ, если тип поля не строка, не число, не дата и не пуст."""
    was = datatype.content_class(content)
    field_types = (content.get(datatype.TEXTBOX_PATTERN) or {}).get(PATTERN_TYPES)
    free = isinstance(field_types, list) and not field_types
    if not free and was not in CLASS_OF_LETTER.values():
        raise EditError(
            f"у поля {element!r} тип {datatype.current_type_words(content)}"
            + (f" (класс «{datatype.CLASS_WORDS[was]}»)" if was else "")
            + ": операция меняет тип поля, у которого тип пуст или это строка, число или дата. Ссылку, булево и составной тип "
              "меняют в конфигураторе (ссылку на другой объект — `bind` по метаданным)")
    return was, free


def field_type_blocker(doc, element):
    """Почему `set_field_type` не меняет тип поля `element` (слова отказа операции), либо `None`, если поле ей подходит: те же проверки, что у операции,
    которые не зависят от нового типа (вид, режим выбора из списка, реквизит формы у поля, класс типа). Новый тип может отказать отдельно."""
    try:
        _place, content, _who, _row = _checked_field(doc, element)
        _class_check(content, element)
    except EditError as e:
        return str(e)
    return None


def set_field_type(doc, element, pattern, unverified=False):
    """Тип поля ввода и его реквизита формы: описатель обоих, `digits` и состав даты поля, запись класса.

    `pattern` — описатель типа в форме `add_attribute`: `{"types": [{"kind": "S", "length": 10}]}` (одиночный блок `S`, `N` или `D`;
    строка с длиной без второго числа дополняется единицей, как у `add_attribute`). Поле привязано к СВОЕМУ реквизиту формы одним
    шагом (иначе отказ), у него не включён `РежимВыбораИзСписка`, и реквизит держит только это поле.

    Что пишется: описатель реквизита формы и описатель поля — тот же блок; среди свойств поля — зеркало типа (`block_mirror`: у
    строки длина в `digits`, у числа три числа, у даты состав); если у поля тип пуст («Произвольный»), то записываются и свойства
    класса (`wrap`, кнопки, `u22`) и блок редактирования — как платформа вернула строку полю после снятия режима выбора из списка.
    Без `unverified` выполняются случаи, записанные платформой (строка, число, дата в поле без типа; смена вида типа между строкой,
    числом и датой; новый тип внутри класса), остальное (кнопка очистки включена, дата с составом не `D`) — только с `unverified=true`.
    """
    place, content, who, row = _checked_field(doc, element)
    new_pattern, string_notes = _one_block(pattern, element)
    block = new_pattern[PATTERN_TYPES][0]
    letter = block.get(PATTERN_KIND)
    new_class = CLASS_OF_LETTER[letter]
    mirror = datatype.block_mirror(block)
    was, free = _class_check(content, element)
    written = []
    platform_made = _platform_made(content, free, was, new_class, block)
    if not unverified and not platform_made and not (was == new_class and not free):
        if free:
            raise EditError(
                f"тип {LETTER_WORDS[letter]} в поле {element!r} без типа платформа записывает так, как запись снята: "
                f"{_PLATFORM_CASES}. Здесь {_why_not(content, free, was, new_class, block)}, и что платформа пишет в таком случае, не "
                "снято. Чтобы всё же записать тип и запись конструктора, передайте unverified=true: результат придётся проверить самостоятельно")
        raise EditError(
            f"у поля {element!r} класс типа «{datatype.CLASS_WORDS[was]}», а новый тип — «{datatype.CLASS_WORDS[new_class]}»: платформа "
            f"меняет класс так, как запись снята: {_PLATFORM_CASES}. Здесь {_why_not(content, free, was, new_class, block)}, и что "
            "платформа пишет в таком случае, не снято. Чтобы всё же выполнить операцию, передайте unverified=true: результат придётся "
            "проверить самостоятельно")
    old_words = datatype.current_type_words(content)
    old_attr = _letter_words((row.get(ATTR_PATTERN) or {}).get(PATTERN_TYPES) if isinstance(row.get(ATTR_PATTERN), dict) else None)
    old_digits = datatype._props(content).get("digits")
    # Реквизит формы: описатель целиком, остальные ключи описателя (метка) остаются.
    attr_pattern = row.get(ATTR_PATTERN) if isinstance(row.get(ATTR_PATTERN), dict) else {}
    attr_pattern = {**attr_pattern, PATTERN_TYPES: copy.deepcopy(new_pattern[PATTERN_TYPES])}
    attr_pattern.setdefault(PATTERN_MARK, "Pattern")
    row[ATTR_PATTERN] = attr_pattern
    old_props = dict(datatype._props(content))
    datatype.set_textbox_type(content, block, mirror, who)
    kept = _keep_residue(content, old_props, free, was, letter)
    if free:
        written.append(_write_class(content, new_class))
    elif was != new_class:
        old_wrap = datatype._props(content).get("wrap")
        written.append(datatype.apply_record(content, new_class, "field", who, was).lstrip("; "))
        if new_class == "string" and old_wrap is not None and datatype._props(content).get("wrap") != old_wrap:
            # Платформа при переходе к строке из числа или даты `wrap` не меняет: запись конструктора его бы включила.
            datatype._props(content)["wrap"] = old_wrap
            written[-1] = re.sub(r"wrap \w+ → \w+(, )?", "", written[-1]).rstrip(" :,")
            written.append(f"wrap остаётся {old_wrap} (платформа при переходе к строке его не меняет)")
    said = (f"поле {element!r}: тип {old_words} → {datatype.current_type_words(content)}"
            + (f", digits {old_digits} → {datatype._props(content).get('digits')}" if old_digits != datatype._props(content).get("digits") else "")
            + f"; реквизит формы {row.get(ATTR_NAME)!r}: тип {old_attr} → {_letter_words(attr_pattern[PATTERN_TYPES])}")
    written.extend(kept)
    said += "".join(f"; {w}" for w in written)
    said += "".join(f"; {n}" for n in string_notes)
    if free and new_class == "string":
        said += ("; запись совпадает с платформенной («Строка 10» из пустого типа — описатель, длина и блок редактирования "
                 "строки)")
    elif platform_made and (free or was != new_class):
        said += ("; запись совпадает с платформенной (вид типа в палитре: описатель, `digits`, кнопка выбора по виду типа, `u22` и "
                 "блок редактирования — как у платформы)")
    elif unverified and (free or was != new_class):
        said += ("; НЕ ПРОВЕРЕНО платформой: запись класса снята с конструктора; образцы форм держат у полей этого типа другие "
                 "варианты (кнопка выбора, `u22`), результат проверяете вы")
    else:
        said += "; смена типа внутри класса: описатель поля повторяет описатель реквизита — так у всех полей образцов"
    return said


_PLATFORM_CASES = ("поле без типа становится строкой, числом или датой, а поле со строкой, числом или датой меняет вид типа между "
                   "ними (состав даты `D`), если кнопка очистки у него выключена; кнопку выбора платформа ставит по виду типа сама")


def _platform_made(content, free, was, new_class, block):
    """Платформа сняла запись класса для смены вида типа между строкой, числом и датой (кнопка выбора — по виду типа, `u22`,
    `digits`) и для числа и даты у поля без типа; у поля с включённой кнопкой очистки и у даты не `D` — нет."""
    return _why_not(content, free, was, new_class, block) is None


def _why_not(content, free, was, new_class, block):
    """Слова о том, что мешает считать запись платформенной; `None`, если платформа писала именно такую."""
    if free and new_class == "string":
        return None
    if not free and was not in ("string", "decimal", "dateTime"):
        return f"у поля тип класса «{datatype.CLASS_WORDS.get(was, was)}»"
    if datatype._props(content).get("clear_button"):
        return "у поля включена кнопка очистки"
    if new_class == "dateTime" and block.get("date_fractions") != "D":
        return "состав даты не `D`"
    return None


def _keep_residue(content, old_props, free, was, letter):
    """При смене вида типа платформа переписывает `digits`, а дробную часть, знак числа и состав даты оставляет прежними, пока
    новый вид типа их не использует (опыт: число 15,2 → строка 20 и число 12,2 → дата — дробная часть 2 осталась). Возвращает слова."""
    if free or was is None or was == datatype.FORM_LETTER_CLASS[letter]:
        return []
    props = datatype._props(content)
    keys = {"N": (), "S": datatype.TEXTBOX_NUMBER[1:] + (datatype.DATE_FRACTIONS,), "D": datatype.TEXTBOX_NUMBER[1:]}[letter]
    return _restore(props, old_props, keys)


def _restore(props, old_props, keys):
    kept = []
    for key in keys:
        if props.get(key) != old_props.get(key):
            props[key] = old_props.get(key)
            kept.append(f"{key} остаётся {old_props.get(key)!r} (платформа при смене вида типа его не трогает)")
    return kept


def _write_class(content, cls):
    """Поле без типа получает запись класса целиком: свойства класса и блок редактирования, если строение не то."""
    from .. import templates
    record = templates.class_record("field", cls)
    datatype.check_record(content, cls, "field", "поля")
    props = datatype._props(content)
    changed = {key: (props.get(key), value) for key, value in record["props"].items() if props.get(key) != value}
    props.update(record["props"])
    out = f"запись класса «{datatype.CLASS_WORDS[cls]}» по конструктору"
    out += (": " + ", ".join(f"{key} {old} → {new}" for key, (old, new) in changed.items())) if changed else ": свойства уже такие"
    if datatype._u3_shape(content[datatype.EDIT_BLOCK[0]]) != datatype._u3_shape(record["u3"]):
        content[datatype.EDIT_BLOCK[0]] = record["u3"]
        out += f"; блок редактирования {record['u3']['u1']['u0'][datatype.GUID]} записан целиком"
    return out
