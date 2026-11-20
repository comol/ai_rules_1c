"""Направляющие края формы: дальние направляющие и их исправление (`normalize_guides`).

Направляющие края — правая (`u4` = 3) и нижняя (`u4` = 4) направляющие страницы формы: координата `u1` и отступ `u7` от края формы,
«край = координата + отступ». У формы платформы отступ правой направляющей 8 (6 при Рамке «Одинарная»; у страницы 0 при закладках «Сверху» — 0), нижней — 8, 19 или от 25 до 37 (нижняя командная панель; чаще всего 33). При смене
размера формы палитрой или мышью платформа двигает такую направляющую вместе с краем: координата += Δ, отступ прежний.

**Дальняя направляющая** — отступ больше `FAR_MARGIN[номер края]` px (правая 20, нижняя 40): позиция не у края формы. Такая получается, если размер формы сменили записью в файл,
оставив координату прежней (платформа при открытии пересчитывает отступ, а не координату). На образце разделителей с дальними направляющими
(472/128 и 470/50 при форме 600×520) окно +200 по ширине дало рост полей +204, горизонтальную прокрутку, и после возврата окна раскладка не
сжалась («залипание»); с направляющими у краёв (592/8 и 512/8) при трёх способах растяжения прокрутки нет, рост равен приросту окна, возврат
точный. У настоящих форм дальние направляющие редки. Предупреждение — `far_words`, исправление — операция
`normalize_guides`.

**Верхняя и нижняя направляющие страницы 0 у края.** Без панели у края они стоят так, как их ставит команда «Удалить все выравнивающие линии» (верхняя 8/0, нижняя
`высота − 8`/8). Конфигуратор при удалении панели направляющих не двигает, а элемент ниже нижней направляющей в предприятии выносит раскладку за край при ходе разделителя
у размера окна из файла. Поэтому: `remove_element` панели у края ставит направляющую (`bar_removed`), конец перечня операций уводит нижнюю направляющую под элемент, который
перечень поставил ниже неё (`keep_bottom`), `normalize_guides` приводит обе (`edge_defaults`), диагностика называет такой элемент (`below_words`).
"""
from . import edit
from .edit.base import EditError

PANEL_TRACE_MIN = 25  # отступ нижней направляющей от края не меньше стольких px — след убранной нижней панели (платформа пишет 25…37)
PANEL_GAP = 8        # платформа ставит верхнюю (нижнюю) направляющую в 8 px от командной панели у края: 33 при панели высотой 25
FAR_MARGIN = {3: 20, 4: 40}   # отступ направляющей края больше стольких px — дальняя (правая: у 4 990 форм из 4 993 он не больше 20; нижняя: платформа пишет до 37)
EDGE_MARGIN = 8      # отступ направляющих у края формы платформы
BORDER_MARGIN = 6    # то же при Рамке «Одинарная» (платформа сдвинула 8 → 6)
TOP_TRACE_MIN = 24   # верхняя направляющая не ниже стольких px + 1 — след убранной панели (панель 23…25 + 8 ≥ 31); меньшие значения платформа пишет сама
TOP_DEFAULT = 8      # верхняя направляющая страницы 0 без панели у верхнего края: координата 8, отступ 0 («Удалить все выравнивающие линии» ставит так)
BOTTOM_DEFAULT = 8   # нижняя без панели у нижнего края: высота формы − 8, отступ 8
ORDERS = {3: "правая", 4: "нижняя"}
PANEL_ORDERS = {2: "верхняя", 4: "нижняя"}


def _int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def edge_guides(doc):
    """Направляющие края формы с целым отступом и координатой: `[(индекс, словарь)]`; пусто, если блока нет или он испорчен."""
    try:
        block = edit.layout_block(edit.container(doc), need=False) if isinstance(doc, dict) else None
    except EditError:      # у документа нет контейнера формы: направляющих нет
        return []
    listed = block.get(edit.GUIDES) if isinstance(block, dict) else None
    return [(at, guide) for at, guide in enumerate(listed if isinstance(listed, list) else ())
            if isinstance(guide, dict) and guide.get(edit.GUIDE_ORDER) in ORDERS
            and _int(guide.get(edit.GUIDE_COORD)) and _int(guide.get(edit.GUIDE_OFFSET))]


