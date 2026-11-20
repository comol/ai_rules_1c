"""Сборка рисунка: таблица видов элементов (`DRAW`), замечания по элементу, варианты на одном месте и сама `render` — клиентская область формы в SVG."""
import re
from xml.sax.saxutils import quoteattr

from .. import bar_platform, edit, layout, platform_pictures, textwidth, validate, variants
from ..layout import fold
from ..edit import ctxmenu as _ctxmenu
from .core import (
    CALIBRATED, DISABLED_FIELD, DISABLED_NOTE, OFF_FILTER, OFF_FILTER_ID, FIELD_BUTTON, FORM_BG, FRAME_NOT_CLAIMED, NESTED_NOTES, PANEL_FRAME_MEASURED, Rendered,
    SCROLL_BAR, STRIP, Unmeasured, _back_of, _clean, _color_of, _dig, _enabled, _first_text, _font_of, _form_enabled, _grey, _n, _scroll_bar, _text, PICTURE_UNSEEN_NOTE, picture_box_empty, picture_box_unseen,
    absolute)
from . import picture_places
from .marks import CODE_DEFS, CODE_TEXT_TYPES, hidden_overlay, overlay_layer
from .bars import (
    AUTO_FILL_KNOWN_NOTE, AUTO_FILL_NOTE, FORM_BAR_FILL, ICON_NOTE, NO_ACTION_NOTE, VERTICAL_NOTE, _auto_fill_bar, _auto_fill_known, _bar_buttons,
    _command_bar, _file_entries, _form_bar_line, bar_fill, bar_back_notes, _form_kind, _action_source_is_table, bar_vertical)
from .fields import DATE_MASK, DATE_MASK_NOTE, FIELD_BUTTON_NAMES, OPEN_DEFAULT_NOTE, bound_elements, _button, _check_box, _date_fractions, _field_class, _field_flags, _field_view, _label, _radio_button, _sheet_box, _text_box, field_text, open_defaults, radio_selected, value_text
from .tables import NEXT_ROW, SAME_COLUMN, _is_list_table, _table_box, hidden_in_file, table_columns
from .panels import _frame, _group_box, _panel, _panel_frame_box
from . import charts


DRAW = {"Label": _label, "TextBox": _text_box, "Button": _button, "CheckBox": _check_box, "RadioButton": _radio_button,
        "CommandBar": _command_bar, "TableBox": _table_box, "Panel": _panel, "GroupBox": _group_box,
        "ComboBox": _text_box, "SpreadsheetDocumentField": _sheet_box, "PictureBox": picture_places.picture_box, "ListBox": lambda *a: [],
        "Splitter": lambda *a: [], "TextDocumentField": lambda *a: [], **charts.DRAW}      # поле текстового документа — белое поле с рамкой: многострочный текст в нём не рисуется
# Рисунок значений снят в предприятии (опыт e230): галочка, точка, текст в поле, Булево, Дата, надпись. Слова остаются у того, что не снималось.
VALUE_TYPES = ("CheckBox", "RadioButton", "TextBox", "ComboBox", "Label")
VALUE_NOTES = {"TextBox": "значение в поле ввода нарисовано по снимку предприятия; «Нет» у Ложь не снималось",
               "ComboBox": "значение в поле выбора нарисовано, только когда оно есть в списке выбора (так показало предприятие; без списка поле выбора пусто); прочие сочетания не снимались"}
FILL = {"Label": "none", "Panel": "none", "GroupBox": "none", "Splitter": "none",
        "CheckBox": "none", "RadioButton": "none", "ProgressBar": "none", "GanttChart": "none"}


PANEL_BACK_NOTE = "заливка панели явным цветом фона (страницы под закладками, у панели без закладок — весь прямоугольник) не сверена с предприятием"
FORM_BACK_NOTE = "заливка формы явным цветом фона не сверена с предприятием; элементы, залитые цветом формы по умолчанию (#FFFFEF), остались им"


def _panel_color(it):
    """Явный цвет фона непрозрачной панели (`#rrggbb`) либо `None`."""
    kind, color, _words = _back_of(it.node)
    return color if kind == "rgb" and _dig(it.node, "content", "u1", "u0", "transparent") is not True else None


def _panel_back(it, page, box):
    """Заливка панели явным цветом фона, если она не прозрачная: страница внутри линий (на 1 px внутрь); у панели без линий страницы — весь её box."""
    color = _panel_color(it)
    if color is None:
        return []
    if page is None:
        bx, by, bw, bh = box
        return [f"<rect class='panel-back' x='{_n(bx)}' y='{_n(by)}' width='{_n(bw)}' height='{_n(bh)}' fill='{color}' stroke='none'/>"]
    bx, by, bw, bh = page
    return [f"<rect class='panel-back' x='{_n(bx + 1)}' y='{_n(by + 1)}' width='{_n(max(bw - 2, 0))}' height='{_n(max(bh - 2, 0))}' fill='{color}' stroke='none'/>"]


def _back_notes(it):
    """Слова о цвете фона, который рендер не знает: цвет стиля или системный; явный цвет панели не сверялся."""
    if it.type == "CommandBar":
        return bar_back_notes(it)
    if it.type not in ("Label", "Panel"):
        return []
    kind, _color, words = _back_of(it.node)
    if it.type == "Panel" and _panel_color(it) is not None:
        return [PANEL_BACK_NOTE]
    if kind == "other":
        name = "надписи" if it.type == "Label" else "панели"
        return [f"цвет фона {name} задан стилем или системой ({words}): заливки нет"]
    return []


