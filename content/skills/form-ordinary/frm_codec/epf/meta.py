"""Внутренние метаданные внешней обработки или отчёта: объекты (реквизиты, табличные части, их реквизиты, формы), пары
идентификаторов типа и основная форма.

Метаданные лежат в элементе, на который указывает элемент `root`. У каждого объекта есть блок имени
`[3, [1, 0, {guid}], "Имя", …]`; перед ним в свойствах стоят пары GUID (TypeId, ValueId) типов, которые объект порождает.
"""
import re

from ..json0 import decode0
from ..tree import parse
from .container import EpfError

GUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

CLASS_FORM = "d5b0e5ed-256d-401c-9c36-f630cafd8a62"
CLASS_ROOT = "c3831ec8-d8d5-4f93-8a22-f9bfae07327f"          # корень внешней обработки
CLASS_ROOT_REPORT = "e41aff26-25cf-4bb6-b6c1-3f478a75f374"   # корень внешнего отчёта
CLASS_FORM_REPORT = "a3b368c0-29e2-11d6-a3c7-0050bae0a776"   # формы внешнего отчёта
FORM_CLASSES = (CLASS_FORM, CLASS_FORM_REPORT)
ROOT_CLASSES = (CLASS_ROOT, CLASS_ROOT_REPORT)
KNOWN_BINARY_CLASSES = FORM_CLASSES + ROOT_CLASSES          # двоичный `.0` у корня — не форма
ZERO_GUID = "00000000-0000-0000-0000-000000000000"
BIN_HEAD = b"\xff\xff\xff\x7f"
WAY_OUT = "Сборка Конфигуратором (1cv8 DESIGNER /LoadExternalDataProcessorOrReportFromFiles) пишет copyinfo сама."

CLASS_NAMES = {
    "ec6bb5e5-b7a8-4d75-bec9-658107a699cf": "реквизит",
    "2bcef0d1-0981-11d6-b9b8-0050bae0a95d": "табличная часть",
    "5d24a9d1-098e-11d6-b9b8-0050bae0a95d": "реквизит",
    "7e7123e0-29e2-11d6-a3c7-0050bae0a776": "реквизит",      # внешний отчёт
    "b077d780-29e2-11d6-a3c7-0050bae0a776": "табличная часть",
    "c339c860-29e2-11d6-a3c7-0050bae0a776": "реквизит",
    CLASS_FORM_REPORT: "форма",
    CLASS_FORM: "форма",
}


def _is_guid(x):
    return isinstance(x, dict) and "guid" in x


def _name_block(x):
    if (isinstance(x, list) and len(x) >= 3 and x[0] == 3 and isinstance(x[1], list) and len(x[1]) == 3
            and x[1][:2] == [1, 0] and _is_guid(x[1][2]) and isinstance(x[2], str)):
        return x[1][2]["guid"], x[2]
    return None


def _find_name(x, depth=0):
    if depth > 4:
        return None
    found = _name_block(x)
    if found:
        return found
    if isinstance(x, list):
        for c in x:
            found = _find_name(c, depth + 1)
            if found:
                return found
    return None


def _types_before(props, depth=0):
    """TypeId пар (TypeId, ValueId), стоящих перед блоком имени, — в порядке следования пар."""
    if not isinstance(props, list) or depth > 4:
        return []
    for i, c in enumerate(props):
        if _find_name(c):
            guids = [x["guid"] for x in props[:i] if _is_guid(x)]
            if guids:
                return [guids[k] for k in range(0, len(guids) - 1, 2)]
            return _types_before(c, depth + 1)
    return []


