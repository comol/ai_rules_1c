"""Тип элемента формы по типу реквизита, к которому он привязан.

Когда платформа привязывает поле ввода к реквизиту объекта, она записывает в поле тип реквизита: описатель типа
(`Content.TextBox/pattern`) и его зеркало среди свойств поля (разрядность, точность, знак, состав даты).

* `S` — блок `{S, длина, u2}`. Длина — это `Length`. `u2` равен 1 при `AllowedLength = Variable` и 0 при `Fixed`. У строки без
  длины блок состоит из одного слова `{S}`.
* `N` — блок `{N, разрядность, дробная часть, неотрицательный}` (`Digits`, `FractionDigits`, `AllowedSign`).
* `D` — блок `{D, состав}`. Состав `Date` записывается буквой `D`, `Time` — буквой `T`, а у `DateTime` буквы нет (`DATE_LETTERS`).
* `B` — блок `{B}`. У поля ввода на булев реквизит его не бывает: платформа рисует флажок.
* `#` — блок `{#, GUID}`, где GUID — это `TypeId` категории `Ref` объекта-цели. Для справочника и документа он берётся из
  выгрузки, для перечисления — из `Enums/<Имя>.xml` (`Config.ref_type_id`).
* Зеркало среди свойств поля: у `N` это те же три числа, у `S` длина строки записывается в разрядность, у `D` состав
  записывается словом, у `B` и у ссылки стоят нули и `Date`.

Команда `bind` записывает и то, что зависит от класса типа, по образцу конструктора форм (`apply_record`, данные — в
`data/templates/class-records.json`). Это `wrap`, кнопки выбора и очистки, `u22` и блок редактирования `u3`. Блок редактирования
зависит от класса: у строки, числа и даты это `9a7643d2…` (вариант 4), у справочника `8585207b…` (вариант 5), у документа
`11fe1b25…` (вариант 3), у перечисления `30ee7b7c…` (вариант 1), а у составного типа блоков два. Запись класса пишется только
тогда, когда класс поля меняется: блок заменяется целиком, если его строение не соответствует новому классу. Если класс поля
не меняется или его нельзя определить, поле остаётся как есть, а расхождение с образцом называется в отчёте. Тип реквизита
формы (`bind copy_type`) записывается другим путём (`form_attribute_block_note`).

Составной тип. Образец конструктора содержит по одному типу: строку, число и ссылку на справочник. Блоки описателя идут в
таком порядке: ссылки по возрастанию GUID `TypeId` (сравнение строк), а булево, строка, дата и число стоят между ними на своих
местах (`COMPOSITE_PLACES`, `composite_order`). Если ссылка попадает в зону неопределённости, операция отказывает. Зеркало
квалификаторов состоит из нулей, а у вложенного поля колонки `digits` равно 255 (это часть записи класса).

Следующее не записывается. Путь привязки записывается, тип остаётся прежним, отчёт называет причину, а без `unverified`
операция отказывает. Это составной тип вне проверенных наборов (со временем, с «датой и временем», с набором типов),
составной тип со ссылкой в зоне неопределённости, `TypeSet`, ссылка на объект вне выгрузки, вид ссылки, который
`ref_type_id` не читает, число без квалификаторов, дата без состава и строка с длиной без `AllowedLength`.
"""

import copy

from .. import metadata, schema

from .names import (
    CONTENT,
    PATTERN_KIND,
    PATTERN_LENGTH,
    PATTERN_NUMBER,
    PATTERN_REF,
    PATTERN_TYPES,
    TEXTBOX_NUMBER,
    TEXTBOX_PATTERN,
    TEXTBOX_PROPS,
    _maybe,
)
from .base import EditError
from .cowrites import DATE_LETTERS, PATTERN_DATE
from .propbase import DATE_FRACTIONS

STRING_ALLOWED = _maybe("PatternType.S", 2)  # u2: 1 — переменная длина, 0 — фиксированная
TYPE_GUID = PATTERN_REF                          # `value_type`: {guid}
GUID = "guid"
EDIT_BLOCK = (_maybe("Content.TextBox", 3), _maybe("Content.TextBox.u3", 1), _maybe("Content.TextBox.u3.u1", 0))

