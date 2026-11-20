"""Уровень 0: преобразование дерева скобочного файла в JSON и обратно без учёта смысла данных.

Блок представляется массивом, а скаляр — числом, строкой или обёрткой. Обёртка нужна там, где вид скаляра нельзя определить
по значению: GUID и строка в JSON выглядят одинаково как текст, а в файле GUID записан без кавычек, а строка в кавычках.
Писатель никогда не определяет по виду текста, нужны ли кавычки.

Дробное число хранится текстом (`Dec` — подкласс `str`) и пишется в JSON без кавычек. `Decimal` только проверяет, что текст
является числом: `Decimal("1e2")` печатается как `1E+2`. `float` значения не затрагивает, потому что 0.1 при обратном
преобразовании уже не совпадает с исходным текстом.

Целое число переводится в `int`, если текст при этом сохраняется. Встречаются целые с ведущими нулями (например,
`00010101000000` — дата 0001-01-01 четырнадцатью цифрами). Такое целое записывается обёрткой `{"num": "<текст как в файле>"}`
по образцу `{"guid": …}` и `{"base64": …}`. Обычное целое обёртки не получает.

Пустое значение (`0,,60` в файле) записывается как `null`, и обёртка ему не нужна. На уровне 0 значение есть у каждого
места списка, пустых мест не бывает, а бывают более короткие списки; отсутствием значений занимается уровень 1. `null` в
диффе (`diff.change_dict`) означает «адреса не было» с одной из сторон; это другой язык, и пустое значение файла печатается
там своей обёрткой.

У обёртки base64 может быть второе поле `layout`: оно показывает, как тело разложено по строкам в файле (три раскладки,
`tokens.B64_LAYOUTS`). Поле есть только тогда, когда байты блока отличаются от нормы. Раскладка — это способ записи значения,
отдельной обёртки для неё нет.
"""
import json
from decimal import Decimal, InvalidOperation

from .tokens import INT_RE, NUM_RE, B64_LAYOUTS, B64_NORM, b64_body
from .tree import Node, Scalar


class Json0Error(ValueError):
    pass


class Dec(str):
    """Дробное число уровня 0: текст как в файле, в JSON без кавычек."""


def int_text_survives(text):
    """Проверяет, сохраняется ли текст целого числа при преобразовании в `int`. Это единственное место, где принимается такое
    решение: по нему `decode0` выбирает между числом и обёрткой, `encode0` решает, принимать ли обёртку, а `typed._fits` решает,
    снимать ли с позиции имя из карты.
    """
    return str(int(text)) == text


def exp_int(text):
    """Возвращает значение целого числа, записанного экспонентой (`2e1`, `1e2`, `1.2e2`), иначе `None`.

    Это вторая форма записи целого у платформы (вид карты `int-exp`): так записывается ширина колонки, у которой на конце нули.
    Экспонента обязательна, поэтому `100.0` не подходит. Дробное число (`93.75`, `1.25e1`) тоже даёт `None`, потому что это другое
    число.
    """
    if not isinstance(text, str) or "e" not in text.lower() or not NUM_RE.fullmatch(text):
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    if number != number.to_integral_value():
        return None
    return int(number)


def int_exp_text(number):
    """Целое число в том виде, как платформа записывает его в поле вида `int-exp`: `Dec` с экспонентой или `int`.

    У целого с нулями на конце мантисса содержит одну цифру до точки, а дальше идёт показатель (`20` → `2e1`, `100` → `1e2`,
    `120` → `1.2e2`). Целое без нулей на конце записывается как есть (`28`, `181`). Ноль записывается целым.
    """
    if isinstance(number, bool) or not isinstance(number, int):
        raise Json0Error(f"целое для записи экспонентой, а пришло {number!r}")
    digits = str(abs(number))
    stripped = digits.rstrip("0")
    if number == 0 or stripped == digits:
        return number
    mantissa = stripped[0] + ("." + stripped[1:] if len(stripped) > 1 else "")
    return Dec(f"{'-' if number < 0 else ''}{mantissa}e{len(digits) - 1}")


