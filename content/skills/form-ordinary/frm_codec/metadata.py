"""Чтение метаданных объектов из выгрузки конфигурации (XML платформы: `Catalogs/*.xml`, `Documents/*.xml`,
`DataProcessors/*.xml`, `Reports/*.xml`).

Модуль нужен для привязки полей формы к реквизитам объекта и для генерации форм. Он читает имя, uuid, реквизиты в порядке
файла (имя, uuid, типы, квалификаторы, применение), стандартные реквизиты с синонимами, табличные части и `TypeId`
сгенерированных типов. Используется только стандартная библиотека. Любое несоответствие приводит к `MetadataError` с
пояснением, а не к пустому результату.

Читаются справочники, документы, обработки и отчёты. У других видов объектов (планы видов и т. д.) набор стандартных
реквизитов другой. Журналы документов, регистры сведений и регистры накопления читаются отдельно, как справочные сведения о
том, с чем работает форма (`ExtraObject`, `Config.extras`): в привязку полей и генерацию они не входят. Версии формата выгрузки перечислены в `FORMAT_VERSIONS`, неизвестная версия приводит к отказу. Функция
`load` читает всю выгрузку сразу, поэтому один файл с версией вне перечня отказывает всю загрузку; чтения только нужного
объекта нет. Исключение — обработки и отчёты: нечитаемый файл обработки (отчёта) не отказывает загрузку, а записывается в `Config.failed`
(полное имя и слова причины). Отказ получает только тот, кто запросил именно этот объект (`Config.object`, `form_object`).

Стандартные реквизиты (`MdObject.standard`) идут в порядке Код, Наименование, Родитель, Владелец; у документа — Номер, Дата.
Их набор определяют свойства объекта: `Код` есть при `CodeLength` > 0, `Наименование` при `DescriptionLength` > 0,
`Родитель` при `Hierarchical`, `Владелец` при непустом `Owners`. У документа `Номер` есть при `NumberLength` > 0 (это не
проверялось: документ с нумератором берёт длину у нумератора, а правило этого не знает), `Дата` есть всегда.
`MdObject.standard_synonyms` — синонимы, переопределённые в `StandardAttributes` (русское имя и текст; если записи нет, то
действует синоним платформы). `MdObject.std_types` — тип и длина стандартных реквизитов, которые колонка списка записывает
в тип значения: `Код` (`CodeType`, `CodeLength`, `CodeAllowedLength`), `Наименование` (строка длины `DescriptionLength`,
`Variable`), `Номер` (`NumberType`, `NumberLength`, `NumberAllowedLength`). У `Дата` типа нет: это всегда дата со временем.

Реквизит (`Attr`). Поле `types` — кортеж значений `v8:Type` как в файле (`xs:decimal`, `cfg:CatalogRef.Товары`).
Поле `type_sets` — отдельный кортеж значений `v8:TypeSet` (`cfg:DefinedType.Вес`, `cfg:Characteristic.X`, `cfg:AnyRef`):
определяемый тип нужно раскрывать через `DefinedTypes/*.xml`, а модуль эти файлы не читает, поэтому потребитель отказывает.
Квалификаторы хранятся раздельно: `string_length` (`Length`), `allowed_length` (`Fixed` или `Variable`), `digits`
(`Digits`), `fraction` (`FractionDigits`), `allowed_sign` (`Any` или `Nonnegative`), `date_fractions` (`Date`, `Time` или
`DateTime`). Если квалификатора нет, значение равно `None`. Поле `length` — разрядность числа, а для строки — её длина;
`precision` — число знаков после запятой. У составного типа, где есть и длина строки, и разрядность, `length` отказывает с
пояснением, и потребитель выбирает между `string_length` и `digits`. Поле `use` содержит `Use` из XML (`ForItem`,
`ForFolder`, `ForFolderAndItem`); если у справочника свойства нет, берётся `ForItem`. У документа и у колонок табличной части
`use` равен `None`.

Группы и элементы. Формы группы привязаны только к `ForFolder` и `ForFolderAndItem`, формы элемента — к `ForItem` и
`ForFolderAndItem`. `MdObject.attributes_for("item"|"folder")` и `tables_for(...)` возвращают нужное подмножество; запрос
`folder` у объекта без групп приводит к отказу. `MdObject.hierarchy_type` — это `HierarchyType` как в файле. Как
`SubordinationUse` влияет на `Владелец` формы группы, не проверялось.

Типы формы. `MdObject.type_ids` — это `TypeId` из `InternalInfo/xr:GeneratedType` по категории (`Object`, `Ref`, `List`,
`Selection`, `Manager` и т. д.). Если у объекта нет `InternalInfo`, словарь пуст, а `type_id(категория)` отказывает с
пояснением. Тип основного реквизита формы записан GUID, равным `TypeId`: у форм объекта категории `Object`, у форм списка
`List`. `Config.object_by_type_id(guid)` возвращает `(MdObject, категория)` или `None`; если один `TypeId` встречается у
двух объектов, загрузка отказывает. `Config.ref_type_id("cfg:CatalogRef.Имя")` возвращает GUID типа-ссылки: это `TypeId`
категории `Ref` справочника или документа из выгрузки, а для перечисления — из `Enums/<Имя>.xml`, который читается по
требованию. Другие виды ссылок и объекты вне выгрузки приводят к отказу.

Обработка (`kind == "processing"`, полное имя «Обработка.Имя»). Реквизиты и табличные части читаются как у документа, но без
`Use`; стандартных реквизитов нет (`standard` пуст). `TypeId` категории `Object` (`DataProcessorObject.Имя`) — это тип
основного реквизита формы обработки. Пустой `<Type/>` означает произвольный тип: `types = ()` и `type_sets = ()`, а
потребитель отказывает полю на такой реквизит с пояснением «произвольного типа». Пустое имя типа (`<v8:Type></v8:Type>`)
приводит к отказу чтения. У реквизита обработки бывают типы, которых нет у справочника (`v8:ValueTable`,
`dcsset:SettingsComposer`, `v8:ValueStorage`): они читаются как есть, а вид элемента для них назовёт потребитель или откажет.

Отчёт (`kind == "report"`, полное имя «Отчет.Имя», при чтении «Отчёт.Имя» тоже принимается) устроен для формы как обработка: реквизиты и табличные
части те же, стандартных реквизитов и групп нет, `TypeId` категории `Object` (`ReportObject.Имя`) — тип основного реквизита формы отчёта. Схема
компоновки данных, макеты и настройки отчёта не читаются.

Значения неизменяемы: списки — кортежи, `Attr` и `Table` хешируются по значению, а `MdObject` и `Config` — по
идентичности.
"""
import dataclasses
import pathlib
import re
import unicodedata
import xml.etree.ElementTree as ET

