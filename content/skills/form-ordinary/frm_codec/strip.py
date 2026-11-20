"""`render --sizes`: форма в нескольких размерах в ряд, с пометками поведения и мёртвых правил; с `--before` — две полосы.

Расчёта здесь нет. Каждый кадр строит `render.render(doc, ширина, высота)`, поведение даёт `layout.coefficients`
(`horizontal_behaviour`, `vertical_behaviour`), мёртвые правила — `layout.dead_rules`, а `min` и `max` — нижний и верхний пределы
`layout.form_range`.

Значки рисуются на кадре «как в файле» (если его нет — на первом): на нижнем (по ширине) и правом (по высоте) краю элемента.
Растягивается вместе с окном — синяя двойная стрелка; сдвигается вместе с краем окна — фиолетовая стрелка в сторону сдвига;
растягивается или сдвигается на долю роста окна — бирюзовый пунктир; без значка — остаётся на месте. Мёртвое правило — красный
кружок с крестом в левом верхнем углу. На кадрах других размеров значков нет. Порог между «растягивается» и «сдвигается»
подобран по горизонтали, по вертикали отдельно не проверялся. Слова поведения — из `layout.behaviour_words`.
"""
import collections
import re
from xml.sax.saxutils import escape, quoteattr

from frm_codec import layout, limits, preview, render

GROW, MOVE, PART, DEAD = "#1565c0", "#7b1fa2", "#00897b", "#d32f2f"
BORDERS = ("верх", "низ", "лево", "право")
MARGIN, GAP, TITLE, BAND = 12, 20, 20, 24
FONT = "font-family='Tahoma, sans-serif'"
LIST_MAX = 30  # имён в одном перечне; остальное — «и ещё N»
MIN_GLYPH = 8  # элемент уже или ниже — значка по этой оси нет: он не поместится


class Frame:
    """Один кадр полосы: `label`, размер, `rendered` (или `None` и `refusal` словами)."""

    def __init__(self, label, size, rendered=None, refusal=None, reasons=(), unmeasured=()):
        self.label, self.size, self.rendered, self.refusal = label, size, rendered, refusal
        self.reasons, self.unmeasured = list(reasons), list(unmeasured)  # причины предела по осям (слова `layout`); минимум не проверялся

    @property
    def title(self):
        return f"{self.size[0]}×{self.size[1]} — {self.label}"


class Behaviour:
    """Поведение элементов формы: `{ключ: (по ширине, по высоте)}`; `dead` — `[(ключ, граница, правило)]`; `unset` — элементы без расчёта."""

    def __init__(self, behave, dead, unset):
        self.behave, self.dead, self.unset = behave, dead, unset
        self.ids = {}                # `{ключ: индекс элемента}` у элементов с однозначным индексом: переименованный элемент — тот же элемент
        self.red = frozenset()       # виновники столкновения или залипания: их `Item.qualified()`; рамка — на кадрах предела

    def lines(self):
        def group(axis):
            parts = []
            for kind in (layout.GROWS, layout.MOVES, layout.PARTLY, layout.STANDS):
                keys = [k for k, pair in self.behave.items() if pair[axis] == kind]
                parts.append(f"{layout.behaviour_words(kind, axis, layout.LISTED)}: {_names(keys)}")
            return "; ".join(parts)
        out = ["при растяжении окна по ширине — " + group(0), "при растяжении окна по высоте — " + group(1)]
        out.append(f"мёртвые правила ({layout.DEAD_RULES_WORDS}): "
                   + (", ".join(f"{k} ({BORDERS[b]}, {r})" for k, b, r in self.dead) or "нет"))
        if self.unset:
            out.append("без расчёта (цикл правил или скрытая страница): " + _names(self.unset))
        return out


def _names(keys):
    if not keys:
        return "нет"
    shown = ", ".join(keys[:LIST_MAX])
    return shown + (f" и ещё {len(keys) - LIST_MAX}" if len(keys) > LIST_MAX else "")


