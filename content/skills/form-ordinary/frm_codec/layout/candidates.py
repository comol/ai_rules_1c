"""Выбор привязок нового элемента перебором кандидатов с проверкой на модели раскладки.

Привязка нового элемента — правила его границ. Копия правил соседа не всегда верна: элемент, привязанный иначе, чем его столбец, при
растяжении окна расходится с соседями или упирается в них. Поэтому после постановки элемента движок пробует несколько вариантов
привязки по каждой оси отдельно и оставляет лучший.

**Кандидаты** (`h_candidates`, `v_candidates`; запись — аргумент `h`/`v` операции `set_anchors`):

* привязки, как они получились при постановке (копия у образца по столбцу), — первый кандидат;
* копия правил (`{"as": …}`) у элемента столбца с другим поведением, у элемента той же строки в соседнем столбце и (по вертикали) у надписи своей пары;
* цепочка за надписью своей пары (`{"after": …}`), только по горизонтали;
* роли: `left`, `stretch`, `right`, `proportional` по горизонтали; `top`, `bottom` по вертикали.

**Проверка** (`assess`) — раскладка формы с новым элементом (`layout.Layout`) при наборе размеров окна: проектный, минимальный (нижний
предел формы), в полтора и вдвое больше; ширина и высота меняются порознь. Кандидат отбрасывается, если:

* сузились пределы раскладки (`limits.compare`) сверх тех сужений, которые есть у всех кандидатов (так: любой элемент под последней
  строкой сужает предел высоты; сужение, объяснённое ужатием таблицы, не считается);
* новый элемент или зависящие от него наезжают на соседей при размере из набора, хотя в проекте не пересекались;
* правила образуют цикл или у нового элемента есть мёртвое правило (без встречной записи).

**Выравнивание** (штраф, а не отказ): края, совпадавшие у нового элемента и соседей по столбцу (тот же тип) или по строке (в проекте
не дальше `TOL` px), должны совпадать при всех размерах набора; зазор между надписью и её полем постоянен. Край, который расходится
уже у соседей между собой, не учитывается: форма была такой и до правки.

**Выбор**: меньший штраф; при равном штрафе — поведение по ширине как у большинства столбца; затем — меньше правил к третьим
элементам; затем порядок кандидатов. Если привязки после постановки не дают ни отказа, ни штрафа и ведут себя как большинство столбца,
перебор не нужен. Не прошёл ни один кандидат — отказ словами.
"""
import copy
import pickle

from .. import layout, limits, patterns
from ..edit.base import EditError

TOL = 2             # края совпадают (и выравнивание держится), если различаются не больше чем на столько px
SLACK = 0.5         # пересечение прямоугольников при размере из набора считается наездом, если больше стольких px по обеим осям
GAP_NEAR = 60       # надпись пары — ближайшая слева на строке поля не дальше стольких px
STRETCHY_ROLES_H = ("left", "stretch", "right", "proportional")
ROLES_V = ("top", "bottom")
CONTAINERS = ("Panel", "GroupBox")
NOT_ALIGNED = ("CommandBar", "Splitter", "Panel", "GroupBox")
SIZE_UP = (1.5, 2.0)
SHOWN = 3           # сколько отброшенных кандидатов называет отчёт
ALIGN_BREAK = 20    # элемент расходится с соседями при размере из набора больше чем на столько px — кандидат «ломает» выравнивание и отбрасывается, как сужающий
NO_LIMIT = 10 ** 6  # «px сужения», если до правки предела не было


def fast_copy(doc):
    """Копия документа (заметно быстрее `copy.deepcopy`; документ — только словари, списки и числа со строками)."""
    try:
        return pickle.loads(pickle.dumps(doc, protocol=pickle.HIGHEST_PROTOCOL))
    except (pickle.PicklingError, TypeError, AttributeError):
        return copy.deepcopy(doc)


# ── Раскладка при наборе размеров ─────────────────────────────────────────────────────────────

def _find(form, name):
    found = [i for i in layout._all_items(form) if i.name == name]
    return found[0] if len(found) == 1 else None


def fixed_size(doc):
    """У формы снято «Изменять размер»: окно не растягивается, поэтому перебор привязок не проверяет растяжение (пределы раскладки, выравнивание и наезды при других
    размерах окна) и привязки соседей не перестраивает ради него."""
    return isinstance(doc, dict) and doc.get("size_change") == "DontChange"


