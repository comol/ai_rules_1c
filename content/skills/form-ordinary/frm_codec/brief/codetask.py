"""Задание на разбор кода формы: то, что известно точно, и вопросы, на которые отвечает модель (`code-task.md`, заготовка `code-notes.json`).

Код формы разбирает модель по `docs/brief-code.md`; навык готовит для неё только точное — то, что находится поиском, а не догадкой:

* события формы и элементов, действия кнопок и их процедуры — из файла формы;
* карта модуля: процедуры с диапазонами строк, какие из них обработчики, какие процедуры вызывают друг друга (по имени в тексте), тело модуля (код вне процедур —
  выполняется при создании формы, до `ПередОткрытием`), вызовы общих модулей вида
  `<ИмяОбщегоМодуля>.<Процедура>(` — со ссылкой на файл в выгрузке (`--config`), без разбора;
* перечень имён на форме: элементы, страницы панелей, колонки таблиц, кнопки панелей — модель называет в записях то, что есть;
* вопросы (`QUESTIONS`, те же слова стоят в инструкции) и схема записи.

Строки модуля в задании — строки файла `module.bsl`, который лежит в каталоге досье рядом: записи разбора проверяются по нему. Файл пишется с переводами строк `\n`,
а одиночный возврат каретки исходного текста — тоже конец строки (как `str.splitlines()`): номера по `cat -n` исходного `form.bsl` могут разойтись.

Указатель мест, меняющих форму, — строки модуля формы, модуля объекта и процедур общих модулей, где стоят слова из замкнутого словаря (`INDEX_WORDS`, `INDEX_COLLECTIONS`):
номер строки, процедура, текст строки. Это перечень для чтения, а не разбор: в досье ничего не попадает без записи модели.
"""
import collections
import json
import pathlib
import re

from . import codenotes, handler_defaults as hd, modulescan as scan
from .fmt import _list

TASK_FILE = "code-task.md"
NOTES_FILE = "code-notes.json"
MODULE_FILE = "module.bsl"
OBJECT_COPY = "object_module.bsl"          # копия модуля объекта в каталоге досье: те же переводы строк и нумерация, что у `module.bsl`
COMMON_COPIES = "common"                   # каталог копий общих модулей: `common/<Имя модуля>.bsl`
INSTRUCTION = "docs/brief-code.md"
INSTRUCTION_PATH = str(pathlib.Path(__file__).resolve().parents[2] / INSTRUCTION)      # полный путь: задание читают из каталога досье, где `docs/` нет
CALLS_SHOWN = 40         # вызовов общих модулей в задании называется не больше стольких
OWNER_SKIP = frozenset({"этаформа", "элементыформы", "этотобъект", "параметры", "новый"})
OBJECT_OWNER_SKIP = frozenset({"этаформа", "элементыформы", "параметры", "новый"})       # владелец вызова, который объектом формы быть не может (`ЭтотОбъект` и псевдоним — могут)
INDEX_WORDS = ("Видимость", "Доступность", "ТолькоПросмотр", "Заголовок", "ТекущаяСтраница", "ТекущийЭлемент", "ТекущаяКолонка", "Свертка", "Пометка", "СоздатьКолонки",
               "Отказ", "РежимРабочегоСтола", "ОткрытьФорму", "Верх", "Лево", "Ширина", "Высота", "Закрыть")
INDEX_COLLECTIONS = ("Кнопки", "Колонки", "Страницы")          # `Кнопки.<метод>`, `Колонки.<метод>`, `Страницы.<…>`, `Страницы[…]`
INDEX_SHOWN = 600        # строк указателя по модулю формы в задании не больше стольких
INDEX_FOREIGN_SHOWN = 200        # и по каждой процедуре другого файла
INDEX_TEXT = 110         # знаков строки кода в указателе
POINTER_TEXT = 60        # знаков строки указателя, где нет ни присваивания, ни вызова
_WB = r"(?<![\wА-Яа-яЁё])"
_WB_ALIAS = r"(?<![0-9A-Za-zА-Яа-яЁё])"          # перед коллекцией допустимо подчёркивание: псевдоним панели с подчёркиванием в начале имени
INDEX_RE = re.compile(_WB + "(?:" + "|".join(INDEX_WORDS) + r")(?![\wА-Яа-яЁё])|" + _WB_ALIAS + "(?:" + "|".join(INDEX_COLLECTIONS) + r")\s*[.\[]", re.I)
_CALL = re.compile(rf"(?<![\w.])(?P<owner>{scan.NAME})\s*\.\s*(?P<proc>{scan.NAME})\s*\(")
_BARE = re.compile(rf"(?<![\w.])(?P<proc>{scan.NAME})\s*\(")
BUILTINS = frozenset({"получитьобщуюформу", "получитьформу", "открытьформу", "открытьформумодально", "вопрос", "предупреждение", "вводзначения", "вводчисла", "вводстроки",
                      "вводдаты", "сообщить", "состояние", "найтипомеченныенаудаление"})      # встроенные функции платформы, которым передают форму: в выгрузке их процедуры нет и быть не может
KEYWORDS = frozenset({"если", "пока", "для", "новый", "возврат", "и", "или", "не", "тогда", "иначе", "каждого", "из", "по", "процедура", "функция"})


def _form_argument(args, aliases=()):
    """Что передано вызванной процедуре: `form` — `ЭтаФорма`, `element` — `ЭлементыФормы…` или псевдоним элемента (процедура может менять форму), иначе `None`."""
    if re.search(r"(?<![\wА-Яа-яЁё.])ЭтаФорма(?![\wА-Яа-яЁё])", args, re.I):
        return "form"
    if re.search(r"(?<![\wА-Яа-яЁё.])ЭлементыФормы(?![\wА-Яа-яЁё])", args, re.I):
        return "element"
    return "element" if any(re.search(rf"(?<![\wА-Яа-яЁё.]){re.escape(name)}(?![\wА-Яа-яЁё(])", args, re.I) for name in aliases) else None


def _remember_form(found, masked, at, number, owner, proc, aliases=(), no_module=False):
    """Запоминает вызов `owner.proc(…)` или `proc(…)`, у которого среди аргументов в этой строке стоит форма, элемент или псевдоним элемента (`_form_argument`). `no_module` —
    владелец вызова не общий модуль выгрузки: модуля в выгрузке нет, что вызванное делает, неизвестно."""
    args = scan.call_args(masked, at)
    passed = _form_argument(args, aliases) if args is not None else None
    if passed is None:
        return
    entry = found.setdefault(((owner or "").casefold(), proc.casefold()), {"module": owner, "procedure": proc, "lines": [], "form": False})
    entry["lines"].append(number)
    entry["form"] = entry["form"] or passed == "form"
    if no_module:
        entry["no_module"] = True


def _word_at(masked, name):
    return re.search(rf"(?<![\wА-Яа-яЁё.]){re.escape(name)}(?![\wА-Яа-яЁё])", masked, re.I) is not None


def _normalized(text):
    return "\n".join(text.lstrip("﻿").splitlines()) + "\n"


