"""Перетаскивание разделителя мышью в режиме предприятия (модель; в предприятии не проверялась).

Разделитель — элемент, от привязок которого и к которому зависит, как меняются размеры соседей при его сдвиге. Модель считает так:
обе границы разделителя по оси движения идут на Δ (его собственные правила `slide` при этом не читаются: платформа после
перетаскивания пишет их заново); остальные границы той же страницы того же родителя считаются теми же правилами, что при растяжении
окна (`layout.coefficients`: первое правило — граница идёт со стороной объекта, пара правил — доля между якорями), только края родителя
стоят на месте (окно не менялось). Пределы — шагами по пикселю в обе стороны до первого из трёх событий: элемент короче своего
минимума (`layout.min_size`; где минимум не проверялся — короче 1 px), элемент, которого не было за краем родителя, вышел за него,
два элемента, которые не пересекались, наехали друг на друга.

Что не проверено и платформой не проверено (перечень вопросов — в `QUESTIONS`): правило пересчёта при перетаскивании то же, что при
растяжении окна, — это допущение модели; не доказано, что платформа ограничивает ход разделителя минимумом соседей (а не пускает
дальше); элементы вложенных панелей модель не считает (граница, привязанная к разделителю другого родителя, не сдвигается).
"""
from .. import edit, guides, layout

EDGE = layout._EDGE          # граница (верх, низ, лево, право) → индекс края в (x, y, x2, y2)
CAP = 1000                   # дальше этого хода модель не ищет предел

QUESTIONS = (
    "при перетаскивании правила границ пересчитываются так же, как при растяжении окна (первое правило — со стороной объекта, "
    "пара правил — долей между якорями)? Мерить: сдвиг на +50 и −50, кромки соседей по снимку, до и после",
    "куда разделитель не пускает: до минимума размера соседа, до края родителя, до наезда на соседа — или платформа не ограничивает ход?",
    "что платформа пишет в правила и координаты самого разделителя после перетаскивания (его `slide` остаётся прежним или переписывается)?",
    "элемент, привязанный к другой стороне соседа (цепочкой), и элемент с двумя правилами на одной границе (как у соседей из форм "
    "платформы) двигаются как считает модель?",
)


def _splitter(form, name):
    found = [i for i in layout._all_items(form) if i.name == name]
    if len(found) != 1:
        known = ", ".join(sorted(i.name for i in layout._all_items(form) if i.type == "Splitter" and i.name)) or "—"
        raise edit.EditError(f"разделителя {name!r} в форме нет (или имя не одно). Разделители: {known}")
    item = found[0]
    if item.type != "Splitter":
        raise edit.EditError(f"«{name}» — не разделитель (вид {item.type}): перетаскивание считается у разделителя")
    return item


def axis_of(item):
    """Ось движения: `0` — по горизонтали (вертикальный разделитель, высота не меньше ширины), `1` — по вертикали."""
    x, y, x2, y2 = item.box
    return 0 if (y2 - y) >= (x2 - x) else 1


def coefficients(form, splitter):
    """`{индекс: (cT, cB, cL, cR)}` — на сколько пикселей идёт граница на пиксель сдвига разделителя; `None` — элемент в цикле правил.
    Считаются элементы родителя разделителя; края родителя не двигаются."""
    axis = axis_of(splitter)
    driven = {(splitter.index, b) for b in ((2, 3) if axis == 0 else (0, 1))}
    memo, busy = {}, set()

    def side(target, s):
        if s in (0, 1, 2, 3):
            return border(target, s)
        if s == 4:
            return (border(target, 0) + border(target, 1)) / 2
        if s == 5:
            return (border(target, 2) + border(target, 3)) / 2
        return 0.0

    def rule_coef(item, rule):
        if rule.obj == 0:
            return 0.0
        target = form.items.get(rule.obj)
        if target is None or target.holder != item.holder:
            return 0.0
        return side(target, rule.side)

    def live(item, b, rule):
        return layout._live(form, item, b, rule)

    def border(item, b):
        key = (item.index, b)
        if key in driven:
            return 1.0
        if key in memo:
            return memo[key]
        if key in busy:
            raise layout.Cycle(key)
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
    for item in form.holders[splitter.holder].children:
        if layout.hidden_page(item) or item.page != splitter.page:
            continue
        try:
            out[item.index] = tuple(border(item, b) for b in range(4))
        except layout.Cycle:
            out[item.index] = None
    return out