def size_set(snap, axis):
    """Размеры оси: проектный, минимальный (нижний предел формы, без предела — 0,6 проектного), в полтора и вдвое больше."""
    base = snap.size[axis]
    low = snap.ranges[axis][0]
    least = int(base * 0.6) if low is None else min(low, base)
    return sorted({base, least, *(round(base * k) for k in SIZE_UP)})


def _window(snap, axis, value):
    """Размер окна `(ширина, высота)`: по оси `axis` — `value`, по другой — проектный."""
    return (value, snap.size[1]) if axis == 0 else (snap.size[0], value)


def _layout_at(form, w, h):
    return layout.Layout(form, w, h, hide=False, scroll=False)


class Verdict:
    """Результат проверки одного кандидата: `hard` — причины отказа, `penalty` — `(нарушений выравнивания, лишних px)`, `notes` — слова
    о нарушениях, `narrowed` — сужения пределов `{(ось, направление)}`, `thirds` — число правил к третьим элементам, `behaviour` —
    поведение по ширине нового элемента.
    """

    def __init__(self):
        self.hard, self.penalty, self.notes = [], (0, 0), []
        self.narrowed, self.thirds, self.behaviour, self.signature = set(), 0, None, None
        self.worst, self.narrow_px = 0, {}
        self.frozen = set()     # оси, по которым у формы появился предел роста меньше `layout.EARLY` px, а до правки его не было (`_freezes`)

    @property
    def breaking(self):
        """Элемент расходится с соседом больше чем на `ALIGN_BREAK` px."""
        return self.worst > ALIGN_BREAK

    @property
    def narrow_total(self):
        return sum(self.narrow_px.values())

    @property
    def clean(self):
        return not self.hard and self.penalty == (0, 0) and not self.narrowed


def _rules_signature(item):
    return tuple(tuple(None if r is None else (r.obj if r.obj != item.index else "self", r.side, r.off) for r in pair) for pair in item.rules)


def _thirds(item):
    return sum(1 for pair in item.rules for r in pair if r is not None and r.obj not in (0, item.index))


def _same_row(a, b):
    return min(a[3], b[3]) - max(a[1], b[1]) > 0 and min(a[3] - a[1], b[3] - b[1]) > 0 and \
        (min(a[3], b[3]) - max(a[1], b[1])) * 2 >= min(a[3] - a[1], b[3] - b[1])


def _overlap(a, b):
    return min(a[2], b[2]) - max(a[0], b[0]) > SLACK and min(a[3], b[3]) - max(a[1], b[1]) > SLACK


def _contains(outer, inner):
    return outer[0] <= inner[0] and outer[1] <= inner[1] and inner[2] <= outer[2] and inner[3] <= outer[3]


def _pair_gap(items, ints, item, pair_of):
    """Зазор между надписью и её полем при раскладке `ints` либо `None`: `pair_of(item)` — второй элемент пары."""
    other = pair_of(item)
    if other is None:
        return None
    a, b = (ints[other.index], ints[item.index]) if other.box[0] < item.box[0] else (ints[item.index], ints[other.index])
    return b[0] - a[2]


def _label_of(items, field):
    """Ближайшая слева надпись на строке поля (не дальше `GAP_NEAR` px) либо `None`."""
    best = None
    for o in items:
        if o is field or o.type != "Label" or not _same_row(o.box, field.box):
            continue
        gap = field.box[0] - o.box[2]
        if -TOL <= gap <= GAP_NEAR and (best is None or gap < field.box[0] - best.box[2]):
            best = o
    return best


def _field_of(items, label):
    best = None
    for o in items:
        if o is label or o.type != "TextBox" or not _same_row(o.box, label.box):
            continue
        gap = o.box[0] - label.box[2]
        if -TOL <= gap <= GAP_NEAR and (best is None or gap < best.box[0] - label.box[2]):
            best = o
    return best


def _neighbours(form, item):
    """Видимые элементы того же родителя и страницы, кроме самого элемента."""
    return [o for o in form.holders[item.holder].children if o is not item and o.visible and o.page == item.page]


