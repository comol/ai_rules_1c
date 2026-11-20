"""Проверка подписей по итоговой форме: ширина и зазор «текст надписи → поле» после ВСЕХ операций перечня.

`set_caption` в перечне операций сам подпись не измеряет (`edit.ops.apply(final_captions=True)`): следующая операция (`move_element`, `set_property`) могла
расширить элемент или подвинуть поле, и замечание по промежуточной форме пугало бы зря. Измерение делается здесь, один раз, по форме, какой она будет записана.
"""
from .base import EditError, find_element


def caption_lines(doc, elements, original=None, rel="", kind=None):
    """Строки для конца отчёта `edit`: `[строка]`. `elements` — имена, чьи подписи правил `set_caption`; `original` — форма до правки (зазор, которого у неё не было)."""
    from .. import lint
    from . import font
    names = list(dict.fromkeys(elements))
    if not names:
        return []
    problems, checked = [], 0
    for name in names:
        try:
            place = find_element(doc, name)
        except EditError:
            continue                      # элемент убран или переименован следующей операцией: проверять нечего
        checked += 1
        words = font.new_text_words(font.node_fit(doc, place.element))
        if words:
            problems.append(f"«{name}»{words}")
    gaps = _gap_remarks(lint.lint(doc, rel, kind=kind))
    if original is not None:
        known = set(_gap_remarks(lint.lint(original, rel, kind=kind)))
        gaps = [g for g in gaps if g not in known]
    problems += gaps
    head = f"Подписи по итоговой форме (правили set_caption: {len(names)})"
    if not problems:
        return [f"{head}: помещаются, зазор «текст надписи → поле» не меньше нормы"]
    return [f"{head}:"] + [f"  {p}" for p in problems]


def _gap_remarks(result):
    return [remark.text for remark in result.remarks if remark.rule == "rhythm:label_text_gap"]
