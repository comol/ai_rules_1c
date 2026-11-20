"""Край страницы панели — к видимой части панели (`normalize_page_edges`).

Предприятие считает правила вложенных элементов панели без рамки от края страницы, равного видимой области панели (`layout.panel_area`),
а не от направляющих края страницы. Если направляющая дальше (или ближе) области, файл расходится с тем, что видит пользователь:
`box` согласован с направляющей, а элементы стоят по области («Размеры» шире на столько же, на сколько страница шире панели).

Операция переносит направляющие края страницы (правую `u4` = 3, нижнюю `u4` = 4: координата плюс отступ) на край области: отступ прежний,
координата — край области минус отступ. `box` вложенных элементов становится местом, где их при проектном размере формы ставит модель
раскладки; правила привязок не меняются (предприятие и так считает их от области). Раскладка проверяется до записи при нескольких размерах
окна: у каждой страницы каждый элемент стоит там же, что до операции, и пределы формы те же; иначе операция отказывает и форма не меняется.
"""
import copy

from .. import edit, layout, limits
from ..edit.base import EditError

# Размеры окна для сверки раскладки до и после: проектный и сдвиги от него (рост и сжатие), а также нижний предел формы по каждой оси.
SIZE_SHIFTS = ((0, 0), (60, 30), (200, 100), (-40, -30), (-100, -60))
MAX_WORDS = 6


def _sizes(form):
    """Размеры окна для сверки: проектный, сдвиги `SIZE_SHIFTS` и нижний предел формы по каждой оси (если он есть)."""
    out = [(form.width + dw, form.height + dh) for dw, dh in SIZE_SHIFTS]
    try:
        (w_lo, _w_hi), (h_lo, _h_hi), _lim = layout.form_range(form)
    except (EditError, layout.Cycle):
        return out
    least = (w_lo if w_lo is not None else form.width, h_lo if h_lo is not None else form.height)
    return list(dict.fromkeys(out + [least]))


def _snapshot(form, groups, sizes):
    """`{(панель, страница, размер): (целые края всех элементов, полоса прокрутки)}` или текст отказа раскладки на этом размере."""
    out = {}
    for key, page, shown in groups:
        for size in sizes:
            try:
                lay = layout.Layout(form, *size, shown=shown)
            except (EditError, layout.Cycle) as e:
                out[(key, page, size)] = f"раскладка отказала: {e}"
                continue
            out[(key, page, size)] = (dict(lay.ints), tuple(lay.scroll))
    return out


def _is_container(form, item):
    """Элемент с вложенными (панель с детьми): у него своя раскладка от его размера, и место ему операция не пишет."""
    holder = form.holders.get(item.index)
    return holder is not None and bool(holder.children)


def _plan(form):
    """Что переносить: `(перенос, пропущено)`.

    `перенос` — `[{holder, page, area, guide, axes, kids}]`: панель, страница, область, край по направляющим, оси с расхождением (больше
    `BOX_TOLERANCE` px), вложенные элементы страницы. `пропущено` — `[слова]`: панели и страницы, которых операция не касается, и почему.
    """
    todo, skipped = [], []
    for holder in form.holders.values():
        owner = holder.item
        if owner is None or _skip_holder(holder):
            continue
        kind = layout._panel_tabs(owner)
        if kind not in layout.PANEL_AREA_CUT:
            continue
        why = _why_not(form, holder, owner)
        if why:
            skipped.append(f"панель «{owner.qualified()}»: {why}")
            continue
        for page, area in sorted(holder.area.items(), key=lambda kv: repr(kv[0])):
            guide = holder.inner.get(page)
            if guide is None:
                continue
            axes = [axis for axis in (0, 1)
                    if (axis == 0 or kind not in layout.PANEL_HEIGHT_DERIVED) and abs(guide[axis] - area[axis]) > layout.BOX_TOLERANCE]
            if axes:
                todo.append({"holder": holder, "page": page, "area": area, "guide": guide, "axes": axes,
                             "kids": [c for c in holder.children if c.page == page]})
    return todo, skipped


def _skip_holder(holder):
    return holder.item is None


def _why_not(form, holder, owner):
    """Почему страницы панели нельзя привести к области (слова) либо `None`: панель обязана быть из проверенных и иметь направляющие страниц."""
    if form.min_note:
        return f"{form.min_note}: область вложенных проверена при DPI 96"
    if not layout._panel_unframed(owner):
        return "у панели есть рамка (или блок рамки не разобран): область вложенных проверена у панели без рамки"
    words = layout.panel_not_checked(form.doc, owner)
    if words:
        return words
    if holder.inner_note:
        return f"у страниц нет направляющих края, край оценён ({holder.inner_note}): переносить нечего"
    if not holder.area:
        return "вложенных элементов нет"
    return None


