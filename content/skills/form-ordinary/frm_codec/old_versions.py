"""Шаблон элемента для формы старой версии общего блока оформления (10, 13, 15): сведение шаблона версии 16 к версии формы.

Шаблоны записаны в версии 16, а платформа 8.3.27 элементов версий 10, 13 и 15 сама не пишет: при пересохранении она поднимает всю форму до 16. Поэтому
источник сведения — корпус форм. По каждому виду и версии строки правила называют позиции узла, где значение у почти всех элементов версии одно и
отличается от шаблона: версия общего блока, длина его хвоста, запись шрифта, версии вложенных записей. Строки лежат в `old_versions.json`: путь по
позициям узла, новое значение или «убрать». Личное элемента (имя, место, обработчики, подсказки, заголовки, цвет рамки) в правило не входит, а
оформление ставят по соседям формы, как у шаблона версии 16.

Правило применяется к виду и версии, только если корпус его подтверждает: в таблице записано, сколько элементов этого вида в формах этой версии равны
сведённому шаблону с точностью до личного, а также до оформления, которое ставят по соседям, и данных вида (кнопок панели, колонок, привязок панели).
Нет ни одного такого элемента или в узле остаётся вложенный элемент версии 16 — отказ словами с числом элементов вида в формах этой версии.
Таблица порождена переписью корпуса форм и руками не правится.

**Табличное поле** сводится не по виду, а по варианту — паре «версия общего блока формы, версия записи самого поля» (раздел `tables`). Запись поля у формы версии 10 пишется
в пяти версиях (10, 11, 12, 14, 15), у 13 и 15 в основном снимке — в одной (17 и 18; у формы 13 встречается и 16), и она одна на форму (снимок: 1 051 форма из 1 051); это поколение платформы, писавшей форму, а не вид данных. У формы,
где табличное поле уже есть, вариант берётся с него; у формы без поля — по записи кнопок командных панелей формы (`mark` 7 → запись 12, 8 → запись 15; доля в корпусе названа в
отчёте); нет ни того ни другого — отказ. Поле сводится вместе с колонкой шаблона и вложенным полем колонки, колонка из образца (табличной части, списка, таблицы значений) — по
строкам образца того же строения, вложенное поле — по строкам колонки, в которой оно лежит. Подтверждение — число полей и колонок корпуса варианта, равных сведённому образцу с
точностью до личного и данных колонки.
"""
import contextlib
import copy
import json
import pathlib
import re
from .datapaths import DATA_DIR

VERSIONS = (10, 13, 15)
# Виды, которых в корпусе форм нет ни одного: сводить шаблон к версии формы не по чему, и `add_element` для формы версии 10, 13 или 15 отказывает
# словами (отказ снимает `unverified`: узел версии 16 встаёт в форму как есть).
UNSEEN_KINDS = ("PDFDocumentField", "GeographicalSchemaField", "GraphicalSchemaField")
TABLE_FILE = DATA_DIR / "old_versions.json"
MISSING = "<нет>"  # у строки правила: позиции у элемента версии V нет
STEP = re.compile(r"([^.\[\]]+)|\[(\d+)\]")

_TABLE = None
_OFF = []  # пока список не пуст, шаблон версии 16 в форму старой версии не сводится: `off`


@contextlib.contextmanager
def off():
    """Шаблоны не сводятся к версии формы: `add_element` ведёт себя, как до правила сведения — отказывает по версии. Нужен бережному режиму `generate`, который для
    формы старой версии ставит поле копией соседа (`like`), а не сведённым шаблоном."""
    _OFF.append(True)
    try:
        yield
    finally:
        _OFF.pop()


def enabled():
    return not _OFF


def table():
    """Порождённая таблица правил: `{"kinds": {вид: {версия: {...}}}, "corpus": {...}}`."""
    global _TABLE
    if _TABLE is None:
        _TABLE = json.loads(TABLE_FILE.read_text(encoding="utf-8"))
    return _TABLE


def steps(path):
    """Путь строки правила — список шагов: ключ (строка) либо номер в списке (число)."""
    return [m.group(1) if m.group(1) is not None else int(m.group(2)) for m in STEP.finditer(path)]


def _parent(node, path, create=False):
    """Контейнер, в котором лежит последний шаг пути, и этот шаг; `None`, если какой-то шаг по дороге отсутствует."""
    parts = steps(path)
    here = node
    for part in parts[:-1]:
        if isinstance(part, int):
            ok = isinstance(here, list) and part < len(here)
        else:
            ok = isinstance(here, dict) and part in here
        if not ok:
            return None
        here = here[part]
    return here, parts[-1]


def _sort_key(path):
    return [(0, p, "") if isinstance(p, int) else (1, 0, p) for p in steps(path)]