# Блок редактирования поля ввода в зависимости от класса типа (GUID).
EDIT_BLOCKS = {
    "string": "9a7643d2-19e9-45e2-8893-280bc9195a97",
    "decimal": "9a7643d2-19e9-45e2-8893-280bc9195a97",
    "dateTime": "9a7643d2-19e9-45e2-8893-280bc9195a97",
    "catalog": "8585207b-9ca7-425b-9385-e8fd67c4e148",
    "document": "11fe1b25-97c5-4d25-ab3f-8c9a5655122e",
    "enum": "30ee7b7c-8dac-4e20-b58e-e7f7742ae8d8",
}
CLASS_WORDS = {"string": "строка", "decimal": "число", "boolean": "булево", "dateTime": "дата",
               "catalog": "ссылка на справочник", "document": "ссылка на документ",
               "enum": "ссылка на перечисление", "composite": "составной тип (строка, число, ссылка на справочник)"}
XS = {"xs:string": "string", "xs:decimal": "decimal", "xs:boolean": "boolean", "xs:dateTime": "dateTime"}
REFS = {"CatalogRef": "catalog", "DocumentRef": "document", "EnumRef": "enum"}


class TypeNotWritten(Exception):
    """Если тип реквизита нельзя записать в поле, возвращается причина для отчёта или отказа."""


# Порядок блоков составного описателя. Ссылки идут по возрастанию GUID `TypeId` (сравнение строк). Примитивные блоки стоят
# между ссылками в порядке: булево, строка, дата, число. Место примитива задаёт окно. Если GUID ссылки не больше `lo`, то
# ссылка стоит перед примитивом. Если он не меньше `hi`, то после. Если он строго между ними, то это зона неопределённости, и
# операция отказывает. Окна заданы здесь и только здесь: B — (5c000000, 5e000000), S — (9b000000, 9c000000), D — (aa000000,
# ab000000), N — (b0000000, b1000000). `D` означает дату с составом `Date`. Время и «дата и время» не проверялись, поэтому
# набор с ними приводит к отказу.
COMPOSITE_PLACES = {
    "B": ("5c000000-0000-4000-8000-000000000035", "5e000000-0000-4000-8000-000000000036"),
    "S": ("9b000000-0000-4000-8000-000000000019", "9c000000-0000-4000-8000-000000000008"),
    "D": ("aa000000-0000-4000-8000-000000000038", "ab000000-0000-4000-8000-000000000039"),
    "N": ("b0000000-0000-4000-8000-000000000004", "b1000000-0000-4000-8000-00000000001d"),
}
COMPOSITE_SIMPLE = {"xs:boolean": "B", "xs:string": "S", "xs:dateTime": "D", "xs:decimal": "N"}  # вид блока по типу реквизита; порядок как в `COMPOSITE_PLACES`
KIND_WORDS = {"B": "булева", "S": "строки", "D": "даты", "N": "числа"}
# Образец конструктора содержит строку, число и один справочник. Запись класса (`class-records.json`) снята с него. Для
# наборов, которых в образце нет, берётся та же запись, и `composite_note` говорит об этом в отчёте.
COMPOSITE_SAMPLE = ["S", "#", "N"]


