"""Один дизайн формы: версия общего блока, вид 8.2 / 8.3, оформление по соседям, сверка с формами.

Все элементы формы держатся в одной версии общего блока и в одном виде; правка формы сверяет
версию и оформление с другими элементами формы и с другими формами системы.

* **Версия общего блока** (первая позиция блока с цветами, шрифтом и рамкой; у контейнера формы —
  `layout_version`) — поколение платформы, сохранявшей форму: 10, 13, 15, 16. Платформа вид сама
  не меняет, а при пересохранении поднимает всю форму до своей версии. Смеси версий в форме нет,
  кроме вложенных элементов колонок. Шрифт зависит от версии (у 10 запись шрифта шестая, у 13,
  15, 16 — седьмая) и между поколениями не переносится.
* **Вид поля ввода «как в 8.2» или «как в 8.3»** — позиция 16 общего блока (`view` карты): 1 —
  8.2 (прямые углы, светлые кнопки), 0 и 2 — 8.3 (скруглённые, бежевые). Это класс
  (`VIEW_CLASS`); `u43` свойств поля — производное (`u43_rule`: 1 при виде 8.2 или явном
  ЦветеРамки, иначе 2), платформа досчитывает его при сохранении. Вид известен у версии 16; у
  поля ввода другой версии `design` называет позицию 16, а не вид.
* **Вложенные элементы колонок** хранятся упакованным конвертом, и их версия бывает другой, чем у
  формы (форма 15 с вложенными 16; форма 16 с вложенными 10 и 15). Платформа такое пишет сама,
  редактор не создаёт (`edit.set_column_control` отказывает так же, как `add_element`);
  `validate` и `design` называют только смесь вне этих пар.
* **Вид новой формы и нового поля** выбирает конфигурация (`choose_view`, `config_view`,
  `--siblings`): форма однородна — вид формы; смешанная или без полей ввода — вид конфигурации
  (по преобладанию полей ввода 16 соседних форм); соседних форм нет — вид большинства формы, при
  равенстве — свой; нет и полей — свой (у шаблона — как пишет конфигуратор 8.3.27). Всю форму к
  одному виду приводит `edit.set_view`, включая вложенные поля ввода колонок; поля другой версии
  общего блока оно не трогает.
* **Оформление по соседям, целым сочетанием.** Сочетание — позиции 2–11 общего блока (`POSITIONS`:
  цвета, шрифт, ПрозрачныйФон, рамка и её цвет); у рамки группы ещё и её рамка, у поля ввода и
  поля выбора — вид (`view_of`). Берётся самое частое сочетание среди элементов того же типа и
  той же версии; при равенстве — сочетание соседа, стоящего в форме раньше; отчёт говорит «поровну».
  Вид — первым, оформление — среди полей этого вида (`by_neighbours`). `like` берёт соседа
  целиком, но вид — формы (`like_view`).
* **Сверка** (`compare`): сводка формы (`summary`) против свода соседних форм (`pool`) — той же
  конфигурации или обработки; каталог выгрузки называет человек. Пять вопросов: версия не та,
  что у большинства; стиль не тот; у элемента сочетание, которого нет у соседей того же типа и
  версии; все сочетания у соседей есть, а самое частое не их; поля ввода 16 не все вида
  конфигурации. Это предупреждения, а не отказы: для правленой формы — сведение, для новой —
  ориентир.
"""
import collections
import copy
import pathlib

from . import props, schema
from .json0 import dumps_line

# ── Версия общего блока ──────────────────────────────────────────────────────────────────────

VERSIONS = (10, 13, 15, 16)
# Корпусный снимок: версия контейнера формы → форм.
CORPUS_FORM_VERSIONS = {10: 2205, 13: 517, 15: 793, 16: 1478}
CORPUS_FORMS = sum(CORPUS_FORM_VERSIONS.values())
# Форм, где общий блок хоть одного элемента (без вложенных элементов колонок) другой версии, чем
# контейнер.
CORPUS_MIXED_FORMS = 0
# Вложенные элементы колонок другой версии, чем форма: (версия формы, версия вложенного) →
# (элементов, форм).
CORPUS_NESTED_ALIEN = {(15, 16): (36, 4), (16, 10): (11, 3), (16, 15): (10, 2)}
CORPUS_NESTED_FORMS = 2230
# Версия записи шрифта при версии общего блока: (запись, блоков).
CORPUS_FONT_BY_VERSION = {10: (6, 32659), 13: (7, 16253), 15: (7, 19560), 16: (7, 33273)}
# Внутри формы: (форм с единственным самым частым сочетанием типа; форм с двумя и больше элементами
# типа).
CORPUS_IN_FORM = {"TextBox": (2592, 2693), "CheckBox": (465, 495), "GroupBox": (644, 658),
                  "Label": (2665, 3166), "Button": (1307, 1813), "TableBox": (554, 616),
                  "Panel": (1548, 1725), "ComboBox": (440, 445), "CommandBar": (320, 2580),
                  "PictureBox": (74, 1161)}
# Шаблон в форме 16 с соседями того же типа: (форм, где оформление соседей отличается от шаблонного;
# форм с соседями).
CORPUS_NEIGHBOURS = {"TextBox": (867, 994), "Label": (895, 1075), "CheckBox": (359, 475),
                     "GroupBox": (206, 257), "Button": (622, 639)}
X19C = ("форма версии 10 с элементами версии 16 открывается, оба поколения рисуются одинаково, "
        "а пересохранение поднимает всю форму до версии 16 (проверено в предприятии)")

COMMON_TRAILS = {anchor[len("Element."):]: props._anchor_trail(anchor, address)
                 for anchor, address in schema.COMMON_BLOCK_ADDRESSES.items()}
LAYOUT_VERSION = schema.MAP["Layout16"].fields[0].name
VERSION_KEY = "u0"  # первая позиция общего блока элемента; карта её не называет


def _int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _dicts(node, skip):
    """Словари под узлом — обходом по словарям, без списков и без ключей из `skip`."""
    for key, value in node.items() if isinstance(node, dict) else ():
        if key in skip or not isinstance(value, dict):
            continue
        yield key, value
        yield from _dicts(value, skip)


def _elements_key():
    from . import validate  # круговой импорт: validate зовёт design
    return validate.PLACEMENT_NAMES[3], validate.PLACEMENT_NAMES[4]


def layout(doc):
    """Общий блок КОНТЕЙНЕРА формы (узел `Layout<версия>`) либо `None`."""
    elements, _items = _elements_key()
    form = doc.get("form") if isinstance(doc, dict) else None
    container = form.get("container") if isinstance(form, dict) else None
    for _key, value in _dicts(container, {elements}):
        if LAYOUT_VERSION in value:
            return value
    return None


def form_version(doc):
    """Версия общего блока формы — у контейнера (`layout_version`); `None`, если не разобран."""
    block = layout(doc)
    value = block.get(LAYOUT_VERSION) if isinstance(block, dict) else None
    return value if _int(value) else None


def block_of(element):
    """Общий блок самого элемента — по адресу карты для его типа; `None`, если блока нет."""
    trail = COMMON_TRAILS.get(element.get("type")) if isinstance(element, dict) else None
    node = element
    for key in trail or ():
        node = node.get(key) if isinstance(node, dict) else None
    return node if trail and isinstance(node, dict) else None


def version_of(block):
    value = block.get(VERSION_KEY) if isinstance(block, dict) else None
    return value if _int(value) else None


def nested_blocks(element):
    """Общие блоки вложенных элементов колонок табличного поля: `[(колонка, вид, блок)]`."""
    from . import edit
    columns = edit.columns_of(element) if isinstance(element, dict) else None
    out = []
    for column in (columns or {}).get(edit.COLUMN_ITEMS) or []:
        head = edit._column_body(column)
        guid = head.get(edit.COLUMN_CONTROL_TYPE)
        kind = schema.element_type_name(guid.get("guid")) if isinstance(guid, dict) else None
        control = head.get(edit.COLUMN_CONTROL)
        packed = control.get(edit.CONTROL_ELEMENT) if isinstance(control, dict) else None
        content = packed.get(edit.PACKED_CONTENT) if isinstance(packed, dict) else None
        block = content
        for key in (COMMON_TRAILS.get(kind) or ())[1:]:
            block = block.get(key) if isinstance(block, dict) else None
        if kind in COMMON_TRAILS and isinstance(block, dict):
            out.append((edit._column_name(column), kind, block))
    return out


def content_versions(kind, content):
    """Версия общего блока в СОДЕРЖИМОМ вложенного элемента колонки вида `kind`: `[(что, версия)]`;
    пусто, если блока нет.
    """
    block = content
    for key in (COMMON_TRAILS.get(kind) or ())[1:]:
        block = block.get(key) if isinstance(block, dict) else None
    version = version_of(block) if kind in COMMON_TRAILS else None
    return [] if version is None else [(f"тело вложенного {kind}", version)]


