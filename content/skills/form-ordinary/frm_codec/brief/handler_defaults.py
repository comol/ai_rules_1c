"""Умолчания разбора кода: обработчики, о которых запись не нужна, и признаки частности, по которым это проверяется.

Запись нужна только частности: тому, что отличается от типового и видно пользователю. Типовое навык считает умолчанием:

* категории, которые навык отмечает сам по тексту процедуры (`SKILL_CATEGORIES`): `modified` — только `Модифицированность = Истина|Ложь`; `empty` — нет операторов (кроме
  `Возврат;` и `СтандартнаяОбработка = Истина;`); `standard` — только `Закрыть()`, `ЗаписатьВФорме()`, `Записать()`;
* категории, которые перечисляет модель одной записью `{"kind": "default", "handlers": [процедуры], "category": …}` (`MODEL_CATEGORIES`): `write`, `rows`, `choice`, `silent`, `linked`.

Модель может назвать процедуру умолчанием, только если в ней нет признака частности (`find_signs`): П1 — окно или сообщение; П2 — свойство элемента формы; П3 — отказ, закрытие,
таймер; П4 — присваивание реквизиту, от которого зависит вид формы; П5 — изменение таблицы формы; П6 — присваивание реквизиту, значение которого показывает поле формы (своё поле или другое: подстановка в связанные поля — тоже частность). Печать
(`Печать…(`, `Напечатать…(`) — окно, П1. Признаки ищутся в самой процедуре, в процедурах модуля формы, которые она вызывает
(любой глубины), и в чужом коде: в процедуре модуля объекта или общего модуля, которую она вызывает (голый вызов процедуры глобального общего модуля тоже), и во всей цепочке вызовов
внутри этого файла. Это поиск слов по тексту без комментариев и содержимого литералов, а не разбор смысла. Вызов кода дальше этого уровня (другой общий модуль) навык не читает: категория такой
процедуры — «не проверено» (`unchecked_reason`), а не «без видимого следа».
"""
import re

from . import modulescan as scan

NAME = scan.NAME
SKILL_CATEGORIES = ("modified", "empty", "standard", "disabled")
MODEL_CATEGORIES = ("write", "rows", "choice", "silent", "linked")       # категории, которые навык определяет сам по тексту процедуры (`guess_category`): модель их не называет
CATEGORY_WORDS = {
    "modified": "отметка изменённости формы", "empty": "пустой обработчик", "standard": "стандартное действие (закрыть, записать)",
    "disabled": "стандартное действие отключено (СтандартнаяОбработка = Ложь без замены)",
    "write": "запись данных", "rows": "пересчёт строк своей таблицы", "choice": "обычный выбор значения из справочника или списка",
    "silent": "значения без видимого следа на форме", "linked": "подстановка и пересчёт связанных полей шапки",
    "unchecked": "не проверено (процедура зовёт код, которого навык не разобрал)",
}
SIGN_WORDS = {"П1": "окно или сообщение", "П2": "свойство или поведение элемента формы", "П3": "отказ, закрытие или таймер", "П4": "вид формы зависит от реквизита", "П5": "изменение таблицы формы",
              "П6": "значение поля формы"}
OPEN_EVENTS = frozenset({"передоткрытием", "приоткрытии", "обновлениеотображения", "послевосстановлениязначений"})       # события открытия формы (по имени события из файла формы)
CLOSE_EVENTS = frozenset({"передзакрытием", "призакрытии"})
WRITE_EVENTS = frozenset({"передзаписью", "призаписи", "послезаписи", "приизмененииданных"})

_STMT_MODIFIED = re.compile(rf"^(?:ЭтаФорма\s*\.\s*)?Модифицированность\s*=\s*(?:Истина|Ложь)$", re.I)
_STMT_IDLE = re.compile(r"^(?:Возврат|СтандартнаяОбработка\s*=\s*Истина)$", re.I)
_STMT_STANDARD = re.compile(r"^(?:ЭтаФорма\s*\.\s*)?(?:Закрыть|ЗаписатьВФорме|Записать)\s*\(\s*\)$", re.I)
_VAR = re.compile(r"^\s*Перем\b", re.I)

_VISUAL = (r"(?:Видимость|Доступность|ТолькоПросмотр|Заголовок|Текст|ТекущаяСтраница|ТекущийЭлемент|ТекущаяКолонка|Пометка|Цвет[\wА-Яа-яЁё]*|Шрифт|Картинка|СписокВыбора|Подсказка|"
           r"ТекстШапки|ТекстПодвала|Свертка|РежимРабочегоСтола|Верх|Лево|Ширина|Высота)")