def _alignment(form, layouts, news, penalty, notes, ignore=()):
    """Нарушения выравнивания новых элементов `news` (список `Item` формы): `layouts` — `[(размер, ints)]`; `penalty` — `[нарушений, лишних px,
    наибольшее расхождение]`."""
    for item in news:
        near = [o for o in _neighbours(form, item) if o.index not in {n.index for n in news} and o.type not in NOT_ALIGNED
                and o.qualified() not in ignore]
        pairs = []
        for key, edge in (("left", 0), ("right", 2)):
            pairs.append((key, edge, [o for o in near if o.type == item.type and abs(o.box[edge] - item.box[edge]) <= TOL]))
        for key, edge in (("top", 1), ("bottom", 3)):
            pairs.append((key, edge, [o for o in near if _same_row(o.box, item.box) and abs(o.box[edge] - item.box[edge]) <= TOL]))
        for key, edge, group in pairs:
            if not group:
                continue
            if len(group) >= 2 and any(abs((ints[o.index][edge] - ints[group[0].index][edge])) > TOL for _s, ints in layouts for o in group[1:]):
                continue    # у соседей выравнивание расходилось и до правки
            worst, where = 0, None
            for size, ints in layouts:
                got = max(abs(ints[item.index][edge] - ints[o.index][edge]) for o in group)
                if got - TOL > worst:
                    worst, where = got - TOL, size
            if worst:
                penalty[0] += 1
                penalty[1] += worst
                penalty[2] = max(penalty[2], worst + TOL)
                notes.append(f"{_edge_word(key)} края «{item.label()}» и соседей ({', '.join(o.label() for o in group[:2])}) расходятся при "
                             f"размере {where[0]}×{where[1]} на {worst + TOL} px")
        gap_pairs = _gaps(_neighbours(form, item), item)
        for other, kind in gap_pairs:
            base = _gap_between(item, other)
            same = [o for o in near if o.type == item.type and abs(o.box[0] - item.box[0]) <= TOL and o is not other]
            varied = False
            for o in same:
                mate = _label_of(near, o) if item.type == "TextBox" else _field_of(near, o)
                if mate is None:
                    continue
                g = [_gap_between(o, mate, ints) for _s, ints in layouts]
                if max(g) - min(g) > TOL:
                    varied = True
                    break
            if varied:
                continue
            gaps = [(size, _gap_between(item, other, ints)) for size, ints in layouts]
            worst = max(abs(g - base) for _s, g in gaps)
            if worst > TOL:
                size = max(gaps, key=lambda p: abs(p[1] - base))[0]
                penalty[0] += 1
                penalty[1] += worst - TOL
                penalty[2] = max(penalty[2], worst)
                notes.append(f"зазор «{item.label()}» → «{other.label()}» не постоянен: {base} px в проекте, при размере {size[0]}×{size[1]} "
                             f"{dict(gaps)[size]} px")


def _edge_word(key):
    return {"left": "левые", "right": "правые", "top": "верхние", "bottom": "нижние"}[key]


def _gaps(near, item):
    if item.type == "TextBox":
        label = _label_of(near, item)
        return [(label, "label")] if label is not None else []
    if item.type == "Label":
        field = _field_of(near, item)
        return [(field, "field")] if field is not None else []
    return []


def _gap_between(a, b, ints=None):
    left, right = (a, b) if a.box[0] <= b.box[0] else (b, a)
    if ints is None:
        return right.box[0] - left.box[2]
    return ints[right.index][0] - ints[left.index][2]


def _collisions(form, layouts, news):
    """Наезды нового элемента и зависящих от него: `[слова]`. Пара, пересекавшаяся в проекте, не считается."""
    out = []
    ids = {n.index for n in news}
    watch = set(ids)
    for o in layout._all_items(form):
        if any(r is not None and r.obj in ids for pair in o.rules for r in pair):
            watch.add(o.index)
    items = {i.index: i for i in layout._all_items(form)}
    for index in sorted(watch):
        a = items[index]
        for o in _neighbours(form, a):
            if o.type in CONTAINERS or a.type in CONTAINERS or (index not in ids and o.index in watch and o.index < index):
                continue
            if _overlap(a.box, o.box) or _contains(a.box, o.box) or _contains(o.box, a.box):
                continue
            for size, ints in layouts:
                if _overlap(ints[index], ints[o.index]):
                    out.append(f"«{a.label()}» наезжает на «{o.label()}» при размере {size[0]}×{size[1]}")
                    break
    return out


class Before:
    """Форма до правки, прочитанная один раз на весь выбор: пределы, имена элементов в цикле."""

    def __init__(self, doc):
        self.doc = doc
        self.snap = limits.snapshot(doc)
        self.cycled = set()
        if self.snap is not None:
            coef = layout.coefficients(self.snap.form, hide=False)
            self.cycled = {i.name for i in layout._all_items(self.snap.form) if coef.get(i.index) is None and i.name}
        self._broken = None

    def broken(self):
        """Виновники диагноза поломок формы до правки `{имя: оси}` (`repair.culprit_axes`); считаются при первом обращении."""
        if self._broken is None:
            from .. import repair
            self._broken = repair.culprit_axes(self.doc)
        return self._broken