def node_versions(node):
    """Версии общих блоков УЗЛА, который встаёт на форму: `[(что, версия)]` — свой блок и
    блоки вложенных элементов его колонок. Вложенных элементов формы шаблон не носит."""
    out = []
    own = version_of(block_of(node))
    if own is not None:
        out.append(("общий блок элемента", own))
    for column, kind, block in nested_blocks(node):
        version = version_of(block)
        if version is not None:
            out.append((f"вложенный {kind} колонки {column!r}", version))
    return out


def elements(doc):
    """Все элементы формы любой глубины: `(имя, узел)` — сверху вниз, в порядке списков."""
    names, items = _elements_key()
    out = []

    def walk(holder):
        block = holder.get(names) if isinstance(holder, dict) else None
        for item in (block.get(items) or []) if isinstance(block, dict) else []:
            if isinstance(item, dict):
                out.append(((item.get("name_block") or {}).get("name"), item))
                walk(item)

    form = doc.get("form") if isinstance(doc, dict) else None
    walk(form.get("container") if isinstance(form, dict) else None)
    return out


def mixed(doc):
    """Элементы, чей общий блок не той версии, что форма: `(версия формы, [(имя, тип, версия)])`.

    Вложенные элементы колонок сюда не входят: у них смесь платформенная (см. описание модуля).
    """
    version = form_version(doc)
    alien = []
    for name, element in elements(doc):
        own = version_of(block_of(element))
        if own is not None and version is not None and own != version:
            alien.append((name, element.get("type"), own))
    return version, alien


def nested_mix(doc):
    """Вложенные элементы колонок другой версии, чем форма, вне пар, которые пишет платформа:
    `[(элемент, колонка, вид, версия)]`.
    """
    version = form_version(doc)
    out = []
    for name, element in elements(doc):
        for column, kind, block in nested_blocks(element):
            own = version_of(block)
            if version is not None and own is not None and own != version \
                    and (version, own) not in CORPUS_NESTED_ALIEN:
                out.append((name, column, kind, own))
    return out


def nested_mix_words(version, found):
    listed = ", ".join(f"{kind} колонки {column!r} у {name!r} ({v})"
                       for name, column, kind, v in found[:5]) + (" …" if len(found) > 5 else "")
    pairs = ", ".join(f"{a} → {b}" for (a, b) in CORPUS_NESTED_ALIEN)
    return (f"у формы версия общего блока {version}, а у вложенных элементов колонок {listed} — "
            "другая, такой пары «форма → вложенный» не бывает: чужая версия у вложенных бывает только "
            f"парами, которые пишет сама платформа ({pairs}). Платформа при пересохранении "
            f"поднимает форму до своей версии — {X19C}")


def versions_words():
    """Числа корпуса словами: «10 — 2 205, 13 — 517, …»."""
    return ", ".join(f"{v} — {_n(n)}" for v, n in CORPUS_FORM_VERSIONS.items())


# ── Оформление: сочетание позиций общего блока ────────────────────────────────────────────────

POSITIONS = (2, 3, 4, 5, 6, 7, 8, 9, 10, 11)
_TEXTBOX_BLOCK = schema.MAP[schema._COMMON_BLOCKS["Element.TextBox"]]
NAMES = {position: _TEXTBOX_BLOCK.fields[position].name for position in POSITIONS}
# Скрытые позиции: 16 и 17 общего блока (16 — при версиях 15 и 16, 17 — только при 16) и их спутник
# — `u43` свойств поля ввода, `L1+17` хвоста свойств поля выбора. Конфигуратор их не показывает.
# Решения по типам:
#
# * поле ввода: в сочетание входит вид (`VIEW_CLASS`), а не тройка; `u43` пишет правило `u43_rule`,
#   позицию 17 — нулём, когда уходит от 2 (17 = 1 бывает только при 16 = 2);
# * поле выбора: вид не проверялся; тройка (16, 17, `L1+17`) берётся как есть (`RAW_VIEW`): берётся та
#   тройка, которая у большинства соседей, и переносится от донора целиком;
# * кнопка (`HIDDEN_CARRIED`): позиции 16 и 17 переносятся от донора; большинство по ним не считается, и они
#   не сверяются;
# * табличное поле (`HIDDEN_PLATFORM`): позицию 16 ставит платформа при сохранении, её не берут у
#   соседей и не сверяют.
HIDDEN = (16, 17)
HIDDEN_KINDS = ("TextBox", "ComboBox")
RAW_VIEW = ("ComboBox",)
HIDDEN_CARRIED = ("Button",)
HIDDEN_PLATFORM = ("TableBox",)
HIDDEN_RESAVED = ("r1", "r2", "r3", "r5", "r7", "r7p", "r8")
NAMES.update({position: f"u{position}" for position in HIDDEN})

# ── Вид поля ввода: «как в 8.2» или «как в 8.3» ─────────────────────────────────────

VIEW_POSITION = 16
VIEW = _TEXTBOX_BLOCK.fields[VIEW_POSITION].name  # `view` карты
VIEW_ENUM = schema.ENUMS[_TEXTBOX_BLOCK.fields[VIEW_POSITION].enum]
# Код позиции → вид.
VIEW_CLASS = {1: "8.2", 0: "8.3", 2: "8.3"}
VIEWS = ("8.2", "8.3")
# Код, который редактор пишет виду: 1 — единственный код 8.2; 0 — так новое поле пишет конфигуратор
# 8.3.27, а 2 он не пишет.
VIEW_WRITTEN = {"8.2": 1, "8.3": 0}
VIEW_WORD = "вид"  # имя вида в сочетании, в сводке и в словах
# Что о скрытых позициях известно — по типу, фразой отчётов, предупреждений и заметок.
VIEW_NOTES = {
    "TextBox": ("вид поля ввода решает позиция 16 (`view`): 1 — «как в 8.2», 0 и 2 — «как в 8.3»"
                "; u43 — производное: платформа досчитывает его при сохранении из вида и из "
                "явного ЦветаРамки"),
    "ComboBox": "вид поля выбора платформой не проверялся (проверен у поля ввода)",
    "Button": "позиция 16 кнопки вида не меняет",
}
# Форм, где скрытые позиции у соседей разные: у поля ввода — позиция 16 или `u43`, у поля выбора —
# 16 или спутник, у прочих — позиция 16. Каждый такой тип описан ровно в одном из решений выше.
# Раскол вида — `CORPUS_VIEW_SPLIT`.
CORPUS_HIDDEN_SPLIT = {"TextBox": 58, "Button": 17, "TableBox": 5, "ComboBox": 3}
# Раскол вида, который называет `design`: у поля ввода — по виду 8.2 / 8.3 у форм версии 16, у поля
# выбора — по тройке. У поля ввода версии 15 `design` называет позицию, а не вид, строкой «TextBox
# (форма 15)».
CORPUS_VIEW_SPLIT = {"TextBox": 53, "TextBox (форма 15)": 2, "ComboBox": 3}
# Значения: у поля ввода пара (позиция 16, `u43`) по версии общего блока; у поля выбора — (позиция
# 16, `L1+17`); у кнопки версии 16 — позиция 16. Вложенные элементы колонок держат те же пары.
CORPUS_TEXTBOX_U16_U43 = {15: {(1, 1): 2857, (0, 2): 4},
                          16: {(0, 2): 5787, (1, 1): 1584, (2, 2): 71, (0, 1): 3}}
CORPUS_COMBOBOX_U16_MATE = {15: {(1, 1): 451}, 16: {(0, 2): 458, (1, 1): 61, (2, 2): 26}}
CORPUS_NESTED_HIDDEN = {("TextBox", 15): {(0, 2): 90, (1, 1): 2942},
                        ("TextBox", 16): {(0, 1): 4, (0, 2): 9634, (1, 1): 6280, (2, 2): 44},
                        ("ComboBox", 15): {(1, 1): 6}, ("ComboBox", 16): {(0, 2): 12, (1, 1): 3}}
CORPUS_BUTTON_U16 = {0: 2506, 2: 142}
CORPUS_TABLEBOX_U16 = {15: {0: 44, 2: 443}, 16: {0: 116, 1: 12, 2: 2126}}
# Правило `u43`: 1 при виде 8.2 или явном (RGB, `color_kind` 0) ЦветеРамки, иначе 2. Счёт: (своё или
# вложенное, версия) → (полей по правилу, полей всего). Про RGB свидетельств мало
# (`CORPUS_U43_RGB`).
CORPUS_U43_RULE = {("своё", 15): (2861, 2861), ("своё", 16): (7444, 7445),
                   ("вложенное", 15): (3032, 3032), ("вложенное", 16): (15958, 15962)}
CORPUS_U43_RGB = {(15, 1): 4, (16, 0): 2}
LAB_PAIRS = {("ComboBox", 16): {(0, 1): "проверочной формой с цветом рамки RGB"},
             ("TextBox", 16): {(0, 1): "проверочной формой с цветом рамки RGB"}}
