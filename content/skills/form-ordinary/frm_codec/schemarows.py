"""Поле географической схемы, поле графической схемы и поле PDF-документа: строки палитры, которые лежат вне общего блока свойств.

Эти строки не названы в карте: значения лежат во вложенных списках записи элемента, и положение значения в таком списке зависит от вида. Модуль называет
строки по их адресам и пишет их через `set_property`.

| Вид | Где лежат строки |
|---|---|
| `GraphicalSchemaField` | в содержимом: `content/u5` — Вывод; `content/u2/0/1/0/<n>` — сетка (запись из позиций: версия 1, цвет фона, ИспользоватьСетку, горизонтальный шаг, вертикальный шаг, режим) |
| `GeographicalSchemaField` | в записи элемента `u3`: `u3/u4` — Вывод; `u3/u2/0/<n>` — счётчик номеров слоя, проекция и смещения; `u3/u2/1` — область данных слоёв и сами слои; `u3/u2/2/0` и `u3/u2/3/0` — Легенда и Заголовок; `u3/u2/6` и `u3/u2/7` — ПоддержкаМасштаба и Масштаб; `u3/u2/8…11` — четыре границы области |
| `PDFDocumentField` | в файле формы строк «Рамка», «ЦветРамки» и «Вывод» нет: платформа их в файл не пишет |

Адрес — путь по узлу элемента в документе уровня 1: имя поля и номера внутри вложенных списков. Каждая позиция названа по записи платформы: значение в ней меняла
ровно эта строка палитры.

**Шесть строк пишутся в файл, но платформа их обратно не читает** (`Row.unkept`): ПоддержкаМасштаба, Масштаб и четыре границы области. После повторного открытия формы палитра
показывает «Все данные», масштаб 1 и границы 0.0', а сохранение формы после такого открытия стирает значения из файла. Они пишутся только с `unverified`.

**Границы области** лежат в `u3/u2/8…11` (южная, северная, западная, восточная), диапазон значения — область данных слоёв (`u3/u2/1/0…3`: первая координата точек слоя
от и до, вторая от и до). Слоя нет — область пуста, диалог платформы принимает только 0 и значение не вводится. Платформа при вводе южной и северной границ ставит
СмещениеДолготы равным их полусумме (`u3/u2/0/3`); запись границ делает то же.

**Слой** (`Row.via`) строкой не пишется: запись слоя тянет за собой счётчик номеров (`u3/u2/0/0`), область данных и число слоёв — их переносит операция `copy_layer` (`edit.layer`).

**Поле PDF-документа** (`Row.unwritten`): три строки платформа в файл не пишет — значения не переживают сохранения, и это видно по двум сеансам. `set_property` отказывает словами.
"""
import copy
import dataclasses
from decimal import Decimal

from . import json0
from .edit.base import EditError, find_element

GRAPH = "GraphicalSchemaField"
GEO = "GeographicalSchemaField"
PDF = "PDFDocumentField"
KINDS = (GRAPH, GEO, PDF)
NAMES_OF_KIND = {GRAPH: "поля графической схемы", GEO: "поля географической схемы", PDF: "поля PDF-документа"}

OUTPUT = {"Авто": 0, "Разрешить": 1, "Запретить": 2}
GRID_MODE = {"Не рисовать сетку": 0, "Рисовать точки": 1, "Рисовать шахматную сетку": 2, "Рисовать линии": 3}
SCALE_KEEPING = {"Все данные": 0, "Задается масштабом": 1, "Заданная область": 2}
LATITUDE = 90
LONGITUDE = 180

