"""Таблицы: колонки (составные шапки, подвал, картинка в колонке), границы и ширины на экране, полоса, прокрутка, обрезка шапки."""

from .. import edit, textwidth
from . import textmeasure
from .core import SCROLL_BAR, _first_text, _n, _scroll_bar, _text, _vline
from .marks import hidden_overlay


# Табличное поле в предприятии (проверено до пикселя по границам колонок списка и табличной части). Шапка — 20 px
# вертикального градиента от #FFFFF7 к #F7EFCE под рамкой и линия #CECAAD под ней (21 px от верха box); разделители колонок
# #BDBD9C через всю шапку. Подвал (флаг `footer`) — зеркально у нижней рамки: линия #CECAAD на 22 px выше нижнего края box,
# 20 px градиента под ней. Ширины колонок в файле — не пиксели: платформа растягивает или сжимает колонки с `size_change`
# «Change» пропорционально так, чтобы они заняли ширину таблицы (минус 2 px рамки и полоса прокрутки), колонки «DontChange»
# (значок списка) остаются как есть; ширина каждой округляется, последняя берёт остаток (границы совпали у списка
# из девяти колонок, у табличной части из десяти и у таблицы из четырёх). Сжатие не ниже 0,75 (`MIN_SCALE`): при большем
# количестве колонок они выходят за поле, и таблица получает горизонтальную прокрутку; растяжение пропорционально (проверено до
# 1,08). Разделители и линия шапки у таблицы другого оформления бывают темнее (#B5B184): цвет взят у шапки табличной части и
# списка, у другой таблицы может отличаться. Заголовок усекается с «…»: место под текст — ширина колонки
# минус 7 (измерено по пяти усечённым заголовкам). Полоса прокрутки списка (15 px справа) нарисована всегда: у списка в
# базе строки есть, а у табличной части и таблицы значений без строк её нет (`_is_list_table`).
#
# Составная колонка (`location`): колонка «На следующей строке» (`OnNextRow`) стоит под предыдущей в её ячейке, колонка «В той же колонке»
# (`SameColumn`) — правее предыдущей в той же строке. Ширина составной колонки — наибольшая из сумм ширин её строк (в файле строки
# одной составной колонки в сумме равны её ширине); ячейки строки делят эту ширину пропорционально записанным ширинам, ячейка строки
# из одной колонки занимает её целиком. Шапка и подвал — по числу строк самой высокой составной колонки: строка 20 px градиента и линия
# 1 px, ячейка без строки под собой занимает все оставшиеся строки (градиент сплошной). Подпись такой ячейки переносится по буквам
# и словам, строки через 14 px. Проверено по шапке документа в предприятии (две строки, до пикселя). Подвал составных колонок
# нарисован ячейками колонок целиком, без деления на строки: деление на строки в подвале не проверено.
TABLE_HEADER, TABLE_PAD, TABLE_TEXT_PAD, TABLE_SCROLL = 20, 4, 7, 15
TABLE_ROW_STEP, TABLE_LINE_STEP = TABLE_HEADER + 1, 14
NEXT_ROW, SAME_COLUMN = "OnNextRow", "SameColumn"
TABLE_GRAD = ("#fffff7", "#f7efce")
TABLE_LINE, TABLE_SEP = "#cecaad", "#bdbd9c"


def column_width(head):
    """Ширина колонки из файла: число (строкой, если записана `1e2` или `162.9999999999999`) либо `None`. Слот ширины
    называется `width` у одних голов и `u4` у других (голова с вложенным элементом). Одна функция для рендера и досье (`brief.content.table_columns`)."""
    for key in ("width", "u4"):
        value = head.get(key)
        if isinstance(value, bool):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _rows_picture(head):
    """У колонки есть картинка строк (`rows_pictures`, источник не 0): значок в ячейках, ширина колонки при сжатии не падает ниже `PICTURE_COLUMN_MIN`."""
    picture = head.get("rows_pictures")
    return isinstance(picture, dict) and picture.get("source") not in (None, 0)


