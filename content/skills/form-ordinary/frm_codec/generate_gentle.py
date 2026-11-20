"""Бережный `generate` поверх формы человека.

**Откуда.** Сценарий: `describe` готовой формы → в описание дописано одно поле → `generate --form <та же форма>`. Движок `generate` перекладывает форму
ЦЕЛИКОМ по своим нормам: надписи у человека стоят с разных x, ширины и высоты свои, колонка без данных и нижняя панель — свои, и всё это движок
«выправлял» бы (на форме документа — 26 операций вместо двух). Для формы СПИСКА бережный режим есть давно (`generate_list`: колонка в конец, прочее
не тронуто); здесь он у форм элемента, документа и обработки.

**Выбор режима** (`choose`). Исходная форма считается «формой движка», если проверка обратным разбором («её `describe` → `generate` поверх неё», размер — её
собственный) оставляет на местах каждый её элемент: те же имена, типы, места, видимость и коэффициенты растяжения (размер формы не сверяется).
Элемент, убранный при такой проверке, считается расхождением. Проверка сравнивает раскладку, а не байты: байты у формы конструктора после неё тоже
разные (движок ставит панели первыми и раздаёт свои индексы), поэтому сравнение байтов не отличило бы форму конструктора от формы человека. Два случая — всегда полная раскладка: у исходной формы нет ни
одного поля и ни одной таблицы на данные (беречь нечего), и `describe` исходной формы не снимается. Ключ `--relayout` (`apply(relayout=True)`) — полная
раскладка явно, для любой исходной формы.

**Бережный режим** (`plan_notes`) — разница описаний `describe(исходной формы)` → описание, переведённая в операции редактора над исходной формой; ничего сверх
разницы не двигается и не переписывается (колонки без данных, панели, шрифты, заголовок, размеры — как были). Выразимое:

* поле добавлено в существующий блок `fields` (блоки сопоставляются по составу полей, не по номеру) — `add_element` надписи и поля `after`
  предыдущего поля блока, `bind`, подпись и свойства нового поля — как у движка (`_Resolver._field`: синоним реквизита, двоеточие по стилю исходной формы,
  кнопка выбора, подсказка). Размер и привязки — по соседу того же типа (`place`): ширину надписи по тексту считает `place`/`textwidth`. Место:
  обычное; не вышло — `shrink=true` (ужать таблицу); не вышло — `grow=true` (форма выше на шаг); какое сработало — в отчёте; не вышло ничего —
  отказ с выходом `--relayout`. Первое поле блока без предыдущего — отказ;
* поле убрано из блока — `remove_element` поля и его надписи (пара — как её находит `shell.find_label`), место остаётся пустым, отчёт это называет;
* колонка добавлена в существующую таблицу — `add_column` в конец (как `generate_list`), убрана — `remove_column`; колонки, которых описание не
  выражает (`skipped` образца), не трогаются;
* заголовок формы, названный описанием и отличный от стоящего, — `set_form_title`; доводка `tune` — после операций, как у движка.

**Отказ словами до записи** (все причины разом, выход — `--relayout`): новый или убранный блок, перестановка блоков или полей, смена `columns` или
вида блока, разница внутри `group`/`tabs`, поле, переехавшее между блоками, поле на форме, которого образец не взял, иная подпись или ширина у поля,
оставшегося в блоке, `width`/`height`/`anchors` у нового поля (место и привязки нового поля — по соседу; свою ширину после ставят в `tune` по имени,
которое назвал отчёт), смена вида, объекта или `form_use`. `size` описания не применяется (размер формы не меняется; отчёт это называет)."""
import copy
import dataclasses

from . import describe as describe_mod, edit, generate, layout, limits, metadata, old_versions, place, shell as shell_mod, textgap, textwidth
from .layout import candidates
from .edit import base, columns as ed_columns, datapath
from .edit.base import EditError
from .generate import GenerateError

LADDER = (("plain", {}, "обычное место"),
          ("shrink", {"shrink": True}, "место освобождено ужатием таблицы (shrink=true)"),
          ("grow", {"grow": True}, "место освобождено ростом формы на шаг (grow=true)"))
OTHER_KINDS = ("command_bar", "group", "tabs", "spreadsheet", "radio", "picture", "row", "beside", "split")
MAX_LISTED = 5
WAY_OUT = ("Выход: ключ --relayout (полная раскладка: форма перекладывается целиком по нормам вида) либо правка формы операциями редактора "
           "(frm_json.py edit) — они двигают только названное")


@dataclasses.dataclass
class Verdict:
    gentle: bool
    line: str                  # первая строка отчёта: режим и почему
    old: object = None         # описание исходной формы (`describe`) — у бережного режима


# ── Выбор режима ───────────────────────────────────────────────────────────────────────────

def _hints(desc):
    """`describe` исходной формы по подсказкам описания: у обработки вид и объект даёт описание, у формы объекта — метаданные."""
    kind = desc.get("kind")
    processing = kind == generate.PROCESSING
    return {"form_use": desc.get("form_use"), "kind": kind if processing else None, "object_name": desc.get("object") if processing else None}


def _snapshot(doc):
    """Что проверка обратным разбором обязана сохранить: у каждого элемента (по родителю, странице и имени) вид, место, видимость и коэффициенты растяжения. Размер формы не сверяется:
    проверка сама записывает размер исходной формы (`circle`), и расхождение по нему невозможно."""
    form = layout.read(doc)
    coefs = layout.coefficients(form, hide=False)
    out = {}
    for holder in form.holders.values():
        for item in holder.children:
            out[(holder.name or "", item.page, item.name or f"#{item.index}")] = (item.type, tuple(item.box), bool(item.visible), coefs.get(item.index))
            if item.type == "TableBox":  # состав колонок: колонку без данных движок убрал бы, а места элементов от этого не меняются
                try:
                    names = tuple(ed_columns._column_name(c) for c in ed_columns.columns_of(item.node)[ed_columns.COLUMN_ITEMS])
                except (EditError, KeyError, TypeError, AttributeError):
                    names = ()
                out[("~колонки", 0, item.name or f"#{item.index}")] = names
    return out


def _differences(before, after):
    """Слова о том, чем раскладки разошлись: пусто — сошлись. Названы первые элементы."""
    items_a, items_b = before, after
    said = []
    gone = [k[2] for k in items_a if k not in items_b and k[0] != "~колонки"]
    moved = [k[2] for k in items_a if k in items_b and k[0] != "~колонки" and items_a[k] != items_b[k]]
    for label, names in (("убраны", gone), ("сдвинуты или иные", moved)):
        if names:
            said.append(f"{label} {len(names)}: {', '.join(names[:MAX_LISTED])}{'…' if len(names) > MAX_LISTED else ''}")
    for k, was in items_a.items():
        if k[0] == "~колонки" and k in items_b and items_b[k] != was:
            lost = [c for c in was if c not in items_b[k]]
            said.append(f"колонки таблицы «{k[2]}»: {'убраны ' + ', '.join(lost) if lost else 'иной состав'}")
    return said


def _has_content(blocks):
    """В описании есть поле или таблица на данные (на любой глубине рамок и закладок)."""
    for block in blocks or ():
        if "fields" in block or "table" in block:
            return True
        if "group" in block and _has_content(block.get("blocks")):
            return True
        if "tabs" in block and any(_has_content(page.get("blocks")) for page in block["tabs"] if isinstance(page, dict)):
            return True
    return False


def circle(old, doc, config, norms, heights):
    """Проверка обратным разбором: описание исходной формы → `generate` поверх неё (размер исходной формы). `(сошёлся, число операций, слова расхождения)`."""
    desc = copy.deepcopy(old)
    desc.pop("skipped", None)
    form = layout.read(doc)
    desc["size"] = [form.width, form.height]
    try:
        ops, _notes = generate.plan_notes(desc, copy.deepcopy(doc), config, norms, heights)
        with old_versions.off():
            made, _bsl, _log = edit.apply(copy.deepcopy(doc), ops, config=config)
    except (GenerateError, EditError) as e:
        return False, 0, [f"проверка обратным разбором отказала словами движка: {e}"]
    said = _differences(_snapshot(doc), _snapshot(made))
    return not said, len(ops), said


