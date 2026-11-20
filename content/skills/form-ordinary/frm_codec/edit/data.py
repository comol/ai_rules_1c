"""Данные и события: реквизит, привязка, событие.

Часть редактора. Все имена доступны через `frm_codec.edit`."""

import copy
import json

from .. import json0, typed, schema, validate

from .names import (
    ACT_KIND,
    ACT_SPEC,
    ATTR_HEAD,
    ATTR_ID,
    ATTR_LIST,
    ATTR_NAME,
    ATTR_PATTERN,
    BINDINGS,
    BIND_ELEMENT,
    BIND_PATH,
    CONTENT,
    CORPUS_BIND_TYPES,
    CORPUS_EVENT_PAIRS,
    CORPUS_PATTERN_LETTERS,
    CORPUS_STAMP,
    DESCRIPTION,
    DESC_NAME,
    EVENTS,
    EVENT_ACTION,
    EVENT_ITEMS,
    EVENT_KIND,
    EVENT_NAME,
    HANDLER,
    INDEX,
    NAME,
    NAME_BLOCK,
    LS_ITEMS,
    NEXT_ID,
    PATH_STEPS,
    PATTERN_KIND,
    PATTERN_MARK,
    PATTERN_TYPES,
    HTML_EVENT_NOTE,
    ROUND_EVENT_NOTE,
    ROUND_EVENT_PAIRS,
    STEP_VALUE,
    TEXTBOX_PATTERN,
)
from .datatype import STRING_ALLOWED
from .names import PATTERN_LENGTH, html_event
from ..eventwords import ENGLISH_BY_RU, EVENT_WORDS
from .base import EditError, _on_corpus, find_element, set_text
from .platform import (
    CORPUS_CONTROL_EVENT_PAIRS,
    ROUND10_EVENT_PAIRS,
    ROUND5_BIND_TYPE,
    ROUND5_EVENT,
    ROUND5_PATTERN_TYPES,
)
from .elements import _short, _type_words
from .columns import column_control
from .formroot import MAIN_ATTRIBUTE_ID
from . import datapath
from . import datatype
from . import valuesrc


# Выбираемое значение переключателя (поле содержимого элемента); у переключателя без данных — вид `U`.
RADIO_VALUE = "selected_value"


# ── Данные и события: проверено запуском в 1С:Предприятии ──

# Три операции ниже проверены исполнением: кнопка записала значение в реквизит, поле его показало, обработчик
# события сообщил об изменении. Поэтому по умолчанию они не отказывают.
def add_attribute(doc, name, donor=None, pattern=None, unverified=False):
    """Реквизит формы: строка списка с новым id, `next_id` увеличивается.

    Реквизит типа Строка, собранный редактором, конфигуратор показывает на закладке «Реквизиты» (палитра —
    Строка, длина 0), а в 1С:Предприятии в него записывается значение из кода и читается обратно.

    Описатель типа (`pattern`) операция сама не строит: он либо передан готовым, либо берётся у донора —
    реквизита той же формы с нужным типом.

    Форму описателя принимают две, и вторая — старая, сырая (`_pattern_doc`): тип записан позицией,
    `{"mark": "Pattern", "u1": ["S"]}`. Нынешняя форма записывает то же словами —
    `{"mark": "Pattern", "types": [{"kind": "S"}]}`; старая принимается как синоним.

    Тип строки пишется только виденными формами: `{"S"}` и `{"S",длина,X}`. Длина без второго числа дополняется `u2` = 1 с пометкой
    в отчёте (`_complete_string_blocks`); прочие невиденные формы блока типа — отказ.

    Донор задаёт не только тип, но и всю остальную строку. В строке реквизита шесть позиций: имя, id и описатель
    здесь свои, остальные копируются у донора. Донор учитывается при любом способе передачи описателя, потому
    что молча пропущенный параметр хуже отсутствующего.

    `next_id` всегда больше наибольшего id и не переиспользует номера удалённых реквизитов; отсюда берётся номер
    нового.

    `unverified` принимается, но ничего не делает — см. `UNVERIFIED_KEPT`.
    """
    attributes = doc.get("attributes")
    rows = attributes.get(ATTR_LIST) if isinstance(attributes, dict) else None
    items = rows.get("items") if isinstance(rows, dict) else None
    if not isinstance(items, list):
        raise EditError("у формы нет разобранного списка реквизитов — заводить реквизит "
                        "не в чем")
    if not items:
        return _add_first_attribute(attributes, rows, name, donor, pattern)
    if datapath.short_attribute_rows(items):
        raise EditError(f"{datapath.short_rows_words(items)}: реквизит {name!r} такой форме не добавить (копия короткой строки с ключами "
                        "name/pattern не собирается кодеком)")
    if name in [row.get(ATTR_NAME) for row in items]:
        raise EditError(f"реквизит {name!r} у формы уже есть")
    if donor is None:
        source = items[-1]
    else:
        source = next((r for r in items if r.get(ATTR_NAME) == donor), None)
        if source is None:
            known = ", ".join(str(r.get(ATTR_NAME)) for r in items)
            raise EditError(f"реквизита-донора {donor!r} нет; есть: {known}")
    if pattern is None:
        if ATTR_PATTERN not in source:
            raise EditError(
                f"у реквизита {source.get(ATTR_NAME)!r} описателя типа нет вовсе (строка из "
                "пяти позиций), и взять тип у него нечем: назовите "
                "другого донора либо передайте pattern готовым")
        pattern = copy.deepcopy(source[ATTR_PATTERN])
    else:
        pattern = _pattern_doc(pattern)
    string_notes = _complete_string_blocks(pattern, name)
    new_id = attributes.get(NEXT_ID)
    if not isinstance(new_id, int) or isinstance(new_id, bool):
        raise EditError(f"у формы не разобран счётчик {NEXT_ID} — выдать id нового реквизита "
                        "нечем")
    row = copy.deepcopy(source)
    row[ATTR_ID] = [new_id]
    row[ATTR_NAME] = name
    row[ATTR_PATTERN] = pattern
    items.append(row)
    rows["count"] = len(items)
    attributes[NEXT_ID] = new_id + 1
    said = f"реквизит {name!r}, id {new_id}, {NEXT_ID} → {new_id + 1}"
    # Остальные позиции строки (в том числе `u1`) копируются со строки-образца. Смысл `u1` не проверялся (у
    # основного реквизита обработок это 0, у остальных чаще 1), поэтому новый реквизит получает то же значение,
    # что у образца, и отчёт называет образец.
    said += "".join(f"; {note}" for note in string_notes)
    said += (f"; строка скопирована с реквизита {source.get(ATTR_NAME)!r} ({'donor' if donor is not None else 'последняя в списке: donor не назван'}), "
             f"u1 = {row.get('u1')!r} оттуда же")
    types = pattern.get(PATTERN_TYPES) if isinstance(pattern, dict) else None
    if types != ROUND5_PATTERN_TYPES:
        # Буква берётся у первого блока. У составного типа блоков несколько, и число корпуса тогда относится к
        # первому блоку; отчёт об этом говорит (`ON_CORPUS`).
        first = types[0] if isinstance(types, list) and types else None
        letter = first.get(PATTERN_KIND) if isinstance(first, dict) else None
        said += _on_corpus("add_attribute/pattern", f"описатель типа {_short(types)}",
                           CORPUS_PATTERN_LETTERS.get(letter))
    return said


