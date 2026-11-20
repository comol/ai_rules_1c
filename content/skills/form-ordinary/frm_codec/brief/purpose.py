"""Раздел «назначение» досье: объект по метаданным, таблицы, модуль формы (процедуры, события, что код меняет у элементов), данные на форме."""

import collections
import re

from .. import census, describe, edit, schema
from ..edit import names as N, formprops
from . import codenotes, content as br_content, module_effects as br_module, moduleview, modulescan as scan, words as br_words, vocab
from .fmt import _list, _table, _title
from .typewords import _std_type_words, _type_words


_HEAD = re.compile(r"(?<![\w.])(процедура|функция|procedure|function)\s+(\w+)\s*(?:\(([^)]*)\))?\s*(экспорт|export)?", re.I)


_PARAMS = re.compile(r"\(([^)]*)\)")


_EXPORT = re.compile(r"(?<![\w.])(экспорт|export)\s*$", re.I)


_END = re.compile(r"(?<![\w.])(конецпроцедуры|конецфункции|endprocedure|endfunction)(?![\w])", re.I)


_SKIP_START = ("//", "&", "перем ", "var ")


def _header_end(coded, at, stop):
    """Индекс последней строки заголовка процедуры: заголовок с параметрами на нескольких строках кончается строкой с закрывающей скобкой."""
    depth, opened = 0, False
    for i in range(at, stop):
        for char in coded[i][1]:
            if char == "(":
                depth, opened = depth + 1, True
            elif char == ")":
                depth -= 1
        if opened and depth <= 0:
            return i
        if i == at and not opened:
            return at
    return at


def parse_module(text):
    """Процедуры и функции модуля: `[{name, kind, line, end, params, export, first}]` в порядке файла (`end` — строка конца).

    `first` — первая содержательная строка тела (не пустая, не комментарий, не объявление `Перем`), обрезанная до `MODULE_LINE`
    знаков; у пустого тела — `None`. Текст — строка либо байты (BOM снимается)."""
    if isinstance(text, (bytes, bytearray)):
        text = bytes(text).decode("utf-8", errors="replace")
    text = text.lstrip("﻿")
    from ..edit.module import _code_lines
    lines = text.splitlines()
    coded = _code_lines(text)
    found = []
    for at, (number, code, _outside) in enumerate(coded):
        head = _HEAD.search(code)
        if head is None or code[:head.start()].strip():
            continue
        found.append((at, head))
    out = []
    for n, (at, head) in enumerate(found):
        stop = found[n + 1][0] if n + 1 < len(found) else len(coded)
        end = next((i for i in range(at + 1, stop) if _END.search(coded[i][1])), None)
        end_line = end + 1 if end is not None else stop          # без «Конец…» процедура тянется до следующей
        end = stop if end is None else end
        header_end = _header_end(coded, at, stop)
        header = " ".join(coded[i][1] for i in range(at, header_end + 1))
        first = None
        for line in lines[header_end + 1:end]:
            body = line.strip()
            if body and not body.casefold().startswith(_SKIP_START):
                first = body if len(body) <= vocab.MODULE_LINE else body[:vocab.MODULE_LINE - 1].rstrip() + "…"
                break
        kind = "функция" if head.group(1).casefold() in ("функция", "function") else "процедура"
        params = _PARAMS.search(header)
        out.append({"name": head.group(2), "kind": kind, "line": at + 1, "end": end_line, "params": (params.group(1) if params else "").strip(),
                    "export": bool(_EXPORT.search(header)), "first": first})
    return out


def _handler_of(row):
    action = row.get(N.EVENT_ACTION) if isinstance(row, dict) else None
    handler = action.get(N.HANDLER) if isinstance(action, dict) else None
    return handler if isinstance(handler, str) and handler else None


def _event_rows(block):
    items = block.get(N.EVENT_ITEMS) if isinstance(block, dict) else None
    return items if isinstance(items, list) else []


def _flat_buttons(buttons):
    for button in buttons:
        yield button
        yield from _flat_buttons(button["children"])


# События формы объекта (справочник, документ…): на месте «Сохраняемых значений» основного реквизита лежит список записей `{код, GUID, {3, имя, {1, процедура, …}}}`: первая — `u1`
# списком, остальные — в `items`. Коды 80000–80003 те же, что у событий настроек отчёта и обработки, но список другой (`props.form_settings` — «события объекта»).
OBJECT_EVENTS = {80000: "ПередЗаписью", 80001: "ПриЗаписи", 80002: "ПослеЗаписи", 80003: "ПриИзмененииДанных"}


def _object_events(doc):
    """`[(код, процедура)]` записывающих событий формы объекта; формы другого строения — пусто. Второе строение («иное» у `props.form_settings`) — те же записи
    списком `u2/u1` = `[число, запись, …]` без `saved_values`."""
    from .. import props
    kind = props.form_settings(doc)
    if kind == "события объекта":
        saved = doc["main_attribute"]["u2"]["saved_values"]
        records = [saved.get("u1")] + [[r.get("u0"), r.get("u1"), r.get("u2")] if isinstance(r, dict) else r for r in saved.get("items") or []]
    elif kind == "иное":
        listed = (doc["main_attribute"]["u2"] or {}).get("u1") if isinstance(doc["main_attribute"].get("u2"), dict) else None
        records = listed[1:] if isinstance(listed, list) and listed and isinstance(listed[0], int) else []
    else:
        return []
    out = []
    for record in records:
        try:
            code, _guid, body = record
            action = body[2]
            procedure = action[1]
        except (TypeError, ValueError, IndexError, KeyError):
            continue
        if code in OBJECT_EVENTS and isinstance(procedure, str) and procedure:
            out.append((code, procedure))
    return out