def choose(desc, doc, config, norms, heights=None, only=False):
    """Режим для описания и исходной формы: `Verdict`. Только расчёт — ни исходная форма, ни файлы не меняются.

    `only=True` (команда `add-field`): режим движка не бывает — форма конструктора тоже правится бережно, а там, где беречь нечего
    (форма списка, нет ни полей, ни таблиц, описание формы снять не удалось), — отказ со словами режима."""
    verdict = _choose(desc, doc, config, norms, heights, only)
    if only and not verdict.gentle:
        raise GenerateError(f"{verdict.line}; бережная правка здесь невозможна, а полная раскладка этой командой не включается "
                            "(выход — `generate --relayout` или `edit`)")
    return verdict


def _choose(desc, doc, config, norms, heights, only):
    kind = desc.get("kind")
    if kind in generate.LIST_KINDS:
        return Verdict(False, "Режим: форма списка — бережный сам (`generate_list`: таблица и колонки исходной формы на месте, недостающая колонка — в конец)")
    try:
        old = describe_mod.describe(copy.deepcopy(doc), config, **_hints(desc)).description
    except (describe_mod.DescribeError, GenerateError, EditError) as e:
        return Verdict(False, f"Режим: полная раскладка — описание исходной формы снять не удалось ({e}); беречь нечего")
    if not _has_content(old.get("blocks")):
        return Verdict(False, "Режим: полная раскладка — в исходной форме нет ни полей, ни таблиц на данные: беречь нечего")
    ok, count, said = circle(old, doc, config, norms, heights)
    if ok and only:
        return Verdict(True, f"Режим: бережный — по команде (операций проверки обратным разбором {count}; форма сходится с описанием, раскладка не меняется — правится только разница описаний)", old)
    if ok:
        return Verdict(False, f"Режим: форма движка — проверка обратным разбором «describe → generate» сошлась (операций {count}: места, привязки и состав колонок всех элементов прежние при прежнем размере формы; описание без `size` даёт форму по содержимому, как прежде); раскладка меняется как прежде")
    return Verdict(True, f"Режим: бережный — форма человека: проверка обратным разбором «describe → generate» разошлась (операций {count}; {'; '.join(said)}); "
                         "применяется только разница описаний, остальное не тронуто (полная раскладка — --relayout)", old)


# ── Разница описаний ──────────────────────────────────────────────────────────────────────────

def _entry(entry):
    """Запись поля → `(ключ, объект записи)`: ключ — как у исходной формы (`("object" | "form", имя)`)."""
    obj = {"data": entry} if isinstance(entry, str) else dict(entry)
    data = generate._strip_object(str(obj.get("data", "")).strip())
    return ("form" if obj.get("source") == "form" else "object", data), obj


def _word(key):
    return f"«{key[1]}»" + (" (реквизит формы)" if key[0] == "form" else "")


def _kind_of(block):
    return next((k for k in generate.BLOCKS if k in block), None)


def _columns_of(block, obj):
    """Колонки блока `table`: список имён (умолчание — все реквизиты части в порядке метаданных, как у движка)."""
    raw = block.get("columns")
    if raw is not None:
        return list(raw)
    name = generate._strip_object(str(block["table"]).strip())
    part = next((t for t in obj.tables if t.name == name), None) if obj is not None else None
    return [a.name for a in part.attributes] if part is not None else None


def _match_fields(olds, news):
    """Блоки `fields` нового описания → блоки образца по составу полей: `{номер нового: номер старого}`; без общих полей — не сопоставлен."""
    pairs, taken = {}, set()
    for at, block in news:
        keys = {_entry(e)[0] for e in block["fields"]}
        best = None
        for o_at, o_block in olds:
            if o_at in taken:
                continue
            share = len(keys & {_entry(e)[0] for e in o_block["fields"]})
            if share and (best is None or share > best[0]):
                best = (share, o_at)
        if best is not None:
            pairs[at] = best[1]
            taken.add(best[1])
    return pairs


def all_bindings(doc, obj):
    """Привязки данных ВСЕХ элементов формы — на любом родителе и странице, видимых и нет: `{ключ реквизита: [(имя элемента, вид)]}`. Ключ — как
    у исходной формы (`("object" | "form", имя)`); табличная часть и прочие пути в счёт не идут."""
    attributes, rows = datapath._attributes(doc)
    head = attributes.get(datapath.ATTR_HEAD) if isinstance(attributes, dict) else None
    main = head.get(datapath.MAIN_ATTRIBUTE_ID) if isinstance(head, dict) else None
    main = main if isinstance(main, int) and not isinstance(main, bool) else None
    form_attrs = {}
    for row in rows:
        ident = datapath._id_of(row)
        if isinstance(ident, int) and not isinstance(ident, bool):
            form_attrs[ident] = row.get(datapath.ATTR_NAME) if isinstance(row.get(datapath.ATTR_NAME), str) else None
    names = {}
    for _name, holder in base.holders(doc):
        for item in (holder.get(base.ELEMENTS) or {}).get(base.ITEMS) or []:
            if isinstance(item, dict) and isinstance(item.get("index"), int):
                names[item["index"]] = (base.name_of(item) or f"#{item['index']}", item.get("type"))
    out = {}
    for row in datapath.binding_rows(attributes):
        steps = row.get("path", {}).get("steps") if isinstance(row.get("path"), dict) else None
        element = row.get(datapath.BIND_ELEMENT)
        if not isinstance(steps, list) or element not in names:
            continue
        kind, name = shell_mod.resolve_binding([x if isinstance(x, dict) else {} for x in steps], main, form_attrs, obj)
        if kind in ("object", "form"):
            out.setdefault((kind, name), []).append(names[element])
    return out


def _keys_in(blocks):
    """Ключи полей, названных в блоках образца на любой глубине (рамки и страницы закладок)."""
    for block in blocks or ():
        if not isinstance(block, dict):
            continue
        if "fields" in block:
            for entry in block["fields"]:
                yield _entry(entry)[0]
        if "group" in block:
            yield from _keys_in(block.get("blocks"))
        if "tabs" in block:
            for page in block["tabs"]:
                if isinstance(page, dict):
                    yield from _keys_in(page.get("blocks"))


@dataclasses.dataclass
class Change:
    removes: list      # [(ключ, слова)]
    adds: list         # [(ключ, запись, ключ предыдущего поля, слова блока)]
    columns: list      # [(таблица исходной формы, ts, добавить [имена], убрать [имена колонок исходной формы])]
    title: object
    notes: list