def _names_by_index(doc):
    """Имя элемента (и вложенного: колонки, страницы) по индексу — для слов отказа: `{индекс: имя}` по всему документу формы."""
    found = {}

    def walk(value):
        if isinstance(value, dict):
            index = value.get(INDEX)
            name = (value.get(NAME_BLOCK) or {}).get(NAME) if isinstance(value.get(NAME_BLOCK), dict) else None
            if isinstance(index, int) and not isinstance(index, bool) and isinstance(name, str) and name:
                found.setdefault(index, name)
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(doc.get("form"))
    return found


def _path_refs(value, ident, owner, out, skip):
    """Пути данных (`steps`), у которых первый шаг — реквизит `ident`, вне таблицы привязок: связь по типу поля и тому подобное. `owner` — имя
    ближайшего элемента сверху (для слов отказа)."""
    if isinstance(value, dict):
        block = value.get(NAME_BLOCK)
        if isinstance(block, dict) and isinstance(block.get(NAME), str) and block.get(NAME):
            owner = block[NAME]
        steps = value.get(PATH_STEPS)
        if isinstance(steps, list) and steps and isinstance(steps[0], dict) and steps[0].get(STEP_VALUE) == ident:
            out.append(owner)
        for key, item in value.items():
            if item is not skip:
                _path_refs(item, ident, owner, out, skip)
    elif isinstance(value, list):
        for item in value:
            if item is not skip:
                _path_refs(item, ident, owner, out, skip)


def remove_attribute(doc, name):
    """Убрать реквизит формы: строка списка реквизитов; `next_id` и привязки остаются согласованными. Обратная к `add_attribute`.

    Операция отказывает словами, пока на реквизит что-то ссылается: основной реквизит формы (на нём стоят данные объекта; сначала смена основного —
    не операция редактора); элементы, привязанные к реквизиту (поле, флажок, табличное поле, колонка: названы по именам — снимите элемент
    `remove_element` или привяжите его к другому реквизиту `bind`); связь по типу других полей (путь «Связь по типу» начинается с реквизита) и запись
    списка «Сохраняемые значения» (`set_saved_values` с `remove`). Молча убрать строку, оставив ссылки, значило бы оставить форму, которую платформа
    прочитает иначе.

    Счётчик `next_id` — «последний выданный номер плюс один»: если убирается реквизит с последним выданным номером (`id` + 1 равно `next_id`),
    счётчик возвращается на него — `add_attribute` → `remove_attribute` даёт исходную форму байт в байт (ссылок на номер нигде не осталось: отказ выше).
    Номер из середины ряда счётчик не двигает: оставшиеся ряды не перенумеровываются. Платформой снятие реквизита не проверялось: форма без строки
    реквизита и без записей о нём в образцах есть (это обычная форма с меньшим числом реквизитов), возврат счётчика — наша договорённость о том же файле.
    """
    attributes = doc.get("attributes")
    rows = attributes.get(ATTR_LIST) if isinstance(attributes, dict) else None
    items = rows.get("items") if isinstance(rows, dict) else None
    if not isinstance(items, list):
        raise EditError("у формы нет разобранного списка реквизитов — убирать нечего")
    if datapath.short_attribute_rows(items):
        raise EditError(f"{datapath.short_rows_words(items)}: у такой формы строку реквизита по имени не найти (имён в коротких строках нет)")
    row = next((r for r in items if r.get(ATTR_NAME) == name), None)
    if row is None:
        known = ", ".join(str(r.get(ATTR_NAME)) for r in items) or "реквизитов нет"
        raise EditError(f"реквизита {name!r} у формы нет; есть: {known}")
    ident = datapath._id_of(row)
    if not isinstance(ident, int) or isinstance(ident, bool):
        raise EditError(f"у реквизита {name!r} не разобран номер (`{ATTR_ID}`) — убирать его по номеру нечем")
    head = attributes.get(ATTR_HEAD)
    main = head.get(MAIN_ATTRIBUTE_ID) if isinstance(head, dict) else None
    if ident == main:
        raise EditError(f"{name!r} — основной реквизит формы (номер {ident} назван в `attributes/u0/main_attribute_id`): на нём держатся данные объекта "
                        "и все пути «Объект.…». Операция основной реквизит не убирает; форму без него собирает `new processing --dialog`")
    refusal = []
    names = _names_by_index(doc)
    bound = []
    for binding in datapath.binding_rows(attributes):
        path = binding.get(BIND_PATH)
        steps = path.get(PATH_STEPS) if isinstance(path, dict) else None
        if isinstance(steps, list) and steps and isinstance(steps[0], dict) and steps[0].get(STEP_VALUE) == ident:
            index = binding.get(BIND_ELEMENT)
            bound.append(f"{names.get(index, 'элемент без имени')} (индекс {index})")
    if bound:
        refusal.append(f"к нему привязаны элементы: {', '.join(bound)} (снимите их `remove_element` или привяжите к другому реквизиту `bind`)")
    others = []
    _path_refs(doc.get("form"), ident, None, others, None)
    if others:
        refusal.append("на него ссылается путь «Связь по типу» у элементов: " + ", ".join(sorted({o or 'форма' for o in others}))
                       + " (снимите связь `set_type_link` без `attribute`)")
    saved = (((doc.get("main_attribute") or {}).get("u2") or {}).get("saved_values") or {}).get("items") or []
    for record in saved:
        pair = record.get("u2") if isinstance(record, dict) else None
        if isinstance(pair, list) and len(pair) > 4 and pair[3] == 1 and pair[4] == [ident]:
            refusal.append("он назван в списке «Сохраняемые значения» (снимите запись `set_saved_values` с `remove`)")
            break
    if refusal:
        raise EditError(f"реквизит {name!r} (номер {ident}) убрать нельзя: " + "; ".join(refusal))
    items.remove(row)
    rows["count"] = len(items)
    said = f"реквизит {name!r}, номер {ident}, убран; реквизитов {len(items)}"
    next_id = attributes.get(NEXT_ID)
    if isinstance(next_id, int) and not isinstance(next_id, bool) and next_id == ident + 1:
        attributes[NEXT_ID] = ident
        said += f"; {NEXT_ID} {next_id} → {ident} (убран последний выданный номер, ссылок на него нет)"
    else:
        said += f"; {NEXT_ID} остаётся {next_id} (убранный номер не последний выданный: прочие реквизиты не перенумеровываются)"
    return said


# Первый реквизит формы, у которой реквизитов нет (заготовка-диалог `new processing --dialog`: `main_attribute_id` −1, список пуст). Строки-образца
# нет, и строка собирается по самому частому виду строки реквизита формы без основного реквизита: `u1` = 1, `u2` = 0, `u3` = 1 (у большинства
# таких строк снимка форм; почти все остальные — `u1` = 0, `u3` = 1). Смысл позиций не проверялся.
FIRST_ROW = {"u1": 1, "u2": 0, "u3": 1}


