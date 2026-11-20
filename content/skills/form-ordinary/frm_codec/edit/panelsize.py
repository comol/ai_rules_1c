"""Панель с вложенными элементами: новый размер (`move_element` с другим размером в `box`) и сдвиг рамки вместе с содержимым (`with_contents`).

**Размер панели.** Дети лежат в координатах страницы панели. Когда край панели уходит на `(dW, dH)`, каждый ребёнок ведёт себя как при росте
родителя в модели раскладки (`layout`): граница идёт за стороной своего объекта — привязанная к правому или нижнему краю панели сдвигается на весь прирост,
растянутая растёт, цепочка идёт за соседом, доля между двумя якорями берёт свою часть. Считается то же, что делает `relayout` для панели, выросшей вместе
с формой (`layout.resize._rewrite`): коэффициенты `layout.coefficients` (без пропуска скрытых страниц — на **всех** страницах панели), целые границы
`floor(v + ½)` (с правилом к центру — `floor(v)`), смещения правил под новый размер, дальние направляющие страниц (3 и 4, запись из девяти позиций) — на
прирост; вложенная панель растёт сама, и её дети считаются тем же ходом. Файловый `box` у страницы, чей край по направляющим не равен области панели,
получает тот же сдвиг (`written = stored + (now − old)`).

Расчёт идёт ДО правок и ничего не пишет: `plan` возвращает записи, `apply` их ставит; отказ оставляет форму прежней.

**Содержимое рамки.** Рамка (GroupBox) — не родитель: элементы «в рамке» её соседи. `contents` берёт соседей той же страницы, чей `box` целиком в рамке; `shift_plan`
сдвигает их на сдвиг левого верхнего угла рамки, привязки остаются теми же, смещения пересчитаны под новое место и под сдвиг сторон названных объектов
(рамки, других участников).
"""
import math

from .base import EditError, elements_of
from .names import (ANCHORS, COORDS, GUIDES, GUIDE_COORD, HEIGHT, INDEX, NAME, NAME_BLOCK, PAGE, RULES, RULE_OBJECT, RULE_OFFSET, RULE_SIDE, WIDTH, X, Y)

# Ключи блока координат в порядке записи `(x, y, x2, y2)`.
FIELDS = (X, Y, WIDTH, HEIGHT)


def _name(element):
    return (element.get(NAME_BLOCK) or {}).get(NAME) or f"#{element.get(INDEX)}"


def _round(value, item, at):
    """Целая граница по дробной (`layout.limit_calc._round_border`): позиция края в `box` → номер границы."""
    from ..layout.limit_calc import _round_border
    from ..layout.model import _EDGE
    return _round_border(value, item, _EDGE.index(at))


