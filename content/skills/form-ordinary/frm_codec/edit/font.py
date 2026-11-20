"""Шрифт элемента. Все имена доступны через фасад `frm_codec.edit`."""

import copy

from .names import (
    ABSOLUTE,
    AUTO,
    COLUMN_CONTROL,
    COLUMN_ITEMS,
    CONTENT,
    COORDS,
    CORPUS_STAMP,
    FONT_BITS,
    FONT_KEYS,
    FONT_KINDS,
    FONT_REF,
    FONT_SCALE,
    FONT_SOURCE,
    FONT_SOURCES,
    FONT_VERSION,
    OVERRIDES,
    SCALE_SET,
    STYLE_FONT,
    STYLE_FONTS,
    SYSTEM_FONT,
    SYSTEM_FONTS,
    WIDTH,
    X,
    _FONT_RUN,
)
from .base import EditError, _on_corpus, find_element
from .platform import (
    CORPUS_CONTROL_FONT_PLACES,
    CORPUS_FONT_FACES,
    CORPUS_FONT_PLACES,
    CORPUS_FONT_RECORDS,
    CORPUS_FONT_SCALE,
    CORPUS_FONT_SIZES,
    ROUND10_AUTO_WARNING,
    ROUND10_FONT,
    ROUND10_FONT_RECORDS,
    ROUND7_FONT_PLACE,
    ROUND7_FONT_RECORDS,
)
from .elements import _short
from . import fontabs as _fontabs
from .columns import _column_name, _columns_holder, column_control


# Шрифт элемента

def _font_places(node, trail=(), skip=()):
    """Находит записи шрифта внутри узла. Обход идёт по словарям и не заходит в списки (как `_caption_places`): шрифты других
    элементов лежат в списках, а именно шрифты колонок в списке колонок и шрифты вложенных элементов в списке элементов. Каждый
    из них адресуется своим путём: колонка — параметром `column`, вложенный элемент — своим именем.

    У колонки есть ещё один отдельный шрифт. Вложенный элемент колонки — это словарь `control`, и в нём лежит собственный шрифт
    (`font`). Его пропускают через `skip`. Шрифт колонки и шрифт её элемента принадлежат разным палитрам; второй адресуется
    параметром `nested=True`.
    """
    for key, value in node.items() if isinstance(node, dict) else ():
        if key in skip:
            continue
        if key in FONT_KEYS and isinstance(value, dict) and FONT_SOURCE in value:
            yield trail + (key,), value
        elif isinstance(value, dict):
            yield from _font_places(value, trail + (key,), skip)


FORM_KIND = "Form"
FORM_FONT_PATH = ("form", "container", "layout_holder", "layout_list", "layout", "font")
# Сколько форм снимка из 4 993 несёт запись шрифта формы данного вида: `(версия записи, вид, маска)`. Записей «Авто» с
# переопределением, шрифта стиля и системного шрифта у форм мало; абсолютного шрифта у формы в образцах нет (его проверила
# платформа).
CORPUS_FORM_FONT_RECORDS = {
    (6, "Auto", 0): 2061, (7, "Auto", 0): 2695, (6, "Auto", 4): 2, (7, "Auto", 4): 6, (6, "Auto", 16): 1,
    (7, "Auto", 16): 1, (7, "Auto", 8): 1, (6, "StyleFont", 0): 139, (7, "StyleFont", 0): 81,
    (7, "StyleFont", 2): 2, (6, "SystemFont", 0): 1, (6, "SystemFont", 1): 1, (7, "SystemFont", 0): 1,
    (7, "SystemFont", 62): 1,
}


def form_font_record(doc):
    """Запись шрифта самой формы (`form/container/layout_holder/layout_list/layout/font`) или отказ словами."""
    node = doc
    for key in FORM_FONT_PATH:
        node = node.get(key) if isinstance(node, dict) else None
    if not isinstance(node, dict) or FONT_SOURCE not in node:
        raise EditError("у формы не разобрана запись шрифта (`" + "/".join(FORM_FONT_PATH) + "`) — править её именами нечем")
    return node


