"""Факты для оценки формы: наблюдения кода с числами и без оценок (раздел «Факты» досье формы).

`facts(doc, structure, meta=None, object_name=None)` возвращает список `Fact(kind, node, element, numbers, words)`:

* `kind` — вид факта (порядок видов ниже — порядок в списке);
* `node` — номер узла структуры (`structure.recognize`) либо `None`, если факт про форму целиком;
* `element` — полное имя элемента так, как оно названо в структуре (`Structure.by_element`), либо `None`; в `words` элемент назван
  коротким именем: полное — только у тёзок (`_Names.short`);
* `numbers` — числа факта словарём; `words` — одна фраза без оценки.

Виды фактов по порядку:

1. `field_width` — ширина поля ввода против данных. Строка длины N: нужная ширина — N средних знаков шрифта элемента (`AVERAGE_TEXT`,
   `textwidth`). Число: разрядность (плюс знак дробной части), знаки «0». Факт, если поле уже нужного (строки длиннее `LONG` знаков не
   проверяются: поле под них уже данных у большинства форм), либо если данных мало (не больше `SHORT` знаков) и поле шире нужного втрое.
   Дата: ширина против нормы 80 (дата) и 120 (дата со временем), факт при расхождении больше `DATE_TOLERANCE` px. Многострочные поля и
   поля составного или неизвестного типа не проверяются; у шрифта, который не проверялся, число — оценка (`numbers["exact"]`).
2. `caption_cut` — текст надписи (флажка, кнопки) шире элемента: подпись в платформе усекается.
   `column_cut` — заголовок колонки табличного поля шире колонки: шапка усекает его с «…» (ширины колонок — как при рисовании, `render.column_edges`;
   нужное — текст заголовка по шрифту шапки плюс отступ `TABLE_TEXT_PAD`; у непроверенного шрифта число — оценка).
3. `tab_order` — порядок обхода (поле `tab_order`, числа «Порядок обхода…», по ним идёт Tab) не совпадает с порядком чтения. Сравниваются видимые элементы, принимающие фокус, в пределах одной
   страницы одного родителя. Факт называет две последовательности узлов («по обходу», «по чтению») и элементы не на месте — те, что не
   входят в наибольшую общую подпоследовательность обоих порядков (`lcs_keep`); у контейнера названо свойство «автопорядок обхода».
4. `default_button` — есть ли кнопка по умолчанию и какая, и режим клавиши Enter формы. Кнопка по умолчанию командной панели — та, чей номер записан в
   панели (`default_button` записи панели); у кнопок-элементов — свой признак. Если на форме нет ни кнопок-элементов, ни кнопок командных панелей, факт говорит
   «быть не может» (`numbers["applicable"]` ложно).
5. `active_on_open` — какой элемент активен при открытии. Факта нет, если на странице нет элементов, принимающих фокус.
6. `out_of_bounds` — элемент выходит за край родителя или имеет нулевой размер (из узлов «неясно» структуры).
7. `overlap` — элемент перекрывается с другими (из узлов «неясно» структуры).
   `bar_covered` — видимый элемент лежит на командной панели и закрывает её кнопки (места кнопок — оценка рендера).
   `labels` — подписи (`_labels`): двоеточие в конце надписи пар «надпись → поле» есть у одних и нет у других, пробел перед двоеточием, надпись с данными
   без подписи рядом, поле ввода без подписи и без подсказки (`numbers["rule"]`: `colon_mix`, `space_before_colon`, `data_label_alone`, `field_unlabeled`).
8. `invisible`, 9. `disabled` — скрытые и недоступные элементы.
10. `required_missing` — реквизит объекта с проверкой заполнения без элемента на форме (нужна выгрузка `meta`).
11. `data_missing` — поле, флажок, переключатель, поле выбора или табличное поле без привязки к данным; переключатель не первый
    в группе данных не несёт (они у первого).
12. `lint`, 13. `anchors`, 14. `guides` — замечания линтера, поломки привязок (`repair.diagnose`) и предупреждение о дальних
    направляющих края (`guides.far_words`) словами о том, что видит пользователь (`brief.words`): без имён операций, номеров позиций и
    формул привязок; повреждённые записи привязок сведены в одну находку.

Форму модуль не меняет. Вывод детерминирован: тот же документ даёт тот же список.
"""
import collections
import math
import re

from .. import describe, design, edit, guides, layout, lint, patterns, render, repair, textgap, textwidth
from . import content as br_content, words as br_words
from ..edit import elements as ed_elements
from .. import structure as structure_mod
from ..edit import names as N
from ..edit.names import DEFAULT_BUTTON, DEFAULT_CONTROL, NO_REFERENCE, TAB_ORDER

Fact = collections.namedtuple("Fact", "kind node element numbers words")

KINDS = ("field_width", "caption_cut", "column_cut", "tab_order", "default_button", "active_on_open", "out_of_bounds", "overlap",
         "bar_covered", "labels", "invisible", "disabled", "required_missing", "data_missing", "lint", "anchors", "guides")

AVERAGE_TEXT = ("Съешь же ещё этих мягких французских булок да выпей чаю Наименование организации контрагента договор склад "
                "Иванов Иван Иванович Петрова Мария Сергеевна Общество с ограниченной ответственностью Ромашка")
