"""Сворачиваемая панель настроек: панель без закладок на краю формы, сосед, занимающий её место, кнопка с пометкой на верхней панели формы и
процедура, которая ставит свёртку панели. Так устроены формы отчётов складской конфигурации (перепись выгрузок конфигураций).

Часть редактора. Свёртки нет в палитре свойств панели и разделителя (проверено в конфигураторе): это свойство времени работы, его ставит код —
`ЭлементыФормы.<Панель>.Свертка = РежимСверткиЭлементаУправления.Лево` (`Нет` разворачивает). Поэтому «сворачиваемая» панель — это четыре вещи,
которые операция ставит вместе:

* панель без закладок (одна страница, без рамки), прижатая к краю формы — левому (`Лево`), правому (`Право`), верхнему (`Верх`) или нижнему (`Низ`) — и сохраняющая размер при растяжении окна;
* сосед (соседи) с границей, обращённой к панели, привязанной к её краю (за дальним краем панели — `after`, перед ближним — `before`), и противоположной — к краю формы: при свёртке он занимает освободившееся место;
* свёрнутая панель исчезает целиком, между открытиями свёртка не запоминается;
* кнопка на верхней командной панели формы с действием-процедурой и пометкой (в файле она стоит: панель развёрнута);
* процедура этой кнопки в модуле: по пометке панель сворачивается, пометка снимается; иначе панель разворачивается, пометка ставится.

Операция правит и форму, и модуль, поэтому стоит в отдельном перечне `COMBINED_OPS` (`edit.ops`): функция получает документ и байты модуля и
возвращает `(слова, новый модуль)`.
"""
import copy
import re

from .. import design as _design
from .base import EditError, container, find_element, name_of, _fit_guides, layout_block, element_names, _bars
from .buttons import add_button, set_button_picture, _action_kind, PROCEDURE_KIND
from .elements import add_element, set_anchors
from .module import append_procedure
from .pages import _dpi_ok
from .setprop import set_property
from .base import set_tool_tip

# Стороны: сторона → (слово режима `РежимСверткиЭлементаУправления`, ось привязки, роль панели у края, цепочка соседа). У `left`/`top` сосед стоит за дальним краем панели
# и идёт за ним (`after`); у `right`/`bottom` — перед её ближним краем, его дальняя граница идёт к ближней стороне панели (`before`).
SIDES = {"left": ("Лево", "h", "left", "after"), "top": ("Верх", "v", "top", "after"),
         "right": ("Право", "h", "right", "before"), "bottom": ("Низ", "v", "bottom", "before")}
# Версии общего блока формы в переписи: 16 у шестидесяти шести форм слева и 15 у четырёх форм сверху.
VERSIONS = (15, 16)
PANEL_NAME = "Настройки"
BUTTON_NAME = "КнопкаСвертки"
BUTTON_TEXT = "Настройки"
BAR_NAME = "ДействияФормы"
# Картинка библиотеки платформы у кнопки во всех семидесяти формах переписи (отображение «Картинка и текст»).
LIBRARY_PICTURE = "fe740df0-d828-4241-a12f-7414e12302e8"
# Зазор между панелью и соседом, при котором соседа считают стоящим рядом: у переписи 0, у соседа сверху 6–7.
NEAR = 8


def procedure_body(panel, bar, button, mode):
    """Тело процедуры кнопки: по пометке панель сворачивается и пометка снимается, иначе панель разворачивается и пометка ставится. Строки — как в
    модулях переписи (семьдесят троек; текст у всех один с точностью до имён и режима `Лево`/`Верх`)."""
    mark = f"ЭлементыФормы.{bar}.Кнопки.{button}.Пометка"
    fold = f"ЭлементыФормы.{panel}.Свертка"
    return (
        f"Если {mark} Тогда",
        f"\t{fold}=РежимСверткиЭлементаУправления.{mode};",
        f"\t{mark}=Ложь;",
        "Иначе",
        f"\t{fold}=РежимСверткиЭлементаУправления.Нет;",
        f"\t{mark}=Истина;",
        "КонецЕсли;")


