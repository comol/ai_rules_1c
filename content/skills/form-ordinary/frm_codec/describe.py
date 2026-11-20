"""Образец: описание формы из самой формы.

Обратное к `generate`: форма платформы → описание из блоков-паттернов того же словаря (`command_bar`, `fields` с `columns`, `group`, `tabs`,
`table`). Описание по правилам движка даёт форму «как у образца» поверх чужой исходной формы. Второго словаря здесь нет: допустимость поля и колонки
решает сам движок (`generate._Resolver.control_of`, `type_problem`, `column_problem`), поэтому то, что попало в блоки, движок принимает, а чего не
принимает — стоит в `"skipped"` с причиной. Поле на реквизит ФОРМЫ (в описании `{"data": имя, "source": "form"}`) у формы вида `processing`
проверяет движок (`generate.FormAttributes.attr` и `control_of`: составной тип другого набора, чем «строка + число + справочник», произвольный тип
и ссылка не на справочник и документ выгрузки — в `skipped` с причиной движка); у формы объекта поле на реквизит формы пропускается. Подпись пары и
флажка, не равная синониму реквизита, передаётся ключом `caption`.

**Панель таблицы и колонка-флажок**: командная панель, источник действий которой — таблица того же родителя, — ключ `bar` блока `table` (у блока по
умолчанию она есть, отсутствие — `bar: false`); булев реквизит у колонки лежит в слоте ДанныеФлажка, и такая колонка — колонка блока, а не пропуск.
Привязку данных (`shell.resolve_binding`) и пару «надпись + поле» (`shell.find_label`) `describe` берёт из `frm_codec/shell.py` — тех же, по которым
`generate` находит в исходной форме элементы для переиспользования.

**Не молча.** Элемент, которого словарь блоков не знает (кнопка, картинка, надпись без поля, поле выбора, табличное поле на реквизит формы,
страница формы, вложенная панель, колонка без данных, поле типа без вида элемента), называется в `"skipped": [{"type", "name", "why"}]` — тип, имя и
причина; `"in"` — где стоит (страница панели). Счёт пропущенного по типам — `Result.counts`.

**Откуда имена.** С выгрузкой (`config`): привязка `[основной, {0, GUID}]` → реквизит объекта, `[основной, -N]` → стандартный, табличная часть — по
метаданным. Привязка к реквизиту ФОРМЫ (путь из одного шага) — имя реквизита формы: это данные обработки (привязка к ним — `bind attribute=` с
`copy_type`); у формы справочника и документа такое поле пропускается (описание формы объекта привязывается к реквизитам объекта), у формы обработки
оно данные, и тип его реквизита проверяет движок. Основной реквизит — тип `Object` обработки выгрузки даёт вид `processing` и реквизиты обработки
голыми именами; поле табличного документа без привязки — блок `spreadsheet`. Без выгрузки реквизит объекта имени не имеет — поле пропущено с
причиной «нужна выгрузка», а не угадано по имени элемента.

**Раскладка в блоки.** Пара — надпись слева от поля (ближайшая несвязанная надпись на той же высоте), флажок — сам по себе. Строки сетки — по
пересечению по вертикали; подряд идущие строки с одним числом пар — один блок `fields` с `columns` (одиночная строка после строк из 2–3 пар — свой
блок: у платформы одиночное поле стоит во всю ширину). Рамка (`GroupBox` с заголовком) забирает поля, чей центр внутри неё; рамка без заголовка и
рамка в рамке в блоки не идут (поля рамки в рамке отнесены к внешней, поля безымянной — к охватывающему уровню). Панель закладок — `tabs`: заголовок
страницы — её подпись (нет или повтор — «Страница N»), страница без блоков словаря в `tabs` не идёт. Таблица — `table` на табличную часть: колонки —
по привязкам колонок (все реквизиты части в порядке метаданных — без ключа `columns`); колонка без данных или такая, которой колонку с путём
`add_column` не запишет, — в `skipped`.

**Форма списка**: основной реквизит — динамический список объекта выгрузки (тип категории `List`) даёт вид `catalog.list`/`document.list` и блоки
`command_bar` (верх) и `table` (`"table": "Список"`, колонки — по путям данных `shell.list_column_key`; без ключа `columns` у колонок конструктора);
поля, надписи и рамки над и под списком, нижняя панель, вторая таблица на список, колонки, которых движок с нуля не напишет (`edit.listcols.classify`:
булева, составной тип, `Родитель`, `Владелец`, `Проведен`…), и колонки без данных — в `skipped` с причиной. **Дерево групп иерархического
справочника** (табличное поле на второй реквизит-список того же объекта и разделитель между ним и списком) — не «вторая таблица» и не пропуск: ключ
`tree: true` блока `table` (дерево исходной формы при генерации остаётся как есть).

**Размер формы и ширина поля.** Нормы не извлекаются: числа — нормы вида. Образец несёт `size` — `[ширина, высота]` формы платформы, если он не равен
тому, что движок даст описанию «по содержимому» (`_content_size`: тот же `generate.plan_notes` без `size`; сторона, где платформа уже содержимого,
берёт содержимое — движок размер меньше содержимого не принимает, `size:narrower`); у формы списка размера нет, без выгрузки сравнивать не с чем
(`size:unknown`). И несёт `width` у поля, которое у платформы НЕ РАСТЯГИВАЕТСЯ при растяжении окна (рост ширины `cR − cL` по `layout.coefficients` меньше
0,9 — остаётся на месте или сдвигается), последнее в ряду блока `fields` верхнего уровня формы (внутренняя колонка сетки остаётся на месте всегда; рамки и страницы панелей — нет)
и расположено не там, где его поставил бы движок (правый край ≠ форма минус отступ нормы вида `field_right_margin`; движок растянул бы такое поле по
решению для класса, а платформа — нет). Растущее и частично растущее поле (`width:grows`, `width:partly`), поле у края колонки, поле уже минимума
платформы (`width:below_minimum`) и поле ряда шире колонок блока ширины не несут. Заданная ширина у `generate` значит «не растягивается» (привязка влево,
`_Layout.fields`).

**Учёт поэлементный.** `elements:total` — все элементы ДОКУМЕНТА (обход `edit.base.holders`, не модели раскладки); каждый узел попадает ровно в одно
из двух множеств — описанных или пропущенных, а `elements:lost` и `elements:double` (должны быть 0) считаются как разность и пересечение множеств,
а не как сумма. Дети элемента без разобранных координат (панель, которую раскладка не открывает) называются поимённо: «панель не разобрана, детей N».
"""
import collections
import copy
import dataclasses

