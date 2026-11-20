"""Вариативность позиций по корпусу.

Ключ — пара «якорь, адрес от якоря». Якорей два вида: корень формы и элемент (блок, у которого есть блок имени
`{14,"…"}`). Считать адреса от корня формы бесполезно: у одного и того же поля ввода адрес зависит от числа
элементов перед ним.

Якорь элемента называется по имени типа (`Element.Label`), как в журнале и в карте. Для типа, которого карта не
знает, якорь называется `Element.<GUID>`.

Позиция получает класс: `const` — по корпусу не меняется, `varies` — меняется, `struct` — различается строением.
У блока нет собственных значений, поэтому его постоянство определяется длиной: одна длина во всём корпусе —
`const`, разные длины — `struct`. Позиция, которая в одних формах является блоком, а в других скаляром, тоже
`struct`.

Классификация намеренно грубая: она отбирает позиции для карты и для билетов, а не объясняет их смысл.

Позиции со счётными списками сводка объединяет в одну строку: у блока содержимого контейнера формы и панели
номер позиции после первого списка в каждой форме свой (`schema.Runs`), а ключ сводки — число, поэтому одна
строка может объединять значения разных свойств. Наружу это не попадает: `FORMAT-open.md` такие строки не
перечисляет (`docs._floating`). Точный подсчёт потребовал бы адресовать позиции отрезком (`1/2/1/1/L6+0`); это
не реализовано.

У статистики два вывода: полный `to_json` (все значения) и `summary` (вход раздела «Открытые позиции» в
`FORMAT.md`). Для обоих действует один отбор: непрозрачные поддеревья (`OPAQUE_SUBTREES`), внутрь встроенного
документа обход не заходит. Сводка отбирает ещё по четырём правилам: только якоря из карты (незнакомый тип
попадает в заявку `unknown_types`), только позиции из нескольких форм, только позиции, доля которых среди
наблюдений якоря не меньше `SUMMARY_MIN_SHARE_PERCENT` процента, и не больше `SUMMARY_VALUES` значений длиной до
`SUMMARY_VALUE_CHARS` знаков.

Сводка не содержит данных форм: строки (имена, подписи, тексты), блоки base64 и GUID, которые не являются постоянными
значениями платформы, в неё не попадают. Вместо них у позиции стоит одна запись на вид — `{"other_texts": N}`, `{"other_guids": N}`,
`{"other_base64": N}`, где N — число разных значений, а рядом число наблюдений. Постоянные значения платформы остаются: числа,
GUID типов элементов и нулевой GUID (`PLATFORM_GUIDS`), прочий GUID, который встречается в формах не меньше чем
`PLATFORM_GUID_CONFIGS` разных конфигураций (`common_guids`), и строки из `PLATFORM_STRINGS`. Идентификатор объекта одной
конфигурации в формах других не встречается, сколько бы раз он ни повторялся в своей.

Файл сводки собран по образцам форм и формам платформы, а набор общих GUID — по образцам. Другой набор форм даст другую
сводку, поэтому пересборка (`frm_json.py stat --commit-summary`) на другом наборе файл меняет.
"""
import collections
import json
import pathlib
import re
from dataclasses import dataclass, field

from .diff import name_block_index
from .guids import ELEMENT_GUIDS, element_type_name
from .json0 import (Dec, decode0, dumps as json0_dumps, dumps_line,
                    loads as json0_loads)
from .tree import Node, Scalar, read_file
from .datapaths import DATA_DIR

