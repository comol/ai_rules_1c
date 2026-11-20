"""Нормы компоновки по виду формы, полученные по набору образцов форм: файл `patterns.json`.

Норма показателя определяется так. Для каждой конфигурации данного вида берётся её самое частое значение показателя (если
значений поровну, то меньшее число). Каждая конфигурация даёт одно значение. Нормой становится значение, которое встречается
у большинства конфигураций, а доля — это доля таких конфигураций. Если значений поровну, выбирается то, у которого больше
форм, а затем меньшее число (сравниваются числа, а не строки). Формы, совпадающие побайтно (по sha256 `form.frm`),
считаются один раз. Для справки рядом хранится распределение по формам. Если у вида меньше трёх конфигураций (`thin`),
нормы нет, и `norm()` возвращает `None`. Хранятся только числа. Регламентированная отчётность, ошибки разбора, формы без
элементов и повторы форм в нормы не входят (`excluded`).

Блок вида: `{forms, configs, thin, <показатель>: {configs, by_config: [[значение, доля, конфигураций]…],
by_form: [[значение, доля, наблюдений, форм]…]}}`. В каждом перечне хранятся первые 8 строк.

Показатели с особым устройством. `label_text_gap` — видимый зазор от конца текста надписи до поля (`textgap`); у его строки есть ещё
`floor` — `[нижняя граница, доля наблюдений ниже неё, число наблюдений]`. `date_field_width` и `datetime_field_width` — ширина поля ввода на
дату и на дату со временем (не растягивающихся полей, только формы DPI 96); у их строки есть ещё `observations` — число полей, а нормой служит
самое частое значение по наблюдениям форм (`by_form`), а не по конфигурациям: конфигурации одной системы дают много почти одинаковых форм. Раздел `shared` хранит те же три показателя по всему корпусу: это запасная норма, когда
у вида мало данных (`date_norm`, `gap_floor`).
"""
import collections
import json
import pathlib
from . import textwidth
from .datapaths import DATA_DIR

PATTERNS_PATH = DATA_DIR / "patterns.json"
EXCLUDED = ("regulated", "error")
TOP = 8
THIN_CONFIGS = 3  # вид из меньшего числа конфигураций — `thin`: при равенстве и при доле 1,0 нормы нет
ROW_DY = 12  # элементы верхнего уровня, у которых верх различается не больше чем на 12 px, образуют одну строку
DATE_KEYS = {"Date": "date_field_width", "DateTime": "datetime_field_width"}  # ширина поля ввода на дату и на дату со временем (не растягивающегося)
DATE_MIN_OBS = 30  # у вида меньше стольких полей даты данного состава — берётся общая норма по корпусу
FLOOR_KEYS = ("label_text_gap",)  # показатели с нижней границей: «не теснее, чем у подавляющего большинства пар»
FLOOR_SHARE = 0.01  # нижняя граница — наименьшее значение, ниже которого лежит не больше этой доли наблюдений
FLOOR_MIN_PAIRS = 100  # у вида меньше стольких пар нижняя граница шумит — берётся общая по корпусу
MULTILINE_KEYS = ("multiline_field_height", "multiline_lines")  # многострочные поля ввода: высота (только у полей не меньше `MULTILINE_MIN_LINES` строк, шрифт по умолчанию) и число строк
MULTILINE_MIN_LINES = 2  # многострочное поле показывает не меньше двух строк: с одной строкой многострочный режим ничего не меняет (у корпуса так 23 % полей)
MULTILINE_BORDER = 4  # рамка поля: высота поля = строки × (высота шрифта + `textgap.LINE_EXTRA`) + рамка (у двух строк шрифта формы — 34, самая частая высота двух строк корпуса)
LINE_EXTRA = 4  # зазор строки: высота строки = высота шрифта + 4 (`textgap.LINE_EXTRA`, он же в линтере подписей)
SHARED = "shared"  # раздел таблицы: нормы по всему корпусу — ширина поля даты и зазор «текст → поле» (запасные, когда данных вида мало)
BAR_RATIO = 4  # командная панель считается горизонтальной, если её ширина не меньше четырёх высот (у верхних панелей отношение обычно не
                         # у квадратных и вертикальных панелей таблиц — от 1 до 4)


def _vkey(v):
    return (1, 0, v) if isinstance(v, str) else (0, v, "")


