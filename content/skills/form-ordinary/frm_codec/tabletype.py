"""Тип значения табличного поля (`content/u1` поля `TableBox`) против данных, к которым поле привязано.

Путь данных табличного поля лежит в таблице привязок формы, а тип значения — в самом поле: `["Pattern", ["#", {"guid": G}]]`. Конструктор
платформы пишет их согласованно. Поле с чужим типом платформа загружает без ошибки, но колонки его выбрасывает: в предприятии таблица формы
списка пустая, у таблицы на табличной части в базе ноль колонок, а после выгрузки и загрузки платформа меняет и источник данных таблицы.
Ни разбор, ни сборка, ни рендер такую форму не отличают от исправной: колонки в файле записаны.

Как пишет конструктор (перепись снимка выгрузок конфигураций `FRM_CONFIG_DUMPS`: 1 296 форм, 2 345 привязанных табличных полей):

* поле на реквизит формы (путь из одного шага) — тип поля равен типу реквизита: 991 поле из 991, из них 370 — таблицы форм списка
  (основной реквизит типа `List` объекта), 379 — таблицы и деревья значений (тип платформы: `ValueTable` → `acf6192e-…`);
* поле на табличную часть объекта (путь «основной реквизит → часть», `[{u0: M}, {u0: 0, u1: {guid: G_ts}}]`) — тип поля равен `TypeId` части
  по выгрузке (`xr:GeneratedType category="TabularSection"`, `metadata.Table.type_id`): 341 из 341;
* привязанного поля с нулевым типом нет ни одного.

Отсюда три правила (`findings`):

1. `attribute` — поле на реквизит формы с одним блоком типа «#»: тип поля не равен типу реквизита;
2. `zero` — привязанное поле с нулевым типом (без выгрузки — единственный признак таблицы на табличной части без типа);
3. `tabular` — с выгрузкой: поле на табличную часть объекта формы, у которой в выгрузке есть `TypeId`, а тип поля другой.

Пути длиннее (настройки построителя отчёта, отбор и т. п.) и путь «основной реквизит → реквизит объекта» (таблица значений в реквизите
обработки) правилами не проверяются: тип таких полей — тип платформы, а сам путь без выгрузки от пути к табличной части не отличить.
"""
import dataclasses

from . import schema
from .edit import base as ed_base
from .edit.datapath import ATTR_HEAD, GUID, MAIN_ATTRIBUTE_ID, STEP_GUID, _id_of, _type_guid
from .edit.names import (ATTR_LIST, ATTR_NAME, BIND_ELEMENT, BIND_PATH, BINDINGS, CONTENT, ELEMENTS, INDEX, ITEMS, PATH_STEPS, STEP_VALUE,
                         TABLE_TYPE)

ZERO = "00000000-0000-0000-0000-000000000000"
WORDS = "тип табличного поля"         # начало каждого замечания: по нему замечания этого рода узнают в общем списке `validate`


@dataclasses.dataclass(frozen=True)
class Finding:
    rule: str           # `attribute`, `zero`, `tabular`
    element: str        # имя табличного поля
    have: str           # тип поля
    want: str           # тип, который пишет конструктор (у `zero` без выгрузки — `None`)
    text: str


def type_of(element):
    """GUID типа значения табличного поля либо `None`, если блок типа не разобран."""
    content = element.get(CONTENT) if isinstance(element, dict) else None
    raw = content.get(TABLE_TYPE) if isinstance(content, dict) else None
    if not (isinstance(raw, list) and len(raw) == 2 and isinstance(raw[1], list) and len(raw[1]) == 2 and raw[1][0] == "#"
            and isinstance(raw[1][1], dict)):
        return None
    guid = raw[1][1].get(GUID)
    return guid if isinstance(guid, str) else None


def set_type(element, guid):
    """Записывает тип значения табличного поля; прежний GUID — в ответ. Блок типа должен быть разобран (`type_of` не `None`)."""
    raw = element[CONTENT][TABLE_TYPE]
    was = raw[1][1].get(GUID)
    raw[1][1] = {GUID: guid}
    return was


