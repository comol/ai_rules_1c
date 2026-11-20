"""Разделы обзора «При открытии» и «Что делает код»: что пользователь видит сразу после открытия формы и что меняется на экране от его действий.

Оба раздела строятся из записей разбора кода, которые сделала модель (`code-notes.json`): значения и условия берутся её словами, переменные модуля не называются
(`moduleview`), выражение не превращается в «да» и «нет». «При открытии» — безусловное состояние, пары «значение — условие» по элементам и эффекты событий открытия;
записи из процедур, которые вызывают только действие пользователя или таймер, сюда не входят. «Что делает код» — по событию «действие → что меняется»: текст модели
об эффекте и приёмники этого эффекта.
"""

import collections
import re

from . import module_effects as effects_mod, moduleview as mv, usual
from .codenotes import CLEAR_WORDS, WHAT_WORDS
from .words import counted

OPEN_EVENTS = ("передоткрытием", "приоткрытии", "обновлениеотображения", "послевосстановлениязначений")      # события формы, которые идут при открытии
OPEN_KINDS = ("visibility", "enabled", "read_only", "title", "current_page", "current_element", "collapse", "checked", "value", "created", "removed", "desktop_mode", "appearance")
KIND_NOUN = {"visibility": "видимость", "enabled": "доступность", "read_only": "«только просмотр»"}
VAR_WORDS = {"visibility": ("показан", "скрыт"), "enabled": ("доступен", "недоступен"), "read_only": ("только просмотр", "доступен для ввода")}      # (Истина, Ложь)
EFFECT_CHARS = 230         # знаков текста одного эффекта
EXPR_CHARS = 100           # знаков пояснения к выражению в скобках
PHRASE_CHARS = 560         # знаков фразы «состояние и условие» одной цели
HEAD_NAMES = 8             # скрытых и недоступных при открытии целей в первой строке называется поимённо
TARGETS_SHOWN = 3          # приёмников эффекта называется поимённо
LISTED_NAMES = 5          # колонок одной таблицы называется поимённо
LITERALS = {"Истина": True, "True": True, "Ложь": False, "False": False}
COLLAPSE_WORDS = {"Верх": "свёрнута вверх", "Низ": "свёрнута вниз", "Лево": "свёрнута влево", "Право": "свёрнута вправо", "Нет": "развёрнута"}
SCREEN_WHAT = frozenset(WHAT_WORDS) - {"write", "other"}      # виды эффекта, которые меняют экран; `other` — только с текстом о видимом (см. `_screen`)
NOISE = re.compile(r"помечает форму (?:как )?изменённ|помечает форму изменен|форма (?:становится )?изменённой|Модифицированность", re.I)      # эффект без видимого результата


def _cap(text, limit):
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0].rstrip(",;:—- ") + "…"


def _drawn_title(value):
    """Заголовок — текст в кавычках целиком и без шаблона `<…>`: его рисунок ставит; описание словами, склейка с выражением и шаблон на рисунке остаются текстом файла."""
    return mv.literal(value) is not None and effects_mod.drawable_text(value)


def _note_name(ctx, note):
    """Имя цели записи в строке обзора: у `current_page` — панель, у прочих — `Context.name`."""
    if note["kind"] == "current_page" and note["target"].get("element"):
        return f"панель «{ctx.short(note['target']['element'])}»"
    return ctx.name(note["target"])


def _by_name(ctx, notes):
    """`{имя цели: [записи]}` — по ним обзор знает, какие записи он назвал, когда называет цель."""
    out = collections.OrderedDict()
    for note in notes:
        out.setdefault(_note_name(ctx, note), []).append(note)
    return out


class Context:
    """Разбор кода, нужный разделам: записи, имена и переменные модуля."""

    def __init__(self, brief, short):
        self.brief = brief
        self.short = short
        self.module = brief["purpose"]["module"]
        self.code = brief["head"].get("code") or {}
        self.vars = {v.casefold() for v in self.module.get("variables") or ()}
        self.accepted = self.code.get("accepted") or []
        self.parsed = self.code.get("state") == "parsed"
        self.said = set()          # номера принятых записей, которые обзор назвал (`unsaid`): запись не должна пропасть из `brief.md` молча

    def types(self):
        """`{полное имя элемента: вид}` по структуре формы."""
        if getattr(self, "_types", None) is None:
            self._types = {e["element"]: e["type"] for e in (self.brief.get("structure") or {}).get("elements", ())}
        return self._types

    # ── Имена и значения ──

    def name(self, target):
        kind, sub = target["kind"], target.get("sub")
        el = self.short(target["element"]) if target.get("element") else None
        if kind == "form":
            return "форма"
        if kind == "element":
            return el or "элемент, имя которого вычисляет код"
        if kind == "page":
            return f"страница «{sub}» панели «{el}»"
        if kind == "column":
            return f"колонка «{sub}» таблицы «{el}»" if sub else f"таблица «{el}»"
        if kind == "button":
            return f"кнопка «{sub}» панели «{el}»" if sub else f"панель «{el}»"
        return el or "форма"

    def state(self, note):
        """`(слова состояния, условие, форма условия)` записи: `clear` — «если …», `inline` — описание после двоеточия, `unclear` — через тире."""
        kind, value = note["kind"], note["value"].strip()
        cond, clear = mv.condition(note["condition"], self.vars, note["lines"][0])
        form = "clear" if clear else "unclear"
        lit = LITERALS.get(value)
        if kind in KIND_NOUN:
            noun = KIND_NOUN[kind]
            if lit is None and mv.mentions(value, self.vars):
                text = f"{noun} задаёт код"
                if clear and cond:
                    on, off = VAR_WORDS[kind]
                    cond = re.sub(r"\bИстина\b", on, re.sub(r"\bЛожь\b", off, re.sub(r"в теле модуля\s*=\s*", "сначала ", cond)))
                    form = "expr"
            elif lit is None:
                text = f"{noun} по выражению «{value}»"
                form = "expr" if clear and cond else form
            else:
                on, off = VAR_WORDS[kind]
                text = on if lit else off
        elif kind == "title":
            shown = mv.title_words(value, self.vars)
            said = _cap(mv.safe_text(note.get("why"), self.vars), EXPR_CHARS) if not shown and note.get("why") else ""
            text = (f"заголовок {shown}" if shown and _drawn_title(value) else f"заголовок задаёт код ({shown})" if shown else f"заголовок задаёт код ({said})" if said else "заголовок задаёт код")          # на картинке — текст файла: слова записи — описание или шаблон
            if (not shown or "<" in value) and clear and cond:
                form = "expr"          # условие названо перечнем того, от чего зависит заголовок, а не условием показа
        elif kind == "current_page":
            text = f"текущая страница «{note['target'].get('sub')}»"
        elif kind == "current_element":
            text = "становится активным элементом"
        elif kind == "collapse":
            text = COLLAPSE_WORDS.get(value, f"свёртка: {value}")
        elif kind == "checked":
            text = "пометка включена" if lit else "пометка снята" if lit is not None else "пометка задаётся кодом"
            if lit is None and clear and cond:
                form = "expr"
        elif kind == "value":
            text = "значение " + self.value_words(value, note["target"].get("element"), note.get("why"))
            if lit is None and effects_mod.value_of(value) is None and clear and cond:
                form = "expr"
            if cond and note["target"].get("element") in self.first_open():
                text = "иначе — " + text          # первое открытие называет литерал тела модуля объекта, условная запись — что будет дальше
        elif kind == "appearance":
            text = "оформление: " + (mv.safe_text(value, self.vars) or "задаёт код")
            if cond and cond.casefold() in text.casefold():
                cond = ""          # условие только повторяет слова оформления («по состоянию документа, если состояние документа»)
        elif kind in ("created", "removed"):
            text = ("создаётся кодом" if kind == "created" else "убирается кодом")
        else:
            text = "режим рабочего стола" if kind == "desktop_mode" else kind
        if lit is None and kind in KIND_NOUN and cond and form in ("clear", "expr") and len(cond) < 90:
            ids = set(re.findall(mv.NAME, value))
            if ids and all(i.casefold() in cond.casefold() for i in ids if i.upper() != "НЕ" and i.upper() != "И" and i.upper() != "ИЛИ"):
                cond = ""                # условие лишь пересказывает выражение: «по выражению «X», если X включён»
        if form == "expr" and cond:
            cond = re.sub(r"^выражение зависит от ", "зависит от ", cond)          # «задаёт код (зависит от …)», а не «если зависит от …»
            lead = re.match(rf"({mv.NAME}):\s*", cond)
            if lead and lead.group(1).casefold() in {w.casefold() for w in re.findall(mv.NAME, value)}:
                cond = cond[lead.end():]          # «Имя: …» повторяет выражение
            cond = _cap(cond, EXPR_CHARS)
        return text, cond, form

    def first_open(self):
        """Элементы, у которых значение первого открытия — литерал тела модуля объекта, а запись модели условна (`иначе — …`)."""
        if getattr(self, "_first", None) is None:
            body = {n["target"]["element"] for n in self.accepted if n.get("object_body") and n["kind"] == "value"}
            self._first = {n["target"]["element"] for n in self.accepted if n["kind"] == "value" and n["condition"] and n["target"]["element"] in body}
        return self._first

    def value_words(self, value, element, why=None):
        """Значение данных поля словами: флажок — «включено»/«снято», остальное — текст в «ёлочках», число, `Истина`/`Ложь`; выражение — слова модели из `why` и «(задаёт код)», без `why` — «задаёт код»;
        само выражение — в `brief.json` и `--detail code`."""
        found = effects_mod.value_of(value)
        if found is None:
            words = _cap(mv.safe_text(why, self.vars), EXPR_CHARS) if why else ""
            return f"задаёт код: {words}" if words else "задаёт код"
        kind, own = found
        if kind == "text" and not effects_mod.drawable_text(own):
            return f"по шаблону «{_cap(own, EXPR_CHARS)}»"          # шаблон `<…>` — слова модели о значении, текстом поля на рисунке он не стоит
        if kind == "bool":
            return ("включено" if own else "снято") if self.types().get(element) == "CheckBox" else ("выбран" if own else "не выбран") if self.types().get(element) == "RadioButton" else "Истина" if own else "Ложь"
        return f"«{_cap(own, EXPR_CHARS)}»" if kind == "text" else own

    def effect_text(self, effect, cap=EFFECT_CHARS):
        """Строка эффекта: слова модели и приёмники этого эффекта (`текст → приёмники`); `cap=None` — без обрезки."""
        text = mv.safe_text(effect["text"] or WHAT_WORDS[effect["what"]], self.vars)
        text = text if cap is None else _cap(text, cap)
        targets = list(dict.fromkeys(a.split("/")[-1] for a in effect["affects"]))
        if not text:
            text = WHAT_WORDS[effect["what"]] if targets else ""            # слова модели целиком были об учётных данных или переменных модуля
            if not text:
                return None
        if effect["what"] == "write":
            text = "в данных: " + text
        if targets and not any(t in text for t in targets):
            text += " → " + ", ".join(targets[:TARGETS_SHOWN]) + (f" и ещё {len(targets) - TARGETS_SHOWN}" if len(targets) > TARGETS_SHOWN else "")          # приёмники называются и при условии
        if effect.get("condition"):
            cond, clear = mv.condition(effect["condition"], self.vars)
            if cond and clear:
                text += _when(cond)          # условие одного эффекта события (не всего события)
        return text