_START = r"(?:^|;|\bТогда\b|\bИначе\b|\bЦикл\b|\bПопытка\b|\bИсключение\b)\s*"
_CHAIN = rf"{NAME}(?:\s*(?:\.\s*{NAME}|\[[^\]]*\]))*"
_P2_ASSIGN = re.compile(rf"{_START}(?P<chain>{_CHAIN})\s*\.\s*(?P<prop>{_VISUAL})\s*=(?![=>])", re.I)
_P2_CALL = re.compile(rf"(?<![\wА-Яа-яЁё])(?P<chain>{_CHAIN})\s*\.\s*(?P<what>(?:Кнопки|Колонки|Страницы)\s*\.\s*(?:Добавить|Вставить|Очистить|Удалить|Сдвинуть)"
                      rf"|СписокВыбора\s*\.\s*(?:Добавить|Вставить|Очистить|ЗагрузитьЗначения)|ОтборСтрок(?:\s*\.\s*{NAME})?\s*\.\s*(?:Установить|Сбросить)|СоздатьКолонки|УстановитьПривязку|УстановитьТекст|Активизировать)\s*\(", re.I)
_P2_VALUE = re.compile(rf"{_START}(?P<chain>{_CHAIN})\s*\.\s*Значение\s*=(?![=>])", re.I)          # значение поля формы: на экране меняется само поле (в P4 не участвует)
_P2_BARE = re.compile(rf"{_START}(?P<prop>Заголовок|ТолькоПросмотр|Доступность)\s*=(?![=>])", re.I)          # свойство самой формы без владельца: только в модуле формы
_P2_ADD = re.compile(r"(?<![\wА-Яа-яЁё.])ЭлементыФормы\s*\.\s*(?:Добавить|Удалить)\s*\(", re.I)
_ROW_WORDS = frozenset({"текущиеданные", "текущаястрока"})
_P1_GLOBAL = re.compile(r"(?<![\wА-Яа-яЁё])(Предупреждение|Вопрос|Сообщить|Состояние|ОткрытьФорму|ВыбратьЭлемент|ВвестиЗначение|ВвестиЧисло|ВвестиСтроку|"
                        r"ВвестиДату|ПоказатьЗначение|ПоказатьПредупреждение|ПоказатьВопрос|ЗапуститьПриложение)\s*\(", re.I)
_P1_METHOD = re.compile(r"\.\s*(Открыть|ОткрытьМодально|Показать|ВыбратьЭлемент|ВыбратьИзСписка)\s*\(", re.I)
_P1_REPORT = re.compile(r"(?<![\wА-Яа-яЁё.])(?:Отчеты|Обработки)\s*\.\s*[\wА-Яа-яЁё]+\s*\.\s*Создать\s*\(", re.I)          # объект отчёта или обработки, созданный кодом: его вывод — окно
_P1_PRINT = re.compile(r"(?<![\wА-Яа-яЁё])(?:[\wА-Яа-яЁё]+\s*\.\s*)*(?P<name>(?:[\wА-Яа-яЁё]*Напечатать|Печать)[\wА-Яа-яЁё]*)\s*\(")          # вызов печати (`Печать(`, `НапечататьВнешнююФорму(`): печатная форма — окно; функция, которая лишь получает список печатных форм, — не печать
_P1_DIALOG = re.compile(r"(?<![\wА-Яа-яЁё])(ДиалогВыбораФайла|ДиалогВыбораКаталога)(?![\wА-Яа-яЁё])", re.I)
_DIALOG_VAR = re.compile(rf"(?<![\w.])(?P<name>{NAME})\s*=\s*Новый\s+(?:ДиалогВыбораФайла|ДиалогВыбораКаталога)", re.I)
_P1_SELECT = re.compile(rf"(?<![\wА-Яа-яЁё.])(?P<name>{NAME})\s*\.\s*Выбрать\s*\(\s*\)", re.I)          # `Диалог.Выбрать()`: окно выбора файла
_CHOICE_OPENER = re.compile(r"(?<![\wА-Яа-яЁё])(ПолучитьФормуВыбора|ОткрытьФормуВыбора|ВыбратьИзСписка)(?![\wА-Яа-яЁё])", re.I)
CHOICE_TOLERATED = frozenset({"открыть", "открытьмодально", "выбратьизсписка"})          # окно выбора значения поля — обычный выбор, а не частность (категория `choice`)
_P3_REFUSE = re.compile(r"(?<![\wА-Яа-яЁё.])Отказ\s*=\s*Истина", re.I)
_P3_CLOSE = re.compile(r"(?<![\wА-Яа-яЁё.])(?:ЭтаФорма\s*\.\s*)?Закрыть\s*\(", re.I)
_P3_WAIT = re.compile(r"(?<![\wА-Яа-яЁё])(?:Под|От)ключитьОбработчикОжидания\s*\(", re.I)
_P5 = re.compile(rf"(?P<chain>{_CHAIN})\s*\.\s*(?P<method>Очистить|Загрузить|ЗагрузитьКолонку|Заполнить|Удалить|Добавить|Вставить|Свернуть|Сдвинуть|Сортировать)\s*\(", re.I)
_P5_VALUE = re.compile(rf"(?P<chain>{_CHAIN})\s*\.\s*Значение\s*\.\s*(?P<method>Очистить|Загрузить|ЗагрузитьКолонку|Заполнить|Удалить|Добавить|Вставить|Сдвинуть|Сортировать|УстановитьАктивность)\s*\(", re.I)          # значение табличного поля, названного параметром или переменной
_STMT_NO_STANDARD = re.compile(r"^СтандартнаяОбработка\s*=\s*Ложь$", re.I)
_P5_SKIP = frozenset({"объект", "элементыформы", "этаформа", "значение", "текущиеданные", "текущаястрока", "этотобъект"})
_LOOP = re.compile(rf"Для\s+Каждого\s+(?P<name>{NAME})\s+Из\s+(?:ЭтаФорма\s*\.\s*)?(?:ЭлементыФормы|ЭтаФорма|ОформленияСтрок)(?![\wА-Яа-яЁё])", re.I)          # переменная цикла по элементам формы либо по ОформленияСтрок: её свойства — свойства элементов
_ALIAS = re.compile(rf"(?<![\w.])(?P<name>{NAME})\s*=\s*(?:ЭтаФорма\s*\.\s*)?(?:ЭлементыФормы|ЭтаФорма)(?![\wА-Яа-яЁё])", re.I)
_ASSIGN = re.compile(rf"{_START}(?P<chain>{_CHAIN})\s*=(?![=>])", re.I)
_KEYWORDS = frozenset(w.casefold() for w in ("Если", "Тогда", "Иначе", "ИначеЕсли", "КонецЕсли", "И", "Или", "Не", "Истина", "Ложь", "Неопределено", "Null", "Новый", "Цикл", "Для", "Каждого", "Из", "По",
                                              "Пока", "КонецЦикла", "Возврат", "Попытка", "Исключение", "КонецПопытки", "ЭтаФорма", "ЭлементыФормы", "Объект", "Значение", "ТекущиеДанные"))
