"""Уровень 1: дерево ⇄ типизированный JSON по карте формата.

Каждый скаляр дерева отображается ровно в одно поле JSON — именованное или `u<индекс>`. Поле `u…` нельзя
удалять: тогда теряется значение, и `encode` отказывает, называя позицию. Узел, тип которого карта не знает,
записывается полем `raw` в виде уровня 0 без потерь, а `validate` выдаёт предупреждение.

Имя в карте — результат наблюдений, а реальный файл может отличаться. Тогда позиция теряет имя, но не значение.
Например, карта называет `2/3/1/1/3` у поля ввода флагом `multi_line`, но у полей другого строения там лежит
GUID. Назвать GUID флагом неверно и опасно при записи: `multi_line: true` записал бы единицу туда, где форма
хранит ссылку. Поэтому при чтении такая позиция получает имя `u3` и значение уровня 0. То же относится к блоку
на позиции, которую карта называет скаляром (`mask`, `show_tabs`), и к скаляру на позиции, которую карта
называет блоком (`picture_size` у панелей).

Правило несимметричное: при чтении имя из карты не навязывается, при записи обязательно. Значение 7 под именем
`multi_line` записать нельзя, отказ называет адрес и значение. Обратное тоже проверяется: ключ `u3` там, где
значение подходит под имя из карты, — отказ.

Битовое слово — единственный случай, когда скаляр файла становится объектом JSON. Вид `bits` раскладывает слово
по именам флагов, а биты, которых журнал не называет, записываются полем `rest`. Это поле пишется всегда, даже
нулевое, иначе слово собралось бы другим числом. Обратно слово собирается сложением тех же масок, и проверка
обратным разбором сходится байт в байт. Если на этой позиции стоит блок или целое с ведущим нулём, имя из карты
снимается (как и у других имён), и позиция называется `u<индекс>`.

Отказ ловит дыру в позициях, но не любую пропажу. Карта не знает длин блоков, поэтому удаление последней позиции
неотличимо от блока, который законно короче; такую пропажу находит сверка с файлом, а не кодек.

`encode` перед выдачей разбирает собственный результат и сравнивает его с входом. Расхождение означает ошибку
кодека, а не пользователя.

Абстрактный тип карты (`Element`, `Layout`) разрешается в обе стороны: `decode` вызывает `schema.pick` по
дереву, `encode` — `schema.pick_doc` по словарю.
"""
from . import packed, schema
from .json0 import Dec, decode0, encode0
from .tree import Node, Scalar

RAW = "raw"


class TypedError(ValueError):
    pass


def _where(path):
    return "/".join(str(p) for p in path) if path else "корень"


# Подходит ли скаляр файла под вид, который карта объявила для этой позиции. Правило хранится в карте
# (`schema.fits_scalar`). Его используют разбор, раскладка (у значения отрезка по маске в JSON нет собственного
# адреса) и сверка зеркал в `validate`: ей нужно знать, применимо ли имя из карты к скаляру файла.
_fits = fits_scalar = schema.fits_scalar


def _is_block_doc(value):
    """Объект JSON, который представляет разбор блока, а не значение уровня 0.

    Обёртки `{"guid": …}`, `{"base64": …}` и `{"num": …}` тоже объекты, но это скаляры файла. У base64 обёртка
    бывает и с признаком раскладки, но это тот же скаляр."""
    return isinstance(value, dict) and set(value) not in (
        {"guid"}, {"base64"}, {"base64", "layout"}, {"num"})


def bits_to_json(slot, word):
    """Битовое слово файла → объект с именованными флагами и остаток.

    Остаток записывается всегда, даже нулевой: это часть слова, которую журнал не назвал, и без неё собралось бы
    другое число. Отрицательное слово считается тем же способом (`-5 & ~1` = `-6`, `-6 | 1` = `-5`)."""
    mask = 0
    out = {}
    for name, bit in slot.bits.items():
        out[name] = bool(word & bit)
        mask |= bit
    out[schema.BITS_REST] = word & ~mask
    return out