KIND_FORM = "Form"
TOP_VALUES = 50
SUMMARY_VALUES = 10
SUMMARY_VALUE_CHARS = 80
SUMMARY_MIN_FORMS = 2
# Минимальная доля наблюдений якоря, при которой позиция попадает в сводку. Доля считается от наблюдений якоря,
# а не всего корпуса: иначе у редкого типа элемента пропало бы всё строение.
SUMMARY_MIN_SHARE_PERCENT = 1
# Строки, которые платформа пишет сама: коды языков, буквы вида значения, маркер описателя, имена полей пары «значение —
# представление», шрифты по умолчанию. Всё прочее — данные форм и в сводку не идёт.
PLATFORM_STRINGS = frozenset({"", "ru", "en", "de", "ru_RU", "U", "#", "S", "N", "D", "B", "Pattern", "Value", "Presentation",
                              "Arial", "Verdana", "MS Shell Dlg"})
# GUID типов элементов (их знает карта) и нулевой GUID — значения платформы при любом числе наблюдений. Любой другой GUID —
# постоянная платформы (набор, класс) только если он есть в формах не меньше чем `PLATFORM_GUID_CONFIGS` конфигураций;
# иначе это идентификатор объекта конфигурации, то есть данные. Число наблюдений тут не мерило: большая конфигурация набирает
# любое число повторов сама.
PLATFORM_GUIDS = frozenset({"00000000-0000-0000-0000-000000000000", *ELEMENT_GUIDS.values()})
PLATFORM_GUID_CONFIGS = 3
GUID_TEXT = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
# Запись о значениях, не попавших в сводку: вид значения → ключ записи.
OTHER_VALUES = {"str": "other_texts", "guid": "other_guids", "base64": "other_base64"}
SUMMARY_PATH = DATA_DIR / "corpus_stat.json"
UNKNOWN_PATH = DATA_DIR / "corpus_unknown.json"
# Длины блоков, которых нет в сводке корпуса, но которые платформа записывает в формах, сохранённых конфигуратором.
PLATFORM_LENS_PATH = DATA_DIR / "platform_lens.json"

# Непрозрачные поддеревья: блоки, внутри которых лежит содержимое чужого документа, а не строение формы. Обход
# учитывает сам блок как любую другую позицию (класс, длину, число форм), но внутрь не заходит. Внутри блока
# `2/11` поля табличного документа лежат строки, колонки и ячейки встроенного документа: позиция `2/11/875/0`
# описывает не формат формы, а чью-то печатную форму.
#
# Цена такого решения: `validate` ничего не говорит о длинах внутри такого блока, а «Открытые позиции» их не
# перечисляют. Элемент внутри непрозрачного блока не станет якорем. Пустая заявка `unknown_types` означает, что
# типов вне карты не осталось.
OPAQUE_SUBTREES = {
    ("Element.SpreadsheetDocumentField", "2/11"):
        "встроенный табличный документ: строки, колонки и ячейки самого документа",
}


@dataclass
class Position:
    kind: str
    path: str
    forms: int = 0
    kinds: dict = field(default_factory=dict)
    values: dict = field(default_factory=dict)
    lens: dict = field(default_factory=dict)


def element_kind(node):
    """Возвращает `Element.<ИмяEN>` для блока элемента; `None`, если блок не элемент.

    Признак элемента один для всего навыка — блок имени (`diff.name_block_index`). Если для GUID имя не нашлось,
    якорь называется самим GUID: незнакомый тип должен попасть в статистику под собственным обозначением."""
    if not isinstance(node, Node) or name_block_index(node) is None:
        return None
    first = node.children[0] if node.children else None
    if isinstance(first, Scalar) and first.kind == "GUID":
        return f"Element.{element_type_name(first.text) or first.text}"
    return "Element.?"


def _bump(counter, key):
    counter[key] = counter.get(key, 0) + 1


