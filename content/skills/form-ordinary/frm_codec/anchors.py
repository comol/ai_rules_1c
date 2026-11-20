"""Привязки границ: встречные записи и роли ручного стиля.

Правило привязки читается «моя граница = сторона объекта + смещение»; второе правило той же
границы — пропорция между двумя якорями. Правило работает, только если у него есть встречная
запись. Родитель — панель или форма, на которой лежит элемент.

* правило на соседа — запись `{0, я, моя граница}` в списке зависимых соседа
  (`dependents_<его сторона>` блока координат);
* правило к краю родителя (объект 0; форма у верхнего уровня, панель у вложенного) — такая же
  запись в списке блока раскладки родителя (`dependents_<край>`).

Без записи элемент в предприятии остаётся на месте, а пересохранение в конфигураторе пропавших записей не
дописывает. Поэтому редактор пишет и края родителя, и второе правило.

## Где лежит встречная запись

Сторона объекта в правиле → список, где лежит запись (`RECORD_LIST`): верх, низ, лево, право —
свои; центр по вертикали (4) пишет в список низа, по горизонтали (5) — в список права; то же у
правил к центру соседа. Первое и второе правило пишут запись одинаково. Висячие записи платформы
(элемента нет, элемент в другом родителе, правила нет) платформа не чистит; редактор чистит:
меняя привязки элемента, он снимает все записи, называющие его индекс, и ставит заново по правилам.

## Роли — ручной стиль таблицы

`set_anchors` пишет привязки по именам ролей: обе границы оси к краям родителя и флаг «Ручная
привязка» оси. Этот стиль переживает пересохранение с АвтоПравилами и не зависит от соседей.
Цепочка к соседу (`after`) — ближняя граница за дальней стороной соседа.

Смещение = координата − сторона объекта. Край родителя:

* у формы — её размер, при Рамке «Одинарная» — размер − 2; иная рамка — отказ, снимаемый
  `unverified`; у формы с видимыми закладками — по направляющим, как у панели (вариант
  `set_anchors/form-tabs`);
* у панели — по направляющим её страницы: правый край = координата направляющей 3 + её отступ,
  нижний — направляющей 4; левый и верхний — ноль.
"""
from . import edit, schema

# Сторона объекта в правиле → индекс списка, где лежит встречная запись (0 верх, 1 низ, 2 лево, 3
# право). Центр пишет в список дальней стороны своей оси.
RECORD_LIST = {0: 0, 1: 1, 2: 2, 3: 3, 4: 1, 5: 3}
TOP, BOTTOM, LEFT, RIGHT, CENTER_V, CENTER_H, NO_SIDE = range(7)
BORDER_WORDS = ("верх", "низ", "лево", "право")
SIDE_LETTERS = {TOP: "t", BOTTOM: "b", LEFT: "l", RIGHT: "r", CENTER_V: "c", CENTER_H: "c"}

# Имена члена списка родителя — у карты (позиции `LayoutRun`).
ROW_MARK, ROW_ELEMENT, ROW_SIDE = (edit._at("LayoutRun", i) for i in (0, 1, 2))
LAYOUT_KEY = schema.MAP["LayoutList"].fields[0].name

# Числа корпуса (`corpus.FROZEN_STAMP`), которые повторяет проза отчётов. Правила к центру родителя
# и соседа: у всех встречная запись в списке дальней стороны оси (`RECORD_LIST`); одна константа на
# привязки и раскладку.
CORPUS_CENTER = {"по вертикали": 103, "по горизонтали": 237, "к соседу": 52}
CORPUS_PANEL_EDGES = {"правому": (25624, 26386), "нижнему": (8576, 9231)}
# Край формы по правилу `holder_edges` — её клиентская область: размер минус Рамка, при видимых
# закладках «Сверху» (DPI 96) — область страниц (W−2, H−20) формулой, при прочих закладках —
# направляющие под `unverified` (`_AT_CLIENT`). Правило «край = размер» считает
# `edit.CORPUS_FORM_EDGES_AT_SIZE`; числа у двух констант разные.
CORPUS_FORM_EDGES_AT_CLIENT = {"правому": (22297, 22433), "нижнему": (9079, 9216)}
# Середина по правилу операции (половина края родителя с отбросом дроби) — у скольких правил к
# центру родителя из всех; края формы с видимыми закладками по направляющим; рамка «Одинарная» —
# «размер − 2»; роль `proportional` — ось с парой на обеих границах; пара `anchor="form"` —
# элементов и форм.
CORPUS_CENTER_MIDDLE = {"форма": (175, 235), "панель": (95, 105)}
CORPUS_FORM_TABS_EDGES = {"правому": (20, 20), "нижнему": (5, 9)}
CORPUS_SINGLE_FRAME_EDGES = {"правому": (17, 28), "нижнему": (3, 16)}
CORPUS_PROPORTIONAL_BOTH = {"по горизонтали": 7484, "по вертикали": 57, "форм": 320}
CORPUS_FORM_PAIR = {"элементов": 17, "форм": 11}

# Рамка формы: край её клиентской области. «Одинарная» проверена в предприятии (отступы направляющих
# 8 → 6, привязки −8 → −6), прочие виды не проверялись; корпус «Одинарную» почти не держит
# (`CORPUS_SINGLE_FRAME_EDGES`).
FRAME_INSET = {None: 0, "WithoutBorder": 0, "Single": 2}

H_ROLES = ("stretch", "left", "right", "proportional", "center", "self", "column", "slide")
# `{"as": "<образец>"[, "with": {"<имя в правилах образца>": "<имя вместо него>"}]}` — не роль, а копия правил образца (`_rules_as`).
AS_KEYS = {"as", "with"}
V_ROLES = ("stretch", "top", "bottom", "proportional", "center", "slide")
AXES = {"h": ("горизонталь", LEFT, RIGHT, edit.MANUAL_H),
        "v": ("вертикаль", TOP, BOTTOM, edit.MANUAL_V)}

ROLE_WORDS = {
    ("h", "stretch"): "растягивать", ("h", "left"): "к левой границе",
    ("h", "right"): "к правой границе", ("h", "proportional"): "пропорционально",
    ("h", "center"): "к центру",
    ("h", "self"): "к своим границам", ("h", "column"): "долей одна граница", ("h", "slide"): "сдвигать долей, размер держать",
    ("v", "stretch"): "растягивать", ("v", "top"): "к верхней границе",
    ("v", "bottom"): "к нижней границе", ("v", "proportional"): "пропорционально",
    ("v", "center"): "к центру", ("v", "slide"): "сдвигать долей, размер держать",
}
# Шапка колонок: ряды `split` корпуса; `(равно, всего)` — элементов, чьи правила двух горизонтальных
# границ равны тому, что пишет роль (со своим соседом, краем формы и смещениями): надпись первой
# колонки (`self`), первое поле (`column`), внутреннее поле (`after-column`); последнее поле
# (`after-stretch`) и надпись следующей колонки (`after`) — давние варианты. Движок пишет одно
# связное семейство «за полем слева», а не самый частый вариант в каждом месте; у `prop_pos`
# совпадает большинство рядов.
CORPUS_SPLIT = {"self": (39, 70), "column": (51, 70), "after-column": (5, 15)}
# Разделитель (перепись форм с разделителем): `соседей рядом` — элементов, чьё правило называет разделитель и которые лежат слева,
# справа, выше или ниже его; `лицом к разделителю` — из них те, чья обращённая к нему граница привязана к ближней стороне разделителя
# (правая граница левого соседа — к его левой стороне и так далее); `со смещением, равным зазору` — из них те, у кого смещение равно
# зазору между границей и стороной (у остальных ±1…2 px); `разделителей со сдвигом долей` — у скольких правила оси движения равны роли
# `slide` (любой из двух порядков границ).
CORPUS_SPLITTER = {"разделителей": 737, "разделителей со сдвигом долей": 400, "соседей рядом": 2009,
                   "лицом к разделителю": 1935, "со смещением, равным зазору": 1711}
