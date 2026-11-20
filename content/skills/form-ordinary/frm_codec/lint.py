"""Линтер ритма формы: замечания, а не отказы. Подробно — `docs/lint.md`.

Форма проверяется по нормам её вида (`patterns.json`) и по раскладке. Замечание ничего не запрещает и не правит, а называет место и число,
с которым форма расходится. Код возврата команды — 0; отказ (1) — только если форму нельзя прочесть или документ испорчен.

Роды замечаний (`Remark.rule`):

1. Ритм (`rhythm:<показатель>`): отступы, шаг и размеры вне диапазона большинства по норме вида; `rhythm:label_text_gap` — видимый зазор от конца
   текста надписи до поля меньше нижней границы нормы вида (`patterns.gap_floor`, `textgap`), только по проверенному шрифту.
2. Привязки не по норме роли (`anchors:<показатель>`): поле, таблица, нижняя и верхняя панели, выравнивание левых полей строк. Если таблиц
   несколько, проверяется вся форма: роль выполнена, когда какая-нибудь таблица растягивается вправо и какая-нибудь вниз.
3. Наезд (`overlap`): два видимых элемента одной панели и страницы пересекаются на глубину не меньше `OVERLAP_MIN`. Не считаются
   охват, картинка-подложка под надписью или картинкой и пара командных панелей.
4. Выход за форму (`outside`): видимый элемент лежит за клиентской областью.
5. Поле уже минимума (`narrow`): ширина поля ввода меньше `layout.min_size`. Высота на минимум не проверяется.
6. Подпись шире элемента (`caption`): текст надписи, флажка или кнопки по шрифту элемента (`textwidth.element_font`) плюс отступ
   подписи шире элемента. Если шрифт не проверялся, замечания нет — в сведениях остаётся строка.
7. Смесь версий и вида (`design`): то, что `design.in_form` называет смесью или расколом; текст обрезается, дальше ссылка
   «подробно: frm_json.py design». С `siblings` добавляется `design.compare`.
8. Выравнивание расходится (`align`): в столбце из четырёх и более полей (надписей) с общим левым (правым) краем при проектном размере один
   элемент при ширине окна в полтора раза больше отходит от остальных больше чем на `ALIGN_TOL` px, а остальные не меньше трёх держатся вместе. Проверяются
   элементы формы и её страниц (не панелей); окно дальше предела раскладки формы модель не растягивает.
9. Отступ от области страницы (`page_inset`): на странице панели закладок «Сверху», «Снизу» (в том числе с прокруткой) и «Слева (вертикально)»
   ближайший к краю области видимый элемент (кроме командных панелей) ближе `layout.PAGE_INSET` (6 px, как у Конфигуратора), но не вплотную.
   Вплотную (0) стоят крупные элементы страницы (таблица, табличный документ, рамка…) — это приём, сведения; прочие — замечание. У панели
   с рамкой проверены левый и верхний отступ: край области справа и снизу у такой панели не снят.
10. Тип табличного поля (`table_type`): тип значения табличного поля не равен типу данных, к которым оно привязано, — реквизита формы (таблица
   формы списка), нулевой у привязанного поля, а с выгрузкой (`config`) — не `TypeId` табличной части. Правило одно с предупреждением `validate`
   (`tabletype.findings`): с чужим типом платформа загружает форму, но колонки таблицы выбрасывает.

Диапазон большинства. Норма вида хранит у каждого показателя два перечня (первые 8 строк): значения по конфигурациям (норма — первое) и
по формам с долями. Диапазон — от меньшего до большего из значений, дающих вместе не меньше `MAJORITY` форм, считая от самого
частого, плюс значение нормы и значения, которые оказались самыми частыми не меньше чем у `VOTES_INSIDE` конфигураций. Значение вне диапазона —
замечание. Показатель не проверяется (`verdict`), если данные по нему есть меньше чем у трёх конфигураций (`Result.thin`), первые 8
значений дают меньше `MAJORITY` (`Result.unjudged`) или диапазон показателя ритма шире `WIDE_RANGE` (`Result.wide`): линтер молчит
вместо догадки и называет такие показатели в сведениях. У вида с менее чем тремя конфигурациями, у регламентированного и у вида вне
перечня норм нормы нет: ритм и роли не проверяются, остальные рода работают. Явный `--kind` вне перечня норм (кроме `regulated` и `other:?`) — отказ словами.

Замечание ритма и роли несёт число нормы и доли: диапазон большинства, норму вида, число конфигураций за норму и долю нормы среди форм.

"""
import collections

from . import census, design, layout, patterns, tabletype, textgap, textwidth
from .edit.base import EditError

MAJORITY = 0.9  # диапазон большинства: значения, дающие вместе не меньше этой доли наблюдений форм
DECOR = ("Label", "PictureBox")  # картинка — подложка только под надписью и другой картинкой; с полем, панелью, флажком — наезд
WIDE_RANGE = 40  # показатель ритма с диапазоном шире стольких px не проверяется: значения не собираются в одну группу
OVERLAP_MIN = 3  # наезд — пересечение глубиной не меньше стольких px по обеим осям
VOTES_INSIDE = 2  # значение, которое самым частым оказалось хотя бы у двух конфигураций, лежит внутри диапазона; значение одной конфигурации — нет
LIST = 3  # сколько мест замечания называется поимённо, остальные — числом

