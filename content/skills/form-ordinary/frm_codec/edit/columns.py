"""Колонки табличного поля и вложенный элемент колонки. Все имена отдаёт фасад `frm_codec.edit`."""

import copy
import re

from .. import schema, typed, design as _design

from .names import (
    COLUMNS_COUNT,
    COLUMNS_PATH,
    COLUMN_CHECK_PATH,
    COLUMN_CONTROL_AT,
    COLUMN_ORDINALS,
    COLUMN_PICTURE_PATH,
    COLUMN_BODY,
    COLUMN_CHECK_DATA,
    COLUMN_CONTROL,
    COLUMN_CONTROL_TYPE,
    COLUMN_DATA,
    COLUMN_DATA_KEYS,
    COLUMN_HEAD,
    COLUMN_HEADER_TEXT,
    COLUMN_INNER,
    COLUMN_ITEMS,
    COLUMN_LOCATION,
    COLUMN_NAME,
    COLUMN_ORDER,
    COLUMN_TYPE,
    COLUMN_VALUE_TYPE,
    CONTENT,
    CONTROL_ELEMENT,
    CONTROL_KIND,
    CONTROL_KINDS,
    CONTROL_LINKS,
    CORPUS_STAMP,
    EVENT_ITEMS,
    EVENTS,
    LS_COUNT,
    LS_ITEMS,
    LS_MARK,
    NEW_COLUMN,
    PACKED_CONTENT,
    PACKED_EMPTY,
    PATTERN_KIND,
    PATTERN_LENGTH,
    PATTERN_MARK,
    PATTERN_NUMBER,
    PATTERN_TYPES,
    TEXTBOX_LENGTH,
    TEXTBOX_NUMBER,
    TEXTBOX_PATTERN,
    TABLE_SOURCE,
    TABLE_TYPE,
    TABLE_SOURCE_BLOCK,
    TABLE_SOURCE_KIND,
    TEXTBOX_PROPS,
    VALUE_LIST_BASE,
)
from .base import EditError, _on_corpus, find_element, set_text
from .platform import (
    COLUMN_KINDS,
    CORPUS_COLUMN_BARE,
    CORPUS_COLUMN_CONTROLS,
    CORPUS_COLUMN_CONTROL_TYPES,
    ROUND10_COLUMN_CONTROL,
    ROUND10_COLUMN_CONTROL_NOTE,
    VALUE_LIST_CHECK,
    VALUE_LIST_COLUMN,
    VALUE_LIST_ROLES,
    VALUE_TABLE,
    VALUE_TABLE_SOURCES,
)
from .elements import _type_words, _version_check


# ── Колонки табличного поля ───────────────────────────────────────────────────────────────────

def columns_of(node):
    """Держатель колонок табличного поля по адресу карты; `None` — это не табличное поле."""
    value = node.get(CONTENT)
    for key in COLUMNS_PATH:
        value = value.get(key) if isinstance(value, dict) else None
    return value if isinstance(value, dict) and isinstance(value.get(COLUMN_ITEMS), list) \
        else None


def is_value_list_column(column):
    """Колонка списка значений: база без обёртки, голова на уровень ближе."""
    kind = column.get(COLUMN_TYPE) if isinstance(column, dict) else None
    return isinstance(kind, dict) and kind.get("guid") == VALUE_LIST_COLUMN


def _column_base(column):
    """База колонки `{8, голова, ссылка, ссылка, ссылка}`; `None` — строения нет.

    У трёх видов колонки она лежит в обёртке с Данными (`1/1`), у колонки списка значений — на
    позиции 1 сама (два строения в карте `TableBoxColumn`). Узел базы у всех один, и всё, что ниже
    неё, адресуется одинаково.
    """
    if not isinstance(column, dict):
        return None
    if is_value_list_column(column):
        base = column.get(VALUE_LIST_BASE)
    else:
        body = column.get(COLUMN_BODY)
        base = body.get(COLUMN_INNER) if isinstance(body, dict) else None
    return base if isinstance(base, dict) else None


def column_places_missing(column):
    """Чего у колонки нет из четырёх мест, которыми её правят. Пустой список — всё на месте.

    Мест четыре: Данные у самой колонки, имя в её теле, порядковый номер и шапка. У колонки списка
    значений Данных-строки нет по строению: обёртки с ними у неё нет, а Данные лежат в базе ссылкой
    `{номер}`, — и это место числится недостающим, хотя имя, номер и шапка на месте.
    """
    head = (_column_base(column) or {}).get(COLUMN_HEAD)
    if is_value_list_column(column):
        missing = [COLUMN_DATA]
    else:
        body = column.get(COLUMN_BODY) if isinstance(column, dict) else None
        missing = [] if isinstance(body, dict) and any(key in body for key in COLUMN_DATA_KEYS) \
            else [COLUMN_DATA]
    if not isinstance(head, dict):
        return missing + [COLUMN_NAME, COLUMN_ORDER, COLUMN_HEADER_TEXT]
    return missing + [key for key in (COLUMN_NAME, COLUMN_ORDER, COLUMN_HEADER_TEXT)
                      if key not in head]


def _columns_holder(doc, table):
    """Держатель колонок табличного поля — без проверки вида: для правки существующей колонки по имени
    (шрифт колонки, её вложенный элемент). Колонка ищется по имени в голове, а голова у всех четырёх
    видов одна и та же.
    """
    place = find_element(doc, table)
    block = columns_of(place.element)
    if block is None:
        raise EditError(f"у элемента {table!r} ({place.element.get('type')}) колонок нет — "
                        "колонки бывают у табличного поля")
    return block


def _columns_of(doc, table, value_list_ok=False):
    """Держатель колонок вместе с проверкой вида колонки — для операций над списком колонок
    (`add_column`, `remove_column`).

    Колонки бывают четырёх видов (`column_type`): `48a6ebc3-…`, `c2cf1953-…`, `737535a4-…` и
    `fbacf851-…` (список значений). У последнего строение другое: обёртки с Данными нет, база
    колонки лежит на уровень ближе, а Данные лежат в базе ссылкой `{номер}`. Копия донора такой
    колонки ставила бы Данные в место, которого у неё нет, поэтому колонку списка значений заводят и
    убирают отдельные ветки `add_column` и `remove_column` (`value_list_ok=True`; `_add_value_list_column`,
    `_remove_value_list_column`), а остальным вызовам такая колонка — отказ словами.

    Без этой проверки `add_column` с `header` падала бы голым `KeyError` мимо отказов CLI, а без
    `header` отчитывалась бы успехом, дописав в короткое тело два ключа, которых там не бывает, — и
    собрать такой документ было бы нельзя.
    """
    block = _columns_holder(doc, table)
    for at, column in enumerate(block[COLUMN_ITEMS]):
        if not isinstance(column, dict):
            raise EditError(f"колонка {at} у {table!r} — не запись: у колонок корпуса это узел с именем и "
                            "Данными; правленый руками документ?")
        if is_value_list_column(column):
            if value_list_ok:
                if _column_base(column) is None:
                    raise EditError(f"у колонки {at} списка значений у {table!r} нет базы — строение не то, "
                                    "что у колонок корпуса")
                continue
            raise EditError(
                f"колонка {at} у {table!r} ({_column_name(column)!r}) — колонка СПИСКА ЗНАЧЕНИЙ "
                f"(`{VALUE_LIST_COLUMN}`): обёртки с Данными у неё нет, Данные лежат в базе "
                "ссылкой {номер}, и копия такой колонки этой веткой не строится. Колонки списка "
                "значений заводят и убирают add_column и remove_column у таблицы, все колонки "
                "которой — этого вида; вложенный элемент правится (set_column_control, set_font и "
                "set_event с nested=true), шрифты колонки — set_font с column")
        missing = column_places_missing(column)
        if missing:
            guid = (column.get(COLUMN_TYPE) or {}).get("guid") \
                if isinstance(column.get(COLUMN_TYPE), dict) else column.get(COLUMN_TYPE)
            raise EditError(
                f"колонка {at} у {table!r} устроена иначе, чем умеет редактор: у неё нет "
                f"{', '.join(missing)} (вид колонки — {guid}). У колонок с обёрткой "
                "эти места есть всегда — правленый руками документ? Править "
                "такую колонку нечем: копировать её вслепую значило бы собрать файл, которого "
                "платформа не писала")
    return block


def _column_name(column):
    """Имя колонки — из единственного его места (голова, позиция 30), а не из Данных.

    У колонки списка на позиции `1/2` лежит другое свойство — флаг «ОтображатьСтандартнуюКартинку»,
    поэтому имя читается из головы. Голова — у всех видов колонки одна, но у колонки списка значений
    на уровень ближе (`_column_base`).
    """
    head = (_column_base(column) or {}).get(COLUMN_HEAD)
    return head.get(COLUMN_NAME) if isinstance(head, dict) else None


