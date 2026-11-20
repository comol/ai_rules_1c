"""Состояние формы для рендера: общий слой, на котором строится и применение разбора кода, и явная просьба модели (`state.json`).

Рисунок формы получает состояние как `render.CodeMarks`: разбор кода (`brief.images.marks_of`) записывает в него то, что код делает безусловно, а `apply` кладёт поверх
явный запрос — тем же способом и в те же поля. Поэтому порядок один: **файл < разбор кода < запрос**; при расхождении побеждает явный запрос (`false` прячет то, что
показывают и файл, и код; `true` показывает то, что прячут файл и код).

`state.json` — замкнутый словарь; чего нет, то не задано:

* `size` — `[ширина, высота]` клиентской области;
* `hidden` — `"hatch"` (скрытое рисуется на своём месте со штриховкой и подписью, кто скрыл: файл, код, запрос) или `"hide"` (как на экране: скрытое не рисуется);
* `conditional` — `"plain"` (умолчание: видимость, которую код меняет по условию или вероятно, нарисована как в файле) или `"hatch"` (она штрихуется так же, как скрытое — элемент, закладка
  страницы, шапка колонки, значок кнопки; слов и уголков нет);
* `visible`, `enabled`, `read_only` — `{элемент: true|false}`; `title` — `{элемент: текст}`;
* `values` — `{элемент: true|false|текст|число}`: значение данных поля ввода, поля выбора, надписи с данными (текст, число), флажка и переключателя (`true` — отмечен, выбран; `false` — снят,
  не выбран; число или текст у переключателя — значение данных: выбран тот, у кого оно равно «ВыбираемомуЗначению»); сильнее значения, которое ставит код;
* `pages` — `{панель: страница}` (имя или номер с нуля) — выбранная страница; `page_visible` — `{панель: {страница: true|false}}`: скрытая страница без закладки, а если скрыта
  выбранная, выбирается первая видимая;
* `columns` — `{таблица: {колонка: true|false}}`; `buttons` — `{панель: {кнопка: true|false}}`;
* `current_element` — имя элемента (рисунок рамки фокуса не строит: имя идёт только в `notes`);
* `collapse` — `{панель: "Нет"|"Верх"|"Низ"|"Лево"|"Право"}`: свёрнутая панель не рисуется (в предприятии она исчезает целиком), соседи, привязанные к её краю, занимают её место.

Имена проверяются по форме: неизвестный элемент, панель, страница, колонка, кнопка и ключ вне схемы — `StateError` словами. Скрытый элемент места не освобождает: соседи в обычной
форме не сдвигаются; колонки пересчитываются по правилам ширин таблицы, кнопки — по раскладке панели.
"""
import json

from . import layout, render, structure as structure_mod
from . import edit

HIDDEN_MODES = ("hide", "hatch")
CONDITIONAL_MODES = ("plain", "hatch")
COLLAPSE_MODES = ("Нет", "Верх", "Низ", "Лево", "Право")
KEYS = ("size", "hidden", "conditional", "visible", "enabled", "read_only", "title", "values", "pages", "page_visible", "columns", "buttons", "current_element", "collapse")


class StateError(ValueError):
    """Состояние не читается или называет то, чего на форме нет."""


def read(path):
    """Содержимое `state.json`: словарь. Не JSON, не словарь, ключ вне схемы — `StateError`."""
    try:
        with open(path, encoding="utf-8-sig") as handle:
            data = json.loads(handle.read())
    except OSError as why:
        raise StateError(f"файл состояния «{path}» не читается: {why.strerror}") from why
    except ValueError as why:
        raise StateError(f"файл состояния «{path}» — не JSON: {why}") from why
    return check_shape(data)


def check_shape(data):
    if not isinstance(data, dict):
        raise StateError("состояние — объект JSON: {\"visible\": {…}, \"pages\": {…}, …}")
    extra = sorted(set(data) - set(KEYS))
    if extra:
        raise StateError(f"в состоянии ключи вне схемы: {', '.join(extra)} (бывают: {', '.join(KEYS)})")
    return data