NS = {"m": "http://v8.1c.ru/8.3/MDClasses", "v8": "http://v8.1c.ru/8.1/data/core",
      "xr": "http://v8.1c.ru/8.3/xcf/readable"}
# Версии формата выгрузки, которые модуль читает. 2.4, 2.15, 2.18 и 2.20 встречались в выгрузках настоящих баз; 2.16 (8.3.23), 2.17 (8.3.24)
# и 2.19 (8.3.26) лежат между ними, и различия этих версий, снятые выгрузками пустой базы, — свойства корня конфигурации, роли и редкие
# свойства форм: имя, синоним, реквизиты, табличные части и `GeneratedType`, которые читает модуль, в них не меняются.
FORMAT_VERSIONS = ("2.4", "2.15", "2.16", "2.17", "2.18", "2.19", "2.20")
STANDARD_IDS = {"Код": -2, "Номер": -2, "Наименование": -3, "Дата": -3, "Родитель": -4, "Владелец": -5}
# XML-имя стандартного реквизита → русское имя
STANDARD_XML = {"Code": "Код", "Description": "Наименование", "Parent": "Родитель", "Owner": "Владелец",
                "Number": "Номер", "Date": "Дата"}
USES = ("ForItem", "ForFolder", "ForFolderAndItem")
DEFAULT_USE = "ForItem"
HIERARCHY_TYPES = ("HierarchyFoldersAndItems", "HierarchyOfItems")
# вид объекта: (каталог выгрузки, тег корня, русское имя в полном имени, английское)
KINDS = {"catalog": ("Catalogs", "Catalog", "Справочник", "Catalog"),
         "document": ("Documents", "Document", "Документ", "Document"),
         "processing": ("DataProcessors", "DataProcessor", "Обработка", "DataProcessor"),
         "report": ("Reports", "Report", "Отчет", "Report")}
# внешний объект: вид → (русское имя в полном имени, тег корня, английское имя)
EXTERNAL_WORDS = {"processing": ("ВнешняяОбработка", "ExternalDataProcessor", "ExternalDataProcessor"),
                  "report": ("ВнешнийОтчет", "ExternalReport", "ExternalReport")}
NO_FOLDER_KINDS = ("document", "processing", "report")       # групп и элементов (`Use`) у этих видов нет
NOT_FATAL_KINDS = ("processing", "report")      # нечитаемый файл такого объекта не отказывает всю загрузку: `Config.failed`
# какие `Use` видит форма: item — форма элемента, folder — форма группы
_USE_FOR = {"item": ("ForItem", "ForFolderAndItem"), "folder": ("ForFolder", "ForFolderAndItem")}


class MetadataError(ValueError):
    pass


def _nfc(s):
    return unicodedata.normalize("NFC", s)


@dataclasses.dataclass(frozen=True)
class Attr:
    name: str
    uuid: str
    types: tuple
    type_sets: tuple = ()
    string_length: object = None
    allowed_length: object = None
    digits: object = None
    fraction: object = None
    allowed_sign: object = None
    date_fractions: object = None
    use: object = None
    synonym: str = ""
    fill_checking: object = None   # `FillChecking`: `ShowError` — реквизит обязателен, `DontCheck` — нет; в файле нет — `None`

    @property
    def length(self):
        """Разрядность числа, а для строки — её длина. Если у составного типа есть и то, и другое, это отказ: выбирает потребитель."""
        if self.string_length is not None and self.digits is not None:
            raise MetadataError(f"у реквизита «{self.name}» составной тип: длина строки {self.string_length} и "
                                f"разрядность числа {self.digits}; какую взять — решает потребитель "
                                "(string_length / digits)")
        return self.digits if self.digits is not None else self.string_length

    @property
    def precision(self):
        return self.fraction