DIGIT_GLYPH = "0"       # знак, которым считается число
SHORT = 10              # данных не больше стольких знаков: поле шире нужного втрое — факт
LONG = 60               # строка длиннее стольких знаков в «поле уже нужного» не считается: поле под длинный текст уже данных у большинства форм
WIDER_TIMES = 3
DATE_NORMS = {"Date": 80, "DateTime": 120}   # ширина поля даты и даты со временем
DATE_TOLERANCE = 20     # расхождение ширины поля даты с нормой больше стольких px — факт
MINORITY_LISTED = 8     # элементов меньшинства раскола вида называется поимённо не больше стольких
LISTED = 3             # сколько имён сводной находки называется поимённо
MISMATCH_LIMIT = 5      # сколько элементов не на месте порядка обхода называется поимённо
SEQUENCE_LIMIT = 12     # длина последовательности узлов порядка обхода и порядка чтения в слове факта

PAD = {"Label": 0, "CheckBox": render.CHECK_CAPTION_PAD, "Button": render.BUTTON_CAPTION_PAD}
NOT_FOCUSED = frozenset({"Label", "GroupBox", "PictureBox", "Splitter", "CommandBar", "Panel", "ProgressBar"})
EXPECT_DATA = frozenset({"TextBox", "CheckBox", "RadioButton", "ComboBox", "TableBox"})
PATTERN_DIGITS, PATTERN_FRACTION = N._at("PatternType.N", 1), N._at("PatternType.N", 2)

_NUMBER = (int, float)


class _Names:
    """Имя элемента в структуре: `qualified()`, у тёзок с `#индекс` (так названы листья `Structure.by_element`)."""

    def __init__(self, form, structure):
        self.structure = structure
        self.by_item = {}
        for item in form.items.values():
            name = item.qualified()
            if name not in structure.by_element:
                name = f"{name}#{item.index}"
            self.by_item[item.index] = name
        self.item_of = {name: form.items[index] for index, name in self.by_item.items()}
        self.shortener = br_words.Shortener(self)

    def of(self, item):
        return self.by_item[item.index]

    def node(self, name):
        return self.structure.by_element.get(name)

    def short(self, name_or_item):
        """Короткое имя элемента (полное — только у тёзок); принимает имя в структуре или сам элемент."""
        name = name_or_item if isinstance(name_or_item, str) else self.of(name_or_item)
        return self.shortener.name(name)

    def text(self, text):
        """Текст, в котором полные имена элементов заменены короткими."""
        return self.shortener.text(text)


def _enabled(node):
    """Флаг доступности элемента (`enabled` в блоке свойств): ближайший к корню; нет значения — доступен."""
    level = [node]
    while level:
        nxt = []
        for block in level:
            for key, value in block.items():
                if key == N.ELEMENTS:
                    continue
                if key == "enabled" and isinstance(value, bool):
                    return value
                if isinstance(value, dict):
                    nxt.append(value)
        level = nxt
    return True


def _pattern(item):
    """Единственный блок типа поля ввода (`{"kind": "S", …}`) или `None`: типа нет либо он составной."""
    content = item.node.get(N.CONTENT)
    pattern = content.get(N.TEXTBOX_PATTERN) if isinstance(content, dict) else None
    types = pattern.get(N.PATTERN_TYPES) if isinstance(pattern, dict) else None
    if isinstance(types, list) and len(types) == 1 and isinstance(types[0], dict):
        return types[0]
    return None


def _int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _need_width(kind, count, font):
    """`(нужная ширина px, измерено ли точно)`: строка — `count` средних знаков шрифта (`AVERAGE_TEXT`), число — `count` знаков «0»."""
    if kind == "S":
        got = textwidth.measure(AVERAGE_TEXT, font)
        return math.ceil(got.px * count / len(AVERAGE_TEXT)), got
    got = textwidth.measure(DIGIT_GLYPH * count, font)
    return got.px, got


def _field_widths(form, doc, names, out):
    """Ширина поля — по модели раскладки при размере формы, как её увидит пользователь; у страницы шире панели она иная, чем в файле, и тогда
    факт называет ширину в файле словами. Сравнение — с разрядностью реквизита (`Pattern`), а не с реальными значениями."""
    model = layout.model_boxes(form)
    for holder in form.holders.values():
        for item in holder.children:
            if item.type != "TextBox" or not item.visible or describe._multiline(item):
                continue
            block = _pattern(item)
            if block is None:
                continue
            kind = block.get(N.PATTERN_KIND)
            font = textwidth.element_font(item.node, doc)
            file_box = lint._file_box(item)
            box = model.get(item.index) or file_box
            have = box[2] - box[0]
            in_file = file_box[2] - file_box[0] if have != file_box[2] - file_box[0] else None
            seen = f" (на экране при размере формы; в файле {in_file} px)" if in_file is not None else ""
            name = names.of(item)
            if kind == "S":
                count, unit = block.get(N.PATTERN_LENGTH), ("знак строки", "знака строки", "знаков строки")
            elif kind == "N":
                digits, fraction = block.get(PATTERN_DIGITS), block.get(PATTERN_FRACTION)
                count = digits + (1 if _int(fraction) and fraction > 0 else 0) if _int(digits) else None
                unit = ("знак числа", "знака числа", "знаков числа")
            elif kind == "D":
                composition = textgap.date_composition(item.node)
                norm = DATE_NORMS.get(composition)
                if norm is not None and abs(have - norm) > DATE_TOLERANCE:
                    which = "дату со временем" if composition == "DateTime" else "дату"
                    out.append(Fact("field_width", names.node(name), name,
                                    {"type": "date", "composition": composition, "have": have, "norm": norm, **({"in_file": in_file} if in_file is not None else {})},
                                    f"поле на {which} шириной {have} px{seen}; норма {norm} px"))
                continue
            else:
                continue
            if not _int(count) or count <= 0:
                continue
            need, got = _need_width(kind, count, font)
            narrow = have < need and count <= LONG
            wide = count <= SHORT and have > WIDER_TIMES * need
            if not (narrow or wide):
                continue
            numbers = {"type": "string" if kind == "S" else "number", "length": count, "need": need, "have": have,
                       "exact": got.exact, **({"in_file": in_file} if in_file is not None else {})}
            what = br_words.plural(count, *unit)
            words = f"поле {have} px{seen} на {count} {what}; по шрифту нужно {need} px"
            if kind == "S":
                words += " (средний знак шрифта элемента)"
            if not got.exact:
                words += f" (оценка: {got.why})"
            out.append(Fact("field_width", names.node(name), name, numbers, words))