def _add_first_attribute(attributes, rows, name, donor, pattern):
    """`add_attribute` у формы с пустым списком реквизитов: донора нет, описатель типа обязателен и передаётся готовым."""
    if donor is not None:
        raise EditError(f"реквизита-донора {donor!r} нет: у формы реквизитов нет вовсе (заготовка внешней обработки, диалог). "
                        "Назовите тип описателем (pattern) без донора")
    if pattern is None:
        raise EditError("у формы реквизитов нет вовсе, и взять тип у донора нечем: передайте pattern готовым "
                        "(`{\"mark\": \"Pattern\", \"types\": [{\"kind\": \"S\"}]}` — строка)")
    pattern = _pattern_doc(pattern)
    string_notes = _complete_string_blocks(pattern, name)
    new_id = attributes.get(NEXT_ID)
    if not isinstance(new_id, int) or isinstance(new_id, bool):
        raise EditError(f"у формы не разобран счётчик {NEXT_ID} — выдать id нового реквизита нечем")
    row = {ATTR_ID: [new_id], **copy.deepcopy(FIRST_ROW), ATTR_NAME: name, ATTR_PATTERN: pattern}
    rows["items"].append(row)
    rows["count"] = len(rows["items"])
    attributes[NEXT_ID] = new_id + 1
    said = (f"реквизит {name!r}, id {new_id}, {NEXT_ID} → {new_id + 1}; первый реквизит формы: строки-образца нет, строка собрана по частому "
            f"виду корпуса (u1 = {FIRST_ROW['u1']}, u2 = {FIRST_ROW['u2']}, u3 = {FIRST_ROW['u3']})")
    said += "".join(f"; {note}" for note in string_notes)
    types = pattern.get(PATTERN_TYPES) if isinstance(pattern, dict) else None
    if types != ROUND5_PATTERN_TYPES:
        first = types[0] if isinstance(types, list) and types else None
        letter = first.get(PATTERN_KIND) if isinstance(first, dict) else None
        said += _on_corpus("add_attribute/pattern", f"описатель типа {_short(types)}", CORPUS_PATTERN_LETTERS.get(letter))
    return said


STRING_ALLOWED_DEFAULT = 1   # самое частое второе число строки с длиной в корпусе: 15 716 из 17 367 блоков `{"S",длина,X}`


def _complete_string_blocks(pattern, name):
    """Блоки типа описателя — только виденными формами. Возвращает фразы для отчёта.

    Строка в корпусе записана двумя формами: `{"S"}` (длины нет) и `{"S",длина,X}`, где X — 1 (15 716 блоков) или 0 (1 651). Формы `{"S",длина}`
    не бывает ни разу, и платформа такой блок не читает («Ошибка формата потока» при открытии формы). Поэтому длина без второго числа
    дополняется X = 1 с пометкой в отчёте; другое X задаётся явно ключом `u2` блока. Остальные блоки с буквой проверяет та же таблица форм, что у
    `validate` (`validate.pattern_shapes`): не виденная корпусом форма — отказ до изменения документа."""
    types = pattern.get(PATTERN_TYPES) if isinstance(pattern, dict) else None
    if not isinstance(types, list):
        return []
    notes = []
    for i, block in enumerate(types):
        if not isinstance(block, dict):
            continue
        if block.get(PATTERN_KIND) == "S" and PATTERN_LENGTH in block and STRING_ALLOWED not in block \
                and set(block) <= {PATTERN_KIND, PATTERN_LENGTH}:
            block[STRING_ALLOWED] = STRING_ALLOWED_DEFAULT
            notes.append(f"строка {block[PATTERN_LENGTH]} без второго числа дополнена {STRING_ALLOWED} = {STRING_ALLOWED_DEFAULT} (виденная форма "
                         f"`{{\"S\",длина,X}}`, X = 1 у 15 716 блоков корпуса, 0 у 1 651; другое задаётся ключом {STRING_ALLOWED})")
        picked = schema.pick_doc("PatternType", block)
        if picked is None:
            continue
        problems = []
        validate._check_shape_seen(block, picked, ("pattern", PATTERN_TYPES, i), problems)
        if problems:
            raise EditError(f"реквизит {name!r}: {problems[0].text}")
    return notes


RADIO_VALUE_EXAMPLE = '{"kind": "N", "value": 1}'
RADIO_VALUE_LETTERS = {"N": ("Число", lambda v: isinstance(v, int) and not isinstance(v, bool)),
                       "S": ("Строка", lambda v: isinstance(v, str)),
                       "B": ("Булево", lambda v: isinstance(v, bool))}


def _radio_head(place):
    """Первый переключатель группы, к которой принадлежит `place`: он сам с признаком «первый в группе» либо ближайший перед ним на той же
    странице того же родителя (группа — первый с признаком и все следующие до следующего первого, как её читает досье). `None` — начала
    группы нет."""
    page = place.page
    for item in reversed(place.items[:place.at + 1]):
        if not isinstance(item, dict) or item.get("type") != "RadioButton" or (item.get("coords") or {}).get("page") != page:
            continue
        if (item.get(NAME_BLOCK) or {}).get("first_in_group") is True:
            return item
    return None


def radio_value(doc, element, value):
    """`selected_value` переключателя скаляром: число, строка или булево приводятся к объекту `{"kind": …, "value": …}` по типу реквизита
    группы — описателю типа первого переключателя группы (его задаёт `bind` с `copy_type`). Возвращает `(значение, слова отчёта)`.

    Приводится только однозначное: тип группы Число, Строка или Булево и значение того же вида (`1` при Число — `{"kind": "N", "value": 1}`).
    Без группы с типом, при другом типе (дата, ссылка, составной) и при несовпадении вида значения — отказ словами с примером объекта.
    Готовый объект (`dict`) и не переключатель сюда не приходят: их разбирает общий путь `set_property`."""
    place = find_element(doc, element)
    if place.element.get("type") != "RadioButton":
        return value, ""
    head = place.element if (place.element.get(NAME_BLOCK) or {}).get("first_in_group") is True else _radio_head(place)
    ask = (f"selected_value у {element!r}: голое значение {value!r} приводится к типу реквизита группы, а ")
    if head is None:
        raise EditError(ask + f"начала группы нет (ни у этого переключателя, ни перед ним на странице нет «первый в группе»): поставьте "
                        f"`first_in_group` первому переключателю, привяжите его `bind` с `copy_type` — или пишите значение объектом, например {RADIO_VALUE_EXAMPLE}")
    types = ((head.get(CONTENT) or {}).get(TEXTBOX_PATTERN) or {}).get(PATTERN_TYPES)
    letters = [b.get(PATTERN_KIND) if isinstance(b, dict) else None for b in types] if isinstance(types, list) else []
    head_name = (head.get(NAME_BLOCK) or {}).get(NAME)
    if len(letters) != 1 or letters[0] not in RADIO_VALUE_LETTERS:
        have = ", ".join(map(str, letters)) or "типа нет"
        raise EditError(ask + f"у первого переключателя группы {head_name!r} {have}: скаляр приводится при типе Число, Строка или Булево. "
                        f"Привяжите его `bind` с `copy_type` к реквизиту нужного типа либо пишите значение объектом, например {RADIO_VALUE_EXAMPLE}")
    letter = letters[0]
    word, fits = RADIO_VALUE_LETTERS[letter]
    if not fits(value):
        raise EditError(ask + f"тип группы ({head_name!r}) — {word} ({letter}), а значение другого вида. Для этой группы: "
                        f'{{"kind": "{letter}", "value": {json.dumps(RADIO_SAMPLE[letter], ensure_ascii=False)}}}, скаляр того же вида приводится сам')
    new = {"kind": letter, "value": value}
    return new, f"значение {value!r} приведено к объекту {json.dumps(new, ensure_ascii=False)} по типу группы переключателей ({head_name!r}: {word})"