def far_guides(doc):
    """Дальние направляющие края: `[(страница, номер края, координата, отступ)]`."""
    return [(guide.get(edit.GUIDE_PAGE), guide[edit.GUIDE_ORDER], guide[edit.GUIDE_COORD], guide[edit.GUIDE_OFFSET])
            for _at, guide in edge_guides(doc) if guide[edit.GUIDE_OFFSET] > FAR_MARGIN[guide[edit.GUIDE_ORDER]]]


def far_words(doc):
    """Предупреждение о дальних направляющих края — строки отчёта; пусто, когда их нет."""
    found = far_guides(doc)
    if not found:
        return []
    named = "; ".join(f"{ORDERS[order]} направляющая {'страницы ' + str(page) + ' ' if page else ''}в {coord} (отступ {margin})"
                      for page, order, coord, margin in found)
    return [f"   предупреждение: дальняя направляющая края: позиция не у края формы — {named}; в предприятии раскладка может «залипать» после "
            "растяжения окна (полоса прокрутки, после возврата окна раскладка не сжимается; у направляющих с отступом 8 так не бывает). "
            "Исправляет операция `normalize_guides` (направляющие к краю, элементы не двигаются)"]


def _bars_at_edges(doc):
    """Командные панели родителя-формы, страницы 0, видимые, на всю ширину формы и касающиеся верхнего или нижнего края:
    `{2: [(имя, низ панели)], 4: [(имя, верх панели)]}` (2 — верхняя направляющая, 4 — нижняя) и размер формы `(ширина, высота)`.
    Форма с закладками «Сверху» и документ без размера — пусто: у них направляющие страницы 0 другого рода."""
    from . import anchors
    out = {2: [], 4: []}
    try:
        container = edit.container(doc)
        block = doc["form"]
        width, height = block.get("width"), block.get("height")
        if not (_int(width) and _int(height)) or anchors.tabs_area(doc) is not None:
            return out, None
        items = (container.get(edit.ELEMENTS) or {}).get(edit.ITEMS) or []
        if not isinstance(items, list):
            return out, None
    except (EditError, KeyError, AttributeError, TypeError):
        return out, None
    for element in items:
        coords = element.get(edit.COORDS) if isinstance(element, dict) else None
        if not isinstance(element, dict) or element.get("type") != "CommandBar" or not isinstance(coords, dict) or coords.get("visible") is False:
            continue
        if coords.get(edit.PAGE, 0) != 0:
            continue
        x, y, right, bottom = (coords.get(k) for k in (edit.X, edit.Y, edit.WIDTH, edit.HEIGHT))
        if not all(_int(v) for v in (x, y, right, bottom)) or x > 1 or right < width - 1:
            continue
        names = element.get(edit.NAME_BLOCK)
        name = names.get(edit.NAME) if isinstance(names, dict) else None
        if y <= 1 and bottom > y:
            out[2].append((name, bottom))
        if bottom >= height - 1 and bottom > y:
            out[4].append((name, y))
    return out, (width, height)


def panel_guides(doc):
    """Направляющие страницы 0 внутри командной панели у края: `[(номер края, координата, имя панели, граница панели, нужная координата)]`.

    Верхняя направляющая (`u4` = 2) внутри верхней панели, если лежит ниже края формы и выше низа панели; платформа ставит её в `PANEL_GAP`
    под панель (панель 25 → 33). Нижняя (`u4` = 4) — зеркально: ниже верха нижней панели и выше нижнего края; платформа — на `PANEL_GAP` над
    панелью (отступ 33 при панели 25). Направляющая у самого края формы (координата 0 сверху, высота формы снизу) не считается: так платформа
    пишет 134 формы корпуса с нижней и 12 с верхней панелью. Из 4 992 форм корпуса направляющая внутри панели у 9 форм (7 нижних направляющих, 2 верхних).
    """
    bars, size = _bars_at_edges(doc)
    if size is None:
        return []
    found = []
    for _at, guide in _all_guides(doc):
        order, coord = guide.get(edit.GUIDE_ORDER), guide.get(edit.GUIDE_COORD)
        if guide.get(edit.GUIDE_PAGE, 0) != 0 or not _int(coord):
            continue
        if order == 2 and bars[2]:
            name, edge = max(bars[2], key=lambda b: b[1])
            if 0 < coord < edge:
                found.append((2, coord, name, edge, edge + PANEL_GAP))
        if order == 4 and bars[4]:
            name, edge = min(bars[4], key=lambda b: b[1])
            if edge < coord < size[1]:
                found.append((4, coord, name, edge, edge - PANEL_GAP))
    return found


