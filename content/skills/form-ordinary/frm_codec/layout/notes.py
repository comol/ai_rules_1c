"""Замечания раскладки: расхождения файла с экраном, страницы, прокрутка, предупреждения (`problems`)."""
import math

from .. import edit, guides
from .model import BORDERS, AXES, AXES_AT, AXES_OF, EPS, _int, min_size, _panel_tabs, DEAD, BOX_TOLERANCE, _num
from .rules import rule_state, dead_rules
from .coeffs import Cycle, coefficients, rule_box, hidden_page, AREA_MIN
from .limit_calc import holder_limits, bounds
from .area import (PANEL_AREA_CUT, PANEL_HEIGHT_DERIVED, PICTURE_TOP_CUT, tab_pictures,
    panel_area, PANEL_KIND_RU, _panel_unframed, _area,
    _same_edge, _kinds_words, _carrier_shown, FRAMES_TABS_MEASURED,
    _form_border_kind)
from .form import read
from .atsize import Layout


# ── Замечания раскладки (`validate` и `design` в CLI) ──

# Предел роста, ближе которого он называется замечанием: «перестанет меняться, едва окно потянули», а не «где-то дальше».
EARLY = 50
# Растягиваемые типы для проверки «к себе в растягивающейся панели»: поле ввода и выбора, таблица, поле документа, панель, рамка группы, панель команд, поля схем и диаграмм. «У дальнего края» — ближе 24 px.
STRETCHY = frozenset({"TextBox", "ComboBox", "ListBox", "TableBox", "SpreadsheetDocumentField",
                      "TextDocumentField", "HTMLDocumentField", "GraphicalSchemaField",
                      "GeographicalSchemaField", "Chart", "GanttChart", "PivotChart",
                      "Dendrogram", "Panel", "GroupBox", "CommandBar"})
NEAR_EDGE = 24
# Растёт ли панель при росте окна, считает раскладка при окне больше на столько пикселей по обеим осям, с остановкой родителей по цепочке.
PANEL_PROBE = 100

# Числа ниже — итоги подсчёта по снимку форм (с идентификатором `CORPUS_STAMP`); в расчёте не участвуют.
CORPUS_STAMP = "по образцам форм"
CORPUS_DEAD = {"формы": 5, "носитель/первое": 15}
CORPUS_GROWTH_LIMITS = {"ширина": {"< 50": 11, "≥ 50": 6}, "высота": {"< 50": 12, "≥ 50": 1}}
# Замечания раскладки по снимку: (замечаний, форм). Правило от области панели без рамки: «к себе в панели» 485 → 486 замечаний (вложенные считаются
# от области, у одной панели растяжение иное); «страница шире панели» 42/12 → 62/13 (панель «Слева» считается по подписи — на одну форму больше);
# «страница уже панели» — новое замечание (в основном формы, где направляющая страницы на H−24 против области H−20). Минимум поля ввода растёт с кнопками, и
# нижний предел `TextBox/ширина` в `CORPUS_RANGE_MIN` держат два поля больше прежнего (16 → 18).
# Закладки с картинкой (встроенный файл тоже картинка): «Слева (горизонтально)» с картинкой область не считает — «шире панели» 62/13 → 42/12, «уже панели» 474 → 470;
# «Сверху» с картинкой — область ниже на 2 px.
CORPUS_WARNINGS = {"к себе в панели": (486, 292), "страница шире панели": (42, 12), "страница уже панели": (476, 130), "ранний предел": (22, 20),
                   "мёртвое правило": (5, 5)}
# Исходы `relayout` туда и обратно. С правилом от области: у вложенных панели без рамки дробное положение (середина нечётной ширины,
# доля) при записи округляется на единицу, и «обратно иначе» растёт с 3 до 8 (шаг +40×+30: расхождение 1 px у разделителя; панели «Не отображать»
# с направляющими глубоко внутри области отказывают, потому что край «край»-пределов теперь область).
CORPUS_RELAYOUT = {"обратно тот же документ": 4520, "обратно иначе": 7,
                   "обратно отказ: остановка раскладки": 46, "обратно отказ: минимум": 47,
                   "обратно отказ: панель перестаёт меняться": 197,
                   "отказ: панель перестаёт меняться": 29, "отказ: DPI не 96": 122,
                   "отказ: страницы формы": 8, "отказ: рамка формы": 7,
                   "отказ: мёртвые правила": 5, "отказ: сырые блоки": 4,
                   "отказ: остановка раскладки": 1}