def _form_bar(doc, bar):
    """Имя верхней командной панели формы: названная `bar`; без неё — `ДействияФормы`, а если её нет, единственная командная панель формы."""
    holder = container(doc)
    items = [it for it in ((holder.get("elements") or {}).get("items") or []) if isinstance(it, dict) and it.get("type") == "CommandBar"]
    names = [name_of(it) for it in items]
    if bar is not None:
        place = find_element(doc, bar)
        if place.element.get("type") != "CommandBar" or place.holder is not holder:
            raise EditError(f"bar {bar!r}: это не командная панель формы (верхнего уровня); командные панели формы: {', '.join(names) or '—'}")
        return bar
    if BAR_NAME in names:
        return BAR_NAME
    if len(names) == 1:
        return names[0]
    if not names:
        raise EditError("на форме нет командной панели, а кнопке свёртки класть некуда: поставьте её (`add_element` с шаблоном CommandBar, левый верхний "
                        "угол формы) либо назовите панель в bar")
    raise EditError(f"командных панелей формы несколько ({', '.join(names)}) и среди них нет «{BAR_NAME}»: назовите нужную в bar")


def _shape(node, side):
    """Чем панель отличается от панелей переписи: `[слова]`. Перепись: Panel, закладки «Не отображать», одна страница, без рамки."""
    out = []
    block = layout_block(node, need=False)
    if not isinstance(block, dict):
        return ["блок раскладки панели не разобран"]
    tabs = block.get("show_tabs")
    if tabs != "DontUse":
        out.append(f"закладки {tabs!r} (в переписи у всех семидесяти — «Не отображать»)")
    pages = (block.get("pages") or {}).get("count")
    if pages != 1:
        out.append(f"страниц {pages} (в переписи у всех одна)")
    try:
        border = node["content"]["u1"]["u0"]["border"].get("border_type")
    except (KeyError, TypeError, AttributeError):
        border = None
    if border not in ("WithoutBorder", "NoBorder", "None", None):
        out.append(f"рамка {border!r} (в переписи у всех без рамки)")
    return out


def _neighbors(place, side, named):
    """Соседи панели — элементы её родителя и страницы, стоящие за её дальним краем: `(перечень, комментарии)`. Названные в `named` берутся все (они
    обязаны стоять за краем), без них — стоящие рядом (зазор не больше `NEAR`) и перекрывающие панель по другой оси."""
    panel = place.element
    pc = panel["coords"]
    page = pc.get("page")
    horizontal = side in ("left", "right")
    along = ("x", "right", "y", "bottom") if horizontal else ("y", "bottom", "x", "right")
    before = SIDES[side][3] == "before"
    far_edge = pc[along[0] if before else along[1]]
    found, notes = [], []
    for item in place.items:
        if item is panel or not isinstance(item, dict):
            continue
        c = item.get("coords") or {}
        if c.get("page") != page or item.get("type") == "CommandBar":
            continue
        name = name_of(item)
        gap = (far_edge - c.get(along[1], 0)) if before else (c.get(along[0], 0) - far_edge)
        overlap = c.get(along[2], 0) < pc[along[3]] and c.get(along[3], 0) > pc[along[2]]
        if named is not None:
            if name not in named:
                continue
            if gap < 0 or not overlap:
                where = {"left": "справа", "top": "снизу", "right": "слева", "bottom": "сверху"}[side]
                raise EditError(f"сосед {name!r} стоит не {where} от панели {name_of(panel)!r} вплотную к её краю: край панели {far_edge}, "
                                f"край соседа {c.get(along[1] if before else along[0])}")
            found.append((item, gap))
        elif 0 <= gap <= NEAR and overlap and item.get("visible", True) is not False:
            found.append((item, gap))
    if named is not None:
        missing = [n for n in named if n not in {name_of(i) for i, _g in found}]
        if missing:
            raise EditError(f"соседи {', '.join(map(repr, missing))} на одной странице с панелью {name_of(panel)!r} в её родителе не найдены")
    return found, notes


