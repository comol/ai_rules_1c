"""Перечень «что код меняет у элементов»: записи разбора модуля, сведённые по элементу и части (`group`).

Записи приходят из разбора, который делает модель (`brief.codenotes`, инструкция `docs/brief-code.md`); этот модуль их только сводит и называет свойства.
Свойства — слова перечня: `видимость`, `доступность`, `только просмотр`, `текущая страница`, `заголовок`; прочие — слова записи (`создаёт колонку`,
`убирает кнопку`, `положение и размер`).
"""
import re

PROPS = {"видимость": "видимость", "доступность": "доступность", "толькопросмотр": "только просмотр",
         "текущаястраница": "текущая страница", "заголовок": "заголовок", "пометка": "пометка", "свертка": "свёртка", "значение": "значение"}
GROUP_APPLIED_PROPS = ("заголовок", "текущая страница", "доступность", "только просмотр", "пометка")       # свойства, у которых вариант группы с `default` рисунок применяет (`brief.codenotes._group_default`); видимость — у группы одной цели
FOCUS_PROP = "становится активным элементом формы"      # запись `current_element` (значения у такой записи нет)
DESKTOP_MODE = "режим рабочего стола"
BY_EXPRESSION = "по условию"           # значение записи, когда код вычисляет его выражением: рисунок его не подставляет, только помечает
CREATED_COLUMN = "создаёт колонку"
GONE = ("убирает страницу", "убирает колонку", "удаляет кнопку", "убирает элемент")      # убрано кодом: рисунок не рисует, когда запись безусловна
ALWAYS_DRAWN = (CREATED_COLUMN, "добавляет кнопку") + GONE


VALUE_PROP = "значение"        # значение поля, надписи, флажка, переключателя: литерал рисунок рисует, выражение только помечает
TEXT_LITERAL = re.compile(r'^"((?:[^"]|"")*)"$')
NUMBER_LITERAL = re.compile(r"^-?\d+(?:\.\d+)?$")
PLACEHOLDER = re.compile(r"<[^<>\n]+>")      # шаблон в тексте записи («Сумма - <сумма>»): слова модели о том, что будет вместо него, а не текст на экране


def drawable_text(text):
    """Текст записи (заголовок, значение), который рисунок вправе поставить на экран: без шаблона `<…>`; шаблон остаётся словами досье, а на рисунке — текст файла."""
    return not PLACEHOLDER.search(text or "")


def value_of(text):
    """Литерал значения поля, как его пишет код: `("bool", True|False)` — `Истина`/`Ложь`, `("text", строка)` — строка в кавычках, `("number", "7")` — число; `None` — выражение."""
    word = (text or "").strip()
    folded = word.casefold()
    if folded in ("истина", "true"):
        return "bool", True
    if folded in ("ложь", "false"):
        return "bool", False
    found = TEXT_LITERAL.match(word)
    if found:
        return "text", found.group(1).replace('""', '"')
    return ("number", word) if NUMBER_LITERAL.match(word) else None


def applies(prop, value):
    """Рисунок применяет безусловное значение свойства, а не только помечает: элемент, страница, колонка, кнопка убраны (`Ложь`), серым стало недоступное («только просмотр» на рисунке не выделяется);
    заголовок-текст и текущая страница — что назвал код (вычисляемый заголовок и текст с шаблоном `<…>` только помечаются); создание и удаление колонок, страниц, кнопок — как названо. `Истина` у видимости и доступности ничего на рисунке не меняет
    (файл рисует элемент видимым и доступным)."""
    return ((prop == "видимость" and value == "Ложь") or (prop == "доступность" and value == "Ложь") or (prop == "только просмотр" and value == "Истина")
            or (prop == "заголовок" and value != BY_EXPRESSION and drawable_text(value)) or prop == "текущая страница" or prop in ALWAYS_DRAWN or (prop == "пометка" and value in ("Истина", "Ложь"))
            or (prop == VALUE_PROP and value != BY_EXPRESSION and drawable_text(value)) or (prop == "свёртка" and value in COLLAPSED_MODES))


COLLAPSED_MODES = ("Лево", "Право", "Верх", "Низ")      # безусловная свёртка панели при открытии: рисунок строит раскладку со свёрнутой панелью (`layout.fold`); `Нет` — как в файле
NOOP = frozenset({("видимость", "Истина"), ("доступность", "Истина"), ("только просмотр", "Ложь")})      # безусловное значение, которое файл и так рисует: пометки нет


def drawn_props(effect):
    """Свойства строки перечня, которые рисунок применил: безусловные и несомненные (`applied`), которые `applies` пускает на рисунок."""
    return [p for p, v in effect["applied"].items() if applies(p, v)]


def procedure_at(procedures, line):
    """Имя процедуры, в теле которой строка `line`; `None` — строка вне процедур."""
    for proc in procedures:
        if proc["line"] <= line <= proc.get("end", proc["line"]):
            return proc["name"]
    return None


def label_map(names):
    """`{короткое имя элемента без регистра: [полные имена]}` — по ним код модуля находит элементы формы."""
    out = {}
    for full, item in names.item_of.items():
        out.setdefault(item.label().casefold(), []).append(full)
    return out