def _where(path):
    return "/".join(str(p) for p in path) if path else "корень"


def decode0(item):
    if isinstance(item, Node):
        return [decode0(c) for c in item.children]
    if item.kind == "INT":
        return int(item.text) if int_text_survives(item.text) else {"num": item.text}
    if item.kind == "DEC":
        return Dec(item.text)
    if item.kind == "STR":
        return item.text
    if item.kind == "EMPTY":
        return None
    if item.kind == "GUID":
        return {"guid": item.text}
    if item.kind == "B64":
        # Раскладка — второе поле той же обёртки, и оно присутствует, только если раскладка не нормальная.
        return {"base64": item.text} if item.layout == B64_NORM else \
               {"base64": item.text, "layout": item.layout}
    raise Json0Error(f"неизвестный вид скаляра {item.kind}")


def _number(text, path):
    if not NUM_RE.fullmatch(text):
        raise Json0Error(f"{_where(path)}: {text!r} не число")
    try:
        Decimal(text)
    except InvalidOperation:
        raise Json0Error(f"{_where(path)}: {text!r} не число")
    return text


def _int_text(text, path):
    """Текст обёртки `num` должен быть целым числом, записанным как в файле, и таким, что его знаки при преобразовании в число не
    сохраняются. Нарушение любого из условий — отказ, а не приведение. Нецелое значение (`01.5`, `0e1`, пробел) в обёртке
    недопустимо. Целое, которое число сохраняет (`7`), в обёртку записывать нельзя, потому что разбор вернул бы `7`.
    """
    if not isinstance(text, str) or not INT_RE.fullmatch(text):
        raise Json0Error(f"{_where(path)}: обёртка num несёт текст целого, как он стоит в файле, "
                         f"а тут {text!r}")
    if int_text_survives(text):
        raise Json0Error(f"{_where(path)}: обёртка num держит знаки, которые число теряет "
                         f"(ведущий ноль, `-0`); у {text!r} их нет — такое пишут числом "
                         f"{int(text)}")
    return text


def _b64_layout(text, layout, path):
    """Раскладка обёртки base64 должна быть известной и отличаться от нормы на этом теле. Нарушение любого условия — отказ, а не
    приведение. Неизвестное имя записать нечем. На теле короче строки все три раскладки пишутся одинаковыми байтами, и разбор
    вернул бы обёртку без признака. Норма записывается пропуском поля.
    """
    if not isinstance(layout, str) or layout not in B64_LAYOUTS:
        raise Json0Error(f"{_where(path)}: раскладки base64 {layout!r} не бывает; известны "
                         f"{', '.join(B64_LAYOUTS)}")
    if b64_body(text, layout) == b64_body(text, B64_NORM):
        raise Json0Error(f"{_where(path)}: раскладка {layout!r} пишет это тело теми же байтами, "
                         "что и норма; признак ставят, только когда байты с нормой расходятся")
    return layout


def encode0(value, path=()):
    if isinstance(value, list):
        return Node([encode0(v, path + (i,)) for i, v in enumerate(value)])
    if value is None:
        # Пустое значение файла (`0,,60`).
        return Scalar("EMPTY", "")
    if isinstance(value, bool):
        # Эта проверка стоит раньше проверки `int`, потому что `True` в Python равно единице и молча превратилось бы в `1`, то есть в
        # булево поле уровня 1.
        raise Json0Error(f"{_where(path)}: булево значение на уровне 0; целое пишется числом")
    if isinstance(value, Dec):
        return Scalar("DEC", _number(str(value), path))
    if isinstance(value, int):
        return Scalar("INT", str(value))
    if isinstance(value, float):
        raise Json0Error(f"{_where(path)}: дробное приехало float, знаки уже потеряны; "
                         "читайте JSON через loads (parse_float=Dec)")
    if isinstance(value, str):
        return Scalar("STR", value)
    if isinstance(value, dict):
        if set(value) == {"guid"} and isinstance(value["guid"], str):
            return Scalar("GUID", value["guid"])
        if set(value) in ({"base64"}, {"base64", "layout"}):
            text = value["base64"]
            if not isinstance(text, str):
                raise Json0Error(f"{_where(path)}: обёртка base64 несёт текст блока, "
                                 f"а тут {text!r}")
            if "layout" not in value:
                return Scalar("B64", text)
            return Scalar("B64", text, _b64_layout(text, value["layout"], path))
        if set(value) == {"num"}:
            return Scalar("INT", _int_text(value["num"], path))
        raise Json0Error(f"{_where(path)}: обёртка {sorted(value)} не guid, не base64 и не num")
    raise Json0Error(f"{_where(path)}: значение {type(value).__name__} в JSON формы не бывает")


