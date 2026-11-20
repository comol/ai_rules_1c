"""Раскладка при заданном размере окна: `Layout`, `lay_out`, `paged_layout`, `form_range`, модельные края."""
import math

from .. import edit
from .model import ORDERS, HOLDER_SIDE, CENTER_SIDES, MIN_SLACK, SCROLL, SCROLL_REACH, EPS, min_size, BOX_TOLERANCE, _EDGE
from .rules import _live, _all_items
from .coeffs import coefficients, _page_by_rules, _pages_by_rules_all, hidden_page
from .limit_calc import holder_limits, _round_border, _moves, bounds
from .area import panel_collision


# ── Раскладка при размере ──

class Layout:
    """Раскладка формы при заданном размере клиентской области.

    `boxes` — `{индекс: (x, y, x2, y2)}` дробные края (вложенные — от своей панели), `ints` — целые, `growth` — `{родитель: (dW,
    dH)}` рост, по которому разложены дети, `asked` — рост, которого просили, `limits` и `frozen` — пределы и сработавшие пределы по
    родителям, `scroll` — сколько полоса прокрутки отняла у окна по ширине и высоте.

    Состояние, которого нет в файле: `order` (`wh` — ширина, потом высота; `hw` — наоборот); `at_open` — открытие в запомненном
    размере, а не переход; `shown` — `{родитель: показанная страница}`; `stale` — размер, при котором скрытые страницы
    перекладывались в последний раз.

    `inversion=False` — минимум типа не считается пределом (перераскладка под `unverified`): идущий по оси элемент, не меньший
    минимума в проекте, получает минимум своего типа или ноль и называется в `collapsed`; остающийся на месте и уже меньший минимума
    остаются как есть. `rules_pages=False` — показанная страница ≥ 1 формы «Сверху» стоит по `box` файла плюс сдвиг (раскладка для
    записи). `rules_all` — прошлая раскладка: страницы ≥ 1 стоят по правилам.
    """

    def __init__(self, form, width, height, inversion=True, hide=True, scroll=True, order="wh",
                 at_open=False, shown=None, stale=None, rules_pages=True, rules_all=False):
        if order not in ORDERS:
            raise edit.EditError(f"порядок осей {order!r}: допустимо «wh» (ширина, потом высота — как "
                                 "ставит пускач) и «hw» (высота, потом ширина)")
        self.form, self.width, self.height = form, width, height
        self.inversion, self.order, self.at_open = inversion, order, at_open
        self.shown, self.stale = shown, stale
        self.scroll = (0, 0)
        # Показанная страница ≥ 1 формы «Сверху» на время расчёта стоит по правилам от области `(W−2, H−20)`; с `rules_pages=False` — по `box` плюс сдвиг.
        swapped = _page_by_rules(form, shown) if rules_pages else []
        if rules_all and rules_pages:  # прошлая раскладка (`stale`): все страницы ≥ 1 стоят там, где их положил показ — по правилам
            swapped += _pages_by_rules_all(form)
        try:
            self.coef = coefficients(form, hide, shown)
            self._old = None
            if shown and stale and hide:
                self._old = Layout(form, *stale, inversion=inversion, hide=False, scroll=scroll, order=order, rules_all=True)
            self._solve(width, height)
            ew, eh = self.effective()
            cut = (SCROLL if eh > height and self.bar_appears(1) else 0, SCROLL if ew > width and self.bar_appears(0) else 0)
            if scroll and cut != (0, 0):
                self.scroll = cut
                self._solve(width - cut[0], height - cut[1])
        finally:
            for item, box in swapped:
                item.box = box

    def bar_appears(self, axis):
        """Даёт ли полосу прокрутки раскладка, вышедшая за окно по оси `axis` (0 — шире окна, 1 — выше; полоса отнимает 16 px по другой оси).

        Полосы нет, когда раскладку по оси держит минимум размера элемента, ближний предел 0 или столкновение с командной панелью
        формы (`panel_collision`) и ни один элемент верхнего уровня, кроме командных панелей, не вылез за окно (`SCROLL_REACH`).
        При пределе «край» или «столкновение» двух элементов содержимого и при вылезшем элементе полоса есть.

        Не проверялось: исключение всех `CommandBar` верхнего уровня, учёт элементов скрытых страниц. Не объяснены открытие в
        запомненном размере, «залипание» и переход, при котором модель даёт полосу, а предприятие нет.
        """
        held = []
        for ax, direction, lim in self.frozen.get(0, ()):
            if ax == axis:
                held += [other for other in self.limits[0].get((ax, direction), ()) if other.whole == lim.whole] or [lim]
        if not held or any(lim.kind != "минимум" and lim.edge != "near" and not panel_collision(lim) for lim in held):
            return True
        window = (self.width, self.height)[axis]
        for index, box in self.ints.items():
            item = self.form.items.get(index)
            if item is not None and item.holder == 0 and item.type != "CommandBar" and box[2 + axis] + SCROLL_REACH[axis] > window:
                return True
        return False

    def _solve(self, width, height):
        form = self.form
        self.boxes, self.ints, self.growth, self.asked, self.limits, self.frozen = \
            {}, {}, {}, {}, {}, {}
        self.collapsed = []
        self.clamped = []
        self._lay(form.holders[0], (width - form.width, height - form.height))

    def _limits(self, holder, asked):
        """Пределы родителя и рост по осям `(ограничения, (lo, hi) по осям, рост)`. Первая ось считается при проектном размере второй,
        вторая — при фактическом росте первой.
        """
        first = 0 if self.order == "wh" else 1
        second = 1 - first
        limits = holder_limits(self.form, holder, self.coef, inversion=self.inversion)
        at_open = self.at_open and holder.key == 0  # проверено у формы; вложенные панели держат как переход
        if at_open:
            limits = self._open_limits(limits)
        bnd = list(bounds(limits))
        grow = [0, 0]
        grow[first] = min(max(asked[first], bnd[first][0]), bnd[first][1])
        if grow[first]:
            other = [0.0, 0.0]
            other[first] = grow[first]
            again = holder_limits(self.form, holder, self.coef, other=tuple(other),
                                  inversion=self.inversion)
            if at_open:
                again = self._open_limits(again)
        else:
            again = limits
        bnd[second] = bounds(again)[second]
        grow[second] = min(max(asked[second], bnd[second][0]), bnd[second][1])
        limits = {**limits, (second, 1): again[(second, 1)], (second, -1): again[(second, -1)]}
        return limits, bnd, grow

    def _lifts(self, item, axis):
        """Поднимается ли элемент до минимума типа при записи вывернутого (`inversion=False`): только идущий по оси и не меньший
        `минимум − 0,5` в проекте.
        """
        c = self.coef.get(item.index)
        if c is None:
            return False
        lo, hi = (c[2], c[3]) if axis == 0 else (c[0], c[1])
        size = item.box[2 + axis] - item.box[axis]
        least = min_size(item)[axis]
        return abs(hi - lo) > EPS and size >= least - MIN_SLACK

    def _open_limits(self, limits):
        """Открытие в запомненном размере: предел «край» у элемента, остающегося на месте, держит смену размера, а не открытие."""
        return {key: [lim for lim in found
                      if not (lim.kind == "край" and not _moves(lim.a, self.coef, lim.axis))]
                for key, found in limits.items()}

    def _lay(self, holder, asked):
        limits, bnd, grow = self._limits(holder, asked)
        (lo_x, hi_x), (lo_y, hi_y) = bnd
        self.limits[holder.key] = limits
        self.asked[holder.key] = asked
        frozen = []
        for axis, (lo, hi) in enumerate(((lo_x, hi_x), (lo_y, hi_y))):
            if asked[axis] > hi:
                frozen.append((axis, 1, limits[(axis, 1)][0]))
            elif asked[axis] < lo:
                frozen.append((axis, -1, limits[(axis, -1)][0]))
        self.frozen[holder.key] = frozen
        self.growth[holder.key] = tuple(grow)
        for item in holder.children:
            c = self.coef.get(item.index)
            if c is None:
                self.boxes[item.index] = tuple(float(v) for v in item.box)
                continue
            x, y, x2, y2 = item.box
            box = [x + c[2] * grow[0], y + c[0] * grow[1],
                   x2 + c[3] * grow[0], y2 + c[1] * grow[1]]
            if not self.inversion:
                for axis, (lo, hi) in enumerate(((0, 2), (1, 3))):
                    least = min_size(item)[axis]
                    if self._lifts(item, axis) and box[hi] < box[lo] + least - EPS:
                        box[hi] = box[lo] + least
                        self.collapsed.append((item, axis))
                    elif not self._lifts(item, axis) and box[hi] < box[lo] - EPS and item.box[hi] >= item.box[lo]:
                        box[hi] = box[lo]  # размер не уходит ниже нуля
                        self.clamped.append((item, axis))
            self.boxes[item.index] = tuple(box)
        self._round(holder, grow)
        if self._old is not None:
            for item in holder.children:
                if hidden_page(item, self.shown):
                    self.boxes[item.index] = self._old.boxes[item.index]
                    self.ints[item.index] = self._old.ints[item.index]
        for item in holder.children:
            if item.index in self.form.holders:
                left, top, right, bottom = self.ints[item.index]
                sub = self.form.holders[item.index]
                w, h = sub.size
                self._lay(sub, ((right - left) - w, (bottom - top) - h))

    @staticmethod
    def _center_anchor(holder, items, item, b):
        """Где стоял якорь первого правила границы, если оно смотрит в центр, до перераскладки; иначе `None`."""
        rule = item.rules[b][0]
        if rule is None or rule.side not in CENTER_SIDES:
            return None
        if rule.obj == 0:
            axis = 1 if rule.side == 4 else 0
            return HOLDER_SIDE[rule.side] * holder.size[axis] + rule.off
        target = items.get(rule.obj)
        if target is None:
            return None
        pair = (1, 3) if rule.side == 4 else (0, 2)
        return sum(target.box[i] for i in pair) / 2 + rule.off

    def _round(self, holder, grow):
        """Целые края детей родителя по шагам: граница строится от округлённой стороны соседа, а не от дробной (вдоль цепочки
        `#16.r+8 → #17.r+8` это даёт у предприятия на 1 px иначе).
        """
        form, items = self.form, {c.index: c for c in holder.children}
        memo, busy = {}, set()

        def border(item, b):
            key = (item.index, b)
            if key in memo:
                return memo[key]
            x0 = item.box[_EDGE[b]]
            if self.coef.get(item.index) is None or key in busy:
                return x0 if isinstance(x0, int) else math.floor(x0 + 0.5 + EPS)
            busy.add(key)
            r1, r2 = item.rules[b]
            value = x0
            anchor = None
            if _live(form, item, b, r1):
                first = x0 + shift(item, r1)
                value = first
                if _live(form, item, b, r2) and r1.off != r2.off:
                    second = x0 + shift(item, r2)
                    value = first + r1.off / (r1.off - r2.off) * (second - first)
                elif isinstance(x0, int):
                    anchor = self._center_anchor(holder, items, item, b)
            busy.discard(key)
            if anchor is None:
                value = _round_border(value, item, b)
            else:
                value = x0 + math.floor(anchor + (value - x0) + EPS) - math.floor(anchor + EPS)
            if not self.inversion and b in (1, 3):
                start = border(item, b - 1 if b == 1 else 2)
                axis = 0 if b == 3 else 1
                project = item.box[2 + axis] - item.box[axis]
                if project >= 0:  # отрицательный уже в проекте — как есть (как `_lay` и проверка записи)
                    value = max(value, start + (min_size(item)[axis] if self._lifts(item, axis) else 0))
            memo[key] = value
            return value


        def shift(item, rule):
            """Сдвиг стороны, на которую смотрит правило (у центра — дробный, `½`)."""
            if rule.obj == 0:
                axis = 1 if rule.side in (0, 1, 4) else 0
                return HOLDER_SIDE.get(rule.side, 0.0) * grow[axis]
            target = items.get(rule.obj)
            if target is None or self.coef.get(target.index) is None:
                return 0
            if rule.side in (0, 1, 2, 3):
                return border(target, rule.side) - target.box[_EDGE[rule.side]]
            pair = (0, 1) if rule.side == 4 else (2, 3)
            now = sum(border(target, b) for b in pair)
            return (now - sum(target.box[_EDGE[b]] for b in pair)) / 2

        for item in holder.children:
            self.ints[item.index] = (border(item, 2), border(item, 0), border(item, 3),
                                     border(item, 1))

    def measured(self, item):
        """`(Лево, Верх, Ширина, Высота)` как их читает предприятие: целые края по шагам, ширина и высота — разность целых краёв."""
        left, top, right, bottom = self.ints[item.index]
        return left, top, right - left, bottom - top

    def edges(self, item):
        """Целые края для записи в файл — те же, что у `measured`."""
        return self.ints[item.index]

    def form_frozen(self):
        return self.frozen.get(0, [])

    def effective(self):
        """Размер, при котором предприятие разложит форму на самом деле (после остановки по пределу)."""
        dw, dh = self.growth[0]
        return self.form.width + dw, self.form.height + dh