def group(rows):
    """Свёртка по элементу и части: `[{element, part, props: {свойство: [значения]}, procedures: [имена], lines: [строки], ranges: [«N–M»], exprs: {свойство: [выражения]},
    conds: {свойство: [условия]}, adds, applied: {свойство: значение}, variants: {свойство: [группы вариантов]},
    }]`.

    Строка — одна принятая запись разбора (`brief.codenotes.effect_rows`): `element`, `part`, `prop`, `value`, `procedure`, `line`, `line_to`, `expr`, `cond`,
    `applied` (безусловная и несомненная), `group` (вариант на одном месте), `add` (что известно о добавляемой кнопке). Выражение — значение записи, когда оно не
    «Истина»/«Ложь»; условие — то, при котором код это делает. `applied` у свойства — значение последней БЕЗУСЛОВНОЙ и несомненной записи: так рисунок показывает то,
    что увидит пользователь; условные записи до неё она перекрыла, условная или вероятная после неё — исключение из умолчания: `applied` несёт безусловное значение, исключение называет досье."""
    order, by = [], {}
    rows = list(rows)
    slots = {}
    for at, row in enumerate(rows):
        slots.setdefault((row["element"], row["part"], row["prop"]), []).append(at)
    for places in slots.values():              # записи одного свойства одного элемента — в порядке выполнения (`order`), остальное — в порядке файла записей
        if len(places) > 1 and all(rows[at].get("order") is not None for at in places):
            for at, row in zip(places, sorted((rows[at] for at in places), key=lambda r: r["order"])):
                rows[at] = row
    for row in rows:
        key = (row["element"], row["part"])
        if key not in by:
            by[key] = {"element": row["element"], "part": row["part"], "props": {}, "procedures": [], "lines": [], "ranges": [], "exprs": {}, "conds": {},
                       "applied": {}, "variants": {}, "_sure": {}}
            order.append(key)
        entry = by[key]
        prop = row["prop"]
        values = entry["props"].setdefault(prop, [])
        if row["value"] not in values:
            values.append(row["value"])
        for field, key_ in (("expr", "exprs"), ("cond", "conds")):
            if row.get(field) and row[field] not in entry[key_].setdefault(prop, []):
                entry[key_][prop].append(row[field])
        if row.get("add") and row["add"] not in entry.setdefault("adds", []):
            entry["adds"].append(row["add"])      # что известно о добавляемой кнопке (`brief.codenotes`): место, картинка, отображение — для рисунка
        if row.get("group"):
            groups = entry["variants"].setdefault(prop, [])
            if row["group"] not in groups:
                groups.append(row["group"])
            entry.setdefault("variant_default", {})[row["group"]] = bool(row.get("default")) or entry.get("variant_default", {}).get(row["group"], False)
        if row["procedure"] and row["procedure"] not in entry["procedures"]:
            entry["procedures"].append(row["procedure"])
        entry["lines"].append(row["line"])
        words = f"{row['line']}–{row['line_to']}" if row.get("line_to") and row["line_to"] != row["line"] else str(row["line"])
        if words not in entry["ranges"]:
            entry["ranges"].append(words)
        if prop == "заголовок" and row["value"] == BY_EXPRESSION and not row.get("cond") and not row.get("group") and not row.get("user_only") and row.get("opening", True):
            entry.setdefault("blank", set()).add(prop)          # безусловный заголовок, который задаёт код выражением: на рисунке — пустая рамка, текст файла он не показывает
        if row.get("user_only") or (row.get("opening") is False and row.get("cond")):
            continue            # условная запись в процедуре, до которой открытие не доходит (её зовут только обработчики действий, таймер, `Выполнить`): вид при открытии она не меняет и безусловное не перекрывает — как в обзоре «При открытии»
        if row.get("group") and not row.get("default") and (prop in GROUP_APPLIED_PROPS or (prop == "видимость" and row.get("group_single"))):
            continue            # другой вариант группы (заголовок, текущая страница, доступность, видимость одной цели): при открытии показан вариант с `default`, остальные итог не перекрывают
        sure = entry["_sure"].setdefault(prop, [])
        sure.append((bool(row.get("applied")), row["value"]))
        decided = next((i for i in range(len(sure) - 1, -1, -1) if sure[i][0]), None)
        if decided is not None and decided == len(sure) - 1:
            entry["applied"][prop] = sure[decided][1]       # последняя безусловная запись решает; условное после неё — исключение
            if len(sure) > 1 and not all(flag for flag, _value in sure):
                # условные и вероятные записи до неё перекрыты: в строке перечня остаётся она, а условия и выражения прежних записей уходят
                entry.setdefault("overridden", {})[prop] = row["line"]
                entry["props"][prop] = [row["value"]]
                for key_ in ("exprs", "conds", "variants"):
                    entry[key_].pop(prop, None)
                for field, key_ in (("expr", "exprs"), ("cond", "conds")):
                    if row.get(field):
                        entry[key_][prop] = [row[field]]
        elif decided is None:
            entry["applied"].pop(prop, None)          # условная запись после безусловной («по умолчанию — исключение») значение по умолчанию не снимает: рисунок показывает умолчание
    out = []
    for key in order:
        entry = by[key]
        entry.pop("_sure")
        blank = sorted(p for p in entry.pop("blank", ()) if p not in entry["applied"])
        if blank:
            entry["blank"] = blank
        out.append(entry)
    return out