# Проекции по кодам: строка палитры, имя значения системного перечисления (справочник `1c8-doc`, `ТипПроекцииГеографическойСхемы`), английское имя.
PROJECTIONS = (
    ("Цилиндрическая проекция Миллера", "ЦилиндрическаяПроекцияМиллера", "CylindricalMillerProjection"),
    ("Цилиндрическая проекция равных областей Ламберта", "ЦилиндрическаяПроекцияРавныхОбластейЛамберта", "CylindricalLambertEqualAreaProjection"),
    ("Цилиндрическая стереографическая проекция Галла", "ЦилиндрическаяСтереографическаяПроекцияГалла", "CylindricalGallStereographicProjection"),
    ("Цилиндрическая равноудаленная проекция", "ЦилиндрическаяРавноудаленнаяПроекция", "CylindricalEquidistantProjection"),
    ("Псевдоцилиндрическая синусоидальная проекция", "ПсевдоцилиндрическаяСинусоидальнаяПроекция", "PseudoCylindricalSinusoidalProjection"),
    ("Псевдоцилиндрическая проекция Молвейда", "ПсевдоцилиндрическаяПроекцияМолвейда", "PseudoCylindricalMollweideProjection"),
    ("Псевдоцилиндрическая проекция Робинсона", "ПсевдоцилиндрическаяПроекцияРобинсона", "PseudoCylindricalRobinsonProjection"),
    ("Псевдоцилиндрическая проекция Экерта 1", "ПсевдоцилиндрическаяПроекцияЭкерта1", "PseudoCylindricalEckert1Projection"),
    ("Псевдоцилиндрическая проекция Экерта 2", "ПсевдоцилиндрическаяПроекцияЭкерта2", "PseudoCylindricalEckert2Projection"),
    ("Псевдоцилиндрическая проекция Экерта 3", "ПсевдоцилиндрическаяПроекцияЭкерта3", "PseudoCylindricalEckert3Projection"),
    ("Псевдоцилиндрическая проекция Экерта 4", "ПсевдоцилиндрическаяПроекцияЭкерта4", "PseudoCylindricalEckert4Projection"),
    ("Псевдоцилиндрическая проекция Экерта 5", "ПсевдоцилиндрическаяПроекцияЭкерта5", "PseudoCylindricalEckert5Projection"),
    ("Псевдоцилиндрическая проекция Экерта 6", "ПсевдоцилиндрическаяПроекцияЭкерта6", "PseudoCylindricalEckert6Projection"),
    ("Псевдоцилиндрическая проекция несимметричных равных областей Хатано", "ПсевдоцилиндрическаяПроекцияНесимметричныхРавныхОбластейХатано",
     "PseudoCylindricalHatanoAsymetricalEqualAreaProjection"),
    ("Псевдоцилиндрическая проекция Локсимутала", "ПсевдоцилиндрическаяПроекцияЛоксимутала", "PseudoCylindricalLoximutalProjection"),
    ("Псевдоцилиндрическая плоско-полярная параболическая проекция МакБрайда-Томаса", "ПсевдоцилиндрическаяПлоскоПолярнаяПараболическаяПроекцияМакБрайдаТомаса",
     "PseudoCylindricalMcBrydeThomasFlatPolarParabolicProjection"),
    ("Псевдоцилиндрическая плоско-полярная проекция четвертого порядка МакБрайда-Томаса", "ПсевдоцилиндрическаяПлоскоПолярнаяПроекцияЧетвертогоПорядкаМакБрайдаТомаса",
     "PseudoCylindricalMcBrydeThomasFlatPolarQuarticProjection"),
    ("Псевдоцилиндрическая плоско-полярная синусоидальная проекция МакБрайда-Томаса", "ПсевдоцилиндрическаяПлоскоПолярнаяСинусоидальнаяПроекцияМакБрайдаТомаса",
     "PseudoCylindricalMcBrydeThomasFlatPolarSinusoidalProjection"),
    ("Псевдоцилиндрическая проекция Путнина P2", "ПсевдоцилиндрическаяПроекцияПутнинаP2", "PseudoCylindricalPutninP2Projection"),
    ("Псевдоцилиндрическая проекция Путнина P5", "ПсевдоцилиндрическаяПроекцияПутнинаP5", "PseudoCylindricalPutninP5Projection"),
    ("Псевдоцилиндрическая проекция Винкеля 1", "ПсевдоцилиндрическаяПроекцияВинкеля1", "PseudoCylindricalWinkel1Projection"),
    ("Псевдоцилиндрическая нормальная проекция Боггса", "ПсевдоцилиндрическаяНормальнаяПроекцияБоггса", "PseudoCylindricalBoggsEumorphicProjection"),
    ("Азимутальная проекция Хамера", "АзимутальнаяПроекцияХамера", "AzimuthalHammerProjection"),
    ("Азимутальная проекция Вагнера 7", "АзимутальнаяПроекцияВагнера7", "AzimuthalWagner7Projection"),
    ("Азимутальная проекция Аитофа", "АзимутальнаяПроекцияАитофа", "AzimuthalAitoffProjection"),
    ("Азимутальная проекция Винкеля Трипеля", "АзимутальнаяПроекцияВинкеляТрипеля", "AzimuthalWinkelTripelProjection"),
    ("Азимутальная равноудаленная проекция", "АзимутальнаяРавноудаленнаяПроекция", "AzimuthalEquidistantProjection"),
    ("Азимутальная проекция равных площадей Ламберта", "АзимутальнаяПроекцияРавныхПлощадейЛамберта", "AzimuthalLambertEqualAreaProjection"),
    ("Прочая эпициклоидальная проекция Августа", "ПрочаяЭпициклоидальнаяПроекцияАвгуста", "MiscellaneousAugustEpicycloidalProjection"),
    ("Прочая шаровая проекция Бекона", "ПрочаяШароваяПроекцияБекона", "MiscellaneousBaconGlobularProjection"),
    ("Прочая шаровая проекция Николоси", "ПрочаяШароваяПроекцияНиколоси", "MiscellaneousNicolosiGlobularProjection"),
    ("Прочая сотовая шаровая 1 проекция", "ПрочаяСотоваяШаровая1Проекция", "MiscellaneousApianGlobular1Projection"),
    ("Прочая овальная проекция Ортелиуса", "ПрочаяОвальнаяПроекцияОртелиуса", "MiscellaneousOrteliusOvalProjection"),
    ("Прочая проекция Ван Дер Гринтена 1", "ПрочаяПроекцияВанДерГринтена1", "MiscellaneousVanDerGrinten1Projection"),
    ("Прочая проекция Ван Дер Гринтена 2", "ПрочаяПроекцияВанДерГринтена2", "MiscellaneousVanDerGrinten2Projection"),
    ("Прочая проекция Ван Дер Гринтена 3", "ПрочаяПроекцияВанДерГринтена3", "MiscellaneousVanDerGrinten3Projection"),
    ("Коническая проекция равных площадей Ламберта", "КоническаяПроекцияРавныхПлощадейЛамберта", "ConicLambertEqualAreaProjection"),
)
PROJECTION_CODES = {}
for _code, _names in enumerate(PROJECTIONS):
    for _name in _names:
        PROJECTION_CODES[_name] = _code