def value_key(value):
    """Ключ счётчика: словарь нельзя хешировать, а его текст теряет вид значения.

    GUID, base64 и целое с ведущим нулём приходят с уровня 0 словарями (`{"guid": …}`, `{"num": …}`), а ключом
    счётчика словарь быть не может. Поэтому ключ — пара «вид, текст», а `value_out` возвращает наружу настоящий
    словарь.

    С дробным числом другая проблема: `Dec` — подкласс `str`, и число `1.5` с строкой `"1.5"` попали бы в один
    ключ. Наружу дробное отдаётся текстом числа, потому что своей обёртки на уровне 0 у него нет.

    Функция публичная: тем же ключом пользуется сопоставление кандидатов, а `value_out` и `cell` печатают
    значения обратно."""
    if isinstance(value, dict):
        if "base64" in value:
            # Раскладка в ключ не входит: блок, записанный одной строкой, содержит то же значение, что
            # записанный строками по 64 знака.
            return ("base64", value["base64"])
        (kind, text), = value.items()
        return (kind, text)
    if isinstance(value, Dec):
        return ("dec", str(value))
    return value


def value_out(key):
    if isinstance(key, tuple):
        kind, text = key
        return Dec(text) if kind == "dec" else {kind: text}
    return key


# Порядок видов значения в сводке. Python не умеет сравнивать между собой целое, дробное, строку и обёртку, а на
# одной позиции они встречаются вместе, поэтому сначала сортируется вид, потом текст. `num` — целое, текст
# которого не совпадает с числом (`00010101000000`), он стоит сразу после целого. `empty` — пустое значение
# файла (`0,,60`, на уровне 0 оно называется `null`) — стоит последним, чтобы порядок прежних видов не
# изменился.
_VALUE_ORDER = {"int": 0, "num": 1, "dec": 2, "str": 3, "guid": 4, "base64": 5, "empty": 6}


def order_key(key):
    """Канонический порядок значения — второй ключ сортировки после частоты.

    Целые числа сортируются как числа, остальное — как текст внутри своего вида. Вид, которого здесь нет, —
    отказ со словами: значения создаёт `value_key`, и новый вид нужно назвать здесь.

    Функция публичная: в том же порядке раскладывает пары значений таблица сопряжённости, и её файл не должен
    зависеть от порядка обхода корпусов."""
    if key is None:
        # Пустое значение приходит в ключ счётчика как `None` (`value_key` его не оборачивает) и не попадает ни
        # в одну ветку ниже: `None` не является ни целым, ни строкой, ни парой.
        return (_VALUE_ORDER["empty"], 0, "")
    if isinstance(key, tuple):
        kind, text = key                       # ("guid" | "base64" | "dec", текст)
        if kind not in _VALUE_ORDER:
            raise ValueError(f"вида значения {kind!r} порядок сводки не знает")
        return (_VALUE_ORDER[kind], 0, text)
    if isinstance(key, int) and not isinstance(key, bool):
        return (_VALUE_ORDER["int"], key, "")
    if isinstance(key, str):
        return (_VALUE_ORDER["str"], 0, key)
    raise ValueError(f"значение {type(key).__name__} порядок сводки не знает")


def top_values(values, limit):
    """Первые `limit` значений по убыванию частоты; равночастотные идут в каноническом порядке.

    `Counter.most_common` отдаёт равночастотные значения в порядке первой встречи, то есть в порядке обхода
    корпуса, а сводка хранится в git. Тогда перестановка каталогов в `frm_json.py stat A B` меняла бы файл, хотя
    данные те же. Поэтому используется полный порядок вместо `most_common`."""
    return sorted(values.items(), key=lambda kv: (-kv[1], order_key(kv[0])))[:limit]


def _cut(value, chars):
    """Значение длиннее предела записывается обрезанным и с пометкой.

    Молчаливая обрезка хуже её отсутствия: многоточие в конце показывает читателю, что перед ним начало
    значения. Дробное число не обрезается при любой длине: обрезанное число — это другое число, и выглядит оно
    как настоящее."""
    if isinstance(value, Dec):
        return value
    if isinstance(value, str) and len(value) > chars:
        return value[:chars] + "…"
    if isinstance(value, dict):
        (kind, text), = value.items()
        return {kind: text[:chars] + "…"} if isinstance(text, str) and len(text) > chars else value
    return value