def diff(desc, old, shell, obj, form_size, problems, bound=None):
    """Разница описаний `old` (образец) → `desc` (новое). Невыразимое — в `problems` словами."""
    ch = Change([], [], [], None, [])
    for key in ("kind", "object"):
        if desc.get(key) is not None and old.get(key) is not None and desc[key] != old[key] and not (
                key == "object" and metadata.same_object_name(desc[key], old[key])):
            problems.append(f"{key} описания «{desc[key]}», а у образца исходной формы «{old[key]}»: другая форма — бережная правка её не делает")
    if desc.get("form_use") is not None and desc["form_use"] != old.get("form_use"):
        problems.append(f"form_use описания «{desc['form_use']}», а у образца «{old.get('form_use')}»: другая роль формы")
    if isinstance(desc.get("size"), list) and list(desc["size"]) != list(form_size):
        ch.notes.append(f"size {desc['size']} из описания не применяется: бережный режим размер формы ({form_size[0]}×{form_size[1]}) не меняет")
    if desc.get("title") and desc["title"] != old.get("title"):
        ch.title = desc["title"]
    olds, news = list(enumerate(old["blocks"])), list(enumerate(desc["blocks"]))
    paired, used_old = {}, set()
    # блоки без полей — равные друг другу (панели команд, рамки, закладки, поле табличного документа)
    for at, block in news:
        kind = _kind_of(block)
        if kind in OTHER_KINDS:
            hit = next((o for o, b in olds if o not in used_old and b == block), None)
            if hit is None:
                near = next((b for o, b in olds if o not in used_old and _kind_of(b) == kind), None)
                what = "новый блок" if near is None else f"блок «{kind}» иной, чем у образца"
                problems.append(f"{what} blocks[{at}] «{kind}»" + ("" if kind == "command_bar" else ": рамки, закладки, поле табличного документа, ряды, блок справа от шапки и области с разделителем бережный режим не правит"))
            else:
                paired[at] = hit
                used_old.add(hit)
    tables_old = {generate._strip_object(str(b["table"]).strip()): o for o, b in olds if _kind_of(b) == "table"}
    for at, block in news:
        if _kind_of(block) == "table":
            name = generate._strip_object(str(block["table"]).strip())
            hit = tables_old.get(name)
            if hit is None:
                problems.append(f"новый блок blocks[{at}]: таблица «{name}» (на форме образца её нет)")
            else:
                paired[at] = hit
                used_old.add(hit)
    f_old = [(o, b) for o, b in olds if _kind_of(b) == "fields"]
    f_new = [(a, b) for a, b in news if _kind_of(b) == "fields"]
    matched = _match_fields(f_old, f_new)
    for at, _block in f_new:
        if at not in matched:
            problems.append(f"новый блок blocks[{at}]: поля {', '.join(_word(_entry(e)[0]) for e in desc['blocks'][at]['fields'])} не стоят ни в одном блоке образца")
        else:
            paired[at] = matched[at]
            used_old.add(matched[at])
    new_everywhere = set(_keys_in(desc["blocks"]))
    for o, b in olds:
        if o not in used_old and _kind_of(b) == "fields" and not ({_entry(e)[0] for e in b["fields"]} & new_everywhere):
            used_old.add(o)  # блок, все поля которого убраны из описания, — удаление этих полей
            for entry in b["fields"]:
                key = _entry(entry)[0]
                found = shell.fields.get(key)
                if found is None:
                    problems.append(f"blocks[{o}] образца: убранное поле {_word(key)} на форме не найдено — убирать нечего")
                else:
                    ch.removes.append((key, found, f"blocks[{o}] образца"))
    for o, b in olds:
        if o not in used_old:
            kind = _kind_of(b)
            names = (", ".join(_word(_entry(e)[0]) for e in b["fields"]) if kind == "fields" else
                     f"«{b['table']}»" if kind == "table" else f"«{kind}»")
            problems.append(f"убранный блок образца blocks[{o}]: {names}")
    order = [paired[a] for a, _b in news if a in paired]
    if order != sorted(order):
        problems.append("блоки идут в ином порядке, чем у образца (перестановка блоков)")
    old_keys = set(_keys_in(old["blocks"]))
    for at, block in f_new:
        if at not in matched:
            continue
        before = old["blocks"][matched[at]]
        _fields_diff(desc, ch, shell, block, before, at, old_keys, problems, bound or {})
    for at, block in news:
        if _kind_of(block) == "table" and at in paired:
            _table_diff(ch, shell, obj, block, old["blocks"][paired[at]], at, problems)
    return ch


def _fields_diff(desc, ch, shell, block, before, at, old_keys, problems, bound):
    where = f"blocks[{at}]"
    if block.get("columns", 1) != before.get("columns", 1):
        problems.append(f"{where}: columns {block.get('columns', 1)} вместо {before.get('columns', 1)} у образца (смена числа колонок сетки)")
    if block.get("align") != before.get("align"):
        problems.append(f"{where}: align {block.get('align')!r} вместо {before.get('align')!r} у образца: выравнивание колонки надписей бережный режим не применяет (форма осталась бы прежней молча)")
    columns = before.get("columns", 1)
    new = [_entry(e) for e in block["fields"]]
    old = [_entry(e) for e in before["fields"]]
    old_map = dict(old)
    new_keys = [k for k, _o in new]
    if len(set(new_keys)) != len(new_keys):
        problems.append(f"{where}: поле названо дважды")
    common_new = [k for k in new_keys if k in old_map]
    common_old = [k for k, _o in old if k in set(new_keys)]
    if common_new != common_old:
        problems.append(f"{where}: поля идут в ином порядке, чем у образца (перестановка полей): {', '.join(_word(k) for k in common_new)} вместо {', '.join(_word(k) for k in common_old)}")
    for key, entry in new:
        if key in old_map:
            _kept_diff(where, key, entry, old_map[key], problems)
            continue
        if key in old_keys:
            problems.append(f"{where}: поле {_word(key)} стоит в образце в другом месте (другой блок, рамка или страница закладок): поле, переехавшее между блоками, бережный режим не переносит")
            continue
        if key in bound or key in shell.fields:
            seen = bound.get(key) or [(shell.fields[key].name, "TextBox")]
            listed = ", ".join(f"{'надпись' if kind == 'Label' else 'элемент'} «{name}» ({kind})" for name, kind in seen)
            problems.append(f"{where}: поле {_word(key)} на форме есть: реквизит уже привязан — {listed}; второго такого же (двойника) бережный режим не ставит")
            continue
        extra = sorted(k for k in ("height", "anchors", "control", "choice_list", "multi_line") if entry.get(k) is not None)
        if extra:
            problems.append(f"{where}: у нового поля {_word(key)} названо {', '.join(extra)}: место и привязки нового поля бережный режим берёт по соседу того же типа (ширину — `width` — принимает); "
                            "прочее ставят после, в `tune`, по имени элемента, которое назовёт отчёт")
        at_new = new_keys.index(key)
        prev = next((k for k in reversed(new_keys[:at_new])), None)
        if prev is None:
            problems.append(f"{where}: поле {_word(key)} — первое в блоке: встать «после предыдущего поля» не за кем; поставьте его после первого поля либо --relayout")
            continue
        after = prev
        if columns > 1:
            # сетка из нескольких колонок: место по ячейке, а не «после предыдущего»: под ячейкой `k − columns`; вставка в середину сдвинула бы ячейки
            # остальных полей — отказ; ячейка первой строки встала бы справа от соседа, а `after` ставит только строкой ниже — отказ
            if any(k in old_map for k in new_keys[at_new + 1:]):
                problems.append(f"{where}: поле {_word(key)} стоит в середине сетки из {columns} колонок: ячейки остальных полей сдвинулись бы, а бережный режим ставит только в конец блока")
                continue
            if at_new < columns:
                problems.append(f"{where}: поле {_word(key)} — в первой строке сетки из {columns} колонок: ячейку справа от соседа операция `after` не ставит (только строкой ниже ячейки над)")
                continue
            after = new_keys[at_new - columns]
        ch.adds.append((key, entry, after, where, new_keys))
    for key, _o in old:
        if key in set(new_keys):
            continue
        found = shell.fields.get(key)
        if found is None:
            problems.append(f"{where}: убранное поле {_word(key)} на форме не найдено — убирать нечего")
        else:
            ch.removes.append((key, found, where))


def _kept_diff(where, key, entry, was, problems):
    """Поле осталось в блоке: подпись и ширина — как у образца, прочие ключи не названы."""
    cap_new, cap_old = entry.get("caption"), was.get("caption")
    if (cap_new is None) != (cap_old is None) or (cap_new is not None and not shell_mod.same_text(cap_new, cap_old)):
        problems.append(f"{where}: подпись поля {_word(key)} иная, чем у образца ({cap_old!r} → {cap_new!r}): смену подписи у оставшегося поля бережный режим не делает "
                        "(set_caption правит надпись, но ширина её места от текста не пересчитывается)")
    if entry.get("width") != was.get("width"):
        problems.append(f"{where}: ширина поля {_word(key)} иная, чем у образца ({was.get('width')} → {entry.get('width')}): бережный режим размер оставшегося поля не меняет")
    extra = sorted(k for k in ("height", "anchors", "control", "props", "font", "choice_list", "multi_line") if entry.get(k) is not None and entry.get(k) != was.get(k))
    if extra:
        problems.append(f"{where}: у оставшегося поля {_word(key)} названо {', '.join(extra)}: образец этого не несёт, а бережный режим оставшегося поля не правит")