def _freezes(was, now, form, coef):
    """Оси, по которым правка «замораживает» форму: предел роста стал меньше `layout.EARLY` px (на форме есть растягиваемые элементы), а до
    правки был дальше либо не было вовсе. Предел, который уже был близко, заморозкой правки не считается."""
    from .. import repair
    out = set()
    for axis in (0, 1):
        a, b = was.room[(axis, 1)], now.room[(axis, 1)]
        if b is not None and b < layout.EARLY and (a is None or a >= layout.EARLY) and repair._stretchy(form, coef, axis):
            out.add(axis)
    return out


def _narrow_px(was, now, changes):
    """Сужение пределов в px по `(ось, направление)`: запас роста или сжатия до правки минус после; предела не было — `NO_LIMIT`."""
    out = {}
    for c in changes:
        a, b = was.room[(c.axis, c.direction)], now.room[(c.axis, c.direction)]
        out[(c.axis, c.direction)] = NO_LIMIT if a is None else abs(a - b)
    return out


def assess(before, after, names, axes=(0, 1), ignore=()):
    """Проверка формы `after` (в ней новые элементы `names`) против `before` (документ либо `Before`): `Verdict` либо `None`, если
    раскладка форму не читает."""
    if not isinstance(before, Before):
        before = Before(before)
    if before.snap is None:
        return None
    verdict = Verdict()
    try:
        form = layout.read(after)
        snap = limits.Snapshot(form, layout.coefficients(form))
        coef = layout.coefficients(form, hide=False)
    except limits.READ_ERRORS:
        verdict.hard.append("раскладка формы с новым элементом не читается")
        return verdict
    news = [_find(form, n) for n in names]
    if any(n is None for n in news):
        return None
    for n in news:
        if coef.get(n.index) is None:
            if n.name not in before.cycled:  # цикл был у этого же элемента до правки (перенос) — его привязки не новые
                verdict.hard.append(f"привязки «{n.label()}» образуют цикл: граница зависит от самой себя")
        else:
            verdict.behaviour = verdict.behaviour or layout.horizontal_behaviour(coef[n.index][2], coef[n.index][3])
    ids = {n.index for n in news}
    for item, border, _which, rule, why in layout.dead_rules(form):
        if item.index in ids or rule.obj in ids:
            verdict.hard.append(f"мёртвое правило «{item.label()}» ({layout.BORDERS[border]}): {why}")
    verdict.thirds = sum(_thirds(n) for n in news)
    verdict.signature = tuple(_rules_signature(n) for n in news)
    if verdict.hard:
        return verdict
    if fixed_size(after):
        return verdict   # форма не растягивается: пределы раскладки и поведение при других размерах окна не проверяются (`fixed_size`)
    changes = limits.unforgiven(limits.compare(before.doc, after, was=before.snap, now=snap))
    verdict.narrowed = {(c.axis, c.direction) for c in changes}
    verdict.narrow_px = _narrow_px(before.snap, snap, changes)
    verdict.frozen = _freezes(before.snap, snap, form, coef)
    penalty, notes, collisions = [0, 0, 0], [], []
    project = {i.index: tuple(i.box) for i in layout._all_items(form)}      # при проектном размере края — это `box`, раскладку считать не нужно
    for axis in axes:
        layouts = [(_window(snap, axis, value), project if value == snap.size[axis] else _layout_at(form, *_window(snap, axis, value)).ints)
                   for value in size_set(snap, axis)]
        _alignment(form, layouts, news, penalty, notes, ignore)
        collisions += _collisions(form, layouts, news)
    verdict.penalty = (penalty[0], penalty[1])
    verdict.worst = penalty[2]
    verdict.notes = notes
    verdict.hard += collisions[:SHOWN]
    return verdict


def _assess(before, after, names, ignore=(), **kw):
    """`assess`; `ignore` передаётся, только если он не пуст."""
    return assess(before, after, names, ignore=ignore, **kw) if ignore else assess(before, after, names, **kw)


# ── Кандидаты ─────────────────────────────────────────────────────────────────────────────────

