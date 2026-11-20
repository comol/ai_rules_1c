"""Записи разбора кода, который сделала модель (`code-notes.json`): проверка и перевод в строки перечня «что код меняет».

Код формы читает модель по `docs/brief-code.md`, а не шаблоны навыка: навык проверяет, что записи ссылаются на то, что есть на форме и в модуле, и только
потом пускает их в досье и на рисунок. Запись, не прошедшая проверку, в досье не попадает — она названа с причиной в разделе «Разбор кода» и в stderr.

Схема файла — `{"notes": [запись, …]}`; запись — замкнутый словарь из пятнадцати ключей (лишний ключ — отказ записи):

* `kind` — `open_refused`, `visibility`, `enabled`, `read_only`, `title`, `current_page`, `current_element`, `created`, `removed`, `geometry`,
  `desktop_mode`, `collapse`, `checked`, `value`, `appearance`, `list_content`, `missing`, `on_event`, `other`;
* `target` — `{"form": true}`, `{"element": имя}`, `{"page": [панель, страница]}` (у страниц формы панель — пустая строка), `{"column": [таблица, колонка]}`,
  `{"button": [панель, кнопка]}` либо, если кнопка лежит в меню другой кнопки, `{"button": [панель, подменю, …, кнопка]}` (путь по именам кнопок файла; у `created` последнее имя — создаваемое);
  у `value` — `{"element": поле с привязкой данных}`; у `missing` — `{"name": имя, как в коде}`; у `visibility`, `enabled`, `read_only` — список целей (словари или короткие имена элементов строками) с одним значением, условием и цитатой: запись
  разворачивается в принятые записи по цели с общим `index`;
* `value` — что код ставит (`Ложь`, `Истина`, текст заголовка, имя страницы, выражение; у `list_content` из литералов `СписокВыбора.Добавить("…")` не нужно); `condition` — условие кода
  законченной фразой, пусто — безусловно (навык «если», «при» и «зависит от» не приклеивает); `message` — сообщение при отказе в открытии, пустая строка у молчаливого отказа (обязательно и только у `open_refused`);
* `default` и `exclusive_group` — необязательны. Группы вариантов одного свойства одной цели в одной процедуре собирает навык (`_auto_groups`), `default: true` называет вариант, который
  при открытии видит пользователь (без него вариант «как в файле»); `exclusive_group` остаётся для вариантов РАЗНЫХ элементов на одном месте;
* `lines` — `[от, до]` строки модуля: внутри одной процедуры либо внутри тела модуля (код вне процедур), `quote` — точная цитата из этого диапазона (у всех видов, и у `other`),
  `why` — причина (для `other`: что код делает и почему это не записано иначе);
* `source` — `{"file": путь от выгрузки, "lines": [от, до], "quote": …}`: эффект стоит в другом модуле (общий модуль, модуль объекта), а в модуле формы — строка вызова (`lines`, `quote`
  записи). Слово действия ищется в цитате записи и в `source`, имя цели — там же; без выгрузки (`--config`) запись с `source` отклоняется;
* `alias` — `{"lines": [от, до], "quote": …}`: строка, где псевдоним получил элемент в другой процедуре;
* `name_expr` — у `created`: выражение, которым код вычисляет имя (имя в цели пусто);
* `event`, `effects` — только у `on_event`.

Ключи прежних записей принимаются: `certainty`, `depends_on`, `form_work` и `category` (у `default`) отбрасываются с одним предупреждением на файл — рисунок применяет литерал без условия, форма
делает сама то, что граф вызовов относит к таймеру и действию, категорию умолчания определяет навык; `targets` и `alias_lines`/`alias_quote` переводятся в `target`-список и `alias`.
Вид состояния (`visibility`, `enabled`, …) в процедуре, до которой доходят только действия, отклоняется с подсказкой `on_event`: состояние записывают только для открытия.

Запись должна быть привязана к коду, а не к форме слов: цитата называет цель (последнее звено имени: элемент, страница, колонка, кнопка; у `created` — создаваемое имя; обращение по индексу
`Колонки[0]`, `Страницы[Инд]` называет цель по порядку в файле) и слово свойства или действия по виду записи (`PROPERTY_WORDS`: `Видимость`, `Доступность`, `Отказ`, …); слово ищется
отдельным словом, без учёта регистра (`глУстЗаголовок…` не даёт слова «Заголовок»); у оформления в `ПриВыводеСтроки` и `ПриПолученииДанных` слово не нужно; цитата может занимать несколько подряд
идущих строк диапазона, пробелы и табуляции в ней сравниваются схлопнутыми. Имена в `affects` записей `on_event` — только то, что есть на форме и в данных, или принятое `created`; путь
проверяется по всем звеньям.

`check` возвращает `(принятые, отклонённые)`; принятая запись несёт разрешённую цель (полные имена элементов формы). `effect_rows` переводит принятые записи
в строки `module_effects.group` (строка несёт `order` — ключ порядка выполнения из `Targets.order_key`: тело модуля, `ПередОткрытием`, `ПриОткрытии`, `ОбновлениеОтображения`, прочие процедуры; вызванная процедура — в месте вызова;
`module_effects.group` упорядочивает по нему записи одного свойства одного элемента, при равенстве — по файлу записей; последняя безусловная запись свойства решает); `form_rows` — в строки о самой форме
(режим рабочего стола, положение и размер, заголовок).
"""
import json
import pathlib
import re

from . import handler_defaults as hd
from .codefacts import COLLECTION_METHODS
from . import module_effects as module
from . import modulescan as scan
from .modulescan import SHOWN, shorten

KINDS = ("open_refused", "visibility", "enabled", "read_only", "title", "current_page", "current_element", "created", "removed", "geometry",
         "desktop_mode", "collapse", "checked", "value", "appearance", "list_content", "missing", "on_event", "other", "default")
WHAT = ("value", "recalc", "fill", "visibility", "enabled", "read_only", "checked", "collapse", "filter", "current", "open_form", "message", "refuse", "write", "other", "none")
WHAT_WORDS = {"value": "меняет значение", "recalc": "пересчитывает", "fill": "заполняет", "visibility": "меняет видимость", "enabled": "меняет доступность",
              "read_only": "меняет «только просмотр»", "checked": "меняет пометку кнопки", "collapse": "сворачивает или разворачивает панель",
              "filter": "меняет отбор или порядок", "current": "меняет текущую строку или страницу", "open_form": "открывает форму", "message": "сообщает",
              "refuse": "отказывает", "write": "записывает или проводит", "other": "прочее"}
NO_EFFECT = "none"          # обработчик разобран, на экране он ничего не меняет: запись считается разобранным обработчиком, в обзор и связи полей не идёт
MIN_QUOTE = 3         # цитата короче трёх знаков («=», «Р») к коду не привязывает: совпадёт с чем угодно
EFFECT_KEYS = frozenset({"what", "affects", "text", "condition"})
COLLAPSE_MODES = ("Нет", "Верх", "Низ", "Лево", "Право")
TARGET_KEYS = ("form", "element", "page", "column", "button", "name")
NOTE_KEYS = frozenset({"kind", "target", "value", "condition", "message", "exclusive_group", "default", "lines", "quote", "why", "event", "effects", "source", "name_expr", "alias"})
# Ключи прежних записей (P1–P4). Записи с ними собираются: ключ либо переводится в нынешний (`targets` → `target`-список, `alias_lines`/`alias_quote` → `alias`), либо отбрасывается
# с одним предупреждением на файл (`DROPPED_KEYS`: навык определяет это сам).
DROPPED_KEYS = ("certainty", "depends_on", "form_work", "category")
LEGACY_KEYS = frozenset({"targets", "alias_lines", "alias_quote"}) | frozenset(DROPPED_KEYS)
SOURCE_KEYS = frozenset({"file", "lines", "quote"})
SOURCE_KINDS = frozenset({"open_refused", "visibility", "enabled", "read_only", "title", "current_page", "current_element", "created", "removed", "geometry", "desktop_mode",
                          "collapse", "checked", "appearance", "list_content", "on_event"})     # виды со словом действия в цитате: его ищут в `source`; у `on_event` источник — процедура другого модуля, которую зовёт обработчик; `missing` и `other` source не имеют
ALIAS_KINDS = frozenset({"visibility", "enabled", "read_only", "title", "current_page", "current_element", "collapse", "desktop_mode", "geometry", "removed", "checked",
                         "appearance", "list_content"})      # виды, у которых имя цели обязано стоять в цитате: к ним применим псевдоним из другой процедуры
WAIT_CALL = re.compile(r'ПодключитьОбработчикОжидания\s*\(\s*"([^"]+)"', re.I)
WAIT_EVENT = "обработчик ожидания"         # событие процедуры, которую платформа вызывает по таймеру после `ПодключитьОбработчикОжидания("Имя", …)`: это не событие файла формы
GROUP_APPLIED = ("title", "current_page", "enabled", "read_only", "checked")
USER_EVENT_OWNERS = frozenset({"element", "column", "panel", "action"})       # события элементов, колонок и кнопок (в том числе созданных кодом: `action`) — по действию пользователя
ACTION_EVENT = "действие кнопки, созданной кодом"        # событие процедуры, которую код привязал к кнопке: `Новый Действие("Имя")`
VISUAL_KINDS = frozenset({"visibility", "enabled", "read_only", "title", "checked", "value", "current_page", "current_element", "collapse", "created", "removed", "geometry", "desktop_mode"})
# виды записей о том, что форма показывает при открытии: безусловными они бывают только там, где код выполняется при открытии (граф вызовов: `Targets.user_only`)
ROW_EVENTS = ("выводестроки", "полученииданных", "onrowoutput", "ondataget")          # события табличного поля, где оформление строк идёт параметром процедуры (`ОформлениеСтроки`, `ОформленияСтрок`)
CELL_TEXT = re.compile(r"\.\s*Ячейки\s*\.", re.I)          # `<Оформление>.Ячейки.<Колонка>.Текст`: текст ячейки строки, а не заголовок колонки
LIFE_ORDER = ("передоткрытием", "приоткрытии", "обновлениеотображения")
ORDER_STEPS = 20000      # шагов обхода графа вызовов на одну запись: у запутанного модуля путь короче полного, но не пустой
NAME_ONLY = re.compile(r"^[\wА-Яа-яЁё]+$")
TARGETS = {
    "open_refused": ("form",),
    "visibility": ("element", "page", "column", "button"),
    "enabled": ("form", "element", "column", "button"),
    "read_only": ("form", "element", "column"),
    "title": ("form", "element", "page", "column", "button"),
    "current_page": ("page",),
    "current_element": ("element",),
    "created": ("element", "page", "column", "button"),
    "removed": ("element", "page", "column", "button"),
    "geometry": ("form", "element"),
    "desktop_mode": ("form",),
    "collapse": ("element",),
    "checked": ("button",),
    "value": ("element",),
    "appearance": ("form", "element", "page", "column", "button"),
    "list_content": ("element", "column"),
    "missing": ("name",),
    "on_event": ("form", "element", "column", "button"),
    "other": TARGET_KEYS[:-1],
}
VALUE_REQUIRED = frozenset({"visibility", "enabled", "read_only", "title", "geometry", "desktop_mode", "value"})   # у остальных значение может быть пустым
# Слова, по которым цитата записи привязана к строке модуля: свойство или метод платформы, который запись описывает. Словарь замкнутый, у каждого вида причина: запись
# с цитатой без этого слова (`quote: "Видимость"` из чужой процедуры, `"Если"`, `"="`) к коду не привязана. Английские синонимы — только известные точно.
# Вид без слова (`created`, `on_event`, `other`) проверяется иначе: `created` — создаваемым именем, `on_event` — процедурой обработчика, `other` — только диапазоном строк.
PROPERTY_WORDS = {
    "open_refused": ("Отказ", "Закрыть", "Cancel", "Close"),        # отказ в открытии: `Отказ = Истина` или `Закрыть()`
    "visibility": ("Видимость", "Visible"),
    "enabled": ("Доступность", "Enabled"),
    "read_only": ("ТолькоПросмотр", "ReadOnly"),
    "title": ("Заголовок", "Текст", "Caption", "Text"),
    "current_page": ("ТекущаяСтраница",),
    "current_element": ("ТекущийЭлемент", "ТекущаяКолонка"),
    "collapse": ("Свертка",),
    "desktop_mode": ("РежимРабочегоСтола",),
    "geometry": ("Верх", "Лево", "Ширина", "Высота", "Привязка", "Привязки"),
    "removed": ("Удалить", "Очистить", "Delete", "Clear"),          # `Кнопки.Удалить`, `Кнопки.Очистить()`, `Колонки.Удалить`
    "checked": ("Пометка", "Check"),
    "appearance": ("ЦветФона", "ЦветТекста", "ЦветФонаПоля", "ЦветТекстаПоля", "ЦветФонаШапки", "ЦветТекстаШапки", "Шрифт", "Картинка", "КартинкаШапки", "ОформлениеСтроки",
                   "Подсказка", "ТекстПодвала", "УстановитьТекст", "Рамка", "BackColor", "TextColor", "Font", "Picture"),
    "list_content": ("СписокВыбора", "СписокЗначений", "ChoiceList", "ValueList"),
}
# Корни обращения в `affects` (`Объект.Реквизит`, `ЭлементыФормы.Таблица.Колонки.Цена`): не имена данных, а слова пути.
PATH_WORDS = frozenset({"объект", "этаформа", "этотобъект", "элементыформы", "колонки", "кнопки", "страницы", "текущаястрока"})
HOLDER_TYPES = {"page": "Panel", "column": "TableBox", "button": "CommandBar"}
HOLDER_WORDS = {"page": "панель", "column": "табличное поле", "button": "командная панель"}
BOOL_PROPS = {"visibility": "видимость", "enabled": "доступность", "read_only": "только просмотр", "checked": "пометка"}
FALSE_WORDS, TRUE_WORDS = ("ложь", "false"), ("истина", "true")
PART_WORDS = {"page": "страница ", "column": "колонка ", "button": "кнопка "}
CLEAR_SUBMENU_PROP = "очищает подменю"
NAMELESS_WORDS = {"button": "кнопка", "page": "страница", "column": "колонка", "element": "элемент"}
REMOVE_PROPS = {"element": "убирает элемент", "page": "убирает страницу", "column": "убирает колонку", "button": "удаляет кнопку"}
CREATE_PROPS = {"element": "создаёт элемент", "page": "создаёт страницу", "column": "создаёт колонку", "button": "добавляет кнопку"}
GEOMETRY_PROP = "положение и размер"
GROUP_KINDS = ("visibility", "created", "collapse", "title", "current_page", "enabled", "read_only", "appearance", "checked")
FORM_KINDS = {"desktop_mode": module.DESKTOP_MODE, "geometry": GEOMETRY_PROP, "enabled": "доступность формы", "read_only": "только просмотр формы",
              "title": "заголовок формы"}
CLEAR_PROP = "очищает все кнопки"
CLEAR_WORDS = "все кнопки"
EMPTY_TEMPLATE = {"notes": []}
LIFE_RANK = {"передоткрытием": 1, "приоткрытии": 2, "обновлениеотображения": 3}      # порядок событий жизни формы (`docs/brief-code.md`, «Порядок жизни обычной формы»)
NOT_ROWS = frozenset({"open_refused", "other", "on_event", "missing", "appearance", "list_content"})      # записи, которые перечня «что код меняет у элементов» не касаются


class NotesError(ValueError):
    """Файл записей разобрать нельзя целиком: не JSON, нет `notes`."""


def read(path):
    """Содержимое файла записей: список записей. Не JSON или не `{"notes": [...]}` — `NotesError` со словами."""
    try:
        with open(path, encoding="utf-8-sig") as handle:
            data = json.loads(handle.read(), strict=False)      # табуляция и перевод строки внутри строки JSON (цитата из кода) — не ошибка
    except OSError as why:
        raise NotesError(f"файл разбора кода «{path}» не читается: {why.strerror}") from why
    except ValueError as why:
        raise NotesError(f"файл разбора кода «{path}» — не JSON: {why}") from why
    if not isinstance(data, dict) or not isinstance(data.get("notes"), list):
        raise NotesError(f"файл разбора кода «{path}»: нужен объект {{\"notes\": [записи]}}")
    return data["notes"]


