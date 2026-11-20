"""Общие картинки конфигурации для рендера: форма ссылается на них по uuid метаданных, файлы лежат в выгрузке рядом с формой.

Ссылка в форме — блок картинки с источником 1, кодом 0 и GUID (`ref.guid`): это `uuid` объекта «Общая картинка», записанный в
`CommonPictures/<Имя>.xml` (`<CommonPicture uuid="…">`). Файл картинки — `CommonPictures/<Имя>/Ext/Picture/<файл>`, имя файла и прозрачность называет
`CommonPictures/<Имя>/Ext/Picture.xml` (`xr:Abs`, `xr:LoadTransparent`, `xr:TransparentPixel`). Ссылки без GUID (код −10, −11, −2, −13) — картинки платформы, их здесь нет.

Корень выгрузки (где лежат `Catalogs/`, `CommonPictures/`, `Configuration.xml`) находится по порядку: ключ `--config`; затем подъём от пути формы до каталога с
`Configuration.xml`; затем по раскладке выгрузки (`<Корень>/<Вид>/<Объект>/Forms/<Форма>/Ext/form.frm`, у общей формы `<Корень>/CommonForms/<Форма>/Ext/form.frm`) —
так корень находится и тогда, когда рядом лежит одна форма без остальной выгрузки.

Имя по uuid берётся из `CommonPictures/*.xml`, запасной источник — `ConfigDumpInfo.xml` (`CommonPicture.<Имя>` и `id`). Ссылка с GUID бывает и на картинку библиотеки платформы,
файла у неё в выгрузке нет: когда `ConfigDumpInfo.xml` лежит рядом и GUID в нём не назван, это картинка платформы — рисуется как раньше, файлов не просит. Что рисуется: PNG как есть; BMP, ICO и GIF — переводом в PNG (`picture_files`); прозрачный пиксель BMP — по `Picture.xml` (`LoadTransparent` и `TransparentPixel`), без него картинка непрозрачна (у ICO и GIF прозрачность своя). Прочие виды файла не рисуются:
на месте картинки остаётся серый квадрат, а команда называет вид словами.

Результат поиска копится на команду (`activate` … `deactivate`): чего не хватило — `needed()`, что не рисуется — `problems()`; командная строка печатает их один раз по концу работы.
"""
import base64
import pathlib
import re


NEED_PREFIX = "нужны файлы выгрузки: "
PICTURES_DIR = "CommonPictures"
INFO_FILE = "ConfigDumpInfo.xml"
ALL_NAMES = f"{PICTURES_DIR}/*.xml"        # имя по uuid узнать не из чего: нужны описания всех общих картинок
WHOLE_DIR_FROM = 10                         # столько недостающих картинок — просят каталог целиком
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

_UUID_HEAD = 8192                           # `uuid` стоит в начале описания, дальше свойства
_UUID = re.compile(r'<CommonPicture\s+uuid="([0-9A-Fa-f-]{36})"')
_INFO = re.compile(r'<Metadata name="CommonPicture\.([^".]+)" id="([0-9A-Fa-f-]{36})"')
_ABS = re.compile(r"<xr:Abs>([^<]*)</xr:Abs>")
_LOAD_TRANSPARENT = re.compile(r"<xr:LoadTransparent>([^<]*)</xr:LoadTransparent>")
_TRANSPARENT_PIXEL = re.compile(r'<xr:TransparentPixel\s+x="(\d+)"\s+y="(\d+)"')


def find_root(form=None, config=None):
    """Корень выгрузки (`pathlib.Path`) либо `None`: ключ `config`, подъём до `Configuration.xml`, раскладка выгрузки по пути формы."""
    if config:
        return pathlib.Path(config)
    if not form:
        return None
    path = pathlib.Path(form)
    for parent in [path] + list(path.parents):
        try:
            if (parent / "Configuration.xml").is_file():
                return parent
        except OSError:
            break
    parts = path.parts
    for at in range(len(parts) - 1, -1, -1):
        if parts[at] == "Forms" and at >= 2:
            return pathlib.Path(*parts[:at - 2]) if at > 2 else pathlib.Path(".")
        if parts[at] == "CommonForms" and at >= 1:
            return pathlib.Path(*parts[:at])
    return None


def _read(path):
    try:
        return path.read_bytes()
    except OSError:
        return None


def _text(path, limit=None):
    data = _read(path)
    if data is None:
        return None
    return (data[:limit] if limit else data).decode("utf-8-sig", errors="replace")


