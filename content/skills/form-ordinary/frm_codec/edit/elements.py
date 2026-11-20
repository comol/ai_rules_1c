"""Элементы: добавление, удаление, переименование, привязки, вид. Все имена отдаёт фасад `frm_codec.edit`."""

import copy
import uuid

from .. import design as _design, json0, schema, typed as _typed
from .base import container as _container, layout_block as _layout_block

from .names import (
    ACTIONS_GUID,
    ACTION_SOURCE,
    ANCHORS,
    BINDINGS,
    BIND_ELEMENT,
    BTN_OWNER,
    BUTTON_ID,
    CONTENT,
    COORDS,
    COUNT,
    TAB_ORDER,
    DEFAULT_BUTTON,
    DEPENDENTS,
    DEP_ELEMENT,
    ELEMENTS,
    EVENTS,
    EVENT_ITEMS,
    HEIGHT,
    INDEX,
    ITEMS,
    LAST_INDEX,
    LS_COUNT,
    LS_ITEMS,
    NAME,
    NAME_BLOCK,
    NO_ANCHOR,
    NO_REFERENCE,
    ON_CORPUS,
    PAGE,
    PAGES,
    PAGE_ITEMS,
    PATTERN_KIND,
    PATTERN_LENGTH,
    PATTERN_NUMBER,
    PATTERN_REF,
    PATTERN_TYPES,
    RULES,
    RULE_OBJECT,
    SHORTCUT,
    SHORTCUT_KEY,
    SHORTCUT_MODIFIERS,
    PAGE_SEQUENCE,
    TEXTBOX_PATTERN,
    TITLE_REF,
    TOOL_TIP,
    WIDTH,
    X,
    Y,
    _run,
)
from .base import (
    EditError,
    Place,
    _bars,
    _buttons,
    _caption_places,
    caption_slot,
    _find_pages,
    _fit_guides,
    _layout_rows,
    _on_corpus,
    element_names,
    elements_of,
    find_element,
    holder_by_name,
    holders,
    no_pages_words,
    pages_count,
    set_caption,
    set_text,
)
from .buttons import _named


# ── Элементы ──────────────────────────────────────────────────────────────────────────────────

def _indexes(doc):
    """`{индекс: узел}` по всем элементам формы, любой глубины."""
    out = {}
    for _name, holder in holders(doc):
        block = holder.get(ELEMENTS)
        for item in (block.get(ITEMS) or []) if isinstance(block, dict) else []:
            if isinstance(item, dict) and isinstance(item.get(INDEX), int) \
                    and not isinstance(item.get(INDEX), bool):
                out[item[INDEX]] = item
    return out


def _title(doc):
    block = doc.get("form")
    return block.get("title") if isinstance(block, dict) else None


def _next_index(doc):
    """Следующий индекс элемента: на единицу больше и счётчика выдачи, и наибольшего занятого.

    Счётчик (`form.title.last_index`) — наибольший ВЫДАННЫЙ номер, он бывает ВПЕРЕДИ наибольшего
    занятого (после удаления элемента номер остаётся за ним); max по занятым выдал бы новому
    элементу уже выдававшийся номер.
    """
    title = _title(doc)
    last = title.get(LAST_INDEX) if isinstance(title, dict) else None
    known = list(_indexes(doc)) + ([last] if isinstance(last, int)
                                   and not isinstance(last, bool) else [])
    return (max(known) if known else 1) + 1


def drop_dependents(doc, index):
    """Убрать ВСЕ встречные записи, называющие этот индекс, — у элементов И у родителей (`dependents_*`
    блока раскладки). Число.

    Зовётся при ДОБАВЛЕНИИ элемента (через `anchors.sync`): висячая запись зависимых может называть
    индекс, который счётчик выдаст следующему элементу, и новый элемент родился бы с чужой
    встречной ссылкой. Индексы платформа не переиспользует, поэтому запись на ещё не существующий
    индекс остаётся от давно удалённого элемента. Правило «висячие не трогаем» (у `validate`) здесь
    не работает: они перестают быть висячими.
    """
    from .. import anchors as _anchors
    return _anchors.drop_naming(doc, index)


def _forget(doc, gone):
    """Убрать из формы всё, что называет удалённые индексы. Возвращает перечень — словами.

    Висячую запись зависимых платформа терпит, но пропавшую запись ЖИВОГО правила не дописывает,
    и без неё правило в предприятии мертво; снимаются только записи удалённых. `form.title` со
    ссылкой на удалённую кнопку платформа сама сбрасывает при первом сохранении. Привязка данных на
    несуществующий элемент в корпусе не встречается.
    """
    said = []
    for _name, holder in holders(doc):
        for item in (holder.get(ELEMENTS) or {}).get(ITEMS) or []:
            coords = item.get(COORDS) if isinstance(item, dict) else None
            if not isinstance(coords, dict):
                continue
            for key in DEPENDENTS:
                members = coords.get(key)
                if isinstance(members, list):
                    left = [m for m in members if m.get(DEP_ELEMENT) not in gone]
                    if len(left) != len(members):
                        said.append(f"{(item.get(NAME_BLOCK) or {}).get(NAME)}/{key}: "
                                    f"убрано записей {len(members) - len(left)}")
                    coords[key] = left
            for side, key in enumerate(ANCHORS):
                anchor = coords.get(key)
                for rule_name in RULES:
                    rule = anchor.get(rule_name) if isinstance(anchor, dict) else None
                    if not isinstance(rule, dict) or rule.get(RULE_OBJECT) not in gone:
                        continue
                    rule.update(NO_ANCHOR)
                    said.append(f"{(item.get(NAME_BLOCK) or {}).get(NAME)}/{key}/{rule_name}: "
                                "привязка сброшена в «нет»")
    title = _title(doc)
    if isinstance(title, dict) and title.get(TITLE_REF) in gone:
        title[TITLE_REF] = NO_REFERENCE
        said.append(f"form.title.{TITLE_REF} → {NO_REFERENCE} («ссылки нет»)")
    attributes = doc.get("attributes")
    bindings = attributes.get(BINDINGS) if isinstance(attributes, dict) else None
    members = bindings.get("items") if isinstance(bindings, dict) else None
    if isinstance(members, list):
        left = [b for b in members if b.get(BIND_ELEMENT) not in gone]
        if len(left) != len(members):
            said.append(f"привязок данных убрано {len(members) - len(left)}")
        bindings["items"] = left
    from . import ctxmenu
    return said + ctxmenu.forget(doc, gone)


def _context_menu_box(template, like, box):
    """Условия `context_menu=true`: шаблон командной панели и значок 24×24, как его ставит платформа."""
    from .ctxmenu import MENU_SIZE
    if template != "CommandBar" or like is not None:
        raise EditError("context_menu=true — панель контекстного меню: template=\"CommandBar\" без like")
    if not (isinstance(box, (list, tuple)) and len(box) == 4 and list(box[2:]) == [MENU_SIZE, MENU_SIZE]):
        raise EditError(f"панель контекстного меню на форме — значок {MENU_SIZE}×{MENU_SIZE}: box — (лево, верх, "
                        f"{MENU_SIZE}, {MENU_SIZE}); платформа ставит такую пустую панель с флагом «Вспомогательная»")


def _renumber(holder):
    """Номер на странице (`page_sequence`) СПЛОШНЯКОМ 0…N−1 в пределах каждой страницы родителя: так платформа
    пересчитывает его при удалении соседа. Порядок обхода (`tab_order`) платформа при этом не пересчитывает.
    """
    by_page = {}
    for item in (holder.get(ELEMENTS) or {}).get(ITEMS) or []:
        coords = item.get(COORDS) if isinstance(item, dict) else None
        if isinstance(coords, dict) and isinstance(coords.get(PAGE), int):
            by_page.setdefault(coords[PAGE], []).append(coords)
    for page, group in by_page.items():
        # Сортировка УСТОЙЧИВА: при равных номерах порядок остаётся тем, в каком элементы лежат в списке,
        # то есть добавленный (он последний) встаёт за своим двойником, а не перед ним.
        for order, coords in enumerate(sorted(group, key=lambda c: (c.get(PAGE_SEQUENCE) or 0))):
            coords[PAGE_SEQUENCE] = order


def _join(first, second):
    return f"{first}; {second}" if first else second


def _links_before(doc, node, name, choice_list, action_source, action_bar):
    """Ключи `choice_list`, `action_source` и `action_bar` у `add_element`: проверка ДО любой записи в форму и список выбора в узле (он ещё не
    в форме). Возвращает слова отчёта о списке выбора; связи с панелью и таблицей пишутся после постановки."""
    kind = node.get("type")
    if (action_source is not None) and kind != "CommandBar":
        raise EditError(f"action_source — источник действий КОМАНДНОЙ ПАНЕЛИ, а шаблон — {kind}; для таблицы источником служит action_bar (имя панели)")
    if (action_bar is not None) and kind != "TableBox":
        raise EditError(f"action_bar — имя командной панели, которая берёт действия ЭТОЙ ТАБЛИЦЫ, а шаблон — {kind}; для панели источник называет action_source (имя таблицы)")
    if action_source is not None:
        if not isinstance(action_source, str) or not action_source:
            raise EditError(f"action_source — имя табличного поля строкой, а пришло {action_source!r}")
        table = find_element(doc, action_source)
        if table.element.get("type") != "TableBox":
            raise EditError(f"action_source {action_source!r} — {table.element.get('type')}: панель берёт действия табличного поля; таблица должна уже стоять на форме "
                            "(поставьте её раньше либо назовите панель у самой таблицы: action_bar)")
    if action_bar is not None:
        if not isinstance(action_bar, str) or not action_bar:
            raise EditError(f"action_bar — имя командной панели строкой, а пришло {action_bar!r}")
        bar = find_element(doc, action_bar)
        if bar.element.get("type") != "CommandBar":
            raise EditError(f"action_bar {action_bar!r} — {bar.element.get('type')}, а источник действий бывает у командной панели (CommandBar)")
    if choice_list is None:
        return ""
    if kind != "ComboBox":
        raise EditError(f"choice_list — список выбора ПОЛЯ ВЫБОРА, а шаблон — {kind}")
    from .rowsa import _set_choice_list
    return _set_choice_list(Place(node, None, None, 0, name), name, choice_list)


def _diagrams_kinds():
    from .. import diagrams as _diagrams
    return _diagrams.KINDS


def _page_arg(doc, holder, page):
    """`page` числом (с нуля) — как есть; именем страницы родителя — номер этой страницы; прочее — отказ словами (раньше строка
    падала трассировкой `TypeError` на сравнении с числом). `holder` — имя родителя (`None`, `""`, `"форма"` — сама форма)."""
    if isinstance(page, int) and not isinstance(page, bool):
        return page
    from .pages import page_number
    if holder is None or (holder in ("", "форма") and not any(n == holder for n, _h in holders(doc))):
        target, who = _container(doc), "формы"
    else:
        target, who = holder_by_name(doc, holder), f"родителя {holder!r}"
    return page_number(target, page, who)


def _on_page(holder, page):
    """Блоки координат элементов родителя, лежащих на этой странице."""
    out = []
    for item in (holder.get(ELEMENTS) or {}).get(ITEMS) or []:
        coords = item.get(COORDS) if isinstance(item, dict) else None
        if isinstance(coords, dict) and coords.get(PAGE) == page:
            out.append(coords)
    return out


def _date_template(doc, template, like):
    """Шаблон нового поля, если он уже несёт описатель даты (узел из другой формы, `like`), — иначе `None`."""
    from .. import textgap
    node = template if isinstance(template, dict) else None
    if like is not None:
        try:
            node = find_element(doc, like).element
        except EditError:
            node = None
    return node if node is not None and textgap.date_composition(node) is not None else None


def _date_variant(doc, found, args):
    """Вариант поля даты без `box`, по порядку: (1) ширина умолчания, поле стоит; (2) ширина умолчания, привязки образца; (3) ширина и привязки
    образца. Предел раскладки (`limits`) сравнивается с вариантом (3): место под последней строкой сужает пределы по высоте у любого поля, а
    поле даты не должно сузить что-то сверх этого. Берётся первый вариант без нового сужения; сужают все — третий. Возвращает `(вариант, слова
    о выборе либо None)`.
    """
    import copy
    from .. import limits, place as _place

    def narrowing(mode):
        trial = copy.deepcopy(doc)
        try:
            add_element(trial, date_mode=mode, search=False, **copy.deepcopy(args))
        except EditError:
            return None
        return limits.unforgiven(limits.compare(doc, trial))
    base = narrowing("sample")
    allowed = {(c.axis, c.direction) for c in base or []}
    said, failed = [], True
    for mode in _place.DATE_ROLES[:-1]:
        bad = narrowing(mode)
        extra = None if bad is None else [c for c in bad if (c.axis, c.direction) not in allowed]
        if extra == []:
            return mode, (("поле даты: " + "; ".join(said) + f" — взят вариант «{_place.DATE_WORDS[mode]}»") if said else None)
        failed = failed and extra is None
        said.append(f"вариант «{_place.DATE_WORDS[mode]}» " + ("не вышел" if extra is None else limits.narrowed_words(extra)))
    if failed:  # место не нашлось ни в одном варианте: отказ первого варианта скажет почему
        return _place.DATE_ROLES[0], None
    return "sample", "поле даты: " + "; ".join(said) + f" — все варианты сужают растяжение формы, взят прежний: {_place.DATE_WORDS['sample']}"