# ── Модуль не получен, код не разобран ──

def handlers_text(module):
    """`(число назначений обработчиков, имена событий открытия)` по файлу формы."""
    rows = module.get("handlers") or []
    opening = [r["event"] for r in rows if r["owner"] == "form" and str(r["event"]).casefold() in OPEN_EVENTS]
    return len(rows), list(dict.fromkeys(opening))


def not_received(module):
    """Предложение о форме без модуля: честно говорит, что код неизвестен, если в файле назначены обработчики."""
    count, opening = handlers_text(module)
    if not count:
        return "Модуль формы не получен; обработчиков событий в файле формы нет, поэтому форма, скорее всего, ведёт себя так, как записано в файле."
    word = counted(count, "обработчик", "обработчика", "обработчиков")
    return (f"Модуль формы не получен: в файле формы назначено {word}" + (f" (события открытия: {', '.join(opening)})" if opening else "")
            + "; что они делают, неизвестно.")


def _handler_kinds(module):
    """Слова о том, на что назначены обработчики: события формы, элементов, колонок, кнопок панелей."""
    rows = module.get("handlers") or []
    count = collections.Counter(r["owner"] for r in rows)
    parts = []
    for owner, one, few, many in (("form", "событие формы", "события формы", "событий формы"), ("element", "событие элементов", "события элементов", "событий элементов"),
                                  ("panel", "кнопка панели", "кнопки панелей", "кнопок панелей"), ("column", "событие колонки", "события колонок", "событий колонок")):
        if count.get(owner):
            parts.append(counted(count[owner], one, few, many))
    return ", ".join(parts)


# ── При открытии ──

def _when(cond):
    """Условие в строке обзора — единственный шаблон: в скобках, словами записи (законченное придаточное: «если …», «при …», «роль без права записи»). Навык «если», «при» и «зависит от»
    к фразе модели не приклеивает."""
    return f" ({cond})" if cond else ""


def _cond_words(text, cond, form=None):
    """Состояние и его условие одной фразой: «текст (условие)»."""
    return text + _when(cond)


def _variant_phrases(ctx, rows):
    """`{имя цели: [фразы]}` и записи, не вошедшие в варианты: у цели, чьё свойство задано группой вариантов на одном месте (`group`, `default`), вариант по умолчанию назван первым —
    «по умолчанию скрыт (условие); иначе — показан, если …»."""
    by = collections.OrderedDict()
    for note in rows:
        if note.get("group") and note["kind"] in (*KIND_NOUN, "title", "current_page", "appearance"):
            by.setdefault((_note_name(ctx, note), note["kind"], note["group"]), []).append(note)
    found, taken = collections.OrderedDict(), set()
    for (name, _kind, _group), notes in by.items():
        default = next((n for n in notes if n.get("default")), None)
        if default is None or len(notes) < 2:
            continue
        text, cond, form = ctx.state(default)
        first = "по умолчанию " + text + (f" ({cond})" if cond else "")
        others = []
        for n in notes:
            if n is not default:
                t, c, f = ctx.state(n)
                others.append(_cond_words(t, c, f))
        found.setdefault(name, []).append(first + ("; иначе — " + "; ".join(dict.fromkeys(others)) if others else ""))
        taken.update(id(n) for n in notes)
    return found, [n for n in rows if id(n) not in taken]


def _phrases(ctx, rows):
    """`{цель: [слова]}`: записи по цели; записи с одним состоянием и разными условиями сведены в одну фразу «состояние: если …; если …»; вариант по умолчанию группы назван."""
    variants, rows = _variant_phrases(ctx, rows)
    per, kinds = collections.OrderedDict(), {}
    for note in rows:
        text, cond, form = ctx.state(note)
        name = _note_name(ctx, note)
        per.setdefault(name, collections.OrderedDict()).setdefault(text, []).append((cond, form))
        kinds.setdefault((name, text), note["kind"])
    out = collections.OrderedDict()
    for name, by_text in per.items():
        phrases = []
        for text, conds in by_text.items():
            conds = [c for c in dict.fromkeys(conds) if c[0]]
            # безусловное состояние при условных записях того же свойства — состояние по умолчанию: последнее слово за условием
            overridden = not conds and any(any(c[0] for c in other) for t, other in by_text.items() if t != text and kinds[(name, t)] == kinds[(name, text)])
            if not conds:
                phrases.append(text + (" по умолчанию" if overridden else ""))
            elif len(conds) == 1:
                phrases.append(_cond_words(text, *conds[0]))
            else:
                phrases.append(text + " (" + "; ".join(c for c, _f in conds[:3]) + ")")
        out[name] = phrases
    for name, phrases in variants.items():
        out.setdefault(name, []).extend(phrases)
    return out


