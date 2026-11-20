"""Общая операция свойств `set_property` и размер формы. Все имена отдаёт фасад `frm_codec.edit`."""

import copy
import struct

from .. import props, schema, design as _design, json0, chartrows as _chartrows, schemarows as _schemarows, kindrows as _kindrows
from . import rowsa as _rowsa, ctxmenu as _ctxmenu

from .names import (
    BINDINGS,
    DEFAULT_CONTROL,
    NO_REFERENCE,
    SEPARATE_BY_PAGE,
    COLUMN_HEAD_NODES,
    COLUMN_VALUE_TYPE,
    COLUMN_WIDTH,
    CORPUS_STAMP,
    GUIDES,
    GUIDE_COORD,
    GUIDE_ORDER,
    GUIDE_PAGE,
    NAME,
    NAME_BLOCK,
    PAGES,
    PAGE_ITEMS,
    RULE_OFFSET,
    SHORTCUT,
    SHOW_TABS,
    TEXTBOX_NUMBER,
    TEXTBOX_PATTERN,
    UNSEEN_NOTE,
    _at,
    _maybe,
)
from .base import EditError, container, control_slot, elements_of, layout_block, one_default_control, pages_of
from .platform import (
    ROUND11_ACCEPTED,
    ROUND11_NOTE,
    ROUND11_PROPERTIES,
    ROUND12_NOTE,
    ROUND12_PROPERTIES,
    ROUND152_BLOCKS,
    ROUND152_PROPERTIES,
    ROUND_STRUCTURE_WORDS,
    WIDTH_CHECKED,
)
from .buttons import (BUTTON_EXTRA_OPS, FILE_KINDS_BY_PLACE, _file_picture, _image_kind, _maybe,
                           read_picture_file)
from .elements import LIST_CHOICE_MODE, _short
from .pages import (
    DPI,
    FORM_BLOCK,
    FORM_NO_BORDER,
    FORM_PAGE_OLD,
    FORM_PAGE_VERSION,
    GUIDE_OFFSET,
    TABS_AREA_NOTE_AFTER,
    TABS_AREA_NOTE_UNMEASURED,
    TABS_FRAMED_NOTE,
    TABS_NO_BAR_FRAMED_NOTE,
    resort_page0,
    BACK_ONE_FORM,
    rewrite_page0_for_tabs,
    rewrite_page0_for_dont_use,
    check_page0_rewritable,
    tabs_back_plan,
    tabs_top_plan,
    top_size_plan,
    top_size_plan_nobar,
    border_nobar_plan,
    page0_rule_applies,
    TOP_SIZE_NOBAR_MEASURED,
    TOP_SIZE_NOBAR_STRUCTURE,
    _form_border_type,
    _form_edge_rules,
)
from .formroot import (
    CORPUS_FORM_WINDOW_LOCATION,
    FORM_BORDER,
    FORM_BORDER_COLOR,
    FORM_BORDER_TABS_WORDS,
    FORM_CENTER,
    FORM_HEIGHT,
    FORM_OVERLAP,
    FORM_SCROLL,
    FORM_SETTINGS,
    FORM_SIZE_NO_DPI,
    FORM_SIZE_OLD,
    FORM_SIZE_SHORT,
    FORM_SIZE_VERSIONS,
    FORM_WIDTH,
    ROUND15_FORM,
    ROUND15_NOTE,
    ROUND17_FORM,
    ROUND17_NOTE,
    ROUND15_SIZE_CHECKED,
    _FORM_LL,
    _form_missing,
    _form_property,
    _form_settings_words,
    _form_trail,
    _form_written,
)
from .propbase import (
    COORDS_NAMES,
    NO_VALUE,
    PROPERTY_OPS,
    SHORTCUT_PARTS,
    _block_bounds,
    _block_mirror,
    _column_marks,
    _find_one,
    _inner_mirrors,
    _mirror_group,
    _pair_bounds,
    _partner_bounds,
    _property_bounds,
    _property_matches,
    _property_refusal,
    _property_root,
    _property_value,
    _unnamed_position,
)
from .formpage import (FORM_PAGE_ANCHOR, ROUND162, ROUND162_NOTE, ROUND162_PROPERTIES, form_page_root,
                            u6_cowrite)
from .cowrites import (
    EXTENSION,
    MASK_NODES,
    NUMBER_QUALIFIERS,
    NUMBER_QUALIFIER_ANCHORS,
    TEXT_DOCUMENT_NODE,
    _extension_value,
    _number_qualifier,
    _cowrites,
    _inverted_words,
    _linked_warning,
    _list_choice_check,
    _list_choice_data,
    _list_choice_off,
)


ROUND_TABLES = (("в предприятии", ROUND11_PROPERTIES, ROUND11_NOTE),
                ("в предприятии", ROUND11_ACCEPTED, None),
                ("в предприятии", ROUND12_PROPERTIES, ROUND12_NOTE))


def _rounds(anchor, path, value, what, text, passed=True, structure=None):
    """Пометки проверок у поля, которое они проверили: `(подтверждено ли, хвост отчёта)`.

    У проверенного значения — слова проверки вместо корпусной пометки «не проверялось» (число
    корпуса остаётся рядом: оно говорит, как часто платформа пишет это сама); у другого значения
    того же поля — хвост «поле проверено в предприятии только значением …», а граница корпусная: сказать, что проверено именно
    это, было бы неправдой. Поле, которого проверки не видели, — `(None, "")`. Если поле проверили
    два раза (ширина колонки) — названы оба.

    `passed=False` — значение граница корпуса сама не пропустила (невиданное под `unverified`):
    тогда пометки нет даже у значения из проверенного класса — его хвост «корпус такого не видел ни
    разу» остаётся.

    `structure` — строение, в котором лежит поле (`_round_structure`). У записи с набором строений
    пометка ставится только в них; у другого строения — слова `ROUND_STRUCTURE_WORDS`, а не
    «подтверждено» (у колонки без вложенного элемента правка ширины пропадает). Строение не
    определено (`None`) — пометки нет и слов нет: оценивать нечего.
    """
    confirmed, parts, only, other = None, [], [], None
    for round_, table, note in ROUND_TABLES:
        spec = table.get((anchor, path))
        if spec is None:
            continue
        checked, shown, words = spec[:3]
        structures = spec[3] if len(spec) > 3 else None
        if structures is not None and structure not in structures:
            if structure is not None:
                other = ROUND_STRUCTURE_WORDS[(anchor, path)][structure]
            continue
        if not checked(value):
            only.append(f"поле проверено {round_} только значением {shown} — {words}")
            confirmed = confirmed or False
            continue
        if not passed:
            only.append(f"поле проверено {round_} только значением {shown} — {words}; значение за "
                        "границей корпуса пометки проверки не получает")
            confirmed = confirmed or False
            continue
        confirmed = True
        parts.append(f"{note}: {words}" if note else words)
    # Слова «проверено только другим значением» нужны, пока значение само не проверено: у проверенного значения другая
    # таблица, называющая то же поле другим значением (РежимВыбораИзСписка ☑ и ☐), их только путала бы.
    if not confirmed:
        parts = only
    if other is not None:
        return False, f"; {other}"
    if confirmed is None:
        return None, ""
    if not confirmed:
        return False, "".join(f"; {part}" for part in parts)
    row = props.corpus_table().get(anchor, {}).get(path) or {}
    seen = dict(row.get("values") or [])
    number = props._number(text)
    if text in seen:
        count = "; такое значение встречается в образцах форм"
    elif row.get("open") and "range" in row and number is not None \
            and row["range"][0] <= number <= row["range"][1]:
        count = f"; внутри диапазона значений образцов форм {row['range'][0]}…{row['range'][1]}"
    elif isinstance(value, str) and schema.STR in props.row_kinds(row):
        # Строка — содержимое (маска): сказано только, что строка такого вида в образцах есть.
        count = f"; {'пустая' if value == '' else 'непустая'} строка такого вида встречается в образцах форм"
    else:
        count = ""
    return True, f"; {what}: " + "; ".join(parts) + count


ROUND_TABLES += ((ROUND162, ROUND162_PROPERTIES, ROUND162_NOTE),
                 ("в предприятии", ROUND152_PROPERTIES, None),
                 ("в предприятии", ROUND15_FORM, ROUND15_NOTE),
                 ("в предприятии", ROUND17_FORM, ROUND17_NOTE))
MOVE_EDGE_STRUCTURE = "элементы сдвигаются вместе с краем"
ROUND_STRUCTURE_WORDS.update({
    (props.FORM_ANCHOR, path): {
        MOVE_EDGE_STRUCTURE: "размер проверен палитрой и мышью, а элементы платформа при этом не двигала (проверено так: «элементы на месте»); "
                             "перенос границ элементов вместе с краем (move_with_edge) повторяет перетаскивание края формы и в предприятии не проверялся",
        "уменьшение": "размер формы проверен при увеличении; уменьшение — та же арифметика, но "
                      "не проверялось",
        "страниц больше одной": "размер проверен у одностраничной формы; у формы со "
                                "страницами правило положено на каждую — не проверялось",
        "с рамкой": "размер проверен у формы без Рамки; с Рамкой — не проверялось",
        TOP_SIZE_NOBAR_STRUCTURE: "размер проверен у формы «Не отображать»; у формы «Сверху» без нижней панели запись "
                                  "(под `unverified`): край H′−20, правила −36",
        "DPI не 96": "проверено на DPI 96; при другом DPI число в единицах формы — не "
                     "проверялось",
        FORM_SIZE_NO_DPI: f"у формы короткий блок без DPI: {FORM_SIZE_SHORT}",
        **{f"поколение {version}": (
            f"размер проверен у формы поколения 16; у поколения {version} — та же "
            "арифметика, но не проверялось"
            + (f": {FORM_SIZE_OLD}" if version == 10 else ""))
           for version in FORM_SIZE_VERSIONS},
        "поколение иное": "размер проверен у формы поколения 16; поколение этой формы не "
                          "разобрано или не из известных (10, 13, 15, 16) — не проверялось",
    } for path in (FORM_WIDTH, FORM_HEIGHT)})
ROUND_STRUCTURE_WORDS.update({
    (props.FORM_ANCHOR, path): {
        "страниц больше одной": f"{what}; у формы со страницами — не проверялось",
        "две страницы": f"{what}; у формы с двумя страницами — не проверялось"}
    for path, what in ((_FORM_LL + "/show_tabs", "закладки проверены у одностраничной формы"),)})
ROUND_STRUCTURE_WORDS[(props.FORM_ANCHOR, FORM_BORDER_COLOR)] = {
    "страниц больше одной": "ЦветРамки проверен у одно- и двухстраничной формы; у формы с "
                            "тремя страницами и больше — не проверялось"}


# ── Размер формы: что платформа переписывает у края ──────────────────────────

# При смене размера формы палитрой или мышью (8.3.27) платформа:
#
# * координаты элементов не меняет;
# * направляющие края (номер 3 — правый, 4 — нижний) двигает вместе с краем: координата += Δ,
#   отступ прежний («размер − отступ»);
# * у каждого элемента верхнего уровня переписывает смещения привязок с объектом 0 (форма) и
#   стороной 3 (правая) или 1 (нижняя): смещение −= Δширины (Δвысоты) — у всех правил с такой парой,
#   `rule` и `rule2`, у любой из четырёх привязок. Итог — «край = размер + смещение»;
# * вложенных (объект 0 у них — край родителя) не трогает.
#
# Операция пишет ровно это. Проверено: одностраничная форма поколения 16 без Рамки при DPI 96,
# размер увеличивался. Страниц больше одной — отказ, снимаемый `unverified` (тогда то же правило на
# каждой странице); Рамка — слова (арифметика та же, но не проверялось); DPI не 96 — отказ,
# снимаемый `unverified`; уменьшение, короткий блок формы без DPI и поколения 10, 13, 15 — слова без
# пометки проверки.
ROUND15_SIZE = ("платформа при смене размера формы элементы не двигает, смещения привязок к краю формы "
                "переписывает так, чтобы край остался на месте, а направляющие края двигает вместе с краем, "
                "отступ остаётся прежним (проверено в предприятии)")
