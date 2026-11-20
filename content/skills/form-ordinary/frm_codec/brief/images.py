"""Три картинки досье формы: чистая, размеченная и поведение при растяжении.

* `clean` — форма на исходном размере без пометок (`render.render`).
* `marked` — та же форма со слоем наложений (`render.render(overlay=…)`): номера узлов структуры у левого верхнего угла
  узла, рамки областей, страниц, групп, колонок и областей содержимого разными цветами, кружки с номерами порядка обхода
  (`tab_order` из файла) у элементов, куда можно перейти с клавиатуры, красные штриховые рамки у узлов «неясно». Слов и легенды на картинке нет.
* `behavior` — полоса кадров `strip.strip(plain=True)`: минимум раскладки, исходный размер, окно «+200 по ширине, +100 по высоте» и предел
  роста, если он конечен. У кадров подписан только размер окна; значки поведения (растёт, сдвигается, на долю роста окна, мёртвое правило) стоят на кадре «как в файле», а слова кадров
  и легенда значков — в тексте досье (раздел «Картинки»).

Длинная сторона каждой картинки — не больше `MAX_SIDE` px: крупная картинка уменьшается (`viewBox` у корня SVG, содержимое
не пересчитывается), метки при этом крупнеют, чтобы читались. Нет конвертера SVG → PNG — все три картинки пишутся как SVG,
а `note` объясняет, что модели они недоступны.
"""
import collections
import pathlib
import re

from frm_codec import edit, layout, preview, render, strip
from frm_codec.render.core import _enabled
from . import module_effects as module

MAX_SIDE = 1600
GROW_W, GROW_H = 200, 100                     # кадр «окно шире на 200, выше на 100»
NO_TAB = frozenset({"Label", "GroupBox", "Splitter", "PictureBox", "CommandBar", "Panel"})  # в обход с клавиатуры не входят
SVG_NS = "xmlns='http://www.w3.org/2000/svg'"
SVG_ONLY_NOTE = ("картинки модели недоступны: {why} Оценка по тексту досье возможна, но слабее — номера узлов на размеченной "
                 "картинке сверить нечем.")

Overlay = collections.namedtuple("Overlay", "nodes tab unclear scale", defaults=(1.0,))
# nodes: [(номер, роль, box)], tab: [(имя, номер, box)], unclear: [box]; box — (лево, верх, право, низ) в клиентской области,
# scale — масштаб итоговой картинки (метки крупнеют, чтобы после уменьшения читались).


def _names(form):
    """`{имя в структуре: индекс}`: имя с родителем, у тёзок в одном родителе — с `#индекс` (как у `structure`)."""
    counts = collections.Counter(it.qualified() for it in form.items.values())
    return {(it.qualified() if counts[it.qualified()] == 1 else f"{it.qualified()}#{it.index}"): it.index
            for it in form.items.values()}


def _union(boxes):
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def overlay_of(doc, structure, rendered=None, scale=1.0):
    """Слой наложений по структуре. Узел получает объединение нарисованных элементов своих и дочерних узлов; узлы, у которых
    ни один элемент не нарисован (скрытые, на непоказанной странице), в слой не входят. `A0` не размечается: это вся форма."""
    rendered = rendered if rendered is not None else render.render(doc)
    form = layout.read(doc)
    names = _names(form)
    drawn = {item.index: (x, y, x + w, y + h) for item, (x, y, w, h) in rendered.items}
    items = {index: form.items[index] for index in drawn}

    def own(node):
        return [drawn[names[n]] for n in node.elements if n in names and names[n] in drawn]

    def box_of(node):
        boxes = own(node) + [b for child in node.children for b in [box_of(child)] if b is not None]
        return _union(boxes) if boxes else None

    nodes, unclear = [], []
    for node in structure.walk():
        if node.id == "A0":
            continue
        box = box_of(node)
        if box is None:
            continue
        nodes.append((node.id, node.role, box))
        if node.role == "unclear":
            unclear.append(_union(own(node)) if own(node) else box)   # рамка обводит сам элемент, а не вложенное в панель
    tab = []
    for name, index in sorted(names.items(), key=lambda kv: kv[1]):
        item = items.get(index)
        if item is None or item.type in NO_TAB or item.coords is None:
            continue
        order = item.coords.get(edit.TAB_ORDER)
        if isinstance(order, int) and not isinstance(order, bool):
            tab.append((name, order, drawn[index]))
    return Overlay(nodes, tab, unclear, scale)