def add_collapsible_panel(doc, bsl, panel, box=None, side="left", neighbors=None, bar=None, button=BUTTON_NAME, text=BUTTON_TEXT,
                          handler=None, picture=None, tool_tip=None, unverified=False):
    """Сворачиваемая панель настроек: панель без закладок на краю формы, сосед на её месте при свёртке, кнопка с пометкой на верхней
    панели формы и процедура кнопки в модуле. Возвращает `(слова отчёта, новый модуль)`.

    **Панель.** `panel` — имя панели. Если панели нет, `box` (`[лево, верх, ширина, высота]`) заводит новую: панель без закладок, одна страница, без
    рамки, привязки как в переписи — у `side="left"` к левому краю с неизменной шириной и по высоте с окном (лево F.l+лево, право F.l+лево+ширина,
    верх, низ), у `side="top"` к верхнему краю с неизменной высотой и по ширине с окном, у `right` и `bottom` зеркально (`h="right"`, `v="bottom"`); направляющие края страницы — по размеру панели. Если
    панель есть, `box` не называют: операция проверяет, что это панель формы (не вложенная), без закладок, с одной страницей и без рамки, и
    привязывает её ось (`h="left"`, `h="right"`, `v="top"` или `v="bottom"`), не трогая другую.

    **Сторона.** `side`: `left` (`Лево`, 66 из 70 троек переписи), `top` (`Верх`, 4), `right` (`Право`) или `bottom` (`Низ`); у двух последних сосед стоит
    перед панелью, и его дальняя граница привязывается к ближней стороне панели (`{"before": <панель>, "role": "stretch"}`; запись корпуса). Свёртка в стороны
    во все четыре стороны проверена в предприятии.

    **Соседи.** `neighbors` — имена элементов, стоящих вплотную к панели со стороны её содержимого (того же родителя и страницы); без них берутся стоящие рядом (зазор не больше
    8 px, перекрытие по другой оси; командные панели не берутся). Каждому граница, обращённая к панели, привязывается к её краю (смещение — прежний
    зазор), противоположная — к краю формы (`{"after": <панель>, "role": "stretch"}`, у `right`/`bottom` — `before`): при `Свертка = Лево` сосед занимает освободившееся место. Соседей может
    не быть (новая панель на пустой форме): тогда отчёт называет привязку, которую надо поставить после появления соседа.

    **Кнопка.** `bar` — командная панель формы (умолчание `ДействияФормы`, иначе единственная); `button` — имя кнопки (`КнопкаСвертки`), `text` — её
    текст (`Настройки`); действие — процедура `handler` (умолчание — имя панели формы плюс имя кнопки, как называет её платформа). Пометка кнопки
    в файле стоит (панель развёрнута). `picture` — GUID картинки библиотеки платформы: по умолчанию та, что стоит у всех кнопок переписи
    (отображение «Картинка и текст»), `False` — без картинки. `tool_tip` — подсказка (в переписи она есть у двадцати из семидесяти кнопок).
    Кнопка встаёт в конец последнего набора панели (в образцах она стоит третьей слева, после первой кнопки и разделителя; место операция не повторяет).

    **Процедура.** Дописывается в конец модуля (`append_procedure`: те же проверки имени и повтора), текст — как в семидесяти модулях переписи.
    Если модуль уже присваивает `Свертка` этой панели, отчёт предупреждает.

    **Условия и отказы** (форма и модуль остаются прежними): модуль не назван; форма не версии 15 или 16 либо с DPI не 96, панель с закладками,
    несколькими страницами или рамкой (перепись такого не видела; `unverified` снимает); панель вложена в другую; имя кнопки или процедуры занято.
    В предприятии свёрнутая панель исчезает целиком (ни полосы, ни рамки), сосед занимает её место, между открытиями свёртка не запоминается.
    """
    if bsl is None:
        raise EditError("операция дописывает процедуру в модуль формы, а модуль не назван: дайте --bsl и --bsl-out")
    if not isinstance(panel, str) or not panel:
        raise EditError("panel — имя панели, непустая строка")
    if side not in SIDES:
        raise EditError(f"side — одно из {', '.join(SIDES)}, а пришло {side!r}")
    mode, axis, own_role, chain_kind = SIDES[side]
    if box is not None and not (isinstance(box, (list, tuple)) and len(box) == 4 and all(isinstance(v, int) and not isinstance(v, bool) for v in box)):
        raise EditError("box — [лево, верх, ширина, высота]: четыре целых")
    if box is not None and (box[2] <= 0 or box[3] <= 0):
        raise EditError(f"box {list(box)}: ширина и высота положительные")
    if neighbors is not None and not (isinstance(neighbors, (list, tuple)) and all(isinstance(n, str) and n for n in neighbors)):
        raise EditError("neighbors — список имён элементов")
    if picture is not None and picture is not False and not (isinstance(picture, str) and re.fullmatch(r"[0-9a-fA-F-]{36}", picture)):
        raise EditError("picture — GUID картинки библиотеки (36 знаков), False (без картинки) либо ничего (картинка переписи)")
    version = _design.form_version(doc)
    deviations = []
    if version not in VERSIONS:
        deviations.append(f"общий блок формы версии {version} (в переписи 16 и 15)")
    if not _dpi_ok(doc):
        deviations.append("DPI формы не 96 (проверки при DPI не 96 редактор не ведёт)")
    existing = panel in element_names(doc)
    new_panel = box is not None
    if new_panel and existing:
        raise EditError(f"панель {panel!r} в форме уже есть: box называют только для новой панели; чтобы сделать существующую сворачиваемой, уберите box")
    if not new_panel and not existing:
        raise EditError(f"панели {panel!r} в форме нет: назовите существующую либо дайте box ([лево, верх, ширина, высота]) для новой")
    place = None
    if existing:
        place = find_element(doc, panel)
        if place.element.get("type") != "Panel":
            raise EditError(f"{panel!r} — {place.element.get('type')}, а не панель (Panel)")
        if place.holder is not container(doc):
            deviations.append("панель лежит внутри другой панели (в переписи все на форме)")
        deviations += _shape(place.element, side)
    if deviations and not unverified:
        raise EditError(f"панель {panel!r}: " + "; ".join(deviations) + ". Перепись (70 троек: форма, панель, процедура) таких не видела, свёртка такой "
                        "формы не проверялась; unverified=True выполняет всё равно")
    bar = _form_bar(doc, bar)
    block = next((b for n, b in _bars(doc) if n == bar), None)
    if block is None or not block.get("button_sets"):
        raise EditError(f"в панели {bar!r} нет ни одного набора кнопок — кнопку класть некуда, а заводить набор редактор не умеет")
    if any(b.get("name") == button for s in block["button_sets"] for b in s.get("buttons") or []):
        raise EditError(f"кнопка {button!r} в панели {bar!r} уже есть")
    handler = handler or f"{bar}{button}"
    # Модуль проверяется первым: отказ по имени процедуры не должен оставить форму с наполовину поставленной панелью.
    new_bsl = append_procedure(bsl, handler, ("Кнопка",), procedure_body(panel, bar, button, mode), unverified=unverified)
    already = re.search(rf"ЭлементыФормы\s*\.\s*{re.escape(panel)}\s*\.\s*Свертка\s*=", bsl.decode("utf-8-sig", "replace"), re.I) is not None
    found = None
    if existing:
        found, _notes = _neighbors(place, side, neighbors)
        if not found and neighbors is None:
            raise EditError(f"рядом с панелью {panel!r} ({ {'left': 'справа', 'top': 'снизу', 'right': 'слева', 'bottom': 'сверху'}[side] } от неё, зазор не больше {NEAR} px) элементов нет: "
                            "при свёртке место занимать некому. Назовите соседей в neighbors либо поставьте их и повторите")
    snapshot = copy.deepcopy(doc)
    try:
        said = _build(doc, panel, box, side, mode, axis, own_role, chain_kind, found, neighbors, bar, button, text, handler, picture, tool_tip, new_panel)
    except Exception:
        doc.clear()
        doc.update(snapshot)
        raise
    tail = f"; в модуле уже есть присваивание Свертка этой панели — проверьте, что две процедуры не спорят" if already else ""
    if deviations:
        tail += "; отклонения от переписи (под unverified): " + "; ".join(deviations)
    return said + tail, new_bsl