def _column_body(column):
    """Голова колонки: `1/1/1` у колонки с обёрткой, `1/1` у колонки списка значений."""
    base = column[VALUE_LIST_BASE] if is_value_list_column(column) \
        else column[COLUMN_BODY][COLUMN_INNER]
    return base[COLUMN_HEAD]


def table_source_kind(node):
    """Вид источника данных табличного поля (`u3/u1/u0`): число или `None`, если блока источника нет."""
    content = node.get(CONTENT)
    source = content.get(TABLE_SOURCE) if isinstance(content, dict) else None
    block = source.get(TABLE_SOURCE_BLOCK) if isinstance(source, dict) else None
    kind = block.get(TABLE_SOURCE_KIND) if isinstance(block, dict) else None
    return kind if isinstance(kind, int) and not isinstance(kind, bool) else None


def value_list_source_block(pattern=None, flag=0):
    """Источник данных табличного поля со списком значений в том виде, как его пишет платформа (блок `2/3`): GUID источника и
    узел с видом 2, описателем типа элементов списка и флагом. `pattern` — описатель в сырой форме (`["Pattern", ["S"]]`);
    без него — пустой описатель («Тип значения списка» не задан). Функция не операция: таблицу со списком значений редактор
    не заводит, а при сборке формы вручную колонки `fbacf851-…` без этого блока платформа при записи снимает."""
    return {"u0": {"guid": schema.VALUE_LIST_SOURCE},
            "u1": {"u0": schema.VALUE_LIST_SOURCE_KIND, "u1": copy.deepcopy(pattern) if pattern is not None else ["Pattern"],
                   "u2": flag}}


def value_list_source_problem(node):
    """Слова о табличном поле, у которого колонки — колонки списка значений, а источник данных другой; `None`, если колонки
    и источник согласованы (или колонок такого вида нет). Источник — GUID блока `2/3` вместе с видом: у табличной части и
    списка справочника вид тоже 2, различает их только GUID."""
    columns = columns_of(node)
    members = columns.get(COLUMN_ITEMS) if columns is not None else None
    if not members or not all(is_value_list_column(c) for c in members):
        return None
    content = node.get(CONTENT)
    source = content.get(TABLE_SOURCE) if isinstance(content, dict) else None
    if not isinstance(source, dict):
        return "у поля нет блока источника данных"
    guid = (source.get("u0") or {}).get("guid") if isinstance(source.get("u0"), dict) else None
    kind = table_source_kind(node)
    if guid == schema.VALUE_LIST_SOURCE and kind == schema.VALUE_LIST_SOURCE_KIND:
        return None
    return (f"источник данных поля — {guid or 'без GUID'}, вид {kind}, а у поля со списком значений он "
            f"{schema.VALUE_LIST_SOURCE}, вид {schema.VALUE_LIST_SOURCE_KIND}")


def _is_value_list_table(node, members, table):
    """Колонки этого табличного поля — колонки списка значений? Все колонки одного вида: смесь в корпусе не встречается
    (ни у одного поля), и строить ветку по первой колонке значило бы править смесь вслепую. Таблица без колонок — по
    типу значения поля (`СписокЗначений`).
    """
    kinds = [is_value_list_column(c) for c in members]
    if kinds and all(kinds):
        return True
    if any(kinds):
        raise EditError(f"у {table!r} колонки списка значений вперемешку с колонками других видов — в образцах форм так "
                        "не бывает ни у одного поля, и операции над списком колонок такого поля не проверены")
    if members:
        return False
    content = node.get(CONTENT)
    return schema.VALUE_LIST_TYPE in repr(content.get(TABLE_TYPE) if isinstance(content, dict) else None)


def _first_column_location(members, name=None):
    """Первая колонка поля стоит «в новой колонке»: так у всех колонок, стоящих первыми, в образцах форм. После
    снятия первой колонки новой первой может оказаться колонка с другим расположением — тогда расположение
    выправляется, и фраза о нём идёт в отчёт.
    """
    if not members:
        return ""
    head = _column_body(members[0])
    was = head.get(COLUMN_LOCATION)
    if was == NEW_COLUMN:
        return ""
    head[COLUMN_LOCATION] = NEW_COLUMN
    return (f"; колонка {_column_name(members[0])!r} стала первой, её расположение {was} → {NEW_COLUMN}: первая колонка "
            "в образцах форм всегда в новой колонке (платформой не проверялось)")


