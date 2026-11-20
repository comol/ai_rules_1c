"""Контейнер `Form.bin` обычной (неуправляемой) формы 1С и связь контейнера с текстовыми файлами рядом.

Платформа выгружает обычную форму только двоичным контейнером `Forms/<Имя>/Ext/Form.bin`. Внутри три секции: `form` (описание
элементов, скобочный текст), `module` (модуль формы на встроенном языке) и `info` (метаинформация; есть не у всех форм). Рядом
с контейнером лежат их текстовые копии: `form.frm`, `form.bsl`, `info.txt`. Модуль делает ту же раскладку, что инструмент выгрузки, и даёт
те же байты. Отличие одно: пустой `info.txt` считается отсутствующей секцией `info`.

Формат устроен так.

* Заголовок 16 байт: маркер `0x7fffffff`, размер блока (`0x200`), число файлов, резерв.
* Блок оглавления: записи `(смещение описания, смещение данных, маркер 0x7fffffff)` по 12 байт; сразу за ними лежит
  необязательный вложенный контейнер с секцией `info`.
* Дальше на каждый файл по два блока: описание (две метки времени, резерв, имя в UTF-16LE) и данные.
* Заголовок каждого блока текстовый, 31 байт: CRLF, три hex-числа через пробел (размер документа, размер блока, смещение
  следующего блока цепочки), CRLF.

Поддерживается только 32-битный контейнер. 64-битный отвергается словами: его раскладка не проверена ни на одном файле, а
разбор наугад подменил бы код формы мусором. Сборка контейнер не повторяет побайтно: `pack(unpack(x))` равен `x` по содержимому
секций, но не по байтам (в заголовке оглавления размер блока `0x1e1`; платформа такой контейнер принимает). Поэтому контейнер собирается заново, только если текст рядом с ним разошёлся с секциями (`repack_if_changed`).
"""
import os
import re
import struct
from pathlib import Path

SECTION_INFO = "info"
SECTION_FORM = "form"
SECTION_MODULE = "module"

BIN_NAME = "Form.bin"
# Имя файла на диске -> секция контейнера.
SIDECARS = {"form.frm": SECTION_FORM, "form.bsl": SECTION_MODULE, "info.txt": SECTION_INFO}

_END32 = 0x7FFFFFFF
_END64 = 0xFFFFFFFFFFFFFFFF
_HEADER = 16
_BLOCK_HEADER = 31          # CRLF + 8 + пробел + 8 + пробел + 8 + пробел + CRLF
_ENTRY = 12
_BLOCK = 0x200
_DESC_PREFIX = 20           # две метки времени (по 8 байт) и резерв (4 байта); у собранного контейнера все нули
_MAX_SIZE = 2 ** 31 - 1     # смещения знаковые 32-битные
_MAX_INFO = 0x10000         # info ищется по подстроке «\r\n0000»: с 65 536 байт размер перестаёт начинаться с нулей
_HEX = re.compile(r"[0-9a-fA-F]+")
_MARK = b"\r\n0000"


class FormBinError(ValueError):
    """Названный отказ разбора или сборки контейнера."""


def file_name(section):
    """Имя файла на диске для секции; неизвестная секция получает расширение `.dat`."""
    for name, known in SIDECARS.items():
        if known == section.lower():
            return name
    return section + ".dat"


def sidecar_section(name):
    """Секция по имени файла рядом с контейнером; `None`, если файл не из набора."""
    return SIDECARS.get(name.lower())


def _quote(raw):
    """Строка в двойных кавычках по правилам `%q` у Go (для текста отказов)."""
    out = ['"']
    for ch in raw.decode("utf-8", "surrogateescape"):
        code = ord(ch)
        if ch == '"' or ch == "\\":
            out.append("\\" + ch)
        elif ch in "\a\b\f\n\r\t\v":
            out.append({"\a": "\\a", "\b": "\\b", "\f": "\\f", "\n": "\\n", "\r": "\\r", "\t": "\\t", "\v": "\\v"}[ch])
        elif 0xDC80 <= code <= 0xDCFF:
            out.append("\\x%02x" % (code - 0xDC00))
        elif code < 0x20 or code == 0x7F:
            out.append("\\x%02x" % code)
        elif ch.isprintable():
            out.append(ch)
        elif code < 0x10000:
            out.append("\\u%04x" % code)
        else:
            out.append("\\U%08x" % code)
    out.append('"')
    return "".join(out)


def _parse_hex(text):
    """Hex-число без знака и без префикса, до 64 бит; иначе `None`."""
    if not _HEX.fullmatch(text):
        return None
    value = int(text, 16)
    return value if value < 2 ** 64 else None


