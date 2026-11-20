"""Связь по типу. Все имена доступны через фасад `frm_codec.edit`."""

import copy

from .. import schema, props, json0

from .names import (
    BIND_ELEMENT,
    BIND_PATH,
    COLUMN_CONTROL,
    CONTENT,
    CONTROL_LINKS,
    CORPUS_STAMP,
    PATH_STEPS,
    STEP_VALUE,
    _at,
    _run,
)
from .base import EditError, _on_corpus, find_element
from .platform import ROUND11_NOTE
from .elements import TYPE_LINK, TYPE_LINK_ITEMS
from .columns import column_control
from .formroot import _guid_like
from .cowrites import _bindings


# Связь по типу

# Запись «Связь по типу» поля ввода имеет вид `{1, счётчик, {0, <GUID вида ссылки>, {2, счётчик, шаги…}}}` (узлы `TypeLink`,
# `TypeLinkEntry`, `TypeLinkPath`). Шаги пути такие же, как у привязки данных. У поля ввода формы это путь к реквизиту
# (`{id реквизита формы},{0,GUID реквизита объекта}`), а у вложенного поля ввода колонки — путь к полю строки таблицы
# (`{-2},{индекс табличного поля},{0},{0,GUID}`).
TYPE_LINK_GUID = "c866d8e7-76ff-4334-9d02-144f1efe5e1d"

TYPE_LINK_PATH = _at("TypeLinkEntry", 2, "TypeLinkPath")
TYPE_LINK_STEPS = _run("TypeLinkPath", schema.Counted)
# Строения пути, которые встречаются в образцах форм (`CORPUS_STAMP`). Запись всегда одна и та же: `{0, c866d8e7-…, путь}`, и
# нулевая позиция равна нулю и у поля формы, и у вложенного поля колонки. Операция пишет её так же. В соседнем списке `links`
# колонки нулевая позиция может быть и единицей: это другие записи (`CORPUS_NESTED_LINK_TWINS`). Шаги названы по виду: `id` —
# числовой идентификатор (реквизита формы или индекса элемента), `0+GUID` — реквизит объекта по GUID из метаданных, `-2` —
# «элемент формы», `0` — ноль, `код` — отрицательное число вместо GUID (стандартный реквизит строки: -6, -7).
CORPUS_TYPE_LINKS = {
    ("TextBox", "id,0+GUID"): 59, ("TextBox", "-2,id,0,0+GUID"): 3,
    ("ColumnControl.TextBox", "-2,id,0,0+GUID"): 93, ("ColumnControl.TextBox", "-2,id,0,код"): 12,
    ("ColumnControl.TextBox", "-2,id,0,0"): 1,
}
# Проверено в предприятии: связь `{id реквизита},{0,GUID}` у поля ввода формы работает, тип поля следует за реквизитом.
EXP_TYPE_LINK = (
    "такую запись конфигуратор пишет сам, а в 1С:Предприятии окно выбора типа предлагает только типы "
    "связанного реквизита, очистка даёт пустое значение его типа, а значение при смене типа приводит "
    "только обработчик ПриИзменении (ПривестиЗначение). " + ROUND11_NOTE
    + ": для связи, собранной редактором, палитра показывает «ТипЗнач», как у соседнего поля, созданного платформой, "
    "а в предприятии при ТипЗнач = Число окно выбора типа предлагает только «Число» — тоже как у "
    "соседнего поля")
# Связь вложенного поля ввода записана в файле дважды: в содержимом поля (`type_link`) и такой же записью в списке связей самой
# колонки (`TableBoxColumn.Control/links`). Запись с нулевой позицией 0 в `links` колонки побайтно равна записи в содержимом и
# стоит в списке последней. Записей с нулём без связи в содержимом и связей без такой записи не бывает. Записи с единицей —
# другие, их смысл не установлен, и операция их не меняет. У поля ввода формы дублирующей записи нет.
CORPUS_NESTED_LINK_TWINS = {"связей": 106, "близнецов": 106, "последних": 106, "сирот": 0}
TWIN_MARK = 0  # нулевая позиция записи-дубликата


def _link_shape(steps):
    """Строение пути по видам шагов: `id,0+GUID`, `-2,id,0,0+GUID` и т. д. Ключ — `CORPUS_TYPE_LINKS`."""
    out = []
    for at, step in enumerate(steps):
        values = list(step.values()) if isinstance(step, dict) else [step]
        if len(values) == 2 and isinstance(values[1], dict):
            out.append("0+GUID")
        elif len(values) == 1 and isinstance(values[0], int) and not isinstance(values[0], bool):
            number = values[0]
            if number == -2:
                out.append("-2")
            elif number < 0:
                out.append("код")
            elif number == 0 and at > 0:
                out.append("0")
            else:
                out.append("id")
        else:
            out.append("?")
    return ",".join(out)