def _caption_rows(form, doc):
    """Надписи, флажки и кнопки с текстом, которым хватает знаков для расчёта: `[(элемент, текст, отступ, есть px, замеры строк)]`.
    Надпись в несколько строк (переносит текст) и текст со знаком вне таблицы ширин при непроверенном шрифте (рендер его не усекает)
    не берутся."""
    for holder in form.holders.values():
        for item in holder.children:
            if not item.visible or item.type not in PAD:
                continue
            text = render.caption_text(item.node, item.type)
            if not text:
                continue
            font = textwidth.element_font(item.node, doc)
            box = lint._file_box(item)
            if item.type == "Label" and textgap.wraps(box, font):
                continue                              # надпись в несколько строк переносит текст: узкая коробка не усечение
            lines = [textwidth.measure(line, font) for line in (text.splitlines() or [text])]
            if not all(m.exact for m in lines) and any(ch not in textwidth.ADVANCE and ch not in "\r\n" for ch in text):
                continue                              # шрифт не проверен и есть знак вне таблицы: рендер подпись не усекает, оценки нет
            yield item, text, PAD[item.type], box[2] - box[0], lines


def _caption_cuts(form, doc, names, out):
    """Подпись шире элемента. Шрифт не проверен (размер стиля, системный шрифт…) — факт по той же оценке, что рисует рендер, с пометкой
    «оценка» (`numbers.exact` ложно); `unchecked_captions` называет элементы, у которых точный расчёт невозможен и фактов нет."""
    for item, text, pad, have, got in _caption_rows(form, doc):
        need = pad + max(m.px for m in got)
        if need <= have:
            continue
        exact = all(m.exact for m in got)
        name = names.of(item)
        words = f"подпись «{text}» требует {'' if exact else '≈'}{_px(need)} px, элемент {_px(have)} px"
        if not exact:
            words += f" (оценка: {next(m.why for m in got if not m.exact)})"
        out.append(Fact("caption_cut", names.node(name), name,
                        {"type": item.type, "need": need, "have": have, "text_width": need - pad, "pad": pad, "exact": exact}, words))


def _px(value):
    """Ширина в px для текста факта: до десятых, целое без хвоста (в расчёте бывает 53.9999999999999)."""
    rounded = round(value, 1)
    return int(rounded) if rounded == int(rounded) else rounded


def _header_picture(head):
    """У колонки в шапке стоит картинка (значок вместо текста): источник картинки заголовка не «нет»."""
    picture = head.get("header_picture")
    return isinstance(picture, dict) and picture.get("source") not in (None, 0)


def _column_cuts(form, doc, names, out):
    """Заголовок колонки табличного поля шире колонки: шапка усекает его с «…» (то же вычисление, что у рисунка, — `render.header_cuts`)."""
    for holder in form.holders.values():
        for item in holder.children:
            if not item.visible or item.type != "TableBox":
                continue
            box = layout.model_boxes(form).get(item.index) or lint._file_box(item)
            name = names.of(item)
            pictured = {c["name"] for c in render.tables.table_columns(item) if _header_picture(c["head"])}
            for cut in render.header_cuts(doc, item, box[2] - box[0]):
                cut = dict(cut, icon=cut["column"] in pictured)
                approx = "" if cut["exact"] else "≈"
                words = (f"заголовок колонки «{cut['column'] or '?'}» таблицы «{names.short(name)}»: «{cut['text']}» требует {approx}{_px(cut['need'])} px, "
                         f"колонка {_px(cut['have'])} px — шапка усекает его с «…»")
                if cut["why"]:
                    words += f" (оценка: {cut['why']})"
                out.append(Fact("column_cut", names.node(name), name, dict(cut, need=_px(cut["need"]), have=_px(cut["have"]), table=name), words))