class Targets:
    """Что есть на форме и в модуле: имена элементов, страниц, колонок, кнопок и число строк модуля — то, на что записи вправе ссылаться."""

    def __init__(self, names, pages, tables, bars, module_text, handlers=None, known_names=(), config_dir=None, object_module=None, table_names=(), field_data=None):
        self.names = names
        self.field_data = field_data          # `{полное имя элемента: (вид привязки, имя данных)}` полей с привязкой (`form`, `object`); `None` — привязки не читались
        self.handlers = handlers
        self.config_dir = pathlib.Path(config_dir) if config_dir is not None else None
        self.object_module = object_module          # путь к модулю объекта формы в выгрузке: вызовы его методов и тело читает задание, признаки частности ищутся и в нём
        self._mapping = None
        self._foreign = {}
        self._chains = {}
        self._inputs = None
        self.created = set()          # `(панель, (имя, …))` кнопок, которые заводит принятая запись `created`: путь через созданное подменю допустим
        self.default_notes = []       # принятые записи `default` (`check`): `{index, handlers, category}`
        self.data_names = {n.casefold() for n in known_names}          # реквизиты формы и объекта, их табличные части и колонки
        self._sources = {}
        self._proc_ranges = None
        self._graph = None
        self._scanned = None
        self._waits = None
        self._params = None
        self._proc_names = {}
        self._words = None
        self._modules = None
        self.case_notes = []          # имена в записи, написанные не так, как на форме (регистр): запись принимается, досье называет расхождение
        self.known = {n.casefold() for n in known_names}
        self.by_label = module.label_map(names)
        self.pages = {}
        for (panel, _at), name in pages.items():
            if name:
                self.pages.setdefault(panel, set()).add(name.casefold())
        self.columns = {t["element"]: {(c["name"] or "").casefold() for c in t["columns"] if c.get("name")} for t in tables}
        # порядок в файле: по нему код обращается по индексу (`Колонки[0]`, `Страницы[Инд]`, `Кнопки[0]`)
        self.column_order = {t["element"]: [(c.get("name") or "").casefold() for c in t["columns"]] for t in tables}
        self.page_order = {}
        for (panel, _at), name in sorted(pages.items(), key=lambda kv: (kv[0][0] or "", kv[0][1])):
            self.page_order.setdefault(panel, []).append((name or "").casefold())
        self.button_order = {bar["element"]: [(b.get("name") or "").casefold() for b in bar["buttons"]] for bar in bars}
        self.dropped_now = set()          # ключи прежних записей, отброшенные при проверке текущей записи (`legacy`)
        self.dropped = {}                 # `{ключ: [номера записей]}` за всю проверку: одно предупреждение на файл (`warnings`)
        self.buttons = {}
        self.menus = {bar["element"]: bar["buttons"] for bar in bars}      # дерево кнопок панели: `{name, children}` — для пути до меню в цели `button`
        for bar in bars:
            found = self.buttons.setdefault(bar["element"], set())

            def walk(items):
                for button in items:
                    if button.get("name"):
                        found.add(button["name"].casefold())
                    walk(button.get("children") or [])
            walk(bar["buttons"])
        text = module_text.decode("utf-8", errors="replace") if isinstance(module_text, (bytes, bytearray)) else module_text
        self.lines = (text or "").lstrip("﻿").splitlines()
        self.module_text = text
        self._reach = None
        self._segments = None
        self.fields = {item.label().casefold() for item in names.item_of.values()}       # то, что на форме видно полем: элементы, колонки, кнопки (и созданное принятым `created`)
        self.page_names = {name for found in self.pages.values() for name in found}
        self.known |= self.page_names              # `affects` вправе назвать страницу панели
        for found in self.columns.values():
            self.known |= found
            self.fields |= found
        for found in self.buttons.values():
            self.fields |= found
        self.known |= self.fields
        self.table_names = {str(n).casefold() for n in table_names} | {t["element"].split("/")[-1].split(".")[-1].casefold() for t in tables} | {
            item.label().casefold() for item in names.item_of.values() if item.type == "TableBox"}

    def has_created(self, panel, path):
        """Кнопку по пути `path` (имена от панели вглубь) завела принятая запись `created`: она есть на форме только после работы кода."""
        return (panel, tuple(str(x).casefold() for x in path)) in self.created

    def menu_children(self, panel, path):
        """Кнопки меню, лежащего по пути `path` (имена кнопок файла без учёта регистра) в панели `panel`; `None` — такого пути в панели нет. Пустой путь — кнопки самой панели."""
        items = self.menus.get(panel)
        if items is None:
            return None
        for name in path:
            items = next((b.get("children") or [] for b in items if (b.get("name") or "").casefold() == name.casefold()), None)
            if items is None:
                return None
        return items

    def segments(self):
        """`[(первая строка, последняя строка)]` мест модуля, внутри которых лежит запись: каждая процедура и каждый кусок тела модуля — подряд идущие строки вне процедур
        (основная программа, `Перем` и код, выполняемый при создании формы до `ПередОткрытием`)."""
        if self._segments is None:
            self._segments = _segments_of(self.module_text or "", len(self.lines))
        return self._segments

    def scanned(self):
        """`modulescan.scan` модуля формы: `[(номер строки, masked, raw)]` — без комментариев, в `masked` ещё и без содержимого литералов."""
        if self._scanned is None:
            self._scanned = scan.scan(self.module_text or "")
        return self._scanned

    def conditions(self):
        """`modulescan.conditions` модуля формы: `{номер строки: условие}`."""
        if self.__dict__.get("_conds") is None:
            self._conds = scan.conditions(self.scanned())
        return self._conds

    def procedure_ranges(self):
        """`{имя процедуры без регистра: (первая строка, последняя строка)}` процедур модуля формы."""
        if self._proc_ranges is None:
            from . import purpose
            self._proc_ranges = {p["name"].casefold(): (p["line"], p["end"]) for p in purpose.parse_module(self.module_text or "")}
        return self._proc_ranges

    def wait_handlers(self):
        """Процедуры модуля, которые код подключает как обработчик ожидания (`ПодключитьОбработчикОжидания("Имя", …)`): платформа вызывает их по таймеру уже после открытия."""
        if self._waits is None:
            known = self.procedure_ranges()
            found = {}
            for _n, _m, raw in self.scanned():
                for hit in WAIT_CALL.finditer(raw):
                    name = hit.group(1).strip()
                    if name.casefold() in known:
                        found.setdefault(name.casefold(), name)
            self._waits = list(found.values())
        return self._waits

    def procedure_params(self, line):
        """Параметры (текст в скобках) процедуры модуля формы, в которой стоит строка; `None` — строка в теле модуля."""
        if self._params is None:
            from . import purpose
            parsed = purpose.parse_module(self.module_text or "")
            self._params = {p["name"].casefold(): p["params"] for p in parsed}
            self._proc_names = {p["name"].casefold(): p["name"] for p in parsed}
        owner = self.owner_of(line)
        return None if owner is None else self._params.get(owner, "")

    def procedure_name(self, line):
        """Имя процедуры модуля формы, в которой стоит строка, как оно написано в модуле."""
        self.procedure_params(line)
        owner = self.owner_of(line)
        return self._proc_names.get(owner, owner) if owner else None

    def mapping(self):
        """`codetask.module_map` модуля формы с выгрузкой и модулем объекта: граф вызовов, вызовы чужого кода и кнопки, которым код привязал процедуры (`Новый Действие("Имя")`)."""
        if self._mapping is None:
            from . import codetask, purpose
            self._mapping = codetask.module_map(purpose.parse_module(self.module_text or ""), self.handlers or [], self.module_text or "", self.config_dir, self.object_module,
                                                data_names=self.data_names, row_roots=self.row_roots(), field_names=self.bound_fields())
        return self._mapping

    def row_roots(self):
        """Процедуры, которые платформа вызывает при выводе строк и получении данных видимой при открытии таблицы (`ПриВыводеСтроки`, `ПриПолученииДанных` таблицы и её колонок): таблицу рисуют
        при открытии, и эти процедуры — часть открытия, а не только действия пользователя. Таблица, скрытая в файле, — нет."""
        out = []
        for row in self.handlers or []:
            if row["owner"] not in ("element", "column") or not any(word in (str(row["event"]) + str(row["code"])).casefold().replace(" ", "") for word in ROW_EVENTS):
                continue
            table = self.names.item_of.get(row["element"] if row["owner"] == "element" else row.get("table"))
            if table is not None and table.visible and row.get("procedure"):
                out.append(row["procedure"])
        return out

    def action_rows(self):
        """Процедуры, привязанные к кнопкам кодом (`Новый Действие("Имя")`): строки вида обработчика с `owner: "action"`."""
        return list(self.mapping().get("actions") or [])

    def handler_rows(self):
        """Обработчики файла формы и привязанные кодом: всё, что платформа вызывает по действию или событию."""
        return list(self.handlers or []) + self.action_rows()

    def graph(self):
        """Граф вызовов модуля формы: `{calls: {процедура без регистра: [(вызываемая, строка вызова)]}, body: [(вызываемая, строка)], life: [процедура], user: [(процедура, событие, где)]}`.
        Вызов — имя процедуры модуля в тексте строки (комментарии и литералы не считаются, `codetask.module_map`). При открытии идут тело модуля и события открытия:
        `ПередОткрытием`, `ПриОткрытии`, `ОбновлениеОтображения`, `ПослеВосстановленияЗначений`. Остальные события формы (`ОбработкаВыбора`, закрытие, запись…), события элементов,
        колонок и кнопок (в том числе созданных кодом) и таймер — по действию, не при открытии."""
        if self._graph is None:
            mapping = self.mapping()
            calls = {p["name"].casefold(): [(c["name"].casefold(), at) for c in p["calls"] for at in c["lines"]] for p in mapping["procedures"]}
            body = [(c["name"].casefold(), at) for piece in mapping["body"] for c in piece["calls"] for at in c["lines"]]
            known = set(calls)
            rows_at_open = {str(n).casefold() for n in self.row_roots()}
            life = [name for name in LIFE_ORDER if name in known]
            user = []
            for row in self.handler_rows():
                name = str(row["procedure"]).casefold()
                if name not in known:
                    continue
                if row["owner"] == "form":
                    if str(row["event"]).casefold() in hd.OPEN_EVENTS:
                        if name not in life:
                            life.append(name)
                    else:
                        user.append((name, row["event"], "форма"))
                elif row["owner"] in USER_EVENT_OWNERS:
                    if name in rows_at_open and name not in life:
                        life.append(name)          # вывод строк видимой таблицы — при открытии
                    else:
                        user.append((name, row["event"], row.get("element") or "форма"))
            for name in self.wait_handlers():
                if name.casefold() in known:
                    user.append((name.casefold(), WAIT_EVENT, "таймер"))
            self._graph = {"calls": calls, "body": body, "life": life, "user": user}
        return self._graph

    def reach(self, roots):
        """Процедуры, достижимые вызовами из `roots` (включая их самих)."""
        calls = self.graph()["calls"]
        seen, todo = set(), list(roots)
        while todo:
            name = todo.pop()
            if name in seen or name not in calls:
                continue
            seen.add(name)
            todo += [callee for callee, _at in calls[name]]
        return seen

    def _foreign_lines(self, path):
        """`modulescan.scan` чужого файла (общий модуль, модуль объекта) или `None`; результат хранится."""
        if path not in self._foreign:
            try:
                self._foreign[path] = scan.scan(pathlib.Path(path).read_text(encoding="utf-8-sig"))
            except (OSError, UnicodeDecodeError):
                self._foreign[path] = None
        return self._foreign[path]

    def _foreign_calls(self):
        """`[(файл, (первая строка, последняя строка), строки вызова в модуле формы, голый ли вызов)]` процедур общих модулей и модуля объекта, которые зовёт модуль формы (по `module_map`).
        Голый вызов — `Имя(…)` процедуры глобального общего модуля без формы и элемента в аргументах: параметры такой процедуры формой не считаются."""
        mapping = self.mapping()
        found, bare = {}, {}
        for group, is_bare in ((list(mapping["common"]) + list(mapping.get("form_calls") or []) + list(mapping.get("object_calls") or []), False), (list(mapping.get("bare_calls") or []), True)):
            for entry in group:
                if entry.get("file") and entry.get("range"):
                    key = (entry["file"], tuple(entry["range"]))
                    found.setdefault(key, []).extend(entry["lines"])
                    bare[key] = bare.get(key, True) and is_bare
        return [(file, span, lines, bare[(file, span)]) for (file, span), lines in found.items()]

    def foreign_scopes(self, reach, ranges):
        """Чужой код, который зовут процедуры `reach` модуля формы: `[(строки файла, [диапазоны процедур], имя модуля, {диапазон: [процедуры от вызванной до этой]}, голый ли вызов)]`. Вызванная процедура и
        все, до которых она доходит вызовами внутри своего файла (любой глубины, цикл обрывается)."""
        spans = [ranges[n] for n in reach if n in ranges]
        out = []
        for file, span, lines, bare in self._foreign_calls():
            if any(a <= n <= b for n in lines for a, b in spans):
                text = self._foreign_lines(file)
                if text is not None:
                    if (file, tuple(span)) not in self._chains:
                        self._chains[(file, tuple(span))] = foreign_chains(text, span)
                    chains = self._chains[(file, tuple(span))]
                    out.append((text, list(chains), _module_label(file), chains, bare))
        return out

    def visual_inputs(self):
        """Имена, от которых зависит вид формы (условия и выражения, внутри которых код меняет свойства элементов): в модуле формы и в чужом коде, который он зовёт."""
        if self._inputs is None:
            lines = self.scanned()
            roots = hd.roots_of(lines)
            for _name, params, _a, _b in scan.procedures_of(lines):
                roots |= {str(x).casefold() for x in params if x}
            found = hd.visual_inputs(lines, roots, None, True)
            for file, span, _lines, bare in self._foreign_calls():
                text = self._foreign_lines(file)
                if text is not None and not bare:
                    found |= hd.visual_inputs(text, roots | {"форма", "формаобъекта"} | hd._params_roots(text, [span]), [span])
            self._inputs = found
        return self._inputs

    def handler_procs(self):
        """`{имя без регистра: имя}` процедур-обработчиков, которые есть в модуле формы: события файла формы, действия кнопок, привязанные кодом, и таймеры."""
        ranges = self.procedure_ranges()
        out = {}
        for row in self.handler_rows():
            name = str(row.get("procedure") or "")
            if name.casefold() in ranges:
                out.setdefault(name.casefold(), name)
        for name in self.wait_handlers():
            if name.casefold() in ranges:
                out.setdefault(name.casefold(), name)
        return out

    def skill_defaults(self):
        """`{имя без регистра: категория}` обработчиков, которые навык отмечает умолчанием сам (`handler_defaults.SKILL_CATEGORIES`)."""
        ranges = self.procedure_ranges()
        opening = {str(r["procedure"]).casefold() for r in self.handler_rows() if r["owner"] == "form" and str(r["event"]).casefold() in hd.OPEN_EVENTS}
        out = {}
        for key in self.handler_procs():
            found = hd.skill_category(self.scanned(), ranges[key][0], ranges[key][1], key in opening or key in LIFE_ORDER)
            if found:
                out[key] = found
        return out

    def own_tables(self, key):
        """Таблицы формы (без регистра), чьи события вызывают процедуру: изменение строк такой таблицы обработчиком её колонки или самой таблицы — типовое (категория `rows`), не П5."""
        out = set()
        for row in self.handler_events().get(key, ()):
            for name in (row.get("table"), row.get("element") if row.get("owner") == "element" else None):
                if name:
                    out.add(str(name).split("/")[-1].split(".")[-1].casefold())
        return out & self.table_names

    def signs(self, name, category=None):
        """Признаки частности процедуры (`handler_defaults.find_signs`)."""
        return hd.find_signs(self, name, category)

    def handler_events(self):
        """`{имя процедуры без регистра: [строки обработчиков]}` — какими событиями вызывается процедура."""
        out = {}
        for row in self.handler_rows():
            out.setdefault(str(row.get("procedure") or "").casefold(), []).append(row)
        return out

    def owner_of(self, line):
        """Имя процедуры (без регистра), в которой стоит строка; `None` — тело модуля."""
        return next((name for name, (a, b) in self.procedure_ranges().items() if a <= line <= b), None)

    def at_opening(self, line):
        """Строка выполняется при открытии: она в теле модуля или в процедуре, достижимой из тела и событий жизни формы. `False` — только по действию пользователя либо
        процедуру никто не вызывает."""
        owner = self.owner_of(line)
        graph = self.graph()
        if owner is None:
            return True
        return owner in self.reach(graph["life"] + [c for c, _at in graph["body"]])

    def user_only(self, line):
        """`{event, where}`: процедура строки достижима только из обработчиков элементов, колонок и кнопок (не из тела и не из событий жизни формы); иначе `None`. События без
        файла формы (`handlers` не переданы) — `None`: доказать нечем."""
        owner = self.owner_of(line)
        graph = self.graph()
        if owner is None or self.at_opening(line):
            return None
        for name, event, where in graph["user"]:
            if owner in self.reach([name]):
                return {"event": event, "where": where}
        return None

    def order_key(self, line):
        """Ключ порядка выполнения строки при открытии: наибольший (последний) из ключей всех путей вызовов от открытия. Путь — `(ранг, строка вызова, …, строка)`: ранг — тело
        модуля 0, события жизни формы по порядку `ПередОткрытием`, `ПриОткрытии`, `ОбновлениеОтображения` 1–3, прочие события формы 4; вызов внутри процедуры стоит на своей строке,
        вызванная процедура выполняется в этом месте при каждом вызове. Строка вне путей от открытия — `(9, строка)`: в порядок открытия не входит."""
        graph = self.graph()
        owner = self.owner_of(line)
        if owner is None:
            return (0, line)
        found, steps = [], [0]

        def walk(name, prefix, stack):
            steps[0] += 1
            if steps[0] > ORDER_STEPS:
                return
            if name == owner:
                found.append(prefix + (line,))
            for callee, at in graph["calls"].get(name, ()):
                if callee not in stack:
                    walk(callee, prefix + (at,), stack | {name})
        for callee, at in graph["body"]:
            walk(callee, (0, at), frozenset())
        for name in graph["life"]:
            walk(name, (LIFE_RANK.get(name, 4),), frozenset())
        return max(found) if found else (9, line)

    def source_text(self, name):
        """`(путь, строки, причина отказа)` файла выгрузки, названного в `source.file` (путь от каталога выгрузки или абсолютный внутри неё)."""
        if self.config_dir is None:
            return None, None, "source проверяется по выгрузке конфигурации: ключ --config не задан, файл не найти"
        if not isinstance(name, str) or not name.strip():
            return None, None, "source.file — путь файла от каталога выгрузки"
        root = self.config_dir.resolve()
        path = (root / name.strip()).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            return None, None, f"source.file «{name}» лежит вне выгрузки конфигурации"
        if not path.is_file():
            return None, None, f"source.file «{name}»: в выгрузке такого файла нет"
        if path.suffix.lower() != ".bsl":
            return None, None, f"source.file «{name}» — не модуль (нужен файл .bsl общего модуля или модуля объекта)"
        if "Forms" in path.relative_to(root).parts:
            return None, None, f"source.file «{name}» — модуль формы: эффект самой формы записывается без source, по её module.bsl"
        if path not in self._sources:
            try:
                self._sources[path] = path.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError) as why:
                return None, None, f"source.file «{name}» не читается: {why}"
        text = self._sources[path]
        return path, text, None

    def reachable(self, procedure):
        """`[(первая строка, последняя строка)]` процедуры `procedure` модуля и процедур, которые она вызывает (по имени в тексте), любой глубины."""
        from . import codetask, purpose
        if self._reach is None:
            procs = purpose.parse_module(self.module_text or "")
            mapping = codetask.module_map(procs, [], self.module_text or "")
            self._reach = {p["name"].casefold(): ((p["line"], p["end"]), [c["name"].casefold() for c in p["calls"]]) for p in mapping["procedures"]}
        seen, todo, out = set(), [procedure.casefold()], []
        while todo:
            name = todo.pop()
            if name in seen or name not in self._reach:
                continue
            seen.add(name)
            out.append(self._reach[name][0])
            todo += self._reach[name][1]
        return out

    def event_rows(self, target):
        """Обработчики файла формы у цели записи: `[{event, code, procedure}]`; `None` — обработчики не переданы."""
        if self.handlers is None:
            return None
        out = []
        if target["kind"] == "form":
            out += [{"owner": "wait", "event": WAIT_EVENT, "code": name, "procedure": name, "element": None} for name in self.wait_handlers()]
        if target["kind"] == "form":
            out += self.action_rows()          # процедура, привязанная кодом к кнопке, — обработчик формы: цель одна
        for row in self.handlers:
            if target["kind"] == "form" and row["owner"] == "form":
                out.append(row)
            elif target["kind"] == "element" and row["owner"] == "element" and row["element"] == target["element"]:
                out.append(row)
            elif target["kind"] == "button" and row["owner"] == "panel" and row.get("bar") == target["element"] and (row.get("button") or "").casefold() == target["sub"].casefold():
                out.append(row)
            elif target["kind"] == "column" and row["owner"] == "column" and row.get("table") == target["element"] and (row.get("column") or "").casefold() == target["sub"].casefold():
                out.append(row)
        return out

    def bound_fields(self):
        """Имена данных (без регистра), которые на форме показывает поле: присваивание такому реквизиту меняет экран (признак П6). Поле — по привязке данных
        (`field_data`, её читает сборка досье); привязки не прочитаны — полем считается одноимённый элемент."""
        if self.field_data is not None:
            return {name.casefold() for _kind, name in self.field_data.values() if name}
        return self.data_names & {item.label().casefold() for item in self.names.item_of.values()}

    def common_modules(self):
        """Имена общих модулей выгрузки (без регистра); без выгрузки пусто."""
        if self._modules is None:
            self._modules = {name.casefold() for _p, name in scan._module_files(self.config_dir)} if self.config_dir is not None else set()
        return self._modules

    def known_words(self):
        """Слова, которые в записи `title` читаются выражением: имена из модуля формы (переменные, параметры, процедуры), данные формы и объекта, элементы."""
        if self._words is None:
            words = {w.casefold() for _n, masked, _r in self.scanned() for w in re.findall(scan.NAME, masked)}
            self._words = words | self.known | self.data_names
        return self._words

    def event_owners(self, event):
        """Фраза-подсказка отказа «нет события у цели»: у каких целей событие `event` есть (цель — в JSON, как её пишут в записи); пусто, если оно нет ни у кого."""
        found = []
        for row in self.handler_rows():
            if event.casefold() not in (str(row.get("event")).casefold(), str(row.get("code")).casefold()):
                continue
            owner = row.get("owner")
            full = ({"form": True} if owner in ("form", "action") else {"element": self.names.item_of[row["element"]].label() if row.get("element") in self.names.item_of else row.get("element")} if owner == "element"
                    else {"column": [row.get("table"), row.get("column")]} if owner == "column" else {"button": [row.get("bar"), row.get("button")]})
            text = json.dumps(full, ensure_ascii=False)
            if text not in found:
                found.append(text)
        return ("; такое событие есть у цели " + " или ".join(found[:3]) + ": назовите её в target") if found else ""

    def row_output(self, target, lines):
        """Цитата стоит в обработчике `ПриВыводеСтроки` или `ПриПолученииДанных` таблицы цели (элемент-таблица либо колонка этой таблицы): оформление строк обращается к таблице через параметр процедуры,
        и её имени в цитате нет."""
        table = target["element"] if target["kind"] in ("element", "column") else None
        if table is None or self.handlers is None:
            return False
        for row in self.handlers:
            if row["owner"] != "element" or row["element"] != table:
                continue
            if not any(word in (str(row["event"]) + str(row["code"])).casefold().replace(" ", "") for word in ROW_EVENTS):
                continue
            if any(first <= lines[0] and lines[1] <= last for first, last in self.reachable(row["procedure"])):
                return True
        return False

    def known_name(self, name):
        """Имя элемента, колонки, реквизита объекта или формы, либо путь из таких имён и слов пути (`PATH_WORDS`), через точку или косую черту (`Панель/Дерево`, как в цели): каждое звено
        должно быть известно, а не только последнее (`Нечто.Номенклатура` с неизвестным «Нечто» — не путь к данным)."""
        links = [link.strip().casefold() for link in re.split(r"[./]", re.sub(r"\[[^\]]*\]", "", name))]
        return bool(links) and all(link and (link in self.known or link in PATH_WORDS) for link in links)

    def element(self, name, must_exist=True):
        """`(полное имя, причина отказа)`: имя — короткое или полное; неоднозначное и несуществующее (при `must_exist`) — отказ."""
        if not isinstance(name, str) or not name.strip():
            return None, "имя элемента пусто"
        name = name.strip()
        if name in self.names.item_of:
            return name, None
        found = self.by_label.get(name.casefold()) or []
        if len(found) == 1:
            label = self.names.item_of[found[0]].label()
            if label != name.split(".")[-1].strip():
                self.case_notes.append(f"«{name}» в записи, «{label}» на форме")
            return found[0], None
        if len(found) > 1:
            return None, f"имя «{name}» неоднозначно (на форме {len(found)} элементов с таким именем): назовите полное имя — " + "; ".join(found)
        if must_exist:
            return None, f"элемента «{name}» на форме нет"
        return name, None