def set_type_link(doc, element, attribute=None, column=None, nested=False, path=None,
                  unverified=False):
    """«Связь по типу» поля ввода: у поля формы или у вложенного поля ввода колонки.

    Запись ссылается на реквизит, тип которого определяет тип поля. Связанный реквизит можно указать тремя способами, и во всех
    случаях получается путь данных, такой же, как у привязки:

    * `attribute` — имя элемента формы, который показывает нужный реквизит; берётся путь его привязки;
    * `attribute` — GUID реквизита объекта; у поля формы путь `{id основного реквизита},{0,GUID}`, у вложенного поля колонки —
      `{-2},{индекс табличного поля},{0},{0,GUID}`;
    * `path` — шаги целиком, как в файле (`[{"u0": 1}, {"u0": 0, "u1": {"guid": …}}]`).

    `attribute=None` и `path=None` снимают связь: «Связь по типу» становится пустой.

    У вложенного поля связь записывается парой (`CORPUS_NESTED_LINK_TWINS`): в содержимое поля и такой же записью последней в
    список связей колонки (`control/links`). Прежний дубликат (запись с нулевой позицией 0) заменяется, а записи с единицей
    остаются. Снятие связи удаляет оба места.

    Граница проверенного — строение пути (`CORPUS_TYPE_LINKS`). Если строение не встречалось, операция отказывает, а
    `unverified=True` отказ снимает. Если GUID реквизита не показывает ни одно поле формы, сверить его не с чем, и отчёт сообщает
    об этом.
    """
    place = find_element(doc, element)
    control = None
    if nested:
        if column is None:
            raise EditError("nested=true — это вложенный элемент КОЛОНКИ: назовите column")
        head, kind, content = column_control(doc, element, column)
        anchor = props.NESTED_ANCHOR + kind
        whose = f"вложенного элемента ({kind}) колонки {column!r} поля {element!r}"
        control = head[COLUMN_CONTROL]
        if not isinstance(control.get(CONTROL_LINKS), list):
            raise EditError(f"у колонки {column!r} поля {element!r} нет списка связей "
                            f"({COLUMN_CONTROL}/{CONTROL_LINKS}); у вложенных "
                            "элементов он всегда есть, и связь вложенного поля лежит и в нём. "
                            "Возможно, документ правили вручную.")
    elif column is not None:
        raise EditError("связь по типу бывает у поля ввода: у колонки её нет, она есть у её "
                        "вложенного элемента. Укажите column и nested=true")
    else:
        kind, content = place.element.get("type"), place.element.get(CONTENT) or {}
        anchor, whose = kind, f"элемента {element!r} ({kind})"
    link = content.get(TYPE_LINK) if isinstance(content, dict) else None
    if not isinstance(link, dict) or not isinstance(link.get(TYPE_LINK_ITEMS), list):
        raise EditError(f"У {whose} связи по типу нет: она бывает только у поля ввода (формы и "
                        "вложенного в колонку); у элементов другого вида такого блока не бывает")
    if attribute is not None and path is not None:
        raise EditError("связанный реквизит указывается одним способом: attribute (имя элемента или "
                        "GUID) либо path (шаги), но не обоими сразу")
    was = link[TYPE_LINK_ITEMS]
    was_shape = _link_shape(((was[0].get(TYPE_LINK_PATH) or {}).get(TYPE_LINK_STEPS) or [])
                            if was and isinstance(was[0], dict) else [])
    if attribute is None and path is None:
        link[TYPE_LINK_ITEMS] = []
        return (f"{whose}: связь по типу снята" + (f" (была {was_shape})" if was else
                                                  " (её и не было)") + _put_twin(control, None))
    said = ""
    if path is not None:
        if not isinstance(path, list) or not all(isinstance(step, dict) for step in path):
            raise EditError("path — список шагов, как в файле: [{\"u0\": 1}, {\"u0\": 0, \"u1\": "
                            "{\"guid\": …}}]")
        steps = copy.deepcopy(path)
        said = "путь задан шагами"
    elif _guid_like(attribute):
        guid = {"guid": attribute}
        if nested:
            steps = [{STEP_VALUE: -2}, {STEP_VALUE: place.index}, {STEP_VALUE: 0},
                     {STEP_VALUE: 0, "u1": guid}]
            said = f"путь строки табличного поля #{place.index} к полю {attribute}"
        else:
            steps = [{STEP_VALUE: _main_step(doc, whose)}, {STEP_VALUE: 0, "u1": guid}]
            said = f"путь основного реквизита к реквизиту {attribute}"
        if not _guid_shown(doc, attribute):
            said += ("; реквизита с этим GUID не показывает ни одно поле формы — сверить его с "
                     "метаданными формой не из чего")
    else:
        if nested:
            raise EditError("у вложенного поля колонки связанный реквизит называют GUID-ом поля "
                            "строки (или path): пути к полю табличной части по имени элемента "
                            "форма не хранит")
        steps = _bound_path(doc, attribute, whose)
        said = f"путь данных элемента {attribute!r}"
    shape = _link_shape(steps)
    seen = CORPUS_TYPE_LINKS.get((anchor, shape))
    if not nested and shape == "id,0+GUID":
        tail = f"; строение {shape}: {EXP_TYPE_LINK}"
    elif seen is not None:
        tail = _on_corpus("set_type_link/path", f"строение {shape}", seen)
    elif unverified:
        tail = _on_corpus("set_type_link/path", f"строение {shape}", None)
    else:
        known = ", ".join(s for (a, s) in CORPUS_TYPE_LINKS if a == anchor)
        raise EditError(f"связь со строением пути {shape} у {anchor} в образцах форм не встречается; "
                        f"встречаются {known or 'никакие'}. Чтобы всё же выполнить "
                        "операцию, передайте unverified=True")
    entry = {"u0": TWIN_MARK, "u1": {"guid": TYPE_LINK_GUID},
             TYPE_LINK_PATH: {"u0": 2, TYPE_LINK_STEPS: steps}}
    link[TYPE_LINK_ITEMS] = [entry]
    return (f"{whose}: связь по типу → {said}" + (f" (была {was_shape})" if was else "")
            + _put_twin(control, entry) + tail)