def _cell_or_below(doc, args):
    """Поле встало в свободную клетку соседнего столбца (`place._free_cell`): не сузила ли клетка пределы раскладки больше, чем место под соседом. Возвращает слова,
    почему клетка отброшена, либо `None` (клетка остаётся). Место под соседом не вышло — клетка остаётся.
    """
    from .. import limits
    from ..layout import candidates

    def narrowed(cell):
        trial = candidates.fast_copy(doc)
        try:
            add_element(trial, search=False, cell=cell, **copy.deepcopy(args))
        except EditError:
            return None
        return {(c.axis, c.direction) for c in limits.unforgiven(limits.compare(doc, trial))}
    in_cell, below = narrowed(True), narrowed(False)
    if in_cell is None or below is None or not in_cell - below:
        return None
    axis, direction = sorted(in_cell - below)[0]
    return (f"клетка соседнего столбца отброшена: она сужает предел раскладки ({limits.layout.AXES[axis]}, {'сжатие' if direction < 0 else 'рост'}), а место под соседом не сужает; "
            "поле поставлено под соседом")


def add_element(doc, template=None, name=None, box=None, holder=None, page=0, caption=None,
                anchor=None, like=None, design=None, unverified=False, siblings=None, after=None,
                kind=None, grow=False, shrink=False, date_mode=None, search=True, cell=True, like_clean=False, context_menu=False, between=None,
                bar_for=None, buttons_alignment=None, attribute=None, columns=None, choice_list=None, action_source=None, action_bar=None, takes_growth=None, replace=False):
    """Элемент на форму или внутрь панели.

    Родитель — панель или форма, на которой лежит элемент.

    `template` — имя встроенного шаблона (`Label`, `Panel`, …) либо узел элемента из другой формы;
    `box` — `(лево, верх, ширина, высота)` в пикселях, как их показывает палитра. Координаты блока
    пишутся КРАЯМИ (право = лево + ширина), перевод делает операция.

    **Без `box` (`frm_codec.place`)** место берётся по соседям: следующей строкой блока после `after`
    (имя ВИДИМОГО соседа того же родителя и страницы) либо после последнего элемента ТОГО ЖЕ типа;
    столбец и размер — соседа того же типа, шаг строк — разность верхов двух последних СМЕЖНЫХ строк
    (между ними нет элемента другого типа, шаг не больше двух норм), иначе норма `pair_pitch` вида
    формы (`kind` — вид из `patterns.json`; нужен, когда шаг брать больше неоткуда, и для размера поля
    ввода без образца того же типа: умолчание — по основному реквизиту). Привязки — ПРАВИЛА того же
    соседа, смещения пересчитаны под место (роли не выводятся; правило образца к третьему элементу
    не переносится — граница встаёт у края родителя); `anchor` их переопределяет. Занятое место
    раздвигается (невидимые и другой столбец — тоже): элементы ниже сдвигаются на шаг вместе с `box`
    и правилами «к верху»; охватывающая место рамка группы растягивается низом. Элемент, который остаётся на месте (привязан к низу),
    наезд и выход за край родителя — отказ до записи с родом причины и выходами.
    **`grow=true`** — форма выше на шаг (только форма; нужен, если без него места нет; размер пишет
    `set_property` формы, привязанное к низу сдвигается вместе с ней); **`shrink=true`** — ужимается
    `TableBox` (минимум высоты 49) сверху на шаг либо, когда место занято рядом нижнего блока (привязан
    к низу обеими границами) под растянутой таблицей, поднимает блок на шаг и ужимает таблицу СНИЗУ
    (сторону выбирает операция, отчёт её называет); панель и прочие типы — отказ. Оба ключа — без
    `box`, взаимно исключают друг друга; по умолчанию ни один не включён, отчёт называет всё
    изменённое сверх «добавить поле». Новый элемент в порядке обхода встаёт следом за соседом.
    `after`, `kind`, `grow`, `shrink` с `box` — отказ: место уже названо.

    **Выбор привязок (`frm_codec.layout.candidates`).** Без `box` и без `anchor` после постановки привязки проверяются на модели раскладки
    при размерах окна меньше и больше проектного; если выравнивание с соседями расходится либо сужаются пределы, перебираются другие
    кандидаты (копия у других элементов столбца и строки, цепочка за надписью пары, роли) и берётся лучший; отчёт называет выбор и
    причины отказа от прочих. Никто не прошёл — отказ, форма не тронута. `search=false` отключает перебор. **Свободная клетка сетки:**
    если место под соседом занято (ряды пришлось бы раздвигать) либо его нет, а в соседнем столбце на строке соседа клетка пуста
    (последнее поле того столбца выше не больше чем на два шага), поле встаёт в эту клетку, форма не растёт, отчёт называет клетку;
    `cell=false` её не ищет. Явный `anchor` без `box`
    перебору не подлежит, но проверяется: отчёт предупреждает о наездах, цикле, мёртвых правилах и расхождении выравнивания.

    **Один дизайн формы (`frm_codec.design`):**

    * **версия общего блока оформления узла — версия формы**, иначе ОТКАЗ словами. Шаблоны — версии
      16; в форму 10, 13 или 15 встаёт шаблон, сведённый к версии формы по правилу корпуса
      (`frm_codec.old_versions`: отчёт называет версию и число подтверждений корпуса); где корпус
      сведения не подтверждает (табличное поле, список, табличный документ версии 10, вариант шаблона
      вне правила) — отказ словами с числом элементов вида в формах этой версии, снятый
      `unverified=True`: тогда в форме остаётся узел версии 16, отчёт говорит, что сделает
      платформа (смесь версий она переносит, а при пересохранении поднимает всю форму до своей);
    * **`like`** — имя элемента ТОЙ ЖЕ формы: новый элемент — его копия, вычищенная так же, как
      шаблон (`templates.clean_node`), и сверх того от всего, что связывает соседа с его данными,
      модулем и соседями (`_like_node`). Версия и оформление приходят от соседа — это дорога, которую
      называет отказ по версии;
    * **оформление встроенного шаблона — по соседям** того же типа и версии в форме: самое частое
      сочетание цветов, шрифта и рамки (`design.by_neighbours`); `design="template"` оставляет
      умолчания шаблона. Узел из другой формы несёт своё оформление и по соседям правится, только если
      попросили (`design="neighbors"`);
    * **вид поля ввода — «как в 8.2» или «как в 8.3» — свойство ФОРМЫ:** новое поле ввода берёт вид
      формы, у смешанной формы и у формы без полей ввода — вид конфигурации (`siblings` — свод
      соседних форм, `frm_json.py edit --siblings`), без соседних форм — вид большинства формы, иначе
      свой (`design.target_view`). Так при любом `design` и у узла из другой формы: стили 8.2 и 8.3 в
      одной форме не смешиваются.

    Операция ведёт сама пять вещей:

    * **индекс** — сквозной по форме, из счётчика выдачи (`_next_index`); счётчик поднимается;
    * **счётчик списка элементов** — поле JSON, `validate` его сверяет;
    * **номер на странице** (`page_sequence`) — следующий свободный В ПРЕДЕЛАХ страницы родителя;
    * **порядок обхода** (`tab_order`) — на единицу больше наибольшего на ТОЙ ЖЕ странице: новый элемент последний в обходе;
    * **встречные записи привязок** — у того, к чьей границе привязались, по ОБОИМ правилам: у соседа
      в его списке зависимых, у края родителя в списке блока раскладки (`anchors.sync`). Без них
      привязка в предприятии мертва.

    **`bar_for`** (`template="CommandBar"`, `frm_codec.edit.autobar`) — командная панель с автозаполнением: `"<имя таблицы>"` (вплотную над таблицей, источник
    действий — таблица), `"form_top"` (`ДействияФормы`) или `"form_bottom"` (`ОсновныеДействияФормы`); `name`, `box` и `anchor` выводятся и могут быть
    названы; `buttons_alignment` (`Left`/`Center`/`Right`) — выравнивание кнопок, умолчание — как у конструктора. Стандартные кнопки ставит платформа;
    `after`, `grow`, `shrink`, `like`, `date_mode`, `caption`, `context_menu`, `between` вместе с `bar_for` — отказ. **`replace=true`** (только `form_top` и
    `form_bottom`) — прежняя панель того же места убирается (`remove_element`, слова в отчёте, её кнопки уходят вместе с ней) и на её месте встаёт новая: одна операция
    вместо пары «убрать заготовку — поставить панель»; без `replace` вторая панель того же места — отказ.

    **Ключи одного вызова** (порядок операций в списке не должен заставлять писать вторую):

    * `choice_list` (`template="ComboBox"`) — список выбора поля выбора сразу при постановке; значение то же, что у `set_property` с `choice_list`
      (строки или `{"value": …, "presentation": …}`); у другого вида — отказ;
    * `action_source` (`template="CommandBar"`) — имя табличного поля, чьи действия панель берёт сама (`set_action_source`); таблица уже стоит на форме;
    * `action_bar` (`template="TableBox"`) — имя уже стоящей командной панели, источником действий которой становится эта таблица (`set_action_source`
      панели на таблицу). Один из двух ключей закрывает порядок «таблица после панели» и «панель после таблицы»; свою панель с автозаполнением над таблицей
      ставит `bar_for`.

    **`template="TreeBox"`, `attribute`, `columns`** (`frm_codec.edit.valuesrc`) — табличное поле на таблицу или дерево значений одним вызовом. `TreeBox` — поле
    дерева значений (шаблон `TableBox`, приведённый к дереву: описатель, источник данных, биты слова флагов, «Иерархия» у первой колонки); `attribute` —
    реквизит формы типа `ValueTable` либо `ValueTree`, к которому поле привязывается (`bind`; поле само приводится к типу реквизита); `columns` — колонки
    (`add_columns`: `name`, `header`, `type`, `width`, `align`, `header_align`, `format`, `hierarchy`), безымянная колонка шаблона при этом снимается. `type` —
    тип колонки (`{"kind": "N", "digits": 15, "fraction": 3}`, `S`, `D`, `B`): платформа создаёт колонки по записи формы, код их заново не добавляет. Панель над таблицей — отдельным вызовом `bar_for`.

    **`context_menu=true`** — панель контекстного меню: `template="CommandBar"` и `box` размером 24×24 (значок меню на форме);
    панель невидимая (Видимость ☐), «Вспомогательная» ☑, как их заводят в конфигураторе.
    Шаблон панели уже вспомогательный, как у панели, которую вставляет платформа; назначает меню элементу
    `set_property` с именем `context_menu`.

    `anchor` — как привязать границы:

    * `self` (умолчание) — низ к своему верху, право к своему леву, флагов нет. Такой элемент при
      растяжении окна не сдвигается, а АвтоПравила формы с ☑ ставят ему свои привязки при записи формы
      (пересчёт запускает любое изменение геометрии на странице; `AUTO_RULES_SELF_WORDS`);
    * `form` — ПРОПОРЦИОНАЛЬНАЯ пара: низ — `F.t+низ | F.b+(низ − высота родителя)`, право — то же по
      ширине, верх и лево без правила, флагов нет (`anchors.FORM_WORDS`). Платформа файл с этой
      парой (без записей) открывает, но при пересохранении сводит её к одиночным `F.b-8`/`F.r-30` и
      дописывает строки родителя; пару С записями предприятию не показывали (вариант
      `add_element/form-pair`, пометка в отчёте). Края — родителя: у вложенного элемента объект 0 —
      край панели; родитель без списков блока раскладки — отказ, как у ролей;
    * роль `set_anchors` — строкой (`stretch`, `proportional`, `center` — обе оси; `left`, `right` —
      горизонталь, `top`, `bottom` — вертикаль, вторая ось «к себе») или объектом `{"h": …, "v": …}`:
      ручной стиль с флагами, как у `set_anchors`; значение оси может быть и копией правил образца
      `{"as": "<имя>"[, "with": {…}]}` (`anchors._rules_as`, `docs/anchors.md`);
      значение оси может быть и `{"splitter": "<имя разделителя>"}` — граница, обращённая к разделителю.

    **`between=["<слева или сверху>", "<справа или снизу>"]`** (только `template="Splitter"`, `frm_codec.edit.splitter`) — разделитель в зазоре
    между двумя соседями: место (зазор целиком, вдоль — протяжение обоих), привязки соседей (граница к стороне разделителя) и самого
    разделителя (роль `slide` по оси движения, повтор соседей по поперечной) выводятся по строению корпуса; `box`, `after`, `kind`, `grow`,
    `shrink`, `like`, `date_mode`, `context_menu`, `caption` вместе с `between` — отказ; `anchor` задаёт оси, которые не выводятся.
    **`takes_growth`** (`"both"` — умолчание, `"before"`, `"after"`; только с `between`) — кто из соседей берёт прирост окна по оси разделителя:
    `both` — оба, прирост делится долей (роль `slide`), `before` — левый (верхний) сосед, правый (нижний) держит размер, `after` — наоборот;
    вместе с `anchor` на той же оси — отказ. Панели таблиц (`bar_for`) соседей разделитель привязывает вслед за таблицами (`edit.splitter`).
    """
    from .. import templates as _templates
    if takes_growth is not None and between is None:
        raise EditError("takes_growth — кто из соседей берёт прирост окна — задают только разделителю между двумя элементами (between)")
    page = _page_arg(doc, holder, page)
    if template == "TreeBox" or attribute is not None or columns is not None:  # табличное поле на таблицу/дерево значений: поле → привязка → колонки (`edit.valuesrc`)
        from . import valuesrc as _valuesrc
        args = dict(template=template, name=name, box=box, holder=holder, page=page, caption=caption, anchor=anchor, like=like, design=design,
                    unverified=unverified, siblings=siblings, after=after, kind=kind, grow=grow, shrink=shrink, date_mode=date_mode, search=search,
                    cell=cell, like_clean=like_clean, context_menu=context_menu, between=between, bar_for=bar_for, buttons_alignment=buttons_alignment,
                    choice_list=choice_list, action_source=action_source, action_bar=action_bar)
        return _valuesrc.add_table(doc, add_element, args, attribute, columns, template == "TreeBox")
    if replace and bar_for is None:
        raise EditError("replace — только с bar_for (панель формы): он заменяет уже стоящую верхнюю или нижнюю панель формы новой")
    if bar_for is not None:  # командная панель с автозаполнением: место, привязки, узел и источник действий выводятся из назначения (`edit.autobar`)
        from . import autobar as _autobar
        args, said_bar, source = _autobar.prepare(doc, bar_for, dict(
            template=template, name=name, box=box, holder=holder, page=page, caption=caption, anchor=anchor, like=like, design=design, kind=kind,
            grow=grow, shrink=shrink, date_mode=date_mode, context_menu=context_menu, between=between, after=after, replace=replace), buttons_alignment)
        said = add_element(doc, unverified=unverified, siblings=siblings, search=search, cell=cell, like_clean=like_clean, **args)
        if source is not None:
            said += "; " + set_action_source(doc, args["name"], source)
        return said + "; " + said_bar
    if buttons_alignment is not None:
        raise EditError("buttons_alignment при постановке — только с bar_for (панель с автозаполнением); у готовой панели выравнивание кнопок — "
                        "set_property name=buttons_alignment")
    if name is None:
        raise EditError("элементу нужно имя (name)")
    if between is not None:  # разделитель в зазоре между двумя элементами: место и привязки выводятся из соседей (`edit.splitter`)
        from . import splitter as _splitter
        return _splitter.add_between(doc, between, add_element, template=template, name=name, holder=holder, page=page, anchor=anchor,
                                     unverified=unverified, takes_growth=takes_growth, others=dict(box=box, after=after, kind=kind, grow=grow, shrink=shrink, like=like,
                                                                       date_mode=date_mode, context_menu=context_menu, caption=caption))
    if context_menu:
        _context_menu_box(template, like, box)
    if box is not None and (after is not None or kind is not None or grow or shrink):
        raise EditError("after, kind, grow и shrink называют, откуда взять место по соседям и как его освободить, а box "
                        "место уже назвал: уберите box либо after/kind/grow/shrink")
    if box is not None and anchor is None:
        anchor = "self"
    date_note = None
    if date_mode is None and box is None and anchor is None:
        found = _date_template(doc, template, like)
        if found is not None:
            date_mode, date_note = _date_variant(doc, found, dict(
                template=template, name=name, holder=holder, page=page, caption=caption, like=like, design=design, unverified=unverified,
                siblings=siblings, after=after, kind=kind, grow=grow, shrink=shrink))
    if design not in (None, *DESIGN_WAYS):
        raise EditError(f"design — {' или '.join(repr(w) for w in DESIGN_WAYS)} (оформление по "
                        f"соседям того же типа либо умолчания шаблона), а не {design!r}")
    if name in element_names(doc):
        raise EditError(f"элемент {name!r} в форме уже есть; имя ищут и билет, и генератор, "
                        "и найдут они один из двойников")
    said_like = None
    said_old = None
    if like is not None:
        if isinstance(template, dict):
            raise EditError("like и узел из другой формы вместе не бывают: like — это «как вот "
                            "этот элемент ЭТОЙ формы», а узел приносит своё. Уберите одно")
        if design is not None:
            raise EditError("у like оформление — соседа, и design к нему не относится: design "
                            "выбирает оформление ШАБЛОНА (по соседям или умолчания)")
        node, said_like = _like_node(doc, like, template, name, caption, unverified,
                                     _siblings_pool(siblings), clean=like_clean)
    elif template is None:
        raise EditError("откуда взять элемент: template (имя шаблона или узел из другой формы) "
                        "либо like (имя элемента этой формы, по образцу которого)")
    else:
        if isinstance(template, str):
            node = _templates.element(template)
            node, said_old = _old_version_node(doc, template, node, unverified)
        else:
            # Узел из другой формы — фрагмент документа уровня 1: прежние имена краёв блока (`width`/`height`)
            # у донора — отказ словами.
            try:
                node = copy.deepcopy(_typed.refuse_old_coords(template))
            except _typed.TypedError as e:
                raise EditError(f"шаблон-узел: {e}") from None
    if not isinstance(node, dict) or COORDS not in node:
        raise EditError("шаблон — это узел элемента с блоком координат; "
                        f"пришло {type(node).__name__}")
    nested = (node.get(ELEMENTS) or {}).get(ITEMS)
    if nested:
        raise EditError("узел с вложенными элементами шаблоном быть не может: их индексы "
                        "сквозные по ДОНОРУ, и на новой форме они займут чужие номера. "
                        "Положите пустой узел, а вложенные — своими вызовами add_element")
    if context_menu:
        node[COORDS]["visible"] = False  # панель-меню невидима на форме: её выбирают как контекстное меню
    if caption is not None:
        caption_slot(node, name)  # заголовок сверяется ДО раздвигания рядов: отказ позже оставил бы форму сдвинутой
    said_version = _version_check(doc, _design.node_versions(node), "add_element", unverified,
                                  kind=node.get("type"), like=like)
    whose = "шаблона" if isinstance(template, str) else "узла из другой формы"
    pool = _siblings_pool(siblings)
    if like is not None:
        said_design = None
    elif not isinstance(template, str) and design != "neighbors":
        said_design = ("оформление — донора (узел из другой формы): по соседям его не правят, "
                       "если не просили design=neighbors")
        view = _design.apply_view(doc, node, whose, pool)
        said_design += f"; {view}" if view else ""
    elif design == "template":
        said_design = "оформление — умолчания шаблона (design=template)"
        view = _design.apply_view(doc, node, whose, pool)
        said_design += f"; {view}" if view else ""
    else:
        said_design = _design.by_neighbours(doc, node, whose, pool)
    holder_node = holder_by_name(doc, holder)
    items = elements_of(holder_node)
    pages = pages_count(holder_node)
    if pages is None and page:
        raise EditError(f"у родителя {holder!r} {no_pages_words(holder_node)} — "
                        "класть элемент можно только на страницу 0")
    if pages is not None and not 0 <= page < pages:
        # Страница без родителя — страница САМОЙ формы, с родителем — страница панели: номер один и тот же,
        # а заводят их разные операции, и отказ называет нужную.
        where, road = (("у формы", "страницу самой формы заводит add_form_page")
                       if holder is None else
                       (f"у родителя {holder!r}", "страницу панели заводит add_page"))
        raise EditError(f"страницы {page} {where} нет: страниц {pages} (счёт с нуля; {road}) "
                        "— такой элемент лёг бы на страницу, которой нет, и в конструкторе его "
                        "не видно")
    heads = _issue_heads(node)
    heads += _shared_button_ids(doc, node)  # до вставки: свои кнопки узла не в счёт
    placed = None
    watched = box is None and search  # привязки проверяются на модели раскладки; до операции — копия формы для сравнения
    if watched:
        from .. import layout as _layout
        from ..layout import candidates as _candidates
    snapshot = _candidates.fast_copy(doc) if watched else None
    explicit = anchor is not None
    if box is None:
        from .. import place as _place
        placed = _place.plan(doc, holder_node, holder, page, node, after, kind, anchor, unverified, grow, shrink, caption, date_mode or "stand", cell)
        if watched and cell and _place.FREE_CELL_MARK in placed.words:
            below = _cell_or_below(doc, dict(template=template, name=name, holder=holder, page=page, caption=caption, like=like, design=design, unverified=unverified,
                                             siblings=siblings, after=after, kind=kind, grow=grow, shrink=shrink, date_mode=date_mode,
                                             like_clean=like_clean))
            if below is not None:
                placed = _place.plan(doc, holder_node, holder, page, node, after, kind, anchor, unverified, grow, shrink, caption, date_mode or "stand", False)
                placed.words += f"; {below}"
        box = placed.box
        if placed.rules is None:
            anchor = placed.anchor  # явный `anchor` либо «к себе»: образца того же типа нет
    index = _next_index(doc)
    left, top, width, height = box
    node[INDEX] = index
    node.setdefault(NAME_BLOCK, {})[NAME] = name
    said_links = _links_before(doc, node, name, choice_list, action_source, action_bar)
    said_title = ""
    if isinstance(template, str) and like is None and node.get("type") in _diagrams_kinds():
        from .. import diagrams as _diagrams
        said_title = _diagrams.name_the_title(node, name)
    coords = _templates.clean_coords(node[COORDS])
    coords.update({X: left, Y: top, WIDTH: left + width, HEIGHT: top + height})
    # Привязки считаются ДО вставки: отказ по роли (соседа нет, края родителя взять неоткуда) не должен
    # оставить форму с наполовину вставленным элементом.
    if placed is not None and placed.rules is not None:
        names = {it.get(INDEX): (it.get(NAME_BLOCK) or {}).get(NAME) for it in items if isinstance(it, dict)}
        names[index] = name
        said_anchor = "правила образца: " + placed.write_rules(coords, index, names)
    else:
        said_anchor = _set_anchors(coords, index, width, height, anchor, doc, holder_node, page,
                                   unverified, name)
    if placed is not None:
        placed.shift()  # после всех отказов: форма до этой строки не тронута
    coords[PAGE] = page
    # Номер на странице — последний (новый элемент лежит в списке последним); порядок обхода — наибольший на
    # странице плюс один, как его платформа даёт новому элементу: Tab идёт к нему последним, переставляет его
    # `set_property tab_order`.
    coords[PAGE_SEQUENCE] = len(_on_page(holder_node, page))
    coords[TAB_ORDER] = max(
        [c.get(TAB_ORDER) or 0 for c in _on_page(holder_node, page)] + [0]) + 1
    node[COORDS] = coords
    items.append(node)
    holder_node[ELEMENTS][COUNT] = len(items)
    if action_source is not None:
        said_links = _join(said_links, set_action_source(doc, name, action_source))
    if action_bar is not None:
        said_links = _join(said_links, set_action_source(doc, action_bar, name))
    # Пересчёт номера на странице — ОБЕИМИ операциями: «сколько уже лежит» равно «следующий свободный», только
    # пока нумерация сплошная, а редактор правит и то, что собрал не он.
    _renumber(holder_node)
    title = _title(doc)
    if isinstance(title, dict) and isinstance(title.get(LAST_INDEX), int):
        title[LAST_INDEX] = max(title[LAST_INDEX], index)
    from .. import anchors as _anchors
    stale, _put = _anchors.sync(doc, index)
    if caption is not None:
        set_caption(doc, name, caption)
    if _find_pages(node) is not None:
        _fit_guides(node, width, height)
    chosen_words = ""
    if watched:
        from .. import textgap as _textgap
        fixed_width = _textgap.date_composition(node) is not None and date_mode != "sample"
        try:
            if explicit:
                chosen_words = _candidates.warn(snapshot, doc, name)
            elif placed is not None and placed.rules is not None:
                chosen_words = _candidates.refine(snapshot, doc, name, unverified,
                                                  (_layout.STANDS, _layout.MOVES) if fixed_width else None, sample=placed.sample) or ""
        except EditError:
            doc.clear()
            doc.update(snapshot)  # отказ перебора: форма остаётся прежней
            raise
    tail = f"; вычищено висячих записей на индекс {index}: {stale}" if stale else ""
    tail += f"; {placed.words}" if placed is not None else ""
    tail += f"; {chosen_words}" if chosen_words else ""
    tail += f"; {date_note}" if date_note else ""
    tail += f"; {said_anchor}" if said_anchor else ""
    if (anchor == "self" or (placed is not None and placed.is_self_shape())) and holder is None and _auto_rules_on(doc):
        tail += f"; {AUTO_RULES_SELF_WORDS}"
    tail += "".join(f"; {said}" for said in heads)
    if holder is None and node.get("type") == "CommandBar" and not page:
        from .. import guides as _guides
        said_guides = _guides.fit_panel(doc, node)
        tail += f"; {said_guides}" if said_guides else ""
    from .. import diagrams as _diagrams
    said_body = _diagrams.mixed_note(_design.elements(doc)) if node.get("type") in _diagrams.KINDS else None
    tail += "".join(f"; {said}" for said in (said_old, said_like, said_design, said_version, said_body, said_title, said_links) if said)
    if isinstance(template, str) and template in TYPE_NOTES:
        tail += f"; {TYPE_NOTES[template]}"
    if holder is None and page:
        tail += _on_corpus("add_element/form-page", f"страница {page} самой формы",
                           CORPUS_FORM_PAGES["элементов на страницах ≥ 1"],
                           counted="элементов верхнего уровня на страницах формы после первой")
    return (f"{holder or 'форма'}: элемент {name!r} ({node.get('type')}), индекс {index}, "
            f"страница {page}, порядок обхода {coords[TAB_ORDER]}{tail}")