def _item_notes(it, doc=None):
    """Что рендер не знает об этом элементе, словами: `[строка]` (одна строка на вид, `render` объединяет их без
    повторов)."""
    out = picture_places.item_notes(it) + _back_notes(it)
    if it.type in CODE_TEXT_TYPES:
        why = _color_of(it.node)[1]
        if why:
            paint = "цветом заголовка рамки #9C6700" if it.type == "GroupBox" else "цветом темы #423100"
            out.append(f"цвет текста подписи задан стилем или системой ({why}): подпись нарисована {paint}")
    if it.type == "TextBox" and doc is not None and _field_class(it, doc) == "dateTime":
        off = _enabled(it.node) is False or not _form_enabled(doc)
        if _date_fractions(doc, it) not in DATE_MASK or off or _field_view(it) == 82:
            out.append(DATE_MASK_NOTE)
    if it.type in ("TextBox", "ComboBox"):
        names = [FIELD_BUTTON_NAMES[f] for f in _field_flags(it) if f in FIELD_BUTTON_NAMES]
        if names:
            out.append(f"ширина кнопок поля ввода ({', '.join(names)}) не проверялась: нарисованы по {FIELD_BUTTON} px (с чертой), как "
                       "кнопка выбора (проверена)")
        if it.type == "ComboBox":
            out.append("у поля выбора кнопка раскрытия списка нарисована по снимкам предприятия (у поля со списком и без списка, 16 px, стрелка); скруглённые углы рамки поля выбора не нарисованы: вид углов зависит от версии формы и у поля выбора не сверялся")
    elif it.type == "RadioButton":
        out.append("у переключателя положение подписи (`title_location`) и выравнивание рисуются по карте, как у флажка; "
                   "круг, точка и отступ подписи сняты в предприятии; положение подписи слева и выравнивание не проверялись")
    elif it.type == "SpreadsheetDocumentField":
        content = _dig(it.node, "content")
        if _dig(content, "show_grid") is True or _dig(content, "show_headers") is True:
            out.append("у поля табличного документа с сеткой или заголовками вид не проверялся (клетка снята при выключенных): "
                       "нарисована только клетка")
    elif it.type == "TableBox":
        columns = table_columns(it)
        if _is_list_table(it, columns):
            out.append("у списка состав и ширины колонок на экране зависят от настройки списка у пользователя (в файле её нет): "
                       "нарисованы колонки файла, полоса прокрутки списка нарисована всегда")
        if any(c["width"] is None for c in columns):
            out.append("у колонки без ширины в файле взята средняя ширина колонок таблицы")
        if any(c.get("location") in (NEXT_ROW, SAME_COLUMN) for c in columns):
            out.append("у таблицы составные колонки (положение «На следующей строке» или «В той же колонке»): шапка нарисована в несколько строк, "
                       "подпись ячейки на несколько строк переносится; подвал, если он включён, нарисован ячейками колонок целиком, без деления на строки — деление в подвале не проверялось")
    elif it.type == "CommandBar":
        box = getattr(it, "box", None)
        if box and bar_vertical(it.node, box[2] - box[0], box[3] - box[1]) and not _auto_fill_bar(it, doc):
            out.append(VERTICAL_NOTE)
        elif _auto_fill_bar(it, doc):
            out.append(AUTO_FILL_NOTE)
        elif _auto_fill_known(it, doc):
            out.append(AUTO_FILL_KNOWN_NOTE)
            if _form_kind(doc) == "document.item" and bar_platform.current().get("posting") is None and not _action_source_is_table(it.node):
                out.append(bar_platform.POSTING_UNKNOWN_NOTE)
        elif any(rep == "Picture" for _k, _t, rep, _w in _bar_buttons(it.node)):
            out.append(ICON_NOTE)
    return out


# Подписи, которые рендер пишет шрифтом элемента, и где лежит текст: надпись и кнопка формы —
# `content/u1/caption`, флажок — `content/u1/u0/caption`, переключатель — `content/u2/u0/caption`, рамка группы
# — `content/u1/caption`.
CAPTION_PATH = {"Label": ("content", "u1", "caption"), "Button": ("content", "u1", "caption"),
                "CheckBox": ("content", "u1", "u0", "caption"), "RadioButton": ("content", "u2", "u0", "caption"),
                "GroupBox": ("content", "u1", "caption")}


def caption_text(node, kind):
    """Подпись элемента вида `kind` точно в том виде, как она лежит в файле (пробел перед подписью флажка в
    платформенных формах сохраняется: он занимает 3 px), либо пустая строка."""
    path = CAPTION_PATH.get(kind)
    return _first_text(_dig(node, *path)) if path else ""


def _font_note(doc, it):
    """Строка для `notes`, если шрифт подписи элемента не проверялся (`textwidth.measure`: `exact` ложно): подпись
    нарисована и усечена по оценке ширины. Если подписи нет, заметки нет."""
    path = CAPTION_PATH.get(it.type)
    text = _first_text(_dig(it.node, *path)) if path else ""
    if not text:
        return None
    got = textwidth.measure(text, _font_of(doc, it))
    if got.exact:
        return None
    return f"шрифт подписи «{it.qualified()}» не проверялся ({got.why}): подпись нарисована и усечена по оценке ширины"


def _hidden(form, item, shown):
    """Элемент не на показанной странице своей панели или формы. Модель (`layout.hidden_page`) считает скрытыми
    страницы панелей и форм с закладками «Сверху» или «Не отображать». У формы с другими закладками модель
    страницы не скрывает, поэтому рендер сам не рисует страницу, которая не показана: показана страница из
    `shown`, иначе нулевая."""
    if layout.hidden_page(item, shown):
        return True
    if item.lazy or item.page is None:
        return False
    return item.page != (shown or {}).get(item.holder, 0)


def context_menu_bars(doc):
    """Индексы командных панелей, которые служат контекстными меню элементов (`context_menu_links`): на экране они появляются по правой кнопке, на форме их нет. Связь с
    неразобранным строением — пусто (рисуется как раньше)."""
    try:
        rows = _ctxmenu.read(doc)
    except edit.EditError:
        return frozenset()
    return frozenset(r["menu"] for r in rows if isinstance(r.get("menu"), int) and not isinstance(r["menu"], bool) and r["menu"] >= 0 and r["menu"] != r["owner"])


def _page_name(form, owner, at):
    """Имя страницы панели (или формы, `owner` 0) в файле; безымянной — «страница N»."""
    holder = form.holders.get(owner)
    block = holder.block if holder is not None else None
    pages = block.get(edit.names.PAGES) if isinstance(block, dict) else None
    items = pages.get(edit.names.PAGE_ITEMS) if isinstance(pages, dict) else None
    row = items[at] if isinstance(items, list) and 0 <= at < len(items) else None
    name = row.get(edit.names.PAGE_NAME) if isinstance(row, dict) else None
    return name if isinstance(name, str) and name else f"страница {at}"


