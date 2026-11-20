"""Пара «надпись + поле» на реквизит формы одним вызовом (`add_pair`).

Составная операция: то, что при ручной правке пишут четырьмя операциями (`add_element` надписи, `add_element` поля, `bind` с `copy_type`, при дате —
`choice_button`) и потом подгоняют по строке. Раскладку операция не выдумывает — она зовёт те же операции с теми же правилами:

* надпись и поле встают по соседям, как `add_element` без `box` (`frm_codec.place`): надпись — под последней надписью, поле — под последним полем ввода,
  размер, привязки и оформление — соседа того же типа; на форме без образца шаг строк даёт вид формы (`kind`);
* поле выравнивается с надписью по строке — так, как стоят уже существующие пары страницы (`move_element` с `keep`: правила привязок те же,
  смещения пересчитаны под место);
* тип поля берётся у реквизита (`bind` с `copy_type`): строка, число, дата; реквизит типа Булево ставится флажком — у флажка своя подпись, надписи нет;
* поле даты получает ширину поля даты того же состава (на форме есть такое — его, иначе норма вида) и кнопку выбора (календарь).

Подпись по умолчанию — имя реквизита словами («СрокВыпуска» → «Срок выпуска:»); имя поля — имя реквизита, имя надписи — «Надпись» + имя поля.
Отказ любого шага возвращает форму прежней.
"""
import copy
import re

from .base import EditError, element_names, elements_of, find_element
from .names import (ATTR_LIST, ATTR_NAME, ATTR_PATTERN, COORDS, HEIGHT, PATTERN_KIND, PATTERN_TYPES, WIDTH, X, Y)

# Надпись выше или ниже своего поля не больше чем на столько — одна строка пары (`place.PAIR_DY`).
PAIR_DY = 3
FIELD_BY_LETTER = {"S": "TextBox", "N": "TextBox", "D": "TextBox", "B": "CheckBox"}


def words_of(name):
    """Имя реквизита словами: «СрокВыпуска» → «Срок выпуска»; подчёркивания — пробелы, регистр первой буквы прежний."""
    spaced = re.sub(r"(?<=[a-zа-яё0-9])(?=[A-ZА-ЯЁ])", " ", str(name).replace("_", " "))
    head, tail = spaced[:1], spaced[1:]
    tail = " ".join(word if word.isupper() and len(word) > 1 else word[:1].lower() + word[1:] for word in tail.split(" "))
    return (head + tail).strip()


def _row(doc, attribute):
    attributes = doc.get("attributes")
    rows = attributes.get(ATTR_LIST) if isinstance(attributes, dict) else None
    items = rows.get("items") if isinstance(rows, dict) else None
    if not isinstance(items, list):
        raise EditError("у формы нет разобранного списка реквизитов — пара без реквизита не нужна (add_attribute заводит реквизит)")
    for row in items:
        if isinstance(row, dict) and row.get(ATTR_NAME) == attribute:
            return row
    known = ", ".join(str(r.get(ATTR_NAME)) for r in items if isinstance(r, dict))
    raise EditError(f"реквизита формы {attribute!r} нет; есть: {known or '—'}. Реквизит заводит add_attribute (пара ставится на реквизит формы)")


def _letter(row, attribute):
    pattern = row.get(ATTR_PATTERN)
    types = pattern.get(PATTERN_TYPES) if isinstance(pattern, dict) else None
    letters = [b.get(PATTERN_KIND) if isinstance(b, dict) else None for b in types] if isinstance(types, list) else []
    if len(letters) != 1 or letters[0] not in FIELD_BY_LETTER:
        have = ", ".join(map(str, letters)) or "описателя типа нет"
        raise EditError(f"реквизит {attribute!r}: {have}. Пара ставится на реквизит одного типа — строка (S), число (N), дата (D) или булево (B, флажок); "
                        "для прочих типов ставьте поле и привязку отдельными операциями (add_element, bind)")
    return letters[0], types[0]


def _date_composition(block):
    from .cowrites import DATE_LETTERS, PATTERN_DATE
    letter = block.get(PATTERN_DATE)
    return next((word for word, code in DATE_LETTERS.items() if code == letter), "DateTime")


def _mate_dy(items, page, skip):
    """Сдвиг верха поля относительно верха его надписи у уже стоящих пар страницы (самая нижняя пара); `skip` — новые элементы, в расчёт не входят;
    пар нет — 0."""
    boxes = [(i.get("type"), i[COORDS]) for i in items if isinstance(i.get(COORDS), dict) and i[COORDS].get("page") == page and all(i is not s for s in skip)]
    best = None
    for kind, c in boxes:
        if kind != "TextBox":
            continue
        for lk, lc in boxes:
            if lk == "Label" and abs(lc[Y] - c[Y]) <= PAIR_DY and lc[WIDTH] <= c[X] + 2 and c[X] - lc[WIDTH] <= 60:
                if best is None or c[Y] > best[0]:
                    best = (c[Y], c[Y] - lc[Y])
    return best[1] if best else 0


