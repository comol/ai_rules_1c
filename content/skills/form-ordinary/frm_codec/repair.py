"""Диагноз поломок привязок формы и режим их исправления (`repair_anchors`).

**Диагноз** (`diagnose`) называет поломки поведения формы при растяжении окна; у каждой есть виновники (элементы) и слова:

* `frozen` — форма не растягивается: предел роста по оси меньше `FREEZE_PX` (`layout.EARLY`) px, хотя на форме есть растягиваемые элементы;
  причина — действующий предел раскладки (`limits`);
* `collision` — при росте окна два элемента сталкиваются не дальше `NEAR_PX` px от проектного размера; столкновение при сжатии на те же
  px — справка (так конструктор ставит нижнюю панель), поломкой оно становится, только если виновника назвал пользователь (`elements`);
* `overlap` — наезд двух элементов не меньше чем на `OVERLAP_PX` px при размере окна из набора `candidates.size_set`, лежащем внутри пределов раскладки;
* `frame` — элемент, лежавший в проекте внутри рамки группы, при размере окна выходит из неё или сдвигается к её заголовку;
* `align` — выравнивание столбца расходится при растяжении (`lint.align_findings` — та же функция, что у замечания `align`); сдвиг меньше
  `ALIGN_FIX_PX` px — справка;
* `dead` — мёртвое правило (граница в предприятии остаётся на месте); `cycle` — привязки образуют цикл;
* `pattern` — формальный рисунок привязок (`anchors_fix`): правило на себя у формы DPI ≠ 96 и висячие записи при нём, пустое правило со смещением.

У формы с запретом изменения размера растяжение не проверяется (справка); `dead`, `cycle` и `pattern` остаются: они не про растяжение.

**Режим исправления** (`repair_anchors`): сначала `normalize_anchors` по элементам с формальными рисунками (правка элемента остаётся, только
если его рисунок исчез); затем по каждому виновнику перебираются кандидаты движка выбора привязок (`candidates.h_candidates`,
`candidates.v_candidates`; копия правил у образца не предлагается, если сам образец назван диагнозом). Кандидат принимается, если улучшает хотя
бы одну поломку виновника, не создаёт и не ухудшает прочих и не сужает предел раскладки формы (`limits.compare`). Из принятых выбирается тот,
что снимает поломки виновника целиком, затем меняет меньше элементов и границ, затем ведёт себя как большинство столбца, затем меньше связывает
с чужими элементами. После каждого принятого кандидата диагноз повторяется; шагов не больше `STEPS`, правок одного элемента не больше `PER_ITEM`.
`box` не меняется; меняются правила виновников (в том числе названных диагнозом после очередной правки) и встречные записи у соседей и родителя.
"""
import collections

from . import anchors, anchors_fix, edit, layout, limits, lint
from .layout import candidates
from .edit.base import EditError

FREEZE_PX = layout.EARLY    # предел роста меньше стольких px при растягиваемых элементах — форма не растягивается (та же граница, что у замечания `layout`)
NEAR_PX = 5         # столкновение при росте не дальше стольких px от проектного размера — поломка; при сжатии — справка
ALIGN_FIX_PX = 8    # расхождение выравнивания меньше стольких px режим не исправляет (справка)
FRAME_TOP_PX = 3    # отступ элемента от верха рамки группы стал меньше проектного больше чем на столько px — поломка
FRAME_EDGE_PX = 2   # элемент выходит за край рамки больше чем на столько px — поломка
STEPS = 12          # принятых правок за один вызов не больше
PER_ITEM = 2        # правок одного элемента не больше
SYNC = object()     # «кандидат» без новых правил: встречные записи по прежним правилам (мёртвое правило из-за пропавшей записи)
STRUCTURAL = ("Splitter", "CommandBar")     # разделитель и командная панель правятся только по мёртвому правилу и циклу: их привязки — часть устройства формы
OVERLAP_PX = 3      # наезд при размере окна меньше стольких px — округление модели, не поломка
SHOWN = 4           # сколько отвергнутых вариантов называет отчёт
KIND_WORDS = {"frozen": "форма не растягивается", "collision": "столкновение при малом изменении размера",
              "overlap": "наезд при размере окна", "align": "выравнивание расходится", "dead": "мёртвое правило",
              "cycle": "цикл привязок", "pattern": "формальный рисунок привязок", "frame": "содержимое уходит из рамки"}


