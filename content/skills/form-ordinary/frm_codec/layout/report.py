"""Отчёт команды `layout`: `summary`, `table`, препятствия и слова о пределах."""
import math

from .. import anchors, edit, guides
from .model import BORDERS, AXES, SCROLL, EPS, caption_measured, _edge_words
from .rules import dead_rules
from .coeffs import coefficients, DEAD_RULES_WORDS, shown_page_diverged, hidden_page
from .limit_calc import _span, holder_limits, _moves, bounds
from .atsize import Layout, form_range
from .notes import (box_mismatches, wide_pages, narrow_pages, wide_pages_words,
    narrow_pages_words, scroll_panels, scroll_panels_words, page0_edge,
    PAGE0_OTHER_WORDS, native_page0_edges, _mismatch_words, _box_words,
    TABS_PAGE0_SHIFT, repeated_top, REPEATED_TOP_WORDS, _size_words,
    _coupled_words, limit_line)


def summary(form, detail=False):
    """Строки сводки: размер, предел раскладки с ограничивающими парами, мёртвые правила, остающиеся на месте элементы на пути. `detail` — по пять ограничений на направление и пределы панелей."""
    coef = coefficients(form)
    lines = []
    nested = sum(len(h.children) for k, h in form.holders.items() if k != 0)
    lines.append(f"форма {form.width}×{form.height} (клиентская область), элементов "
                 f"{len(coef)} (вложенных {nested})"
                 + (f", сырых блоков координат {len(form.raw)} — в раскладку не идут"
                    if form.raw else ""))
    (w_lo, w_hi), (h_lo, h_hi), limits = form_range(form, coef)
    lines.append(f"раскладка следует за окном: ширина {_size_words(w_lo, w_hi)}, высота "
                 f"{_size_words(h_lo, h_hi)}")
    coupled = _coupled_words(form, coef)
    if coupled:
        lines.append("  " + coupled)
    lines.extend(line.strip() for line in guides.far_words(form.doc))
    lines.extend(line.strip() for line in guides.below_words(form.doc))
    lines.extend(line.strip() for line in guides.panel_words(form.doc))
    if "device_width" not in form.doc["form"] and form.tabs_area is not None:
        lines.append("блок формы короткого поколения (без dpi и device_*): область страниц проверена у поколения 16, "
                     "здесь она принята как у DPI 96, шрифт формы (от него зависит полоса закладок) не учитывается "
                     "— не проверялось")
    top = form.holders[0]
    if top.inner_note:
        lines.append(f"предел «к краю» формы считается от оценки — {top.inner_note}")
    elif top.inner and set(top.inner.values()) != {(form.width, form.height)}:
        words = anchors.holder_edges(form.doc, top.node, min(top.inner, key=repr))[2]
        if len(set(top.inner.values())) > 1:
            words += f" (по страницам: {_edge_words(top)})"
        lines.append(f"предел «к краю» формы считается от её края, а не от размера — {words} "
                     "(правило привязок, `anchors.holder_edges`)")
    acting, following = [], []
    holders = [form.holders[0]] + ([h for k, h in form.holders.items() if k != 0]
                                   if detail else [])
    for holder in holders:
        lims = limits if holder.key == 0 else holder_limits(form, holder, coef)
        if holder.key != 0:
            lines.append(f"панель «{holder.item.qualified()}» (её содержимое; клиентская область "
                         f"{_edge_words(holder)}"
                         + (f" — {holder.inner_note}" if holder.inner_note else "") + "):")
        for axis in (0, 1):
            for direction in (1, -1):
                found = lims[(axis, direction)]
                for lim in found[:5 if detail else 1]:
                    lines.append("  " + limit_line(form, coef, axis, direction, lim))
                if holder.key != 0:
                    continue
                # «На пути» — элемент, остающийся на месте и держащий действующий предел; два следующих выводятся отдельной строкой.
                for at, lim in enumerate(found[:3]):
                    who = obstacle(lim, coef)
                    if who is not None:
                        (acting if at == 0 else following).append(who)
    for found in wide_pages(form):
        lines.append(wide_pages_words(*found))
    for found in narrow_pages(form):
        lines.append(narrow_pages_words(*found))
    for found in scroll_panels(form):
        lines.append(scroll_panels_words(*found))
    for words in _hidden_words(form):
        lines.append(words)
    for holder in holders:
        edge = _edge_zero(holder, coef)
        if edge:
            shown = ", ".join(f"«{item.qualified()}»" for item in edge[:6]) + \
                (f" и ещё {len(edge) - 6}" if len(edge) > 6 else "")
            lines.append(f"предела «край» нет у элементов на самом краю {_holder_words(holder)} "
                         f"(панель команд с отступом 0; элемент за краем, где расстояние до края меньше нуля, — "
                         f"не проверялось): {shown}; у обычного элемента с отступом 0 предел есть (проверено у "
                         "одной надписи, у прочих типов — по аналогии); прямой переход со значительно большего размера такой предел не держал: "
                         "например, 1000 → 700 стоит на 700, а не на 708")
    for holder in holders:
        breach = _near_breach(form, holder, coef)
        if breach:
            shown = ", ".join(f"«{item.qualified()}» ({side}, при сжатии на {d} px)"
                              for item, side, d in breach[:6]) + \
                (f" и ещё {len(breach) - 6}" if len(breach) > 6 else "")
            lines.append(f"доля за ближним краем {_holder_words(holder)} — не проверялось: {shown}; предел 0 проверен у границы, которая целиком "
                         "идёт с краем окна, у доли его нет (проверены доля и центр, до нуля они не доходили), "
                         "`relayout` такой размер отказывает без unverified")
    unknown = _unmeasured_buttons(form, coef)
    if unknown:
        shown = ", ".join(f"«{item.qualified()}» (подпись «{item.caption or ''}»)" for item in unknown[:6]) + \
            (f" и ещё {len(unknown) - 6}" if len(unknown) > 6 else "")
        lines.append(f"ширина кнопки, которая по ширине меняется вместе с окном, при сужении зависит от подписи: {shown} — минимум не проверялся, расчёт берёт 46; "
                     "проверено «ОК» 25, «кнопка» 46, «Кнопка с п» 65, «Кнопка с подписью дл» 124, «Кнопка с подписью для проверки» 181, у подписи из 50 знаков 298 и из 70 знаков 404 "
                     "(у 298 и 404 минимум выше проекта — кнопка, побывавшая шире, стоит на нём; расчёт берёт проектную ширину), формулы нет")
    native = native_page0_edges(form)
    if native is not None and not repeated_top(form):  # при повторном «Сверху» «родная» строка спорила бы с REPEATED_TOP_WORDS
        lines.append(f"страница 0 формы «Сверху» записана платформой: смещения считаны от края файла "
                     f"{native[0]}×{native[1]} (ширина, высота − {TABS_PAGE0_SHIFT}); предприятие ставит её "
                     "элементы на (−2, −1) от конструктора — свойство платформы, а не расхождение записи")
    if repeated_top(form):
        lines.append(REPEATED_TOP_WORDS)
    mismatches = box_mismatches(form)
    kind = page0_edge(form.doc) if form.tabs_area is not None else None
    if mismatches and kind == edit.NOBAR8 and edit.framed_nobar8(form.doc):
        lines.append(f"у формы «Сверху» Рамка «Одинарная», нижней командной панели формы нет, отступ направляющих страницы 0 — 6 "
                     f"(край конструктора (W−2, H−2) = {form.width - 2}×{form.height - 2}): страницу 0 платформа при включении "
                     "закладок не переписывала, и предприятие ставит элементы по области (W−2, H−20) — на "
                     f"(0, −18) от конструктора; смещения правил операции здесь пишутся от направляющих "
                     f"(W−2, H−2), а у формы без Рамки (`nobar8`) — от области (W−2, H−20); `validate` об этом молчит")
    elif mismatches and kind == edit.NOBAR8:
        lines.append("у формы «Сверху» нет нижней панели с правилом «к низу формы» 0 (отступ нижней направляющей 8): страницу 0 "
                     "платформа при включении закладок не переписывала, и элементы с правилами к правому и "
                     "нижнему краю предприятие ставит на (−2, −20) от конструктора по области (W−2, H−20); "
                     "`validate` об этом молчит — правило страницы 0 к такой форме не применимо")
    elif mismatches and kind is None and not edit.page0_rule_applies(form.doc):
        lines.append("у формы «Сверху» нет нижней панели с правилом «к низу формы» 0, а отступ нижней направляющей страницы 0 не из "
                     "проверенных видов (33, 8, у Рамки «Одинарная» 6): платформа писала страницу с отступом 16 при крае H−36 "
                     "(форма без панели; правка «Верх» у формы с панелью), других видов не встречалось; "
                     "модель этого вида не знает, box сверен от области (W−2, H−20), расхождение ниже не доказывает "
                     "дефект записи")
    elif mismatches and kind in PAGE0_OTHER_WORDS:
        lines.append(f"вид нижнего края страницы 0 формы «Сверху»: {PAGE0_OTHER_WORDS[kind]}; при включении «Сверху» платформа "
                     "такую страницу пишет иначе и в таком виде, как в файле, её не "
                     "оставляет — файл записан не ею (прогноз редактора, прежний редактор, правка руками); модель записи "
                     "платформы здесь не знает, box сверен от области (W−2, H−20) без поправки, и расхождение ниже не "
                     "доказывает дефект записи; `validate` об этом молчит")
    for item, stored, found in mismatches[:6 if not detail else None]:
        lines.append(_mismatch_words(form, item, stored, found))
    dead = dead_rules(form)
    lines.append(f"мёртвые правила ({DEAD_RULES_WORDS}): {len(dead)}")
    for item, border, which, rule, why in dead:
        lines.append(f"  «{item.qualified()}» {BORDERS[border]}, {which} "
                     f"{rule.text(item.index)}: {why}")
    from .. import anchors_fix
    lines += anchors_fix.summary_lines(form)
    acting = list(dict.fromkeys(acting))
    following = [who for who in dict.fromkeys(following) if who not in acting]
    lines.append("элементы, которые остаются на месте и держат предел: " + (", ".join(
        f"«{o.qualified()}»" for o in acting) if acting else "нет"))
    if following:
        lines.append("ещё элементы, до которых раскладка дойдёт, если снять действующие пределы: "
                     + ", ".join(f"«{o.qualified()}»" for o in following))
    return lines