# Вид у полей ввода формы: форм со смесью видов, единственный вид большинства, виды поровну; дорога
# `choose_view` без соседних форм: вид формы (однородной), большинства (смешанной), виды поровну (свой,
# 8.3), шаблона (полей ввода нет).
CORPUS_VIEWS = {"TextBox": {"форм со смесью видов": 55, "единственный вид": 54, "виды поровну": 1,
                            "целое сочетание дало бы вид меньшинства": 1,
                            "шаблон: вид формы": 941, "шаблон: вид большинства формы": 52,
                            "шаблон: виды поровну": 1, "шаблон: вид шаблона": 484}}
# Вид конфигурации — вид большинства полей ввода 16 её форм (корень выгрузки; у внешней обработки —
# её каталог); в каталогах из одной формы вид — свойство формы, `--siblings` соседей не даёт.
# Правило нового поля в форме 16 (`target_view`): форма однородна — вид формы; смешанная или без
# полей ввода — вид конфигурации; нет и его — шаблон. Счёт дорог — `CORPUS_CONFIG_VIEW`,
# `CORPUS_CONFIG_VIEW_DIFFERS`: у смешанной формы без соседей берётся вид большинства формы, а не
# шаблона — он чаще совпадает с видом конфигурации.
CORPUS_CONFIGS = {"конфигураций с полями ввода 16": 15, "форм 16 с полями ввода две и больше": 8,
                  "из них смешанных": 8, "каталогов из одной формы": 7}
CORPUS_CONFIG_VIEW = {"вид формы": 941, "вид конфигурации — полей ввода нет": 482,
                      "вид конфигурации — форма смешанная": 53, "вид шаблона": 2}
CORPUS_CONFIG_VIEW_DIFFERS = {"однородная форма не вида конфигурации": 87,
                              "смешанная: большинство формы другого вида": 12,
                              "смешанная: виды поровну в форме": 1,
                              "смешанная: шаблон не вида конфигурации": 43}
# Вложенные поля ввода колонок несут позицию 16 (версии 15 и 16), у соседей она разная, поэтому
# `set_view` приводит и их; вид вложенного поля не проверялся. Вложенные поля другой версии, чем
# форма, оно не трогает и называет.
CORPUS_NESTED_VIEWS = {"табличных полей": 1977, "у колонок одного поля разный вид": 190,
                       "форм": 952, "вложенные разного вида": 118,
                       "форм и со своими полями": 533, "виды вложенных и своих расходятся": 62}
TEXTBOX_PROPS = COMMON_TRAILS["TextBox"][:-1]  # свойства поля: общий блок — их позиция 0
TEXTBOX_U43 = getattr(schema.MAP[schema._COMMON_BLOCKS["Element.TextBox"].rsplit(".", 1)[0]]
                      .fields.get(43), "name", "u43")
COMBOBOX_PROPS = COMMON_TRAILS["ComboBox"][:-1]
# Хвост блока свойств поля выбора адресуется от конца списка выбора (`L1+<смещение>`); карта имени
# позиции 17 хвоста не даёт, ключ в JSON запасной.
COMBOBOX_MATE = "L1+17"
# Спутник позиции 16: тип → (адрес блока свойств от элемента, ключ спутника в нём). Спутник поля
# выбора — безымянная позиция хвоста (`edit.SIDE_POSITIONS`); `u43` поля ввода пишет правило.
MATES = {"TextBox": (TEXTBOX_PROPS, TEXTBOX_U43), "ComboBox": (COMBOBOX_PROPS, COMBOBOX_MATE)}
# Пары (16, спутник), которые держит снимок: `validate` предупреждает о прочих.
SEEN_PAIRS = {("TextBox", v): set(pairs) for v, pairs in CORPUS_TEXTBOX_U16_U43.items()}
SEEN_PAIRS.update({("ComboBox", v): set(pairs) for v, pairs in CORPUS_COMBOBOX_U16_MATE.items()})
for _key, _pairs in (*CORPUS_NESTED_HIDDEN.items(), *LAB_PAIRS.items()):
    SEEN_PAIRS[_key] |= set(_pairs)
GROUP_BORDER_TRAIL = props._anchor_trail(
    "Element.GroupBox",
    (2, 1, next(i for i, slot in schema.MAP["Content.GroupBox.u1"].fields.items()
                if getattr(slot, "name", None) == "border")))
GROUP_BORDER = "border рамки группы"


def _line(value):
    return dumps_line(value, bools=True)


def _group_border(element):
    node = element
    for key in GROUP_BORDER_TRAIL:
        node = node.get(key) if isinstance(node, dict) else None
    return node


def _values(block):
    return list(block.values()) if isinstance(block, dict) else []


def view_code(value):
    """Код позиции 16 поля ввода: имя перечисления `TextBox.View` → код, целое — оно же."""
    if isinstance(value, str):
        return VIEW_ENUM.codes.get(value)
    return value if _int(value) else None


def _view_value(code):
    """Значение позиции 16 для JSON — имя перечисления, если у кода оно есть."""
    return next((name for name, c in VIEW_ENUM.codes.items() if c == code), code)


def class_of(block):
    """Вид по общему блоку поля ввода — «8.2», «8.3» или `None` (позиции 16 нет, код незнаком)."""
    values = _values(block)
    return VIEW_CLASS.get(view_code(values[VIEW_POSITION])) if len(values) > VIEW_POSITION \
        else None


def textbox_view(element):
    """Вид поля ввода (`class_of` его общего блока); у прочих типов — `None`."""
    return class_of(block_of(element)) if element.get("type") == "TextBox" else None


def rgb_border(block):
    """Явный (RGB) ЦветРамки у общего блока: вид цвета 0 (карта, узел `Color`)."""
    values = _values(block)
    colour = values[6] if len(values) > 6 else None
    return isinstance(colour, dict) and colour.get("color_kind") == 0


def u43_rule(block):
    """`u43` по правилу платформы: 1 при виде 8.2 или явном ЦветеРамки, иначе 2; `None` — вида
    у блока нет. Числа и оговорка про RGB — у `CORPUS_U43_RULE`."""
    view = class_of(block)
    if view is None:
        return None
    return 1 if view == "8.2" or rgb_border(block) else 2


U43_WORDS = ("u43 — производное вида: платформа досчитывает его при сохранении (1 при виде 8.2 "
             "или явном ЦветеРамки, иначе 2; про RGB-рамку свидетельств "
             "мало)")
# Вид проверен у версии 16: у поля ввода другой версии `design` называет позицию 16, а не вид, и
# `set_view` его не трогает.
UNMEASURED = ("у поля ввода не версии 16 вид не проверялся: он известен у версии 16, а у 10 "
              "и 13 позиции 16 нет вовсе")


# `like` у полей ввода формы 15: позиция 16 копии берётся у образца, а не приводится к большинству
# формы (`CORPUS_VIEW_SPLIT`).
CORPUS_LIKE15 = {"полей ввода формы 15": 2861, "прежнее правило привело бы": 2}


def kept_words(block, whose):
    """Фраза отчёта у поля ввода НЕ версии 16, которому вид не пишется: позиция 16 и `u43` остаются,
    как у `whose`. `None` — у версии 16 (там вид пишется) и у прочих типов.

    Одно место на три дороги, где новое поле ввода получало вид формы (`like_view`, `apply_view`,
    `by_neighbours`). У `by_neighbours` с соседями той же версии фраза другая
    (`carried_view_words`): позиция 16 и `u43` переносятся от донора как есть. Условие «позиции 16 нет»
    (`class_of` — `None`, версии 10 и 13) несущее: без него отчёт говорил бы о позиции, которой нет.
    """
    version = version_of(block)
    if version == 16 or class_of(block) is None:
        return None
    return (f"позиция 16 — как у {whose} ({_raw_view(block)}), u43 — тоже: {UNMEASURED}, и "
            f"приводить позицию к большинству формы {version} значило бы утверждать вид, "
            f"которого никто не видел, — set_view форме {version} отказывает тем же доводом")


def put_raw_view(element, donor):
    """Позиция 16 общего блока и `u43` свойств поля ввода НЕ версии 16 — от `donor` как есть: имена
    изменённых.

    Так оформление по соседям (`by_neighbours`) переносит у поля формы 15 сочетание целиком: оно
    выбирается по большинству соседей вместе с позицией 16 как есть (`view_of`); без переноса новое поле
    получило бы сочетание, которого у соседей нет. Это копия чужого сырого значения, а не утверждение вида. Соседи той же
    версии, поэтому позиция у них под одним ключом (`u16` кодом у версии 15).
    """
    target, source = block_of(element), block_of(donor)
    keys, theirs = list(target), list(source.values())
    changed = []
    if len(keys) > VIEW_POSITION and len(theirs) > VIEW_POSITION:
        key = keys[VIEW_POSITION]
        if _line(target[key]) != _line(theirs[VIEW_POSITION]):
            target[key] = copy.deepcopy(theirs[VIEW_POSITION])
            changed.append(NAMES[VIEW_POSITION])
    mine, other = _textbox_props(element) or {}, _textbox_props(donor) or {}
    if TEXTBOX_U43 in mine and TEXTBOX_U43 in other and \
            _line(mine[TEXTBOX_U43]) != _line(other[TEXTBOX_U43]):
        mine[TEXTBOX_U43] = copy.deepcopy(other[TEXTBOX_U43])
        changed.append(TEXTBOX_U43)
    return changed


