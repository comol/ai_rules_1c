"""Короткий обзор формы: `brief.md`. Подробности (`brief --detail …`) пишет `markdown.render_detail`; полные данные — в `brief.json`.

Обзор собирается из словаря `brief.json` и ничего не вычисляет заново. Он отвечает на два вопроса: что пользователь видит при открытии формы и что меняется на экране
от его действий (разделы «При открытии» и «Что делает код»), и добавляет к ним: что это за форма (области, главное поле), состав, как форма ведёт себя при растяжении окна,
проблемы, особенное для правки и куда смотреть дальше. Переменные модуля в обзоре не называются.
"""

import collections
import types

from . import areas, moduleview as mv, opening, vocab
from .facts_section import icon_column
from .fmt import _list
from .purpose import _short_of
from .words import counted

LISTED = 6                 # элементов в одной строке обзора называется поимённо, остальные — числом
KIND_LINES = 8             # видов элементов в строке «элементы» не больше стольких
PANELS_SHOWN = 5           # панелей со страницами в «Составе» называется не больше стольких
TABLES_SHOWN = 6          # таблиц и панелей кнопок в обзоре называется не больше стольких
PROBLEM_LINES = 7          # строк «проблем»
SPECIAL_LINES = 6          # строк «особенного для правки»
SMALL_OVERLAP = 24         # наложение мелкой кнопки или картинки (до стольких px) не считается проблемой
NEAR_LIMIT = 200           # предел раскладки ближе стольких px к размеру формы в файле называется в обзоре; дальше — обычное растяжение
SKIPPED_PX = 2             # выход за край или направляющая в пределах стольких px не считается проблемой

TYPE_WORDS = {"TextBox": "полей ввода", "Label": "надписей", "Button": "кнопок", "CheckBox": "флажков", "ComboBox": "полей выбора", "TableBox": "табличных полей",
              "Panel": "панелей", "CommandBar": "командных панелей", "GroupBox": "рамок группы", "PictureBox": "картинок", "RadioButton": "переключателей",
              "SpreadsheetDocumentField": "полей табличного документа", "HTMLDocumentField": "полей HTML", "Splitter": "разделителей", "ListBox": "списков",
              "CalendarBox": "календарей", "ProgressBar": "индикаторов", "TrackBar": "полос регулирования", "TextDocumentField": "полей текстового документа",
              "Chart": "диаграмм", "GanttChart": "диаграмм Ганта", "PivotChart": "сводных диаграмм", "Dendrogram": "дендрограмм", "PDFDocumentField": "полей PDF",
              "GeographicalSchemaField": "географических схем", "GraphicalSchemaField": "графических схем"}

VISIBLE_KINDS = ("column_cut", "overlap", "caption_cut", "out_of_bounds", "handler_missing", "code_missing")      # проблемы, которые пользователь видит на экране или в работе формы
DPI_NOTES = ("версия общего блока формы", "в записи формы нет DPI", "DPI формы")      # оговорки шапки о версии блока и DPI
SHORT_MODE = "ДляКраткогоОтображения"      # колонки краткого режима отбора дублируют колонки подробного: платформа показывает один набор


def _render(brief):
    """`(строки обзора, Context)`: контекст помнит, какие принятые записи обзор назвал (`Context.said`)."""
    head = brief["head"]
    short = _short_of(brief["structure"])
    ctx = opening.Context(brief, short)
    lines = [f"# Досье формы: {head['form']}", ""]
    lines += _head_lines(brief, ctx)
    lines += _what(brief, short, ctx)
    lines += opening.opening_lines(ctx, _page_marks(brief, ctx))
    lines += opening.actions_lines(ctx)
    lines += _stretch(brief)
    lines += _problems(brief, short, ctx)
    lines += _special(brief, short, ctx)
    lines += _next(brief)
    return lines, ctx


def render_overview(brief):
    return "\n".join(_render(brief)[0]).rstrip("\n") + "\n"


SAID_KINDS = frozenset(opening.OPEN_KINDS) | {"list_content", "missing"}      # принятые записи, которые меняют экран или работу формы и обязаны быть названы в обзоре


