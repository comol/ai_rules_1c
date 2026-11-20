"""Сборка досье: `build` собирает разделы, пишет `brief.md`, `brief.json` и картинки."""

import json
import pathlib
import re

from .. import bar_platform, census, describe, edit, layout, lstring, metadata, patterns
from .. import structure as structure_mod
from . import codefacts, codenotes, codetask, content, editing, facts as br_facts, images as br_images, modulescan, places as br_places, vocab
from .paths import OBJECT_KINDS, _display_path, _object_by_path
from .head import _description, _head
from .purpose import _Binder, _effect_detail, _extra_of, _purpose, handlers, parse_module
from .outline import _bars, _columns_by_code, _element_rows, _page_nodes, _table_kinds, _tables
from .behavior import _behavior
from . import stretch as br_stretch
from .norms import _norms
from .style import _style, _style_behaviour_notes
from .facts_section import _applicability, _drop_duplicates, _facts_json, _focus_by_code, _switched_by_code
from .pictures import _images_section
from .markdown import DETAIL_PARTS, render_md


def detail_parts(detail):
    """Части подробностей по ключу `--detail` (строка через запятую, список либо `None`): `all` — все; неизвестное имя — `ValueError` словами."""
    if not detail:
        return None
    names = [x.strip() for x in (detail.split(",") if isinstance(detail, str) else detail) if x.strip()]
    unknown = [x for x in names if x != "all" and x not in DETAIL_PARTS]
    if unknown:
        raise ValueError(f"--detail: неизвестная часть «{unknown[0]}»; бывают {', '.join(DETAIL_PARTS)}, all")
    return list(DETAIL_PARTS) if "all" in names else names


def build(doc, form_path, config_dir=None, out_dir=None, module_text=None, origin=None, code_notes=None, state=None, hidden="hatch", conditional="plain", detail=None, root_xml=None):
    """Досье формы `doc`; `origin` — форма выгрузки, копия которой строится (`--origin`): она не сосед для стиля конфигурации; подписи читаются на основном языке выгрузки (`lstring`), без выгрузки — по правилу без него. Остальное — `_build`.

    `detail` — части подробностей (`--detail`: `structure`, `columns`, `facts`, `norms`, `style`, `editing`, `code`, `all`): их текст идёт в `brief-full.md`, а `brief.md` остаётся обзором.
    `code_notes` — записи разбора кода, который сделала модель (`brief.codenotes`: список записей из `code-notes.json`); без них досье строится как при `--no-code`:
    модуль формы читается только точным поиском (процедуры, обработчики, имена элементов), а что код меняет на экране, неизвестно.

    `root_xml` — корневой XML выгрузки внешней обработки или отчёта (`--root-xml`): реквизиты и табличные части объекта формы берутся из него, выгрузка
    конфигурации (`config_dir`) рядом необязательна."""
    if hidden not in ("hide", "hatch"):
        raise ValueError(f"режим скрытого — hide или hatch, а не «{hidden}»")
    if conditional not in ("plain", "hatch"):
        raise ValueError(f"режим условного — plain или hatch, а не «{conditional}»")
    parts = detail_parts(detail)
    module_text = modulescan.effective(module_text)          # модуль без процедур и операторов — модуля нет
    if state:
        from .. import formstate
        formstate.apply(doc, state)         # неизвестное имя в состоянии — отказ словами до сборки, а не «картинки не построены»
    code = metadata._main_language(pathlib.Path(config_dir)) if config_dir is not None else None
    with lstring.main_language(code), bar_platform.context():       # вид формы и проведение документа `_build` называет, когда они известны
        return _build(doc, form_path, config_dir, out_dir, module_text, origin, code_notes, state, hidden, conditional, parts, root_xml)


