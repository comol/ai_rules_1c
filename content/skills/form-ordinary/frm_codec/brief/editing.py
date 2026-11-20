"""Раздел досье «Что и как можно менять»: возможности редактора на ЭТОЙ форме — без советов, что менять.

Раздел 9 `brief.md` и ключ `editing` в `brief.json`. Из чего он состоит:

1. **Ограничения формы** (`_constraints`): то, из-за чего операции редактора откажут или поведут себя иначе. Источник каждого пункта — функция,
   которой пользуется сама операция: `edit_elements.old_version_refusal` (шаблоны для старых версий), `edit_pages.form_page_bounds` (страницы формы:
   поколение, DPI, Рамка), `anchors_fix.high_dpi`, `guides.far_guides`, `design` (смесь оформления), `lstring` (подпись на нескольких языках).
   Поломки привязок и фиксированный размер читаются из раздела «Поведение» (`repair.diagnose`).
2. **Имена, на которые опирается код** (`_code_names`): элементы, кнопки, колонки и страницы, названные в модуле, и обработчики событий —
   что сломают `rename_element` и `remove_element`, `remove_button`, `remove_column`, `remove_page`.
3. **Операции по видам элементов этой формы**: таблица `OPS` (одна на всё досье: вид или форма → операции → что меняют → документ) и оговорки
   по данным формы (`_notes`). Тест сверяет `OPS` с перечнем операций редактора (`edit_ops.FORM_OPS`, `MODULE_OPS`, `COMBINED_OPS`): каждая операция
   отнесена к виду или к форме, лишних имён нет.
4. **Частые правки** (`_examples`): место и размер, растяжение, подпись, шрифт, порядок обхода, новое поле, колонка, страница, обработчик — по примеру записи
   `ops.json` на настоящих именах элементов. Пример перед выдачей исполняется редактором на копии формы; не выполнившийся не выдаётся.
5. **Как проверить правку** (`VERIFY`): команды навыка.

Форму раздел не меняет: операции выполняются на копии документа в памяти.
"""
import collections
import copy
import json
import re

from .. import anchors_fix, design, guides, layout, lstring, repair, templates
from . import modulescan as scan, content, module_effects as br_module, vocab
from ..edit import base as ed_base, data as ed_data, elements as ed_elements, fieldtype as ed_fieldtype, formpage as ed_formpage, formprops as ed_formprops, ops as ed_ops, pages as ed_pages, scope as ed_scope
from ..edit import collapse as ed_collapse
from ..edit.base import EditError

# ── Таблица операций ──

D_RULES = "docs/edit-rules.md"
D_ANCHORS = "docs/anchors.md"
D_FONT = "docs/edit-font-menu.md"
D_BUTTONS = "docs/edit-buttons.md"
D_COLUMNS = "docs/edit-columns.md"
D_SETPROP = "docs/edit-setprop.md"
D_FORMPROPS = "docs/edit-formprops.md"
D_MODULE = "docs/edit-module-data.md"
D_PAGES = "docs/form-pages.md"
D_DESIGN = "docs/design.md"
D_LAYOUT = "docs/layout.md"

FORM, MODULE, ANY = "form", "module", "*"      # область операции, кроме видов элементов: форма в целом, модуль, любой элемент
Op = collections.namedtuple("Op", "kinds changes doc")

BAR_BUTTON_OPS = ("add_button", "move_button", "remove_button", "set_button_action", "set_button_picture", "set_button_text", "set_description", "set_tool_tip")

# Одна таблица на всё досье. Ключ — имя операции в `ops.json`; `kinds` — к каким видам она относится (`FORM` — к форме, `MODULE` — к модулю,
# `ANY` — к любому элементу). У вида `bind` перечень берёт из кода операции (виды, у которых привязка подтверждена).
OPS = {
    # форма в целом
    "set_form_title": Op((FORM,), "заголовок окна формы", D_FORMPROPS),
    "set_form_event": Op((FORM,), "обработчик события самой формы (процедура модуля) либо его снятие", D_FORMPROPS),
    "set_tab_order": Op((FORM,), "порядок обхода (Tab) страницы формы или панели: одним перечнем имён либо по порядку чтения структуры", D_RULES),
    "set_saved_values": Op((FORM,), "список «Сохраняемые значения» формы отчёта и обработки", D_FORMPROPS),
    "add_attribute": Op((FORM,), "новый реквизит формы с описателем типа", D_MODULE),
    "remove_attribute": Op((FORM,), "снятие реквизита формы; отказ, пока на него ссылаются элемент, связь по типу или «Сохраняемые значения», и для основного реквизита", D_MODULE),
    "add_form_page": Op((FORM,), "новая страница самой формы (не панели)", D_PAGES),
    "move_form_page": Op((FORM,), "страница самой формы на другое место: before / after / index", D_PAGES),
    "remove_form_page": Op((FORM,), "удаление страницы самой формы", D_PAGES),
    "set_view": Op((FORM,), "вся форма в одном виде оформления: «как в 8.2» или «как в 8.3»", D_DESIGN),
    "relayout": Op((FORM,), "форма под новый размер клиентской области: координаты и привязки пересчитываются, как их покажет предприятие", D_LAYOUT),
    "normalize_anchors": Op((FORM,), "привязки начисто по текущему поведению, места не меняются", D_ANCHORS),
    "repair_anchors": Op((FORM,), "исправление привязок, из-за которых форма не растягивается как положено; место и размер элементов не меняются", D_ANCHORS),
    "normalize_guides": Op((FORM,), "дальние направляющие края формы переносятся к краю; элементы и привязки не меняются", D_FORMPROPS),
    "normalize_page_edges": Op((FORM,), "края страниц панелей переносятся к видимой части панели; раскладка в предприятии не меняется, box вложенных пересчитывается", D_LAYOUT),
    "add_period_choice": Op((FORM, MODULE), "набор «Выбор периода» (две надписи, два поля даты, кнопка) и его обработчик в модуле", D_MODULE),
    "add_collapsible_panel": Op((FORM, MODULE), "сворачиваемая панель настроек: панель без закладок на краю формы, соседи на её месте при свёртке, кнопка с пометкой на панели формы и её процедура в модуле", D_MODULE),
    # модуль
    "append_procedure": Op((MODULE,), "процедура в конец модуля формы (существующий текст модуля операции не правят)", D_MODULE),
    # любой элемент
    "add_element": Op((ANY,), "новый элемент по шаблону вида или по образцу соседа; место, размер и привязки берутся по соседям", D_RULES),
    "add_pair": Op((ANY,), "надпись и поле ввода на реквизит формы одним вызовом: место по соседям, выравнивание по строке, тип и привязка по реквизиту", D_RULES),
    "remove_element": Op((ANY,), "элемент вместе с вложенными, его узел, счётчики и ссылки на него", D_RULES),
    "rename_element": Op((ANY,), "имя элемента (ссылки в файле идут по индексу, модуль не правится)", D_RULES),
    "move_element": Op((ANY,), "место и размер элемента; родитель и страница; привязки проверяются на модели раскладки", D_RULES),
    "reparent": Op((ANY,), "элемент к другому родителю: на форму или на страницу панели", D_RULES),
    "change_type": Op((ANY,), "вид элемента на месте: имя, место, привязки, данные и события сохраняются", D_RULES),
    "set_anchors": Op((ANY,), "привязки границ элемента по именам ролей осей", D_ANCHORS),
    "set_font": Op((ANY,), "шрифт элемента (у колонки таблицы — три шрифта: ячейки, шапки, подвала)", D_FONT),
    "set_property": Op((ANY,), "свойство элемента, колонки, страницы или самой формы по имени из карты формата", D_SETPROP),
    "set_event": Op((ANY,), "обработчик события элемента: процедура модуля", D_RULES),
    # по видам
    "set_caption": Op(("Label", "CheckBox", "RadioButton", "Button", "GroupBox"), "заголовок элемента (текст надписи, флажка, кнопки, рамки группы)", D_RULES),
    "bind": Op(tuple(ed_data.CORPUS_BIND_TYPES), "привязка данных: реквизит формы или путь по метаданным (`data`, нужна выгрузка)", D_MODULE),
    "set_type_link": Op(("TextBox",), "«Связь по типу» поля ввода и вложенного поля колонки", D_RULES),
    "set_field_type": Op(("TextBox",), "тип поля ввода и его реквизита формы (строка, число, дата)", D_MODULE),
    "set_menu_mode": Op(("Button",), "режим меню кнопки формы", D_FONT),
    "set_action_source": Op(("CommandBar",), "источник действий командной панели: табличное поле формы", D_RULES),
    "add_button": Op(("CommandBar",), "кнопка, подменю или разделитель в командную панель", D_BUTTONS),
    "move_button": Op(("CommandBar",), "кнопка на другое место в её наборе: before / after / index (порядок в файле — порядок на экране)", D_BUTTONS),
    "remove_button": Op(("CommandBar",), "кнопка из командной панели (узел и запись действия)", D_BUTTONS),
    "set_button_action": Op(("CommandBar",), "действие кнопки панели: стандартное либо процедура модуля", D_BUTTONS),
    "set_button_picture": Op(("CommandBar",), "картинка кнопки панели", D_BUTTONS),
    "set_button_text": Op(("CommandBar",), "текст кнопки панели", D_BUTTONS),
    "set_description": Op(("CommandBar",), "пояснение кнопки панели (строка состояния)", D_BUTTONS),
    "set_tool_tip": Op(("CommandBar",), "подсказка кнопки панели", D_BUTTONS),
    "set_button_shortcut": Op(("CommandBar", "Button"), "сочетание клавиш кнопки панели или кнопки формы", D_BUTTONS),
    "add_column": Op(("TableBox",), "колонка в табличное поле: по соседней колонке или по образцу; данные колонки", D_COLUMNS),
    "add_columns": Op(("TableBox",), "колонки таблицы или дерева значений одной операцией: имя, заголовок, тип, ширина, выравнивание, формат", D_COLUMNS),
    "set_column_type": Op(("TableBox",), "тип колонки таблицы или дерева значений (строка, число, дата, булево) и описатель её поля ввода", D_COLUMNS),
    "remove_column": Op(("TableBox",), "колонка из табличного поля", D_COLUMNS),
    "set_column_control": Op(("TableBox",), "вид вложенного элемента колонки (поле ввода, флажок, поле выбора)", D_COLUMNS),
    "add_page": Op(("Panel",), "страница панели (место — before / after / index, без них последней)", D_RULES),
    "move_page": Op(("Panel",), "страница панели на другое место: before / after / index (порядок страниц в файле — порядок закладок)", D_PAGES),
    "remove_page": Op(("Panel",), "удаление страницы панели", D_RULES),
    "copy_layer": Op(("GeographicalSchemaField",), "слой поля географической схемы из формы-образца", D_SETPROP),
}