def _all_guides(doc):
    """Все направляющие блока раскладки родителя-формы с целой координатой: `[(индекс, словарь)]`."""
    try:
        block = edit.layout_block(edit.container(doc), need=False) if isinstance(doc, dict) else None
    except EditError:
        return []
    listed = block.get(edit.GUIDES) if isinstance(block, dict) else None
    return [(at, g) for at, g in enumerate(listed if isinstance(listed, list) else ()) if isinstance(g, dict)]


def panel_words(doc):
    """Предупреждение о направляющих внутри панелей у края — строки отчёта; пусто, когда их нет."""
    found = panel_guides(doc)
    if not found:
        return []
    named = "; ".join(f"{'верхняя' if order == 2 else 'нижняя'} направляющая в {coord} внутри панели «{name}» "
                      f"({'до' if order == 2 else 'от'} {edge}), платформа ставит в {want}"
                      for order, coord, name, edge, want in found)
    return ["   предупреждение: направляющая формы внутри командной панели у края — " + named + "; при растяжении окна возможна полоса прокрутки формы "
            "(опыт в предприятии: из четырёх форм с такими направляющими и панелями у краёв три получили полосу прокрутки при каждом растяжении "
            "(у формы с одной верхней панелью — горизонтальную), четвёртая — в одном заходе из двух, и раскладка после возврата окна не вернулась; "
            "та же форма с направляющими 33/H−33 полос не дала, форма без панелей — тоже; размер окна, при котором полоса появится, не выведен: она шла уже "
            "на +45×+23; причина не выяснена, правило выведено из совпадения). Исправляет операция `normalize_guides` (направляющие к панелям, элементы не двигаются)"]


def fit_panel(doc, element):
    """Для `add_element`: поставленная командная панель родителя-формы у края стала поверх направляющей страницы 0 — направляющая уходит на
    `PANEL_GAP` от панели, как у платформы. Направляющие вне панели не трогаются. Возвращает слова операции или `""`."""
    names = element.get(edit.NAME_BLOCK)
    name = names.get(edit.NAME) if isinstance(names, dict) else None
    moved = []
    for order, coord, who, _edge, want in panel_guides(doc):
        if who != name:
            continue
        for _at, guide in _all_guides(doc):
            if guide.get(edit.GUIDE_ORDER) == order and guide.get(edit.GUIDE_PAGE, 0) == 0 and guide.get(edit.GUIDE_COORD) == coord:
                height = doc["form"]["height"]
                guide[edit.GUIDE_COORD] = want
                if order == 4:
                    guide[edit.GUIDE_OFFSET] = height - want
                moved.append(f"{'верхняя' if order == 2 else 'нижняя'} направляющая {coord} → {want}")
                break
    if not moved:
        return ""
    return ("направляющие формы стояли внутри панели и перенесены от неё на 8 px, как ставит платформа (" + "; ".join(moved)
            + "): иначе при растяжении окна форма получала полосу прокрутки (проверено одним опытом в предприятии, вне него не проверялось)")


def _page0(doc):
    """Стандартные направляющие страницы 0 по номерам края: `{номер: словарь}` (первая из совпавших; добавленные человеком линии имеют иной номер)."""
    out = {}
    for _at, guide in _all_guides(doc):
        if (guide.get(edit.GUIDE_PAGE, 0) == 0 and guide.get(edit.GUIDE_ORDER) in (2, 3, 4)
                and _int(guide.get(edit.GUIDE_COORD)) and _int(guide.get(edit.GUIDE_OFFSET))):
            out.setdefault(guide[edit.GUIDE_ORDER], guide)
    return out


