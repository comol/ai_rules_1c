"""Привязки, ломающие растяжение в предприятии, и операция `normalize_anchors`.

Форма может не растягиваться, если окно открыто не проектным размером; модель `layout` рост предсказывает и этого не видит.
Решающий рисунок — правило на саму себя с записями на себя (нижняя панель): на форме с DPI 120 он ломает растяжение по высоте, на
DPI 96 не мешает (проверено в предприятии). Лечит переписывание привязок по роли. Прочие рисунки по одиночке не мешают: `lint`
выводит их справкой, а не замечанием.

Состав: `PATTERNS` — перечень рисунков (новый рисунок — одна запись); `scan(form)` — где какой рисунок (его читают `lint`, `layout`,
`render --sizes` и сама операция); `normalize_anchors(doc, elements=None)` — привязки элементов переписываются начисто по их текущему
поведению (роль оси выводится из коэффициентов границ, `layout.coefficients`), `box` не меняется. Правила пишет `anchors.plan`,
встречные записи — `anchors.sync`. Элемент, чьё поведение не выводится, не трогается и называется с причиной. Проверка: координаты
всех элементов при трёх размерах окна до и после равны (`layout_snapshot`).

Роль выводится из коэффициентов: `stretch` — (0; 1), `right` — (1; 1), `left` — (0; 0), `center` — (½; ½), `proportional` —
(lo/край; hi/край). Элемент, чьи коэффициенты не совпали ни с одной ролью (шапка колонок, цепочка с долей), роли не получает: запись
похожей ролью изменила бы раскладку. Оси обрабатываются по отдельности.

"""
import collections
import copy

from . import anchors, edit, layout

# Три размера проверки: проектный, шире и выше (приращение считается от проектного размера формы).
GUARD_GROWTH = ((0, 0), (253, 121), (0, 260))
# Край записи смещений у вложенных панели без рамки (`Form._panels_by_rules_from_area`): видимая область, а не направляющие страницы.
AREA_EDGE_WORDS = ("край записи смещений вложенных панели без рамки — видимая область панели, а не направляющие страницы: "
                   "предприятие считает правила вложенных от неё")
EPS = 1e-6
PROPORTION_EPS = 1e-4

# Статусы рисунка — что известно о его влиянии; слова идут в отчёты `lint`, `layout` и `render --sizes`.
DECISIVE = ("проверено в предприятии на форме DPI 120: ломает растяжение по высоте при открытии не проектным размером; "
            "на DPI 96 — не мешает")
ALONE = "по одиночке растяжению не мешает (проверено)"
NOT_CHECKED = "влияние на предприятие не проверялось"


class Pattern(collections.namedtuple("Pattern", "key title status source find")):
    """Один рисунок привязок: `find(form)` → `[Finding]`."""
    __slots__ = ()


class Finding(collections.namedtuple("Finding", "subject where words")):
    """`subject` — элемент, чьи правила дали рисунок (или `None`), `where` — место словами, `words` — что именно."""
    __slots__ = ()


def _items(form):
    for key in form.holders:
        yield from form.holders[key].children


def _holder_words(holder):
    return "формы" if holder.item is None else f"панели «{holder.name}»"


# ── Рисунки ──

def _own_rules(form):
    """Правило ближней границы на саму себя (низ панели → «верх = свой низ − 24»): так нижнюю панель пишет платформа. Правило дальней границы от своей ближней стороны (`self`, `after`) рисунком не считается."""
    found = []
    for item in _items(form):
        for border, pair in enumerate(item.rules):
            near = border in (0, 2)
            for rule in pair:
                if rule is None or rule.obj != item.index:
                    continue
                legal = (not near) and rule.side == (0 if border == 1 else 2)
                if not legal:
                    found.append(Finding(item, item.qualified(),
                                         f"«{item.qualified()}» {layout.BORDERS[border]} граница — {rule.text(item.index)} "
                                         "(правило на себя)"))
    return found


def _expected_records(form):
    """Записи, которых требуют правила: `{(куда, (элемент, граница))}`; `куда` — `("holder", ключ, список)` либо `("item", индекс, список)`."""
    out = set()
    for item in _items(form):
        for border, pair in enumerate(item.rules):
            for rule in pair:
                if rule is None:
                    continue
                listed = anchors.RECORD_LIST.get(rule.side)
                if listed is None:
                    continue
                where = ("holder", item.holder, listed) if rule.obj == 0 else ("item", rule.obj, listed)
                out.add((where, (item.index, border)))
    return out