KIND_LABEL = {FORM: "Форма в целом", MODULE: "Модуль формы", ANY: "Любой элемент",
              "Label": "Надпись (Label)", "TextBox": "Поле ввода (TextBox)", "ComboBox": "Поле выбора (ComboBox)", "CheckBox": "Флажок (CheckBox)",
              "RadioButton": "Переключатель (RadioButton)", "Button": "Кнопка (Button)", "GroupBox": "Рамка группы (GroupBox)", "Panel": "Панель (Panel)",
              "CommandBar": "Командная панель (CommandBar)", "TableBox": "Табличное поле (TableBox)",
              "GeographicalSchemaField": "Поле географической схемы (GeographicalSchemaField)"}

# Шаблоны, которые `add_element` берёт по имени (каталог `frm_codec/data/templates/`, без служебных файлов колонок, меню и действий).
ADD_TEMPLATES = ("Button", "CalendarBox", "Chart", "CheckBox", "ComboBox", "CommandBar", "Dendrogram", "GanttChart", "GeographicalSchemaField",
                 "GraphicalSchemaField", "GroupBox", "HTMLDocumentField", "Label", "ListBox", "Panel", "PDFDocumentField", "PictureBox", "PivotChart",
                 "ProgressBar", "RadioButton", "Splitter", "SpreadsheetDocumentField", "TableBox", "TableBox-tabular", "TextBox", "TextDocumentField", "TrackBar")
LISTED = 6              # элементов в одной строке перечня называется поимённо, остальные — числом
CODE_ROWS = 40          # строк таблицы «Имена в коде» не больше стольких
HANDLERS_LISTED = 12    # обработчиков в перечне
REASON_CHARS = 260     # знаков причины отказа операции в оговорке

# Оговорка к примеру `move_element`: без `anchor` привязки пишутся заново, и перенос меняет поведение при растяжении окна, а порядок обхода уходит в конец.
MOVE_WARN = ("без ключа `anchor` операция пишет привязки заново — перебором на модели раскладки, и поведение при растяжении окна может измениться "
             "(у поля, привязанного к разделителю или к соседу, — тоже); чтобы сдвинуть элемент, не меняя его поведения, добавьте `\"anchor\": \"keep\"` "
             "(прежние привязки, смещения пересчитываются; только в том же родителе и на той же странице), либо `{\"as\": \"<сосед по столбцу>\"}` — правила соседа; подробно — `docs/edit-rules.md`")

CODE_BY_HAND = ("Правка кода — руками в модуле (`form.bsl`), затем `pack` или загрузка формы: операции редактора существующий текст модуля не правят "
                "(`append_procedure` только добавляет процедуру в конец).")

VERIFY = (
    ("правка в копию", "`frm_json.py edit <форма> --ops ops.json -o правка.frm --render cmp.png` — исходная форма не меняется; для операций с модулем добавьте "
                       "`--bsl form.bsl --bsl-out правка.bsl`, для путей по метаданным — `--config <выгрузка>`; строка «Записано» показывает результат, картинка — «до | после»"),
    ("досье заново", "`frm_json.py brief правка.frm [--config <выгрузка> --origin <form.frm исходной формы в выгрузке>]` — сравните разделы 3 (структура), 4 (поведение) и 7 (факты) "
                     "с прежними; `--origin` не даёт исходной форме стать соседом своей копии (иначе раздел 6 и число соседей считаются с ней)"),
    ("растяжение", "`frm_json.py render правка.frm --sizes 715x440,968x561,min,max --before <форма> -o strip.png` — кадры при разных размерах окна; "
                   "`frm_json.py anchors-check правка.frm` — диагноз привязок после правки"),
    ("проверка формата", "`frm_json.py validate правка.frm` — три уровня проверки; её же выполняет `edit` перед записью"),
    ("в предприятии", "загрузка формы в базу и просмотр в 1С:Предприятии — вне навыка"),
)


# ── Разбор операций ──

def table_check():
    """Расхождения таблицы `OPS` с перечнем операций редактора: `(нет в таблице, лишние в таблице)`."""
    known = set(ed_ops.FORM_OPS) | set(ed_ops.MODULE_OPS) | set(ed_ops.COMBINED_OPS)
    return sorted(known - set(OPS)), sorted(set(OPS) - known)


def _short(text, limit=REASON_CHARS):
    """Текст в одну строку не длиннее `limit` знаков; обрезка — по границе слова, с многоточием."""
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    cut = text[:limit - 1]
    return (cut.rsplit(" ", 1)[0] if " " in cut else cut).rstrip(" ,;:") + "…"


def _list(names, limit=LISTED):
    names = [str(n) for n in names]
    shown = ", ".join(f"«{n}»" for n in names[:limit])
    return shown + (f" и ещё {len(names) - limit}" if len(names) > limit else "")


class _Ctx:
    """Что известно о форме: данные раздела, на которых строятся ограничения, оговорки и примеры."""

    def __init__(self, doc, form, structure, names, elements, tables, bars, module, module_text, head, behavior, event_words):
        self.doc, self.form, self.structure, self.names = doc, form, structure, names
        self.elements, self.tables, self.bars, self.module = elements, tables, bars, module
        self.module_text, self.head, self.behavior, self.event_words = module_text, head, behavior, event_words
        self.version = design.form_version(doc)
        self.by_kind = collections.OrderedDict()
        for row in elements:
            self.by_kind.setdefault(row["type"], []).append(row)
        self.pairs = [(n.elements[0], n.elements[1], n.id) for n in structure.walk() if n.kind == "label_field" and len(n.elements) == 2]
        self.pair_labels = {names.short(a) for a, _b, _n in self.pairs}
        counts = collections.Counter(item.name for item in form.items.values())
        self.unique = {name for name, n in counts.items() if n == 1 and name}      # имена, которыми операции находят элемент
        self.effects = {}
        for effect in module.get("effects") or []:
            self.effects.setdefault(effect["element"], []).append(effect)
        self.refused = []         # шаблоны, которые не встанут в форму этой версии: [(шаблон, причина)]
        self.refs = {}            # имена в коде: `_code_names`

    def short(self, full):
        return self.names.short(full)

    def rows(self, kind):
        return self.by_kind.get(kind, [])

    def has_module(self):
        return bool(self.module.get("present"))

    def coded_props(self, wanted, part=None):
        """Короткие имена элементов, у которых код меняет одно из свойств `wanted`; `part` — «кнопка»: свойства кнопок панели."""
        out = []
        for element, entries in self.effects.items():
            for e in entries:
                own = e["part"] is None if part is None else bool(e["part"] and e["part"].startswith(part))
                if own and set(e["props"]) & set(wanted):
                    out.append(self.short(element))
                    break
        return out