# Оговорки к элементам, которых платформа сама не связывает с другими частями формы. Элемент ставится без этой связи.
DATA_FIELD_NOTE = ("элемент поставлен без данных: реквизит формы заводит add_attribute (у индикатора и полосы — число, у поля "
                   "календаря — дата), привязку — bind")
TYPE_NOTES = {
    "ProgressBar": DATA_FIELD_NOTE,
    "TrackBar": DATA_FIELD_NOTE,
    "CalendarBox": DATA_FIELD_NOTE,
    **{kind: ("элемент поставлен с умолчаниями панели элементов: реквизита формы нет; данные диаграммы задаёт код модуля")
       for kind in ("Chart", "GanttChart", "Dendrogram", "PivotChart")},
    "Splitter": ("разделитель поставлен сам по себе, соседей с ним операция не связывает: у формы, где разделитель работает, "
                 "граница каждого соседа привязана к его стороне (set_anchors у соседа с любой стороны — роль "
                 "{\"splitter\": \"<имя разделителя>\"}; разделитель между двумя элементами целиком — add_element с between)"),
}


# АвтоПравила у элемента `self`: платформа дописывает привязку, когда ПЕРЕСЧИТЫВАЕТ привязки страницы формы. Пересчёт
# запускает любое изменение геометрии на странице (сдвиг мышью, вставка, копирование элемента — и с возвратом на место) и не
# запускают правка свойства элемента, просмотр палитры, правка заголовка формы. Пересчитываются все элементы страницы 0 без
# «Ручной привязки»; внутри панелей и на страницах формы после первой — нет. Конфигуратор показывает вычисленную привязку в
# диалоге «Установить привязки…» ДО всяких правок, в файл она попадает при пересчёте.
AUTO_RULES_SELF_WORDS = (
    "АвтоПравила формы ☑ пересчитывают привязки элементов страницы 0 без флага «Ручная привязка», когда в конфигураторе меняют "
    "геометрию на странице (сдвиг, вставка или копирование элемента, даже с возвратом на место); правка свойства элемента, "
    "просмотр палитры и правка заголовка формы пересчёт не запускают. Привязка «к себе» без флага переживёт сохранение, пока "
    "геометрию на странице не меняли; пересчёт запишет ей низ — к низу нижнего соседа, смещение — расстояние до него, с "
    "встречной записью. Устойчивая запись — роль с флагом; конфигуратор показывает вычисленную привязку в диалоге «Установить "
    "привязки…» до записи; запись редактора этого не ведёт")