def _font_record(doc, element, font, column, nested=False):
    """Возвращает `(запись шрифта, тип, имя поля, чей это шрифт словами)` по адресу вызова.

    Шрифт выбирается по имени поля из карты (`font`, `header_font`, `footer_font`, `text_font`): у табличного поля таких шрифтов
    три, и у колонки три (ШрифтШапки, ШрифтПодвала, ШрифтТекста). Если такого шрифта нет, отказ перечисляет шрифты узла.

    Параметр `nested=True` означает адрес «колонка → вложенный элемент», то есть шрифт элемента, в котором редактируется ячейка.
    Тип в этом случае — `ColumnControl.<вид>`, а допустимые значения заданы отдельно (`CORPUS_CONTROL_FONT_PLACES`).
    """
    place = find_element(doc, element)
    kind = place.element.get("type")
    if nested:
        if column is None:
            raise EditError("nested=true — это вложенный элемент КОЛОНКИ: назовите column")
        _head, nested_kind, root = column_control(doc, element, column)
        kind = f"ColumnControl.{nested_kind}"
        whose = f"вложенного элемента ({nested_kind}) колонки {column!r} поля {element!r}"
    elif column is None:
        root, whose = place.element.get(CONTENT) or {}, f"элемента {element!r} ({kind})"
    else:
        block = _columns_holder(doc, element)
        found = [item for item in block[COLUMN_ITEMS] if _column_name(item) == column]
        if not found:
            known = ", ".join(str(_column_name(item)) for item in block[COLUMN_ITEMS]) or "—"
            raise EditError(f"колонки {column!r} у {element!r} нет; есть: {known}")
        if len(found) > 1:
            raise EditError(f"колонок с именем {column!r} у {element!r} — {len(found)}; "
                            "какую из них править, по имени не решить")
        root, kind = found[0], "TableBoxColumn"
        whose = f"колонки {column!r} поля {element!r}"
    places = list(_font_places(root, skip=() if nested else (COLUMN_CONTROL,)))
    same = [(trail, record) for trail, record in places if trail[-1] == font]
    if not same and kind == "SpreadsheetDocumentField":
        raise EditError(f"у {whose} шрифта нет: в палитре поля табличного документа строки «Шрифт» нет, и записи шрифта в "
                        "элементе нет — править нечего")
    if not same:
        known = ", ".join(sorted({trail[-1] for trail, _r in places})) or "—"
        raise EditError(f"шрифта {font!r} у {whose} нет; есть: {known}. Имена шрифтов карта "
                        f"знает такие: {', '.join(FONT_KEYS)}")
    if len(same) > 1:
        where = ", ".join("/".join(trail) for trail, _r in same)
        raise EditError(f"шрифтов {font!r} у {whose} несколько ({where}) — какой из них ваш, "
                        "карта не различает; правьте JSON по адресу")
    return same[0][1], kind, font, whose


def _order_overrides(overrides):
    """Ключи переопределений в порядке карты. Если ключ неизвестен, операция отказывает и перечисляет известные. Порядок совпадает
    с порядком значений в файле (`Masked.bits`): имя шрифта (бит 1) стоит последним.
    """
    unknown = [key for key in overrides if key not in FONT_BITS and key != SCALE_SET]
    if unknown:
        raise EditError(f"в переопределениях шрифта нет ключей {', '.join(sorted(unknown))}; "
                        f"карта знает {', '.join(FONT_BITS)} и обязательный {SCALE_SET}")
    out = {key: overrides[key] for key in FONT_BITS if key in overrides}
    # Значение флага берётся как есть и не приводится к булеву. Приведение молча исправило бы чужую ошибку, например «1» вместо
    # `true`, а о такой ошибке должна сообщить проверка.
    out[SCALE_SET] = overrides.get(SCALE_SET, False)
    return out


def font_word(overrides):
    """Маска, которую сборка получит из этих ключей: биты со значением плюс бит без значения. Маски берутся из отрезка карты. По
    маске определяется, встречалась ли платформе такая запись.
    """
    word = sum(mask for name, (mask, _kind) in _FONT_RUN.bits.items() if name in overrides)
    return word + (_FONT_RUN.flags[SCALE_SET] if overrides.get(SCALE_SET) else 0)


TYPEFACE_WAYS = ("single", "group")
# По умолчанию ставится один бит. В диалоге «Выбор шрифта» одна галочка «Из стиля» управляет четырьмя флагами начертания, и
# когда платформа сама изменяет одно только зачёркивание, она записывает все четыре бита и насыщенность 400. Запись с одним
# битом платформа тоже принимает и при пересохранении не переписывает. Умолчанием выбрано меньшее вмешательство: правка «сделай
# наклонным» не объявляет запись владельцем ещё трёх свойств, которые брались из стиля.
TYPEFACE_GROUP = ("weight", "italic", "underline", "strikeout")
TYPEFACE_FILL = {"weight": 400, "italic": False, "underline": False, "strikeout": False}