def behaviour_of(doc, shown=None, marks=None):
    """Поведение элементов, которые `render` рисует при размере формы; ключи — `preview.keyed`. `marks` — пометки кода и состояние (`render.CodeMarks`): рисуется то же, что на остальных
    картинках досье."""
    rendered = render.render(doc, None, None, shown, marks=marks)
    form = layout.read(doc)
    coef = layout.coefficients(form, shown=shown)
    keyed = preview.keyed(rendered)
    by_index = {item.index: key for key, (item, _box) in keyed.items()}
    behave, unset = {}, []
    for key, (item, _box) in keyed.items():
        c = coef.get(item.index)
        if c is None:
            unset.append(key)
            continue
        top, bottom, left, right = c
        behave[key] = (layout.horizontal_behaviour(left, right), layout.vertical_behaviour(top, bottom))
    dead = [(by_index.get(item.index, item.qualified()), border, rule.text(item.index))
            for item, border, _which, rule, _why in layout.dead_rules(form)]
    result = Behaviour(behave, dead, unset)
    counts = collections.Counter(item.index for item, _box in keyed.values())
    result.ids = {key: item.index for key, (item, _box) in keyed.items() if isinstance(item.index, int) and counts[item.index] == 1}
    return result


def _same_element(before, after):
    """`{ключ после: ключ до}` для одного и того же элемента: по индексу, а без однозначного индекса — по ключу (имя с родителем)."""
    old_by_index = {index: key for key, index in before.ids.items()}
    out = {}
    for key in after.behave:
        index = after.ids.get(key)
        out[key] = old_by_index.get(index) if index is not None and index in old_by_index else (key if key not in before.ids and key not in after.ids else None)
    return out


def changed(before, after):
    """Слова о смене поведения общих элементов и мёртвых правил; пусто — не менялось. Элементы сопоставляются по индексу, переименованный — тот же."""
    parts = []
    same = _same_element(before, after)
    for key, now in after.behave.items():
        was = before.behave.get(same[key]) if same[key] is not None else None
        if was is None or was == now:
            continue
        axes = [f"{name}: было — {layout.behaviour_words(w, axis, layout.BRIEF)}, "
                f"стало — {layout.behaviour_words(n, axis, layout.BRIEF)}" for axis, name, w, n in
                ((0, "по ширине", was[0], now[0]), (1, "по высоте", was[1], now[1])) if w != n]
        parts.append(f"«{key}» ({'; '.join(axes)})")
    lines = ["при растяжении окна изменилось поведение: " + "; ".join(parts) if parts else
             "при растяжении окна поведение общих элементов не изменилось "
             f"({sum(1 for k in after.behave if same[k] is not None and same[k] in before.behave)})"]
    renamed = {old: new for new, old in same.items() if old is not None and old != new}
    b, a = {(renamed.get(k, k), bd, r) for k, bd, r in before.dead}, set(after.dead)
    if a - b:
        lines.append("новые мёртвые правила: " + ", ".join(f"{k} ({BORDERS[bd]}, {r})" for k, bd, r in sorted(a - b)))
    if b - a:
        lines.append("мёртвых правил больше нет: " + ", ".join(f"{k} ({BORDERS[bd]}, {r})" for k, bd, r in sorted(b - a)))
    return lines


# ── Размеры ──

def _shift(d, plus, minus):
    return f"{plus} на {d}" if d > 0 else f"{minus} на {-d}"