# Показатели ритма: число — отступ, шаг или размер. Слова — название показателя в замечании.
RHYTHM = {
    "pair_pitch": "шаг строк пар (верх строки → верх следующей)",
    "label_left": "левый отступ надписи",
    "field_right_margin": "правый отступ поля",
    "label_field_gap": "зазор «надпись → поле»",
    "label_height": "высота надписи",
    "field_height": "высота поля",
    "top_bar_x": "лево верхней командной панели",
    "top_bar_y": "верх верхней командной панели",
    "top_bar_height": "высота верхней командной панели",
    "bottom_bar_x": "лево нижней командной панели",
    "bottom_bar_height": "высота нижней командной панели",
}
# Меры ролей: 0 или 1. Слова — название значения в замечании.
ANCHORS = {
    "field_right_to_form": ("поле", {1: "правый край привязан к форме", 0: "правый край не привязан к форме"}),
    "table_right_bottom_to_form": ("таблица", {1: "привязана к правому и нижнему краю формы",
                                               0: "не привязана к правому и нижнему краю формы"}),
    "bottom_bar_to_form": ("нижняя панель", {1: "привязана к низу формы", 0: "не привязана к низу формы"}),
    "bottom_bar_full_width": ("нижняя панель", {1: "на всю ширину формы", 0: "не на всю ширину формы"}),
    "top_bar_full_width": ("верхняя панель", {1: "на всю ширину формы", 0: "не на всю ширину формы"}),
    "field_x_aligned": ("строки пар", {1: "левые поля первых пар строк в одном столбце", 0: "левые поля первых пар строк в разных столбцах"}),
    "field_x_columns": ("колонка пар", {1: "левые поля колонки в одном столбце", 0: "левые поля колонки в разных столбцах"}),
}
GROUPS = {"rhythm": "ритм", "anchors": "привязки роли", "overlap": "наезд", "outside": "выход за форму",
          "narrow": "поле уже минимума", "caption": "подпись шире элемента", "design": "смесь версий и вида",
          "align": "выравнивание расходится при растяжении", "page_inset": "отступ от области страницы",
          "table_type": "тип табличного поля"}
ALIGN_TOL = 2  # края столбца совпадают (и выравнивание держится), если различаются не больше чем на столько px
ALIGN_SHIFT = 5  # сдвиг от остальных не больше стольких px замечанием не считается
ALIGN_MIN = 4  # столбец из стольких элементов и более: один выбивается, остальные (не меньше трёх) держатся вместе
ALIGN_GROW = 1.5  # во сколько раз ширина окна больше проектной при проверке выравнивания
ALIGN_TYPES = ("TextBox", "Label")  # поля ввода и надписи: у них столбцы с общим краем — норма раскладки
# Виды закладок, у которых проверяется отступ от области страницы: норма 6 есть у большинства страниц корпуса; у «Не отображать» и «Слева (горизонтально)»
# вложенные заполняют панель вплотную (0 — норма), у прочих видов область не снята.
INSET_KINDS = ("Top", "TopScrolling", "Bottom", "BottomScrolling", "LeftVertical")
# Элемент, который занимает страницу целиком: вплотную к области он стоит как приём, а не как прижатый текст.
FILL_TYPES = frozenset({"TableBox", "SpreadsheetDocumentField", "TextDocumentField", "GroupBox", "Panel", "ListBox", "Chart", "GanttChart",
                        "PivotChart", "Splitter", "Dendrogram", "HTMLDocumentField", "PDFDocumentField", "GraphicalSchema", "GeographicalSchema"})
INSET_SIDES = (("слева", 0), ("сверху", 1), ("справа", 2), ("снизу", 3))
FRAMED_SIDES = (0, 1)  # у панели с рамкой край области справа и снизу не снят: проверяются левый и верхний отступ
DESIGN_CUT = 240  # слова `design` в замечании обрезаются: это ссылка, а не пересказ


class Remark(collections.namedtuple("Remark", "rule where text")):
    """Замечание: `rule` — `<род>[:<показатель>]`, `where` — места (имена элементов через запятую или пусто), `text` — слова."""
    __slots__ = ()

    @property
    def group(self):
        return self.rule.split(":", 1)[0]


class Result:
    """`Result`: `kind` — вид (или `None`), `remarks`, `info` — сведения словами, `judged`, `unjudged`, `thin` (`[(показатель, число конфигураций)]`), `wide` — показатели по результату проверки."""

    def __init__(self, kind):
        self.kind = kind
        self.remarks = []
        self.info = []
        self.judged = []
        self.unjudged = []
        self.thin = []
        self.wide = []


def _pct(x):
    value = round(x * 100, 1)
    return (f"{value:.0f}" if value == int(value) else f"{value:.1f}".replace(".", ",")) + " %"


