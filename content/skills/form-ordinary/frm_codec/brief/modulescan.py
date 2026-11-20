"""Чтение текста модуля формы без разбора смысла: строки без комментариев, условия `Если`, границы процедур, файлы общих модулей выгрузки.

Лексика, а не язык: комментарии `//` отсечены, содержимое строковых литералов в `masked` заменено знаком `\\0` (длина строки не меняется), в `raw` оно осталось как есть;
регулярные выражения идут по `masked`, значения читаются из `raw` по тем же позициям. Что делает код, решает модель по `docs/brief-code.md`; здесь — только то,
что находится точным поиском: границы процедур, условие, в котором стоит строка, вызовы одной процедуры другой, файлы общих модулей.
"""
import pathlib
import re

NAME = r"[\wА-Яа-яЁё]+"
MASK = "\0"
_IF = re.compile(r"^\s*Если\b(?P<c>.*?)\bТогда\b", re.I)
_ELSIF = re.compile(r"^\s*ИначеЕсли\b(?P<c>.*?)\bТогда\b", re.I)
_ELSE = re.compile(r"^\s*Иначе\b\s*$", re.I)
_ENDIF = re.compile(r"^\s*КонецЕсли\b", re.I)
_HEAD = re.compile(r"^\s*(?:Процедура|Функция)\s+(?P<name>[\wА-Яа-яЁё]+)\s*\((?P<params>[^)]*)\)?", re.I)      # заголовок бывает на нескольких строках: скобка на первой не закрыта
_END = re.compile(r"^\s*Конец(?:Процедуры|Функции)\b", re.I)
_VAR = re.compile(r"(?:Перем|Var)\b", re.I)
SHOWN = 90          # знаков условия и выражения в перечне


def scan(text):
    """`[(номер строки, masked, raw)]` — строки модуля без комментариев; в `masked` содержимое литералов заменено `\\0`, длина обеих строк одна."""
    if isinstance(text, (bytes, bytearray)):
        text = bytes(text).decode("utf-8", errors="replace")
    text = text.lstrip("﻿")
    out, inside = [], False
    for number, line in enumerate(text.splitlines(), 1):
        if inside and line.lstrip().startswith("//"):
            out.append((number, "", ""))
            continue
        masked, raw, i = [], [], 0
        while i < len(line):
            char = line[i]
            if inside:
                if char == '"':
                    if line[i + 1:i + 2] == '"':
                        masked.append(MASK * 2)
                        raw.append('""')
                        i += 2
                        continue
                    inside = False
                    masked.append('"')
                else:
                    masked.append(MASK)
                raw.append(char)
                i += 1
                continue
            if char == "/" and line[i + 1:i + 2] == "/":
                break
            if char == '"':
                inside = True
            masked.append(char)
            raw.append(char)
            i += 1
        out.append((number, "".join(masked), "".join(raw)))
    return out


def _statement(masked):
    """Строка несёт код: не пустая и не объявление `Перем`, не директива препроцессора (`#Область`) и не `&`."""
    word = masked.strip()
    return bool(word) and not word.startswith(("#", "&")) and not _VAR.match(word)


def has_code(text):
    """В модуле есть процедуры, функции или операторы. Только BOM, пробелы, комментарии, `Перем` и `#Область` — кода нет: такой модуль для формы то же, что отсутствующий."""
    return any(_statement(masked) for _number, masked, _raw in scan(text))


def effective(text):
    """Текст модуля или `None`, если в нём нет кода (`has_code`)."""
    return text if text is not None and has_code(text) else None


def body_ranges(lines, spans):
    """`[(первая строка, последняя строка)]` кусков тела модуля: код вне процедур (основная программа выполняется при создании формы, до `ПередОткрытием`).
    `lines` — результат `scan`, `spans` — `[(первая, последняя)]` процедур; пустые строки, комментарии и `Перем` в кусок не входят, но не разрывают его."""
    out, current = [], None
    for number, masked, _raw in lines:
        if any(first <= number <= last for first, last in spans):
            if current is not None:
                out.append(tuple(current))
                current = None
        elif _statement(masked):
            current = [current[0] if current else number, number]
    if current is not None:
        out.append(tuple(current))
    return out


def conditions(lines):
    """`{номер строки: условие}` — условия `Если`, в которых стоит строка (внутреннее первым, через « И »); у строки вне условий записи нет. Стек сбрасывается на границе
    процедуры. Многострочное условие (`Тогда` на следующей строке) не читается: такая строка условия не даёт."""
    out, stack = {}, []
    for number, masked, raw in lines:
        if _HEAD.match(masked) or _END.match(masked):
            stack = []
            continue
        match = _IF.match(masked)
        if match:
            stack.append(raw[match.start("c"):match.end("c")].strip())
            continue
        match = _ELSIF.match(masked)
        if match and stack:
            stack[-1] = raw[match.start("c"):match.end("c")].strip()
            continue
        if _ELSE.match(masked) and stack:
            stack[-1] = "НЕ (" + stack[-1] + ")"
            continue
        if _ENDIF.match(masked):
            if stack:
                stack.pop()
            continue
        if stack:
            out[number] = " И ".join(reversed(stack))
    return out


def shorten(text, limit=SHOWN):
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def procedures_of(lines):
    """`[(имя, параметры, первая строка, последняя строка)]` процедур и функций модуля (по `scan`)."""
    out, current = [], None
    for number, masked, _raw in lines:
        head = _HEAD.match(masked)
        if head:
            if current is not None:
                out.append(current)
            current = [head.group("name"), [p.strip().split("=")[0].replace("Знач ", "").strip() for p in head.group("params").split(",") if p.strip()], number, None]
        elif _END.match(masked) and current is not None:
            current[3] = number
            out.append(current)
            current = None
    if current is not None:
        current[3] = lines[-1][0] if lines else current[2]
        out.append(current)
    return [tuple(p) for p in out]


def _procedure_at(procs, number):
    for name, _params, first, last in procs:
        if first <= number <= (last if last is not None else first):
            return name
    return None


def _module_files(config_dir):
    """`[(путь, имя модуля)]` модулей выгрузки, где живут процедуры, видимые форме: общие модули и модули верхнего уровня (`Ext/*.bsl`)."""
    root = pathlib.Path(config_dir)
    out = []
    for path in sorted(root.glob("CommonModules/*/Ext/Module.bsl")):
        out.append((path, path.parent.parent.name))
    for path in sorted((root / "Ext").glob("*.bsl")) if (root / "Ext").is_dir() else ():
        out.append((path, path.stem))
    return out




def call_args(masked, start):
    """Текст между скобками вызова, чья открывающая скобка стоит на `start - 1`, до парной скобки в этой же строке; `None` — скобка в строке не закрыта."""
    depth = 1
    for i in range(start, len(masked)):
        if masked[i] in "([":
            depth += 1
        elif masked[i] in ")]":
            depth -= 1
            if depth == 0:
                return masked[start:i]
    return None


def find_procedure(config_dir, name, module=None):
    """`(путь файла, имя модуля, первая строка, последняя строка)` первой процедуры или функции `name` в общих модулях и модулях верхнего уровня выгрузки; `module` сужает поиск
    одним модулем. Нет такой — `None`."""
    wanted = name.casefold()
    for path, mod in _module_files(config_dir):
        if module and mod.casefold() != module.casefold():
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        if wanted not in text.casefold():
            continue
        for proc in procedures_of(scan(text)):
            if proc[0].casefold() == wanted:
                return path, mod, proc[2], proc[3] if proc[3] is not None else proc[2]
    return None