def unsaid(brief):
    """Принятые записи с видимым эффектом, которых в обзоре нет ни словами, ни строкой «как обычно»: `[запись]`; пусто — обзор ничего не потерял. Нужна проверке досье: потерянная запись видна в ней."""
    _lines, ctx = _render(brief)
    return [n for n in ctx.accepted if n["kind"] in SAID_KINDS and n["index"] not in ctx.said]


def _kind_text(head):
    """Вид формы словами: форма с основным реквизитом «регламентированный отчёт» у обработки — всё же форма обработки."""
    obj = head["object"] or head.get("object_by_path") or ""
    if head["kind"] == "regulated" and obj.startswith("Обработка."):
        return "форма обработки"
    return head["kind_words"]


def _head_lines(brief, ctx):
    head = brief["head"]
    got = head["received"]
    lines = [f"- Вид формы: {_kind_text(head)}; объект: {_object(head)}"]
    size = f"{head['size'][0]}×{head['size'][1]} px"
    if head.get("fixed_size"):
        lines.append(f"- Размер клиентской области {size}; размер окна фиксирован («Изменять размер» снято), окно равно размеру из файла плюс рамка")
    else:
        lines.append(f"- Размер клиентской области {size} (размер из файла; платформа открывает форму запомненным размером пользователя, и он может быть иным)")
    lines.append("- Код: " + _code_state(brief))
    pic = head.get("pictures") or {}
    lines.append("- Картинки: `clean.png`, `marked.png`, `behavior.png` (скрытое: " + ("со штриховкой" if pic.get("hidden") == "hatch" else "не нарисовано")
                 + "; условное: " + ("со штриховкой" if pic.get("conditional") == "hatch" else "как в файле") + "); условности — `docs/brief.md`")
    absent = [m["what"] for m in head["missing"] if "модуль формы" not in m["what"]]
    if not got["config"] and not any("выгрузк" in a for a in absent):
        absent.append("выгрузка конфигурации")
    if absent:
        lines.append("- Нет: " + "; ".join(absent) + " (что без этого не оценить — шапка в `brief --detail structure`)")
    broken = (brief.get("stretch") or {}).get("broken")
    for note in head["notes"]:
        if note.startswith(DPI_NOTES) and not broken:
            continue          # версия блока и DPI влияют на картинки и нормы, а не на то, что видит пользователь: подробности — `brief --detail structure`
        lines.append(f"- Оговорка: {note}")
    if (head.get("code") or {}).get("masked"):
        lines.append(f"- Учётные данные в записях разбора и модуле (`Pwd=`, `User ID=`, `UID=` и им подобные) заменены на `***`: {head['code']['masked']}; в досье и `brief.json` их нет, "
                     "из `code-notes.json` их тоже стоит убрать")
    return lines + [""]


def _object(head):
    if head["object"]:
        return head["object"]
    if head.get("object_by_path"):
        return f"по пути формы — {head['object_by_path']}"
    return head.get("object_note") or "не определён"


def _code_state(brief):
    head, module = brief["head"], brief["purpose"]["module"]
    code = head.get("code") or {}
    if not module["present"]:
        text = opening.not_received(module).rstrip(".")
        return text[0].lower() + text[1:]
    cover = module.get("coverage")
    if code.get("state") == "parsed":
        text = f"модуль формы есть, разобран моделью: записей {len(code['accepted'])}" + (f", отклонено {len(code['rejected'])}" if code["rejected"] else "")
        if cover:
            text += f"; обработчиков разобрано {cover['parsed']} из {cover['handlers']}"
        return text
    if code.get("state") == "not_parsed":
        return (f"модуль формы есть (процедур и функций: {module['procedures']}), **код не разобран**: что он делает на экране, неизвестно — разбор по `docs/brief-code.md` "
                "(задание `code-task.md`)")
    return "модуль формы есть"