# Разбор исходов «обратно иначе» по причине: прежний отступ сохранён или иное; числа сдвинуты теми же округлениями дробного положения.
CORPUS_BACK = {"свой отступ": 235, "иное": 55}
# Сводка `layout`, «box не согласован»: форм и элементов снимка.
# (Элемент страницы панели, стоящей шире области из-за минимума вложенного, записан по раскладке в проекте — `design_place` — и замечанием не называется.)
CORPUS_BOX_MISMATCH = {"форм": 97, "элементов": 929}
CORPUS_HIDDEN = {"со скрытыми": 1200, "сверено": 1171, "отказ": 29}
# Нечётный шаг окна: «тот же документ» меньше, «иначе» больше — тот же пиксель округления центра или доли у вложенных панели без рамки;
# «обратно иначе» не больше названного числа.
CORPUS_ODD_TRIP = {"тот же документ": 44, "обратно иначе": 11, "обратно отказ": 14, "туда отказ": 8}
CORPUS_BACK_MIN = {"Label/ширина": 1, "TextBox/ширина": 1, "TableBox/высота": 1, "Panel/ширина": 44}  # разбивка «обратно отказ: минимум» по типу и оси
# Предел сжатия, который держит «минимум», по типу и оси (каждая 20-я форма снимка).
CORPUS_RANGE_SUM = (53822, 37457)
CORPUS_RANGE_MIN = {"SpreadsheetDocumentField/высота": 48, "TableBox/ширина": 65, "TableBox/высота": 92,
                    "SpreadsheetDocumentField/ширина": 4, "Panel/ширина": 11, "Panel/высота": 65, "CommandBar/ширина": 1,
                    "TextBox/высота": 2, "TextBox/ширина": 18, "HTMLDocumentField/ширина": 1, "HTMLDocumentField/высота": 1,
                    "Label/ширина": 4, "ListBox/высота": 1, "ComboBox/ширина": 1}
CORPUS_RESIDUE = {"проверено": 4956, "не проверить": 37}
# У скольких родителей край оценён: правило привязок его не дало.
CORPUS_EDGE_ESTIMATED = {"форма": 2}


def box_mismatches(form):
    """Элементы, чей `box` не согласован с правилами: `[(элемент, файловый box, положение по правилам)]`. Положение по правилам —
    `rule_box`; родитель с оценённым краем пропускается. Предприятие ставит элемент по правилам, а не по `box`, только у формы с
    закладками «Сверху»; у прочих замечание говорит, что результат неизвестен.
    """
    out, memos, placed_cache = [], {}, {}
    native = native_page0_edges(form)
    for holder in form.holders.values():
        if holder.inner_note or not holder.inner:
            continue
        memo = memos.setdefault(holder.key, {})
        for item in holder.children:
            edge = holder.inner.get(item.page)
            if edge is None:
                continue
            if native is not None and holder.key == 0 and item.page == 0 and not hidden_page(item):
                edge = native
            stored = item.stored or item.box
            found = rule_box(form, item, edge, memo)
            if any(abs(a - b) > BOX_TOLERANCE for a, b in zip(stored, found)):
                if item.from_area:
                    # Страница панели, которая в проектном размере не сжимается до области (элемент дошёл до минимума), стоит шире области: файл
                    # записывает то, что предприятие показывает в проекте, — положение по раскладке, а не по правилам от области.
                    placed = design_place(form, holder, item, placed_cache)
                    if placed is not None and all(abs(a - b) <= BOX_TOLERANCE for a, b in zip(stored, placed)):
                        continue
                area = holder.area.get(item.page)
                if area is not None and not _same_edge(area, edge):
                    # Панель без рамки проверенного вида: предприятие ставит вложенные от области, а не от направляющей страницы. Элемент,
                    # записанный по правилам от направляющей, называет страница (`wide_pages`: «шире видимой части панели»); прочие
                    # сверяются с областью.
                    near = rule_box(form, item, area, memos.setdefault(("area", holder.key), {}))
                    if any(abs(a - b) > BOX_TOLERANCE for a, b in zip(stored, near)):
                        out.append((item, stored, near))
                    continue
                out.append((item, stored, found))
    return out


def shown_for(form, holder, page):
    """Какие страницы показаны, когда считается страница `page` панели `holder`: сама она и страницы панелей, в которые она вложена
    (`{ключ родителя: страница}`, как `shown` раскладки)."""
    shown = {holder.key: page}
    owner = holder.item
    while owner is not None:
        parent = form.holders[owner.holder]
        if owner.page is not None:
            shown[parent.key] = owner.page
        owner = parent.item
    return shown


def design_place(form, holder, item, cache):
    """Целые края элемента панели по раскладке при проектном размере формы, страница показана; `None`, если раскладка отказала или у элемента
    краёв нет. Общий для страницы расчёт хранится в `cache`."""
    key = (holder.key, item.page)
    if key not in cache:
        try:
            cache[key] = dict(Layout(form, form.width, form.height, shown=shown_for(form, holder, item.page)).ints)
        except (edit.EditError, Cycle):
            cache[key] = None
    ints = cache[key]
    return tuple(ints[item.index]) if ints and item.index in ints else None