class Finding(collections.namedtuple("Finding", "kind key culprits axes words badness")):
    """Одна поломка: `key` — устойчивое имя (по нему сравнивают диагнозы до и после правки), `culprits` — квалифицированные имена виновников,
    `axes` — оси (0 — ширина, 1 — высота), в которых их привязки могут помочь, `badness` — насколько плохо (больше — хуже)."""
    __slots__ = ()


class Diagnosis:
    """Поломки формы: `findings`, `snap` — пределы (`limits.Snapshot`) либо `None`, `error` — слова, если раскладка форму не читает,
    `info` — справочные строки (то, что поломкой не считается), `soft` — находки-справка: поломкой они становятся, только если виновника назвал
    пользователь (`diagnose(soft_for=…)`)."""

    def __init__(self):
        self.findings, self.snap, self.error, self.info, self.soft = [], None, None, [], []
        self.by_key = {}

    def add_soft(self, finding, soft_for):
        """Находка, которую режим исправления не трогает без явного указания: справка либо поломка, если виновник назван в `soft_for`."""
        if soft_for and any(name in soft_for for name in finding.culprits):
            self.add(finding)
        else:
            self.soft.append(finding)

    def add(self, finding):
        if finding.key not in self.by_key:
            self.findings.append(finding)
            self.by_key[finding.key] = finding

    @property
    def signature(self):
        return tuple(sorted((repr(f.key), f.badness) for f in self.findings))

    def culprit_axes(self):
        """`{имя виновника: оси}`: по каким осям образец называет диагноз."""
        out = {}
        for f in self.findings:
            for name in f.culprits:
                out.setdefault(name, set()).update(f.axes)
        return out

    def culprits(self):
        """`{имя виновника: [Finding]}` в порядке находок."""
        out = {}
        for f in self.findings:
            for name in f.culprits:
                out.setdefault(name, []).append(f)
        return out


def _stretchy(form, coef, axis):
    """Есть ли на форме элемент, растягивающийся по оси (рост размера не меньше `GROW_MIN` роста окна)."""
    for item in form.holders[0].children:
        c = coef.get(item.index)
        if c is None or not item.visible or item.type in STRUCTURAL:
            continue
        growth = (c[3] - c[2]) if axis == 0 else (c[1] - c[0])
        if growth >= layout.GROW_MIN:
            return True
    return False


def _limit_culprits(lim, coef, axis):
    """Виновники предела-столкновения: тот из пары, кто остаётся на месте по оси (если оба сдвигаются — оба); у предела другого рода — никто."""
    if lim.kind != "столкновение":
        return []
    pair = [lim.a, lim.b]
    fixed = [o for o in pair if not layout._moves(o, coef, axis)]
    return [o.qualified() for o in (fixed or pair)]


def _limit_findings(out, form, snap, coef, soft_for):
    for axis in (0, 1):
        for direction in (1, -1):
            found = snap.limits.get((axis, direction))
            room = snap.room[(axis, direction)]
            if not found or room is None or found[0].kind != "столкновение":
                continue
            margin = room if direction > 0 else -room
            lim = found[0]
            culprits = _limit_culprits(lim, coef, axis)
            if not culprits:
                continue
            if direction > 0 and margin < FREEZE_PX and _stretchy(form, coef, axis):
                out.add(Finding("frozen", ("frozen", axis, direction), tuple(culprits), (axis,),
                                f"раскладка перестаёт растягиваться почти сразу ({layout.AXES[axis]} {layout._size_words(*snap.ranges[axis])}, "
                                f"предел роста {room:+d} px), хотя на форме есть растягиваемые элементы: {lim.words(form, coef)}",
                                FREEZE_PX - margin))
            elif margin <= NEAR_PX:
                key = ("collision", axis, direction)
                if direction > 0:
                    out.add(Finding("collision", key, tuple(culprits), (axis,),
                                    f"{layout.AXES[axis]}, рост: предел {room:+d} px — {lim.words(form, coef)}", NEAR_PX + 1 - margin))
                else:
                    out.add_soft(Finding("collision", key, tuple(culprits), (axis,),
                                         f"при сжатии окна ниже проектного размера на {margin} px: {lim.words(form, coef)}", NEAR_PX + 1 - margin), soft_for)


