"""Панели и закладки: полоса закладок, страницы, обрезка и прокрутка полосы, рамка группы и панели."""
import math

from .. import edit, layout, textwidth
from .core import (EDGE, FORM_BG, _dig, GROUP_TOP, LEFT_STRIP, LEFT_TAB, NO_FRAME, STRIP, picture_box_unseen, _caption, _color_of, _font_of, _n, _page_captions, _scroll_bar,
                   _text)
from . import charts, groupbox, picture_bitmap, picture_places, tab_corner_data
from .marks import hidden_overlay


# Закладки «Сверху» и «Снизу» (у «Снизу с прокруткой» то же): естественная ширина закладки — ширина текста по шрифту панели плюс 20 px, у закладки со значком — ещё место под значок и
# 3 px промежутка (`layout.TAB_PICTURE` — 19 px при значке 16); между закладками 6 px; первая закладка стоит на левом краю панели. Числа — в `layout.area` (одни и те же для рисунка и
# для области вложенных). Значок закладки рисуется картинкой (файл, платформа, конфигурация) либо серым квадратом, если картинки нет.
TAB_PAD, TAB_GAP, TAB_PICTURE = layout.TAB_PAD, layout.TAB_GAP, layout.TAB_PICTURE
TAB_PICTURE_GAP = TAB_PICTURE - 16               # промежуток 3 px в естественной ширине закладки со значком; подпись начинается на 2 px правее места под значок
TAB_ACTIVE, TAB_INACTIVE = ("#ffffef", "#b5b184"), ("#efebce", "#cecaad")


TAB_CORNER, TAB_ACCENT = 3, "#ffe2a5"
HEADER, PAGE_BOTTOM_GAP = 16, 11       # код 13: заголовок страницы 16 px с линией под ним; линия у нижней границы страницы 0 на 11 px выше низа панели (149 из 160 px)
ARROW_FILL, ARROW_ON, ARROW_OFF = "#f7f3de", "#423100", "#b5a87a"

# Закладки не помещаются в панель («Сверху», «Снизу»): полоса занимает ширину панели минус TAB_RIGHT_MARGIN (7 px; 8 px, если у какой-либо закладки есть значок), ширины сжимаются
# по `squeeze_widths` (самая широкая уменьшается на 5 px, пока сумма не влезет), подпись усекается по месту без многоточия; когда не помещается и знак, закладка пуста. Правило проверено
# по краям закладок и подписям 66 панелей снимков предприятия (без значков и со значками 16 и 32 px, ширины 60–766 px, от 2 до 8 закладок).
# Вертикальные закладки («Слева», «Справа») сжимаются по общему уровню (`_fit_tabs`), по высоте панели, без промежутков и без правого поля; подпись начинается на 4 px от края
# закладки (`layout.VERTICAL_PAD` = 8 на оба конца): у панели 160 px при 8 закладках закладки по 20 px и подписи из одной буквы, при 100 px — без текста.
TAB_RIGHT_MARGIN, TAB_DOTS, LEFT_STRIP_PAD = 7, 9, 17
TAB_RIGHT_MARGIN_PICTURE = 8         # у панели, закладки которой несут значки, полоса короче на 8 px (без значков — на 7)


def _fit_tabs(items, font, avail, gap=TAB_GAP, trim=TAB_PAD):
    """`items` — `[(подпись, лишняя ширина закладки)]`; возвращает `[(подпись для рисунка, ширина закладки)]`. Если всё помещается — естественные ширины;
    иначе подбирается общий уровень: закладка получает min(своя ширина, уровень), уровень — наибольший, при котором сумма с промежутками не больше `avail`.
    `trim` — сколько от закладки уходит на поля подписи при усечении (у вертикальных закладок меньше, чем у горизонтальных)."""
    nat = [textwidth.measure(t, font).px + TAB_PAD + extra for t, extra in items]
    gaps = gap * max(len(items) - 1, 0)
    if sum(nat) + gaps <= avail:
        return [(t, w) for (t, _), w in zip(items, nat)]
    lo, hi = 0.0, float(max(nat))
    for _ in range(40):
        mid = (lo + hi) / 2
        if sum(min(w, mid) for w in nat) + gaps <= avail:
            lo = mid
        else:
            hi = mid
    level = lo
    out = []
    for (t, extra), w in zip(items, nat):
        if w <= level:
            out.append((t, w))
            continue
        out.append((cut_tab_text(t, font, level - trim - extra), level))
    return out


TAB_MIN, TAB_SQUEEZE_STEP, TAB_FLOOR = 33, 5, 9


