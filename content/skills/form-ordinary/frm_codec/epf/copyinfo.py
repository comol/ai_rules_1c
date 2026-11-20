"""Таблица ссылок `copyinfo`: что обычные формы обработки берут из метаданных обработки, и её дополнение.

`copyinfo` — `{4, {N, объект…}, {M, тип…}, {K, путь…}, {0,0}, {0}}`, кодировка UTF-8 с BOM, строки CRLF:

* объект `{uuid, uuid, глубина, {класс,"Имя"}, …}` — цепочка классов и имён от верхнего (колонка табличной части — два звена);
* тип `{TypeId, GUID владельца, индекс}` — индекс — номер пары (TypeId, ValueId) у владельца;
* путь данных `{{0, GUID}, TypeId основного реквизита, {-1}}` — привязка элемента формы `[основной реквизит, {0, GUID}]`;
* два последних раздела в проверенных файлах всегда `{0,0}` и `{0}`; разделы идут по возрастанию GUID.

Каждый GUID из текста обычных форм, который есть во внутренних метаданных (реквизит, табличная часть, реквизит табличной
части — объект; TypeId из пар типов объекта — тип, и его владелец — объект), попадает в таблицу; плюс основная форма и пути
привязок через основной реквизит. Ссылки на объекты конфигурации (стиль, справочник) из одного файла не восстановить —
они не дописываются.

Проверено только то, что есть в образцах: версия 4 и шесть разделов; свои типы с индексом пары 0; пути через основной реквизит
из двух шагов, ведущие к объекту обработки, с типом основного реквизита из пар обработки. Всё остальное — отказ словами, а не
запись: из образцов не видно, как платформа записала бы такую ссылку.
"""
from .. import typed
from ..json0 import decode0, encode0
from ..tree import parse, render
from .container import EpfError
from .meta import CLASS_ROOT, FORM_CLASSES, GUID_RE, WAY_OUT


def _main_type(attributes, main):
    for item in attributes.get("list", {}).get("items", []):
        if item.get("u0") == [main]:
            types = item.get("pattern", {}).get("types") or []
            if types and isinstance(types[0].get("value_type"), dict):
                return types[0]["value_type"].get("guid")
    return None


def _form_paths(text, form_name):
    """Привязки через основной реквизит: `(GUID, TypeId основного реквизита, шаги пути, номер элемента)`.
    Отказ разбора — `EpfError`."""
    try:
        attributes = typed.decode(parse(text))["attributes"]
    except Exception:
        raise EpfError(f"форма {form_name} не разобрана: строение не проверялось. " + WAY_OUT) from None
    main = attributes.get("u0", {}).get("main_attribute_id")
    main_type = _main_type(attributes, main)
    out = []
    for binding in attributes.get("bindings", {}).get("items", []):
        steps = binding.get("path", {}).get("steps", [])
        if len(steps) >= 2 and steps[0].get("u0") == main and isinstance(steps[1].get("u1"), dict):
            out.append((steps[1]["u1"]["guid"], main_type, steps, binding.get("element")))
    return out


class Result:
    def __init__(self):
        self.objects, self.types, self.paths = [], [], []   # (guid, подпись)
        self.tree = None
        self.text = None

    @property
    def changed(self):
        return bool(self.objects or self.types or self.paths)


def _check_shape(tree):
    if not (isinstance(tree, list) and len(tree) == 6 and tree[0] == 4 and tree[4] == [0, 0] and tree[5] == [0]):
        shown = f"версия {tree[0]}, разделов {len(tree) - 1}" if isinstance(tree, list) and tree else "не блок"
        raise EpfError(f"строение copyinfo не проверялось ({shown}; проверено: версия 4, шесть разделов, хвост {{0,0}} и {{0}}). "
                       + WAY_OUT)