def _guide(holder, page, order):
    """Направляющая края страницы: первая с этим номером края и этой страницей (как у `anchors._guide_edges`) либо `None`."""
    block = holder.block
    listed = block.get(edit.GUIDES) if isinstance(block, dict) else None
    for guide in listed if isinstance(listed, list) else ():
        if isinstance(guide, dict) and guide.get(edit.GUIDE_PAGE) == page and guide.get(edit.GUIDE_ORDER) == order:
            return guide
    return None


def _apply(form, todo, boxes):
    """Записать в документ формы направляющие и `box`: `todo` — `_plan`, `boxes` — `{индекс: края}`. Возвращает `(перенесено строк, элементов переписано)`."""
    moved = []
    for step in todo:
        holder = form.holders[step["holder"].key]
        for axis in step["axes"]:
            guide = _guide(holder, step["page"], 3 + axis)
            guide[edit.GUIDE_COORD] += step["area"][axis] - step["guide"][axis]
            moved.append((holder.key, step["page"], axis))
    rewritten = 0
    for index, edges in boxes.items():
        item = form.items[index]
        for field, value in zip((edit.X, edit.Y, edit.WIDTH, edit.HEIGHT), edges):
            item.coords[field] = value
        rewritten += 1
    return len(moved), rewritten


def _check_guides(doc, todo):
    """Отказ словами, если направляющей страницы с целой координатой нет или новая координата вышла бы отрицательной."""
    form = layout.read(doc)
    for step in todo:
        holder = form.holders[step["holder"].key]
        for axis in step["axes"]:
            guide = _guide(holder, step["page"], 3 + axis)
            where = f"страница {step['page']} панели «{holder.item.qualified()}»"
            if guide is None or not layout._int(guide.get(edit.GUIDE_COORD)) or not layout._int(guide.get(edit.GUIDE_OFFSET)):
                raise EditError(f"{where}: направляющей {('правого', 'нижнего')[axis]} края с целой координатой и отступом нет — переносить нечего")
            if guide[edit.GUIDE_COORD] + step["area"][axis] - step["guide"][axis] < 0:
                raise EditError(f"{where}: край области {layout._num(step['area'][axis])} при отступе {guide[edit.GUIDE_OFFSET]} дал бы отрицательную координату направляющей")


def normalize_page_edges(doc, panel=None):
    """Края страниц панелей без рамки — к видимой части панели; раскладка в предприятии не меняется.

    `panel` — имя панели (полное, если имя не одно): без него обходятся все панели формы. Страница с направляющими края, дальше или
    ближе области больше чем на 1 px, получает край по области (отступ прежний); `box` её вложенных элементов (кроме панелей с
    вложенными) становится местом по модели раскладки при проектном размере формы. Панели, чья область не проверялась (`panel_not_checked`),
    панели с рамкой и форма с DPI не 96 не трогаются и называются в отчёте. До записи раскладка проверяется при нескольких размерах окна и
    пределы формы сравниваются: расхождение — отказ, форма не меняется.
    """
    form = layout.read(doc)
    todo, skipped = _plan(form)
    if panel is not None:
        todo = [s for s in todo if panel in (s["holder"].item.name, s["holder"].item.qualified())]
        skipped = [w for w in skipped if f"«{panel}»" in w]
        found = [h for h in form.holders.values() if h.item is not None and panel in (h.item.name, h.item.qualified())]
        if not found:
            raise EditError(f"panel {panel!r}: панели с таким именем в форме нет")
        if len(found) > 1 and not any(h.item.qualified() == panel for h in found):
            raise EditError(f"panel {panel!r}: имя встречается несколько раз — назовите панель полным именем (`Родитель/Панель`)")
    tail = (". Не тронуты: " + "; ".join(skipped)) if skipped else ""
    if not todo:
        return ("normalize_page_edges: страниц панелей, чьи направляющие края отличаются от видимой части панели больше чем на 1 px, нет — "
                "форма не изменена" + tail + ".")
    _check_guides(doc, todo)
    groups = [(s["holder"].key, s["page"], layout.shown_for(form, s["holder"], s["page"])) for s in todo]
    sizes = _sizes(form)
    before = _snapshot(form, groups, sizes)
    before_doc = copy.deepcopy(doc)
    # Новое место вложенного — по раскладке при проектном размере формы, каждая страница показана.
    boxes, kept, containers = {}, 0, []
    design = (form.width, form.height)
    for step, (key, page, _shown) in zip(todo, groups):
        got = before[(key, page, design)]
        if isinstance(got, str):
            raise EditError(f"страница {page} панели «{step['holder'].item.qualified()}»: {got} — место элементов по модели не получить")
        ints = got[0]
        for kid in step["kids"]:
            if _is_container(form, kid):
                containers.append(kid)
                continue
            edges = tuple(ints[kid.index])
            if edges == tuple(kid.stored or kid.box):
                kept += 1
            else:
                boxes[kid.index] = edges
    work = copy.deepcopy(doc)
    work_form = layout.read(work)
    _apply(work_form, todo, boxes)
    after_form = layout.read(work)
    after = _snapshot(after_form, groups, sizes)
    bad = [(key, page, size) for (key, page, size), was in before.items() if after[(key, page, size)] != was]
    if bad:
        key, page, size = bad[0]
        raise EditError(f"после переноса раскладка страницы {page} панели «{form.holders[key].item.qualified()}» при {size[0]}×{size[1]} "
                        f"разошлась с прежней ({len(bad)} из {len(before)} проверенных сочетаний «страница × размер»): операция не записана, форма не изменена")
    changed = limits.compare(before_doc, work)
    if changed:
        raise EditError("после переноса изменились пределы раскладки формы (" + "; ".join(c.words for c in changed) + "): операция не записана, форма не изменена")
    left = [step for step in todo if _still_gap(after_form, step)]
    if left:
        raise EditError("после переноса страница " + ", ".join(f"{s['page']} панели «{s['holder'].item.qualified()}»" for s in left)
                        + " по-прежнему расходится с областью: операция не записана, форма не изменена")
    _apply(form, todo, boxes)
    return _words(form, todo, sizes, boxes, kept, containers, after_form, tail)