@dataclasses.dataclass(frozen=True)
class Table:
    name: str
    uuid: str
    attributes: tuple
    synonym: str = ""
    use: object = None
    type_id: object = None  # `TypeId` типа табличной части (`xr:GeneratedType category="TabularSection"`): тип значения табличного поля формы

    def attribute(self, name):
        """Колонка по имени. Если её нет, отказ перечисляет имена."""
        for a in self.attributes:
            if a.name == name:
                return a
        raise MetadataError(f"в табличной части «{self.name}» нет реквизита «{name}»; реквизиты: "
                            f"{', '.join(a.name for a in self.attributes) or 'нет'}")

    def attribute_by_uuid(self, uid):
        for a in self.attributes:
            if a.uuid == uid:
                return a
        return None


@dataclasses.dataclass(frozen=True, eq=False)
class MdObject:
    kind: str
    name: str
    uuid: str
    attributes: tuple
    standard: tuple
    tables: tuple
    owners: tuple = ()
    hierarchical: bool = False
    synonym: str = ""
    hierarchy_type: object = None
    type_ids: dict = dataclasses.field(default_factory=dict)
    standard_synonyms: dict = dataclasses.field(default_factory=dict)
    std_types: dict = dataclasses.field(default_factory=dict)  # стандартный реквизит → `(тип, длина, допустимая длина)` из свойств объекта
    posting: object = None     # у документа — `Posting` из свойств: `Allow` (проводится) или `Deny`; у остальных видов и без свойства — `None`
    external: bool = False     # внешняя обработка или внешний отчёт (корневой XML выгрузки внешнего объекта, `external_root`)

    @property
    def full_name(self):
        if self.external:
            return f"{EXTERNAL_WORDS[self.kind][0]}.{self.name}"
        return f"{KINDS[self.kind][2]}.{self.name}"

    def attribute(self, name):
        """Реквизит по имени. Если его нет, отказ перечисляет имена и, если это отсутствующий стандартный реквизит, называет причину."""
        for a in self.attributes:
            if a.name == name:
                return a
        extra = ""
        if name in STANDARD_IDS and name not in self.standard:
            extra = (f"; «{name}» — стандартный реквизит, которого у объекта нет (его включают свойства объекта: "
                     "CodeLength, DescriptionLength, NumberLength, Hierarchical, Owners)")
        elif name in self.standard:
            extra = f"; «{name}» — стандартный реквизит, а не пользовательский (стандартные: {', '.join(self.standard)})"
        raise MetadataError(f"у объекта «{self.full_name}» нет реквизита «{name}»; реквизиты: "
                            f"{', '.join(a.name for a in self.attributes) or 'нет'}{extra}")

    def table(self, name):
        for t in self.tables:
            if t.name == name:
                return t
        raise MetadataError(f"у объекта «{self.full_name}» нет табличной части «{name}»; табличные части: "
                            f"{', '.join(t.name for t in self.tables) or 'нет'}")

    def table_by_uuid(self, uid):
        for t in self.tables:
            if t.uuid == uid:
                return t
        return None

    def has_folders(self):
        """Есть ли у объекта группы: это справочник с `Hierarchical` и видом `HierarchyFoldersAndItems`."""
        return self.kind == "catalog" and self.hierarchical and self.hierarchy_type == "HierarchyFoldersAndItems"

    def _for(self, kind, items, what):
        if kind not in _USE_FOR:
            raise MetadataError(f"вид формы {kind!r} неизвестен: «item» (элемент) или «folder» (группа)")
        if kind == "folder" and not self.has_folders():
            why = ("документ" if self.kind == "document" else
                   "обработка" if self.kind == "processing" else
                   "отчёт" if self.kind == "report" else
                   "справочник не иерархический" if not self.hierarchical else
                   "иерархия «HierarchyOfItems» (группы не бывают)" if self.hierarchy_type == "HierarchyOfItems" else
                   "вид иерархии в файле не назван")
            raise MetadataError(f"у объекта «{self.full_name}» нет групп ({why}): {what} группы не бывает")
        if self.kind in NO_FOLDER_KINDS:
            return tuple(items)
        return tuple(x for x in items if (x.use or DEFAULT_USE) in _USE_FOR[kind])

    def attributes_for(self, kind):
        """Реквизиты, которые видны форме элемента (`item`) или группы (`folder`), по свойству `Use`."""
        return self._for(kind, self.attributes, "реквизитов")

    def tables_for(self, kind):
        return self._for(kind, self.tables, "табличных частей")

    def type_id(self, category):
        """`TypeId` сгенерированного типа заданной категории (`Object`, `List`, `Ref` и т. д.). Если типа нет, отказ перечисляет категории."""
        if category not in self.type_ids:
            raise MetadataError(f"у объекта «{self.full_name}» нет сгенерированного типа категории «{category}»; "
                                f"категории: {', '.join(self.type_ids) or 'нет (в файле нет InternalInfo)'}")
        return self.type_ids[category]


# вид справочного объекта: (каталог выгрузки, тег корня, русское имя в полном имени)
EXTRA_KINDS = {"journal": ("DocumentJournals", "DocumentJournal", "ЖурналДокументов"),
               "inforeg": ("InformationRegisters", "InformationRegister", "РегистрСведений"),
               "accreg": ("AccumulationRegisters", "AccumulationRegister", "РегистрНакопления")}