def table_columns(it, with_hidden=False):
    """`[{"head", "name", "header", "footer", "width", "fixed"}]` видимых колонок табличного поля в порядке файла; `[]` — колонок нет. `with_hidden` — и скрытые в файле
    (у них `hidden` истинно)."""
    block = edit.columns.columns_of(it.node)
    out = []
    for column in (block or {}).get(edit.columns.COLUMN_ITEMS) or []:
        base = edit.columns._column_base(column) if isinstance(column, dict) else None
        head = base.get(edit.columns.COLUMN_HEAD) if isinstance(base, dict) else None
        if not isinstance(head, dict):
            continue
        flags = head.get("flags") if isinstance(head.get("flags"), dict) else {}
        file_hidden = flags.get("visible") is False
        if file_hidden and not with_hidden:
            continue
        out.append({"hidden": file_hidden, "head": head, "name": head.get(edit.columns.COLUMN_NAME), "width": column_width(head),
                    "header": _first_text(head.get(edit.columns.COLUMN_HEADER_TEXT)),
                    "footer": _first_text(head.get("footer_text")), "fixed": head.get("size_change") == "DontChange",
                    "picture": _rows_picture(head),
                    "location": head.get(edit.columns.COLUMN_LOCATION),
                    "guid": (column.get(edit.columns.COLUMN_TYPE) or {}).get("guid") if isinstance(column.get(edit.columns.COLUMN_TYPE), dict) else None})
    return out


# Колонка с картинкой строк при сжатии не уже 25 px (колонка значка статуса шириной 28 в файле стоит 25 при сжатии остальных до 0,75, а не 21; проверено на одной колонке).
# Следующие колонки сдвигаются вправо на разницу (границы соседних колонок совпали до пикселя).
PICTURE_COLUMN_MIN = 25
MIN_SCALE = 0.75   # колонки не сжимаются сильнее: иначе таблица шире поля и получает горизонтальную прокрутку


def column_edges(columns, total):
    """Правые границы колонок (накопленные ширины, px): `[int]`. Колонки без ширины в файле берут среднюю. Колонки «Change»
    умножаются на `k = (total − фиксированные) / сумма`, но не меньше `MIN_SCALE`: тогда последняя граница больше `total`
    (таблица шире поля — горизонтальная прокрутка), а иначе последняя колонка берёт остаток."""
    known = [c["width"] for c in columns if c["width"]]
    mean = sum(known) / len(known) if known else 100.0
    widths = [c["width"] or mean for c in columns]
    fixed = sum(wd for c, wd in zip(columns, widths) if c["fixed"])
    flexible = sum(wd for c, wd in zip(columns, widths) if not c["fixed"])
    k = max(total - fixed, 0) / flexible if flexible else 1.0
    clamped = k < MIN_SCALE
    k = max(k, MIN_SCALE)
    edges, at = [], 0
    for n, (c, wd) in enumerate(zip(columns, widths)):
        at += wd if c["fixed"] else max(int(wd * k + 0.5), PICTURE_COLUMN_MIN if c.get("picture") else 0)
        edges.append(total if n == len(columns) - 1 and not clamped else at)
    return edges


def column_groups(columns):
    """Составные колонки: `[{rows: [[колонка, …], …], width, fixed}]` — колонки в порядке файла, сгруппированные по `location`. Первая колонка
    начинает группу, даже если у неё записано иное положение. Ширина группы — наибольшая сумма ширин её строк (колонка без ширины берёт
    среднюю); группа «не менять ширину», если такова каждая её колонка."""
    known = [c["width"] for c in columns if c["width"]]
    mean = sum(known) / len(known) if known else 100.0
    groups = []
    for c in columns:
        place = c.get("location")
        if groups and place == NEXT_ROW:
            groups[-1]["rows"].append([c])
        elif groups and place == SAME_COLUMN:
            groups[-1]["rows"][-1].append(c)
        else:
            groups.append({"rows": [[c]]})
    for g in groups:
        g["width"] = max(sum(c["width"] or mean for c in row) for row in g["rows"])
        g["fixed"] = all(c["fixed"] for row in g["rows"] for c in row)
        g["picture"] = any(c.get("picture") for row in g["rows"] for c in row)
    return groups


