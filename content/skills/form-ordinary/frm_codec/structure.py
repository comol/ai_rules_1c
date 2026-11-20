"""Структура формы: дерево областей, страниц, групп, разделов, рядов, пар и колонок (основа досье формы).

`recognize(doc)` разбирает форму детерминированно и без правок: каждый элемент с блоком координат
оказывается в дереве РОВНО ОДИН раз — в листе либо в списке `elements` составного узла (рамка группы,
раздел, панель, область содержимого с панелью команд). Элементы без блока координат (сырые) в дерево не идут:
их имена — в `Structure.raw`.

Роли узла (`Node.role`): `area` (вся форма, панель, многоколонная область), `page`, `group` (рамка с
содержимым), `section` (рамка-заголовок без содержимого и всё, что лежит под ней до следующей рамки), `top_bar`,
`bottom_bar`, `row`, `pair`, `column`, `content`, `buttons`, `single`, `unclear`.
Номер узла — буква и число: `A` — области (форма `A0`, панели, многоколонные области, шапка, подвал, области
содержимого), `T` — страницы, `G` — группы и разделы, `R` — ряды, `P<ряд>.<номер>` — пары, `C` — колонки,
`S` — одиночные элементы, `U` — неясные. Числа идут в порядке чтения.

Ход разбора:

1. Контейнеры: форма, панели и их страницы. Страница формы с номером 0 — её первая страница, как у `layout.hidden_page`
   (`docs/form-pages.md`): при двух и более страницах каждая, в том числе нулевая, — узел `T` (`caption` — подпись закладки);
   при одной страницы-узла нет. Рамка группы в записи не контейнер: в группу идёт всё, что целиком внутри рамки (смещения рамок
   друг в друга — по меньшей рамке).
2. Неясное: нулевой размер, выход за край родителя, перекрытие с другим видимым элементом ТОЙ ЖЕ страницы (элементы разных
   страниц друг с другом не сравниваются). Такой элемент — лист `unclear` с причиной словами и в ряды не идёт; рамка, ставшая
   неясной, сохраняет свои вложенные элементы детьми.
3. Раздел: рамка без вложенных элементов не выше `SECTION_H` — линия-заголовок раздела (в корпусе таких 88 % всех рамок).
   Надпись, лежащая на рамке, — её заголовок и входит в узел. Ряды и блоки под рамкой до следующей рамки, раздела или конца
   контейнера, середина которых по горизонтали внутри рамки, — дети раздела.
4. Панели команд: у верхнего и у нижнего края родителя — шапка и подвал, если панель видима и горизонтальна; вплотную над
   содержимым либо сбоку от него — часть его узла (над содержимым формы панель на всю ширину формы — не панель таблицы);
   скрытая и вертикальная панель вне содержимого — одиночный элемент. Элементы, целиком лежащие на видимой панели, — дети её узла.
5. Содержимое: табличное поле, поле документа и прочее крупное; картинка не больше `ICON_MAX` px по большей стороне — значок,
   одиночный элемент, а не содержимое.
6. Ряды: элементы, у которых верх различается не больше `patterns.ROW_DY`. Скрытый элемент в ряды не идёт: он одиночный лист
   с пометкой «скрыт». Пара: сначала «надпись слева» (`shell.find_label`, как у `describe`), затем «флажок слева» (`checkbox_field`),
   затем «надпись над полем» только у поля, не получившего пару, затем «подпись → значение» (`caption_value`, правая надпись
   с привязкой данных). Одно поле — в одной паре. Надпись под полем вплотную — подсказка к полю: одиночный элемент с `hint`.
   Флажок и переключатель без поля — пара сами с собой.
7. Колонки — по правилам `describe` (`rowgrid`): таблица, рамка, панель (и неясная, перекрытая другим элементом) или панель команд
   между рядами рвёт серию рядов из одних пар; подряд идущие ряды с одним числом пар — один блок. Блок из одного ряда одной пары — не колонка; из двух рядов и
   больше с одной парой — колонка; с двумя парами и больше — многоколонная область, если левые края пар по колонкам
   совпадают в пределах `place.COLUMN_DX`, иначе ряды остаются рядами. Последний неполный ряд, прилегающий к такому блоку и
   стоящий в первых его колонках, — часть блока. Номер ряда у пары — в номере (`P3.1` и `P3.2` — один ряд) и в `Node.row`.
8. Порядок чтения: контейнер режется вертикальным просветом на левую и правую стопки, если они стоят рядом по высоте
   (левая читается целиком раньше правой), иначе горизонтальным — на полосы сверху вниз; нечего резать — по `(верх, лево)`.

Размеры и места узла — в координатах родителя (формы или панели); у составного узла — объединение
дочерних. У колонки `field_left` — левый край полей её пар (ширина подписей — `field_left − box[0]`).
"""
import dataclasses

from . import layout, patterns, place, render, rowgrid, shell
from .edit import datapath

AREA, PAGE, GROUP, SECTION = "area", "page", "group", "section"
TOP_BAR, BOTTOM_BAR, ROW, PAIR = "top_bar", "bottom_bar", "row", "pair"
COLUMN, CONTENT, BUTTONS, SINGLE, UNCLEAR = "column", "content", "buttons", "single", "unclear"

ROLES = (AREA, PAGE, GROUP, SECTION, TOP_BAR, BOTTOM_BAR, ROW, PAIR, COLUMN, CONTENT, BUTTONS, SINGLE, UNCLEAR)
PREFIX = {AREA: "A", TOP_BAR: "A", BOTTOM_BAR: "A", CONTENT: "A", BUTTONS: "A", PAGE: "T", GROUP: "G", SECTION: "G",
          ROW: "R", PAIR: "P", COLUMN: "C", SINGLE: "S", UNCLEAR: "U"}