def _build(doc, panel, box, side, mode, axis, own_role, chain_kind, found, neighbors, bar, button, text, handler, picture, tool_tip, new_panel):
    steps = []
    if new_panel:
        left, top, width, height = box
        steps.append(f"панель {panel!r} {left},{top} {width}×{height}")
        add_element(doc, "Panel", panel, [left, top, width, height])
        set_property(doc, element=panel, name="show_tabs", value="DontUse")
        node = find_element(doc, panel).element
        _fit_guides(node, width, height, doc=doc)
    steps_h = []
    other = "v" if axis == "h" else "h"
    set_anchors(doc, panel, **{axis: own_role, other: "stretch" if new_panel else None})
    edge = {"left": "левому", "right": "правому", "top": "верхнему", "bottom": "нижнему"}[side]
    steps_h = [f"панель: к {edge} краю с неизменным размером" + ((", по " + ("высоте" if axis == "h" else "ширине") + " с окном") if new_panel else "")]
    if new_panel:
        # соседи новой панели — те, что уже стоят за её дальним краем (панель встала на место, соседи ждали её)
        found, _notes = _neighbors(find_element(doc, panel), side, neighbors)
    named = []
    for item, gap in found or []:
        name = name_of(item)
        chain = {chain_kind: panel, "role": "stretch"}
        set_anchors(doc, name, **{axis: chain})
        named.append(f"{name!r}" + (f" (зазор {gap})" if gap else ""))
    add_button(doc, bar, button, text=text, procedure=handler)
    if picture is not False:
        set_button_picture(doc, bar, button, library=picture or LIBRARY_PICTURE)
        set_property(doc, element=bar, button=button, name="representation", value="PictureText")
    set_property(doc, element=bar, button=button, name="check", value=True)
    if tool_tip is not None:
        set_tool_tip(doc, bar, button, tool_tip)
    where = {"left": "слева", "top": "сверху", "right": "справа", "bottom": "снизу"}[side]
    return (f"Сворачиваемая панель: панель {panel!r} {where} ({'новая' if new_panel else 'существующая'}, без закладок); "
            + "; ".join(steps_h)
            + ("; соседи " + ", ".join(named) + ": граница, обращённая к панели, привязана к её краю, противоположная — к краю формы, поэтому при свёртке они занимают место "
               "(вторая ось соседей не менялась: чтобы они росли с окном по другой оси, как панель, поставьте её set_anchors)"
               if named else
               f"; соседей нет: после того как они появятся, привязать каждого set_anchors {axis}={{\"{chain_kind}\": \"{panel}\", \"role\": \"stretch\"}}")
            + f"; кнопка {button!r} в панели {bar!r} с пометкой (панель развёрнута) и процедурой {handler!r}"
            + ("" if picture is False else "; картинка библиотеки платформы, отображение «Картинка и текст»")
            + f"; процедура {handler!r} дописана в модуль (по пометке Свертка = {mode}, иначе Нет)")


