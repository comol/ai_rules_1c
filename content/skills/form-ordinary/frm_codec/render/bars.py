"""Командные панели: состав кнопок (файл, платформа, автозаполнение, добавленное кодом), ширины, значки, вертикальная панель, панель формы и её линия."""
import math
import re
from xml.sax.saxutils import escape

from .. import bar_platform, edit, layout, lstring, platform_pictures, textwidth, validate
from . import action_icons, picture_bitmap
from .core import OFF_FILTER_ID, _back_of, _clean, _dig, _enabled, _form_enabled, _grey, _n, _text, _vline
from .marks import hidden_overlay


# Кнопка-элемент с картинкой (`content/u1/picture`, источник не 0): значок-заглушка 16×16 (серый квадрат с чертой — самой
# картинки в файле нет, она в конфигурации). Без текста значок стоит по центру кнопки, с текстом — слева (`picture_location`
# «Left», умолчание) или справа от него, а текст занимает остаток. Положение «Сверху»/«Снизу»/«Без текста»/«Вместо» и размер
# значка не проверялись: значок рисуется как при «Left».
BUTTON_ICON, BUTTON_ICON_GAP = 16, 4


def _icon(x, y, title=None, action=None, bitmap=None):
    """Значок кнопки: один на кнопку формы и кнопку командной панели; `title` — название кнопки (подсказка в SVG). `action` — название стандартного
    действия (платформа или стандартное действие файла): у известного таблице `action_icons` рисуется его значок, у остальных — заглушка (серый квадрат:
    картинки конфигурации в файле нет). `bitmap` — `data:`-адрес PNG картинки, вложенной в файл (`picture_bitmap`): рисуется она сама, 16×16."""
    if bitmap:
        return picture_bitmap.image_tag(x, y, bitmap, BUTTON_ICON, _clean(title) if title else None)
    if action:
        drawn = action_icons.draw(x, y, action)
        if drawn:
            return drawn
    inner = f"<title>{escape(_clean(title))}</title>" if title else ""
    end = f">{inner}</rect>" if inner else "/>"
    return (f"<rect class='icon button-picture' x='{_n(x + 0.5)}' y='{_n(y + 0.5)}' width='{BUTTON_ICON - 1}' height='{BUTTON_ICON - 1}' "
            f"fill='#d8d8d8' stroke='#888'{end}")


# Кнопки командной панели: рисуются кнопки верхнего набора блока действий — того, на который не ссылается ни
# одна кнопка-подменю (у подменю набор называет GUID головы блока, см. `docs/codec-blocks.md`). Остальные наборы
# — меню подменю, на полосе их нет. Разделитель рисуется чертой без текста (у части разделителей в файле есть
# текст), подменю — с «▾», кнопка с отображением «Картинка» занимает место под значок (сами значки не рисуются).
# Ширины приблизительные, как и шрифт.
# Замер по снимкам предприятия: значок — шаг 23 px (22,7–23), разделитель — 5 px, меню со стрелкой — 5,4 px на знак + 20; ширина кнопки с текстом — `_entry_width`.
BAR_GLYPH, BAR_SEP, BAR_ICON, BAR_PAD, BAR_MORE = 5.5, 5, 23, 8, 14
# Оценка ширины по знакам (запасная, когда нет метрик шрифта): кнопка с картинкой и текстом — 36 px сверх текста; жирный шрифт панели — знак 6,4 px вместо 5,5.
BAR_POPUP, BAR_ARROW, BAR_BOTH, BAR_BOLD = 20, 8, 36, 1.165
# Подменю с картинкой без текста — значок со стрелкой, 24 px (в предприятии такое подменю помещается в панель шириной 32 px при полях 1,5 и 6 px).
BAR_POPUP_ICON = 24
# Кнопка с картинкой и текстом: ширина = метрики текста (жирного, у панели с жирным шрифтом) + 26, надпись начинается на 18 px правее картинки (картинка — с x = 4 от начала кнопки).
# Четыре кнопки с картинкой и текстом на двух панелях: 158, 116, 161 и 73 px при тексте 132, 90, 135 и 47 — везде 26.
BAR_BOTH_PAD, BAR_BOTH_TEXT = 26, 22
# Левое поле полосы 1,5 px (первая кнопка начинается с x = 1,5 от левого края панели), правое — 6. Проверка: у панели документа разделители по снимку 68, 96, 147, 198
# и по модели 68, 96, 147, 198; у панели списка по снимку 71, 168, 219, 323, 387, 415 (окно со своим сдвигом 3 px) и по модели 71, 168, 219, 324, 387,5, 415,5.
BAR_START, BAR_END = 1.5, 6
# Панель, выровненная вправо («ОК | Записать | Закрыть»): последняя кнопка кончается на 3 px от края панели (центр надписи «Закрыть» стоит на 3 px правее, чем при поле 6;
# проверено на двух формах); ширины кнопок — по метрикам шрифта, см. `_entry_width`.
BAR_RIGHT_END = 3


def _own_set(block):
    """Верхний набор блока действий либо `None`: первый по файлу набор, на который не ссылается кнопка-подменю, с кнопками (пустой двойник пропускается)."""
    sets = edit.buttons._button_sets_by_pair(block)
    named = set()
    for action in block.get(edit.base.ACTIONS) or []:
        if isinstance(action, dict) and edit.buttons._action_kind(block, action) == "кнопка-подменю":
            named |= {pair for pair in validate._refs_in(action.get(edit.buttons.ACT_SPEC), edit.buttons.REF_ID,
                                                          edit.buttons.REF_CODE) if pair in sets}
    all_sets = [s for s in block.get(edit.base.BUTTON_SETS) or [] if isinstance(s, dict)]
    free = []
    for item in all_sets:
        ref = item.get(edit.buttons.SET_REF)
        pair = (ref.get("guid"), item.get(edit.buttons.SET_CODE)) if isinstance(ref, dict) else None
        if pair not in named:
            free.append(item)
    # пустой двойник подменю (в файле стоит раньше основного набора) — не верхний набор: берётся первый свободный набор с кнопками
    with_buttons = next((item for item in free if item.get(edit.base.BUTTONS)), None)
    if with_buttons is not None:
        return with_buttons
    return free[0] if free else (all_sets[0] if all_sets else None)