RADIO_SAMPLE = {"N": 1, "S": "текст", "B": True}


def _short_dates(pattern):
    """Краткая запись состава даты в описателе: `{"kind": "D", "date": "Date|Time|DateTime"}` наравне с `date_fractions` (так же состав
    называет ключ `attributes` описания `generate`). `Date` — буква `D`, `Time` — `T`, `DateTime` — без буквы (платформа не пишет её у
    «даты и времени»). Исходный описатель не меняется; два ключа вместе, не слово из трёх и ключ не у даты — отказ словами."""
    types = pattern.get(PATTERN_TYPES)
    if not isinstance(types, list) or not any(isinstance(b, dict) and "date" in b for b in types):
        return pattern
    from .cowrites import DATE_LETTERS, PATTERN_DATE
    out = copy.deepcopy(pattern)
    for block in out[PATTERN_TYPES]:
        if not isinstance(block, dict) or "date" not in block:
            continue
        if block.get(PATTERN_KIND) != "D":
            raise EditError(f'date — состав даты, он бывает только у блока {{"kind": "D"}}, а блок — {block.get(PATTERN_KIND)!r}')
        word = datatype.date_part(block)           # общий разбор слова и буквы (`datatype.date_part`): тот же, что у колонок таблицы значений и `attributes`
        del block["date"]
        block.pop(PATTERN_DATE, None)
        if DATE_LETTERS[word] is not None:
            block[PATTERN_DATE] = DATE_LETTERS[word]
    return out


def _short_fraction(pattern):
    """`fraction` — синоним `fraction_digits` в блоке числа описателя (так ключ зовётся у `generate.attributes` и колонок).
    Оба ключа с разными значениями, а также `fraction` не у числа — отказ словами. Исходный описатель не меняется."""
    types = pattern.get(PATTERN_TYPES)
    if not isinstance(types, list) or not any(isinstance(b, dict) and "fraction" in b for b in types):
        return pattern
    out = copy.deepcopy(pattern)
    for block in out[PATTERN_TYPES]:
        if not isinstance(block, dict) or "fraction" not in block:
            continue
        value = block.pop("fraction")
        if block.get(PATTERN_KIND) != "N":
            raise EditError(f'fraction — знаки после запятой, они бывают только у блока {{"kind": "N"}}, а блок — {block.get(PATTERN_KIND)!r}')
        if "fraction_digits" in block and block["fraction_digits"] != value:
            raise EditError(f"знаки после запятой названы дважды разно: fraction ({value!r}) и fraction_digits ({block['fraction_digits']!r}) — оставьте один ключ")
        block["fraction_digits"] = value
    return out


def _named_types(pattern):
    """Имена типов платформы в блоках описателя: `{"kind": "ValueTable"}` и `{"kind": "#", "value_type": {"guid": …}}` с известным
    GUID — это `{"kind": "#", "value_type": "ValueTable"}`, как отдаёт `decode`. Правится на месте и возвращается тот же объект, как и остальное в `_pattern_doc`; блоки других типов остаются как есть."""
    types = pattern.get(PATTERN_TYPES) if isinstance(pattern, dict) else None
    if not isinstance(types, list):
        return pattern
    table = schema.GUID_NAMES["AttributeType"]
    by_guid = {guid: name for name, guid in table.items()}
    out = pattern
    for block in out[PATTERN_TYPES]:
        if not isinstance(block, dict):
            continue
        letter = block.get(PATTERN_KIND)
        if isinstance(letter, str) and letter not in table and schema.pick_doc("PatternType", block) is None:
            raise EditError(f"тип {letter!r} в описателе карта не знает: буквы типа — S (строка), N (число), D (дата), B (булево), # (ссылка на объект или "
                            f"тип платформы); типы платформы без квалификаторов называются по имени — {', '.join(table)}")
        if letter in table:
            if set(block) != {PATTERN_KIND}:
                raise EditError(f"у типа {letter!r} квалификаторов нет, а в блоке есть ещё {sorted(set(block) - {PATTERN_KIND})}")
            block["value_type"] = letter
            block[PATTERN_KIND] = "#"
        elif letter == "#":
            value = block.get("value_type")
            if isinstance(value, dict) and set(value) == {"guid"} and value["guid"] in by_guid:
                block["value_type"] = by_guid[value["guid"]]
            elif isinstance(value, str) and value not in table:
                raise EditError(f"у типа {value!r} имени в карте нет: именем пишут {', '.join(table)}, любой другой тип платформы или объекта — "
                                "обёрткой {\"guid\": \"…\"}")
    return out


def _pattern_doc(pattern):
    """Описатель типа в нынешней форме; старая, сырая форма принимается как синоним.

    Старая — `{"mark": "Pattern", "u1": ["S"], "u2": …}`, новая — `{"mark": "Pattern", "types": [{"kind":
    "S"}]}`. Перевод выполняется не разбором ключей вручную, а через уровень 0: старая запись — тот же блок,
    записанный позициями. Из неё строится дерево, и карта читает его как обычно, поэтому синоним не может
    разойтись с разбором.

    Формы различает ключ `types`: у новой он есть всегда (у произвольного типа — пустой список), у старой его
    нет.
    """
    if not isinstance(pattern, dict):
        return pattern
    if PATTERN_TYPES in pattern:
        return _named_types(_short_dates(_short_fraction(pattern)))
    stale = sorted((int(key[1:]), key) for key in pattern
                   if key.startswith("u") and key[1:].isdigit())
    if not stale:
        return pattern
    raw = [pattern.get(PATTERN_MARK)] + [pattern[key] for _at, key in stale]
    try:
        return _named_types(typed.decode(json0.encode0(raw, ()), "Pattern"))
    except ValueError as e:
        raise EditError(f"описатель типа записан позициями ({', '.join(k for _a, k in stale)}), "
                        "и прочитать его как описатель не вышло: "
                        f"{e}. Нынешняя форма — "
                        '{"mark": "Pattern", "types": [{"kind": "S"}]}')


def _attribute_type(place, row, name):
    """Тип поля по реквизиту формы для `bind(copy_type=True)`: `(блок, зеркало)` у поля ввода либо `None` у флажка
    (его вид и есть тип). Всё остальное — отказ со словами до изменения документа."""
    kind = place.element.get("type")
    pattern = row.get(ATTR_PATTERN)
    types = pattern.get(PATTERN_TYPES) if isinstance(pattern, dict) else None
    letters = [b.get(PATTERN_KIND) if isinstance(b, dict) else None for b in types] if isinstance(types, list) else None
    if kind == "CheckBox":
        if letters != ["B"]:
            raise EditError(f"флажок привязывается к булеву реквизиту, а у реквизита формы {name!r} описатель {letters}")
        return None
    if kind == "RadioButton":
        if letters != ["N"]:
            raise EditError(f"первый переключатель группы повторяет тип реквизита формы; проверено Число, а у реквизита {name!r} "
                            f"описатель {letters or 'пустой'}: значение переключателя по умолчанию для других типов не проверялось")
        return copy.deepcopy(types[0]), None
    if kind != "TextBox":
        raise EditError(f"copy_type: тип по реквизиту формы переносится в поле ввода (TextBox), флажок (CheckBox) и "
                        f"переключатель (RadioButton), а у элемента вид {kind}")
    if not letters or len(letters) != 1 or letters[0] not in datatype.FORM_ATTRIBUTE_LETTERS:
        raise EditError(f"у реквизита формы {name!r} описатель типа {letters or 'пустой'}: поле ввода повторяет одиночный блок "
                        f"{', '.join(datatype.FORM_ATTRIBUTE_LETTERS)} (составной тип и прочие буквы зеркало квалификаторов не проверялось)")
    block = copy.deepcopy(types[0])
    datatype.textbox_type_places(place.element.get(CONTENT), f"поля {place.element.get('type')}")
    return block, datatype.block_mirror(block)