def code_task(doc, form_path, config_dir=None, out_dir=None, module_text=None, command="", root_xml=None):
    """Задание на разбор кода формы моделью: `code-task.md`, заготовка `code-notes.json` и `module.bsl` в каталоге досье (`brief.codetask`); досье не строится.

    Возвращает `{task, notes, module, procedures}`. Раскладка, которая форму не читает, — `edit.EditError` словами."""
    lang = metadata._main_language(pathlib.Path(config_dir)) if config_dir is not None else None
    with lstring.main_language(lang), bar_platform.context():
        form_path = pathlib.Path(form_path)
        out = pathlib.Path(out_dir) if out_dir is not None else form_path.parent / vocab.DEFAULT_DIR
        form = layout.read(doc)
        rec = census.record(doc, str(form_path.resolve()))
        structure = structure_mod.recognize(doc, rec["kind"], modeled=True)
        meta = metadata.load_for(config_dir, root_xml)
        _hint_kind, hint_object = describe.hints_from_path(form_path.resolve())
        binder = _Binder(doc, meta, hint_object)
        names = br_facts._Names(form, structure)
        tables = _tables(form, names, binder)
        bars = content.bars(form, names)
        pages = content.page_names(form, names)
        rows = handlers(doc, form, names)
        object_module = _object_module(form_path, config_dir)
        targets = make_targets(doc, form, names, tables, binder, module_text, config_dir, object_module)
        mapping = targets.mapping()
        on_form = codetask.form_names(form, names, tables, bars, pages)
        on_form["saved"] = codetask.saved_values(doc)
        bound = {name.casefold() for _kind, name in (field_data(names, binder) or {}).values()}          # поле у реквизита — то, что к нему привязано, а не одноимённый элемент
        main = binder.ctx.main if binder.ctx is not None else None
        on_form["data"] = list(data_names(binder)[0])          # реквизиты формы и объекта: источник начального значения называет задание
        on_form["attributes"] = [(name, name.casefold() in bound) for ident, name in (binder.ctx.form_attrs.items() if binder.ctx is not None else ()) if name and ident != main]
        written = codetask.write(out, _display_path(form_path, config_dir), rows, mapping, on_form, module_text, command, object_module, codetask.handler_marks(targets), None, codetask.handler_goals(targets))
        return dict(written, procedures=len(mapping["procedures"]))


def data_names(binder):
    """`(имена данных, имена табличных частей)`: реквизиты формы и объекта, их табличные части и колонки — на них ссылаются `affects`, и они не модули."""
    known, parts = [], []
    if binder.ctx is not None:
        known += [n for n in binder.ctx.form_attrs.values() if n]
    obj = binder.obj
    if obj is not None:
        try:
            known += list(obj.standard) + [a.name for a in obj.attributes]
            for part in obj.tables:
                known += [part.name] + [a.name for a in part.attributes]
                parts.append(part.name)
        except (AttributeError, edit.EditError):
            pass
    return known, parts


def field_data(names, binder):
    """`{полное имя элемента: (вид привязки, имя данных)}` элементов, привязанных к реквизиту формы (`form`) или объекта (`object`): по привязке данных, а не по имени элемента.
    Привязка к реквизиту объекта, имя которого без выгрузки не узнать, — `("object_unresolved", "")`: поле с данными есть, имени данных нет. Привязки не прочитаны — `None`."""
    if binder.ctx is None:
        return None
    out = {}
    for full, item in names.item_of.items():
        kind, name = binder.ctx.binding(item)
        if kind in ("form", "object") and name:
            out[full] = (kind, name)
        elif kind == "object_unresolved":
            out[full] = (kind, "")
    return out


def make_targets(doc, form, names, tables, binder, module_text, config_dir=None, object_module=None):
    """`codenotes.Targets`: что есть на форме и в модуле, обработчики файла формы и имена данных (реквизиты формы и объекта, их табличные части и колонки), на которые
    ссылаются `affects` записей `on_event`; `config_dir` — выгрузка конфигурации, по ней проверяется `source` записи; `object_module` — модуль объекта формы."""
    known, parts = data_names(binder)
    return codenotes.Targets(names, content.page_names(form, names), _tables(form, names, binder), content.bars(form, names), module_text,
                             handlers(doc, form, names), known, config_dir, object_module, parts, field_data(names, binder))


TIMER = re.compile(r'ПодключитьОбработчикОжидания\s*\(\s*"([^"]+)"\s*,\s*([^,)]+?)\s*(?:,\s*([^)]+?)\s*)?\)', re.I)