def _table_diff(ch, shell, obj, block, before, at, problems):
    where = f"blocks[{at}]"
    name = generate._strip_object(str(block["table"]).strip())
    if block.get("bar", generate.TABLE_BAR_DEFAULT) != before.get("bar", generate.TABLE_BAR_DEFAULT):
        problems.append(f"{where}: bar у таблицы «{name}» иной, чем у образца: панель таблицы бережный режим не ставит и не убирает")
    old_cols, new_cols = _columns_of(before, obj), _columns_of(block, obj)
    if old_cols is None or new_cols is None:
        problems.append(f"{where}: у таблицы «{name}» колонки взять неоткуда (табличной части нет в выгрузке)")
        return
    if len(set(new_cols)) != len(new_cols):
        problems.append(f"{where}: колонка названа дважды")
        return
    found = shell.tables.get(name)
    if found is None:
        problems.append(f"{where}: таблицы «{name}» в исходной форме нет — колонки добавлять некуда")
        return
    common_new = [c for c in new_cols if c in old_cols]
    common_old = [c for c in old_cols if c in new_cols]
    if common_new != common_old:
        problems.append(f"{where}: колонки таблицы «{name}» идут в ином порядке, чем у образца (перестановка колонок)")
    have = {c.key: c for c in found.columns if c.key is not None}
    add, drop = [], []
    for column in new_cols:
        if column in old_cols:
            continue
        if column in have:
            problems.append(f"{where}: колонка «{column}» в таблице «{found.name}» есть, а образец её не взял — двойника бережный режим не ставит")
        else:
            add.append(column)
    for column in old_cols:
        if column in new_cols:
            continue
        if column not in have:
            problems.append(f"{where}: убранная колонка «{column}» в таблице «{found.name}» не найдена")
        else:
            drop.append(have[column].name)
    if add or drop:
        ch.columns.append((found, name, add, drop, where))


# ── Операции ──────────────────────────────────────────────────────────────────────────────────

def _field_blocks(blocks):
    """Блоки `fields` верхнего уровня как `[(ключи полей, число колонок сетки)]`."""
    return [(tuple(_entry(e)[0] for e in b["fields"]), b.get("columns", 1)) for b in blocks if isinstance(b, dict) and "fields" in b]


def _explained_by_cells(want, got, cells):
    """Расхождение описания и прочтения формы объяснено полями в свободных клетках (`cells` — `[(ключ поля, ключ соседа)]`) либо `None`.

    Объяснено, если порядок полей тот же, а каждый блок описания либо стоит в форме как есть, либо целиком лежит в блоке формы, куда слились
    блоки с полем из клетки или её соседом (без клеток `cells` пуст, и объяснить нечем). Любое иное расхождение (поле в чужом блоке, иной порядок, чужая сетка)
    не объясняется.
    """
    special = {k for pair in cells for k in pair}
    flat = lambda blocks: [k for keys, _c in blocks for k in keys]
    if flat(want) != flat(got):
        return None
    touched = lambda blocks: [b for b in blocks if special & set(b[0])]
    merged = {k for b in touched(got) for k in b[0]}
    if not all(set(b[0]) <= merged for b in touched(want)):
        return None
    if any(b not in got and not set(b[0]) <= merged for b in want if not special & set(b[0])):
        return None
    return ", ".join(f"«{k[1]}»" for k, _n in cells) + " стоит в свободной клетке соседнего столбца сетки, а не новой строкой ниже — блоки поля описания и сетки шапки слились"


def _show(blocks):
    return "; ".join(f"[{', '.join(k[1] for k in keys)}]" + (f"×{columns}" if columns > 1 else "") for keys, columns in blocks)


def _scope(desc, doc, config):
    """Объект, роль и реквизиты формы — как у `generate.plan_notes`: `(обработка?, объект, роль, реквизиты формы, причина «объекта нет»)`."""
    if desc["kind"] == generate.PROCESSING:
        obj, form, no_object = generate._processing_scope(desc, doc, config)
        return True, obj, None, form, no_object
    if not isinstance(config, metadata.Config):
        raise GenerateError("config — выгрузка конфигурации (metadata.load)")
    obj = generate._object_of(desc, doc, config)
    if obj.kind != generate.KINDS[desc["kind"]]:
        raise GenerateError(f"вид «{desc['kind']}» — {generate.KIND_WORDS[generate.KINDS[desc['kind']]]}, а объект «{obj.full_name}» — "
                            f"{generate.KIND_WORDS.get(obj.kind, obj.kind)}")
    role = desc.get("form_use")
    if role is not None:
        try:
            obj.attributes_for(role)
        except metadata.MetadataError as e:
            raise GenerateError(f"form_use: {e}") from None
    return False, obj, role, None, ""


def _bind_ops(spec, name, role):
    """`bind` нового поля и свойства при нём — как `generate._ops_of` (кроме места)."""
    form_use = {"form_use": role} if role else {}
    ops = []
    if spec.attribute is not None:
        ops.append({"op": "bind", "element": name, "attribute": spec.attribute, "copy_type": True})
    else:
        ops.append({"op": "bind", "element": name, "data": spec.data, **form_use})
    if spec.choice and "choice_button" not in (spec.props or {}):
        ops.append({"op": "set_property", "element": name, "name": "choice_button", "value": True})
    if spec.tip is not None and "tool_tip" not in (spec.props or {}):
        ops.append({"op": "set_property", "element": name, "name": "tool_tip", "value": spec.tip})
    for prop, value in (spec.props or {}).items():
        ops.append({"op": "set_property", "element": name, "name": prop, "value": value})
    if spec.font:
        ops.append({"op": "set_font", "element": name, **spec.font})
    return ops


class _Run:
    """Рабочая копия исходной формы: группы операций применяются по одной, чтобы место следующей группы считалось от результата предыдущей."""

    def __init__(self, doc, config):
        self.doc, self.config, self.ops, self.words = copy.deepcopy(doc), config, [], []
        self.ref_notes = []  # привязки пары, взятые у пары-образца (последняя попытка `_pair_ops`)
        self.free_cells = []  # имена полей, вставших в свободную клетку соседнего столбца сетки (`place._free_cell`)
        self.cell_keys = []  # то же по ключам описания: `(ключ поля, ключ соседа)`
        self.cell_used = False  # последняя попытка `_pair_ops` поставила поле в такую клетку

    def names(self):
        return set(base.element_names(self.doc))

    def test_group(self, group, verify=None):
        """Группа операций на копии, рабочая копия не меняется: `(ok, журнал | причина, документ)`; `verify(документ) → причина | None`."""
        try:
            with old_versions.off():
                made, _bsl, log = edit.apply(copy.deepcopy(self.doc), copy.deepcopy(group), config=self.config)
        except EditError as e:
            return False, str(e), None
        if verify is not None:
            why = verify(made)
            if why:
                return False, why, None
        return True, log, made

    def commit(self, group, made):
        """Принять проверенную группу: результат становится рабочей копией, операции — частью перечня."""
        self.doc = made
        self.ops += group

    def try_group(self, group, verify=None):
        """Группа операций на копии: `(ok, журнал | причина)`; удачная (и прошедшая `verify(документ) → причина | None`) остаётся в рабочей копии и в перечне."""
        ok, said, made = self.test_group(group, verify)
        if ok:
            self.commit(group, made)
        return ok, said


def label_prefix(shell):
    """Приставка имён надписей исходной формы (`ПрефиксПоле` — «Префикс»): общая у всех её пар, имя надписи = приставка + имя поля; иначе — «Надпись» (правило конструктора)."""
    prefixes = {found.label.name[:-len(found.name)] for found in shell.fields.values()
                if found.type == "TextBox" and found.label is not None and found.label.name.endswith(found.name)
                and len(found.label.name) > len(found.name)}
    fixed = sorted(prefixes)
    return fixed[0] if len(fixed) == 1 else "Надпись"


def _ref_pair(scan, order_keys, at, above, text="", doc=None):
    """Пара-образец для колонки надписей и поля: ячейка над (сетка), ближайшая предыдущая пара блока, ближайшая следующая, любая пара исходной формы; из них — первая, чья надпись
    вмещает новую подпись `text` (колонка надписей блока, а не короткая «от» между полями), иначе первая из найденных; нет пары — `None`."""
    candidates = ([above] if above is not None else []) + list(reversed(order_keys[:at])) + list(order_keys[at + 1:]) + list(scan.fields)
    pairs = []
    for key in candidates:
        found = scan.fields.get(key)
        if found is not None and found.type == "TextBox" and found.label is not None and found.box is not None and found not in pairs:
            pairs.append(found)
    # надпись-заголовок (выше поля больше чем на `PAIR_DY` — «ПРИМЕР» у номера документа) колонку надписей не задаёт: у образца берутся пары с надписью высоты поля
    plain = [f for f in pairs if abs((f.label.box[3] - f.label.box[1]) - (f.box[3] - f.box[1])) <= place.PAIR_DY]
    pairs = plain or pairs
    for found in pairs:
        need = place._need("Label", 0, text, textwidth.element_font(found.label.node, doc))[0] if text else 0
        if found.label.box[2] - found.label.box[0] >= need:
            return found
    return pairs[0] if pairs else None