def set_font(doc, element=None, font="font", column=None, source=None, style_font=None,
             system_font=None, size=None, bold=None, italic=None, underline=None,
             strikeout=None, face=None, scale=None, scale_set=None, typeface="single",
             reset=False, unverified=False, nested=False, form=False):
    """Задаёт шрифт элемента по именам из палитры.

    В файле шрифт хранится «от противного»: записано то, чем он отличается от шрифта-основы (`source`), и маска, которая
    показывает, какие свойства заданы. Операция сама ведёт вид записи и его ссылку, набор переопределений, порядок значений,
    обязательный `scale_set` и правило «масштаб допустим только в версии 7».

    Параметры названы так же, как в палитре. `size` задаётся в пунктах (12 даёт `size10`, равный 120). `bold` — булево значение
    (700 против 400), остальные параметры как в диалоге. `reset=True` возвращает «Авто» без переопределений и ссылки.

    Хвост записи (`L1+0`) операция не меняет, потому что его смысл не установлен. У изменённой записи остаётся прежний хвост, и
    отчёт сообщает об этом.

    Абсолютный шрифт (`source="Absolute"`, гарнитура и размер вместе) пишет `edit.fontabs`: у него все свойства лежат на своих
    позициях, маски нет. Возврат с него — `source="StyleFont"` (шрифт стиля «Шрифт текста», иной — `style_font`) и `reset` либо
    `source="Auto"`: запись собирается целиком заново (`edit.fontabs.leave`); системный шрифт и значения вместе с возвратом — отказ.

    Граница проверенного проходит по трём признакам (`ON_CORPUS`): чей это шрифт, сочетание «вид записи + маска» и значения
    размера с именем шрифта (это перечень, а не правило). Если первые два признака не встречаются в образцах и не проверялись,
    операция отказывает, и отказ снимается ключом `unverified=True`. По третьему признаку добавляется только пометка.

    Шрифт вложенного элемента колонки (`column` и `nested=True`) — это шрифт ячейки в режиме редактирования. В режиме показа
    ячейку рисует шрифт самой колонки (ШрифтТекста, `text_font`). Результат зависит от вида записи. Запись «Авто» с одним битом
    полужирного платформа сохраняет и показывает в палитре, но в редактировании она не действует. Запись диалога действует:
    шрифт стиля «Шрифт текста», начертание группой, `scale_set`
    (`source="StyleFont", style_font="TextFont", typeface="group", scale_set=True`). Операция пишет обе записи, отчёт сообщает,
    что проверено, и подсказывает, что нужно задать, чтобы изменить вид ячейки в режиме показа. Для любой записи «Авто» с
    переопределением у вложенного элемента отчёт добавляет предупреждение (`ROUND10_AUTO_WARNING`), но не отказывает.

    `form=True` — шрифт САМОЙ формы (строка «Шрифт» палитры формы; `element`, `column` и `nested` не называют). Запись та же,
    что у элементов, и правка идёт теми же параметрами. Шрифт формы действует на все элементы с шрифтом «Авто», поэтому отчёт
    сообщает, у скольких подписей (надпись, флажок, кнопка) после правки не хватает ширины. Платформа проверяла одну правку —
    абсолютный Arial 13 полужирный из «Авто»; прочие записи формы стоят на образцах форм
    (`CORPUS_FORM_FONT_RECORDS`, `ON_CORPUS["set_font/form"]`).

    Проверка `validate` уровня 2 иногда сообщает о длине записи иначе. Операция определяет границу по всем образцам, а проверка —
    по конкретному адресу, и для редкого адреса без достаточного числа образцов эти ответы расходятся. Например, три шрифта
    колонки с одним переопределением дают запись длины 6, а у поля текстового документа образцов мало. Длину записи определяет
    число переопределений, поэтому предупреждение остаётся верным.
    """
    if form:
        if element is not None or column is not None or nested:
            raise EditError("form=true — шрифт самой формы; element, column и nested здесь не называют: у формы один "
                            "шрифт, у элемента и колонки — свой")
        if font != "font":
            raise EditError(f"у формы один шрифт, `font`, а не {font!r}")
        record, kind, name, whose = form_font_record(doc), FORM_KIND, "font", "формы"
    elif element is None:
        raise EditError("назовите element (элемент формы) либо form=true (шрифт самой формы)")
    else:
        record, kind, name, whose = _font_record(doc, element, font, column, nested)
    overrides = record.get(OVERRIDES)
    was = record.get(FONT_SOURCE)
    if not isinstance(overrides, dict) and was != ABSOLUTE:
        raise EditError(f"запись шрифта {name!r} у {whose} не разобрана (нет {OVERRIDES!r}) — "
                        "править её именами нечем")
    absolute = was == ABSOLUTE or source == ABSOLUTE
    leaving = was == ABSOLUTE and source != ABSOLUTE and (reset or source is not None)
    if absolute and not leaving and reset:
        raise EditError(f"reset возвращает {AUTO!r}, а source={ABSOLUTE!r} задаёт абсолютный шрифт: назовите что-то одно")
    if leaving and reset and source not in (None, AUTO):
        raise EditError(f"reset возвращает {AUTO!r}, а source={source!r} просит другой вид: назовите что-то одно")
    if typeface not in TYPEFACE_WAYS:
        raise EditError(f"начертание пишут одним из двух способов: {', '.join(TYPEFACE_WAYS)} "
                        f"— а не {typeface!r}. Способ 'single' ставит ровно названные флаги (платформа "
                        "такую запись принимает), способ 'group' — все четыре флага сразу и насыщенность "
                        "явно (так пишет сама платформа: диалог держит одну галочку «Из стиля» "
                        "на всё начертание)")
    values = {"size10": None if size is None else _size10(size), "weight": _weight(bold),
              "italic": italic, "underline": underline, "strikeout": strikeout, "face": face}
    values = {key: value for key, value in values.items() if value is not None}
    for key, value in values.items():
        _font_value(key, value)
    asked = dict(values)
    with_reset = sorted(asked) + [name for name, value in
                                  (("source", source), ("style_font", style_font),
                                   ("system_font", system_font), ("scale", scale),
                                   ("scale_set", scale_set)) if value is not None]
    if leaving:
        given = [key for key, value in (("system_font", system_font), ("scale", scale), ("scale_set", scale_set)) if value is not None]
        draft, said = _fontabs.leave(record, kind, name, AUTO if reset else source, style_font, values, given, typeface,
                                     unverified)
        said = f"{whose}: шрифт {name!r} → возврат с абсолютного: {said}"
        said += _font_bounds(draft, kind, name, unverified, {})
        before = _fit_before(doc, element, column, nested, form)
        record.clear()
        record.update(draft)
        return said + _fit_words(before, doc, element, column, nested, form)
    if absolute:
        given = [key for key, value in (("style_font", style_font), ("system_font", system_font), ("scale", scale),
                                        ("scale_set", scale_set)) if value is not None]
        draft, said = _fontabs.build(record, was == ABSOLUTE, kind, name, values, given, typeface, unverified)
        said = f"{whose}: шрифт {name!r} → {said}"
        if kind == FORM_KIND:
            said += _on_corpus("set_font/form", "шрифт формы", 1)
        before = _fit_before(doc, element, column, nested, form)
        record.clear()
        record.update(draft)
        return said + _fit_words(before, doc, element, column, nested, form)
    if reset and with_reset:
        raise EditError("reset снимает переопределения ВСЕ и возвращает «Авто»; назвать его "
                        "вместе со значением значит попросить две разные правки — "
                        f"названо {', '.join(with_reset)}. Поставьте шрифт одним вызовом либо "
                        "сбросьте его отдельным")
    # Правится черновик записи, и только в конце он попадает в документ. При отказе документ должен остаться прежним, а границы
    # проверяются по готовой записи.
    draft = copy.deepcopy(record)
    if reset:
        draft.pop(FONT_REF, None)
        draft[FONT_SOURCE] = AUTO
        draft[OVERRIDES] = _order_overrides({SCALE_SET: False})
        said = f"{whose}: шрифт {name!r} → {AUTO} без переопределений"
    else:
        new = dict(overrides)
        new.update(values)
        if typeface == "group" and any(key in values for key in TYPEFACE_GROUP):
            for key, default in TYPEFACE_FILL.items():
                new.setdefault(key, default)
        if scale_set is not None:
            _font_value(SCALE_SET, scale_set)
            new[SCALE_SET] = scale_set
        # Бит 512 допустим только в версии 7. В версии 6 позиции масштаба нет, и без этой проверки операция запрещала бы писать
        # масштаб, но разрешала бы установить бит, который означает масштаб. Проверка стоит рядом с проверкой масштаба.
        if new.get(SCALE_SET) and draft.get(FONT_VERSION) != 7:
            raise EditError(
                f"{SCALE_SET} — бит про МАСШТАБ, а здесь запись версии "
                f"{draft.get(FONT_VERSION)}, у которой позиции масштаба нет вовсе (не ноль, а "
                "нет позиции). В образцах форм все записи с этим битом имеют версию 7, а у версии 6 их нет; поднять бит здесь значит собрать запись, "
                "которую платформа не пишет. Масштаб в этом случае тоже запрещён")
        target = source if source is not None else was
        if source is not None and source not in FONT_SOURCES:
            raise EditError(f"вида записи шрифта {source!r} карта не знает; есть "
                            f"{', '.join(FONT_SOURCES)}")
        _font_ref(draft, target, was, style_font, system_font)
        draft[FONT_SOURCE] = target
        draft[OVERRIDES] = _order_overrides(new)
        if scale is not None:
            _scale_value(scale)
            if draft.get(FONT_VERSION) != 7 or FONT_SCALE not in draft:
                raise EditError(
                    f"масштаб есть только у записи ВЕРСИИ 7, а здесь версия "
                    f"{draft.get(FONT_VERSION)}: у версии 6 позиции под масштаб нет вовсе — не "
                    "ноль, а нет позиции. Так во всех записях образцов форм, и `validate` "
                    "уровня 2 отвергает такую пару")
            draft[FONT_SCALE] = scale
        said = f"{whose}: шрифт {name!r} → " + _font_words(draft, values, typeface)
    tail = _font_bounds(draft, kind, name, unverified, asked)
    before = _fit_before(doc, element, column, nested, form)
    record.clear()
    record.update(draft)
    return said + tail + _fit_words(before, doc, element, column, nested, form)