def obstacle(lim, coef):
    """Элемент, остающийся на месте и держащий предел: у столкновения — тот, до которого доходит другой элемент, у края — тот, что остаётся у края."""
    if lim.kind == "столкновение" and not _moves(lim.b, coef, lim.axis):
        return lim.b
    if lim.kind == "край" and not _moves(lim.a, coef, lim.axis):
        return lim.a
    return None


def table(form, width, height, **state):
    """Раскладка при размере строками: шапка с остановкой по пределу и `имя;Лево;Верх;Ширина;Высота`. `state` — то, чего нет в файле (`order`, `at_open`, `shown`, `stale`)."""
    lay = Layout(form, width, height, **state)
    eff = lay.effective()
    head = f"== {width}×{height} → раскладка {eff[0]}×{eff[1]}"
    frozen = lay.form_frozen()
    if frozen:
        head += " (раскладка перестала меняться: " + "; ".join(
            f"{AXES[axis]} — {lim.words(form, lay.coef)}" for axis, _d, lim in frozen) + ")"
    lines = [head]
    for key, found in lay.frozen.items():
        if key != 0 and found:
            holder = form.holders[key]
            lines.append(f"   раскладка содержимого панели «{holder.item.qualified()}» перестала меняться: "
                         + "; ".join(f"{AXES[axis]} — {lim.words(form, lay.coef)}"
                                     for axis, _d, lim in found))
    if any(lay.scroll):
        cuts = [f"{AXES[axis]} -{cut} (раскладка {'выше' if axis == 0 else 'шире'} окна)"
                for axis, cut in enumerate(lay.scroll) if cut]
        lines.append("   полоса прокрутки отняла у окна: " + ", ".join(cuts)
                     + " (`Layout.bar_appears`); после вычета по одной оси раскладка может перестать "
                       "вмещаться по другой, вторая полоса не считается — не проверялось")
    for axis, (size, window) in enumerate(((eff[0], width), (eff[1], height))):
        if size > window and not lay.scroll[1 - axis]:
            lines.append(f"   раскладка {'шире' if axis == 0 else 'выше'} окна, но полосы прокрутки нет: её держит минимум "
                         "размера элемента, ближний предел 0 или столкновение с командной панелью формы (проверено у верхней `ДействияФормы`, "
                         "которая остаётся на месте; нижняя панель, сдвигающаяся вверх, и свободные командные панели верхнего уровня — по аналогии), и ни один элемент формы, "
                         "кроме командных панелей, за окно не вышел; "
                         + ("нижняя командная панель шире окна полосу не создаёт" if axis == 0 else
                            "нижняя панель срезана окном, а не прокручивается") + ".")
    if lay.at_open:
        lines.append("   открытие в запомненном размере (модель): предел «край» у элемента, остающегося на месте, "
                     "не держит; вычет полосы прокрутки при открытии не объяснён. Результаты разных форм противоречат друг другу: "
                     "у части форм край у элемента, остающегося на месте, открытие не держал, у части — удержал, у части появилась "
                     "горизонтальная полоса (она отнимает 16 px высоты), хотя раскладка по ширине в окно вмещается. "
                     "Как переход модель сходится с замером, с `--at-open` расходится")
        lines.append("   край держит или не держит открытие форма (вид края), а не путь: (а) обычный край (отступ 8): повторное "
                     "открытие после проектного размера в том же сеансе предел «край» не держит — это и считает `--at-open`; "
                     "(б) элемент на самом краю (отступ 0): повторное открытие после проектного предел держит — `--at-open` для такой формы не нужен; "
                     "(в) прямой переход со значительно большего размера (1000 → 700): раскладка стоит на 700, а не на 708")
        lines.append("   раскладка при открытии в запомненном меньшем размере может ложиться на ближний предел кнопки "
                     "(например, 712 = 900 − 188, где 188 — Лево кнопки в раскладке 900), а в переходе — на предел, на котором раскладка перестала меняться; "
                     "условие неполно, и расчёт открытия по этому правилу в модель не внесён")
        if eff[1] > height:
            lines.append(_sticky_words(height, eff[1]))
    lines += _order_words(form, lay, width, height, state)
    for words in _hidden_words(form, lay.shown, lay.stale):
        lines.append("   " + words)
    if repeated_top(form):
        lines.append("   " + REPEATED_TOP_WORDS)
    lines.append("имя;Лево;Верх;Ширина;Высота (вложенные — от левого верха области страницы своей панели, как в box)")
    for key in form.holders:
        for item in form.holders[key].children:
            x, y, w, h = lay.measured(item)
            lines.append(f"{item.qualified()};{x};{y};{w};{h}")
    return lines


