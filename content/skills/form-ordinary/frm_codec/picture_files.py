"""Картинка из файла любого вида, который платформа вкладывает в форму: PNG, BMP, ICO, GIF → PNG для рисунка и размер в пикселях.

Что берётся и как читается (только стандартная библиотека):

* PNG — как есть (рисует средство просмотра); размер — из заголовка; прозрачность — своя, у PNG без альфы картинка непрозрачна.
* BMP — несжатый, с палитрой (1, 4, 8 бит) и без неё (24, 32 бита). Прозрачным считается цвет ВЕРХНЕГО левого пикселя (`key="corner"`), либо пикселя с заданными координатами, либо ничего (`key=None`).
* ICO — первое изображение каталога (у файла из нескольких размеров платформа берёт то, что стоит первым; другого опыт не показал): PNG внутри значка — как есть; иначе BMP без файлового заголовка с
  двойной высотой (рисунок и маска «И»). Прозрачность: у 32-битного рисунка с ненулевым альфа-каналом — он; иначе маска «И» (бит 1 — прозрачный пиксель).
* GIF — первый кадр, глобальная или местная палитра, чересстрочный порядок, прозрачный индекс из блока управления рисунком; LZW разбирается здесь.

Прочее (сжатый BMP, неизвестная глубина, обрезанные данные, неизвестное начало файла, больше `MAX_PIXELS` точек) — `None`: на месте картинки рисуется серый квадрат, а рендер называет причину в `notes`
(`why_unreadable`).
"""
import collections
import hashlib
import struct
import zlib

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_SIDE = 4096
MAX_PIXELS = 2_000_000          # потолок картинки по числу точек (около 1 414 × 1 414): разбор идёт кортежами на Python, 4096 × 8192 съело бы гигабайты; картинки форм — до нескольких сотен точек по стороне


class Decoded:
    """PNG (байты) и размер картинки в пикселях."""

    def __init__(self, png, w, h):
        self.png, self.w, self.h = png, w, h


def kind_of(data):
    """`"png"`, `"bmp"`, `"ico"`, `"gif"` по началу файла либо `None`."""
    if data[:8] == PNG_SIGNATURE:
        return "png"
    if data[:2] == b"BM":
        return "bmp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"\x00\x00\x01\x00":
        return "ico"
    return None


