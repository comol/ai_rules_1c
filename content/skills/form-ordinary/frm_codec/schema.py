"""Карта формата: узел → позиция → имя, вид, источник знания.

Из карты порождаются `FORMAT.md`, `frm.schema.json` и оба направления уровня 1. У каждого поля есть вид источника
(`SOURCE_KINDS`): `doc` — документация, `lab` — проверка в предприятии, `lab-outside` — то же, но значение легло вне
узла подэлемента, `exp` — отдельный опыт, `round` — форму собрал кодек, и платформа её приняла, `corpus` — формы
конфигураций, `smoke` — проверка на образцовой форме. Умолчания у вида источника нет. У поля, узла, перечисления и
постоянного значения есть краткое примечание. Позиция без записи в карте зовётся `u<индекс>` и переносится как есть.
Узел с типом вне карты разбором не раскрывается: он остаётся сырым (`raw`)."""
import dataclasses
import difflib
import sys
from dataclasses import dataclass, field

from .guids import (ELEMENT_GUIDS, FORM_CONTAINER_GUID, PAL_GUIDS, X2_GUIDS,
                    element_type_name)
# Правило «текст целого переживает `int`» живёт в одном месте на весь навык (`json0`): по нему
# решают и вид значения уровня 0, и демоция уровня 1, и выбор варианта по первому скаляру.
from .json0 import exp_int, int_text_survives
from .tree import Node
# Виды полей приезжают из `frm_codec.kinds` — единственного места, где они объявлены, — и
# перевыставляются здесь, чтобы у карты был один вход.
from .kinds import INT, DEC, STR, GUID, B64, BOOL, ENUM, TYPE, NODE, BITS, INT_EXP, INT_DEC

SOURCE_KINDS = ("doc", "lab", "lab-outside", "exp", "round", "corpus", "smoke")

# Имя остатка битового слова.
BITS_REST = "rest"

# Вид скаляра ФАЙЛА по виду поля КАРТЫ.
_SCALAR_KIND_OF = {INT: "INT", DEC: "DEC", STR: "STR", GUID: "GUID", B64: "B64",
                   BOOL: "INT", ENUM: "INT", TYPE: "GUID", BITS: "INT"}


class SchemaError(ValueError):
    pass


def fits_scalar(slot, item):
    """Подходит ли скаляр ФАЙЛА виду, который карта объявила у этой позиции."""
    if not isinstance(slot, F):
        return False
    if slot.kind == INT_EXP:
        # Две записи одного целого: целым, пока текст переживает `int`, и экспонентой, пока значение
        # целое.
        if item.kind == "INT":
            return int_text_survives(item.text)
        return item.kind == "DEC" and exp_int(item.text) is not None
    if slot.kind == INT_DEC:
        # Целое (единица) и десятичная дробь: два вида одной величины.
        return item.kind == "DEC" or (item.kind == "INT" and int_text_survives(item.text))
    if item.kind != _SCALAR_KIND_OF.get(slot.kind):
        return False
    if item.kind == "INT" and not int_text_survives(item.text):
        # Целое с ведущим нулём на уровне 0 записывается обёрткой `{"num": …}`, и под именем вида INT ему не
        # место: разбор вернул бы из имени число, а число потеряло бы знаки — файл собрался бы
        # другим.
        return False
    if slot.kind == BOOL:
        # Число вне 0/1 имя опровергает: флаг двузначен по определению, и третьего значения у него
        # не бывает.
        return item.text in ("0", "1")
    if slot.kind == TYPE:
        return element_type_name(item.text) is not None
    return True


# Имена GUID типов реквизитов формы. Типы платформы без квалификаторов пишутся блоком `{"#", GUID}`, как ссылки на объекты конфигурации; три
# GUID корпуса принадлежат типам самой платформы. Перепись 4 993 форм основного снимка: реквизиты формы с блоком `{"#", GUID}` единственным
# типом, привязанные к элементам. Вид определён по привязанному элементу: таблица значений — табличное поле (563 из 563 привязок), дерево
# значений — табличное поле (194 из 194; от таблицы значений отличается первой колонкой «Иерархия» и тремя битами слова флагов), список значений —
# поле списка (55 из 77, ещё 9 табличных полей с колонками `fbacf851-…` и 13 полей ввода).
GUID_NAMES = {
    "AttributeType": {
        "ValueTable": "acf6192e-81ca-46ef-93a6-5a6968b78663",
        "ValueTree": "e603c0f2-92fb-4d47-8f38-a44a381cf235",
        "ValueList": "4772b3b4-f4a3-49c0-a1a5-8cb5961511a3",
    },
}


def guid_name(slot, text):
    """Имя GUID для поля с таблицей имён; `None`, если поле таблицы не имеет или GUID в ней нет."""
    table = GUID_NAMES.get(slot.names) if getattr(slot, "names", None) else None
    if not table:
        return None
    for name, guid in table.items():
        if guid == text:
            return name
    return None


def type_guid(value):
    """GUID типа из значения `value_type` блока типа (`{"#", GUID}`) в любой из двух записей `decode`: обёртка `{"guid": …}` либо имя типа платформы
    (`"ValueTable"`). Нет GUID (не обёртка, имени нет в таблице) — `None`. Единственное место, через которое потребители читают тип ссылки."""
    if isinstance(value, dict):
        guid = value.get("guid")
        return guid if isinstance(guid, str) else None
    if isinstance(value, str):
        return GUID_NAMES["AttributeType"].get(value)
    return None


def guid_of_name(slot, name):
    """GUID по имени для поля с таблицей имён; `None`, если имени нет."""
    table = GUID_NAMES.get(slot.names) if getattr(slot, "names", None) else None
    return table.get(name) if table else None


@dataclass(frozen=True)
class F:
    """Скаляр на позиции."""
    name: str
    kind: str
    source: str
    const: object = None
    seen: tuple = ()
    enum: str = None
    note: str = None
    bits: dict = None
    mirror_of: str = None
    # Зеркало, которое палитра платформы при правке свойства не пишет: в файле формы оба места согласованы, и
    # редактор записывает зеркало сам (`set_property`).
    primary_only: bool = False
    # Имена GUID: ключ таблицы `GUID_NAMES`. Поле остаётся GUID в файле, а в JSON известный GUID читается именем (`"ValueTable"`),
    # неизвестный — обёрткой `{"guid": …}`, как раньше.
    names: str = None

    def __post_init__(self):
        if self.names is not None and self.kind != GUID:
            raise SchemaError(f"поле {self.name}: таблица имён GUID бывает только у вида {GUID}, а здесь вид {self.kind}")
        if (self.kind == BITS) != bool(self.bits):
            raise SchemaError(f"поле {self.name}: таблица битов бывает только у вида {BITS} и "
                              f"обязательна у него, а здесь вид {self.kind} и биты {self.bits!r}")
        if not self.bits:
            return
        if BITS_REST in self.bits:
            raise SchemaError(f"поле {self.name}: бит {BITS_REST!r} назвать нельзя — этим именем "
                              "записывается остаток слова, и бит затёр бы его молча")
        seen = {}
        for name, mask in self.bits.items():
            if not isinstance(mask, int) or isinstance(mask, bool) or mask <= 0:
                raise SchemaError(f"поле {self.name}: маска бита {name!r} — {mask!r}, а маска это "
                                  "положительное целое")
            if mask in seen:
                raise SchemaError(f"поле {self.name}: биты {seen[mask]!r} и {name!r} стоят на "
                                  f"одной маске {mask:#x} — в файле это ОДИН бит, и какое из "
                                  "двух свойств им записано, журнал не различает")
            seen[mask] = name


@dataclass(frozen=True)
class N:
    """Вложенный блок на позиции."""
    name: str
    type: str
    source: str
    note: str = None
    mirror_of: str = None


@dataclass(frozen=True)
class R:
    """Повтор: все позиции начиная со `start` — узлы одного типа, в JSON они массив."""
    name: str
    type: str
    start: int
    source: str
    note: str = None


@dataclass(frozen=True)
class Enum:
    """Коды палитры плюс то, чего палитра не объясняет. Два разных незнания, и сводить их в одно поле
    нельзя."""
    codes: dict
    default: str = None
    source: str = ""
    missing: tuple = ()
    seen: tuple = ()
    note: str = None


@dataclass(frozen=True)
class Const:
    """ПОСТОЯННОЕ значение поля там, где само поле карты общее, а постоянно оно в одном месте."""
    value: str
    where: str
    source: str
    note: str = None


@dataclass(frozen=True)
class Fixed:
    """Отрезок раскладки с фиксированными позициями: имя по СМЕЩЕНИЮ от начала ОТРЕЗКА."""
    fields: dict = field(default_factory=dict)
    length: int = None


@dataclass(frozen=True)
class Counted:
    """Счётный список: на первой позиции отрезка СЧЁТЧИК, за ним столько же узлов одного типа."""
    name: str
    type: str
    source: str
    note: str = None
    at_most: int = None


@dataclass(frozen=True)
class CountedPairs:
    """Счётный список ПАР: счётчик, а за ним по ДВА места на члена — скаляр-ключ и узел. Имя ключа
    обязано быть СВОБОДНЫМ у типа члена — иначе поле узла и ключ затёрли бы друг друга; это
    проверяется при построении карты."""
    name: str
    type: str
    key: str
    key_kind: str
    source: str
    note: str = None

    def __post_init__(self):
        if self.key_kind not in (GUID, INT, STR):
            # Видов ровно три, и отбор не по вкусу: у ключа НЕТ своего адреса в JSON — он лежит
            # внутри объекта члена, — а значит нет и места для демоции.
            raise SchemaError(f"список пар {self.name}: ключ вида {self.key_kind} не заведён — "
                              f"ключом бывает {GUID}, {INT} или {STR}, и вид здесь не догадка")


@dataclass(frozen=True)
class Flagged:
    """Отрезок по БИТАМ: слово флагов, а за ним по блоку на каждый поднятый бит."""
    name: str
    bits: dict
    source: str
    note: str = None

    def __post_init__(self):
        if not self.bits:
            raise SchemaError(f"отрезок по битам {self.name}: таблица битов пуста — тогда за "
                              "словом не бывает ни одного блока, и отрезок не нужен вовсе")
        seen = {}
        for name, pair in self.bits.items():
            mask, _type = pair
            _check_mask(f"отрезок по битам {self.name}", name, mask, seen)

    @property
    def mask(self):
        """Слово из всех названных битов: что вне его — бит, которого карта не знает."""
        out = 0
        for mask, _type in self.bits.values():
            out |= mask
        return out

    def raised(self, word):
        """Имена поднятых битов В ПОРЯДКЕ ФАЙЛА."""
        if word & ~self.mask:
            return None
        return [name for name, (mask, _type) in self.bits.items() if word & mask]

    def word(self, names):
        out = 0
        for name in names:
            out |= self.bits[name][0]
        return out


@dataclass(frozen=True)
class Masked:
    """Отрезок по МАСКЕ: слово маски, а за ним по СКАЛЯРУ на каждый поднятый бит."""
    name: str
    bits: dict
    source: str
    flags: dict = None
    lead: tuple = ()
    note: str = None

    def __post_init__(self):
        if not self.bits:
            raise SchemaError(f"отрезок по маске {self.name}: таблица битов пуста — тогда за "
                              "словом не бывает ни одного значения, и отрезок не нужен вовсе")
        seen = {}
        for name, pair in self.bits.items():
            mask, kind = pair
            _check_mask(f"отрезок по маске {self.name}", name, mask, seen)
            if kind in (BITS, ENUM, NODE) or kind not in _SCALAR_KIND_OF:
                # У члена отрезка нет своего слота в карте: вид объявлен один на бит, а перечислению
                # и битовому слову нужна вторая таблица (`enum`, `bits`), которую держать тут негде.
                raise SchemaError(f"отрезок по маске {self.name}: у бита {name!r} вид {kind} не "
                                  f"заведён — за битом стоит один скаляр, и вид ему нужен "
                                  f"такой, которому хватает имени и вида")
        for name, mask in (self.flags or {}).items():
            _check_mask(f"отрезок по маске {self.name}", name, mask, seen)
        busy = set(self.bits) | set(self.flags or ()) | {self.name}
        for slot in self.lead:
            if slot.name in busy:
                raise SchemaError(f"отрезок по маске {self.name}: имя {slot.name!r} занято "
                                  "дважды — у каждого значения файла ровно одно поле JSON")
            busy.add(slot.name)

    @property
    def mask(self):
        """Слово из всех названных битов — и со значением, и без: что вне его, карте неизвестно."""
        out = 0
        for mask, _kind in self.bits.values():
            out |= mask
        for mask in (self.flags or {}).values():
            out |= mask
        return out

    def raised(self, word):
        """Имена битов СО ЗНАЧЕНИЕМ в порядке файла."""
        if word & ~self.mask:
            return None
        return [name for name, (mask, _kind) in self.bits.items() if word & mask]

    def flags_of(self, word):
        """Биты без значения — именем и булевым: они записываются в JSON всегда."""
        return {name: bool(word & mask) for name, mask in (self.flags or {}).items()}

    def word(self, names, values):
        """Слово обратно: биты по набору ключей плюс биты, поднятые булевыми полями."""
        out = 0
        for name in names:
            out |= self.bits[name][0]
        for name, mask in (self.flags or {}).items():
            if values.get(name):
                out |= mask
        return out


def _check_mask(where, name, mask, seen):
    """Маска бита — положительное целое, и на одной маске не бывает двух имён."""
    if not isinstance(mask, int) or isinstance(mask, bool) or mask <= 0:
        raise SchemaError(f"{where}: маска бита {name!r} — {mask!r}, а маска это положительное "
                          "целое")
    if mask in seen:
        raise SchemaError(f"{where}: биты {seen[mask]!r} и {name!r} стоят на одной маске "
                          f"{mask:#x} — в файле это ОДИН бит, и какое из двух значений им "
                          "записано, замер не различает")
    seen[mask] = name


def masked_slot(segment, name):
    """Псевдослот значения по биту: своего слота у члена отрезка нет, вид объявлен таблицей."""
    return F(name, segment.bits[name][1], segment.source)


@dataclass(frozen=True)
class Along:
    """Парный отрезок: столько СКАЛЯРОВ, сколько узлов в списке соседнего поля.

    `one_unless` — имя флага того же узла: при флаге 0 скаляр ОДИН на весь узел (при пустом списке — ни одного), сколько бы узлов ни было в
    списке. Так платформа пишет «АктивизироватьПоУмолчанию» родителя без «Распределять по страницам»."""
    name: str
    kind: str
    source: str
    items_of: str
    note: str = None
    one_unless: str = None

    def __post_init__(self):
        if self.kind != INT:
            raise SchemaError(f"парный отрезок {self.name}: вид {self.kind} не заведён, "
                              f"бывает только {INT}")


@dataclass(frozen=True)
class Gated:
    """Необязательный блок за ФЛАГОМ СТРОЕНИЯ: есть он в файле или нет, решает поле ГОЛОВЫ. Перечислены
    ОБА набора, и это не избыточность: флаг со значением вне их обоих значит «карта не знает, какой
    длины узел», и такой узел обязан уехать сырым."""
    name: str
    type: str
    source: str
    by: str
    when: tuple
    without: tuple
    note: str = None

    def __post_init__(self):
        for field_name, values in (("when", self.when), ("without", self.without)):
            if not values:
                raise SchemaError(f"необязательный блок {self.name}: набор {field_name} пуст — "
                                  "оба набора значений флага называет карта, и пустой означал "
                                  "бы, что одно из двух строений не встречается никогда")
            for value in values:
                if not isinstance(value, int) or isinstance(value, bool):
                    raise SchemaError(f"необязательный блок {self.name}: значение флага "
                                      f"{value!r} не целое — флаг читается из файла числом")
        both = set(self.when) & set(self.without)
        if both:
            raise SchemaError(f"необязательный блок {self.name}: значение "
                              f"{', '.join(str(v) for v in sorted(both))} объявлено и с блоком, "
                              "и без него — какой длины узел при нём, карта тогда не отвечает")

    def count(self, value):
        """Сколько блоков при таком значении флага."""
        if value in self.when:
            return 1
        if value in self.without:
            return 0
        return None


@dataclass(frozen=True)
class Runs:
    """Раскладка узла ЗА фиксированной головой: отрезки подряд, начиная с позиции `start`."""
    start: int
    segments: tuple


def run_key(lists_before, offset):
    """Ключ JSON и адрес позиции в плавающем отрезке: `L6+0` — первая позиция за шестым списком. Одно
    написание на все три места, где адрес виден человеку: `FORMAT.md`, отказы кодека и сам ключ
    JSON."""
    return f"L{lists_before}+{offset}"


def run_list_key(number):
    """Адрес самого списка: `L1` — первый список узла."""
    return f"L{number}"


@dataclass(frozen=True)
class Packed:
    """Узел УПАКОВАН: в файле у него одна позиция — скаляр base64, а позиции карты лежат ВНУТРИ."""
    payload: F
    note: str = None


@dataclass(frozen=True)
class NodeType:
    name: str
    fields: dict = field(default_factory=dict)
    repeat: R = None
    note: str = None
    runs: Runs = None
    packed: Packed = None

    def __post_init__(self):
        if self.packed is not None:
            # Раскрытый узел упаковки — это ровно три позиции (`frm_codec.packed`), и описать его
            # иначе значило бы разойтись с тем, что раскрытие отдаёт: содержимое — блок, число
            # пустых кусков — целое, раскладка — строка.
            kinds = {index: (type(slot), getattr(slot, "kind", None))
                     for index, slot in self.fields.items()}
            if self.repeat is not None or self.runs is not None or \
                    kinds != {0: (N, None), 1: (F, INT), 2: (F, STR)}:
                raise SchemaError(f"узел {self.name}: упакованный узел описывается тремя полями — "
                                  "0 блок содержимого, 1 целое (пустые куски), 2 строка "
                                  "(раскладка base64), без повтора и раскладки")
        """Три заставы на раскладку, и каждая закрывает свой способ описать несуществующее.

        Повтор рядом со счётными списками — это два разных ответа на вопрос «чьи позиции после
        головы»: повтор забирает их все до конца, отрезки делят их между собой.

        Первый отрезок обязан быть списком: если бы он был фиксированным, его позиции считались
        бы от начала узла числом — то есть были бы головой, а не отрезком, и адрес `L0+k` обещал
        бы плавание там, где его нет.

        Открытый отрезок («до конца блока») бывает только последним: у того, за кем что-то
        идёт, конец надо знать, иначе следующий отрезок начинается неизвестно где.

        Четвёртая застава — про ТИХУЮ потерю: два фиксированных отрезка подряд неразличимы по
        ключу. Запасное имя позиции считается от числа списков ПЕРЕД отрезком (`L<n>+<k>`), а у
        соседних `Fixed` это число одно и то же — значит ключи наложились бы, разбор потерял бы
        значение молча, а сборка отказала бы «нет полей» про ключи, которые в документе есть.
        Два отрезка подряд — это один отрезок, и писать их надо одним."""
        if self.runs is None:
            return
        if self.repeat is not None:
            raise SchemaError(f"узел {self.name}: повтор и счётные списки вместе не бывают — "
                              "повтор забирает все позиции до конца блока, а отрезки делят их")
        if not self.runs.segments or isinstance(self.runs.segments[0], Fixed):
            raise SchemaError(f"узел {self.name}: первый отрезок раскладки обязан быть списком; "
                              "фиксированные позиции перед первым списком — это голова узла "
                              "(обычные поля), их адресуют числом")
        for before, segment in zip(self.runs.segments, self.runs.segments[1:]):
            if isinstance(before, Fixed) and isinstance(segment, Fixed):
                raise SchemaError(f"узел {self.name}: два фиксированных отрезка подряд — это "
                                  "один отрезок, и писать их надо одним: запасные ключи у них "
                                  "совпадают (номер считается от числа списков ПЕРЕД отрезком), "
                                  "и позиция второго затёрла бы позицию первого молча")
            if isinstance(before, Fixed) and isinstance(segment, Masked) and segment.lead:
                # Та же тихая потеря: запасные ключи у обоих считаются от одного и того же числа
                # списков, у фиксированного отрезка смещения идут с нуля, а у слотов перед
                # значениями — с единицы.
                raise SchemaError(f"узел {self.name}: отрезок по маске со слотами перед "
                                  "значениями не может идти следом за фиксированным отрезком: "
                                  "запасные ключи у них считаются от одного числа списков и "
                                  "наложились бы молча")
        for segment in self.runs.segments[:-1]:
            if isinstance(segment, Fixed) and segment.length is None:
                raise SchemaError(f"узел {self.name}: отрезок «до конца блока» бывает только "
                                  "последним — иначе неизвестно, где начинается следующий")


# ELEMENT_GUIDS, FORM_CONTAINER_GUID и element_type_name приходят из frm_codec.guids и здесь
# перевыставлены: у карты один вход, а второй список GUID разошёлся бы со статистикой молча.

MAP = {}


def _add(node):
    MAP[node.name] = node
    return node


def node_type(type_name):
    """Узел карты по имени. Незнакомое имя — отказ СО СЛОВАМИ и с похожими именами рядом."""
    node = MAP.get(type_name)
    if node is None:
        close = difflib.get_close_matches(type_name, MAP, n=3)
        raise SchemaError(f"узла {type_name!r} в карте нет"
                          + (f"; похожие имена: {', '.join(close)}" if close else ""))
    return node


def _place(type_name, path, slot):
    """Механическое «общий префикс = props» соврало бы: у Панели и Табличного поля общего префикса у
    именованных адресов нет вовсе, а у соседей он разный."""
    node = node_type(type_name)
    indexes = [int(part) for part in path.split("/")]
    for index in indexes[:-1]:
        step = node.fields.get(index)
        if step is None:
            step = N(f"u{index}", f"{node.name}.u{index}", source="corpus")
            node.fields[index] = step
            if step.type not in MAP:
                _add(NodeType(step.type))
        if isinstance(step, F):
            raise SchemaError(f"{node.name}: позиция {index} — скаляр {step.name}, "
                              f"внутрь неё адреса {path} нет")
        node = node_type(step.type)
    last = indexes[-1]
    busy = node.fields.get(last)
    if busy is not None:
        raise SchemaError(f"{node.name}: позиция {last} уже занята полем {busy.name}, "
                          f"а таблица кладёт туда {slot.name}")
    if node.runs is not None and last >= node.runs.start:
        # Молча положить сюда поле значило бы дать позиции ДВА имени: числовое из таблицы и
        # плавающее из раскладки, — и какое из них увидит `decode`, зависело бы от порядка проверок.
        raise SchemaError(f"{node.name}: позиция {last} лежит за головой узла (голова кончается "
                          f"на {node.runs.start}), а дальше идут счётные списки — числом такая "
                          f"позиция не адресуется; имя ей дают отрезком раскладки, а не строкой "
                          f"таблицы ({slot.name})")
    node.fields[last] = slot
    return slot


# ── Костяк ────────────────────────────────────────────────────────────────────────────────────

_add(NodeType("Form", {
    0: F("version", INT, seen=(27, 26, 25, 23, 20), source="corpus"),
    1: N("form", "FormBlock", source="corpus"),
    2: N("attributes", "Attributes", source="smoke"),
    3: N("main_attribute", "MainAttribute", source="corpus"),
}))

_add(NodeType("MainAttribute", {
    0: F("main_attribute_type", GUID, source="exp",
         note="Тип основного реквизита формы; в палитре формы это строка «Тип значения»."),
}, note="Описатель основного реквизита формы. Позиции 1 и 2 имени не имеют. Позиция 1 равна 1, "
        "если блок состоит из трёх позиций, и 0, если из двух. Позиция 2 есть только у блока из "
        "трёх позиций: это блок событий и настроек основного реквизита (узел `MainAttribute.u2`) "
        "длиной от 2 до 6 позиций."))

# Выбор варианта блока формы.
_FORM_BLOCK_COMMON = {
    1: N("title", "Title", source="doc"),
    2: N("container", "Container", source="doc"),
    3: F("width", INT, source="doc"),
    4: F("height", INT, source="doc"),
    # Поля стоят ЗДЕСЬ, а не строками таблицы ниже, потому что блок формы — выбор варианта.
    5: F("enter_key_behavior", ENUM, enum="Form.EnterKeyBehavior",
         source="lab"),
    # Четыре свойства страницы «Редактирование» палитры формы.
    6: F("use_grid", BOOL, source="exp",
         note="Свойство формы «ИспользоватьСетку»."),
    7: F("use_align_lines", BOOL, source="exp",
         note="Свойство формы «ИспользоватьВыравнивающиеЛинии»."),
    8: F("horizontal_grid_step", INT, source="exp"),
    9: F("vertical_grid_step", INT, source="exp"),
    10: F("save_count", INT, source="exp",
          note="Служебный счётчик, который конфигуратор меняет при сохранении формы; в палитре его "
               "нет. При сравнении двух форм разница в этом поле — не правка."),
}

_add(NodeType("FormBlock", note="Вариант выбирается по первому скаляру: 18 — блок из 14 позиций с "
                                "физическим размером и DPI, 16 — блок из 11 позиций без них."))

_add(NodeType("FormBlock18", {
    0: F("kind", INT, const=18, source="corpus"),
    **_FORM_BLOCK_COMMON,
    11: F("device_width", INT, source="smoke"),
    12: F("device_height", INT, source="smoke"),
    13: F("dpi", INT, seen=(96, 120, 144, 192), source="doc"),
}, note="Блок формы из 14 позиций: заголовок, контейнер, логический размер, поведение клавиши "
        "Enter, настройки сетки, служебный счётчик, физический размер и DPI."))

_add(NodeType("FormBlock16", {
    0: F("kind", INT, const=16, source="corpus",
         note="Вариант блока без физического размера и DPI. Он встречается при всех пяти версиях "
              "формы, а вариант 18 — только при версии 27."),
    **_FORM_BLOCK_COMMON,
}, note="Короткий блок формы из 11 позиций. Позиций `device_width`, `device_height` и `dpi` в нём "
        "нет: это отдельный вид блока, а не блок с обрезанным концом."))

_add(NodeType("Title", {
    0: N("caption", "LocalizedString", source="lab",
         note="Заголовок формы — свойство «ЗаголовокФормы»."),
    1: F("last_index", INT, source="corpus",
         note="Наибольший индекс, когда-либо выданный элементу формы. Он не меньше наибольшего "
              "индекса среди элементов: номер удалённого элемента остаётся занятым. Операции "
              "редактора, добавляющие элемент, увеличивают это число; `validate` уровня 2 "
              "предупреждает, если оно меньше наибольшего индекса."),
}, note="Позиция 2 не имеет имени: это ссылка на элемент формы по индексу, обычно на командную "
        "панель, реже на кнопку. Если элемент удалить, платформа при сохранении записывает сюда "
        "−1. `validate` уровня 2 предупреждает, если элемента с таким индексом нет."))


_add(NodeType("Container", {
    0: F("type_guid", GUID, const=FORM_CONTAINER_GUID, source="corpus"),
    1: N("layout_holder", "LayoutHolder", source="corpus"),
    2: N("elements", "Elements", source="doc"),
}))

_add(NodeType("LayoutHolder", {
    1: N("layout_list", "LayoutList", source="corpus"),
    2: N("events", "EventList.PageContainer", source="exp",
         note="Обработчики событий встроенного контейнера страниц формы, а не самой формы. Палитра "
              "показывает событие «ПриСменеСтраницы» среди событий формы, но записывается оно "
              "сюда."),
}, note="Содержимое формы. Позиция 0 имени не имеет: это версия описания (значение 1)."))
# ── Блок содержимого: счётные списки, а за ними ещё поля ──────────────────────────────────────
_add(NodeType("LayoutRun", {
    0: F("mark", INT, const=0, source="corpus"),
    1: F("element", INT, source="corpus",
         note="Индекс элемента, чья граница привязана к этому краю родителя (в правиле привязки "
              "объект равен 0)."),
    2: F("side", INT, source="corpus",
         note="Граница названного элемента; коды те же, что у `AnchorRule.side`: 0 — верхняя, 1 — "
              "нижняя, 2 — левая, 3 — правая. В списках верхнего и нижнего края встречаются только "
              "0 и 1, в списках левого и правого — только 2 и 3."),
}, note=(
    "Встречная запись привязки к краю родителя: `{0, индекс элемента, его граница}`. Строение и "
    "смысл те же, что у записи зависимого элемента в блоке координат (`CoordsDependent`).")))
# Шесть счётных списков блока раскладки родителя — ОДИН перечень на контейнер формы и на панель:
# раскладка у них общая, и два перечня, разойдясь, назвали бы один список двумя именами.
HOLDER_DEPENDENTS = ("dependents_top", "dependents_bottom", "dependents_left", "dependents_right")
_HOLDER_EDGE_WORDS = ("верхнему", "нижнему", "левому", "правому")


def _holder_lists():
    edges = tuple(
        Counted(name, "LayoutRun", source="exp",
                note=f"Элементы, привязанные к {word} краю родителя: по одной записи "
                     f"`{{0, элемент, его граница}}` на каждое правило привязки с объектом 0 и "
                     f"стороной {side} у элемента этого родителя, первое и второе правило поровну"
                     + (", а также на каждое правило к центру по вертикали (сторона 4)" if side == 1
                        else ", а также на каждое правило к центру по горизонтали (сторона 5)"
                        if side == 3 else "")
                     + ". Без такой записи привязка в предприятии не работает.")
        for side, (name, word) in enumerate(zip(HOLDER_DEPENDENTS, _HOLDER_EDGE_WORDS)))
    spare = tuple(Counted(f"list{n}", "LayoutRun", source="corpus") for n in (5, 6))
    return edges + spare
_add(NodeType("Guide", note=(
    "Направляющая линия конструктора: блок из девяти позиций `{2, координата, 1\\|0, 1, номер, 0, "
    "…}`.")))