def _sticky_words(height, floor):
    """Слова о «залипании» при открытии формы ниже предела высоты (наблюдение, в расчёт не входит). Если при открытии появилась
    вертикальная полоса, раскладка остаётся на `2·L + 16 − H0`; если элемент вылез, а полосы нет, — на пределе `L`; если ничего не
    вылезло и полосы нет, следует за окном. Откуда берётся полоса при открытии, не объяснено.
    """
    return ("   залипание (наблюдение, в расчёт не входит): форма открыта ниже предела высоты "
            f"({height} < {floor}). Исход зависит от того, была ли вертикальная полоса прокрутки при этом открытии или переходе: "
            "(1) была — возврат к проектному размеру оставит раскладку больше проектной (залипание): по формуле её высота "
            f"2·{floor} + 16 − {height} = {2 * floor + SCROLL - height} (L — предел формы, H0 — первое за сеанс открытие ниже предела); "
            "у части форм число отличается от формулы, а залипание бывает и без открытия ниже предела — слова выводятся только при `--at-open`; "
            "до конца сеанса 1С раскладка за окном не следует, повторное открытие её не пересчитывает, новый `.epf` в том же сеансе и новый сеанс состояния не наследуют; "
            f"(2) полосы не было, но элемент вылез — раскладка стоит на пределе {floor} и за окном не следует; "
            "(3) полосы не было и ничего не вылезло — раскладка следует за окном и не стоит на пределе; "
            "одно растущее поле без нижней надписи тоже не липнет. Закрытие крестиком или кодом исход не определяет. "
            "Откуда полоса при открытии, не объяснено: решает слот или имя формы, а порядок открытия не решает, "
            "поэтому какой из исходов будет, до открытия не сказать")


