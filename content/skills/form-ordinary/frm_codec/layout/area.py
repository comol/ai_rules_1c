"""Область страницы панели, закладки, край страницы 0 и рамка формы: то, что нужно форме и раскладке от платформы."""
from .. import edit
from .model import _panel_tabs, BOX_TOLERANCE
from .coeffs import hidden_page


# Область страницы панели по виду закладок: сколько отнять от размера панели `(W, H)`, чтобы получить край `(право, низ)`
# области, от которой предприятие считает правила вложенных (панель без рамки): Top, TopScrolling, Bottom — 682×60 при 684×80,
# LeftHorizontal — по подписи (`panel_area`; 612×78 при «Страница1»), DontUse — 684×80. Высота у «Не отображать» и «Слева
# (горизонтально)» выведена, а не проверена (`PANEL_HEIGHT_DERIVED`). Панель с рамкой и прочие виды закладок не проверялись.
PANEL_AREA_CUT = {"Top": (2, 20), "TopScrolling": (2, 20), "Bottom": (2, 20), "LeftHorizontal": (72, 2), "DontUse": (0, 0)}
PANEL_HEIGHT_DERIVED = frozenset({"LeftHorizontal", "DontUse"})
# «Сверху» с картинкой у закладки: ряд закладок 20 px вместо 18, область ниже на 2 px (проверено в предприятии: поле с низом 92 встало на 90).
PICTURE_TOP_CUT = (2, 22)
# «Слева (горизонтально)»: полоса закладок — ширина самой длинной подписи шрифтом панели плюс 16 px (70 при «Страница1» 54 px, 157 при
# «Фискальные регистраторы» 141 px, при растяжении окна не меняется); область начинается правее полосы и рамки 2 px.
LEFT_STRIP_PAD, LEFT_FRAME = 16, 2
TAB_PICTURE_WORDS = "у закладок панели картинки: полоса закладок выше обычной, область вложенных не проверялась у этого вида"
LEFT_TAB_WORDS = ("ширина полосы закладок «Слева (горизонтально)» берётся по подписи шрифтом панели; подпись или шрифт не из проверенных, "
                  "область вложенных не проверялась у этого вида")


# Отступ вложенного элемента от области страницы панели закладок «Сверху»/«Снизу»: 6 px со всех сторон, как ставит Конфигуратор (форма от своего
# края — 8). Одно число на `generate` (блок закладок), линтер (`page_inset`) и правила правки.
PAGE_INSET = 6


def tab_pictures(node):
    """`[bool]` — у какой закладки панели задана картинка (`title_picture`: источник не 0 либо заполнена ссылка `ref`); пусто, если закладок не разобрать."""
    block = edit.layout_block(node, need=False)
    pages = block.get("pages") if isinstance(block, dict) else None
    items = pages.get("items") if isinstance(pages, dict) else None
    if not isinstance(items, list):
        return []
    out = []
    for page in items:
        picture = page.get("title_picture") if isinstance(page, dict) else None
        ref = picture.get("ref") if isinstance(picture, dict) else None
        # картинка есть, если задан источник либо ссылка на неё (имя или состав ссылки): у части записей `source` — 0, а ссылка заполнена
        # встроенный файл (`ref.u1` = 3, тело в `ref.u7`) — тоже картинка
        out.append(isinstance(picture, dict) and (bool(picture.get("source")) or (
            isinstance(ref, dict) and (ref.get("u2") not in ([0], None) or bool(ref.get("u3")) or bool(ref.get("u7"))))))
    return out


def tab_captions(node):
    """Подписи закладок панели списком строк; пусто, если закладок не разобрать."""
    block = edit.layout_block(node, need=False)
    pages = block.get("pages") if isinstance(block, dict) else None
    items = pages.get("items") if isinstance(pages, dict) else None
    out = []
    for page in items if isinstance(items, list) else ():
        caption = page.get("caption") if isinstance(page, dict) else None
        texts = caption.get("items") if isinstance(caption, dict) else None
        first = texts[0] if isinstance(texts, list) and texts else None
        out.append(first.get("text", "") if isinstance(first, dict) and isinstance(first.get("text"), str) else "")
    return out


