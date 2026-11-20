"""Раздел «факты» досье: отбор фактов (`brief.facts`) для вывода, факты по коду модуля, строки markdown."""

import collections

from .. import describe, lint, render
from ..edit import names as N
from . import editing, facts as br_facts, module_effects as br_module, words as br_words, vocab
from .fmt import _list


def _facts_json(facts):
    return [{"kind": f.kind, "node": f.node, "element": f.element, "numbers": f.numbers, "words": f.words} for f in facts]


def _drop_duplicates(facts):
    """Замечание линтера о том, о чём уже сказано числами, не повторяется: о подписи, перекрытии и выходе за край — факт того же вида
    о тех же элементах; о привязках — находка раздела «Поведение» о тех же элементах; о ритме и привязках роли — раздел «Нормы вида»."""
    have = collections.defaultdict(set)
    for f in facts:
        if f.kind == "anchors":
            have["anchors"].update(f.numbers["culprits"])
        elif f.element:
            have[f.kind].add(f.element.split("#")[0])
    out = []
    for f in facts:
        if f.kind == "lint":
            group, _colon, key = f.numbers["rule"].partition(":")
            if key in lint.RHYTHM or key in lint.ANCHORS or key == "label_text_gap":
                continue
            twin = vocab.LINT_DUPLICATES.get(group)
            if twin and f.numbers["where"] and all(name in have[twin] for name in f.numbers["where"]):
                continue
        out.append(f)
    return out


def _applicability(form, names):
    """`{вид факта: слова}` — виды, которым на этой форме не к чему применяться: «проверено, фактов нет» про них было бы неправдой."""
    items = [i for i in form.items.values() if i.visible]
    out = {}
    if not any(i.type == "TextBox" and not describe._multiline(i) and (br_facts._pattern(i) or {}).get(N.PATTERN_KIND) in ("S", "N", "D")
               for i in items):
        out["field_width"] = "нет однострочных полей ввода строки, числа или даты"
    if not any(i.type in br_facts.PAD and render.caption_text(i.node, i.type) for i in items):
        out["caption_cut"] = "нет надписей, флажков и кнопок с текстом"
    if not any(i.type == "TableBox" for i in items):
        out["column_cut"] = "нет табличных полей"
    if not any(i.type == "CommandBar" for i in items) or len(items) < 2:
        out["bar_covered"] = "нет командных панелей или других элементов на форме"
    focused = collections.Counter((i.holder, i.page or 0) for i in items if br_facts._focused(i))
    if not any(count > 1 for count in focused.values()):
        out["tab_order"] = "нет двух элементов, принимающих фокус, в одном контейнере"
    if not focused:
        out["active_on_open"] = "нет элементов, принимающих фокус"
    if not any(i.type in br_facts.EXPECT_DATA for i in items):
        out["data_missing"] = "нет полей, флажков, переключателей и таблиц, которым нужны данные"
    return out


def _focus_by_code(facts, module, names):
    """«Активный при открытии не назначен» у формы: если код назначает активный элемент формы в процедуре открытия (`ПриОткрытии`,
    `ПередОткрытием`), факт говорит, каким элементом и где; назначение в других процедурах называется, но
    при открытии не считается."""
    rows = [e for e in module["effects"] if br_module.FOCUS_PROP in e["props"]]
    if not rows:
        return facts
    out = []
    for f in facts:
        if f.kind == "active_on_open" and not f.numbers.get("present") and not f.numbers.get("holder") and f.numbers.get("page") == 0:
            at_open = [(e, p) for e in rows for p in e["procedures"] if p.casefold() in OPEN_PROCEDURES]
            other = [(e, p) for e in rows for p in e["procedures"] if p.casefold() not in OPEN_PROCEDURES]
            if at_open:
                says = "; ".join(f"«{names.short(e['element'])}» в процедуре {p}" for e, p in at_open)
                numbers = dict(f.numbers, set_by_code=[{"element": e["element"], "procedure": p} for e, p in at_open])
                f = f._replace(numbers=numbers, words="в форме элемент, активный при открытии, не назначен, но код назначает его при открытии: " + says)
            elif other:
                says = "; ".join(f"«{names.short(e['element'])}» в процедуре {p}" for e, p in other)
                f = f._replace(words=f.words + "; код назначает активный элемент не при открытии: " + says)
        out.append(f)
    return out