def _items(doc):
    form = layout.read(doc)
    return form, {i.name: i for h in form.holders.values() for i in h.children if i.name}


def _verify_pair(doc, name, label):
    """Пара встала парой: надпись на строке поля и слева от него, ничто видимое на них не наезжает (рамка, внутри которой они стоят, не помеха), всё внутри формы."""
    form, items = _items(doc)
    field = items[name]
    mine = [field] + ([items[label]] if label else [])
    if label:
        lab = items[label]
        height = min(lab.box[3] - lab.box[1], field.box[3] - field.box[1])
        if shell_mod.overlap(lab.box[1], lab.box[3], field.box[1], field.box[3]) * 2 < height:
            return f"надпись «{label}» не на строке поля «{name}» (надпись {tuple(lab.box)}, поле {tuple(field.box)})"
        if lab.box[2] > field.box[0] + shell_mod.LABEL_OVERLAP:
            return f"надпись «{label}» {tuple(lab.box)} не слева от поля «{name}» {tuple(field.box)}: она длиннее колонки надписей"
    for new in mine:
        x0, y0, x1, y1 = new.box
        if x0 < 0 or y0 < 0 or x1 > form.width or y1 > form.height:
            return f"«{new.name}» {tuple(new.box)} выходит за форму {form.width}×{form.height}"
        for other in form.holders[0].children:
            if not other.visible or other in mine or other.name in (name, label):
                continue
            ox0, oy0, ox1, oy1 = other.box
            if min(x1, ox1) - max(x0, ox0) <= 0 or min(y1, oy1) - max(y0, oy0) <= 0:
                continue
            if other.type in ("GroupBox", "Panel") and ox0 <= x0 and oy0 <= y0 and x1 <= ox1 and y1 <= oy1:
                continue
            return f"«{new.name}» {tuple(new.box)} наезжает на «{other.name}» ({other.type}) {tuple(other.box)}"
    return None


VERSION_MARK = "общий блок оформления узла"
OTHER_COLUMN_DX = 100   # на сколько px левый край поля пары-образца должен отстоять от места, чтобы считать его другим столбцом (ручной разнобой x и сдвиг под длинную надпись — меньше)


LETTER_GROUPS = {"S": "string", "N": "number", "D": "date", "B": "bool", "#": "ref"}
CLASS_GROUPS = {"string": "string", "decimal": "number", "dateTime": "date", "boolean": "bool", "catalog": "ref", "document": "ref", "enum": "ref"}
STANDARD_GROUPS = {"Наименование": "string", "Дата": "date", "Родитель": "ref", "Владелец": "ref"}
CODE_GROUPS = {"String": "string", "Number": "number"}


def value_group(obj, spec):
    """Вид значения нового поля: `string`, `number`, `date`, `bool`, `ref` либо `None` (составной или неизвестный тип)."""
    if spec.control == "CheckBox":
        return "bool"
    if obj is None:
        return None
    attr = next((a for a in obj.attributes if a.name == spec.name), None)
    if attr is not None:
        try:
            return CLASS_GROUPS.get(datapath.datatype.type_class(attr))
        except datapath.datatype.TypeNotWritten:
            return None
    if spec.name in ("Код", "Номер"):
        return CODE_GROUPS.get((obj.std_types.get(spec.name) or (None,))[0])
    return STANDARD_GROUPS.get(spec.name)


def _field_group(field):
    """Вид значения поля исходной формы по первому блоку описателя типа; `None` — не определён."""
    content = field.node.get("content") if isinstance(field.node, dict) else None
    pattern = content.get("pattern") if isinstance(content, dict) else None
    types = pattern.get("types") if isinstance(pattern, dict) else None
    first = types[0] if isinstance(types, list) and types and isinstance(types[0], dict) else {}
    return LETTER_GROUPS.get(first.get("kind"))


class _Subset:
    def __init__(self, fields):
        self.fields = fields


def _like_donors(doc, obj, template, order_keys, at, above, text, group=None):
    """Доноры для формы другой версии: `(поле, его надпись или None, вид значения донора совпал)` — копия соседа того же вида элемента ставится вместо шаблона.

    Донор — сосед с тем же видом значения, что у нового реквизита (`group`): для поля ввода — пара-образец среди таких полей, для флажка — флажок. Если
    такого нет, берётся любой сосед того же вида элемента, а его поведение и тип копия всё равно сбрасывает (`like_clean`). Нет и такого — `None`."""
    scan = shell_mod.scan(doc, obj)
    if template == "CheckBox":
        boxes = [f for f in scan.fields.values() if f.type == "CheckBox"]
        return (boxes[0].name, None, True) if boxes else None
    same = {key: f for key, f in scan.fields.items() if group is not None and _field_group(f) == group}
    for pool, matched in ((_Subset(same), True), (scan, False)):
        ref = _ref_pair(pool, order_keys, at, above, text, doc) if pool.fields else None
        if ref is not None:
            return ref.name, ref.label.name, matched
    return None