# ── Ограничения формы ──

def _version_refusals(doc, version):
    """`[(шаблон, причина)]` — шаблоны `add_element`, которые не встанут в форму версии 10, 13 или 15 без `unverified`; для версии 16 пусто."""
    out = []
    for name in ADD_TEMPLATES:
        node = templates.element(name)
        reason = ed_elements.old_version_refusal(doc, version, name, node.get("type"))
        if reason is not None:
            out.append((name, reason))
    return out


def _constraints(ctx):
    """`(ограничения, проверено без находок)`: ограничения — `[{key, title, points, ops}]` только те, что есть у формы; `points` — предложения-пункты."""
    found, clear = [], []
    doc, version = ctx.doc, ctx.version

    def add(key, title, points, ops):
        found.append({"key": key, "title": title, "points": points, "ops": ops})

    # версия записи и поколение платформы
    if version is None:
        add("version", "Версия записи формы не прочитана", ["Версию общего блока контейнера формы прочесть не из чего: сверки версий у операций нет."], ["add_element", "change_type"])
    elif version != 16:
        ctx.refused = _version_refusals(doc, version)
        points = [f"Форма записана поколением {version}, а шаблоны элементов записаны версией 16: в форму встаёт шаблон, сведённый к версии формы по правилу, "
                  "которое подтверждает корпус форм."]
        if ctx.refused:
            points.append("Не встанут без `unverified` (отказ называет причину и число подтверждающих элементов): " + ", ".join(name for name, _r in ctx.refused)
                          + ". Выход без `unverified` — `like` (копия соседа этой формы) либо узел из формы той же версии.")
        if version == ed_formpage.FORM_PAGE_OLD:
            points.append(f"Свойства страницы формы (`set_property` с ключом `page`): у поколения {version} страницы устроены иначе, операция отказывает, и `unverified` "
                          "отказа не снимает.")
        else:
            points.append(f"Свойства страницы формы (`set_property` с ключом `page`) и операции со страницами проверены у поколения {ed_formpage.FORM_PAGE_VERSION}: "
                          "у этого поколения они отказывают без `unverified`.")
        points.append("`set_view` у формы не версии 16 отказывает: вид поля ввода там задаёт поколение, выход — пересохранение формы в конфигураторе.")
        add("version", f"Версия записи формы — {version}", points,
            ["add_element", "change_type", "set_property", "add_form_page", "move_form_page", "remove_form_page", "move_page", "remove_page", "set_view"])
    else:
        clear.append("версия записи 16 (шаблоны всех видов, страницы и вид оформления проверены у неё)")

    # связи между полями по обработчикам событий (разбор кода)
    links = ctx.module.get("event_links") or []
    if links:
        add("event_links", "Связи между полями по обработчикам событий",
            ["Обработчики событий одного поля меняют другие поля и колонки (по разбору кода): " + _list(
                f"«{l['source']}» ({l['event']}) → {', '.join(l['targets'])}" + (f" (и реквизиты {', '.join(l['data'])})" if l.get("data") else "") for l in links) + ".",
             "Переименование и удаление названного поля или колонки ломает связь: код обращается к ним по имени."], ["rename_element", "remove_element"])
        # DPI и Рамка
    dpi = (doc.get("form") or {}).get("dpi")
    bounds = ed_pages.form_page_bounds(doc)
    if dpi is not None and dpi != 96:
        points = [f"DPI формы — {dpi}: размеры в пикселях, ширины текста и нормы досье рассчитаны на 96."]
        ops = []
        if any(b.startswith("DPI формы") for b in bounds):
            points.append("Операции со страницами формы проверялись при DPI 96 и без `unverified` отказывают.")
            ops += ["add_form_page", "remove_form_page"]      # перестановка страниц (`move_form_page`) от DPI и Рамки не зависит
        if anchors_fix.high_dpi(ctx.form):
            points.append("Правило привязки «на саму себя» на такой форме ломает растяжение по высоте; `normalize_anchors` и `repair_anchors` исправляют именно такие записи.")
            ops += ["normalize_anchors", "repair_anchors"]
        add("dpi", f"DPI формы — {dpi}", points, ops)
    else:
        clear.append("DPI 96 (или записи DPI нет)")
    border = [b for b in bounds if b.startswith("у формы Рамка")]
    if border:
        add("border", "У формы есть Рамка",
            [f"У формы Рамка ({ed_pages._form_border_type(doc)}): проверялись формы без Рамки, а Рамка сама сдвигает отступы направляющих.",
             "Операции со страницами формы без `unverified` отказывают."], ["add_form_page", "remove_form_page"])

    # смесь оформления
    _version, alien = design.mixed(doc)
    nested = design.nested_mix(doc)
    minority = design.view_minority(doc)
    views = design.form_views(doc, version) if version is not None else collections.Counter()
    points = []
    if alien:
        points.append("Элементы с версией общего блока, отличной от версии формы: " + _list(f"{n} ({t}, версия {v})" for n, t, v in alien) + ".")
    if nested:
        points.append("Вложенные поля колонок другой версии, чем форма, вне пар, которые пишет платформа: " + _list(f"{k} колонки {c} у {n}" for n, c, k, _v in nested) + ".")
    if minority:
        points.append("У полей два вида оформления (8.2 и 8.3 вперемешку); меньшинство: " + "; ".join(f"{kind} — {_list(items)}" for kind, items in minority.items()) + ".")
    elif len(views) > 1:
        points.append("У полей ввода два вида оформления поровну: " + design.views_words(views) + ".")
    if points:
        points.append("Новый элемент берёт вид формы (у смешанной — вид конфигурации, `--siblings`); `set_view` приводит все поля ввода формы к одному виду.")
        add("design", "Оформление формы смешанное", points, ["add_element", "set_view"])
    else:
        clear.append("оформление однородно (одна версия общего блока, один вид полей ввода)")

    # «Изменять размер» снято
    if ctx.head.get("fixed_size"):
        add("fixed_size", "Изменять размер снято",
            ["Окно формы не растягивается: диагноз привязок и `repair_anchors` не проверяют растяжение (остаются только мёртвые правила, циклы и формальные рисунки), "
             "раскладка при растяжении не рассчитывается."], ["repair_anchors", "normalize_anchors", "relayout"])
    else:
        clear.append("размер формы изменяемый")

    # дальние направляющие
    far = guides.far_guides(doc)
    if far:
        words = "; ".join(f"{guides.ORDERS[order]} направляющая {'страницы ' + str(page) + ' ' if page else ''}в {coord} (отступ {margin})" for page, order, coord, margin in far)
        add("guides", "Дальние направляющие края формы",
            [words.capitalize() + ": позиция не у края формы, в предприятии раскладка может «залипать» после растяжения окна.",
             "`normalize_guides` переносит их к краю, элементы и привязки не меняются; смена размера формы (`set_property`) двигает направляющие вместе с краем."],
            ["normalize_guides", "set_property"])
    else:
        clear.append("направляющие края у края формы")

    # страницы панелей не по видимой части
    pages = layout.wide_pages(ctx.form) + layout.narrow_pages(ctx.form)
    if pages:
        names = ", ".join(sorted({f"«{owner.qualified()}» (страница {page})" for owner, page, *_rest in pages}))
        add("page_edges", "Края страниц панелей не по видимой части панели",
            [f"Направляющие края страницы стоят не по видимой области панели: {names}. Предприятие считает правила вложенных от области, поэтому поля в файле нарисованы не там, где их увидит пользователь.",
             "`normalize_page_edges` переносит направляющие страницы на край области и записывает вложенным элементам то место, где их ставит предприятие; раскладка при любом размере окна не меняется, "
             "а перед записью операция это проверяет."], ["normalize_page_edges"])
    else:
        clear.append("края страниц панелей совпадают с видимой частью панели")

    # привязки
    anchors = [p for p in ctx.behavior.get("problems", []) if p["kind"] == "anchors"]
    if anchors:
        words = [f"{repair.KIND_WORDS.get(p['numbers'].get('finding'), p['numbers'].get('finding'))}: {_short(ctx.names.text(p['words']), 200)}" for p in anchors]
        points = ["Диагноз привязок (`anchors-check`): " + "; ".join(words[:LISTED]) + (f"; и ещё {len(words) - LISTED}" if len(words) > LISTED else "") + ".",
                  "`repair_anchors` перебирает варианты привязок виновников, место и размер не меняет; вариант, который сужает предел раскладки или после которого элемент "
                  "перестал бы растягиваться, отвергается, и тогда поломка остаётся с причиной в отчёте.",
                  "Командная панель и разделитель правятся только по мёртвому правилу и циклу, остальное вручную (`set_anchors`). Пара «надпись и поле» чинится цепочкой: "
                  "сначала надпись, затем поле; если цепочка не дошла до конца, правка отменяется."]
        add("anchors", "Найдены поломки привязок", points, ["repair_anchors", "set_anchors", "normalize_anchors"])
    else:
        clear.append("поломок привязок диагноз не нашёл")

    # имена элементов: операции находят элемент по имени
    twins = sorted({name for name, n in collections.Counter(item.name for item in ctx.form.items.values()).items() if n > 1 and name})
    nameless = [item for item in ctx.form.items.values() if not item.name]
    if twins or nameless:
        points = []
        if twins:
            points.append("Имя носят несколько элементов (на разных панелях и страницах): " + _list(twins) + ".")
        if nameless:
            points.append(f"Элементов без имени: {len(nameless)}.")
        points.append("Операции находят элемент по имени и по такому имени отказывают («какой из них править, по имени не решить»); `rename_element` ищет элемент так же, "
                      "поэтому переименовать тёзку этим способом нельзя.")
        add("names", "Имена элементов неоднозначны", points, ["rename_element", "move_element", "remove_element", "set_caption", "set_font", "set_anchors", "set_event"])
    else:
        clear.append("имена элементов уникальны")

    # подпись на нескольких языках
    several = _multilingual(ctx)
    if several:
        add("languages", "Подписи на нескольких языках",
            ["Подпись записана на нескольких языках у " + _list(several) + ".",
             "`set_caption` и `set_button_text` переписывают только член, который показывает платформа (основной язык конфигурации из выгрузки; без выгрузки — `ru`), "
             "остальные члены остаются как были."], ["set_caption", "set_button_text"])
    else:
        clear.append("подписей на нескольких языках нет")
    return found, clear