INPUT_TYPES = frozenset({"TextBox", "ComboBox"})          # поле ввода и поле выбора
INPUTS_SHOWN = 12
OBJECT_LABEL = "модуль объекта"          # имя модуля объекта в признаках: в нём имя без префикса — реквизит объекта


def _is_end(masked):
    return bool(scan._END.match(masked))


def body_masked(lines, first, last):
    """Строки тела процедуры (`modulescan.scan`) между заголовком и `Конец…`: `[(номер, masked)]`; заголовок на нескольких строках пропускается до закрывающей скобки, `Перем` — тоже."""
    out, header = [], True
    for number, masked, _raw in lines:
        if number < first or number > last:
            continue
        if header:
            if ")" in masked or number > first + 6:
                header = False
            continue
        if _is_end(masked) or not masked.strip() or _VAR.match(masked):
            continue
        out.append((number, masked))
    return out


def statements(lines, first, last):
    """Операторы процедуры: тело без комментариев, склеенное в одну строку и разрезанное по `;` (содержимое литералов замаскировано)."""
    text = " ".join(masked.strip() for _n, masked in body_masked(lines, first, last))
    return [s.strip() for s in text.split(";") if s.strip()]


def skill_category(lines, first, last, opening=False):
    """Вид умолчания, который навык отмечает сам (`modified`, `empty`, `standard`), или `None`. `opening` — процедура события открытия: `Закрыть()` в ней отказ, а не стандартное действие."""
    stmts = [s for s in statements(lines, first, last) if not _STMT_IDLE.match(s)]
    if not stmts:
        return "empty"
    if all(_STMT_NO_STANDARD.match(s) for s in stmts):
        return "disabled"
    if all(_STMT_MODIFIED.match(s) for s in stmts):
        return "modified"
    if not opening and all(_STMT_MODIFIED.match(s) or _STMT_STANDARD.match(s) for s in stmts):
        return "standard"
    return None


def roots_of(lines, params=()):
    """Имена, через которые код обращается к элементам формы: `ЭлементыФормы`, `ЭтаФорма`, переменные-псевдонимы и переменные циклов по `ЭлементыФормы`, параметры процедуры."""
    out = {"элементыформы", "этаформа", "элемент"} | {str(p).casefold() for p in params if p}
    for _n, masked, _raw in lines:
        for pattern in (_ALIAS, _LOOP):
            for hit in pattern.finditer(masked):
                out.add(hit.group("name").casefold())
    return out


def _chain_has_row(chain):
    return any(token.casefold() in _ROW_WORDS for token in re.split(r"[.\[\]\s]+", chain))


def visual_assignments(masked, roots, form=False):
    """`[(слово, что)]` по строке: присваивание свойству элемента формы (П2) либо вызов метода элемента (`Кнопки.Добавить(`, `СписокВыбора.Очистить(`, `СоздатьКолонки(`);
    `form` — строка модуля формы: голое `Заголовок = …` — свойство самой формы."""
    out = []
    if form:
        out += [(hit.group("prop"), "присваивает свойство формы " + hit.group("prop")) for hit in _P2_BARE.finditer(masked)]
    for hit in _P2_ASSIGN.finditer(masked):
        chain = hit.group("chain")
        root = re.split(r"[.\[\s]", chain.strip(), maxsplit=1)[0].casefold()
        if root in roots and not _chain_has_row(chain):
            out.append((hit.group("prop"), "присваивает свойство " + hit.group("prop")))
    for hit in _P2_CALL.finditer(masked):
        chain = hit.group("chain")
        root = re.split(r"[.\[\s]", chain.strip(), maxsplit=1)[0].casefold()
        if root in roots and not _chain_has_row(chain):
            out.append((re.sub(r"\s+", "", hit.group("what")), "вызывает " + re.sub(r"\s+", "", hit.group("what"))))
    if _P2_ADD.search(masked):
        out.append(("ЭлементыФормы.Добавить", "создаёт или удаляет элемент"))
    return out