def bits_shape_error(slot, value):
    """Возвращает, чего не хватает значению JSON, чтобы быть этим битовым словом; `None` — всё на месте.

    Одна функция обслуживает чтение, запись и проверку."""
    if not isinstance(value, dict):
        return (f"поле {slot.name} — битовое слово, и пишут его объектом флагов "
                f"({', '.join(sorted(slot.bits))} и {schema.BITS_REST}), а пришло {value!r}")
    missing = [name for name in sorted(set(slot.bits) | {schema.BITS_REST}) if name not in value]
    if missing:
        return (f"поле {slot.name}: нет флагов " + ", ".join(missing)
                + " — слово собирается из всех разом, и пропущенный флаг уехал бы нулём")
    extra = sorted(set(value) - set(slot.bits) - {schema.BITS_REST})
    if extra:
        return (f"поле {slot.name}: флагов " + ", ".join(extra) + " карта не знает; "
                f"биты называет только она, а неназванные записываются в {schema.BITS_REST}")
    for name in sorted(slot.bits):
        if not isinstance(value[name], bool):
            return f"поле {slot.name}: флаг {name} булев, а пришло {value[name]!r}"
    rest = value[schema.BITS_REST]
    if not isinstance(rest, int) or isinstance(rest, bool):
        return f"поле {slot.name}: остаток {schema.BITS_REST} — целое, а пришло {rest!r}"
    mask = 0
    for bit in slot.bits.values():
        mask |= bit
    if rest & mask:
        return (f"поле {slot.name}: остаток {rest} задевает названные биты ({mask:#x}) — "
                "тогда их значение записалось бы дважды и по-разному")
    return None


def bits_from_json(slot, value):
    word = value[schema.BITS_REST]
    for name, bit in slot.bits.items():
        if value[name]:
            word |= bit
    return word


def fits_json(slot, value, path):
    """То же со стороны JSON: подходит ли значение под имя, которое карта дала позиции.

    Вопрос задаётся дважды: для ключа `u<индекс>` на позиции с именем (если значение подходит, разбор назовёт
    поле по карте) и для ключа с именем (ответ «нет» — отказ: имя обязательно). Имя функции публичное, потому
    что тот же вопрос задаёт `validate`, и у проверки и у записи ответ должен быть одним."""
    if slot.kind == schema.BITS:
        # Битовое слово проверяется первым: в JSON оно объект, и общая проверка ниже («объект — блок, а не
        # скаляр») отвергла бы его раньше, чем дошла бы до таблицы битов.
        return bits_shape_error(slot, value) is None
    if isinstance(value, list) or _is_block_doc(value):
        return False
    if isinstance(value, bool):
        return slot.kind == schema.BOOL
    if isinstance(value, str) and not isinstance(value, Dec):
        if slot.kind == schema.ENUM:
            enum = schema.ENUMS.get(slot.enum)
            return bool(enum) and value in enum.codes
        if slot.kind == schema.TYPE:
            return value in schema.ELEMENT_GUIDS
        if slot.kind == schema.GUID and getattr(slot, "names", None):
            return schema.guid_of_name(slot, value) is not None
    return _fits(slot, encode0(value, path))


def _scalar_to_json(slot, item):
    # Адреса у перевода нет намеренно: несовпадение значения с именем было обнаружено раньше, в `_fits`.
    if not _fits(slot, item):
        return decode0(item)
    if slot.kind == schema.BOOL:
        return item.text == "1"
    if slot.kind == schema.BITS:
        return bits_to_json(slot, int(item.text))
    if slot.kind == schema.ENUM:
        enum = schema.ENUMS.get(slot.enum)
        code = int(item.text)
        for name, value in (enum.codes.items() if enum else ()):
            if value == code:
                return name
        return decode0(item)  # код не установлен — остаётся числом
    if slot.kind == schema.TYPE:
        return schema.element_type_name(item.text)
    if slot.kind == schema.GUID and getattr(slot, "names", None):
        named = schema.guid_name(slot, item.text)
        if named is not None:
            return named
    return decode0(item)