def frames_for(doc, text, shown=None, marks=None):
    """Кадры по перечню `--sizes` (`ШxВ`, `min`, `max` через запятую): `(кадры, слова о пределах)`."""
    form = layout.read(doc)
    coef = layout.coefficients(form, shown=shown)
    (w_lo, w_hi), (h_lo, h_hi), limits = layout.form_range(form, coef)
    base = (form.width, form.height)
    notes, wanted = [], []

    def why(direction, vals):
        """Слова причины предела по осям (как у `layout`) и перечень «Имя по оси», где минимум не проверялся."""
        lines, unmeasured = [], []
        for axis, value in enumerate(vals):
            found = limits[(axis, direction)]
            if value is None or not found:
                lines.append(f"{layout.AXES[axis]}: предела нет")
                continue
            lines.append(layout.limit_line(form, coef, axis, direction, found[0]))
            if layout.min_unmeasured(found[0]):
                unmeasured.append(f"{found[0].a.qualified()} по {layout.AXES_AT[axis]}")
        return lines, unmeasured

    for token in (t.strip() for t in text.split(",")):
        low = token.lower().replace("х", "x")
        if low in ("min", "max"):
            lo = low == "min"
            w, h = (w_lo, h_lo) if lo else (w_hi, h_hi)
            if w is None and h is None:
                notes.append("предела сжатия нет — кадра «минимум» нет" if lo else "предела роста нет — ряд без него")
                continue
            size = (base[0] if w is None else w, base[1] if h is None else h)
            what = "минимум раскладки" if lo else "предел роста раскладки"
            for axis, v in (("ширине", w), ("высоте", h)):
                if v is None:
                    what += f" (по {axis} предела нет)"
            reasons, unmeasured = why(-1 if lo else 1, (w, h))
            if unmeasured:
                what += f" (не проверялось: {', '.join(unmeasured)})"
            wanted.append((size, what, reasons, unmeasured))
            continue
        try:
            w, h = (int(v) for v in low.split("x"))
        except ValueError:
            raise ValueError(f"--sizes {token!r}: размер пишется ШxВ (715x440), либо слова min и max") from None
        if w <= 0 or h <= 0:
            raise ValueError(f"--sizes {token!r}: размер должен быть положительным")
        if (w, h) == base:
            what = "как в файле"
        else:
            parts = []
            if w != base[0]:
                parts.append(_shift(w - base[0], "шире", "уже"))
            if h != base[1]:
                parts.append(_shift(h - base[1], "выше", "ниже"))
            what = ", ".join(parts)
        wanted.append(((w, h), what, [], []))
    if not wanted:
        raise ValueError("--sizes: ни одного кадра — назовите размер ШxВ")
    frames = []
    for size, what, reasons, unmeasured in wanted:
        try:
            frames.append(Frame(what, size, render.render(doc, size[0], size[1], shown, marks=marks), None, reasons, unmeasured))
        except ValueError as refusal:
            frames.append(Frame(what, size, refusal=str(refusal), reasons=reasons, unmeasured=unmeasured))
    return frames, notes


# ── Рисунок ──

def _arrow(x1, y1, x2, y2, color, kind, name, axis, double=False, dashed=False):
    """Стрелка с наконечником у `(x2, y2)` (при `double` и у `(x1, y1)`) — один `<g>` с классом `beh <вид> <ось>`."""
    dx = (x2 > x1) - (x2 < x1)
    dy = (y2 > y1) - (y2 < y1)

    def head(x, y, sx, sy):
        return (f"<polygon points='{x},{y} {x - 4 * sx + 3 * sy},{y - 4 * sy + 3 * sx} "
                f"{x - 4 * sx - 3 * sy},{y - 4 * sy - 3 * sx}' fill='{color}'/>")
    dash = " stroke-dasharray='3 2'" if dashed else ""
    body = f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='{color}' stroke-width='2'{dash}/>"
    if not dashed:
        body += head(x2, y2, dx, dy)
        if double:
            body += head(x1, y1, -dx, -dy)
    return f"<g class='beh {kind} {axis}' data-name={quoteattr(name)}>{body}</g>"


