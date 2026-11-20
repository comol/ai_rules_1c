"""Растяжение окна для обзора: что растёт, что сдвигается, где предел — по модели раскладки (`layout.Layout`), только видимые элементы.

Прирост окна берётся из раскладки формы при двух размерах, а не из записи привязок узла: записи не говорят, растёт ли панель, внутри которой лежит элемент,
и не учитывают скрытое. Предел — самый тесный из предела формы и пределов видимых панелей (с содержимым; предел панели пересчитан на размер окна по доле прироста,
которую панель забирает). Форма, у которой решающая поломка привязок (DPI не 96, правило на саму себя), по высоте не растягивается — это сказано следствием.
"""

import math

from .. import anchors_fix, layout

GROW_W, GROW_H = 200, 100           # прирост окна, на котором считается поведение (как в `layout --grow 200x100`)
LISTED = 5                          # элементов в одной строке называется поимённо


def _visible(item, skip=(), names=None):
    """Элемент виден в файле и нарисован на `clean.png`, и так же видны все панели, в которых он лежит (`skip` — имена элементов ненарисованных страниц и скрытого)."""
    while item is not None:
        if not item.visible or (names is not None and names.of(item) in skip):
            return False
        item = getattr(item, "owner", None)
    return True


def undrawn(structure, not_drawn):
    """Имена элементов узлов структуры, которых нет на `clean.png` (`images.not_drawn`), вместе с вложенными узлами."""
    dead = set(not_drawn or ())
    out = set()

    def walk(node, gone):
        gone = gone or node.id in dead
        if gone:
            out.update(node.elements)
        for child in node.children:
            walk(child, gone)
    walk(structure.root if hasattr(structure, "root") else structure, False)
    return out


def _area(item):
    x, y, x2, y2 = item.box
    return max(x2 - x, 0) * max(y2 - y, 0)


def _delta(before, after, axis):
    """`(рост размера, сдвиг начала)` по оси."""
    lo, hi = (0, 2) if axis == 0 else (1, 3)
    return (after[hi] - after[lo]) - (before[hi] - before[lo]), after[lo] - before[lo]


def _movement(form, names, grow_w, grow_h, skip=()):
    """`{ось: {grow: [(имя, на сколько)], move: [(имя, на сколько)]}}` по видимым элементам; ось — `width`, `height`."""
    base = layout.Layout(form, form.width, form.height).ints
    wide = layout.Layout(form, form.width + grow_w, form.height + grow_h).ints
    out = {"width": {"grow": [], "move": []}, "height": {"grow": [], "move": []}}
    ranked = sorted((i for i in form.items.values() if i.index in base and i.index in wide and _visible(i, skip, names)), key=lambda i: -_area(i))
    for item in ranked:
        name = names.short(item)
        for axis, key in ((0, "width"), (1, "height")):
            size, shift = _delta(base[item.index], wide[item.index], axis)
            if size > 0:
                out[key]["grow"].append((name, size, item.type, item))
            elif size == 0 and shift:
                out[key]["move"].append((name, shift, item.type, item))
    for key in out:
        original = {kind: out[key][kind] for kind in ("grow", "move")}
        for kind in ("grow", "move"):
            rows = original[kind]
            ids = {id(item) for _n, _by, _t, item in rows} | ({id(item) for _n, _by, _t, item in original["grow"]} if kind == "move" else set())
            kept = []
            for name, by, typ, item in rows:
                owner, nested = item.owner, False
                while owner is not None:
                    if id(owner) in ids:
                        nested = True            # элемент в панели, которая сама растёт или сдвигается: его движение — следствие
                        break
                    owner = getattr(owner, "owner", None)
                if not nested:
                    kept.append([name, by, typ])
            out[key][kind] = kept
    return out


def _cause(lim, axis, where="формы"):
    a = f"«{lim.a.label()}»"
    if lim.kind == "столкновение":
        return f"{a} наезжает на «{lim.b.label()}»"
    if lim.kind == "край":
        return f"{a} подходит к краю {where} ближе {lim.note} px" if lim.note else f"{a} упирается в край {where}"
    return f"{a} сжимается до минимума"