def add_column(doc, table, name, header=None, donor=None, data=None, config=None, form_use=None,
               unverified=False, template=None):
    """Колонка в табличное поле: копия соседней, своё имя и Данные, свой номер.

    Имя и Данные — разные места: имя колонки в её теле, Данные — отдельно. `data` — Данные новой
    колонки. Умолчание — имя: платформа принимает колонку с Данными, равными имени, и у большинства
    колонок корпуса они равны. Равенство не закон: `data=""` оставляет Данные пустыми,
    `data="Сумма"` ставит своё.

    Данные ставятся только у колонки таблицы значений — там, где они строка. У колонки списка на
    этом месте лежит другое свойство (флаг «ОтображатьСтандартнуюКартинку»), и запись туда строки
    испортила бы флаг. Данные тогда остаются донорскими, а `data` при явном вызове — отказ словами.

    Номер колонки не перенумеровывается ни при добавлении соседей, ни при удалении. Новый берётся на
    единицу больше наибольшего; номер не равен месту в списке (так у примерно половины наборов
    корпуса), и пересчёт по местам переписал бы половину корпуса не тем. Колонки одного поля
    различаются ровно четырьмя значениями — двумя именами, заголовком и номером.

    **Колонка табличной части (вид `c2cf1953…`).** Её данные — не строка, а путь в самой колонке
    (`u1/u1/u2`: `[0, {guid реквизита ТЧ}]`, `[-2]` номер строки, `[-1]` не заданы), и копия донора
    несла бы путь чужой колонки. Поэтому у колонки ТЧ `data` — путь по метаданным,
    `"Объект.ТЧ.Реквизит"` (`НомерСтроки` — номер строки), по правилу `bind`: путь пишется сразу
    вместе с типом колонки и её вложенного поля ввода (нужна выгрузка `config` и привязка таблицы к
    ТЧ; `form_use` — как у `bind`); без `data` колонка получает `[-1]` — «данные не заданы» — а тип
    остаётся донорским (отчёт об этом говорит). Колонки с `[-1]` платформа пишет сама (вычисляемые и
    служебные).

    **Образец конструктора — `template`.** Вместо копии соседней колонка берётся из образцов, снятых
    с форм конструктора форм платформы 8.3.27 (`templates.TABULAR_COLUMNS`): `row_number` (путь
    `[-2]`), `string`, `decimal`, `catalog`, `boolean`, образцы даты (три состава), документа,
    перечисления и составного типа — вложенное поле ввода по типу, ширина 100 (у номера строки 28),
    режим редактирования, как у конструктора. Нужны `data` (путь по метаданным, образец без данных
    не бывает) и привязка таблицы к ТЧ; `donor` рядом — отказ. Образец можно класть и в таблицу без
    колонок: копировать нечего, образец — сам источник (так собирается новая таблица на ТЧ,
    `generate`). Колонка-флажок (`boolean`): булев реквизит конструктор пишет не в Данные, а в
    ДанныеФлажка (`u3`, слот `COLUMN_CHECK_PATH`): Данные `[-1]`, вложенный элемент — флажок, тип
    значения колонки — умолчание (строка 10). Порядковые номера (`COLUMN_ORDINALS`): в слот с
    данными — место реквизита в табличной части по выгрузке (с нуля; у номера строки −2), в прочие
    −1; номер колонки (`COLUMN_ORDER`) — наибольший плюс один, у первой колонки 0. У каждого класса
    типа свой образец (`template_kind`: у даты по составу реквизита). Вложенное поле после образца
    ещё раз получает запись класса (`edit.datatype.apply_record`): у образца она та же, у колонки
    без образца (`bind`) — единственный способ получить её.

    **Колонка табличного поля списка.** Таблица, привязанная к динамическому списку объекта выгрузки
    (основной реквизит формы списка), — другое дело: колонка вида списка, путь `data="<реквизит
    формы>.<колонка>"` (стандартная колонка или реквизит объекта), образец — конструктора
    (стандартные) либо колонки табличной части того же класса (реквизиты); `template`, `donor` и
    `form_use` там отказ. Подробно — `frm_codec/edit/listcols.py`. Нужна выгрузка `config`.
    """
    if config is not None:
        from . import listcols as _list  # здесь, а не наверху: edit.listcols сам читает колонки
        if _list.list_attribute(doc, find_element(doc, table), _list.datapath.load_config(config)) is not None:
            return _list.add_list_column(doc, table, name, header, data, config, form_use, unverified, template, donor)
    block = _columns_of(doc, table, value_list_ok=True)
    members = block[COLUMN_ITEMS]
    if name in [_column_name(column) for column in members]:
        raise EditError(f"колонка {name!r} у {table!r} уже есть")
    place = find_element(doc, table)
    if _is_value_list_table(place.element, members, table):
        return _add_value_list_column(doc, table, name, header, donor, data, template, form_use, block, unverified)
    first = None
    old_said = None
    if template is not None:
        source = _template_source(template, donor, data, table, name)
        source, old_said = old_column(doc, place.element, source, f"column-tabular-{template}", unverified)
    elif not members:
        source, first = _first_column(doc, place, table, name, donor, unverified)
    elif donor is None:
        source = members[-1]
    else:
        source = next((c for c in members if _column_name(c) == donor), None)
        if source is None:
            known = ", ".join(str(_column_name(c)) for c in members)
            raise EditError(f"колонки-донора {donor!r} у {table!r} нет; есть: {known}")
    column = copy.deepcopy(source)
    written = None
    extra = ""
    tabular = (column.get(COLUMN_TYPE) or {}).get("guid") == schema.TABULAR_COLUMN
    if form_use is not None and not (tabular and data is not None):
        raise EditError("form_use нужен пути по метаданным: колонка табличной части с data=\"Объект.ТЧ.Реквизит\"; "
                        f"у колонки донора {name!r} такого пути не будет, и форма элемента или группы не при чём")
    if tabular:
        from . import datapath as _path     # здесь, а не наверху: edit.datapath сам читает колонки
        base = _column_base(column)
        if not isinstance(base, dict) or _path.COLUMN_PATH not in base:
            raise EditError("у колонки-донора нет места пути данных — строение не то, что у колонок корпуса")
        was = base[_path.COLUMN_PATH]
        if data is None:
            base[_path.COLUMN_PATH] = list(_path.NO_DATA)
            written = ""
            extra = (f"; путь данных {_path.NO_DATA} («данные не заданы»), донорский {was} не копируется — "
                     "привязка по реквизиту: bind с table, column и data; тип колонки остался донорским")
        else:
            new, said_path, attr, ordinal = _path.column_path(doc, find_element(doc, table), name, data, config,
                                                              unverified, form_use)
            checkbox = template == "boolean"
            _template_class(template, attr, name)
            plan = _path.column_type_plan(column, attr, _path.load_config(config), unverified, f"колонка {name!r}",
                                          checkbox=checkbox)
            slot = COLUMN_CHECK_PATH if checkbox else _path.COLUMN_PATH
            head = _column_body(column)
            for path_slot in (_path.COLUMN_PATH, COLUMN_CHECK_PATH, COLUMN_PICTURE_PATH):
                base[path_slot] = list(_path.NO_DATA)
            base[slot] = new
            for ordinal_slot in COLUMN_ORDINALS:
                head[ordinal_slot] = -1
            head[COLUMN_ORDINALS[1] if checkbox else COLUMN_ORDINALS[0]] = ordinal
            written = ""
            extra = (f"; путь данных {new} ({said_path})" + (", слот ДанныеФлажка" if checkbox else "")
                     + f", порядковый номер {ordinal}" + _path.apply_column_type(
                column, plan[0], f"колонки {name!r}") + "".join(f"; {n}" for n in plan[1]))
    elif isinstance(column[COLUMN_BODY].get(COLUMN_DATA), str):
        written = name if data is None else data
        column[COLUMN_BODY][COLUMN_DATA] = written
    elif data is not None:
        raise EditError(
            f"Данные колонке {name!r} у {table!r} не поставить: у колонки-донора на этом месте "
            "не строка, а флаг «ОтображатьСтандартнуюКартинку» — так устроены колонки списка. Строкой Данные бывают только у колонки "
            "ТАБЛИЦЫ ЗНАЧЕНИЙ; уберите data, и колонка возьмёт Данные донора")
    body = _column_body(column)
    body[COLUMN_NAME] = name
    body[COLUMN_ORDER] = max([_column_body(c).get(COLUMN_ORDER) or 0 for c in members], default=-1) + 1
    if header is not None:
        set_text(body[COLUMN_HEADER_TEXT], header)
    elif first is not None:
        set_text(body[COLUMN_HEADER_TEXT], name)      # заголовок шаблона — служебная строка, а не имя колонки
        extra += "; заголовок — имя колонки (header не назван; заголовок шаблона — служебная строка)"
    if old_said:
        extra += f"; {old_said}"
    if first is not None:
        extra += (f"; {first}" if first else "") + _on_corpus(
            "add_column/first", "первая колонка таблицы значений из шаблона редактора", True)
    members.append(column)
    block[COLUMNS_COUNT] = len(members)
    # Про Данные отчёт говорит всегда, в том числе когда они остались донорскими: умолчание «Данные
    # = имя» верно у колонки таблицы значений и не работает у колонки списка, и человек обязан
    # узнать об этом из отчёта, а не из палитры.
    said = ("Данные колонки табличной части — путь" if tabular else
            f"Данные {written!r}" if written is not None else "Данные донора не тронуты")
    return f"{table}: колонка {name!r}, номер {body[COLUMN_ORDER]}, {said}{extra}"


def old_column(doc, table_node, column, template, unverified):
    """`(колонка, фраза отчёта)`: образец колонки `template` для формы старой версии общего блока (10, 13, 15) сведён к версии формы и записи самого табличного поля
    (`old_versions`, раздел `tables`); образец без подтверждения корпусом — ОТКАЗ словами, `unverified` оставляет образец версии 16 (смесь версий называет проверка формы).
    Форма версии 16 и бережный режим (`old_versions.off`) — образец без изменений и без фразы.
    """
    from .. import old_versions as _old
    version = _design.form_version(doc)
    if version not in _old.VERSIONS or not _old.enabled():
        return column, None
    record = _old.table_record(table_node)
    reason = _old.column_refusal(version, record, template)
    if reason is not None:
        if unverified:
            return column, None
        raise EditError(reason + ". Позвать всё же можно — unverified=True (образец версии 16 в форме версии "
                        f"{version}: при первом сохранении в конфигураторе форма целиком уйдёт в версию платформы). Дорога — donor: колонка этой же таблицы")
    return _old.reduce_column(column, template, version, record)


def old_control(doc, table_node, body, key, unverified):
    """`(тело, фраза)`: содержимое вложенного поля колонки (`key` — `TextBox-S`, `TextBox-N`, `CheckBox`) для формы старой версии сведено к версии формы и записи поля; иначе — как
    `old_column`. Вид без образца сведения (`ComboBox`) в форме старой версии — отказ с дорогой `template`."""
    from .. import old_versions as _old
    version = _design.form_version(doc)
    if version not in _old.VERSIONS or not _old.enabled():
        return body, None
    record = _old.table_record(table_node)
    reason = _old.control_refusal(version, record, key)
    if reason is not None:
        if unverified:
            return body, None
        raise EditError(reason + ". Позвать всё же можно — unverified=True (тело версии 16 в форме версии "
                        f"{version}: при первом сохранении в конфигураторе форма целиком уйдёт в версию платформы)")
    return _old.reduce_control(body, key, version, record)


def _first_column(doc, place, table, name, donor, unverified):
    """Первая колонка таблицы без колонок: шаблон редактора, если это таблица или дерево значений; иначе отказ словами.

    Колонка таблицы значений — единственная, которую можно положить без образца конструктора и без донора: таблицы и
    деревья значений без колонок в образцах форм есть (вид данных 5 и 4), у них те же поля табличного поля, что у таблиц с
    колонками, а первая колонка любого вида стоит «в новой колонке», как в шаблоне. Версия общего блока вложенного поля
    сверяется с версией формы, как у `set_column_control`: шаблон взят из другой формы.
    """
    if donor is not None:
        raise EditError(f"donor называет колонку-источник, а у {table!r} колонок нет: копировать нечего")
    kind = table_source_kind(place.element)
    if kind in VALUE_TABLE_SOURCES:
        from .. import templates as _templates
        column, said_old = old_column(doc, place.element, _templates.table_first_column(), "TableBox", unverified)
        head = _column_body(column)
        _kind, content = nested_control(head, f"образца первой колонки {name!r}")
        said = _version_check(doc, _design.content_versions("TextBox", content), "add_column", unverified, kind="TextBox")
        return column, "; ".join(x for x in (said_old, said) if x)
    who = ("колонку табличной части с данными — `template` (образец конструктора) и `data=\"Объект.ТЧ.Реквизит\"`; "
           "колонку таблицы формы списка — `data=\"<реквизит формы>.<колонка>\"` с выгрузкой конфигурации (`--config`)")
    raise EditError(f"у {table!r} нет ни одной колонки, а образец колонки такого поля у редактора не заведён "
                    f"(вид данных {kind if kind is not None else 'не прочитан'}; шаблон — только у таблицы и дерева значений, "
                    f"{', '.join(f'{k} — {v}' for k, v in VALUE_TABLE_SOURCES.items())}). Первую {who}")