def majority(row, share=MAJORITY):
    """Диапазон большинства показателя: `(меньшее, большее, доля форм)` либо `None`, если первые строки перечня форм вместе не дают `share`."""
    chosen, covered = [], 0.0
    for value, part, *_ in row["by_form"]:
        chosen.append(value)
        covered += part
        if covered >= share - 1e-9:
            break
    else:
        return None
    norm = row["by_config"][0][0]
    values = chosen + [norm] + [v for v, _share, votes in row["by_config"] if votes >= VOTES_INSIDE]
    return min(values), max(values), round(covered, 4)


def verdict(key, row, share=MAJORITY):
    """Проверяется ли показатель по строке нормы: `("judged", (меньшее, большее, доля))`, `("thin", None)`, `("nomajority", None)` либо
    `("wide", (…))`. Одно место для линтера и замеров.
    """
    if row["configs"] < patterns.THIN_CONFIGS:
        return "thin", None
    span = majority(row, share)
    if span is None:
        return "nomajority", None
    if key in RHYTHM and span[1] - span[0] > WIDE_RANGE:
        return "wide", span
    return "judged", span


def _norm_words(row, kind, shared=False):
    """«норма N: самое частое значение у k из n конфигураций и у Y % форм»: каждое замечание несёт число нормы и обе доли. `shared` — строка общая по корпусу: так и названа."""
    value, part, votes = row["by_config"][0]
    seen = next((p for v, p, *_ in row["by_form"] if v == value), None)
    forms = f" и у {_pct(seen)} форм" if seen is not None else ""
    return f"{'общая норма по корпусу' if shared else 'норма вида ' + kind} — {value}: самое частое значение у {votes} из {row['configs']} конфигураций{forms}"


def _list(found):
    """`значение у «имя»` через запятую: первые `LIST`, остальные числом."""
    shown = ", ".join(f"{v} у «{n}»" if n else f"{v}" for v, n in found[:LIST])
    return shown + (f" … и ещё {len(found) - LIST}" if len(found) > LIST else "")


def _names(found):
    return ", ".join(sorted({n for _v, n in found if n}))


def _stack(rec):
    """Таблицы верхнего уровня, если их больше одной, — `(имена, значение роли по форме целиком)`, иначе `None`. Роль «таблица забирает
    рост окна» проверяется по форме целиком: достаточно, чтобы какая-нибудь таблица растягивалась вправо и какая-нибудь вниз.
    """
    tables = [t for t in rec["top"] if t["type"] == "TableBox"]
    if len(tables) < 2:
        return None
    value = int(any(t["right_to_form"] for t in tables) and any(t["bottom_to_form"] for t in tables))
    return ", ".join(t["name"] for t in tables), value


def _norm_remarks(result, rec, block, kind, share):
    who, shift = {}, {}
    values = patterns._measures(rec, who, shift)
    stack = _stack(rec)
    for key in list(RHYTHM) + list(ANCHORS):
        row = block.get(key)
        seen = values.get(key)
        if not row or not seen:
            continue
        status, span = verdict(key, row, share)
        if status == "thin":
            result.thin.append((key, row["configs"]))  # данные меньше чем у трёх конфигураций нормой не служат
            continue
        if status == "nomajority":
            result.unjudged.append(key)
            continue
        lo, hi, covered = span
        if status == "wide":
            result.wide.append((key, lo, hi))
            continue
        result.judged.append(key)
        names = who[key]
        if key == "table_right_bottom_to_form" and stack is not None:
            seen, names = [stack[1]], [stack[0]]
        grown = shift.get(key) or [0] * len(seen)        # крупный шрифт: верхняя граница диапазона высот выше на разницу высот шрифта (`patterns.font_excess`); нижняя прежняя — у корпуса крупные шрифты в низких надписях часты
        off = [(v, n) for v, n, d in zip(seen, names, grown) if v < lo or v - d > hi]
        if not off:
            continue
        where = _names(off)
        moved = sorted({(n, d) for v, n, d in zip(seen, names, grown) if d and (v, n) in off and n})
        range_words = (f"диапазон большинства {lo}–{hi}" if lo != hi else f"большинство — {lo}")
        if key in RHYTHM:
            text = (f"{RHYTHM[key]}: {_list(off)} — вне диапазона: {range_words} ({_pct(covered)} наблюдений форм вида "
                    f"{kind}); {_norm_words(row, kind)}")
            if moved:
                text += ("; шрифт выше шрифта формы, верхняя граница диапазона выше на разницу высот шрифта: "
                         + ", ".join(f"«{n}» на {d} px" for n, d in moved[:LIST]) + (f" … и ещё {len(moved) - LIST}" if len(moved) > LIST else ""))
            result.remarks.append(Remark(f"rhythm:{key}", where, text))
        else:
            role, words = ANCHORS[key]
            said = ", ".join(f"«{n}»: {words[v]}" if n else words[v] for v, n in off[:LIST])
            said += f" … и ещё {len(off) - LIST}" if len(off) > LIST else ""
            wanted = words[lo] if lo == hi else "значения большинства — оба"
            text = (f"{role} не по норме роли: {said}; у вида {kind} {wanted} в {_pct(covered)} наблюдений форм; "
                    f"{_norm_words(row, kind)}")
            result.remarks.append(Remark(f"anchors:{key}", where, text))