class _Names:
    """Что есть на форме: элементы по имени, страницы панелей, колонки таблиц, кнопки панелей."""

    def __init__(self, doc):
        from .brief import content, facts, module_effects
        self.form = layout.read(doc)
        self.names = facts._Names(self.form, structure_mod.recognize(doc))
        self.labels = module_effects.label_map(self.names)
        self.pages = content.page_names(self.form, self.names)
        self.bars = content.bars(self.form, self.names)
        self._nodes = None

    def item(self, name, what="элемент"):
        if not isinstance(name, str) or not name.strip():
            raise StateError(f"имя пусто: нужно имя {what}")
        name = name.strip()
        full = name if name in self.names.item_of else None
        if full is None:
            found = self.labels.get(name.casefold()) or []
            if not found:
                raise StateError(f"{what.capitalize()} «{name}» на форме нет")
            if len(found) > 1:
                raise StateError(f"имя «{name}» неоднозначно (на форме {len(found)} элементов с таким именем): назовите полное — " + "; ".join(found))
            full = found[0]
        return self.names.item_of[full]

    def holder(self, name, type_, what):
        item = self.item(name, what)
        if item.type != type_:
            raise StateError(f"«{name}» — {item.type}, а не {what}")
        return item

    def page(self, panel, page):
        """`номер страницы` панели: `page` — подпись закладки, имя страницы, узел `T<N>` досье или номер с нуля (`frm_codec/pagerefs.py`)."""
        from . import pagerefs
        if self._nodes is None:
            self._nodes = pagerefs.nodes_of(self.form)
        try:
            return pagerefs.resolve(self.form, panel.index, page, self._nodes, what=f"панели «{panel.name}»")
        except ValueError as why:
            raise StateError(str(why)) from why

    def columns(self, table):
        from .render import tables
        return [c["name"] for c in tables.table_columns(table, True) if c["name"]]

    def buttons(self, bar):
        out = []

        def walk(items):
            for b in items:
                if b.get("name"):
                    out.append(b["name"])
                walk(b.get("children") or [])
        for row in self.bars:
            if row["item"] is bar:
                walk(row["buttons"])
        return out


def _flags(value, what):
    if not isinstance(value, dict):
        raise StateError(f"«{what}» — словарь {{имя: true|false}}")
    for name, flag in value.items():
        if not isinstance(flag, bool):
            raise StateError(f"в «{what}» у «{name}» нужно true или false")
    return value


