"""Перераскладка (`relayout`): запись новых привязок при заданном размере и отказы словами."""
import math

from .. import anchors, edit, guides
from .model import BORDERS, AXES, HOLDER_SIDE, CENTER_SIDES, MARGIN, SCROLL, EPS, _int, min_size, caption_measured, ALIVE, _EDGE
from .rules import rule_state, _live, dead_rules
from .coeffs import hidden_page
from .limit_calc import _span, _round_border, _moves
from .form import read
from .atsize import Layout, paged_layout, form_range
from .notes import wide_pages, narrow_pages, _box_words, _size_words, _coupled_words
from .report import obstacle, GUIDE_AXIS, GUIDE_MARK, _holder_words


def relayout(doc, width=None, height=None, unverified=False):
    """Форма `W×H` → `W'×H'` с координатами элементов, какими их покажет предприятие при `W'×H'`.

    Исключение — страница ≥ 1 формы «Сверху» с несогласованным `box`: в файл идёт `box` плюс сдвиг, смещения правил не
    трогаются, и координаты записанной формы не равны показанным.

    Пишется: края каждого элемента; смещения всех правил так, чтобы «граница = сторона + смещение» держалось при новом размере;
    направляющие с отступом от дальнего края и дальние (3 и 4) при любом отступе — к новому краю (`_follows_far_edge`); размер
    формы (при DPI 96 и физический). Встречных записей операция не пишет и не трогает.

    Отказ, если при `W'×H'` раскладка перестаёт меняться (предел называется родом, с советом; `unverified` его не снимает) или в
    форме есть мёртвые правила (`unverified` снимает отказ). `unverified` снимает также отказ при DPI не 96, нескольких страницах
    формы, рамке формы, сырых блоках координат, пределе «минимум», связанном пределе по двум осям и элементе за ближним краем.

    Отчёт называет, как изменился диапазон раскладки, и, если назад к прежнему размеру форма не вернётся, причину
    (`_back_words`). Под `unverified` поле ввода, вышедшее за предел, пишется минимумом 11×19, а не нулём; у надписи, кнопки,
    таблицы и панели с закладками «Сверху» поднимаются только идущие по оси элементы, не меньшие минимума в проекте.
    """
    form = read(doc)
    new_w = form.width if width is None else width
    new_h = form.height if height is None else height
    for value, name in ((new_w, "width"), (new_h, "height")):
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise edit.EditError(f"{name}: размер клиентской области — целое больше нуля, а "
                                 f"пришло {value!r}")
    if (new_w, new_h) == (form.width, form.height):
        return f"relayout: размер тот же ({new_w}×{new_h}) — перекладывать нечего"
    block = doc["form"]
    dpi = block.get("dpi")
    notes = []
    if "device_width" in block and dpi != 96:
        if not unverified:
            raise edit.EditError(
                f"у формы DPI {dpi}: число размера — в единицах формы, а что показывает "
                "предприятие при таком DPI, не проверялось (раскладка проверена при DPI 96). Позвать всё же можно "
                "— unverified=True: физический размер запишется как размер × DPI/96 с "
                "отбрасыванием дробной части")
        notes.append(f"DPI {dpi} — не проверялось")
    pages = edit.pages_count(edit.container(doc))
    if pages and pages > 1:
        if not unverified:
            raise edit.EditError(
                f"у формы страниц {pages}: раскладка проверена на одностраничных формах, а "
                "направляющие и элементы у каждой страницы свои. Позвать всё же можно — "
                "unverified=True: каждая страница перекладывается тем же правилом")
        notes.append(f"страниц формы {pages} — перекладывается каждая, не проверялось")
    if anchors._visible_tabs(doc, edit.container(doc)) is not None:
        why = anchors.tabs_unverified(doc)
        if not unverified:
            if why is None:
                head = ("у формы видны закладки «Сверху»: предприятие ставит её элементы по правилам от области "
                        "страниц (ширина − 2, высота − 20), а не по сохранённому box, и что "
                        "запишет конфигуратор при привязанных элементах страницы, не проверялось")
            else:
                head = (f"у формы видны закладки, а область страниц для них не проверялась ({why}): предприятие ставит "
                        "элементы страницы по неизвестному правилу, модель берёт край по размеру формы, и что "
                        "запишет конфигуратор при привязанных элементах страницы, не проверялось")
            raise edit.EditError(head + ". Позвать всё же можно — unverified=True: boxes переписываются по модели")
        if why is None:
            notes.append("закладки формы — перераскладка по правилам от области страниц (W−2, H−20), при привязанных "
                         "элементах страницы не проверялась")
        else:
            notes.append(f"закладки формы — перераскладка от оценённого края (размер формы): область страниц "
                         f"не проверялась ({why})")
    if _form_border(doc):
        if not unverified:
            raise edit.EditError(
                "у формы рамка: она отнимает у клиентской области два пикселя, а раскладка с "
                "рамкой не проверялась. Позвать всё же можно — unverified=True")
        notes.append("рамка формы — не проверялось")
    if form.raw:
        shown = ", ".join(f"«{item.qualified()}»" for item in form.raw[:6]) + \
            (" …" if len(form.raw) > 6 else "")
        if not unverified:
            raise edit.EditError(
                f"у элементов {len(form.raw)} блок координат лежит сырым ({shown}): карта его не "
                "разобрала, и ни краёв, ни правил их модуль не читает — перераскладка оставила бы "
                "их на месте со всем содержимым, а предприятие их, возможно, двигает. "
                "Позвать всё же можно — unverified=True: они останутся, где стоят")
        notes.append(f"сырых блоков координат {len(form.raw)} ({shown}) — оставлены на месте со "
                     "всем содержимым, их раскладку модуль не читает")
    dead = dead_rules(form)
    if dead and not unverified:
        shown = "; ".join(f"«{item.qualified()}» {BORDERS[b]} ({which} {rule.text(item.index)})"
                          for item, b, which, rule, _why in dead[:6])
        raise edit.EditError(
            f"в форме мёртвых правил {len(dead)}: {shown}{' …' if len(dead) > 6 else ''}. В "
            "предприятии такие границы остаются на месте (нет встречной записи), и перекладывать "
            "их как живые значило бы записать не ту раскладку. Позвать всё же можно — "
            "unverified=True: мёртвые границы останутся на месте, как в предприятии")
    if dead:
        notes.append(f"мёртвых правил {len(dead)} — их границы оставлены на месте, как в "
                     "предприятии; смещения переписаны под новый размер")
    lay = paged_layout(form, new_w, new_h, scroll=False)
    stops = blocking(form, lay)
    order_tail = _order_tail(form, lay, new_w, new_h)
    caption_stops = [lim.a for _k, _a, _d, lim in stops
                     if lim.kind == "минимум" and lim.a.type == "Button" and not caption_measured(lim.a)]
    if stops and all(liftable(lim) for _k, _a, _d, lim in stops):
        if not unverified:
            raise edit.EditError(_inversion_refusal(form, lay, stops, new_w, new_h) + order_tail
                                 + _scroll_tail(form, new_w, new_h))
        for item in caption_stops:
            notes.append(f"кнопка «{item.qualified()}» с подписью «{item.caption or ''}»: минимум ширины кнопки зависит от подписи "
                         "(проверено «ОК» 25, «кнопка» 46, 10 знаков — 65, 20 — 124, 30 — 181, 50 — 298, 70 — 404; формулы нет), "
                         "у этой подписи он не проверялся — взят 46")
        lay = paged_layout(form, new_w, new_h, inversion=False, scroll=False)
        stops = blocking(form, lay)
        for item, axis in lay.collapsed:
            least = min_size(item)[axis]
            what = f"минимума {least}" if least else "нуля"
            notes.append(f"«{item.qualified()}» сжат до {what} по {('ширине', 'высоте')[axis]} — "
                         "предел снят unverified, вывернутый элемент записан минимумом "
                         f"({'минимум типа ' + str(least) if least else 'нулём: минимум типа по этой оси не проверялся'}); "
                         "проектный размер вне предела платформа не чинит (поле 0 px остаётся "
                         "0 px), а первый же размер кодом поставит элемент на предел. Поднимаются только "
                         "элементы, которые по этой оси растягиваются или сдвигаются вместе с окном и не меньше минимума в проекте: остающиеся на месте и "
                         "уже меньшие остаются как есть")
        for item, axis in lay.clamped:
            notes.append(f"«{item.qualified()}» по {('ширине', 'высоте')[axis]} стал бы отрицательным — записан нулём "
                         "(проект уже меньше минимума, предел «до нуля»): платформа такой проект не чинит, сжатие из "
                         "него не проверялось")
    stops = [stop for stop in stops if not liftable(stop[3])]
    if stops:
        raise edit.EditError(_freeze_refusal(form, lay, stops, new_w, new_h) + order_tail
                             + _scroll_tail(form, new_w, new_h, lay.inversion))
    beyond = _beyond_near(form, lay)
    if beyond:
        shown = "; ".join(f"«{item.qualified()}» {side} {value}" for item, side, value in beyond[:6])
        if not unverified:
            raise edit.EditError(
                f"при {new_w}×{new_h} элемент уходит за левый или верхний край родителя ({shown}"
                f"{' …' if len(beyond) > 6 else ''}): ближний предел 0 проверен у одной надписи на форме по ширине; у долей его нет (не проверялось), "
                "у других типов он снят, а что платформа делает с элементом за нулём, не проверялось. "
                "Выберите размер, где он остаётся в родителе, — или позовите с unverified=True: "
                "координаты запишутся как посчитаны (отрицательные)")
        notes.append(f"за левым или верхним краем родителя ({shown}) — не проверялось, записано как посчитано")
    if order_tail:
        notes.append(order_tail.strip(". ").strip())
    for key, found in lay.frozen.items():
        if key != 0 and found:
            holder = form.holders[key]
            notes.append(f"панель «{holder.item.qualified()}» станет меньше своего содержимого: "
                         "оно в ней остаётся на месте, предприятие покажет полосу прокрутки")
    narrowed = _narrowed_buttons(form, lay)
    if narrowed:
        shown = ", ".join(f"«{item.qualified()}» (подпись «{item.caption or ''}»)" for item in narrowed[:6]) + \
            (f" и ещё {len(narrowed) - 6}" if len(narrowed) > 6 else "")
        notes.append(f"кнопка сужена по правилам: {shown}: минимум ширины по подписи не проверялся — расчёт взял 46; проверено «ОК» 25, «кнопка» 46, 10 знаков — 65, "
                     "20 — 124, 30 — 181, 50 — 298, 70 — 404")
    notes += _hidden_relayout_words(form)
    for key, holder in form.holders.items():
        far = _beyond_far(holder, lay.coef)
        if far:
            shown = ", ".join(f"«{item.qualified()}»" for item in far[:6]) + \
                (f" и ещё {len(far) - 6}" if len(far) > 6 else "")
            notes.append(f"за дальним краем {_holder_words(holder)} (граница элемента лежит за краем, расстояние до края меньше нуля): {shown} — предела «край» у "
                         "них нет, что делает платформа с элементом за краем при смене размера, не проверялось; "
                         "записано как посчитано")
    return _rewrite(doc, form, lay, new_w, new_h, dpi, notes)