def _what(brief, short, ctx):
    """Что это за форма: объект и назначение, области с главным, данные, слова модели о форме целиком."""
    head, purpose = brief["head"], brief["purpose"]
    obj = purpose["object"]
    extra = purpose.get("extra_object")
    first = _kind_text(head)
    first = first[0].upper() + first[1:]
    if obj is not None:
        first += f" объекта {obj['full_name']}" + (f" («{obj['synonym']}»)" if obj["synonym"] else "")
    elif extra is not None:
        first += f": {extra['full_name']}"
    elif head["object"]:
        first += f" объекта {head['object']}"
    elif head.get("object_by_path"):
        first += f" объекта {head['object_by_path']}"
    window = opening.form_title(ctx, purpose["title"])
    first += (f"; {window}" if window else "") + "."
    lines = ["## Что это за форма", "", first]
    work = opening.form_purpose(ctx)
    if work:
        lines.append("Что форма делает сама (по разбору модели):")
        lines += [f"- {why}" for why in work]
    synthesis = areas.build(brief)
    if synthesis["lines"]:
        lines += ["Что на экране:"] + [(f"  - {line.strip()}" if line.startswith("  ") else f"- {line}") for line in synthesis["lines"]]
    if synthesis["main"]:
        lines.append(f"Главное на форме: {synthesis['main']}.")
    tables = purpose["tables"]
    data = []
    if tables:
        data.append("таблицы " + ", ".join(f"«{short(t['element'])}»" for t in tables[:4]) + (f" и ещё {len(tables) - 4}" if len(tables) > 4 else ""))
    if obj is not None and obj["role"] == "object":
        data.append(f"реквизитов объекта {len(obj['standard']) + len(obj['attributes'])}, табличных частей {len(obj['tables'])}")
    if purpose["form_attributes"]:
        data.append(f"реквизитов формы {len(purpose['form_attributes'])}")
    if data:
        lines.append("Данные: " + "; ".join(data) + ".")
    saved = purpose.get("saved_values") or []
    if saved:
        lines.append("Сохраняемые значения формы (восстанавливаются при открытии, при первом открытии пусты): " + _list([f"«{n}»" for n in saved], 12) + ".")
    return lines + [""]


def _source(table):
    """Данные таблицы одним словом: без приставки «реквизит формы» и без повтора имени таблицы."""
    source = table["source"] or table["kind"] or "без источника"
    for prefix in ("реквизит формы ", "табличная часть "):
        if source.startswith(prefix) and source[len(prefix):] == table["short"]:
            return prefix.strip()
    return source


def _page_marks(brief, ctx):
    """`{(панель, подпись страницы без регистра): слова}` о страницах, видимость которых задаёт код. Слова идут по ЗНАЧЕНИЮ записи, а не по порядку условий: вариант по умолчанию назван первым
    («при открытии (по умолчанию) скрыта: …; иначе — видна, если …»), у страницы без варианта по умолчанию — «видна, если …» и «скрыта, если …» по значениям записей."""
    notes = collections.defaultdict(list)
    for n in ctx.accepted:
        if n["kind"] == "visibility" and n["target"]["kind"] == "page" and n["target"].get("element"):
            notes[(n["target"]["element"], str(n["target"].get("sub") or "").casefold())].append(n)
    by_name = {}
    for effect in brief["purpose"]["module"].get("effects") or []:
        part = effect.get("part") or ""
        if part.startswith("страница ") and "видимость" in effect["props"]:
            by_name[(effect["element"], part[len("страница "):].casefold())] = effect
    out = {}
    for page in brief["structure"]["pages"]:
        name = page.get("code_page")
        effect = by_name.get((page["panel"], (name or "").casefold())) if name else None
        if effect is None:
            continue
        words = _visibility_words(ctx, notes.get((page["panel"], (name or "").casefold())) or []) or _effect_words(ctx, effect)
        out[(page["panel"], page["caption"].casefold())] = words
    return out


def _effect_words(ctx, effect):
    """Слова о видимости страницы по сводной строке модуля, когда записей со значениями нет: условие без значения называется как есть только в форме «закладка …» (модель сама назвала, когда страница видна)."""
    values = effect["props"]["видимость"]
    conds = [mv.condition(c, ctx.vars)[0] for c in effect.get("conds", {}).get("видимость", [])]
    conds = [c for c in dict.fromkeys(conds) if c and not c.startswith("по условию")]
    exprs = [e for e in effect.get("exprs", {}).get("видимость", []) if e and not mv.mentions(e, ctx.vars)]
    first = conds[0].split(";")[0].strip() if conds else ""
    if first.startswith("закладка "):
        return first[len("закладка "):]
    if values == ["Ложь"] and not conds:
        return "код её прячет"
    if exprs:
        return f"видна по выражению «{exprs[0]}»"
    return "видимость задаёт код"