def _column(form, item):
    """Элементы столбца нового: тот же тип, совпадают левый и правый край (а нет таких — левый)."""
    same = [o for o in _neighbours(form, item) if o.type == item.type]
    both = [o for o in same if abs(o.box[0] - item.box[0]) <= TOL and abs(o.box[2] - item.box[2]) <= TOL]
    return both or [o for o in same if abs(o.box[0] - item.box[0]) <= TOL]


def column_behaviour(form, coef, item, ignore=()):
    """Поведение по ширине, которое у большинства столбца нового элемента выше него (нет таких — всего столбца); при равенстве — у
    ближайшего по вертикали; нет столбца — `None`.
    """
    column = [o for o in _column(form, item) if o.qualified() not in ignore]
    column = [o for o in column if o.box[1] <= item.box[1]] or column
    counts = {}
    for o in column:
        c = coef.get(o.index)
        if c is not None:
            counts.setdefault(layout.horizontal_behaviour(c[2], c[3]), []).append(o)
    if not counts:
        return None
    best = max(len(g) for g in counts.values())
    top = [(abs(o.box[1] - item.box[1]), beh) for beh, g in counts.items() if len(g) == best for o in g]
    return min(top)[1]


def named_broken(excluded, name, axis):
    """Назван ли элемент `name` диагнозом поломок по оси `axis`: `excluded` — имена виновников (по любой оси) либо `{имя: оси}`."""
    if name not in excluded:
        return False
    return not isinstance(excluded, dict) or axis in excluded[name]


def _broken(o, excluded, skipped, axis):
    """Элемент `o` назван диагнозом по оси `axis` (`excluded` — виновники): копия его правил не предлагается; причину записывает в `skipped` (если он есть)."""
    if not named_broken(excluded, o.qualified(), axis):
        return False
    if skipped is not None:
        skipped.append(f"копия у «{o.label()}» не предлагается: сам образец назван диагнозом поломок привязок (`anchors-check`)")
    return True


def h_candidates(form, coef, item, excluded=(), skipped=None):
    """Кандидаты привязки по горизонтали `[(слова, значение h)]` после первого (первый — привязки как поставлены). Копия правил у образца из
    `excluded` (виновники диагноза поломок) не предлагается; слова об этом — в списке `skipped`."""
    out, seen = [], set()
    column = [o for o in _column(form, item) if not _broken(o, excluded, skipped, 0)]
    by_behaviour = {}
    for o in column:
        c = coef.get(o.index)
        if c is not None:
            by_behaviour.setdefault(layout.horizontal_behaviour(c[2], c[3]), []).append(o)
    for beh, group in by_behaviour.items():
        near = min(group, key=lambda o: abs(o.box[1] - item.box[1]))
        out.append((f"как у «{near.label()}» (столбец, {beh})", {"as": near.name}))
        seen.add(near.index)
    row = [o for o in _neighbours(form, item) if o.type == item.type and o.index not in seen
           and abs(o.box[0] - item.box[0]) > TOL and abs(o.box[1] - item.box[1]) <= patterns.ROW_DY and not _broken(o, excluded, skipped, 0)]
    for o in sorted(row, key=lambda o: abs(o.box[0] - item.box[0]))[:2]:
        out.append((f"как у «{o.label()}» (та же строка, другой столбец)", {"as": o.name}))
    label = _label_of(_neighbours(form, item), item) if item.type == "TextBox" else None
    if label is not None and label.name:
        out.append((f"за надписью «{label.label()}», размер прежний", {"after": label.name}))
        out.append((f"за надписью «{label.label()}», правый край к краю родителя", {"after": label.name, "role": "stretch"}))
    for role in STRETCHY_ROLES_H:
        out.append((f"роль {role}", role))
    return [c for c in out if c[1] is not None]


def v_candidates(form, coef, item, excluded=(), skipped=None):
    """Кандидаты привязки по вертикали; `excluded` и `skipped` — как у `h_candidates`."""
    out = []
    near = _neighbours(form, item)
    mates = [o for o in near if o.name and abs(o.box[1] - item.box[1]) <= patterns.ROW_DY and abs(o.box[0] - item.box[0]) > TOL
             and o.type not in NOT_ALIGNED and not _broken(o, excluded, skipped, 1)]
    label = _label_of(near, item) if item.type == "TextBox" else None
    if label is not None and label.name and not _broken(label, excluded, skipped, 1):
        out.append((f"как у надписи «{label.label()}» (своя пара)", {"as": label.name}))
    for o in sorted(mates, key=lambda o: abs(o.box[0] - item.box[0]))[:2]:
        if label is None or o is not label:
            out.append((f"как у «{o.label()}» (та же строка)", {"as": o.name}))
    for role in ROLES_V:
        out.append((f"роль {role}", role))
    return out