def _share(coef, owner, axis):
    """Какая доля роста окна доходит до панели `owner`: произведение долей панели и всех панелей, в которых она лежит; `None` — коэффициенты не вычислены (цикл правил)."""
    total, item = 1.0, owner
    while item is not None:
        c = coef.get(item.index)
        if c is None:
            return None
        total *= (c[3] - c[2]) if axis == 0 else (c[1] - c[0])
        item = getattr(item, "owner", None)
    return total


def _limits(form, coef, skip=(), names=None):
    """`{ось: (размер окна, слова причины, вид)}` — предел, который наступит первым при сжатии окна: из пределов раскладки формы и пределов видимых нарисованных панелей с содержимым
    (предел панели пересчитан на окно по доле роста, которую до неё доводят все её владельцы). Предел, у которого участвует невидимый или ненарисованный элемент, не берётся.
    Все виды пределов равны: первым называется тот, чей размер окна ближе к текущему (при равных — столкновение, потом край, потом минимум)."""
    (_w, _h), (_w2, _h2), limits = layout.form_range(form, coef)
    rank = {"столкновение": 0, "край": 1}
    out = {}
    for axis, key in ((0, "width"), (1, "height")):
        found = []                                   # (рост окна, приоритет вида, слова, вид)
        for lim in limits.get((axis, -1)) or []:
            if _hidden_pair(lim, skip, names):
                continue
            found.append((lim.whole, rank.get(lim.kind, 2), _cause(lim, axis), lim.kind))
        for holder in form.holders.values():
            owner = holder.item
            if holder.key == 0 or owner is None or not _visible(owner, skip, names):
                continue
            share = _share(coef, owner, axis)
            if share is None or share < 0.05:
                continue                 # панель с окном не растёт и не сжимается: её содержимое пределом окна не станет
            for lim in layout.holder_limits(form, holder, coef).get((axis, -1)) or []:
                if lim.whole >= 0 or _hidden_pair(lim, skip, names):
                    continue
                found.append((math.ceil(lim.whole / share), rank.get(lim.kind, 2), _cause(lim, axis, f"панели «{owner.label()}»"), lim.kind))
        if found:
            best = min(found, key=lambda f: (-f[0], f[1]))
            size = (form.width, form.height)[axis] + best[0]
            out[key] = (max(size, 0), best[2], best[3])
    return out


def _hidden_pair(lim, skip, names):
    """Предел назван по элементу, которого пользователь не видит."""
    return any(item is not None and not _visible(item, skip, names) for item in (lim.a, getattr(lim, "b", None)))


def build(form, names, skip=()):
    """Словарь растяжения для `brief.json`: `{error, grow, move, limits, broken}`; расчёт, который не удался, — `error` словами. `skip` — имена элементов, которых нет на `clean.png`."""
    result = {"error": None, "grow_by": [GROW_W, GROW_H], "width": {"grow": [], "move": []}, "height": {"grow": [], "move": []}, "limits": {}, "broken": None}
    try:
        coef = layout.coefficients(form)
        result.update(_movement(form, names, GROW_W, GROW_H, skip))
        result["limits"] = {k: {"size": v[0], "cause": v[1], "kind": v[2]} for k, v in _limits(form, coef, skip, names).items()}
        scanned = anchors_fix.scan(form)
        if anchors_fix.decisive(form, scanned):
            culprits = list(dict.fromkeys(f.where for key in anchors_fix.VERDICT for f in scanned.get(key, ())))
            result["broken"] = {"dpi": form.doc["form"].get("dpi"), "elements": culprits}
            result["limits"].pop("height", None)          # привязки сломаны по высоте: предел по этой оси назвать нельзя
    except Exception as why:        # расчёт модели не вправе ронять сборку досье; причина названа в обзоре
        result["error"] = f"{type(why).__name__}: {why}"
    return result
