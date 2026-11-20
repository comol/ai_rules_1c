"""Откуда команды навыка берут форму и когда они раскладывают и собирают `Form.bin`. Подробно — `docs/formbin.md`.

Форму называют путём к `form.frm`, к `Form.bin`, к каталогу `Ext` или к каталогу формы (`Forms/<Имя>`); документы уровня 1
(`.json`) этот модуль не разбирает. Решение о раскладке и сборке принимается здесь, в одном месте.

| команда                       | `form.frm` рядом есть | `form.frm` рядом нет, есть `Form.bin`              |
|-------------------------------|-----------------------|----------------------------------------------------|
| чтение (`decode`, `lint` …)   | читает файл           | распаковывает в памяти, на диск не пишет           |
| правка (`edit`, `generate` …) | правит файл           | читает контейнер в памяти; при записи `-o …/form.frm` рядом с `Form.bin` раскладывает недостающие файлы |

После правки `Form.bin` собирается, только если `form.frm`, `form.bsl` или `info.txt` разошлись с его секциями. В каталоге с внешней
сборкой (среди каталогов выше есть `.v8mirror.json`) навык `Form.bin` не собирает: при отправке файлов его соберёт внешний инструмент.

Если содержимое файлов и контейнера разошлось, направление расхождения определяет время изменения: файлы новее контейнера —
это правка рукой (правка и `pack` её собирают); контейнер новее файлов — файлы устарели (например, после новой выгрузки), и сборка
из них откатила бы контейнер: правка и `pack` отказывают, чтение читает контейнер.
"""
import os
from pathlib import Path

from . import formbin
from .tree import parse

MIRROR_STATE = ".v8mirror.json"
FORM_FILE = "form.frm"
BIN_LOWER = formbin.BIN_NAME.lower()


class FormRef:
    """Место формы: каталог, путь к `form.frm` (файла может не быть) и путь к `Form.bin` (или `None`)."""

    def __init__(self, dir_path, frm, bin_path):
        self.dir, self.frm, self.bin = Path(dir_path), Path(frm), bin_path

    @property
    def plain(self):
        """Файл `*.frm` с другим именем: контейнера у него нет, собирать и раскладывать нечего."""
        return self.frm.name != FORM_FILE


def is_form_ref(path):
    """Путь называет форму (а не документ уровня 1): каталог, файл `*.frm` или `Form.bin`."""
    p = Path(path)
    return p.is_dir() or p.suffix.lower() == ".frm" or p.name.lower() == BIN_LOWER


def check_output(path, flag, form=True):
    """Файл вывода команды: `Form.bin` (с любым регистром) и каталог отвергаются до любой работы. Запись текста формы поверх
    двоичного контейнера уничтожила бы его. Возвращает `Path`."""
    p = Path(path)
    if p.name.lower() == BIN_LOWER or p.is_dir():
        what = "Form.bin" if p.name.lower() == BIN_LOWER else "каталог"
        tail = (f"{flag} — путь к form.frm рядом с Form.bin (…/Ext/form.frm); Form.bin навык собирает сам"
                if form else f"{flag} — путь к файлу вывода")
        raise ValueError(f"{flag} называет {what} ({p}): {tail}")
    return p


def _bin_in(dir_path):
    """`Form.bin` в каталоге (имя без учёта регистра) или `None`."""
    try:
        names = sorted(os.listdir(dir_path))
    except OSError:
        return None
    for name in names:
        if name.lower() == BIN_LOWER and (Path(dir_path) / name).is_file():
            return Path(dir_path) / name
    return None


def bin_in(dir_path):
    return _bin_in(dir_path)


def _ref_in(dir_path):
    dir_path = Path(dir_path)
    frm, container = dir_path / FORM_FILE, _bin_in(dir_path)
    if frm.is_file() or container is not None:
        return FormRef(dir_path, frm, container)
    return None