def _top_items(doc):
    """Элементы родителя-формы списком; не список (испорченный документ) — пусто."""
    try:
        items = (edit.container(doc).get(edit.ELEMENTS) or {}).get(edit.ITEMS) or []
    except (EditError, AttributeError, TypeError):
        return []
    return [e for e in items if isinstance(e, dict)] if isinstance(items, list) else []


def skip_reason(doc):
    """Почему новые шаги (положение по умолчанию верхней и нижней направляющих, ход за удалённой панелью, конец перечня) форму не трогают: `""`, если трогают.
    Закладки «Сверху» (направляющие страницы 0 другого рода), Рамка (у платформы край H−2, положение по умолчанию не проверялось) и документ без размера."""
    from . import anchors
    try:
        block = doc["form"]
        if not (_int(block.get("width")) and _int(block.get("height"))):
            return "нет размера формы"
        if anchors.tabs_area(doc) is not None:
            return "закладки «Сверху»"
    except (KeyError, AttributeError, TypeError, EditError):
        return "нет размера формы"
    return "рамка" if _border(doc) else ""


def _bars_any(doc):
    """Все командные панели родителя-формы на странице 0, любой ширины и видимости: `[(имя, лево, верх, низ)]`."""
    out = []
    for element in _top_items(doc):
        coords = element.get(edit.COORDS)
        if element.get("type") != "CommandBar" or not isinstance(coords, dict) or coords.get(edit.PAGE, 0) != 0:
            continue
        x, y, bottom = coords.get(edit.X), coords.get(edit.Y), coords.get(edit.HEIGHT)
        if not (_int(x) and _int(y) and _int(bottom) and bottom > y):
            continue
        names = element.get(edit.NAME_BLOCK)
        out.append(((names.get(edit.NAME) if isinstance(names, dict) else None), x, y, bottom))
    return out


def _has_panel(doc, order, coord, height):
    """Направляющая `order` (2 верхняя, 4 нижняя) страницы 0 стоит у панели: панель любой ширины и видимости касается верхнего края формы (нижняя — стоит не дальше
    `PANEL_GAP` от нижнего) либо начинается у левого края формы и лежит выше (ниже) направляющей не дальше `PANEL_GAP` — платформа ставит направляющую в 8 px от панели,
    в том числе от частичной. Панель таблицы (она над таблицей, правее левого края и ниже верхнего) панелью формы не считается."""
    for _name, left, top, bottom in _bars_any(doc):
        if order == 2 and (top <= 1 or (left <= 1 and 0 < coord - bottom <= PANEL_GAP)):
            return True
        if order == 4 and (bottom >= height - PANEL_GAP or (left <= 1 and 0 < top - coord <= PANEL_GAP)):
            return True
    return False


def _size(doc):
    try:
        width, height = doc["form"].get("width"), doc["form"].get("height")
    except (KeyError, AttributeError, TypeError):
        return None
    return (width, height) if _int(width) and _int(height) else None


def _edge_presence(doc):
    """Какие панели касаются верхнего и нижнего краёв страницы 0 (любой ширины и видимости): `{2: bool, 4: bool}`."""
    size = _size(doc)
    if size is None:
        return {2: False, 4: False}
    bars = _bars_any(doc)
    return {2: any(top <= 1 for _n, _l, top, _b in bars), 4: any(bottom >= size[1] - 1 for _n, _l, _t, bottom in bars)}


def _flow_items(doc):
    """Элементы родителя-формы на странице 0 независимо от видимости, кроме командных панелей: `[(ключ, имя, низ)]`. Панели не считаются: нижняя лежит под нижней
    направляющей по замыслу."""
    out = []
    for at, element in enumerate(_top_items(doc)):
        coords = element.get(edit.COORDS)
        if not isinstance(coords, dict) or element.get("type") == "CommandBar" or coords.get(edit.PAGE, 0) != 0:
            continue
        bottom = coords.get(edit.HEIGHT)
        if not _int(bottom):
            continue
        names = element.get(edit.NAME_BLOCK)
        name = names.get(edit.NAME) if isinstance(names, dict) else None
        out.append((element.get(edit.INDEX, ("at", at)), name or "без имени", bottom))
    return out