def _order_words(form, lay, width, height, state):
    """Слова о порядке осей: при другом порядке раскладка встаёт иначе — `[строка]`; пусто, когда порядок ничего не меняет."""
    if width == form.width or height == form.height:
        return []
    other = "hw" if lay.order == "wh" else "wh"
    alt = Layout(form, width, height, **{**state, "order": other})
    if alt.effective() == lay.effective():
        return []
    names = {"wh": "ширина, потом высота", "hw": "высота, потом ширина"}
    mine, theirs = lay.effective(), alt.effective()
    return [f"   порядок осей «{names[lay.order]}»: раскладка {mine[0]}×{mine[1]}; при порядке «{names[other]}» "
            f"она встала бы на {theirs[0]}×{theirs[1]} (предел второй оси считается при фактическом росте "
            "первой; порядок при мыши не проверялся)"]


# ── Перераскладка под новый размер (операция редактора `relayout`) ──

GUIDE_AXIS = edit._maybe("Guide", 2)  # 1 — вертикальная линия (ось X), 0 — горизонтальная
GUIDE_MARK = edit._maybe("Guide", 0)  # 2 — запись из девяти позиций; 1 — другая запись


def _unmeasured_buttons(form, coef):
    """Кнопки, идущие по ширине (ширина меняется с окном), с подписью, по которой минимум не проверялся (`BUTTON_MIN_BY_CAPTION`)."""
    return [item for item in form.items.values()
            if not item.raw and item.type == "Button" and not caption_measured(item) and coef.get(item.index) is not None
            and _moves(item, coef, 0) and abs(coef[item.index][3] - coef[item.index][2]) > EPS]


