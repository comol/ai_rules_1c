"""Места формы, на которых код меняет, что видно: страницы панелей и варианты на одном месте.

* страница панели, видимость которой задаёт код (`ЭлементыФормы.<Панель>.Страницы.<Имя>.Видимость = …`): у узла страницы в дереве и в строке закладок —
  пометка «видимость задаёт код: …»; страница, которую код только прячет, названа «на экране её нет»;
* элементы на одном месте, видимость которых переключает код (`variants`): досье называет всех вариантов места, рисунок — одного.

Код читается по присваиваниям (`brief.module_effects`), а не исполняется: пометка говорит, чем задана видимость, а не что покажет форма при открытии."""
from .. import variants
from . import content

PAGE_PROP = "видимость"


def _page_words(effect, detail):
    """`(слова, прячется ли безусловно)` о видимости страницы по записи перечня `effect`; `detail(effect, свойство)` — слова о выражении и условии."""
    values = effect["props"].get(PAGE_PROP) or []
    bits = detail(effect, PAGE_PROP)
    if values == ["Ложь"] and not bits:
        return "код прячет её безусловно: на экране её нет", True
    if bits:
        return "видимость задаёт код: " + "; ".join(bits), False
    return "видимость задаёт код (" + "/".join(values) + ")", False


def pages(form, names, page_nodes, effects, detail):
    """Страницы панелей, видимость которых задаёт код: `{номер узла страницы: {"page", "panel", "words", "gone"}}`.

    `page_nodes` — `{(панель, номер страницы): (номер узла, подпись)}` (`brief._page_nodes`); `effects` — перечень «что код меняет»
    (`brief.module_effects.group`); `detail` — слова о выражении и условии записи (`brief._effect_detail`)."""
    by_name = {(panel, (name or "").casefold()): at for (panel, at), name in content.page_names(form, names).items()}
    out = {}
    for effect in effects:
        part = effect.get("part") or ""
        if not part.startswith("страница ") or PAGE_PROP not in effect["props"]:
            continue
        at = by_name.get((effect["element"], part[len("страница "):].casefold()))
        node = page_nodes.get((effect["element"], at)) if at is not None else None
        if node is None:
            continue
        words, gone = _page_words(effect, detail)
        out[node[0]] = {"page": part[len("страница "):], "panel": effect["element"], "words": words, "gone": gone}
    return out


def variant_places(form, names, marks):
    """Варианты на одном месте: `[{"elements": [имена в структуре], "nodes": [номера узлов], "drawn": имя}]` — по всем родителям формы.

    `marks` — пометки кода (`brief.images.marks_of`, в них `groups` и `defaults`); места элементов — `Item.box` при размере формы."""
    out = []
    for key, holder in form.holders.items():
        entries = [(it, tuple(it.box)) for it in holder.children if it.box is not None]
        for members in variants.groups(entries, marks):
            first = variants.drawn(members, defaults=marks.defaults)
            labels = [names.of(m) for m in members]
            out.append({"elements": labels, "nodes": [names.node(n) for n in labels],
                        "drawn": names.of(first) if first is not None else None})
    return out


def tree_notes(page_marks, places, names):
    """`{номер узла: слова}` для `Structure.lines`: пометки страниц и вариантов."""
    out = {node: info["words"] for node, info in page_marks.items()}
    for place in places:
        for name, node in zip(place["elements"], place["nodes"]):
            others = [names.short(n) for n in place["elements"] if n != name]
            words = f"вариант на том же месте: {', '.join(others)} (видимость задаёт код)"
            out[node] = f"{out[node]}; {words}" if node in out else words
    return out


def element_marks(places, page_marks, names):
    """`{имя элемента: [слова]}` для строк таблицы структуры: варианты у элементов и видимость страниц у панели."""
    out = {}
    for place in places:
        for name in place["elements"]:
            others = [names.short(n) for n in place["elements"] if n != name]
            out.setdefault(name, []).append("вариант на том же месте: " + ", ".join(f"«{o}»" for o in others))
    panels = {}
    for node, info in page_marks.items():
        panels.setdefault(info["panel"], []).append((node, info))
    for panel, found in panels.items():
        found.sort(key=lambda pair: (len(pair[0]), pair[0]))
        out.setdefault(panel, []).append("видимость страниц задаёт код: " + ", ".join(node for node, _info in found)
                                          + ("; на экране нет: " + ", ".join(node for node, info in found if info["gone"]) if any(i["gone"] for _n, i in found) else ""))
    return out