def carried_view_words(block, donor):
    """Фраза отчёта `by_neighbours` у поля ввода не версии 16, когда позиция 16 и `u43` взяты у
    соседа-донора как есть (`put_raw_view`).
    """
    version = version_of(block)
    return (f"позиция 16 и u43 — как у соседа {donor!r}, чьё сочетание взято ({_raw_view(block)}): "
            f"копия его сырых значений, как у like, — позиция 16 входит в сочетание формы "
            f"{version} как есть, и своя позиция дала бы новому полю сочетание, которого у "
            f"соседей нет; вид при этом не утверждается: {UNMEASURED} — set_view форме {version} "
            "отказывает тем же доводом")


def _raw_view(block):
    """Позиция 16 поля ввода кодом строкой («1», «0»); `None` — позиции нет (версии 10 и 13)."""
    values = _values(block)
    code = view_code(values[VIEW_POSITION]) if len(values) > VIEW_POSITION else None
    return None if code is None else _line(code)


def resave_words(version):
    """Дорога формы не версии 16 к одному виду — одна у отказа `set_view` и у раскола `design`: вид
    проверен у версии 16, а пересохранение в 8.3.27 поднимает форму до неё.
    """
    lifted = "" if version == 10 else f"; подъём формы {version} пересохранением не проверялся"
    survive = ("; поля с позицией 16 = 1, судя по образцам форм, переживают подъём (вид 8.2)"
               if version == 15 else "")
    return (f"дорога — пересохранение в конфигураторе: 8.3.27 поднимает форму до 16 ({X19C}"
            f"{lifted}){survive} — и после пересохранения форму выравнивает set_view")


def put_u43(block, props_block):
    """`u43` поля ввода — правилом платформы: `["u43"]`, если изменился, иначе `[]`."""
    want = u43_rule(block)
    if want is None or not isinstance(props_block, dict) or TEXTBOX_U43 not in props_block:
        return []
    if props_block[TEXTBOX_U43] == want:
        return []
    props_block[TEXTBOX_U43] = want
    return [TEXTBOX_U43]


def put_class(block, view):
    """Вид `view` («8.2»/«8.3») общему блоку поля ввода: имена изменённых позиций.

    Вид того же класса не трогается (0 и 2 — один вид 8.3). Новый пишется кодом `VIEW_WRITTEN`, а
    позиция 17, если стояла 1, становится 0: 17 = 1 бывает только при 16 = 2. `u43` — отдельно
    (`put_u43`): он зависит и от ЦветаРамки.
    """
    keys = list(block) if isinstance(block, dict) else []
    if len(keys) <= VIEW_POSITION or class_of(block) == view:
        return []
    key = keys[VIEW_POSITION]
    code = VIEW_WRITTEN[view]
    # Под именем карты — имя значения; под запасным ключом (имя снято демоцией) — число.
    block[key] = _view_value(code) if key == VIEW else code
    changed = [VIEW]
    if len(keys) > HIDDEN[1] and block[keys[HIDDEN[1]]] == 1 and code != 2:
        block[keys[HIDDEN[1]]] = 0
        changed.append(NAMES[HIDDEN[1]])
    return changed


def carried(kind):
    """Позиции общего блока, которые оформление по соседям переносит от донора: сочетание и, у поля
    выбора и кнопки, скрытые позиции (`RAW_VIEW`, `HIDDEN_CARRIED`). Вид поля ввода не переносится,
    а пишется (`put_class`).
    """
    return POSITIONS + (HIDDEN if kind in RAW_VIEW or kind in HIDDEN_CARRIED else ())


def _props(element, kind=None):
    """Блок свойств, где лежит спутник позиции 16 (`MATES`), либо `None`."""
    trail = MATES.get(kind or element.get("type"), ((), None))[0]
    node = element
    for key in trail:
        node = node.get(key) if isinstance(node, dict) else None
    return node if trail and isinstance(node, dict) else None


def _textbox_props(element):
    return _props(element, "TextBox")


def mate_of(element):
    """`(ключ спутника, значение строкой или None)` у поля ввода и поля выбора, иначе `None`."""
    kind = element.get("type")
    if kind not in MATES:
        return None
    key = MATES[kind][1]
    block = _props(element) or {}
    return key, (_line(block[key]) if key in block else None)


def view_of(element):
    """ВИД элемента — хвост сочетания: у поля ввода версии 16 `(("вид", «8.2»|«8.3»|None),)`, у поля
    ввода другой версии — позиция 16 как есть (`(("u16", "1"),)`; вид там не проверялся), у поля
    выбора — тройка скрытых позиций как есть (16, 17 и `L1+17`), у прочих типов — `None`.
    """
    kind = element.get("type")
    if kind == "TextBox":
        block = block_of(element)
        if version_of(block) != 16:
            return ((NAMES[VIEW_POSITION], _raw_view(block)),)
        return ((VIEW_WORD, class_of(block)),)
    if kind in RAW_VIEW:
        values = _values(block_of(element))
        return tuple((NAMES[p], _line(values[p]) if p < len(values) else None)
                     for p in HIDDEN) + (mate_of(element),)
    return None


VIEW_NAMES = frozenset({VIEW_WORD} | {NAMES[p] for p in HIDDEN} | {MATES["ComboBox"][1]})


def combo(element):
    """Сочетание оформления элемента: `((имя, значение строкой), …)` или `None` без блока.

    Позиции берутся ПО МЕСТУ, а не по ключу: ключ у позиции бывает запасным (`u2` вместо
    `back_color`, когда значение снято демоцией), а место одно у всех версий. У поля ввода и поля
    выбора в хвосте — вид (`view_of`), у рамки группы — её рамка.
    """
    block = block_of(element)
    if block is None:
        return None
    kind = element.get("type")
    values = list(block.values())
    out = tuple((NAMES[p], _line(values[p]) if p < len(values) else None) for p in POSITIONS)
    view = view_of(element)
    if view is not None:
        out += view
    if kind == "GroupBox":
        out += ((GROUP_BORDER, _line(_group_border(element))),)
    return out


def view_words(view):
    """Вид словами: у поля ввода «8.2» (у поля ввода не версии 16 — код позиции 16: «1»), у поля
    выбора «u16=0, u17=0, L1+17=2»."""
    if not view:
        return "—"
    if len(view) == 1 and view[0][0] == NAMES[VIEW_POSITION]:
        return str(view[0][1])
    return ", ".join(str(value) if name == VIEW_WORD else f"{name}={value}"
                     for name, value in view)


def _raw_kind(kind, version):
    """Поле ввода не версии 16: вид у него не проверялся, хвост сочетания — позиция 16 как есть."""
    return kind == "TextBox" and version != 16


def hidden_words(names, kind):
    """Имена изменённых или различающихся полей и, если среди них вид, — что он означает."""
    listed = ", ".join(names)
    if kind == "TextBox" and NAMES[VIEW_POSITION] in names and VIEW_WORD not in names:
        return f"{listed} (позиция 16: {UNMEASURED})"
    if any(name in VIEW_NAMES or name in (VIEW, TEXTBOX_U43) for name in names):
        what = "вид — позиция 16 (`view`) и производное u43" if kind == "TextBox" \
            else "u16, u17 и спутник — скрытые позиции"
        listed += f" ({what}: {VIEW_NOTES[kind]})"
    return listed


def _put_mate(element, donor):
    """Спутник позиции 16 `donor` → `element`: `[его ключ]`, если изменился, иначе `[]`."""
    mine, theirs = _props(element) or {}, _props(donor) or {}
    key = MATES[element.get("type")][1]
    if key in mine and key in theirs and _line(mine[key]) != _line(theirs[key]):
        mine[key] = copy.deepcopy(theirs[key])
        return [key]
    return []


def put_combo(element, donor):
    """Оформление `donor` → `element` (тот же тип и та же версия): имена изменённых полей.

    Вид поля ввода здесь не переносится — его пишет `put_class`, а `u43` — `put_u43`."""
    target, source = block_of(element), block_of(donor)
    kind = element.get("type")
    wanted = carried(kind)
    keys, theirs = list(target), list(source.items())
    changed = []
    rebuilt = []
    for position, key in enumerate(keys):
        if position in wanted and position < len(theirs):
            their_key, their_value = theirs[position]
            if _line(target[key]) != _line(their_value) or key != their_key:
                changed.append(NAMES[position])
            rebuilt.append((their_key, copy.deepcopy(their_value)))
        else:
            rebuilt.append((key, target[key]))
    target.clear()
    target.update(rebuilt)
    if kind in RAW_VIEW:
        changed += _put_mate(element, donor)
    if kind == "GroupBox":
        border, theirs_border = _group_border(element), _group_border(donor)
        if isinstance(border, dict) and isinstance(theirs_border, dict) \
                and _line(border) != _line(theirs_border):
            border.clear()
            border.update(copy.deepcopy(theirs_border))
            changed.append(GROUP_BORDER)
    return changed