_add(NodeType("PictureSet.Form", {
    1: F("picture_size", INT, source="exp",
         note="Свойство формы «РазмерКартинки»: 0 — «Реальный размер», 1 — «Растянуть». Остальные "
              "коды не проверялись, поэтому поле — число, а не перечисление."),
    2: N("picture", "Picture", source="exp"),
}, note="Набор картинок формы. Он стоит первой позицией после шести счётных списков (`L6+0`)."))
_add(NodeType("LayoutList", {
    0: N("layout", "Layout", source="corpus",
         note="Общий блок свойств контейнера формы. Его длина (13, 15, 17 или 18) зависит от "
              "версии блока, по которой выбирается вариант узла `Layout`."),
}, runs=Runs(2, (
    *_holder_lists(),
    Fixed({
        0: N("pictures", "PictureSet.Form", source="exp"),
        1: F("show_tabs", ENUM, enum="Form.ShowTabs", source="exp"),
        2: F("separate_by_page", BOOL, source="exp"),
        3: N("pages", "PanelPages", source="exp",
             note="Список страниц формы; это тот же узел, что список страниц панели. Страницы у "
                  "обычной формы есть всегда, даже если закладки не видны."),
        4: F("auto_rules", BOOL, source="exp"),
        5: F("auto_tab_order", BOOL, source="exp"),
        6: F("scroll_page_mode", BOOL, source="exp",
             note="Свойство формы «РежимПрокручиваемыхСтраниц»."),
    }, length=7),
    Counted("guides", "Guide", source="exp"),
    Fixed({
        0: F("use_visible_area_only", BOOL, source="exp",
             note="Свойство формы «Исп. только видимую область». В файле флаг перевёрнут: 1 "
                  "означает, что галочка в палитре снята. Карта значение не переворачивает."),
    }, length=1),
    Along("default_control", INT, source="exp", items_of="pages", one_unless="separate_by_page",
          note="Свойство «АктивизироватьПоУмолчанию»: номер элемента, по одному числу на каждую "
               "страницу формы, если у формы стоит «Распределять по страницам» (`separate_by_page`), "
               "и одно число на всю форму, если не стоит. Значение 4294967295 (−1) означает, что элемент "
               "не задан."),
    Fixed({
        0: F("picture_location", ENUM, enum="Form.PictureLocation", source="exp",
             note="Свойство формы «ПоложениеКартинки». В палитре строка доступна, только если "
                  "«РазмерКартинки» не равен «Растянуть»."),
        3: N("back_color", "Color", source="exp",
             mirror_of="1/2/1/1/0/2"),
    }),
)), note="Блок содержимого контейнера формы. Он устроен так же, как блок содержимого панели: в "
         "позиции 0 общий блок свойств, затем шесть счётных списков, а после них набор картинок, "
         "ОтображениеЗакладок, РаспределятьПоСтраницам, список страниц, АвтоПравила, "
         "АвтоПорядокОбхода, РежимПрокручиваемыхСтраниц и второй адрес цвета фона. Позиции после "
         "списков сдвигаются на сумму их счётчиков, поэтому адресуются смещением от конца списка "
         "(`L6+0` и дальше). Если отрезки не сходятся с длиной блока, узел остаётся неразобранным "
         "и выдаётся предупреждение уровня 1."))
_add(NodeType("Layout", {}, note="Общий блок свойств контейнера формы; такой же блок лежит первым "
                                 "в блоке содержимого панели. Вариант выбирается по первому "
                                 "скаляру — версии блока (10, 13, 15 или 16), и длина блока "
                                 "зависит от версии. Версия этого блока — версия всей формы: общий "
                                 "блок каждого элемента формы имеет ту же версию. Блок версии, "
                                 "которой нет в карте, остаётся неразобранным."))

# Шесть свойств общего блока.
_LAYOUT_COMMON = {
    1: F("enabled", BOOL, source="exp",
         note="Свойство формы «Доступность»."),
    2: N("back_color", "Color", source="exp",
         note="Свойство формы «ЦветФона». Платформа записывает его дважды: сюда и в конец блока "
              "содержимого (`LayoutList`, позиция `L8+3`, то же имя). Этот адрес — первичный; "
              "`validate` уровня 2 предупреждает, если значения разошлись."),
    3: N("text_color", "Color", source="exp"),
    4: N("font", "Font", source="exp",
         note="Свойство формы «Шрифт»; запись шрифта та же, что у элементов."),
    6: N("border_color", "Color", source="exp"),
    11: N("border", "Border", source="exp",
          note="Рамка формы: тип рамки лежит в `11/3`, признак «рамка задана явно» — в `11/4`."),
}
_add(NodeType("Layout16", {0: F("layout_version", INT, const=16, source="corpus"),
                           **_LAYOUT_COMMON},
              note="Общий блок свойств версии 16, длина 18."))
_add(NodeType("Layout15", {0: F("layout_version", INT, const=15, source="corpus"),
                           **_LAYOUT_COMMON},
              note="Общий блок свойств версии 15, длина 17."))
_add(NodeType("Layout13", {0: F("layout_version", INT, const=13, source="corpus"),
                           **_LAYOUT_COMMON},
              note="Общий блок свойств версии 13, длина 15."))
_add(NodeType("Layout10", {0: F("layout_version", INT, const=10, source="corpus"),
                           **_LAYOUT_COMMON},
              note="Общий блок свойств версии 10, длина 13. Эта версия бывает только у формы с "
                   "коротким блоком формы (`FormBlock16`)."))

_add(NodeType("Elements", {0: F("count", INT, source="smoke",
                                note="Число элементов в списке; оно равно числу записей за "
                                     "счётчиком.")},
              repeat=R("items", "Element", start=1, source="corpus"),
              note="Список элементов. Он стоит в файле в двух местах: у контейнера формы (`1/2/2`) "
                   "— элементы верхнего уровня, и последней позицией записи каждого элемента (`5`, "
                   "у элементов из семи позиций — `6`) — вложенные в него элементы. Поэтому карта "
                   "рекурсивна: `Elements` → `Element` → `Elements`. Страницу панели, на которой "
                   "лежит вложенный элемент, задаёт поле `page` блока координат; порядок в списке "
                   "страницу не задаёт."))

_add(NodeType("Element", {}, note="Элемент формы. Вариант выбирается по GUID типа элемента — "
                                  "первому скаляру записи."))

_add(NodeType("CoordsDependent", {
    0: F("mark", INT, const=0, source="corpus"),
    1: F("element", INT, source="corpus",
         note="Индекс элемента, чья граница привязана к этой стороне. Платформа не удаляет такие "
              "записи вместе с элементом, поэтому индекс может называть элемент, которого в форме "
              "уже нет; `validate` об этом не предупреждает."),
    2: F("side", INT, source="corpus",
         note="Граница названного элемента; коды те же, что у `AnchorRule.side`: 0 — верхняя, 1 — "
              "нижняя, 2 — левая, 3 — правая."),
}, note="Встречная запись привязки в блоке координат: `{0, индекс элемента, сторона}`. Она "
        "означает, что граница названного элемента привязана к этой стороне."))

# Прежние имена краёв `Coords` (у формы и у колонки `width`/`height` — настоящие размеры): на входе документа
# уровня 1 они отказ (`typed.refuse_old_coords`), а не синоним.
OLD_COORDS_NAMES = ("width", "height")
# Поля, переименованные в карте: прежнее имя → новое. Во входном JSON (`encode`, `validate`, `edit --ops`) — отказ словами
# (`typed.old_field_places`), без совместимости. `allowed_sign` → `nonnegative`: значение то же.
OLD_FIELD_NAMES = {"allowed_sign": "nonnegative"}

_add(NodeType("Coords", {
    0: F("mark", INT, seen=(8, 3), source="corpus"),
    1: F("x", INT, source="doc"),
    2: F("y", INT, source="doc"),
    3: F("right", INT, source="doc",
         note="Правый край элемента в координатах родителя, а не ширина; ширина равна `right − x`."),
    4: F("bottom", INT, source="doc",
         note="Нижний край элемента в координатах родителя, а не высота; высота равна `bottom − "
              "y`."),
    5: F("visible", BOOL, source="doc"),
    6: N("top_anchor", "Anchor", source="lab"),
    7: N("bottom_anchor", "Anchor", source="lab"),
    8: N("left_anchor", "Anchor", source="lab"),
    9: N("right_anchor", "Anchor", source="corpus"),
}, runs=Runs(12, (
    Counted("dependents_top", "CoordsDependent", source="corpus"),
    Counted("dependents_bottom", "CoordsDependent", source="corpus"),
    Counted("dependents_left", "CoordsDependent", source="corpus"),
    Counted("dependents_right", "CoordsDependent", source="corpus"),
    Counted("list5", "CoordsDependent", source="corpus"),
    Counted("list6", "CoordsDependent", source="corpus"),
    Fixed({
        0: F("page", INT, source="round",
             note="Номер страницы родителя, на которой лежит элемент; страницы нумеруются с нуля."),
        1: F("page_sequence", INT, source="round",
             note="НЕ порядок обхода (опыты T120 и T121: Tab и числа «Порядок обхода…» идут по `L6+2`, "
                  "а не по этой позиции). Номер элемента на странице родителя: 0, 1, 2 и далее без "
                  "пропусков и повторов; платформа пересчитывает его при удалении соседа. Смысл не "
                  "установлен."),
        2: F("tab_order", INT, source="exp",
             note="Порядок обхода («Форма → Порядок обхода…», Tab в предприятии). Номера от 1 в пределах "
                  "страницы родителя; при удалении соседа платформа их не пересчитывает (пропуски "
                  "бывают), новому элементу даёт наибольший плюс один. При АвтоПорядокОбхода платформа "
                  "ведёт их по положению элементов."),
        3: F("manual_anchor_h", BOOL, source="lab",
             note="Галочка «Ручная привязка» по горизонтали (диалог «Привязка границ», вкладка "
                  "«Простая», раздел «Горизонтальная»). Привязки, которые ставят автоправила, этот "
                  "флаг не поднимают."),
        4: F("manual_anchor_v", BOOL, source="lab",
             note="Галочка «Ручная привязка» по вертикали (диалог «Привязка границ», вкладка "
                  "«Простая», раздел «Вертикальная»); пара к позиции `L6+3`."),
    }, length=5),
)), note="Блок координат: голова из двенадцати позиций, шесть счётных списков зависимых элементов "
         "и хвост из пяти позиций. Списки содержат встречные записи привязок: "
         "`dependents_<сторона>` перечисляет элементы, привязанные к этой стороне элемента. Без "
         "встречной записи привязка в предприятии не работает, а платформа при пересохранении её "
         "не добавляет; редактор заводит встречные записи вместе с привязкой. Пятый и шестой "
         "списки всегда пусты; `validate` уровня 2 предупреждает, если они не пусты. Блок с меткой "
         "3 в позиции 0 устроен иначе, без счётных списков, и остаётся неразобранным."))
_add(NodeType("Anchor", {
    0: F("mark", INT, const=0, source="corpus"),
    1: N("rule", "AnchorRule", source="lab",
         note="Жёсткая привязка: граница элемента равна стороне объекта плюс смещение. Когда "
              "родитель растягивается, граница сдвигается вместе со стороной объекта на то же "
              "расстояние. Без встречной записи правило в предприятии не работает."),
    2: N("rule2", "AnchorRule", source="corpus",
         note="Второе правило той же границы — пропорциональная привязка (в диалоге «Привязка "
              "границ» — строка «Сохранять пропорции до:»). Граница сохраняет долю k отрезка между "
              "объектами двух правил: если их стороны сдвинулись на Δ1 и Δ2, граница сдвигается на "
              "Δ1 + k·(Δ2 − Δ1), где k = смещение1 / (смещение1 − смещение2). Без первого правила "
              "второе не встречается, и встречная запись нужна ему так же, как первому. Имя "
              "`rule2` дано по строению записи."),
}, note="Привязка одной границы элемента: метка (всегда 0) и два правила — жёсткое (`rule`) и "
        "пропорциональное (`rule2`). Каждому правилу нужна встречная запись; редактор заводит её "
        "для обоих правил."))
_add(NodeType("AnchorRule", {
    0: F("mark", INT, const=2, source="corpus"),
    1: F("object", INT, source="lab",
         note="Объект привязки: −1 — граница не привязана; 0 — родитель (у элемента верхнего "
              "уровня это форма, у вложенного — панель); иначе — индекс соседнего элемента."),
    2: F("side", INT, source="lab",
         note="Сторона объекта, к которой привязана граница: 0 — верхняя, 1 — нижняя, 2 — левая, 3 "
              "— правая, 4 — центр по вертикали (только у верхней и нижней границ), 5 — центр по "
              "горизонтали (только у левой и правой), 6 — привязки нет. Правило к центру пишет "
              "встречную запись в список нижней (4) или правой (5) стороны объекта."),
    3: F("offset", INT, source="lab",
         note="Смещение в пикселях; бывает отрицательным."),
}, note="Запись правила привязки: `{2, объект, сторона, смещение}`."))

_add(NodeType("NameBlock", {
    0: F("mark", INT, const=14, source="corpus"),
    1: F("name", STR, source="doc"),
    2: F("action_source", INT, source="exp"),
    3: F("modifies_data", BOOL, source="lab"),
    4: F("skip_on_input", BOOL, source="lab"),
    5: F("first_in_group", BOOL, source="lab"),
}, note="Общий блок имени элемента. Позиции 2–5 одинаковы у надписи, поля ввода, кнопки, флажка, "
        "командной панели, рамки группы, панели, табличного поля, поля картинки, поля выбора и "
        "поля табличного документа."))

_add(NodeType("Attributes", {
    1: F("next_id", INT, source="corpus"),
    2: N("list", "AttributeList", source="smoke"),
    3: N("bindings", "BindingList", source="exp",
         note="Таблица привязок данных «элемент → реквизит»."),
}, note="Реквизиты формы. Позиция 0 — блок из одного числа: номер основного реквизита формы "
        "(`main_attribute_id`, свойство «Данные» в палитре формы)."))
_add(NodeType("BindingList", runs=Runs(0, (
    Counted("items", "AttributeBinding", source="corpus"),
)), note="Счётный список привязок."))
_add(NodeType("AttributeBinding", {
    0: F("element", INT, source="exp",
         note="Индекс элемента, к которому привязаны данные. Элемент с таким индексом должен быть "
              "в форме; `validate` уровня 2 предупреждает, если его нет."),
    1: N("path", "AttributePath", source="exp"),
}, note="Привязка данных: `{индекс элемента, путь к реквизиту}`."))
_add(NodeType("AttributePath", runs=Runs(0, (
    Counted("steps", "AttributePathStep", source="corpus"),
)), note="Путь к данным — счётный список шагов. Число шагов картой не ограничено; что означают "
         "пути длиннее одного шага, не проверялось."))
_add(NodeType("AttributePathStep", note=(
    "Шаг пути к данным. Первый шаг — блок из одного числа, обычно номер реквизита формы; бывают и "
    "отрицательные числа, их смысл не установлен. Следующие шаги — `{0, GUID}` (реквизит по GUID "
    "метаданных) или блок из одного числа. Позиции шага имени не имеют: строение у шагов разное.")))
_add(NodeType("AttributeList", {0: F("count", INT, source="smoke")},
              repeat=R("items", "Attribute", start=1, source="corpus")))
_add(NodeType("Attribute", {
    4: F("name", STR, source="smoke",
         note="Имя реквизита формы, например `ОбработкаОбъект`. У некоторых реквизитов на этой "
              "позиции стоит блок; тогда позиция теряет имя и называется `u4`."),
    5: N("pattern", "Pattern", source="doc"),
}))
_add(NodeType("Pattern", {0: F("mark", STR, const="Pattern", source="corpus",
                                 note="Метка описателя типа.")},
              repeat=R("types", "PatternType", start=1,
                       source="lab",
                       note="Блоки типа. Их бывает несколько (составной тип) или ни одного "
                            "(произвольный тип)."),
              note="Описатель типа: метка «Pattern», за ней блоки типа (`{\"S\",150,1}`, "
                   "`{\"N\",9,0,1}`, `{\"#\",<GUID>}`). Это не типизированное значение "
                   "(`TypedValue`), хотя блоки обоих начинаются буквой типа: у типа за буквой идут "
                   "квалификаторы (`{\"N\",9,0,1}` — длина 9, точность 0, неотрицательное), а у "
                   "значения — само значение (`{\"N\",7}`)."))

# ── Блок типа внутри описателя ────────────────────────────────────────────────────────────────
_add(NodeType("PatternType", note=(
    "Блок типа в описателе. Вариант выбирается по букве типа — первому скаляру (строке). Блок с "
    "незнакомой буквой остаётся неразобранным, его значение сохраняется.")))
_add(NodeType("PatternType.S", {
    0: F("kind", STR, const="S", source="lab"),
    1: F("length", INT, source="corpus",
         note="Длина строки."),
}, note="Строка: `{\"S\",150,1}` — длина и второе число (1 — 15 716 блоков корпуса, 0 — 1 651), либо `{\"S\"}`. "
        "Блока `{\"S\",длина}` без второго числа корпус не видел ни разу, и платформа его не читает "
        "(«Ошибка формата потока»); `validate` на нём отказывает. Второе число имени не "
        "имеет: оно похоже на допустимую длину (переменная или фиксированная), но это не "
        "проверялось."))
_add(NodeType("PatternType.N", {
    0: F("kind", STR, const="N", source="lab"),
    1: F("digits", INT, source="lab",
         note="Длина числа (`КвалификаторыЧисла.Разрядность`)."),
    2: F("fraction_digits", INT, source="lab",
         note="Точность (`РазрядностьДробнойЧасти`)."),
    3: F("nonnegative", BOOL, source="lab",
         note="Неотрицательный (`ДопустимыйЗнак`): 1 — только неотрицательные значения (палитра ☑), 0 — знак разрешён."),
}, note="Число: `{\"N\",9,0,1}` — длина, точность, знак; либо `{\"N\"}`."))
_add(NodeType("PatternType.D", {
    0: F("kind", STR, const="D", source="lab"),
    1: F("date_fractions", STR, source="lab"),
}, note="Дата: `{\"D\",\"D\"}`, `{\"D\",\"T\"}` или `{\"D\"}`."))
_add(NodeType("PatternType.B", {
    0: F("kind", STR, const="B", source="lab"),
}, note="Булево: `{\"B\"}`."))
_add(NodeType("PatternType.Ref", {
    0: F("kind", STR, const="#", source="lab"),
    1: F("value_type", GUID, source="exp", names="AttributeType",
         note="GUID типа. Три GUID типов платформы читаются именами: `ValueTable` (таблица значений), `ValueTree` (дерево значений), "
              "`ValueList` (список значений); остальные — обёрткой `{\"guid\": …}`."),
}, note="Ссылка: `{\"#\", GUID типа}`."))

# ── Типизированное значение ───────────────────────────────────────────────────────────────────

_add(NodeType("TypedValue", note=(
    "Типизированное значение `{буква, значение}`. Вариант выбирается по букве типа — первому "
    "скаляру; это строка, а не число.")))
_add(NodeType("TypedValue.N", {
    0: F("kind", STR, const="N", source="exp"),
    1: F("value", INT, source="exp"),
}, note="Число: `{\"N\",7}`."))
_add(NodeType("TypedValue.S", {
    0: F("kind", STR, const="S", source="exp"),
    1: F("value", STR, source="exp"),
}, note="Строка."))
_add(NodeType("TypedValue.B", {
    0: F("kind", STR, const="B", source="exp"),
    1: F("value", BOOL, source="corpus"),
}, note="Булево."))
_add(NodeType("TypedValue.U", {
    0: F("kind", STR, const="U", source="corpus"),
}, note="Значение не задано: блок из одной буквы `{\"U\"}`, позиции 1 нет."))
_add(NodeType("TypedValue.Ref", {
    0: F("kind", STR, const="#", source="corpus"),
    1: F("value_type", GUID, source="exp"),
}, note="Ссылочное значение `{\"#\", GUID типа, тело}`. Тело (позиция 2) имени не имеет: его "
        "строение зависит от типа."))

# ── Общие блоки, встречающиеся у многих типов ─────────────────────────────────────────────────
_add(NodeType("LocalizedString", {
    0: F("mark", INT, const=1, seen=(1,), source="corpus"),
    1: F("count", INT, source="lab"),
}, repeat=R("items", "LangText", start=2, source="lab"),
   note="Многоязычная строка `{1,N,{\"ru\",\"текст\"},…}`; при N = 0 записей нет вовсе, и блок "
        "состоит из двух скаляров."))
_add(NodeType("LangText", {
    0: F("lang", STR, source="doc"),
    1: F("text", STR, source="doc"),
}))

_add(NodeType("Color", {
    0: F("mark", INT, const=3, source="corpus",
         note="Метка блока цвета."),
    1: F("color_kind", INT, source="lab"),
    2: N("value", "ColorValue", source="lab"),
}, note="Блок цвета из трёх позиций: метка 3, вид цвета и значение. Строение одинаково у всех "
        "адресов цвета."))
_add(NodeType("ColorValue", {
    0: F("code", INT, source="lab",
         note="При `color_kind` = 0 это цвет RGB, младший байт — красный. При других видах цвета "
              "здесь код цвета стиля или системного цвета; он бывает отрицательным."),
}))


# ── Составные значения ────────────────────────────────────────────────────────────────────────

_add(NodeType("Picture", {
    1: F("source", INT, source="lab",
         note="Источник картинки: 0 — картинки нет, 1 — картинка из библиотеки, 3 — картинка "
              "встроена в форму (тело в base64). Другие коды не проверялись, поэтому поле — число."),
    2: N("ref", "PictureRef", source="lab"),
}, note="Блок картинки из 8–10 позиций; длина зависит от версии формы. Тот же блок лежит у кнопки, "
        "поля ввода, формы и внутри наборов картинок надписи, панели и поля картинки. Позиции "
        "начиная с 3 имени не имеют (имя дало бы другой ключ в JSON каждой формы с картинкой). "
        "У встроенной картинки BMP позиции 4 и 5 — координаты пикселя прозрачности (x, y) от "
        "верхнего левого угла с нуля, прозрачен каждый пиксель этого цвета; `-1, -1` — картинка "
        "непрозрачна. У PNG, ICO и GIF прозрачность своя, позиции 4 и 5 точкой не служат. "
        "У кнопки командной панели блок пишет операция `set_button_picture`."))
_add(NodeType("PictureRef", {
    0: F("code", INT, source="corpus"),
    1: F("guid", GUID, source="lab"),
}, note="Ссылка на картинку: код и, если картинка из библиотеки, её GUID."))

_add(NodeType("Border", {
    3: F("border_type", ENUM, enum="PictureBox.Border",
         source="lab"),
    4: F("explicit", BOOL, source="lab",
         note="Признак «рамка задана явно, а не взята из стиля»; конфигуратор ставит его вместе с "
              "типом рамки."),
    6: F("style_item", GUID, source="lab"),
}, note="Блок рамки из семи позиций: голова, устроенная как блок цвета, тип рамки, признак «рамка "
        "задана явно» и элемент стиля. Позиция 5 имени не имеет."))

# ── Шрифт ─────────────────────────────────────────────────────────────────────────────────────
_FONT_SOURCE = F("source", ENUM, enum="Font.Source", source="exp",
                 note="Вид записи шрифта; по нему выбирается вариант узла `Font`.")
_add(NodeType("Font", note="Запись шрифта. Вариант выбирается по второму скаляру (позиция 1) — "
                           "виду записи шрифта. Предпоследняя позиция записей видов 1–3 (`L1+0`) "
                           "имени не имеет: платформа её хранит, но нигде не показывает."))
_add(NodeType("Font.v0", {
    1: _FONT_SOURCE,
    2: F("flags", INT, source="exp",
         note="Слово флагов на том же месте, что слово маски у видов 1–3, но здесь оно читается "
              "целым числом: смысл битов у абсолютного шрифта не установлен."),
    3: F("size10", INT, source="exp",
         note="Размер шрифта в десятых долях пункта: 12 пунктов — 120, 8 пунктов — 80; по "
              "умолчанию 130."),
    7: F("weight", INT, source="exp", note="Насыщенность: 400 обычный, 700 полужирный."),
    8: F("italic", BOOL, source="exp"),
    9: F("underline", BOOL, source="exp"),
    10: F("strikeout", BOOL, source="exp"),
    16: F("face", STR, source="exp",
          note="Имя шрифта; по умолчанию у абсолютного шрифта — «MS Shell Dlg»."),
    18: F("scale", INT, source="exp", note="Масштаб в процентах; обычное значение 100."),
}, note="Абсолютный шрифт: все свойства записаны своими позициями. Запись состоит из 19 позиций; в "
        "части форм их 18 — без позиции масштаба."))

# Маска и значения. Имена те же, что у абсолютного шрифта (`Font.v0`), и это не сходство слов:
# свойство одно и то же, а смысловой дифф и редактор обязаны видеть его под одним именем у всех
# видов записи.
_FONT_BITS = {"size10": (0x2, INT), "weight": (0x4, INT), "italic": (0x8, BOOL),
              "underline": (0x10, BOOL), "strikeout": (0x20, BOOL), "face": (0x1, STR)}
_FONT_SCALE_FLAG = {"scale_set": 0x200}
_FONT_SCALE_FIELD = F("scale", INT, source="round",
                      note="Масштаб в процентах — последняя позиция записи. Она есть только у "
                           "версии записи 7; у версии 6 позиции нет совсем.")


def _font_runs(lead=()):
    """Раскладка записи шрифта видов 1–3: слово маски, [ссылка], значения, хвост, [масштаб]. Одна на
    три варианта: отличает их только ссылка, которой у «Авто» нет."""
    return Runs(2, (
        Masked("overrides", _FONT_BITS, flags=_FONT_SCALE_FLAG, lead=lead, source="round",
               note="Переопределённые свойства: в файле слово маски, за ним по одному значению на "
                    "каждый поднятый бит. Поднятый бит означает, что свойство задано записью, а не "
                    "взято из стиля (в диалоге «Выбор шрифта» снята галочка «Из стиля»). Галочка у "
                    "начертания одна на четыре флага, поэтому платформа поднимает их биты вместе."),
        Fixed({1: _FONT_SCALE_FIELD}, length=None),
    ))


_add(NodeType("SystemFontRef", {
    0: F("system_font", ENUM, enum="Font.SystemFont", source="round",
         note="Номер пункта в списке системных шрифтов диалога «Выбор шрифта»."),
}, note="Ссылка на системный шрифт: блок из одного числа."))
_add(NodeType("StyleFontRef", {
    0: F("style_font", ENUM, enum="Font.StyleFont", source="round",
         note="Шрифт стиля платформы — отрицательный код. Встречается и 0 вместе с GUID в позиции "
              "1; этот случай имени не имеет."),
}))
_add(NodeType("Font.v3", {1: _FONT_SOURCE}, runs=_font_runs(),
              note="Шрифт «Авто» (так его показывает палитра): ссылки на шрифт нет, поэтому запись "
                   "на одну позицию короче, чем у системного шрифта и шрифта стиля."))
_FONT_REF_NOTE = ("Ссылка стоит между словом маски и значениями по битам, поэтому адресуется от "
                  "отрезка: `L0+1` — первая позиция после слова маски. Само слово маски полем JSON "
                  "не является.")
_add(NodeType("Font.v1", {1: _FONT_SOURCE},
              runs=_font_runs((N("ref", "SystemFontRef", source="round",
                                 note=_FONT_REF_NOTE),)),
              note="Системный шрифт: за словом маски стоит ссылка на пункт списка системных "
                   "шрифтов."))
_add(NodeType("Font.v2", {1: _FONT_SOURCE},
              runs=_font_runs((N("ref", "StyleFontRef", source="round",
                                 note=_FONT_REF_NOTE),)),
              note="Шрифт стиля: за словом маски стоит ссылка на шрифт стиля."))

_add(NodeType("Shortcut", {
    0: F("mark", INT, const=0, source="corpus"),
    1: F("key", INT, source="lab",
         note="Виртуальный код клавиши Windows: K = 75, F5 = 116, A = 65; 0 — сочетание не задано."),
    2: F("modifiers", INT, source="lab",
         note="Модификаторы клавиши — сумма битов: Shift = 4, Ctrl = 8, Alt = 16 (Ctrl+Shift = "
              "12)."),
}))

# ── Обработчики событий ───────────────────────────────────────────────────────────────────────
EVENT_HANDLER_GUID = "e1692cc2-605b-4535-84dd-28440238746c"


# Чьи события лежат в списке — родительным падежом, для примечаний узлов списка и записи обработчика.
_EVENT_OWNERS = {
    "Button": "кнопки", "CalendarBox": "поля календаря", "CheckBox": "флажка",
    "ComboBox": "поля выбора", "Form": "формы", "FormSettings": "сохранения значений формы",
    "GeographicalSchemaField": "поля географической схемы",
    "GraphicalSchemaField": "поля графической схемы", "HTMLDocumentField": "поля HTML-документа",
    "Label": "надписи", "ListBox": "поля списка",
    "PageContainer": "встроенного контейнера страниц формы", "Panel": "панели",
    "PictureBox": "поля картинки", "RadioButton": "переключателя",
    "SpreadsheetDocumentField": "поля табличного документа", "TableBox": "табличного поля",
    "TextBox": "поля ввода", "TrackBar": "регулятора",
}