def _multilingual(ctx):
    """Короткие имена элементов, у которых подпись записана больше чем одним членом."""
    out = []
    for item in ctx.form.items.values():
        try:
            slot = ed_base.caption_slot(item.node, item.name)
        except (EditError, KeyError, TypeError, AttributeError):
            continue
        if isinstance(slot, dict) and len(lstring._members(slot)) > 1:
            out.append(ctx.short(item.qualified()))
    return out


# ── Имена, на которые опирается код ──

_NAME = r"[\wА-Яа-яЁё]+"
REF = re.compile(rf"(?<![\w.])(?:ЭтаФорма\s*\.\s*)?ЭлементыФормы\s*\.\s*(?P<el>{_NAME})(?:\s*\.\s*(?P<part>Страницы|Кнопки|Колонки)\s*\.\s*(?P<sub>{_NAME}))?"
                 rf"(?:\s*\.\s*(?P<member>{_NAME}))?", re.I)
BY_STRING = re.compile(r'(?<![\w.])(?:ЭтаФорма\s*\.\s*)?ЭлементыФормы\s*(?:\[\s*"(?P<s1>[^"]+)"\s*\]|\.\s*Найти\s*\(\s*"(?P<s2>[^"]+)"\s*\))', re.I)
PART_OPS = {"кнопки": ("remove_button",), "колонки": ("remove_column",), "страницы": ("remove_page",)}
PART_WORDS = {"кнопки": "кнопка", "колонки": "колонка", "страницы": "страница"}
COLLECTION_METHODS = ("найти", "получить", "количество", "индекс")      # `ЭлементыФормы.Найти(…)` — обращение к коллекции, а не к элементу
PART_METHODS = vocab.PART_METHODS      # метод коллекции `Кнопки.Удалить(…)`, `Колонки.Добавить(…)`: после точки стоит не имя кнопки, колонки или страницы


def _procedure_at(procs, number):
    for name, _params, first, last in procs:
        if first <= number <= (last if last is not None else first):
            return name
    return None


def _code_names(ctx):
    """`{present, rows, handlers, unknown}`: что в тексте модуля названо по имени и что сломает переименование или удаление; `unknown` — обращений к именам,
    которых на форме нет."""
    module = ctx.module
    if ctx.module_text is None:
        return {"present": False, "rows": [], "handlers": [], "unknown": 0, "unknown_names": []}
    lines = scan.scan(ctx.module_text)
    procs = scan.procedures_of(lines)
    by_label = br_module.label_map(ctx.names)
    buttons = {}
    for bar in ctx.bars:
        names_ = set()

        def walk(items):
            for b in items:
                names_.add(b["name"])
                walk(b.get("children") or [])
        walk(bar.get("buttons") or [])
        buttons[bar["element"]] = names_
    columns = {t["element"]: {c["name"] for c in t["columns"] if c.get("name")} for t in ctx.tables}
    found = collections.OrderedDict()
    unknown = 0

    def add(label, how, part, sub, number, member):
        nonlocal unknown
        fulls = by_label.get(label.casefold())
        if not fulls:
            unknown += 1
            return
        for full in fulls:
            key = (full, part, sub)
            entry = found.setdefault(key, {"element": full, "short": ctx.short(full), "part": part, "sub": sub, "how": set(), "procedures": [], "lines": [], "members": []})
            entry["how"].add(how)
            proc = _procedure_at(procs, number)
            if proc and proc not in entry["procedures"]:
                entry["procedures"].append(proc)
            entry["lines"].append(number)
            if member and member not in entry["members"]:
                entry["members"].append(member)

    for number, masked, raw in lines:
        for hit in REF.finditer(masked):
            if hit.group("el").casefold() in COLLECTION_METHODS:
                continue
            part = hit.group("part").casefold() if hit.group("part") else None
            if part and hit.group("sub").casefold() in PART_METHODS and masked[hit.end():].lstrip().startswith("("):
                add(hit.group("el"), "имя", None, None, number, f"{hit.group('part')}.{hit.group('sub')}")        # `ЭлементыФормы.Панель.Кнопки.Удалить(…)`: метод коллекции, к панели обращение есть, кнопки с таким именем нет
                continue
            add(hit.group("el"), "имя", part, hit.group("sub") if part else None, number, hit.group("member") if not part else None)
        for hit in BY_STRING.finditer(raw):
            add(hit.group("s1") or hit.group("s2"), "строка", None, None, number, None)
    rows = []
    for entry in found.values():
        item = ctx.names.item_of.get(entry["element"])
        kind = item.type if item is not None else None
        part, sub = entry["part"], entry["sub"]
        exists = None
        if part == "кнопки":
            exists = sub in buttons.get(ctx.short(entry["element"]), buttons.get(entry["element"], set()))
        elif part == "колонки":
            exists = sub in columns.get(ctx.short(entry["element"]), columns.get(entry["element"], set()))
        breaks = list(PART_OPS[part]) if part else ["rename_element", "remove_element"]
        rows.append({"element": entry["element"], "short": entry["short"], "type": kind, "node": ctx.names.node(entry["element"]),
                     "part": PART_WORDS[part] if part else None, "sub": sub, "in_file": exists,
                     "how": sorted(entry["how"]), "members": entry["members"], "procedures": entry["procedures"][:3], "uses": len(entry["lines"]),
                     "breaks": breaks})
    handlers = []
    for row in module.get("handlers") or []:
        if row.get("owner") == "element":
            handlers.append({"element": row["element"], "event": row["event"], "procedure": row["procedure"], "found": row.get("found")})
    unknown_names = [{"name": m["name"], "procedure": m["procedure"], "line": m["line"], "uses": len(m["lines"])} for m in module.get("missing_refs") or []]
    return {"present": True, "rows": rows, "handlers": handlers, "unknown": unknown, "unknown_names": unknown_names}


# ── Оговорки операций на этой форме ──

def _count(node):
    """Элементов узла структуры вместе с вложенными узлами."""
    return len(node.elements) + sum(_count(child) for child in node.children)


