"""Место нового элемента без `box` — по соседям.

`add_element` без `box` не требует координат: элемент встаёт следующей строкой блока, в который
добавлен. Модуль только считает (пишет лишь по `Place.shift`): выбор места, сдвиг мешающих, слова
отчёта; отказ приходит до первой записи. Родитель — панель или форма, на которой лежит элемент.

* **Сосед** — `after=<имя>` либо последний видимый элемент того же типа на той же странице того же
  родителя (самый нижний верх, при равных — по порядку в списке); такого типа нет — последний из
  сдвигающихся вместе с окном (привязанные к низу панели не в счёт); все остаются на месте — последний из всех. Пустая страница
  без `after` — отказ.
* **Место** — столбец соседа, верх = верх соседа + шаг. Шаг строк — разность верхов двух последних
  строк того же типа, оканчивающихся соседом (верхи, различающиеся не больше чем на
  `patterns.ROW_DY`, — одна строка). Строки берутся, только если смежны: между ними нет видимого
  элемента другого типа (панель, таблица, строка флажков, надпись-заголовок отделяют строки
  блоками), и
  шаг не больше двух норм `pair_pitch` вида (больше — норма вида, отчёт говорит). Строки нет или она
  не смежна — норма `pair_pitch` вида формы (вид — параметр `kind` либо по основному реквизиту,
  `census.KNOWN`); нормы нет — отказ.
* **Размер** — как у ближайшего элемента того же типа (сосед, иначе последний такого типа). Такого
  типа нет: у поля ввода высота `field_height` вида, ширина до правого края родителя минус
  `field_right_margin`; у надписи и флажка с `caption` — высота `label_height` (у флажка нормы нет
  — 15, у надписи без нормы 19), ширина по тексту; у прочих типов размера взять неоткуда — отказ.
* **Подпись в самом элементе** (надпись, флажок, переключатель, кнопка формы) — ширина не меньше
  текста по `textwidth` плюс отступ: надпись 0, флажок 16 (`render.CHECK_CAPTION_PAD`), кнопка 4
  (`render.BUTTON_CAPTION_PAD`), переключатель 20 (не проверялось): `max(ширина образца, текст +
  отступ)`. `CommandBarButton` не затронута: ширину считает платформа. Надпись шире образца,
  которую пришлось бы посадить на поле, уже стоящее правее на её строке, — отказ (раздвигать поле
  вниз развалило бы пару). Поле, встающее на строку, где надпись колонки надписей ждёт его и
  перекрывает место, встаёт после неё с зазором пары (правый край прежний); ширина после этого
  ниже `MIN_FIELD_W` или ниже половины прежней — отказ; надпись и поле — разными операциями.
* **Шрифт подписи** — текст меряется `textwidth.measure` шрифтом, действующим у нового узла
  (`textwidth.element_font` после оформления по соседям в `add_element`), а не шрифтом формы;
  шрифт не проверялся — оценка и строка в отчёте. С `shrink`-подъёмом наезд надписи на поле ряда
  ниже проверяется после подъёма (`widen_hit`).
* **Привязки** — как у ближайшего элемента того же типа (сосед, иначе последний такого типа не
  ниже соседа): правила всех четырёх границ с флагами «Ручная привязка» копируются, смещения
  пересчитываются под новое место (`_copy_rules`: смещение образца + сдвиг границы − сдвиг стороны
  объекта). Переносится всё, что бывает у платформенных форм: границы без правила, пара долей,
  правила к краю родителя и к себе. Правило к третьему элементу (не к образцу, не к краю) не
  переносится: встречная запись легла бы чужому элементу — граница идёт за самим образцом той же
  стороной объекта (`верх = Сосед.низ + k` → `верх = образец.низ + зазор`), вторая граница-доля
  снимается; слова называют, какое правило куда ушло. Элемента того же типа нет — «к себе», как у
  `box`; `anchor=` называет привязку руками. Образец ниже места — отказ.
* **Раздвигание** — только если место занято (прямоугольник нового элемента пересекает чей-то,
  видимый или нет; `docs/layout.md`). Тогда все элементы родителя и страницы, чей верх не выше места
  минус полшага (`step // 2`), видимые и невидимые, в том числе другого столбца (отчёт называет их),
  сдвигаются вниз на шаг: `box` и правила «к верху» — прямым сдвигом (`set_anchors`/`relayout` не
  зовутся). Правило каждой границы пересчитывается одной формулой: смещение += сдвиг своей границы −
  сдвиг стороны объекта. Рамка группы, охватывающая место (`GroupBox`, чей прямоугольник содержит
  место по ширине, начинается не ниже соседа и кончается ниже верха места), не помеха: её низ растёт
  на шаг вместе с рядами.
* **Явные ключи для места, которого нет** — по умолчанию выключены, отчёт называет всё, что
  изменилось сверх «добавить поле».
  * `grow=true` — форма выше на шаг (только форма: у панели высота — внешняя раскладка, отказ).
    Размер пишет `set_property` формы (платформа элементы не двигает, а переписывает смещения
    привязок к краю формы и отступы направляющих), затем всё с верхом не выше места − полшага сдвигается
    на шаг, в том числе привязанное к низу целиком. Включается, только если без него места нет.
  * `shrink=true` — ужимается только `TableBox` (минимум высоты 49): верх на шаг ниже, низ и правило
    к низу на месте; условия — у верха не больше одного правила и не к низу формы, у низа одно
    правило `F.b`, высота после ужатия не ниже минимума. Панель и прочие типы — отказ. Отчёт
    называет потерянные px и то, что раскладка при сжатии окна теперь перестанет меняться на шаг раньше.
    Минимум 49 принимается и при DPI 120, если «не проверялось» только из-за DPI 120 (шрифты таблицы
    и шапки по умолчанию); DPI 144 и прочие, иной шрифт — отказ; отчёт называет допуск словами.
  * Вторая сторона `shrink` — подъём нижнего блока (`lift_applies`): место занято рядом, привязанным
    к низу формы обеими границами (по одному правилу `F.b`), сосед сам из такого блока, над ним
    ужимаемая `TableBox`. Блок подъёма (элементы с верхом от низа таблицы до места − полшага,
    видимые
    и невидимые, другие столбцы тоже) сдвигается вверх на шаг, таблица ужимается снизу (минимум 49), новый
    встаёт на прежнее место ряда соседа с прежними правилами образца; ниже места не тронуто. Отказы
    словами: между таблицей и местом элемент не к низу; элемент блока привязан к низу одной
    границей;
    таблица ниже минимума; наезд после подъёма; образец привязок не из блока (нужен `anchor=`). Шаг
    при подъёме (и когда строк нет, а сосед привязан к низу) — расстояние до ближайшего ряда ниже,
    привязанного к низу (`_lower_gap`, не больше двух норм).
* **Отказы словами, до записи**: место занято элементом, который остаётся на месте (привязанным к низу, к центру по
  вертикали либо парой долей); место занято элементом, начинающимся выше места; после сдвига кто-то
  наезжает на кого-то, в том числе новый на сдвинутого; несдвигаемый элемент привязан по вертикали
  к сдвигаемому; низ нового или сдвинутого выходит за край родителя там, где раньше помещался.
  Отказ «места нет» называет род причины и выходы: нижний элемент целиком (командная панель) —
  `grow`, `relayout height=<высота + шаг>`; растянутый вниз — `grow` или `shrink` (`relayout` не
  поможет); прочее — `box`.
"""
from . import layout, patterns, textgap, textwidth
from .edit import names as N
from .edit.base import EditError

SIDE_TOP, SIDE_BOTTOM, SIDE_LEFT, SIDE_RIGHT, SIDE_CENTER_V, SIDE_CENTER_H = range(6)
EMPTY = -1  # объект правила «нет правила»
SELF = "self"
PITCH_CAP = 2  # шаг строк больше стольких норм `pair_pitch` — норма вида
FRAME = "GroupBox"  # охватывающая рамка
SQUEEZABLE = "TableBox"  # ужимается только таблица
# Подпись в самом элементе: ширина не меньше текста по `textwidth` плюс отступ подписи от левого
# края box. Надпись — 0, флажок — `render.CHECK_CAPTION_PAD` (16), переключатель —
# `render.RADIO_CAPTION_PAD` (16, как у флажка; e230), кнопка формы — `render.BUTTON_CAPTION_PAD` (4). Кнопки
# командной панели (`CommandBarButton`) сюда не относятся: ширину считает платформа. Числа берутся
# из рендера на вызове.
CAPTION_TYPES = ("Label", "CheckBox", "RadioButton", "Button")
LABEL_H = 19  # высота новой надписи без нормы вида `label_height` (так пишет конструктор форм 1С)
BUTTON_H = 23  # высота новой кнопки формы без образца (нормы вида в `patterns.json` нет)
FLAG_H = 15  # высота нового флажка без нормы (как `generate.FLAG_H`)
PAIR_DY = 3  # надпись пары выше или ниже своего поля не больше чем на столько (на 1–3 px выше — одна строка пары)
_SHIFTING = (layout.MOVES, layout.PARTLY)  # поле сдвигается вместе с краем окна или на долю его роста
COLUMN_DX = 2  # левые края элементов одного столбца различаются не больше чем на столько
FREE_CELL_MARK = "свободная клетка сетки"  # слова отчёта о поле, вставшем в клетку соседнего столбца
MIN_CELL_GAP = 4  # клетка не ближе стольких px к чужой надписи слева, если у столбца своего зазора «надпись → поле» нет
MIN_FIELD_W = 11  # поле уже платформенного минимума (`layout.MIN_SIZE`) не пишется

ADVICE = {
    "A": ("Выходы: grow=true — форма становится выше на шаг, и нижние элементы сдвигаются вместе с ней; либо relayout "
          "height=<высота формы + шаг> и повторить add_element; либо box. set_anchors у этого элемента не поможет: "
          "нижняя панель, сменив роль, перестанет быть нижней"),
    "B": ("relayout здесь не поможет: растянутый элемент растягивается вниз вместе с формой, а его верх остаётся под последним "
          "полем. Выходы: grow=true — форма становится выше на шаг; shrink=true — ужать таблицу на шаг, если мешает она "
          "(только TableBox, минимум 49); либо box"),
    "E": ("Выходы: grow=true — форма становится выше на шаг; либо relayout height=<высота формы + шаг> и повторить "
          "add_element; либо box"),
    "C": "Задайте box либо after=<другой сосед>",
    "D": "Снимите привязку (set_anchors) у этого элемента либо задайте box",
}


class RoomRefusal(EditError):
    """Отказ рода «места нет»: `text` — слова причины, `cause` — род (`A` — нижний элемент целиком, `B`
    — растянутый вниз, `E` — края и наезды, `C` — прочий элемент, остающийся на месте); по роду к тексту дописываются
    выходы (`ADVICE`).
    """

    def __init__(self, text, cause="E"):
        self.text, self.cause = text, cause
        super().__init__(f"{text}. {ADVICE[cause]}")