_LOOP_TABLE = re.compile(rf"Для\s+Каждого\s+(?P<var>{NAME})\s+Из\s+(?P<chain>{_CHAIN})\s+Цикл", re.I)


def _has_refusal_param(lines, number):
    """Процедура модуля, в которой стоит строка `number`, принимает параметр `Отказ`: `Отказ = Истина` в ней — отказ, а не обычная переменная."""
    for _name, params, first, last in scan.procedures_of(lines):
        if first <= number <= (last if last is not None else first):
            return any(str(p).casefold() == "отказ" for p in params)
    return False


def scan_lines(lines, spans, roots, tables, choice=False, label=None, own=frozenset()):
    """Признаки частности в строках `lines` (`modulescan.scan`) внутри диапазонов `spans`: `[{sign, word, line, where}]`; `tables` — имена таблиц формы и табличных частей без регистра;
    `choice` — процедура открывает форму выбора поля: окно выбора значения частностью не считается; `own` — таблицы самого обработчика (его строки меняют без признака П5);
    `label` — `None` для модуля формы: только в нём голое `Заголовок = …` — свойство формы."""
    found = []
    loops = {}
    dialogs = {m.group("name").casefold() for _n, masked, _raw in lines for m in _DIALOG_VAR.finditer(masked)}
    for number, masked, _raw in lines:
        if not any(a <= number <= b for a, b in spans) or not masked.strip() or scan._HEAD.match(masked) or _is_end(masked):
            continue
        for hit in _P1_GLOBAL.finditer(masked):
            found.append({"sign": "П1", "word": hit.group(1), "line": number, "where": label})
        for hit in _P1_METHOD.finditer(masked):
            if choice and hit.group(1).casefold() in CHOICE_TOLERATED:
                continue
            found.append({"sign": "П1", "word": hit.group(1), "line": number, "where": label})
        for _hit in _P1_REPORT.finditer(masked):
            found.append({"sign": "П1", "word": "Отчет.Создать()", "line": number, "where": label})
        for hit in _P1_PRINT.finditer(masked):
            found.append({"sign": "П1", "word": hit.group("name") + "()", "line": number, "where": label})
        for hit in _P1_DIALOG.finditer(masked):
            found.append({"sign": "П1", "word": hit.group(1), "line": number, "where": label})
        for hit in _P1_SELECT.finditer(masked):
            if hit.group("name").casefold() in dialogs or "диалог" in hit.group("name").casefold():
                found.append({"sign": "П1", "word": "Диалог.Выбрать()", "line": number, "where": label})
        for word, _what in visual_assignments(masked, roots, label is None):
            found.append({"sign": "П2", "word": word, "line": number, "where": label})
        for hit in _P2_VALUE.finditer(masked):
            chain = hit.group("chain")
            own_value = re.sub(r"\s+", "", chain).casefold() + ".значение"
            if re.split(r"[.\[\s]", chain.strip(), maxsplit=1)[0].casefold() in roots and not _chain_has_row(chain) and own_value not in re.sub(r"\s+", "", masked[hit.end():]).casefold():
                found.append({"sign": "П2", "word": "Значение", "line": number, "where": label})
        if _P3_REFUSE.search(masked) and _has_refusal_param(lines, number):
            found.append({"sign": "П3", "word": "Отказ = Истина", "line": number, "where": label})
        if _P3_CLOSE.search(masked):
            found.append({"sign": "П3", "word": "Закрыть()", "line": number, "where": label})
        if _P3_WAIT.search(masked):
            found.append({"sign": "П3", "word": "обработчик ожидания", "line": number, "where": label})
        p5_before = len(found)
        for hit in _P5.finditer(masked):
            tokens = [t.casefold() for t in re.split(r"[.\[\]\s]+", hit.group("chain")) if t and t.casefold() not in _P5_SKIP]
            hit_table = next((t for t in tokens if t in tables), None)
            if hit_table:
                found.append({"sign": "П5", "word": f"{hit.group('method')} таблицы {hit_table}", "line": number, "where": label})
        if len(found) == p5_before:
            for hit in _P5_VALUE.finditer(masked):
                chain = hit.group("chain")
                if re.split(r"[.\[\s]", chain.strip(), maxsplit=1)[0].casefold() in roots and not _chain_has_row(chain):
                    found.append({"sign": "П5", "word": f"{hit.group('method')} значения таблицы {re.split(r'[.[ ]', chain.strip(), maxsplit=1)[0] if '[' not in chain else 'по имени из переменной'}", "line": number, "where": label})
        for hit in _LOOP_TABLE.finditer(masked):
            tokens = [t.casefold() for t in re.split(r"[.\[\]\s]+", hit.group("chain")) if t and t.casefold() not in _P5_SKIP]
            hit_table = next((t for t in tokens if t in tables), None)
            if hit_table and hit_table not in own:
                loops[hit.group("var").casefold()] = hit_table          # цикл по строкам чужой таблицы формы: присваивание полю переменной цикла меняет её строки
        for hit in _ASSIGN.finditer(masked):
            tokens = re.split(r"[.\s]+", hit.group("chain").strip())
            if len(tokens) == 2 and tokens[0].casefold() in loops:
                found.append({"sign": "П5", "word": f"меняет строки таблицы {loops[tokens[0].casefold()]}", "line": number, "where": label})
    return found