def _put_twin(control, entry):
    """Дубликат связи вложенного поля в списке связей колонки. Если задан `entry`, он ставится последним, а прежний дубликат
    удаляется; если `None`, дубликат убирается. Записи с нулевой позицией 1 остаются на своих местах. Результат — хвост
    отчёта; для поля формы (`control is None`) он пуст.
    """
    if control is None:
        return ""
    links = control[CONTROL_LINKS]
    kept = [item for item in links if not (isinstance(item, dict)
                                           and item.get("u0") == TWIN_MARK)]
    gone = len(links) - len(kept)
    control[CONTROL_LINKS] = kept + ([copy.deepcopy(entry)] if entry is not None else [])
    others = f"; записей с единицей рядом — {len(kept)}, не тронуты" if kept else ""
    if entry is None:
        return (f"; близнец связи в списке связей колонки ({COLUMN_CONTROL}/{CONTROL_LINKS}) "
                f"{'убран' if gone else 'не стоял'} — связь вложенного поля живёт парой, и без "
                f"связи близнеца платформа не пишет{others}")
    return (f"; та же запись — последней в списке связей колонки ({COLUMN_CONTROL}/"
            f"{CONTROL_LINKS}){', прежний близнец заменён' if gone else ''}: у вложенного поля "
            f"связь лежит парой — близнец побайтно "
            f"равен связи и стоит последним{others}")


def _bound_path(doc, name, whose):
    """Шаги привязки элемента `name`: путь к реквизиту, который он показывает."""
    place = find_element(doc, name)
    rows = [row for row in _bindings(doc) if row.get(BIND_ELEMENT) == place.index]
    if not rows:
        raise EditError(f"у элемента {name!r} привязки данных нет — связать {whose} не с чем. "
                        "Назовите элемент, который показывает нужный реквизит, GUID реквизита "
                        "или path")
    steps = (rows[0].get(BIND_PATH) or {}).get(PATH_STEPS)
    if not isinstance(steps, list) or not steps:
        raise EditError(f"путь привязки элемента {name!r} не разобран — взять его нечем")
    return copy.deepcopy(steps)


def _main_step(doc, whose):
    """Первый шаг пути к реквизиту объекта — тот, через который идут привязки формы. Карта основной реквизит не называет, а путь
    привязки называет: `{id},{0,GUID}`. Если у разных привязок первые шаги различаются, операция отказывает: какой реквизит
    формы нужен, решает человек (параметр `path`).
    """
    first = {json0.dumps_line(row.get(BIND_PATH, {}).get(PATH_STEPS, [None])[0])
             for row in _bindings(doc)
             if len((row.get(BIND_PATH) or {}).get(PATH_STEPS) or []) == 2
             and isinstance(row[BIND_PATH][PATH_STEPS][1], dict)
             and "u1" in row[BIND_PATH][PATH_STEPS][1]}
    if len(first) != 1:
        raise EditError(f"первый шаг пути к реквизиту объекта у {whose} взять неоткуда: привязок "
                        f"«реквизит формы → реквизит объекта» в форме {'нет' if not first else 'с разным началом: ' + ', '.join(sorted(first))}. "
                        "Назовите элемент, показывающий нужный реквизит, или path")
    step = json0.loads(first.pop())
    return step.get(STEP_VALUE) if isinstance(step, dict) else step


def _guid_shown(doc, guid):
    for row in _bindings(doc):
        for step in (row.get(BIND_PATH) or {}).get(PATH_STEPS) or []:
            if isinstance(step, dict) and (step.get("u1") or {}).get("guid") == guid:
                return True
    return False