def _auto_rules_on(doc):
    """АвтоПравила формы ☑ — иначе платформе нечем привязывать (флаг не 0)."""
    block = _layout_block(_container(doc), need=False) if isinstance(doc, dict) else None
    return isinstance(block, dict) and block.get("auto_rules") is not False


def _siblings_pool(siblings):
    """Свод соседних форм для вида конфигурации (`design.pool`) либо `None`.

    Соседей читает `frm_json.py edit --siblings <каталог>` — один раз на перечень, исключив саму
    форму, — и подаёт их операциям, у которых параметр есть (`apply(siblings=…)`). В перечне операций
    каталог не пишут: операция не знает, где лежит форма.
    """
    if siblings is None or isinstance(siblings, dict):
        return siblings
    raise EditError("siblings в перечне операций не пишут: соседние формы читает frm_json.py "
                    "edit --siblings <каталог выгрузки> — один раз на перечень и без самой формы "
                    f"(пришло {siblings!r})")


# Оговорка о виде ВЛОЖЕННЫХ полей колонок — одна на поля ввода и поля выбора: вложенные поля формы,
# приведённой к 8.2, и контрольной 8.3 в предприятии не различаются ни видом, ни поведением при
# вводе (редактор ячейки рисуется без рамки, кнопка поля выбора в ячейке одинакова).
NESTED_VIEW_WORDS = (
    "вид вложенного поля колонки на экране не отличим ни при стиле формы, заданном в конфигурации, ни при "
    "«Авто» и не различим по поведению при вводе (кнопка выбора в покое не видна у обоих видов, "
    "«▼» поля выбора — только при редактировании, F4 открывает калькулятор у обоих): поле пишется "
    "ради согласия с видом формы, проверить глазами нечем")


def set_view(doc, view=None, siblings=None):
    """Вся форма — в ОДНОМ виде: «как в 8.2» или «как в 8.3».

    Стили 8.2 и 8.3 в одной форме не смешиваются, вид — тот, что преимущественно используется в
    конфигурации. Вид поля ввода решает позиция 16 общего блока (`view` карты): 1 — «как в 8.2», 0 и
    2 — «как в 8.3». Операция ставит его ВСЕМ полям ввода формы другого вида — кодом
    `design.VIEW_WRITTEN` (1 у 8.2; 0 у 8.3 — так новое поле пишет конфигуратор 8.3.27), позицию 17
    обнуляет, если стояла 1 (17 = 1 бывает только при 16 = 2), а `u43` пишет правилом платформы
    (`design.u43_rule`). Поля того же вида не трогаются: 0 и 2 — один вид.

    `view` — «8.2» или «8.3»; не назван — вид конфигурации (`siblings`, свод соседних форм:
    `frm_json.py edit --siblings <каталог>`), вид большинства полей ввода версии 16 соседних форм.

    **Вложенные поля ввода колонок приводятся тоже — с оговоркой.** Позицию 16 они несут, и у соседей
    она разная (`design.CORPUS_NESTED_VIEWS`), но вид вложенного поля на экране не отличим, и отчёт
    называет их отдельно (`NESTED_VIEW_WORDS`). Поля выбора не трогаются: их вид не проверялся, —
    и отчёт называет их, свои и вложенные в колонки, с позицией 16, какая осталась. **Поля ввода другой
    версии общего блока, чем форма, не трогаются и называются.**

    Отказ — форма не версии 16: вид там задаёт поколение (у версии 15 позиция 16 — 1 у почти всех
    полей, у 10 и 13 позиции нет), и вид не проверялся; дорога — пересохранение
    (`design.resave_words`).
    """
    version = _design.form_version(doc)
    if version != 16:
        fifteen = _design.CORPUS_TEXTBOX_U16_U43[15]
        raise EditError(
            f"вид 8.2/8.3 ставят форме версии общего блока 16, а у этой — {version}: у версии 10 "
            f"и 13 позиции вида нет вовсе, у 15 она 1 у {_design._n(fifteen[(1, 1)])} полей "
            f"ввода снимка из {_design._n(sum(fifteen.values()))}, — то есть вид там задаёт "
            f"поколение платформы, сохранявшей форму последней; {_design.resave_words(version)}")
    if view is not None and view not in _design.VIEWS:
        raise EditError(f"view — {' или '.join(repr(v) for v in _design.VIEWS)} (вид «как в "
                        f"8.2» или «как в 8.3»), а не {view!r}")
    pool = _siblings_pool(siblings)
    if view is None:
        if pool is None:
            raise EditError("вид не назван: view — «8.2» или «8.3», либо соседние формы той же "
                            "конфигурации (frm_json.py edit --siblings <каталог>) — тогда вид "
                            "конфигурации, вид большинства полей ввода версии 16 соседних форм")
        view, theirs = _design.config_view(pool)
        if view is None:
            raise EditError(f"{_design._config_words(pool, 16, None, theirs)} — назовите view "
                            "(«8.2» или «8.3»)")
        source = f"вид конфигурации — {_design._config_words(pool, 16, view, theirs)}"
    else:
        source = "назван"
    own, nested, alien, total, nested_combos = [], [], [], 0, []
    for name, element in _design.elements(doc):
        block = _design.block_of(element) if element.get("type") == "TextBox" else None
        if block is not None and _design.version_of(block) != version:
            alien.append(f"{name} — {_design.version_of(block)}")
        elif _design.class_of(block) is not None:
            total += 1
            words = _view_words(block, _design._textbox_props(element), view)
            if words:
                own.append(f"{name} ({words})")
        for column, kind, block in _design.nested_blocks(element):
            if kind == "ComboBox":
                # Вложенные ПОЛЯ ВЫБОРА колонок операция не приводит (вид поля выбора не проверялся) — и называет
                # их, как свои поля выбора формы.
                nested_combos.append(f"{name}/{column} (позиция 16 — "
                                     f"{_design._raw_view(block) or 'нет'})")
            if kind != "TextBox":
                continue
            if _design.version_of(block) != version:
                alien.append(f"{name}/{column} — {_design.version_of(block)}")
            elif _design.class_of(block) is not None:
                words = _view_words(block, _design._parent_of(element, block), view)
                if words:
                    nested.append(f"{name}/{column} ({words})")
    combos = [name for name, element in _design.elements(doc)
              if element.get("type") == "ComboBox" and _design.block_of(element) is not None]
    said = [f"вид формы — {view} ({source})"]
    if not total:
        said.append("полей ввода в форме нет")
    elif own:
        said.append(f"поля ввода приведены к виду {view}: {len(own)} из {total} — "
                    + ", ".join(own))
    else:
        said.append(f"все {total} полей ввода уже вида {view} — не тронуты")
    if nested:
        said.append(f"вложенные поля ввода колонок приведены к виду {view}: {len(nested)} — "
                    + ", ".join(nested) + f" ({NESTED_VIEW_WORDS})")
    if alien:
        said.append(f"поля ввода другой версии общего блока, чем форма, не тронуты "
                    f"({len(alien)}: {', '.join(alien)}): {_design.UNMEASURED}")
    if combos:
        said.append(f"поля выбора не тронуты ({len(combos)}: {', '.join(map(str, combos[:5]))}"
                    f"{' …' if len(combos) > 5 else ''}): {_design.VIEW_NOTES['ComboBox']}")
    if nested_combos:
        said.append(f"вложенные поля выбора колонок не тронуты — остались прежнего вида "
                    f"({len(nested_combos)}: {', '.join(nested_combos[:5])}"
                    f"{' …' if len(nested_combos) > 5 else ''}): вид поля выбора — тройка "
                    "позиций (16, 17 и спутник `L1+17`), и тройкой он не приводится — "
                    f"{_design.VIEW_NOTES['ComboBox']}; "
                    + ("та же оговорка о вложенных полях, что выше" if nested
                       else NESTED_VIEW_WORDS))
    said.append(_design.VIEW_NOTES["TextBox"])
    return "; ".join(said)


def _view_words(block, props_block, view):
    """Вид одному полю ввода: слова «view As83 → As82, u43 2 → 1» или пусто — вид тот же."""
    before = {"block": dict(block), "u43": (props_block or {}).get(_design.TEXTBOX_U43)}
    changed = _design.put_class(block, view)
    if not changed:
        return ""
    changed += _design.put_u43(block, props_block)
    keys = list(block)
    out = []
    for name in changed:
        if name == _design.TEXTBOX_U43:
            out.append(f"u43 {before['u43']} → {props_block[_design.TEXTBOX_U43]}")
        else:
            at = _design.VIEW_POSITION if name == _design.VIEW else _design.HIDDEN[1]
            out.append(f"{name} {_short(before['block'][keys[at]])} → {_short(block[keys[at]])}")
    return ", ".join(out)


DESIGN_WAYS = ("neighbors", "template")
# Виды, которые ставятся по образцу соседа (`like`), — те, у кого есть шаблон, кроме табличного
# поля: у него колонки (имя, Данные, заголовок, тип, вложенный элемент со своими обработчиками и
# связями), и что из этого чистить, не проверялось. Прочие виды шаблона не имеют — их приносят узлом
# из другой формы.
LIKE_KINDS = ("Label", "TextBox", "CheckBox", "Button", "GroupBox", "Panel", "CommandBar")
# Что у соседей одного типа в одной форме ЛИЧНОЕ — числа отчёта `_like_node` и SKILL.md.
CORPUS_LIKE_PERSONAL = {
    ("Label", "caption"): (2849, 3166), ("Label", "events"): (354, 3166),
    ("Label", "tool_tip"): (226, 3166),
    ("TextBox", "pattern"): (2454, 2693), ("TextBox", "events"): (2142, 2693),
    ("TextBox", "tool_tip"): (2339, 2693),
    ("Button", "caption"): (1788, 1813), ("Button", "events"): (1803, 1813),
    ("Button", "tool_tip"): (1203, 1813),
    ("CheckBox", "caption"): (484, 495), ("CheckBox", "events"): (338, 495),
    ("CheckBox", "tool_tip"): (345, 495),
    ("GroupBox", "caption"): (628, 658),
    ("CommandBar", "action_source"): (890, 2580),
    ("TableBox", "columns"): (615, 616),
}