# Образцы колонки табличной части (`templates.TABULAR_COLUMNS`) и классы типа, которые каждый берёт.
# Образец — колонка, как её пишет конструктор форм платформы 8.3.27: вложенное поле ввода по типу
# реквизита, ширина, режим редактирования. У каждого класса типа есть образец (дата в трёх составах,
# документ, перечисление и составной тип).
TABULAR_TEMPLATES = {
    "row_number": (None,),
    "string": ("string",),
    "decimal": ("decimal",),
    "catalog": ("catalog",),
    "boolean": ("boolean",),
    "date": ("dateTime",),
    "datetime": ("dateTime",),
    "time": ("dateTime",),
    "document": ("document",),
    "enum": ("enum",),
    "composite": ("composite",),
}
# Образец даты — по составу (`DateFractions` реквизита): записи различаются описателем и зеркалом
# состава, а кнопка выбора, `wrap` и `u22` у всех три равны.
DATE_TEMPLATES = {"Date": "date", "DateTime": "datetime", "Time": "time"}
TEMPLATE_BY_CLASS = {cls: kind for kind, classes in TABULAR_TEMPLATES.items() for cls in classes if cls is not None and cls != "dateTime"}


def template_kind(attr):
    """Образец колонки по реквизиту табличной части: класс типа, у даты ещё и состав. Тип, которого
    запись не выражает, — `TypeNotWritten`.
    """
    from . import datatype as _types
    cls = _types.type_class(attr)
    return DATE_TEMPLATES[attr.date_fractions] if cls == "dateTime" else TEMPLATE_BY_CLASS[cls]


def _template_source(template, donor, data, table, name):
    """Колонка-образец конструктора для `add_column(template=…)` либо отказ словами."""
    from .. import templates as _templates
    if template not in TABULAR_TEMPLATES:
        raise EditError(f"template — образец колонки табличной части: {', '.join(TABULAR_TEMPLATES)}; пришло {template!r}")
    if donor is not None:
        raise EditError("template и donor называют две разные колонки-источника: образец конструктора либо копия соседней — одно из двух")
    if data is None:
        raise EditError(f"template {template!r} — образец колонки табличной части, а её путь по метаданным (data=\"Объект.ТЧ.Реквизит\") "
                        f"не назван: колонка {name!r} у {table!r} без данных образцом не бывает")
    return _templates.tabular_column(template)


def _template_class(template, attr, name):
    """Образец подходит реквизиту: класс типа, у даты — состав (`template_kind`); НомерСтроки —
    `row_number`; несовпадение — отказ словами.
    """
    if template is None:
        return
    from . import datatype as _types
    if attr is None:
        want, said = "row_number", "номер строки"
    else:
        try:
            want = template_kind(attr)
        except _types.TypeNotWritten:
            return           # тип без класса: отказ скажет `column_type_plan` своими словами
        cls = _types.type_class(attr)
        said = _types.CLASS_WORDS[cls] + (f", состав {attr.date_fractions}" if cls == "dateTime" else "")
    if template != want:
        what = "номера строки" if template == "row_number" else ", ".join(
            _types.CLASS_WORDS.get(c, c) for c in TABULAR_TEMPLATES[template]) + (
            f" (состав {next(k for k, v in DATE_TEMPLATES.items() if v == template)})" if template in DATE_TEMPLATES.values() else "")
        raise EditError(f"колонка {name!r}: образец {template!r} — для {what}, а реквизит — {said}; нужен образец {want!r}")


def remove_column(doc, table, name):
    """Колонка из табличного поля. Номера оставшихся не трогаются.

    Номер оставшейся колонки прежний — то самое правило `add_column`, по которому номер не равен
    месту в списке. Первая колонка в образцах форм всегда стоит «в новой колонке»: если после снятия первой
    новой первой стала колонка с иным расположением, оно выправляется (отчёт это говорит).

    **Последняя колонка.** Таблицу без колонок оставляет только таблица значений или дерево значений (такие таблицы в образцах
    форм есть, и поля самого табличного поля у них те же, что у таблиц с колонками). У остальных видов (табличная
    часть, список, список значений) таблицы без колонок в образцах форм нет ни одной, и последнюю колонку операция не
    снимает.

    **Колонка списка значений** снимается так же, но только если останется хотя бы одна колонка этого вида.
    """
    block = _columns_of(doc, table, value_list_ok=True)
    members = block[COLUMN_ITEMS]
    column = next((c for c in members if _column_name(c) == name), None)
    if column is None:
        known = ", ".join(str(_column_name(c)) for c in members)
        raise EditError(f"колонки {name!r} у {table!r} нет; есть: {known}")
    place = find_element(doc, table)
    value_list = _is_value_list_table(place.element, members, table)
    tail = ""
    if len(members) == 1:
        kind = table_source_kind(place.element)
        if value_list:
            raise EditError(f"это единственная колонка {table!r}; таблицы со списком значений без колонок в образцах форм "
                            "нет ни одной, и заводить такую таблицу редактор не станет")
        if kind not in VALUE_TABLE_SOURCES or (column.get(COLUMN_TYPE) or {}).get("guid") != VALUE_TABLE:
            raise EditError(f"это единственная колонка {table!r}; табличного поля без колонок, кроме таблицы и дерева значений "
                            "({}), в образцах форм нет ни одного, и заводить его редактор не станет".format(
                                ", ".join(f"{k} — {v}" for k, v in VALUE_TABLE_SOURCES.items())))
        tail = _on_corpus("remove_column/last", "таблица значений без колонок", True)
    index = members.index(column)
    members.remove(column)
    block[COLUMNS_COUNT] = len(members)
    if index == 0:
        tail = _first_column_location(members) + tail
    if value_list:
        tail += _on_corpus("remove_column/value-list", "колонка списка значений снята", True)
    return f"{table}: колонка {name!r} убрана, колонок {len(members)}{tail}"


# ── Колонка списка значений ───────────────────────────────────────────────────────

def _slot_ref(base, key):
    """Ссылка базы колонки списка значений: поле элемента списка (`0` Значение, `1` Представление, `2` Пометка, `3`
    Картинка) либо `-1` — ссылки нет; `None` — запись другого строения.
    """
    value = base.get(key)
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], int) and not isinstance(value[0], bool):
        return value[0]
    return None


def value_list_role(column):
    """Поле элемента списка, которое показывает колонка: `Значение`, `Представление`, `Пометка` либо `None` — другое
    (картинка, два поля в одной колонке, ссылка не по строению корпуса).
    """
    base = _column_base(column) or {}
    refs = [_slot_ref(base, key) for key in ("u2", "u3", "u4")]
    for role, (key, code) in VALUE_LIST_ROLES.items():
        want = [-1, -1, -1]
        want[("u2", "u3", "u4").index(key)] = code
        if refs == want:
            return role
    return None


def _no_header(head):
    """Заголовок колонки пуст так, как у колонки без заголовка в образцах форм: запись без языков, счётчик 0."""
    block = head[COLUMN_HEADER_TEXT]
    block.clear()
    block.update({LS_MARK: 1, LS_COUNT: 0, LS_ITEMS: []})