def _page_groups(ctx):
    """`[(панель, [(номер страницы, имя страницы, подпись закладки, число элементов)])]` — панели формы с их страницами; имя — то, которым страницу называют операции."""
    page_names = content.page_names(ctx.form, ctx.names)
    pages = collections.OrderedDict()
    for node in ctx.structure.walk():
        if node.role == "page" and node.holder is not None:
            name = page_names.get((node.holder, node.page))
            pages.setdefault(node.holder, []).append((node.page, name, node.caption or "", _count(node)))
    return [(ctx.short(holder), rows) for holder, rows in pages.items()]


# Где ставить элемент на странице панели: `box` вложенного — от левого верха области страницы, отступ от её краёв — норма Конфигуратора (у формы — 8 от края).
PAGE_PLACE_WORDS = (f"на странице панели с закладками «Сверху» и «Снизу» `box` — от левого верха области страницы (размер панели минус полоса закладок и линии страницы), "
                    f"отступ элемента от краёв области — {layout.PAGE_INSET} px, как у Конфигуратора (у формы — 8 от её края); у панели «Не отображать» и «Слева (горизонтально)» "
                    f"отступа нет — вложенные стоят вплотную, панель раскладывает форму")


def _page_words(ctx):
    out = []
    for panel, rows in _page_groups(ctx):
        listed = []
        for n, name, caption, count in rows:
            label = f"«{name}»" if name else f"номер {n}"
            listed.append(f"{label}" + (f" (закладка «{caption}»)" if caption and caption != name else "") + f", элементов {count}")
        out.append(f"«{panel}»: " + "; ".join(listed))
    return out


def _form_page_words(ctx):
    """Страницы самой формы (не панелей): `«имя» (закладка «…»), элементов N`; пусто, если страница одна."""
    page_names = content.page_names(ctx.form, ctx.names)
    pages = [n for n in ctx.structure.walk() if n.role == "page" and n.holder is None]
    if len(pages) < 2:
        return []
    out = []
    for node in pages:
        name = page_names.get((None, node.page))
        label = f"«{name}»" if name else f"номер {node.page}"
        out.append(label + (f" (закладка «{node.caption}»)" if node.caption and node.caption != name else "") + f", элементов {_count(node)}")
    return out


EVENTS_LISTED = 8      # событий одного вида в оговорке `set_event` называется не больше стольких


def _events_of(kind, event_words):
    pairs = {event for k, event in list(ed_data.CORPUS_EVENT_PAIRS) + list(ed_data.ROUND_EVENT_PAIRS) if k == kind}
    return sorted(event_words.get(event, event) for event in pairs)


def _problems(ctx):
    return [p for p in ctx.behavior.get("problems", []) if p["kind"] == "anchors"]


def _notes(ctx, op):
    """Оговорки к операции на этой форме: `[строка]`; пусто — особых нет."""
    out = []
    code = ctx.refs.get("rows", [])

    def coded(breaking):
        return list(dict.fromkeys(r["short"] for r in code if r["part"] is None and breaking in r["breaks"]))

    if op == "add_element":
        if ctx.refused:
            out.append(f"в форму версии {ctx.version} не встанут шаблоны: " + ", ".join(n for n, _r in ctx.refused))
        panels = _page_words(ctx)
        if panels:
            out.append("внутрь панели — `holder` и `page`: " + "; ".join(panels[:3]))
            out.append(PAGE_PLACE_WORDS + "; без `box` элемент встаёт по соседям страницы, на пустой странице операция `box` требует")
        if ctx.pairs:
            out.append("надпись и поле пары — отдельные элементы, пару составляют двумя вызовами")
    elif op == "remove_element":
        names = coded("remove_element")
        if names:
            out.append("названы в коде (обращение по прежнему имени сломается, модуль операция не правит): " + _list(names))
        nested = [ctx.short(i.qualified()) for i in ctx.form.items.values()
                  if i.type == "Panel" and any(o.qualified().startswith(i.qualified() + "/") for o in ctx.form.items.values())]
        if nested:
            out.append("вместе с панелью уходят вложенные элементы: " + _list(nested))
        if ctx.refs.get("handlers"):
            out.append("процедура-обработчик остаётся в модуле без элемента (операции модуля только добавляют процедуры)")
    elif op == "rename_element":
        names = coded("rename_element")
        if names:
            out.append("названы в коде (обращение по прежнему имени сломается, модуль операция не правит): " + _list(names))
        out.append("имя процедуры-обработчика хранится в самом элементе и не меняется")
    elif op == "move_element":
        if ctx.pairs:
            out.append(f"пар «надпись → поле»: {len(ctx.pairs)}; двигается один элемент, второй двигают отдельно (например, "
                       + f"«{ctx.short(ctx.pairs[0][0])}» → «{ctx.short(ctx.pairs[0][1])}»)")
        panels = _page_words(ctx)
        if panels:
            out.append("на другую панель или страницу — `holder`, `page` либо `reparent`: " + "; ".join(panels[:3]))
            out.append(PAGE_PLACE_WORDS)
    elif op == "reparent":
        panels = _page_words(ctx)
        out.append("панели и страницы: " + "; ".join(panels[:3]) if panels else "панелей со страницами на форме нет: переносить можно только на форму")
        if panels:
            out.append(PAGE_PLACE_WORDS + "; без `box` платформа ставит элемент в точку вставки (21, 21), поэтому `box` называют")
    elif op == "change_type":
        if ctx.refused:
            out.append(f"новый вид по шаблону из отказов версии {ctx.version} тоже откажет: " + ", ".join(n for n, _r in ctx.refused))
    elif op == "set_anchors":
        problems = _problems(ctx)
        out.append("диагноз привязок: " + _short("; ".join(ctx.names.text(p["words"]) for p in problems), 220) if problems else "поломок привязок диагноз не нашёл")
        if ctx.head.get("fixed_size"):
            out.append("«Изменять размер» снято: растяжение у формы не рассчитывается")
    elif op == "set_event":
        parts = [f"{kind}: " + ", ".join(events[:EVENTS_LISTED]) + (f" и ещё {len(events) - EVENTS_LISTED}" if len(events) > EVENTS_LISTED else "")
                 for kind in ctx.by_kind for events in [_events_of(kind, ctx.event_words)] if events]
        if parts:
            out.append("события, которые операция ставит без `unverified`, по видам этой формы — " + "; ".join(parts))
        out.append("процедура должна быть в модуле (`append_procedure`)" + ("" if ctx.has_module() else "; модуля рядом с формой нет: нужны `--bsl` и `--bsl-out`"))
    elif op == "set_property":
        changed = ctx.coded_props(("видимость", "доступность", "только просмотр"))
        if changed:
            out.append("видимость или доступность задаёт код модуля у " + _list(changed) + ": значение из файла код перекроет при открытии или по условию")
    elif op == "set_caption":
        coded_text = ctx.coded_props(("заголовок", "пометка"))
        if coded_text:
            out.append("текст на экране подставляет код у " + _list(coded_text) + ": в файле лежит заготовка")
        labels = [r["short"] for r in ctx.rows("Label") if r["short"] in ctx.pair_labels]
        if labels:
            out.append("подпись поля в паре — отдельная надпись (Label): " + _list(labels))
        several = _multilingual(ctx)
        if several:
            out.append("подпись на нескольких языках у " + _list(several) + ": правится видимый член")
    elif op == "bind":
        bound = [r["short"] for r in ctx.elements if r["type"] in ed_data.CORPUS_BIND_TYPES and r.get("data")]
        free = [r["short"] for r in ctx.rows("TextBox") if not r.get("data")]
        if bound:
            out.append(f"данные есть у {len(bound)} элементов; поля ввода без данных: " + (_list(free) if free else "нет"))
        if not ctx.head["received"]["config"]:
            out.append("выгрузки конфигурации у досье нет: путь по метаданным (`data`) без `--config` операция не выполнит")
    elif op == "set_field_type":
        ok, blocked = [], []
        for row in ctx.rows("TextBox"):
            if row["short"] not in ctx.unique:
                continue
            reason = ed_fieldtype.field_type_blocker(ctx.doc, row["short"])
            (blocked if reason else ok).append((row["short"], reason))
        if ok:
            out.append("подходят поля: " + _list([n for n, _r in ok]))
        if blocked:
            out.append("не подходят: " + _list([n for n, _r in blocked]) + f"; например, «{blocked[0][0]}» — {_short(blocked[0][1])}")
    elif op in BAR_BUTTON_OPS or op in ("set_action_source", "set_button_shortcut"):
        out += _bar_notes(ctx, op)
    elif op in ("add_column", "remove_column", "set_column_control"):
        out += _table_notes(ctx, op)
    elif op in ("add_page", "move_page", "remove_page"):
        pages = _page_words(ctx)
        out.append("панели формы: " + "; ".join(pages) if pages else "у панелей формы страниц нет")
        if op == "remove_page":
            out.append("страницу с элементами и единственную страницу операция не удаляет (с `unverified` тоже)")
            named = sorted({r["sub"] for r in code if r["part"] == "страница"})
            if named:
                out.append("названы в коде: " + _list(named))
    elif op == "set_saved_values":
        try:
            ed_formprops._saved_block(ctx.doc)
            out.append("у формы есть блок настроек: список доступен")
        except EditError:
            out.append("недоступна: «Сохраняемые значения» есть только у формы отчёта и обработки (блок настроек основного реквизита)")
    elif op == "set_view":
        if ctx.version != 16:
            out.append(f"форма версии {ctx.version}: операция отказывает")
        else:
            out.append("виды полей ввода сейчас: " + (design.views_words(design.form_views(ctx.doc, ctx.version)) or "полей ввода нет"))
    elif op in ("add_form_page", "move_form_page", "remove_form_page"):
        own = _form_page_words(ctx)
        out.append("страницы формы: " + "; ".join(own) if own else "у формы одна страница (закладок нет)")
        if op == "move_form_page":      # перестановка от DPI и Рамки не зависит: её граница — закладки и поколение формы
            try:
                bounds = ed_pages._form_move_wider(ctx.doc, ed_pages._form_pages_block(ctx.doc).get("show_tabs"), ctx.version)
            except EditError as why:
                bounds = [str(why)]
            out.append("без `unverified` откажет: " + "; ".join(_short(b, 110) for b in bounds) if bounds
                       else "проверенный случай: поколение 16, закладки «Не отображать» или «Сверху»")
        else:
            bounds = ed_pages.form_page_bounds(ctx.doc)
            out.append("без `unverified` откажет: " + "; ".join(_short(b, 110) for b in bounds) if bounds else "проверенный случай: поколение 16, DPI 96, без Рамки")
    elif op == "normalize_page_edges":
        pages = layout.wide_pages(ctx.form) + layout.narrow_pages(ctx.form)
        out.append(f"страниц панелей не по видимой части: {len({(o.qualified(), pg) for o, pg, *_r in pages})}" if pages else "страниц панелей не по видимой части нет: форма не изменится")
    elif op == "normalize_guides":
        far = guides.far_guides(ctx.doc)
        out.append(f"дальних направляющих: {len(far)}" if far else "дальних направляющих нет: форма не изменится")
    elif op in ("repair_anchors", "normalize_anchors"):
        problems = _problems(ctx)
        out.append(f"поломок по диагнозу: {len(problems)}" if problems else "поломок нет: форма не изменится")
        if ctx.head.get("fixed_size"):
            out.append("растяжение не проверяется («Изменять размер» снято)")
    elif op == "set_form_event":
        form_handlers = [h for h in ctx.module.get("handlers") or [] if h.get("owner") == "form"]
        out.append("уже названы в файле: " + _list(f"{h['event']} → {h['procedure']}" for h in form_handlers) if form_handlers else "обработчиков события формы в файле нет")
    elif op == "append_procedure":
        out.append(f"в модуле процедур и функций: {ctx.module.get('procedures', 0)}" if ctx.has_module()
                   else "модуля рядом с формой нет: нужны `--bsl` и `--bsl-out` (файл можно завести пустым)")
    elif op == "add_period_choice":
        out.append("правит форму и модуль: нужны `--bsl` и `--bsl-out`" + ("" if ctx.has_module() else "; модуля рядом с формой нет"))
    elif op == "add_collapsible_panel":
        out.append("правит форму и модуль: нужны `--bsl` и `--bsl-out`" + ("" if ctx.has_module() else "; модуля рядом с формой нет"))
        for sample in ed_collapse.find_samples(ctx.doc)[:2]:
            marked = "; ".join(f"«{b}» панели «{bar}»" for bar, _name, b in sample["buttons"][:3])
            out.append(f"панель «{sample['panel']}» устроена как сворачиваемая ({'слева' if sample['side'] == 'left' else 'сверху'}, без закладок; на её краю: "
                       + _list(sample["neighbors"]) + ")" + (f"; кнопки с пометкой в файле на панелях формы: {marked}" if marked else "")
                       + ": свёртку ставит код модуля, файл этого не говорит")
    elif op == "relayout":
        if ctx.head.get("fixed_size"):
            out.append("«Изменять размер» снято: размер окна задаёт файл")
    return out