# Закладки панели: размеры, общие для рисунка и области страницы. Все числа сняты в предприятии у панели 300×160 без рамки, шрифт по умолчанию
# (проверено: «Сверху», «Снизу», «Слева» и «Справа» вертикально и горизонтально, с прокруткой, в несколько строк, с перестановкой рядов); где число
# оценено, это сказано рядом.
TAB_PAD, TAB_GAP, TAB_PICTURE = 20, 6, 19      # закладка шире подписи на 20 px, между закладками 6 px, картинка добавляет 19 px (закладка «Три» с картинкой — 58 px)
TAB_STRIP, TAB_STRIP_PICTURE = 18, 20          # высота полосы закладок; 20 — когда хотя бы у одной закладки есть картинка (так же ширина вертикальной полосы)
ROW_INSET = 6                                  # ряд закладок «в несколько строк» из нескольких закладок начинается на 6 px правее края панели, ряд из одной закладки — на краю
SCROLL_ARROWS = 28                             # две кнопки прокрутки у закладок «с прокруткой»
VERTICAL_PAD = 8                               # у вертикальной закладки подпись начинается на 4 px от края, и столько же остаётся с другого конца
LEFT_PICTURE_EXTRA = 25                        # «Слева/Справа (горизонтально)»: полоса шире на 25 px, когда у закладки есть картинка
ROWS_TOP, ROWS_BOTTOM = ("TopMultiLine", "TopMultilineTransposition"), ("BottomMultiLine", "BottomMultilineTransposition")
SCROLL_KINDS = ("TopScrolling", "BottomScrolling")
VERTICAL_KINDS = ("LeftVertical", "RightVertical")
SIDE_KINDS = ("LeftHorizontal", "RightHorizontal")
TRANSPOSED = ("TopMultilineTransposition", "BottomMultilineTransposition")
# Виды закладок, у которых есть правило области страницы (`panel_area`); часть из них — только когда у закладок есть картинка (так снято).
PANEL_AREA_KINDS = frozenset(PANEL_AREA_CUT) | {"BottomScrolling"} | frozenset(VERTICAL_KINDS) | frozenset(ROWS_TOP) | frozenset(ROWS_BOTTOM)
PICTURE_ONLY_WORDS = ("область вложенных у этого положения закладок снята только у панели, у закладок которой есть картинка; "
                      "без картинки высота полосы не проверялась")
SIDE_AREA_WORDS = ("у закладок «Слева (горизонтально)» и «Справа (горизонтально)» картинка: страница уже вложенных, предприятие их не сжимает "
                   "и показывает с прокруткой; область вложенных не проверялась у этого вида")
RIGHT_AREA_WORDS = ("область вложенных у «Справа (горизонтально)» не проверялась (столбец закладок и линии страницы сняты только с картинкой у закладки, "
                    "вложенные на такой странице предприятие не сжимает)")
MEASURE_WORDS = "ширина подписи закладки не измерена (шрифт или знаки не из проверенных): размер закладок и область вложенных не считаются"
NO_AREA_WORDS = ("у «Прокручиваемых страниц» (код 13) заголовки страниц идут друг под другом, полосы закладок нет; область вложенных не проверялась")


def tab_picture_height(node):
    """Высота самой высокой картинки закладок панели: вложенной в файл, картинки платформы или общей картинки конфигурации (из выгрузки); 0 — картинок нет, а у нечитаемой — высота серого квадрата (16)."""
    from ..render import panels, picture_bitmap
    tallest = 0
    for block in panels.page_picture_blocks(node):
        bitmap = picture_bitmap.data_uri(block)
        if bitmap is not None:
            tallest = max(tallest, picture_bitmap.size_of(bitmap)[1])
    return tallest