PERIODICITY = {"Nonperiodical": "непериодический", "Second": "по секундам", "Day": "по дням", "Month": "по месяцам", "Quarter": "по кварталам",
               "Year": "по годам", "RecorderPosition": "по позиции регистратора"}
WRITE_MODE = {"Independent": "независимый", "RecorderSubordinate": "подчинён регистратору"}
REGISTER_TYPE = {"Balance": "остатки", "Turnovers": "обороты"}


@dataclasses.dataclass(frozen=True)
class JournalColumn:
    name: str
    synonym: str
    documents: tuple      # имена документов, чьи реквизиты входят в графу (из `References`)


@dataclasses.dataclass(frozen=True, eq=False)
class ExtraObject:
    """Журнал документов или регистр (сведений, накопления): состав объекта для досье. Типы формы — `type_ids` (`List`, `RecordManager` и т. д.)."""
    kind: str
    name: str
    synonym: str
    type_ids: dict
    registered: tuple = ()          # журнал: имена документов журнала
    columns: tuple = ()             # журнал: графы (`JournalColumn`)
    dimensions: tuple = ()          # регистр: `Attr`
    resources: tuple = ()
    attributes: tuple = ()
    periodicity: object = None      # регистр сведений: слова периодичности
    write_mode: object = None       # регистр сведений: слова режима записи
    register_type: object = None    # регистр накопления: слова вида

    @property
    def full_name(self):
        return f"{EXTRA_KINDS[self.kind][2]}.{self.name}"


@dataclasses.dataclass(frozen=True, eq=False)
class Config:
    root: str
    objects: dict          # полное русское имя → MdObject
    failed: dict = dataclasses.field(default_factory=dict)  # обработки, чей файл не прочитан: полное имя → слова
    main_language: str = None   # код основного языка конфигурации (`Configuration.xml`/`DefaultLanguage` → `Languages/<имя>.xml`), если прочитан
    extras: dict = dataclasses.field(default_factory=dict)   # журналы и регистры: полное русское имя → `ExtraObject`
    has_dump: bool = True       # `False` — выгрузки конфигурации нет, в `objects` только внешний объект из корневого XML (`load_for`)
    _by_type: dict = dataclasses.field(default=None, repr=False)
    _enum_refs: dict = dataclasses.field(default_factory=dict, repr=False)

    def __post_init__(self):
        idx = {}
        for o in self.objects.values():
            for cat, tid in o.type_ids.items():
                if tid in idx:
                    raise MetadataError(f"в выгрузке «{self.root}» TypeId {tid} у двух объектов: "
                                        f"«{idx[tid][0].full_name}» ({idx[tid][1]}) и «{o.full_name}» ({cat})")
                idx[tid] = (o, cat)
        object.__setattr__(self, "_by_type", idx)

    def object(self, full_name):
        key = _normalize(full_name)
        if key in self.objects:
            return self.objects[key]
        alias = _external_alias(key)
        if alias in self.objects:
            return self.objects[alias]       # «Обработка.Имя» называет и внешнюю обработку: её собственное имя в описании
        if key in self.failed:
            raise MetadataError(f"в выгрузке «{self.root}» объект «{key}» не прочитан: {self.failed[key]}")
        where = f"в выгрузке «{self.root}»" if self.has_dump else "среди объектов корневого XML"
        raise MetadataError(f"{where} нет объекта «{full_name}»; объекты: "
                            f"{', '.join(sorted(self.objects))}"
                            + (f"; не прочитаны: {', '.join(sorted(self.failed))}" if self.failed else ""))

    def extra_by_type_id(self, guid):
        """`(ExtraObject, категория)` журнала или регистра, у которого сгенерированный тип имеет этот `TypeId`, либо `None`."""
        guid = (guid or "").strip().lower()
        for o in self.extras.values():
            for cat, tid in o.type_ids.items():
                if tid == guid:
                    return o, cat
        return None

    def failed_reason(self, full_name):
        """Слова причины, по которой обработка с этим именем не прочитана (`Config.failed`). Если её нет среди нечитаемых, `None`."""
        return self.failed.get(_normalize(full_name))

    def object_by_type_id(self, guid):
        """Возвращает `(MdObject, категория)` объекта, у которого сгенерированный тип имеет этот `TypeId`, либо `None`."""
        return self._by_type.get((guid or "").strip().lower())

    def ref_type_id(self, type_name):
        """GUID типа-ссылки по значению `v8:Type` реквизита (`cfg:CatalogRef.Склады`): это `TypeId` категории `Ref`.

        Справочник и документ берутся из загруженных объектов, перечисление — из соседнего `Enums/<Имя>.xml` (нужен один `TypeId`).
        Другие виды ссылок (план обмена, план видов характеристик, определяемый тип и т. д.) приводят к отказу, как и объект,
        которого нет в выгрузке (частичная выгрузка); отказ называет объект.
        """
        kind, dot, name = (type_name[4:] if type_name.startswith("cfg:") else type_name).partition(".")
        if not dot or not name:
            raise MetadataError(f"тип «{type_name}» — не ссылка на объект (ждётся cfg:CatalogRef.Имя)")
        if not self.has_dump:
            raise MetadataError(f"тип «{type_name}» — ссылка на объект конфигурации, а выгрузки конфигурации не дано (--config КАТАЛОГ): "
                                "GUID типа-ссылки взять неоткуда")
        name = _nfc(name)
        if kind in ("CatalogRef", "DocumentRef"):
            key = f"{'Справочник' if kind == 'CatalogRef' else 'Документ'}.{name}"
            found = self.objects.get(key)
            if found is None:
                raise MetadataError(f"в выгрузке «{self.root}» нет объекта «{key}», на который ссылается тип "
                                    f"«{type_name}» (выгрузка частичная?)")
            return found.type_id("Ref")
        if kind != "EnumRef":
            raise MetadataError(f"тип «{type_name}»: ссылки вида {kind} выгрузка не разбирает "
                                "(читаются CatalogRef, DocumentRef, EnumRef)")
        if name in self._enum_refs:
            return self._enum_refs[name]
        path = pathlib.Path(self.root) / "Enums" / f"{name}.xml"
        if not path.is_file():
            raise MetadataError(f"в выгрузке «{self.root}» нет перечисления «{name}» (Enums/{name}.xml), "
                                f"на которое ссылается тип «{type_name}»")
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as e:
            raise MetadataError(f"Enums/{name}.xml: не разобрать XML ({e})") from None
        enum = root.find("m:Enum", NS)
        ids = _type_ids(enum, f"Enums/{name}.xml") if enum is not None else {}
        if "Ref" not in ids:
            raise MetadataError(f"Enums/{name}.xml: у перечисления нет сгенерированного типа категории «Ref»")
        self._enum_refs[name] = ids["Ref"]
        return ids["Ref"]