def _event_nodes(type_name, source, measured_whole=True, with_enum=True):
    """Список обработчиков и его запись — узлы ПО ТИПУ элемента, а не общие на всех."""
    if type_name not in _EVENT_OWNERS:
        raise SchemaError(f"узлы событий {type_name}: в _EVENT_OWNERS нет имени владельца событий — добавьте его "
                          "родительным падежом, им называются узлы в справочнике")
    list_name = f"EventList.{type_name}"
    item_name = f"EventHandler.{type_name}"
    carried = source if measured_whole else "corpus"
    _add(NodeType(list_name, {
        0: F("count", INT, source=carried,
             note="Число обработчиков в списке; у пустого списка — 0."),
    }, repeat=R("items", item_name, start=1, source=source),
       note=f"Список обработчиков событий {_EVENT_OWNERS[type_name]}."))
    # `with_enum=False` — там, где имён по-английски взять негде.
    event_slot = F("event", ENUM, enum=f"{type_name}.Event", source=carried,
                   note="Код события.") \
        if with_enum else \
        F("event", INT, source=carried)
    _add(NodeType(item_name, {
        0: event_slot,
        1: F("mark", GUID, const=EVENT_HANDLER_GUID, source=carried,
             note="Метка записи обработчика."),
        2: N("action", "EventAction", source=source),
    }, note=f"Запись обработчика события {_EVENT_OWNERS[type_name]}: код события, метка и "
            "действие."))


_add(NodeType("EventAction", note=(
    "Действие обработчика. Вариант выбирается по метке — первому скаляру: 3 — процедура модуля "
    "формы, 6 — стандартное действие. Узел с другой меткой остаётся неразобранным.")))
_add(NodeType("EventAction.v3", {
    0: F("mark", INT, const=3, source="corpus"),
    1: F("handler", STR, source="lab",
         note="Имя процедуры-обработчика в модуле формы."),
    2: N("description", "ActionDescription", source="lab"),
}, note="Процедура модуля формы: `{3, имя, описание}`."))
_add(NodeType("EventAction.v6", {
    0: F("mark", INT, const=6, source="corpus"),
    4: N("ref", "ActionRef", source="exp",
         note="Ссылка на источник действия: набор кнопок, названный той же парой «GUID владельца, "
              "код», что в `ActionSpec`."),
    3: F("standard_action", ENUM, enum="CommandBarButton.StandardAction",
         source="exp",
         note="Код стандартного действия. Имена есть у пятнадцати кодов; остальные коды остаются "
              "числами."),
}, note=(
    "Стандартное действие: `{6, целое, GUID, код, {1, число, GUID, число, b}, 0, 1}`. Позиции 1, "
    "2, 5 и 6 имени не имеют.")))
_add(NodeType("ActionRef", {
    0: F("mark", INT, const=1, source="corpus"),
    2: F("ref_id", GUID, source="exp",
         note="GUID владельца набора кнопок — первая половина ссылки. Это то же значение, что "
              "`ref_id` в `ActionSpec.v1`, `ActionSpec.v4` и у самого набора (`ButtonSet.ref_id`)."),
    3: F("ref_code", INT, source="exp",
         note="Код набора у владельца — вторая половина ссылки."),
}, note=(
    "Ссылка на источник действия: `{1, число, GUID, код, число}`. Обычно она называет набор кнопок "
    "своей командной панели или служебную пару «никуда» (`357c6a54-…`, 2147483647). Если ссылка не "
    "подходит ни под один случай, `validate` уровня 2 предупреждает. Позиции 1 и 4 имени не имеют.")))
_add(NodeType("ActionDescription", {
    0: F("mark", INT, const=1, source="corpus"),
    1: F("name", STR, source="lab"),
    2: N("u2", "LocalizedString", source="corpus"),
    3: N("u3", "LocalizedString", source="corpus"),
    4: N("u4", "LocalizedString", source="corpus"),
    5: N("picture", "Picture", source="lab",
         note="Картинка действия — тот же блок картинки, что у кнопки."),
}, note="Описание действия. Позиции 2–4 — три многоязычные строки: заголовок, подсказка и "
        "пояснение действия. Какая из них какая, не установлено, поэтому они названы по позициям."))


# Список ВЛОЖЕННЫХ элементов — последняя позиция записи элемента, и слот здесь ОДИН объект на все
# двадцать пять типов: блок у них один и тот же.
_NESTED_ELEMENTS = N(
    "elements", "Elements", source="corpus",
    note="Вложенные элементы; тот же узел, что у контейнера формы. Непустым список бывает только "
         "у панели и поля табличного документа.")


def _element_node(type_name, source, content_seen=None, name_index=4):
    """Общая шапка элемента: GUID типа, индекс, содержимое, координаты, имя."""
    _add(NodeType(f"Element.{type_name}", {
        0: F("type", TYPE, source=source),
        1: F("index", INT, source="doc"),
        2: N("content", f"Content.{type_name}", source="doc"),
        name_index - 1: N("coords", "Coords", source="doc"),
        name_index: N("name_block", "NameBlock", source="doc"),
        name_index + 1: _NESTED_ELEMENTS,
    }))
    # `content_kind` — первый скаляр блока содержимого. Различать типы по нему нельзя, поэтому имя
    # из старой спеки не берётся.
    _add(NodeType(f"Content.{type_name}",
                  {0: content_seen} if content_seen is not None else {}))


def _content_kind(const, note=None):
    return F("content_kind", INT, const=const, source="corpus", note=note)


# Первый скаляр блока содержимого: слот на тип, и у каждого свой источник.
_CONTENT_KIND = {
    "Label": _content_kind(3), "TextBox": _content_kind(9),
    "CheckBox": _content_kind(1), "Button": _content_kind(1),
    "CommandBar": _content_kind(2), "TableBox": _content_kind(5),
    "Panel": _content_kind(1), "GroupBox": _content_kind(0),
    "ComboBox": _content_kind(2), "PictureBox": _content_kind(1),
    "Splitter": _content_kind(0), "RadioButton": _content_kind(4),
    "ListBox": _content_kind(1), "HTMLDocumentField": _content_kind(5),
    "ProgressBar": _content_kind(0), "TrackBar": _content_kind(1),
    "CalendarBox": _content_kind(1),
    "PDFDocumentField": F("content_kind", INT, const=0, source="exp",
                          note="Блок содержимого поля PDF-документа состоит из одного этого числа."),
    "Chart": _content_kind(11),
    "GanttChart": _content_kind(17),
    "GeographicalSchemaField": _content_kind(16),
    "SpreadsheetDocumentField": F(
        "content_kind", INT, source="corpus",
        note="Первый скаляр блока содержимого. Только у этого типа он меняется от формы к форме "
             "(например, 16, 17 или 18); по строению это версия записи."),
}

# Умолчание — 4 (детей шесть); у двух типов номер пятый, и это НЕ «хвост подлиннее», а другой состав
# узла.
_NAME_INDEX = {"GeographicalSchemaField": 5, "Chart": 5}

for _type in PAL_GUIDS:
    _element_node(_type, "smoke", _CONTENT_KIND[_type])
for _type in X2_GUIDS:
    _element_node(_type, "exp", _CONTENT_KIND.get(_type), _NAME_INDEX.get(_type, 4))

_add(dataclasses.replace(
    MAP["Element.Chart"],
    note="Позиция 3 — тело диаграммы: список из 214 позиций, первая — версия записи (74 у платформы 8.3.27, 64 у форм старых конфигураций). В карте эта "
         "позиция без имени (`u3`): положение значений в теле зависит от числа серий и точек. Строки палитры из тела пишет `set_property` по своим именам, "
         "а обработчики событий — `set_event`; таблица имён — в справочнике `set_property`, абзац «Диаграмма»."))

for _kind, _word in (("GanttChart", "диаграммы Ганта"), ("Dendrogram", "дендрограммы"), ("PivotChart", "сводной диаграммы")):
    _add(dataclasses.replace(
        MAP["Content." + _kind],
        note=f"Блок содержимого {_word}: позиция 1 (`u1`) — `[0, [11], тело диаграммы]`, остальные свойства вида лежат в позициях блока и в теле записи. В карте эти позиции без "
             "имён: положение значений в теле зависит от числа серий и точек. Строки палитры пишет `set_property` по своим именам"
             + ("" if _kind == "PivotChart" else ", а обработчики событий — `set_event`")
             + f"; таблица имён — в справочнике `set_property`, абзац «{ {'GanttChart': 'Диаграмма Ганта', 'Dendrogram': 'Дендрограмма', 'PivotChart': 'Сводная диаграмма'}[_kind] }»."))

# Списки обработчиков заводятся у двух типов.
_event_nodes("CheckBox", "lab")
_event_nodes("GeographicalSchemaField",
             "lab")
# Остальные списки обработчиков частых типов.
for _type, _source, _whole in (
        ("Label", "lab", True),
        ("Button", "lab", True),
        ("Panel", "lab", True),
        ("PictureBox", "lab", False),
        ("ComboBox", "lab", False),
        ("TextBox", "lab", False),
        ("TableBox", "lab", False),
        ("SpreadsheetDocumentField",
         "lab", False)):
    _event_nodes(_type, _source, _whole)

# Списки обработчиков шести редких типов.
for _type, _source, _whole in (
        ("CalendarBox", "lab", False),
        ("GraphicalSchemaField",
         "lab", True),
        ("HTMLDocumentField",
         "lab", True),
        ("ListBox", "lab", False),
        ("RadioButton", "lab", True),
        ("TrackBar", "lab", True)):
    _event_nodes(_type, _source, _whole)

# Три списка обработчиков самой ФОРМЫ.
_event_nodes("Form", "exp")
_event_nodes("FormSettings", "exp", with_enum=False)
_event_nodes("PageContainer", "exp", with_enum=False)


# ── Связи контекстного меню ───────────────────────────────────────────────────────────────────
_add(NodeType("ContextMenuLinks", {
    0: F("count", INT, source="exp",
         note="Число связей; у формы без контекстных меню блок состоит из одного нуля."),
    1: F("owner", INT, source="exp",
         note="Индекс элемента — владельца меню (то же число, что в поле `index` элемента); 0 — "
              "контекстное меню самой формы."),
    2: F("menu", INT, source="exp",
         note="Индекс командной панели, ставшей контекстным меню; −1 — меню нет."),
    3: F("kind", GUID, source="exp",
         note="Вид связи: `b78f2e80-ec68-11d4-9dcf-0050bae2bc79` у заданного контекстного меню, "
              "`357c6a54-357d-425d-a2bd-22f4f6e86c87` — если снято «АвтоКонтекстноеМеню»."),
}, note="Связи контекстных меню формы (позиция 11 корня формы): элемент-владелец, командная панель "
        "меню и вид связи. Две последние позиции записи имени не имеют."))


# ── Блок содержимого ПАНЕЛИ: та же раскладка, что у контейнера формы ──────────────────────────
_add(NodeType("Content.Panel.u1", runs=Runs(2, (
    *_holder_lists(),
    Fixed({
        0: N("pictures", "PictureSet.Panel", source="lab"),
        1: F("show_tabs", ENUM, enum="Panel.ShowTabs",
             source="lab"),
        2: F("separate_by_page", BOOL, source="lab"),
        3: N("pages", "PanelPages", source="lab",
             note="Список страниц панели."),
        4: F("auto_rules", BOOL, source="exp",
             note="Свойство панели «АвтоПравила»."),
        5: F("auto_tab_order", BOOL, source="exp",
             note="Свойство панели «АвтоПорядокОбхода»."),
        6: F("scroll_page_mode", BOOL, source="lab"),
    }, length=7),
    Counted("guides", "Guide", source="corpus",
            note="Направляющие панели — тот же отрезок, что у контейнера формы (`LayoutList`, "
                 "`L7`)."),
    Fixed({
        0: F("use_visible_area_only", BOOL, source="exp",
             note="Свойство панели «Исп. только видимую область» (группа «Редактирование»). В "
                  "файле флаг перевёрнут, как у формы: 1 означает, что галочка снята."),
    }, length=1),
    Along("default_control", INT, source="corpus", items_of="pages", one_unless="separate_by_page",
          note="Свойство «АктивизироватьПоУмолчанию»: по одному числу на каждую страницу панели, "
               "если у панели стоит «Распределять по страницам» (`separate_by_page`), и одно число на "
               "всю панель, если не стоит, — как у формы."),
    Fixed({
        0: F("picture_location", ENUM, enum="Panel.PictureLocation", source="exp",
             note="Свойство панели «ПоложениеКартинки». В палитре строка доступна, только если "
                  "«РазмерКартинки» не равен «Растянуть»."),
        3: N("back_color", "Color", source="lab",
             mirror_of="2/1/0/2",
             note="Второй адрес свойства панели «ЦветФона»."),
    }),
)), note=(
    "Блок содержимого панели. Он устроен так же, как блок содержимого контейнера формы "
    "(`LayoutList`): голова из двух позиций, шесть счётных списков, семь полей, седьмой список "
    "(направляющие), флаг, отрезок по одному числу на страницу и хвост.")))


# ── Набор картинок ────────────────────────────────────────────────────────────────────────────
_add(NodeType("PictureSet.Label", {
    1: F("picture_size", INT, source="lab"),
    2: N("picture", "Picture", source="lab"),
}, note="Набор картинок надписи (адрес `2/1/12` от записи элемента)."))
_add(NodeType("PictureSet.Panel", {
    1: F("picture_size", ENUM, enum="Panel.PictureSize",
         source="lab"),
    2: N("picture", "Picture", source="lab"),
}, note="Набор картинок панели; первая позиция после шести счётных списков (`L6+0`)."))
_add(NodeType("PictureSet.PictureBox", {
    1: F("picture_size", ENUM, enum="PictureBox.PictureSize",
         source="lab", mirror_of="2/1/2",
         note="Второй адрес свойства «РазмерКартинки»."),
    2: N("picture", "Picture", source="lab"),
}, note="Набор картинок поля картинки, адрес `2/1/4`."))


# ── Рамка группы: свой узел ради девятого кода ────────────────────────────────────────────────
_add(NodeType("Border.GroupBox", {
    3: F("border_type", ENUM, enum="GroupBox.Border",
         source="lab"),
    4: MAP["Border"].fields[4],
    6: MAP["Border"].fields[6],
}, note="Блок рамки группы: те же семь позиций, что у блока рамки других типов (`Border`). "
        "Отдельный узел нужен из-за своего перечисления типов рамки (`GroupBox.Border`)."))


# ── Выбор варианта блока `2/3/1` Табличного поля ────────────────────────────────────────────────────
TABLE_BOX_SOURCE_BLOCK = "Content.TableBox.u3.u1"
_add(NodeType("Content.TableBox.u3",
              {1: N("u1", TABLE_BOX_SOURCE_BLOCK, source="corpus")}))
MAP["Content.TableBox"].fields[3] = N("u3", "Content.TableBox.u3", source="corpus")
_add(NodeType(TABLE_BOX_SOURCE_BLOCK, note=(
    "Источник данных табличного поля. Вариант выбирается по первому скаляру — виду источника. Поля "
    "названы только у вариантов 5 (таблица значений) и 12 (список справочника); смысл остальных "
    "кодов не установлен. Вид 2 общий у нескольких источников (список значений, табличная часть, "
    "список): различает их GUID блока `2/3` (позиция 0); у списка значений это "
    "`1a8e49a1-4dad-4421-8145-6b379f9935c7`, и колонки такого поля — колонки списка значений "
    "(`fbacf851-…`), у другого источника платформа их при записи снимает.")))
for _code in (1, 2, 3, 4, 5, 6, 7, 10, 11, 12):
    _add(NodeType(f"{TABLE_BOX_SOURCE_BLOCK}.v{_code}"))


# ── Подэлементы ───────────────────────────────────────────────────────────────────────────────

_add(NodeType("Element.TableBoxColumn", note=(
    "Колонка табличного поля с обёрткой: `{GUID вида колонки, {4 \\| 1 \\| 8, {8, {версия, …}}, "
    "Данные, …}}`. Первое число обёртки — 4 у колонки списка, 1 у колонки табличной части, 8 у "
    "колонки таблицы значений; версия головы — от 15 до 19. Вид колонки выбирает узел "
    "`TableBoxColumn`.")))
# Виды колонки по GUID.
LIST_COLUMN = "48a6ebc3-fcc8-4f8f-b399-459fb32aa46b"
VALUE_TABLE_COLUMN = "737535a4-21e6-4971-8513-3e3173a9fedd"
TABULAR_COLUMN = "c2cf1953-2796-4fe2-b78c-ff84140b124e"
VALUE_LIST_COLUMN = "fbacf851-e6ff-4107-9e08-4302dda1d14d"
WRAPPED_COLUMN_KINDS = (LIST_COLUMN, VALUE_TABLE_COLUMN, TABULAR_COLUMN)
# Голова колонки — выбор варианта по ВИДУ её вложенного элемента: у колонки с элементом — узел
# `COLUMN_HEAD`, у колонки без элемента (пустой GUID `control_type`) — `COLUMN_HEAD_BARE`.
COLUMN_HEAD = "Element.TableBoxColumn.u1.u1.u1"
COLUMN_HEAD_FORK = "TableBoxColumnHead"
COLUMN_HEAD_BARE = "TableBoxColumnHead.NoControl"
ZERO_GUID = "00000000-0000-0000-0000-000000000000"
# Виды вложенного элемента колонки — ровно три.
COLUMN_CONTROL_KINDS = ("TextBox", "CheckBox", "ComboBox")
# Тип значения табличного поля со списком значений — `СписокЗначений`: он стоит описателем в блоке
# содержимого поля (`2/1`) у всех 29 полей с колонками `fbacf851-…`.
VALUE_LIST_TYPE = "4772b3b4-f4a3-49c0-a1a5-8cb5961511a3"
# Источник данных такого поля — блок `2/3`: GUID источника (позиция 0, `u0`) и узел `2/3/1` с видом 2, описателем типа элементов
# списка (позиция 1) и флагом (позиция 2). GUID у всех 29 полей с колонками `fbacf851-…` один; у табличной части и списка
# вид источника тоже 2, различает их только GUID.
VALUE_LIST_SOURCE = "1a8e49a1-4dad-4421-8145-6b379f9935c7"
VALUE_LIST_SOURCE_KIND = 2
_add(NodeType("TableBoxColumn", note=(
    "Колонка табличного поля. Вариант выбирается по GUID вида колонки (`column_type`, позиция 0): "
    "у колонки списка значений (`fbacf851-…`) — `TableBoxColumn.ValueList`, у трёх других видов — "
    "`Element.TableBoxColumn`. Колонка незнакомого вида остаётся неразобранной.")))
_add(NodeType("TableBoxColumn.ValueList", {
    0: F("column_type", GUID, const=VALUE_LIST_COLUMN, source="corpus",
         note="GUID вида колонки: колонка табличного поля, у которого тип значения — список "
              "значений."),
    1: N("u1", "Element.TableBoxColumn.u1.u1", source="corpus",
         note="База колонки — тот же узел, что у колонок других видов по адресу `1/1`."),
}, note=(
    "Колонка табличного поля со списком значений: `{fbacf851-…, база}`. Обёртки с данными, как у "
    "колонок трёх других видов, у неё нет.")))
# Якорь колонки без обёртки: `узел → (тип якоря, позиция базы у узла, адрес базы у якоря)`.
COLUMN_ANCHOR = {"TableBoxColumn.ValueList": ("Element.TableBoxColumn", 1, (1, 1))}
_add(NodeType("TableBoxColumns", {
    0: F("count", INT, source="corpus"),
}, repeat=R("items", "TableBoxColumn", start=1, source="corpus",
            note="Колонки табличного поля. Вариант каждой колонки выбирает узел `TableBoxColumn` "
                 "по GUID вида: `TableBoxColumn.ValueList` у колонки списка значений, "
                 "`Element.TableBoxColumn` у остальных."),
   note="Список колонок табличного поля."))

_add(NodeType("Element.CommandBarButton", note=(
    "Кнопка командной панели: запись `{метка, имя, ИзменяетДанные, …}` в списке пар набора кнопок "
    "(`ButtonSet`). Запись бывает двух длин: 16 позиций при метке 8 и 13 позиций при метке 7. "
    "Названные позиции у обеих одинаковы, позиции 13–15 есть только у длинной записи. Подсказка, "
    "пояснение, картинка и сочетание клавиш кнопки лежат не здесь, а в записи действия "
    "(`CommandBarAction`).")))

# ── Блок действий командной панели (`2/1/7`) ─────────────────────────────────────────────────

_add(NodeType("CommandBarActions", {
    0: F("mark", INT, const=5, source="corpus"),
    2: F("last_number", INT, source="exp",
         note="Последний выданный номер кнопки — счётчик панели, а не число кнопок. Он не меньше "
              "наибольшего номера кнопки; при удалении кнопки его не уменьшают. `validate` уровня "
              "2 проверяет, что номера кнопок не повторяются и не превышают это число."),
}, runs=Runs(4, (
    Counted("actions", "CommandBarAction", source="lab-outside",
            note="Записи действий панели."),
    Counted("button_sets", "ButtonSet", source="corpus",
            note="Наборы кнопок: набор самой панели и по одному набору на каждое её подменю."),
)), note=(
    "Блок действий командной панели: `{5, GUID, код, 1, счётчик, записи…, счётчик, наборы…}`.")))

_add(NodeType("CommandBarAction", {
    0: F("mark", INT, seen=(6, 7), source="corpus",
         note="Число постоянных позиций записи, а не версия: длина записи равна этому числу плюс "
              "число поднятых битов поля флагов."),
    1: F("id", GUID, source="corpus",
         note="GUID действия; тот же GUID стоит ключом пары у кнопки (`id`)."),
    3: F("kind", GUID, source="exp",
         note="GUID вида действия: `abde0c9a…` — ссылка (разделитель, подменю или «никуда»), "
              "`e1692cc2…` — процедура модуля формы, `fbe38877…` — стандартное действие, "
              "`c93a51ed…` — по строению тоже ссылка, её смысл не проверялся. От вида зависит "
              "описание действия (`action`)."),
    4: N("action", "ActionSpec", source="exp",
         note="Описание действия; вариант выбирается по первому скаляру (`ActionSpec`), и он "
              "соответствует виду действия."),
}, runs=Runs(5, (
    Flagged("extras", {
        "tool_tip": (0x2, "LocalizedString"),
        "description": (0x4, "LocalizedString"),
        "picture": (0x1, "Picture"),
        "shortcut": (0x8, "Shortcut"),
    }, source="lab-outside",
        note="Блоки по битам поля флагов: подсказка, пояснение, картинка и сочетание клавиш. "
             "Порядок ключей в таблице — порядок блоков в файле; по возрастанию масок блоки не "
             "идут. При стандартном действии блок сочетания клавиш необязателен."),
    Fixed({}, length=None),
)), note=(
    "Запись действия кнопки командной панели: `{метка, GUID действия, 1, GUID вида, описание, "
    "флаги, блоки по флагам, [хвост]}`. По GUID действия (позиция 1) кнопка находит свою запись. "
    "Позиция 2 имени не имеет (всегда 1).")))

_add(NodeType("ActionSpec", note=(
    "Описание действия. Вариант выбирается по первому скаляру; вариантов четыре, по одному на "
    "каждый вид действия (`CommandBarAction.kind`). Процедуру модуля (3) и стандартное действие "
    "(6) разбирает узел `EventAction`.")))
_add(NodeType("ActionSpec.v1", {
    0: F("mark", INT, const=1, source="exp"),
    1: F("ref_id", GUID, source="exp",
         note="GUID владельца набора кнопок — первая половина ссылки; вторая, `ref_code`, называет "
              "набор у этого владельца."),
    2: F("ref_code", INT, source="exp",
         note="Код набора у владельца — вторая половина ссылки."),
}, note=(
    "Ссылка `{1, GUID, код}`. Так записаны разделитель (`9d0a2e40-…`, 0), подменю (ссылка на набор "
    "кнопок этой панели) и кнопка без действия (`357c6a54-…`, 2147483647). Если ссылка не подходит "
    "ни под один случай, `validate` уровня 2 предупреждает.")))
_add(NodeType("ActionSpec.v4", {
    0: F("mark", INT, const=4, source="corpus"),
    1: F("ref_id", GUID, source="corpus",
         note="GUID владельца набора — та же первая половина ссылки, что у `ActionSpec.v1`."),
    2: F("ref_code", INT, source="corpus",
         note="Код набора кнопок — того, что лежит в `ButtonSet.code` этой же панели."),
}, note=(
    "Ссылка из шести позиций: `{4, GUID, код набора, блок, 0, 0}`. Смысл этого вида не проверялся; "
    "по строению это ссылка на набор кнопок своей панели.")))

# Постоянные значения по имени.
CONSTS = {
    "ButtonSet.MenuButtons": Const(
        "31946946-0a9b-40a2-95cf-82f200778341",
        where="`ButtonSet.ref_id` набора кнопок выпадающего меню кнопки формы (`Content.Button.u1.menu`)",
        source="round",
        note="Набор кнопок меню кнопки формы всегда несёт этот GUID. Со случайным GUID платформа "
             "форму открывает и сохраняет, но меню не выпадает; другое значение `validate` "
             "отвергает на уровне 1."),
}
# Набор кнопок меню кнопки формы.
MENU_BUTTON_SET = CONSTS["ButtonSet.MenuButtons"].value
# Четыре постоянных GUID наборов КОМАНДНОЙ ПАНЕЛИ — словарь без имён ролей, поэтому не `CONSTS`. Им
# же живёт предупреждение `validate` о наборе панели вне словаря.
PANEL_BUTTON_SETS = ("b78f2e80-ec68-11d4-9dcf-0050bae2bc79",
                     "875faa24-ba4b-4731-9f11-7a7cea99ef16",
                     "cbcbb11d-a355-470e-990c-87f7bbfb2146",
                     "206a2abe-8e83-45dc-95d3-0d325b6339f5")

_add(NodeType("ButtonSet", {
    0: F("mark", INT, const=5, source="corpus"),
    1: F("ref_id", GUID, source="exp",
         note="GUID владельца набора — первая половина пары, по которой набор адресуют. У меню "
              "кнопки формы GUID постоянный (`ButtonSet.MenuButtons`): со случайным GUID форма "
              "открывается и сохраняется, но меню не выпадает, поэтому другое значение `validate` "
              "отвергает на уровне 1. Набор командной панели несёт один из четырёх постоянных GUID "
              "(`b78f2e80-…`, `875faa24-…`, `cbcbb11d-…`, `206a2abe-…`) либо GUID из позиции 1 "
              "своего блока действий; набор подменю почти всегда несёт GUID блока. Другое значение "
              "`validate` называет предупреждением уровня 2."),
    2: F("code", INT, source="corpus",
         note="Номер набора у владельца — вторая половина пары, которой набор адресуют."),
}, runs=Runs(4, (
    CountedPairs("buttons", "Element.CommandBarButton", key="id", key_kind=GUID,
                 source="corpus",
                 note="Список кнопок: счётчик, а дальше по два места на кнопку — её GUID и сама "
                      "запись."),
    Fixed({}, length=None),
)), note=(
    "Набор кнопок: `{5, GUID, код, 0, счётчик, GUID, кнопка, GUID, кнопка, …, хвост}`.")))

_add(NodeType("Element.PanelPage", note=(
    "Страница панели или формы: запись `{<код>, Заголовок, Картинка, −1, Видимость, Доступность, "
    "Имя, …}` в списке страниц (`L6+3` блока содержимого панели и контейнера формы). Позиция 0 "
    "имени не имеет: это 3, 4 или 5, и от неё зависит длина записи (8, 10 или 11 позиций).")))
_add(NodeType("PanelPages", note=(
    "Список страниц панели или формы. Вариант выбирается по первому скаляру; известен один вариант "
    "(1). Узел с другим первым скаляром остаётся неразобранным.")))
_add(NodeType("PanelPages.v1", {
    0: F("kind", INT, const=1, source="corpus",
         note="Признак варианта: за единицей идут счётчик и страницы."),
    1: F("count", INT, source="corpus"),
}, repeat=R("items", "Element.PanelPage", start=2, source="corpus"),
   note="Список страниц панели и формы."))


# ── Выбор варианта блока `2/3/1/1` Поля ввода ───────────────────────────────────────────────────────
TEXTBOX_VALUE_BLOCK = "Content.TextBox.u3.u1.u1"
_add(NodeType("Content.TextBox.u3",
              {1: N("u1", "Content.TextBox.u3.u1", source="corpus")}))
_add(NodeType("Content.TextBox.u3.u1",
              {1: N("u1", TEXTBOX_VALUE_BLOCK, source="corpus")}))
MAP["Content.TextBox"].fields[3] = N("u3", "Content.TextBox.u3", source="corpus")
_add(NodeType(TEXTBOX_VALUE_BLOCK,
              note="Блок редактирования поля ввода. Вариант выбирается по первому скаляру (от 0 до "
                   "5); по строению это код вида значения поля: у варианта 4 рядом лежат перенос "
                   "по словам, маска и режим пароля, у варианта 5 — GUID ссылочного типа. Имён у "
                   "кодов нет, поэтому варианты названы числами. Блок с другим кодом остаётся "
                   "неразобранным."))
for _code in (0, 1, 2, 3, 4, 5):
    _add(NodeType(f"{TEXTBOX_VALUE_BLOCK}.v{_code}"))


# ── Список выбора поля выбора: НЕОБЯЗАТЕЛЬНЫЙ блок, а за ним ещё поля ────────────────────────
_add(NodeType("Content.ComboBox.u1", runs=Runs(25, (
    Counted("choice_list", "ValueList", source="exp", at_most=1,
            note="Список выбора — в палитре строка «Строки списка выбора» со ссылкой «Открыть» "
                 "(группа «Использование»). Это счётный список из нуля или одного блока: счётчик "
                 "означает, что список задан."),
    Fixed({
        5: F("choice_list_height", INT, source="lab"),
        6: F("choice_list_width", INT, source="lab"),
    }, length=None),
)), note=(
    "Блок свойств поля выбора: позиции 0–24, затем счётный список выбора и хвост, адресуемый от "
    "конца списка (`L1+…`).")))