_CALL_OF = re.compile(rf"(?<![\wА-Яа-яЁё.])({scan.NAME})(?=\s*\()")


def foreign_chains(lines, span):
    """`{(первая строка, последняя): [имена процедур от вызванной до этой]}` — процедура файла `lines` (`modulescan.scan`) в диапазоне `span` и все процедуры того же файла, до которых
    она доходит вызовами по имени (`Имя(`), любой глубины; цикл вызовов обрывается, каждая процедура берётся по кратчайшему пути."""
    procs = {name.casefold(): (name, first, last if last is not None else first) for name, _p, first, last in scan.procedures_of(lines)}
    entry = next((key for key, (_n, first, _l) in procs.items() if first == span[0]), None)
    if entry is None:
        return {tuple(span): []}
    out = {(procs[entry][1], procs[entry][2]): [procs[entry][0]]}
    todo = [(entry, [procs[entry][0]])]
    seen = {entry}
    while todo:
        key, path = todo.pop(0)
        _name, first, last = procs[key]
        for number, masked, _raw in lines:
            if not first < number <= last:
                continue
            for hit in _CALL_OF.finditer(masked):
                callee = hit.group(1).casefold()
                if callee in procs and callee not in seen:
                    seen.add(callee)
                    out[(procs[callee][1], procs[callee][2])] = path + [procs[callee][0]]
                    todo.append((callee, path + [procs[callee][0]]))
    return out


def _module_label(path):
    """Короткое имя модуля по пути файла выгрузки: общий модуль — его имя, модуль объекта — «модуль объекта»."""
    parts = pathlib.PurePath(str(path)).parts
    if "CommonModules" in parts:
        return parts[parts.index("CommonModules") + 1]
    return hd.OBJECT_LABEL if pathlib.PurePath(str(path)).name == "ObjectModule.bsl" else pathlib.PurePath(str(path)).stem


def _pair(value):
    return isinstance(value, list) and len(value) == 2 and all(isinstance(x, str) or x is None for x in value)


def _resolve(kind, target, targets, nameless=False):
    """`(цель, причина)`: разрешённая цель записи — словарь `{kind, element, sub}`; вид цели проверен по `TARGETS`. `nameless` — у кнопки имя пусто (его заменяет `name_expr`)."""
    if not isinstance(target, dict) or len(target) != 1:
        return None, ("цель — словарь из одного ключа: form, element, page, column или button" + (
            "; у other цель обязательна: то, что относится ко всей форме или к нескольким элементам сразу (цикл по ЭлементыФормы, общая подготовка), — {\"form\": true}"
            if kind == "other" else ""))
    (key, value), = target.items()
    if key not in TARGET_KEYS:
        return None, f"цель «{key}» не из словаря ({', '.join(TARGET_KEYS)})"
    if key not in TARGETS[kind]:
        if kind == "current_page":
            return None, ("current_page — страница, которую код делает текущей: цель {\"page\": [панель, страница]}, например {\"page\": [\"ПанельПоказателя\", \"ПлатёжПоПериоду\"]}; "
                          f"цель «{key}» (панель целиком) не подходит. Страница задана переменной или вычисляется — created с name_expr либо other с причиной")
        return None, f"запись вида «{kind}» не бывает с целью «{key}» (бывает: {', '.join(TARGETS[kind])})"
    if key == "form":
        if value is not True:
            return None, "цель form — это {\"form\": true}"
        return {"kind": "form", "element": None, "sub": None}, None
    if key == "name":
        if not isinstance(value, str) or not value.strip():
            return None, "цель name — имя, как оно написано в коде"
        name = value.strip()
        if name.casefold() in COLLECTION_METHODS:
            return None, (f"«{name}» — метод коллекции ЭлементыФормы (`ЭлементыФормы.{name}(…)`), а не имя элемента: missing не бывает; если код создаёт элемент, запишите created "
                          "с name_expr (имя вычисляется) или с именем элемента")
        if not NAME_ONLY.match(name):
            return None, f"цель name — одно имя без точек, скобок и пробелов (как в коде после `ЭлементыФормы.`), а не «{shorten(name, 40)}»"
        if name in targets.names.item_of or name.casefold() in targets.by_label or name.casefold() in targets.fields or name.casefold() in targets.page_names:
            return None, f"«{name}» на форме есть: запись missing — для имени, которого на форме нет (у существующего цель — element, page, column или button)"
        return {"kind": "name", "element": None, "sub": name}, None
    if key == "element" and nameless and isinstance(value, str) and not value.strip():
        return {"kind": "element", "element": None, "sub": None, "known": False}, None          # элемент, имя которого код вычисляет (`name_expr`)
    if key == "element":
        full, why = targets.element(value, must_exist=kind != "created")
        if why:
            return None, why
        return {"kind": "element", "element": full, "sub": None, "known": full in targets.names.item_of}, None
    nested = key == "button" and isinstance(value, list) and len(value) > 2
    if nested:
        if not all(isinstance(x, str) and x.strip() for x in value[:-1]) or not isinstance(value[-1], str) or (not value[-1].strip() and not nameless):
            return None, "цель button с меню — [панель, подменю, …, кнопка]: имена строками, без пустых звеньев (пусто может быть только последнее, у created с name_expr)"
        path = [x.strip() for x in value[1:-1]]
        value = [value[0], value[-1]]
    elif not _pair(value):
        return None, f"цель {key} — пара [{HOLDER_WORDS[key]}, имя]" + (" либо [панель, подменю, …, кнопка]" if key == "button" else "")
    else:
        path = []
    holder, sub = value[0] or "", (value[1] or "").strip()
    if not sub and not (nameless and key in ("button", "page", "column")):
        return None, f"в цели {key} не названо имя" + (" (пустое имя кнопки — только у created с name_expr)" if key == "button" else " (пустое имя — только у created с name_expr)" if key in ("page", "column") else "")
    if holder == "" and key == "page":
        panel = None
    else:
        panel, why = targets.element(holder)
        if why:
            return None, why
        item = targets.names.item_of[panel]
        if item.type != HOLDER_TYPES[key]:
            return None, f"«{holder}» — {item.type}, а не {HOLDER_WORDS[key]}: у него нет такой цели" + _button_element_hint(key, sub, targets)
    dynamic = False
    if path:
        children = targets.menu_children(panel, path)
        if children is None:
            if not targets.has_created(panel, path):
                return None, (f"в панели «{holder}» нет меню по пути {' → '.join(path)}: подменю называют по кнопкам файла, от панели вглубь; меню, которое создаёт код, — после принятой записи created "
                              "этого меню")
            children, dynamic = [], True          # меню создано кодом (принятая запись created): его кнопок в файле нет
        pool = {(b.get("name") or "").casefold() for b in children if b.get("name")}
    else:
        pool = (targets.pages if key == "page" else targets.columns if key == "column" else targets.buttons).get(panel, set())
    known = bool(sub) and sub.casefold() in pool
    if not known and key == "button" and sub and targets.has_created(panel, path + [sub]):
        dynamic = True
    if not known and kind not in ("created",) and not (nameless and not sub) and not dynamic:
        owner = "формы" if panel is None else f"«{holder}»"
        return None, f"у {owner} нет {'страницы' if key == 'page' else 'колонки' if key == 'column' else 'кнопки'} «{sub}»" + (
            f" (есть: {', '.join(sorted(pool))})" if pool else "") + _button_element_hint(key, sub, targets)
    return {"kind": key, "element": panel, "sub": sub, "known": known, **({"path": path} if path else {}), **({"dynamic": True} if dynamic else {})}, None


def _button_element_hint(key, sub, targets):
    """Подсказка к отказу цели `button`: «кнопка» с таким именем — элемент формы вида Button (она лежит на форме или странице, а не на командной панели): цель `{"element": имя}`."""
    if key != "button":
        return ""
    found = targets.by_label.get((sub or "").casefold()) or []
    if len(found) == 1 and targets.names.item_of[found[0]].type == "Button":
        return f"; «{sub}» — элемент формы вида «Кнопка», а не кнопка командной панели: цель {{\"element\": \"{targets.names.item_of[found[0]].label()}\"}}"
    return ""


def _lines(note, targets, key="lines"):
    value = note.get(key)
    if not (isinstance(value, list) and len(value) == 2 and all(isinstance(x, int) and not isinstance(x, bool) for x in value)):
        return None, f"{key} — пара целых [от, до]"
    first, last = value
    if first < 1 or last < first:
        return None, f"{key} [{first}, {last}]: строки с единицы, «от» не больше «до»"
    if last > len(targets.lines):
        return None, f"{key} [{first}, {last}]: в модуле {len(targets.lines)} строк"
    if not any(a <= first and last <= b for a, b in targets.segments()):
        return None, (f"строки {first}–{last} лежат не в одном месте модуля: запись описывает одну процедуру или одну часть тела модуля (вне процедур), а диапазон переходит "
                      "границу процедуры; разнесите запись по местам")
    return (first, last), None


def strip_comment(text):
    """Цитата без хвостовых комментариев: в каждой строке отрезается всё от `//` вне строкового литерала; пробелы на концах строк снимаются."""
    out = []
    for line in text.split("\n"):
        inside, cut = False, len(line)
        for at, char in enumerate(line):
            if char == '"':
                inside = not inside
            elif char == "/" and not inside and line[at:at + 2] == "//":
                cut = at
                break
        out.append(line[:cut].rstrip())
    return "\n".join(out).strip()


def _alias(note, kind, target, quote, targets):
    """`(alias, причина)`: псевдоним, полученный в другой процедуре. `alias` — `{"lines": [от, до], "quote": …}`: присваивание `Псевдоним = ЭлементыФормы.<Цель>…` (одно место модуля);
    цитата записи обращается к этому псевдониму по имени. Без ключа — `(None, None)`."""
    if "alias" not in note:
        return None, None
    given = note["alias"]
    if not isinstance(given, dict) or set(given) != {"lines", "quote"}:
        return None, 'alias — словарь {"lines": [от, до], "quote": …}: строки присваивания псевдонима и цитата из них'
    if kind not in ALIAS_KINDS:
        return None, f"псевдоним (alias) бывает у видов, где имя цели стоит в цитате ({', '.join(sorted(ALIAS_KINDS))}), а не у «{kind}»"
    if target["kind"] == "form":
        return None, "у цели «форма» имени нет, псевдоним не нужен"
    span, why = _lines(given, targets, "lines")
    if why:
        return None, "alias." + why
    text = given.get("quote")
    text = strip_comment(text) if isinstance(text, str) else ""
    if len(text) < MIN_QUOTE:
        return None, f"alias.quote — точная цитата из строк alias.lines, не короче {MIN_QUOTE} знаков"
    if _squash(text) not in _squash(" ".join(raw for n, _m, raw in targets.scanned() if span[0] <= n <= span[1])):
        return None, f"alias.quote «{shorten(text, 60)}» не найдена в строках {span[0]}–{span[1]} модуля (комментарии не считаются)"
    names = _target_names(note, target, targets)
    if names and not any(_word_in(n, text) for n in names):
        return None, f"в alias.quote нет имени цели «{names[-1]}»: присваивание псевдонима называет то, что запись описывает"
    variables = [m.group(1) for m in re.finditer(r"(?<![\wА-Яа-яЁё.])([\wА-Яа-яЁё]+)\s*=(?!=)", text)]
    if not any(_word_in(v, quote) for v in variables):
        return None, ("в цитате записи нет псевдонима из alias.quote" + (f" («{variables[0]}»)" if variables else "") + ": цитата обращается к элементу через эту переменную, "
                      "а alias.quote — строка, где она получена")
    return {"lines": list(span), "quote": text}, None


def _segments_of(text, count):
    """`[(первая, последняя)]` процедур текста и кусков вне процедур; `count` — число строк текста."""
    from . import purpose
    spans = sorted((p["line"], p["end"]) for p in purpose.parse_module(text))
    out = list(spans)
    at = 1
    for first, last in spans + [(count + 1, count + 1)]:
        if first > at:
            out.append((at, first - 1))
        at = max(at, last + 1)
    return sorted(out)


def _squash(text):
    return " ".join(text.split())


def _word_in(word, text):
    """Слово `word` стоит в `text` отдельным именем (без регистра, соседние знаки — не буквы и не цифры): `Цена` не находится в `ЦенаВходная`."""
    return re.search(r"(?<![\wА-Яа-яЁё])" + re.escape(word) + r"(?![\wА-Яа-яЁё])", text, re.I) is not None


def _target_names(note, target, targets):
    """Имена цели записи, одно из которых обязано стоять в цитате: последнее звено имени (`Объект.Поле` → `Поле`); у элемента — и его короткое имя на форме. У `form` имён нет."""
    if target["kind"] == "form":
        return []
    if target["kind"] == "element":
        given = note.get("target", {}).get("element")
        out = [str(given).strip().split(".")[-1]] if isinstance(given, str) else []
        item = targets.names.item_of.get(target["element"])
        if item is not None:
            out.append(item.label())
        if note.get("kind") == "value" and targets.field_data:
            out.append((targets.field_data.get(target["element"]) or ("", ""))[1])          # код присваивает данным поля, а не элементу: `Реквизит = "…"`
        return [n for n in dict.fromkeys(out) if n]
    return [target["sub"]]


def _masked(scanned, lines):
    """Текст строк `lines` без комментариев и без содержимого литералов, пробелы схлопнуты: слово действия обязано стоять в коде, а не в строке или комментарии."""
    return _squash(" ".join(m for n, m, _raw in scanned if lines[0] <= n <= lines[1]))


def _missing_access(name, quote):
    """В цитате имя стоит обращением к элементу: `ЭлементыФормы.<имя>`, `ЭлементыФормы["<имя>"]`, `.Кнопки.|.Колонки.|.Страницы.<имя>`, `["<имя>"]`, `Найти("<имя>")`."""
    n = re.escape(name)
    pattern = (rf"ЭлементыФормы\s*\.\s*{n}(?![\wА-Яа-яЁё])|\[\s*\"{n}\"\s*\]|\.\s*(?:Кнопки|Колонки|Страницы)\s*\.\s*{n}(?![\wА-Яа-яЁё])"
               rf"|Найти\s*\(\s*\"{n}\"\s*\)")
    return re.search(pattern, quote, re.I) is not None


