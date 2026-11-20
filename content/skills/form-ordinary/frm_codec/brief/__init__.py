"""Досье формы для модели: назначение, структура, поведение, отклонения от норм, стиль конфигурации, факты, картинки и возможности правки.

`build(doc, form_path, config_dir=None, out_dir=None, module_text=None, ..., detail=None)` собирает досье одной формы и пишет в каталог `brief.md` (короткий обзор для модели:
`brief.overview`), `brief.json` (полные данные ключами) и три картинки (`brief.images.write_images`); при `detail` — ещё `brief-full.md` (подробности частей: `brief.markdown.render_detail`).
Форму и её файлы модуль не меняет. Вывод детерминирован: одна форма с теми же входами даёт те же файлы.

Обзор `brief.md`: шапка, «Что это за форма», «Состав», «Что делает код» (при разобранном коде), «Растяжение окна», «Проблемы», «Особенное для правки», «Как исследовать дальше».
Подробности (`--detail structure|columns|facts|norms|style|editing|code|all`) идут разделами прежнего досье:

1. шапка — вид формы, объект (по метаданным либо по пути формы), версия, размер, DPI, что досье получило и чего нет (у отсутствующего
   названо, чего без него не оценить);
2. назначение — объект по метаданным выгрузки (реквизиты, табличные части), таблицы формы, данные на форме, события формы и элементов с
   процедурами модуля (одна процедура у нескольких кнопок панели — одна строка), что код модуля меняет у элементов по разбору модели (`brief.codenotes`, `brief.module_effects`);
3. структура — дерево узлов (`structure.recognize`), таблица элементов (короткие имена, надпись пары в строке поля, свойства),
   страницы панелей (закладки либо «закладок нет»), колонки каждой таблицы и кнопки каждой командной панели (`brief.content`);
4. поведение — предел раскладки, что растягивается (с долей роста окна) и что остаётся на месте по узлам, проблемы раскладки;
5. нормы вида — только показатели вне диапазона большинства по `patterns.json`;
6. стиль конфигурации — те же показатели у соседних форм того же вида в выгрузке (самое частое значение и число форм);
7. факты для оценки (`brief.facts.facts`), кроме тех, что названы в разделе «Поведение»; тексты — словами (`brief.words`);
8. картинки и их условности;
9. что и как можно менять — ограничения формы, имена, на которые опирается код, операции редактора по видам элементов формы, частые правки с
   примерами `ops.json`, как проверить правку (`brief.editing`).

`brief.json` несёт разделы ключами `head`, `purpose`, `structure`, `behavior`, `norms`, `style`, `facts`, `images`, `editing`; номера узлов
совпадают с `brief.md` и с номерами узлов на `marked.png`. Имена элементов в `brief.json` полные, в `brief.md` — короткие.

Без выгрузки конфигурации, без `form.bsl` и без соседних форм досье строится, а недостающее разделы называют словами. Форма версии
не 16 или с DPI не 96 строится тоже: шапка говорит, что картинки и нормы рассчитаны на версию 16 и DPI 96.

Код разложен пакетом по разделам досье; сам `brief` — фасад: `build`, `render_md`, `parse_module`, `handlers` и прочие имена прежнего модуля берутся отсюда, а лежат так:

* `vocab` — слова и словари (виды форм, события, подписи, имена типов платформы, пороги); `fmt` — мелкая запись текста; `typewords`, `paths`;
* разделы: `head` (шапка), `purpose` (назначение, модуль формы), `outline` (структура), `behavior`, `norms`, `style`, `facts_section`, `pictures`;
* `markdown` — запись `brief.md`; `assemble` — `build` и запись `brief.json`;
* `modulescan` — чтение текста модуля без разбора смысла (строки без комментариев, границы процедур, условия); `codetask` — задание на разбор кода (`code-task.md`, карта модуля,
  перечень имён на форме, вопросы); `codenotes` — проверка записей разбора, которые сделала модель (`code-notes.json`), и перевод их в перечень «что код меняет»; `module_effects` — свёртка
  перечня; `codefacts` — точный поиск обращений к несуществующим элементам и обработчиков без процедуры; `code_marks` — состояние формы по коду для `edit --render`;
* `content`, `editing`, `facts`, `images`, `places`, `words` — состав как в предприятии, факты, картинки, места на форме, возможности правки, слова вывода.

Код формы разбирает модель по `docs/brief-code.md`, а не шаблоны навыка: у формы с модулем сначала выдаётся только задание на разбор (`code_task`), затем `build(…, code_notes=…)`
проверяет записи и собирает досье; без записей (`--no-code`) досье не говорит, что код делает на экране.
"""