_MANUAL = "ручной стиль совпал с моделью до пикселя (проверено в предприятии)"
EVIDENCE = {role: _MANUAL for role in ("stretch", "left", "right", "top", "bottom")}
# Роли `proportional` здесь нет: пара проверена на одной границе, а роль пишет её на обеих — у неё
# пометка `set_anchors/proportional-both`, как у центра — своя.
EVIDENCE.update({
    "splitter": ("привязка границы соседа к стороне разделителя — запись корпуса: так привязано подавляющее большинство соседей "
                 "разделителей, смещение чаще всего равно зазору; в предприятии не проверялась"),
    "slide": ("разделитель: ближняя граница от своей дальней, дальняя — долей между краями родителя — запись корпуса: так привязана "
              "большая часть разделителей; в предприятии не проверялась"),
    "as": "правила образца: те же объекты и стороны, смещения пересчитаны под место (в предприятии не проверялось)",
    "keep": "прежние правила пересчитаны под новое место (в предприятии не проверялось)",
    "after": "цепочка со встречной записью сдвигается за соседом, без записи — остаётся на месте (проверено в "
             "предприятии)",
    "before": "дальняя граница к ближней стороне соседа: запись корпуса — правая граница к левой стороне другого элемента, нижняя к верхней "
              "(у не-разделителей 1 290 и 1 446 правил корпуса и выгрузок, у разделителей 536 и 554); в предприятии не проверялась",
    "before-stretch": "дальняя граница к ближней стороне соседа, ближняя к краю родителя: запись корпуса (см. «before»); в предприятии не проверялась",
    "after-stretch": "дальняя граница к краю родителя: проверено в предприятии, в том числе "
                     "после пересохранения",
    # Шапка колонок: корпус называет вид ряда и число рядов (`CORPUS_SPLIT`); проверено в
    # предприятии: ряд из трёх долей делит прирост, пересохранение записи не тронуло.
    "self": "шапка колонок: надпись первой колонки — запись платформы; в предприятии шапка делит "
            "прирост, пересохранение записи не тронуло",
    "column": "шапка колонок: первое поле ряда — запись платформы; проверено в предприятии "
              "(с правилом левой границы к краю формы и без него)",
    "after-column": "шапка колонок: внутреннее поле ряда — запись платформы; "
                    "проверено в предприятии: делит прирост, пересохранение записи не тронуло",
})


class Plan:
    """Привязки одной оси: правила двух границ, флаг и слова отчёта."""

    __slots__ = ("axis", "rules", "flag", "words", "behaviour", "notes")

    def __init__(self, axis):
        self.axis, self.rules, self.flag = axis, {}, True
        self.words, self.behaviour, self.notes = "", "", []


def _rule(target, side, offset):
    return {edit.RULE_OBJECT: target, edit.RULE_SIDE: side, edit.RULE_OFFSET: int(offset)}


def _none():
    return dict(edit.NO_ANCHOR)


def rule_text(rule, me=None, names=None):
    """Правило строкой: `F.r-8` (край родителя), `S.l+88` (сам), `ПолеНомер.r+10`, `-`."""
    target, side, offset = (rule.get(edit.RULE_OBJECT), rule.get(edit.RULE_SIDE),
                            rule.get(edit.RULE_OFFSET))
    if target == -1 or side == NO_SIDE:
        return "-"
    who = "F" if target == 0 else "S" if target == me else (names or {}).get(target, f"#{target}")
    return f"{who}.{SIDE_LETTERS.get(side, side)}{offset:+d}"


# ── Встречные записи ──────────────────────────────────────────────────────────────────────────

def _items(holder):
    block = holder.get(edit.ELEMENTS)
    items = block.get(edit.ITEMS) if isinstance(block, dict) else None
    return [item for item in items or () if isinstance(item, dict)]


def _coords(item):
    coords = item.get(edit.COORDS)
    return coords if isinstance(coords, dict) and edit.X in coords else None


def _index(item):
    value = item.get(edit.INDEX)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


# Прежние имена четырёх списков родителя — `list1…list4` (поля строки — `u0…u2`). Документ уровня 1
# с такими ключами собран прежней картой: проверка и сборка его отвергают («dependents_top — список
# L1, и пишут его массивом…»), прежнее имя — отказ словами.
FORMER_LISTS = ("list1", "list2", "list3", "list4")


def side_lists(block):
    """Четыре списка родителя в блоке раскладки — `[верх, низ, лево, право]` как лежат: массив,
    испорченное руками значение или `None`, если ключа нет; `None` целиком — блока нет.

    Одно место, где названы списки родителя (`edit.LAYOUT_LISTS[:4]`): им читают и привязки
    (`holder_lists`), и раскладка (`layout._rows`). Прежние имена (`FORMER_LISTS`) — отказ словами;
    поля строки в прежнем написании (`u0…u2`) отдельно не ловятся — смесь, собранную руками,
    отвергает проверка.
    """
    if not isinstance(block, dict):
        return None
    former = [name for name in FORMER_LISTS if name in block]
    if former:
        raise edit.EditError(
            f"списки родителя названы прежними именами ({', '.join(former)}) — так их звала карта "
            f"прежних версий; теперь это {', '.join(edit.LAYOUT_LISTS[:4])}, а поля строки — "
            f"{ROW_MARK}, {ROW_ELEMENT}, {ROW_SIDE}. Документ собран прежней картой, и второго "
            "написания здесь не читает никто (проверка и сборка его тоже отвергают): перечитайте "
            "форму (frm_json.py decode) и перенесите правку")
    return [block.get(key) for key in edit.LAYOUT_LISTS[:4]]


def holder_lists(holder):
    """Четыре списка родителя — `[верх, низ, лево, право]`, либо `None`, если блока нет или хоть
    один из них не массив."""
    lists = side_lists(edit.layout_block(holder, need=False))
    if lists is None or not all(isinstance(lst, list) for lst in lists):
        return None
    return lists


def record_home(holder, by_index, index, rule):
    """Где лежит встречная запись правила: `(список, чей, имя списка)` или `None` и причина.

    `by_index` — элементы этого родителя: правило на соседа называет элемент того же родителя;
    называющее иной — висячее, записи у него нет.
    """
    target, side = rule.get(edit.RULE_OBJECT), rule.get(edit.RULE_SIDE)
    if target in (None, -1) or side not in RECORD_LIST:
        return None, "нет"
    at = RECORD_LIST[side]
    if target == 0:
        lists = holder_lists(holder)
        if lists is None:
            return None, "у родителя нет списков"
        return (lists[at], "носитель", edit.LAYOUT_LISTS[at]), "носитель"
    item = by_index.get(target)
    coords = _coords(item) if item is not None else None
    if coords is None or not isinstance(coords.get(edit.DEPENDENTS[at]), list):
        return None, "висячее"
    kind = "сам" if target == index else "сосед"
    return (coords[edit.DEPENDENTS[at]], kind, edit.DEPENDENTS[at]), kind


def _member_key(member, element_key, side_key):
    return (member.get(element_key), member.get(side_key)) if isinstance(member, dict) else None


def _record(owner, index, border):
    if owner == "носитель":
        return {ROW_MARK: 0, ROW_ELEMENT: index, ROW_SIDE: border}
    return {edit.DEP_MARK: 0, edit.DEP_ELEMENT: index, edit.DEP_SIDE: border}


def _keys(owner):
    return (ROW_ELEMENT, ROW_SIDE) if owner == "носитель" else (edit.DEP_ELEMENT, edit.DEP_SIDE)


def _insert(members, record, owner):
    """Запись на своё место: в списке родителя — по (элемент, граница); у соседа — в конец (порядок там
    не важен).
    """
    element_key, side_key = _keys(owner)
    key = (record[element_key], record[side_key])
    if owner != "носитель":
        members.append(record)
        return
    for at, member in enumerate(members):
        other = _member_key(member, element_key, side_key)
        if other is not None and None not in other and other > key:
            members.insert(at, record)
            return
    members.append(record)


def _all_lists(doc):
    """Все списки встречных записей формы: `(список, чей, ключи)` — родителей и элементов."""
    out = []
    for _name, holder in edit.holders(doc):
        block = edit.layout_block(holder, need=False)
        if isinstance(block, dict):
            for key in edit.LAYOUT_LISTS:
                if isinstance(block.get(key), list):
                    out.append((block[key], "носитель"))
        for item in _items(holder):
            coords = _coords(item)
            for key in edit.DEPENDENTS + edit.EMPTY_LISTS:
                if coords is not None and isinstance(coords.get(key), list):
                    out.append((coords[key], "сосед"))
    return out


def drop_naming(doc, index):
    """Снять ВСЕ записи, называющие индекс, — у родителей и у элементов. Возвращает их число."""
    dropped = 0
    for members, owner in _all_lists(doc):
        element_key, _side = _keys(owner)
        left = [m for m in members if not (isinstance(m, dict) and m.get(element_key) == index)]
        dropped += len(members) - len(left)
        members[:] = left
    return dropped


def _locate(doc, index):
    for _name, holder in edit.holders(doc):
        for item in _items(holder):
            if _index(item) == index:
                return holder, item
    raise edit.EditError(f"элемента с индексом {index} в форме нет")


def put_records(doc, index):
    """Записи по правилам элемента: `[(чей, имя списка, граница, имя соседа)]` поставленных.

    Зовётся после `drop_naming`: записей, называющих индекс, в форме в этот миг нет, и всё
    поставленное — ровно то, чего требуют правила."""
    holder, item = _locate(doc, index)
    coords = _coords(item)
    by_index = {_index(i): i for i in _items(holder)}
    names = {_index(i): edit.name_of(i) for i in _items(holder)}
    out = []
    for border, key in enumerate(edit.ANCHORS):
        anchor = coords.get(key) if coords else None
        for rule_name in edit.RULES:
            rule = anchor.get(rule_name) if isinstance(anchor, dict) else None
            if not isinstance(rule, dict):
                continue
            home, _why = record_home(holder, by_index, index, rule)
            if home is None:
                continue
            members, owner, list_name = home
            record = _record("носитель" if owner == "носитель" else "сосед", index, border)
            if record in members:
                continue
            _insert(members, record, "носитель" if owner == "носитель" else "сосед")
            out.append((owner, list_name, border, names.get(rule.get(edit.RULE_OBJECT))))
    return out