def _visibility_words(ctx, notes):
    """Слова о видимости страницы по записям: вариант по умолчанию первым, значения — как в записях; пусто, когда записи не дают ясных условий."""
    def phrase(note):
        cond, clear = mv.condition(note["condition"], ctx.vars, note["lines"][0])
        value = opening.LITERALS.get(note["value"].strip())
        if value is None:
            return None
        return ("видна" if value else "скрыта"), (cond if clear and cond and not cond.startswith("по условию") else "")
    rows = [(n, phrase(n)) for n in notes]
    rows = [(n, p) for n, p in rows if p is not None]
    if not rows:
        return ""
    default = next(((n, p) for n, p in rows if n.get("default")), None)
    if default is not None and len(rows) > 1:
        first = "при открытии (по умолчанию) " + default[1][0] + (f" ({default[1][1]})" if default[1][1] else "")
        others = [f"{p[0]} ({p[1]})" if p[1] else p[0] for n, p in rows if n is not default[0]]
        return first + ("; иначе — " + "; ".join(dict.fromkeys(others)) if others else "")
    parts = [f"{p[0]} ({p[1]})" if p[1] else ("код её прячет" if p[0] == "скрыта" else p[0]) for _n, p in rows]
    return "; ".join(dict.fromkeys(parts))


def _columns_shown(table):
    return [c for c in table["columns"] if SHORT_MODE not in (c["name"] or "")]


def composition_lines(brief):
    """Раздел «Состав» для `brief --detail structure`: в обзор он не входит (виды элементов, страницы панелей, таблицы, панели кнопок)."""
    short = _short_of(brief["structure"])
    return _composition(brief, short, opening.Context(brief, short))


def _composition(brief, short, ctx):
    structure = brief["structure"]
    lines = ["## Состав", ""]
    count = collections.Counter(e["type"] for e in structure["elements"])
    total = sum(count.values())
    kinds = "; ".join(f"{TYPE_WORDS.get(t, t)} — {n}" for t, n in count.most_common(KIND_LINES))
    rest = len(count) - KIND_LINES
    lines.append(f"- Элементов {total}: {kinds}" + (f"; других видов ещё {rest}" if rest > 0 else ""))
    by_panel = collections.OrderedDict()
    for p in structure["pages"]:
        by_panel.setdefault(p["panel"], []).append(p)
    sizes = _page_sizes(structure["tree"])
    marks = _page_marks(brief, ctx)
    not_drawn = set(brief["images"].get("not_drawn") or [])
    dead = areas.undrawn_elements(brief)
    for panel, pages in list(by_panel.items())[:PANELS_SHOWN]:
        where = "страницы формы" if not panel else f"панель «{panel.split('/')[-1]}»"

        marked = [p for p in pages if marks.get((panel, p["caption"].casefold()))]
        plain = [p for p in pages if p not in marked]
        shown = (marked + plain)[:max(LISTED, len(marked))]
        shown.sort(key=pages.index)
        listed = ", ".join(f"«{p['caption']}» ({sizes.get(p['node'], 0)})" for p in shown) + (f" и ещё {len(pages) - len(shown)}" if len(pages) > len(shown) else "")
        by_words = collections.OrderedDict()
        for p in marked:
            by_words.setdefault(marks[(panel, p["caption"].casefold())], []).append(f"«{p['caption']}»")
        coded = "; видимость страниц задаёт код: " + "; ".join(f"{', '.join(names)} — {words}" for words, names in by_words.items()) if by_words else ""
        lines.append(f"- {where[0].upper() + where[1:]}: {listed}" + ("" if pages[0]["tabs_shown"] else "; закладок нет, страницы переключает код") + coded)
        if pages and all(p["node"] in not_drawn for p in pages) and panel not in dead:          # панель сама на ненарисованной странице: сказано строкой о страницах ниже
            lines.append(f"- {where[0].upper() + where[1:]} на картинке пуста: ни одна страница не нарисована (элементов в них {sum(sizes.get(p['node'], 0) for p in pages)}); "
                         "открыть страницу на картинке — `--state` (`docs/layout.md`)")
    if len(by_panel) > PANELS_SHOWN:
        rest = list(by_panel.values())[PANELS_SHOWN:]
        lines.append(f"- Ещё панелей со страницами: {len(rest)} (страниц {sum(len(r) for r in rest)})")
    hidden_pages = [p for p in structure["pages"] if p["node"] in not_drawn and not all(q["node"] in not_drawn for q in by_panel.get(p["panel"], ()))]
    if hidden_pages:
        elements = sum(sizes.get(p["node"], 0) for p in hidden_pages)
        lines.append(f"- Страницы, которых нет на картинках: {len(hidden_pages)} (элементов в них {elements}); открыть их на картинке — `--state` (`docs/layout.md`)")
    tables = structure["tables"]
    if tables:
        shown = []
        for t in tables[:TABLES_SHOWN]:
            columns = _columns_shown(t)
            shown.append(f"«{t['short']}» ({_source(t)}; колонок {len(columns)}, видимых {sum(1 for c in columns if c['visible'])})" + (" скрыта" if t["hidden"] else ""))
        lines.append("- Таблицы: " + "; ".join(shown) + (f"; и ещё {len(tables) - TABLES_SHOWN}" if len(tables) > TABLES_SHOWN else ""))
    bars = structure["bars"]
    if bars:
        shown = [f"«{b['short']}» — {b['count']}" + (" (автозаполнение)" if b["auto_fill"] else "") for b in bars[:TABLES_SHOWN]]
        lines.append("- Командные панели и кнопок в них: " + "; ".join(shown) + (f"; и ещё {len(bars) - TABLES_SHOWN}" if len(bars) > TABLES_SHOWN else ""))
    invisible = [f for f in brief["facts"] if f["kind"] == "invisible"]
    if invisible:
        lines.append(f"- Скрыто в файле: {len(invisible)} (" + _list([_name(f, short) for f in invisible], 5) + ")")
    return lines + [""]