def _column_events(form, names):
    """Обработчики вложенных элементов колонок табличных полей: `[(таблица, колонка, код события, процедура)]`."""
    out = []
    for item in form.items.values():
        if item.type != "TableBox":
            continue
        block = edit.columns.columns_of(item.node)
        for column in (block or {}).get(edit.columns.COLUMN_ITEMS) or []:
            base = edit.columns._column_base(column) if isinstance(column, dict) else None
            head = base.get(edit.columns.COLUMN_HEAD) if isinstance(base, dict) else None
            if not isinstance(head, dict) or not head.get(edit.columns.COLUMN_NAME):
                continue
            try:
                _kind, content = edit.columns.nested_control(head, "")
            except edit.EditError:
                continue                 # вложенного элемента у колонки нет или он не раскрыт — событий нет
            for row in _event_rows(content.get(N.EVENTS)):
                procedure = _handler_of(row)
                if procedure is not None:
                    out.append((names.of(item), head[edit.columns.COLUMN_NAME], row.get(N.EVENT_NAME), procedure))
    return out


def handlers(doc, form, names):
    """Обработчики формы: события формы (в том числе записывающие у формы объекта), события элементов, события вложенных элементов колонок и действия кнопок панелей,
    у которых названа процедура.

    `[{owner, element, node, event, code, procedure}]`: `owner` — `form`, `element`, `column` или `panel`; `event` — имя события по-русски, а у
    события, которому русского имени нет, его код; кнопка панели — `element` = `Панель/Кнопка`, `bar`, `button`, `button_text`; колонка — `element` = `Таблица/Колонка`,
    `table`, `column`."""
    out = []
    for key, (code, ru, _synonym, _params, place) in formprops.FORM_EVENTS.items():
        try:
            block, _where = formprops._event_list(doc, key)
        except edit.EditError:
            continue
        value = key if place == formprops.PLACE_FORM else code
        for row in _event_rows(block):
            if isinstance(row, dict) and row.get(N.EVENT_NAME) == value and _handler_of(row):
                out.append({"owner": "form", "element": None, "node": "A0", "event": ru, "code": key, "procedure": _handler_of(row)})
    for code, procedure in _object_events(doc):
        out.append({"owner": "form", "element": None, "node": "A0", "event": OBJECT_EVENTS[code], "code": str(code), "procedure": procedure})
    for item in form.items.values():
        content = item.node.get(N.CONTENT)
        block = content.get(N.EVENTS) if isinstance(content, dict) else None
        for row in _event_rows(block):
            procedure = _handler_of(row)
            if procedure is None:
                continue
            code = row.get(N.EVENT_NAME)
            name = names.of(item)
            out.append({"owner": "element", "element": name, "node": names.node(name),
                        "event": vocab.EVENT_WORDS.get(code, str(code)), "code": str(code), "procedure": procedure})
    for table, column, code, procedure in _column_events(form, names):
        out.append({"owner": "column", "element": f"{table}/{column}", "node": names.node(table), "event": vocab.EVENT_WORDS.get(code, str(code)), "code": str(code),
                    "procedure": procedure, "table": table, "column": column})
    for bar in br_content.bars(form, names):
        for button in _flat_buttons(bar["buttons"]):
            if button["procedure"]:
                out.append({"owner": "panel", "element": f"{bar['element']}/{button['name']}", "node": names.node(bar["element"]),
                            "event": "действие кнопки", "code": "action", "procedure": button["procedure"],
                            "bar": bar["element"], "button": button["name"], "button_text": button["text"]})
    return out


def _module_section(rows, module_text, names, code=None, tables=()):
    """Раздел «Модуль»: `{present, handlers, procedures, others, effects, form_effects, code}`; у каждого обработчика — что делает процедура, а `effects` —
    что код меняет у элементов (видимость, доступность, текущая страница, заголовок, кнопки панелей: удаляет, прячет, добавляет) и колонок таблиц по записям
    разбора, который сделала модель (`code`: `{state, accepted, rejected}`, `brief.codenotes`); без разбора перечень пуст."""
    code = code or {"state": "none", "accepted": [], "rejected": []}
    if module_text is None:
        for row in rows:
            row["does"] = None
            row["found"] = None
        return {"present": False, "coverage": None, "handlers": rows, "others": [], "procedures": 0, "procedure_names": [], "variables": [], "effects": [], "form_effects": [], "events": [], "event_links": [], "code": _code_json(code)}
    procedures = parse_module(module_text)
    by_name = {p["name"].casefold(): p for p in procedures}
    used = set()
    for row in rows:
        found = by_name.get(row["procedure"].casefold())
        row["found"] = found is not None
        row["does"] = found["first"] if found else None
        if found:
            used.add(found["name"].casefold())
            row["line"] = found["line"]
    others = [{"name": p["name"], "line": p["line"], "export": p["export"], "first": p["first"]}
              for p in procedures if p["name"].casefold() not in used]
    effects = br_module.group(codenotes.effect_rows(code["accepted"], procedures))
    for effect in effects:
        effect["node"] = names.node(effect["element"])
    coverage = _coverage(rows, procedures, code["accepted"], module_text, code.get("defaults") or (), code.get("actions") or ()) if code["state"] == "parsed" else None
    return {"present": True, "coverage": coverage, "handlers": rows, "others": others, "procedures": len(procedures),
            "procedure_names": [p["name"] for p in procedures], "variables": sorted(moduleview.module_variables(module_text, [i.label() for i in names.item_of.values()])), "effects": effects,
            "form_effects": codenotes.form_rows(code["accepted"], procedures), "events": codenotes.events(code["accepted"]),
            "event_links": _element_links(codenotes.event_links(code["accepted"]), names, tables), "code": _code_json(code)}