def _caption_fit(doc, element, column, nested):
    """Возвращает `(подпись, нужно, есть, шрифт, проверен, причина)` для надписи, флажка или кнопки формы по действующему шрифту
    или `None`, если элемент не имеет подписи, это колонка или текста нет. Это одно измерение для отчёта «подпись перестала
    помещаться»: оно выполняется до правки и после неё.
    """
    if column is not None or nested:
        return None
    return _node_fit(doc, find_element(doc, element).element)


def node_fit(doc, node):
    """Измерение подписи узла после правки текста: `(подпись, нужно, есть, шрифт, проверен, причина)` или `None` (подписи нет или это не надпись, флажок, кнопка)."""
    return _node_fit(doc, node)


def new_text_words(fit):
    """Слова отчёта после правки текста подписи: помещается ли новый текст в ширину элемента. Пусто, если помещается или измерять нечего.

    Ширина элемента не меняется. Если шрифт не проверялся, нужная ширина — оценка, и отчёт говорит об этом."""
    if fit is None:
        return ""
    from .. import place
    text, need, have, font, exact, why = fit
    if need <= have:
        return ""
    shown = f"«{text}» шрифтом {place.font_words(font)}"
    if not exact:
        return (f"; подпись {shown} по оценке не помещается: нужно около {need} px, есть {have} (ширина по этому шрифту не проверялась: {why}) — "
                "в предприятии она может быть усечена «…»; размер элемента не менялся: ширину ставит move_element с box либо set_property")
    return (f"; подпись {shown} не помещается: нужно {need} px, есть {have} — в предприятии она усечена «…»; "
            "размер элемента не менялся: ширину ставит move_element с box либо set_property")


