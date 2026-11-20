"""Пиксели картинки и масштабирование, как это делает предприятие (стандартная библиотека).

Что снято по снимкам предприятия (после приведения цвета к 16 битам):

* **Растянутая картинка формы** — ближайший сосед по центрам пикселей, СИММЕТРИЧНЫЙ: источник для приёмника `i` в левой половине — `ceil((2i+1)·s/(2t)) − 1`, в правой — зеркально
  (`s − 1 − m(t − 1 − i)`), то есть на ровной границе («центр приёмника ровно на краю пикселя источника») выбирается пиксель ближе к краю картинки. Простая формула `floor((2i+1)·s/(2t))` даёт 76 лишних точек
  из 69 630 на ровных границах правой половины; симметричная — ни одной.
* **Сжатие со сглаживанием** (картинка надписи и значок командной панели крупнее квадрата) — среднее по площади (каждый приёмник — взвешенное по покрытию среднее исходных пикселей),
  цвет усредняется с весом альфа, результат округляется. **Растяжение со сглаживанием** (картинка в поле «Растянуть») — линейное по центрам пикселей, по каждой оси отдельно, значение усекается (1 600 из 1 600 точек у поля 40×20 → 40×40). 32 → 16 в панели совпало точно на всех непрозрачных пикселях; 16 → 15 и 32 → 22 — с отклонением на шаг 16-битного цвета у части краевых точек.
"""
import struct
import zlib

from . import picture_files