def button_picture(block, button):
    """Блок картинки кнопки панели (`source`, `ref`, `u7`…) либо `None`."""
    try:
        action = edit.base._action_of(block, button, "", button.get(edit.buttons.BTN_NAME))
    except edit.base.EditError:
        return None
    picture = (action.get(edit.base.EXTRAS) or {}).get(edit.buttons.PICTURE_BIT) if isinstance(action, dict) else None
    return picture if isinstance(picture, dict) else None


def picture_blocks(node):
    """Блоки картинок кнопок верхнего набора панели (кнопки с картинкой, у прочих — `None`)."""
    block = _dig(node, "content", "u1", "actions")
    if not isinstance(block, dict):
        return []
    return [button_picture(block, button) for button in (_own_set(block) or {}).get(edit.base.BUTTONS) or [] if isinstance(button, dict)]


def button_has_picture(block, button):
    """У кнопки есть картинка: в записи её действия блок картинки не пуст (источник не 0). Записи действия нет — картинки нет."""
    try:
        action = edit.base._action_of(block, button, "", button.get(edit.buttons.BTN_NAME))
    except edit.base.EditError:
        return False
    picture = (action.get(edit.base.EXTRAS) or {}).get(edit.buttons.PICTURE_BIT) if isinstance(action, dict) else None
    return isinstance(picture, dict) and picture.get(edit.buttons.PIC_SOURCE) not in (None, 0)


# Как показана кнопка командной панели. Проверено в предприятии: «Картинка» — одна картинка, «Надпись» — один текст
# (картинка при этом не видна), «НадписьКартинка» — оба, «Авто» у кнопки панели С КАРТИНКОЙ — картинка (текст уходит в подсказку).
# **«Авто» у кнопки со СТАНДАРТНЫМ действием — тоже одна картинка, даже без картинки в файле: у стандартного действия есть своя** (T109: значки
# «Найти в списке», «Перечитать», «Скопировать», «?» у кнопок с текстом-заглушкой; T110: «Восстановить значения…» и «Сохранить значения…» с настоящим
# текстом показаны одними значками). Не проверялось: «Авто» без картинки и без стандартного действия (по справке и по образцам — текст),
# «Картинка» без картинки (кнопка пуста).
VIEW_PICTURE, VIEW_BOTH, VIEW_TEXT = "картинка", "картинка и текст", "текст"


def button_view(representation, picture, standard=False):
    """`(как показана, проверено ли)` кнопки панели по её отображению, наличию картинки в файле и стандартному действию (своя картинка у платформы);
    слова — `VIEW_*`, у «Картинки» без картинки — «пусто»."""
    have = picture or standard
    if representation == "Picture":
        return (VIEW_PICTURE, True) if have else ("пусто", False)
    if representation == "Text":
        return VIEW_TEXT, True
    if representation == "PictureText":
        return (VIEW_BOTH, True) if have else (VIEW_TEXT, False)
    return (VIEW_PICTURE, True) if have else (VIEW_TEXT, False)     # «Авто» и не названное отображение


def button_standard(block, button):
    """Стандартное действие кнопки: число или имя перечисления файла; `None` — у кнопки иное действие или записи действия нет."""
    try:
        action = edit.base._action_of(block, button, "", button.get(edit.buttons.BTN_NAME))
    except edit.base.EditError:
        return None
    if edit.buttons._action_kind(block, action) != edit.buttons.STANDARD_KIND:
        return None
    spec = action.get(edit.buttons.ACT_SPEC)
    return spec.get(edit.buttons.STANDARD_ACTION) if isinstance(spec, dict) else None


def button_no_action(block, button):
    """У кнопки панели нет действия: ни обработчика, ни стандартного действия, ни подменю (вид «кнопка без действия» — `NO_ACTION_KIND`). Такую кнопку предприятие показывает серой."""
    try:
        action = edit.base._action_of(block, button, "", button.get(edit.buttons.BTN_NAME))
    except edit.base.EditError:
        return False
    return edit.buttons._action_kind(block, action) == edit.NO_ACTION_KIND


def button_menu_pair(block, button):
    """Пара «GUID набора, код» подменю кнопки либо `None`: кнопка не подменю."""
    try:
        action = edit.base._action_of(block, button, "", button.get(edit.buttons.BTN_NAME))
    except edit.base.EditError:
        return None
    if edit.buttons._action_kind(block, action) != "кнопка-подменю":
        return None
    spec = action.get(edit.buttons.ACT_SPEC)
    return ((spec.get(edit.buttons.REF_ID) or {}).get("guid"), spec.get(edit.buttons.REF_CODE)) if isinstance(spec, dict) else None


def shown_text(block, button):
    """`(текст, откуда)`: что написано на кнопке панели в предприятии. `откуда`: `file` (текст файла), `action` (текст стандартного действия, а в файле
    имя-заглушка `"#"`), `menu` (название стандартного меню у подменю с именем-заглушкой), `stub` (заглушка осталась: платформенного текста в снимках нет)."""
    block_text = button.get(edit.buttons.BTN_TEXT)
    text = lstring.visible_text(block_text) or ""
    if not lstring.is_placeholder(block_text):
        return text.strip(), "file"
    if button.get("button_type") == "Popup":
        name = bar_platform.menu_text(button_menu_pair(block, button))
        return (name, "menu") if name else (text.strip(), "stub")
    code = button_standard(block, button)
    if code is not None:
        name = bar_platform.action_text(code)
        return (name, "action") if name else (_not_stub(text.strip()), "stub")
    return _not_stub(text.strip()), "stub"