def _element_links(links, names, tables=()):
    """Связи «поле → поля» только между элементами формы: приёмник, которого на форме нет (реквизит формы или объекта), переходит в `data`; связь без элементов-приёмников отбрасывается."""
    labels = {item.label().casefold() for item in names.item_of.values()} | {str(c["name"] if isinstance(c, dict) else c).casefold() for t in tables for c in t.get("columns") or ()}
    out = []
    for link in links:
        keep = [a for a in link["targets"] if a.split(".")[0].casefold() in labels or a.split(".")[-1].casefold() in labels]
        moved = [a for a in link["targets"] if a not in keep]
        if keep:
            out.append(dict(link, targets=keep, data=list(dict.fromkeys(link["data"] + moved))))
    return out


COVERAGE_UNIT = "процедур-обработчиков"          # единица счёта «разобрано N из M»: процедура, а не строка таблицы событий (одна процедура бывает у нескольких событий)


def _coverage(rows, procedures, accepted, module_text, defaults=(), actions=()):
    """Сколько обработчиков формы разобрано: `{handlers, parsed, absent, events, defaults, unparsed, unit}`. Обработчик — процедура, названная в файле формы или привязанная кодом
    (`Новый Действие("Имя")`) и имеющаяся в модуле (одна на несколько событий считается раз; `events` — число таких событий); `absent` — имена процедур из файла формы, которых в модуле нет:
    в счёт не входят. Он разобран, если это умолчание (`defaults`: навык отметил сам либо назвала запись `default`) или в его теле или в теле процедуры, которую он вызывает (и так далее по цепочке
    вызовов), есть принятая запись разбора с этим модулем формы (запись с `source` — по строке вызова в модуле формы). `unparsed` — имена не разобранных."""
    text = module_text.decode("utf-8", errors="replace") if isinstance(module_text, (bytes, bytearray)) else module_text
    lines = text.lstrip("\ufeff").splitlines()
    by_name = {p["name"].casefold(): p for p in procedures}
    noted = [n["lines"] for n in accepted if n.get("lines")]
    own = {name: any(a <= p["end"] and p["line"] <= b for a, b in noted) for name, p in by_name.items()}
    calls = {}
    for name, p in by_name.items():
        body = " ".join(lines[p["line"]:p["end"]]).casefold()
        calls[name] = [other for other in by_name if other != name and re.search(r"(?<![\wа-яё])" + re.escape(other) + r"(?![\wа-яё])", body)]
    every = list(rows) + list(actions)
    handlers = {r["procedure"].casefold() for r in every if (r["procedure"] or "").casefold() in by_name}      # обработчик без процедуры в модуле разбирать нечего: в M не входит
    events = sum(1 for r in every if (r["procedure"] or "").casefold() in by_name)
    absent = sorted({r["procedure"] for r in rows if r["procedure"] and r["procedure"].casefold() not in by_name}, key=str.casefold)
    default_names = {str(d["procedure"]).casefold() for d in defaults}

    def reaches(name, seen):
        if own.get(name):
            return True
        seen.add(name)
        return any(reaches(c, seen) for c in calls.get(name, ()) if c not in seen)
    parsed = {h for h in handlers if h in default_names or reaches(h, set())}
    unparsed = sorted((by_name[h]["name"] for h in handlers - parsed), key=lambda n: by_name[n.casefold()]["line"])
    return {"handlers": len(handlers), "parsed": len(parsed), "absent": absent, "events": events, "defaults": len(handlers & default_names), "unparsed": unparsed, "unit": COVERAGE_UNIT}


def _code_json(code):
    """Разбор кода для `brief.json`: `{state: parsed|not_parsed|none, accepted: [записи], rejected: [{index, kind, why}], open_refused, others}`."""
    accepted = code["accepted"]
    return {"state": code["state"], "accepted": [{"index": n["index"], "kind": n["kind"], "target": n["target"], "value": n["value"], "condition": n["condition"],
                                                  "lines": n["lines"], "opening": n.get("opening", True), "user_only": n.get("user_only", False),
                                                  "group": n.get("group", ""), "default": bool(n.get("default")), "order": list(n["order"]) if n.get("order") else None,
                                                  "name_expr": n.get("name_expr", ""), "why": n.get("why", ""), **({"object_body": True} if n.get("object_body") else {})}
                                                 for n in accepted],
            "rejected": [{"index": r["index"], "kind": r["kind"], "why": r["why"]} for r in code["rejected"]],
            "warnings": list(code.get("warnings") or []), "uncovered": list(code.get("uncovered") or []),
            "open_refused": codenotes.refusals(accepted), "others": codenotes.others(accepted), "form_title": codenotes.form_titles(accepted),
            "missing": codenotes.missing(accepted), "appearance": codenotes.appearances(accepted),
            "sources": [{"index": n["index"], "kind": n["kind"], "file": n["source"]["file"], "lines": n["source"]["lines"]} for n in accepted if n.get("source")],
            "defaults": [dict(d) for d in code.get("defaults") or []], "by_data": codenotes.by_data(accepted),
            "actions": [dict(a) for a in code.get("actions") or []],
            "name_notes": [{"index": n["index"], "notes": n["names_note"]} for n in accepted if n.get("names_note")]}