UNKEPT_WORDS = ("платформа записывает значение в файл, но при повторном открытии формы не читает его: палитра показывает значение по умолчанию (у "
                "строки ПоддержкаМасштаба «Все данные», у строки Масштаб 1, у границ области 0.0'), и сохранение формы после такого открытия стирает значение из файла")
NO_LAYER_WORDS = ("слоя в поле нет, и область данных пуста: диапазон допустимых значений границы платформа берёт из слоёв, при их отсутствии он 0.0'–0.0', и ни одно "
                  "значение, кроме нуля, диалог не принимает; слой — операция `copy_layer`")
PDF_WORDS = ("в файл не пишется: два захода без следа — значения не переживают сохранения (запись элемента при любых значениях равна записи при значениях по умолчанию, "
             "кроме привязок границ, а после повторного открытия палитра показывает умолчание)")
PDF_PROOF = ("два захода: значения не переживают сохранения — {what} в палитре выставлены, форма сохранена, и запись элемента равна записи по умолчанию (кроме привязок границ); "
             "значения выставлены заново, форма сохранена, закрыта и открыта — палитра показала умолчание (Одинарная, Авто, Авто), выгрузка равна базе у всех семи копий")
LAYER_WORDS = ("слой строкой не пишется: запись слоя тянет за собой счётчик номеров, область данных и число слоёв; перенос слоя из формы-образца — операция `copy_layer`")


@dataclasses.dataclass(frozen=True)
class Row:
    kind_of: str          # вид элемента
    name: str             # имя для `set_property`
    group: str            # группа палитры
    label: str            # подпись строки палитры
    kind: str             # flag, enum, int
    at: tuple             # путь по узлу элемента: ключ, затем номера внутри вложенных списков; пустой — адреса нет
    codes: dict = None    # слово палитры → код (у списков)
    low: int = None       # наименьшее целое, которое платформа принимала
    high: int = None      # наибольшее целое: граница диапазона в диалоге палитры
    note: str = ""
    refuse: str = ""      # не пусто — запись отказывает этими словами
    unkept: bool = False  # пишется в файл, но платформа обратно не читает: только под `unverified`
    unwritten: str = ""   # не пусто — строка в файл не пишется: доказательство словами (два сеанса)
    via: str = ""         # не пусто — строка строкой не пишется, её пишет эта операция
    pair: tuple = ()      # у границы области: (откуда в области данных нижний край диапазона, откуда верхний, позиция противоположной границы, нижняя ли эта граница)