def assignment_names(lines, spans):
    """`[(имя, строка, с префиксом Объект/ЭтаФорма)]` — простые присваивания `Имя = …`, `Объект.Имя = …`, `ЭтаФорма.Имя = …` (последнее звено цепочки) в диапазонах."""
    out = []
    for number, masked, _raw in lines:
        if not any(a <= number <= b for a, b in spans):
            continue
        for hit in _ASSIGN.finditer(masked):
            tokens = re.split(r"[.\s]+", hit.group("chain").strip())
            if len(tokens) == 1:
                out.append((tokens[0], number, False))
            elif len(tokens) == 2 and tokens[0].casefold() in ("объект", "этаформа", "этотобъект"):
                out.append((tokens[1], number, True))
    return out


def visual_inputs(lines, roots, spans=None, form=False):
    """Имена (без регистра), от которых зависит вид формы: слова условий `Если` и правых частей присваиваний, внутри которых код меняет свойство элемента (П2). Это общий словарь модуля:
    присваивание такому реквизиту в обработчике — П4."""
    conds = scan.conditions(lines)
    out = set()
    for number, masked, _raw in lines:
        if spans is not None and not any(a <= number <= b for a, b in spans):
            continue
        hits = visual_assignments(masked, roots, form)
        if not hits:
            continue
        text = conds.get(number, "") + " " + masked.split("=", 1)[-1]
        text = re.sub(r'"[^"]*"', " ", text)
        for word in re.findall(NAME, text):
            if word.casefold() not in _KEYWORDS and not word.isdigit():
                out.add(word.casefold())
    return out


def find_signs(targets, name, category=None):
    """Признаки частности процедуры `name` модуля формы: в ней, в процедурах модуля формы, которые она вызывает, и на один уровень в модуле объекта и общих модулях.
    `[{sign, word, line, where}]`: `where` — `None` (модуль формы) либо имя модуля; сначала модуль формы, по строке."""
    key = name.casefold()
    ranges = targets.procedure_ranges()
    if key not in ranges:
        return []
    reach = targets.reach([key])
    spans = [ranges[n] for n in reach if n in ranges]
    lines = targets.scanned()
    mod_roots = roots_of(lines)
    for n in reach:
        mod_roots |= {p.casefold() for p in re.findall(NAME, targets.procedure_params(ranges[n][0]) or "")}
    tables = targets.table_names
    choice = category == "choice" and any(_CHOICE_OPENER.search(m) for n, m, _r in lines if any(a <= n <= b for a, b in spans))
    own = targets.own_tables(key)
    found = scan_lines(lines, spans, mod_roots, tables, choice, None, own)
    inputs = targets.visual_inputs()
    data = targets.data_names
    fields = targets.bound_fields()
    for word, number, prefixed in assignment_names(lines, spans):
        if word.casefold() in inputs and (prefixed or word.casefold() in data):
            found.append({"sign": "П4", "word": word, "line": number, "where": None})
        elif word.casefold() in fields and (prefixed or word.casefold() in data):
            found.append({"sign": "П6", "word": word, "line": number, "where": None})
    first_level = targets.foreign_scopes(reach, ranges)
    columns = set().union(*targets.columns.values()) if targets.columns else set()
    deep = deep_scopes(targets, first_level)
    for text_lines, span_list, label, chains, bare in first_level + deep:
        foreign_roots = roots_of(text_lines) | ({"форма", "формаобъекта"} | _params_roots(text_lines, span_list) if not bare else set())          # голому вызову форму не передали: его параметры формой не считаются
        theirs = scan_lines(text_lines, span_list, foreign_roots, tables, choice, label, own)
        for word, number, prefixed in assignment_names(text_lines, span_list):
            if word.casefold() in inputs and (prefixed or (word.casefold() in data and label == OBJECT_LABEL)):          # имя без префикса — реквизит только в модуле объекта; в общем модуле это локальная переменная
                theirs.append({"sign": "П4", "word": word, "line": number, "where": label})
            elif word.casefold() in fields and (prefixed or (word.casefold() in data and label == OBJECT_LABEL)):
                theirs.append({"sign": "П6", "word": word, "line": number, "where": label})
        for column, number in param_assignments(text_lines, span_list, columns | (set() if bare else fields)):
            theirs.append({"sign": "П5", "word": f"присваивает «{column}»", "line": number, "where": label})
        for sign in theirs:
            chain = next((c for (a, b), c in chains.items() if a <= sign["line"] <= b), None)
            if chain and len(chain) > 1:
                sign["via"] = chain[:-1]          # процедуры от вызванной формой до той, где стоит признак (без неё самой)
            sign["deep"] = any(scope[0] is text_lines for scope in deep)          # второй уровень общих модулей: после признаков первого
        found += theirs
    found.sort(key=lambda s: (s.get("deep", False), s["where"] is not None, s["where"] or "", s["line"], s["sign"]))
    return found


