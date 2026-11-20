"""Пределы раскладки: `Limit`, `holder_limits`, `bounds` — размер, при котором раскладка перестаёт меняться."""
import math

from .model import (CENTER_SIDES, MARGIN, COLLISION_SLACK, BUTTON_MIN_BY_CAPTION,
    BUTTON_ABOVE_PROJECT, MIN_WHERE_BUTTON_HEIGHT, MIN_WHERE, PANEL_WHERE,
    MIN_SLACK, NEAR_MEASURED, NEAR_CENTER_MEASURED, SHARE_OBSERVED,
    FROZEN_BELOW_MIN, EPS, min_size, caption_measured,
    _panel_tabs, _num)
from .coeffs import STANDS, behaviour_words, AREA_MIN


class Limit:
    """Предел раскладки родителя по оси и направлению: рост `d` и что его ограничивает.

    `kind`: «столкновение» (`a` наезжает на `b`), «край» (`a` подошёл к краю ближе отступа), «минимум» (`a` сжался до минимума
    типа, а у типа без числа до нуля). `whole` — целый рост в пикселях. `edge` у края — «far» (правый или нижний) или «near»
    (левая или верхняя граница элемента, идущего с дальним краем, не уходит за 0 родителя). У «far» `share` — доля роста окна,
    с которой идёт граница, если она меньше 1.
    """
    __slots__ = ("axis", "direction", "d", "whole", "kind", "a", "b", "note", "edge", "share", "measured", "center")

    def __init__(self, axis, direction, d, kind, a, b=None, note=None, edge=None, share=None, measured=True, center=False):
        self.axis, self.direction, self.d, self.kind = axis, direction, d, kind
        self.a, self.b, self.note, self.edge, self.share = a, b, note, edge, share
        self.measured = measured  # у ближнего предела: проверен ли он именно для этого типа, родителя и оси
        self.center = center  # у ближнего предела: граница идёт к центру родителя, а не с дальним краем
        self.whole = math.floor(d + EPS) if direction > 0 else math.ceil(d - EPS)

    def words(self, form, coef):
        a = _named(self.a, coef, self.axis)
        if self.kind == "столкновение":
            b = _named(self.b, coef, self.axis)
            return f"{a} доходит до {b}"
        if self.kind == "край" and self.edge == "near":
            side = "левого" if self.axis == 0 else "верхнего"
            who = "" if self.measured else (
                f"; проверено у кнопки, поля ввода и надписи на форме по ширине (привязка к дальнему краю), у центра — у одной надписи; "
                f"у типа «{self.a.type}» / по {'высоте' if self.axis else 'ширине'} / внутри панели — по аналогии, не проверялось"
                + ("; в панели содержимое при сужении прокручивается с полосой, а не срезается" if self.a.holder else ""))
            how = ("граница идёт к центру родителя, и у неё ближний предел тоже действует (Лево 0, а не −20; "
                   "раскладка встаёт на проект минус удвоенный проектный отступ) — ") if self.center else ""
            return (f"{a} доходит до {side} края родителя — {how}ближний предел 0: раскладка встаёт там, где "
                    f"{'Лево' if self.axis == 0 else 'Верх'} элемента 0, окно сужается дальше, срезая её справа "
                    f"(снизу) без полос{who}")
        if self.kind == "край":
            if not self.note:
                # «Ближе 0 px» смысла не имеет: элемент уже на краю.
                return f"{a} стоит на самом краю родителя — сжатие сразу вывело бы его за край"
            tail = ""
            if self.edge == "far" and self.share and self.share >= SHARE_OBSERVED:
                tail = (f"; граница идёт долей ({self.share:.2f} роста окна): у такой доли раскладка иногда перестаёт меняться "
                        "на пределе, а иногда следует за окном дальше, и условие не выяснено; расчёт держит предел всегда, "
                        "и форма, которая шла прыжком или была открыта ниже предела, с ним расходится")
            elif self.edge == "far" and self.share:
                tail = (f"; граница идёт долей ({self.share:.2f} роста окна): у такой доли остановка раскладки не проверялась "
                        "(проверена доля около 0,99), расчёт держит предел")
            return f"{a} подходит к краю родителя ближе {self.note} px{tail}"
        axis_word = "ширина" if self.axis == 0 else "высота"
        least = min_size(self.a)[self.axis]
        size0 = self.a.box[2 + self.axis] - self.a.box[self.axis]
        if least and size0 < least - MIN_SLACK and (self.a.type, self.axis) in FROZEN_BELOW_MIN and self.direction < 0:
            return (f"{a} уже в проекте меньше минимума ({axis_word} {size0} при {least}): раскладка по этой оси не сжимается "
                    "вовсе — стоит на проектном размере, а платформа элемент не чинит (проверено у одной таблицы по высоте; "
                    "у других типов сжатие из такого состояния не проверялось — до нуля); "
                    "так, пока таблица ни разу не достигала минимума; после того как раскладка хоть раз была выше проектной "
                    "и таблица достигла минимума, нижний предел — проектная высота плюс (минимум − проектная высота таблицы), например 303 = 300 + (49 − 46), "
                    "и модель этого не знает: она стоит на проектной высоте, расхождение названо поимённо)"
                    + ("; у формы с закладками «Сверху» платформа при этом поднимает таблицу до минимума, область страниц "
                       "H − 20 против раскладки H − 19, и у проектного размера есть полоса 16 по ширине — не проверялось"
                       if form.tabs_area is not None else ""))
        if self.note == AREA_MIN:
            return (f"{a} по правилам от области панели уже в проектном размере меньше минимума ({axis_word} {_num(size0)} при {least}), "
                    "хотя в файле не меньше: страница перестаёт сжиматься, когда он достиг минимума, и панель прокручивается")
        if least and size0 < least - MIN_SLACK:
            return (f"{a} уже в проекте меньше минимума ({axis_word} {size0} при {least}): платформа его не "
                    "чинит, и сжатие из такого состояния идёт до нуля (рост из него проверен; сжатие нет)")
        if least:
            where = (PANEL_WHERE.get(_panel_tabs(self.a)) if self.a.type == "Panel"
                     else MIN_WHERE.get(self.a.type))
            if self.a.type == "Button":
                if self.axis == 1:
                    where = MIN_WHERE_BUTTON_HEIGHT
                elif not caption_measured(self.a):
                    where += f"; у подписи «{self.a.caption or ''}» не проверялось — расчёт взял {least}"
                elif self.a.caption in BUTTON_ABOVE_PROJECT:
                    where += (f"; у этой подписи минимум {BUTTON_MIN_BY_CAPTION[self.a.caption]} выше проекта: кнопка, начавшая в проекте {least}, "
                              f"не сжимается совсем, а побывавшая шире сжимается до {BUTTON_MIN_BY_CAPTION[self.a.caption]} и стоит на нём, в том числе при "
                              "возврате к проектному размеру; расчёт даёт проектную ширину — "
                              "история «побывала шире минимума» в него не входит")
            return f"{a} сжимается до минимума ({axis_word} {least}{'; ' + where if where else ''})"
        return f"{a} сжимается до нуля ({axis_word}; минимум не проверялся)"