def old_version_refusal(doc, version, template, kind):
    """Почему шаблон `template` вида `kind` не встаёт в форму старой версии общего блока (10, 13, 15) — слова без хвоста про `unverified`; `None` — встаёт.

    Одно место для `add_element`, `change_type` и досье: корпус форм сведения шаблона версии 16 к этой версии не подтверждает (вид без образцов,
    табличное поле, диаграмма, вариант шаблона вне правила). Форма версии 16 и версия вне правила — `None`."""
    from .. import old_versions as _old, diagrams as _diagrams
    if version not in _old.VERSIONS:
        return None
    if kind in _old.UNSEEN_KINDS:
        return _old.unseen_refusal(kind, version)
    if not _old.enabled():
        return None
    if kind == "TableBox":
        return _old.table_refusal(doc, version, template)
    if kind in _diagrams.KINDS:  # тело диаграммы записано своей версией, общего блока оформления у шаблона нет
        return _diagrams.old_form_refusal(kind, version)
    if kind not in _old.table()["templates"]:
        return None  # у шаблона нет общего блока (табличный документ): версию формы он не несёт, сводить нечего
    return _old.refusal(kind, version, template)


def _old_version_node(doc, template, node, unverified):
    """Шаблон версии 16 для формы старой версии общего блока (10, 13, 15): `(узел, фраза отчёта)`. Узел сведён к версии формы по правилу корпуса
    (`old_versions`), смеси версий нет. Там, где корпус сведения не подтверждает, — ОТКАЗ словами (`old_version_refusal`) с числом элементов вида в
    формах этой версии; `unverified` оставляет шаблон 16 как раньше, и смесь версий называет `_version_check`. Форма версии 16 и версия, которой
    нет в правиле, — узел без изменений."""
    from .. import old_versions as _old, diagrams as _diagrams
    version = _design.form_version(doc)
    kind = node.get("type") if isinstance(node, dict) else None
    reason = old_version_refusal(doc, version, template, kind) if isinstance(node, dict) else None
    if reason is not None:
        if not unverified:
            if kind in _old.UNSEEN_KINDS:
                raise EditError(reason + ". Позвать всё же можно — unverified=True (узел версии 16 встанет в форму версии "
                                f"{version} как есть: при первом сохранении в конфигураторе форма целиком уйдёт в версию платформы)")
            if kind in _diagrams.KINDS:
                raise EditError(reason + ". Позвать всё же можно — unverified=True (шаблон версии "
                                f"{_diagrams.TEMPLATE_BODY_VERSION} в форме версии {version}: при первом сохранении в конфигураторе "
                                "форма целиком уйдёт в версию платформы)")
            raise EditError(reason + ". Позвать всё же можно — unverified=True (шаблон 16 в форме версии "
                            f"{version}: при первом сохранении в конфигураторе форма целиком уйдёт в версию платформы)")
        if kind in _old.UNSEEN_KINDS:
            return node, f"узел версии 16 в форме версии {version} (unverified): {reason}"
        return node, None
    if version not in _old.VERSIONS or not isinstance(node, dict) or not _old.enabled():
        return node, None
    if kind == "TableBox":
        return _old.reduce_table(doc, node, template, version)
    if kind in _diagrams.KINDS or kind not in _old.table()["templates"]:
        return node, None  # диаграмма и шаблон без общего блока (табличный документ): версию формы они не несут, сводить нечего
    return _old.reduce_template(node, kind, version)


def _version_check(doc, found, op, unverified, kind=None, like=None):
    """Версии общих блоков нового узла (`found` — `[(что, версия)]`) против версии формы: `None`, фраза
    отчёта или ОТКАЗ.

    Одно место на все операции, вставляющие узел с общим блоком (`add_element`,
    `set_column_control`). У кнопки панели, страницы и меню общего блока нет, а колонку `add_column`
    копирует с соседки той же формы.
    """
    version = _design.form_version(doc)
    if version is None:
        return ("версию общего блока формы прочесть не из чего (блок контейнера не разобран) — "
                "сверки версий нет")
    alien = [(what, v) for what, v in found if v != version]
    if not alien:
        return None
    theirs = ", ".join(f"{what} — {v}" for what, v in alien)
    if unverified:
        return (f"смесь версий собрана по unverified: у узла {theirs}, у формы {version}. "
                f"Смешанных форм корпус не держит ни одной; {_design.X19C}, — то есть при "
                "первом сохранении в конфигураторе форма целиком уйдёт в версию платформы")
    road = ""
    if op == "add_element":
        same = [name for name, element in _design.elements(doc)
                if element.get("type") == kind and name]
        if kind not in LIKE_KINDS:
            road = (f" Дорога — узел вида {kind} из формы той же версии (template — узел): "
                    f"по образцу соседа (like) ставятся {', '.join(LIKE_KINDS)}.")
        elif same:
            road = (f" Дорога — like: элемент по образцу соседа того же вида (в форме есть "
                    f"{', '.join(same[:5])}{' …' if len(same) > 5 else ''}), версия и оформление "
                    "придут от него; либо узел из формы той же версии (template — узел).")
        else:
            road = (f" Соседей вида {kind} в форме нет, и like не к кому; дорога — узел из формы "
                    "той же версии (template — узел).")
        if like is not None:
            road = (" Сосед like сам другой версии, чем форма, — форма уже смешанная "
                    "(validate это называет); чинить её — пересохранением в конфигураторе.")
    elif op == "set_column_control":
        road = (" У вложенных элементов колонок смесь бывает и у платформы "
                "(форма 15 с вложенными 16, форма 16 с вложенными 10 и 15); откуда она там, не "
                "проверялось, и редактор её не заводит. Дорога — template: тело "
                f"вложенного {kind} той же версии (из соседней колонки этой формы или из формы "
                "той же версии).")
    raise EditError(
        f"общий блок оформления узла — {theirs}, а у формы — {version}. Смешанных форм платформа "
        "не пишет: элементы той же версии, что форма. Платформа смесь переносит, но вид решают "
        f"значения оформления, а при пересохранении она поднимает всю форму до своей версии — "
        f"{_design.X19C}.{road} Позвать всё же можно — unverified=True")


def _like_node(doc, like, template, name, caption, unverified=False, siblings=None, clean=False):
    """Узел по образцу соседа ЭТОЙ формы: `(узел, фраза отчёта)`.

    Чистится так же, как шаблон (`templates.clean_node`: имя, координаты, привязки границ, списки
    зависимых, вложенные, головы блоков действий), и сверх того — от ЛИЧНОГО соседа: то, что
    связывает соседа с ЕГО данными, модулем и соседями и имеет пустое значение, одинаковое у всех
    версий:

    * обработчики событий — список пуст;
    * подсказка — пуста; заголовок — `caption`, а без него ИМЯ элемента (так платформа ставит
      заголовок новой надписи и кнопке);
    * ИсточникДействий (`name_block.action_source`) — «нет»: это ссылка на ДРУГОЙ элемент формы;
    * КнопкаПоУмолчанию и сочетание клавиш — сняты: они единственны в форме;
    * связь по типу поля ввода — снята: это путь к реквизиту соседа;
    * вид поля ввода — вид ФОРМЫ (`design.like_view`): у однородной формы он и так соседа; у
      смешанной — вид конфигурации (`siblings`), без соседних форм — большинства формы, при равенстве —
      соседа. Сосед другого вида копируется с видом формы И оформлением (позиции 2–11) самого
      частого сочетания полей этого вида.

    **Тип значения поля ввода остаётся соседским, и отчёт его называет:** с ним ходят кнопки выбора,
    квалификаторы, маска и блок редактирования значения, и «пустого» значения у этого узла нет.
    Берут соседа того же типа значения — или правят свойства после. Прочее личное переносится в копию
    как есть (формат, маска, кнопки выбора, картинки, `u19`/`u20`, гиперссылка надписи, меню
    кнопки); отчёт называет это одной фразой (`LIKE_KEPT`).

    **РежимВыбораИзСписка соседа — отказ, снимаемый `unverified`.** Режим связан с данными: у поля с
    реквизитом формы платформа снимает тип у поля и у реквизита, и `set_property` поле БЕЗ привязки этим
    режимом не снабжает. У копии привязки нет всегда (она живёт в таблице формы по индексу элемента),
    поэтому молча собирать такое поле нельзя.

    Отказ — у соседа с ДЕТЬМИ (вложенные элементы, колонки, кнопки панели или меню): они сами личное
    соседа, и индексы вложенных сквозные по форме.
    """
    from .. import templates as _templates
    place = find_element(doc, like)
    kind = place.element.get("type")
    if isinstance(template, str) and template != kind:
        raise EditError(f"сосед {like!r} — {kind}, а просили {template}: по образцу берут соседа "
                        f"ТОГО ЖЕ вида (иначе и запись, и оформление — чужого вида). Соседи вида "
                        f"{template}: " + (", ".join(n for n, e in _design.elements(doc)
                                                   if e.get("type") == template and n) or "нет"))
    if kind not in LIKE_KINDS:
        raise EditError(
            f"по образцу соседа ставятся {', '.join(LIKE_KINDS)}; у {kind} " + (
                "колонки — личное соседа (имя, Данные, заголовок, тип, вложенный элемент со своими "
                "обработчиками и связями: у соседних табличных полей колонки обычно разные), и что из них чистить, не "
                "проверялось" if kind == "TableBox" else "что у него личное, не проверялось")
            + ". Дорога — узел из формы той же версии (template — узел)")
    node = copy.deepcopy(place.element)
    children = []
    if (node.get(ELEMENTS) or {}).get(ITEMS):
        children.append(f"вложенных элементов {len(node[ELEMENTS][ITEMS])}")
    buttons = sum(len(_buttons(block)) for _bar, block in _bars(node))
    if buttons:
        children.append(f"кнопок {buttons}")
    if children:
        raise EditError(f"у соседа {like!r} ({kind}) дети — {', '.join(children)}: они его личное "
                        "(вложенные — со сквозными индексами формы, кнопки — со своими действиями), "
                        "и копия их не несёт. Возьмите соседа без них либо шаблон")
    mode = (node.get(CONTENT) or {}).get(LIST_CHOICE_MODE) if kind == "TextBox" else None
    if mode is True and not unverified:
        raise EditError(
            f"у соседа {like!r} включён РежимВыбораИзСписка ({LIST_CHOICE_MODE}), а у копии привязки "
            "данных нет: привязка живёт в таблице формы по индексу элемента и в копию не переносится. "
            "Режим связан с данными (у поля с реквизитом формы платформа снимает тип у поля и у "
            f"реквизита), и поле без привязки set_property им "
            "не снабжает — отказ, снимаемый unverified: что платформа сделает с таким полем, не "
            f"проверялось (у поля ввода без привязки с этим режимом тип пуст). Дорога — сосед без режима, а режим ставит set_property, когда поле "
            "привязано к данным; позвать всё же можно — unverified=True, и режим сдвинется с копией "
            "как есть")
    if _find_pages(node) is not None:
        # Направляющие страниц пересчитываются под новый размер (`_fit_guides`) — тем же правилом, что у
        # шаблона панели, и с той же границей: геометрия проверена только при закладках сверху.
        # Спрашивается ДО правки документа, на копии.
        try:
            _fit_guides(copy.deepcopy(node), 1, 1)
        except EditError as e:
            raise EditError(f"по образцу панели {like!r} не поставить: {e}") from None
    _templates.clean_node(node)
    said = [f"по образцу {like!r} (версия общего блока "
            f"{_design.version_of(_design.block_of(node))} и оформление — соседа)"]
    content = node.get(CONTENT) if isinstance(node.get(CONTENT), dict) else {}
    for _key, block in _like_places(node, EVENTS):
        if block.get(EVENT_ITEMS):
            said.append(f"обработчиков соседа {len(block[EVENT_ITEMS])} — сняты")
        block[EVENT_ITEMS] = []
        block["count"] = 0
    for _key, block in _like_places(node, TOOL_TIP):
        if block.get(LS_ITEMS):
            said.append("подсказка соседа снята")
        block[LS_ITEMS] = []
        block[LS_COUNT] = 0
    captions = list(_caption_places(content))
    if len(captions) == 1:
        set_text(captions[0][1], caption if caption is not None else name)
        said.append("заголовок — " + ("caption" if caption is not None else "имя элемента")
                    + " (чужой не переносится)")
    names = node.get(NAME_BLOCK)
    source = names.get(ACTION_SOURCE) if isinstance(names, dict) else None
    if isinstance(source, int) and not isinstance(source, bool) and source != NO_REFERENCE:
        names[ACTION_SOURCE] = NO_REFERENCE
        said.append(f"ИсточникДействий соседа (элемент #{source}) снят")
    for _key, block in _like_places(node, DEFAULT_BUTTON, leaf=True):
        if block.get(DEFAULT_BUTTON) is True:
            block[DEFAULT_BUTTON] = False
            said.append("КнопкаПоУмолчанию снята (она в форме одна)")
    for _key, block in _like_places(node, SHORTCUT):
        if block.get(SHORTCUT_KEY) or block.get(SHORTCUT_MODIFIERS):
            said.append("сочетание клавиш снято (у копии оно было бы вторым)")
        block[SHORTCUT_KEY], block[SHORTCUT_MODIFIERS] = 0, 0
    link = content.get(TYPE_LINK)
    if isinstance(link, dict) and isinstance(link.get(TYPE_LINK_ITEMS), list):
        if link[TYPE_LINK_ITEMS]:
            said.append("связь по типу соседа снята")
        link[TYPE_LINK_ITEMS] = []
    holder = _find_pages(node)
    pages = holder[PAGES][PAGE_ITEMS] if holder is not None else []
    if len(pages) > 1:
        said.append(f"страниц {len(pages)} — как у соседа, с его именами и заголовками")
    if clean:
        said.append(_like_reset(node, kind))
    pattern = content.get(TEXTBOX_PATTERN) if kind == "TextBox" and not clean else None
    if isinstance(pattern, dict):
        said.append(f"тип значения — соседа: {_type_words(pattern)} (с ним его кнопки, "
                    "квалификаторы и маска; нужен другой — берите соседа того типа)")
    if mode is True:
        said.append(f"РежимВыбораИзСписка соседа уехал с копией по unverified в поле без привязки "
                    f"данных — не проверялось (у такого поля тип пуст); "
                    "привяжите поле к данным и проверьте платформой")
    if kind in LIKE_KEPT and not clean:
        said.append(f"как у соседа остались {LIKE_KEPT[kind]} — это оформление и поведение, а не "
                    "связь, и копия их не чистит")
    view = _design.like_view(doc, node, like, siblings)
    if view:
        said.append(view)
    return node, "; ".join(said)