def _gap_remarks(result, rec, table, kind):
    """Текст надписи вплотную к полю: видимый зазор от конца текста до поля (`textgap`) меньше нижней границы нормы (`patterns.gap_floor`).
    Только пары, у которых шрифт надписи проверен: по оценочной ширине замечание не выдаётся.
    """
    who = {}
    seen = patterns._measures(rec, who).get("label_text_gap")
    if not seen:
        return
    row, why = patterns.gap_row(table, kind)
    if row is None:
        result.info.append(f"зазор «текст надписи → поле» не проверяется: {why}")
        return
    floor, share, total = row["floor"]
    result.judged.append("label_text_gap")
    off = [(v, n) for v, n in zip(seen, who["label_text_gap"]) if v < floor]
    if off:
        scope = f"общая по корпусу: {why}" if why else f"вид {kind}"
        result.remarks.append(Remark(
            "rhythm:label_text_gap", _names(off),
            f"текст надписи вплотную к полю: видимый зазор «конец текста надписи → поле» {_list(off)} — меньше нижней границы {floor} "
            f"({scope}; ниже неё {_pct(share)} наблюдений форм из {total} пар); {_norm_words(row, kind, bool(why))}"))


def _multiline_info(result, rec, table):
    """Многострочные поля ввода формы: сведения, не замечания. Высота такого поля не входит в `field_height` и шаг строк (`patterns._measures`), а своей нормы у неё
    нет: высота определяется числом строк текста, и большинства среди форм корпуса нет (общая строка `multiline_lines` таблицы норм — доля полей, показывающих одну строку,
    и самая частая высота по конфигурациям)."""
    found = [t for t in rec["top"] if t["type"] == "TextBox" and t.get("multi_line")]
    if not found:
        return
    listed = ", ".join(f"«{t['name']}» — {patterns.text_lines(t['box'][3] - t['box'][1], t.get('ppem', patterns.textwidth.DEFAULT_PPEM))} стр. "
                       f"({t['box'][3] - t['box'][1]} px)" for t in found[:LIST]) + (f" … и ещё {len(found) - LIST}" if len(found) > LIST else "")
    shared = table.get(patterns.SHARED) or {}
    lines, height = shared.get("multiline_lines"), shared.get("multiline_field_height")
    stat = ""
    if lines and "below_min" in lines and height and height["by_config"]:
        _min, share, _below, total = lines["below_min"]
        value, _part, votes = height["by_config"][0]
        stat = (f": в корпусе {_pct(share)} из {total} многострочных полей показывают меньше {_min} строк, самая частая высота поля не меньше {_min} строк — "
                f"{value} px (у {votes} из {height['configs']} конфигураций)")
    result.info.append(f"многострочные поля ввода: {listed} — высота в норму ритма «высота поля» не входит, своей нормы у неё нет{stat}")


def _file_box(item):
    return item.stored if item.stored is not None else item.box


def _inside(a, b):
    """Края `a` лежат внутри краёв `b` (касание края — внутри)."""
    return a[0] >= b[0] and a[1] >= b[1] and a[2] <= b[2] and a[3] <= b[3]


def _depth(a, b):
    """Глубина пересечения: меньшая из двух сторон общего прямоугольника (0 и меньше — не пересекаются)."""
    return min(min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1]))


def _decor(a, b):
    """Картинка-подложка: `PictureBox` с надписью или другой картинкой (`DECOR`); с любым другим типом — обычная пара."""
    if "PictureBox" not in (a.type, b.type):
        return False
    other = b if a.type == "PictureBox" else a
    return other.type in DECOR


def _geometry(result, form):
    groups = collections.defaultdict(list)
    for holder in form.holders.values():
        for item in holder.children:
            if item.visible:
                groups[(item.holder, item.page)].append(item)
    for there in groups.values():
        for at, a in enumerate(there):
            for b in there[at + 1:]:
                ab, bb = _file_box(a), _file_box(b)
                if _decor(a, b) or a.type == b.type == "CommandBar":
                    continue
                if _inside(ab, bb) or _inside(bb, ab):
                    continue  # охват — не наезд: рамка, панель, полоса команд держат своё
                if _depth(ab, bb) >= OVERLAP_MIN:
                    result.remarks.append(Remark(
                        "overlap", f"{a.qualified()}, {b.qualified()}",
                        f"наезд: «{a.qualified()}» ({a.type}, {tuple(ab)}) и «{b.qualified()}» ({b.type}, {tuple(bb)}) "
                        f"пересекаются на одном родителе и одной странице"))
    width, height = form.width, form.height
    for item in form.holders[0].children:
        box = _file_box(item)
        if item.visible and (box[0] < 0 or box[1] < 0 or box[2] > width or box[3] > height):
            result.remarks.append(Remark(
                "outside", item.qualified(),
                f"выход за форму: «{item.qualified()}» ({item.type}, {tuple(box)}) за клиентской областью {width}×{height}"))
    for holder in form.holders.values():
        for item in holder.children:
            if item.type == "TextBox" and item.visible:
                box, least = _file_box(item), layout.min_size(item)[0]
                if box[2] - box[0] < least:
                    result.remarks.append(Remark(
                        "narrow", item.qualified(),
                        f"поле «{item.qualified()}» шириной {box[2] - box[0]} уже минимума поля ввода платформы ({least})"))