def _pairs(ctx, rows):
    """`[(имена, слова)]`: цели с одной и той же фразой (состояние и условие) — одной строкой; фразы, у которых совпал весь список целей, сведены в одну строку через «; »."""
    groups = collections.OrderedDict()
    for name, phrases in _phrases(ctx, rows).items():
        for phrase in phrases:
            groups.setdefault(phrase, []).append(name)
    merged = collections.OrderedDict()
    for phrase, names in groups.items():
        merged.setdefault(tuple(names), []).append(phrase)
    return [(list(names), "; ".join(phrases)) for names, phrases in merged.items()]


def _fixed(ctx, note):
    """Запись безусловна: без условия и несомненна (заголовок без условия — тоже: вероятность относится к значению, а не к тому, что код его ставит)."""
    if note["condition"]:
        return False
    return True


def _covering(group):
    """Группа записей (или одна запись) одного свойства одного элемента даёт итог при любом исходе: в ней есть вариант по умолчанию («Иначе») среди вариантов одной группы, либо запись одна и безусловна.
    Вариант по умолчанию без группы со своим условием («формат не передан») покрывает только это условие."""
    return any(n.get("default") and n.get("group") for n in group) or (len(group) == 1 and not group[0].get("group") and not group[0]["condition"])


def _is_copy(ctx, note):
    """Запись `Элемент.Значение = Реквизит`: значение — данные самого поля (`Вид` у поля, привязанного к реквизиту `Вид`). Это копия, а не новое значение: итог — то, что стояло в реквизите раньше."""
    if note["kind"] != "value":
        return False
    word = re.sub(r"^(?:ЭтотОбъект|Объект|ЭтаФорма)\s*\.\s*", "", note["value"].strip(), flags=re.I).casefold()
    for e in (ctx.brief.get("structure") or {}).get("elements", ()):
        if e["element"] == note["target"].get("element"):
            data = re.sub(r"^реквизит (?:формы|объекта)\s+", "", e.get("data") or "")
            return bool(data) and data.casefold() == word
    return False


def split_overridden(rows, is_copy=lambda note: False):
    """`(записи, перекрытые)`: запись, после которой на пути открытия (`order`) стоит группа того же свойства того же элемента, покрывающая все исходы (с веткой «Иначе» либо безусловная),
    перекрыта — при открытии итогом она не бывает, её условие относится к действию пользователя. Группа — записи с одним `group`; записи без `order` в сравнении не участвуют.
    Перекрывает только другое значение: копия данных поля (`is_copy`) и то же значение, что стояло раньше, раньшего не снимают."""
    slots = collections.OrderedDict()
    for n in rows:
        if n.get("order"):
            slots.setdefault((repr(n["target"]), n["kind"]), []).append(n)
    dropped = set()
    for notes in slots.values():
        groups = collections.OrderedDict()
        for n in notes:
            groups.setdefault(("g", n["group"]) if n.get("group") else ("n", id(n)), []).append(n)
        spans = [(min(tuple(n["order"]) for n in g), max(tuple(n["order"]) for n in g), _covering(g), g) for g in groups.values()]
        for first, last, _cover, group in spans:
            if any(cover and first2 > last and not _no_change(group, other, is_copy) for first2, _l2, cover, other in spans if other is not group):
                dropped.update(id(n) for n in group)
    return [n for n in rows if id(n) not in dropped], [n for n in rows if id(n) in dropped]


def _no_change(early, late, is_copy):
    """Поздняя группа не меняет итог ранней: одна запись, и она копирует данные поля либо ставит то же значение, что каждая ранняя."""
    if len(late) != 1:
        return False
    return is_copy(late[0]) or all(n["value"].strip() == late[0]["value"].strip() for n in early)


def opening_rows(ctx):
    """`(записи открытия, перекрытые при открытии)`: состояния, оформление и созданное, которые код ставит при открытии."""
    rows = [n for n in ctx.accepted if n["kind"] in OPEN_KINDS and n.get("opening", True) and n["kind"] not in ("created", "removed")]
    return split_overridden(rows, lambda n: _is_copy(ctx, n))


def has_sections(ctx):
    """Разделы «При открытии» и «Что делает код» есть, когда код разобран либо модуль не получен, а обработчики в файле формы назначены; иначе сказать о них нечего."""
    if ctx.parsed:
        return True
    return not ctx.module["present"] and bool(handlers_text(ctx.module)[0])


def _folded(names):
    """`[(слова, [имена целей])]`: колонки одной таблицы свёрнуты в одно слово, элементы поимённо."""
    columns, rest = collections.OrderedDict(), []
    for name in names:
        match = re.fullmatch(r"колонка «(.+?)» таблицы «(.+?)»", name)
        if match:
            columns.setdefault(match.group(2), []).append((match.group(1), name))
        else:
            rest.append((name, [name]))
    out = list(rest)
    for table, cols in columns.items():
        shown = ", ".join(f"«{c}»" for c, _n in cols[:LISTED_NAMES])
        words = f"{counted(len(cols), 'колонка', 'колонки', 'колонок')} таблицы «{table}»" + (f" ({shown}{', …' if len(cols) > LISTED_NAMES else ''})" if len(cols) > 1 else f" («{cols[0][0]}»)")
        out.append((words, [n for _c, n in cols]))
    return out


def _listed(ctx, names, by_name, limit, wrap=lambda text: text):
    """Имена целей строкой: первые `limit` слов и «и ещё N»; запись, у которой за пределом осталась бы ни одной названной цели, называется всё равно (запись из обзора не пропадает).
    Названные записи — в `ctx.said`. `by_name` — `_by_name` тех же записей."""
    entries = _folded(names)
    kept = entries[:limit]
    said = {n["index"] for _words, members in kept for m in members for n in by_name.get(m, ())}
    for entry in entries[limit:]:
        found = {n["index"] for m in entry[1] for n in by_name.get(m, ())}
        if found - said:
            kept.append(entry)
            said |= found
    ctx.said |= said
    rest = len(entries) - len(kept)
    return ", ".join(wrap(words) for words, _members in kept) + (f" и ещё {rest}" if rest else "")


def _counts(names):
    """«элементов: N, колонок: M» по именам целей."""
    columns = sum(1 for n in names if n.startswith("колонка "))
    parts = []
    if len(names) - columns:
        parts.append(f"элементов: {len(names) - columns}")
    if columns:
        parts.append(f"колонок: {columns}")
    return ", ".join(parts)


def _refreshed(note):
    """Запись стоит на пути от `ОбновлениеОтображения` (ранг 3 в порядке жизни формы): платформа вызывает событие при открытии и после каждого изменения данных и записи, запись действует и тогда."""
    return bool(note.get("order")) and note["order"][0] == 3 and note.get("opening", True)


def _pair_lines(ctx, notes, title):
    """Строки «title (элементов: N):» и по строке на цели с одним и тем же состоянием и условием; без предела числа строк (запись, спрятанная за «ещё N условий», из обзора пропадала)."""
    pairs = _pairs(ctx, notes)
    by_name = _by_name(ctx, notes)
    everything = list(dict.fromkeys(n for names, _p in pairs for n in names))
    lines = [f"- {title} ({_counts(everything)}):"]
    for names, phrase in pairs:
        lines.append(f"  - {_cap(_listed(ctx, names, by_name, 4), 400)}: {_cap(phrase, PHRASE_CHARS)}")
    return lines