def _dangling(form):
    """Записи без правила — висячие: `[(куда, (элемент, граница))]`. Элементы с неразобранным блоком координат и списки не массивом пропускаются."""
    expected = _expected_records(form)
    raw = {item.index for item in form.raw if isinstance(item.index, int)}
    out = []
    for key, holder in form.holders.items():
        if holder.rows is not None:
            for listed, rows in holder.rows.items():
                for record in sorted(rows or ()):
                    if record[0] not in raw and (("holder", key, listed), record) not in expected:
                        out.append((("holder", key, listed), record))
    for item in _items(form):
        for listed, members in enumerate(item.deps):
            for record in sorted(members or ()):
                if record[0] not in raw and (("item", item.index, listed), record) not in expected:
                    out.append((("item", item.index, listed), record))
    return out


def _dangling_records(form):
    found = []
    for (kind, owner, listed), (index, border) in _dangling(form):
        named = form.items.get(index)
        who = f"«{named.qualified()}»" if named is not None else f"элемент {index} (в форме его нет)"
        if kind == "holder":
            holder = form.holders[owner]
            place, name = f"список {edit.LAYOUT_LISTS[listed]} {_holder_words(holder)}", _holder_words(holder)
        else:
            holder_item = form.items[owner]
            place, name = f"«{holder_item.qualified()}» {edit.DEPENDENTS[listed]}", holder_item.qualified()
        found.append(Finding(named, name,
                             f"{place}: запись ({who}, {layout.BORDERS[border]}) без правила, на которое она указывает"))
    return found


def _box_off(form):
    found = []
    for item, stored, now in layout.box_mismatches(form):
        found.append(Finding(item, item.qualified(),
                             f"«{item.qualified()}»: box {tuple(stored)} не согласован с правилами {tuple(now)}"))
    return found


def _empty_offset(form):
    """Пустое правило (объект −1) со смещением — платформа пишет {−1, 6, 0}."""
    found = []
    for item in list(_items(form)) + list(form.raw):
        coords = item.coords if isinstance(item.coords, dict) else {}
        for border, key in enumerate(edit.ANCHORS):
            anchor = coords.get(key)
            if not isinstance(anchor, dict):
                continue
            for name in edit.RULES:
                rule = anchor.get(name)
                if not isinstance(rule, dict) or rule.get(edit.RULE_OBJECT) != -1:
                    continue
                shift = rule.get(edit.RULE_OFFSET)
                if isinstance(shift, int) and not isinstance(shift, bool) and shift != 0:
                    label = item.qualified() if item.name or item.index is not None else "?"
                    found.append(Finding(item if not item.raw else None, label,
                                         f"«{label}» {layout.BORDERS[border]} граница: пустое правило со смещением {shift}"))
    return found


# Записи, которые платформа пишет сама (перепись корпуса, 4 993 формы): правило на себя у командной панели (нижняя панель:
# верх = свой низ − высота) — у 2 655 форм, у разделителя (ближняя граница от своей дальней: `S.r−толщина`) — у 231 формы; запись без правила,
# указывающая на границу командной панели (список зависимых у соседа нижней панели и у неё самой), — у 2 844 форм. Заготовка `new processing`
# и разделитель, поставленный `between`, несут ровно их: справкой «поломка?» они не являются.
PLATFORM_RECORDS = {"форм": 4993, "own-rule": {"CommandBar": 2655, "Splitter": 231}, "dangling-record": {"CommandBar": 2844}}


def platform_standard(key, finding):
    """Находка — запись, которую платформа пишет сама (`PLATFORM_RECORDS`): правило на себя у панели или разделителя, запись на границу панели."""
    kind = getattr(finding.subject, "type", None)
    return kind in PLATFORM_RECORDS.get(key, {})