def bind(doc, element=None, attribute=None, unverified=False, data=None, table=None,
         column=None, config=None, form_use=None, replace=False, copy_type=False):
    """Привязка данных: строка «элемент → реквизит» в таблице привязок.

    Платформа проверяла привязку поля ввода к реквизиту формы: палитра показывает Данные, а при исполнении поле
    показывает значение, записанное кодом.

    Для элемента другого вида привязка подтверждена корпусом, но только если корпус этот вид содержит. Привязки
    в корпусе есть у десяти видов (`CORPUS_BIND_TYPES`); у остальных (кнопка, панель, рамка группы) их нет.
    Такую привязку уровень 1 пропускает, но ни платформа, ни корпус её не подтверждают, поэтому это отказ, а не
    пометка. Отказ снимает `unverified=True`; тогда отчёт говорит «корпус такого не видел ни разу».

    Привязка называет элемент индексом, а реквизит — его id. Путь в привязке счётный, и здесь записывается путь
    из одного шага. В корпусе встречаются пути длиннее (два, три, четыре, пять шагов). Двухшаговые пути строит
    только `data=` (реквизит объекта, стандартный реквизит, табличная часть). Что означают остальные длинные
    пути, не проверялось, и операция их не строит.

    `unverified` здесь действует — см. `UNVERIFIED_KEPT`.

    У диаграммы `Chart` обработчик лежит внутри тела записи, и пишет его `chartrows.set_event`: имя события — русское, из палитры
    (`Выбор`, `ОбработкаРасшифровки`, `ПриАктивизации`, `ПриРедактированииЗначения`), запись встаёт на место по коду 0…3.

    Путь по метаданным задают ключи `data`, `table` + `column` и `config`. `attribute` называет реквизит формы,
    а `data` — реквизит объекта конфигурации в том виде, как его пишут в коде: `"Объект.Артикул"`, стандартный
    `"Объект.Код"`, табличная часть `"Объект.Штрихкоды"` (у табличного поля). Для колонки задаются `table` (имя
    табличного поля), `column` (имя колонки) и `data="Объект.Штрихкоды.Штрихкод"` (`...НомерСтроки` — номер
    строки). Колонка берёт реквизит той же табличной части, что и таблица, а путь записывается в саму колонку, а
    не в таблицу привязок. Объект находится по типу основного реквизита формы в выгрузке `config` (`frm_json.py
    edit --config КАТАЛОГ`); правило и его границы описаны в `frm_codec/edit/datapath.py`. Нужно указать ровно
    одно из `attribute` и `data`. `form_use` принимает `"item"` или `"folder"` — форма элемента или форма группы
    у справочника с группами (реквизиты и табличные части содержат `Use`). Без `form_use` отказ выдаётся только
    тогда, когда выбранный реквизит относится к одной из этих двух форм. `form_use` и `config` без `data` (для
    формы — `attribute=`) — отказ.

    `data=` записывает и тип. У поля ввода записываются описатель типа и зеркало квалификаторов по реквизиту
    (`frm_codec/edit/datatype.py`: строка, число, дата, ссылка на справочник, документ, перечисление); у табличного
    поля на табличную часть — тип значения поля, `TypeId` части по выгрузке (с нулевым или чужим типом платформа
    выбрасывает колонки таблицы; части без `TypeId` — отказ, `unverified` пишет только путь); у колонки
    табличной части — тип колонки и тип её вложенного поля ввода. Составной тип, набор типов, ссылка на объект
    вне выгрузки и сочетание «вид элемента + класс типа», которое не проверялось, дают отказ, снимаемый
    `unverified` (с ним записывается только путь, а отчёт сообщает, что тип остался прежним). Таблица
    привязывается к табличной части, только если все её колонки принадлежат этой табличной части. `replace=True`
    для колонки заменяет уже заданный путь (и тип).

    `copy_type=True` вместе с `attribute=`: поле ввода (`TextBox`) получает тип реквизита формы — описатель и
    зеркало квалификаторов (так же, как `data=` берёт их у реквизита объекта; `attribute=` без этого ключа тип
    не меняет). Платформа делает описатель поля равным описателю реквизита; зеркало вычисляет
    `edit.datatype.block_mirror` (у части полей длину задал человек в палитре; число без квалификаторов —
    отказ). Поддерживаются одиночные блоки `S`, `N`, `D`, `#`; составной тип, пустой описатель и остальные буквы
    дают отказ со словами (зеркало для них не проверялось). У `CheckBox` описателя нет, поэтому реквизит должен
    быть булевым (`B`); для остальных видов элементов ключ — отказ. Без `attribute` ключ — тоже отказ.

    Новая строка таблицы привязок встаёт на место по номеру элемента: во всех формах корпуса с двумя и более
    привязками строки идут по возрастанию номера.
    """
    if column is not None or table is not None:
        if column is None or table is None or data is None or element is not None \
                or attribute is not None:
            raise EditError("привязка колонки — table, column и data, и больше ничего: у колонки "
                            "нет элемента и реквизита формы (`element`, `attribute`)")
        return datapath.bind_column(doc, table, column, data, config, unverified, form_use, replace)
    if replace:
        raise EditError("replace — замена пути данных КОЛОНКИ (table, column, data): у элемента привязка "
                        "уже есть — отказ, второй платформа не писала ни разу")
    if element is None:
        raise EditError("не назван элемент (element); привязка колонки — table и column")
    if (attribute is None) == (data is None):
        raise EditError("ровно одно из двух: attribute — реквизит формы, data — путь по "
                        "метаданным («Объект.Реквизит»)")
    if data is None and (config is not None and not copy_type or form_use is not None):
        raise EditError("config и form_use нужны только пути по метаданным (data): у реквизита формы "
                        "(attribute) форм элемента и группы нет (config рядом с attribute допустим только с copy_type: он называет класс "
                        "ссылки для слов о блоке редактирования)")
    if copy_type and attribute is None:
        raise EditError("copy_type — тип поля берётся у реквизита ФОРМЫ (attribute); у пути по метаданным (data) тип пишет сам bind")
    place = find_element(doc, element)
    kind = place.element.get("type")
    seen = CORPUS_BIND_TYPES.get(kind)
    if seen is None and not unverified:
        known = ", ".join(sorted(CORPUS_BIND_TYPES, key=lambda name: -CORPUS_BIND_TYPES[name]))
        raise EditError(
            f"привязки данных у элемента вида {kind} в образцах форм нет ни одной: они есть только у "
            f"десяти видов — {known}. Платформа проверяла "
            "привязку поля ввода, то есть такую форму не подтверждает ни платформа, ни корпус. "
            "Уровень 1 её пропустит, и файл соберётся, — а что покажет палитра, не знает никто. "
            "Позвать всё же можно — unverified=True, — и тогда результат проверяете вы")
    attributes = doc.get("attributes")
    plan, copied, form_row = None, None, None
    source_words = ""
    if data is not None:
        plan = datapath.element_steps(doc, data, place, config, unverified, f"{data!r}", form_use)
        steps = plan.steps
        target = f"{data} ({plan.said})"
    else:
        rows = attributes.get(ATTR_LIST) if isinstance(attributes, dict) else None
        items = rows.get("items") if isinstance(rows, dict) else []
        found = [row for row in items if row.get(ATTR_NAME) == attribute]
        if not found:
            known = ", ".join(str(r.get(ATTR_NAME)) for r in items) or "—"
            raise EditError(f"реквизита {attribute!r} у формы нет; есть: {known}")
        value = found[0].get(ATTR_ID)
        attr_id = value[0] if isinstance(value, list) and value else None
        steps = [{STEP_VALUE: attr_id}]
        form_row = found[0]
        target = f"{attribute} (id {attr_id})"
        if copy_type:
            copied = _attribute_type(place, found[0], attribute)
    bindings = attributes.get(BINDINGS)
    if not isinstance(bindings, dict) or not isinstance(bindings.get("items"), list):
        raise EditError("у формы не разобрана таблица привязок данных")
    datapath.binding_rows(attributes)
    for row in bindings["items"]:
        if row.get(BIND_ELEMENT) == place.index:
            raise EditError(f"у элемента {element!r} привязка данных уже есть — "
                            "второй платформа не писала ни разу")
    if form_row is not None and not copy_type:
        source_words = valuesrc.on_bind(doc, place, form_row, attribute, unverified)   # тип платформы у реквизита: таблица, дерево, список значений
    new = {BIND_ELEMENT: place.index, BIND_PATH: {PATH_STEPS: steps}}
    # Место по номеру элемента: в корпусе порядок соблюдается без исключений (см. выше).
    at = next((i for i, row in enumerate(bindings["items"])
               if isinstance(row.get(BIND_ELEMENT), int) and row[BIND_ELEMENT] > place.index),
              len(bindings["items"]))
    bindings["items"].insert(at, new)
    said = f"привязка: {element} (#{place.index}) → {target}{source_words}"
    if data is None and copy_type and kind == "RadioButton":
        content = place.element.get(CONTENT)
        was = _type_words(content.get(TEXTBOX_PATTERN))
        content[TEXTBOX_PATTERN][PATTERN_TYPES] = [copied[0]]
        value = content.get(RADIO_VALUE)
        if isinstance(value, dict) and value.get("kind") == "U":
            content[RADIO_VALUE] = {"kind": "N", "value": 0}
            said += "; выбираемое значение U → Число 0 (так записывает платформа у первого переключателя группы)"
        said += f"; тип переключателя: {was} → {_type_words(content.get(TEXTBOX_PATTERN))} (по реквизиту формы {attribute!r})"
    elif data is None and copy_type and copied is not None:
        was = datatype.current_type_words(place.element.get(CONTENT))
        datatype.set_textbox_type(place.element.get(CONTENT), copied[0], copied[1], f"поля {element!r}")
        said += f"; тип поля: {was} → {datatype.current_type_words(place.element.get(CONTENT))} (по реквизиту формы {attribute!r})"
        note = datatype.form_attribute_block_note(place.element.get(CONTENT), copied[0], datapath.load_config(config) if config else None)
        said += f"; {note}" if note else ""
    if plan is not None:
        said += datapath.apply_type(place, plan, data)
        said += "".join(f"; {n}" for n in plan.notes)
        said += datapath.corpus_words(kind, plan.path_kind)
    elif kind != ROUND5_BIND_TYPE:
        said += _on_corpus("bind/element", f"элемент вида {kind}", seen)
    return said


