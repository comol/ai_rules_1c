"""Картинка, вложенная в файл формы (источник «из файла», `source` = 3): файл любого вида → PNG для рисунка.

Обычная форма хранит картинку по-разному: картинка библиотеки платформы (`source` 1, отрицательный код либо GUID платформы: рисует `platform_pictures`) или общая картинка конфигурации (`source` 1 с GUID конфигурации:
файл ищет `configpics` в выгрузке) или собственный рисунок, вложенный в файл как есть (`source` 3, запись `u7`): PNG, BMP, ICO или GIF (`picture_files`). Для третьего способа настоящий значок есть в самом файле, и рендер
рисует его, а не серый квадрат. У BMP прозрачность задаёт сама запись картинки: позиции `u4`, `u5` — координаты пикселя прозрачности (x, y) от ВЕРХНЕГО левого угла с нуля, прозрачен каждый пиксель того же цвета; `-1, -1` — картинка непрозрачна
(как `TransparentPixel` общей картинки). Точка за пределами картинки ничего не прозрачит и названа в `notes`. У PNG, ICO и GIF прозрачность своя (альфа-канал, маска значка, прозрачный индекс), `u4`/`u5` у них точкой
прозрачности не служат; PNG и GIF без неё непрозрачны.
Картинка стоит в своём размере: `Bitmap.w/h` (у картинки платформы — как у неё в каталоге).
"""
import base64
from xml.sax.saxutils import escape

import collections
import hashlib

from .. import picture_files, picture_raster
from .core import _n
from ..platform_pictures import Bitmap

def uri_of_file(data, key="corner"):
    """`Bitmap` (`data:image/png;base64,…` со своим размером) по байтам файла картинки либо `None` (вид не опознан или не читается)."""
    got = picture_files.decode(data, key)
    return Bitmap("data:image/png;base64," + base64.b64encode(got.png).decode("ascii"), got.w, got.h) if got else None


def _placeholder_png():
    rows = [[(153, 153, 153, 255) if y in (0, 15) or x in (0, 15) else (216, 216, 216, 255) for x in range(16)] for y in range(16)]
    return picture_files.png_of(16, 16, rows)


PLACEHOLDER_NAME = "unreadable"
PLACEHOLDER = Bitmap("data:image/png;base64," + base64.b64encode(_placeholder_png()).decode("ascii"), 16, 16, PLACEHOLDER_NAME)


def is_placeholder(bitmap):
    """Это серый квадрат 16×16, который стоит на месте вложенной картинки, файл которой не читается."""
    return getattr(bitmap, "name", None) == PLACEHOLDER_NAME


def file_bytes(picture):
    """Байты файла вложенной картинки (`{source: 3, u7: [[{base64: …}]]}`) либо `None`: блок не такой или данных нет."""
    if not isinstance(picture, dict) or picture.get("source") != 3:
        return None
    try:
        return base64.b64decode(picture["u7"][0][0]["base64"])
    except (TypeError, KeyError, IndexError, ValueError):
        return None


def unreadable_reason(picture):
    """Слова, почему вложенная в файл картинка не читается (вид не опознан, слишком крупная, строение), либо `None`, если картинки нет или она читается."""
    data = file_bytes(picture)
    return picture_files.why_unreadable(data) if data is not None and uri_of_file(data) is None else None


def data_uri(picture):
    """`data:image/png;base64,…` (у картинки платформы — `platform_pictures.Bitmap` со своим размером, PNG или SVG) по блоку картинки кнопки: вложенной в файл (`{source: 3, u7: [[{base64: …}]]}`) либо общей картинки конфигурации (источник 1 со ссылкой-GUID,
    файл ищет `configpics` в выгрузке); `None` — картинки в файле нет, она не читается или её файла нет. Результат — `Bitmap` со своим размером, кроме общей картинки конфигурации."""
    if isinstance(picture, dict) and picture.get("source") == 1:
        from .. import configpics, platform_pictures
        name = platform_pictures.name_of_picture(picture)       # картинка библиотеки платформы — раньше выгрузки: GUID платформы в выгрузке не бывает
        if name:
            return platform_pictures.bitmap(name) or PLACEHOLDER      # файла картинки нет: серый квадрат, причину называет `notes` (`platform_pictures.missing_note`)
        return configpics.uri_of(picture)
    if not isinstance(picture, dict) or picture.get("source") != 3:
        return None
    data = file_bytes(picture)
    if data is None:
        return None
    return uri_of_file(data, transparent_key(picture)) or PLACEHOLDER          # файл не читается: серый квадрат на месте картинки (причину называют `notes`)


def transparent_key(picture):
    """Ключ прозрачности BMP по записи картинки: `(x, y)` — точка прозрачного цвета (`u4`, `u5`), `None` — картинка непрозрачна (`-1, -1`, пустые и невозможные значения)."""
    x, y = picture.get("u4"), picture.get("u5")
    if isinstance(x, bool) or isinstance(y, bool) or not isinstance(x, int) or not isinstance(y, int) or x < 0 or y < 0:
        return None
    return x, y


def transparent_point_outside(picture):
    """Слова, если у вложенного BMP точка прозрачности лежит за пределами картинки (она ничего не прозрачит), иначе `None`."""
    data = file_bytes(picture)
    key = transparent_key(picture) if data is not None and data[:2] == b"BM" else None
    if key is None:
        return None
    got = picture_files.decode(data, None)
    if got is None or (key[0] < got.w and key[1] < got.h):
        return None
    return f"точка прозрачности вложенной картинки ({key[0]}, {key[1]}) лежит за пределами {got.w}×{got.h}: картинка нарисована непрозрачной"