HORIZONTAL_STRIPS = ("Top", "TopScrolling", "Bottom", "BottomScrolling")
STRIP_PICTURE_PAD = 4                          # полоса выше самой высокой картинки закладок на 4 px (картинка 16 px — 20, картинка 32 px — 36: снято в предприятии у одной формы)


def strip_height(node, kind=None):
    """Высота полосы закладок: 20 px, если у какой-то закладки есть картинка, иначе 18 px (так снято у «Сверху»; у «Снизу», рядов и вертикальных положений
    высота при картинке снята, без картинки — по аналогии). У полосы «Сверху» и «Снизу» (`kind`) с картинкой выше 16 px — высота картинки плюс 4 (картинка 32 px — 36 px, снято одной формой)."""
    base = TAB_STRIP_PICTURE if any(tab_pictures(node)) else TAB_STRIP
    if kind in HORIZONTAL_STRIPS:
        return max(base, tab_picture_height(node) + STRIP_PICTURE_PAD) if any(tab_pictures(node)) else base
    return base


def tab_widths(doc, owner):
    """`[(подпись, ширина закладки в один ряд, есть ли картинка)]` либо `None`, если ширина какой-то подписи не измерена."""
    from .. import textwidth
    font = textwidth.element_font(owner.node, doc)
    captions, pictures = tab_captions(owner.node), tab_pictures(owner.node)
    out = []
    for at, text in enumerate(captions):
        measured = textwidth.measure(text, font)
        if not measured.exact:
            return None
        picture = at < len(pictures) and pictures[at]
        out.append((text, measured.px + TAB_PAD + (TAB_PICTURE if picture else 0), bool(picture)))
    return out


def tab_rows(widths, avail):
    """Закладки «в несколько строк»: `[[номера закладок]]` — подряд в ряд, пока ряд с промежутками 6 px помещается в `avail`. Проверено по формам с 3 и
    8 страницами: ряды набираются по порядку страниц, закладка не переносится назад."""
    rows, used = [[]], 0
    for at, width in enumerate(widths):
        need = width + (TAB_GAP if rows[-1] else 0)
        if rows[-1] and used + need > avail:
            rows.append([])
            used, need = 0, width
        rows[-1].append(at)
        used += need
    return rows


def row_order(rows, kind, active):
    """Ряды от дальнего от страницы к ближнему. При перестановке рядов ряд выбранной закладки идёт ближним, остальные сохраняют порядок (так ряды стоят
    при открытии формы; после щелчков по закладкам порядок зависит от истории — предприятие меняет местами выбранный ряд и ближний, в рисунке не
    воспроизводится)."""
    order = list(range(len(rows)))
    if kind in TRANSPOSED:
        home = next((r for r, row in enumerate(rows) if active in row), None)
        if home is not None:
            order.remove(home)
            order.append(home)
    return order


def row_widths(widths, row, avail):
    """Ширины закладок одного ряда: ряд растягивается на всю ширину поровну (остаток — первым закладкам); ряд из одной закладки занимает ширину панели минус 1."""
    if len(row) == 1:
        return [avail + ROW_INSET]
    natural = [widths[at] for at in row]
    extra = avail - sum(natural) - TAB_GAP * (len(row) - 1)
    share, rest = divmod(max(extra, 0), len(row))
    return [w + share + (1 if k < rest else 0) for k, w in enumerate(natural)]


def multi_rows(doc, owner, width, active=0):
    """`(ряды закладок от дальнего к ближнему, ширины, слова)` для «в несколько строк»; ряды пусты, слова названы, если ширина подписи не измерена."""
    widths = tab_widths(doc, owner)
    if widths is None:
        return None, None, MEASURE_WORDS
    natural = [w for _t, w, _p in widths]
    avail = width - ROW_INSET - 1
    rows = tab_rows(natural, avail)
    return [rows[r] for r in row_order(rows, _panel_tabs(owner), active)], natural, None