GEO_EVENTS_HOLDER = "u3"


def kind_event_words(kind):
    """События вида по карте словами: `Click (Нажатие), …`; пусто, если у вида перечня событий нет."""
    enum = schema.ENUMS.get(f"{kind}.Event")
    if enum is None:
        return ""
    return ", ".join(f"{name} ({EVENT_WORDS[name]})" if name in EVENT_WORDS else str(name) for name in enum.codes)


def event_english(kind, event):
    """Русское имя события палитры («Нажатие») → имя карты (`Click`), если у вида такое событие есть. Английское имя, число и всё
    неизвестное возвращаются как пришли; русское имя, которого у вида нет, — отказ со списком событий вида."""
    if not isinstance(event, str) or event not in ENGLISH_BY_RU:
        return event
    found = ENGLISH_BY_RU[event]
    enum = schema.ENUMS.get(f"{kind}.Event")
    if enum is None:
        return event       # диаграммы и поле HTML-документа называют события по-своему (русские имена палитры без английских)
    if found in enum.codes:
        return found
    have = kind_event_words(kind)
    raise EditError(f"события «{event}» ({found}) у вида {kind} нет; события вида по карте: {have}")


def set_event(doc, element, event, procedure=None, text=None, unverified=False, column=None,
              nested=False, remove=False):
    """Обработчик события элемента: процедура модуля; `remove=True` снимает обработчик (запись события уходит из списка, процедура в модуле остаётся).

    Пустое имя процедуры (`""`) — отказ: платформа пустое имя не проверяла, а запись с пустым именем читалась бы как «обработчик без процедуры».
    Снять обработчик — `remove=true` без `procedure` и `text`. Снятие у диаграмм (Диаграмма, Ганта, Дендрограмма, Сводная) операция не делает.

    Место другое, чем у кнопки панели: у элемента это список событий в его содержимом, у кнопки — запись
    действия в панели. Сам блок действия одинаков (`EventAction`), и вид действия-процедуры в обоих случаях
    задаётся одним GUID.

    Платформа проверяла `OnChange` у поля ввода: палитра показывает ПриИзменении = `ПолеJSONПриИзменении`, лупа
    приводит в процедуру модуля, а при исполнении ввод в поле выводит сообщение из обработчика.

    Остальные пары «тип + событие» подтверждены корпусом, но только те, которые в нём есть
    (`CORPUS_EVENT_PAIRS`). По карте допустимы 92 пары; 39 из них в корпусе не встречаются — 13 у самой формы
    (операция правит элементы и к форме не обращается) и 26 у элементов. Из этих 26 платформа приняла семнадцать
    (см. ниже), а девять остаются отказом: пять у табличного поля (`TableBox.BeforeCollapse` и соседние) и
    четыре у схем. Пару, которой нет в корпусе, операция отвергает. Так же отвергается пара, которой нет и в
    карте (`TextBox.Click`). Отказ снимает `unverified=True`.

    Семнадцать пар, которых нет в корпусе, платформа приняла (`ROUND_EVENT_PAIRS`). Для них отчёт пишет
    «проверено — принято платформой, обработчик вызывается в предприятии» и добавляет условие, без которого
    обработчик не вызывается (разрешено перетаскивание у элемента, кнопка регулирования; у поля календаря и поля
    картинки — ещё и проверка приёмника, разрешившая действие; поле табличного документа принимает бросок
    стандартной обработкой даже при пустой проверке). `unverified` для них принимается и ничего не меняет.

    Новая запись встаёт на своё место по коду события, а не в конец: при пересохранении платформа переставляет
    записи по возрастанию кода (`Tuning` (4) перед `Opening` (5)). В корпусе это правило соблюдается без
    исключений: во всех списках обработчиков с несколькими записями коды строго возрастают. Существующая запись
    при замене остаётся на своём месте.

    `unverified` здесь действует — см. `UNVERIFIED_KEPT`.

    `column` + `nested=True` — обработчик вложенного элемента колонки. У самой колонки событий нет (в её палитре
    нет группы «События»), а у вложенного элемента, редактирующего ячейку, есть свои девять. Список событий там
    — тот же узел, что у элемента формы, и правило размещения по коду то же. Граница по корпусу своя: пары
    вложенных элементов (`CORPUS_CONTROL_EVENT_PAIRS`, тринадцать пар). Пара, которой там нет, — отказ,
    снимаемый `unverified=True`; результаты проверки семнадцати пар элементов формы сюда не переносятся.

    Две пары вложенных элементов проверены платформой (`ROUND10_EVENT_PAIRS`), и отчёт об этом сообщает.
    ПриИзменении вложенного поля ввода вызывается в 1С:Предприятии. У вложенного поля выбора (колонка с числом)
    платформа обработчик приняла (палитра, лупа, модуль), но в предприятии он не вызывается: ввод числа с
    клавиатуры поле выбора не принимает, как и поле выбора той же колонки, созданное платформой. Остальные пары
    помечаются «стоит на корпусе».
    """
    place = find_element(doc, element)
    kind = place.element.get("type")
    if remove:
        if procedure is not None or text is not None:
            raise EditError("remove=true снимает обработчик, а procedure и text называют новый: это две разные правки — "
                            "снимите обработчик одним вызовом, поставьте другим")
    elif procedure is None:
        raise EditError(f"set_event у {element!r}: назовите процедуру модуля (procedure); чтобы снять обработчик, передайте remove=true")
    elif not isinstance(procedure, str) or not procedure:
        raise EditError(f"set_event у {element!r}: имя процедуры — непустая строка, а пришло {procedure!r}; "
                        "чтобы снять обработчик, передайте remove=true — пустое имя обработчик не снимает")
    if nested or column is not None:
        if not (nested and column is not None):
            raise EditError("обработчик вложенного элемента колонки адресуют ДВУМЯ параметрами — "
                            "column (какая колонка) и nested=true (её вложенный элемент): у "
                            "самой колонки событий нет, и один column был бы адресом в никуда")
        _head, kind, content = column_control(doc, element, column)
        event = event_english(kind, event)
        who = f"{element}/{column} (вложенный {kind})"
        seen = CORPUS_CONTROL_EVENT_PAIRS.get((kind, event))
        if seen is None and not unverified:
            known = ", ".join(sorted(name for other, name in CORPUS_CONTROL_EVENT_PAIRS
                                     if other == kind))
            raise EditError(
                f"обработчика {kind}.{event} у вложенного элемента колонки в образцах форм нет: у {kind} "
                + (f"встречались только {known}" if known else "их нет вовсе")
                + ". Позвать всё же можно — unverified=True")
        accepted = ROUND10_EVENT_PAIRS.get((kind, event))
        tail = (f"; пара {kind}.{event}: {accepted}" if accepted
                else _on_corpus("set_event/control", f"пара {kind}.{event}", seen))
        if remove:
            return _drop_event(content, kind, event, who, f"вложенного элемента колонки {column!r}")
        return _put_event(content, kind, event, procedure, text, who, tail,
                          f"вложенного элемента колонки {column!r}")
    event = event_english(kind, event)     # русское имя палитры («Нажатие») принимается наравне с английским (`Click`)
    from .. import diagrams as _diagrams
    if remove and (kind == "Chart" or kind in _diagrams.KINDS):
        raise EditError(f"set_event remove: у элемента {element!r} ({kind}) обработчики лежат внутри тела диаграммы, и снятие записи оттуда операция не делает "
                        "— диаграмма снимает их только заменой; уберите событие в конфигураторе")
    if kind == "HTMLDocumentField":
        return _set_html_event(place, element, event, procedure, text, remove)
    if kind == "GeographicalSchemaField" and event in GEO_OTHER_EVENT:
        return _set_geo_other_event(place, element, procedure, text, remove)
    if kind == "Chart":
        from .. import chartrows as _chartrows
        return _chartrows.set_event(doc, element, event, procedure, text)
    if kind in _diagrams.KINDS:
        from .. import kindrows as _kindrows
        return _kindrows.set_event(doc, element, event, procedure, text)
    if remove:
        holder = place.element.get(GEO_EVENTS_HOLDER) if kind == "GeographicalSchemaField" else place.element.get(CONTENT)
        return _drop_event(holder or {}, kind, event, element, f"элемента {element!r} ({kind})")
    seen = CORPUS_EVENT_PAIRS.get((kind, event))
    accepted = ROUND_EVENT_PAIRS.get((kind, event))
    if seen is None and accepted is None and not unverified:
        known = ", ".join(sorted(name for other, name in CORPUS_EVENT_PAIRS if other == kind))
        rounds = ", ".join(sorted(name for other, name in ROUND_EVENT_PAIRS if other == kind))
        raise EditError(
            f"обработчика события {kind}.{event} в образцах форм нет: у элементов вида {kind} встречались "
            + (f"только {known}" if known else "никакие")
            + (f"; по карте у вида {kind} события: {kind_event_words(kind)}" if kind_event_words(kind) else "")
            + (f"; платформа сверх того проверила запуском {rounds}" if rounds else "")
            + ". Платформа проверяла TextBox.OnChange и семнадцать невиданных корпусом "
            "пар четырёх типов — эту пару не проверял никто, то есть "
            "такую форму не подтверждает ни платформа, ни корпус. Позвать всё же можно — "
            "unverified=True, — и тогда результат проверяете вы. Если события с таким именем у этого "
            "элемента не бывает вовсе, сборка отвергнет его и отдельно — перечислением карты")
    if (kind, event) == ROUND5_EVENT:
        tail = ""
    elif seen is None and accepted is not None:
        _round, condition = accepted
        tail = f"; пара {kind}.{event}: {ROUND_EVENT_NOTE}" + (f"; {condition}" if condition
                                                               else "")
    else:
        tail = _on_corpus("set_event/handler", f"пара {kind}.{event}", seen)
    # У поля географической схемы список обработчиков лежит не в содержимом, а в блоке записи элемента (позиция 3, `u3`).
    holder = place.element.get(GEO_EVENTS_HOLDER) if kind == "GeographicalSchemaField" else place.element.get(CONTENT)
    return _put_event(holder or {}, kind, event, procedure, text, element,
                      tail, f"элемента {element!r} ({kind})")