def _switched_by_code(facts, module, names):
    """Перекрытия, в которых элементы переключаются кодом (видимость): так делают панели «друг над другом» — перекрытие может быть задумано."""
    switched = {e["element"] for e in module["effects"] if "видимость" in e["props"] and e["part"] is None}
    if not switched:
        return facts
    out = []
    for f in facts:
        if f.kind == "overlap" and f.element:
            members = [f.element] + list(f.numbers.get("with") or [])
            hit = [m for m in members if m in switched]
            if len(hit) == len(members):
                f.numbers["switched_by_code"] = "all"
                f = f._replace(words=f.words + ": видимость всех этих элементов переключает код, перекрытие может быть задумано")
            elif hit:
                f.numbers["switched_by_code"] = "some"
                f = f._replace(words=f.words + ": видимость части этих элементов переключает код (" + ", ".join(
                    f"«{names.short(m)}»" for m in hit) + ")")
        out.append(f)
    return out


GROUP_MIN = 4            # скрытых, недоступных и без данных элементов не меньше стольких — одна сводная строка


INEXACT_SHOWN = 6        # элементов с неточной проверкой подписи называется поимённо


GROUP_SHOWN = 25         # элементов в одной сводной строке фактов называется не больше стольких


GROUPED = ("invisible", "disabled", "data_missing")      # много однотипных элементов: одна строка на вид, а не строка на элемент


OPEN_PROCEDURES = ("приоткрытии", "передоткрытием")    # где форма ещё открывается: назначенный там активный элемент — «при открытии»


FIELD_WIDTH_NOTE = ("Нужная ширина считается по разрядности реквизита, а не по данным (длина строки, знаки числа): реальные значения чаще короче, и узкое поле "
                    "числа может быть осознанным. Поля с одинаковым типом, шириной и нужной шириной названы одной строкой.")


def _field_width_lines(found):
    """Строки факта «Ширина поля против данных»: одинаковые слова (тот же тип, ширина и нужная ширина) — одна строка «у N полей»; пометка о разрядности."""
    groups = collections.OrderedDict()
    for f in found:
        groups.setdefault(f["words"], []).append(f)
    lines = []
    for words, members in groups.items():
        if len(members) == 1:
            lines.append(f"- {members[0]['node'] or 'форма'}: {words}")
        else:
            lines.append(f"- у {len(members)} полей ({_list([m['node'] or '?' for m in members])}): {words}")
    return lines + ["", FIELD_WIDTH_NOTE]


ICON_COLUMN_PX = 24           # колонка уже этого, как и колонка с подписью из одного-двух знаков, — значок или флажок: усечённая подпись у неё ожидаема


def icon_column(fact):
    """Факт «заголовок колонки не помещается» о колонке-значке: узкая колонка, подпись не длиннее двух знаков или картинка в шапке."""
    n = fact["numbers"]
    return n["have"] <= ICON_COLUMN_PX or len(n["text"].strip()) <= 2 or bool(n.get("icon"))


def column_cut_lines(found):
    """Строки факта «заголовок колонки не помещается»: одна строка на таблицу, колонки перечнем «подпись (нужно N px, есть M px)»; колонки-значки названы числом."""
    by_table = collections.OrderedDict()
    for f in found:
        by_table.setdefault(f["numbers"]["table"], []).append(f)
    lines = []
    for table, members in by_table.items():
        real = [f for f in members if not icon_column(f)]
        icons = len(members) - len(real)
        listed = "; ".join(f"«{f['numbers']['text']}» ({'' if f['numbers']['exact'] else '≈'}{f['numbers']['need']}/{f['numbers']['have']} px)" for f in real)
        lines.append(f"- таблица «{table.split('/')[-1]}» ({members[0]['node'] or '?'}): " + (listed or "только колонки-значки")
                     + (f"; колонок-значков ещё {icons}" if icons and real else ""))
    return lines + ["", "В скобках: нужная ширина с отступом и ширина колонки на экране (≈ — оценка по ширине текста). Шапка усекает подпись с «…»; колонки-значки (уже "
                    f"{ICON_COLUMN_PX} px, с подписью из одного-двух знаков или с картинкой в шапке) в перечне не разбираются."]