ACTION_STUB = re.compile(r"Действие\d*")      # имя, которое платформа даёт новой кнопке панели: подписью на экране не бывает


def _not_stub(text):
    """Заглушка «ДействиеN» на кнопке не рисуется (подпись неизвестна — пустая)."""
    return "" if ACTION_STUB.fullmatch(text) else text


# Кнопка без действия: текст серым #A5944A (самый тёмный пиксель подписей «Добавить», «Записать», «ОК» на снимках e239; у недоступных элементов — `DISABLED_TEXT`, #9C8C4A, из другой выборки).
NO_ACTION_TEXT = "#a5944a"
NO_ACTION_NOTE = ("кнопки командной панели без действия (нет ни обработчика, ни стандартного действия, ни подменю) нарисованы серым текстом #A5944A: так их показало предприятие; "
                  "значок такой кнопки (если она с картинкой) не проверялся")
OPEN_EMPTY_ACTIVE = {"добавить", "упорядочить по возрастанию", "упорядочить по убыванию"}   # активные значки панели пустой таблицы значений при открытии формы
DEFAULT_ACTION = 141       # стандартное действие «Записать и закрыть» — кнопка «ОК»; у панели без номера кнопки по умолчанию она считается кнопкой по умолчанию
PRESSED_FILL = "#efebce"   # заливка нажатой кнопки («Пометка»)
BAR_KIND = {"sep": "Separator", "popup": "Popup", "icon": "Action", "both": "Action", "text": "Action"}


def _file_entries(node):
    """Кнопки верхнего набора панели записями: `{kind: sep|icon|both|text|popup, text, hint, rep, source: file, …}`; значок (`icon`) текста не рисует,
    его название — в `hint` (подсказка)."""
    block = _dig(node, "content", "u1", "actions")
    if not isinstance(block, dict):
        return []  # панель без блока действий (автозаполнение): подписей в файле нет
    own = _own_set(block)
    default_number = _dig(node, "content", "u1", "default_button")
    if not isinstance(default_number, int) or isinstance(default_number, bool):
        default_number = None      # записи панели старой версии позиции не несут
    out = []
    for button in (own or {}).get(edit.base.BUTTONS) or []:
        if not isinstance(button, dict):
            continue
        kind, rep = button.get("button_type"), button.get("representation")
        if kind == "Separator":
            out.append({"kind": "sep", "text": "", "hint": "", "rep": rep, "source": "file", "origin": "file", "popup": False, "enabled": True})
            continue
        text, origin = shown_text(block, button)
        text = _clean(text)
        standard = button_standard(block, button)
        picture = button_has_picture(block, button)
        view, _checked = button_view(rep, picture, standard is not None)
        if kind == "Popup" and not (picture and view in (VIEW_PICTURE, VIEW_BOTH)):
            view = VIEW_TEXT          # подменю без картинки — текстом; с картинкой при «Авто» и «Картинка» — одной картинкой со стрелкой (текст в подсказке)
        nameless = kind == "Popup" and origin == "stub"
        if nameless:
            view = VIEW_PICTURE       # подменю без подписи (в файле заглушка «#»): платформа показывает значок со стрелкой, имя элемента не выводит
        if view in (VIEW_PICTURE, "пусто"):
            entry_kind = "icon"
        elif view == VIEW_BOTH:
            entry_kind = "both"
        else:
            entry_kind = "popup" if kind == "Popup" else "text"
        entry = {"name": button.get(edit.buttons.BTN_NAME), "kind": entry_kind, "text": "" if entry_kind == "icon" else text,
                 "hint": "" if nameless else text or _clean(edit.buttons._button_text(button) or ""),
                 "rep": rep, "source": "file", "origin": origin, "popup": kind == "Popup",
                 "enabled": button.get("enabled") is not False}
        if standard is not None and kind != "Popup":
            entry["std_name"] = bar_platform.action_text(standard)     # значок принадлежит действию, а не подписи: у «Провести» с текстом в файле и «Авто» платформа рисует свою картинку
        if kind != "Popup" and button_no_action(block, button):
            entry["no_action"] = True      # без действия: серый текст (снимок e239), доступность в файле не при чём
        if button.get("check") is True and kind != "Popup":
            entry["check"] = True          # «Пометка» в файле: кнопка нажата (чёрная рамка 1 px и заливка на всю ширину кнопки)
        if kind == "Popup" and entry_kind == "icon":
            entry["arrow"] = True          # подменю одной картинкой: справа от значка стрелка ▾
        bitmap = picture_bitmap.data_uri(button_picture(block, button))
        if bitmap and entry_kind in ("icon", "both"):
            entry["bitmap"] = bitmap       # собственный рисунок кнопки вложен в файл (BMP): рисуется он, а не квадрат
        is_default = standard == DEFAULT_ACTION if default_number is None else bool(default_number) and button.get(edit.buttons.NUMBER) == default_number
        if entry_kind in ("text", "both") and is_default:
            entry["default"] = True        # кнопка по умолчанию: номер задан в записи панели (`default_button`), без него — «Записать и закрыть»
            if standard == DEFAULT_ACTION:
                # Жирной платформа показывает её только со СВОЕЙ процедурой (снимок T280, форма E2); «ОК» со стандартным действием «Записать и закрыть» (141) — обычным
                # шрифтом (T280: E1, D0, C0; T283: D2, C1). Другие стандартные действия у кнопки по умолчанию в снимках не встречались — там по-прежнему жирным.
                entry["plain"] = True
        raw = _clean(lstring.visible_text(button.get(edit.buttons.BTN_TEXT)) or "") if origin == "file" else ""
        if entry_kind == "text" and raw.strip() == text and raw != text:
            entry["raw"] = raw             # пробелы по краям надписи ширину кнопки держат (у «      OK      » кнопка шире текста на 12 пробелов)
        out.append(entry)
    return out