def column_cells(columns, total):
    """`(строк в шапке, [ячейка])`: ячейки колонок при ширине поля `total`. Ячейка — `{column, group, row, rows, below, left, right}`: `row` — строка
    составной колонки, `below` — под ней в той же составной колонке есть ещё строка, `rows` — на сколько строк шапки ячейка простирается (ячейка последней строки группы занимает остаток), `left` и `right` —
    края от левого края поля в px. Границы групп — как у `column_edges`."""
    groups = column_groups(columns)
    edges = column_edges(groups, total) if groups else []
    total_rows = max((len(g["rows"]) for g in groups), default=1)
    known = [c["width"] for c in columns if c["width"]]
    mean = sum(known) / len(known) if known else 100.0
    cells = []
    for n, (g, edge) in enumerate(zip(groups, edges)):
        left = edges[n - 1] if n else 0
        span = edge - left
        for r, row in enumerate(g["rows"]):
            widths = [c["width"] or mean for c in row]
            whole, acc, at = sum(widths), 0.0, left
            for k, (c, wd) in enumerate(zip(row, widths)):
                acc += wd
                right = edge if k == len(row) - 1 else left + int(acc / whole * span + 0.5)
                cells.append({"column": c, "group": n, "row": r, "rows": total_rows - r if r == len(g["rows"]) - 1 else 1,
                              "below": r < len(g["rows"]) - 1, "left": at, "right": right})
                at = right
    return total_rows, cells


def band_height(rows):
    """Высота градиента шапки или подвала из `rows` строк: строка 20 px и линия 1 px между строками."""
    return rows * TABLE_ROW_STEP - 1


def _wrap(text, avail, font, lines):
    """`(строки, усечена ли)`: подпись в ячейке шириной `avail` px не больше чем в `lines` строк. Подпись из одного слова, не вместившаяся в ячейку,
    переносится по буквам («Касса/счет» — «Касса/сче» и «т»). В подписи из нескольких слов перенос идёт по пробелам, а слово шире ячейки обрезается
    по ширине без «…» и остаток слова пропадает («Сумма прихода» в узкой ячейке — «Сум» и «при»). Последняя строка, не вместившая остаток
    подписи из одного слова, усекается с «…»."""
    if lines <= 1:
        shown, cut, _known = textmeasure.fit(text, avail, font)
        return [shown], cut
    wide = lambda s: textwidth.measure(s, font).px
    avail -= 1      # подпись, занявшая всю ширину, переносится: в предприятии «Объем» (35 px) в ячейке 42 px — «Объе / м»
    rest = text.strip()
    spaced = " " in rest
    out, cut = [], False

    def prefix(word):
        return word[:max((k for k in range(1, len(word) + 1) if wide(word[:k]) <= avail), default=1)]

    while rest and len(out) < lines:
        if wide(rest) <= avail:
            return out + [rest], cut
        if spaced:
            word, _sep, tail = rest.partition(" ")
            if len(out) < lines - 1 or wide(word) > avail:
                if wide(word) <= avail:        # слово помещается: строка набирается словами, пока они входят
                    line = word
                    while tail and wide(line + " " + tail.split(" ", 1)[0]) <= avail:
                        nxt, _s, tail = tail.partition(" ")
                        line += " " + nxt
                    out.append(line)
                else:
                    out.append(prefix(word))
                    cut = True
                rest = tail.lstrip()
                continue
        if len(out) == lines - 1:
            shown, was_cut, _known = textmeasure.fit(rest, avail + 1, font)
            return out + [shown], cut or was_cut
        n = len(prefix(rest))
        out.append(rest[:n].rstrip())
        rest = rest[n:].lstrip()
    return out, cut or bool(rest)