from . import patterns, generate, generate_list, layout, metadata, rowgrid, shell, textgap
from .edit import base as ed_base, columns as ed_columns, datapath, listcols
from .edit.base import EditError
from .edit.names import (ATTR_HEAD, ATTR_NAME, CAPTION, CONTENT, ELEMENTS, ITEMS, LS_ITEMS, NAME, NAME_BLOCK, PAGES,
                         PAGE_CAPTION, PAGE_ITEMS, SHOW_TABS, TEXT)


class DescribeError(ValueError):
    """Форму не разобрать в описание — словами (подкласс `ValueError`: CLI печатает его как отказ)."""


# Надпись и поле одной пары — правило `shell.find_label` (зазор `MAX_LABEL_GAP`, нахлёст `LABEL_OVERLAP`): одно на `describe` и на `generate`, который по нему находит надпись поля исходной формы для переиспользования.
MAX_LABEL_GAP = shell.MAX_LABEL_GAP
LABEL_OVERLAP = shell.LABEL_OVERLAP
MAX_COLUMNS = generate.MAX_COLUMNS

FIELD_TYPES = ("TextBox", "CheckBox")
EDGE_MARGIN = 8                  # правый отступ поля у края формы, когда нормы вида нет (так у платформы: форма − 8)
ROW_ORDER, TABLE_ORDER, GROUP_ORDER, TABS_ORDER = 0, 1, 2, 3


@dataclasses.dataclass
class Result:
    """Описание и то, что про него надо знать: слова для отчёта и счёт."""
    description: dict
    notes: list
    counts: collections.Counter       # `skipped:<тип>` — пропущено по видам элементов, `blocks:<ключ>` — блоков, `fields`, `columns`;
                                      # учёт: `elements:total|described|skipped|lost|double`; подписи: `captions:same|carried|unread`


# ── Безопасное чтение документа ───────────────────────────────────────────────────────────────