def _normalize(full_name):
    full_name = _nfc(full_name)
    for ru, tag, en in EXTERNAL_WORDS.values():
        for pre in (ru, en, ru.replace("Отчет", "Отчёт")):
            if full_name.startswith(pre + "."):
                return f"{ru}.{full_name[len(pre) + 1:]}"
    full_name = full_name.replace("Отчёт.", "Отчет.", 1) if full_name.startswith("Отчёт.") else full_name
    for _, (_, _, ru, en) in KINDS.items():
        for pre in (ru, en):
            if full_name.startswith(pre + "."):
                return f"{ru}.{full_name[len(pre) + 1:]}"
    return full_name


def _external_alias(key):
    """Полное имя внешнего объекта, которое называет «Обработка.Имя» либо «Отчет.Имя»; другому ключу — `None`."""
    for kind, (ext_ru, _tag, _en) in EXTERNAL_WORDS.items():
        pre = KINDS[kind][2] + "."
        if key.startswith(pre):
            return f"{ext_ru}.{key[len(pre):]}"
    return None


def same_object_name(a, b):
    """Называют ли два полных имени один объект: с точностью до написания вида («Отчёт.» и «Отчет.») и до того, что «Обработка.Имя» называет и
    внешнюю обработку «ВнешняяОбработка.Имя» (так же «Отчет.» и «ВнешнийОтчет.»)."""
    x, y = _normalize(a), _normalize(b)
    return x == y or _external_alias(x) == y or _external_alias(y) == x


def _q(tag):
    return "{%s}%s" % (NS["m"], tag)


def _text(el, path, where, required=True):
    f = el.find(path, NS)
    if f is None:
        if required:
            raise MetadataError(f"{where}: нет элемента {path}")
        return None
    return (f.text or "").strip()


def _int(el, path, where):
    t = _text(el, path, where)
    try:
        return int(t)
    except ValueError:
        raise MetadataError(f"{where}: {path} = «{t}», ожидалось число") from None


def _synonym(props, path="m:Synonym"):
    for it in props.findall(f"{path}/v8:item", NS):
        if _text(it, "v8:lang", "синоним", False) == "ru":
            return _text(it, "v8:content", "синоним", False) or ""
    return ""


def _use(p, where, kind_word):
    u = _text(p, "m:Use", where, False)
    if u is None:
        return DEFAULT_USE
    if u not in USES:
        raise MetadataError(f"{where}: {kind_word} Use = «{u}», известны {', '.join(USES)}")
    return u


def _attr(el, where, with_use):
    p = el.find("m:Properties", NS)
    if p is None:
        raise MetadataError(f"{where}: у реквизита нет Properties")
    name = _text(p, "m:Name", where)
    where = f"{where}, реквизит «{name}»"
    uid = el.get("uuid")
    if not uid:
        raise MetadataError(f"{where}: нет uuid")
    t = p.find("m:Type", NS)
    if t is None:
        raise MetadataError(f"{where}: нет типа")
    types = tuple((x.text or "").strip() for x in t if x.tag == "{%s}Type" % NS["v8"])
    sets = tuple((x.text or "").strip() for x in t if x.tag == "{%s}TypeSet" % NS["v8"])
    if not all(types + sets):
        raise MetadataError(f"{where}: тип не назван")      # `<Type><v8:Type/></Type>` — пустое имя типа; `<Type/>` без детей — произвольный тип (ниже)
    sl = al = dg = fr = sg = df = None
    if t.find("v8:StringQualifiers", NS) is not None:
        sl = _int(t, "v8:StringQualifiers/v8:Length", where)
        al = _text(t, "v8:StringQualifiers/v8:AllowedLength", where, False)
    q = t.find("v8:NumberQualifiers", NS)
    if q is not None:
        dg = _int(q, "v8:Digits", where)
        fr = _int(q, "v8:FractionDigits", where)
        sg = _text(q, "v8:AllowedSign", where, False)
    if t.find("v8:DateQualifiers", NS) is not None:
        df = _text(t, "v8:DateQualifiers/v8:DateFractions", where, False)
    use = _use(p, where, "реквизит") if with_use else None
    return Attr(name, uid, types, sets, sl, al, dg, fr, sg, df, use, _synonym(p), _text(p, "m:FillChecking", where, False))