def _add_value_list_column(doc, table, name, header, donor, data, template, form_use, block, unverified):
    """Колонка списка значений: `data` называет поле элемента списка — `Значение`, `Представление` или `Пометка`.

    У колонки этого вида нет образца конструктора форм, и колонка строится по записи образцов форм. Поэтому берутся только те случаи,
    где образец формы однозначен:

    * **Пометка** — колонка без вложенного элемента: ссылка `u3 = [2]`, порядковые числа `-1, 0, -1`, тип значения «Строка
      10» с признаком `u2 = 1`, режим редактирования «Непосредственно», ширина 21 (`width_computed` 3), заголовок пуст
      (6 колонок из 6). Остальное — у колонки-донора. Вложенный элемент донора снимается: голова переходит в строение
      без элемента.
    * **Значение** и **Представление** — копия колонки-донора, которая показывает другое из этих двух полей через поле
      ввода строки (`Строка` без длины, `TextBox`); меняется только ссылка `u2` (`[0]` или `[1]`). Донор с иным типом
      значения или иным вложенным элементом — отказ: тип новой колонки у платформы не проверялся.

    Колонка на поле, которое в таблице уже показывает другая колонка, — отказ: в образцах форм у таблиц со списком значений
    такого нет ни у одной. Картинка — отказ: колонки только с картинкой в образцах форм нет.
    """
    if template is not None or form_use is not None:
        raise EditError("у колонки списка значений нет ни `template`, ни `form_use`: поле элемента списка называет `data` "
                        "(" + ", ".join(VALUE_LIST_ROLES) + ")")
    if data is None:
        raise EditError(f"у колонки списка значений нужен `data` — поле элемента списка ({', '.join(VALUE_LIST_ROLES)}); "
                        f"колонка {name!r} у {table!r}")
    if data == "Картинка":
        raise EditError("колонку с одной картинкой элемента списка редактор не заводит: в образцах форм картинка бывает только "
                        "рядом со значением в одной колонке, а отдельной колонки-картинки нет ни у одного поля")
    if data not in VALUE_LIST_ROLES:
        raise EditError(f"data колонки списка значений — поле элемента списка: {', '.join(VALUE_LIST_ROLES)}; пришло {data!r}")
    members = block[COLUMN_ITEMS]
    if not members:
        raise EditError(f"у {table!r} нет ни одной колонки, а образца колонки списка значений у редактора нет: "
                        "образца такой колонки у конструктора форм нет")
    roles = {_column_name(c): value_list_role(c) for c in members}
    if data in roles.values():
        who = next(n for n, r in roles.items() if r == data)
        raise EditError(f"поле {data!r} у {table!r} уже показывает колонка {who!r}: второй колонки на то же поле в образцах форм "
                        "нет ни у одной таблицы со списком значений")
    if data == "Пометка":
        source = _value_list_donor(members, donor, table, lambda c: True, "любая колонка таблицы")
    else:
        source = _value_list_donor(
            members, donor, table,
            lambda c: value_list_role(c) in ("Значение", "Представление") and _is_string_text_box(c),
            "колонка на Значение или Представление с полем ввода строки без длины")
    column = copy.deepcopy(source)
    base = _column_base(column)
    head = _column_body(column)
    key, code = VALUE_LIST_ROLES[data]
    for slot in ("u2", "u3", "u4"):
        base[slot] = [-1]
    base[key] = [code]
    for ordinal in COLUMN_ORDINALS:
        head[ordinal] = -1
    head[COLUMN_ORDINALS[("u2", "u3", "u4").index(key)]] = 0
    notes = []
    if data == "Пометка":
        if not _head_is_bare(head):
            _drop_control(head)
        head[COLUMN_VALUE_TYPE] = {PATTERN_MARK: "Pattern", PATTERN_TYPES: [{PATTERN_KIND: "S", PATTERN_LENGTH: 10, "u2": 1}]}
        head["edit_mode"] = VALUE_LIST_CHECK["edit_mode"]
        head["width_computed"] = VALUE_LIST_CHECK["width_computed"]
        head.pop("u4", None)
        head["width"] = VALUE_LIST_CHECK["width"]
        if "width_mirror" in head:
            head["width_mirror"] = VALUE_LIST_CHECK["width"]
        _no_header(head)
        notes.append("колонка-пометка: тип значения Строка 10, режим редактирования «Непосредственно», ширина 21, "
                     "без вложенного элемента (так в образцах форм у всех таких колонок)")
    head[COLUMN_NAME] = name
    head[COLUMN_ORDER] = max([_column_body(c).get(COLUMN_ORDER) or 0 for c in members], default=-1) + 1
    if header is not None:
        if header:
            set_text(head[COLUMN_HEADER_TEXT], header)
        else:
            _no_header(head)
    elif data != "Пометка":
        notes.append("заголовок донорский")
    members.append(column)
    block[COLUMNS_COUNT] = len(members)
    return (f"{table}: колонка списка значений {name!r} на поле «{data}», номер {head[COLUMN_ORDER]}, образец — колонка "
            f"{_column_name(source)!r}" + "".join(f"; {n}" for n in notes)
            + _on_corpus("add_column/value-list", f"колонка на поле «{data}»", True))


def _is_string_text_box(column):
    """Колонка с вложенным полем ввода, тип значения которой — строка без длины (`[S]`)."""
    head = _column_body(column)
    if _head_is_bare(head) or not isinstance(head.get(COLUMN_CONTROL), dict):
        return False
    guid = (head.get(COLUMN_CONTROL_TYPE) or {}).get("guid") if isinstance(head.get(COLUMN_CONTROL_TYPE), dict) else None
    types = (head.get(COLUMN_VALUE_TYPE) or {}).get(PATTERN_TYPES) or []
    return guid == schema.ELEMENT_GUIDS["TextBox"] and len(types) == 1 and types[0] == {PATTERN_KIND: "S"}


def _value_list_donor(members, donor, table, fits, what):
    """Образец новой колонки списка значений: названный `donor` либо последняя подходящая; нет — отказ словами."""
    if donor is not None:
        found = next((c for c in members if _column_name(c) == donor), None)
        if found is None:
            known = ", ".join(str(_column_name(c)) for c in members)
            raise EditError(f"колонки-донора {donor!r} у {table!r} нет; есть: {known}")
        if not fits(found):
            raise EditError(f"колонка {donor!r} у {table!r} не годится в образцы: нужна {what}")
        return found
    fitting = [c for c in members if fits(c)]
    if not fitting:
        raise EditError(f"у {table!r} нет образца для новой колонки: нужна {what} (тип значения новой колонки у платформы "
                        "не проверялся, и колонка не строится из чужого образца)")
    return fitting[-1]


# ── Вложенный элемент колонки ─────────────────────────────────────────────────────

def _column(doc, table, name):
    """Колонка по имени — одна, иначе отказ со списком имеющихся. Вид колонки не важен: имя лежит в
    голове, а голова у всех четырёх видов одна.
    """
    block = _columns_holder(doc, table)
    found = [item for item in block[COLUMN_ITEMS] if _column_name(item) == name]
    if not found:
        known = ", ".join(str(_column_name(item)) for item in block[COLUMN_ITEMS]) or "—"
        raise EditError(f"колонки {name!r} у {table!r} нет; есть: {known}")
    if len(found) > 1:
        raise EditError(f"колонок с именем {name!r} у {table!r} — {len(found)}; какую из них "
                        "править, по имени не решить")
    return found[0]


NO_CONTROL = "none"          # `control` у `set_column_control`: снять вложенный элемент («пустая строка» палитры)


def _head_is_bare(head):
    """Голова колонки без вложенного элемента: пустой GUID типа элемента (`control_type`)."""
    kind = head.get(COLUMN_CONTROL_TYPE)
    return isinstance(kind, dict) and kind.get("guid") == schema.ZERO_GUID


def _unnamed_position(key):
    match = re.fullmatch(r"u(\d+)", key) if isinstance(key, str) else None
    return int(match.group(1)) if match else None


def _reshaped_head(head, to_bare, control_type=None, control_block=None):
    """Голова колонки в другом строении: без вложенного элемента (`to_bare`) либо с ним. Новый словарь, `head` не тронут.

    Голова с элементом на одну позицию длиннее: блок элемента стоит на позиции 39, а у колонки без элемента на ней число 0
    и всё, что за ним, стоит на одну позицию ближе (`schema.COLUMN_HEAD_BARE`). Безымянные позиции за 39 поэтому
    переименовываются на единицу (`u40` ↔ `u39`); именованные (зеркало ширины `width_mirror`) называются одинаково в обоих
    строениях и остаются. Ключи идут в порядке позиций, как их отдаёт разбор файла.
    """
    at = COLUMN_CONTROL_AT
    if to_bare:
        if COLUMN_CONTROL not in head or f"u{at}" in head:
            raise EditError("голова колонки устроена не так, как у колонки с вложенным элементом (блока элемента нет или на его "
                            "месте лишняя безымянная позиция): править такую колонку нечем")
        step, floor = -1, at + 1
    else:
        if COLUMN_CONTROL in head:
            raise EditError("голова колонки без вложенного элемента несёт блок элемента: правленый руками документ?")
        step, floor = 1, at
    out = {}
    for key, value in head.items():
        if to_bare and key == COLUMN_CONTROL:
            continue
        number = _unnamed_position(key)
        out[f"u{number + step}" if number is not None and number >= floor else key] = value
    if not to_bare:
        out[COLUMN_CONTROL_TYPE] = control_type
        out[COLUMN_CONTROL] = control_block
    variant = schema.COLUMN_HEAD_BARE if to_bare else schema.COLUMN_HEAD
    where = {slot.name: index for index, slot in schema.MAP[variant].fields.items()}

    def position(key):
        return where[key] if key in where else (_unnamed_position(key) if _unnamed_position(key) is not None else 10 ** 6)

    return {key: out[key] for key in sorted(out, key=position)}


def _drop_control(head):
    """Колонке без вложенного элемента — голова другого строения; элемент у колонки был, и вместе с ним уходит его блок."""
    new = _reshaped_head(head, True)
    new[COLUMN_CONTROL_TYPE] = {"guid": schema.ZERO_GUID}
    head.clear()
    head.update(new)