def _group_line(found):
    shown = "; ".join(f"{f['node'] or '?'} {f['words']}" for f in found[:GROUP_SHOWN])
    return f"- {len(found)} шт.: {shown}" + (f"; …и ещё {len(found) - GROUP_SHOWN}" if len(found) > GROUP_SHOWN else "")


def _md_facts(facts, checked):
    lines = ["## 7. Факты для оценки", "", "Наблюдения кода с числами, без оценок. Привязки и направляющие названы в разделе «Поведение»."]
    by = collections.OrderedDict((kind, []) for kind in vocab.FACT_TITLES)
    for f in facts:
        by[f["kind"]].append(f)
    unset = [f for f in by["active_on_open"]
             if not f["numbers"].get("present") and not f["numbers"].get("holder") and f["numbers"].get("page") == 0
             and not f["numbers"].get("set_by_code")]
    by["active_on_open"] = [f for f in by["active_on_open"] if f not in unset]
    for kind, found in by.items():
        if not found:
            continue
        lines += ["", f"### {vocab.FACT_TITLES[kind]}"]
        if kind in GROUPED and len(found) >= GROUP_MIN:
            lines.append(_group_line(found))
        elif kind == "column_cut":
            lines += column_cut_lines(found)
        elif kind == "field_width":
            lines += _field_width_lines(found)
        elif kind == "code_missing":
            lines += [f"- {f['node'] or 'модуль'}: {f['words']}" for f in found] + ["", editing.CODE_BY_HAND]
        else:
            lines += [f"- {f['node'] or ('модуль' if kind == 'code_missing' else 'форма')}: {f['words']}" for f in found]
    not_applicable = checked.get("not_applicable") or {}
    inexact = checked.get("inexact_captions") or []
    no_module = checked.get("without_module") or []
    empty = [vocab.FACT_TITLES[k] for k, v in by.items()
             if not v and k not in checked["without_config"] and k not in no_module and k not in not_applicable and k != "default_button"
             and not (k == "active_on_open" and unset) and not (k == "caption_cut" and inexact)]
    if empty:
        lines += ["", "Проверено, фактов нет: " + "; ".join(empty) + "."]
    if inexact:
        shown = "; ".join(f"«{e['short']}» ({e['why']})" for e in inexact[:INEXACT_SHOWN])
        more = f" и ещё {len(inexact) - INEXACT_SHOWN}" if len(inexact) > INEXACT_SHOWN else ""
        lines += ["", f"Не проверено точно у {br_words.counted(len(inexact), 'элемента', 'элементов', 'элементов')} "
                  f"(«{vocab.FACT_TITLES['caption_cut']}»; по оценке ширины подпись помещается): {shown}{more}."]
    if not_applicable:
        lines += ["", "Не к чему применить: " + "; ".join(f"{vocab.FACT_TITLES[k]} ({why})" for k, why in not_applicable.items() if k in vocab.FACT_TITLES) + "."]
    if unset:
        lines += ["", "Элемент, активный при открытии формы, не назначен — у большинства форм так."]
    if no_module:
        lines += ["", "Не проверялось без модуля формы: " + "; ".join(vocab.FACT_TITLES[k] for k in no_module) + "."]
    if checked["without_config"]:
        lines += ["", "Не проверялось без выгрузки: " + "; ".join(vocab.FACT_TITLES[k] for k in checked["without_config"]) + "."]
    return lines + [""]