class Meta:
    """`objs`: GUID → цепочка `[(класс, имя), …]` от верхнего; `types`: TypeId → (GUID владельца, индекс пары);
    `root` — GUID самой обработки; `default_form` — GUID основной формы или `None`; `form_slots` — GUID заполненных слотов
    после имени корня (первый — основная форма, дальше у обработки дополнительная форма, у отчёта — схема, формы настроек и т. п.)."""

    def __init__(self, text):
        self.objs = {}
        self.types = {}
        self.default_form = None
        tree = decode0(parse(text))
        top = tree[3]
        cls, props = top[0]["guid"], top[1]
        (self.root, name) = _find_name(props)
        self.objs[self.root] = [(cls, name)]
        for i, ty in enumerate(_types_before(props)):
            self.types[ty] = (self.root, i)
        after = False
        slots = []
        for c in props[1]:
            if isinstance(c, list) and _find_name(c):
                after = True
                continue
            if after and _is_guid(c) and c["guid"] != ZERO_GUID:
                slots.append(c["guid"])
        self.form_slots = slots          # заполненные слоты после имени: основная форма, затем дополнительные
        self.default_form = slots[0] if slots else None
        self._walk(props[3:], [])

    def _walk(self, items, chain):
        for ch in items:
            if not (isinstance(ch, list) and len(ch) >= 2 and _is_guid(ch[0]) and isinstance(ch[1], int)):
                continue
            cls = ch[0]["guid"]
            for it in ch[2:]:
                if _is_guid(it):  # формы и макеты: только GUID, имя — из собственного элемента контейнера
                    self.objs[it["guid"]] = chain + [(cls, None)]
                    continue
                props = it[0] if isinstance(it, list) and it and isinstance(it[0], list) else it
                found = _find_name(props)
                if not found:
                    continue
                uid, name = found
                self.objs[uid] = chain + [(cls, name)]
                for i, ty in enumerate(_types_before(props)):
                    self.types[ty] = (uid, i)
                if isinstance(it, list) and len(it) > 2:
                    self._walk(it[2:], chain + [(cls, name)])

    def label(self, guid):
        """Название объекта словами: «реквизит Флаг», «реквизит Число табличной части ТЧ»."""
        chain = self.objs.get(guid)
        if not chain:
            return f"объект {guid}"
        cls, name = chain[-1]
        if guid == self.root:
            return f"корневой объект {name}"
        what = CLASS_NAMES.get(cls, "объект")
        text = f"{what} {name}" if name else f"{what} {guid}"
        if len(chain) > 1 and chain[-2][1]:
            text += f" табличной части {chain[-2][1]}"
        return text


class Processing:
    """Разобранная обработка: контейнер, метаданные и обычные формы `{GUID формы: текст form.frm}`."""

    def __init__(self, container, meta, forms, form_names, form_modules=None):
        self.container = container
        self.meta = meta
        self.forms = forms
        self.form_names = form_names
        self.form_modules = form_modules if form_modules is not None else {}   # GUID формы → текст модуля формы (секция `module` Form.bin)


def load(container):
    """Разбирает метаданные и обычные формы контейнера. Отказ — `EpfError` словами."""
    from .. import formbin

    root = container.get("root")
    if root is None:
        raise EpfError("в контейнере нет элемента root: это не внешняя обработка и не отчёт")
    found = GUID_RE.search(root.data.decode("utf-8-sig", "replace"))
    meta_item = container.get(found.group(0)) if found else None
    if meta_item is None:
        raise EpfError("в контейнере нет элемента внутренних метаданных, на который указывает root")
    try:
        meta = Meta(meta_item.data.decode("utf-8-sig"))
    except Exception:  # разбор чужой структуры: любой сбой — отказ словами, не трассировка
        raise EpfError("внутренние метаданные не разобраны: строение не проверялось. " + WAY_OUT) from None
    root_class = meta.objs[meta.root][0][0]
    if root_class not in ROOT_CLASSES:
        raise EpfError(f"корень метаданных класса {root_class}: состав copyinfo такого объекта не проверялся. " + WAY_OUT)
    for guid, chain in list(meta.objs.items()):
        item = container.get(guid)
        if chain[-1][1] is None and item is not None:
            quoted = re.search(r'"([^"]*)"', item.data.decode("utf-8-sig", "replace"))
            meta.objs[guid] = chain[:-1] + [(chain[-1][0], quoted.group(1) if quoted else None)]
    forms, names, modules = {}, {}, {}
    for item in container.items:
        name = item.name
        if not name.endswith(".0"):
            continue
        guid = name[:-2]
        chain = meta.objs.get(guid)
        cls = chain[-1][0] if chain else None
        data = item.data
        shown = (chain[-1][1] if chain else None) or guid
        binary = data[:4] == BIN_HEAD
        if cls in FORM_CLASSES:
            if not binary:
                if data[:3] == b"\xef\xbb\xbf" or data[:1] == b"{":
                    continue  # текст управляемой формы: обычной формы здесь нет
                raise EpfError(f"форма {shown} ({name}) не похожа ни на Form.bin, ни на текст управляемой формы: "
                               "не проверялось. " + WAY_OUT)
            try:
                sections = formbin.unpack(data)
            except ValueError as exc:
                raise EpfError(f"форма {shown} ({name}) не прочитана: {exc}") from None
            if "form" not in sections:
                raise EpfError(f"форма {shown} ({name}): в Form.bin нет секции form. " + WAY_OUT)
            text = sections["form"]
            forms[guid] = text.decode("utf-8-sig") if isinstance(text, bytes) else text
            names[guid] = shown
            body = sections.get("module")
            modules[guid] = (body.decode("utf-8-sig", "replace") if isinstance(body, bytes) else body) if body is not None else ""
        elif binary and cls not in KNOWN_BINARY_CLASSES:
            raise EpfError(f"элемент {shown} ({name}) двоичного вида {"класса " + cls if cls else "вне внутренних метаданных"}: форма незнакомого класса, "
                           "не проверялось. " + WAY_OUT)
    return Processing(container, meta, forms, names, modules)