def platform_words(standard):
    """Одна строка справки о записях, которые пишет сама платформа: `standard` — `[(ключ рисунка, Finding)]`."""
    places = list(dict.fromkeys(f.where for _k, f in standard))
    seen = {}
    for key, f in standard:
        seen.setdefault(key, f.subject.type)
    bits = []
    if any(k == "own-rule" and f.subject.type == "CommandBar" for k, f in standard):
        bits.append(f"правило панели на себя (нижняя панель: верх = свой низ − высота) — у {PLATFORM_RECORDS['own-rule']['CommandBar']} форм")
    if any(k == "own-rule" and f.subject.type == "Splitter" for k, f in standard):
        bits.append(f"правило разделителя на себя — у {PLATFORM_RECORDS['own-rule']['Splitter']} форм")
    if any(k == "dangling-record" for k, f in standard):
        bits.append(f"встречная запись на границу панели без правила — у {PLATFORM_RECORDS['dangling-record']['CommandBar']} форм")
    return (f"справка: как у платформы, не поломка ({'; '.join(bits)} из {PLATFORM_RECORDS['форм']} форм корпуса; те же записи несёт заготовка "
            f"new processing): {', '.join('«' + p + '»' for p in places)}")


# Перечень рисунков. Статус — что известно о рисунке, источник — откуда он взят.
PATTERNS = (
    Pattern("own-rule", "правило на саму себя",
            DECISIVE,
            "нижняя панель: верх → свой низ −24, записи панели на саму себя",
            _own_rules),
    Pattern("dangling-record", "встречная запись без правила",
            f"ломает растяжение вместе с правилом на себя (у формы с DPI не 96); отдельно {ALONE}",
            "запись у таблицы на панель, правила нет; платформа висячих записей не чистит",
            _dangling_records),
    Pattern("box-off", "box не согласован с правилами",
            ALONE,
            "`layout.box_mismatches`",
            _box_off),
    Pattern("empty-offset", "пустое правило со смещением",
            f"{NOT_CHECKED}; платформа так не пишет",
            "пересчёт привязок писал шаг в пустое правило; `validate` предупреждает",
            _empty_offset),
)
BY_KEY = {p.key: p for p in PATTERNS}
# Рисунки, по которым `lint` выдаёт замечание: решающий. Прочие — справка (строка сведений).
VERDICT = frozenset({"own-rule"})


def scan(form):
    """Где какие рисунки: `{ключ: [Finding]}` — только найденные, в порядке `PATTERNS`."""
    out = {}
    for pattern in PATTERNS:
        found = pattern.find(form)
        if found:
            out[pattern.key] = found
    return out


def count(doc):
    """`{ключ: число находок}` по документу."""
    return {key: len(found) for key, found in scan(layout.read(doc)).items()}


def _list(found, limit=3):
    shown = "; ".join(f.words for f in found[:limit])
    return shown + (f"; … и ещё {len(found) - limit}" if len(found) > limit else "")


def _names(found):
    seen = list(dict.fromkeys(f.where for f in found))
    return ", ".join(seen)


EXIT = "выход — операция normalize_anchors (привязки начисто по текущему поведению, места не меняются)"


def high_dpi(form):
    """У формы DPI не 96: только на ней правило на саму себя ломает растяжение (проверено в предприятии)."""
    block = form.doc.get("form") if isinstance(form.doc, dict) else None
    return isinstance(block, dict) and "device_width" in block and block.get("dpi") != 96


def decisive(form, scanned):
    """Есть рисунок, дающий замечание, и форма, на которой он ломает растяжение."""
    return high_dpi(form) and any(key in VERDICT for key in scanned)


def remarks(form, scanned=None):
    """Замечания для `lint`: `[(ключ рисунка, места, слова, замечание ли)]`.

    Замечание выдаётся только по рисунку из `VERDICT` на форме с DPI ≠ 96; иначе это справка.
    """
    scanned = scan(form) if scanned is None else scanned
    out = []
    for key, found in scanned.items():
        pattern = BY_KEY[key]
        names = _names(found)
        if key in VERDICT and high_dpi(form):
            text = (f"привязки, ломающие растяжение в предприятии: {pattern.title} — {len(found)}: {_list(found)}; "
                    f"статус: {pattern.status}; {EXIT} или normalize_anchors с elements=[{names}]")
            out.append((key, names, text, True))
        elif key in VERDICT:
            text = (f"справка (не замечание): {pattern.title} — {len(found)}: {_list(found)}; так пишет платформа; "
                    "на DPI 96 растяжению не мешает")
            out.append((key, names, text, False))
        else:
            text = (f"справка (не замечание): {pattern.title} — {len(found)}: {_list(found)}; статус: {pattern.status}; "
                    "исправляет normalize_anchors")
            out.append((key, names, text, False))
    return out