def below_bottom(doc):
    """Элементы страницы 0 ниже нижней направляющей: `[(ключ, имя, низ, на сколько px ниже)]`. Только у формы без нижней панели (любой ширины и видимости, у края
    или в 8 px под направляющей), без закладок «Сверху» и без Рамки; командные панели не считаются."""
    guide = _page0(doc).get(4)
    if skip_reason(doc) or guide is None:
        return []
    coord = guide[edit.GUIDE_COORD]
    if _has_panel(doc, 4, coord, _size(doc)[1]):
        return []
    return [(key, name, bottom, bottom - coord) for key, name, bottom in _flow_items(doc) if bottom > coord]


def below_words(doc):
    """Предупреждение об элементах ниже нижней направляющей страницы 0 — строки отчёта; пусто, когда таких нет."""
    found = below_bottom(doc)
    if not found:
        return []
    height = _size(doc)[1]
    named = "; ".join(f"«{name}» на {over} px (низ {bottom}{', ниже края формы' if bottom > height else ''})" for _key, name, bottom, over in found[:5])
    if len(found) > 5:
        named += f"; и ещё {len(found) - 5}"
    guide = _page0(doc)[4]
    return [f"   предупреждение: элемент ниже нижней направляющей страницы 0 ({guide[edit.GUIDE_COORD]}/{guide[edit.GUIDE_OFFSET]}) — {named}: конфигуратор так не ставит "
            "(у размера окна из файла ход разделителя выносит раскладку за край: таблицы уходят за низ клиентской области, появляется вертикальная полоса "
            "прокрутки формы). Исправляет операция `normalize_guides` (нижняя направляющая под элементы, элементы не двигаются)"]


def _bottom_target(doc, height):
    """Куда ставить нижнюю направляющую страницы 0 без панели: `height − BOTTOM_DEFAULT`, а если элементы ниже — под самый нижний из них. Элемент ниже края
    формы не считается: после смены размера платформа держит направляющую у края (`высота − 8`), а не под вылезшим элементом."""
    low = max((bottom for _key, _name, bottom in _flow_items(doc) if bottom <= height), default=0)
    return min(height, max(height - BOTTOM_DEFAULT, low))


def _put(guide, coord, height=None):
    was = f"{guide[edit.GUIDE_COORD]}/{guide[edit.GUIDE_OFFSET]}"
    guide[edit.GUIDE_COORD] = coord
    guide[edit.GUIDE_OFFSET] = 0 if height is None else height - coord
    return was, f"{coord}/{guide[edit.GUIDE_OFFSET]}"


def _bar_around(doc, coord):
    """Имя командной панели страницы 0 (любая ширина, видимость и место), внутри которой лежала бы направляющая в `coord` (верх панели < координата < низ), или `None`."""
    for name, _left, top, bottom in _bars_any(doc):
        if top < coord < bottom:
            return name or "без имени"
    return None


def _top_is_trace(doc, coord):
    """Верхняя направляющая — след убранной панели: координата больше `TOP_TRACE_MIN`, а над ней пусто — нет элемента страницы 0, чей верх выше координаты (направляющая
    не проходит через элемент и не лежит под ним), и нет командной панели целиком выше. Малые значения и направляющие внутри содержимого — не след, их `normalize_guides`
    не двигает."""
    if coord <= TOP_TRACE_MIN:
        return False
    for element in _top_items(doc):
        coords = element.get(edit.COORDS)
        if not isinstance(coords, dict) or coords.get(edit.PAGE, 0) != 0:
            continue
        top, bottom = coords.get(edit.Y), coords.get(edit.HEIGHT)
        if element.get("type") == "CommandBar":
            if _int(bottom) and bottom <= coord:
                return False
        elif _int(top) and top < coord:
            return False
    return True


def _bottom_is_defect(doc, coord, height):
    """Нижняя направляющая страницы 0 без панели нуждается в правке: элемент страницы 0 (не командная панель, любой видимости) стоит ниже неё и в пределах формы
    (`coord < низ ≤ height`) либо она след убранной нижней панели (отступ от края от `PANEL_TRACE_MIN` до `FAR_MARGIN[4]`). Направляющая у самого края, малые отступы и
    направляющая ниже края формы — то, что платформа пишет сама, и без опыта не двигаются."""
    if PANEL_TRACE_MIN <= height - coord <= FAR_MARGIN[4]:
        return True
    return any(coord < bottom <= height for _key, _name, bottom in _flow_items(doc))