def _remove_control(doc, table, column, unverified):
    """`set_column_control(control="none")`: снять вложенный элемент колонки — «ЭлементУправления» становится пустой строкой.

    Колонка остаётся с тем же типом значения, шириной и шрифтами, голова переходит в строение без элемента. В образцах форм
    колонок без вложенного элемента много, и всё, что операция пишет, — строение их головы (блока элемента нет,
    пустой GUID типа). Что платформа переписывает, снимая элемент, кроме GUID и конверта, не проверялось, поэтому отчёт говорит
    «платформой не проверялось».

    Отказ словами, и документ не тронут:

    * у колонки элемента нет уже;
    * у элемента есть связи (`control.links`) или обработчики событий: их унесло бы молча;
    * колонка такого вида с такими буквами типа значения без элемента в образцах форм не встречается (снимается
      `unverified=True`; перечень встречающихся называет отказ).
    """
    item = _column(doc, table, column)
    if _head_is_bare(_column_body(item)):
        raise EditError(f"у колонки {column!r} вложенного элемента нет: «ЭлементУправления» уже пустая строка; снимать нечего")
    head, was, content = column_control(doc, table, column)
    kind_words, kind_guid = _column_kind_words(item)
    links = head[COLUMN_CONTROL].get(CONTROL_LINKS) or []
    if links:
        raise EditError(f"у вложенного элемента колонки {column!r} {len(links)} связ(и) (`{CONTROL_LINKS}`): снятие элемента унесло бы "
                        "их молча. Уберите их руками, если они не нужны, и повторите")
    events = (content.get(EVENTS) or {}).get(EVENT_ITEMS) if isinstance(content.get(EVENTS), dict) else None
    if events:
        names = ", ".join(str(row.get("event")) for row in events if isinstance(row, dict))
        raise EditError(f"у вложенного элемента колонки {column!r} есть обработчики событий ({names}): снятие элемента унесло бы "
                        "их молча, а снять обработчик операцией редактора нельзя. Уберите их правкой формы и повторите")
    letters = _type_letters(head.get(COLUMN_VALUE_TYPE))
    seen = CORPUS_COLUMN_BARE.get((kind_guid, letters))
    if seen is None and not unverified:
        known = ", ".join(sorted(sig for (g, sig), n in CORPUS_COLUMN_BARE.items() if g == kind_guid))
        raise EditError(f"колонка вида «{kind_words}» без вложенного элемента с типом значения {_type_words(head.get(COLUMN_VALUE_TYPE))} "
                        f"(буквы {letters}) в образцах форм не встречается: у колонок этого вида без элемента тип — {known}. "
                        "Позвать всё же можно — unverified=True")
    _drop_control(head)
    return (f"{table}/{column}: вложенный элемент {was} снят — колонка без вложенного элемента, голова на одну позицию короче, "
            f"тип значения {_type_words(head.get(COLUMN_VALUE_TYPE))} не тронут"
            + _on_corpus("set_column_control/nested", f"колонка вида «{kind_words}» без элемента с типом значения {letters}", seen))


def column_control(doc, table, name):
    """`(голова колонки, вид элемента, содержимое)` вложенного элемента — адрес «колонка → вложенный
    элемент», которым его правят операции элемента (`set_font`, `set_event` с `nested=True`). Отказ
    — если элемента у колонки нет или он не раскрыт.

    Колонка без элемента — законное состояние файла, а не порча: тип пустой, и позиции элемента нет
    вовсе либо на ней ноль (так пишет платформа, когда в палитре «ЭлементУправления» выбрана пустая
    строка). Сырой конверт — тоже законное: его не раскрыло сжатие этой машины (`frm_codec.packed`).
    """
    head = _column_body(_column(doc, table, name))
    kind, content = nested_control(head, f"колонки {name!r} поля {table!r}")
    return head, kind, content


def nested_control(head, whose):
    """`(вид элемента, содержимое)` вложенного элемента по ГОЛОВЕ колонки; нет или не раскрыт — отказ
    словами.

    Отдельно от `column_control` ради колонки, которой в документе ещё нет (копия донора в
    `add_column`).
    """
    guid = (head.get(COLUMN_CONTROL_TYPE) or {}).get("guid") \
        if isinstance(head.get(COLUMN_CONTROL_TYPE), dict) else None
    control = head.get(COLUMN_CONTROL)
    kind = schema.element_type_name(guid) if guid else None
    if not isinstance(control, dict) or kind is None:
        raise EditError(f"у {whose} вложенного элемента нет (тип "
                        f"{guid or '—'}): в палитре у неё «ЭлементУправления» — пустая строка. "
                        "Как платформа заводит элемент у такой "
                        "колонки, не проверялось")
    element = control.get(CONTROL_ELEMENT)
    content = element.get(PACKED_CONTENT) if isinstance(element, dict) else None
    if not isinstance(content, dict) or typed.RAW in content:
        raise EditError(f"вложенный элемент {whose} не раскрыт — конверт "
                        "хранится сырой строкой base64 (причину называет `validate`), и править "
                        "его именами нечем")
    return kind, content


def _column_kind_words(column):
    guid = (column.get(COLUMN_TYPE) or {}).get("guid")
    return COLUMN_KINDS.get(guid, guid), guid


