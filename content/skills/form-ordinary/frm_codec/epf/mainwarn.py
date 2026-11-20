"""Предупреждение `epf-copyinfo`: у обычной формы нет основного реквизита, а её модуль вызывает экспортные методы модуля обработки.

Основной реквизит обычной формы обработки (`main_attribute_id`) — `ОбработкаОбъект`: через него модуль формы видит реквизиты и экспортные
процедуры и функции модуля обработки. Форма без основного реквизита их не видит, и вызов по голому имени при открытии формы не компилируется
(«Процедура или функция с указанным именем не определена»). Команда не отказывает — форма-диалог без основного реквизита бывает, — а
называет вызовы.

Модуль обработки — элемент `<GUID корня>.0` внешнего контейнера: вложенный контейнер с текстом `text` (UTF-8 с меткой порядка байтов). Вызов —
голое имя перед скобкой: не после точки; комментарии (`//`), строки (`"…"` с `""`, продолжения `|` внутри строки), даты (`'…'`), директивы
компиляции (`&…`) и строки препроцессора (`#…`) в счёт не идут; имя, объявленное процедурой или функцией в самом модуле формы, — тоже.
Экспортные методы обработки — объявления `Процедура|Функция Имя(…) Экспорт` (параметры могут переноситься, иметь `Знач` и значения по
умолчанию). Регистр имён не различается."""
import re

from . import container as cont
from . import meta as meta_mod
from .container import EpfError

MAX_NAMES = 10
_DECL = re.compile(r"(?<![\w.])(?:Процедура|Функция|Procedure|Function)\s+(\w+)\s*\(([^)]*)\)\s*(Экспорт|Export)?(?![\w])", re.I | re.S)
_CALL = re.compile(r"(\w+)\s*\(")
UNREAD = "{module} не прочитан: вызовы не проверены"
ABSENT = object()      # в контейнере нет элемента модуля объекта: экспортных методов нет


def blank_out(text):
    """Текст модуля, где комментарии, строки, даты и строки директив и препроцессора заменены пробелами (переносы строк остаются).
    Строка, начатая с `&`, гасится целиком: директива с объявлением на одной строке не проверялась (собственная процедура формы тогда не будет
    видна). Скобки и кавычки строки сохраняются парой, чтобы разбор объявлений видел значение по умолчанию как `""`."""
    out, i, n = [], 0, len(text)
    line_start = True
    while i < n:
        c = text[i]
        if c == "\n":
            out.append(c)
            i += 1
            line_start = True
            continue
        if line_start and c in " \t\r":
            out.append(c)
            i += 1
            continue
        if line_start and c in "#&":
            while i < n and text[i] != "\n":
                out.append(" ")
                i += 1
            continue
        line_start = False
        if c == "/" and text[i:i + 2] == "//":
            while i < n and text[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if c == '"':
            out.append('"')
            i += 1
            while i < n:
                if text[i] == '"':
                    if text[i + 1:i + 2] == '"':
                        out.append("  ")
                        i += 2
                        continue
                    break
                out.append("\n" if text[i] == "\n" else " ")
                i += 1
            out.append('"')
            i += 1
            continue
        if c == "'":
            end = text.find("'", i + 1)
            nl = text.find("\n", i + 1)
            if end != -1 and (nl == -1 or end < nl):
                out.append(" " * (end - i + 1))
                i = end + 1
                continue
        out.append(c)
        i += 1
    return "".join(out)


def exported(text):
    """Экспортные методы модуля: `{имя в нижнем регистре: имя как объявлено}`."""
    return {m.group(1).lower(): m.group(1) for m in _DECL.finditer(blank_out(text)) if m.group(3)}


def declared(text):
    """Все методы модуля (экспортные и нет): множество имён в нижнем регистре."""
    return {m.group(1).lower() for m in _DECL.finditer(blank_out(text))}


def bare_calls(text):
    """Имена, за которыми идёт скобка и перед которыми нет точки, в порядке первого появления: `{нижний регистр: как написано}`."""
    clean = blank_out(text)
    found = {}
    for m in _CALL.finditer(clean):
        at = m.start() - 1
        while at >= 0 and clean[at] in " \t\r\n":
            at -= 1
        if at >= 0 and clean[at] == ".":
            continue
        found.setdefault(m.group(1).lower(), m.group(1))
    return found


def object_module(container, root_guid):
    """Текст модуля обработки; `ABSENT`, если элемента `<корень>.0` в контейнере нет (модуля объекта нет); `None`, если элемент есть, но не прочитан."""
    item = container.get(f"{root_guid}.0")
    if item is None:
        return ABSENT
    try:
        inner = cont.read(item.data)
        text = inner.get("text")
        return None if text is None else text.data.decode("utf-8-sig")
    except (EpfError, UnicodeDecodeError):
        return None


def main_attribute_id(form_text):
    from .. import typed
    from ..tree import parse
    try:
        return typed.decode(parse(form_text))["attributes"].get("u0", {}).get("main_attribute_id")
    except Exception:  # noqa: BLE001 — разбор формы уже прошёл в copyinfo; здесь сбой значит «основной реквизит неизвестен»
        return None


def warnings(proc):
    """Строки предупреждений по формам процессинга без основного реквизита."""
    lines = []
    candidates = [g for g, text in proc.forms.items() if main_attribute_id(text) == -1]
    if not candidates:
        return lines
    module = object_module(proc.container, proc.meta.root)
    if module is ABSENT:
        return lines          # модуля объекта нет — вызывать нечего
    methods = exported(module) if module is not None else None
    report = proc.meta.objs[proc.meta.root][0][0] == meta_mod.CLASS_ROOT_REPORT
    word = "модуль отчёта" if report else "модуль обработки"
    genitive = "модуля отчёта" if report else "модуля обработки"
    for guid in candidates:
        name = proc.form_names.get(guid, guid)
        if methods is None:
            lines.append(f"Предупреждение: у формы {name} нет основного реквизита, {UNREAD.format(module=word)}.")
            continue
        text = proc.form_modules.get(guid, "")
        own = declared(text)
        calls = [methods[k] for k in bare_calls(text) if k in methods and k not in own]
        if not calls:
            continue
        shown = ", ".join(calls[:MAX_NAMES]) + (f" и ещё {len(calls) - MAX_NAMES}" if len(calls) > MAX_NAMES else "")
        way = ("собрать форму с основным реквизитом (new report --root-xml или --type-id, затем generate --form) либо назначить «Данные» формы в Конфигураторе" if report else
               "собрать форму с основным реквизитом (new processing --root-xml или --type-id, затем generate --form) либо назначить «Данные» формы в Конфигураторе")
        lines.append(f"Предупреждение: у формы {name} нет основного реквизита, а её модуль вызывает экспортные методы {genitive}: {shown} — "
                     f"без основного реквизита они не определены, и форма при открытии не компилируется. Выход: {way}. "
                     "Запись copyinfo от этого не меняется.")
    return lines