def liftable(lim):
    """Предел, который `relayout` снимает под `unverified`: «минимум» размера и ближний предел 0 у типа, где он не проверялся. Прочие пределы останавливают раскладку всегда."""
    return lim.kind == "минимум" or (lim.edge == "near" and not lim.measured)


def _narrowed_buttons(form, lay):
    """Кнопки с непроверенной подписью, чья ширина при раскладке `lay` меньше проектной. Это заметка отчёта, а не отказ: отказ ломал бы обратный путь."""
    out = []
    for item in form.items.values():
        if item.raw or item.type != "Button" or caption_measured(item) or item.index not in lay.ints:
            continue
        left, _top, right, _bottom = lay.ints[item.index]
        if right - left < item.box[2] - item.box[0]:
            out.append(item)
    return out


def _hidden_relayout_words(form):
    """Строка отчёта `relayout` о страницах, не показанных в сеансе: в записи каждая страница раскладывается так, как раскладывается показанная. `[строка]` либо пусто."""
    out = []
    for key, holder in form.holders.items():
        hidden = [child for child in holder.children if hidden_page(child)]
        if not hidden:
            continue
        pages = ", ".join(str(p) for p in sorted({child.page for child in hidden}, key=repr))
        whose = (("формы «Не отображать»" if form.pages_off else "формы «Сверху»") if key == 0
                 else f"панели «{holder.item.qualified()}»")
        out.append(f"страницы {pages} {whose} (элементов {len(hidden)}) перекладываются как показанные: предприятие "
                   "раскладывает скрытую страницу только тогда, когда её показывают, а не при смене размера формы; в файл страница пишется так, "
                   "как её разложило бы показанной, поэтому открытая позже она стоит так же, как стояла бы в исходной форме")
    return out