# ── Выбор ─────────────────────────────────────────────────────────────────────────────────────

def _set(doc, name, axis, spec, unverified):
    from .. import anchors
    anchors.set_anchors(doc, name, unverified=unverified, **{axis: spec})


class _Trial:
    """Кандидат: `hard` — причины отказа (без прощённых), `blocked` — слова, если поведение полю не подходит, `extra` — сужения сверх общих
    для всех кандидатов, `why` — почему не взят (заполняется выбором)."""
    __slots__ = ("words", "spec", "doc", "verdict", "why", "hard", "blocked", "extra", "copy_of")

    def __init__(self, words, spec, doc, verdict, copy_of=()):
        self.words, self.spec, self.doc, self.verdict = words, spec, doc, verdict
        self.why, self.hard, self.blocked, self.extra = None, [], None, set()
        self.copy_of = tuple(copy_of)       # элементы, названные диагнозом поломок, у которых скопированы правила этого кандидата


def _rank(trial, majority, order):
    v = trial.verdict
    return (len(v.hard), 1 if trial.copy_of else 0, v.penalty, 0 if majority is None or v.behaviour == majority else 1, v.thirds, order)


def _settled(verdict, majority):
    """Кандидат, лучше которого по главным признакам не бывает: нет отказа, сужения, разрыва и расхождения выравнивания, поведение как у
    большинства столбца. Перебор на нём останавливается (остальные варианты выиграли бы только числом правил к третьим элементам)."""
    return (not verdict.hard and not verdict.narrowed and not verdict.breaking and verdict.penalty == (0, 0)
            and (majority is None or verdict.behaviour == majority))


def _structure(item, axis):
    """Строение правил границ оси элемента без смещений: `((объект или «self», сторона), …)` по границам оси."""
    borders = (2, 3) if axis == 0 else (0, 1)
    return tuple(tuple(None if r is None else ("self" if r.obj == item.index else r.obj, r.side) for r in item.rules[b]) for b in borders)


def copied_from(form, item, broken, axis, sample):
    """Образец оси `axis`, названный диагнозом поломок: `sample` — запись самой операции (`{ось: имя образца}`; у `add_element` — тот, у кого
    скопированы привязки), `broken` — виновники диагноза. Нет записи — образец не называется. Возвращает `(имя,)` либо `()`."""
    if not broken or not sample or sample.get(axis) is None:
        return ()
    return tuple(o.label() for o in _neighbours(form, item) if o.label() == sample[axis] and named_broken(broken, o.qualified(), axis))


def _search(before, doc, name, axis, specs, unverified, allowed, base, base_words="привязки как поставлены (копия у образца)", majority=None, copy_of=(),
            ignore=()):
    """Перебор кандидатов одной оси над `doc`: список `_Trial` (первый — привязки как поставлены, `base` — их проверка). Перебор останавливается
    на первом кандидате, лучше которого по главным признакам не бывает (`_settled`); остальные варианты не проверяются."""
    trials = [_Trial(base_words, None, doc, base, copy_of)]
    seen = {base.signature}
    for words, spec in specs:
        work = fast_copy(doc)
        try:
            _set(work, name, "h" if axis == 0 else "v", spec, unverified)
        except EditError:
            continue
        verdict = _assess(before, work, [name], axes=(axis,), ignore=ignore)
        if verdict is None or verdict.signature in seen:
            continue
        seen.add(verdict.signature)
        trial = _Trial(words, spec, work, verdict)
        if axis == 0 and allowed is not None and verdict.behaviour not in allowed:
            trial.blocked = (f"при растяжении окна поле по ширине {layout.behaviour_words(verdict.behaviour)}, "
                             "а полю такого вида это не подходит")
        trials.append(trial)
        if not trial.blocked and _settled(verdict, majority):
            break
    excused = set(base.hard)  # причины, которые есть и у привязок как поставлены: их вызывает другая ось, кандидату этой оси они в вину не ставятся
    for t in trials:
        t.hard = [h for h in t.verdict.hard if t.spec is None or h not in excused]
    live = [t for t in trials if not t.hard and not t.blocked]
    inherent = set.intersection(*(t.verdict.narrowed for t in live)) if live else set()
    for t in live:
        t.extra = t.verdict.narrowed - inherent
    # Новый предел роста ближе `layout.EARLY` px (форма почти перестаёт расти) отвергает кандидата всегда: наименьшее сужение (`_pick`) выбирают
    # только среди кандидатов без него. Предел, общий для всех кандидатов оси (его вызывает другая ось), в вину кандидату не ставится.
    shared = set.intersection(*(t.verdict.frozen for t in live)) if live else set()
    for t in live:
        if t.verdict.frozen - shared:
            axes = " и ".join(layout.AXES[a] for a in sorted(t.verdict.frozen - shared))
            t.blocked = f"после правки у формы появляется предел роста ({axes}) ближе {layout.EARLY} px: форма почти перестаёт растягиваться"
    return trials