class Place:
    """Выбранное место: `box`, привязка (`anchor` для `_set_anchors` либо `rules` образца), сдвиг и
    слова.
    """

    def __init__(self, box, anchor, rules, flags, movers, adjust, step, words, grow=None, sample=None):
        self.box, self.anchor, self.rules, self.flags = box, anchor, rules, flags
        self.sample = sample        # `{ось: имя элемента}`: у кого скопированы привязки (0 — ширина, 1 — высота); `None`, если копии нет
        self.movers, self.adjust, self.step, self.words = movers, adjust, step, words
        self.grow = grow

    def shift(self):
        """Записать: размер формы при `grow` (до всего прочего: прежние смещения правил к низу формы
        платформа переписывает только так), затем `box` двигавшихся и пересчёт смещений. Зовут один
        раз, после проверок.
        """
        if self.grow is not None:
            from .edit import setprop
            doc, height, unverified = self.grow
            setprop.set_property(doc, form=True, name="height", value=height, unverified=unverified)
        for _label, coords, dtop, dbottom in self.movers:
            coords[N.Y] += dtop
            coords[N.HEIGHT] += dbottom
        for rule, change in self.adjust:
            rule[N.RULE_OFFSET] += change

    def is_self_shape(self):
        """Скопированные правила — те, что пишет `anchor=self`: низ к своему верху, право к своему
        леву, больше ничего.
        """
        if self.rules is None:
            return False
        top, bottom, left, right = (self.rules[b] for b in range(4))
        return (top == [None, None] and left == [None, None]
                and bottom[0] is not None and bottom[0][:2] == (SELF, SIDE_TOP) and bottom[1] is None
                and right[0] is not None and right[0][:2] == (SELF, SIDE_LEFT) and right[1] is None)

    def write_rules(self, coords, index, names):
        """Правила образца — в блок координат нового элемента (`SELF` — его индекс); слова записанного
        для отчёта.
        """
        from . import anchors as _anchors
        words = []
        for border, key in enumerate(N.ANCHORS):
            for which, slot in zip(N.RULES, self.rules[border]):
                coords[key][which].update(
                    dict(N.NO_ANCHOR) if slot is None else
                    {N.RULE_OBJECT: index if slot[0] == SELF else slot[0], N.RULE_SIDE: slot[1], N.RULE_OFFSET: slot[2]})
            written = [_anchors.rule_text(coords[key][which], index, names) for which in N.RULES
                       if coords[key][which][N.RULE_OBJECT] != EMPTY]
            words.append(f"{BORDERS[border]} {' & '.join(written) or '—'}")
        coords[N.MANUAL_H], coords[N.MANUAL_V] = self.flags
        return ", ".join(words)


def _rect(coords):
    return coords[N.X], coords[N.Y], coords[N.WIDTH], coords[N.HEIGHT]