def min_unmeasured(lim):
    """Предел держится на минимуме, который не проверялся (сжатие «до нуля»): кадр на таком пределе — оценка модели, а не снимок предприятия."""
    if lim.kind != "минимум":
        return False
    least = min_size(lim.a)[lim.axis]
    size0 = lim.a.box[2 + lim.axis] - lim.a.box[lim.axis]
    if least and lim.direction < 0 and (lim.a.type, lim.axis) in FROZEN_BELOW_MIN and size0 < least - MIN_SLACK:
        return False  # таблица ниже минимума остаётся на проектном размере; слова это называют
    return not least or size0 < least - MIN_SLACK


def _named(item, coef, axis):
    """Имя элемента с пометкой «(остаётся на месте)» по оси предела."""
    moving = _moves(item, coef, axis)
    tail = "" if item.visible else ", невидимый"
    return f"«{item.label()}»" + (f" ({behaviour_words(STANDS)}" + tail + ")" if not moving else
                                  (f" ({tail[2:]})" if tail else ""))


def _span(item, coef, axis):
    """Края элемента по оси как линейные функции роста: `((начало, наклон), (конец, наклон))`."""
    x, y, x2, y2 = item.box
    c = coef[item.index]
    if axis == 0:
        return (x, c[2]), (x2, c[3])
    return (y, c[0]), (y2, c[1])


def _overlap_interval(p, q):
    """Интервал роста `(L, U)`, на котором отрезки сталкиваются (или `None`): пересечение больше допуска `COLLISION_SLACK`."""
    (a0, sa0), (a1, sa1) = p
    (b0, sb0), (b1, sb1) = q
    lo, hi = -math.inf, math.inf
    for base, slope in ((b1 - a0, sb1 - sa0), (a1 - b0, sa1 - sb0)):
        if abs(slope) < EPS:
            if base <= COLLISION_SLACK + EPS:
                return None
            continue
        root = (COLLISION_SLACK - base) / slope
        if slope > 0:
            lo = max(lo, root)
        else:
            hi = min(hi, root)
    return (lo, hi) if lo < hi - EPS else None