def composite_order(refs, simple, name="?"):
    """Порядок видов блоков описателя составного типа по GUID `TypeId` ссылок. Результат — список из `B`, `S`, `D`, `N` (`simple`) и
    `#` на месте каждой ссылки (`refs` — GUID по возрастанию). Если ссылка попадает в зону неопределённости
    (`COMPOSITE_PLACES`), возникает `TypeNotWritten`.
    """
    marks = sorted(str(g).strip().lower() for g in refs)
    slots = {}
    kinds = [k for k in "BSDN" if k in simple]
    for g in marks:
        index = 0
        for kind in kinds:
            below, above = COMPOSITE_PLACES[kind]
            if g >= above:
                index += 1
            elif g > below:
                raise TypeNotWritten(
                    f"тип реквизита «{name}»: ссылка {g} в составном типе лежит в зоне неопределённости места {KIND_WORDS[kind]} ({below}…{above}): "
                    "блоки описателя идут по возрастанию GUID, а где платформа поставит эту ссылку относительно "
                    f"{KIND_WORDS[kind]}, не проверялось (окна заданы в `COMPOSITE_PLACES`)")
        slots.setdefault(index, []).append(g)
    order = []
    for index in range(len(kinds) + 1):
        order += ["#"] * len(slots.get(index, []))
        if index < len(kinds):
            order.append(kinds[index])
    return order


def _composite_parts(attr):
    """Составной набор по типам реквизита: `(виды простых блоков, имена ссылок)`. Если набор не относится к проверенным, возвращается `None`."""
    if attr.type_sets or len(attr.types) < 2:
        return None
    simple, refs = set(), []
    for name in attr.types:
        if name in COMPOSITE_SIMPLE:
            simple.add(COMPOSITE_SIMPLE[name])
        elif name.startswith("cfg:") and name[len("cfg:"):].partition(".")[0] in REFS:
            refs.append(name)
        else:
            return None
    if "D" in simple and attr.date_fractions != "Date":
        return None
    return simple, refs


def composite_ok(attr):
    """Проверяет, что тип набора можно записать как составной (`COMPOSITE_PLACES`). Нужно не меньше двух типов из списка: булево,
    строка, дата (состав `Date`), число, ссылка на справочник, документ или перечисление. `TypeSet` и остальные виды не подходят.
    """
    return _composite_parts(attr) is not None


def type_class(attr):
    """Класс типа реквизита: `string`, `decimal`, `boolean`, `dateTime`, `catalog`, `document`, `enum` или `composite`. Для составного
    типа вне проверенных наборов (`composite_ok`), для `TypeSet` и для прочих видов возникает `TypeNotWritten` с пояснением.
    """
    if attr.type_sets:
        raise TypeNotWritten(f"тип реквизита «{attr.name}» — набор типов ({', '.join(attr.type_sets)}): "
                             "определяемый тип требует раскрытия, а составной описатель с ним не проверялся")
    if not attr.types:
        raise TypeNotWritten(f"реквизит «{attr.name}» произвольного типа (в выгрузке `<Type/>` без типов): описателя типа для него нет")
    if len(attr.types) != 1:
        if composite_ok(attr):
            return "composite"
        raise TypeNotWritten(f"тип реквизита «{attr.name}» составной ({', '.join(attr.types)}): можно записать набор из булева, строки, даты (состав Date), числа и "
                             "ссылок на справочник, документ, перечисление: для них проверен порядок блоков по GUID ссылок (`COMPOSITE_PLACES`); "
                             "время, «дата и время», набор типов и прочие виды в составном типе не поддерживаются")
    name = attr.types[0]
    if name in XS:
        return XS[name]
    kind = name[len("cfg:"):].partition(".")[0] if name.startswith("cfg:") else ""
    if kind in REFS:
        return REFS[kind]
    raise TypeNotWritten(f"тип реквизита «{attr.name}» — {name}: такого вида типа выгрузка не разбирает "
                         "(строка, число, булево, дата, ссылка на справочник, документ, перечисление, составной тип строка+число+справочник)")


def _string_block(attr):
    block = {PATTERN_KIND: "S"}
    if attr.string_length:
        if attr.allowed_length not in ("Variable", "Fixed"):
            raise TypeNotWritten(f"у строки «{attr.name}» длина {attr.string_length}, а допустимая длина "
                                 "(AllowedLength) в выгрузке не названа")
        block[PATTERN_LENGTH] = attr.string_length
        block[STRING_ALLOWED] = 1 if attr.allowed_length == "Variable" else 0
    return block