def _json_to_scalar(slot, value, path):
    if slot is not None:
        if slot.kind == schema.BOOL:
            if not isinstance(value, bool):
                raise TypedError(f"{_where(path)}: поле {slot.name} булево, а пришло {value!r}")
            return Scalar("INT", "1" if value else "0")
        if slot.kind == schema.BITS:
            problem = bits_shape_error(slot, value)
            if problem:
                raise TypedError(f"{_where(path)}: {problem}")
            return Scalar("INT", str(bits_from_json(slot, value)))
        if slot.kind == schema.ENUM:
            enum = schema.ENUMS.get(slot.enum)
            if enum and isinstance(value, int) and not isinstance(value, bool):
                # Число, у которого есть имя, отвергается с этим именем: иначе разбор вернул бы имя, а проверка
                # обратным разбором объявила бы ошибкой кодека выбор автора JSON. Код без имени (палитра
                # неполна, `Enum.seen`) допускается числом.
                for known_name, code in enum.codes.items():
                    if code == value:
                        raise TypedError(f"{_where(path)}: у кода {value} перечисления "
                                         f"{slot.enum} есть имя {known_name!r} — его и пишут, "
                                         "иначе разбор вернёт не то, что записано")
            if isinstance(value, str) and not isinstance(value, Dec):
                # Перечень известных значений собирается отдельной строкой заранее, чтобы в отказе не оказалось
                # пустого текста.
                known = ("карта знает " + ", ".join(sorted(enum.codes))) if enum else \
                        f"перечисления {slot.enum} в карте нет вовсе"
                if not enum or value not in enum.codes:
                    raise TypedError(f"{_where(path)}: значения {value!r} у перечисления "
                                     f"{slot.enum} нет; {known}")
                return Scalar("INT", str(enum.codes[value]))
        if slot.kind == schema.TYPE and isinstance(value, str) and value in schema.ELEMENT_GUIDS:
            return Scalar("GUID", schema.ELEMENT_GUIDS[value])
        if slot.kind == schema.GUID and getattr(slot, "names", None) and isinstance(value, str) and not isinstance(value, Dec):
            guid = schema.guid_of_name(slot, value)
            if guid is None:
                raise TypedError(f"{_where(path)}: у типа {value!r} имени нет; карта знает "
                                 f"{', '.join(schema.GUID_NAMES[slot.names])}, любой другой тип пишут обёрткой {{\"guid\": …}}")
            return Scalar("GUID", guid)
        if slot.kind == schema.GUID and getattr(slot, "names", None) and isinstance(value, dict) and set(value) == {"guid"} \
                and isinstance(value["guid"], str) and schema.guid_name(slot, value["guid"]) is not None:
            raise TypedError(f"{_where(path)}: у типа {value['guid']} есть имя {schema.guid_name(slot, value['guid'])!r} — его и пишут, "
                             "иначе разбор вернёт не то, что записано")
        if not fits_json(slot, value, path):
            # Общий случай того же правила, что у булева значения и перечисления выше: имя обязательно.
            raise TypedError(f"{_where(path)}: поле {slot.name} карта объявила видом "
                             f"{slot.kind}, а пришло {value!r}; под этим именем пишут только "
                             f"то, что виду подходит, иначе разбор вернёт значение как u…")
    return encode0(value, path)


def _name_for(fallback, slot, child, path):
    """Имя поля JSON для позиции и слот, по которому переводится значение.

    Слот `None` означает «переносить уровнем 0»: карта либо не называет позицию, либо называет её не тем, что
    лежит в файле (имя снято).

    `fallback` — запасное имя позиции: `u<индекс>` в обычном блоке и `L<n>+<k>` там, где номер позиции меняется
    (счётные списки). Правило снятия имени одинаково для обоих.

    Скаляр на позиции повтора — единственный случай, когда имя не снимается, а выдаётся отказ: позиции повтора
    образуют диапазон, у списка JSON нет адресов, и скаляр посередине сдвинул бы каждого следующего на одну
    позицию."""
    if slot is None:
        return fallback, None
    if isinstance(child, Node):
        if isinstance(slot, (schema.N, schema.R)):
            return slot.name, slot
        return fallback, None
    if isinstance(slot, schema.R):
        raise TypedError(f"{_where(path)}: карта ждёт здесь узел списка {slot.name}, "
                         "а в файле скаляр; места для него в списке нет")
    if isinstance(slot, schema.N) or not _fits(slot, child):
        return fallback, None
    return slot.name, slot


def _name_at(node_type, index, child, path):
    """То же по числовому адресу — у узла без счётных списков."""
    return _name_for(f"u{index}", schema.slot_at(node_type, index), child, path + (index,))


def along_slot(segment):
    """Псевдослот члена парного отрезка: у члена нет собственного адреса, вид один на весь отрезок.

    Он создаётся здесь, а не в карте, потому что в карте у отрезка одно объявление на все члены. Имя члена снять
    нельзя, поэтому нецелое значение члена `schema.read_runs` отвергает раньше, и весь узел остаётся сырым."""
    return schema.F(segment.name, segment.kind, segment.source)


def pair_key_slot(segment):
    """Псевдослот ключа пары, по той же причине, что `along_slot`: вид один на весь список.

    Имя ключа тоже снять нельзя: `read_runs` отвергает пару, у которой ключ не того вида, и весь узел остаётся
    сырым."""
    return schema.F(segment.key, segment.key_kind, segment.source)


def _pair_from_json(segment, item, index, path):
    """Обратное преобразование: объект члена → `(узел, ключ)`. Ключ снимается первым, потому что `_encode_node`
    узнаёт сырой узел по единственному ключу `raw`."""
    if not isinstance(item, dict):
        raise TypedError(f"{_where(path + (index,))}: член списка {segment.name} — объект с "
                         f"полями узла {segment.type} и ключом {segment.key}, а пришло {item!r}")
    if segment.key not in item:
        raise TypedError(f"{_where(path + (index,))}: у члена списка {segment.name} нет поля "
                         f"{segment.key} — этим ключом он связан с записью действия, и взять "
                         "его больше неоткуда")
    rest = {key: value for key, value in item.items() if key != segment.key}
    key_at = schema.pair_key_index(index)
    return (_encode_node(rest, segment.type, path + (index,)),
            _json_to_scalar(pair_key_slot(segment), item[segment.key], path + (key_at,)))