def unchecked_captions(doc, structure):
    """Подписи, которые по непроверенному шрифту нельзя сравнить с элементом точно, а факта нет: `[(узел, имя, причина)]`
    (они не скрываются за строкой «проверено, фактов нет»; у подписей с фактом оценка названа в самом факте)."""
    form = layout.read(doc)
    names = _Names(form, structure)
    out = []
    for item, _text, pad, have, got in _caption_rows(form, doc):
        if all(m.exact for m in got) or pad + max(m.px for m in got) > have:
            continue
        name = names.of(item)
        out.append((names.node(name), name, next(m.why for m in got if not m.exact)))
    return out


def _bar_covered(form, names, out):
    """Видимый элемент лежит на командной панели (целиком в её рамке) и закрывает её нарисованные кнопки. Места кнопок —
    раскладка рендера (`render.bar_spans`): ширины приблизительные, поэтому факт говорит «оценка»; кнопки, ушедшие под «»», не считаются."""
    for holder in form.holders.values():
        bars = [i for i in holder.children if i.visible and i.type == "CommandBar"]
        for bar in bars:
            if render.bar_vertical(bar.node, bar.box[2] - bar.box[0], bar.box[3] - bar.box[1]):
                continue                              # значки вертикальной панели стоят столбиком: места по ширине оценить нечем
            spans, _overflow = render.bar_spans(bar.node, bar.box[2] - bar.box[0])
            shown = [(kind, text, start, width) for kind, text, _rep, start, width in spans if kind != "Separator"]
            if not shown:
                continue
            for item in holder.children:
                if item is bar or not item.visible or item.type == "CommandBar" or (item.page or 0) != (bar.page or 0):
                    continue
                a, b = bar.box, item.box
                if not (a[0] <= b[0] and a[1] <= b[1] and a[2] >= b[2] and a[3] >= b[3]):
                    continue
                left, right = b[0] - a[0], b[2] - a[0]
                hit = [text or "значок" for _k, text, start, width in shown if min(right, start + width) - max(left, start) > 0]
                if not hit:
                    continue
                name = names.of(item)
                out.append(Fact("bar_covered", names.node(name), name,
                                {"bar": names.of(bar), "x0": b[0], "x1": b[2], "buttons": hit, "estimate": True},
                                f"элемент «{names.short(item)}» ({b[0]}–{b[2]}) лежит на командной панели «{names.short(bar)}» поверх кнопок: "
                                + ", ".join(f"«{t}»" for t in hit[:LISTED]) + (f" и ещё {len(hit) - LISTED}" if len(hit) > LISTED else "")
                                + "; места кнопок — оценка (ширины кнопок платформа не проверялась)"))


def _focused(item):
    return item.visible and item.type not in NOT_FOCUSED


def _holder_node(holder, names):
    return "A0" if holder.item is None else names.node(names.of(holder.item))


def lcs_keep(tab, read):
    """Индексы `tab`, входящие в наибольшую общую подпоследовательность `tab` и `read` (последовательности имён без повторов).

    Элементы вне этой подпоследовательности — «не на месте»: минимальный набор, который надо переставить, чтобы обход шёл в порядке
    чтения. Один переставленный элемент даёт одно расхождение, а не сдвиг всех мест после него."""
    n, m = len(tab), len(read)
    table = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            table[i][j] = table[i + 1][j + 1] + 1 if tab[i] == read[j] else max(table[i + 1][j], table[i][j + 1])
    keep, i, j = set(), 0, 0
    while i < n and j < m:
        if tab[i] == read[j]:
            keep.add(i)
            i, j = i + 1, j + 1
        elif table[i + 1][j] >= table[i][j + 1]:
            i += 1
        else:
            j += 1
    return keep


def _sequence(names_list, names, limit=SEQUENCE_LIMIT):
    """Номера узлов подряд (повтор подряд сворачивается) для перечня имён, не длиннее `limit`; `(узлы, обрезано ли)`."""
    nodes = []
    for name in names_list:
        node = names.node(name) or "?"
        if not nodes or nodes[-1] != node:
            nodes.append(node)
    return nodes[:limit], len(nodes) > limit


def _auto_order(holder):
    block = holder.block
    value = block.get("auto_tab_order") if isinstance(block, dict) else None
    return value if isinstance(value, bool) else None


def _tab_order(form, names, structure, out):
    place = {name: at for at, name in enumerate(structure.reading_order())}
    for holder in form.holders.values():
        pages = collections.defaultdict(list)
        for item in holder.children:
            if _focused(item):
                pages[item.page or 0].append(item)
        for page in sorted(pages):
            items = pages[page]
            tab = [names.of(i) for i in sorted(items, key=lambda i: (i.coords.get(TAB_ORDER) or 0, i.index))]
            read = sorted(tab, key=lambda n: place.get(n, len(place)))
            keep = lcs_keep(tab, read)
            off = [name for at, name in enumerate(tab) if at not in keep]
            if not off:
                continue
            tab_nodes, tab_cut = _sequence(tab, names)
            read_nodes, read_cut = _sequence(read, names)
            auto = _auto_order(holder)
            where = "формы" if holder.item is None else f"панели «{names.short(holder.item)}»"
            on_page = f", страница {page}" if page else ""
            words = (f"порядок обхода {where}{on_page}: по обходу " + " → ".join(tab_nodes) + (" …" if tab_cut else "")
                     + "; по чтению " + " → ".join(read_nodes) + (" …" if read_cut else "")
                     + f"; не на месте {len(off)} из {len(tab)}: " + ", ".join(f"«{names.short(n)}»" for n in off[:MISMATCH_LIMIT])
                     + (f" и ещё {len(off) - MISMATCH_LIMIT}" if len(off) > MISMATCH_LIMIT else ""))
            if auto is not None:
                words += ("; у контейнера включён автопорядок обхода: порядок ведёт платформа по положению элементов (сверху вниз, слева направо) "
                          "и пересчитывает номера в файле при сохранении" if auto else "; автопорядок обхода у контейнера выключен: порядок задан номерами")
            out.append(Fact("tab_order", _holder_node(holder, names), None,
                            {"holder": holder.item.qualified() if holder.item is not None else None, "page": page,
                             "count": len(tab), "mismatched": len(off), "off": off, "tab_nodes": tab_nodes, "read_nodes": read_nodes,
                             "keep": len(keep), "auto": auto}, words))