FORM_EDGES = {"width": (3, 3, "правому", "правой"), "height": (1, 4, "нижнему", "нижней")}


def _form_pages_count(doc):
    """Страниц самой формы; `None` — блок раскладки контейнера не разобран."""
    block = layout_block(container(doc), need=False) if isinstance(doc, dict) else None
    return None if block is None else len(block[PAGES][PAGE_ITEMS])


def _edge_guide_write(guide, coord, offset, delta):
    """Запись направляющей края при смене размера: координата += Δ, отступ прежний (так платформа двигает её вместе с краем)."""
    return (guide, GUIDE_COORD, coord + delta, None, "направляющая")


def _form_edge_guides(doc, number, pages):
    """Направляющие края формы с номером `number` (3 — правый, 4 — нижний) на её страницах."""
    block = layout_block(container(doc), need=False)
    out = []
    for guide in (block or {}).get(GUIDES) or ():
        where = guide.get(GUIDE_PAGE) if isinstance(guide, dict) else None
        if isinstance(where, int) and not isinstance(where, bool) and 0 <= where < pages \
                and guide.get(GUIDE_ORDER) == number:
            out.append(guide)
    return out


# Форма «Сверху» со страницами и нижней панелью: числа «третьей раскладки» (правая направляющая
# страницы 0 → (W′−2, 0), нижняя → (H′−20−19, 19), правила «к низу формы» −19, страницы ≥ 1 →
# (W′−10, 8) и (H′−28, 8)) задаёт область страниц, а не вид закладок. Правило «край остаётся на
# месте» с этой записью расходится в 31 месте (8 направляющих и 23 смещения): без ключа отказ, под
# `unverified` операция пишет раскладку области страниц (`edit.pages.top_size_plan`), а если форма
# не в проверенном состоянии — правило «край остаётся на месте».
FORM_SIZE_TABS_WORDS = (
    "у формы «Сверху» (проверено у формы с нижней панелью) платформа пишет при смене размера "
    "не правило «край остаётся на месте», а раскладку области страниц (правая направляющая страницы 0 → "
    "(W′−2, 0), нижняя → (H′−20−19, 19), правила «к низу формы» страницы 0 −19, страницы ≥ 1 → (W′−10, 8) и (H′−28, 8), box не "
    "тронуты); правило «край остаётся на месте» с этой записью расходится в 31 месте (8 направляющих и 23 смещения). Под `unverified` операция "
    "пишет раскладку области страниц, когда форма в проверенном состоянии (правая страницы 0 с краем W, нижняя — H−19, страницы ≥ 1 "
    "по «Сверху»), иначе правило «край остаётся на месте» с этим расхождением")


def _tabs_top(doc):
    """Закладки формы — «Сверху»."""
    block = layout_block(container(doc), need=False)
    return isinstance(block, dict) and block.get(SHOW_TABS) == "Top"


def _form_size_writes(doc, axis, old, new, unverified, move_with_edge=False):
    """Размер формы: `(записи, слова, строение)` — смещения привязок и координаты направляющих края, как
    их переписывает платформа, или отказ.

    Строение — для пометки проверки (`ROUND15_FORM`): проверено у одностраничной формы поколения 16
    без Рамки при DPI 96, размер увеличивался (`ROUND15_SIZE_CHECKED`). Прочее — слова
    `ROUND_STRUCTURE_WORDS` без пометки: DPI не 96 (и отказ, снимаемый `unverified`), короткий блок
    формы без DPI, поколение не 16, страниц больше одной (и отказ), Рамка, уменьшение.
    """
    side, number, edge, edge_f = FORM_EDGES[axis]
    delta = new - old
    size_now = old
    pages = _form_pages_count(doc) or 1
    border = _form_border_type(doc)
    block = doc.get(FORM_BLOCK) if isinstance(doc, dict) else None
    dpi = block.get(DPI) if isinstance(block, dict) else None
    if pages > 1 and not unverified:
        raise EditError(
            f"{axis} у формы: страниц самой формы {pages}, а размер проверен у "
            "ОДНОСТРАНИЧНОЙ формы — смещения привязок к краю и координаты направляющих края "
            "платформа переписала на одной странице, и что она делает с направляющими и "
            "элементами других страниц, не проверялось. Позвать всё же можно — "
            "unverified=True: то же правило ляжет на каждую страницу (направляющие края — по "
            "номеру страницы, элементы — по своей странице)"
            + (". " + FORM_SIZE_TABS_WORDS if _tabs_top(doc) else ""))
    writes, notes = [], []
    formula = None
    if pages > 1 and _tabs_top(doc) and unverified:
        plan, why = top_size_plan(doc, axis, old, new)
        if plan is not None:
            formula = plan
            writes = list(plan)
            notes.append(why)
            if (axis, delta) not in (("width", 2), ("height", 20)):
                notes.append(f"приращение {axis} {delta:+d}: формула проверена при приращениях (+2, +20) — ровно то, что закладки "
                             "«Сверху» отнимают у области; другое приращение не проверялось")
        else:
            notes.append(f"раскладка области страниц не применена: {why}")
    nobar_top = pages == 1 and _tabs_top(doc) and not page0_rule_applies(doc)
    if nobar_top:
        # «Сверху» без нижней панели: платформа пишет не правило «край остаётся на месте», а край
        # H′−20. Без ключа отказ: область H′−20 и откат правил не разведены; форма в проверенном
        # состоянии либо правило «край остаётся на месте» с его расхождением (22–23 места).
        plan, why = top_size_plan_nobar(doc, axis, old, new)
        if plan is not None:
            if not unverified:
                raise EditError(
                    f"{axis} у формы: у формы «Сверху» без нижней командной панели платформа пишет при смене размера не правило "
                    f"«край остаётся на месте», а {TOP_SIZE_NOBAR_MEASURED}. Позвать всё же можно — unverified=True: операция запишет то же")
            formula = plan
            writes = list(plan)
            notes.append(why)
            if (axis, delta) not in (("width", 2), ("width", 10), ("height", 20), ("height", 10)):
                notes.append(f"приращение {axis} {delta:+d}: формула проверена при приращениях ширины +2, +10 и высоты +20, +10; другое приращение "
                             "не проверялось; правая ось — одна точка (ΔW = 10), «W′−2» и «прежний край + ΔW − 2» не различены")
        else:
            notes.append(f"раскладка вида без панели не применена: {why}; правило «край остаётся на месте» с этим расхождением (22–23 места)")
    shift, grow = f"{-delta:+d}", f"{delta:+d}"
    if nobar_top and formula is None and not unverified:
        # Форма «Сверху» без панели вне проверенного состояния: правило «край остаётся на месте»
        # здесь заведомо неверно (22–23 места), без ключа отказ
        raise EditError(f"{axis} у формы: у формы «Сверху» без нижней командной панели размер платформа пишет по краю H′−20 (`top_size_plan_nobar`), а здесь форма не в "
                        "проверенном состоянии (нижний край не H−36, правая не на W, страницы после первой, DPI), и правило «край остаётся на месте» с этим расхождением "
                        "(22–23 места) — заведомо не то, что пишет платформа. Позвать всё же можно — unverified=True: запишется это правило со словами")
    if move_with_edge and formula is not None:
        raise EditError(f"{axis} у формы: ключ move_with_edge (элементы сдвигаются вместе с краем) здесь не применим — у формы «Сверху» раскладку области страниц при смене размера "
                        "платформа пишет сама (`top_size_plan`), и перенос элементов вместе с краем с ней не сведён. Смените размер без ключа")
    if formula is None:
        rules = _form_edge_rules(doc, side)
        askew = 0
        for element, _anchor, rule, edge_at in rules:
            if edge_at != size_now + rule[RULE_OFFSET]:
                askew += 1
            if not move_with_edge:
                writes.append((rule, RULE_OFFSET, rule[RULE_OFFSET] - delta, None,
                               f"{(element.get(NAME_BLOCK) or {}).get(NAME)}"))
        edge_words = ""
        if move_with_edge:
            from . import edgemove
            moves, moved_names, clashes = edgemove.plan(container(doc), axis, delta)
            if clashes and not unverified:
                shown = "; ".join(f"«{name}» держат {', '.join(f'«{n}»' for n in names)}" for name, names in clashes[:6])
                raise EditError(f"{axis} у формы с move_with_edge: у сдвигаемых вместе с краем элементов есть зависимые, которые за них держатся правилом: {shown}. "
                                "Платформа пересчитала бы места зависимых сама, а в файле они остались бы прежними. Позвать всё же можно — unverified=True: зависимые "
                                "остаются на местах, смещения привязок не меняются")
            writes += moves
            left_behind = "; ".join(f"«{name}» — {', '.join(names)}" for name, names in clashes)
            edge_words = (f"move_with_edge: границы {len(moved_names)} элементов, привязанных к {edge} краю (форма или край панели), сдвинуты на {delta:+d} вместе с краем "
                          "(смещения привязок прежние, «край = размер + смещение» держится), как при перетаскивании края формы в конфигураторе; "
                          + (f"зависимые от них элементы остались на местах: {left_behind}; " if clashes else "")
                          + "в предприятии этот перенос не проверялся")
        guides = _form_edge_guides(doc, number, pages)
        moved_guides, unbound, odd = 0, 0, 0
        for guide in guides:
            offset = guide.get(GUIDE_OFFSET)
            if not isinstance(offset, int) or isinstance(offset, bool) or offset == 0:
                unbound += 1
                continue
            if guide.get(GUIDE_COORD) != size_now - offset:
                odd += 1
            coord = guide.get(GUIDE_COORD)
            if not isinstance(coord, int) or isinstance(coord, bool):
                unbound += 1
                continue
            writes.append(_edge_guide_write(guide, coord, offset, delta))
            moved_guides += 1
        elements = len({id(element) for element, *_rest in rules})
        shift, grow = f"{-delta:+d}", f"{delta:+d}"
        if move_with_edge:
            notes.append(f"{edge_words}; направляющих края (номер {number}) сдвинуто {moved_guides} (координата {grow}, отступ прежний)")
        else:
            notes.append(
                f"{ROUND15_SIZE}; операция пишет то же: смещений привязок к {edge} краю формы (объект 0, "
                f"сторона {side}; `rule` и `rule2`, у любой из четырёх привязок) переписано "
                f"{len(rules)} у {elements} элементов ВЕРХНЕГО уровня ({shift}), "
                f"направляющих края (номер {number}) сдвинуто {moved_guides} (координата {grow}, отступ прежний). "
                "Координаты элементов прежние: «растянуть к новому краю» — отдельное действие "
                "(координаты элементов), которого операция не делает. Вложенные элементы не тронуты — объект 0 "
                "у их привязки край родителя (панели), а не формы (проверено). У элемента верхнего уровня "
                "дальний край равен размеру формы плюс смещение, а координата направляющей с отступом — "
                "«размер − отступ»")
        if askew and not move_with_edge:
            notes.append(f"у {askew} из {len(rules)} правил край элемента и до правки не был «размер + "
                         "смещение» — у проверенных форм равенство держалось у всех, и что платформа делает с "
                         f"таким правилом, не проверялось; операция сдвинула его тем же {shift}")
        if odd:
            notes.append(f"у {odd} направляющих края координата и до правки не была «размер − "
                         f"отступ» — не проверялось; операция сдвинула координату тем же {grow}")
        if unbound:
            notes.append(f"направляющих края без отступа (0 — к краю не привязаны) {unbound}: не "
                         "тронуты — у проверенных форм отступ был 8, а что платформа делает с нулевым, "
                         "не проверялось")
        # Направляющие без номера края (добавленные человеком): платформа таких не видела.
        extra = [g for g in (layout_block(container(doc), need=False) or {}).get(GUIDES) or ()
                 if isinstance(g, dict) and g.get(GUIDE_ORDER) not in (1, 2, 3, 4)
                 and g.get(GUIDE_OFFSET)]
        if extra:
            notes.append(f"направляющих без номера края с отступом у формы {len(extra)} — не тронуты: "
                         "таких в проверенных формах не было, и что с ними делает платформа, не проверялось")
    if pages > 1 and _tabs_top(doc) and formula is None:
        notes.append(FORM_SIZE_TABS_WORDS)
    if pages > 1 and formula is None:
        notes.append(f"страниц самой формы {pages}: то же правило положено на каждую (направляющие "
                     "края — по номеру страницы, элементы — по своей странице) — не "
                     "проверялось: размер проверен у одностраничной формы")
    if border not in (None, FORM_NO_BORDER) and formula is not None:
        notes.append(f"у формы Рамка ({border}): раскладка области страниц проверена у формы без Рамки — с Рамкой не "
                     "проверялась")
    elif border not in (None, FORM_NO_BORDER):
        notes.append(f"у формы Рамка ({border}): арифметика та же, что у формы с Рамкой "
                     "(координата прежняя, отступ свой, 6 вместо 8), но размер формы с "
                     "Рамкой не проверялся")
    if delta < 0:
        notes.append("размер УМЕНЬШЕН: проверялось увеличение" + ("; арифметика та же (смещения " + shift + ")" if formula is None
                                                                else "; раскладка области страниц при уменьшении не проверялась")
                     + ", но уменьшение не проверялось — " + (
                         "элементы, привязанные к краю, сдвигаются вместе с ним (move_with_edge), остальные у края могут оказаться за новым краем формы"
                         if move_with_edge else "элементы у края могут оказаться за новым краем формы, операция их не двигает"))
    # Короткий блок формы (DPI нет — у форм 8.0/8.1) и поколения 10, 13, 15 — не отказ (арифметика
    # корпусу не противоречит, `CORPUS_FORM_EDGES_AT_SIZE`), а слова и без пометки проверки.
    version = _design.form_version(doc)
    if dpi is None:
        notes.append("у формы короткий блок — DPI и физического размера нет: правило "
                     "положено и на неё, но проверялась форма с DPI 96, и пометки проверки нет")
    if version != FORM_PAGE_VERSION:
        notes.append(f"форма поколения {version}: правило положено и на неё, но проверялась "
                     f"форма поколения {FORM_PAGE_VERSION}, и пометки проверки нет"
                     + (f" ({FORM_SIZE_OLD})" if version == FORM_PAGE_OLD else ""))
    if move_with_edge:
        structure = MOVE_EDGE_STRUCTURE
    elif dpi is not None and dpi != 96:
        structure = "DPI не 96"
    elif dpi is None:
        structure = FORM_SIZE_NO_DPI
    elif version != FORM_PAGE_VERSION:
        structure = f"поколение {version}" if version in FORM_SIZE_VERSIONS else \
            "поколение иное"
    elif pages > 1:
        structure = "страниц больше одной"
    elif nobar_top and formula is not None:
        structure = TOP_SIZE_NOBAR_STRUCTURE
    elif border not in (None, FORM_NO_BORDER):
        structure = "с рамкой"
    elif delta < 0:
        structure = "уменьшение"
    else:
        structure = ROUND15_SIZE_CHECKED
    return writes, notes, structure


