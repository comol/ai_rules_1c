"""Коэффициенты роста границ (`Cycle`, `coefficients`), поведение по осям и края элемента по правилам (`rule_box`)."""
from .model import HOLDER_SIDE, DEAD, BOX_TOLERANCE, _EDGE
from .rules import rule_state, _live, _all_items


# ── Коэффициенты: сколько пикселей проходит граница на пиксель роста родителя ──

class Cycle(Exception):
    pass


def coefficients(form, hide=True, shown=None):
    """`{индекс: (cT, cB, cL, cR)}`; `None` у элемента в цикле правил.

    Граница без правила или с мёртвым первым правилом не сдвигается (0). Живое первое правило: граница идёт со стороной объекта
    (у родителя начало 0, дальний край 1, центр ½; у элемента — коэффициент его стороны). Живое второе — доля между якорями,
    `c1 + k·(c2 − c1)`. Элементы скрытой страницы панели — `None`; с `hide=False` они считаются как показанные.
    """
    memo, busy = {}, set()

    def side_coef(target, side):
        if side in (0, 1, 2, 3):
            return border(target, side)
        if side == 4:
            return (border(target, 0) + border(target, 1)) / 2
        if side == 5:
            return (border(target, 2) + border(target, 3)) / 2
        return 0.0

    def rule_coef(item, rule):
        if rule.obj == 0:
            return HOLDER_SIDE.get(rule.side, 0.0)
        target = form.items.get(rule.obj)
        if target is None or target.holder != item.holder:
            return 0.0  # сырой сосед или чужой родитель: `rule_state` это назвал
        return side_coef(target, rule.side)

    def live(item, b, rule):
        return rule is not None and rule_state(form, item, b, rule)[0] != DEAD

    def border(item, b):
        key = (item.index, b)
        if key in memo:
            return memo[key]
        if key in busy:
            raise Cycle(key)
        busy.add(key)
        r1, r2 = item.rules[b]
        if not live(item, b, r1):
            value = 0.0
        else:
            c1 = rule_coef(item, r1)
            if live(item, b, r2) and r1.off != r2.off:
                c2 = rule_coef(item, r2)
                value = c1 + r1.off / (r1.off - r2.off) * (c2 - c1)
            else:
                value = c1
        busy.discard(key)
        memo[key] = value
        return value

    out = {}
    for item in _all_items(form):
        if hide and hidden_page(item, shown):
            out[item.index] = None
            continue
        try:
            out[item.index] = tuple(border(item, b) for b in range(4))
        except Cycle:
            out[item.index] = None
    return out


GROW_MIN = 0.9  # рост ширины поля при растяжении окна, с которого поле «растягивается» (`docs/generate.md`)
MOVE_MAX = 0.1  # рост ширины не больше этого — ширина «постоянна»: элемент остаётся на месте (обе границы на месте) либо сдвигается (обе идут с краем формы)
GROWS, STANDS, MOVES, PARTLY = "grows", "stands", "moves", "partly"  # внутренние названия поведения; слова для вывода — в `BEHAVIOUR_WORDS`

# Единственный словарь поведения при растяжении окна: все команды (`layout`, `render --sizes`, отчёты правки и исправления
# привязок, линтер) берут слова отсюда; у `MOVES` слова зависят от оси: вправо у ширины, вниз у высоты.
BEHAVIOUR_WORDS = {
    # название: (об одном элементе, перечнем «…: имена», в легенде рисунка, краткое — в паре «было → стало»)
    GROWS: ("растягивается вместе с окном", "растягиваются", "растягивается вместе с окном", "растягивается"),
    STANDS: ("остаётся на месте", "остаются на месте", "остаётся на месте", "остаётся на месте"),
    PARTLY: ("растягивается или сдвигается на долю роста окна (пропорционально)", "пропорционально росту окна",
             "растягивается или сдвигается на долю роста окна", "меняется пропорционально росту окна"),
}
MOVES_WORDS = ("сдвигается вправо вместе с правым краем окна", "сдвигаются вправо", "сдвигается вправо вместе с правым краем окна",
               "сдвигается вправо"), ("сдвигается вниз вместе с нижним краем окна", "сдвигаются вниз",
                                      "сдвигается вниз вместе с нижним краем окна", "сдвигается вниз")
DEAD_RULE_WORDS = "без встречной записи: в предприятии не действует, граница остаётся на месте"  # пояснение к «мёртвому правилу»
DEAD_RULES_WORDS = "без встречной записи: в предприятии не действуют, границы остаются на месте"  # то же о нескольких
SENTENCE, LISTED, LEGEND, BRIEF = range(4)  # номер формы слова в `BEHAVIOUR_WORDS`


def behaviour_words(behaviour, axis=0, form=SENTENCE):
    """Слова о поведении `behaviour` (`GROWS`, `STANDS`, `MOVES`, `PARTLY`) по оси `axis` (0 — ширина, 1 — высота) в форме `form`:
    `SENTENCE` — о нём самом («остаётся на месте»), `LISTED` — подпись перечня («остаются на месте»), `LEGEND` — подпись значка,
    `BRIEF` — краткая, для пары «было → стало». Поведение `None` (цикл правил) — «не вычисляется».
    """
    if behaviour is None:
        return "не вычисляется"
    return (MOVES_WORDS[axis] if behaviour == MOVES else BEHAVIOUR_WORDS[behaviour])[form]


