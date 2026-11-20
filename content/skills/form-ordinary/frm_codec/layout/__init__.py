"""Раскладка обычной формы при заданном размере окна.

Модуль читает привязки и считает, где предприятие покажет каждый элемент, когда клиентская область формы (`Форма.Ширина/Высота`,
не окно) стала `W×H`. Пишет он одно — перераскладку (`relayout`). Встречные записи привязок ведёт модуль `anchors`.
Родитель элемента — форма или панель, на которой он лежит (в коде — `Holder`).

Правила модели:

* Граница = сторона объекта + смещение. Второе правило — доля `k` между двумя якорями (`k = смещение1 / (смещение1 −
  смещение2)`). Цепочки транзитивны. Граница без правила не сдвигается относительно начала родителя.
* Правило без встречной записи в предприятии не действует (`anchors.RECORD_LIST`, `anchors.side_lists`). Запись центра лежит в
  списке дальней стороны. Центр со строкой модель считает живым (половина прироста); предприятием это не проверялось.
* Раскладка перестаёт меняться (предел сжатия), когда два элемента, не пересекавшиеся в проекте, сталкиваются
  (`COLLISION_SLACK`); элемент подошёл бы к краю области ближе `MARGIN` (или своего проектного отступа, если он меньше); левая
  (верхняя) граница элемента, идущего с дальним краем, ушла бы за 0 родителя; элемент стал бы меньше минимума своего типа
  (`MIN_SIZE`, `PANEL_MIN`; если числа нет, минимум не проверялся и сжатие идёт до нуля).
* Порядок осей (`order`): вторая ось считается при фактическом росте первой.
* Раскладка выше окна отнимает у ширины полосу прокрутки 16, шире — у высоты (`SCROLL`), но не всегда (`Layout.bar_appears`).
* Элементы страницы панели, кроме первой, при смене размера не показаны и остаются на проектном месте (`hidden_page`). После
  показа и перехода на другую страницу скрытая стоит там, где её оставила последняя раскладка (`stale`).

Чего модель не знает, она называет словами: минимум панели с остальными видами закладок; рамку формы; DPI не 96; несколько
страниц формы (кроме закладок «Сверху» при DPI 96 без рамки или с рамкой «Одинарная»); закладки других положений; полосу
прокрутки при открытии в запомненном размере; «залипание» (`docs/layout.md`); порядок осей при мыши. Состояние сеанса, которого
нет в файле, задают аргументы `Layout`: `order`, `at_open`, `shown`, `stale`.

Край родителя для предела «к краю» определяет `anchors.holder_edges`; если он не даёт край, край оценивается, и отчёт пишет
«край оценён: …» (`_inner`). Блок координат держит края (`x, y, right, bottom`). Целые границы:
`floor(v + ½)`, с правилом к центру — `floor(v)`; вдоль цепочки `#N.r+8` граница строится от округлённой стороны соседа.
"""
import math

from .. import anchors, edit, guides, lstring
from .model import (BORDERS, BORDER_KEYS, AXES, AXES_AT,
    AXES_OF, ORDERS, HOLDER_SIDE, SIDE_CH,
    CENTER_SIDES, MARGIN, COLLISION_SLACK, TEXTBOX_BUTTONS,
    TEXTBOX_BUTTON_WIDTH, MIN_SIZE, PANEL_MIN, BUTTON_MIN_BY_CAPTION,
    BUTTON_ABOVE_PROJECT, BUTTON_LONG, MIN_WHERE_BUTTON_HEIGHT, MIN_WHERE,
    PANEL_WHERE, MIN_SLACK, NEAR_MEASURED, NEAR_CENTER_MEASURED,
    SHARE_OBSERVED, FROZEN_BELOW_MIN, SCROLL, SCROLL_REACH,
    SIDE_WORDS, EPS, Rule, Item,
    Holder, _items_of, _int, _pair,
    textbox_buttons, min_size, _caption, caption_measured,
    _panel_tabs, _min_note, _item, _rule,
    _rows, _inner, _estimate, _edge_words,
    ALIVE, DEAD, UNKNOWN, BOX_TOLERANCE,
    _num, _EDGE)