_add(NodeType("ValueList", {
    0: F("mark", INT, seen=(9, 8), source="corpus"),
    1: N("columns", "ValueListColumns", source="exp"),
    2: N("u2", "ValueList.u2", source="corpus"),
}, note=(
    "Сериализованный СписокЗначений: `{9\\|8, шапка колонок, тело, {0,0}}`. Позиция 3 — блок "
    "`{0,0}` — есть только при метке 9, и имени у неё нет.")))
_add(NodeType("ValueList.u2", {
    6: N("rows", "ValueListRows", source="exp"),
}, note=(
    "Тело списка `{2,2,0,0,1,1, строки, -1, X}`; позиции, кроме строк, имени не имеют.")))
_add(NodeType("ValueListRows", {
    0: F("mark", INT, const=1, source="corpus"),
    1: F("count", INT, source="corpus"),
}, repeat=R("items", "ValueListRow", start=2, source="exp"),
   note="Счётный список строк `{1, N, строка…}`."))
_add(NodeType("ValueListRow", {
    0: F("mark", INT, const=2, source="corpus"),
    1: F("index", INT, source="corpus",
         note="Номер строки; он не обязан совпадать с местом строки в списке."),
    3: N("value", "TypedValue", source="exp"),
    4: N("presentation", "TypedValue", source="exp",
         note="Представление строки — ссылочное значение под GUID «строки представления»."),
}, note="Запись строки `{2, номер, 2, значение, представление, 0}`."))
_add(NodeType("ValueListColumns", {
    0: F("count", INT, source="corpus",
         note="Число колонок; в списке выбора их всегда две."),
}, repeat=R("items", "ValueListColumn", start=1, source="exp"),
   note="Шапка колонок `{2, колонка, колонка}`."))
_add(NodeType("ValueListColumn", {
    0: F("index", INT, source="corpus",
         note="Номер колонки: 0 у «Value» и 1 у «Presentation»."),
    1: F("name", STR, source="exp"),
    2: N("pattern", "Pattern", source="exp",
         note="Тип колонки — тот же описатель типа (`Pattern`), что у реквизита формы."),
    3: F("caption", STR, source="exp",
         note="Видимый заголовок колонки в диалоге: «Значение» и «Представление»."),
}, note="Запись колонки `{номер, имя, тип, заголовок, 10\\|0}`."))


# ── Выпадающее меню кнопки формы: НЕОБЯЗАТЕЛЬНЫЙ блок за флагом строения ──────────────────────
_add(NodeType("Content.Button.u1", runs=Runs(12, (
    Gated("menu", "CommandBarActions", source="lab",
          by="menu_mode", when=(1, 2), without=(0,),
          note="Выпадающее меню кнопки формы — тот же блок действий, что у командной панели. Когда "
               "меню нет, ключа `menu` в JSON нет."),
    Fixed({
        3: F("layout_state", INT, source="round",
             note="Состояние, которое платформа вычисляет сама при сохранении; это не свойство "
                  "палитры. Записанное сюда значение платформа перезаписывает."),
    }, length=None),
)), note=(
    "Тело записи кнопки формы: голова из двенадцати позиций, необязательный блок меню и хвост.")))


# ── Битовые слова ─────────────────────────────────────────────────────────────────────────────
TABLE_BOX_FLAGS = {
    "header": 0x1,
    "footer": 0x2,                       # Подвал
    "vertical_lines": 0x4,
    "horizontal_lines": 0x8,
    "use_alternation_row_color": 0x10,
    "read_only": 0x400,                  # 1 = редактирование РАЗРЕШЕНО (см. заметку поля)
    "enable_start_drag": 0x4000,
    "auto_insert_new_row": 0x8000,
    "enable_drag": 0x1000000,            # 1 = перетаскивание ЗАПРЕЩЕНО (см. заметку поля)
    "change_setting_of_columns": 0x2000000,
    "change_position_of_columns": 0x4000000,
}

# Табличное поле, `2/3/1/1` варианта 12 (источник — список справочника).
TABLE_BOX_TREE_FLAGS = {"tree": 0x1}

# Колонка табличного поля, `1/1/1/9`.
TABLE_BOX_COLUMN_FLAGS = {
    "show_hierarchy": 0x1,
    "read_only": 0x2,
    "enabled": 0x200,
    "visible": 0x400,
    # Имя то же, что у элементов (`DefaultControl` справочника): у элемента свойство лежит номером в
    # списке раскладки, у колонки — битом, а строка палитры одна.
    "default_control": 0x2000,
    "mark_negatives": 0x8000,
    "skip_on_input": 0x10000,
    "change_visible": 0x40000,           # 1 = изменение ЗАПРЕЩЕНО (см. заметку поля)
    "auto_mark_incomplete": 0x80000,
    "auto_cell_height": 0x100000,
    "hyperlink": 0x200000,
    "change_setting": 0x400000,
    "change_position": 0x800000,
}

# Поле списка, `2/1/1/1`.
LIST_BOX_FLAGS = {
    "read_only": 0x400,                  # 1 = редактирование РАЗРЕШЕНО (см. заметку поля)
}