def neighbours(doc, kind, version):
    """Соседи того же типа и той же версии общего блока: `[(имя, узел, сочетание)]`."""
    out = []
    for name, element in elements(doc):
        if element.get("type") != kind:
            continue
        if version_of(block_of(element)) != version:
            continue
        found = combo(element)
        if found is not None:
            out.append((name, element, found))
    return out


def neighbour_font(doc, kind, nodes):
    """Описание шрифта НОВОГО элемента типа `kind` (`Label`, `CheckBox`), каким его сделает
    `by_neighbours` среди соседей `nodes`: сочетание большинства (при равенстве — у стоящего раньше), шрифт
    донора по `textwidth.element_font`; соседей той же версии нет — шрифт шаблона (`Auto` — шрифт
    формы). Одно место для генерации: она считает ширины до того, как `add_element` оформит узлы.
    """
    from . import templates, textwidth
    template = templates.element(kind)
    version = version_of(block_of(template))
    same = [(e, combo(e)) for e in nodes if e.get("type") == kind and version_of(block_of(e)) == version and combo(e) is not None]
    if not same:
        return textwidth.element_font(template, doc)
    counts = collections.Counter(found for _e, found in same)
    top = max(counts.values())
    chosen = next(found for found in counts if counts[found] == top)
    donor = next(e for e, found in same if found == chosen)
    return textwidth.element_font(donor, doc)


# ── Вид формы и вид конфигурации ─────────────────────────────────────────────────

def form_views(doc, version):
    """Виды своих полей ввода формы этой версии общего блока: счётчик «8.2»/«8.3»."""
    return collections.Counter(
        view for _n, element in elements(doc)
        if element.get("type") == "TextBox" and version_of(block_of(element)) == version
        for view in (textbox_view(element),) if view is not None)


def views_words(counts):
    """«8.2 — 8, 8.3 — 5» — по убыванию."""
    return ", ".join(f"{view} — {n}" for view, n in counts.most_common()) or "полей нет"


def _pool_views(combos, own=None):
    """Виды полей ввода 16 в своде (`pool["combos"]`), за вычетом сводки формы `own`."""
    counts = collections.Counter()
    for found, n in (combos.get(("TextBox", 16)) or {}).items():
        view = dict(found).get(VIEW_WORD) if found else None
        if view in VIEWS:
            counts[view] += n
    for kind, version, _name, found in (own or {}).get("elements") or ():
        view = dict(found).get(VIEW_WORD) if kind == "TextBox" and version == 16 and found \
            else None
        if view in VIEWS:
            counts[view] -= 1
    return +counts


def config_view(siblings, own=None):
    """Вид конфигурации: `(вид или None, счётчик видов полей ввода 16 у соседних форм)`.

    Соседи — свод `pool` (прочие формы конфигурации или обработки; `own` — сводка формы, если она в
    своде). Вид — вид БОЛЬШИНСТВА полей ввода версии 16; при равенстве видов и при отсутствии полей — `None`.
    """
    if siblings is None:
        return None, collections.Counter()
    counts = _pool_views(siblings.get("combos") or {}, own)
    top = counts.most_common(2)
    if not top or (len(top) == 2 and top[0][1] == top[1][1]):
        return None, counts
    return top[0][0], counts


def _config_words(siblings, version, config, theirs):
    if siblings is None:
        return "вид конфигурации не спрашивали: соседних форм не дали (--siblings)"
    if version != 16:
        return f"вид конфигурации считается по полям ввода версии 16, а здесь версия {version}"
    if config is None:
        return ("у соседних форм преобладающего вида нет: " + views_words(theirs)
                if theirs else "у соседних форм полей ввода версии 16 нет")
    return f"у полей ввода соседних форм {views_words(theirs)}"


PREFER_WHY = {"шаблона": " — так новое поле пишет конфигуратор 8.3.27"}


def choose_view(mine, config, prefer):
    """Правило вида нового поля ввода — одно на редактор и на проверку корпуса: `(вид, дорога)`.

    `mine` — счётчик видов полей ввода формы, `config` — вид конфигурации (или `None`), `prefer` —
    собственный вид того, что встаёт (шаблона, узла, соседа `like`). Дороги:

    * «вид формы» — форма однородна: новое поле не раскалывает её;
    * «вид конфигурации …» — форма смешанная или полей ввода в ней нет, а соседние формы дали вид;
    * «вид большинства формы» — смешанная, соседних форм не дали (или вида у них нет); шаблон чаще
      промахнулся бы;
    * «виды поровну» — большинства нет: собственный вид (`prefer`);
    * «вид шаблона» — полей ввода нет ни в форме, ни у соседей: собственный вид.
    """
    if len(mine) == 1:
        return next(iter(mine)), "вид формы"
    if config is not None:
        return config, ("вид конфигурации — форма смешанная" if mine
                        else "вид конфигурации — полей ввода нет")
    if mine:
        top = mine.most_common(2)
        if top[0][1] > top[1][1]:
            return top[0][0], "вид большинства формы"
        return prefer, "виды поровну"
    return prefer, "вид шаблона"


def target_view(doc, version, prefer, whose, siblings=None):
    """Вид нового поля ввода: `(вид, откуда словами)` — правило `choose_view` на этой форме."""
    mine = form_views(doc, version)
    config, theirs = config_view(siblings) if version == 16 else (None, collections.Counter())
    view, road = choose_view(mine, config, prefer)
    about = _config_words(siblings, version, config, theirs)
    if road == "вид формы":
        return view, f"вид формы — все {mine[view]} полей ввода формы вида {view}"
    if road.startswith("вид конфигурации"):
        head = f"форма смешанная ({views_words(mine)})" if mine else "полей ввода в форме нет"
        return view, (f"{head} — взят вид конфигурации: {about}"
                      + ("; выровнять форму — set_view" if mine else ""))
    if road == "вид большинства формы":
        return view, (f"форма смешанная ({views_words(mine)}) — взят вид большинства формы "
                      f"({about}); выровнять форму — set_view")
    if road == "виды поровну":
        return view, (f"форма смешанная, виды поровну ({views_words(mine)}) — взят вид {whose} "
                      f"({view}){PREFER_WHY.get(whose, '')} ({about}); выровнять форму — set_view")
    return view, (f"полей ввода в форме нет — вид {whose} ({view}){PREFER_WHY.get(whose, '')} "
                  f"({about})")


def apply_view(doc, node, whose, siblings=None):
    """Вид формы НОВОМУ полю ввода, чьё оформление не правится по соседям (`design=template`, узел из
    другой формы без `design=neighbors`): фраза отчёта или `None` у прочих типов.
    """
    block = block_of(node)
    mine = class_of(block) if node.get("type") == "TextBox" else None
    if mine is None:
        return None
    kept = kept_words(block, whose)
    if kept:
        return f"вид не пишется: {kept}"
    view, how = target_view(doc, version_of(block), mine, whose, siblings)
    changed = put_class(block, view) + put_u43(block, _textbox_props(node))
    return (f"вид — {view}: {how}" + (f"; от {whose} отличаются {', '.join(changed)}"
                                     if changed else "") + f"; {VIEW_NOTES['TextBox']}")


def _majority_view(same, prefer=None, whose="шаблона"):
    """Вид большинства соседей (у поля выбора — тройкой как есть): `(вид, у скольких, всего,
    слова о равенстве или None)`.

    Равенство решается в пользу `prefer` — собственного вида того, что встаёт, если он среди поделивших
    первое место; иначе — вид соседа, стоящего в форме раньше.
    """
    views = collections.Counter(view_of(element) for _n, element, _c in same)
    top = max(views.values())
    leaders = [view for view in views if views[view] == top]
    if len(leaders) == 1:
        return leaders[0], top, len(same), None
    chosen = prefer if prefer in leaders else leaders[0]
    how = f"взят вид {whose} (свой){PREFER_WHY.get(whose, '')}" \
        if chosen == prefer else "взят вид соседа, стоящего в форме раньше"
    return chosen, top, len(same), f"виды поровну — по {top} у каждого из {len(leaders)} видов, {how}"