def set_column_control(doc, table, column, control, template=None, unverified=False):
    """Сменить вид вложенного элемента колонки — строка палитры «ЭлементУправления» — завести его у колонки без
    элемента (`control` — вид, ровно та же запись) или снять (`control="none"`, пустая строка палитры).

    **Завести и снять.** Голова колонки без вложенного элемента на одну позицию короче: блок элемента стоит на
    позиции 39, а за ним всё — на позицию дальше (`_reshaped_head`). Операция переносит голову из одного строения в
    другое и ничего больше не меняет — тип значения, ширина и шрифты колонки остаются. Заведение берёт тело из шаблона
    (поле ввода строки или числа; иначе `template`) и проверяет сочетание «вид колонки × вид элемента × буквы типа» по
    образцам форм; снятие проверяет, что колонка такого вида с таким типом без элемента в образцах форм есть
    (`CORPUS_COLUMN_BARE`). Связи и обработчики вложенного элемента снятие не уносит — отказ. Оба действия
    платформой не проверялись: отчёт говорит об этом.

    Колонка несёт элемент-редактор ячейки, и вид его — не значение, а тип вложенного элемента
    (справочник: `КолонкаТабличногоПоля.УстановитьЭлементУправления(<Тип>)`, типы ПолеВвода,
    ПолеВыбора, Флажок). Платформа при смене переписывает ровно две позиции: GUID типа
    (`control_type`) и конверт (`control.element`). Операция делает то же: новый GUID и тело нового
    вида — из шаблона (файлы `data/templates/column-control-*.json`) или из `template` (содержимое вложенного
    элемента того же вида из другой формы, как у `add_element`).

    **Тип значения колонки операция ведёт так, как его ведёт платформа, — там, где это проверено**
    (три случая из восьми сочетаний «вид колонки × вид элемента»). У колонки таблицы значений тип
    свой, и платформа меняет его вместе с элементом: при смене на флажок он становится Булево, при
    смене на поле выбора обнуляется. У колонки табличной части смена поля ввода на поле выбора тип
    не трогает, и операция его у табличной части и списка не трогает вовсе. Отчёт называет прежний
    тип, когда он меняется.

    **Остальное не проверялось, и спрашивается корпус — по трём признакам:** вид колонки, вид
    элемента и буквы типа значения после смены (`CORPUS_COLUMN_CONTROL_TYPES`). Невиданное сочетание
    — отказ, снимаемый `unverified=True` (и тогда пометка «не видел»), виденное — пометка с числом
    таких колонок. Корпус там держит только строку и булево (числа, даты и ссылки у флажков колонок
    табличной части и списка не встречаются), поэтому поле ввода с числом, ставшее флажком, осталось
    бы с числом.

    **У поля ввода описатель типа лежит и в теле** (позиция 1, `pattern`), а у флажка и поля выбора
    его в теле нет. Поле ввода получает описателем тип колонки, а шаблон под него берётся того же
    типа: строковый или числовой. Квалификаторы ставятся и в свойства поля — там первичный адрес
    строки палитры «Длина» (`digits`): у числа длина, точность и знак, у строки её длина (нет длины
    — ноль); точность и знак у строки остаются шаблонными. Иного типа шаблона нет, и тогда нужен
    `template`.

    Отказы — словами:

    * вид не из трёх (палитра колонки таблицы значений предлагает ещё «Поле календаря», но в корпусе
      его нет ни у одной колонки, и строения его тела карта не видела);
    * вид тот же — менять нечего;
    * поле выбора у колонки списка — в корпусе нет ни одного (`CORPUS_COLUMN_CONTROLS`; снимается
      `unverified=True`);
    * не поле ввода у колонки списка значений (`fbacf851-…`): у всех её вложенных элементов в
      корпусе — поле ввода, и как платформа ведёт у неё смену вида, не проверялось (снимается
      `unverified=True`; тип значения колонки операция у неё не трогает);
    * сочетание «вид колонки × вид элемента × буквы типа», которого корпус не видел, — например,
      флажок у колонки табличной части с числом (снимается `unverified=True`);
    * у элемента есть связи (`control.links`) — они бывают только у поля ввода, и унести их молча
      нельзя;
    * поле ввода, а тип колонки не строка и не число, и `template` не дан.

    **Проверен один вариант** (`ROUND10_COLUMN_CONTROL`): у колонки табличной части с числом поле
    ввода → поле выбора, тело — шаблон редактора. Конструктор принял форму без сообщений, палитра
    нового поля выбора совпала с платформенной сменой, пересохранение конверт не тронуло; в
    1С:Предприятии ввод числа с клавиатуры поле выбора не приняло — так же, как платформенное. На
    этом варианте отчёт говорит «проверено». Прочие — другой вид колонки, другие буквы типа, флажок,
    поле ввода из поля выбора, тело из `template` — говорят «есть в корпусе, не проверялось» с
    числом колонок этого вида с этим элементом и этими буквами типа, либо, с `unverified=True`,
    «корпус такого не видел».
    """
    from .. import templates as _templates
    if control == NO_CONTROL:
        return _remove_control(doc, table, column, unverified)
    if control not in CONTROL_KINDS:
        raise EditError(
            f"вида {control!r} у вложенного элемента колонки не бывает: справочник у свойства "
            "ЭлементУправления называет три — ПолеВвода, ПолеВыбора, Флажок (TextBox, ComboBox, "
            f"CheckBox; снять элемент — control=\"{NO_CONTROL}\"), и корпус держит ровно их. Палитра колонки "
            "таблицы значений предлагает ещё «Поле календаря», но ни у одной колонки "
            "корпуса его нет, и строения его тела карта не видела")
    item = _column(doc, table, column)
    created = _head_is_bare(_column_body(item))
    if created:
        head, was, content = _column_body(item), None, None
    else:
        head, was, content = column_control(doc, table, column)
    kind_words, kind_guid = _column_kind_words(item)
    if was == control:
        raise EditError(f"вложенный элемент колонки {column!r} уже {control}; менять нечего. "
                        "Его свойства правят операции элемента с адресом колонки: set_font и "
                        "set_event с column и nested=true")
    pair_seen = CORPUS_COLUMN_CONTROLS.get((kind_guid, control))
    if pair_seen is None and not unverified:
        raise EditError(
            f"{control} у колонки вида «{kind_words}» в образцах форм нет: "
            "у колонок этого вида бывают только "
            + ", ".join(k for (g, k), n in sorted(CORPUS_COLUMN_CONTROLS.items(),
                                                 key=lambda kv: -kv[1]) if g == kind_guid)
            + ". Позвать всё же можно — unverified=True")
    control_block = None if created else head[COLUMN_CONTROL]
    links = [] if created else control_block.get(CONTROL_LINKS) or []
    if links and control != "TextBox":
        raise EditError(
            f"у вложенного элемента колонки {column!r} {len(links)} связ(и) (`{CONTROL_LINKS}`), "
            "а они бывают только у поля ввода — 279 колонок из 279 в корпусе; у флажка и поля "
            "выбора нет ни одной. Унести их молча значило бы стереть чужую настройку: уберите их "
            "руками, если они не нужны, и повторите")
    value_type = copy.deepcopy(head.get(COLUMN_VALUE_TYPE))
    old_type = _type_words(value_type)
    said_type = ""
    if created:
        pass               # заведение элемента тип колонки не меняет: как платформа ведёт тип при этом, не проверялось
    elif kind_guid == VALUE_TABLE and control == "CheckBox":
        value_type = {PATTERN_MARK: "Pattern", PATTERN_TYPES: [{PATTERN_KIND: "B"}]}
        said_type = "тип значения колонки → Булево (так делает платформа)"
    elif kind_guid == VALUE_TABLE and control == "ComboBox":
        value_type = {PATTERN_MARK: "Pattern", PATTERN_TYPES: []}
        said_type = "тип значения колонки обнулён (так делает платформа)"
    if template is not None:
        if not isinstance(template, dict) or template.get(CONTROL_KIND) != CONTROL_KINDS[control]:
            raise EditError(f"template — это содержимое вложенного элемента вида {control}: "
                            f"объект с {CONTROL_KIND} = {CONTROL_KINDS[control]}, а пришло "
                            f"{template.get(CONTROL_KIND) if isinstance(template, dict) else template!r}")
        body, source = copy.deepcopy(template), "содержимое из template, взято как есть"
    else:
        key = control
        if control == "TextBox":
            letters = [t.get(PATTERN_KIND) for t in (value_type or {}).get(PATTERN_TYPES) or []
                       if isinstance(t, dict)]
            if letters not in (["S"], ["N"]):
                raise EditError(
                    f"поле ввода несёт описатель типа в самом теле, а тип колонки — "
                    f"{','.join(map(str, letters)) or 'пустой'}; шаблонов у редактора два — "
                    "строковое и числовое поле ввода (их написала платформа), — а тело иного "
                    "типа устроено иначе (вид значения `u3` следует за типом). "
                    "Дайте template — содержимое поля ввода того же типа из другой колонки")
            key = f"TextBox-{letters[0]}"
        body, _sample_type = _templates.column_control(key)
        body, old_said = old_control(doc, find_element(doc, table).element, body, key, unverified)
        if control == "TextBox":
            body[TEXTBOX_PATTERN] = copy.deepcopy(value_type)
            qualifiers = value_type[PATTERN_TYPES][0]
            props = body
            for step in TEXTBOX_PROPS:
                props = props[step]
            if key == "TextBox-N":
                for target, origin in zip(TEXTBOX_NUMBER, PATTERN_NUMBER):
                    props[target] = qualifiers.get(origin)
            else:
                props[TEXTBOX_LENGTH] = qualifiers.get(PATTERN_LENGTH) or 0
        source = f"шаблон вложенного поля {key}" + (f" ({old_said})" if old_said else "")
    # Последний вопрос — к корпусу, по трём признакам: тип значения колонки после смены (у таблицы
    # значений его ставит сама операция, у прочих он прежний). Спрашивается до первой правки
    # документа: отказ документ не трогает.
    letters = _type_letters(value_type)
    seen = CORPUS_COLUMN_CONTROL_TYPES.get((kind_guid, control, letters))
    if seen is None and pair_seen is not None and not unverified:
        known = [(sig, n) for (g, k, sig), n in CORPUS_COLUMN_CONTROL_TYPES.items()
                 if (g, k) == (kind_guid, control)]
        raise EditError(
            f"{control} у колонки вида «{kind_words}» с типом значения {_type_words(value_type)} "
            f"(буквы {letters}) в образцах форм нет: тип колонки у таких элементов — "
            + ", ".join(str(sig) for sig, n in sorted(known, key=lambda kv: -kv[1]))
            + ". Как платформа ведёт тип колонки при такой смене, не проверялось: проверены только смена "
            "поля ввода на поле ВЫБОРА у колонки табличной части (тип не тронут) и смена на флажок "
            "у таблицы значений (тип стал Булево). Операция тип "
            "колонки не трогает, и форма вышла бы такой, какой в образцах форм нет. Позвать "
            "всё же можно — unverified=True")
    # Версия тела — версия формы: шаблоны вложенных элементов — версии 16, и в форму другой версии
    # тело встаёт только с unverified. Тоже до первой правки.
    said_version = _version_check(doc, _design.content_versions(control, body),
                                  "set_column_control", unverified, kind=control)
    if created:
        empty = 0
        new = _reshaped_head(head, False, {"guid": schema.ELEMENT_GUIDS[control]},
                             {CONTROL_ELEMENT: {PACKED_CONTENT: body, PACKED_EMPTY: 0}, CONTROL_LINKS: []})
        head.clear()
        head.update(new)
    else:
        old_element = control_block.get(CONTROL_ELEMENT) or {}
        empty = old_element.get(PACKED_EMPTY) or 0
        control_block[CONTROL_ELEMENT] = {PACKED_CONTENT: body, PACKED_EMPTY: 0}
        head[COLUMN_CONTROL_TYPE] = {"guid": schema.ELEMENT_GUIDS[control]}
        if said_type:
            head[COLUMN_VALUE_TYPE] = value_type
    parts = [f"{table}/{column}: вложенный элемент "
             + (f"заведён у колонки без элемента → {control}" if created else f"{was} → {control}") + f" ({source})"]
    if said_type:
        parts.append(f"{said_type}, было {old_type}")
    if empty:
        parts.append(f"пустых кусков за прежним телом было {empty} — у нового их нет, как у "
                     "большинства блоков")
    if said_version:
        parts.append(said_version)
    what = f"{control} у колонки вида «{kind_words}» с типом значения {letters}"
    if created:
        return ("; ".join(parts) + ", голова колонки на одну позицию длиннее, тип значения не тронут"
                + _on_corpus("set_column_control/nested", f"колонка вида «{kind_words}» с элементом {control}", True)
                + _on_corpus("set_column_control/control", what, seen, counted="таких колонок"))
    if template is None and (kind_guid, was, control, letters) == ROUND10_COLUMN_CONTROL:
        return "; ".join(parts) + f"; {what}: {ROUND10_COLUMN_CONTROL_NOTE}"
    return "; ".join(parts) + _on_corpus("set_column_control/control", what, seen,
                                         counted="таких колонок")