# Кнопки, которые добавляет код модуля (`Кнопки.Добавить(…)`, `Кнопки.Вставить(индекс, …)` у панели формы; в том числе вызовом процедуры общего модуля из `ПриОткрытии`),
# и убирает его (`removed`):
# в файле их нет, а предприятие рисует их при открытии. Рисунок получает их от `marks` (`CodeMarks.parts["buttons"]`, запись разбора кода `created` с целью «кнопка», `brief.codenotes`) и ставит на
# конец набора кнопок панели (место, куда `Кнопки.Вставить` ставит кнопку, запись разбора не хранит) без пометки: что кнопку добавляет код, говорит досье. Показ — как у кнопки файла (`button_view`); картинка — из таблицы
# библиотеки платформы по имени картинки (`platform_pictures`; любое из 299 имён), у неизвестного имени — квадрат. Кнопка, которую код добавляет по условию, не рисуется: в файле её нет, а на экране
# она может быть и не быть.
ADDED_DISPLAY = {"картинка": "Picture", "надпись": "Text", "надписькартинка": "PictureText"}


def _added_entry(add):
    """Запись панели по сведениям о добавляемой кнопке; `None` — рисовать нечего (текст строит код, имени нет)."""
    kind, text = add.get("kind"), add.get("text")
    if kind == "разделитель":
        return {"kind": "sep", "text": "", "hint": "", "rep": None, "source": "code", "origin": "code", "popup": False, "enabled": True, "added": True,
                "name": add.get("name")}
    if not text:
        return None
    rep = ADDED_DISPLAY.get((add.get("display") or "").casefold(), "Auto")
    picture = bool(add.get("picture"))
    popup = kind == "подменю"
    view, _checked = button_view(rep, picture)
    if popup and not (picture and view in (VIEW_PICTURE, VIEW_BOTH)):
        view = VIEW_TEXT
    entry_kind = "icon" if view in (VIEW_PICTURE, "пусто") else "both" if view == VIEW_BOTH else "popup" if popup else "text"
    entry = {"kind": entry_kind, "text": "" if entry_kind == "icon" else _clean(text), "hint": _clean(text), "rep": rep, "source": "code", "origin": "code",
             "popup": popup, "enabled": True, "added": True, "name": add.get("name"), "picture_name": add.get("picture")}
    bitmap = platform_pictures.bitmap(add.get("picture")) if picture else None
    if bitmap is not None:
        entry["bitmap"] = bitmap          # картинка библиотеки платформы по имени из разбора кода
    return entry


def _with_added(entries, added, removed=(), hatch_removed=None, checked=None, disabled=()):
    """Кнопки файла без убранных кодом (`removed` — имена без регистра) плюс добавленные кодом: на место `Вставить`, иначе в конец. Кнопка, которая в файле уже есть под
    тем же именем, не добавляется. `checked` — `{имя без регистра: bool}`: пометка кнопки, которую код ставит безусловно (нажата или нет), сильнее пометки файла. `disabled` — имена без регистра кнопок, которые код безусловно делает недоступными: серые."""
    have = {(e.get("name") or "").casefold() for e in entries if e.get("name")}
    out = [e for e in entries if (e.get("name") or "").casefold() not in removed] if removed else list(entries)
    for e in out:
        key = (e.get("name") or "").casefold()
        if checked and key in checked and e["kind"] != "sep" and not e.get("popup"):
            if checked[key]:
                e["check"] = True
            else:
                e.pop("check", None)
    for e in out:
        if disabled and (e.get("name") or "").casefold() in disabled and e["kind"] != "sep":
            e["enabled"] = False
    for e in out:
        if hatch_removed and (e.get("name") or "").casefold() in hatch_removed:
            e["hatched"] = hatch_removed[(e.get("name") or "").casefold()]       # режим `hatch`: убранная кнопка остаётся на месте со штриховкой; значение — кто её убрал
    for add in added or ():
        entry = _added_entry(add)
        if entry is None or (entry["name"] and entry["name"].casefold() in have):
            continue
        at = add.get("index")
        out.insert(at if isinstance(at, int) and 0 <= at <= len(out) else len(out), entry)
    return out


def _entry_width(entry):
    kind, text = entry["kind"], entry["text"]
    if kind == "sep":
        return BAR_SEP
    if kind == "icon":
        if entry.get("popup") and not entry.get("arrow"):
            return BAR_POPUP_ICON
        return BAR_ICON + (BAR_ARROW if entry.get("arrow") else 0)
    glyph = BAR_GLYPH * (BAR_BOLD if entry.get("bold") else 1)
    font = entry.get("font")
    if kind == "both":
        if font is not None:
            return BAR_BOTH_PAD + textwidth.measure(text, font).px + (BAR_ARROW if entry.get("popup") else 0)
        return BAR_BOTH + glyph * len(text) + (BAR_ARROW if entry.get("popup") else 0)
    if kind == "popup":
        return BAR_POPUP + glyph * len(text)
    if font is not None:     # кнопка с текстом: ширина по метрикам шрифта + 8 (нижняя панель «ОК | Записать | Закрыть» по двум снимкам — до ±1 px)
        return BAR_PAD + textwidth.measure(entry.get("raw", text), font).px
    return BAR_PAD + glyph * len(text)


def _auto_fill_flag(node):
    return _dig(node, "content", "u1", "auto_fill") is True


def _action_source_is_table(node):
    source = _dig(node, "name_block", "action_source")
    return isinstance(source, int) and not isinstance(source, bool) and source not in (0, 4294967295)