def timers(module_text, opening_lines=None):
    """Таймеры модуля: `[{handler, interval, once, line, in, condition, opening}]` — вызовы `ПодключитьОбработчикОжидания("Имя", Интервал[, Однократно])`: интервал и условие подключения;
    `opening` — вызов выполняется при открытии (строка из `opening_lines` — граф вызовов разбора кода); без разбора кода все таймеры считаются подключёнными при открытии."""
    if not module_text:
        return []
    lines = modulescan.scan(module_text)
    conds = modulescan.conditions(lines)
    procs = parse_module(module_text)
    out = []
    for number, _masked, raw in lines:
        for hit in TIMER.finditer(raw):
            owner = next((p["name"] for p in procs if p["line"] <= number <= p["end"]), None)
            out.append({"handler": hit.group(1).strip(), "interval": hit.group(2).strip(), "once": (hit.group(3) or "").strip().casefold() in ("истина", "true"),
                        "line": number, "in": owner, "condition": conds.get(number, ""), "opening": opening_lines is None or number in opening_lines})
    return out


def _object_module(form_path, config_dir):
    """Путь к модулю объекта формы в выгрузке (`<Вид>/<Объект>/Ext/ObjectModule.bsl`) либо `None`: нет выгрузки, у формы нет объекта или файла нет."""
    if config_dir is None:
        return None
    parts = pathlib.Path(form_path).resolve().parts
    for at in range(len(parts) - 1, -1, -1):
        if parts[at] in OBJECT_KINDS and parts[at + 2:at + 3] == ("Forms",):
            path = pathlib.Path(*parts[:at + 2]) / "Ext" / "ObjectModule.bsl"
            return str(path) if path.is_file() else None
    return None


def _code(doc, module_text, code_notes, names, form, tables, binder, config_dir=None, form_path=None):
    """Разбор кода для досье: `{state, accepted, rejected}`; `state` — `none` (модуля нет), `not_parsed` (модуль есть, записей нет), `parsed`."""
    if module_text is None:
        return {"state": "none", "accepted": [], "rejected": []}
    if code_notes is None:
        return {"state": "not_parsed", "accepted": [], "rejected": []}
    targets = make_targets(doc, form, names, tables, binder, module_text, config_dir, _object_module(form_path, config_dir) if form_path is not None else None)
    accepted, rejected = codenotes.check(code_notes, targets)
    masked = codenotes.mask_credentials(accepted) + codenotes.mask_credentials(rejected)
    mapping = targets.mapping()
    uncovered = [{"file": f, "line": n, "procedure": p, "text": t} for f, n, p, t in codetask.uncovered_opening(targets, accepted, mapping)]
    overlapped = [{"line": n, "by": by} for n, by in codetask.overlapped_for(targets, accepted)]          # строки, закрытые записью позднего вызова
    return {"state": "parsed", "accepted": accepted, "rejected": rejected, "masked": masked, "warnings": codenotes.warnings(accepted, targets), "uncovered": uncovered, "overlapped": overlapped,
            "timer_open": [t["line"] for t in timers(module_text) if targets.at_opening(t["line"])],
            "defaults": default_rows(targets), "actions": [{"procedure": a["procedure"], "panel": a["element"], "lines": list(a["lines"]), "file": a["file"]} for a in targets.action_rows()]}


UNCOVERED_FILE = "uncovered.txt"


def _write_uncovered(out, code):
    """Полный перечень непокрытых строк пути открытия — в `uncovered.txt` рядом с досье, по строке на запись: `файл строка процедура: текст`. Перечня нет — файл убирается. Возвращает путь либо `None`."""
    path = pathlib.Path(out) / UNCOVERED_FILE
    rows = code.get("uncovered") or []
    if not rows:
        path.unlink(missing_ok=True)
        return None
    path.write_text("".join(f"{u['file']} {u['line']} {u['procedure'] or 'тело модуля'}: {u['text']}\n" for u in rows), encoding="utf-8")
    return str(path)