def _glyphs(name, box, pair):
    x, y, w, h = box
    out = []
    horiz, vert = pair
    if w >= MIN_GLYPH:
        yy = y + max(h - 5, h // 2)
        out.append({layout.GROWS: lambda: _arrow(x + 3, yy, x + w - 3, yy, GROW, "grows", name, "h", double=True),
                    layout.MOVES: lambda: _arrow(x + max(w - 16, 3), yy, x + w - 3, yy, MOVE, "moves", name, "h"),
                    layout.PARTLY: lambda: _arrow(x + 3, yy, x + w - 3, yy, PART, "partly", name, "h", dashed=True)
                    }.get(horiz, lambda: "")())
    if h >= MIN_GLYPH:
        xx = x + max(w - 5, w // 2)
        out.append({layout.GROWS: lambda: _arrow(xx, y + 3, xx, y + h - 3, GROW, "grows", name, "v", double=True),
                    layout.MOVES: lambda: _arrow(xx, y + max(h - 16, 3), xx, y + h - 3, MOVE, "moves", name, "v"),
                    layout.PARTLY: lambda: _arrow(xx, y + 3, xx, y + h - 3, PART, "partly", name, "v", dashed=True)
                    }.get(vert, lambda: "")())
    return "".join(out)


def _dead_mark(name, box, border, rule, titled=True):
    x, y = box[0] + 7, box[1] + 7
    label = f"<title>{escape(f'{name}: {BORDERS[border]}, {rule}')}</title>" if titled else ""
    return (f"<g class='beh dead' data-name={quoteattr(name)}>{label}"
            f"<circle cx='{x}' cy='{y}' r='5' fill='white' stroke='{DEAD}' stroke-width='1.5'/>"
            f"<path d='M{x - 2.5},{y - 2.5} L{x + 2.5},{y + 2.5} M{x + 2.5},{y - 2.5} L{x - 2.5},{y + 2.5}' "
            f"stroke='{DEAD}' stroke-width='1.5'/></g>")


def red_marks(frame, red):
    """Красные рамки вокруг виновников столкновения или залипания на кадре предела: SVG-текст в координатах кадра."""
    out = []
    for key, (item, (x, y, w, h)) in preview.keyed(frame.rendered).items():
        if item.qualified() in red:
            out.append(f"<rect class='beh red' data-name={quoteattr(key)} x='{x - 1.5}' y='{y - 1.5}' width='{w + 3}' height='{h + 3}' "
                       f"fill='none' stroke='{DEAD}' stroke-width='2'/>")
    return "".join(out)


def marks(frame, behaviour):
    """Значки поведения и мёртвых правил на кадре: SVG-текст в координатах кадра."""
    keyed = preview.keyed(frame.rendered)
    parts = []
    for key, (_item, box) in keyed.items():
        pair = behaviour.behave.get(key)
        if pair:
            parts.append(_glyphs(key, box, pair))
    for key, border, rule in behaviour.dead:
        if key in keyed:
            parts.append(_dead_mark(key, keyed[key][1], border, rule))
    return "".join(parts)


def _text(x, y, text, size=12, bold=False):
    return (f"<text x='{x}' y='{y}' {FONT} font-size='{size}'{' font-weight=\"bold\"' if bold else ''}>"
            f"{escape(text)}</text>")


def _wrap(text, width):
    chars = max(width // 6, 12)
    return re.findall(rf".{{1,{chars}}}(?:\s+|$)|\S+", text) or [text]


def size_title(frame):
    """Подпись кадра без слов: только размер окна."""
    return f"{frame.size[0]}×{frame.size[1]}"


def _slot(frame, plain=False):
    return max(frame.size[0], 8 * len(size_title(frame) if plain else frame.title) + 6)


def _band_height(frames):
    return TITLE + max(f.size[1] for f in frames)


def _band(frames, behaviour, x0, y0, title=None, plain=False):
    """Полоса кадров: `(svg-части, ширина, высота)`. `plain` — у кадра только размер окна: ни названия кадра, ни слов отказа (они в тексте досье)."""
    parts, x = [], x0
    top = y0
    if title:
        parts.append(_text(x0, y0 + 14, title, 14, True))
        top += BAND
    marked = next((i for i, f in enumerate(frames) if f.rendered and f.label == "как в файле"),
                  next((i for i, f in enumerate(frames) if f.rendered), None))
    for i, frame in enumerate(frames):
        w, h = frame.size
        parts.append(_text(x, top + 13, size_title(frame) if plain else frame.title, 13, True))
        fy = top + TITLE
        if frame.rendered is not None:
            tag = {"до": "b", "после": "a"}.get(title, "f") + f"{i}_"   # у каждого кадра свои идентификаторы: иначе обрезка подписей панелей второго кадра идёт по рамке первого
            parts.append(f"<svg x='{x}' y='{fy}' width='{w}' height='{h}'>{preview._inner(frame.rendered.svg, tag)}</svg>")
        else:
            parts.append(f"<rect x='{x}' y='{fy}' width='{w}' height='{h}' fill='#e8e8e8'/>")
            if not plain:
                parts.append(_text(x + 6, fy + 16, "кадра нет:", 12, True))
                for n, line in enumerate(_wrap(frame.refusal, w - 12)[:max((h - 24) // 15, 2)]):
                    parts.append(_text(x + 6, fy + 32 + 15 * n, line.strip()))
        parts.append(f"<rect x='{x - 0.5}' y='{fy - 0.5}' width='{w + 1}' height='{h + 1}' fill='none' stroke='#888'/>")
        if i == marked and behaviour is not None:
            parts.append(f"<g transform='translate({x},{fy})'>{marks(frame, behaviour)}</g>")
        if frame.rendered is not None and frame.reasons and behaviour is not None and behaviour.red:
            parts.append(f"<g transform='translate({x},{fy})'>{red_marks(frame, behaviour.red)}</g>")
        x += _slot(frame, plain) + GAP
    return parts, x - GAP - x0, (top - y0) + _band_height(frames)


def legend_words(estimate=False, red=False):
    """Слова легенды значков поведения: `[строка]` — то, что без `plain` стоит под кадрами, а в досье названо текстом."""
    words = layout.behaviour_words
    out = [f"значок у нижнего края элемента: по ширине — {words(layout.GROWS, 0, layout.LEGEND)}; значок у правого края: по высоте — {words(layout.GROWS, 1, layout.LEGEND)}",
           f"стрелка: по ширине — {words(layout.MOVES, 0, layout.LEGEND)}; по высоте — {words(layout.MOVES, 1, layout.LEGEND)}",
           f"пунктирная стрелка: {words(layout.PARTLY, 0, layout.LEGEND)}",
           "красный кружок с крестиком — мёртвое правило: привязка к краю без парной привязки с другой стороны, в предприятии не действует, граница остаётся на месте",
           f"без значка: {words(layout.STANDS, 0, layout.LEGEND)}"]
    if red:
        out.append("красная рамка — виновник столкновения или залипания на кадре предела")
    if estimate:
        out.append("кадр «не проверялось» — оценка модели (минимум элемента платформой не проверялся, сжатие идёт до нуля), а не снимок предприятия")
    return out


def _legend(y, estimate=False, red=False):
    words = layout.behaviour_words
    rows = [(_arrow(4, 8, 28, 8, GROW, "grows", "", "h", double=True),
             f"по ширине — {words(layout.GROWS, 0, layout.LEGEND)} (значок у нижнего края элемента)"),
            (_arrow(8, 2, 8, 18, GROW, "grows", "", "v", double=True),
             f"по высоте — {words(layout.GROWS, 1, layout.LEGEND)} (значок у правого края)"),
            (_arrow(10, 8, 26, 8, MOVE, "moves", "", "h"), f"по ширине — {words(layout.MOVES, 0, layout.LEGEND)}"),
            (_arrow(8, 3, 8, 17, MOVE, "moves", "", "v"), f"по высоте — {words(layout.MOVES, 1, layout.LEGEND)}"),
            (_arrow(4, 8, 28, 8, PART, "partly", "", "h", dashed=True), words(layout.PARTLY, 0, layout.LEGEND)),
            (_dead_mark("", (0, 0, 14, 14), 0, "", titled=False),
             f"мёртвое правило ({layout.DEAD_RULE_WORDS})")]
    parts = [_text(MARGIN, y + 12, "Поведение при растяжении окна (значки на кадре «как в файле»; без значка — "
                   f"{words(layout.STANDS, 0, layout.LEGEND)}):", 12, True)]
    y += 22
    for glyph, text in rows:
        parts.append(f"<g transform='translate({MARGIN},{y})'>{glyph}</g>")
        parts.append(_text(MARGIN + 38, y + 12, text))
        y += 20
    if red:
        parts.append(f"<rect x='{MARGIN}' y='{y + 3}' width='22' height='12' fill='none' stroke='{DEAD}' stroke-width='2'/>")
        parts.append(_text(MARGIN + 38, y + 12, "красная рамка — виновник столкновения или залипания на кадре предела"))
        y += 20
    if estimate:
        parts.append(_text(MARGIN, y + 12, "Кадр с пометкой «не проверялось» — оценка модели (минимум элемента платформой не проверялся, сжатие идёт до нуля), а не снимок предприятия.", 12, True))
        y += 20
    return parts, y


class Strip:
    """Итог `render --sizes`: `svg`, `lines` — слова в stdout, `notes` — в stderr."""

    def __init__(self, svg, lines, notes, frames=(), legend=()):
        self.svg, self.lines, self.notes = svg, lines, notes
        self.frames, self.legend = list(frames), list(legend)       # слова кадров (`размер — название`) и легенды: в досье, не на картинке


def strip(doc, sizes, before=None, shown=None, red=(), marks=None, plain=False):
    """Полоса кадров `doc`; с `before` — две полосы, «до» над «после». `red` — квалифицированные имена элементов, которые на кадрах
    предела (кадр, у которого названа причина предела) обводятся красной рамкой: виновники столкновения или залипания раскладки. `marks` — пометки кода и состояние формы
    (`render.CodeMarks`) для кадров «после»; кадры «до» рисуются без них. `plain` — у кадров только размер окна, без легенды и слов (досье называет их текстом)."""
    notes = []
    docs = [("до", before), ("после", doc)] if before is not None else [(None, doc)]
    bands, lines, behaviours = [], [], []
    for title, d in docs:
        frames, limit_notes = frames_for(d, sizes, shown, marks if d is doc else None)
        notes.extend(f"{title + ': ' if title else ''}{n}" for n in limit_notes)
        bands.append((title, frames))
        behaviours.append(behaviour_of(d, shown, marks if d is doc else None))
        behaviours[-1].red = frozenset(red)
        for frame in frames:
            if frame.rendered is not None:
                for item in frame.rendered.unknown:
                    notes.append(f"Незнакомый тип, нарисован серым: {item}")
                notes.extend(frame.rendered.notes)
            else:
                notes.append(f"{frame.title}: кадра нет — {frame.refusal}")
    from . import anchors_fix
    for title, d in docs:
        note = anchors_fix.strip_note(layout.read(d))
        if note:
            lines.append(f"{title + ': ' if title else ''}{note}")
    notes = list(dict.fromkeys(notes))
    for (title, _frames), (_t, d), beh in zip(bands, docs, behaviours):
        if title:
            lines.append(f"{title}:")
        snap = limits.snapshot(d, shown)
        lines.append(("  " if title else "") + "пределы раскладки: "
                     + (limits.range_words(snap) if snap is not None else "форму раскладка не читает"))
        lines.extend(("  " if title else "") + line for line in beh.lines())
    for (title, frames), _beh in zip(bands, behaviours):
        for frame in frames:
            if frame.reasons:
                lines.append(f"{title + ': ' if title else ''}{frame.title}:")
                lines.extend("  " + r for r in frame.reasons)
    if before is not None:
        lines.extend(changed(behaviours[0], behaviours[1]))
        words = limits.changed_words(before, doc, shown)
        if words is not None:
            lines.append(words)
    parts, width, y = [], 0, MARGIN
    for (title, frames), beh in zip(bands, behaviours):
        band_parts, w, h = _band(frames, beh, MARGIN, y, title, plain)
        parts.extend(band_parts)
        width = max(width, w)
        y += h + GAP
    estimate = any(f.unmeasured for _t, fr in bands for f in fr)
    legend, bottom = ([], y) if plain else _legend(y, estimate, bool(red))
    total_w = max(width + 2 * MARGIN, 560)
    total_h = bottom + MARGIN
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' width='{total_w}' height='{total_h}'>"
           f"<rect width='{total_w}' height='{total_h}' fill='white'/>" + "".join(parts + legend) + "</svg>")
    return Strip(svg, lines, notes, [f"{f.title}" + ("" if f.rendered is not None else f" (кадра нет: {f.refusal})") for f in bands[-1][1]], legend_words(estimate, bool(red)))