def _number_block(attr):
    if attr.digits is None or attr.fraction is None:
        raise TypeNotWritten(f"у числа «{attr.name}» в выгрузке нет квалификаторов (Digits, FractionDigits)")
    return {PATTERN_KIND: "N", PATTERN_NUMBER[0]: attr.digits, PATTERN_NUMBER[1]: attr.fraction,
            PATTERN_NUMBER[2]: attr.allowed_sign == "Nonnegative"}


def blocks_of(block):
    """Описатель типа как список блоков: у простого класса один блок, у составного — несколько в порядке записи конструктора."""
    return [copy.deepcopy(b) for b in block] if isinstance(block, list) else [copy.deepcopy(block)]


def pattern_block(attr, config):
    """Блок описателя типа и зеркало квалификаторов поля ввода: `(блок, зеркало, класс)`.

    Зеркало — это `(разрядность, дробная часть, неотрицательный, состав даты)` среди свойств поля. У составного типа «блок» —
    это список блоков в порядке `composite_order`, а зеркало состоит из нулей (разрядность 255 у колонки ставит запись класса,
    `apply_record`). `TypeNotWritten` означает, что тип нельзя записать в поле.
    """
    cls = type_class(attr)
    name = attr.name
    mirror = [0, 0, False, "Date"]
    if cls == "string":
        block = _string_block(attr)
        mirror[0] = attr.string_length or 0
    elif cls == "decimal":
        block = _number_block(attr)
        mirror[:3] = [block[PATTERN_NUMBER[0]], block[PATTERN_NUMBER[1]], block[PATTERN_NUMBER[2]]]
    elif cls == "boolean":
        block = {PATTERN_KIND: "B"}
    elif cls == "dateTime":
        if attr.date_fractions not in DATE_LETTERS:
            raise TypeNotWritten(f"у даты «{name}» состав (DateFractions = {attr.date_fractions!r}) не назван "
                                 "или не Date/Time/DateTime")
        block = {PATTERN_KIND: "D"}
        if DATE_LETTERS[attr.date_fractions] is not None:
            block[PATTERN_DATE] = DATE_LETTERS[attr.date_fractions]
        mirror[3] = attr.date_fractions
    elif cls == "composite":
        simple, ref_names = _composite_parts(attr)
        guids = {}
        for ref in ref_names:
            try:
                guids[config.ref_type_id(ref)] = ref
            except metadata.MetadataError as e:
                raise TypeNotWritten(f"тип реквизита «{name}»: {e}") from None
        made = {"S": lambda: _string_block(attr), "N": lambda: _number_block(attr), "B": lambda: {PATTERN_KIND: "B"},
                "D": lambda: {PATTERN_KIND: "D", PATTERN_DATE: DATE_LETTERS["Date"]}}
        block, refs = [], iter(sorted(g.strip().lower() for g in guids))
        for kind in composite_order(list(guids), simple, name):
            block.append({PATTERN_KIND: "#", TYPE_GUID: {GUID: next(refs)}} if kind == "#" else made[kind]())
    else:
        try:
            guid = config.ref_type_id(attr.types[0])
        except metadata.MetadataError as e:
            raise TypeNotWritten(f"тип реквизита «{name}»: {e}") from None
        block = {PATTERN_KIND: "#", TYPE_GUID: {GUID: guid}}
    return block, tuple(mirror), cls


DATE_BY_LETTER = {letter: word for word, letter in DATE_LETTERS.items()}