def _name(fact, short):
    """Имя для строки обзора: элемент, а у факта без элемента — то, о чём он (событие и процедура, имя из кода)."""
    n = fact.get("numbers") or {}
    if fact.get("element"):
        return short(fact["element"])
    if n.get("name"):
        return n["name"]
    if n.get("event"):
        return f"событие «{n['event']}»" + (f" ({n['element']})" if n.get("element") else " формы")
    return fact.get("node") or "форма"


def _page_sizes(tree):
    """`{узел страницы: элементов в ней и во вложенных узлах}`."""
    out = {}

    def walk(node):
        total = len(node.get("elements") or [])
        for child in node.get("children") or []:
            total += walk(child)
        if node.get("role") == "page":
            out[node["id"]] = total
        return total
    walk(tree)
    return out


def _movers(rows, limit=4):
    """«A (+200), B (+100)» — элементы и на сколько."""
    shown = ", ".join(f"{name} ({'+' if by > 0 else '−'}{abs(by)})" for name, by, _t in rows[:limit])
    return shown + (f" и ещё {len(rows) - limit}" if len(rows) > limit else "")


def _stretch(brief):
    """Растяжение окна: обычное — одна строка; подробно — «не растягивается», поломка привязок, предел ближе `NEAR_LIMIT` px к размеру в файле."""
    behavior, st = brief["behavior"], brief.get("stretch") or {}
    head_size = brief["head"]["size"]
    lines = ["## Растяжение окна", ""]
    if behavior["resize_forbidden"]:
        return lines + ["Размер окна не меняется («Изменять размер» снято): привязки к краям формы ничего не растягивают.", ""]
    if st.get("error"):
        return lines + [f"Раскладку при другом размере окна посчитать не удалось ({st['error']}); привязки — `brief --detail structure`.", ""]
    grow_w, grow_h = st["grow_by"]
    broken = st.get("broken")
    size_of = {"width": head_size[0], "height": head_size[1]}
    more = []
    for key, word in (("width", "ширине"), ("height", "высоте")):
        limit = (st.get("limits") or {}).get(key)
        if not limit:
            continue
        if limit["kind"] == "край" and limit["size"] >= size_of[key]:
            more.append(f"- Окно по {word} нельзя сделать меньше, чем в файле ({limit['size']} px): {limit['cause']}")
        elif limit["kind"] == "столкновение":
            more.append(f"- Первым наступает предел по {word}: окно уже {limit['size']} px — элементы перекроют друг друга ({limit['cause']})")
        elif size_of[key] - limit["size"] < NEAR_LIMIT:
            more.append(f"- Первым наступает предел по {word}: окно уже {limit['size']} px — раскладка перестанет сжиматься и начнёт обрезаться ({limit['cause']})")
    culprits = _anchor_culprits(brief)
    if culprits:
        more.append(f"- Привязки элементов {_list(['«' + c + '»' for c in culprits], 3)} повреждены: как они поведут себя при растяжении окна, не гарантировано")
    if broken:
        names = ", ".join(f"«{n}»" for n in broken["elements"][:3])
        grow = st["height"]["grow"]
        more.append(f"- По высоте форма не растягивается: при DPI {broken['dpi']} правило привязки {names} на саму себя ломает растяжение по высоте"
                       + (f"; без поломки растянулись бы {_movers(grow)}" if grow else ""))
    if not more:
        bits = []
        for key, word in (("width", "ширине"), ("height", "высоте")):
            grow = st[key]["grow"]
            bits.append(f"по {word} растут {_movers(grow, 2)}" if grow else f"по {word} ничего не растёт")
        return lines + [f"Обычное: при увеличении окна на {grow_w}×{grow_h} px {'; '.join(bits)}, остальное сдвигается или остаётся на месте; сжимается без обрезки "
                        "до размера, близкого к размеру в файле. Подробно — `brief --detail structure`, `frm_json.py layout`.", ""]
    bits = []
    for key, word in (("width", "ширине"), ("height", "высоте")):
        grow = st[key]["grow"]
        if grow and not (key == "height" and broken):
            bits.append(f"по {word} растут {_movers(grow, 2)}")
    if bits:
        lines.append(f"Если окно шире на {grow_w} px и выше на {grow_h} px: {'; '.join(bits)}.")
    return lines + more + [""]