def _cell_lines(cell):
    """Сколько строк подписи вмещает ячейка: первая — в верхней строке шапки, дальше через `TABLE_LINE_STEP` до нижнего края."""
    return 1 + (band_height(cell["rows"]) - TABLE_HEADER) // TABLE_LINE_STEP


def _gradient(ident):
    return (f"<linearGradient id='{ident}' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='{TABLE_GRAD[0]}'/>"
            f"<stop offset='1' stop-color='{TABLE_GRAD[1]}'/></linearGradient>")


def _table_band(doc, it, cells, rows, x, top, w, shown, ident, key, scroll=0, hidden=None):
    """Полоса шапки или подвала из `rows` строк: градиент, разделители и подписи; `key` — `header` или `footer`. Ячейки шапки — по колонкам, подвала —
    по составным колонкам целиком. `hidden` — `{имя без регистра: кто скрыл}` колонок, скрытых безусловно (режим `hatch`): ячейка со штриховкой, без подписи."""
    clip = f"{ident}{key}"
    height = band_height(rows)
    out = []
    if rows == 1:
        out.append(f"<rect class='table-{key}' x='{_n(x + 1)}' y='{_n(top)}' width='{max(shown if scroll else w - 2, 0)}' height='{height}' fill='url(#{ident})'/>")        # у таблицы с полосой прокрутки шапка и подвал кончаются у левого края полосы
    else:
        for cell in cells:
            cell_top = top + TABLE_ROW_STEP * cell["row"] if key == "header" else top
            out.append(f"<rect class='table-{key}' x='{_n(x + 1 + cell['left'])}' y='{_n(cell_top)}' width='{max(cell['right'] - cell['left'], 0)}' "
                       f"height='{band_height(cell['rows']) if key == 'header' else height}' fill='url(#{ident})'/>")
    out.append(f"<clipPath id='{clip}'><rect x='{_n(x + 1)}' y='{_n(top)}' width='{max(shown, 0)}' height='{height}'/></clipPath><g clip-path='url(#{clip})'>")
    for cell in cells:
        c, left, right = cell["column"], x + 1 + cell["left"], x + 1 + cell["right"]
        cell_top = top + TABLE_ROW_STEP * cell["row"] if key == "header" else top
        cell_height = band_height(cell["rows"]) if key == "header" else height
        edge = cell["right"]
        last = edge == max(k["right"] for k in cells if k["group"] == cell["group"])
        if not last:      # граница между ячейками одной строки составной колонки
            out.append(_vline(x + edge + 0.5, cell_top, cell_top + cell_height, TABLE_SEP))
        elif edge < shown or scroll or edge > shown:  # правая граница последней колонки — рамка (без полосы прокрутки) и разделителя не имеет
            out.append(_vline(x + edge + 0.5, top, top + height, TABLE_SEP))
        if key == "header" and cell["below"]:      # линия между строками составной колонки
            out.append(f"<line class='table-line' x1='{_n(left)}' y1='{_n(cell_top + TABLE_HEADER + 0.5)}' x2='{_n(right)}' y2='{_n(cell_top + TABLE_HEADER + 0.5)}' stroke='{TABLE_LINE}'/>")
        text = c[key]
        if text:
            font = textwidth.element_font(c["head"], doc, key + "_font")
            lines, _cut = _wrap(text, right - left - TABLE_TEXT_PAD, font, _cell_lines(cell) if key == "header" else 1)
            align = c["head"].get(key + "_horizontal_align")
            for n, line in enumerate(lines):
                baseline = cell_top + 14 + TABLE_LINE_STEP * n
                if align == "Right":
                    out.append(_text(right - 3, baseline, line, "end", font))
                elif align == "Center":
                    out.append(_text((left + right) / 2, baseline, line, "middle", font))
                else:
                    out.append(_text(left + TABLE_PAD - 1, baseline, line, font=font))
    out.append("</g>")
    if key == "header" and hidden:
        for n, cell in enumerate(cells):
            name = (cell["column"].get("name") or "").casefold()
            at = (x + 1 + cell["left"], top + TABLE_ROW_STEP * cell["row"], cell["right"] - cell["left"], band_height(cell["rows"]))
            if name in hidden:
                out += hidden_overlay(*at, hidden[name])
    return out


