"""Пределы раскладки формы до и после правки.

Предел раскладки — размеры окна, между которыми форма следует за окном (`layout.form_range`): по каждой оси нижний (сжатие) и верхний
(рост); «без предела» — предела нет. Сравниваются не размеры, а запас относительно проектного размера формы: правка, поднявшая форму
на шаг, сдвигает оба размера на шаг и предела не меняет.

Предел сужается, когда появился предел, которого не было, или запас роста (сжатия) стал меньше. Расширение — обратное. Форма, которую
раскладка не читает, не сравнивается.
"""
from . import layout
from .edit.base import EditError

READ_ERRORS = (EditError, ValueError, KeyError, TypeError, IndexError, AttributeError, layout.Cycle)


class Snapshot:
    """Пределы одной формы: `size` — проектный `(ширина, высота)`, `room[(ось, направление)]` — запас в пикселях или `None` (предела нет),
    `ranges` — `((мин. ширина, макс. ширина), (мин. высота, макс. высота))`, `limits` — ограничивающие пары, `names` — имена элементов."""

    def __init__(self, form, coef):
        (w_lo, w_hi), (h_lo, h_hi), self.limits = layout.form_range(form, coef)
        self.form, self.coef = form, coef
        self.size = (form.width, form.height)
        self.ranges = ((w_lo, w_hi), (h_lo, h_hi))
        self.room = {}
        for axis in (0, 1):
            lo, hi = self.ranges[axis]
            self.room[(axis, -1)] = None if lo is None else lo - self.size[axis]
            self.room[(axis, 1)] = None if hi is None else hi - self.size[axis]
        self.names = {item.qualified() for item in layout._all_items(form)}


def snapshot(doc, shown=None):
    """Пределы формы `doc` (при `shown` — с показанными страницами панелей, как у `render --shown`) либо `None`, если раскладка её не читает."""
    try:
        form = layout.read(doc)
        return Snapshot(form, layout.coefficients(form, shown=shown))
    except READ_ERRORS:
        return None


def range_words(snap):
    """`ширина 433…без предела, высота 253…без предела`."""
    return ", ".join(f"{layout.AXES[axis]} {layout._size_words(*snap.ranges[axis])}" for axis in (0, 1))


def _worse(before, after, direction):
    """Запас после правки меньше прежнего (у сжатия запас — отрицательное число, и меньше он по модулю)."""
    if after is None:
        return False
    if before is None:
        return True
    return after < before if direction > 0 else after > before


def _cause(snap, was, axis, direction):
    lim = (snap.limits.get((axis, direction)) or [None])[0]
    if lim is None:
        return ""
    text = f"{lim.kind}: {lim.words(snap.form, snap.coef)}"
    fresh = [item.qualified() for item in (lim.a, lim.b) if item is not None and item.qualified() not in was.names]
    if fresh:
        text += "; новый элемент: " + ", ".join(f"«{name}»" for name in fresh)
    return text


def _forgivable(was, now, axis, direction, a, b):
    """Сужение — следствие ужатия таблицы: действующий предел высоты при сжатии — минимум таблицы, которая после правки ниже, и запас
    сократился не больше, чем таблица (так работает `shrink`: таблица ниже на шаг, минимум формы выше на шаг)."""
    if axis != 1 or direction != -1 or a is None or b is None:
        return False
    lim = (now.limits.get((axis, direction)) or [None])[0]
    if lim is None or lim.kind != "минимум" or lim.a.type != "TableBox":
        return False
    before = {item.qualified(): item for item in layout._all_items(was.form)}.get(lim.a.qualified())
    if before is None:
        return False
    drop = (before.box[3] - before.box[1]) - (lim.a.box[3] - lim.a.box[1])
    return 0 < drop and b - a <= drop


class Change:
    """Одно изменение предела по оси и направлению: `kind` — `narrowed` либо `widened`, `span` — предел оси до и после, `what` — слова
    направления с причиной, `forgivable` — сужение объяснено ужатием таблицы (`_forgivable`)."""

    def __init__(self, axis, direction, kind, span, what, forgivable=False):
        self.axis, self.direction, self.kind, self.span, self.what, self.forgivable = axis, direction, kind, span, what, forgivable

    @property
    def words(self):
        return f"{self.span} ({self.what})"


def compare(before, after, shown=None, was=None, now=None):
    """Изменения пределов между документами `before` и `after`: список `Change` (по одному на ось и направление); пусто — пределы те же
    либо раскладка форму не читает. `was` и `now` — уже снятые `Snapshot` (чтобы не читать форму заново)."""
    was = was or snapshot(before, shown)
    now = now or snapshot(after, shown)
    if was is None or now is None:
        return []
    out = []
    for axis in (0, 1):
        same = was.ranges[axis] == now.ranges[axis]
        if same:
            # Те же размеры окна «до» и «после»: изменился размер самой формы, а с ним запас относительно него — числа пределов без пояснения читались бы как «ничего не изменилось».
            span = (f"{layout.AXES[axis]} {layout._size_words(*now.ranges[axis])} — размеры окна прежние, размер формы "
                    f"{was.size[axis]} → {now.size[axis]}")
        else:
            span = f"{layout.AXES[axis]} {layout._size_words(*was.ranges[axis])} → {layout._size_words(*now.ranges[axis])}"
        for direction in (-1, 1):
            a, b = was.room[(axis, direction)], now.room[(axis, direction)]
            what = "сжатие" if direction < 0 else "рост"
            if same and (a is not None or b is not None):
                what += f": запас {_reserve(a)} → {_reserve(b)}"
            if _worse(a, b, direction):
                why = _cause(now, was, axis, direction)
                out.append(Change(axis, direction, "narrowed", span, what + (f" — {why}" if why else ""), _forgivable(was, now, axis, direction, a, b)))
            elif _worse(b, a, direction):
                out.append(Change(axis, direction, "widened", span, what))
    return out


def _reserve(room):
    """Запас в пикселях относительно размера формы: `без предела` или `N px`."""
    return "без предела" if room is None else f"{abs(room)} px"


NARROWED = "правка ограничила растяжение формы: "
WIDENED = "пределы раскладки расширились: "


def _grouped(changes, kind):
    """Слова по осям: предел оси один раз, затем направления."""
    spans = {}
    for c in changes:
        if c.kind == kind:
            spans.setdefault((c.axis, c.span), []).append(c.what)
    return [f"{span} ({'; '.join(whats)})" for (_axis, span), whats in spans.items()]


def narrowed_words(changes):
    """Одна строка о сужении (`NARROWED…`) либо пусто."""
    found = _grouped(changes, "narrowed")
    return NARROWED + "; ".join(found) if found else ""


def widened_words(changes):
    found = _grouped(changes, "widened")
    return WIDENED + "; ".join(found) if found else ""


def unforgiven(changes):
    """Сужения, которые не объяснены ужатием таблицы."""
    return [c for c in changes if c.kind == "narrowed" and not c.forgivable]


def changed_words(before, after, shown=None):
    """Строка `render --sizes --before`: все изменения пределов либо «пределы раскладки не изменились»; `None` — форму не прочитать."""
    was, now = snapshot(before, shown), snapshot(after, shown)
    if was is None or now is None:
        return None
    changes = compare(before, after, shown)
    if not changes:
        return ("пределы раскладки не изменились (сравнивается запас роста и сжатия относительно размера формы, а не сами размеры): "
                f"{range_words(now)}")
    parts = [f"сужение — {w}" for w in _grouped(changes, "narrowed")] + [f"расширение — {w}" for w in _grouped(changes, "widened")]
    return "пределы изменились: " + "; ".join(parts)
