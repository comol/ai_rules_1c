"""Усечение подписи с «…»: рендер рисует подпись в пределах её прямоугольника, как это делает платформа.

Ширина считается по `textwidth` (Microsoft Sans Serif, целые ширины для 11 px): ширина строки равна сумме ширин знаков, а «…»
имеет ширину 6. Никакого порога нет.

Подпись помещается, если её ширина не больше ширины надписи. Иначе берётся самое длинное начало подписи, у которого начало
вместе с «…» помещается: «Номер» в 33 px превращается в «Ном…». Если в подписи есть знак, которого нет в таблице
`textwidth`, рендер сообщает, что ширина не проверена (`измерена` равно ложь), и такая подпись не усекается.
"""

from .. import textwidth

ELLIPSIS = "…"


def width(text):
    """Возвращает `(ширина в px, есть ли знак вне таблицы)`."""
    return float(sum(textwidth.ADVANCE.get(ch, 0) for ch in text)), any(ch not in textwidth.ADVANCE for ch in text)


def fit(text, avail, font=None, keep_space=False):
    """Возвращает `(строка, усечена ли, проверена ли ширина)`: подпись в `avail` px либо её начало с «…». Если в строке есть знак вне
    таблицы, она не усекается, и ширина считается непроверенной. Если не помещается даже «…», возвращается пустая строка.

    Параметр `font` — описание действующего шрифта элемента (`textwidth.element_font`). Ширина вычисляется функцией
    `textwidth.measure` для этого шрифта: размер берётся по ppem, у жирного шрифта добавляется 1 px на знак, а «…» измеряется
    тем же шрифтом (у жирного оно равно 7). Признак проверенности тогда зависит ещё и от шрифта (`Measured.exact`): для
    непроверенного шрифта усечение выполняется по оценке ширины, а причину сообщает вызывающий код. Без `font` используется
    обычный шрифт 11 px.
    """
    if font is None:
        full, unknown = width(text)
        dots = width(ELLIPSIS)[0]
        wide = lambda s: width(s)[0]
        exact = True
    else:
        unknown = any(ch not in textwidth.ADVANCE for ch in text)
        full = textwidth.measure(text, font).px
        dots = textwidth.measure(ELLIPSIS, font).px
        wide = lambda s: textwidth.measure(s, font).px
        exact = textwidth.measure(text, font).exact
    if unknown:
        return text, False, False
    face = (font or {}).get("face")
    if face and face not in textwidth.MEASURED_FACES:
        # гарнитура переопределена (Arial и др.): таблицы ширин у неё нет, оценка по Microsoft Sans Serif на 10 % выше настоящей (Arial 11 полужирный: «МАРКИРОВКА ЯЧЕЕК»
        # на экране 157 px, по оценке 175) — усечение по такой оценке врало бы, подпись остаётся целой, ширина «не измерена»
        return text, False, False
    if full <= avail:
        return text, False, exact
    for n in range(len(text) - 1, 0, -1):
        head = text[:n] if keep_space else text[:n].rstrip()
        if wide(head) + dots <= avail:
            return head + ELLIPSIS, True, exact
    return (ELLIPSIS, True, exact) if dots <= avail else ("", True, exact)


def wrap(text, avail, font=None, max_lines=2):
    """Перенос подписи по словам в `avail` px: `[строка, …]` не длиннее `max_lines` (так переносит текст надпись, чья высота вмещает
    несколько строк). Слово берётся целиком, пока строка с ним помещается; слово шире `avail` рвётся по знакам. Явный перевод строки
    в тексте начинает новую строку. Что не поместилось в последнюю строку, усекается с «…» (`fit`). Ширина — как у `fit`: для знака
    вне таблицы строка не усекается и не переносится (ширина не проверена): возвращаются строки текста между переводами строк — подпись как есть.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if any(ch not in textwidth.ADVANCE and ch != "\n" for ch in text):
        paragraphs = text.split("\n")      # ширина не известна: по словам не переносится и не усекается, но явный перевод строки начинает строку
        return paragraphs[:max_lines - 1] + [" ".join(paragraphs[max_lines - 1:])] if len(paragraphs) > max_lines else paragraphs
    wide = (lambda s: textwidth.measure(s, font).px) if font is not None else (lambda s: width(s)[0])
    lines, rest = [], text
    while rest is not None:
        if len(lines) == max_lines - 1:  # последняя строка: всё остальное одной строкой, лишнее — «…»
            lines.append(fit(rest.replace("\n", " "), avail, font)[0])
            break
        head, sep, after = rest.partition("\n")
        words, line, left = head.split(" "), "", None
        for i, word in enumerate(words):
            trial = word if not line else line + " " + word
            if wide(trial) <= avail:
                line = trial
                continue
            if line:
                left = " ".join(words[i:])
                break
            cut = next((n for n in range(len(word) - 1, 0, -1) if wide(word[:n]) <= avail), 1)  # слово шире строки — по знакам
            line, left = word[:cut], " ".join([word[cut:]] + words[i + 1:])
            break
        lines.append(line)
        if left is not None:
            rest = left + ("\n" + after if sep else "")
        else:
            rest = after if sep else None
    return lines
