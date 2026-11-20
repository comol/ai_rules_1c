"""Дерево скобочного файла: блоки и скаляры, адреса позиций, канонический писатель.

Писатель воспроизводит раскладку платформы. Блок из одних скаляров пишется в одну строку. В блоке с вложенными блоками
каждый вложенный блок начинается с новой строки, скаляры после закрывающей скобки вложенного блока продолжают её строку, а
закрывающая скобка самого блока переходит на новую строку только тогда, когда последний потомок — блок.

У блока `#base64:` раскладка не выводится из правила, а запоминается при разборе (поле `layout` у скаляра; три известные
раскладки описаны в `tokens`).

Шестой вид скаляра — `EMPTY`, пустое значение между запятыми (`0,,60`). У него нет лексемы, и он определяется по месту:
запятая там, где ожидалось значение.

Функции `parse_path` и `write_file` — пара к `path_str` и `read_file`. Они нужны кодеку, где адрес приходит строкой из JSON,
а изменённое дерево записывается на диск.
"""
from dataclasses import dataclass, field
from .tokens import scan, FrmSyntaxError, B64_NORM, B64_PREFIX, b64_body

BOM = "\ufeff"
CRLF = "\r\n"


@dataclass(frozen=True)
class Scalar:
    kind: str   # INT DEC STR GUID B64 EMPTY
    text: str
    # Раскладка тела base64 (`tokens.B64_LAYOUTS`) — то, как текст разложен по строкам. У остальных видов скаляра поле содержит
    # норму и не читается. В сравнении на равенство оно участвует, потому что правка, которая изменила только раскладку, меняет
    # байты файла.
    layout: str = B64_NORM


@dataclass
class Node:
    children: list = field(default_factory=list)


def parse(text):
    """Строит дерево из текста файла. Пустое значение между запятыми — это скаляр `EMPTY`, а не отказ.

    * Пустое значение посреди блока (`{0,,60}`) — скаляр.
    * Пустое значение в начале блока (`{,1}`) — та же конструкция, и она принимается той же веткой.
    * Пустое значение в конце блока (`{1,}`) — отказ «запятая перед закрывающей скобкой». Писатель соблюдает ту же границу
      (`_render`).
    """
    tokens = scan(text)
    pos = 0

    def expect(kind):
        nonlocal pos
        if pos >= len(tokens) or tokens[pos].kind != kind:
            at = tokens[pos].pos if pos < len(tokens) else len(text)
            raise FrmSyntaxError(f"ожидался {kind}", text, at)
        pos += 1

    def node():
        nonlocal pos
        expect("LBRACE")
        n = Node()
        while True:
            tok = tokens[pos] if pos < len(tokens) else None
            if tok is None:
                raise FrmSyntaxError("файл кончился внутри блока", text, len(text))
            if tok.kind == "RBRACE":
                pos += 1
                return n
            if tok.kind == "LBRACE":
                n.children.append(node())
            elif tok.kind == "COMMA":
                # Запятая на месте значения означает пустое значение (см. описание модуля и `parse`). Сама запятая здесь не потребляется: её
                # заберёт общий разделитель ниже.
                n.children.append(Scalar("EMPTY", ""))
            else:
                n.children.append(Scalar(tok.kind, tok.text, tok.layout)); pos += 1
            tok = tokens[pos] if pos < len(tokens) else None
            if tok is not None and tok.kind == "COMMA":
                pos += 1
                if pos < len(tokens) and tokens[pos].kind == "RBRACE":
                    raise FrmSyntaxError("запятая перед закрывающей скобкой", text, tok.pos)
            elif tok is not None and tok.kind != "RBRACE":
                # `{1 2}`: без этой проверки разбор молча объединял бы два значения в один блок. Писатель всегда ставит запятую между
                # потомками, поэтому её отсутствие означает повреждение файла.
                raise FrmSyntaxError("после значения ожидалась запятая или закрывающая скобка", text, tok.pos)

    root = node()
    if pos != len(tokens):
        raise FrmSyntaxError("текст после корневого блока", text, tokens[pos].pos)
    return root


def _scalar_text(s):
    if s.kind == "EMPTY":
        # Пустое значение печатается как пустое место; разделители вокруг него ставит `_render`.
        return ""
    if s.kind == "STR":
        return '"' + s.text.replace('"', '""') + '"'
    if s.kind == "B64":
        # Раскладку тела записывает `tokens.b64_body` — та же функция, которая определила её при разборе.
        return B64_PREFIX + b64_body(s.text, s.layout)
    return s.text


def _render(node, out, path=()):
    out.append("{")
    last_was_node = False
    last = node.children[-1] if node.children else None
    if isinstance(last, Scalar) and last.kind == "EMPTY":
        # Граница та же, что при разборе (`parse`): пустое значение допустимо посреди блока и в начале, но не в конце. Писатель хранит
        # путь, чтобы отказ называл адрес в дереве, собранном из JSON.
        raise ValueError(f"{path_str(path) or 'корень'}: пустое значение последним ребёнком "
                         "блока — в файле такого не встречено, а записанное так обратно не "
                         "читается: разбор отвечает «запятая перед закрывающей скобкой»")
    for i, child in enumerate(node.children):
        if isinstance(child, Node):
            if i > 0:
                out.append(",")
            out.append(CRLF)
            _render(child, out, path + (i,))
            last_was_node = True
        else:
            if i > 0:
                out.append(",")
            out.append(_scalar_text(child))
            last_was_node = False
    if last_was_node:
        out.append(CRLF)
    out.append("}")


def render(node):
    # У формы нет завершающего перевода строки: форма заканчивается закрывающей скобкой.
    out = [BOM]
    _render(node, out)
    return "".join(out)


def render_body(node):
    """Текст блока, записанный тем же писателем, но без BOM. Так хранится тело упакованного элемента (`frm_codec.packed`): его BOM
    находится в двоичном конверте, а не в тексте.
    """
    out = []
    _render(node, out)
    return "".join(out)


def walk(node, path=()):
    yield path, node
    if isinstance(node, Node):
        for i, child in enumerate(node.children):
            if isinstance(child, Node):
                yield from walk(child, path + (i,))
            else:
                yield path + (i,), child


def get(node, path):
    for i in path:
        node = node.children[i]
    return node


def path_str(path):
    return "/".join(str(i) for i in path)


def parse_path(text):
    return tuple(int(p) for p in text.split("/")) if text else ()


def read_file(path):
    with open(path, "rb") as f:
        return parse(f.read().decode("utf-8"))


def write_file(path, node):
    with open(path, "wb") as f:
        f.write(render(node).encode("utf-8"))