def boxes_at(form, splitter, delta, coef=None):
    """`{индекс: (x, y, x2, y2)}` после сдвига на `delta` px: только те, у кого что-то сдвинулось, и сам разделитель."""
    coef = coefficients(form, splitter) if coef is None else coef
    out = {}
    for index, c in coef.items():
        if c is None:
            continue
        item = form.items[index]
        box = list(item.box)
        for b in range(4):
            box[EDGE[b]] = item.box[EDGE[b]] + int(round(c[b] * delta))
        out[index] = tuple(box)
    return out


def _overlap(a, b):
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def _problem(form, splitter, coef, moved, delta, start_overlaps, outside0):
    """Первое событие, останавливающее ход на `delta`, словами; `None` — ход свободен."""
    for index, box in moved.items():
        item = form.items[index]
        w, h = box[2] - box[0], box[3] - box[1]
        mw, mh = layout.min_size(item)
        if w < max(mw, 1):
            return f"«{item.label()}» сжимается до ширины {w}" + (f" (минимум {mw})" if mw else " (короче 1 px)")
        if h < max(mh, 1):
            return f"«{item.label()}» сжимается до высоты {h}" + (f" (минимум {mh})" if mh else " (короче 1 px)")
        holder = form.holders[item.holder]
        try:
            right, bottom = holder.edge(item.page)
        except (KeyError, TypeError):
            right, bottom = holder.size
        out = (box[0] < 0, box[1] < 0, box[2] > right, box[3] > bottom)
        for flag, was, word in zip(out, outside0.get(index, (False,) * 4), ("верхний", "левый", "правый", "нижний")):
            if flag and not was:
                return f"«{item.label()}» выходит за {word} край родителя"
    indexes = list(moved)
    others = {i: form.items[i].box for i in coef if i not in moved and coef[i] is not None}
    for i in indexes:
        for j, other in list(others.items()) + [(k, moved[k]) for k in indexes if k > i]:
            if (min(i, j), max(i, j)) in start_overlaps:
                continue
            if _overlap(moved[i], other):
                return f"«{form.items[i].label()}» наезжает на «{form.items[j].label()}»"
    return None


def limits(form, splitter, coef=None):
    """Пределы хода: `{+1: (шаги, причина), -1: (шаги, причина)}` — на сколько px вперёд/назад можно двигать; причина `None` — до `CAP`."""
    coef = coefficients(form, splitter) if coef is None else coef
    live = {i: c for i, c in coef.items() if c is not None}
    start = {i: form.items[i].box for i in live}
    start_overlaps = {(i, j) for i in live for j in live if i < j and _overlap(start[i], start[j])}
    outside0 = {}
    for i in live:
        holder = form.holders[form.items[i].holder]
        try:
            right, bottom = holder.edge(form.items[i].page)
        except (KeyError, TypeError):
            right, bottom = holder.size
        b = start[i]
        outside0[i] = (b[1] < 0, b[0] < 0, b[2] > right, b[3] > bottom)
    out = {}
    for sign in (1, -1):
        steps, why = 0, None
        for n in range(1, CAP + 1):
            moved = {i: box for i, box in boxes_at(form, splitter, sign * n, coef).items() if box != start[i]}
            why = _problem(form, splitter, coef, moved, sign * n, start_overlaps, outside0)
            if why:
                break
            steps = n
        out[sign] = (steps, why)
    return out