_RESIZED = collections.OrderedDict()
_RESIZED_SIZE = 512


def _resized(uri, w, h, how):
    """Пересчитанный `data:`-адрес; помнится по хешу адреса (ключ в сотни килобайт держал бы память), а не по самому адресу."""
    token = (hashlib.sha1(uri.encode("ascii", "ignore")).digest(), w, h, how)
    if token in _RESIZED:
        _RESIZED.move_to_end(token)
        return _RESIZED[token]
    got = _resize_uncached(uri, w, h, how)
    _RESIZED[token] = got
    while len(_RESIZED) > _RESIZED_SIZE:
        _RESIZED.popitem(last=False)
    return got


def _resize_uncached(uri, w, h, how):
    if w <= 0 or h <= 0:
        return None                         # нулевой размер места: пересчитывать некуда (рисунок строит вызывающий)
    head, _, body = uri.partition(",")
    if "image/png" not in head:
        return None
    got = picture_raster.read_png(base64.b64decode(body))
    if got is None or not got[2]:
        return None
    rows = (picture_raster.nearest if how == "nearest" else picture_raster.area)(got[2], w, h)
    return "data:image/png;base64," + base64.b64encode(picture_raster.png_of_rows(rows)).decode("ascii")


def resized(bitmap, w, h, how="area"):
    """`Bitmap` картинки, пересчитанной в `w`×`h` пикселей по правилу предприятия (`picture_raster`: `area` — среднее по площади, `nearest` — симметричный ближайший сосед) либо `None`, если исходник не PNG или не читается."""
    out = _resized(str(bitmap), w, h, how)
    return Bitmap(out, w, h, getattr(bitmap, "name", None)) if out else None


def scaled_at(x, y, w, h, bitmap, how="area", css="icon button-bitmap", title=None, clip=None):
    """`<image>` картинки `bitmap`, пересчитанной в `w`×`h` и положенной в (x, y) один к одному; нечитаемая PNG-картинка (SVG, необычный PNG) — растяжение средством просмотра."""
    own = (getattr(bitmap, "w", None), getattr(bitmap, "h", None))
    if own == (w, h):
        return image_at(x, y, w, h, bitmap, css, title, clip)
    made = resized(bitmap, w, h, how)
    return image_at(x, y, w, h, made if made else bitmap, css, title, clip, crisp=(how == "nearest" and made is None))


def size_of(bitmap, box=16):
    """Размер картинки `(w, h)` в пикселях: у `Bitmap` — свой, у остальных (заглушка, значок действия) — квадрат `box`."""
    return getattr(bitmap, "w", box), getattr(bitmap, "h", box)


def image_tag(x, y, bitmap, box=16, title=None, css="icon button-bitmap"):
    """`<image>` картинки `bitmap` (`data:`-адрес) в квадрате `box`×`box` с левым верхним углом (x, y). Картинка стоит по центру квадрата в своём размере (`Bitmap.w/h`;
    у платформы 12×12 в кнопке 16×16 — с отступом по 2 px); крупнее квадрата сжимается в него; у картинки без размера (значок действия) размер — весь квадрат."""
    w, h = size_of(bitmap, box)
    if w > box or h > box:                      # значок командной панели и кнопки поля — не больше квадрата: крупнее сжимается по большей стороне (32 px в панели — 16 px, снято в предприятии)
        scale = min(box / w, box / h)
        w, h = max(round(w * scale), 1), max(round(h * scale), 1)
    left, top = x + (box - w) // 2, y + (box - h) // 2
    return scaled_at(left, top, w, h, bitmap, "area", css, title)


def image_at(x, y, w, h, bitmap, css="icon button-bitmap", title=None, clip=None, crisp=False):
    """`<image>` картинки `bitmap` растянутой на `w`×`h` с левым верхним углом (x, y): `clip` = `(x, y, w, h)` обрезает по прямоугольнику; `crisp` — без сглаживания, ближайший
    сосед (картинка формы, растянутая на клиентскую область: края ступеньками, как в предприятии); иначе размер в свои пиксели или сглаживание (надпись)."""
    inner = f"<title>{escape(title)}</title>" if title else ""
    own = (getattr(bitmap, "w", None), getattr(bitmap, "h", None))
    stretched = None not in own and round(w * own[1]) != round(h * own[0])       # пропорции не свои: без `none` средство просмотра вписало бы картинку, а не растянуло
    image = (f"<image class='{css}' x='{_n(x)}' y='{_n(y)}' width='{_n(w)}' height='{_n(h)}' href='{bitmap}'"
             + (" preserveAspectRatio='none'" if stretched else "")
             + (" image-rendering='optimizeSpeed' style='image-rendering:pixelated'" if crisp else "") + f">{inner}</image>")
    if clip is None:
        return image
    cx, cy, cw, ch = clip
    cid = f"pc{_n(cx)}_{_n(cy)}_{_n(cw)}_{_n(ch)}".replace(".", "p")
    return f"<clipPath id='{cid}'><rect x='{_n(cx)}' y='{_n(cy)}' width='{_n(cw)}' height='{_n(ch)}'/></clipPath><g clip-path='url(#{cid})'>{image}</g>"