_SPACE = re.compile("[\t\n\v\f\r \x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+")


def _fields(raw):
    """Слова между пробелами (набор пробелов — как у `strings.Fields` в Go); недекодируемые байты сохраняются."""
    return [w for w in _SPACE.split(raw.decode("utf-8", "surrogateescape")) if w]


# ---------------------------------------------------------------------------------------------------------------------
# Разбор


class _Reader:
    def __init__(self, data):
        self.data = data

    def block_header(self, offset):
        """Заголовок блока по смещению: `(размер документа, размер блока, смещение следующего)`."""
        have = len(self.data)
        if offset > have or have - offset < _BLOCK_HEADER:
            avail = have - offset if offset < have else 0
            raise FormBinError(f"Form.bin: не прочитать заголовок блока по смещению {offset}: "
                               f"осталось {avail} байт из нужных {_BLOCK_HEADER}")
        buf = self.data[offset:offset + _BLOCK_HEADER]
        parts = _fields(buf[2:_BLOCK_HEADER - 2])
        if len(parts) < 3:
            raise FormBinError(f"Form.bin: неверный формат заголовка блока по смещению {offset}: {_quote(buf)}")
        values = []
        for part in parts[:3]:
            value = _parse_hex(part)
            if value is None:
                quoted = _quote(part.encode("utf-8", "surrogateescape"))
                raise FormBinError(f"Form.bin: заголовок блока по смещению {offset}, поле {quoted} не hex-число")
            values.append(value)
        return tuple(values)

    def block(self, offset):
        """Блок целиком: `(размер документа, смещение следующего, данные)`; данные обрезаются по концу файла."""
        doc_size, block_size, nxt = self.block_header(offset)
        start = offset + _BLOCK_HEADER
        if start >= len(self.data):
            return doc_size, nxt, b""
        return doc_size, nxt, self.data[start:start + min(block_size, len(self.data) - start)]

    def document(self, offset, full):
        """Документ по цепочке блоков. `full` отдаёт блоки целиком, без обрезки по размеру документа: так читается
        оглавление, потому что секция `info` лежит за границей его документа, внутри того же блока."""
        out = bytearray()
        doc_size = None
        seen = set()
        while offset != _END32 and offset != 0:
            if offset in seen:
                raise FormBinError(f"Form.bin: цепочка блоков зациклилась на смещении {offset}")
            seen.add(offset)
            size, nxt, data = self.block(offset)
            if doc_size is None:
                doc_size = size
            out += data
            if len(out) > len(self.data):
                raise FormBinError(f"Form.bin: цепочка блоков длиннее файла ({len(out)} байт при файле в {len(self.data)})")
            offset = nxt
            if not full and len(out) >= doc_size:
                break
        if not full and doc_size is not None and len(out) > doc_size:
            del out[doc_size:]
        return bytes(out)

    def index(self):
        """Оглавление: список пар `(смещение описания, смещение данных)` и вложенная секция `info` (или `None`)."""
        index = self.document(_HEADER, True)
        entries = []
        pos = 0
        while pos + _ENTRY <= len(index):
            desc, data, marker = struct.unpack_from("<III", index, pos)
            if marker != _END32:      # запись без маркера — конец оглавления
                break
            entries.append((desc, data))
            pos += _ENTRY
        info = None
        if pos < len(index) - 4:
            rest = index[pos:]
            if rest.startswith(_MARK):
                info = _embedded_info(rest)
        return entries, info

    def file_entry(self, desc_offset, data_offset):
        desc = self.document(desc_offset, False)
        if len(desc) < _DESC_PREFIX:
            raise FormBinError(f"Form.bin: описание файла по смещению {desc_offset} слишком короткое, {len(desc)} байт")
        name = _section_name(desc[_DESC_PREFIX:])
        if name == "":
            raise FormBinError(f"Form.bin: пустое имя секции в описании по смещению {desc_offset}")
        return name, self.document(data_offset, False)


def _section_name(buf):
    """Имя секции: UTF-16LE до первого нулевого символа; нечётный хвост отбрасывается."""
    end = 0
    while end + 1 < len(buf) and (buf[end] or buf[end + 1]):
        end += 2
    return buf[:end].decode("utf-16-le", "replace")


