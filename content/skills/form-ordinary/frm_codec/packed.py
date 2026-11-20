"""Упакованный элемент: блок `{#base64:AgFTS2…}` — сериализованный элемент в конверте.

У колонки табличного поля есть вложенный элемент — редактор значения ячейки (поле ввода, флажок или поле выбора). Рядом с
GUID его типа (`control_type`) платформа записывает строку base64, внутри которой лежит такое же скобочное содержимое, как
у элемента этого типа на форме:

* заголовок из 18 байт одинаков у всех блоков (`HEADER`);
* далее идёт raw deflate (без заголовка zlib); внутри него 8 байт длины (little-endian, равна длине остатка), BOM и
  скобочный текст, первое число которого — `content_kind` типа: 9 у поля ввода, 1 у флажка, 2 у поля выбора;
* после этого куска у части блоков лежат ещё k пустых кусков: тот же заголовок и deflate от «длина 3 + BOM» (по 27 байт;
  k от 1 до 15). Что означает k, не установлено; кодек сохраняет его в поле `empty_chunks`.

Штатный zlib (уровень 6, `memLevel` 8, стратегия по умолчанию, окно 2¹⁵) даёт те же байты, что и платформа.

При разборе проверяется, что блок собирается обратно в те же байты. Блок раскрывается, только если собранный обратно блок
совпадает с исходным: заголовок известен, длина и BOM на месте, хвост состоит ровно из k пустых кусков, писатель дерева
повторяет текст, а сжатие на этой машине даёт поток платформы. Иначе узел остаётся сырым (`raw`), а причину сообщает
`validate`. Граница: на машине, где zlib сжимает иначе (zlib-ng и подобные), блоки останутся сырыми. Это не нарушает
побайтное совпадение при обратной сборке, но уменьшает глубину разбора.

Изменённый блок собирается тем же сжатием, с тем же заголовком и с тем же числом пустых кусков, которое записано в JSON.
Раскладка base64 по строкам сохраняется такой же, как у блока, если она указана (`layout`).
"""
import base64
import binascii
import zlib

from .tokens import B64_LAYOUTS, B64_NORM, b64_body
from .tree import Node, Scalar, parse, render_body

HEADER = bytes.fromhex("0201534b6ff4888dc14ea0d5ebb6bda0a70d")
BOM = b"\xef\xbb\xbf"
LENGTH_BYTES = 8
# Параметры сжатия — штатные параметры zlib: именно они воспроизводят поток платформы.
LEVEL, WBITS, MEM_LEVEL, STRATEGY = 6, -15, 8, zlib.Z_DEFAULT_STRATEGY


class PackedError(ValueError):
    """Блок нельзя раскрыть или собрать; исключение содержит причину словами."""


def deflate(plain):
    packer = zlib.compressobj(LEVEL, zlib.DEFLATED, WBITS, MEM_LEVEL, STRATEGY)
    return packer.compress(plain) + packer.flush()


def chunk(text):
    """Один кусок: заголовок и deflate от (длина, BOM, текст). Длина считается вместе с BOM."""
    body = BOM + text.encode("utf-8")
    return HEADER + deflate(len(body).to_bytes(LENGTH_BYTES, "little") + body)


# Пустой кусок — «длина 3 + BOM», 27 байт. Платформа дописывает его k раз после тела.
EMPTY_CHUNK = chunk("")


def _read_chunk(raw, at):
    """Возвращает `(текст, позиция после куска)` для одного куска, начинающегося с позиции `at`. При ошибке возникает `PackedError`."""
    if raw[at:at + len(HEADER)] != HEADER:
        raise PackedError(f"заголовок {raw[at:at + len(HEADER)].hex()} не тот: у платформы он "
                          f"всегда {HEADER.hex()}")
    unpacker = zlib.decompressobj(WBITS)
    try:
        plain = unpacker.decompress(raw[at + len(HEADER):])
    except zlib.error as e:
        raise PackedError(f"поток deflate не раскрывается: {e}") from None
    if not unpacker.eof:
        raise PackedError("поток deflate обрывается раньше конца")
    if len(plain) < LENGTH_BYTES:
        raise PackedError(f"кусок короче головы длины: {len(plain)} байт при {LENGTH_BYTES}")
    size = int.from_bytes(plain[:LENGTH_BYTES], "little")
    if size != len(plain) - LENGTH_BYTES:
        raise PackedError(f"длина в голове куска {size}, а за ней {len(plain) - LENGTH_BYTES} байт")
    body = plain[LENGTH_BYTES:]
    if not body.startswith(BOM):
        raise PackedError("у куска нет BOM — у платформы он есть всегда")
    try:
        text = body[len(BOM):].decode("utf-8")
    except UnicodeDecodeError as e:
        raise PackedError(f"текст куска не UTF-8: {e}") from None
    return text, len(raw) - len(unpacker.unused_data)


