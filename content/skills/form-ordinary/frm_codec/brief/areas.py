"""Синтез «что это за форма» для обзора: области формы с положением, подписью и главным элементом.

Читает только `brief.json` (список элементов с местом и размером, страницы панелей): верхний уровень формы делится на шапку, подвал, крупные области и «остальное»; про
каждое называется положение на форме, что внутри и что в области главное. Главное на форме — самый крупный по площади элемент-содержимое (таблица, поле табличного
документа, текстовое поле, диаграмма), если он занимает заметную долю формы.
"""

import collections

CONTENT_WORDS = {"TableBox": "таблица", "SpreadsheetDocumentField": "поле табличного документа", "TextDocumentField": "текстовое поле",
                 "HTMLDocumentField": "поле HTML", "Chart": "диаграмма", "GanttChart": "диаграмма Ганта", "PivotChart": "сводная диаграмма",
                 "Dendrogram": "дендрограмма", "PictureBox": "картинка", "PDFDocumentField": "поле PDF", "GeographicalSchemaField": "географическая схема",
                 "GraphicalSchemaField": "графическая схема"}
BAND = 0.2             # доля высоты формы: выше неё лежит шапка, ниже (1 − BAND) — подвал
BIG = 0.06             # доля площади формы, с которой элемент верхнего уровня считается областью
MAIN = 0.12            # доля площади формы, с которой содержимое называется главным
LISTED = 5             # названий в одном перечне
REGIONS = 6            # областей в синтезе не больше стольких


def _box(e):
    return e["x"], e["y"], e["x"] + e["width"], e["y"] + e["height"]


def _area(e):
    return max(e["width"], 0) * max(e["height"], 0)


def _clean(text):
    return " ".join((text or "").replace(":", " ").split()).strip()


def _list(names, limit=LISTED):
    shown = ", ".join(names[:limit])
    return shown + (f" и ещё {len(names) - limit}" if len(names) > limit else "")


def _where(box, width, height):
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    full = (x2 - x1) >= 0.85 * width
    if full:
        return "сверху" if cy < height / 3 else "снизу" if cy > 2 * height / 3 else "в середине"
    side = "слева" if cx < 0.4 * width else "справа" if cx > 0.6 * width else "в центре"
    if (y2 - y1) < 0.5 * height:
        side += " вверху" if cy < height / 3 else " внизу" if cy > 2 * height / 3 else ""
    return side


def _inside(rows, name):
    """Элементы, лежащие внутри панели `name` на любой глубине."""
    prefix = name + "/"
    return [r for r in rows if r["element"].startswith(prefix)]


def _pages_of(brief, element):
    """`(подписи страниц панели, показаны ли закладки)`."""
    found = [p for p in brief["structure"]["pages"] if p["panel"] == element and p["caption"]]
    return [p["caption"] for p in found], bool(found and found[0]["tabs_shown"])


def _content_name(brief, e):
    return f"{CONTENT_WORDS[e['type']]} «{e['short']}»"


def _main_inside(brief, rows):
    """Самое крупное содержимое среди `rows` — строка элемента либо `None`."""
    found = [r for r in rows if r["type"] in CONTENT_WORDS and r["type"] != "PictureBox"]
    return max(found, key=_area) if found else None


def _open_page(brief, panel):
    """Подпись открытой страницы панели — первой из нарисованных на `clean.png`; `None`, если у панели нет страниц или ни одна не нарисована."""
    skip = set((brief.get("images") or {}).get("not_drawn") or [])
    for page in brief["structure"]["pages"]:
        if page["panel"] == panel and page["caption"] and page.get("node") not in skip:
            return page["caption"]
    return None


def _frames(rows):
    """Подписи рамок групп среди `rows`."""
    out = []
    for r in sorted((r for r in rows if r["type"] == "GroupBox"), key=lambda r: (r["y"], r["x"])):
        text = _clean(r.get("caption"))
        if any(ch.isalpha() for ch in text):
            out.append(f"«{text}»")
    return list(dict.fromkeys(out))