def _pair_to_json(segment, node, index, path):
    """Член списка пар: поля узла и поле ключа в одном объекте.

    В файле ключ лежит перед узлом (`schema.pair_key_index`), а в JSON он помещается внутрь объекта узла: формат
    связывает «этот ключ — у этого узла». Сырой узел принимает ключ так же: `encode` снимает его до проверки на
    `raw`."""
    item = decode(node.children[index], segment.type, path + (index,))
    key_at = schema.pair_key_index(index)
    item[segment.key] = _scalar_to_json(pair_key_slot(segment), node.children[key_at])
    return item


def decode(node, type_name="Form", path=()):
    # Пустой узел с выбором варианта остаётся нераскрытым: выбирать вариант не по чему, а у абстрактного типа
    # нет полей. Он записывается сырым без потерь.
    picked = schema.pick(type_name, node) if node.children else \
        (None if type_name in schema.ABSTRACT else type_name)
    if picked is None or picked not in schema.MAP:
        return {RAW: decode0(node)}
    node_type = schema.MAP[picked]
    if node_type.packed is not None:
        # Упакованный узел раскрывается в три позиции и дальше разбирается как обычный блок. Если раскрыть его
        # не удалось (заголовок не тот или сжатие не повторяет платформу), он остаётся сырым; причину сообщит
        # `validate`.
        try:
            node = packed.unpack_node(node)
        except packed.PackedError:
            return {RAW: decode0(node)}
    if node_type.runs is not None:
        return _decode_runs(node, node_type, path)
    out = {}
    repeat = []
    for i, child in enumerate(node.children):
        name, slot = _name_at(node_type, i, child, path)
        if isinstance(child, Node):
            if isinstance(slot, schema.R):
                repeat.append(decode(child, slot.type, path + (i,)))
            elif isinstance(slot, schema.N):
                out[name] = decode(child, slot.type, path + (i,))
            else:
                out[name] = decode0(child)
        else:
            out[name] = _scalar_to_json(slot, child) if slot else decode0(child)
    if node_type.repeat:
        out[node_type.repeat.name] = repeat
    return out


def _decode_runs(node, node_type, path):
    """Узел со счётными списками: раскладка вычисляется по самому файлу.

    Счётчик в JSON не попадает, потому что равен длине массива. Если строение не сошлось, узел остаётся сырым;
    `validate` предупреждает о сыром узле."""
    plan = schema.read_runs(node_type, node.children)
    if plan is None:
        return {RAW: decode0(node)}
    spots, lists = plan
    # Ключи собираются в порядке позиций файла, а не списками подряд, поэтому порядок в JSON повторяет порядок в
    # файле. Список ставится на позицию своего первого члена, а пустой — туда, где стоял бы счётчик.
    at = {}
    for segment, start, members in lists:
        if isinstance(segment, schema.Gated):
            # Блока может не быть совсем. Тогда в JSON нет ключа — ни пустого массива, ни `null`: массив обещал
            # бы список, которого у необязательного блока нет, а позиция `start` при отсутствии блока
            # принадлежит хвосту.
            if members:
                at[start] = (segment.name,
                             decode(node.children[start], segment.type, path + (start,)))
            continue
        if isinstance(segment, schema.Counted):
            value = [decode(node.children[i], segment.type, path + (i,)) for i in members]
        elif isinstance(segment, schema.CountedPairs):
            value = [_pair_to_json(segment, node, i, path) for i in members]
        elif isinstance(segment, schema.Flagged):
            names = segment.raised(int(node.children[start].text))
            value = {name: decode(node.children[i], segment.bits[name][1], path + (i,))
                     for name, i in zip(names, members)}
        elif isinstance(segment, schema.Masked):
            # Порядок ключей: сначала значения в порядке файла, затем биты без значения в порядке их объявления
            # в карте. У этих битов своего места в файле нет.
            word = int(node.children[start].text)
            value = {name: _scalar_to_json(schema.masked_slot(segment, name), node.children[i])
                     for name, i in zip(segment.raised(word), members)}
            value.update(segment.flags_of(word))
        else:
            slot = along_slot(segment)
            value = [_scalar_to_json(slot, node.children[i]) for i in members]
        at[start] = (segment.name, value)
    # Позиция вне блока сюда не попадает: `read_runs` вернула бы `None`.
    for index, (fallback, slot) in spots.items():
        child = node.children[index]
        name, slot = _name_for(fallback, slot, child, path + (index,))
        if isinstance(child, Node):
            value = decode(child, slot.type, path + (index,)) if isinstance(slot, schema.N) \
                else decode0(child)
        else:
            value = _scalar_to_json(slot, child) if slot else decode0(child)
        at[index] = (name, value)
    return {name: value for _index, (name, value) in sorted(at.items())}