def _only_shows(item, prop, values):
    """Условная запись, которая только показывает: `Видимость = Истина` у элемента, видимого в файле, и `Доступность = Истина` у доступного в файле ничего на экране не меняют (прятать
    нечему), и штриховкой «видимость задаёт код» помечаться не должны."""
    if item is None or not values or any(v != "Истина" for v in values):
        return False
    if prop == "видимость":
        return bool(item.visible)
    if prop == "доступность":
        return _enabled(item.node) is not False
    return False


def marks_of(doc, structure, effects, form_rows=()):
    """`{индекс элемента: {свойство: [значения]}}` — что код модуля меняет у элементов по записям разбора (`brief.module_effects.group`): только то, что код делает по условию
    или вероятно (на картинке не рисуется, называется в `notes` и досье); безусловное и несомненное — в `applied` результата и его `parts` (`render.CodeMarks`): рисунок применяет его.
    Имя элемента в `effects` — имя в структуре (с `#индекс` у тёзок). Страницы панелей и колонки таблиц несут свои сведения в `parts`: страница — по имени страницы в
    коде, колонка — по имени колонки. Варианты на одном месте — `groups` и `defaults`. `form_rows` — что код делает с самой формой (`brief.codenotes.form_rows`): безусловно снятая
    доступность формы — `form_disabled`."""
    from . import content
    from . import facts
    form = layout.read(doc)
    by_name = {}
    for item in form.items.values():
        name = item.qualified()
        by_name[name if name in structure.by_element else f"{name}#{item.index}"] = item.index
    marks = render.CodeMarks()
    form_enabled = [r for r in form_rows or () if r["prop"] == "доступность формы"]
    if form_enabled and all(r.get("applied") for r in form_enabled) and form_enabled[-1]["value"] == "Ложь":
        marks.form_disabled = True
    page_at = None
    switched = set()
    for effect in effects or ():
        index = by_name.get(effect.get("element"))
        if index is None:
            continue
        part = effect.get("part")
        if part is None and "видимость" in effect["props"]:
            switched.add(index)
        applied = effect.get("applied") or {}
        shown = {p: v for p, v in effect["props"].items() if p not in applied or not (module.applies(p, applied[p]) or (p, applied[p]) in module.NOOP)}
        if part is None and "убирает элемент" in applied:
            marks.applied.setdefault(index, {})["видимость"] = "Ложь"          # элемент убран кодом безусловно
            marks.hidden_src[("el", index)] = "код"
        if part is None:
            kept = {p: v for p, v in shown.items() if p in ("видимость", "доступность", "только просмотр", "заголовок") and not _only_shows(form.items.get(index), p, v)
                    and not (p == "заголовок" and p in effect.get("blank", ()))}
            if kept:
                marks.setdefault(index, {}).update(kept)
            if module.VALUE_PROP in applied and module.applies(module.VALUE_PROP, applied[module.VALUE_PROP]):
                marks.field_values[index] = module.value_of(applied[module.VALUE_PROP])          # значение данных поля: флажок, переключатель, текст поля и надписи
            for p, v in applied.items():
                if module.applies(p, v) and p not in ("текущая страница", module.VALUE_PROP):
                    marks.applied.setdefault(index, {})[p] = v
                    if p == "свёртка":
                        marks.collapsed[index] = v
                    if (p, v) == ("видимость", "Ложь"):
                        marks.hidden_src[("el", index)] = "код"
            if "заголовок" in effect.get("blank", ()) and form.items.get(index) is not None:
                marks.applied.setdefault(index, {})["заголовок"] = ""          # заголовок задаёт код выражением: рамка без текста
            if applied.get("видимость") == "Истина" and form.items.get(index) is not None and not form.items[index].visible:
                marks.force_show.add(index)        # безусловное `Видимость = Истина` у скрытого в файле: на экране элемент виден
                marks.parts.setdefault("shown_by_code", set()).add(index)
            for group in effect.get("variants", {}).get("видимость", []):
                marks.groups.setdefault(group, []).append(index)
                if effect.get("variant_default", {}).get(group):
                    marks.defaults.add(index)
            if "текущая страница" in applied:
                if page_at is None:
                    page_at = {(owner, (name or "").casefold()): at for (owner, at), name in content.page_names(form, facts._Names(form, structure)).items()}
                at = page_at.get((_owner_name(by_name, index), applied["текущая страница"].casefold()))
                if at is not None:
                    marks.parts.setdefault("current_page", {})[index] = at
        elif part.startswith("колонка "):
            name = part[len("колонка "):].casefold()
            if shown.get("видимость") or shown.get("заголовок"):
                marks.parts.setdefault("columns", {}).setdefault((index, name), {}).update({p: v for p, v in shown.items() if p in ("видимость", "заголовок")})
            keep = {p: v for p, v in applied.items() if p in ("видимость", "заголовок") and module.applies(p, v)}
            if "убирает колонку" in effect["props"] and "убирает колонку" in applied:
                keep["видимость"] = "Ложь"
            if keep:
                marks.parts.setdefault("applied_columns", {}).setdefault((index, name), {}).update(keep)
            if applied.get("видимость") == "Истина":
                marks.show_columns.add((index, name))        # безусловное `Видимость = Истина` у колонки, скрытой в файле: на экране колонка видна
            if module.CREATED_COLUMN in applied:          # созданная по условию колонка не рисуется: в файле её нет, а на экране она может быть и не быть
                marks.parts.setdefault("new_columns", {}).setdefault(index, []).append({"name": part[len("колонка "):], "title": effect["props"][module.CREATED_COLUMN][0] or part[len("колонка "):]})
        elif part.startswith("кнопка "):
            if "заголовок" in applied and module.applies("заголовок", applied["заголовок"]):
                marks.parts.setdefault("button_titles", {}).setdefault(index, {})[part[len("кнопка "):]] = applied["заголовок"]
            if "пометка" in applied and module.applies("пометка", applied["пометка"]):
                marks.parts.setdefault("checked_buttons", {}).setdefault(index, {})[part[len("кнопка "):].casefold()] = applied["пометка"] == "Истина"
            if applied.get("доступность") == "Ложь":
                marks.parts.setdefault("disabled_buttons", {}).setdefault(index, []).append(part[len("кнопка "):].casefold())          # безусловно недоступная кнопка серая
            for add in effect.get("adds") or ():          # кнопка, которую добавляет код безусловно, рисуется на панели (`render._with_added`); добавленная по условию — нет
                if add.get("conditional"):
                    continue
                marks.parts.setdefault("buttons", {}).setdefault(index, []).append(add)
            if "удаляет кнопку" in shown or any(v != "Истина" for v in shown.get("видимость") or ()):      # видимость кнопки по условию: штрихуется в режиме `conditional=hatch`
                marks.parts.setdefault("cond_buttons", {}).setdefault(index, []).append(part[len("кнопка "):].casefold())
            gone = ("удаляет кнопку" in applied) or applied.get("видимость") == "Ложь"
            if gone:
                marks.parts.setdefault("removed_buttons", {}).setdefault(index, []).append(part[len("кнопка "):].casefold())
        elif part.startswith("страница "):
            if page_at is None:
                page_at = {(owner, (name or "").casefold()): at for (owner, at), name in content.page_names(form, facts._Names(form, structure)).items()}
            at = page_at.get((_owner_name(by_name, index), part[len("страница "):].casefold()))
            if at is not None:
                for prop in ("видимость", "заголовок"):          # условная видимость и вычисляемый заголовок закладки только помечаются
                    if shown.get(prop):
                        marks.parts.setdefault("pages", {}).setdefault((index, at), {})[prop] = shown[prop]
                keep = {p: v for p, v in applied.items() if p in ("видимость", "заголовок") and module.applies(p, v)}
                if "убирает страницу" in applied:
                    keep["видимость"] = "Ложь"
                if keep:
                    marks.parts.setdefault("applied_pages", {}).setdefault((index, at), {}).update(keep)
    _overlapping_variants(form, marks, switched)
    return marks


