"""Свойства страниц самой формы: Видимость, Доступность и КартинкаЗаголовка.

Страница формы — та же запись `Element.PanelPage`, что и страница панели, но лежит в контейнере формы. `set_property` с
`form=true` и `page` ставит три свойства группы «Текущая страница» палитры формы; Имя и Заголовок страницы эта операция не
пишет. Все имена отдаёт фасад `frm_codec.edit`.
"""

from .. import design as _design
from .base import EditError, PAGES
from .names import PAGE_ITEMS, PAGE_NAME, _at, _maybe
from .platform import LIST_CHOICE_CHECKED
from .pages import FORM_PAGE_OLD, FORM_PAGE_VERSION, _form_pages_block, _page_by_name

# Якорь пометок проверки: у страницы формы он свой: значения проверены у страницы формы, а у страницы панели те же
# значения не проверялись. Граница корпуса у страницы формы — таблица страницы панели (`props.PAGE_ANCHOR`): запись одна.
FORM_PAGE_ANCHOR = "FormPage"
FORM_PAGE_PROPERTIES = ("visible", "enabled", "title_picture")

PAGE_TITLE_PICTURE = _at("Element.PanelPage", 2)
PICTURE_U6 = _maybe("Picture", 6)
PICTURE_REF = _at("Picture", 2)
# Позиции записи картинки заголовка страницы в строении «из файла»: метка записи 4, источник 3, тело — файл целиком.
FILE_REF = {"code": 4, "u1": 3, "u2": [0], "u3": "", "u4": -1, "u5": -1, "u6": 0, "u8": 0, "u9": ""}
FILE_OUTER = (("mark", 8), ("source", 0))
FORM_PAGE_COUPLED_U6 = 2

FORM_PAGE_WORDS = {
    "name": "имя страницы — её адрес: по нему её находят операции (add_form_page, remove_form_page, page=…) и код модуля; "
            "переименования страницы формы у редактора нет",
    "caption": "заголовок страницы формы не проверялся: set_property ставит у страницы формы Видимость, Доступность и "
               "КартинкаЗаголовка",
}


def form_page_root(doc, page, name, unverified):
    """`(страница, чьими словами, слова о поколении формы)` — страница формы по номеру с нуля (целое) или по имени (строка).

    Свойства проверены у формы поколения 16 (`FORM_PAGE_VERSION`); у других поколений отказ снимает `unverified`, а у поколения
    10 (8.0/8.1) страница устроена иначе, и его не снимает ничто. Имя, которое носит не одна страница, и пустое имя страницу
    не определяют — отказ называет номера.
    """
    if name not in FORM_PAGE_PROPERTIES:
        raise EditError(f"{name} у страницы формы: " + FORM_PAGE_WORDS.get(
            name, "у страницы формы set_property ставит Видимость (visible), Доступность (enabled) и КартинкаЗаголовка "
                  "(title_picture); прочее по имени не пишется"))
    version = _design.form_version(doc)
    if version == FORM_PAGE_OLD:
        raise EditError(
            f"{name} у страницы формы: форма поколения {FORM_PAGE_OLD} (8.0/8.1) — её страницы устроены иначе (имена пустые, "
            "направляющих у второй страницы нет), и свойства страницы у этого поколения не проверялись; unverified этого "
            "отказа не снимает. Конфигуратор 8.3 при сохранении поднимает форму до своей версии — правьте поднятую")
    block = _form_pages_block(doc)
    pages = (block.get(PAGES) or {}).get(PAGE_ITEMS) or []
    if not pages:
        raise EditError(f"{name} у страницы формы: у формы нет страниц — править нечего")
    if isinstance(page, bool) or not isinstance(page, (int, str)):
        raise EditError(f"page у формы — номер страницы с нуля (целое) или её имя (строка), а пришло {page!r}")
    if isinstance(page, int):
        if not 0 <= page < len(pages):
            known = ", ".join(f"{i}: {item.get(PAGE_NAME)!r}" for i, item in enumerate(pages))
            raise EditError(f"страницы формы с номером {page} нет (счёт с нуля); есть {known}")
        index = page
    else:
        index = _page_by_name(pages, page, "формы")
    item = pages[index]
    named = item.get(PAGE_NAME)
    whose = f"страницы {index}" + (f" ({named!r})" if named else "") + " формы"
    words = ""
    if version != FORM_PAGE_VERSION:
        if not unverified:
            raise EditError(
                f"{name} у {whose}: свойства страницы формы проверены у формы поколения {FORM_PAGE_VERSION}, а эта форма — "
                f"поколения {version}. Позвать всё же можно — unverified=True, — и тогда результат проверяете вы")
        words = (f"форма поколения {version}, а свойства страницы формы проверены у поколения {FORM_PAGE_VERSION}: "
                 "не проверялось")
    return item, whose, words


