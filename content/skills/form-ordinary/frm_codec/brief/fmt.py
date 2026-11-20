"""Мелкая запись текста досье: перечни с «и ещё N», ячейки и таблицы markdown, доли, названия показателей и видов форм."""

from .. import lint
from . import vocab


def _list(names, limit=vocab.LISTED):
    names = list(names)
    text = ", ".join(str(n) for n in names[:limit])
    return text + (f" и ещё {len(names) - limit}" if len(names) > limit else "")


def _quoted(names, limit=vocab.LISTED):
    names = list(names)
    text = ", ".join(f"«{n}»" for n in names[:limit])
    return text + (f" и ещё {len(names) - limit}" if len(names) > limit else "")


def _cell(value):
    """Ячейка таблицы markdown: без переносов и вертикальных черт."""
    return "" if value is None else str(value).replace("|", "/").replace("\n", " ")


def _pct(share):
    value = round(share * 100, 1)
    return (f"{value:.0f}" if value == int(value) else f"{value:.1f}".replace(".", ",")) + " %"


def _table(head, rows):
    lines = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    lines += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return lines


def _title(description):
    return (description or {}).get("title")


def _measure_label(key):
    return lint.RHYTHM.get(key) or vocab.ANCHOR_LABELS.get(key) or (vocab.GAP_LABEL if key == "label_text_gap" else key)


def _kind_words(kind):
    if kind in vocab.KIND_WORDS:
        return vocab.KIND_WORDS[kind]
    if kind == "other:CommonForms":
        return "общая форма"
    if kind.startswith("other:"):
        return f"форма прочего вида ({kind[6:]})"
    return kind