# Безымянная строка группы «Другие» в палитре поля географической схемы: лупа создаёт в модуле процедуру `<имя элемента>(Элемент)` без суффикса события, а
# в списке обработчиков появляется запись с кодом 2. Имени у события нет ни в палитре, ни в справочнике, поэтому его называют `Unnamed` либо числом 2.
GEO_OTHER_EVENT = ("Unnamed", 2)
GEO_OTHER_EVENT_CODE = 2
GEO_OTHER_EVENT_NOTE = ("принято платформой — безымянная строка группы «Другие»: лупа создала процедуру с именем элемента и параметром `Элемент`, запись "
                        "легла в список с кодом 2; вызов обработчика в предприятии не проверялся, имени у события платформа не показывает")


def _set_geo_other_event(place, element, procedure, text, remove=False):
    """Обработчик безымянного события поля географической схемы (код 2 в списке записи элемента `u3`)."""
    from ..chartrows import humanize
    if remove:
        return _drop_event(place.element.get(GEO_EVENTS_HOLDER) or {}, "GeographicalSchemaField", GEO_OTHER_EVENT_CODE, element,
                           f"элемента {element!r} (GeographicalSchemaField)", "Unnamed")
    if not isinstance(procedure, str) or not procedure:
        raise EditError(f"set_event у {element!r}: имя процедуры — непустая строка, а пришло {procedure!r}")
    # Описание — имя процедуры словами, как его пишет платформа: подчёркивание — пробел, регистр частей между подчёркиваниями остаётся (`Geo_Е` → `Geo Е`).
    text = text if text is not None else " ".join(humanize(part) for part in procedure.split("_"))
    return _put_event(place.element.get(GEO_EVENTS_HOLDER) or {}, "GeographicalSchemaField", GEO_OTHER_EVENT_CODE, procedure, text, element,
                      f"; событие Unnamed: {GEO_OTHER_EVENT_NOTE}", f"элемента {element!r} (GeographicalSchemaField)", "Unnamed")