def date_part(spec):
    """Состав даты по записи типа — слово `Date`, `Time` или `DateTime`, либо `None`, если запись состава не называет. ОДИН разбор на все места,
    где тип даты пишет человек: ключ `attributes` описания `generate`, колонки таблицы значений, описатель типа реквизита (`add_attribute`, `bind`).
    Ключей два: `date` — слово (`Date`, `Time`, `DateTime`) и `date_fractions` — буква блока описателя (`D` — дата, `T` — время; у «даты и
    времени» буквы нет, поэтому её называет только слово). Оба вместе, слово не из трёх и буква не из двух — `EditError` словами."""
    word, has_letter = spec.get("date"), "date_fractions" in spec
    if word is not None and has_letter:
        raise EditError(f"состав даты назван дважды: date ({word!r}) и date_fractions ({spec['date_fractions']!r}) — оставьте один ключ")
    if word is not None:
        if word not in DATE_LETTERS:
            raise EditError(f'date — состав даты: {", ".join(DATE_LETTERS)}, а пришло {word!r}. Дата: {{"date": "Date"}}, время: "Time", '
                            'дата и время: "DateTime"')
        return word
    if has_letter:
        letter = spec["date_fractions"]
        if letter not in ("D", "T"):
            raise EditError(f'date_fractions — буква состава: "D" (дата) или "T" (время), а пришло {letter!r}; дату со временем называет слово '
                            '{"date": "DateTime"}')
        return DATE_BY_LETTER[letter]
    return None
FORM_ATTRIBUTE_LETTERS = ("S", "N", "D", "#")  # одиночные блоки, у которых поле ввода повторяет реквизит формы


def block_mirror(block):
    """Зеркало квалификаторов среди свойств поля ввода по готовому блоку описателя: `(разрядность, дробная часть, неотрицательный,
    состав даты)`. Это обратная операция к `pattern_block`: та строит блок по метаданным, а эта строит зеркало по блоку
    реквизита формы. Результат почти всегда совпадает с `block_mirror`. Если поле не повторяет реквизит (другая длина, «точность
    2» у строки, «ДатаВремя» у ссылки), результат расходится. Для числа без квалификаторов правило отказывает.
    """
    kind = block.get(PATTERN_KIND) if isinstance(block, dict) else None
    mirror = [0, 0, False, "Date"]
    if kind == "S":
        mirror[0] = block.get(PATTERN_LENGTH) or 0
    elif kind == "N":
        mirror[:3] = [block.get(PATTERN_NUMBER[0]), block.get(PATTERN_NUMBER[1]), block.get(PATTERN_NUMBER[2])]
        if any(v is None for v in mirror[:3]):
            raise EditError("у числа в описателе реквизита нет квалификаторов (разрядность, дробная часть, знак): зеркало в поле записать "
                            "нечем. Такой описатель встречается в образцах форм крайне редко")
    elif kind == "D":
        if PATTERN_DATE in block and block[PATTERN_DATE] not in DATE_BY_LETTER:
            raise EditError(f"состав даты в описателе {block[PATTERN_DATE]!r}: платформа пишет {', '.join(map(repr, DATE_BY_LETTER))} "
                            "(а у «дата и время» буквы нет). Другую букву операция не угадывает. Возможно, документ правили вручную.")
        mirror[3] = DATE_BY_LETTER[block[PATTERN_DATE]] if PATTERN_DATE in block else "DateTime"
    elif kind != "#":
        raise EditError(f"зеркало квалификаторов по описателю {kind!r} не проверялось (проверены {', '.join(FORM_ATTRIBUTE_LETTERS)})")
    return tuple(mirror)


def _props(content):
    node = content
    for step in TEXTBOX_PROPS:
        node = node.get(step) if isinstance(node, dict) else None
    return node if isinstance(node, dict) else None


def textbox_type_places(content, who):
    """`(описатель типа, свойства поля)` у содержимого поля ввода — либо отказ словами."""
    pattern = content.get(TEXTBOX_PATTERN) if isinstance(content, dict) else None
    types = pattern.get(PATTERN_TYPES) if isinstance(pattern, dict) else None
    props = _props(content)
    keys = TEXTBOX_NUMBER + (DATE_FRACTIONS,)
    if not isinstance(types, list) or props is None or any(k not in props for k in keys):
        raise EditError(f"у {who} нет описателя типа или квалификаторов среди свойств, хотя у полей ввода они всегда есть. "
                        "Возможно, документ правили вручную.")
    return pattern, props


def set_textbox_type(content, block, mirror, who):
    """Записать тип в содержимое поля ввода: описатель и зеркало. Путь привязки здесь не трогается."""
    pattern, props = textbox_type_places(content, who)
    pattern[PATTERN_TYPES] = blocks_of(block)
    for key, value in zip(TEXTBOX_NUMBER + (DATE_FRACTIONS,), mirror):
        props[key] = value