def _naming(doc, index):
    """Записи, называющие индекс: множество `(id списка, граница)`."""
    out = set()
    for members, owner in _all_lists(doc):
        element_key, side_key = _keys(owner)
        out |= {(id(members), m.get(side_key)) for m in members
                if isinstance(m, dict) and m.get(element_key) == index}
    return out


def sync(doc, index, keep_places=False):
    """Встречные записи элемента заново: снять все, называющие его, поставить по правилам.

    `keep_places=True` (привязка `keep` у `move_element`): запись, снятая и поставленная заново, возвращается на прежнее место в списке — иначе у соседей
    она ушла бы в конец, и в списке зависимых порядок записей менялся бы без причины.

    Возвращает `(снято, поставлено)`: число снятых и не вернувшихся записей и перечень всех записей,
    которых требуют правила элемента. Висячих записей платформа не чистит, редактор — чистит:
    запись, называющая индекс, говорит «ко мне привязан элемент N», и у элемента, чьи привязки
    поменяли, старая запись соврала бы о правиле, которого больше нет.
    """
    before = _naming(doc, index)
    saved = []
    if keep_places:
        for members, owner in _all_lists(doc):
            element_key, side_key = _keys(owner)
            hits = [(at, (m.get(element_key), m.get(side_key))) for at, m in enumerate(members)
                    if isinstance(m, dict) and m.get(element_key) == index]
            if hits:
                saved.append((members, owner, hits))
    drop_naming(doc, index)
    put = put_records(doc, index)
    for members, owner, hits in saved:
        element_key, side_key = _keys(owner)
        back = []
        for at, key in hits:
            found = next((m for m in members if isinstance(m, dict) and (m.get(element_key), m.get(side_key)) == key), None)
            if found is not None:
                members.remove(found)
                back.append((at, found))
        for at, found in back:
            members.insert(min(at, len(members)), found)
    return len(before - _naming(doc, index)), put


def records_words(put, dropped_before=None):
    """Отчёт о записях: у родителя сколько и где, у соседей — у кого."""
    holder = [f"{name}/{BORDER_WORDS[border]}" for owner, name, border, _n in put
              if owner == "носитель"]
    neighbours = [f"«{who}».{name}" for owner, name, _b, who in put if owner == "сосед"]
    own = sum(1 for owner, *_rest in put if owner == "сам")
    parts = [f"у родителя {len(holder)}" + (f" ({', '.join(holder)})" if holder else "")]
    if neighbours:
        parts.append(f"у соседей {len(neighbours)} ({', '.join(neighbours)})")
    if own:
        parts.append(f"свои {own}")
    text = "встречных записей: " + "; ".join(parts)
    if dropped_before is not None:
        text += f"; прежних снято {dropped_before}"
    return text


# ── Края родителя ─────────────────────────────────────────────────────────────────────────────

def _frame(doc):
    block = edit.layout_block(edit.container(doc), need=False)
    layout = block.get(LAYOUT_KEY) if isinstance(block, dict) else None
    border = layout.get("border") if isinstance(layout, dict) else None
    return border.get("border_type") if isinstance(border, dict) else None


def _visible_tabs(doc, holder):
    """Закладки формы, если родитель — сама форма и они ВИДНЫ; иначе `None`."""
    if holder is not edit.container(doc):
        return None
    block = edit.layout_block(holder, need=False)
    tabs = block.get(edit.SHOW_TABS) if isinstance(block, dict) else None
    return None if tabs in (None, "DontUse") else tabs


def _tabs_mark(doc, holder):
    """Пометка края формы с видимыми закладками шире проверенного (`set_anchors/form-tabs`: закладки не
    «Сверху», Рамка, DPI не 96 — край по направляющим) либо `None`.
    """
    # Закладки «Сверху» с DPI 96 (без Рамки и с «Одинарной»): край формулой, без пометки.
    if _visible_tabs(doc, holder) is None or tabs_unverified(doc) is None:
        return None
    seen = sum(total for _ok, total in CORPUS_FORM_TABS_EDGES.values())
    return edit._on_corpus("set_anchors/form-tabs", "край формы с закладками", seen,
                           counted="правил к правому и нижнему краю формы с видимыми "
                                   "закладками")[2:]


def tabs_area(doc):
    """Область страниц формы с видимыми закладками: `(W−2, H−20)` либо `None`.

    При закладках «Сверху», DPI 96 и форме без Рамки (или с Рамкой одного из семи видов) предприятие
    считает правила всех страниц формы и её командных панелей от области страниц `(W−2, H−20)` — не
    от сохранённого box и не от направляющих страницы 0 (у форм, записанных платформой, они разные:
    у формы с нижней командной панелью платформа пишет `(W, H−19)`; `docs/form-pages.md`). Край —
    формулой, направляющие не читаются. Проверено поколение блока формы 16 (поля `dpi`, `device_*`):
    короткий блок (поколение 10) проходит как DPI 96, шрифт формы (от него зависит высота полосы
    закладок) не учитывается. `None` — закладок нет, они не «Сверху», DPI не 96, у формы Рамка вне
    семи проверенных видов или размер не целый: не проверялось (см. `tabs_unverified`).
    """
    tabs = _visible_tabs(doc, edit.container(doc))
    form = doc.get("form") if isinstance(doc, dict) else None
    if tabs != "Top" or not isinstance(form, dict) or _tabs_unmeasured(doc, form):
        return None
    width, height = form.get("width"), form.get("height")
    ok = all(isinstance(v, int) and not isinstance(v, bool) for v in (width, height))
    return (width - 2, height - 20) if ok else None


# Виды Рамки, при которых область страниц с закладками «Сверху» проверена: `(W−2, H−20)` у всех семи
# (`Single`, `Double`, `Embossed`, `Indented`, `Underline`, `Overline`, `DoubleUnderline`). Один
# список с `edit.pages.FRAMED_UNTOUCHED` (источник; `layout.FRAMES_TABS_MEASURED` ссылается туда
# же).
FRAMES_MEASURED_TABS = edit.FRAMED_UNTOUCHED


def _tabs_unmeasured(doc, form):
    """Чем закладки «Сверху» отличаются от проверенного: слова либо `None`."""
    if "device_width" in form and form.get("dpi") != 96:
        return f"DPI {form.get('dpi')}"
    # Рамка вычета не добавляет: область та же (W−2, H−20) у всех семи проверенных видов. Прочее не
    # проверялось.
    if _frame(doc) not in (None, "WithoutBorder") + FRAMES_MEASURED_TABS:
        return f"Рамка {_frame(doc)!r}"
    return None


def tabs_unverified(doc):
    """Слова, если закладки формы видны, а правило области страниц к ним не применимо (закладки не
    «Сверху», Рамка, DPI не 96); иначе `None`. Форма без закладок — `None`."""
    tabs = _visible_tabs(doc, edit.container(doc))
    if tabs is None:
        return None
    form = doc.get("form") if isinstance(doc, dict) else None
    if tabs != "Top":
        return f"закладки {tabs!r}: область страниц проверена только при «Сверху»"
    why = _tabs_unmeasured(doc, form) if isinstance(form, dict) else None
    return f"закладки «Сверху» и {why}: область страниц при этом не проверялась" if why else None


def holder_edges(doc, holder, page, unverified=False):
    """`(право, низ, слова)` — дальние края родителя в его координатах; ближние — ноль.

    У формы — размер (минус рамка), у панели — направляющие 3 и 4 страницы элемента (их координата
    плюс отступ). У формы с видимыми закладками «Сверху» (DPI 96, без Рамки или с Рамкой одного из
    семи проверенных видов) — область страниц `(W−2, H−20)` формулой. При прочих закладках, Рамке
    вне семи видов (`FRAMES_MEASURED_TABS`) и DPI не 96 — отказ, снимаемый `unverified` (тогда
    направляющие страницы: вариант `set_anchors/form-tabs`). Родитель без таких направляющих —
    отказ: края взять неоткуда, а «ширина − 2» верна лишь у части панелей.
    """
    if holder is edit.container(doc):
        tabs = _visible_tabs(doc, holder)
        area = tabs_area(doc)
        if area is not None:
            return area[0], area[1], (
                f"край формы с закладками («Сверху»): область страниц {area[0]}×{area[1]} = "
                "(ширина − 2, высота − 20) по формуле; направляющие страницы не "
                "читаются — у формы с нижней панелью платформа пишет (W, H−19), без неё (W, H), и ни то ни "
                "другое не край предприятия; для ЗАПИСИ смещений — `file_edges`")
        if tabs is not None:
            if not unverified:
                raise edit.EditError(
                    f"у формы видны закладки, а область страниц ({tabs_unverified(doc) or 'размер формы не целый'}) не "
                    "проверялась: край по направляющим страницы ненадёжен. unverified=True возьмёт "
                    "направляющие страницы")
            right, bottom = _guide_edges(holder, page, "у формы")
            return right, bottom, (f"край формы с закладками ({tabs}) по направляющим страницы "
                                   f"{page}: {right}×{bottom} — не проверялось")
        form = doc.get("form") or {}
        width, height = form.get("width"), form.get("height")
        frame = _frame(doc)
        # Вид рамки не строкой (документ правлен руками) — как неизвестная рамка: отказ словами.
        inset = FRAME_INSET.get(frame) if isinstance(frame, (str, type(None))) else None
        if inset is None:
            if not unverified:
                raise edit.EditError(
                    f"у формы Рамка {frame!r}: край её клиентской области проверен только "
                    "без рамки и при «Одинарной» (размер − 2); у прочих видов рамки он не проверялся. "
                    "unverified=True посчитает от «размер − 2»")
            inset = 2
        words = f"край формы: {width - inset}×{height - inset}"
        if inset:
            words += f" (размер {width}×{height} минус рамка {frame!r})"
        return width - inset, height - inset, words
    name = (holder.get(edit.NAME_BLOCK) or {}).get(edit.NAME)
    right, bottom = _guide_edges(holder, page, f"у панели {name!r}")
    return right, bottom, f"край панели «{name}» по направляющим страницы {page}: {right}×{bottom}"