def _effects_lines(ctx, ev, indent):
    """Эффекты события, по одному на строку: видимые первыми, без обрезки."""
    visible, hidden = [], []
    for e in ev["effects"]:
        text = ctx.effect_text(e, cap=None)
        if not text:
            continue
        (visible if e["what"] in SCREEN_WHAT and (e["affects"] or e["text"]) else hidden).append(text)      # видимое первым; `other` — после него
    return [f"{indent}- {t}" for t in visible + hidden]


def _timer_lines(ctx, opening=True):
    """Таймеры (`ПодключитьОбработчикОжидания`): процедура, интервал и условия подключения; одинаковые подключения из разных процедур сведены в одну строку. `opening` — подключённые при
    открытии (по графу вызовов) либо подключённые по действию пользователя: те в «При открытии» не входят."""
    groups = collections.OrderedDict()
    for t in ctx.module.get("timers") or []:
        if bool(t.get("opening", True)) == opening:
            groups.setdefault((t["handler"], t["interval"], bool(t.get("once"))), []).append(t)
    out = []
    for (handler, interval, once), rows in groups.items():
        every = f"каждые {interval} с" if re.fullmatch(r"[\d.,]+", interval) else f"с интервалом, который задаёт выражение «{interval}»"
        where = []
        for t in rows:
            cond, clear = mv.condition(t["condition"], ctx.vars, t["line"]) if t.get("condition") else ("", True)
            where.append((t["in"] or "тело модуля") + (_when(cond) if cond and clear else ""))
        out.append(f"- Таймер: процедура «{handler}» {every}{', один раз' if once else ''}; подключается {'в' if opening else 'по действию пользователя, в'}: {'; '.join(dict.fromkeys(where))}.")
    return out


def _opened_pages(ctx):
    """`[(панель или «форма», открытая страница, по условию)]` панелей с несколькими страницами: страница, выбранная кодом безусловно, иначе первая нарисованная; только видимые панели.
    «По условию» — код выбирает текущую страницу по условию либо прячет саму открытую страницу: безусловным «открыта» это называть нельзя."""
    from . import areas
    structure = ctx.brief.get("structure")
    if not structure or "tree" not in structure:
        return []
    skip = set((ctx.brief.get("images") or {}).get("not_drawn") or [])
    dead = areas.undrawn_elements(ctx.brief) | set(structure.get("hidden", ())) | areas._hidden_by_code(ctx.brief)
    chosen, by_condition = {}, set()
    for n in ctx.accepted:
        if n["kind"] == "current_page" and n["target"].get("element"):
            if _fixed(ctx, n):
                chosen[n["target"]["element"]] = n["target"].get("sub")
                ctx.said.add(n["index"])
            else:
                by_condition.add(n["target"]["element"])
    by_panel = collections.OrderedDict()
    for p in structure["pages"]:
        by_panel.setdefault(p["panel"], []).append(p)
    out = []
    for panel, pages in by_panel.items():
        if len(pages) < 2 or (panel and panel in dead):
            continue
        shown = [p for p in pages if p.get("node") not in skip]
        word = chosen.get(panel)
        page = next((p for p in pages if word and p.get("code_page") and p["code_page"].casefold() == str(word).casefold()), None) or (shown[0] if shown else None)
        if page:
            out.append((panel.split("/")[-1] if panel else "форма", page["caption"], panel in by_condition or bool(page.get("by_code"))))
    return out


def _headline(ctx, fixed, conditional, events, refused):
    """Первая строка раздела: что пользователь видит при открытии формы — открытые страницы, скрытое, недоступное, режим, заголовок, что форма делает сама."""
    bits = []
    pages = _opened_pages(ctx)
    if pages:
        bits.append("открыты страницы: " + ", ".join(f"«{at}» ({panel}{', по условию — ниже' if cond else ''})" for panel, at, cond in pages[:3]) + (f" и ещё {len(pages) - 3}" if len(pages) > 3 else ""))
    off, cut, ro, title = [], [], False, None
    by_name = _by_name(ctx, fixed)
    for n in fixed:
        value = LITERALS.get(n["value"].strip())
        if n["kind"] == "visibility" and value is False:
            off.append(ctx.name(n["target"]))
        elif n["kind"] == "enabled" and value is False:
            cut.append(ctx.name(n["target"]))
        elif n["kind"] == "read_only" and n["target"]["kind"] == "form" and value is not False:
            ro = True
        elif n["kind"] == "title" and n["target"]["kind"] == "form":
            title = ctx.state(n)[0]
            title = None if title == "заголовок задаёт код" else title          # «Что это за форма» уже говорит, что заголовок окна задаёт код
    for word, names in (("скрыто", off), ("недоступно", cut)):
        if names:
            bits.append(f"{word}: " + _listed(ctx, names, by_name, HEAD_NAMES))
    if ro:
        bits.append("форма только для просмотра")
    if title:
        bits.append(title.replace("заголовок", "заголовок окна", 1))
    if any(n["kind"] == "read_only" and n["target"]["kind"] == "form" for n in conditional):
        bits.append("режим «только просмотр» формы зависит от условия")
    if conditional:
        bits.append(f"зависит от условий ({_counts(list(_phrases(ctx, conditional)))}) — ниже")          # те же цели, что в списке ниже: число в итоге и в списке одно
    if events:
        count = sum(1 for ev in events for e in ev["effects"] if _screen(e))
        bits.append(f"форма сама выполняет действия: {count} (ниже)" if count else "форма сама выполняет служебные действия без видимого эффекта")
    if refused:
        bits.append("форма может не открыться")
    if not bits:
        return "Видно при открытии: форма такая, как на `clean.png`."
    return "Видно при открытии: " + "; ".join(bits) + "."