COLUMN_TYPE_KINDS = ("S", "N", "D", "B")


def column_type_block(spec):
    """Блок типа колонки по описанию `{"kind": "S"|"N"|"D"|"B", …}` — в виде самых частых записей корпуса (строка без длины `{S}` либо `{S, длина, u2 = 1}`,
    число `{N, разрядность, дробная часть, неотрицательное}`, дата `{D, date_fractions}` или `{D}` — дата и время, булево `{B}`). Невиданное — отказ словами."""
    if not isinstance(spec, dict) or spec.get("kind") not in COLUMN_TYPE_KINDS:
        raise EditError(f"тип колонки — объект с kind {', '.join(COLUMN_TYPE_KINDS)} (`{{\"kind\": \"N\", \"digits\": 15, \"fraction\": 3}}`), а пришло {spec!r}")
    kind = spec["kind"]
    allowed = {"S": {"length"}, "N": {"digits", "fraction", "fraction_digits", "nonnegative"}, "D": {"date", "date_fractions"}, "B": set()}[kind]
    stray = sorted(set(spec) - {"kind"} - allowed)
    if stray:
        raise EditError(f"у типа {kind} ключей {', '.join(map(repr, stray))} нет; бывают {', '.join(sorted(allowed)) or 'никаких'}")

    def whole(key, low):
        value = spec.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < low:
            raise EditError(f"{key} — целое не меньше {low}, а пришло {value!r}")
        return value
    if kind == "S":
        if spec.get("length") is None:
            return {PATTERN_KIND: "S"}
        return {PATTERN_KIND: "S", PATTERN_LENGTH: whole("length", 1), "u2": 1}
    if kind == "N":
        digits = whole("digits", 1)
        fraction = spec.get("fraction", spec.get("fraction_digits", 0))
        if not isinstance(fraction, int) or isinstance(fraction, bool) or not 0 <= fraction <= digits:
            raise EditError(f"fraction — целое от 0 до разрядности {digits}, а пришло {fraction!r}")
        sign = spec.get("nonnegative", False)
        if not isinstance(sign, bool):
            raise EditError(f"nonnegative — true или false, а пришло {sign!r}")
        return {PATTERN_KIND: "N", PATTERN_NUMBER[0]: digits, PATTERN_NUMBER[1]: fraction, PATTERN_NUMBER[2]: sign}
    if kind == "D":
        from . import datatype as _types
        part = _types.date_part(spec)       # слово `date` либо буква `date_fractions`: один разбор с `attributes` описания и описателем реквизита
        if part == "Time":
            raise EditError("состав даты колонки: Date (дата) или DateTime (дата и время, без ключа состава); время (`Time`, буква `T`) "
                            "в нестроковом поле колонки не проверялось")
        return {PATTERN_KIND: "D", "date_fractions": "D"} if part == "Date" else {PATTERN_KIND: "D"}
    return {PATTERN_KIND: "B"}


def _check_data(item, column, checkbox):
    """Данные колонки таблицы значений: у колонки с флажком — «ДанныеФлажка» = имя колонки, «Данные» пусты (корпус: у 61 из 86 колонок с флажком и булевым типом,
    у остальных чаще «Данные» = имя при «ДанныеФлажка» пустом); у остальных колонок — «Данные» = имя, «ДанныеФлажка» пусты. Возвращает слова, если что-то сменилось."""
    body = item[COLUMN_BODY]
    if checkbox:
        if body.get(COLUMN_CHECK_DATA) == column and body.get(COLUMN_DATA) == "":
            return ""
        body[COLUMN_DATA], body[COLUMN_CHECK_DATA] = "", column
        return f"«Данные» пусты, «ДанныеФлажка» = {column!r} (так у колонок корпуса с флажком: без этого значение показывается текстом «Да»/«Нет»)"
    if body.get(COLUMN_CHECK_DATA):
        body[COLUMN_DATA], body[COLUMN_CHECK_DATA] = column, ""
        return f"«ДанныеФлажка» пусты, «Данные» = {column!r}"
    return ""


def set_column_type(doc, table, column, type, unverified=False):
    """Тип значения колонки таблицы или дерева значений: `{"kind": "S"|"N"|"D"|"B", …}` — тип колонки (`value_type` головы) и описатель её вложенного поля ввода
    пишутся вместе, как у колонок корпуса (колонок с типом поля ввода, равным типу колонки, подавляющее большинство). Платформа создаёт такие колонки при
    открытии формы по этой записи, поэтому код, заполняющий таблицу, их уже не добавляет.

    Строка — длина в разрядность поля (`digits`); число — разрядность, дробная часть, знак (поле: `digits`, `fraction_digits`, `wrap` снят, как у образца числа);
    дата — кнопка выбора, `wrap` снят, `date_fractions` `Date`/`DateTime` (у даты без времени ещё `u22` = 2, как у колонок корпуса); булево — флажок
    (`set_column_control`) с режимом редактирования «Непосредственно». Колонка — только вида таблицы значений, вложенный элемент — поле ввода (у булева — любой
    из двух, флажок ставится сам). Правится на месте: обработчики и шрифты вложенного поля остаются."""
    from .setprop import set_property
    block = column_type_block(type)
    place = find_element(doc, table)
    members = _columns_of(doc, table)[COLUMN_ITEMS]
    item = next((c for c in members if _column_name(c) == column), None)
    if item is None:
        raise EditError(f"колонки {column!r} у {table!r} нет; есть: {', '.join(str(_column_name(c)) for c in members)}")
    if (item.get(COLUMN_TYPE) or {}).get("guid") != VALUE_TABLE:
        raise EditError(f"тип колонки ставит set_column_type у колонки таблицы или дерева значений; колонка {column!r} — "
                        f"«{_column_kind_words(item)[0]}»: тип колонки табличной части и списка берётся у реквизита объекта")
    head = _column_body(item)
    kind, content = nested_control(head, f"колонки {column!r}")
    pattern = {PATTERN_MARK: "Pattern", PATTERN_TYPES: [block]}
    words = []
    if block[PATTERN_KIND] == "B":
        if kind == "TextBox":
            words.append(set_column_control(doc, table, column, "CheckBox", unverified=unverified))
        elif kind != "CheckBox":
            raise EditError(f"у колонки {column!r} вложенный элемент {kind}: булева колонка — флажок")
        words.append(set_property(doc, element=table, column=column, name="edit_mode", value="Directly", unverified=unverified))
        head[COLUMN_VALUE_TYPE] = pattern
        words.append(_check_data(item, column, True))
        return f"{table}/{column}: тип значения → Булево; " + "; ".join(words)
    if kind != "TextBox":
        raise EditError(f"у колонки {column!r} вложенный элемент {kind}, а поле ввода — единственный вид, в котором колонка получает тип {block[PATTERN_KIND]}: "
                        "верните поле ввода (`set_column_control`)")
    props = content
    for step in TEXTBOX_PROPS:
        props = props[step]
    was = _type_words(head.get(COLUMN_VALUE_TYPE))
    back = _check_data(item, column, False)
    head[COLUMN_VALUE_TYPE] = copy.deepcopy(pattern)
    content[TEXTBOX_PATTERN] = copy.deepcopy(pattern)
    letter = block[PATTERN_KIND]
    props["digits"] = block.get(PATTERN_LENGTH, 0) if letter == "S" else (block[PATTERN_NUMBER[0]] if letter == "N" else 0)
    if letter == "N":
        props["fraction_digits"], props["nonnegative"] = block[PATTERN_NUMBER[1]], block[PATTERN_NUMBER[2]]
    props["wrap"] = letter == "S"
    if letter == "D":
        props["choice_button"] = True
        props["date_fractions"] = "Date" if block.get("date_fractions") else "DateTime"
        props["u22"] = 2 if block.get("date_fractions") else 0
    return (f"{table}/{column}: тип значения колонки и её поля ввода {was} → {_type_words(pattern)}" + (f"; {back}" if back else "") + "; "
            "записано как у колонок корпуса — описатель поля равен типу колонки"
            + _on_corpus("set_column_type", f"колонка таблицы значений типа {letter} с полем ввода того же типа", True))


def _type_letters(pattern):
    """Буквы типа значения — ключ `CORPUS_COLUMN_CONTROL_TYPES`: без повторов и по алфавиту («#+S»,
    «B+D+N+S»), «пустой» — если типов нет. Квалификаторов здесь нет намеренно: набор букв закрыт, а
    набор блоков с квалификаторами — нет.
    """
    types = (pattern or {}).get(PATTERN_TYPES) if isinstance(pattern, dict) else None
    if not types:
        return "пустой"
    return "+".join(sorted({str(item.get(PATTERN_KIND)) if isinstance(item, dict) else "?"
                            for item in types}))
