"""Перераскладка и перечень операций (`FORM_OPS`, `apply`). Все имена отдаёт фасад `frm_codec.edit`."""

import inspect

from .. import typed

from .names import FONT_KINDS
from .base import (
    EditError,
    set_button_text,
    set_caption,
    set_description,
    set_form_title,
    set_tool_tip,
)
from .buttons import (
    add_button,
    move_button,
    remove_button,
    set_button_action,
    set_button_picture,
    set_button_shortcut,
)
from .elements import add_element, move_element, remove_element, rename_element, set_action_source, set_anchors, set_view
from .changetype import change_type
from .reparent_ops import reparent
from .columns import add_column, remove_column, set_column_control, set_column_type
from .valuesrc import add_columns
from .font import set_font
from .pages import add_form_page, add_page, move_form_page, move_page, remove_form_page
from .module import append_procedure, module_words
from .period import add_period_choice
from .collapse import add_collapsible_panel
from .pair import add_pair
from .data import add_attribute, bind, remove_attribute, set_event
from .layer import copy_layer
from .formprops import set_form_event, set_saved_values
from .setprop import set_property
from .taborder import set_tab_order
from .typelink import set_type_link
from .fieldtype import set_field_type
from .drafts import remove_page, set_menu_mode


# ── Перераскладка под новый размер ──

def relayout(doc, width=None, height=None, unverified=False):
    """Форма под новый размер клиентской области — с координатами, какими их покажет предприятие.

    Расчёт — в `frm_codec.layout`; здесь только вход операции. Модуль раскладки сам вызывает этот,
    поэтому импорт наверху замкнул бы их в цикл.
    """
    from .. import layout
    return layout.relayout(doc, width=width, height=height, unverified=unverified)


def normalize_anchors(doc, elements=None, unverified=False):
    """Привязки начисто по текущему поведению, места не меняются. Расчёт — в `frm_codec.anchors_fix`
    (там же слова); импорт отложен по той же причине, что у `relayout`.
    """
    from .. import anchors_fix
    return anchors_fix.normalize_anchors(doc, elements=elements, unverified=unverified)


def repair_anchors(doc, elements=None, dry_run=False, unverified=False):
    """Исправление привязок, из-за которых форма не растягивается как положено; `box` не меняется. Расчёт — в `frm_codec.repair`
    (там же слова); импорт отложен по той же причине, что у `relayout`.
    """
    from .. import repair
    return repair.repair_anchors(doc, elements=elements, dry_run=dry_run, unverified=unverified)


def normalize_guides(doc, margin=None, unverified=False):
    """Дальние направляющие края формы — к краю (отступ 8, при Рамке 6); элементы и привязки не меняются. Расчёт и слова — в `frm_codec.guides`."""
    from .. import guides
    return guides.normalize_guides(doc, margin=margin, unverified=unverified)


def normalize_page_edges(doc, panel=None):
    """Края страниц панелей без рамки — к видимой части панели; раскладка в предприятии не меняется. Расчёт и слова — в `frm_codec.layout.page_edges`."""
    from ..layout import page_edges
    return page_edges.normalize_page_edges(doc, panel=panel)


# ── Перечень операций ──

# Имя операции в `ops.json` — имя функции. Второго списка имён нет: отдельный перечень разошёлся бы
# с функциями при добавлении операции.
FORM_OPS = {fn.__name__: fn for fn in (
    set_form_title, set_caption, set_button_text, set_tool_tip, set_description,
    set_button_picture, set_button_shortcut,
    add_button, move_button, remove_button, set_button_action, set_menu_mode,
    add_element, add_pair, remove_element, rename_element, move_element, change_type, reparent, set_action_source, set_anchors, set_font,
    add_column, add_columns, remove_column, set_column_control, set_column_type, add_page, move_page, remove_page,
    add_attribute, remove_attribute, bind, set_event, set_property, set_type_link, set_view, copy_layer,
    add_form_page, move_form_page, remove_form_page, set_form_event, set_saved_values, set_field_type, set_tab_order)}