def value_kind(key):
    """Вид значения по ключу счётчика (`value_key`): `str`, `guid`, `base64` или `None` для чисел и пустого значения."""
    if isinstance(key, str):
        return "str"
    if isinstance(key, tuple) and key[0] in ("guid", "base64"):
        return key[0]
    return None


def common_guids(paths, config_of):
    """Множество GUID (строчными), которые лежат в формах не меньше чем `PLATFORM_GUID_CONFIGS` разных конфигураций.

    `paths` — файлы форм, `config_of(путь)` — имя конфигурации формы (`census.config_of`). GUID ищется по тексту файла, где бы он
    ни лежал: такое множество шире тех GUID, что есть в сводке, и это нужно, чтобы одно правило обслуживало и сводку, и границу
    значений (`props.summary`)."""
    seen = {}
    for path in paths:
        config = config_of(str(path))
        text = pathlib.Path(path).read_bytes().decode("utf-8", "replace")
        for guid in set(GUID_TEXT.findall(text)):
            seen.setdefault(guid.lower(), set()).add(config)
    return frozenset(g for g, configs in seen.items() if len(configs) >= PLATFORM_GUID_CONFIGS)


def is_platform_value(key, count, common=frozenset()):
    """Значение остаётся в сводке, если его пишет платформа, а не автор формы (правила — у `PLATFORM_STRINGS` и
    `common_guids`; `common` — множество общих GUID). Число, дробное число и пустое значение — всегда. `count` оставлен для
    вызывающих: число наблюдений значения не решает."""
    kind = value_kind(key)
    if kind == "str":
        return key in PLATFORM_STRINGS
    if kind == "guid":
        return key[1] in PLATFORM_GUIDS or key[1].lower() in common
    return kind is None


def is_other(value):
    """Запись `{"other_…": N}` о значениях, которых в сводке нет."""
    return isinstance(value, dict) and len(value) == 1 and next(iter(value)) in OTHER_VALUES.values()


def summary_values(values, limit=SUMMARY_VALUES, common=frozenset()):
    """Значения позиции для сводки: до `limit` постоянных значений платформы по убыванию частоты, затем по одной записи
    `{"other_…": число разных}` с числом наблюдений на каждый вид отброшенных значений."""
    kept = {k: n for k, n in values.items() if is_platform_value(k, n, common)}
    rows = [[_cut(value_out(v), SUMMARY_VALUE_CHARS), n] for v, n in top_values(kept, limit)]
    for kind, name in OTHER_VALUES.items():
        dropped = [n for k, n in values.items() if value_kind(k) == kind and k not in kept]
        if dropped:
            rows.append([{name: len(dropped)}, sum(dropped)])
    return rows


def _visit(node, kind, path, stats, seen):
    for i, child in enumerate(node.children):
        here = path + (i,)
        child_kind, child_path = kind, here
        if isinstance(child, Node):
            ek = element_kind(child)
            if ek:
                child_kind, child_path = ek, ()
        key = (kind, "/".join(str(x) for x in here))
        pos = stats.setdefault(key, Position(kind=key[0], path=key[1]))
        if key not in seen:
            seen.add(key)
            pos.forms += 1
        if isinstance(child, Node):
            _bump(pos.lens, len(child.children))
            # Непрозрачный блок учитывается сам (его длина уже посчитана строкой выше), а внутрь обход не
            # заходит: там содержимое чужого документа, а не строение формата.
            if key not in OPAQUE_SUBTREES:
                _visit(child, child_kind, child_path, stats, seen)
        else:
            _bump(pos.kinds, child.kind)
            _bump(pos.values, value_key(decode0(child)))