class _Binder:
    """Что называет привязка элемента: слова и вид привязки (`describe._Ctx`)."""

    def __init__(self, doc, meta, object_name):
        try:
            self.ctx = describe._Ctx(doc, meta, None, None, object_name)
        except edit.EditError:
            self.ctx = None

    @property
    def obj(self):
        return None if self.ctx is None else (self.ctx.obj or self.ctx.list_obj)

    def words(self, item):
        """`(вид, слова)`; вид — `form`, `object`, `table`, `main`, `object_unresolved`, `other` либо `None` (привязки нет)."""
        if self.ctx is None:
            return None, None
        steps = self.ctx.bound.get(item.index)
        if steps is None:
            return None, None
        if len(steps) == 1 and steps[0].get("u0") == self.ctx.main:
            return "main", "основной реквизит формы"
        kind, name = self.ctx.binding(item)
        return {"none": (None, None), "form": ("form", f"реквизит формы {name}"), "object": ("object", f"реквизит объекта {name}"),
                "table": ("table", f"табличная часть {name}"),
                "object_unresolved": ("object_unresolved", "реквизит объекта (имя без выгрузки не определить)"),
                "other": ("other", self._path_words(steps))}[kind]

    def _path_words(self, steps):
        """Путь данных привязки иного вида словами: первое звено — реквизит формы, если он назван; имена остальных звеньев выгрузка не даёт."""
        first = steps[0].get("u0") if steps else None
        name = self.ctx.form_attrs.get(first)
        more = len(steps) - 1
        if name:
            return f"реквизит формы {name}" + (
                f", далее по {br_words.counted(more, 'звену', 'звеньям', 'звеньям')} пути (имена не расшифрованы)" if more else " (привязка иного вида)")
        return f"путь данных из {br_words.counted(len(steps), 'звена', 'звеньев', 'звеньев')} (имена не расшифрованы)"


def _object_section(binder, form, meta):
    obj = binder.obj
    if meta is None or obj is None:
        return None
    ctx = binder.ctx
    role = None
    if ctx.obj is not None and obj.kind == "catalog":
        try:
            role = describe._role(ctx, None)
        except edit.EditError:
            role = None
    try:
        attributes = obj.attributes_for(role) if role else obj.attributes
        tables = obj.tables_for(role) if role else obj.tables
    except edit.EditError:
        attributes, tables = obj.attributes, obj.tables
    shown = set()
    for holder in form.holders.values():
        for item in holder.children:
            kind, words = binder.words(item)
            if kind in ("object", "table"):
                shown.add(words.split(" ", 2)[-1])
    list_form = ctx.list_obj is not None
    standard = [{"name": name, "synonym": obj.standard_synonyms.get(name) or "", "type": _std_type_words(obj, name),
                 "required": None, "on_form": name in shown} for name in obj.standard]
    rows = [{"name": a.name, "synonym": a.synonym, "type": _type_words(a), "required": a.fill_checking == "ShowError",
             "on_form": a.name in shown} for a in attributes]
    parts = [{"name": t.name, "synonym": t.synonym, "on_form": t.name in shown,
              "columns": [{"name": a.name, "synonym": a.synonym, "type": _type_words(a)} for a in t.attributes]} for t in tables]
    return {"full_name": obj.full_name, "synonym": obj.synonym, "role": "list" if list_form else "object",
            "standard": standard, "attributes": rows, "tables": parts,
            "without_element": [] if list_form else [r["name"] for r in standard + rows if not r["on_form"]],
            "tables_without_element": [] if list_form else [t["name"] for t in parts if not t["on_form"]]}


def _main_type_guid(binder, doc):
    """GUID типа основного реквизита формы, когда тип — один объектный тип конфигурации, иначе `None`."""
    ctx = binder.ctx
    row = ctx.main_row if ctx is not None else None
    types = (row.get("pattern") or {}).get("types") if isinstance(row, dict) and isinstance(row.get("pattern"), dict) else None
    block = types[0] if isinstance(types, list) and len(types) == 1 and isinstance(types[0], dict) else None
    if block is None or block.get("kind") != "#":
        return None
    value = block.get("value_type")
    return schema.type_guid(value)


def _extra_of(binder, doc, config, hint_object=None):
    """Журнал документов или регистр, с которым работает форма: `(ExtraObject, категория)` либо `None`. Объект ищется по типу основного реквизита
    формы, а без него — по месту формы в выгрузке."""
    if config is None:
        return None
    guid = _main_type_guid(binder, doc)
    hit = config.extra_by_type_id(guid) if guid else None
    if hit is None and hint_object and hint_object in config.extras:
        return config.extras[hint_object], None
    return hit


def _main_attribute_words(binder, doc, config, hint_object=None):
    """Основной реквизит формы словами: имя и тип; `None`, если у формы его нет."""
    ctx = binder.ctx
    name = census.main_attribute(doc)
    if not name:
        return None
    row = ctx.main_row if ctx is not None else None
    types = (row.get("pattern") or {}).get("types") if isinstance(row, dict) and isinstance(row.get("pattern"), dict) else None
    block = types[0] if isinstance(types, list) and len(types) == 1 and isinstance(types[0], dict) else None
    if block is None:
        return f"{name}"
    kind = block.get("kind")
    if kind == "#":
        guid = _main_type_guid(binder, doc)
        hit = config.object_by_type_id(guid) if config is not None and guid else None
        if hit is not None:
            return f"{name} — тип {hit[0].full_name}"
        extra = _extra_of(binder, doc, config, hint_object)
        if extra is not None:
            return f"{name} — тип {extra[0].full_name} ({vocab.EXTRA_ROLES.get(extra[1], 'тип формы')})"
        if config is None:
            return f"{name} — тип объекта формы (выгрузка не задана, тип не назван)"
        return f"{name} — тип вне прочитанной выгрузки (читаются {vocab.READ_WORDS})"
    return f"{name} — {br_content.TYPE_LETTERS.get(kind, 'произвольный тип')}"


