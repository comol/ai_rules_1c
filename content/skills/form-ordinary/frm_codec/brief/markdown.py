"""Запись `brief.md` (обзор) и `brief-full.md` (подробности по запросу `--detail`)."""

import re

from . import editing
from .head import _md_head
from .purpose import _md_purpose, md_code_section
from .outline import _md_structure, md_columns
from .behavior import _md_behavior
from .norms import _md_norms
from .style import _md_style
from .facts_section import _md_facts
from .pictures import _md_images
from .overview import composition_lines, render_overview

DETAIL_PARTS = ("structure", "columns", "facts", "norms", "style", "editing", "code")
DETAIL_WORDS = {"structure": "объект, дерево узлов, таблица элементов, панели кнопок, растяжение окна, картинки",
                "columns": "колонки таблиц", "facts": "факты для оценки", "norms": "нормы вида", "style": "стиль конфигурации",
                "editing": "ограничения правки, имена в коде, примеры", "code": "модуль формы: обработчики, что код меняет, события, связи"}


def render_md(brief, parts=None):
    """Обзор формы (`brief.md`), когда `parts` не названы; иначе подробности названных частей (`DETAIL_PARTS`) — текст `brief-full.md`."""
    if parts is None:
        return _without_variables(render_overview(brief), brief)
    return render_detail(brief, parts)


def render_detail(brief, parts):
    head, purpose = brief["head"], brief["purpose"]
    parts = set(parts)
    lines = [f"# Досье формы, подробности: {head['form']}", "",
             "Обзор формы — `brief.md`; здесь разделы, которые попросили ключом `--detail`: " + ", ".join(p for p in DETAIL_PARTS if p in parts) + ".", ""]
    lines += _md_head(head)
    if "structure" in parts:
        lines += _md_purpose(purpose, head, brief["structure"], module=False)
        lines += composition_lines(brief)
    if "code" in parts:
        lines += md_code_section(purpose, brief["structure"])
    if "structure" in parts:
        lines += _md_structure(brief["structure"], brief["images"], purpose["module"])
    if "columns" in parts:
        lines += md_columns(brief["structure"])
    if "structure" in parts:
        lines += _md_behavior(brief["behavior"])
    if "norms" in parts:
        lines += _md_norms(brief["norms"])
    if "style" in parts:
        lines += _md_style(brief["style"], brief["norms"], brief["behavior"]["resize_forbidden"])
    if "facts" in parts:
        lines += _md_facts(brief["facts"], brief["facts_checked"])
    if "structure" in parts:
        lines += _md_images(brief["images"])
    if "editing" in parts:
        lines += editing.md_lines(brief["editing"])
    return _without_variables("\n".join(lines).rstrip("\n") + "\n", brief)


def _without_variables(text, brief):
    """Подробности не называют переменные модуля (приватное состояние кода): имя заменено на «…». Имя, которое одновременно реквизит формы или элемент, остаётся — это имя данных, а не переменной."""
    module = brief["purpose"]["module"]
    known = {n.casefold() for n in brief["purpose"].get("form_attributes") or ()} | {e["short"].casefold() for e in brief["structure"]["elements"]} | {e["element"].casefold() for e in brief["structure"]["elements"]}
    names = [v for v in module.get("variables") or () if v.casefold() not in known]
    if not names:
        return text
    pattern = re.compile(r"(?<![\wА-Яа-яЁё])(?:" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")(?![\wА-Яа-яЁё])", re.I)
    return pattern.sub("…", text)