def _int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _hit(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _name(item):
    return (item.get(N.NAME_BLOCK) or {}).get(N.NAME)


class _Peer:
    __slots__ = ("item", "coords", "name", "index", "type", "order", "visible")

    def __init__(self, item, coords, order):
        self.item, self.coords, self.order = item, coords, order
        self.name, self.index, self.type = _name(item), item.get(N.INDEX), item.get("type")
        self.visible = coords.get("visible", True) is not False

    @property
    def rect(self):
        return _rect(self.coords)

    def label(self):
        return f"«{self.name}»" if self.name else f"#{self.index}"


def _peers(holder, page, hidden=False):
    """Элементы родителя на странице с разобранным блоком координат. Без `hidden` — только видимые
    (соседи, строки, образец); с `hidden` — и невидимые: они участвуют в столкновениях и сдвигаются со
    своей строкой (`docs/layout.md`).
    """
    out = []
    for order, item in enumerate((holder.get(N.ELEMENTS) or {}).get(N.ITEMS) or []):
        coords = item.get(N.COORDS) if isinstance(item, dict) else None
        if not isinstance(coords, dict) or not all(_int(coords.get(k)) for k in (N.X, N.Y, N.WIDTH, N.HEIGHT)):
            continue
        if coords.get(N.PAGE) != page:
            continue
        peer = _Peer(item, coords, order)
        if peer.visible or hidden:
            out.append(peer)
    return out


def _rules_of(coords, sides):
    """Словари правил указанных сторон (оба правила каждой); чужой вид блока привязок — пусто. Пустое
    правило (объект `EMPTY`, −1, сторона 6) не отдаётся и потому не пересчитывается ни одним
    сдвигом: платформа пишет его {−1, 6, 0}; влияние ненулевого смещения на предприятие не
    проверялось.
    """
    out = []
    for side in sides:
        block = coords.get(N.ANCHORS[side])
        for key in N.RULES:
            rule = block.get(key) if isinstance(block, dict) else None
            if isinstance(rule, dict) and _int(rule.get(N.RULE_OBJECT)) and rule[N.RULE_OBJECT] != EMPTY:
                out.append(rule)
    return out


def _rule(coords, side, which):
    block = coords.get(N.ANCHORS[side])
    rule = block.get(N.RULES[which]) if isinstance(block, dict) else None
    if not isinstance(rule, dict) or rule.get(N.RULE_OBJECT) in (None, EMPTY):
        return None
    return rule[N.RULE_OBJECT], rule[N.RULE_SIDE], rule[N.RULE_OFFSET]


BOTTOM_WORDS, CENTER_WORDS, PAIR_WORDS = "привязан к низу родителя", "привязан к центру родителя", "ведёт пара долей по вертикали"


def _stuck_reasons(peer):
    """Почему элемент нельзя сдвинуть вниз прямым сдвигом: привязан к низу или к центру родителя, либо
    второе правило границы —
    пара долей. Слова в порядке обхода (верх, низ); пусто — сдвигается.
    """
    out = []
    for side in (0, 1):
        for rule in _rules_of(peer.coords, (side,)):
            if rule[N.RULE_OBJECT] == 0 and rule[N.RULE_SIDE] in (SIDE_BOTTOM, SIDE_CENTER_V):
                out.append(BOTTOM_WORDS if rule[N.RULE_SIDE] == SIDE_BOTTOM else CENTER_WORDS)
        second = _rule(peer.coords, side, 1)
        if second is not None and second[0] != peer.index:
            out.append(PAIR_WORDS)
    return out


def _why_stuck(peer):
    """Первая причина `_stuck_reasons` либо `None` — сдвигается."""
    reasons = _stuck_reasons(peer)
    return reasons[0] if reasons else None


def _stuck_cause(peer):
    """Род элемента, остающегося на месте, для совета: `A` — привязан к низу целиком (верх идёт за низом формы или за
    собой: нижняя командная панель), `B` — растянут вниз (верх к верху формы или к элементу, низ к
    низу формы), `C` — прочее.
    """
    if set(_stuck_reasons(peer)) != {BOTTOM_WORDS}:
        return "C"
    top = _rule(peer.coords, 0, 0)
    if top is None:
        return "B"
    target, side, _off = top
    if target == peer.index:
        return "A"
    if target == 0:
        return "A" if side == SIDE_BOTTOM else "B" if side == SIDE_TOP else "C"
    return "B"


def _squeezable(peer):
    """Ужимается сверху при `shrink`: таблица, у верха не больше одного правила и не к низу/центру
    формы, у низа одно правило `F.b`.
    """
    if peer.type != SQUEEZABLE:
        return False
    t0, t1, b0, b1 = (_rule(peer.coords, border, which) for border in (0, 1) for which in (0, 1))
    if t1 is not None or b1 is not None:
        return False
    if t0 is not None and (t0[0] == peer.index or (t0[0] == 0 and t0[1] != SIDE_TOP)):
        return False
    return b0 is not None and b0[0] == 0 and b0[1] == SIDE_BOTTOM


# ── Привязки как у образца ────────────────────────────────────────────────────────────────────

BORDERS = ("верх", "низ", "лево", "право")


def _copy_rules(peer, new, names=None, keep_third=False):
    """Правила четырёх границ образца для нового элемента: те же объекты и стороны, смещения
    пересчитаны под место.

    Правило читается «моя граница = сторона объекта + смещение», пересчёт один на все: смещение
    нового = смещение образца + сдвиг границы образца в новое место − сдвиг стороны объекта (ноль у
    края родителя и у любого другого элемента, сдвиг собственной стороны у правила «к себе»).
    Сдвигаемых тут нет по построению: образец, чьё правило называет сдвигаемого, — отказ раньше
    (`_decide`), сам образец ниже места — тоже.

    Правило к третьему элементу (ни к образцу, ни к краю родителя) не переносится: цепочка образца —
    его соседи, и встречная запись легла бы чужому элементу. Первое правило такой границы
    переводится на сам образец той же стороной объекта (`верх = Сосед.низ + k` образца → `верх =
    образец.низ + зазор`), смещение пересчитывается по положению нового; второе правило (доля)
    снимается. Какое правило куда ушло, возвращает второй результат. Объект «сам» остаётся «сам»
    (`SELF`). Возвращает `({граница: [(объект, сторона, смещение)|None, …]}, [слова])`.
    """
    old = peer.rect
    delta = {0: new[1] - old[1], 1: new[3] - old[3], 2: new[0] - old[0], 3: new[2] - old[2]}
    own = dict(delta)
    own[SIDE_CENTER_V] = (delta[0] + delta[1]) // 2
    own[SIDE_CENTER_H] = (delta[2] + delta[3]) // 2
    position = {0: new[1], 1: new[3], 2: new[0], 3: new[2]}
    at_peer = {SIDE_TOP: old[1], SIDE_BOTTOM: old[3], SIDE_LEFT: old[0], SIDE_RIGHT: old[2],
               SIDE_CENTER_V: (old[1] + old[3]) // 2, SIDE_CENTER_H: (old[0] + old[2]) // 2}
    out, notes = {}, []
    for border in range(4):
        slots = []
        for which in (0, 1):
            rule = _rule(peer.coords, border, which)
            if rule is None:
                slots.append(None)
                continue
            target, side, offset = rule
            if target not in (0, peer.index) and not keep_third:
                who = (names or {}).get(target) or f"#{target}"
                vertical = border in (0, 1)
                if which == 0 and side in at_peer and (side in (SIDE_TOP, SIDE_BOTTOM, SIDE_CENTER_V)) == vertical:
                    slots.append((peer.index, side, position[border] - at_peer[side]))
                    notes.append(f"{BORDERS[border]}: правило образца к «{who}» не перенесено (цепочка образца — его соседей), "
                                 f"граница идёт за самим образцом «{peer.name or peer.index}»")
                else:
                    slots.append(None)
                    notes.append(f"{BORDERS[border]}: " + (f"правило образца к «{who}» не перенесено" if which == 0 else
                                                          f"вторая граница образца к «{who}» не перенесена")
                                 + " — граница без этого правила")
                continue
            moved = 0
            if target == peer.index:
                moved, target = own.get(side, 0), SELF
            slots.append((target, side, offset + delta[border] - moved))
        out[border] = slots
    return out, notes


# ── Вид формы и нормы ─────────────────────────────────────────────────────────────────────────

_NORMS = {}


def _norm(doc, kind, key):
    """Норма правила вида формы (`kind` либо по основному реквизиту) либо `None`."""
    if kind is None:
        try:
            from . import census
            kind = census.KNOWN.get(census.main_attribute(doc))
        except Exception:  # документ не формы объекта — вида нет
            kind = None
    if kind is None:
        return None, None
    if not _NORMS:
        _NORMS.update(patterns.load())
    return patterns.norm(_NORMS, kind, key), kind


def _lower_gap(vis, nbr, norm):
    """Шаг нижнего блока: сосед привязан к низу (обе границы), и ниже него есть ряд (элемент любого
    типа), тоже привязанный к низу, — шаг равен разности верхов; не больше двух норм `pair_pitch`,
    нормы нет — не больше самого шага. `None` — применять нечего (норма вида).
    """
    if not _bottom_bound(nbr):
        return None
    below = sorted(p.rect[1] for p in vis if _bottom_bound(p) and p.rect[1] > nbr.rect[1] + patterns.ROW_DY)
    if not below:
        return None
    got = below[0] - nbr.rect[1]
    return got if norm is None or got <= PITCH_CAP * norm else None


def _rows_pitch(same, vis, nbr_top):
    """Шаг строк по верхам элементов одного типа: верх строки соседа (самый высокий верх в пределах
    `ROW_DY` выше него) минус верх строки перед ней. `(шаг, помехи)`: `(None, [])` — строки выше
    нет; помехи — видимые элементы другого типа между двумя строками: они делают шаг блоком, а не
    строкой.
    """
    tops = [p.coords[N.Y] for p in same if p.coords[N.Y] <= nbr_top]
    row = min(t for t in tops + [nbr_top] if nbr_top - t <= patterns.ROW_DY)
    prior = [t for t in tops if t < row - patterns.ROW_DY]
    if not prior:
        return None, []
    last = max(prior)  # самый нижний верх предыдущей строки; верх самой строки — самый высокий
    before = min(t for t in prior if last - t <= patterns.ROW_DY)
    kinds = {p.type for p in same}
    between = [p for p in vis if p.type not in kinds and last + patterns.ROW_DY < p.coords[N.Y] < row - patterns.ROW_DY]
    return row - before, between


# ── Выбор места ───────────────────────────────────────────────────────────────────────────────

def _behaviours(doc, peers):
    """`{индекс: поведение по ширине}` у перечисленных элементов (`layout.horizontal_behaviour`); форма, которую раскладка не читает, — пусто."""
    from . import layout
    try:
        coef = layout.coefficients(layout.read(doc), hide=False)
    except (EditError, ValueError, KeyError, TypeError, IndexError):
        return {}
    return {p.index: layout.horizontal_behaviour(coef[p.index][2], coef[p.index][3])
            for p in peers if coef.get(p.index) is not None}


def _column_peer(doc, nbr, above, old, kind_of):
    """Образец горизонтальных привязок по столбцу нового элемента: `(образец, слова | None)`; вертикальные идут за соседом по ряду (`old`).

    Столбец — элементы того же типа не ниже соседа, у которых совпадают и левый, и правый край с новым элементом (новый встаёт под
    соседом и берёт ширину образца по ряду): поля разной ширины на одном x в столбец не входят. Если они ведут себя по ширине
    по-разному (остаются на месте, растягиваются, сдвигаются, меняются пропорционально), образцом служит нижний из тех, кого больше; при равенстве групп — самый
    близкий к месту. Образец не меняется, если он из выбранной группы. Элемента того же типа в столбце нет — образец прежний
    (по странице), и слова это говорят.
    """
    if old is None:
        return None, None
    x = nbr.coords[N.X]
    right = x + old.coords[N.WIDTH] - old.coords[N.X]          # правый край нового: ширину он берёт у образца по ряду
    column = [p for p in above if abs(p.coords[N.X] - x) <= COLUMN_DX and abs(p.coords[N.WIDTH] - right) <= COLUMN_DX]
    if not column:
        return old, (f"в столбце x={x} элементов типа {kind_of} нет — образец привязок {old.label()} взят по странице, "
                     "а не по столбцу")
    behaviour = _behaviours(doc, column)
    groups = {}
    for p in column:
        if p.index in behaviour and behaviour[p.index] is not None:
            groups.setdefault(behaviour[p.index], []).append(p)
    if len(groups) < 2:
        return (old if old in column or not column else _last(column)), None
    most = max(len(g) for g in groups.values())
    lowest = _last([p for g in groups.values() if len(g) == most for p in g])
    chosen = behaviour[lowest.index]
    tie = sum(1 for g in groups.values() if len(g) == most) > 1
    if old.index in behaviour and behaviour[old.index] == chosen:
        return old, None
    counts = ", ".join(f"{layout.behaviour_words(beh, 0, layout.LISTED)}: {len(g)}" for beh, g in groups.items())
    return lowest, (f"в столбце x={x} элементы типа {kind_of} ведут себя по-разному ({counts}); образец привязок {lowest.label()} — "
                    + ("групп поровну, взят ближайший к месту" if tie else "поведение большинства столбца"))


def _last(peers):
    return max(peers, key=lambda p: (p.coords[N.Y], p.order))


def _neighbour(peers, holder_label, after, kind_of):
    if after is not None:
        found = [p for p in peers if p.name == after]
        if not found:
            names = ", ".join(sorted(p.name for p in peers if p.name)) or "—"
            raise EditError(f"after={after!r}: такого элемента на этой странице {holder_label} нет (видимые: {names}); "
                            "сосед берётся из того же родителя и страницы")
        if len(found) > 1:
            raise EditError(f"after={after!r}: имя носят {len(found)} элемента родителя — к какому, по имени не решить")
        return found[0]
    if not peers:
        raise EditError(f"без box место берётся по соседям, а на этой странице {holder_label} элементов нет: "
                        "задайте box (первый элемент) либо after у элемента, который есть")
    same = [p for p in peers if p.type == kind_of]
    return _last(same or [p for p in peers if not _why_stuck(p)] or peers)


class _Ctx:
    """Всё, что не зависит от режима (`plain`/`grow`/`shrink`): сосед, шаг, размер, образец."""


def plan(doc, holder, holder_name, page, node, after=None, kind=None, anchor=None, unverified=False, grow=False, shrink=False,
         caption=None, date_mode="stand", cell=True):
    """Место нового `node` в `holder` на странице `page`: `Place` либо `EditError` словами (форма не
    тронута).

    Сначала место ищется как есть (`plain`: свободное либо раздвигание рядов); `grow`/`shrink`
    включаются, только когда без них места нет.
    """
    if grow and shrink:
        raise EditError("grow и shrink вместе не бывают: первый делает форму выше, второй ужимает таблицу — выберите одно")
    if grow and holder_name is not None:
        raise EditError(f"grow относится к форме: у панели «{holder_name}» высота — внешняя раскладка (её задают правила и размер "
                        "формы), и перекладывать содержимое панели операция не умеет. Освободите место box либо relayout формы")
    if grow and anchor is not None:
        raise EditError("grow с явным anchor не сочетается: края родителя для ролей считаются до роста формы, и привязка к низу "
                        "легла бы на старый край. Уберите anchor (правила возьмутся у образца) либо поставьте роль вторым вызовом set_anchors")
    c = _context(doc, holder, holder_name, page, node, after, kind, anchor, unverified, caption, date_mode)
    if c.widen_hit is not None:
        if shrink and lift_applies(c):
            try:
                return _decide_lift(c)
            except RoomRefusal as lift:
                raise EditError(f"{c.widen_hit}; и с shrink=true подъём нижнего блока не вышел: {lift.text}") from None
        raise c.widen_hit
    refusal, placed = None, None
    try:
        placed = _decide(c, "plain")
    except RoomRefusal as e:
        refusal = e
    if refusal is None and not placed.movers:
        return placed
    found = _free_cell(c, doc, holder, holder_name, page, node, kind, anchor, unverified, caption, date_mode) if cell else None
    if found is not None:  # место под соседом занято или не раздвигается, а клетка сетки рядом свободна: пара встаёт туда, форма не растёт
        return found
    if refusal is None:
        return placed
    plain = refusal
    if not (grow or shrink):
        raise plain
    flag = "grow=true" if grow else "shrink=true"
    try:
        if shrink and lift_applies(c):
            return _decide_lift(c)
        return _decide(c, "grow" if grow else "shrink")
    except RoomRefusal as second:
        same = "причина та же" if second.text == plain.text else second.text
        raise EditError(f"{plain.text}; и с {flag} места нет: {same}. {ADVICE[second.cause]}") from None


def _frames_of(c, rect):
    """Рамки группы, которые целиком содержат прямоугольник `rect`, как множество их индексов."""
    return {p.index for p in c.all if p.type == FRAME and p.rect[0] <= rect[0] and p.rect[1] <= rect[1] and rect[2] <= p.rect[2] and rect[3] <= p.rect[3]}


def _pair_label(c, field):
    """Надпись пары поля: ближайшая слева на его строке (не дальше 60 px) либо `None`."""
    labels = [q for q in c.vis if q.type == "Label" and abs(q.rect[1] - field.rect[1]) <= PAIR_DY and q.rect[2] <= field.rect[0] + 2
              and field.rect[0] - q.rect[2] <= 60]
    return max(labels, key=lambda q: q.rect[2]) if labels else None


def _real_column(c, last, members):
    """Настоящий столбец сетки: кроме последнего поля `last` есть ещё одно с теми же левым и правым краями на соседней строке выше (шаг больше
    `patterns.ROW_DY` и не больше двух норм шага), и у обоих своя надпись пары в одной колонке надписей. Одно поле (подполе строки, «Код на
    карте» справа от «Сотрудника») столбцом не считается.
    """
    same = [p for p in members if p is not last and abs(p.rect[0] - last.rect[0]) <= COLUMN_DX and abs(p.rect[2] - last.rect[2]) <= COLUMN_DX
            and patterns.ROW_DY < last.rect[1] - p.rect[1] <= PITCH_CAP * c.step]
    if not same:
        return False
    prev = max(same, key=lambda p: p.rect[1])
    a, b = _pair_label(c, last), _pair_label(c, prev)
    return a is not None and b is not None and abs(a.rect[0] - b.rect[0]) <= COLUMN_DX


def _free_cell(c, doc, holder, holder_name, page, node, kind, anchor, unverified, caption, date_mode):
    """Свободная клетка сетки (шапка из нескольких колонок пар «надпись + поле»): `Place` либо `None`.

    Новое поле встаёт не под соседом, а в столбце ПРАВЕЕ соседа на строке соседа (описание читает сетку по строкам, и поле не должно
    оказаться раньше соседа). Условия: (1) последнее поле столбца стоит выше этой строки не больше чем на два шага; (2) столбец непрерывен:
    между его последним полем и строкой клетки нет элемента, перекрывающего столбец по горизонтали; (3) клетка поля и клетка надписи его
    пары пусты (ни видимого, ни невидимого элемента; охватывающая рамка группы не мешает); (4) сосед, клетка и последнее поле столбца лежат
    в одних и тех же рамках группы; (5) слева от клетки на её строке нет чужой надписи ближе, чем зазор «надпись → поле» этого столбца.
    Образец размера и привязок — последнее поле столбца. Берётся ближайший по высоте столбец, при равенстве — ближайший по горизонтали.
    Место должно получиться без раздвигания рядов, роста формы и ужатия таблицы; слова называют клетку. Явный `anchor` и не поле ввода —
    клетку не ищем.
    """
    if c.kind_of != "TextBox" or anchor is not None or c.peer is None or c.nbr.type != "TextBox":
        return None
    nbr = c.nbr
    columns = {}
    for p in c.vis:
        if p.type != "TextBox" or p is nbr:
            continue
        key = next((x for x in columns if abs(x - p.rect[0]) <= COLUMN_DX), p.rect[0])
        columns.setdefault(key, []).append(p)
    found = []
    for x, members in columns.items():
        if x <= nbr.rect[0] + COLUMN_DX:
            continue
        last = _last(members)
        gap = nbr.rect[1] - last.rect[1]
        if not last.name or gap <= patterns.ROW_DY or gap > PITCH_CAP * c.step:
            continue
        if not _real_column(c, last, members):
            continue
        cell = (last.rect[0], nbr.rect[1], last.rect[2], nbr.rect[1] + (last.rect[3] - last.rect[1]))
        mate = _pair_label(c, last)
        zone = [cell] + ([(mate.rect[0], nbr.rect[1] + (mate.rect[1] - last.rect[1]), mate.rect[2], nbr.rect[1] + (mate.rect[3] - last.rect[1]))]
                         if mate is not None else [])
        if any(_hit(z, q.rect) and q.type != FRAME for z in zone for q in c.all):
            continue
        band = (last.rect[0], last.rect[3], last.rect[2], cell[1])        # между последним полем столбца и клеткой
        if any(q is not last and q.type != FRAME and _hit(band, q.rect) for q in c.all):
            continue
        if _frames_of(c, nbr.rect) != _frames_of(c, cell) or _frames_of(c, cell) != _frames_of(c, last.rect):
            continue
        start = zone[-1][0]
        near = max(last.rect[0] - mate.rect[2], 0) if mate is not None else MIN_CELL_GAP
        if any(q.type == "Label" and q is not mate and _same_line(q.rect, zone[-1]) and 0 <= start - q.rect[2] < max(near, MIN_CELL_GAP)
               for q in c.vis):
            continue
        found.append((gap, x - nbr.rect[0], last))
    for _gap, _dx, last in sorted(found, key=lambda f: f[:2]):
        try:
            c2 = _context(doc, holder, holder_name, page, node, last.name, kind, anchor, unverified, caption, date_mode, top=nbr.rect[1])
            placed = _decide(c2, "plain")
        except EditError:
            continue
        if placed.movers or placed.grow is not None:
            continue
        placed.words += (f"; {FREE_CELL_MARK}: столбец x={c2.box[0]}, строка y={c2.box[1]} — на этой строке «{nbr.name or nbr.index}» стоит в соседнем "
                         f"столбце слева, а здесь клетка поля и надписи пуста, поле встало после «{last.name}» без раздвигания рядов и роста формы")
        return placed
    return None


def _same_line(a, b):
    """Прямоугольники лежат на одной строке: пересекаются по высоте больше чем на половину меньшего."""
    inter = min(a[3], b[3]) - max(a[1], b[1])
    return inter * 2 >= min(a[3] - a[1], b[3] - b[1]) > 0


class _Damaged(EditError):
    """Испорченный документ: края родителя не вычислить (не то же, что «края для записи не
    проверялись», где проверка краёв пропускается).
    """


def _edges(doc, holder, page, unverified):
    """Края родителя для записи (`anchors.file_edges`); испорченный размер формы — отказ словами, а не
    трассировка.
    """
    from . import anchors as _anchors
    try:
        return _anchors.file_edges(doc, holder, page, unverified)
    except (TypeError, ValueError, KeyError, AttributeError):
        raise _Damaged("края родителя взять не из чего: размер формы или направляющие родителя не целые числа — документ испорчен, "
                       "место без box по такой форме не считается; задайте box") from None


def _caption_of(node):
    from . import shell
    return shell.caption_of(node)


def _caption_pad(type_):
    """Отступ подписи от левого края box у типов с подписью в самом элементе (`CAPTION_TYPES`) либо
    `None`.
    """
    if type_ not in CAPTION_TYPES:
        return None
    from . import render
    return {"Label": 0, "CheckBox": render.CHECK_CAPTION_PAD, "RadioButton": render.RADIO_CAPTION_PAD, "Button": render.BUTTON_CAPTION_PAD}[type_]


def _need(type_, pad, text, font=None):
    """Ширина элемента по подписи: отступ + самая длинная строка мерой `textwidth.measure` действующего
    шрифта нового элемента `font` (`textwidth.element_font` после оформления по соседям; нет
    описания — шрифт формы по умолчанию); знак вне таблицы — самый широкий; у надписи не меньше
    минимума платформы. Возвращает `(ширина, проверено, причина «не проверялось»)`.
    """
    lines = text.splitlines() or [text]
    got, exact, why = 0, True, []
    for line in lines:
        m = textwidth.measure(line, font)
        got = max(got, m.px)
        exact = exact and m.exact
        if m.why and m.why not in why:
            why.append(m.why)
    got += pad
    if type_ == "Label":
        from . import layout
        got = max(got, layout.MIN_SIZE["Label"][0])
    return got, exact, "; ".join(why)


def font_words(font):
    """Шрифт подписи словами для отчёта: `10 pt жирный` (размер неизвестен — `размер не известен`)."""
    font = font or textwidth.DEFAULT_FONT
    size = font.get("size")
    return ((f"{size:g} pt" if size is not None else "размер не известен") + (" жирный" if font.get("bold") else "")
            + (" курсив" if font.get("italic") else ""))


def pair_stats(doc, pairs, estimate=False):
    """Зазор и запас колонки надписей по её парам `[(имя надписи, узел надписи, рамка, левый край поля)]`: `(наименьший видимый зазор «текст →
    поле» | None, пара с ним, наименьший запас рамки за текстом, все ли шрифты проверены)`. Считаются только надписи в одну строку (по проверенному
    шрифту, а с `estimate` и по оценке); запас — у надписей с выравниванием по левому краю (у выровненной вправо или по центру текст сидит не у
    левого края), нет таких — 0. Берётся наименьшее: колонку задаёт самая плотная пара, а у коротких надписей рамка шире текста просто потому,
    что колонка шире их.
    """
    gaps, slacks, exact = [], [], True
    for name, node, rect, field_left in pairs:
        got = textgap.label_text_end(node, doc, rect, estimate)
        if got is None:
            if textgap.alignment(node) == "Left" and textgap.clipped(node, doc, rect):
                slacks.append(0)  # текст не помещается в рамку: колонка тесна, запаса нет
            continue
        exact = exact and got[2]
        gaps.append((field_left - got[0], name))
        if textgap.alignment(node) == "Left":
            slacks.append(max(rect[2] - rect[0] - got[1], 0))
    least = min(gaps, default=(None, None))
    return least[0], least[1], min(slacks, default=0), exact


def _column_pairs(peers, column):
    """Пары колонки надписей среди `peers` (видимые элементы родителя и страницы): надпись с левым краём в колонке и ближайшее поле ввода правее неё на её строке."""
    out = []
    for q in peers:
        if q.type != "Label" or abs(q.rect[0] - column) > COLUMN_DX:
            continue
        fields = [f for f in peers if f.type == "TextBox" and abs(f.rect[1] - q.rect[1]) <= PAIR_DY and f.rect[0] >= q.rect[2] - 2]
        if fields:
            out.append((q.name or q.index, q.item, q.rect, min(f.rect[0] for f in fields)))
    return out


def gap_need(doc, kind, ref_vis=None, ref_words=None):
    """Видимый зазор «конец текста надписи → поле», который держит новая пара: `(px, слова)`. Не меньше большего из двух чисел: зазор у
    пары-образца `ref_vis` (`ref_words` — какая это пара), но не больше нормы вида, и нижняя граница нормы вида `label_text_gap` (вид не
    определён или у него мало данных — общая по корпусу). Широкий зазор образца — чаще следствие ширины колонки надписей, а не замысла:
    у надписей короче колонки он велик сам, и требовать его от новой надписи значило бы выталкивать поле из колонки. `(None, слова)` —
    зазор взять неоткуда: пара ведётся по зазору рамок, как раньше.
    """
    parts, got = [], []
    _value, found = _norm(doc, kind, "label_text_gap")
    if not _NORMS:
        _NORMS.update(patterns.load())
    norm = patterns.gap_norm(_NORMS, found or kind)
    if ref_vis is not None:
        used = ref_vis if norm is None else min(ref_vis, norm)
        got.append(used)
        parts.append(f"{ref_words} {ref_vis} px" + (f", учтено не больше нормы вида — {used} px" if used != ref_vis else ""))
    floor, words = patterns.gap_floor(_NORMS, found or kind)
    if floor is not None:
        got.append(floor)
        parts.append(words)
    if not got:
        return None, "видимого зазора «текст надписи → поле» взять неоткуда (у образца нет текста, нормы нет) — пара ведётся по зазору рамок"
    return max(got), f"видимый зазор «текст → поле» не меньше {max(got)} px: " + "; ".join(parts)


def column_gap(doc, kind, pairs):
    """Правило колонки надписей по её парам (`pair_stats`): `(нужный видимый зазор | None, запас новой надписи, слова, шрифты проверены)`.
    Запас новой надписи — запас колонки, но не больше нужного зазора: рамка не должна уходить за конец текста дальше, чем идёт зазор до поля.
    """
    least, name, slack, exact = pair_stats(doc, pairs, True)
    need, words = gap_need(doc, kind, least, f"у самой плотной пары колонки надписей «{name}»" + ("" if exact else " (по оценке ширины: шрифт надписи не проверялся)"))
    return need, (slack if need is None else min(slack, need)), words, exact


DATE_ROLES = ("stand", "role", "sample")  # варианты поля даты по порядку: ширина умолчания, поле остаётся на месте; ширина умолчания и роль образца; ширина и роль образца
DATE_WORDS = {"stand": "ширина умолчания, поле остаётся на месте", "role": "ширина умолчания, привязки образца", "sample": "ширина и привязки образца"}


def existing_date(doc, composition, where=None):
    """Поле даты того же состава, которое уже есть на форме и не растягивается: `(ширина, слова)` либо `None`. «Только время» считается
    как «дата», «дата со временем» — отдельно. Порядок поиска: в столбце нового поля (тот же родитель и страница, тот же левый край),
    иначе ближайшее по вертикали на той же панели и странице, иначе ближайшее на форме. `where` — `(узел родителя | None, страница, левый край,
    верх)`; без него ищется ближайшее к верху формы.
    """
    group = "DateTime" if composition == "DateTime" else "Date"
    try:
        form = layout.read(doc)
        coefs = layout.coefficients(form, hide=False)
    except (EditError, ValueError, KeyError, TypeError, IndexError):
        return None
    holder, page, left, top = where if where is not None else (None, None, None, 0)
    found = []
    for h in form.holders.values():
        for it in h.children:
            if it.type != "TextBox" or not it.visible:
                continue
            got = textgap.date_composition(it.node)
            if got is None or ("DateTime" if got == "DateTime" else "Date") != group:
                continue
            c = coefs.get(it.index)
            if c is None or layout.horizontal_behaviour(c[2], c[3]) not in (layout.STANDS, layout.MOVES):
                continue
            same = where is not None and (h.node is holder or (holder is None and h.key == 0)) and it.page == page
            tier = 0 if same and left is not None and abs(it.box[0] - left) <= COLUMN_DX else 1 if same else 2
            found.append((tier, abs(it.box[1] - top), it.box[1], it.box[0], it))
    if not found:
        return None
    tier, _dy, _y, _x, it = min(found, key=lambda f: f[:4])
    where_words = ("в столбце нового поля", "на той же панели и странице", "на форме")[tier]
    # Ширина — как записана в файле (`stored`): новое поле пишется в координатах файла, а положение по правилам от области панели бывает дробным.
    box = it.stored or it.box
    return box[2] - box[0], f"как у поля даты «{it.name or it.index}» того же состава ({where_words}): {box[2] - box[0]} px"


def date_width(doc, composition, kind=None, where=None):
    """Ширина нового поля даты: `(px | None, слова)`. Сначала ширина поля даты того же состава, уже стоящего на форме (`existing_date`); иначе самая частая ширина
    ширины по формам корпуса — вида, а у вида с малым числом полей общая (`patterns.date_norm`). Поле «только время» своего умолчания не имеет
    и берёт «дата».
    """
    tail = "; у поля «только время» своего умолчания нет — взято умолчание «дата»" if composition == "Time" else ""
    got = existing_date(doc, composition, where)
    if got is not None:
        return got[0], f"ширина поля даты {got[0]} px — {got[1]}{tail}"
    _value, found = _norm(doc, kind, "date_field_width")
    if not _NORMS:
        _NORMS.update(patterns.load())
    key = patterns.DATE_KEYS.get(composition, patterns.DATE_KEYS["Date"])
    width, words = patterns.date_norm(_NORMS, found or kind, key)
    if width is None:
        return None, words
    return width, f"ширина поля даты {width} px — на форме нет поля даты этого состава, {words}{tail}"


def date_room(c, doc, kind, peer):
    """Правый край, до которого поле даты может дойти: край родителя минус правый отступ полей (`field_right_margin` вида, иначе отступ образца) либо `None`."""
    try:
        edge = _edges(doc, c.holder, c.page, c.unverified)[0]
    except _Damaged:
        raise
    except EditError:
        return None
    margin = _norm(doc, kind, "field_right_margin")[0]
    if margin is None and peer is not None:
        margin = max(edge - peer.rect[2], 0)
    return edge - (margin or 0)


def _refuse_widened(c, holder, page, unverified, left, top, height, text):
    """Подпись шире образца: надпись или флажок стали шире и наехали бы на элемент, стоявший правее на
    той же строке (поле пары, которое уже есть), либо вышли бы за край родителя. Раздвинуть поле
    вниз значило бы развалить пару — отказ словами.

    Наезд на стоящее поле — не немедленный отказ, а `EditError` в `c.widen_hit`: у `shrink` с
    подъёмом нижнего блока новый встаёт на прежний ряд соседа, а не на ряд ниже, где расположено поле, и
    наезд проверяется после подъёма (`_decide_lift`: `_collisions`). Край родителя — отказ сразу.
    """
    old_w, need = c.widened
    mine, orig = (left, top, left + need, top + height), (left, top, left + old_w, top + height)
    for p in c.all:
        if p.rect[0] >= orig[2] and _hit(mine, p.rect) and not _hit(orig, p.rect):
            c.widen_hit = EditError(
                f"подпись «{text}» ({need} px по textwidth) шире образца ({old_w} px) и наехала бы на «{p.name or p.index}» ({p.type}, x={p.rect[0]}) "
                "этой строки: поле пары уже есть, а колонку надписей по одному полю не сдвигают. Выходы: подпись короче; box с шириной и местом, "
                "которые вы выбрали; либо вставьте надпись ДО поля — поле встанет после неё с зазором пары")
            break
    try:
        right = _edges(c.doc, holder, page, unverified)[0]
    except _Damaged:
        raise
    except EditError:
        right = None
    if right is not None and left + need > right:
        raise EditError(f"подпись «{text}» ({need} px по textwidth) не помещается: от x={left} до края родителя {right - left} px. "
                        "Подпись короче либо box")


def _after_wide_label(c, doc, kind, peer, left, top, width, height):
    """Поле пары встаёт после надписи своей строки, если та длиннее колонки либо её текст подходит к колонке ближе нужного зазора.
    Надпись — в колонке надписей пары (её левый край — как у надписи пары соседа, а без неё — `label_left` вида), стоит на одной строке
    с местом (верх в пределах `PAIR_DY`) и ждёт поля (правее неё на строке никого). Такая надпись не двигается — левый край поля
    уходит вправо, правый остаётся на месте (у фиксированного поля сдвиг вправо вынес бы его за правый отступ формы, у растягивающегося
    он держится правилом), ширина уменьшается. Левый край поля — наибольший из двух: правый край надписи плюс зазор рамок пары и конец
    текста надписи плюс видимый зазор (`gap_need`: у пары-образца либо нижняя граница нормы вида — что больше). Не колонка надписей
    (заметка во всю ширину, подпись над блоком) или поле осталось бы уже минимума платформы — правило не применяется. Возвращает
    `(левый край, ширина)`; слова — в `c.pair_note`.
    """
    new = (left, top, left + width, top + height)
    field = c.nbr if c.nbr.type == "TextBox" else peer
    own = [] if field is None else [p for p in c.vis if p.type == "Label" and p.rect[2] <= field.rect[0]
                                    and p.rect[1] < field.rect[3] and field.rect[1] < p.rect[3]]
    near = max(own, key=lambda p: p.rect[2]) if own else None
    column = near.rect[0] if near is not None else _norm(doc, kind, "label_left")[0]
    if column is None:  # колонки надписей взять неоткуда (нет образца и нормы `label_left`): место как есть
        return left, width
    need_gap, _slack, gap_words, _exact = column_gap(doc, kind, _column_pairs(c.vis, column))

    def waits(p):
        """Ждёт поля: правее неё на строке никого, и она свободна — не лежит на панели, командной
        панели или другом элементе (подпись на нижней панели — часть панели, а не надпись пары;
        рамка группы не в счёт).
        """
        return not any(q.index != p.index and (q.rect[0] >= p.rect[2] and q.rect[1] < p.rect[3] and p.rect[1] < q.rect[3]
                                       or q.type != FRAME and _hit(p.rect, q.rect)) for q in c.all)

    def reaches(p):
        """Текст надписи с видимым зазором не умещается до места: конец текста плюс зазор правее левого края поля."""
        got = None if need_gap is None else textgap.label_text_end(p.item, doc, p.rect, True)
        return got is not None and got[0] + need_gap > left
    labels = [p for p in c.vis if p.type == "Label" and p.rect[0] == column and p.rect[0] < left and abs(p.rect[1] - top) <= PAIR_DY
              and (p.rect[2] > left and _hit(new, p.rect) or reaches(p)) and waits(p)]
    if not labels:
        return left, width
    label = max(labels, key=lambda p: p.rect[2])
    if near is not None:
        gap, gap_from = field.rect[0] - near.rect[2], f"как у пары «{near.name or near.index}» → «{field.name or field.index}»"
    else:
        gap, found = _norm(doc, kind, "label_field_gap")
        gap_from = f"норма вида «{found}» (label_field_gap)"
        if gap is None:
            return left, width
    new_left = label.rect[2] + gap
    seen = None if need_gap is None else textgap.label_text_end(label.item, doc, label.rect, True)
    visible = ""
    if seen is not None and seen[0] + need_gap > new_left:
        new_left = seen[0] + need_gap
        visible = f"; левый край — по видимому зазору: конец текста надписи x={seen[0]} + {need_gap} px ({gap_words})"
    elif seen is not None:
        visible = f"; видимый зазор «текст → поле» {new_left - seen[0]} px — не меньше нужного ({need_gap}: {gap_words})"
    if c.date_fixed:  # поле даты не растягивается: ширина умолчания остаётся, правый край сдвигается за левым, пока есть место до края родителя
        room = c.date_room
        shown = _caption_of(label.item) or label.name or label.index
        if room is not None and room - new_left < MIN_FIELD_W:
            raise EditError(
                f"подпись «{shown}» шире столбца надписей: поле даты после неё (x от {new_left}) вышло бы за край родителя с отступом ({room}): "
                f"места {room - new_left} px, меньше минимума поля {MIN_FIELD_W}. Выходы: подпись короче; явный box у поля (ширину и место назовёте вы)")
        narrowed = ""
        if room is not None and new_left + width > room:
            narrowed = f"; ширина {width} → {room - new_left}: правее нет места до края родителя с отступом ({room})"
            width = room - new_left
        c.date_fixed = width
        c.pair_note = (f"поле сдвинуто: подпись «{shown}» шире столбца надписей; "
                       f"поле даты встало после надписи «{label.name or label.index}» (x={new_left}, зазор рамок пары {gap} — {gap_from}), "
                       f"а не колонкой (x={left}); правый край {new_left + width}{narrowed or '; ширина остаётся'}{visible}")
        return new_left, width
    right = left + width  # правый край поля — край колонки, он остаётся; ширина уменьшается
    text = _caption_of(label.item) or label.name or label.index
    have = (near.rect[2] - near.rect[0]) if near is not None else left - column - gap  # столбец надписей: ширина надписи пары соседа, а без неё — до поля за зазором
    need = label.rect[2] - label.rect[0]
    if right - new_left < MIN_FIELD_W or (right - new_left) * 2 < width:
        raise EditError(
            f"подпись «{text}» шире столбца надписей (нужно {need}, столбец {have}): поле после неё и зазора пары {gap} стало бы шириной "
            f"{right - new_left} px (x от {new_left} до прежнего правого края {right}; было {width}) — "
            f"{'уже минимума платформы ' + str(MIN_FIELD_W) if right - new_left < MIN_FIELD_W else 'меньше половины прежней'}. "
            "Выходы: подпись короче (caption); явный box у поля (ширину и место назовёте вы)")
    over = label.rect[2] + gap - left
    c.pair_note = (f"поле сдвинуто: подпись «{text}» шире столбца надписей (нужно {need}, столбец {have}); "
                   f"подпись длиннее колонки на {over} px: поле встало после надписи «{label.name or label.index}» (x={new_left}, зазор пары {gap} — "
                   f"{gap_from}), а не колонкой (x={left}); ширина {width} → {right - new_left}, правый край {right} прежний{visible}")
    return new_left, right - new_left


def _context(doc, holder, holder_name, page, node, after, kind, anchor, unverified, caption=None, date_mode="stand", top=None):
    from . import anchors as _anchors
    c = _Ctx()
    c.doc, c.holder, c.page, c.node, c.anchor, c.unverified = doc, holder, page, node, anchor, unverified
    c.where = "формы" if holder_name is None else f"панели «{holder_name}»"
    c.holder_name = holder_name
    c.vis = _peers(holder, page)
    c.all = _peers(holder, page, hidden=True)
    c.kind_of, c.kind = node.get("type"), kind
    c.nbr = nbr = _neighbour(c.vis, c.where, after, c.kind_of)
    same = [p for p in c.vis if p.type == c.kind_of]
    above = [p for p in same if p.coords[N.Y] <= nbr.coords[N.Y]]
    c.peer = peer = nbr if nbr.type == c.kind_of else (_last(above or same) if same else None)
    c.peer_h, c.column_words = _column_peer(doc, nbr, above, peer, c.kind_of)  # образец для привязок по горизонтали; по вертикали — `c.peer`
    step, between = _rows_pitch(same, c.vis, nbr.coords[N.Y])
    norm, found = _norm(doc, kind, "pair_pitch")
    c.step_from = "по двум последним строкам блока"
    why = None
    if step is not None and between:
        shown = ", ".join(f"{p.label()} ({p.type})" for p in between[:3]) + (" …" if len(between) > 3 else "")
        why = f"строка выше отделена {shown}: шаг через блок — не шаг строк"
    elif step is not None and norm is not None and step > PITCH_CAP * norm:
        why = f"шаг по строкам {step} больше двух норм вида ({PITCH_CAP * norm}): строки не смежны"
    if (step is None or why is not None) and _lower_gap(c.vis, nbr, norm) is not None:
        step = _lower_gap(c.vis, nbr, norm)
        c.step_from = f"по ряду ниже соседа в нижнем блоке (оба привязаны к низу, шаг блока — его собственный, а не норма вида)"
    elif step is None or why is not None:
        if norm is None:
            raise EditError(
                "шаг строк взять неоткуда: " + (why + ", а нормы вида формы нет" if why else
                    "в блоке (у соседа " + nbr.label() + ") одна строка элементов такого типа, а нормы вида формы нет")
                + f" ({'вид ' + repr(found) + ' без нормы' if found else 'вид формы не определён: основной реквизит не объект справочника или документа'}). "
                "Задайте kind=<вид из patterns.json> либо box")
        step = norm
        c.step_from = (f"по норме вида «{found}» (pair_pitch): " + (why or "в блоке одна строка"))
    c.step = step
    text = caption if isinstance(caption, str) and caption.strip() else None
    pad = _caption_pad(c.kind_of)
    font = textwidth.element_font(node, doc) if pad is not None else None  # оформление по соседям записано до `plan` (`add_element`): шрифт узла — действующий
    need, exact, why_est = (None, True, "") if pad is None or text is None else _need(c.kind_of, pad, text, font)
    c.font_words = None
    if need is not None:
        c.font_words = (f"шрифт подписи {font_words(font)}" if font and (font.get("size") != textwidth.DEFAULT_SIZE or font.get("bold")
                                                                           or font.get("italic")) else None)
        if not exact:
            c.font_words = (f"шрифт подписи {font_words(font)} не проверялся ({why_est}): ширина {need} px по оценке, не по шрифту предприятия — "
                            "проверьте подпись в конструкторе")
    c.widened = None
    if peer is not None:
        width = peer.coords[N.WIDTH] - peer.coords[N.X]
        height = peer.coords[N.HEIGHT] - peer.coords[N.Y]
        c.size_from = f"как у {peer.label()}"
        if need is not None and need > width:
            slack = column_gap(doc, kind, _column_pairs(c.vis, peer.rect[0]))[1] if c.kind_of == "Label" else 0  # запас рамки надписи за текстом — колонки надписей: у новой надписи такой же
            if slack:  # запас не должен занимать место, которого нет: до ближайшего элемента правее на строке и до края родителя
                x0, y0 = nbr.coords[N.X], nbr.coords[N.Y] + step
                rights = [p.rect[0] for p in c.all if p.rect[0] >= x0 + need and p.rect[1] < y0 + height and y0 < p.rect[3]]
                try:
                    rights.append(_edges(doc, holder, page, unverified)[0])
                except _Damaged:
                    raise
                except EditError:
                    pass
                limit = min(rights) if rights else None
                if limit is not None:
                    slack = max(min(slack, limit - x0 - need), 0)
                partners = [q for q in c.vis if q.type == "TextBox" and abs(q.rect[1] - peer.rect[1]) <= PAIR_DY and q.rect[0] >= peer.rect[2] - 2]
                if partners:  # поле пары образца после надписи с запасом не должно стать уже половины прежней ширины и минимума поля
                    f = min(partners, key=lambda q: q.rect[0])
                    left_over = f.rect[2] - (x0 + need) - max(f.rect[0] - peer.rect[2], 0) - max(MIN_FIELD_W, -(-(f.rect[2] - f.rect[0]) // 2))
                    slack = max(min(slack, left_over), 0)
            c.widened = (width, need + slack)
            c.size_from += (f"; подпись «{text}» шире образца по textwidth ({need} px против {width}: текст {need - pad}"
                            + (f" + отступ подписи {pad}" if pad else "") + f") — ширина {need + slack}"
                            + (f" (текст {need} + запас {slack}, как у колонки надписей)" if slack else ""))
            c.size_from += f" ({c.font_words})" if c.font_words else ""
            width = need + slack
    elif c.kind_of in ("Label", "CheckBox", "Button"):
        # Надпись и флажок без образца того же типа: высота — норма вида (`label_height`; у флажка
        # нормы нет), нет нормы — высота конструктора (надпись 19, флажок 15); ширина — по тексту
        # подписи. Стиль «во всю строку» (`ShellStyle.flags_full`) тут не бывает: образца того же
        # типа в блоке нет.
        if need is None:
            raise EditError(
                f"размер взять неоткуда: в блоке нет элемента типа {c.kind_of}, а ширина берётся по тексту подписи, и подписи нет. "
                "Задайте caption (ширина — по textwidth) либо box")
        norm_h, found = _norm(doc, kind, "label_height") if c.kind_of == "Label" else (None, None)
        if norm_h is not None:
            height, h_from = norm_h, f"норма вида «{found}» (label_height)"
        elif c.kind_of == "Button":
            height, h_from = BUTTON_H, "кнопка формы 23 (нормы вида нет)"
        else:
            height = LABEL_H if c.kind_of == "Label" else FLAG_H
            h_from = (f"высота конструктора (у вида нормы {'label_height ' if c.kind_of == 'Label' else 'флажка '}нет): "
                      f"{'надпись' if c.kind_of == 'Label' else 'флажок'} {height}")
        width = need
        c.size_from = (f"по тексту подписи «{text}»: ширина {need} px по textwidth"
                       + (f" (текст {need - pad} + отступ подписи {pad})" if pad else "")
                       + (f" ({c.font_words})" if c.font_words else "") + f", высота {height} — {h_from}; "
                       "элементов такого типа в блоке нет")
    else:
        # Шаблон размера не несёт: «взять у шаблона» — нулевой элемент. Норма есть у поля ввода
        # (высота `field_height`, ширина до правого края родителя минус `field_right_margin`), у
        # надписи и флажка — по подписи. У прочих типов без образца размера взять неоткуда — отказ,
        # а не угаданная ширина.
        height_norm, found = _norm(doc, kind, "field_height") if c.kind_of == "TextBox" else (None, None)
        margin, _f = _norm(doc, kind, "field_right_margin") if c.kind_of == "TextBox" else (None, None)
        try:
            right = _edges(doc, holder, page, unverified)[0]
        except _Damaged:
            raise
        except EditError:
            right = None
        if height_norm is None or margin is None or right is None or right - margin - nbr.coords[N.X] < 11:
            raise EditError(
                f"размер взять неоткуда: в блоке нет элемента типа {c.kind_of}, а норма есть только у поля ввода (TextBox: "
                "field_height и field_right_margin вида формы, край родителя); у надписи и флажка размер берётся по подписи "
                "(нужен caption). У кнопки, переключателя и прочих типов нормы нет. Задайте box либо поставьте образец такого типа")
        width, height = right - margin - nbr.coords[N.X], height_norm
        c.size_from = "по норме вида (field_height, field_right_margin); элементов такого типа в блоке нет"
    if not exact and c.font_words and c.font_words not in c.size_from:
        c.size_from += f"; {c.font_words}"
    c.date_fixed, c.date_room, c.date_role = None, None, date_mode
    composition = textgap.date_composition(node) if c.kind_of == "TextBox" else None
    if composition is not None and date_mode != "sample":  # поле даты: ширина умолчания вместо ширины образца, и не растягивается
        got, words = date_width(doc, composition, kind, (holder, page, nbr.coords[N.X], nbr.coords[N.Y] + step))
        if got is not None:
            c.date_room = date_room(c, doc, kind, peer)
            room = None if c.date_room is None else c.date_room - nbr.coords[N.X]
            if room is not None and got > room:
                if room < MIN_FIELD_W:
                    raise EditError(f"поле даты шириной {got} не помещается: от x={nbr.coords[N.X]} до края родителя с отступом {room} px, меньше минимума "
                                    f"поля {MIN_FIELD_W}. Задайте box либо освободите место")
                words += f"; ширина {got} → {room}: правее нет места до края родителя с отступом ({c.date_room})"
                got = room
            width, c.date_fixed = got, got
            c.size_from = f"{words}; поле даты не растягивается (высота как у {peer.label() if peer is not None else 'нормы вида'})"
    elif composition is not None:
        c.size_from += "; поле даты по ширине и привязкам как у образца (умолчание даты сужало растяжение формы)"
    left = nbr.coords[N.X]
    top = nbr.coords[N.Y] + step if top is None else top  # `top` задаёт строку явно: клетка сетки в соседнем столбце
    c.column = left
    c.pair_note = None
    c.widen_hit = None
    if c.widened is not None:
        _refuse_widened(c, holder, page, unverified, left, top, height, text)
    if c.kind_of == "TextBox":
        left, width = _after_wide_label(c, doc, kind, peer, left, top, width, height)
    c.box = (left, top, width, height)
    c.new = (left, top, left + width, top + height)
    try:
        c.edge = _edges(doc, holder, page, unverified)[1]
    except _Damaged:
        raise
    except EditError:
        c.edge = None
    c.all_holder = _peers_all(holder)
    c.names = {p.index: p.name for p in c.all_holder}
    return c


def _encloses(p, c):
    """Рамка группы, охватывающая место: содержит новое по ширине, начинается не ниже соседа и
    кончается ниже верха места.
    """
    x, y, r, b = p.rect
    return (p.type == FRAME and p is not c.nbr and x <= c.new[0] and c.new[2] <= r
            and y <= c.nbr.coords[N.Y] and c.new[1] < b)


def _side_delta(D, target, side):
    """Сдвиг стороны объекта: у сдвигающегося вместе с окном — своя, у прочих и у края родителя — ноль. `None` — центр при
    нечётной сумме.
    """
    shift = D.get(target)
    if target == 0 or shift is None:
        return 0
    if side == SIDE_TOP:
        return shift[0]
    if side == SIDE_BOTTOM:
        return shift[1]
    if side == SIDE_CENTER_V:
        total = shift[0] + shift[1]
        return None if total % 2 else total // 2
    return 0


def _decide(c, mode):
    """Место в режиме `plain` (свободно либо раздвинуть ряды), `grow` (форма выше на шаг) или `shrink`
    (ужать таблицу).
    """
    grow, shrink = mode == "grow", mode == "shrink"
    step, new = c.step, c.new
    left, top, width, height = c.box
    edge = None if c.edge is None else c.edge + (step if grow else 0)
    if edge is not None and new[3] > edge:
        raise RoomRefusal(f"новый элемент ({left}, {top}, {width}, {height}) вышел бы за низ {c.where}: низ {new[3]} > {edge}", "E")
    frames = [p for p in c.all if _encloses(p, c)]
    frame_ids = {id(p) for p in frames}
    busy = [p for p in c.all if id(p) not in frame_ids and _hit(new, p.rect)]
    grow_op = _grow_op(c, step) if grow else None
    if not busy:
        for f in frames:
            if new[3] > f.rect[3]:
                raise RoomRefusal(f"новый элемент ({left}, {top}, {width}, {height}) выходит за низ рамки {f.label()} ({f.rect[3]}): "
                                  "расширять рамку операция умеет только вместе с раздвиганием рядов", "C")
        if grow:
            _refuse_centre_bound(c, step)
        peer_rules, peer, notes = _peer_rules(c, grow_op)
        words = ("; место свободно — раздвигать нечего"
                 + ("; форма выше на %d (grow): высота %d → %d, сдвигать нечего — новому не хватало места под последней строкой"
                    % (step, grow_op[1] - step, grow_op[1]) if grow else ""))
        return _place(c, words, [], [], peer_rules, peer, notes, grow_op)
    threshold = top - step // 2
    reasons = {id(p): _stuck_reasons(p) for p in c.all}

    def rides(p):
        if p.rect[1] < threshold:
            return False
        got = reasons[id(p)]
        return not got or (grow and set(got) == {BOTTOM_WORDS})
    squeeze = {}
    for p in busy:
        if shrink and p.rect[1] >= threshold and reasons[id(p)] and _squeezable(p):
            squeeze[id(p)] = p
        elif not rides(p) and reasons[id(p)]:
            raise RoomRefusal(
                f"место ({left}, {top}) занято элементом {p.label()} ({p.type}), который {reasons[id(p)][0]}: он не сдвигается, "
                "и раздвинуть форму вниз некуда — наезда операция не пишет", _stuck_cause(p))
        elif p.rect[1] < threshold:
            raise RoomRefusal(
                f"место ({left}, {top}) занято элементом {p.label()} ({p.type}), который начинается выше места "
                f"(верх {p.coords[N.Y]}): сдвинуть вниз нечего", "C")
    for f in frames:
        if set(reasons[id(f)]) - {BOTTOM_WORDS}:
            raise RoomRefusal(f"рамка {f.label()}, охватывающая место, {[r for r in reasons[id(f)] if r != BOTTOM_WORDS][0]}: "
                              "её низ не вырастет вместе с рядами", "C")
    riders = [p for p in c.all if p.rect[1] >= threshold and rides(p) and id(p) not in squeeze]
    # сдвиги границ (верх, низ) двигавшихся: сдвигающийся вместе с окном — (шаг, шаг), ужатый — (шаг, 0), рамка — (0,
    # шаг)
    while True:
        Dp = {id(p): (step, step) for p in riders}
        Dp.update({i: (step, 0) for i in squeeze})
        Dp.update({id(f): (0, step) for f in frames})
        by_id = {id(p): p for p in c.all}
        hits = _collisions(c.all, Dp, new, frame_ids)
        added = False
        if shrink:
            for _p, q in hits:
                if q is not None and id(q) not in Dp and q.rect[1] >= threshold and reasons[id(q)] and _squeezable(q):
                    squeeze[id(q)] = q
                    added = True
        if not added:
            break
    Di = {by_id[i].index: shift for i, shift in Dp.items()}
    adjust = _vertical_adjust(c, Di)
    movers = [(p.label(), p.coords, *Dp[id(p)]) for p in c.all if id(p) in Dp]
    rules_peer = c.peer
    if rules_peer is not None and rules_peer.index in Di:
        raise EditError(
            f"образец привязок {rules_peer.label()} лежит ниже места и при сдвиге сам поедет: привязки у него читать нельзя. "
            "Задайте anchor= (роль строкой либо {\"h\": …, \"v\": …}) либо after у элемента того же типа выше")
    # проверки после сдвига
    least = {}
    if squeeze:
        least = _squeeze_minimum(c, list(squeeze.values()), step)
    for p, q in hits:
        if p is None:
            raise RoomRefusal(
                f"новый элемент ({left}, {top}, {width}, {height}) лёг бы поверх элемента {q.label()} ({q.type}): после сдвига на "
                f"{step} его верх {_moved(q, Dp)[1]}, а низ нового {new[3]} — сдвиг не освободил место"
                + (f" (элемент {reasons[id(q)][0]})" if reasons[id(q)] else ""), "E")
        raise RoomRefusal(
            f"после сдвига на {step} элемент {p.label()} наехал бы на {q.label()}"
            + (f", который {reasons[id(q)][0]}" if reasons[id(q)] else "") + ": освободить место нельзя",
            _stuck_cause(q) if reasons[id(q)] else "E")
    if edge is not None:
        for p in c.all:
            if id(p) in Dp and p.rect[3] <= edge < _moved(p, Dp)[3]:
                raise RoomRefusal(f"элемент {p.label()} после сдвига вышел бы за низ {c.where} ({_moved(p, Dp)[3]} > {edge}): "
                                  f"форме не хватает {_moved(p, Dp)[3] - edge} px", "E")
    squeezed = [(p, p.rect[3] - p.rect[1], least[id(p)]) for p in squeeze.values()]
    if grow:
        _refuse_centre_bound(c, step)
    peer_rules, peer, notes = _peer_rules(c, grow_op)
    # слова
    shown = lambda ps: ", ".join(p.label() for p in ps)
    hidden = [p for p in riders if not p.visible]
    aside = [p for p in riders if p.rect[2] <= new[0] or p.rect[0] >= new[2]]
    if grow:
        words = (f"; форма выше на {step} (grow): высота {grow_op[1] - step} → {grow_op[1]}; место занято — сдвинуты вниз на {step} "
                 f"(box и правила «к верху», у привязанных к низу правило к низу прежнее): {shown(riders)}")
    else:
        words = f"; место занято — сдвинуты вниз на {step} (box и правила «к верху»): {shown(riders)}"
    if squeezed:
        words += ("; ужаты сверху на %d (shrink; низ и правило к низу на месте): " % step
                  + ", ".join(f"{p.label()} ({p.type}) высота {h} → {h - step}, минимум {m}" for p, h, m in squeezed)
                  + " — таблица стала ниже на %d px, раскладка при сжатии окна перестанет меняться на шаг раньше" % step)
    if getattr(c, "dpi_note", None):
        words += f"; {c.dpi_note}"
    if frames:
        words += f"; рамка, охватывающая место, выросла низом на {step}: {shown(frames)}"
    if hidden:
        words += f"; невидимые сдвигаются со своей строкой: {shown(hidden)}"
    if aside:
        words += (f"; в том числе вне столбца нового ({shown(aside)}): в другом столбце открыта пустая строка, а нового поля рядом "
                  "с ними нет (то же поле там — вторым вызовом, after=); у пары «надпись + поле» это вторая половина строки")
    return _place(c, words, movers, adjust, peer_rules, peer, notes, grow_op)


def _bottom_bound(p):
    """Обе вертикальные границы привязаны к низу родителя одним правилом каждая, вторых правил нет (ряд
    нижнего блока: высота постоянна, сдвигается вместе с низом формы).
    """
    top0, top1, low0, low1 = (_rule(p.coords, border, which) for border in (0, 1) for which in (0, 1))
    return (top1 is None and low1 is None and top0 is not None and low0 is not None
            and top0[0] == 0 and top0[1] == SIDE_BOTTOM and low0[0] == 0 and low0[1] == SIDE_BOTTOM)


def _lift_tables(c):
    """Ужимаемые таблицы выше соседа (низ таблицы не ниже верха соседа): ближайшая снизу — первая."""
    return sorted((p for p in c.all if _squeezable(p) and p.rect[3] <= c.nbr.rect[1]), key=lambda p: -p.rect[3])


def lift_applies(c):
    """Какую сторону берёт `shrink`: подъём нижнего блока — когда место занято привязанным к низу рядом
    (обе границы), а сосед сам из нижнего блока и над ним есть ужимаемая таблица. Занято тем, что
    ниже, или таблицей — прежний `shrink` (таблица ниже места ужимается сверху).
    """
    return (_bottom_bound(c.nbr) and bool(_lift_tables(c))
            and any(_hit(c.new, p.rect) and _bottom_bound(p) for p in c.all))


def _decide_lift(c):
    """`shrink` вверх: место занято рядом нижнего блока — ряд соседа и всё, что над ним до таблицы,
    поднимается на шаг, таблица над блоком ужимается снизу на шаг, новый элемент встаёт на прежнее
    место ряда соседа, привязки как у образца.

    Блок подъёма — элементы страницы с верхом от низа таблицы до места минус полшага: все обязаны
    быть привязаны к низу обеими границами (`_bottom_bound`); в других столбцах поднимаются вместе.
    Остальные не трогаются. Правила пересчитываются той же формулой, что у сдвига вниз
    (`_vertical_adjust`).
    """
    import copy
    step, step_from = c.step, c.step_from
    table = _lift_tables(c)[0]
    threshold = c.nbr.rect[1] + step - step // 2
    block = [p for p in c.all if p is not table and table.rect[3] <= p.rect[1] < threshold]
    for p in block:
        if _bottom_bound(p):
            continue
        low = sum(1 for border in (0, 1) if any(r[N.RULE_OBJECT] == 0 and r[N.RULE_SIDE] == SIDE_BOTTOM for r in _rules_of(p.coords, (border,))))
        if low == 1:
            raise RoomRefusal(f"подъём нижнего блока: {p.label()} ({p.type}) привязан к низу одной границей (растянут или привязан иначе): "
                              "поднять его на шаг значило бы изменить высоту — операция так не делает", "B")
        raise RoomRefusal(f"подъём нижнего блока: между таблицей {table.label()} и местом находится {p.label()} ({p.type}, верх {p.rect[1]}), "
                          "который не привязан к низу: он не поднимется, а ряды выше него без него не поднять", "C")
    left, _top, width, height = c.box
    top = c.nbr.rect[1]  # новый — на прежнем месте ряда соседа
    work = copy.copy(c)
    work.box, work.new = (left, top, width, height), (left, top, left + width, top + height)
    work.step, work.step_from = step, step_from
    Dp = {id(p): (-step, -step) for p in block}
    Dp[id(table)] = (0, -step)
    by_id = {id(p): p for p in c.all}
    Di = {by_id[i].index: shift for i, shift in Dp.items()}
    adjust = _vertical_adjust(c, Di)
    least = _squeeze_minimum(c, [table], step)
    for p, q in _collisions(c.all, Dp, work.new, set()):
        if p is None:
            raise RoomRefusal(f"подъём нижнего блока: новый элемент ({left}, {top}, {width}, {height}) лёг бы поверх {q.label()} ({q.type}) "
                              "после подъёма", "E")
        raise RoomRefusal(f"подъём нижнего блока: после подъёма на {step} элемент {p.label()} наехал бы на {q.label()}", "E")
    if c.peer is not None and c.anchor is None and c.peer.index not in {b.index for b in block}:
        raise EditError(f"подъём нижнего блока: образец привязок {c.peer.label()} не из блока подъёма — привязки нового скопировать не с кого "
                        "(новый встаёт в нижний блок, а правила образца не к низу). Задайте anchor= (например {\"h\": \"left\", \"v\": \"bottom\"})")
    if c.peer is None and c.anchor is None:
        raise EditError("подъём нижнего блока: образца привязок того же типа в блоке нет — «к себе» новому в нижнем блоке не подходит. "
                        "Задайте anchor= (например {\"h\": \"left\", \"v\": \"bottom\"})")
    peer_rules, peer, notes = _peer_rules(work, None)
    shown = ", ".join(p.label() for p in sorted(block, key=lambda p: (p.rect[1], p.rect[0])))
    aside = [p for p in block if p.rect[2] <= work.new[0] or p.rect[0] >= work.new[2]]
    height_was = table.rect[3] - table.rect[1]
    words = (f"; место занято рядом нижнего блока, привязанным к низу — выбрана сторона «подъём» (shrink): подняты на {step} (box и правила "
             f"к низу): {shown}; таблица {table.label()} ({table.type}) ужата снизу на {step} (низ и правило к низу, верх на месте): "
             f"высота {height_was} → {height_was - step}, минимум {least[id(table)]}, таблица стала ниже на {step} px, раскладка при сжатии окна "
             f"перестанет меняться на шаг раньше; новый — на прежнем месте ряда {c.nbr.label()} ({left}, {top}); ниже места ничего не тронуто")
    if getattr(c, "dpi_note", None):
        words += f"; {c.dpi_note}"
    if aside:
        words += (f"; в том числе вне столбца нового ({', '.join(p.label() for p in aside)}): поднимаются вместе, в другом столбце "
                  "освобождается строка под ними")
    movers = [(p.label(), p.coords, *Dp[id(p)]) for p in c.all if id(p) in Dp]
    return _place(work, words, movers, adjust, peer_rules, peer, notes, None)


def _vertical_adjust(c, Di):
    """Пересчёт вертикальных правил при сдвиге границ `Di` (`{индекс: (сдвиг верха, сдвиг низа)}`):
    смещение += сдвиг своей границы − сдвиг стороны объекта; несдвигаемому такой пересчёт невозможен
    — отказ. Общий для сдвига вниз и подъёма.
    """
    adjust = []
    for p in c.all_holder:
        for border in (0, 1):
            for rule in _rules_of(p.coords, (border,)):
                target, side = rule[N.RULE_OBJECT], rule[N.RULE_SIDE]
                own = Di.get(p.index, (0, 0))[border]
                under = _side_delta(Di, target, side)
                if under is None:
                    raise RoomRefusal(f"правило элемента {p.label()} к центру сдвигаемого {_label(c, target)} при нечётном сдвиге "
                                      f"{Di[target][0] + Di[target][1]} дало бы дробь", "C")
                change = own - under
                if not change:
                    continue
                if p.index not in Di:
                    raise RoomRefusal(
                        f"элемент {p.label()} привязан по вертикали к сдвигаемому элементу #{target}: при сдвиге он поехал бы сам, "
                        "а не остался на месте", "D")
                adjust.append((rule, change))
    return adjust


def _label(c, index):
    return f"«{c.names[index]}»" if c.names.get(index) else f"#{index}"


def _moved(p, Dp):
    x, y, r, b = p.rect
    dt, db = Dp.get(id(p), (0, 0))
    return x, y + dt, r, b + db


def _collisions(peers, Dp, new, skip):
    """Пары `(двигавшийся, другой)`, которые после сдвига пересекаются, а до него нет, и пары `(None,
    q)` — новый против `q` после
    сдвига. Рамки, охватывающие место (`skip`), с новым не сверяются: оно внутри них по построению.
    """
    out = []
    for p in peers:
        if id(p) not in Dp:
            continue
        now = _moved(p, Dp)
        for q in peers:
            if q is not p and _hit(now, _moved(q, Dp)) and not _hit(p.rect, q.rect):
                out.append((p, q))
    for q in peers:
        if id(q) not in skip and _hit(new, _moved(q, Dp)):
            out.append((None, q))
    return out


# Допуск DPI 120: минимум высоты таблицы 49 проверен при DPI 96, а форма DPI 120 в предприятии
# показана 1 : 1 (расхождений дальше 0 px — одно наблюдение одной формы). Допуск — только для ужатия
# таблицы (`shrink` обеих сторон) и только когда «не проверялось» только из-за DPI 120 (шрифты
# таблицы и шапки — по умолчанию); `layout.min_size` и раскладка DPI 120 остаются «не проверялось».
# DPI 144 и прочие — отказ.
TABLE_MIN_DPI120 = 120
DPI120_WORDS = "минимум таблицы 49 проверен при DPI 96; форма DPI 120 показана 1 : 1 (одно наблюдение одной формы)"


def _table_dpi120_ok(item):
    """«Не проверялось» у таблицы — только из-за DPI 120: форма DPI 120, шрифт шапки (`content/u2/u0`)
    — по умолчанию (у таблицы шрифта элемента `content/u1/u0` нет: `u1` — Pattern).
    """
    if item is None or item.min_note != f"DPI {TABLE_MIN_DPI120}":
        return False
    try:
        head = item.node["content"]["u2"]["u0"]["font"]
    except (KeyError, TypeError):
        return True
    return not (isinstance(head, dict) and head.get("source", "Auto") != "Auto")


def _squeeze_minimum(c, tables, step):
    """Минимум высоты каждой ужимаемой таблицы (`layout.min_size`, 49) и проверка «после ужатия не
    ниже»; не проверялся — отказ.
    """
    from . import layout
    try:
        lay = layout.read(c.doc)
    except Exception:
        lay = None
    out = {}
    for p in tables:
        item = lay.items.get(p.index) if lay is not None else None
        least = layout.min_size(item)[1] if item is not None else 0
        if not least and _table_dpi120_ok(item):
            least = layout.MIN_SIZE[SQUEEZABLE][1]
            c.dpi_note = DPI120_WORDS
        if not least:
            raise RoomRefusal(f"минимум высоты у {p.label()} ({p.type}) не проверялся: ужать до неизвестного предела нельзя", "B")
        height = p.rect[3] - p.rect[1]
        if height - step < least:
            raise RoomRefusal(f"{p.label()} ({p.type}) после ужатия на {step} стала бы {height - step} px при минимуме {least}", "B")
        out[id(p)] = least
    return out


def _refuse_centre_bound(c, step):
    """`grow` не пишется, если у формы есть элемент с правилом к центру формы по вертикали (объект 0,
    сторона «центр»): центр уходит на разницу целых половин высоты, а что платформа делает с таким
    смещением при смене размера, не проверялось (проверены только правила к низу): box остаётся на месте,
    смещение как было — и правило перестаёт сходиться с box. Зовут там, где место уже найдено, —
    отказ «места нет» от того, кто сам остаётся на месте, остаётся прежним.
    """
    for peer in _peers_all(_holder_of(c.doc, c)):
        if any(rule[N.RULE_OBJECT] == 0 and rule[N.RULE_SIDE] == SIDE_CENTER_V for rule in _rules_of(peer.coords, (0, 1))):
            raise RoomRefusal(f"grow: форму выше на {step} сделать нельзя — {peer.label()} ({peer.type}) привязан к центру формы по вертикали: "
                              "центр уйдёт на половину прироста, а как платформа переписывает такое смещение при смене размера, не проверялось "
                              "(проверены только правила к низу); смещение, оставленное как есть, разойдётся с box", "C")


def _grow_op(c, step):
    """Форма выше на шаг: `(копия формы после записи размера, новая высота, unverified)`. Запись
    размера делает `set_property` формы — на копии она сверяется сейчас, отказ идёт словами оттуда;
    у копии читаются правила образца после записи.
    """
    import copy
    from .edit import setprop
    block = c.doc.get("form") if isinstance(c.doc, dict) else None
    old = block.get("height") if isinstance(block, dict) else None
    if not _int(old):
        raise EditError("grow: у формы нет целой высоты в блоке размера — выше сделать нечего")
    work = copy.deepcopy(c.doc)
    try:
        setprop.set_property(work, form=True, name="height", value=old + step, unverified=c.unverified)
    except EditError as e:
        raise EditError(f"grow: форму выше на {step} сделать нельзя — {e}") from None
    return work, old + step, c.unverified


def _peer_rules(c, grow_op):
    """Правила образцов для нового (`_copy_rules`) — по образцам ПОСЛЕ записи размера формы при `grow`: верх и низ — у образца по ряду
    (`c.peer`), лево и право — у образца по столбцу (`c.peer_h`); либо `None` («к себе»/явный anchor).
    """
    peer = c.peer
    if c.anchor is not None or peer is None:
        return None, peer, []
    again = {}
    if grow_op is not None:
        again = {p.index: p for p in _peers(_holder_of(grow_op[0], c), c.page, hidden=True)}
    rules, notes = _copy_rules(again.get(peer.index, peer), c.new, c.names)
    peer_h = c.peer_h or peer
    source_h = again.get(peer_h.index, peer_h)
    shares = _behaviours(c.doc, [peer_h]).get(peer_h.index) in _SHIFTING
    if peer_h is not peer or shares:
        # Образец сдвигается или ведёт долями: правила к третьим элементам (разделитель шапки, надпись столбца) берутся дословно, как у `{"as": …}`;
        # перевод на самого образца оставил бы новый элемент без доли.
        rules_h, notes_h = _copy_rules(source_h, c.new, c.names, keep_third=shares)
        rules = {**rules, 2: rules_h[2], 3: rules_h[3]}
        notes = [n for n in notes if not n.startswith(("лево", "право"))] + [n for n in notes_h if n.startswith(("лево", "право"))]
        if shares:
            notes.append("лево и право: образец сдвигается либо ведёт долями — правила к третьим элементам скопированы дословно")
    if c.date_fixed and c.date_role == "stand":
        # Поле даты остаётся на месте: оба края — к левому краю родителя (роль `left`)
        rules = {**rules, 2: [(0, SIDE_LEFT, c.new[0]), None], 3: [(0, SIDE_LEFT, c.new[0] + c.date_fixed), None]}
        notes = [n for n in notes if not n.startswith(("лево", "право"))] + [
            f"лево и право: поле даты остаётся на месте — оба края к левому краю родителя (x={c.new[0]}, ширина {c.date_fixed})"]
    elif c.date_fixed:
        # Поле даты не растягивается, но идёт с колонкой: правое правило — то же, что левое образца, со смещением на ширину
        rules = {**rules, 3: [None if r is None else (r[0], r[1], r[2] + c.date_fixed) for r in rules[2]]}
        notes = [n for n in notes if not n.startswith("право")] + [
            f"право: то же правило, что лево, со смещением на ширину поля даты {c.date_fixed} (поле не растягивается)"]
    return rules, peer, notes


def _holder_of(work, c):
    from .edit import base
    return base.holder_by_name(work, c.holder_name)


def _place(c, words, movers, adjust, peer_rules, peer, notes, grow_op):
    left, top, width, height = c.box
    rules, flags, chosen, anchor_words = None, None, c.anchor, None
    if c.anchor is None and peer is None:
        chosen, anchor_words = SELF, "привязки — к себе (элемента такого типа в блоке нет)"
    elif c.anchor is None:
        rules = peer_rules
        flags = ((c.peer_h or peer).coords.get(N.MANUAL_H), peer.coords.get(N.MANUAL_V))
        anchor_words = f"привязки как у {peer.label()} (правила и флаги скопированы, смещения пересчитаны под место)"
        if c.peer_h is not None and c.peer_h is not peer:
            anchor_words += f"; по горизонтали — как у {c.peer_h.label()}"
        if c.column_words:
            anchor_words += f"; {c.column_words}"
        if notes:
            anchor_words += "; " + "; ".join(notes)
    text = (f"место без box: ({left}, {top}, {width}, {height}) — ниже {c.nbr.label()} в его столбце x={c.column}, шаг {c.step} "
            f"{c.step_from}, размер {c.size_from}" + (f"; {c.pair_note}" if c.pair_note else "") + (f"; {anchor_words}" if anchor_words else "") + words)
    sample = {0: (c.peer_h or peer).name or f"#{(c.peer_h or peer).index}", 1: peer.name or f"#{peer.index}"} if rules is not None else None
    place = Place(c.box, chosen, rules, flags, movers, adjust, c.step, text,
                  grow=None if grow_op is None else (c.doc, grow_op[1], grow_op[2]), sample=sample)
    return place


def _peers_all(holder):
    """Все элементы родителя на ЛЮБОЙ странице: вертикальные правила чужих страниц тоже называют
    сдвигаемых.
    """
    out = []
    for order, item in enumerate((holder.get(N.ELEMENTS) or {}).get(N.ITEMS) or []):
        coords = item.get(N.COORDS) if isinstance(item, dict) else None
        if isinstance(coords, dict) and all(_int(coords.get(k)) for k in (N.X, N.Y, N.WIDTH, N.HEIGHT)):
            out.append(_Peer(item, coords, order))
    return out