TABS_PAGE0_SHIFT = 19  # низ страницы 0 формы «Сверху» у платформы — H − 19


def _int_pair(a, b):
    return all(isinstance(v, int) and not isinstance(v, bool) for v in (a, b))


def file_edges(doc, holder, page, unverified=False):
    """Края родителя для записи смещений: `(право, низ, слова)`.

    Отличается от `holder_edges` одним случаем — страница 0 формы с видимыми закладками «Сверху»,
    которую переписала платформа или `rewrite_page0_for_tabs`: её направляющие дают `(W, H − 19)`, и
    от них платформа считает смещения в файле, а box согласован с правилами по файлу: `box = край +
    смещение`. Край предприятия `(W − 2, H − 20)` (`holder_edges`, `tabs_area`) остаётся краем
    модели раскладки. У страницы 0 с иными направляющими (форма, записанная прежним редактором, —
    `H`; форма без нижней панели) и у страниц ≥ 1 — `holder_edges`.
    """
    area = tabs_area(doc)
    if area is not None and holder is edit.container(doc) \
            and _frame(doc) in FRAMES_MEASURED_TABS:
        # Запись смещений у формы с Рамкой и закладками проверена на одном виде: страница 0 формы
        # без нижней командной панели с отступом нижней направляющей 6 (= 8 − 2 Рамки,
        # `edit.framed_nobar8`), страница добавлена `add_form_page` из «Не отображать». Прочее (иной
        # вид нижнего края, страницы ≥ 1) — под `unverified`.
        measured = page == 0 and edit.framed_nobar8(doc)
        if not unverified and not measured:
            raise edit.EditError(
                f"у формы Рамка {'«Одинарная»' if _frame(doc) == 'Single' else repr(_frame(doc))} и видимые закладки «Сверху»: область страниц предприятия "
                "(W−2, H−20) проверена при семи видах Рамки, а запись смещений при Рамке — только на странице 0 "
                "формы без нижней командной панели с отступом нижней направляющей 6 и только при «Одинарной»; у иного вида "
                "нижнего края и у страниц после первой край для записи по направляющим не надёжен. "
                "unverified=True возьмёт направляющие страницы")
        right, bottom = _guide_edges(holder, page, "у формы")
        if measured:
            return right, bottom, (f"край формы с Рамкой и закладками по направляющим страницы {page}: "
                                   f"{right}×{bottom} — страница 0 без "
                                   "нижней панели, отступ 6 (проверено в предприятии); смещения пишутся от направляющих, а предприятие ставит "
                                   "элемент по области (W−2, H−20) — на 18 px выше его box; у формы "
                                   "«Сверху» без Рамки (`nobar8`) край записи — область (W−2, H−20)")
        return right, bottom, (f"край формы с Рамкой и закладками по направляющим страницы {page}: "
                               f"{right}×{bottom} — запись при Рамке не проверялась")
    if area is not None and holder is edit.container(doc) and page == 0:
        try:
            right, bottom = _guide_edges(holder, 0, "у формы")
        except edit.EditError:
            right = bottom = None
        form = doc.get("form") or {}
        width, height = form.get("width"), form.get("height")
        # Правый край — ширина (одна страница) либо ширина − 2 (вторая страница «Сверху» сдвигает у
        # первой отступ правой направляющей 8 → 6 и правила +2); нижний — высота − 19.
        if _int_pair(width, height) and bottom == height - TABS_PAGE0_SHIFT \
                and right in (width, width - 2):
            return right, bottom, (
                f"край страницы 0 формы с закладками («Сверху») по её направляющим: {right}×{bottom} = "
                f"(ширина{'' if right == width else ' − 2'}, высота − {TABS_PAGE0_SHIFT}) — так "
                "платформа пишет смещения при включении закладок; предприятие поставит "
                "элемент на (−2, −1) от конструктора")
    return holder_edges(doc, holder, page, unverified)


def _guide_edges(holder, page, whose):
    """Правый и нижний край родителя: координата направляющей 3 (4) страницы плюс отступ."""
    block = edit.layout_block(holder, need=False)
    found = block.get(edit.GUIDES) if isinstance(block, dict) else None
    guides = {}
    # Список направляющих не массив (документ правлен руками) — как без направляющих: отказ словами.
    for guide in found if isinstance(found, list) else ():
        if isinstance(guide, dict) and guide.get(edit.GUIDE_PAGE) == page:
            guides.setdefault(guide.get(edit.GUIDE_ORDER), guide)
    edges = []
    for order in (3, 4):
        guide = guides.get(order) or {}
        coord, margin = guide.get(edit.GUIDE_COORD), guide.get(edit.GUIDE_OFFSET)
        if not isinstance(coord, int) or not isinstance(margin, int):
            raise edit.EditError(
                f"{whose} на странице {page} нет направляющей {order} с отступом — край "
                "родителя взять неоткуда. Он равен координате направляющей плюс отступ; "
                "«ширина − 2» верна лишь у части панелей")
        edges.append(coord + margin)
    return edges[0], edges[1]


# ── Роли ──────────────────────────────────────────────────────────────────────────────────────

def _spec(axis, value):
    """Роль оси из JSON: имя роли или `{"after": имя[, "role": "stretch"]}`."""
    roles = H_ROLES if axis == "h" else V_ROLES
    if isinstance(value, dict) and "as" in value:
        with_ = value.get("with", {})
        if (set(value) - AS_KEYS or not isinstance(value["as"], str) or not isinstance(with_, dict)
                or not all(isinstance(k, str) and isinstance(v, str) for k, v in with_.items())):
            raise edit.EditError(
                f"{axis}: привязка «как у образца» — {{\"as\": \"<имя образца>\"}} и необязательное \"with\": "
                f"{{\"<имя в правилах образца>\": \"<имя вместо него>\"}}, а пришло {value!r}")
        return "as", value
    if isinstance(value, dict) and "splitter" in value:
        if set(value) != {"splitter"} or not isinstance(value["splitter"], str):
            raise edit.EditError(
                f"{axis}: привязка к разделителю — {{\"splitter\": \"<имя разделителя>\"}} и больше ничего (вторая граница "
                f"оси остаётся как была), а пришло {value!r}")
        return "splitter", value["splitter"]
    if value == "keep":
        return "keep", None
    if isinstance(value, str):
        if value in roles:
            return value, None
        raise edit.EditError(
            f"{axis}: роль {value!r} не знаю; по {AXES[axis][0]} — {', '.join(roles)} либо "
            "цепочка {\"after\": \"<имя соседа>\"} (сдвигается за ним, размер держит), {\"after\": "
            "\"<имя>\", \"role\": \"stretch\"} (ближняя граница за соседом, дальняя к краю), {\"splitter\": \"<имя>\"} "
            "(сторона соседа разделителя) и {\"as\": \"<имя образца>\"} (правила образца)")
    if isinstance(value, dict) and "before" in value:
        role = value.get("role", "keep")
        if set(value) - {"before", "role"} or role not in ("keep", "stretch") or not isinstance(value["before"], str):
            raise edit.EditError(
                f"{axis}: цепочка «назад» — {{\"before\": \"<имя соседа>\"}} (дальняя граница к ближней стороне соседа, размер держится) и "
                f"необязательное \"role\": \"stretch\" (ближняя граница к краю родителя), а пришло {value!r}")
        return {"keep": "before", "stretch": "before-stretch"}[role], value["before"]
    if isinstance(value, dict) and set(value) <= {"after", "role"} and "after" in value:
        role = value.get("role", "keep")
        if role not in ("keep", "stretch", "column") or not isinstance(value["after"], str):
            raise edit.EditError(
                f"{axis}: цепочка — {{\"after\": \"<имя соседа>\"}} и необязательное \"role\": "
                f"\"stretch\" (дальняя граница к краю родителя) либо \"column\" (дальняя граница — долей, "
                f"шапка колонок), а пришло {value!r}")
        if role == "column" and axis != "h":
            raise edit.EditError(
                f"{axis}: цепочка с \"role\": \"column\" — только по горизонтали: шапку колонок снимок держит "
                "по ширине, по вертикали такой записи у него нет")
        return {"keep": "after", "stretch": "after-stretch", "column": "after-column"}[role], value["after"]
    raise edit.EditError(f"{axis}: роль — строка ({', '.join(roles)}) или {{\"after\": "
                         f"\"<имя соседа>\"}}, а пришло {value!r}")