def _table(el, where, with_use):
    p = el.find("m:Properties", NS)
    name = _text(p, "m:Name", where) if p is not None else None
    if not name:
        raise MetadataError(f"{where}: у табличной части нет имени")
    where = f"{where}, табличная часть «{name}»"
    if not el.get("uuid"):
        raise MetadataError(f"{where}: нет uuid")
    attrs = tuple(_attr(a, where, False) for a in el.findall("m:ChildObjects/m:Attribute", NS))
    _unique([a.name for a in attrs], where)
    use = _use(p, where, "табличная часть") if with_use else None
    return Table(name, el.get("uuid"), attrs, _synonym(p), use, _type_ids(el, where).get("TabularSection"))


def _unique(names, where):
    seen = set()
    for n in names:
        if n in seen:
            raise MetadataError(f"{where}: имя «{n}» повторяется")
        seen.add(n)


def _type_ids(el, where):
    ids = {}
    for g in el.findall("m:InternalInfo/xr:GeneratedType", NS):
        cat = g.get("category")
        tid = _text(g, "xr:TypeId", where, False)
        if not cat or not tid:
            raise MetadataError(f"{where}: у GeneratedType нет category или TypeId")
        if cat in ids:
            raise MetadataError(f"{where}: категория сгенерированного типа «{cat}» повторяется")
        ids[cat] = tid.lower()
    return ids


def _standard_synonyms(p, std):
    out = {}
    for sa in p.findall("m:StandardAttributes/xr:StandardAttribute", NS):
        ru = STANDARD_XML.get(sa.get("name"))
        if ru in std:
            s = _synonym(sa, "xr:Synonym")
            if s:
                out[ru] = s
    return out


def _object(path, kind):
    where = f"{path.parent.name}/{path.name}"
    root = _meta_root(path, where)
    el = root.find(f"m:{KINDS[kind][1]}", NS)
    if el is None:
        raise MetadataError(f"{where}: в файле нет элемента {KINDS[kind][1]}")
    return _build_object(el, kind, where, stem=path.stem)


def _meta_root(path, where, wrong="корень не MetaDataObject", bad_xml="не разобрать XML"):
    """Корень файла выгрузки (`MetaDataObject`) известной версии формата; иначе `MetadataError`."""
    try:
        root = ET.parse(path).getroot()
    except OSError as e:
        raise MetadataError(f"{where}: файл не прочитан ({e.strerror or e})") from None
    except ET.ParseError as e:
        raise MetadataError(f"{where}: {bad_xml} ({e})") from None
    if root.tag != _q("MetaDataObject"):
        raise MetadataError(f"{where}: {wrong}")
    ver = root.get("version")
    if ver not in FORMAT_VERSIONS:
        raise MetadataError(f"{where}: формат выгрузки {ver!r} неизвестен (читаются {', '.join(FORMAT_VERSIONS)}); "
                            "догадываться о его раскладке нельзя. Форме с нуля (`new`, `generate` без `--form`) тип основного реквизита "
                            "можно задать ключом --type-id без выгрузки")
    return root