def _u3_shape(u3):
    """Строение блока редактирования: число блоков, GUID первого блока и наличие второго. По этим признакам конструктор различает классы типа."""
    if not isinstance(u3, dict):
        return None
    first = (u3.get("u1") or {}).get("u0") if isinstance(u3.get("u1"), dict) else None
    return (u3.get("u0"), first.get(GUID) if isinstance(first, dict) else None, "u2" in u3)


def content_class(content):
    """Класс типа поля ввода по его текущему содержимому (до записи нового типа) или `None`. Класс определяется по описателю (`S`,
    `N`, `D`, `B`; несколько блоков означают составной тип), а у ссылки `#` — по GUID блока редактирования (`EDIT_BLOCKS`).
    Если класс определить нельзя, возвращается `None`, и для записи класса такое поле считается чужим.
    """
    pattern = content.get(TEXTBOX_PATTERN) if isinstance(content, dict) else None
    types = pattern.get(PATTERN_TYPES) if isinstance(pattern, dict) else None
    if not isinstance(types, list) or not types or not all(isinstance(b, dict) for b in types):
        return None
    if len(types) > 1:
        return "composite"
    kind = types[0].get(PATTERN_KIND)
    if kind in FORM_LETTER_CLASS:
        return FORM_LETTER_CLASS[kind]
    if kind == "B":
        return "boolean"
    if kind == "#":
        guid = edit_block_guid(content)
        return next((c for c in ("catalog", "document", "enum") if EDIT_BLOCKS[c] == guid), None)
    return None


def composite_note(block):
    """Слова про составной описатель для отчёта. Они нужны, если набор или порядок блоков отличаются от образца конструктора
    (`COMPOSITE_SAMPLE`: строка, ссылка, число). Иначе результат пуст. Запись класса и второй блок редактирования (`u3/u2`) сняты с
    образца, а зависят ли они от набора и места ссылки, не проверялось.
    """
    if not isinstance(block, list) or [b.get(PATTERN_KIND) for b in block if isinstance(b, dict)] == COMPOSITE_SAMPLE:
        return ""
    kinds = "+".join(str(b.get(PATTERN_KIND)) for b in block if isinstance(b, dict))
    return (f"; составной тип {kinds}, а у образца конструктора — {'+'.join(COMPOSITE_SAMPLE)}: порядок блоков определён правилом GUID (`COMPOSITE_PLACES`), "
            "запись класса и второй блок редактирования (`u3/u2`) взяты с образца, а зависят ли они от набора и места ссылки, не проверялось")


def check_record(content, cls, host, who):
    """Отказ до правки, если записи класса негде лечь: у поля нет свойств или блока редактирования."""
    from .. import templates
    if templates.class_record(host, cls) is None:
        return
    if _props(content) is None or EDIT_BLOCK[0] not in content:
        raise EditError(f"у {who} нет свойств или блока редактирования, хотя у полей ввода они всегда есть. Возможно, документ правили вручную.")


def write_type_and_record(content, block, mirror, cls, host, who):
    """Записывает тип в поле ввода (описатель и зеркало, `set_textbox_type`) и запись класса (`apply_record`), возвращает слова для
    отчёта. Класс поля до записи определяется по его содержимому (`content_class`). Одно и то же место используют `bind` для
    поля и колонки, `add_column` и `generate`.
    """
    was = content_class(content)
    digits = _props(content).get("digits") if _props(content) is not None else None
    set_textbox_type(content, block, mirror, who)
    if cls == "composite" and was == "composite":
        _props(content)["digits"] = digits  # `digits` входит и в зеркало (у составного типа нули), и в запись класса (у колонки 255): поле того же класса его не теряет
    elif cls == "composite" and was is None:
        from .. import templates
        _props(content)["digits"] = templates.class_record(host, cls)["props"]["digits"]  # класс неизвестен: зеркало не должно затереть `digits` нулём
    return apply_record(content, cls, host, who, was) + composite_note(block)