from .rules import (rule_state, _live, dead_rules, _all_items)
from .coeffs import (Cycle, coefficients, GROW_MIN, MOVE_MAX,
    GROWS, STANDS, MOVES, PARTLY,
    BEHAVIOUR_WORDS, MOVES_WORDS, DEAD_RULE_WORDS, DEAD_RULES_WORDS,
    SENTENCE, LISTED, LEGEND, BRIEF,
    behaviour_words, horizontal_behaviour, vertical_behaviour, rule_box,
    _page_by_rules, _pages_by_rules_all, shown_page_diverged, hidden_page,
    AREA_MIN)
from .limit_calc import (Limit, min_unmeasured, _named, _span,
    _overlap_interval, holder_limits, _center_border, _round_border,
    _steps_to_edge, _crossing, _moves, bounds)
from .area import (PAGE_INSET, PANEL_AREA_CUT, PANEL_HEIGHT_DERIVED, PICTURE_TOP_CUT, LEFT_STRIP_PAD,
    LEFT_FRAME, TAB_PICTURE_WORDS, LEFT_TAB_WORDS, tab_pictures,
    tab_captions, panel_area, panel_not_checked, PANEL_KIND_RU,
    _NO_BORDER, _panel_unframed, _area, _same_edge,
    _kinds_words, _carrier_shown, FRAMES_TABS_MEASURED, _form_border_kind,
    panel_collision,
    TAB_PAD, TAB_GAP, TAB_PICTURE, TAB_STRIP, TAB_STRIP_PICTURE, ROW_INSET, SCROLL_ARROWS, VERTICAL_PAD, LEFT_PICTURE_EXTRA,
    ROWS_TOP, ROWS_BOTTOM, SCROLL_KINDS, VERTICAL_KINDS, SIDE_KINDS, TRANSPOSED, PANEL_AREA_KINDS,
    SIDE_AREA_WORDS, RIGHT_AREA_WORDS, PICTURE_ONLY_WORDS, NO_AREA_WORDS, MEASURE_WORDS,
    strip_height, tab_widths, tab_rows, row_order, row_widths, multi_rows, left_strip, panel_frame)
from .form import (Form, _whole_box, read)
from .atsize import (Layout, lay_out, _page_variants, paged_layout,
    model_boxes, apply_model_boxes, form_range)
from .notes import (EARLY, STRETCHY, NEAR_EDGE, PANEL_PROBE,
    CORPUS_STAMP, CORPUS_DEAD, CORPUS_GROWTH_LIMITS, CORPUS_WARNINGS,
    CORPUS_RELAYOUT, CORPUS_BACK, CORPUS_BOX_MISMATCH, CORPUS_HIDDEN,
    CORPUS_ODD_TRIP, CORPUS_BACK_MIN, CORPUS_RANGE_SUM, CORPUS_RANGE_MIN,
    CORPUS_RESIDUE, CORPUS_EDGE_ESTIMATED, box_mismatches, shown_for,
    design_place, nested_area_mismatches, nested_area_words, wide_pages,
    narrow_pages, _page_gaps, wide_pages_words, narrow_pages_words,
    scroll_panels, scroll_panels_words, page0_edge, page0_rewritten,
    PAGE0_OTHER_WORDS, native_page0_edges, _mismatch_words, _box_words,
    TABS_PAGE0_SHIFT, _page0_edges, REPEATED_TOP_OFFSETS, repeated_top,
    REPEATED_TOP_WORDS, _from_area_elements, _page0_guide_offset, tabs_page0_problems,
    problems, panel_share, _share, _dead_tail,
    _to_self, _size_words, _coupled_words, limit_line)
from .report import (summary, obstacle, table, _sticky_words,
    _order_words, GUIDE_AXIS, GUIDE_MARK, _unmeasured_buttons,
    _hidden_words, _edge_zero, _near_breach, _holder_words)
from .resize import (relayout, liftable, _narrowed_buttons, _hidden_relayout_words,
    _beyond_far, blocking, _limit_phrase, _advice,
    _names, _scroll_tail, _order_tail, _beyond_near,
    _freeze_refusal, _inversion_refusal, _form_border, _moves_in,
    _follows_far_edge, _panel_written, _rewrite, RELAYOUT_WINDOW_WORDS,
    _file_vs_screen_words, _range_change, _bound, back_stops,
    _back_words, margin_class, _side_shift)