def file_shape(value):
    """Картинка заголовка в строении «из файла», как её записала платформа: метка записи 4, источник 3 без GUID,
    тело `#base64` целиком, остальные позиции записи — как у картинки без файла."""
    if not isinstance(value, dict):
        return False
    ref = value.get(PICTURE_REF)
    if not isinstance(ref, dict):
        return False
    body = ref.get("u7")
    if not (isinstance(body, list) and len(body) == 1 and isinstance(body[0], list) and len(body[0]) == 1
            and isinstance(body[0][0], dict) and set(body[0][0]) == {"base64"}):
        return False
    if any(ref.get(key) != want for key, want in FILE_REF.items()) or set(ref) != set(FILE_REF) | {"u7"}:
        return False
    return all(value.get(key) == want for key, want in FILE_OUTER)


# Проверено в конфигураторе: значения страницы формы и снятие РежимаВыбораИзСписка. Предприятие этих
# значений не запускало: в палитре формы они стоят, пересохранение сохранило.
ROUND162 = "в конфигураторе"
ROUND162_NOTE = "проверено в конфигураторе"
ROUND162_PAGE = {
    (FORM_PAGE_ANCHOR, "visible"): (
        lambda value: value is False, "☐",
        "Видимость страницы формы ☐ — группа «Текущая страница» палитры формы, пересохранение сохранило"),
    (FORM_PAGE_ANCHOR, "enabled"): (
        lambda value: value is False, "☐",
        "Доступность страницы формы ☐ — группа «Текущая страница» палитры формы, пересохранение сохранило"),
    (FORM_PAGE_ANCHOR, "title_picture"): (
        file_shape, "картинкой из файла (BMP/PNG вложена в форму, источник 3 без GUID)",
        "КартинкаЗаголовка страницы формы из файла — строение записи: метка 4, источник 3, тело файла целиком; палитра "
        "показала картинку, пересохранение сохранило"),
}
ROUND162_LIST_CHOICE = {
    ("TextBox", "content/list_choice_mode"): (
        lambda value: value is False, "☐ у поля со своим реквизитом формы и пустым типом",
        "снятие РежимаВыбораИзСписка у поля ввода, привязанного к своему реквизиту ФОРМЫ путём из одного шага, с пустым "
        "типом: режим и КнопкаСпискаВыбора ☐, блок редактирования убран, тип остаётся «Произвольный» (пересохранение "
        "сохранило)",
        {LIST_CHOICE_CHECKED}),
}
ROUND162_PROPERTIES = {**ROUND162_PAGE, **ROUND162_LIST_CHOICE}


def u6_cowrite(item, new_picture=None):
    """Безымянная позиция 6 картинки заголовка: при установке картинки платформа ставит 2 (у новой страницы было 0); Видимость и
    Доступность её не меняют. Другое значение (1 — у страниц форм с ЦветомРамки) операция не трогает. Возвращает `(запись или
    None, слова)`: запись — `(держатель, ключ, значение, причина, метка)` для общего цикла записи."""
    picture = new_picture if new_picture is not None else item.get(PAGE_TITLE_PICTURE)
    if not isinstance(picture, dict) or picture.get(PICTURE_U6) != 0:
        return None, ""
    why = "при установке картинки заголовка платформа ставит этой позиции 2 (было 0); Видимость и Доступность её не меняют"
    return (picture, PICTURE_U6, FORM_PAGE_COUPLED_U6, why, f"{PAGE_TITLE_PICTURE}/{PICTURE_U6}"), why