def apply_record(content, cls, host, who, was=None):
    """Запись класса типа поля ввода в том виде, как её пишет конструктор: `wrap`, кнопки выбора и очистки, `u22` (у составного типа
    вместе с `digits`) и блок редактирования `u3`. Параметр `host` равен `"field"` (поле шапки) или `"column"` (вложенное поле
    колонки): у составного типа `digits` в этих случаях равен 0 и 255. Описатель и зеркало записывает `set_textbox_type`.

    Запись выполняется при смене класса. Параметр `was` — класс поля до записи типа (`content_class`). Если класс назван и
    отличается от нового (`was` не `None` и не `cls`), поле получает запись конструктора, а блок редактирования заменяется
    целиком, когда его строение не соответствует классу. Если класс не меняется или неизвестен (`was is None`), поле остаётся как
    есть: повторная привязка `bind` не меняет настройки человека, а донор `add_column` не теряет вложенное поле. Расхождение с
    записью конструктора называется в отчёте. Новое поле из шаблона панели или образца колонки получает запись так же. Функция
    возвращает слова для отчёта; для класса без записи (булево) они пусты.
    """
    from .. import templates
    record = templates.class_record(host, cls)
    if record is None:
        return ""
    check_record(content, cls, host, who)
    props = _props(content)
    diff = {key: (props.get(key), value) for key, value in record["props"].items() if props.get(key) != value}
    shape_differs = _u3_shape(content[EDIT_BLOCK[0]]) != _u3_shape(record["u3"])
    if was is None or was == cls:
        why = "того же класса" if was == cls else "класс которого до записи не назвать (описателя типа нет или он разобран иначе)"
        if not diff and not shape_differs:
            return f"; поле {why}: «{CLASS_WORDS[cls]}», свойства как у конструктора"
        words = [f"{key} {old} (конструктор пишет {new})" for key, (old, new) in diff.items()]
        if shape_differs:
            words.append("блок редактирования другого строения")
        return f"; поле {why}: «{CLASS_WORDS[cls]}» — свойства остались прежними и расходятся с записью конструктора: {', '.join(words)}"
    props.update(record["props"])
    out = (f"; запись класса «{CLASS_WORDS[cls]}» по конструктору (прежний класс — «{CLASS_WORDS[was]}»)"
           + (f": {', '.join(f'{key} {old} → {new}' for key, (old, new) in diff.items())}" if diff else ": свойства уже такие"))
    if shape_differs:
        content[EDIT_BLOCK[0]] = record["u3"]
        out += f", блок редактирования {record['u3']['u1']['u0'][GUID]} записан целиком"
    return out


def current_type_words(content):
    """Описатель типа поля словами для отчёта: «S(10)», «#», «составной»."""
    pattern = content.get(TEXTBOX_PATTERN) if isinstance(content, dict) else None
    types = pattern.get(PATTERN_TYPES) if isinstance(pattern, dict) else None
    if not isinstance(types, list):
        return "не разобран"
    if not types:
        return "пустой"
    return "+".join(str(b.get(PATTERN_KIND)) for b in types if isinstance(b, dict))


def edit_block_guid(content):
    """GUID блока редактирования (`u3`) в содержимом поля ввода или `None`."""
    node = content
    for step in EDIT_BLOCK[:2]:
        node = node.get(step) if isinstance(node, dict) else None
    return (node.get(EDIT_BLOCK[2]) or {}).get(GUID) if isinstance(node, dict) \
        and isinstance(node.get(EDIT_BLOCK[2]), dict) else None


def edit_block_note(content, cls):
    """Слова про блок редактирования (`u3`), если он не совпадает с блоком, обычным для класса типа; иначе пусто."""
    guid = edit_block_guid(content)
    want = EDIT_BLOCKS.get(cls)
    if want is None or guid == want:
        return ""
    return (f"блок редактирования поля (u3) остался прежним ({guid}), а для типа «{CLASS_WORDS[cls]}» в образцах форм "
            f"стоит {want} (так у подавляющего большинства полей): bind его не пересобирает, и принимает ли платформа поле с таким блоком, "
            "не проверялось")