MODULE_OPS = {append_procedure.__name__: append_procedure}
# Операции, которые правят и форму, и модуль: функция получает документ и байты модуля, возвращает `(слова, новый модуль)`.
COMBINED_OPS = {add_period_choice.__name__: add_period_choice, add_collapsible_panel.__name__: add_collapsible_panel}
# Перераскладка: вход выше, расчёт в `frm_codec.layout`.
FORM_OPS[relayout.__name__] = relayout
FORM_OPS[normalize_anchors.__name__] = normalize_anchors
FORM_OPS[repair_anchors.__name__] = repair_anchors
FORM_OPS[normalize_guides.__name__] = normalize_guides
FORM_OPS[normalize_page_edges.__name__] = normalize_page_edges


def _bool_defaults():
    """Параметры операций, у которых умолчание булево. Перечень считается, а не пишется руками:
    операция с новым флагом попадает в него сама, и проверка вида значения её накрывает.
    """
    out = set()
    for fn in list(FORM_OPS.values()) + list(MODULE_OPS.values()) + list(COMBINED_OPS.values()):
        for name, param in inspect.signature(fn).parameters.items():
            if isinstance(param.default, bool):
                out.add(name)
    return out


# Галочки — параметры, значение которых только `true` или `false`. Источники: биты записи шрифта с видом `bool` (их объявляет
# карта), флаг без значения (`scale_set`) и параметры с булевым умолчанием (`unverified`, `reset`, `drop_items`). `bold` назван
# вручную: в диалоге это галочка «Полужирный», а в файле насыщенность числом (700 или 400), и вывести «булев» из карты нельзя.
BOOL_PARAMS = ({name for name, kind in FONT_KINDS.items() if kind == "bool"}
               | _bool_defaults() | {"bold"})


def apply(doc, ops, bsl=None, siblings=None, config=None, final_captions=False):
    """Перечень операций подряд: `(документ, модуль, журнал строк)`.

    Операции идут в порядке записи, и каждая видит результат предыдущей. Отказ любой операции останавливает перечень
    и называет её номер.

    `siblings` — свод соседних форм той же конфигурации (`design.pool`; `frm_json.py edit --siblings`). Его получают
    операции с таким параметром (`add_element`, `set_view` — вид конфигурации).

    `config` — выгрузка конфигурации (`metadata.Config` или каталог). Её получают операции с таким параметром
    (`bind` с путём по метаданным). Если у операции нет своего `config`, она берёт выгрузку отсюда; если выгрузки нет,
    операция отказывает словами (`--config`).

    `final_captions=True` — `set_caption` не измеряет подпись сразу: ширину и зазор «текст → поле» проверяет вызывающий один раз по итоговой форме
    (`edit.final.caption_lines`), потому что следующие операции (`move_element`, `set_property`) могут их поменять.
    """
    from .base import DEFER_FIT
    was_deferred = DEFER_FIT[0]
    DEFER_FIT[0] = bool(final_captions)
    try:
        return _apply(doc, ops, bsl, siblings, config)
    finally:
        DEFER_FIT[0] = was_deferred