def apply_rows(node, rows):
    """Применяет строки правила к узлу (на месте): сначала значения (по возрастанию путей), потом «убрать» (по убыванию, чтобы номера в списках не
    сдвигались). Позиция, которой в шаблоне нет и к которой дороги нет, — `ValueError`: таблица разошлась с шаблоном."""
    sets = sorted((r for r in rows if r["value"] != MISSING), key=lambda r: _sort_key(r["path"]))
    drops = sorted((r for r in rows if r["value"] == MISSING), key=lambda r: _sort_key(r["path"]), reverse=True)
    for row in sets:
        found = _parent(node, row["path"])
        if found is None:
            raise ValueError(f"позиции {row['path']} нет в шаблоне, и дороги к ней нет")
        container, last = found
        value = copy.deepcopy(row["value"])
        if isinstance(last, int):
            if not isinstance(container, list) or last > len(container):
                raise ValueError(f"позиции {row['path']} нет в шаблоне, и дороги к ней нет")
            if last == len(container):
                container.append(value)
            else:
                container[last] = value
        else:
            if not isinstance(container, dict):
                raise ValueError(f"позиции {row['path']} нет в шаблоне, и дороги к ней нет")
            container[last] = value
    for row in drops:
        found = _parent(node, row["path"])
        if found is None:
            continue  # родитель уже заменён или убран строкой выше по пути
        container, last = found
        if isinstance(last, int):
            if not (isinstance(container, list) and last < len(container)):
                continue
            del container[last]
        elif isinstance(container, dict) and last in container:
            del container[last]
        else:
            continue
        # Список или словарь, который опустел от этого «убрать», у элемента версии V отсутствует целиком: платформа не пишет пустых хвостов. Номера выше
        # убранного уже обработаны (строки идут по убыванию), поэтому сдвиг номеров ниже ничего не портит.
        parts = steps(row["path"])[:-1]
        while parts and not container:
            above = _parent(node, "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in parts).lstrip("."))
            if above is None:
                break
            holder, key = above
            if isinstance(key, int):
                del holder[key]
            else:
                del holder[key]
            container = holder
            parts = parts[:-1]
    return node


def entry(kind, version):
    """Запись таблицы по виду и версии либо `None`: корпус элементов этого вида в формах этой версии не содержит."""
    return table()["kinds"].get(kind, {}).get(str(version))


def unseen_refusal(kind, version):
    """Фраза отказа для вида из `UNSEEN_KINDS` в форме старой версии: корпус не содержит ни одного элемента вида."""
    return (f"вид {kind} для формы версии {version} не сводится: в корпусе форм нет ни одного такого элемента, и правила сведения шаблона "
            "версии 16 к этой версии взять неоткуда")


def refusal(kind, version, template):
    """Фраза отказа либо `None`, если шаблон для версии сводится."""
    meta = table()
    names = meta["templates"].get(kind) or []
    seen = entry(kind, version)
    count = (seen or {}).get("elements", 0)
    where = f"в формах версии {version} корпуса {count} элементов вида {kind}"
    if template not in names:
        return (f"шаблон {template!r} для формы версии {version} не сводится: правило выведено из шаблона "
                f"{', '.join(names) or '—'} ({where}); дорога — like либо узел из формы той же версии")
    if seen is not None and seen.get("nested_left"):
        return (f"шаблон {template!r} для формы версии {version} не сводится: колонки шаблона несут вложенные элементы с общим блоком версии 16 "
                f"({', '.join(seen['nested_left'])}), правило для вложенных тел не выведено, и узел остался бы смешанным ({where}). "
                "Дорога — like либо узел из формы той же версии")
    if seen is None or not seen.get("confirmed"):
        return (f"шаблон {template!r} для формы версии {version} не сводится: корпус не подтверждает ни одного элемента вида {kind}, равного "
                f"шаблону, сведённому к версии {version} ({where}). Дорога — like либо узел из формы той же версии")
    return None


def reduce_template(node, kind, version):
    """Узел шаблона версии 16, сведённый к `version` (копия), и фраза отчёта."""
    seen = entry(kind, version)
    out = apply_rows(copy.deepcopy(node), seen["rows"])
    words = (f"шаблон версии 16 сведён к версии формы {version} по правилу корпуса: {len(seen['rows'])} позиций, строки держат от "
             f"{seen['min_share']:.1%} элементов вида {kind} версии {version}; подтверждено {seen['confirmed']} из {seen['elements']} "
             "элементов корпуса (равны сведённому шаблону с точностью до имени, места, обработчиков, подсказок, заголовков и цвета рамки); "
             "оформление — по соседям формы, как у шаблона 16")
    return out, words


# ── Табличное поле: варианты, колонки, вложенные поля ─────────────────────────────────────────────

NESTED = "u1.u1.u1.control.element.content"  # вложенное поле колонки — путь от колонки
# Записи табличного поля, которых нет в основном снимке корпуса, но которые встречаются в дополнительном (у формы версии 13 — 16, на одну позицию короче): у формы без поля
# отличить их нечем (запись кнопок командных панелей та же), и отчёт называет это допущение.
ALSO_SEEN = {13: 16}
GENERATION_MARKS = "командных панелей формы: запись кнопок `mark`"


def tables():
    """Раздел `tables` таблицы: `{"variants": {"версия.запись": {...}}, "generation": {...}}`."""
    return table().get("tables") or {"variants": {}, "generation": {}}


def table_record(node):
    """Версия записи самого табличного поля (`content.u2.u1.u0`) либо `None`."""
    try:
        value = node["content"]["u2"]["u1"]["u0"]
    except (KeyError, TypeError):
        return None
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def variant(version, record):
    """Запись раздела `tables` по версии формы и версии записи поля либо `None`: корпус таких полей не содержит."""
    return tables()["variants"].get(f"{version}.{record}")


def form_generation(doc, version):
    """`(запись, слова)` — версия записи табличного поля, как её пишет платформа этого поколения, для формы `doc` версии `version`; запись `None` — определить нечем (слова называют причину).

    Порядок: запись поля, которое уже есть в форме (у всех полей формы она одна); у формы версий 13 и 15 запись одна (единственная в корпусе); у формы версии 10 без поля — запись
    кнопок командных панелей формы.
    """
    from . import design as _design
    from . import edit as _edit
    records = {table_record(el) for _name, el in _design.elements(doc) if el.get("type") == "TableBox"}
    if len(records) > 1:
        return None, f"в форме табличные поля с разными записями ({', '.join(str(r) for r in sorted(records, key=str))}): поколение платформы, писавшей форму, неоднозначно"
    if records:
        record = next(iter(records))
        if variant(version, record) is None:
            return None, f"запись табличного поля формы — {record}, а корпус форм версии {version} таких полей не содержит"
        return record, f"запись табличного поля формы — {record} (у всех полей формы запись одна: так в корпусе у всех форм)"
    known = sorted(v["record"] for v in tables()["variants"].values() if v["version"] == version)
    if len(known) == 1:
        also = ALSO_SEEN.get(version)
        return known[0], (f"в форме нет табличного поля; запись поля у форм версии {version} в корпусе одна — {known[0]}"
                          + (f", но встречается и запись {also}: у формы без поля признака поколения нет, и берётся {known[0]}" if also else ""))
    marks = set()
    for _name, block in _edit._bars(doc):
        for one in block.get("button_sets") or []:
            for button in (one.get("buttons") or []) if isinstance(one, dict) else []:
                if isinstance(button, dict) and isinstance(button.get("mark"), int):
                    marks.add(button["mark"])
    seen = (tables()["generation"].get(str(version)) or {})
    if len(marks) == 1 and str(next(iter(marks))) in seen:
        mark = next(iter(marks))
        guess = seen[str(mark)]
        return guess["record"], (f"в форме нет табличного поля; поколение платформы — по записи кнопок {GENERATION_MARKS} {mark}: у форм версии {version} с таким признаком "
                                 f"запись поля {guess['record']} у {guess['share']:.1%} из {guess['of']}")
    why = "в форме нет ни табличного поля, ни командной панели с кнопками, по которым узнаётся поколение платформы" if not marks else \
        f"признак поколения (запись кнопок командных панелей {sorted(marks)}) в корпусе не встречается"
    return None, f"запись табличного поля у форм версии {version} пишется в нескольких версиях (по поколению платформы), и {why}"


def _table_refusal(version, record, template, words):
    seen = variant(version, record)
    where = f"в формах версии {version} корпуса {seen['tables']} табличных полей с записью {record}"
    kinds = tables()["variants"]
    if template not in seen["top"]["confirmed"]:
        return f"шаблон {template!r} для формы версии {version} не сводится: правило выведено из шаблонов {', '.join(seen['top']['confirmed'])} ({where})"
    if not seen["top"]["confirmed"][template]:
        return (f"шаблон {template!r} для формы версии {version} (запись поля {record}) не сводится: корпус не подтверждает ни одного табличного поля с записью {record}, равного "
                f"шаблону, сведённому к этому варианту ({where}). Дорога — like либо узел из формы той же версии")
    if template == "TableBox":
        first = seen["templates"].get("TableBox")
        if first is None or not first["confirmed"]:
            return (f"шаблон 'TableBox' для формы версии {version} (запись поля {record}) не сводится: колонка шаблона не подтверждена корпусом ни у одной колонки варианта "
                    f"({where}). Дорога — like либо узел из формы той же версии")
    return None


def table_refusal(doc, version, template):
    """Фраза отказа для табличного поля `template` в форме `doc` версии `version` либо `None`."""
    if template not in ("TableBox", "TableBox-tabular"):
        names = ", ".join(("TableBox", "TableBox-tabular"))
        return f"шаблон {template!r} для формы версии {version} не сводится: правило выведено из шаблонов {names}"
    record, words = form_generation(doc, version)
    if record is None:
        return f"шаблон {template!r} для формы версии {version} не сводится: {words}. Дорога — like либо узел из формы той же версии"
    return _table_refusal(version, record, template, words)


def reduce_table(doc, node, template, version):
    """Узел табличного поля версии 16 (копия), сведённый к варианту формы, и фраза отчёта."""
    record, how = form_generation(doc, version)
    seen = variant(version, record)
    out = apply_rows(copy.deepcopy(node), seen["top"]["rows"])
    parts = [f"шаблон версии 16 сведён к версии формы {version}, запись табличного поля {record} ({how}): строк поля {len(seen['top']['rows'])}, "
             f"слабейшая держит {seen['top']['min_share']:.1%} полей варианта; подтверждено {seen['top']['confirmed'][template]} из {seen['tables']} полей корпуса"]
    if template == "TableBox":
        from . import edit as _edit
        holder = _edit.columns_of(out)
        first = seen["templates"]["TableBox"]
        rows = seen["columns"][first["group"]]["rows"]
        for column in holder[_edit.COLUMN_ITEMS]:
            apply_rows(column, rows)
        parts.append(f"колонка шаблона — строк {len(rows)}, подтверждено {first['confirmed']} колонок корпуса варианта")
    return out, "; ".join(parts)


def column_refusal(version, record, template):
    """Фраза отказа для колонки-образца `template` (табличной части, списка, таблицы значений) в таблице версии `version` с записью `record` либо `None`."""
    seen = variant(version, record)
    if seen is None:
        return f"корпус форм версии {version} не содержит табличных полей с записью {record}"
    found = seen["templates"].get(template)
    if found is None:
        return (f"образец колонки {template!r} для формы версии {version} (запись поля {record}) не сводится: в корпусе нет колонок такого строения в таких полях "
                f"({seen['tables']} полей)")
    if not found["confirmed"]:
        group = seen["columns"][found["group"]]
        return (f"образец колонки {template!r} для формы версии {version} (запись поля {record}) не сводится: корпус не подтверждает ни одной колонки, равной образцу, сведённому к "
                f"этому варианту (колонок строения образца в корпусе {group['of']})")
    return None


def reduce_column(column, template, version, record):
    """Колонка-образец (копия), сведённая к варианту, и фраза отчёта. Образец берут свежим: строки применяются по положению позиций."""
    seen = variant(version, record)
    found = seen["templates"][template]
    rows = seen["columns"][found["group"]]["rows"]
    out = apply_rows(copy.deepcopy(column), rows)
    return out, (f"образец колонки {template!r} сведён к версии формы {version}, запись поля {record}: строк {len(rows)}, подтверждено {found['confirmed']} из "
                 f"{seen['columns'][found['group']]['of']} колонок строения образца")


def nested_rows(rows):
    """Строки колонки, относящиеся к вложенному полю, — пути от его содержимого."""
    cut = len(NESTED) + 1
    return [dict(r, path=r["path"][cut:]) for r in rows if r["path"].startswith(NESTED + ".")]


def control_refusal(version, record, key):
    """Фраза отказа для содержимого вложенного поля колонки `key` (`TextBox-S`, `TextBox-N`, `CheckBox`) либо `None`."""
    seen = variant(version, record)
    if seen is None:
        return f"корпус форм версии {version} не содержит табличных полей с записью {record}"
    found = seen["controls"].get(key)
    if found is None or not found["confirmed"]:
        return (f"тело вложенного поля {key!r} для формы версии {version} (запись поля {record}) не сводится: корпус не подтверждает ни одного вложенного поля, равного телу, "
                "сведённому к этому варианту. Дорога — template: содержимое вложенного поля того же вида из колонки формы той же версии")
    return None


def reduce_control(body, key, version, record):
    """Содержимое вложенного поля (копия), сведённое к варианту, и фраза отчёта."""
    seen = variant(version, record)
    found = seen["controls"][key]
    rows = nested_rows(seen["columns"][found["source"]]["rows"])
    out = apply_rows(copy.deepcopy(body), rows)
    return out, (f"тело вложенного поля {key!r} сведено к версии формы {version}, запись поля {record}: строк {len(rows)}, подтверждено {found['confirmed']} вложенных полей корпуса")