ROLE_WORDS = {AREA: "область", PAGE: "страница", GROUP: "группа", SECTION: "раздел", TOP_BAR: "шапка", BOTTOM_BAR: "подвал",
              ROW: "ряд", PAIR: "пара", COLUMN: "колонка", CONTENT: "содержимое", BUTTONS: "кнопки",
              SINGLE: "элемент", UNCLEAR: "неясно"}

LABEL_FIELD, CHECKBOX_FIELD, CAPTION_VALUE = "label_field", "checkbox_field", "caption_value"
PAIR_KINDS = (LABEL_FIELD, CHECKBOX_FIELD, CAPTION_VALUE)
KIND_WORDS = {LABEL_FIELD: "надпись и поле", CHECKBOX_FIELD: "флажок и поле", CAPTION_VALUE: "подпись и значение"}

CONTENT_TYPES = frozenset({"TableBox", "SpreadsheetDocumentField", "TextDocumentField", "HTMLDocumentField",
                           "PDFDocumentField", "Chart", "GanttChart", "Dendrogram", "PivotChart",
                           "GeographicalSchemaField", "GraphicalSchemaField", "PictureBox"})
FIELD_TYPES = frozenset({"TextBox", "ComboBox", "ListBox", "ProgressBar", "TrackBar"})  # поля, которым надпись — пара
SELF_PAIR_TYPES = frozenset({"CheckBox", "RadioButton"})  # у них своя надпись
FRAME, PANEL, BAR, BUTTON, LABEL, SPLITTER = "GroupBox", "Panel", "CommandBar", "Button", "Label", "Splitter"
CHECK, PICTURE = "CheckBox", "PictureBox"

ROW_DY = patterns.ROW_DY
COLUMN_DX = place.COLUMN_DX
PAIR_GAP = shell.MAX_LABEL_GAP   # зазор «надпись → поле» в ряду, px (правило `shell.find_label`)
UNIT_GAP = 6           # единица измерения стоит от поля не дальше стольких px справа
UNIT_SIGNS = frozenset({"х", "x", "×", "%", "г", "т", "л", "кг", "шт", "мм", "см", "руб", "грн", "коп"})   # единицы без точки
ABOVE_GAP = 4          # зазор «надпись над полем» по вертикали, px
ABOVE_OVERLAP = 1      # допустимое наползание надписи на поле сверху, px
EDGE = 6               # «прижата к краю»: не дальше стольких px от края родителя
BAR_GAP = 4            # панель команд вплотную к содержимому: зазор не больше стольких px
OVERLAP_MIN = 4        # перекрытие учитывается, если по обеим осям не меньше стольких px (меньшее — неточность в пикселях)
# Картинка не больше стольких px по большей стороне — значок. Порог по снимку 4 993 форм: из 3 163 картинок в областях содержимого
# 3 001 (95 %) не больше 40 px; между 40 и 48 px — всего 10 картинок, дальше по 25 и меньше на восьмерку (крупные начинаются с 48).
ICON_MAX = 40
# Рамка без вложенных элементов не выше стольких px — линия-заголовок раздела. По снимку: из 2 293 пустых рамок 2 037 имеют высоту
# 15–19 px (подпись раздела), 162 — до 10 px; выше 20 px пустых горизонтальных рамок единицы.
SECTION_H = 20
STACK_SHARE = 0.5      # стопки рядом: вертикальные размеры левой и правой пересекаются не меньше чем на эту долю меньшей
HOSTS = frozenset({BAR, LABEL, PICTURE})   # на них кладут другие элементы: полоса панели команд, подложка, картинка
MANY_NAMES = 3         # в причине перекрытия называется не больше стольких имён
CONTAINERS = frozenset({PANEL, BAR, SPLITTER, FRAME})
EDGE_TOLERANCE = 2     # выход за край родителя на столько px и меньше — неточность разметки, а не «неясно»
OVER_SHARE = 0.25      # мелкий элемент поверх контейнера: его площадь не больше этой доли площади контейнера


def _over_field(lab, field):
    """Надпись стоит над полем: их проекции по горизонтали пересекаются не меньше чем на половину меньшей (надпись шире поля или смещена на несколько px,
    как «Год», «Месяц», «День» над полями соседнего ряда, — одно и то же отношение, а не «совпал левый край на 2 px»)."""
    common = min(lab.box[2], field.box[2]) - max(lab.box[0], field.box[0])
    narrow = min(lab.box[2] - lab.box[0], field.box[2] - field.box[0])
    return narrow > 0 and common * 2 >= narrow


def is_unit_text(text):
    """Текст надписи — единица измерения или знак между полями: до четырёх знаков с точкой в конце («дн.», «ч.», «мин.») либо знак из `UNIT_SIGNS` («х», «%», «кг»)."""
    text = text.strip()
    return bool(text) and (text.casefold() in UNIT_SIGNS or (len(text) <= 4 and text.endswith(".") and text[:-1].isalpha()))


@dataclasses.dataclass
class Node:
    id: str
    role: str
    box: tuple
    elements: list
    children: list
    reason: str = None
    holder: str = None
    page: int = 0
    kind: str = None          # у пары: `label_field`, `checkbox_field`, `caption_value` (флажок или переключатель сами по себе — `None`)
    row: int = None           # у пары: номер её ряда (тот же, что в номере `P<ряд>.<номер>`)
    field_left: float = None  # у колонки: левый край полей её пар
    caption: str = None       # у страницы: подпись закладки
    hint: str = None          # у надписи под полем вплотную: номер узла поля, которому она подсказка
    unit: str = None          # у короткой надписи-единицы справа от поля вплотную («дн.», «ч.», «х»): номер узла поля, которому она единица

    def to_json(self):
        out = {"id": self.id, "role": self.role, "box": [_num(v) for v in self.box], "elements": list(self.elements)}
        if self.reason is not None:
            out["reason"] = self.reason
        if self.holder is not None:
            out["holder"] = self.holder
        if self.page:
            out["page"] = self.page
        for key in ("kind", "row", "caption", "hint", "unit"):
            if getattr(self, key) is not None:
                out[key] = getattr(self, key)
        if self.field_left is not None:
            out["field_left"] = _num(self.field_left)
        if self.children:
            out["children"] = [child.to_json() for child in self.children]
        return out