def _beyond_far(holder, coef):
    """Дети родителя за дальним краем (расстояние до края меньше нуля, граница идёт с краем): предела «край» у них нет."""
    out = []
    for item in holder.children:
        if coef.get(item.index) is None:
            continue
        edge = holder.edge(item.page)
        for axis in (0, 1):
            (_s0, _k0), (s1, k1) = _span(item, coef, axis)
            if k1 < 1 - EPS and edge[axis] - s1 < 0:
                out.append(item)
                break
    return out


def blocking(form, lay):
    """Что не даёт разложить форму при размере `lay`: `[(родитель, ось, направление, Limit)]`. Остановленная раскладка формы — всегда;
    остановленное содержимое панели — только по оси, где в панели есть элементы, следующие за ней при растяжении.
    """
    out = [(0, axis, direction, lim) for axis, direction, lim in lay.form_frozen()]
    for key, found in lay.frozen.items():
        if key == 0:
            continue
        holder = form.holders[key]
        out += [(key, axis, direction, lim) for axis, direction, lim in found
                if _moves_in(holder, lay.coef, axis, lim.a.page)]
    return out


def _limit_phrase(form, coef, key, axis, direction, lim):
    """Предел словами с родом: «ширина не сжимается вовсе» или «сжимается не дальше N»; затем род и пара."""
    holder = form.holders[key]
    base = holder.size[axis]
    verb = "растёт" if direction > 0 else "сжимается"
    if lim.whole == 0:
        head = f"{AXES[axis]} не {verb} вовсе (предел — нынешний размер {base})"
    else:
        head = f"{AXES[axis]} {verb} не дальше {base + lim.whole}"
    page = ""
    if lim.a is not None and lim.a.page not in (None, 0) and key in form.holders:
        owner = f"«{holder.item.qualified()}»" if holder.item is not None else "формы"
        page = (f" [стоп страницы {lim.a.page} {owner}: в сеансе без неё он не виден — `layout --size ШxВ "
                f"--shown {holder.item.label() if holder.item is not None else 0}={lim.a.page}`]")
    return f"{head} — {lim.kind}: {lim.words(form, coef)}{page}"