def _pair_ops(run, obj, spec, name, label, after, extra, order_keys, at, above, role, problems_out, copy_as=True, date_mode="stand", cell=True):
    """Операции одной пары по рабочей копии: поле — `add_element` по соседу (место, сдвиг, привязки — `place`), затем колонка и ширина как у пары-образца (`move_element`, только если
    место поля иное), затем надпись — на строке поля, в колонке надписей образца (`add_element` с `box`). Нет образца — слова в `problems_out`, операций нет."""
    template = "CheckBox" if spec.control == "CheckBox" else "TextBox"
    run.ref_notes = []
    add = {"op": "add_element", "template": template, "name": name, "after": after, "search": False, **extra,
           **({"caption": spec.text} if template == "CheckBox" else {})}
    if not cell:
        add["cell"] = False       # свободная клетка соседнего столбца не подошла (пара в ней не встала): место — под соседом
    donors = None
    try:
        with old_versions.off():  # форма старой версии — копия соседа (`like`), а не шаблон, сведённый к её версии
            tmp, _b, placed_log = edit.apply(copy.deepcopy(run.doc), [add], config=run.config)
    except EditError as e:
        # Форма старой версии: шаблоны (версия 16) не встают, дорога — копия соседа того же вида (`like`): версия и оформление приходят от него
        if VERSION_MARK not in str(e):
            raise
        donors = _like_donors(run.doc, obj, template, order_keys, at, above, spec.text, value_group(obj, spec))
        if donors is None:
            raise
        add = {**add, "like": donors[0], "like_clean": True}
        group_note = (f"форма другой версии общего блока, чем шаблоны: поле «{name}» — копия соседа «{donors[0]}» (`like`: версия и оформление — соседа"
                      + (f", надпись — копия «{donors[1]}»" if donors[1] else "") + "); "
                      + ("вид значения соседа тот же" if donors[2] else "соседа с таким же видом значения нет, взят другой") + "; поведение соседа "
                      "(только просмотр, доступность, кнопки, маска, формат) возвращено к умолчаниям, тип значения и квалификаторы пишет привязка к реквизиту")
        run.ref_notes.append(group_note)
        with old_versions.off():
            tmp, _b, placed_log = edit.apply(copy.deepcopy(run.doc), [add], config=run.config)
    run.cell_used = place.FREE_CELL_MARK in "".join(placed_log)
    form, items = _items(tmp)
    field = items[name]
    left, top, right, bottom = field.box
    all_coefs = layout.coefficients(form, hide=False)
    coefs = all_coefs.get(field.index)
    v = "bottom" if coefs is not None and coefs[0] == 1 else "top"
    group = [add]
    move, label_op = None, None
    anchor_h = "left"
    date_fixed = False
    if template == "TextBox":
        scan = shell_mod.scan(tmp, obj)
        ref = _ref_pair(scan, order_keys, at, above, spec.text, tmp)
        if ref is not None and place.FREE_CELL_MARK in "".join(placed_log) and abs(ref.box[0] - left) > place.COLUMN_DX:
            # поле встало в свободную клетку соседнего столбца (`place._free_cell`): колонку надписей и поле берём у пары этого столбца
            same = [f for f in scan.fields.values() if f.type == "TextBox" and f.label is not None and f.box is not None and f.name != name
                    and abs(f.box[0] - left) <= place.COLUMN_DX]
            if same:
                ref = min(same, key=lambda f: abs(f.box[1] - top))
        if ref is None:
            problems_out.append("в исходной форме нет пары «надпись + поле», по которой взять колонку надписей и поле, — бережный режим её не выдумывает")
            return None
        if getattr(run, "keep_column", False) and place.FREE_CELL_MARK not in "".join(placed_log) and abs(ref.box[0] - left) > OTHER_COLUMN_DX:
            # `add-field`: место открыло строку под соседом, а пара-образец по ширине надписи стоит в другом столбце — пара ушла бы туда, и открытая строка осталась бы пустой
            problems_out.append(f"место открыло строку в столбце x={left}, а пара-образец «{ref.name}» стоит в столбце x={ref.box[0]}: пара ушла бы в чужой столбец, и открытая строка осталась бы пустой")
            return None
        lb, rf = ref.label.box, ref.box
        font = textwidth.element_font(ref.label.node, tmp)
        need = place._need("Label", 0, spec.text, font)[0]
        # Надпись — «текст + запас» (запас рамки образца за текстом; у выровненной вправо или по центру надписи его нет), поле — не ближе
        # видимого зазора «конец текста → поле»: у пары-образца или нижней границы нормы вида (что больше), и не ближе зазора рамок образца.
        column_pairs = [(f.label.name, f.label.node, f.label.box, f.box[0]) for f in scan.fields.values()
                        if f.type == "TextBox" and f.label is not None and f.label.box is not None and f.box is not None
                        and abs(f.label.box[0] - lb[0]) <= place.COLUMN_DX]
        need_gap, slack, gap_words, _exact = place.column_gap(tmp, None, column_pairs)
        align = textgap.alignment(ref.label.node)
        label_w = max(lb[2] - lb[0], need + (slack if align == "Left" else 0))
        gap = rf[0] - lb[2]
        left = max(rf[0], lb[0] + label_w + max(gap, 0))
        new_text = textwidth.measure(spec.text, font)
        if need_gap is not None:
            ended = textgap.text_end(lb[0], label_w, new_text.px, align)
            said = f"надпись «{label}»: {gap_words}" + ("" if new_text.exact else f"; текст новой надписи по оценке ширины ({new_text.why})")
            if ended + need_gap > left:
                left = ended + need_gap
                run.ref_notes.append(f"{said} — поле «{name}» сдвинуто до x={left}")
            else:
                run.ref_notes.append(f"{said} — у новой пары видимый зазор {left - ended} px")
        else:
            run.ref_notes.append(f"надпись «{label}»: {gap_words}")
        right = rf[2]
        label_top = top + (lb[1] - rf[1])
        label_op = {"op": "add_element", "template": "Label", **({"like": donors[1], "like_clean": True} if donors and donors[1] else {}), "name": label, "box": [lb[0], label_top, label_w, lb[3] - lb[1]], "anchor": {"h": "left", "v": v}, "caption": spec.text}
        anchor_h = "stretch" if ref.behaviour == layout.GROWS else "left"
        # Колонка ведёт себя иначе, чем «растягивается» и «остаётся на месте» (доли, сдвиг вправо): привязки пары копируются у пары-образца, а не пишутся ролью `left`.
        label_coefs = all_coefs.get(ref.label.index)
        label_beh = layout.horizontal_behaviour(label_coefs[2], label_coefs[3]) if label_coefs else None
        if copy_as and label_beh not in (None, layout.STANDS):
            label_op["anchor"]["h"] = {"as": ref.label.name}
            run.ref_notes.append(f"надпись «{label}»: привязки как у «{ref.label.name}» (при растяжении окна колонка надписей {layout.behaviour_words(label_beh)})")
        date_fixed = False
        if spec.date is not None and not spec.width and date_mode == "sample":
            run.ref_notes.append(f"поле «{name}» на дату: умолчание даты сужало растяжение формы — взяты ширина и привязки образца")
        if spec.date is not None and not spec.width and date_mode != "sample":
            # Поле даты: ширина — поле даты того же состава на форме либо самая частая ширина в корпусе, не растягивается; левый край — колонка полей образца
            # (либо после надписи, выше), правый идёт за левым. Вариант «stand» — поле остаётся на месте, «role» — привязки образца (поле сдвигается вместе с колонкой).
            column = [f for f in scan.fields.values() if f.type == "TextBox" and textgap.date_composition(f.node)
                      and abs(f.box[0] - rf[0]) <= place.COLUMN_DX]
            source = min(column, key=lambda f: abs(f.box[1] - top)) if column else ref
            width, date_words = place.date_width(tmp, spec.date, None, (form.holders[0].node, field.page, left, top))
            if width is None:
                run.ref_notes.append(f"поле «{name}» на дату: ширина как у образца — {date_words}")
            else:
                edge = form.holders[0].edge(field.page)[0]
                margin = place._norm(tmp, None, "field_right_margin")[0]
                room = edge - (max(edge - rf[2], 0) if margin is None else margin)
                if left + width > room:
                    if room - left < generate.PLATFORM_MIN_FIELD_W:
                        problems_out.append(f"поле даты «{name}» шириной {width} не помещается: от x={left} до края родителя с отступом {room - left} px")
                        return None
                    date_words += f"; ширина {width} → {room - left}: правее нет места до края родителя с отступом ({room})"
                    width = room - left
                date_fixed = True
                right = left + width
                run.ref_notes.append(f"поле «{name}»: {date_words}; не растягивается")
                anchor_h = "left"
                if date_mode == "role" and source.behaviour == layout.GROWS:
                    raise EditError(f"привязки образца «{source.name}» растягивают поле — ширина умолчания {width} при них не держится")
                if date_mode == "role" and copy_as and source.behaviour in (layout.MOVES, layout.PARTLY):
                    anchor_h = {"as": source.name}
                    if source.label is not None and any(r is not None and r.obj == source.label.index
                                                         for border in (2, 3) for r in items[source.name].rules[border]):
                        anchor_h["with"] = {source.label.name: label}
                    run.ref_notes.append(f"поле «{name}»: привязки как у «{source.name}» ({'поле даты в столбце' if column else 'образец'}; при растяжении окна колонка {layout.behaviour_words(source.behaviour)} — "
                                         "поле идёт с колонкой, ширина умолчания)")
                elif date_mode == "role":
                    run.ref_notes.append(f"поле «{name}»: привязки образца «{source.name}» — при растяжении окна образец {layout.behaviour_words(source.behaviour)}; поле даты остаётся на месте")
        elif copy_as and ref.behaviour in (layout.MOVES, layout.PARTLY) and not spec.width:
            anchor_h = {"as": ref.name}
            if any(r is not None and r.obj == ref.label.index for border in (2, 3) for r in items[ref.name].rules[border]):
                anchor_h["with"] = {ref.label.name: label}      # правило поля к надписи колонки идёт к новой надписи
            run.ref_notes.append(f"поле «{name}»: привязки как у «{ref.name}» (при растяжении окна колонка полей {layout.behaviour_words(ref.behaviour)})")
    if spec.width:
        right = left + spec.width
        anchor_h = "left"
    if (left, right) != (field.box[0], field.box[2]) or isinstance(anchor_h, dict) or (template == "TextBox" and date_fixed):
        if right - left < generate.PLATFORM_MIN_FIELD_W:
            problems_out.append(f"поле «{name}» осталось бы шириной {right - left} px (меньше минимума платформы {generate.PLATFORM_MIN_FIELD_W}): надпись «{spec.text}» занимает колонку надписей")
            return None
        move = {"op": "move_element", "name": name, "box": [left, top, right - left, bottom - top], "anchor": {"h": anchor_h, "v": v}}
        group.append(move)
    if label_op is not None:
        if isinstance(move, dict) and isinstance(move["anchor"]["h"], dict):
            group.insert(1, label_op)  # правило поля к надписи колонки называет новую надпись: она уже должна стоять
        else:
            group.append(label_op)
    return group + _bind_ops(spec, name, role)


def _cell_words(doc, name, after):
    """Слова о поле, вставшем в свободную клетку соседнего столбца сетки: какая клетка и чем она отличается от «под соседом»."""
    found = _items(doc)[1]
    field, nbr = found.get(name), found.get(after)
    if field is None or nbr is None:
        return ""
    return (f"; {place.FREE_CELL_MARK}: столбец x={field.box[0]}, строка y={field.box[1]} — клетка рядом со строкой «{after}», а не новая строка под ней; "
            "форма не выросла")