class Structure:
    def __init__(self, root, kind=None, hidden=(), raw=()):
        self.root = root
        self.kind = kind
        self.hidden = frozenset(hidden)         # qualified-имена невидимых элементов
        self.raw = list(raw)                    # qualified-имена элементов без блока координат: в дерево они не идут
        self.by_element = {}
        for node in self.walk():
            for name in node.elements:
                self.by_element[name] = node.id
        for node in self.walk():
            if node.hint is not None:
                node.hint = self.by_element.get(node.hint, node.hint)
            if node.unit is not None:
                node.unit = self.by_element.get(node.unit, node.unit)

    def walk(self):
        """Узлы в порядке чтения: родитель, затем дети по порядку."""
        stack = [self.root]
        while stack:
            node = stack.pop()
            yield node
            stack.extend(reversed(node.children))

    def reading_order(self):
        """Qualified-имена элементов в порядке чтения."""
        return [name for node in self.walk() for name in node.elements]

    def node(self, ident):
        for node in self.walk():
            if node.id == ident:
                return node
        return None

    def to_json(self):
        out = {"kind": self.kind, "root": self.root.to_json()}
        if self.raw:
            out["raw"] = list(self.raw)
        return out

    def lines(self, name_of=None, hidden_tabs=(), leaf_boxes=True, notes=None):
        """Строки дерева: отступ по глубине, `номер роль: элементы (лево,верх–право,низ)`, вид пары (кроме обычной «надпись → поле»), подсказка,
        подпись закладки, пометки «скрыт» и причина «неясно». Внутри панели имена даны относительно неё (`Кнопка`, а не `Панель/Кнопка`);
        `name_of` — функция «имя в структуре → показанное имя» (короткие имена досье), вместо относительных.
        `hidden_tabs` — панели (у формы — `""`), у которых закладки не отображаются: их страница названа «страница», а не «закладка»;
        `leaf_boxes=False` — у пары и одиночного элемента места нет (оно в таблице элементов, где у каждого своя строка);
        `notes` — `{номер узла: слова}`: пометка, которую узлу добавляет вызывающий (код меняет видимость страницы, вариант на том же месте)."""
        out = []

        def put(node, depth):
            prefix = f"{node.holder}/" if node.holder else ""
            if name_of is not None:
                names = [name_of(n) for n in node.elements]
            else:
                names = [n[len(prefix):] if prefix and n.startswith(prefix) else n for n in node.elements]
            text = " → ".join(names) if node.role == PAIR else ", ".join(names)
            what = f"{node.id} {ROLE_WORDS[node.role]}"
            if text:
                what += f": {text}"
            l, t, r, b = (_num(v) for v in node.box)
            if leaf_boxes or node.role not in (PAIR, SINGLE):
                what += f" ({l},{t}–{r},{b})"
            if node.kind and node.kind != LABEL_FIELD:       # «надпись → поле» — обычная пара, стрелка её уже называет
                what += f", {KIND_WORDS[node.kind]}"
            if node.hint:
                what += f", подсказка к {node.hint}"
            if node.unit:
                what += f", единица поля {node.unit}"
            if node.caption:
                what += (f", страница «{node.caption}» (закладок нет, страницы переключает модуль)"
                         if (node.holder or "") in hidden_tabs else f", закладка «{node.caption}»")
            hidden = [n for n in node.elements if n in self.hidden]
            if hidden:
                what += ", скрыт" if len(hidden) == 1 else f", скрыты: {len(hidden)}"
            if notes and notes.get(node.id):
                what += f", {notes[node.id]}"
            if node.reason:
                what += f" — {node.reason}"
            out.append("  " * depth + what)
            for child in node.children:
                put(child, depth + 1)

        put(self.root, 0)
        return out


def _num(value):
    """Целое число места: дробное (середина нечётной ширины, след пересчёта привязок) округляется до пикселя."""
    return int(value) if isinstance(value, int) else int(round(value))


class _Row:
    """Ряд: кластер блоков с близкими верхами. Номер ряда выдаётся при нумерации, в порядке чтения."""
    __slots__ = ("pairs", "number")

    def __init__(self):
        self.pairs = 0
        self.number = None


class _Unit:
    __slots__ = ("kind", "items", "box", "how", "hint", "unit")

    def __init__(self, kind, items, how=None, hint=None, unit=None):
        self.kind, self.items, self.how, self.hint, self.unit = kind, items, how, hint, unit
        self.box = _union([it.box for it in items])


def _union(boxes):
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def _contains(a, b):
    """Элемент `a` — рамка, и `b` целиком внутри неё. Рамки с равными рамками вкладываются по индексу."""
    if a is b or a.type != FRAME:
        return False
    A, B = a.box, b.box
    if not (A[0] <= B[0] and A[1] <= B[1] and A[2] >= B[2] and A[3] >= B[3]):
        return False
    return A != B or b.type != FRAME or a.index < b.index


def _hosted(host, it):
    """`it` целиком на подложке `host` (панель команд, надпись-полоса, картинка): так форму и рисуют."""
    A, B = host.box, it.box
    return host.type in HOSTS and A[0] <= B[0] and A[1] <= B[1] and A[2] >= B[2] and A[3] >= B[3]


