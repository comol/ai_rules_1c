"""Строки палитры, которые лежат вне обычного поля узла: список выбора поля выбора и порядок обхода (`tab_order` — позиция `L6+2`).

Обе записи идут через `set_property` (имена `choice_list` и `tab_order`): отдельной операции у них нет. Вход — `write`; он
возвращает отчёт либо `None`, если имя не его.
"""
import copy

from .. import templates
from .base import EditError, find_element

CHOICE_LIST = "choice_list"
TAB_ORDER = "tab_order"
NAMES = (CHOICE_LIST, TAB_ORDER)
# Версии записи поля выбора, у которых блок списка имеет вид шаблона (метка 9, хвост из двух нулей). У версии 21 метка 8 и
# хвоста нет: такой блок редактор не строит.
CHOICE_RECORD_VERSIONS = (29, 30)
# Виды значения строки списка, которые писала платформа: строка, число, булево.
CHOICE_VALUE_KINDS = ("S", "N", "B")
LANGUAGE = "ru"


def write(doc, element, name, value, unverified=False):
    """Свойство `choice_list` или `tab_order` элемента формы; `None` — имя не из этой пары."""
    if name not in NAMES:
        return None
    place = find_element(doc, element)
    if name == TAB_ORDER:
        return _set_tab_order(place, element, value, unverified)
    return _set_choice_list(place, element, value)


# ── Порядок обхода ───────────────────────────────────────────────────────────────────────────

def auto_tab_order(holder):
    """Флаг «АвтоПорядокОбхода» родителя: у формы — в списке раскладки, у панели — в блоке содержимого; `None` — флага в документе нет."""
    for path in (("layout_holder", "layout_list"), ("content", "u1")):
        node = holder
        for key in path:
            node = node.get(key) if isinstance(node, dict) else None
        flag = node.get("auto_tab_order") if isinstance(node, dict) else None
        if isinstance(flag, bool):
            return flag
    return None


def _set_tab_order(place, element, value, unverified=False):
    """Порядок обхода (позиция `L6+2` блока координат): элемент встаёт на место `value` (с единицы) среди элементов своего родителя
    и своей страницы; элементы страницы получают номера 1…N по новому порядку. При АвтоПорядокОбхода родителя — отказ: номера ведёт
    платформа по положению, «Порядок обхода…» в конфигураторе тоже отказывает; `unverified` пишет номера всё равно."""
    from . import elements as ee
    if isinstance(value, bool) or not isinstance(value, int):
        raise EditError(f"tab_order у {element!r}: порядок обхода — поле блока координат (`L6+2`), и его задают целым — номером элемента среди элементов "
                        f"страницы родителя, считая с единицы (1 — первый), а пришло {value!r}")
    coords = place.element[ee.COORDS]
    group = [item for item in place.items if isinstance(item, dict)
             and isinstance(item.get(ee.COORDS), dict) and item[ee.COORDS].get(ee.PAGE) == coords.get(ee.PAGE)]
    if not 1 <= value <= len(group):
        raise EditError(f"tab_order у {element!r}: на странице {len(group)} элементов, место от 1 до {len(group)}, а пришло {value}")
    auto = auto_tab_order(place.holder)
    if auto and not unverified:
        where = "формы" if "layout_holder" in place.holder else "панели"
        raise EditError(f"tab_order у {element!r}: у {where} включён АвтоПорядокОбхода — платформа ведёт порядок по положению элементов, а "
                        "конфигуратор при нём отказывает («Невозможно изменить порядок, так как установлено свойство автопорядок обхода»); "
                        "сначала `set_property` `auto_tab_order` = false у этого родителя, либо unverified — номера запишутся, но платформа "
                        "может пересчитать их по положению")
    ordered = sorted((item for item in group if item is not place.element), key=lambda item: item[ee.COORDS].get(ee.TAB_ORDER) or 0)
    was = sorted(group, key=lambda item: item[ee.COORDS].get(ee.TAB_ORDER) or 0).index(place.element) + 1
    ordered.insert(value - 1, place.element)
    for number, item in enumerate(ordered, 1):
        item[ee.COORDS][ee.TAB_ORDER] = number
    tail = ("; у родителя включён АвтоПорядокОбхода, платформа может пересчитать номера по положению (unverified)" if auto else "")
    if was == value:
        return f"порядок обхода {element!r}: место {value} уже было; номера страницы заново 1…{len(group)}{tail}"
    return (f"порядок обхода {element!r}: место {was} → {value} среди {len(group)} элементов страницы; номера страницы заново 1…{len(group)} "
            "по новому порядку (как платформа нумерует при перестановке в диалоге «Настройка порядка обхода…»; "
            f"как пойдёт Tab в предприятии по этой записи, платформа не проверяла){tail}")


# ── Список выбора ────────────────────────────────────────────────────────────────────────────