def locate(path):
    """`FormRef` по пути к `form.frm`, `Form.bin`, каталогу `Ext` или каталогу формы. Нет ни `form.frm`, ни `Form.bin`
    либо неоднозначно — отказ словами."""
    p = Path(path)
    if p.is_dir():
        found = [ref for ref in (_ref_in(p), _ref_in(p / "Ext")) if ref is not None]
        if not found:
            raise ValueError(f"в каталоге {p} нет ни form.frm, ни Form.bin (в подкаталоге Ext тоже): "
                             "назовите форму путём к form.frm, Form.bin или каталогу формы; "
                             "для дерева форм — frm_json.py unpack|pack КАТАЛОГ --all")
        if len(found) > 1:
            raise ValueError(f"в каталоге {p} форма лежит и в нём самом, и в подкаталоге Ext: неоднозначно — "
                             "назовите форму путём к form.frm или Form.bin")
        return found[0]
    if p.name.lower() in (FORM_FILE, BIN_LOWER):
        ref = _ref_in(p.parent)
        if ref is None or (p.name.lower() == BIN_LOWER and ref.bin is None):
            raise ValueError(f"нет такого файла: {p}")
        return ref
    if p.suffix.lower() == ".frm":
        if not p.is_file():
            raise ValueError(f"нет такого файла: {p}")
        return FormRef(p.parent, p, None)
    raise ValueError(f"{p}: это не форма — нужен form.frm, Form.bin или каталог формы")


def under_mirror(dir_path):
    """Среди каталогов от этого вверх есть `.v8mirror.json` — каталог с внешней сборкой."""
    start = Path(dir_path).resolve()
    return any((d / MIRROR_STATE).exists() for d in (start, *start.parents))


# ---------------------------------------------------------------------------------------------------------------------
# Направление расхождения


class Divergence:
    """Расхождение файлов рядом с контейнером. `kind`: `none` (совпадают), `files` (все разошедшиеся файлы новее
    контейнера — правка рукой), `bin` (контейнер новее всех разошедшихся — файлы устарели), `mixed` (и то и другое).
    `files` — `[(имя, время изменения в нс)]`."""

    def __init__(self, kind, files, bin_ns):
        self.kind, self.files, self.bin_ns = kind, files, bin_ns

    def names(self):
        return ", ".join(name for name, _ns in self.files)

    def times(self):
        import datetime
        def fmt(ns):
            return datetime.datetime.fromtimestamp(ns / 1e9).strftime("%Y-%m-%d %H:%M:%S")
        return "; ".join(f"{name} — {fmt(ns)}" for name, ns in self.files) + f"; Form.bin — {fmt(self.bin_ns)}"


def divergence(bin_path):
    """`Divergence` файлов рядом с контейнером. Контейнер нечитаем — `FormBinError`."""
    bin_path = Path(bin_path)
    names = formbin.changed_files(bin_path)
    if not names:
        return Divergence("none", [], 0)
    bin_ns = bin_path.stat().st_mtime_ns
    files = [(n, (bin_path.parent / n).stat().st_mtime_ns) for n in names]
    newer = [n for n, ns in files if ns > bin_ns]
    kind = "files" if len(newer) == len(files) else "bin" if not newer else "mixed"
    return Divergence(kind, files, bin_ns)


def _stale_refusal(dv, ref_dir, what):
    unpack_cmd = f"frm_json.py unpack --force {ref_dir}"
    if dv.kind == "bin":
        return (f"файлы рядом с Form.bin устарели ({dv.names()}): контейнер новее ({dv.times()}). {what} собрала бы контейнер из них "
                f"и откатила его. Выход: `{unpack_cmd}` (файлы перезаписываются из контейнера), затем повторите команду")
    return (f"файлы рядом с Form.bin разошлись с ним по-разному: часть новее контейнера, часть старее ({dv.times()}). "
            f"{what} не знает, чьи правки нужны. Выход: `{unpack_cmd}` оставляет контейнер и перезаписывает файлы; "
            "чтобы сохранить правки файлов, обновите время изменения устаревших файлов и повторите команду")


# ---------------------------------------------------------------------------------------------------------------------
# Чтение


def _from_container(ref):
    sections = formbin.unpack(ref.bin.read_bytes())
    if formbin.SECTION_FORM not in sections:
        raise ValueError(f"в {ref.bin} нет секции form: контейнер без описания формы")
    return sections[formbin.SECTION_FORM]