def left_strip(doc, owner, width):
    """Ширина полосы закладок «Слева/Справа (горизонтально)»: самая длинная подпись плюс 17 px (плюс 25 px, когда у какой-то закладки есть картинка), не шире
    панели; `None` — подпись не измерена."""
    widths = tab_widths(doc, owner)
    if not widths:
        return None
    from .. import textwidth
    font = textwidth.element_font(owner.node, doc)
    text = max(textwidth.measure(t, font).px for t, _w, _p in widths)
    return min(text + LEFT_STRIP_PAD + 1 + (LEFT_PICTURE_EXTRA if any(tab_pictures(owner.node)) else 0), width)


def panel_frame(doc, owner, size, active=0):
    """`((x, y, ширина, высота) линий страницы относительно панели | None, слова | None)` для закладок панели `owner` при размере `size`. Линии идут по краю
    страницы; область вложенных — внутри них (на 1 px с каждой стороны). Проверено у панели без рамки: «Сверху» и «Снизу» (в том числе с прокруткой) — страница
    ниже (выше) полосы; «в несколько строк» — ниже ряда или рядов (ряд равен полосе; у «Снизу» страница короче на один пиксель на ряд сверх первого);
    «вертикально» — правее левой полосы и левее правой; «горизонтально» — правее (левее) столбца закладок; «Не отображать» — вся панель. Для кода 13
    полосы нет — `None`."""
    kind = _panel_tabs(owner)
    w, h = size
    s = strip_height(owner.node, kind)
    if kind in ("Top", "TopScrolling"):
        return (0, s, w, h - s), None
    if kind in ("Bottom", "BottomScrolling"):
        return (0, 0, w, h - s), None
    if kind in ROWS_TOP or kind in ROWS_BOTTOM:
        rows, _natural, words = multi_rows(doc, owner, w, active)
        if rows is None:
            return None, words
        n = len(rows)
        if kind in ROWS_TOP:
            return (0, s * n, w, h - s * n), None
        return (0, 0, w, h - (s + 1) * n + 1), None
    if kind == "LeftVertical":
        return (s, 0, w - s, h), None
    if kind == "RightVertical":
        return (0, 0, w - s, h), None
    if kind in SIDE_KINDS:
        strip = left_strip(doc, owner, w)
        if strip is None:
            return None, MEASURE_WORDS
        return ((strip - 1, 0, w - strip + 1, h) if kind == "LeftHorizontal" else (0, 0, w - strip + 1, h)), None
    if kind == "DontUse":
        return (0, 0, w, h), None
    return None, NO_AREA_WORDS if kind == 13 else None


def _owner_size(owner):
    x, y, x2, y2 = owner.box
    return x2 - x, y2 - y


