"""Перепись набора форм для норм компоновки: одна запись на форму.

Вид формы определяется по имени основного реквизита, потому что платформа назначает его по виду формы. Если реквизит
переименован, вид определяется по классу пути и имени формы. Регламентированные отчёты выделены в отдельный вид
`regulated` и в нормы не входят, потому что их формы создаёт сама 1С.
"""
import hashlib
import os
from pathlib import PurePosixPath

from frm_codec import layout, textgap, textwidth

CLASSES = {
    "Catalogs", "Documents", "DataProcessors", "Reports", "ChartsOfCharacteristicTypes", "ChartsOfAccounts",
    "ChartsOfCalculationTypes", "InformationRegisters", "AccumulationRegisters", "AccountingRegisters",
    "CalculationRegisters", "BusinessProcesses", "Tasks", "ExchangePlans", "DocumentJournals", "Enums",
    "CommonForms", "Constants", "FilterCriteria", "SettingsStorages",
}
KNOWN = {"СправочникОбъект": "catalog.item", "СправочникСписок": "catalog.list",
         "ДокументОбъект": "document.item", "ДокументСписок": "document.list",
         "ОбработкаОбъект": "processing", "ОтчетОбъект": "report",
         # остальные имена, найденные при переписи (`design_census_report.KNOWN`): основной реквизит с известным видом важнее пути
         "РегистрСведенийМенеджерЗаписи": "other:InformationRegisters",
         "РегистрСведенийСписок": "other:InformationRegisters",
         "РегистрНакопленияСписок": "other:AccumulationRegisters",
         "ПланВидовХарактеристикОбъект": "other:ChartsOfCharacteristicTypes",
         "ПланВидовХарактеристикСписок": "other:ChartsOfCharacteristicTypes",
         "ПланСчетовОбъект": "other:ChartsOfAccounts", "ПланСчетовСписок": "other:ChartsOfAccounts",
         "ПланОбменаОбъект": "other:ExchangePlans", "ПланОбменаСписок": "other:ExchangePlans",
         "ЖурналДокументовСписок": "other:DocumentJournals", "ПеречислениеСписок": "other:Enums",
         "БизнесПроцессОбъект": "other:BusinessProcesses", "ЗадачаОбъект": "other:Tasks",
         "ПланВидовРасчетаОбъект": "other:ChartsOfCalculationTypes",
         "РегистрБухгалтерииСписок": "other:AccountingRegisters"}
BY_CLASS = {"DataProcessors": "processing", "External": "processing", "Reports": "report"}
LIST_FORMS = ("ФормаСписка", "ФормаВыбора", "ФормаВыбораГруппы", "ФормаСпискаГрупп")
# Регламентированная отчётность: объект, в имени которого есть корень `Регламентированн` (с любым окончанием и в любом месте)
# или которое начинается с `РеглОтч`, а также объект типовой библиотеки электронной отчётности. Формы таких объектов создаёт
# сама 1С, и в нормы они не входят. Имена `РегламентнаяОперация` и `РегламентныеДокументы` этого корня не содержат и в
# регламентированную отчётность не входят.
REGULATED_ROOT = "Регламентированн"
REGULATED_PREFIX = "РеглОтч"
REGULATED_OBJECTS = ("ДокументооборотСКонтролирующимиОрганами",)
# Наборы-выгрузки, у которых конфигурацию определяет не `bases/<база>` и не `epf/<обработка>`, задаются переменной окружения
# `FRM_DUMP_SETS` — `имя:сегментов,имя:сегментов`: имя каталога набора и число сегментов пути от него (включительно), которые
# образуют конфигурацию. 1 — весь набор одна конфигурация, 2 — конфигурация лежит в подкаталоге набора. Без переменной наборов
# нет: конфигурацией считается путь до каталога класса объекта.
DUMP_SETS_ENV = "FRM_DUMP_SETS"
PAIR_DY = 3  # надпись и поле находятся в одной строке, если их верхние края отличаются не больше чем на 3 px


def dump_sets():
    """Наборы-выгрузки из `FRM_DUMP_SETS`: `{имя: число сегментов}`. Запись без числа или с нечисловым — отказ."""
    out = {}
    for item in filter(None, (part.strip() for part in os.environ.get(DUMP_SETS_ENV, "").split(","))):
        name, _, count = item.partition(":")
        if not name or not count.isdigit() or int(count) < 1:
            raise ValueError(f"{DUMP_SETS_ENV}: запись «{item}» не вида имя:сегментов (число не меньше 1)")
        out[name] = int(count)
    return out


