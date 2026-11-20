"""Факты о коде модуля, которые не зависят от свойств элементов: обращения к элементам, которых на форме нет, и обработчики без процедуры.

`missing_refs(module_text, names, elements)` — обращения `ЭлементыФормы.<Имя>` (и `ЭлементыФормы["Имя"]`, `ЭлементыФормы.Найти("Имя")`) к имени, которого на форме
нет: `[{name, how, procedure, line, lines, text, cond, in_try, last, callers, candidates}]` по одной записи на имя и процедуру. У каждого — строка первого
обращения и её текст, условие `Если`, в котором оно стоит, признак «внутри Попытки», последняя строка процедуры (до неё строки не выполнятся, если ошибка не перехвачена),
процедуры модуля, которые её вызывают, и кандидаты — элементы формы, похожие по имени или подписи (по сходству слов, а не утверждение).

`missing_handlers(handlers, module_text)` — обработчики элементов, формы и кнопок панелей, чьей процедуры в модуле нет: `[{element, event, procedure, owner, commented, line}]`;
`commented` — процедура в модуле есть, но закомментирована.

`facts(missing, handlers)` — два вида фактов раздела «Факты для оценки»: `code_missing` и `handler_missing`; слова — без оценок и без советов об операциях.
Модуль читается по строкам без комментариев и без текста литералов (`brief.modulescan.scan`); вызовы методов и динамические имена не ищутся.
"""
import collections
import difflib
import re

from . import modulescan as scan, vocab

_NAME = r"[\wА-Яа-яЁё]+"
REF = re.compile(rf"(?<![\w.])(?:ЭтаФорма\s*\.\s*)?ЭлементыФормы\s*\.\s*(?P<el>{_NAME})(?:\s*\.\s*(?P<part>Страницы|Кнопки|Колонки)\s*\.\s*(?P<sub>{_NAME}))?", re.I)
BY_STRING = re.compile(r'(?<![\w.])(?:ЭтаФорма\s*\.\s*)?ЭлементыФормы\s*(?:\[\s*"(?P<s1>[^"]+)"\s*\]|\.\s*Найти\s*\(\s*"(?P<s2>[^"]+)"\s*\))', re.I)
COLLECTION_METHODS = vocab.PART_METHODS      # `ЭлементыФормы.Найти(…)`, `ЭлементыФормы.Добавить(…)` — обращение к коллекции, а не к элементу (те же слова, что у `Кнопки.Удалить`)
_TRY = re.compile(r"^\s*Попытка\b", re.I)
_EXCEPT = re.compile(r"^\s*Исключение\b", re.I)
_END_TRY = re.compile(r"^\s*КонецПопытки\b", re.I)
_COMMENTED = "//"
TEXT_CHARS = 100           # знаков строки кода в слове факта
CANDIDATES = 3             # кандидатов называется не больше
NAME_RATIO = 0.75          # сходство имён по `difflib`, с которого имя — кандидат
PREFIXES = {"надпись": "Label", "поле": "TextBox", "кнопка": "Button", "флажок": "CheckBox", "переключатель": "RadioButton", "панель": "Panel",
            "таблица": "TableBox", "рамка": "GroupBox", "картинка": "PictureBox", "разделитель": "Splitter"}   # слово в начале имени → вид элемента
_WORD = re.compile(r"[А-ЯЁA-Z]?[а-яёa-z]+|[А-ЯЁA-Z]+(?![а-яёa-z])|\d+")


def _words(name):
    """Слова имени по границам регистра: `ПодписьАльфа` → `[подпись, альфа]`."""
    return [w.casefold() for w in _WORD.findall(name)]


def _caption_words(text):
    return [w.casefold() for w in re.findall(r"[\wА-Яа-яЁё]+", text or "")]


def candidates(name, elements):
    """Элементы формы, похожие на отсутствующее имя: по тому же слову в имени, по близкому имени и по подписи (подпись из первых букв слова имени: «ч.» ↔ `УстаревшаяНадпись`).
    Вид, названный приставкой имени (`Надпись…`, `Поле…`), должен совпасть. `[{short, type, caption, why}]`, лучшие первыми, не больше `CANDIDATES`."""
    words = _words(name)
    kind = PREFIXES.get(words[0]) if len(words) > 1 else None
    rest = words[1:] if kind else words
    found = []
    for row in elements:
        short = row.get("short")
        if not short or short.casefold() == name.casefold():
            continue
        if kind and row.get("type") != kind:
            continue
        have = _words(short)
        have = have[1:] if len(have) > 1 and PREFIXES.get(have[0]) else have
        caption = _caption_words(row.get("caption"))
        why = None
        score = 0.0
        shared = [w for w in rest if len(w) >= 3 and w in have]
        ratio = difflib.SequenceMatcher(None, "".join(rest), "".join(have)).ratio() if rest and have else 0.0       # без приставки вида: `Надпись…` у всех одна
        if ratio >= NAME_RATIO:
            why, score = f"имя близко к «{name}»", ratio
        elif shared:
            why, score = f"в имени то же слово «{shared[0]}»", 0.5 + 0.05 * len(shared[0])
        else:
            # подпись — начало слова имени: «а.» и «б.» у `ПодписьАльфа` и `ПодписьБета`; одно слово подписи, не длиннее трёх знаков
            if len(caption) == 1 and len(caption[0]) <= 3 and any(w.startswith(caption[0]) for w in rest):
                why, score = f"подпись «{row.get('caption')}» — начало слова «{next(w for w in rest if w.startswith(caption[0]))}» из имени", 0.6
            elif any(len(w) >= 3 and w in caption for w in rest):
                why, score = "то же слово в подписи", 0.55
        if why:
            found.append((score, row, why))
    found.sort(key=lambda t: (-t[0], t[1].get("short", "")))
    return [{"short": r["short"], "type": r.get("type"), "caption": r.get("caption") or "", "why": why} for _s, r, why in found[:CANDIDATES]]


