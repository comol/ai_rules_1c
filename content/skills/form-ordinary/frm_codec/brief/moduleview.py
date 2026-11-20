"""Слова записей разбора кода для обзора: переменные модуля, чистка условий и значений, безопасный пересказ текста модели.

Переменные модуля пользователю формы ничего не говорят: обзор не называет их ни в условии, ни в значении. Условие, которое без переменной не читается,
заменяется словами «по условию в коде, строка N»; скобочные пояснения модели, в которых стоит переменная или ссылка на строку, отбрасываются.
Текст модели о работе с учётными данными (пароль, учётная запись, строка соединения) в обзор не попадает: клаузы с такими словами вырезаются.
"""

import re

from . import modulescan as scan

NAME = scan.NAME
_DECLARE = re.compile(r"^\s*(?:Перем|Var)\s+(?P<names>.+?)\s*;", re.I)
_ASSIGN = re.compile(r"^\s*(?P<name>[\wА-Яа-яЁё]+)\s*=(?!=)")
_PAREN = re.compile(r"\s*\([^()]*\)")
_TECH_PAREN = re.compile(r"строк|вызов|процедур|переменн|модул|обработчик", re.I)
_SECRET = re.compile(r"встроенн\w+ учётн\w+|SQL-подключени|строк\w* соединения|\b(?:Pwd|UID|User\s*ID)\b|\*\*\*", re.I)
_MODULE_WORDS = re.compile(r"переменн\w+ модуля|в теле модуля", re.I)
LIMIT = 170          # знаков условия или текста модели в строке обзора


def module_variables(text, known=()):
    """Имена переменных модуля формы: объявленные `Перем` и присвоенные в теле модуля вне процедур (без регистра); имя из `known` (элементы формы, реквизиты) присвоением
    в теле переменной не становится. Модуля нет — пустое множество."""
    if not text:
        return set()
    known = {k.casefold() for k in known}
    from .purpose import parse_module
    procedures = parse_module(text)
    inside = set()
    for p in procedures:
        inside.update(range(p["line"], p["end"] + 1))
    found, assigned_names = set(), set()
    for number, masked, _raw in scan.scan(text):
        if number in inside or not masked.strip():
            continue
        declared = _DECLARE.match(masked)
        if declared:
            for part in declared.group("names").split(","):
                word = part.strip().split()
                if word:
                    found.add(word[0].casefold())
            continue
        assigned = _ASSIGN.match(masked)
        if assigned:
            assigned_names.add(assigned.group("name").casefold())
    return found | (assigned_names - known)


def mentions(text, variables):
    """Первая переменная модуля, названная в тексте, либо `None`."""
    for word in re.findall(NAME, text or ""):
        if word.casefold() in variables:
            return word
    return None


def shorten(text, limit=LIMIT):
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:—-")
    return cut + "…"


def scrub(text, variables):
    """Текст модели без имён переменных модуля: «через переменную X», «(X)» убираются; клауза, в которой имя осталось, и клауза «переменная модуля …» отбрасываются."""
    text = " ".join((text or "").split())
    for name in re.findall(NAME, text):
        if name.casefold() in variables:
            word = re.escape(name)
            text = re.sub(rf"\s*\(\s*{word}\s*\)", "", text)
            text = re.sub(rf",?\s*через переменную\s+{word}", "", text)
    clauses = [c.strip() for c in re.split(r";\s*", text) if c.strip()]
    kept = [c for c in clauses if not mentions(c, variables) and not re.match(r"переменн\w+ модуля", c, re.I)]
    return "; ".join(kept)


def safe_text(text, variables=()):
    """Текст модели без клауз об учётных данных (делится по «;») и без переменных модуля."""
    text = re.sub(r"\s*\(строк[аи]?\s+[\d–\-, и]+\)", "", " ".join((text or "").split()))          # «(строки 410–420)» читателю формы ничего не говорит
    parts = [p.strip() for p in re.split(r";\s*", text) if p.strip()]
    out = "; ".join(p for p in parts if not _SECRET.search(p))
    return scrub(out, variables) if variables else out


def condition(text, variables, line=None):
    """Условие записи словами для обзора: `(текст, ясно)`. Пустое условие — `("", True)`. Скобочные пояснения с переменной модуля или ссылкой на строку
    отбрасываются; если переменная остаётся в самом условии, смысла не извлечь — «по условию в коде, строка N» (`ясно` ложно)."""
    text = " ".join((text or "").split())
    if not text:
        return "", True

    def drop(match):
        inner = match.group(0)
        return "" if _TECH_PAREN.search(inner) or mentions(inner, variables) else inner
    text = _PAREN.sub(drop, text).strip(" ;,")
    text = re.sub(r"\s*\((?:при|после) [^()]*\)", "", text).strip(" ;,")          # «(при открытии и при изменении)» говорит, когда проверяется условие, а не в чём оно
    text = re.sub(r"^переменная модуля\s*:\s*", "", text, flags=re.I)
    if not text or mentions(text, variables):
        return (f"по условию в коде, строка {line}" if line else "по условию в коде"), False
    text = re.sub(r'"([^"]*)"', r"«\1»", safe_text(text))
    return shorten(text), True


def literal(value):
    """Значение-текст в кавычках целиком — без кавычек; иначе `None`."""
    value = (value or "").strip()
    if len(value) > 1 and value[0] == value[-1] == '"' and value.count('"') == 2:
        return value[1:-1]
    return None


def title_words(value, variables):
    """Значение заголовка словами: текст в кавычках — «текст»; `«текст» + выражение` — «текст…»; иное выражение (или переменная модуля) — `None`."""
    value = (value or "").strip()
    text = literal(value)
    if text is not None:
        return f"«{text}»"
    head = re.match(r'^"([^"]*)"\s*\+', value)
    if head and not mentions(head.group(0), variables):
        return f"«{head.group(1).rstrip()}…»"
    if value and '"' not in value and "+" not in value and (" " in value or value.endswith(":")) and not mentions(value, variables):
        words = re.sub(r"<([^>]*)>", lambda m: "…" if re.search(r"[().]", m.group(1)) else m.group(0), value)          # подстановка словами остаётся («<номер>»), вызов или путь — «…»
        return "«" + shorten(words, 110) + "»"          # описание текста словами, а не выражение
    return None