LABEL_WRAP_LINES = textgap.LABEL_WRAP_LINES  # надпись высотой от стольких строк переносит текст по словам, и замечания по ширине у неё нет
LINE_EXTRA = textgap.LINE_EXTRA  # высота строки подписи = ppem шрифта + столько (11 px → 15; не проверялось): порог «заведомо одна строка» — один на линтер и `textgap`
CAPTION_TYPES = ("Label", "CheckBox", "Button")  # у этих типов отступ подписи известен (`render.CHECK_CAPTION_PAD`, `BUTTON_CAPTION_PAD`); у переключателя нет


def _captions(result, doc, form):
    """Подпись шире элемента: текст по действующему шрифту (`textwidth.element_font`) плюс отступ подписи (надпись 0, флажок 16, кнопка
    4) шире элемента — в предприятии подпись усекается «…». Если шрифт не проверялся, замечания нет — строка в `info`; у
    переключателя так же. Невидимые элементы не проверяются.
    """
    from . import render
    blind, radios = [], []
    for holder in form.holders.values():
        for item in holder.children:
            if not item.visible or item.type not in CAPTION_TYPES + ("RadioButton",):
                continue
            text = render.caption_text(item.node, item.type)
            if not text:
                continue
            if item.type == "RadioButton":
                radios.append(item.qualified())
                continue
            pad = {"Label": 0, "CheckBox": render.CHECK_CAPTION_PAD, "Button": render.BUTTON_CAPTION_PAD}[item.type]
            font = textwidth.element_font(item.node, doc)
            lines = text.splitlines() or [text]
            got = [textwidth.measure(line, font) for line in lines]
            need = pad + max(m.px for m in got)
            box = _file_box(item)
            have = box[2] - box[0]
            if item.type == "Label" and textgap.wraps(box, font):
                continue  # надпись высотой в несколько строк переносит текст по словам: узкая коробка не означает усечения
            if not all(m.exact for m in got):
                blind.append((item.qualified(), next(m.why for m in got if not m.exact)))
            elif need > have:
                from . import place
                result.remarks.append(Remark(
                    "caption", item.qualified(),
                    f"подпись шире элемента: «{item.qualified()}» ({item.type}) — «{text}» шрифтом {place.font_words(font)}: нужно {need} px "
                    f"(текст {need - pad}" + (f" + отступ подписи {pad}" if pad else "") + f"), есть {have}; в предприятии подпись усечена"))
    if blind:
        result.info.append("подпись шире элемента не проверяется у " + "; ".join(f"«{name}» (шрифт не проверялся: {why})" for name, why in blind[:LIST])
                           + (f" и ещё {len(blind) - LIST}" if len(blind) > LIST else "") + ": по оценочной ширине подписи замечание не выдаётся")
    if radios:
        result.info.append("подпись шире элемента не проверяется у переключателей (отступ подписи не проверялся): " + ", ".join(f"«{n}»" for n in radios[:LIST])
                           + (f" и ещё {len(radios) - LIST}" if len(radios) > LIST else ""))


def align_findings(form):
    """Расхождения выравнивания при растяжении: `[Drift]`. У элементов формы и её страниц одного типа (`ALIGN_TYPES`) общий левый или правый
    край в проекте; при ширине окна `ALIGN_GROW` проектной (раскладка — `layout.Layout`; дальше предела раскладки формы окно модель не растягивает)
    один из них отходит от остальных, которые держатся на одной вертикали. Находка — только когда выбивается ровно один элемент, а остальных
    не меньше трёх: столбец, который делится пополам (часть остаётся на месте, часть растягивается), чаще задуман, и по такому делению нельзя сказать,
    какая половина неправа. Функцию зовут `lint` (замечание `align`) и режим исправления привязок (`repair`).
    """
    try:
        lay = layout.Layout(form, round(form.width * ALIGN_GROW), form.height, hide=False, scroll=False)
    except (EditError, ValueError, KeyError, TypeError, IndexError, AttributeError, layout.Cycle):
        return []
    width = lay.effective()[0]
    found = []
    groups = collections.defaultdict(list)
    for item in form.holders[0].children:
        if item.visible and item.type in ALIGN_TYPES and item.index in lay.ints and not _subfield(form, item):
            groups[(item.page, item.type)].append(item)
    for (_page, kind), items in sorted(groups.items(), key=lambda kv: (repr(kv[0][0]), kv[0][1])):
        for edge, word in ((0, "левые"), (2, "правые")):
            cluster = []
            for item in sorted(items, key=lambda i: i.box[edge]) + [None]:
                if cluster and (item is None or item.box[edge] - cluster[0].box[edge] > ALIGN_TOL):
                    drift = _outlier(lay, cluster, edge, word, kind, width)
                    if drift is not None:
                        found.append(drift)
                    cluster = []
                if item is not None:
                    cluster.append(item)
    return found