def walk_blocks(node, kind=KIND_FORM, path=(), parent=None):
    """Блоки дерева с тем же адресом, под которым `collect_root` считает их длины: `(якорь, адрес от якоря, блок, родительский блок)`.

    Обход повторяет `_visit` (якорь меняется на элементе, внутрь непрозрачных поддеревьев не заходит); нужен проверке длин,
    чтобы по найденной длине дойти до самого блока и посмотреть на его строение."""
    for i, child in enumerate(node.children):
        here = path + (i,)
        child_kind, child_path = kind, here
        if isinstance(child, Node):
            ek = element_kind(child)
            if ek:
                child_kind, child_path = ek, ()
        if isinstance(child, Node):
            key = (kind, "/".join(str(x) for x in here))
            yield kind, key[1], child, node
            if key not in OPAQUE_SUBTREES:
                yield from walk_blocks(child, child_kind, child_path, node)


def pages_slot(kind, path):
    """Место, где может лежать список страниц: блок прямо в теле панели (`2/1/<n>` от якоря `Element.Panel`) либо в блоке контейнера формы
    (`1/2/1/1/<n>` от корня). Номер `n` у разных форм разный — перед списком разное число списков стиля."""
    parts = path.split("/")
    return (kind == "Element.Panel" and len(parts) == 3 and parts[:2] == ["2", "1"]) or (kind == KIND_FORM and len(parts) == 5 and parts[:4] == ["1", "2", "1", "1"])


def pages_list(node):
    """Блок «список страниц панели» `{флаг, число страниц, запись страницы × число}` — по строению, а не по адресу: у панелей разного
    строения (число списков стиля перед ним) он стоит на разных позициях. Возвращает число страниц или `None`.

    Признак: второй член — целое число N ≥ 1, членов ровно N + 2, все после второго — блоки одной длины от 8 до 12."""
    kids = node.children if isinstance(node, Node) else ()
    if len(kids) < 3 or not all(isinstance(k, Scalar) for k in kids[:2]):
        return None
    try:
        count = int(kids[1].text)
    except (TypeError, ValueError):
        return None
    records = kids[2:]
    if count < 1 or len(records) != count or not all(isinstance(k, Node) for k in records):
        return None
    if len({len(k.children) for k in records}) != 1 or not 8 <= len(records[0].children) <= 12:
        return None
    return count


def collect_root(root, stats=None):
    stats = stats if stats is not None else {}
    _visit(root, KIND_FORM, (), stats, set())
    return stats


def collect(paths):
    stats = {}
    for path in paths:
        collect_root(read_file(path), stats)
    return stats


def classify(pos):
    if pos.lens and pos.kinds:
        # В одних формах блок, в других скаляр: различается строение, а не значение.
        return "struct"
    if len(pos.lens) > 1 or len(pos.kinds) > 1:
        return "struct"
    if pos.lens:
        # Блок: собственных значений у него нет, постоянство определяется длиной, и длина здесь одна.
        return "const"
    return "const" if len(pos.values) == 1 else "varies"


def to_json(stats):
    """Полный вывод: все значения до `TOP_VALUES`, без обрезки текста.

    Обрезан ли перечень, видно по сравнению `shown` и `distinct`, а не по булеву полю: писатель уровня 0 булевых
    значений не знает (`True` в Python равно единице)."""
    out = {}
    for (kind, path), pos in sorted(stats.items()):
        top = top_values(pos.values, TOP_VALUES)
        out.setdefault(kind, {})[path] = {
            "class": classify(pos), "forms": pos.forms, "distinct": len(pos.values),
            "kinds": dict(sorted(pos.kinds.items())),
            "lens": {str(k): v for k, v in sorted(pos.lens.items())},
            "values": [[value_out(v), n] for v, n in top], "shown": len(top)}
    return out


def is_map_anchor(kind):
    """Якорь, который читает карта: корень формы и элемент известного типа.

    Незнакомый тип в сводку не входит: строка о нём среди позиций карты выглядела бы как поле, которое никто не
    разбирает. Такой тип попадает в заявку `unknown_types` вместе с данными о его распространённости."""
    if kind == KIND_FORM:
        return True
    name = kind.split(".", 1)[1] if kind.startswith("Element.") else ""
    return name in ELEMENT_GUIDS


