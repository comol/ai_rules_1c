"""Видимый зазор «конец текста надписи → поле» и состав даты поля ввода.

Рамка надписи и текст в ней — разные вещи: надпись шире своего текста на запас, а у надписи с выравниванием по правому краю или по
центру текст стоит не у левого края рамки. Глаз видит зазор от конца текста до поля, поэтому нормы и новая пара считаются по нему
(`label_text_gap` в `patterns.json`).

* `label_text_end` — x конца текста надписи. Только для надписи в одну строку, текст которой помещается в рамку; без `estimate` — только
  по проверенному шрифту (`textwidth.measure` с `exact`), иначе `None`: по оценке ширины норма и замечание линтера не строятся.
  Пробелы не в сторону текста (в конце — у надписи слева, в начале — у надписи справа) не считаются. Конец текста у надписи, выровненной вправо,
  принят у правого края рамки (не проверялось: рендер рисует на 2 px левее).
* `date_composition` — состав даты у поля ввода, чей описатель типа — один блок `D`: `Date`, `Time` или `DateTime`.
"""
from . import textwidth
from .edit import cowrites, names as N

LABEL_WRAP_LINES = 2  # надпись высотой от стольких строк переносит текст по словам: конец текста у неё не одна точка
LINE_EXTRA = 4        # высота строки подписи = ppem шрифта + столько (как в линтере подписей)
DATE_LETTERS = {"D": "Date", "T": "Time"}  # буква состава в описателе типа; без буквы — `DateTime` (`edit.datatype.DATE_BY_LETTER`)


def wraps(box, font):
    """Надпись такой высоты переносит текст по словам (высота от `LABEL_WRAP_LINES` строк): у неё нет одной точки конца текста, и зазор до поля не считается."""
    return box[3] - box[1] >= LABEL_WRAP_LINES * (textwidth.ppem_of(font.get("size") or textwidth.DEFAULT_SIZE) + LINE_EXTRA)


def alignment(node):
    """Выравнивание подписи надписи по карте (`content/u1/horizontal_align`): `Left`, `Right`, `Center`; нет значения — `Left`."""
    block = node.get(N.CONTENT) if isinstance(node, dict) else None
    block = block.get("u1") if isinstance(block, dict) else None
    value = block.get("horizontal_align") if isinstance(block, dict) else None
    return value if value in ("Right", "Center") else "Left"


def text_end(left, width, need, align):
    """x конца текста шириной `need` в рамке `[left, left + width]`: слева — `left + need`, справа — правый край рамки, по центру — её
    середина плюс половина текста (целое вниз). Текст шире рамки в предприятии усекается — виден он до края рамки.
    """
    need = min(need, width)
    if align == "Right":
        return left + width
    if align == "Center":
        return left + (width + need) // 2
    return left + need


def _single_line(node, doc, box):
    """`(текст без лишних пробелов, шрифт, выравнивание)` надписи в одну строку, не переносящей текст, либо `None`."""
    from . import render
    align = alignment(node)
    text = render.caption_text(node, "Label")
    text = text.rstrip() if align == "Left" else text.lstrip() if align == "Right" else text.strip()
    if not text or "\n" in text or "\r" in text:
        return None
    font = textwidth.element_font(node, doc)
    return None if wraps(box, font) else (text, font, align)


def label_text_end(node, doc, box, estimate=False):
    """`(x конца текста, ширина текста, проверен ли шрифт)` надписи в рамке `box` либо `None`: подписи нет, она в несколько строк, надпись
    переносит текст (`wraps`) или текст шире рамки (усечён либо перенесён — одной точки конца нет, `clipped`). Шрифт не проверялся — `None`, а
    с `estimate=True` — оценка ширины (третье значение ложно): нормы и линтер оценкой не пользуются, новая пара без другого выхода пользуется
    и говорит об этом в отчёте.
    """
    got = _single_line(node, doc, box)
    if got is None:
        return None
    text, font, align = got
    measured = textwidth.measure(text, font)
    if (not measured.exact and not estimate) or measured.px > box[2] - box[0]:
        return None
    return text_end(box[0], box[2] - box[0], measured.px, align), measured.px, measured.exact


def clipped(node, doc, box):
    """Текст надписи в одну строку шире её рамки (по оценке ширины): рамка колонки тесна, запаса за текстом у такой надписи нет."""
    got = _single_line(node, doc, box)
    return got is not None and textwidth.measure(got[0], got[1]).px > box[2] - box[0]


def date_composition(node):
    """Состав даты поля ввода: `Date`, `Time`, `DateTime`, а у поля не на дату (и у составного типа) — `None`."""
    content = node.get(N.CONTENT) if isinstance(node, dict) else None
    pattern = content.get(N.TEXTBOX_PATTERN) if isinstance(content, dict) else None
    types = pattern.get(N.PATTERN_TYPES) if isinstance(pattern, dict) else None
    if not isinstance(types, list) or len(types) != 1 or not isinstance(types[0], dict) or types[0].get(N.PATTERN_KIND) != "D":
        return None
    letter = types[0].get(cowrites.PATTERN_DATE)
    return DATE_LETTERS.get(letter) if letter is not None else "DateTime"


def _find_key(node, key):
    """Все значения под ключом `key` на любой глубине узла (словари и списки)."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                yield v
            else:
                yield from _find_key(v, key)
    elif isinstance(node, list):
        for v in node:
            yield from _find_key(v, key)


def is_multi_line(node):
    """Поле ввода в многострочном режиме (`multi_line` — истина в блоке значения поля). Одно правило для переписи норм (`census`), линтера и `describe`."""
    return any(v is True for v in _find_key(node, cowrites.MULTI_LINE))