def _build_object(el, kind, where, stem=None, external=False):
    """`MdObject` по элементу объекта (`Catalog`, `DataProcessor`, `ExternalDataProcessor`, …). `stem` — имя файла: имя объекта обязано с ним
    совпадать (у корневого XML внешнего объекта файл переименовать можно, и `stem` не дают)."""
    p = el.find("m:Properties", NS)
    if p is None:
        raise MetadataError(f"{where}: нет Properties")
    name = _nfc(_text(p, "m:Name", where))
    if stem is not None and name != _nfc(stem):
        raise MetadataError(f"{where}: имя объекта «{name}» не совпадает с именем файла")
    if not el.get("uuid"):
        raise MetadataError(f"{where}: нет uuid объекта")
    with_use = kind == "catalog"
    attrs = tuple(_attr(a, where, with_use) for a in el.findall("m:ChildObjects/m:Attribute", NS))
    tables = tuple(_table(t, where, with_use) for t in el.findall("m:ChildObjects/m:TabularSection", NS))
    _unique([a.name for a in attrs] + [t.name for t in tables], where)
    owners, hier, htype, std, std_types = (), False, None, [], {}
    if kind == "catalog":
        if _int(p, "m:CodeLength", where) > 0:
            std.append("Код")
            std_types["Код"] = (_text(p, "m:CodeType", where, False), _int(p, "m:CodeLength", where), _text(p, "m:CodeAllowedLength", where, False))
        if _int(p, "m:DescriptionLength", where) > 0:
            std.append("Наименование")
            std_types["Наименование"] = ("String", _int(p, "m:DescriptionLength", where), "Variable")
        hier = _text(p, "m:Hierarchical", where) == "true"
        htype = _text(p, "m:HierarchyType", where, False)
        if htype is not None and htype not in HIERARCHY_TYPES:
            raise MetadataError(f"{where}: HierarchyType = «{htype}», известны {', '.join(HIERARCHY_TYPES)}")
        if hier:
            std.append("Родитель")
        owners = tuple((x.text or "").strip() for x in p.findall("m:Owners/xr:Item", NS))
        if owners:
            std.append("Владелец")
    elif kind == "document":
        if _int(p, "m:NumberLength", where) > 0:
            std.append("Номер")
            std_types["Номер"] = (_text(p, "m:NumberType", where, False), _int(p, "m:NumberLength", where), _text(p, "m:NumberAllowedLength", where, False))
        std.append("Дата")
    return MdObject(kind, name, el.get("uuid"), attrs, tuple(std), tables, owners, hier, _synonym(p), htype,
                    _type_ids(el, where), _standard_synonyms(p, std), std_types,
                    _text(p, "m:Posting", where, False) if kind == "document" else None, external)


def _extra_object(path, kind):
    """Журнал документов или регистр из файла выгрузки; нечитаемый файл — `MetadataError`."""
    where = f"{path.parent.name}/{path.name}"
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as e:
        raise MetadataError(f"{where}: не разобрать XML ({e})") from None
    sub, tag, _ru = EXTRA_KINDS[kind]
    el = root.find(f"m:{tag}", NS)
    if root.tag != _q("MetaDataObject") or el is None:
        raise MetadataError(f"{where}: в файле нет элемента {tag}")
    p = el.find("m:Properties", NS)
    if p is None:
        raise MetadataError(f"{where}: нет Properties")
    name = _nfc(_text(p, "m:Name", where))
    attrs = {k: tuple(_attr(a, where, False) for a in el.findall(f"m:ChildObjects/m:{k}", NS)) for k in ("Dimension", "Resource", "Attribute")}
    cols, docs = [], ()
    if kind == "journal":
        docs = tuple(_nfc((x.text or "").strip().partition(".")[2]) for x in p.findall("m:RegisteredDocuments/xr:Item", NS))
        for c in el.findall("m:ChildObjects/m:Column", NS):
            cp = c.find("m:Properties", NS)
            refs = []
            for x in cp.findall("m:References/xr:Item", NS):
                doc = (x.text or "").strip().split(".")
                if len(doc) > 1 and _nfc(doc[1]) not in refs:
                    refs.append(_nfc(doc[1]))
            cols.append(JournalColumn(_nfc(_text(cp, "m:Name", where)), _synonym(cp), tuple(refs)))
    per = _text(p, "m:InformationRegisterPeriodicity", where, False)
    wm = _text(p, "m:WriteMode", where, False)
    rt = _text(p, "m:RegisterType", where, False)
    return ExtraObject(kind, name, _synonym(p), _type_ids(el, where), docs, tuple(cols), attrs["Dimension"], attrs["Resource"], attrs["Attribute"],
                       PERIODICITY.get(per, per) if kind == "inforeg" else None, WRITE_MODE.get(wm, wm) if kind == "inforeg" else None,
                       REGISTER_TYPE.get(rt, rt) if kind == "accreg" else None)


def _main_language(root):
    """Код основного языка выгрузки (`ru`) либо `None`: нет `Configuration.xml`, `DefaultLanguage` или файла языка."""
    try:
        text = (root / "Configuration.xml").read_text(encoding="utf-8-sig")
        match = re.search(r"<DefaultLanguage>\s*Language\.([^<\s]+)\s*</DefaultLanguage>", text)
        if match is None:
            return None
        lang = ET.parse(root / "Languages" / f"{match.group(1)}.xml").getroot()
        code = lang.find(".//m:LanguageCode", NS)
        return code.text.strip() if code is not None and code.text and code.text.strip() else None
    except (OSError, ET.ParseError, UnicodeDecodeError):
        return None


def load(config_dir):
    """Загружает выгрузку конфигурации (каталог с `Catalogs/`, `Documents/` и (или) `DataProcessors/`) в `Config`.

    Справочник или документ, который не читается, отказывает загрузку, а обработка — нет (`Config.failed`).
    """
    root = pathlib.Path(config_dir)
    if not root.is_dir():
        raise MetadataError(f"каталог выгрузки «{config_dir}» не найден")
    objects, failed, found = {}, {}, False
    for kind, (sub, _, ru, _en) in KINDS.items():
        d = root / sub
        if not d.is_dir():
            continue
        found = True
        for f in sorted(d.glob("*.xml")):
            if kind in NOT_FATAL_KINDS:
                try:
                    o = _object(f, kind)
                except MetadataError as e:
                    failed[f"{ru}.{_nfc(f.stem)}"] = str(e)
                    continue
            else:
                o = _object(f, kind)
            objects[f"{ru}.{o.name}"] = o
    if not found:
        raise MetadataError(f"в «{config_dir}» нет ни каталога Catalogs, ни Documents, ни DataProcessors: "
                            "это не выгрузка конфигурации")
    extras = {}
    for kind, (sub, _, ru) in EXTRA_KINDS.items():
        d = root / sub
        for f in sorted(d.glob("*.xml")) if d.is_dir() else ():
            try:
                o = _extra_object(f, kind)
            except MetadataError as e:
                failed[f"{ru}.{_nfc(f.stem)}"] = str(e)       # журнал или регистр, который не прочитан, форму не отказывает
                continue
            extras[o.full_name] = o
    return Config(str(root), objects, failed, main_language=_main_language(root), extras=extras)