def _narrow_words(verdict):
    parts = [f"{layout.AXES[a]}, {'сжатие' if d < 0 else 'рост'} " + ("— предела не было" if px >= NO_LIMIT else f"на {px} px")
             for (a, d), px in sorted(verdict.narrow_px.items())]
    return "; ".join(parts)


def _pick(trials, majority):
    """Лучший кандидат и способ выбора: `(trial, how)`. `how`: `clean` — есть кандидат без сужения сверх общего и без разрыва выравнивания;
    `narrow` — такого нет, взят не ломающий выравнивание с наименьшим сужением; `break` — все ломают, взят ломающий меньше всего. `(None, None)` —
    все кандидаты с отказом."""
    live = [t for t in trials if not t.hard and not t.blocked]
    order = {id(t): i for i, t in enumerate(trials)}
    good = [t for t in live if not t.extra and not t.verdict.breaking]
    if good:
        return min(good, key=lambda t: _rank(t, majority, order[id(t)])), "clean"
    whole = [t for t in live if not t.verdict.breaking]
    if whole:
        return min(whole, key=lambda t: (t.verdict.narrow_total, _rank(t, majority, order[id(t)]))), "narrow"
    if live:
        return min(live, key=lambda t: (t.verdict.worst, t.verdict.narrow_total, _rank(t, majority, order[id(t)]))), "break"
    return None, None


def _why(trial, best, how):
    v = trial.verdict
    if trial.hard:
        return trial.hard[0]
    if trial.blocked:
        return trial.blocked
    if trial.copy_of and best is not trial:
        return f"копия у «{trial.copy_of[0]}» не берётся: образец назван диагнозом поломок привязок (`anchors-check`)"
    if trial.extra and how == "clean":
        axis, direction = sorted(trial.extra)[0]
        return f"сужает предел раскладки ({layout.AXES[axis]}, {'сжатие' if direction < 0 else 'рост'}), а другие варианты не сужают"
    if v.breaking:
        return f"разводит элемент с соседом на {v.worst} px при растяжении окна (граница {ALIGN_BREAK} px)"
    if trial.extra:
        return "сужает предел раскладки сильнее выбранного варианта"
    return None