def squeeze_widths(natural, budget, active=0, step=TAB_SQUEEZE_STEP):
    """Ширины закладок «Сверху» и «Снизу», когда они не помещаются: самая широкая закладка уменьшается на 5 px, пока сумма не станет не больше `budget` (ширина полосы без промежутков).
    Из равных по ширине первой уменьшается показанная закладка (`active`), дальше — самая правая. Закладка рисуется не уже `TAB_FLOOR` px (`drawn_width`), но место в полосе занимает по этому расчёту.
    Проверено по краям закладок панелей с подписями «1»…«11111», «Страница1…5» и составами из 2–8 закладок, без значков и со значками 16 и 32 px: ширины совпали точно, в том числе неровные
    (33, 33, 33, 34, 35 у подписей «1», «11», «111», «1111», «11111»)."""
    widths = list(natural)
    while sum(widths) > budget and max(widths) > TAB_FLOOR:
        widest = max(widths)
        tied = [i for i, v in enumerate(widths) if v == widest]
        pick = active if active in tied else tied[-1]
        widths[pick] -= step
    return widths


def drawn_width(layout_width):
    """Ширина нарисованной закладки: не меньше 9 px (место в полосе — по `squeeze_widths`)."""
    return max(layout_width, TAB_FLOOR)


def row_tabs(items, font, avail, active=0, gap=TAB_GAP):
    """`[(подпись для рисунка, ширина закладки)]` закладок «Сверху» и «Снизу»: `items` — `[(подпись, лишняя ширина закладки)]`. Естественная ширина — текст плюс 20 px и лишнее, не меньше 33 px; не помещаются в `avail` —
    `squeeze_widths`; подпись усекается по месту (`cut_tab_text`) в ширину закладки минус 20 px и лишнее."""
    nat = [max(round(textwidth.measure(t, font).px) + TAB_PAD + extra, TAB_MIN) for t, extra in items]
    budget = avail - gap * max(len(items) - 1, 0)
    widths = squeeze_widths(nat, budget, active) if sum(nat) > budget else nat
    out = []
    for (t, extra), w, n in zip(items, widths, nat):
        out.append((t, w) if w >= n else (cut_tab_text(t, font, w - TAB_PAD - extra), w))
    return out


def cut_tab_text(t, font, room):
    """Подпись закладки в `room` px: самое длинное начало с «…», а когда и одного знака с многоточием не помещается, — первый знак без многоточия, если он сам помещается (два знака без
    многоточия предприятие не оставляет: «Ст» при 14 px места показано как «С»), иначе пусто."""
    head = t
    while head and textwidth.measure(head, font).px + TAB_DOTS > room:
        head = head[:-1]
    if head:
        return head.rstrip() + "…"
    first = t[:1]
    return first if first.strip() and textwidth.measure(first, font).px <= room else ""


def _tab_picture_size(picture):
    """`(ширина, высота)` значка закладки: у картинки — её размер (файл, платформа, конфигурация), у заглушки — 13×13."""
    return picture_bitmap.size_of(picture, 13) if isinstance(picture, str) else (13, 13)


def _tab_picture(x, y, picture):
    """Значок закладки: картинка (`data:`-адрес в `picture`: файл, платформа, общая картинка конфигурации из выгрузки) в своём размере (снято: 16×16 у закладки «Сверху», слева от подписи на 10 px от края)
    либо серый квадрат 13×13 (картинки в файле и в выгрузке нет)."""
    if isinstance(picture, str):
        w, h = picture_bitmap.size_of(picture)
        return picture_bitmap.image_at(x, y, w, h, picture, "tab-picture tab-bitmap")
    return f"<rect class='tab-picture' x='{_n(x + 0.5)}' y='{_n(y + 0.5)}' width='13' height='13' fill='#d8d8d8' stroke='#999'/>"


def picture_slot(pictures):
    """Ширина места под значок в закладках панели: самый широкий значок (у заглушки 16); 0 — значков нет."""
    sizes = [_tab_picture_size(p)[0] if p is not True else 16 for p in pictures if p]
    return max(sizes) if sizes else 0


def _icon_fits(picture, slot, tab_width):
    """Значок помещается в закладку: 10 px от левого края, внутри места под значок по центру, до правого края (снято: у закладки 34 px со значком 16 px в месте 32 — рисуется, у 33 px — нет)."""
    pw = _tab_picture_size(picture)[0] if picture is not True else 16
    return TAB_PAD // 2 + (slot - pw) // 2 + pw <= round(tab_width)