ROWS = (
    # ── Поле графической схемы ────────────────────────────────────────────────────────────────────
    Row(GRAPH, "output", "Использование", "Вывод", "enum", ("content", "u5"), OUTPUT,
        note="«Разрешить» — 1, «Запретить» — 2, «Авто» — 0 (значение по умолчанию)."),
    Row(GRAPH, "use_grid", "Редактирование", "ИспользоватьСетку", "flag", ("content", "u2", 0, 1, 0, 2),
        note="При ☐ палитра делает серыми строки РежимОтрисовкиСетки и обоих шагов; значения в них остаются."),
    Row(GRAPH, "grid_mode", "Редактирование", "РежимОтрисовкиСетки", "enum", ("content", "u2", 0, 1, 0, 5), GRID_MODE,
        note="Платформа записала все четыре значения; «Рисовать линии» (3) — умолчание."),
    Row(GRAPH, "grid_horizontal_step", "Редактирование", "ГоризонтальныйШагСетки", "int", ("content", "u2", 0, 1, 0, 3), low=1,
        note="Умолчание 20; платформа записала 31."),
    Row(GRAPH, "grid_vertical_step", "Редактирование", "ВертикальныйШагСетки", "int", ("content", "u2", 0, 1, 0, 4), low=1,
        note="Умолчание 20; платформа записала 47."),
    # ── Поле географической схемы ─────────────────────────────────────────────────────────────────
    Row(GEO, "output", "Использование", "Вывод", "enum", ("u3", "u4"), OUTPUT, note="«Разрешить» — 1, «Запретить» — 2, «Авто» — 0."),
    Row(GEO, "projection", "Оформление", "Проекция", "enum", ("u3", "u2", 0, 1), PROJECTION_CODES,
        note="Код — номер пункта списка палитры с нуля (порядок списка не алфавитный); платформа записала все 37 кодов. Значение — строка палитры, имя "
             "системного перечисления `ТипПроекцииГеографическойСхемы` или английское имя."),
    Row(GEO, "latitude_shift", "Оформление", "СмещениеШироты", "int", ("u3", "u2", 0, 2), low=-LATITUDE, high=LATITUDE,
        note="Целое число градусов; диалог принимает значения от −90 до 90. Платформа записала 11."),
    Row(GEO, "longitude_shift", "Оформление", "СмещениеДолготы", "int", ("u3", "u2", 0, 3), low=-LONGITUDE, high=LONGITUDE,
        note="Целое число градусов; диалог принимает значения от −180 до 180. Платформа записала 22."),
    Row(GEO, "show_legend", "Оформление", "Легенда", "flag", ("u3", "u2", 2, 0), note="По умолчанию ☑ (1)."),
    Row(GEO, "show_title", "Оформление", "Заголовок", "flag", ("u3", "u2", 3, 0), note="По умолчанию ☑ (1)."),
    Row(GEO, "scale_keeping", "Оформление", "ПоддержкаМасштаба", "enum", ("u3", "u2", 6), SCALE_KEEPING, unkept=True,
        note="«Все данные» — 0, «Задается масштабом» — 1, «Заданная область» — 2; платформа записала 1 и 2. При «Заданной области» оживают четыре строки границ."),
    Row(GEO, "scale", "Оформление", "Масштаб", "int", ("u3", "u2", 7), low=1, unkept=True,
        note="Строка серая, пока ПоддержкаМасштаба не равна «Задается масштабом». Платформа записала 313."),
    Row(GEO, "south_latitude", "Оформление", "ШиротаЮжнойГраницы", "border", ("u3", "u2", 8), unkept=True, pair=(0, 2, 9, True),
        note="Градусы целым числом, в пределах первой координаты точек слоя (`u3/u2/1/0` и `u3/u2/1/2`); значение вне диапазона платформа не принимает."),
    Row(GEO, "north_latitude", "Оформление", "ШиротаСевернойГраницы", "border", ("u3", "u2", 9), unkept=True, pair=(0, 2, 8, False),
        note="То же, что у южной; южная не больше северной."),
    Row(GEO, "west_longitude", "Оформление", "ДолготаЗападнойГраницы", "border", ("u3", "u2", 10), unkept=True, pair=(1, 3, 11, True),
        note="Градусы целым числом, в пределах второй координаты точек слоя (`u3/u2/1/1` и `u3/u2/1/3`); значение вне диапазона платформа не принимает."),
    Row(GEO, "east_longitude", "Оформление", "ДолготаВосточнойГраницы", "border", ("u3", "u2", 11), unkept=True, pair=(1, 3, 10, False),
        note="То же, что у западной; западная не больше восточной."),
    Row(GEO, "layers", "Оформление", "Слои", "layer", ("u3", "u2", 1, 5), via="copy_layer",
        note="Слой переносит операция `copy_layer` (запись слоя, область данных, число слоёв и счётчик номеров)."),
    Row(GEO, "unnamed_event", "Другие", "(подпись пустая)", "event", ("u3", "events"),
        note="Событие — операция `set_event` (имя `Unnamed` либо число 2): запись обработчика с кодом 2 в списке записи элемента."),
    # ── Поле PDF-документа ────────────────────────────────────────────────────────────────────────
    Row(PDF, "border", "Другие", "Рамка", "enum", (), refuse=PDF_WORDS,
        unwritten=PDF_PROOF.format(what="Рамка (семь значений: Нет рамки, Двойная, Выпуклая, Вдавленная, Подчеркивание, Двойное подчеркивание, Черта сверху)")),
    Row(PDF, "border_color", "Другие", "ЦветРамки", "enum", (), refuse=PDF_WORDS, unwritten=PDF_PROOF.format(what="ЦветРамки (RGB и стиль «Рамка»)")),
    Row(PDF, "output", "Другие", "Вывод", "enum", (), refuse=PDF_WORDS, unwritten=PDF_PROOF.format(what="Вывод («Запретить» и «Разрешить»)")),
)
BY_KIND = {kind: {row.name: row for row in ROWS if row.kind_of == kind} for kind in KINDS}
NAMES = tuple(dict.fromkeys(row.name for row in ROWS))
BY_LABEL = {(row.kind_of, row.group, row.label): row for row in ROWS}