def param_assignments(text_lines, spans, names):
    """`[(имя, строка)]` — присваивания `Параметр.Имя = …` в процедурах чужого кода (`spans`), где `Параметр` — параметр процедуры, а `Имя` (без регистра) — колонка таблицы формы или поле формы из `names`:
    процедура другого модуля, получившая строку, элемент или объект, меняет то, что показывает форма."""
    params = _params_roots(text_lines, spans)
    out = []
    for number, masked, _raw in text_lines:
        if not any(a <= number <= b for a, b in spans):
            continue
        for hit in _ASSIGN.finditer(masked):
            tokens = re.split(r"[.\s]+", hit.group("chain").strip())
            if len(tokens) == 2 and tokens[0].casefold() in params and tokens[1].casefold() in names:
                out.append((tokens[1], number))
    return out


def _calls_of(targets, text_lines, spans, label):
    """`[(модуль или None, процедура)]` — вызовы в процедурах `spans` чужого файла: `Модуль.Процедура(` общего модуля выгрузки и голое `Процедура(`, которой нет в этом файле (платформенные имена пропущены)."""
    own = {p[0].casefold() for p in scan.procedures_of(text_lines)}
    modules = targets.common_modules()
    out = []
    for number, masked, _raw in text_lines:
        if not any(a <= number <= b for a, b in spans) or scan._HEAD.match(masked):
            continue
        for hit in _HOP.finditer(masked):
            if hit.group("owner").casefold() in modules and hit.group("owner").casefold() != str(label).casefold():
                out.append((hit.group("owner"), hit.group("proc")))
        for hit in _BARE_CALL.finditer(masked):
            if hit.group("proc").casefold() not in own:
                out.append((None, hit.group("proc")))
    return out


def _resolved(targets, calls):
    """`({(модуль, процедура): (путь, первая, последняя строка)}, [не найденные «Модуль.Процедура» или «Процедура»])` — вызовы `calls` (`_calls_of`), найденные в общих модулях выгрузки."""
    from . import codetask          # поздний импорт: codetask сам читает этот модуль
    skip = codetask.BUILTINS | codetask.KEYWORDS | _PLATFORM
    found, lost = {}, []
    bare = {proc.casefold(): proc for owner, proc in calls if owner is None and proc.casefold() not in skip}
    where = codetask._find_many(targets.config_dir, set(bare)) if bare and targets.config_dir is not None else {}
    for owner, proc in dict.fromkeys(calls):
        if owner is None:
            if proc.casefold() in skip:
                continue
            hit = where.get(proc.casefold())
            if hit:
                found[(hit[1], proc)] = (hit[0], hit[2], hit[3])
            else:
                lost.append(proc)
        else:
            hit = scan.find_procedure(targets.config_dir, proc, owner) if targets.config_dir is not None else None
            if hit:
                found[(owner, proc)] = (hit[0], hit[2], hit[3])
            else:
                lost.append(f"{owner}.{proc}")
    return found, lost


def deep_scopes(targets, scopes):
    """Второй уровень чужого кода: процедуры общих модулей выгрузки, которые зовёт код `scopes` (`Targets.foreign_scopes`), с цепочкой вызовов внутри их файла. Форму им не передавали: параметры формой не считаются."""
    from . import codenotes          # поздний импорт: codenotes сам читает этот модуль
    key = tuple((id(lines), tuple(spans)) for lines, spans, _l, _c, _b in scopes)
    cache = targets.__dict__.setdefault("_deep", {})
    if key in cache:
        return cache[key]
    done = {(id(lines), tuple(r)) for lines, spans, _l, _c, _b in scopes for r in spans}
    out = []
    for text_lines, spans, label, _chains, _bare in scopes:
        found, _lost = _resolved(targets, _calls_of(targets, text_lines, spans, label))
        for (owner, _proc), (path, first, last) in found.items():
            lines = targets._foreign_lines(path)
            if lines is None or (id(lines), (first, last)) in done:
                continue
            done.add((id(lines), (first, last)))
            chains = codenotes.foreign_chains(lines, (first, last))
            out.append((lines, list(chains), owner, chains, True))
    cache[key] = out
    return out


_COLLECTIONS = frozenset({"колонки", "страницы", "кнопки"})