FORM_LETTER_CLASS = {"S": "string", "N": "decimal", "D": "dateTime"}
# Блок редактирования поля ввода, привязанного к реквизиту формы с одиночным `#`: у справочника, документа и перечисления свои
# блоки; блок строки `9a7643d2…` у них не встречается.
FORM_REF_BLOCKS = "у справочника, документа и перечисления блоки свои, блок строки у таких полей не встречается"


def form_ref_class(config, guid):
    """Класс типа-ссылки реквизита формы по GUID и выгрузке (`catalog`, `document`, `enum`) или `None`. `None` возвращается, если
    выгрузки нет, GUID не из неё или категория не `Ref`. Перечисление распознаётся, только если выгрузка уже читала его
    `Enums/<Имя>.xml` (`ref_type_id`).
    """
    if config is None or not guid:
        return None
    hit = config.object_by_type_id(guid)
    if hit is not None:
        return hit[0].kind if hit[1].lower() == "ref" and hit[0].kind in ("catalog", "document") else None
    return "enum" if guid.strip().lower() in {v.strip().lower() for v in config._enum_refs.values()} else None


def form_attribute_block_note(content, block, config=None):
    """Слова про блок редактирования (`u3`) поля, которое взяло тип реквизита формы (`bind copy_type`), или пусто.

    `copy_type` не пересобирает блок: он остаётся от шаблона (блок строки). Для `S`, `N`, `D` это обычный блок, для `#` — нет
    (`FORM_REF_BLOCKS`). Класс цели называет выгрузка (`config`); без неё в отчёте сказано, что класс не назван.
    """
    letter = block.get(PATTERN_KIND) if isinstance(block, dict) else None
    if letter in FORM_LETTER_CLASS:
        return edit_block_note(content, FORM_LETTER_CLASS[letter])
    if letter != "#":
        return ""
    value = block.get(TYPE_GUID)
    cls = form_ref_class(config, schema.type_guid(value))
    guid = edit_block_guid(content)
    if cls is not None:
        want = EDIT_BLOCKS[cls]
        if guid == want:
            return ""
        return (f"блок редактирования поля (u3) остался прежним ({guid}), а у полей на реквизит формы — «{CLASS_WORDS[cls]}» — в образцах форм "
                f"стоит {want} ({FORM_REF_BLOCKS}): copy_type его не пересобирает, и принимает ли платформа поле с таким блоком, "
                "не проверялось")
    if guid != EDIT_BLOCKS["string"]:
        return ""
    return (f"блок редактирования поля (u3) — блок СТРОКИ ({guid}), а у полей на реквизит-ссылку формы такого блока не бывает ({FORM_REF_BLOCKS}; "
            "справочник — 8585207b…, документ — 11fe1b25…, перечисление — 30ee7b7c…): copy_type его не пересобирает, класс цели не назван "
            "(выгрузки нет или тип не из неё — `--config`), и открывается ли выбор из такого поля, не проверялось")


# Классы типа, которые бывают у каждого вида элемента, привязанного платформой к реквизиту объекта. Остальные сочетания
# приводят к отказу, который снимается ключом `unverified`.
CLASSES_BY_KIND = {
    "TextBox": ("string", "decimal", "dateTime", "catalog", "document", "enum", "composite"),
    "CheckBox": ("boolean",),
    "ComboBox": ("boolean", "decimal", "string"),
    "Label": ("string", "dateTime", "catalog", "enum"),
}
KIND_NOTES = {
    "TextBox": "строка, число, дата, справочник, документ, перечисление, набор типов; булева нет; составной тип «строка + число + справочник» — только по образцу конструктора",
    "CheckBox": "только булев реквизит",
    "ComboBox": "булево, число, строка",
    "Label": "строка, дата, справочник, перечисление; числа, документа и булева нет",
}
