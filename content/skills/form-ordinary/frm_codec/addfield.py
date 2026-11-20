"""Вывод реквизитов шапки на готовую форму одним вызовом (команда `add-field`).

Описание формы снимается `describe`, реквизит дописывается в блок полей, и результат отдаётся бережному режиму `generate` — он
ставит пару «надпись + поле» по тем же правилам, что и при ручной правке описания. Вместо общей проверки «форма читается как описание»
здесь проверяется именно правка: `describe` после правки равен `describe` до неё плюс добавленное поле на названном месте. Без `--after`
место перебирается: первый вариант, прошедший бережный режим и эту проверку, принимается.

Реквизиты выводятся по одному, по порядку: следующий ставится на форму, уже получившую предыдущий. Причины отказа, которые от места не
зависят (тип значения, реквизит не той формы, вид формы), проверяются до перебора и называются один раз."""
import copy
import dataclasses
import pathlib

from . import describe as describe_mod, generate, generate_gentle, layout, shell as shell_mod, typed
from .edit import datapath
from .tree import read_file

OBJECT_PREFIX = datapath.OBJECT_WORD + "."
MAX_TRIES = 12             # предел вариантов места на один реквизит
BODY_KINDS = ("table", "tabs", "spreadsheet")   # блоки, после которых поля уже не шапка, а подвал


class AddFieldError(ValueError):
    """Отказ команды словами: реквизит не тот, места нет, форму описать не удалось."""


@dataclasses.dataclass
class Step:
    name: str                  # реквизит
    place: str                 # принятое место словами
    tried: int                 # сколько вариантов места проверено, включая принятый
    rejected: list             # [(место словами, причина)] — отвергнутые варианты
    report: object             # `generate.Report` принятого варианта


@dataclasses.dataclass
class Outcome:
    steps: list                # [Step] по порядку вывода
    present: list              # [(имя, [имена элементов])] — уже на форме, не добавлялись
    hidden: list               # [(имя, [имена скрытых элементов])] — на форме только скрытыми элементами, не добавлялись
    out_path: str              # где лежит результат (`None`, если добавлять было нечего)


def _field_blocks(blocks):
    """Блоки `fields` верхнего уровня описания в порядке описания. Блоки внутри рамок и закладок не берутся: бережный режим
    их не правит (разница внутри `group` и `tabs` — его отказ)."""
    return [block for block in blocks or () if isinstance(block, dict) and "fields" in block]


def _header_numbers(blocks):
    """Номера блоков полей (среди всех блоков полей), которые стоят до первой таблицы, закладок или табличного документа, — шапка; остальные — подвал."""
    numbers, seen = [], 0
    for block in blocks or ():
        if not isinstance(block, dict):
            continue
        if "fields" in block:
            numbers.append(seen)
            seen += 1
        elif any(kind in block for kind in BODY_KINDS):
            break
    return numbers


def _bare(name):
    name = str(name).strip()
    return name[len(OBJECT_PREFIX):] if name.startswith(OBJECT_PREFIX) else name


def _fold(name):
    return str(name).casefold()


def path_object(path):
    """Объект по месту формы в выгрузке (`<Вид>/<Объект>/Forms/<Форма>/…`): «Справочник.Имя» либо `None`. Только для слов отказа: привязать реквизиты
    по месту формы нельзя — их адресует тип основного реквизита формы, и он должен найтись в выгрузке."""
    parts = list(pathlib.Path(path).parts)
    if "Forms" in parts:
        at = len(parts) - 1 - parts[::-1].index("Forms")
        if at >= 2 and parts[at - 2] in KIND_DIRS:
            return f"{KIND_DIRS[parts[at - 2]]}.{parts[at - 1]}"
    return None


KIND_DIRS = {"Catalogs": "Справочник", "Documents": "Документ", "DataProcessors": "Обработка"}


def _no_kind_words(doc, place):
    """Почему описание не назвало ни вида, ни объекта формы."""
    attributes, rows = datapath._attributes(doc)
    head = attributes.get(datapath.ATTR_HEAD)
    main = head.get(datapath.MAIN_ATTRIBUTE_ID) if isinstance(head, dict) else None
    row = next((r for r in rows if datapath._id_of(r) == main), None)
    where = f"; по месту формы в выгрузке это форма объекта «{place}»" if place else ""
    if row is None:
        return ("у формы нет основного реквизита — это вспомогательная форма (подбор, настройка, заполнение): реквизиты объекта на ней "
                "адресовать не от чего" + where)
    return ("тип основного реквизита формы не найден в выгрузке (выгрузка другой версии или частичная, либо форма не объекта выгрузки): "
            "привязать реквизиты по месту формы нельзя — их адресует этот тип" + where)