# Спутник ЦветаРамки формы: безымянная `title_picture/u6` страниц формы. Пересохранение переписывает
# её у первой страницы 2 → 1 при RGB ЦветеРамки. Обратный путь RGB → стилевой: платформа
# пересчитывает её в 2 на каждой странице, операция пишет 2 сразу. Проверено у одностраничной формы;
# у многостраничной правило то же на каждую страницу — слова «не проверялось». Иное значение позиции
# (0 у страниц форм без стиля, `CORPUS_PAGE_TITLE_U6`) не трогается.
PAGE_TITLE_PICTURE = _at("Element.PanelPage", 2)
TITLE_U6 = _maybe("Picture", 6)
COLOR_KIND = _at("Color", 1)
BORDER_COLOR_RGB = 0
ROUND15_BORDER_PAGE = ("спутник ЦветаРамки RGB: пересохранение переписывает "
                       "`title_picture/u6` страницы формы 2 → 1, у форм без ЦветаРамки — нет "
                       "(проверено в предприятии)")
ROUND16_BORDER_PAGES = ("у формы с двумя страницами `title_picture/u6` [1, 1] платформа приняла и "
                        "сохранила как записано")
ROUND16_BORDER_BACK = ("обратный путь ЦветаРамки RGB → стилевой: собрано с "
                       "`title_picture/u6` = 1, платформа при сборке и при Ctrl+S пересчитала её в "
                       "2; операция пишет 2 сразу")
BORDER_PAGES_CHECKED = 2  # страниц у проверенной формы с RGB


def _border_color_pages(doc, target, found_all, trail, new, pages):
    """ЦветРамки формы: `(записи, слова)` — `title_picture/u6` страниц формы: RGB — 2 → 1, RGB →
    стилевой — 1 → 2; стилевой, который и был стилевым, — позицию не трогает.
    """
    current = next((found.holder.get(found.key) for found in found_all
                    if _form_trail(found) == FORM_BORDER_COLOR), None)
    was = current.get(COLOR_KIND) if isinstance(current, dict) else None
    kind = was
    if trail == FORM_BORDER_COLOR:
        kind = new.get(COLOR_KIND) if isinstance(new, dict) else kind
    elif trail == f"{FORM_BORDER_COLOR}/{COLOR_KIND}":
        kind = new
    block = layout_block(container(doc), need=False)
    items = (block or {}).get(PAGES, {}).get(PAGE_ITEMS) or []
    pictures = [(at, (page or {}).get(PAGE_TITLE_PICTURE)) for at, page in enumerate(items)
                if isinstance(page, dict)]
    rgb = kind == BORDER_COLOR_RGB
    back = not rgb and was == BORDER_COLOR_RGB
    if not rgb and not back:
        seen = ", ".join(f"{at}: {picture.get(TITLE_U6)!r}" for at, picture in pictures
                         if isinstance(picture, dict))
        return [], [f"ЦветРамки формы не RGB (вид {kind!r}) и до правки не был RGB (вид {was!r}): "
                    "спутник `title_picture/u6` страниц формы операция не трогает "
                    f"(сейчас по страницам {seen or '—'})"]
    source, target_value = (1, 2) if back else (2, 1)
    writes, moved, other = [], [], []
    for at, picture in pictures:
        value = picture.get(TITLE_U6) if isinstance(picture, dict) else None
        if value == source:
            writes.append((picture, TITLE_U6, target_value, None, f"страница {at}"))
            moved.append(at)
        elif value != target_value:
            other.append(f"{at}: {value!r}")
    notes = []
    words = ROUND16_BORDER_BACK if back else ROUND15_BORDER_PAGE
    if moved:
        notes.append(f"`title_picture/u6` страниц формы ({', '.join(map(str, moved))}) "
                     f"{source} → {target_value} — {words}")
    else:
        notes.append(f"`title_picture/u6` страниц формы уже {target_value} — писать нечего "
                     f"({words})")
    if pages == BORDER_PAGES_CHECKED and not back:
        notes.append(ROUND16_BORDER_PAGES)
    elif pages > (1 if back else BORDER_PAGES_CHECKED):
        notes.append(f"страниц самой формы {pages}: спутник записан у каждой — не "
                     "проверялось; проверено: ЦветРамки "
                     + ("при обратном пути у одностраничной формы" if back else
                        "у одно- и двухстраничной формы"))
    if other:
        notes.append(f"у страниц {', '.join(other)} позиция ни {source}, ни {target_value} — не "
                     "тронута: такого значения не встречалось")
    return writes, notes