def _node_fit(doc, node):
    """То же измерение для узла элемента: `(подпись, нужно, есть, шрифт, проверен, причина)` или `None`."""
    from .. import render, textwidth
    kind = node.get("type")
    path = render.CAPTION_PATH.get(kind)
    coords = node.get(COORDS)
    if kind not in ("Label", "CheckBox", "Button") or not path or not isinstance(coords, dict):
        return None
    text = render._first_text(render._dig(node, *path))
    try:
        have = coords[WIDTH] - coords[X]
    except (KeyError, TypeError):
        return None
    if not text or not isinstance(have, int):
        return None
    pad = {"Label": 0, "CheckBox": render.CHECK_CAPTION_PAD, "Button": render.BUTTON_CAPTION_PAD}[kind]
    font = textwidth.element_font(node, doc)
    got = [textwidth.measure(line, font) for line in (text.splitlines() or [text])]
    need = pad + max(m.px for m in got)
    return text, need, have, font, all(m.exact for m in got), next((m.why for m in got if not m.exact), "")


def _form_fits(doc):
    """Измерения подписей всех элементов формы в порядке файла: `[(имя, измерение)]`; нужны для шрифта формы."""
    from .. import props
    from .base import name_of
    out = []
    for node in props.elements(doc):
        fit = _node_fit(doc, node)
        if fit is not None:
            out.append((name_of(node) or "?", fit))
    return out


def _fit_before(doc, element, column, nested, form):
    return _form_fits(doc) if form else _caption_fit(doc, element, column, nested)


def _fit_words(before, doc, element, column, nested, form):
    if not form:
        return _caption_words(before, _caption_fit(doc, element, column, nested))
    words = _form_caption_words(before, _form_fits(doc))
    record = form_font_record(doc)
    if isinstance(record, dict) and record.get("source") != "Absolute":
        words += ("; шрифт формы не абсолютный: элементы «Авто» его не наследуют (наследуют абсолютный шрифт формы), подписи "
                  "остались прежними")
    return words


