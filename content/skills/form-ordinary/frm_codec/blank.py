"""Форма с нуля: пустая заготовка формы, как её создаёт конструктор платформы (команда `new`, `generate` без `--form`).

Заготовка — форма конструктора платформы 8.3.27 без содержимого: остаются панели формы и основной реквизит. Шесть видов:

| вид | что остаётся |
|---|---|
| `processing` | панель `ДействияФормы`, панель `ОсновныеДействияФормы` с кнопкой «Закрыть», основной реквизит `ОбработкаОбъект`; его тип называют `--root-xml`, `--type-id` или `--object` с `--config` — без них отказ |
| `processing --dialog` | то же, без основного реквизита и без реквизитов формы (форма-диалог; модуль формы не видит реквизитов и методов модуля обработки) |
| `report` | то же, что у `processing`, но по форме внешнего отчёта конструктора: нижняя панель с «Закрыть» («Сформировать» с процедурой формы и разделитель убраны), основной реквизит `ОтчетОбъект`, тип значения формы отчёта; тип основного реквизита называют `--root-xml` (внешний отчёт), `--type-id` или `--object Отчет.Имя` с `--config` — без них отказ; `--dialog` — отказ |
| `catalog.item`, `document.item` | обе панели формы с кнопками «ОК», «Записать», «Закрыть», основной реквизит `СправочникОбъект` / `ДокументОбъект` |
| `catalog.list`, `document.list` | табличное поле со стандартными колонками, панель `ДействияФормы`, основной реквизит-список; тип поля — тип основного реквизита |

Кнопок с обработчиками в заготовке нет: кнопки панелей — стандартные действия платформы. Готовые документы лежат в `frm_codec/data/blanks/*.json`.
Здесь — то, что выполняется при вызове: тип основного реквизита по выгрузке, заголовок, размер и свежие GUID панелей.

Новых форм в метаданных заготовка не заводит: форму объекту создают в конфигураторе (или берут существующую); навык пишет её содержимое.
"""
import copy
import dataclasses
import pathlib
import re
import uuid

from . import edit, json0, metadata, tabletype, typed
from .datapaths import BLANKS_DIR
from .edit import base as ed_base
from .edit.names import ACTIONS_GUID, BTN_OWNER
from .tree import render

KINDS = ("processing", "report", "catalog.item", "document.item", "catalog.list", "document.list")
EXTERNAL_KINDS = ("processing", "report")      # формы без объекта-ссылки: основной реквизит — Object обработки либо отчёта
LIST_KINDS = ("catalog.list", "document.list")
DEFAULT_SIZE = (400, 300)
MIN_WIDTH = 100
BAR_H = 25                         # высота панелей формы в заготовке: 25 (верхняя от верха формы, нижняя до низа)
TOP_BAR, BOTTOM_BAR = "ДействияФормы", "ОсновныеДействияФормы"
LIST_PAD_X, LIST_TOP, LIST_PAD_BOTTOM = 8, 33, 8      # таблица списка конструктора: от (8, 33) до (ширина − 8, высота − 8)
MODULE_BYTES = b"\xef\xbb\xbf"   # модуль формы, созданной конструктором, пуст: одна метка порядка байтов (как у выгрузки платформы)
OBJECT_WORDS = {"catalog.item": "Справочник", "catalog.list": "Справочник", "document.item": "Документ", "document.list": "Документ",
                "processing": "Обработка", "report": "Отчет"}
# Заголовок, который конструктор даёт форме по синониму объекта: «Товары», «Справочник Товары», «Документы Заказ», «Обработка  Загрузка»
# (у обработки два пробела, как записывает платформа).
TITLE_FORMS = {"catalog.item": "{s}", "document.item": "{s}", "catalog.list": "Справочник {s}", "document.list": "Документы {s}",
               "processing": "Обработка  {s}", "report": "Отчет  {s}"}
NO_OBJECT_TITLE = "Форма"
MAIN_TYPE = {"processing": "Object", "report": "Object", "catalog.item": "Object", "document.item": "Object", "catalog.list": "List", "document.list": "List"}


class BlankError(ValueError):
    """Отказ словами: заготовку по этим параметрам не собрать."""


@dataclasses.dataclass
class Blank:
    doc: dict
    module: bytes
    notes: list
    source: str          # слова: из какой заготовки собрано

    def frm_bytes(self):
        """Текст `form.frm` (кодек проверяет собственную сборку разбором)."""
        return render(typed.encode(self.doc)).encode("utf-8")