def _on_top(small, large):
    """`small` — мелкий элемент поверх контейнера `large` (панель, рамка, поле содержимого): кнопка в углу поля, флажок над рядом закладок, рамка-заголовок над панелью.
    Контейнер при этом остаётся ясным: перекрытие значит «поверх», а не «неясно». Мелкий элемент, торчащий из рамки или поля наполовину и более, остаётся «неясно»."""
    if large.type not in (PANEL, FRAME) and large.type not in CONTENT_TYPES:
        return False
    area = lambda it: (it.box[2] - it.box[0]) * (it.box[3] - it.box[1])
    if area(small) > OVER_SHARE * area(large):
        return False
    A, B = large.box, small.box
    if A[0] - EDGE_TOLERANCE <= B[0] and A[1] - EDGE_TOLERANCE <= B[1] and A[2] + EDGE_TOLERANCE >= B[2] and A[3] + EDGE_TOLERANCE >= B[3]:
        return True                                  # целиком на контейнере (с допуском на край)
    dx, dy = min(A[2], B[2]) - max(A[0], B[0]), min(A[3], B[3]) - max(A[1], B[1])
    return large.type == PANEL and dx > 0 and dy > 0 and dx * dy >= 0.5 * area(small)      # рамка-заголовок и флажок над рядом закладок панели: больше половины на панели


def _names(items, limit=MANY_NAMES):
    names = [it.qualified() for it in items]
    text = ", ".join(names[:limit])
    return text if len(names) <= limit else f"{text} и ещё {len(names) - limit}"


def _horizontal(item):
    return item.box[2] - item.box[0] >= item.box[3] - item.box[1]


def _icon(item):
    return item.type == PICTURE and max(item.box[2] - item.box[0], item.box[3] - item.box[1]) <= ICON_MAX


def _across(a, b):
    """Размер общего отрезка двух рамок по горизонтали."""
    return min(a[2], b[2]) - max(a[0], b[0])


def _sort(nodes):
    return sorted(nodes, key=lambda n: (n.box[1], n.box[0]))


def _cut(nodes, axis):
    """Разрез по оси (0 — вертикальный просвет, 1 — горизонтальный): `(до, после)` либо `None`. Просвет — место, через которое не проходит ни
    один узел (касание краёв — тоже просвет)."""
    ordered = sorted(nodes, key=lambda n: (n.box[axis], n.box[axis + 2]))
    reach = ordered[0].box[axis + 2]
    for at in range(1, len(ordered)):
        if ordered[at].box[axis] >= reach:
            return ordered[:at], ordered[at:]
        reach = max(reach, ordered[at].box[axis + 2])
    return None


def _side_by_side(left, right):
    """Левая и правая стопки стоят рядом: их вертикальные размеры пересекаются не меньше чем на `STACK_SHARE` меньшего."""
    tops = [min(n.box[1] for n in side) for side in (left, right)]
    bottoms = [max(n.box[3] for n in side) for side in (left, right)]
    share = min(bottoms) - max(tops)
    small = min(bottoms[0] - tops[0], bottoms[1] - tops[1])
    return share > 0 and share >= STACK_SHARE * small


def _read(nodes):
    """Порядок чтения узлов одного контейнера: левая стопка целиком, затем правая; полосы сверху вниз; иначе `(верх, лево)`."""
    nodes = _sort(nodes)
    if len(nodes) < 2:
        return nodes
    cut = _cut(nodes, 0)
    if cut is not None and _side_by_side(*cut):
        return _read(cut[0]) + _read(cut[1])
    cut = _cut(nodes, 1)
    if cut is not None:
        return _read(cut[0]) + _read(cut[1])
    return nodes