def by_neighbours(doc, node, whose="шаблона", siblings=None):
    """Оформление нового узла — по соседям того же типа и версии.

    Возвращает фразу отчёта; узел правится на месте. Соседи другой версии не в счёт (шрифт между
    поколениями не переносится), и отчёт это говорит — и когда соседей той же версии нет вовсе, и
    когда часть соседей отброшена. `whose` — чьё оформление правится: шаблона либо узла из другой
    формы (`design=neighbors`).

    У ПОЛЯ ВВОДА вид — свойство формы: сначала вид (`target_view`: вид формы, у смешанной —
    конфигурации, `siblings`), потом самое частое сочетание среди соседей этого вида; вид пишется
    `put_class`, `u43` — правилом платформы. У ПОЛЯ ВЫБОРА выбор идёт в два шага по тройке
    скрытых позиций: сначала берётся вид большинства соседей, потом сочетание среди соседей этого вида.
    У КНОПКИ скрытые позиции переносятся от донора, и большинство по ним не считается (`HIDDEN_CARRIED`).
    У поля ввода НЕ версии 16 вида нет, а позиция 16 входит в сочетание как есть: берётся сочетание,
    которое у большинства соседей, и донор отдаёт также позицию 16 и `u43` (`put_raw_view`).
    """
    kind = node.get("type")
    block = block_of(node)
    version = version_of(block)
    if version is None:
        return f"общего блока оформления у элемента нет — оформление {whose}"
    same = neighbours(doc, kind, version)
    alien = collections.defaultdict(list)
    for name, element in elements(doc):
        other = version_of(block_of(element)) if element.get("type") == kind else None
        if other is not None and other != version:
            alien[other].append(str(name))
    view = class_of(block) if kind == "TextBox" else None
    said_view = ""
    before = (_textbox_props(node) or {}).get(TEXTBOX_U43)
    kept = kept_words(block, whose) if kind == "TextBox" else None
    if kept:
        # Поле ввода не версии 16: вид не выбирается и классом не пишется. Если соседи есть,
        # сочетание берётся целиком вместе с позицией 16 и `u43` донора (`put_raw_view`); если соседей нет,
        # позиция 16 и `u43` остаются такими, как у узла.
        view, said_view = None, f"; вид не пишется: {kept}"
    if view is not None:
        view, how = target_view(doc, version, view, whose, siblings)
        said_view = f"; вид — {view}: {how}; {VIEW_NOTES[kind]}"
        same = [row for row in same if textbox_view(row[1]) == view]
    elif kind in RAW_VIEW and same:
        raw, top_view, total, tie = _majority_view(same, prefer=view_of(node), whose=whose)
        said_view = (f"; вид по скрытым позициям — {view_words(raw)}: у {top_view} из {total}"
                     + (f" ({tie})" if tie else "") + f"; {VIEW_NOTES[kind]}")
        same = [row for row in same if view_of(row[1]) == raw]
    if not same:
        changed = []
        if view is not None:
            changed = put_class(block, view) + put_u43(block, _textbox_props(node))
        tail = (f"; от {whose} отличаются {', '.join(changed)}" if changed else "") + said_view
        if alien and not neighbours(doc, kind, version):
            return (f"соседи того же типа ({kind}) есть, но другой версии общего блока "
                    f"({', '.join(map(str, sorted(alien)))}), а у {whose} — {version}: оформление "
                    "между версиями не переносится (запись шрифта у версии 10 — шестая, у прочих — "
                    f"седьмая) — оформление {whose}"
                    + tail)
        return f"соседей того же типа ({kind}) в форме нет — оформление {whose}" + tail
    counts = collections.Counter(found for _n, _e, found in same)
    top = max(counts.values())
    leaders = [found for found in counts if counts[found] == top]
    # Равенство решает порядок: сочетание соседа, который в форме идёт раньше, — `counts` помнит порядок
    # первого появления, а `same` идёт сверху вниз.
    chosen = leaders[0]
    donor = next(element for _n, element, found in same if found == chosen)
    names = [name for name, _e, found in same if found == chosen]
    changed = put_combo(node, donor)
    if view is not None:
        changed += put_class(block, view)
        put_u43(block, _textbox_props(node))
        if (_textbox_props(node) or {}).get(TEXTBOX_U43) != before:
            changed.append(TEXTBOX_U43)
    elif kept:
        changed += put_raw_view(node, donor)
        said_view = f"; вид не пишется: {carried_view_words(block, names[0])}"
    who = ", ".join(str(name) for name in names[:5]) + (" …" if len(names) > 5 else "")
    head = (f"оформление — по соседям того же типа: сочетание {top} из {len(same)} ({who})"
            + (f"; сочетания поровну — {len(leaders)} по {top}, взято у стоящего в форме раньше"
               if len(leaders) > 1 else ""))
    if alien:
        head += ("; соседи другой версии общего блока не в счёт (оформление между версиями не "
                 "переносится): " + "; ".join(
                     f"{v} — {', '.join(n[:5])}{' …' if len(n) > 5 else ''}"
                     for v, n in sorted(alien.items())))
    words = ", ".join(changed)
    if kind in HIDDEN_CARRIED and any(name in VIEW_NAMES for name in changed):
        words += (" (u16, u17 — скрытые позиции: у кнопки они переносятся от соседа, чьё оформление "
                  f"взято, и вид по ним не определяется: {VIEW_NOTES[kind]})")
    return head + (f"; от {whose} отличаются {words}" if changed
                   else f"; оно совпало с оформлением {whose}") + said_view


def like_view(doc, node, like, siblings=None):
    """Вид копии поля ввода по образцу соседа — вид ФОРМЫ (`target_view`); фраза или `None`.

    Сосед того вида, что у формы, копируется как есть; при равенстве видов — тоже. Сосед ДРУГОГО вида —
    копия получает вид формы, а с ним и оформление (позиции 2–11) самого частого сочетания полей
    этого вида: копия с оформлением соседа и чужим видом дала бы сочетание, которого в форме нет.
    """
    block = block_of(node)
    mine = class_of(block) if node.get("type") == "TextBox" else None
    if mine is None:
        return None
    kept = kept_words(block, f"соседа {like!r}")
    if kept:
        # Форма 15: копия несёт свои позицию 16 и u43, как у образца: вид у 15 не проверялся, и
        # `set_view` форме 15 отказывает.
        return f"вид не пишется: {kept}"
    version = version_of(block)
    view, how = target_view(doc, version, mine, f"соседа {like!r}", siblings)
    if view == mine:
        return f"вид — {view}: {how}" if len(form_views(doc, version)) > 1 else None
    before = (_textbox_props(node) or {}).get(TEXTBOX_U43)
    same = [row for row in neighbours(doc, "TextBox", version) if textbox_view(row[1]) == view]
    said = ""
    changed = []
    if same:
        counts = collections.Counter(found for _n, _e, found in same)
        top = max(counts.values())
        chosen = next(found for found in counts if counts[found] == top)
        donor = next(element for _n, element, found in same if found == chosen)
        names = [str(name) for name, _e, found in same if found == chosen]
        changed = put_combo(node, donor)
        said = (f"; оформление — полей вида {view} (сочетание {top} из {len(same)}: "
                f"{', '.join(names[:5])}{' …' if len(names) > 5 else ''}): копия с оформлением "
                "соседа и чужим видом дала бы сочетание, которого в форме нет ни у одного поля")
    changed += put_class(block, view)
    put_u43(block, _textbox_props(node))
    if (_textbox_props(node) or {}).get(TEXTBOX_U43) != before:
        changed.append(TEXTBOX_U43)
    return (f"вид — {view}: {how}; у {like!r} был {mine}{said}; от соседа отличаются "
            f"{', '.join(changed)}; {VIEW_NOTES['TextBox']}")


def hidden_pairs(doc):
    """Пары (позиция 16, спутник) у полей ввода и выбора формы и вложенных элементов колонок:
    `[(чьё словами, тип, версия, (16, спутник))]` — только у версий, где позиция 16 есть."""
    out = []
    for name, element in elements(doc):
        kind = element.get("type")
        if kind in MATES:
            out += _pair_of(f"{kind} {name!r}", kind, block_of(element), _props(element))
        for column, nested_kind, block in nested_blocks(element):
            if nested_kind in MATES:
                parent = _parent_of(element, block)
                out += _pair_of(f"вложенный {nested_kind} колонки {column!r} у {name!r}",
                                nested_kind, block, parent)
    return out


def _pair_of(who, kind, block, props_block):
    values = _values(block)
    key = MATES[kind][1]
    if len(values) <= 16 or not isinstance(props_block, dict) or key not in props_block:
        return []
    u16 = view_code(values[16]) if kind == "TextBox" else values[16]
    mate = props_block[key]
    if not (_int(u16) and _int(mate)):
        return []
    return [(who, kind, version_of(block), (u16, mate))]


def _parent_of(node, target):
    """Словарь, у которого `target` — значение (обход вглубь по словарям и спискам)."""
    stack = [node]
    while stack:
        here = stack.pop()
        values = here.values() if isinstance(here, dict) else here
        for value in values:
            if value is target:
                return here if isinstance(here, dict) else None
            if isinstance(value, (dict, list)):
                stack.append(value)
    return None


def pair_words(who, kind, version, pair):
    """Слова `validate` о паре (16, спутник), которой нет у корпуса форм."""
    source = CORPUS_TEXTBOX_U16_U43 if kind == "TextBox" else CORPUS_COMBOBOX_U16_MATE
    counts = source.get(version) or {}
    lab = LAB_PAIRS.get((kind, version)) or {}
    listed = ", ".join(f"({a}, {b}) — {_n(counts[(a, b)])}" for a, b in sorted(counts))
    listed += "".join(f"; ({a}, {b}) — подтверждено {copy_}" for (a, b), copy_ in lab.items())
    mate = MATES[kind][1]
    view = (f" (вид {VIEW_CLASS[pair[0]]})"
            if kind == "TextBox" and version == 16 and pair[0] in VIEW_CLASS else "")
    # У поля ввода фраза начинается идентификатором `u43` — его заглавной не пишут.
    how = (f"{U43_WORDS}, и при сохранении она перепишет его" if kind == "TextBox"
           else "Спутник ходит с позицией 16 жёстко, и такую пару "
                "собирают правкой одной из двух")
    return (f"{who}: пара скрытых позиций (16, {mate}) = ({pair[0]}, {pair[1]}){view} — такой пары "
            f"нет у элементов этого "
            f"типа версии {version} (у своих: {listed}). {how}; {VIEW_NOTES[kind]}")