def file_name(kind, external=False):
    if kind not in KINDS:
        raise BlankError(f"вид формы {kind!r} не из перечня: {', '.join(KINDS)}")
    return kind + ("-external" if external else "")


def load(name):
    path = pathlib.Path(BLANKS_DIR) / f"{name}.json"
    if not path.exists():
        raise BlankError(f"заготовки {name!r} нет: {path.name} не найден в данных навыка")
    return json0.loads(path.read_text(encoding="utf-8"))


def _main_row(doc):
    attributes = doc["attributes"]
    main = attributes["u0"]["main_attribute_id"]
    return next((r for r in attributes["list"]["items"] if r["u0"] == [main]), None)


def retarget(doc, guid):
    """Тип основного реквизита заготовки — `guid` (тип `Object` или `List` объекта выгрузки). Табличное поле, привязанное к основному реквизиту
    (таблица формы списка), получает тот же тип: конструктор пишет полю тип его реквизита, а поле с типом формы, из которой снята заготовка,
    платформа показывает без колонок (`frm_codec/tabletype.py`)."""
    row = _main_row(doc)
    if row is None:
        raise BlankError("у заготовки нет основного реквизита: тип ставить некуда")
    row["pattern"]["types"][0]["value_type"]["guid"] = guid
    for _name, table in tabletype.bound_to(doc, doc["attributes"]["u0"]["main_attribute_id"]):
        tabletype.set_type(table, guid)


def _walk_strings(value, fn):
    """Заменяет строки-GUID по всему документу; fn(строка) → новая строка."""
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str):
                value[key] = fn(item)
            else:
                _walk_strings(item, fn)
    elif isinstance(value, list):
        for at, item in enumerate(value):
            if isinstance(item, str):
                value[at] = fn(item)
            else:
                _walk_strings(item, fn)


def reissue_guids(doc):
    """Головы блоков действий панелей и GUID их кнопок выдаются заново: платформа ведёт их у каждой формы свои, один GUID кнопки не встречается
    в двух блоках действий. Замена идёт по всему документу сразу (владельцы кнопок, наборы), поэтому ссылки не расходятся. `uuid.uuid4` —
    тот, что подменяет `generate` для повторяемости сборки."""
    mapping = {}
    for _name, block in ed_base._bars(doc):
        head = (block.get(ACTIONS_GUID) or {}).get("guid")
        if head:
            mapping[head] = str(uuid.uuid4())
        for _set, button in edit._buttons(block):
            ident = (button.get(edit.BUTTON_ID) or {}).get("guid")
            if ident:
                mapping[ident] = str(uuid.uuid4())

    def swap(text):
        return mapping.get(text, text)

    def swap_guid(value):
        if isinstance(value, dict):
            if set(value) == {"guid"} and value["guid"] in mapping:
                value["guid"] = mapping[value["guid"]]
            else:
                for item in value.values():
                    swap_guid(item)
        elif isinstance(value, list):
            for item in value:
                swap_guid(item)
    swap_guid(doc)
    return len(mapping)


def _placed(kind):
    """Имена элементов, которые заготовка ставит к краям формы: панели формы и (у списка) таблица."""
    table = {"catalog.list": "СправочникСписок", "document.list": "ДокументСписок"}.get(kind)
    return (TOP_BAR, table) if table else (TOP_BAR, BOTTOM_BAR)


def resize(doc, kind, width, height):
    """Форма нового размера: документ с размером, направляющими края и панелями (у списка — таблицей) у краёв. Привязки панелей остаются
    записью конструктора: `set_property` переписывает смещения привязок к краю так, чтобы край остался на месте, а заготовке край нужен у
    нового края формы, поэтому правила возвращаются прежние и меняются только координаты (нижняя панель привязана к низу формы, верхняя и
    таблица списка — к правому краю). `move_element` не годится: он пишет привязки заново, а заготовка должна остаться записью конструктора."""
    def coords(document, name):
        return ed_base.find_element(document, name).element[edit.COORDS]
    kept = {name: {key: copy.deepcopy(coords(doc, name)[key]) for key in edit.ANCHORS if key in coords(doc, name)} for name in _placed(kind)}
    doc, _bsl, _log = edit.apply(doc, [{"op": "set_property", "form": True, "name": "width", "value": width},
                                       {"op": "set_property", "form": True, "name": "height", "value": height}])
    for name, anchors in kept.items():
        coords(doc, name).update(copy.deepcopy(anchors))
    coords(doc, TOP_BAR)["right"] = width
    if kind in LIST_KINDS:
        table = coords(doc, _placed(kind)[1])
        table["right"], table["bottom"] = width - LIST_PAD_X, height - LIST_PAD_BOTTOM
    else:
        bar = coords(doc, BOTTOM_BAR)
        bar["y"], bar["right"], bar["bottom"] = height - BAR_H, width, height
    return doc