def _hidden_words(form, shown=None, stale=None):
    """Слова про страницы панелей и формы с закладками, не показанные при смене размера: `[строка]`."""
    out = []
    for key, holder in form.holders.items():
        hidden = [child for child in holder.children if hidden_page(child, shown)]
        if hidden:
            pages = sorted({child.page for child in hidden}, key=repr)
            whose = (("формы с закладками «Не отображать»" if form.pages_off
                      else "формы с закладками «Сверху»") if key == 0 else f"панели «{holder.item.qualified()}»")
            where = ("стоят на размере {}×{}, где их оставила прошлая раскладка".format(*stale)
                     if shown and key in shown and stale else "стоят на проектном месте")
            seen = (f"показана страница {shown[key]}" if shown and key in shown else
                    "показанная страница раскладывается на текущий размер")
            extra = ""
            if shown and key in shown and key == 0 and shown[key] >= 1:
                diverged = shown_page_diverged(form, shown)
                extra += ("; показанная страница ≥ 1 формы «Сверху» считается по правилам от области страниц (W−2, H−20), как страница 0, а не по box "
                          "файла плюс сдвиг: box предприятие не читает, элемент стоит по правилам даже при сдвинутом box")
                if diverged:
                    extra += ("; у этой формы box и правила разошлись: " + ", ".join(
                        f"«{it.qualified()}» (по box {_box_words(have)}, по правилам {_box_words(want)})" for it, have, want in diverged[:6])
                        + " — таблица считает по правилам, `relayout` пишет в файл box + сдвиг: показ записанной формы равен показу исходной")
            if shown and key in shown and stale and len({c.page for c in holder.children}) > 2:
                extra += ("; страниц больше двух: прошлая раскладка берётся для всех страниц вместе, а не "
                          "для той, что была показана тогда, — не проверялось")
            out.append(f"страницы {', '.join(str(p) for p in pages)} {whose} "
                       f"не показаны — не перекладываются, {where} и в пределах не "
                       f"участвуют (элементов {len(hidden)}; {seen}{extra}; `relayout` пределы и позиции скрытых страниц считает — каждая страница как показанная, и отказ называет страницу и ключ `--shown`)")
    return out


def _edge_zero(holder, coef):
    """Дети родителя, у которых предела «край» нет: на самом дальнем краю (отступ 0) панели команд, не идущие с краем, и вышедшие за край (не проверялось)."""
    out = []
    for item in holder.children:
        if coef.get(item.index) is None:
            continue
        edge = holder.edge(item.page)
        for axis in (0, 1):
            (_s0, _k0), (s1, k1) = _span(item, coef, axis)
            gap = edge[axis] - s1
            if k1 < 1 - EPS and (gap < 0 or (gap == 0 and item.type == "CommandBar")):
                out.append(item)
                break
    return out


def _near_breach(form, holder, coef):
    """Дети родителя, чья левая (верхняя) граница идёт долей (0 < k0 < 1) и уходит за ноль внутри допустимого сжатия. У доли ближнего
    предела нет, и что платформа делает с элементом за нулём, не проверялось.
    """
    limits = holder_limits(form, holder, coef)
    out = []
    for axis, side in ((0, "слева"), (1, "сверху")):
        lo = bounds(limits)[axis][0]
        for item in holder.children:
            if coef.get(item.index) is None:
                continue
            (s0, k0), _far = _span(item, coef, axis)
            if k0 <= EPS or k0 >= 1 - EPS or s0 < 0:
                continue
            need = math.floor((s0 + 0.5) / k0) + 1  # на сколько сжать, чтобы граница ушла ниже −0,5
            if -lo >= need:
                out.append((item, side, need))
    return out


def _holder_words(holder):
    return "формы" if holder.item is None else f"панели «{holder.item.qualified()}»"