def _anchor_culprits(brief):
    """Элементы с повреждёнными привязками: от них зависит, как форма поведёт себя при растяжении."""
    found = [f for f in (brief.get("behavior") or {}).get("problems", ()) if f["kind"] == "anchors"] + [f for f in brief.get("facts", ()) if f["kind"] == "anchors"]
    return list(dict.fromkeys(c for f in found for c in f["numbers"].get("culprits", [])))


def _overlap_skipped(fact, rows):
    """Перекрытие, которое проблемой не считается: рамка-заголовок группы, мелкая кнопка или картинка в углу, варианты, которые переключает код."""
    if fact["numbers"].get("switched_by_code") == "all":
        return True
    others = [rows.get(n) for n in fact["numbers"].get("with") or []]
    if others and all(o is not None and o["type"] == "GroupBox" for o in others):
        return True                     # рамка-заголовок группы над панелью — обычный приём
    row = rows.get(fact.get("element"))
    if row is None:
        return False
    if row["type"] == "GroupBox":
        return True
    return row["type"] in ("Button", "PictureBox", "Label") and row["width"] <= SMALL_OVERLAP and row["height"] <= SMALL_OVERLAP


def _problems(brief, short, ctx=None):
    """Проблемы, видимые пользователю, по видам со следствием и именами элементов (до `PROBLEM_LINES` строк): усечённые шапки и подписи, наложения, выход за край,
    обработчик без процедуры, обращение кода к несуществующему элементу. Привязки — в «Растяжении окна»; ширина полей, порядок обхода, направляющие, линтер — в `--detail facts`.
    Нет таких проблем — раздела нет."""
    ctx = ctx or types.SimpleNamespace(said=set(), accepted=[])          # без разбора кода записей, которые надо назвать, нет
    rows = {e["element"]: e for e in brief.get("structure", {}).get("elements", [])}
    dead = areas.undrawn_elements(brief) | set((brief.get("structure") or {}).get("hidden", ()))
    facts = [f for f in brief["facts"] if f["kind"] in VISIBLE_KINDS]
    facts = [f for f in facts if not _on_undrawn(f, dead)]
    groups = collections.OrderedDict()
    for f in list(brief["behavior"]["problems"]) + facts:
        if f["kind"] in VISIBLE_KINDS:
            groups.setdefault(f["kind"], []).append(f)
    out = []
    no_module = not brief.get("purpose", {}).get("module", {}).get("present", True)
    for kind, found in groups.items():
        title = vocab.FACT_TITLES.get(kind, kind)
        if kind == "column_cut":
            real = [f for f in found if not icon_column(f) and SHORT_MODE not in f["numbers"]["column"]]
            if not real:
                continue
            tables = sorted({f["numbers"]["table"].split("/")[-1] for f in real})
            out.append(f"- {title}: {counted(len(real), 'колонка', 'колонки', 'колонок')} в {counted(len(tables), 'таблице', 'таблицах', 'таблицах')} ({_list(tables, 3)}); "
                       "шапка покажет подпись усечённой с «…»")
        elif kind == "overlap":
            real = [f for f in found if not _overlap_skipped(f, rows)]
            if not real:
                continue
            out.append(f"- {title}: {len(real)} ({_list([_name(f, short) for f in real], 3)}); элементы лежат друг на друге"
                       + ("; возможно, это варианты на одном месте, которые переключает код (модуль не получен)" if no_module else ""))
        elif kind == "caption_cut":
            real = [f for f in found if f["numbers"].get("exact", True) and (not ((rows.get(f.get("element")) or {}).get("data")) or (rows.get(f.get("element")) or {}).get("type") != "Label")]
            if not real:
                continue                 # надпись с данными: на экране будет значение, а не текст подписи; оценка по ненайденному шрифту — не факт
            out.append(f"- {title}: {len(real)} ({_list(list(dict.fromkeys(_name(f, short) for f in real)), 3)}); подпись будет обрезана")
        elif kind == "out_of_bounds":
            real = [f for f in found if f["numbers"].get("zero_size") or _outside(f) > SKIPPED_PX]
            if not real:
                continue
            out.append(f"- {title}: {len(real)} ({_list([_name(f, short) for f in real], 3)}); часть элемента не видна или обрезается")
        elif kind == "handler_missing":
            names = [f"«{f['numbers']['event']}» у «{f['numbers']['element']}»" if f["numbers"].get("element") else f"«{f['numbers']['event']}» формы" for f in found]
            out.append(f"- {title}: {len(found)} ({_list(names, 3)}); событие ничего не вызовет")
        elif kind == "code_missing":
            ctx.said.update(n["index"] for n in ctx.accepted if n["kind"] == "missing" and n["target"].get("sub") in {f["numbers"]["name"] for f in found})
            for in_try in (False, True):
                group = [f for f in found if bool(f["numbers"].get("in_try")) == in_try]
                if not group:
                    continue
                names = list(dict.fromkeys(f"«{f['numbers']['name']}»" + (f" ({f['numbers']['where']})" if f["numbers"].get("where") else "") for f in group))
                conds = list(dict.fromkeys(f["numbers"]["cond"] for f in group if f["numbers"].get("cond")))
                tail = ("; обращения стоят в `Попытке`: ошибка гасится, действие не выполняется" if in_try
                        else "; вне `Попытки` это ошибка выполнения: процедура прерывается" + (f" (под условием: {_list(conds, 2)})" if conds and all(f["numbers"].get("cond") for f in group) else ""))
                out.append(f"- Код обращается к элементам, которых на форме нет: {_list(names, 6)}{tail}")
    if not out:
        return []
    lines = ["## Проблемы", ""] + out[:PROBLEM_LINES]
    if len(out) > PROBLEM_LINES:
        lines.append(f"- …и ещё видов проблем: {len(out) - PROBLEM_LINES}")
    return lines + [""]