def _enter_words(doc):
    mode = (doc.get("form") or {}).get("enter_key_behavior") if isinstance(doc, dict) else None
    return {"DefaultButton": "клавиша Enter нажимает кнопку по умолчанию",
            "ControlNavigation": "клавиша Enter переходит к следующему элементу"}.get(mode), mode


def _bar_buttons(form, names):
    """Кнопки командных панелей формы: `(число кнопок, [(панель, текст кнопки по умолчанию)])`; кнопка по умолчанию панели — та, номер которой записан в панели."""
    total, defaults = 0, []
    for item in form.items.values():
        if item.type != "CommandBar":
            continue
        entries = render.bars._file_entries(item.node)
        total += sum(1 for e in entries if e["kind"] != "sep")
        defaults += [(names.short(item), e["text"] or e["hint"]) for e in entries if e.get("default")]
    return total, defaults


def _default_buttons(form, doc, names, out):
    buttons = [i for h in form.holders.values() for i in h.children if i.type == "Button"]
    bar_total, bar_defaults = _bar_buttons(form, names)
    enter, mode = _enter_words(doc)
    tail = f"; {enter}" if enter else ""
    if not buttons and not bar_total:
        out.append(Fact("default_button", "A0", None, {"present": False, "buttons": 0, "bar_buttons": 0, "applicable": False, "enter": mode},
                        "кнопок на форме нет: кнопки по умолчанию быть не может" + tail))
        return
    flagged = [i for i in buttons
               if any(block.get(DEFAULT_BUTTON) is True for _k, block in ed_elements._like_places(i.node, DEFAULT_BUTTON, leaf=True))]
    if not flagged and not bar_defaults:
        out.append(Fact("default_button", "A0", None, {"present": False, "buttons": len(buttons), "bar_buttons": bar_total, "applicable": True, "enter": mode},
                        f"кнопки по умолчанию нет; кнопок-элементов на форме: {len(buttons)}; кнопок командных панелей: {bar_total}" + tail))
        return
    named = [f"«{names.short(i)}»" for i in flagged] + [f"«{text}» (командная панель «{bar}»)" for bar, text in bar_defaults]
    count = len(named)
    first = names.of(flagged[0]) if flagged else None
    out.append(Fact("default_button", names.node(first) if first else "A0", first,
                    {"present": True, "count": count, "buttons": len(buttons), "bar_buttons": bar_total, "applicable": True, "enter": mode},
                    f"кнопка по умолчанию: {', '.join(named)}" + ("" if count == 1 else f" ({count} кнопки)") + tail))


def _active_on_open(form, doc, names, out):
    for holder in form.holders.values():
        block = edit.layout_block(holder.node, need=False)
        control = block.get(DEFAULT_CONTROL) if isinstance(block, dict) else None
        control = control if isinstance(control, list) else []
        on_page = collections.defaultdict(list)
        for item in holder.children:
            if _focused(item):
                on_page[item.page or 0].append(item)
        for page in sorted(on_page):
            index = control[page] if page < len(control) else NO_REFERENCE
            item = form.items.get(index) if _int(index) and index != NO_REFERENCE else None
            if item is None and (holder.item is not None or page != 0):
                continue          # про панель и страницы, кроме нулевой страницы формы, говорится только когда элемент назначен
            where = "" if holder.item is None else f" панели «{names.short(holder.item)}»"
            on = f", страница {page}" if page else ""
            if item is None:
                out.append(Fact("active_on_open", "A0", None, {"present": False, "page": page, "holder": None},
                                f"элемент, активный при открытии формы, не назначен{on}"))
            else:
                name = names.of(item)
                out.append(Fact("active_on_open", names.node(name), name,
                                {"present": True, "page": page,
                                 "holder": holder.item.qualified() if holder.item is not None else None},
                                f"при открытии{where}{on} активен «{names.short(item)}»"))


WINDOW_SCAN = 600           # на сколько px шире (выше) формы окно проверяется, когда ищется размер, при котором элемент виден целиком


def _fits(form, item, width, height):
    """Элемент `item` лежит целиком в своём родителе при размере окна `width×height` по модели раскладки: `(по ширине, по высоте)`; `None` — раскладка не читает такой размер."""
    try:
        lay = layout.Layout(form, width, height)
    except edit.EditError:
        return None
    box, holder = lay.ints.get(item.index), form.holders.get(item.holder)
    if box is None or holder is None:
        return None
    grow = lay.growth.get(item.holder, (0, 0))
    return box[2] <= holder.size[0] + grow[0], box[3] <= holder.size[1] + grow[1]