def _read(path):
    try:
        return pathlib.Path(path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None


_ALIAS = re.compile(rf"(?<![\w.])(?P<name>{scan.NAME})\s*=\s*(?:ЭтаФорма\s*\.\s*)?(?:ЭлементыФормы|ЭтаФорма)(?![\wА-Яа-яЁё])", re.I)
_RECEIVER = re.compile(rf"(?P<name>{scan.NAME})\s*\.\s*$")
_COLLECTION_HIT = re.compile(_WB_ALIAS + "(?:" + "|".join(INDEX_COLLECTIONS) + r")\s*[.\[]", re.I)


_NEW_ASSIGN = re.compile(rf"(?<![\w.])(?P<name>{scan.NAME})\s*=\s*Новый(?![\wА-Яа-яЁё])", re.I)
_ADD_ASSIGN = re.compile(rf"(?<![\w.])(?P<name>{scan.NAME})\s*=\s*(?P<root>{scan.NAME})(?:\s*\.\s*{scan.NAME})*\s*\.\s*(?:Добавить|Вставить)\s*\(", re.I)          # `Элемент = Список.Добавить(…)`: элемент списка данных
_CREATE_ASSIGN = re.compile(rf"(?<![\w.])(?P<name>{scan.NAME})\s*=\s*(?:ЭтаФорма\s*\.\s*)?(?:ЭлементыФормы\s*\.\s*Добавить|[\w.\[\]А-Яа-яЁё\"]*?\.\s*(?:Страницы|Колонки|Кнопки)\s*\.\s*(?:Добавить|Вставить))\s*\(", re.I)
_CREATED_COLLECTION = re.compile(r"(?<![\wА-Яа-яЁё])(?:Кнопки|Колонки|Страницы)\s*[.\[]|СоздатьКолонки|Отказ", re.I)
TWIN_MIN = 3             # строк указателя, начиная с которых процедура-близнец сворачивается в «как X»
_ASSIGN_ROOT = re.compile(rf"^\s*(?P<name>{scan.NAME})\s*=\s*(?P<root>{scan.NAME})", re.I)
_COND_HEAD = re.compile(r"^\s*(?:Если|ИначеЕсли|Пока)(?![\wА-Яа-яЁё])", re.I)
_COND_END = re.compile(r"(?<![\wА-Яа-яЁё])(?:Тогда|Цикл)(?![\wА-Яа-яЁё])", re.I)
_CHAIN = re.compile(r"(?P<root>[\wА-Яа-яЁё]+)(?:\s*(?:\.\s*[\wА-Яа-яЁё]+|\[[^\]]*\]))*\s*\.\s*$")
READ_WORDS = frozenset(w.casefold() for w in ("Видимость", "Доступность", "ТолькоПросмотр", "Заголовок", "ТекущаяСтраница", "ТекущийЭлемент", "ТекущаяКолонка", "Свертка", "Пометка",
                                              "РежимРабочегоСтола", "Верх", "Лево", "Ширина", "Высота"))          # слова-свойства: сами по себе только читаются в условии и справа от `=`
CALL_WORDS = ("закрыть", "откр", "создатьколонки")          # вызовы, которые в условии не читают, а делают
FORM_ROOTS = frozenset({"этаформа", "элементыформы", "форма", "этотобъект"})
FOLD_FROM = 4            # подряд идущих однотипных строк указателя, начиная с которых они сворачиваются в одну


class Folded(str):
    """Свёрнутая строка указателя: текст уже оформлен (не в обратных кавычках)."""


def _is_read(masked, hit):
    """Слово-свойство только читается: стоит в условии `Если`/`ИначеЕсли`/`Пока` (до `Тогда`/`Цикл`) либо справа от `=` присваивания. Вызовы (`ОткрытьФорму(`, `Закрыть(`, `Кнопки.Очистить`) — не свойства."""
    word = hit.group(0).casefold()
    base = 0
    if _COND_HEAD.match(masked):
        end = _COND_END.search(masked)
        if (end is None or hit.start() < end.start()) and not word.startswith(CALL_WORDS):
            return True
        base = end.end() if end else len(masked)
    if word not in READ_WORDS:
        return False
    eq = re.search(r"(?<![<>=])=(?![=>])", masked[base:])
    if eq is None:
        return False
    at = base + eq.start()
    return hit.start() > at and re.fullmatch(r"\s*[^\s=<>(),;]+\s*", masked[base:at]) is not None


def _chain_root(before):
    """Первое звено цепочки `Корень.Звено.Звено.` перед словом указателя; `None` — слово стоит без владельца."""
    found = _CHAIN.search(before)
    return found.group("root") if found else None


def _local_roots(lines, procs):
    """`{процедура: {имя: корень выражения справа}}` — присваивания `Имя = Корень…` по процедурам (для сведения локальной переменной к параметру, псевдониму или форме)."""
    out = {}
    for number, masked, _raw in lines:
        found = _ASSIGN_ROOT.match(masked)
        if found:
            out.setdefault(scan._procedure_at(procs, number), {})[found.group("name").casefold()] = found.group("root").casefold()
    return out


def _is_data_hit(masked, hit, aliases, params, news=frozenset(), roots=None, allowed=frozenset()):
    """Совпадение указателя — не про форму: `Закрыть` или `Колонки.`/`Кнопки.`/`Страницы.` у переменной с данными (`Таб.Колонки.Добавить`, `Чтение.Закрыть()`), свойство переменной,
    которой в процедуре присвоен `Новый …` (`Диалог.Заголовок`), слово-свойство, которое только читается (`_is_read`). Элементы формы доступны только через `ЭлементыФормы`, поэтому коллекция
    без него — данные, если владелец не псевдоним элемента и не параметр процедуры (параметр может быть и элементом, и формой). `roots` и `allowed` — у процедур других файлов: цепочка,
    корень которой не параметр, не псевдоним и не форма (`Номенклатура.БазоваяЕдиница.Ширина`), — данные."""
    if _is_read(masked, hit):
        return True
    word = hit.group(0)
    before = masked[:hit.start()]
    receiver = _RECEIVER.search(before)
    if receiver is None:
        return False            # владельца в строке нет: он на предыдущей строке или слова стоят сами по себе
    owner = receiver.group("name").casefold()
    if owner in news and owner not in aliases:
        return True
    if roots is not None:
        root = (_chain_root(before) or owner).casefold()
        seen = set()
        while root not in allowed and root in roots and root not in seen:
            seen.add(root)
            root = roots[root]
        if root not in allowed and "элементыформы" not in before.casefold():
            return True
    if owner in aliases or owner in params or owner in ("этаформа", "элементыформы"):
        return False
    if _COLLECTION_HIT.match(word) or word.casefold().startswith("закрыть"):
        return "элементыформы" not in before.casefold()
    return False


ASSIGNED_WORDS = READ_WORDS | {"отказ"}          # слова, которые в указателе значат присваивание: чтение как аргумента или в выражении форму не меняет


def _is_change(masked, hit):
    """Совпадение указателя меняет форму: слово-свойство стоит слева от `=` (`Элемент.Видимость = …`), метод или коллекция — вызов (`Закрыть(`, `ОткрытьФорму(`, `Кнопки.Добавить(`, `Страницы[…]`);
    слово-свойство в аргументе вызова или в выражении — чтение."""
    word = hit.group(0).casefold().rstrip(".[ ")
    if word in ASSIGNED_WORDS:
        return re.match(r"\s*(?:\[[^\]]*\]\s*)?=(?![=>])", masked[hit.end():]) is not None
    return True


def _fold(rows):
    """Подряд идущие однотипные строки одной процедуры (`ЭлементыФормы.<имя>.Доступность = Ложь;` × 44) — одной строкой с числом, диапазоном и именами."""
    def key(row):
        return re.sub(r"(ЭлементыФормы\s*\.\s*)[\wА-Яа-яЁё]+", r"\1<имя>", row[2]), row[1]
    out, at = [], 0
    while at < len(rows):
        end = at
        while end + 1 < len(rows) and key(rows[end + 1]) == key(rows[at]):
            end += 1
        run = rows[at:end + 1]
        if len(run) >= FOLD_FROM:
            names = list(dict.fromkeys(m for _n, _p, text in run for m in re.findall(r"ЭлементыФормы\s*\.\s*([\wА-Яа-яЁё]+)", text)))
            shown = ", ".join(names[:6]) + (", …" if len(names) > 6 else "")
            out.append((run[0][0], run[0][1], Folded(f"{len(run)} × `{_pointer_cell(key(run[0])[0])}` — строки {run[0][0]}–{run[-1][0]}" + (f" ({shown})" if names else ""))))
        else:
            out.extend(run)
        at = end + 1
    return out


def pointer_rows(lines, first=None, last=None, foreign=False, fold=True, strict=True):
    """`[(номер строки, процедура или None, текст строки)]` — строки (`modulescan.scan`) со словами указателя (`INDEX_RE`); `first`–`last` сужает диапазон. Заголовки процедур и
    строки без кода в указатель не входят; не входят и строки, где все совпадения — данные, а не форма (`_is_data_hit`); `foreign` — процедура другого файла (данные там отсекаются
    строже). Слово-свойство считается только слева от `=`, а метод и коллекция — вызовом (`_is_change`); `strict=False` оставляет и чтения. Подряд идущие однотипные строки сворачиваются (`_fold`),
    `fold=False` отдаёт их по одной."""
    procs = scan.procedures_of(lines)
    aliases = {m.group("name").casefold() for _n, masked, _raw in lines for m in _ALIAS.finditer(masked)}
    news = {}
    for number, masked, _raw in lines:
        for m in _NEW_ASSIGN.finditer(masked):
            news.setdefault(scan._procedure_at(procs, number), set()).add(m.group("name").casefold())
        for m in _ADD_ASSIGN.finditer(masked):
            if m.group("root").casefold() not in aliases and m.group("root").casefold() not in ("элементыформы", "этаформа"):
                news.setdefault(scan._procedure_at(procs, number), set()).add(m.group("name").casefold())          # элемент списка значений: его `Пометка` — данные
    local = _local_roots(lines, procs) if foreign else {}
    out = []
    for number, masked, raw in lines:
        if (first is not None and number < first) or (last is not None and number > last):
            continue
        if not masked.strip() or scan._HEAD.match(masked) or not INDEX_RE.search(masked):
            continue
        owner = next((p for p in procs if p[2] <= number <= (p[3] if p[3] is not None else p[2])), None)
        params = {str(p).casefold() for p in (owner[1] if owner else ())}
        name = scan._procedure_at(procs, number)
        roots = local.get(name, {}) if foreign else None
        allowed = (params | aliases | FORM_ROOTS) if foreign else frozenset()
        if all(_is_data_hit(masked, hit, aliases, params, news.get(name, frozenset()), roots, allowed) or (strict and not _is_change(masked, hit)) for hit in INDEX_RE.finditer(masked)):
            continue
        out.append((number, name, scan.shorten(raw.strip(), INDEX_TEXT)))
    if not fold:
        return out
    by_number = {n: (masked, raw) for n, masked, raw in lines}
    return _fold(_fold_twins(_fold_created(out, lines, procs, by_number), by_number))


def _fold_created(rows, lines, procs, by_number):
    """Свойства только что созданного элемента (`Поле = ЭлементыФормы.Добавить(…)`, `Страницы.Вставить(…)`) — одной строкой после строки создания: «свойства созданного «Поле»: строки 72–80»."""
    created = {}
    for number, masked, _raw in lines:
        m = _CREATE_ASSIGN.search(masked)
        if m:
            created.setdefault(scan._procedure_at(procs, number), {})[m.group("name").casefold()] = (m.group("name"), number)
    out, group = [], {}
    for number, name, text in rows:
        masked = by_number.get(number, ("", ""))[0]
        root = re.match(rf"\s*(?P<var>{scan.NAME})\s*\.", masked)
        found = created.get(name, {}).get(root.group("var").casefold()) if root else None
        if found and number > found[1] and not _CREATED_COLLECTION.search(masked):
            key = (name, found[0], found[1])
            if key in group:
                group[key].append(number)
                continue
            group[key] = [number]
            out.append((number, name, key))
            continue
        out.append((number, name, text))
    folded = []
    for number, name, text in out:
        if isinstance(text, tuple):
            numbers = group[text]
            folded.append((number, name, Folded(f"свойства созданного «{text[1]}» (создан в строке {text[2]}) — {len(numbers)} " + ("строка" if len(numbers) == 1 else "строк") + f", {numbers[0]}–{numbers[-1]}")))
        else:
            folded.append((number, name, text))
    return folded


def _skeleton(raw):
    """Строка без имён: слова обрезаны до шести знаков, числа остаются — процедуры-близнецы, различающиеся только именами, дают равные последовательности."""
    return tuple(w[:6].casefold() if not w.isdigit() else w for w in re.findall(scan.NAME, raw))


TWIN_SHARE = 0.7        # доля строк процедуры, повторяющих строки более ранней процедуры, с которой она сворачивается в «как X»


def _fold_twins(rows, by_number):
    """Процедура, чьи строки указателя в основном повторяют строки более ранней процедуры с точностью до имён (три настройки закладок по видам регистров), сворачивается: повторённые строки
    заменяет одна «как в X: N строк, отличаются имена», отличающиеся остаются как есть."""
    order, by_proc = [], {}
    for row in rows:
        if row[1] not in by_proc:
            order.append(row[1])
        by_proc.setdefault(row[1], []).append(row)

    def key_of(row):
        return ("folded",) if isinstance(row[2], Folded) else _skeleton(by_number.get(row[0], ("", ""))[1])
    pools = {}
    drop = {}
    for name in order:
        items = by_proc[name]
        if name is None or len(items) < TWIN_MIN:
            continue
        keys = [key_of(r) for r in items]
        best, best_hits = None, []
        for other, pool in pools.items():
            left = {}
            for k in pool:
                left[k] = left.get(k, 0) + 1
            hits = []
            for at, k in enumerate(keys):
                if left.get(k):
                    left[k] -= 1
                    hits.append(at)
            if len(hits) > len(best_hits):
                best, best_hits = other, hits
        if best is not None and len(best_hits) >= max(TWIN_MIN, TWIN_SHARE * len(items)):
            drop[name] = (best, set(best_hits))
        else:
            pools[name] = keys
    out, said = [], set()
    for row in rows:
        name = row[1]
        if name in drop:
            items = by_proc[name]
            at = items.index(row)
            if at in drop[name][1]:
                if name not in said:
                    said.add(name)
                    hits = [items[i] for i in sorted(drop[name][1])]
                    out.append((hits[0][0], name, Folded(f"как в {drop[name][0]}: те же {len(hits)} строк указателя (строки {hits[0][0]}–{hits[-1][0]}), отличаются имена элементов")))
                continue
        out.append(row)
    return out


EXEC_CALL = re.compile(r"(?<![\w.])Выполнить\s*\(", re.I)
OPEN_EVENTS = ("передоткрытием", "приоткрытии", "обновлениеотображения")           # события жизни формы при открытии (по имени процедуры)
CLOSE_EVENTS = ("передзакрытием", "призакрытии")
BY_NAME_EVENTS = frozenset(OPEN_EVENTS + CLOSE_EVENTS + ("обработкаоповещения", "внешнеесобытие"))          # процедуры, которые платформа вызывает по имени, без привязки в файле формы
FORM_BOUND = frozenset({"передзаписью", "призаписи", "послезаписи", "приизмененииданных", "передудалением", "обработкавыбора"})        # события формы, которые привязывают в файле: без привязки процедура не вызывается
ELEMENT_SUFFIXES = ("приизменении", "началовыбора", "очистка", "обработкавыбора", "приактивизациистроки", "приначалередактирования", "приокончанииредактирования",
                    "передудалением", "передначаломдобавления", "привыводестроки", "приполученииданных", "нажатие", "регулирование")


def _literal_parts(parts):
    return [x[1:-1] for x in parts if len(x) > 1 and x[0] == x[-1] == '"']


def _execute_links(lines, procedures):
    """Вызовы через `Выполнить(…)`: `[{line, expr, procedure, var, prefix, suffix, matches, literals: [(литерал, строка вызова, процедура-вызывающая)]}]`.

    Выражение вида `Режим + "_Показать()"` с параметром процедуры-обёртки даёт образец имени (`*_Показать`): `matches` — процедуры модуля по образцу, `literals` — строковые аргументы
    вызовов обёртки (`Перейти("Ожидание")` → `Ожидание_Показать`). Строка без переменной (`Выполнить("Имя()")`) — прямой вызов процедуры (`direct`)."""
    names = {p["name"].casefold(): p["name"] for p in procedures}

    def procedure_of(number):
        return next((p for p in procedures if p["line"] <= number <= p["end"]), None)
    out = []
    for number, masked, raw in lines:
        if not EXEC_CALL.search(masked):
            continue
        for hit in EXEC_CALL.finditer(raw):
            expr = scan.call_args(raw, hit.end())
            if expr is None:
                continue
            parts = [x.strip() for x in re.split(r"\s*\+\s*", expr.strip())]
            var = next((x for x in parts if re.fullmatch(scan.NAME, x)), None)
            wrapper = procedure_of(number)
            entry = {"line": number, "expr": expr.strip(), "procedure": wrapper["name"] if wrapper else None, "prefix": "", "suffix": "", "var": var, "matches": [], "literals": []}
            out.append(entry)
            if var is None:
                text = "".join(_literal_parts(parts))
                called = re.match(r"\s*([\wА-Яа-яЁё]+)", text)
                if called and called.group(1).casefold() in names:
                    entry["matches"] = [names[called.group(1).casefold()]]
                    entry["direct"] = True
                continue
            at = parts.index(var)
            entry["prefix"] = "".join(_literal_parts(parts[:at]))
            entry["suffix"] = "".join(_literal_parts(parts[at + 1:])).split("(")[0].strip()
            if entry["prefix"] or entry["suffix"]:
                entry["matches"] = [n for key, n in names.items() if key.startswith(entry["prefix"].casefold()) and key.endswith(entry["suffix"].casefold())
                                    and len(key) > len(entry["prefix"]) + len(entry["suffix"])]
            if not wrapper:
                continue
            params = [x.strip().split("=")[0].strip() for x in (wrapper.get("params") or "").split(",")]
            params = [x[4:].strip() if x.casefold().startswith("знач ") else x for x in params]
            if var not in params:
                continue
            entry["param"] = True
            index = params.index(var)
            call = re.compile(rf"(?<![\w.]){re.escape(wrapper['name'])}\s*\(", re.I)
            for n2, masked2, raw2 in lines:
                if n2 == number or not call.search(masked2):
                    continue
                for h2 in call.finditer(raw2):
                    args = scan.call_args(raw2, h2.end())
                    values = [x.strip() for x in args.split(",")] if args is not None else []
                    if index < len(values) and len(values[index]) > 1 and values[index][0] == values[index][-1] == '"':
                        caller = procedure_of(n2)
                        entry["literals"].append((values[index][1:-1], n2, caller["name"] if caller else None))
    return out


def _when(procs, waits, execute, opening):
    """`{имя без регистра: слова}` — когда процедура выполняется: при открытии, при закрытии, по действию, по таймеру, через `Выполнить`; «не вызывается» — ни событие, ни вызов."""
    timer = {w["name"].casefold() for w in waits}
    through = {m.casefold() for e in execute for m in e["matches"]}
    called = {c["name"].casefold() for p in procs for c in p["calls"]}
    out = {}
    for p in procs:
        key = p["name"].casefold()
        events = [h for h in p["handlers"] if h["event"] != codenotes.WAIT_EVENT]
        form_events = {str(h["event"]).casefold() for h in events if h["where"] == "форма"}
        if key in OPEN_EVENTS or form_events & hd.OPEN_EVENTS:
            out[key] = "при открытии"
        elif key in CLOSE_EVENTS or form_events & hd.CLOSE_EVENTS:
            out[key] = "при закрытии"
        elif form_events & hd.WRITE_EVENTS:
            out[key] = "при записи"
        elif key in opening:
            out[key] = "при открытии" + (" и по действию" if events else "")
        elif key in timer:
            out[key] = "по таймеру"
        elif events:
            out[key] = "по действию"
        elif key in through:
            out[key] = "через Выполнить"
        elif key in called:
            out[key] = "по действию"
        elif p["export"]:
            out[key] = "экспорт (вызов извне)"
        elif key in BY_NAME_EVENTS:
            out[key] = "платформа вызывает по имени"
        else:
            out[key] = "не вызывается"
    return out


def _unbound(name, item):
    """Процедура названа как событие, но в файле формы не привязана и никто её не вызывает: платформа её не вызывает."""
    key = name.casefold()
    if item["handlers"] or key in BY_NAME_EVENTS:
        return False
    return key in FORM_BOUND or any(key.endswith(suffix) for suffix in ELEMENT_SUFFIXES)


ACTION_NEW = re.compile(r'Новый\s+Действие\s*\(\s*"(?P<name>[^"]+)"', re.I)
_BUTTON_ADD = re.compile(rf"(?P<chain>{scan.NAME}(?:\s*\.\s*{scan.NAME})*)\s*\.\s*Кнопки\b(?:\s*\.\s*{scan.NAME})*\s*\.\s*(?:Добавить|Вставить)\s*\(", re.I)


def action_rows(lines, procedures, foreign=None):
    """Процедуры модуля формы, которые код привязывает к кнопке: `Новый Действие("Имя")` (`foreign` — путь чужого файла: в нём процедура с этим именем есть → привязка внутри файла, не к форме).
    Строка вида обработчика: `{owner: "action", element: панель или None, event, code, procedure, lines, file, labels: [литералы вызова]}`; панель — имя перед `.Кнопки…Добавить(`."""
    known = {p["name"].casefold(): p["name"] for p in procedures}
    own = {h[0].casefold() for h in scan.procedures_of(lines)} if foreign else set()
    alias_of = {m.group("name").casefold(): m.group("element") for _n, masked, _raw in lines
                for m in re.finditer(rf"(?<![\w.])(?P<name>{scan.NAME})\s*=\s*(?:ЭтаФорма\s*\.\s*)?ЭлементыФормы\s*\.\s*(?P<element>{scan.NAME})\s*;", masked)}
    out = {}
    for number, _masked, raw in lines:
        for hit in ACTION_NEW.finditer(raw):
            name = hit.group("name").strip()
            if name.casefold() not in known or name.casefold() in own:
                continue
            panel, labels = None, []
            add = [m for m in _BUTTON_ADD.finditer(raw[:hit.start()])]
            if add:
                last = add[-1]
                panel = last.group("chain").split(".")[-1].strip()
                panel = None if panel.casefold() in ("элементыформы", "этаформа") else alias_of.get(panel.casefold(), panel)
                labels = re.findall(r'"([^"]*)"', raw[last.end():hit.start()])[:3]
            row = out.setdefault(name.casefold(), {"owner": "action", "element": panel, "node": None, "event": codenotes.ACTION_EVENT, "code": known[name.casefold()],
                                                   "procedure": known[name.casefold()], "lines": [], "file": foreign, "labels": labels})
            row["lines"].append(number)
            if panel and not row["element"]:
                row["element"] = panel
    return list(out.values())


_HEADER = re.compile(rf"(?im)^[ \t]*(?:Процедура|Функция)[ \t]+({scan.NAME})")


def _find_many(config_dir, names):
    """`{имя без регистра: (путь файла, имя модуля, первая строка, последняя строка)}` первых процедур и функций с этими именами в общих модулях и модулях верхнего уровня выгрузки
    (порядок поиска — как у `modulescan.find_procedure`); каждый файл читается один раз."""
    wanted = set(names)
    found = {}
    for path, module in scan._module_files(config_dir):
        if len(found) == len(wanted):
            break
        text = _read(path)
        if text is None:
            continue
        here = {h.casefold() for h in _HEADER.findall(text)} & (wanted - set(found))
        if not here:
            continue
        for proc in scan.procedures_of(scan.scan(text)):
            key = proc[0].casefold()
            if key in here and key not in found:
                found[key] = (path, module, proc[2], proc[3] if proc[3] is not None else proc[2])
    return found


def module_map(procedures, handlers, module_text, config_dir=None, object_module=None, data_names=(), row_roots=(), field_names=()):
    """Карта модуля: `{procedures: [{name, kind, line, end, export, handlers, calls: [{name, lines}], when, unbound}], body: [{line, end, calls}], common: [{module, procedure, lines, file, found}],
    object_calls: [{module, procedure, lines, file, range}], bare_calls: [{module, procedure, lines, file, where, range}], index: {module: [(строка, процедура, текст)], foreign: [{file, procedure, range, why, rows}]}, execute: [...], opening: [имена],
    config, config_dir}`.

    `row_roots` — имена процедур обработчиков вывода строк видимых таблиц (`Targets.row_roots`): таблицу рисуют при открытии, и они часть пути открытия. `field_names` — данные, которые на форме
    показывает поле (`Targets.field_data`): переданные вызову, они, как и параметр обработчика (элемент, оформление строк) и псевдоним, дают вызванной процедуре доступ к элементу.

    `object_module` — путь к модулю объекта формы: вызов `ЭтотОбъект.Метод(`, `Псевдоним.Метод(` и `Метод(` без владельца, где `Метод` есть среди процедур этого файла и нет среди процедур
    формы и общих модулей, — вызов метода объекта (`object_calls`). `bare_calls` — голые вызовы `Имя(…)` процедур глобальных общих модулей (форма и элемент не переданы): задание о них не говорит,
    но признаки частности ищутся и в них.

    `procedures` — `brief.parse_module`; `handlers` — `brief.handlers` (с `procedure`, `event`, `element`); вызов процедуры модуля — её имя в строках другой процедуры
    (комментарии и литералы не считаются); `body` — куски тела модуля, код вне процедур (`line`–`end`; вызовы процедур из них); общий модуль — `Владелец.Процедура(` с владельцем, у которого в выгрузке есть `CommonModules/<Владелец>/Ext/Module.bsl`
    (без выгрузки — все такие вызовы, с `file: None`). Вызов через `Выполнить(…)` с литералом аргумента обёртки — ребро графа от вызывающей процедуры к процедуре по образцу имени."""
    lines = scan.scan(module_text)
    by_proc = {p["name"].casefold(): p for p in procedures}
    aliases = {m.group("name").casefold() for _n, masked, _raw in lines for m in _ALIAS.finditer(masked)}
    out = []
    for p in procedures:
        body = [(n, m) for n, m, _raw in lines if p["line"] < n <= p["end"]]
        calls = []
        for other in procedures:
            if other["name"].casefold() == p["name"].casefold():
                continue
            hit = [n for n, m in body if _word_at(m, other["name"])]
            if hit:
                calls.append({"name": other["name"], "lines": hit})
        events = [h for h in handlers if (h["procedure"] or "").casefold() == p["name"].casefold()]
        out.append({"name": p["name"], "kind": p["kind"], "line": p["line"], "end": p["end"], "export": p["export"],
                    "handlers": [{"event": h["event"], "where": h.get("element") or "форма"} for h in events], "calls": calls})
    body = []
    for first, last in scan.body_ranges(lines, [(p["line"], p["end"]) for p in procedures]):
        inside = [(n, m) for n, m, _raw in lines if first <= n <= last]
        calls = []
        for p in procedures:
            hit = [n for n, m in inside if _word_at(m, p["name"])]
            if hit:
                calls.append({"name": p["name"], "lines": hit})
        body.append({"line": first, "end": last, "calls": calls})
    execute = _execute_links(lines, procedures)
    for entry in execute:           # литерал аргумента обёртки связывает вызывающую процедуру с процедурой по образцу имени
        if entry.get("direct"):
            edges = [(entry["matches"][0], entry["line"], entry["procedure"])]
        elif not entry.get("param"):            # имя собрано из переменной модуля или выражения, литерала нет: ребро идёт к каждой процедуре по образцу
            edges = [(name, entry["line"], entry["procedure"]) for name in entry["matches"]]
        else:
            edges = [(entry["prefix"] + lit + entry["suffix"], n, caller) for lit, n, caller in entry["literals"]]
        for target, number, caller in edges:
            if target.casefold() not in by_proc:
                continue
            holder = next((o for o in out if caller and o["name"].casefold() == caller.casefold()), None)
            box = holder["calls"] if holder is not None else next((b["calls"] for b in body if b["line"] <= number <= b["end"]), None)
            if box is None:
                continue
            found = next((c for c in box if c["name"].casefold() == target.casefold()), None)
            if found is None:
                box.append({"name": by_proc[target.casefold()]["name"], "lines": [number]})
            elif number not in found["lines"]:
                found["lines"].append(number)
    waits = []
    for number, _masked, raw in lines:
        for hit in codenotes.WAIT_CALL.finditer(raw):
            name = hit.group(1).strip()
            found = by_proc.get(name.casefold())
            if found is None:
                continue
            entry = next((w for w in waits if w["name"].casefold() == name.casefold()), None)
            if entry is None:
                entry = {"name": found["name"], "lines": [], "range": (found["line"], found["end"])}
                waits.append(entry)
            entry["lines"].append(number)
            for item in out:
                if item["name"].casefold() == name.casefold() and not any(h["event"] == codenotes.WAIT_EVENT for h in item["handlers"]):
                    item["handlers"].append({"event": codenotes.WAIT_EVENT, "where": "таймер"})
    graph = {p["name"].casefold(): [c["name"].casefold() for c in p["calls"]] for p in out}
    roots = [name for name in OPEN_EVENTS if name in graph] + [c["name"].casefold() for piece in body for c in piece["calls"]]
    roots += [str(h["procedure"]).casefold() for h in handlers if h.get("owner") == "form" and str(h["event"]).casefold() in hd.OPEN_EVENTS and str(h["procedure"]).casefold() in graph]
    roots += [str(name).casefold() for name in row_roots if str(name).casefold() in graph]
    opening, todo = set(), list(roots)
    while todo:
        name = todo.pop()
        if name in opening or name not in graph:
            continue
        opening.add(name)
        todo += graph[name]
    when = _when(out, waits, execute, opening)
    for item in out:
        item["when"] = when[item["name"].casefold()]
        item["unbound"] = _unbound(item["name"], item)
    modules = {}
    if config_dir is not None:
        modules = {name.casefold(): path for path, name in scan._module_files(config_dir)}
    common, with_form, object_calls, bare = {}, {}, {}, {}
    object_procs = {}
    if object_module:
        object_text = _read(object_module)
        if object_text is not None:
            object_procs = {h[0].casefold(): h for h in scan.procedures_of(scan.scan(object_text))}
    local = {m.group("name").casefold() for _n, masked, _raw in lines for m in re.finditer(rf"(?<![\w.])(?P<name>{scan.NAME})\s*=(?!=)", masked)}
    local |= {w.casefold() for p in procedures for w in re.findall(scan.NAME, p.get("params") or "")}

    def object_call(owner, proc, number):
        entry = object_calls.setdefault(((owner or "").casefold(), proc.casefold()), {"module": owner, "procedure": proc, "lines": [], "file": str(object_module),
                                                                                       "range": (object_procs[proc.casefold()][2], object_procs[proc.casefold()][3] or object_procs[proc.casefold()][2])})
        entry["lines"].append(number)

    handler_params = {}          # параметры обработчиков, в которых приходит элемент (первый параметр, оформление строк): переданные дальше, они дают вызванному доступ к элементу
    handled = {str(h["procedure"]).casefold() for h in handlers if h.get("procedure")}
    for p in procedures:
        if p["name"].casefold() in handled:
            names = [x.strip().split("=")[0].strip() for x in (p.get("params") or "").split(",") if x.strip()]
            names = [x[4:].strip() if x.casefold().startswith("знач ") else x for x in names]
            handler_params[p["name"].casefold()] = {n.casefold() for i, n in enumerate(names) if i == 0 or n.casefold() in ("оформленияСтрок".casefold(), "оформлениеСтроки".casefold())}
    fields = {str(n).casefold() for n in field_names}

    def passable(number):
        owner = next((p for p in procedures if p["line"] <= number <= p["end"]), None)
        return aliases | handler_params.get(owner["name"].casefold(), set()) | fields if owner else aliases | fields

    for number, masked, _raw in lines:
        aliases_here = passable(number)
        for hit in _CALL.finditer(masked):
            owner, proc = hit.group("owner"), hit.group("proc")
            if owner.casefold() in by_proc or (owner.casefold() in data_names and owner.casefold() not in modules):
                continue
            if proc.casefold() in object_procs and owner.casefold() not in modules and owner.casefold() not in OBJECT_OWNER_SKIP:
                object_call(owner, proc, number)
                _remember_form(with_form, masked, hit.end(), number, owner, proc, aliases_here)
                continue
            if owner.casefold() in OWNER_SKIP:
                continue
            path = modules.get(owner.casefold())
            if config_dir is not None and path is None:
                if owner.casefold() not in local and owner.casefold() not in aliases:       # владелец не переменная модуля: общий модуль, которого в выгрузке нет
                    _remember_form(with_form, masked, hit.end(), number, owner, proc, aliases_here, no_module=True)
                continue
            entry = common.setdefault((owner.casefold(), proc.casefold()), {"module": owner, "procedure": proc, "lines": [], "file": str(path) if path else None,
                                                                              "found": None, "range": None})
            entry["lines"].append(number)
            _remember_form(with_form, masked, hit.end(), number, owner, proc, aliases_here)
        for hit in _BARE.finditer(masked):
            proc = hit.group("proc")
            if proc.casefold() in by_proc or proc.casefold() in KEYWORDS or masked[:hit.start()].rstrip().casefold().endswith(("процедура", "функция")):
                continue
            if proc.casefold() in object_procs:
                object_call(None, proc, number)
            elif proc.casefold() not in BUILTINS:
                bare.setdefault(proc.casefold(), {"module": None, "procedure": proc, "lines": []})["lines"].append(number)
            _remember_form(with_form, masked, hit.end(), number, None, proc, aliases_here)
    for entry in common.values():
        if entry["file"]:
            try:
                text = pathlib.Path(entry["file"]).read_text(encoding="utf-8-sig")
                found = [h for h in scan.procedures_of(scan.scan(text)) if h[0].casefold() == entry["procedure"].casefold()]
                entry["found"] = bool(found)
                entry["range"] = (found[0][2], found[0][3] if found[0][3] is not None else found[0][2]) if found else None
            except (OSError, UnicodeDecodeError):
                entry["found"] = None
    form_calls = []
    for (_owner, _proc), entry in with_form.items():
        if not entry["module"] and entry["procedure"].casefold() in BUILTINS:
            entry.update({"file": None, "where": None, "range": None, "builtin": True})        # встроенная функция платформы: читать нечего
            form_calls.append(entry)
            continue
        if entry.get("no_module"):
            entry.update({"file": None, "where": None, "range": None})
            form_calls.append(entry)
            continue
        found = scan.find_procedure(config_dir, entry["procedure"], entry["module"]) if config_dir is not None else None
        entry.update({"file": str(found[0]) if found else None, "where": found[1] if found else None, "range": (found[2], found[3]) if found else None})
        if found is None and entry["procedure"].casefold() in object_procs:         # процедура не в общем модуле, а в модуле объекта формы
            first, last = object_procs[entry["procedure"].casefold()][2:4]
            entry.update({"file": str(object_module), "where": "объекта", "range": (first, last if last is not None else first)})
        if entry["file"] is None and not entry["module"] and not entry["form"]:
            continue            # процедура без владельца с одним элементом в аргументах, которой нет ни в общих модулях, ни в модуле объекта, — встроенная функция: читать нечего
        form_calls.append(entry)
    bare_calls = []
    if config_dir is not None and bare:
        for key, (path, module, first, last) in _find_many(config_dir, set(bare)).items():
            bare_calls.append(dict(bare[key], file=str(path), where=module, range=(first, last)))
    index = {"module": pointer_rows(lines), "foreign": []}
    seen = set()
    texts = {}
    for entry in list(common.values()) + form_calls + list(object_calls.values()) + bare_calls:
        if not entry.get("file") or not entry.get("range") or (entry["file"], tuple(entry["range"])) in seen:
            continue
        seen.add((entry["file"], tuple(entry["range"])))
        if entry["file"] not in texts:
            text = _read(entry["file"])
            texts[entry["file"]] = scan.scan(text) if text is not None else None
        if texts[entry["file"]] is None:
            continue
        rows, via = pointer_rows(texts[entry["file"]], *entry["range"], foreign=True), []
        if not rows:             # обёртка без слов указателя: действие стоит уровнем глубже, в процедуре того же файла («через УстановитьВидимость»)
            file_procs = scan.procedures_of(texts[entry["file"]])
            inside = " ".join(m for n, m, _r in texts[entry["file"]] if entry["range"][0] < n <= entry["range"][1])
            for name, _params, first, last in file_procs:
                if name.casefold() != entry["procedure"].casefold() and _word_at(inside, name):
                    deeper = pointer_rows(texts[entry["file"]], first, last if last is not None else first, foreign=True)
                    if deeper:
                        rows += deeper
                        via.append(f"{name} {first}–{last if last is not None else first}")
        if not rows and entry in bare_calls:
            continue            # голый вызов процедуры без слов указателя в задании не нужен: признаки частности в нём ищет проверка
        index["foreign"].append({"file": entry["file"], "procedure": entry["procedure"], "range": tuple(entry["range"]), "rows": rows, "via": via})
    copies = {}
    if object_module and object_procs:
        copies[str(object_module)] = OBJECT_COPY
    shown_files = {item["file"] for item in index["foreign"]}
    for entry in list(common.values()) + form_calls + [b for b in bare_calls if b["file"] in shown_files]:
        if entry.get("file") and entry["file"] not in copies:
            name = f"{COMMON_COPIES}/{entry.get('where') or entry['module']}.bsl"
            copies[entry["file"]] = name if name not in copies.values() else f"{COMMON_COPIES}/{len(copies)}-{pathlib.Path(name).name}"
    actions = action_rows(lines, procedures)
    for source, name in copies.items():
        text = _read(source)
        if text is not None:
            actions += [dict(a, file=_rel(source, {"config_dir": str(config_dir) if config_dir is not None else None})) for a in action_rows(scan.scan(text), procedures, source)
                        if a["procedure"].casefold() not in {x["procedure"].casefold() for x in actions}]
    for row in actions:                 # процедура, которую код привязал к кнопке, — обработчик действия: «по действию», а не «не вызывается»
        item = next((o for o in out if o["name"].casefold() == row["procedure"].casefold()), None)
        if item is not None:
            item["handlers"].append({"event": row["event"], "where": row["element"] or "форма"})
            if item["when"] == "не вызывается":
                item["when"] = "по действию"
            item["unbound"] = False
    return {"procedures": out, "body": body, "waits": waits, "common": list(common.values()), "form_calls": form_calls, "object_calls": list(object_calls.values()), "bare_calls": bare_calls, "index": index,
            "execute": execute, "opening": sorted(opening), "config": config_dir is not None, "config_dir": str(config_dir) if config_dir is not None else None, "copies": copies,
            "actions": actions}


NOT_CONTAINERS = frozenset({"Splitter", "GroupBox", "Frame", "Rectangle", "Line"})          # рамки и разделители стоят «на» полях по замыслу: местом вариантов они не бывают
OVERLAP_SHARE = 0.5          # две рамки одной страницы «на одном месте», если общая площадь не меньше этой доли меньшей рамки
SCREEN_SIGNS = (("Предупреждение", r"Предупреждение\s*\("), ("Вопрос", r"(?<![\wА-Яа-яЁё.])Вопрос\s*\("), ("Сообщить", r"Сообщить\s*\("), ("Состояние", r"Состояние\s*\("),
                ("ОткрытьМодально", r"ОткрытьМодально"), ("Открыть()", r"\.\s*Открыть\s*\("), ("ОткрытьФорму", r"ОткрытьФорму"), ("ВыбратьЭлемент", r"ВыбратьЭлемент"),
                ("Показать()", r"\.\s*Показать\s*\("), ("Диалог выбора", r"Выбрать\s*\(\s*\)"), ("ЭлементыФормы", r"ЭлементыФормы\s*[.\[]"))
SIGNS_SHOWN = 2
RARE_FILE = "docs/brief-code-rare.md"
RARE_PATH = str(pathlib.Path(__file__).resolve().parents[2] / RARE_FILE)


def saved_values(doc):
    """Имена «Сохраняемых значений» формы отчёта или обработки (восстанавливаются при открытии, при первом открытии пусты); у формы без такого блока — пусто."""
    try:
        from .. import props
        from ..edit import formprops
        if props.form_settings(doc) != "настройки":
            return []
        return [name for name in (formprops._saved_name(row) for row in doc["main_attribute"]["u2"]["saved_values"]["items"]) if name]
    except Exception:                                          # блок строения иного: «сохраняемых значений» нет — не отказ задания
        return []


def _overlaps(form):
    """`[(имя, имя)]` — элементы одной страницы одного родителя, чьи рамки в файле лежат почти друг на друге: варианты одного места, которые код показывает по условию."""
    items = [i for i in form.items.values() if i.name and i.type not in NOT_CONTAINERS and i.box and (i.box[2] - i.box[0]) > 0 and (i.box[3] - i.box[1]) > 0]
    out = []
    for at, a in enumerate(items):
        for b in items[at + 1:]:
            if a.holder != b.holder or a.page != b.page:
                continue
            w = min(a.box[2], b.box[2]) - max(a.box[0], b.box[0])
            h = min(a.box[3], b.box[3]) - max(a.box[1], b.box[1])
            small = min((a.box[2] - a.box[0]) * (a.box[3] - a.box[1]), (b.box[2] - b.box[0]) * (b.box[3] - b.box[1]))
            if w > 0 and h > 0 and w * h >= OVERLAP_SHARE * small:
                out.append((a.qualified(), b.qualified()))
    return out


def _tree_words(buttons):
    """Кнопки панели словами с вложенностью: `Действие, Режим ▸ (Первый, Второй), Очистить ×2`."""
    names = [b.get("name") for b in buttons if b.get("name")]
    seen, out = set(), []
    for button in buttons:
        name = button.get("name")
        if not name or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        count = sum(1 for n in names if n.casefold() == name.casefold())
        children = [c for c in (button.get("children") or []) if c.get("name")]
        text = button.get("text")
        label = name + (f" «{text}»" if text and text.casefold() != name.casefold() else "")
        out.append(label + (f" ▸ ({_tree_words(children)})" if children else "") + (f" ×{count}" if count > 1 else ""))
    return ", ".join(out)


def form_names(form, names, tables, bars, pages):
    """Имена на форме, которыми называют цель записи: `{elements: [(короткое имя, вид)], pages: {панель: [имя]}, columns: {таблица: [имя]}, buttons: {панель: [имя]},
    button_tree: {панель: «кнопки с вложенностью»}, overlaps: [(имя, имя)]}`."""
    elements = [(names.short(name), item.type) for name, item in names.item_of.items()]
    out_pages = {}
    for (panel, _at), name in pages.items():
        if name:
            out_pages.setdefault("" if panel is None else names.short(panel), []).append(name)
    columns = {t["short"]: [c["name"] for c in t["columns"] if c.get("name")] for t in tables}
    buttons, tree = {}, {}
    for bar in bars:
        found = buttons.setdefault(names.short(bar["element"]), [])

        def walk(items):
            for button in items:
                if button.get("name"):
                    found.append(button["name"])
                walk(button.get("children") or [])
        walk(bar["buttons"])
        tree[names.short(bar["element"])] = _tree_words(bar["buttons"])
    first_page = {}
    for (panel, at), name in pages.items():
        if name and panel is not None and (panel not in first_page or at < first_page[panel][0]):
            first_page[panel] = (at, name)
    from . import facts as br_facts
    return {"elements": elements, "pages": out_pages, "columns": {k: v for k, v in columns.items() if v}, "buttons": {k: v for k, v in buttons.items() if v},
            "button_tree": {k: v for k, v in tree.items() if v and buttons.get(k)}, "overlaps": _overlaps(form),
            "short_of": {name: names.short(name) for name in names.item_of},
            "hidden": [names.short(name) for name, item in names.item_of.items() if not item.visible],
            "disabled": [names.short(name) for name, item in names.item_of.items() if not br_facts._enabled(item.node)],
            "open_pages": {names.short(panel): name for panel, (_at, name) in first_page.items()},
            "bar_buttons": {names.short(bar["element"]): _flat_buttons(bar["buttons"]) for bar in bars}}


def _flat_buttons(buttons):
    """`[(имя, подпись, подменю ли)]` всех кнопок панели с вложенными, в порядке файла."""
    out = []
    for button in buttons:
        if button.get("name"):
            out.append((button["name"], button.get("text") or "", bool(button.get("children"))))
        out += _flat_buttons(button.get("children") or [])
    return out


def _ranges(lines):
    return ", ".join(str(n) for n in lines[:8]) + (f" …(всего {len(lines)})" if len(lines) > 8 else "")


def _lines_word(lines):
    """«строка 5» или «строки 5, 9»."""
    return ("строка " if len(lines) == 1 else "строки ") + _ranges(lines)


def _rel(path, mapping):
    """Путь файла от каталога выгрузки (так его называют в `source.file`); без выгрузки или вне неё — как есть."""
    root = mapping.get("config_dir")
    if root and path:
        try:
            return pathlib.Path(path).resolve().relative_to(pathlib.Path(root).resolve()).as_posix()
        except ValueError:
            pass
    return str(path)


_LEFT = re.compile(r"^(?P<left>[^=(]*?)\s*(?:=(?![=>])|\()")


def _pointer_cell(text):
    """Строка указателя без правой части: `Панель.Видимость =`, `Кнопки.Добавить(…)`, `Отказ =`; префикс `ЭлементыФормы.` и `ЭтаФорма.` не нужен. Нет ни `=`, ни скобки — строка как есть."""
    found = _LEFT.match(text.strip())
    if found is None:
        return scan.shorten(text.strip(), POINTER_TEXT)
    left = re.split(r"(?:\bТогда\b|\bИначе\b|\bЦикл\b|;)\s*", found.group("left").strip())[-1]
    left = re.sub(r"^(?:ЭтаФорма\s*\.\s*)?(?:ЭлементыФормы\s*\.\s*)?", "", left.strip())
    return left + (" =" if text.strip()[found.end() - 1] == "=" else "(…)")


def _index_table(rows, shown):
    lines = ["| Строка | Процедура | Код |", "|---|---|---|"]
    for number, procedure, text in rows[:shown]:
        cell = str(text) if isinstance(text, Folded) else f"`{_pointer_cell(text).replace('|', '¦').replace('`', chr(39))}`"
        lines.append(f"| {number} | {procedure or 'тело модуля'} | {cell} |")
    if len(rows) > shown:
        lines.append(f"| … | … | и ещё {len(rows) - shown} строк (показаны первые {shown}) |")
    return lines


def _reach(procs, name):
    """Имена процедур (без регистра), достижимых вызовами из `name`, включая её саму."""
    calls = {p["name"].casefold(): [c["name"].casefold() for c in p["calls"]] for p in procs}
    seen, todo = set(), [name.casefold()]
    while todo:
        current = todo.pop()
        if current in seen or current not in calls:
            continue
        seen.add(current)
        todo += calls[current]
    return seen


def screen_hints(mapping, module_lines, procedure, data_names=()):
    """Видно ли на экране: «вероятно: Предупреждение (37), ЭлементыФормы (46, 51)» или «признаков нет». Признаки — по тексту процедуры и вызванных ею процедур модуля формы; это поиск
    слов, а не разбор: что код делает, решаете вы."""
    if module_lines is None:
        return "—"
    reach = _reach(mapping["procedures"], procedure)
    spans = [(p["line"], p["end"]) for p in mapping["procedures"] if p["name"].casefold() in reach]
    found = {}
    names = [re.escape(n) for n in data_names if n]
    assign = re.compile(rf"^\s*(?:Объект\s*\.\s*)?(?:{'|'.join(names)})\s*=(?!=)", re.I) if names else None
    for number, masked, _raw in module_lines:
        if not any(a < number <= b for a, b in spans):
            continue
        for label, pattern in SCREEN_SIGNS:
            if re.search(pattern, masked, re.I):
                found.setdefault(label, []).append(number)
        if assign is not None and assign.match(masked):
            found.setdefault("присваивание реквизиту", []).append(number)
    if not found:
        return "признаков нет"
    return "вероятно: " + ", ".join(f"{label} ({found[label][0]})" for label in list(found)[:SIGNS_SHOWN])


def _target_of(row, kinds=None, short=None):
    """Цель записи для обработчика файла формы — в JSON, как её пишут в `code-notes.json`; у элемента вида «Кнопка» — `{"element": …}` (кнопка командной панели называется иначе).
    `short` — `{полное имя: короткое}`: цель называет короткое имя (у тёзок оно полное). Процедура, привязанная кодом к кнопке, — всегда цель-форма."""
    short = short or {}
    if row.get("owner") == "action":
        return json.dumps({"form": True})          # процедура, привязанная кодом: одна цель — форма, где бы ни лежала панель
    if row.get("owner") == "element" and kinds and kinds.get(short.get(str(row.get("element")), str(row.get("element")))) == "Button":
        return json.dumps({"element": short.get(row["element"], row["element"])}, ensure_ascii=False)
    if row.get("owner") in ("form", "element"):
        return ""          # цель очевидна: форма — {"form": true}, элемент — {"element": «Где»}
    if row.get("owner") == "column":
        return json.dumps({"column": [short.get(row["table"], row["table"]), row["column"]]}, ensure_ascii=False)
    if row.get("owner") == "panel":
        return json.dumps({"button": [short.get(row["bar"], row["bar"]), row["button"]]}, ensure_ascii=False)
    return json.dumps({"element": short.get(row["element"], row["element"])}, ensure_ascii=False)


def _when_of(row, found):
    """Когда выполняется обработчик: событие жизни формы — при открытии, закрытии; события элементов, колонок и кнопок — по действию; процедура на пути открытия — и при открытии."""
    if found is None:
        return "—"
    when = found.get("when") or ""
    if row.get("owner") == "form":
        key = (row["procedure"] or "").casefold()
        event = str(row["event"]).casefold()
        if key in OPEN_EVENTS or event in hd.OPEN_EVENTS or any(event == word for word in ("перед открытием", "при открытии", "обновление отображения")):
            return "при открытии"
        if key in CLOSE_EVENTS or event in hd.CLOSE_EVENTS:
            return "при закрытии"
        if event in hd.WRITE_EVENTS:
            return "при записи"
        return "по действию" if "открытии" not in when else when
    return when or "по действию"


def rare_sections(mapping, module_lines, handlers=()):
    """Разделы справочника редких случаев (`docs/brief-code-rare.md`), нужные этому модулю: `[(раздел, чем вызван)]`; пусто — читать справочник незачем."""
    out = []
    text = "\n".join(masked for _n, masked, _raw in (module_lines or ()))
    if mapping.get("execute"):
        out.append(("Выполнить", "в модуле есть `Выполнить(…)`"))
    if mapping.get("waits"):
        out.append(("Таймер", "в модуле есть `ПодключитьОбработчикОжидания`"))
    if re.search(r"Кнопки\s*(?:\.\s*(?:Добавить|Вставить|Очистить|Удалить)|\[)", text, re.I) or mapping.get("actions"):
        out.append(("Кнопки, созданные кодом", "код добавляет, вставляет, удаляет или очищает кнопки либо обращается к ним по номеру"))
    if any(re.search("выводестроки|полученииданных", str(h.get("event", "")).casefold().replace(" ", "")) for h in handlers) or re.search(r"ОформлениеСтроки|ОформленияСтрок", text, re.I):
        out.append(("Оформление строк", "в модуле оформляют строки таблицы"))
    if _ALIAS.search(text) and re.search(r"(?m)^\s*[\wА-Яа-яЁё]+\s*=\s*(?:ЭтаФорма\s*\.\s*)?ЭлементыФормы", text):
        out.append(("Псевдоним элемента", "элемент лежит в переменной"))
    if re.search(r"(?<![\wА-Яа-яЁё.])ЭтаФорма\s*\.\s*[\wА-Яа-яЁё]+", text, re.I):
        out.append(("Свойства формы и имена вне формы", "в модуле есть `ЭтаФорма.<свойство>`"))
    if re.search(r"Для\s+Каждого[^;]*?Из\s+ЭлементыФормы", text, re.I):
        out.append(("Псевдоним элемента", "в модуле есть цикл по `ЭлементыФормы`"))
    seen, unique = set(), []
    for name, why in out:
        if name not in seen:
            seen.add(name)
            unique.append((name, why))
    return unique


_ACCESS = re.compile(rf"(?:ЭлементыФормы|Страницы|Кнопки|Колонки)\s*\.\s*({scan.NAME})|\[\s*\"({scan.NAME})\"\s*\]|Найти\s*\(\s*\"({scan.NAME})\"\s*\)", re.I)          # как код называет элемент, страницу, кнопку, колонку


def _named_text(module_lines, mapping):
    """Текст, в котором код называет элементы: модуль формы и копии чужих файлов, которые читает задание (модуль объекта, общие модули)."""
    parts = ["\n".join(raw for _n, _m, raw in (module_lines or ()))]
    for source in (mapping.get("copies") or {}):
        text = _read(source)
        if text is not None:
            parts.append(text)
    return "\n".join(parts)


def _elements_by_kind(elements):
    """Элементы формы по видам, самые частые первыми: `TextBox: А, Б; Label: В`."""
    by_kind = {}
    for name, kind in elements:
        by_kind.setdefault(kind, []).append(name)
    return "; ".join(f"{kind}: {_list(found, 400)}" for kind, found in sorted(by_kind.items(), key=lambda kv: (-len(kv[1]), kv[0])))


def _calls_cell(item):
    """Процедуры модуля, которые зовёт процедура (до трёх, с первой строкой вызова)."""
    names = [f"{c['name']} ({c['lines'][0]})" for c in item["calls"][:3]]
    return ", ".join(names) + (f", …ещё {len(item['calls']) - 3}" if len(item["calls"]) > 3 else "") if names else "—"


def _where_of(row, short=None):
    """Где стоит обработчик: короткое имя элемента (у тёзок — полное), `Таблица/Колонка`, `Панель/Кнопка`, `форма`."""
    short = short or {}

    def name(full):
        return short.get(full, full)
    if row.get("owner") == "action":
        at = f"строка {row['lines'][0]}" + (f", {row['file']}" if row.get("file") else "")
        return (f"{name(row['element'])} (кнопка, созданная кодом: {at})" if row.get("element") else f"кнопка, созданная кодом ({at})")
    if row.get("owner") == "column" and row.get("table"):
        return f"{name(row['table'])}/{row['column']}"
    if row.get("owner") == "panel" and row.get("bar"):
        return f"{name(row['bar'])}/{row['button']}"
    return name(row["element"]) if row.get("element") else "форма"


def _implied_name(row, short=None):
    """Имя процедуры, которое платформа даёт обработчику сама: событие формы — имя события; элемент — имя и событие; колонка — таблица, колонка и событие; кнопка панели — панель и кнопка.
    `None` — у обработчика иной вид (кнопка, созданная кодом)."""
    short = short or {}

    def leaf(full):
        return short.get(full, full).split("/")[-1]
    event = re.sub(r"\s+", "", str(row.get("event") or ""))
    owner = row.get("owner")
    if owner == "form":
        return event
    if owner == "element" and row.get("element"):
        return leaf(row["element"]) + event
    if owner == "column" and row.get("table"):
        return leaf(row["table"]) + str(row.get("column") or "") + event
    if owner == "panel" and row.get("bar"):
        return leaf(row["bar"]) + str(row.get("button") or "")
    return None


def _same_procedure(rows):
    """`[(строка, [имена остальных кнопок])]`: кнопки одной панели с одной процедурой (одна `Операция` у девяти кнопок) идут одной строкой; остальные строки — как есть."""
    out, at = [], {}
    for row in rows:
        if row.get("owner") == "panel" and row.get("button"):
            key = (str(row["procedure"]).casefold(), row.get("bar"))
            if key in at:
                at[key][1].append(row["button"])
                continue
            at[key] = (row, [])
            out.append(at[key])
            continue
        out.append((row, []))
    return out


def _plural(n, forms):
    return forms[0] if n % 10 == 1 and n % 100 != 11 else forms[1] if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else forms[2]


def handler_marks(targets):
    """`{процедура без регистра: слова}` — колонка «Признак» задания: `умолчание: …` (навык отметил сам), `частность: <признак> (строка)` либо `кандидат в умолчание`.
    Это поиск слов по тексту процедуры, вызываемых ею процедур модуля формы (и по `Выполнить(…)` по образцу имени) и на один уровень модуля объекта и общих модулей, а не разбор. Процедура, которая
    зовёт другие через `Выполнить(<переменная> + "_Имя()")`, названа частностью: `Выполнить → N процедур`."""
    skill = targets.skill_defaults()
    pattern = {}
    for e in targets.mapping().get("execute") or []:
        if e.get("matches") and not e.get("direct") and not e.get("param") and e.get("procedure"):
            pattern.setdefault(e["procedure"].casefold(), set()).update(m.casefold() for m in e["matches"])
    out = {}
    for key, name in targets.handler_procs().items():
        if key in skill:
            out[key] = f"умолчание: {hd.CATEGORY_WORDS[skill[key]]}; записи не нужно"
            continue
        signs = targets.signs(name)
        jump = f"Выполнить → {len(pattern[key])} {_plural(len(pattern[key]), ('процедура', 'процедуры', 'процедур'))} по образцу" if key in pattern else ""
        if signs or jump:
            out[key] = "частность: " + "; ".join(x for x in (jump, hd.signs_text(signs, 1, False) if signs else "") if x)          # окно и сообщение (П1) идут первыми, поэтому единственный показанный признак их не прячет
            continue
        reason = hd.unchecked_reason(targets, name)
        out[key] = "кандидат в умолчание" + (f" (не проверено: {reason})" if reason else "")
    return out


GOALS_SHOWN = 12          # целей обработчика в ячейке таблицы; остальные числом, полный перечень повторяет предупреждение проверки


def _goals_cell(found):
    return ", ".join(found[:GOALS_SHOWN]) + (f", …ещё {len(found) - GOALS_SHOWN}" if len(found) > GOALS_SHOWN else "")


def handler_goals(targets):
    """`{процедура без регистра: [цели]}` — колонка «Видимые цели» задания (`handler_defaults.visible_targets`) у обработчиков, которые не умолчание навыка."""
    skill = targets.skill_defaults()
    out = Goals()
    for key, name in targets.handler_procs().items():
        if key not in skill:
            found = hd.visible_targets(targets, name, out.lines)
            if found:
                out[key] = found
    return out


class Goals(dict):
    """`handler_goals`: `{процедура: [цели]}`; `lines` — строки модуля формы, чьи присваивания свойств цели колонки целиком называют: в «Указателе мест» их не повторяют."""

    def __init__(self):
        super().__init__()
        self.lines = set()


def task_md(form_label, handlers, mapping, on_form, dossier_dir, command, object_module=None, module_lines=None, marks=None, context=None, goals=None):
    """Текст `code-task.md`. `command` — как собрать досье после разбора (слова с командой); `module_lines` — `modulescan.scan` модуля формы; `marks` — колонка «Признак»
    (`handler_marks`); `context` — `{attributes: [(имя, есть поле)], ...}` для строки о реквизитах формы."""
    rare = rare_sections(mapping, module_lines, handlers)
    lines = [f"# Задание: разбор кода формы {form_label}", "",
             f"Нужны этот файл, модуль `{MODULE_FILE}` (рядом; номера строк в задании и в записях — его номера) и инструкция `{INSTRUCTION_PATH}` (шпаргалка в начале). "
             f"Запишите ответы в `{NOTES_FILE}`, затем соберите досье: {command}", ""]
    if rare:
        lines += [f"Редкие случаи этого модуля — в справочнике `{RARE_PATH}`; читайте только разделы: " + "; ".join(f"«{name}» ({why})" for name, why in rare) + ".", ""]
    lines += ["## События формы и действия кнопок (из файла формы)", ""]
    absent = []
    all_rows = list(handlers) + [a for a in (mapping.get("actions") or []) if a["procedure"].casefold() not in {(h["procedure"] or "").casefold() for h in handlers}]
    if all_rows:
        lines += ["«Признак» — поиск слов, а не разбор: решаете вы. `частность: …` (окно и сообщение названы первыми) — запишите on_event или запись нужного вида. Обработчики без частности "
                  "(умолчание навыка и кандидаты) стоят списком под таблицей. «Где» — короткое имя элемента (у тёзок полное). Пустая «Процедура» — платформа дала имя сама (форма — событие; "
                  "элемент — имя и событие; колонка — таблица, колонка и событие; кнопка панели — панель и кнопка). Пустое «Когда» — по действию. «Видимые цели» — что обработчик меняет на экране (поиск слов): назовите каждую в `affects` записи.", "",
                  "| Где | Событие | Процедура | Строки в модуле | Когда | Признак | Вызывает | Видимые цели | Цель кнопки или колонки |", "|---|---|---|---|---|---|---|---|---|"]
        procs = {p["name"].casefold(): p for p in mapping["procedures"]}
        short = on_form.get("short_of") or {}
        kinds = {short_name: kind for short_name, kind in on_form.get("elements", [])}
        quiet = collections.OrderedDict()          # обработчики без частности: `{признак: [процедура (строки)]}` — списком под таблицей, не строками
        for h, same in _same_procedure(all_rows):
            found = procs.get((h["procedure"] or "").casefold())
            if found is None:
                absent.append(h["procedure"])
            mark = (marks or {}).get((h["procedure"] or "").casefold(), "—") if found else "—"
            where, target = _where_of(h, short), _target_of(h, kinds, short)
            if same:          # одна процедура у нескольких кнопок одной панели: одна строка, по записи на каждую кнопку
                bar = short.get(h["bar"], h["bar"])
                where = f"{bar}/{{" + ", ".join([h["button"]] + same) + f"}} ×{len(same) + 1}"
                target = json.dumps({"button": [bar, "<кнопка из колонки «Где»>"]}, ensure_ascii=False)
            if found is not None and h.get("owner") != "action" and mark.startswith(("умолчание", "кандидат в умолчание")):
                entry = f"{where} · {h['event']} · {found['name']} ({found['line']}–{found['end']})" + (f" · цель {target}" if target else "")
                group = mark.split(" (не проверено")[0] + (" (не проверено — код других модулей не прочитан)" if "(не проверено" in mark else "")          # причина — в процедуре, не в заголовке группы
                if entry not in quiet.setdefault(group, []):
                    quiet[group].append(entry)
                continue
            implied = _implied_name(h, short)
            name = "" if implied and implied.casefold() == (h["procedure"] or "").casefold() and not same and found is not None else h["procedure"]
            when = _when_of(h, found)
            lines.append(f"| {where} | {h['event']} | {name} | " + (f"{found['line']}–{found['end']}" if found else "процедуры нет в модуле") + f" | {'' if when == 'по действию' else when} | "
                         + f"{mark} | {_calls_cell(found) if found else '—'} | {_goals_cell((goals or {}).get((h['procedure'] or '').casefold(), []))} | {'`' + target + '`' if target else ''} |")
        if quiet:
            lines += ["", "Без частности по поиску слов (где · событие · процедура (строки)). Умолчания навык отметил сам; кандидатов запишите одной записью `default`, если окна, сообщения, вида формы и отказа в них нет:", ""]
            lines += [f"- {mark.replace('; записи не нужно', '')}: " + ", ".join(entries) for mark, entries in quiet.items()]
        if absent:
            lines += ["", "Обработчики без процедуры в модуле разбирать нечего: " + ", ".join(dict.fromkeys(a for a in absent if a)) + "; в счёт «разобрано N из M» они не входят."]
    else:
        lines.append("В файле формы нет событий и действий кнопок с процедурами.")
    waits = mapping.get("waits") or []
    if waits:
        lines += ["", "## Обработчики ожидания (таймеры)", "",
                  "Процедуру, подключённую `ПодключитьОбработчикОжидания(\"Имя\", …)`, платформа вызывает по таймеру уже после открытия: её строки не выполняются при открытии. "
                  "Запишите, что она меняет на экране, как `on_event` с целью-формой и событием «" + codenotes.WAIT_EVENT + "»:", ""]
        lines += [f"- {w['name']} — подключена {_lines_word(w['lines'])}; процедура в строках {w['range'][0]}–{w['range'][1]}" for w in waits]
    execute = mapping.get("execute") or []
    if execute:
        lines += ["", "## Вызовы через Выполнить", "",
                  "Граф связывает вызывающую процедуру с процедурами по образцу имени: литерал аргумента обёртки — с одной (`Перейти(\"Ожидание\")` → `Ожидание_Показать`), имя из переменной модуля — "
                  "со всеми по образцу. Процедура, до которой доходят только такие вызовы из обработчика действия, выполняется по действию: что она меняет, записывайте `on_event` этого обработчика "
                  "(по записи на переход), запись состояния в ней отклонят:", ""]
        for e in execute:
            bits = [f"строка {e['line']} `Выполнить({scan.shorten(e['expr'], 80)})`" + (f" в {e['procedure']}" if e["procedure"] else "")]
            if e["matches"]:
                bits.append("процедуры по образцу: " + ", ".join(e["matches"][:8]))
            if e["literals"]:
                bits.append("литералы аргумента: " + ", ".join(f"\"{lit}\" ({n}" + (f", {caller}" if caller else "") + ")" for lit, n, caller in e["literals"][:8]))
            lines.append("- " + "; ".join(bits))
    lines += ["", "## Карта модуля", ""]
    others = [p for p in mapping["procedures"] if not p["handlers"] or p.get("unbound")]
    if others:
        lines += ["Обработчики — в таблице выше (колонка «Вызывает»); здесь остальные процедуры (имя и строки), по тому, когда они выполняются.", ""]
        by_when = {}
        for p in others:
            what = "не привязана (платформа не вызывает): записей не нужно" if p.get("unbound") else p.get("when", "") or "—"
            by_when.setdefault(what, []).append(f"{p['name']}{' (экспорт)' if p['export'] else ''} {p['line']}–{p['end']}")
        lines += [f"- {what}: " + "; ".join(names) for what, names in by_when.items()]
        calling = [f"{p['name']} → " + ", ".join(f"{c['name']} ({_ranges(c['lines'])})" for c in p["calls"]) for p in others if p["calls"]]
        if calling:
            lines += ["", "Вызовы между процедурами модуля (строки вызова): " + "; ".join(calling) + "."]
    elif mapping["procedures"]:
        lines.append("Все процедуры модуля — обработчики (таблица выше).")
    else:
        lines.append("В модуле нет процедур и функций.")
    lines += ["", "Тело модуля — код вне процедур. Он выполняется при создании формы, раньше `ПередОткрытием`; записи о нём принимаются с `lines` внутри одного куска:", ""]
    if mapping["body"]:
        for piece in mapping["body"]:
            calls = "; ".join(f"{c['name']} ({_ranges(c['lines'])})" for c in piece["calls"])
            lines.append(f"- строки {piece['line']}–{piece['end']}" + (f"; вызывает процедуры модуля: {calls}" if calls else ""))
    else:
        lines.append("- кода вне процедур нет")
    lines += _foreign_calls(mapping, object_module, module_lines)
    index = mapping.get("index") or {"module": [], "foreign": []}
    lines += ["", "## Указатель мест, меняющих форму", "",
              "Строки, где стоят слова `" + "`, `".join(INDEX_WORDS) + "`, `" + "`, `".join(c + ".…" for c in INDEX_COLLECTIONS) + "`; чтения в условиях и свойства объектов `Новый …` не входят. "
              "Это перечень для чтения, а не разбор. Строка вне перечня тоже может менять форму (имя через переменную, цикл); строки, чьи цели названы в «Видимых целях» таблицы, здесь не повторяются. "
              "После сборки досье навык назовёт строки пути открытия, не покрытые записями.", "",
              f"Модуль формы `{MODULE_FILE}` (номера строк — его номера):", ""]
    shown_rows = [r for r in index["module"] if r[0] not in getattr(goals, "lines", ())]          # строки, чьи цели названы в колонке «Видимые цели», не повторяются
    lines += _index_table(shown_rows, INDEX_SHOWN) if shown_rows else ["В модуле формы таких строк нет." if not index["module"] else "Все строки модуля формы названы целями в таблице событий."]
    for entry in index["foreign"]:
        if not entry["rows"]:
            continue            # процедура без таких строк названа в разделе «Другой код» (строки вызова и процедуры)
        via = f", через {', '.join(entry['via'])}" if entry.get("via") else ""
        lines += ["", f"Файл `{_rel(entry['file'], mapping)}`, процедура {entry['procedure']} (строки {entry['range'][0]}–{entry['range'][1]}{via}; номера — строки этого файла; "
                  "запись о ней — с `source`):", ""]
        lines += _index_table(entry["rows"], INDEX_FOREIGN_SHOWN)
    named_text = _named_text(module_lines, mapping)
    tokens = {w.casefold() for w in re.findall(scan.NAME, named_text)}
    accessed = {(a or b or c).casefold() for a, b, c in _ACCESS.findall(named_text)}
    every = bool(re.search(r"Для\s+Каждого[^;]*?Из\s+(?:ЭтаФорма\s*\.\s*)?ЭлементыФормы|ЭлементыФормы\s*\[\s*[^\"\]\s]", named_text, re.I))          # цикл по элементам или имя из переменной: назвать может любой
    short = on_form.get("short_of") or {}
    with_handler = {short.get(r["element"], r["element"]) for r in all_rows if r.get("element") and r.get("owner") in ("element", "action")} | {
        short.get(r["bar"], r["bar"]) for r in all_rows if r.get("owner") == "panel" and r.get("bar")} | {
        short.get(r["table"], r["table"]) for r in all_rows if r.get("owner") == "column" and r.get("table")}
    named = [(n, k) for n, k in on_form["elements"] if every or (n.split("/")[-1].casefold() in accessed and n not in with_handler)]
    rest_kinds = {}
    for n, k in on_form["elements"]:
        if (n, k) not in named:
            rest_kinds[k] = rest_kinds.get(k, 0) + 1
    lines += ["", "## Что есть на форме (называйте в записях только это)", "",
              ("Элементы, которые названы в коде (с обработчиком — в таблице событий, здесь не повторяются), по видам (вид: имена): " if not every else "Элементы по видам (вид: имена; код обращается к элементам по имени из переменной): ")
              + (_elements_by_kind(named) if named else "нет") + "."
              + (" Остальные код не называет или они в таблице событий: " + ", ".join(f"{k} — {v}" for k, v in sorted(rest_kinds.items(), key=lambda kv: (-kv[1], kv[0]))) + "." if rest_kinds else "")]
    shown_names = {n for n, _k in named} | {n for n, _k in on_form["elements"] if n in with_handler}          # «скрыт в файле» — у каждого названного: и у элемента из таблицы событий
    state = []
    hidden = [n for n in on_form.get("hidden") or [] if n in shown_names]
    disabled = [n for n in on_form.get("disabled") or [] if n in shown_names]
    opened = {p: page for p, page in (on_form.get("open_pages") or {}).items() if p in shown_names}
    if opened:
        state.append("открыта страница (в файле): " + "; ".join(f"{p} — {page}" for p, page in opened.items()))
    if hidden:
        state.append("скрыты в файле: " + _list(hidden, 300))
    if disabled:
        state.append("недоступны в файле: " + _list(disabled, 300))
    if state:
        lines += ["", "Состояние в файле (до работы кода) у названных: " + "; ".join(state) + "."]
    attributes = (context or {}).get("attributes") or on_form.get("attributes") or []
    if attributes:
        bare = [name for name, shown in attributes if not shown]
        lines += ["", f"Реквизитов формы {len(attributes)}: при открытии они пусты, кроме сохраняемых и поставленных кодом. Реквизит, у которого на форме есть поле, — видимое: значение, которое он получает при "
                  "открытии, записывается (запись `value`, цель — поле); присваивание реквизиту без поля — данные, записи не нужно. У " + (f"{len(attributes) - len(bare)} из них есть поле на форме (по привязке данных)"
                  + (", у остальных поля нет: " + _list(bare, 300) if bare else "") if len(bare) < len(attributes) else "всех поля на форме нет: " + _list(bare, 300)) + "."]
    drivers = _initial_sources(module_lines, on_form, attributes, mapping)
    if drivers:
        lines += ["", "От этих реквизитов зависит вид формы; начальное значение при открытии: " + "; ".join(drivers) + "."]
    if on_form["pages"]:
        lines += ["", "Страницы панелей:"] + [f"- {holder or 'сама форма'}: {_list(found, 200)}" for holder, found in on_form["pages"].items()]
    if on_form["columns"]:
        lines += ["", "Колонки таблиц (названные в модуле или в вызываемом коде — по именам, остальные числом; цель колонки в событиях задана в таблице выше):"]
        for holder, found in on_form["columns"].items():
            named_cols = [c for c in found if c.casefold() in tokens]
            lines.append(f"- {holder}: {len(found)}" + (f", код называет: {_list(named_cols, 200)}" if named_cols else ", код их не называет"))
    bar_buttons = on_form.get("bar_buttons") or {}
    if on_form.get("buttons"):
        lines += ["", "Кнопки командных панелей (цель кнопки из файла — `{\"button\": [панель, кнопка]}`, где бы она ни лежала; перечислены названные в коде или с обработчиком, остальные числом; подменю — «▸»):"]
        handled = {(short.get(r["bar"], r["bar"]), str(r.get("button") or "").casefold()) for r in all_rows if r.get("owner") == "panel"}
        for holder, found in on_form["buttons"].items():
            flat = bar_buttons.get(holder) or [(n, "", False) for n in found]
            chosen = [(n, t, m) for n, t, m in flat if n.casefold() in accessed or (holder, n.casefold()) in handled]
            words = ", ".join(n + (f" «{t}»" if t and t.casefold() != n.casefold() else "") + (" ▸" if m else "") for n, t, m in chosen)
            lines.append(f"- {holder}: {len(flat)}" + (f"; {words}" if words else "; код кнопок не называет"))
    overlaps = on_form.get("overlaps") or []
    if overlaps:
        lines += ["", "Элементы, которые в файле занимают одно место (код обычно показывает по условию один из них; варианты РАЗНЫХ элементов на одном месте — общая `exclusive_group`): "
                  + _list([f"{a} ↔ {b}" for a, b in overlaps], 300) + "."]
    saved = on_form.get("saved") or []
    if saved:
        lines += ["", "Сохраняемые значения формы (восстанавливаются при открытии; при первом открытии пусты): " + _list(saved, 200) + "."]
    lines += ["", "## Как записать", "",
              f"Файл `{NOTES_FILE}` — `{{\"notes\": [...]}}`; поля записей, виды и примеры — в инструкции. Запись, которая не сошлась с формой или с модулем, в досье не попадёт: она будет названа с причиной.", ""]
    return "\n".join(lines)


def _initial_sources(module_lines, on_form, attributes, mapping):
    """`[«Реквизит — откуда его значение при открытии»]` для реквизитов формы, от которых зависит вид формы (слова условий и правых частей рядом со свойствами элементов): сохраняемое значение
    (при первом открытии пусто), присваивание в теле модуля либо ничего — тогда начальное значение типа (Ложь, 0, пусто)."""
    taken = {n.split("/")[-1].split(".")[-1].casefold() for n, _k in on_form.get("elements") or []} | {c.casefold() for cols in (on_form.get("columns") or {}).values() for c in cols}
    attributes = list({n.casefold(): (n, s) for n, s in list(attributes or []) + [(d, False) for d in on_form.get("data") or []] if n and n.casefold() not in taken}.values())
    if not module_lines or not attributes:
        return []
    roots = hd.roots_of(module_lines)
    for _name, params, _first, _last in scan.procedures_of(module_lines):
        roots |= {str(x).casefold() for x in params if x}
    inputs = hd.visual_inputs(module_lines, roots, None, True)
    saved = {str(s).casefold() for s in on_form.get("saved") or []}
    body, inside = {}, {}
    procs = scan.procedures_of(module_lines)
    for number, masked, _raw in module_lines:
        for m in re.finditer(rf"(?:^|;)\s*(?P<name>{scan.NAME})\s*=(?![=>])", masked):
            owner = scan._procedure_at(procs, number)
            if owner is None:
                body.setdefault(m.group("name").casefold(), number)
            else:
                inside.setdefault(m.group("name").casefold(), []).append(f"{owner} ({number})")
    out = []
    for name, _shown in attributes:
        key = name.casefold()
        if key not in inputs:
            continue
        if key in saved:
            out.append(f"{name} — сохраняемое значение (при первом открытии пусто: Ложь, 0)")
        elif key in body:
            out.append(f"{name} — тело модуля формы (строка {body[key]})")
        elif key in inside:
            out.append(f"{name} — присваивается в " + ", ".join(inside[key][:3]))
        else:
            out.append(f"{name} — до открытия не задаётся: начальное значение типа (Ложь, 0, пусто)")
    return out[:12]


def object_context(object_module, module_lines, mapping):
    """Модуль объекта, который читает форма: `{body: [(строка, текст)], exports: [(имя, строка объявления, [(процедура, строка присваивания)])]}` — тело модуля (присваивания реквизитам,
    которые форма называет) и экспортные переменные, которые форма читает. Номера строк — по копии `object_module.bsl`."""
    text = _read(object_module) if object_module else None
    if text is None:
        return None
    lines = scan.scan(text)
    procs = scan.procedures_of(lines)
    spans = [(first, last if last is not None else first) for _n, _p, first, last in procs]
    form_text = " ".join(masked for _n, masked, _raw in (module_lines or ()))

    def read_by_form(name):
        return re.search(r"(?<![\wА-Яа-яЁё])" + re.escape(name) + r"(?![\wА-Яа-яЁё])", form_text, re.I) is not None
    body, exports = [], []
    for number, masked, raw in lines:
        if any(a <= number <= b for a, b in spans) or not masked.strip() or masked.strip().startswith(("#", "&")):
            continue
        declared = re.match(r"\s*Перем\s+(?P<names>.+?)\s+Экспорт\s*;?\s*$", masked, re.I)
        if declared:
            for name in re.findall(scan.NAME, declared.group("names")):
                if read_by_form(name):
                    sets = [(scan._procedure_at(procs, n) or "тело модуля", n) for n, m, _r in lines if re.match(rf"\s*(?:Объект\s*\.\s*)?{re.escape(name)}\s*=(?!=)", m)]
                    exports.append((name, number, sets[:4]))
            continue
        assign = re.match(rf"\s*(?:Объект\s*\.\s*)?(?P<name>{scan.NAME})\s*=(?!=)", masked)
        if assign and read_by_form(assign.group("name")):
            body.append((number, scan.shorten(raw.strip(), INDEX_TEXT)))
    fills = []          # `ОбработкаЗаполнения` объекта: начальные значения нового документа, которые форма показывает при открытии
    for name, _params, first, last in procs:
        if name.casefold() == "обработказаполнения":
            ours = list(dict.fromkeys(m.group("name") for n, masked, _raw in lines if first < n <= (last or first) for m in [re.match(rf"\s*(?:Объект\s*\.\s*)?(?P<name>{scan.NAME})\s*=(?!=)", masked)]
                                      if m and read_by_form(m.group("name"))))
            if ours:
                fills.append((first, last or first, ours))
    return {"body": body[:20], "exports": exports[:12], "fills": fills}


def visual_calls(module_lines, procedures):
    """`{(владелец без регистра, процедура без регистра): [(строка, свойство)]}` — вызовы чужих процедур и функций в условии или правой части присваивания, которым код меняет свойство
    элемента (`Видимость = ОбщийМодуль.Функция(…)`): от результата зависит вид формы."""
    if not module_lines:
        return {}
    mine = {p["name"].casefold() for p in procedures}
    roots = hd.roots_of(module_lines)
    conds = scan.conditions(module_lines)
    out = {}
    for number, masked, _raw in module_lines:
        hits = hd.visual_assignments(masked, roots, True)
        if not hits:
            continue
        text = conds.get(number, "") + " " + masked.split("=", 1)[-1]
        text = re.sub(r'"[^"]*"', '""', text)
        seen = set()
        for hit in _CALL.finditer(text):
            seen.add((hit.group("owner").casefold(), hit.group("proc").casefold()))
        for hit in _BARE.finditer(text):
            seen.add(("", hit.group("proc").casefold()))
        for key in seen:
            if key[1] in mine or key[1] in KEYWORDS or key[1] in BUILTINS:
                continue
            out.setdefault(key, []).append((number, hits[0][0]))
    return out


def _foreign_calls(mapping, object_module, module_lines=None):
    """Раздел «Чужой код»: модуль объекта (тело, экспортные переменные), общие модули (каждый — заголовком один раз, под ним процедуры), модули, которых нет в выгрузке."""
    lines = ["", "## Другой код, который может менять форму", ""]
    decides = visual_calls(module_lines, mapping["procedures"])
    foreign_rows = {(e["file"], e["procedure"].casefold()): len(e["rows"]) for e in (mapping.get("index") or {}).get("foreign", [])}
    config = mapping["config"]
    groups, order = {}, []

    def item(entry, passed):
        key = entry.get("file") or f"?{entry.get('module')}"
        if key not in groups:
            groups[key] = {"file": entry.get("file"), "module": entry.get("where") or entry.get("module"), "items": {}, "object": False}
            order.append(key)
        slot = groups[key]["items"].setdefault(entry["procedure"].casefold(), {"name": entry["procedure"], "module": entry.get("module"), "lines": [], "range": entry.get("range"),
                                                                              "passed": False, "found": entry.get("found"), "builtin": entry.get("builtin"), "no_module": entry.get("no_module"),
                                                                              "decides": decides.get(((entry.get("module") or "").casefold(), entry["procedure"].casefold())) or []})
        slot["lines"] += [n for n in entry["lines"] if n not in slot["lines"]]
        slot["passed"] = slot["passed"] or passed
        return slot
    known = {((e.get("module") or "").casefold(), e["procedure"].casefold()): e for e in mapping["common"]}
    for entry in mapping["common"]:
        item(entry, False)
    for entry in mapping.get("form_calls") or []:
        twin = known.get(((entry.get("module") or "").casefold(), entry["procedure"].casefold()))
        item(dict(entry, file=twin["file"], found=twin["found"], range=twin["range"]) if twin is not None and entry.get("file") is None and not entry.get("no_module") else entry, True)
    if object_module:
        lines += ["Модуль объекта: `" + str(object_module) + "`" + _source_line(object_module, mapping) + " (читайте, если форма вызывает методы своего объекта или код объекта открывает форму и ставит ей свойства)."]
        context = object_context(object_module, module_lines, mapping)
        if context and context["body"]:
            lines += ["Тело модуля объекта выполняется до открытия формы; присваивания реквизитам, которые читает форма (безусловный литерал полю навык применяет сам; записи нужны остальные): "
                      + "; ".join(f"{n}: `{t}`" for n, t in context["body"]) + "."]
        for first, last, names in (context["fills"] if context else ()):
            lines += [f"Начальные значения нового объекта ставит `ОбработкаЗаполнения` (строки {first}–{last}): {', '.join(names[:12])}" + (f", …ещё {len(names) - 12}" if len(names) > 12 else "")
                      + " — при открытии нового документа эти поля уже заполнены: скажите об этом записью `other` (цель-форма, `why` — значения словами, `condition` «новый объект»)."]
        if context and context["exports"]:
            lines += ["Экспортные переменные объекта, которые читает форма: " + "; ".join(
                f"{name} (объявлена в {at})" + (" — ставится: " + ", ".join(f"{proc} ({n})" for proc, n in sets) if sets else "") for name, at, sets in context["exports"]) + "."]
        calls = mapping.get("object_calls") or []
        if calls:
            lines += ["Вызовы методов объекта (по имени в тексте): " + "; ".join(
                f"{(c['module'] + '.' if c['module'] else '') + c['procedure']} ({_ranges(c['lines'])}; процедура {c['range'][0]}–{c['range'][1]})" for c in calls[:CALLS_SHOWN])
                      + (f"; …и ещё {len(calls) - CALLS_SHOWN}" if len(calls) > CALLS_SHOWN else "") + "."]
        else:
            lines += ["Вызовов методов объекта в модуле формы нет."]
        lines += [""]
    else:
        lines += ["Модуль объекта: не найден (выгрузка конфигурации не задана или у формы нет объекта).", ""]
    lines += ["Модуль приложения и `ПриНачалеРаботыСистемы` в задание не входят: стартовую форму открывают они.", ""]
    if not config:
        lines += ["Выгрузка конфигурации не задана: модули не проверены, файлы не определены; вызовы вида `Имя.Процедура(` (в списке могут быть и переменные) и вызовы, которым передана форма или элемент:", ""]
        names = [slot for key in order for slot in groups[key]["items"].values()]
        for slot in names[:CALLS_SHOWN]:
            name = (slot["module"] + "." if slot["module"] else "") + slot["name"]
            lines.append(f"- {name} — {_lines_word(slot['lines'])}; " + ("встроенная функция платформы (читать нечего)" if slot["builtin"] else "файл не определён")
                         + ("; форма или элемент переданы" if slot["passed"] and not slot["builtin"] else ""))
        if len(names) > CALLS_SHOWN:
            lines.append(f"- …и ещё {len(names) - CALLS_SHOWN}")
        if not names:
            lines.append("- нет")
        return lines
    shown = 0
    others = []
    missing = {}
    for key in order:
        group = groups[key]
        if group["file"] is None:
            for slot in group["items"].values():
                if slot["builtin"]:
                    others.append(f"{slot['name']} ({_ranges(slot['lines'])}; встроенная функция платформы)")
                elif slot["no_module"]:
                    missing.setdefault(slot["module"], []).append(f"{slot['name']} ({_ranges(slot['lines'])})")
            continue
        heads = []
        rest = []
        for slot in group["items"].values():
            rows = foreign_rows.get((group["file"], slot["name"].casefold()), 0)
            if slot["passed"] or rows or slot["decides"]:
                heads.append(slot)
            else:
                where = f"; {slot['range'][0]}–{slot['range'][1]}" if slot.get("range") else ""
                rest.append(f"{(slot['module'] + '.' if slot['module'] and slot['module'] != group['module'] else '')}{slot['name']} ({_ranges(slot['lines'])}{where})")
        if not heads and not rest:
            continue
        lines += [f"Модуль **{group['module']}** — `{_rel(group['file'], mapping)}` (в `source.file`)" + _copy_word(group["file"], mapping) + ":"]
        for slot in heads:
            if shown >= CALLS_SHOWN:
                break
            shown += 1
            where = (f"процедура в строках {slot['range'][0]}–{slot['range'][1]}" if slot.get("range") else "процедуры в нём нет")
            passed = "; передана форма или элемент" if slot["passed"] else ""
            if slot["decides"]:
                passed += f"; результат решает {slot['decides'][0][1]} (строки {', '.join(str(n) for n, _w in slot['decides'][:4])}) — читать эту процедуру"
            lines.append(f"- {slot['name']} — вызов: {_lines_word(slot['lines'])}; {where}{passed}")
        if rest:
            lines.append("- прочие вызовы (в процедурах нет строк указателя, форма и элементы не переданы; в скобках строки вызова и строки процедуры в этом файле): " + ", ".join(rest[:20]) + (f", …и ещё {len(rest) - 20}" if len(rest) > 20 else ""))
        lines.append("")
    for module, calls in missing.items():
        lines += [f"Модуля в выгрузке нет: **{module}** — вызовы {', '.join(calls[:8])}; форма или элемент переданы, что он с ними делает, неизвестно: запись `other` с причиной «модуль не выгружен»."]
    if others:
        lines += ["Встроенные функции платформы, которым передана форма или элемент (читать нечего): " + ", ".join(others[:10]) + "."]
    if not (shown or missing or others or any(g["file"] for g in groups.values())):
        lines.append("Вызовов общих модулей, процедуры которых могут менять форму, нет.")
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def _copy_word(path, mapping):
    copy = (mapping.get("copies") or {}).get(str(path))
    return f"; копия `{copy}` в каталоге досье — номера строк по ней" if copy else ""


def _source_line(path, mapping):
    copy = (mapping.get("copies") or {}).get(str(path))
    return (f"; в `source.file` — `{_rel(path, mapping)}`" + (f", номера строк — по копии `{copy}` в каталоге досье" if copy else "")) if mapping.get("config_dir") else ""


def _setup_blocks(module, accepted):
    """`[(от, до)]` — блоки настройки созданного: подряд идущие строки после записи `created` или `other`, которые присваивают свойства или вызывают методы той переменной, куда записано
    создание (`Таб = ЭлементыФормы.Добавить(…)` → `Таб.Верх = …`, `Таб.СоздатьКолонки()`); пустые строки и комментарии блок не обрывают, любая другая строка — обрывает. Блок покрыт записью."""
    by_number = {n: masked for n, masked, _raw in module}
    last_line = max(by_number) if by_number else 0
    out = []
    for note in accepted:
        if note["kind"] not in ("created", "other"):
            continue
        names = {m.group("name").casefold() for n in range(note["lines"][0], note["lines"][1] + 1) for m in _CREATE_ASSIGN.finditer(by_number.get(n, ""))}
        if not names:
            continue
        end, at = None, note["lines"][1] + 1
        while at <= last_line:
            masked = by_number.get(at, "")
            if masked.strip():
                root = re.match(rf"\s*(?P<var>{scan.NAME})\s*[.\[]", masked)
                if root is None or root.group("var").casefold() not in names:
                    break
                end = at
            at += 1
        if end is not None:
            out.append((note["lines"][1] + 1, end))
    return out


_ASSIGNED = re.compile(rf"(?P<chain>{hd._CHAIN})\s*\.\s*(?P<prop>{hd._VISUAL})\s*=(?![=>])", re.I)


def _assigned_key(masked):
    """`(элемент, свойство)` присваивания свойству элемента в строке (текст цепочки без `ЭтаФорма.`/`ЭлементыФормы.`, без регистра) либо `None`."""
    hit = _ASSIGNED.search(masked)
    if hit is None:
        return None
    chain = re.sub(r"\s+", "", hit.group("chain")).casefold()
    chain = re.sub(r"^(?:этаформа\.)?(?:элементыформы\.)?", "", chain)
    return chain, hit.group("prop").casefold()


def overlapped_opening(targets, module, own):
    """`[(строка, строка перекрывающей записи)]` — строки пути открытия, которые перекрывает более поздний вызов: тот же элемент и свойство присваивает позже по порядку выполнения строка другого
    вызова (другая цепочка вызовов от открытия), и она покрыта записью (`own` — диапазоны строк принятых записей). Состояние, которое тут же заменили, на экране не видно: запись нужна итогу, а не
    промежуточному шагу; ссылка — на строку, чья запись описывает итог. Ветки одной процедуры друг друга не перекрывают."""
    rows = {}
    for number, masked, _raw in module:
        key = _assigned_key(masked)
        if key is not None and targets.at_opening(number):
            rows[number] = (key, targets.order_key(number))
    covering = [(order, number, key) for number, (key, order) in rows.items() if any(a <= number <= b for a, b in own)]
    out = []
    for number, (key, order) in rows.items():
        later = [n for o, n, k in covering if k == key and o > order and o[:-1] != order[:-1]]
        if later:
            out.append((number, min(later, key=lambda n: rows[n][1])))
    return out


def overlapped_for(targets, accepted):
    """`overlapped_opening` с теми же диапазонами записей, что у `uncovered_opening` (строки записей и блоки настройки созданного)."""
    module = scan.scan(targets.module_text or "")
    return overlapped_opening(targets, module, [tuple(n["lines"]) for n in accepted] + _setup_blocks(module, accepted))


def _squash_text(text):
    return re.sub(r"\s+", " ", str(text)).strip().casefold()


def _opening_data_rows(targets, module, mapping):
    """`[(строка, процедура, текст)]` пути открытия, которых нет в указателе, а видно их на экране: присваивание данным, которые показывает поле или надпись формы (`Реквизит = …`, `Объект.Реквизит = …`),
    и вызов процедуры модуля, которого нет в выгрузке (`no_module`: что он меняет, неизвестно), с формой, элементом или псевдонимом в аргументах."""
    fields = targets.bound_fields()
    procs = scan.procedures_of(module)
    found = {}
    for number, masked, raw in module:
        if not targets.at_opening(number) or scan._HEAD.match(masked):
            continue
        for hit in hd._ASSIGN.finditer(masked):
            tokens = re.split(r"[.\s]+", hit.group("chain").strip())
            name = tokens[-1] if len(tokens) == 1 or (len(tokens) == 2 and tokens[0].casefold() in ("объект", "этаформа", "этотобъект")) else None
            if name and name.casefold() in fields and (len(tokens) == 2 or name.casefold() in targets.data_names):
                found[number] = (number, scan._procedure_at(procs, number), scan.shorten(raw.strip(), INDEX_TEXT))
    texts = {n: raw for n, _m, raw in module}
    for entry in mapping.get("form_calls") or []:
        if entry.get("no_module"):
            for number in entry["lines"]:
                if targets.at_opening(number) and number not in found:
                    found[number] = (number, scan._procedure_at(procs, number), scan.shorten(texts.get(number, "").strip(), INDEX_TEXT))
    return list(found.values())


def uncovered_opening(targets, accepted, mapping):
    """Строки указателя на пути открытия, которые не покрыты ни одной принятой записью: `[(файл, строка, процедура, текст)]`; `файл` — `module.bsl` либо путь от каталога выгрузки.

    Путь открытия: тело модуля формы, события жизни формы и всё, что они вызывают (`Targets.at_opening`), включая процедуры других файлов, вызванные со строки пути открытия. Строка модуля
    формы покрыта записью, чьи `lines` её содержат, либо блоком настройки созданного ею элемента (`_setup_blocks`); строка чужого файла — записью с `source`, чьи `lines` её содержат, либо записью любого вида на строку вызова процедуры (в том числе
    `other` с причиной: модель о процедуре сказала). `mapping` — `module_map` с теми же выгрузкой и модулем объекта."""
    module = scan.scan(targets.module_text or "")
    own = [tuple(n["lines"]) for n in accepted] + _setup_blocks(module, accepted)
    sourced = [(n["source"]["file"], tuple(n["source"]["lines"])) for n in accepted if n.get("source")]
    out = []
    overlapped = {number for number, _by in overlapped_opening(targets, module, own)}
    rows = [(number, procedure, shown) for number, procedure, shown in pointer_rows(module, fold=False) if targets.at_opening(number)] + _opening_data_rows(targets, module, mapping)
    covered = {(procedure, _squash_text(shown)) for number, procedure, shown in rows if any(a <= number <= b for a, b in own)}          # повтор покрытой строки той же процедуры отдельной записи не просит
    for number, procedure, shown in sorted(rows):
        if not any(a <= number <= b for a, b in own) and number not in overlapped and (procedure, _squash_text(shown)) not in covered:
            out.append((MODULE_FILE, number, procedure, shown))
    calls = {}
    for entry in list(mapping["common"]) + list(mapping.get("form_calls") or []) + list(mapping.get("object_calls") or []):
        if entry.get("file") and any(targets.at_opening(n) for n in entry["lines"]):
            calls.setdefault((entry["file"], entry["procedure"].casefold()), []).extend(entry["lines"])
    seen = set()
    for foreign in mapping["index"]["foreign"]:
        key = (foreign["file"], foreign["procedure"].casefold())
        if key not in calls or (foreign["file"], tuple(foreign["range"])) in seen:
            continue
        seen.add((foreign["file"], tuple(foreign["range"])))
        if any(a <= n <= b for n in calls[key] for a, b in own):
            continue
        file_text = _read(foreign["file"])
        if file_text is None:
            continue
        rel = _rel(foreign["file"], mapping)
        for number, procedure, shown in pointer_rows(scan.scan(file_text), *foreign["range"], foreign=True, fold=False):
            if not any(path == rel and a <= number <= b for path, (a, b) in sourced):
                out.append((rel, number, procedure, shown))
    return out


def write(out_dir, form_label, handlers, mapping, on_form, module_text, command, object_module=None, marks=None, context=None, goals=None):
    """Пишет `code-task.md`, `code-notes.json` (заготовка; существующий файл не трогается) и `module.bsl` в каталог досье; возвращает пути."""
    import json
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    text = module_text.decode("utf-8", errors="replace") if isinstance(module_text, (bytes, bytearray)) else module_text
    (out / MODULE_FILE).write_text(_normalized(text), encoding="utf-8")       # номера строк — как у `splitlines()`: одиночный возврат каретки тоже конец строки
    for source, name in (mapping.get("copies") or {}).items():
        other = _read(source)
        if other is not None:
            (out / name).parent.mkdir(parents=True, exist_ok=True)
            (out / name).write_text(_normalized(other), encoding="utf-8")        # копия чужого файла с той же нумерацией: `source.lines` считаются по ней
    (out / TASK_FILE).write_text(task_md(form_label, handlers, mapping, on_form, out, command, object_module, scan.scan(_normalized(text)), marks, context, goals), encoding="utf-8")
    notes = out / NOTES_FILE
    if not notes.exists():              # записи, которые модель уже сделала, повторный вызов не стирает
        notes.write_text(json.dumps(codenotes.EMPTY_TEMPLATE, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"task": str(out / TASK_FILE), "notes": str(notes), "module": str(out / MODULE_FILE)}
