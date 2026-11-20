"""Сравнение двух деревьев по адресам позиций и поиск элементов по имени.

Адрес — это кортеж индексов от корня сравниваемого узла. Блок сравнивается как ("LIST", число потомков), скаляр — как есть.
Если позиции нет с одной из сторон, вместо значения используется None. Элемент формы определяется по блоку имени
{14,"<имя>",…}: элементом считается родитель этого блока.

У подэлемента (колонки табличного поля, кнопки командной панели, страницы панели) такого блока нет, а имя лежит обычным
скаляром внутри его блока. Подэлемент находят две функции вместе: `find_scalar` возвращает все адреса имени, а
`sibling_container` по ряду соседних копий с такими же именами определяет блок копии.
"""
from dataclasses import dataclass
from .json0 import decode0
from .tree import Node, Scalar, get, walk, path_str


@dataclass(frozen=True)
class Change:
    path: tuple
    old: object
    new: object


def _flatten(node):
    out = {}
    for path, item in walk(node):
        out[path] = ("LIST", len(item.children)) if isinstance(item, Node) else item
    return out


def diff(a, b):
    fa, fb = _flatten(a), _flatten(b)
    changes = []
    for path in sorted(set(fa) | set(fb), key=lambda p: (len(p), p)):
        if fa.get(path) != fb.get(path):
            changes.append(Change(path, fa.get(path), fb.get(path)))
    return changes


def name_block_index(element):
    """Индекс блока имени {14,"<имя>",…} среди потомков элемента или None, если такого блока нет. Этот признак общий для всего
    навыка: по нему определяется и сам элемент (`find_named`), и его соседи, потому что блок координат стоит непосредственно
    перед именем.
    """
    if not isinstance(element, Node):
        return None
    for i, child in enumerate(element.children):
        if not isinstance(child, Node) or len(child.children) < 2:
            continue
        first, second = child.children[0], child.children[1]
        if first == Scalar("INT", "14") and isinstance(second, Scalar) and second.kind == "STR":
            return i
    return None


def find_named(root, prefix):
    found = {}
    for path, item in walk(root):
        i = name_block_index(item)
        if i is None:
            continue
        name = item.children[i].children[1].text
        if name.startswith(prefix):
            found[name] = (path, item)
    return found


def find_scalar(root, text):
    """Адреса всех строковых скаляров с заданным текстом. Учитываются только строки: число 8 и строка "8" — разные значения формата."""
    return [path for path, item in walk(root)
            if isinstance(item, Scalar) and item.kind == "STR" and item.text == text]


def _names_under(block_path, paths, names):
    n = len(block_path)
    return {names[p] for p in paths if len(p) > n and p[:n] == block_path}


def sibling_container(root, paths):
    """Преобразует адрес имени в адрес блока копии, которой это имя принадлежит.

    Блок копии — это ближайший предок имени, у родителя которого не меньше двух блоков-потомков, и в каждом из них ровно одно имя
    из заданных. Копий всегда не меньше двух, потому что базовая пара обязательна. Имена сравниваются по тексту, а не по адресу,
    потому что имя одной копии встречается в её блоке несколько раз.

    Если такого блока нет, операция отказывает и называет имя. Единственная копия в форме (базовая пара не создана)
    неотличима от повреждения формата.
    """
    paths = list(paths)
    if not paths:
        raise ValueError("адресов имён не дано: искать копии не по чему")
    names = {}
    for path in paths:
        item = get(root, path)
        if not isinstance(item, Scalar):
            raise ValueError(f"по адресу {path_str(path)} лежит блок, а не имя копии")
        names[path] = item.text
    known = ", ".join(sorted(set(names.values())))
    found = {}
    for path in paths:
        block = _copy_block(root, path, paths, names)
        if block is None:
            raise ValueError(
                f"имя {names[path]} ({path_str(path)}): блока копии нет — ни один его предок не "
                f"стоит в ряду, где не меньше двух блоков и в каждом ровно одно из имён "
                f"({known}); при единственной копии сравнивать не с чем — поставьте базовую пару")
        found[path] = block
    return found


def _copy_block(root, path, paths, names):
    for depth in range(len(path) - 1, 0, -1):
        block = path[:depth]
        parent_path = path[:depth - 1]
        parent = get(root, parent_path)
        siblings = [parent_path + (i,) for i, child in enumerate(parent.children)
                    if isinstance(child, Node)]
        marked = [s for s in siblings if len(_names_under(s, paths, names)) == 1]
        if len(marked) >= 2 and block in marked:
            return block
    return None


def _json_value(item):
    """Значение изменения для журнала и для печати.

    `None` в `base` и `exp` означает, что с этой стороны адреса не было. Пустое значение файла (`EMPTY`, на уровне 0 — `null`)
    передаётся своей обёрткой `{"empty": ""}`: `null` выглядел бы как отсутствие адреса, а `""` совпал бы со строкой нулевой длины.
    """
    if item is None:
        return None
    if isinstance(item, Scalar) and item.kind == "EMPTY":
        return {"empty": ""}
    if isinstance(item, tuple):
        return {"list": item[1]}
    if item.kind == "INT":
        return int(item.text)
    if item.kind == "DEC":
        return {"dec": item.text}
    if item.kind == "B64":
        # Используется тот же `decode0`, что на уровне 0, чтобы учесть признак раскладки. Иначе правка, которая изменила только
        # раскладку блока, печаталась бы как два одинаковых значения.
        return decode0(item)
    if item.kind == "GUID":
        return {"guid": item.text}
    return item.text


def change_dict(change):
    return {"path": path_str(change.path), "base": _json_value(change.old), "exp": _json_value(change.new)}