def visible_at(form, item, axis):
    """Наименьший размер окна по оси (0 — ширина, 1 — высота), при котором по модели раскладки элемент лежит в родителе целиком, либо `None`: до `WINDOW_SCAN` px
    сверх размера формы такого нет. Поиск делением пополам: предполагается, что с ростом окна выход за край только уменьшается; значение — «около», а не точная граница."""
    base = (form.width, form.height)
    size = lambda extra: (base[0] + extra if axis == 0 else base[0], base[1] + extra if axis == 1 else base[1])
    top = _fits(form, item, *size(WINDOW_SCAN))
    if top is None or not top[axis]:
        return None
    low, high = 0, WINDOW_SCAN
    while high - low > 2:
        mid = (low + high) // 2
        got = _fits(form, item, *size(mid))
        if got is not None and got[axis]:
            high = mid
        else:
            low = mid
    return base[axis] + high


def _unclear(names, structure, form, out):
    for node in structure.walk():
        if node.role != "unclear" or not node.elements:
            continue
        name = node.elements[0]
        item = names.item_of.get(name)
        for part in (node.reason or "").split("; "):
            if part.startswith("перекрывается с "):
                text = part[len("перекрывается с "):]
                more = 0
                if " и ещё " in text:
                    text, tail = text.rsplit(" и ещё ", 1)
                    more = int(tail) if tail.isdigit() else 0
                numbers = {"with": text.split(", "), "more": more}
                out.append(Fact("overlap", node.id, name, numbers, f"элемент {names.text(part)}"))
            elif part:
                size = list(form.holders[item.holder].size) if item is not None else None
                zero = part.startswith("нулевой размер")
                numbers = {"box": list(node.box), "parent_size": size, "zero_size": zero}
                words = f"элемент {names.text(part)}"
                if item is not None and not zero and size is not None:
                    over = [axis for axis in (0, 1) if node.box[2 + axis] > size[axis]]
                    seen = {("width", "height")[axis]: visible_at(form, item, axis) for axis in over}
                    if seen:
                        numbers["visible_at"] = seen
                        said = [(f"по ширине — при ширине окна около {v} px (форма {form.width})" if k == "width" else f"по высоте — при высоте окна около {v} px (форма {form.height})")
                                if v is not None else (f"по {'ширине' if k == 'width' else 'высоте'} — ни при каком росте окна до +{WINDOW_SCAN} px"
                                                       f" (по модели раскладки)") for k, v in seen.items()]
                        words += "; целиком виден (по модели раскладки: край к краю родителя): " + "; ".join(said)
                out.append(Fact("out_of_bounds", node.id, name, numbers, words))


def _state(form, names, out):
    for item in form.items.values():
        name = names.of(item)
        if not item.visible:
            out.append(Fact("invisible", names.node(name), name, {"type": item.type}, f"«{names.short(item)}» ({item.type}) скрыт"))
        if not _enabled(item.node):
            out.append(Fact("disabled", names.node(name), name, {"type": item.type}, f"«{names.short(item)}» ({item.type}) недоступен"))


def _data(doc, form, meta, object_name, names, out):
    try:
        ctx = describe._Ctx(doc, meta, None, None, object_name)
    except edit.EditError:
        return
    obj = ctx.obj
    if obj is None and meta is not None and object_name:
        try:
            obj = meta.object(object_name)
        except Exception:  # noqa: BLE001 — нет такого объекта в выгрузке: обязательных реквизитов назвать не по чему
            obj = None
    shown = set()
    radios = br_content.radio_groups(form)
    for item in form.items.values():
        kind, name = ctx.binding(item)
        if kind == "object" and name:
            shown.add(name)
        if item.type in EXPECT_DATA and item.visible and kind == "none":
            if item.type == "RadioButton" and radios.get(item.index, (None, 1, 1))[1] > 1:
                continue          # данные и значение группы переключателей несёт первый переключатель; остальные — «без данных» не бывают
            element = names.of(item)
            out.append(Fact("data_missing", names.node(element), element, {"type": item.type},
                            f"«{names.short(item)}» ({item.type}) без привязки к данным"))
    if obj is None:
        return
    role = describe._role(ctx, None) if ctx.obj is not None and obj.kind in ("catalog",) else None
    try:
        attributes = obj.attributes_for(role) if role else obj.attributes
    except Exception:  # noqa: BLE001
        attributes = obj.attributes
    for attr in attributes:
        if attr.fill_checking == "ShowError" and attr.name not in shown:
            out.append(Fact("required_missing", None, None,
                            {"attribute": attr.name, "synonym": attr.synonym, "object": obj.full_name},
                            f"реквизит «{attr.name}» объекта «{obj.full_name}» требует заполнения, элемента на форме нет"))


LABELS_LISTED = 4        # элементов в слове факта о подписях называется поимённо