def min_size(kind):
    if kind in LIST_KINDS:
        from . import generate_list
        return generate_list.LIST_MIN_W, generate_list.LIST_MIN_H
    return MIN_WIDTH, 2 * BAR_H + 10


def check_size(kind, size):
    width, height = size
    low_w, low_h = min_size(kind)
    if width < low_w or height < low_h:
        raise BlankError(f"размер {width}×{height} мал: форме вида «{kind}» нужно не меньше {low_w}×{low_h} "
                         "(панели формы и отступы)")


def parse_size(text):
    """`400x300` / `400×300` → `(400, 300)`."""
    parts = str(text).lower().replace("×", "x").replace("х", "x").split("x")
    if len(parts) != 2 or not all(p.strip().isdigit() and int(p) > 0 for p in parts):
        raise BlankError(f"размер — ШxВ целыми пикселями (например 400x300), а пришло {text!r}")
    return int(parts[0]), int(parts[1])


def _object_for(kind, object_name, config):
    """Объект выгрузки заготовки: `(MdObject или None, слова о том, почему его нет)`."""
    word = OBJECT_WORDS[kind]
    if config is None:
        return None, "выгрузка конфигурации не дана"
    if object_name is None:
        return None, "объект не назван"
    full = object_name.strip()
    try:
        obj = config.object(full)
    except metadata.MetadataError as e:
        if kind in EXTERNAL_KINDS:
            return None, str(e)
        raise BlankError(f"object: {e}") from None
    if kind == "report":      # «Отчет.», «Отчёт.», «Report.» и полные внешние имена называют отчёт одинаково: решает вид объекта, а не написание
        if obj.kind != "report" or obj.external:
            raise BlankError(f"object: {full!r} — {'внешний отчёт из корневого XML' if obj.external else 'не отчёт'}: форма вида «report» заводится "
                             "на отчёт выгрузки конфигурации «Отчет.Имя» (внешний отчёт даёт --root-xml)")
        return obj, ""
    if not full.startswith(word + "."):
        raise BlankError(f"object: {full!r} — не {word.lower()}: форма вида «{kind}» заводится на объект «{word}.Имя»")
    return obj, ""


NO_TYPE_PROCESSING = (
    "у формы внешней обработки основной реквизит — `ОбработкаОбъект` с типом Object этой обработки; без него модуль формы не видит "
    "реквизитов и экспортных методов модуля обработки, и при открытии формы вызовы их не компилируются. Назовите источник типа: "
    "`--root-xml <Имя>.xml` (корневой XML выгрузки внешней обработки; тип берётся из xr:GeneratedType category=\"Object\"), "
    "`--type-id <GUID>` (TypeId этого GeneratedType: он лежит в `<Имя>.xml` выгрузки обработки, в блоке InternalInfo) или "
    "`--object Обработка.Имя --config <каталог выгрузки>` (обработка из выгрузки конфигурации). Нужна форма-диалог без основного реквизита "
    "(дополнительная форма, которой модуль обработки не нужен) — `--dialog`")
NO_TYPE_REPORT = (
    "у формы отчёта основной реквизит — `ОтчетОбъект` с типом Object этого отчёта; без него модуль формы не видит реквизитов и "
    "экспортных методов модуля отчёта, и при открытии формы вызовы их не компилируются. Назовите источник типа: `--root-xml <Имя>.xml` "
    "(корневой XML выгрузки внешнего отчёта; тип берётся из xr:GeneratedType category=\"Object\"), `--type-id <GUID>` (TypeId этого "
    "GeneratedType: он лежит в `<Имя>.xml` выгрузки отчёта, в блоке InternalInfo) или `--object Отчет.Имя --config <каталог выгрузки>` "
    "(отчёт из выгрузки конфигурации). Формы-диалога отчёта у вида report нет: `--dialog` не берётся")
NO_TYPE_REPORT_GENERATE = (
    "у формы отчёта основной реквизит — `ОтчетОбъект` с типом Object этого отчёта; без него модуль формы не видит реквизитов и "
    "экспортных методов модуля отчёта, и при открытии формы вызовы их не компилируются. Назовите источник типа: `--root-xml <Имя>.xml` "
    "(корневой XML выгрузки внешнего отчёта; тип берётся из xr:GeneratedType category=\"Object\"), `--type-id <GUID>` (TypeId этого "
    "GeneratedType: он лежит в `<Имя>.xml` выгрузки отчёта, в блоке InternalInfo) или `--config`, где есть отчёт из `object` описания. "
    "Формы-диалога отчёта нет: `--dialog` не берётся")