def round_children(form, holder, coef, grow):
    """`{индекс: (x, y, x2, y2)}` — целые края детей родителя `holder`, когда он вырос на `grow = (dW, dH)`: те же шаги округления, что у раскладки формы
    (`Layout._round`), без расчёта пределов и без размера окна. Для правки размера панели (`edit.panelsize`)."""
    lay = Layout.__new__(Layout)
    lay.form, lay.coef, lay.ints, lay.inversion = form, coef, {}, True
    lay._round(holder, grow)
    return lay.ints


def lay_out(form, width, height):
    return Layout(form, width, height)


def _page_variants(form):
    """`{((родитель, страница), …): [элементы]}`: цепочка страниц от элемента до формы (страница 0 опускается)."""
    out = {}
    for item in _all_items(form):
        chain, at = {}, item
        while at is not None:
            if at.page not in (None, 0):
                chain[at.holder] = at.page
            at = form.holders[at.holder].item
        out.setdefault(tuple(sorted(chain.items())), []).append(item)
    return out


def paged_layout(form, width, height, **state):
    """Раскладка для записи: каждая страница раскладывается так, как раскладывается показанная (в записанной форме страница при показе
    должна встать так, как поставила бы её исходная форма). Возвращает `Layout` страницы 0, в котором элементы других страниц
    взяты из раскладки, где показана их страница. Пределы страниц в один предел панели не складываются.
    """
    variants = _page_variants(form)
    base = Layout(form, width, height, **state)
    base.coef = dict(base.coef)
    for chain, items in variants.items():
        if not chain:
            continue
        lay = Layout(form, width, height, shown=dict(chain), rules_pages=False, **state)
        for item in items:
            base.coef[item.index] = lay.coef[item.index]
            base.boxes[item.index] = lay.boxes[item.index]
            base.ints[item.index] = lay.ints[item.index]
        mine = {item.index for item in items}
        base.collapsed += [(item, axis) for item, axis in lay.collapsed if item.index in mine]
        base.clamped += [(item, axis) for item, axis in lay.clamped if item.index in mine]
        for key, found in lay.frozen.items():
            have = base.frozen.setdefault(key, [])
            for axis, direction, lim in found:
                if not any(axis == a and direction == d and lim.kind == other.kind and lim.a is other.a
                           and lim.b is other.b for a, d, other in have):
                    have.append((axis, direction, lim))
    return base


