"""Внешний контейнер 8.3 (`.epf`, `.erf`; 32-битный формат): элементы с описанием и данными.

Заголовок — четыре слова `{0x7fffffff, 512, …, …}`, дальше блоки: 31 байт заголовка (`\\r\\n`, три числа по восемь шестнадцатеричных
цифр — размер документа, размер блока, адрес следующего или `0x7fffffff`) и тело. Первый документ — оглавление: тройки
`{адрес описания, адрес данных, 0x7fffffff}`. Описание элемента — 20 байт и имя в UTF-16LE; данные сжаты raw deflate (элемент
может быть и несжатым).

Запись: описание блоком точного размера, данные блоком не меньше 512 байт; элемент, данные которого не меняли, пишется теми же
байтами описания и теми же сжатыми данными.
"""
import struct
import zlib

END = 0x7FFFFFFF
BLOCK_HEAD = 31
MIN_BLOCK = 512


class EpfError(ValueError):
    pass


def _document(buf, offset):
    out = bytearray()
    total = None
    seen = set()
    while True:
        if offset in seen or offset < 0 or offset + BLOCK_HEAD > len(buf):
            raise EpfError(f"не контейнер .epf/.erf: блок по смещению {offset} выходит за файл")
        seen.add(offset)
        head = buf[offset:offset + BLOCK_HEAD]
        if head[:2] != b"\r\n" or head[10:11] != b" " or head[19:20] != b" ":
            raise EpfError(f"не контейнер .epf/.erf: нет заголовка блока по смещению {offset}")
        try:
            size, block, nxt = int(head[2:10], 16), int(head[11:19], 16), int(head[20:28], 16)
        except ValueError:
            raise EpfError(f"не контейнер .epf/.erf: заголовок блока по смещению {offset} не прочитан") from None
        if total is None:
            total = size
        out += buf[offset + BLOCK_HEAD:offset + BLOCK_HEAD + block]
        if nxt == END:
            break
        offset = nxt
    if len(out) < total:
        raise EpfError("не контейнер .epf/.erf: документ короче заявленного размера")
    return bytes(out[:total])


class Item:
    """Элемент контейнера. `raw` — данные как лежат в файле (сжатые), `None` — данных нет."""

    def __init__(self, desc, raw):
        self.desc = desc
        self.raw = raw
        self._data = None

    @property
    def name(self):
        return self.desc[20:].decode("utf-16-le").rstrip("\x00")

    @property
    def data(self):
        """Распакованное содержимое (несжатое отдаётся как есть)."""
        if self._data is None:
            raw = self.raw or b""
            try:
                self._data = zlib.decompress(raw, -15)
            except zlib.error:
                self._data = raw
        return self._data

    def set_data(self, data):
        comp = zlib.compressobj(9, zlib.DEFLATED, -15)
        self.raw = comp.compress(data) + comp.flush()
        self._data = bytes(data)


class Container:
    def __init__(self, head, items):
        self.head = head          # третье и четвёртое слова заголовка — как были
        self.items = items

    def get(self, name):
        for it in self.items:
            if it.name == name:
                return it
        return None

    def names(self):
        return [it.name for it in self.items]


def read(buf):
    buf = bytes(buf)
    if len(buf) < 16 + BLOCK_HEAD:
        raise EpfError("не контейнер .epf/.erf: файл слишком короткий")
    # Первое слово заголовка у сборки платформой и у сборки `ibcmd` разное (`0x7fffffff` и произвольное число), поэтому
    # контейнер узнаётся по блоку оглавления, а не по нему; запись всегда ставит `0x7fffffff`.
    if struct.unpack("<Q", buf[:8])[0] == 0xFFFFFFFFFFFFFFFF:
        raise EpfError("64-битный формат контейнера не поддерживается: его раскладка не проверялась. Сборка Конфигуратором "
                       "(1cv8 DESIGNER /LoadExternalDataProcessorOrReportFromFiles) пишет copyinfo сама.")
    head = struct.unpack("<IIII", buf[:16])
    toc = _document(buf, 16)
    items = []
    for i in range(0, len(toc) - 11, 12):
        desc_at, data_at, _ = struct.unpack("<III", toc[i:i + 12])
        if desc_at == END:
            continue
        desc = _document(buf, desc_at)
        if len(desc) < 20:
            raise EpfError("не контейнер .epf/.erf: описание элемента короче 20 байт")
        items.append(Item(desc, _document(buf, data_at) if data_at != END else None))
    return Container(head, items)


def _block(data, size):
    return b"\r\n%08x %08x %08x \r\n" % (len(data), size, END) + data + bytes(size - len(data))


def write(container):
    toc_size = 12 * len(container.items)
    offset = 16 + BLOCK_HEAD + max(toc_size, MIN_BLOCK)
    toc = bytearray()
    body = bytearray()
    for it in container.items:
        desc_at = offset
        body += _block(it.desc, len(it.desc))
        offset += BLOCK_HEAD + len(it.desc)
        if it.raw is None:
            toc += struct.pack("<III", desc_at, END, END)
            continue
        size = max(len(it.raw), MIN_BLOCK)
        data_at = offset
        body += _block(it.raw, size)
        offset += BLOCK_HEAD + size
        toc += struct.pack("<III", desc_at, data_at, END)
    head = struct.pack("<IIII", END, MIN_BLOCK, container.head[2], container.head[3])
    return head + _block(bytes(toc), max(toc_size, MIN_BLOCK)) + bytes(body)