VARIANT_OVERLAP = 0.5                                   # доля меньшего из двух элементов, которую второй перекрывает: так лежат варианты на одном месте
VARIANT_TYPES = frozenset({"Label", "TextBox", "CheckBox", "ComboBox", "RadioButton", "Button", "PictureBox"})      # рамки, панели и таблицы вариантами места не бывают: они вмещают другие элементы


def _overlap_share(a, b):
    """Доля меньшего из двух мест, которую занимает пересечение (0, когда мест нет или они не пересекаются)."""
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return w * h / smaller if w > 0 and h > 0 and smaller > 0 else 0.0


def _overlapping_variants(form, marks, switched):
    """Элементы одного родителя и одной страницы, видимых в файле, которые код показывает и прячет (запись о видимости) и которые в файле лежат друг на друге (перекрытие не меньше
    `VARIANT_OVERLAP` меньшего места), — варианты на одном месте, даже если модель не назвала `exclusive_group`: на экране остаётся один. Группу, которую назвала модель и в которой несколько элементов, не трогает."""
    named = {i for members in marks.groups.values() if len(members) > 1 for i in members}          # группа из одного элемента вариантом места не считается
    for key, holder in form.holders.items():
        mine = [it for it in holder.children if it.index in switched and it.index not in named and it.type in VARIANT_TYPES and it.visible and it.box is not None]
        clusters = []
        for it in mine:
            joined = [c for c in clusters if c[0].page == it.page and any(_overlap_share(tuple(it.box), tuple(o.box)) >= VARIANT_OVERLAP for o in c)]
            merged = [it] + [o for c in joined for o in c]
            clusters = [c for c in clusters if c not in joined] + [merged]
        for at, cluster in enumerate(c for c in clusters if len(c) > 1):
            marks.groups[f"на одном месте {key}/{at}"] = [it.index for it in sorted(cluster, key=lambda m: m.index)]