def element_words(form, item, before, after):
    """Слова об элементе: по каждой оси — «растёт/сжимается на n» или «сдвигается вправо/влево/вниз/вверх на n»; `None` — на месте."""
    parts = []
    for axis, (lo_b, hi_b, names) in enumerate(((0, 2, ("влево", "вправо")), (1, 3, ("вверх", "вниз")))):
        lo, hi = after[lo_b] - before[lo_b], after[hi_b] - before[hi_b]
        if lo == 0 and hi == 0:
            continue
        size = hi - lo
        if size == 0:
            parts.append(f"сдвигается {names[1] if hi > 0 else names[0]} на {abs(hi)}")
        else:
            grow = f"{'растёт' if size > 0 else 'сжимается'} на {abs(size)} ({layout.AXES[axis]})"
            edges = []
            if lo:
                edges.append(f"{'левая' if axis == 0 else 'верхняя'} граница {'+' if lo > 0 else '−'}{abs(lo)}")
            if hi:
                edges.append(f"{'правая' if axis == 0 else 'нижняя'} граница {'+' if hi > 0 else '−'}{abs(hi)}")
            parts.append(grow + " — " + ", ".join(edges))
    return "; ".join(parts) or None


def table(form, name, deltas=(50, -50)):
    """Таблица «сдвиг разделителя → что с каждым элементом»: строками; `deltas` — сдвиги вдоль оси (+ вправо/вниз)."""
    splitter = _splitter(form, name)
    axis = axis_of(splitter)
    coef = coefficients(form, splitter)
    cycles = sorted(form.items[i].label() for i, c in coef.items() if c is None)
    lim = limits(form, splitter, coef)
    way = (("влево", "вправо"), ("вверх", "вниз"))[axis]
    lines = [f"== перетаскивание разделителя «{name}» ({'вертикальный, ход по горизонтали' if axis == 0 else 'горизонтальный, ход по вертикали'}); "
             "модель, в предприятии не проверялась"]
    for sign, word in ((1, way[1]), (-1, way[0])):
        steps, why = lim[sign]
        lines.append(f"   до упора {word}: {steps} px" + (f" — {why}" if why else f" (предел не найден до {CAP})"))
    for delta in deltas:
        direction = way[1] if delta > 0 else way[0]
        lines.append(f"-- сдвиг {direction} на {abs(delta)}")
        steps, why = lim[1 if delta > 0 else -1]
        if abs(delta) > steps:
            lines.append(f"   за пределом хода ({steps} px: {why}) — раскладку на такой сдвиг модель не считает")
            continue
        moved = boxes_at(form, splitter, delta, coef)
        still = []
        for index in coef:
            item = form.items[index]
            if coef[index] is None:
                continue
            what = element_words(form, item, item.box, moved[index])
            if what is None:
                still.append(item.label())
            else:
                lines.append(f"   {item.label()}: {what}")
        if still:
            lines.append("   остальные на месте: " + ", ".join(still))
    if cycles:
        lines.append("   не вычисляются (цикл правил): " + ", ".join(cycles))
    return lines


def rows(form, name, delta):
    """Для проверки по снимку: `{имя: (x, y, x2, y2)}` всех элементов родителя после сдвига на `delta`."""
    splitter = _splitter(form, name)
    coef = coefficients(form, splitter)
    moved = boxes_at(form, splitter, delta, coef)
    return {form.items[i].label(): box for i, box in moved.items()}


def window_rows(form, grow_w, grow_h):
    """`{имя: (x, y, x2, y2)}` элементов родителя формы при приросте окна `grow_w`×`grow_h` (модель раскладки)."""
    lay = layout.Layout(form, form.width + grow_w, form.height + grow_h)
    out = {}
    for item in form.holders[0].children:
        x, y, w, h = lay.measured(item)
        out[item.label()] = (x, y, x + w, y + h)
    return out