def read_text(path, notes):
    """Байты текста формы (`form.frm`) для команды чтения. Файл рядом есть и согласован с контейнером (или контейнера нет) —
    читается файл; расходится и новее контейнера — файл, с советом `pack`; расходится и устарел — контейнер, с советом
    `unpack --force`; нет файла — секция `form` контейнера, распакованная в памяти. Возвращает `(байты, FormRef)`; `notes`
    пополняется строками для пользователя."""
    ref = locate(path)
    checked = ref.bin is not None and not ref.plain and not under_mirror(ref.dir)
    if checked:
        try:
            dv = divergence(ref.bin)
        except (formbin.FormBinError, OSError) as err:
            if ref.frm.is_file():
                notes.append(f"Form.bin рядом не читается ({err}): форма прочитана из form.frm")
                return ref.frm.read_bytes(), ref
            raise
        if dv.kind == "files":
            notes.append("Form.bin не совпадает с form.frm/form.bsl/info.txt — соберите "
                         f"`frm_json.py pack {ref.dir}`; команда работает с файлами")
        elif dv.kind in ("bin", "mixed"):
            tail = ("файлы рядом устарели" if dv.kind == "bin" else "часть файлов рядом новее контейнера, часть старее")
            notes.append(f"{tail} ({dv.times()}): форма прочитана из Form.bin; чтобы обновить файлы, "
                         f"выполните `frm_json.py unpack --force {ref.dir}`")
            return _from_container(ref), ref
    if ref.frm.is_file():
        return ref.frm.read_bytes(), ref
    data = _from_container(ref)
    notes.append(f"form.frm рядом нет: форма прочитана из {ref.bin.name} в памяти, на диск ничего не записано")
    return data, ref


def read_tree(path, notes):
    """Дерево формы (`tree.Node`) для команды чтения: `(дерево, FormRef)`."""
    data, ref = read_text(path, notes)
    return parse(data.decode("utf-8")), ref


def read_form_node(path):
    """Дерево формы из файла `*.frm` или `Form.bin` без заметок и проверок расхождения (соседние формы)."""
    from .tree import read_file
    p = Path(path)
    if p.name.lower() == BIN_LOWER:
        sections = formbin.unpack(p.read_bytes())
        if formbin.SECTION_FORM not in sections:
            raise ValueError(f"в {p} нет секции form")
        return parse(sections[formbin.SECTION_FORM].decode("utf-8"))
    return read_file(p)


def form_key(path):
    """Кто в выгрузке хозяин формы: `(вид, объект, имя формы)` по пути `…/<Вид>/<Объект>/Forms/<Имя>/Ext/form.frm`, иначе `None` (копия вне выгрузки)."""
    parts = Path(path).parts
    for i in range(len(parts) - 1, 1, -1):
        if parts[i] == "Forms" and i + 1 < len(parts):
            return parts[i - 2], parts[i - 1], parts[i + 1]
    return None


def same_forms(root, skip):
    """Формы под `root`, которые есть сама форма из `skip`, но лежат под другим путём: тот же вид, объект и имя формы в выгрузке (копия формы вне выгрузки
    лежит под тем же путём от каталога вида) либо, если у формы нет места в выгрузке, единственная форма выгрузки с тем же содержимым (неправленая копия;
    несколько одинаковых форм не различить, и ни одна не исключается). Пути, равные путям `skip`, сюда не входят: их исключает `sibling_paths` и так."""
    skip = [Path(p) for p in skip]
    resolved = {p.resolve() for p in skip}
    keys = {k for k in (form_key(p.resolve()) for p in skip) if k is not None}
    blobs = [p.read_bytes() for p in skip if p.is_file() and form_key(p.resolve()) is None]
    sizes = {len(blob) for blob in blobs}
    out, equal = [], []
    for p in sorted(Path(root).rglob("*.frm")):
        if p.resolve() in resolved:
            continue
        if form_key(p.resolve()) in keys:
            out.append(p)
        elif blobs and p.stat().st_size in sizes and any(p.read_bytes() == blob for blob in blobs):
            equal.append(p)
    return out + (equal if len(equal) == 1 else [])