def _footer_cells(cells, rows):
    """Ячейки подвала: по одной на составную колонку (подпись первой колонки группы), на все строки подвала."""
    out = []
    for n in sorted({c["group"] for c in cells}):
        mine = [c for c in cells if c["group"] == n]
        out.append(dict(mine[0], row=0, rows=rows, below=False, left=min(c["left"] for c in mine), right=max(c["right"] for c in mine)))
    return out


def coded_columns(columns, gone=(), new=(), retitle=None, show=(), hatch_file=False):
    """Колонки с учётом разбора кода: убранные безусловно (`gone` — имена без регистра) выпадают, созданные (`new` — `[{name, title}]`) встают в конец с шириной
    по умолчанию, подписи, которые код ставит безусловно (`retitle` — `{имя без регистра: подпись}`), заменяют подписи файла."""
    out = [c for c in columns if (c["name"] or "").casefold() not in gone and (not c.get("hidden") or hatch_file or (c["name"] or "").casefold() in show)]
    for c in out:
        if retitle and (c["name"] or "").casefold() in retitle:
            c["header"] = retitle[(c["name"] or "").casefold()]
    have = {(c["name"] or "").casefold() for c in columns}
    for add in new or ():
        if add["name"].casefold() not in have:
            out.append({"head": {}, "name": add["name"], "width": None, "header": add["title"], "footer": None, "fixed": False, "picture": None, "location": None,
                        "guid": None, "added": True})
    return out


def hidden_in_file(it, show=()):
    """`{имя колонки без регистра: имя как в файле}` колонок, скрытых в файле и не показанных запросом."""
    return {(c["name"] or "").casefold(): c["name"] for c in table_columns(it, True) if c.get("hidden") and c.get("name") and (c["name"] or "").casefold() not in show}


def _table_box(doc, it, x, y, w, h, gone=(), new=(), retitle=None, show=(), hatch_file=False, hidden=None):
    """`hidden` — `{имя без регистра: кто скрыл}` колонки, скрытые безусловно кодом или запросом и оставленные на месте
    (режим `hatch`); с `hatch_file` к ним добавляются скрытые в файле («файл»)."""
    hidden = {**(hidden or {}), **{name: "файл" for name in hidden_in_file(it, show)}} if hatch_file else dict(hidden or {})
    columns = coded_columns(table_columns(it, with_hidden=bool(show) or hatch_file), gone, new, retitle, show, hatch_file)
    flags = _table_flags(it)
    scroll = TABLE_SCROLL if _is_list_table(it, columns) else 0
    shown = max(w - 2 - scroll, 0)
    rows, cells = column_cells(columns, shown) if columns else (1, [])
    bh = band_height(rows)
    hscroll = bool(cells) and max(c["right"] for c in cells) > shown and h > bh + SCROLL_BAR + 4       # колонки шире поля: горизонтальная прокрутка под подвалом (одно наблюдение)
    below = SCROLL_BAR if hscroll else 0
    footer = (1 + bh if flags.get("footer") is True else 0) + below      # полоса подвала с линией над ней и полоса прокрутки под ним
    ident = f"tg{it.index}"
    out = [f"<defs>{_gradient(ident)}<clipPath id='{ident}c'><rect x='{_n(x + 1)}' y='{_n(y + 1)}' width='{_n(max(w - 2, 0))}' height='{_n(max(h - 2, 0))}'/></clipPath></defs>",
           f"<g clip-path='url(#{ident}c)'>"]       # шапка, тело и подвал не выходят за внутреннюю границу рамки
    if flags.get("header") is not False and h > bh + 1:
        out += _table_band(doc, it, cells, rows, x, y + 1, w, shown, ident, "header", scroll, hidden)
        out.append(f"<line class='table-line' x1='{_n(x + 1)}' y1='{_n(y + bh + 1.5)}' x2='{_n(x + 1 + shown if scroll else x + w - 1)}' y2='{_n(y + bh + 1.5)}' stroke='{TABLE_LINE}'/>")
    if flags.get("footer") is True and h > 2 * bh + 3:
        out.append(f"<line class='table-line' x1='{_n(x + 1)}' y1='{_n(y + h - bh - 1.5 - below)}' x2='{_n(x + 1 + shown if scroll else x + w - 1)}' y2='{_n(y + h - bh - 1.5 - below)}' stroke='{TABLE_LINE}'/>")
        out += _table_band(doc, it, _footer_cells(cells, rows), rows, x, y + h - 1 - bh - below, w, shown, ident, "footer", scroll)
    if hscroll:
        out.append(_scroll_bar(x + 1, y + h - 1 - SCROLL_BAR, w - 2 - scroll, SCROLL_BAR))
    if scroll and h > bh + 4:
        top = y + 1             # вертикальная полоса начинается от верхней рамки и перекрывает строку шапки: её первая кнопка стоит на уровне шапки
        bottom = y + h - 1 - footer
        out.append(_scroll_bar(x + w - 1 - scroll, top, scroll, max(bottom - top, 0)))
    out.append("</g>")
    return out