@dataclasses.dataclass(frozen=True, eq=False)
class ExternalRoot:
    """Корневой XML выгрузки внешней обработки или внешнего отчёта: имя, синоним (русский), `TypeId` типа `Object` и разобранный объект
    (`obj`: реквизиты, табличные части, типы; `MdObject.external`)."""
    name: str
    synonym: str
    object_type_id: str
    kind: str          # `processing` (ExternalDataProcessor) или `report` (ExternalReport)
    obj: object        # MdObject


def external_root(path):
    """Читает корневой XML выгрузки внешней обработки или внешнего отчёта (`<Имя>.xml` рядом с каталогом `<Имя>/`): `ExternalRoot`.

    Разбор реквизитов и табличных частей — тот же, что у обработки и отчёта конфигурации (`_build_object`). Отказ словами (`MetadataError`): файл
    не читается или не XML; формат выгрузки неизвестен; корень не `ExternalDataProcessor` и не `ExternalReport` (объект конфигурации, чужой
    корень); нет `InternalInfo/xr:GeneratedType category="Object"` или у него нет `TypeId` либо тот не GUID; реквизит или табличная часть
    не разобраны."""
    where = f"корневой XML {path}"
    root = _meta_root(path, where, "не корневой XML выгрузки (ожидается MetaDataObject с одним объектом)", "не XML")
    if len(root) != 1:
        raise MetadataError(f"{where}: не корневой XML выгрузки (ожидается MetaDataObject с одним объектом)")
    el = root[0]
    tag = el.tag.split("}")[-1]
    kind = next((k for k, (_ru, t, _en) in EXTERNAL_WORDS.items() if t == tag), None)
    if kind is None:
        raise MetadataError(f"{where}: объект {tag}, а нужна внешняя обработка (ExternalDataProcessor) или внешний отчёт (ExternalReport)"
                            + ("; объект конфигурации читается через --config" if tag in {t for _d, t, _r, _e in KINDS.values()} else ""))
    props = el.find("m:Properties", NS)
    name = _text(props, "m:Name", where, False) if props is not None else None
    if not name:
        raise MetadataError(f"{where}: у внешнего объекта нет Properties/Name")
    generated = [g for g in el.findall("m:InternalInfo/xr:GeneratedType", NS) if g.get("category") == "Object"]
    if len(generated) != 1:
        raise MetadataError(f"{where}: у {tag} {name} {'нет' if not generated else 'несколько'} InternalInfo/xr:GeneratedType "
                            'category="Object" — тип основного реквизита взять неоткуда')
    guid = _text(generated[0], "xr:TypeId", where, False) or ""
    if not re.fullmatch(r"[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", guid):
        raise MetadataError(f"{where}: TypeId типа Object объекта {name} — {guid!r}, а не GUID")
    obj = _build_object(el, kind, where, external=True)
    return ExternalRoot(obj.name, obj.synonym, guid.lower(), kind, obj)


def load_for(config_dir=None, root_xml=None):
    """`Config` для команды с ключами `--config` и `--root-xml`: выгрузка конфигурации, внешний объект из корневого XML либо оба вместе; ничего не
    дано — `None`.

    Внешний объект входит в `Config` как обработка или отчёт (`MdObject.external`, полное имя «ВнешняяОбработка.Имя» либо «ВнешнийОтчет.Имя»;
    «Обработка.Имя» и «Отчет.Имя» его тоже называют, пока в выгрузке нет одноимённого объекта конфигурации). Объект с таким именем и в
    выгрузке, и в корневом XML — отказ «объект один»: два источника реквизитов одного объекта разошлись бы молча. Ссылочные типы реквизитов
    внешнего объекта (`cfg:CatalogRef.X`) берутся из выгрузки; без неё поле на такой реквизит отказывает словами."""
    base = load(config_dir) if config_dir is not None else None
    if root_xml is None:
        return base
    ext = external_root(root_xml).obj
    if base is None:
        return Config(str(pathlib.Path(root_xml).resolve().parent), {ext.full_name: ext}, has_dump=False)
    twin = f"{KINDS[ext.kind][2]}.{ext.name}"
    if twin in base.objects or twin in base.failed:
        raise MetadataError(f"объект «{ext.name}» назван и в выгрузке конфигурации ({twin}), и в корневом XML внешнего объекта {root_xml}: "
                            "объект один — реквизиты берутся из одного источника (уберите --root-xml или --config)")
    return Config(base.root, {**base.objects, ext.full_name: ext}, base.failed, main_language=base.main_language, extras=base.extras)