def coded_doc(doc, marks):
    """`(документ, не удалось)`: копия документа с заголовками, которые код ставит безусловно (`marks.applied`, `marks.parts["button_titles"]`), для рисунка. Заголовок, который
    редактор поставить не может (имя элемента не единственное, у вида нет заголовка), остаётся без подстановки (заголовок задаёт код): его индекс — в `не удалось`."""
    import copy
    from ..edit import base as ed_base
    form = layout.read(doc)
    titles = {i: p["заголовок"] for i, p in marks.applied.items() if "заголовок" in p}
    buttons = getattr(marks, "parts", {}).get("button_titles") or {}
    if not titles and not buttons and not marks.form_disabled:
        return doc, []
    work, failed = copy.deepcopy(doc), []
    if marks.form_disabled:
        try:
            holder = work["form"]["container"]["layout_holder"]["layout_list"]["layout"]
            holder["enabled"] = False
        except (KeyError, TypeError):
            failed.append(0)
    for index, text in titles.items():
        item = form.items.get(index)
        try:
            if item is None or not item.name:
                raise edit.EditError("безымянный элемент")
            ed_base.set_caption(work, item.name, text)
        except (edit.EditError, KeyError, TypeError, ValueError):
            failed.append(index)
            marks.setdefault(index, {})["заголовок"] = [text]
    for index, named in buttons.items():
        item = form.items.get(index)
        for name, text in named.items():
            try:
                ed_base.set_button_text(work, item.name, name, text)
            except (edit.EditError, KeyError, TypeError, ValueError, AttributeError):
                failed.append(index)
    return work, failed


def _owner_name(by_name, index):
    """Имя панели в структуре по индексу (так её называет `brief.content.page_names`)."""
    return next((name for name, i in by_name.items() if i == index), None)


# ── Страницы, которые меняет код ──

PAGE_PICTURES = 4          # дополнительных картинок страниц, которые меняет код, не больше стольких


def _page_nodes_of(structure):
    """`[(узел страницы, множество имён элементов страницы и вложенных узлов)]` по порядку структуры."""
    out = []

    def collect(node, acc):
        acc.update(node.elements)
        for child in node.children:
            collect(child, acc)
        return acc
    for node in structure.walk():
        if node.role == "page" and node.caption is not None:
            out.append((node, collect(node, set())))
    return out