def chain_name(targets, chain):
    """Имя элемента формы, которое называет цепочка присваивания (`ЭлементыФормы.Номер`, `ЭлементыФормы.Товары.Колонки.Цена`): элемент, колонка, страница, кнопка; `None` — цепочка не про форму (строка таблицы,
    элемент по индексу, переменная, имя вне формы)."""
    tokens = [x for x in re.split(r"[.\[\]\s]+", chain) if x]
    if tokens and tokens[0].casefold() in ("элементыформы", "этаформа"):
        tokens = tokens[1:]
    if not tokens or any(x.casefold() in _ROW_WORDS for x in tokens):
        return None
    if len(tokens) >= 3 and tokens[1].casefold() in _COLLECTIONS:
        name = tokens[2]
    elif len(tokens) == 1:
        name = tokens[0]
    else:
        return None
    return name if name.casefold() in targets.fields | targets.page_names | targets.table_names else None


def visible_targets(targets, name, lines=None):
    """Видимые цели обработчика `name`: `[имя]` — то, что его тело и процедуры модуля формы, которые оно вызывает, меняют на экране: элементы, колонки, страницы и кнопки, которым код присваивает свойство
    или значение; поля, показывающие присваиваемые данные; колонки и поля, которые присваивает чужой код (`присваивает «Цена»`); окна и сообщения (`окно Вопрос`). Это поиск слов по тексту: запись
    обработчика называет каждую цель (`affects`) либо `why` — почему её не видно. `lines` — множество, в которое попадают номера строк модуля формы, чьи присваивания свойств названы целями целиком."""
    key = name.casefold()
    ranges = targets.procedure_ranges()
    if key not in ranges:
        return []
    spans = [ranges[n] for n in targets.reach([key]) if n in ranges]
    out = []
    for number, masked, _raw in targets.scanned():
        if not any(a <= number <= b for a, b in spans) or scan._HEAD.match(masked):
            continue
        hits = [h for pattern in (_P2_ASSIGN, _P2_VALUE) for h in pattern.finditer(masked)]
        names = [chain_name(targets, h.group("chain")) for h in hits]
        for found in names:
            if found and found not in out:
                out.append(found)
        if lines is not None and hits and all(names):
            lines.add(number)
    windows = []
    for sign in targets.signs(name):
        if sign["sign"] in ("П4", "П6") and not sign["where"] and sign["word"] not in out:
            out.append(sign["word"])
        elif sign["sign"] == "П5" and sign["word"].startswith("присваивает «"):
            found = sign["word"][len("присваивает «"):-1]
            if found not in out:
                out.append(found)
        elif sign["sign"] == "П1" and sign["word"] not in windows:
            windows.append(sign["word"])
    return out + ["окно " + w for w in windows]


def uncovered_targets(targets, accepted, name):
    """Цели обработчика `name` (`visible_targets`), которых нет ни в одной принятой записи с его процедурами: пусто, если записей `on_event` об обработчике нет вовсе (это «не разобрано», а не пропуск
    цели). Цель названа, когда она в `affects` эффекта, в цели записи или есть эффект-окно (`message`, `open_form`) для `окно …`."""
    key = name.casefold()
    ranges = targets.procedure_ranges()
    if key not in ranges:
        return []
    spans = [ranges[n] for n in targets.reach([key]) if n in ranges]
    mine = [n for n in accepted if any(a <= n["lines"][0] and n["lines"][1] <= b for a, b in spans)]
    if not any(n["kind"] == "on_event" for n in mine) or any(n.get("none_signs") for n in mine):          # «ничего не меняет» при признаке частности — свое предупреждение
        return []
    named, windows = set(), False
    for note in mine:
        target = note["target"]
        named |= {str(x).split("/")[-1].split(".")[-1].strip().casefold() for x in (target.get("element"), target.get("sub")) if x}
        for effect in note.get("effects") or ():
            named |= {a.split(".")[-1].strip().casefold() for a in effect["affects"]}
            windows = windows or effect["what"] in ("message", "open_form")
    return [x for x in visible_targets(targets, name) if (not windows if x.startswith("окно ") else x.casefold() not in named)]


def _params_roots(text_lines, spans):
    """Параметры процедур чужого модуля в диапазонах: форма и элемент приходят параметром."""
    out = set()
    for _name, params, first, last in scan.procedures_of(text_lines):
        if any(first >= a and (last or first) <= b for a, b in spans):
            out |= {str(p).casefold() for p in params if p}
    return out


def sign_text(sign, via=True):
    """Признак словами и местом: `Вопрос (533)`, `Видимость (Общий 12)`; `via` — с цепочкой процедур чужого файла («через А → Б»)."""
    where = f"{sign['where']} {sign['line']}" if sign.get("where") else str(sign["line"])
    if via and sign.get("via"):
        where += ", через " + " → ".join(sign["via"])
    if sign["sign"] == "П4":
        return f"присваивает {sign['word']} — от него зависит вид формы ({where})"
    return f"{sign['word']} ({where})"


def signs_text(signs, limit=2, via=True):
    """Несколько признаков одной строкой: все окна и сообщения (П1) — каждое слово; вместе с прочими (разные слова) не больше `limit` мест, остальные прочие — «…ещё N»."""
    seen, windows, other = set(), [], []
    for sign in sorted(signs, key=lambda s: s["sign"] != "П1"):          # окно и сообщение (П1) первыми и без обрезки: их «…ещё N» не прячет
        key = (sign["sign"], sign["word"], sign.get("where"))
        if key in seen:
            continue
        seen.add(key)
        (windows if sign["sign"] == "П1" else other).append(sign_text(sign, via))
    room = max(limit - len(windows), 0)          # окна занимают место первыми, но не обрезаются: «…ещё N» считает только прочие признаки
    return "; ".join(windows + other[:room]) + (f"; …ещё {len(other) - room}" if len(other) > room else "")


