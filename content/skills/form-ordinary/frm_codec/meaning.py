"""Смысловой дифф: сравнение двух форм по именам из карты без шума, который создаёт платформа.

Команда `frm_json.py diff` сравнивает деревья по адресам. Для формы с командной панелью такое сравнение шумит: при каждой
выгрузке платформа выдаёт кнопкам новые GUID и переставляет записи действий в списке, поэтому даже копия без правок
показывает десятки отличий.

Смысловой дифф разбирает обе формы по карте (уровень 1) и заменяет GUID кнопки устойчивым именем «панель/набор/имя кнопки».
Записи действий выстраиваются в порядке этих имён, и затем сравниваются деревья JSON. В результате остаются только те
изменения, которые сделал человек.

Позиционный дифф смысловой не заменяет. Он не печатает адреса, а печатает путь по ключам JSON. Позиции, которым карта не
дала имени, сравниваются под запасными именами (`u7`, `L1+0`). Формы, строение которых карта не разбирает, сравниваются как
сырые узлы (`raw`), и их разница видна целым куском.

Что считается одной кнопкой. Ключ кнопки состоит из четырёх частей: путь элементов до панели, номер набора, имя кнопки и,
если в наборе есть кнопки с одинаковым именем, порядковый номер среди них. Кнопки с одинаковым именем сравниваются по
положению в наборе.

Кнопку и её запись действия связывает один и тот же GUID (`id` у обеих). Поэтому переименование ключа переносится на записи
действий: после него список действий сортируется по ключу и не зависит от порядка при выгрузке.

Списки с устойчивым ключом сравниваются по ключу: лишний член называется целиком (`MISSING` с одной стороны). Если ключ есть
не у всех членов списка, список сравнивается по положению (`_keyed`).

GUID кнопки бывает неоднозначным: в редких формах две кнопки (разделители в разных наборах одной панели) имеют один GUID.
Ключ закрепляется за первой найденной кнопкой, потому что порядок обхода устойчив; последняя кнопка его не переписывает.

Имена из карты (`actions`, `button_sets`, `buttons`, `id`, `name`, `name_block`) запрашиваются у самой карты (`_names`). Если
бы они были записаны здесь, переименование отрезка в карте молча вернуло бы сравнение к позиционному.
"""
from . import schema, typed
from .json0 import dumps_line
from .tree import read_file

BUTTON = "BTN"
# Условное имя последнего члена пути в строке про порядок членов списка. Оно записано по-русски, чтобы его нельзя было
# спутать с ключом документа.
ORDER = "порядок"


def _names():
    """Имена из карты, на которых основано переименование: два счётных списка блока действий, список кнопок набора и его ключ, имя
    кнопки, блок имени элемента и имя внутри него. Обёртка `{"guid": …}` сюда не входит: это запись скаляра уровня 0.
    """
    actions, button_sets = (segment.name
                            for segment in schema.MAP["CommandBarActions"].runs.segments)
    buttons = schema.MAP["ButtonSet"].runs.segments[0]
    button_name = schema.MAP["Element.CommandBarButton"].fields[1].name
    name_block = next(slot.name for slot in schema.MAP["Element.CommandBar"].fields.values()
                      if isinstance(slot, schema.N) and slot.type == "NameBlock")
    element_name = schema.MAP["NameBlock"].fields[1].name
    return (actions, button_sets, buttons.name, buttons.key, button_name,
            name_block, element_name)


NAMES = _names()


def _bars(doc):
    """Блоки действий командных панелей, где бы они ни лежали, вместе с путём имён до них. Блок находится по строению: его узнают по
    паре ключей `actions` и `button_sets`. Путь состоит из имён элементов, внутри которых лежит блок, сверху вниз.
    """
    actions, button_sets, _buttons, _key, _button_name, name_block, element_name = NAMES

    def walk(value, trail):
        if isinstance(value, dict):
            name = (value.get(name_block) or {}).get(element_name)
            here = trail + (name,) if isinstance(name, str) else trail
            if actions in value and button_sets in value:
                yield here, value
            for item in value.values():
                yield from walk(item, here)
        elif isinstance(value, list):
            for item in value:
                yield from walk(item, trail)
    yield from walk(doc, ())


def _keys(doc):
    """Заменяет GUID кнопки устойчивым именем. Кнопкам с одинаковым именем в наборе добавляется порядковый номер. Повторный GUID
    ключ не переписывает: он закрепляется за первой найденной кнопкой.
    """
    _actions, button_sets, buttons_key, id_key, button_name, _nb, _en = NAMES
    out = {}
    for trail, block in _bars(doc):
        for s, button_set in enumerate(block.get(button_sets) or []):
            if not isinstance(button_set, dict):
                continue
            seen = {}
            for button in button_set.get(buttons_key) or []:
                if not isinstance(button, dict) or not isinstance(button.get(id_key), dict):
                    continue
                guid = button[id_key].get("guid")
                name = button.get(button_name) if isinstance(button.get(button_name), str) \
                    else "?"
                seen[name] = seen.get(name, 0) + 1
                tail = "" if seen[name] == 1 else f"#{seen[name]}"
                out.setdefault(guid, f"{BUTTON}:{'/'.join(trail)}:{s}:{name}{tail}")
    return out