def _check_sizes(snap, axis):
    """Размеры оси для проверки наездов и рамок: набор 134 и верхний предел раскладки (на нём раскладка останавливается, и поломка видна именно там)."""
    sizes = set(candidates.size_set(snap, axis))
    if snap.ranges[axis][1] is not None:
        sizes.add(snap.ranges[axis][1])
    return sorted(sizes)


def overlap_pairs(items, project, ints):
    """Пары `(a, b)` элементов одного родителя и страницы, не пересекавшиеся в проекте (`project`) и пересекающиеся в раскладке `ints`:
    `[(Item, Item, px)]`, `px` — меньшая из сторон пересечения. Контейнеры (панель, рамка группы) в пары не входят."""
    out = []
    for at, a in enumerate(items):
        for b in items[at + 1:]:
            if a.holder != b.holder or a.page != b.page:
                continue
            ra, rb = ints[a.index], ints[b.index]
            if not candidates._overlap(ra, rb):
                continue
            pa, pb = project[a.index], project[b.index]
            if candidates._overlap(pa, pb) or candidates._contains(pa, pb) or candidates._contains(pb, pa):
                continue
            px = min(min(ra[2], rb[2]) - max(ra[0], rb[0]), min(ra[3], rb[3]) - max(ra[1], rb[1]))
            out.append((a, b, round(px, 1)))
    return out


def _overlap_findings(out, form, snap):
    items = [i for i in layout._all_items(form) if i.visible and i.type not in candidates.CONTAINERS and i.box is not None]
    if len(items) > 400:
        return          # попарная проверка форм в сотни элементов дороже, чем полезна; такие формы диагноз по наездам не проверяет
    project = {i.index: tuple(i.box) for i in layout._all_items(form)}
    for axis in (0, 1):
        lo, hi = snap.ranges[axis]
        for value in _check_sizes(snap, axis):
            if value == snap.size[axis] or (lo is not None and value < lo) or (hi is not None and value > hi):
                continue
            size = candidates._window(snap, axis, value)
            lay = candidates._layout_at(form, *size)
            for a, b, px in overlap_pairs(items, project, lay.ints):
                if px < OVERLAP_PX:
                    continue
                names = tuple(sorted((a.qualified(), b.qualified())))
                out.add(Finding("overlap", ("overlap",) + names, names, (0, 1),
                                f"«{a.qualified()}» наезжает на «{b.qualified()}» при размере окна {size[0]}×{size[1]} (на {px:g} px)", px))


def _frame_findings(out, form, snap):
    items = [i for i in layout._all_items(form) if i.visible and i.box is not None]
    frames = [i for i in items if i.type == "GroupBox"]
    if not frames or len(items) > 400:
        return
    project = {i.index: tuple(i.box) for i in items}
    inside = {g.index: [o for o in items if o is not g and o.holder == g.holder and o.page == g.page
                        and candidates._contains(project[g.index], project[o.index])] for g in frames}
    if not any(inside.values()):
        return
    for axis in (0, 1):
        lo, hi = snap.ranges[axis]
        for value in _check_sizes(snap, axis):
            if value == snap.size[axis] or (lo is not None and value < lo) or (hi is not None and value > hi):
                continue
            size = candidates._window(snap, axis, value)
            lay = candidates._layout_at(form, *size)
            for g in frames:
                gi = lay.ints[g.index]
                for o in inside[g.index]:
                    oi = lay.ints[o.index]
                    was, now = o.box[1] - g.box[1], oi[1] - gi[1]
                    out_px = max(gi[0] - oi[0], oi[2] - gi[2], oi[3] - gi[3], gi[1] - oi[1], 0)
                    if was - now > FRAME_TOP_PX or out_px > FRAME_EDGE_PX:
                        key = ("frame", g.qualified(), o.qualified())
                        out.add(Finding("frame", key, (g.qualified(), o.qualified()), (0, 1),
                                        f"«{o.qualified()}» уходит из рамки «{g.qualified()}» при размере окна {size[0]}×{size[1]}: отступ от верха рамки "
                                        f"{was} → {now} px" + (f", выступ за край {out_px:g} px" if out_px > FRAME_EDGE_PX else ""),
                                        max(was - now, out_px)))