def find_samples(doc):
    """Панели формы, устроенные как сворачиваемые по ПЕРЕПИСИ (по файлу, код модуля не читается): `[{panel, side, neighbors, buttons}]`.

    Панель формы (не вложенная) без закладок, одна страница, без рамки; соседи — элементы её родителя, чья ближняя граница привязана к дальнему краю
    панели (`left`: левая граница к правой стороне панели, `top`: верхняя к нижней); `buttons` — кнопки с пометкой и действием-процедурой на командных
    панелях формы, `[(панель, кнопка, текст)]`. Свёртку ставит код модуля: что кнопка делает именно это, файл не говорит.
    """
    holder = container(doc)
    items = [it for it in ((holder.get("elements") or {}).get("items") or []) if isinstance(it, dict)]
    buttons = []
    for bar, block in _bars(doc):
        if not any(it.get("type") == "CommandBar" and name_of(it) == bar for it in items):
            continue
        for bset in block.get("button_sets") or []:
            for b in bset.get("buttons") or []:
                action = next((a for a in block.get("actions") or [] if a.get("id") == b.get("id")), None)
                if b.get("check") is True and action is not None and _action_kind(block, action) == PROCEDURE_KIND:
                    shown = " ".join(t.get("text", "") for t in (b.get("text") or {}).get("items") or []) or b.get("name")
                    buttons.append((bar, b.get("name"), shown))
    out = []
    for it in items:
        if it.get("type") != "Panel" or _shape(it, None):
            continue
        index = it.get("index")
        for side, key, edge in (("left", "left_anchor", 3), ("top", "top_anchor", 1), ("right", "right_anchor", 2), ("bottom", "bottom_anchor", 0)):
            near = [name_of(o) for o in items if o is not it and ((o.get("coords") or {}).get(key) or {}).get("rule", {}).get("object") == index
                    and o["coords"][key]["rule"].get("side") == edge]
            if near:
                out.append({"panel": name_of(it), "side": side, "neighbors": near, "buttons": buttons})
    return out