def _advice(stops, coef):
    """Совет по роду предела: остающийся на месте элемент на пути — убрать его, у края — привязать к краю; край и столкновение элементов, которые растягиваются или сдвигаются вместе с окном, — выбрать размер в пределах."""
    blockers, at_edge, moving = [], [], False
    for *_where, lim in stops:
        who = obstacle(lim, coef)
        if who is None:
            moving = True
        elif lim.kind == "столкновение":
            blockers.append(who)
        else:
            at_edge.append(who)
    parts = []
    if blockers:
        many = len(set(blockers)) > 1
        parts.append(f"уберите с пути {_names(blockers)}, котор{'ые остаются' if many else 'ый остаётся'} на месте "
                     f"(оживите {'их' if many else 'его'} привязку по этой оси встречной записью "
                     "или сдвиньте)")
    if at_edge:
        many = len(set(at_edge)) > 1
        parts.append(f"привяжите к краю {_names(at_edge)}, котор{'ые остаются' if many else 'ый остаётся'} на месте у края "
                     "(со встречной записью)")
    tail = "выберите размер в пределах" + (": элементы, которые следуют за окном, сходятся или подходят к "
                                            "краю сами" if moving and not parts else "")
    return ("; ".join(parts) + " — или " if parts else "") + tail


def _names(items):
    return ", ".join(f"«{item.label()}»" for item in dict.fromkeys(items))


def _scroll_tail(form, new_w, new_h, inversion=True):
    """Слова о полосе прокрутки в отказе `relayout`: пределы считаются без неё (`scroll=False`), полоса только называется; пусто, когда раскладка в окно вмещается."""
    bars = Layout(form, new_w, new_h, inversion=inversion).scroll
    if bars == (0, 0):
        return ""
    cuts = [f"{AXES[axis]} на {cut} px (раскладка {'выше' if axis == 0 else 'шире'} окна)"
            for axis, cut in enumerate(bars) if cut]
    return (". Раскладка при таком окне не вмещается: предприятие покажет полосу прокрутки и отнимет у окна "
            + ", ".join(cuts) + " — предел назван без неё, потому что причина — первая остановка раскладки, а не полоса")


def _order_tail(form, lay, new_w, new_h):
    """Слова, если при другом порядке осей раскладка при `new_w×new_h` стоит иначе; порядок при мыши не проверялся. Пусто, когда порядок ничего не меняет."""
    other = "hw" if lay.order == "wh" else "wh"
    alt = Layout(form, new_w, new_h, order=other, scroll=False)
    if alt.effective() == lay.effective():
        return ""
    names = {"wh": "ширина, потом высота", "hw": "высота, потом ширина"}
    mine, theirs = lay.effective(), alt.effective()
    return (f". Порядок осей: расчёт идёт «{names[lay.order]}» (раскладка {mine[0]}×{mine[1]}); при порядке "
            f"«{names[other]}» она встала бы на {theirs[0]}×{theirs[1]} — см. `layout --order {other}`; "
            "порядок при мыши не проверялся")


def _beyond_near(form, lay):
    """Элементы, чья левая или верхняя граница при раскладке `lay` ушла за ноль родителя, хотя в проекте не уходила: `[(элемент, «слева»/«сверху», значение)]`."""
    out = []
    for item in form.items.values():
        if item.raw or item.index not in lay.ints:
            continue
        left, top, _right, _bottom = lay.ints[item.index]
        if left < 0 and item.box[0] >= 0:
            out.append((item, "слева", left))
        if top < 0 and item.box[1] >= 0:
            out.append((item, "сверху", top))
    return out


def _freeze_refusal(form, lay, stops, new_w, new_h):
    (w_lo, w_hi), (h_lo, h_hi), _l = form_range(form, lay.coef, inversion=lay.inversion)
    tail = _advice(stops, lay.coef)
    on_form = [stop for stop in stops if stop[0] == 0]
    coupled = _coupled_words(form, lay.coef, lay.inversion, lay.order,
                             lay.growth[0][0 if lay.order == "wh" else 1])
    if on_form:
        return (f"при {new_w}×{new_h} раскладка формы перестаёт меняться: " + "; ".join(
                    _limit_phrase(form, lay.coef, *stop) for stop in on_form)
                + f" (раскладка следует за окном в пределах ширины {_size_words(w_lo, w_hi)}, "
                  f"высоты {_size_words(h_lo, h_hi)}"
                  + (f"; {coupled}" if coupled else "")
                  + "). Предприятие при таком окне "
                  "оставляет раскладку прежней и показывает пустое поле или прокрутку, а правила этого не описывают; "
                  f"{tail}")
    key = stops[0][0]
    holder = form.holders[key]
    return (f"раскладка содержимого панели «{holder.item.qualified()}» при новом размере перестаёт меняться — "
            + "; ".join(_limit_phrase(form, lay.coef, *stop) for stop in stops
                        if stop[0] == key)
            + "; в панели есть элементы, которые следуют за ней при растяжении, и остановившуюся раскладку правилами "
              f"не удержать; {tail}")