def plan(doc, holder, page, index, box, axis, value, unverified=False, edges=None):
    """Правила одной оси по роли — ДО записи: отказ не должен оставить форму наполовину правленой.

    `box` — края элемента `(x, y, x2, y2)` в координатах родителя. `edges` — `(право, низ, слова)` края, от которого пишутся
    смещения, если он не краю файла `file_edges` (панель без рамки: видимая область, от неё предприятие считает правила); без него
    край берётся как раньше."""
    role, other = _spec(axis, value)
    _label, near, far, _flag = AXES[axis]
    x, y, x2, y2 = box
    lo, hi = (x, x2) if axis == "h" else (y, y2)
    result = Plan(axis)
    # Дальний край родителя нужен роли, у которой есть правило к нему; «к левому» и «к верхнему»
    # берутся от ближнего края (ноль), и им ни рамка формы, ни направляющие панели не нужны.
    need_edge = role not in ("after", "before", "before-stretch", "left", "top", "self", "as", "splitter", "keep")
    edge_words = None
    if need_edge:
        right, bottom, edge_words = edges or file_edges(doc, holder, page, unverified)
        extent = right if axis == "h" else bottom
    near_side, far_side, center = ((LEFT, RIGHT, CENTER_H) if axis == "h"
                                   else (TOP, BOTTOM, CENTER_V))
    if role == "stretch":
        result.rules = {near: [_rule(0, near_side, lo)], far: [_rule(0, far_side, hi - extent)]}
    elif role in ("left", "top"):
        result.rules = {near: [_rule(0, near_side, lo)], far: [_rule(0, near_side, hi)]}
    elif role in ("right", "bottom"):
        result.rules = {near: [_rule(0, far_side, lo - extent)],
                        far: [_rule(0, far_side, hi - extent)]}
    elif role == "proportional":
        result.rules = {near: [_rule(0, near_side, lo), _rule(0, far_side, lo - extent)],
                        far: [_rule(0, near_side, hi), _rule(0, far_side, hi - extent)]}
    elif role == "center":
        middle = extent // 2
        result.rules = {near: [_rule(0, center, lo - middle)], far: [_rule(0, center, hi - middle)]}
    elif role == "self":  # левая граница без правила (остаётся на месте), правая — своя левая плюс ширина: надпись шапки колонок
        result.rules = {near: [], far: [_rule(index, near_side, hi - lo)]}
    elif role == "slide":  # ближняя граница — своя дальняя минус размер, дальняя — долей между краями: разделитель, держит размер и идёт долей прироста
        result.rules = {near: [_rule(index, far_side, lo - hi)],
                        far: [_rule(0, near_side, hi), _rule(0, far_side, hi - extent)]}
    elif role == "splitter":  # правило получает только граница, обращённая к разделителю; вторая остаётся как была
        result.rules = _splitter_rules(doc, holder, page, index, box, axis, other)
    elif role == "as":
        result.rules, result.flag, as_notes = _rules_as(doc, holder, page, index, box, axis, other)
    elif role == "keep":
        result.rules, result.flag = _rules_keep(holder, page, index, box, axis)
    elif role == "column":  # левая граница без правила (остаётся на месте), правая — долей между краями формы: первое поле шапки колонок
        result.rules = {near: [], far: [_rule(0, near_side, hi), _rule(0, far_side, hi - extent)]}
    else:
        neighbour = _neighbour(doc, holder, page, index, other)
        n_coords = _coords(neighbour)
        n_hi = n_coords[edit.WIDTH] if axis == "h" else n_coords[edit.HEIGHT]
        n_index = _index(neighbour)
        n_lo = n_coords[edit.X] if axis == "h" else n_coords[edit.Y]
        if role in ("before", "before-stretch"):
            # «назад»: дальняя граница к БЛИЖНЕЙ стороне соседа (правая — к левой, нижняя — к верхней), смещение — зазор со знаком
            far_rule = _rule(n_index, near_side, hi - n_lo)
            result.rules = {near: [_rule(index, far_side, lo - hi)] if role == "before" else [_rule(0, near_side, lo)], far: [far_rule]}
        elif role == "after":
            far_rules = [_rule(index, near_side, hi - lo)]
        elif role == "after-stretch":
            far_rules = [_rule(0, far_side, hi - extent)]
        else:  # after-column: дальняя граница долей между правой границей соседа и краем формы (внутренние поля шапки колонок)
            far_rules = [_rule(n_index, far_side, hi - n_hi), _rule(0, far_side, hi - extent)]
        if role not in ("before", "before-stretch"):
            result.rules = {near: [_rule(n_index, far_side, lo - n_hi)], far: far_rules}
    result.words, result.behaviour = _describe(axis, role, other, lo, hi,
                                               extent if need_edge else None, holder, doc)
    if role == "as":
        result.notes += as_notes
    if edge_words:
        result.notes.append(edge_words)
        tabs = _tabs_mark(doc, holder)
        if tabs:
            result.notes.append(tabs)
    result.notes += _evidence(axis, role, holder, doc, index)
    return result


def _find_named(doc, holder, name, what):
    found = [item for item in _items(holder) if (item.get(edit.NAME_BLOCK) or {}).get(edit.NAME) == name]
    if not found:
        raise edit.EditError(f"{what} {name!r} среди элементов этого родителя нет: правила копируются у элемента того же родителя")
    if len(found) > 1:
        raise edit.EditError(f"имя {name!r} носят {len(found)} элемента родителя — какой взять, по имени не решить; переименуйте один (`rename_element`)")
    if _coords(found[0]) is None or _index(found[0]) is None:
        raise edit.EditError(f"у элемента {name!r} блок координат не разобран — правила взять неоткуда")
    return found[0]