def nested_area_mismatches(form, shown=None):
    """Вложенные элементы, чей `box` не согласован с правилами от области страницы панели её вида закладок:
    `[(элемент, панель, файловый box, положение по правилам, прежние виды, под которые записаны направляющие)]`. Замечание — только у
    панели без рамки (`_panel_unframed`), где направляющие (`Holder.inner`) легли на область другого проверенного вида: так выглядит
    панель, чьи закладки поменяли, не переложив вложенные. Вертикальные края у «Не отображать» и «Слева (горизонтально)» не
    считаются (`PANEL_HEIGHT_DERIVED`).
    """
    out = []
    for holder in form.holders.values():
        owner = holder.item
        kind = _panel_tabs(owner) if owner is not None else None
        if kind not in PANEL_AREA_CUT or holder.inner_note or not _panel_unframed(owner):
            continue
        if not _carrier_shown(form, owner, shown):
            continue
        edge, _why = panel_area(form.doc, owner, holder.size)
        if edge is None:
            continue
        sides = (0, 2) if kind in PANEL_HEIGHT_DERIVED else (0, 1, 2, 3)
        memo = {}
        for item in holder.children:
            if not item.visible or hidden_page(item, shown):
                continue
            written = holder.inner.get(item.page)
            if written is None or _same_edge(written, edge):
                continue
            was = [k for k in PANEL_AREA_CUT if _same_edge(written, _area(holder.size, k))]
            if not was:
                continue
            stored = item.stored or item.box
            found = rule_box(form, item, edge, memo)
            if any(abs(found[i] - stored[i]) > BOX_TOLERANCE for i in sides):
                out.append((item, owner, stored, found, was))
    return out


def nested_area_words(item, panel, stored, found, was):
    """Слова замечания о `nested_area_mismatches`: какой проверенный край предприятие поставит на N, а файл — на M."""
    kind = _panel_tabs(panel)
    if kind == "LeftHorizontal":
        cut_words = "размер панели минус полоса закладок по подписи и 2 px"
    else:
        cut = PICTURE_TOP_CUT if any(tab_pictures(panel.node)) else PANEL_AREA_CUT[kind]
        cut_words = f"размер панели минус ({cut[0]}, {cut[1]})"
    sides = ("левый", "верхний", "правый", "нижний")
    measured = (0, 2) if kind in PANEL_HEIGHT_DERIVED else (0, 1, 2, 3)
    edges = [f"{sides[i]} край на {_num(found[i])}, файл — на {_num(stored[i])}" for i in measured
             if abs(found[i] - stored[i]) > BOX_TOLERANCE]
    caveats = []
    if kind in PANEL_HEIGHT_DERIVED:
        caveats.append("вертикальные края не проверялись: высота области этого вида выведена, а не снята")
    return (f"у вложенного элемента «{item.label()}» панели «{panel.qualified()}» box не согласован с правилом от области "
            f"вида закладок «{PANEL_KIND_RU[kind]}» ({cut_words}, панель без рамки): "
            f"предприятие поставит {'; '.join(edges)}. Направляющие панели записаны под вид {_kinds_words(was)}, вложенные "
            "правка вида не перекладывает, а предприятие ставит их по правилам от области нового вида"
            + (f" ({'; '.join(caveats)})" if caveats else ""))


def wide_pages(form, shown=None):
    """Страницы панелей без рамки проверенного вида, чьи направляющие края дальше видимой области панели:
    `[(панель, страница, направляющая (право, низ), область, [(ось, на сколько шире)], элементов по направляющей, элементов всего)]`.
    Предприятие считает правила вложенных от края страницы, равного области (`Form._panels_by_rules_from_area`), и у такой страницы
    вложенные, записанные по правилам от направляющей, встают иначе: у «Номенклатуры» страница 0 шире области на 135 px, и «Размеры»
    при том же окне уже на столько же. Страница, чья направляющая легла на область другого проверенного вида, названа
    `nested_area_mismatches` и здесь не повторяется. Родитель с оценённым краем (направляющих нет) пропускается.
    """
    return _page_gaps(form, shown, wider=True)


def narrow_pages(form, shown=None):
    """Страницы панелей без рамки проверенного вида, чьи направляющие края ближе (выше) видимой области панели больше чем на 1 px: те
    же поля, что у `wide_pages`, `[(ось, на сколько уже)]`. Проверено в предприятии: направляющая по высоте
    ближе области на 4 px, вложенные встали по области; привязанные вправо или вниз длиннее, чем в файле.
    """
    return _page_gaps(form, shown, wider=False)