# Поведение, которое `like_clean` возвращает к значениям шаблона того же вида: `(путь от узла элемента, имена полей карты)`. Имя берётся, только если
# оно есть и у копии, и у шаблона (запись старой версии короче). Оформление (шрифт, цвета, рамка, вид поля) не сбрасывается — оно и есть смысл `like`.
LIKE_RESET = {
    "TextBox": [(("content",), ("text_edit_mirror", "choose_type", "list_choice_mode")),
                (("content", "u2", "u0"), ("read_only", "text_edit", "choice_list_button", "choice_button", "clear_button", "spin_button", "open_button",
                                           "mask", "format", "multi_line_code", "multi_line_mirror", "wrap", "password_mode_mirror", "extended_edit_mirror",
                                           "mark_negatives", "fixed_fraction_digits", "digits", "fraction_digits", "nonnegative", "horizontal_align",
                                           "vertical_align", "date_fractions", "auto_mark_incomplete", "auto_choice_incomplete", "incomplete_choice_mode",
                                           "choice_list_height", "choice_list_width")),
                (("content", "u2", "u0", "u0"), ("enabled",))],
    "CheckBox": [(("content", "u1", "u0", "u0"), ("enabled",)), (("content", "u1"), ("three_state",))],
    "Label": [(("content", "u1", "u0"), ("enabled",)), (("content", "u1"), ("hyperlink", "mark_negatives", "scrolling_text"))],
}
# Узлы, которые у поля ввода заменяются шаблонными целиком: описатель типа и блок редактирования. Тип и квалификаторы пишет привязка к реквизиту.
LIKE_RESET_WHOLE = {"TextBox": [("content", "pattern"), ("content", "u3")]}


def _walk(node, path):
    for key in path:
        node = node.get(key) if isinstance(node, dict) else None
    return node if isinstance(node, dict) else None


def _like_reset(node, kind):
    """Копия соседа → поведение шаблона того же вида; слова отчёта: что было у соседа и сброшено. Тип значения и блок редактирования — шаблонные
    (нейтральная строка); тип и квалификаторы реквизита запишет `bind`, а у стандартного реквизита они остаются шаблонными, как на шаблонном пути."""
    from .. import templates as _templates
    base = _templates.element(kind)
    changed = []
    for path, names in LIKE_RESET.get(kind, ()):
        have, template = _walk(node, path), _walk(base, path)
        for key in names if have is not None and template is not None else ():
            if key in have and key in template and have[key] != template[key]:
                changed.append(f"{key} = {have[key]!r}")
                have[key] = copy.deepcopy(template[key])
    whole = []
    for path in LIKE_RESET_WHOLE.get(kind, ()):
        have, template = _walk(node, path[:-1]), _walk(base, path[:-1])
        if have is not None and template is not None and path[-1] in have and path[-1] in template and have[path[-1]] != template[path[-1]]:
            have[path[-1]] = copy.deepcopy(template[path[-1]])
            whole.append(path[-1])
    said = ("поведение соседа возвращено к умолчаниям нового поля" + (f" (у соседа было: {', '.join(changed)})" if changed else " (совпало с умолчаниями)")
            + "; оформление (шрифт, цвета, рамка, вид) — соседа")
    if whole:
        said += "; тип значения и блок редактирования — шаблонные: тип и квалификаторы запишет привязка к реквизиту"
    return said


# Личное соседа, которое `like` НЕ чистит: оформление и поведение, а не связь с данными, модулем и
# соседями. Отчёт называет его одной фразой.
LIKE_KEPT = {
    "TextBox": "формат, маска, кнопки выбора и их картинки, картинка поля, u19/u20",
    "Label": "гиперссылка и картинки",
    "Button": "картинка и меню кнопки (menu_mode)",
}


def _like_places(node, key, leaf=False):
    """`(ключ, словарь)` под узлом, где лежит ключ `key`: сам словарь-значение ключа либо, при `leaf`,
    словарь, которому ключ принадлежит. Обход по словарям — в списки и во вложенные элементы не
    заходит.
    """
    for name, value in node.items() if isinstance(node, dict) else ():
        if name == ELEMENTS:
            continue
        if name == key:
            if leaf:
                yield name, node
            elif isinstance(value, dict):
                yield name, value
        if isinstance(value, dict):
            yield from _like_places(value, key, leaf)


def _issue_heads(node):
    """Голова блока действий у пересаживаемого узла: НОВОЙ панели — новая, КОПИИ — прежняя.

    Шаблон командной панели везёт НУЛЕВУЮ голову (как у меню), и здесь ей выдаётся своя — так делает
    платформа с новой панелью. Узел из другой формы — КОПИЯ, и его голова остаётся: платформа ведёт
    копии и так, и так (одна голова на всех либо у каждой своя), а сохранить голову — единственное, что
    не требует переписывать ссылки на неё (владельцы кнопок, GUID наборов-подменю, хвосты наборов, связи
    контекстного меню в корне формы).

    **GUID кнопок у копий РАЗНЫЕ:** платформа перевыпускает их при каждой выгрузке, и один GUID кнопки не
    встречается в двух блоках действий. GUID кнопок донора не трогаются; общие с формой — если донор та же
    форма — называет `_shared_button_ids`, а решает человек.

    Владельцы кнопок блока, расположенные на НУЛЕ, переводятся на новую голову вместе с ней (кнопка при
    нулевом владельце — то, чего платформа не пишет). **Прочие ссылки на нулевую голову не
    переводятся:** набор-подменю с GUID головы и описания вида 1, которые его называют, остаются на
    нуле; «все нули блока — голова» неверно (ноль встречается и в другой роли, `actions/…/action/u2`).
    """
    from ..templates import ZERO_GUID  # круговой импорт: templates зовёт edit
    said = []
    for _bar, block in _bars(node):
        head = block.get(ACTIONS_GUID)
        guid = head.get("guid") if isinstance(head, dict) else None
        if guid not in (None, ZERO_GUID):
            if node.get("type") == "CommandBar":
                said.append(f"голова панели прежняя, как у копии ({guid})")
            continue
        new = str(uuid.uuid4())
        block[ACTIONS_GUID] = {"guid": new}
        for _set, button in _buttons(block):
            owner = button.get(BTN_OWNER)
            if not isinstance(owner, dict) or owner.get("guid") in (None, ZERO_GUID):
                button[BTN_OWNER] = {"guid": new}
        said.append(f"голова блока действий выдана заново ({new}), как платформа выдаёт её "
                    "новой панели")
    return said


def _shared_button_ids(doc, node):
    """Сколько GUID кнопок пересаживаемого узла уже есть у кнопок формы — фразой отчёта.

    GUID кнопки не встречается в двух блоках действий, а редактор GUID донора сохраняет. Донор из ЭТОЙ ЖЕ
    формы даёт две панели с общими GUID — состояние, которого платформа не писала. Операция его не чинит
    (что правильно, не проверялось), но и молча не собирает.
    """
    theirs = {(button.get(BUTTON_ID) or {}).get("guid")
              for _name, block in _bars(doc) for _set, button in _buttons(block)}
    mine = {(button.get(BUTTON_ID) or {}).get("guid")
            for _name, block in _bars(node) for _set, button in _buttons(block)}
    shared = sorted(guid for guid in mine & theirs if guid)
    if not shared:
        return []
    return [f"GUID кнопок донора сохранены, и {len(shared)} из {len(mine)} уже есть у кнопок "
            "этой формы — донор, видимо, она же: GUID кнопки в двух блоках "
            "действий не бывает, и что платформа сделает с общими, не проверялось"]


def _set_anchors(coords, index, width, height, anchor, doc, holder_node, page=0,
                 unverified=False, name=None):
    """Привязки границ нового узла: к себе (умолчание), пара `form` либо роли `set_anchors`.

    Возвращает слова для отчёта (у `self` — `None`). Встречные записи здесь не пишутся: узла в форме
    ещё нет, их ставит `anchors.sync` после вставки.

    **Второе правило пишется ПО ИМЕНИ, а не по виду значения.** Позиция приходит блоком, поэтому поиск
    «массива из четырёх чисел» ничего бы не нашёл, причём молча: проверка обратным разбором
    непоставленную привязку не замечает.
    """
    from .. import anchors as _anchors
    axes = _anchors.anchor_axes(anchor)
    box = (coords[X], coords[Y], coords[WIDTH], coords[HEIGHT])
    rules = {1: [_anchors._rule(index, 0, height)], 3: [_anchors._rule(index, 2, width)]}
    if anchor == "form":
        rules = _anchors.form_pair(doc, holder_node, page, box, unverified)
        _anchors._need_lists(holder_node, [rules], name)
    for side, key in enumerate(ANCHORS):
        chosen = rules.get(side, []) + [dict(NO_ANCHOR)] * (2 - len(rules.get(side, [])))
        for rule_name, rule in zip(RULES, chosen):
            coords[key][rule_name].update(rule)
    if anchor == "form":
        return _anchors.form_words(doc, holder_node)
    if axes is None:
        return None
    plans = [_anchors.plan(doc, holder_node, page, index, box, axis, value, unverified)
             for axis, value in zip(("h", "v"), axes) if value is not None]
    _anchors._need_lists(holder_node, [p.rules for p in plans], name)
    loop = _anchors._cycle(doc, holder_node, index, plans)
    if loop:
        raise EditError(f"цепочка замкнулась бы — граница зависела бы от самой себя: {loop} (`.t .b .l .r` — верх, низ, лево, право). "
                        "Задайте другую привязку либо снимите правила соседей, которые идут к этому элементу")
    _anchors.write(coords, plans)
    return _anchors.plans_words(plans, index, holder_node, {index: name})


# Варианты привязок шире проверенного (`form-tabs`, `proportional-both`, `form-pair`). Проверено
# предприятием: ручной стиль формы (края формы без закладок и панели по верху, лево и право), доля
# второго правила на ОДНОЙ границе, цепочки со встречной записью.
ON_CORPUS.update({
    "set_anchors/center":
        "центр БЕЗ встречной записи в предприятии не реагирует; центр СО строкой проверен (чётный "
        "рост; при нечётном размере родителя — не проверялось). Запись центр по вертикали пишет в "
        "список нижнего края объекта, по горизонтали — правого. Середину операция берёт как "
        "половину края родителя с отбросом дроби (край — как у прочих ролей: у формы размер минус "
        "рамка, у панели направляющие)",
    "set_anchors/form-tabs":
        "край формы с ВИДИМЫМИ закладками, когда они не «Сверху», у формы Рамка кроме семи проверенных видов "
        "или DPI не 96 (закладки «Сверху», DPI 96, без Рамки и с Рамкой «Одинарная», «Двойная», "
        "«Выпуклая», «Вдавленная», «Подчеркивание», «Черта сверху», «Двойное подчеркивание» проверены, "
        "край формулой (W−2, H−20), пометки нет), операция берёт по направляющим "
        "страницы, как у панели (область страниц меньше формы; под unverified)",
    "set_anchors/proportional-both":
        "роль `proportional` пишет пропорциональную пару на ОБЕИХ границах оси; предприятию "
        "показывали пару на одной границе элемента: долю одной границы оно ведёт, обеих сразу — не "
        "проверялось. В образцах форм такая ось есть — обе границы с парой к краям родителя, флаг поднят",
    "add_element/form-pair":
        "пара `anchor=\"form\"` без встречных записей: платформа файл открывает, но при "
        "пересохранении сводит пару к одиночным правилам `F.b-8` и `F.r-30` и дописывает к ним "
        "строки родителя. Пару со встречными записями предприятию не показывали, а без записей она "
        "не работает вовсе. В образцах форм такая пара есть — верх и лево без правила, низ и право "
        "пропорциональными парами к краям родителя",
    "set_anchors/panel-bottom":
        "проверены привязки вложенного к верхнему, левому и правому краю панели, к НИЖНЕМУ — нет. "
        "Нижний край панели — не её высота, а место над полосой закладок (у закладок сверху обычно "
        "−20…−24, у прочих своё), и операция берёт его у направляющей 4 страницы",
})