def _place_pair(run, obj, key, spec, after, role, notes, problems, where, prefix, order_keys, at, above):
    """Пара «надпись + поле» (флажок — один элемент) в блок: одна ступень лестницы обычное → shrink → grow на пару целиком; после постановки —
    проверка геометрии пары, иначе следующая ступень или отказ."""
    used = run.names()
    name = generate._unique(spec.field_name, used)
    label = generate._unique(prefix + spec.field_name, used | {name}) if spec.control != "CheckBox" else None
    refusals = []

    def check(doc):
        """Пара встала парой и не ограничила растяжение формы (сужение, объяснённое ужатием таблицы, не в счёт)."""
        why = _verify_pair(doc, name, label)
        if why:
            return why
        narrowed = limits.unforgiven(limits.compare(run.doc, doc))
        return limits.narrowed_words(narrowed) if narrowed else None

    date_modes = place.DATE_ROLES if spec.date is not None and not spec.width else (None,)
    names = [n for n in (name, label) if n]
    for mode, extra, words in LADDER:
        found = []         # варианты, прошедшие проверку: (слова о привязках, группа, документ, проверка движка, вариант даты, отброшенная копия `as`)
        for cell in (True, False):
            cell_tried = False   # попытка поставила поле в свободную клетку соседнего столбца: если пара в ней не встала, место — под соседом
            for date_mode in date_modes:
                copied = None      # привязки пары-образца (`as`), которые не прошли проверку пределов
                for copy_as in (True, False):
                    try:
                        group = _pair_ops(run, obj, spec, name, label, after, extra, order_keys, at, above, role, refusals, copy_as, date_mode or "stand", cell)
                    except EditError as e:
                        refusals.append((f"дата «{place.DATE_WORDS[date_mode]}»: " if date_mode else "") + f"{mode}: {e}")
                        break
                    if group is None:
                        problems.append(f"{where}: поле {_word(key)} не встало на форму ни одним способом — " + "; ".join(refusals))
                        return None, None
                    as_notes = list(run.ref_notes)
                    cell_tried = cell_tried or run.cell_used
                    ok, said, made = run.test_group(group, verify=check)
                    verdict = candidates.assess(run.doc, made, names) if ok else None
                    if ok and verdict is not None and verdict.hard:
                        ok, said = False, "; ".join(verdict.hard[:2])
                    if ok:
                        found.append((as_notes, group, made, verdict, date_mode, copied, place.FREE_CELL_MARK in "".join(said)))
                        if verdict is None or verdict.penalty == (0, 0) or not (copy_as and as_notes):
                            break      # привязки без расхождений (либо другого варианта копии нет): перебирать дальше нечего
                        continue       # копия `as` расходится с соседями: вариант с ролями рядом проверяется тоже
                    if copy_as and as_notes:
                        copied = said
                        continue
                    refusals.append((f"дата «{place.DATE_WORDS[date_mode]}»: " if date_mode else "") + f"{mode}: {said}" + (f" (с привязками пары-образца: {copied})" if copied else ""))
                    break
                if found and found[-1][3] is not None and found[-1][3].penalty == (0, 0):
                    break          # вариант даты без расхождений найден
            if found or not cell_tried:
                break
        if found:
            best = min(range(len(found)), key=lambda i: ((0, 0) if found[i][3] is None else found[i][3].penalty, i))
            as_notes, group, made, verdict, date_mode, copied, used_cell = found[best]
            run.commit(group, made)
            if used_cell:
                run.free_cells.append(name)
            rest = [f for i, f in enumerate(found) if i != best and f[3] is not None and f[3].penalty != (0, 0)]
            notes.append(f"поле {_word(key)}: " + (f"надпись «{label}» и поле «{name}»" if label else f"флажок «{name}»") + f" после «{after}» — {words}; "
                         "поле — в колонке полей образца, надпись — на строке поля в колонке надписей"
                         + "".join(f"; {note}" for note in as_notes)
                         + (f"; привязки пары-образца не прошли проверку ({copied}) — взяты роли `left`/`stretch`" if copied else "")
                         + (f"; вариант поля даты «{place.DATE_WORDS[date_mode]}» после отказов: " + "; ".join(r for r in refusals if r.startswith("дата "))
                            if date_mode not in (None, "stand") else "")
                         + (f"; проверено на модели раскладки при размерах окна меньше и больше проектного: выравнивание с соседями сохраняется"
                            if verdict is not None and verdict.penalty == (0, 0) else "")
                         + (f"; на модели раскладки выравнивание с соседями расходится ({'; '.join(verdict.notes[:2])})"
                            + ("; другого варианта нет" if len(found) == 1 else "") if verdict is not None and verdict.penalty != (0, 0) else "")
                         + (f"; отброшены варианты с большим расхождением: {len(rest)}" if rest and verdict is not None and verdict.penalty != (0, 0) else "")
                         + (_cell_words(made, name, after) if used_cell else ""))
            return name, label
    hint = (" (сужение предела: выход — операция `set_anchors` в `tune` с явной ролью или образцом `{\"as\": \"<имя элемента>\"}` у новой пары)"
            if any(limits.NARROWED in r for r in refusals) else "")
    problems.append(f"{where}: поле {_word(key)} не встало на форму ни одним способом — " + "; ".join(refusals) + hint)
    return None, None


def _top_keys(desc):
    """Ключи полей блоков `fields` верхнего уровня по порядку описания (блоки не различаются: слитые и разделённые блоки дают тот же перечень)."""
    return [_entry(e)[0] for block in desc.get("blocks") or () if isinstance(block, dict) and "fields" in block for e in block["fields"]]


def _tokens(desc, skip=()):
    """Верхний уровень описания в порядке чтения: поле — `("поле", ключ)`, любой прочий блок — `("блок", номер среди прочих)`; `skip` — ключи, которые не считаются."""
    out, other = [], 0
    for block in desc.get("blocks") or ():
        if isinstance(block, dict) and "fields" in block:
            out += [("поле", key) for key in (_entry(e)[0] for e in block["fields"]) if key not in skip]
        else:
            out.append(("блок", other))
            other += 1
    return out


def _grids(desc):
    """`{ключ поля: число колонок сетки его блока}`."""
    return {_entry(e)[0]: block.get("columns", 1) for block in desc.get("blocks") or () if isinstance(block, dict) and "fields" in block for e in block["fields"]}


def edit_problems(before, after, added, place=None):
    """Проверка правки «добавлены только эти поля» (`add-field`): `describe` формы после правки равен `describe` до правки плюс добавленные поля.

    `before`, `after` — описания формы до и после; `added` — имена добавленных реквизитов; `place` — `(поле перед новым или None, поле после нового или None)`, место, которое
    назвала команда. Сверяются: порядок полей и прочих блоков (таблицы, панели, рамки, закладки, табличные документы) относительно друг друга — без добавленных полей он тот же;
    число колонок сетки у прежних полей то же; прочие блоки без изменений; новое поле читается в том же блоке сразу после названного соседа и перед следующим (границы блоков
    сетки могут сместиться, если поле слило или разделило блоки). Возвращает перечень расхождений словами; пусто — правка чистая."""
    gone = {("object", name) for name in added}
    problems = []
    was, now = _top_keys(before), [key for key in _top_keys(after) if key not in gone]
    if was != now:
        lost = [k[1] for k in was if k not in now]
        extra = [k[1] for k in now if k not in was]
        problems.append("поля — " + ("пропали: " + ", ".join(lost) if lost else "") + ("; " if lost and extra else "") + ("появились лишние: " + ", ".join(extra) if extra else "")
                        + ("порядок полей иной" if not lost and not extra else ""))
    elif _tokens(before) != _tokens(after, gone):
        problems.append("поля стоят иначе относительно таблиц, панелей и рамок (поле прочитано по другую сторону блока)")
    for what in sorted(gone - {key for key in _top_keys(after)}):
        problems.append(f"добавленное поле «{what[1]}» не читается на форме")
    cols_before, cols_after = _grids(before), _grids(after)
    mixed = {_entry(e)[0] for block in after.get("blocks") or () if isinstance(block, dict) and "fields" in block
             and gone & {_entry(e)[0] for e in block["fields"]} for e in block["fields"]}      # блок нового поля мог слиться со свободной клеткой — его колонки вправе измениться
    changed = [k[1] for k in cols_before if k in cols_after and k not in mixed and cols_before[k] != cols_after[k]]
    if changed:
        problems.append(f"число колонок сетки изменилось у полей: {', '.join(changed[:5])}")
    others_before = [b for b in before.get("blocks") or () if not (isinstance(b, dict) and "fields" in b)]
    others_after = [b for b in after.get("blocks") or () if not (isinstance(b, dict) and "fields" in b)]
    if others_before != others_after:
        problems.append(f"прочие блоки (таблицы, панели, рамки, закладки) читаются иначе: до {_show_other(others_before)}, после {_show_other(others_after)}")
    if place is not None and len(added) == 1:
        problems += _place_problems(after, ("object", added[0]), place)
    return problems