def opening_lines(ctx, page_marks=None):
    """Раздел «При открытии»: что видно сразу после открытия."""
    if not has_sections(ctx):
        return []
    lines = ["## При открытии", ""]
    module = ctx.module
    if not module["present"]:
        lines.append(not_received(module))
        started = [f"{r['event']} (процедура {r['procedure']})" for r in module["handlers"] if r["owner"] == "form" and str(r["event"]).casefold() in OPEN_EVENTS]
        if started:
            lines.append("- Обработчики открытия в файле формы: " + ", ".join(started) + ".")
        lines.append("Что пользователь видит при открытии, по файлу не определить: `clean.png` показывает форму по файлу, а код может скрыть и показать элементы, сделать их недоступными, "
                     "заполнить поля и задать текущую страницу.")
        return lines + [""]
    rows, _shadowed = opening_rows(ctx)
    events = [e for e in module.get("events") or [] if e["source"] == "форма" and str(e["event"]).casefold() in OPEN_EVENTS]
    refused = ctx.code.get("open_refused") or []
    timers = _timer_lines(ctx)
    choices = _choice_lines(ctx, opening=True)
    built = _form_others(ctx, opening=True)
    made = _made(ctx, opening=True)
    if not rows and not events and not refused and not choices and not built and not made:
        lines.append("Видно при открытии: форма такая, как на `clean.png`; код при открытии ничего не меняет на экране.")
        lines += timers + _page_lines(ctx, page_marks)
        return lines + [""]
    fixed = [n for n in rows if _fixed(ctx, n)]
    # безусловная запись, после которой в модуле стоит условная запись о том же свойстве того же элемента, итогом не является: последнее слово за условной
    kept = [n for n in fixed if n.get("object_body") or not any(m is not n and m["kind"] == n["kind"] and m["target"] == n["target"] and m["lines"][0] > n["lines"][0] and not _fixed(ctx, m) for m in rows)]
    ctx.said.update(n["index"] for n in fixed if n not in kept)          # итог — условная запись ниже: она названа, перекрытая безусловная — нет
    fixed = kept
    ctx.said.update(n["index"] for n in fixed if _same_as_file(ctx, n))          # экран такой же, как нарисован по файлу: сказать нечего
    conditional = [n for n in rows if n not in fixed and not _said_with_pages(ctx, n, page_marks) and not (n["kind"] == "title" and n["target"]["kind"] == "form" and _title_in_head(ctx, n))]
    lines.append(_headline(ctx, fixed, conditional, events, refused))
    stops = []
    for r in refused:
        cond, _clear = mv.condition(r["condition"], ctx.vars, r["lines"][0])
        stops.append("- Форма может не открыться" + (f" ({cond})" if cond else " безусловно") + (f"; сообщение «{r['message']}»" if r["message"] else ""))
    lines += list(dict.fromkeys(stops))          # одинаковые причины отказа из разных мест кода — одной строкой
    other = [n for n in fixed if not _in_headline(n) and not _same_as_file(ctx, n) and n["kind"] != "value"]          # что сказано первой строкой (скрыто, недоступно, «только просмотр», заголовок, страницы), не повторяется
    if other:
        lines.append("- Безусловно: " + _fixed_words(ctx, other))
    first = ctx.first_open()
    copies = [n for n in fixed if _is_copy(ctx, n)]          # `Поле.Значение = Реквизит`: поле показывает собственные данные, сказать нечего
    ctx.said.update(n["index"] for n in copies)
    plain = [n for n in fixed if n["kind"] == "value" and not n.get("spread") and n not in copies]
    for label, group in (("Значения полей при открытии", [n for n in plain if n["target"].get("element") not in first]), ("При первом открытии", [n for n in plain if n["target"].get("element") in first])):
        values = _value_line(ctx, group, label)
        if values:
            lines.append(values)
    if events:
        lines.append("- Что форма делает сама при открытии (слова модели; видимое первым):")
        order = {name: at for at, name in enumerate(OPEN_EVENTS)}
        for ev in sorted(events, key=lambda e: order[str(e["event"]).casefold()]):
            cond, clear = mv.condition(ev["condition"], ctx.vars, ev["lines"][0])
            sub = _effects_lines(ctx, ev, "    ")
            if not sub:
                continue
            lines.append(f"  - {ev['event']}" + (_when(cond) if cond and clear else "") + (" — при открытии и после каждого изменения и записи" if str(ev["event"]).casefold() == "обновлениеотображения" else "") + ":")
            lines += sub
    lines += choices
    lines += built
    if made:
        lines.append("- Код при открытии: " + made)
    lines += timers
    refreshed = [n for n in conditional if _refreshed(n)]
    for group, title in (([n for n in conditional if not _refreshed(n)], "Зависит от условий"),
                         (refreshed, "Зависит от условий и пересчитывается при открытии и после каждого изменения и записи, ОбновлениеОтображения")):
        if group:
            lines += _pair_lines(ctx, group, title)
    lines += _page_lines(ctx, page_marks)
    drawn = _drawn(ctx, rows)
    if drawn:
        lines.append(drawn)
    return lines + [""]


LISTS_SHOWN = 12           # списков выбора в обзоре поимённо
LIST_CHARS = 110           # знаков в перечне значений одного списка
LOOKS_SHOWN = 8            # строк оформления в «Что делает код»


def _list_words(text):
    """Значения списка выбора: до пяти — перечнем, больше — числом и первыми четырьмя; значения короче 40 знаков."""
    parts = [p.strip() for p in re.split(r";\s*", text or "") if p.strip()]
    if len(parts) > 5:
        return f"{len(parts)} значений: " + "; ".join(_cap(p, 40) for p in parts[:4]) + "; …"
    return _cap("; ".join(parts), LIST_CHARS)


def _choice_lines(ctx, opening):
    """Списки выбора, которые код задаёт полям: «Список «Поле»: значения»; `opening` — записи открытия либо записи, которые код ставит позже (по действию, при выводе строк)."""
    found, said = collections.OrderedDict(), {}
    for n in ctx.accepted:
        if n["kind"] != "list_content" or bool(n.get("opening", True)) != opening:
            continue
        value = _list_words(mv.safe_text(n["value"], ctx.vars))
        if not value:
            continue
        cond, clear = mv.condition(n["condition"], ctx.vars, n["lines"][0]) if n.get("condition") else ("", True)
        tail = _when(cond)
        found.setdefault(ctx.name(n["target"]), []).append(value + tail)
        said.setdefault(ctx.name(n["target"]), set()).add(n["index"])
    if not found:
        return []
    lines = [f"- Списки выбора, которые задаёт код ({len(found)}):"]
    for name, values in list(found.items())[:LISTS_SHOWN]:
        ctx.said |= said[name]
        lines.append(f"  - {name}: " + "; ".join(dict.fromkeys(values)))
    if len(found) > LISTS_SHOWN:
        lines.append(f"  - ещё {len(found) - LISTS_SHOWN}: `brief --detail code`")
    return lines


def _look_lines(ctx):
    """Оформление, которое код задаёт не при открытии, а при выводе строк и по действию: цвет, шрифт, текст ячеек; по цели одна строка."""
    by, said = collections.OrderedDict(), {}
    for n in ctx.accepted:
        if n["kind"] != "appearance" or n.get("opening", True):
            continue
        value = _cap(mv.safe_text(n["value"], ctx.vars), 200)
        if not value:
            continue
        cond, clear = mv.condition(n["condition"], ctx.vars, n["lines"][0]) if n.get("condition") else ("", True)
        by.setdefault(ctx.name(n["target"]), []).append(value + _when(cond))
        said.setdefault(ctx.name(n["target"]), set()).add(n["index"])
    if not by:
        return []
    lines = []
    for name, values in list(by.items())[:LOOKS_SHOWN]:
        ctx.said |= said[name]
        label = name if name.startswith(("колонка", "страница", "кнопка", "панель", "таблица", "форма")) else f"«{name}»"
        lines.append(f"- {label}: оформление — " + "; ".join(dict.fromkeys(values)))
    if len(by) > LOOKS_SHOWN:
        lines.append(f"- Оформление ещё у {len(by) - LOOKS_SHOWN}: `brief --detail code`")
    return lines


def _title_in_head(ctx, note):
    """Условный заголовок окна, который «Что это за форма» уже называет вместе с условием (`form_title`): в «Зависит от условий» не повторяется; без слов заголовка (задаёт код) условие остаётся здесь."""
    return bool(mv.title_words(note["value"], ctx.vars))


def _said_with_pages(ctx, note, page_marks):
    """Условие видимости страницы, которое уже названо в перечне «Страницы, которых нет на `clean.png`» (слова те же, что у страницы в `page_marks`): второй раз в «Зависит от условий» не повторяется."""
    target = note["target"]
    if note["kind"] != "visibility" or target["kind"] != "page" or not page_marks:
        return False
    rows = [r for r in (ctx.brief.get("images") or {}).get("code_pages") or [] if not r.get("same_as_clean")]
    pages = (ctx.brief.get("structure") or {}).get("pages") or []
    for r in rows:
        if r["panel"] == target.get("element") and (r["panel"], r["caption"].casefold()) in page_marks:
            page = next((p for p in pages if p.get("node") == r["node"]), None)
            if page and str(page.get("code_page") or "").casefold() == str(target.get("sub") or "").casefold():
                ctx.said.add(note["index"])
                return True
    return False