def sibling_paths(root, skip=()):
    """Формы под каталогом для сравнения с соседями: все `*.frm`, а также `Form.bin`, рядом с которым `form.frm` нет (его
    форма читается из контейнера в памяти). Сама форма не сосед: исключаются пути из `skip`, формы с тем же видом, объектом и именем формы
    (`same_forms`), неправленые копии и `Form.bin` рядом с ними. Возвращает отсортированный список."""
    root = Path(root)
    skip = [Path(p) for p in skip]
    twins = set(same_forms(root, skip))
    gone = {p.resolve() for p in skip} | {p.resolve() for p in twins}
    found = [p for p in root.rglob("*.frm") if p.resolve() not in gone]
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if name.lower() == BIN_LOWER:
                frm = Path(dirpath) / FORM_FILE
                if not frm.exists() and frm.resolve() not in gone:
                    found.append(Path(dirpath) / name)
    return sorted(found)


# ---------------------------------------------------------------------------------------------------------------------
# Правка


def read_bsl(path):
    """Байты модуля для `--bsl`. Файла нет, а рядом лежит `Form.bin` — модуль берётся из контейнера в памяти."""
    p = Path(path)
    if not p.exists() and p.name.lower() == "form.bsl":
        container = _bin_in(p.parent)
        if container is not None:
            sections = formbin.unpack(container.read_bytes())
            if formbin.SECTION_MODULE in sections:
                return sections[formbin.SECTION_MODULE]
    return p.read_bytes()


def source_for_write(path, notes):
    """Исходная форма для команды правки: `(байты form.frm, FormRef)`. Читается в памяти, на диск ничего не пишется.
    Файлы рядом устарели (контейнер новее) или расходятся по-разному — отказ словами."""
    ref = locate(path)
    if ref.bin is not None and not ref.plain and not under_mirror(ref.dir):
        try:
            dv = divergence(ref.bin)
        except (formbin.FormBinError, OSError):
            if not ref.frm.is_file():
                raise
        else:
            if dv.kind in ("bin", "mixed"):
                raise ValueError(_stale_refusal(dv, ref.dir, "Правка"))
    if ref.frm.is_file():
        return ref.frm.read_bytes(), ref
    return _from_container(ref), ref


def exists_before(paths):
    """Какие из путей существуют сейчас: снимок до записи для `finish_write`."""
    return {str(Path(p)) for p in paths if p and Path(p).exists()}