def _side_position(coords, side):
    x, y, x2, y2 = coords[edit.X], coords[edit.Y], coords[edit.WIDTH], coords[edit.HEIGHT]
    return {TOP: y, BOTTOM: y2, LEFT: x, RIGHT: x2, CENTER_V: (y + y2) // 2, CENTER_H: (x + x2) // 2}[side]


def _rules_as(doc, holder, page, index, box, axis, spec):
    """Правила границ оси по образцу: `({граница: [правила]}, флаг, слова)`.

    Правило читается «моя граница = сторона объекта + смещение». Объект и сторона остаются теми же, смещение пересчитывается под
    место: у края родителя и у третьего элемента — на сдвиг границы, у правила «к себе» — ещё и на сдвиг своей стороны. Правило к
    элементу из `with` переходит на названный вместо него: смещение — от его стороны. Образец на другой странице и пустые
    правила не копируются: у пустого правила нет объекта.
    """
    pattern = _find_named(doc, holder, spec["as"], "образца")
    if _index(pattern) == index:
        raise edit.EditError(f"образец {spec['as']!r} — сам элемент: копировать правила у себя незачем")
    coords = _coords(pattern)
    if coords.get(edit.PAGE) != page:
        raise edit.EditError(f"образец {spec['as']!r} лежит на странице {coords.get(edit.PAGE)}, а элемент — на {page}")
    pattern_index = _index(pattern)
    swap, names = {}, {}
    for old, new in (spec.get("with") or {}).items():
        replacement = _find_named(doc, holder, new, "замены в with")
        if _coords(replacement).get(edit.PAGE) != page:
            raise edit.EditError(f"замена {new!r} из with лежит на странице {_coords(replacement).get(edit.PAGE)}, а элемент — на {page}")
        swap[_index(_find_named(doc, holder, old, "элемента из with"))] = replacement
        names[_index(_find_named(doc, holder, old, "элемента из with"))] = old
    used = set()
    _label, near, far, flag = AXES[axis]
    edges = {TOP: box[1], BOTTOM: box[3], LEFT: box[0], RIGHT: box[2]}
    new_sides = {**edges, CENTER_V: (box[1] + box[3]) // 2, CENTER_H: (box[0] + box[2]) // 2}
    rules, notes = {}, []
    for border in (near, far):
        out = []
        delta = edges[border] - _side_position(coords, border)
        for which in edit.RULES:
            rule = coords[edit.ANCHORS[border]][which]
            target, side, offset = rule[edit.RULE_OBJECT], rule[edit.RULE_SIDE], rule[edit.RULE_OFFSET]
            if target == -1 or side == NO_SIDE:
                continue
            if target == index:
                raise edit.EditError(f"правило образца {spec['as']!r} ведёт к самому элементу: копия замкнула бы границу на себя")
            if target == pattern_index:
                out.append(_rule(index, side, offset + delta - (new_sides[side] - _side_position(coords, side))))
            elif target in swap:
                used.add(target)
                replacement = swap[target]
                out.append(_rule(_index(replacement), side, edges[border] - _side_position(_coords(replacement), side)))
                notes.append(f"правило образца к «{names[target]}» перенесено на «{(replacement.get(edit.NAME_BLOCK) or {}).get(edit.NAME)}»")
            else:
                out.append(_rule(target, side, offset + delta))
        rules[border] = out
    unused = [names[t] for t in swap if t not in used]
    if unused:
        raise edit.EditError(f"with называет {', '.join(repr(n) for n in unused)}, а у образца {spec['as']!r} на границах оси {axis} нет правила к нему: "
                             "замена ничего бы не поменяла — уберите ключ либо возьмите другой образец")
    manual = coords.get(flag)
    return rules, manual if isinstance(manual, bool) else True, notes


def _rules_keep(holder, page, index, box, axis):
    """Правила границ оси, какими они были у самого элемента: `({граница: [правила]}, флаг)`.

    Объекты и стороны правил остаются прежними, смещения пересчитываются под новое место: у края родителя и у третьего элемента — на сдвиг
    границы, у правила «к себе» — ещё и на сдвиг своей стороны. Элемент должен лежать в этом же родителе на этой же странице: правила на
    соседей и край прежнего родителя в другом родителе означали бы другое.
    """
    old = next((item for item in _items(holder) if _index(item) == index), None)
    if old is None:
        raise edit.EditError("привязка `keep` (оставить прежние правила) возможна, только если элемент остаётся в том же родителе: "
                             "правила на соседей и край прежнего родителя в другом родителе означали бы другое. Задайте привязку ролью")
    coords = _coords(old)
    if coords.get(edit.PAGE) != page:
        raise edit.EditError(f"привязка `keep` (оставить прежние правила) возможна, только если элемент остаётся на той же странице "
                             f"({coords.get(edit.PAGE)}), а назначена {page}: задайте привязку ролью")
    _label, near, far, flag = AXES[axis]
    edges = {TOP: box[1], BOTTOM: box[3], LEFT: box[0], RIGHT: box[2]}
    new_sides = {**edges, CENTER_V: (box[1] + box[3]) // 2, CENTER_H: (box[0] + box[2]) // 2}
    rules = {}
    for border in (near, far):
        out = []
        delta = edges[border] - _side_position(coords, border)
        for which in edit.RULES:
            rule = coords[edit.ANCHORS[border]][which]
            target, side, offset = rule[edit.RULE_OBJECT], rule[edit.RULE_SIDE], rule[edit.RULE_OFFSET]
            if target == -1 or side == NO_SIDE:
                continue
            if target == index:
                out.append(_rule(index, side, offset + delta - (new_sides[side] - _side_position(coords, side))))
            else:
                out.append(_rule(target, side, offset + delta))
        rules[border] = out
    manual = coords.get(flag)
    return rules, manual if isinstance(manual, bool) else True


def _neighbour(doc, holder, page, index, name):
    found = [item for item in _items(holder)
             if (item.get(edit.NAME_BLOCK) or {}).get(edit.NAME) == name]
    if not found:
        where = "формы" if holder is edit.container(doc) else \
            f"панели «{(holder.get(edit.NAME_BLOCK) or {}).get(edit.NAME)}»"
        raise edit.EditError(f"соседа {name!r} среди элементов {where} нет: цепочка идёт к "
                             "элементу того же родителя")
    if len(found) > 1:
        raise edit.EditError(f"имя {name!r} носят {len(found)} элемента родителя — к какому "
                             "вязать, по имени не решить; переименуйте один (`rename_element`)")
    item = found[0]
    if _index(item) == index:
        raise edit.EditError("цепочка к самому себе — это не цепочка: «размер держит» дальняя "
                             "граница и так пишет правилом к своей стороне")
    coords = _coords(item)
    if coords is None:
        raise edit.EditError(f"у соседа {name!r} блок координат не разобран — его края "
                             "взять неоткуда")
    if coords.get(edit.PAGE) != page:
        raise edit.EditError(f"сосед {name!r} лежит на странице {coords.get(edit.PAGE)}, а "
                             f"элемент — на {page}: правил на соседа с другой страницы снимок "
                             "не держит ни одного")
    return item


SPLITTER_THICKNESS = (4, 24)   # толщина разделителя корпуса по оси: от 4 до 24 px (386 разделителей с двумя соседями; 6 — 216, 4 — 140)


def splitter_item(doc, holder, page, index, name, axis=None):
    """Разделитель по имени — элемент того же родителя и страницы вида `Splitter`; ось `axis` (`h`/`v`) должна быть той, по которой он делит
    соседей: вертикальный (высота не меньше ширины) делит по горизонтали, горизонтальный — по вертикали."""
    item = _neighbour(doc, holder, page, index, name)
    if item.get("type") != "Splitter":
        raise edit.EditError(f"«{name}» — не разделитель (вид {item.get('type')}): роль {{\"splitter\": …}} привязывает границу соседа к "
                             "стороне элемента вида Splitter; к другому элементу — {\"after\": …}")
    c = _coords(item)
    tall = c[edit.HEIGHT] - c[edit.Y] >= c[edit.WIDTH] - c[edit.X]
    if axis is not None and tall != (axis == "h"):
        raise edit.EditError(f"разделитель «{name}» {'вертикальный' if tall else 'горизонтальный'}: он делит соседей по "
                             f"{'горизонтали' if tall else 'вертикали'}, а ось {axis} — по "
                             f"{'горизонтали' if axis == 'h' else 'вертикали'}; задайте ось {'h' if tall else 'v'}")
    return item


def _splitter_rules(doc, holder, page, index, box, axis, name):
    """Правило границы элемента, обращённой к разделителю: `{граница: [правило]}`.

    Элемент слева (выше) разделителя привязывает правую (нижнюю) границу к его левой (верхней) стороне, элемент справа (ниже) — левую
    (верхнюю) к правой (нижней); смещение — координата границы минус координата стороны. Вторую границу оси операция не трогает: её
    привязывает человек к краю родителя или к другому элементу. Лежащий по обе стороны разделителя, внутри него или не рядом (вне длины
    разделителя) элемент — отказ: сторону по такому положению не вывести.
    """
    item = splitter_item(doc, holder, page, index, name, axis)
    c = _coords(item)
    sx, sy, sx2, sy2 = c[edit.X], c[edit.Y], c[edit.WIDTH], c[edit.HEIGHT]
    x, y, x2, y2 = box
    lo, hi = (x, x2) if axis == "h" else (y, y2)
    s_lo, s_hi = (sx, sx2) if axis == "h" else (sy, sy2)
    cross = (min(y2, sy2) - max(y, sy)) if axis == "h" else (min(x2, sx2) - max(x, sx))
    near, far = (LEFT, RIGHT) if axis == "h" else (TOP, BOTTOM)
    words = ("левее", "правее") if axis == "h" else ("выше", "ниже")
    if cross <= 0:
        raise edit.EditError(f"элемент не рядом с разделителем «{name}»: по {'вертикали' if axis == 'h' else 'горизонтали'} они не пересекаются, "
                             "и сторону по такому положению не вывести")
    if hi <= s_hi and lo < s_lo:
        return {far: [_rule(_index(item), near, hi - s_lo)]}
    if lo >= s_lo and hi > s_hi:
        return {near: [_rule(_index(item), far, lo - s_hi)]}
    raise edit.EditError(f"элемент лежит не {words[0]} и не {words[1]} разделителя «{name}» (внутри него или по обе стороны): сторону, к которой "
                         "привязать границу, по такому положению не вывести — подвиньте элемент (move_element) или привяжите границу ролью "
                         "оси")


def _describe(axis, role, other, lo, hi, extent, holder, doc):
    """Слова оси: что записано и что элемент будет делать при растяжении родителя."""
    top = holder is edit.container(doc)
    panel = (holder.get(edit.NAME_BLOCK) or {}).get(edit.NAME)
    whose = "окна" if top else f"панели «{panel}»"
    with_whom = "окном" if top else f"панелью «{panel}»"
    if role in ("before", "before-stretch"):
        side = "левой" if axis == "h" else "верхней"
        edge = "левым" if axis == "h" else "верхним"
        size = "ширина" if axis == "h" else "высота"
        words = f"перед соседом «{other}» (дальняя граница — к его {side} стороне)"
        if role == "before":
            return words, f"сдвигается вместе с «{other}» назад, {size} держится"
        return words + ", ближняя граница — к краю", \
            f"дальняя граница идёт за «{other}», ближняя — с {edge} краем {whose}: занимает место, которое освобождает сосед"
    if role in ("after", "after-stretch", "after-column"):
        side = "правой" if axis == "h" else "нижней"
        words = f"за соседом «{other}» ({side} границей)"
        if role == "after-column":
            share = hi / extent if extent else 0
            return words + ", дальняя граница — долей между границей соседа и краем окна", (
                f"ближняя граница сдвигается за «{other}», дальняя проходит долей {share:.0%} прироста ширины {whose} "
                "от границы соседа: колонка шапки растягивается и сдвигается")
        if role == "after":
            size = "ширина" if axis == "h" else "высота"
            return words, f"сдвигается за «{other}», {size} держится"
        edge = "правым" if axis == "h" else "нижним"
        return words + f", дальняя граница — к краю", \
            f"ближняя граница сдвигается за «{other}», дальняя — с {edge} краем {whose}: растягивается"
    if role == "splitter":
        return (f"к стороне разделителя «{other}» (граница, обращённая к нему; вторая граница не менялась)",
                f"граница идёт за разделителем «{other}»: сдвигается, когда он сдвигается")
    if role == "keep":
        return ("прежние (те же объекты и стороны)", "правила те же, смещения пересчитаны под новое место")
    if role == "as":
        return (f"как у «{other['as']}» (правила границ скопированы, смещения пересчитаны под место)",
                "ведёт себя как образец: правила тех же объектов и сторон")
    words = ROLE_WORDS[(axis, role)]
    if role == "self":
        return words, "остаётся на месте по левой границе, ширина сохраняется"
    if role == "slide":
        share = hi / extent if extent else 0
        size = "ширина" if axis == "h" else "высота"
        return words, (f"дальняя граница проходит долей {share:.0%} прироста {'ширины' if axis == 'h' else 'высоты'} {whose}, ближняя "
                       f"идёт за ней: сдвигается, {size} держится")
    if role == "column":
        share = hi / extent if extent else 0
        return words, (f"левая граница остаётся на месте, правая проходит долей {share:.0%} прироста ширины {whose}: "
                       "колонка шапки растягивается и сдвигает следующую")
    if axis == "h":
        what = {"stretch": f"растягивается по ширине вместе с {with_whom}",
                "left": "остаётся на месте у левого края",
                "right": f"сдвигается вправо с правым краем {whose}",
                "center": f"держится середины {whose}: сдвигается на половину прироста ширины"}
    else:
        what = {"stretch": f"растягивается по высоте вместе с {with_whom}",
                "top": "остаётся на месте у верхнего края",
                "bottom": f"сдвигается вниз с нижним краем {whose}",
                "center": f"держится середины {whose}: сдвигается на половину прироста высоты"}
    if role == "proportional":
        near, far = lo / extent if extent else 0, hi / extent if extent else 0
        growth = "ширины" if axis == "h" else "высоты"
        grow = far - near
        return words, (f"растягивается и сдвигается долей: ближняя граница проходит {near:.0%} прироста "
                       f"{growth} {whose}, дальняя {far:.0%} — элемент растягивается на {grow:.0%} прироста")
    return words, what[role]


def _header_label(holder, index):
    """Элемент — надпись (запись шапки колонок описывает только надпись первой колонки)."""
    item = next((i for i in _items(holder) if index is not None and _index(i) == index), None)
    return item is not None and item.get("type") == "Label"


def _evidence(axis, role, holder, doc, index=None):
    """Свидетельства роли — перечнем: проверенное словами, шире проверенного — пометками.

    Пометок бывает две разом: пропорция вложенного по вертикали шире проверенного и парой на обеих
    границах, и нижним краем панели.
    """
    words = "по горизонтали" if axis == "h" else "по вертикали"
    notes = []
    if role == "center":
        notes.append(edit._on_corpus("set_anchors/center", "центр", CORPUS_CENTER[words],
                                     counted="правил к центру родителя с встречной "
                                             "записью")[2:])
    if role == "proportional":
        notes.append(edit._on_corpus("set_anchors/proportional-both",
                                     "пропорция на обеих границах",
                                     CORPUS_PROPORTIONAL_BOTH[words],
                                     counted=f"осей {words} с парой на обеих границах")[2:])
    nested_far = holder is not edit.container(doc) and axis == "v" and role in (
        "stretch", "bottom", "proportional", "after-stretch", "slide")
    if nested_far:
        ok, total = CORPUS_PANEL_EDGES["нижнему"]
        notes.append(edit._on_corpus("set_anchors/panel-bottom", "нижний край панели", total,
                                     counted="правил вложенных к нижнему краю панели")[2:])
    if role == "self" and not _header_label(holder, index):
        return ["привязка «к себе» — запись платформы для элемента, не привязанного ни к чему: при растяжении окна он остаётся на месте"]
    return notes or [EVIDENCE[role]]


def write(coords, plans):
    """Правила и флаги осей в блок координат."""
    for axis_plan in plans:
        _label, _near, _far, flag = AXES[axis_plan.axis]
        for border in axis_plan.rules:
            rules = axis_plan.rules[border] + [_none()] * (2 - len(axis_plan.rules[border]))
            for rule_name, rule in zip(edit.RULES, rules):
                coords[edit.ANCHORS[border]][rule_name].update(rule)
        coords[flag] = axis_plan.flag


# Центр оси зависит от ОБЕИХ её сторон: середина объекта движется, когда движется любая из них.
CENTER_SIDES = {CENTER_V: (TOP, BOTTOM), CENTER_H: (LEFT, RIGHT)}
# Циклы в корпусе (`corpus.FROZEN_STAMP`): родителей с элементами; из них тех, где элементы связаны
# КОЛЬЦОМ по разным границам, и тех, где граница через соседей зависит от самой себя.
CORPUS_CYCLES = {"носителей": 14001, "кольцо элементов": 22, "цикл границ": 0}


def _depends_on(rule):
    """Границы, за которыми идёт граница с этим правилом: `[(индекс, граница)]`.

    Край родителя (объект 0) и «нет» — пусто: край родителя движется окном или панелью, а не
    элементами родителя, и цикла через него не бывает. Центр — обе стороны своей оси."""
    target, side = rule.get(edit.RULE_OBJECT), rule.get(edit.RULE_SIDE)
    if not isinstance(target, int) or isinstance(target, bool) or target <= 0:
        return []
    sides = CENTER_SIDES.get(side, (side,) if side in (TOP, BOTTOM, LEFT, RIGHT) else ())
    return [(target, one) for one in sides]


def border_graph(holder):
    """Граф ГРАНИЦ родителя: `{(индекс, граница): {(индекс, граница), …}}` — за кем она идёт.

    Узел — граница элемента, а не элемент: элементы, связанные друг с другом по РАЗНЫМ
    границам (`A.лево → B.лево`, `B.право → A.право`), кольца не образуют, пока ни одна
    граница не зависит от самой себя. Правило «к себе» — ребро внутри элемента (низ → свой
    верх): без него цепочка `after` (дальняя граница держит размер от ближней) цикла не
    замкнула бы."""
    edges = {}
    for item in _items(holder):
        coords, me = _coords(item), _index(item)
        if coords is None:
            continue
        for border, key in enumerate(edit.ANCHORS):
            anchor = coords.get(key)
            for rule_name in edit.RULES:
                rule = anchor.get(rule_name) if isinstance(anchor, dict) else None
                if isinstance(rule, dict):
                    edges.setdefault((me, border), set()).update(_depends_on(rule))
    return edges


def border_loop(edges, start):
    """Путь по границам от `start` обратно к ней — `[start, …, start]` — или `None`."""
    stack = [(node, [start, node]) for node in sorted(edges.get(start, ()), reverse=True)]
    seen = set()
    while stack:
        node, path = stack.pop()
        if node == start:
            return path
        if node in seen:
            continue
        seen.add(node)
        stack += [(nxt, path + [nxt]) for nxt in sorted(edges.get(node, ()), reverse=True)]
    return None


def _cycle(doc, holder, index, plans):
    """Замкнётся ли граница на себя, если записать эти правила: путь по границам или `None`.

    Граф — границ (`border_graph`), и цикл ищется только через границы, которые операция меняет:
    кольцо, которого она не касается, — не её дело. Поиск по графу элементов отвергал бы раскладки,
    которые платформа пишет сама: элементы бывают связаны кольцом по разным границам, и роль
    элемента кольца получала бы отказ — даже «к нижнему краю», которая соседа не называет вовсе.
    """
    names = {_index(item): (item.get(edit.NAME_BLOCK) or {}).get(edit.NAME)
             for item in _items(holder)}
    edges = border_graph(holder)
    changed = [border for p in plans for border in p.rules]
    for p in plans:
        for border, rules in p.rules.items():
            edges[(index, border)] = {node for rule in rules for node in _depends_on(rule)}
    for border in changed:
        path = border_loop(edges, (index, border))
        if path:
            return " → ".join(f"{names.get(i) or f'#{i}'}.{SIDE_LETTERS[b]}" for i, b in path)
    return None


def set_anchors(doc, element, h=None, v=None, unverified=False):
    """Привязки элемента по именам ролей осей — ручной стиль с флагами.

    `h` — горизонталь: `stretch` (лево и право к краям родителя — растягивается), `left` (обе к левому —
    остаётся на месте), `right` (обе к правому — сдвигается вправо), `proportional` (обе — долей между краями),
    `center` (обе к середине родителя), `self` (левая граница без правила, правая от своей левой —
    надпись шапки колонок), `column` (левая без правила, правая долей между краями — первое поле
    шапки колонок), `slide` (ближняя граница — своя дальняя минус размер, дальняя — долей между краями родителя: разделитель сдвигается на долю
    прироста и держит размер); `v` — вертикаль: `stretch`, `top`, `bottom`, `proportional`, `center`, `slide`. Сторона соседа разделителя —
    `{"splitter": "<имя разделителя>"}`: правило получает только граница, обращённая к нему (у левого/верхнего соседа дальняя — к ближней
    стороне разделителя, у правого/нижнего ближняя — к дальней), сторону берут по положению; вторая граница оси не меняется. Цепочка к
    соседу того же родителя — `{"after": "<имя>"}` (ближняя граница за его дальней стороной, дальняя
    держит размер: сдвигается за ним), `{"after": "<имя>", "role": "stretch"}` (дальняя — к краю родителя:
    растягивается) либо `{"after": "<имя>", "role": "column"}` (дальняя — долей между границей соседа и
    краем родителя; только `h`). Копия правил образца — `{"as": "<имя образца>"[, "with": {"<имя в правилах образца>": "<замена>"}]}` (смещения пересчитаны под место; не проверялось в предприятии). Ось, которую не назвали, остаётся как была.

    Операция пишет оба правила обеих границ оси (второе — пропорциональное или «нет»), поднимает
    флаг «Ручная привязка» оси и ведёт встречные записи: снимает все, называющие элемент, и ставит
    заново по правилам — у соседа в его списке зависимых, у родителя в списке края. Без встречной
    записи правило в предприятии не работает.

    Смещения: смещение = координата − сторона объекта; край родителя — у формы её размер (минус
    рамка), у панели — по направляющим страницы (`holder_edges`). Отчёт называет записанное и то,
    что элемент будет делать при растяжении родителя.
    """
    if h is None and v is None:
        raise edit.EditError("назовите хотя бы одну ось: h (горизонталь) или v (вертикаль) — "
                             f"роли {', '.join(H_ROLES)} / {', '.join(V_ROLES)} или "
                             "{\"after\": \"<имя соседа>\"}")
    place = edit.find_element(doc, element)
    coords = _coords(place.element)
    if coords is None or not all(isinstance(coords.get(k), dict) for k in edit.ANCHORS):
        raise edit.EditError(f"у элемента {element!r} блок координат не разобран (метка 3): "
                             "привязки писать некуда")
    index = _index(place.element)
    box = (coords[edit.X], coords[edit.Y], coords[edit.WIDTH], coords[edit.HEIGHT])
    page = coords.get(edit.PAGE)
    plans = [plan(doc, place.holder, page, index, box, axis, value, unverified)
             for axis, value in (("h", h), ("v", v)) if value is not None]
    _need_lists(place.holder, [p.rules for p in plans], element)
    loop = _cycle(doc, place.holder, index, plans)
    if loop:
        holders = f"{CORPUS_CYCLES['носителей']:,}".replace(",", " ")
        raise edit.EditError(
            f"цепочка замкнулась бы — граница зависела бы от самой себя: {loop} (`.t .b .l .r` — "
            "верх, низ, лево, право). Такая граница раскладку не решает, и циклов границ снимок "
            f"не держит ни одного (у {holders} родителей); элементы, связанные друг с другом по "
            "РАЗНЫМ границам, — не цикл, такие раскладки операция принимает")
    write(coords, plans)
    dropped, put = sync(doc, index)
    return f"{element}: {plans_words(plans, index, place.holder)}; {records_words(put, dropped)}"


def _need_lists(holder, rule_sets, element):
    """Правило к краю родителя без списков родителя было бы мёртвым — отказ заранее.

    `rule_sets` — наборы правил `{граница: [правило, …]}`: у ролей — по оси, у пары `anchor="form"`
    — один. Проверка одна на обе дороги.
    """
    if holder_lists(holder) is not None:
        return
    if any(rule[edit.RULE_OBJECT] == 0 for rules_by in rule_sets for rules in rules_by.values()
           for rule in rules):
        raise edit.EditError(f"у родителя элемента {element!r} не разобраны списки блока "
                             "раскладки: правило к краю без встречной записи в предприятии не "
                             "работает, а записать её некуда")


def axis_words(axis_plan, index, holder, extra=None):
    """Слова одной оси: роль, правила границ, флаг и поведение при растяжении."""
    label, near, far, _flag = AXES[axis_plan.axis]
    names = {_index(i): (i.get(edit.NAME_BLOCK) or {}).get(edit.NAME) for i in _items(holder)}
    names.update(extra or {})
    rules = []
    for border in (near, far):
        if border not in axis_plan.rules:  # роль называет одну границу оси: вторую не меняла
            continue
        text = "|".join(rule_text(rule, index, names) for rule in axis_plan.rules[border]) or "без правила"
        rules.append(f"{BORDER_WORDS[border]} {text}")
    return (f"{label} — {axis_plan.words}: {', '.join(rules)}, флаг «Ручная привязка» {'☑' if axis_plan.flag else '☐'} — "
            f"при растяжении {axis_plan.behaviour}")


def plans_words(plans, index, holder, extra=None):
    """Слова всех осей и — один раз — край родителя и свидетельства."""
    notes = []
    for axis_plan in plans:
        notes += [note for note in axis_plan.notes if note not in notes]
    return "; ".join([axis_words(p, index, holder, extra) for p in plans] + notes)


# ── Роли у add_element ────────────────────────────────────────────────────────────────────────

BOTH_AXES = ("stretch", "proportional", "center", "keep")


def anchor_axes(anchor):
    """`anchor` у `add_element` → `(h, v)` ролей либо `None` у `self` и `form`.

    Строка роли, общей для обеих осей (`stretch`, `proportional`, `center`), — обе оси;
    `left`/`right` — горизонталь, `top`/`bottom` — вертикаль, вторая ось остаётся «к себе»;
    объект `{"h": …, "v": …}` — как у `set_anchors`."""
    if anchor in ("self", "form"):
        return None
    if isinstance(anchor, str):
        if anchor in BOTH_AXES:
            return anchor, anchor
        if anchor in ("left", "right"):
            return anchor, None
        if anchor in ("top", "bottom"):
            return None, anchor
        raise edit.EditError(
            f"привязка {anchor!r} не знаю: 'self' (к своим границам — АвтоПравила формы "
            "поставят свои при сохранении), 'form' (низ и право — долей между краями родителя, "
            "см. справку), роль set_anchors строкой — stretch, proportional, center (обе оси), "
            "left/right (горизонталь), top/bottom (вертикаль) — либо {\"h\": …, \"v\": …}")
    if isinstance(anchor, dict) and anchor and set(anchor) <= {"h", "v"}:
        return anchor.get("h"), anchor.get("v")
    raise edit.EditError(f"привязка — строка роли или {{\"h\": …, \"v\": …}}, а пришло "
                         f"{anchor!r}")


def form_pair(doc, holder, page, box, unverified=False):
    """Правила `anchor="form"`: низ и право — пропорциональная пара между краями родителя.

    Первое правило — от ближнего края (`F.t+низ`, `F.l+право`), второе — от дальнего; верх и лево
    без правила, флагов нет. Платформа файл с такой парой (без записей) открывает, но при
    пересохранении сводит её к одиночным правилам `F.b-8`/`F.r-30` и дописывает к ним строки
    родителя — пару не удерживает. Предприятие ведёт границу с парой долей, а без встречных записей
    — никак; пара с записями не проверялась (вариант `add_element/form-pair`). Края — родителя, а не
    формы: у вложенного элемента объект 0 — край панели.
    """
    x, y, x2, y2 = box
    right, bottom, _words = file_edges(doc, holder, page, unverified)
    return {BOTTOM: [_rule(0, TOP, y2), _rule(0, BOTTOM, y2 - bottom)],
            RIGHT: [_rule(0, LEFT, x2), _rule(0, RIGHT, x2 - right)]}


FORM_WORDS = ("anchor=\"form\": низ и право — ДОЛЕЙ между краями родителя (пропорциональная "
              "пара: первое правило от ближнего края, второе от дальнего), верх и лево без "
              "правила, флагов нет — при растяжении окна элемент растягивается и сдвигается на долю прироста "
              "(низ/высота родителя по высоте, право/ширина по ширине), а не прижимается к краю; "
              "«к краю» — anchor={\"h\": \"stretch\", …} или роли set_anchors")


def form_words(doc, holder):
    """Отчёт пары `anchor="form"`: что записано и пометки шире проверенного."""
    words = FORM_WORDS + edit._on_corpus("add_element/form-pair", "пара form",
                                         CORPUS_FORM_PAIR["элементов"],
                                         counted="элементов с такой парой")
    tabs = _tabs_mark(doc, holder)
    return words + (f"; {tabs}" if tabs else "")