# ── Поля, подтверждённые копиями диалога ──────────────────────────────────────────────────────
_LAB_FIELDS = [
    # ── Составные значения: по одному применению на узел ──────────────────────────────────────
    ("Element.Button", "2/1/8",
     N("picture", "Picture", source="lab")),
    ("Element.Button", "2/1/9",
     N("shortcut", "Shortcut", source="lab")),
    ("Element.PictureBox", "2/1/0/11",
     N("border", "Border", source="lab")),
    # Применений у рамки два, а не одно, и второе — не украшение.
    ("Element.TextDocumentField", "2/0/11",
     N("border", "Border", source="lab",
       note="Рамка поля текстового документа — тот же блок рамки, что у поля картинки.")),
    ("Element.Label", "2/1/0/4",
     N("font", "Font", source="lab")),
    ("Element.CheckBox", "2/2",
     N("events", "EventList.CheckBox", source="lab")),
    ("Element.GeographicalSchemaField", "3/3",
     N("events", "EventList.GeographicalSchemaField",
       source="lab",
       note="Список обработчиков поля географической схемы. Он лежит не в блоке содержимого, а в "
            "отдельной позиции 3 записи элемента (поэтому запись элемента состоит из семи "
            "позиций); остальные позиции блока `3` имени не имеют.")),

    # ── Кнопка ────────────────────────────────────────────────────────────────────────────────
    ("Element.Button", "2/1/0/12",
     N("tool_tip", "LocalizedString", source="lab")),
    ("Element.Button", "2/1/2",
     N("caption", "LocalizedString", source="lab")),
    ("Element.Button", "2/1/3",
     F("horizontal_align", ENUM, enum="Button.HorizontalAlign",
       source="lab")),
    ("Element.Button", "2/1/4",
     F("vertical_align", ENUM, enum="Button.VerticalAlign",
       source="lab")),
    ("Element.Button", "2/1/6",
     F("picture_location", ENUM, enum="Button.PictureLocation",
       source="lab")),
    ("Element.Button", "2/1/7",
     F("picture_size", ENUM, enum="Button.PictureSize",
       source="lab")),
    ("Element.Button", "2/1/10", F("multi_line", BOOL, source="lab")),
    ("Element.Button", "2/1/11",
     F("menu_mode", ENUM, enum="Button.MenuMode", source="lab",
       note="Свойство «РежимМеню». Оно меняет строение записи: при значениях 1 и 2 в файле "
            "появляется блок меню (`menu`), и хвост записи сдвигается на одну позицию. Менять это "
            "поле в JSON без `menu` нельзя: платформа такой файл не открывает, а `validate` уровня "
            "1 отказывает до записи.")),

    # ── Флажок ────────────────────────────────────────────────────────────────────────────────
    ("Element.CheckBox", "2/1/0/0/1",
     F("enabled", BOOL, source="lab")),
    ("Element.CheckBox", "2/1/0/0/2",
     N("back_color", "Color", source="lab")),
    ("Element.CheckBox", "2/1/0/0/3",
     N("text_color", "Color", source="lab")),
    ("Element.CheckBox", "2/1/0/0/5",
     F("transparent", BOOL, source="lab")),
    ("Element.CheckBox", "2/1/0/0/6",
     N("border_color", "Color", source="lab")),
    ("Element.CheckBox", "2/1/0/0/12",
     N("tool_tip", "LocalizedString", source="lab")),
    ("Element.CheckBox", "2/1/0/2",
     N("caption", "LocalizedString", source="lab")),
    ("Element.CheckBox", "2/1/0/3",
     F("title_location", ENUM, enum="CheckBox.TitleLocation",
       source="lab")),
    ("Element.CheckBox", "2/1/0/4",
     F("horizontal_align", ENUM, enum="CheckBox.HorizontalAlign",
       source="lab")),
    ("Element.CheckBox", "2/1/0/5",
     F("vertical_align", ENUM, enum="CheckBox.VerticalAlign",
       source="lab")),

    # ── Командная панель ──────────────────────────────────────────────────────────────────────
    ("Element.CommandBar", "2/1/0/5",
     F("transparent", BOOL, source="lab")),
    ("Element.CommandBar", "2/1/0/12",
     N("tool_tip", "LocalizedString", source="lab")),
    ("Element.CommandBar", "2/1/2",
     F("orientation", ENUM, enum="CommandBar.Orientation",
       source="lab")),
    ("Element.CommandBar", "2/1/3",
     F("auto_fill", BOOL, source="lab")),
    ("Element.CommandBar", "2/1/4",
     F("buttons_alignment", ENUM, enum="CommandBar.ButtonsAlignment",
       source="lab")),

    # ── Рамка группы ──────────────────────────────────────────────────────────────────────────
    ("Element.GroupBox", "2/1/0/5",
     F("transparent", BOOL, source="lab")),
    ("Element.GroupBox", "2/1/0/12",
     N("tool_tip", "LocalizedString", source="lab")),
    ("Element.GroupBox", "2/1/2",
     N("caption", "LocalizedString", source="lab")),

    # ── Надпись ───────────────────────────────────────────────────────────────────────────────
    ("Element.Label", "2/1/0/1",
     F("enabled", BOOL, source="lab")),
    ("Element.Label", "2/1/0/2",
     N("back_color", "Color", source="lab")),
    ("Element.Label", "2/1/0/3",
     N("text_color", "Color", source="lab")),
    ("Element.Label", "2/1/0/5", F("transparent", BOOL, source="lab")),
    ("Element.Label", "2/1/0/6",
     N("border_color", "Color", source="lab")),
    ("Element.Label", "2/1/0/12",
     N("tool_tip", "LocalizedString", source="lab")),
    ("Element.Label", "2/1/2",
     N("caption", "LocalizedString", source="lab")),
    ("Element.Label", "2/1/3",
     F("horizontal_align", ENUM, enum="Label.HorizontalAlign",
       source="lab")),
    ("Element.Label", "2/1/4",
     F("vertical_align", ENUM, enum="Label.VerticalAlign",
       source="lab")),
    ("Element.Label", "2/1/5", F("hyperlink", BOOL, source="lab")),
    ("Element.Label", "2/1/6", F("mark_negatives", BOOL, source="lab")),
    ("Element.Label", "2/1/9",
     F("scrolling_text", ENUM, enum="Label.ScrollingText",
       source="lab")),
    ("Element.Label", "2/1/10",
     N("format", "LocalizedString", source="lab",
       note="Форматная строка надписи — многоязычная строка, как подсказка.")),

    # ── Панель ────────────────────────────────────────────────────────────────────────────────
    ("Element.Panel", "2/1/0/5", F("transparent", BOOL, source="lab")),
    ("Element.Panel", "2/1/0/12",
     N("tool_tip", "LocalizedString", source="lab")),
    # Позиции `2/1/8`…`2/1/14` из карты УБРАНЫ, и не потому, что имена оказались неверны: адрес у
    # них был снят на форме пула, где все шесть счётных списков блока пусты.

    # ── Табличное поле ────────────────────────────────────────────────────────────────────────
    ("Element.TableBox", "2/2/0/12",
     N("tool_tip", "LocalizedString", source="lab")),
    ("Element.TableBox", "2/2/1/1",
     F("flags", BITS, source="lab", bits=TABLE_BOX_FLAGS,
       note="Слово флагов табличного поля; имя поля дано картой. Биты `read_only` и `enable_drag` "
            "в файле перевёрнуты: значение «Истина» у свойств «ТолькоПросмотр» и "
            "«РазрешитьПеретаскивание» снимает бит, то есть 1 означает «выключено». Карта значения "
            "не переворачивает.")),
    ("Element.TableBox", "2/2/1/9",
     F("horizontal_scroll_bar", ENUM, enum="TableBox.HorizontalScrollBar",
       source="lab")),
    ("Element.TableBox", "2/2/1/10",
     F("vertical_scroll_bar", ENUM, enum="TableBox.VerticalScrollBar",
       source="lab")),
    ("Element.TableBox", "2/2/1/13",
     F("row_input_mode", ENUM, enum="TableBox.RowInputMode",
       source="lab")),
    ("Element.TableBox", "2/2/1/15",
     F("selection_mode", ENUM, enum="TableBox.SelectionMode",
       source="lab")),
    ("Element.TableBox", "2/2/1/16",
     F("header_height", INT, source="lab")),
    ("Element.TableBox", "2/2/1/17",
     F("footer_height", INT, source="lab")),
    ("Element.TableBox", "2/2/1/20",
     F("initial_list_view", ENUM, enum="TableBox.InitialListView",
       source="lab")),
    ("Element.TableBox", "2/2/1/24",
     F("output", ENUM, enum="TableBox.Output", source="lab")),

    # ── Поле ввода ────────────────────────────────────────────────────────────────────────────
    ("Element.TextBox", "2/2/0/0/1",
     F("enabled", BOOL, source="lab")),
    ("Element.TextBox", "2/2/0/0/5",
     F("transparent", BOOL, source="lab")),
    ("Element.TextBox", "2/2/0/0/6",
     N("border_color", "Color", source="lab")),
    ("Element.TextBox", "2/2/0/0/7",
     N("field_back_color", "Color", source="lab")),
    ("Element.TextBox", "2/2/0/0/8",
     N("field_text_color", "Color", source="lab")),
    ("Element.TextBox", "2/2/0/0/9",
     N("button_back_color", "Color", source="lab")),
    ("Element.TextBox", "2/2/0/0/10",
     N("button_text_color", "Color", source="lab")),
    ("Element.TextBox", "2/2/0/0/12",
     N("tool_tip", "LocalizedString", source="lab")),
    ("Element.TextBox", "2/2/0/4",
     F("wrap", BOOL, source="lab",
       note="Перенос по словам: 1 — включён, 0 — выключен. Когда задают маску, конфигуратор "
            "снимает перенос.")),
    ("Element.TextBox", "2/2/0/12",
     F("text_edit", BOOL, source="lab",
       note="Свойство «РедактированиеТекста». В файле значение перевёрнуто: 1 означает, что "
            "редактирование запрещено. Второй адрес — позиция `2/5` записи элемента.")),
    ("Element.TextBox", "2/5",
     F("text_edit_mirror", BOOL, source="lab",
       mirror_of="2/2/0/12",
       note="Второй адрес свойства «РедактированиеТекста».")),
    ("Element.TextBox", "2/2/0/6",
     F("choice_list_button", BOOL, source="lab")),
    ("Element.TextBox", "2/2/0/7", F("choice_button", BOOL, source="lab")),
    ("Element.TextBox", "2/2/0/8", F("clear_button", BOOL, source="lab")),
    ("Element.TextBox", "2/2/0/9", F("spin_button", BOOL, source="lab")),
    ("Element.TextBox", "2/2/0/10", F("open_button", BOOL, source="lab")),
    ("Element.TextBox", "2/2/0/13", F("read_only", BOOL, source="lab")),
    ("Element.TextBox", "2/2/0/17",
     F("horizontal_align", ENUM, enum="TextBox.HorizontalAlign",
       source="lab")),
    ("Element.TextBox", "2/2/0/18",
     F("vertical_align", ENUM, enum="TextBox.VerticalAlign",
       source="lab")),
    ("Element.TextBox", "2/2/0/21",
     F("mask", STR, source="lab",
       note="Свойство «Маска». Платформа записывает его дважды: здесь и в `2/3/1/1/4`.")),
    ("Element.TextBox", "2/2/0/31",
     F("choice_list_height", INT, source="lab")),
    ("Element.TextBox", "2/2/0/32",
     F("choice_list_width", INT, source="lab")),
    ("Element.TextBox", "2/2/0/35",
     F("auto_mark_incomplete", BOOL, source="lab")),
    ("Element.TextBox", "2/2/0/36",
     F("auto_choice_incomplete", BOOL, source="lab")),
    ("Element.TextBox", "2/2/0/37",
     F("incomplete_choice_mode", ENUM, enum="TextBox.IncompleteChoiceMode",
       source="lab")),
    # Три строки с якорем-ВАРИАНТОМ: адрес у них считается от варианта выбора варианта, а не от элемента
    # (см. объявление `Content.TextBox.u3.u1.u1` выше).
    (f"{TEXTBOX_VALUE_BLOCK}.v4", "3",
     F("multi_line", BOOL, source="lab")),
    (f"{TEXTBOX_VALUE_BLOCK}.v4", "4",
     F("mask", STR, source="lab")),
    (f"{TEXTBOX_VALUE_BLOCK}.v4", "5",
     F("password_mode", BOOL, source="lab")),
    ("Element.TextBox", "2/6",
     F("choose_type", BOOL, source="lab")),

    # ── Форма ─────────────────────────────────────────────────────────────────────────────────
    ("Form", "4",
     N("events", "EventList.Form", source="exp",
       note="Список обработчиков событий формы: тринадцать событий с кодами 70000…70012. Записи "
            "лежат в файле по возрастанию кода.")),
    ("Form", "5", F("auto_title", BOOL, source="lab")),
    ("Form", "6",
     F("window_state", ENUM, enum="Form.WindowState",
       source="lab")),
    ("Form", "7",
     F("window_dock_location", ENUM, enum="Form.WindowDockLocation",
       source="lab",
       note="Коды похожи на битовую маску (Лево 1, Верх 2, Право 4, Низ 8), но сочетание двух "
            "сторон не проверялось, и карта его не объявляет.")),
    ("Form", "9",
     F("window_location_center", BOOL, source="lab",
       note="Палитра показывает свойство «РасположениеОкна» одной строкой с тремя значениями, "
            "а файл хранит два флага. Значение «Центрировать» ставит единицу в этой позиции, "
            "«НеПерекрыватьВладельца» — в позиции 16, «Авто» оставляет оба флага нулями.")),
    ("Form", "10",
     F("size_change", ENUM, enum="Form.SizeChange",
       source="lab")),
    ("Form", "11",
     N("context_menu_links", "ContextMenuLinks", source="exp")),
    ("Form", "13/2",
     N("caption_picture", "Picture", source="lab",
       note="Картинка заголовка формы — первая в наборе из трёх картинок; набор устроен так же, "
            "как у надписи и панели.")),
    ("Form", "14",
     F("window_appearance_mode", ENUM, enum="Form.WindowAppearanceMode",
       source="lab")),
    ("Form", "15",
     F("change_window_appearance_mode", ENUM, enum="Form.ChangeWindowAppearanceMode",
       source="lab")),
    ("Form", "16",
     F("window_location_dont_overlap_owner", BOOL,
       source="lab",
       note="Второй флаг свойства «РасположениеОкна»: единица означает «НеПерекрыватьВладельца». "
            "Первый флаг — позиция 9.")),
    ("Form", "17", F("desktop_mode", BOOL, source="lab")),
    ("Form", "18", F("allow_close", BOOL, source="lab")),
    ("Form", "19",
     F("auto_fill_check", BOOL, source="exp",
       note="Свойство «ПроверятьЗаполнениеАвтоматически». Позиция есть только у формы версии 27; у "
            "версии 26 корень формы заканчивается позицией 18.")),
    ("Form", "3/2/1",
     F("save_values", BOOL, source="exp",
       note="Свойство формы «Сохранять значения». У части форм на этом месте лежит блок; тогда "
            "позиция теряет имя.")),
    ("Form", "3/2/4",
     F("restore_values_on_open", BOOL, source="exp",
       note="Свойство формы «ВосстанавливатьЗначенияПриОткрытии». В формах встречается и значение "
            "3; оно не булево, и позиция тогда теряет имя.")),
    ("Form", "3/2/3",
     N("events", "EventList.FormSettings", source="exp",
       note="Обработчики событий «ПередСохранениемЗначений» и «ПослеВосстановленияЗначений». Они "
            "лежат в блоке основного реквизита, хотя палитра показывает их среди событий формы.")),

    # ── Общее у всех типов: блок имени ────────────────────────────────────────────────────────

    # ── Надпись ───────────────────────────────────────────────────────────────────────────────
    ("Element.Label", "2/1/12",
     N("pictures", "PictureSet.Label", source="lab",
       note="Набор из трёх картинок надписи; сама картинка — вторая позиция набора.")),
    ("Element.Label", "2/1/0/11",
     N("border", "Border", source="lab",
       note="Рамка надписи — в общем блоке свойств, как у большинства типов.")),
    ("Element.Label", "2/2",
     N("events", "EventList.Label", source="lab")),

    # ── Кнопка ────────────────────────────────────────────────────────────────────────────────
    ("Element.Button", "2/1/0/1",
     F("enabled", BOOL, source="lab")),
    ("Element.Button", "2/1/0/6",
     N("border_color", "Color", source="lab")),
    ("Element.Button", "2/1/0/9",
     N("button_back_color", "Color", source="lab")),
    ("Element.Button", "2/1/0/10",
     N("button_text_color", "Color", source="lab")),
    ("Element.Button", "2/1/5",
     F("default_button", BOOL, source="lab")),
    ("Element.Button", "2/2",
     N("events", "EventList.Button", source="lab")),

    # ── Флажок ────────────────────────────────────────────────────────────────────────────────
    ("Element.CheckBox", "2/1/0/0/11",
     N("border", "Border", source="lab")),
    ("Element.CheckBox", "2/1/2",
     F("three_state", BOOL, source="lab")),

    # ── Командная панель ──────────────────────────────────────────────────────────────────────
    ("Element.CommandBar", "2/1/0/1",
     F("enabled", BOOL, source="lab")),
    ("Element.CommandBar", "2/1/0/2",
     N("back_color", "Color", source="lab")),
    ("Element.CommandBar", "2/1/0/6",
     N("border_color", "Color", source="lab")),
    ("Element.CommandBar", "2/1/0/9",
     N("button_back_color", "Color",
       source="lab")),
    ("Element.CommandBar", "2/1/0/10",
     N("button_text_color", "Color",
       source="lab")),
    ("Element.CommandBar", "2/1/0/11",
     N("border", "Border", source="lab")),
    ("Element.CommandBar", "2/1/5",
     F("secondary", BOOL, source="lab")),
    ("Element.CommandBar", "2/1/11",
     F("default_button", INT, source="corpus",
       note="Номер кнопки панели, выбранной по умолчанию (`number` кнопки): её текст полужирный, если у кнопки своя процедура (у стандартного действия «Записать и закрыть» — обычный), ноль — такой кнопки нет.")),
    ("Element.CommandBar", "2/1/7",
     N("actions", "CommandBarActions", source="lab-outside",
       note="Блок действий и кнопок панели.")),

    # ── Рамка группы ──────────────────────────────────────────────────────────────────────────
    ("Element.GroupBox", "2/1/0/1",
     F("enabled", BOOL, source="lab")),
    ("Element.GroupBox", "2/1/0/3",
     N("text_color", "Color", source="lab")),
    ("Element.GroupBox", "2/1/0/6",
     N("border_color", "Color", source="lab")),
    ("Element.GroupBox", "2/1/3",
     N("border", "Border.GroupBox", source="lab")),

    # ── Панель ────────────────────────────────────────────────────────────────────────────────
    ("Element.Panel", "2/1/0/1",
     F("enabled", BOOL, source="lab")),
    ("Element.Panel", "2/1/0/2",
     N("back_color", "Color", source="lab",
       note="Свойство панели «ЦветФона». Платформа записывает его дважды: сюда и в конец блока "
            "содержимого панели (`Content.Panel.u1`, позиция `L8+3`, то же имя). Этот адрес — "
            "первичный; `validate` уровня 2 предупреждает, если значения разошлись.")),
    ("Element.Panel", "2/1/0/3",
     N("text_color", "Color", source="lab")),
    ("Element.Panel", "2/1/0/6",
     N("border_color", "Color", source="lab")),
    ("Element.Panel", "2/1/0/11",
     N("border", "Border", source="lab",
       note="Рамка панели доступна в палитре только при «ОтображенииЗакладок» = «Не отображать»; "
            "при других значениях строка серая.")),
    ("Element.Panel", "2/2",
     N("events", "EventList.Panel", source="lab")),

    # ── Поле картинки ─────────────────────────────────────────────────────────────────────────
    ("Element.PictureBox", "2/1/0/1",
     F("enabled", BOOL, source="lab")),
    ("Element.PictureBox", "2/1/0/2",
     N("back_color", "Color", source="lab")),
    ("Element.PictureBox", "2/1/0/3",
     N("text_color", "Color", source="lab")),
    ("Element.PictureBox", "2/1/0/5",
     F("transparent", BOOL, source="lab")),
    ("Element.PictureBox", "2/1/0/6",
     N("border_color", "Color", source="lab")),
    ("Element.PictureBox", "2/1/0/12",
     N("tool_tip", "LocalizedString", source="lab")),
    ("Element.PictureBox", "2/1/2",
     F("picture_size", ENUM, enum="PictureBox.PictureSize",
       source="lab",
       note="Свойство «РазмерКартинки». Второй адрес — в наборе картинок (`2/1/4/1`).")),
    ("Element.PictureBox", "2/1/3",
     F("hyperlink", BOOL, source="lab")),
    ("Element.PictureBox", "2/1/4",
     N("pictures", "PictureSet.PictureBox", source="lab")),
    ("Element.PictureBox", "2/1/6",
     F("zoomable", BOOL, source="lab")),
    ("Element.PictureBox", "2/1/7",
     F("use_context_menu", BOOL, source="lab")),
    ("Element.PictureBox", "2/1/8",
     F("enable_start_drag", BOOL, source="lab")),
    ("Element.PictureBox", "2/1/9",
     F("enable_drag", BOOL, source="lab")),
    ("Element.PictureBox", "2/1/10",
     N("nonselected_picture_text", "LocalizedString",
       source="lab")),
    ("Element.PictureBox", "2/1/14",
     F("scale", INT_DEC, source="lab",
       note="Масштаб поля картинки: 1 — 100 %, остальное — десятичная дробь одинарной точности (373 % — `3.730000019073486`).")),
    ("Element.PictureBox", "2/2",
     N("events", "EventList.PictureBox", source="lab")),

    # ── Поле со списком ───────────────────────────────────────────────────────────────────────
    ("Element.ComboBox", "2/1/0/1",
     F("enabled", BOOL, source="lab")),
    ("Element.ComboBox", "2/1/0/6",
     N("border_color", "Color", source="lab")),
    ("Element.ComboBox", "2/1/0/7",
     N("field_back_color", "Color", source="lab")),
    ("Element.ComboBox", "2/1/0/8",
     N("field_text_color", "Color", source="lab")),
    ("Element.ComboBox", "2/1/0/9",
     N("button_back_color", "Color",
       source="lab")),
    ("Element.ComboBox", "2/1/0/10",
     N("button_text_color", "Color",
       source="lab")),
    ("Element.ComboBox", "2/1/0/11",
     N("border", "Border", source="lab")),
    ("Element.ComboBox", "2/1/0/12",
     N("tool_tip", "LocalizedString", source="lab")),
    ("Element.ComboBox", "2/1/7",
     F("choice_button", BOOL, source="lab")),
    ("Element.ComboBox", "2/1/8",
     F("clear_button", BOOL, source="lab")),
    ("Element.ComboBox", "2/1/9",
     F("spin_button", BOOL, source="lab")),
    ("Element.ComboBox", "2/1/10",
     F("open_button", BOOL, source="lab")),
    ("Element.ComboBox", "2/1/12",
     F("text_edit", BOOL, source="lab",
       note="Свойство «РедактированиеТекста». Значение в файле перевёрнуто, как у поля ввода: 1 "
            "означает, что редактирование запрещено.")),
    ("Element.ComboBox", "2/1/13",
     F("read_only", BOOL, source="lab")),
    # `choice_list_height` и `choice_list_width` стояли ЗДЕСЬ числами 31 и 32 и уехали в раскладку
    # узла `Content.ComboBox.u1` (`L1+5`, `L1+6`): перед ними лежит необязательный блок списка
    # выбора, и номер, снятый с формы пула, верен только при пустом списке.
    ("Element.ComboBox", "2/2",
     N("events", "EventList.ComboBox", source="lab")),

    # ── Поле ввода ────────────────────────────────────────────────────────────────────────────
    ("Element.TextBox", "2/1",
     N("pattern", "Pattern", source="lab",
       note="Описатель типа реквизита, к которому привязано поле.")),
    ("Element.TextBox", "2/2/0/14",
     F("digits", INT, source="lab",
       note="«Длина» в палитре: у числа — разрядность, у строки — длина строки; если длины нет, 0. "
            "У поля ввода в колонке значение выводит платформа из типа колонки, и `set_property` "
            "его там не пишет.")),
    ("Element.TextBox", "2/2/0/15",
     F("fraction_digits", INT, source="lab")),
    ("Element.TextBox", "2/2/0/16",
     F("nonnegative", BOOL, source="lab")),
    ("Element.TextBox", "2/2/0/27",
     F("mark_negatives", BOOL, source="lab")),
    ("Element.TextBox", "2/2/0/28",
     N("picture", "Picture", source="lab",
       note="Картинка поля ввода. Она лежит прямо в этой позиции, а не в наборе из трёх картинок, "
            "как у надписи, панели и поля картинки.")),
    ("Element.TextBox", "2/2/0/30",
     F("date_fractions", ENUM, enum="TextBox.DateFractions",
       source="lab",
       note="Свойство «СоставДаты». В описателе типа (`2/1/1/1`) то же свойство записано буквой, и "
            "коды двух мест не связаны.")),
    ("Element.TextBox", "2/2/0/33",
     N("shortcut", "Shortcut", source="lab",
       note="Сочетание клавиш — тот же блок из трёх позиций, что у кнопки.")),
    ("Element.TextBox", "2/2/0/34",
     N("format", "LocalizedString", source="lab")),
    ("Element.TextBox", "2/2/0/0/11",
     N("border", "Border", source="lab")),
    ("Element.TextBox", "2/4",
     N("events", "EventList.TextBox", source="lab")),
    (f"{TEXTBOX_VALUE_BLOCK}.v4", "6",
     F("extended_edit", BOOL, source="lab")),

    # ── Табличное поле ────────────────────────────────────────────────────────────────────────
    ("Element.TableBox", "2/2/0/1",
     F("enabled", BOOL, source="lab")),
    ("Element.TableBox", "2/2/0/6",
     N("border_color", "Color", source="lab")),
    ("Element.TableBox", "2/2/0/7",
     N("field_back_color", "Color", source="lab")),
    ("Element.TableBox", "2/2/0/8",
     N("field_text_color", "Color",
       source="lab")),
    ("Element.TableBox", "2/2/0/11",
     N("border", "Border", source="lab")),
    ("Element.TableBox", "2/2/1/2",
     N("header_back_color", "Color",
       source="lab")),
    ("Element.TableBox", "2/2/1/3",
     N("header_text_color", "Color",
       source="lab")),
    ("Element.TableBox", "2/2/1/4",
     N("footer_back_color", "Color",
       source="lab")),
    ("Element.TableBox", "2/2/1/5",
     N("footer_text_color", "Color",
       source="lab")),
    ("Element.TableBox", "2/2/1/6",
     N("selection_back_color", "Color",
       source="lab")),
    ("Element.TableBox", "2/2/1/7",
     N("selection_text_color", "Color",
       source="lab")),
    ("Element.TableBox", "2/2/1/8",
     N("alternation_row_back_color", "Color",
       source="lab")),
    ("Element.TableBox", "2/2/1/11",
     F("fixed_left", INT, source="lab")),
    ("Element.TableBox", "2/2/1/12",
     F("fixed_right", INT, source="lab")),
    ("Element.TableBox", "2/2/1/21",
     F("initial_tree_view", ENUM, enum="TableBox.InitialTreeView",
       source="lab",
       note="Свойство «НачальноеОтображениеДерева». Задавая его, конфигуратор включает и флаг "
            "дерева в блоке источника данных (`2/3/1/1`).")),
    ("Element.TableBox", "2/2/1/22",
     F("change_row_set", BOOL, source="lab")),
    ("Element.TableBox", "2/4",
     N("events", "EventList.TableBox", source="lab",
       note="Обычные события табличного поля. Иерархические события лежат отдельным списком в "
            "блоке источника данных (`2/3/1/8`) и есть только у поля, привязанного к списку "
            "иерархического справочника.")),
    # Поля варианта выбора варианта источника данных: адрес считается от самого варианта.
    (f"{TABLE_BOX_SOURCE_BLOCK}.v12", "1",
     F("flags", BITS, bits=TABLE_BOX_TREE_FLAGS, source="lab",
       note="Слово флагов источника данных; назван один проверенный бит — `tree` (отображение "
            "дерева). Имя поля дано картой: в справочнике такого свойства нет.")),
    (f"{TABLE_BOX_SOURCE_BLOCK}.v12", "3",
     F("hierarchical_view", BOOL, source="lab",
       note="Свойство «ИерархическийПросмотр» списка справочника. У источника «таблица значений» "
            "(вариант 5) на этой позиции лежит «ИзменятьПорядокСтрок».")),
    (f"{TABLE_BOX_SOURCE_BLOCK}.v12", "4",
     F("change_hierarchical_view", BOOL,
       source="lab")),
    (f"{TABLE_BOX_SOURCE_BLOCK}.v12", "5",
     F("view_folders_and_items", ENUM, enum="TableBox.ViewFoldersAndItems",
       source="lab")),
    (f"{TABLE_BOX_SOURCE_BLOCK}.v12", "6",
     F("change_current_parent", BOOL,
       source="lab")),
    (f"{TABLE_BOX_SOURCE_BLOCK}.v12", "8",
     N("events", "EventList.TableBox",
       source="lab",
       note="Иерархические события: ПередИзменениемРодителя, ПередУстановкойПометкиУдаления, "
            "ПередРазворачиванием, ПередСворачиванием.")),
    (f"{TABLE_BOX_SOURCE_BLOCK}.v12", "10/1",
     F("new_row_show_check", ENUM, enum="TableBox.NewRowShowCheck",
       source="lab")),
    (f"{TABLE_BOX_SOURCE_BLOCK}.v12", "11",
     F("autonumeration", ENUM, enum="TableBox.Autonumeration",
       source="lab")),
    (f"{TABLE_BOX_SOURCE_BLOCK}.v5", "3",
     F("change_row_order", BOOL, source="lab",
       note="Свойство «ИзменятьПорядокСтрок» источника «таблица значений». У списка справочника "
            "(вариант 12) на этой позиции лежит «ИерархическийПросмотр».")),

    # ── Поле табличного документа ─────────────────────────────────────────────────────────────
    ("Element.SpreadsheetDocumentField", "2/8",
     F("enabled", BOOL, source="lab")),
    ("Element.SpreadsheetDocumentField", "2/9",
     N("border_color", "Color",
       source="lab")),
    ("Element.SpreadsheetDocumentField", "2/10",
     N("border", "Border",
       source="lab")),
    ("Element.SpreadsheetDocumentField", "2/15",
     F("horizontal_scroll_bar", BOOL,
       source="lab")),
    ("Element.SpreadsheetDocumentField", "2/16",
     F("vertical_scroll_bar", BOOL,
       source="lab")),
    ("Element.SpreadsheetDocumentField", "2/17",
     N("events", "EventList.SpreadsheetDocumentField",
       source="lab")),
    ("Element.SpreadsheetDocumentField", "2/18",
     F("read_only", BOOL,
       source="lab",
       note="Свойство «ТолькоПросмотр». Платформа записывает его в трёх местах: здесь, в `2/20` и "
            "внутри встроенного табличного документа (`2/11/55`). `validate` предупреждает, если "
            "значения расходятся.")),
    ("Element.SpreadsheetDocumentField", "2/19",
     F("protection", BOOL,
       source="lab")),
    ("Element.SpreadsheetDocumentField", "2/20",
     F("read_only_mirror", BOOL, mirror_of="2/18",
       source="lab")),
    ("Element.SpreadsheetDocumentField", "2/11/55",
     F("read_only_mirror", BOOL, mirror_of="2/18",
       source="lab",
       note="Третий адрес свойства «ТолькоПросмотр» — внутри встроенного табличного документа.")),
    ("Element.SpreadsheetDocumentField", "2/21",
     F("show_grid", BOOL,
       source="lab")),
    ("Element.SpreadsheetDocumentField", "2/22",
     F("show_headers", BOOL,
       source="lab")),
    ("Element.SpreadsheetDocumentField", "2/23",
     F("show_groups", BOOL,
       source="lab")),
    ("Element.SpreadsheetDocumentField", "2/24",
     F("black_and_white_view", BOOL,
       source="lab")),
    ("Element.SpreadsheetDocumentField", "2/25",
     F("enable_start_drag", BOOL,
       source="lab")),
    ("Element.SpreadsheetDocumentField", "2/26",
     F("enable_drag", BOOL,
       source="lab")),
    ("Element.SpreadsheetDocumentField", "2/27",
     F("show_selection", ENUM, enum="SpreadsheetDocumentField.ShowSelection",
       source="lab")),
    ("Element.SpreadsheetDocumentField", "2/28",
     F("output", ENUM, enum="SpreadsheetDocumentField.Output",
       source="lab")),
    ("Element.SpreadsheetDocumentField", "2/31",
     F("horizontal_scroll_bar_mirror", BOOL, mirror_of="2/15",
       source="lab")),
    ("Element.SpreadsheetDocumentField", "2/32",
     F("vertical_scroll_bar_mirror", BOOL, mirror_of="2/16",
       source="lab")),
    ("Element.SpreadsheetDocumentField", "2/14/4",
     F("show_grid_mirror", BOOL, mirror_of="2/21",
       source="lab")),
    ("Element.SpreadsheetDocumentField", "2/14/5",
     F("show_headers_mirror", BOOL, mirror_of="2/22",
       source="lab")),
    ("Element.SpreadsheetDocumentField", "2/14/7",
     F("show_groups_mirror_1", BOOL, mirror_of="2/23",
       source="lab")),
    ("Element.SpreadsheetDocumentField", "2/14/8",
     F("show_groups_mirror_2", BOOL, mirror_of="2/23",
       source="lab")),
    ("Element.SpreadsheetDocumentField", "2/14/10",
     F("black_and_white_view_mirror", BOOL, mirror_of="2/24",
       source="lab")),

    # ── Подэлементы: списки у родителей ───────────────────────────────────────────────────────
    ("Element.TableBox", "2/2/1/23",
     N("columns", "TableBoxColumns", source="corpus")),
    # Список страниц панели (прежде `2/1/11`) переехал в раскладку `Content.Panel.u1` отрезком
    # `L6+3`: числовой адрес был верен только у панели пула с пустыми счётными списками.

    # ── Колонка табличного поля ───────────────────────────────────────────────────────────────
    ("Element.TableBoxColumn", "1/2",
     F("data", STR, source="lab",
       note="Свойство «Данные» колонки таблицы значений — строка. У колонок других видов на этом "
            "месте лежит число (у колонки списка — флаг «ОтображатьСтандартнуюКартинку»), и "
            "позиция теряет имя (`u2`).")),
    ("Element.TableBoxColumn", "1/1/1/30",
     F("name", STR, source="round",
       note="Имя колонки; другого места для имени в записи нет. Позиция `1/2` колонки — это "
            "«Данные», а не второе имя.")),
    # Всякий, кто сравнивает две формы, обязан знать, что различие здесь — не правка человека.
    ("Element.TableBoxColumn", "1/1/1/32",
     F("width_computed", INT, source="lab",
       note="Состояние конструктора, а не свойство: платформа вычисляет это число сама по ширине "
            "колонки. Записывать его не нужно — платформа его перезапишет.")),
    ("Element.TableBoxColumn", "1/1/1/35",
     N("value_type", "Pattern", source="corpus",
       note="Тип значения колонки — тот же описатель типа (`Pattern`), что у реквизита формы и "
            "переключателя; тип бывает составным.")),
    ("Element.TableBoxColumn", "0",
     F("column_type", GUID, source="corpus",
       note="GUID вида колонки: `48a6ebc3-…` — колонка списка, `c2cf1953-…` — колонка табличной "
            "части, `737535a4-…` — колонка таблицы значений.")),
    ("Element.TableBoxColumn", "1/1/1/1",
     N("header_text", "LocalizedString",
       source="lab")),
    ("Element.TableBoxColumn", "1/1/1/2",
     N("footer_text", "LocalizedString",
       source="lab")),
    ("Element.TableBoxColumn", "1/1/1/3",
     N("header_tool_tip", "LocalizedString",
       source="lab")),
    ("Element.TableBoxColumn", "1/1/1/4",
     F("width", INT_EXP, source="lab")),
    ("Element.TableBoxColumn", "1/1/1/9",
     F("flags", BITS, source="lab",
       bits=TABLE_BOX_COLUMN_FLAGS,
       note="Слово флагов колонки; имя поля дано картой. Бит `change_visible` в файле перевёрнут: "
            "значение «Ложь» у свойства «ИзменятьВидимость» ставит бит. Бит `default_control` — "
            "«Активизировать по умолчанию»: платформа его хранит и показывает, но при добавлении "
            "строки кнопкой не применяет.")),
    ("Element.TableBoxColumn", "1/1/1/10",
     N("header_picture", "Picture",
       source="lab")),
    ("Element.TableBoxColumn", "1/1/1/11",
     N("rows_pictures", "Picture",
       source="lab")),
    ("Element.TableBoxColumn", "1/1/1/12",
     N("footer_picture", "Picture",
       source="lab")),
    ("Element.TableBoxColumn", "1/1/1/16",
     N("field_back_color", "Color",
       source="lab")),
    ("Element.TableBoxColumn", "1/1/1/17",
     N("field_text_color", "Color",
       source="lab")),
    ("Element.TableBoxColumn", "1/1/1/18",
     N("header_back_color", "Color",
       source="lab")),
    ("Element.TableBoxColumn", "1/1/1/19",
     N("header_text_color", "Color",
       source="lab")),
    ("Element.TableBoxColumn", "1/1/1/20",
     N("footer_back_color", "Color",
       source="lab")),
    ("Element.TableBoxColumn", "1/1/1/21",
     N("footer_text_color", "Color",
       source="lab")),
    ("Element.TableBoxColumn", "1/1/1/25",
     F("edit_mode", ENUM, enum="TableBoxColumn.EditMode",
       source="lab")),
    ("Element.TableBoxColumn", "1/1/1/26",
     F("location", ENUM, enum="TableBoxColumn.Location",
       source="lab")),
    ("Element.TableBoxColumn", "1/1/1/27",
     F("header_horizontal_align", ENUM, enum="TableBoxColumn.HeaderHorizontalAlign",
       source="lab")),
    ("Element.TableBoxColumn", "1/1/1/28",
     F("horizontal_align_in_column", ENUM, enum="TableBoxColumn.HorizontalAlignInColumn",
       source="lab")),
    ("Element.TableBoxColumn", "1/1/1/29",
     F("footer_horizontal_align", ENUM, enum="TableBoxColumn.FooterHorizontalAlign",
       source="lab")),
    ("Element.TableBoxColumn", "1/1/1/33",
     F("size_change", ENUM, enum="TableBoxColumn.SizeChange",
       source="lab")),
    ("Element.TableBoxColumn", "1/1/1/34",
     N("format", "LocalizedString", source="lab")),
    ("Element.TableBoxColumn", "1/1/1/37",
     F("cell_height", INT, source="lab")),
    ("Element.TableBoxColumn", "1/1/1/45",
     F("width_mirror", INT_EXP, source="lab",
       mirror_of="1/1/1/4",
       note="Второй адрес ширины колонки — ширина в единицах 96 DPI. При DPI формы 96 значения "
            "равны; при другом DPI ширина больше зеркала во столько же раз (при 120 — в 1,25 "
            "раза), зеркало дробное и теряет имя. `set_property` при DPI не 96 ширину не пишет.")),
    ("Element.TableBoxColumn", "1/3",
     F("check_data", STR, source="lab",
       note="Свойство «ДанныеФлажка» — строка у колонки таблицы значений. У колонки списка здесь "
            "число или позиции нет; тогда позиция теряет имя.")),

    # ── Кнопка командной панели ───────────────────────────────────────────────────────────────
    ("Element.CommandBarButton", "0",
     F("mark", INT, seen=(8, 7), source="corpus")),
    ("Element.CommandBarButton", "1",
     F("name", STR, source="round")),
    ("Element.CommandBarButton", "2",
     F("modifies_data", BOOL,
       source="lab")),
    ("Element.CommandBarButton", "4",
     N("text", "LocalizedString", source="exp",
       note="Видимый текст кнопки — свойство «Текст» в палитре. Это отдельное от имени кнопки "
            "свойство.")),
    ("Element.CommandBarButton", "6",
     F("owner", GUID, source="round",
       note="Владелец кнопки — GUID из позиции 1 того блока действий (`CommandBarActions`), в "
            "котором лежит кнопка: у кнопки командной панели это блок панели, у пункта выпадающего "
            "меню кнопки формы — блок меню. Редактор ставит его сам; `validate` уровня 2 "
            "предупреждает о чужом владельце.")),
    ("Element.CommandBarButton", "7",
     F("number", INT, source="exp",
       note="Сквозной номер кнопки в панели: номера выдаются по порядку создания, начиная с 1, и "
            "не повторяются.")),
    ("Element.CommandBarButton", "9",
     F("button_type", ENUM, enum="CommandBarButton.ButtonType",
       source="lab")),
    ("Element.CommandBarButton", "10",
     F("representation", ENUM, enum="CommandBarButton.Representation",
       source="lab")),
    ("Element.CommandBarButton", "11",
     F("enabled", BOOL, source="lab")),
    ("Element.CommandBarButton", "12",
     F("check", BOOL, source="lab")),

    # ── Страница панели ───────────────────────────────────────────────────────────────────────
    ("Element.PanelPage", "1",
     N("caption", "LocalizedString", source="lab")),
    ("Element.PanelPage", "2",
     N("title_picture", "Picture", source="lab")),
    ("Element.PanelPage", "4",
     F("visible", BOOL, source="lab")),
    ("Element.PanelPage", "5",
     F("enabled", BOOL, source="lab")),
    # Имя страницы — свидетельство КРУГА.
    ("Element.PanelPage", "6",
     F("name", STR, source="round")),

    # ── Поле календаря ────────────────────────────────────────────────────────────────────────
    ("Element.CalendarBox", "2/1/0/1",
     F("enabled", BOOL, source="lab")),
    ("Element.CalendarBox", "2/1/0/5",
     F("transparent", BOOL, source="lab")),
    ("Element.CalendarBox", "2/1/0/7",
     N("field_back_color", "Color",
       source="lab")),
    ("Element.CalendarBox", "2/1/0/8",
     N("field_text_color", "Color",
       source="lab")),
    ("Element.CalendarBox", "2/1/0/9",
     N("button_back_color", "Color",
       source="lab")),
    ("Element.CalendarBox", "2/1/0/10",
     N("button_text_color", "Color",
       source="lab")),
    ("Element.CalendarBox", "2/1/0/11",
     N("border", "Border", source="lab",
       note="Рамка поля календаря. Строки «ЦветРамки» в палитре календаря нет.")),
    ("Element.CalendarBox", "2/1/2",
     N("holiday_color", "Color",
       source="lab")),
    # Две даты периода отображения.
    ("Element.CalendarBox", "2/1/5",
     F("display_period_begin", INT, source="exp",
       note="Свойство «НачалоПериодаОтображения»: дата целым числом вида ГГГГММДДЧЧММСС; непустой период "
            "проверен в 1С:Предприятии. Пустая дата (`00010101000000`) записывается обёрткой "
            "`{\"num\": …}`, и позиция теряет имя.")),
    ("Element.CalendarBox", "2/1/6",
     F("display_period_end", INT, source="exp",
       note="Свойство «КонецПериодаОтображения»: дата целым числом вида ГГГГММДДЧЧММСС; значение 20261231235959 "
            "(конец года, 23:59:59) проверено в 1С:Предприятии.")),
    ("Element.CalendarBox", "2/1/3",
     N("selection_back_color", "Color",
       source="lab")),
    ("Element.CalendarBox", "2/1/4",
     N("selection_text_color", "Color",
       source="lab")),
    ("Element.CalendarBox", "2/1/7",
     F("show_current_date", BOOL, source="lab")),
    ("Element.CalendarBox", "2/1/8",
     F("calendar_navigation", BOOL,
       source="lab")),
    ("Element.CalendarBox", "2/1/9",
     F("selection_mode", ENUM, enum="CalendarBox.SelectionMode",
       source="lab")),
    ("Element.CalendarBox", "2/1/10",
     F("enable_start_drag", BOOL, source="lab")),
    ("Element.CalendarBox", "2/1/11",
     F("enable_drag", BOOL, source="lab")),
    ("Element.CalendarBox", "2/2",
     N("events", "EventList.CalendarBox",
       source="lab")),

    # ── Поле графической схемы ────────────────────────────────────────────────────────────────
    ("Element.GraphicalSchemaField", "2/0/1",
     F("enabled", BOOL, source="lab")),
    ("Element.GraphicalSchemaField", "2/0/5",
     F("transparent", BOOL,
       source="lab")),
    ("Element.GraphicalSchemaField", "2/0/6",
     N("border_color", "Color",
       source="lab")),
    ("Element.GraphicalSchemaField", "2/0/11",
     N("border", "Border",
       source="lab",
       note="Рамка; коды типов рамки те же, что у других типов элементов.")),
    ("Element.GraphicalSchemaField", "2/3",
     N("events", "EventList.GraphicalSchemaField",
       source="lab")),
    ("Element.GraphicalSchemaField", "2/4",
     F("read_only", BOOL,
       source="lab")),

    # ── Поле HTML-документа ───────────────────────────────────────────────────────────────────
    ("Element.HTMLDocumentField", "2/2",
     N("events", "EventList.HTMLDocumentField",
       source="lab")),
    ("Element.HTMLDocumentField", "2/3",
     N("border_color", "Color",
       source="lab")),
    ("Element.HTMLDocumentField", "2/4",
     N("border", "Border",
       source="lab",
       note="Рамка поля HTML-документа лежит прямо в блоке содержимого: общего блока свойств у "
            "этого типа нет.")),
    ("Element.HTMLDocumentField", "2/5",
     F("mode", ENUM, enum="HTMLDocumentField.Mode", source="exp",
       note="Режим: 1 «Просмотр» (по умолчанию), 2 «Редактирование».")),
    ("Element.HTMLDocumentField", "2/6",
     F("output", ENUM, enum="HTMLDocumentField.Output",
       source="lab")),

    # ── Поле списка ───────────────────────────────────────────────────────────────────────────
    ("Element.ListBox", "2/1/0/6",
     N("border_color", "Color", source="lab")),
    ("Element.ListBox", "2/1/0/7",
     N("field_back_color", "Color", source="lab")),
    ("Element.ListBox", "2/1/0/8",
     N("field_text_color", "Color", source="lab")),
    ("Element.ListBox", "2/1/0/11",
     N("border", "Border", source="lab")),
    ("Element.ListBox", "2/1/0/12",
     N("tool_tip", "LocalizedString", source="lab")),
    ("Element.ListBox", "2/1/1/1",
     F("flags", BITS, bits=LIST_BOX_FLAGS, source="lab",
       note="Слово флагов поля списка; имя поля дано картой. Бит `read_only` перевёрнут: 1 "
            "означает, что редактирование разрешено (в палитре «ТолькоПросмотр» = «Ложь»).")),
    ("Element.ListBox", "2/1/4",
     F("show_picture", BOOL, source="lab")),
    ("Element.ListBox", "2/1/5",
     F("show_check_box", BOOL, source="lab")),
    ("Element.ListBox", "2/2",
     N("events", "EventList.ListBox", source="lab")),

    # ── Индикатор ─────────────────────────────────────────────────────────────────────────────
    ("Element.ProgressBar", "2/1/0/1",
     F("enabled", BOOL, source="lab")),
    ("Element.ProgressBar", "2/1/0/2",
     N("back_color", "Color", source="lab")),
    ("Element.ProgressBar", "2/1/0/6",
     N("border_color", "Color", source="lab")),
    ("Element.ProgressBar", "2/1/0/11",
     N("border", "Border", source="lab")),
    ("Element.ProgressBar", "2/1/0/12",
     N("tool_tip", "LocalizedString", source="lab")),
    ("Element.ProgressBar", "2/1/2",
     F("min_value", INT, source="lab")),
    ("Element.ProgressBar", "2/1/3",
     F("max_value", INT, source="lab")),
    ("Element.ProgressBar", "2/1/4",
     F("step", INT, source="lab")),
    ("Element.ProgressBar", "2/1/5",
     F("show_style", ENUM, enum="ProgressBar.ShowStyle",
       source="lab")),
    ("Element.ProgressBar", "2/1/6",
     F("show_percent", BOOL, source="lab")),
    ("Element.ProgressBar", "2/1/7",
     F("orientation", ENUM, enum="ProgressBar.Orientation",
       source="lab")),

    # ── Переключатель ─────────────────────────────────────────────────────────────────────────
    ("Element.RadioButton", "2/1",
     N("pattern", "Pattern", source="lab",
       note="Описатель типа данных переключателя. Платформа заполняет его у первого переключателя "
            "группы (свойство «ПервыйВГруппе»).")),
    ("Element.RadioButton", "2/2/0/0/1",
     F("enabled", BOOL, source="lab")),
    ("Element.RadioButton", "2/2/0/0/2",
     N("back_color", "Color", source="lab")),
    ("Element.RadioButton", "2/2/0/0/3",
     N("text_color", "Color", source="lab")),
    ("Element.RadioButton", "2/2/0/0/5",
     F("transparent", BOOL, source="lab")),
    ("Element.RadioButton", "2/2/0/0/6",
     N("border_color", "Color", source="lab")),
    ("Element.RadioButton", "2/2/0/0/11",
     N("border", "Border", source="lab",
       note="Рамка переключателя — в общем блоке свойств, как у надписи и флажка.")),
    ("Element.RadioButton", "2/2/0/0/12",
     N("tool_tip", "LocalizedString", source="lab")),
    ("Element.RadioButton", "2/2/0/2",
     N("caption", "LocalizedString", source="lab")),
    ("Element.RadioButton", "2/2/0/3",
     F("title_location", ENUM, enum="RadioButton.TitleLocation",
       source="lab")),
    ("Element.RadioButton", "2/2/0/4",
     F("horizontal_align", ENUM, enum="RadioButton.HorizontalAlign",
       source="lab")),
    ("Element.RadioButton", "2/2/0/5",
     F("vertical_align", ENUM, enum="RadioButton.VerticalAlign",
       source="lab")),
    ("Element.RadioButton", "2/4",
     N("selected_value", "TypedValue", source="exp",
       note="Свойство «ВыбираемоеЗначение» — типизированное значение (`TypedValue`), например "
            "`{\"N\",7}`.")),
    ("Element.RadioButton", "2/5",
     N("events", "EventList.RadioButton",
       source="lab")),

    # ── Разделитель ───────────────────────────────────────────────────────────────────────────
    ("Element.Splitter", "2/1/0/1",
     F("enabled", BOOL, source="lab")),
    ("Element.Splitter", "2/1/0/2",
     N("back_color", "Color", source="lab")),
    ("Element.Splitter", "2/1/0/5",
     F("transparent", BOOL, source="lab")),
    ("Element.Splitter", "2/1/0/11",
     N("border", "Border", source="lab",
       note="Рамка разделителя. По умолчанию рамки нет, поэтому строка «ЦветРамки» в палитре "
            "серая.")),
    ("Element.Splitter", "2/1/0/12",
     N("tool_tip", "LocalizedString", source="lab")),
    ("Element.Splitter", "2/1/2",
     F("orientation", ENUM, enum="Splitter.Orientation",
       source="lab")),

    # ── Поле текстового документа ─────────────────────────────────────────────────────────────
    ("Element.TextDocumentField", "2/0/1",
     F("enabled", BOOL, source="lab")),
    ("Element.TextDocumentField", "2/0/6",
     N("border_color", "Color",
       source="lab")),
    ("Element.TextDocumentField", "2/3",
     F("extension", GUID, source="exp",
       note="Расширение поля («Не указано», HTML, «Текстовый макет», «Язык запросов», «Встроенный "
            "язык») — GUID; нулевой GUID значит «Не указано».")),
    ("Element.TextDocumentField", "2/5",
     F("read_only", BOOL, source="exp",
       note="Флаг «ТолькоПросмотр».")),
    ("Element.TextDocumentField", "2/6",
     F("output", ENUM, enum="TextDocumentField.Output", source="exp")),

    # ── Полоса регулирования ──────────────────────────────────────────────────────────────────
    ("Element.TrackBar", "2/1/0/1",
     F("enabled", BOOL, source="lab")),
    ("Element.TrackBar", "2/1/0/2",
     N("back_color", "Color", source="lab")),
    ("Element.TrackBar", "2/1/0/3",
     N("text_color", "Color", source="lab")),
    ("Element.TrackBar", "2/1/0/5",
     F("transparent", BOOL, source="lab")),
    ("Element.TrackBar", "2/1/0/6",
     N("border_color", "Color", source="lab")),
    ("Element.TrackBar", "2/1/0/9",
     N("button_back_color", "Color",
       source="lab")),
    ("Element.TrackBar", "2/1/0/11",
     N("border", "Border", source="lab")),
    ("Element.TrackBar", "2/1/0/12",
     N("tool_tip", "LocalizedString", source="lab")),
    ("Element.TrackBar", "2/1/2",
     F("min_value", INT, source="lab")),
    ("Element.TrackBar", "2/1/3",
     F("max_value", INT, source="lab")),
    ("Element.TrackBar", "2/1/4",
     F("step", INT, source="lab",
       note="Свойство «Шаг». Если шаг больше разности максимума и минимума, платформа без "
            "предупреждения уменьшает его до этой разности.")),
    ("Element.TrackBar", "2/1/5",
     F("large_step", INT, source="lab")),
    ("Element.TrackBar", "2/1/6",
     F("marking_appearance", ENUM, enum="TrackBar.MarkingAppearance",
       source="lab")),
    ("Element.TrackBar", "2/1/7",
     F("orientation", ENUM, enum="TrackBar.Orientation",
       source="lab")),
    ("Element.TrackBar", "2/1/8",
     F("marking_step", INT, source="lab")),
    ("Element.TrackBar", "2/2",
     N("events", "EventList.TrackBar", source="lab")),
]

for _anchor, _path, _slot in _LAB_FIELDS:
    _place(_anchor, _path, _slot)


# ── Общий блок свойств: цвета, которых палитра типа не показывает ─────────────────────────────
_COMMON_COLOR_NAMES = {2: "back_color", 3: "text_color", 6: "border_color",
                       7: "field_back_color", 8: "field_text_color",
                       9: "button_back_color", 10: "button_text_color"}


def _common_color(position):
    """Слот цвета общего блока: имя по позиции."""
    return N(_COMMON_COLOR_NAMES[position], "Color", source="corpus",
             note="Имя дано по той же позиции у других типов элементов, а не по палитре этого "
                  "типа.")


