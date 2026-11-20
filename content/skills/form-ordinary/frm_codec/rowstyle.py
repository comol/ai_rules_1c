"""Стиль рядов полей в несколько колонок: как платформа привязывает ряд к краям формы.

Ряд — это не менее двух полей ввода верхнего уровня, вертикальные интервалы которых пересекаются. Поле ряда описывается
словарём `{"box", "cl", "cr", "n", "col"}`: края `(лево, верх, право, низ)`, коэффициенты левой и правой границы
(`layout.coefficients`; `None` означает цикл правил), число полей в ряду и номер слева направо. Вид ряда (`classify_row`)
определяется записью привязок, а не поведением поля:

* `prop_pos` — каждая граница задана долей собственного положения (`cL = x1 / W`, `cR = x2 / W`); так записывает роль
  `proportional`;
* `split` — шапка колонок: левое поле привязано левой границей, правая граница задана долей `x2 / W`; следующее поле берёт
  левую границу у правой границы левого соседа, его правая граница задана долей, а у последнего поля — краем формы;
* `stand`, `move`, `stand+grow`, `stand+move`, `other`, `cycle` — остальные виды; в стиль исходной формы они не входят.

Стиль исходной формы (`style_of`) — это вид, которым записана большая часть рядов её полей. Им `generate` записывает ряды,
которые строит сам.
"""
import collections

TOLERANCE_COEF = 0.02  # допуск на долю: округление долей до пикселя при ширине формы от 400 до 900
ROW_Y = 6  # поля одного ряда: верхние края отличаются не больше чем на 6 px
ROW_STYLES = ("prop_pos", "split")  # виды рядов, которые умеет записывать движок (роли `proportional`, `column`, `self` и цепочки `after`)
STYLE_MIN_ROWS = 2  # стиль исходной формы определяется, если рядов из двух и более полей не меньше двух: по одному ряду стиль не определить


def classify_row(row, width):
    """Вид ряда из `N` ≥ 2 полей, слева направо: `stand` (все поля не сдвигаются), `move` (все сдвигаются), `prop_pos`, `split` (см.
    описание модуля), `stand+grow` (внутренние поля не сдвигаются, последнее растягивается), `stand+move` (внутренние поля не
    сдвигаются, последнее сдвигается), `other`. Вид `cycle` означает, что у какого-то поля цикл правил. Допуск на долю задаёт
    `TOLERANCE_COEF`.
    """
    if any(f["cl"] is None or f["cr"] is None for f in row):
        return "cycle"

    def near(a, b):
        return abs(a - b) <= TOLERANCE_COEF
    cl, cr = [f["cl"] for f in row], [f["cr"] for f in row]
    if all(near(a, 0) and near(b, 0) for a, b in zip(cl, cr)):
        return "stand"
    if all(near(a, 1) and near(b, 1) for a, b in zip(cl, cr)):
        return "move"
    # `split` проверяется раньше `prop_pos`: шапка колонок без надписей между полями (зазоры меньше допуска, равного 0,02 ширины)
    # подходит под оба вида, а её запись — цепочка `after`. Вид `prop_pos` для такого ряда выбирается, только если цепочка не
    # сходится.
    ok = near(cl[0], 0) and near(cr[0], row[0]["box"][2] / width)
    for i in range(1, len(row)):
        ok = ok and near(cl[i], cr[i - 1]) and (near(cr[i], 1) if i == len(row) - 1 else near(cr[i], row[i]["box"][2] / width))
    if ok:
        return "split"
    if all(near(f["cl"], f["box"][0] / width) and near(f["cr"], f["box"][2] / width) for f in row):
        return "prop_pos"
    inner = all(near(a, 0) and near(b, 0) for a, b in zip(cl[:-1], cr[:-1]))
    if inner and near(cl[-1], 0) and near(cr[-1], 1):
        return "stand+grow"
    if inner and near(cl[-1], 1) and near(cr[-1], 1):
        return "stand+move"
    return "other"


def _overlap(a, b):
    return min(a[3], b[3]) - max(a[1], b[1])


def with_columns(fields):
    """Принимает поля `[{"box", "cl", "cr", …}]` в порядке обхода и возвращает те же словари с добавленными `n` (сколько полей в их
    ряду) и `col` (номер слева направо).
    """
    out = []
    for item in fields:
        row = sorted((o for o in fields if _overlap(item["box"], o["box"]) > 0), key=lambda o: o["box"][0])
        out.append({**item, "n": len(row), "col": row.index(item)})
    return out


def rows_of(fields):
    """Ряды из двух и более полей: `[[поле, …]]` слева направо. Параметр `fields` — словари с `n` и `col` (`with_columns`) в порядке
    обхода.
    """
    used, rows = set(), []
    for i, f in enumerate(fields):
        if f["col"] != 0 or f["n"] < 2 or i in used:
            continue
        row = [f]
        for j in range(i + 1, len(fields)):
            g = fields[j]
            if len(row) < f["n"] and g["col"] == len(row) and g["n"] == f["n"] and abs(g["box"][1] - f["box"][1]) <= ROW_Y:
                row.append(g)
                used.add(j)
        if len(row) == f["n"]:
            rows.append(row)
    return rows


def style_of(fields, width, majority):
    """Стиль рядов полей исходной формы: `(вид или None, число рядов этого вида, число рядов всего)`. Вид — `prop_pos` или `split`,
    которым записана доля рядов из двух и более полей не меньше `majority`, при условии что таких рядов не меньше
    `STYLE_MIN_ROWS`. Иначе стиля нет. Параметр `fields` — словари с краями и коэффициентами (без `n` и `col`), `width` — ширина
    формы.
    """
    if not width:
        return None, 0, 0
    kinds = collections.Counter(classify_row(row, width) for row in rows_of(with_columns(fields)))
    total = sum(kinds.values())
    for kind in ROW_STYLES:
        if kinds[kind] >= STYLE_MIN_ROWS and kinds[kind] >= majority * total:
            return kind, kinds[kind], total
    return None, max((kinds[k] for k in ROW_STYLES), default=0), total