def _on_undrawn(fact, dead):
    """Замечание относится к элементу или таблице, которых нет на картинках."""
    numbers = fact.get("numbers") or {}
    names = [fact.get("element"), numbers.get("table")] + list(numbers.get("with") or [])
    return any(n in dead for n in names if n)


def _outside(fact):
    box, parent = fact["numbers"].get("box"), fact["numbers"].get("parent_size")
    if not box or not parent:
        return 99
    return max(box[2] - parent[0], box[3] - parent[1], -box[0], -box[1], 0)


def _special(brief, short, ctx):
    """Особенное для правки: только ограничения (что нельзя переименовать, удалить и сломать); нет ограничений — раздела нет."""
    editing = brief["editing"]
    out = []
    for c in editing["constraints"]:
        if c["title"].startswith("Связи между полями") or c["title"].startswith(("Оформление формы смешанное", "Края страниц", "Найдены поломки привязок")):
            continue                    # связи — строкой ниже; оформление, края страниц и привязки — замечания к раскладке, они в `--detail editing`
        out.append(f"- {c['title']} (операции: " + ", ".join(f"`{o}`" for o in c["ops"][:4]) + (", …" if len(c["ops"]) > 4 else "") + ")")
    out = out[:5]
    code = editing["code"]
    module = brief["purpose"]["module"]
    named = list(dict.fromkeys(r["short"] for r in code["rows"])) if code["present"] else []
    if code["present"] and named:
        out.append(f"- На имена опирается код модуля: элементов {len(named)} ({_list(named, LISTED)}): переименование и удаление этих элементов его сломает")
    elif module["present"] is False and module["handlers"]:
        count, _opening = opening.handlers_text(module)
        out.append(f"- Модуль формы не получен, а в файле назначено обработчиков: {count}: что именно называет код, неизвестно, переименование и удаление элементов с обработчиками "
                   "может его сломать")
    links = _links(module, named)
    if links:
        out.append(f"- Связи «поле → поля» в коде: {len(links)} (поля из них, названные в коде по имени, не переименовывать и не убирать; перечень — `brief --detail code`)")
    if not out:
        return []
    return ["## Особенное для правки", ""] + out[:SPECIAL_LINES] + [""]