def _border_axis(border):
    return 1 if border in (0, 1) else 0


def _pattern_findings(out, form):
    scanned = anchors_fix.scan(form)
    decisive = anchors_fix.decisive(form, scanned)
    standard = []
    for key, found in scanned.items():
        harmful = (key in ("own-rule", "dangling-record") and decisive) or key == "empty-offset"
        for f in found:
            if not harmful:
                if anchors_fix.platform_standard(key, f):  # запись, которую платформа пишет сама: одна строка в конце, а не по строке на запись
                    standard.append((key, f))
                    continue
                out.info.append(f"справка: {anchors_fix.BY_KEY[key].title} — {f.words}")
                continue
            culprits = (f.subject.qualified(),) if f.subject is not None else ()
            out.add(Finding("pattern", ("pattern", key, f.words), culprits, (),
                            f"{anchors_fix.BY_KEY[key].title}: {f.words}", 1))
    if standard:
        out.info.append(anchors_fix.platform_words(standard))


def diagnose(doc, quick=False, soft_for=None):
    """`Diagnosis` формы `doc`. `quick` — без проверки наездов и рамок при размерах окна (она тратит несколько раскладок); `soft_for` — имена
    элементов, названных пользователем: их находки-справка считаются поломками."""
    out = Diagnosis()
    try:
        form = layout.read(doc)
        coef = layout.coefficients(form)
        out.snap = limits.Snapshot(form, coef)
        flat = layout.coefficients(form, hide=False)
    except limits.READ_ERRORS as e:
        out.error = f"раскладка форму не читает: {e}"
        return out
    stretch = doc.get("size_change") != "DontChange"
    if stretch:
        _limit_findings(out, form, out.snap, coef, soft_for)
    else:
        out.info.append("справка: у формы запрещено изменение размера окна — растягивание не проверяется")
    for item in layout._all_items(form):
        if item.raw or not item.visible:
            continue
        if flat.get(item.index) is None:
            out.add(Finding("cycle", ("cycle", item.qualified()), (item.qualified(),), (0, 1),
                            f"привязки «{item.qualified()}» образуют цикл: граница зависит от самой себя", 1))
    seen = set()
    for item, border, _which, _rule, why in layout.dead_rules(form):
        if (item.index, border) in seen:
            continue
        seen.add((item.index, border))
        out.add(Finding("dead", ("dead", item.qualified(), border), (item.qualified(),), (_border_axis(border),),
                        f"мёртвое правило «{item.qualified()}» ({layout.BORDERS[border]} граница): {why}", 1))
    for drift in (lint.align_findings(form) if stretch else ()):
        finding = Finding("align", ("align", drift.odd.qualified(), drift.edge), (drift.odd.qualified(),), (0,), drift.text, drift.shift)
        if drift.shift >= ALIGN_FIX_PX:
            out.add(finding)
        else:
            out.add_soft(finding, soft_for)
    _pattern_findings(out, form)
    if not quick and stretch:
        _overlap_findings(out, form, out.snap)
        _frame_findings(out, form, out.snap)
    return out


def culprit_axes(doc):
    """Виновники диагноза (без проверки наездов): `{имя: оси}` — элементы, которые нельзя брать образцом привязок по этим осям."""
    d = diagnose(doc, quick=True)
    out = {}
    if d.error is None:
        for f in d.findings:
            for name in f.culprits:
                out.setdefault(name, set()).update(f.axes)
    return out


def describe(d):
    """Строки отчёта `anchors-check`: поломки по видам с виновниками и словами; пусто — поломок нет."""
    lines = []
    by_kind = collections.Counter(f.kind for f in d.findings)
    if by_kind:
        lines.append("поломок привязок: " + ", ".join(f"{KIND_WORDS[k]} — {n}" for k, n in sorted(by_kind.items())))
    for f in d.findings:
        names = ", ".join(f"«{n}»" for n in f.culprits) or "виновник не назван"
        lines.append(f"  [{f.kind}] виновники: {names}; {f.words}")
    for f in d.soft:
        lines.append(f"справка [{f.kind}] {', '.join(f'«{n}»' for n in f.culprits)}: {f.words}")
    return lines