def check_canonical_u(name, path):
    """Написание `u<индекс>` должно быть каноническим, без ведущих нулей; иначе отказ теми же словами.

    Проверка общая для обоих разборов ключа (`slot_for` и `slot_in_runs`). Ключ `u01` лёг бы на позицию 1,
    разбор вернул бы её как `u1`, и проверка обратным разбором объявила бы «ошибку кодека» вместо опечатки
    автора JSON."""
    digits = name[1:]
    if str(int(digits)) != digits:
        raise TypedError(f"{_where(path)}: ключ {name!r} не по форме u<число>: позиция "
                         f"пишется без ведущих нулей и обычными цифрами — u{int(digits)}")


def slot_for(node_type, type_name, by_name, name, value, path):
    """Позиция и слот по ключу JSON. Ключ, которого нет в карте, — отказ с его именем.

    Имя функции публичное: тем же разбором пользуется уровень 1 в `validate`, и отказы проверки и записи
    одинаковы.

    Ключ `u<индекс>` разбирается как позиция, а не поиском по именам: карта так же называет безымянные блоки
    (`u8` — и имя блока, и адрес снятого имени, `schema._place`). Два смысла различает значение: объект — блок
    карты, скаляр — перенос уровня 0.

    Написание имени каноническое, без ведущих нулей (`u01` — отказ)."""
    if name.startswith("u") and name[1:].isdigit():
        check_canonical_u(name, path)
        index = int(name[1:])
        named = schema.slot_at(node_type, index)
        if isinstance(named, schema.R):
            raise TypedError(f"{_where(path)}: позиция {index} — часть списка {named.name}; "
                             f"его узлы перечисляет он, а не поле {name}")
        return fallback_slot(index, named, name, value, path)
    if name in by_name:
        return by_name[name]
    raise TypedError(f"{_where(path)}: ключа {name!r} в карте узла {type_name} нет")


def fallback_slot(index, named, name, value, path):
    """Разбор запасного ключа позиции: `u<индекс>` и `L<n>+<k>` разбираются одним правилом.

    Правило нетривиально (безымянный блок карты называется тем же ключом; значение, подходящее под имя из карты,
    под запасным ключом — отказ), поэтому оно вынесено в одну функцию."""
    if isinstance(named, schema.N):
        if _is_block_doc(value):
            return index, named
        if isinstance(value, list):
            raise TypedError(f"{_where(path)}: позиция {index} названа картой блоком "
                             f"{named.type}; блок пишут объектом, списком уровня 0 его "
                             "разбор потом не признает")
        return index, None
    if named is not None and fits_json(named, value, path + (index,)):
        raise TypedError(f"{_where(path)}: позиция {index} названа картой — {named.name}, и "
                         f"это значение её виду подходит; имя {name} остаётся за тем, чего "
                         "карта в этом файле не узнаёт")
    return index, None


def slot_in_runs(places, type_name, name, value, path):
    """Позиция и слот по ключу JSON у узла со счётными списками.

    `places` — результат `schema.doc_runs`, разложенный по ключам: имя из карты и запасной ключ ведут к одной
    позиции. Функция парная к `slot_for`: здесь номер позиции вычисляется по спискам, и ключа, которого нет в
    раскладке, быть не может."""
    by_name, by_fallback = places
    # Запасной ключ проверяется первым: у безымянного блока карты имя и запасной ключ совпадают (`u0`), и при
    # проверке по имени скаляр на этой позиции попал бы в разбор блока. В `slot_for` порядок такой же.
    if name in by_fallback:
        index, named = by_fallback[name]
        return fallback_slot(index, named, name, value, path)
    if name in by_name:
        return by_name[name]
    if name.startswith("u") and name[1:].isdigit():
        check_canonical_u(name, path)
        raise TypedError(f"{_where(path)}: позиция {name} лежит за головой узла {type_name} — "
                         "дальше идут счётные списки, и номер позиции у каждой формы свой; "
                         "такие позиции зовут L<номер списка>+<смещение>")
    raise TypedError(f"{_where(path)}: ключа {name!r} в карте узла {type_name} нет")