def _platform_entries(items):
    """Запись платформы — `(вид, текст)` либо `(вид, текст, подсказка)`: у значка текст — подсказка платформы, у «text» (кнопка с текстом) подсказка своя."""
    return [{"kind": "icon" if kind == "icon▾" else kind, "text": "" if kind in ("icon", "icon▾") else text, "hint": (rest[0] if rest else text), "rep": "Auto",
             "source": "platform", "origin": "platform", "popup": kind == "popup", "arrow": kind == "icon▾"} for kind, text, *rest in items]


def _form_kind(doc):
    """Вид формы: из контекста сборки досье (`bar_platform.context`), иначе по основному реквизиту документа; `None` — не определить."""
    got = bar_platform.current()
    if got.get("kind"):
        return got["kind"]
    if doc is not None:
        from .. import census
        return census.KNOWN.get(census.main_attribute(doc))
    return None


def table_kind_of(item):
    """Вид данных табличного поля по типу его колонок: «список», «табличная часть», «таблица значений», «список значений»; `None` — колонок нет или тип не известен."""
    block = edit.columns.columns_of(item.node) if item is not None else None
    for column in (block[edit.columns.COLUMN_ITEMS] if block is not None else ()):
        kind = column.get(edit.columns.COLUMN_TYPE) if isinstance(column, dict) else None
        if isinstance(kind, dict) and kind.get("guid") in edit.platform.COLUMN_KINDS:
            return edit.platform.COLUMN_KINDS[kind["guid"]]
    return None


def _table_data_kind(node, doc):
    """Вид данных табличного поля, чьи действия показывает панель `node` (`name_block/action_source`): из контекста сборки досье, иначе по колонкам таблицы в `doc`."""
    source = _dig(node, "name_block", "action_source")
    known = bar_platform.current().get("tables")
    if known is not None:
        return known.get(source)
    if doc is None or not _action_source_is_table(node):
        return None
    try:
        return table_kind_of(layout.read(doc).items.get(source))
    except edit.EditError:
        return None


def has_saved_values(doc):
    """У основного реквизита формы непустой список «Сохраняемые значения» (формы обработки и отчёта)."""
    saved = _dig(doc, "main_attribute", "u2", "saved_values")
    count = saved.get("count") if isinstance(saved, dict) else None
    return isinstance(count, int) and not isinstance(count, bool) and count > 0


def _is_bottom(node):
    """Нижняя панель формы: линия сверху (у верхней панели формы — подчёркивание)."""
    return _dig(node, "content", "u1", "u0", "border", "border_type") == "Overline"


def _has_main_attribute(doc):
    """У формы есть основной реквизит (документ без списка реквизитов — как с основным: контекст сборки досье называет вид сам)."""
    if not isinstance(doc, dict) or not isinstance(doc.get("attributes"), dict):
        return True
    from .. import census
    return census.main_attribute(doc) is not None


def _platform_fill(node, doc):
    table = _action_source_is_table(node)
    return bar_platform.fill(table, _form_kind(doc), bar_platform.current().get("posting"), bar_platform.current().get("groups"),
                             _table_data_kind(node, doc) if table else None, has_saved_values(doc),
                             bottom=_is_bottom(node), main=_has_main_attribute(doc))


# Вертикальная командная панель (ориентация панели в файле — «Вертикальная»; «Авто» — по форме: выше, чем шире): значки столбиком, по 23 px на значок вдоль высоты
# (снимок T110-5: две кнопки «+» и «×» панели 24×101 слева от таблицы стоят одна под другой по центру ширины панели). Первый значок — не у самого верха панели
# (на снимке его центр ≈ на 40 px ниже верха панели рядом с таблицей, шапка таблицы 20 px): `BAR_VSTART` — по снимку, ±3 px. Текстовые кнопки и подменю
# вертикальной панели не наблюдались: нарисованы значком (подсказка — текст кнопки).
BAR_VSTART = 28.5
VERTICAL_NOTE = ("вертикальная командная панель (ориентация «Вертикальная» либо «Авто» у панели выше, чем шире): значки нарисованы столбиком, по 23 px на значок; "
                 "положение первого значка по наблюдению в предприятии (±3 px), текстовые кнопки и подменю вертикальной панели не наблюдались и нарисованы значком")


def bar_vertical(node, w, h):
    """Панель рисуется столбиком: ориентация в файле «Vertical»; «Auto» — когда панель выше, чем шире (как её ставит платформа, по форме, не проверялось); «Horizontal» — никогда."""
    orientation = _dig(node, "content", "u1", "orientation")
    return orientation == "Vertical" or (orientation not in ("Horizontal", "Vertical") and h > w)


def _vertical_layout(node, h, doc=None):
    """Раскладка вертикальной панели высотой `h`: `(записи, переполнена, слова)`; `start` — от верха панели, ширина записи вдоль высоты — `BAR_ICON`."""
    entries, _overflow, words = bar_layout(node, 10 ** 6, doc)
    out, at = [], BAR_VSTART
    overflow = False
    for e in entries:
        if e["kind"] == "sep":
            size = BAR_SEP
        else:
            e = dict(e, kind="icon", text="", width=BAR_ICON, hint=e["hint"] or e["text"])
            size = BAR_ICON
        if at + size > h - BAR_MORE:
            overflow = True
            break
        out.append(dict(e, start=at, width=size))
        at += size
    return out, overflow, words