# ── Исправление ───────────────────────────────────────────────────────────────────────────────

def _rules(form):
    """`{индекс: (правила четырёх границ, флаги «Ручная привязка»)}` — то, что меняет `set_anchors` у самого элемента."""
    return {i.index: (tuple(tuple(None if r is None else (r.obj, r.side, r.off) for r in pair) for pair in i.rules), i.manual)
            for i in layout._all_items(form) if not i.raw}


def _touched(before, after):
    """`(затронуто элементов, затронуто границ)` между двумя `_rules`."""
    elements = borders = 0
    for index, (rules, manual) in after.items():
        was = before.get(index)
        if was is None:
            continue
        changed = sum(1 for a, b in zip(rules, was[0]) if a != b)
        if changed or manual != was[1]:
            elements += 1
        borders += changed
    return elements, borders


def _boxes(form):
    return {i.index: tuple(i.box) for i in layout._all_items(form) if not i.raw}


def _rule_words(item):
    out = []
    for border, pair in enumerate(item.rules):
        text = ", ".join(r.text(item.index) for r in pair if r is not None) or "нет"
        out.append(f"{layout.BORDERS[border]} {text}")
    return "; ".join(out)


def _axis_words(item, axis):
    borders = (2, 3) if axis == 0 else (0, 1)
    return "; ".join(f"{layout.BORDERS[b]} " + (", ".join(r.text(item.index) for r in item.rules[b] if r is not None) or "нет") for b in borders)


def _growth(c, axis):
    """Рост размера элемента на пиксель роста окна по оси: `c` — коэффициенты границ `(верх, низ, лево, право)`."""
    return (c[3] - c[2]) if axis == 0 else (c[1] - c[0])


def _foreign(form, item):
    """Сколько правил привязывают границу к элементам, не бывшим парой этого элемента (его надпись или поле) и не самим им: чем меньше, тем
    ближе привязка к устройству пары."""
    near = candidates._neighbours(form, item)
    mate = candidates._label_of(near, item) if item.type == "TextBox" else candidates._field_of(near, item)
    allowed = {0, item.index} | ({mate.index} if mate is not None else set())
    return sum(1 for pair in item.rules for r in pair if r is not None and r.obj not in allowed)


class _Try:
    __slots__ = ("words", "spec", "axis", "doc", "diag", "resolved", "touched", "foreign", "mismatch", "order")


def _compare(before, after, name):
    """`(годен, снято ли всё, слова отказа)` для кандидата: годен, если у виновника хоть одна поломка улучшилась и никакой новой или худшей нет.
    Новое расхождение выравнивания у другого элемента не считается новым, пока форма не растягивалась по ширине: оно проявилось, когда
    раскладка пошла дальше предела, и следующий шаг чинит его как обычную поломку."""
    hidden = any(f.kind == "frozen" and f.axes == (0,) for f in before.findings)
    for key, f in after.by_key.items():
        was = before.by_key.get(key)
        if was is None:
            if hidden and f.kind == "align" and name not in f.culprits:
                continue    # расхождение выравнивания других элементов было и раньше: пока форма не растягивается, раскладка его не показывает
            return False, False, f"появилась поломка: {f.words}"
        if f.badness > was.badness:
            return False, False, f"поломка ухудшилась: {f.words}"
    mine = [f for f in before.findings if name in f.culprits]
    improved = [f for f in mine if f.key not in after.by_key or after.by_key[f.key].badness < f.badness]
    if not improved:
        return False, False, "поломки виновника не изменились"
    return True, all(f.key not in after.by_key for f in mine), None