def _dict(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def _int(value):
    return isinstance(value, int) and not isinstance(value, bool)


_text = shell._text


def _caption(item):
    """Подпись элемента: у него она одна, иначе (нет или несколько) — `None`."""
    return shell.caption_of(item.node)


def _form_title(doc):
    title = _dict(_dict(doc.get("form")).get("title")).get(CAPTION)
    return _text(title)


_same_text = shell.same_text


def _multiline(item):
    """Поле ввода в многострочном режиме (`multi_line` — истина в блоке значения поля)."""
    return textgap.is_multi_line(item.node)


def _children(node):
    block = node.get(ELEMENTS) if isinstance(node, dict) else None
    items = block.get(ITEMS) if isinstance(block, dict) else None
    return [c for c in items if isinstance(c, dict)] if isinstance(items, list) else []


def _nested(node):
    """Все элементы под узлом, на любой глубине (сверху вниз)."""
    for child in _children(node):
        yield child
        yield from _nested(child)


class _Bare:
    """Элемент документа без разобранных координат: вид, имя и узел — всё, что нужно учёту и причине."""

    def __init__(self, node):
        self.node, self.type = node, str(node.get("type"))
        names = node.get(NAME_BLOCK)
        self.name = names.get(NAME) if isinstance(names, dict) and isinstance(names.get(NAME), str) else None


class _Ctx:
    """Всё, что одно извлечение знает о форме: модель раскладки, привязки, объект выгрузки и имена."""

    def __init__(self, doc, config, form_use, kind, object_name):
        self.doc, self.config = doc, config
        self.form = layout.read(doc)
        attributes, rows = datapath._attributes(doc)
        self.attributes = attributes
        head = _dict(attributes.get(ATTR_HEAD))
        main = head.get(datapath.MAIN_ATTRIBUTE_ID)
        self.main = main if _int(main) else None
        self.form_attrs = {}
        self.main_row = None
        for row in rows:
            ident = datapath._id_of(row)
            if _int(ident):
                self.form_attrs[ident] = row.get(ATTR_NAME) if isinstance(row.get(ATTR_NAME), str) else None
                if ident == self.main:
                    self.main_row = row
        self.bound = {}
        for row in datapath.binding_rows(attributes):
            steps = _dict(row.get("path")).get("steps")
            element = row.get(datapath.BIND_ELEMENT)
            if _int(element) and isinstance(steps, list) and element not in self.bound:
                self.bound[element] = [s if isinstance(s, dict) else {} for s in steps]
        self.notes = []
        self.counts = collections.Counter()
        self.skipped = []
        self.described, self.skipped_ids = set(), set()      # узлы документа (`id`), учтённые описанием и пропуском
        self.obj = None
        self.list_obj = None  # форма СПИСКА: основной реквизит — динамический список объекта выгрузки (тип категории `List`)
        if config is not None and self.main_row is not None:
            guid = datapath._type_guid(self.main_row)
            hit = config.object_by_type_id(guid) if guid else None
            if hit and hit[1].lower() == "object":
                self.obj = hit[0]
            elif hit and hit[1].lower() == listcols.LIST_CATEGORY and hit[0].kind in generate_list.LIST_KINDS.values():
                self.list_obj = hit[0]
        self.role = form_use
        self.resolver = None
        self.processing = False          # форма обработки (вид processing): данные — реквизиты формы и реквизиты обработки
        self.sheets = set()              # имена уже описанных полей табличного документа
        self.seen = {}
        self.kind, self.object_name = kind, object_name
        self._coefficients = self._edge_margin = None

    # привязка элемента → что она называет (правило одно с `generate`: `shell.resolve_binding`)
    def binding(self, item):
        return shell.resolve_binding(self.bound.get(item.index), self.main, self.form_attrs, self.obj)

    def clean(self, text):
        """Причина без пути к выгрузке на диске: описание уезжает дальше машины, на которой его сняли."""
        root = getattr(self.config, "root", None)
        return text.replace(f"«{root}»", "«выгрузке»").replace(str(root), "выгрузка") if root else text

    def mark(self, item):
        """Элемент показан описанием (поле, надпись пары, рамка, таблица, панель, панель команд)."""
        if id(item.node) in self.described or id(item.node) in self.skipped_ids:
            self.counts["elements:double"] += 1
        self.described.add(id(item.node))

    def skip(self, item, why, where=None):
        why = self.clean(why)
        entry = {"type": str(item.type)}
        if item.name:
            entry["name"] = item.name
        entry["why"] = why
        if where:
            entry["in"] = where
        self.skipped.append(entry)
        self.counts[f"skipped:{item.type}"] += 1
        if id(item.node) in self.described or id(item.node) in self.skipped_ids:
            self.counts["elements:double"] += 1
        self.skipped_ids.add(id(item.node))

    def unresolved(self, what):
        """Почему имя объекта взять неоткуда: обработка — метаданные обработок не читаются; иначе — выгрузки нет либо объект по ней не найден."""
        if self.config is None:
            return f"{what}: имя даёт выгрузка (--config) или, у внешней обработки, корневой XML (--root-xml), их не дано"
        if not self.config.has_dump:
            return (f"{what}: объект формы по корневому XML не найден (основной реквизит формы — не тип Object этого внешнего объекта) — "
                    "имя реквизита объекта взять неоткуда")
        if self.kind == "processing":
            said = self.config.failed_reason(self.object_name) if self.object_name else None
            why = (f"файл обработки «{self.object_name}» не прочитан: {said}" if said else
                   "основной реквизит формы — не тип этой обработки в выгрузке"
                   + (f"; не прочитаны файлы обработок: {'; '.join(f'{k} — {v}' for k, v in sorted(self.config.failed.items()))}"
                      if self.config.failed else ""))
            return f"{what}: объект обработки по выгрузке не найден ({why}) — имя реквизита объекта взять неоткуда"
        return f"{what}: имя даёт выгрузка (--config), а объект формы по ней не найден (основной реквизит формы не объект этой выгрузки)"

    def expected_text(self, kind, name):
        """Подпись, которую движок поставит сам при отсутствии `caption`: синоним реквизита объекта, у реквизита формы — его имя;
        `None` — не узнать."""
        if kind == "form":
            return name
        if kind == "object" and self.resolver is not None:
            try:
                return self.resolver.text_of(datapath.resolve(self.obj, name, self.role))
            except (EditError, generate.GenerateError):
                return None
        return None

    def coefficients(self):
        """Коэффициенты привязок модели раскладки формы (`layout.coefficients`, без скрытия страниц): считаются один раз."""
        if self._coefficients is None:
            self._coefficients = layout.coefficients(self.form, hide=False)
        return self._coefficients

    def edge_margin(self):
        """Правый отступ поля у края колонки: норма вида `field_right_margin` (большинство форм в конфигурациях); вида нет или нормы нет — `EDGE_MARGIN`."""
        if self._edge_margin is None:
            value = patterns.norm(patterns.load(), self.kind, "field_right_margin") if self.kind else None
            self._edge_margin = value if _int(value) else EDGE_MARGIN
        return self._edge_margin

    def entry(self, name, kind, text, present):
        """Запись поля для `fields`: имя либо объект `{"data", "source"?, "caption"?}`. `text` — подпись надписи пары (у флажка — его заголовок),
        `present` — есть ли такая надпись вовсе. Подпись, не равная синониму, передаётся ключом `caption`."""
        entry = {"data": name}
        if kind == "form":
            entry["source"] = "form"  # реквизит формы, а не объекта: голое имя их не различает
        if present and text is None:
            self.counts["captions:unread"] += 1         # подпись есть, а прочитать её нельзя: движок поставит синоним
        elif text is not None:
            expected = self.expected_text(kind, name)
            if expected is not None and _same_text(text, expected):
                self.counts["captions:same"] += 1
            else:
                entry["caption"] = text
                self.counts["captions:carried"] += 1
        return entry if len(entry) > 1 else name


# ── Поле, таблица, колонки ────────────────────────────────────────────────────────────────────

def _field_name(ctx, item, kind, name, where):
    """Имя реквизита для блока `fields` либо `None` (причина — в `skipped`)."""
    if kind == "none":
        ctx.skip(item, "поле без привязки к данным: имя реквизита взять неоткуда", where)
    elif kind == "object_unresolved":
        ctx.skip(item, ctx.unresolved("реквизит объекта"), where)
    elif kind == "form":
        if ctx.processing:                      # данные обработки: тип реквизита формы проверяет движок (`FormAttributes`), как и поле объекта
            try:
                target = datapath.Target("formattr", name, {}, ctx.resolver.form.attr(name))
                ctx.resolver.control_of(target)
            except generate.GenerateError as e:
                ctx.skip(item, f"«{name}»: {e}", where)
                return None
            return name
        if ctx.obj is not None:
            ctx.skip(item, f"реквизит формы «{name}», не объекта: описание формы объекта привязывается к реквизитам объекта", where)
        else:
            return name
    elif kind == "table":
        ctx.skip(item, f"привязано к табличной части «{name}»: её показывает блок table, а не поле", where)
    elif kind == "object":
        try:
            target = datapath.resolve(ctx.obj, name, ctx.role)
            control, _choice = ctx.resolver.control_of(target)
            reason = ctx.resolver.type_problem(target, control)
        except (EditError, generate.GenerateError) as e:
            ctx.skip(item, f"«{name}»: {e}", where)
            return None
        if reason:
            ctx.skip(item, f"«{name}»: {reason}", where)
            return None
        return name
    else:
        ctx.skip(item, "привязка не к реквизиту объекта и не к реквизиту формы (путь длиннее или иного вида)", where)
    return None


def _key(name, kind):
    """Ключ учёта «один реквизит — одно поле»: у реквизита формы свой (одно имя бывает и у реквизита формы, и у реквизита объекта)."""
    return f"форма.{name}" if kind == "form" else name


def _claim(ctx, item, data, where):
    """Один реквизит — одно поле: повтор уходит в `skipped`."""
    if data in ctx.seen:
        ctx.skip(item, f"«{data}» уже показан ({ctx.seen[data]}): одному реквизиту — одно поле", where)
        return False
    ctx.seen[data] = where or "верх формы"
    return True


def _table_block(ctx, item, ts_name, where):
    """Блок `table` на табличную часть либо `None`."""
    ts = next(t for t in ctx.obj.tables if t.name == ts_name)
    try:
        datapath.resolve(ctx.obj, ts_name, ctx.role)
    except EditError as e:
        ctx.skip(item, f"«{ts_name}»: {e}", where)
        return None
    if not _claim(ctx, item, f"Объект.{ts_name}", where):
        return None
    names, seen = [], set()
    block = ed_columns.columns_of(item.node)
    for column in _list(_dict(block).get(ed_columns.COLUMN_ITEMS)):
        base = ed_columns._column_base(column)
        head = _dict(_dict(base).get(ed_columns.COLUMN_HEAD))
        label = head.get(ed_columns.COLUMN_NAME) if isinstance(head.get(ed_columns.COLUMN_NAME), str) else None
        cell = {"type": "TableBoxColumn", **({"name": label} if label else {}), "in": item.name or ts_name}
        path = _dict(base).get(datapath.COLUMN_PATH)
        if path == datapath.NO_DATA:  # колонка-флажок: булев реквизит конструктор пишет в слот ДанныеФлажка, а не в Данные
            check = _dict(base).get(ed_columns.COLUMN_CHECK_PATH)
            if isinstance(check, list) and len(check) == 2 and check[0] == 0 and isinstance(check[1], dict):
                path = check
        if path == [datapath.ROW_NUMBER_ID]:                 # номер строки — колонка без реквизита; генерация ставит её «по просьбе»
            if datapath.ROW_NUMBER in seen:
                ctx.skipped.append({**cell, "why": "номер строки уже показан колонкой"})
                ctx.counts["skipped:TableBoxColumn"] += 1
            else:
                seen.add(datapath.ROW_NUMBER)
                names.append(datapath.ROW_NUMBER)
            continue
        if not (isinstance(path, list) and len(path) == 2 and path[0] == 0 and isinstance(path[1], dict)):
            ctx.skipped.append({**cell, "why": "колонка без данных (путь не на реквизит части)"})
            ctx.counts["skipped:TableBoxColumn"] += 1
            continue
        attr = next((a for a in ts.attributes if a.uuid == path[1].get("guid")), None)
        if attr is None:
            ctx.skipped.append({**cell, "why": "колонка не на реквизит этой табличной части"})
            ctx.counts["skipped:TableBoxColumn"] += 1
            continue
        reason = ctx.resolver.column_problem(attr)
        if reason is None and attr.name in seen:
            reason = f"реквизит «{attr.name}» уже показан колонкой: одна колонка на реквизит"
        if reason is not None:
            ctx.skipped.append({**cell, "why": ctx.clean(reason)})
            ctx.counts["skipped:TableBoxColumn"] += 1
            continue
        seen.add(attr.name)
        names.append(attr.name)
    if not names:
        ctx.seen.pop(f"Объект.{ts_name}", None)
        ctx.skip(item, f"табличная часть «{ts_name}»: нет колонок, которые описание выразит", where)
        return None
    ctx.mark(item)
    out = {"table": f"{datapath.OBJECT_WORD}.{ts_name}"}
    if names != [a.name for a in ts.attributes]:
        out["columns"] = names
    ctx.counts["columns"] += len(names)
    return out


# ── Сетка пар ─────────────────────────────────────────────────────────────────────────────────

@dataclasses.dataclass
class _Cell:
    name: str                    # реквизит
    entry: object                # что идёт в `fields`: имя либо `{"data", "source"?, "caption"?}`
    top: int
    bottom: int
    left: int
    item: object = None  # поле (элемент модели раскладки): ширина и привязка справа — у него


def _overlap(a_top, a_bottom, b_top, b_bottom):
    return min(a_bottom, b_bottom) - max(a_top, b_top)


def _rows(cells):
    """Ячейки → строки по пересечению по вертикали, внутри строки слева направо."""
    rows = []
    for cell in sorted(cells, key=lambda c: (c.top, c.left)):
        if rows:
            first = rows[-1][0]
            height = min(cell.bottom - cell.top, first.bottom - first.top)
            if height > 0 and _overlap(cell.top, cell.bottom, first.top, first.bottom) * 2 >= height:
                rows[-1].append(cell)
                continue
        rows.append([cell])
    return [sorted(r, key=lambda c: c.left) for r in rows]


def _runs(rows):
    """Строки одного куска → блоки `fields`: подряд идущие строки с одним числом пар — один блок. Одиночная строка после строк
    из нескольких пар — свой блок на одну колонку: внутренняя колонка сетки остаётся на месте, а одиночное поле у платформы занимает
    всю ширину (последняя колонка растягивается вправо). Правило общее с `structure` (`rowgrid.runs`)."""
    return rowgrid.runs(rows)


def _segments(rows, separators):
    """Ряды → куски: таблица, рамка или панель между двумя рядами рвёт сетку (блок `fields` через неё не идёт). Правило общее с
    `structure` (`rowgrid.joined`)."""
    out = []
    for row in rows:
        if out and rowgrid.joined(out[-1][-1][0].top, row[0].top, separators):
            out[-1].append(row)
        else:
            out.append([row])
    return out


def _fixed_width(ctx, cell):
    """Ширина поля, которую образец обязан нести, либо `None`. Поле последнее в ряду, у платформы НЕ РАСТЯГИВАЕТСЯ при растяжении окна и расположено не у края колонки,
    где его поставил бы движок (форма минус правый отступ нормы вида): иначе движок растянул бы его по решению для класса, а платформа — нет. Растягивается ли поле, определяется
    по РОСТУ ширины (`layout.horizontal_behaviour`: `cR − cL`), а не по правому коэффициенту: поле с cL = cR = 1 («Код» справочника: обе границы идут с краем
    формы, ширина постоянна) ширину несёт. Растущее поле, частично растущее (пропорциональная шапка: ширина не постоянна, но и не растягивается целиком — выбор
    зависит от конфигурации) и поле в цикле правил ширины не несут."""
    item = cell.item
    if item is None or item.type != "TextBox":
        return None
    found = ctx.coefficients().get(item.index)
    behaviour = None if found is None else layout.horizontal_behaviour(found[2], found[3])
    if behaviour in (None, layout.GROWS, layout.PARTLY):
        ctx.counts["width:rule_cycle" if behaviour is None else "width:grows" if behaviour == layout.GROWS else "width:partly"] += 1
        return None
    width = item.box[2] - item.box[0]
    if item.box[2] == ctx.form.width - ctx.edge_margin():
        ctx.counts["width:at_the_column_edge"] += 1
        return None
    if width < generate.PLATFORM_MIN_FIELD_W:
        ctx.counts["width:below_minimum"] += 1
        return None
    ctx.counts["width:carried"] += 1
    ctx.counts["width:carried_moving"] += int(behaviour == layout.MOVES)  # из них поля со сдвигающимися границами (cL = cR = 1): ширину несут
    return width


def _fields_blocks(ctx, rows, where, separators=(), widths=False):
    """Ряды ячеек → блоки `fields` `(верх, блок)`: подряд идущие ряды с одним числом пар — один блок с `columns`. `widths` — родитель сама форма: последнее поле ряда несёт ширину,
    если у платформы оно не растягивается и расположено не у края колонки (`_fixed_width`)."""
    out = []
    for segment in _segments(rows, separators):
        for run in _runs(segment):
            names, columns = [], run["n"]
            for row in run["rows"]:
                entries = [c.entry for c in row]
                if widths and len(row) <= MAX_COLUMNS:          # строка шире колонок перекладывается: последнее поле ряда уже не последняя колонка
                    width = _fixed_width(ctx, row[-1])
                    if width is not None:
                        last = entries[-1]
                        entries[-1] = {**(last if isinstance(last, dict) else {"data": last}), "width": width}
                names += entries
            if columns > MAX_COLUMNS:
                ctx.notes.append(f"{where or 'верх формы'}: в строке {columns} пар, а колонок в блоке не больше "
                                 f"{MAX_COLUMNS} — строка разложится по {MAX_COLUMNS}")
                columns = MAX_COLUMNS
                ctx.counts["rows_wider_than_columns"] += 1
            block = {"fields": names}
            if columns > 1:
                block["columns"] = columns
            ctx.counts["fields"] += len(names)
            out.append((run["rows"][0][0].top, block))
    return out


def _pair(ctx, fields, labels):
    """Поля с их надписями → ячейки; использованные надписи уходят из `labels`."""
    cells = []
    for item, name, kind in fields:
        label = None
        ctx.mark(item)
        text, present = (_caption(item), True) if item.type == "CheckBox" else (None, False)
        if item.type == "TextBox":
            label = shell.find_label(item, labels)
            if label is not None:
                labels.remove(label)
                ctx.mark(label)
                text, present = _caption(label), True
        left = label.box[0] if label is not None else item.box[0]
        cells.append(_Cell(name, ctx.entry(name, kind, text, present), item.box[1], item.box[3], left, item))
    return cells


def _inside(item, frame):
    cx, cy = (item.box[0] + item.box[2]) / 2, (item.box[1] + item.box[3]) / 2
    return frame.box[0] <= cx <= frame.box[2] and frame.box[1] <= cy <= frame.box[3]


def _area(item):
    return max(0, item.box[2] - item.box[0]) * max(0, item.box[3] - item.box[1])


# ── Родитель: форма целиком или страница панели ───────────────────────────────────────────────

def _scope(ctx, items, where, allow_tabs, top_level):
    """Блоки одного родителя (формы или страницы панели) сверху вниз."""
    form = ctx.form
    entities = []                                # (верх, порядок, блок); у панели «блок» — сам элемент
    if top_level:                                # страницы самой формы: на них свои рамки и поля, а места у них общие
        rest = []
        for item in items:
            if item.page not in (0, None):
                ctx.skip(item, f"страница формы {item.page}: словарь блоков страниц формы не знает", where)
                if item.type == "Panel":
                    _skip_inside(ctx, item)
            else:
                rest.append(item)
        items = rest
    frames = [i for i in items if i.type == "GroupBox" and i.visible]
    nested = {id(f) for f in frames if any(g is not f and _inside(f, g) and _area(g) > _area(f) for g in frames)}
    owner = {}
    for item in items:
        if item.type == "GroupBox" or not item.visible:
            continue
        mine = [f for f in frames if id(f) not in nested and _inside(item, f)]
        if mine:
            owner[id(item)] = max(mine, key=_area)
    titled = {id(f): _caption(f) for f in frames if id(f) not in nested}
    for f in frames:
        if id(f) in nested:
            ctx.skip(f, "рамка внутри рамки: поля отнесены к внешней, а рамка без блока в словаре", where)
        elif not titled[id(f)]:
            ctx.skip(f, "рамка без заголовка: блок group требует заголовок, поля отнесены к охватывающему уровню", where)
    named = {id(f) for f in frames if titled.get(id(f))}
    labels = []
    fields_free, fields_in = [], collections.defaultdict(list)
    bars_top = bars_bottom = None
    tables, sheets = [], []
    table_index = {i.index for i in items if i.type == "TableBox" and i.visible}
    table_bar_of = {i.index: _dict(i.node.get("name_block")).get("action_source") for i in items
                    if i.type == "CommandBar" and i.visible and _dict(i.node.get("name_block")).get("action_source") in table_index}
    table_bars = collections.defaultdict(list)  # индекс таблицы → ВСЕ её панели (у таблицы их бывает несколько)
    for item in sorted(items, key=lambda i: (i.box[1], i.box[0]) if i.box else (0, 0)):
        if item.type == "GroupBox" and item.visible:
            continue                                 # рамка — выше, по своему заголовку
        if not item.visible:
            ctx.skip(item, "элемент невидим", where)
            if item.type == "Panel":
                _skip_inside(ctx, item)
            continue
        if item.type == "CommandBar":
            if item.index in table_bar_of:                 # панель таблицы: источник действий — таблица этого родителя; её показывает ключ `bar` блока table
                table_bars[table_bar_of[item.index]].append(item)
                continue
            if top_level and item.box[1] < 12 and bars_top is None:
                bars_top = item
                ctx.mark(item)
            elif top_level and item.box[3] >= form.height - 2 and bars_bottom is None:
                bars_bottom = item
                ctx.mark(item)
            else:
                ctx.skip(item, "командная панель не формы (панель таблицы или кнопок): в словаре только верхняя и нижняя панели формы", where)
            continue
        if item.type == "Panel":
            if allow_tabs:
                entities.append((item.box[1], TABS_ORDER, item))
                _note_frame(ctx, item, "панель закладок", owner, named, titled, where)
            else:
                ctx.skip(item, "панель закладок вне верха формы: в словаре панели только на верхнем уровне", where)
                _skip_inside(ctx, item)
            continue
        kind, name = ctx.binding(item)
        if item.type == "Label":
            if kind == "none":
                labels.append(item)
            else:
                ctx.skip(item, "надпись, привязанная к данным: словарь надписей без поля не знает", where)
            continue
        if item.type == "TextBox" and _multiline(item):
            ctx.skip(item, "многострочное поле: словарь блоков многострочного режима не знает (движок ставит однострочное)", where)
            continue
        if item.type in FIELD_TYPES:
            data = _field_name(ctx, item, kind, name, where)
            if data is not None:
                (fields_in[id(owner[id(item)])] if id(item) in owner and id(owner[id(item)]) in named else fields_free).append(
                    (item, data, kind))
            continue
        if item.type == "TableBox":
            if kind == "table":
                tables.append((item, name))
                _note_frame(ctx, item, "таблица", owner, named, titled, where)
            elif kind == "form":
                ctx.skip(item, f"таблица на реквизит формы «{name}», а не на табличную часть: describe описывает блоком table только табличную часть; `generate` ставит таблицу на реквизит формы блоком table с \"source\": \"form\" и колонками", where)
            else:
                ctx.skip(item, "табличное поле не на табличную часть объекта" if kind != "object_unresolved"
                         else ctx.unresolved("табличная часть"), where)
            continue
        if item.type == generate.SHEET and ctx.processing:
            if kind != "none":
                ctx.skip(item, "поле табличного документа с привязкой к данным: блок spreadsheet — поле без привязки "
                               "(у корпуса привязок к такому элементу нет ни одной)", where)
            elif not item.name or not generate.IDENT.match(item.name) or item.name in ctx.sheets:
                ctx.skip(item, "у поля табличного документа нет имени-идентификатора либо оно повторяется: блок spreadsheet называет поле", where)
            else:
                ctx.sheets.add(item.name)
                sheets.append(item)
                _note_frame(ctx, item, "поле табличного документа", owner, named, titled, where)
            continue
        ctx.skip(item, "вид элемента вне словаря блоков (command_bar, fields, group, tabs, table"
                       + (", spreadsheet)" if ctx.processing else ")"), where)
    for item in sheets:
        ctx.mark(item)
        entities.append((item.box[1], TABLE_ORDER, {"spreadsheet": item.name}))
    for item, ts_name in tables:
        block = _table_block(ctx, item, ts_name, where)
        if block is not None:
            bars = table_bars.pop(item.index, [])
            if bars:
                bar = shell.nearest_bar(item, bars)      # блок table показывает ОДНУ панель — ближайшую к таблице; остальные — в пропуск словами
                ctx.mark(bar)
                ctx.counts["bars:table"] += 1
                for other in bars:
                    if other is not bar:
                        ctx.skip(other, f"вторая командная панель того же источника-таблицы («{bar.name}» ближе к таблице): блок table показывает одну панель", where)
            else:
                block["bar"] = False                 # у блока table по умолчанию панель есть (`generate.TABLE_BAR_DEFAULT`): её отсутствие — ключ
            entities.append((item.box[1], TABLE_ORDER, block))
    for bars in table_bars.values():                 # панели таблицы, которой нет в описании (таблица пропущена)
        for bar in bars:
            ctx.skip(bar, "командная панель таблицы, которую описание не показывает блоком table (таблица пропущена или не на табличную часть)", where)
    separators = [e[0] for e in entities] + [f.box[1] for f in frames if id(f) in named]
    free = [(i, n, k) for i, n, k in fields_free if _claim(ctx, i, _key(n, k), where)]
    cells = _pair(ctx, free, labels)
    for frame in frames:
        if id(frame) not in named:
            continue
        mine = [(i, n, k) for i, n, k in fields_in[id(frame)] if _claim(ctx, i, _key(n, k), where)]
        blocks = [b for _t, b in _fields_blocks(ctx, _rows(_pair(ctx, mine, labels)), where)]
        if not blocks:
            ctx.skip(frame, "рамка без полей словаря: блок group держит только fields", where)
            continue
        ctx.mark(frame)
        entities.append((frame.box[1], GROUP_ORDER, {"group": titled[id(frame)], "blocks": blocks}))
    for label in labels:                         # не пара ни одного поля
        ctx.skip(label, "надпись без поля рядом: из надписей словарь делает только пару «надпись + поле»", where)
    entities += [(top, ROW_ORDER, block) for top, block in _fields_blocks(ctx, _rows(cells), where, separators, widths=top_level)]
    entities.sort(key=lambda e: (e[0], e[1]))
    return [(order, block) for _top, order, block in entities], bars_top, bars_bottom


def _note_frame(ctx, item, what, owner, named, titled, where):
    """Таблица или панель закладок внутри рамки: блок `group` держит только `fields`, и у сгенерированной формы она встанет ВНЕ рамки, а рамка охватит
    одни поля."""
    frame = owner.get(id(item))
    if frame is not None and id(frame) in named:
        ctx.counts["blocks_left_the_frame"] += 1
        ctx.notes.append(f"{where or 'верх формы'}: {what} «{item.name or item.type}» стояла внутри рамки «{titled[id(frame)]}», "
                         "а блок group держит только fields — у сгенерированной формы она встанет вне рамки")


def _skip_inside(ctx, panel):
    """Всё, что стоит внутри пропущенной панели, называется поимённо: без панели блоков для него нет."""
    holder = ctx.form.holders.get(panel.index)
    for child in holder.children if holder is not None else ():
        ctx.skip(child, f"внутри пропущенной панели «{panel.name}»", panel.name)
        if child.type == "Panel":
            _skip_inside(ctx, child)


def _skip_raw_children(ctx, raw):
    """Дети элемента без разобранных координат: раскладка в него не заходит, но документ их держит. Называются поимённо, с числом всех вложенных."""
    below = list(_nested(raw.node))
    if not below:
        return
    label = raw.name or str(raw.type)
    for node in below:
        ctx.skip(_Bare(node), f"внутри элемента без разобранных координат «{label}»: панель не разобрана, детей {len(below)}", raw.name)


def _tabs_block(ctx, panel):
    """Блок `tabs` из панели закладок либо `None`."""
    holder = ctx.form.holders.get(panel.index)
    block = ed_base.layout_block(panel.node, need=False)
    pages = _list(_dict(_dict(block).get(PAGES)).get(PAGE_ITEMS))
    if holder is None or not pages:
        ctx.skip(panel, "панель без разобранных страниц", None)
        _skip_inside(ctx, panel)
        return None
    if _dict(block).get(SHOW_TABS) == "DontUse":
        ctx.counts["tabs_not_shown"] += 1
        ctx.notes.append(f"{panel.name or 'Панель'}: у панели закладок вид «Не отображать» — словарь вида закладок не выражает, "
                         "движок поставит закладки «Сверху»")
    by_page = collections.defaultdict(list)
    for child in holder.children:
        by_page[child.page if _int(child.page) else 0].append(child)
    out, titles = [], set()
    for at, page in enumerate(pages):
        title = _text(_dict(page).get(PAGE_CAPTION))
        place = f"{panel.name or 'Панель'}/{title or f'Страница {at + 1}'}"
        if not title or title in titles:
            if title:
                ctx.notes.append(f"{place}: заголовок страницы повторяется — страница названа «Страница {at + 1}»")
            title = f"Страница {at + 1}"
        made, _bt, _bb = _scope(ctx, by_page.get(at, []), place, False, False)
        blocks = [block for _order, block in made]
        if not blocks:
            ctx.skipped.append({"type": "PanelPage", "name": title, "why": "страница без блоков словаря", "in": panel.name or "Панель"})
            ctx.counts["skipped:PanelPage"] += 1
            continue
        titles.add(title)
        out.append({"page": title, "blocks": blocks})
    for at, extra in by_page.items():
        if at >= len(pages):
            for child in extra:
                ctx.skip(child, f"элемент на странице {at}, которой у панели нет", panel.name)
    if not out:
        ctx.skip(panel, "ни на одной странице нет блоков словаря", None)
        return None
    ctx.mark(panel)
    return {"tabs": out}


# Форма списка

LIST_WHY = {"TextBox": "поле над или под списком (отбор): блок fields у формы списка не делается — общего скелета у корпуса нет",
            "CheckBox": "флажок над или под списком (отбор): блок fields у формы списка не делается — общего скелета у корпуса нет",
            "ComboBox": "поле выбора над или под списком (отбор): блок fields у формы списка не делается — общего скелета у корпуса нет",
            "Label": "надпись формы списка: блок fields у формы списка не делается — общего скелета у корпуса нет",
            "GroupBox": "рамка формы списка: блок group у формы списка не делается — общего вида у корпуса нет",
            "Splitter": "разделитель формы списка без дерева групп: словарь блоков его не знает"}


def _list_table_block(ctx, item, table, obj):
    """Блок `table` формы списка либо `None`: колонки — по ключам исходной формы, что движок не напишет с нуля (`edit.listcols.classify`) — в `skipped` с его причиной."""
    names, seen = [], set()
    for column in table.columns:
        cell = {"type": "TableBoxColumn", **({"name": column.name} if column.name else {}), "in": item.name or shell.LIST_KEY}
        if column.key is None:
            why = "колонка без данных (путь не на стандартный реквизит и не на реквизит объекта) или не колонка списка"
        elif column.key in seen:
            why = f"колонка «{column.key}» уже показана: одна колонка на реквизит"
        else:
            try:
                listcols.classify(obj, column.key, ctx.config)
                why = None
            except EditError as e:
                why = ctx.clean(str(e))
        if why is not None:
            ctx.skipped.append({**cell, "why": why})
            ctx.counts["skipped:TableBoxColumn"] += 1
            continue
        seen.add(column.key)
        names.append(column.key)
    if not names:
        ctx.skip(item, "у таблицы списка нет колонок, которые описание выразит", None)
        return None
    ctx.mark(item)
    out = {"table": shell.LIST_KEY}
    if names != generate_list.default_columns(obj):
        out["columns"] = names
    ctx.counts["columns"] += len(names)
    return out


def _list_blocks(ctx, items):
    """Блоки формы списка: верхняя панель и таблица на динамический список; всё прочее верхнего уровня — в `skipped` с причиной. `(блоки, верхняя панель, нижняя панель)`."""
    obj = ctx.list_obj
    try:
        found = shell.scan(ctx.doc, obj)
    except EditError as e:
        raise DescribeError(f"форма списка разобрана не так, как у платформы: {e}") from None
    main = found.lists[0] if found.lists else None
    trees = {t.index for t in found.trees}
    deferred = []                       # дерево групп и разделитель: что с ними будет, зависит от того, описана ли таблица списка
    table_block, bar_top, bar_bottom = None, None, None
    for item in sorted(items, key=lambda i: (i.box[1], i.box[0]) if i.box else (0, 0)):
        if item.page not in (0, None):
            ctx.skip(item, f"страница формы {item.page}: словарь блоков страниц формы не знает")
        elif not item.visible:
            ctx.skip(item, "элемент невидим")
        elif item.type == "TableBox" and main is not None and item.index == main.index:
            table_block = _list_table_block(ctx, item, main, obj)
            continue
        elif item.type == "TableBox" and item.index in trees:
            deferred.append(item)
            continue
        elif item.type == "Splitter" and trees:
            deferred.append(item)
            continue
        elif item.type == "TableBox":
            ctx.skip(item, "вторая таблица на динамический список формы: блок table — одна таблица на список" if main is not None and item.index in {x.index for x in found.lists[1:]} else
                     "табличное поле не на динамический список формы: блок table формы списка — только на список")
            continue
        elif item.type == "CommandBar":
            if item.box[1] < 12 and bar_top is None:
                bar_top = item
                ctx.mark(item)
            elif item.box[3] >= ctx.form.height - 2 and bar_bottom is None:
                ctx.skip(item, "нижняя панель команд: у формы списка её нет (конструктор не ставит, корпус — 13 форм из 440 (patterns.json))")
            else:
                ctx.skip(item, "командная панель не верхняя панель формы: в словаре списка только верхняя")
            continue
        else:
            ctx.skip(item, LIST_WHY.get(item.type, f"вид элемента «{item.type}» вне словаря блоков списка (command_bar, table)"))
        if item.type == "Panel":
            _skip_inside(ctx, item)
    for item in deferred:
        if table_block is None:
            ctx.skip(item, "дерево групп (или его разделитель) без таблицы списка: блока table нет, дереву не при чём")
        else:
            ctx.mark(item)
    if table_block is not None and any(i.type == "TableBox" for i in deferred):
        table_block = {"table": table_block["table"], "tree": True, **{k: v for k, v in table_block.items() if k != "table"}}
    if main is None:
        ctx.notes.append("на форме нет табличного поля на динамический список (основной реквизит формы): блока table нет, описание генерации не годится")
    blocks = [table_block] if table_block is not None else []
    return blocks, bar_top, bar_bottom


# ── Вход ──────────────────────────────────────────────────────────────────────────────────────

def _content_size(desc, doc, config, notes=None):
    """Размер формы, который движок даст этому описанию «по содержимому» (`generate.plan_notes` без `size`): `(ширина, высота)`; описание не годится
    движку — `None`. Любое иное исключение движка (его дефект) `describe` не роняет — извлечение не должно зависеть от построения плана, — но и молча не
    глотает: слова — в `notes`, размер — `None` (`size:unknown`)."""
    try:
        ops, _notes = generate.plan_notes(copy.deepcopy(desc), copy.deepcopy(doc), config, patterns.load())
    except (generate.GenerateError, EditError):
        return None
    except Exception as e:      # noqa: BLE001 — дефект движка называется, а не роняет извлечение
        if notes is not None:
            notes.append(f"размер формы не сверен: движок не смог построить план описания ({type(e).__name__}: {e}); `size` не записан")
        return None
    got = {op["name"]: op["value"] for op in ops if op.get("op") == "set_property" and op.get("form") and op.get("name") in ("width", "height")}
    return (got["width"], got["height"]) if len(got) == 2 else None


def _form_size(ctx, doc, config, desc):
    """Размер формы образца: `[ширина, высота]`, когда размер платформы не равен тому, что движок даст «по содержимому», иначе `None` (ключ `size` не
    пишется). Движок не принимает размер меньше содержимого: у стороны, где платформа уже, берётся содержимое (`size:narrower`). Форма списка и описание
    без вида размер не несут: у списка его решает исходная форма; описание, которое движку не годится (нет выгрузки), сравнить не с чем — `size:unknown`."""
    if ctx.list_obj is not None or not any(k in b for b in desc["blocks"] for k in ("fields", "table", "tabs", "group", "spreadsheet")):
        return None
    content = _content_size(desc, doc, config, ctx.notes) if ctx.kind else None
    if content is None:
        ctx.counts["size:unknown"] += 1
        return None
    size = [max(ctx.form.width, content[0]), max(ctx.form.height, content[1])]
    if ctx.form.width < content[0] or ctx.form.height < content[1]:
        ctx.counts["size:narrower"] += 1
    if size == list(content):
        ctx.counts["size:same_as_content"] += 1
        return None
    ctx.counts["size:carried"] += 1
    return size


def describe(doc, config=None, form_use=None, kind=None, object_name=None):
    """Форма (документ уровня 1) → `Result`. `config` — `metadata.Config` либо `None`; `form_use` — `item`/`folder` у
    справочника с группами (без него выбирается по именам полей); `kind` и `object_name` — вид и объект, когда по метаданным
    их не найти (обработка: `processing`, `Обработка.Имя`). Отказ — `DescribeError` словами."""
    if not isinstance(doc, dict):
        raise DescribeError("форма — документ уровня 1 (JSON-объект), а пришло другое")
    if config is not None and not isinstance(config, metadata.Config):
        raise DescribeError("config — выгрузка конфигурации (metadata.load)")
    if form_use not in (None, *generate.ROLE_FORMS):
        raise DescribeError(f"form_use — {' или '.join(generate.ROLE_FORMS)}, а пришло {form_use!r}")
    try:
        ctx = _Ctx(doc, config, form_use, kind, object_name)
    except EditError as e:
        raise DescribeError(f"форма разобрана не так, как у платформы: {e}") from None
    if ctx.list_obj is not None:
        if form_use is not None:
            raise DescribeError("form_use — у формы списка форм элемента и группы нет")
        ctx.kind = f"{ctx.list_obj.kind}.list"
        ctx.object_name = ctx.list_obj.full_name
    elif ctx.obj is not None:
        ctx.role = _role(ctx, form_use)
        ctx.kind = generate.PROCESSING if ctx.obj.kind in ("processing", "report") else f"{ctx.obj.kind}.item"       # форма отчёта — как форма обработки: данные в реквизитах формы
        ctx.object_name = ctx.obj.full_name
    ctx.processing = ctx.kind == generate.PROCESSING
    if ctx.processing:
        try:
            ctx.resolver = generate._Resolver(ctx.obj, ctx.role, config, generate.FormAttributes(doc, config))
        except generate.GenerateError as e:
            raise DescribeError(f"форма разобрана не так, как у платформы: {e}") from None
    elif ctx.obj is not None:
        ctx.resolver = generate._Resolver(ctx.obj, ctx.role, config)
    top_items = [c for c in ctx.form.holders[0].children]
    if ctx.list_obj is not None:
        blocks, bar_top, bar_bottom = _list_blocks(ctx, top_items)
    else:
        entities, bar_top, bar_bottom = _scope(ctx, top_items, None, True, True)
        blocks = []
        for order, block in entities:
            if order == TABS_ORDER:
                made = _tabs_block(ctx, block)
                if made is not None:
                    blocks.append(made)
            else:
                blocks.append(block)
    for item in ctx.form.raw:                    # без разобранных координат: в раскладку не попали, но не пропали молча
        ctx.skip(item, "элемент без разобранного блока координат: его место неизвестно")
        _skip_raw_children(ctx, item)
    everything = [id(n) for n in _nested(ed_base.container(doc))]      # обход ДОКУМЕНТА (узлы с вложенными), не модели раскладки
    ctx.counts["elements:total"] = len(everything)
    ctx.counts["elements:described"] = len(ctx.described)
    ctx.counts["elements:skipped"] = len(ctx.skipped_ids)
    ctx.counts["elements:lost"] = len(set(everything) - ctx.described - ctx.skipped_ids)
    out = {}
    if ctx.kind:
        out["kind"] = ctx.kind
    if ctx.object_name:
        out["object"] = ctx.object_name
    title = _form_title(doc)
    if title:
        out["title"] = title
    if ctx.obj is not None and ctx.role is not None:
        out["form_use"] = ctx.role
    final = []
    if bar_top is not None:
        final.append({"command_bar": "top"})
    final += blocks
    if bar_bottom is not None:
        final.append({"command_bar": "bottom"})
    out["blocks"] = final
    size = _form_size(ctx, doc, config, out)
    if size is not None:
        out["size"] = size
    if ctx.skipped:
        out["skipped"] = ctx.skipped
    if not ctx.kind:
        ctx.notes.append("вид и объект формы не определены (основной реквизит не объект выгрузки; для обработки — kind и "
                         "object_name): описание без kind и object генерации не годится")
    for block in final:
        ctx.counts["blocks:" + next(k for k in generate.BLOCKS if k in block)] += 1
    return Result(out, ctx.notes, ctx.counts)


def hints_from_path(path):
    """Вид и объект по месту файла в выгрузке: `…/DataProcessors/<Имя>/Forms/<Форма>/Ext/form.frm` — обработка. Остальное —
    `(None, None)`: форма объекта называется метаданными, а для прочих мест (отчёты, регистры, общие формы) вид словарю
    неизвестен — подсказывать нечего."""
    parts = list(getattr(path, "parts", None) or str(path).replace("\\", "/").split("/"))
    if "Forms" in parts:
        at = len(parts) - 1 - parts[::-1].index("Forms")
        if at >= 2 and parts[at - 2] == "DataProcessors":
            return "processing", f"Обработка.{parts[at - 1]}"
    return None, None


def _role(ctx, form_use):
    """Чья форма — элемента или группы — у справочника с группами: названная, иначе та, под которой названные полями
    реквизиты и табличные части разрешаются все (роль без различий — `None`). Не нашлась ни одна — `None`: отказ у каждого
    поля скажет движок словами."""
    obj = ctx.obj
    if form_use is not None or not obj.has_folders():
        return form_use
    names = []
    for item in ctx.form.holders[0].children:
        kind, name = ctx.binding(item)
        if kind in ("object", "table") and name:
            names.append(name)
    for role in (None, "item", "folder"):
        try:
            for name in names:
                datapath.resolve(obj, name, role)
        except EditError:
            continue
        if role is not None:
            ctx.notes.append(f"форма названа «{role}» по именам полей: под этой ролью разрешаются все привязанные реквизиты")
        return role
    ctx.notes.append("у справочника с группами названные реквизиты не разрешаются ни под одной ролью формы — form_use не выбран")
    return None