def _page_lines(ctx, page_marks):
    """Страницы, которых нет на `clean.png`, но которые меняет код: картинки досье и команда для остальных; страница, чья картинка не отличается от `clean.png`, не перечисляется."""
    rows = [r for r in (ctx.brief.get("images") or {}).get("code_pages") or [] if not r.get("same_as_clean")]
    if not rows:
        return []
    lines = ["- Страницы, которых нет на `clean.png`, но которые меняет код:"]
    groups = collections.OrderedDict()
    for r in rows:
        panel = (r["panel"] or "форма").split("/")[-1]
        words = (page_marks or {}).get((r["panel"], r["caption"].casefold())) or r["why"]
        groups.setdefault((r["panel"], panel, words), []).append(r)          # страницы одной панели с одними и теми же словами — одной строкой
    for (holder, panel, words), items in groups.items():
        pages = ", ".join(f"«{r['caption']}»" + (f" (`{r['file']}`)" if r.get("file") else f" (картинка та же, что у «{r['same_as_page']}»)" if r.get("same_as_page") else "") for r in items)
        shown = " (на картинке нарисована как при показе)" if any(r.get("when_shown") for r in items) else ""
        lines.append(f"  - {'страница' if len(items) == 1 else 'страницы'} {pages} {'панели «' + panel + '»' if holder else 'формы'}: {words}{shown}")
    rest = [r for r in rows if not r.get("file") and not r.get("same_as_page") and not r.get("unreachable")]
    if rest:
        r = rest[0]
        name = (r["panel"] or "форма").split("/")[-1]
        lines.append(f"  - страницы без картинки открывает команда: `frm_json.py render <форма> --shown '{name}={r['caption'] if r['panel'] else r['at']}'`")
    return lines


def _value_line(ctx, notes, label="Значения полей при открытии"):
    """Строка «Значения полей при открытии» (у полей с условной записью, когда литерал даёт тело модуля объекта, — «При первом открытии»): безусловные значения данных, которые код ставит полям, — флажки по включённости, остальные поля с их значением."""
    checks, others = {True: [], False: []}, collections.OrderedDict()
    by_name = _by_name(ctx, notes)
    for n in notes:
        name = ctx.name(n["target"])
        found = effects_mod.value_of(n["value"])
        if ctx.types().get(n["target"]["element"]) == "CheckBox" and found and found[0] == "bool":
            checks[found[1]].append(name)
        else:
            others.setdefault(ctx.value_words(n["value"], n["target"]["element"], n.get("why")), []).append(name)

    def wrap(text):
        return text if text.startswith(("колонк", "кнопка", "страница", "панель", "таблица")) else f"«{text}»"
    parts = []
    for flag, word in ((True, "включены"), (False, "сняты")):
        names = checks[flag]
        if names:
            parts.append(f"{'флажок' if len(names) == 1 else 'флажки'} {_listed(ctx, names, by_name, HEAD_NAMES, wrap)} — {word[:-1] if len(names) == 1 else word}")
    for words, names in others.items():
        parts.append(f"{_listed(ctx, names, by_name, HEAD_NAMES, wrap)} — {words}")
    return f"- {label}: " + "; ".join(parts) + "." if parts else None


def _same_as_file(ctx, note):
    """Безусловная запись, после которой экран такой же, как нарисован по файлу: `Видимость = Истина` у элемента или колонки, видимых в файле. `Доступность = Истина` сюда не входит: рядом
    цикл или условная запись могли закрыть ту же цель, и безусловное «доступен» — исключение из них."""
    value = LITERALS.get(note["value"].strip())
    if value is not True or note["kind"] != "visibility":
        return False
    target = note["target"]
    structure = ctx.brief.get("structure") or {}
    if target["kind"] == "element":
        return target["element"] not in set(structure.get("hidden") or ())
    if target["kind"] == "column":
        for table in structure.get("tables") or ():
            if table["element"] == target.get("element"):
                return all(c["visible"] for c in table["columns"] if c["name"] == target.get("sub"))
    return False


def _in_headline(note):
    """Безусловная запись, о которой уже сказала первая строка раздела (`_headline`)."""
    value = LITERALS.get(note["value"].strip())
    kind = note["kind"]
    return ((kind in ("visibility", "enabled") and value is False) or (kind == "read_only" and note["target"]["kind"] == "form" and value is not False)
            or (kind == "title" and note["target"]["kind"] == "form") or kind == "current_page")


def _fixed_words(ctx, fixed):
    """Безусловное состояние: что скрыто, недоступно, только просмотр, какие страницы и заголовок."""
    by = collections.OrderedDict()
    for name, phrases in _phrases(ctx, fixed).items():
        for text in phrases:
            by.setdefault(text, [])
            if name not in by[text]:
                by[text].append(name)
    by_name = _by_name(ctx, fixed)
    return "; ".join(f"{_listed(ctx, names, by_name, 5)} — {text}" for text, names in by.items())


def _drawn(ctx, rows):
    """Чем `clean.png` отличается от открытой формы, когда это не очевидно: режим «только просмотр» формы на картинке не выделяется. Условное нарисовано как в файле — об этом говорит шапка досье."""
    read_only = any(n["kind"] == "read_only" and n["target"]["kind"] == "form" and LITERALS.get(n["value"].strip()) is not False and _fixed(ctx, n) for n in rows)
    collapse = any(n["kind"] == "collapse" and not (n["value"].strip() in effects_mod.COLLAPSED_MODES and _fixed(ctx, n)) for n in rows)
    lists = {n["target"].get("element") for n in ctx.accepted if n["kind"] == "list_content"}
    combos = list(dict.fromkeys(ctx.short(n["target"]["element"]) for n in rows if n["kind"] == "value" and _fixed(ctx, n) and ctx.types().get(n["target"].get("element")) == "ComboBox"
                                and n["target"].get("element") in lists))
    notes = (["режим «только просмотр» формы не выделяется: поля нарисованы как в файле"] * read_only + ["свёртка панелей по условию не показана: панели нарисованы как в файле"] * collapse
             + ([f"значение поля выбора не нарисовано, пока его нет в списке выбора файла (список задаёт код): {', '.join('«' + c + '»' for c in combos)}"] if combos else []))
    return "- На `clean.png` " + "; ".join(notes) + "." if notes else None


# ── Что делает код ──

def _later(ctx):
    """Заголовок окна, который код меняет не при открытии, а по действию или по таймеру: слова либо `None`."""
    notes = [n for n in ctx.accepted if n["kind"] == "title" and n["target"]["kind"] == "form" and not n.get("opening", True)]
    if not notes:
        return None
    parts = []
    for n in notes:
        text, cond, form = ctx.state(n)
        parts.append(text[len("заголовок "):] + (f" — {cond}" if cond else ""))
    return "Заголовок окна позже меняется (по действию или по таймеру): " + _cap("; ".join(dict.fromkeys(parts)), 360)


def _rank(ctx, ev):
    """Важность события для пользователя: кнопки командной панели формы, потом поля и кнопки вложенных панелей, потом таблицы, потом события формы."""
    source = ev["source"]
    if source == "форма":
        return 3
    parts = source.split("/")
    types = ctx.types()
    if any(types.get("/".join(parts[:i])) == "TableBox" for i in range(1, len(parts) + 1)):
        return 2
    if ev["event"] == "действие кнопки":
        return 0 if len(parts) <= 2 else 1
    return 1


def _screen(e):
    """Эффект меняет экран: вид эффекта экранный (с приёмником или словами), либо `other` со словами о видимом (не «помечает форму изменённой»)."""
    if e["what"] in SCREEN_WHAT:
        return bool(e["affects"] or e["text"])
    return e["what"] == "other" and bool(e["text"]) and not NOISE.search(e["text"])


def _event_texts(ctx, ev):
    """Слова эффектов события одной строкой каждый: видимые первыми, запись данных и служебное — после; одинаковые склеены."""
    quiet_effects = [e for e in ev["effects"] if not _screen(e) and e["text"] and not NOISE.search(e["text"])]
    return list(dict.fromkeys(t for t in (ctx.effect_text(e, cap=None) for e in [e for e in ev["effects"] if _screen(e)] + quiet_effects) if t))