class Drift(collections.namedtuple("Drift", "odd edge word kind count x width shift")):
    """Один отошедший элемент: `odd` — он, `edge` — 0 (левый край) или 2 (правый), `count` — элементов в столбце, `x` — общий край в проекте,
    `width` — ширина окна проверки, `shift` — на сколько px он отходит от остальных."""
    __slots__ = ()

    @property
    def text(self):
        return (f"выравнивание расходится при растяжении: {self.word} края {self.count} элементов ({self.kind}) совпадают в проекте "
                f"(x≈{self.x}); при ширине окна {self.width} «{self.odd.label()}» отходит от остальных на {self.shift} px")


def _drift(result, form):
    for drift in align_findings(form):
        result.remarks.append(Remark("align", drift.odd.label(), drift.text))


def _subfield(form, item):
    """Левее элемента на той же строке стоит элемент того же типа (формы и той же страницы): элемент — подполе строки, а не ячейка столбца."""
    return any(o is not item and o.visible and o.page == item.page and o.type == item.type and o.box[2] <= item.box[0] + ALIGN_TOL
               and min(o.box[3], item.box[3]) - max(o.box[1], item.box[1]) > 0 for o in form.holders[0].children)


def _outlier(lay, cluster, edge, word, kind, width):
    """`Drift`, если в столбце `cluster` при раскладке `lay` один элемент отошёл от остальных, а остальные держатся вместе; иначе `None`."""
    if len(cluster) < ALIGN_MIN:
        return None
    places = sorted(lay.ints[i.index][edge] for i in cluster)
    groups = []
    for value in places:
        if groups and value - groups[-1][0] <= ALIGN_TOL:
            groups[-1][1] += 1
        else:
            groups.append([value, 1])
    if len(groups) != 2 or min(g[1] for g in groups) != 1:  # два места и один отошедший: у остальных не меньше `ALIGN_MIN − 1` — столбец не меньше `ALIGN_MIN`
        return None
    main = max(groups, key=lambda g: g[1])[0]
    odd = next(i for i in cluster if abs(lay.ints[i.index][edge] - main) > ALIGN_TOL)
    shift = abs(lay.ints[odd.index][edge] - main)
    if shift <= ALIGN_SHIFT:
        return None
    return Drift(odd, edge, word, kind, len(cluster), cluster[0].box[edge], width, shift)


CLOSE_PX = 2  # отступ 0…2 px — «вплотную к рамке страницы», 3…5 — «ближе нормы»; род один


def _page_key(page):
    return (not isinstance(page, int), page if isinstance(page, int) else repr(page))


def _px(value):
    """Число в слова: целые пиксели, как печатают прочие замечания (модель отдаёт дробный край)."""
    return int(round(value))


def _span(item, which, form):
    """`(края, откуда)`: края элемента для отступа (`which` 0 — файл, 1 — место в предприятии: `item.box`, если элемент стоит по правилам от области) и
    для каждой из четырёх сторон элемент-источник края (`None` — сам элемент). Вложенная панель «Не отображать» без рамки невидима: берутся края
    содержимого её видимой (первой) страницы, обрезанные по самой панели."""
    box = _file_box(item) if which == 0 or not item.from_area else item.box
    if item.type == "Panel" and layout._panel_tabs(item) == "DontUse" and layout._panel_unframed(item):
        inner = form.holders.get(item.index)
        kids = [c for c in (inner.children if inner else ()) if c.visible and c.type != "CommandBar" and not layout.hidden_page(c)]
        if kids:
            boxes = [_file_box(c) if which == 0 or not c.from_area else c.box for c in kids]
            x0, y0 = box[0] + min(b[0] for b in boxes), box[1] + min(b[1] for b in boxes)
            x1, y1 = box[0] + max(b[2] for b in boxes), box[1] + max(b[3] for b in boxes)
            via = (min(zip(boxes, kids), key=lambda bk: bk[0][0])[1], min(zip(boxes, kids), key=lambda bk: bk[0][1])[1],
                   max(zip(boxes, kids), key=lambda bk: bk[0][2])[1], max(zip(boxes, kids), key=lambda bk: bk[0][3])[1])
            return (max(x0, box[0]), max(y0, box[1]), min(x1, box[2]), min(y1, box[3])), via
    return box, (None,) * 4


def _named(item, side, via):
    """`«имя» (тип)`; у вложенной панели — через какой элемент на какой её странице отступ."""
    text = f"«{item.label()}» ({item.type})"
    inner = via[side] if via else None
    return text[:-1] + f", через «{inner.label()}» на её странице {inner.page or 0})" if inner is not None else text


def _least(item, box, axis):
    """Наименьший размер элемента по оси: минимум типа (`layout.min_size`); `None` — у типа минимум не проверен, тесной области и сжатия по нему не утверждается."""
    return layout.min_size(item)[axis] or None