class _Builder:
    def __init__(self, form):
        self.form = form
        self.cluster = {}       # id(узла пары или ряда) → _Row
        counts = {}
        for it in form.items.values():
            counts[it.qualified()] = counts.get(it.qualified(), 0) + 1
        # имя с родителем; у тёзок в одном родителе (бывает в выгрузках) к имени добавляется `#<индекс>`: узлы различимы
        self.names = {it.index: (it.qualified() if counts[it.qualified()] == 1 else f"{it.qualified()}#{it.index}")
                      for it in form.items.values()}
        self._by_name = {name: form.items[index] for index, name in self.names.items()}
        self.bound = set()      # индексы элементов, привязанных к данным
        try:
            for row in datapath.binding_rows(form.doc.get("attributes") or {}):
                element = row.get(datapath.BIND_ELEMENT)
                if isinstance(element, int) and not isinstance(element, bool):
                    self.bound.add(element)
        except Exception:  # noqa: BLE001 — таблицы привязок нет: подписей-значений тогда не опознать, остальное работает
            self.bound = set()

    def _name(self, it):
        return self.names[it.index]

    # ── контейнеры ────────────────────────────────────────────────────────────────────────────

    def root(self):
        form = self.form
        holder = form.holders[0]
        node = Node("A0", AREA, (0, 0, form.width, form.height), [], [])
        node.children = self._pages(holder, None)
        return node

    def _pages(self, holder, holder_name):
        """Страницы контейнера: одна страница — содержимое прямо в контейнере, несколько — узлы `T` по номеру страницы."""
        size = holder.size
        pages = {}
        for it in holder.children:
            pages.setdefault(it.page or 0, []).append(it)
        if len(pages) <= 1:
            number, items = next(iter(pages.items())) if pages else (0, [])
            return self._scope(items, size, self._edge(holder, number), holder_name, number)
        return self._order(self._tab_nodes(holder, pages, holder_name))

    def _tab_nodes(self, holder, pages, holder_name):
        tabs = []
        captions = render._page_captions(holder.node)
        for number in sorted(pages):
            kids = self._scope(pages[number], holder.size, self._edge(holder, number), holder_name, number)
            tab = Node("", PAGE, _union([k.box for k in kids]) if kids else (0, 0, 0, 0), [], kids, holder=holder_name, page=number)
            if number < len(captions) and captions[number]:
                tab.caption = captions[number]
            tabs.append(tab)
        return tabs

    @staticmethod
    def _edge(holder, page):
        """Нижний край клиентской области страницы родителя: он выше размера, когда платформа оставляет полосу под закладки."""
        got = (holder.inner or {}).get(page)
        return min(holder.size[1], got[1]) if got else holder.size[1]

    def _panel(self, item, holder_name):
        holder = self.form.holders.get(item.index)       # у панели без элементов держателя нет
        node = Node("", AREA, item.box, [self._name(item)], [], holder=holder_name, page=item.page or 0)
        node.children = self._pages(holder, self._name(item)) if holder is not None else []
        return node

    # ── неясное ───────────────────────────────────────────────────────────────────────────────

    def _unclear(self, items, size):
        """`{индекс: причина}`: нулевой размер, выход за край родителя, перекрытие с другим видимым элементом."""
        width, height = size
        why = {}
        for it in items:
            l, t, r, b = it.box
            if r <= l or b <= t:
                why.setdefault(it.index, []).append(f"нулевой размер ({_num(r - l)}×{_num(b - t)})")
                continue
            if it.visible:
                out = []
                if l < -EDGE_TOLERANCE:
                    out.append(f"лево {_num(l)}")
                if t < -EDGE_TOLERANCE:
                    out.append(f"верх {_num(t)}")
                if r > width + EDGE_TOLERANCE:
                    out.append(f"право {_num(r)} при ширине {_num(width)}")
                if b > height + EDGE_TOLERANCE:
                    out.append(f"низ {_num(b)} при высоте {_num(height)}")
                if out:
                    why.setdefault(it.index, []).append("выходит за край родителя: " + ", ".join(out))
        pool = [it for it in items
                if it.visible and it.box[2] > it.box[0] and it.box[3] > it.box[1] and it.type != SPLITTER]
        pool.sort(key=lambda it: (it.box[0], it.box[1], it.index))
        hits = {}
        for at, a in enumerate(pool):
            for b in pool[at + 1:]:
                if b.box[0] > a.box[2] - OVERLAP_MIN:
                    break
                dx = min(a.box[2], b.box[2]) - max(a.box[0], b.box[0])
                dy = min(a.box[3], b.box[3]) - max(a.box[1], b.box[1])
                if dx < OVERLAP_MIN or dy < OVERLAP_MIN:
                    continue
                if _contains(a, b) or _contains(b, a) or _hosted(a, b) or _hosted(b, a):
                    continue
                if a.type == b.type == BAR and abs(a.box[1] - b.box[1]) <= 2 and abs(a.box[3] - b.box[3]) <= 2:
                    continue                                  # две панели команд в одной полосе
                if {a.type, b.type} == {LABEL, FRAME}:   # надпись поверх верхней кромки рамки — её заголовок
                    continue
                if _on_top(a, b) or _on_top(b, a):          # мелкий элемент поверх контейнера: контейнер ясный
                    continue
                hits.setdefault(a.index, []).append(b)
                hits.setdefault(b.index, []).append(a)
        for index, partners in hits.items():
            why.setdefault(index, []).append("перекрывается с " + _names(partners))
        return {index: "; ".join(words) for index, words in why.items()}

    # ── разбор одной страницы контейнера ──────────────────────────────────────────────────────

    def _scope(self, items, size, edge, holder_name, page):
        reasons = self._unclear(items, size)
        nodes = []
        rest = []
        frames = []
        for it in items:
            if it.index in reasons:
                node = self._leaf(UNCLEAR, [it], holder_name, page, reason=reasons[it.index])
                if it.type == PANEL:                   # дети панели остаются в дереве: они лежат в её координатах
                    holder = self.form.holders.get(it.index)
                    node.children = self._pages(holder, self._name(it)) if holder is not None else []
                elif it.type == FRAME:
                    frames.append((it, node))
                nodes.append(node)
            else:
                rest.append(it)
        # рамка, ставшая неясной, не теряет вложенное: ясные элементы внутри неё — её дети, а не общий поток
        for it, node in sorted(frames, key=lambda p: (p[0].box[2] - p[0].box[0]) * (p[0].box[3] - p[0].box[1])):
            inner = [x for x in rest if _contains(it, x)]
            if inner:
                rest = [x for x in rest if not any(x is y for y in inner)]
                node.children = self._arrange(inner, size, edge, holder_name, page, False)
        # неясный видимый элемент (панель, перекрытая другим) рвёт серии колонок, как и ясный разделитель
        unclear_seps = [it.box for it in items if it.index in reasons and it.visible]
        return self._order(nodes + self._arrange(rest, size, edge, holder_name, page, True, unclear_seps))

    def _leaf(self, role, items, holder_name, page, reason=None):
        return Node("", role, _union([it.box for it in items]), [self._name(it) for it in items], [],
                    reason=reason, holder=holder_name, page=page)

    def _arrange(self, items, size, edge, holder_name, page, edges, outside_seps=()):
        nodes = []
        seps = list(outside_seps)                                         # рамки видимых элементов, вынутых из потока рядов (не узлов): они рвут серии колонок
        frames = [it for it in items if it.type == FRAME]
        free = []
        sections = []
        for it in items:
            if any(_contains(f, it) for f in frames):
                continue                                  # лежит в рамке: его разберёт узел группы
            if it.type == FRAME:
                inner = [x for x in items if _contains(it, x)]
                if not inner and it.box[3] - it.box[1] <= SECTION_H:
                    node = self._leaf(SECTION, [it], holder_name, page)
                    sections.append(node)
                else:
                    node = self._leaf(GROUP, [it], holder_name, page)
                    node.children = self._arrange(inner, size, edge, holder_name, page, False)
                nodes.append(node)
                if it.visible:
                    seps.append(it.box)
            else:
                free.append(it)

        for node in sections:                             # надпись, лежащая на рамке-заголовке, — её заголовок
            frame = self._item(node.elements[0])
            for it in list(free):
                if (it.type == LABEL and it.visible and min(it.box[2], frame.box[2]) - max(it.box[0], frame.box[0]) >= OVERLAP_MIN
                        and min(it.box[3], frame.box[3]) - max(it.box[1], frame.box[1]) >= OVERLAP_MIN):
                    node.elements.append(self._name(it))
                    node.box = _union([node.box, it.box])
                    free.remove(it)

        used = set()
        bar_node = {}                                     # индекс панели команд → узел, в котором она лежит
        bars = [it for it in free if it.type == BAR and it.visible]
        for it in free:
            if it.type in CONTENT_TYPES and not _icon(it):
                kit = self._with_bars(it, bars, used, size, holder_name is None) if it.visible else [it]
                node = self._leaf(CONTENT, kit, holder_name, page)
                for member in kit:
                    if member.type == BAR:
                        bar_node[member.index] = node
                nodes.append(node)
                used.add(it.index)
                if it.visible:
                    seps.extend(member.box for member in kit)
            elif it.type == PANEL:
                node = self._panel(it, holder_name)
                nodes.append(node)
                used.add(it.index)
                if it.visible:
                    seps.append(it.box)
        for it in free:
            if it.type == BAR and it.visible and it.index not in used and edges and _horizontal(it):
                if it.box[1] <= EDGE:
                    role = TOP_BAR
                elif edge - it.box[3] <= EDGE:
                    role = BOTTOM_BAR
                else:
                    continue
                node = self._leaf(role, [it], holder_name, page)
                nodes.append(node)
                bar_node[it.index] = node
                used.add(it.index)
                seps.append(it.box)
        for it in free:
            if it.index not in used and it.type in (SPLITTER, BAR):
                node = self._leaf(SINGLE, [it], holder_name, page)
                nodes.append(node)
                used.add(it.index)
                if it.type == BAR and it.visible:
                    bar_node[it.index] = node
                if it.visible:
                    seps.append(it.box)

        # элементы, целиком лежащие на видимой панели команд, — дети узла этой панели
        visible_bars = sorted((it for it in free if it.type == BAR and it.visible), key=lambda it: it.index)
        for it in free:
            if it.index in used or it.type in CONTAINERS or (it.type in CONTENT_TYPES and not _icon(it)):
                continue
            for bar in visible_bars:
                if _hosted(bar, it):
                    host = bar_node[bar.index]
                    host.children.append(self._leaf(SINGLE, [it], holder_name, page))
                    used.add(it.index)
                    break
        for node in nodes:
            if node.role in (CONTENT, TOP_BAR, BOTTOM_BAR, SINGLE) and node.children:
                node.children = sorted(node.children, key=lambda c: (c.box[0], c.box[1]))
                node.box = _union([node.box] + [c.box for c in node.children])

        for it in free:                                   # скрытое в ряды, колонки и шапку не идёт: отдельными листами
            if it.index not in used and not it.visible:
                nodes.append(self._leaf(SINGLE, [it], holder_name, page))
                used.add(it.index)

        flow = [it for it in free if it.index not in used]
        nodes += self._rows(flow, seps, holder_name, page, edge, edges)
        self._fill_sections(nodes, sections)
        return self._order(nodes)

    def _with_bars(self, it, bars, used, size, form_level):
        """Содержимое с его панелями команд: горизонтальная вплотную над ним и вертикальные сбоку. Панель на всю ширину
        ФОРМЫ — панель формы, а не таблицы; в панели закладок и в рамке это правило не действует (ширина — по таблице)."""
        kit = [it]
        for bar in bars:
            if bar.index in used or not _horizontal(bar):
                continue
            if form_level and bar.box[0] <= 0 and bar.box[2] >= size[0]:
                continue
            gap = it.box[1] - bar.box[3]
            if -2 <= gap <= BAR_GAP and min(it.box[2], bar.box[2]) - max(it.box[0], bar.box[0]) > 0:
                kit.insert(0, bar)
                used.add(bar.index)
                break
        for side in (0, 1):
            for bar in bars:
                if bar.index in used or _horizontal(bar):
                    continue
                gap = it.box[0] - bar.box[2] if side == 0 else bar.box[0] - it.box[2]
                if -2 <= gap <= BAR_GAP and min(it.box[3], bar.box[3]) - max(it.box[1], bar.box[1]) > 0:
                    kit.insert(0, bar) if side == 0 else kit.append(bar)
                    used.add(bar.index)
                    break
        return kit

    def _fill_sections(self, nodes, sections):
        """Дети раздела: узлы того же уровня, у которых верх не выше рамки, середина по горизонтали внутри неё и между рамкой и узлом нет
        другой рамки (группы или раздела) на их горизонтали."""
        if not sections:
            return
        frames = {id(n): n.box for n in nodes if n.role in (GROUP, SECTION)}
        for node in sections:                             # рамка раздела — без надписи-заголовка
            frames[id(node)] = self._item(node.elements[0]).box
        taken = {id(s): [] for s in sections}
        for n in nodes:
            if n.role in (GROUP, SECTION, TOP_BAR, BOTTOM_BAR):
                continue                                  # шапка и подвал принадлежат контейнеру, а не разделу
            centre = (n.box[0] + n.box[2]) / 2
            best = None
            for s in sections:
                fb = frames[id(s)]
                if fb[1] <= n.box[1] and fb[0] <= centre <= fb[2] and (best is None or fb[1] > frames[id(best)][1]):
                    best = s
            if best is None:
                continue
            top = frames[id(best)][1]
            if any(top < gb[1] <= n.box[1] and _across(gb, n.box) > 0 for gid, gb in frames.items() if gid != id(best)):
                continue
            taken[id(best)].append(n)
        for s in sections:
            kids = taken[id(s)]
            if not kids:
                continue
            s.children = self._order(kids)
            s.box = _union([s.box] + [k.box for k in kids])
            nodes[:] = [n for n in nodes if not any(n is k for k in kids)]

    # ── ряды, пары, колонки ───────────────────────────────────────────────────────────────────

    def _units(self, flow):
        """Блоки ряда: пары собраны по приоритету, остальное — одиночные элементы. Одно поле — в одной паре."""
        used = set()
        units = []
        key = lambda it: (it.box[1], it.box[0], it.index)  # noqa: E731
        fields = sorted((it for it in flow if it.type in FIELD_TYPES), key=key)
        pool = sorted((it for it in flow if it.type == LABEL), key=key)
        checks = sorted((it for it in flow if it.type == CHECK), key=key)

        def take(how, *items):
            used.update(it.index for it in items)
            units.append(_Unit(PAIR, list(items), how))

        unit_of = {lab.index: field for lab, field in self._unit_labels(pool, fields).items()}   # 0. единицы справа от поля вплотную: надпись поля справа не берут
        pool = [lab for lab in pool if lab.index not in unit_of]
        for field in fields:                              # 1. надпись слева (правило `shell.find_label`, как у `describe`)
            lab = shell.find_label(field, pool)
            if lab is not None:
                pool.remove(lab)
                take(LABEL_FIELD, lab, field)
        for field in fields:                              # 2. флажок слева: «☑ Использовать [поле]»
            if field.index in used:
                continue
            check = shell.find_label(field, checks)
            if check is not None:
                checks.remove(check)
                take(CHECKBOX_FIELD, check, field)
        for lab in list(pool):                            # 3. надпись над полем — только у поля без пары
            if any(shell.find_label(f, [lab]) is lab for f in fields):
                continue                                  # справа от надписи есть поле: оно её, а не нижнее
            for field in fields:
                if (field.index not in used and -ABOVE_OVERLAP <= field.box[1] - lab.box[3] <= ABOVE_GAP
                        and (abs(field.box[0] - lab.box[0]) <= COLUMN_DX or (_over_field(lab, field) and lab.index not in self.bound))):
                    pool.remove(lab)
                    take(LABEL_FIELD, lab, field)
                    break
        for right in sorted((it for it in pool if it.index in self.bound), key=key):   # 4. подпись → значение
            if right not in pool:
                continue
            left = shell.find_label(right, [it for it in pool if it is not right])
            if left is not None:
                pool.remove(left)
                pool.remove(right)
                take(CAPTION_VALUE, left, right)
        hints = {}
        for lab in pool:                                  # надпись под полем вплотную — подсказка к нему, если поле одно
            near = [f for f in fields if -1 <= lab.box[1] - f.box[3] <= ABOVE_GAP and abs(lab.box[0] - f.box[0]) <= COLUMN_DX]
            if len(near) == 1:
                hints[lab.index] = self._name(near[0])
        for it in flow:
            if it.index in used:
                continue
            if it.type in SELF_PAIR_TYPES:
                units.append(_Unit(PAIR, [it]))
            elif it.index in unit_of:
                units.append(_Unit(SINGLE, [it], unit=self._name(unit_of[it.index])))
            else:
                units.append(_Unit(SINGLE, [it], hint=hints.get(it.index)))
        return units

    def _unit_labels(self, pool, fields):
        """`{надпись: поле}`: короткая надпись-единица измерения вплотную справа от поля в том же ряду («дн.», «ч.», «х» между полями) — единица этого поля, а не надпись
        следующего (`UNIT_GAP`, `is_unit_text`); поле берётся ближайшее слева."""
        out = {}
        for lab in pool:
            text = (render.caption_text(lab.node, LABEL) or "").strip()
            if not is_unit_text(text):
                continue
            best = None
            for field in fields:
                gap = lab.box[0] - field.box[2]
                height = min(lab.box[3] - lab.box[1], field.box[3] - field.box[1])
                if -1 <= gap <= UNIT_GAP and height > 0 and shell.overlap(lab.box[1], lab.box[3], field.box[1], field.box[3]) * 2 >= height \
                        and (best is None or gap < best[0]):
                    best = (gap, field)
            if best is not None:
                out[lab] = best[1]
        return out

    def _clusters(self, units):
        rows = []
        for unit in sorted(units, key=lambda u: (u.box[1], u.box[0])):
            if rows and unit.box[1] - rows[-1][0].box[1] <= ROW_DY:
                rows[-1].append(unit)
            else:
                rows.append([unit])
        return rows

    def _rows(self, flow, seps, holder_name, page, edge, edges):
        nodes = []
        for line in self._clusters(self._units(flow)):
            line.sort(key=lambda u: (u.box[0], u.box[1]))
            row = _Row()
            leaves = []
            for unit in line:
                if unit.kind == PAIR:
                    row.pairs += 1
                    leaf = self._leaf(PAIR, unit.items, holder_name, page)
                    leaf.id = f"{row.pairs}"                 # номер в ряду; полный номер — при нумерации
                    leaf.kind = unit.how
                else:
                    leaf = self._leaf(SINGLE, unit.items, holder_name, page)
                    leaf.hint = unit.hint
                    leaf.unit = unit.unit
                self.cluster[id(leaf)] = row
                leaves.append(leaf)
            nodes.append(self._line(leaves, row, holder_name, page, edge, edges))
        return self._columns(nodes, seps)

    def _line(self, leaves, row, holder_name, page, edge, edges):
        if all(leaf.role == SINGLE and self._is_button(leaf) for leaf in leaves):
            items = [self._item(name) for leaf in leaves for name in leaf.elements]
            top, bottom = min(it.box[1] for it in items), max(it.box[3] for it in items)
            role = TOP_BAR if edges and top <= EDGE else BOTTOM_BAR if edges and edge - bottom <= EDGE else BUTTONS
            node = self._leaf(role, items, holder_name, page)
            self.cluster[id(node)] = row
            return node
        if len(leaves) == 1 and leaves[0].role == SINGLE:
            return leaves[0]
        node = Node("", ROW, _union([leaf.box for leaf in leaves]), [], leaves, holder=holder_name, page=page)
        self.cluster[id(node)] = row
        return node

    def _item(self, name):
        return self._by_name[name]

    def _is_button(self, leaf):
        return self._by_name[leaf.elements[0]].type == BUTTON

    def _columns(self, nodes, seps):
        """Серии рядов из одних пар → колонки и многоколонные области; серию рвёт всё, что не ряд из пар, и разделитель между рядами."""
        nodes = _sort(nodes)
        out = []
        series = []

        def flush():
            out.extend(self._grid(series))
            series.clear()

        for node in nodes:
            if node.role == ROW and all(c.role == PAIR for c in node.children):
                if series and self._broken(series[-1], node, seps):
                    flush()
                series.append(node)
            else:
                flush()
                out.append(node)
        flush()
        return out

    @staticmethod
    def _broken(prev, node, seps):
        """Между рядами лежит разделитель, перекрывающий один из них по горизонтали (правило `rowgrid.joined`)."""
        tops = [s[1] for s in seps if _across(s, prev.box) > 0 or _across(s, node.box) > 0]
        return not rowgrid.joined(prev.box[1], node.box[1], tops)

    def _grid(self, rows):
        """Серия рядов из пар → узлы: блоки по `rowgrid.runs`; колонка — блок из двух рядов и больше с одной парой, многоколонная
        область — блок с двумя парами и больше в ряду при совпадении левых краёв пар по колонкам; прочие ряды остаются рядами."""
        if len(rows) < 2:
            return list(rows)
        node_of = {id(r.children): r for r in rows}
        blocks = [dict(b) for b in rowgrid.runs([r.children for r in rows])]
        out = []
        at = 0
        while at < len(blocks):
            n, taken = blocks[at]["n"], list(blocks[at]["rows"])
            nxt = blocks[at + 1] if at + 1 < len(blocks) else None
            if n >= 2 and len(taken) >= 2 and nxt is not None and nxt["n"] < n and self._aligned(taken + [nxt["rows"][0]], n):
                taken.append(nxt["rows"][0])               # неполный последний ряд блока: его пары стоят в первых колонках
                nxt["rows"] = nxt["rows"][1:]
            if len(taken) >= 2 and n == 1:
                out.append(self._column(taken))
            elif len(taken) >= 2 and n >= 2 and self._aligned(taken, n):
                out.append(self._area(taken, n))
            else:
                out.extend(node_of[id(r)] for r in taken)
            at += 1
            while at < len(blocks) and not blocks[at]["rows"]:
                at += 1
        return out

    @staticmethod
    def _aligned(rows, n):
        """Левые края пар по колонкам совпадают в пределах `COLUMN_DX`: `j`-я пара каждого ряда — в `j`-й колонке, колонки различимы."""
        full = [r for r in rows if len(r) == n]
        if len(full) < 2:
            return False
        lefts = []
        for j in range(n):
            col = [r[j].box[0] for r in rows if len(r) > j]
            if max(col) - min(col) > COLUMN_DX:
                return False
            lefts.append(col)
        return all(min(lefts[j + 1]) - max(lefts[j]) > COLUMN_DX for j in range(n - 1))

    def _column(self, rows):
        pairs = [p for r in rows for p in r]
        first = pairs[0]
        node = Node("", COLUMN, _union([p.box for p in pairs]), [], pairs, holder=first.holder, page=first.page)
        node.field_left = self._field_left(pairs)
        return node

    def _area(self, rows, n):
        columns = []
        for j in range(n):
            pairs = [r[j] for r in rows if len(r) > j]
            first = pairs[0]
            col = Node("", COLUMN, _union([p.box for p in pairs]), [], pairs, holder=first.holder, page=first.page)
            col.field_left = self._field_left(pairs)
            columns.append(col)
        first = columns[0].children[0]
        return Node("", AREA, _union([c.box for c in columns]), [], columns, holder=first.holder, page=first.page)

    def _field_left(self, pairs):
        lefts = [self._item(p.elements[-1]).box[0] for p in pairs if len(p.elements) == 2]
        return min(lefts) if lefts else None

    # ── порядок и номера ──────────────────────────────────────────────────────────────────────

    def _order(self, nodes):
        """Порядок чтения: стопки слева направо, внутри — сверху вниз; страницы формы — по номеру в местах, занятых страницами."""
        if not any(n.role == PAGE for n in nodes):
            return _read(nodes)
        ordered = _sort(nodes)
        slots = [at for at, n in enumerate(ordered) if n.role == PAGE]
        pages = sorted((n for n in ordered if n.role == PAGE), key=lambda n: n.page)
        for at, node in zip(slots, pages):
            ordered[at] = node
        return ordered