def page_names_of(form, owner):
    """`{номер страницы с нуля: имя}` страниц панели (или формы, `owner` 0) по файлу; безымянная называется «страница N» (так же её называет `--state`)."""
    holder = form.holders.get(owner)
    block = holder.block if holder is not None else None
    pages = block.get(edit.names.PAGES) if isinstance(block, dict) else None
    items = pages.get(edit.names.PAGE_ITEMS) if isinstance(pages, dict) else None
    return {at: _page_name(form, owner, at) for at in range(len(items))} if isinstance(items, list) else {}


def _bar_names(it):
    """`{имя кнопки без регистра: имя как в файле}` кнопок командной панели."""
    return {(e["name"]).casefold(): e["name"] for e in _file_entries(it.node) if e.get("name")}


def _applied_words(form, marks):
    """Слова о том, что на рисунке применено: `[строка]`; пусто — ничего. Что поставил явный запрос (`marks.asked`) — «по запросу применено …» (слова самого запроса в `requested`),
    что взято из разбора кода — «по разбору кода применено …»; имена страниц, колонок и кнопок — как в файле."""
    if marks is None:
        return []
    out = []
    parts = getattr(marks, "parts", None) or {}
    applied = getattr(marks, "applied", None) or {}
    asked = getattr(marks, "asked", None) or set()
    hatch = getattr(marks, "hatch_hidden", False)
    for line in getattr(marks, "requested", None) or ():
        out.append("по запросу применено: " + line)
    if getattr(marks, "form_disabled", False):
        out.append("по разбору кода применено, форма недоступна целиком: все элементы серые")

    def name(index):
        return form.items[index].qualified() if index in form.items else f"#{index}"

    hidden = sorted(name(i) for i, p in applied.items() if p.get("видимость") == "Ложь" and i not in (getattr(marks, "force_show", None) or ()) and ("el", i, "видимость") not in asked)
    if hidden and not hatch:
        out.append("по разбору кода применено, не нарисованы (видимость Ложь или убраны): " + ", ".join(hidden)
                   + "; раскладка соседних элементов посчитана как при видимых")
    asked_hidden = sorted(name(i) for i, p in applied.items() if p.get("видимость") == "Ложь" and ("el", i, "видимость") in asked)
    if asked_hidden and not hatch:
        out.append("по запросу применено, не нарисованы (видимость Ложь): " + ", ".join(asked_hidden) + "; раскладка соседних элементов посчитана как при видимых")
    off = sorted(name(i) for i, p in applied.items() if p.get("доступность") == "Ложь" and ("el", i, "доступность") not in asked)
    if off:
        out.append("по разбору кода применено, нарисованы серыми (недоступны): " + ", ".join(off))
    titles = sorted(name(i) for i, p in applied.items() if p.get("заголовок") and ("el", i, "заголовок") not in asked)
    if titles:
        out.append("по разбору кода применено, заголовок задан кодом: " + ", ".join(titles))
    if not hatch:       # в режиме `hatch` страницы, колонки и кнопки остаются на месте со штриховкой: об этом говорит заметка о скрытом, а не «убраны»
        gone = sorted(f"{name(owner)}: {_page_name(form, owner, at)}" for (owner, at), p in (parts.get("applied_pages") or {}).items()
                      if p.get("видимость") == "Ложь" and ("page", owner, at) not in asked)
        if gone:
            out.append("по разбору кода применено, страницы убраны: " + ", ".join(gone))
    gone = []       # скрытая колонка не рисуется и ширины не занимает в обоих режимах
    for (owner, column), p in (parts.get("applied_columns") or {}).items():
        if p.get("видимость") == "Ложь" and ("col", owner, column) not in asked:
            shown = {(c["name"] or "").casefold(): c["name"] for c in table_columns(form.items[owner], True) if c.get("name")} if owner in form.items else {}
            gone.append(f"{name(owner)}: {shown.get(column, column)}")
    if gone:
        out.append("по разбору кода применено, колонки убраны: " + ", ".join(sorted(gone)))
    shown_code = sorted(name(i) for i in (parts.get("shown_by_code") or ()) if i in (getattr(marks, "force_show", None) or ()))
    if shown_code:
        out.append("по разбору кода применено, показаны элементы, скрытые в файле (код делает их видимыми безусловно): " + ", ".join(shown_code))
    filled = sorted(f"{name(i)} — {_value_words(form, i, v)}" for i, v in (getattr(marks, "field_values", None) or {}).items() if i in form.items and ("el", i, "значение") not in asked)
    if filled:
        out.append("по разбору кода применено, значения полей при открытии: " + ", ".join(filled))
    checked = []
    for i, buttons in (parts.get("checked_buttons") or {}).items():
        shown = _bar_names(form.items[i]) if i in form.items else {}
        checked += [f"{name(i)}: {shown.get(n, n)} ({'нажата' if flag else 'пометка снята'})" for n, flag in buttons.items()]
    if checked:
        out.append("по разбору кода применено, пометка кнопок: " + ", ".join(sorted(checked)))
    current = {i: at for i, at in (parts.get("current_page") or {}).items() if ("cur", i) not in asked}
    if current:
        out.append("по разбору кода применено, текущая страница: " + ", ".join(f"{name(i)} — {_page_name(form, i, at)}" for i, at in sorted(current.items())))
    new = sorted(f"{name(i)}: {c['name']}" for i, cols in (parts.get("new_columns") or {}).items() for c in cols)
    if new:
        out.append("по разбору кода применено, колонки созданы кодом (ширина по умолчанию, не по файлу): " + ", ".join(new))
    if not hatch:
        removed = []
        for i, names in (parts.get("removed_buttons") or {}).items():
            shown = _bar_names(form.items[i]) if i in form.items else {}
            removed += [f"{name(i)}: {shown.get(n, n)}" for n in names if ("btn", i, n) not in asked]
        if removed:
            out.append("по разбору кода применено, кнопки убраны: " + ", ".join(sorted(removed)))
    return out