def holder_limits(form, holder, coef, other=(0.0, 0.0), inversion=True):
    """Пределы раскладки родителя: `{(ось, направление): [Limit, …]}` по возрастанию расстояния; первый действует. Направление +1 —
    рост, −1 — сжатие. Столкновение считается у пары детей одной страницы, чьи внутренности в проекте не пересекались; касание
    законно. `inversion=False` — без предела «минимум» и без ближнего предела 0 у типов, где он не проверялся. Пары ищутся
    обходом отрезков по началу (`_crossing`): на странице бывает до полутысячи элементов.
    """
    out = {(axis, direction): [] for axis in (0, 1) for direction in (1, -1)}
    kids = [item for item in holder.children if coef.get(item.index) is not None]
    by_page = {}
    for item in kids:
        by_page.setdefault(item.page, []).append(item)
    spans = {item.index: (_span(item, coef, 0), _span(item, coef, 1)) for item in kids}
    for page_items in by_page.values():
        rows = [spans[item.index] for item in page_items]
        for axis in (0, 1):
            cross = 1 - axis
            shifted = [((s[cross][0][0] + s[cross][0][1] * other[cross]),
                        (s[cross][1][0] + s[cross][1][1] * other[cross])) for s in rows]
            for i, j in _crossing(shifted):
                sa, sb = rows[i], rows[j]
                (a0, sa0), (a1, sa1) = sa[axis]
                (b0, sb0), (b1, sb1) = sb[axis]
                if abs(sb1 - sa0) < EPS and abs(sa1 - sb0) < EPS:
                    continue  # по оси идут вместе или стоят оба: сойтись нечем
                found = _overlap_interval(sa[axis], sb[axis])
                # Пересекались по оси уже в проекте (рамка группы вокруг полей): пределом такая пара не служит.
                if found is None:
                    continue
                a, b = page_items[i], page_items[j]
                lo, hi = found
                first, second = (a, b) if _moves(a, coef, axis) else (b, a)
                if lo >= -EPS:
                    out[(axis, 1)].append(Limit(axis, 1, lo, "столкновение", first, second))
                elif hi <= EPS:
                    out[(axis, -1)].append(Limit(axis, -1, hi, "столкновение", first, second))
    for item in kids:
        size = holder.edge(item.page)
        for axis in (0, 1):
            (s0, k0), (s1, k1) = spans[item.index][axis]
            full = size[axis]
            far = min(MARGIN, full - s1)
            # Дальний край: расстояние до края считается в целых пикселях. У отступа 0 предел «край» есть у обычного элемента
            # (элемент у правого края формы 700 шириной 80 держит раскладку на 700) и нет у панели команд формы — это различает тип.
            if k1 < 1 - EPS and (far > 0 or (far == 0 and item.type != "CommandBar")):
                steps = _steps_to_edge(item, axis, full, s1, k1, far)
                out[(axis, -1)].append(Limit(axis, -1, -(steps - 1), "край", item, note=far,
                                             edge="far", share=k1 if k1 > EPS else None))
            # Ближний предел 0: левая (верхняя) граница, целиком идущая с дальним краем (k0 = 1), не уходит за 0 родителя. Проверено у одной
            # надписи по ширине; у прочих типов, по высоте и внутри панели — по аналогии (`near_known`, `liftable`). У границы-доли, границы,
            # которая не идёт, и проекта за 0 предела нет.
            near_known = item.type in NEAR_MEASURED and holder.key == 0 and axis == 0
            if k0 >= 1 - EPS and s0 >= 0 and (inversion or near_known):
                out[(axis, -1)].append(Limit(axis, -1, -math.floor(s0 + 0.5), "край", item, note=0, edge="near",
                                             measured=near_known))
            # Граница к центру родителя (k0 = ½) тоже имеет предел: `Лево` 60 на окне 540 стоит на 0, а не на −20. У доли предела нет.
            elif abs(k0 - 0.5) < EPS and s0 >= 0 and _center_border(item, axis) and (
                    (holder.key == 0 and inversion) or (item.type in NEAR_CENTER_MEASURED and axis == 0)):
                out[(axis, -1)].append(Limit(axis, -1, -math.floor(s0 / k0 + 0.5), "край", item, note=0, edge="near",
                                             measured=item.type in NEAR_CENTER_MEASURED and axis == 0,
                                             center=True))
            if inversion and abs(k1 - k0) > EPS:
                least = min_size(item)[axis]
                size0 = s1 - s0
                # Проект меньше минимума: платформа его не чинит, а сжатие из такого состояния не проверялось — остаётся предел «до нуля».
                direction = 1 if k1 < k0 else -1
                threshold = least - MIN_SLACK if least and size0 >= least - MIN_SLACK else 0.0
                stored = item.stored or item.box
                lifted = bool(item.from_area and least and size0 < least - MIN_SLACK and stored[2 + axis] - stored[axis] >= least - MIN_SLACK)
                if lifted:
                    # Размер по правилам от области панели в проектном размере бывает ниже минимума, хотя в файле он не меньше (`Размеры` −39
                    # при минимуме 11): это не проект, который платформа не чинит, а расчёт; страница перестаёт сжиматься, когда элемент
                    # дошёл до минимума. Элемент, который меньше минимума уже в файле, остаётся «до нуля».
                    threshold = least - MIN_SLACK
                # Таблица ниже минимума в проекте (46 при 49) при сжатии не сжимается: раскладка стоит на проектном размере. Проверено у одной
                # таблицы по высоте; у формы с закладками «Сверху» платформа поднимает её до минимума, правило там не сужено.
                if least and size0 < least - MIN_SLACK and (item.type, axis) in FROZEN_BELOW_MIN and direction < 0:
                    threshold = size0
                d = (threshold - size0) / (k1 - k0)
                out[(axis, direction)].append(Limit(axis, direction, d, "минимум", item, note=AREA_MIN if lifted else None))
    for found in out.values():
        # Действует ближайший к нулю. Исключение — «минимум» элемента, чей размер по правилам от области панели в проекте ниже минимума:
        # предел стоит за нулём (рост панели, с которого элемент дошёл до минимума), и страница не сжимается раньше него. Таких пределов
        # несколько — это нижние границы сжатия, и действует наибольший (`d` больше), а не ближайший к нулю.
        found.sort(key=lambda lim: (0, -lim.d) if lim.note == AREA_MIN and lim.direction < 0 and lim.d > 0 else (1, abs(lim.d)))
    return out