def _row_value(spec, number, element):
    """Значение строки: `{"kind": …, "value": …}` из скаляра или готового объекта."""
    raw = spec.get("value") if isinstance(spec, dict) and "kind" not in spec else spec
    if isinstance(raw, dict):
        kind, payload = raw.get("kind"), raw.get("value")
    elif isinstance(raw, bool):
        kind, payload = "B", raw
    elif isinstance(raw, int):
        kind, payload = "N", raw
    elif isinstance(raw, str):
        kind, payload = "S", raw
    else:
        raise EditError(f"choice_list у {element!r}: у строки {number} значение — строка, целое или булево, а пришло {raw!r}")
    checks = {"S": isinstance(payload, str), "N": isinstance(payload, int) and not isinstance(payload, bool),
              "B": isinstance(payload, bool)}
    if kind not in CHOICE_VALUE_KINDS or not checks[kind]:
        raise EditError(f"choice_list у {element!r}: у строки {number} значение {raw!r} не подходит; "
                        f"платформа писала строку (S), число (N) и булево (B); дата и прочие виды не проверялись")
    return {"kind": kind, "value": payload}


def _row_parts(value, element):
    """Строки списка выбора как `[(значение `{"kind", "value"}`, представление или `None`)]`: вся проверка строк, одна на `set_property choice_list`,
    `add_element` и ключ `choice_list` описания `generate` (`check_rows`). Не список, значение не строка/целое/булево, представление не строка — `EditError`."""
    if not isinstance(value, list):
        raise EditError(f"choice_list у {element!r}: список выбора задаётся списком строк (скаляр или {{\"value\": …, \"presentation\": …}}), "
                        f"а пришло {value!r}")
    out = []
    for number, spec in enumerate(value):
        text = spec.get("presentation") if isinstance(spec, dict) and "kind" not in spec else None
        if text is not None and not isinstance(text, str):
            raise EditError(f"choice_list у {element!r}: у строки {number} представление — строка, а пришло {text!r}")
        out.append((_row_value(spec, number, element), text))
    return out


def check_rows(value, element):
    """Виды значений строк списка выбора (`S`, `N`, `B`) по порядку строк; ошибка строки — `EditError` теми же словами, что у `set_property`."""
    return [kind_value["kind"] for kind_value, _text in _row_parts(value, element)]


def _set_choice_list(place, element, value):
    """Список выбора поля выбора: блок списка значений собирается по шаблону, строки — по образцу строки.

    Значение — список строк; строка — скаляр либо объект `{"value": …, "presentation": "…"}`. Пустой список убирает блок.
    Номер текущей строки блока платформа ставит последним (`n − 1`), редактор пишет так же."""
    node = place.element
    if node.get("type") != "ComboBox":
        raise EditError(f"choice_list — список выбора ПОЛЯ ВЫБОРА, а {element!r} — {node.get('type')}")
    if not isinstance(value, list):
        raise EditError(f"choice_list у {element!r}: список выбора задаётся списком строк (скаляр или {{\"value\": …, \"presentation\": …}}), "
                        f"а пришло {value!r}")
    props_block = node["content"]["u1"]
    if props_block.get("record_version") not in CHOICE_RECORD_VERSIONS:
        raise EditError(f"choice_list у {element!r}: версия записи поля выбора {props_block.get('record_version')}; блок списка построен "
                        f"по записям версий {CHOICE_RECORD_VERSIONS}, у прочих он другой (у версии 21 метка 8 и нет хвоста) и не строится")
    pattern = templates.load("choice-list")
    block, sample = pattern["block"], pattern["row"]
    rows = []
    for number, (kind_value, text) in enumerate(_row_parts(value, element)):
        row = copy.deepcopy(sample)
        row["index"] = number
        row["value"] = kind_value
        row["presentation"]["u2"] = [1, LANGUAGE, text] if text else [0]
        rows.append(row)
    had = len(props_block["choice_list"][0]["u2"]["rows"]["items"]) if props_block.get("choice_list") else 0
    if not rows:
        props_block["choice_list"] = []
        return f"список выбора {element!r}: убран (было строк {had})"
    block["u2"]["rows"] = {"mark": 1, "count": len(rows), "items": rows}
    block["u2"]["u8"] = len(rows) - 1
    props_block["choice_list"] = [block]
    kinds = sorted({row["value"]["kind"] for row in rows})
    return (f"список выбора {element!r}: строк {had} → {len(rows)}, значения вида {', '.join(kinds)}; блок собран по записи платформы "
            "(строки со значением и представлением, номер текущей строки — последняя)" + (
                "; число и булево платформа писала сама, а строку проверяли заполнением списка в диалоге; в предприятии список, "
                "собранный редактором, не проверялся" if kinds != ["S"] else "; в предприятии список, собранный редактором, не проверялся"))