def _extra_section(binder, doc, config, hint_object=None):
    """Состав журнала документов или регистра из выгрузки (раздел «Назначение») либо `None`."""
    found = _extra_of(binder, doc, config, hint_object)
    if found is None:
        return None
    obj, category = found
    section = {"full_name": obj.full_name, "synonym": obj.synonym, "kind": obj.kind, "role": vocab.EXTRA_ROLES.get(category, "тип формы"),
               "registered": list(obj.registered),
               "columns": [{"name": c.name, "synonym": c.synonym, "documents": list(c.documents)} for c in obj.columns]}
    for key, members in (("dimensions", obj.dimensions), ("resources", obj.resources), ("attributes", obj.attributes)):
        section[key] = [{"name": a.name, "synonym": a.synonym, "type": _type_words(a)} for a in members]
    section["periodicity"], section["write_mode"], section["register_type"] = obj.periodicity, obj.write_mode, obj.register_type
    return section


def _purpose(doc, form, structure, names, meta, binder, description, module_text, kind, tables, code=None, hint_object=None):
    section = {"title": _title(description), "object": None, "form_attributes": [], "data": [], "tables": [], "module": None,
               "description": description}
    obj = _object_section(binder, form, meta)
    section["object"] = obj
    section["main_attribute"] = census.main_attribute(doc)
    section["main_attribute_words"] = _main_attribute_words(binder, doc, meta, hint_object)
    section["extra_object"] = _extra_section(binder, doc, meta, hint_object)
    if binder.ctx is not None:
        main = binder.ctx.main
        section["form_attributes"] = [name for ident, name in binder.ctx.form_attrs.items() if ident != main and name]
    for node in structure.walk():
        for name in node.elements:
            item = names.item_of.get(name)
            if item is None:
                continue
            kind_, words = binder.words(item)
            if words:
                section["data"].append({"node": node.id, "element": name, "type": item.type, "data": words})
    section["tables"] = [{"element": t["element"], "node": t["node"], "kind": t["kind"], "source": t["source"],
                          "columns": [c["name"] for c in t["columns"]], "visible": sum(1 for c in t["columns"] if c["visible"])}
                         for t in tables]
    section["module"] = _module_section(handlers(doc, form, names), module_text, names, code, tables)
    return section


def _clean_cond(text, variables):
    """Условие без переменных модуля: смысл, если он читается без них, иначе «по условию в коде»; без переменных модуля текст не меняется."""
    return moduleview.condition(text, variables)[0] if variables and text else text


def _effect_detail(effect, prop, shown=None, variables=()):
    """Слова о том, чем задано значение свойства: значение (текст в кавычках) или выражение, условие, зависимость и «вероятно»; `variables` — переменные модуля (без регистра):
    их имена в условиях и выражениях не называются."""
    limit = shown or scan.SHOWN
    exprs = effect["exprs"].get(prop, [])[:2]
    bits = [(f"значение «{scan.shorten(x[1:-1], limit)}»" if len(x) > 1 and x[0] == x[-1] == '"' and x.count('"') == 2 else
             "выражение задаёт код" if moduleview.mentions(x, variables) else f"выражение «{scan.shorten(x, limit)}»") for x in exprs]
    if variables and effect["conds"].get(prop):
        effect = dict(effect, conds=dict(effect["conds"], **{prop: [_clean_cond(c, variables) for c in effect["conds"][prop]]}))
    return bits + codenotes.detail_words(effect, prop, limit)


EFFECT_LISTED = 8        # элементов в строке перечня «что меняет код» называется не больше стольких


EFFECT_ORDER = ("видимость", "доступность", "только просмотр", "текущая страница", "заголовок", "пометка", "свёртка",
                br_module.FOCUS_PROP)


EXTRA_TITLES = {"journal": "Журнал документов", "inforeg": "Регистр сведений", "accreg": "Регистр накопления"}


def _md_extra(extra):
    """Журнал документов или регистр, с которым работает форма: состав из выгрузки."""
    lines = [f"{EXTRA_TITLES[extra['kind']]}: {extra['full_name']}" + (f" («{extra['synonym']}»)" if extra["synonym"] else "") + "."]
    if extra["kind"] == "journal":
        lines += ["", "Документы журнала: " + (_list(extra["registered"], 99) or "нет") + "."]
        if extra["columns"]:
            lines += ["", "Графы журнала:", ""]
            lines += _table(["Графа", "Синоним", "В каких документах есть"],
                            [[c["name"], c["synonym"], ", ".join(c["documents"])] for c in extra["columns"]])
    else:
        facts = "; ".join(f"{label}: {extra[key]}" for label, key in (("периодичность", "periodicity"), ("режим записи", "write_mode"), ("вид", "register_type")) if extra.get(key))
        if facts:
            lines.append(facts[0].upper() + facts[1:] + ".")
        for title, key in (("Измерения", "dimensions"), ("Ресурсы", "resources"), ("Реквизиты регистра", "attributes")):
            if extra[key]:
                lines += ["", f"{title}:", ""]
                lines += _table(["Имя", "Синоним", "Тип"], [[a["name"], a["synonym"], a["type"]] for a in extra[key]])
    return lines + [""]