def _still_gap(form, step):
    holder = form.holders[step["holder"].key]
    guide, area = holder.inner.get(step["page"]), holder.area.get(step["page"])
    return guide is None or area is None or any(abs(guide[a] - area[a]) > layout.BOX_TOLERANCE for a in step["axes"])


def _names(items, limit=MAX_WORDS):
    shown = ", ".join(f"«{i.qualified()}»" for i in items[:limit])
    return shown + (f" и ещё {len(items) - limit}" if len(items) > limit else "")


def _words(form, todo, sizes, boxes, kept, containers, after_form, tail):
    """Отчёт операции: что перенесено, что записано вложенным, что осталось как было и чем проверена раскладка."""
    parts = []
    for step in todo:
        axes = ", ".join(f"{('по ширине', 'по высоте')[a]} {layout._num(step['guide'][a])} → {layout._num(step['area'][a])}" for a in step["axes"])
        parts.append(f"«{step['holder'].item.qualified()}», страница {step['page']}: {axes}")
    lines = [f"normalize_page_edges: край страницы приведён к видимой области панели (страниц: {len(todo)}): " + "; ".join(parts[:MAX_WORDS])
             + (f" и ещё {len(parts) - MAX_WORDS}" if len(parts) > MAX_WORDS else "")
             + f". Направляющие сдвинуты с прежним отступом, правила привязок не менялись. box переписан у {len(boxes)} вложенных элементов "
               f"(у {kept} он уже стоял там, где ставит модель)"]
    if containers:
        lines.append(f"box панелей с вложенными элементами не менялся ({_names(containers)}): их содержимое раскладывается от размера панели в файле")
    outside = []
    for step in todo:
        edge = after_form.holders[step["holder"].key].area.get(step["page"])
        for kid in step["kids"]:
            item = after_form.items[kid.index]
            if not _is_container(after_form, item) and any(item.box[2 + a] > edge[a] + layout.BOX_TOLERANCE for a in step["axes"]):
                outside.append(item)
    if outside:
        lines.append(f"за новым краем страницы остались элементы без правила к этому краю ({_names(outside)}): их место прежнее, предприятие их не сдвигает")
    scrolled = [owner for owner, *_rest in layout.scroll_panels(after_form) if owner.index in {s["holder"].key for s in todo}]
    if scrolled:
        lines.append("страница, как и прежде, перестаёт сжиматься, когда элемент по правилам от области доходит до минимума, и панель прокручивается "
                     "(`layout` называет ширину окна, с которой прокрутка исчезает); box таких элементов — место при проектном размере формы, а не "
                     "результат правил от области")
    lines.append(f"До записи раскладка проверена по модели при размерах окна {', '.join(f'{w}×{h}' for w, h in sizes)}, каждая из страниц ({len(todo)}) показана: "
                 "положение каждого элемента, полоса прокрутки и пределы формы те же, что до операции")
    return ". ".join(lines) + tail + "."