def summary_lines(form, scanned=None):
    """Строки сводки `layout`: пусто, когда нет решающего рисунка на форме DPI ≠ 96."""
    scanned = scan(form) if scanned is None else scanned
    if not decisive(form, scanned):
        return []
    parts = [f"{BY_KEY[key].title} {len(found)}" for key, found in scanned.items()]
    return [f"привязки с рисунками, ломающими растяжение в предприятии (у формы с DPI не 96; модель их не видит): {'; '.join(parts)} — "
            f"{EXIT}; подробно — frm_json.py lint"]


def strip_note(form, scanned=None):
    """Пометка у кадров `render --sizes`: пусто, когда нет решающего рисунка на форме DPI ≠ 96."""
    scanned = scan(form) if scanned is None else scanned
    if not decisive(form, scanned):
        return ""
    parts = [f"{BY_KEY[key].title} ({len(found)})" for key, found in scanned.items()]
    return ("модель может не совпасть с предприятием: привязки с рисунками, ломающими растяжение — " + ", ".join(parts)
            + "; normalize_anchors")


# ── Роли по коэффициентам ──

def _close(a, b, eps=EPS):
    return abs(a - b) <= eps


def role_of(axis, near, far, extent):
    """Роль оси по коэффициентам её границ `(near, far)`: имя роли либо `(None, причина)`.

    Роль с несовпавшими коэффициентами не подбирается: она изменила бы раскладку. `extent` — край панели или формы (нужен
    пропорциональной роли).
    """
    left, right = ("left", "right") if axis == "h" else ("top", "bottom")
    if _close(near, 0) and _close(far, 1):
        return "stretch", None
    if _close(near, 0) and _close(far, 0):
        return left, None
    if _close(near, 1) and _close(far, 1):
        return right, None
    if _close(near, 0.5) and _close(far, 0.5):
        return "center", None
    return None, f"коэффициенты границ ({near:.4g}; {far:.4g}) ни одна роль не воспроизводит"


def _proportional(near, far, lo, hi, extent):
    return bool(extent) and _close(near, lo / extent, PROPORTION_EPS) and _close(far, hi / extent, PROPORTION_EPS)


def _blocked(form, item):
    """Причина, по которой элемент не трогается совсем, или `None`: мёртвые и не проверяемые правила."""
    for border, pair in enumerate(item.rules):
        for which, rule in zip(("первое", "второе"), pair):
            if rule is None:
                continue
            state, why = layout.rule_state(form, item, border, rule)
            if state != layout.ALIVE:
                kind = "правило не действует" if state == layout.DEAD else "правило нельзя проверить"
                return f"{kind}: {layout.BORDERS[border]} граница, {which} {rule.text(item.index)} — {why}"
    return None


def _pick(form, names):
    """Элементы по именам: `None` — вся форма. Имя неоднозначно или такого нет — отказ словами."""
    if names is None:
        return list(_items(form))
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise edit.EditError(f"elements — список имён элементов, а пришло {names!r}")
    picked = []
    for name in names:
        found = [item for item in _items(form) if name in (item.name, item.qualified())]
        if not found:
            raise edit.EditError(f"элемента {name!r} в форме нет. Есть: {', '.join(i.qualified() for i in _items(form))}")
        if len(found) > 1:
            raise edit.EditError(f"имя {name!r} носят {len(found)} элемента ({', '.join(i.qualified() for i in found)}) — "
                                 "назовите с панелью (Панель/Имя)")
        if found[0] not in picked:
            picked.append(found[0])
    return picked


def _snapshot(doc, sizes):
    """`{размер: {элемент: (x, y, w, h)}}` — раскладка формы при размерах окна."""
    form = layout.read(doc)
    out = {}
    for width, height in sizes:
        lay = layout.Layout(form, width, height)
        out[(width, height)] = {item.qualified(): tuple(lay.measured(item)) for holder in form.holders.values()
                                for item in holder.children}
    return out


def guard_sizes(doc):
    """Три размера для проверки раскладки: проектный, шире, выше."""
    block = doc["form"]
    return [(block["width"] + dw, block["height"] + dh) for dw, dh in GUARD_GROWTH]


def layout_snapshot(doc, sizes=None):
    """Раскладка при трёх размерах окна — для сравнения до и после (`same_layout`)."""
    return _snapshot(doc, sizes or guard_sizes(doc))


def same_layout(before, after):
    """Расхождения двух снимков: `[(размер, элемент, было, стало)]`; пусто — координаты всех элементов равны."""
    out = []
    for size, boxes in before.items():
        for name, box in boxes.items():
            now = after.get(size, {}).get(name)
            if now != box:
                out.append((size, name, box, now))
    return out