def _apply(doc, ops, bsl, siblings, config):
    """Тело `apply`: перечень операций подряд."""
    # Документ со старыми именами краёв (`width`/`height`) — отказ `TypedError` (подкласс ValueError) словами: раскладка
    # ищет края по `right`/`bottom` и приняла бы такой блок за «сырой».
    typed.refuse_old_coords(doc)
    # Перечень операций: прежнее имя поля — ключом параметра, именем `set_property` или концом адреса — тот же отказ.
    found = typed.old_field_places(ops, strings=True)
    if found:
        raise EditError(f"операции {found[0][1]}")
    if config is not None:
        from . import datapath
        config = datapath.load_config(config)  # каталог читается один раз на весь перечень
    from .. import guides
    watch = guides.Watch(doc)       # панели у краёв и элементы ниже нижней направляющей: что стояло до перечня, перечень не виноват
    log = []
    for number, op in enumerate(ops, 1):
        if not isinstance(op, dict) or "op" not in op:
            raise EditError(f"операция {number}: это объект с полем \"op\" и параметрами, "
                            f"а пришло {op!r}")
        name = op["op"]
        kwargs = {key: value for key, value in op.items() if key != "op"}
        # Приставку с номером операции добавляет только это место. Ветка модуля обёрнута тем же `try`, чтобы
        # номер был и в её отказах.
        try:
            if name in MODULE_OPS:
                if bsl is None:
                    raise EditError("операция правит модуль формы, а модуль не назван: "
                                    "дайте --bsl и --bsl-out")
                before = bsl
                bsl = _call(MODULE_OPS[name], bsl, kwargs)
                said = f"{name}: модуль {len(bsl)} байт" + (
                    module_words(before, kwargs) if name == append_procedure.__name__ else "")
            elif name in COMBINED_OPS:
                if bsl is None:
                    raise EditError("операция правит и модуль формы, а модуль не назван: дайте --bsl и --bsl-out")
                said, bsl = _call_combined(COMBINED_OPS[name], doc, bsl, kwargs)
            elif name in FORM_OPS:
                if siblings is not None and "siblings" not in kwargs \
                        and "siblings" in inspect.signature(FORM_OPS[name]).parameters:
                    kwargs["siblings"] = siblings
                # `bind attribute=` — реквизит формы: выгрузка ему не нужна, а общий `config` вызвал бы отказ «config нужен только пути по
                # метаданным». С `copy_type` выгрузка называет класс ссылки для слов о блоке редактирования.
                if config is not None and "config" not in kwargs \
                        and not (name == "bind" and kwargs.get("attribute") is not None and not kwargs.get("copy_type")) \
                        and "config" in inspect.signature(FORM_OPS[name]).parameters:
                    kwargs["config"] = config
                said = _call(FORM_OPS[name], doc, kwargs)
            else:
                known = ", ".join(sorted(FORM_OPS) + sorted(MODULE_OPS) + sorted(COMBINED_OPS))
                raise EditError(f"{name!r} такой нет; есть {known}")
        except EditError as e:
            raise EditError(f"операция {number} ({name}): {e}") from None
        log.append(f"{number}. {said}")
        watch.step(doc, number)
    watch.finish(doc, log)
    return doc, bsl, log


def _call_combined(fn, doc, bsl, kwargs):
    """Операция над формой и модулем: проверка параметров та же, что у `_call` (первый аргумент — документ, второй — модуль)."""
    try:
        inspect.signature(fn).bind(doc, bsl, **kwargs)
    except TypeError as e:
        known = ", ".join(list(inspect.signature(fn).parameters)[2:])
        raise EditError(f"{e}; параметры этой операции — {known}") from None
    return fn(doc, bsl, **kwargs)


def _call(fn, first, kwargs):
    """Вызов операции с проверкой параметров до вызова: сначала имена, потом виды значений.

    Разбор параметров отделён от исполнения: иначе опечатка в имени ключа и дефект внутри операции пришли бы одним
    отказом (`TypeError`), и дефект читался бы как ошибка пользователя.

    Вид значения проверяется здесь у галочек — одно место на все операции. В JSON любая непустая строка истинна,
    поэтому без проверки `"bold": "нет"` дал бы полужирный, `"scale_set": "нет"` поднял бы бит 512, а `"reset": "нет"` сбросил
    бы шрифт. Проверка идёт по связанным аргументам, а не по `kwargs`, чтобы так же ловился позиционный вызов.
    """
    try:
        bound = inspect.signature(fn).bind(first, **kwargs)
    except TypeError as e:
        known = ", ".join(list(inspect.signature(fn).parameters)[1:])
        raise EditError(f"{e}; параметры этой операции — {known}") from None
    for name, value in bound.arguments.items():
        if name in BOOL_PARAMS and value is not None and not isinstance(value, bool):
            raise EditError(
                f"{name}: это ГАЛОЧКА — true или false, а пришло {value!r}. В JSON истинна "
                "ЛЮБАЯ непустая строка, поэтому «нет» и «false» здесь включили бы ровно то, "
                f"что вы выключали. Галочки этой операции: "
                f"{', '.join(n for n in inspect.signature(fn).parameters if n in BOOL_PARAMS)}")
    return fn(first, **kwargs)