def _rows(top):
    """Элементы верхнего уровня, сгруппированные по строкам: элементы с близкими значениями y попадают в одну строку."""
    rows, cur, cur_y = [], [], None
    for t in sorted(top, key=lambda t: (t["box"][1], t["box"][0])):
        if cur_y is None or t["box"][1] - cur_y > ROW_DY:
            if cur:
                rows.append(cur)
            cur, cur_y = [t], t["box"][1]
        else:
            cur.append(t)
    if cur:
        rows.append(cur)
    return rows


def _skeleton(top):
    out = []
    for r in _rows(top):
        r = "+".join(sorted({x["type"] for x in r}))
        if out and out[-1] == r:
            continue
        out.append(r)
    return " / ".join(out)


def _inside(a, b):
    return a[0] >= b[0] and a[1] >= b[1] and a[2] <= b[2] and a[3] <= b[3]


def main_bars(top):
    """Командные панели верхнего уровня, которые оцениваются как верхняя или нижняя панель формы. Это горизонтальные панели (ширина
    не меньше высоты, умноженной на `BAR_RATIO`), которые не лежат целиком внутри другой командной панели формы. Панель с теми
    же краями, что у ранее найденной, считается вложенной, и остаётся первая. Вертикальная панель таблицы панелью формы не
    считается.
    """
    bars = [t for t in top if t["type"] == "CommandBar"]
    out = []
    for at, t in enumerate(bars):
        b = t["box"]
        if b[2] - b[0] < (b[3] - b[1]) * BAR_RATIO:
            continue
        if any(_inside(b, o["box"]) and (o["box"] != b or oat < at) for oat, o in enumerate(bars) if oat != at):
            continue
        out.append(t)
    return out


COLUMN_TOL = 2   # надписи с левыми краями, различающимися не больше чем на 2 px, — одна колонка пар


def _column_edges(pairs, put):
    """`field_x_columns`: по колонке пар (надписи с общим левым краем, пары из разных строк) — 1, если левые края её полей совпадают, иначе 0.
    Показатель `field_x_aligned` смотрит только левую пару каждой строки, а эта мера — каждую колонку, в том числе правую. Поле, которому подошли
    две надписи, остаётся у ближайшей (`census`: поле берёт ближайшую надпись слева, а надпись — любое поле правее)."""
    nearest = {}
    for i, lbt, ft in pairs:
        gap = ft["box"][0] - lbt["box"][2]
        if ft["name"] not in nearest or gap < nearest[ft["name"]][0]:
            nearest[ft["name"]] = (gap, i, lbt, ft)
    columns = []
    for _gap, i, lbt, ft in sorted(nearest.values(), key=lambda t: (t[2]["box"][0], t[2]["box"][1])):
        for column in columns:
            if abs(column[0][1]["box"][0] - lbt["box"][0]) <= COLUMN_TOL:
                column.append((i, lbt, ft))
                break
        else:
            columns.append([(i, lbt, ft)])
    for column in columns:
        if len({row for row, _l, _f in column}) >= 2:
            first = min(column, key=lambda p: (p[2]["box"][1], p[2]["box"][0]))[2]
            put("field_x_columns", int(len({f["box"][0] for _r, _l, f in column}) == 1), first["name"])


def _left_base(top, label):
    """Край, от которого меряется левый отступ надписи: правый край ближайшего элемента слева, который лежит на одной с ней высоте (картинка, рамка
    группы, любой элемент верхнего уровня другой строки), либо левый край рамки, в которой надпись стоит, либо край формы (0)."""
    lb = label["box"]
    base = label["frame"][0] if label.get("frame") else 0
    for t in top:
        if t is label:
            continue
        b = t["box"]
        if b[2] <= lb[0] and min(b[3], lb[3]) > max(b[1], lb[1]) and b[2] > base:
            base = b[2]
    return base