def _state(lines):
    """`{номер строки: внутри Попытки}` — строка стоит между `Попытка` и `Исключение` (блок `Исключение` ошибку не перехватывает); счёт сбрасывается на границе процедуры."""
    out, depth = {}, 0
    for number, masked, _raw in lines:
        if scan._HEAD.match(masked):
            depth = 0
        out[number] = depth > 0
        if _TRY.match(masked):
            depth += 1
            out[number] = True
        elif _EXCEPT.match(masked) and depth:
            depth -= 1
            out[number] = False
        elif _END_TRY.match(masked) and depth:
            depth -= 1
    return out


def _callers(lines, procs, target):
    """Процедуры модуля, в чьём теле есть вызов `target(…)`, кроме самой `target`."""
    call = re.compile(rf"(?<![\w.]){re.escape(target)}\s*\(", re.I)
    out = []
    for number, masked, _raw in lines:
        if call.search(masked):
            who = scan._procedure_at(procs, number)
            if who and who.casefold() != target.casefold() and who not in out and not _is_header(masked):
                out.append(who)
    return out


def _is_header(masked):
    return bool(scan._HEAD.match(masked))


def missing_refs(module_text, names, elements=()):
    """Обращения к элементам, которых на форме нет; см. описание модуля. `names` — `brief.facts._Names`; `elements` — строки таблицы элементов формы (`short`, `type`, `caption`)."""
    if module_text is None:
        return []
    from . import module_effects as module
    known = module.label_map(names)
    lines = scan.scan(module_text)
    procs = scan.procedures_of(lines)
    cond = scan.conditions(lines)
    trying = _state(lines)
    last_of = {name: (last if last is not None else first) for name, _p, first, last in procs}
    found = collections.OrderedDict()
    for number, masked, raw in lines:
        hits = []
        for hit in REF.finditer(masked):
            if hit.group("el").casefold() in COLLECTION_METHODS:
                continue
            hits.append((hit.group("el"), "имя"))
        for hit in BY_STRING.finditer(raw):
            hits.append((hit.group("s1") or hit.group("s2"), "строка"))
        for label, how in hits:
            if known.get(label.casefold()):
                continue
            proc = scan._procedure_at(procs, number)
            entry = found.setdefault((label.casefold(), proc), {
                "name": label, "how": how, "procedure": proc, "line": number, "lines": [], "text": scan.shorten(raw.strip(), TEXT_CHARS),
                "cond": cond.get(number), "in_try": trying.get(number, False), "last": last_of.get(proc), "callers": [], "candidates": []})
            entry["lines"].append(number)
    for entry in found.values():
        if entry["procedure"]:
            entry["callers"] = _callers(lines, procs, entry["procedure"])
        entry["candidates"] = candidates(entry["name"], elements)
    return list(found.values())


PART_WORDS = {"колонки": "колонка таблицы", "кнопки": "кнопка панели", "страницы": "страница панели"}


def _holder_of(note):
    """Чья часть отсутствует — по цитате записи: `ЭлементыФормы.Таблица.Колонки.Имя` → «колонка таблицы «Таблица»»; без такого обращения — `None`."""
    found = re.search(rf"ЭлементыФормы\s*\.\s*(?P<holder>{_NAME})\s*\.\s*(?P<part>Колонки|Кнопки|Страницы)\s*\.", note.get("quote") or "", re.I)
    return f"{PART_WORDS[found.group('part').casefold()]} «{found.group('holder')}»" if found else None