def edge_defaults(doc, skip=(), notes=None):
    """Верхняя и нижняя направляющие страницы 0 без панели у своего края — в положение «Удалить все выравнивающие линии». Верхняя 8/0 — только когда она след убранной
    панели (`_top_is_trace`); нижняя `высота − 8`/8 (ниже самого нижнего элемента, если он ниже) — только когда ниже неё есть элемент или она след убранной нижней
    панели (`_bottom_is_defect`). Панель у края (любой ширины и видимости, у самого края либо в 8 px
    от направляющей) — направляющая остаётся от панели. Положение по умолчанию не ставится внутрь любой командной панели страницы 0 (любая ширина, видимость и место):
    направляющая не меняется, а панель называется в `notes`. Закладки «Сверху», Рамка и документ без размера не трогаются (`skip_reason`).
    `skip` — направляющие, которые операция уже поставила сама (дальняя нижняя с отступом, названным вызывающим): их положение не пересматривается.
    Возвращает `[слова]` о сдвинутых."""
    if skip_reason(doc):
        return []
    size = _size(doc)
    notes = notes if notes is not None else []
    found = {order: guide for order, guide in _page0(doc).items() if not any(guide is other for other in skip)}
    top, bottom, moved = found.get(2), found.get(4), []
    if top is not None and not _has_panel(doc, 2, top[edit.GUIDE_COORD], size[1]) and _top_is_trace(doc, top[edit.GUIDE_COORD]) \
            and (top[edit.GUIDE_COORD], top[edit.GUIDE_OFFSET]) != (TOP_DEFAULT, 0):
        around = _bar_around(doc, TOP_DEFAULT)
        if around:
            notes.append(f"верхняя {top[edit.GUIDE_COORD]}/{top[edit.GUIDE_OFFSET]} не тронута: {TOP_DEFAULT} попало бы внутрь панели «{around}»")
        else:
            was, now = _put(top, TOP_DEFAULT)
            moved.append(f"верхняя {was} → {now}")
    if bottom is not None and not _has_panel(doc, 4, bottom[edit.GUIDE_COORD], size[1]) and _bottom_is_defect(doc, bottom[edit.GUIDE_COORD], size[1]):
        want = _bottom_target(doc, size[1])
        if (bottom[edit.GUIDE_COORD], bottom[edit.GUIDE_OFFSET]) != (want, size[1] - want):
            around = _bar_around(doc, want)
            if around:
                notes.append(f"нижняя {bottom[edit.GUIDE_COORD]}/{bottom[edit.GUIDE_OFFSET]} не тронута: {want} попало бы внутрь панели «{around}»")
            else:
                was, now = _put(bottom, want, size[1])
                moved.append(f"нижняя {was} → {now}")
    return moved


def below_snapshot(doc):
    """Элементы ниже нижней направляющей: `{ключ: на сколько px}` — `keep_bottom` двигает направляющую только из-за нового или углубившегося."""
    return {key: over for key, _name, _bottom, over in below_bottom(doc)}


def keep_bottom(doc, before):
    """Конец перечня операций: элемент, оказавшийся ниже нижней направляющей страницы 0 по вине перечня (его не было ниже или он ушёл ниже), — нижняя направляющая уходит
    под элементы (`высота − 8`/8 или под самый нижний). Прежние нарушения формы не трогаются; элемент ниже края формы направляющую не двигает. Верхняя не двигается: выше
    неё конфигуратор элемент ставит свободно. Возвращает слова или `""`."""
    size = _size(doc)
    if size is None:
        return ""
    grew = [(name, over) for key, name, bottom, over in below_bottom(doc) if over > before.get(key, 0) and bottom <= size[1]]
    if not grew:
        return ""
    guide = _page0(doc)[4]
    want = _bottom_target(doc, size[1])
    if want <= guide[edit.GUIDE_COORD]:
        return ""
    was, now_ = _put(guide, want, size[1])
    return (f"нижняя направляющая страницы 0 {was} → {now_}: " + ", ".join(f"«{n}»" for n, _o in grew[:5]) + (f" и ещё {len(grew) - 5}" if len(grew) > 5 else "")
            + " оказались бы ниже неё; ниже нижней направляющей конфигуратор элементы не ставит, а в предприятии при ходе разделителя раскладка выходит за край")