DIALOG_REPORT_REFUSAL = ("--dialog у формы отчёта не берётся: формы-диалога отчёта (без основного реквизита) навык не собирает — в выгрузках конфигураций "
                         "такая форма единична, и тип значения формы у неё нулевой, а не тип формы отчёта; заготовка по ней не собрана и "
                         "в предприятии не проверялась. Форма отчёта несёт основной реквизит `ОтчетОбъект`")
DIALOG_NOTE = ("форма-диалог: основного реквизита и реквизитов формы нет; модуль формы не видит реквизитов и экспортных методов модуля "
               "обработки (вызов экспортной процедуры обработки по голому имени при открытии формы не компилируется)")


NO_TYPE_GENERATE = (
    "у формы внешней обработки основной реквизит — `ОбработкаОбъект` с типом Object этой обработки; без него модуль формы не видит "
    "реквизитов и экспортных методов модуля обработки, и при открытии формы вызовы их не компилируются. Назовите источник типа: "
    "`--root-xml <Имя>.xml` (корневой XML выгрузки внешней обработки; тип берётся из xr:GeneratedType category=\"Object\"), "
    "`--type-id <GUID>` (TypeId этого GeneratedType: он лежит в `<Имя>.xml` выгрузки обработки, в блоке InternalInfo) или `--config`, "
    "где есть обработка из `object` описания. Нужна форма-диалог без основного реквизита (дополнительная форма, которой модуль "
    "обработки не нужен) — `--dialog`")