def children_plan(doc, node, dw, dh):
    """Записи для детей панели `node`, когда её размер вырос на `(dw, dh)`: `(записи, слова, число детей, число смещений)`; запись — `(словарь, ключ, значение)`.

    Отказ словами: цикл правил у ребёнка, отрицательный размер ребёнка, ребёнок меньше минимума своего типа при сжатии.
    """
    from ..layout import read
    from ..layout.coeffs import coefficients
    from ..layout.model import CENTER_SIDES, EPS, _EDGE
    from ..layout.resize import _follows_far_edge, _live, _side_shift
    from ..layout.model import min_size
    from ..layout.atsize import round_children
    from ..layout.report import GUIDE_AXIS, GUIDE_MARK
    form = read(doc)
    index = node.get(INDEX)
    if index not in form.holders:
        raise EditError(f"панель {_name(node)!r}: в раскладке такого родителя нет — документ с испорченными вложенными элементами")
    coef = coefficients(form, hide=False)
    growth = {index: (dw, dh)}
    old_int, new_int, order = {}, {}, []

    def walk(holder, d):
        ints = round_children(form, holder, coef, d)
        for child in holder.children:
            if coef.get(child.index) is None:
                raise EditError(f"у элемента «{child.qualified()}» правила привязок замкнуты в цикл: так панель не растянуть, цикл разберите заранее (`anchors-check`)")
            old = tuple(v if isinstance(v, int) else _round(v, child, at) for at, v in enumerate(child.box))
            now = ints[child.index]
            old_int[child.index], new_int[child.index] = old, now
            order.append((holder, child))
            if child.index in form.holders:
                grew = ((now[2] - now[0]) - (old[2] - old[0]), (now[3] - now[1]) - (old[3] - old[1]))
                growth[child.index] = grew
                walk(form.holders[child.index], grew)

    walk(form.holders[index], (dw, dh))
    for holder, child in order:
        old, now = old_int[child.index], new_int[child.index]
        old_size, now_size = (old[2] - old[0], old[3] - old[1]), (now[2] - now[0], now[3] - now[1])
        if (now_size[0] < 0 and old_size[0] >= 0) or (now_size[1] < 0 and old_size[1] >= 0):
            raise EditError(f"при новом размере панели элемент «{child.qualified()}» получил бы отрицательный размер ({now_size[0]}×{now_size[1]}, был {old_size[0]}×{old_size[1]}): "
                            "так панель не сжать — выберите размер больше либо сначала уберите привязку элемента к краю")
        least = min_size(child)
        for axis in (0, 1):
            if now_size[axis] < old_size[axis] and now_size[axis] < least[axis]:
                raise EditError(f"при новом размере панели элемент «{child.qualified()}» ({child.type}) стал бы {now_size[axis]} px "
                                f"по {'ширине' if axis == 0 else 'высоте'}, а минимум его типа — {least[axis]}: платформа меньше не сжимает. "
                                "Выберите размер панели больше")
    writes, offsets, halves = [], 0, 0
    for holder, child in order:
        old, now = old_int[child.index], new_int[child.index]
        written = now
        if child.stored is not None and tuple(child.stored) != tuple(child.box):
            written = tuple(s0 + n - o for s0, n, o in zip(child.stored, now, old))
        for rule_border, pair in enumerate(child.rules):
            shift = now[_EDGE[rule_border]] - old[_EDGE[rule_border]]
            for rule_name, rule in zip(RULES, pair):
                if rule is None:
                    continue
                side = _side_shift(form, child, rule, growth[holder.key], new_int)
                first = pair[0]
                center_first = (first is not None and first.side in CENTER_SIDES
                                and _live(form, child, rule_border, first)
                                and coef.get(child.index) is not None
                                and isinstance(child.box[_EDGE[rule_border]], int)
                                and (pair[1] is None or pair[1].off == first.off
                                     or not _live(form, child, rule_border, pair[1])))
                if center_first and (rule_name == RULES[0]
                                     or (pair[1] is not None and pair[1].off == first.off
                                         and _live(form, child, rule_border, pair[1]))):
                    value = rule.off
                else:
                    value = rule.off + shift - side
                if value != int(value):
                    halves += 1
                value = int(math.ceil(value - EPS))
                if value != rule.off:
                    writes.append((child.coords[ANCHORS[rule_border]][rule_name], RULE_OFFSET, value))
                    offsets += 1
        for key, value in zip(FIELDS, written):
            if child.coords.get(key) != value:
                writes.append((child.coords, key, value))
    guides = 0
    blocks = [(form.holders[key].block, grew) for key, grew in growth.items()]
    for block, (gw, gh) in blocks:
        found = block.get(GUIDES) if isinstance(block, dict) else None
        for guide in found if isinstance(found, list) else ():
            if not isinstance(guide, dict) or guide.get(GUIDE_MARK) != 2 \
                    or not isinstance(guide.get(GUIDE_COORD), int) or not _follows_far_edge(guide):
                continue
            step = gw if guide.get(GUIDE_AXIS) == 1 else gh
            if step:
                writes.append((guide, GUIDE_COORD, guide[GUIDE_COORD] + step))
                guides += 1
    moved = sum(1 for _h, child in order if new_int[child.index] != old_int[child.index])
    pages = sorted({child.page for holder, child in order if holder.key == index and isinstance(child.page, int)})
    nested = sum(1 for key in growth if key != index)
    words = (f"размер панели {_name(node)!r} изменился на {dw:+d}×{dh:+d}: дети на всех страницах панели ({', '.join(map(str, pages)) or '—'}) "
             f"идут по своим правилам к краям страницы по модели раскладки — сдвинуто {moved} из {len(order)} (вложенных панелей {nested}), "
             f"смещений привязок переписано {offsets}, дальних направляющих страниц перенесено {guides}"
             + (f"; смещений с дробью ½ округлено {halves}" if halves else "")
             + "; мышью за край панели в конфигураторе не сверялось (расчёт тот же, что у `relayout` для панели, выросшей вместе с формой)")
    return writes, words, len(order), offsets