def anchor_forms(stats):
    """Сколько форм у каждого якоря: максимум `forms` по его позициям.

    Первая позиция якоря присутствует в каждой форме, где он встретился (пустых узлов не бывает), поэтому
    максимум равен числу таких форм."""
    out = {}
    for (kind, _), pos in stats.items():
        if pos.forms > out.get(kind, 0):
            out[kind] = pos.forms
    return out


def summary(stats, common=frozenset()):
    """Сводка для git: якоря карты, позиции не из одной формы и с долей не меньше заданного процента, значения с
    двумя пределами.

    Сводка служит входом раздела «Открытые позиции» в `FORMAT.md` и источником чисел наблюдений в карте,
    поэтому она детерминирована и отобрана. У блока рядом с классом стоит `lens`: без него строка блока ничего
    бы не говорила (значений у блока нет).

    Минимальная доля (`SUMMARY_MIN_SHARE_PERCENT`) считается от числа форм своего якоря (`anchor_forms`):
    позиция, которая встречается реже процента таких форм, характерна для отдельной конфигурации, а не для
    формата. Цена: `validate` ничего не говорит о такой позиции, а «Открытые позиции» её не перечисляют.

    Детерминированность означает независимость от порядка обхода: порядок значений задаёт `top_values`, а `lens`
    и `kinds` сортируются по своему ключу (длина, вид скаляра)."""
    out = {}
    forms_at = anchor_forms(stats)
    for (kind, path), pos in sorted(stats.items()):
        if not is_map_anchor(kind) or pos.forms < SUMMARY_MIN_FORMS:
            continue
        if pos.forms * 100 < forms_at[kind] * SUMMARY_MIN_SHARE_PERCENT:
            continue
        out.setdefault(kind, {})[path] = {
            "class": classify(pos), "forms": pos.forms, "distinct": len(pos.values),
            # Ключи длины приводятся к строкам: JSON не хранит числа в ключах, и без приведения `summary()` и
            # `load_summary()` возвращали бы разное.
            "lens": {str(k): v for k, v in sorted(pos.lens.items())},
            "values": summary_values(pos.values, common=common)}
    return out


def unknown_types(stats):
    """Заявка на расширение карты: типы элементов, которых нет в `guids`.

    Из сводки они исключены (`is_map_anchor`), и без этой таблицы информация о них пропала бы совсем.

    В таблице три числа, и каждое отвечает на свой вопрос. `forms` — в скольких формах встретился тип, от этого
    зависит, стоит ли его описывать. `instances` — сколько всего экземпляров типа. `positions` — насколько
    сложен тип внутри, то есть сколько полей придётся описать в карте.

    `instances` считается по позиции `0` якоря, где лежит GUID типа, по одному скаляру на экземпляр."""
    rows = {}
    for (kind, path), pos in sorted(stats.items()):
        if is_map_anchor(kind) or not kind.startswith("Element."):
            continue
        row = rows.setdefault(kind.split(".", 1)[1],
                              {"guid": kind.split(".", 1)[1], "instances": 0, "forms": 0,
                               "positions": 0})
        row["positions"] += 1
        row["forms"] = max(row["forms"], pos.forms)
        if path == "0":
            row["instances"] = sum(pos.values.values())
    return [rows[g] for g in sorted(rows, key=lambda g: (-rows[g]["forms"], -rows[g]["instances"], g))]


def load_summary(path=None):
    """Читается тем же уровнем 0, которым пишется, иначе проверка обратным разбором не сошлась бы на дробных
    числах.

    `json0.loads` возвращает дробное `Dec`, как его отдаёт `summary`. Стандартный `json.loads` вернул бы
    `float`, и сравнение прогона с файлом молча расходилось бы."""
    path = pathlib.Path(path) if path else SUMMARY_PATH
    if not path.exists():
        return {}
    return json0_loads(path.read_text(encoding="utf-8"))