_COMPOSITE = object()


def _basic(value, bools=False):
    """Печатает одиночное значение. Значение `_COMPOSITE` означает массив или объект, и его печатает вызывающий.

    Это общая часть двух писателей: `dumps` пишет в несколько строк, `dumps_line` — в одну. Правила для видов значений у них
    одинаковы. `Dec` — подкласс `str`, и писатель, который об этом не знает, поставил бы кавычки вокруг дробного числа.

    Параметр `bools` различает два уровня. На уровне 0 булевых значений нет, и сводка `dumps_line` отказывает при их появлении.
    На уровне 1 булево значение печатается словом. `encode0` записывает значения в дерево и по-прежнему отвергает булевы
    значения.
    """
    if isinstance(value, Dec):
        return str(value)
    if isinstance(value, bool):
        # Проверка раньше `int`: `True` в Python равно единице.
        if not bools:
            raise Json0Error("булева значения в JSON формы нет")
        return json.dumps(value)
    if value is None or isinstance(value, (int, str)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (dict, list)):
        return _COMPOSITE
    raise Json0Error(f"значение {type(value).__name__} в JSON формы не бывает")


def dumps(value, indent=1, _level=0):
    """Собственный писатель. `json.dumps` поставил бы кавычки вокруг `Dec`, а раскладка «массив из одних скаляров в одну строку»
    повторяет правило файла. Писатель обслуживает оба уровня — сводку уровня 0 и документ уровня 1, — поэтому булевы значения он
    печатает (`_basic(bools=True)`).
    """
    pad, step = " " * (indent * _level), " " * (indent * (_level + 1))
    basic = _basic(value, bools=True)
    if basic is not _COMPOSITE:
        return basic
    if isinstance(value, dict):
        if not value:
            return "{}"
        items = [json.dumps(k, ensure_ascii=False) + ": " + dumps(v, indent, _level + 1)
                 for k, v in value.items()]
        return "{\n" + ",\n".join(step + i for i in items) + "\n" + pad + "}"
    if isinstance(value, list):
        if not value:
            return "[]"
        if all(not isinstance(v, (list, dict)) for v in value):
            return "[" + ", ".join(dumps(v, indent, _level + 1) for v in value) + "]"
    items = [dumps(v, indent, _level + 1) for v in value]
    return "[\n" + ",\n".join(step + i for i in items) + "\n" + pad + "]"


def dumps_line(value, bools=False):
    """Работает как `dumps`, но пишет в одну строку и по тому же правилу печатает дробные числа.

    Функция нужна там, где запись обязана занимать одну строку: сводка набора форм (`stat.dump_summary`) записывает по одной
    позиции на строку.

    Параметр `bools` тот же, что у `dumps`. Уровень 0 булевых значений не знает (по умолчанию `False`), а смысловой дифф
    сравнивает документы уровня 1.

    Ключи объекта явно приводятся к строке, потому что JSON не допускает числа в ключах.
    """
    basic = _basic(value, bools=bools)
    if basic is not _COMPOSITE:
        return basic
    if isinstance(value, dict):
        items = [json.dumps(str(k), ensure_ascii=False) + ":" + dumps_line(v, bools)
                 for k, v in value.items()]
        return "{" + ",".join(items) + "}"
    return "[" + ",".join(dumps_line(v, bools) for v in value) + "]"


def loads(text):
    return json.loads(text, parse_float=Dec)