def bar_layout(node, w, doc=None, added=None, removed=(), hatch_removed=None, checked=None, disabled=()):
    """Раскладка панели шириной `w`: `(записи, переполнена, слова)`. Запись — `{kind, text, hint, source, start, width, …}`: кнопки файла и (у панели с
    автозаполнением) кнопки платформы по наблюдению (`bar_platform.fill`); `слова` — чего в составе автозаполнения не известно (`None` — известно всё).
    Начало — от левого края панели. Не поместившиеся кнопки уходят под «»» (переполнена). Ширины приблизительные (`BAR_*`): места — оценка рендера.

    Порядок у панели с автозаполнением: кнопки файла до подменю «Перейти» (если оно есть) — голова платформы — «Перейти» — хвост платформы — остальные кнопки
    файла; без «Перейти» в файле — голова, хвост, кнопки файла. У двух наблюдённых списков «обновить» стоит по-разному относительно «Перейти»: оценка."""
    entries = _with_added(_file_entries(node), added, removed, hatch_removed, checked, disabled)
    font = textwidth.element_font(node, doc)
    bold = font["bold"]
    for e in entries:
        e["bold"] = bold or bool(e.get("default") and not e.get("plain"))
        e["font"] = dict(font, bold=True) if e["bold"] else font
    words = None
    if _auto_fill_flag(node):
        head, tail, words, _src = _platform_fill(node, doc)
        head, tail = _platform_entries(head), _platform_entries(tail)
        if _action_source_is_table(node) and _table_data_kind(node, doc) == bar_platform.TABLE_VALUES:
            for e in head + tail:          # таблица значений при открытии пуста: активны «Добавить» и сортировки, прочее серое (T249: 05–08; T292: 05)
                if e["kind"] == "icon" and action_icons.key_of(e["hint"]) not in OPEN_EMPTY_ACTIVE:
                    e["enabled"] = False
        # кнопок с текстом платформа не ставит (`bar_platform`): «Выбрать» у списка справочника — кнопка файла (стандартное действие 95), двойника у неё нет
        if head or tail:
            goto = next((i for i, e in enumerate(entries) if e["popup"] and e["origin"] == "menu" and e["text"] == "Перейти"), None)
            if goto is not None:
                entries = entries[:goto] + head + entries[goto:goto + 1] + tail + entries[goto + 1:]
            else:
                entries = head + tail + entries
    entries = _tidy(entries)
    for e in entries:
        e["width"] = _entry_width(e)
    total = sum(e["width"] for e in entries)
    align = _dig(node, "content", "u1", "buttons_alignment")
    room = w - BAR_START - BAR_END
    overflow = total > room
    if overflow:
        kept, used = [], 0
        for e in entries:
            if used + e["width"] > room - BAR_MORE:
                break
            kept.append(e)
            used += e["width"]
        entries, total, align = kept, used, "Left"
    at = BAR_START
    if align == "Right":
        at = w - BAR_RIGHT_END - total
    elif align == "Center":
        at = (w - total) / 2
    for e in entries:
        e["start"] = at
        at += e["width"]
    return entries, overflow, words


def _tidy(entries):
    """Разделители подряд сворачиваются в один, в начале и в конце полосы разделителей нет."""
    out = []
    for e in entries:
        if e["kind"] == "sep" and (not out or out[-1]["kind"] == "sep"):
            continue
        out.append(e)
    while out and out[-1]["kind"] == "sep":
        out.pop()
    return out


def _bar_buttons(node):
    """`[(вид, подпись, представление, ширина)]` кнопок верхнего набора панели в файле (кнопок платформы нет)."""
    return [(BAR_KIND[e["kind"]], e["text"] + (" ▾" if e["kind"] == "popup" else ""), "Picture" if e["kind"] == "icon" else e["rep"], _entry_width(e))
            for e in _file_entries(node)]


# Командная панель с автозаполнением (`auto_fill`): платформа ставит свой состав сама. Состав известен по наблюдению для панели формы документа,
# формы списка документов и справочника и табличного поля (`bar_platform.fill`); у остальных видов формы кнопок платформы рендер не угадывает, а рисует
# полосу без кнопок: пунктирный контур внутри box и пометку. Контур и пометка показывают место, а не вид, который нарисует платформа.
AUTO_FILL_MARK = "кнопки: автозаполнение"
AUTO_FILL_NOTE = ("у командной панели с автозаполнением кнопок в файле нет, а состав у этого вида формы в предприятии не наблюдался: платформа "
                  "рисует полосу значков сама (полоса 24 px над таблицей), состав и ширины не проверялись — нарисована полоса "
                  "без кнопок с пометкой «" + AUTO_FILL_MARK + "»")
AUTO_FILL_KNOWN_NOTE = ("командная панель с автозаполнением: кнопки платформы нарисованы по наблюдению в предприятии (" + bar_platform.FILL_SOURCE + "), в файле "
                        "их нет; значок стандартного действия — картинка библиотеки платформы, неизвестное название — серый квадрат, "
                        "название — подсказка (`title`); порядок кнопок платформы и файла и ширины приблизительные")
ICON_NOTE = ("у командной панели значок стандартного действия (отображение «Картинка», «Авто») — картинка библиотеки платформы; картинка конфигурации "
             "рисуется из выгрузки, а без её файла — серый квадрат, название — подсказка (`title`); ширина значка 23 px по наблюдению в предприятии")


def _auto_fill_bar(it, doc=None):
    """Панель с `auto_fill`, у которой нет ни кнопок файла, ни наблюдённого состава платформы: полоса оставлена платформе."""
    if not _auto_fill_flag(it.node) or _file_entries(it.node):
        return False
    head, tail, _words, _src = _platform_fill(it.node, doc)
    return not (head or tail)


def _auto_fill_known(it, doc=None):
    """Панель с `auto_fill`, у которой состав платформы известен по наблюдению."""
    if not _auto_fill_flag(it.node):
        return False
    head, tail, _words, _src = _platform_fill(it.node, doc)
    return bool(head or tail)