def _bar_notes(ctx, op):
    out = []
    auto = [b["short"] for b in ctx.bars if b.get("auto_fill") and not b["count"]]
    filled = [b for b in ctx.bars if b["count"]]
    if op in BAR_BUTTON_OPS:
        if auto and op == "add_button":
            out.append("панели с автозаполнением: " + _list(auto) + " — стандартные кнопки платформа ставит сама, `add_button` кладёт в файл свою; расположение своей кнопки среди стандартных досье не описывает")
        elif auto:
            out.append("кнопок в файле нет, их ставит платформа («автозаполнение»): " + _list(auto) + " — стандартную кнопку убрать или изменить нельзя")
        if filled:
            out.append("кнопки в файле: " + "; ".join(f"«{b['short']}» — " + _list([x["name"] for x in b["buttons"] if x["kind"] != "separator"]) for b in filled[:3]))
        by_code = ctx.coded_props(("видимость", "доступность"), part="кнопка")
        if by_code:
            out.append("код модуля прячет, удаляет или добавляет кнопки у " + _list(by_code) + ": картина на экране может отличаться от файла")
    elif op == "set_action_source":
        out.append("табличные поля формы: " + _list([t["short"] for t in ctx.tables]) if ctx.tables else "табличных полей на форме нет")
    elif op == "set_button_shortcut":
        buttons = [r["short"] for r in ctx.rows("Button")]
        if buttons:
            out.append("кнопки формы (`element`): " + _list(buttons))
    return out


def _table_notes(ctx, op):
    """Оговорки операций над колонками: по строке на группу таблиц одного вида с одинаковым текстом."""
    groups = collections.OrderedDict()
    for table in ctx.tables:
        names = [c["name"] for c in table["columns"] if c.get("name")]
        if not names:
            tail = ": колонок нет" + ("; копировать нечего, колонку берут из образцов (`template`)" if op == "add_column" else "")
        elif op == "add_column":
            if table["kind"] == "табличная часть":
                tail = ": данные колонки — путь по метаданным (`data=\"Объект.ТЧ.Реквизит\"`, нужны выгрузка и привязка таблицы к табличной части); без `data` данные не заданы"
            elif table["kind"] == "список":
                tail = ": колонка списка — `data=\"<реквизит формы>.<колонка>\"` (стандартная колонка или реквизит объекта)"
            elif table["kind"] == "список значений":
                tail = ": колонки списка значений заводятся особой веткой операции"
            else:
                tail = ": колонка копирует соседнюю (`donor`), данные — одноимённая колонка таблицы значений"
        elif op == "remove_column":
            used = sorted({r["sub"] for r in ctx.refs.get("rows", []) if r["part"] == "колонка" and r["short"] == table["short"]})
            tail = "; названы в коде: " + _list(used) if used else ""
        else:
            others = [f"{c['name']}: {c['control']}" for c in table["columns"] if c.get("control")]
            tail = "; " + ("вложенный элемент не поле ввода у " + _list(others) if others else "у всех вложенный элемент — поле ввода")
        groups.setdefault((table["kind"], tail), []).append(table["short"])
    return [f"{_list(shorts)} — {kind}{tail}" for (kind, tail), shorts in groups.items()]


# ── Частые правки ──

def _apply(doc, ops, module_text):
    """Выполнить `ops` на копии формы: `(отчёт, None)` либо `(None, причина отказа)`."""
    work = copy.deepcopy(doc)
    bsl = module_text.encode("utf-8") if isinstance(module_text, str) else (bytes(module_text) if module_text is not None else b"")
    try:
        _doc, _bsl, log = ed_ops.apply(work, ops, bsl=bsl)
    except (EditError, ValueError, KeyError, TypeError) as why:
        return None, str(why)
    return "\n".join(log), None


TRIES = 4       # попыток подобрать выполнимый пример одной задачи


def _first_ok(ctx, tries):
    """Первая из попыток `(описание, ops)`, которую редактор выполняет без отказа: `(описание, ops, отчёт)` либо `None`."""
    for words, ops in tries[:TRIES]:
        report, why = _apply(ctx.doc, ops, ctx.module_text)
        if why is None:
            return words, ops, report
    return None