def _number(root, cluster):
    counts = {}

    def take(prefix):
        counts[prefix] = counts.get(prefix, 0) + 1
        return counts[prefix]

    def row_number(node):
        row = cluster.get(id(node))
        if row is None:
            return None
        if row.number is None:
            row.number = take("R")
        return row.number

    def put(node):
        if node.id != "A0":
            if node.role == PAIR:
                inner = node.id
                node.row = row_number(node)
                node.id = f"P{node.row}.{inner}"
            elif node.role == ROW:
                node.id = f"R{row_number(node)}"
            else:
                node.id = f"{PREFIX[node.role]}{take(PREFIX[node.role])}"
        for child in node.children:
            put(child)

    put(root)


def recognize(doc, kind=None, modeled=False):
    """Структура формы `doc` (документ уровня 1). Форму не меняет; отказ раскладки (`layout.read`) идёт словами.
    `modeled` — места элементов, которые предприятие ставит по правилам привязок, а не по файлу, берутся по модели раскладки при размере формы
    (`layout.apply_model_boxes`); по умолчанию — как записано в файле."""
    form = layout.read(doc)
    if modeled:
        layout.apply_model_boxes(form)
    builder = _Builder(form)
    root = builder.root()
    _number(root, builder.cluster)
    hidden = [builder.names[it.index] for it in form.items.values() if not it.visible]
    return Structure(root, kind, hidden, [it.qualified() for it in form.raw])