def _bar_gone(doc, order):
    """Панель у края `order` убрана: направляющая встаёт как после «Удалить все выравнивающие линии» (верхняя 8/0, нижняя `высота − 8`/8), если у неё нет другой панели.
    Возвращает слова или `""`."""
    if skip_reason(doc):
        return ""
    size = _size(doc)
    guide = _page0(doc).get(order)
    if guide is None or _has_panel(doc, order, guide[edit.GUIDE_COORD], size[1]):
        return ""
    want = TOP_DEFAULT if order == 2 else _bottom_target(doc, size[1])
    around = _bar_around(doc, want)
    if around:
        return f"{'верхняя' if order == 2 else 'нижняя'} направляющая страницы 0 {guide[edit.GUIDE_COORD]}/{guide[edit.GUIDE_OFFSET]} не тронута: {want} попало бы внутрь панели «{around}»"
    if order == 2:
        was, now = _put(guide, TOP_DEFAULT)
    else:
        was, now = _put(guide, want, size[1])
    return "" if was == now else f"{'верхняя' if order == 2 else 'нижняя'} направляющая страницы 0 {was} → {now}"


class Watch:
    """Слежение за перечнем операций (`edit.apply`): какие операции убрали панель у края и какая первой поставила элемент ниже нижней направляющей.
    Направляющие двигаются в конце перечня: панель убрали и поставили новую — направляющая остаётся; слова ложатся в строку той операции, которая причина."""

    def __init__(self, doc):
        self.before = below_snapshot(doc)
        self.present = _edge_presence(doc)
        self.lost = {}
        self.culprit = None

    def step(self, doc, number):
        now = _edge_presence(doc)
        for order in (2, 4):
            if self.present[order] and not now[order]:
                self.lost[order] = number
            elif now[order]:
                self.lost.pop(order, None)
        self.present = now
        if self.culprit is None and any(over > self.before.get(key, 0) for key, over in below_snapshot(doc).items()):
            self.culprit = number

    def finish(self, doc, log):
        """Двигает направляющие и дописывает слова в строки `log` (номер операции − 1; без причины — в последнюю)."""
        if not log:
            return
        gone = {}
        for order, number in sorted(self.lost.items()):
            said = _bar_gone(doc, order)
            if said:
                gone.setdefault(number, []).append(said)
        for number, parts in gone.items():
            log[number - 1] += "; панели у края не осталось, направляющая встала как после «Удалить все выравнивающие линии» в Конфигураторе: " + "; ".join(parts)
        kept = keep_bottom(doc, self.before)
        if kept:
            log[(self.culprit or len(log)) - 1] += "; " + kept