def horizontal_behaviour(left, right):
    """Поведение поля по горизонтали при растяжении окна по коэффициентам границ: `GROWS` — рост ширины не меньше `GROW_MIN`;
    `STANDS` — обе границы остаются на месте; `MOVES` — ширина почти постоянна (рост не больше `MOVE_MAX`), а границы идут с краем
    формы; `PARTLY` — между ними. Цикл правил — `None`.
    """
    if left is None or right is None:
        return None
    growth = right - left
    if growth >= GROW_MIN:
        return GROWS
    if growth <= MOVE_MAX:
        return STANDS if left == 0 and right == 0 else MOVES
    return PARTLY


def vertical_behaviour(top, bottom):
    """Поведение элемента по вертикали — двойник `horizontal_behaviour`. Порог подобран по горизонтали, по вертикали отдельно не проверялся."""
    return horizontal_behaviour(top, bottom)

def rule_box(form, item, edge, memo=None):
    """Края элемента `(x, y, x2, y2)` по его правилам при крае родителя `edge = (право, низ)`. Граница без правила или с мёртвым первым
    остаётся, где стоит в файле; сырой сосед, сосед другого родителя и цикл не сдвигают границу. Так предприятие ставит элемент у
    формы с видимыми закладками, и так же `problems` считает положение «по правилам».
    """
    memo = {} if memo is None else memo
    busy = set()

    def side_value(owner, rule):
        if rule.obj == 0:
            k = HOLDER_SIDE.get(rule.side, 0.0)
            return k * (edge[0] if rule.side in (2, 3, 5) else edge[1])
        target = form.items.get(rule.obj)
        if target is None or target.holder != owner.holder:
            return None
        if rule.side in (0, 1, 2, 3):
            return border(target, rule.side)
        pair = (0, 1) if rule.side == 4 else (2, 3)
        return (border(target, pair[0]) + border(target, pair[1])) / 2

    def border(target, b):
        key = (target.index, b)
        if key in memo:
            return memo[key]
        x0 = (target.stored or target.box)[_EDGE[b]]
        if key in busy:
            return x0
        busy.add(key)
        r1, r2 = target.rules[b]
        value = x0
        if _live(form, target, b, r1):
            a1 = side_value(target, r1)
            if a1 is not None:
                value = a1 + r1.off
                if _live(form, target, b, r2) and r1.off != r2.off:
                    a2 = side_value(target, r2)
                    if a2 is not None:
                        value = a1 + r1.off / (r1.off - r2.off) * (a2 - a1)
        busy.discard(key)
        value = round(value, 6)
        memo[key] = value
        return value

    top, bottom, left, right = (border(item, b) for b in range(4))
    return (left, top, right, bottom)


def _page_by_rules(form, shown):
    """Положение показанной страницы ≥ 1 формы «Сверху» по правилам от области страниц: `[(элемент, прежний box)]`; после расчёта `box`
    нужно вернуть. Предприятие `box` таких элементов не читает. Страница, не названная в `shown`, стоит по `box`, как скрытая.
    """
    if not shown or form.tabs_area is None or not isinstance(shown.get(0), int) or shown[0] < 1:
        return []
    memo, fresh = {}, []
    for item in form.holders[0].children:
        if item.page == shown[0] and not item.raw:
            fresh.append((item, rule_box(form, item, form.tabs_area, memo)))
    swapped = [(item, item.box) for item, _box in fresh]
    for item, box in fresh:
        item.box = box
    return swapped


def _pages_by_rules_all(form):
    """Положение всех страниц ≥ 1 формы «Сверху» по правилам от области страниц, как `_page_by_rules`. Нужна прошлой раскладке
    (`stale`): страница ≥ 1 раскладывается только при показе, а скрытая стоит там, где её оставил показ.
    """
    if form.tabs_area is None:
        return []
    memo, fresh = {}, []
    for item in form.holders[0].children:
        if item.page not in (None, 0) and not item.raw:
            fresh.append((item, rule_box(form, item, form.tabs_area, memo)))
    swapped = [(item, item.box) for item, _box in fresh]
    for item, box in fresh:
        item.box = box
    return swapped


def shown_page_diverged(form, shown):
    """Элементы показанной страницы ≥ 1 формы «Сверху», чей `box` разошёлся с положением по правилам: `[(элемент, по box, по
    правилам)]`. `relayout` пишет в файл по `box`, и показ записанной формы равен показу исходной.
    """
    if not shown or form.tabs_area is None or not isinstance(shown.get(0), int) or shown[0] < 1:
        return []
    memo, out = {}, []
    for item in form.holders[0].children:
        if item.page == shown[0] and not item.raw:
            want = rule_box(form, item, form.tabs_area, memo)
            if any(abs(a - b) > BOX_TOLERANCE for a, b in zip(item.box, want)):
                out.append((item, item.box, want))
    return out


def hidden_page(item, shown=None):
    """Элемент страницы панели, кроме первой: при смене размера страница не показана, и предприятие её не перекладывает. Какая
    страница показана, файл не говорит: считается первая, пока `shown` не назовёт другую. Страницы формы — так же, но только у
    формы с закладками «Сверху» (`Form.tabs_area`) и «Не отображать» (`Form.pages_off`); у прочих форм не проверялось.
    """
    if not item.lazy:
        return False
    if shown is not None and item.holder in shown:
        return item.page not in (None, shown[item.holder])
    return item.page not in (0, None)


# ── Пределы ──

AREA_MIN = "минимум от области"  # `Limit.note` у «минимума» элемента, чей размер по правилам от области панели в проекте ниже минимума