COLLECTION_OF = {"button": "Кнопки", "page": "Страницы", "column": "Колонки"}


def _name_expr(expr, target, quote, targets):
    """Причина отказа выражению имени созданного (кнопка, страница, колонка, элемент), иначе `None`: не короче трёх знаков, не литерал в кавычках, стоит в цитате, а цитата обращается к тому,
    куда код добавляет (`Панель.Кнопки`, `Панель.Страницы`, `Таблица.Колонки`, `ЭлементыФормы.Добавить`)."""
    expr = expr.strip()
    if len(expr) < MIN_QUOTE:
        return f"name_expr «{expr}» короче {MIN_QUOTE} знаков: так не называют вычисляемое имя"
    if _is_literal(expr):
        return "name_expr — литерал в кавычках: имя не вычисляется; запишите created с именем в цели"
    if _squash(expr).casefold() not in _squash(quote).casefold():
        return f"в цитате нет выражения имени «{shorten(expr, 60)}»: цитата называет то, что запись описывает"
    if target["kind"] == "element":
        if re.search(r"ЭлементыФормы\s*\.\s*Добавить\b", quote, re.I) is None:
            return "цитата не обращается к `ЭлементыФормы.Добавить(…)`: элемент, имя которого вычисляется, код создаёт этим вызовом"
        return None
    word = COLLECTION_OF[target["kind"]]
    if target["element"] is None:
        return None          # страница самой формы: панели в цитате нет
    holder = targets.names.item_of[target["element"]].label()
    if re.search(r"(?<![\wА-Яа-яЁё])" + re.escape(holder) + r"\s*\.\s*" + word + r"\b", quote, re.I) is None:
        return f"цитата не обращается к {'панели ' if target['kind'] == 'button' else ''}«{holder}» (`{holder}.{word}…`): «{holder}» в цели названа не та, куда код добавляет"
    return None


def _bound(note, kind, target, quote, targets, name_quote=None, masked=None, lines=None, alias=None):
    """Причина отказа, если цитата не привязана к записи, иначе `None`: в цитате стоит имя цели (последнее звено), а у видов из `PROPERTY_WORDS` ещё слово свойства или действия;
    у `created` — создаваемое имя. Без этого запись с цитатой «Видимость» из чужой процедуры или «Если» подтверждала бы что угодно. У записи с `source` слово действия ищется в цитате
    `source`, а имя цели — в обеих цитатах (`name_quote`): другой модуль получает элемент параметром и называет его иначе (`Элемент.Заголовок`), а имя стоит в строке вызова."""
    if kind in ("on_event", "other"):
        return None
    if kind == "title" and CELL_TEXT.search(name_quote or quote):
        return ("это текст ячеек строк (`….Ячейки.<Колонка>.Текст`), а не заголовок колонки: запишите appearance с целью-колонкой (или таблицей) и словами в value — "
                "«текст ячейки — количество с «шт»»")
    names = _target_names(note, target, targets)
    if kind == "created" and note.get("name_expr"):
        names = []         # имени у кнопки нет: вместо него `name_expr`, он проверяется отдельно
    if alias or (kind == "appearance" and lines and targets.row_output(target, lines)):
        names = []         # имя цели назвал псевдоним из другой процедуры (проверен в `_alias`) либо оформление строк в `ПриВыводеСтроки`, где таблица — параметр процедуры, а не имя в цитате
    if target["kind"] == "button" and _loop_over_buttons(name_quote or quote, target, targets):
        names = []         # цикл по кнопкам меню: имя кнопки в цитате не стоит, кнопку называет цель, а условие — `condition`
    indexed = _index_access(name_quote or quote, target, targets)
    if isinstance(indexed, str):
        return indexed
    if indexed:
        names = []         # обращение по индексу (`Колонки[0]`, `Страницы[Инд]`): цель называет порядок в файле, а не имя в цитате
    if names and not any(_word_in(n, name_quote or quote) for n in names):
        return (_unknown_in_quote(name_quote or quote, targets, names[-1]) or f"в цитате нет {'создаваемого имени' if kind == 'created' else 'имени цели'} «{names[-1]}»: возьмите в quote строку с этим именем (например `{names[-1]}.Видимость`); "
                "через псевдоним — строка получения и строка действия подряд, а из другой процедуры — ключ alias; по номеру — `Колонки[0]`")
    if target.get("path") and not _menu_access(name_quote or quote, targets, target):
        panel = targets.names.item_of[target["element"]].label()
        menu = target["path"][-1]
        return (f"цель — кнопка в меню «{panel} → {' → '.join(target['path'])} → {target['sub']}», а в цитате нет обращения к меню: цитата обращается к кнопке так, как это делает код "
                f"(`{panel}.Кнопки.{menu}.Кнопки.{target['sub']}`, `{menu}.Кнопки.{target['sub']}`), — или цель кнопки из файла: {{\"button\": [\"{panel}\", \"{target['sub']}\"]}}")
    if kind == "missing" and re.search(r"(?<![\wА-Яа-яЁё.])ЭтаФорма\s*\.\s*" + re.escape(target["sub"]) + r"(?![\wА-Яа-яЁё])", quote, re.I):
        return (f"`ЭтаФорма.{target['sub']}` — свойство самой формы (панель, заголовок, размер), а не элемент: цель {{\"form\": true}} "
                "(`ЭтаФорма.Панель.ЦветФона` — appearance формы, `ЭтаФорма.Заголовок` — title формы); missing бывает у имени, которого нет и у формы")
    if kind == "missing" and not _missing_access(target["sub"], quote):
        return (f"в цитате имя «{target['sub']}» не стоит обращением к элементу: нужно `ЭлементыФормы.{target['sub']}`, `ЭлементыФормы[\"{target['sub']}\"]`, "
                f"`….Кнопки.|Колонки.|Страницы.{target['sub']}` или `Найти(\"{target['sub']}\")`")
    words = PROPERTY_WORDS.get(kind)
    seen = name_quote or quote           # слово действия ищется и в цитате записи, и в `source.quote`
    if kind == "appearance" and CELL_TEXT.search(seen):
        words = words + ("Текст",)           # `Оформление.Ячейки.Количество.Текст`: слово «Текст» — оформление ячейки, если в цитате `.Ячейки.`
    if kind == "title" and target["kind"] == "column":
        words = words + ("ТекстШапки",)      # заголовок колонки обычной формы задаёт `ТекстШапки`
    if kind == "appearance" and lines and targets.row_output(target, lines):
        words = None                         # оформление строк в `ПриВыводеСтроки` и `ПриПолученииДанных`: таблица — параметр процедуры, слово действия не нужно
    if kind == "appearance" and words and _word_in("ТекстШапки", seen) and not any(_word_in(w, seen) for w in words):
        return ("ТекстШапки — заголовок колонки, а не оформление: запишите title с целью {\"column\": [таблица, колонка]} и value — текстом шапки "
                "(оформление — цвет, шрифт, картинка, оформление строк)")
    if words and not any(_word_in(w, seen) for w in words):
        hint = ""
        if kind == "title" and target["kind"] != "column" and _word_in("ТекстШапки", seen):
            hint = "ТекстШапки — заголовок колонки: цель {\"column\": [таблица, колонка]}. "
        return (f"{hint}в цитате нет слова «{words[0]}»" + (f" (или {', '.join('«' + w + '»' for w in words[1:])})" if len(words) > 1 else "")
                + f": запись «{kind}» привязана к строке, где оно стоит (слово ищется отдельным словом без учёта регистра: `ПоставитьЗаголовок…` слова «Заголовок» не даёт). "
                "Действие делает процедура другого модуля — в `lines`/`quote` строка вызова, а строку с действием дайте в `source`")
    if words and masked is not None and not any(_word_in(w, masked) for w in words):
        return f"слово «{words[0]}» стоит в комментарии или строковом литерале, а не в коде: запись привязана к строке кода"
    return None


_FORM_ITEM = re.compile(r"ЭлементыФормы\s*\.\s*([\wА-Яа-яЁё]+)", re.I)


def _unknown_in_quote(quote, targets, wanted):
    """Подсказка к отказу «в цитате нет имени цели»: код называет `ЭлементыФормы.<имя>`, элемента с таким именем на форме нет (это данные элемента либо устаревшее имя) — запись `missing`."""
    unknown = [n for n in dict.fromkeys(_FORM_ITEM.findall(quote)) if n not in targets.names.item_of and n.casefold() not in targets.by_label and n.casefold() not in targets.fields]
    if not unknown:
        return None
    for name in unknown:
        whole = next((full for full in sorted(targets.by_label) if len(full) > len(name) and full.startswith(name.casefold())), None)
        if whole is not None:
            return (f"цитата оборвана посреди имени? «{name}» — начало имени элемента «{targets.names.item_of[targets.by_label[whole][0]].label()}»: "
                    "цитата берёт строку целиком, а не первые знаки")
    return (f"в коде «{unknown[0]}» — не элемент «{wanted}»: элемента с таким именем на форме нет (так называются данные элемента или устаревшее имя), поэтому это запись missing "
            f"с целью {{\"name\": \"{unknown[0]}\"}}, а не запись о «{wanted}»")


_MENU_ACCESS = re.compile(r"\.\s*Кнопки\b", re.IGNORECASE)


def _menu_access(quote, targets, target):
    """Цитата обращается к кнопкам меню, а не панели: перед `.Кнопки` стоит не сама панель (её имя, подпись, `ЭлементыФормы["…"]`) и не `ЭлементыФормы`, а другое имя
    (`Подменю.Кнопки`) либо элемент набора (`Кнопки[0].Кнопки`)."""
    item = targets.names.item_of.get(target["element"])
    panel = {target["element"].split(".")[-1].casefold()} | ({item.label().casefold()} if item is not None else set())
    for m in _MENU_ACCESS.finditer(quote):
        before = quote[:m.start()].rstrip()
        if before.endswith("]"):
            if re.search(r"ЭлементыФормы\s*\[[^\]]*\]$", before, re.IGNORECASE):
                continue
            return True
        receiver = re.search(r"([\w]+)$", before)
        if receiver and receiver.group(1).casefold() not in panel and receiver.group(1).casefold() != "элементыформы":
            return True
    return False


LOOP_BUTTONS = re.compile(rf"Для\s+Каждого\s+(?P<var>{scan.NAME})\s+Из\s+(?P<chain>[^\n]*?)\.\s*Кнопки\s*(?:Цикл|\n|$)", re.I)


def _loop_over_buttons(quote, target, targets):
    """Цитата — цикл по кнопкам панели или меню (`Для Каждого К Из ЭлементыФормы.КП.Кнопки.Вид.Кнопки Цикл` и строки с `К.` ниже): имени одной кнопки в ней нет, запись о кнопке принимается
    с привязкой к панели в цикле и переменной цикла в строках после него."""
    item = targets.names.item_of.get(target.get("element"))
    if item is None:
        return False
    holders = {target["element"].split(".")[-1].casefold(), item.label().casefold()}
    for hit in LOOP_BUTTONS.finditer(quote):
        chain = {t.casefold() for t in re.split(r"[.\s\[\]\"]+", hit.group("chain")) if t}
        if holders & chain and _word_in(hit.group("var"), quote[hit.end():]):
            return True
    return False


INDEX_ACCESS = re.compile(r"(?P<coll>Колонки|Страницы|Кнопки)\s*\[\s*(?P<index>[^\]]+?)\s*\]", re.I)
COLLECTION_KIND = {"колонки": "column", "страницы": "page", "кнопки": "button"}
COLLECTION_NOUN = {"column": "колонка", "page": "страница", "button": "кнопка"}


def _index_access(quote, target, targets):
    """Цитата обращается к цели по индексу коллекции (`Колонки[0]`, `Страницы[Инд]`, `Кнопки[Номер]`): имя цели в ней не стоит, цель называет место в файле. `False` — обращения по индексу
    нет; `True` — есть (число проверено по порядку файла, остальное — переменная цикла); строка — причина отказа: индекс не сходится с порядком файла."""
    kind = target["kind"]
    if kind not in COLLECTION_NOUN or target.get("path") or not target.get("sub"):
        return False
    for hit in INDEX_ACCESS.finditer(quote):
        if COLLECTION_KIND[hit.group("coll").casefold()] != kind:
            continue
        index = hit.group("index")
        if not re.fullmatch(r"\d+", index):
            return True
        order = (targets.column_order if kind == "column" else targets.page_order if kind == "page" else targets.button_order).get(target["element"], [])
        if int(index) >= len(order):
            return f"{hit.group(0)}: в файле {len(order)} элементов коллекции, индекс считается с нуля по порядку файла"
        if order[int(index)] != target["sub"].casefold():
            return (f"{hit.group(0)}: по порядку файла это {COLLECTION_NOUN[kind]} «{order[int(index)] or 'без имени'}», а в цели «{target['sub']}» "
                    "(индекс считается с нуля по порядку файла)")
        return True
    return False


def _is_literal(text):
    return len(text) > 1 and text[0] == text[-1] == '"' and text.count('"') == 2


def _reach_in(calls, name):
    seen, todo = set(), [name]
    while todo:
        cur = todo.pop()
        if cur in seen or cur not in calls:
            continue
        seen.add(cur)
        todo += calls[cur]
    return seen


def _calls_name(quote, name):
    """В цитате стоит вызов `Имя(` или `Владелец.Имя(`."""
    return re.search(r"(?<![\wА-Яа-яЁё])" + re.escape(name) + r"\s*\(", quote, re.I) is not None


def _source(note, kind, targets):
    """`(source, причина отказа)`: `source` записи — `{file, lines, quote}` проверен по файлу выгрузки (строки внутри одной процедуры или куска тела, цитата найдена
    в этих строках); без `source` — `(None, None)`."""
    if "source" not in note:
        return None, None
    source = note["source"]
    if kind not in SOURCE_KINDS:
        return None, f"source бывает у видов, где в цитате ищется слово действия, и у on_event ({', '.join(sorted(SOURCE_KINDS))}), а не у «{kind}»"
    if not isinstance(source, dict) or set(source) != SOURCE_KEYS:
        return None, "source — словарь {file, lines, quote}: файл от каталога выгрузки, строки в нём и точная цитата"
    path, text, why = targets.source_text(source.get("file"))
    if why:
        return None, why
    lines = text.splitlines()
    value = source.get("lines")
    if not (isinstance(value, list) and len(value) == 2 and all(isinstance(x, int) and not isinstance(x, bool) for x in value)):
        return None, "source.lines — пара целых [от, до]"
    first, last = value
    if first < 1 or last < first or last > len(lines):
        return None, f"source.lines [{first}, {last}]: в файле «{source['file']}» {len(lines)} строк, строки с единицы, «от» не больше «до»"
    if not any(a <= first and last <= b for a, b in _segments_of(text, len(lines))):
        return None, f"source.lines {first}–{last} лежат не в одной процедуре файла «{source['file']}»: запись описывает одну процедуру или один кусок тела модуля"
    quote = source.get("quote")
    if not isinstance(quote, str) or len(quote.strip()) < MIN_QUOTE:
        return None, f"source.quote — точная цитата из строк {first}–{last} файла, не короче {MIN_QUOTE} знаков"
    cleaned = strip_comment(quote)            # как у quote записи: хвостовой комментарий в цитате отрезается
    if not cleaned:
        return None, "source.quote — комментарий, а не код (комментарии не считаются): цитата берёт строку кода"
    quote = cleaned
    scanned = scan.scan(text)
    if _squash(quote) not in _squash(" ".join(raw for n, _m, raw in scanned if first <= n <= last)):
        there = shorten(_squash(" ".join(strip_comment(raw) for n, _m, raw in scanned if first <= n <= last)), 120)
        return None, (f"source.quote «{shorten(quote.strip(), 60)}» не найдена в строках {first}–{last} файла «{source['file']}» (комментарии не считаются); в этих строках стоит: «{there}». "
                      "Цитата — точный текст кода без комментария и без многоточия")
    from . import codetask, purpose
    procs = purpose.parse_module(text)
    owner = next((p["name"] for p in procs if p["line"] <= first and last <= p["end"]), None)
    if owner is None:
        return None, f"source.lines {first}–{last} лежат в теле модуля «{source['file']}», а не в процедуре: к вызову из модуля формы тело не привязать"
    calls = {p["name"].casefold(): [c["name"].casefold() for c in p["calls"]] for p in codetask.module_map(procs, [], text)["procedures"]}
    callers = [name for name in calls if owner.casefold() in _reach_in(calls, name)]
    note_quote = note.get("quote") or ""
    if not any(_calls_name(note_quote, name) for name in callers) and not _wrapper_calls(note_quote, callers, targets):
        return None, (f"в `quote` записи нет вызова процедуры «{owner}» (или процедуры того же файла, из которой она вызывается): `source` описывает то, что делает вызванная процедура, "
                      "а строка вызова в модуле формы — `Имя(` или `Владелец.Имя(` — обязана стоять в цитате записи; вызов процедуры модуля формы, которая её вызывает, тоже годится")
    return {"file": source["file"].strip(), "lines": [first, last], "quote": quote.strip()}, None


def _wrapper_calls(quote, callers, targets):
    """Цитата записи вызывает процедуру модуля формы, которая (прямо или цепочкой процедур формы) вызывает одну из процедур `callers` другого файла: обёртка модуля формы над общим кодом."""
    ranges = targets.procedure_ranges()
    scanned = targets.scanned()
    for name in [n for n in ranges if _calls_name(quote, n)]:
        spans = [ranges[x] for x in targets.reach([name]) if x in ranges]
        text = " ".join(m for n, m, _r in scanned if any(a <= n <= b for a, b in spans))
        if any(_calls_name(text, caller) for caller in callers):
            return True
    return False


def legacy(note, targets):
    """Запись прежнего вида (P1–P4) в нынешний: `alias_lines`/`alias_quote` → `alias`; `certainty`, `depends_on`, `form_work`, `category` отбрасываются — их определяет навык, —
    а название ключа попадает в `targets.dropped` (одно предупреждение на файл, `warnings`). `targets` (список целей) переводит `check`, не эта функция. Новая запись возвращается копией."""
    if not isinstance(note, dict) or not (set(note) & LEGACY_KEYS):
        return note
    note = dict(note)
    for key in DROPPED_KEYS:
        if key in note:
            del note[key]
            targets.dropped_now.add(key)
    pair = [note.pop(k) for k in ("alias_lines", "alias_quote") if k in note]
    if pair:
        note["alias"] = {"lines": pair[0], "quote": pair[1]} if len(pair) == 2 else {"lines": None, "quote": None}      # одного из двух ключей не хватает: `_alias` назовёт причину
    return note


