"""Состояние формы по разбору кода и запросу (`CodeMarks`) и слой наложений размеченной картинки досье (`overlay_layer`). На картинке из пометок кода остаётся только штриховка
безусловно скрытого; условное, уголки и подписи в рисунок не попадают: о них говорят `notes` и досье."""
from xml.sax.saxutils import escape, quoteattr

from .core import _clean, _n


CODE_HATCH_COLOR = "#ef6c00"       # штриховка безусловно скрытого


class CodeMarks(dict):
    """Состояние формы по коду: `{индекс элемента: {свойство: [значения]}}` — то, что код делает по условию или вероятно (на картинке не рисуется, называется в `notes`); в `parts` —
    сведения о частях элементов, у которых нет своего индекса: `pages` — `{(индекс панели, номер страницы): {свойство: …}}`, `columns` — `{(индекс таблицы, имя колонки без регистра):
    {свойство: …}}`, `buttons` — `{индекс панели: [сведения о кнопке, которую добавляет код]}` (`_added_entry`). Видимость страницы штрихует её закладку, видимость
    колонки — её шапку.

    Что код делает безусловно и несомненно, рисунок применяет: `applied` — `{индекс элемента: {свойство: значение}}` (`видимость` Ложь — не нарисован, `доступность`
    Ложь — серым; «только просмотр» на рисунке не выделяется), а в `parts`: `applied_pages` и `applied_columns` (те же ключи, что у `pages` и `columns`; страница без закладки, колонка
    без ячейки, заголовок другим текстом), `current_page` — `{индекс панели: номер страницы}`, `new_columns` — `{индекс таблицы: [{name, title}]}`, `removed_buttons` —
    `{индекс панели: [имена кнопок]}`; `disabled_buttons` — `{индекс панели: [имена кнопок без регистра]}`, которые код безусловно делает недоступными (серые); `cond_buttons` — `{индекс панели: [имена кнопок без регистра]}`, видимость которых код меняет по условию. Варианты на одном месте — `groups`: `{группа: [индексы элементов]}` и `defaults` — индексы, которые рисуются из группы."""

    def __init__(self, *args, parts=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.parts = parts or {}
        self.applied = {}
        self.field_values = {}             # значения данных полей, которые рисунок рисует: `{индекс: ("bool", True|False) | ("text", строка) | ("number", "7")}` (`brief.module_effects.value_of`)
        self.groups = {}
        self.defaults = set()
        self.form_disabled = False
        self.hatch_hidden = False          # режим скрытого: скрытое рисуется на своём месте со штриховкой (`hatch`) либо не рисуется (`hide`)
        self.hatch_conditional = False     # режим условного: видимость, которую код меняет по условию или вероятно, рисуется той же штриховкой, что скрытое (`hatch`), либо как в файле (`plain`)
        self.hidden_src = {}               # кто скрыл: `{("el", индекс) | ("page", панель, номер) | ("col", таблица, имя без регистра) | ("btn", панель, имя без регистра): "код" | "запрос"}`; запрос записывает `formstate`;
                                           # нет записи: у элемента — файл (если его не прячет `applied`), у страницы, колонки и кнопки — код (файл прячет только колонку, это знает сам рисунок)
        self.asked = set()                 # то, что поставил явный запрос (`--state`), в тех же ключах (`("el", индекс, свойство)`, `("cur", панель)`, …): в слова «по разбору кода» не входит
        self.rejected = []                 # отклонённые записи разбора кода: `[{index, kind, why}]` (`brief.code_marks`); рисунок о них говорит в `notes`
        self.force_show = set()            # индексы элементов, которые запрос показывает, хотя файл или код их скрывают
        self.show_columns = set()          # `(индекс таблицы, имя без регистра)` колонок, скрытых в файле, которые запрос показывает
        self.forced_enabled = {}           # `{индекс: bool}` доступность по запросу (сильнее файла и кода)
        self.collapsed = {}                # `{индекс панели: Лево|Право|Верх|Низ}` — свёрнутые панели: рисунок строит раскладку со свёрнутой панелью (`layout.fold`)
        self.requested = []                # слова о том, что взято из запроса (`--state`), для `notes` и легенды

    def __bool__(self):
        return bool(len(self) or any(self.parts.values()) or self.applied or self.field_values or self.groups or self.form_disabled or self.force_show or self.show_columns
                    or self.forced_enabled or self.hatch_hidden or self.hatch_conditional or self.requested or self.rejected or self.collapsed)


CODE_TEXT_TYPES = frozenset({"Label", "Button", "CheckBox", "RadioButton", "GroupBox"})      # виды, у которых есть подпись с цветом текста (`scene._item_notes`)
CODE_DEFS = ("<defs><pattern id='code-hatch' width='6' height='6' patternUnits='userSpaceOnUse' patternTransform='rotate(45)'>"
             f"<line x1='0' y1='0' x2='0' y2='6' stroke='{CODE_HATCH_COLOR}' stroke-width='1.5' stroke-opacity='0.75'/></pattern></defs>")


def hidden_overlay(x, y, w, h, who, conditional=False):
    """Скрытое в режиме `hatch`: штриховка и пунктирный контур, без текста и уголка. Кто скрыл (`файл`, `код`, `запрос`), на картинке не написано: оно в атрибуте `data-hidden-by`,
    в `notes` рендера и в досье. Одно оформление у элементов, закладок, шапок колонок и кнопок. Условное (`conditional`): нарисовано как видимое, поверх него — та же штриховка
    той же плотности, без контура."""
    conditional = conditional or who == "условие"
    stroke = "stroke='none'" if conditional else f"stroke='{CODE_HATCH_COLOR}' stroke-opacity='0.8' stroke-width='1' stroke-dasharray='4 2'"
    cond = " data-conditional='1'" if conditional else ""
    return [f"<rect class='hidden-hatch'{cond} data-hidden-by={quoteattr(who)} x='{_n(x)}' y='{_n(y)}' width='{_n(w)}' height='{_n(h)}' fill='url(#code-hatch)' {stroke}/>"]


# ── Слой наложений (размеченная картинка досье формы) ──

OVERLAY_COLORS = {"area": "#1565c0", "page": "#6a1b9a", "group": "#2e7d32", "section": "#2e7d32", "top_bar": "#00838f", "bottom_bar": "#00838f",
                  "buttons": "#00838f", "column": "#ef6c00", "content": "#ad1457", "row": "#616161", "pair": "#616161",
                  "single": "#616161", "unclear": "#d32f2f"}
OVERLAY_FRAMED = frozenset({"area", "page", "group", "section", "top_bar", "bottom_bar", "buttons", "column", "content"})
OVERLAY_SMALL = frozenset({"row", "pair", "single", "unclear"})
OVERLAY_TAB = "#fbc02d"    # кружок порядка обхода
OVERLAY_LABEL = 9           # кегль метки узла при масштабе 1, px
OVERLAY_GLYPH_W = 0.62      # ширина знака метки в долях кегля


def _overlay_font(size):
    return f"font-family='Tahoma, sans-serif' font-size='{size}'"


def _overlay_clash(placed, box):
    return next((p for p in placed if not (box[2] <= p[0] or box[0] >= p[2] or box[3] <= p[1] or box[1] >= p[3])), None)


def overlay_layer(overlay, width, height):
    """SVG-части слоя наложений: рамки узлов по ролям, метки номеров узлов у левого верхнего угла, кружки порядка обхода,
    красные штриховые рамки «неясно». Метки не налезают друг на друга: занятое место обходится сдвигом вправо, затем вниз.
    `overlay` — `nodes [(номер, роль, (лево, верх, право, низ))]`, `tab [(имя, номер, box)]`, `unclear [box]` и необязательный
    `scale` (масштаб итоговой картинки: кегль меток растёт, чтобы после уменьшения они читались). Координаты — клиентской
    области формы."""
    scale = getattr(overlay, "scale", 1.0) or 1.0
    size = min(max(round(OVERLAY_LABEL / scale), OVERLAY_LABEL), 3 * OVERLAY_LABEL)
    pad, line = max(size // 4, 2), size + 3
    parts = ["<g class='overlay'>"]
    for ident, role, (l, t, r, b) in overlay.nodes:
        if role in OVERLAY_FRAMED:
            parts.append(f"<rect class='frame {role}' data-node='{ident}' x='{l + 0.5}' y='{t + 0.5}' "
                         f"width='{max(r - l - 1, 0)}' height='{max(b - t - 1, 0)}' fill='none' "
                         f"stroke='{OVERLAY_COLORS[role]}' stroke-width='1.5' stroke-opacity='0.85'/>")
    for l, t, r, b in overlay.unclear:
        parts.append(f"<rect class='unclear' x='{l + 0.5}' y='{t + 0.5}' width='{max(r - l - 1, 0)}' height='{max(b - t - 1, 0)}' "
                     f"fill='none' stroke='{OVERLAY_COLORS['unclear']}' stroke-width='2' stroke-dasharray='6 3'/>")
    placed = []
    occupied = [(box, ident) for ident, role, box in overlay.nodes if role in OVERLAY_SMALL]      # где стоят подписи и поля: метка на них не ложится
    for ident, role, box in overlay.nodes:
        w = round(len(ident) * size * OVERLAY_GLYPH_W + 2 * pad)
        # Метка стоит вне текста: над рамкой узла, а если там занято или края нет — у нижнего края внутри, слева от узла, у верхнего угла внутри; берётся место с наименьшим
        # перекрытием с чужими мелкими узлами и уже поставленными метками (при равенстве — первое по порядку).
        spots = [(box[0], box[1] - line + 1), (box[0], box[3] - line), (box[0] - w, box[1]), (box[0], box[1])]

        def cost(spot):
            x, y = min(max(spot[0], 0), max(width - w, 0)), spot[1]
            area = lambda a: max(min(a[2], x + w) - max(a[0], x), 0) * max(min(a[3], y + line) - max(a[1], y), 0)
            lost = (0 if y >= 0 else -y * w) + (0 if y + line <= height else (y + line - height) * w)
            own = role in OVERLAY_SMALL       # мелкий узел — это сама подпись или поле: метка поверх него закрывает содержимое; рамку-контейнер метка внутри не закрывает
            return lost * 4 + sum(area(b) for b, other in occupied if own or other != ident) + sum(area(p) for p in placed)
        x, y = min(spots, key=cost)
        y = max(y, 0)
        for _ in range(60):
            x = min(max(x, 0), max(width - w, 0))
            hit = _overlay_clash(placed, (x, y, x + w, y + line))
            if hit is None:
                break
            if hit[2] + 1 + w <= width:
                x = hit[2] + 1
            else:
                x, y = box[0], hit[3] + 1
        placed.append((x, y, x + w, y + line))
        color = OVERLAY_COLORS.get(role, "#616161")
        parts.append(f"<g class='label' data-node='{ident}'><rect x='{x}' y='{y}' width='{w}' height='{line}' fill='white' "
                     f"fill-opacity='0.6' stroke='{color}' stroke-width='0.5'/>"
                     f"<text x='{x + pad}' y='{y + size}' {_overlay_font(size)} font-weight='bold' fill='{color}'>"
                     f"{escape(ident)}</text></g>")
    radius = size * 0.8
    for name, number, (l, t, r, b) in overlay.tab:
        cx, cy = max(r - radius - 1, l + radius), t + radius + 1
        parts.append(f"<g class='tab' data-name={quoteattr(_clean(name))}><circle cx='{_n(cx)}' cy='{_n(cy)}' r='{_n(radius)}' "
                     f"fill='{OVERLAY_TAB}' stroke='#5d4037' stroke-width='1'/>"
                     f"<text x='{_n(cx)}' y='{_n(cy + size * 0.35)}' text-anchor='middle' {_overlay_font(size - 1)} "
                     f"font-weight='bold' fill='#3e2723'>{number}</text></g>")
    parts.append("</g>")
    return parts
