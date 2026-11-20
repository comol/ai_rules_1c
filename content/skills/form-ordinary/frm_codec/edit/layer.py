"""Слой поля географической схемы: перенос из формы-образца (`copy_layer`).

Слой платформа заводит только импортом файла SHP (диалог «Настройка слоев»). Запись слоя лежит в записи элемента `u3` в трёх местах, и перенос берёт их вместе:

| Место | Что в нём |
|---|---|
| `u3/u2/0/0` | счётчик номеров: слой, серии данных, объекты и их значения получают номера подряд; у поля без слоёв 1, у поля с одним слоем в три точки 9 |
| `u3/u2/1/0…3` | область данных слоёв: первая координата точек от и до, вторая от и до (границы области — `u3/u2/8…11` — выбираются внутри неё) |
| `u3/u2/1/4`, `u3/u2/1/5` | число слоёв и запись слоя: номер, имя, область слоя, видимость, масштабы, GUID, серии данных, объекты с геометрией, значения серий |

Запись самодостаточна: ссылок на другие места формы и на метаданные в ней нет, номера внутри неё выдержаны от 2 до счётчика. Поэтому её переносят как есть, а не пересобирают.
Граница переноса — снятое платформой: у образца ровно один слой, у приёмника слоёв нет (с двумя слоями номера и порядок записей не сняты). Строка палитры «Слои» пишется
только этой операцией; ПоддержкаМасштаба, границы области и СмещениеДолготы — отдельные строки (`set_property`), операция их не трогает.
"""
import copy
import pathlib

from .base import EditError, find_element
from ..json0 import dumps
from .. import schemarows

SHAPE = "запись элемента не того строения, какое снято у платформы 8.3.27: "


def _geo(doc, element, what):
    node = find_element(doc, element).element
    if node.get("type") != schemarows.GEO:
        raise EditError(f"{what} {element!r} — {node.get('type')}, а слои бывают у поля географической схемы ({schemarows.GEO})")
    try:
        u2 = node["u3"]["u2"]
        counter, area = u2[0][0], u2[1]
        if not (isinstance(counter, int) and isinstance(area, list) and len(area) >= 6):
            raise TypeError
    except (KeyError, IndexError, TypeError):
        raise EditError(f"{what} {element!r}: {SHAPE}нет счётчика номеров слоя (`u3/u2/0/0`) или области данных (`u3/u2/1`)") from None
    return node, u2


def _donor_layer(u2, element, source):
    counter, area = u2[0][0], u2[1]
    layers, record = area[4], area[5]
    if layers != 1 or not isinstance(record, list) or not record:
        raise EditError(f"у образца {element!r} формы {source} слоёв {layers!r}, запись слоя {'есть' if record else 'пуста'}: переносится ровно один слой "
                        "(у двух слоёв порядок записей и номера не сняты)")
    if record[0] != 2 or not isinstance(record[1], str) or counter < 2:
        raise EditError(f"запись слоя образца {element!r} {SHAPE}номер слоя {record[0]!r} (ждали 2), имя {record[1]!r}, счётчик {counter!r}")
    extent = [schemarows._decimal(value) for value in area[:4]]
    own = [schemarows._decimal(value) for value in record[3:7]]
    if extent != own:
        raise EditError(f"область данных образца {element!r} не равна области слоя в его записи ({extent} против {own}): запись не того строения, слой не переносится")
    guid = next((item["guid"] for item in record if isinstance(item, dict) and "guid" in item), None)
    return counter, area, record, guid


def copy_layer(doc, element, source, from_element, unverified=False):
    """Слой поля географической схемы `from_element` формы `source` (путь к `form.frm`) — полем `element` этой формы.

    Переносятся запись слоя, область данных слоёв, число слоёв и счётчик номеров (`u3/u2/0/0`, `u3/u2/1/0…5`); ПоддержкаМасштаба, границы области и СмещениеДолготы не
    трогаются — это строки `set_property`. У образца обязан быть ровно один слой, у приёмника — ни одного. Слой с тем же GUID, что уже есть в этой форме, переносится только
    с `unverified`: повтор GUID слоя платформа не выдавала.
    """
    from .. import typed
    from ..tree import read_file
    path = pathlib.Path(source)
    if not path.is_file():
        raise EditError(f"source: файла формы-образца {source!r} нет; нужен путь к form.frm формы, где слой завела платформа")
    donor_doc = typed.decode(read_file(path))
    _donor_node, donor_u2 = _geo(donor_doc, from_element, "образец")
    counter, area, record, guid = _donor_layer(donor_u2, from_element, source)
    node, u2 = _geo(doc, element, "элемент")
    mine = u2[1]
    if u2[0][0] != 1 or mine[4] or mine[5]:
        raise EditError(f"у {element!r} уже есть слой (число слоёв {mine[4]}, счётчик номеров {u2[0][0]}): номера слоя, серий и объектов общие для всех слоёв поля, и как слить два "
                        "набора, платформа не показывала; слой переносится в поле без слоёв")
    if guid and not unverified and f'"{guid}"' in dumps(doc):
        raise EditError(f"слой с GUID {guid} в форме уже есть: платформа повтор GUID слоя не выдавала. Если перенос нужен, позвать можно — unverified=True, — и тогда результат "
                        "проверяете вы")
    u2[0][0] = counter
    mine[:4] = copy.deepcopy(area[:4])
    mine[4] = 1
    mine[5] = copy.deepcopy(record)
    series = record[15] if isinstance(record[15], int) else "?"
    return (f"поле географической схемы {element!r}: слой {record[1]!r} перенесён с {from_element!r} формы {path.name}: запись слоя (серий {series}), область данных "
            f"{[str(value) for value in area[:4]]}, число слоёв 1, счётчик номеров {counter} (позиции u3/u2/0/0, u3/u2/1/0…5); ПоддержкаМасштаба, границы области и СмещениеДолготы "
            "не менялись — их ставит set_property; запись слоя взята как есть у платформы, открытие перенесённого слоя в платформе не проверялось")