_STRING = re.compile(r'"((?:[^"]|"")*)"')
_TEMPLATE_PART = re.compile(r"<[^<>]*>")
_OPERATOR_WORDS = frozenset(w.casefold() for w in ("Не", "И", "Или", "Новый", "Тогда", "Иначе", "Если", "Истина", "Ложь", "Неопределено", "Null", "Тип"))


def _stub_value(kind, value, lines, targets, source=None):
    """Причина отказа `value` записи `title`/`value` или `None`. Текст в прямых кавычках — только если такой литерал стоит в строках записи: переменная часть пишется в `<…>`
    (`"Перемещение <номер> (<дата>)"`), а то, что стоит между `<…>`, обязано быть литералом кода. Вне кавычек — выражение из кода: два слова подряд без знака между ними — описание, не выражение;
    у заголовка одно слово без кавычек должно быть именем из модуля или данных формы."""
    text = value.strip()
    code_text = _squash(" ".join(raw for n, _m, raw in targets.scanned() if lines[0] <= n <= lines[1]))
    if source:          # литерал стоит в строках чужого модуля, на которые ссылается `source`
        code_text += " " + _squash(" ".join(raw for n, _m, raw in scan.scan(targets.source_text(source["file"])[1]) if source["lines"][0] <= n <= source["lines"][1]))
    for literal in _STRING.findall(text):
        for part in _TEMPLATE_PART.split(literal.replace('""', '"')):
            part = _squash(part).strip(" \t.,:;!?()[]«»“”„\"'-–—/№")          # знаки по краям куска — склейка шаблона, не литерал
            if re.search(r"[\wА-Яа-яЁё]", part) and part not in code_text:
                return (f"value {shorten(text, 60)}: «{shorten(part, 40)}» в строках {lines[0]}–{lines[1]}{' и в source' if source else ''} нет, а в прямых кавычках стоит только литерал из кода; переменная часть "
                        "пишется в <…> (\"Перемещение <номер> (<дата>)\"). Выход: value — выражением из кода (`Строка(Номер)`) и why — смысл словами; литерал другого модуля — в `source`")
    bare = _STRING.sub(" ", text)
    words = [w for w in re.findall(r"[\wА-Яа-яЁё]+|\S", bare)]
    for left, right in zip(words, words[1:]):
        if re.fullmatch(r"[\wА-Яа-яЁё]+", left) and re.fullmatch(r"[\wА-Яа-яЁё]+", right) and left.casefold() not in _OPERATOR_WORDS and right.casefold() not in _OPERATOR_WORDS:
            return (f"value «{shorten(text, 60)}» — слова подряд без кавычек и знаков: это описание. Это выражение: value — выражением из кода (имя переменной или реквизита, вызов) "
                    "либо литералом кода в прямых кавычках (переменная часть — в <…>), смысл — в why")
    if kind == "title" and re.fullmatch(r"[\wА-Яа-яЁё]+|[^\w\s\"()+.,;]{1,3}", text) and text.casefold() not in targets.known_words():
        return (f"value «{text}» — одно слово без кавычек, и такого имени нет ни в модуле, ни среди данных формы: текст заголовка пишут в прямых кавычках "
                f"(\"{text}\"), выражение — именем переменной или реквизита, как в коде")
    return None


_EQ_LITERAL = re.compile(r'(?<![<>=\wА-Яа-яЁё.])(?P<var>[\wА-Яа-яЁё]+)\s*=\s*"(?P<lit>[^"\n]+)"')
_IF_LINE = re.compile(r"^\s*(?:Иначе)?Если\b", re.I)
_EXPORT_VAR = re.compile(r"^\s*Перем\b[^;]*\bЭкспорт\b", re.I)
_PLAIN_VALUE = re.compile(r'^\s*(?:"[^"]*"|Истина|Ложь|Неопределено|[-\d.]+)\s*$', re.I)
NOTIFY_EVENTS = frozenset({"обработкаоповещения"})          # параметры этих процедур приходят из `Оповестить(…)` других модулей: искать значение надо во всей выгрузке


def _literal_lines(text):
    """Строки модуля с литералами вне условий `Если`: `[(masked, raw)]` — там, где значение присваивают или передают."""
    return [(masked, raw) for _n, masked, raw in scan.scan(text) if masked.strip() and not _IF_LINE.match(masked)]


def _dump_literals(targets):
    """Все строковые литералы вне условий `Если` в модулях выгрузки (без регистра); без выгрузки — `None`. Читается один раз на `Targets`."""
    if targets.config_dir is None:
        return None
    if targets.__dict__.get("_dump_literals") is None:
        found = set()
        for path in targets.config_dir.rglob("*.bsl"):
            try:
                text = path.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError):
                continue
            for _masked, raw in _literal_lines(text):
                found.update(x.casefold() for x in re.findall(r'"([^"\n]+)"', raw))
        targets.__dict__["_dump_literals"] = found
    return targets._dump_literals


def unreachable_branch(lines, targets):
    """Причина отказа, если запись лежит в ветке `Если Переменная = "Значение"`, а значение нигде не присваивается и не передаётся, иначе `None`. Переменная — переменная модуля (не экспортная, все её
    присваивания в модуле — литералы) либо параметр `ОбработкаОповещения` (тогда значения ищутся и во всей выгрузке: оповещают из других модулей); реквизит формы, поле и прочее — значение
    приходит от пользователя или платформы, ветку считают достижимой. Условия с `Или` и `НЕ (…)` не читаются."""
    cond = targets.conditions().get(lines[0], "")
    cond = re.sub(r"НЕ\s*\([^()]*\)", " ", cond, flags=re.I)
    if not cond or re.search(r"(?<![\wА-Яа-яЁё])Или(?![\wА-Яа-яЁё])", cond, re.I):
        return None
    owner = targets.procedure_name(lines[0])
    params = {x.strip().split("=")[0].replace("Знач ", "").strip().casefold() for x in (targets.procedure_params(lines[0]) or "").split(",") if x.strip()}
    notify = bool(owner) and owner.casefold() in NOTIFY_EVENTS
    declared = {}
    for _n, masked, _raw in targets.scanned():
        if _EXPORT_VAR.match(masked):
            for name in re.findall(r"[\wА-Яа-яЁё]+", masked.split("Перем", 1)[-1]):
                declared[name.casefold()] = "export"
    variables = module_variables_of(targets) - set(declared)
    text = "\n".join(raw for _n, _m, raw in targets.scanned())
    here = {x.casefold() for _m, raw in _literal_lines(text) for x in re.findall(r'"([^"\n]+)"', raw)}
    for hit in _EQ_LITERAL.finditer(cond):
        var, lit = hit.group("var").casefold(), hit.group("lit")
        if var in targets.data_names or var in targets.fields:
            continue
        if lit.casefold() in here:
            continue
        if var in variables:
            others = [m.group("rhs") for _n, masked, _r in targets.scanned() for m in [re.match(rf"\s*{re.escape(var)}\s*=(?![=>])\s*(?P<rhs>[^;]*);?", masked, re.I)] if m]
            if any(not _PLAIN_VALUE.match(x) for x in others):
                continue
        elif var in params and notify:
            dump = _dump_literals(targets)
            if dump is None or lit.casefold() in dump:
                continue
        else:
            continue
        return (f"условие «{hit.group(0)}»: значение «{lit}» модуль {'и выгрузка ' if var in params else ''}нигде не присваивает и не передаёт — ветка не выполняется, её не записывают "
                "(если значение приходит снаружи, скажите об этом в why записи other)")
    return None


_CELL_NAME = re.compile(r"\.\s*Ячейки\s*\.\s*(?P<name>[\wА-Яа-яЁё]+)")


def absent_cell(target, quote, targets):
    """Причина отказа записи `appearance`, если цитата оформляет ячейку `….Ячейки.<Колонка>` колонки, которой у таблицы цели нет: такое оформление на экране ничего не даёт (код обрывается или пишет в пустоту)."""
    table = target["element"] if target["kind"] in ("element", "column") else None
    columns = targets.columns.get(table) if table else None
    if not columns:
        return None
    for name in dict.fromkeys(m.group("name") for m in _CELL_NAME.finditer(quote)):
        if name.casefold() not in columns:
            return (f"в цитате ячейка «{name}», а у таблицы «{targets.names.item_of[table].label()}» такой колонки нет: оформление несуществующей колонки на экране ничего не даёт — "
                    f"запишите missing с целью {{\"name\": \"{name}\"}} или не записывайте")
    return None


def check_one(note, targets):
    """`(принятая запись, причина отказа)`: проверенная запись с полями `kind`, `target`, `value`, `condition`, `message`, `group`, `default`, `lines`, `quote`, `why`;
    ровно один из двух элементов пары — `None`."""
    if not isinstance(note, dict):
        return None, "запись — словарь"
    targets.case_notes = []
    if note.get("kind") == "default":
        return None, "запись default проверяется вместе со списком записей (`codenotes.check`): она называет процедуры, а не строки модуля"
    note = legacy(note, targets)
    extra = sorted(set(note) - NOTE_KEYS)
    if extra:
        return None, f"ключи вне схемы: {', '.join(extra)}"
    kind = note.get("kind")
    if kind not in KINDS:
        return None, f"kind «{kind}» не из словаря ({', '.join(KINDS)})"
    if kind != "on_event" and ("event" in note or "effects" in note):
        return None, "event и effects бывают только у on_event"
    name_expr = note.get("name_expr", "")
    if "name_expr" in note and (kind != "created" or not isinstance(name_expr, str) or not name_expr.strip()):
        return None, "name_expr — непустое выражение имени, и только у created (кнопка, страница, колонка или элемент, имя которого код вычисляет)"
    target, why = _resolve(kind, note.get("target"), targets, nameless=bool(name_expr))
    if why:
        return None, why
    if kind == "created" and name_expr and (target["sub"] or (target["kind"] == "element" and target["element"])):
        return None, ("name_expr бывает у created с пустым именем в цели: {\"button\": [панель, \"\"]}, {\"page\": [панель, \"\"]}, {\"column\": [таблица, \"\"]} или {\"element\": \"\"}: "
                      "имя вычисляется выражением, и в цели оно пусто")
    lines, why = _lines(note, targets)
    if why:
        return None, why
    quote = note.get("quote")
    if isinstance(quote, str):
        cleaned = strip_comment(quote)            # хвостовой комментарий в цитате отрезается: комментарии к коду не относятся
        if quote.strip() and not cleaned:
            return None, "quote — комментарий, а не код (комментарии не считаются): цитата берёт строку кода"
        quote = cleaned
    if not isinstance(quote, str) or not quote.strip():
        return None, "quote — точная строка из диапазона lines, а она пуста (цитата нужна у всех видов записи, у other тоже)"
    if len(quote.strip()) < MIN_QUOTE:
        return None, f"quote «{quote.strip()}» короче {MIN_QUOTE} знаков: такая цитата совпадёт с чем угодно и к коду запись не привязывает"
    if _squash(quote) not in _squash(" ".join(raw for n, _m, raw in targets.scanned() if lines[0] <= n <= lines[1])):
        return None, f"quote «{shorten(quote.strip(), 60)}» не найдена в строках {lines[0]}–{lines[1]} модуля (комментарии не считаются)"
    value = note.get("value", "")
    if not isinstance(value, str):
        return None, "value — строка"
    if kind in VALUE_REQUIRED and not value.strip():
        return None, f"у записи «{kind}» нужно value"
    if kind == "list_content" and not value.strip():
        value = _list_literals(lines, targets)
        if not value:
            return None, ("у list_content в строках нет литералов `СписокВыбора.Добавить(\"…\")`, и value пусто: напишите value — значения словами (список из литералов навык собирает сам, "
                          "value тогда не нужно)")
    if kind == "value" and value.strip() and '"' not in value and f'"{value.strip()}"' in quote and module.value_of(value) is None:
        value = f'"{value.strip()}"'        # value без кавычек, совпадающее со строковым литералом цитаты, — текст, а не выражение
    condition = note.get("condition", "")
    if not isinstance(condition, str):
        return None, "condition — строка (пусто — безусловно)"
    message = note.get("message", "")
    if kind == "open_refused" and (not isinstance(message, str) or "message" not in note):
        return None, "у open_refused нужно message — сообщение, которое код показывает при отказе (пустая строка, если код отказывает молча)"
    if kind != "open_refused" and "message" in note:
        return None, "message бывает только у open_refused"
    group = note.get("exclusive_group", "")
    if not isinstance(group, str):
        return None, "exclusive_group — строка (имя места, где варианты разных элементов; у вариантов одного свойства одной цели не нужен)"
    default = note.get("default", False)
    if not isinstance(default, bool):
        return None, "default — true или false"
    why_text = note.get("why", "")
    if kind == "other" and not (isinstance(why_text, str) and why_text.strip()):
        return None, "у записи other нужно why — что код делает и почему это не записано иначе"
    event, effects = "", []
    if kind == "collapse" and value.strip() not in COLLAPSE_MODES:
        return None, f"у записи collapse value — режим свёртки из {', '.join(COLLAPSE_MODES)}, а не «{value.strip()}»"
    if kind == "collapse" and targets.names.item_of[target["element"]].type != "Panel":
        return None, "свёртка бывает у панели"
    if kind == "value":
        why = _value_target(target, targets)
        if why:
            return None, why
    source, why = _source(note, kind, targets)
    if why:
        return None, why
    alias, why = _alias(note, kind, target, quote, targets)
    if why:
        return None, why
    bound = source["quote"] if source else quote            # слово действия стоит там, где действие: в `source`, если запись о другом модуле
    if name_expr:
        why = _name_expr(name_expr, target, bound, targets)
        if why:
            return None, why
    masked = _masked(targets.scanned(), lines)
    if source:          # слово действия ищется в коде обеих цитат: строки вызова в модуле формы и строк `source`
        masked += " " + _masked(scan.scan(targets.source_text(source["file"])[1]), source["lines"])
    why = _bound(note, kind, target, bound, targets, quote + "\n" + bound if source else None, masked, lines, alias)       # последним среди проверок записи: сначала схема, потом привязка к коду
    if why:
        return None, why
    why = _meaning(kind, target, lines, targets, masked, bool(source))
    if why:
        return None, why
    if kind != "other":
        why = unreachable_branch(lines, targets)
        if why:
            return None, why
    if kind == "appearance":
        why = absent_cell(target, bound, targets)
        if why:
            return None, why
    if kind in ("title", "value") and value.strip():
        why = _stub_value(kind, value, lines, targets, source)
        if why:
            return None, why
        if not (isinstance(why_text, str) and why_text.strip()) and (_is_expression(value.strip()) if kind == "title" else module.value_of(value) is None):
            return None, (f"{kind} «{shorten(value.strip(), 50)}» записан выражением кода: нужен why — смысл словами для досье (досье печатает его вместо выражения: "
                          "«Склад: склад сотрудника текущего пользователя (задаёт код)»)")
    if kind in VISUAL_KINDS:
        user = targets.user_only(lines[0])
        if user:
            return None, (f"это происходит по событию «{user['event']}» ({user['where']}), а не при открытии: вид формы записывают только для открытия (тело модуля, ПередОткрытием, ПриОткрытии, "
                          "ОбновлениеОтображения и что они вызывают), а перемены по действию — on_event с event «" + str(user["event"]) + "» и эффектом {\"what\": \"" + _STATE_WHAT.get(kind, "other")
                          + "\", \"affects\": [" + ('"Панель/Страница"' if kind == "current_page" else "имя") + "]}" + ("; одна запись на переход, условие перехода — в condition" if kind == "current_page" else ""))
    if kind in VISUAL_KINDS:
        why = _flag_gate(lines, targets, source)
        if why:
            return None, why
    if kind == "on_event":
        event, effects, why = _on_event(note, target, lines, targets, quote, source)
        if why:
            return None, why
        if not source and any(e["what"] == "refuse" for e in effects):
            why = _refusal_without_param(lines, targets, masked)
            if why:
                return None, why
    none_signs = _none_signs(event, effects, target, targets) if kind == "on_event" else ""
    user_only = targets.user_only(lines[0]) is not None
    return {"kind": kind, "target": target, "value": value.strip(), "condition": condition.strip(), "message": message.strip() if message else "",
            "names_note": list(targets.case_notes), "alias": alias, "none_signs": none_signs,
            "group": group, "default": default, "lines": lines, "quote": quote.strip(), "why": why_text.strip() if why_text else "",
            "form_work": kind == "other" and target["kind"] == "form" and user_only,          # форма делает сама по таймеру или действию: «Что это за форма», а не «При открытии»
            "event": event, "effects": effects, "source": source, "name_expr": name_expr.strip() if name_expr else "", "order": targets.order_key(lines[0]), "user_only": user_only,
            "opening": targets.at_opening(lines[0])}, None


VALUE_TYPES = ("TextBox", "ComboBox", "CheckBox", "RadioButton", "Label")      # поля, у которых есть значение из данных; текст надписи без данных — `title`


def _value_target(target, targets):
    """Причина отказа записи `value`, если цель не поле с привязкой данных: значение поля — значение данных, на которые поле привязано (без привязки поле ничего не показывает)."""
    item = targets.names.item_of.get(target["element"])
    if item is None or item.type not in VALUE_TYPES:
        return f"value бывает у поля ввода, поля выбора, флажка, переключателя и надписи с данными, а «{target['element']}» — {item.type if item is not None else 'не элемент'}"
    if targets.field_data is not None and target["element"] not in targets.field_data:
        return (f"у «{target['element']}» нет привязки к реквизиту: value — значение данных поля; текст надписи без данных — title, цвет и шрифт — appearance, "
                "а присваивание реквизиту без поля записи не требует")
    return None


_STATE_WHAT = {"visibility": "visibility", "enabled": "enabled", "read_only": "read_only", "checked": "checked", "value": "value", "collapse": "collapse", "current_page": "current", "current_element": "current"}


_FLAG_COND = re.compile(rf"^\s*(?:НЕ\s+)?(?P<flag>{scan.NAME})\s*$", re.I)
_FALSE_RHS = re.compile(r"^\s*(?:Ложь|Неопределено|Null|0|\"\")\s*$", re.I)


def _split_args(text):
    """Аргументы вызова по запятым верхнего уровня."""
    out, depth, start = [], 0, 0
    for at, ch in enumerate(text):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "," and depth == 0:
            out.append(text[start:at])
            start = at + 1
    return out + [text[start:]]