def _form_caption_words(before, after):
    """Слова отчёта о шрифте формы: чьи подписи перестали помещаться (абсолютный шрифт формы действует на все элементы с «Авто»). Размеры
    элементов правка не меняет."""
    was = {i: fit for i, (_name, fit) in enumerate(before)}
    worse, still, unknown, reason = [], 0, 0, ""
    for i, (name, fit) in enumerate(after):
        _text, need, have, _font, exact, why = fit
        if not exact:
            unknown += 1
            reason = reason or why
            continue
        if need <= have:
            continue
        old = was.get(i)
        if old is not None and old[4] and old[1] <= old[2]:
            worse.append(name)
        else:
            still += 1
    out = ""
    if worse:
        out += (f"; подписи, которые перестали помещаться (абсолютный шрифт формы действует на элементы с «Авто»): {len(worse)} — "
                + ", ".join(worse[:8]) + (" и другие" if len(worse) > 8 else "")
                + "; размеры элементов правка не меняет (ширину ставит set_property, add_element или move_element с box)")
    if still:
        out += f"; не помещались и раньше: {still}"
    if unknown:
        out += f"; подписей, ширину которых по новому шрифту не проверить: {unknown} ({reason})"
    return out


def _caption_words(before, after):
    """Слова отчёта для случая, когда после смены шрифта подпись перестала помещаться. Размер элемента не меняется: правка шрифта
    элементы не сдвигает. Если подпись по новому шрифту не проверена, вывода о ней нет, и отчёт сообщает об этом.
    """
    if after is None:
        return ""
    from .. import place
    text, need, have, font, exact, why = after
    shown = f"«{text}» шрифтом {place.font_words(font)}"
    if not exact:
        return f"; подпись {shown} по новому шрифту не проверялась ({why}): помещается ли она в {have} px, неизвестно; размер элемента не менялся"
    if need <= have:
        return ""
    fitted = before is not None and before[4] and before[1] <= before[2]
    return (f"; подпись {shown} {'перестала помещаться' if fitted else 'не помещается'}: нужно {need} px, есть {have} — в предприятии она усечена «…»; "
            "размер элемента не менялся (правка шрифта элементы не двигает): ширину ставит add_element/move_element с box либо set_property")


def _size10(size):
    """Переводит размер из пунктов в десятые доли пункта, как он хранится в файле. Размер может быть дробным, например 6,5."""
    if isinstance(size, bool) or not isinstance(size, (int, float)):
        raise EditError(f"размер шрифта — число в ПУНКТАХ (12 значит 12 пунктов), а не {size!r}")
    value = round(size * 10)
    if abs(size * 10 - value) > 1e-9:
        raise EditError(f"размер {size} в файле лежит десятыми долями пункта, и {size * 10} "
                        "целым не выходит: мельче десятой пункта размера не бывает")
    if value <= 0:
        raise EditError(f"размер шрифта больше нуля, а не {size}")
    return value


def _scale_value(scale):
    """Масштаб — целое число процентов. Некорректное значение — это отказ операции, а не проверки. Верхнего предела нет: у
    неабсолютных записей встречается только значение 100, а любое другое отвергает соседняя проверка и называет это число.
    """
    if isinstance(scale, bool) or not isinstance(scale, int):
        raise EditError(
            f"масштаб — целое число процентов (100 значит «как есть»), а не {scale!r}. "
            f"В образцах форм у записей видов 1–3 он всегда равен {CORPUS_FONT_SCALE[0]}, и другое значение отвергается отдельной проверкой")
    if scale <= 0:
        raise EditError(f"масштаб больше нуля, а не {scale}")