def _auto_fill_strip(it, x, y, w, h):
    if w < 8 or h < 6:
        return []
    return [f"<rect class='auto-fill' x='{_n(x + 2.5)}' y='{_n(y + 2.5)}' width='{_n(w - 5)}' height='{_n(h - 5)}' fill='none' "
            "stroke='#b5b184' stroke-dasharray='3 2'/>",
            f"<text class='auto-fill-mark' x='{_n(x + 8)}' y='{_n(y + h - 7)}' text-anchor='start' font-family='Tahoma, sans-serif' "
            f"font-size='9' fill='#999'>{AUTO_FILL_MARK}</text>"]


def bar_spans(node, w):
    """Кнопки, которые панель шириной `w` рисует, и места их левых краёв: `([(вид, подпись, представление, начало, ширина)], переполнена)`.
    Начало — от левого края панели. Не поместившиеся кнопки уходят под «»» (переполнена), подписи не выпускаются. Ширины кнопок
    приблизительные (`BAR_*`): места — оценка рендера. У панели с автозаполнением в раскладку входят и кнопки платформы по наблюдению."""
    entries, overflow, _words = bar_layout(node, w)
    return [(BAR_KIND[e["kind"]], e["text"] + (" ▾" if e["kind"] == "popup" else ""), "Picture" if e["kind"] == "icon" else e["rep"], e["start"], e["width"])
            for e in entries], overflow


def _action_of(entry):
    """Название стандартного действия записи панели для значка: у кнопки платформы и у стандартного действия файла; у кнопки с картинкой конфигурации — нет."""
    if entry.get("origin") == "code":
        return None          # картинку из библиотеки, которую код назначил кнопке (`БиблиотекаКартинок.Печать`), даёт `entry["bitmap"]`
    if entry.get("origin") in ("action", "platform"):
        return entry["hint"]
    return entry.get("std_name")      # текст из файла, картинка — стандартного действия (значок одной картинкой): рисуется значок по названию действия


def _arrow_mark(x, y):
    """Стрелка ▾ рядом со значком (у «Истории отборов», «Отбор по виду документа»)."""
    return f"<path class='icon-arrow' d='M{_n(x)} {_n(y - 1)}h5l-2.5 3z' fill='#423100'/>"


def _vertical_bar(doc, it, x, y, w, h):
    entries, overflow, _words = _vertical_layout(it.node, h, doc)
    clip = f"bar{it.index}"
    out = [f"<clipPath id='{clip}'><rect x='{_n(x)}' y='{_n(y)}' width='{_n(w)}' height='{_n(h)}'/></clipPath>",
           f"<g clip-path='url(#{clip})'>"]
    for e in entries:
        at = y + e["start"]
        if e["kind"] == "sep":
            line = int(at + BAR_SEP / 2) + 0.5
            out.append(f"<line x1='{_n(x + 3)}' y1='{_n(line)}' x2='{_n(x + w - 3)}' y2='{_n(line)}' stroke='#b5b184'/>")
        else:
            out.append(_icon(x + (w - BUTTON_ICON) / 2, at + (BAR_ICON - BUTTON_ICON) / 2, e["hint"], _action_of(e), e.get("bitmap")))
    if overflow:
        out.append(_text(x + w / 2, y + h - 3, "»", "middle"))
    out.append("</g>")
    return out


_HEX = re.compile(r"#([0-9a-fA-F]{6})\b")


def _pale(match):
    r, g, b = (int(match.group(1)[i:i + 2], 16) for i in (0, 2, 4))
    grey = 0.299 * r + 0.587 * g + 0.114 * b
    level = round(grey * 0.55 + 232 * 0.45)       # значок недоступной кнопки в предприятии — бледно-серый (снимки T249, T292, T280: серые «Перечитать», «Отмена проведения»)
    return f"#{level:02x}{level:02x}{level:02x}"


def _grey_icons(parts):
    """Значок недоступной кнопки: картинка (`<image class='icon …'>`) идёт через фильтр `OFF_FILTER` (так её сводит платформа), квадрат-заглушка — бледно-серый (подписи уже серые — `_grey`)."""
    return [part.replace("<image class='icon", f"<image filter='url(#{OFF_FILTER_ID})' class='icon", 1) if part.startswith("<image class='icon")
            else _HEX.sub(_pale, part) if "class='icon" in part else part for part in parts]


