"""Страница панели по ссылке: один способ назвать страницу для `render --shown`, `layout --shown` и `--state pages` (и так же её называет досье).

Ссылка — любое из четырёх:

* имя закладки как в обзоре досье — подпись («Параметры отчета»), без учёта регистра;
* имя страницы в файле (то, что код пишет после `Страницы.`);
* узел структуры досье `T2` — закладка `T2` в разделе «Структура» («Закладки страниц панели «Панель1»: T1 — «Основное»; T2 — …»); панель при ней называть не надо;
* номер страницы с нуля (`0`, `2`); безымянная страница — «страница N» (то же число).

Название, которое подходит двум страницам одной панели, — отказ с перечнем номеров: догадки нет. Страница, которой у панели нет, — отказ с перечнем того, что есть."""
import re

from . import structure as structure_mod
from .render import page_names_of
from .render.core import _page_captions

NODE = re.compile(r"^[Tt]\d+$")


def pages_of(form, owner):
    """`{номер с нуля: (имя в файле, подпись закладки)}` страниц панели (`owner` — индекс) или формы (0): безымянная называется «страница N», у страницы без подписи подпись пуста."""
    holder = form.holders.get(owner)
    names = page_names_of(form, owner)
    captions = _page_captions(holder.node) if holder is not None and holder.node is not None else []
    return {at: (name, captions[at] if at < len(captions) else "") for at, name in names.items()}


def nodes_of(form):
    """`{T-узел структуры: (индекс панели или формы, номер страницы)}` закладок, которые досье называет `T1`, `T2`, …: у панели с двумя и более страницами. Узел без панели в форме — пропущен."""
    structure = structure_mod.recognize(form.doc)
    from .brief import facts
    names = facts._Names(form, structure)
    owner_of = {None: 0}
    for key, holder in form.holders.items():
        if holder.item is not None:
            owner_of[names.of(holder.item)] = key
    return {node.id: (owner_of[node.holder], node.page) for node in structure.walk() if node.role == structure_mod.PAGE and node.id and node.holder in owner_of}


def _listing(pages):
    return ", ".join(f"«{caption or name}» ({at})" if (caption or name) != f"страница {at}" else f"«страница {at}»" for at, (name, caption) in sorted(pages.items()))


def resolve(form, owner, ref, nodes=None, what="панели"):
    """Номер страницы панели (формы) `owner` по ссылке `ref`. `nodes` — `nodes_of(form)` (считается один раз на разбор команды). Отказ — `ValueError` словами."""
    pages = pages_of(form, owner)
    text = str(ref).strip()
    if text.lstrip("-").isdigit():
        at = int(text)
        holder = form.holders.get(owner)
        used = {c.page for c in holder.children if isinstance(c.page, int)} | {0} if holder is not None else {0}      # страницы без записи в блоке закладок, но с элементами
        if at in pages or at in used:
            return at
        raise ValueError(f"у {what} нет страницы {at} (есть: {_listing(pages) or 'одна без закладки'})")
    if NODE.match(text):
        node = (nodes if nodes is not None else nodes_of(form)).get("T" + text[1:])
        if node is None:
            raise ValueError(f"в структуре досье нет закладки {text.upper()}")
        if node[0] != owner:
            raise ValueError(f"закладка {text.upper()} принадлежит другой панели (индекс {node[0]}), а не {what}")
        return node[1]
    folded = text.casefold()
    for key in (0, 1):          # имя страницы в файле — то, что называет код, — сильнее подписи закладки: по имени ищется первым
        found = [at for at, label in pages.items() if (label[key] or "").casefold() == folded]
        if len(found) > 1:
            raise ValueError(f"название «{text}» подходит нескольким страницам {what} ({', '.join(map(str, sorted(found)))}): назовите номер с нуля или узел T")
        if found:
            return found[0]
    raise ValueError(f"у {what} нет страницы «{text}» (есть: {_listing(pages) or 'одна без закладки'})")


def resolve_node(form, ref):
    """`(индекс панели или формы, номер страницы)` по узлу `T<N>` без названия панели; иная ссылка — `None`."""
    text = str(ref).strip()
    if not NODE.match(text):
        return None
    node = nodes_of(form).get("T" + text[1:])
    if node is None:
        raise ValueError(f"в структуре досье нет закладки {text.upper()}")
    return node