def code_pages(doc, structure, effects, not_drawn):
    """Страницы, которых нет на `clean.png`, но что-то на них меняет код: `[{node, panel, at, caption, why, score, elements}]`, самые важные первыми, не больше `PAGE_PICTURES`
    с картинкой (`picture` истинно), остальные — только в списке (для них досье даёт команду `render --shown`). Важность: код сам выбирает страницу (3), задаёт видимость страницы (2),
    меняет видимость или доступность элементов на ней (1 за элемент). `panel` — имя панели в структуре; у страниц формы (`panel` пусто) картинки нет."""
    from . import content
    from . import facts
    form = layout.read(doc)
    names = facts._Names(form, structure)
    nodes = _page_nodes_of(structure)
    by_node = {node.id: (node, elems) for node, elems in nodes}
    at_of = {}
    for (owner, at), name in content.page_names(form, names).items():
        at_of[(owner, (name or "").casefold())] = at
    found = {}

    def hit(node, score, why):
        row = found.setdefault(node.id, {"node": node.id, "panel": node.holder, "at": node.page, "caption": node.caption, "score": 0, "whys": [], "elements": 0})
        row["score"] += score
        if why not in row["whys"]:
            row["whys"].append(why)
    for effect in effects or ():
        part, element = effect.get("part"), effect.get("element")
        props = effect.get("props") or {}
        if part is None and "текущая страница" in props:
            for page in props["текущая страница"]:
                at = at_of.get((element, (page or "").casefold()))
                for node, _elems in nodes:
                    if node.holder == element and node.page == at and node.id in not_drawn:
                        hit(node, 3, "код выбирает эту страницу")
        elif part and part.startswith("страница "):
            at = at_of.get((element, part[len("страница "):].casefold()))
            for node, _elems in nodes:
                if node.holder == element and node.page == at and node.id in not_drawn:
                    hit(node, 2, "код задаёт видимость или заголовок закладки")
        elif part is None and element and any(p in props for p in ("видимость", "доступность", "только просмотр", "заголовок")):
            for node, elems in nodes:
                if element in elems and node.id in not_drawn:
                    hit(node, 1, "код меняет элементы страницы")
                    found[node.id]["elements"] += 1
    ranked = sorted(found.values(), key=lambda r: -r["score"])
    strip = content.strip_hidden(form, names)
    out = []
    for row in ranked:
        row["unreachable"] = row["score"] < 3 and (row["panel"] or "") in strip          # закладок нет, и ни одна ветка кода не делает страницу текущей: пользователь её не увидит
        row["picture"] = bool(row["panel"]) and not row["unreachable"] and sum(1 for r in out if r["picture"]) < PAGE_PICTURES
        row["why"] = "код эту страницу не выбирает: закладок нет" if row["unreachable"] else "; ".join(row["whys"])
        row.pop("whys")
        out.append(row)
    return out


def _file_part(text):
    """Часть имени файла картинки: без разделителей путей и пробелов."""
    return re.sub(r"[\\/:*?\"<>|\s]+", "_", str(text)).strip("_") or "страница"


def _show_page(doc, structure, marks, holder, at):
    """Страница `at` панели `holder`, которую код по умолчанию прячет, на картинке показана: снимает с неё безусловное «видимость — Ложь» (и условную пометку), а с самой панели и с панелей, в которых она лежит,
    — безусловное «видимость — Ложь» от кода, а скрытую в файле панель, которую код показывает по условию, показывает (спрятанная панель скрывает страницу вместе с содержимым); `True`, когда что-то из этого было скрыто."""
    form = layout.read(doc)
    for item in form.items.values():
        name = item.qualified()
        if (name if name in structure.by_element else f"{name}#{item.index}") != holder:
            continue
        key = (item.index, at)
        was = (marks.parts.get("applied_pages") or {}).get(key, {}).get("видимость") == "Ложь"
        for part in ("applied_pages", "pages"):
            props = (marks.parts.get(part) or {}).get(key)
            if props and "видимость" in props:
                props.pop("видимость")
                if not props:
                    marks.parts[part].pop(key)
        owner = item
        while owner is not None:
            props = marks.applied.get(owner.index)
            if props and props.get("видимость") == "Ложь":
                props.pop("видимость")
                marks.hidden_src.pop(("el", owner.index), None)
                was = True
            if not owner.visible and marks.get(owner.index, {}).get("видимость"):          # скрыта в файле, а код показывает её по условию: на картинке показана
                marks.force_show.add(owner.index)
                marks.parts.setdefault("shown_by_code", set()).add(owner.index)
                was = True
            owner = getattr(owner, "owner", None)
        return was
    return False


def _page_chain(structure, row):
    """Страницы, на которых лежит панель страницы `row` (от внешней к внутренней): чтобы показать вложенную страницу, надо открыть и их."""
    chain = [(node.holder, node.page) for node, elems in _page_nodes_of(structure) if row["panel"] in elems and node.holder and node.page is not None]
    return [x for x in chain if x != (row["panel"], row["at"])]