def load_platform_lens(path=None):
    """Длины блоков, которые платформа записывает в сохранённых ею формах и которых нет в корпусе: `{"lens": {якорь: {адрес: [длина, …]}},
    "pages": {якорь: {"counts": [число страниц, …], "record_lens": [длина записи страницы, …]}}, "forms": N}`; нет файла — пусто."""
    path = pathlib.Path(path) if path else PLATFORM_LENS_PATH
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_unknown(path=None):
    path = pathlib.Path(path) if path else UNKNOWN_PATH
    if not path.exists():
        return []
    return json0_loads(path.read_text(encoding="utf-8"))


def dump_summary(stats, indent=1, common=frozenset()):
    """Одна строка на позицию: дифф остаётся построчным, а размер втрое меньше, чем при отступах на всю глубину.
    Сразу видно, какая позиция изменилась.

    Строка пишется через `json0.dumps_line`, а не `json.dumps`: `Dec` — подкласс `str`, и стандартный писатель
    взял бы дробное в кавычки, из-за чего число `1.5` нельзя было бы отличить от строки `"1.5"`. Правило печати
    дробных чисел одно для всего навыка."""
    data = summary(stats, common)
    pad = " " * indent
    out = ["{"]
    kinds = sorted(data)
    for ki, kind in enumerate(kinds):
        out.append(f"{pad}{json.dumps(kind, ensure_ascii=False)}: " + "{")
        paths = sorted(data[kind])
        for pi, path in enumerate(paths):
            row = dumps_line({k: data[kind][path][k] for k in sorted(data[kind][path])})
            tail = "," if pi + 1 < len(paths) else ""
            out.append(f"{pad * 2}{json.dumps(path)}: {row}{tail}")
        out.append(pad + "}" + ("," if ki + 1 < len(kinds) else ""))
    out.append("}")
    return "\n".join(out) + "\n"


def dump_json(stats, indent=1):
    """Полный вывод в файл. Тем же писателем и по той же причине, что и сводка."""
    return json0_dumps(to_json(stats), indent=indent) + "\n"


def dump_unknown(stats, indent=1):
    """Заявка в файл. Тем же писателем, чтобы правило печати было одно для всех трёх файлов."""
    return json0_dumps(unknown_types(stats), indent=indent) + "\n"


def cell(value):
    """Значение в ячейке markdown-таблицы: обрезается и очищается от знаков, ломающих разметку.

    Вертикальная черта в строковом значении разорвала бы столбец, а перевод строки — строку таблицы.

    Функция публичная: её вызывают два места — таблица статистики (`to_markdown`) и таблицы `frm_codec.docs`
    («Открытые позиции», «Имя карты против корпуса»).

    Значение печатает `json0.dumps_line` — тот же писатель, что у сводки: GUID выглядит как `{"guid": …}`,
    строка берётся в кавычки (пустая строка не превращается в пустую ячейку), дробное число пишется без кавычек.

    После этого экранируется только вертикальная черта: перевод строки и возврат каретки писатель уже заменил
    экранированными знаками внутри строки JSON."""
    return dumps_line(_cut(value, SUMMARY_VALUE_CHARS)).replace("|", "\\|")


def to_markdown(stats):
    lines = []
    data = to_json(stats)
    for kind in sorted(data):
        rows = data[kind]
        counts = collections.Counter(r["class"] for r in rows.values())
        lines.append(f"## {kind}\n")
        lines.append(f"Позиций {len(rows)}: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) + "\n")
        lines.append("| адрес | класс | форм | значений | первые значения |")
        lines.append("|---|---|---|---|---|")
        for path in sorted(rows, key=lambda p: (p.count("/"), p)):
            r = rows[path]
            first = ", ".join(f"{cell(v)} ({n})" for v, n in r["values"][:5])
            lines.append(f"| `{path}` | {r['class']} | {r['forms']} | {r['distinct']} | {first} |")
        lines.append("")
    return "\n".join(lines)
