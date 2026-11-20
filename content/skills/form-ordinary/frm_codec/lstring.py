"""Видимый текст локализованной строки: одно правило на рендер, раскладку, линтер, описание, досье и редактор.

Строка формы бывает на нескольких языках: члены `{"lang": "ru", "text": "…"}`. Член с кодом `"#"` — запись без языка (в корпусе она
стоит рядом с `ru` у 272 форм из 5 438, у 1 186 строк), и показывает платформа не её.

**Источник правила — наблюдение T108 в предприятии и конфигураторе (документ с подписью на двух языках)**: у строки `{"#","Надпись"},{"ru","Касса/Счет:"}`
предприятие и конфигуратор показывают `ru`; `"#"` не виден нигде; в конфигурации один язык, код `ru`. Что платформа покажет
при ином основном языке и у строки только из `"#"`, не проверялось: для них правило — допущение (основной язык; потом `ru`; потом
первый член не `"#"`; потом `"#"`).

Основной язык конфигурации знает только выгрузка (`Configuration.xml`, `DefaultLanguage`, код — в `Languages/<имя>.xml`); досье
ставит его на время сборки (`main_language`), без него действует правило без основного языка.
"""
import contextlib

from .edit.names import LANG, LS_ITEMS, TEXT

NO_LANGUAGE = "#"
DEFAULT_LANGUAGE = "ru"

_main = [None]


@contextlib.contextmanager
def main_language(code):
    """На время блока основной язык конфигурации — `code` (`None` — неизвестен)."""
    before = _main[0]
    _main[0] = code if isinstance(code, str) and code else None
    try:
        yield
    finally:
        _main[0] = before


def current_main():
    return _main[0]


def _members(block):
    items = block.get(LS_ITEMS) if isinstance(block, dict) else None
    return [m for m in items if isinstance(m, dict)] if isinstance(items, list) else []


def visible_member(block, main=None):
    """Член строки, который показывает платформа, либо `None` (членов нет). Порядок: член основного языка конфигурации (если он
    известен), `ru`, первый член не `"#"`, `"#"`."""
    members = _members(block)
    main = main if main is not None else _main[0]
    wanted = [main] if main and main != NO_LANGUAGE else []
    for code in wanted + [DEFAULT_LANGUAGE]:
        for member in members:
            if member.get(LANG) == code:
                return member
    for member in members:
        if member.get(LANG) != NO_LANGUAGE:
            return member
    return members[0] if members else None


def visible_text(block, main=None):
    """Видимый текст строки как лежит в файле, либо `None`: членов нет или у видимого нет текста."""
    member = visible_member(block, main)
    text = member.get(TEXT) if member is not None else None
    return text if isinstance(text, str) else None


def is_placeholder(block, main=None):
    """У строки нет текста, который показала бы платформа: членов нет, видимый член пуст либо это член `"#"` (имя, которое конфигуратор
    подставляет кнопке или подменю: «Подменю1», «Действие2», «Кн записать»). Для такой строки платформа берёт текст откуда-то ещё:
    у кнопки со стандартным действием — текст действия, у подменю, привязанного к стандартному набору, — название набора («Действия»,
    «Перейти»); см. `bar_platform` (наблюдения T109, T110)."""
    member = visible_member(block, main)
    if member is None:
        return True
    text = member.get(TEXT)
    return member.get(LANG) == NO_LANGUAGE or not isinstance(text, str) or not text.strip()