def normalize_guides(doc, margin=None, unverified=False):
    """Дальние направляющие края — к краю формы: край (координата + отступ) прежний, отступ — `margin` (умолчание 8, при Рамке 6), координата —
    край минус отступ. Направляющие с отступом не больше `FAR_MARGIN` своего края не трогаются, элементы и привязки тоже.

    Вторая часть — **направляющие внутри командных панелей у краёв** (`panel_guides`): верхняя уходит на `PANEL_GAP` под верхнюю панель, нижняя —
    на `PANEL_GAP` над нижней (панель 25 → 33 и H−33, как у платформы); в опыте в предприятии это сняло полосу прокрутки при растяжении окна.

    Третья часть — **верхняя и нижняя направляющие страницы 0 без панели у своего края** (`edge_defaults`): 8/0 и `высота − 8`/8 (под самый нижний элемент, если он ниже).

    `margin` — целое от 0 до 20; большее число — это снова дальняя правая направляющая, под `unverified`. Возвращает отчёт.
    """
    if margin is None:
        margin = BORDER_MARGIN if _border(doc) else EDGE_MARGIN
    elif not _int(margin) or margin < 0:
        raise EditError(f"margin: целое неотрицательное число (отступ направляющей от края формы), а пришло {margin!r}")
    elif margin > FAR_MARGIN[3] and not unverified:
        raise EditError(f"margin {margin}: отступ больше {FAR_MARGIN[3]} — это снова дальняя направляющая (`far_words`); платформа пишет 8 "
                        f"(6 при Рамке). Позвать всё же можно — unverified=True")
    moved, placed = [], []
    for _at, guide in edge_guides(doc):
        was = guide[edit.GUIDE_OFFSET]
        if was <= FAR_MARGIN[guide[edit.GUIDE_ORDER]]:
            continue
        edge = guide[edit.GUIDE_COORD] + was
        placed.append(guide)
        moved.append(f"{ORDERS[guide[edit.GUIDE_ORDER]]} страницы {guide.get(edit.GUIDE_PAGE)}: {guide[edit.GUIDE_COORD]}/{was} → {edge - margin}/{margin}")
        guide[edit.GUIDE_COORD] = edge - margin
        guide[edit.GUIDE_OFFSET] = margin
    panel = []
    for order, coord, name, _edge, want in panel_guides(doc):
        for _at, guide in _all_guides(doc):
            if guide.get(edit.GUIDE_ORDER) == order and guide.get(edit.GUIDE_PAGE, 0) == 0 and guide.get(edit.GUIDE_COORD) == coord:
                guide[edit.GUIDE_COORD] = want
                if order == 4:
                    guide[edit.GUIDE_OFFSET] = doc["form"]["height"] - want
                panel.append(f"{PANEL_ORDERS[order]} направляющая {coord} → {want} (панель «{name}»)")
                break
    blocked = []
    edges = edge_defaults(doc, skip=placed, notes=blocked)
    skipped = skip_reason(doc)
    if not moved and not panel and not edges:
        return ("; ".join(blocked) + "; " if blocked else "") + (f"normalize_guides: дальних направляющих края (отступ правой больше {FAR_MARGIN[3]}, нижней больше {FAR_MARGIN[4]}) нет, форма не изменена; "
                "направляющих внутри командных панелей у краёв тоже нет; "
                + (f"верхняя и нижняя направляющие страницы 0 не проверялись: {skipped} (положение по умолчанию у такой формы не проверялось)" if skipped else
                   "верхняя и нижняя направляющие страницы 0 без панели у края уже в положении по умолчанию (8/0 и высота − 8/8)"))
    said = []
    if moved:
        said.append(f"normalize_guides: направляющих края перенесено к краю формы {len(moved)} (край прежний, отступ {margin}): " + "; ".join(moved)
                    + "; элементы и привязки не тронуты. Форма с направляющими у краёв в предприятии проверена: поля растут ровно на прирост окна, "
                      "после возврата окна раскладка прежняя"
                    + ("; отступ не 8 (в том числе 6 при Рамке) в предприятии не проверялся" if margin != EDGE_MARGIN else ""))
    if panel:
        said.append(("normalize_guides: " if not moved else "") + f"направляющих внутри панелей у краёв перенесено от панели на {PANEL_GAP} px, как ставит платформа, {len(panel)}: "
                    + "; ".join(panel) + "; элементы и привязки не тронуты. Форма с направляющими 33/H−33 при растяжении окна полос не дала, с направляющими "
                      "внутри панелей — давала (один опыт в предприятии)")
    if edges:
        said.append(("normalize_guides: " if not said else "") + "направляющие страницы 0 без панели у края поставлены как после «Удалить все выравнивающие линии» в Конфигураторе ("
                    + "; ".join(edges) + "); элементы и привязки не тронуты. Форма с такими направляющими в предприятии при ходе разделителя у размера окна из файла "
                      "раскладку за край не выносит (опыт на форме, где нижняя направляющая стояла выше низа таблиц, — выносила)")
    return "; ".join(said) + ("; " + "; ".join(blocked) if blocked else "")


def _border(doc):
    """Рамка формы не «Нет»: `border_type` блока рамки; нечитаемое — без рамки."""
    from .edit.pages import _form_border_type, FORM_NO_BORDER
    value = _form_border_type(doc)
    return value not in (None, FORM_NO_BORDER)