def _fix_words(side, cut, edge, near):
    """Чем исправить. Область теснее наименьшего размера элемента плюс два отступа — размером панели (`move_element` панели); иначе сдвигом: левая и
    верхняя стороны — с сохранением противоположного края, элемент постоянного размера сдвигают, а не сжимают. `near` — `[(элемент, его края)]`."""
    axis = 0 if side in (0, 2) else 1
    if any(_least(item, box, axis) is not None and _least(item, box, axis) + 2 * cut > edge[axis] for item, box in near):
        return ("область страницы теснее наименьшего размера элемента плюс два отступа: исправляется размером панели "
                "(`move_element` панели с новым `box`), а не сдвигом элемента")
    shrinks = any(_least(item, box, axis) is not None and _least(item, box, axis) < box[axis + 2] - box[axis] for item, box in near)
    size = ("ширину", "высоту")[axis]
    keep = ("правый", "нижний")[axis]
    # сдвиг до нормы уронит противоположный отступ ниже нормы (элемент растянут через страницу): сжатие нужно, проверен ли минимум типа или нет
    squeezed = any(_px(box[axis] if side in (0, 1) else edge[axis] - box[axis + 2]) + _px(edge[axis] - box[axis + 2] if side in (0, 1) else box[axis]) < 2 * cut
                   for item, box in near)
    if side in (0, 1):
        how = f"сдвиньте и сохраните {keep} край (уменьшите {size})" if shrinks or squeezed else "сдвиньте"
    else:
        how = f"уменьшите {size}" if squeezed else (f"сдвиньте или уменьшите {size}" if shrinks else "сдвиньте")
    return f"`move_element` с `box` в координатах страницы и `\"anchor\": \"keep\"`: {how}"


def _page_inset(result, doc, form):
    """Отступ видимых вложенных от области страницы панели (`layout.panel_area`) ближе нормы `layout.PAGE_INSET`: замечание на сторону страницы.
    Отступ меряется по месту в предприятии (`item.box` модели, когда элемент стоит по правилам от области), расхождение с файлом называется.
    Отступ 0 у крупных элементов (`FILL_TYPES`) — приём, он идёт в сведения; больше нормы замечанием не бывает; элемент за областью — сведения.
    Панель, у которой область не снята, — строка сведений.
    """
    cut = layout.PAGE_INSET
    fills, blind, framed_note, outside, differs = [], [], [], [], []
    for holder in form.holders.values():
        owner = holder.item
        if owner is None or owner.type != "Panel" or not owner.visible:
            continue
        kind = layout._panel_tabs(owner)
        if kind in ("DontUse", "LeftHorizontal"):
            continue  # вложенные заполняют панель: 0 — норма раскладки
        pages = collections.defaultdict(list)
        for item in holder.children:
            if item.visible and item.type != "CommandBar":
                pages[item.page].append(item)
        if not pages:
            continue
        edge, why = layout.panel_area(doc, owner, holder.size)
        framed = not layout._panel_unframed(owner)
        if kind not in INSET_KINDS or edge is None:
            blind.append(f"«{owner.qualified()}» ({why or 'норма отступа у этого вида закладок не снята'})")
            continue
        if framed:
            framed_note.append(f"у «{owner.qualified()}» (рамка) проверены левый и верхний отступ; правый и нижний край области не сняты")
        captions = layout.tab_captions(owner.node)
        for page, items in sorted(pages.items(), key=lambda kv: _page_key(kv[0])):
            file_spans = [_span(item, 0, form) for item in items]
            model_spans = [_span(item, 1, form) for item in items]
            label = f"страница {page}" + (f" «{captions[page]}»" if isinstance(page, int) and page < len(captions) and captions[page] else "")
            for word, side in INSET_SIDES:
                if framed and side not in FRAMED_SIDES:
                    continue
                inset = lambda box: _px(box[side] if side < 2 else (edge[side - 2] - box[side]))  # noqa: E731
                where = f"«{owner.qualified()}», {label}, {word}"
                for item, (box, via) in zip(items, model_spans):
                    if inset(box) < 0:
                        outside.append(f"{where}: {_named(item, side, via)} {inset(box)} px")
                inside = [(inset(m[0]), inset(f[0]), item, m) for item, m, f in zip(items, model_spans, file_spans) if inset(m[0]) >= 0]
                if not inside:
                    continue
                least = min(m for m, _f, _i, _s in inside)
                near = [(f, item, span) for m, f, item, span in inside if m == least]
                if least == 0:
                    if all(item.type in FILL_TYPES for _f, item, _s in near):
                        fills.append(f"{where}: " + ", ".join(f"«{i.label()}»" for _f, i, _s in near[:LIST]))
                        continue
                    near = [(f, item, span) for f, item, span in near if item.type not in FILL_TYPES]
                elif not 0 < least < cut:
                    file_least = min((f for _m, f, _i, _s in inside if f >= 0), default=cut)
                    if 0 < file_least < cut:
                        differs.append(f"{where}: в файле {file_least}, в предприятии {least}")
                    continue
                names = ", ".join(_named(item, side, span[1]) for _f, item, span in near[:LIST]) + (f" … и ещё {len(near) - LIST}" if len(near) > LIST else "")
                changed = sorted({f for f, _i, _s in near if f != least})
                seen = f"; в файле {', '.join(map(str, changed))}, в предприятии {least}: `box` расходится с правилами" if changed else ""
                result.remarks.append(Remark(
                    "page_inset", ", ".join(item.qualified() for _f, item, _s in near[:LIST]),
                    f"{'вплотную к рамке страницы' if least <= CLOSE_PX else 'ближе нормы к рамке страницы'}: панель «{owner.qualified()}», {label} "
                    f"(номер с нуля, как `page` в операциях), {word}: {names} — отступ {least} px от области страницы{seen}; норма Конфигуратора — "
                    f"{cut} px от области страницы; исправление: {_fix_words(side, cut, edge, [(item, span[0]) for _f, item, span in near])}"))
    if fills:
        result.info.append("вплотную к области страницы (отступ 0) стоят крупные элементы страницы — приём, не замечание: " + "; ".join(fills[:LIST])
                           + (f" и ещё {len(fills) - LIST}" if len(fills) > LIST else ""))
    if outside:
        result.info.append("элементы за областью страницы (отступ отрицательный; правилом не проверяются): " + "; ".join(outside[:LIST])
                           + (f" и ещё {len(outside) - LIST}" if len(outside) > LIST else ""))
    if differs:
        result.info.append("отступ в файле меньше нормы, а в предприятии нет (`box` расходится с правилами от области): " + "; ".join(differs[:LIST])
                           + (f" и ещё {len(differs) - LIST}" if len(differs) > LIST else ""))
    if framed_note:
        result.info.append("; ".join(framed_note[:LIST]) + (f" и ещё {len(framed_note) - LIST}" if len(framed_note) > LIST else ""))
    if blind:
        result.info.append("отступ от области страницы не проверяется у " + "; ".join(blind[:LIST])
                           + (f" и ещё {len(blind) - LIST}" if len(blind) > LIST else ""))