def _font_value(key, value):
    """Вид значения определяет карта. Если значение не подходит, операция отказывает, а не оставляет сырой узел. Вид объявлен в
    таблице битов (`Masked.bits`); неподходящее значение сделало бы запись сырой, потому что у члена отрезка нет собственного
    адреса в JSON.
    """
    kind = FONT_KINDS[key]
    fits = {"bool": lambda v: isinstance(v, bool),
            "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "str": lambda v: isinstance(v, str)}[kind]
    if not fits(value):
        raise EditError(f"у переопределения {key!r} карта объявила вид {kind}, а пришло "
                        f"{value!r}: значение другого вида делает всю запись шрифта сырой — "
                        "своего адреса в JSON у него нет, и снять с него имя нечем")


def _weight(bold):
    """Насыщенность по галочке: 700 против 400. Других значений платформа в этом поле не пишет."""
    return None if bold is None else (700 if bold else 400)


def _font_ref(record, target, was, style_font, system_font):
    """Ссылка записи. У вида «Авто» её нет, а у двух остальных видов она своя и обязательна."""
    if target == AUTO:
        if style_font is not None or system_font is not None:
            raise EditError(f"у шрифта {AUTO!r} ссылки нет вовсе — ни на шрифт стиля, ни на "
                            "системный; уберите style_font/system_font либо назовите source")
        record.pop(FONT_REF, None)
        return
    named = {"StyleFont": (style_font, STYLE_FONT, STYLE_FONTS),
             "SystemFont": (system_font, SYSTEM_FONT, SYSTEM_FONTS)}
    wrong = [f"{key}={value!r}" for kind, (value, key, _codes) in named.items()
             if value is not None and kind != target]
    if wrong:
        raise EditError(f"при source={target!r} ссылка называется иначе: {', '.join(wrong)} "
                        f"здесь ни при чём — у {target!r} своя ссылка, и она одна")
    value, key, codes = named[target]
    if value is None:
        if was == target and isinstance(record.get(FONT_REF), dict):
            return  # вид не менялся: ссылка остаётся прежней
        if len(codes) == 1:
            value = next(iter(codes))
        else:
            raise EditError(
                f"при source={target!r} надо назвать {key}: карта знает "
                f"{', '.join(codes)} — это шрифты из списка диалога «Выбор шрифта». "
                "Выбрать один за вас нельзя: в образцах форм их пять, и палитра показывает разные")
    if value not in codes:
        raise EditError(f"{key}={value!r} карта не знает; есть {', '.join(codes)}"
                        + ("" if key != SYSTEM_FONT else
                           ". Ниже в списке диалога стоят «OEM моноширинный…» и «ANSI "
                           "моноширинный…», но их номеров не мерил никто, и выдуманных имён "
                           "им здесь нет"))
    ref = {key: value}
    if FONT_REF in record:
        record[FONT_REF] = ref
    else:
        _put_after(record, FONT_REF, ref, OVERRIDES)


def _put_after(node, key, value, after):
    """Ставит ключ на своё место в объекте: сразу после названного (JSON читают глазами и сверяют диффом)."""
    items = list(node.items())
    at = [name for name, _v in items].index(after) + 1
    node.clear()
    node.update(items[:at] + [(key, value)] + items[at:])


def _font_words(record, values, typeface):
    """Отчёт о правке шрифта: вид, ссылка, что переопределено и каким способом задано начертание."""
    ref = record.get(FONT_REF)
    said = str(record.get(FONT_SOURCE))
    if isinstance(ref, dict):
        said += " (" + ", ".join(f"{key}={value!r}" for key, value in ref.items()) + ")"
    overrides = record[OVERRIDES]
    shown = ", ".join(f"{key} {_short(overrides[key])}" for key in overrides)
    said += f"; переопределено: {shown}; маска {font_word(overrides)}"
    # Способ записи отчёт называет по фактически записанному, а не по одному параметру; унаследованные биты перечисляются по именам.
    if any(key in values for key in TYPEFACE_GROUP):
        here = [key for key in TYPEFACE_GROUP if key in overrides]
        kept = [key for key in here if key not in values]
        if typeface == "group":
            said += "; начертание ЧЕТЫРЬМЯ битами разом — так пишет сама платформа"
        elif kept:
            said += (f"; начертание записано ОДНИМ битом, а в записи их {len(here)}: прежние "
                     "явные значения сохранены — "
                     + ", ".join(f"{key} {_short(overrides[key])}" for key in kept))
        else:
            said += "; начертание одним битом — платформа такую запись принимает"
    if isinstance(ref, dict) and STYLE_FONT in ref and len(ref) > 1:
        said += ("; у ссылки на шрифт стиля осталась вторая позиция — пара «0 плюс GUID», "
                 "которую платформа не показала ни разу")
    return said


def _font_bounds(record, kind, name, unverified, asked):
    """Описывает, насколько вызов шире проверенного платформой. Пометки и отказы формируются здесь, в одном месте.

    Границ три: чей это шрифт, сочетание «версия записи + вид + маска» и значения размера с именем шрифта. Первые две
    относятся к форме записи, и непроверенные случаи отвергаются. Третья относится к содержимому строки и числа, и отказ там был
    бы утверждением о платформе без оснований.

    Числа в отказах относятся к неабсолютным записям, потому что абсолютные операция не пишет вовсе.
    """
    tail = ""
    place = (kind, name)
    if kind.startswith("ColumnControl."):
        # Вложенный элемент колонки: граница своя, и слова свои.
        nested = (kind[len("ColumnControl."):], name)
        seen = CORPUS_CONTROL_FONT_PLACES.get(nested)
        if seen is None and not unverified:
            raise EditError(f"шрифта {name!r} у вложенного элемента {nested[0]} в образцах форм нет: "
                            "у вложенных элементов колонок шрифт один, `font`. "
                            "Чтобы всё же выполнить операцию, передайте unverified=True")
        what = f"шрифт {name!r} вложенного {nested[0]}"
        # У вложенного поля ввода запись «Авто» с битом сохраняется, но в режиме редактирования не действует. Запись диалога
        # действует. Это не отказ: отчёт сообщает об этом словами (для остальных записей и видов то же знание содержится в тексте
        # варианта `set_font/control`).
        ref = record.get(FONT_REF) if isinstance(record.get(FONT_REF), dict) else {}
        key = ((record.get(FONT_VERSION), record.get(FONT_SOURCE), font_word(record[OVERRIDES])),
               ref.get(STYLE_FONT))
        note = ROUND10_FONT_RECORDS.get(key) if nested == ROUND10_FONT else None
        tail += f"; {what}: {note}" if note else _on_corpus("set_font/control", what, seen)
        if record.get(FONT_SOURCE) == AUTO and font_word(record[OVERRIDES]):
            tail += f"; {ROUND10_AUTO_WARNING}"
    elif kind == FORM_KIND:
        # Шрифт самой формы: адрес один, и граница своя — запись по образцам форм (`CORPUS_FORM_FONT_RECORDS`), платформа
        # проверяла одну правку, её слова — `ON_CORPUS["set_font/form"]`.
        shape = (record.get(FONT_VERSION), record.get(FONT_SOURCE),
                 font_word(record[OVERRIDES]) if isinstance(record.get(OVERRIDES), dict) else None)
        tail += _on_corpus("set_font/form", "шрифт формы",
                           CORPUS_FORM_FONT_RECORDS.get(shape) or (1 if record.get(FONT_SOURCE) == ABSOLUTE else None))
    elif place != ROUND7_FONT_PLACE:
        seen = CORPUS_FONT_PLACES.get(place)
        if seen is None and not unverified:
            known = ", ".join(f"{a}.{b}" for (a, b), count
                              in sorted(CORPUS_FONT_PLACES.items(), key=lambda kv: -kv[1])[:5])
            raise EditError(
                f"шрифта {name!r} у элемента вида {kind} в образцах форм нет: "
                f"записи шрифта лежат по двадцати двум адресам, "
                f"чаще всего {known}. Шрифт проверялся только у надписи, поэтому такую запись не "
                "подтверждают ни платформа, ни образцы форм. Чтобы всё же выполнить операцию, передайте unverified=True")
        tail += _on_corpus("set_font/place", f"шрифт {name!r} у {kind}", seen)
    triple = (record.get(FONT_VERSION), record.get(FONT_SOURCE), font_word(record[OVERRIDES]))
    said = f"запись «{triple[1]} с маской {triple[2]}» версии {triple[0]}"
    if triple not in ROUND7_FONT_RECORDS:
        seen = CORPUS_FONT_RECORDS.get(triple)
        if seen is None and not unverified:
            near = ", ".join(str(word) for version, source, word
                             in sorted(CORPUS_FONT_RECORDS, key=lambda t: -CORPUS_FONT_RECORDS[t])
                             if (version, source) == (triple[0], triple[1]))
            raise EditError(
                f"{said} не встречается в образцах форм и не проверялась на платформе: среди "
                "неабсолютных записей бывает пятьдесят сочетаний «версия, вид, маска», а у "
                f"{triple[1]} версии {triple[0]} встречаются маски {near or '—'}. Маска — это "
                "набор переопределённых свойств, и новое сочетание платформа, скорее всего, "
                "примет, но подтвердить это нечем. Чтобы всё же выполнить операцию, передайте "
                "unverified=True; результат придётся проверить самостоятельно")
        tail += _on_corpus("set_font/record", said, seen)
    if record.get(FONT_SCALE) is not None and record[FONT_SCALE] != CORPUS_FONT_SCALE[0] \
            and not unverified:
        raise EditError(
            f"масштаб {record[FONT_SCALE]} в образцах форм не встречается: у неабсолютных записей версии 7 он "
            f"всегда равен {CORPUS_FONT_SCALE[0]}, и диалог показывает «Масштаб: 100 %». Свойство у платформы есть "
            "(у абсолютного шрифта масштаб лежит своей позицией и меняется), но записи видов 1–3 с "
            "другим масштабом не подтверждены ни платформой, ни образцами форм. "
            "Чтобы всё же выполнить операцию, передайте unverified=True")
    for param, table, what in (("face", CORPUS_FONT_FACES, "имя шрифта"),
                               ("size10", CORPUS_FONT_SIZES, "размер")):
        value = record[OVERRIDES].get(param)
        if param in asked and value is not None and value not in table:
            tail += _on_corpus("set_font/value", f"{what} {value!r}", None)
    return tail