def _source_flag(lines, source, targets):
    """Переменная модуля формы, которую вызов передаёт параметру-флагу в условии строки `source` (процедура чужого модуля: `Если Флаг Тогда`, а в вызове стоит `мФлаг`); `None` — условие иное
    или аргумент не имя."""
    _path, text, _why = targets.source_text(source["file"])
    if text is None:
        return None
    src_lines = scan.scan(text)
    match = _FLAG_COND.match(scan.conditions(src_lines).get(source["lines"][0], ""))
    proc = next((p for p in scan.procedures_of(src_lines) if p[2] <= source["lines"][0] <= (p[3] if p[3] is not None else p[2])), None)
    if not match or proc is None:
        return None
    params = [x.casefold() for x in proc[1]]
    if match.group("flag").casefold() not in params:
        return None
    index = params.index(match.group("flag").casefold())
    for number, _masked, raw in targets.scanned():
        if lines[0] <= number <= lines[1]:
            for hit in re.finditer(rf"(?<![\wА-Яа-яЁё]){re.escape(proc[0])}\s*\(", raw):
                args = _split_args(scan.call_args(raw, hit.end()) or "")
                if index < len(args) and re.fullmatch(scan.NAME, args[index].strip()):
                    return args[index].strip()
    return None


def _flag_gate(lines, targets, source=None):
    """Причина отказа записи вида формы при открытии, если её условие — одна переменная модуля, которой открытие не ставит: никто (ветка не выполняется) или только обработчик действия
    (тогда перемена — действие: `on_event` того обработчика). Условие записи о чужом модуле (`source`) — параметр-флаг: берётся переменная, которую передаёт вызов. Переменная с `Экспорт` и
    реквизит формы — не флаг модуля: их ставит иной код."""
    if source:
        flag = _source_flag(lines, source, targets)
        if flag is None or not targets.at_opening(lines[0]):
            return None
        match = _FLAG_COND.match(flag)
    else:
        cond = scan.conditions(targets.scanned()).get(lines[0], "")
        match = _FLAG_COND.match(cond)
        if not match or not targets.at_opening(lines[0]):
            return None
    flag = match.group("flag")
    key = flag.casefold()
    text = targets.module_text or ""
    if re.search(rf"(?i)Перем\b[^;]*(?<![\wА-Яа-яЁё]){re.escape(flag)}(?![\wА-Яа-яЁё])[^;]*Экспорт", text):
        return None
    if key not in {v.casefold() for v in module_variables_of(targets)}:
        return None
    sets = []
    for number, masked, raw in targets.scanned():
        for hit in re.finditer(rf"(?<![\wА-Яа-яЁё.]){re.escape(flag)}\s*=(?![=>])\s*([^;]*)", raw):
            if not _FALSE_RHS.match(hit.group(1)) and not re.match(r"\s*(?:Перем)\b", masked):
                sets.append(number)
    if not sets:
        return (f"условие записи — переменная модуля «{flag}», а ни одна строка модуля формы не ставит её в значение, отличное от Ложь: ветка не выполняется, записи нет")
    if not any(targets.at_opening(n) for n in sets):
        owner = targets.procedure_name(sets[0])
        return (f"условие записи — переменная модуля «{flag}», которую ставит только обработчик действия ({owner or 'тело модуля'}, строка {sets[0]}): перемена зависит от действия, а не от открытия — "
                f"запишите on_event того обработчика с эффектом, а при открытии записи нет")
    return None


def module_variables_of(targets):
    """Переменные модуля формы (`Перем …` и присвоенные в теле) без реквизитов и элементов."""
    from . import moduleview
    return moduleview.module_variables(targets.module_text or "", list(targets.known) + list(targets.data_names))




LIST_ADD = re.compile(r"СписокВыбора\s*\.\s*Добавить\s*\(\s*(?P<first>\"(?:[^\"]|\"\")*\"|[-\d.]+)\s*(?:,\s*(?P<second>\"(?:[^\"]|\"\")*\"))?", re.I)


def _list_literals(lines, targets):
    """Значения списка выбора из литералов в строках `lines`: `СписокВыбора.Добавить("Значение"[, "Представление"])` — представление, если есть, иначе значение; через «; »."""
    text = " ".join(raw for n, _m, raw in targets.scanned() if lines[0] <= n <= lines[1])
    found = []
    for hit in LIST_ADD.finditer(text):
        word = (hit.group("second") or hit.group("first")).strip()
        found.append(word[1:-1].replace('""', '"') if word.startswith('"') else word)
    return "; ".join(dict.fromkeys(found))


REFUSAL = re.compile(r"(?<![\wА-Яа-яЁё.])Отказ\s*=\s*Истина", re.I)
REMOVE_ONE = re.compile(r"Кнопки\s*\.\s*Удалить", re.I)


def _refusal_without_param(lines, targets, masked):
    """Причина отказа записи, которая утверждает отказ (`open_refused`, эффект `refuse`): `Отказ = Истина` стоит в процедуре без параметра `Отказ` — локальная переменная. У `other`
    и прочих эффектов `on_event` проверки нет: там запись как раз и говорит, что форма не откажет."""
    if not REFUSAL.search(masked):
        return None
    params = targets.procedure_params(lines[0])
    if params is None or _word_in("Отказ", params):
        return None
    owner = targets.procedure_name(lines[0])
    return (f"«Отказ = Истина» стоит в процедуре «{owner}», у которой нет параметра Отказ ({params or 'параметров нет'}): это обычная переменная, форма от неё не откажет и не отменится. "
            "Отказ бывает в событии с параметром Отказ (ПередОткрытием, ПередЗакрытием, ПриНачалеРедактирования, ПередУдалением, …); здесь запишите то, что код делает на самом деле "
            "(other с причиной «форма откроется, пользователь увидит только предупреждение» либо on_event с эффектом message)")


def _meaning(kind, target, lines, targets, masked, foreign):
    """Причина отказа записи, у которой цитата на месте, а смысл не сходится с кодом, иначе `None`: `Отказ = Истина` в процедуре без параметра `Отказ` (локальная переменная, форма от неё не
    откажет) и `Кнопки.Удалить(…)` с целью-панелью (удалена одна кнопка, а не панель)."""
    if kind == "open_refused" and not foreign:
        why = _refusal_without_param(lines, targets, masked)
        if why:
            return why
    if kind == "removed" and target["kind"] == "element" and not _word_in("Очистить", masked):
        item = targets.names.item_of.get(target["element"])
        if item is not None and item.type == "CommandBar" and REMOVE_ONE.search(masked):
            return ("`Кнопки.Удалить(…)` убирает одну кнопку панели, а не панель: цель — {\"button\": [панель, имя кнопки]} (имя — по файлу формы, если код называет его через переменную, "
                    "прочитайте её), а если имя кнопки узнать нельзя — other с причиной. Цель-панель у removed — только для `Кнопки.Очистить()` со value «все кнопки»")
    return None


NOT_AN_EFFECT = re.compile(r"^\s*(?:Возврат\b.*|СтандартнаяОбработка\s*=.*|(?:Процедура|Функция)\b.*|Конец(?:Процедуры|Функции|Если|Цикла|Попытки)\b.*|Иначе\s*|Попытка\s*|Исключение\s*)$", re.I)
WINDOW_WORD = re.compile(r"Сообщ|Предупрежд|Вопрос|Состояни|Открыт|Показ|Выбра|Выбор|Ввод|Диалог|Печат|Оповест|Исключени", re.I)          # корни слов окна и сообщения: подходят и обёртки конфигурации с приставкой (`ПрефиксСообщить`)
WINDOW_WHAT = ("message", "open_form")


def _not_an_effect(quote):
    """Цитата `on_event` — не эффект: все её строки (без комментариев) — `Возврат;`, `СтандартнаяОбработка = …`, заголовок процедуры, `КонецЕсли`, `Иначе`."""
    rows = [x for x in (strip_comment(line) for line in quote.split("\n")) if x]
    return bool(rows) and all(NOT_AN_EFFECT.match(x) for x in rows)


NO_ASK_PARAM = re.compile(r"Не(?:Спрашивать|Запрашивать|Подтвержд)|БезВопрос|БезЗапрос|БезПодтвержд|Молча", re.I)          # параметр «не показывать вопрос»


def _silenced_window(lines, source, targets):
    """`(процедура, параметр)`, если вызов в `lines` передаёт литерал `Истина` параметру «не спрашивать» процедуры из `source`, где стоит окно: вопрос с таким вызовом не показывают (флаг не литерал — вопрос возможен)."""
    try:
        text = targets.source_text(source["file"])[1]
    except (KeyError, TypeError):
        return None
    first = source["lines"][0]
    owner = next((p for p in scan.procedures_of(scan.scan(text)) if p[2] <= first <= (p[3] if p[3] is not None else p[2])), None)
    if owner is None:
        return None
    flags = [(i, str(p).strip()) for i, p in enumerate(owner[1]) if NO_ASK_PARAM.search(str(p))]
    if not flags:
        return None
    code = " ".join(raw for n, _m, raw in targets.scanned() if lines[0] <= n <= lines[1])
    for call in re.finditer(rf"(?<![\wА-Яа-яЁё.])(?:[\wА-Яа-яЁё]+\s*\.\s*)?{re.escape(owner[0])}\s*\(", code, re.I):
        args, depth, current = [], 1, ""
        for char in code[call.end():]:
            depth += (char == "(") - (char == ")")
            if depth == 0:
                break
            if char == "," and depth == 1:
                args.append(current.strip())
                current = ""
            else:
                current += char
        args.append(current.strip())
        for index, name in flags:
            if index < len(args) and args[index].casefold() == "истина":
                return owner[0], name
    return None


def _window_in(text, lines, targets):
    """В тексте строк стоит слово окна или сообщения либо вызов процедуры модуля формы, где оно стоит (любой глубины)."""
    if WINDOW_WORD.search(text):
        return True
    ranges = targets.procedure_ranges()
    scanned = targets.scanned()
    for name in targets.reach([n for n in ranges if _calls_name(text, n)]):
        a, b = ranges[name]
        if any(a < n <= b and WINDOW_WORD.search(m) for n, m, _r in scanned):
            return True
    return False


def _on_event(note, target, lines, targets, quote="", source=None):
    """`(событие, эффекты, причина отказа)` записи `on_event`: событие есть у цели в файле формы, строки — в процедуре обработчика или в вызываемых ею, эффекты названы по словарю
    и называют то, что есть на форме или в данных; цитата стоит на строке видимого эффекта или вызова процедуры, которая его делает (не `Возврат;`, не заголовок процедуры)."""
    event = note.get("event")
    if not isinstance(event, str) or not event.strip():
        return None, None, "у on_event нужно event — имя события из файла формы"
    event = event.strip()
    rows = targets.event_rows(target)
    if rows is not None:
        mine = [r for r in rows if event.casefold() in (str(r["event"]).casefold(), str(r["code"]).casefold())]
        if not mine:
            return None, None, f"в файле формы у цели нет события «{event}» с обработчиком (есть: {', '.join(sorted({str(r['event']) for r in rows})) or 'нет'})" + targets.event_owners(event)
        ranges = []
        for row in mine:
            ranges += targets.reachable(row["procedure"])
        if not any(first <= lines[0] and lines[1] <= last for first, last in ranges):
            return None, None, (f"строки {lines[0]}–{lines[1]} лежат вне процедуры обработчика ({', '.join(sorted({r['procedure'] for r in mine}))}) и процедур, которые она вызывает")
    effects = note.get("effects")
    if not isinstance(effects, list) or not effects:
        return None, None, "у on_event нужен непустой список effects: [{what, affects, text}] (и необязательное condition — условие именно этого эффекта)"
    out = []
    for at, effect in enumerate(effects, 1):          # номер эффекта в отказах — с единицы
        if not isinstance(effect, dict):
            return None, None, f"effects[{at}] (счёт с единицы) — словарь {{what, affects, text}}"
        extra = sorted(set(effect) - EFFECT_KEYS)
        if extra:
            return None, None, f"effects[{at}]: ключи вне схемы: {', '.join(extra)}"
        if effect.get("what") not in WHAT:
            return None, None, f"effects[{at}].what «{effect.get('what')}» не из словаря ({', '.join(WHAT)})"
        affects, text = effect.get("affects", []), effect.get("text", "")
        if not isinstance(affects, list) or any(not isinstance(a, str) or not a.strip() for a in affects):
            return None, None, f"effects[{at}].affects — список имён"
        if not isinstance(text, str) or (not text.strip() and effect["what"] == "other"):
            return None, None, f"effects[{at}].text — краткое описание (у what «other» обязательно)"
        condition = effect.get("condition", "")
        if not isinstance(condition, str):
            return None, None, f"effects[{at}].condition — строка (когда условен именно этот эффект; пусто — условие записи или безусловно)"
        unknown = [a for a in affects if not targets.known_name(a)]
        if unknown:
            local = [a for a in unknown if re.fullmatch(scan.NAME, a.strip()) and a.strip().casefold() in targets.known_words()]
            if local:
                return None, None, (f"effects[{at}].affects: {', '.join('«' + a + '»' for a in local)} — переменная модуля, а не поле или реквизит формы: на экран она попадает через поле — "
                                    "назовите это поле или скажите словами в text (affects пустой)")
            return None, None, (f"effects[{at}].affects называет то, чего нет на форме и в данных: {', '.join('«' + a + '»' for a in unknown)} "
                                "(путь проверяется по всем звеньям; имя, которое создаёт код, — после принятой записи created)")
        clean = [a.strip().split("/")[-1].strip() if "/" in a else a.strip() for a in affects]          # `Панель/Дерево` — тот же элемент, что `Дерево`: в досье его короткое имя
        out.append({"what": effect["what"], "affects": clean, "text": text.strip(), "condition": condition.strip(), "pages": _pages_of(effect["what"], affects, targets),
                    "fields": [a for a in clean if a.split(".")[-1].strip().casefold() in targets.fields],
                    "data": [a for a in clean if a.split(".")[-1].strip().casefold() not in targets.fields]})
    if any(e["what"] != NO_EFFECT for e in out) and _not_an_effect(quote):
        return None, None, (f"цитата «{shorten(quote.strip(), 50)}» — не эффект (возврат, стандартная обработка, заголовок процедуры): цитата записи on_event стоит на строке видимого "
                            "эффекта — окна, сообщения, присваивания полю — или вызова процедуры, которая его делает; имя цели в ней не нужно")
    shown = [e["what"] for e in out if e["what"] in WINDOW_WHAT]
    if shown:
        text = _masked(targets.scanned(), lines)
        if source:
            text += " " + (source["quote"] if isinstance(source, dict) else "")
        silenced = _silenced_window(lines, source, targets) if source and "message" in shown else None
        if silenced:
            return None, None, (f"у эффекта «message» вопрос не показывается: вызов {silenced[0]} передаёт параметру «{silenced[1]}» литерал Истина: вопрос с таким флагом "
                                "не показывают — уберите эффект «message» (флаг не литерал — оставьте)")
        if not _window_in(text, lines, targets):
            near = _nearest_window(lines, targets)
            return None, None, (f"расширьте lines до строки окна: у эффекта «{shown[0]}» в строках {lines[0]}–{lines[1]} и в процедурах модуля формы, которые они вызывают, нет Предупреждение, Вопрос, Сообщить, "
                                "Состояние, Открыть…"
                                + (f"; ближайшая строка окна в этой процедуре или вызываемых — {near}, например lines [{min(lines[0], near)}, {max(lines[1], near)}]" if near else "")
                                + "; окно в процедуре другого модуля — вызов в lines и source; окна нет — уберите эффект «" + shown[0] + "»")
    return event, out, None


def _pages_of(what, affects, targets):
    """`[(панель, страница)]` — страницы панелей, которые эффект `current` называет путём `Панель/Страница`: по ним досье строит картинку экрана. Имя без панели страницей панели не считается."""
    if what != "current":
        return []
    out = []
    for given in affects:
        parts = [x.strip() for x in given.split("/")]
        if len(parts) != 2:
            continue
        panel, _why = targets.element(parts[0], False)
        if panel in targets.names.item_of and parts[1].casefold() in targets.pages.get(panel, ()):
            out.append((panel, parts[1]))
    return out


def _nearest_window(lines, targets):
    """Номер ближайшей к `lines` строки окна или сообщения в той же процедуре модуля формы и в процедурах, которые она вызывает; `None` — такой строки там нет."""
    ranges = targets.procedure_ranges()
    owner = targets.owner_of(lines[0])
    spans = [ranges[n] for n in targets.reach([owner])] if owner else []
    found = [n for n, masked, _raw in targets.scanned() if WINDOW_WORD.search(masked) and not re.match(r"\s*(?:Процедура|Функция)\b", masked, re.I) and any(a <= n <= b for a, b in spans)]
    return min(found, key=lambda n: min(abs(n - lines[0]), abs(n - lines[1]))) if found else None


def _none_signs(event, effects, target, targets):
    """Слова признаков частности, если запись говорит «на экране ничего не меняет» (все эффекты `none`), а в процедуре обработчика они есть; иначе пустая строка."""
    if not effects or any(e["what"] != NO_EFFECT for e in effects):
        return ""
    rows = targets.event_rows(target) or []
    signs = []
    for row in rows:
        if event.casefold() in (str(row["event"]).casefold(), str(row["code"]).casefold()):
            signs += targets.signs(str(row["procedure"]))
    return hd.signs_text(signs) if signs else ""


def event_links(accepted):
    """Связи «поле → поля» по записям `on_event`: `[{source, event, targets: [имена], data: [имена], what: [слова], lines, condition}]`. `targets` — только то, что на форме видно
    полем (элемент, колонка, кнопка), без самого источника: переименование или удаление такого поля ломает связь; `data` — реквизиты формы и объекта, которые обработчик меняет
    (их имена не меняют без правки кода). Запись без полей-приёмников связью не считается. `pairs` — пары «эффект → его приёмники» по эффектам записи: слова эффекта (`word`), текст
    модели (`text`) и приёмники именно этого эффекта (`fields` — поля, `data` — данные); виды и приёмники разных эффектов записи не склеиваются."""
    out = []
    for note in accepted:
        if note["kind"] != "on_event":
            continue
        shown = [e for e in note["effects"] if e["what"] != NO_EFFECT]
        if not shown:
            continue
        note = dict(note, effects=shown)
        t = note["target"]
        source = "форма" if t["kind"] == "form" else t["element"] if t["kind"] == "element" else f"{t['element']}/{t['sub']}"
        own = {x.casefold() for x in ((t["element"] or "").split(".")[-1].split("/")[-1], t["sub"] or "") if x}
        names = [a for a in dict.fromkeys(a for e in note["effects"] for a in e["fields"]) if a.split(".")[-1].strip().casefold() not in own]
        if not names:
            continue
        data = list(dict.fromkeys(a for e in note["effects"] for a in e["data"]))
        pairs = [{"what": e["what"], "word": WHAT_WORDS[e["what"]], "text": e.get("text", ""), "condition": e.get("condition", ""), "fields": [a for a in e["fields"] if a in names], "data": list(e["data"])}
                 for e in note["effects"]]
        out.append({"source": source, "event": note["event"], "targets": names, "data": data, "what": list(dict.fromkeys(WHAT_WORDS[e["what"]] for e in note["effects"])),
                    "pairs": pairs, "lines": list(note["lines"]), "condition": note["condition"]})
    return out


