"""Токенизатор скобочного файла form.frm.

Скаляров пять видов: целое, дробное (текст хранится дословно), строка в кавычках (кавычка внутри удваивается, перевод строки
внутри допускается), GUID без кавычек и блок `#base64:` на много строк. Любой другой текст без кавычек вызывает отказ с
указанием адреса.

Дробное число может быть записано и с экспонентой (`1e2`, `1.4e2`, `1.05000000000000e-1`): экспонента, как и точка, делает
число дробным.

Лексема блока `#base64:` содержит ещё и раскладку — то, как тело разложено по строкам. Само тело хранится в чистом виде, но
блок нужно записывать обратно теми же байтами. Раскладок три, и опознаёт их писатель тела (`b64_body`): читатель и писатель
используют одну и ту же функцию.
"""
import re
from dataclasses import dataclass

GUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
NUM_RE = re.compile(r"-?\d+(\.\d+)?([eE][-+]?\d+)?")
# Целое — число без точки и без экспоненты. Это определение нужно и `scan` (вид лексемы), и `json0` (обёртка `{"num": …}`
# принимает текст целого таким, как он записан в файле).
INT_RE = re.compile(r"-?\d+")
B64_PREFIX = "#base64:"
WHITESPACE = " \t\r\n"
B64_WIDTH = 64
# Внутри блока base64 платформа разделяет строки последовательностью CR CR LF, а не CR LF. Полные строки состоят ровно из 64 знаков.
B64_SEP = "\r\r\n"
# Три раскладки: нормальная, одной строкой и с разделителем только между строками. Порядок значим, см. `b64_layout`.
B64_NORM = "norm"
B64_FLAT = "flat"
B64_NO_TAIL = "no-tail"
B64_LAYOUTS = (B64_NORM, B64_FLAT, B64_NO_TAIL)


class FrmSyntaxError(ValueError):
    def __init__(self, message, text, pos):
        self.pos = pos
        self.line = text.count("\n", 0, pos) + 1
        last_nl = text.rfind("\n", 0, pos)
        self.col = pos - last_nl
        super().__init__(f"{message} (строка {self.line}, колонка {self.col})")


@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    pos: int
    # Раскладка имеет значение только у вида B64. У остальных видов в ней всегда стоит норма, и она не читается.
    layout: str = B64_NORM


def b64_body(clean, layout):
    """Тело блока `#base64:` в том виде, как оно лежит в файле: чистый base64 и раскладка. По нему же `b64_layout` определяет
    раскладку, поэтому правило записи у читателя и писателя одно.
    """
    if layout == B64_FLAT:
        return clean
    if layout not in (B64_NORM, B64_NO_TAIL):
        raise ValueError(f"раскладки base64 {layout!r} не бывает; известны "
                         f"{', '.join(B64_LAYOUTS)}")
    full = len(clean) - len(clean) % B64_WIDTH
    lines = [clean[i:i + B64_WIDTH] for i in range(0, full, B64_WIDTH)]
    tail = clean[full:]
    if layout == B64_NO_TAIL:
        # Разделитель только между строками: у тела, длина которого кратна 64, после последней полной строки разделителя нет. От нормы
        # эта раскладка отличается только на теле такой длины; на остальных телах обе раскладки дают одинаковые байты, и определяется
        # норма.
        return B64_SEP.join(lines + ([tail] if tail else []))
    # Норма: разделитель стоит после каждой полной строки. У тела, длина которого кратна 64, платформа пишет разделитель и перед
    # закрывающей скобкой. Остаток не считается строкой, и разделитель после него не ставится.
    return "".join(line + B64_SEP for line in lines) + tail


def _b64_runs(body, limit=6):
    """Описывает фактическое содержимое тела: длины отрезков без пробелов и переводы строк между ними. Используется в отказе
    «раскладка не опознана».
    """
    lengths, seps = [], set()
    i, n = 0, len(body)
    while i < n:
        start = i
        while i < n and body[i] not in WHITESPACE:
            i += 1
        lengths.append(i - start)
        start = i
        while i < n and body[i] in WHITESPACE:
            i += 1
        if i > start:
            seps.add(body[start:i])
    shown = ", ".join(str(x) for x in lengths[:limit]) + ("…" if len(lengths) > limit else "")
    return (f"отрезки {shown or 'ни одного'}; "
            f"переводы строк {', '.join(sorted(repr(s) for s in seps)) or 'их нет'}")


def b64_layout(body, text, pos):
    """Возвращает чистое тело блока и его раскладку. Берётся первая из трёх известных раскладок, которая подходит; если ни одна не
    подходит, это отказ.

    Порядок перебора значим. На коротком теле (меньше 64 знаков) все три раскладки дают одинаковые байты, и норма, стоящая
    первой, принимает такой блок. Признак раскладки появляется на уровне 0 только тогда, когда байты отличаются от нормы.

    Четвёртая раскладка недопустима: тело попало бы в JSON в чистом виде, а при обратной записи было бы записано по норме.
    """
    clean = "".join(ch for ch in body if ch not in WHITESPACE)
    for layout in B64_LAYOUTS:
        if b64_body(clean, layout) == body:
            return clean, layout
    raise FrmSyntaxError(
        f"раскладка блока base64 не опознана: известны три — строки длиной {B64_WIDTH} с "
        "CR CR LF после каждой полной, одна строка без разрывов и разделитель только между "
        f"строками; а здесь {_b64_runs(body)}", text, pos)


def scan(text):
    if text.startswith("\ufeff"):
        text = text[1:]
    tokens = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in WHITESPACE:
            i += 1
        elif c == "{":
            tokens.append(Token("LBRACE", "{", i)); i += 1
        elif c == "}":
            tokens.append(Token("RBRACE", "}", i)); i += 1
        elif c == ",":
            tokens.append(Token("COMMA", ",", i)); i += 1
        elif c == '"':
            start = i
            i += 1
            buf = []
            while True:
                if i >= n:
                    raise FrmSyntaxError("незакрытая строка", text, start)
                if text[i] == '"':
                    if i + 1 < n and text[i + 1] == '"':
                        buf.append('"'); i += 2
                    else:
                        i += 1; break
                else:
                    buf.append(text[i]); i += 1
            tokens.append(Token("STR", "".join(buf), start))
        elif text.startswith(B64_PREFIX, i):
            start = i
            i += len(B64_PREFIX)
            end = text.find("}", i)
            if end < 0:
                raise FrmSyntaxError("незакрытый блок base64", text, start)
            body, layout = b64_layout(text[i:end], text, start)
            tokens.append(Token("B64", body, start, layout))
            i = end
        else:
            m = GUID_RE.match(text, i)
            # Граница у GUID такая же, как у числа. Иначе `…-3435eada2433zz` разобралось бы как GUID и посторонний текст. Если GUID не
            # подошёл, действует общий отказ ниже.
            if m and (m.end() == n or text[m.end()] in ",}" + WHITESPACE):
                tokens.append(Token("GUID", m.group(0), i)); i = m.end(); continue
            m = NUM_RE.match(text, i)
            if m and (m.end() == n or text[m.end()] in ",}" + WHITESPACE):
                kind = "INT" if INT_RE.fullmatch(m.group(0)) else "DEC"
                tokens.append(Token(kind, m.group(0), i)); i = m.end(); continue
            j = i
            while j < n and text[j] not in ",}" + WHITESPACE:
                j += 1
            raise FrmSyntaxError(f"неизвестный токен {text[i:j]!r}", text, i)
    return tokens