def _inversion_refusal(form, lay, stops, new_w, new_h):
    (w_lo, w_hi), (h_lo, h_hi), _l = form_range(form, lay.coef)
    parts = []
    for key, axis, direction, lim in stops:
        where = "формы" if key == 0 else f"панели «{form.holders[key].item.qualified()}»"
        parts.append(f"в раскладке {where} {lim.words(form, lay.coef)}")
    near = [lim for _k, _a, _d, lim in stops if lim.edge == "near"]
    least = [lim for _k, _a, _d, lim in stops if lim.kind == "минимум"]
    captions = [lim.a for lim in least if lim.a.type == "Button" and not caption_measured(lim.a)]
    what = []
    if least:
        what.append("предел минимума размера: он проверен у поля ввода 11×19, надписи 15×15, кнопки (высота 17; ширина "
                    "зависит от подписи: «ОК» 25, «кнопка» 46, 65 при 10 знаках, 124 при 20, 181 при 30, 298 при 50, 404 при 70, у иной подписи не проверялась), таблицы 20×49 и панели по виду "
                    "закладок («Сверху» и «Снизу» 19×37, «Слева (горизонтально)» 89×19, без закладок 17×17); "
                    "у остальных типов и видов закладок, при DPI не 96 и шрифте не по умолчанию минимум не проверялся (до нуля)")
    if near:
        what.append("ближний предел 0: он проверен у кнопки, поля ввода и надписи на форме по ширине, привязанных вправо "
                    "(раскладка встаёт там, где их Лево 0), у центра — у одной надписи, у других типов, по высоте и внутри панели — по аналогии, не проверялся")
    if captions:
        shown = ", ".join(f"«{item.qualified()}» (подпись «{item.caption or ''}»)" for item in captions[:6])
        what.append(f"минимум ширины кнопки зависит от подписи — {shown}: проверено «ОК» 25, «кнопка» 46, 10 знаков — 65, 30 знаков — 181 "
                    "(20 знаков — 124, 50 — 298, 70 — 404), формулы нет, у этой подписи минимум не проверялся, расчёт взял 46")
    return (f"при {new_w}×{new_h} " + "; ".join(parts) + " — это " + "; а также ".join(what) + ". Форму, записанную ЗА "
            "пределом, платформа не чинит (поле 0 px остаётся 0 px, пока к нему не пришли сменой "
            f"размера). Выберите размер в пределах (ширина {_size_words(w_lo, w_hi)}, высота "
            f"{_size_words(h_lo, h_hi)}) — или позовите с unverified=True: предел не считается, вывернутый "
            "элемент запишется минимумом своего типа там, где он проверен, иначе нулём (ближний предел 0 снимается совсем, "
            "координаты запишутся как посчитаны, отрицательные); остающийся на месте и уже меньший минимума в проекте остаются как есть")


def _form_border(doc):
    """Есть ли у формы рамка: вид рамки блока раскладки контейнера не «нет»."""
    found = edit.layout_block(edit.container(doc), need=False)
    frame = found.get("layout") if isinstance(found, dict) else None
    value = frame.get("border") if isinstance(frame, dict) else None
    kind = value.get("border_type") if isinstance(value, dict) else None
    return kind not in (None, "None", "WithoutBorder", "NoBorder")


def _moves_in(holder, coef, axis, page=None):
    """Идёт ли по оси хоть один ребёнок родителя (с `page` — только этой страницы и без страницы)."""
    return any(_moves(child, coef, axis) for child in holder.children
               if page is None or child.page in (None, page))


def _follows_far_edge(guide):
    """Идёт ли направляющая при перераскладке к новому краю родителя. С отступом от дальнего края — идёт. Дальняя направляющая (3 —
    правая, 4 — нижняя) идёт и при отступе 0: иначе край панели по `anchors.holder_edges` разошёлся бы с документом. Что платформа
    делает с такой направляющей, не проверялось: это выбор модели.
    """
    offset = guide.get(edit.GUIDE_OFFSET)
    return bool(offset) or (guide.get(edit.GUIDE_ORDER) in (3, 4) and _int(offset))


def _panel_written(owner, raw_edges, new_edges):
    """`(как записана панель, как её разложила раскладка)` — оба `(ширина, высота)`. Панель страницы 0 формы «Сверху»: в файле её
    `box` в координатах конструктора (`stored`), у предприятия — по правилам от области (`box`). Пишется `stored + (now − box)`.
    """
    rx, ry, rx2, ry2 = raw_edges
    lay_size = (rx2 - rx, ry2 - ry)
    if owner.stored is not None and tuple(owner.stored) != tuple(owner.box):
        sx, sy, sx2, sy2 = owner.stored
        bx, by, bx2, by2 = (v if isinstance(v, int) else _round_border(v, owner, _EDGE.index(i))
                            for i, v in enumerate(owner.box))
        nx, ny, nx2, ny2 = new_edges   # с поправкой родителя: у панели в панели файловый размер растёт и на неё
        return ((sx2 - sx) + ((nx2 - nx) - (bx2 - bx)), (sy2 - sy) + ((ny2 - ny) - (by2 - by))), lay_size
    x, y, x2, y2 = new_edges
    return (x2 - x, y2 - y), lay_size