# Якорь, адрес общего блока.
_COMMON_COLOR_GAPS = (
    ("Element.Button", "2/1/0", (2, 3, 7, 8)),
    ("Element.CalendarBox", "2/1/0", (2, 3, 6)),
    ("Element.CheckBox", "2/1/0/0", (7, 8, 9, 10)),
    ("Element.ComboBox", "2/1/0", (2, 3)),
    ("Element.CommandBar", "2/1/0", (3, 7, 8)),
    ("Element.GroupBox", "2/1/0", (2, 7, 8, 9, 10)),
    ("Element.Label", "2/1/0", (7, 8, 9, 10)),
    ("Element.ListBox", "2/1/0", (2, 3, 9, 10)),
    ("Element.Panel", "2/1/0", (7, 8, 9, 10)),
    ("Element.PictureBox", "2/1/0", (7, 8, 9, 10)),
    ("Element.ProgressBar", "2/1/0", (3, 7, 8, 9, 10)),
    ("Element.RadioButton", "2/2/0/0", (7, 8, 9, 10)),
    ("Element.Splitter", "2/1/0", (3, 6, 7, 8, 9, 10)),
    ("Element.TableBox", "2/2/0", (2, 3, 9, 10)),
    ("Element.TextBox", "2/2/0/0", (2, 3)),
    ("Element.TextDocumentField", "2/0", (2, 3, 7, 8, 9, 10)),
    ("Element.TrackBar", "2/1/0", (7, 8, 10)),
)

for _anchor, _base, _positions in _COMMON_COLOR_GAPS:
    for _position in _positions:
        _place(_anchor, f"{_base}/{_position}", _common_color(_position))


# ── ПрозрачныйФон: та же пятая позиция у шести типов, где имени не было ───────────────────────
_TRANSPARENT_NOTE = ("Флаг «ПрозрачныйФон». Имя дано по той же позиции у других типов элементов, "
                     "а не по палитре этого типа.")
for _anchor, _path in (("Element.Button", "2/1/0/5"), ("Element.ComboBox", "2/1/0/5"),
                       ("Element.ListBox", "2/1/0/5"),
                       ("Element.TableBox", "2/2/0/5"), ("Element.TextDocumentField", "2/0/5")):
    _place(_anchor, _path, F("transparent", BOOL, source="corpus", note=_TRANSPARENT_NOTE))
# У индикатора позицию проверила платформа: палитра показывает ☑, фон в предприятии прозрачный.
_place("Element.ProgressBar", "2/1/0/5",
       F("transparent", BOOL, source="exp",
         note="Флаг «ПрозрачныйФон». Проверен в 1С:Предприятии: палитра показывает ☑, фон индикатора прозрачный."))

# ── Поля схем: общий блок свойств по тем же позициям, что у других видов ──────────────────────
# У поля графической схемы общий блок лежит в `2/0`, у поля географической схемы он развёрнут прямо в блоке содержимого (`2/<позиция>`,
# позиция 0 — версия блока, 16). Строение то же, что у остальных видов: позиции 1 «Доступность», 2–3 цвета фона и текста, 5
# «ПрозрачныйФон», 6 цвет рамки, 7–10 цвета поля и кнопки, 11 рамка, 12 подсказка. Имена даны по тем же позициям у других видов:
# у видов схем записи платформы на эти строки нет, а корпус не держит ни одного элемента этих видов.
_SCHEMA_COMMON_NOTE = "Имя дано по той же позиции общего блока у других видов элементов."
# Имена, подтверждённые записью платформы (поле географической схемы: Доступность, ЦветФона, ПрозрачныйФон, ЦветРамки, Рамка, Подсказка; поле графической схемы:
# ЦветФона), имеют источник `exp`; остальные названы по позиции другого вида.
_SCHEMA_CONFIRMED_NOTE = "Имя подтверждено записью платформы: значение в этой позиции меняет именно эта строка палитры."
_GEO_CONFIRMED = (1, 2, 5, 6, 11, 12)
_GRAPH_CONFIRMED = (2,)
for _anchor, _base, _confirmed in (("Element.GraphicalSchemaField", "2/0", _GRAPH_CONFIRMED), ("Element.GeographicalSchemaField", "2", _GEO_CONFIRMED)):
    def _how(position, confirmed=_confirmed):
        return ("exp", _SCHEMA_CONFIRMED_NOTE) if position in confirmed else ("corpus", _SCHEMA_COMMON_NOTE)
    for _position in (2, 3, 7, 8, 9, 10):
        _source, _note = _how(_position)
        _place(_anchor, f"{_base}/{_position}", N(_COMMON_COLOR_NAMES[_position], "Color", source=_source, note=_note))
    _source, _note = _how(12)
    _place(_anchor, f"{_base}/12", N("tool_tip", "LocalizedString", source=_source, note=_note))
for _path, _slot in (
        ("1", F("enabled", BOOL, source="exp", note=_SCHEMA_CONFIRMED_NOTE)),
        ("5", F("transparent", BOOL, source="exp", note=_SCHEMA_CONFIRMED_NOTE)),
        ("6", N("border_color", "Color", source="exp", note=_SCHEMA_CONFIRMED_NOTE)),
        ("11", N("border", "Border", source="exp", note=_SCHEMA_CONFIRMED_NOTE))):
    _place("Element.GeographicalSchemaField", f"2/{_path}", _slot)
# Строки палитры, которые лежат вне общего блока, в карте без имён: положение значения зависит от вида записи. Их называет `schemarows`, пишет `set_property`.
_add(dataclasses.replace(
    MAP["Element.GeographicalSchemaField.u3"],
    note="Запись `u3` элемента без имён позиций, кроме списка обработчиков: позиция 4 — Вывод, позиция 2 — вложенные списки со строками палитры (Проекция, "
         "СмещениеШироты, СмещениеДолготы, Легенда, Заголовок, ПоддержкаМасштаба, Масштаб, четыре границы области) и область данных слоёв с записью слоя (позиция 1 "
         "вложенного списка). Строки пишет `set_property` по именам таблицы в справочнике `set_property`, абзац «Поле географической и поле графической схем»; "
         "ПоддержкаМасштаба, Масштаб и границы области платформа записывает, но при повторном открытии формы не читает; слой переносит операция `copy_layer`."))
_add(dataclasses.replace(
    MAP["Content.GraphicalSchemaField"],
    note="Позиция 2 — запись сетки: ИспользоватьСетку, горизонтальный и вертикальный шаги, РежимОтрисовкиСетки; цвет фона записан в ней вторым местом. "
         "Позиция 5 — Вывод. Строки пишет `set_property` по именам таблицы в справочнике `set_property`, абзац «Поле географической и поле графической схем»."))

# У формы общий блок — это `Layout`, выбор варианта по версии раскладки, и слот надо класть в КАЖДЫЙ её
# вариант: поле абстрактного узла разбор не увидит никогда (`pick` выбирает вариант).
for _position in (7, 8, 9, 10):
    _slot = _common_color(_position)
    for _variant in ("Layout16", "Layout15", "Layout13", "Layout10"):
        _place(_variant, str(_position), _slot)


# ── Голова блока рамки — тот же блок цвета ────────────────────────────────────────────────────
_BORDER_HEAD_NOTE = ("Голова блока рамки — блок цвета `{3, вид, {код}}`. Какой это цвет, не "
                     "установлено; свойство «ЦветРамки» лежит в другом месте.")
_BORDER_HEAD = {
    0: F("mark", INT, const=3, source="corpus", note=_BORDER_HEAD_NOTE),
    1: F("color_kind", INT, source="corpus", note=_BORDER_HEAD_NOTE),
    2: N("value", "ColorValue", source="corpus", note=_BORDER_HEAD_NOTE),
}
for _name in ("Border", "Border.GroupBox"):
    for _position, _slot in _BORDER_HEAD.items():
        _place(_name, str(_position), _slot)


# ── Второй адрес свойств строки у поля ввода ──────────────────────────────────────────────────
_TEXTBOX_SECOND = ("Второй адрес свойства. Палитра при правке пишет только первичное поле, а "
                   "`set_property` записывает оба места.")
_LAB_MIRRORS = [
    ("Element.TextBox", "2/2/0/26",
     F("multi_line_mirror", BOOL, source="corpus", mirror_of="2/3/1/1/3",
       primary_only=True,
       note=_TEXTBOX_SECOND)),
    ("Element.TextBox", "2/2/0/5",
     F("password_mode_mirror", BOOL, source="corpus", mirror_of="2/3/1/1/5",
       primary_only=True,
       note=_TEXTBOX_SECOND)),
    ("Element.TextBox", "2/2/0/38",
     F("extended_edit_mirror", BOOL, source="corpus", mirror_of="2/3/1/1/6",
       primary_only=True,
       note=_TEXTBOX_SECOND)),
    # Четвёртая позиция зеркалом НЕ является: значения у неё другие.
    ("Element.TextBox", "2/2/0/3",
     F("multi_line_code", INT, source="corpus",
       note="Значение, производное от `multi_line` (`2/3/1/1/3`): 2, если многострочный режим "
            "включён, и 0, если нет.")),
]

for _anchor, _path, _slot in _LAB_MIRRORS:
    _place(_anchor, _path, _slot)


# ── Безымянные позиции надписи ────────────────────────────────────────────────────────────────
_LABEL_ROUND7P = [
    ("2/1/11", F("picture_location", ENUM, enum="Label.PictureLocation", source="round",
                 note="Свойство надписи «ПоложениеКартинки». Коды не совпадают с кодами кнопки "
                      "(`Button.PictureLocation`).")),
    ("2/1/13", F("picture_size", ENUM, enum="Label.PictureSize", source="round",
                 note="Свойство надписи «РазмерКартинки». Это не второй адрес размера из набора "
                      "картинок (`2/1/12/1`): значения в двух местах независимы.")),
    ("2/1/12/6", F("border_state", INT, source="round",
                   note="Состояние, которое платформа вычисляет сама при сохранении; это не "
                        "свойство палитры. Записанное сюда значение платформа перезаписывает.")),
]
for _path, _slot in _LABEL_ROUND7P:
    _place("Element.Label", _path, _slot)


# ── Остаток свойств частых типов ──────────────────────────────────────────────────────────────
_add(NodeType("TypeLink", runs=Runs(1, (
    Counted("items", "TypeLinkEntry", source="exp", at_most=1,
            note="Связь по типу — счётный список из нуля или одной записи."),
)), note="Блок «Связь по типу» поля ввода: `{1, счётчик, запись…}`."))
_add(NodeType("TypeLinkEntry", {
    2: N("path", "TypeLinkPath", source="exp",
         note="Путь к реквизиту, с которым связан тип поля."),
}, note="Запись связи по типу: `{0, GUID, путь}`. Позиции 0 и 1 имени не имеют. В предприятии "
        "связь работает так: при пустом значении окно «Выбор типа данных» (F4) предлагает только "
        "типы связанного реквизита, очистка (Shift+F4) даёт пустое значение этого типа, а смена "
        "типа в связанном реквизите уже введённое значение не приводит. Связь пишет операция "
        "`set_type_link`."))
_add(NodeType("TypeLinkPath", runs=Runs(1, (
    Counted("steps", "AttributePathStep", source="corpus"),
)), note="Путь связи по типу: `{2, счётчик, шаг…}` — как путь привязки данных, но с головой; "
         "первая позиция всегда 2."))
_add(NodeType("SavedValues", {
    1: F("count", INT, source="exp"),
}, repeat=R("items", "SavedValue", start=2, source="exp"),
   note="Список «Сохраняемые значения» формы: `{0, счётчик, запись…}`. У форм объектов (например, "
        "формы элемента справочника) на этом месте лежит список событий объекта, и у узла в JSON "
        "нет поля `count`. Без `count` это не список значений: дописанная в него запись станет "
        "испорченным событием, и `validate` этого не заметит."))
_add(NodeType("SavedValue", note=(
    "Запись сохраняемого значения: `{\"#\", 91f722a0-4cc1-11d6-a3c9-0050bae0a776, {3, GUID, имя "
    "реквизита формы, признак[, {id}]}}`.")))
# ── Вложенный элемент колонки ─────────────────────────────────────────────────────────────────
_add(NodeType("ColumnControl", note=(
    "Содержимое вложенного элемента колонки. Вариант выбирается по первому числу тела "
    "(`content_kind` узла `Content.<Тип>`): 9 — поле ввода, 1 — флажок, 2 — поле выбора. Строение "
    "то же, что у содержимого элемента этого вида на форме. Вид должен совпадать с GUID типа у "
    "колонки (`control_type`); если они расходятся, `validate` уровня 2 отказывает и называет оба "
    "места.")))
_add(NodeType("ColumnControl.Packed", {
    0: N("content", "ColumnControl", source="exp",
         note="Содержимое вложенного элемента — того же вида, что `control_type` колонки."),
    1: F("empty_chunks", INT, source="corpus",
         note="Число пустых кусков за телом в конверте; каждый кусок — 27 байт (тот же заголовок и "
              "сжатая пустая строка). Правка тела сохраняет это число, новый элемент получает 0."),
    2: F("layout", STR, source="corpus",
         note="Признак нестандартной раскладки строк base64 — тот же, что поле `layout` у обёртки "
              "уровня 0. При обычной раскладке поля нет."),
}, packed=Packed(
    payload=F("packed", B64, source="exp",
              note="Так позиция выглядит в файле: одна строка base64."),
    note="Конверт `{#base64:…}` (`frm_codec.packed`): 18 байт постоянного заголовка "
         "`0201534b6ff4888dc14ea0d5ebb6bda0a70d`, raw deflate, 8 байт длины, BOM и текст тела; за "
         "телом — пустые куски."),
    note="Вложенный элемент колонки в конверте base64."))
_add(NodeType("TableBoxColumn.Control", {
    0: N("element", "ColumnControl.Packed", source="exp",
         note="Сам вложенный элемент — в конверте base64 (узел `ColumnControl.Packed`)."),
}, runs=Runs(1, (
    Counted("links", "TypeLinkEntry", source="corpus",
            note="Связи вложенного элемента: счётный список записей того же строения, что у связи "
                 "по типу поля ввода (`TypeLinkEntry`). Запись с 0 в позиции 0 повторяет связь по "
                 "типу вложенного поля ввода; `set_type_link` пишет и снимает её в обоих местах. "
                 "Смысл записей с 1 не проверялся."),
)), note=(
    "Вложенный элемент колонки — элемент, которым редактируется значение ячейки (свойство "
    "«ЭлементУправления»; тип ПолеВвода, ПолеВыбора или Флажок): `{конверт, счётчик, запись…}`. "
    "Смена типа элемента заменяет конверт целиком.")))

_X16_FIELDS = [
    ("Element.SpreadsheetDocumentField", "2/12",
     F("save_position", BOOL, source="exp",
       note="Свойство «Сохранять позицию» (группа «Использование»). В справочнике платформы этого "
            "свойства нет, поэтому английское имя поля составлено по подписи в палитре; это не "
            "`СохранятьСвойстваОтображения`.")),
    ("Element.SpreadsheetDocumentField", "2/13",
     F("save_fixing_position", BOOL, source="exp",
       note="Свойство «Сохранять позицию фиксации» (группа «Использование»); по умолчанию "
            "включено.")),
    ("Element.TextBox", "2/2/0/11",
     F("fixed_fraction_digits", BOOL, source="exp",
       note="Свойство «ФиксДробнаяЧасть» (группа «Характеристики»); у числа по умолчанию включено. "
            "В справочнике платформы свойства нет, английское имя составлено картой.")),
    ("Element.TextBox", "2/2/0/29",
     N("choice_button_picture", "Picture", source="exp",
       note="Свойство «КартинкаКнопкиВыбора» (`ChoiceButtonPicture`); доступно при включённой "
            "«КнопкаВыбора».")),
    ("Element.TextBox", "2/8",
     N("type_link", "TypeLink", source="exp",
       note="Свойство «Связь по типу» (группа «Использование»): путь к реквизиту, с которым связан "
            "тип значения поля. Это не свойство `ЭлементСвязиПоТипу` из справочника, где хранится "
            "номер элемента; английское имя взято у свойства `СвязьПоТипу` (`TypeLink`) "
            "управляемой формы. Связь пишет операция `set_type_link`.")),
    ("Element.PictureBox", "2/1/5",
     N("shortcut", "Shortcut", source="exp",
       note="Свойство «СочетаниеКлавиш» поля картинки — тот же блок из трёх позиций, что у кнопки. "
            "В палитре оно доступно только при включённой «Гиперссылке».")),
    ("Element.TableBox", "2/2/1/14",
     F("row_selection_mode", ENUM, enum="TableBox.RowSelectionMode", source="exp",
       note="Свойство табличного поля «РежимВыделенияСтроки».")),
    ("Element.TableBoxColumn", "1/4",
     F("picture_data", STR, source="exp",
       note="Свойство «ДанныеКартинки» (`PictureData`) колонки таблицы значений: имя "
            "колонки-источника картинки. У колонок других видов этой позиции нет.")),
    ("Element.TableBoxColumn", "1/1/1/38",
     F("control_type", GUID, source="exp",
       note="Свойство «ЭлементУправления» колонки: GUID типа вложенного элемента из того же "
            "словаря, что у элементов формы (поле ввода, поле выбора, флажок); пустой GUID — "
            "элемента нет. От него зависит строение головы колонки.")),
    ("Element.TableBoxColumn", "1/1/1/39",
     N("control", "TableBoxColumn.Control", source="exp",
       note="Вложенный элемент колонки (узел `TableBoxColumn.Control`). Если элемента нет, на этом "
            "месте стоит число 0, и позиция теряет имя.")),
    ("Form", "3/2/2",
     N("saved_values", "SavedValues", source="exp",
       note="Свойство формы «Сохраняемые значения» — список реквизитов, значения которых "
            "сохраняются. У форм объектов на этом месте лежит другой список (узел `SavedValues`).")),
]
for _anchor, _path, _slot in _X16_FIELDS:
    _place(_anchor, _path, _slot)


# ── Последние свойства частых типов и формы ───────────────────────────────────────────────────
_X18_FIELDS = [
    ("Form", "12/1",
     F("style", GUID, source="exp",
       note="Свойство формы «Стиль» (`Style`, группа «Оформление») — GUID объекта стиля "
            "конфигурации. Если стиль «Авто», позиции нет: блок состоит из одной позиции.")),
    ("Element.TextBox", "2/9",
     F("list_choice_mode", BOOL, source="exp",
       note="Свойство «РежимВыбораИзСписка» (`ListChoiceMode`, группа «Использование») у поля "
            "ввода формы и у поля ввода в колонке. Когда режим включают в палитре, платформа "
            "заодно ставит «КнопкаСпискаВыбора», у поля формы снимает «КнопкаВыбора» и "
            "«КнопкаОчистки» и меняет блок редактирования поля. `set_property` записывает эти "
            "сопутствующие изменения сам.")),
    ("Attributes", "0/0",
     F("main_attribute_id", INT, source="exp",
       note="Свойство формы «Данные» (`Data`, группа «Основные»): номер реквизита формы, "
            "назначенного основным; −1 — основного реквизита нет. Это то же число, что в блоке "
            "номера самого реквизита (`list/items/*/u0`) и в первом шаге пути привязки данных. "
            "Признака «основной» у самого реквизита нет. `set_property` это поле не пишет и "
            "отказывает: смена основного реквизита перестраивает форму.")),
]
for _anchor, _path, _slot in _X18_FIELDS:
    _place(_anchor, _path, _slot)


# ── Версия записи и версии вложенных блоков ───────────────────────────────────────────────────
_RECORD_VERSION = "Версия записи; от неё зависит длина записи."
for _anchor, _path in (("Element.Label", "2/1/1"), ("Element.Button", "2/1/1"),
                       ("Element.CommandBar", "2/1/1"), ("Element.CheckBox", "2/1/1"),
                       ("Element.CheckBox", "2/1/0/1"), ("Element.ComboBox", "2/1/1"),
                       ("Element.TextBox", "2/2/0/1"), ("Element.RadioButton", "2/2/1"),
                       ("Element.RadioButton", "2/2/0/1"), ("Element.GroupBox", "2/1/1"),
                       ("Element.PictureBox", "2/1/1")):
    _place(_anchor, _path, F("record_version", INT, source="corpus", note=_RECORD_VERSION))

# Версия есть и у вложенных блоков.
_FONT_VERSION = F("version", INT, source="corpus",
                  note="Версия записи шрифта: 6 при версии общего блока 10, 7 при 13, 15 и 16.")
for _variant in ("Font.v0", "Font.v1", "Font.v2", "Font.v3"):
    _place(_variant, "0", _FONT_VERSION)

# ── Шрифт у прочих элементов ──────────────────────────────────────────────────────────────────
_FONT_PLACE = "Запись шрифта — тот же узел, что у надписи."
_FONT_PLACES = [
    ("Element.Button", "2/1/0/4", "font", "lab"),
    ("Element.CalendarBox", "2/1/0/4", "font", "lab"),
    ("Element.CheckBox", "2/1/0/0/4", "font", "lab"),
    ("Element.ComboBox", "2/1/0/4", "font", "lab"),
    ("Element.CommandBar", "2/1/0/4", "font", "lab"),
    ("Element.GroupBox", "2/1/0/4", "font", "lab"),
    ("Element.ListBox", "2/1/0/4", "font", "lab"),
    ("Element.Panel", "2/1/0/4", "font", "lab"),
    ("Element.PictureBox", "2/1/0/4", "font", "lab"),
    ("Element.ProgressBar", "2/1/0/4", "font", "lab"),
    ("Element.RadioButton", "2/2/0/0/4", "font", "lab"),
    ("Element.Splitter", "2/1/0/4", "font", "corpus"),
    ("Element.TableBox", "2/2/0/4", "font", "lab"),
    ("Element.TableBox", "2/2/1/18", "header_font", "lab"),
    ("Element.TableBox", "2/2/1/19", "footer_font", "lab"),
    ("Element.TableBoxColumn", "1/1/1/22", "text_font", "lab"),
    ("Element.TableBoxColumn", "1/1/1/23", "header_font", "lab"),
    ("Element.TableBoxColumn", "1/1/1/24", "footer_font", "lab"),
    ("Element.TextBox", "2/2/0/0/4", "font", "lab"),
    ("Element.TextDocumentField", "2/0/4", "font", "lab"),
    ("Element.TrackBar", "2/1/0/4", "font", "corpus"),
]

for _anchor, _path, _name, _source in _FONT_PLACES:
    _place(_anchor, _path, N(_name, "Font", source=_source, note=_FONT_PLACE))

_PICTURE_SET_VERSION = F("version", INT, source="corpus",
                         note="Версия записи набора картинок: 3 при версии общего блока 10, 4 при "
                              "13, 7 при 15, 8 при 16. От версии зависит длина набора: 3, 5, 8 и 9 "
                              "позиций соответственно.")
for _name in ("PictureSet.Label", "PictureSet.Panel", "PictureSet.PictureBox"):
    _place(_name, "0", _PICTURE_SET_VERSION)

# У самой картинки нулевая позиция ВЕРСИЕЙ не названа, и решили это два адреса из семи.
_place("Picture", "0",
       F("mark", INT, source="corpus",
         note="Метка блока картинки; это не версия. Метка задаёт длину записи: при 3 и 7 хвостовой "
              "позиции нет, при 4 и 8 она есть, 0 бывает у пустой картинки поля картинки. Редактор "
              "не пишет это поле по имени."))

# Позиция 13 корня формы — тот же набор из трёх картинок, что у надписи и панели, и это видно по
# числам: длины 3, 5, 8 и 9, нулевая позиция 3/4/7/8 по версии общего блока, вторая — блок картинки
# длиной 8…10.
_place("Element.SpreadsheetDocumentField", "2/14/0",
       F("version", INT, source="corpus",
         note="Версия записи блока `2/14`: 1 при `content_kind` 14, 2 при 16, 3 при 17 и 18. Что "
              "за запись лежит в `2/14`, не установлено."))

_place("Form", "13/0",
       F("version", INT, source="corpus",
         note="Версия записи набора картинок формы: 3 при версии общего блока 10, 4 при 13, 7 при "
              "15, 8 при 16."))