def unpack(b64):
    """Возвращает `(текст тела, число пустых кусков)` из текста base64. При ошибке возникает `PackedError`. Проверка «соберётся ли
    блок обратно в те же байты» выполняется здесь же, в самом конце.
    """
    try:
        raw = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError) as e:
        raise PackedError(f"текст блока — не base64: {e}") from None
    text, at = _read_chunk(raw, 0)
    rest = raw[at:]
    empty, tail = divmod(len(rest), len(EMPTY_CHUNK))
    if tail or rest != EMPTY_CHUNK * empty:
        raise PackedError(f"за телом {len(rest)} байт, и это не пустые куски по "
                          f"{len(EMPTY_CHUNK)} байт — такого хвоста у платформы не бывает")
    if chunk(text) + rest != raw:
        raise PackedError(f"сжатие этой машины (zlib {zlib.ZLIB_RUNTIME_VERSION}, уровень "
                          f"{LEVEL}) даёт не те байты, что у платформы; штатный zlib их повторяет — "
                          "здесь, видимо, другой "
                          "компрессор или другая сборка zlib")
    return text, empty


def pack(text, empty=0):
    """Текст base64 блока по тексту тела и числу пустых кусков."""
    return base64.b64encode(chunk(text) + EMPTY_CHUNK * empty).decode("ascii")


# Узел дерева и «виртуальный» узел карты
# Карта описывает упакованный элемент тремя позициями, которых нет в файле: содержимое элемента, число пустых кусков и
# раскладка base64 по строкам (последняя — только когда она не нормальная). При раскрытии получается такой узел, а дальше его
# разбирают и собирают те же правила, что и любой другой блок.
CONTENT, EMPTY, LAYOUT = 0, 1, 2


def payload_of(node):
    """Скаляр base64 блока-обёртки. Если обёртка не состоит из одного скаляра base64, это отказ."""
    if not isinstance(node, Node) or len(node.children) != 1 \
            or not isinstance(node.children[0], Scalar) or node.children[0].kind != "B64":
        raise PackedError("блок упакованного элемента — это ровно один скаляр base64, "
                          "а здесь другое строение")
    return node.children[0]


def unpack_node(node):
    """Обёртка `{#base64:…}` превращается в виртуальный узел `{содержимое, k[, раскладка]}`."""
    payload = payload_of(node)
    text, empty = unpack(payload.text)
    try:
        body = parse(text)
    except ValueError as e:
        raise PackedError(f"текст тела не разбирается: {e}") from None
    if render_body(body) != text:
        raise PackedError("писатель дерева не повторяет текст тела байт в байт, а должен повторять")
    children = [body, Scalar("INT", str(empty))]
    if payload.layout != B64_NORM:
        children.append(Scalar("STR", payload.layout))
    return Node(children)


def pack_node(virtual, where="корень"):
    """Виртуальный узел превращается в обёртку `{#base64:…}`. Если собирать нечего, возникает отказ с пояснением."""
    children = virtual.children
    if len(children) not in (2, 3):
        raise PackedError(f"{where}: у упакованного элемента две или три позиции — содержимое, "
                          f"число пустых кусков и (не всегда) раскладка, — а здесь {len(children)}")
    body, empty = children[0], children[1]
    if not isinstance(body, Node):
        raise PackedError(f"{where}: содержимое упакованного элемента — блок, а пришёл скаляр")
    if not isinstance(empty, Scalar) or empty.kind != "INT" or not empty.text.lstrip("-").isdigit() \
            or int(empty.text) < 0:
        raise PackedError(f"{where}: число пустых кусков — целое от нуля, а пришло "
                          f"{getattr(empty, 'text', empty)!r}")
    layout = B64_NORM
    if len(children) == 3:
        mark = children[2]
        layout = mark.text if isinstance(mark, Scalar) and mark.kind == "STR" else None
        if layout not in B64_LAYOUTS or layout == B64_NORM:
            raise PackedError(f"{where}: раскладки base64 {layout!r} здесь не бывает; признак "
                              f"пишут, когда она не норма: {', '.join(B64_LAYOUTS[1:])}")
    text = pack(render_body(body), int(empty.text))
    if layout != B64_NORM and b64_body(text, layout) == b64_body(text, B64_NORM):
        raise PackedError(f"{where}: раскладка {layout!r} пишет это тело теми же байтами, что и "
                          "норма (тело изменилось, и признак раскладки больше ничего не "
                          "различает) — уберите его")
    return Node([Scalar("B64", text, layout)])