_BARE_CALL = re.compile(rf"(?<![\wА-Яа-яЁё.])(?P<proc>{NAME})\s*\(")


_PLATFORM = frozenset(w.casefold() for w in (
    "Строка", "Число", "Дата", "Формат", "СтрДлина", "Лев", "Прав", "Сред", "Найти", "СтрЗаменить", "СтрНайти", "СокрЛП", "СокрЛ", "СокрП", "ВРег", "НРег", "ТРег", "Тип", "ТипЗнч", "Тип",
    "Макс", "Мин", "Окр", "Цел", "Pow", "Sqrt", "ТекущаяДата", "НачалоДня", "КонецДня", "НачалоМесяца", "КонецМесяца", "Год", "Месяц", "День", "ПустаяСтрока", "ЗначениеЗаполнено",
    "Булево", "ЗаписьЖурналаРегистрации", "ОписаниеОшибки", "ИнформацияОбОшибке", "ВызватьИсключение", "ПолучитьПредставление", "Нрег", "Символ", "КодСимвола", "Base64Значение"))          # встроенные функции платформы: голый вызов с таким именем в общий модуль не ведёт


_HOP = re.compile(rf"(?<![\wА-Яа-яЁё.])(?P<owner>{NAME})\s*\.\s*(?P<proc>{NAME})\s*\(")


def unchecked_reason(targets, name):
    """Почему признаков процедуры `name` навыку не хватает для слова «без следа на экране», либо пустая строка: процедура (или вызываемые) зовёт общий модуль, которого нет в выгрузке, или код, лежащий
    в другом общем модуле, чем тот, что навык разобрал (поиск признаков идёт по модулю формы, по вызванной процедуре и её цепочке в её файле)."""
    key = name.casefold()
    ranges = targets.procedure_ranges()
    if key not in ranges:
        return ""
    reach = targets.reach([key])
    spans = [ranges[n] for n in reach if n in ranges]
    mapping = targets.mapping()
    missing = sorted({e["module"] for e in mapping.get("form_calls") or [] if e.get("no_module") and e.get("module") and any(a <= n <= b for n in e["lines"] for a, b in spans)}, key=str.casefold)
    if missing:
        return "модуля «" + "», «".join(missing[:3]) + "» нет в выгрузке"
    first_level = targets.foreign_scopes(reach, ranges)
    deep = deep_scopes(targets, first_level)
    hops = []
    for text_lines, span_list, label, _chains, _bare in first_level:          # вызов, которого в выгрузке нет, навык не прочитал
        hops += [name for name in _resolved(targets, _calls_of(targets, text_lines, span_list, label))[1] if "." in name and name not in hops]
    read = {(id(lines), tuple(r)) for lines, spans, _l, _c, _b in first_level + deep for r in spans}
    for text_lines, span_list, label, _chains, _bare in deep:          # код третьего уровня: второй уровень навык прочитал, дальше не идёт
        found, lost = _resolved(targets, _calls_of(targets, text_lines, span_list, label))
        hops += [f"{owner}.{proc}" for (owner, proc), (path, first, last) in found.items() if (id(targets._foreign_lines(path)), (first, last)) not in read and f"{owner}.{proc}" not in hops]
        hops += [name for name in lost if "." in name and name not in hops]
    if hops:
        return "вызывает код другого общего модуля: " + ", ".join(hops[:3]) + (f" и ещё {len(hops) - 3}" if len(hops) > 3 else "")
    return ""


def guess_category(targets, name, owner=None, event=""):
    """Вероятная категория умолчания для процедуры без признаков частности (подсказка заданию; решает модель): `rows`, `choice`, `linked`, `write` или `silent`."""
    key = name.casefold()
    ranges = targets.procedure_ranges()
    lines = targets.scanned()
    if key not in ranges:
        return "silent"
    spans = [ranges[n] for n in targets.reach([key]) if n in ranges]
    if "началовыбора" in str(event).casefold().replace(" ", "") and any(_CHOICE_OPENER.search(m) for n, m, _r in lines if any(a <= n <= b for a, b in spans)):
        return "choice"
    if owner == "column":
        return "rows"
    names = assignment_names(lines, [ranges[key]])
    inputs = {item.label().casefold() for item in targets.names.item_of.values() if item.type in INPUT_TYPES}
    if any(w.casefold() in inputs for w, _n, _p in names):          # связанные поля шапки — только поля ввода: эффект на надпись или другой элемент — частность
        return "linked"
    if any(re.search(r"(?<![\wА-Яа-яЁё.])Записать\s*\(", m, re.I) for n, m, _r in lines if any(a <= n <= b for a, b in spans)):
        return "write"
    return "silent"