from .vocab import (
    REFERENCE_VERSION, REFERENCE_DPI, LISTED, MODULE_LINE, OTHER_PROCEDURES, STYLE_MIN, POOL_FROM, DEFAULT_DIR, KIND_WORDS, EVENT_WORDS,
    ANCHOR_LABELS, GAP_LABEL, REMEMBERED_SIZE_WORDS, DESKTOP_NOTE, FIXED_SIZE_WORDS, FACT_TITLES, IN_BEHAVIOR, NEEDS_MODULE, NEEDS_CONFIG,
    LINT_DUPLICATES, WITHOUT, READ_WORDS, EXTRA_ROLES, TYPE_WORDS, REF_WORDS, PLATFORM_TYPE_WORDS, DATE_WORDS, MARK_SHOWN, FOLD_LISTED
)  # noqa: F401
from .fmt import (
    _list, _quoted, _cell, _pct, _table, _title, _measure_label, _kind_words
)  # noqa: F401
from .typewords import (
    platform_type_words, _type_words, _std_type_words
)  # noqa: F401
from .paths import (
    _display_path, METADATA_DIRS, OBJECT_KINDS, _object_by_path, _inside, _meta_key
)  # noqa: F401
from .head import (
    _head, _kind_source, _description, _object_line, _md_head
)  # noqa: F401
from .purpose import (
    _HEAD, _PARAMS, _EXPORT, _END, _SKIP_START, _header_end, parse_module, _handler_of, _event_rows, _flat_buttons, handlers, _module_section,
    _Binder, _object_section, _main_type_guid, _extra_of, _main_attribute_words, _extra_section, _purpose, _effect_detail, EFFECT_LISTED,
    EFFECT_ORDER, EXTRA_TITLES, _md_extra, _md_purpose, _fold_handlers, _places_text, _md_module, _md_form_effects, _md_code, _effect_prop,
    _short_of
)  # noqa: F401
from .outline import (
    _page_nodes, _effect_marks, _element_rows, _table_kinds, _tables, _screen_widths, _columns_by_code, _bars, COLUMNS_SHOWN, PLACEHOLDER_TEXT,
    _action_name, _button_label, _submenu_note, _bar_code_marks, _buttons_text, _fill_items, _md_bars, LOCATION_WORDS, _md_columns, _md_pages,
    DEFAULT_PAIR, DATA_PREFIX, _data_cell, _element_table, _md_structure, _flat
)  # noqa: F401
from .behavior import (
    ROW_ROLES, _share, _group_behaviour, _shares, _named, _behaviour_text, _row_nodes, _own_members, _behavior, _md_behavior
)  # noqa: F401
from .norms import (
    _norm_row, _multiline_of, _norms, _md_norms
)  # noqa: F401
from .style import (
    _measured, _neighbor, _mode, _style, _style_behaviour_notes, EDGE_ANCHORS, _md_style
)  # noqa: F401
from .facts_section import (
    _facts_json, _drop_duplicates, _applicability, _focus_by_code, _switched_by_code, GROUP_MIN, INEXACT_SHOWN, GROUP_SHOWN, GROUPED,
    OPEN_PROCEDURES, FIELD_WIDTH_NOTE, _field_width_lines, _group_line, _md_facts
)  # noqa: F401
from .pictures import (
    IMAGE_WORDS, _images_section, IMAGE_CONVENTIONS, _md_images
)  # noqa: F401
from .markdown import (
    render_md, render_detail, DETAIL_PARTS, DETAIL_WORDS
)  # noqa: F401
from .overview import (
    render_overview
)  # noqa: F401
from .assemble import (
    build, _build, code_task
)  # noqa: F401