def _cut(text, limit=DESIGN_CUT):
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " …"


def _design(result, doc, siblings):
    _info, warnings = design.in_form(doc)
    if siblings is not None:
        _more, found = design.compare(design.summary(doc), siblings)
        warnings = list(warnings) + list(found)
    for kind, text in warnings:
        result.remarks.append(Remark("design", "", f"{kind}: {_cut(text)} — подробно: frm_json.py design"))


def lint(doc, rel="", kind=None, table=None, siblings=None, share=MAJORITY, config=None):
    """Замечания к документу формы уровня 1: `Result`. `rel` — путь формы в выгрузке (по нему определяется вид), `kind` называет вид
    явно, `table` — таблица норм (умолчание — `patterns.json`), `siblings` — свод соседей для сверки со своей конфигурацией, `config` —
    выгрузка конфигурации (`metadata.Config`) для типа таблиц на табличных частях.
    Испорченный документ — `edit.EditError` словами; решает вызывающий (`validate`).
    """
    table = patterns.load() if table is None else table
    if kind is not None and kind not in table["kinds"] and kind != "regulated" and not kind.endswith(":?"):
        known = ", ".join(sorted(table["kinds"]))
        raise ValueError(f"вида «{kind}» нет в перечне норм: опечатка молча отключила бы ритм и роли. Виды с нормами: {known}; "
                         "вне перечня — `regulated` (регламентированная отчётность) и `other:?` (место формы неизвестно)")
    rec = census.record(doc, rel)
    kind = kind or rec["kind"]
    rec["kind"] = kind
    result = Result(kind)
    block = table["kinds"].get(kind)
    if block is None:
        result.info.append(f"вид формы — {kind}: норм у вида нет ({_why_no_norms(kind)}) — ритм и привязки роли не проверяются; "
                           "--kind называет вид явно")
    elif block.get("thin"):
        result.info.append(f"вид формы — {kind}: он из {block['configs']} конфигураций (меньше {patterns.THIN_CONFIGS}) — "
                           "норм не даёт, ритм и привязки роли не проверяются")
    else:
        result.info.append(f"вид формы — {kind}: норм {block['forms']} форм, {block['configs']} конфигураций; "
                           f"диапазон большинства — значения, дающие вместе {_pct(share)} наблюдений форм")
        _norm_remarks(result, rec, block, kind, share)
        _gap_remarks(result, rec, table, kind)
        if result.unjudged:
            result.info.append("не проверяются показатели без явного большинства: " + ", ".join(sorted(set(result.unjudged))))
        if result.thin:
            result.info.append(f"не проверяются показатели, по которым есть данные меньше чем у {patterns.THIN_CONFIGS} конфигураций, — они нормой не служат: " +
                               "; ".join(f"{key} — данные только у {n}" for key, n in sorted(set(result.thin))))
        if result.wide:
            result.info.append(f"не проверяются показатели, у которых диапазон большинства шире {WIDE_RANGE} px (значения не собираются в одну группу): " +
                               ", ".join(f"{key} {lo}–{hi}" for key, lo, hi in sorted(set(result.wide))))
    _multiline_info(result, rec, table)
    form = layout.read(doc)
    from . import anchors_fix
    for key, where, text, verdict in anchors_fix.remarks(form):
        if verdict:
            result.remarks.append(Remark(f"anchors:{key}", where, text))
        else:
            result.info.append(text)  # справка, не замечание
    _geometry(result, form)
    _captions(result, doc, form)
    _drift(result, form)
    _page_inset(result, doc, form)
    _design(result, doc, siblings)
    for found in tabletype.findings(doc, config):
        result.remarks.append(Remark("table_type", found.element, found.text))
    return result


def _why_no_norms(kind):
    if kind == "regulated":
        return "регламентированная отчётность в нормы не входит"
    if kind.endswith(":?"):
        return "место формы в выгрузке неизвестно"
    return "в перечне норм такого вида нет"