def refine(before, doc, name, unverified=False, allowed=None, moved=False, sample=None):
    """Выбрать привязки элемента `name` (он уже стоит в `doc`, привязки — как поставила операция; `before` — форма до операции).

    Если нужна другая привязка, она записывается в `doc` операцией `set_anchors`. Возвращает слова для отчёта либо `None`, если
    раскладка форму не читает. Отказ (`EditError`) — у всех вариантов отказ модели (наезд, цикл, мёртвое правило); `doc` при этом не
    тронут. Сужение предела отказом не бывает: если без сужения варианта нет, берётся вариант с наименьшим сужением, и отчёт его называет.
    `allowed` — поведения по ширине, допустимые полю (поле даты не растягивается), `None` — любые; `moved` — элемент перенесён, а не
    новый (слова отчёта); `sample` — `{ось: имя образца}`, у кого операция скопировала привязки (`place.Place.sample`): образец, названный диагнозом
    поломок, не берётся, а выравнивание с ним не считается.
    """
    before = before if isinstance(before, Before) else Before(before)
    form = layout.read(doc)
    coef = layout.coefficients(form, hide=False)
    broken = set() if moved else before.broken()
    copied = [copied_from(form, _find(form, name), broken, axis, sample) for axis in (0, 1)]
    ignore = {o.qualified() for o in _neighbours(form, _find(form, name)) if o.label() in {c for pair in copied for c in pair}}
    first = _assess(before, doc, [name], ignore=ignore)
    if first is None:
        return None
    if fixed_size(doc) and not first.hard:
        return ("форма не растягивается («Изменять размер» снято): растяжение окна не проверялось, перебор привязок не нужен; "
                "привязки оставлены как поставлены, правила и цепочки проверены на модели раскладки")
    majority = column_behaviour(form, coef, _find(form, name), ignore)
    if first.clean and (majority is None or first.behaviour == majority) and not any(copied):
        return ("привязки проверены на модели раскладки при размерах окна меньше и больше проектного: выравнивание с соседями и пределы "
                "сохраняются" + ("" if majority is None else f"; при растяжении окна поле по ширине {layout.behaviour_words(first.behaviour)} — как у большинства столбца"))
    base_words = "привязки после переноса" if moved else "привязки как поставлены (копия у образца)"
    said, chosen, work = [], {}, doc
    for axis in (0, 1):
        form = layout.read(work)
        coef = layout.coefficients(form, hide=False)
        item = _find(form, name)
        majority = column_behaviour(form, coef, item, ignore) if axis == 0 else None
        skipped = []
        specs = h_candidates(form, coef, item, before.broken(), skipped) if axis == 0 else v_candidates(form, coef, item, before.broken(), skipped)
        base = _assess(before, work, [name], axes=(axis,), ignore=ignore)
        trials = _search(before, work, name, axis, specs, unverified, allowed, base, base_words, majority, copied[axis], ignore)
        axis_word = "горизонталь" if axis == 0 else "вертикаль"
        best, how = _pick(trials, majority)
        if best is None:
            what = "элемента" if moved else "нового элемента"
            raise EditError(f"привязки {what} «{name}», {axis_word}: у всех {len(trials)} вариантов отказ модели раскладки — "
                            f"{'; '.join(f'{t.words}: {t.hard[0] if t.hard else t.blocked}' for t in trials)}. Выходы: явная привязка (`anchor`, `{{\"as\": "
                            "\"<имя>\"}}` у образца, который ведёт себя как нужно); либо `relayout`")
        for t in trials:
            t.why = None if t is best else _why(t, best, how)
        rejected = [f"{t.words} — {t.why}" for t in trials if t.why is not None]
        cut = "; отброшены: " + "; ".join(rejected[:SHOWN]) + (" …" if len(rejected) > SHOWN else "") if rejected else ""
        if best.spec is None:
            said.append(f"{axis_word}: {base_words} проверены на модели{cut}")
            if best.copy_of:
                said[-1] += (f"; привязки скопированы у «{best.copy_of[0]}», названного диагнозом поломок привязок (`anchors-check`): "
                             "другого варианта нет")
        else:
            chosen["h" if axis == 0 else "v"] = best.spec
            work = best.doc
            said.append(f"{axis_word}: выбран вариант «{best.words}»{cut or '; прочие варианты не лучше'}")
        v = best.verdict
        if how != "clean":
            breaking = [t for t in trials if t.verdict.breaking and not t.hard and not t.blocked]
            if how == "narrow" and breaking:
                said[-1] += (f"; правка сужает растяжение формы ({_narrow_words(v)}): другие варианты разводят элемент с соседом на "
                             f"{min(t.verdict.worst for t in breaking)} px и больше")
            else:
                said[-1] += f"; все варианты сужают растяжение формы или ломают выравнивание, взят наименьший ущерб: {_narrow_words(v) or 'без сужения'}"
                if v.breaking:
                    said[-1] += f"; элемент расходится с соседом на {v.worst} px"
        elif v.narrow_px:
            said[-1] += f"; остаётся сужение предела раскладки ({_narrow_words(v)}): оно есть у всех вариантов"
        if skipped and not copied[axis]:
            said[-1] += "; " + "; ".join(dict.fromkeys(skipped))
        if best.verdict.hard:
            said[-1] += f"; остаётся: {'; '.join(best.verdict.hard[:SHOWN])}"
        if v.notes:
            said[-1] += f"; остаётся: {'; '.join(v.notes[:SHOWN])}"
    for key, spec in chosen.items():
        _set(doc, name, key, spec, unverified)
    return "привязки выбраны перебором на модели раскладки: " + "; ".join(said)


def warn(before, doc, name):
    """Проверка явно названных привязок: слова предупреждения либо пусто (наезды, цикл, мёртвые правила, расхождение выравнивания)."""
    verdict = assess(before, doc, [name])
    if verdict is None:
        return ""
    found = verdict.hard + verdict.notes
    return ("предупреждение: привязки названы явно и проверены на модели раскладки — " + "; ".join(found[:SHOWN * 2])) if found else ""