def _labels(doc, form, meta, object_name, names, structure, out):
    """Подписи: единообразие пар «надпись → поле» (двоеточие в конце надписи то есть, то нет; пробел перед двоеточием), надпись с данными без подписи рядом
    и поле ввода без подписи и без подсказки. Подпись — надпись пары «надпись → поле» (узел `P` вида «надпись и поле»); поле, не вошедшее в пару, — одиночный элемент `S`
    (в том числе на командной панели). Скрытые элементы не берутся."""
    try:
        ctx = describe._Ctx(doc, meta, None, None, object_name)
    except edit.EditError:
        ctx = None
    with_colon, without, spaced, lonely_labels, lonely_fields = [], [], [], [], []
    continued = {id(kid) for node in structure.walk() if node.role == structure_mod.ROW
                 and any(k.role == structure_mod.PAIR and k.kind == structure_mod.LABEL_FIELD for k in node.children)
                 for kid in node.children if kid.role == structure_mod.SINGLE}       # продолжение ряда с подписью (число в нескольких единицах): отдельной подписи не ждёт
    for node in structure.walk():
        members = [names.item_of[n] for n in node.elements if n in names.item_of]
        if node.role == structure_mod.PAIR and node.kind == structure_mod.LABEL_FIELD:
            label = next((i for i in members if i.type == "Label" and i.visible), None)
            if label is None:
                continue
            text = (render.caption_text(label.node, "Label") or "").strip()
            if not text:
                continue
            if re.search(r"\s:$", text):
                spaced.append((names.of(label), text))
            (with_colon if text.endswith(":") else without).append((names.of(label), text))
        elif node.role == structure_mod.SINGLE and len(members) == 1 and not node.hint:
            item = members[0]
            if not item.visible:
                continue
            if item.type == "Label" and ctx is not None and ctx.binding(item)[0] != "none":
                lonely_labels.append(names.of(item))
            elif item.type in ("TextBox", "ComboBox") and id(node) not in continued and not br_content.tool_tip(item):
                lonely_fields.append(names.of(item))

    def listed(rows):
        names_ = [r[0] if isinstance(r, tuple) else r for r in rows]
        return ", ".join(f"«{names.short(n)}»" for n in names_[:LABELS_LISTED]) + (f" и ещё {len(names_) - LABELS_LISTED}" if len(names_) > LABELS_LISTED else "")

    def put(rule, rows, numbers, words):
        first = rows[0][0] if isinstance(rows[0], tuple) else rows[0]
        out.append(Fact("labels", names.node(first), first, {"rule": rule, **numbers}, words))

    if with_colon and without:
        minority = without if len(without) <= len(with_colon) else with_colon
        put("colon_mix", minority, {"with_colon": len(with_colon), "without_colon": len(without), "minority": [m[0] for m in minority]},
            f"у пар «надпись → поле» двоеточие в конце надписи есть у {len(with_colon)}, нет у {len(without)}; "
            f"{'без двоеточия' if minority is without else 'с двоеточием'}: {listed(minority)}")
    if spaced:
        put("space_before_colon", spaced, {"labels": [m[0] for m in spaced], "texts": [m[1] for m in spaced[:LABELS_LISTED]]},
            f"пробел перед двоеточием в надписи пары: {', '.join('«' + t + '»' for _n, t in spaced[:LABELS_LISTED])}"
            + (f" и ещё {len(spaced) - LABELS_LISTED}" if len(spaced) > LABELS_LISTED else ""))
    if lonely_labels:
        put("data_label_alone", lonely_labels, {"labels": lonely_labels},
            f"надпись с данными без подписи рядом (не в паре «надпись → поле»): {listed(lonely_labels)}")
    if lonely_fields:
        put("field_unlabeled", lonely_fields, {"fields": lonely_fields},
            f"поле ввода без подписи и без подсказки (на форме, в том числе на командной панели): {listed(lonely_fields)}")


def _first_name(where, names):
    for part in (where or "").split(", "):
        if part in names.structure.by_element:
            return part
    return None


def _lint(doc, names, structure, out):
    kind = structure.kind
    if kind is not None and kind not in patterns.load()["kinds"] and kind != "regulated" and not kind.endswith(":?"):
        kind = "other:?"                      # вид без норм: ритм и привязки роли не проверяются, остальные замечания идут
    for remark in lint.lint(doc, "", kind).remarks:
        name = _first_name(remark.where, names)
        words = br_words.plain_design(remark.text) if remark.rule == "design" else None
        minority = []
        if words and remark.text.startswith(("раскол вида", "раскол позиции 16")):
            minority = [n for found in design.view_minority(doc).values() for n in found]
            if minority:
                words += "; меньшинство: " + ", ".join(f"«{names.short(n)}»" for n in minority[:MINORITY_LISTED]) + (
                    f" и ещё {len(minority) - MINORITY_LISTED}" if len(minority) > MINORITY_LISTED else "")
        out.append(Fact("lint", names.node(name) if name else None, name,
                        {"rule": remark.rule, "where": [p for p in remark.where.split(", ") if p],
                         **({"detail": remark.text} if words else {}), **({"minority": minority} if minority else {})},
                        words or names.text(remark.text)))


def _anchor_words(finding, names):
    """Находка привязок словами о том, что при этом происходит с формой в предприятии; без имён операций и записей привязок."""
    if finding.kind == "dead":
        _tag, _name, border = finding.key
        who = names.short(finding.culprits[0]) if finding.culprits else "?"
        return (f"у «{who}» {br_words.DEAD_BORDER.get(border, '?')} граница привязана так, что в предприятии не следует за окном: "
                "остаётся на месте при любом размере")
    return names.text(finding.words)