def _action_groups(ctx, rows, words):
    """`[(ранг, [строки])]`: частности по важности для пользователя; события с одной и той же реакцией (два и больше) сведены в одну строку."""
    buckets = collections.OrderedDict()
    for ev in rows:
        cond, clear = mv.condition(ev["condition"], ctx.vars, ev["lines"][0])
        texts = _event_texts(ctx, ev)
        tail = _when(cond) if cond and clear and cond.casefold() not in " ".join(texts).casefold() else ""          # условие, которое уже сказано в тексте эффекта, не повторяется
        button = ev["event"] == "действие кнопки"
        key = (button, tuple(texts), tail, ev["source"].rsplit("/", 1)[0] if button else "")
        buckets.setdefault(key, []).append((ev, texts, tail))
    out = []
    for (button, texts, tail, panel), items in buckets.items():
        sources = list(dict.fromkeys(ev["source"] for ev, _t, _tl in items))
        if len(sources) >= 2 or (not button and len(items) >= 2):
            if button:
                captions = [words.button.get(src) or src.split("/")[-1] for src in sources]
                shown = [f"«{c}»" + (f" ({src.split('/')[-1]})" if captions.count(c) > 1 else "") for c, src in list(zip(captions, sources))[:3]]          # одинаковые подписи — с именами
                names = ", ".join(shown) + (", …" if len(sources) > 3 else "")
                head = f"{counted(len(sources), 'кнопка', 'кнопки', 'кнопок')} панели «{panel.split('/')[-1]}» ({names})" if panel else f"{counted(len(sources), 'кнопка', 'кнопки', 'кнопок')} ({names})"
            elif len(sources) == 1:
                head = f"«{sources[0].split('/')[-1]}» ({', '.join(dict.fromkeys(str(ev['event']) for ev, _t, _tl in items))})"
            else:
                head = f"{counted(len(items), 'событие', 'события', 'событий')}: " + ", ".join(f"«{ev['source'].split('/')[-1]}» ({ev['event']})" for ev, _t, _tl in items[:3]) + (", …" if len(items) > 3 else "")
            ev0 = items[0][0]
            lines = [f"- {head}: {texts[0]}{tail}"] if len(texts) == 1 else [f"- {head}{tail}:"] + [f"  - {t}" for t in texts]
            out.append((_rank(ctx, ev0), lines))
            continue
        for ev, texts_, tail_ in items:
            head = words.source(ev)
            lines = [f"- {head}: {texts_[0]}{tail_}"] if len(texts_) == 1 else [f"- {head}{tail_}:"] + [f"  - {t}" for t in texts_]
            out.append((_rank(ctx, ev), lines))
    out.sort(key=lambda row: row[0])          # сортировка устойчива: внутри ранга порядок модуля
    return out


def actions_lines(ctx):
    """Раздел «Что делает код»: только частности — действие или событие → что меняется на экране (видимое первым, одинаковые реакции в одной строке); обычное сведено в строку «Остальное — как обычно»."""
    if not has_sections(ctx):
        return []
    lines = ["## Что делает код", ""]
    module = ctx.module
    if not module["present"]:
        kinds = _handler_kinds(module)
        lines.append("Какие действия пользователя что меняют на экране, неизвестно: модуль формы не получен." + (f" Назначены обработчики: {kinds}." if kinds else ""))
        return lines + [""]
    events = [e for e in module.get("events") or [] if not (e["source"] == "форма" and str(e["event"]).casefold() in OPEN_EVENTS)]
    screen = [ev for ev in events if any(_screen(e) for e in ev["effects"])]
    quiet = [ev for ev in events if ev not in screen]
    words = usual.Words(ctx)
    particular, counts = usual.split(ctx, screen, words)
    defaults, procedures, read = usual.defaults_of(ctx), usual.procedures_of(ctx), usual.read_by_conditions(ctx)
    for ev in quiet:
        cat = usual.category(ctx, ev, words, defaults, procedures, read) or usual.QUIET
        counts[cat] = counts.get(cat, 0) + 1
    for cat, number in usual.silent_split(ctx, events).items():
        counts[cat] = counts.get(cat, 0) + number
    for _rank_, group in _action_groups(ctx, particular, words):
        lines += group
    lines += _shadow_lines(ctx, words)
    made = _made(ctx)
    if made:
        lines.append("- " + made)
    later = _later(ctx)
    if later:
        lines.append("- " + later)
    lines += _refresh_lines(ctx) + _look_lines(ctx) + _choice_lines(ctx, opening=False) + _timer_lines(ctx, opening=False)
    by_why = collections.OrderedDict()
    for target, why in _others(ctx, element_level=True)[:5]:
        by_why.setdefault(why, []).append(target)
    for why, targets in by_why.items():
        lines.append(f"- {', '.join(dict.fromkeys(targets))}: {why}")
    lines += _form_others(ctx, opening=False)
    rest = usual.rest_line(counts, usual.write_words(ctx))
    if rest:
        lines.append(rest)
    if len(lines) == 2:
        lines.append("По разбору код ничего не меняет на экране.")
    elif not rest:
        lines += ["", "Условия, строки модуля и все обработчики — `brief --detail code`."]
    return lines + [""]


EXPR_KINDS = frozenset({"visibility", "enabled", "read_only", "checked", "value"})      # виды записей, у которых value — выражение кода, а не слова модели
INPUT_TYPES = frozenset({"TextBox", "CheckBox", "ComboBox", "RadioButton"})      # поля, правку которых платформа сообщает форме


def _refresh_lines(ctx):
    """«После правки поля «X» пересчитывается: …»: записи на пути от `ОбновлениеОтображения`, чьё условие или выражение называет поле формы (по имени, подписи или данным: слово в «ёлочках» условия или имя в
    выражении значения); платформа вызывает событие после каждого изменения данных, поэтому цели меняются сразу, а не только при открытии."""
    fields = collections.OrderedDict()
    for e in (ctx.brief.get("structure") or {}).get("elements", ()):
        if e["type"] not in INPUT_TYPES:
            continue
        data = re.sub(r"^реквизит (?:формы|объекта)\s+", "", e.get("data") or "")
        short = e.get("short") or e["element"].split("/")[-1]
        for key in (short, e.get("caption"), data):
            if key and len(key) >= 3:
                fields.setdefault(key.casefold(), short)
    by_source = collections.OrderedDict()
    for n in ctx.accepted:
        if not _refreshed(n) or n["kind"] not in OPEN_KINDS or _fixed(ctx, n) and n["kind"] != "value":
            continue
        words = {w.casefold() for w in re.findall(r"«([^»]+)»", n["condition"])} | ({w.casefold() for w in re.findall(mv.NAME, n["value"])} if n["kind"] in EXPR_KINDS else set())          # слова условия — только в «ёлочках», имена в значении — только у выражений: проза называет понятия, а не поля
        target = _note_name(ctx, n)
        for word in words:
            source = fields.get(word)
            if source and source.casefold() != target.casefold():
                by_source.setdefault(source, [])
                if target not in by_source[source]:
                    by_source[source].append(target)
    return [f"- После правки «{source}» пересчитывается (ОбновлениеОтображения): {_cap(', '.join(targets[:6]) + (f' и ещё {len(targets) - 6}' if len(targets) > 6 else ''), 300)}"
            for source, targets in by_source.items()]


NAMELESS = {"page": ("закладка", "панели"), "button": ("кнопка", "панели"), "column": ("колонка", "таблицы"), "element": ("элемент", "формы")}      # что создаёт код, когда имя вычисляет выражение


