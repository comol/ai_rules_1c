"""Стандартные действия формы документа, которых нет среди пятнадцати имён карты: «Провести» (24) и «Отмена проведения» (29).

Корпус (22 785 записей стандартных действий кнопок панелей формы, снимок и дополнительный корпус): у обоих действий запись одного строения — позиция 2 несёт
GUID `55c7732c-0c33-4394-adca-9d15082552b6`, ссылка на источник — «основной набор» (`b78f2e80-…`) с кодом набора, в котором лежит кнопка, число позиции 1 —
`4294967295`. У действий «Записать» (140), «Записать и закрыть» (141) и «Закрыть» эта позиция нулевая, поэтому кнопку одного вида нельзя переделать в кнопку
другого сменой кода: запись получила бы чужой GUID. Так пишет конфигуратор действия документа в меню «Действия» верхней панели формы (по 452 записи каждого, формы документов
и списков документов). Постановка без донора идёт без `unverified`. В нижней панели формы корпуса этих действий нет ни в одной форме (перепись: 593 верхние панели форм и 3 контекстные панели форм списков), в нижнюю панель операция их ставит только по прямой просьбе и говорит об этом сведением (`bottom_bar_note`).

Модуль даёт запись действия по строению корпуса (`spec_for`), донора (`donor_matches`) и отказы словами (`refuse_wrong_kind`).
"""
import copy

DOC_ACTIONS = {24: "Провести", 29: "Отмена проведения"}
DOC_U2 = "55c7732c-0c33-4394-adca-9d15082552b6"
ZERO_GUID = "00000000-0000-0000-0000-000000000000"
SOURCE_U1 = 4294967295      # число позиции 1 у записей этих действий в корпусе
DOCUMENT_KIND = "document.item"


def is_document_action(code):
    return isinstance(code, int) and not isinstance(code, bool) and code in DOC_ACTIONS


def form_kind(doc):
    """Вид формы по основному реквизиту (`census.KNOWN`) либо `None`."""
    from .. import census
    try:
        return census.KNOWN.get(census.main_attribute(doc))
    except Exception:  # noqa: BLE001 — документ не формы объекта: вида нет
        return None


def refuse_wrong_kind(doc, code):
    """«Провести» — действие формы ДОКУМЕНТА: у формы с другим основным реквизитом отказ словами."""
    kind = form_kind(doc)
    if kind != DOCUMENT_KIND:
        from .base import EditError
        have = f"вид формы — «{kind}»" if kind else "вида формы нет (основной реквизит не называет вид объекта)"
        raise EditError(f"«{DOC_ACTIONS[code]}» ({code}) — стандартное действие формы документа (в корпусе: {DOCUMENT_KIND}, списки документов, журналы), а здесь {have}: "
                        "на форме обработки, справочника или отчёта проводить нечего; свою команду с обработчиком ставит add_button с procedure")


def is_bottom_form_bar(doc, node):
    """Панель формы у нижнего края — так её узнаёт `autobar` (собственные действия формы, верх не выше 12, низ у нижнего края формы)."""
    from .. import layout
    from .names import ACTION_SOURCE, COORDS, HEIGHT, NAME_BLOCK, Y
    if not isinstance(node, dict) or (node.get(NAME_BLOCK) or {}).get(ACTION_SOURCE) != 0:
        return False
    c = node.get(COORDS) or {}
    return c.get(Y, 0) >= 12 and c.get(HEIGHT, 0) >= layout.read(doc).height - 2


def bottom_bar_note(doc, node, code):
    """Сведение (не отказ) при постановке «Провести» / «Отмены проведения» в нижнюю панель формы: в формах корпуса они стоят в верхней панели."""
    if is_bottom_form_bar(doc, node):
        return ("; в формах корпуса эти действия стоят в верхней панели (её автозаполнение ставит их у документа само); "
                "в нижней панели — по вашей просьбе")
    return ""


def spec_for(code, button_set):
    """Запись действия `{6, …}` для кода из `DOC_ACTIONS`: источник — набор, в котором лежит кнопка (как в корпусе)."""
    from .names import REF_ID, REF_CODE, SET_REF, SET_CODE
    ref = button_set.get(SET_REF) if isinstance(button_set, dict) else None
    guid = ref.get("guid") if isinstance(ref, dict) else None
    if not isinstance(guid, str):
        from .base import EditError
        raise EditError("у набора кнопок нет владельца (GUID источника действий): ссылку для «Провести» не из чего построить; "
                        "возьмите донора — кнопку этой панели с таким же действием")
    return {"mark": 6, "u1": SOURCE_U1, "u2": {"guid": DOC_U2}, "standard_action": None,
            "ref": {"mark": 1, "u1": 99, REF_ID: {"guid": guid}, REF_CODE: button_set.get(SET_CODE), "u4": 1}, "u5": 0, "u6": 1}


def donor_matches(source_spec):
    """Запись донора годится для «Провести» / «Отмены проведения»: у неё тот же GUID позиции 2."""
    u2 = source_spec.get("u2") if isinstance(source_spec, dict) else None
    return isinstance(u2, dict) and u2.get("guid") == DOC_U2


def clone(spec):
    return copy.deepcopy(spec)