def _embedded_info(data):
    """Секция `info` из вложенного контейнера в хвосте блока оглавления: после имени `info` (UTF-16LE) и его нулевого
    завершителя идёт заголовок блока данных. Любая неудача означает «секции нет»."""
    name = b"i\0n\0f\0o\0"
    at = data.find(name)
    if at < 0:
        return None
    start_from = at + len(name) + 4
    if start_from > len(data):
        return None
    rel = data.find(_MARK, start_from)
    if rel < 0:
        return None
    head = rel + 2
    if head + 27 > len(data):
        return None
    parts = _fields(data[head:head + 27])
    if len(parts) < 2:
        return None
    size = _parse_hex(parts[0])
    if size is None:
        return None
    start = rel + _BLOCK_HEADER
    if start > len(data):
        return None
    return data[start:start + min(size, len(data) - start)]


def _reader(data):
    if len(data) < _HEADER:
        raise FormBinError(f"Form.bin: файл слишком короткий, {len(data)} байт при заголовке в {_HEADER}")
    if struct.unpack_from("<I", data)[0] == _END32:
        return _Reader(data)
    if struct.unpack_from("<Q", data)[0] == _END64:
        raise FormBinError("Form.bin: 64-битный контейнер не поддерживается — его раскладка не проверена ни на одном "
                           "реальном файле, а разбор наугад молча подменил бы код формы мусором")
    raise FormBinError(f"Form.bin: это не контейнер Form.bin — вместо маркера 0x{_END32:08x} в начале файла "
                       f"0x{struct.unpack_from('<I', data)[0]:08x}")


def unpack(data):
    """Секции контейнера: `{имя секции: содержимое}` (`form`, `module`, `info`). Нечитаемая запись — отказ, а не пропуск:
    молча потерянная секция после обратной сборки уничтожила бы часть формы. Пустая `info` считается отсутствующей."""
    reader = _reader(bytes(data))
    entries, info = reader.index()
    sections = {}
    if info:
        sections[SECTION_INFO] = info
    for desc, body in entries:
        name, content = reader.file_entry(desc, body)
        if name in sections:
            raise FormBinError(f"Form.bin: секция {_quote(name.encode())} встречается дважды")
        sections[name] = content
    if not sections:
        raise FormBinError("Form.bin: контейнер не содержит ни одной секции")
    return sections


# ---------------------------------------------------------------------------------------------------------------------
# Сборка


def _block_header(doc_size, block_size):
    return b"\r\n%08x %08x %08x \r\n" % (doc_size, block_size, _END32)


def _file_entry(name):
    return bytes(_DESC_PREFIX) + name.encode("utf-16-le") + bytes(4)


def _align(size):
    return _BLOCK if size == 0 else (size + _BLOCK - 1) // _BLOCK * _BLOCK


def _pad(out, target):
    if len(out) < target:
        out += bytes(target - len(out))


def pack(sections):
    """Контейнер из секций. `form` и `module` обязательны, `info` нет; других секций упаковщик не знает. Пустая `info`
    считается отсутствующей. `info` от 65 536 байт — отказ: при разборе её не найти."""
    for needed in (SECTION_FORM, SECTION_MODULE):
        if needed not in sections:
            raise FormBinError(f"Form.bin: отсутствует обязательная секция {_quote(needed.encode())}")
    unknown = sorted(name for name in sections if name not in (SECTION_FORM, SECTION_MODULE, SECTION_INFO))
    if unknown:
        raise FormBinError(f'Form.bin: упаковщик знает только секции "form", "module" и "info", а переданы ещё: '
                           f"{', '.join(unknown)}")
    info = sections.get(SECTION_INFO) or None
    if info is not None and len(info) >= _MAX_INFO:
        raise FormBinError(f'Form.bin: секция "info" в {len(info)} байт не читается обратно, предел — {_MAX_INFO - 1}')

    files = [(SECTION_FORM, bytes(sections[SECTION_FORM])), (SECTION_MODULE, bytes(sections[SECTION_MODULE]))]
    entries_size = len(files) * _ENTRY
    info_entry = b""
    embedded = 0
    if info is not None:
        info_entry = _file_entry(SECTION_INFO)
        embedded = _BLOCK_HEADER + len(info_entry) + _BLOCK_HEADER + len(info)
    index_total = _align(_BLOCK_HEADER + entries_size + embedded)

    offset = _HEADER + index_total
    placed = []
    for name, body in files:
        entry = _file_entry(name)
        desc_block = _align(_BLOCK_HEADER + len(entry))
        data_block = _align(_BLOCK_HEADER + len(body))
        placed.append((entry, body, offset, offset + desc_block, desc_block, data_block))
        offset += desc_block + data_block
    if offset > _MAX_SIZE:
        raise FormBinError(f"Form.bin: контейнер вышел на {offset} байт, предел формата — {_MAX_SIZE}")

    out = bytearray(struct.pack("<IIII", _END32, _BLOCK, len(files), 0))
    out += _block_header(entries_size, index_total - _BLOCK_HEADER)
    for _entry, _body, desc_at, data_at, _db, _ddb in placed:
        out += struct.pack("<III", desc_at, data_at, _END32)
    if info is not None:
        # Вложенный контейнер: заголовок описания, описание, заголовок данных, данные. Размер блока у описания — его длина,
        # у данных — 512; при разборе берётся только размер документа.
        out += _block_header(len(info_entry), len(info_entry)) + info_entry
        out += _block_header(len(info), _BLOCK) + info
    _pad(out, _HEADER + index_total)
    for entry, body, _desc_at, data_at, desc_block, data_block in placed:
        out += _block_header(len(entry), desc_block - _BLOCK_HEADER) + entry
        _pad(out, data_at)
        out += _block_header(len(body), data_block - _BLOCK_HEADER) + body
        _pad(out, data_at + data_block)
    return bytes(out)