def _made_phrase(ctx, n):
    """`(ключ группы, слова, где)` записи `created`/`removed`; запись с `name_expr` — словами модели и без выражения: имя вычисляет код, на форме его нет."""
    t = n["target"]
    value = mv.literal(n["value"].strip()) or n["value"].strip()
    value = mv.scrub(value, ctx.vars) if value else ""
    if n.get("name_expr"):
        noun, holder = NAMELESS[t["kind"]]
        what = _cap(value, 60) if value else noun
        cond, clear = mv.condition(n["condition"], ctx.vars, n["lines"][0]) if n.get("condition") else ("", True)
        tail = f" ({'' if clear else 'условие: '}{cond})" if cond else ""
        place = ctx.short(t["element"]) if t.get("element") else None
        return (what, tail), what + tail, place
    what = ctx.name(t) or "элемент, имя которого вычисляет код"
    if value and value not in what:
        what = f"{_cap(value, 50)} в «{ctx.short(t['element'])}»" if t.get("element") and t["kind"] == "element" else f"{what} ({_cap(value, 50)})"
    cond, clear = mv.condition(n["condition"], ctx.vars, n["lines"][0]) if n.get("condition") else ("", True)
    tail = (f" ({'' if clear else 'условие: '}{cond})" if cond else "") + (" — при открытии на экране её нет" if t["kind"] == "button" and t.get("element") and usual.Words(ctx).hidden(t["element"]) else "")
    return (what, tail), what + tail, None


def _shadow_lines(ctx, words):
    """Что код ставит по действию пользователя там, где при открытии итог другой: записи, которые при открытии перекрыты (`split_overridden`), — у события своего обработчика."""
    _rows, shadowed = opening_rows(ctx)
    if not shadowed:
        return []
    owner = {}
    for (source, event), proc in usual.procedures_of(ctx).items():
        owner.setdefault(proc.casefold(), []).append({"source": source, "event": event})
    by_proc = collections.OrderedDict()
    for n in shadowed:
        by_proc.setdefault(usual.procedure_at(ctx, n["lines"][0]) or "", []).append(n)
    out = []
    for proc, notes in by_proc.items():
        events = owner.get(proc.casefold(), [])
        label = words.source(events[0]) if events else (f"процедура «{proc}»" if proc else "код")
        if len(events) > 1:
            label += f" и ещё {len(events) - 1}"
        parts = []
        by_name = _by_name(ctx, notes)
        for names, phrase in _pairs(ctx, notes):
            parts.append(f"{_listed(ctx, names, by_name, 3)}: {phrase}")
        by_action = any(not (e["source"] == "форма" and str(e["event"]).casefold() in OPEN_EVENTS) for e in events)          # обработчик открытия действием пользователя не бывает
        out.append(f"- {label}, " + ("по действию (при открытии это перекрыто)" if by_action else "при открытии перекрыто позднейшей записью") + ": " + "; ".join(parts))
    return list(dict.fromkeys(out))          # без предела: запись, спрятанная за «ещё N таких мест», из обзора пропадала


FORM_OTHERS = 10           # записей `other` о форме целиком в «Что делает код»


def _form_others(ctx, opening=False):
    """Записи `other` с целью-формой, которые форма не делает сама: то, что код строит и ставит в форме (созданное по данным, привязки, колонки); слова модели, одинаковые склеены. Граф вызовов
    решает, где они стоят: выполняются при открытии (`opening`) — в «При открытии», иначе в «Что делает код»; по таймеру и действию — в «Что это за форма» (`form_purpose`)."""
    texts = list(dict.fromkeys(why for _target, why in _others(ctx, element_level=False, opening=opening) if why))
    if not texts:
        return []
    lines = ["- Ещё код делает с формой" + (" при открытии" if opening else "") + ":"] + [f"  - {t}" for t in texts[:FORM_OTHERS]]
    if len(texts) > FORM_OTHERS:
        lines.append(f"  - ещё {len(texts) - FORM_OTHERS}: `brief --detail code`")
    return lines


def _clears(note):
    """Запись `removed` о кнопках целиком: `Кнопки.Очистить()` у панели или у подменю — кнопки пропали, а сама панель или подменю остались."""
    return note["kind"] == "removed" and note["target"]["kind"] in ("button", "element") and note["value"].strip().casefold().startswith(CLEAR_WORDS)


def _clear_phrase(ctx, n):
    """`(ключ, слова, где)` записи об очистке кнопок: «подменю «X» панели «Y»» либо «панель «Y»»."""
    t = n["target"]
    what = f"подменю «{t['sub']}» панели «{ctx.short(t['element'])}»" if t["kind"] == "button" and t.get("sub") else f"панель «{ctx.short(t['element'])}»" if t.get("element") else "кнопки"
    return (what, ""), what, None


def _made(ctx, opening=False):
    """Что код создаёт, убирает и очищает при открытии (`opening`, раздел «При открытии», с условием) либо позже: один раз, без повтора строк эффектов; созданное по данным (имя вычисляет код) сведено по словам модели и условию, держатели — списком. Очистка кнопок
    называется очисткой: само подменю или панель остаются."""
    bits = []
    for title, kind, clear in (("создаёт", "created", False), ("убирает", "removed", False), ("очищает кнопки", "removed", True)):
        seen = collections.OrderedDict()
        for n in ctx.accepted:
            if n["kind"] != kind or (kind == "removed" and _clears(n) != clear) or bool(n.get("opening", True)) != opening:
                continue
            key, text, place = _clear_phrase(ctx, n) if clear else _made_phrase(ctx, n)
            ctx.said.add(n["index"])
            places = seen.setdefault(key, [text, []])[1]
            if place and place not in places:
                places.append(place)
        words = []
        for text, places in seen.values():
            where = f" в «{'», «'.join(places[:3])}»" + (f" и ещё {len(places) - 3}" if len(places) > 3 else "") if places else ""
            words.append(text.replace(" (", where + " (", 1) if where and " (" in text else text + where)
        if words:
            bits.append(f"{title}: " + ", ".join(words))
    return "; ".join(bits)


def _others(ctx, element_level, opening=None):
    """Записи `other`: цели-элемента (`element_level` истинно) или формы целиком (ложно): `[(цель, слова)]` без учётных данных и переменных модуля. У формы целиком `opening` отбирает
    выполняемые при открытии (истина) либо остальные (ложь)."""
    out = []
    for o in ctx.code.get("others") or []:
        is_form = o["target"]["kind"] == "form"
        if is_form == element_level or (is_form and o.get("form_work")):
            continue          # запись, которую форма делает сама по таймеру или действию, идёт в «Что это за форма» (`form_purpose`)
        if is_form and opening is not None and bool(o.get("opening", True)) != opening:
            continue
        why = _cap(mv.safe_text(o["why"], ctx.vars), 220)
        if why and not re.search(r"на экран не влияет|не влияет на экран", why):
            out.append((ctx.name(o["target"]), why))
    return out


def form_title(ctx, file_title):
    """Заголовок окна словами для «Что это за форма»: если код ставит заголовок при открытии — «задаёт код (текст из кода); в файле — «…»», иначе заголовок из файла (или пусто)."""
    notes = [n for n in ctx.accepted if n["kind"] == "title" and n["target"]["kind"] == "form" and n.get("opening", True)]
    ctx.said.update(n["index"] for n in notes)
    if not notes:
        return f"заголовок окна «{file_title}»" if file_title else ""
    shown = []
    for n in notes:
        words = mv.title_words(n["value"], ctx.vars)
        if words:
            _text, cond, form = ctx.state(n)
            shown.append(words + (_when(cond) if cond and form in ("expr", "clear") else ""))
    shown = list(dict.fromkeys(shown))
    text = "заголовок окна задаёт код" + (f" ({'; '.join(shown[:2])})" if shown else "")
    return text + (f"; в файле — «{file_title}»" if file_title and f"«{file_title}»" not in shown else "")


def form_purpose(ctx):
    """Слова модели о том, что форма делает сама и что видно пользователю: записи `other` с целью-формой и пометкой `form_work`; прочие записи не берутся."""
    if not ctx.parsed:
        return []
    out = []
    for o in ctx.code.get("others") or []:
        if o["target"]["kind"] == "form" and o.get("form_work"):
            why = mv.safe_text(o["why"], ctx.vars)
            if why:
                out.append(why)
    return out