def _anchors(doc, names, out):
    pattern = []
    for finding in repair.diagnose(doc).findings:
        if finding.kind == "pattern":
            pattern.append(finding)
            continue
        name = next((c for c in finding.culprits if c in names.structure.by_element), None)
        out.append(Fact("anchors", names.node(name) if name else None, name,
                        {"finding": finding.kind, "culprits": list(finding.culprits), "axes": list(finding.axes),
                         "badness": finding.badness}, _anchor_words(finding, names)))
    if pattern:
        culprits = list(dict.fromkeys(c for f in pattern for c in f.culprits))
        orphans = sum(1 for f in pattern if not f.culprits)
        parts = []
        if culprits:
            parts.append(f"у {br_words.counted(len(culprits), 'элемента', 'элементов', 'элементов')} записи привязок повреждены: "
                         + ", ".join(f"«{names.short(c)}»" for c in culprits[:LISTED]) + (f" и ещё {len(culprits) - LISTED}" if len(culprits) > LISTED else ""))
        if orphans:
            parts.append(f"{br_words.counted(orphans, 'запись указывает', 'записи указывают', 'записей указывают')} на элемент, которого в форме нет")
        first = next((c for c in culprits if c in names.structure.by_element), None)
        out.append(Fact("anchors", names.node(first) if first else None, first,
                        {"finding": "pattern", "culprits": culprits, "axes": [], "badness": len(pattern), "orphans": orphans},
                        "; ".join(parts) + ": как такие элементы поведут себя при растяжении окна, не гарантировано"))


def _guides(doc, out):
    lines = guides.far_words(doc)
    if lines:
        numbers = {"far": [{"page": page, "edge": edge, "coord": coord, "margin": margin}
                           for page, edge, coord, margin in guides.far_guides(doc)]}
        out.append(Fact("guides", "A0", None, numbers, br_words.plain_guides(numbers)))


def _wide_pages(form, names, out):
    """Страница панели шире её видимой части (`layout.wide_pages`) и панель, которая при сужении окна прокручивается (`layout.scroll_panels`)."""
    for owner, page, guide, area, over, by_guide, total in layout.wide_pages(form):
        numbers = {"wide_page": {"panel": owner.name, "page": page, "guide": list(guide), "area": list(area),
                                 "over": [{"axis": axis, "px": px} for axis, px in over], "by_guide": by_guide, "total": total}}
        out.append(Fact("guides", names.node(owner.name), owner.name, numbers, names.text(br_words.plain_wide_page(numbers["wide_page"]))))
    for owner, page, guide, area, over, by_guide, total in layout.narrow_pages(form):
        numbers = {"narrow_page": {"panel": owner.name, "page": page, "guide": list(guide), "area": list(area),
                                   "under": [{"axis": axis, "px": px} for axis, px in over], "by_guide": by_guide, "total": total}}
        out.append(Fact("guides", names.node(owner.name), owner.name, numbers, names.text(br_words.plain_narrow_page(numbers["narrow_page"]))))
    off = {}
    for item, _stored, _found in layout.box_mismatches(form):
        if item.from_area:
            off.setdefault(item.holder, []).append(item.name)
    for key, listed in off.items():
        owner = form.holders[key].item
        numbers = {"area_off": {"panel": owner.name, "items": listed[:LISTED], "count": len(listed)}}
        out.append(Fact("guides", names.node(owner.name), owner.name, numbers, names.text(br_words.plain_area_off(numbers["area_off"]))))
    for owner, axis, at, item, least in layout.scroll_panels(form):
        numbers = {"scroll_panel": {"panel": owner.name, "axis": axis, "window": at, "item": item.name, "min": least}}
        out.append(Fact("guides", names.node(owner.name), owner.name, numbers, names.text(br_words.plain_scroll_panel(numbers["scroll_panel"]))))


def facts(doc, structure, meta=None, object_name=None):
    """Факты формы `doc` по её структуре: `[Fact]` в порядке видов (`KINDS`), внутри вида — в порядке чтения узлов.

    `meta` — выгрузка конфигурации (`metadata.Config`) либо `None`; `object_name` — полное имя объекта формы
    (`Справочник.Имя`), когда по метаданным его не найти. Испорченный документ — `edit.EditError` словами."""
    form = layout.read(doc)
    names = _Names(form, structure)
    out = []
    _field_widths(form, doc, names, out)
    _caption_cuts(form, doc, names, out)
    _column_cuts(form, doc, names, out)
    _bar_covered(form, names, out)
    _labels(doc, form, meta, object_name, names, structure, out)
    _tab_order(form, names, structure, out)
    _default_buttons(form, doc, names, out)
    _active_on_open(form, doc, names, out)
    _unclear(names, structure, form, out)
    _state(form, names, out)
    _data(doc, form, meta, object_name, names, out)
    _lint(doc, names, structure, out)
    _anchors(doc, names, out)
    _guides(doc, out)
    _wide_pages(form, names, out)
    place = {node.id: at for at, node in enumerate(structure.walk())}
    order = {kind: at for at, kind in enumerate(KINDS)}
    return sorted(out, key=lambda f: (order[f.kind], place.get(f.node, len(place)), f.element or ""))