def _value_words(form, index, value):
    """Значение поля словами для `notes`: флажок — «отмечен»/«снят», остальное — «значение «…»»."""
    kind, own = value
    if kind == "select":
        return "выбран" if own else "не выбран"
    if kind == "bool":
        return "отмечен" if own and form.items[index].type == "CheckBox" else "не отмечен" if form.items[index].type == "CheckBox" else ("Истина" if own else "Ложь")
    return f"«{own}»"


def _may_toggle(values, visible):
    """Код может изменить видимость по условию: у видимого в файле — если среди значений есть не «Истина» (Ложь или выражение), у скрытого — если есть не «Ложь»."""
    return any(v != ("Истина" if visible else "Ложь") for v in values or ())


def _shown_by_code(form, marks, shown):
    """Показанные страницы панелей с учётом разбора кода: страница, названная текущей безусловно, а при убранной нулевой — первая из оставшихся. Заданное вызывающим
    (`shown`) сильнее разбора."""
    parts = getattr(marks, "parts", None) or {}
    chosen = dict(parts.get("current_page") or {})
    gone = {}
    for (owner, at), props in (parts.get("applied_pages") or {}).items():
        if props.get("видимость") == "Ложь":
            gone.setdefault(owner, set()).add(at)       # скрытая страница не показана в обоих режимах: выбрана первая видимая (в `hatch` её закладка остаётся на месте, со штриховкой)
    for owner, pages in gone.items():
        if owner in chosen and chosen[owner] not in pages:
            continue
        holder = form.holders.get(owner)
        block = holder.block if holder is not None else None
        pages_block = block.get(edit.names.PAGES) if isinstance(block, dict) else None
        count = len(pages_block.get(edit.names.PAGE_ITEMS) or []) if isinstance(pages_block, dict) else 0
        rest = [n for n in range(count) if n not in pages]
        if rest:
            chosen[owner] = rest[0]
    if not chosen:
        return shown
    return {**chosen, **(shown or {})}


HIDDEN_BLOCK = re.compile(r"^<g [^>]*data-index='(\d+)'[^>]*data-hidden='1'>")
ELEMENT_OPEN = re.compile(r"^<g data-name=[^>]*data-index='(\d+)'(?![^>]*data-hidden)")


def _hatch_below_visible(parts, drawn):
    """Штриховка скрытого лежит под всем видимым, что нарисовано раньше неё и пересекается с ней: сначала рисовалась ветка скрытого элемента, а видимый элемент другой ветки формы
    шёл раньше, и штриховка ложилась на него. Блок переносится перед первым таким элементом; панели, в которых лежит сам скрытый элемент, не в счёт."""
    rects = {it.index: (x, y, x + w, y + h) for it, (x, y, w, h) in drawn}
    items = {it.index: it for it, _box in drawn}
    for at in range(len(parts)):
        found = HIDDEN_BLOCK.match(parts[at])
        if not found:
            continue
        index = int(found.group(1))
        mine = rects.get(index)
        if mine is None:
            continue
        family, owner = {index}, getattr(items.get(index), "owner", None)
        while owner is not None:
            family.add(owner.index)
            owner = getattr(owner, "owner", None)
        for before in range(at):
            hit = ELEMENT_OPEN.match(parts[before])
            if not hit:
                continue
            other = int(hit.group(1))
            box = rects.get(other)
            if other in family or box is None or box[0] >= mine[2] or mine[0] >= box[2] or box[1] >= mine[3] or mine[1] >= box[3]:
                continue
            parts.insert(before, parts.pop(at))
            break