def address(row):
    """Адрес строки текстом (`content/u2/0/1/0/5`); пустая строка — адреса нет."""
    return "/".join(str(step) for step in row.at)


ADDRESSES = {(row.kind_of, address(row)): row for row in ROWS if row.at}
GRID_RECORD = ("content", "u2", 0, 1, 0)
GRID_COLOR = GRID_RECORD + (1,)
GRID_USE = GRID_RECORD + (2,)


# ── Чтение ────────────────────────────────────────────────────────────────────────────────────────

def _walk(node, at):
    """Значение по пути либо `KeyError`/`IndexError`/`TypeError`, если пути в записи нет."""
    for step in at:
        node = node[step]
    return node


def _shape_refusal(node, row):
    """Слова, если запись элемента не того строения, что у платформы 8.3.27 (адрес не читается); `None` — читается."""
    try:
        _walk(node, row.at)
    except (KeyError, IndexError, TypeError):
        return ("запись элемента не того строения, какое снято у платформы 8.3.27: места " + f"`{address(row)}`" + " в ней нет, и позицию писать некуда")
    if row.at[:2] == ("content", "u2"):
        head = _walk(node, GRID_RECORD)
        if not isinstance(head, list) or len(head) < 6:
            return "запись сетки не того строения, какое снято у платформы 8.3.27: меньше шести позиций"
    return None


def _label(row, code):
    if row.name == "projection":
        return PROJECTIONS[code][0] if isinstance(code, int) and not isinstance(code, bool) and 0 <= code < len(PROJECTIONS) else code
    for label, known in (row.codes or {}).items():
        if known == code:
            return label
    return code


def pretty(value, row):
    """Значение строки в читаемом виде по сырому."""
    if row.kind == "flag":
        return bool(value) if value in (0, 1) else value
    if row.kind == "enum":
        return _label(row, value)
    if row.kind == "border":
        return _number(value)
    if row.kind == "layer":
        return value[1] if isinstance(value, list) and len(value) > 1 else None
    return value


def _number(raw):
    """Число из записи платформы: целое, целое экспонентой (`6e1` → 60) или десятичная дробь (`57.5` — текстом)."""
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int):
        return raw
    whole = json0.exp_int(raw)
    if whole is not None:
        return whole
    return raw


def _decimal(raw):
    return Decimal(str(_number(raw)))


def _decimal_text(number):
    """Десятичное число → запись платформы: целое — `json0.int_exp_text` (`60` → `6e1`, `55` → `55`), дробь — текстом."""
    if number == number.to_integral_value():
        return json0.int_exp_text(int(number))
    return json0.Dec(format(number.normalize(), "f"))