def _describe(doc, config, kind, object_name, place=None):
    """Описание формы, объект выгрузки и сведения области (`generate_gentle._scope`); отказ — словами."""
    try:
        result = describe_mod.describe(copy.deepcopy(doc), config, kind=kind, object_name=object_name)
    except (describe_mod.DescribeError, generate.GenerateError, ValueError) as e:
        raise AddFieldError(f"описание формы снять не удалось: {e}") from None
    desc = result.description
    if not desc.get("kind") or not desc.get("object"):
        raise AddFieldError("вид формы и её объект определить не удалось: " + _no_kind_words(doc, place))
    if desc.get("kind") in generate.LIST_KINDS:
        raise AddFieldError("форма списка: реквизит шапки выводится на форму элемента, документа или обработки; "
                            "колонку списка добавляет `generate` по описанию (эта команда её не добавляет — не реализовано)")
    try:
        scope = generate_gentle._scope(desc, doc, config)
    except generate.GenerateError as e:
        raise AddFieldError(str(e)) from None
    if scope[1] is None:
        raise AddFieldError("у формы нет объекта в выгрузке: реквизиты шапки взять не из чего")
    return desc, scope


def _canonical(obj, raw):
    """Имя реквизита шапки как в выгрузке (имена 1С не различают регистр); отказ словами для табличной части, реквизита ТЧ и неизвестного имени."""
    name = _bare(raw)
    if not name:
        raise AddFieldError("пустое имя реквизита в --attr")
    if "." in name:
        raise AddFieldError(f"«{name}»: реквизит табличной части эта команда не выводит (не реализовано): колонку добавляет "
                            "`generate` с блоком `table` либо операция редактора `add_column`")
    for part in obj.tables:
        if _fold(part.name) == _fold(name):
            raise AddFieldError(f"«{part.name}» — табличная часть, а не реквизит шапки: таблицу на форму эта команда не выводит (не реализовано)")
    for known in [a.name for a in obj.attributes] + list(obj.standard):
        if _fold(known) == _fold(name):
            return known
    names = [a.name for a in obj.attributes] + list(obj.standard)
    raise AddFieldError(f"у объекта «{obj.full_name}» нет реквизита шапки «{name}» (реквизиты и стандартные реквизиты: "
                        f"{', '.join(names) or 'нет'}); реквизит формы эта команда не выводит (не реализовано)")


def _independent_refusal(desc, doc, config, scope, name):
    """Причины, которые от места не зависят: тип значения не поддержан, реквизит не относится к этой форме (форма группы, использование). Проверяет тот же разбор поля,
    что и бережный режим. Возвращает слова отказа или `None`."""
    processing, obj, role, form, no_object = scope
    try:
        shell = shell_mod.scan(doc, obj)
    except generate.GenerateError as e:
        return str(e)
    except Exception:  # noqa: BLE001 — исходная форма не разобрана: об этом скажет бережный режим
        return None
    resolver = generate._Resolver(obj, role, config, form, shell)
    if processing:
        resolver.no_object = no_object
    resolver._field({"data": name}, f"поле «{name}»")
    if resolver.problems:
        return "; ".join(resolver.problems) + " (причина не зависит от места: перебирать места нечего)"
    return None


def places(desc, after=None):
    """Варианты места для нового поля: `[(номер блока, позиция, слова)]` — без `--after` в порядке перебора, с ним — одно названное место.

    Порядок перебора: конец самого большого блока полей шапки (при равенстве — первого), концы прочих блоков шапки по убыванию числа полей,
    затем места после каждого поля — самого большого блока, потом прочих, снизу вверх. Блоки ниже первой таблицы или закладок (подвал) в перебор не входят:
    туда реквизит ставится только по явному `--after`. Нет блока шапки — берутся все блоки."""
    blocks = _field_blocks(desc.get("blocks"))
    if not blocks:
        raise AddFieldError("на форме нет блока полей шапки, в который можно добавить реквизит: полей нет или они стоят внутри рамок и закладок, "
                            "которые бережный режим не правит (форму с нуля создаёт `generate --relayout`)")
    if after is not None:
        anchor = _fold(_bare(after))
        for number, block in enumerate(blocks):
            names = [generate_gentle._entry(e)[0][1] for e in block["fields"]]
            hit = next((i for i, n in enumerate(names) if _fold(n) == anchor), None)
            if hit is not None:
                return [(number, hit + 1, f"после поля «{names[hit]}» (блок полей {number + 1} из {len(blocks)})")]
        have = ", ".join(generate_gentle._entry(e)[0][1] for b in blocks for e in b["fields"])
        raise AddFieldError(f"--after «{_bare(after)}»: такого поля нет в блоках полей формы (поля: {have})")
    pool = _header_numbers(desc.get("blocks")) or list(range(len(blocks)))
    order = sorted(pool, key=lambda n: (-len(blocks[n]["fields"]), n))
    found = [(n, len(blocks[n]["fields"]), f"в конец блока полей {n + 1} из {len(blocks)} ({len(blocks[n]['fields'])} полей)") for n in order]
    for number in order:        # затем после каждого поля: сначала самый большой блок, потом прочие по убыванию
        for at in range(len(blocks[number]["fields"]) - 1, 0, -1):
            name = generate_gentle._entry(blocks[number]["fields"][at - 1])[0][1]
            found.append((number, at, f"после поля «{name}» (блок полей {number + 1} из {len(blocks)})"))
    return found[:MAX_TRIES]