# Перечисления. Ключ включает тип элемента НАРОЧНО: коды установлены у конкретного типа, и у Надписи
# с Полем ввода `ВертикальноеПоложение` совпадать не обязано.
ENUMS = {
    # Рамка: коды сняты у девятнадцати типов, и все девятнадцать дали ОДНО И ТО ЖЕ.
    "PictureBox.Border": Enum({"Indented": 3, "Embossed": 2, "Double": 200,
                               "DoubleUnderline": 5, "Single": 1, "Underline": 4, "Overline": 7,
                               "WithoutBorder": 0}, default="WithoutBorder",
                              source="lab",
                              missing=("Rounded (not_in_palette)",),
                              note="Коды идут не подряд: «Двойная» — 200, «Черта сверху» — 7, кода "
                                   "6 нет."),
    # События. Ключ тот же `<Тип>.<Свойство>`, только свойство здесь одно на все события типа: коды
    # лежат в ОДНОЙ позиции записи обработчика, и перечисление у неё общее.
    "CheckBox.Event": Enum({"OnChange": 2147483647},
                           source="lab",
                           note="Единственное событие флажка в палитре 8.3.27."),
    "GeographicalSchemaField.Event": Enum(
        {"Selection": 0, "DetailProcessing": 1},
        source="lab"),
    "Button.HorizontalAlign": Enum({"Left": 0, "Center": 1, "Right": 2}, default="Center",
                                   source="lab",
                                   missing=("Auto (not_in_palette)", "Justify (not_in_palette)")),
    "Button.VerticalAlign": Enum({"Top": 0, "Center": 1, "Bottom": 2}, default="Center",
                                 source="lab"),
    "Button.PictureLocation": Enum({"Left": 0, "Right": 1}, default="Left",
                                   source="lab"),
    "Button.MenuMode": Enum({"DontUse": 0, "Use": 1, "UseExtra": 2}, default="DontUse",
                            source="lab"),
    "Button.PictureSize": Enum({"RealSize": 0, "Stretch": 1, "Proportionally": 2, "Tile": 3,
                                "AutoSize": 4, "ByFontSize": 7}, default="RealSize",
                               source="lab",
                               missing=("AutoSizeIgnoreScale (not_in_palette)",
                                        "RealSizeIgnoreScale (not_in_palette)")),
    "CheckBox.HorizontalAlign": Enum({"Left": 0, "Center": 1, "Right": 2}, default="Left",
                                     source="lab",
                                     missing=("Auto (not_in_palette)", "Justify (not_in_palette)")),
    "CheckBox.VerticalAlign": Enum({"Top": 0, "Center": 1, "Bottom": 2}, default="Center",
                                   source="lab"),
    "CheckBox.TitleLocation": Enum({"TitleLeft": 0, "TitleRight": 1}, default="TitleRight",
                                   source="lab"),
    "CommandBar.Orientation": Enum({"Vertical": 0, "Horizontal": 1, "Auto": 2}, default="Auto",
                                   source="lab"),
    "CommandBar.ButtonsAlignment": Enum({"Left": 0, "Center": 1, "Right": 2}, default="Left",
                                        source="lab"),
    "Label.HorizontalAlign": Enum({"Left": 0, "Center": 1, "Right": 2, "Auto": 4},
                                  default="Auto", source="lab",
                                  missing=("Justify (not_in_palette)",)),
    "Label.VerticalAlign": Enum({"Top": 0, "Center": 1, "Bottom": 2}, default="Center",
                                source="lab"),
    "Label.ScrollingText": Enum({"DontUse": 0, "VerySlow": 1, "Slow": 2, "Normal": 3, "Fast": 4,
                                 "VeryFast": 5}, default="DontUse",
                                source="lab"),
    # Умолчания у них не объявлено.
    "Label.PictureLocation": Enum({"Left": 1, "Right": 3, "Center": 5}, source="round",
                                  seen=((2, 110),),
                                  note="Свойство надписи «ПоложениеКартинки». Коды не совпадают с "
                                       "кодами кнопки (`Button.PictureLocation`); значение 2 не "
                                       "проверялось."),
    "Label.PictureSize": Enum({"RealSize": 0, "AutoSize": 4}, source="round", seen=((2, 3),)),
    "Panel.PictureSize": Enum({"RealSize": 0, "Stretch": 1, "Proportionally": 2, "Tile": 3,
                               "AutoSize": 4, "ByFontSize": 7}, default="Stretch",
                              source="lab",
                              missing=("AutoSizeIgnoreScale (not_in_palette)",
                                       "RealSizeIgnoreScale (not_in_palette)"),
                              seen=((11, 752), (368, 607), (22, 403), (37, 371), (24, 356),
                                    (451, 341), (316, 239), (30, 198), (31, 194))),
    "Panel.ShowTabs": Enum({"DontUse": 0, "Top": 1, "Bottom": 2, "LeftVertical": 3,
                            "RightVertical": 4, "LeftHorizontal": 5, "RightHorizontal": 6,
                            "TopScrolling": 7, "TopMultiLine": 8,
                            "TopMultilineTransposition": 9, "BottomScrolling": 10,
                            "BottomMultiLine": 11, "BottomMultilineTransposition": 12},
                           default="Top", source="lab",
                           seen=((16, 9),),
                           note="Код 13 без имени: панель с включённым режимом прокручиваемых страниц показывает заголовки страниц друг под другом "
                                "и полосу прокрутки вместо закладок."),
    # Кодов ДВА, хотя в списке палитры пять пунктов (Лево, Верх, Право, Низ, Центр) — остальные три
    # никто не ставил.
    "Panel.PictureLocation": Enum({"Right": 3, "Center": 5}, source="exp",
                                  seen=((2, 1),),
                                  note="Свойство панели «ПоложениеКартинки» "
                                       "(`ПоложениеКартинкиПанели` в справочнике); проверены два "
                                       "значения из пяти."),
    "Form.PictureLocation": Enum({"Right": 3, "Center": 5}, source="exp",
                                 seen=((4, 3), (2, 1)),
                                 note="Свойство формы «ПоложениеКартинки»; коды те же, что у "
                                      "панели."),
    "TableBox.HorizontalScrollBar": Enum({"DontUse": 0, "UseAlways": 1, "AutoUse": 2},
                                         default="AutoUse",
                                         source="lab"),
    "TableBox.VerticalScrollBar": Enum({"DontUse": 0, "UseAlways": 1, "AutoUse": 2},
                                       default="AutoUse",
                                       source="lab"),
    "TableBox.RowInputMode": Enum({"EndOfList": 0, "EndOfWindow": 1, "AfterCurrentRow": 2,
                                   "BeforeCurrentRow": 3}, default="EndOfList",
                                  source="lab"),
    "TableBox.SelectionMode": Enum({"SingleLine": 0, "MultiLine": 1}, default="SingleLine",
                                   source="lab"),
    # Пунктов в палитре ровно два.
    "TableBox.RowSelectionMode": Enum({"Cell": 0, "Row": 1}, source="exp",
                                      note="Свойство табличного поля «РежимВыделенияСтроки»."),
    "TableBox.InitialListView": Enum({"Beginning": 0, "End": 1, "Auto": 2}, default="Auto",
                                     source="lab",
                                     seen=((4294967295, 188),)),
    "TableBox.Output": Enum({"Auto": 0, "Enable": 1, "Disable": 2}, default="Auto",
                            source="lab"),
    "TextBox.HorizontalAlign": Enum({"Left": 0, "Center": 1, "Right": 2, "Auto": 4},
                                    default="Auto",
                                    source="lab",
                                    missing=("Justify (not_in_palette)",)),
    "TextBox.VerticalAlign": Enum({"Top": 0, "Center": 1, "Bottom": 2}, default="Top",
                                  source="lab"),
    "TextBox.IncompleteChoiceMode": Enum({"OnEnterPressed": 0, "OnActivate": 1},
                                         default="OnEnterPressed",
                                         source="lab"),
    # Форма.
    "Form.EnterKeyBehavior": Enum({"DefaultButton": 0, "ControlNavigation": 1},
                                  default="ControlNavigation",
                                  source="lab"),
    "Form.SizeChange": Enum({"Change": 0, "DontChange": 1}, default="Change",
                            source="lab"),
    # Своё перечисление, а не `Panel.ShowTabs`, хотя блок один и тот же.
    "Form.ShowTabs": Enum({"DontUse": 0, "Top": 1}, default="DontUse",
                          source="exp",
                          note="Свойство формы «ОтображениеЗакладок». Проверены коды двух значений "
                               "из десяти; код 13 встречается в формах вместе с "
                               "«РежимПрокручиваемыхСтраниц»."),
    # Шрифт.
    "Font.Source": Enum({"Absolute": 0, "SystemFont": 1, "StyleFont": 2, "Auto": 3},
                        source="round",
                        note="Вид записи шрифта. По этому полю выбирается вариант узла `Font`, "
                             "поэтому имя есть у каждого кода."),
    "Font.StyleFont": Enum({"TextFont": -20, "SmallTextFont": -30, "NormalTextFont": -31,
                            "LargeTextFont": -32, "ExtraLargeTextFont": -33},
                           source="round", seen=((0, 257),),
                           note="Шрифты стиля платформы: −20 — «Шрифт текста», −30 — «Мелкий шрифт "
                                "текста», −31 — «Обычный шрифт текста», −32 — «Крупный шрифт "
                                "текста», −33 — «Очень крупный шрифт текста». Код 0 встречается "
                                "рядом с GUID и имени не имеет."),
    "Font.SystemFont": Enum({"DialogsAndMenus": 0}, source="round",
                            note="Пункты списка «Системный шрифт» диалога «Выбор шрифта». Проверен "
                                 "только первый пункт: 0 — «Шрифт диалогов и меню»."),
    "Form.WindowState": Enum({"Docked": 1, "Float": 2, "Normal": 4, "Autohide": 16},
                             default="Normal", source="lab"),
    "Form.WindowDockLocation": Enum({"Left": 1, "Top": 2, "Right": 4, "Bottom": 8},
                                    default="Left",
                                    source="lab"),
    "Form.WindowAppearanceMode": Enum({"Minimized": 0, "Normal": 1, "Maximized": 2},
                                      default="Normal",
                                      source="lab"),
    "Form.ChangeWindowAppearanceMode": Enum({"Enable": 0, "Disable": 1, "Auto": 2},
                                            default="Auto",
                                            source="lab"),
    "Form.Event": Enum({"BeforeOpen": 70000, "OnOpen": 70001, "BeforeClose": 70002,
                        "OnClose": 70003, "ChoiceProcessing": 70004,
                        "ObjectActivationProcessing": 70005,
                        "NewObjectWriteProcessing": 70006, "NotificationProcessing": 70007,
                        "OnReopen": 70008, "RefreshDisplay": 70009, "ExternalEvent": 70010,
                        "AddInDetachmentOnError": 70011, "FillCheckProcessing": 70012},
                       source="exp",
                       note="Записи обработчиков лежат в файле по возрастанию кода, а не в порядке "
                            "палитры: «ПриПовторномОткрытии» и «ОбновлениеОтображения» в палитре "
                            "стоят третьей и четвёртой строкой, а их коды — 70008 и 70009."),
    "PictureBox.PictureSize": Enum({"RealSize": 0, "Stretch": 1, "Proportionally": 2, "Tile": 3,
                                    "AutoSize": 4, "ByFontSize": 7}, default="RealSize",
                                   source="lab",
                                   missing=("AutoSizeIgnoreScale (not_in_palette)",
                                            "RealSizeIgnoreScale (not_in_palette)"),
                                   note="Те же шесть кодов, что у кнопки и панели."),
    # Рамка группы: ДЕВЯТЬ кодов вместо восьми. «Скруглённая» = 6 есть только у неё, и она же
    # умолчание; у прочих типов этого пункта в палитре нет вовсе.
    "GroupBox.Border": Enum({"WithoutBorder": 0, "Single": 1, "Embossed": 2, "Indented": 3,
                             "Underline": 4, "DoubleUnderline": 5, "Rounded": 6, "Overline": 7,
                             "Double": 200}, default="Rounded",
                            source="lab",
                            note="Коды те же, что у других типов (`PictureBox.Border`), плюс код 6 "
                                 "— «Скруглённая»."),
    # События частых типов.
    "Label.Event": Enum({"Click": 0}, source="lab"),
    "Button.Event": Enum({"Click": 0}, source="lab"),
    "Panel.Event": Enum({"OnCurrentPageChange": 0},
                        source="lab"),
    "PictureBox.Event": Enum({"Click": 0, "DragStart": 3, "DragCheck": 4, "DragEnd": 5,
                              "Drag": 6}, source="lab"),
    "ComboBox.Event": Enum({"StartListChoice": 1, "StartChoice": 2, "Clearing": 3, "Tuning": 4,
                            "Opening": 5, "ChoiceProcessing": 7, "TextEditEnd": 10,
                            "AutoCompleteText": 11, "OnChange": 2147483647},
                           source="lab"),
    "TextBox.Event": Enum({"StartListChoice": 1, "StartChoice": 2, "Clearing": 3, "Tuning": 4,
                           "Opening": 5, "ChoiceProcessing": 7, "TextEditEnd": 10,
                           "AutoCompleteText": 11, "OnChange": 2147483647},
                          source="lab",
                          missing=("Creating (not_in_palette)",),
                          note="Коды совпадают с кодами поля выбора (`ComboBox.Event`), но "
                               "перечисление у каждого типа своё."),
    "TableBox.Event": Enum({"Selection": 34, "OnActivateRow": 35, "OnActivateColumn": 36,
                            "OnActivateCell": 37, "BeforeAddRow": 40, "BeforeRowChange": 41,
                            "BeforeDeleteRow": 42, "OnStartEdit": 43, "BeforeEditEnd": 44,
                            "OnCheckChange": 45, "OnCurrentParentChange": 46, "OnRowOutput": 47,
                            "ValueChoice": 48, "OnEditEnd": 49, "NewObjectWriteProcessing": 50,
                            "AfterDeleteLine": 51, "ChoiceProcessing": 52, "OnDataGet": 53,
                            "DragStart": 900, "DragCheck": 901, "DragEnd": 902, "Drag": 903,
                            "BeforeParentChange": 10000, "BeforeSetDeletionMark": 10001,
                            "BeforeExpand": 10002, "BeforeCollapse": 10003},
                           source="lab",
                           note="Двадцать шесть событий в двух списках: обычные лежат в `2/4`, "
                                "четыре иерархических — в блоке источника данных."),
    "SpreadsheetDocumentField.Event": Enum(
        {"Selection": 0, "DetailProcessing": 1, "OnActivate": 2, "DragStart": 3, "DragCheck": 4,
         "DragEnd": 5, "Drag": 6, "OnChangeAreaContent": 7},
        source="lab",
        missing=("OnActivateArea (not_in_palette)",)),
# Свойства частых типов.
    "TextBox.DateFractions": Enum({"Date": 0, "Time": 1, "DateTime": 2}, default="Date",
                                  source="lab"),
    "TableBox.InitialTreeView": Enum(
        {"ExpandTopLevel": 1, "ExpandAllLevels": 2}, source="lab",
        missing=("NoExpand (ok)",), seen=((0, 3661),),
        note="Код значения «НеРаскрывать» (`NoExpand`) не установлен; вероятно, это 0, но это не "
             "проверялось."),
    "TableBox.NewRowShowCheck": Enum({"DontCheck": 0, "FilterMismatchMessage": 1},
                                     default="FilterMismatchMessage",
                                     source="lab"),
    "TableBox.Autonumeration": Enum({"Auto": 0, "DontUse": 1}, default="Auto",
                                    source="lab"),
    "TableBox.ViewFoldersAndItems": Enum({"Items": 0, "Folders": 1, "FoldersAndItems": 2},
                                         default="FoldersAndItems",
                                         source="lab"),
    "SpreadsheetDocumentField.ShowSelection": Enum(
        {"WhenActive": 0, "Always": 1}, default="WhenActive",
        source="lab"),
    "SpreadsheetDocumentField.Output": Enum(
        {"Auto": 0, "Enable": 1, "Disable": 2}, default="Auto",
        source="lab"),
    # Подэлементы.
    "TableBoxColumn.EditMode": Enum({"Directly": 0, "Enter": 1, "EnterOnInput": 2},
                                    default="Enter",
                                    source="lab"),
    "TableBoxColumn.Location": Enum({"NewColumn": 0, "OnNextRow": 1, "SameColumn": 2},
                                    default="NewColumn",
                                    source="lab"),
    "TableBoxColumn.HeaderHorizontalAlign": Enum(
        {"Left": 0, "Center": 1, "Right": 2}, default="Left",
        source="lab",
        missing=("Auto (not_in_palette)", "Justify (not_in_palette)")),
    "TableBoxColumn.HorizontalAlignInColumn": Enum(
        {"Left": 0, "Center": 1, "Right": 2, "Auto": 4}, default="Auto",
        source="lab",
        missing=("Justify (not_in_palette)",)),
    "TableBoxColumn.FooterHorizontalAlign": Enum(
        {"Left": 0, "Center": 1, "Right": 2}, default="Left",
        source="lab",
        missing=("Auto (not_in_palette)", "Justify (not_in_palette)")),
    "TableBoxColumn.SizeChange": Enum({"Change": 0, "DontChange": 1}, default="Change",
                                      source="lab"),
    "CommandBarButton.ButtonType": Enum({"Action": 0, "Popup": 1, "Separator": 2},
                                        default="Action",
                                        source="lab"),
    "CommandBarButton.Representation": Enum({"Auto": 0, "Text": 1, "Picture": 2,
                                             "PictureText": 3}, default="Auto",
                                            source="lab"),
    # Пятнадцать пунктов списка «Действие» палитры.
    "CommandBarButton.StandardAction": Enum(
        {"Dobavit": 80, "Skopirovat": 82, "Udalit": 83, "Izmenit": 84,
         "PeremestitVverh": 85, "PeremestitVniz": 86,
         "SortirovatPoVozrastaniyu": 88, "SortirovatPoUbyvaniyu": 89,
         "ZakonchitRedaktirovanie": 94, "NastroykaSpiska": 97, "VyvestiSpisok": 99,
         "Zakryt": 142, "SohranitZnacheniya": 143, "VosstanovitZnacheniya": 144,
         "Spravka": 300},
        source="exp",
        seen=((91, 1173), (53, 1171), (93, 1171), (90, 1155), (38, 924), (141, 830), (140, 758),
              (71, 638), (20, 602), (72, 592), (21, 543), (65, 512), (24, 465), (29, 465),
              (95, 419), (147, 402), (145, 385), (146, 375), (40, 178), (9, 169), (8, 155),
              (6, 153), (44, 130), (23, 124), (31, 119), (107, 100), (120, 89), (121, 89),
              (42, 80), (58, 77), (108, 67), (12, 43), (7, 42), (11, 42), (109, 36), (110, 36),
              (27, 23), (47, 23), (100, 15), (2, 12), (106, 11), (10, 10), (101, 9), (105, 8),
              (102, 7), (13, 6), (16, 6), (18, 6), (1, 5), (3, 4), (320, 3), (321, 3), (4, 2),
              (5, 2), (14, 2), (15, 2), (17, 2), (19, 2), (25, 1)),
        note="Стандартное действие кнопки командной панели. Имена значений — транслитерация "
             "русских подписей палитры: английских имён в справочнике нет. Названо пятнадцать "
             "кодов; остальные коды остаются числами."),
# Десять редких типов.
    "CalendarBox.SelectionMode": Enum({"Single": 0, "Multiple": 1, "Interval": 2},
                                      default="Single",
                                      source="lab"),
    "CalendarBox.Event": Enum({"OnActivateDate": 0, "Selection": 1, "OnPeriodOutput": 2,
                               "DragStart": 3, "DragCheck": 4, "DragEnd": 5, "Drag": 6,
                               "OnChange": 2147483647},
                              source="lab"),
    "GraphicalSchemaField.Event": Enum(
        {"Selection": 0, "OnActivate": 1},
        source="lab",
        note="Не путать с полем географической схемы: у него свои коды и своё перечисление "
             "(`GeographicalSchemaField.Event`)."),
    "HTMLDocumentField.Mode": Enum({"View": 1, "Edit": 2}, default="View", source="exp"),
    "HTMLDocumentField.Output": Enum({"Auto": 0, "Enable": 1, "Disable": 2}, default="Auto",
                                     source="lab"),
    "TextDocumentField.Output": Enum({"Auto": 0, "Enable": 1, "Disable": 2}, default="Auto",
                                     source="exp"),
    "HTMLDocumentField.Event": Enum(
        {"DocumentComplete": 0},
        source="lab",
        seen=((2, 26),),
        note="Единственное событие поля HTML-документа, которое платформа пишет именем. Остальные 62 события палитры "
             "(от `onhelp` до `onresize`) лежат в файле ЧИСЛАМИ 1…62 в порядке строк палитры; число остаётся числом, "
             "а их имена по палитре (и сами числа) принимает операция `set_event`."),
    "ListBox.Event": Enum({"OnCheckChange": 17, "Selection": 34, "OnActivateRow": 37},
                          source="lab",
                          note="Коды из того же ряда, что у табличного поля (34 Выбор, 37 "
                               "ПриАктивизации), но перечисление своё."),
    "ProgressBar.ShowStyle": Enum({"Broken": 0, "Smooth": 1, "BrokenTilt": 2}, default="Smooth",
                                  source="lab"),
    "ProgressBar.Orientation": Enum({"Vertical": 0, "Horizontal": 1, "Auto": 2}, default="Auto",
                                    source="lab"),
    "RadioButton.TitleLocation": Enum({"TitleLeft": 0, "TitleRight": 1}, default="TitleRight",
                                      source="lab"),
    "RadioButton.HorizontalAlign": Enum({"Left": 0, "Center": 1, "Right": 2}, default="Left",
                                        source="lab",
                                        missing=("Auto (not_in_palette)",
                                                 "Justify (not_in_palette)")),
    "RadioButton.VerticalAlign": Enum({"Top": 0, "Center": 1, "Bottom": 2}, default="Center",
                                      source="lab"),
    "RadioButton.Event": Enum({"OnChange": 2147483647},
                              source="lab"),
    "Splitter.Orientation": Enum({"Vertical": 0, "Horizontal": 1, "Auto": 2}, default="Auto",
                                 source="lab"),
    "TrackBar.MarkingAppearance": Enum({"DontShow": 0, "TopLeft": 1, "BottomRight": 2,
                                        "BothSides": 3}, default="BottomRight",
                                       source="lab"),
    "TrackBar.Orientation": Enum({"Vertical": 0, "Horizontal": 1, "Auto": 2}, default="Auto",
                                 source="lab"),
    "TrackBar.Event": Enum({"OnChange": 2147483647},
                           source="lab"),
}


@dataclass(frozen=True)
class Fork:
    """Выбор варианта по СКАЛЯРУ: значение в позиции `index` называет конкретный тип узла."""
    key: str
    names: dict
    index: int = 0
    kind: str = INT
    enum: str = None

    def __post_init__(self):
        if self.kind not in (INT, STR, GUID):
            # Видов три, и отбор не по вкусу: выбор варианта решает ЗНАЧЕНИЕ файла, а значит вид обязан
            # совпадать сам с собой на уровне 0.
            raise SchemaError(f"развилка по {self.key}: вид {self.kind} не заведён, "
                              f"дискриминатором бывает {INT}, {STR} или {GUID}")
        if self.enum is not None and self.kind != INT:
            raise SchemaError(f"развилка по {self.key}: перечисление бывает только у целого "
                              "дискриминатора — у строкового и у GUID значение и есть имя")


# Общий блок ПОЛЯ ВВОДА — выбор варианта по ВЕРСИИ блока: у версии 15 позиция 16 безымянна (`u16`), у 10,
# 13 и 16.
TEXTBOX_COMMON = "Content.TextBox.u2.u0.u0"
TEXTBOX_COMMON_FORK = "TextBoxCommon"
TEXTBOX_COMMON_15 = "TextBoxCommon.v15"

# Выбора варианта по скаляру.
FORKS = {
    "FormBlock": Fork("kind", {18: "FormBlock18", 16: "FormBlock16"}),
    "Layout": Fork("layout_version",
                   {16: "Layout16", 15: "Layout15", 13: "Layout13", 10: "Layout10"}),
    TEXTBOX_VALUE_BLOCK: Fork("u0", {code: f"{TEXTBOX_VALUE_BLOCK}.v{code}"
                                     for code in (0, 1, 2, 3, 4, 5)}),
    # Первая выбор варианта не по нулевой позиции (вторая — голова колонки, ниже).
    "Font": Fork("source", {code: f"Font.v{code}" for code in (0, 1, 2, 3)}, index=1,
                 enum="Font.Source"),
    "PanelPages": Fork("kind", {1: "PanelPages.v1"}),
    TABLE_BOX_SOURCE_BLOCK: Fork("u0", {code: f"{TABLE_BOX_SOURCE_BLOCK}.v{code}"
                                        for code in (1, 2, 3, 4, 5, 6, 7, 10, 11, 12)}),
    # Выбора варианта по СТРОКЕ, и обе по букве типа: у типизированного ЗНАЧЕНИЯ и у блока ТИПА в
    # описателе.
    "TypedValue": Fork("kind", {"N": "TypedValue.N", "S": "TypedValue.S", "B": "TypedValue.B",
                                "U": "TypedValue.U", "#": "TypedValue.Ref"}, kind=STR),
    "PatternType": Fork("kind", {"S": "PatternType.S", "N": "PatternType.N",
                                 "D": "PatternType.D", "B": "PatternType.B",
                                 "#": "PatternType.Ref"}, kind=STR),
    # Действие обработчика события: процедура модуля (3) против стандартного действия (6).
    "EventAction": Fork("mark", {3: "EventAction.v3", 6: "EventAction.v6"}),
    # Описание действия командной панели.
    "ActionSpec": Fork("mark", {1: "ActionSpec.v1", 3: "EventAction.v3",
                                6: "EventAction.v6", 4: "ActionSpec.v4"}),
    # Содержимое вложенного элемента колонки: варианты — ТЕ ЖЕ узлы, что у элементов формы, и
    # выбирает их первое число тела.
    "ColumnControl": Fork("content_kind", {9: "Content.TextBox", 1: "Content.CheckBox",
                                           2: "Content.ComboBox"}),
    # Колонка табличного поля по GUID своего вида.
    "TableBoxColumn": Fork("column_type", {**{guid: "Element.TableBoxColumn"
                                              for guid in WRAPPED_COLUMN_KINDS},
                                           VALUE_LIST_COLUMN: "TableBoxColumn.ValueList"},
                           kind=GUID),
    # Голова колонки по ВИДУ вложенного элемента — вторая выбор варианта не по первому скаляру: GUID
    # `control_type` стоит на позиции 38.
    COLUMN_HEAD_FORK: Fork("control_type", {ZERO_GUID: COLUMN_HEAD_BARE,
                                            **{ELEMENT_GUIDS[kind]: COLUMN_HEAD
                                               for kind in COLUMN_CONTROL_KINDS}},
                           index=38, kind=GUID),
    # Общий блок поля ввода по ВЕРСИИ.
    TEXTBOX_COMMON_FORK: Fork("u0", {10: TEXTBOX_COMMON, 13: TEXTBOX_COMMON, 16: TEXTBOX_COMMON,
                                     15: TEXTBOX_COMMON_15}),
}

def _is_variant_of(fork):
    """Предикат «это имя — вариант вот этой выбора варианта»."""
    names = set(fork.names.values())
    return lambda name: name in names


# Абстрактные типы и признак их конкретных вариантов.
ABSTRACT = {
    # Вариант элемента — тот, чей ТИП карта знает по GUID, и перечень их один на весь навык
    # (`guids.ELEMENT_GUIDS`).
    "Element": lambda name: name.startswith("Element.") and name[len("Element."):] in ELEMENT_GUIDS,
    **{name: _is_variant_of(fork) for name, fork in FORKS.items()},
}


def variants(type_name):
    """Конкретные типы абстрактного узла; пусто — тип конкретен."""
    fork = FORKS.get(type_name)
    if fork is not None:
        # `set` здесь несущий: у выбора варианта описания действия ДВА кода ведут в один и тот же
        # `EventAction`, и список с повтором дал бы `anyOf` из двух одинаковых веток и второй обход
        # того же узла у всякого, кто перебирает варианты.
        return sorted(set(fork.names.values()))
    matches = ABSTRACT.get(type_name)
    return sorted(name for name in MAP if matches(name)) if matches else []


def _fork_value(node, fork):
    """Скаляр выбора варианта — целое, строка или GUID в позиции `fork.index`; иначе None."""
    first = node.children[fork.index] if len(node.children) > fork.index else None
    if fork.kind == STR:
        return first.text if getattr(first, "kind", None) == "STR" else None
    if fork.kind == GUID:
        return first.text if getattr(first, "kind", None) == "GUID" else None
    if getattr(first, "kind", None) != "INT" or not int_text_survives(first.text):
        return None
    return int(first.text)


def pick(type_name, node):
    """Имя конкретного типа узла по ДЕРЕВУ."""
    if type_name == "Element":
        first = node.children[0] if node.children else None
        guid = getattr(first, "text", None) if getattr(first, "kind", None) == "GUID" else None
        name = element_type_name(guid) if guid else None
        return f"Element.{name}" if name else None
    fork = FORKS.get(type_name)
    if fork is not None:
        return fork.names.get(_fork_value(node, fork))
    return type_name


def pick_doc(type_name, doc):
    """Имя конкретного типа узла по JSON. **Имя типа обязано быть строкой, и это проверяется, а не
    подразумевается.** JSON правят руками, и `type` там бывает обёрткой GUID (`{"guid": …}`) — той
    самой, какой этот скаляр выглядит на уровне 0."""
    if isinstance(doc, dict) and set(doc) == {"raw"}:
        return None
    if type_name == "Element":
        name = doc.get("type")
        if name is not None and not isinstance(name, str):
            raise SchemaError(f"поле type должно быть ИМЕНЕМ типа элемента, а пришло {name!r}; "
                              f"карта знает {', '.join(sorted(ELEMENT_GUIDS))}")
        return f"Element.{name}" if name in ELEMENT_GUIDS else None
    fork = FORKS.get(type_name)
    if fork is not None:
        value = doc.get(fork.key)
        # Вид дискриминатора сверяется ЗДЕСЬ, а не подразумевается, и проверяются оба вида.
        if fork.kind == STR:
            if not isinstance(value, str):
                return None
        elif fork.kind == GUID:
            # GUID в документе — обёртка `{"guid": …}` (уровень 0 и поле вида `guid` пишут его
            # одинаково).
            if not (isinstance(value, dict) and set(value) == {"guid"}
                    and isinstance(value["guid"], str)):
                return None
            value = value["guid"]
        elif fork.enum and isinstance(value, str):
            # Дискриминатор с ИМЕНЕМ: поле выбора варианта объявлено перечислением, и в JSON лежит имя
            # кода, а не код.
            enum = ENUMS.get(fork.enum)
            value = enum.codes.get(value) if enum else None
        elif not isinstance(value, int) or isinstance(value, bool):
            return None
        return fork.names.get(value)
    return type_name


def slot_at(node_type, index):
    slot = node_type.fields.get(index)
    if slot is not None:
        return slot
    if node_type.repeat and index >= node_type.repeat.start:
        return node_type.repeat
    return None


def file_slot_at(node_type, index):
    """Слот по адресу ФАЙЛА."""
    if node_type.packed is not None:
        return node_type.packed.payload if index == 0 else None
    return slot_at(node_type, index)


def file_variants(type_name):
    """Варианты выбора варианта, в которые ведёт АДРЕС ФАЙЛА от якоря-родителя."""
    return [name for name in variants(type_name) if name not in COLUMN_ANCHOR]


def packed_anchor(content_type):
    """Якорь содержимого из упаковки: `Content.TextBox` → `Element.TextBox`."""
    if content_type.startswith("Content.") and \
            content_type[len("Content."):] in ELEMENT_GUIDS:
        return "Element." + content_type[len("Content."):]
    return None


def resolve(type_name, path):
    """Позиция без имени — `(узел, None)`, а не отказ: безымянная позиция законна и зовётся
    `u<индекс>`."""
    node = node_type(type_name)
    for i, index in enumerate(path):
        slot = file_slot_at(node, index)
        if i == len(path) - 1:
            return node, slot
        if slot is None:
            return node, None
        if isinstance(slot, F):
            raise SchemaError(f"{node.name}: позиция {index} — скаляр {slot.name}, "
                              "внутрь неё адреса нет")
        node = node_type(slot.type)
    return node, None


def resolve_any(type_name, path):
    """Слот по адресу С РАСКРЫТИЕМ выбора варианта: у абстрактного типа пробуются все варианты."""
    names = file_variants(type_name)
    if not names:
        node_type(type_name)
        names = [type_name]
    for name in names:
        if not path:
            continue
        node = node_type(name)
        slot = file_slot_at(node, path[0])
        if len(path) == 1:
            if slot is not None:
                return slot
            continue
        if isinstance(slot, (N, R)):
            found = resolve_any(slot.type, path[1:])
            if found is not None:
                return found
    return None


def slot_chain(type_name, path):
    """Слоты по ВСЕЙ дороге к адресу, с раскрытием выбора варианта."""
    names = file_variants(type_name) or [type_name]
    best = ()
    for name in names:
        node, out = node_type(name), []
        for i, index in enumerate(path):
            slot = file_slot_at(node, index)
            out.append(slot)
            if slot is None or i == len(path) - 1 or isinstance(slot, F):
                break
            if file_variants(slot.type):
                out.extend(slot_chain(slot.type, path[i + 1:]))
                break
            node = node_type(slot.type)
        if (len(out), out and out[-1] is not None) > (len(best), best and best[-1] is not None):
            best = tuple(out)
    return best


def is_placeholder(slot):
    """Позиция без имени: её либо нет в карте вовсе, либо стоит блок-заглушка `u<индекс>`. Правила,
    которым важно «карта тут молчит», обязаны считать их молчанием — иначе список записей."""
    name = getattr(slot, "name", None)
    return slot is None or (name is not None and name.startswith("u") and name[1:].isdigit())


# ── Счётные списки: раскладка узла, у которого позиции плавают ────────────────────────────────


def _items_in(node, type_name):
    """Сколько узлов в списке блока."""
    picked = pick(type_name, node) if node.children else None
    node_type = MAP.get(picked) if picked else None
    if node_type is None or node_type.repeat is None:
        return None
    return max(0, len(node.children) - node_type.repeat.start)


def _head_spots(node_type):
    """Голова узла: обычные поля карты по числовым адресам."""
    spots, named = {}, {}
    for index in range(node_type.runs.start):
        slot = node_type.fields.get(index)
        spots[index] = (f"u{index}", slot)
        if slot is not None:
            named[slot.name] = index
    return spots, named


def _fixed_spots(segment, at, lists_before, length, spots, named):
    for offset in range(length):
        slot = segment.fields.get(offset)
        spots[at + offset] = (run_key(lists_before, offset), slot)
        if slot is not None:
            named[slot.name] = at + offset


def _head_int(children, at):
    """Целое на позиции `at`, переживающее `int`."""
    item = children[at] if at < len(children) else None
    if item is None or isinstance(item, Node) or item.kind != "INT" \
            or not int_text_survives(item.text):
        return None
    return int(item.text)


_ORDINALS = ("нулевой", "первый", "второй", "третий", "четвёртый", "пятый", "шестой",
             "седьмой", "восьмой", "девятый", "десятый")