def read(element_node, name):
    """Значение строки в читаемом виде у узла элемента; отказ словами, если адреса нет или записи в узле нет."""
    row = _row(element_node.get("type"), name)
    refusal = row.refuse or _shape_refusal(element_node, row)
    if refusal:
        raise EditError(f"{name} {NAMES_OF_KIND[row.kind_of]}: {refusal}")
    return pretty(_walk(element_node, row.at), row)


def _row(kind, name):
    rows = BY_KIND.get(kind) or {}
    if name not in rows:
        raise EditError(f"у {NAMES_OF_KIND.get(kind, kind)} такой строки палитры нет: {name!r}; есть {', '.join(rows)}")
    return rows[name]


# ── Запись ────────────────────────────────────────────────────────────────────────────────────────

def _shown(value):
    if isinstance(value, bool):
        return "☑" if value else "☐"
    return f"«{value}»" if isinstance(value, str) else repr(value)


def _code_of(row, value, unverified):
    """Код списка по слову палитры; число — только под `unverified`."""
    if isinstance(value, str) and value in row.codes:
        return row.codes[value]
    if row.name == "projection":
        known = "строка палитры (37 проекций), имя значения системного перечисления `ТипПроекцииГеографическойСхемы` или английское имя"
    else:
        known = ", ".join(f"«{label}» ({code})" for label, code in row.codes.items())
    if isinstance(value, bool) or not isinstance(value, int):
        raise EditError(f"{row.name} ({row.label}): значение — {known} или число кода под `unverified`, а пришло {value!r}")
    if not unverified:
        raise EditError(f"{row.name} ({row.label}): число кода записывается только под `unverified`; слово палитры — {known}")
    limit = len(PROJECTIONS) if row.name == "projection" else max(row.codes.values()) + 1
    if not 0 <= value < limit:
        raise EditError(f"{row.name} ({row.label}): код {value} вне списка палитры (коды от 0 до {limit - 1})")
    return value


def _flag_of(row, value, unverified):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int) and value in (0, 1) and unverified:
        return value
    raise EditError(f"{row.name} ({row.label}): флажок — true или false, а пришло {value!r}")


def _int_of(row, value, unverified):
    if isinstance(value, bool) or not isinstance(value, int):
        raise EditError(f"{row.name} ({row.label}): платформа записывает целое число, а пришло {value!r}; дробные значения не проверялись")
    if row.high is not None and not row.low <= value <= row.high:
        raise EditError(f"{row.name} ({row.label}): диалог палитры принимает значения от {row.low} до {row.high}, а пришло {value}")
    if row.low is not None and row.high is None and value < row.low and not unverified:
        raise EditError(f"{row.name} ({row.label}): значение меньше {row.low} платформа не писала; позвать всё же можно — unverified=True, — и тогда результат "
                        "проверяете вы")
    return value


def _warnings(node, row, new):
    """Слова о строке, которая в палитре при соседнем значении серая: значение записано, а действует ли оно, не проверялось."""
    if row.kind_of == GRAPH and row.name in ("grid_mode", "grid_horizontal_step", "grid_vertical_step"):
        if _walk(node, GRID_USE) == 0:
            return (f"ВНИМАНИЕ: строка {row.label} в палитре серая при ИспользоватьСетку ☐; значение записано, но действует ли оно при выключенной сетке, "
                    "не проверялось")
    if row.kind_of == GEO and row.name == "scale":
        if _walk(node, ("u3", "u2", 6)) != SCALE_KEEPING["Задается масштабом"]:
            return ("ВНИМАНИЕ: строка Масштаб в палитре серая, пока ПоддержкаМасштаба не равна «Задается масштабом»; значение записано, но действует ли оно при "
                    "другой поддержке, не проверялось")
    if row.kind == "border":
        out = []
        if _walk(node, ("u3", "u2", 6)) != SCALE_KEEPING["Заданная область"]:
            out.append(f"ВНИМАНИЕ: строка {row.label} в палитре серая, пока ПоддержкаМасштаба не равна «Заданная область»; значение записано, но действует ли оно при "
                       "другой поддержке, не проверялось")
        if any(_decimal(_walk(node, ("u3", "u2", at))) == 0 for at in BORDER_PLACES):
            out.append("ВНИМАНИЕ: заданы не все четыре границы; незаданные платформа при выборе «Заданной области» заполняет по слою, что она пишет для них в файл, "
                       "не снято — задавайте все четыре")
        return "; ".join(out)
    return ""