def _rewrite(doc, form, lay, new_w, new_h, dpi, notes):
    old_range = form_range(form)
    new = {}
    for holder in form.holders.values():
        for item in holder.children:
            new[item.index] = lay.edges(item)
    growth = {}
    raw = dict(new)  # края по раскладке — до поправок ниже
    for key, holder in form.holders.items():
        if key == 0:
            growth[key] = (new_w - form.width, new_h - form.height)
            continue
        w, h = holder.size
        written, lay_size = _panel_written(holder.item, raw[key], new[key])
        growth[key] = (written[0] - w, written[1] - h)
        d = (written[0] - lay_size[0], written[1] - lay_size[1])
        if d == (0, 0):
            continue
        for child in holder.children:
            c = lay.coef.get(child.index)
            if c is None:
                continue
            edges = list(new[child.index])
            for b, at in enumerate(_EDGE):
                edges[at] += int(math.floor(c[b] * d[0 if b >= 2 else 1] + 0.5 + EPS))
            new[child.index] = tuple(edges)
    moved = offsets = to_edge = halves = nested = 0
    centers = []
    negative = [(item, now) for key, holder in form.holders.items() for item in holder.children
                for now in (new[item.index],)
                if (now[2] < now[0] and item.box[2] >= item.box[0])
                or (now[3] < now[1] and item.box[3] >= item.box[1])]
    if negative:
        shown = "; ".join(f"«{item.qualified()}» {_box_words(now)}" for item, now in negative[:6])
        raise edit.EditError(
            f"при {new_w}×{new_h} размер элемента вышел бы отрицательным ({shown}"
            f"{' …' if len(negative) > 6 else ''}): так форму не записать ни с unverified, ни без — "
            "платформа проект меньше минимума не чинит, а отрицательный размер в файле — испорченный "
            "документ. Выберите размер, где элемент остаётся неотрицательным (предел «до нуля» назван в "
            "`layout`)")
    for key, holder in form.holders.items():
        for item in holder.children:
            old, now = item.box, new[item.index]
            written = now
            if item.stored is not None and item.stored != old:
                written = tuple(s0 + n - (o if isinstance(o, int) else _round_border(o, item, _EDGE.index(i)))
                                for i, (s0, n, o) in enumerate(zip(item.stored, now, old)))
            # Положение по правилам от области бывает дробным (доля правила): сдвиг считается от округлённого, как у `written`.
            raw_old = old
            old = tuple(o if isinstance(o, int) else _round_border(o, item, _EDGE.index(i)) for i, o in enumerate(old))
            for rule_border, pair in enumerate(item.rules):
                shift = now[_EDGE[rule_border]] - old[_EDGE[rule_border]]
                for rule_name, rule in zip(edit.RULES, pair):
                    if rule is None:
                        continue
                    side = _side_shift(form, item, rule, growth[key], new)
                    alive = rule_state(form, item, rule_border, rule)[0] == ALIVE
                    if rule.side in CENTER_SIDES and shift and alive:
                        centers.append(item)
                    first = pair[0]
                    center_first = (first is not None and first.side in CENTER_SIDES
                                    and _live(form, item, rule_border, first)
                                    and lay.coef.get(item.index) is not None
                                    and isinstance(raw_old[_EDGE[rule_border]], int)
                                    and (pair[1] is None or pair[1].off == first.off
                                         or not _live(form, item, rule_border, pair[1])))
                    if center_first and (rule_name == edit.RULES[0]
                                         or (pair[1] is not None and pair[1].off == first.off
                                             and _live(form, item, rule_border, pair[1]))):
                        value = rule.off
                    else:
                        value = rule.off + shift - side
                    if value != int(value):
                        halves += 1
                    value = int(math.ceil(value - EPS))
                    if value != rule.off:
                        item.coords[edit.ANCHORS[rule_border]][rule_name][edit.RULE_OFFSET] = value
                        offsets += 1
                        to_edge += rule.obj == 0 and key == 0
            if tuple(now) != tuple(old):
                moved += 1
                nested += key != 0
            if tuple(written) != tuple(item.stored or old):
                for field, value in zip((edit.X, edit.Y, edit.WIDTH, edit.HEIGHT), written):
                    item.coords[field] = value
    guides = 0
    blocks = [(holder.block, growth[key]) for key, holder in form.holders.items()]
    for index, item in form.items.items():
        if item.type == "Panel" and index not in form.holders and index in new:
            written, _lay = _panel_written(item, raw[index], new[index])
            ex = [v if isinstance(v, int) else _round_border(v, item, _EDGE.index(i)) for i, v in enumerate(item.box)]
            w, h = ex[2] - ex[0], ex[3] - ex[1]
            blocks.append((edit.layout_block(item.node, need=False), (written[0] - w, written[1] - h)))
    for block, (dw, dh) in blocks:
        found = block.get(edit.GUIDES) if isinstance(block, dict) else None
        for guide in found if isinstance(found, list) else ():
            if not isinstance(guide, dict) or guide.get(GUIDE_MARK) != 2 \
                    or not _int(guide.get(edit.GUIDE_COORD)) or not _follows_far_edge(guide):
                continue
            step = dw if guide.get(GUIDE_AXIS) == 1 else dh
            if step:
                guide[edit.GUIDE_COORD] = guide[edit.GUIDE_COORD] + step
                guides += 1
    block = doc["form"]
    old_size = (form.width, form.height)
    block["width"], block["height"] = new_w, new_h
    for axis, value in (("width", new_w), ("height", new_h)):
        device = f"device_{axis}"
        if device in block:
            block[device] = value if dpi == 96 else int(value * dpi // 96)
    if centers:
        who = list(dict.fromkeys(centers))
        shown = ", ".join(f"«{item.qualified()}»" for item in who[:5]) + \
            (" …" if len(who) > 5 else "")
        notes.append(f"правил к центру со встречной записью сдвинуто {len(centers)} ({shown}) — "
                     "их границы идут на половину прироста стороны объекта; центр со строкой проверен при "
                     "чётном росте (остаток 0), а при нечётном размере родителя, когда сторона-центр дробная, "
                     "семантика платформы («от box» или «от правил») не проверялась: модель — от правил, край "
                     "`floor(сторона + смещение)`, смещение центра не меняется"
                     + (f"; смещений с дробью ½ округлено {halves}" if halves else ""))
    elif halves:
        notes.append(f"смещений с дробью ½ округлено {halves} — у правил к центру без встречной "
                     "записи: их граница остаётся на месте, смещение пересчитано под новый размер")
    after = read(doc)
    exact_words = _file_vs_screen_words(form)
    new_range = form_range(after)
    (w_lo, w_hi), (h_lo, h_hi), _lim = new_range
    change = _range_change(old_range, new_range)
    back = _back_words(form, lay.coef, after, old_size)
    return (f"relayout: форма {old_size[0]}×{old_size[1]} → {new_w}×{new_h}; элементов "
            f"сдвинуто {moved} (вложенных {nested}), смещений привязок переписано {offsets} "
            f"(к краю формы {to_edge}), направляющих у дальнего края перенесено {guides}; "
            f"координаты — те, что предприятие показывает при {new_w}×{new_h} по модели раскладки{exact_words}; новая раскладка следует за окном в пределах ширины "
            f"{_size_words(w_lo, w_hi)}, высоты {_size_words(h_lo, h_hi)} (прежде — ширины "
            f"{_size_words(*old_range[0])}, высоты {_size_words(*old_range[1])})"
            + ("; диапазон изменился: " + ", ".join(change) if change else "")
            + (f"; {back}" if back else "")
            + ("; " + "; ".join(notes) if notes else "")
            + RELAYOUT_WINDOW_WORDS
            + "; перераскладка проверена в предприятии (координаты совпали с показанными); "
              "не проверялось: рамка формы, DPI не 96, несколько страниц и закладки формы, вид "
              "дальних направляющих с отступом 0 в конструкторе")


# Цена смены размера формы: размер окна, который предприятие запомнило для формы, привязан к её имени и проектному размеру (`docs/layout.md`,
# «Открытие и смена размера»), и у формы с новым проектным размером его нет.
RELAYOUT_WINDOW_WORDS = ("; размер формы изменился, поэтому размер окна, запомненный пользователями для прежнего проектного размера, к новой форме "
                         "не относится: она откроется в новом проектном размере")


def _file_vs_screen_words(form):
    """Оговорка к «координаты — те, что предприятие показывает» у формы со страницей панели, чей край по направляющим не равен видимой области:
    у такой страницы координаты вложенных в файле записаны от направляющих, а на экране элементы стоят по правилам от области, и `relayout` это
    расхождение не убирает (`normalize_page_edges`). Пусто, если таких страниц нет."""
    pages = sorted({(owner.qualified(), page) for owner, page, *_rest in wide_pages(form) + narrow_pages(form)}, key=repr)
    if not pages:
        return ""
    named = ", ".join(f"«{name}» (страница {page})" for name, page in pages[:6]) + (f" и ещё {len(pages) - 6}" if len(pages) > 6 else "")
    return (f", кроме страниц панелей, чей край по направляющим не равен видимой области панели ({named}): у них в файле координаты записаны от направляющих, "
            "а на экране элементы стоят по правилам от области, и файл с экраном расходится так же, как до операции — сводит их `normalize_page_edges`")


def _range_change(old, new):
    """Как сдвинулись пределы раскладки: «ширина прежде сжималась до 624, теперь — до 664»."""
    out = []
    for axis in (0, 1):
        (o_lo, o_hi), (n_lo, n_hi) = old[axis], new[axis]
        if o_lo != n_lo:
            out.append(f"{AXES[axis]} прежде сжималась {_bound(o_lo)}, теперь — {_bound(n_lo)}")
        if o_hi != n_hi:
            out.append(f"{AXES[axis]} прежде росла {_bound(o_hi)}, теперь — {_bound(n_hi)}")
    return out


def _bound(value):
    return "без предела" if value is None else f"до {value}"


def back_stops(after, old_size):
    """Вернётся ли форма после перераскладки к прежнему размеру: пределы раскладки при прежнем размере, каждая страница показана, без полосы прокрутки. Пусто — вернётся."""
    lay = paged_layout(after, *old_size, scroll=False)
    stops = blocking(after, lay)
    if stops:
        bars = Layout(after, *old_size).scroll
        if any(bars):
            lay.back_scroll = bars
    return lay, stops


def _back_words(form, coef, after, old_size):
    """Строка отчёта, если назад к прежнему размеру форма не вернётся, — с родом причины по ограничивающему элементу исходной формы:

    * «свой отступ» — элемент стоял к краю ближе `MARGIN`; после перераскладки отступ вырос, и сжатие назад упирается в `MARGIN`;
    * «округление» — край-доля стоял ровно в `MARGIN`, и целое расстояние до края при первом же пикселе сжатия меньше
      (`_steps_to_edge`). У малой доли предел по модели целого расстояния равен 0, это не проверялось.
    """
    lay, stops = back_stops(after, old_size)
    if not stops:
        return None
    key, axis, direction, lim = stops[0]
    where = "формы" if key == 0 else f"панели «{after.holders[key].item.qualified()}»"
    words = (f"назад к {old_size[0]}×{old_size[1]} новая форма уже не вернётся — раскладка "
             f"{where}: {_limit_phrase(after, lay.coef, key, axis, direction, lim)}")
    kind = margin_class(form, coef, key, lim)
    if kind == "свой отступ":
        words += (f" (род «свой отступ»: в исходной форме «{lim.a.label()}» стоял к краю ближе "
                  f"{MARGIN} px, и модель позволяла ему этот отступ; после перераскладки отступ "
                  f"вырос, и сжатие упирается в {MARGIN} px — цена правила «{MARGIN} или "
                  "свой, если меньше»)")
    elif kind == "округление":
        words += (f" (род «округление»: край-доля «{lim.a.label()}» и в исходной форме стоял ровно "
                  f"в {MARGIN} px от края, а целое расстояние до края при первом же пикселе сжатия "
                  f"уже меньше {MARGIN} — край сдвигается на долю пикселя, округление на целый: "
                  "исходная форма по этой оси не сжималась вовсе, а перераскладка сохранила этот "
                  "предел. У малой доли предел 0 — по модели целого расстояния, не проверялось)")
    elif lim.kind == "минимум":
        words += (" (род «минимум типа»: перераскладка вернулась бы к размеру, при котором элемент меньше "
                  "минимума своего типа — минимум проверен у поля ввода, надписи, кнопки, таблицы и панели с "
                  "закладками «Сверху»)")
    bars = getattr(lay, "back_scroll", None)
    if bars:
        words += (f" (при прежнем размере раскладка по {'высоте' if bars[0] else 'ширине'} не "
                  f"вмещается в окно: полоса прокрутки отнимет ещё {SCROLL} px у "
                  f"{'ширины' if bars[0] else 'высоты'}, и сжатие упрётся в свой предел и по ней)")
    return words


def margin_class(form, coef, key, lim):
    """Род края, держащего обратный путь: «свой отступ», «округление» или `None` (иное)."""
    if lim.kind != "край" or lim.edge == "near":
        return None
    item = form.items.get(lim.a.index)
    holder = form.holders.get(key)
    c = coef.get(lim.a.index)
    if item is None or holder is None or c is None:
        return None
    x, y, x2, y2 = item.box
    s1 = x2 if lim.axis == 0 else y2
    k = c[3] if lim.axis == 0 else c[1]
    edge = holder.inner.get(item.page)
    if edge is None:
        return None
    margin = edge[lim.axis] - s1  # дальний предел «край» (ближний — edge near, выше отсеян)
    if margin < MARGIN:
        return "свой отступ"
    if margin == MARGIN and EPS < k < 1 - EPS:
        return "округление"
    return None


def _side_shift(form, item, rule, growth, new):
    """Насколько сдвинулась сторона объекта правила: у родителя — 0, прирост или его половина; у элемента — сдвиг его границы."""
    if rule.obj == 0:
        axis = 1 if rule.side in (0, 1, 4) else 0
        return HOLDER_SIDE.get(rule.side, 0.0) * growth[axis]
    target = form.items.get(rule.obj)
    if target is None or target.index not in new:
        return 0
    old, now = tuple(o if isinstance(o, int) else _round_border(o, target, _EDGE.index(i)) for i, o in enumerate(target.box)), new[target.index]
    if rule.side in (0, 1, 2, 3):
        return now[_EDGE[rule.side]] - old[_EDGE[rule.side]]
    pair = (1, 3) if rule.side == 4 else (0, 2)
    return sum(now[i] - old[i] for i in pair) / 2