def _rows(doc):
    """`(номер основного реквизита, {номер: строка реквизита}, {индекс элемента: шаги пути})` либо `None`, если реквизиты не разобраны."""
    attributes = doc.get("attributes") if isinstance(doc, dict) else None
    if not isinstance(attributes, dict):
        return None
    head = attributes.get(ATTR_HEAD)
    main = head.get(MAIN_ATTRIBUTE_ID) if isinstance(head, dict) else None
    block = attributes.get(ATTR_LIST)
    rows = block.get("items") if isinstance(block, dict) else None
    binds = attributes.get(BINDINGS)
    items = binds.get("items") if isinstance(binds, dict) else None
    if not isinstance(rows, list) or not isinstance(items, list):
        return None
    by_id = {_id_of(r): r for r in rows if isinstance(r, dict)}
    paths = {}
    for row in items:
        path = row.get(BIND_PATH) if isinstance(row, dict) else None
        steps = path.get(PATH_STEPS) if isinstance(path, dict) else None
        if isinstance(steps, list) and steps and all(isinstance(s, dict) for s in steps):
            paths[row.get(BIND_ELEMENT)] = steps
    return main, by_id, paths


def tables(doc):
    """Табличные поля формы на любой глубине: `[(имя, узел, шаги пути или None)]`."""
    found = _rows(doc)
    if found is None:
        return []
    _main, _by_id, paths = found
    try:
        holders = ed_base.holders(doc)
    except ed_base.EditError:
        return []
    out = []
    for _name, holder in holders:
        block = holder.get(ELEMENTS)
        for item in (block.get(ITEMS) or []) if isinstance(block, dict) else []:
            if isinstance(item, dict) and item.get("type") == "TableBox":
                out.append((ed_base.name_of(item), item, paths.get(item.get(INDEX))))
    return out


def bound_to(doc, attribute_id):
    """Табличные поля, привязанные к реквизиту формы `attribute_id` путём из одного шага: `[(имя, узел)]`."""
    return [(name, node) for name, node, steps in tables(doc) if steps and len(steps) == 1 and steps[0].get(STEP_VALUE) == attribute_id]


def findings(doc, config=None):
    """Расхождения типа табличных полей с данными привязки (правила — в описании модуля). `config` — `metadata.Config` выгрузки: с ним проверяется и
    тип таблицы на табличной части."""
    found = _rows(doc)
    if found is None:
        return []
    main, by_id, _paths = found
    obj = None
    if config is not None and main in by_id:
        hit = config.object_by_type_id(_type_guid(by_id[main]))
        obj = hit[0] if hit else None
    out = []
    for name, node, steps in tables(doc):
        have = type_of(node)
        if not steps or have is None:
            continue
        if len(steps) == 1:
            row = by_id.get(steps[0].get(STEP_VALUE))
            want = _type_guid(row) if row is not None else None
            if want is not None and have != want:
                attr = row.get(ATTR_NAME)
                platform = next((n for n, g in schema.GUID_NAMES["AttributeType"].items() if g == want), None)
                out.append(Finding("attribute", name, have, want, (
                    f"{WORDS} «{name}» — {have}, а реквизит формы «{attr}», к которому оно привязано, — типа {want}"
                    + (f" ({platform})" if platform else "") + ": конструктор пишет полю тип его реквизита; с другим типом платформа загружает форму, "
                    f"но таблицу показывает без колонок. Тип поля — `content/u1` табличного поля: {want}")))
            continue
        tabular = len(steps) == 2 and steps[0].get(STEP_VALUE) == main and steps[1].get(STEP_VALUE) == 0 \
            and isinstance(steps[1].get(STEP_GUID), dict)
        part = None
        if tabular and obj is not None:
            part = next((t for t in obj.tables if t.uuid == steps[1][STEP_GUID].get(GUID)), None)
        if part is not None and part.type_id:
            if have == part.type_id:
                continue
            out.append(Finding("tabular", name, have, part.type_id, (
                f"{WORDS} «{name}» — {'нулевой' if have == ZERO else have}, а табличная часть «{part.name}» объекта «{obj.full_name}», к которой "
                f"оно привязано, — типа {part.type_id} (TypeId части по выгрузке): с другим типом платформа загружает форму, но колонки таблицы "
                f"выбрасывает. Тип поля — `content/u1` табличного поля: {part.type_id}; у новой таблицы его пишет `bind` с `data`")))
        elif have == ZERO:
            out.append(Finding("zero", name, have, None, (
                f"{WORDS} «{name}» нулевой ({ZERO}), а поле привязано к данным: конструктор пишет полю тип его данных (у таблицы на табличной "
                "части — TypeId части по выгрузке); с нулевым типом платформа загружает форму, но колонки таблицы выбрасывает. Тип поля — "
                "`content/u1` табличного поля; `validate --config` называет нужный TypeId, у новой таблицы его пишет `bind` с `data`")))
    return out