BORDER_PLACES = (8, 9, 10, 11)
SHIFT_PLACE = ("u3", "u2", 0, 3)


def _area(node):
    """Область данных слоёв `u3/u2/1`: четыре края (первая координата от и до, вторая от и до), число слоёв, запись слоя."""
    area = _walk(node, ("u3", "u2", 1))
    if not isinstance(area, list) or len(area) < 6:
        raise EditError("запись области данных слоёв не того строения, какое снято у платформы 8.3.27: меньше шести позиций")
    return area


def _has_layer(node):
    area = _area(node)
    return bool(area[4]) and isinstance(area[5], list) and bool(area[5])


def _border_of(node, row, value):
    """Значение границы: целые градусы внутри области данных слоёв, не нарушающие порядка с противоположной границей. Отказ — всегда, `unverified` не снимает."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise EditError(f"{row.name} ({row.label}): платформа записывает градусы целым числом, а пришло {value!r}; минуты, секунды и дробные значения не проверялись")
    if not _has_layer(node):
        raise EditError(f"{row.name} ({row.label}): {NO_LAYER_WORDS}")
    area = _area(node)
    low, high = _decimal(area[row.pair[0]]), _decimal(area[row.pair[1]])
    if not low <= value <= high:
        raise EditError(f"{row.name} ({row.label}): диалог платформы принимает значения внутри области данных слоёв — от {low} до {high}, а пришло {value}")
    other = _decimal(_walk(node, ("u3", "u2", row.pair[2])))
    if other != 0 and (value > other if row.pair[3] else value < other):
        raise EditError(f"{row.name} ({row.label}): порядок «{'меньшая' if row.pair[3] else 'большая'} граница — {row.label}» нарушен: противоположная граница {other}, "
                        f"а пришло {value}; такой порядок платформа не проверялся")
    return json0.int_exp_text(value)


def _shift_follows_borders(node):
    """СмещениеДолготы равно полусумме южной и северной границ (так платформа пересчитала его трижды: 45.45 → 57.8 → 57.5 при слое 30.3…60.6 и границах 55 и 60);
    пересчёт — только когда заданы обе. Возвращает слова отчёта или пустую строку."""
    south, north = (_decimal(_walk(node, ("u3", "u2", at))) for at in (8, 9))
    if south == 0 or north == 0:
        return ""
    holder = _walk(node, SHIFT_PLACE[:-1])
    before = holder[SHIFT_PLACE[-1]]
    holder[SHIFT_PLACE[-1]] = _decimal_text((south + north) / 2)
    return (f"СмещениеДолготы {_number(before)} → {_number(holder[SHIFT_PLACE[-1]])} (позиция {'/'.join(str(step) for step in SHIFT_PLACE)}): платформа ставит его "
            "равным полусумме южной и северной границ и пересчитывает при каждом вводе, запись делает то же")


def write(doc, element, name, value, unverified=False):
    """Строка палитры по имени (`set_property`); `None`, если элемент другого вида или имени нет у этого вида."""
    place = find_element(doc, element)
    node = place.element
    kind = node.get("type")
    row = (BY_KIND.get(kind) or {}).get(name)
    if row is None:
        return None
    where = f"{name} у {element!r} ({kind}): {row.label}"
    if row.refuse:
        raise EditError(f"{where} — {row.refuse}.")
    if row.via:
        raise EditError(f"{where} — {LAYER_WORDS}.")
    refusal = _shape_refusal(node, row)
    if refusal:
        raise EditError(f"{where} — {refusal}.")
    if row.kind == "event":
        raise EditError(f"{where} — это событие: его пишет операция set_event (имя `Unnamed` либо число 2), а не set_property.")
    if row.unkept and not unverified:
        raise EditError(f"{where} — {UNKEPT_WORDS}. Позвать всё же можно — unverified=True, — и тогда результат проверяете вы.")
    if row.kind == "flag":
        new = _flag_of(row, value, unverified)
    elif row.kind == "enum":
        new = _code_of(row, value, unverified)
    elif row.kind == "border":
        new = _border_of(node, row, value)
    else:
        new = _int_of(row, value, unverified)
    holder = _walk(node, row.at[:-1])
    before = pretty(holder[row.at[-1]], row)
    holder[row.at[-1]] = new
    after = pretty(new, row)
    said = f"{NAMES_OF_KIND[kind].replace('поля', 'поле', 1)} {element!r}: {row.label} ({row.group}) {_shown(before)} → {_shown(after)}; позиция {address(row)}"
    words = [UNKEPT_WORDS] if row.unkept else []
    if row.kind == "border" and row.pair[0] == 0:
        followed = _shift_follows_borders(node)
        if followed:
            words.append(followed)
    warning = _warnings(node, row, new)
    if warning:
        words.append(warning)
    return said + "".join(f"; {text}" for text in words)


def mirror_back_color(doc, element):
    """После записи ЦветаФона у поля графической схемы: тот же цвет во втором месте — записи сетки (`content/u2/0/1/0/1`).

    Платформа пишет цвет фона дважды: в общем блоке и в записи сетки. Возвращает слова отчёта или пустую строку, если у элемента другой вид."""
    node = find_element(doc, element).element
    if node.get("type") != GRAPH:
        return ""
    problem = _shape_refusal(node, BY_KIND[GRAPH]["use_grid"])
    if problem:
        return f"второе место цвета (запись сетки) не записано — {problem}"
    color = node["content"]["u0"]["back_color"]
    record = _walk(node, GRID_RECORD)
    before = record[1]
    record[1] = _grid_color(color)
    return (f"то же в записи сетки {'/'.join(str(step) for step in GRID_COLOR)} ({_color_text(before)} → {_color_text(record[1])}): платформа пишет цвет фона дважды, "
            "и правка одного места разошлась бы с другим")


def _grid_color(block):
    """Блок цвета общего блока (`decode`) → сырой блок записи сетки `[3, вид, [код]]`."""
    return [block["mark"], block["color_kind"], [block["value"]["code"]]]


def _color_text(raw):
    if isinstance(raw, list) and len(raw) == 3 and isinstance(raw[2], list) and raw[2]:
        return f"вид {raw[1]}, код {raw[2][0]}"
    return repr(raw)


# ── Для документов и покрытия ─────────────────────────────────────────────────────────────────────

def coverage_address(kind, group, label):
    """Адрес строки палитры для покрытия: `row:<вид>/<адрес>`; у строки без адреса — `None`. `ValueError`, если строки в таблице нет."""
    row = BY_LABEL.get((kind, group, label))
    if row is None or not row.at:
        return None
    return f"row:{kind}/{address(row)}"


def check_address(text):
    """Адрес `row:<вид>/<адрес>` обязан называть строку таблицы; возвращает строку."""
    kind, _, path = text[len("row:"):].partition("/")
    if (kind, path) not in ADDRESSES:
        raise ValueError(f"адрес {text!r}: в таблице строк схем (`schemarows.ROWS`) такого нет")
    return ADDRESSES[(kind, path)]


def unwritten_words(kind, group, label):
    """Доказательство, что строка без адреса в файл не пишется: `("not_written", слова)`; `None`, если такого доказательства у строки нет."""
    row = BY_LABEL.get((kind, group, label))
    return ("not_written", row.unwritten) if row is not None and row.unwritten else None


def refusal_words(kind, group, label):
    """Слова отказа у строки без адреса (`Row.refuse`); `None`, если строки нет или адрес есть."""
    row = BY_LABEL.get((kind, group, label))
    return row.refuse if row is not None and row.refuse else None


def doc_rows(kind):
    """Строки таблицы вида для документа: `[(имя, подпись, значения, адрес, примечание)]`."""
    out = []
    for row in ROWS:
        if row.kind_of != kind:
            continue
        if row.kind == "flag":
            values = "`true` или `false`"
        elif row.kind == "enum" and row.name == "projection":
            values = "одна из 37 строк палитры"
        elif row.kind in ("event", "layer"):
            values = "—"
        elif row.kind == "border":
            values = "целое число градусов в пределах области слоёв"
        elif row.kind == "enum":
            values = ", ".join(f"«{label}»" for label in row.codes)
        else:
            values = "целое число" + (f" от {row.low}" if row.low is not None and row.high is None else "") + \
                (f" от {row.low} до {row.high}" if row.high is not None else "")
        out.append((row.name, row.label, values, address(row) or "—", row.refuse or row.note))
    return out


def projections_text():
    """Проекции по кодам: `код — строка палитры`."""
    return "; ".join(f"{code} — {names[0]}" for code, names in enumerate(PROJECTIONS))