def _encode_node(doc, type_name, path):
    if not isinstance(doc, dict):
        # JSON правят вручную, и блок в нём может оказаться числом или списком уровня 0. Без этой проверки
        # сборка падала бы с голым `TypeError` в глубине обхода, где адрес уже не виден.
        raise TypedError(f"{_where(path)}: карта ждёт здесь блок {type_name}, а пришло {doc!r}; "
                         "блок пишут объектом с полями")
    if set(doc) == {RAW}:
        return encode0(doc[RAW], path)
    # Выбор варианта на стороне JSON — пара к `pick` в `decode`.
    picked = schema.pick_doc(type_name, doc)
    if picked is None and type_name in schema.ABSTRACT:
        # Отказ называет выбор варианта, а не первый ключ: иначе `type: "Надпись"` (опечатка или русское имя)
        # выглядел бы как «ключа type в карте узла Element нет».
        raise TypedError(f"{_where(path)}: тип узла не опознан по значениям, которые его "
                         f"называют; карта знает {', '.join(schema.variants(type_name))}")
    type_name = picked or type_name
    node_type = schema.MAP.get(type_name)
    if node_type is None:
        raise TypedError(f"{_where(path)}: карта не знает типа узла {type_name}")
    if node_type.runs is not None:
        return _encode_runs(doc, node_type, type_name, path)
    by_name = {}
    for index, slot in node_type.fields.items():
        by_name[slot.name] = (index, slot)
    repeat_name = node_type.repeat.name if node_type.repeat else None
    children = {}
    for name, value in doc.items():
        if name == repeat_name:
            if not isinstance(value, list):
                # Те же слова, что в проверке (`validate._check_shape`): разные тексты об одной ошибке читались
                # бы как две ошибки. Без этой проверки `enumerate` падал бы с голым `TypeError`.
                raise TypedError(f"{_where(path)}: {name} — список узлов "
                                 f"{node_type.repeat.type}, а пришло {value!r}")
            for offset, item in enumerate(value):
                index = node_type.repeat.start + offset
                children[index] = _encode_node(item, node_type.repeat.type, path + (index,))
            continue
        index, slot = slot_for(node_type, type_name, by_name, name, value, path)
        if index in children:
            raise TypedError(f"{_where(path)}: позиция {index} занята дважды — ключом {name!r} и "
                             "соседним; у каждого значения файла ровно одно поле JSON")
        if isinstance(slot, schema.N):
            children[index] = _encode_node(value, slot.type, path + (index,))
        elif isinstance(value, (list, dict)) and slot is None:
            children[index] = encode0(value, path + (index,))
        else:
            children[index] = _json_to_scalar(slot, value, path + (index,))
    node = _close_node(children, path, lambda index: f"u{index}")
    if node_type.packed is not None:
        # Обратное преобразование к раскрытию в `decode`: три позиции карты складываются в конверт.
        try:
            return packed.pack_node(node, _where(path))
        except packed.PackedError as e:
            raise TypedError(str(e)) from None
    return node


def _close_node(children, path, key_of):
    """Дети блока по позициям → узел. Дыра посередине — отказ с именами пропавших позиций.

    Имя позиции передаёт вызывающий: у обычного блока это `u<индекс>`, у блока со счётными списками — ключ, под
    которым позиция стоит в раскладке (номер у каждой формы свой)."""
    if children and sorted(children) != list(range(max(children) + 1)):
        missing = [i for i in range(max(children) + 1) if i not in children]
        raise TypedError(f"{_where(path)}: нет полей на позициях "
                         + ", ".join(key_of(i) for i in missing)
                         + " — их значения взять неоткуда, а порядок детей блока держит формат")
    return Node([children[i] for i in sorted(children)])