def _md_purpose(purpose, head, structure, module=True):
    lines = ["## 2. Назначение", ""]
    if purpose["title"]:
        lines.append(f"Заголовок формы: «{purpose['title']}».")
    obj = purpose["object"]
    extra = purpose.get("extra_object")
    if obj is None:
        if extra is not None:
            lines += _md_extra(extra)
        elif head.get("object_note"):
            lines.append(head["object_note"][0].upper() + head["object_note"][1:] + ".")
        else:
            lines.append("Метаданные объекта недоступны: "
                         + ("выгрузка конфигурации не задана" if not head["received"]["config"] else "объект формы в выгрузке не найден")
                         + "; " + vocab.WITHOUT["config" if not head["received"]["config"] else "object"] + ".")
        if purpose.get("main_attribute_words"):
            lines.append(f"Основной реквизит формы: {purpose['main_attribute_words']}.")
    else:
        what = "динамический список объекта" if obj["role"] == "list" else "объект"
        lines.append(f"{what.capitalize()}: {obj['full_name']}" + (f" («{obj['synonym']}»)" if obj["synonym"] else "") + ".")
        rows = [[a["name"], a["synonym"], a["type"], "да" if a["required"] else ("" if a["required"] is None else "нет"),
                 "да" if a["on_form"] else "нет"] for a in obj["standard"] + obj["attributes"]]
        if rows and obj["role"] == "object":
            lines += ["", "Реквизиты (стандартные первыми):", ""]
            lines += _table(["Имя", "Синоним", "Тип", "Обязательный", "Есть элемент на форме"], rows)
        elif rows:
            lines += ["", "Реквизиты объекта: " + ", ".join(a["name"] for a in obj["standard"] + obj["attributes"]) + "."]
        for part in (obj["tables"] if obj["role"] == "object" else ()):
            lines += ["", f"Табличная часть «{part['name']}»" + (f" («{part['synonym']}»)" if part["synonym"] else "")
                      + ((": есть на форме." if part["on_form"] else ": на форме нет.") if obj["role"] == "object" else "."), ""]
            lines += _table(["Колонка", "Синоним", "Тип"], [[c["name"], c["synonym"], c["type"]] for c in part["columns"]])
        if obj["role"] == "object":
            lines += ["", "Реквизиты объекта без элемента на форме: " + (_list(obj["without_element"], 99) or "нет") + "."]
            if obj["tables_without_element"]:
                lines.append("Табличные части без элемента: " + _list(obj["tables_without_element"], 99) + ".")
    if purpose["form_attributes"]:
        lines += ["", "Реквизиты формы: " + _list(purpose["form_attributes"], 99) + "."]
    if purpose["data"]:
        lines += ["", f"Данные на форме: привязки есть у {len(purpose['data'])} элементов (элемент → данные — в колонке «Данные» таблицы структуры)."]
    if purpose["tables"]:
        short = _short_of(structure)
        lines += ["", "Таблицы на форме (колонки — `brief --detail columns`):"]
        for t in purpose["tables"]:
            lines.append(f"- «{short(t['element'])}» ({t['node'] or '?'}): " + "; ".join(x for x in (t["kind"], t["source"]) if x)
                         + f"; колонок {len(t['columns'])}, видимых {t['visible']}")
    if module:
        lines += _md_module(purpose["module"], structure)
    return lines + [""]


def md_code_section(purpose, structure):
    """Модуль формы отдельным разделом (`--detail code`): обработчики, что код меняет, события и связи."""
    return ["## 2а. Модуль формы", ""] + _md_module(purpose["module"], structure)[1:] + [""]


def _fold_handlers(rows, short):
    """Строки таблицы обработчиков: одна процедура на одно событие у нескольких элементов или кнопок одной панели — одна строка."""
    out, index = [], {}
    for r in rows:
        key = (r["event"], r["procedure"], r["owner"] in ("panel", "column"))
        if key not in index:
            index[key] = {"node": "", "event": r["event"], "procedure": r["procedure"], "found": r["found"], "does": r["does"], "places": {}}
            out.append(index[key])
        entry = index[key]
        if r["node"] and r["node"] not in entry["node"].split(", "):
            entry["node"] = ", ".join(x for x in (entry["node"], r["node"]) if x)
        if r["owner"] == "form":
            entry["places"].setdefault("форма", [])
        elif r["owner"] == "panel":
            entry["places"].setdefault(("панель", short(r["bar"])), []).append(r["button_text"] or r["button"])
        elif r["owner"] == "column":
            entry["places"].setdefault(("таблица", short(r["table"])), []).append(r["column"])
        else:
            entry["places"].setdefault(None, []).append(short(r["element"]))
    return out


def _places_text(entry):
    parts = []
    for place, names in entry["places"].items():
        if place == "форма":
            parts.append("форма")
        elif place is None:
            parts.append(_list(names, vocab.FOLD_LISTED) + (f" ({len(names)})" if len(names) > vocab.FOLD_LISTED else ""))
        else:
            listed = ", ".join(f"«{n}»" for n in names[:vocab.FOLD_LISTED]) + (f" и ещё {len(names) - vocab.FOLD_LISTED}" if len(names) > vocab.FOLD_LISTED else "")
            parts.append(f"{place[0]} {place[1]}: {listed}")
    return "; ".join(parts)