def _set_html_event(place, element, event, procedure, text, remove=False):
    """Обработчик события поля HTML-документа: 63 события палитры, у каждого свой код в файле.

    `DocumentComplete` платформа пишет именем, остальные 62 — числами 1…62 в порядке строк палитры (`html_event`). Все 63
    записи платформа приняла; `unverified` для этого поля ничего не меняет, а событие вне палитры — отказ без обхода: у
    него не может быть кода."""
    found = html_event(event)
    if found is None:
        raise EditError(f"у поля HTML-документа события {event!r} нет: 63 события палитры — ДокументСформирован "
                        "(DocumentComplete) и 62 события от onhelp до onresize (имя из палитры, например onclick, "
                        "или число 1…62 по порядку строк; в палитре «onproperychange» без «t»)")
    stored, label = found
    if remove:
        return _drop_event(place.element.get(CONTENT) or {}, "HTMLDocumentField", stored, element,
                           f"элемента {element!r} (HTMLDocumentField)", label)
    if label == "DocumentComplete":
        pair = ("HTMLDocumentField", label)
        tail = _on_corpus("set_event/handler", f"пара {pair[0]}.{label}", CORPUS_EVENT_PAIRS[pair])
    else:
        tail = f"; событие {label}: {HTML_EVENT_NOTE}"
    return _put_event(place.element.get(CONTENT) or {}, "HTMLDocumentField", stored, procedure, text, element, tail,
                      f"элемента {element!r} (HTMLDocumentField)", label)


def _drop_event(content, kind, event, who, whose, label=None):
    """Снятие обработчика: запись события уходит из списка содержимого, счётчик пересчитывается; процедура в модуле остаётся.

    Запись ищется по имени (коду) события, как при замене. Другие записи не двигаются. Платформа снятие не проверяла."""
    block = content.get(EVENTS)
    items = block.get(EVENT_ITEMS) if isinstance(block, dict) else None
    if not isinstance(items, list):
        raise EditError(f"у {whose} не разобран список событий")
    at = next((i for i, row in enumerate(items) if isinstance(row, dict) and row.get(EVENT_NAME) == event), None)
    if at is None:
        have = ", ".join(str(row.get(EVENT_NAME)) for row in items if isinstance(row, dict)) or "—"
        raise EditError(f"обработчика события {label or event} у {whose} нет; в списке: {have}")
    was = items[at].get(EVENT_ACTION, {}).get(HANDLER) if isinstance(items[at].get(EVENT_ACTION), dict) else None
    del items[at]
    block["count"] = len(items)
    seen = CORPUS_EVENT_REMOVE_SEEN
    return (f"{who}: обработчик события {label or event} снят" + (f" (была процедура {was!r})" if was else "")
            + "; процедура в модуле остаётся — уберите её сами" + _on_corpus("set_event/remove", f"событие {label or event}", seen))


CORPUS_EVENT_REMOVE_SEEN = 1


def _put_event(content, kind, event, procedure, text, who, tail, whose, label=None):
    """Запись обработчика в список событий содержимого элемента — на место по коду.

    Одно и то же место используется для элемента формы и для вложенного элемента колонки: список в обоих случаях
    — один и тот же узел, и правило «вставка по коду, замена на месте» одно."""
    from .. import templates
    block = content.get(EVENTS)
    items = block.get(EVENT_ITEMS) if isinstance(block, dict) else None
    if not isinstance(items, list):
        raise EditError(f"у {whose} не разобран список событий")
    sample = templates.action("procedure")
    spec = copy.deepcopy(sample[ACT_SPEC])
    spec[HANDLER] = procedure
    spec[DESCRIPTION][DESC_NAME] = procedure
    for value in spec[DESCRIPTION].values():
        if isinstance(value, dict) and LS_ITEMS in value and text is not None:
            set_text(value, text)
    for row in items:
        if isinstance(row, dict) and row.get(EVENT_NAME) == event:
            row[EVENT_KIND] = copy.deepcopy(sample[ACT_KIND])
            row[EVENT_ACTION] = spec
            return f"{who}: событие {label or event} → процедура {procedure!r} (замена){tail}"
    at = _event_place(kind, items, event)
    items.insert(at, {EVENT_NAME: event, EVENT_KIND: copy.deepcopy(sample[ACT_KIND]),
                      EVENT_ACTION: spec})
    block["count"] = len(items)
    where = "" if at == len(items) - 1 else \
        f", на место по коду — перед {items[at + 1].get(EVENT_NAME)}"
    return f"{who}: событие {label or event} → процедура {procedure!r} (заведено{where}){tail}"


def event_code(kind, event):
    """Код события по перечислению карты `<Тип>.Event`; число возвращается как есть; `None` — код неизвестен.

    Числовые коды бывают у списков без перечисления (`HTMLDocumentField`, события настроек формы): число и есть
    код."""
    if isinstance(event, int) and not isinstance(event, bool):
        return event
    enum = schema.ENUMS.get(f"{kind}.Event")
    return enum.codes.get(event) if enum is not None else None


def _event_place(kind, items, event):
    """Куда вставить новую запись: перед первой записью с большим кодом, иначе в конец.

    Запись с неизвестным кодом (событие, которого нет в перечислении карты) в сравнении не участвует: новая
    запись просто проходит мимо неё, потому что переставлять неизвестное нельзя. Новое событие без кода встаёт в
    конец, и сборка потом отвергнет его по перечислению."""
    code = event_code(kind, event)
    if code is None:
        return len(items)
    for at, row in enumerate(items):
        other = event_code(kind, row.get(EVENT_NAME)) if isinstance(row, dict) else None
        if other is not None and other > code:
            return at
    return len(items)