def _try_item(work, cur, item_name, finds, unverified, excluded, trace=None, whole=False, soft_for=None):
    """Лучший кандидат для виновника `item_name` либо `(None, [причины отказа вариантов])`."""
    form = layout.read(work)
    coef = layout.coefficients(form, hide=False)
    items = {i.qualified(): i for i in layout._all_items(form)}
    item = items.get(item_name)
    rejected = []
    if item is None or item.raw:
        return None, ["элемент не разобран раскладкой"]
    if item.type in STRUCTURAL and not all(f.kind in ("dead", "cycle") for f in finds):
        return None, [f"«{item.type}» — часть устройства формы, его привязки вручную: `set_anchors`"]
    if not item.name or sum(1 for i in items.values() if i.name == item.name) != 1:
        return None, ["имя элемента пусто или не уникально: правила по имени не записать (`rename_element`)"]
    axes = sorted({a for f in finds for a in f.axes})
    skipped = []
    base_rules = _rules(form)
    base_boxes = _boxes(form)
    majority = candidates.column_behaviour(form, coef, item)
    c0 = coef.get(item.index)
    tried = []
    plans = []
    if any(f.kind == "dead" for f in finds):
        plans.append((axes[0], [("встречные записи восстановлены по прежним правилам", SYNC)]))
    for axis in axes:
        plans.append((axis, candidates.h_candidates(form, coef, item, excluded, skipped) if axis == 0
                      else candidates.v_candidates(form, coef, item, excluded, skipped)))
    for axis, specs in plans:
        for order, (words, spec) in enumerate(specs):
            trial = candidates.fast_copy(work)
            try:
                if spec is SYNC:
                    anchors.sync(trial, item.index)
                else:
                    candidates._set(trial, item.name, "h" if axis == 0 else "v", spec, unverified)
            except EditError as e:
                rejected.append(f"{words}: {e}")
                continue
            after = diagnose(trial, soft_for=soft_for)
            if after.error is not None:
                rejected.append(f"{words}: {after.error}")
                continue
            narrowed = limits.unforgiven(limits.compare(None, None, was=cur.snap, now=after.snap)) if cur.snap is not None else []
            if narrowed:
                rejected.append(f"{words}: сужает предел раскладки — {limits.narrowed_words(narrowed)}")
                continue
            ok, resolved, why = _compare(cur, after, item_name)
            if not ok:
                rejected.append(f"{words}: {why}")
                continue
            new_form = layout.read(trial)
            if _boxes(new_form) != base_boxes:
                rejected.append(f"{words}: изменился бы box")
                continue
            new_item = {i.qualified(): i for i in layout._all_items(new_form)}[item_name]
            c_new = layout.coefficients(new_form, hide=False).get(new_item.index)
            if c_new is not None and c0 is not None and _growth(c0, axis) >= layout.GROW_MIN > _growth(c_new, axis):
                rejected.append(f"{words}: элемент перестал бы растягиваться по {layout.AXES_AT[axis]}")
                continue
            t = _Try()
            t.words, t.spec, t.axis, t.doc, t.diag, t.resolved = words, spec, axis, trial, after, resolved
            t.touched = _touched(base_rules, _rules(new_form))
            t.foreign = _foreign(new_form, new_item)
            t.mismatch = 0 if axis == 1 or majority is None or c_new is None or layout.horizontal_behaviour(c_new[2], c_new[3]) == majority else 1
            t.order = (axis, order)
            tried.append(t)
            if trace is not None:
                trace.append((words, t.resolved, t.touched, t.foreign, after.signature))
    if whole:
        for t in [t for t in tried if not t.resolved]:
            rejected.append(f"{t.words}: поломку только ослабляет, а цепочка правок до её снятия не дошла — форма меняется лишь ради полного исправления")
        tried = [t for t in tried if t.resolved]
    rejected = list(dict.fromkeys(skipped + rejected))
    if not tried:
        return None, rejected
    def rank(t):
        left = sum(f.badness for f in t.diag.findings)
        if t.resolved:
            return (0, t.touched, t.mismatch, t.foreign, left, t.order)
        return (1, left, t.touched, t.mismatch, t.foreign, t.order)

    best = min(tried, key=rank)
    return best, rejected


def _name_words(names):
    return ", ".join(f"«{n}»" for n in names)