def _examples(ctx):
    """Частые правки: `[{task, op, doc, words, ops, report, why}]`; `ops` пуст, если на этой форме выполнимого примера не нашлось (`why` — почему)."""
    out = []
    boxes = {r["element"]: [r["x"], r["y"], r["width"], r["height"]] for r in ctx.elements if r.get("x") is not None}

    def add(task, names, doc, found, why, warn=None):
        if found is None:
            out.append({"task": task, "op": names, "doc": doc, "words": None, "ops": [], "report": None, "why": why, "warn": warn})
        else:
            words, ops, report = found
            out.append({"task": task, "op": names, "doc": doc, "words": words, "ops": ops, "report": _short(report, 220), "why": None, "warn": warn})

    unique = [r for r in ctx.elements if r["short"] in ctx.unique and r["element"] == r["short"] and r["element"] in boxes]
    fields = [r for r in unique if r["type"] == "TextBox"]
    tries = []
    for dx, dy, dw, label in ((0, 0, -16, "уже на 16 px"), (0, 0, 16, "шире на 16 px"), (0, 8, 0, "ниже на 8 px")):
        for row in fields[:2]:
            x, y, w, h = boxes[row["element"]]
            tries.append((f"поле «{row['short']}» {label}", [{"op": "move_element", "name": row["short"], "box": [x + dx, y + dy, w + dw, h]}]))
    add("Место и размер элемента", ["move_element"], D_RULES, _first_ok(ctx, tries), "на форме нет поля ввода с однозначным именем либо проверка раскладки отвергает сдвиг", MOVE_WARN)
    standing = set()
    for node in ctx.behavior.get("nodes", []):
        standing |= set(node["width"].get("stands", []))
    tries = [(f"поле «{r['short']}» растягивается по ширине вместе с окном", [{"op": "set_anchors", "element": r["short"], "h": "stretch"}])
             for r in sorted(fields, key=lambda r: r["short"] not in standing)]
    add("Растяжение при изменении окна (привязки)", ["set_anchors"], D_ANCHORS, _first_ok(ctx, tries), "на форме нет поля ввода с однозначным именем")
    captioned = [r for r in unique if r["type"] in ("Label", "CheckBox", "Button", "GroupBox") and r.get("caption")]
    tries = [(f"подпись «{r['short']}» → «Новая подпись:»", [{"op": "set_caption", "element": r["short"], "text": "Новая подпись:"}]) for r in captioned]
    add("Подпись", ["set_caption"], D_RULES, _first_ok(ctx, tries), "на форме нет элемента с подписью и однозначным именем")
    styled = [r for r in unique if r["type"] in ("Label", "CheckBox", "TextBox")]
    tries = [(f"элемент «{r['short']}» — полужирный", [{"op": "set_font", "element": r["short"], "bold": True}]) for r in styled]
    add("Шрифт", ["set_font"], D_FONT, _first_ok(ctx, tries), "на форме нет подходящего элемента")
    focus = [r for r in unique if r["type"] in ("TextBox", "CheckBox", "ComboBox", "Button", "TableBox")]
    tries = [("порядок обхода (Tab) формы — по порядку чтения структуры", [{"op": "set_tab_order", "by": "reading"}]),
             ("порядок обхода (Tab) формы — по порядку чтения структуры, автопорядок обхода формы выключен",
              [{"op": "set_property", "form": True, "name": "auto_tab_order", "value": False}, {"op": "set_tab_order", "by": "reading"}])]
    for row in focus:
        tab = [{"op": "set_property", "element": row["short"], "name": "tab_order", "value": 1}]
        tries.append((f"элемент «{row['short']}» — первый в порядке обхода (Tab)", tab))
        tries.append((f"элемент «{row['short']}» — первый в порядке обхода (Tab), автопорядок обхода формы выключен",
                      [{"op": "set_property", "form": True, "name": "auto_tab_order", "value": False}] + tab))
    add("Порядок обхода", ["set_tab_order", "set_property"], D_RULES, _first_ok(ctx, tries),
        "на форме нет элемента с однозначным именем, которому можно задать порядок обхода (при АвтоПорядокОбхода панели операция отказывает)")
    tries = []
    for row in reversed(fields):
        tries.append((f"новое поле ввода «НовоеПоле» ниже поля «{row['short']}»", [{"op": "add_element", "template": "TextBox", "name": "НовоеПоле", "after": row["short"]}]))
        tries.append((f"новое поле ввода «НовоеПоле» ниже поля «{row['short']}», форма выше на шаг (`grow`)",
                      [{"op": "add_element", "template": "TextBox", "name": "НовоеПоле", "after": row["short"], "grow": True}]))
    add("Новое поле рядом с существующим", ["add_element"], D_RULES, _first_ok(ctx, tries),
        "нет поля ввода, рядом с которым можно поставить новое, либо место не нашлось")
    tries = []
    for table in ctx.tables:
        columns = [c["name"] for c in table["columns"] if c.get("name")]
        if columns and table["short"] in ctx.unique and table["kind"] != "список значений":
            tries.append((f"в таблицу «{table['short']}» — колонка «НоваяКолонка» по образцу колонки «{columns[-1]}»",
                          [{"op": "add_column", "table": table["short"], "name": "НоваяКолонка", "header": "Новая колонка", "donor": columns[-1]}]))
    add("Колонка таблицы", ["add_column"], D_COLUMNS, _first_ok(ctx, tries), "на форме нет табличного поля с колонками, для которого пример выполнился бы")
    tries = [(f"в панель «{panel}» — страница «НоваяСтраница»", [{"op": "add_page", "panel": panel, "name": "НоваяСтраница", "caption": "Новая страница"}])
             for panel, _pages in _page_groups(ctx) if panel in ctx.unique]
    add("Страница панели", ["add_page"], D_RULES, _first_ok(ctx, tries), "на форме нет панели со страницами")
    tries = [(f"панель «{r['short']}» сворачивается кнопкой «{ed_collapse.BUTTON_TEXT}» верхней панели формы", [{"op": "add_collapsible_panel", "panel": r["short"]}])
             for r in unique if r["type"] == "Panel"]
    if tries:       # пример только у формы с панелью: у остальных строки «без готового примера» стали бы шумом в каждом досье
        add("Сворачиваемая панель", ["add_collapsible_panel"], D_MODULE, _first_ok(ctx, tries),
            "у панелей формы нет соседа рядом, а пример нужен с соседом, и командной панели формы с набором кнопок")
    tries = []
    for row in fields:
        procedure = f"{row['short']}ПриИзменении"
        tries.append((f"поле «{row['short']}»: событие «ПриИзменении» → процедура «{procedure}»",
                      [{"op": "append_procedure", "name": procedure, "params": ["Элемент"], "body": ["// действия при изменении поля"]},
                       {"op": "set_event", "element": row["short"], "event": "OnChange", "procedure": procedure}]))
    add("Обработчик события", ["append_procedure", "set_event"], D_MODULE, _first_ok(ctx, tries), "на форме нет поля ввода с однозначным именем")
    keys = {word: key for key, word in ctx.event_words.items()}
    tries = [(f"у элемента «{ctx.short(h['element'])}» снять обработчик события «{ctx.event_words.get(h['event'], h['event'])}» (процедура остаётся в модуле)",
              [{"op": "set_event", "element": ctx.short(h["element"]), "event": keys.get(h["event"], h["event"]), "remove": True}])
             for h in ctx.module.get("handlers", []) if h.get("owner") == "element" and h.get("found") and ctx.short(h["element"]) in ctx.unique]
    add("Снять обработчик события", ["set_event"], D_RULES, _first_ok(ctx, tries), "в файле нет обработчика события элемента с однозначным именем")
    return out


# ── Сборка раздела ──

def _table_rows(ctx):
    """Строки таблицы `OPS` с оговорками этой формы: `{form, module, any, kinds}`; у строки вида — `kinds` (виды формы из `OPS`) и `elements`."""
    def row(name, **extra):
        op = OPS[name]
        return {"op": name, "changes": op.changes, "doc": op.doc, "notes": _notes(ctx, name), **extra}

    order = list(ctx.by_kind)
    kind_rows = []
    for name, op in OPS.items():
        present = [k for k in order if k in op.kinds]
        if present and ANY not in op.kinds:
            kind_rows.append((order.index(present[0]), name, present))
    kind_rows.sort(key=lambda item: item[0])      # устойчиво: внутри вида — порядок `OPS`
    return {"form": [row(n) for n, o in OPS.items() if FORM in o.kinds],
            "module": [row(n) for n, o in OPS.items() if MODULE in o.kinds and FORM not in o.kinds],
            "any": [row(n) for n, o in OPS.items() if ANY in o.kinds],
            "kinds": [row(n, kinds=present, elements={k: [r["short"] for r in ctx.rows(k)] for k in present}) for _i, n, present in kind_rows]}