def is_regulated(obj):
    return REGULATED_ROOT in obj or obj.startswith(REGULATED_PREFIX) or obj in REGULATED_OBJECTS


def where(rel):
    parts = PurePosixPath(str(rel).replace("\\", "/")).parts      # путь Windows приходит с обратной косой
    if len(parts) >= 4 and parts[-1] == "form.frm" and parts[-2] == "Ext" and parts[-4] == "CommonForms":
        return ("CommonForms", parts[-3], parts[-3])      # общая форма: `CommonForms/<Имя>/Ext/form.frm`, без `Forms`
    if "Forms" not in parts:
        return ("?", "?", "?")
    i = len(parts) - 1 - parts[::-1].index("Forms")
    form = parts[i + 1] if i + 1 < len(parts) else "?"
    obj = parts[i - 1] if i >= 1 else "?"
    klass = parts[i - 2] if i >= 2 else "?"
    return ("External" if klass not in CLASSES else klass, obj, form)


def config_of(rel):
    """Конфигурация учитывается в нормах один раз. База определяется по пути до `bases/<база>` (внутри `src` и `ext/<расширение>`:
    расширение — часть базы), внешняя обработка — по пути до `epf/<обработка>`. У наборов-выгрузок из `FRM_DUMP_SETS` раскладка
    своя: конфигурацию образуют столько первых сегментов набора, сколько там названо. Путь бывает абсолютным или отсчитываться
    от корня снимка; берётся самый левый признак. Если признака нет, берётся путь до каталога класса объекта, а если нет и
    его — значение «?».
    """
    parts = PurePosixPath(str(rel).replace("\\", "/")).parts
    sets = dump_sets()
    found = [(i, m) for m in ("bases", "epf", *sets) if m in parts for i in [parts.index(m)]]
    if found:
        i, m = min(found)
        if m == "bases" and i + 1 < len(parts) and i >= 1:
            return "/".join(parts[i - 1:i + 2])
        if m == "epf" and i + 1 < len(parts) and i >= 1:
            return "/".join(parts[i - 1:i + 2])
        if m in sets and i + sets[m] <= len(parts):
            return "/".join(parts[i:i + sets[m]])
    for i, seg in enumerate(parts):
        if seg in CLASSES and i >= 1:
            return "/".join(parts[max(0, i - 2):i])
    return "?"


def config_kind(config):
    """Вид конфигурации для подсчёта в отчёте: база, внешняя обработка или выгрузка набора."""
    if "/bases/" in config:
        return "база"
    if "/epf/" in config:
        return "внешняя обработка"
    return "выгрузка" if config.split("/")[0] in dump_sets() else "прочее"


def kind_of(klass, obj, form, main):
    if is_regulated(obj):
        return "regulated"
    if klass == "CommonForms":
        return "other:CommonForms"  # раздел общих форм: основной реквизит `ОбработкаОбъект` у них не определяет вид
    if main in KNOWN:
        return KNOWN[main]
    if form.startswith(LIST_FORMS) and klass in ("Catalogs", "Documents"):
        return {"Catalogs": "catalog.list", "Documents": "document.list"}[klass]
    return BY_CLASS.get(klass, f"other:{klass}")


def main_attribute(doc):
    attrs = doc.get("attributes") or {}
    main_id = (attrs.get("u0") or {}).get("main_attribute_id")
    for row in (attrs.get("list") or {}).get("items") or []:
        ident = row.get("u0")
        ident = ident[0] if isinstance(ident, list) and ident else ident
        if ident == main_id:
            return row.get("name")
    return None


def _to_form(item, side, form_side):
    return any(r is not None and r.obj == 0 and r.side == form_side for r in item.rules[side])


def font_ppem(node, doc):
    """Высота шрифта элемента в px (`textwidth.ppem_of` по размеру в пунктах) либо `None`: размер шрифта неизвестен (стиль без размера)."""
    try:
        size = textwidth.element_font(node, doc).get("size")
    except (KeyError, TypeError, ValueError, IndexError, AttributeError):  # шрифт, который запись не разбирает: поведение размера неизвестно
        return None
    return textwidth.ppem_of(size) if size else None