def build(kind, object_name=None, config=None, title=None, size=None, type_id=None, root_xml=None, dialog=False, for_generate=False):
    """Заготовка формы вида `kind`; `Blank` либо `BlankError` словами.

    * `catalog.*`, `document.*` — нужны `object_name` («Справочник.Имя») и `config` (выгрузка, `metadata.Config`): тип основного реквизита берётся
      оттуда (`Object` у элемента, `List` у списка). Без них отказ — основной реквизит формы объекта без типа объекта не бывает.
    * `processing` — тип основного реквизита один из четырёх источников: `config` с обработкой `object_name` (её `Object`), `type_id` (GUID
      типа, заданный явно: Object обработки, элемента или List списка; у форм справочника и документа — вместо выгрузки), `root_xml` (корневой
      XML выгрузки внешней обработки: `Object` и синоним для заголовка) либо `dialog=True` — заготовка без основного реквизита и без
      реквизитов формы (форма-диалог). Ни одного источника — отказ: форма внешней обработки без основного реквизита не видит модуля обработки.
    * `report` — то же, что `processing`, но по форме внешнего отчёта конструктора (основной реквизит `ОтчетОбъект`, нижняя панель с «Закрыть»): источник типа —
      `config` с отчётом `object_name` («Отчет.Имя»), `type_id` либо `root_xml` (корневой XML внешнего отчёта); `dialog` — отказ.
    * `title` — заголовок формы; без него — по синониму объекта, как у конструктора, а без объекта «Форма».
    * `size` — `(ширина, высота)`; без него 400×300.
    """
    if kind not in KINDS:
        raise BlankError(f"вид формы {kind!r} не из перечня: {', '.join(KINDS)}")
    notes = []
    if type_id is not None and not re.fullmatch(r"[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", type_id):
        raise BlankError(f"type_id — GUID типа основного реквизита (вида 12345678-1234-1234-1234-123456789abc), а пришло {type_id!r}")
    sources = [word for word, given in (("--type-id", type_id is not None), ("--root-xml", root_xml is not None),
                                         ("--object/--config", config is not None)) if given]
    if kind == "report" and dialog:
        raise BlankError(DIALOG_REPORT_REFUSAL)
    if (root_xml is not None or dialog) and kind not in EXTERNAL_KINDS:
        raise BlankError(f"{'--root-xml' if root_xml is not None else '--dialog'} — ключ формы внешней обработки или отчёта (виды «processing», "
                         f"«report»), а вид «{kind}» заводится на объект выгрузки (--object и --config) либо на --type-id")
    if dialog and sources:
        raise BlankError(f"--dialog (форма без основного реквизита) вместе с {', '.join(sources)} не берётся: тип основного реквизита либо задан, "
                         "либо формы-диалога нет")
    if root_xml is not None and len(sources) > 1:
        raise BlankError(f"тип основного реквизита один: --root-xml вместе с {', '.join(w for w in sources if w != '--root-xml')} не берётся")
    root = None
    if root_xml is not None:
        try:
            root = metadata.external_root(root_xml)
        except metadata.MetadataError as e:
            raise BlankError(str(e)) from None
        if root.kind != kind:
            raise BlankError(f"корневой XML {root_xml}: объект {'ExternalReport' if root.kind == 'report' else 'ExternalDataProcessor'}, а вид «{kind}» "
                             f"заводится на {'внешнюю обработку (ExternalDataProcessor)' if kind == 'processing' else 'внешний отчёт (ExternalReport)'}"
                             + ("; в описании generate корню ExternalReport отвечает объект «ВнешнийОтчет.Имя» или «Отчет.Имя», корню ExternalDataProcessor — "
                                "«ВнешняяОбработка.Имя» или «Обработка.Имя» (вид описания processing)" if for_generate else
                                f"; форма {'внешнего отчёта — вид «report»' if root.kind == 'report' else 'внешней обработки — вид «processing»'}"))
        type_id = root.object_type_id
    obj, why = _object_for(kind, object_name, config)
    if kind in EXTERNAL_KINDS and obj is None and type_id is None and not dialog:
        tail = ""
        if config is not None and object_name:
            said = config.failed_reason(object_name)
            what = "отчёта" if kind == "report" else "обработки"
            tail = (f" (файл {what} «{object_name}» в выгрузке не прочитан: {said})" if said
                    else f" (в выгрузке нет {'отчёта' if kind == 'report' else 'обработки'} «{object_name}»)")
        if kind == "report":
            raise BlankError((NO_TYPE_REPORT_GENERATE if for_generate else NO_TYPE_REPORT) + tail)
        raise BlankError((NO_TYPE_GENERATE if for_generate else NO_TYPE_PROCESSING) + tail)
    if kind not in EXTERNAL_KINDS and obj is None and type_id is None:
        raise BlankError(f"форма вида «{kind}» заводится на объект выгрузки: нужны --object («{OBJECT_WORDS[kind]}.Имя») и --config (каталог "
                         f"выгрузки конфигурации) — {why}. Основной реквизит формы объекта несёт тип этого объекта; без объекта заготовки нет. "
                         "Выгрузки нет, а GUID типа известен (Object у элемента, List у списка) — назовите его в --type-id: заготовка та же, "
                         "с панелями вида и основным реквизитом этого типа, без реквизитов объекта")
    if obj is not None and type_id is not None:
        raise BlankError("type_id и объект выгрузки вместе не берутся: тип основного реквизита один — либо из выгрузки, либо заданный явно")
    external = kind == "processing" and obj is None and type_id is None   # здесь только `dialog`: без источника типа выше отказ
    doc = load(file_name(kind, external))
    where = f"форма конструктора вида «{kind}»"
    if obj is not None:
        try:
            guid = obj.type_id(MAIN_TYPE[kind])
        except metadata.MetadataError as e:
            raise BlankError(f"object: {e}") from None
        retarget(doc, guid)
        notes.append(f"основной реквизит формы — тип «{MAIN_TYPE[kind]}» объекта «{obj.full_name}» ({guid})")
    elif root is not None:
        retarget(doc, type_id)
        notes.append(f"основной реквизит формы — тип «Object» внешн{'его отчёта' if kind == 'report' else 'ей обработки'} «{root.name}» ({type_id}), из корневого XML")
    elif type_id is not None:
        retarget(doc, type_id)
        notes.append(f"основной реквизит формы — тип {type_id}, заданный явно")
    else:
        notes.append(f"{DIALOG_NOTE}; реквизиты формы заводит операция add_attribute либо ключ attributes описания generate")
        where += ", без основного реквизита"
    if title is None:
        synonym = getattr(obj, "synonym", "") if obj is not None else (root.synonym if root is not None else "")
        title = TITLE_FORMS[kind].format(s=synonym) if synonym else NO_OBJECT_TITLE
    width, height = size or DEFAULT_SIZE
    check_size(kind, (width, height))
    try:
        doc, _bsl, _log = edit.apply(doc, [{"op": "set_form_title", "text": title}])
        if (width, height) != tuple(doc_size(doc)):
            doc = resize(doc, kind, width, height)
    except ed_base.EditError as e:
        raise BlankError(f"заготовка не собралась: {e}") from None
    reissue_guids(doc)
    notes.append(f"размер {width}×{height}, заголовок «{title}»; модуль формы пуст")
    return Blank(doc, MODULE_BYTES, notes, where)


def doc_size(doc):
    return doc["form"]["width"], doc["form"]["height"]
