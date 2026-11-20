"""Раздел «стиль конфигурации» досье: те же показатели у соседних форм того же вида в выгрузке."""

import collections
import concurrent.futures
import functools
import os
import pathlib

from .. import census, formsource, lint, lstring, patterns, typed
from .. import structure as structure_mod
from . import words as br_words, vocab
from .fmt import _measure_label, _table
from .paths import _inside, _meta_key


def _measured(measures):
    return {k: v for k, v in measures.items() if k in lint.RHYTHM or k in lint.ANCHORS or k == "label_text_gap"}


def _neighbor(path, main=None):
    """Вид и показатели соседней формы либо `None`, если форму не прочесть. Работает в процессе пула, поэтому на верхнем уровне;
    основной язык выгрузки (`main`) приходит параметром: процесс пула контекста родителя не наследует."""
    try:
        doc = typed.decode(formsource.read_form_node(path))
        with lstring.main_language(main):
            rec = census.record(doc, str(path))
            return rec["kind"], _measured(patterns._measures(rec))
    except Exception:  # noqa: BLE001 — нечитаемый сосед в свод не идёт и досье не прерывает
        return None


def _mode(values):
    count = collections.Counter(values)
    return min(count, key=lambda v: (-count[v], patterns._vkey(v)))


def _style(rec, kind, form_path, config_dir, table, meta, origin=None):
    out = {"config": config_dir is not None, "forms": 0, "found": 0, "unread": 0, "rows": [], "words": None}
    if config_dir is None:
        out["words"] = "выгрузка конфигурации не задана (`--config`): стиль конфигурации не определяется"
        return out
    paths = formsource.sibling_paths(config_dir, [form_path] + ([origin] if origin else []))
    key_of_form = _meta_key(pathlib.Path(form_path).resolve().parent)
    if key_of_form is not None and not _inside(form_path, config_dir):
        # форма вне выгрузки, а её копия в выгрузке есть (тот же путь от каталога вида объекта): соседом себе она не бывает
        paths = [p for p in paths if _meta_key(p.parent) != key_of_form]
    if len(paths) > vocab.POOL_FROM:
        with concurrent.futures.ProcessPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) - 2)) as pool:
            read = list(pool.map(functools.partial(_neighbor, main=lstring.current_main()), paths, chunksize=8))
    else:
        read = [_neighbor(p, lstring.current_main()) for p in paths]
    out["found"] = len(paths)
    out["unread"] = sum(1 for r in read if r is None)
    same = [measures for r in read if r is not None for k, measures in [r] if k == kind]
    out["forms"] = len(same)
    if not same:
        out["words"] = "соседних форм того же вида в выгрузке нет: " + vocab.WITHOUT["neighbors"]
        return out
    own = patterns._measures(rec)
    for key in list(lint.RHYTHM) + list(lint.ANCHORS) + ["label_text_gap"]:
        if not own.get(key):
            continue
        modes = [_mode(m[key]) for m in same if m.get(key)]
        if len(modes) < vocab.STYLE_MIN:
            continue
        top = _mode(modes)
        have = modes.count(top)
        count = collections.Counter(own[key])
        mixed = len(count) > 1 and max(count.values()) == 1        # все значения у формы разные: «самого частого» нет
        mine = None if mixed else _mode(own[key])
        corpus = patterns.norm(table, kind, key)
        label = _measure_label(key)
        row = {"key": key, "label": label, "own": mine, "mixed": mixed, "own_count": len(own[key]), "style": top, "forms": have,
               "of": len(modes), "corpus_norm": corpus,
               "differs": (not mixed) and mine != top, "differs_from_corpus": corpus is not None and top != corpus}
        if key in lint.ANCHORS:
            words = lint.ANCHORS[key][1]
            row["own_words"], row["style_words"] = words.get(mine), words.get(top)
            row["corpus_norm_words"] = words.get(corpus)
        else:
            row["corpus_norm_words"] = corpus
        out["rows"].append(row)
    return out


def _style_behaviour_notes(style, behavior):
    """Показатели привязок стиля — про прямую запись привязки на форму; раздел «Поведение» — про итог (привязка к соседу тоже следует за
    окном). Строка стиля «нижняя панель не привязана к низу формы» рядом с «сдвигается вниз вместе с краем окна» без пояснения выглядит
    противоречием: у такой строки `behavior_note` говорит, что итог — следование за окном."""
    follows = [n["node"] for n in behavior.get("nodes", []) if n["role"] == structure_mod.BOTTOM_BAR and "moves" in n["height"]]
    if not follows:
        return
    for row in style.get("rows", []):
        if row["key"] == "bottom_bar_to_form" and row["own"] == 0:
            row["behavior_note"] = (f"привязка записана не прямо на низ формы, но по разделу «Поведение» нижняя панель ({', '.join(follows)}) "
                                    "сдвигается вниз вместе с краем окна: в предприятии итог — следование за окном")


EDGE_ANCHORS = ("field_right_to_form", "table_right_bottom_to_form", "bottom_bar_to_form", "bottom_bar_full_width", "top_bar_full_width")


def _md_style(style, norms, fixed=False):
    lines = ["## 6. Стиль конфигурации", ""]
    if style["words"]:
        return lines + [style["words"], ""]
    lines.append(f"Соседних форм того же вида в выгрузке: {style['forms']}"
                 + (f" (прочитано не удалось: {style['unread']})" if style["unread"] else "")
                 + ". Показатель формы — его самое частое значение у формы; показаны показатели, которые есть не меньше чем у "
                   f"{vocab.STYLE_MIN} соседей.")
    if not style["rows"]:
        return lines + ["", "Показателей с достаточным числом соседей нет.", ""]
    rows, same = [], []
    for r in style["rows"]:
        if fixed and r["key"] in EDGE_ANCHORS:
            continue
        own = r.get("own_words") or r["own"]
        top = r.get("style_words") or r["style"]
        mark = []
        if r.get("mixed"):
            mark.append(f"у формы {r['own_count']} " + br_words.plural(r["own_count"], "разное значение", "разных значения", "разных значений") + ", общего нет")
        elif r["differs"]:
            mark.append("у формы иначе")
        if r["differs_from_corpus"]:
            norm = r["corpus_norm_words"] if r.get("corpus_norm_words") is not None else r["corpus_norm"]
            mark.append(f"стиль отличается от нормы вида ({norm})")
        if r.get("behavior_note"):
            mark.append(r["behavior_note"])
        if not mark:
            same.append(r["label"])
            continue
        rows.append([r["label"], "разные" if r.get("mixed") else own, f"{top} — у {r['forms']} из {r['of']} форм", "; ".join(mark)])
    if rows:
        lines += [""] + _table(["Показатель", "У формы", "В конфигурации", "Пометка"], rows)
    if same:
        lines += ["", "Совпадают с конфигурацией и с нормой вида: " + ", ".join(same) + "."]
    return lines + [""]