def panel_area(doc, owner, size):
    """`(край (право, низ) | None, слова | None)`: видимая область панели `owner` без рамки при размере панели `size`, от которой
    предприятие считает правила вложенных. `None` с словами — область этого вида не проверялась (вложенные стоят по `box` и росту).
    Область — внутренность линий страницы (`panel_frame`): на 1 px внутрь с каждой стороны. «Сверху», «Сверху (с прокруткой)», «Снизу» и «Снизу (с прокруткой)»
    — без картинок у закладок 682×60 при 684×80, с картинкой 682×58; «Слева (горизонтально)» — по самой длинной подписи (`LEFT_STRIP_PAD`), только если
    ширина подписи измерена и картинок нет; вертикальные положения и «в несколько строк» — только с картинкой у закладки (так снято)."""
    kind = _panel_tabs(owner)
    pictures = any(tab_pictures(owner.node))
    if kind == "RightHorizontal":
        return None, SIDE_AREA_WORDS if pictures else RIGHT_AREA_WORDS
    if kind == 13:
        return None, NO_AREA_WORDS
    if kind not in PANEL_AREA_KINDS:
        return None, None
    if kind == "DontUse":
        cut = PANEL_AREA_CUT[kind]
    elif kind in ("Top", "TopScrolling", "Bottom", "BottomScrolling") and pictures:
        cut = PICTURE_TOP_CUT
    elif kind in SIDE_KINDS and pictures:
        return None, SIDE_AREA_WORDS
    elif kind in VERTICAL_KINDS or kind in ROWS_TOP or kind in ROWS_BOTTOM:
        if not pictures:
            return None, PICTURE_ONLY_WORDS
        frame, words = panel_frame(doc, owner, size)
        if frame is None:
            return None, words
        return (frame[2] - 2, frame[3] - 2), None
    elif pictures:
        return None, TAB_PICTURE_WORDS
    elif kind == "LeftHorizontal":
        from .. import textwidth
        captions = tab_captions(owner.node)
        font = textwidth.element_font(owner.node, doc)
        measured = [textwidth.measure(t, font) for t in captions]
        if not captions or not all(m.exact for m in measured):
            return None, LEFT_TAB_WORDS
        cut = (max(m.px for m in measured) + LEFT_STRIP_PAD + LEFT_FRAME, LEFT_FRAME)
    else:
        cut = PANEL_AREA_CUT["Bottom" if kind == "BottomScrolling" else kind]
    return (size[0] - cut[0], size[1] - cut[1]), None


def panel_not_checked(doc, owner):
    """Слова, почему вложенные панели без рамки считаются по `box` и росту, а не от области; `None` — правило от области действует."""
    return panel_area(doc, owner, _owner_size(owner))[1]


# Виды закладок панели русскими словами (как говорят отчёт `set_property` и конструктор).
PANEL_KIND_RU = {"Top": "Сверху", "TopScrolling": "Сверху (с прокруткой)", "Bottom": "Снизу", "BottomScrolling": "Снизу (с прокруткой)",
                 "LeftHorizontal": "Слева (горизонтально)", "DontUse": "Не отображать"}
_NO_BORDER = (None, "None", "WithoutBorder", "NoBorder")


def _panel_unframed(item):
    """Панель без рамки: таблица областей проверена только на таких; блок рамки не разобран — тоже не считается проверенным."""
    try:
        border = item.node["content"]["u1"]["u0"]["border"]
    except (KeyError, TypeError):
        return False
    return isinstance(border, dict) and border.get("border_type") in _NO_BORDER


def _area(panel_size, kind):
    cut = PANEL_AREA_CUT[kind]
    return panel_size[0] - cut[0], panel_size[1] - cut[1]


def _same_edge(a, b):
    return all(abs(x - y) <= BOX_TOLERANCE for x, y in zip(a, b))


def _kinds_words(kinds):
    return " / ".join(f"«{PANEL_KIND_RU[k]}»" for k in kinds)


def _carrier_shown(form, owner, shown):
    """Панель видима сама, на показанной странице своего родителя и так вверх по цепочке."""
    while owner is not None:
        if not owner.visible or hidden_page(owner, shown):
            return False
        owner = form.holders[owner.holder].item
    return True


FRAMES_TABS_MEASURED = frozenset(edit.FRAMED_UNTOUCHED)


def _form_border_kind(doc):
    """Вид рамки формы (`border_type`) либо `None`."""
    found = edit.layout_block(edit.container(doc), need=False)
    frame = found.get("layout") if isinstance(found, dict) else None
    value = frame.get("border") if isinstance(frame, dict) else None
    return value.get("border_type") if isinstance(value, dict) else None


def panel_collision(lim):
    """Столкновение с командной панелью верхнего уровня: раскладку держит кромка панели формы, а не содержимое, и полосы прокрутки
    такая раскладка не даёт, пока ни один элемент не вылез за окно. Проверено у верхней панели; нижняя, идущая вверх, — по
    аналогии, в предприятии не проверялось.
    """
    return lim.kind == "столкновение" and any(o is not None and o.type == "CommandBar" and o.holder == 0 for o in (lim.a, lim.b))