def merge(proc):
    """Дополняет `copyinfo` обработки. Записанное не меняется. Возвращает `Result` (с новым текстом, если что-то дописано)."""
    meta = proc.meta
    item = proc.container.get("copyinfo")
    if item is None:
        raise EpfError("в контейнере нет элемента copyinfo: команда дополняет таблицу, но не создаёт её")
    old = item.data
    try:
        tree = decode0(parse(old.decode("utf-8-sig")))
    except Exception:
        raise EpfError("copyinfo не разобран: строение не проверялось. " + WAY_OUT) from None
    _check_shape(tree)
    try:
        objs = {o[0]["guid"]: o for o in tree[1][1:]}
        types = {t[0]["guid"]: t for t in tree[2][1:]}
        links = {p[0][1]["guid"]: p for p in tree[3][1:]}
    except Exception:
        raise EpfError("copyinfo не разобран: строение записей не проверялось. " + WAY_OUT) from None
    res = Result()

    def add_obj(guid):
        if guid in objs or guid not in meta.objs:
            return
        chain = meta.objs[guid]
        objs[guid] = [{"guid": guid}, {"guid": guid}, len(chain)] + [[{"guid": c}, n] for c, n in chain]
        res.objects.append((guid, meta.label(guid)))

    if proc.forms and meta.default_form in meta.objs:
        add_obj(meta.default_form)
    for slot in meta.form_slots[1:]:
        if slot not in meta.objs or meta.objs[slot][-1][0] not in FORM_CLASSES:
            continue            # макеты и прочее в слотах — не форма
        if meta.objs[meta.root][0][0] != CLASS_ROOT:
            raise EpfError(f"у отчёта заполнен дополнительный слот формы ({meta.label(slot)}): состав copyinfo для него не "
                           "проверялся. " + WAY_OUT)
        if proc.forms:
            add_obj(slot)       # дополнительная форма обработки пишется так же, как основная
    for guid_form, text in proc.forms.items():
        form = proc.form_names[guid_form]
        for g in sorted(set(GUID_RE.findall(text))):
            if g in meta.types:
                owner, idx = meta.types[g]
                if g not in types:
                    if idx:
                        raise EpfError(f"форма {form} ссылается на тип {meta.label(owner)} (пара типов {idx + 1}), которого нет в "
                                       "copyinfo: запись типа с индексом пары больше нуля не проверялась. " + WAY_OUT)
                    types[g] = [{"guid": g}, {"guid": owner}, idx]
                    res.types.append((g, meta.label(owner)))
                add_obj(owner)
            elif g in meta.objs and g != meta.root and meta.objs[g][-1][0] not in FORM_CLASSES:
                add_obj(g)
        for g, main_type, steps, element in _form_paths(text, form):
            # Проверки не зависят от порядка привязок: `continue` по уже записанному пути стоит после них.
            where = f"в форме {form}, элемент №{element}, путь {_steps_text(steps, meta, g)}"
            if len(steps) > 2:
                raise EpfError(f"привязка через основной реквизит длиннее двух шагов {where}: такой путь в copyinfo не проверялся. "
                               + WAY_OUT)
            if g not in meta.objs:
                raise EpfError(f"привязка {where} ведёт к объекту, которого нет в метаданных обработки: не проверялось. " + WAY_OUT)
            if main_type not in meta.types:
                raise EpfError(f"привязка {where}: тип основного реквизита не из пар типов обработки: не проверялось. " + WAY_OUT)
            if g in links:
                continue
            links[g] = [[0, {"guid": g}], {"guid": main_type}, [-1]]
            res.paths.append((g, f"{meta.label(g)} (через основной реквизит формы)"))
    if not res.changed:
        return res
    ordered = lambda d: [v for _, v in sorted(d.items())]
    res.tree = [4, [len(objs)] + ordered(objs), [len(types)] + ordered(types), [len(links)] + ordered(links), tree[4], tree[5]]
    text = render(encode0(res.tree)).encode("utf-8")
    res.text = b"\xef\xbb\xbf" + text if old.startswith(b"\xef\xbb\xbf") and not text.startswith(b"\xef\xbb\xbf") else text
    return res


def _steps_text(steps, meta, guid):
    """Путь словами: «основной реквизит → реквизит Имя» и число лишних шагов, если их больше двух."""
    text = f"основной реквизит → {meta.label(guid) if guid in meta.objs else 'объект вне метаданных обработки ' + guid}"
    return text + (f" (+ ещё шагов: {len(steps) - 2})" if len(steps) > 2 else "")