def _with_field(desc, number, at, name):
    made = copy.deepcopy(desc)
    _field_blocks(made["blocks"])[number]["fields"].insert(at, name)
    return made


def _neighbours(desc, number, at):
    """Имена полей до и после места вставки в блоке (`None` — нет)."""
    keys = [generate_gentle._entry(e)[0][1] for e in _field_blocks(desc["blocks"])[number]["fields"]]
    return (keys[at - 1] if at else None, keys[at] if at < len(keys) else None)


def reason_lines(rejected):
    """Отвергнутые варианты по строкам: одинаковая причина — одной строкой для всех мест, без обрезки; хвост «Выход: …» бережного режима отбрасывается
    (команда называет свои выходы)."""
    grouped = {}
    for words, why in rejected:
        grouped.setdefault(" ".join(str(why).split()).split(". Выход:")[0], []).append(words)
    return [f"  {'; '.join(places)} — {why}" for why, places in grouped.items()]


def _visible_names(doc):
    form = layout.read(doc)
    return {i.name for h in form.holders.values() for i in h.children if i.visible}


def run(form_path, config, config_dir, attrs, after, out_path, workdir, siblings=None, kind=None, object_name=None):
    """Реквизиты → форма: перебор мест, бережный режим и проверка правки; результат пишется в `out_path` при успехе всех шагов.

    `workdir` — каталог для промежуточных форм (между реквизитами). Отказ — `AddFieldError` с перечнем отвергнутых вариантов."""
    if not attrs:
        raise AddFieldError("не назван ни один реквизит: --attr ИМЯ (можно несколько раз)")
    doc = typed.decode(read_file(str(form_path)))
    desc, scope = _describe(doc, config, kind, object_name, path_object(form_path))
    obj = scope[1]
    wanted = []
    for raw in attrs:
        name = _canonical(obj, raw)
        if name not in wanted:
            wanted.append(name)
    bound = generate_gentle.all_bindings(doc, obj)
    named = {generate_gentle._entry(e)[0] for block in _field_blocks(desc.get("blocks")) for e in block["fields"]}
    visible = _visible_names(doc)
    present, hidden = [], []
    for name in wanted:
        elements = [n for n, _t in bound.get(("object", name), [])]
        if elements and not any(n in visible for n in elements):
            hidden.append((name, elements))
        elif elements or ("object", name) in named:
            present.append((name, elements))
    skipped = {n for n, _e in present} | {n for n, _e in hidden}
    todo = [name for name in wanted if name not in skipped]
    outcome = Outcome([], present, hidden, None)
    if not todo:
        return outcome
    for name in todo:
        why = _independent_refusal(desc, doc, config, scope, name)
        if why:
            raise AddFieldError(f"реквизит «{name}» не выводится: {why}")
    current = pathlib.Path(form_path)
    anchor = after
    for number, name in enumerate(todo):
        last = number == len(todo) - 1
        target = pathlib.Path(out_path) if last else pathlib.Path(workdir) / f"step{number}.frm"
        doc = typed.decode(read_file(str(current)))
        desc, _scope = _describe(doc, config, kind, object_name)
        rejected, tried = [], 0
        for block, at, words in places(desc, anchor):
            tried += 1
            try:
                report = generate.apply(_with_field(desc, block, at, name), current, config_dir, target, overwrite=True, siblings=siblings,
                                        config=config, gentle_only=True, edit_of=[name], edit_place=_neighbours(desc, block, at))
            except generate.GenerateError as e:
                rejected.append((words, str(e)))
                continue
            outcome.steps.append(Step(name, words, tried, rejected, report))
            break
        else:
            raise AddFieldError(_refusal(name, anchor, rejected))
        current, anchor = target, name if after is not None else None
    outcome.out_path = str(current)
    return outcome


def _refusal(name, after, rejected):
    lines = [f"реквизит «{name}» не встал на форму: проверено мест {len(rejected)} (предел {MAX_TRIES}), бережный режим отвергает каждое"]
    lines += reason_lines(rejected)
    lines.append("Выходы: другое место (--after), `generate --relayout` (полная раскладка) или `edit` (операции редактора)" if after is not None
                 else "Выходы: назвать место ключом --after ПОЛЕ, `generate --relayout` (полная раскладка) или `edit` (операции редактора)")
    return "\n".join(lines)