def _mates(doc, holder, page, after):
    """`(сосед для надписи, сосед для поля)` по `after`: названа надпись пары — сосед поля её поле справа на строке, названо поле — сосед надписи
    её надпись слева на строке. Пары у названного нет — оба под ним. `after` не назван — `(None, None)`."""
    if after is None:
        return None, None
    from .base import holder_by_name
    target = holder_by_name(doc, None if holder in (None, "", "форма") else holder)
    items = [i for i in elements_of(target) if isinstance(i.get(COORDS), dict) and i[COORDS].get("page") == page]
    named = next((i for i in items if (i.get("name_block") or {}).get("name") == after), None)
    if named is None:
        return after, after
    c = named[COORDS]
    name_of = lambda i: (i.get("name_block") or {}).get("name")
    if named.get("type") == "Label":
        mates = [i for i in items if i.get("type") in ("TextBox", "ComboBox") and abs(i[COORDS][Y] - c[Y]) <= PAIR_DY and i[COORDS][X] >= c[WIDTH] - 2
                 and i[COORDS][X] - c[WIDTH] <= 60]
        return after, (name_of(min(mates, key=lambda i: i[COORDS][X])) if mates else after)
    mates = [i for i in items if i.get("type") == "Label" and abs(i[COORDS][Y] - c[Y]) <= PAIR_DY and i[COORDS][WIDTH] <= c[X] + 2 and c[X] - i[COORDS][WIDTH] <= 60]
    return (name_of(max(mates, key=lambda i: i[COORDS][WIDTH])) if mates else after), after


def add_pair(doc, attribute, caption=None, name=None, label_name=None, holder=None, page=0, after=None, kind=None, width=None,
             unverified=False, siblings=None):
    """Пара «надпись + поле» на реквизит формы `attribute`: надпись, поле ввода (флажок у булева), привязка с типом реквизита и выравнивание по строке.

    * `caption` — подпись надписи (у флажка — его подпись); умолчание — имя реквизита словами с двоеточием («Срок выпуска:»), у флажка без двоеточия.
    * `name` — имя поля (умолчание — имя реквизита), `label_name` — имя надписи (умолчание — «Надпись» + имя поля).
    * `holder`, `page`, `after` — как у `add_element`: родитель, страница (номер или имя) и сосед, после которого встаёт пара: надпись или поле
      предыдущей пары (вторая половина её пары находится на строке сама); без `after` надпись встаёт под последней надписью, поле — под последним полем.
    * `kind` — вид формы из `patterns.json`; нужен, когда шаг строк взять неоткуда (на форме нет двух смежных строк полей).
    * `width` — ширина поля (умолчание — как у соседнего поля, у даты — ширина поля даты того же состава).

    Дата — со своей шириной и кнопкой выбора (`choice_button`). Тип реквизита — строка, число, дата или булево; иной — отказ словами. Раскладку и
    привязки выбирают `add_element` (по соседям, с проверкой на модели раскладки) и `move_element` (`keep`): правил раскладки здесь нет.
    Отказ любого шага возвращает форму прежней."""
    snapshot = copy.deepcopy(doc)
    try:
        return _add_pair(doc, attribute, caption, name, label_name, holder, page, after, kind, width, unverified, siblings)
    except EditError:
        doc.clear()
        doc.update(snapshot)
        raise


def _add_pair(doc, attribute, caption, name, label_name, holder, page, after, kind, width, unverified, siblings):
    from . import elements as ee
    from .data import bind
    from .setprop import set_property
    row = _row(doc, attribute)
    letter, block = _letter(row, attribute)
    field = name or attribute
    label = label_name or "Надпись" + field
    taken = element_names(doc)
    for each in ((field,) if letter == "B" else (field, label)):
        if each in taken:
            raise EditError(f"элемент {each!r} в форме уже есть: назовите другое имя ({'name' if each == field else 'label_name'}) либо снимите прежний")
    if width is not None and (isinstance(width, bool) or not isinstance(width, int) or width <= 0):
        raise EditError(f"width — ширина поля в пикселях, целое положительное, а пришло {width!r}")
    common = dict(holder=holder, page=page, kind=kind, unverified=unverified, siblings=siblings)
    said = []
    if letter == "B":
        text = caption if caption is not None else words_of(attribute)
        said.append(ee.add_element(doc, "CheckBox", field, caption=text, after=after, **common))
        said.append(bind(doc, field, attribute, unverified=unverified, copy_type=True))
        return f"пара {attribute!r}: флажок {field!r} (у булева реквизита своя подпись, надписи нет)" + "".join(f"; {w}" for w in said)
    text = caption if caption is not None else words_of(attribute) + ":"
    after_label, after_field = _mates(doc, holder, ee._page_arg(doc, holder, page), after)
    said.append(ee.add_element(doc, "Label", label, caption=text, after=after_label, **common))
    said.append(ee.add_element(doc, "TextBox", field, after=after_field, **common))
    said.append(bind(doc, field, attribute, unverified=unverified, copy_type=True))
    composition = _date_composition(block) if letter == "D" else None
    if letter == "D":
        said.append(set_property(doc, field, "choice_button", True, unverified=unverified))
    said.append(_align(doc, field, label, holder, page, width, composition, kind))
    return f"пара {attribute!r}: надпись {label!r} + поле {field!r}" + "".join(f"; {w}" for w in said if w)


def _align(doc, field, label, holder, page, width, composition, kind):
    """Поле — на строку надписи (со сдвигом, какой у уже стоящих пар) и нужной ширины; правила привязок прежние (`keep`)."""
    from . import elements as ee
    from .. import place as _place
    f, l = find_element(doc, field), find_element(doc, label)
    fc, lc = f.element[COORDS], l.element[COORDS]
    dy = _mate_dy(elements_of(f.holder), f.page, (f.element, l.element))
    top = lc[Y] + dy
    w, h = fc[WIDTH] - fc[X], fc[HEIGHT] - fc[Y]
    said = ""
    if width is not None:
        w = width
    elif composition is not None:
        got, words = _place.date_width(doc, composition, kind)
        if got is not None:
            w, said = got, words
    if (fc[Y], fc[WIDTH] - fc[X]) == (top, w):
        return said
    moved = ee.move_element(doc, field, (fc[X], top, w, h), anchor="keep", holder=holder, page=page)
    return f"поле выровнено по строке надписи: верх {fc[Y]} → {top}, ширина {fc[WIDTH] - fc[X]} → {w}" + (f"; {said}" if said else "") + f" ({moved})"