def _md_module(module, structure):
    lines = ["", "Модуль формы и обработчики:"]
    rows = module["handlers"]
    short = _short_of(structure)
    variables = {v.casefold() for v in module.get("variables") or ()}
    if not module["present"]:
        lines.append("")
        lines.append("Модуль формы не получен. Обработчики, названные в форме: " + (", ".join(f"{r['procedure']} ({r['event']})" for r in rows) if rows else "нет") + ".")
        return lines
    if not rows:
        lines += ["", f"В форме нет событий и действий кнопок с процедурами; процедур и функций в модуле: {module['procedures']}."]
    else:
        lines.append("")
        folded = _fold_handlers(rows, short)
        lines += _table(["Узел", "Где", "Событие", "Процедура", "Что делает (первая строка тела)"],
                        [[e["node"], _places_text(e), e["event"], e["procedure"],
                          ("процедуры нет в модуле" if not e["found"] else (e["does"] or "тело пусто"))] for e in folded])
    lines += _md_code(module, variables)
    if module["effects"]:
        lines += ["", "Что код меняет у элементов (по разбору, который сделала модель; «где в коде» — строки модуля; условие и выражение — как записала модель):", ""]
        rows_e = []
        for e in module["effects"]:
            order = sorted(e["props"], key=lambda x: EFFECT_ORDER.index(x) if x in EFFECT_ORDER else len(EFFECT_ORDER))
            parts = []
            for p in order:
                detail = _effect_detail(e, p, 400, variables)
                shown = _effect_prop(e, p) if p != "текущая страница" else p + " (" + "/".join(v for v in e["props"][p] if v) + ")"
                parts.append(shown + (" — " + ", ".join(detail) if detail else ""))
            what = ("; " if any(" — " in x for x in parts) else ", ").join(parts)
            drawn = br_module.drawn_props(e)
            if drawn:
                what += "; на рисунке применено: " + ", ".join(sorted(drawn))
            where = ", ".join(e["procedures"]) or "вне процедур"
            where += (": строки " if len(e["ranges"]) > 1 or "–" in e["ranges"][0] else ": строка ") + ", ".join(e["ranges"])
            rows_e.append([e["node"] or "?", short(e["element"]) + (f" ({e['part']})" if e["part"] else ""), what, where])
        lines += _table(["Узлы", "Элементы", "Что меняет", "Где в коде"], rows_e)
    lines += _md_pages(module, short, variables)
    lines += _md_form_effects(module, variables)
    lines += _md_events(module, short, variables)
    if module["others"]:
        shown = module["others"][:vocab.OTHER_PROCEDURES]
        lines += ["", f"Прочие процедуры и функции модуля ({len(module['others'])}; в скобках строка начала, экспортные помечены): "
                  + ", ".join(f"{p['name']} ({p['line']}" + (", экспорт" if p["export"] else "") + ")" for p in shown)
                  + (f" …и ещё {len(module['others']) - len(shown)}" if len(module["others"]) > len(shown) else "") + "."]
    return lines


def _md_pages(module, short, variables):
    """Текущая страница панелей парами «страница — условие»: по записям разбора, в порядке выполнения."""
    notes = [n for n in (module.get("code") or {}).get("accepted") or [] if n["kind"] == "current_page" and n["target"].get("element")]
    if not notes:
        return []
    lines = ["", "Какую страницу панели выбирает код (страница — условие, при котором код её выбирает; строки модуля):", ""]
    for n in notes:
        cond = _clean_cond(n["condition"], variables)
        lines.append(f"- панель «{short(n['target']['element'])}»: страница «{n['target'].get('sub')}» — " + (cond if cond else "безусловно") + f" (строки {n['lines'][0]}–{n['lines'][1]})")
    return lines


def _md_events(module, short, variables=()):
    """Поведение при работе: что происходит, когда пользователь работает с элементами формы (по записям `on_event`), и связи «поле → поля»."""
    events = module.get("events") or []
    if not events:
        return []
    lines = ["", "Поведение при работе (события формы и элементов по разбору модели: что делает обработчик, на что влияет, при каком условии; строки модуля):", ""]
    rows = []
    for e in events:
        what = "; ".join(codenotes.WHAT_WORDS[x["what"]] + (f" ({', '.join(x['affects'])})" if x["affects"] else "") + (f" — {x['text']}" if x["text"] else "") for x in e["effects"])
        cond = scan.shorten(_clean_cond(e["condition"], variables), 70) if e["condition"] else ""
        rows.append([short(e["source"]) if e["source"] != "форма" else "форма", e["event"], what, cond,
                     f"{e['lines'][0]}–{e['lines'][1]}"])
    lines += _table(["Элемент", "Событие", "Что делает и на что влияет", "Условие", "Строки"], rows)
    links = module.get("event_links") or []
    if links:
        lines += ["", "Связи «поле → поля» (обработчик одного поля меняет другие поля и колонки; при правке формы не ломать — переименование или удаление названного поля ломает связь):", ""]
        for link in links:
            lines.append(f"- {short(link['source']) if link['source'] != 'форма' else 'форма'} ({link['event']}) → {', '.join(link['targets'])}"
                         + (f" (и реквизиты {', '.join(link['data'])})" if link.get("data") else "") + f": {', '.join(link['what'])} (строки {link['lines'][0]}–{link['lines'][1]})")
    return lines


def _md_form_effects(module, variables=()):
    """Что код меняет у самой формы (`РежимРабочегоСтола`, положение и размер): где и как."""
    rows = module.get("form_effects") or []
    if not rows:
        return []
    lines = ["", "Что код меняет у формы (по разбору модели):", ""]
    return lines + _table(["Свойство", "Где в коде", "Значение"], [
        [r["prop"] + (" (`РежимРабочегоСтола`)" if r["prop"] == br_module.DESKTOP_MODE else ""), f"{r['where']}: строки {r['line']}–{r['line_to']}",
         ("по условию: " + ("выражение задаёт код" if moduleview.mentions(r["expr"], variables) else r["expr"]) if r["expr"] else r["value"])
         + (f"; условие «{scan.shorten(_clean_cond(r['cond'], variables), 60)}»" if r["cond"] else "")] for r in rows])