class _Run:
    """Итог одного прохода исправления: `work` — документ, `cur` — его диагноз, `changes` — `[(имя, слова, ключи улучшенных, но не снятых поломок)]`,
    `dead_ends` — `{имя: (подпись диагноза, причины отказа вариантов)}`, `count` — число правок по именам."""

    def __init__(self, work, cur):
        self.work, self.cur = work, cur
        self.changes, self.dead_ends, self.count = [], {}, collections.Counter()
        self.named = set(cur.culprits())        # виновники диагноза исходной формы и каждого состояния после очередной правки
        self.weakened = {}                      # ключ поломки → номер правки, которая её ослабила


def _run(work, cur, allowed, unverified, banned):
    """Проход: пока есть виновник, для которого нашёлся кандидат, правка применяется и диагноз повторяется. `banned` — имена, которым частичное
    улучшение запрещено (принимается только вариант, снимающий поломку целиком)."""
    run = _Run(work, cur)
    while len(run.changes) < STEPS and run.cur.error is None:
        broken = run.cur.culprit_axes()
        run.named |= set(broken)
        moved = False
        for name, finds in run.cur.culprits().items():
            finds = [f for f in finds if f.kind != "pattern"]
            if not finds or (allowed is not None and name not in allowed) or run.count[name] >= PER_ITEM:
                continue
            if run.dead_ends.get(name, (None,))[0] == run.cur.signature:
                continue
            best, rejected = _try_item(run.work, run.cur, name, finds, unverified, broken, whole=name in banned, soft_for=allowed)
            if best is None:
                run.dead_ends[name] = (run.cur.signature, rejected)
                continue
            was_item = {i.qualified(): i for i in layout._all_items(layout.read(run.work))}[name]
            was_words, was_range = _axis_words(was_item, best.axis), limits.range_words(run.cur.snap)
            after_item = {i.qualified(): i for i in layout._all_items(layout.read(best.doc))}[name]
            fixed = [f for f in finds if f.key not in best.diag.by_key]
            partial = [f for f in finds if f.key in best.diag.by_key and best.diag.by_key[f.key].badness < f.badness]
            number = len(run.changes) + 1
            fixed_words = [f"поломку, ослабленную правкой {run.weakened[f.key]}" if f.key in run.weakened else f.words for f in fixed]
            text = (f"«{name}», {layout.AXES[best.axis]}: {was_words} → {_axis_words(after_item, best.axis)}; вариант «{best.words}»; "
                    + (f"снимает: {'; '.join(fixed_words)}" if fixed else "поломка остаётся, но слабее: "
                       + "; ".join(best.diag.by_key[f.key].words for f in partial))
                    + (f"; пределы {was_range} → {limits.range_words(best.diag.snap)}" if best.diag.snap is not None else ""))
            run.changes.append((name, text, [f.key for f in partial] if not best.resolved else []))
            for f in partial:
                run.weakened.setdefault(f.key, number)
            run.count[name] += 1
            run.work, run.cur = best.doc, best.diag
            moved = True
            break
        if not moved:
            break
    return run


def repair_anchors(doc, elements=None, dry_run=False, unverified=False):
    """Исправляет привязки, из-за которых форма не растягивается как положено (`diagnose`). Возвращает отчёт; `dry_run` — только отчёт, форма
    не меняется. `elements` — имена виновников, которых можно править (без него — все виновники диагноза, кроме находок-справки; названному
    элементу правятся и они).

    Правка, которая лишь ослабила поломку, остаётся только как звено цепочки, закончившейся снятием поломки: если поломка в конце проходов
    осталась, виновнику запрещается частичное улучшение, и проход повторяется с начала (форма не меняется ради неполной правки).
    """
    return _repair(doc, elements, dry_run, unverified)[0]