def _parse_check(dir_path, names):
    if FORM_FILE in names:
        frm = Path(dir_path) / FORM_FILE
        try:
            parse(frm.read_bytes().decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as err:
            raise ValueError(f"{frm} не разбирается ({err}): Form.bin не собран, пока форма не читается") from None


def build(container):
    """Сборка контейнера из файлов рядом, если они разошлись с ним: `True` — собран, `False` — не изменился. Отказ словами:
    файлы устарели (контейнер новее) или смешанно, `form.frm` не разбирается, нечитаемый контейнер, нет обязательной секции."""
    container = Path(container)
    dv = divergence(container)
    if dv.kind == "none":
        return False
    if dv.kind in ("bin", "mixed"):
        raise ValueError(_stale_refusal(dv, container.parent, "Сборка"))
    _parse_check(container.parent, [n for n, _ns in dv.files])
    return formbin.repack_if_changed(container)


def finish_write(paths, notes, was=frozenset(), source=None):
    """После записи файлов формы. Для каждого каталога, куда записан `form.frm`, `form.bsl` или `info.txt` и где лежит
    `Form.bin`: если `form.frm` там до записи не было, недостающие файлы раскладываются из контейнера (записанные не
    трогаются); потом контейнер собирается заново — только если содержимое разошлось с секциями. В каталоге с внешней сборкой не
    собирается. `was` — снимок `exists_before`, `source` — `FormRef` исходной формы (если `-o` лежит у другого контейнера, об
    этом строка). Каталога с `Form.bin` нет (форма из одного `form.frm`) — ничего не делается."""
    dirs = []
    for path in paths:
        p = Path(path)
        if p.name.lower() in formbin.SIDECARS and p.parent not in dirs:
            dirs.append(p.parent)
    for dir_path in dirs:
        container = _bin_in(dir_path)
        if container is None:
            continue
        try:
            if str(dir_path / FORM_FILE) not in was:
                laid = [n for n in formbin.unpack_file(container, only_missing=True)]
                if laid:
                    notes.append(f"Form.bin разложен рядом: {', '.join(sorted(laid))}")
            if source is not None and source.dir.resolve() != dir_path.resolve():
                notes.append(f"форма записана в каталог другой формы ({dir_path}): модуль и метаинформация там остаются "
                             "от неё (form.bsl, info.txt или секции её Form.bin)")
            if under_mirror(dir_path):
                notes.append(f"Form.bin не собран: {dir_path} лежит в каталоге с внешней сборкой, его соберёт внешний инструмент при отправке файлов")
                continue
            rebuilt = build(container)
        except OSError as err:
            raise ValueError(f"файлы формы записаны, но Form.bin не собран: {err}") from None
        except formbin.FormBinError as err:
            raise ValueError(f"файлы формы записаны, но Form.bin не собран: {err}") from None
        except ValueError as err:
            raise ValueError(f"файлы формы записаны, но {err}") from None
        notes.append(f"Form.bin собран: {container}" if rebuilt else f"Form.bin не изменился: {container}")


# ---------------------------------------------------------------------------------------------------------------------
# Явные команды


def unpack_command(path, everything, force=False):
    """`unpack`: раскладывает контейнеры; уже разложенные формы (с `form.frm` рядом) не трогает, с `force` перезаписывает
    файлы из контейнера. Возвращает `(строки отчёта, код возврата)`."""
    lines = []
    if not everything:
        ref = locate(path)
        if ref.bin is None or ref.plain:
            raise ValueError(f"рядом с {ref.frm} нет Form.bin: раскладывать нечего")
        if ref.frm.is_file() and not force:
            line = f"Уже разложено: {ref.dir} — form.frm лежит рядом, не тронуто"
            try:
                dv = divergence(ref.bin)
            except (formbin.FormBinError, OSError):
                dv = None
            if dv is not None and dv.kind in ("bin", "mixed"):
                line += (f"; файлы рядом устарели или расходятся ({dv.times()}) — `frm_json.py unpack --force {ref.dir}` "
                         "перезапишет их из контейнера")
            return [line], 0
        written = formbin.unpack_file(ref.bin, only_missing=not force)
        return [f"{'Перезаписано' if force else 'Разложено'}: {ref.bin} → {', '.join(sorted(written))}"], 0
    root = Path(path)
    if not root.is_dir():
        raise ValueError(f"{root}: с --all называют каталог, в котором лежат формы")
    done = already = 0
    failed = []
    for container in formbin.find_bins(root):
        if (container.parent / FORM_FILE).is_file() and not force:
            already += 1
            continue
        try:
            formbin.unpack_file(container, only_missing=not force)
        except (formbin.FormBinError, OSError) as err:
            failed.append((container, str(err)))
        else:
            done += 1
    lines.append(f"{'Перезаписано' if force else 'Разложено'}: {done}; уже разложено: {already}; нечитаемых: {len(failed)}")
    lines += [f"Нечитаемая: {container}: {why}" for container, why in failed]
    return lines, 1 if failed else 0


def _pack_one(container, force):
    """`(исход, строка)`: `built`, `same`, `mirror`, `failed`."""
    if not force and under_mirror(container.parent):
        return "mirror", f"{container}: каталог с внешней сборкой — собирает внешний инструмент"
    try:
        rebuilt = build(container)
    except (formbin.FormBinError, OSError, ValueError) as err:
        return "failed", f"{container}: отказ — {err}"
    return ("built", f"{container}: собран") if rebuilt else ("same", f"{container}: не изменился")


# Модуль новой формы: платформа пишет пустой модуль одной меткой порядка байтов.
EMPTY_MODULE = b"\xef\xbb\xbf"


def create_command(path, force):
    """`pack --create`: новый `Form.bin` у формы, контейнера которой ещё нет (метаданные формы созданы вне конфигуратора). Секции — `form` из
    `form.frm`, `module` из `form.bsl` (нет файла — пустой модуль, и тот же `form.bsl` кладётся рядом), `info` — только из непустого `info.txt`:
    у большинства контейнеров платформы этой секции нет. Упаковщик тот же, что у пересборки. Отказ словами: контейнер уже есть, `form.frm` нет
    или он не разбирается, каталог с внешней сборкой без `force`. Возвращает `(строки отчёта, код возврата)`."""
    ref = locate(path)
    if ref.plain:
        raise ValueError(f"{ref.frm}: контейнер собирают рядом с form.frm (…/Ext/form.frm), а у файла другое имя")
    if ref.bin is not None:
        raise ValueError(f"рядом с {ref.frm} Form.bin уже есть ({ref.bin.name}): --create делает новый контейнер, а этот пересобирает "
                         "frm_json.py pack без ключа")
    if not ref.frm.is_file():
        raise ValueError(f"нет файла {ref.frm}: собирать контейнер не из чего")
    if not force and under_mirror(ref.dir):
        raise ValueError(f"{ref.dir} лежит в каталоге с внешней сборкой ({MIRROR_STATE} выше по дереву): Form.bin собирает внешний инструмент "
                         "при отправке файлов; ключ --force соберёт его вручную")
    _parse_check(ref.dir, [FORM_FILE])
    module_path, info_path = ref.dir / "form.bsl", ref.dir / "info.txt"
    lines = []
    sections = {formbin.SECTION_FORM: ref.frm.read_bytes()}
    if module_path.is_file():
        sections[formbin.SECTION_MODULE] = module_path.read_bytes()
    else:
        sections[formbin.SECTION_MODULE] = EMPTY_MODULE
    info = info_path.read_bytes() if info_path.is_file() else b""
    if info:
        sections[formbin.SECTION_INFO] = info
    packed = formbin.pack(sections)
    target = ref.dir / formbin.BIN_NAME
    tmp = target.with_name(target.name + ".create")
    try:
        tmp.write_bytes(packed)
        os.replace(tmp, target)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
    if not module_path.is_file():
        module_path.write_bytes(EMPTY_MODULE)
        lines.append(f"{module_path}: модуля не было — положен пустой (как у новой формы платформы)")
    parts = ["form", "module"] + (["info"] if info else [])
    lines.append(f"{target}: Form.bin создан ({len(packed)} байт; секции {', '.join(parts)})")
    return lines, 0


def pack_command(path, everything, force):
    """`pack`: собирает `Form.bin` там, где `form.frm`/`form.bsl`/`info.txt` разошлись с секциями. В каталоге с внешней
    сборкой отказывает (собирает внешний инструмент), с `force` собирает. Файлы, устаревшие относительно контейнера, и нечитаемый `form.frm` —
    отказ. Возвращает `(строки отчёта, код возврата)`."""
    if not everything:
        ref = locate(path)
        if ref.bin is None or ref.plain:
            raise ValueError(f"рядом с {ref.frm} нет Form.bin: собирать не во что (новый контейнер создаёт платформа)")
        if not force and under_mirror(ref.dir):
            raise ValueError(f"{ref.dir} лежит в каталоге с внешней сборкой ({MIRROR_STATE} выше по дереву): Form.bin собирает внешний инструмент "
                             "при отправке файлов; ключ --force соберёт его вручную")
        outcome, line = _pack_one(ref.bin, force)
        if outcome == "failed":
            raise ValueError(line.split(": отказ — ", 1)[1])
        return [line], 0
    root = Path(path)
    if not root.is_dir():
        raise ValueError(f"{root}: с --all называют каталог, в котором лежат формы")
    counts = {"built": 0, "same": 0, "mirror": 0, "failed": 0}
    lines = []
    for container in formbin.find_bins(root):
        outcome, line = _pack_one(container, force)
        counts[outcome] += 1
        if outcome in ("built", "failed"):
            lines.append(line)
    summary = (f"Собрано: {counts['built']}; не изменилось: {counts['same']}; отказов: {counts['failed']}"
               + (f"; в каталогах с внешней сборкой (не собирались): {counts['mirror']}" if counts["mirror"] else ""))
    return lines + [summary], 1 if counts["failed"] else 0