def build(doc, form, structure, names, elements, tables, bars, module, module_text, head, behavior, event_words):
    """Раздел «Что и как можно менять»: словарь `editing` для `brief.json`. Аргументы — то, что `brief` уже собрал к этому месту."""
    ctx = _Ctx(doc, form, structure, names, elements, tables, bars, module, module_text, head, behavior, event_words)
    constraints, clear = _constraints(ctx)
    ctx.refs = _code_names(ctx)
    return {"constraints": constraints, "constraints_clear": clear, "code": ctx.refs, "ops": _table_rows(ctx), "examples": _examples(ctx),
            "verify": [{"what": what, "how": how} for what, how in VERIFY]}


# ── brief.md ──

def md_lines(editing):
    """Строки раздела 9 `brief.md`."""
    lines = ["## 9. Что и как можно менять", "",
             "Из-за чего операции редактора (`frm_json.py edit --ops`) откажут на этой форме и как проверить правку. Раздел — данные о возможностях, "
             "что менять, он не говорит. Перечень операций, их ключи и отказы — в `docs/edit-rules.md` и в документах операций; операция вне проверенного отказывает "
             "словами и называет причину, `unverified` снимает часть отказов.", "", ed_scope.RULE_LINE, ""]
    lines += _md_constraints(editing)
    lines += _md_code(editing["code"])
    lines += _md_examples(editing["examples"])
    lines += ["**Как проверить правку.**", ""]
    lines += [f"- {v['what']}: {v['how']}" for v in editing["verify"]]
    lines.append("")
    return lines


def _cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def _md_constraints(editing):
    lines = ["**Ограничения формы** (из-за чего операции откажут или поведут себя иначе).", ""]
    if editing["constraints"]:
        for c in editing["constraints"]:
            lines.append(f"- **{c['title']}.** Операции: " + ", ".join(f"`{o}`" for o in c["ops"]) + ".")
            lines += [f"  - {point}" for point in c["points"]]
        lines.append("")
    else:
        lines += ["Ограничений от самой формы нет.", ""]
    if editing["constraints_clear"]:
        lines += ["Проверено, ограничений нет: " + "; ".join(editing["constraints_clear"]) + ".", ""]
    return lines


def _md_code(code):
    lines = ["**Имена, на которые опирается код модуля** (что сломают `rename_element`, `remove_element`, `remove_button`, `remove_column`, `remove_page`).", ""]
    if not code["present"]:
        return lines + ["Модуль формы не получен: какие имена элементов он называет, неизвестно; ограничения от кода не оценить, элементы с обработчиками переименовывать и удалять осторожно.", ""]
    rows = code["rows"]
    if rows:
        lines += ["| Имя | Вид | Как названо в коде | Где (процедуры; число обращений) | Что сломает |", "|---|---|---|---|---|"]
        for r in rows[:CODE_ROWS]:
            name = f"{r['short']}.{r['part']} {r['sub']}" if r["part"] else r["short"]
            if r["part"] and r["in_file"] is False:
                name += " (в файле такой нет)"
            how = ", ".join(r["how"]) + (f"; члены: {', '.join(r['members'])}" if r["members"] else "")
            where = (", ".join(r["procedures"]) if r["procedures"] else "вне процедур") + f" ({r['uses']})"
            lines.append(f"| {_cell(name)} | {_cell(r['type'] or '—')} | {_cell(how)} | {_cell(where)} | {', '.join('`' + o + '`' for o in r['breaks'])} |")
        if len(rows) > CODE_ROWS:
            lines.append(f"| … | | | | и ещё {len(rows) - CODE_ROWS} |")
        lines.append("")
    else:
        lines += ["Элементы формы по имени в тексте модуля не названы: переименование и удаление элементов код не ломает.", ""]
    handlers = code["handlers"]
    if handlers:
        shown = "; ".join(f"{h['element']}.{h['event']} → {h['procedure']}" for h in handlers[:HANDLERS_LISTED])
        lines += [f"Обработчики событий элементов ({len(handlers)}): {shown}" + (f"; и ещё {len(handlers) - HANDLERS_LISTED}" if len(handlers) > HANDLERS_LISTED else "")
                  + ". `rename_element` их не нарушает (имя процедуры хранится в элементе); `remove_element` оставляет процедуру в модуле без элемента.", ""]
    lines += ["Динамические имена и обращения не по имени элемента перечень не находит: он называет то, что нашлось в тексте"
              + (f" (обращения к именам, которых на форме нет, — {_missing_list(code['unknown_names'])}; подробно — «Факты для оценки», раздел 7)." if code.get("unknown") else "."), ""]
    if code.get("unknown"):
        lines += [CODE_BY_HAND, ""]
    return lines


def _missing_list(rows):
    """Имена, которых на форме нет, с процедурой и строкой: `«Имя» (процедура, строка N)`."""
    return ", ".join(f"«{r['name']}» ({r['procedure'] or 'вне процедур'}, строка {r['line']})" for r in rows[:LISTED * 2]) + (
        f" и ещё {len(rows) - LISTED * 2}" if len(rows) > LISTED * 2 else "")


def _md_ops(table):
    lines = ["**Операции по видам элементов этой формы** (оговорки — по данным формы; полное описание — в документе операции).", ""]
    groups = [("Форма в целом", table["form"], False), (KIND_LABEL[MODULE], table["module"], False), (KIND_LABEL[ANY] + " (все виды)", table["any"], False),
              ("По видам элементов", table["kinds"], True)]
    for title, rows, by_kind in groups:
        if not rows:
            continue
        head = "| Операция | Виды формы | Что меняет | Оговорки на этой форме | Документ |" if by_kind else "| Операция | Что меняет | Оговорки на этой форме | Документ |"
        lines += [f"*{title}*", "", head, "|---|---|---|---|---|" if by_kind else "|---|---|---|---|"]
        for r in _merged(rows):
            marks = list(dict.fromkeys(m for m in (ed_scope.rebuild_note(o) for o in r["ops"]) if m))
            notes = _cell("; ".join(r["notes"] + marks) or "—")
            ops = ", ".join(f"`{o}`" for o in r["ops"])
            if by_kind:
                kinds = "; ".join(f"{k}: {_list(r['elements'][k], 4)}" for k in r["kinds"])
                lines.append(f"| {ops} | {_cell(kinds)} | {_cell(r['changes'])} | {notes} | `{r['doc']}` |")
            else:
                lines.append(f"| {ops} | {_cell(r['changes'])} | {notes} | `{r['doc']}` |")
        lines.append("")
    return lines


def _merged(rows):
    """Строки таблицы для `brief.md`: подряд идущие операции с одинаковыми видами, непустыми оговорками и документом — одной строкой."""
    out = []
    for r in rows:
        last = out[-1] if out else None
        if last and r["notes"] and last["notes"] == r["notes"] and last["doc"] == r["doc"] and last.get("kinds") == r.get("kinds"):
            last["ops"].append(r["op"])
            last["changes"] += "; " + r["changes"]
        else:
            out.append({**r, "ops": [r["op"]]})
    return out


def _md_examples(examples):
    lines = ["**Частые правки и как их сделать.** Пример — содержимое `ops.json` (список операций, выполняются подряд); каждый выполнен редактором на копии этой формы без отказа.", ""]
    skipped = []
    for e in examples:
        head = f"- *{e['task']}*: `{'`, `'.join(e['op'])}` (`{e['doc']}`)."
        if e["ops"]:
            lines += [head + f" Пример — {e['words']}:", "", "  ```json"] + ["  " + line for line in _json(e["ops"]).splitlines()] + ["  ```"]
            if e.get("warn"):
                lines.append(f"  Осторожно: {e['warn']}.")
            if ed_scope.whole_form_ops(e["ops"]):
                lines.append("  Пересборка дизайна — только по явной просьбе пользователя: пример меняет форму целиком.")
        else:
            skipped.append(e["task"])
    if skipped:
        lines.append("- Без готового примера на этой форме: " + "; ".join(skipped) + " (операции — в `docs/edit-rules.md`).")
    lines.append("")
    return lines


def _json(ops):
    """Перечень операций: по операции на строке, ключи в порядке записи."""
    return "[\n" + ",\n".join("  " + json.dumps(op, ensure_ascii=False) for op in ops) + "\n]"