def apply(doc, state, marks=None):
    """Накладывает состояние `state` (словарь `state.json`) на пометки `marks` (`render.CodeMarks`; нет — новые). Возвращает `(marks, (ширина, высота) или None)`.

    Явный запрос сильнее разбора кода: то, что он называет, переписывает записанное разбором. Режим скрытого `hidden` ставится в `marks.hatch_hidden` (нет в `state` — не трогается)."""
    state = check_shape(state)
    marks = marks if marks is not None else render.CodeMarks()
    names = _Names(doc)
    size = None
    if "size" in state:
        value = state["size"]
        if not (isinstance(value, list) and len(value) == 2 and all(isinstance(x, int) and not isinstance(x, bool) and x > 0 for x in value)):
            raise StateError("size — пара положительных целых [ширина, высота]")
        size = tuple(value)
        marks.requested.append(f"размер клиентской области {value[0]}×{value[1]}")
    if "hidden" in state:
        if state["hidden"] not in HIDDEN_MODES:
            raise StateError(f"hidden — «hide» или «hatch», а не «{state['hidden']}»")
        marks.hatch_hidden = state["hidden"] == "hatch"
    if "conditional" in state:
        if state["conditional"] not in CONDITIONAL_MODES:
            raise StateError(f"conditional — «plain» или «hatch», а не «{state['conditional']}»")
        marks.hatch_conditional = state["conditional"] == "hatch"
    def said(text):
        marks.requested.append(text)

    for name, flag in _flags(state.get("visible", {}), "visible").items():
        item = names.item(name)
        props = marks.applied.setdefault(item.index, {})
        marks.asked.add(("el", item.index, "видимость"))
        if flag:
            props.pop("видимость", None)
            marks.force_show.add(item.index)
        else:
            props["видимость"] = "Ложь"
            marks.force_show.discard(item.index)
            marks.hidden_src[("el", item.index)] = "запрос"
        said(f"{'показан' if flag else 'скрыт'} элемент «{name}»")
    for name, flag in _flags(state.get("enabled", {}), "enabled").items():
        item = names.item(name)
        marks.applied.setdefault(item.index, {}).pop("доступность", None)
        marks.forced_enabled[item.index] = flag
        said(f"элемент «{name}» {'доступен' if flag else 'недоступен'}")
    for name, flag in _flags(state.get("read_only", {}), "read_only").items():
        item = names.item(name)
        props = marks.applied.setdefault(item.index, {})
        marks.asked.add(("el", item.index, "только просмотр"))
        if flag:
            props["только просмотр"] = "Истина"
        else:
            props.pop("только просмотр", None)
        said(f"элемент «{name}»{'' if flag else ' не'} только для просмотра")
    titles = state.get("title", {})
    if not isinstance(titles, dict) or any(not isinstance(t, str) for t in titles.values()):
        raise StateError("title — словарь {элемент: текст}")
    for name, text in titles.items():
        marks.applied.setdefault(names.item(name).index, {})["заголовок"] = text
        marks.asked.add(("el", names.item(name).index, "заголовок"))
        said(f"заголовок «{name}» — «{text}»")
    values = state.get("values", {})
    if not isinstance(values, dict):
        raise StateError("values — словарь {элемент: true|false|текст|число}")
    from .brief import codenotes, module_effects
    for name, given in values.items():
        item = names.item(name)
        if item.type not in codenotes.VALUE_TYPES:
            raise StateError(f"у «{name}» ({item.type}) значения данных нет: values — поле ввода, поле выбора, надпись с данными, флажок и переключатель")
        if isinstance(given, bool):
            value = ("select" if item.type == "RadioButton" else "bool", given)          # у переключателя `true` — он выбран, а не «данные равны Истине»
        elif isinstance(given, (int, float)):
            value = ("number", str(given))
        elif isinstance(given, str):
            value = ("text", given)
        else:
            raise StateError(f"значение «{name}» — true, false, текст или число")
        if item.type == "CheckBox" and value[0] != "bool":
            raise StateError(f"флажок «{name}» принимает true или false")
        marks.field_values[item.index] = value
        marks.asked.add(("el", item.index, module_effects.VALUE_PROP))
        said(f"значение «{name}» — {value[1] if value[0] not in ('bool', 'select') else ('true' if value[1] else 'false')}")
    pages = state.get("pages", {})
    if not isinstance(pages, dict):
        raise StateError("pages — словарь {панель: страница}")
    for name, page in pages.items():
        panel = names.holder(name, "Panel", "панель")
        at = names.page(panel, page)
        marks.parts.setdefault("current_page", {})[panel.index] = at
        marks.asked.add(("cur", panel.index))
        said(f"у панели «{name}» выбрана страница «{page}»")
    visible_pages = state.get("page_visible", {})
    if not isinstance(visible_pages, dict):
        raise StateError("page_visible — словарь {панель: {страница: true|false}}")
    for name, flags in visible_pages.items():
        panel = names.holder(name, "Panel", "панель")
        for page, flag in _flags(flags, "page_visible").items():
            at = names.page(panel, page)
            props = marks.parts.setdefault("applied_pages", {}).setdefault((panel.index, at), {})
            marks.asked.add(("page", panel.index, at))
            if flag:
                props.pop("видимость", None)
                marks.hidden_src.pop(("page", panel.index, at), None)
            else:
                props["видимость"] = "Ложь"
                marks.hidden_src[("page", panel.index, at)] = "запрос"
            said(f"у панели «{name}» страница «{page}» {'показана' if flag else 'скрыта'}")
    columns = state.get("columns", {})
    if not isinstance(columns, dict):
        raise StateError("columns — словарь {таблица: {колонка: true|false}}")
    for name, flags in columns.items():
        table = names.holder(name, "TableBox", "табличное поле")
        have = {c.casefold(): c for c in names.columns(table)}
        for col, flag in _flags(flags, "columns").items():
            if col.casefold() not in have:
                raise StateError(f"у «{name}» нет колонки «{col}» (есть: {', '.join(have.values()) or 'нет'})")
            key = (table.index, col.casefold())
            props = marks.parts.setdefault("applied_columns", {}).setdefault(key, {})
            marks.asked.add(("col", table.index, col.casefold()))
            if flag:
                props.pop("видимость", None)
                marks.hidden_src.pop(("col", table.index, col.casefold()), None)
                marks.show_columns.add(key)
            else:
                props["видимость"] = "Ложь"
                marks.hidden_src[("col", table.index, col.casefold())] = "запрос"
                marks.show_columns.discard(key)
            said(f"у «{name}» колонка «{col}» {'показана' if flag else 'скрыта'}")
    buttons = state.get("buttons", {})
    if not isinstance(buttons, dict):
        raise StateError("buttons — словарь {панель: {кнопка: true|false}}")
    for name, flags in buttons.items():
        bar = names.holder(name, "CommandBar", "командная панель")
        have = {b.casefold(): b for b in names.buttons(bar)}
        for btn, flag in _flags(flags, "buttons").items():
            if btn.casefold() not in have:
                raise StateError(f"у «{name}» нет кнопки «{btn}» (есть: {', '.join(have.values()) or 'нет'})")
            gone = marks.parts.setdefault("removed_buttons", {}).setdefault(bar.index, [])
            marks.asked.add(("btn", bar.index, btn.casefold()))
            if flag and btn.casefold() in gone:
                gone.remove(btn.casefold())
                marks.hidden_src.pop(("btn", bar.index, btn.casefold()), None)
            elif not flag and btn.casefold() not in gone:
                gone.append(btn.casefold())
                marks.hidden_src[("btn", bar.index, btn.casefold())] = "запрос"
            elif not flag:
                marks.hidden_src[("btn", bar.index, btn.casefold())] = "запрос"
            said(f"у «{name}» кнопка «{btn}» {'показана' if flag else 'скрыта'}")
    if "current_element" in state:
        names.item(state["current_element"])
        said(f"активный элемент — «{state['current_element']}» (рамка фокуса не рисуется)")
    collapse = state.get("collapse", {})
    if not isinstance(collapse, dict):
        raise StateError("collapse — словарь {панель: режим}")
    for name, mode in collapse.items():
        panel = names.holder(name, "Panel", "панель")
        if mode not in COLLAPSE_MODES:
            raise StateError(f"свёртка панели «{name}» — одно из {', '.join(COLLAPSE_MODES)}, а не «{mode}»")
        if mode == "Нет":
            marks.collapsed.pop(panel.index, None)
            said(f"панель «{name}» развёрнута")
        else:
            marks.collapsed[panel.index] = mode
            said(f"панель «{name}» свёрнута ({mode}): не рисуется, соседи, привязанные к её краю, заняли её место")
    return marks, size