def apply(writes):
    for target, key, value in writes:
        target[key] = value


# ── Рамка с содержимым ──────────────────────────────────────────────────────────────────────────

def _side(box, side):
    x, y, x2, y2 = box
    return {0: y, 1: y2, 2: x, 3: x2, 4: (y + y2) // 2, 5: (x + x2) // 2}.get(side)


def _box(element):
    c = element.get(COORDS)
    return tuple(c[k] for k in FIELDS) if isinstance(c, dict) and all(isinstance(c.get(k), int) and not isinstance(c.get(k), bool) for k in FIELDS) else None


def contents(frame_holder, frame, page):
    """Элементы родителя рамки на странице `page`, чей `box` целиком внутри рамки (не сама рамка): `[узел]`."""
    box = _box(frame)
    if box is None:
        return []
    fx, fy, fx2, fy2 = box
    found = []
    for other in elements_of(frame_holder):
        if other is frame or not isinstance(other, dict):
            continue
        coords, ob = other.get(COORDS), _box(other)
        if ob is None or coords.get(PAGE) != page:
            continue
        if ob[0] >= fx and ob[1] >= fy and ob[2] <= fx2 and ob[3] <= fy2:
            found.append(other)
    return found


def shift_plan(holder, frame, new_frame_box, members, shift):
    """Записи для сдвига `members` на `shift = (dx, dy)` вместе с рамкой: `(записи, слова)`.

    Привязки участников остаются теми же объектами и сторонами; смещение правила пересчитывается как `смещение + сдвиг своей границы − сдвиг стороны объекта`:
    край родителя и сосед, стоящий на месте, остаются на месте, участник и рамка идут на свой сдвиг (рамка — на разницу её сторон до и после). Так же пересчитываются правила
    элементов, стоящих на месте и называющих рамку или участника: их границы стоят на месте, а сторона объекта ушла. `new_frame_box` — край рамки после переноса, `(x, y, x2, y2)`.
    """
    dx, dy = shift
    old_frame = _box(frame)
    moved = {m[INDEX]: (m, _box(m)) for m in members}
    frame_index = frame[INDEX]

    def side_shift(target, side):
        if target == frame_index:
            return _side(new_frame_box, side) - _side(old_frame, side)
        entry = moved.get(target)
        if entry is None or side not in (0, 1, 2, 3, 4, 5):
            return 0
        box = entry[1]
        after = (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)
        return _side(after, side) - _side(box, side)

    writes, rules_fixed = [], 0
    for other in elements_of(holder):
        if not isinstance(other, dict) or other is frame or not isinstance(other.get(COORDS), dict):
            continue
        coords = other[COORDS]
        mine = other[INDEX] in moved
        border_shift = (dy, dy, dx, dx) if mine else (0, 0, 0, 0)
        if mine:
            box = _box(other)
            for key, value in zip(FIELDS, (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)):
                writes.append((coords, key, value))
        for border, key in enumerate(ANCHORS):
            block = coords.get(key)
            for rule_name in RULES:
                rule = block.get(rule_name) if isinstance(block, dict) else None
                if not isinstance(rule, dict):
                    continue
                target, side, offset = rule.get(RULE_OBJECT), rule.get(RULE_SIDE), rule.get(RULE_OFFSET)
                if not isinstance(target, int) or not isinstance(offset, int) or target == -1:
                    continue
                if target == 0:
                    named = 0
                elif target == other[INDEX]:
                    named = side_shift(target, side) if mine else 0
                else:
                    named = side_shift(target, side)
                value = offset + border_shift[border] - named
                if value != offset:
                    writes.append((rule, RULE_OFFSET, value))
                    rules_fixed += 1
    words = (f"вместе с рамкой {_name(frame)!r} сдвинуто {len(members)} элементов на {dx:+d}×{dy:+d} "
             f"({', '.join(_name(m) for m in members[:8])}{' …' if len(members) > 8 else ''}); привязки те же, смещений переписано {rules_fixed}")
    return writes, words