def events(accepted):
    """Записи `on_event` для раздела «Поведение при работе»: `[{source, event, effects, condition, lines}]` в порядке файла записей."""
    out = []
    for note in accepted:
        if note["kind"] == "on_event" and any(e["what"] != NO_EFFECT for e in note["effects"]):          # `what: none` — обработчик разобран, на экране ничего: в обзор не идёт
            t = note["target"]
            out.append({"source": "форма" if t["kind"] == "form" else t["element"] if t["kind"] == "element" else f"{t['element']}/{t['sub']}",
                        "event": note["event"], "effects": [e for e in note["effects"] if e["what"] != NO_EFFECT], "condition": note["condition"], "lines": list(note["lines"])})
    return out


LOG_FILE = "code-notes.log"


def log_build(out_dir, accepted, rejected, unparsed=0, now=None):
    """Дописывает в `code-notes.log` рядом с досье строку одной сборки `--code-notes`: номер сборки, время, принято (записей файла, не целей), отклонено и их номера, число «не разобран».
    По журналу считается «с первого раза» — доля записей, принятых первой же сборкой, а не пересказ модели. Возвращает путь файла."""
    import datetime
    path = pathlib.Path(out_dir) / LOG_FILE
    try:
        number = len(path.read_text(encoding="utf-8").splitlines()) + 1
    except OSError:
        number = 1
    bad = sorted({r["index"] for r in rejected})
    row = (f"{number}\t{(now or datetime.datetime.now()).isoformat(timespec='seconds')}\tпринято {len({a['index'] for a in accepted if 'index' in a})}"
           f"\tотклонено {len(bad)}" + (" (" + ", ".join(str(i) for i in bad) + ")" if bad else "") + f"\tне разобран {unparsed}\n")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(row)
    return path


CREDENTIAL = re.compile(r"(?i)\b(pass"
                        r"word|pwd|user\s*id|userid|uid|пароль)(\s*=\s*)(\"[^\"]*\"|'[^']*'|[^;\s,\"']+)")


def _mask(text):
    return CREDENTIAL.subn(lambda m: m.group(1) + m.group(2) + "***", text)


def mask_credentials(value):
    """Учётные данные из строк записей и модуля (`Pwd=…`, `User ID=…`, `UID=…`) заменяет на `***` на месте; возвращает число замен.
    Досье учётных данных не переносит: пароль из строки соединения в модуле не должен попасть ни в `brief.md`, ни в `brief.json`."""
    count = 0
    items = value.items() if isinstance(value, dict) else enumerate(value) if isinstance(value, list) else ()
    for key, item in list(items):
        if isinstance(item, str):
            new, n = _mask(item)
            if n:
                value[key] = new
                count += n
        else:
            count += mask_credentials(item)
    return count


DEFAULT_KEYS = frozenset({"kind", "handlers"})


def check_default(note, targets):
    """`(принятая запись, причина отказа)` записи `default`: `{kind, handlers, categories}` — процедуры-обработчики, которые модель считает умолчанием (запись о них не нужна); категорию каждой
    определяет навык (`handler_defaults.guess_category`). Принимается каждая процедура, в которой нет признака частности (`handler_defaults.find_signs`); остальные названы в причине со строкой
    и признаком, а принятые остаются. Обе части могут быть заполнены. Ключ `category` прежних записей отбрасывается (`legacy`)."""
    if "category" in note:
        targets.dropped_now.add("category")
        note = {k: v for k, v in note.items() if k != "category"}
    extra = sorted(set(note) - DEFAULT_KEYS)
    if extra:
        return None, f"ключи вне схемы: {', '.join(extra)} (запись default — только kind и handlers)"
    names = note.get("handlers")
    if not isinstance(names, list) or not names or any(not isinstance(x, str) or not x.strip() for x in names):
        return None, "handlers — непустой список имён процедур-обработчиков из таблицы событий задания"
    ranges = targets.procedure_ranges()
    procs = targets.handler_procs() if targets.handlers is not None else {k: k for k in ranges}
    skill = targets.skill_defaults()
    ok, reasons, categories = [], [], {}
    for given in dict.fromkeys(x.strip() for x in names):
        key = given.casefold()
        if key not in ranges:
            reasons.append(f"«{given}»: такой процедуры в модуле формы нет")
        elif key not in procs:
            reasons.append(f"«{given}»: не обработчик (в файле формы нет события или кнопки с этой процедурой, код её к кнопке не привязывает); обработчиками считаются процедуры из таблицы задания")
        elif key in skill:
            ok.append(procs[key])
            categories[key] = skill[key]
        else:
            row = (targets.handler_events().get(key) or [{}])[0]
            category = hd.guess_category(targets, given, row.get("owner"), row.get("event") or "")
            signs = targets.signs(given, category)
            if not signs and category == "silent" and hd.unchecked_reason(targets, given):
                category = "unchecked"          # признаков не нашли, но процедура зовёт код, которого навык не разобрал: «без видимого следа» он не скажет
            if signs:
                words = "; ".join(dict.fromkeys(f"{x['sign']}: {hd.SIGN_WORDS[x['sign']]}" for x in signs))
                opening = any(r["owner"] == "form" and str(r["event"]).casefold().replace(" ", "") in hd.OPEN_EVENTS for r in targets.handler_events().get(key, ()))
                what = ("запишите её on_event этого события: цель {\"form\": true}, event — имя события, эффект value с affects — реквизитом, который оно ставит (если оно меняет вид формы — записью "
                        "нужного вида)" if opening else "запишите её on_event или записью нужного вида")
                reasons.append(f"в {procs[key]} — {hd.signs_text(signs)}: это частность ({words}); {what}")
            else:
                ok.append(procs[key])
                categories[key] = category
    done = {"kind": "default", "handlers": ok, "categories": categories} if ok else None
    return done, ("; ".join(reasons) if reasons else None)


TARGETS_KINDS = ("visibility", "enabled", "read_only")
TARGET_LIST_HINT = 'target — цель {"element": имя} или список целей [{"element": "А"}, {"page": ["Панель", "Стр"]}] (короткое имя элемента можно строкой: ["А", "Б"])'


def _target_list(note):
    """Список целей записи: `target` — список либо прежний ключ `targets`; `None` — запись об одной цели. `([цели], причина)` для списка."""
    if "targets" in note and "target" in note:
        return None, 'ключи target и targets вместе не бывают: список целей — значение target'
    given = note["targets"] if "targets" in note else note.get("target")
    if not isinstance(given, list):
        return None, None
    return given, None


def _expand_targets(note, targets):
    """`([принятые записи по целям], причина отказа)` записи со списком целей (`visibility`, `enabled`, `read_only`): одно значение, условие и цитата на несколько целей. Цель — словарь
    или короткое имя элемента строкой. Каждая цель проверяется как отдельная запись с теми же строками и цитатой (имя цели стоит в цитате либо цель называет индекс `Колонки[0]`); хотя бы одна
    отказала — отказывает вся запись, причина называет цель. У явной `exclusive_group` своё имя на каждую цель: «<имя>: <цель>»."""
    given, why = _target_list(note)
    if why:
        return None, why
    if note.get("kind") not in TARGETS_KINDS:
        return None, f"список целей бывает у видов {', '.join(TARGETS_KINDS)}; у «{note.get('kind')}» одна запись — одна цель, повторите запись для каждой"
    if not given or any(not isinstance(t, (dict, str)) or (isinstance(t, str) and not t.strip()) for t in given):
        return None, TARGET_LIST_HINT
    given = [{"element": t.strip()} if isinstance(t, str) else t for t in given]
    seen = [json.dumps(t, sort_keys=True, ensure_ascii=False) for t in given]
    if len(set(seen)) != len(seen):
        return None, f"в списке целей «{_target_word(given[next(i for i, x in enumerate(seen) if seen.count(x) > 1)])}» дважды: уберите повтор"
    base = {k: v for k, v in note.items() if k not in ("target", "targets")}
    out = []
    for at, one in enumerate(given, 1):
        record = dict(base, target=one)
        if base.get("exclusive_group"):
            record["exclusive_group"] = f"{base['exclusive_group']}: {_target_word(one)}"
        done, why = check_one(record, targets)
        if why:
            return None, f"цель {at} ({_target_word(one)}): {why}" + ("; у списка целей цитата называет каждую цель: возьмите строки, где названа каждая" if "имени цели" in why else "")
        out.append(done)
    return out, None


def _target_word(target):
    """Цель одним словом для имени группы и причины отказа: `Час`, `Панель/Кнопка`."""
    (key, value), = target.items() if isinstance(target, dict) and len(target) == 1 else [("?", "?")]
    return "/".join(str(x) for x in value) if isinstance(value, list) else str(value)


def check(notes, targets):
    """`(принятые, отклонённые)`; отклонённая — `{"index": номер с единицы, "kind", "why", "note"}`. Принятые идут в порядке файла. Записи `default` в принятые не входят:
    они ложатся в `targets.default_notes` (`{index, handlers, categories}`), отклонённые процедуры — в отклонённые. После проверки навык собирает сам: группы вариантов (`_auto_groups`),
    запись об отключённом стандартном действии (`_disabled_notes`), снимает с умолчаний процедуры, до которых дотягивается принятая запись (`_drop_covered_defaults`)."""
    results = {}
    targets.created = set()
    targets.default_notes = []
    targets.dropped = {}

    def run(at, note):
        targets.dropped_now = set()
        if isinstance(note, dict) and note.get("kind") == "default":
            done, why = check_default(note, targets)
            if done:
                targets.default_notes.append(dict(done, index=at))
            results[at] = ([], {"index": at, "kind": "default", "why": why, "note": note} if why else None)
        else:
            if isinstance(note, dict) and (isinstance(note.get("target"), list) or "targets" in note):
                note = legacy(note, targets)
                done, why = _expand_targets(note, targets)
            else:
                done, why = check_one(note, targets)
                done = [done] if done is not None else None
            if why:
                results[at] = ([], {"index": at, "kind": note.get("kind") if isinstance(note, dict) else None, "why": why, "note": note})
            else:
                for item in done:
                    item["index"] = at
                results[at] = (done, None)
                for item in done:
                    register(item)
        for key in targets.dropped_now:
            targets.dropped.setdefault(key, []).append(at)

    def register(done):
        if done["kind"] == "created":          # то, что код создаёт (колонка, элемент, кнопка), — имя, на которое могут ссылаться `affects`: только принятая запись его заводит
            target = done["target"]
            if target["kind"] == "button" and target["sub"]:
                targets.created.add((target["element"], tuple(x.casefold() for x in list(target.get("path") or []) + [target["sub"]])))
            if not done["name_expr"]:
                created = (target["sub"] if target["sub"] else target["element"]).casefold().split(".")[-1]
                targets.known.add(created)
                if target["kind"] != "page":
                    targets.fields.add(created)

    def of_kind(want):
        return [(at, n) for at, n in enumerate(notes, 1) if isinstance(n, dict) and n.get("kind") == want]
    first, later = of_kind("created"), of_kind("on_event")
    middle = [(at, n) for at, n in enumerate(notes, 1) if not isinstance(n, dict) or n.get("kind") not in ("created", "on_event")]
    for at, note in first:          # сначала созданное: на него ссылаются цели других записей (подменю, созданное кодом) и `affects`
        run(at, note)
    for at, note in middle:
        run(at, note)
    for at, note in later:          # on_event — после остальных: их `created` уже принят, и `affects` вправе назвать созданное ниже по файлу записей
        run(at, note)
    accepted = [item for at in sorted(results) for item in results[at][0]]
    rejected = [results[at][1] for at in sorted(results) if results[at][1] is not None]
    targets.default_notes.sort(key=lambda d: d["index"])
    _auto_groups(accepted, targets)
    _drop_covered_defaults(accepted, targets)
    accepted += _disabled_notes(accepted, targets)
    accepted += _object_values(accepted, targets)
    accepted += _spread_values(accepted, targets)
    return accepted, rejected


AUTO_GROUP_KINDS = ("visibility", "enabled", "read_only", "title", "current_page", "collapse", "checked")


def _target_key(target):
    return (target["kind"], target["element"], target["sub"], tuple(target.get("path") or ()))


def _auto_groups(accepted, targets):
    """Группы вариантов собирает навык: условные записи (и запись с `default`) одного вида об одной цели в одной процедуре — ветки Если/Иначе одного свойства, одна группа. Группа нужна, когда
    модель назвала вариант при открытии (`default`): рисунок применит его, остальные варианты останутся «как в файле». Явная `exclusive_group` (варианты РАЗНЫХ элементов на одном месте)
    не трогается; записи, которые модель в группу не поместила, и без `default` остаются как были."""
    buckets = {}
    for note in accepted:
        if note["group"] or note["kind"] not in AUTO_GROUP_KINDS or not (note["condition"] or note["default"]):
            continue
        buckets.setdefault((note["kind"], _target_key(note["target"]), targets.owner_of(note["lines"][0])), []).append(note)
    for (kind, _target, _owner), notes in buckets.items():
        if any(n["default"] for n in notes):
            name = f"{kind}: {_target_word_of(notes[0]['target'])} (строки {notes[0]['lines'][0]}–{max(n['lines'][1] for n in notes)})"
            for n in notes:
                n["group"] = name


def _target_word_of(target):
    """Цель принятой записи одним словом: `Поле`, `Таблица/Колонка`, `форма`."""
    if target["kind"] == "form":
        return "форма"
    return "/".join(x for x in ((target["element"] or "").split(".")[-1], target["sub"]) if x)


def _drop_covered_defaults(accepted, targets):
    """Процедура, до которой дотягивается принятая запись (сама или процедуры, которые она вызывает), из умолчаний снимается: запись — частность, умолчанием она быть не может."""
    if not targets.default_notes:
        return
    ranges = targets.procedure_ranges()
    for entry in targets.default_notes:
        keep = []
        for name in entry["handlers"]:
            spans = [ranges[n] for n in targets.reach([name.casefold()]) if n in ranges]
            if any(not n.get("source") and any(a <= n["lines"][0] and n["lines"][1] <= b for a, b in spans) for n in accepted if n["kind"] != "on_event" or any(e["what"] != NO_EFFECT for e in n["effects"])):
                continue
            keep.append(name)
        entry["handlers"] = keep
    targets.default_notes = [e for e in targets.default_notes if e["handlers"]]


def _disabled_notes(accepted, targets):
    """Записи `on_event` об обработчиках, которые только отключают стандартное действие (`СтандартнаяОбработка = Ложь` без замены): навык отмечает их сам, модели писать не нужно. Обработчик,
    о котором модель записала что-то своё, не трогается."""
    if targets.handlers is None:
        return []
    out = []
    for key, category in targets.skill_defaults().items():
        if category != "disabled":
            continue
        first, last = targets.procedure_ranges()[key]
        if any(not n.get("source") and first <= n["lines"][0] and n["lines"][1] <= last for n in accepted):
            continue
        for row in targets.handler_events().get(key, ()):
            target = _row_target(row)
            if target is None:
                continue
            quote = next((raw.strip() for n, m, raw in targets.scanned() if first <= n <= last and _STMT_OFF.search(m)), "СтандартнаяОбработка = Ложь;")
            line = next((n for n, m, _raw in targets.scanned() if first <= n <= last and _STMT_OFF.search(m)), first)
            out.append({"kind": "on_event", "target": target, "value": "", "condition": "", "message": "", "names_note": [], "alias": None, "none_signs": "",
                        "group": "", "default": False, "lines": [line, line], "quote": quote, "why": "", "form_work": False, "event": str(row["event"]),
                        "effects": [{"what": "other", "affects": [], "text": hd.CATEGORY_WORDS["disabled"], "condition": "", "fields": [], "data": []}], "source": None, "name_expr": "",
                        "order": targets.order_key(line), "user_only": targets.user_only(line) is not None, "opening": targets.at_opening(line), "index": 0, "auto": True})
    return out


OBJECT_BODY = "тело модуля объекта"
_BLOCK_OPEN = re.compile(r"^\s*(?:Если|Для|Пока|Попытка)(?![\wА-Яа-яЁё])", re.I)
_BLOCK_CLOSE = re.compile(r"^\s*Конец(?:Если|Цикла|Попытки)(?![\wА-Яа-яЁё])", re.I)
_BODY_ASSIGN = re.compile(rf"^\s*(?:(?:Объект|ЭтотОбъект)\s*\.\s*)?(?P<name>{scan.NAME})\s*=(?!=)\s*(?P<rhs>.+?)\s*;?\s*$")