UNCOVERED_SHOWN = 12
UNCOVERED_FILE = "uncovered.txt"          # полный перечень непокрытых строк пути открытия (`assemble._write_uncovered`)


def _md_code(module, variables=()):
    """Разбор кода моделью: отказ в открытии, отклонённые записи с причиной и то, что прочитано, но записано как `other`."""
    code = module.get("code") or {}
    lines = []
    for r in code.get("open_refused") or []:
        lines += ["", f"Форма может не открыться (строки {r['lines'][0]}–{r['lines'][1]}): " + (f"условие «{scan.shorten(_clean_cond(r['condition'], variables), 80)}»" if r["condition"] else "безусловно")
                  + (f", сообщение «{r['message']}»" if r["message"] else ", без сообщения") + "."]
    for m in code.get("missing") or []:
        lines += ["", f"Код обращается к «{m['name']}», такого элемента на форме нет (строки {m['lines'][0]}–{m['lines'][1]}): `{scan.shorten(m['quote'], 90)}`"
                  + (f"; {m['why']}" if m["why"] else "") + (f"; условие «{scan.shorten(_clean_cond(m['condition'], variables), 70)}»" if m["condition"] else "") + "."]
    if code.get("appearance"):
        lines += ["", "Оформление и списки значений, которые задаёт код (словами; на рисунке не рисуются):", ""]
        for a in code["appearance"]:
            t = a["target"]
            where = "форма" if t["kind"] == "form" else t["element"] if t["kind"] == "element" else f"{t['element'] or 'форма'}/{t['sub']}"
            lines.append(f"- {where}: {'список значений' if a['kind'] == 'list_content' else 'оформление'} — " + (a["value"] or a["why"] or scan.shorten(a["quote"], 80))
                         + (f"; условие «{scan.shorten(_clean_cond(a['condition'], variables), 70)}»" if a["condition"] else "") + f" (строки {a['lines'][0]}–{a['lines'][1]})")
    if code.get("sources"):
        files = sorted({s["file"] for s in code["sources"]})
        lines += ["", f"Эффекты в других модулях (записи с `source`: {len(code['sources'])}; файлы: {', '.join(files)})."]
    if code.get("name_notes"):
        lines += ["", "Имена в записях написаны не так, как на форме (регистр); записи приняты по имени формы: "
                  + "; ".join(f"запись {n['index']} — {', '.join(n['notes'])}" for n in code["name_notes"]) + "."]
    if code.get("others"):
        lines += ["", "Прочитано, но записано как «прочее» (модель не смогла записать иначе):", ""]
        lines += [f"- строки {o['lines'][0]}–{o['lines'][1]}: {moduleview.safe_text(o['why'], variables) or 'текст модели убран: в нём учётные данные или переменные модуля'}" for o in code["others"]]
    if code.get("by_data"):
        lines += ["", "Код строит по данным (имя — выражение; на форме в файле этого нет):", ""]
        for b in code["by_data"]:
            t = b["target"]
            where = {"page": "страница", "column": "колонка", "button": "кнопка", "element": "элемент"}[t["kind"]] + (f" {t['element']}" if t.get("element") else "")
            lines.append(f"- {where}: имя `{scan.shorten(b['name_expr'], 50)}`" + (f", {b['value']}" if b["value"] else "") + (f"; {b['condition']}" if b["condition"] else "")
                         + f" (строки {b['lines'][0]}–{b['lines'][1]})")
    cover = module.get("coverage") or {}
    if cover.get("handlers") is not None and code.get("state") == "parsed":
        lines += ["", f"Разобрано {cover['unit']} {cover['parsed']} из {cover['handlers']} (событий в таблице {cover['events']}); из них умолчаний, о которых запись не нужна, — {cover['defaults']}."]
        if cover.get("unparsed"):
            lines += [f"Не разобран: {', '.join(cover['unparsed'][:30])}" + (f" …и ещё {len(cover['unparsed']) - 30}" if len(cover["unparsed"]) > 30 else "")
                      + " — прочтите в модуле: запись при частности, default при умолчании (`docs/brief-code.md`)."]
    if cover.get("absent"):
        lines += ["", "Обработчики из файла формы без процедуры в модуле (разбирать нечего, в счёт «разобрано N из M» не входят): " + ", ".join(cover["absent"][:12]) + "."]
    if code.get("uncovered"):
        shown = code["uncovered"][:UNCOVERED_SHOWN]
        lines += ["", "Не разобрано на пути открытия (строки указателя задания без записей; запись или `other` с причиной): "
                  + "; ".join(f"{u['file']} {u['line']} `{scan.shorten(u['text'], 60)}`" for u in shown) + (f"; …и ещё {len(code['uncovered']) - len(shown)}; полный перечень — {UNCOVERED_FILE} рядом с досье" if len(code["uncovered"]) > len(shown) else "") + "."]
    if code.get("warnings"):
        lines += ["", "Предупреждения разбора:", ""] + [f"- {w}" for w in code["warnings"]]
    if code.get("rejected"):
        lines += ["", "Разбор кода: отклонённые записи (в досье не вошли; исправьте `code-notes.json` и соберите досье заново):", ""]
        lines += [f"- запись {r['index']} ({r['kind'] or '?'}): {r['why']}" for r in code["rejected"]]
    return lines


def _effect_prop(effect, prop):
    values = [v for v in effect["props"][prop] if v] if prop != "текущая страница" else []
    return prop + (f" ({'/'.join(values)})" if values else "")


def _short_of(structure):
    """Функция «имя в структуре → короткое имя» по таблице элементов структуры."""
    table = {e["element"]: e["short"] for e in structure["elements"]}
    return lambda name: table.get(name, name)