def _page_gaps(form, shown, wider):
    out = []
    for holder in form.holders.values():
        owner = holder.item
        if owner is None or not holder.area or holder.inner_note or not _carrier_shown(form, owner, shown):
            continue
        kind = _panel_tabs(owner)
        for page, area in sorted(holder.area.items(), key=lambda kv: repr(kv[0])):
            guide = holder.inner.get(page)
            if guide is None:
                continue
            sign = 1 if wider else -1
            over = [(axis, _num(sign * (guide[axis] - area[axis]))) for axis in (0, 1)
                    if (axis == 0 or kind not in PANEL_HEIGHT_DERIVED) and sign * (guide[axis] - area[axis]) > BOX_TOLERANCE]
            if not over or any(_same_edge(guide, _area(holder.size, k)) for k in PANEL_AREA_CUT):
                continue
            kids = [c for c in holder.children if c.page == page and c.visible]
            memo = {}
            by_guide = sum(1 for c in kids if all(abs(a - b) <= BOX_TOLERANCE
                                                  for a, b in zip(c.stored or c.box, rule_box(form, c, guide, memo))))
            out.append((owner, page, guide, area, over, by_guide, len(kids)))
    return out


def wide_pages_words(owner, page, guide, area, over, by_guide, total):
    """Слова замечания о `wide_pages`."""
    axes = "; ".join(f"{('по ширине', 'по высоте')[axis]} на {extra} px" for axis, extra in over)
    return (f"страница {page} панели «{owner.qualified()}» шире видимой части панели {axes} (край по направляющим {_num(guide[0])}×{_num(guide[1])}, "
            f"область {_num(area[0])}×{_num(area[1])}): предприятие считает правила вложенных от края страницы, равного области, а не "
            f"от направляющей, и записанные по правилам от направляющей ({by_guide} из {total}) встают иначе: привязанные вправо или "
            "вниз уже (короче), чем в файле; у элемента, дошедшего до минимума, страница перестаёт сжиматься и панель прокручивается; "
            "свести файл с областью без изменения раскладки — операция `normalize_page_edges`")


def narrow_pages_words(owner, page, guide, area, over, by_guide, total):
    """Слова замечания о `narrow_pages`."""
    axes = "; ".join(f"{('по ширине', 'по высоте')[axis]} на {extra} px" for axis, extra in over)
    return (f"страница {page} панели «{owner.qualified()}» уже (ниже) видимой части панели {axes} (край по направляющим {_num(guide[0])}×{_num(guide[1])}, "
            f"область {_num(area[0])}×{_num(area[1])}): предприятие ставит элементы страницы по правилам от области, а не от направляющей, и "
            f"привязанные вправо или вниз ({by_guide} из {total} записаны по правилам от направляющей) шире (длиннее), чем в файле; "
            "свести файл с областью без изменения раскладки — операция `normalize_page_edges`")