def _form_checks(doc, target, found_all, old, new, bit, unverified, move_with_edge=False):
    """Что у свойства формы зависит от документа: `(записи, оговорки, хвост отчёта)` или отказ.

    * Размеры (`width`, `height`) — с физическим размером при DPI 96; при другом DPI — отказ,
      снимаемый `unverified` (число там в единицах формы, а что показывает палитра, не проверялось).
      Смещения привязок к краю и координаты направляющих края — как их переписывает платформа
      (`_form_size_writes`); элементы на месте, направляющие края идут вместе с краем.
    * «Сохранять значения» и ВосстанавливатьЗначенияПриОткрытии — только у блока НАСТРОЕК: у формы
      объекта на тех же позициях другое (отказ без выхода).
    * Рамка (вид) и РежимПрокручиваемыхСтраниц — перестройка раскладки: платформа сдвигает отступы
      направляющих и привязки элементов к краю формы, а операция блок координат не ведёт; отказ,
      снимаемый `unverified`.
    * ПоложениеОкна — два флага одной строки палитры: поставленный снимает второй.
    * ЦветРамки RGB — спутник `title_picture/u6` страниц формы (2 → 1).

    Четвёртое в ответе — строение для пометки проверки (`ROUND15_FORM`): у размеров своё
    (`_form_size_writes`: поколение, DPI, страницы, Рамка, знак правки), у прочих — одна страница у
    формы или больше.
    """
    trail = _form_trail(target)
    writes, notes = [], []
    pages = _form_pages_count(doc) or 1
    structure = "одна страница" if pages == 1 else (
        "две страницы" if pages == 2 else "страниц больше одной")
    written, row = _form_written(trail)
    if move_with_edge and written not in (FORM_WIDTH, FORM_HEIGHT):
        raise EditError("move_with_edge — ключ размера самой формы (`form: true`, `width` или `height`): элементы, привязанные к правому или нижнему краю, "
                        "сдвигаются вместе с краем; к другим свойствам формы он не относится")
    if written in (FORM_WIDTH, FORM_HEIGHT):
        # Размер тем же числом — не правка: строения нет, и пометки проверки тоже (ниже, при новом
        # числе, строение даёт `_form_size_writes`).
        structure = None
    block = doc.get(FORM_BLOCK) if isinstance(doc, dict) else {}
    if written in (FORM_SETTINGS + "/save_values", FORM_SETTINGS + "/restore_values_on_open"):
        words = _form_settings_words(doc, target.slot.name)
        if words is not None:
            raise EditError(words)
    if written in (FORM_WIDTH, FORM_HEIGHT) and new != old:
        axis = "width" if written == FORM_WIDTH else "height"
        device = f"device_{axis}"
        dpi = block.get(DPI) if isinstance(block, dict) else None
        if isinstance(block, dict) and device in block:
            if dpi != 96 and not unverified:
                raise EditError(
                    f"{axis} у формы: DPI формы {dpi}, и число в файле — в единицах ФОРМЫ, а какое "
                    "число показывает палитра при таком DPI, не проверялось (проверено на DPI "
                    f"96). Физический размер операция вывела бы по правилу {axis} × "
                    f"{dpi}/96 с отбрасыванием дробной части, но единицы самого числа остаются догадкой. Позвать всё же "
                    "можно — unverified=True: число запишется как дано, в единицах формы")
            want = new if dpi == 96 else int(new * dpi // 96)
            if block[device] != want:
                rule = ("при DPI 96 физический размер равен логическому"
                        if dpi == 96 else
                        f"при DPI {dpi} физический размер — {axis} × {dpi}/96 с отбрасыванием "
                        f"дробной части; число {axis} — в единицах формы, что "
                        "показывает палитра при таком DPI, не проверялось")
                writes.append((block, device, want, rule,
                               f"form/{device}"))
        else:
            notes.append("у короткого блока формы (16) физического размера и DPI нет — "
                         f"записан один {axis}")
        edge_writes, edge_notes, structure = _form_size_writes(doc, axis, old, new, unverified, move_with_edge)
        writes += edge_writes
        notes += edge_notes
    if written == FORM_BORDER:
        holder = next((found.holder.get(found.key) for found in found_all
                       if _form_trail(found) == FORM_BORDER), None)
        was = holder.get("border_type") if isinstance(holder, dict) else None
        if trail == FORM_BORDER:
            will = new.get("border_type") if isinstance(new, dict) else was
        else:
            will = new if trail == FORM_BORDER + "/border_type" else was
        if will != was:
            words = ("рамка формы отнимает у её клиентской области два пикселя, и платформа, "
                     "ставя Рамку «Одинарная», сдвинула вместе с ней "
                     "отступы правой и нижней направляющих (8 → 6) и привязки к правому и нижнему "
                     "краю формы у всех элементов (−8 → −6); операция блок "
                     "координат и направляющие не ведёт")
            block = layout_block(container(doc), need=False)
            shown_tabs = block.get(SHOW_TABS) if isinstance(block, dict) else None
            tabbed = shown_tabs == "Top"  # проверено только «Сверху»
            if tabbed:
                words += "; " + FORM_BORDER_TABS_WORDS
            # У формы без нижней панели «Одинарная» при «Не отображать» платформа переписывает
            # нижний край страницы 0 (412/8 → 396/6, 387/33 → 387/15, правила +2) — под `unverified`
            # операция пишет и его.
            nobar_writes, nobar_words = (None, "") if tabbed else border_nobar_plan(doc, will)
            if not unverified:
                raise EditError(
                    f"Рамка формы {_short(was)} → {_short(will)}: это перестройка раскладки — {words}. "
                    + ("Из конструктора такую Рамку не поставить (строка серая); " if tabbed else
                       "Правьте Рамку формы в конфигураторе; ")
                    + "позвать всё же можно — "
                    + (f"unverified=True: запишется рамка и сдвиг нижнего края страницы 0 ({nobar_words}). " if nobar_writes is not None else
                       "unverified=True: запишется ровно рамка, а направляющие и привязки останутся как были"))
            if nobar_writes is not None:
                writes += nobar_writes
                notes.append(f"Рамка формы и сдвиг нижнего края страницы 0: {nobar_words}")
            else:
                notes.append(f"Рамка формы записана одна: {words} — сдвиг не сделан")
        if trail == FORM_BORDER + "/border_type" and will != was and will not in (None, "WithoutBorder") \
                and isinstance(holder, dict) and holder.get("explicit") is False:
            # Платформа, поставив вид Рамки, пишет и `explicit` false → true (проверено у всех семи
            # видов); редактор оставлял `false`.
            writes.append((holder, "explicit", True,
                           "платформа при всех проверенных видах Рамки пишет и признак явной Рамки; «Нет рамки» не проверялось — у «Нет рамки» признак не трогается",
                           "form/layout/border/explicit"))
    if written == FORM_SCROLL and new != old:
        words = ("вместе с ним платформа поставила ОтображениеЗакладок "
                 "кодом 13, которого перечисление не знает, и сдвинула привязки всех элементов к "
                 "правому и нижнему краю формы на 8 (−8 → 0); в образцах форм режим не встречается")
        if not unverified:
            raise EditError(
                f"РежимПрокручиваемыхСтраниц формы {_short(old)} → {_short(new)}: это перестройка "
                f"раскладки — {words}; операция блок координат не ведёт. Ставьте режим в "
                "конфигураторе; позвать всё же можно — unverified=True: запишется один флаг")
        notes.append(f"записан один флаг: {words} — операция этого не повторила")
    if written == FORM_BORDER_COLOR:
        page_writes, page_notes = _border_color_pages(doc, target, found_all, trail, new, pages)
        writes += page_writes
        notes += page_notes
    if written in (FORM_CENTER, FORM_OVERLAP) and new is True:
        other = FORM_OVERLAP if written == FORM_CENTER else FORM_CENTER
        if doc.get(other) is True:
            writes.append((doc, other, False,
                           "ПоложениеОкна — ОДНА строка палитры о трёх значениях (Авто, "
                           "Центрировать, НеПерекрыватьВладельца), а в файле два флага: оба сразу "
                           "не встречаются ни у одной формы; каждый ставится при снятом втором",
                           other))
    tail = ""
    if row is not None:
        tail = f"; строку «{row[0]}» платформа записывает сама ({row[1]})"
        if (props.FORM_ANCHOR, written) not in ROUND15_FORM \
                and (props.FORM_ANCHOR, written) not in ROUND17_FORM:
            tail += ("; правку операцией у этой строки не проверяли (проверены Стиль и "
                     f"{len(ROUND15_FORM)} строк палитры формы, этой среди них нет)")
    return writes, notes, tail, structure


# Смена вида закладок панели с вложенными элементами: поле записывается, вложенные не трогаются — их
# box и направляющие остаются под прежний вид, а предприятие ставит вложенные по правилам от области
# страницы нового вида (проверено у панели без Рамки: «Сверху», «Сверху (с прокруткой)», «Снизу» —
# размер панели минус (2, 20), «Слева (горизонтально)» — минус (72, 2), «Не отображать» — как есть).
# Что платформа пишет в файл при смене вида в конструкторе, не проверялось. Замечание `validate`
# приходит только у панели без Рамки, чьи направляющие легли на область другого проверенного вида; у
# панели с Рамкой и с иными направляющими раскладка вложенных после смены вида не проверялась, и
# тишина `validate` не значит «проверено».
NESTED_TABS_WORDS = (
    "вложенные элементы панели при смене вида закладок не перекладываются: их box и направляющие остаются под прежний вид; "
    "предприятие разложит их по правилам от области страницы нового вида (проверено у панели без Рамки: «Сверху», «Сверху (с "
    "прокруткой)», «Снизу», «Слева (горизонтально)», «Не отображать»); замечание `validate` («область "
    "вложенных») придёт только у панели без Рамки, чьи направляющие легли на область другого проверенного вида — у панели с "
    "Рамкой и с иными направляющими раскладка вложенных после смены вида не проверялась, молчание `validate` не значит «проверено»; "
    "что пишет конфигуратор при смене вида, не проверялось — проверьте раскладку в предприятии")


def _has_nested(node):
    try:
        return any(isinstance(item, dict) for item in elements_of(node))
    except EditError:
        return False


def _set_property(doc, element=None, name=None, value=NO_VALUE, column=None, nested=False,
                  page=None, button=None, form=False, unverified=False, move_with_edge=False):
    """Поле карты по имени — у элемента, у колонки (`column`), у её вложенного элемента (`column` +
    `nested=True`), у страницы панели (`page`), у кнопки командной панели (`button`; `element` тогда
    — имя панели или кнопки-меню) или у самой формы (`form=True`, без `element`).

    **Имя — как в `FORMAT.md`**: голое (`mask`), путём от корня, когда голое носят несколько полей
    (`u3/u1/u1/mask`), или битом слова (`flags/default_control`, а если бит с таким именем у корня
    один — просто `default_control`). Значение — как его отдаёт `decode`: перечисление именем, флаг
    `true`/`false`, блок объектом; многоязычную строку можно дать текстом.

    **Чего операция не пишет — и отказывает словами** (`_property_refusal`): поле, у которого есть
    своя операция (шрифт, события, подпись, связь по типу, меню, колонки, кнопки, страницы, имя),
    флаг строения (ключ варианта, флаг необязательного блока, счётчик, версия записи, постоянное),
    список или отрезок раскладки, блок-родитель и безымянную позицию.

    **Что ведёт сама**: зеркала (`mirror_of` карты — то же значение по второму адресу; у
    блока-зеркала — и его подполя, `_block_mirror`; у блока, внутри которого лежит зеркало, — и
    первичное, `_inner_mirrors`) и то, что платформа пишет одной правкой палитры (`_cowrites`: маска
    в двух местах и снятый перенос строк, код многострочности, квалификаторы типа в описателе, бит
    «Дерево»). Отчёт называет каждое.

    **Граница — три яруса** (`_property_bounds`): значение, которое корпус держит у этого поля этого
    типа, — «есть в корпусе» с числом; которого корпус не держит, а платформа писала в проверенных
    формах, — пометка с формой; невиданное — отказ, снимаемый `unverified=True`. Правило одно, по
    какой дороге ни пиши: блок сверяется и каждым скалярным подполем по его строке
    (`_block_bounds`), а поле, что ходит парой (метка картинки — с версией записи, код цвета — с
    видом, код ссылки картинки — с источником), — ещё и строкой пары (`_pair_bounds`, у вида цвета
    по имени — `_partner_bounds`); у картинки колонки метка та же, что у двух соседних
    (`_column_marks`). У проверенных значений вместо корпусной пометки — «подтверждено в
    конфигураторе и предприятии» (`ROUND11_PROPERTIES`), у ГоризонтальногоПоложения — «подтверждено
    конфигуратором», у «Активизировать по умолчанию» колонки — «принято платформой, действие не
    установлено» (`ROUND11_ACCEPTED`); то же у `ROUND12_PROPERTIES` и `ROUND152_PROPERTIES` (значения новых видов, подтверждённые живыми кругами), Стиль формы — `ROUND12_STYLE`.
    У прочих значений слова «проверено платформой» отчёт не говорит, а у невиданного, пропущенного
    `unverified`, пометки проверки нет — остаётся «корпус такого не видел ни разу». Пометка ставится
    только в том строении, которое проверяли (`_round_structure`): ширину — у колонки с вложенным
    элементом и зеркалом, РежимВыбораИзСписка поля формы — у поля со своим реквизитом формы
    строкового типа; у прочих — слова `ROUND_STRUCTURE_WORDS`.

    **Целое двумя записями** (вид `int-exp`, ширина колонки) операция пишет так, как пишет платформа
    (`json0.int_exp_text`: `20` → `2e1`, `28` → `28`) — в оба адреса, и у колонки без вложенного
    элемента тоже: зеркало там на позицию раньше (`schema.COLUMN_HEAD_BARE`). У формы с DPI не 96
    ширину с зеркалом не пишет вовсе, а без зеркала — только под `unverified` и без пометки
    проверки: число там в единицах формы (`_mirror_dpi_check`).

    **РежимВыбораИзСписка ☑ у поля формы** ведёт и тип — по виду данных поля (`_list_choice_data`):
    у реквизита формы в один шаг снимает тип у поля и реквизита и ставит Длину 255, как журнал;
    через основной реквизит тип не трогает; прочее — отказ словами.

    **`move_with_edge`** (только `form: true` и `width`/`height`) — размер формы, как при перетаскивании её края в конфигураторе: элементы, привязанные
    к правому (нижнему) краю формы, сдвигаются вместе с краем (их граница += Δ, смещения привязок прежние; у панели вложенные элементы, привязанные к её
    краю, — на изменение размера панели). Без ключа — как при смене размера палитрой: элементы на месте, смещения привязок переписаны. Отказ словами,
    если у сдвигаемого элемента есть зависимые от него (снимает `unverified`: они остаются на местах) или размер элемента стал бы нулевым.

    **Преднастройки палитры** (`LINKED`): строка, живая только при другом значении соседа,
    записывается, а отчёт предупреждает, если сосед сейчас не тот.
    """
    if name is None:
        raise EditError("name — имя поля карты (как в FORMAT.md) или путь к нему, а его нет")
    if value is NO_VALUE:
        raise EditError("value — значение поля, как его отдаёт decode, а его нет")
    if not form and element is not None and column is None and not nested and page is None and button is None \
            and name in _rowsa.NAMES:
        return _rowsa.write(doc, element, name, value, unverified)
    if not form and element is not None and column is None and not nested and page is None and button is None \
            and name in _chartrows.NAMES:
        # Строки палитры диаграммы лежат в теле записи (`chartrows`); у элемента другого вида те же имена идут обычным путём.
        found = _chartrows.write(doc, element, name, value, unverified)
        if found is not None:
            return found
    if not form and element is not None and column is None and not nested and page is None and button is None \
            and name in _kindrows.NAMES:
        # Строки палитры диаграммы Ганта, дендрограммы и сводной диаграммы — в теле записи и в блоке содержимого (`kindrows`).
        found = _kindrows.write(doc, element, name, value, unverified)
        if found is not None:
            return found
    if not form and element is not None and column is None and not nested and page is None and button is None \
            and name in _schemarows.NAMES:
        # Строки палитры полей схем и поля PDF-документа лежат во вложенных списках записи элемента (`schemarows`); у других видов те же имена идут обычным путём.
        found = _schemarows.write(doc, element, name, value, unverified)
        if found is not None:
            return found
    if name in BORDER_BLOCK_NAMES and isinstance(value, str) and not form:
        # Рамка словом у любого вида: слово палитры («Одинарная») или имя перечисления (`Single`) ставит вид рамки, а блок целиком
        # (голова, признак «задана явно», элемент стиля) пишет общий путь `border/border_type` так, как его пишет платформа для этого вида.
        name, value = f"{name}/border_type", border_word(value, name)
    form_page = bool(form) and page is not None and page is not False
    page_note = ""
    if form_page:
        named = [key for key, given in (("element", element), ("column", column),
                                        ("nested", nested), ("button", button))
                 if given not in (None, False)]
        if named:
            raise EditError(f"form=true с page — свойство СТРАНИЦЫ формы, и {', '.join(named)} у него не "
                            "называют")
        item, whose, page_note = form_page_root(doc, page, name, unverified)
        # Страница формы — та же запись, что у панели: якорь границы корпуса общий (`PanelPage`).
        root, root_type, anchor, stop, base = item, "Element.PanelPage", props.PAGE_ANCHOR, (), ()
    elif form:
        named = [key for key, given in (("element", element), ("column", column),
                                        ("nested", nested), ("page", page), ("button", button))
                 if given not in (None, False)]
        if named:
            raise EditError(f"form=true — свойство САМОЙ формы, и {', '.join(named)} у него не "
                            "называют")
        if name in _ctxmenu.NAMES:
            return _ctxmenu.set_by_name(doc, None, name, value)
        special = _form_property(doc, name, value, unverified)
        if special is not None:
            return special
        # Корень — сам документ, якорь границы — `Form`; что форма пишет, решает перечень строк её
        # палитры (`FORM_WRITES`, `_form_refusal`).
        root, root_type, anchor, stop, base, whose = (doc, props.FORM_TYPE, props.FORM_ANCHOR,
                                                      props.FORM_STOP, (), "формы")
    elif element is None:
        raise EditError("element — имя элемента формы (или form=true — свойство самой формы), а "
                        "его нет")
    else:
        if name in VISIBLE_NAMES and column is None and page is None and button is None and not nested:
            return _set_visible(doc, element, value)
        if name == "default_control" and column is None and page is None and button is None and not nested:
            return _set_default_control(doc, element, value)
        if name in _ctxmenu.NAMES and column is None and page is None and button is None and not nested:
            return _ctxmenu.set_by_name(doc, element, name, value)
        root, root_type, anchor, stop, base, whose = _property_root(doc, element, column, nested,
                                                                    page, button)
    if anchor in NUMBER_QUALIFIER_ANCHORS and name in NUMBER_QUALIFIERS and not (column or nested or page is not None or button):
        return _number_qualifier(doc, element, anchor, name, value)
    found_all = list(props.fields(root, root_type, stop=stop + tuple(PROPERTY_OPS)))
    lost = list(props.demoted(root, root_type, stop=stop + tuple(PROPERTY_OPS)))
    matches = _property_matches(found_all, name, whose)
    if not matches:
        matches = _demoted_matches(lost, name)
        found_all += [found for found, _bit in matches]
    if not matches:
        missing = _form_missing(root, found_all, name) if anchor == props.FORM_ANCHOR \
            else _unnamed_position(root, found_all, name, whose)
        raise EditError(missing or _property_missing(found_all, name, whose, anchor))
    groups = []
    for found, bit in matches:
        primary, _mirrors = (found, []) if bit is not None else _mirror_group(found_all, found, base)
        primary = _block_mirror(found_all, primary, base)[0]
        twin = next(((node, key) for node, key in MASK_NODES if (primary.node, primary.key) ==
                     (node, key)), None)
        mark = (MASK_NODES[0], None) if twin is not None else (id(primary), bit)
        if mark not in [group[0] for group in groups]:
            groups.append((mark, primary, bit))
    if len(groups) > 1:
        where = ", ".join("/".join(primary.trail) + (f"/{bit}" if bit else "")
                          for _mark, primary, bit in groups)
        raise EditError(f"имя {name!r} у {whose} носят "
                        f"{schema.plural(len(groups), 'поле', 'поля', 'полей')} ({where}) — какое "
                        "ставить, по имени не решить; назовите путём, как в перечне")
    _mark, target, bit = groups[0]
    if (target.node, target.key) == MASK_NODES[1]:
        target = _find_one(found_all, *MASK_NODES[0]) or target
    refusal = _property_refusal(target, anchor, bit)
    if refusal is not None:
        raise EditError(f"{name} у {whose}: {refusal}")
    slot, holder, key = target.slot, target.holder, target.key
    current = holder.get(key)
    old = current.get(bit) if bit is not None and isinstance(current, dict) else current
    if bit is None and (target.node, slot.name) == (TEXT_DOCUMENT_NODE, EXTENSION):
        value = _extension_value(value, name, whose)
    file_words = ""
    if bit is None and _is_file_value(value):
        value, file_words = _file_picture_value(slot, current, value, name, whose, anchor, unverified)
    radio_words = ""
    if (bit is None and slot.name == "selected_value" and not form and element is not None and column is None and not nested and page is None
            and button is None and not isinstance(value, dict)):
        from .data import radio_value
        value, radio_words = radio_value(doc, element, value)
    new = _property_value(slot, bit, value, current, name, whose)
    notation = dpi_note = ""
    if bit is None and isinstance(slot, schema.F) and slot.kind == schema.INT_EXP:
        new, notation = _platform_int(new, name, whose)
        dpi_note = _mirror_dpi_check(doc, found_all + lost, target, base, whose, unverified)
    if bit is None and isinstance(slot, schema.F) and slot.kind == schema.INT_DEC:
        new, notation = _platform_scale(new, name, whose)
    data_writes, data_notes, data_kind = [], [], None
    if form_page:
        # Страница формы: безымянная позиция 6 картинки заголовка 0 → 2 меняется только при установке картинки; Видимость и
        # Доступность её не трогают (снято по одной правке на страницу).
        item = root
        if name == "title_picture" and isinstance(new, dict) and old != new:
            new = dict(new)
            cowrite, words = u6_cowrite(item, new)
            if cowrite is not None:
                new[cowrite[1]] = cowrite[2]
                data_notes.append(f"{cowrite[4]} 0 → {cowrite[2]} — {words}")
    # Свойство самой формы: что зависит от документа, а не от поля, — DPI у размеров, строение блока
    # основного реквизита у сохранения значений, перестройка раскладки у Рамки и
    # РежимаПрокручиваемыхСтраниц, согласованные поля и оговорки; отказ — до любой записи.
    form_writes, form_notes, form_tail, form_structure = [], [], "", None
    if anchor == props.FORM_ANCHOR:
        form_writes, form_notes, form_tail, form_structure = _form_checks(
            doc, target, found_all + lost, old, new, bit, unverified, move_with_edge)
    elif move_with_edge:
        raise EditError("move_with_edge — ключ размера самой формы (`form: true`, `width` или `height`): элементы, привязанные к правому или нижнему краю, "
                        "сдвигаются вместе с краем; к другим свойствам он не относится")
    tabs_switch, tabs_words, tabs_note, tabs_back = False, [], TABS_AREA_NOTE_UNMEASURED, False
    if form and slot.name == SHOW_TABS and new == "Top" and old != "Top":
        if old == "DontUse":
            # Один признак вида нижнего края на все операции страниц: отказ словами у видов, которые
            # платформа переписала иначе (`nobar33`, `bar8`, `nobar8`), — без ключа; под ним запись.
            tabs_switch, tabs_words, tabs_note = tabs_top_plan(doc, unverified=unverified)
        else:
            tabs_words = [f"закладки были {_short(old)}, а проверялось включение «Сверху» из «Не отображать»"]
        if tabs_words and not unverified:
            raise EditError(
                f"show_tabs у формы: «Сверху» включают, и платформа при этом переписывает страницу 0 "
                f"(нижняя направляющая −19, смещения к низу формы +19, номера создания) — это проверено "
                f"у формы без Рамки при DPI 96 из «Не отображать»; здесь шире: "
                f"{'; '.join(tabs_words)}. Позвать всё же можно — unverified=True: поле запишется, "
                "страница 0 пересчитывается только у вида `bar33` (панель и отступ 33) при крае "
                "нижней направляющей по высоте формы; у прижатого элемента его собственные правила к низу формы не трогаются — "
                "отчёт это называет")
        if tabs_switch:
            check_page0_rewritable(doc)       # отказ словами — до любой записи
    if form and slot.name == SHOW_TABS and old == "Top" and new == "DontUse":
        # Обратный путь: страница 0 переписывается третьей раскладкой; проверено на одной форме —
        # без `unverified` отказ словами, с ним — запись.
        tabs_back, tabs_note = tabs_back_plan(doc)
        if tabs_back and not unverified:
            raise EditError(f"show_tabs у формы: {tabs_note or BACK_ONE_FORM}")
    if (target.node, key) == ("Content.TextBox", LIST_CHOICE_MODE):
        _list_choice_check(found_all, old, new, whose)
        if new is True and old is not True:
            data_writes, data_notes, data_kind = _list_choice_data(doc, element, anchor,
                                                                   found_all, whose, unverified)
        elif new is False and old is True:
            data_writes, data_notes, data_kind = _list_choice_off(doc, element, anchor,
                                                                  found_all, whose, unverified)
    # Поле, чьё имя снято демоцией, зовётся по имени карты и в пути границы: корпус держит его
    # значения под именем (там, где вид подошёл), а запасной ключ — свойство этого файла.
    renamed = key != slot.name and bit is None
    trail = target.trail[:-1] + (slot.name,) if renamed else target.trail
    path = "/".join(trail) + (f"/{bit}" if bit else "")
    kind = "bit" if bit else ("node" if isinstance(slot, schema.N) else slot.kind)
    text = props.value_text(props.bit_slot(slot, bit) if bit else slot, new)
    shown = slot.name if bit is None else f"{key}/{bit}"
    brief = _short(new)
    brief = brief if len(brief) <= 120 else brief[:120] + "…"
    tail = _property_bounds(anchor, path, kind, text, new, f"{shown} = {brief}", unverified)
    outer = props.holders({found.trail: found for found in found_all}, target.trail)
    extra = ""
    if bit is None and isinstance(slot, schema.N):
        extra += _block_bounds(anchor, trail, slot, new, outer, shown, unverified)
        extra += _column_marks(target, new, unverified)
    elif bit is None:
        field = (target.node, slot.name)
        extra += _pair_bounds(anchor, path, text, f"{shown} = {brief}",
                              props.partner_of(field, outer), unverified, field, said=True)
        extra += _partner_bounds(anchor, found_all, target, new, unverified)
    # Пометка проверки — только у значения, которое граница корпуса пропустила сама: «не видел» у
    # невиданного под `unverified` обязано остаться, по какой бы дороге — поле, подполе блока или
    # пара — его ни сказали. У ширины формы с DPI не 96 пометки нет вовсе: проверка шла на DPI 96.
    if dpi_note:
        confirmed, round_tail = None, ""
    else:
        structure = form_structure if form_structure is not None else \
            _round_structure(target, found_all + lost, base, data_kind)
        confirmed, round_tail = _rounds(FORM_PAGE_ANCHOR if form_page else anchor, path, new,
                                        f"{shown} = {brief}", text,
                                        passed=UNSEEN_NOTE not in tail + extra,
                                        structure=structure)
    if confirmed and (anchor, path) in ROUND152_BLOCKS:
        extra = ""           # подполя проверенного блока цвета проверены вместе с ним
    tail = (round_tail if confirmed else tail + round_tail) + extra + dpi_note + form_tail
    writes = []
    _primary, places, depth = _block_mirror(found_all, target, base)
    for place in places:
        if place is target:
            continue
        where = "/".join(place.trail) + (f"/{bit}" if bit else "")
        # Имя блока у второго места — его путь без подполя: у зеркала путь на шаг короче, чем у
        # первичного.
        block = place.trail[:len(place.trail) - (len(target.trail) - depth)]
        note = (f"то же подполе второго места блока — блок {'/'.join(block)} лежит в "
                "файле дважды (зеркало `mirror_of` карты), и правка подполя в одном месте из "
                "двух уехала бы в базу наполовину")
        if bit is not None:
            twin = dict(place.holder.get(place.key) or {})
            twin[bit] = new
            writes.append((place.holder, place.key, twin, note, where))
        else:
            writes.append((place.holder, place.key, copy.deepcopy(new), note, where))
    if bit is not None:
        word = dict(current)
        word[bit] = new
        writes.insert(0, (holder, key, word, None, path))
    else:
        writes.insert(0, (holder, key, new, None, path))
        _primary, mirrors = _mirror_group(found_all + lost, target, base)
        for mirror in mirrors:
            note = "зеркало — второй адрес того же свойства в карте, то же значение"
            if getattr(mirror.slot, "primary_only", False):
                note += (" (платформа при правке свойства записывает только первичное место, а в формах "
                         "оба места согласованы)")
            writes.append((mirror.holder, mirror.key, copy.deepcopy(new), note,
                           "/".join(mirror.trail)))
        if isinstance(slot, schema.N):
            writes += _inner_mirrors(found_all + lost, target, new, base)
        cowrites, notes = _cowrites(found_all, target, new, anchor)
        writes += cowrites + data_writes + form_writes
        notes += data_notes + form_notes + ([page_note] if page_note else [])
    said = [f"{whose}: {shown} {_short(old)} → {_short(new)}"
            + (" (то же значение, что стояло)" if old == new and type(old) is type(new) else "")]
    if file_words:
        said.append(file_words)
    if radio_words:
        said.append(radio_words)
    if notation:
        said.append(notation)
    inverted = _inverted_words(target, bit, new)
    if inverted:
        said.append(inverted)
    if renamed:
        said.append(f"имя {slot.name} у поля было снято демоцией — значение {_short(old)} не того "
                    f"вида, что объявила карта ({slot.kind}), и JSON звал позицию {key}; значение "
                    "нужного вида возвращает ей имя")
    for where, what, val, why, label in writes:
        if why is not None:
            said.append(f"{label} {_short(where.get(what, '—'))} → "
                        f"{'—' if val is None else _short(val)} — {why}")
        if val is None:
            where.pop(what, None)
        else:
            _put_named(where, what, val, [f for f in found_all + lost
                                          if f.holder is where and f.key == what])
    if bit is None:
        said += notes
    if form and slot.name == SHOW_TABS and new == "Top":
        if tabs_switch:
            said.append(rewrite_page0_for_tabs(doc))
            if tabs_words:
                said.append("не проверялось: " + "; ".join(tabs_words))
        else:
            said.append(TABS_AREA_NOTE_AFTER if old == "Top" else tabs_note)
            if old != "Top" and tabs_note in (TABS_FRAMED_NOTE, TABS_NO_BAR_FRAMED_NOTE):
                resort_page0(doc)  # Рамка: страницу 0 не переписывает, порядок номеров — пишет
                # У `nobar8` с элементом на/ниже направляющей (`TABS_NO_BAR_NOTE`) порядок не
                # пишется: платформа пересортировала его при включении «Сверху», но на одной форме,
                # собранной редактором, а корпус порядок (низ, лево) не держит (слова
                # `TABS_NO_BAR_NOTE`).
            if tabs_words and old != "Top":
                said.append("не проверялось (записано под unverified): " + "; ".join(tabs_words))
    elif form and slot.name == SHOW_TABS and old == "Top" and new == "DontUse":
        said.append(rewrite_page0_for_dont_use(doc) if tabs_back else tabs_note)
    if not form and anchor == "Panel" and slot.name == SHOW_TABS and old != new and _has_nested(root):
        said.append(NESTED_TABS_WORDS)
    result = "; ".join(said) + tail + _linked_warning(found_all, target)
    if name == "back_color" and element is not None and not (form or column or nested or page is not None or button):
        mirrored = _schemarows.mirror_back_color(doc, element)      # у поля графической схемы цвет фона лежит ещё и в записи сетки
        if mirrored:
            result += "; " + mirrored
    return result


# Картинка из файла: значение `{"file": путь}` вместо блока Picture. Адреса — те, где картинку из файла записал
# конфигуратор (`FILE_NOTE`); `(якорь, поле)`. Якорь формы — `props.FORM_ANCHOR`; страница панели — поле
# `title_picture` (в карте типизировано как Picture, а лежит набором: внешняя запись с вложенной картинкой в `ref`).
FILE_PICTURE_ANCHORS = ("Button", "Label", "PictureBox", props.FORM_ANCHOR)
# КартинкаЗаголовка САМОЙ формы (`u13/caption_picture`) в конфигураторе не записывали: адрес карта знает, строение то же, что у
# остальных, но платформа его из файла не писала — только под `unverified`.
FORM_CAPTION_PICTURE = "caption_picture"


def _is_file_value(value):
    return isinstance(value, dict) and "file" in value and set(value) <= {"file"}


# Внешняя запись заголовка страницы: безымянная позиция u6. Платформа пишет её у каждой страницы с картинкой значением 2
# (в корпусе — у 77 из 79 страниц с картинкой, у двух остальных 1; нуля у страницы с картинкой нет ни разу, а у страниц
# без картинки 0 встречается 693 раза). Страница, у которой стоял 0, при установке картинки получает 2; значение, которого у
# страницы с картинкой не бывает, платформа не пишет. На то, нарисует ли платформа значок, позиция не влияет: страница с 0
# и картинкой рисовалась, страницы с 2 и картинкой рисовались и не рисовались.
PAGE_NO_PICTURE_U6 = 0
PAGE_WITH_PICTURE_U6 = 2
PAGE_U6_WORDS = ("позиция u6 внешней записи страницы 0 → 2: так платформа пишет страницу с картинкой (у 77 из 79 страниц "
                 "корпуса с картинкой 2, у двух 1, нуля нет); от неё значок на закладке не зависит")
# Что платформа нарисовала на закладке страницы: PNG 16×16 (две страницы, у одной из них позиция u6 была 0). У трёх
# страниц, заведённых add_page (PNG 32×32, ICO, GIF), значок не нарисован ни в предприятии, ни в конфигураторе, хотя палитра
# картинку показывает; записи этих страниц совпадают с записью страницы, поставленной платформой.
PAGE_DRAWN_FILE = ("PNG", "16×16")
PAGE_TAB_WORDS = ("значок на закладке рисуется у PNG 16×16; у PNG 32×32, ICO и GIF на закладке страницы, заведённой add_page, "
                  "платформа его не нарисовала (палитра картинку видит, запись страницы такая же, как у рисующейся); "
                  "причина — вид файла или положение страницы — не отделена")


def _file_picture_value(slot, current, value, name, whose, anchor, unverified):
    """`(значение для поля, слова отчёта)` — картинка из файла вместо блока: `{"file": путь}`.

    Строение — как у кнопки панели (`edit.buttons._file_picture`): встроенная без GUID, тело — файл целиком; метку
    берёт у блока, который стоял в узле (она ходит за версией записи-владельца). Страница панели несёт картинку
    внутри `ref` внешней записи (`{8,0,{4,3,{0},"",-1,-1,0,тело,0,""},…}`): внешняя запись остаётся как была.
    Дороги нет у колонок, вложенных элементов и кнопок командной панели: якорь их узла не в перечне `FILE_PICTURE_ANCHORS`.
    """
    page_title = slot.name == "title_picture"
    allowed = (slot.name == "picture" and anchor in FILE_PICTURE_ANCHORS) \
        or (page_title and anchor == props.PAGE_ANCHOR) or (slot.name == FORM_CAPTION_PICTURE
                                                  and anchor == props.FORM_ANCHOR)
    if not isinstance(slot, schema.N) or not allowed:
        raise EditError(
            f"{name} у {whose}: картинку из файла ({{\"file\": путь}}) ставят только у кнопки формы, надписи, "
            "поля картинки, страницы панели (`page`, свойство title_picture) и самой формы; у колонки и "
            "кнопки командной панели — иначе (set_button_picture у кнопки панели)")
    if not isinstance(current, dict):
        raise EditError(f"{name} у {whose}: в узле картинки нет, а блок строят по стоявшему")
    data = read_picture_file(value["file"])
    inner = current.get("ref") if page_title else current
    mark = inner.get("code") if page_title and isinstance(inner, dict) else (
        inner.get("mark") if isinstance(inner, dict) else None)
    words = []
    if mark not in (3, 4):
        if not unverified:
            raise EditError(
                f"{name} у {whose}: у стоявшей картинки метка блока {mark!r}, а запись из файла проверена при "
                "метке 4 (метка 3 — тот же блок без хвостовой позиции, у записей версии 3); какая метка у такой "
                "записи с телом, не проверялось. unverified=True снимает отказ: ставится метка 3")
        words.append(f"метка блока была {mark!r}: ставится 3 — не проверялось")
        mark = 3
    block, shape = _file_picture(None, value["file"], data, unverified, mark, corpus_words=False)
    if slot.name == FORM_CAPTION_PICTURE:
        if not unverified:
            raise EditError(
                f"{name} у {whose}: КартинкаЗаголовка формы из файла в конфигураторе не записывали (картинку формы и "
                "страницы панели записывали); строение то же, что у «Картинки», но платформа его по этому адресу "
                "не писала. unverified=True снимает отказ")
        words.append("КартинкаЗаголовка формы из файла не проверялась: у прочих адресов то же строение записано "
                     "конфигуратором")
    if page_title:
        body = block[_maybe("Picture", 7)]
        ref = {"code": mark, "u1": 3, "u2": [0], "u3": "", "u4": -1, "u5": -1, "u6": 0, "u7": body, "u8": 0}
        if mark == 4:
            ref["u9"] = ""
        out = dict(current)
        out["ref"] = ref
        words.append("страница панели: картинка лежит в `ref` внешней записи")
        if out.get(TITLE_U6) == PAGE_NO_PICTURE_U6:
            out[TITLE_U6] = PAGE_WITH_PICTURE_U6
            words.append(PAGE_U6_WORDS)
        block = out
    kind, _size, _whole = _image_kind(data)
    if page_title and (kind, _size) != PAGE_DRAWN_FILE:
        words.append(PAGE_TAB_WORDS)
    place = "page" if page_title else ("form" if anchor == props.FORM_ANCHOR else anchor)
    if slot.name != FORM_CAPTION_PICTURE and kind is not None:
        if kind in FILE_KINDS_BY_PLACE.get(place, ()):
            words.append(f"{kind} у этого вида записан конфигуратором этим строением")
        else:
            words.append(f"{kind} у этого вида в конфигураторе не ставили (там: "
                         f"{', '.join(FILE_KINDS_BY_PLACE.get(place, ())) or '—'}); строение общее у всех "
                         "картинок из файла, и все виды у кнопок панели записаны им же")
    return block, f"картинка {shape}" + ("; " + "; ".join(words) if words else "")


def _round_structure(target, found_all, base, data_kind=None):
    """Строение, в котором лежит поле, — для пометки проверок (`_rounds`); `None` — не различается.

    У ширины колонки строений четыре: есть ли у колонки вложенный элемент (вариант головы по
    `control_type`, `schema.COLUMN_HEAD_FORK`) и есть ли у этой головы зеркало ширины. Проверена
    ширина у колонки с элементом и зеркалом (`WIDTH_CHECKED`); у колонки без элемента без зеркала
    правка пропадает. У РежимаВыбораИзСписка поля формы строение — вид его данных, как его назвал
    `_list_choice_data`.
    """
    if target.node in COLUMN_HEAD_NODES and target.slot.name == COLUMN_WIDTH:
        _primary, mirrors = _mirror_group(found_all, target, base)
        element = "с вложенным элементом" if target.node == schema.COLUMN_HEAD \
            else "без вложенного элемента"
        return WIDTH_CHECKED if element == "с вложенным элементом" and mirrors \
            else f"{element}, {'с зеркалом' if mirrors else 'без зеркала'}"
    return data_kind


def _platform_int(value, name, whose):
    """Целое вида `int-exp` — записью платформы: `(значение, слова отчёта или "")`.

    Дано целым или экспонентой — пишется по правилу корпуса (`json0.int_exp_text`): с нулями на
    конце экспонентой, без них целым. Ширину 20, поставленную целым, пересохранение возвращает как
    `2e1`.
    """
    number = value if isinstance(value, int) and not isinstance(value, bool) \
        else json0.exp_int(str(value))
    if number is None:
        raise EditError(f"{name} у {whose}: целое, а пришло {value!r}")
    out = json0.int_exp_text(number)
    if str(out) == str(value):
        return out, ""
    return out, (f"записано так, как пишет платформа: {_short(value)} → {_short(out)} — целое с "
                 "нулями на конце она пишет экспонентой (`20` → `2e1`)")


def _platform_scale(value, name, whose):
    """Число вида `int-dec` (масштаб поля картинки) — записью платформы: `(значение, слова отчёта или "")`.

    Единица пишется целым `1`. Любое другое положительное число платформа пишет десятичной дробью одинарной точности: 3.73 →
    `3.730000019073486`. Редактор приводит значение к этой записи сам.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float, json0.Dec)):
        raise EditError(f"{name} у {whose}: число (1 — 100 %, 3.73 — 373 %), а пришло {value!r}")
    number = float(str(value)) if isinstance(value, json0.Dec) else float(value)
    if not number > 0:
        raise EditError(f"{name} у {whose}: масштаб больше нуля (1 — 100 %), а пришло {value!r}")
    single = struct.unpack("f", struct.pack("f", number))[0]
    out = 1 if single == 1.0 else json0.Dec("%.16g" % single)
    if str(out) == str(value):
        return out, ""
    return out, (f"записано так, как пишет платформа: {_short(value)} → {_short(out)} — единица целым, остальное дробью "
                 "одинарной точности")


# Ширина колонки в корпусе (`CORPUS_STAMP`): запись каждой ширины и то, как ширина ходит со своим
# зеркалом при DPI формы. Зеркало у колонок двух строений головы: с вложенным элементом — на позиции
# 45, без элемента — на 44. У форм с DPI не 96 `set_property` ширины отказывает на каждой колонке
# (`CORPUS_WIDTH_OTHER_DPI`): собранная под `unverified` колонка несла бы одно число в двух
# единицах.
CORPUS_WIDTHS = {"экспонента": 16813, "целое без нуля": 13123, "целое с нулём": 43,
                 "дробное": 5956}
CORPUS_WIDTH_MIRRORS = {"при 96 равны": 6156, "при 96 всего": 6156, "при другом равны": 0,
                        "при другом всего": 2346, "без элемента при 96": 567,
                        "без элемента при другом": 226}
CORPUS_WIDTH_OTHER_DPI = {"с зеркалом": 2346, "без зеркала": 1548, "форм без зеркала": 18,
                          "форм с зеркалом": 63, "форм с колонками": 81, "форм": 122}
# Голова колонки двух строений (числа названы в заметке `schema.COLUMN_HEAD_FORK`):
# длины голов — позиций — у колонки без вложенного элемента и с ним, и запись зеркала ширины у
# колонки без элемента.
CORPUS_COLUMN_HEADS = {"без элемента": {39: 2307, 42: 3484, 44: 112, 45: 793},
                       "с элементом": {40: 9547, 43: 10277, 45: 1706, 46: 7709}}
CORPUS_BARE_MIRRORS = {"при 96 целым": 217, "при 96 экспонентой": 149, "при 96 дробным": 201,
                       "при 120": 225, "при 144": 1}


def _mirror_dpi_check(doc, found_all, target, base, whose, unverified=False):
    """Поле вида `int-exp` у формы с DPI не 96 — отказ, либо хвост отчёта при снятом отказе.

    У ширины колонки зеркало — ширина в единицах 96 DPI, а первичное — в единицах формы: при 96 они
    равны, при 120 и 144 не равны (ширина больше ровно в 1,25 и 1,5 раза, зеркало дробное с хвостом
    округления) — у колонок обоих строений головы: зеркало на 45 у колонки с вложенным элементом и
    на 44 у колонки без него. Поставить одно число в оба адреса значило бы собрать колонку, какой
    платформа не пишет, а как она округляет зеркало, не проверялось, — поэтому отказ, и `unverified`
    его не снимает: это не граница корпуса, а известное неравенство. Зеркало ищется и среди позиций,
    чьё имя снято демоцией: у форм с DPI 120 оно дробное и лежит под запасным ключом (`u45`, у
    колонки без элемента `u44`).

    Колонка без зеркала — тоже отказ, но снимаемый `unverified`: ширина там тоже в единицах формы
    (`26.25` = 21 × 1,25 при 120), а проверка шла на форме с DPI 96 — как платформа пересчитывает
    число палитры в единицы формы, не проверялось. Снятый отказ даёт хвост отчёта (`""` — формы с
    DPI 96 или без DPI).
    """
    _primary, mirrors = _mirror_group(found_all, target, base)
    block = doc.get(FORM_BLOCK) if isinstance(doc, dict) else None
    dpi = block.get(DPI) if isinstance(block, dict) else None
    if dpi in (None, 96):
        return ""
    if mirrors:
        raise EditError(
            f"{target.slot.name} у {whose}: у формы DPI {dpi}, а зеркало ширины платформа пишет в "
            "единицах 96 DPI — при 96 оно равно ширине, при другом DPI не равно ей "
            "(больше в dpi/96 раз, дробным с хвостом округления). Как платформа округляет зеркало, не проверялось, и "
            "одно число в обоих адресах собрало бы колонку, какой она не пишет; ширину такой "
            "формы правят в конфигураторе")
    units = (f"ширина в единицах формы при DPI {dpi}; пересчёт от палитры ({dpi}/96) не проверялся — "
             "проверка шла на форме с DPI 96")
    if not unverified:
        raise EditError(
            f"{target.slot.name} у {whose}: у формы DPI {dpi}, и {units}. Зеркала у колонки нет, "
            "но число в файле — не число палитры: при DPI 120 ширина `26.25` — это 21 × 1,25 "
            "(колонки без зеркала у форм с DPI не 96 бывают). Позвать всё "
            "же можно — unverified=True: число запишется "
            "как дано, в единицах формы")
    return f"; {target.slot.name}: {units}; пометки проверки здесь нет"


VISIBLE_NAMES = ("visible", "coords/visible")

# Рамка элемента словом: блок рамки (`border`, у списка подписей — `labels_border`) принимает слово палитры или имя перечисления.
BORDER_BLOCK_NAMES = ("border", "labels_border")
BORDER_RU = {ru: en for en, ru in _chartrows.BORDER_ENGLISH.items()}
BORDER_RU.update({"Без рамки": "WithoutBorder", "Скругленная": "Rounded", "Скругленная рамка": "Rounded"})
BORDER_RU_LOWER = {ru.lower(): en for ru, en in BORDER_RU.items()}


def border_word(value, name="border"):
    """Слово рамки палитры («Одинарная», «Нет рамки», «Двойная») либо имя перечисления (`Single`) → имя перечисления `border_type`.
    Другое слово — отказ со списком обоих рядов."""
    text = value.strip()
    if text in BORDER_RU.values():
        return text
    found = BORDER_RU_LOWER.get(text.lower().replace("ё", "е"))
    if found is not None:
        return found
    pairs = ", ".join(f"«{ru}» = {en}" for en, ru in _chartrows.BORDER_ENGLISH.items())
    raise EditError(f"{name}: рамка словом — слово палитры или имя перечисления ({pairs}); пришло {value!r}. "
                    "Блок рамки целиком (объект с border_type и explicit) тоже принимается")


def set_property(doc, element=None, name=None, value=NO_VALUE, column=None, nested=False,
                 page=None, button=None, form=False, unverified=False, move_with_edge=False):
    reshape = _separate_by_page_change(doc, element, name, value, column, nested, page, button, form, unverified)
    said = _set_property(doc, element, name, value, column, nested, page, button, form, unverified, move_with_edge)
    return said + reshape() if reshape else said


set_property.__doc__ = _set_property.__doc__ + """
    **«Распределять по страницам» у родителя с несколькими страницами** (`separate_by_page`) меняет и «АктивизироватьПоУмолчанию»:
    с флагом платформа пишет по числу на страницу, без него — одно число на весь родитель. Что она оставляет при переключении, не
    проверялось: отказ, который снимает `unverified` (тогда без флага остаётся первое число, с флагом остальные страницы получают «не задан»).
    """


def _separate_by_page_change(doc, element, name, value, column, nested, page, button, form, unverified):
    """Переключение «Распределять по страницам» у родителя с несколькими страницами: отказ без `unverified`, с ним — функция, которая после
    записи флага приводит список «АктивизироватьПоУмолчанию» к форме, которой требует новый флаг, и отдаёт строку для отчёта. Прочие
    правки — `None`."""
    if not (isinstance(name, str) and name.split("/")[-1] == SEPARATE_BY_PAGE) or not isinstance(value, bool) \
            or column is not None or nested or page is not None or button is not None:
        return None
    from .base import find_element
    try:
        holder = container(doc) if form else find_element(doc, element).element if element is not None else None
        block = layout_block(holder, need=False) if holder is not None else None
    except EditError:
        return None
    if not isinstance(block, dict) or block.get(SEPARATE_BY_PAGE) is value or not isinstance(block.get(DEFAULT_CONTROL), list):
        return None
    pages = len(pages_of(holder))
    if pages < 2:
        return None
    whose = "формы" if form else f"у {element!r}"
    if not unverified:
        raise EditError(f"«Распределять по страницам» {whose} с {pages} страницами меняет и «АктивизироватьПоУмолчанию»: с флагом платформа "
                        "пишет по числу на страницу, без него — одно число на весь родитель; что она оставляет при переключении, не "
                        "проверялось. Поставьте флаг в конфигураторе или повторите с \"unverified\": true")

    def reshape():
        control = block[DEFAULT_CONTROL]
        block[DEFAULT_CONTROL] = control[:1] if not value else (control[:1] + [NO_REFERENCE] * pages)[:pages]
        return ("; «АктивизироватьПоУмолчанию» " + ("одно на родитель (оставлено первое число)" if not value
                                                   else f"по числу на страницу (страницы 2–{pages} — «не задан»)")
                + ", что пишет платформа, не проверялось")
    return reshape


NO_AUTO_MENU = _ctxmenu.NO_AUTO_MENU
# Типы, у которых в палитре нет строки «АктивизироватьПоУмолчанию» (по снимкам палитр девяти типов шаблонов).
NO_DEFAULT_CONTROL = ("Splitter", "ProgressBar", "RadioButton", "PictureBox")
# У двух из них строка есть не всегда: она появляется вместе с другой галочкой. Для такого случая запись не проверялась.
DEFAULT_CONTROL_APPEARS_WITH = {"RadioButton": "ПервыйВГруппе ☑", "PictureBox": "Гиперссылка ☑"}


def _set_default_control(doc, element, value):
    """«АктивизироватьПоУмолчанию» элемента. Свойство хранится не в элементе, а в блоке раскладки его родителя:
    список `default_control` содержит по одному числу на страницу — индекс элемента, который получает фокус при
    открытии, либо 4294967295 («не задан»). Включение записывает индекс элемента на его странице и вытесняет
    прежний элемент этой страницы (на странице он один). Выключение снимает флаг, только если на странице стоит
    этот элемент."""
    from .base import find_element
    if not isinstance(value, bool):
        raise EditError(f"АктивизироватьПоУмолчанию — флаг: значение true или false, а не {value!r}")
    place = find_element(doc, element)
    kind = place.element.get("type")
    if kind in NO_DEFAULT_CONTROL:
        appears = DEFAULT_CONTROL_APPEARS_WITH.get(kind)
        raise EditError(f"у элемента вида {kind} в палитре нет строки «АктивизироватьПоУмолчанию», и в блоке "
                        "раскладки родителя платформа для него её не пишет"
                        + (f"; строка появляется вместе с {appears}, запись для этого случая не проверялась" if appears else ""))
    block = layout_block(place.holder)
    control = block.get(DEFAULT_CONTROL)
    page = place.element["coords"].get("page", 0)
    pages = len(pages_of(place.holder))
    if one_default_control(block) and pages > 1:
        raise EditError(f"у родителя элемента {element!r} снято «Распределять по страницам», и «АктивизироватьПоУмолчанию» у него одно на "
                        f"все {pages} страницы; что платформа пишет при выборе элемента на таком родителе, не проверялось — поставьте "
                        "флаг в конфигураторе")
    page = control_slot(block, page) if isinstance(page, int) else page
    if not isinstance(control, list) or not isinstance(page, int) or not 0 <= page < len(control):
        raise EditError(f"у родителя элемента {element!r} список «АктивизироватьПоУмолчанию» не разобран "
                        "или короче числа страниц: правка не сделана")
    index = place.element["index"]
    current = control[page]
    if value:
        control[page] = index
        said = "поставлена" + (" (уже стояла)" if current == index else "")
        if current not in (index, NO_REFERENCE):
            said += f"; прежний элемент страницы (индекс {current}) вытеснен — на странице он один"
    elif current == index:
        control[page] = NO_REFERENCE
        said = "снята"
    else:
        said = "не менялась: на странице стоит другой элемент" if current != NO_REFERENCE else "не менялась: на странице не задана"
    return f"{element}: АктивизироватьПоУмолчанию {said} (список раскладки родителя, страница {page})"


def _set_visible(doc, element, value):
    """Видимость элемента — флаг в его блоке координат (строка палитры «Видимость»). Платформа при снятии
    галочки меняет только этот флаг. Размер, привязки и порядок обхода остаются прежними, поэтому скрытый
    элемент продолжает занимать место в раскладке формы."""
    from .base import find_element
    if not isinstance(value, bool):
        raise EditError(f"Видимость — флаг: значение true или false, а не {value!r}")
    place = find_element(doc, element)
    coords = place.element["coords"]
    if not isinstance(coords.get("visible"), bool):
        raise EditError(f"у элемента {element!r} в блоке координат нет флага видимости")
    before = coords["visible"]
    coords["visible"] = value
    return (f"{element}: Видимость {'☑' if value else '☐'}"
            + ("" if before != value else " (уже стояла)")
            + "; размер, привязки и порядок обхода не менялись, скрытый элемент остаётся в раскладке формы")


def _demoted_matches(lost, name):
    """Поле по имени среди позиций, чьё имя снято демоцией (`props.demoted`)."""
    parts = [part for part in str(name).split("/") if part]
    return [(found, None) for found in lost if found.slot.name == parts[-1]
            and (len(parts) == 1 or found.trail[-len(parts):-1] == tuple(parts[:-1]))]


def _put_named(holder, key, value, found):
    """Значение на место — а у позиции под запасным ключом ещё и ИМЯ карты на том же месте.

    Ключ меняется, а порядок ключей нет: он повторяет порядок позиций файла, и JSON читают
    глазами сверху вниз как сам блок."""
    slot = found[0].slot if found else None
    if slot is not None and isinstance(slot, schema.F) and slot.name != key:
        items = [(slot.name if k == key else k, value if k == key else v)
                 for k, v in holder.items()]
        holder.clear()
        holder.update(items)
        return
    holder[key] = value


# Свойства палитры, которые лежат не в элементе: строка палитры у элемента есть, а поле карты — в
# корне формы или у родителя. Назвав их у элемента, человек получает не «поля нет», а адрес и
# операцию. Ключ — имя поля карты.
NOT_IN_ELEMENT = {
    "default_control": ("АктивизироватьПоУмолчанию лежит не в элементе, а в списке раскладки "
                        "РОДИТЕЛЯ — по числу на каждую его страницу (`LayoutList/default_control`); "
                        "операции у него нет, правьте JSON родителя"),
    "menu": ("КонтекстноеМеню лежит не в элементе, а в корне формы — связями контекстного меню "
             "(`ContextMenuLinks/menu`); операции у него нет под именем menu: контекстное меню ставит "
             "set_property с именем context_menu"),
    "kind": ("АвтоКонтекстноеМеню лежит не в элементе, а в корне формы — связями контекстного "
             "меню (`ContextMenuLinks/kind`); операции у него нет"),
    BINDINGS: "Данные элемента лежат не в нём, а в таблице привязок формы — операция bind",
    "data": "Данные элемента лежат не в нём, а в таблице привязок формы — операция bind",
    "width": ("размер элемента — не свойство: его задают края right и bottom блока координат (ширина — right − x), "
              "их ставит add_element box=… или move_element; отдельной правки координат у редактора нет"),
    "height": ("размер элемента — не свойство: его задают края right и bottom блока координат (высота — bottom − y), "
               "их ставит add_element box=… или move_element; отдельной правки координат у редактора нет"),
    TEXTBOX_PATTERN: ("тип значения элемента лежит в описателе РЕКВИЗИТА формы "
                      "(`Attribute/pattern`) — его ставит add_attribute, а связь — bind"),
}


def _anchor_has(anchor, name):
    """Держит ли карта поле с таким именем в узлах этого якоря — у содержимого элемента, у
    колонки, у страницы. Нужно отказу «поля нет»: у кнопки `menu` — блок её меню (своя
    операция), а у надписи то же слово зовёт контекстное меню формы, и совет у них разный."""
    kind = anchor[len(props.NESTED_ANCHOR):] if anchor.startswith(props.NESTED_ANCHOR) else anchor
    prefixes = {props.COLUMN_ANCHOR: "Element.TableBoxColumn",
                props.PAGE_ANCHOR: "Element.PanelPage"}
    prefix = prefixes.get(anchor, f"Content.{kind}")
    return any(getattr(slot, "name", None) == name
               for type_name, node in schema.MAP.items()
               if type_name == prefix or type_name.startswith(prefix + ".")
               for _addr, slot in schema.node_slots(node))


def _property_missing(found_all, name, whose, anchor):
    """Отказ «такого поля нет» — с тем, где оно на самом деле живёт, если это известно."""
    last = str(name).split("/")[-1]
    if anchor in (props.BUTTON_ANCHOR, props.MENU_ANCHOR):
        # Блок по биту, названный путём (`shortcut/key`) или полем своего узла (`key`, `modifiers` —
        # поля сочетания), — туда же, куда сам блок: «поля нет» без адреса отправляло бы искать его
        # в узле кнопки.
        parts = [part for part in str(name).split("/") if part]
        bit = next((part for part in parts if part in BUTTON_EXTRA_OPS), None)
        if bit is None and last in SHORTCUT_PARTS:
            bit = SHORTCUT
        if bit is not None:
            return f"{name!r} у {whose}: {BUTTON_EXTRA_OPS[bit]}"
    if last in PROPERTY_OPS and PROPERTY_OPS[last][0] != "—" and _anchor_has(anchor, last):
        also = (f". Если же речь о другом свойстве с тем же словом: {NOT_IN_ELEMENT[last]}"
                if last in NOT_IN_ELEMENT and anchor not in (props.COLUMN_ANCHOR,
                                                             props.PAGE_ANCHOR) else "")
        return (f"поля {name!r} у {whose} сейчас нет, а там, где оно бывает, у него своя "
                f"операция — {PROPERTY_OPS[last][0]}: {PROPERTY_OPS[last][1]}{also}")
    if last in COORDS_NAMES:
        return (f"{name!r} — поле блока координат"
                ", а не свойства: координаты и привязки ведут "
                "операции размещения (add_element box=…), и отдельной правки координат у "
                "редактора нет — встречные записи привязок и порядок обхода по странице она "
                "обязана была бы вести сама")
    if last in NOT_IN_ELEMENT and anchor not in (props.COLUMN_ANCHOR, props.PAGE_ANCHOR):
        return f"{name!r} у {whose}: {NOT_IN_ELEMENT[last]}"
    if anchor == props.COLUMN_ANCHOR and last in TEXTBOX_NUMBER:
        return (f"{name!r} у {whose}: «Длина» колонки — квалификатор в описателе её типа "
                f"({COLUMN_VALUE_TYPE}), и правится он вместе с типом; отдельной операции у него "
                "нет. У вложенного поля ввода колонки поле digits есть, но его выводит платформа "
                "из того же типа колонки, и отдельно его не ставят")
    if last in PROPERTY_OPS and PROPERTY_OPS[last][0] != "—":
        return (f"поля {name!r} у {whose} нет; а там, где оно есть, у него своя операция — "
                f"{PROPERTY_OPS[last][0]}")
    names = sorted({found.key for found in found_all
                    if not schema.is_placeholder(found.slot) and _property_refusal(found, anchor)
                    is None})
    from .. import diagrams
    if "(Chart)" in str(whose):
        note = (". Строки палитры диаграммы лежат в теле записи и пишутся по своим именам: "
                + ", ".join(_chartrows.NAMES) + "; события — set_event. Строка «Доступность» в файл не записывается")
    elif any(f"({kind})" in str(whose) for kind in _kindrows.KINDS):
        kind = next(kind for kind in _kindrows.KINDS if f"({kind})" in str(whose))
        note = (f". Строки палитры этого вида лежат в записи и пишутся по своим именам: {', '.join(_kindrows.BY_KIND[kind])}"
                + ("" if kind == _kindrows.PIVOT else "; события — set_event") + ". У строки «Доступность» места в записи нет")
    else:
        note = ("" if not any(f"({kind})" in str(whose) for kind in diagrams.KINDS) else
                ". Свойства самой диаграммы (тип, подписи, оси, серии, события) не пишутся: их позиции в теле записи не установлены")
    return (f"поля {name!r} у {whose} нет; по имени правятся: {', '.join(names) or '—'}. Имена — "
            f"как в FORMAT.md, путь — ключи от корня через «/»{note}")