def _tab(x, y, w, h, text, font=None, picture=False, active=False, below=0, rounded=False, center=False, inset=None, mark=True, slot=0, text_dy=0, flip=False):
    """Закладка: верхние углы срезаны на 3 px, нижней границы нет (под полосой идёт линия страницы), у активной — оранжевая полоса 2 px под верхней границей и заливка
    до линии страницы (линия под активной закладкой прерывается). Края и цвета проверены до пикселя; срез угла нарисован по виду. `below` — на сколько строк
    ниже `h` закладка закрывает линию страницы (у активной 1). `flip` — закладка «Снизу»: зеркало «Сверху» по вертикали (срезаны нижние углы, верхней границы нет — над закладкой идёт
    линия страницы, у активной она прерывается, оранжевая полоса 2 px над нижней границей; `below` — на сколько строк выше `y` активная закладка закрывает линию). `center` — подпись по центру закладки (ряды «в несколько строк», пока у закладки нет
    картинки); `inset` — сдвиг подписи от левого края вместо обычных 10 px (столбец «Слева/Справа (горизонтально)» с картинками)."""
    fill, stroke = TAB_ACTIVE if active else TAB_INACTIVE
    box_attr = f" data-box='{_n(x)} {_n(y)} {_n(w)} {_n(h)}'" if mark else ""
    c, bottom = TAB_CORNER, y + h + (below if active else 0)
    if rounded and flip:
        top = y - (below if active else 0)
        outline = f"M{_n(x + 0.5)} {_n(top)}V{_n(y + h - c - 0.5)}L{_n(x + c + 0.5)} {_n(y + h - 0.5)}H{_n(x + w - c - 0.5)}L{_n(x + w - 0.5)} {_n(y + h - c - 0.5)}V{_n(top)}"
        out = [f"<path class='tab'{box_attr} d='{outline}Z' fill='{fill}' stroke='none'/>",
               f"<path class='tab-edge' d='{outline}' fill='none' stroke='{stroke}'/>"]
    elif rounded:
        outline = f"M{_n(x + 0.5)} {_n(bottom)}V{_n(y + c + 0.5)}L{_n(x + c + 0.5)} {_n(y + 0.5)}H{_n(x + w - c - 0.5)}L{_n(x + w - 0.5)} {_n(y + c + 0.5)}V{_n(bottom)}"
        out = [f"<path class='tab'{box_attr} d='{outline}Z' fill='{fill}' stroke='none'/>",
               f"<path class='tab-edge' d='{outline}' fill='none' stroke='{stroke}'/>"]
    else:    # закладки «Слева»: прямоугольник с полной рамкой (срез углов и вид без нижней границы сверены только у «Сверху» и «Снизу»)
        out = [f"<rect class='tab'{box_attr} x='{_n(x + 0.5)}' y='{_n(y + 0.5)}' width='{max(w - 1, 0)}' height='{max(h - 1, 0)}' fill='{fill}' stroke='{stroke}'/>"]
    if active and rounded:
        out.append(f"<rect class='tab-accent' x='{_n(x + c)}' y='{_n(y + h - c if flip else y + 1)}' width='{_n(max(w - 2 * c, 0))}' height='2' fill='{TAB_ACCENT}'/>")
    if rounded:
        out += [f"<rect class='tab-corner' x='{px}' y='{py}' width='1' height='1' fill='{color}'/>" for px, py, color in tab_corner_data.corner_pixels(active, flip, x, y, w, h)]
        if flip and active:
            out += [f"<rect class='tab-corner' x='{_n(jx)}' y='{_n(y - 1)}' width='1' height='1' fill='{color}'/>"
                    for jx, color in ((x + w - 2, tab_corner_data.JOINT_INNER), (x + w, tab_corner_data.JOINT_OUTER), (x + w + 1, tab_corner_data.JOINT_OUTER))]
    at = x + (TAB_PAD // 2 if inset is None else inset)
    if picture:
        pw, ph = _tab_picture_size(picture)
        room = slot or pw
        pic_at = at + (room - pw) // 2 if inset is None else x + 6        # значок по центру места под значок (16 px в месте 32 — на 8 px правее); столбец с картинками: значок у левого края
        out.append(_tab_picture(math.floor(pic_at), y + (h - ph) // 2 - (1 if flip else 0), picture))      # по высоте по центру полосы (у полосы 20 px и значка 16 px — на 2 px от верха; у закладки «Снизу» на 1 px выше: 1 px от верха, 3 px до нижней границы, снято T333)
        if inset is None:
            at += room + TAB_PICTURE_GAP - 1           # подпись правее места под значок на 2 px (место + 10 + 2): чернила подписи на 29-м столбце закладки при значке 16 px
    if center and not picture:
        return out + [_text(x + w / 2, y + text_dy + min(13, h - 4), text, anchor="middle", font=font)]
    return out + [_text(at, y + text_dy + min(13, h - 4), text, font=font)]


def _side_tab(x, y, w, h, side, text, font=None, picture=False, active=False, clip=""):
    """Вертикальная закладка «Слева» (`side` = «L») или «Справа» («R»): срезаны два угла у внешнего края, линии у страницы нет (активная закрывает линию страницы
    на 1 px), у активной оранжевая полоса 2 px у внешнего края. Подпись читается сверху вниз (повёрнута по часовой стрелке) и у «Слева», и у «Справа»; картинка
    стоит над подписью, не повёрнута. Срез углов нарисован по виду, края и цвета сверены."""
    fill, stroke = TAB_ACTIVE if active else TAB_INACTIVE
    c = TAB_CORNER
    if side == "L":
        x0, x1 = x, x + w + (1 if active else 0)
        outline = f"M{_n(x1)} {_n(y + 0.5)}H{_n(x0 + c + 0.5)}L{_n(x0 + 0.5)} {_n(y + c + 0.5)}V{_n(y + h - c - 0.5)}L{_n(x0 + c + 0.5)} {_n(y + h - 0.5)}H{_n(x1)}"
    else:
        x0, x1 = x - (1 if active else 0), x + w
        outline = f"M{_n(x0)} {_n(y + 0.5)}H{_n(x1 - c - 0.5)}L{_n(x1 - 0.5)} {_n(y + c + 0.5)}V{_n(y + h - c - 0.5)}L{_n(x1 - c - 0.5)} {_n(y + h - 0.5)}H{_n(x0)}"
    box = f"{_n(x0)} {_n(y)} {_n(x1 - x0)} {_n(h)}"
    out = [f"<path class='tab' data-box='{box}' d='{outline}Z' fill='{fill}' stroke='none'/>", f"<path class='tab-edge' d='{outline}' fill='none' stroke='{stroke}'/>"]
    if active:
        ax = x + 1 if side == "L" else x + w - 3
        out.append(f"<rect class='tab-accent' x='{_n(ax)}' y='{_n(y + c)}' width='2' height='{_n(max(h - 2 * c, 0))}' fill='{TAB_ACCENT}'/>")
    top = y + 4
    if picture:
        out.append(_tab_picture(x + (w - 13) / 2, top, picture))
        top += TAB_PICTURE
    if text:
        px = x + w / 2 - 4
        out.append(_text(px, top, text, font=font, extra=f" transform='rotate(90 {_n(px)} {_n(top)})'"))
    return out


def _arrow_button(x, y, w, h, direction, enabled=True):
    """Кнопка прокрутки закладок: рамка и стрелка-треугольник (◄ ► ▲ ▼); недоступная — блёклая."""
    cx, cy = x + w / 2, y + h / 2
    shape = {"L": f"M{_n(cx + 2)} {_n(cy - 4)}L{_n(cx - 2)} {_n(cy)}L{_n(cx + 2)} {_n(cy + 4)}Z", "R": f"M{_n(cx - 2)} {_n(cy - 4)}L{_n(cx + 2)} {_n(cy)}L{_n(cx - 2)} {_n(cy + 4)}Z",
             "U": f"M{_n(cx - 4)} {_n(cy + 2)}L{_n(cx)} {_n(cy - 2)}L{_n(cx + 4)} {_n(cy + 2)}Z", "D": f"M{_n(cx - 4)} {_n(cy - 2)}L{_n(cx)} {_n(cy + 2)}L{_n(cx + 4)} {_n(cy - 2)}Z"}[direction]
    return [f"<rect class='tab-arrow' x='{_n(x + 0.5)}' y='{_n(y + 0.5)}' width='{max(w - 1, 0)}' height='{max(h - 1, 0)}' fill='{ARROW_FILL}' stroke='{EDGE}'/>",
            f"<path class='tab-arrow-mark' d='{shape}' fill='{ARROW_ON if enabled else ARROW_OFF}'/>"]


def _page_pictures(node):
    """`[bool]` — у какой закладки панели задана картинка (`title_picture/source` не 0)."""
    return layout.tab_pictures(node)


def _page_bitmaps(node):
    """`[data:-адрес | None]` — картинка каждой закладки панели, которую можно нарисовать (общая картинка конфигурации или вложенная в файл)."""
    block = edit.layout_block(node, need=False)
    pages = block.get("pages") if isinstance(block, dict) else None
    items = pages.get("items") if isinstance(pages, dict) else None
    return [picture_bitmap.data_uri(_title_picture_block(page.get("title_picture"))) if isinstance(page, dict) else None for page in items] if isinstance(items, list) else []


def page_picture_blocks(node):
    """Блоки картинок закладок панели (в виде обычного блока картинки), у страниц без картинки — пусто."""
    block = edit.layout_block(node, need=False)
    pages = block.get("pages") if isinstance(block, dict) else None
    items = pages.get("items") if isinstance(pages, dict) else None
    return [_title_picture_block(page.get("title_picture")) for page in items if isinstance(page, dict)] if isinstance(items, list) else []


def _title_picture_block(picture):
    """Блок картинки закладки в виде обычного блока картинки (`source`, `ref`, `u7`). У страницы панели `title_picture` — набор картинок, и сама картинка лежит в его `ref`:
    `u1` — источник, `u2` — `[код, GUID]`, `u7` — тело вложенной картинки (так у всех закладок корпуса с картинкой, `source` набора — 0)."""
    ref = picture.get("ref") if isinstance(picture, dict) else None
    if not isinstance(ref, dict) or picture.get("source"):
        return picture
    link = ref.get("u2")
    if isinstance(link, list) and link:
        block = {"code": link[0]}
        if len(link) > 1:
            block["guid"] = link[1]          # без GUID ссылка короче: `[код]` (картинка платформы по коду)
    else:
        block = {}
    return {"source": ref.get("u1"), "ref": block, "u7": ref.get("u7")}


def _scrolling_pages(doc, it, x, y, w, h, captions, shown_at, gone, hidden, cond):
    """Код 13 (`show_tabs` = 13, «Прокручиваемые страницы»): вместо полосы закладок — заголовки страниц друг под другом, у каждого справа три значка
    («, », ▾); справа вертикальная полоса прокрутки 16 px. Видна первая страница с заголовком, заголовок следующей начинается под линией на 11 px выше нижнего края панели.
    Положение значков и заголовка следующей страницы снято по одному кадру; то, что происходит при прокрутке, не воспроизводится."""
    font = _font_of(doc, it)
    out = []
    shown = [n for n in range(len(captions)) if n not in gone]
    inner = w - 16
    at = y
    for k, n in enumerate(shown[:2]):
        # заголовок 16 px и под ним линия (первая страница); у следующей страницы линия над заголовком — у нижней границы страницы
        top = y if k == 0 else y + h - PAGE_BOTTOM_GAP + 1
        line = y + HEADER if k == 0 else y + h - PAGE_BOTTOM_GAP
        out.append(f"<rect class='page-header' x='{_n(x)}' y='{_n(top)}' width='{_n(inner)}' height='{_n(HEADER if k == 0 else max(PAGE_BOTTOM_GAP - 1, 0))}' fill='{TAB_INACTIVE[0]}' stroke='none'/>")
        out.append(f"<rect class='page-header-line' x='{_n(x)}' y='{_n(line)}' width='{_n(inner)}' height='1' fill='{EDGE}'/>")
        out.append(_text(x + 3, top + 12, captions[n], font=font))
        for dx, mark in ((44, "«"), (30, "»"), (14, "▾")):
            out.append(_text(x + inner - dx, top + 12, mark, font=font, fill=ARROW_ON if k else ARROW_OFF))
        if n in hidden or n in cond:
            out += hidden_overlay(x, top, inner, HEADER, hidden.get(n) or cond[n])
    out.append(_scroll_bar(x + inner, y, 16, h))
    return out


def _panel(doc, it, x, y, w, h, gone=(), retitle=None, active=None, hidden=None, cond=None):
    """Закладки панели. `gone` — номера страниц, которые код убирает безусловно: закладки у них нет; `hidden` — `{номер страницы: кто скрыл}` в режиме `hatch`: закладка остаётся на месте
    со штриховкой, без подписи и неактивная; `cond` — `{номер страницы: кто}` закладки, видимость которых код меняет по условию (режим `conditional=hatch`): та же штриховка, но закладка
    ведёт себя как в файле (выбор активной не меняется);
    `retitle` — `{номер страницы: подпись}`, которую код ставит безусловно; `active` — номер показанной страницы (закладка активна), без него — первая из оставшихся видимых.
    Положения закладок: «Сверху», «Снизу» (в том числе с прокруткой — две кнопки справа, закладки обрезаются перед ними), «в несколько строк» (ряды по ширине панели,
    при «перестановке рядов» ряд выбранной закладки ближе к странице), «Слева» и «Справа» вертикально, «Слева» и «Справа» горизонтально (столбец), код 13."""
    hidden = hidden or {}
    cond = {n: who for n, who in (cond or {}).items() if n not in hidden}
    tabs = layout._panel_tabs(it)
    captions = _page_captions(it.node)
    if retitle:
        captions = [retitle.get(n, t) for n, t in enumerate(captions)]
    shown_at = active if active is not None and active not in gone and active not in hidden else next((n for n in range(len(captions)) if n not in gone and n not in hidden), 0)
    s = layout.strip_height(it.node, tabs)
    font = _font_of(doc, it)
    pictures, bitmaps = _page_pictures(it.node), _page_bitmaps(it.node)
    pic = lambda n: (bitmaps[n] if n < len(bitmaps) and bitmaps[n] else True) if n < len(pictures) and pictures[n] else False
    shown = [n for n in range(len(captions)) if n not in gone]
    if tabs in ("Top", "TopScrolling", "Bottom", "BottomScrolling"):  # полоса 18 px (20 px с картинкой) сверху или снизу
        top = y + h - s if tabs in ("Bottom", "BottomScrolling") else y
        out, at = [], x
        scrolling = tabs in layout.SCROLL_KINDS
        slot = picture_slot([pic(n) for n in shown])           # место под значок — по самому широкому значку панели; у каждого значка своё положение внутри места
        extra = slot + TAB_PICTURE_GAP
        natural = {n: (captions[n], textwidth.measure(captions[n], font).px + TAB_PAD + (extra if pic(n) else 0)) for n in shown}
        overflow = scrolling and sum(w_ for _t, w_ in natural.values()) + TAB_GAP * max(len(shown) - 1, 0) > w - 1
        if scrolling:
            fitted = natural
        else:
            fitted = dict(zip(shown, row_tabs([(captions[n], extra if pic(n) else 0) for n in shown], font, w - (TAB_RIGHT_MARGIN_PICTURE if slot else TAB_RIGHT_MARGIN), shown.index(shown_at) if shown_at in shown else 0)))
        limit = x + w - (layout.SCROLL_ARROWS if overflow else 0)
        clip = f"tabs{_n(x)}_{_n(y)}".replace(".", "p")
        if overflow:
            out.append(f"<clipPath id='{clip}'><rect x='{_n(x)}' y='{_n(top - 1)}' width='{_n(limit - x)}' height='{_n(s + 3)}'/></clipPath><g clip-path='url(#{clip})'>")
        for n, t in enumerate(captions):
            if n in gone:
                continue
            picture = pic(n)
            t, tw = fitted[n]
            if at >= limit:
                break
            drawn_at = at
            if not scrolling:
                tw = drawn_width(tw)
            if slot and not scrolling:
                drawn_at = math.floor(at + 0.5)                  # у панели со значками закладки стоят на целых пикселях: края округляются
                tw = math.floor(at + tw + 0.5) - drawn_at
            if picture and not scrolling and not _icon_fits(picture, slot, tw):
                picture = False              # значок не помещается в закладку (10 px от края, место под значок, до правого края): предприятие его не рисует, подпись занимает место значка
                t = cut_tab_text(captions[n], font, tw - TAB_PAD)
            wider = (not picture and not scrolling and tw > natural[n][1] + 0.5 and bool(t))       # закладка шире подписи (минимум 33 px у «1»…«3»): подпись по центру закладки
            out += _tab(drawn_at, top, tw, min(s, h), t, font, picture, n == shown_at, below=1, rounded=True, flip=tabs in ("Bottom", "BottomScrolling"), mark=tabs not in ("Top", "Bottom"), slot=slot, center=wider, text_dy=max(min(s, h) - layout.TAB_STRIP_PICTURE, 0) // 2)
            if n in hidden or n in cond:
                out += hidden_overlay(drawn_at, top, tw, min(s, h), hidden.get(n) or cond[n])
            at += fitted[n][1] + TAB_GAP
        if overflow:
            out.append("</g>")
            line = top + s if tabs == "TopScrolling" else top - 1       # кнопки висят на линии страницы: у «Сверху» над ней, у «Снизу» под ней
            ay = line - 14 if tabs == "TopScrolling" else line
            out += _arrow_button(x + w - layout.SCROLL_ARROWS, ay, 14, 15, "L", enabled=False)
            out += _arrow_button(x + w - layout.SCROLL_ARROWS + 14, ay, 14, 15, "R")
        return out
    if tabs in layout.ROWS_TOP or tabs in layout.ROWS_BOTTOM:  # ряды закладок: от дальнего к ближнему
        natural = [textwidth.measure(captions[n], font).px + TAB_PAD + (TAB_PICTURE if pic(n) else 0) for n in shown]
        rows = layout.tab_rows(natural, w - layout.ROW_INSET - 1)
        order = layout.row_order(rows, tabs, shown.index(shown_at) if shown_at in shown else 0)
        out, drawn = [], []
        for k, r in enumerate(order):
            row = rows[r]
            ry = y + k * s if tabs in layout.ROWS_TOP else y + h - 1 - s * (k + 1)
            widths = layout.row_widths(natural, row, w - layout.ROW_INSET - 1)
            at = x + (layout.ROW_INSET if len(row) > 1 else 0)
            for at_i, tw in zip(row, widths):
                n = shown[at_i]
                drawn.append((n == shown_at, at, ry, tw, n))
                at += tw + TAB_GAP
        for is_active, at, ry, tw, n in sorted(drawn, key=lambda d: d[0]):
            out += _tab(at, ry, tw, s + 1, captions[n], font, pic(n), is_active, rounded=True, center=True)
            if n in hidden or n in cond:
                out += hidden_overlay(at, ry, tw, s + 1, hidden.get(n) or cond[n])
        return out
    if tabs in layout.VERTICAL_KINDS:  # столбец закладок вдоль левого или правого края, подписи сверху вниз
        side = "L" if tabs == "LeftVertical" else "R"
        sx = x if side == "L" else x + w - s
        fitted = _fit_tabs([(captions[n], TAB_PICTURE if pic(n) else 0) for n in shown], font, h, gap=0, trim=layout.VERTICAL_PAD)
        out, edge, total = [], y, 0.0
        for k, (n, (t, th)) in enumerate(zip(shown, fitted)):
            if k in (0, len(shown) - 1) and len(shown) > 2 and t and not t.endswith("…") and t != captions[n]:
                t = ""       # крайняя закладка, сжатая до букв без многоточия: предприятие подписи не показывает (у восьми закладок на 160 px — первая и последняя)
            nxt = y + round(total + th)
            total += th
            out += _side_tab(sx, edge, s, nxt - edge, side, t, font, pic(n), n == shown_at)
            if n in hidden or n in cond:
                out += hidden_overlay(sx, edge, s, nxt - edge, hidden.get(n) or cond[n])
            edge = nxt
        return out
    if tabs in layout.SIDE_KINDS:  # закладки столбиком: полоса по подписи (71 px, если ширина не измерена), закладка 22 px
        out, row = [], 0
        strip = _left_strip(it, font, w, doc)
        sx = x if tabs == "LeftHorizontal" else x + w - strip
        picture_column = any(pictures)
        visible = len(shown) if LEFT_TAB * len(shown) <= h else max((h - 28) // LEFT_TAB, 1)
        for n in shown[:visible]:
            out += _tab(sx, y + LEFT_TAB * row, strip, LEFT_TAB, captions[n], font, pic(n), n == shown_at, inset=30 if picture_column else None)
            if n in hidden or n in cond:
                out += hidden_overlay(sx, y + LEFT_TAB * row, strip, LEFT_TAB, hidden.get(n) or cond[n])
            row += 1
        if visible < len(shown):    # столбец не помещается: внизу у страницы две кнопки ▲▼ (первая недоступна, пока столбец не прокручен)
            bx = sx + strip - 6 - 28 if tabs == "LeftHorizontal" else sx + 9
            out += _arrow_button(bx, y + h - 12, 14, 12, "U", enabled=False)
            out += _arrow_button(bx + 14, y + h - 12, 14, 12, "D")
        return out
    if tabs == 13:
        return _scrolling_pages(doc, it, x, y, w, h, captions, shown_at, set(gone), hidden, cond)
    return []  # «Не отображать»: линий панели нет вовсе


# Рамка группы — по виду рамки, высоте и шрифту заголовка: `groupbox.py`.
GROUP_TITLE = groupbox.GROUP_TITLE


def _group_box(doc, it, x, y, w, h):
    return groupbox.title_parts(doc, it, x, y, w, h, _font_of(doc, it))


def _group_frame(it, x, y, w, h, font=None):
    return groupbox.frame(it, x, y, w, h, font)


def _left_strip(it, font, w, doc=None):
    """Ширина полосы закладок «Слева/Справа (горизонтально)»: самая длинная подпись по шрифту панели плюс 17 px (плюс 25 px, когда у какой-то закладки есть картинка), но не шире панели
    (проверено: подпись 166 px — полоса 183 px на панели 200 px, подпись 54 px — 71 px, подпись 194 px с картинкой — 236 px; подписи не усекаются). Если ширина подписи не
    измерена, берётся 71 px."""
    measured = [textwidth.measure(t, font) for t in _page_captions(it.node)]
    if not measured or not all(m.exact for m in measured):
        return min(LEFT_STRIP, w)
    extra = layout.LEFT_PICTURE_EXTRA if any(layout.tab_pictures(it.node)) else 0
    return min(max(m.px for m in measured) + LEFT_STRIP_PAD + extra, w)


def _panel_frame_box(it, x, y, w, h, font=None, doc=None):
    """Прямоугольник рамки панели по линии страницы (`layout.panel_frame`): «Сверху» — от линии под полосой до низа box; «Снизу» — от верха box до линии над
    полосой; «в несколько строк» — ниже (выше) рядов; «вертикально» — правее левой полосы и левее правой; «горизонтально» — правее (левее) столбца закладок.
    Код 13 — линий страницы нет, `None`. Без документа (`doc`) считаются только «Сверху», «Снизу» и «Слева (горизонтально)»; для вида, которого не проверяли,
    рамка рисуется по всему box."""
    tabs = layout._panel_tabs(it)
    if tabs == 13:
        return None
    if doc is not None:
        frame, _why = layout.panel_frame(doc, it, (w, h))
        if frame is not None:
            fx, fy, fw, fh = frame
            return x + fx, y + fy, max(fw, 0), max(fh, 0)
    if tabs in ("Top", "TopScrolling"):
        return x, y + STRIP, w, max(h - STRIP, 0)
    if tabs in ("Bottom", "BottomScrolling"):
        return x, y, w, max(h - STRIP, 0)
    if tabs == "LeftHorizontal":
        strip = _left_strip(it, font, w)
        return x + strip - 1, y, max(w - strip + 1, 0), h
    return x, y, w, h


# Кнопка формы: рамка #B5B184 со срезанными углами и заливка полосами сверху вниз (снято столбцом пикселей кнопки 23 px: строки 1–2 белые, дальше
# #FFFBEF, #F7FBE7, #F7F7E7, #F7F7DE, #F7F3DE, #F7F3D6, #EFEFD6, нижняя строка #EFEFDE). Полосы заданы строками кнопки 23 px и растягиваются на другую высоту
# пропорционально (кнопки другой высоты по цвету не сверялись).
BUTTON_BANDS = ((1, 2, "#ffffff"), (3, 4, "#fffbef"), (5, 7, "#f7fbe7"), (8, 9, "#f7f7e7"), (10, 14, "#f7f7de"), (15, 15, "#f7f3de"),
                (16, 17, "#f7f3d6"), (18, 20, "#efefd6"), (21, 21, "#efefde"))


def _button_face(x, y, w, h):
    stops = []
    for first, last, color in BUTTON_BANDS:
        a, b = first / 23, (last + 1) / 23
        stops.append(f"<stop offset='{a:.4f}' stop-color='{color}'/><stop offset='{b:.4f}' stop-color='{color}'/>")
    ident = f"btnface{_n(x)}_{_n(y)}".replace(".", "p")
    return [f"<rect class='frame' x='{_n(x + 0.5)}' y='{_n(y + 0.5)}' width='{max(w - 1, 0)}' height='{max(h - 1, 0)}' rx='2.5' fill='none' stroke='{EDGE}'/>",
            f"<linearGradient id='{ident}' x1='0' y1='0' x2='0' y2='1'>{''.join(stops)}</linearGradient>",
            f"<rect class='button-face' x='{_n(x + 1)}' y='{_n(y + 1)}' width='{max(w - 2, 0)}' height='{max(h - 2, 0)}' rx='1.5' fill='url(#{ident})' stroke='none'/>",
            # угол кнопки срезан: пиксель угла — фон формы (снимок: #FFFFEF), соседние с ним — #E7E7CE
            *[f"<rect class='button-corner' x='{_n(cx)}' y='{_n(cy)}' width='1' height='1' fill='{FORM_BG}'/>"
              for cx, cy in ((x, y), (x + w - 1, y), (x, y + h - 1), (x + w - 1, y + h - 1))]]


def _frame(it, x, y, w, h, font=None, doc=None):
    """Видимая рамка элемента: внешний край совпадает с box, толщина 1 px (поле, таблица, поле табличного
    документа, кнопка, поле с кнопкой даты). У надписи в предприятии рамки нет совсем (снимки e239v2, все формы): место надписи показывает `layout`, не рисунок.
    Разделитель не рисуется (остаётся щель), у панели «Не отображать» линий нет. Рамка группы — `_group_frame`,
    рамка панели — по линии страницы (`_panel_frame_box`). У командной панели над таблицей, у флажка и
    переключателя рамки нет — виден фон формы (`NO_FRAME`); у командной панели формы одна линия —
    `_form_bar_line`."""
    if it.type in NO_FRAME or it.type == "Label" or (it.type == "Panel" and layout._panel_tabs(it) == "DontUse") or picture_box_unseen(it) or picture_places.box_frameless(it) or charts.gantt_known(it):
        return []
    if it.type == "GroupBox":
        return _group_frame(it, x, y, w, h, font)
    if it.type == "Panel":
        box = _panel_frame_box(it, x, y, w, h, font, doc)
        if box is None:
            return []
        x, y, w, h = box
    if it.type == "Button":
        return _button_face(x, y, w, h)
    return [f"<rect class='frame' x='{_n(x + 0.5)}' y='{_n(y + 0.5)}' width='{max(w - 1, 0)}' height='{max(h - 1, 0)}' "
            f"fill='none' stroke='{EDGE}'/>"]