class Pictures:
    """Картинки конфигурации одной выгрузки: поиск по uuid с памятью на время команды."""

    def __init__(self, root):
        self.root = root
        self._names = None          # uuid (строчными) → имя из CommonPictures/*.xml
        self._info = None           # uuid → имя из ConfigDumpInfo.xml
        self._info_ok = False
        self._cache = {}
        self._needed = []           # пути от корня выгрузки; порядок появления
        self._problems = []

    def _by_xml(self):
        if self._names is None:
            self._names = {}
            folder = self.root / PICTURES_DIR if self.root else None
            try:
                files = sorted(p for p in folder.iterdir() if p.suffix == ".xml" and p.is_file()) if folder and folder.is_dir() else []
            except OSError:
                files = []
            for file in files:
                found = _UUID.search(_text(file, _UUID_HEAD) or "")
                if found:
                    self._names[found.group(1).lower()] = file.stem
        return self._names

    def _by_info(self):
        if self._info is None:
            self._info = {}
            text = _text(self.root / INFO_FILE) if self.root else None
            self._info_ok = text is not None
            for name, uuid in _INFO.findall(text or ""):
                self._info[uuid.lower()] = name
        return self._info

    def _info_read(self):
        """ConfigDumpInfo.xml читается (он есть в выгрузке и разобран)."""
        self._by_info()
        return self._info_ok

    def name_of(self, uuid):
        """Имя общей картинки по uuid либо `None`."""
        key = uuid.lower()
        return self._by_xml().get(key) or self._by_info().get(key)

    def _need(self, path):
        if path not in self._needed:
            self._needed.append(path)

    def _problem(self, text):
        if text not in self._problems:
            self._problems.append(text)

    def uri(self, uuid):
        """`data:image/png;base64,…` общей картинки с этим uuid либо `None` (не нашлась или не рисуется — причина в `needed()`/`problems()`)."""
        key = uuid.lower()
        if key not in self._cache:
            self._cache[key] = self._load(key)
        return self._cache[key]

    def _load(self, uuid):
        name = self.name_of(uuid)
        if name is None:
            if self._info_read():
                return None          # ConfigDumpInfo.xml перечисляет все общие картинки конфигурации: этой в нём нет — значит, это картинка платформы, файла у неё в выгрузке нет
            if not self._by_xml():
                self._need(ALL_NAMES)
            self._need(INFO_FILE)    # описаний не хватает или они неполны: решает ConfigDumpInfo.xml
            return None
        ext = self.root / PICTURES_DIR / name / "Ext"
        described = _text(ext / "Picture.xml")
        shown = f"{PICTURES_DIR}/{name}/Ext"
        if described is None:
            self._need(shown)
            return None
        file = _ABS.search(described)
        if not file or not file.group(1).strip() or "/" in file.group(1) or "\\" in file.group(1) or ".." in file.group(1):
            self._problem(f"картинка конфигурации «{name}»: в Picture.xml нет имени файла картинки — рисуется серый квадрат")
            return None
        file = file.group(1).strip()
        data = _read(ext / "Picture" / file)
        if data is None:
            self._need(shown)
            return None
        return self._draw(name, file, data, described)

    def _draw(self, name, file, data, described):
        suffix = pathlib.PurePath(file).suffix.lower()
        from . import picture_files
        from .render import picture_bitmap
        kinds = {".png": "png", ".bmp": "bmp", ".ico": "ico", ".gif": "gif"}
        if suffix not in kinds:
            self._problem(f"картинка конфигурации «{name}»: вид файла {suffix or file} не рисуется — рисуется серый квадрат")
            return None
        if picture_files.kind_of(data) != kinds[suffix]:
            self._problem(f"картинка конфигурации «{name}»: файл {file} не {kinds[suffix].upper()} — рисуется серый квадрат")
            return None
        key = "corner"
        if suffix == ".bmp":
            load = _LOAD_TRANSPARENT.search(described)
            key = None
            if load and load.group(1).strip().lower() == "true":
                pixel = _TRANSPARENT_PIXEL.search(described)
                key = (int(pixel.group(1)), int(pixel.group(2))) if pixel else "corner"
        bitmap = picture_bitmap.uri_of_file(data, key)
        if bitmap is None:
            self._problem(f"картинка конфигурации «{name}»: {kinds[suffix].upper()} {file} этого строения не читается — рисуется серый квадрат")
            return None
        return bitmap

    def needed(self):
        """Пути от корня выгрузки, которых не хватило (порядок появления); при многих недостающих — каталог `CommonPictures` целиком."""
        paths = list(self._needed)
        if sum(1 for p in paths if p not in (ALL_NAMES, INFO_FILE)) >= WHOLE_DIR_FROM:
            return [PICTURES_DIR]
        return paths

    def problems(self):
        return list(self._problems)


_active = None


def activate(form=None, config=None):
    """Включить поиск картинок для команды: `form` — путь формы, `config` — каталог выгрузки. Без обоих — выключено."""
    global _active
    _active = Pictures(find_root(form, config)) if form or config else None
    return _active


def deactivate():
    global _active
    _active = None


def active():
    return _active


def uri_of(picture):
    """`data:`-адрес общей картинки по блоку картинки формы (источник 1, ссылка с GUID) либо `None`: поиск выключен, ссылка без GUID (картинка платформы), файла нет."""
    if _active is None or not isinstance(picture, dict) or picture.get("source") != 1:
        return None
    ref = picture.get("ref")
    guid = ref.get("guid") if isinstance(ref, dict) else None
    guid = guid.get("guid") if isinstance(guid, dict) else guid
    if not isinstance(guid, str) or not guid:
        return None
    return _active.uri(guid)


def need_line():
    """Строка «нужны файлы выгрузки: …» либо пусто."""
    if _active is None:
        return ""
    paths = _active.needed()
    return NEED_PREFIX + ", ".join(paths) if paths else ""


def problem_lines():
    return _active.problems() if _active is not None else []