# ── Сверка с формами системы ─────────────────────────────────────────────────────────────────

# Шум сверки на корпусе — соседи каждой формы: прочие формы её конфигурации
# (`compare(minus=True)`). Форм с соседями и предупреждений по видам; «вид» — поля ввода 16 формы не
# все того вида, что у конфигурации.
SIBLINGS_FORMS = 4983
SIBLINGS_NOISE = {"версия": 1770, "стиль": 285, "тип": 5012, "элемент": 871, "вид": 140}
SIBLINGS_PAIRS = 24289  # пар «форма, тип», у которых соседи той же версии есть


def style_of(doc):
    """GUID объекта стиля формы или `None` («Авто»)."""
    from . import edit
    block = doc.get(edit.STYLE_BLOCK) if isinstance(doc, dict) else None
    value = block.get(edit.STYLE) if isinstance(block, dict) else None
    return value.get("guid") if isinstance(value, dict) else None


def summary(doc):
    """Сводка оформления формы — то, что сверяется с соседями. Сериализуема (для пула)."""
    return {"version": form_version(doc), "style": style_of(doc),
            "elements": [(element.get("type"), version_of(block_of(element)), name,
                          combo(element)) for name, element in elements(doc)
                         if block_of(element) is not None]}


def read_summary(path):
    """Сводка формы с диска: `(путь, сводка)` либо `(путь, None)`, если форму не прочесть."""
    from . import formsource, typed
    try:
        return str(path), summary(typed.decode(formsource.read_form_node(pathlib.Path(path))))
    except (ValueError, OSError):
        return str(path), None


def read_siblings(root, mine=()):
    """Соседи из каталога выгрузки: `(пути, непрочитанные, свод)` — все `*.frm` под `root` и все `Form.bin`, рядом с которыми
    `form.frm` нет (они читаются в памяти), кроме путей `mine` (сама форма). Читаются пулом процессов, когда их больше двадцати: у конфигурации
    тысячи форм."""
    import os
    root = pathlib.Path(root)
    if not root.is_dir():
        raise ValueError(f"каталога соседей нет: {root}")
    from . import formsource
    paths = formsource.sibling_paths(root, mine)
    if len(paths) > 20:
        import concurrent.futures
        with concurrent.futures.ProcessPoolExecutor(
                max_workers=max(1, (os.cpu_count() or 2) - 2)) as workers:
            read = list(workers.map(read_summary, paths, chunksize=8))
    else:
        read = [read_summary(p) for p in paths]
    lost = [p for p, s in read if s is None]
    return paths, lost, pool(s for _p, s in read)


def _style_words(guid):
    return "Авто (стиля нет)" if guid is None else f"GUID {guid}"


def _majority(counter):
    top = max(counter.values())
    return top, [key for key, n in counter.items() if n == top]


def _combo_words(left, right, kind):
    """Какие поля двух сочетаний разные: имена через запятую, и если среди них вид — чего он
    стоит (`hidden_words`)."""
    return hidden_words([name for (name, a), (_n, b) in zip(left, right) if a != b], kind) or "—"


def pool(summaries):
    """Свод сводок соседей: число форм, версии, стили и сочетания по `(тип, версия)`.

    Сверка идёт со СВОДОМ, а не со списком: у конфигурации тысячи форм, и сверять каждую с каждой
    значило бы пересчитывать один свод тысячи раз. Форму из свода вычитает `compare(minus=True)`.
    """
    out = {"forms": 0, "versions": collections.Counter(), "styles": collections.Counter(),
           "combos": collections.defaultdict(collections.Counter)}
    for s in summaries:
        if s is None:
            continue
        out["forms"] += 1
        out["versions"][s["version"]] += 1
        out["styles"][s["style"]] += 1
        for kind, version, _name, found in s["elements"]:
            out["combos"][(kind, version)][found] += 1
    return out


def _top(counter, own=None):
    """`(наибольшее, [ключи с ним], всего)` у счётчика за вычетом `own` (формы в своде)."""
    top, leaders, total = 0, [], 0
    for key, n in counter.items():
        n -= (own or {}).get(key, 0)
        total += n
        if n > top:
            top, leaders = n, [key]
        elif n == top and n > 0:
            leaders.append(key)
    return top, leaders, total


def compare(form, siblings, minus=False):
    """Сверка сводки формы со сводом соседей (`pool`): `(строки сведений, предупреждения)`.

    `minus` — форма сама лежит в своде и вычитается из него. Вопросов пять: версия и стиль — у
    большинства ли; по каждому типу — есть ли сочетание каждого элемента у соседей той же версии
    вовсе, а если все есть — то ли самое частое; и вид полей ввода 16 — тот ли, что у конфигурации.
    Равенство у соседей засчитывается форме: большинство тогда — все, кто делит первое место.
    Предупреждение — пара `(вид, слова)`.
    """
    info, warnings = [], []
    forms = siblings["forms"] - (1 if minus else 0)
    if forms <= 0:
        return ["соседних форм нет — сверять не с чем"], []
    mine = collections.Counter([form["version"]]) if minus else None
    top, leaders, _total = _top(siblings["versions"], mine)
    info.append(f"соседей {forms}: версия " + ", ".join(
        f"{v} — {n - (mine or {}).get(v, 0)}" for v, n in siblings["versions"].most_common()
        if n - (mine or {}).get(v, 0) > 0))
    if form["version"] not in leaders:
        warnings.append(
            ("версия", f"версия общего блока формы — {form['version']}, а у большинства соседей "
                       f"{'/'.join(map(str, leaders))} ({top} из {forms}). В одной конфигурации "
                       "формы разных поколений — обычное дело, поэтому для ПРАВЛЕНОЙ формы это сведение; НОВУЮ форму "
                       f"собирают в версии большинства — и её элементы тоже ({X19C})"))
    mine = collections.Counter([form["style"]]) if minus else None
    top, leaders, _total = _top(siblings["styles"], mine)
    info.append("стиль: " + ", ".join(
        f"{_style_words(g)} — {n - (mine or {}).get(g, 0)}"
        for g, n in siblings["styles"].most_common() if n - (mine or {}).get(g, 0) > 0))
    if form["style"] not in leaders:
        warnings.append(
            ("стиль", f"стиль формы — {_style_words(form['style'])}, а у большинства соседей — "
                      f"{' / '.join(_style_words(g) for g in leaders)} ({top} из {forms}); вид "
                      "элементов решает стиль формы, и форма со своим стилем выглядит "
                      "иначе соседей при тех же записях элементов"))
    rows = collections.defaultdict(list)
    for kind, version, name, found in form["elements"]:
        rows[(kind, version)].append((name, found))
    for (kind, version), items in rows.items():
        own = collections.Counter(found for _n, found in items)
        top, their_top, total = _top(siblings["combos"].get((kind, version)) or {},
                                     own if minus else None)
        if total <= 0:
            info.append(f"{kind} (версия {version}): у соседей той же версии таких нет — "
                        "оформление сверить не с чем")
            continue
        info.append(f"{kind} (версия {version}): в форме {len(items)}, у соседей {total}, самое "
                    f"частое сочетание у соседей — у {top}")
        if kind in HIDDEN_KINDS and _measured(kind, version, _views(own)):
            theirs_views = _views(collections.Counter(
                {found: n - (own[found] if minus else 0)
                 for found, n in siblings["combos"][(kind, version)].items()}))
            raw = _raw_kind(kind, version)
            info.append(f"{kind} (версия {version}): {'позиция 16' if raw else 'вид'} в форме — "
                        f"{_views_words(_views(own))}; у соседей — "
                        f"{_views_words(+theirs_views)}" + (f" ({UNMEASURED})" if raw else ""))
        theirs = siblings["combos"][(kind, version)]
        absent = [(name, found) for name, found in items
                  if theirs.get(found, 0) - (own[found] if minus else 0) <= 0]
        if absent:
            names = ", ".join(str(name) for name, _f in absent[:5]) + \
                (" …" if len(absent) > 5 else "")
            warnings.append(
                ("элемент", f"{kind}: сочетания оформления у {names} нет ни у одного элемента того "
                            f"же типа и версии у соседей ({total}); с самым частым у соседей "
                            f"различаются {_combo_words(absent[0][1], their_top[0], kind)}"))
            continue
        _t, own_top = _majority(own)
        if not set(own_top) & set(their_top):
            warnings.append(
                ("тип", f"{kind}: самое частое сочетание оформления формы — не то, что у соседей "
                        f"той же версии ({top} из {total}); различаются "
                        f"{_combo_words(own_top[0], their_top[0], kind)}"))
    said = _view_against_config(form, siblings, minus)
    if said:
        info.append(said[0])
        if said[1]:
            warnings.append(("вид", said[1]))
    return info, warnings