def read_png(data):
    """`(ширина, высота, [строки [(r, g, b, a)]])` из PNG либо `None`: цвет типов 0, 2, 3, 4, 6, глубина 1–8 и 16 (старший байт), без чересстрочности."""
    try:
        if data[:8] != picture_files.PNG_SIGNATURE:
            return None
        pos, header, palette, trns, idat = 8, None, None, None, b""
        while pos < len(data):
            size, kind = struct.unpack_from(">I4s", data, pos)
            body = data[pos + 8:pos + 8 + size]
            if kind == b"IHDR":
                header = struct.unpack(">IIBBBBB", body)
            elif kind == b"PLTE":
                palette = [tuple(body[i:i + 3]) for i in range(0, len(body), 3)]
            elif kind == b"tRNS":
                trns = body
            elif kind == b"IDAT":
                idat += body
            elif kind == b"IEND":
                break
            pos += 12 + size
        width, height, depth, color, _comp, _filt, interlace = header
        if interlace or color not in (0, 2, 3, 4, 6) or depth not in (1, 2, 4, 8, 16) or not 0 < width <= picture_files.MAX_SIDE or not 0 < height <= picture_files.MAX_SIDE or width * height > picture_files.MAX_PIXELS:
            return None
        channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
        bits = channels * depth
        stride = (width * bits + 7) // 8
        bpp = max(bits // 8, 1)
        need = height * (stride + 1)
        raw = zlib.decompressobj().decompress(idat, need + 1)           # не больше нужного: сжатая бомба не раздувается
        if len(raw) < need:
            return None
        rows, prev = [], bytearray(stride)
        for y in range(height):
            kind = raw[y * (stride + 1)]
            line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                up = prev[i]
                corner = prev[i - bpp] if i >= bpp else 0
                if kind == 1:
                    line[i] = (line[i] + left) & 255
                elif kind == 2:
                    line[i] = (line[i] + up) & 255
                elif kind == 3:
                    line[i] = (line[i] + (left + up) // 2) & 255
                elif kind == 4:
                    p = left + up - corner
                    pa, pb, pc = abs(p - left), abs(p - up), abs(p - corner)
                    line[i] = (line[i] + (left if pa <= pb and pa <= pc else up if pb <= pc else corner)) & 255
                elif kind != 0:
                    return None
            prev = line
            rows.append(_pixels(line, width, depth, color, palette, trns))
        return width, height, rows
    except (struct.error, zlib.error, IndexError, TypeError, ValueError):
        return None


def _samples(line, width, channels, depth):
    if depth == 8:
        return list(line[:width * channels])
    if depth == 16:
        return [line[2 * i] for i in range(width * channels)]
    out, mask = [], (1 << depth) - 1
    for i in range(width * channels):
        shift = 8 - depth - (i * depth) % 8
        out.append((line[i * depth // 8] >> shift) & mask)
    return out


def _pixels(line, width, depth, color, palette, trns):
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    s = _samples(line, width, channels, depth)
    full = [line[2 * i] << 8 | line[2 * i + 1] for i in range(width * channels)] if depth == 16 else s      # прозрачный цвет tRNS — полный отсчёт (у 16 бит два байта)
    key = struct.unpack(">3H", trns[:6]) if trns and color == 2 and len(trns) >= 6 else struct.unpack(">H", trns[:2])[0] if trns and color == 0 and len(trns) >= 2 else None
    top = (1 << min(depth, 8)) - 1
    row = []
    for x in range(width):
        if color == 6:
            row.append(tuple(s[4 * x:4 * x + 4]))
        elif color == 2:
            r, g, b = s[3 * x:3 * x + 3]
            a = 0 if key is not None and tuple(full[3 * x:3 * x + 3]) == key else 255
            row.append((r, g, b, a))
        elif color == 4:
            g, a = s[2 * x:2 * x + 2]
            row.append((g, g, g, a))
        elif color == 0:
            g = s[x] * 255 // top
            a = 0 if key is not None and full[x] == key else 255
            row.append((g, g, g, a))
        else:
            r, g, b = palette[s[x]]
            a = trns[s[x]] if trns and s[x] < len(trns) else 255
            row.append((r, g, b, a))
    return row


def png_of_rows(rows):
    return picture_files.png_of(len(rows[0]), len(rows), rows)


def mirror_map(t, s):
    """Источник для каждого из `t` приёмников при растяжении без сглаживания `s` пикселей на `t` (симметричный ближайший сосед — см. докстринг модуля)."""
    half = [min(s - 1, max(0, -(-((2 * i + 1) * s) // (2 * t)) - 1)) for i in range(t)]
    return [half[i] if 2 * i < t else s - 1 - half[t - 1 - i] for i in range(t)]


def nearest(rows, tw, th):
    """Строки `th`×`tw` — растяжение ближайшим соседом (картинка формы «Растянуть»)."""
    sh, sw = len(rows), len(rows[0])
    mx, my = mirror_map(tw, sw), mirror_map(th, sh)
    return [[rows[my[y]][mx[x]] for x in range(tw)] for y in range(th)]


def _spans(t, s):
    """Веса исходных пикселей для каждого из `t` приёмников: сжатие — покрытие (среднее по площади), растяжение — линейное по центрам пикселей (как при растяжении картинки в поле: сверено на снимке)."""
    if t > s:
        out = []
        for i in range(t):
            pos = (i + 0.5) * s / t - 0.5
            k = int(pos // 1)
            f = pos - k
            out.append([(min(max(k, 0), s - 1), 1 - f), (min(max(k + 1, 0), s - 1), f)])
        return out
    out = []
    for i in range(t):
        a, b = i * s / t, (i + 1) * s / t
        row, k = [], int(a)
        while k < b and k < s:
            lo, hi = max(a, k), min(b, k + 1)
            if hi > lo:
                row.append((k, (hi - lo) / (b - a)))
            k += 1
        out.append(row)
    return out


def area(rows, tw, th):
    """Строки `th`×`tw` — среднее по площади с весом альфа (значок панели 32 → 16, картинка надписи)."""
    sh, sw = len(rows), len(rows[0])
    sx, sy = _spans(tw, sw), _spans(th, sh)
    grow = tw >= sw and th >= sh          # растяжение: значение усекается (снято: 1 600 из 1 600 у поля «Растянуть»), сжатие — округляется
    shift = 0.0 if grow else 0.5
    out = []
    for y in range(th):
        line = []
        for x in range(tw):
            r = g = b = wa = a = 0.0
            for ky, wy in sy[y]:
                for kx, wx in sx[x]:
                    pr, pg, pb, pa = rows[ky][kx]
                    w = wx * wy
                    r += pr * pa * w
                    g += pg * pa * w
                    b += pb * pa * w
                    wa += pa * w
                    a += pa * w
            if wa:
                line.append((int(r / wa + shift), int(g / wa + shift), int(b / wa + shift), int(a + shift)))
            else:
                line.append((0, 0, 0, 0))
        out.append(line)
    return out