def _center_border(item, axis):
    """Левая (верхняя) граница элемента по оси идёт к центру родителя или соседа: хотя бы одно её правило смотрит в центр."""
    border = 2 if axis == 0 else 0
    return any(rule is not None and rule.side in CENTER_SIDES for rule in item.rules[border])


def _round_border(value, item, border):
    """Целая граница по дробной: `floor(v + ½)`, у границы с правилом к центру — `floor(v)`."""
    center = any(rule is not None and rule.side in CENTER_SIDES for rule in item.rules[border])
    return math.floor(value + EPS) if center else math.floor(value + 0.5 + EPS)


def _steps_to_edge(item, axis, full, s1, k1, need):
    """Первое сжатие родителя `m ≥ 1`, при котором дальний край элемента подходит к краю ближе `need`: целое расстояние
    `(full − m) − round(s1 − k1·m) < need`. Расстояние с ростом `m` не растёт, поэтому `m` ищется вилкой. Округление здесь прямое, а
    в `Layout._round` — по шагам от округлённого соседа; расхождение на 1 px бывает лишь у редких недействующих пределов.
    """
    border = 3 if axis == 0 else 1

    def near(m):
        return (full - m) - _round_border(s1 - k1 * m, item, border) < need

    hi = 1
    while not near(hi) and hi < 1 << 40:
        hi *= 2
    lo = hi // 2 + 1 if hi > 1 else 1
    while lo < hi:
        mid = (lo + hi) // 2
        if near(mid):
            hi = mid
        else:
            lo = mid + 1
    return lo


def _crossing(intervals):
    """Пары `(i, j)`, `i < j`, чьи открытые отрезки пересекаются (обходом по началу). Отрезок нулевой длины не пересекается ни с чем."""
    order = sorted(range(len(intervals)), key=lambda k: intervals[k][0])
    active, out = [], []
    for i in order:
        start, end = intervals[i]
        active = [j for j in active if intervals[j][1] - start > EPS]
        if end - start > EPS:
            out.extend((min(i, j), max(i, j)) for j in active)
            active.append(i)
    out.sort()
    return out


def _moves(item, coef, axis):
    c = coef.get(item.index)
    if c is None:
        return False
    pair = (c[2], c[3]) if axis == 0 else (c[0], c[1])
    return any(abs(v) > EPS for v in pair)


def bounds(limits):
    """`((lo_x, hi_x), (lo_y, hi_y))` целым ростом родителя; бесконечность — предела нет."""
    out = []
    for axis in (0, 1):
        up = limits[(axis, 1)]
        down = limits[(axis, -1)]
        out.append((down[0].whole if down else -math.inf, up[0].whole if up else math.inf))
    return tuple(out)