def set_anchors(doc, element, h=None, v=None, unverified=False):
    """Привязки элемента по ИМЕНАМ ролей осей — ручной стиль с флагами.

    `h`: `stretch` (растягивается по ширине), `left` (лежит у левого края), `right` (сдвигается с правым),
    `proportional` (обе границы долей между краями), `center` (к середине родителя), `self` (левая
    граница без правила, правая от своей левой — надпись шапки колонок), `column` (левая без правила,
    правая долей между краями — первое поле шапки колонок), `slide` (дальняя граница долей между краями,
    ближняя от неё — размер держится: разделитель); `v`: `stretch`, `top`, `bottom`,
    `proportional`, `center`, `slide`. Сторона соседа разделителя — `{"splitter": "<имя разделителя>"}`
    (граница, обращённая к нему, идёт к его стороне; вторая граница оси не меняется). Цепочка «назад» — `{"before": "<имя>"}` (дальняя граница к ближней стороне соседа, размер держится) и `{"before": "<имя>", "role": "stretch"}` (ближняя — к краю родителя). Цепочка к соседу того же родителя — `{"after": "<имя>"}` (сдвигается за ним,
    размер держит), `{"after": "<имя>", "role": "stretch"}` (ближняя граница за соседом, дальняя к краю
    родителя) и `{"after": "<имя>", "role": "column"}` (дальняя долей между границей соседа и краем
    родителя — внутреннее поле шапки колонок; только `h`). Флаг «Ручная привязка» оси поднимается,
    встречные записи — у соседа и у родителя — ставятся по обоим правилам, прежние снимаются. Подробно —
    `frm_codec.anchors.set_anchors`.
    """
    from .. import anchors as _anchors
    return _anchors.set_anchors(doc, element, h=h, v=v, unverified=unverified)


def remove_element(doc, name):
    """Элемент с формы: узел, счётчик, строки родителя и все ссылки на него.

    Вместе с узлом уходят и вложенные в него: индексы у них сквозные по форме, и ссылки на каждый
    чистятся так же. Ссылки трёх родов операция чистит сама: `validate` про висячие записи зависимых
    молчит, а платформа чинит их только при первом сохранении. Привязки ДРУГИХ элементов к удаляемому
    сбрасываются в «привязки нет» и называются в отчёте. Поле строки родителя, называющее элемент, — у
    привязок (`anchors.ROW_ELEMENT`): одно имя на весь навык.
    """
    from .. import anchors as _anchors
    place = find_element(doc, name)
    gone, node = set(), place.element
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current.get(INDEX), int) and not isinstance(current.get(INDEX), bool):
            gone.add(current[INDEX])
        stack += [item for item in (current.get(ELEMENTS) or {}).get(ITEMS) or []
                  if isinstance(item, dict)]
    place.items.remove(node)
    place.holder[ELEMENTS][COUNT] = len(place.items)
    rows = _layout_rows(place.holder)
    for key, members in rows.items():
        left = [row for row in members if row.get(_anchors.ROW_ELEMENT) not in gone]
        if len(left) != len(members):
            rows[key][:] = left
    said = _forget(doc, gone)
    _renumber(place.holder)
    tail = ("; " + "; ".join(said)) if said else ""
    return f"убран элемент {name!r} (индексы {sorted(gone)}){tail}"


def _inside(root, holder):
    """Лежит ли родитель `holder` в поддереве узла `root` (сам `root` — да): панель, в которую нельзя переносить собственную панель."""
    if holder is root:
        return True
    return any(isinstance(child, dict) and _inside(child, holder) for child in (root.get(ELEMENTS) or {}).get(ITEMS) or ())


def move_element(doc, name, box=None, anchor=None, holder=None, page=None, unverified=False, search=True, by=None, with_contents=False, contents_anchor=None):
    """Существующий элемент на новое место — размер, привязки краёв, родитель и страница; всё прочее (имя,
    индекс, привязка данных, события, оформление, подпись) остаётся как было.

    Нужна генерации: форма-оболочка с полями, надписями, таблицей и колонками **переиспользуется**, а не
    удаляется и создаётся заново (`remove_element` + `add_element` дают новый индекс, теряют имя и
    обработчики, и обработчик в модуле остаётся без элемента).

    `box` — `(лево, верх, ширина, высота)` в пикселях родителя, `anchor` — как у `add_element`; `"keep"` — прежние правила элемента (те же объекты и стороны,
    смещения пересчитаны под новое место; только в том же родителе и на той же странице; без `anchor` у формы с «Изменять размер» снято берётся `keep`)
    (умолчание — «к себе»; без `anchor` после переноса привязки проверяются на модели раскладки и, если элемент расходится с
    соседями нового места, перебираются кандидаты, как у `add_element`; `search=false` отключает перебор), `holder` — имя родителя (панель); **без `holder` элемент остаётся в своём родителе и на своей странице** (правка на месте: ширина,
    сдвиг), `"holder": ""` или `"holder": "форма"` — перенос прямо на форму; `page` — страница родителя (без него: у элемента, не
    менявшего родителя, — его страница, при переносе к другому родителю — 0). Привязки границ пишутся ЗАНОВО: старые правила элемента и встречные записи, называющие
    его, снимаются (`anchors.sync`); прочие элементы, привязанные к нему, свои правила сохраняют
    (смещения не пересчитываются: переносят все такие элементы вместе, как `generate`). Если родитель и страница те же, место в списке
    элементов, номер на странице (`page_sequence`) и порядок обхода (`tab_order`) прежние; иначе элемент последний в списке и по номеру на
    странице назначения, а порядок обхода — наибольший плюс один. Расчёт привязок идёт ДО правок: отказ оставляет форму
    прежней.

    **Привязки соседей к переносимому.** Запись «ко мне привязан элемент N» лежит в координатах самого
    переносимого (`DEPENDENTS`), и без неё правило соседа в предприятии мертво. При том же родителе эти
    списки остаются как были. При смене родителя правило соседа на переносимый становится висячим:
    оно снимается в «нет», а заметка операции перечисляет (элемент, сторона).

    **Панель с вложенными элементами** (Panel) переносится и меняет размер. Дети лежат в координатах страницы панели, и при том же размере их `box`
    не меняется: панель встаёт на новое место, привязки панели и встречные записи соседей — как у любого элемента. Другой размер в `box` ведёт детей по их
    правилам к краям страницы на ВСЕХ страницах панели, как рост родителя в модели раскладки (`edit.panelsize`: привязанные к правому и нижнему краю сдвигаются,
    растянутые растут, дальние направляющие страниц переезжают); отчёт называет, сколько детей сдвинулось. Мышью за край панели в конфигураторе это не
    сверялось. Перенос панели с детьми к другому родителю и в свою же вложенную панель — отказ.

    `by=[dx, dy]` вместо `box` — сдвиг на смещение при прежнем размере (для панели, рамки и обычного элемента). `with_contents=true` у рамки (GroupBox) сдвигает вместе с
    ней соседей той же страницы, чей `box` целиком внутри рамки (в рамке они лежат не детьми, а соседями): их привязки те же, смещения пересчитаны, а правила
    элементов, остающихся на месте и называющих рамку или участника, получают смещение под ушедшую сторону. Рамка меняет размер — содержимое сдвигается на сдвиг левого верхнего
    угла и размер не меняет. Только в своём родителе и на своей странице.

    `contents_anchor={"v": "bottom"}` (только с `with_contents`) после сдвига ставит участникам привязки ролями `set_anchors` по названным осям (`h`, `v`; ось, которую не
    назвали, остаётся как была): рамка, привязанная к низу, увлекает содержимое при растяжении окна, только если и оно привязано к низу, а `keep` оставляет участникам
    прежние (например, верхние) правила.

    Операция отказывает словами в случаях: перенос панели с детьми к другому родителю; в качестве родителя указан сам переносимый элемент или его вложенная панель;
    у родителя нет указанной страницы; `with_contents` у не рамки. Пересадка узла между формами не поддерживается.
    """
    from .. import anchors as _anchors, templates as _templates
    from . import panelsize as _panelsize
    place = find_element(doc, name)
    node = place.element
    if (box is None) == (by is None):
        raise EditError("укажите ровно одно из двух: `box` — (лево, верх, ширина, высота) на новом месте, или `by` — сдвиг [dx, dy] при прежнем размере")
    if by is not None:
        if not (isinstance(by, (list, tuple)) and len(by) == 2 and all(isinstance(v, int) and not isinstance(v, bool) for v in by)):
            raise EditError("by — два целых [dx, dy]: сдвиг вправо и вниз в пикселях родителя (отрицательные — влево и вверх)")
        here = node.get(COORDS)
        if not (isinstance(here, dict) and all(isinstance(here.get(k), int) and not isinstance(here.get(k), bool) for k in (X, Y, WIDTH, HEIGHT))):
            raise EditError(f"у элемента {name!r} нет блока координат с целыми краями: сдвигать на смещение нечего — укажите `box`")
        box = (here[X] + by[0], here[Y] + by[1], here[WIDTH] - here[X], here[HEIGHT] - here[Y])
    if not (isinstance(box, (list, tuple)) and len(box) == 4 and all(isinstance(v, int) and not isinstance(v, bool) for v in box)):
        raise EditError("box — четыре целых (лево, верх, ширина, высота) в пикселях родителя")
    if box[2] <= 0 or box[3] <= 0:
        raise EditError(f"box {tuple(box)}: ширина и высота — положительные")
    if with_contents and node.get("type") != "GroupBox":
        raise EditError(f"with_contents — сдвиг рамки вместе с содержимым, а {name!r} — {node.get('type')}, не рамка (GroupBox). У панели дети сдвигаются сами: "
                        "они лежат в её координатах")
    has_children = bool((node.get(ELEMENTS) or {}).get(ITEMS))
    if contents_anchor is not None:
        if not with_contents:
            raise EditError("contents_anchor — привязки участникам рамки, они бывают только вместе с with_contents")
        if not (isinstance(contents_anchor, dict) and contents_anchor and set(contents_anchor) <= {"h", "v"}):
            raise EditError('contents_anchor — объект с осями "h" и/или "v" (роли `set_anchors`: {"v": "bottom"}), а пришло ' + repr(contents_anchor))
    old_name = next((n for n, h in holders(doc) if h is place.holder), None)
    if holder is None:
        target = place.holder
    elif holder in ("", "форма") and not any(n == holder for n, _h in holders(doc)):
        target = _container(doc)
    else:
        target = holder_by_name(doc, holder)
    holder = next((n for n, h in holders(doc) if h is target), None)  # имя родителя; None — форма
    if target is node or any(h is target for _n, h in holders(doc) if _inside(node, h)):
        raise EditError(f"элемент {name!r} не может стать родителем самого себя или своей вложенной панели")
    if has_children and target is not place.holder:
        raise EditError(f"у элемента {name!r} ({node.get('type')}) есть вложенные элементы, а перенос к другому родителю (в панель или на форму) с детьми не проверялся: "
                        "правила детей — в координатах страницы панели, и их перенос вместе с панелью в другого родителя платформой не проверялся. Сдвиг в том же родителе (box, by) операция умеет; "
                        "чтобы переложить панель, соберите её на новом месте и перенесите детей по одному (`move_element` с `holder`)")
    if with_contents and (target is not place.holder or (page is not None and page != place.page)):
        raise EditError("with_contents (рамка вместе с содержимым) — только в своём родителе и на своей странице: содержимое — соседи рамки, и на другую страницу "
                        "или в другого родителя оно с ней не уйдёт. Перенесите рамку и каждый элемент отдельно")
    if page is None:
        page = place.page if target is place.holder and isinstance(place.page, int) else 0
    else:
        page = _page_arg(doc, holder, page)
    where_was = f"на панели «{old_name}»" if old_name else "прямо на форме"
    if anchor == "keep" and (target is not place.holder or place.page != page):
        raise EditError(f"привязка `keep` (оставить прежние правила) возможна, только если элемент остаётся в том же родителе и на той же странице, "
                        f"а {name!r} лежит {where_was}, на странице {place.page}. Правка на месте — без holder и page (они остаются прежними); перенос — "
                        "привязка ролью, а не keep (holder — имя панели, а чтобы положить на форму, \"holder\": \"\")")
    pages = pages_count(target)
    if pages is None and page:
        raise EditError(f"у родителя {holder!r} {no_pages_words(target)} — класть элемент можно только на страницу 0")
    if pages is not None and not 0 <= page < pages:
        raise EditError(f"страницы {page} {'у формы' if holder is None else f'у родителя {holder!r}'} нет: страниц {pages} (счёт с нуля)")
    auto_keep = False
    if anchor is None and doc.get("size_change") == "DontChange" and target is place.holder and place.page == page:
        # У формы с «Изменять размер» снято растягивать нечего: привязки прежние, чужие правила и встречные записи не перестраиваются.
        anchor, auto_keep = "keep", True
    watched = (anchor is None or anchor == "keep") and search  # привязки без названия — перебор, `keep` — проверка прежних правил на модели раскладки
    if watched:
        from ..layout import candidates as _candidates
        snapshot = _candidates.fast_copy(doc)
    searching = anchor is None
    if anchor is None:
        anchor = "self"
    index = node[INDEX]
    left, top, width, height = box
    if not isinstance(node.get(COORDS), dict):
        raise EditError(f"у элемента {name!r} нет блока координат (в документе он не запись): двигать нечего — правленый руками документ?")
    child_writes = content_writes = None
    members = []
    before_contents = copy.deepcopy(doc) if contents_anchor else None
    side_words = []
    here = node[COORDS]
    if has_children and all(isinstance(here.get(k), int) for k in (X, Y, WIDTH, HEIGHT)):
        grew = (width - (here[WIDTH] - here[X]), height - (here[HEIGHT] - here[Y]))
        if grew != (0, 0):
            child_writes, said, _n, _o = _panelsize.children_plan(doc, node, *grew)
            side_words.append(said)
    if with_contents:
        members = _panelsize.contents(place.holder, node, place.page)
        shift = (left - here[X], top - here[Y])
        if not members:
            side_words.append(f"with_contents: внутри рамки {name!r} нет ни одного элемента целиком — сдвигается одна рамка")
        elif shift != (0, 0):
            content_writes, said = _panelsize.shift_plan(place.holder, node, (left, top, left + width, top + height), members, shift)
            side_words.append(said)
        else:
            side_words.append(f"with_contents: рамка не сдвинулась (меняется только размер) — содержимое ({len(members)}) остаётся на месте")
    scratch = _templates.clean_coords(node[COORDS])
    scratch.update({X: left, Y: top, WIDTH: left + width, HEIGHT: top + height})
    said_anchor = _set_anchors(scratch, index, width, height, anchor, doc, target, page, unverified, name)
    old_page, old_holder = place.page, place.holder
    same_holder = target is old_holder
    # Правила ДРУГИХ элементов, называющие переносимый (`B привязан к A`): встречная запись лежит в
    # координатах A (`DEPENDENTS`), и без неё правило в предприятии не работает. Перечень берётся до
    # правок — отказ оставляет форму прежней.
    neighbours = []
    for other in elements_of(old_holder):
        other_coords = other.get(COORDS) if other is not node else None
        if not isinstance(other_coords, dict):
            continue
        for border, key in enumerate(ANCHORS):
            side_block = other_coords.get(key)
            for rule_name in RULES:
                rule = side_block.get(rule_name) if isinstance(side_block, dict) else None
                if isinstance(rule, dict) and rule.get(RULE_OBJECT) == index:
                    neighbours.append((other, border, rule))
    kept = ({key: copy.deepcopy(node[COORDS][key]) for key in DEPENDENTS if isinstance(node[COORDS].get(key), list)} if same_holder else {})
    creation = (node[COORDS].get(TAB_ORDER) if target is old_holder and old_page == page else None)
    in_place = same_holder and old_page == page
    old_seq = node[COORDS].get(PAGE_SEQUENCE)
    if in_place and not (isinstance(old_seq, int) and not isinstance(old_seq, bool)):
        in_place = False
    items = elements_of(target)
    if not in_place:
        place.items.pop(place.at)
        place.holder[ELEMENTS][COUNT] = len(place.items)
        _renumber(place.holder)
    scratch[PAGE] = page
    scratch[PAGE_SEQUENCE] = old_seq if in_place else len(_on_page(target, page))
    scratch[TAB_ORDER] = creation if isinstance(creation, int) and not isinstance(creation, bool) else max(
        [c.get(TAB_ORDER) or 0 for c in _on_page(target, page)] + [0]) + 1
    scratch.update(kept)  # тот же родитель: встречные записи чужих правил на переносимый остаются как были (их правила целы)
    node[COORDS] = scratch
    if not in_place:
        items.append(node)
        target[ELEMENTS][COUNT] = len(items)
        _renumber(target)
    _anchors.sync(doc, index, keep_places=(anchor == "keep"))  # снимает ВСЕ записи, называвшие индекс (старые правила), и ставит по новым; при `keep` — на прежние места списков
    if child_writes:
        _panelsize.apply(child_writes)
    if content_writes:
        _panelsize.apply(content_writes)
    if contents_anchor and members:
        try:
            for member in members:
                _anchors.set_anchors(doc, (member.get(NAME_BLOCK) or {}).get(NAME), h=contents_anchor.get("h"), v=contents_anchor.get("v"), unverified=unverified)
        except EditError:
            doc.clear()
            doc.update(before_contents)
            raise
        side_words.append(f"участникам рамки поставлены привязки {contents_anchor}")
    cut = []
    if not same_holder:
        # Другой родитель: правило соседа называет элемент чужого родителя — висячее; снимается в «нет» (как
        # при `remove_element`), называется.
        for other, border, rule in neighbours:
            rule.update(NO_ANCHOR)
            cut.append(f"«{(other.get(NAME_BLOCK) or {}).get(NAME)}»/{_anchors.BORDER_WORDS[border]}")
    tail = f"; {said_anchor}" if said_anchor else ""
    if side_words:
        tail += "; " + "; ".join(side_words)
    if auto_keep:
        tail += "; форма не растягивается («Изменять размер» снято): привязки оставлены прежними"
    if watched:
        try:
            chosen_words = (_candidates.refine(snapshot, doc, name, unverified, moved=True) if searching
                            else _candidates.warn(snapshot, doc, name))
        except EditError:
            doc.clear()
            doc.update(snapshot)
            raise
        tail += f"; {chosen_words}" if chosen_words else ""
    if in_place:
        tail += "; номер на странице, порядок обхода и место в списке элементов прежние"
    else:
        tail += (f"; порядок обхода — наибольший плюс один на странице {page}" + ("" if same_holder else " родителя")
                 + ", элемент последний в списке элементов и по номеру на странице" if creation is None else
                 f"; порядок обхода (L6+2) прежний, элемент последний в списке элементов и по номеру на странице")
    if cut:
        tail += (f"; родитель сменился — привязки соседей к элементу сняты в «нет» ({len(cut)}: {', '.join(cut)}); "
                 "при необходимости задайте им привязки заново")
    return (f"{holder or 'форма'}: элемент {name!r} ({node.get('type')}) перенесён, индекс {index} прежний, страница {page}, "
            f"box {tuple(box)}{tail}")