# ---------------------------------------------------------------------------------------------------------------------
# Файлы рядом с контейнером


def unpack_file(bin_path, only_missing=False):
    """Раскладывает контейнер рядом с ним: по файлу на секцию. Возвращает имена записанных файлов. По умолчанию уже
    существующие файлы перезаписываются (истина — в контейнере, как у инструмента выгрузки); `only_missing` пишет только недостающие."""
    bin_path = Path(bin_path)
    sections = unpack(bin_path.read_bytes())
    written = []
    for section, body in sections.items():
        name = file_name(section)
        target = bin_path.parent / name
        if only_missing and target.exists():
            continue
        target.write_bytes(body)
        written.append(name)
    return written


def find_bins(root):
    """Все `Form.bin` под каталогом (имя без учёта регистра), в порядке пути."""
    root = Path(root)
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        found += [Path(dirpath) / n for n in sorted(filenames) if n.lower() == BIN_NAME.lower()]
    return found


def unpack_under(root, only_missing=False):
    """Раскладывает все `Form.bin` под каталогом. Нечитаемый контейнер обход не прерывает: он попадает в список отказов.
    Возвращает `(число разложенных, [(путь, причина)])`."""
    done, failed = 0, []
    for path in find_bins(root):
        try:
            unpack_file(path, only_missing)
        except (FormBinError, OSError) as err:
            failed.append((path, str(err)))
            continue
        done += 1
    return done, failed


def sidecar_sections(dir_path, inside):
    """Секции, какими они станут при сборке: файл рядом заменяет секцию, нет файла — секция остаётся как в контейнере.
    Пустой `info.txt` значит «секции `info` нет». Возвращает `(секции, имена разошедшихся файлов)`."""
    dir_path = Path(dir_path)
    nxt, changed = {}, []
    for name, section in SIDECARS.items():
        try:
            body = (dir_path / name).read_bytes()
        except FileNotFoundError:
            if section in inside:
                nxt[section] = inside[section]
            continue
        if section == SECTION_INFO:
            if body:
                nxt[section] = body
            if (body or None) != (inside.get(section) or None):
                changed.append(name)
            continue
        nxt[section] = body
        if section not in inside or inside[section] != body:
            changed.append(name)
    return nxt, changed


def changed_files(bin_path):
    """Имена файлов рядом (`form.frm`, `form.bsl`, `info.txt`), содержимое которых разошлось с секциями контейнера (сравниваются
    секции, не байты контейнера). Контейнер нечитаем — отказ `FormBinError`."""
    bin_path = Path(bin_path)
    return sidecar_sections(bin_path.parent, unpack(bin_path.read_bytes()))[1]


def differs(bin_path):
    """Разошлось ли содержимое файлов рядом с секциями контейнера."""
    return bool(changed_files(bin_path))


def repack_if_changed(bin_path):
    """Собирает контейнер заново, если текст рядом с ним разошёлся с его секциями. Возвращает `True`, если контейнер
    переписан. Сравниваются секции, а не байты контейнера: сборка не побайтова, и сравнение байтов давало бы «изменилось»
    всегда. Запись идёт через временный файл рядом и замену: половина контейнера на месте рабочей формы хуже
    несобранной правки."""
    bin_path = Path(bin_path)
    nxt, changed = sidecar_sections(bin_path.parent, unpack(bin_path.read_bytes()))
    if not changed:
        return False
    packed = pack(nxt)
    tmp = bin_path.with_name(bin_path.name + ".repack")
    try:
        tmp.write_bytes(packed)
        os.replace(tmp, bin_path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
    return True