def canon(doc):
    """Документ, в котором вместо GUID кнопок стоят устойчивые имена, а записи действий упорядочены."""
    keys = _keys(doc)

    def rename(value):
        if isinstance(value, dict):
            if set(value) == {"guid"} and value["guid"] in keys:
                return {"guid": keys[value["guid"]]}
            return {key: rename(item) for key, item in value.items()}
        if isinstance(value, list):
            return [rename(item) for item in value]
        return value

    doc = rename(doc)
    actions_key = NAMES[0]
    for _trail, block in _bars(doc):
        actions = block.get(actions_key)
        if isinstance(actions, list):
            # Ключ сортировки — переименованный `id`. У записи без кнопки остаётся GUID, и такие записи собираются в конце в порядке
            # своих значений.
            block[actions_key] = sorted(actions, key=_order)
    return doc


def _order(action):
    id_key = NAMES[3]
    guid = (action.get(id_key) or {}).get("guid") if isinstance(action, dict) else None
    named = isinstance(guid, str) and guid.startswith(BUTTON + ":")
    # `bools=True`, потому что запись действия содержит флаги уровня 1.
    return (0 if named else 1, guid or "", dumps_line(action, bools=True))


def changes(left, right, path=(), out=None):
    """Возвращает различия двух разобранных форм как список `(путь ключей, было, стало)`.

    Если ключа с одной из сторон нет, это `MISSING`, а не `None`: `None` означает «пустое значение файла».

    Списки сравниваются по положению, кроме списков с устойчивым ключом (`_keyed`). Для них сравнение идёт по ключу, а лишние
    члены называются целиком. Иначе новые кнопки платформы вставали бы в середину упорядоченного списка и сдвигали остальные.
    """
    out = [] if out is None else out
    if isinstance(left, dict) and isinstance(right, dict):
        for key in list(left) + [key for key in right if key not in left]:
            if key not in left:
                out.append((path + (key,), MISSING, right[key]))
            elif key not in right:
                out.append((path + (key,), left[key], MISSING))
            else:
                changes(left[key], right[key], path + (key,), out)
    elif isinstance(left, list) and isinstance(right, list):
        keyed_left, keyed_right = _keyed(left), _keyed(right)
        if keyed_left is not None and keyed_right is not None:
            order = _order_changed(keyed_left, keyed_right)
            if order is not None:
                out.append((path + (ORDER,), order[0], order[1]))
            for key in list(keyed_left) + [k for k in keyed_right if k not in keyed_left]:
                if key not in keyed_left:
                    out.append((path + (key,), MISSING, keyed_right[key]))
                elif key not in keyed_right:
                    out.append((path + (key,), keyed_left[key], MISSING))
                else:
                    changes(keyed_left[key], keyed_right[key], path + (key,), out)
            return out
        for i in range(max(len(left), len(right))):
            if i >= len(left):
                out.append((path + (i,), MISSING, right[i]))
            elif i >= len(right):
                out.append((path + (i,), left[i], MISSING))
            else:
                changes(left[i], right[i], path + (i,), out)
    elif left != right:
        out.append((path, left, right))
    return out


def _order_changed(keyed_left, keyed_right):
    """Возвращает `(порядок слева, порядок справа)`, если общие члены идут в разном порядке, иначе `None`.

    У кнопок набора порядок означает порядок на экране слева направо, а сравнение по ключу про порядок ничего не говорит.
    Порядок сравнивается только по общим членам: добавленная или удалённая кнопка сдвигает позиции соседей, но не меняет их
    взаимный порядок.

    Печатается не весь ряд, а только расходящийся участок: общие начало и конец отрезаются.

    У записей действий порядок не важен: `canon` сортирует обе стороны по ключу.
    """
    left = [key for key in keyed_left if key in keyed_right]
    right = [key for key in keyed_right if key in keyed_left]
    if left == right:
        return None
    head = 0
    while head < len(left) and left[head] == right[head]:
        head += 1
    tail = 0
    while tail < len(left) - head and left[-1 - tail] == right[-1 - tail]:
        tail += 1
    cut = slice(head, len(left) - tail)
    return ([_short(key) for key in left[cut]], [_short(key) for key in right[cut]])


def _short(key):
    """Конец ключа — имя кнопки. В строке про порядок панель и набор повторять не нужно."""
    return key.rsplit(":", 1)[-1]


def _keyed(items):
    """Возвращает `{ключ: член}`, если у каждого члена списка есть устойчивый ключ, иначе `None`.

    Устойчивым считается только переименованный `id` (`BTN:…`) из `canon`, потому что платформа выдаёт сырой GUID заново при
    каждой выгрузке. Правило «всё или ничего» нужно, чтобы половина списка не сравнивалась по имени, а половина по положению.
    Список с повторяющимся ключом тоже сравнивается по положению.
    """
    id_key = NAMES[3]
    out = {}
    for item in items:
        if not isinstance(item, dict):
            return None
        key = (item.get(id_key) or {}).get("guid") if isinstance(item.get(id_key), dict) \
            else None
        if not isinstance(key, str) or not key.startswith(BUTTON + ":") or key in out:
            return None
        out[key] = item
    return out or None


class _Missing:
    """Значение «ключа с этой стороны не было» отличается и от `None`, и от пустого значения."""

    def __repr__(self):
        return "—"


MISSING = _Missing()


def compare(left_path, right_path):
    """Две формы с диска и их смысловые различия."""
    return changes(canon(typed.decode(read_file(left_path))),
                   canon(typed.decode(read_file(right_path))))


def show(value, width=110):
    """Значение для печати: JSON в одну строку, длинное значение заканчивается на «…».

    Используется тот же писатель, что и у позиционного диффа (`json0.dumps_line`). Печатается уровень 1, поэтому `bools=True`:
    булевы значения составляют половину документа, и без этого ключа режим отказывал бы при любом изменении флага.
    """
    if value is MISSING:
        return "—"
    text = dumps_line(value, bools=True)
    return text if len(text) <= width else text[:width] + "…"