def _links(module, named):
    """Связи «поле → поля», в которых код обращается к приёмнику по имени элемента (а не по совпадению имени реквизита с элементом)."""
    keep = {n.casefold() for n in named}
    return [l for l in module.get("event_links") or [] if any(t.split("/")[-1].casefold() in keep for t in l["targets"])]


def _next(brief):
    module = brief["purpose"]["module"]
    code = (brief["head"].get("code") or {}).get("state")
    steps = []
    if not module["present"] and module["handlers"]:
        count, opening_events = opening.handlers_text(module)
        steps.append(f"**Получите модуль формы (`form.bsl`).** В файле формы назначено обработчиков {count}"
                     + (f", в том числе событий открытия: {', '.join(opening_events)}" if opening_events else "")
                     + "; без модуля неизвестно, что форма делает при открытии и от действий. Выгрузка платформы кладёт `form.bsl` рядом с `form.frm`; затем `frm_json.py brief <форма> "
                     "[--config …]` выдаст задание `code-task.md`, а разбор записывается по `docs/brief-code.md`.")
    elif module["present"] and code != "parsed":
        steps.append("**Код не разобран — начните с модуля формы.** Задание и карта модуля: `frm_json.py brief <форма> [--config …]` (создаёт `code-task.md`); "
                     "правила записей — `docs/brief-code.md`; затем `--code-notes code-notes.json` собирает досье с разбором. Без этого досье не знает, что форма делает на экране.")
    elif module["present"] and (module.get("coverage") or {}).get("parsed", 0) < (module.get("coverage") or {}).get("handlers", 0):
        cover = module["coverage"]
        steps.append(f"**Разобрано обработчиков {cover['parsed']} из {cover['handlers']}** — остальные прочтите в модуле формы (`form.bsl` рядом с `form.frm`, задание `code-task.md`, "
                     "правила — `docs/brief-code.md`).")
    lines = ["## Как исследовать дальше", ""] + [f"{i}. {t}" for i, t in enumerate(steps, 1)] + ([""] if steps else [])
    lines.append("Подробности — `frm_json.py brief <форма> --detail structure|columns|facts|norms|style|editing|code|all` (пишет `brief-full.md`); раскладка — `layout`, `anchors-check`; "
                 "правка — `edit --ops` (`docs/edit-rules.md`, перед ней — `--detail editing`); полные данные — `brief.json`; картинки: `clean.png` — как видит пользователь, "
                 "`marked.png` — номера узлов, `behavior.png` — кадры при разных размерах окна.")
    return lines + [""]