def _measured(kind, version, views):
    """Есть ли что сказать о хвосте сочетания: у поля ввода версии 10 и 13 позиции 16 нет вовсе."""
    return not _raw_kind(kind, version) or any(value is not None for view in views
                                                for _name, value in view)


def _view_against_config(form, siblings, minus):
    """Вид полей ввода 16 формы против вида конфигурации: `(сведение, предупреждение или None)`
    либо `None`, если полей ввода 16 в форме нет."""
    mine = collections.Counter(
        dict(found).get(VIEW_WORD) for kind, version, _n, found in form["elements"]
        if kind == "TextBox" and version == 16 and found)
    mine = collections.Counter({view: n for view, n in mine.items() if view in VIEWS})
    if not mine:
        return None
    config, theirs = config_view(siblings, form if minus else None)
    about = _config_words(siblings, 16, config, theirs)
    line = f"вид конфигурации — {config or 'не определён'}: {about}"
    other = sum(n for view, n in mine.items() if view != config)
    if config is None or not other:
        return line, None
    return line, (f"поля ввода формы — {views_words(mine)}, а вид конфигурации — {config} "
                  f"({about}): стили 8.2 и 8.3 в одной форме не смешиваются, вид берётся тот, что "
                  f"преобладает в конфигурации, — форму ведут к "
                  f"виду конфигурации: set_view с --siblings (у НОВОЙ формы — сразу). Так у "
                  f"{_n(SIBLINGS_NOISE['вид'])} форм корпуса из {_n(SIBLINGS_FORMS)}; "
                  f"{VIEW_NOTES['TextBox']}")


def in_form(doc):
    """Сверка ВНУТРИ формы: `(строки сведений, предупреждения)` — смесь версий (и у вложенных
    элементов колонок), сочетания по типам, раскол вида (у поля ввода формы не версии 16 — раскол
    позиции 16: вид там не проверялся)."""
    version, alien = mixed(doc)
    info = [f"версия общего блока формы — {version}"]
    warnings = []
    if alien:
        warnings.append(("смесь", mix_words(version, alien)))
    nested = nested_mix(doc)
    if nested:
        warnings.append(("смесь у вложенных", nested_mix_words(version, nested)))
    kinds = collections.defaultdict(list)
    names = collections.defaultdict(list)
    for name, element in elements(doc):
        found = combo(element)
        if found is not None:
            kinds[element.get("type")].append(found)
            names[element.get("type")].append((name, version_of(block_of(element))))
    for kind, rows in kinds.items():
        counts = collections.Counter(rows)
        info.append(f"{kind}: {len(rows)}, сочетаний оформления {len(counts)}"
                    + (f" (самое частое — у {max(counts.values())})" if len(counts) > 1 else ""))
        # Вид — среди элементов версии формы: элемент другой версии назван смесью, а хвост его
        # сочетания другой (у поля ввода не 16 — позиция 16 как есть, `view_of`).
        same = [(name, found) for (name, own), found in zip(names[kind], rows)
                if own == version or version is None]
        views = _views(collections.Counter(found for _n, found in same))
        if kind in HIDDEN_KINDS and same and _measured(kind, version, views):
            # У поля ввода формы не версии 16 — позиция 16, а не вид.
            raw = _raw_kind(kind, version)
            info.append(f"{kind}: {'позиция 16' if raw else 'вид'} — {_views_words(views)}"
                        + (f" ({UNMEASURED})" if raw else ""))
            if len(views) > 1:
                warnings.append(("раскол позиции 16" if raw else "раскол вида",
                                 _split_words(kind, views, [n for n, _f in same],
                                              [f for _n, f in same], version)))
    nested = collections.defaultdict(collections.Counter)
    for _n, element in elements(doc):
        for _c, nested_kind, block in nested_blocks(element):
            if nested_kind == "TextBox":
                own = version_of(block)
                nested[own][class_of(block) if own == 16 else _raw_view(block)] += 1
    for own, views in sorted(nested.items(), key=lambda item: item[0] != 16):
        if own == 16:
            views.pop(None, None)
            if views:
                info.append(f"вложенные поля ввода колонок: вид — {views_words(views)} (вид "
                            "вложенного поля колонки платформой не проверялся"
                            + ("; set_view приводит и их)" if version == 16 else ")"))
            continue
        codes = "; ".join(f"{code} — {n}" for code, n in views.most_common() if code is not None)
        info.append(f"вложенные поля ввода колонок версии {own} ({sum(views.values())}): "
                    + (f"позиция 16 — {codes}" if codes else "позиции 16 нет")
                    + f" ({UNMEASURED}" + ("; set_view их не трогает)" if version == 16 else ")"))
    return info, warnings


def view_minority(doc):
    """Элементы меньшинства раскола вида (позиции 16 у поля выбора и у формы не версии 16): `{тип: [имена]}`; видов поровну — у типа записи нет
    (меньшинства нет), раскола нет — пусто. Те же элементы названы в тексте предупреждения `in_form`, но он обрезается линтером."""
    version = form_version(doc)
    kinds = collections.defaultdict(list)
    for name, element in elements(doc):
        found = combo(element)
        if found is not None and (version_of(block_of(element)) == version or version is None):
            kinds[element.get("type")].append((name, found))
    out = {}
    for kind, rows in kinds.items():
        views = _views(collections.Counter(found for _n, found in rows))
        if kind not in HIDDEN_KINDS or len(views) < 2 or not _measured(kind, version, views):
            continue
        top = views.most_common(2)
        if top[0][1] > top[1][1]:
            out[kind] = [str(name) for name, found in rows if _view_part(found) != top[0][0]]
    return out


def _split_words(kind, views, names, rows, version=16):
    """Слова «раскол вида»: кто не вида большинства — или виды поровну, и как редактор выбирает вид.

    У поля ввода формы не версии 16 это не раскол ВИДА, а разная позиция 16 (вид там не проверялся),
    и дорога другая: `set_view` такой форме отказывает, форму поднимает до 16 пересохранение в
    конфигураторе (`resave_words`).
    """
    top = views.most_common(2)
    listed = _views_words(views)
    raw = _raw_kind(kind, version)
    if top[0][1] > top[1][1]:
        minority = [str(name) for name, found in zip(names, rows) if _view_part(found) != top[0][0]]
        who = (f"{'позиция 16 не та, что у большинства' if raw else 'не вида большинства'}: "
               f"{', '.join(minority[:5])}{' …' if len(minority) > 5 else ''}")
    else:
        who = f"{'значения' if raw else 'виды'} поровну — по {top[0][1]}"
    if raw:
        return (f"{kind} (форма {version}): у полей ввода позиция 16 разная — {listed}; {who}"
                + f"; {UNMEASURED}, и set_view форме версии {version} отказывает; "
                  f"{resave_words(version)}")
    if kind == "TextBox":
        road = ("вид — свойство формы: новое поле редактор ставит в вид конфигурации (с "
                "--siblings), без соседних форм — в вид большинства формы, при равенстве — в свой; "
                "выровнять форму — set_view (view 8.2 или 8.3, либо вид конфигурации с --siblings)")
    else:
        road = ("новое поле редактор ставит в вид большинства соседей, при равенстве — в свой; "
                "вид поля выбора платформой не проверялся, и set_view его не трогает")
    return (f"{kind}: у элементов формы {len(views)} вида — {listed}; {who}. Поля "
            f"меньшинства нарисованы иначе соседей; {road}. "
            f"{VIEW_NOTES[kind][0].upper()}{VIEW_NOTES[kind][1:]}")


def _plural_forms(n):
    """«у N форм» — родительный падеж: «формы» только у 1, 21, 31…"""
    return f"{n} формы" if n % 10 == 1 and n % 100 != 11 else f"{n} форм"


def _view_part(found):
    return tuple(pair for pair in found if pair[0] in VIEW_NAMES)


def _views(combos):
    """Счётчик сочетаний → счётчик ВИДОВ (хвост сочетания)."""
    out = collections.Counter()
    for found, n in combos.items():
        out[_view_part(found)] += n
    return out


def _views_words(views):
    return "; ".join(f"{view_words(view)} — {n}" for view, n in views.most_common())


def mix_words(version, alien):
    """Слова о смеси версий в форме — одни у `validate` и у сверки."""
    listed = ", ".join(f"{name} ({kind}, {v})" for name, kind, v in alien[:5]) \
        + (" …" if len(alien) > 5 else "")
    return (f"у формы версия общего блока {version}, а у элементов {listed} — другая: смешанных "
            "форм не бывает (элементы той же версии, что форма). Платформа смесь переносит, а при пересохранении "
            f"поднимает всю форму до своей версии — {X19C}")


def _n(number):
    return f"{number:,}".replace(",", " ")