# ── Операция ──

def _words(role):
    return anchors.ROLE_WORDS.get(("h", role)) or anchors.ROLE_WORDS[("v", role)]


def normalize_anchors(doc, elements=None, unverified=False):
    """Привязки элементов — начисто по их текущему поведению; места не меняются.

    `elements` — имена элементов (с панелью, если имя не одно: `Панель/Имя`); без него — вся форма. Поведение по оси берётся из
    текущих правил (`layout.coefficients`): граница, идущая за краем, — `stretch`, обе с дальним краем — `right`/`bottom`, обе
    стоят — `left`/`top`, обе с серединой — `center`. Правила и встречные записи переписываются как у `set_anchors`; правило «к себе»
    и висячие записи уходят.

    Не трогается и называется с причиной: элемент с мёртвым правилом (решает человек), в цикле правил, с осью, чьё поведение не
    воспроизводит ни одна роль (шапка колонок, цепочка с долей — для них `set_anchors` с `self`/`column`), с краем панели или формы,
    который не проверялся (`unverified` снимает отказ там, где его снимает `set_anchors`). Проверка: раскладка при трёх размерах
    окна (проектный, шире на 253×121, выше на 260) до и после — координаты всех элементов равны; иначе отказ, форма не меняется.
    """
    saved = copy.deepcopy(doc)           # отказ сверки раскладки возвращает документ прежним: правка идёт в нём самом
    form = layout.read(doc)
    coef = layout.coefficients(form, hide=False)
    picked = _pick(form, elements)
    whole = elements is None
    before_scan = scan(form)
    before = layout_snapshot(doc)
    changed, skipped, notes, subjects = [], [], [], collections.defaultdict(list)
    for key, found in before_scan.items():
        for f in found:
            if f.subject is not None:
                subjects[f.subject.index].append(BY_KEY[key].title)

    for item in picked:
        label = item.qualified()
        blocked = _blocked(form, item)
        if blocked:
            skipped.append(f"«{label}»: не тронут — {blocked}")
            continue
        c = coef.get(item.index)
        if c is None:
            skipped.append(f"«{label}»: не тронут — привязки образуют цикл, поведение элемента не вычисляется")
            continue
        holder = form.holders[item.holder]
        top, bottom, left, right = c
        x, y, x2, y2 = (item.coords[edit.X], item.coords[edit.Y], item.coords[edit.WIDTH], item.coords[edit.HEIGHT])
        page = item.coords.get(edit.PAGE)
        edges, stored_off = None, False
        area = holder.area.get(item.page) if item.from_area else None
        if area is not None:
            # Предприятие ставит такой элемент по правилам от видимой области панели: смещения пишутся от неё и от положения по правилам в
            # проектном размере панели (`Item.box` у такого элемента — оно, целыми), файловый box не меняется (он мог быть записан от
            # направляющей страницы или не по своим правилам).
            guide = holder.inner.get(item.page)
            words = AREA_EDGE_WORDS
            if guide is not None and layout._same_edge(guide, area):
                try:        # направляющая на области: слова прежние (край панели по направляющим), края — область
                    words = anchors.file_edges(doc, holder.node, page, unverified)[2]
                except edit.EditError:
                    pass
            edges = (area[0], area[1], words)
            stored_off = any(abs(a - b) > layout.BOX_TOLERANCE for a, b in zip(item.stored or item.box, item.box))
            x, y, x2, y2 = (layout._round_border(item.box[at], item, border) for at, border in ((0, 2), (1, 0), (2, 3), (3, 1)))
        values, why = {}, []
        for axis, (near, far), (lo, hi) in (("h", (left, right), (x, x2)), ("v", (top, bottom), (y, y2))):
            role, reason = role_of(axis, near, far, None)
            if role is None:
                try:
                    right_edge, bottom_edge, _w = edges or anchors.file_edges(doc, holder.node, page, unverified)
                except edit.EditError as e:
                    why.append(f"{anchors.AXES[axis][0]}: {reason}; край панели или формы не проверялся — {e}")
                    continue
                extent = right_edge if axis == "h" else bottom_edge
                if _proportional(near, far, lo, hi, extent):
                    role = "proportional"
                else:
                    why.append(f"{anchors.AXES[axis][0]}: {reason}")
                    continue
            values[axis] = role
        if not values:
            skipped.append(f"«{label}»: не тронут — " + "; ".join(why))
            continue
        try:
            plans = [anchors.plan(doc, holder.node, page, item.index, (x, y, x2, y2), axis, role, unverified, edges)
                     for axis, role in values.items()]
            anchors._need_lists(holder.node, [p.rules for p in plans], label)
            loop = anchors._cycle(doc, holder.node, item.index, plans)
            if loop:
                raise edit.EditError(f"цепочка замкнулась бы: {loop}")
        except edit.EditError as e:
            skipped.append(f"«{label}»: не тронут — {e}")
            continue
        anchors.write(item.coords, plans)
        dropped, put = anchors.sync(doc, item.index)
        for p in plans:
            notes += [n for n in p.notes if n not in notes]
        was = subjects.get(item.index)
        said = ", ".join(f"{anchors.AXES[axis][0]} {role}" for axis, role in values.items())
        text = f"«{label}»: {said}" + (f" (было: {', '.join(dict.fromkeys(was))})" if was else "")
        if stored_off:
            text += (f"; правила записаны от видимой области панели и положения в предприятии ({layout._box_words((x, y, x2, y2))}), box в файле "
                     f"прежний ({layout._box_words(item.stored or item.box)}): он записан от направляющей страницы или не по своим правилам")
        if why:
            text += "; ось не тронута — " + "; ".join(why)
        changed.append(text + f"; встречных записей: поставлено {len(put)}, прежних снято {dropped}")

    removed = _sweep(doc, form, whole)
    after = layout_snapshot(doc)
    differ = same_layout(before, after)
    if differ:
        size, name, was, now = differ[0]
        doc.clear()
        doc.update(saved)
        named = next((i for h in form.holders.values() for i in h.children if i.qualified() == name), None)
        if named is not None and named.from_area:
            cause = ("Элемент лежит в панели без рамки: предприятие ставит вложенные по правилам от её видимой области, а положение "
                     "с дробной стороной (доля окна, центр, сосед с долей) после перезаписи округляется иначе — на один пиксель")
        else:
            cause = ("Одна из причин: граница элемента идёт за соседом, чья сторона — доля окна (например, ровно половина). "
                     "Исходная цепочка правил округляет сторону соседа, а правило по роли — свою долю, и при нечётном размере окна они расходятся "
                     "на один пиксель")
        raise edit.EditError(
            f"Проверка раскладки не пройдена: при размере окна {size[0]}×{size[1]} элемент «{name}» сместился (был {was}, стал {now}). "
            f"Всего смещений: {len(differ)}. Форма не изменена. Чтобы найти причину, запустите операцию с параметром elements "
            "для отдельных элементов. " + cause + "; остальные элементы переписывайте через elements, а этому поставьте привязки через set_anchors")
    after_scan = scan(layout.read(doc))
    lines = [f"normalize_anchors: переписано элементов {len(changed)}, не тронуто {len(skipped)}. Размеры окна для проверки раскладки: "
             + ", ".join(f"{w}×{h}" for w, h in guard_sizes(doc)) + ". Проверка раскладки пройдена: координаты всех элементов не изменились"]
    lines += ["  " + t for t in changed]
    lines += ["  " + t for t in skipped]
    if removed:
        lines.append(f"  висячих записей убрано при подметании: {removed}")
    lines.append("  рисунки до → после: " + (", ".join(
        f"{BY_KEY[k].title} {len(before_scan.get(k, ()))} → {len(after_scan.get(k, ()))}" for k in
        dict.fromkeys(list(before_scan) + list(after_scan))) or "не было"))
    left_over = [t for k, found in after_scan.items() for t in [f"{BY_KEY[k].title}: {_list(found)}"]]
    if left_over:
        lines.append("  остались (элементы не тронуты): " + "; ".join(left_over))
    lines += ["  " + n for n in notes]
    return "\n".join(lines)


def _sweep(doc, form, whole):
    """Висячие записи, называющие несуществующий элемент, снимаются (только при полной форме): платформа их не чистит, а `anchors.sync` чистит записи только тронутых элементов."""
    if not whole:
        return 0
    removed = 0
    fresh = layout.read(doc)
    gone = {index for (_where, (index, _b)) in _dangling(fresh) if index not in fresh.items
            and index not in {r.index for r in fresh.raw}}
    for index in gone:
        removed += anchors.drop_naming(doc, index)
    return removed