def set_action_source(doc, bar, source=None):
    """ИсточникДействий командной панели (`name_block.action_source`): табличное поле формы — его ИНДЕКС,
    платформа автозаполняет панель действиями этой таблицы; без `source` — сама форма (0, как у
    `ДействияФормы`). Прочие значения источника — «нет» (`4294967295`) и индекс не таблицы.
    """
    place = find_element(doc, bar)
    if place.element.get("type") != "CommandBar":
        raise EditError(f"элемент {bar!r} — {place.element.get('type')}, а источник действий бывает у командной панели (CommandBar)")
    if source is None:
        value, words = 0, "форма"
    else:
        table = find_element(doc, source)
        if table.element.get("type") != "TableBox":
            raise EditError(f"источник действий {source!r} — {table.element.get('type')}: панель берёт действия табличного поля (TableBox) "
                            "или формы (без source)")
        value, words = table.index, f"табличное поле {source!r} (индекс {table.index})"
    block = place.element[NAME_BLOCK]  # панель найдена по имени из этого блока, он — запись
    was = block.get(ACTION_SOURCE)
    block[ACTION_SOURCE] = value
    return f"источник действий панели {bar!r}: {was} → {value} ({words})"


def rename_element(doc, old, new):
    """Имя элемента. Ссылки на элементы в файле идут по ИНДЕКСУ, а не по имени — поэтому правится ровно
    одно место, и платформа показывает новое имя в списке ИсточникДействий панели, не теряя связи.
    """
    place = find_element(doc, old)
    if new in element_names(doc):
        raise EditError(f"элемент {new!r} в форме уже есть")
    place.element[NAME_BLOCK][NAME] = new
    return f"{old} → {new}"


def _type_words(pattern):
    """Тип значения словами для отчёта: буквы с квалификаторами числа и строки."""
    types = (pattern or {}).get(PATTERN_TYPES) if isinstance(pattern, dict) else None
    if not types:
        return "пустой"
    words = []
    for item in types:
        if not isinstance(item, dict):
            words.append("?")
            continue
        letter = item.get(PATTERN_KIND)
        if letter == "N":
            words.append(f"N({item.get(PATTERN_NUMBER[0])},{item.get(PATTERN_NUMBER[1])})")
        elif letter == "S" and item.get(PATTERN_LENGTH) is not None:
            words.append(f"S({item.get(PATTERN_LENGTH)})")
        elif letter == "#":
            # Буква ссылки — «#» (голым знаком отчёт читался бы как опечатка). Имени типа форма не несёт — только
            # GUID из метаданных конфигурации.
            ref = item.get(PATTERN_REF)
            guid = schema.type_guid(ref)
            words.append(ref if isinstance(ref, str) and guid else f"ссылка (GUID типа {guid})" if guid else "ссылка")
        else:
            words.append(str(letter))
    return ", ".join(words)


# Формы, у которых страниц формы больше одной (`CORPUS_STAMP`).
CORPUS_FORM_PAGES = {
    "форм": 8,
    "по числу страниц": {2: 6, 7: 2},
    "по закладкам": {"DontUse": 7, "Top": 1},
    "по поколению": {16: 5, 15: 2, 10: 1},
    "не первых страниц": 18,
    # чем не первая страница отличается от первой той же формы, кроме имени и заголовка
    "отличие от первой": {(): 14, ("visible",): 2, ("enabled", "visible"): 1,
                          ("title_picture",): 1},
    "направляющие не первых": {"по умолчанию, не отображать": 9, "по умолчанию, сверху": 6,
                               "сдвинуты": 2, "нет": 1},
    # позиция 7 правой (номер 3) и нижней (номер 4) направляющей контейнера формы на ВСЕХ её страницах =
    # ширина/высота − координата: (сколько так, сколько направляющих).
    "отступ от дальнего края": {"правые": (4962, 5010), "нижние": (4954, 5010)},
    "АктивизироватьПоУмолчанию «нет»": (17, 18),
    "элементов на страницах ≥ 1": 110,
    "форм с элементами на страницах ≥ 1": 7,
    "номер на странице сплошной": (25, 25),
    "порядок обхода 1…N": (23, 25),
}


def _short(value):
    """Значение ОДНОЙ строкой для отчёта: `["N", 9, 0]`.

    Своё, а не `json0.dumps`: тот печатает документ столбиком, а строка отчёта обязана уместиться в
    строку.
    """
    if isinstance(value, list):
        return "[" + ", ".join(_short(item) for item in value) + "]"
    if isinstance(value, dict):
        # Тело встроенной картинки — файл в base64: в строку отчёта идёт длина, а не файл.
        return "{" + ", ".join(
            f"{key}: " + (f"<{len(item)} знаков base64>" if key == "base64" and isinstance(item, str)
                          and len(item) > 40 else _short(item)) for key, item in value.items()) + "}"
    if isinstance(value, json0.Dec):
        return str(value)  # дробное и экспонента — числом, как в JSON: `2e1`, не `'2e1'`
    return repr(value)


def _slot_type_name(kind):
    """Имя поля по ТИПУ его блока: у карты такое поле одно (связь по типу, блок действий)."""
    names = {slot.name for node in schema.MAP.values() for slot in (node.fields or {}).values()
             if isinstance(slot, schema.N) and slot.type == kind}
    if len(names) != 1:
        raise schema.SchemaError(f"редактор ждёт одно имя у поля с узлом {kind}, а карта даёт "
                                 f"{sorted(names)}")
    return names.pop()


TYPE_LINK = _slot_type_name("TypeLink")

# Блок редактирования поля ввода при РежимеВыбораИзСписка — строение платформы байт в байт
# (`{763308b0-…,{0}}`; до правки стояло `{9a7643d2-…,{4,…}}`, запись длиннее). Нулевая позиция блока
# `u3` (единица) не меняется.
LIST_CHOICE_MODE = _named("Content.TextBox", "list_choice_mode")[1]

# РежимВыбораИзСписка у поля ввода ФОРМЫ и ВИД его данных: различает не «есть ли данные», а чьи они:
#
# * поле, привязанное к СВОЕМУ реквизиту формы путём из одного шага: платформа вместе с режимом
#   снимает тип у поля и у реквизита (описатели становятся пустыми) и ставит Длину 255 (0 → 255);
# * поле, показывающее реквизит ОБЪЕКТА через основной реквизит (поле значения → `[{1},{0,GUID}]`): тип не
#   тронут, его задаёт объект, а не форма.
#
# Путь через ДРУГОЙ реквизит формы в 2+ шага режима не носит; поле без привязки — крайне редко, и
# тип у него пуст; реквизит формы, который держат и другие привязки, режима не носит.
CORPUS_LIST_CHOICE_DATA = {"реквизит формы": (21, 50), "через основной": (244, 1),
                           "через реквизит формы": (0, 0), "без привязки": (0, 2)}

TYPE_LINK_ITEMS = _run("TypeLink", schema.Counted)