def scroll_panels(form, shown=None):
    """Панели, чья страница при сужении окна перестаёт сжиматься: `[(панель, ось, окно меньше N, элемент, минимум)]`. Элемент по
    правилам от области в проектном размере уже ниже своего минимума (`Item.from_area`, предел стоит за нулём), и страница не
    сжимается дальше размера, где он достиг минимума: панель получает полосу прокрутки (мерено на «Номенклатуре»: ширина окна 724 —
    полоса, 765 — нет). Порог считается раскладкой формы бисекцией по размеру окна; `N` — первый размер без прокрутки.
    """
    coef = coefficients(form, hide=True, shown=shown)
    out = []
    for holder in form.holders.values():
        owner = holder.item
        if owner is None or not holder.area or not _carrier_shown(form, owner, shown):
            continue
        limits = holder_limits(form, holder, coef)
        for axis in (0, 1):
            found = limits[(axis, -1)]
            if not found or found[0].note != AREA_MIN or found[0].d <= EPS:
                continue
            lim = found[0]
            base = (form.width, form.height)
            size = lambda v: (v, form.height) if axis == 0 else (form.width, v)

            def scrolls(v):
                try:
                    lay = Layout(form, *size(v), hide=True, scroll=False, shown=shown)
                except edit.EditError:
                    return False
                return any(a == axis and d < 0 for a, d, _lim in lay.frozen.get(holder.key, ()))

            lo = next((v for v in (base[axis], base[axis] * 3 // 4, base[axis] // 2, base[axis] // 4, 20) if scrolls(v)), None)
            if lo is None:
                continue
            hi, cap = lo + 16, 8 * base[axis] + 4096
            while scrolls(hi) and hi < cap:
                lo, hi = hi, hi * 2
            while hi - lo > 1:
                mid = (lo + hi) // 2
                lo, hi = (mid, hi) if scrolls(mid) else (lo, mid)
            n = None if scrolls(hi) else hi
            out.append((owner, axis, n, lim.a, min_size(lim.a)[axis]))
    return out


def scroll_panels_words(owner, axis, n, item, least):
    """Слова о `scroll_panels`."""
    when = (f"при {AXES_AT[axis]} окна меньше {n}" if n is not None else "в проектном размере и меньше")
    return (f"панель «{owner.qualified()}» прокручивается по {('ширине', 'высоте')[axis]} {when}: по правилам от области страницы "
            f"«{item.qualified()}» ушёл бы ниже минимума ({least}), и страница перестаёт сжиматься; полоса прокрутки "
            "внизу панели у «Сверху» проверена по ширине окна; высота и другие виды закладок не проверялись")


def page0_edge(doc):
    """Вид нижнего края страницы 0 для сверок (`edit.page0_edge_kind`): `bar33`, `nobar8`, `nobar33`, `bar8` либо `None`; у формы с
    рамкой «Одинарная» без панели с отступом 6 — `nobar8`. Платформа переписывает страницу 0 по-разному в зависимости от вида.
    """
    kind = edit.page0_edge_kind(doc)
    if kind is None and edit.framed_nobar8(doc):
        return edit.NOBAR8
    return kind


def page0_rewritten(doc):
    """Страница 0 записана платформой так, как её знает модель (`bar33`; при `None` — пока файл укладывается в `(W или W−2, H−19)`).
    `nobar8` платформа не переписывала, а `nobar33` и `bar8` переписала иначе, и модель их не знает.
    """
    kind = page0_edge(doc)
    return kind == edit.BAR33 or (kind is None and edit.page0_rule_applies(doc))


PAGE0_OTHER_WORDS = {
    edit.NOBAR33: "нижней панели формы нет, отступ нижней направляющей 33 (направляющая 387/33 → 368/16, "
                  "правила «к низу формы» +36)",
    edit.BAR8: "нижняя панель формы есть, отступ нижней направляющей 8 (направляющие 692/8 → 700/0 и "
               "412/8 → 420/0, панель и правила «к низу» не тронуты)",
}


def native_page0_edges(form):
    """`(право, низ)` страницы 0 формы «Сверху», записанной платформой или `rewrite_page0_for_tabs` (края файла `(W или W−2, H−19)`); иначе `None`."""
    if form.tabs_area is None or not page0_rewritten(form.doc):
        return None
    found = _page0_edges(form.doc)
    if found is None:
        return None
    _at, right, bottom = found
    if bottom == form.height - TABS_PAGE0_SHIFT and right in (form.width, form.width - 2):
        return right, bottom
    return None


def _mismatch_words(form, item, stored, found):
    """Слова замечания: где элемент стоит в файле и где по правилам его поставит предприятие."""
    head = f"box «{item.qualified()}» не согласован с правилами: в файле {_box_words(stored)}"
    native = native_page0_edges(form)
    if native is not None and item.holder == 0 and item.page == 0 and not hidden_page(item):
        return head + f", по правилам от края страницы 0 файла {native[0]}×{native[1]}: {_box_words(found)}"
    if form.tabs_area is not None and item.holder == 0 and not hidden_page(item):
        return head + (f"; предприятие поставит его на {_box_words(found)} — по правилам от области "
                       "страниц, а не по box")
    if form.tabs_area is not None and item.holder == 0:
        return head + (f", по правилам от области страниц {_box_words(found)}: пока страница {item.page} скрыта, "
                       "предприятие её не перекладывает (стоит по box); показанная страница формы «Сверху» "
                       "раскладывается по правилам от области")
    if item.from_area:
        return head + (f"; по модели предприятие поставит его на {_box_words(found)} — по правилам от видимой области панели, а не по "
                       "box: файл записан не по своим правилам (в предприятии такой элемент открылся по правилу, не по файлу)")
    return head + (f", по правилам от края родителя {_box_words(found)}; по чему предприятие поставит "
                   "такой элемент (по правилам, как у формы с закладками «Сверху», или по box), "
                   "не проверялось")


def _box_words(box):
    x, y, x2, y2 = box
    return f"{_num(x)};{_num(y)} {_num(x2 - x)}×{_num(y2 - y)}"


TABS_PAGE0_SHIFT = 19  # так платформа поднимает низ страницы 0


def _page0_edges(doc):
    """`(индекс направляющей, право, низ)` страницы 0 формы либо `None` (направляющих нет или не целые)."""
    block = edit.layout_block(edit.container(doc), need=False)
    guides = {}
    listed = block.get(edit.GUIDES) if isinstance(block, dict) else None
    for at, g in enumerate(listed if isinstance(listed, list) else ()):  # испорченный документ (не список) — «направляющих нет», не исключение
        if isinstance(g, dict) and g.get(edit.GUIDE_PAGE) == 0:
            guides.setdefault(g.get(edit.GUIDE_ORDER), (at, g))
    if 3 not in guides or 4 not in guides:
        return None
    edges = []
    for order in (3, 4):
        g = guides[order][1]
        if not (_int(g.get(edit.GUIDE_COORD)) and _int(g.get(edit.GUIDE_OFFSET))):
            return None
        edges.append(g[edit.GUIDE_COORD] + g[edit.GUIDE_OFFSET])
    return guides[4][0], edges[0], edges[1]


REPEATED_TOP_OFFSETS = (0, 19)  # правая направляющая страницы 0 700/0, нижняя 382/19 (край 401), правила к низу +19


def repeated_top(form):
    """Страница 0 записана так, как платформа пишет её при повторном «Сверху» после «Не отображать»: правая направляющая `W` с
    отступом 0, нижняя `H − 38` с отступом 19. Модель такие формы не знает: предприятие кладёт их элементы иначе.
    """
    if form.tabs_area is None:
        return False
    found = _page0_edges(form.doc)
    if found is None or found[1:] != (form.width, form.height - TABS_PAGE0_SHIFT):
        return False
    block = edit.layout_block(edit.container(form.doc), need=False)
    offsets = {}
    listed = block.get(edit.GUIDES) if isinstance(block, dict) else None
    for g in listed if isinstance(listed, list) else ():
        if isinstance(g, dict) and g.get(edit.GUIDE_PAGE) == 0 and g.get(edit.GUIDE_ORDER) in (3, 4):
            offsets.setdefault(g[edit.GUIDE_ORDER], g.get(edit.GUIDE_OFFSET))
    return (offsets.get(3), offsets.get(4)) == REPEATED_TOP_OFFSETS


REPEATED_TOP_WORDS = ("страница 0 формы «Сверху» записана как при повторном «Сверху» после «Не отображать» (правая направляющая 700/0, нижняя 382/19, правила "
                      "к низу +19; итог один при одной, двух и трёх страницах): предприятие кладёт такие формы иначе модели — "
                      "элементы у правого края на 16 уже, у нижнего на 19 ниже. Направляющие со второго «Сверху» не накапливаются, "
                      "а раскладка при каждом сжатии сдвигается дальше; область страниц (W−18, H−1) одним числом не описывается. "
                      "Причина в файле не названа, правило не выведено — расчёт раскладки по такой форме недостоверен")


def _from_area_elements(doc, height):
    """Имена элементов страницы 0, чьи правила к низу формы положены от области (W−2, H−20), а не от края `height`."""
    out = []
    for item in edit.container(doc).get(edit.ELEMENTS, {}).get(edit.ITEMS) or []:
        coords = item.get(edit.COORDS) if isinstance(item, dict) else None
        if not isinstance(coords, dict) or coords.get(edit.PAGE) != 0:
            continue
        for key, edge_key in ((edit.ANCHORS[0], edit.Y), (edit.ANCHORS[1], edit.HEIGHT)):
            for rname in edit.RULES:
                rule = (coords.get(key) or {}).get(rname)
                if isinstance(rule, dict) and rule.get(edit.RULE_OBJECT) == 0 \
                        and rule.get(edit.RULE_SIDE) == 1 and _int(rule.get(edit.RULE_OFFSET)) \
                        and _int(coords.get(edge_key)) \
                        and coords[edge_key] != height + rule[edit.RULE_OFFSET]:
                    name = (item.get(edit.NAME_BLOCK) or {}).get(edit.NAME)
                    if name not in out:
                        out.append(name)
    return out


def _page0_guide_offset(doc):
    """Отступ нижней направляющей страницы 0 (для слов) либо «—»."""
    for guide in edit.layout_block(edit.container(doc)).get(edit.GUIDES) or ():
        if isinstance(guide, dict) and guide.get(edit.GUIDE_PAGE) == 0 and guide.get(edit.GUIDE_ORDER) == 4:
            return guide.get(edit.GUIDE_OFFSET)
    return "—"


def tabs_page0_problems(doc, form):
    """`[(вид, адрес, текст)]` для формы с видимыми закладками «Сверху» и нижней командной панелью формы.

    * Край страницы 0 `(W или W−2, H−19)` — так её пишут платформа и `rewrite_page0_for_tabs`: `box` сверяется с правилами от
      краёв файла (`anchors.file_edges`); у родной формы замечаний нет.
    * Край `H` — страница записана как у формы без закладок: одно замечание; совет «`show_tabs=DontUse`, затем `Top`» даётся,
      только если все правила страницы 0 к низу формы положены от `H`.
    * Иной край — слова с фактической разницей, без совета.
    """
    if form.tabs_area is None or not page0_rewritten(doc):
        return []  # `nobar8` не переписана, `nobar33` и `bar8` — иначе: модель их не знает (`summary`)
    found = _page0_edges(doc)
    if found is None:
        return []
    at, right, bottom = found
    where = ("form", "container", "layout_holder", "layout_list", edit.GUIDES, at)
    kind = "страница 0 при закладках"
    if bottom == form.height - TABS_PAGE0_SHIFT and right in (form.width, form.width - 2):
        out, memo = [], {}
        for item in form.holders[0].children:
            if hidden_page(item) or item.page != 0:
                continue
            stored = item.stored or item.box
            want = rule_box(form, item, (right, bottom), memo)
            if any(abs(a - b) > BOX_TOLERANCE for a, b in zip(stored, want)):
                out.append(("box не согласован", item.path + (edit.COORDS,),
                            f"box «{item.qualified()}» не согласован с правилами от края страницы 0 "
                            f"({right}, {bottom}): в файле {_box_words(stored)}, по правилам "
                            f"{_box_words(want)}"))
        return out
    if bottom == form.height and _form_border_kind(doc) in FRAMES_TABS_MEASURED:
        return []
    if bottom == form.height and page0_edge(doc) is None:
        return [(kind, where,
                 f"вид нижнего края страницы 0 не из проверенных: нижняя направляющая стоит на {bottom} (H), отступ "
                 f"{(_page0_guide_offset(doc))}; при включении «Сверху» платформа пишет такую страницу иначе "
                 "(направляющие 700/0 и 420/0), и модель этого вида не знает — края файла от неё не сверялись, совета нет")]
    if bottom == form.height:
        text = (f"нижняя направляющая страницы 0 стоит на {bottom}, а конфигуратор при закладках "
                f"«Сверху» пишет {form.height - TABS_PAGE0_SHIFT} (высота {form.height} − "
                f"{TABS_PAGE0_SHIFT}): страница записана как у формы без закладок, и "
                "смещения её элементов к низу формы не пересчитаны — в предприятии низ встанет на 20 px "
                "выше конструктора, а не на 1")
        odd = _from_area_elements(doc, form.height)
        if odd:
            text += (f". Совета «show_tabs=DontUse, затем Top» нет: элементы {', '.join(odd)} положены "
                     "от области страниц (W−2, H−20), а не от H, и переключение закладок сдвинуло бы "
                     f"их ещё на {TABS_PAGE0_SHIFT}")
        else:
            text += (". Закладки включают заново: show_tabs=DontUse, затем show_tabs=Top "
                     "(операция пересчитает страницу 0)")
        return [(kind, where, text)]
    return [(kind, where,
             f"нижняя направляющая страницы 0 стоит на {bottom}: это не H ({form.height}, как у формы "
             f"без закладок) и не H−{TABS_PAGE0_SHIFT} ({form.height - TABS_PAGE0_SHIFT}, как пишет "
             f"конфигуратор при закладках «Сверху») — на {bottom - form.height} от H; как платформа "
             "пишет такую страницу, не проверялось, совета нет")]


def problems(doc):
    """Замечания раскладки: `[(вид, адрес, текст)]` — мёртвые правила, ранний предел роста формы, «к себе» в растягивающейся панели."""
    try:
        form = read(doc)
    except edit.EditError:
        return []
    coef = coefficients(form, hide=False)
    out = []
    by_item = {}
    for item, border, which, rule, why in dead_rules(form):
        by_item.setdefault(item.index, (item, []))[1].append((border, which, rule, why))
    for item, found in by_item.values():
        parts = "; ".join(f"{BORDERS[b]} — {which} {rule.text(item.index)}: {why}"
                          for b, which, rule, why in found)
        out.append(("мёртвое правило", item.path + (edit.COORDS,),
                    f"у «{item.qualified()}» правил без встречной записи "
                    f"{len(found)} ({parts}). В предприятии такая граница остаётся на месте, а "
                    "пересохранение формы записей не дописывает"))
    # Только у форм, где область страниц известна: у прочих `box` записала платформа, и замечание было бы шумом. Вместо сверки с областью — одна проверка: нижняя направляющая страницы 0 стоит на H−19.
    out += tabs_page0_problems(doc, form)
    for found in nested_area_mismatches(form):
        out.append(("область вложенных", found[0].path + (edit.COORDS,), nested_area_words(*found)))
    for found in wide_pages(form):
        out.append(("страница шире панели", found[0].path + (edit.COORDS,), wide_pages_words(*found)))
    for found in narrow_pages(form):
        out.append(("страница уже панели", found[0].path + (edit.COORDS,), narrow_pages_words(*found)))
    for found in scroll_panels(form):
        out.append(("прокрутка панели", found[0].path + (edit.COORDS,), scroll_panels_words(*found)))
    if doc.get("size_change") != "DontChange":
        limits = holder_limits(form, form.holders[0], coef)
        for axis in (0, 1):
            found = limits[(axis, 1)]
            if not found or found[0].whole >= EARLY:
                continue
            lim = found[0]
            base = form.width if axis == 0 else form.height
            # «Перестанет меняться» — остановка раскладки по пределу проверена; предел +0 (касание) тоже.
            out.append(("ранний предел", lim.a.path + (edit.COORDS,),
                        f"при росте окна по {('ширине', 'высоте')[axis]} больше чем "
                        f"на {lim.whole} px (до {base + lim.whole}) раскладка формы перестанет меняться "
                        f"— {lim.words(form, coef)}; дальше окно растёт пустым полем. Предел ближе {EARLY} px"
                        f"{_dead_tail(form, lim)}"))
    probe = None
    for holder in form.holders.values():
        if holder.item is None or coef.get(holder.item.index) is None:
            continue
        pc = coef[holder.item.index]
        for axis in (0, 1):
            span = (pc[3] - pc[2]) if axis == 0 else (pc[1] - pc[0])
            if span <= EPS:
                continue
            stuck = [child for child in holder.children
                     if child.type in STRETCHY and _to_self(form, child, axis)
                     and holder.edge(child.page)[axis]
                     - (child.box[2] if axis == 0 else child.box[3]) <= NEAR_EDGE]
            if not stuck:
                continue
            if probe is None:
                probe = Layout(form, form.width + PANEL_PROBE, form.height + PANEL_PROBE,
                               hide=False)
            share = panel_share(probe, holder.item, axis)
            if share <= EPS:
                continue  # от своего родителя панель растягивается, а от окна — нет
            names = ", ".join(f"«{child.label()}»" for child in stuck[:5]) + \
                (f" и ещё {len(stuck) - 5}" if len(stuck) > 5 else "")
            out.append(("к себе в панели", holder.item.path + (edit.COORDS,),
                        f"панель «{holder.item.qualified()}» растягивается по "
                        f"{('ширине', 'высоте')[axis]} (на {_share(share)} прироста окна), а у "
                        f"её дальнего края «к себе» стоят {names}: за растягивающейся панелью они не "
                        "пойдут, а при сжатии панели их закроет полоса прокрутки"))
    return out


def panel_share(lay, item, axis):
    """На сколько пикселей панель растягивается по оси на пиксель роста окна — по раскладке `lay` с остановкой всех родителей по цепочке. Ноль — панель не растягивается."""
    grown = lay.growth[0][axis]
    if grown <= EPS:
        return 0.0
    x, y, x2, y2 = lay.boxes[item.index]
    ox, oy, ox2, oy2 = item.box
    extent = ((x2 - x) - (ox2 - ox)) if axis == 0 else ((y2 - y) - (oy2 - oy))
    return extent / grown


def _share(value):
    """Доля словами: два знака, а у доли меньше сотой — три."""
    return f"{value:.3f}".replace(".", ",") if value < 0.005 else \
        f"{value:.2f}".replace(".", ",")


def _dead_tail(form, lim):
    tail = []
    for who in (lim.a, lim.b):
        if who is None:
            continue
        dead = [(b, r) for b, pair in enumerate(who.rules) for r in pair
                if r is not None and rule_state(form, who, b, r)[0] == DEAD]
        if dead:
            tail.append(f"у «{who.label()}» мёртвые правила ({len(dead)}) — он стоит потому, "
                        "что им нет встречной записи")
    return ("; " + "; ".join(tail)) if tail else ""


def _to_self(form, item, axis):
    """По оси нет ни одного живого правила к родителю или соседу — только «к себе» или ничего."""
    for border in ((2, 3) if axis == 0 else (0, 1)):
        for rule in item.rules[border]:
            if rule is None or rule.obj == item.index:
                continue
            if rule_state(form, item, border, rule)[0] != DEAD:
                return False
    return True


# ── Отчёт команды `frm_json.py layout` ──

def _size_words(lo, hi):
    left = "—" if lo is None else str(lo)
    right = "без предела" if hi is None else str(hi)
    return f"{left}…{right}"


def _coupled_words(form, coef, inversion=True, order="wh", at=None):
    """Оговорка к диапазону «следует за окном»: предел второй оси зависит от фактического роста по первой. `at` — рост по первой
    оси, при котором спрашивают (отказ `relayout`). Пусто, когда предел второй оси от него не зависит.
    """
    top = form.holders[0]
    alone = bounds(holder_limits(form, top, coef, inversion=inversion))
    first = 0 if order == "wh" else 1
    second = 1 - first
    base = (form.width, form.height)
    if at is not None:
        probes = [at]
    else:
        probes = sorted({d for d in (*alone[first], 25, 50, 100, 200) if not math.isinf(d) and d > 0})
    out = []
    for d in probes:
        if d == 0:
            continue
        other = [0.0, 0.0]
        other[first] = d
        got = bounds(holder_limits(form, top, coef, other=tuple(other), inversion=inversion))[second]
        if got != alone[second]:
            lo, hi = (None if math.isinf(v) else base[second] + v for v in got)
            out.append(f"при {AXES_AT[first]} {base[first] + d} предел {AXES_OF[second]}: {_size_words(lo, hi)}")
    if not out:
        return ""
    return ("диапазон считает оси порознь, а предел второй оси зависит от фактического роста по первой "
            f"(порядок «{AXES[first]}, потом {AXES[second]}»): " + "; ".join(out[:3]))


def limit_line(form, coef, axis, direction, lim):
    """Строка причины предела — слово в слово та, что печатает `layout`; её же берёт `render --sizes`."""
    return f"{AXES[axis]}, {'рост' if direction > 0 else 'сжатие'}: {lim.whole:+d} — {lim.kind}: {lim.words(form, coef)}"