def _command_bar(doc, it, x, y, w, h, added=None, removed=(), hatch_removed=None, checked=None, disabled=()):
    if bar_vertical(it.node, w, h) and not _auto_fill_bar(it, doc):
        return _vertical_bar(doc, it, x, y, w, h)
    if _auto_fill_bar(it, doc):
        return _auto_fill_strip(it, x, y, w, h)
    entries, overflow, _words = bar_layout(it.node, w, doc, added, removed, hatch_removed, checked, disabled)
    clip = f"bar{it.index}"
    out = [f"<clipPath id='{clip}'><rect x='{_n(x)}' y='{_n(y)}' width='{_n(w)}' height='{_n(h)}'/></clipPath>",
           f"<g clip-path='url(#{clip})'>"]
    bar_off = _enabled(it.node) is False or not _form_enabled(doc)  # недоступна вся панель или вся форма
    for e in entries:
        at = x + e["start"]
        kind = e["kind"]
        first = len(out)
        if e.get("check") and kind != "sep":
            out.append(f"<rect class='button-pressed' x='{_n(at + 0.5)}' y='{_n(y + 1.5)}' width='{_n(e['width'] - 1)}' height='{_n(h - 3)}' fill='{PRESSED_FILL}' stroke='#000000'/>")
        if kind == "sep":
            out.append(_vline(int(at + BAR_SEP / 2) + 0.5, y + 3, y + h - 3, "#b5b184"))        # линия на полупикселе: разделитель по снимку — столбец 68–69 при центре 68
        elif kind in ("icon", "both"):
            left = math.floor(at) + ((e["width"] - BUTTON_ICON) // 2 if kind == "icon" else (BAR_ICON - BUTTON_ICON) // 2)     # значок панели — на целом пикселе: начало кнопки отбрасывается до целого (24,5 → 24), поле значка — целое (23 px → 3); у кнопки с текстом то же (T337: панель формы, начало 1,5 → значок на x = 4, второй значок 164,5 → 167)
            out.append(_icon(left, y + (h - BUTTON_ICON) // 2, e["hint"], _action_of(e), e.get("bitmap")))
            if e.get("arrow"):
                out.append(_arrow_mark(left + BUTTON_ICON + 1, y + h // 2))
            if kind == "both":
                out.append(_text(at + (BAR_BOTH_TEXT if e.get("font") is not None else BAR_BOTH - 4.5), y + h - 7, e["text"] + (" ▾" if e.get("popup") else ""),
                                 font={"bold": True} if e.get("bold") else None))
        elif e["text"]:
            lead = textwidth.measure(" " * (len(e["raw"]) - len(e["raw"].lstrip())), e["font"]).px if e.get("raw") else 0   # пробелы перед надписью сдвигают её
            shown = _text(at + BAR_PAD / 2 + lead, y + h - 7, e["text"] + (" ▾" if kind == "popup" else ""), font={"bold": True} if e.get("bold") else None)
            if kind == "text" and e["source"] == "platform" and e["hint"] and e["hint"] != e["text"]:      # подсказка кнопки платформы с текстом («Выбрать значение»)
                shown = f"<g>{shown}<title>{escape(e['hint'])}</title></g>"
            out.append(shown)
        if bar_off or not e.get("enabled", True):
            out[first:] = _grey_icons(_grey(out[first:]))
        elif e.get("no_action"):
            out[first:] = _grey(out[first:], NO_ACTION_TEXT)
        if e.get("hatched"):
            out += hidden_overlay(at, y, e["width"], h, e["hatched"])
    if overflow:
        out.append(_text(x + w - 12, y + h - 7, "»"))
    out.append("</g>")
    return out


# Командная панель формы (источник действий — форма, `name_block/action_source == 0`: `ДействияФормы`,
# `ОсновныеДействияФормы`): заливка #F7F7DE и одна линия #B5B184 со стороны содержимого — у верхней панели по
# нижнему краю box, у нижней по верхнему. С другой стороны проходит линия страницы формы. Командная панель над
# таблицей и любая другая (источник не форма) рисуются без заливки и линий: виден фон формы.
FORM_BAR_FILL, FORM_BAR_LINE = "#f7f7de", "#b5b184"


def _form_bar(it):
    return it.type == "CommandBar" and _dig(it.node, "name_block", "action_source") == 0


NO_SOURCE = 4294967295


def _free_filled_bar(it):
    """Панель без источника действий и без прозрачности залита своим цветом фона: «Авто» — заливка #F7F7DE (проверено на трёх панелях обработки и верхней панели элемента справочника; прозрачные панели тех же форм заливки не имеют);
    явный цвет — этот цвет (не сверено); цвет стиля «Фон формы» — заливки нет (панели «Отгрузки» с таким фоном стоят в предприятии прямо на фоне формы, ни заливки, ни линии). Прочие цвета стиля и системные — как «Авто», слова в `notes`.
    Линию рисует `border_type` панели («Снизу» — внизу, «Сверху» — вверху; без рамки — без линии)."""
    return (it.type == "CommandBar" and _dig(it.node, "name_block", "action_source") == NO_SOURCE
            and _dig(it.node, "content", "u1", "u0", "transparent") is False and _back_of(it.node)[0] != "form")


def _filled_bar(it):
    return _form_bar(it) or _free_filled_bar(it)


def bar_fill(it):
    """Заливка командной панели: `none`, цвет панели формы или явный цвет фона свободной панели."""
    if not _filled_bar(it):
        return "none"
    if _free_filled_bar(it):
        kind, color, _words = _back_of(it.node)
        if kind == "rgb":
            return color
    return FORM_BAR_FILL


BAR_BACK_NOTE = "заливка командной панели явным цветом фона не сверялась с предприятием (сверены «Авто» и стиль «Фон формы»)"


def bar_back_notes(it):
    """Слова о цвете фона свободной непрозрачной панели, которого рендер не знает, либо `[]`."""
    if not (it.type == "CommandBar" and _dig(it.node, "name_block", "action_source") == NO_SOURCE
            and _dig(it.node, "content", "u1", "u0", "transparent") is False):
        return []
    kind, _color, words = _back_of(it.node)
    if kind == "rgb":
        return [BAR_BACK_NOTE]
    if kind == "other":
        return [f"цвет фона командной панели задан стилем или системой ({words}): панель залита как при «Авто» (#F7F7DE)"]
    return []


def _form_bar_line(it, x, y, w, h, height):
    """Линия панели формы со стороны содержимого: у панели в верхней половине клиентской области она внизу, иначе
    вверху. У свободной залитой панели — по `border_type` (`Underline` — внизу, `Overline` — вверху)."""
    if _free_filled_bar(it):
        kind = _dig(it.node, "content", "u1", "u0", "border", "border_type")
        if kind not in ("Underline", "Overline"):
            return []
        at = y + h - 0.5 if kind == "Underline" else y + 0.5
        return [f"<line class='bar-line' x1='{_n(x)}' y1='{_n(at)}' x2='{_n(x + w)}' y2='{_n(at)}' stroke='{FORM_BAR_LINE}'/>"]
    if not _form_bar(it):
        return []
    at = y + h - 0.5 if y + h / 2 < height / 2 else y + 0.5
    return [f"<line class='bar-line' x1='{_n(x)}' y1='{_n(at)}' x2='{_n(x + w)}' y2='{_n(at)}' stroke='{FORM_BAR_LINE}'/>"]