def _ordinal(number):
    return _ORDINALS[number] if number < len(_ORDINALS) else f"{number}-й"


def _shown(children, index):
    """Что стоит на позиции — словами, а не питоновским `repr`."""
    if index >= len(children):
        return "конец блока"
    item = children[index]
    if isinstance(item, Node):
        return f"блок из {len(item.children)} позиций"
    return f"{item.kind} {item.text}" if item.kind != "INT" else f"число {item.text}"


def plural(count, one, few, many):
    """Число со словом в нужном падеже: «1 запись», «2 записи», «5 записей»."""
    tail, tens = count % 10, count % 100
    if tens in range(11, 15) or tail == 0 or tail >= 5:
        return f"{count} {many}"
    return f"{count} {one}" if tail == 1 else f"{count} {few}"


def _no(why, reason):
    """Отказ раскладки с причиной: `None` наружу, фраза — в список `why`, если его просили."""
    if why is not None:
        why.append(reason)
    return None


def runs_failure(node_type, children):
    """Почему раскладка узла не сошлась — ОДНОЙ фразой."""
    why = []
    if read_runs(node_type, children, why) is not None:
        return None
    return why[0] if why else "строение не сошлось с картой"


def read_runs(node_type, children, why=None):
    """Раскладка по ДЕТЯМ узла: `(spots, lists)`; Значение при этом цело, а `validate` про сырой узел
    предупреждает. `why` — список, куда кладётся ПРИЧИНА отказа, когда её просят (`runs_failure`)."""
    runs = node_type.runs
    if len(children) < runs.start:
        return _no(why, f"голова узла — {runs.start} позиций, а детей всего {len(children)}")
    spots, named = _head_spots(node_type)
    lists = []
    at, seen = runs.start, 0
    for segment in runs.segments:
        if isinstance(segment, Fixed):
            length = segment.length if segment.length is not None else len(children) - at
            if length < 0 or at + length > len(children):
                return _no(why, f"хвост за списком {run_list_key(seen)} объявлен длиной {length}, "
                                f"а детей осталось {len(children) - at}")
            _fixed_spots(segment, at, seen, length, spots, named)
            at += length
            continue
        if isinstance(segment, Flagged):
            word = _head_int(children, at)
            names = segment.raised(word) if word is not None else None
            if names is None:
                # Либо на месте слова не целое, либо в слове бит, которого таблица не называет.
                return _no(why, f"слово флагов {segment.name} на позиции {at} — "
                                f"{_shown(children, at)}, и сколько блоков за ним, неизвестно")
            if at + 1 + len(names) > len(children) \
                    or any(not isinstance(children[at + 1 + k], Node)
                           for k in range(len(names))):
                return _no(why, f"слово флагов {segment.name} обещает "
                                f"{plural(len(names), 'блок', 'блока', 'блоков')}, а стоят за "
                                f"ним не блоки либо их меньше")
            lists.append((segment, at, tuple(range(at + 1, at + 1 + len(names)))))
            at, seen = at + 1 + len(names), seen + 1
            continue
        if isinstance(segment, Masked):
            word = _head_int(children, at)
            names = segment.raised(word) if word is not None else None
            if names is None:
                # Либо на месте слова не целое, либо в слове бит, которого таблица не называет.
                return _no(why, f"слово маски {segment.name} на позиции {at} — "
                                f"{_shown(children, at)}, и сколько значений за ним, неизвестно")
            first = at + 1 + len(segment.lead)
            if first + len(names) > len(children):
                return _no(why, f"слово маски {segment.name} обещает "
                                f"{plural(len(names), 'значение', 'значения', 'значений')}, а "
                                f"детей за ним {max(0, len(children) - first)}")
            for offset, slot in enumerate(segment.lead, start=1):
                index = at + offset
                child = children[index]
                if isinstance(slot, N) != isinstance(child, Node):
                    # Демоции у этой позиции нет: своего числового адреса у неё тоже нет, а ключ
                    # `L<n>+<k>` считается от отрезка, который тут как раз и не сошёлся.
                    return _no(why, f"перед значениями отрезка {segment.name} карта ждёт "
                                    f"{slot.name}, а на позиции {index} стоит "
                                    f"{_shown(children, index)}")
                spots[index] = (run_key(seen, offset), slot)
                named[slot.name] = index
            for offset, name in enumerate(names):
                index = first + offset
                item = children[index]
                if isinstance(item, Node) or not fits_scalar(masked_slot(segment, name), item):
                    return _no(why, f"в отрезке {segment.name} значение бита {name} — "
                                    f"{_shown(children, index)}, а карта объявила его видом "
                                    f"{segment.bits[name][1]}")
            lists.append((segment, at, tuple(range(first, first + len(names)))))
            at, seen = first + len(names), seen + 1
            continue
        if isinstance(segment, Gated):
            index = named.get(segment.by)
            value = _head_int(children, index) if index is not None else None
            if value is None:
                return _no(why, f"необязательному блоку {segment.name} не по чему решить, есть "
                                f"он или нет: поля {segment.by} в голове нет либо там не целое")
            count = segment.count(value)
            if count is None:
                # Значение вне обоих наборов — это не «блока нет», а «длины узла мы не знаем».
                return _no(why, f"{segment.by} = {value}: карта не знает, стоит ли при этом "
                                f"значении блок {segment.name} — с ним "
                                f"{', '.join(str(v) for v in segment.when)}, без него "
                                f"{', '.join(str(v) for v in segment.without)}")
            if count and (at >= len(children) or not isinstance(children[at], Node)):
                return _no(why, f"{segment.by} = {value} обещает блок {segment.name} на позиции "
                                f"{at}, а там {_shown(children, at)}")
            lists.append((segment, at, tuple(range(at, at + count))))
            at, seen = at + count, seen + 1
            continue
        if isinstance(segment, CountedPairs):
            count = _head_int(children, at)
            if count is None or count < 0 or at + 1 + 2 * count > len(children):
                return _no(why, f"счётчик списка пар {segment.name} на позиции {at} — "
                                f"{_shown(children, at)}, а на пару нужно ДВЕ позиции; детей "
                                f"{len(children)}")
            # Пара — «скаляр объявленного вида, потом блок».
            kind = _SCALAR_KIND_OF[segment.key_kind]
            bad = False
            for k in range(count):
                key, item = children[at + 1 + 2 * k], children[at + 2 + 2 * k]
                if isinstance(key, Node) or key.kind != kind or not isinstance(item, Node):
                    bad = True
                    break
                if kind == "INT" and not int_text_survives(key.text):
                    bad = True
                    break
            if bad:
                return _no(why, f"в списке пар {segment.name} член не по форме «ключ, блок»")
            lists.append((segment, at,
                          tuple(at + 2 + 2 * k for k in range(count))))
            at, seen = at + 1 + 2 * count, seen + 1
            continue
        if isinstance(segment, Counted):
            if at >= len(children):
                return _no(why, f"счётчик {_ordinal(seen + 1)} списка ({segment.name}) должен "
                                f"стоять на позиции {at}, а детей всего {len(children)}")
            counter = children[at]
            if isinstance(counter, Node) or counter.kind != "INT" \
                    or not int_text_survives(counter.text):
                return _no(why, f"на месте счётчика {_ordinal(seen + 1)} списка "
                                f"({segment.name}, позиция {at}) стоит "
                                f"{_shown(children, at)}, а счётчик — целое")
            count, first = int(counter.text), at + 1
        else:
            index = named.get(segment.items_of)
            holder = children[index] if index is not None and index < len(children) else None
            slot = spots[index][1] if index is not None else None
            if not isinstance(holder, Node) or not isinstance(slot, N):
                return _no(why, f"парному отрезку {segment.name} не у кого спросить длину: "
                                f"поля {segment.items_of} в голове нет либо там не блок")
            count = _items_in(holder, slot.type)
            if count is None:
                return _no(why, f"парному отрезку {segment.name} не у кого спросить длину: "
                                f"список {segment.items_of} не читается")
            if segment.one_unless is not None:
                flag_at = named.get(segment.one_unless)
                flag = _head_int(children, flag_at) if flag_at is not None else None
                if flag not in (0, 1):
                    return _no(why, f"длину парного отрезка {segment.name} задаёт и флаг {segment.one_unless}, а на его месте "
                                    + (_shown(children, flag_at) if flag_at is not None else "ничего нет"))
                if flag == 0:
                    count = min(count, 1)
            first = at
        if count < 0 or first + count > len(children):
            return _no(why, f"{_ordinal(seen + 1)} список ({segment.name}) обещает "
                            f"{plural(count, 'запись', 'записи', 'записей')} с позиции {first}, "
                            f"а детей всего {len(children)}")
        block = isinstance(segment, Counted)
        if any(isinstance(children[first + k], Node) != block for k in range(count)):
            # У счётного списка члены — блоки, у парного отрезка — скаляры.
            bad = next(k for k in range(count)
                       if isinstance(children[first + k], Node) != block)
            words = ("запись", "записи", "записей") if block else ("число", "числа", "чисел")
            return _no(why, f"{_ordinal(seen + 1)} список ({segment.name}) обещает "
                            f"{plural(count, *words)}, а на месте {bad + 1}-й стоит "
                            f"{_shown(children, first + bad)}")
        # `"INT"` здесь — вид скаляра ФАЙЛА (`tree.Scalar.kind`), а не вид поля карты (`INT`, он же
        # `"int"`): пишутся они похоже, а значат разное, и путаница читалась бы как «ни один член не
        # целый».
        if not block and any(children[first + k].kind != "INT"
                             or not int_text_survives(children[first + k].text)
                             for k in range(count)):
            # Члены парного отрезка записываются массивом БЕЗ ключей, и снять имя у одного из них (демоция)
            # нечем — своего адреса у него нет.
            return _no(why, f"в парном отрезке {segment.name} член не целый")
        lists.append((segment, at, tuple(range(first, first + count))))
        at, seen = first + count, seen + 1
    if at != len(children):
        return _no(why, f"отрезки кончились на позиции {at}, а детей {len(children)}")
    return spots, lists


def _tail_length(segment, doc, lists_before):
    """Длина открытого отрезка по ДОКУМЕНТУ: на единицу больше самого дальнего смещения."""
    best = -1
    prefix = run_key(lists_before, "")
    for key in doc:
        digits = key[len(prefix):]
        if key.startswith(prefix) and digits.isdigit() and str(int(digits)) == digits:
            best = max(best, int(digits))
    for offset, slot in segment.fields.items():
        if slot.name in doc:
            best = max(best, offset)
    return best + 1


def _require_closed(segment, doc, at, lists_before, length):
    """У отрезка ОБЪЯВЛЕННОЙ длины в документе обязана быть каждая позиция. Иначе отказ. Отказ
    приезжает из `doc_runs`, а не из двух мест порознь: и запись, и проверка зовут её."""
    missing = []
    for offset in range(length):
        slot = segment.fields.get(offset)
        key = slot.name if slot is not None else run_key(lists_before, offset)
        if key not in doc:
            missing.append(key)
    if missing:
        raise SchemaError(
            f"нет полей {', '.join(missing)}: у отрезка за списком "
            f"{run_list_key(lists_before)} длина "
            f"объявлена картой ({length}) и подтверждена корпусом, а не выведена из документа — "
            "значит позиция не «короткий хвост», а пропажа, и соседи при записи уехали бы на "
            "чужие места")


def doc_runs(node_type, doc):
    """Та же раскладка по ДОКУМЕНТУ. Отказ со словами: собрать нечем, а молчать нельзя."""
    runs = node_type.runs
    spots, named = _head_spots(node_type)
    lists = []
    at, seen = runs.start, 0
    for segment in runs.segments:
        if isinstance(segment, Fixed):
            length = segment.length if segment.length is not None \
                else _tail_length(segment, doc, seen)
            _fixed_spots(segment, at, seen, length, spots, named)
            if segment.length is not None:
                _require_closed(segment, doc, at, seen, length)
            at += length
            continue
        if isinstance(segment, Flagged):
            picked = doc.get(segment.name)
            if not isinstance(picked, dict):
                raise SchemaError(f"{segment.name} — отрезок по битам {run_list_key(seen + 1)}, "
                                  f"и пишут его объектом ({', '.join(segment.bits)}; лишнее "
                                  f"место занимать не надо), а пришло {picked!r}")
            unknown = [key for key in picked if key not in segment.bits]
            if unknown:
                raise SchemaError(f"{segment.name}: битов " + ", ".join(sorted(unknown))
                                  + " карта не знает; имена здесь называет только она, а слово "
                                    "флагов собирается из присутствующих ключей")
            names = [name for name in segment.bits if name in picked]
            lists.append((segment, at, tuple(range(at + 1, at + 1 + len(names)))))
            at, seen = at + 1 + len(names), seen + 1
            continue
        if isinstance(segment, Masked):
            picked = doc.get(segment.name)
            if not isinstance(picked, dict):
                # Перечень называет и ОБЯЗАТЕЛЬНЫЕ ключи: человек соберёт объект по этому списку, и
                # умолчи мы про бит без значения — он получил бы второй отказ на том же месте.
                required = "".join(f"; {name} — булево поле, и оно обязательно"
                                   for name in (segment.flags or ()))
                raise SchemaError(f"{segment.name} — отрезок по маске {run_list_key(seen + 1)}, "
                                  f"и пишут его объектом ({', '.join(segment.bits)}; лишнее "
                                  f"место занимать не надо{required}), а пришло {picked!r}")
            unknown = [key for key in picked
                       if key not in segment.bits and key not in (segment.flags or ())]
            if unknown:
                raise SchemaError(f"{segment.name}: битов " + ", ".join(sorted(unknown))
                                  + " карта не знает; имена здесь называет только она, а слово "
                                    "маски собирается из присутствующих ключей")
            for flag in (segment.flags or ()):
                # Бит без значения записывается ВСЕГДА и только булевым: из набора ключей он не выводится, а
                # «ключ есть, значит поднят» сделало бы `false` ловушкой — человек написал бы «нет»,
                # а в файл уехало бы «да».
                if flag not in picked:
                    raise SchemaError(f"{segment.name}: нет флага {flag} — значения у этого бита "
                                      "нет, и из набора ключей он не выводится; он записывается булевым "
                                      "полем всегда, и пропущенный уехал бы нулём")
                if not isinstance(picked[flag], bool):
                    raise SchemaError(f"{segment.name}: флаг {flag} булев, а пришло "
                                      f"{picked[flag]!r}")
            names = [name for name in segment.bits if name in picked]
            for offset, slot in enumerate(segment.lead, start=1):
                spots[at + offset] = (run_key(seen, offset), slot)
                named[slot.name] = at + offset
            first = at + 1 + len(segment.lead)
            lists.append((segment, at, tuple(range(first, first + len(names)))))
            at, seen = first + len(names), seen + 1
            continue
        if isinstance(segment, Gated):
            value = _doc_gate(segment, doc, spots, named)
            block = doc.get(segment.name)
            if value is None:
                raise SchemaError(
                    f"{segment.name}: есть этот блок в файле или нет, решает поле {segment.by}, "
                    f"а прочесть его нечем — {doc.get(segment.by)!r}")
            count = segment.count(value)
            if count is None:
                raise SchemaError(
                    f"{segment.by} = {value}: карта не знает, стоит ли при этом значении блок "
                    f"{segment.name}; с ним {', '.join(str(v) for v in segment.when)}, без него "
                    f"{', '.join(str(v) for v in segment.without)}")
            if count and not isinstance(block, dict):
                raise SchemaError(
                    f"{segment.by} = {value}, и при этом значении в файле стоит блок "
                    f"{segment.name}, а в документе его нет (пришло {block!r}). Платформа такой "
                    f"файл отвергает целиком; либо добавьте {segment.name}, либо поставьте "
                    f"{segment.by} из набора {', '.join(str(v) for v in segment.without)}")
            if not count and block is not None:
                raise SchemaError(
                    f"{segment.by} = {value}, и при этом значении блока {segment.name} в файле "
                    f"не бывает, а в документе он есть. Либо уберите его, либо поставьте "
                    f"{segment.by} из набора {', '.join(str(v) for v in segment.when)}")
            lists.append((segment, at, tuple(range(at, at + count))))
            at, seen = at + count, seen + 1
            continue
        items = doc.get(segment.name)
        if not isinstance(items, list):
            raise SchemaError(f"{segment.name} — список {run_list_key(seen + 1)}, и пишут его "
                              f"массивом, а пришло {items!r}")
        if isinstance(segment, CountedPairs):
            # Ключ у члена свой, и позиция у него своя — перед узлом.
            lists.append((segment, at,
                          tuple(at + 2 + 2 * k for k in range(len(items)))))
            at, seen = at + 1 + 2 * len(items), seen + 1
            continue
        if isinstance(segment, Along):
            count = _doc_items_in(segment, doc, spots, named)
            if count is None:
                raise SchemaError(f"{segment.name}: длину этого отрезка задаёт список внутри "
                                  f"{segment.items_of}, а прочесть его там нечем")
            single = False
            if segment.one_unless is not None:
                flag = doc.get(segment.one_unless)
                if not isinstance(flag, bool):
                    raise SchemaError(f"{segment.name}: длину этого отрезка задаёт и флаг {segment.one_unless} (true или false), "
                                      f"а пришло {flag!r}")
                single = not flag
                if single:
                    count = min(count, 1)
            if count != len(items):
                if single:
                    raise SchemaError(f"{segment.name}: в списке {len(items)}, а при {segment.one_unless} = false "
                                      "(«Распределять по страницам» снято) отрезок — одно число на весь родитель, сколько бы ни было "
                                      f"узлов в {segment.items_of}")
                raise SchemaError(f"{segment.name}: в списке {len(items)}, а в {segment.items_of} "
                                  f"узлов {count} — отрезок идёт по одному на каждый, и своего "
                                  "счётчика у него в файле нет")
        first = at + 1 if isinstance(segment, Counted) else at
        lists.append((segment, at, tuple(range(first, first + len(items)))))
        at, seen = first + len(items), seen + 1
    return spots, lists


def counter_index(segment, start):
    """Позиция счётчика отрезка."""
    return start if isinstance(segment, (Counted, CountedPairs)) else None


def pair_key_index(node_index):
    """Позиция КЛЮЧА пары по позиции её узла: ключ лежит ровно перед узлом."""
    return node_index - 1


def _doc_gate(segment, doc, spots, named):
    """Значение флага строения по ДОКУМЕНТУ — числом."""
    index = named.get(segment.by)
    slot = spots[index][1] if index is not None else None
    if slot is None:
        return None
    value = doc.get(slot.name)
    if isinstance(value, str) and slot.kind == ENUM:
        enum = ENUMS.get(slot.enum)
        value = enum.codes.get(value) if enum else None
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    return value


def _doc_items_in(segment, doc, spots, named):
    """Сколько узлов в списке соседнего поля ДОКУМЕНТА."""
    holder = doc.get(segment.items_of)
    slot = spots[named[segment.items_of]][1] if segment.items_of in named else None
    if not isinstance(holder, dict) or not isinstance(slot, N):
        return None
    picked = pick_doc(slot.type, holder)
    node = MAP.get(picked) if picked else None
    repeat = node.repeat if node is not None else None
    inner = holder.get(repeat.name) if repeat is not None else None
    return len(inner) if isinstance(inner, list) else None


def node_slots(node):
    """Все слоты узла с адресами, в порядке позиций: поля, повтор, отрезки раскладки. Разные языки
    адреса в одной таблице читались бы как ошибка, поэтому язык здесь один и он же стоит в отказах
    кодека."""
    out = [(str(index), node.fields[index]) for index in sorted(node.fields)]
    if node.repeat is not None:
        out.append((f"{node.repeat.start}…", node.repeat))
    if node.runs is not None:
        seen = 0
        for segment in node.runs.segments:
            if isinstance(segment, Fixed):
                out += [(run_key(seen, offset), segment.fields[offset])
                        for offset in sorted(segment.fields)]
                continue
            # Слоты ПЕРЕД значениями отрезка по маске — такие же слоты карты, как всякий другой: их
            # печатает `FORMAT.md`, по ним обход доходит до вложенных узлов, и пропусти их этот
            # перечень — блок ссылки шрифта уехал бы в «прочие узлы» молча.
            out += [(run_key(seen, offset), slot)
                    for offset, slot in enumerate(getattr(segment, "lead", ()), start=1)]
            seen += 1
            out.append((run_list_key(seen), segment))
    return out


def in_runs(type_name, path):
    """Уходит ли числовой адрес в плавающую часть узла."""
    names = file_variants(type_name) or [type_name]
    for name in names:
        node = MAP.get(name)
        if node is None or not path:
            continue
        if node.runs is not None and path[0] >= node.runs.start:
            return True
        slot = file_slot_at(node, path[0])
        if len(path) > 1 and isinstance(slot, (N, R)) and in_runs(slot.type, path[1:]):
            return True
    return False


def _doc_names(node):
    """ВСЕ имена, под которыми узел выкладывает свои значения в JSON."""
    names = {slot.name for slot in node.fields.values()}
    if node.repeat is not None:
        names.add(node.repeat.name)
    for segment in (node.runs.segments if node.runs is not None else ()):
        if isinstance(segment, Fixed):
            names |= {slot.name for slot in segment.fields.values()}
        else:
            names.add(segment.name)
            names |= {slot.name for slot in getattr(segment, "lead", ())}
    return names


def _check_pair_keys():
    """Имя ключа списка пар обязано быть СВОБОДНЫМ у типа члена."""
    for node in MAP.values():
        if node.runs is None:
            continue
        for segment in node.runs.segments:
            if not isinstance(segment, CountedPairs):
                continue
            member = MAP.get(segment.type)
            if member is None:
                raise SchemaError(f"{node.name}: список пар {segment.name} ссылается на тип "
                                  f"{segment.type}, которого в карте нет")
            names = _doc_names(member)
            if segment.key in names:
                # «Занято» — не обязательно полем: имя бывает и у повтора, и у отрезка раскладки, и
                # в JSON все трое кладут значение под своим именем.
                raise SchemaError(f"{node.name}: ключ {segment.key!r} списка пар "
                                  f"{segment.name} занят у узла {segment.type} — этим именем он "
                                  "уже выкладывает значение в JSON (поле, повтор или отрезок "
                                  "раскладки), и ключ затёр бы его молча")


def _check_fork_enums():
    """У выбора варианта с ИМЕНАМИ перечисление обязано называть каждый её код."""
    for type_name, fork in FORKS.items():
        if not fork.enum:
            continue
        enum = ENUMS.get(fork.enum)
        if enum is None:
            raise SchemaError(f"развилка {type_name}: перечисления {fork.enum!r} в карте нет")
        missing = sorted(code for code in fork.names if code not in enum.codes.values())
        if missing:
            raise SchemaError(f"развилка {type_name}: у кодов {missing} нет имени в "
                              f"перечислении {fork.enum} — разбор оставил бы их числом, и поле "
                              "развилки ездило бы то именем, то числом")


def _note(type_name, text):
    """Заметка узлу, которого карта не объявляла, а собрала по дороге. Звать эту функцию можно только
    тогда, когда карта уже собрана."""
    node = MAP[type_name]
    if node.note is not None:
        raise SchemaError(f"узел {type_name}: заметка уже стоит, а вторая затёрла бы первую")
    MAP[type_name] = dataclasses.replace(node, note=text)


# ── Общий блок свойств: что платформа не показывает ───────────────────────────────────────────
_COMMON_BLOCK_NOTE = (
    "Общий блок свойств элемента, одинаковый у семнадцати типов. Длина блока зависит от версии "
    "(позиция 0): 10 — 13 позиций, 13 — 15, 15 — 17, 16 — 18. Версия блока у элементов формы та "
    "же, что у формы; исключение — вложенные элементы колонок. Позиция 16 бывает у версий 15 и 16, "
    "позиция 17 — только у 16; платформа их хранит, но в палитре не показывает. Редактор не "
    "заводит в форме элементы другой версии (`add_element` и `set_column_control` отказывают), "
    "`validate` уровня 2 предупреждает о смеси версий, а `frm_json.py design` сравнивает форму с "
    "соседними формами.")
_COMMON_BLOCKS = {}
for _anchor, _base, *_rest in _COMMON_COLOR_GAPS:
    _name = f"Content.{_anchor[len('Element.'):]}" \
        + "".join(f".u{_step}" for _step in _base.split("/")[1:])
    _COMMON_BLOCKS[_anchor] = _name
    _note(_name, _COMMON_BLOCK_NOTE)
# Позиция 16 общего блока ПОЛЯ ВВОДА — `view`. Имя и перечисление — только у поля ввода.
ENUMS["TextBox.View"] = Enum(
    {"As82": 1, "As83": 0, "As83Alt": 2}, source="exp",
    note="Вид поля ввода: 1 — «как в 8.2» (прямые углы, светлые кнопки «…»/«×», чёрные значки), 0 "
         "и 2 — «как в 8.3» (скруглённые углы, бежевые кнопки).")
_place("Element.TextBox", "2/2/0/0/16", F(
    "view", ENUM, enum="TextBox.View", source="exp",
    note="Вид поля ввода: «как в 8.2» (`As82`) или «как в 8.3» (`As83`, `As83Alt`). В палитре "
         "этого свойства нет, при пересохранении платформа его сохраняет. Позиция есть у версий "
         "общего блока 15 и 16, но имя у неё только при версии 16. Вид — свойство всей формы: его "
         "выравнивает операция `set_view`, а `set_property` это поле не пишет."))
# Свойства поля ввода: у безымянной позиции 43 строки в таблице нет (карта её не называет).
_note("Content.TextBox.u2.u0", (
    "Свойства поля ввода. Позиция 43 имени не имеет: платформа вычисляет её при сохранении из вида "
    "поля (`view`) и цвета рамки, и редактор пишет её по тому же правилу."))
# Адрес общего блока у записи элемента — позициями файла, по типу.
COMMON_BLOCK_ADDRESSES = {_anchor: tuple(int(_step) for _step in _base.split("/"))
                          for _anchor, _base, *_rest in _COMMON_COLOR_GAPS}


# ── Голова колонки: два строения по виду вложенного элемента ──────────────────────────────────
_HEAD_MIRROR = 45
_BARE_MIRROR = 44
_head_fields = MAP[COLUMN_HEAD].fields
if _head_fields[_HEAD_MIRROR].name != "width_mirror" or _BARE_MIRROR in _head_fields:
    raise SchemaError(f"{COLUMN_HEAD}: голова колонки ждёт зеркало ширины на позиции "
                      f"{_HEAD_MIRROR} и безымянную {_BARE_MIRROR}, а карта держит "
                      f"{_head_fields.get(_HEAD_MIRROR)!r} и {_head_fields.get(_BARE_MIRROR)!r}")
_add(NodeType(COLUMN_HEAD_BARE, {
    **{index: slot for index, slot in _head_fields.items() if index != _HEAD_MIRROR},
    _BARE_MIRROR: F(
        "width_mirror", INT_EXP, source="round", mirror_of="1/1/1/4",
        note="Второй адрес ширины у колонки без вложенного элемента; платформа берёт ширину из "
             "этого адреса. `set_property` пишет ширину в оба адреса, а у формы с DPI не 96 "
             "отказывает, как и у колонки с элементом."),
}, note=(
    "Голова колонки без вложенного элемента (пустой GUID `control_type`). Поля те же, что у головы "
    "с элементом, но всё после позиции 39 стоит на одну позицию ближе; зеркало ширины — на позиции "
    "44. На позиции 39 в файлах стоит число 0, поэтому она теряет имя `control`. Блок элемента при "
    "пустом GUID бывает только после ручной правки; `validate` о нём предупреждает.")))
_add(NodeType(COLUMN_HEAD_FORK, note=(
    "Голова колонки табличного поля. Вариант выбирается по GUID вида вложенного элемента "
    "(`control_type`, позиция 38): голова с элементом или без него. Голова с незнакомым GUID "
    "остаётся неразобранной.")))
MAP["Element.TableBoxColumn.u1.u1"].fields[1] = N(
    "u1", COLUMN_HEAD_FORK, source="corpus",
    note="Голова колонки — вариант выбирается по виду вложенного элемента (`TableBoxColumnHead`).")


# ── Общий блок поля ввода: два узла по версии блока ───────────────────────────────────────────
_textbox_common = MAP[TEXTBOX_COMMON].fields
if TEXTBOX_COMMON != _COMMON_BLOCKS["Element.TextBox"] or _textbox_common[16].name != "view" \
        or 17 in _textbox_common:
    raise SchemaError(f"{TEXTBOX_COMMON}: развилка по версии ждёт общий блок поля ввода с `view` "
                      "на позиции 16 и без имени на 17, а карта держит другое")
_add(NodeType(TEXTBOX_COMMON_15, {index: slot for index, slot in _textbox_common.items()
                                  if index != 16}, note=(
    "Общий блок поля ввода версии 15. Он такой же, как у версий 10, 13 и 16 "
    "(`Content.TextBox.u2.u0.u0`), но позиция 16 здесь имени не имеет (`u16`): вид поля у версии "
    "15 не проверялся. Для формы версии 15 `set_view` отказывает.")))
_add(NodeType(TEXTBOX_COMMON_FORK, note=(
    "Общий блок свойств поля ввода. Вариант выбирается по версии блока: у версии 15 позиция 16 "
    "имени не имеет, у версий 10, 13 и 16 узел общий. Блок незнакомой версии остаётся "
    "неразобранным.")))
MAP["Content.TextBox.u2.u0"].fields[0] = N(
    "u0", TEXTBOX_COMMON_FORK, source="corpus",
    note="Общий блок свойств поля ввода; вариант выбирается по версии блока.")


_check_pair_keys()
_check_fork_enums()


# Полные источники и примечания приезжают из отдельного модуля, если он лежит рядом (в prod-копии его нет).
try:
    from . import schema_sources as _sources
except ImportError:
    pass
else:
    _sources.install(sys.modules[__name__])