def record(doc, rel):
    klass, obj, form_name = where(rel)
    rec = {"path": rel, "kind": kind_of(klass, obj, form_name, main_attribute(doc)), "config": config_of(rel)}
    form = layout.read(doc)
    rec["w"], rec["h"] = form.width, form.height
    rec["top"] = [{"type": it.type, "name": it.name, "box": list(it.box),
                   "right_to_form": _to_form(it, 3, 3), "bottom_to_form": _to_form(it, 1, 1)}
                  for it in form.holders[0].children if it.visible]
    # Размеры в пикселях сравнимы только при DPI 96 (у формы без записи DPI — короткое поколение): надписи и поля на другом DPI в нормы ширины и зазора не идут.
    dpi_ok = (doc.get("form") or {}).get("dpi") in (None, 96)
    shown = [it for it in form.holders[0].children if it.visible]
    for t, it in zip(rec["top"], shown):
        if dpi_ok and t["type"] in ("Label", "TextBox"):
            ppem = font_ppem(it.node, doc)
            if ppem is not None and ppem != textwidth.DEFAULT_PPEM:
                t["ppem"] = ppem  # шрифт крупнее или мельче шрифта формы по умолчанию: линтер сдвигает диапазон высот на разницу (`lint._norm_remarks`)
        if t["type"] == "TextBox" and textgap.is_multi_line(it.node):
            t["multi_line"] = True  # многострочное поле: своя норма высоты (`multiline_field_height`, `multiline_lines`), в `field_height` не входит
        if t["type"] == "Label":  # конец текста надписи: x и ширина текста; `None` — не одна строка, шрифт не проверялся или DPI не 96
            got = textgap.label_text_end(it.node, doc, t["box"]) if dpi_ok else None
            t["text_end"], t["text_w"] = got[:2] if got is not None else (None, None)
    # поля на дату: все видимые поля ввода форм и панелей, кроме колонок табличных полей; `stretches` — поле растягивается с окном (в норму ширины не идёт)
    rec["dates"] = []
    if dpi_ok:
        try:
            coefs = layout.coefficients(form, hide=False)
        except Exception:  # noqa: BLE001 — форма, которую раскладка не читает: поведение полей неизвестно
            coefs = {}
        for holder in form.holders.values():
            for it in holder.children:
                composition = textgap.date_composition(it.node) if it.type == "TextBox" and it.visible else None
                if composition is not None:
                    c = coefs.get(it.index)
                    behaviour = layout.horizontal_behaviour(c[2], c[3]) if c is not None else None
                    rec["dates"].append([composition, it.box[2] - it.box[0], it.name, behaviour not in (layout.STANDS, layout.MOVES)])
    frames = [t["box"] for t in rec["top"] if t["type"] == "GroupBox"]
    for t in rec["top"]:
        if t["type"] in ("Label", "TextBox"):  # рамка группы: отступы внутри неё меряются от рамки, а не от края формы
            inside = [g for g in frames if g != t["box"] and g[0] <= t["box"][0] and g[1] <= t["box"][1] and g[2] >= t["box"][2] and g[3] >= t["box"][3]]
            if inside:
                t["frame"] = list(min(inside, key=lambda g: (g[2] - g[0]) * (g[3] - g[1])))
    labels = [t for t in rec["top"] if t["type"] == "Label"]
    fields = [t for t in rec["top"] if t["type"] == "TextBox"]
    rec["pairs"] = []
    for lb in labels:
        same = [f for f in fields if abs(f["box"][1] - lb["box"][1]) <= PAIR_DY and f["box"][0] >= lb["box"][2] - 2]
        if same:
            f = min(same, key=lambda f: f["box"][0] - lb["box"][2])
            rec["pairs"].append([lb["name"], f["name"]])
    return rec


def record_path(path):
    """Запись о форме по пути. Если разбор не удался, возвращается запись с полем `error`, а исключение не возникает: перепись
    считает отказы и не прерывается на первом.
    """
    from pathlib import Path
    from frm_codec import typed
    from frm_codec.tree import read_file
    path = Path(path)
    rel = str(path)
    try:
        rec = record(typed.decode(read_file(path)), rel)
        rec["sha"] = hashlib.sha256(path.read_bytes()).hexdigest()    # байтовые повторы форм считаются один раз
        return rec
    except Exception as exc:  # noqa: BLE001 — отказ учитывается и не прерывает обход
        return {"path": rel, "kind": "error", "error": f"{type(exc).__name__}: {exc}"[:200]}