def default_rows(targets):
    """Обработчики-умолчания: `[{procedure, category, by}]` в порядке модуля. `by` — `skill` (навык отметил сам: `modified`, `empty`, `standard`) либо `model` (запись `default`: `write`, `rows`, `choice`,
    `silent`, `linked`); слова категорий — `handler_defaults.CATEGORY_WORDS`."""
    procs = targets.handler_procs()
    found = {key: {"procedure": procs[key], "category": cat, "by": "skill"} for key, cat in targets.skill_defaults().items()}
    for entry in targets.default_notes:
        for name in entry["handlers"]:
            found.setdefault(name.casefold(), {"procedure": name, "category": entry["categories"].get(name.casefold(), "silent"), "by": "model"})
    ranges = targets.procedure_ranges()
    return sorted(found.values(), key=lambda r: ranges.get(r["procedure"].casefold(), (0, 0))[0])


def _build(doc, form_path, config_dir=None, out_dir=None, module_text=None, origin=None, code_notes=None, state=None, hidden="hatch", conditional="plain", parts=None, root_xml=None):
    """Досье формы `doc` (документ уровня 1): словарь `brief.json`; `brief.md`, `brief.json` и картинки пишутся в `out_dir`.

    `form_path` — путь формы (вид и конфигурация определяются по нему); `config_dir` — каталог выгрузки конфигурации либо `None`;
    `out_dir` — каталог досье (умолчание — `<каталог формы>/.v8tmp/brief/`); `module_text` — текст модуля формы (строка или байты)
    либо `None`. Раскладка, которая форму не читает, — `edit.EditError` словами."""
    form_path = pathlib.Path(form_path)
    out = pathlib.Path(out_dir) if out_dir is not None else form_path.parent / vocab.DEFAULT_DIR
    form = layout.read(doc)
    layout.apply_model_boxes(form)       # место элемента на экране по модели при размере формы; в файле — `item.stored`
    rec = census.record(doc, str(form_path.resolve()))
    kind = rec["kind"]
    table = patterns.load()
    structure = structure_mod.recognize(doc, kind, modeled=True)
    meta = metadata.load_for(config_dir, root_xml)
    _hint_kind, hint_object = describe.hints_from_path(form_path.resolve())
    binder = _Binder(doc, meta, hint_object)
    obj = binder.obj
    path_object = hint_object or _object_by_path(form_path)
    bar_platform.set_context(groups=(obj.has_folders() if getattr(obj, "kind", None) == "catalog" else None), kind=kind, posting={"Allow": True, "Deny": False}.get(getattr(obj, "posting", None)) if getattr(obj, "kind", None) == "document" else None)
    found_extra = _extra_of(binder, doc, meta, path_object)
    bar_platform.set_context(tables=_table_kinds(form, binder),
                             role={"Record": "record", "RecordManager": "record", "List": "list"}.get(found_extra[1]) if found_extra else None)
    names = br_facts._Names(form, structure)
    description = _description(doc, meta, kind, hint_object)
    facts_all = br_facts.facts(doc, structure, meta, hint_object)
    red = {c for f in facts_all if f.kind == "anchors" and f.numbers.get("finding") in ("collision", "frozen") for c in f.numbers["culprits"]}
    out.mkdir(parents=True, exist_ok=True)
    tables = _tables(form, names, binder)
    code = _code(doc, module_text, code_notes, names, form, tables, binder, config_dir, form_path)
    code["uncovered_file"] = _write_uncovered(out, code)
    purpose = _purpose(doc, form, structure, names, meta, binder, description, module_text, kind, tables, code, path_object)
    purpose["saved_values"] = codetask.saved_values(doc)          # «Сохраняемые значения» формы отчёта и обработки: при открытии они приходят заполненными
    code["masked"] = code.get("masked", 0) + codenotes.mask_credentials(purpose["module"]["handlers"]) + codenotes.mask_credentials(purpose["module"]["others"])
    purpose["module"]["code"]["masked"] = code["masked"]
    purpose["module"]["timers"] = timers(module_text, code.get("timer_open")) if module_text else []
    _columns_by_code(tables, purpose["module"])
    try:
        written = br_images.write_images(doc, structure, out, red, purpose["module"]["effects"], purpose["module"].get("form_effects"), hidden, state, conditional)   # пометки кода на картинках — по модулю
    except (edit.EditError, ValueError, OSError) as why:
        written = None
        images = {"error": f"картинки не построены: {why}"}
    else:
        images = _images_section(written)
    effects = purpose["module"]["effects"]
    page_marks = br_places.pages(form, names, _page_nodes(structure), effects, lambda e, p: _effect_detail(e, p, vocab.MARK_SHOWN))
    places = br_places.variant_places(form, names, br_images.marks_of(doc, structure, effects, purpose["module"].get("form_effects")))
    elements = _element_rows(structure, names, form, doc, binder, purpose["module"], br_places.element_marks(places, page_marks, names))
    missing = codefacts.missing_refs(module_text, names, elements)
    missing += codefacts.noted_refs(module_text, purpose["module"]["code"].get("missing") or [], missing)
    purpose["module"]["missing_refs"] = missing
    facts = _focus_by_code(_switched_by_code(facts_all, purpose["module"], names), purpose["module"], names)
    facts = facts + codefacts.facts(missing, codefacts.missing_handlers(purpose["module"]["handlers"], module_text), br_facts.Fact, names)
    style = _style(rec, kind, form_path, config_dir, table, meta, origin)
    facts_shown = [f for f in _drop_duplicates(facts) if f.kind not in vocab.IN_BEHAVIOR]
    strip = content.strip_hidden(form, names)
    result = {
        "head": _head(doc, form, rec, form_path, config_dir, meta, binder, module_text, style, images if written else {}, hint_object,
                       _extra_of(binder, doc, meta, path_object)),
        "purpose": purpose,
        "structure": {"kind": kind, "tree": structure.to_json()["root"], "lines": structure.lines(names.short, strip, leaf_boxes=False, notes=br_places.tree_notes(page_marks, places, names)),
                      "elements": elements,
                      "tables": tables, "bars": _bars(form, names, structure),
                      "hidden": sorted(structure.hidden), "raw": list(structure.raw),
                      "pages": [{"node": n.id, "caption": n.caption, "panel": n.holder, "tabs_shown": (n.holder or "") not in strip,
                                 "by_code": page_marks[n.id]["words"] if n.id in page_marks else None, "gone": page_marks[n.id]["gone"] if n.id in page_marks else False,
                                 "code_page": page_marks[n.id]["page"] if n.id in page_marks else None}
                                for n in structure.walk() if n.role == structure_mod.PAGE and n.caption],
                      "variants": places},
        "behavior": _behavior(doc, form, structure, names, facts),
        "stretch": br_stretch.build(form, names, br_stretch.undrawn(structure, (images or {}).get("not_drawn"))),
        "norms": _norms(rec, kind, structure, table, names),
        "style": style,
        "facts": _facts_json(facts_shown),
        "images": images,
    }
    result["head"]["code"] = purpose["module"]["code"]
    result["head"]["pictures"] = {"hidden": (images or {}).get("hidden_mode", hidden), "conditional": (images or {}).get("conditional_mode", conditional),
                                  "state": sorted(k for k in (state or {}) if k not in ("hidden", "conditional")),
                                  "requested": list((images or {}).get("requested") or [])}
    if any(r["prop"] == "режим рабочего стола" for r in purpose["module"].get("form_effects") or []):
        result["head"]["notes"].append(vocab.DESKTOP_NOTE)
    _style_behaviour_notes(result["style"], result["behavior"])
    result["editing"] = editing.build(doc, form, structure, names, result["structure"]["elements"], tables, result["structure"]["bars"], purpose["module"], module_text,
                                            result["head"], result["behavior"], vocab.EVENT_WORDS)
    result["facts_checked"] = {"without_config": [] if meta is not None else list(vocab.NEEDS_CONFIG), "not_applicable": _applicability(form, names),
                               "without_module": [] if module_text is not None else list(vocab.NEEDS_MODULE),
                               "inexact_captions": [{"node": n, "element": e, "short": names.short(e), "why": w} for n, e, w in br_facts.unchecked_captions(doc, structure)]}
    (out / "brief.md").write_text(render_md(result), encoding="utf-8")
    if parts:
        (out / "brief-full.md").write_text(render_md(result, parts), encoding="utf-8")
    elif (out / "brief-full.md").is_file():
        (out / "brief-full.md").unlink()          # подробности прежнего запуска устарели: досье собрано заново без них
    (out / "brief.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return result