def _page_pictures(doc, structure, effects, form_rows, pages, out, hidden, conditional):
    """`{ключ файла: svg}` картинок страниц, которые меняет код: страница открыта через состояние `pages`, остальное как на `clean`. Страница, которую рендер открыть не смог, пропускается
    (`picture` ложно, в `why` — причина)."""
    from .. import formstate
    pictures = {}
    for row in pages:
        if not row["picture"]:
            continue
        marks = marks_of(doc, structure, effects, form_rows)
        marks.hatch_hidden = hidden == "hatch"
        marks.hatch_conditional = conditional == "hatch"
        chain = _page_chain(structure, row)
        row["when_shown"] = any([_show_page(doc, structure, marks, holder, at) for holder, at in chain + [(row["panel"], row["at"])]])          # скрытая по умолчанию страница (и страницы над ней) рисуется так, как выглядит при показе
        try:
            formstate.apply(doc, {"pages": dict({holder: str(at) for holder, at in chain}, **{row["panel"]: str(row["at"])})}, marks)
            marks.hatch_hidden = hidden == "hatch"
            marks.hatch_conditional = conditional == "hatch"
            shown_doc, _failed = coded_doc(doc, marks)
            svg = render.render(shown_doc, marks=marks or None).svg
        except (formstate.StateError, edit.EditError, ValueError) as why:
            row["picture"], row["why"] = False, row["why"] + f" (картинка не построена: {why})"
            continue
        key = f"clean-{_file_part(row['panel'].split('/')[-1])}-{_file_part(row['caption'])}"
        pictures[key], _scale = fit(svg)
        row["key"] = key
    return pictures


# ── Масштаб и запись ──

def fit(svg):
    """`(svg, масштаб)`: длинная сторона не больше `MAX_SIDE`. Масштаб < 1 — обёртка `viewBox` у корня: размеры корня
    уменьшаются, содержимое то же."""
    size = preview.svg_size(svg)
    if size is None:
        return svg, 1.0
    scale = min(1.0, MAX_SIDE / max(size))
    if scale >= 1.0:
        return svg, 1.0
    w, h = size
    nw, nh = max(round(w * scale), 1), max(round(h * scale), 1)
    root = re.search(r"<svg\b[^>]*>", svg)
    tag = re.sub(r"\bwidth=['\"][0-9.]+['\"]", f"width='{nw}'", root.group(0), count=1)
    tag = re.sub(r"\bheight=['\"][0-9.]+['\"]", f"height='{nh}' viewBox='0 0 {w} {h}'", tag, count=1)
    return svg[:root.start()] + tag + svg[root.end():], round(nw / w, 4)


def _behavior_svg(doc, red=(), marks=None):
    """`(svg, слова кадров, слова легенды, причина)`: полоса `strip.strip` без слов на картинке (у кадров только размер окна); слова — в досье. Форма, для которой кадры не строятся,
    получает пустую картинку, причина — словами в досье."""
    base = f"min,{doc['form']['width']}x{doc['form']['height']},{doc['form']['width'] + GROW_W}x{doc['form']['height'] + GROW_H},max"
    if doc.get("size_change") == "DontChange":
        base = f"{doc['form']['width']}x{doc['form']['height']}"     # окно фиксированного размера не растягивается: кадров роста нет
    try:
        got = strip.strip(doc, base, red=red, marks=marks or None, plain=True)
        return got.svg, got.frames, got.legend, None
    except ValueError as why:
        return f"<svg {SVG_NS} width='600' height='60'><rect width='600' height='60' fill='#e8e8e8'/></svg>", [], [], f"кадров нет: {why}"