def render(doc, width=None, height=None, shown=None, overlay=None, marks=None):
    fatal = [p for p in validate.validate(doc) if p.fatal]
    if fatal:
        raise ValueError(f"документ не проходит проверку ({fatal[0].text}) — рендер по нему не строю")
    platform_pictures.take_missed()
    folded = {i: m for i, m in (getattr(marks, "collapsed", None) or {}).items() if m in fold.MODES}
    if folded:
        doc = fold.fold_doc(doc, folded)       # свёрнутая панель — нулевой протяжённости у края свёртки; соседи занимают её место (`layout.fold`)
    form = layout.read(doc)
    width, height = width or form.width, height or form.height
    shown = _shown_by_code(form, marks, shown)
    try:
        lay = layout.Layout(form, width, height, shown=shown)
    except edit.EditError as why:  # раскладка перестаёт меняться с отказом или правила зациклились: догадку не рисуем
        raise ValueError(f"раскладка отказала при размере {width}x{height} ({why}) — рендер по ней не строю") from why
    unknown, notes, drawn, conditional, labels, hatched, dropped = [], [], [], set(), [], [], []

    def note(text):
        if text not in notes:
            notes.append(text)

    back_kind, back_color, back_words = _back_of({"content": {"back_color": _dig(doc, "form", "container", "layout_holder", "layout_list", "layout", "back_color")}})
    if back_kind == "rgb":
        note(FORM_BACK_NOTE)
    elif back_kind == "other":
        note(f"цвет фона формы задан стилем или системой ({back_words}): форма нарисована цветом по умолчанию {FORM_BG.upper()}")
    parts = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}'>",
             f"<rect width='{width}' height='{height}' fill='{back_color if back_kind == 'rgb' else FORM_BG}'/>"]

    if (textwidth._form_font_record(doc) or {}).get("source") == "StyleFont":
        note(textwidth.STYLE_AUTO_NOTE)
    under_picture, picture_words = picture_places.form_picture(doc, width, height)
    parts.extend(under_picture)           # картинка формы лежит под всеми элементами
    for words in picture_words:
        note(words)
    form_picture = bool(under_picture)
    border = layout._form_border_kind(doc) if layout._form_border(doc) else None
    if border is not None:
        note(f"у формы с Рамкой ({border!r}) отступ клиентской области не проверялся: элементы поставлены без отступа Рамки")
    if form.raw:
        note(f"сырых элементов (без целого индекса или разобранного блока координат): {len(form.raw)} — не нарисованы, "
             "модель раскладки их не считает")

    # Вложенный элемент, чей box не согласован с правилом области вида закладок панели, рендер рисует по box из
    # файла, а предприятие разместит его по правилам. Расхождение сообщается, но не рисуется.
    for found in layout.nested_area_mismatches(form, shown):
        if getattr(found[0], "index", None) in folded:
            continue       # свёрнутая панель не видна: замечания о её страницах не нужны
        note(layout.nested_area_words(*found))
    for found in layout.wide_pages(form, shown):
        if getattr(found[0], "index", None) in folded:
            continue       # свёрнутая панель не видна: замечания о её страницах не нужны
        note(layout.wide_pages_words(*found))
    for found in layout.narrow_pages(form, shown):
        if getattr(found[0], "index", None) in folded:
            continue       # свёрнутая панель не видна: замечания о её страницах не нужны
        note(layout.narrow_pages_words(*found))

    parts_of = getattr(marks, "parts", None) or {}
    applied = getattr(marks, "applied", None) or {}
    applied_hide = {i for i, props in applied.items() if props.get("видимость") == "Ложь"}
    applied_off = {i for i, props in applied.items() if props.get("доступность") == "Ложь"}
    force_show = getattr(marks, "force_show", None) or set()
    forced_enabled = getattr(marks, "forced_enabled", None) or {}
    hatch_hidden = bool(getattr(marks, "hatch_hidden", False))
    hatch_cond = bool(getattr(marks, "hatch_conditional", False))          # режим условного: видимость по условию — та же штриховка, что у скрытого
    asked = getattr(marks, "asked", None) or set()
    values = getattr(marks, "field_values", None) or {}
    defaults = {i: v for i, v in open_defaults(doc, form).items() if i not in values and ("el", i, "значение") not in (getattr(marks, "asked", None) or set())}
    cond_hatched = []
    hidden_src = getattr(marks, "hidden_src", None) or {}
    applied_hide -= force_show
    grouped = {i for members in (getattr(marks, "groups", None) or {}).values() for i in members}
    variant_skip, variant_drawn, variant_hatched = set(), {}, set()
    ctx_bars = context_menu_bars(doc)
    data_bound = bound_elements(doc)

    def find_variants(key):
        """Варианты на одном месте среди детей `key`: рисуется первый видимый, остальные пропускаются, у первого — метка."""
        entries = []
        for it in form.holders[key].children:
            if it.index in grouped and it.index in lay.ints:
                try:
                    x, y, w, h = absolute(form, lay, it)
                except Unmeasured:
                    continue
                entries.append((it, (x, y, x + max(w, 0), y + max(h, 0))))
        for members in variants.groups(entries, marks):
            first = variants.drawn(members, lambda m: _hidden(form, m, shown) or m.index in applied_hide, marks.defaults)
            if first is None:
                continue
            variant_drawn[first.index] = [m.name or m.type for m in members if m is not first]
            variant_skip.update(m.index for m in members if m is not first)

    def walk(key, level):
        under, mark = [], len(parts)         # скрытое со штриховкой ложится под видимое того же уровня (в начале своей панели или формы)
        if marks:
            find_variants(key)
        # Порядок наложения: командные панели рисуются раньше остальных элементов той же панели или формы,
        # поэтому поля, флажки и надписи ложатся поверх них, как в платформе. Панели с вложенными элементами,
        # таблицы и прочее рисуются в порядке файла.
        for it in sorted(form.holders[key].children, key=lambda c: c.type != "CommandBar"):
            if _hidden(form, it, shown):
                continue  # не показанный — вместе со всем, что в нём
            if it.index in folded:
                continue  # свёрнутая панель исчезает целиком, без штриховки: ни полосы, ни рамки
            if it.index in variant_skip:
                # вариант на том же месте — другой вариант группы нарисован: этот со штриховкой под ним (в режимах скрытого и условного «hatch»), без собственного текста; иначе не рисуется
                if (hatch_hidden or hatch_cond) and it.index in lay.ints:
                    try:
                        vx, vy, vw, vh = absolute(form, lay, it)
                    except Unmeasured:
                        continue
                    under.append(f"<g data-name={quoteattr(_clean(it.name or ''))} data-type={quoteattr(_clean(it.type or ''))} data-index='{it.index}' data-holder='{key}' "
                                 f"data-level='{level}' data-hidden='1'>" + "".join(hidden_overlay(vx, vy, max(vw, 0), max(vh, 0), "вариант")) + "</g>")
                    hatched.append(f"{it.qualified()} (вариант на том же месте)")
                    variant_hatched.add(it.index)
                continue
            if it.type == "CommandBar" and it.index in ctx_bars and not it.visible:
                continue  # контекстное меню (панель, скрытая в файле и названная меню элемента) появляется по правой кнопке, на форме его нет
            hidden_by = None
            if it.index not in force_show and (it.index in applied_hide or not it.visible):
                hidden_by = hidden_src.get(("el", it.index), "код" if it.index in applied_hide else "файл")
            cond_by = None
            if hatch_cond and marks and it.index not in force_show and it.index not in applied_hide and ("el", it.index, "видимость") not in asked \
                    and _may_toggle((marks.get(it.index) or {}).get("видимость"), it.visible):
                cond_by = "условие"       # видимость задаёт код по условию (или вероятно): файл или запрос её не определили
            if hidden_by and not hatch_hidden and not cond_by:
                continue    # скрытое «как на экране» не рисуется вместе со всем, что в нём
            if it.index not in lay.ints:
                note(f"«{it.qualified()}» не нарисован: у элемента нет индекса, модель раскладки его не считает")
                continue
            try:
                x, y, w, h = absolute(form, lay, it)
            except Unmeasured as why:
                note(str(why))
                continue
            w, h = max(w, 0), max(h, 0)  # отрицательный размер SVG не принимает
            drawn.append((it, (x, y, w, h)))
            if hidden_by and hatch_hidden:
                # Скрытое на экране не видно: контур и штриховка без собственного текста, под видимым; вложенные не рисуются (скрыт весь контейнер).
                under.append(f"<g data-name={quoteattr(_clean(it.name or ''))} data-type={quoteattr(_clean(it.type or ''))} data-index='{it.index}' data-holder='{key}' "
                             f"data-level='{level}' data-hidden='1'>" + "".join(hidden_overlay(x, y, w, h, hidden_by)) + "</g>")       # один блок: `_hatch_below_visible` переносит его целиком
                hatched.append(f"{it.qualified()} ({hidden_by})")
                if marks and marks.get(it.index):
                    conditional.add(it.index)
                continue
            draw = DRAW.get(it.type)
            if it.type == "GanttChart" and not charts.gantt_known(it):
                draw = None          # запись тела не версии 74: каркас не снимался — серый прямоугольник вида
            fill = bar_fill(it) if it.type == "CommandBar" \
                else FILL.get(it.type, "white" if draw else "#bbb")
            off = draw is not None and it.type != "CommandBar" and (_enabled(it.node) is False or not _form_enabled(doc) or it.index in applied_off)  # панель серит кнопки по одной
            if it.index in forced_enabled and draw is not None and it.type != "CommandBar":
                off = not forced_enabled[it.index]
            if it.type == "GanttChart" and draw is None:
                fill = "#bbb"
            if it.type == "PictureBox" and picture_places.box_bitmap(it) is not None:
                fill = FORM_BG          # поле с картинкой залито цветом формы (снимки предприятия), а не белым
            if it.type == "Label" and _dig(it.node, "content", "u1", "u0", "transparent") is not True and _back_of(it.node)[0] == "rgb":
                fill = _back_of(it.node)[1]           # надпись залита своим цветом фона (снято в предприятии: серые и белые плитки у надписей панели управления)
            if form_picture and picture_places.background(doc, it):
                fill = picture_places.background(doc, it)       # поверх картинки формы надпись, поле картинки и панель залиты цветом формы
            if it.type == "PictureBox" and not picture_box_unseen(it) and picture_box_empty(it):
                fill = "none"           # рамка поля картинки без картинки: внутри фон формы, не белое (снимки e239v2, формы 02 и 04)
            if picture_box_unseen(it):
                fill = "none"           # поле картинки без картинки и без рамки в предприятии не видно
                note(PICTURE_UNSEEN_NOTE)
            if off and it.type in ("TextBox", "ComboBox"):
                fill = DISABLED_FIELD
            # `data-name` не уникален (бывают одноимённые вложенные элементы и безымянные), поэтому адрес
            # элемента задаёт `data-index`. `data-holder` — индекс панели или формы (0 — форма), `data-level` —
            # глубина (0 — верхний уровень формы); они нужны для наложения.
            parts.append(f"<g data-name={quoteattr(_clean(it.name or ''))} data-type={quoteattr(_clean(it.type or ''))} "
                         f"data-index='{it.index}' data-holder='{key}' data-level='{level}'>")
            # Первый <rect> группы — точный box (заливка без обводки), по нему читают края. Видимая рамка
            # рисуется на пикселях box отдельным элементом (внешний край рамки совпадает с краем box).
            parts.append(f"<rect x='{x}' y='{y}' width='{w}' height='{h}' fill='{fill}' stroke='none'/>")
            frame = _frame(it, x, y, w, h, _font_of(doc, it) if it.type == "GroupBox" else None, doc)
            panel_measured = it.type == "Panel" and layout._panel_tabs(it) in PANEL_FRAME_MEASURED
            if it.type == "Panel" and layout._panel_tabs(it) == "DontUse" and not layout._panel_unframed(it):
                note(f"у панели «{it.qualified()}» («Не отображать») с Рамкой рамка не нарисована: не проверялось")
            if frame and it.type not in CALIBRATED and it.type not in FRAME_NOT_CLAIMED and not panel_measured:
                note(f"рамка типа «{it.type}» в предприятии не сверена (сверены: "
                     f"{', '.join(sorted(CALIBRATED))})")
            parts.extend(frame)
            if it.type == "Panel":
                page = _panel_frame_box(it, x, y, w, h, _font_of(doc, it), doc)
                parts.extend(_panel_back(it, page, (x, y, w, h)))
                if page is not None:
                    parts.extend(picture_places.panel_picture(it, page))          # картинка панели — фон страницы под вложенными элементами
            parts.extend(_form_bar_line(it, x, y, w, h, height))
            if draw is None:
                unknown.append(f"{it.qualified()} ({it.type})")
                pass          # у вида без каркаса видна только рамка и заливка: имя вида на картинке не пишется (оно — в `unknown` и в досье)
            else:
                extra = {}
                if it.type == "GanttChart":
                    note(charts.GANTT_NOTE)
                    if charts.scale_days(it) is None:
                        note(charts.GANTT_SCALE_NOTE)
                elif it.type == "ProgressBar":
                    note(charts.PROGRESS_NOTE)
                if it.type == "Label":
                    extra["data_bound"] = it.index in data_bound
                if it.type in VALUE_TYPES and (it.index in values or it.index in defaults):
                    by_default = it.index not in values
                    value = defaults[it.index] if by_default else values[it.index]
                    drawn_value = {"CheckBox": value == ("bool", True), "RadioButton": bool(radio_selected(it, value))}.get(it.type, (field_text(it, value) if it.type != "Label" else value_text(value)) is not None)
                    if drawn_value:
                        extra["value"] = value
                        if by_default:
                            note(OPEN_DEFAULT_NOTE)
                        elif VALUE_NOTES.get(it.type):
                            note(VALUE_NOTES[it.type])
                if it.type == "Panel":
                    gone = {at for (owner, at), props in (parts_of.get("applied_pages") or {}).items() if owner == it.index and props.get("видимость") == "Ложь"}
                    if (shown or {}).get(it.index) is not None:
                        extra["active"] = shown[it.index]
                    if gone and hatch_hidden:
                        extra["hidden"] = {at: hidden_src.get(("page", it.index, at), "код") for at in gone}
                        hatched.append(f"{it.qualified()}: страницы " + ", ".join(f"{_page_name(form, it.index, at)} ({extra['hidden'][at]})" for at in sorted(gone)))
                        gone = set()
                    if gone:
                        extra["gone"] = gone
                    titles = {at: props["заголовок"] for (owner, at), props in (parts_of.get("applied_pages") or {}).items() if owner == it.index and props.get("заголовок")}
                    if titles:
                        extra["retitle"] = titles
                    conditional.update(("page", it.index, at) for (owner, at) in (parts_of.get("pages") or {}) if owner == it.index)
                    if hatch_cond:
                        seen = set(extra.get("hidden", ())) | set(extra.get("gone", ()))
                        by_condition = {at: "условие" for (owner, at), props in (parts_of.get("pages") or {}).items()
                                        if owner == it.index and at not in seen and ("page", owner, at) not in asked and _may_toggle(props.get("видимость"), True)}
                        if by_condition:
                            extra["cond"] = by_condition
                            cond_hatched.append(f"{it.qualified()}: страницы " + ", ".join(_page_name(form, it.index, at) for at in sorted(by_condition)))
                            for at in by_condition:
                                if set(parts_of["pages"][(it.index, at)]) <= {"видимость"}:
                                    conditional.discard(("page", it.index, at))
                elif it.type == "CommandBar":
                    added_here = (parts_of.get("buttons") or {}).get(it.index)
                    if added_here:
                        extra["added"] = added_here
                    checked_here = (parts_of.get("checked_buttons") or {}).get(it.index)
                    if checked_here:
                        extra["checked"] = checked_here
                    disabled_here = (parts_of.get("disabled_buttons") or {}).get(it.index)
                    if disabled_here:
                        extra["disabled"] = disabled_here          # кнопки, которые код безусловно делает недоступными, серые
                    removed_here = (parts_of.get("removed_buttons") or {}).get(it.index)
                    if removed_here:
                        if hatch_hidden:
                            extra["hatch_removed"] = {name: hidden_src.get(("btn", it.index, name), "код") for name in removed_here}
                            shown_names = _bar_names(it)
                            hatched.append(f"{it.qualified()}: кнопки " + ", ".join(f"{shown_names.get(name, name)} ({who})" for name, who in extra["hatch_removed"].items()))
                        else:
                            extra["removed"] = removed_here
                    if hatch_cond:
                        shown_names = _bar_names(it)
                        by_condition = {name: "условие" for name in (parts_of.get("cond_buttons") or {}).get(it.index, ())
                                        if name in shown_names and name not in (removed_here or ()) and ("btn", it.index, name) not in asked}
                        if by_condition:
                            extra["hatch_removed"] = {**by_condition, **(extra.get("hatch_removed") or {})}
                            cond_hatched.append(f"{it.qualified()}: кнопки " + ", ".join(shown_names[name] for name in sorted(by_condition)))
                elif it.type == "TableBox":
                    conditional.update(("column", it.index, name) for (owner, name) in (parts_of.get("columns") or {}) if owner == it.index)
                    gone = {name for (owner, name), props in (parts_of.get("applied_columns") or {}).items() if owner == it.index and props.get("видимость") == "Ложь"}
                    extra["show"] = {name for (owner, name) in (getattr(marks, "show_columns", None) or ()) if owner == it.index}
                    file_hidden = hidden_in_file(it, extra["show"])
                    if hatch_hidden:        # скрытая колонка не нарисована и ширины не занимает (как на экране): штриховки у неё нет
                        shown_names = {(c["name"] or "").casefold(): c["name"] for c in table_columns(it, True) if c.get("name")}
                        said = [f"{name} (файл)" for name in file_hidden.values()] + [f"{shown_names.get(name, name)} ({hidden_src.get(('col', it.index, name), 'код')})"
                                                                                       for name in sorted(gone) if name not in file_hidden]
                        if said:
                            dropped.append(f"{it.qualified()}: " + ", ".join(said))
                    if hatch_cond:
                        shown_names = {(c["name"] or "").casefold(): c["name"] for c in table_columns(it, True) if c.get("name")}
                        by_condition = {}
                        for (owner, name), props in (parts_of.get("columns") or {}).items():
                            if owner != it.index or name in gone or name in extra.get("hidden", ()) or ("col", owner, name) in asked:
                                continue
                            if _may_toggle(props.get("видимость"), name not in file_hidden):
                                by_condition[name] = "условие"
                                if name in file_hidden:
                                    extra["show"] = set(extra["show"]) | {name}          # скрыта в файле, а код может показать: нарисована со штриховкой
                                if set(props) <= {"видимость"}:
                                    conditional.discard(("column", it.index, name))
                        if by_condition:
                            extra["hidden"] = {**(extra.get("hidden") or {}), **by_condition}
                            cond_hatched.append(f"{it.qualified()}: колонки " + ", ".join(shown_names.get(name, name) for name in sorted(by_condition)))
                    if gone:
                        extra["gone"] = gone
                    titles = {name: props["заголовок"] for (owner, name), props in (parts_of.get("applied_columns") or {}).items() if owner == it.index and props.get("заголовок")}
                    if titles:
                        extra["retitle"] = titles
                    if (parts_of.get("new_columns") or {}).get(it.index):
                        extra["new"] = parts_of["new_columns"][it.index]
                drawn_parts = draw(doc, it, x, y, w, h, **extra)
                if off:
                    drawn_parts = _grey(drawn_parts)
                if off or (it.type == "CommandBar" and (_enabled(it.node) is False or not _form_enabled(doc) or any(
                        not en["enabled"] for en in _file_entries(it.node)))):
                    note(DISABLED_NOTE)
                if it.type == "CommandBar" and any(en.get("no_action") for en in _file_entries(it.node)):
                    note(NO_ACTION_NOTE)
                parts.extend(drawn_parts)
                for line in _item_notes(it, doc) + [_font_note(doc, it) or ""]:
                    if line:
                        note(line)
            if marks and marks.get(it.index) and not (cond_by and set(marks[it.index]) <= {"видимость"}) and it.index not in variant_drawn:
                conditional.add(it.index)          # вариант на том же месте назван своей пометкой («один из вариантов»), а не «как в файле»
            if cond_by and it.type != "Panel":
                parts.extend(hidden_overlay(x, y, w, h, cond_by, conditional=True))
                cond_hatched.append(it.qualified())
            if it.index in variant_drawn:
                labels.append((it, (x, y, w, h)))
            parts.append("</g>")
            if it.index in form.holders and it.type == "Panel":
                tabs = layout._panel_tabs(it)
                if tabs in NESTED_NOTES and any(c.visible for c in form.holders[it.index].children):
                    note(f"у панели «{it.qualified()}» с закладками {tabs!r}: {NESTED_NOTES[tabs]}")
                if layout._panel_unframed(it) and layout.panel_not_checked(doc, it) and any(c.visible for c in form.holders[it.index].children):
                    note(f"у панели «{it.qualified()}» {layout.panel_not_checked(doc, it)}; вложенные стоят по box и росту панели")
                # Содержимое страницы обрезается границей панели: что вышло за неё, пользователь не видит (страница шире или выше панели прокручивается),
                # и на рисунке оно не ложится поверх соседних элементов формы.
                clip = f"panel{it.index}"
                cx, cy, cw, ch = x, y, w, h
                page = _panel_frame_box(it, x, y, w, h, None, doc)    # страница показывает свою внутренность: вышедшее за линии страницы закладки не закрывает
                if page is not None and layout._panel_tabs(it) not in ("DontUse", None, "Top", "TopScrolling", "Bottom"):
                    cx, cy, cw, ch = page[0] + 1, page[1] + 1, max(page[2] - 2, 0), max(page[3] - 2, 0)
                parts.append(f"<clipPath id='{clip}'><rect x='{_n(cx)}' y='{_n(cy)}' width='{_n(cw)}' height='{_n(ch)}'/></clipPath>"
                             f"<g class='panel-content' clip-path='url(#{clip})'>")
                walk(it.index, level + 1)
                parts.append("</g>")
                if cond_by:          # штриховка условной панели лежит поверх вложенных
                    parts.extend(hidden_overlay(x, y, w, h, cond_by, conditional=True))
                    cond_hatched.append(it.qualified())
                # Полоса — когда страница панели перестала сжиматься: и по пределу «минимум от области», и по обычному минимуму вложенного
                # элемента (проверено в предприятии: таблица в панели «Не отображать» встала на высоте 49, у панели появилась полоса 16 px).
                bars = {axis for axis, direction, _lim in lay.frozen.get(it.index, ()) if direction < 0}
                if bars:
                    # Страница панели перестала сжиматься (элемент дошёл до минимума): у панели полоса прокрутки, 16 px внутри рамки
                    # у нижнего (горизонтальная) и правого (вертикальная) края области страницы. У «Сверху» проверена по ширине окна.
                    parts.append("<g class='panel-scroll'>")
                    ax, ay = x + 1, y + 1
                    aw, ah = max(w - 2, 0), max(h - 2, 0)
                    strip = layout.strip_height(it.node, layout._panel_tabs(it))
                    if layout._panel_tabs(it) in ("Bottom", "BottomScrolling"):
                        ah -= strip
                    elif layout._panel_tabs(it) in ("Top", "TopScrolling"):
                        ay, ah = ay + strip, ah - strip
                    if 0 in bars:
                        parts.append(_scroll_bar(ax, ay + ah - SCROLL_BAR, aw - (SCROLL_BAR if 1 in bars else 0), SCROLL_BAR))
                    if 1 in bars:
                        parts.append(_scroll_bar(ax + aw - SCROLL_BAR, ay, SCROLL_BAR, ah - (SCROLL_BAR if 0 in bars else 0)))
                    parts.append("</g>")
                    note(f"у панели «{it.qualified()}» страница перестала сжиматься: полоса прокрутки нарисована внизу (справа) области панели "
                         "16 px; положение сверено у «Сверху» по ширине окна, высота и другие виды закладок — по аналогии")
        parts[mark:mark] = under

    walk(0, 0)
    _hatch_below_visible(parts, drawn)
    # Полосы прокрутки формы рисуются там, где их предсказывает модель (`Layout.scroll`: по ширине —
    # вертикальная полоса, по высоте — горизонтальная; 16 px). Положение относительно краёв клиентской области
    # по кадру окна формы не снималось.
    bar_w, bar_h = lay.scroll
    if bar_w or bar_h:
        parts.append("<g class='form-scroll'>")
        if bar_w:
            parts.append(_scroll_bar(width - bar_w, 0, bar_w, height - bar_h))
        if bar_h:
            parts.append(_scroll_bar(0, height - bar_h, width - bar_w, bar_h))
        parts.append("</g>")
        note("полосы прокрутки формы нарисованы по `Layout.scroll` (16 px у правого и нижнего края клиентской области): "
             "положение на кадре окна формы не снято")
    for it, _box in labels:
        note(f"«{it.qualified()}» — один из вариантов на одном месте (видимость задаёт код): нарисован вариант по умолчанию (в разборе кода) либо первый видимый "
             f"в файле, остальные {'со штриховкой' if variant_hatched else 'не нарисованы'}: {', '.join(variant_drawn[it.index])}")
    for line in _applied_words(form, marks):
        note(line)
    rejected = getattr(marks, "rejected", None) or []
    if rejected:
        note(f"записи разбора кода отклонены ({len(rejected)}) и в рисунок не вошли: " + "; ".join(f"запись {r['index']} ({r['kind'] or '?'}): {r['why']}" for r in rejected))
    if hatched:
        note("режим скрытого «hatch»: скрытое нарисовано на своём месте со штриховкой (подписи на картинке нет); кто скрыл — " + ", ".join(sorted(hatched))
             + "; на экране его нет, место соседей посчитано как при видимом")
    if dropped:
        note("скрытые колонки не нарисованы и ширины у видимых не занимают, как на экране (штриховки у них нет): " + "; ".join(sorted(dropped)))
    if cond_hatched:
        note("режим условного «hatch»: что код скрывает или показывает по условию (или вероятно), нарисовано на своём месте со штриховкой, как скрытое (подписи на картинке нет): "
             + ", ".join(sorted(cond_hatched)) + "; условие названо в разделе «Что код меняет» досье")
    if hatched or cond_hatched:
        parts.insert(2, CODE_DEFS)
    if conditional:
        note(f"условное из разбора кода (видимость, доступность, заголовок задаёт код по условию или вероятно) у {len(conditional)} мест нарисовано, как в файле, без пометок на картинке: "
             "что и при каком условии делает код, названо в разделе «Что код меняет» досье")
    if overlay is not None:
        parts.extend(overlay_layer(overlay, width, height))
    if any(f"url(#{OFF_FILTER_ID})" in part for part in parts):
        parts.insert(1, OFF_FILTER)         # одно определение на рисунок: картинки недоступных кнопок ссылаются на него
    parts.append("</svg>")
    missing = platform_pictures.missing_note(platform_pictures.take_missed())
    if missing:
        note(missing)
    return Rendered("\n".join(parts), unknown, notes, drawn, (width, height))