def noted_refs(module_text, notes, found):
    """Обращения к отсутствующему, которые прочитала модель и принял разбор (`code.missing`: колонка, кнопка, страница — `ЭлементыФормы.Таблица.Колонки.Имя`), но прямой поиск `missing_refs`
    не нашёл: те же записи (`how` — «запись разбора»), по одной на имя и процедуру. Условие — слова записи; «внутри Попытки» и последняя строка процедуры — по тексту модуля. `found` — результат
    `missing_refs`: имя, уже названное им в этой процедуре, не повторяется."""
    if module_text is None or not notes:
        return []
    lines = scan.scan(module_text)
    procs = scan.procedures_of(lines)
    trying = _state(lines)
    last_of = {name: (last if last is not None else first) for name, _p, first, last in procs}
    raw_at = {number: raw for number, _masked, raw in lines}
    have = {(m["name"].casefold(), m["procedure"]) for m in found}
    out = collections.OrderedDict()
    for note in notes:
        number = note["lines"][0]
        proc = scan._procedure_at(procs, number)
        key = (note["name"].casefold(), proc)
        if key in have:
            continue
        entry = out.setdefault(key, {"name": note["name"], "how": "запись разбора", "where": _holder_of(note), "procedure": proc, "line": number, "lines": [], "text": scan.shorten(raw_at.get(number, "").strip(), TEXT_CHARS),
                                     "cond": note.get("condition") or None, "in_try": trying.get(number, False), "last": last_of.get(proc), "callers": [], "candidates": []})
        if number not in entry["lines"]:
            entry["lines"].append(number)
    for entry in out.values():
        if entry["procedure"]:
            entry["callers"] = _callers(lines, procs, entry["procedure"])
    return list(out.values())


def missing_handlers(handlers, module_text):
    """Обработчики, чьей процедуры в модуле нет (строки `handlers` — `brief.handlers` после `_module_section`: `found` ложно)."""
    if module_text is None:
        return []
    if isinstance(module_text, (bytes, bytearray)):
        module_text = bytes(module_text).decode("utf-8", errors="replace")
    text = module_text.lstrip("﻿").splitlines()
    out = []
    for row in handlers:
        if row.get("found") is not False:
            continue
        name = row["procedure"]
        head = re.compile(rf"^\s*{re.escape(_COMMENTED)}+\s*(?:Процедура|Функция)\s+{re.escape(name)}\s*\(", re.I)
        at = next((n for n, line in enumerate(text, 1) if head.match(line)), None)
        out.append({"element": row.get("element"), "event": row["event"], "procedure": name, "owner": row["owner"], "node": row.get("node"),
                    "commented": at is not None, "line": at})
    return out


def missing_words(m):
    """Слова факта об обращении к несуществующему элементу."""
    where = f"процедура {m['procedure']}, строка {m['line']}" if m["procedure"] else f"вне процедур, строка {m['line']}"
    more = f" (всего обращений в этой процедуре: {len(m['lines'])}; строки {', '.join(map(str, m['lines'][:6]))})" if len(m["lines"]) > 1 else ""
    what = f"элементу «{m['name']}»" + (f" ({m['where']})" if m.get("where") else "")
    parts = [f"код обращается к {what}, которого на форме нет: {where}{more}: `{m['text']}`"]
    if m["in_try"]:
        parts.append("обращение стоит внутри `Попытки`: ошибку перехватывает блок `Исключение`, выполнение продолжается с него")
    else:
        tail = f"строки процедуры после него (до {m['last']}) не выполняются" if m["last"] and m["last"] > m["line"] else "процедура на этом обращении прерывается"
        cond = f"; обращение стоит под условием «{m['cond']}», без него ошибки нет" if m["cond"] else ""
        parts.append(f"при выполнении этой строки возникает ошибка времени выполнения (на этой форме в предприятии не проверялось), {tail} и вызывающая процедура, "
                     f"если ошибку не перехватывают{cond}")
    if m["callers"]:
        parts.append("процедуру вызывают: " + ", ".join(m["callers"]))
    if m["candidates"]:
        parts.append("элементы формы, похожие по смыслу (по сходству слов, а не утверждение): " + "; ".join(
            f"«{c['short']}» ({c['type']}" + (f", подпись «{c['caption']}»" if c["caption"] else "") + f"; {c['why']})" for c in m["candidates"]))
    return "; ".join(parts)


def handler_words(h):
    """Слова факта об обработчике без процедуры."""
    who = f"«{h['element']}»" if h.get("element") else "формы"
    if h["commented"]:
        said = f"процедура «{h['procedure']}» в модуле закомментирована (строка {h['line']})"
    else:
        said = f"процедуры «{h['procedure']}» в модуле нет"
    return (f"у {who} событие «{h['event']}» назначено процедуре «{h['procedure']}»: {said}; что платформа делает при этом событии, "
            "на этой форме в предприятии не проверялось")


def facts(missing, handlers, Fact, names):
    """`[Fact]` видов `code_missing` и `handler_missing` (`Fact` — `brief.facts.Fact`)."""
    out = []
    for m in missing:
        out.append(Fact("code_missing", None, None, {**{k: m[k] for k in ("name", "how", "procedure", "line", "lines", "text", "cond", "in_try", "last", "callers", "candidates")}, "where": m.get("where")},
                        missing_words(m)))
    for h in handlers:
        element = h.get("element")
        full = element if element in names.structure.by_element else None
        out.append(Fact("handler_missing", names.node(full) if full else h.get("node"), full,
                        {"element": element, "event": h["event"], "procedure": h["procedure"], "owner": h["owner"], "commented": h["commented"], "line": h["line"]},
                        handler_words(h)))
    return out