def _panel_text(brief, panel, rows, visible):
    """Слова об элементе-панели: страницы, открытая страница и главное содержимое. Берутся только нарисованные элементы (`rows` уже отсеяны), поэтому описана открытая закладка."""
    inner = [r for r in _inside(rows, panel["element"]) if r["element"] not in visible.get("hidden", ())]
    pages, tabs = _pages_of(brief, panel["element"])
    main = _main_inside(brief, inner)
    bits = []
    if pages:
        opened = _open_page(brief, panel["element"])
        bits.append(("закладки " if tabs else "страницы (переключает код) ") + _list([f"«{p}»" for p in pages], 4) + (f"; открыта «{opened}»" if opened else ""))
    frames = _frames(inner)
    if frames:
        bits.append("рамки " + _list(frames, 4))
    fields = _fields(inner)
    if fields:
        bits.append("поля " + _list(fields, 5))
    if main is not None:
        bits.append(_content_name(brief, main))
    return f"панель «{panel['short']}»" + (" — " + "; ".join(bits) if bits else "")


def _fields(rows, limit=LISTED):
    """Подписи полей: надписи с текстом, без двоеточий, в порядке чтения."""
    labels = sorted((r for r in rows if r["type"] == "Label" and _clean(r.get("caption"))), key=lambda r: (r["y"] // 12, r["x"]))
    names = [_clean(r["caption"]) for r in labels]
    return list(dict.fromkeys(n for n in names if len(n) <= 32 and any(ch.isalpha() for ch in n) and '"' not in n))


def build(brief):
    """`{lines: [строки], main: имя главного или None}` — области формы словами; пусто, если синтез строить не из чего.

    Если всю форму занимает одна панель без страниц, области описаны внутри неё."""
    width, height = brief["head"]["size"]
    hidden = set(brief["structure"].get("hidden", ())) | undrawn_elements(brief) | _hidden_by_code(brief)
    rows = [r for r in brief["structure"]["elements"] if r["element"] not in hidden and not _under_hidden(r, hidden)]      # только нарисованное и видимое
    lines, regions, others, region_lines = _level(brief, rows, "", width, height, hidden)
    if len(regions) == 1 and regions[0]["type"] == "Panel" and _area(regions[0]) >= 0.5 * width * height:
        panel = regions[0]
        inner = _level(brief, rows, panel["element"] + "/", max(panel["width"], 1), max(panel["height"], 1), hidden)[0]
        if len(inner) >= 2:
            pages, tabs = _pages_of(brief, panel["element"])
            opened = _open_page(brief, panel["element"])
            head = f"Всю форму занимает панель «{panel['short']}»" + (f" ({'закладки' if tabs else 'страницы, переключает код'} {_list([f'«{p}»' for p in pages], 6)}); открыта «{opened}»" if pages and opened else "")
            lines = [x for x in lines if x != region_lines.get(panel["element"])] + [head + ", внутри неё:"] + ["  " + line for line in inner]
    return {"lines": lines, "main": _main(brief, rows, hidden, width * height)}


def _main(brief, rows, hidden, form_area):
    biggest = max((r for r in rows if r["element"] not in hidden and r["type"] in CONTENT_WORDS and r["type"] != "PictureBox" and not _under_hidden(r, hidden)), key=_area, default=None)
    if biggest is not None and _area(biggest) >= MAIN * max(form_area, 1):
        return _content_name(brief, biggest)
    return None


def _level(brief, rows, prefix, width, height, hidden):
    """`(строки, области, остальное)` одного уровня: элементы с приставкой `prefix` и без вложенных имён."""
    top = [r for r in rows if r["element"].startswith(prefix) and "/" not in r["element"][len(prefix):] and r["element"] not in hidden]
    if not top:
        return [], [], [], {}
    visible = {"hidden": hidden}
    form_area = max(width * height, 1)
    head_bits, foot_bits, regions, rest, frames = [], [], [], [], []
    boxes = [g for g in top if g["type"] == "GroupBox"]
    for r in sorted(top, key=lambda r: (r["y"], r["x"])):
        x1, y1, x2, y2 = _box(r)
        in_frame = any(g is not r and _contained(r, g) for g in boxes)          # надпись внутри рамки группы принадлежит рамке, а не шапке и не подвалу
        if r["type"] in ("Splitter", "GroupBox") and _area(r) < BIG * form_area:
            if r["type"] == "GroupBox" and any(ch.isalpha() for ch in _clean(r.get("caption"))):
                frames.append(_clean(r["caption"]))
            continue
        if y2 <= BAND * height and not in_frame and r["type"] in ("Button", "CommandBar", "Label", "PictureBox") and _area(r) < 0.5 * form_area:
            head_bits.append(r)
        elif y1 >= (1 - BAND) * height and not in_frame and r["type"] in ("Button", "CommandBar", "Label", "CheckBox") and _area(r) < 0.5 * form_area:
            foot_bits.append(r)
        elif _area(r) >= BIG * form_area and r["type"] in ("Panel", "GroupBox", "TableBox", "SpreadsheetDocumentField", "TextDocumentField", "HTMLDocumentField",
                                                            "Chart", "GanttChart", "PivotChart", "Dendrogram", "PDFDocumentField", "GeographicalSchemaField",
                                                            "GraphicalSchemaField", "PictureBox"):
            regions.append(r)
        else:
            rest.append(r)
    lines, region_lines = [], {}

    def bar_text(bits):
        buttons = [_clean(r["caption"]) for r in bits if r["type"] == "Button" and any(ch.isalpha() for ch in _clean(r.get("caption")))]
        bars = [f"«{r['short']}»" for r in bits if r["type"] == "CommandBar"]
        labels = [f"«{_clean(r['caption'])}»" for r in bits if r["type"] == "Label" and any(ch.isalpha() for ch in _clean(r.get("caption")))]
        out = []
        if bars:
            out.append("командная панель " + _list(bars, 3))
        if buttons:
            out.append("кнопки " + _list(buttons, 5))
        if labels:
            out.append("надписи " + _list(labels, 3))
        return ", ".join(out)
    if head_bits and bar_text(head_bits):
        lines.append("Сверху: " + bar_text(head_bits))
    chosen = sorted(regions, key=lambda r: -_area(r))[:REGIONS]
    for r in sorted(chosen, key=lambda r: (int(r["y"] // max(height / 8, 1)), r["x"])):
        place = _where(_box(r), width, height)
        if r["type"] == "Panel":
            text = _panel_text(brief, r, rows, visible)
        elif r["type"] == "GroupBox":
            text = f"рамка «{_clean(r.get('caption')) or r['short']}»"
            inner = [q for q in rest if _contained(q, r)]
            fields = _fields(inner)
            if fields:
                text += " — поля " + _list(fields)
        else:
            text = _content_name(brief, r)
        line = f"{place[0].upper() + place[1:]}: {text}"
        region_lines[r["element"]] = line
        lines.append(line)
    if frames:
        lines.append("Рамки групп: " + _list([f"«{f}»" for f in dict.fromkeys(frames)], 5))
    fields = _fields([r for r in rest if not any(_contained(r, g) for g in regions if g["type"] == "GroupBox")])
    if fields:
        lines.append("Поля формы: " + _list(fields, 6))
    if foot_bits and bar_text(foot_bits):
        lines.append("Внизу: " + bar_text(foot_bits))
    others = [r for r in rest if r["type"] not in ("Label", "Splitter", "GroupBox")]
    return lines, regions, others, region_lines


def _contained(small, big):
    sx1, sy1, sx2, sy2 = _box(small)
    bx1, by1, bx2, by2 = _box(big)
    return sx1 >= bx1 - 2 and sy1 >= by1 - 2 and sx2 <= bx2 + 2 and sy2 <= by2 + 2


def undrawn_elements(brief):
    """Имена элементов, которых нет на `clean.png`: лежащих в узлах из `images.not_drawn` (ненарисованные страницы и скрытое) и под ними."""
    skip = set((brief.get("images") or {}).get("not_drawn") or [])
    out = set()

    def walk(node, dead):
        dead = dead or node["id"] in skip
        if dead:
            out.update(node.get("elements") or [])
        for child in node.get("children") or []:
            walk(child, dead)
    tree = (brief.get("structure") or {}).get("tree")
    if tree:
        walk(tree, False)
    return out


def _hidden_by_code(brief):
    """Элементы, которые код прячет безусловно: на экране их нет, в областях и главном они не называются."""
    effects = (brief.get("purpose", {}).get("module") or {}).get("effects") or []
    return {e["element"] for e in effects if e.get("part") is None and (e.get("applied") or {}).get("видимость") == "Ложь"}


def _under_hidden(row, hidden):
    parts = row["element"].split("/")
    return any("/".join(parts[:i]) in hidden for i in range(1, len(parts)))