def _encode_runs(doc, node_type, type_name, path):
    """Сборка узла со счётными списками: счётчики берутся из длин массивов.

    Обратное преобразование к `_decode_runs`; обе функции считают раскладку по одному правилу (`schema`)."""
    try:
        spots, lists = schema.doc_runs(node_type, doc)
    except schema.SchemaError as e:
        raise TypedError(f"{_where(path)}: {e}")
    by_name, by_fallback = {}, {}
    for index, (fallback, slot) in spots.items():
        by_fallback[fallback] = (index, slot)
        if slot is not None:
            by_name[slot.name] = (index, slot)
    runs = {segment.name: (segment, start, members) for segment, start, members in lists}
    children = {}
    for name, value in doc.items():
        if name in runs:
            segment, start, members = runs[name]
            counter = schema.counter_index(segment, start)
            if counter is not None:
                children[counter] = Scalar("INT", str(len(members)))
            if isinstance(segment, schema.Flagged):
                # Слово флагов собирается из ключей и не бывает полем JSON: два источника одних и тех же данных
                # недопустимы.
                picked = [bit for bit in segment.bits if bit in value]
                children[start] = Scalar("INT", str(segment.word(picked)))
                for index, bit in zip(members, picked):
                    children[index] = _encode_node(value[bit], segment.bits[bit][1],
                                                   path + (index,))
                continue
            if isinstance(segment, schema.Masked):
                # Слово маски собирается из двух источников: набор ключей даёт биты со значением, булевы поля —
                # биты без значения. Полем JSON само слово не бывает.
                picked = [bit for bit in segment.bits if bit in value]
                children[start] = Scalar("INT", str(segment.word(picked, value)))
                for index, bit in zip(members, picked):
                    children[index] = _json_to_scalar(schema.masked_slot(segment, bit),
                                                      value[bit], path + (index,))
                continue
            if isinstance(segment, schema.Gated):
                # У необязательного блока бывает одно место или ни одного. Это определяет флаг в голове блока, а
                # не документ: `doc_runs` уже отказала, если они не сходятся.
                for index in members:
                    children[index] = _encode_node(value, segment.type, path + (index,))
                continue
            if isinstance(segment, schema.CountedPairs):
                for index, item in zip(members, value):
                    children[index], children[schema.pair_key_index(index)] = \
                        _pair_from_json(segment, item, index, path)
                continue
            for index, item in zip(members, value):
                children[index] = _encode_node(item, segment.type, path + (index,)) \
                    if isinstance(segment, schema.Counted) \
                    else _json_to_scalar(along_slot(segment), item, path + (index,))
            continue
        index, slot = slot_in_runs((by_name, by_fallback), type_name, name, value, path)
        if index in children:
            raise TypedError(f"{_where(path)}: позиция {index} занята дважды — ключом {name!r} и "
                             "соседним; у каждого значения файла ровно одно поле JSON")
        if isinstance(slot, schema.N):
            children[index] = _encode_node(value, slot.type, path + (index,))
        elif isinstance(value, (list, dict)) and slot is None:
            children[index] = encode0(value, path + (index,))
        else:
            children[index] = _json_to_scalar(slot, value, path + (index,))
    def key_of(index):
        # Имя из карты, если оно есть: сообщение «нет поля L7+0» заставило бы искать безымянную позицию там, где
        # имя на месте. То же правило в проверке (`_check_gaps`).
        fallback, slot = spots.get(index, (f"u{index}", None))
        return slot.name if isinstance(slot, (schema.F, schema.N)) else fallback

    return _close_node(children, path, key_of)


def _coords_slot_names():
    """Имена полей, которыми карта называет блок `Coords` (сейчас одно — `coords`).

    Обход выполняет `schema.node_slots`, единый перечень для всего навыка: самодельный обход не видел бы
    `repeat` и `lead` отрезков."""
    names = set()
    for node_type in schema.MAP.values():
        names.update(slot.name for _addr, slot in schema.node_slots(node_type)
                     if isinstance(slot, schema.N) and slot.type == "Coords")
    return names


COORDS_SLOTS = _coords_slot_names()


def old_coords_places(value, path=()):
    """Все места документа, где край блока координат назван прежним именем (`width`, `height`): `[(адрес, слова)]`.

    Узел `Coords` держит края под именами `right` и `bottom`; прежние имена больше не читаются. Адрес — тот же путь,
    что и в словах отказа, но отдельным значением; прочие `width`/`height` (форма, колонка) тут ни при чём."""
    out = []
    if isinstance(value, list):
        for i, item in enumerate(value):
            out += old_coords_places(item, path + (i,))
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in COORDS_SLOTS and isinstance(item, dict):
                old = [name for name in schema.OLD_COORDS_NAMES if name in item]
                if old:
                    out.append((_where(path + (key,)), f"{_where(path + (key,))}: {'стоят' if len(old) > 1 else 'стоит'} {' и '.join(old)} — "
                                "старые имена координат больше не читаются: разберите форму заново из form.frm "
                                "(края блока называются right и bottom)"))
                if "L6+2" in item:
                    out.append((_where(path + (key,)), f"{_where(path + (key,))}: стоит L6+2 — старый JSON: позиция L6+2 называется `tab_order` "
                                "(порядок обхода), а прежнее поле `tab_order` позиции L6+1 — `page_sequence`, порядком обхода оно не является: "
                                "разберите форму заново из form.frm"))
            out += old_coords_places(item, path + (key,))
    return out