def text_lines(height, ppem):
    """Сколько строк текста помещается в поле высотой `height` при шрифте высотой `ppem` px: `(высота − рамка) // (ppem + зазор строки)`."""
    return max(0, (height - MULTILINE_BORDER) // (ppem + LINE_EXTRA))


def font_excess(item):
    """На сколько px шрифт элемента выше шрифта формы по умолчанию (`textwidth.DEFAULT_PPEM`); мельче умолчания и неизвестный размер — 0."""
    return max(0, item.get("ppem", textwidth.DEFAULT_PPEM) - textwidth.DEFAULT_PPEM)


def _measures(rec, who=None, shift=None):
    """Показатели формы: `{показатель: [значения]}`. Словарь `who` имеет вид `{показатель: [имена]}` и заполняется параллельно
    значениям: в нём записано имя элемента, давшего значение (у показателя всей формы — `None`). По нему линтер (`lint.py`)
    называет место замечания, а норму и замечание вычисляет одна и та же функция. Словарь `shift` — параллельно им, на сколько px высота показателя
    выросла от крупного шрифта (`font_excess`): линтер сдвигает диапазон на эту разницу; нормы по ней не строятся (корпус отвечает «как поставили»).

    Многострочное поле ввода (`multi_line` в записи) в `field_height` не входит и шаг строк за собой не меряет: его высота — по числу строк,
    а не по ритму пар. Свои показатели: `multiline_lines` (сколько строк текста помещается) и `multiline_field_height` (высота поля не меньше
    `MULTILINE_MIN_LINES` строк при шрифте по умолчанию).

    Роли: «левый отступ надписи» берётся только у надписи, левее которой в строке нет другого элемента верхнего уровня, и меряется от ближайшего элемента
    слева на её высоте (картинка, рамка группы; `_left_base`), а без такого — от края формы; «правый отступ поля» у элемента внутри рамки группы
    меряется от рамки (`frame` записи переписи), а не от края формы;
    «верхняя/нижняя панель» — только `main_bars`.
    """
    by = {t["name"]: t for t in rec["top"]}
    rows = _rows(rec["top"])
    row_of = {id(t): i for i, r in enumerate(rows) for t in r}
    left_edge = {i: min(t["box"][0] for t in r) for i, r in enumerate(rows)}
    right_field = {i: max((t["box"][2] for t in r if t["type"] == "TextBox"), default=None)
                   for i, r in enumerate(rows)}
    m = collections.defaultdict(list)
    names = {} if who is None else who

    def put(key, value, name=None, excess=0):
        m[key].append(value)
        names.setdefault(key, []).append(name)
        if shift is not None:
            shift.setdefault(key, []).append(excess)
    pairs = []  # (строка поля, надпись, поле)
    for lname, fname in rec["pairs"]:
        lbt, ft = by[lname], by[fname]
        lb, f = lbt["box"], ft["box"]
        i = row_of[id(ft)]
        pairs.append((i, lbt, ft))
        if lb[0] == left_edge[row_of[id(lbt)]]:  # только надпись, левее которой в строке нет других элементов
            put("label_left", lb[0] - _left_base(rec["top"], lbt), lname)  # от ближайшего слева (картинка, рамка группы), иначе от края формы
        if f[2] == right_field[i]:  # только самое правое поле строки
            put("field_right_margin", (ft["frame"][2] if ft.get("frame") else rec["w"]) - f[2], fname)
        put("label_field_gap", f[0] - lb[2], fname)
        if lbt.get("text_end") is not None:  # видимый зазор — от конца текста надписи, а не от её рамки (`textgap`)
            put("label_text_gap", f[0] - lbt["text_end"], fname)
        put("label_height", lb[3] - lb[1], lname, font_excess(lbt))
        if not ft.get("multi_line"):
            put("field_height", f[3] - f[1], fname, font_excess(ft))
        put("field_right_to_form", int(ft["right_to_form"]), fname)
    pair_rows = {}
    for i, lbt, ft in pairs:
        pair_rows.setdefault(i, []).append((lbt, ft))
    ys = {i: min(ft["box"][1] for _, ft in ps) for i, ps in pair_rows.items()}
    for i in sorted(ys):  # шаг считается только между соседними строками формы; строка с многострочным полем шага не даёт: её высота — по строкам текста
        if i + 1 in ys and not any(ft.get("multi_line") for _, ft in pair_rows[i]):
            put("pair_pitch", ys[i + 1] - ys[i], min(pair_rows[i + 1], key=lambda p: p[1]["box"][1])[1]["name"],
                max(max(font_excess(lbt), font_excess(ft)) for lbt, ft in pair_rows[i]))
    _column_edges(pairs, put)
    leaders = [min(ps, key=lambda p: (p[0]["box"][0], p[1]["box"][0]))
               for _, ps in sorted(pair_rows.items())]  # левая пара каждой строки
    if len(leaders) >= 2:
        put("field_x_aligned", int(len({ft["box"][0] for _, ft in leaders}) == 1))
    if leaders:
        lbt, ft = min(leaders, key=lambda p: (p[0]["box"][0], p[0]["box"][1]))
        put("label_column_width", ft["box"][0] - lbt["box"][0], lbt["name"])
    for composition, width, dname, *rest in rec.get("dates") or ():  # поля на дату — отдельно по составу; «только время» своего показателя не имеет
        key = DATE_KEYS.get(composition)
        if key is not None and not (rest and rest[0]):  # растягивающиеся поля в норму ширины не идут
            put(key, width, dname)
    for t in rec["top"]:                          # многострочные поля — все видимые поля формы, не только стоящие в паре с надписью слева
        if t["type"] == "TextBox" and t.get("multi_line"):
            ppem = t.get("ppem", textwidth.DEFAULT_PPEM)
            lines = text_lines(t["box"][3] - t["box"][1], ppem)
            put("multiline_lines", lines, t["name"])
            if lines >= MULTILINE_MIN_LINES and ppem == textwidth.DEFAULT_PPEM:
                put("multiline_field_height", t["box"][3] - t["box"][1], t["name"])
    main = {id(t) for t in main_bars(rec["top"])}
    for t in rec["top"]:
        b = t["box"]
        if t["type"] == "CommandBar" and id(t) in main and b[1] < 12:
            put("top_bar_height", b[3] - b[1], t["name"])
            put("top_bar_x", b[0], t["name"])
            put("top_bar_y", b[1], t["name"])
            put("top_bar_full_width", int(b[0] <= 0 and b[2] >= rec["w"]), t["name"])
        if t["type"] == "CommandBar" and id(t) in main and b[3] >= rec["h"] - 2:
            put("bottom_bar_height", b[3] - b[1], t["name"])
            put("bottom_bar_x", b[0], t["name"])
            put("bottom_bar_y", b[1], t["name"])
            put("bottom_bar_full_width", int(b[0] <= 0 and b[2] >= rec["w"]), t["name"])
            put("bottom_bar_to_form", int(t["bottom_to_form"]), t["name"])
        if t["type"] == "TableBox":
            put("table_right_bottom_to_form", int(t["right_to_form"] and t["bottom_to_form"]), t["name"])
    put("skeleton", _skeleton(rec["top"]))
    return m


def _norm_rows(votes_by_config, observations, form_counts):
    """Строки перечней одного показателя: значения по конфигурациям и по формам (оба перечня упорядочены по убыванию; при
    равенстве сравниваются числа).
    """
    configs = len(votes_by_config)
    votes = collections.Counter(votes_by_config.values())
    by_config = sorted(votes.items(), key=lambda kv: (-kv[1], -form_counts[kv[0]], _vkey(kv[0])))[:TOP]
    total = sum(observations.values())
    by_form = sorted(observations.items(), key=lambda kv: (-kv[1], _vkey(kv[0])))[:TOP]
    return {"configs": configs,
            "by_config": [[v, round(n / configs, 4), n] for v, n in by_config],
            "by_form": [[v, round(n / total, 4), n, form_counts[v]] for v, n in by_form]}


def _floor(observations):
    """Нижняя граница показателя: `[значение, доля наблюдений ниже него, наблюдений]`. Значение — наименьшее, ниже которого лежит не больше
    `FLOOR_SHARE` наблюдений. Наблюдения с отрицательным зазором (текст надписи заходит под поле) не считаются: это наезд, его называет свое
    правило, а длинный хвост наездов тянул бы границу вниз. Формы-повторы уже отброшены.
    """
    kept = {value: n for value, n in observations.items() if value >= 0}
    total = sum(kept.values())
    if not total:
        return [0, 0.0, 0]
    below = 0
    for value in sorted(kept):
        if (below + kept[value]) / total > FLOOR_SHARE:
            return [value, round(below / total, 4), total]
        below += kept[value]
    return [max(kept), round(below / total, 4), total]


STAMP = "снимок корпуса форм"


def aggregate(records, stamp):
    excluded = collections.Counter()
    seen = set()
    forms = collections.Counter()
    per_config = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(
        collections.Counter)))  # вид → показатель → конфигурация → значения
    observed = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    form_counts = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    configs = collections.defaultdict(set)
    for rec in sorted(records, key=lambda r: r["path"]):  # побайтный повтор: остаётся первая форма по пути
        kind = rec["kind"]
        if kind in EXCLUDED:
            excluded[kind] += 1
            continue
        if not rec["top"]:
            excluded["empty"] += 1
            continue
        sha = rec.get("sha")
        if sha is not None and sha in seen:
            excluded["duplicate"] += 1
            continue
        seen.add(sha)
        forms[kind] += 1
        config = rec.get("config", "?")
        configs[kind].add(config)
        for key, values in _measures(rec).items():
            per_config[kind][key][config].update(values)
            observed[kind][key].update(values)
            form_counts[kind][key].update(set(values))
            if key in DATE_KEYS.values() or key in FLOOR_KEYS or key in MULTILINE_KEYS:  # ширина поля даты, зазор «текст → поле» и многострочные поля — ещё и общие по корпусу
                per_config[SHARED][key][config].update(values)
                observed[SHARED][key].update(values)
                form_counts[SHARED][key].update(set(values))
    shared = per_config.pop(SHARED, {})
    shared_rows = {key: _norm_rows({c: min(cnt.items(), key=lambda kv: (-kv[1], _vkey(kv[0])))[0] for c, cnt in shared[key].items()},
                              observed[SHARED][key], form_counts[SHARED][key])
              for key in sorted(shared)}
    for key in DATE_KEYS.values():
        if key in shared_rows:
            shared_rows[key]["observations"] = sum(observed[SHARED][key].values())
    for key in FLOOR_KEYS:
        if key in shared_rows:
            shared_rows[key]["floor"] = _floor(observed[SHARED][key])
    if "multiline_lines" in shared_rows:
        lines = observed[SHARED]["multiline_lines"]
        total = sum(lines.values())
        below = sum(n for value, n in lines.items() if value < MULTILINE_MIN_LINES)
        shared_rows["multiline_lines"]["observations"] = total
        shared_rows["multiline_lines"]["below_min"] = [MULTILINE_MIN_LINES, round(below / total, 4), below, total]
    kinds = {}
    for kind in sorted(per_config):
        block = {"forms": forms[kind], "configs": len(configs[kind]),
                 "thin": len(configs[kind]) < THIN_CONFIGS}
        for key in sorted(per_config[kind]):
            votes = {c: min(cnt.items(), key=lambda kv: (-kv[1], _vkey(kv[0])))[0]
                     for c, cnt in per_config[kind][key].items()}
            block[key] = _norm_rows(votes, observed[kind][key], form_counts[kind][key])
            if key in DATE_KEYS.values():
                block[key]["observations"] = sum(observed[kind][key].values())
            if key in FLOOR_KEYS:
                block[key]["floor"] = _floor(observed[kind][key])
        kinds[kind] = block
    return {"stamp": stamp, "excluded": dict(sorted(excluded.items())), "kinds": kinds, SHARED: shared_rows}