def _normalize(work, start, allowed, unverified, lines):
    """`normalize_anchors` по элементам с формальными рисунками, по одному: правка остаётся, только если рисунок элемента исчез. Возвращает
    `{имя: причина}` для рисунков, которые остались."""
    formal = [f for f in start.findings if f.kind == "pattern"]
    names = sorted({c for f in formal for c in f.culprits if allowed is None or c in allowed})
    why = {}
    kept = 0
    for name in names:
        trial = candidates.fast_copy(work)
        try:
            said = anchors_fix.normalize_anchors(trial, elements=[name], unverified=unverified)
        except EditError as e:
            why[name] = f"normalize_anchors отказал — {e}"
            continue
        was = sum(1 for f in start.findings if f.kind == "pattern" and name in f.culprits)
        now = sum(1 for f in diagnose(trial, quick=True, soft_for=allowed).findings if f.kind == "pattern" and name in f.culprits)
        if now < was:
            work.clear()
            work.update(trial)
            kept += 1
            if now:
                why[name] = "normalize_anchors снял не все рисунки элемента: " + "; ".join(r.strip() for r in said.splitlines()[1:] if f"«{name}»" in r)[:300]
        else:
            rows = "; ".join(r.strip() for r in said.splitlines()[1:] if f"«{name}»" in r)
            why[name] = ("формальная правка не снимает рисунок" + (f": {rows[:300]}" if rows else "") + "; правка отменена, форма не меняется ради неё")
    if names:
        lines.append(f"  формальные рисунки: normalize_anchors оставлен у {kept} из {len(names)} элементов")
    return why


def _repair(doc, elements, dry_run, unverified):
    """Работа `repair_anchors`: `(отчёт, _Run)`; `_Run` — для тестов (`named` — все названные диагнозом по ходу работы)."""
    form0 = layout.read(doc)
    allowed = None if elements is None else {i.qualified() for i in anchors_fix._pick(form0, elements)}
    work = candidates.fast_copy(doc)
    start = diagnose(work, soft_for=allowed)
    if start.error is not None:
        raise EditError(f"исправить нельзя: {start.error}")
    head = "repair_anchors" + (" (пробный прогон: форма не изменяется)" if dry_run else "")
    if not start.findings:
        notes = [f.words for f in start.soft] + start.info
        return (f"{head}: поломок привязок нет, форма не изменена" + ("" if not notes else "; " + "; ".join(notes[:3])), None)
    lines = [f"{head}: найдено поломок {len(start.findings)}; пределы до правки: {limits.range_words(start.snap)}"]
    original_boxes = _boxes(layout.read(work))
    formal_why = _normalize(work, start, allowed, unverified, lines)

    after_formal = diagnose(work, soft_for=allowed)
    banned = set()
    while True:
        run = _run(candidates.fast_copy(work), after_formal, allowed, unverified, banned)
        stale = next(((name, keys) for name, _text, keys in run.changes if any(k in run.cur.by_key for k in keys)), None)
        if stale is None or stale[0] in banned:
            break
        banned.add(stale[0])
    lines += [f"  {n}. {text}" for n, (_name, text, _keys) in enumerate(run.changes, 1)]
    if _boxes(layout.read(run.work)) != original_boxes:
        raise EditError("внутренняя ошибка: положение или размер элемента изменились при исправлении привязок, форма не изменена")
    cur = run.cur
    lines.append(f"  итог: исправлено правок {len(run.changes)}, поломок осталось {len(cur.findings)}; пределы после правки: "
                 + (limits.range_words(cur.snap) if cur.snap is not None else "не читаются"))
    for f in cur.findings:
        who = _name_words(f.culprits) or "виновник не назван"
        why = []
        for name in f.culprits:
            stuck = run.dead_ends.get(name)
            if stuck is not None and stuck[0] == cur.signature:
                why += list(dict.fromkeys(stuck[1]))[:SHOWN]
            elif allowed is not None and name not in allowed:
                why.append(f"«{name}» не назван в elements")
            elif run.count[name] >= PER_ITEM:
                why.append(f"у «{name}» уже {PER_ITEM} правки: предел повторов")
        if f.kind == "pattern" and not why:
            why += [formal_why.get(name, "normalize_anchors не вызывался для этого элемента (его нет в elements)") for name in f.culprits]
        if not why and len(run.changes) >= STEPS:
            why.append(f"достигнут предел {STEPS} правок за вызов")
        lines.append(f"  осталось [{f.kind}] {who}: {f.words}" + (f"; почему не исправлено: {'; '.join(why)}" if why else "")
                     + "; выход: привязки названного элемента вручную (`set_anchors`), проверка — `layout` и `render --sizes --before`")
    if not dry_run:
        doc.clear()
        doc.update(run.work)
    return "\n".join(lines), run