def write_images(doc, structure, out_dir, red=(), effects=(), form_rows=(), hidden="hatch", state=None, conditional="plain"):
    """Пишет `clean`, `marked` и `behavior` в `out_dir` (PNG, а без конвертера — SVG) и возвращает
    `red` — квалифицированные имена виновников столкновения и залипания: на кадрах предела они обведены красным.
    `{"clean": путь, "marked": путь, "behavior": путь, "scale": масштаб clean и marked, "behavior_scale": масштаб полосы,
    "format": "png"|"svg", "note": слова или None, "not_drawn": [номера узлов, которых на картинке нет]}`. Нарисована страница 0
    каждой панели и формы; узлы других страниц и невидимых элементов в `not_drawn`."""
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for old in list(out.glob("clean-*.png")) + list(out.glob("clean-*.svg")):          # картинки страниц прежнего запуска устарели
        old.unlink()
    marks = marks_of(doc, structure, effects, form_rows)
    marks.hatch_hidden = hidden == "hatch"
    marks.hatch_conditional = conditional == "hatch"
    size = None
    if state:
        from .. import formstate
        _marks, size = formstate.apply(doc, state, marks)
        if "hidden" not in state:
            marks.hatch_hidden = hidden == "hatch"
        if "conditional" not in state:
            marks.hatch_conditional = conditional == "hatch"
    shown_doc, _failed = coded_doc(doc, marks)
    clean = render.render(shown_doc, size[0] if size else None, size[1] if size else None, marks=marks or None)
    # штриховка условного: меняется ли картинка от неё (если нет, условные варианты на картинке не отличимы от нарисованного)
    mode = marks.hatch_conditional
    marks.hatch_conditional = not mode
    other = render.render(shown_doc, size[0] if size else None, size[1] if size else None, marks=marks or None).svg
    marks.hatch_conditional = mode
    same = other == clean.svg
    size = clean.size
    scale = min(1.0, MAX_SIDE / max(size))
    overlay = overlay_of(doc, structure, clean, scale)
    marked_svg = render.render(shown_doc, size[0] if size else None, size[1] if size else None, overlay=overlay, marks=marks or None).svg
    behavior_svg, behavior_frames, behavior_legend, behavior_why = _behavior_svg(shown_doc, red, marks)
    pictures = {"clean": clean.svg, "marked": marked_svg,         # слов, пометок и легенды на картинках нет: условности — в разделе 8 досье
                "behavior": behavior_svg}
    scales = {}
    for key in pictures:
        pictures[key], scales[key] = fit(pictures[key])
    drawn = {ident for ident, _role, _box in overlay.nodes}
    result = {"scale": min(scales["clean"], scales["marked"]), "behavior_scale": scales["behavior"], "format": "png", "note": None,
              "hidden_mode": "hatch" if marks.hatch_hidden else "hide", "conditional_mode": "hatch" if marks.hatch_conditional else "plain", "conditional_same": same, "requested": list(marks.requested),
              "behavior_frames": behavior_frames, "behavior_legend": behavior_legend, "behavior_why": behavior_why,
              "code_notes": [n for n in clean.notes if "по разбору кода" in n or "по запросу" in n or "режим скрытого" in n or "режим условного" in n or "вариантов на одном месте" in n or "один из вариантов" in n],
              "not_drawn": [n.id for n in structure.walk() if n.id != "A0" and n.id not in drawn]}
    result["code_pages"] = code_pages(doc, structure, effects, set(result["not_drawn"]))
    pictures.update(_page_pictures(doc, structure, effects, form_rows, result["code_pages"], out, hidden, conditional))
    try:
        for key, svg in pictures.items():
            preview.svg_to_png(svg, out / f"{key}.png")
            (out / f"{key}.svg").unlink(missing_ok=True)
            result[key] = str(out / f"{key}.png")
        clean_bytes = (out / "clean.png").read_bytes()
        kept = {}
        for row in result["code_pages"]:
            if row.get("key"):
                row["file"] = f"{row.pop('key')}.png"
                data = (out / row["file"]).read_bytes()
                if data == clean_bytes:          # страница выглядит так же, как clean.png: отдельная картинка ничего не добавляет
                    (out / row["file"]).unlink()
                    row["file"], row["picture"], row["same_as_clean"] = None, False, True
                elif data in kept:          # и так же, как уже записанная страница: вторая такая же картинка не пишется
                    (out / row["file"]).unlink()
                    row["file"], row["picture"], row["same_as_page"] = None, False, kept[data]
                else:
                    kept[data] = row["caption"]
    except preview.PngUnavailable as why:
        for key, svg in pictures.items():
            (out / f"{key}.png").unlink(missing_ok=True)
            (out / f"{key}.svg").write_text(svg, encoding="utf-8")
            result[key] = str(out / f"{key}.svg")
        kept = {}
        for row in result["code_pages"]:
            if row.get("key"):
                row["file"] = f"{row.pop('key')}.svg"
                data = (out / row["file"]).read_text(encoding="utf-8")
                if data == pictures["clean"]:
                    (out / row["file"]).unlink()
                    row["file"], row["picture"], row["same_as_clean"] = None, False, True
                elif data in kept:
                    (out / row["file"]).unlink()
                    row["file"], row["picture"], row["same_as_page"] = None, False, kept[data]
                else:
                    kept[data] = row["caption"]
        result["format"], result["note"] = "svg", SVG_ONLY_NOTE.format(why=str(why).rstrip(".") + ".")
    return result