def old_field_places(value, path=(), strings=False):
    """Все места, где поле карты названо прежним именем (`schema.OLD_FIELD_NAMES`): `[(адрес, слова)]`.

    Ключ словаря с прежним именем — всегда; со `strings=True` ещё и строка, равная прежнему имени или заканчивающаяся им
    после косой черты (так называют поле `set_property` и адреса вида `u2/u0/allowed_sign`). Прежнее имя не читается
    никем: молчаливое чтение дало бы форму, которую платформа и карта называют иначе."""
    out = []

    def words(old, where):
        return (where, f"{where}: поле переименовано: `{old}` → `{schema.OLD_FIELD_NAMES[old]}` "
                       "(значение то же: true — неотрицательный); прежнее имя больше не читается")
    if isinstance(value, list):
        for i, item in enumerate(value):
            out += old_field_places(item, path + (i,), strings)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in schema.OLD_FIELD_NAMES:
                out.append(words(key, _where(path + (key,))))
            out += old_field_places(item, path + (key,), strings)
    elif strings and isinstance(value, str):
        for old in schema.OLD_FIELD_NAMES:
            if value == old or value.endswith("/" + old):
                out.append(words(old, _where(path)))
    return out


def refuse_old_coords(doc):
    """Документ как есть, если в нём нет прежних имён краёв; иначе `TypedError` словами на первом найденном месте.

    Общая застава `encode`, редактора и команд: молчаливое чтение старого имени дало бы форму, которую никто не
    разбирал."""
    found = old_coords_places(doc) + old_field_places(doc)
    if found:
        raise TypedError(found[0][1])
    return doc


def encode(doc, type_name="Form", check=True):
    refuse_old_coords(doc)
    node = _encode_node(doc, type_name, ())
    if check:
        again = decode(node, type_name)
        if again != doc:
            raise TypedError("ошибка кодека: разбор собственной сборки не совпал с входом "
                             f"({first_difference(doc, again)})")
    return node


def first_difference(a, b, path=()):
    """Адрес и значения первого расхождения двух документов словами, а не просто «не равны».

    Проверку обратным разбором выполняют два места: самопроверка `encode` (ошибка кодека) и уровень 3 в
    `validate` (ошибка документа)."""
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a or key not in b or a[key] != b[key]:
                if key in a and key in b:
                    return first_difference(a[key], b[key], path + (key,))
                return f"{'/'.join(map(str, path + (key,)))}: только с одной стороны"
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                return first_difference(x, y, path + (i,))
    return f"{'/'.join(map(str, path)) or 'корень'}: {a!r} против {b!r}"


def unknown_counts(root, type_name="Form", counts=None, path=()):
    """Сколько позиций у каждого типа узла осталось без имени — показатель полноты карты.

    Считается тем же `_name_at`, что вызывает `decode`: безымянной считается и позиция, у которой в карте нет
    имени, и позиция, у которой имя снято из-за несовпадения вида."""
    counts = counts if counts is not None else {}
    # Пустой узел с выбором варианта не раскрывается — по тому же правилу, что в `decode`: счётчик считает то,
    # что видно в JSON, а там такой узел остаётся сырым.
    picked = schema.pick(type_name, root) if root.children else \
        (None if type_name in schema.ABSTRACT else type_name)
    if picked is None or picked not in schema.MAP:
        counts[RAW] = counts.get(RAW, 0) + 1
        return counts
    node_type = schema.MAP[picked]
    if node_type.packed is not None:
        try:
            root = packed.unpack_node(root)
        except packed.PackedError:
            counts[RAW] = counts.get(RAW, 0) + 1
            return counts
    if node_type.runs is not None:
        plan = schema.read_runs(node_type, root.children)
        if plan is None:
            counts[RAW] = counts.get(RAW, 0) + 1
            return counts
        spots, lists = plan
        for segment, start, members in lists:
            if isinstance(segment, (schema.Counted, schema.CountedPairs, schema.Gated)):
                for i in members:
                    unknown_counts(root.children[i], segment.type, counts, path + (i,))
            elif isinstance(segment, schema.Flagged):
                names = segment.raised(int(root.children[start].text))
                for name, i in zip(names, members):
                    unknown_counts(root.children[i], segment.bits[name][1], counts, path + (i,))
        for i, (fallback, slot) in sorted(spots.items()):
            _name, slot = _name_for(fallback, slot, root.children[i], path + (i,))
            if slot is None:
                counts[picked] = counts.get(picked, 0) + 1
            elif isinstance(slot, schema.N):
                unknown_counts(root.children[i], slot.type, counts, path + (i,))
        return counts
    for i, child in enumerate(root.children):
        name, slot = _name_at(node_type, i, child, path)
        if slot is None:
            counts[picked] = counts.get(picked, 0) + 1
        if isinstance(child, Node) and isinstance(slot, (schema.N, schema.R)):
            unknown_counts(child, slot.type, counts, path + (i,))
    return counts
