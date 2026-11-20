"""Каркасный рендер обычной формы в SVG: клиентская область предприятия при заданном размере окна.

Координаты берутся только из модели раскладки (`layout.Layout`); второй модели нет, и ключей `coords` рендер не
читает (края блока координат отдаёт `Layout.measured`). У вложенных элементов координаты отсчитываются от их
панели плюс отступ области страницы, зависящий от вида закладок (`PAGE_AREA_OFFSET`). Каждый тип рисуется
узнаваемым каркасом в точных координатах; незнакомый тип — серым прямоугольником с именем, и в `unknown`
попадает строка о нём. Высоту поля рендер не вычисляет (19 или 22 — свойство файла) и рисует box из модели.
Шрифт и цвета приблизительные; тексты по пикселям не сравниваются.

Что рендер не знает, он называет в `notes`, а не дорисовывает догадкой. Вложенные элементы панели с видом
закладок, для которого отступ неизвестен, не рисуются; сама форма при этом рисуется, остальные элементы на
месте."""
from . import action_icons, charts, glyph_text, picture_bitmap, textmeasure, window_frame  # noqa: F401  (модули рендера: имена прежние)
from .core import (
    CALIBRATED, COLOR_BLACK, DISABLED_FIELD, DISABLED_NOTE, DISABLED_TEXT, EDGE, FIELD_BUTTON, FONT, FORM_BG,
    FORM_TABS_OFFSET, FRAME_NOT_CLAIMED, GROUP_TOP, LEFT_STRIP, LEFT_TAB, NESTED_NOTES, NO_FRAME, PAGE_AREA_OFFSET, PANEL_FRAME_MEASURED,
    PICTURE_UNSEEN_NOTE, Rendered, SCROLL_BAR, SCROLL_BUTTON_H, SCROLL_BUTTON_V, SCROLL_DARK, SCROLL_LIGHT, STRIP, TEXT_COLOR, TOLERANCE, Unmeasured, _BAD_XML,
    _NOT_OWN, _TEXT_TAG, _caption, _clean, _color_of, _dig, _enabled, _first_text, _font_attrs, _font_of, _form_enabled, _form_offset,
    _form_tabs, _grey, _label_lines, _line_pitch, _n, _page_captions, _panel_offset, _scroll_arrow, _scroll_bar, _text, _vline, absolute, picture_box_unseen)  # noqa: F401
from .marks import (
    CODE_DEFS, CODE_HATCH_COLOR, CODE_TEXT_TYPES, CodeMarks, OVERLAY_COLORS,
    OVERLAY_FRAMED, OVERLAY_GLYPH_W, OVERLAY_LABEL, OVERLAY_SMALL, OVERLAY_TAB, _overlay_clash, _overlay_font,
    overlay_layer)  # noqa: F401
from .bars import (
    ADDED_DISPLAY, AUTO_FILL_KNOWN_NOTE, AUTO_FILL_MARK, AUTO_FILL_NOTE, BAR_ARROW, BAR_BOLD, BAR_BOTH, BAR_BOTH_PAD,
    BAR_BOTH_TEXT, BAR_END, BAR_GLYPH, BAR_ICON, BAR_KIND, BAR_MORE, BAR_PAD, BAR_POPUP, BAR_POPUP_ICON, BAR_RIGHT_END, BAR_SEP, BAR_START,
    BAR_VSTART, BUTTON_ICON, BUTTON_ICON_GAP, DEFAULT_ACTION, FORM_BAR_FILL, FORM_BAR_LINE, ICON_NOTE, NO_ACTION_NOTE, NO_ACTION_TEXT, NO_SOURCE, VERTICAL_NOTE, VIEW_BOTH,
    VIEW_PICTURE, VIEW_TEXT, _action_of, _action_source_is_table, _added_entry, _arrow_mark, _auto_fill_bar, _auto_fill_flag,
    _auto_fill_known, _auto_fill_strip, _bar_buttons, _command_bar, _entry_width, _file_entries, _filled_bar, _form_bar, _form_bar_line,
    _form_kind, _free_filled_bar, _icon, _own_set, _platform_entries, _platform_fill, _table_data_kind, _tidy, _vertical_bar,
    _vertical_layout, _with_added, bar_layout, bar_spans, bar_vertical, button_has_picture, button_menu_pair, button_no_action, button_picture,
    bar_back_notes, bar_fill, button_standard, button_view, shown_text, table_kind_of)  # noqa: F401
from .fields import (
    BUTTON_CAPTION_PAD, CELL, CHECK_CAPTION_PAD, CHECK_TEXT_LEFT_X, CHECK_TEXT_X, COMBO_ARROW, FIELD_BUTTONS,
    FIELD_BUTTON_NAMES, RADIO_CAPTION_PAD, RADIO_TEXT_X, _button, _check_box, _combo_has_list, _field_flags, _has_picture, _label, _own_bitmap, _radio_button,
    _sheet_box, _text_box, _title_text, element_button_picture)  # noqa: F401
from .tables import (
    MIN_SCALE, NEXT_ROW, PICTURE_COLUMN_MIN, SAME_COLUMN, TABLE_GRAD, TABLE_HEADER, TABLE_LINE, TABLE_LINE_STEP, TABLE_PAD, TABLE_ROW_STEP,
    TABLE_SCROLL, TABLE_SEP, TABLE_TEXT_PAD, _cell_lines, _footer_cells, _gradient, _is_list_table, _rows_picture, _table_band, _table_box,
    _table_flags, _wrap, band_height, column_cells, column_edges, column_groups, column_screen_widths, column_width, header_cuts,
    table_columns)  # noqa: F401
from .panels import (
    TAB_ACCENT, TAB_ACTIVE, TAB_CORNER, TAB_GAP, TAB_INACTIVE, TAB_PAD, TAB_PICTURE, _frame, _group_box, _group_frame, _page_pictures,
    _panel, _panel_frame_box, _tab)  # noqa: F401
from .scene import (
    CAPTION_PATH, DRAW, FILL, _font_note, _hidden, _item_notes, caption_text, context_menu_bars, page_names_of, render)  # noqa: F401

# Поле календаря рисует `calendar_box`; в таблицу `DRAW` оно записано здесь, а не в `scene.py`.
from . import calendar_box  # noqa: E402
DRAW.setdefault("CalendarBox", calendar_box.draw)