def png_of(width, height, rows):
    """PNG RGBA из списка строк `[(r, g, b, a), ...]` сверху вниз."""
    raw = b"".join(b"\x00" + bytes(c for px in row for c in px) for row in rows)

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    return (PNG_SIGNATURE + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def _dib(data, at, icon=False, pixel_offset=None):
    """Рисунок BMP с заголовком в `data[at:]`: `(ширина, высота, строки RGB или RGBA сверху вниз, есть_альфа, конец рисунка)`; у значка высота в заголовке двойная (рисунок и маска «И»)."""
    size, width, height, _planes, bpp, compression = struct.unpack_from("<IiiHHI", data, at)
    if size < 40 or compression != 0 or width <= 0 or height == 0 or bpp not in (1, 4, 8, 24, 32) or width > MAX_SIDE or abs(height) > 2 * MAX_SIDE:
        return None
    top_down = height < 0
    height = abs(height)
    if icon:
        height //= 2
    if height <= 0 or width * height > MAX_PIXELS:
        return None
    palette = []
    if bpp <= 8:
        count = struct.unpack_from("<I", data, at + 32)[0] or (1 << bpp)
        base = at + size
        palette = [(data[base + 4 * i + 2], data[base + 4 * i + 1], data[base + 4 * i]) for i in range(min(count, 1 << bpp))]
        pixels = base + 4 * min(count, 1 << bpp)
    else:
        pixels = at + size
    if pixel_offset is not None:
        pixels = pixel_offset          # начало пикселей называет файловый заголовок BMP
    stride = ((width * bpp + 31) // 32) * 4
    if len(data) - pixels < stride * height:          # данных меньше, чем строк: не разбирать зря
        return None
    rows, alpha_seen = [], False
    for y in range(height):
        start = pixels + stride * (y if top_down else height - 1 - y)
        line = data[start:start + stride]
        if len(line) < stride:
            return None
        row = []
        for x in range(width):
            if bpp == 8:
                row.append(palette[line[x]] if line[x] < len(palette) else (0, 0, 0))
            elif bpp == 4:
                idx = (line[x // 2] >> 4) if x % 2 == 0 else (line[x // 2] & 15)
                row.append(palette[idx] if idx < len(palette) else (0, 0, 0))
            elif bpp == 1:
                idx = (line[x // 8] >> (7 - x % 8)) & 1
                row.append(palette[idx] if idx < len(palette) else (0, 0, 0))
            elif bpp == 24:
                row.append((line[3 * x + 2], line[3 * x + 1], line[3 * x]))
            else:
                a = line[4 * x + 3]
                alpha_seen = alpha_seen or a != 0
                row.append((line[4 * x + 2], line[4 * x + 1], line[4 * x], a))
        rows.append(row)
    return width, height, rows, bpp == 32 and alpha_seen, pixels + stride * height


def _bmp(data, key):
    try:
        offset = struct.unpack_from("<I", data, 10)[0]
        got = _dib(data, 14, pixel_offset=offset)
        if got is None:
            return None
        width, height, rows, _alpha, _end = got
        rows = [[px[:3] for px in row] for row in rows]
        if key == "corner":
            color = rows[0][0]                 # верхний левый пиксель (строки идут сверху вниз)
        elif key is None:
            color = None
        else:
            x, y = key
            color = rows[y][x] if 0 <= y < height and 0 <= x < width else None     # пиксель вне картинки ничего не прозрачит
        return Decoded(png_of(width, height, [[(*px, 0 if color is not None and px == color else 255) for px in row] for row in rows]), width, height)
    except (struct.error, IndexError):
        return None


def _ico(data):
    try:
        count = struct.unpack_from("<H", data, 4)[0]
        if count < 1:
            return None
        _w, _h, _colors, _res, _planes, _bits, length, offset = struct.unpack_from("<BBBBHHII", data, 6)
        image = data[offset:offset + length]
        if len(image) < length or length < 8:
            return None
        if image[:8] == PNG_SIGNATURE:
            return _png(image)
        got = _dib(image, 0, icon=True)
        if got is None:
            return None
        width, height, rows, alpha, end = got
        if alpha:
            return Decoded(png_of(width, height, rows), width, height)
        mask_stride = ((width + 31) // 32) * 4
        out = []
        for y in range(height):
            start = end + mask_stride * (height - 1 - y)          # маска «И» идёт снизу вверх, как и рисунок
            line = image[start:start + mask_stride]
            row = []
            for x in range(width):
                hidden = len(line) == mask_stride and (line[x // 8] >> (7 - x % 8)) & 1
                px = rows[y][x]
                row.append((px[0], px[1], px[2], 0 if hidden else 255))
            out.append(row)
        return Decoded(png_of(width, height, out), width, height)
    except (struct.error, IndexError):
        return None


def _png(data):
    try:
        width, height = struct.unpack_from(">II", data, 16)
    except struct.error:
        return None
    return Decoded(data, width, height) if 0 < width <= MAX_SIDE and 0 < height <= MAX_SIDE and width * height <= MAX_PIXELS else None


def _lzw(data, min_size, count):
    """Индексы цветов (`count` штук) из LZW-потока GIF."""
    clear, end = 1 << min_size, (1 << min_size) + 1
    size, next_code = min_size + 1, end + 1
    table = {i: bytes([i]) for i in range(clear)}
    out, previous, bits, nbits = bytearray(), None, 0, 0
    for byte in data:
        bits |= byte << nbits
        nbits += 8
        while nbits >= size:
            code = bits & ((1 << size) - 1)
            bits >>= size
            nbits -= size
            if code == clear:
                table = {i: bytes([i]) for i in range(clear)}
                size, next_code, previous = min_size + 1, end + 1, None
                continue
            if code == end:
                return bytes(out[:count])
            if previous is None:
                if code not in table:
                    return None
                chunk = table[code]
            elif code in table:
                chunk = table[code]
                if next_code < 4096:
                    table[next_code] = previous + chunk[:1]
                    next_code += 1
            elif code == next_code and next_code < 4096:
                chunk = previous + previous[:1]
                table[next_code] = chunk
                next_code += 1
            else:
                return None
            out += chunk
            previous = chunk
            if next_code == (1 << size) and size < 12:
                size += 1
            if len(out) >= count:
                return bytes(out[:count])
    return bytes(out) if len(out) >= count else None


def _gif(data):
    try:
        width, height, flags = struct.unpack_from("<HHB", data, 6)
        at = 13
        palette = []
        if flags & 0x80:
            n = 2 << (flags & 7)
            palette = [tuple(data[at + 3 * i:at + 3 * i + 3]) for i in range(n)]
            at += 3 * n
        transparent = None
        while at < len(data):
            block = data[at]
            if block == 0x21:                                  # расширение: нужен блок управления рисунком (0xF9)
                label = data[at + 1]
                at += 2
                if label == 0xF9 and data[at] >= 4:
                    if data[at + 1] & 1:
                        transparent = data[at + 4]
                while data[at]:
                    at += data[at] + 1
                at += 1
            elif block == 0x2C:
                left, top, w, h, local = struct.unpack_from("<HHHHB", data, at + 1)
                at += 10
                if local & 0x80:
                    n = 2 << (local & 7)
                    palette = [tuple(data[at + 3 * i:at + 3 * i + 3]) for i in range(n)]
                    at += 3 * n
                min_size = data[at]
                at += 1
                chunks = bytearray()
                while data[at]:
                    chunks += data[at + 1:at + 1 + data[at]]
                    at += data[at] + 1
                if (not 2 <= min_size <= 8 or not palette or not (0 < width <= MAX_SIDE and 0 < height <= MAX_SIDE) or w * h == 0
                        or width * height > MAX_PIXELS or w * h > MAX_PIXELS):
                    return None
                index = _lzw(bytes(chunks), min_size, w * h)
                if index is None:
                    return None
                order = list(range(h))
                if local & 0x40:                               # чересстрочный порядок: строки 0,8,16… затем 4,12… затем 2,6… затем 1,3,…
                    order = [y for start, step in ((0, 8), (4, 8), (2, 4), (1, 2)) for y in range(start, h, step)]
                rows = [[(0, 0, 0, 0)] * width for _ in range(height)]
                for n, y in enumerate(order):
                    for x in range(w):
                        i = index[n * w + x]
                        if 0 <= top + y < height and 0 <= left + x < width:
                            rows[top + y][left + x] = (0, 0, 0, 0) if i == transparent or i >= len(palette) else (*palette[i], 255)
                return Decoded(png_of(width, height, rows), width, height)
            else:
                return None
    except (struct.error, IndexError):
        return None
    return None


def size_of(data):
    """`(ширина, высота)` картинки по заголовку файла, не разбирая её, либо `None`."""
    try:
        kind = kind_of(data)
        if kind == "png":
            return struct.unpack_from(">II", data, 16)
        if kind == "gif":
            return struct.unpack_from("<HH", data, 6)
        if kind == "bmp":
            _size, width, height = struct.unpack_from("<Iii", data, 14)
            return width, abs(height)
        if kind == "ico":
            width, height = data[6], data[7]
            return width or 256, height or 256
    except (struct.error, IndexError):
        return None
    return None


_CACHE = collections.OrderedDict()
_CACHE_SIZE = 64


def decode(data, key="corner"):
    """`Decoded` (PNG и размер) по байтам файла либо `None`: вид не опознан, строение не читается или картинка больше `MAX_PIXELS`. `key` — прозрачный цвет BMP (см. докстринг модуля).
    Результат помнится по хешу байтов и ключу: форма несёт одну картинку на много мест, и разбирать файл каждый раз незачем."""
    token = (hashlib.sha1(data).digest(), key)
    if token in _CACHE:
        _CACHE.move_to_end(token)
        return _CACHE[token]
    kind = kind_of(data)
    got = _png(data) if kind == "png" else _bmp(data, key) if kind == "bmp" else _ico(data) if kind == "ico" else _gif(data) if kind == "gif" else None
    _CACHE[token] = got
    while len(_CACHE) > _CACHE_SIZE:
        _CACHE.popitem(last=False)
    return got


def why_unreadable(data):
    """Причина, по которой `decode` вернул `None`, словами для `notes`: вид не опознан, картинка слишком крупная или строение не читается (сжатый BMP, неизвестная глубина, обрезанные данные)."""
    kind = kind_of(data)
    if kind is None:
        return "вид файла не опознан (читаются PNG, BMP, ICO и GIF)"
    size = size_of(data)
    if size is None or size[0] <= 0 or size[1] <= 0:
        return f"заголовок файла вида {kind.upper()} повреждён (размер картинки не читается)"
    if size[0] * size[1] > MAX_PIXELS or size[0] > MAX_SIDE or size[1] > 2 * MAX_SIDE:
        return f"картинка {size[0]}×{size[1]} крупнее {MAX_PIXELS:,} точек".replace(",", " ")
    return f"файл вида {kind.upper()} не читается (сжатие, глубина цвета или обрезанные данные)"