def column_screen_widths(it, width):
    """Ширина ячеек видимых колонок табличного поля на экране (px, целые) при ширине таблицы `width`: в порядке `table_columns`; пусто — колонок нет.
    Платформа сжимает колонки, когда их сумма больше таблицы (`column_edges`), поэтому она может быть иной, чем в файле (`column_width`);
    ячейка колонки «На следующей строке» или «В той же колонке» — по правилу составной колонки (`column_cells`)."""
    columns = table_columns(it)
    if not columns:
        return []
    scroll = TABLE_SCROLL if _is_list_table(it, columns) else 0
    _rows, cells = column_cells(columns, max(width - 2 - scroll, 0))
    return [cell["right"] - cell["left"] for cell in cells]


def header_cuts(doc, it, width):
    """Заголовки видимых колонок табличного поля шириной `width` px (по файлу), которые шапка усекает с «…»: `[{column, text, need, have, exact, why}]`.
    Ширина ячеек и место под текст — те же, что при рисовании (`column_cells`, `TABLE_TEXT_PAD`): `have` — ширина ячейки, `need` — текст плюс отступ;
    ячейка, занимающая несколько строк шапки, переносит подпись и усекает только остаток."""
    columns = table_columns(it)
    if not columns or _table_flags(it).get("header") is False:
        return []
    scroll = TABLE_SCROLL if _is_list_table(it, columns) else 0
    _rows, cells = column_cells(columns, max(width - 2 - scroll, 0))
    out = []
    for cell in cells:
        c = cell["column"]
        text = c["header"]
        if not text:
            continue
        font = textwidth.element_font(c["head"], doc, "header_font")
        have = cell["right"] - cell["left"]
        _lines, cut = _wrap(text, have - TABLE_TEXT_PAD, font, _cell_lines(cell))
        if not cut:
            continue
        got = textwidth.measure(text, font)
        out.append({"column": c["name"], "text": text, "need": got.px + TABLE_TEXT_PAD, "have": have, "exact": bool(got.exact), "why": None if got.exact else got.why})
    return out


def _table_flags(it):
    """Флаги табличного поля (`header`, `footer` …): тот же поиск, что у досье (`brief.content.table_flags`)."""
    def walk(value):
        if isinstance(value, dict):
            flags = value.get("flags")
            if isinstance(flags, dict) and "read_only" in flags and "header" in flags:
                return flags
            for key, sub in value.items():
                if key in ("columns", "elements") or key == edit.columns.COLUMN_ITEMS:
                    continue
                found = walk(sub)
                if found:
                    return found
        return None
    return walk((it.node or {}).get("content")) or {}


def _is_list_table(it, columns):
    """Таблица на динамический список (колонки вида «колонка списка»): строки в базе есть, полоса прокрутки показана."""
    return bool(columns) and all(c.get("guid") == edit.platform.LIST_COLUMN for c in columns)
