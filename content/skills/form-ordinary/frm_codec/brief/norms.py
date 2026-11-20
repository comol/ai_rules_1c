"""Раздел «нормы вида» досье: показатели вне диапазона большинства."""

from .. import describe, lint, patterns
from . import vocab
from .fmt import _list, _measure_label, _pct, _table


def _norm_row(key, label, off, row, lo, hi, covered, words=None):
    value, part, votes = row["by_config"][0]
    seen = next((p for v, p, *_ in row["by_form"] if v == value), None)
    return {"key": key, "label": label, "have": off, "norm": value, "norm_configs": votes, "configs": row["configs"],
            "norm_forms_share": seen, "range": [lo, hi], "covered": covered, "words": words}


def _multiline_of(names, name):
    """Элемент `name` — многострочное поле ввода: норма высоты поля — про однострочные, такие поля в неё не входят."""
    item = names.item_of.get(name) if name else None
    return item is not None and item.type == "TextBox" and describe._multiline(item)


def _norms(rec, kind, structure, table, names):
    out = {"kind": kind, "status": "judged", "rows": [], "judged": [], "not_judged": {}, "words": None}
    block = table["kinds"].get(kind)
    if block is None:
        out["status"] = "no_norms"
        out["words"] = f"норм у вида «{kind}» нет ({lint._why_no_norms(kind)}): отклонения не определяются"
        return out
    if block.get("thin"):
        out["status"] = "thin"
        out["words"] = (f"вид «{kind}» есть в {block['configs']} конфигурациях (меньше {patterns.THIN_CONFIGS}): "
                        "норм он не даёт, отклонения не определяются")
        return out
    out["norm_forms"], out["norm_configs"] = block["forms"], block["configs"]
    who = {}
    values = patterns._measures(rec, who)
    stack = lint._stack(rec)

    def node_of(name):
        return structure.by_element.get(name) if name else None

    for key in list(lint.RHYTHM) + list(lint.ANCHORS):
        row, seen = block.get(key), values.get(key)
        if not row or not seen:
            continue
        status, span = lint.verdict(key, row)
        if status != "judged":
            out["not_judged"].setdefault(status, []).append(key)
            continue
        lo, hi, covered = span
        who_names = who[key]
        if key == "table_right_bottom_to_form" and stack is not None:
            seen, who_names = [stack[1]], [stack[0]]
        out["judged"].append(key)
        off = [{"value": v, "element": n, "node": node_of(n), "short": names.short(n) if n else None}
               for v, n in zip(seen, who_names) if (v < lo or v > hi) and not (key == "field_height" and _multiline_of(names, n))]
        if not off:
            continue
        if key in lint.RHYTHM:
            out["rows"].append(_norm_row(key, lint.RHYTHM[key], off, row, lo, hi, covered))
        else:
            words = lint.ANCHORS[key][1]
            for item in off:
                item["words"] = words[item["value"]]
            out["rows"].append(_norm_row(key, vocab.ANCHOR_LABELS[key], off, row, lo, hi, covered, words={str(k): v for k, v in words.items()}))
    seen = values.get("label_text_gap")
    if seen:
        row, why = patterns.gap_row(table, kind)
        if row is not None:
            floor, share, total = row["floor"]
            out["judged"].append("label_text_gap")
            off = [{"value": v, "element": n, "node": node_of(n), "short": names.short(n) if n else None}
                   for v, n in zip(seen, who["label_text_gap"]) if v < floor]
            if off:
                item = _norm_row("label_text_gap", vocab.GAP_LABEL, off, row, floor, None, 1 - share)
                item["floor"] = floor
                item["pairs"] = total
                item["shared"] = bool(why)
                out["rows"].append(item)
    return out


def _md_norms(norms):
    lines = ["## 5. Нормы вида", ""]
    if norms["status"] != "judged":
        return lines + [norms["words"], ""]
    lines.append(f"Нормы вида «{norms['kind']}» — по {norms['norm_forms']} формам из {norms['norm_configs']} конфигураций; "
                 "показаны только отклонения от диапазона большинства форм вида (высота поля — только у однострочных полей).")
    if not norms["rows"]:
        lines += ["", f"Отклонений нет (проверено показателей: {len(norms['judged'])})." if norms["judged"] else "Показателей, которые можно сверить с нормой этого вида, на форме не нашлось: проверять нечего."]
    else:
        rows = []
        for r in norms["rows"]:
            have = _list(f"{h['value'] if 'words' not in h else h['words']} у «{h['short']}»" if h["element"]
                         else str(h["value"]) for h in r["have"])
            node = ", ".join(sorted({h["node"] for h in r["have"] if h["node"]}))
            share = f"{_pct(r['norm_forms_share'])} форм" if r["norm_forms_share"] is not None else ""
            if "floor" in r:
                rng = f"не меньше {r['floor']}" + (" (общая по корпусу)" if r["shared"] else "")
                norm = f"{r['norm']}: {r['norm_configs']} из {r['configs']} конфигураций"
            else:
                lo, hi = r["range"]
                rng = f"{lo}–{hi}" if lo != hi else str(lo)
                norm = f"{r['norm']}: {r['norm_configs']} из {r['configs']} конфигураций, {share}"
            if r["key"] in ("field_right_to_form", "table_right_bottom_to_form", "bottom_bar_to_form", "bottom_bar_full_width",
                            "top_bar_full_width", "field_x_aligned", "field_x_columns") and r["words"]:
                norm = f"{r['words'].get(str(r['norm']))}: {r['norm_configs']} из {r['configs']} конфигураций, {share}"
                rng = r["words"].get(str(r["range"][0])) if r["range"][0] == r["range"][1] else "оба значения"
            rows.append([node, r["label"], have, norm, rng])
        lines += [""] + _table(["Узел", "Показатель", "У формы", "Норма вида (самое частое значение)", "Диапазон большинства"], rows)
    if norms["not_judged"]:
        words = {"thin": "данных меньше трёх конфигураций", "nomajority": "нет явного большинства", "wide": "значения не собираются в одну группу"}
        lines += [""] + [f"Не проверялись ({words[k]}): {', '.join(_measure_label(key) for key in v)}."
                         for k, v in norms["not_judged"].items()]
    return lines + [""]