def write(table, path=PATTERNS_PATH):
    pathlib.Path(path).write_text(json.dumps(table, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                                  encoding="utf-8")


def load(path=PATTERNS_PATH):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def norm(table, kind, key):
    """Норма показателя вида — это значение, которое встречается у большинства конфигураций. Для вида `thin` возвращается `None`."""
    block = table["kinds"].get(kind)
    if not block or block.get("thin"):
        return None
    rows = (block.get(key) or {}).get("by_config")
    return rows[0][0] if rows else None


def _row_of(table, kind, key, least_pairs=0):
    """Строка показателя `key`: `(строка, пояснение)`. Строка вида берётся, если у вида не меньше `THIN_CONFIGS`
    конфигураций (и, если задано `least_pairs`, у строки не меньше стольких наблюдений); иначе — общая строка по корпусу (раздел
    `shared`). Пояснение — пусто у строки вида и словами о причине у общей; строки нет совсем — `(None, слова)`.
    """
    row = ((table.get("kinds") or {}).get(kind) or {}).get(key)
    if row and row["configs"] >= THIN_CONFIGS and (not least_pairs or row.get("floor", [0, 0, 0])[2] >= least_pairs):
        return row, ""
    shared = (table.get(SHARED) or {}).get(key)
    if not shared or not shared["by_config"]:
        return None, f"нормы {key} нет ни у вида «{kind}», ни общей по корпусу"
    if not kind:
        return shared, "вид формы не определён"
    return shared, (f"у вида «{kind}» конфигураций меньше {THIN_CONFIGS}" if not row or row["configs"] < THIN_CONFIGS
                    else f"у вида «{kind}» меньше {least_pairs} наблюдений")


def _pct1(share):
    """Доля в процентах с одним знаком и запятой: `64,7 %`."""
    return f"{share * 100:.1f}".replace(".", ",") + " %"


def date_norm(table, kind, key):
    """Ширина поля даты (`key` из `DATE_KEYS`): `(значение, слова о том, откуда оно)` либо `(None, слова)`. Это самая частая ширина по наблюдениям форм
    (повторы форм отброшены; растягивающиеся поля не считаются): вида — если у него не меньше `DATE_MIN_OBS` полей этого состава, иначе
    общая по корпусу. Самое частое значение по конфигурациям здесь не используется: конфигурации одной системы дают много почти одинаковых форм.
    """
    row = ((table.get("kinds") or {}).get(kind) or {}).get(key)
    if row and row.get("observations", 0) >= DATE_MIN_OBS:
        source = f"самая частая ширина в формах вида «{kind}»"
    else:
        row = (table.get(SHARED) or {}).get(key)
        if not row or not row["by_form"]:
            return None, f"нормы {key} нет ни у вида «{kind}», ни общей по корпусу"
        source = "самая частая ширина во всех формах корпуса (" + (f"у вида «{kind}» полей этого состава меньше {DATE_MIN_OBS}" if kind else "вид формы не определён") + ")"
    value, share, observations, _forms = row["by_form"][0]
    return value, f"{source} {key}: {value} px — {_pct1(share)} из {row['observations']} полей"


def gap_row(table, kind):
    """Строка `label_text_gap`, по которой берётся нижняя граница: `(строка, пояснение)` (`_row_of`; у строки вида не меньше `FLOOR_MIN_PAIRS` пар)."""
    return _row_of(table, kind, "label_text_gap", FLOOR_MIN_PAIRS)


def gap_norm(table, kind):
    """Норма видимого зазора «текст надписи → поле» (`label_text_gap`) — значение большинства конфигураций, того же ряда, что и нижняя граница: `int | None`."""
    row, _why = gap_row(table, kind)
    return None if row is None else row["by_config"][0][0]


def gap_floor(table, kind):
    """Нижняя граница видимого зазора «текст надписи → поле» (`label_text_gap`): `(значение, слова)` либо `(None, слова)`."""
    row, why = gap_row(table, kind)
    if row is None:
        return None, why
    value, share, total = row["floor"]
    source = f"общая нижняя граница по корпусу ({why})" if why else f"нижняя граница нормы вида «{kind}»"
    return value, (f"{source} label_text_gap: {value} px — ниже неё лежит {_pct1(share)} из {total} пар "
                   f"(норма по конфигурациям — {row['by_config'][0][0]})")


def first_difference(have, want):
    """Первое различие двух таблиц словами с указанием вида и показателя (`kinds/catalog.item/field_height: было … → стало …`)."""
    for top in sorted(set(have) | set(want)):
        a, b = have.get(top), want.get(top)
        if a == b:
            continue
        if top != "kinds" or not isinstance(a, dict) or not isinstance(b, dict):
            return f"раздел «{top}»: было {a!r} → стало {b!r}"
        for kind in sorted(set(a) | set(b)):
            ka, kb = a.get(kind), b.get(kind)
            if ka == kb:
                continue
            if not isinstance(ka, dict) or not isinstance(kb, dict):
                return f"вид «{kind}»: {'нет в файле' if ka is None else 'нет в пересборке'}"
            for key in sorted(set(ka) | set(kb)):
                if ka.get(key) != kb.get(key):
                    return f"kinds/{kind}/{key}: было {_short(ka.get(key))} → стало {_short(kb.get(key))}"
    return "различий нет"


def _short(v, limit=160):
    text = json.dumps(v, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + "…"