def window_warnings(form, grow_w, grow_h):
    """Предупреждения к росту окна: строки или пусто. Два случая, оба — про полосу прокрутки и «залипание» раскладки.

    1. **Элемент выходит за край окна.** При окне `W×H` правый (нижний) край элемента верхнего уровня, кроме командной панели, дальше
       окна: «выходит за край на N px — появится прокрутка» (полосу даёт вышедший за окно элемент, `Layout.bar_appears`). Порог
       `SCROLL_REACH` там для раскладки, которую держит минимум; при росте окна он не берётся: у `Опыт70` низ в 30 px от края — не
       предупреждение. Элемент, который растёт и сдвигается по правилам, за окно не выходит; случай — привязка с положительным
       смещением от дальнего края или элемент, вылезший за форму в проекте.
    2. **Дальняя направляющая края.** Правая (нижняя) направляющая формы стоит не у края (отступ правой больше 20, нижней больше 40 — `guides.FAR_MARGIN`): у образца с
       направляющими 472/128 и 470/50 окно +200 по ширине дало рост полей +204, горизонтальную прокрутку и невозврат раскладки после возврата окна
       («залипание»; `docs/layout.md`, раздел «Залипание»); тот же образец с направляющими 592/8 и 512/8 прокрутки не дал. Исправляет операция
       `normalize_guides`. Предела «край» на проектном размере модель больше не называет: образец без него залипал при дальних направляющих.
    """
    out = []
    window = (form.width + grow_w, form.height + grow_h)
    lay = layout.Layout(form, *window, scroll=False)
    for item in form.holders[0].children:
        if item.type == "CommandBar":
            continue
        x, y, w, h = lay.measured(item)
        for axis, far in enumerate((x + w, y + h)):
            if far > window[axis]:
                out.append(f"   предупреждение: при окне {window[0]}×{window[1]} «{item.label()}» выходит за край на {far - window[axis]} px "
                           f"({'правый' if axis == 0 else 'нижний'} край {far} при окне {window[axis]}) — появится прокрутка и отнимет "
                           f"{layout.SCROLL} px у {'высоты' if axis == 0 else 'ширины'} окна (`Layout.bar_appears`)")
    out.extend(guides.far_words(form.doc))
    out.extend(guides.below_words(form.doc))
    if grow_w > 0 or grow_h > 0:
        out.extend(guides.panel_words(form.doc))
    return out


def window_table(form, grow_w, grow_h):
    """Растяжение окна на `grow_w`×`grow_h` (прирост клиентской области): что делает каждый элемент родителя формы. Разделитель идёт
    по СВОИМ правилам (`slide` и прочие строения корпуса: стоит, идёт вместе с краем или делит прирост долей), соседи — по правилам к его сторонам
    и к краям родителя, то есть вслед за разделителем. Считает модель раскладки (`layout.Layout`): минимумы и пределы учтены ею."""
    coef = layout.coefficients(form)
    after = window_rows(form, grow_w, grow_h)
    lines = [f"== окно {form.width}×{form.height} → {form.width + grow_w}×{form.height + grow_h} (прирост +{grow_w}/+{grow_h}); модель раскладки"]
    still = []
    for item in form.holders[0].children:
        what = element_words(form, item, item.box, after[item.label()])
        if item.type == "Splitter":
            axis = axis_of(item)
            c = coef.get(item.index)
            share = ""
            if c is not None:
                lo, hi = (c[2], c[3]) if axis == 0 else (c[0], c[1])
                share = (f" (граница идёт на долю {lo:.0%} прироста {layout.AXES_OF[axis]}, размер "
                         f"{'держится' if abs(hi - lo) < 1e-9 else 'меняется'})")
            lines.append(f"   {item.label()} [разделитель, свои правила]: {what or 'остаётся на месте'}{share}")
        elif what is None:
            still.append(item.label())
        else:
            lines.append(f"   {item.label()}: {what}")
    if still:
        lines.append("   остальные на месте: " + ", ".join(still))
    lines.extend(window_warnings(form, grow_w, grow_h))
    return lines