def _object_values(accepted, targets):
    """Записи `value` из тела модуля объекта, которые навык делает сам: безусловное присваивание литерала (`Истина`, `Ложь`, число, строка) реквизиту объекта, к которому привязано поле формы,
    выполняется до открытия формы, и поле показывает это значение. Присваивание внутри `Если`, `Для`, `Пока`, `Попытка` и вне тела модуля не берётся; из нескольких побеждает последнее.
    Данные, для которых модель уже записала безусловное `value` или условное значение-литерал, не трогаются: её запись точнее; условное значение-выражение («сохранённые настройки») литерал тела не гасит — это значение первого открытия. Запись несёт номер строки модуля объекта в `object_line`, `lines` у неё `[0, 0]`
    (строки модуля формы она не покрывает)."""
    if not targets.object_module or not targets.field_data:
        return []
    try:
        text = pathlib.Path(targets.object_module).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return []
    lines = scan.scan(text)
    spans = [(first, last if last is not None else first) for _n, _p, first, last in scan.procedures_of(lines)]
    bound = {}
    for full, (kind, name) in targets.field_data.items():
        if kind == "object":
            bound.setdefault(name.casefold(), []).append(full)
    last, depth = {}, 0
    for number, masked, raw in lines:
        if any(a <= number <= b for a, b in spans) or not masked.strip():
            continue
        if _BLOCK_CLOSE.match(masked):
            depth = max(depth - 1, 0)
            continue
        if _BLOCK_OPEN.match(masked):
            depth += 1
            continue
        found = _BODY_ASSIGN.match(raw)
        if depth or not found or found.group("name").casefold() not in bound:
            continue
        literal_ = module.value_of(found.group("rhs"))
        if literal_ is None:
            last.pop(found.group("name").casefold(), None)        # последнее присваивание — выражение: итог при открытии неизвестен
        else:
            last[found.group("name").casefold()] = (number, found.group("rhs"), raw.strip())
    own = {targets.field_data[n["target"]["element"]][1].casefold() for n in accepted
           if n["kind"] == "value" and n["target"]["element"] in targets.field_data and (not n["condition"] or module.value_of(n["value"]) is not None)}
    out = []
    for name, (number, rhs, quote) in last.items():
        if name in own:
            continue
        for full in bound[name]:
            out.append({"kind": "value", "target": {"kind": "element", "element": full, "sub": None, "known": True}, "value": rhs, "condition": "", "message": "", "names_note": [],
                        "alias": None, "none_signs": "", "group": "", "default": False, "lines": [0, 0], "object_line": number, "quote": quote, "why": "", "form_work": False,
                        "event": "", "effects": [], "source": None, "name_expr": "", "order": (-1, number), "user_only": False, "opening": True, "index": 0, "auto": True,
                        "object_body": True})
    return out


def _spread_values(accepted, targets):
    """Значение данных видят все поля, привязанные к ним: переключатели группы, надпись с данными рядом с полем. Запись `value` на один элемент даёт копии на остальные элементы с теми же
    данными (`spread`); у элемента со своей записью `value` копия не нужна."""
    if not targets.field_data:
        return []
    by_data = {}
    for full, key in targets.field_data.items():
        if key[1]:
            by_data.setdefault((key[0], key[1].casefold()), []).append(full)
    has = {n["target"]["element"] for n in accepted if n["kind"] == "value"}
    out = []
    for note in list(accepted):
        if note["kind"] != "value" or note.get("spread") or not targets.field_data.get(note["target"]["element"], ("", ""))[1]:
            continue
        kind, name = targets.field_data[note["target"]["element"]]
        for full in by_data[(kind, name.casefold())]:
            if full != note["target"]["element"] and full not in has:
                out.append(dict(note, target=dict(note["target"], element=full), spread=True))
    return out


_STMT_OFF = re.compile(r"СтандартнаяОбработка\s*=\s*Ложь", re.I)


def _row_target(row):
    """Цель принятой записи по строке обработчика из файла формы: форма, элемент, колонка таблицы, кнопка панели; `None` — иное (кнопка, созданная кодом)."""
    owner = row.get("owner")
    if owner == "form":
        return {"kind": "form", "element": None, "sub": None}
    if owner == "element" and row.get("element"):
        return {"kind": "element", "element": row["element"], "sub": None, "known": True}
    if owner == "column" and row.get("table") and row.get("column"):
        return {"kind": "column", "element": row["table"], "sub": row["column"], "known": True}
    if owner == "panel" and row.get("bar") and row.get("button"):
        return {"kind": "button", "element": row["bar"], "sub": row["button"], "known": True}
    return None


def _group_default(note, single=False):
    """Вариант группы по заголовку, текущей странице или доступности, который форма показывает при открытии (`default: true`, `sure`): рисунок применяет его, остальные варианты группы названы
    в досье. Безусловным он не бывает — у него есть условие ветки, — поэтому его принимают за итог отдельным правилом. Видимость так же, если все записи группы — об одной цели
    («безусловно, а ниже перекрыто по условию»); у группы из разных элементов `default` только выбирает, кого рисовать на общем месте."""
    return bool(note["group"] and note["default"] and (note["kind"] in GROUP_APPLIED or (note["kind"] == "visibility" and single)))


def single_target_groups(accepted):
    """`{(группа, вид)}` групп, все записи которых описывают одну цель: значение `default` у такой группы — итог при открытии."""
    seen = {}
    for note in accepted:
        if note.get("group"):
            t = note["target"]
            seen.setdefault((note["group"], note["kind"]), set()).add((t["kind"], t["element"], t["sub"], tuple(t.get("path") or ())))
    return {key for key, targets in seen.items() if len(targets) == 1}


ROW_STYLE = re.compile(r"ОформлениеСтроки|ОформленияСтрок", re.I)


def _default_disagreements(groups):
    """Предупреждения о группах, которые делят условие, а вариант по умолчанию выбрали разный: две группы одной цели-выбора (закладки и поля одного вида операции) показывают при открытии
    один и тот же вариант условия. `groups` — `{(группа, вид): [записи]}`; условие варианта по умолчанию одной группы встречается в другой группе у записи без `default`."""
    defaults = {}
    for key, notes in groups.items():
        chosen = [n for n in notes if n["default"] and n["condition"]]
        if chosen:
            defaults[key] = {n["condition"].casefold() for n in chosen}
    out, said = [], set()
    for key, notes in groups.items():
        if key not in defaults:
            continue
        for other, others in groups.items():
            if other == key or other not in defaults or (other, key) in said:
                continue
            shared = {n["condition"].casefold() for n in notes if n["condition"]} & {n["condition"].casefold() for n in others if n["condition"]}
            if shared and (defaults[key] & shared) != (defaults[other] & shared):
                said.add((key, other))
                out.append(f"группы «{key[0]}» и «{other[0]}» делят условие (" + ", ".join(f"«{shorten(c, 40)}»" for c in sorted(shared)[:2]) + "), а default у них разный: при открытии верно одно условие — "
                           "default ставят варианту с одним и тем же условием")
    return out


def _numbers(indexes, limit=6):
    """Номера записей для предупреждения: первые `limit`, дальше «…»."""
    indexes = sorted(set(indexes))
    shown = ", ".join(str(i) for i in indexes[:limit])
    return shown + (f", … (всего {len(indexes)})" if len(indexes) > limit else "")


def warnings(accepted, targets=None):
    """Предупреждения о записях, которые приняты, но подозрительны: `[слова]`. Варианты разных групп с общим условием, у которых `default` разный. Оформление строк записано `on_event`. Запись
    «ничего не меняет», а в процедуре есть признак частности. С `targets` — ключи прежних записей, которые навык определяет сам (`DROPPED_KEYS`): одна строка на файл."""
    groups = {}
    for note in accepted:
        if note["group"]:
            groups.setdefault((note["group"], note["kind"]), []).append(note)
    out = []
    if targets is not None and targets.dropped:
        out.append("ключи больше не нужны, записи приняты без них: " + "; ".join(
            f"{key} (записи {_numbers(indexes)}) — {DROPPED_WHY[key]}" for key, indexes in targets.dropped.items()))
    out += _default_disagreements(groups)
    for note in accepted:
        if note["kind"] == "on_event" and ROW_STYLE.search(note["quote"]) and any(w in str(note["event"]).casefold().replace(" ", "") for w in ROW_EVENTS):
            out.append(f"запись {note['index']} (on_event «{note['event']}»): оформление строк таблицы (ОформлениеСтроки) записывают видом appearance с целью-таблицей или колонкой, а не on_event — "
                       "соответствие «условие строки → вид» тогда попадает в досье")
        if note.get("none_signs"):
            out.append(f"запись {note['index']} (on_event «{note['event']}»): записано «на экране ничего не меняет», а в процедуре есть признак частности — {note['none_signs']}: проверьте эффект по коду")
    if targets is not None:
        for key, name in targets.handler_procs().items():
            left = hd.uncovered_targets(targets, accepted, name)
            if left:
                out.append(f"обработчик {name}: цели из колонки «Видимые цели» задания не названы в записях — {', '.join(left)}: назовите их в affects (эффекты записей on_event) или в why напишите, что их не видно")
    return out


DROPPED_WHY = {"certainty": "рисунок применяет то, что обзор называет «при открытии»: литерал без условия и вариант с default; выражение не рисуется",
               "depends_on": "зависимость называет условие словами", "form_work": "запись other формы по таймеру или действию навык относит к «что форма делает сама» по графу вызовов",
               "category": "категорию умолчания определяет навык"}


def literal(value):
    """`Ложь`, `Истина` либо `None`: значение логического свойства, когда запись называет его прямо."""
    word = value.strip().casefold()
    return "Ложь" if word in FALSE_WORDS else "Истина" if word in TRUE_WORDS else None


def sure(note):
    """Запись безусловна и названа литералом: рисунок применяет её, а не только помечает. Это же слова обзора «при открытии»: литерал без условия — итог, выражение и условие — нет;
    рисунок и текст расходиться не могут, потому что решает одно правило. Созданное по выражению имени (`name_expr`) литералом не названо."""
    if note["condition"]:
        return False
    if note["kind"] in BOOL_PROPS or note["kind"] == "desktop_mode":
        return literal(note["value"]) is not None
    if note["kind"] == "title":
        return not _is_expression(note["value"])
    if note["kind"] == "value":
        return module.value_of(note["value"]) is not None
    return True


def _literal_form(found):
    """Литерал значения поля в канонической записи строки перечня: `Истина`, `Ложь`, текст в кавычках, число."""
    kind, value = found
    return ("Истина" if value else "Ложь") if kind == "bool" else '"' + value.replace('"', '""') + '"' if kind == "text" else value


def _is_expression(text):
    """Значение заголовка — выражение, а не текст: текстом считается только строка в кавычках целиком (`"Новый"`); всё остальное (`"Итого: " + Сумма`, `Наименование`) — выражение."""
    return not (len(text) > 1 and text[0] == text[-1] == '"' and text.count('"') == 2)


def _unquote(text):
    return text[1:-1] if len(text) > 1 and text[0] == text[-1] == '"' and text.count('"') == 2 else text


def effect_rows(accepted, procedures):
    """Строки для `module_effects.group` из принятых записей: `[{element, part, prop, value, procedure, line, line_to, expr, cond, applied, group, default, add}]`. Записи о самой форме (`target.form`) и `open_refused`, `other` сюда не идут: `form_rows`, шапка и раздел «Разбор кода»."""
    rows = []
    singles = single_target_groups(accepted)
    for note in accepted:
        target, kind = note["target"], note["kind"]
        if kind == "on_event":
            for effect in note["effects"]:          # экран, на который переходит действие: картинка страницы; на рисунке «как в файле» (запись не безусловна и вне открытия)
                for panel, page in effect.get("pages") or ():
                    rows.append({"element": panel, "part": None, "prop": "текущая страница", "value": page, "procedure": module.procedure_at(procedures, note["lines"][0]), "line": note["lines"][0],
                                 "line_to": note["lines"][1], "expr": None, "cond": effect.get("condition") or note["condition"] or None, "applied": False, "group": "", "group_single": False,
                                 "default": False, "order": note.get("order"), "user_only": True, "opening": False})
            continue
        if kind in NOT_ROWS or target["kind"] == "form":
            continue
        part = PART_WORDS[target["kind"]] + target["sub"] if target["sub"] else None
        menu = " → ".join(target["path"]) if target.get("path") else None
        if menu and kind != "created" and part:
            part += f" (в меню «{menu}»)"
        if note["name_expr"]:
            part = f"{NAMELESS_WORDS[target['kind']]} (имя — выражение «{shorten(note['name_expr'], 40)}»)"
        element = target["element"]
        if element is None and target["kind"] == "element":
            continue            # элемент, имя которого вычисляет код: на форме его нет, в перечень по элементам не входит (запись — в `by_data`)
        value, expr, add = note["value"], None, None
        if kind in BOOL_PROPS:
            prop = BOOL_PROPS[kind]
            value, expr = (literal(value), None) if literal(value) else ("по условию", value)
        elif kind == "title":
            prop = "заголовок"
            if _is_expression(value):
                value, expr = "по условию", value
            else:
                value = _unquote(value)
                expr = '"' + value + '"'        # заголовок-текст в перечне назван «значение «…»»
        elif kind == "value":
            prop = module.VALUE_PROP
            found = module.value_of(value)
            value, expr = (_literal_form(found), None) if found else (module.BY_EXPRESSION, value)
        elif kind == "current_page":
            prop, part = "текущая страница", None
            element, value = target["element"], target["sub"]
        elif kind == "collapse":
            prop = "свёртка"          # безусловная свёртка при открытии рисунок применяет (`layout.fold`); по условию — запись в досье
        elif kind == "current_element":
            prop, value = module.FOCUS_PROP, ""
        elif kind == "created":
            prop = CREATE_PROPS[target["kind"]]
            value = _unquote(value) or target["sub"]
            if menu:
                prop = f"в меню «{menu}» добавлено"     # кнопка меню на полосе панели не рисуется: меню остаётся как в файле
            elif target["kind"] == "button":
                add = {"name": target["sub"] or None, "kind": "действие", "text": value or ("…" if note["name_expr"] else ""), "index": None, "picture": None, "display": None,
                       "conditional": bool(note["condition"]), "computed": note["name_expr"] or None}
        elif kind == "removed":
            prop = REMOVE_PROPS[target["kind"]]
            if target["kind"] == "element" and value.casefold().startswith(CLEAR_WORDS):
                prop = CLEAR_PROP            # `Кнопки.Очистить()`: запись о панели со словами «все кнопки» в value
            elif target["kind"] == "button" and value.casefold().startswith(CLEAR_WORDS):
                prop = CLEAR_SUBMENU_PROP    # `Кнопки.Очистить()` у подменю: кнопки подменю очищены, само подменю остаётся
            value = ""
        else:    # geometry у элемента
            prop, expr = GEOMETRY_PROP, None
        if element is None and target["kind"] == "page":
            continue            # страницы самой формы в перечень элементов не входят: у формы нет имени в структуре
        proc = OBJECT_BODY if note.get("object_body") else module.procedure_at(procedures, note["lines"][0])
        rows.append({"element": element, "part": part, "prop": prop, "value": value, "procedure": proc, "line": note.get("object_line") or note["lines"][0], "line_to": note.get("object_line") or note["lines"][1],
                     "expr": expr, "cond": note["condition"] or None, "applied": sure(note) and not note["group"] or _group_default(note, (note["group"], kind) in singles), "group": note["group"],
                     "group_single": (note["group"], kind) in singles,
                     "default": note["default"], "order": note.get("order"), "user_only": note.get("user_only", False), "opening": note.get("opening", True),
                     **({"add": add} if add else {})})
    return rows


def form_rows(accepted, procedures):
    """Что код меняет у самой формы: `[{prop, where, line, line_to, value, expr, cond, procedure, applied}]` — режим рабочего стола, положение и размер,
    доступность и «только просмотр» формы."""
    out = []
    for note in accepted:
        if note["target"]["kind"] != "form" or note["kind"] not in FORM_KINDS:
            continue
        value = note["value"]
        boolean = note["kind"] in ("desktop_mode", "enabled", "read_only")
        title_expr = note["kind"] == "title" and _is_expression(value)
        if note["kind"] == "title" and not title_expr:
            value = _unquote(value)
        out.append({"prop": FORM_KINDS[note["kind"]], "where": "модуль формы", "line": note["lines"][0], "line_to": note["lines"][1],
                    "value": (literal(value) or "по условию") if boolean else "по условию" if title_expr else value,
                    "expr": value if (boolean and not literal(value)) or title_expr else None,
                    "cond": note["condition"] or None, "procedure": module.procedure_at(procedures, note["lines"][0]),
                    "applied": sure(note)})
    return out


def by_data(accepted):
    """`[{target, name_expr, value, condition, lines}]` — записи `created` с `name_expr`: страницы, колонки, кнопки и элементы, которые код строит по данным (имя — выражение)."""
    return [{"target": n["target"], "name_expr": n["name_expr"], "value": n["value"], "condition": n["condition"], "lines": list(n["lines"])}
            for n in accepted if n["kind"] == "created" and n["name_expr"]]


def missing(accepted):
    """`[{name, lines, quote, why, condition}]` — записи `missing`: код обращается к имени, которого на форме нет."""
    return [{"name": n["target"]["sub"], "lines": list(n["lines"]), "quote": n["quote"], "why": n["why"], "condition": n["condition"]}
            for n in accepted if n["kind"] == "missing"]


def appearances(accepted):
    """`[{target, kind, value, lines, condition, quote}]` — записи `appearance` и `list_content`: оформление и списки значений, которые код задаёт; в досье словами, на рисунке не рисуются."""
    return [{"target": n["target"], "kind": n["kind"], "value": n["value"], "lines": list(n["lines"]), "condition": n["condition"], "quote": n["quote"], "why": n["why"],
             "group": n["group"], "default": n["default"]}
            for n in accepted if n["kind"] in ("appearance", "list_content")]


def refusals(accepted):
    """`[{condition, message, lines}]` — записи `open_refused`: форма может не открыться."""
    return [{"condition": n["condition"], "message": n["message"], "lines": list(n["lines"])}
            for n in accepted if n["kind"] == "open_refused"]


def form_titles(accepted):
    """`[{value, expr, condition, lines}]` — записи `title` о самой форме (`ЭтаФорма.Заголовок`): текст в кавычках — `value`, выражение — `expr`."""
    out = []
    for n in accepted:
        if n["kind"] == "title" and n["target"]["kind"] == "form":
            expr = _is_expression(n["value"])
            out.append({"value": "" if expr else _unquote(n["value"]), "expr": n["value"] if expr else "", "condition": n["condition"], "lines": list(n["lines"])})
    return out


def others(accepted):
    """`[{target, lines, why, quote, condition, form_work, opening}]` — записи `other`: то, что модель прочитала, но записать иначе не смогла; `form_work` — форма делает сама по таймеру или действию
    (граф вызовов), `opening` — строка выполняется при открытии."""
    return [{"target": n["target"], "lines": list(n["lines"]), "why": n["why"], "quote": n["quote"], "condition": n["condition"], "form_work": bool(n.get("form_work")),
             "opening": bool(n.get("opening", True))}
            for n in accepted if n["kind"] == "other"]


def detail_words(effect, prop, limit=SHOWN):
    """Слова о том, при каких условиях и насколько твёрдо: условие, зависимость, «вероятно» — для строки перечня и подсказки на рисунке."""
    bits = []
    for x in effect["conds"].get(prop, [])[:2]:
        bits.append(f"условие «{shorten(x, limit)}»")
    if prop in effect.get("overridden", {}):
        bits.append(f"условные записи раньше перекрыты безусловной (строка {effect['overridden'][prop]})")
    return bits
