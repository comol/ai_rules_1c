"""Картинки библиотеки платформы (`БиблиотекаКартинок`, 299 имён) для рендера: значки стандартных действий и картинки, на которые форма ссылается без файла.

Откуда: платформа 1С:Предприятие 8.3.27.1936, вариант интерфейса «обычное приложение» (`version8_2_OrdinaryApp`), обычная плотность экрана; каталог — `data/platform_pictures/`
(файлы PNG и SVG как отдала платформа, `index.json`: имя → файл, размер, код и GUID ссылки).

Как форма ссылается на такую картинку (блок картинки, источник 1): отрицательным кодом без GUID (20 картинок: −13 «Печать», −1 «ПолеВводаВыбрать», −8/−9 «ПереместитьВлево/Вправо»…) либо
кодом 0 и GUID картинки платформы. Общие картинки конфигурации (GUID, которого нет в каталоге) рисует `configpics`.

`Bitmap` — `data:`-адрес со своим размером в пикселях: 283 картинки 16×16 (263 PNG и 20 SVG), 10 — 12×12 (значок в кнопке 16×16 стоит по центру), 4 — 32×32, 2 — 16×24.
"""
import base64
import json
import os
import pathlib
import unicodedata
from functools import lru_cache

from . import datapaths

ENV_DIR = "FRM_PLATFORM_PICTURES"      # каталог с файлами картинок платформы (PNG и SVG); пусто — `data/platform_pictures/` пакета

MEDIA = {"png": "image/png", "svg": "image/svg+xml"}


class Bitmap(str):
    """`data:`-адрес картинки с её размером: `.w`, `.h` (пиксели), `.name` — имя в библиотеке."""

    def __new__(cls, uri, w, h, name=None):
        self = super().__new__(cls, uri)
        self.w, self.h, self.name = w, h, name
        return self


def _key(name):
    return unicodedata.normalize("NFC", " ".join((name or "").split())).casefold().replace("ё", "е")


@lru_cache(maxsize=1)
def _index():
    """`(имя → запись, имя без регистра → имя, код → имя, guid → имя)`."""
    path = datapaths.PLATFORM_PICTURES_DIR / "index.json"
    table = json.loads(path.read_text(encoding="utf-8"))
    by_key = {_key(name): name for name in table}
    by_code = {rec["code"]: name for name, rec in table.items() if rec["code"]}
    by_guid = {rec["guid"]: name for name, rec in table.items() if rec["guid"]}
    return table, by_key, by_code, by_guid


def names():
    """Имена картинок библиотеки."""
    return sorted(_index()[0])


def name_of_code(code):
    """Имя картинки библиотеки по отрицательному коду ссылки (без GUID) либо `None`."""
    return _index()[2].get(code)


def record(name):
    """Запись каталога `{file, w, h, code, guid}` по имени (регистр не важен) либо `None`."""
    table, by_key, _code, _guid = _index()
    real = by_key.get(_key(name))
    return dict(table[real], name=real) if real else None


def known(name):
    return _key(name) in _index()[1]


def files_dir():
    """Где лежат файлы картинок платформы: переменная `FRM_PLATFORM_PICTURES`, иначе `data/platform_pictures/` пакета. Сам `index.json` — всегда в пакете."""
    own = os.environ.get(ENV_DIR)
    return pathlib.Path(own) if own else datapaths.PLATFORM_PICTURES_DIR


_MISSED = []          # имена картинок, которые известны каталогу, а файла нет: рендер называет их в `notes` (`take_missed`)
_BITMAPS = {}


def take_missed():
    """Имена картинок, которых не нашлось файлом, с прошлого вызова; список очищается."""
    out = list(dict.fromkeys(_MISSED))
    del _MISSED[:]
    return out


def missing_note(names, where=None):
    """Строка `notes` о картинках платформы без файлов, либо `None`, если `names` пуст."""
    if not names:
        return None
    return (f"картинки платформы не нарисованы ({', '.join(names)}): файлов картинок платформы нет в каталоге {where or files_dir()}; "
            "положите их туда, чтобы рендер их рисовал, — на месте картинки серый квадрат")


def bitmap(name):
    """`Bitmap` картинки библиотеки по имени (регистр не важен) либо `None`: имени нет в каталоге или файла картинки нет (тогда имя попадает в `take_missed`)."""
    table, by_key, _code, _guid = _index()
    real = by_key.get(_key(name))
    if real is None:
        return None
    rec = table[real]
    path = files_dir() / rec["file"]
    cached = _BITMAPS.get(path)
    if cached is not None:
        return cached
    try:
        data = path.read_bytes()
    except OSError:
        _MISSED.append(real)
        return None
    kind = rec["file"].rsplit(".", 1)[1]
    got = _BITMAPS[path] = Bitmap(f"data:{MEDIA[kind]};base64," + base64.b64encode(data).decode("ascii"), rec["w"], rec["h"], real)
    return got


def _guid_of(ref):
    guid = ref.get("guid") if isinstance(ref, dict) else None
    guid = guid.get("guid") if isinstance(guid, dict) else guid
    return guid.lower() if isinstance(guid, str) and guid else None


def name_of_picture(picture):
    """Имя картинки платформы по блоку картинки формы (источник 1: отрицательный код либо GUID из каталога) либо `None`: не платформенная ссылка или имени нет."""
    if not isinstance(picture, dict) or picture.get("source") != 1:
        return None
    ref = picture.get("ref")
    if not isinstance(ref, dict):
        return None
    guid = _guid_of(ref)
    _table, _keys, by_code, by_guid = _index()
    code = ref.get("code")
    name = by_guid.get(guid) if guid else by_code.get(code) if isinstance(code, int) and not isinstance(code, bool) and code < 0 else None
    return name


def of_picture(picture):
    """`Bitmap` картинки платформы по блоку картинки формы либо `None`: не платформенная ссылка, имени нет или нет файла картинки."""
    name = name_of_picture(picture)
    return bitmap(name) if name else None