def model_boxes(form):
    """`{индекс: (x, y, x2, y2)}` — целые края по модели раскладки при размере формы из файла у элементов, чьё место на экране иное, чем в файле:
    у страницы шире панели и у закладок «Сверху» предприятие ставит элементы по правилам привязок, а не по `box` файла (`item.stored` — край в файле).
    Раскладка, которую не посчитать, — пусто. Результат запоминается на форме."""
    cached = getattr(form, "_model_boxes", None)
    if cached is None:
        cached = {}
        if any(item.stored is not None for item in form.items.values()):
            try:
                found = paged_layout(form, form.width, form.height).ints
            except (edit.EditError, KeyError, ValueError, ZeroDivisionError, RecursionError):
                found = {}
            for index, box in found.items():
                item = form.items.get(index)
                # Файл может совпасть с раскладкой, а `item.box` (правила от области) — нет: страница, которая из-за минимума вложенного стоит шире
                # области, записана по раскладке в проекте (`normalize_page_edges`), и на экране элемент стоит там же, где в файле.
                if item is not None and item.stored is not None and (tuple(box) != tuple(item.stored) or (
                        item.from_area and any(abs(a - b) > BOX_TOLERANCE for a, b in zip(box, item.box)))):
                    cached[index] = tuple(box)
        form._model_boxes = cached
    return cached


def apply_model_boxes(form):
    """Ставит у элементов, чьё место на экране иное, края по модели раскладки (`model_boxes`): `item.box` — на экране, `item.stored` — в файле.
    Повторный вызов ничего не меняет. Возвращает `{индекс: край в файле}`."""
    out = {}
    for index, box in model_boxes(form).items():
        item = form.items[index]
        out[index] = item.stored
        item.box = box
    return out


def form_range(form, coef=None, inversion=True):
    """Предел раскладки всей формы: `((min_w, max_w), (min_h, max_h), limits)` — размеры, между которыми раскладка следует за окном."""
    coef = coefficients(form) if coef is None else coef
    limits = holder_limits(form, form.holders[0], coef, inversion=inversion)
    (lo_x, hi_x), (lo_y, hi_y) = bounds(limits)

    def size(base, d):
        return None if math.isinf(d) else base + d

    return ((size(form.width, lo_x), size(form.width, hi_x)),
            (size(form.height, lo_y), size(form.height, hi_y)), limits)