def _place_problems(after, key, place):
    """Новое поле `key` читается в том же блоке сразу после названного соседа и перед следующим."""
    prev, following = place
    for block in after.get("blocks") or ():
        if not (isinstance(block, dict) and "fields" in block):
            continue
        keys = [_entry(e)[0] for e in block["fields"]]
        if key not in keys:
            continue
        at = keys.index(key)
        got_prev = keys[at - 1][1] if at else None
        got_next = keys[at + 1][1] if at + 1 < len(keys) else None
        wrong = []
        if prev is not None and got_prev != prev:
            wrong.append(f"перед ним прочитано {'«' + got_prev + '»' if got_prev else 'ничего (первое поле блока)'}, а место называло «{prev}»")
        if following is not None and got_next != following:
            wrong.append(f"после него прочитано {'«' + got_next + '»' if got_next else 'ничего (последнее поле блока)'}, а место называло «{following}»")
        return [f"новое поле «{key[1]}» прочитано не там, где названо место: " + "; ".join(wrong)] if wrong else []
    return []


def _show_other(blocks):
    return ", ".join(next((f"{k} {v}" for k, v in b.items() if k in generate.BLOCKS and not isinstance(v, (list, dict))), next(iter(b), "?")) for b in blocks) or "нет"


def plan_notes(desc, doc, config, norms, heights=None, verdict=None, edit_of=None, edit_place=None):
    """Описание поверх формы человека → `(операции, заметки)`; отказ — `GenerateError` со всеми причинами. Операции применимы к `doc` подряд (место нового
    поля посчитано на рабочей копии: тем же перечнем `edit.apply` даст ту же форму)."""
    generate.check_description(desc)
    old = verdict.old if verdict is not None else describe_mod.describe(copy.deepcopy(doc), config, **_hints(desc)).description
    processing, obj, role, form, no_object = _scope(desc, doc, config)
    try:
        shell = shell_mod.scan(doc, obj)
    except EditError as e:
        raise GenerateError(f"исходная форма не разобрана для бережной правки ({e}); {WAY_OUT}") from None
    problems = []
    lform = layout.read(doc)
    ch = diff(desc, old, shell, obj, (lform.width, lform.height), problems, all_bindings(doc, obj))
    resolver = generate._Resolver(obj, role, config, form, shell)
    if processing:
        resolver.no_object = no_object
    attribute_ops = []
    if processing and "attributes" in desc:
        declared = []
        attribute_ops = form.declare(desc["attributes"], "attributes", declared)
        problems += declared
    specs = {}
    for key, entry, _after, where, _order in ch.adds:
        spec = resolver._field({k: v for k, v in entry.items() if k in generate.FIELD_KEYS}, f"{where}/{_word(key)}")
        if spec is not None:
            specs[key] = spec
    problems += resolver.problems
    if problems:
        raise GenerateError("бережный режим: разница описаний не выражается операциями без перекладки формы — "
                            + "; ".join(f"{i}) {p}" for i, p in enumerate(problems, 1)) + f". {WAY_OUT}")
    run = _Run(doc, config)
    run.keep_column = edit_of is not None
    notes = [f"исходная форма — форма человека: {len(shell.fields)} полей и {len(shell.tables)} таблиц на данные остаются на своих местах, двигается только разница"]
    ok, said = run.try_group(attribute_ops) if attribute_ops else (True, None)
    if not ok:
        problems.append(f"реквизиты формы: {said}")
    for key, found, where in ch.removes:
        group = [{"op": "remove_element", "name": found.name}]
        if found.label is not None:
            group.insert(0, {"op": "remove_element", "name": found.label.name})
        ok, said = run.try_group(group)
        if not ok:
            problems.append(f"{where}: поле {_word(key)} не убирается: {said}")
        else:
            notes.append(f"убрано поле {_word(key)}: «{found.name}»" + (f" и надпись «{found.label.name}»" if found.label is not None else "")
                         + " — место осталось пустым, ряды ниже не подтянуты")
    for table, name, add, drop, where in ch.columns:
        columns = {}
        if add:
            seen = len(resolver.problems)
            block = resolver._table({"table": f"{datapath.OBJECT_WORD}.{name}", "columns": list(add), "bar": False}, where)
            columns = {c[0]: c for c in (block.columns if block is not None else [])}
            problems += resolver.problems[seen:]
        group = []
        for column in add:
            if column in columns:
                cname, header, data, template = columns[column]
                group.append({"op": "add_column", "table": table.name, "name": cname, "header": header, "data": data, "template": template,
                              **({"form_use": role} if role else {})})
        for dropped in drop:
            group.append({"op": "remove_column", "table": table.name, "name": dropped})
        ok, said = run.try_group(group)
        if not ok:
            problems.append(f"{where}: колонки таблицы «{table.name}» не изменились: {said}")
        else:
            notes.append(f"таблица «{table.name}»: " + "; ".join(x for x in ((f"колонки добавлены в конец: {', '.join(add)}" if add else ""),
                                                                           (f"убраны колонки: {', '.join(drop)}" if drop else "")) if x))
    prefix = label_prefix(shell)
    placed = {key: found.name for key, found in shell.fields.items()}
    labels = {key: (found.label.name if found.label is not None else None) for key, found in shell.fields.items()}
    for key, entry, after_key, where, order in ch.adds:
        spec = specs.get(key)
        if spec is None:
            continue
        after = placed.get(after_key)
        if after is None:
            problems.append(f"{where}: перед полем {_word(key)} стоит {_word(after_key)}, которого на форме нет")
            continue
        columns = next((b.get("columns", 1) for b in desc["blocks"] if "fields" in b and key in [_entry(e)[0] for e in b["fields"]]), 1)
        at = order.index(key)
        above = after_key if columns > 1 else None
        name, label = _place_pair(run, obj, key, spec, after, role, notes, problems, where, prefix, order, at, above)
        if name is not None and name in run.free_cells:
            run.cell_keys.append((key, after_key))
        if name is not None:
            placed[key], labels[key] = name, label
    if problems:
        raise GenerateError("бережный режим: " + "; ".join(f"{i}) {p}" for i, p in enumerate(problems, 1)) + f". {WAY_OUT}")
    if ch.adds or ch.removes:
        # проверка качества: форма, прочитанная `describe`, даёт те же блоки полей (состав, порядок, число колонок сетки), что названо в описании
        try:
            again = describe_mod.describe(copy.deepcopy(run.doc), config, **_hints(desc)).description
        except (describe_mod.DescribeError, GenerateError, EditError) as e:
            raise GenerateError(f"бережный режим: результат не читается `describe` ({e}); {WAY_OUT}") from None
        if edit_of is not None:
            wrong = edit_problems(old, again, edit_of, edit_place)
            if wrong:
                raise GenerateError("бережный режим: после правки форма читается иначе, чем до неё, не только добавленными полями: "
                                    + "; ".join(wrong) + f". {WAY_OUT}")
            want = got = _field_blocks(again["blocks"])
        else:
            want, got = _field_blocks(desc["blocks"]), _field_blocks(again["blocks"])
        if want != got:
            explained = _explained_by_cells(want, got, run.cell_keys)
            if explained is None:
                raise GenerateError("бережный режим: форма после правки читается иначе, чем описание (поле встало не в тот блок или ряд сетки): "
                                    f"описание — {_show(want)}, форма — {_show(got)}. {WAY_OUT}")
            notes.append(f"форма читается иначе, чем описание ({_show(got)} вместо {_show(want)}): {explained}")
    ops = run.ops
    if ch.title:
        ops.append({"op": "set_form_title", "text": ch.title})
    ops += copy.deepcopy(desc.get("tune", []))
    notes += ch.notes
    notes += resolver.notes
    return ops, notes
